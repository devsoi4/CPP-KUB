"""ควบคุม gdb (GDB/MI) เพื่อเดินโปรแกรมทีละบรรทัดและเก็บ Snapshot ของตัวแปรทุกครั้งที่หยุด

ลำดับงาน: คอมไพล์ด้วย Runner (-g -O0) → เปิด ``gdb --interpreter=mi3`` → break ที่ main → รัน
→ ทุกครั้งที่ ``*stopped`` ถามเฟรม/ตัวแปร/ชนิด/ที่อยู่ แล้วส่ง ``stopped(Snapshot)``

stdin ของโปรแกรมมาจากไฟล์ (ข้อมูลนำเข้าล่วงหน้า) และ stdout/stderr ถูกเขียนลงไฟล์แล้วอ่านต่อท้ายหลังหยุดทุกครั้ง
(ใช้ ``-exec-arguments < in > out 2>&1``)

หมายเหตุ: ส่วนนี้เขียนจากความรู้เรื่อง GDB/MI โดยยังไม่เคยรันกับ gdb จริงบน Windows (ยังไม่มี gdb.exe ใน
compiler\\bin ตอนพัฒนา) — งานที่ต้องตรวจเมื่อมี gdb: (1) การ redirect ``<``/``>`` ของ gdb บน Windows
ใช้ได้จริงหรือไม่ ถ้าไม่ ให้เปลี่ยนเป็นรันโปรแกรมผ่าน pipe, (2) ค่า std::string (ใช้ ``name.c_str()``)
"""
from __future__ import annotations

import codecs
import re
from collections import deque
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from ..compiler import IS_WINDOWS, NO_GDB_MSG, Runner, find_gdb, work_dir
from . import model
from .gdbmi import Record, parse_record

STEP_LIMIT = 100_000
RUN_TIMEOUT_MS = 15_000       # คำสั่งรัน/เดินที่ไม่หยุดนานเกินนี้ถือว่าวนไม่รู้จบ
MAX_FRAMES = 30
SRC_NAME = "main.cpp"          # Runner เขียนซอร์สของนักเรียนเป็นไฟล์นี้เสมอ
_STRING_VALUE = re.compile(r'"((?:[^"\\]|\\.)*)"')


class DebugSession(QObject):
    stopped = Signal(object)        # Snapshot
    output = Signal(str)            # ข้อความที่โปรแกรมพิมพ์ออกมาใหม่
    finished = Signal(int, str)     # exit code, เหตุผล: ok|crash|stopped|step_limit|timeout|gdb_died
    failed = Signal(str)            # เริ่มดีบักไม่ได้ (ไม่มี gdb ฯลฯ)

    def __init__(self, runner: Runner, parent: QObject | None = None):
        super().__init__(parent)
        self.runner = runner
        self.run_timeout_ms = RUN_TIMEOUT_MS
        self._proc: QProcess | None = None
        self._starting = False
        self._done = True
        self._busy = False
        self._buf = ""
        self._token = 0
        self._inflight: tuple[int, Callable | None] | None = None
        self._queue: deque[tuple[str | None, Callable | None]] = deque()
        self._console = ""
        self._prev: model.Snapshot | None = None
        self._steps = 0
        self._kind = ""
        self._finish_tries = 0
        self._signal: str | None = None
        self._crashed = False
        self._out_path: Path | None = None
        self._out_pos = 0
        self._dec = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._preset = ""
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        runner.compile_done.connect(self._on_compile_done)

    # ---------- สถานะ ----------
    @property
    def active(self) -> bool:
        return (not self._done) and self._proc is not None and self._proc.state() != QProcess.NotRunning

    @property
    def busy(self) -> bool:
        return self._busy

    # ---------- เริ่ม/หยุด ----------
    def start(self, source: str, preset: str = "") -> None:
        self.stop(quiet=True)
        if find_gdb() is None:
            self.failed.emit(NO_GDB_MSG)
            return
        self._reset()
        self._preset = preset
        self._starting = True
        self.runner.start(source, run_after=False)

    def _reset(self) -> None:
        self._done = False
        self._busy = True
        self._buf = ""
        self._queue.clear()
        self._inflight = None
        self._prev = None
        self._steps = 0
        self._kind = "start"
        self._finish_tries = 0
        self._signal = None
        self._crashed = False
        self._out_pos = 0
        self._dec.reset()

    def stop(self, quiet: bool = False) -> None:
        self._starting = False
        if self._done and self._proc is None:
            return
        was_active = not self._done
        self._shutdown()
        if was_active and not quiet:
            self.finished.emit(-1, "stopped")

    def _shutdown(self) -> None:
        self._done = True
        self._busy = False
        self._timer.stop()
        proc, self._proc = self._proc, None
        if proc is not None:
            try:
                proc.finished.disconnect()
            except (RuntimeError, TypeError):
                pass
            if proc.state() != QProcess.NotRunning:
                proc.kill()
                proc.waitForFinished(2000)
            proc.deleteLater()

    def _end(self, code: int, reason: str) -> None:
        if self._done:
            return
        self._shutdown()
        self.finished.emit(code, reason)

    # ---------- เปิด gdb ----------
    def _on_compile_done(self, ok: bool, _diags, _raw: str) -> None:
        if not self._starting:
            return
        self._starting = False
        exe = self.runner.exe_path
        gdb = find_gdb()
        if not ok or exe is None or gdb is None:
            self._done = True
            self._busy = False
            return
        wd = work_dir()
        in_path = wd / "debug_in.txt"
        self._out_path = wd / "debug_out.txt"
        in_path.write_text(self._preset, encoding="utf-8", newline="")
        self._out_path.write_text("", encoding="utf-8")
        proc = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        sep = ";" if IS_WINDOWS else ":"
        env.insert("PATH", str(Path(gdb).parent) + sep + env.value("PATH"))
        proc.setProcessEnvironment(env)
        proc.setWorkingDirectory(str(wd))
        if IS_WINDOWS:
            try:
                def _no_window(args):
                    args.flags |= 0x08000000  # CREATE_NO_WINDOW
                proc.setCreateProcessArgumentsModifier(_no_window)
            except Exception:
                pass
        proc.readyReadStandardOutput.connect(self._on_stdout)
        proc.finished.connect(self._on_gdb_finished)
        proc.errorOccurred.connect(self._on_gdb_error)
        self._proc = proc
        proc.start(gdb, ["--interpreter=mi3", "-q", "--nx"])
        fwd = lambda p: str(p).replace("\\", "/")  # noqa: E731
        for cmd in ("-gdb-set confirm off", "-gdb-set pagination off", "-gdb-set print pretty off",
                    f'-file-exec-and-symbols "{fwd(exe)}"',
                    f'-exec-arguments < "{fwd(in_path)}" > "{fwd(self._out_path)}" 2>&1',
                    "-break-insert -t main"):
            self._enqueue(cmd, None)
        self._enqueue("-exec-run", None)
        self._arm_timer()

    def _on_gdb_error(self, err) -> None:
        if err == QProcess.FailedToStart and not self._done:
            self._shutdown()
            self.failed.emit("เรียกใช้ gdb ไม่สำเร็จ ตรวจว่าไฟล์ gdb ไม่เสียหาย")

    def _on_gdb_finished(self, *_a) -> None:
        if self._done:
            return
        if self._kind == "start" and self._prev is None:     # ล้มก่อนหยุดที่ main เลย (เช่น ขาด DLL)
            err = ""
            if self._proc is not None:
                err = bytes(self._proc.readAllStandardError()).decode("utf-8", errors="replace").strip()
            self._shutdown()
            self.failed.emit("gdb เริ่มทำงานไม่ได้" + (f": {err}" if err else ""))
            return
        self._end(-1, "gdb_died")

    # ---------- ส่งคำสั่ง / รับผลลัพธ์ ----------
    def _enqueue(self, cmd: str | None, handler: Callable | None, front: bool = False) -> None:
        if front:
            self._queue.appendleft((cmd, handler))
        else:
            self._queue.append((cmd, handler))
        self._pump()

    def _enqueue_front(self, items: list[tuple[str | None, Callable | None]]) -> None:
        self._queue.extendleft(reversed(items))
        self._pump()

    def _pump(self) -> None:
        while self._inflight is None and self._queue and self._proc is not None:
            cmd, handler = self._queue.popleft()
            if cmd is None:
                if handler:
                    handler(None)
                continue
            self._token += 1
            self._inflight = (self._token, handler)
            self._console = ""
            self._proc.write(f"{self._token}{cmd}\n".encode("utf-8"))

    def _on_stdout(self) -> None:
        if self._proc is None:
            return
        self._buf += bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._on_record(parse_record(line))

    def _on_record(self, r: Record) -> None:
        if self._done:
            return
        if r.kind == "console":
            self._console += r.text
        elif r.kind == "result":
            if self._inflight and r.token == self._inflight[0]:
                _tok, handler = self._inflight
                self._inflight = None
                if handler:
                    handler(r)
                self._pump()
        elif r.kind == "exec" and r.cls == "stopped":
            self._on_stopped(r.data)

    # ---------- หยุดที่จุดใดจุดหนึ่ง ----------
    def _arm_timer(self) -> None:
        self._timer.start(self.run_timeout_ms)

    def _on_timeout(self) -> None:
        if not self._done and self._busy:
            self._read_output()
            self._end(-1, "timeout")

    def _issue(self, kind: str, cmd: str) -> None:
        if self._done or self._busy or self._proc is None:
            return
        self._steps += 1
        if self._steps > STEP_LIMIT:
            self._end(-1, "step_limit")
            return
        self._kind = kind
        self._finish_tries = 0
        self._busy = True
        self._arm_timer()
        self._enqueue(cmd, None)

    def step_over(self) -> None:
        self._issue("over", "-exec-next")

    def step_into(self) -> None:
        self._issue("into", "-exec-step")

    def step_out(self) -> None:
        self._issue("out", "-exec-finish")

    def resume(self) -> None:
        self._issue("continue", "-exec-continue")

    def _read_output(self) -> None:
        if self._out_path is None:
            return
        try:
            with open(self._out_path, "rb") as f:
                f.seek(self._out_pos)
                data = f.read()
        except OSError:
            return
        self._out_pos += len(data)
        text = self._dec.decode(data)
        if text:
            self.output.emit(text)

    def _on_stopped(self, data: dict) -> None:
        self._timer.stop()
        reason = data.get("reason", "")
        if reason.startswith("exited"):
            self._on_exited(reason, data)
            return
        frame = data.get("frame", {}) or {}
        in_user = Path(frame.get("file", "") or frame.get("fullname", "")).name.lower() == SRC_NAME
        if reason == "signal-received":
            self._signal = data.get("signal-name", "SIGSEGV")
            self._crashed = True
        elif not in_user:                # ตกไปในโค้ดไลบรารี → ออกมา/รันต่อ ไม่ให้นักเรียนเห็น
            self._busy = True
            self._arm_timer()
            if self._kind == "into" and self._finish_tries < 5:
                self._finish_tries += 1
                self._enqueue("-exec-finish", None)
            else:
                self._enqueue("-exec-continue", None)
            return
        self._collect()

    def _on_exited(self, reason: str, data: dict) -> None:
        self._read_output()
        code = 0
        if reason == "exited":
            try:
                code = int(data.get("exit-code", "0"), 8)
            except ValueError:
                code = 0
        crashed = reason == "exited-signalled" or self._crashed
        snap = model.Snapshot([], exited=True, exit_code=code)
        self._busy = False
        self.stopped.emit(snap)
        self._end(code, "crash" if crashed else "ok")

    # ---------- เก็บ Snapshot ----------
    def _collect(self) -> None:
        frames: list[model.Frame] = []

        def on_frames(r: Record | None) -> None:
            stack = (r.data.get("stack", []) if r and r.cls == "done" else [])
            items: list[tuple[str | None, Callable | None]] = []
            for fr in stack:
                if Path(fr.get("file", "") or fr.get("fullname", "")).name.lower() != SRC_NAME:
                    continue
                lvl = fr.get("level", "0")
                items.append((f"-stack-list-variables --thread 1 --frame {lvl} --all-values",
                              self._on_vars(fr, frames)))
            items.append((None, finalize))
            self._enqueue_front(items)

        def finalize(_r) -> None:
            snap = model.Snapshot(frames, signal=self._signal)
            model.resolve_pointer_targets(snap)
            items: list[tuple[str | None, Callable | None]] = []
            for fr in snap.frames:
                for var in fr.args + fr.locals:
                    if self._wants_pointee(var):
                        items.append((f'-data-evaluate-expression --thread 1 --frame {fr.level} "*{var.name}"',
                                      self._on_pointee(var)))
            items.append((None, lambda _r2: emit(snap)))
            self._enqueue_front(items)

        def emit(snap: model.Snapshot) -> None:
            model.mark_changes(self._prev, snap)
            self._prev = snap
            self._busy = False
            self._read_output()
            self.stopped.emit(snap)

        self._enqueue(f"-stack-list-frames 0 {MAX_FRAMES - 1}", on_frames)

    def _on_vars(self, fr: dict, frames: list[model.Frame]) -> Callable:
        lvl = fr.get("level", "0")

        def handler(r: Record | None) -> None:
            raw = [dict(v) for v in (r.data.get("variables", []) if r and r.cls == "done" else [])]
            items: list[tuple[str | None, Callable | None]] = []
            for v in raw:
                name = v.get("name", "")
                base = f"--thread 1 --frame {lvl}"
                items.append((f'-interpreter-exec {base} console "whatis {name}"',
                              lambda _r, v=v: v.__setitem__("type", self._type_from_console())))
                items.append((f'-data-evaluate-expression {base} "&{name}"',
                              lambda r2, v=v: v.__setitem__("addr", _int_value(r2))))
                items.append((f'-data-evaluate-expression {base} "sizeof({name})"',
                              lambda r2, v=v: v.__setitem__("size", _int_value(r2))))
                items.append((None, lambda _r, v=v, base=base: self._maybe_string(v, base)))
            items.append((None, lambda _r: self._frame_done(fr, raw, frames)))
            self._enqueue_front(items)

        return handler

    @staticmethod
    def _wants_pointee(var: model.Var) -> bool:
        """pointer ที่ชี้ออกนอกตัวแปรที่รู้จัก (เช่น heap) และไม่ใช่ char* → อ่านค่าที่ชี้เพื่อวาดกล่อง heap"""
        return (var.kind == "pointer" and var.points_to is None and bool(var.target) and not var.unreadable
                and not var.type.replace("const", "").strip().startswith("char"))

    @staticmethod
    def _on_pointee(var: model.Var) -> Callable:
        def handler(r: Record | None) -> None:
            if r is not None and r.cls == "done":
                var.pointee = str(r.data.get("value", ""))
            else:
                var.pointee = model.UNREADABLE_POINTEE
        return handler

    def _type_from_console(self) -> str:
        m = re.search(r"type = (.*)", self._console)
        return m.group(1).strip() if m else ""

    def _maybe_string(self, v: dict, base: str) -> None:
        """std::string: gdb ไม่มี pretty printer ในตัว จึงถามเนื้อความด้วย c_str()"""
        if not re.match(r"std::(__cxx11::)?basic_string", v.get("type", "")):
            return

        def on_str(r: Record | None) -> None:
            if r and r.cls == "done":
                m = _STRING_VALUE.search(r.data.get("value", ""))
                if m:
                    v["value"] = '"' + m.group(1) + '"'

        self._enqueue_front([(f'-data-evaluate-expression {base} "{v["name"]}.c_str()"', on_str)])

    def _frame_done(self, fr: dict, raw: list[dict], frames: list[model.Frame]) -> None:
        frame = model.build_frame(fr, raw)
        by_name = {v.get("name"): v for v in raw}
        for var in frame.args + frame.locals:
            src = by_name.get(var.name, {})
            var.address = src.get("addr")
            var.size = src.get("size")
        frames.append(frame)


def _int_value(r: Record | None) -> int | None:
    """ค่าจาก -data-evaluate-expression เช่น ``(int *) 0x61ff08`` หรือ ``4`` → int (None ถ้าอ่านไม่ได้)"""
    if r is None or r.cls != "done":
        return None
    text = str(r.data.get("value", ""))
    m = re.search(r"0x[0-9a-fA-F]+", text) or re.search(r"-?\d+", text)
    if not m:
        return None
    try:
        return int(m.group(0), 0)
    except ValueError:
        return None
