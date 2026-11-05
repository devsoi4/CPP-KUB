"""คอมไพล์และรันโค้ด C++ ด้วย g++ (หรือ clang++) พร้อมรองรับภาษาไทย (UTF-8)

หลักการสำคัญ:
- เขียนซอร์สเป็น UTF-8 และสั่งคอมไพล์ด้วย -finput-charset/-fexec-charset=UTF-8
  ทำให้ cout << "สวัสดี" และ cin >> ชื่อ ทำงานผ่าน pipe ได้ตรงกันทุกระบบ
- ใช้โฟลเดอร์ทำงานที่เป็น ASCII เสมอ (เพราะ MinGW บางรุ่นเปิดพาธภาษาไทยไม่ได้)
- ใส่ prelude ที่ทำให้ stdout ไม่ถูก buffer เพื่อให้ข้อความถามก่อนรับ input แสดงทันที
"""
from __future__ import annotations

import codecs
import os
import shutil
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from . import errors_th

IS_WINDOWS = sys.platform == "win32"
EXE_NAME = "main.exe" if IS_WINDOWS else "main"

RUN_IDLE_TIMEOUT_MS = 15_000     # ไม่มีการป้อน input ใหม่นานเกินนี้ → หยุดโปรแกรม
COMPILE_TIMEOUT_MS = 60_000
OUTPUT_LIMIT_CHARS = 200_000     # กันโปรแกรมที่พิมพ์ไม่หยุด

PRELUDE_H = """\
// สร้างโดย CPP-KUB: ทำให้ stdout/stderr ไม่ถูก buffer
#include <cstdio>
#include <iostream>
namespace {
struct CppLearnInit {
    CppLearnInit() {
        std::setvbuf(stdout, nullptr, _IONBF, 0);
        std::setvbuf(stderr, nullptr, _IONBF, 0);
    }
};
static CppLearnInit cpplearn_init_instance;
}
"""

NO_COMPILER_MSG = (
    "ไม่พบตัวคอมไพล์ C++ (g++)\n"
    "• ถ้าเป็นเวอร์ชันแจกจ่าย ให้ตรวจว่าโฟลเดอร์ 'compiler' อยู่ข้างไฟล์โปรแกรมครบถ้วน\n"
    "• หรือติดตั้ง MinGW-w64 / MSYS2 แล้วเพิ่ม g++ ใน PATH"
)

NO_GDB_MSG = (
    "ไม่พบตัวดีบั๊ก (gdb) จึงใช้ตัวช่วยมองเห็นการทำงานไม่ได้\n"
    "• ถ้าเป็นเวอร์ชันแจกจ่าย ให้ใส่ gdb.exe ไว้ในโฟลเดอร์ 'compiler\\bin' (MinGW-w64 แบบเต็มมี gdb ให้)\n"
    "• หรือติดตั้ง MinGW-w64 / MSYS2 ที่มี gdb แล้วเพิ่มใน PATH"
)


def app_dir() -> Path:
    """โฟลเดอร์ของโปรแกรม (รองรับทั้งรันด้วย python และแพ็กด้วย PyInstaller)"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def find_compiler() -> str | None:
    """หา g++ โดยดูตัวที่แพ็กมากับโปรแกรมก่อน แล้วค่อยหาใน PATH"""
    exe = "g++.exe" if IS_WINDOWS else "g++"
    bundled = app_dir() / "compiler" / "bin" / exe
    if bundled.is_file():
        return str(bundled)
    for name in ("g++", "clang++"):
        found = shutil.which(name)
        if found:
            return found
    return None


def find_gdb() -> str | None:
    """หา gdb โดยดูตัวที่แพ็กมากับโปรแกรมก่อน แล้วค่อยหาใน PATH"""
    exe = "gdb.exe" if IS_WINDOWS else "gdb"
    bundled = app_dir() / "compiler" / "bin" / exe
    if bundled.is_file():
        return str(bundled)
    return shutil.which("gdb")


def _is_ascii(path: Path) -> bool:
    try:
        str(path).encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def work_dir() -> Path:
    """โฟลเดอร์ทำงานแบบ ASCII ที่เขียนได้ (ตัดปัญหาชื่อผู้ใช้/โฟลเดอร์ภาษาไทย)"""
    candidates = [app_dir() / "work"]
    if IS_WINDOWS:
        candidates.append(Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "CPP-KUB")
        candidates.append(Path(os.environ.get("SystemDrive", "C:") + "\\") / "CPP-KUB")
    candidates.append(Path(tempfile.gettempdir()) / "cpp_learn")
    fallback: Path | None = None
    for d in candidates:
        try:
            d.mkdir(parents=True, exist_ok=True)
            probe = d / ".write_test"
            probe.write_text("x", encoding="utf-8")
            probe.unlink()
        except OSError:
            continue
        if _is_ascii(d):
            return d
        fallback = fallback or d
    if fallback:
        return fallback
    raise OSError("ไม่พบโฟลเดอร์ที่เขียนไฟล์ได้สำหรับคอมไพล์")


def build_args(src: Path, exe: Path, prelude: Path, std: str = "c++17") -> list[str]:
    args = [
        f"-std={std}", "-Wall", "-Wextra", "-g", "-O0",
        "-finput-charset=UTF-8", "-fexec-charset=UTF-8",
        "-fdiagnostics-color=never",
        "-include", str(prelude),
        str(src), "-o", str(exe),
    ]
    if IS_WINDOWS:
        args.insert(0, "-static")  # ไม่ต้องพึ่ง DLL ของ MinGW ตอนรัน
    return args


def describe_exit(code: int, crashed: bool) -> str | None:
    """แปลรหัสออกที่ผิดปกติเป็นคำอธิบายภาษาไทย (คืน None ถ้าปกติ)"""
    win = {
        0xC0000005: "เข้าถึงหน่วยความจำผิดพลาด (access violation) — มักเกิดจากดัชนี array เกินขอบเขต "
                    "หรือ pointer ที่ไม่ได้ชี้ไปที่ใด",
        0xC0000094: "หารด้วยศูนย์ (integer divide by zero)",
        0xC00000FD: "stack เต็ม (stack overflow) — มักเกิดจากฟังก์ชัน recursion ที่ไม่มีเงื่อนไขหยุด",
        0xC0000374: "หน่วยความจำถูกทำให้เสียหาย (heap corruption)",
        0xC0000409: "โปรแกรมถูกหยุดจากการตรวจพบความผิดปกติ (abort / buffer overrun)",
    }
    posix = {
        11: "เข้าถึงหน่วยความจำผิดพลาด (segmentation fault) — มักเกิดจากดัชนี array เกินขอบเขต "
            "pointer ผิด หรือ recursion ลึกเกินไป",
        8: "คำนวณผิดพลาด เช่น หารด้วยศูนย์ (floating point exception)",
        6: "โปรแกรมถูกยกเลิก (abort) เช่น exception ที่ไม่ได้จับ หรือ assert ล้มเหลว",
    }
    unsigned = code & 0xFFFFFFFF
    if unsigned in win:
        return win[unsigned]
    if crashed and code in posix:
        return posix[code]
    return None


class Runner(QObject):
    """ควบคุมวงจร คอมไพล์ → รัน → รับ/ส่งข้อมูล"""

    compile_started = Signal()
    compile_done = Signal(bool, object, str)   # ok, list[Diagnostic], raw stderr
    problem = Signal(str)                      # ปัญหาที่ไม่ใช่ error ของโค้ด เช่น ไม่พบ g++
    run_started = Signal()
    output = Signal(str, bool)                 # ข้อความ, เป็น stderr หรือไม่
    run_finished = Signal(int, str)            # exit code, เหตุผล

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._cc: QProcess | None = None
        self._proc: QProcess | None = None
        self._reason = "ok"
        self._out_chars = 0
        self._dec_out = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._dec_err = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.timeout.connect(self._on_idle_timeout)
        self._cc_timer = QTimer(self)
        self._cc_timer.setSingleShot(True)
        self._cc_timer.timeout.connect(self._on_compile_timeout)
        self.idle_timeout_ms = RUN_IDLE_TIMEOUT_MS
        self._cc_cancelled = False
        self._run_after = True
        self._exe: Path | None = None

    # ---------- สถานะ ----------
    @property
    def exe_path(self) -> Path | None:
        """พาธของไฟล์ที่คอมไพล์ล่าสุด (None ถ้ายังไม่เคยคอมไพล์)"""
        return self._exe

    @property
    def is_compiling(self) -> bool:
        return self._cc is not None and self._cc.state() != QProcess.NotRunning

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.state() != QProcess.NotRunning

    @property
    def busy(self) -> bool:
        return self.is_compiling or self.is_running

    # ---------- คอมไพล์ ----------
    def start(self, source: str, *, run_after: bool = True) -> None:
        self.stop()
        cc = find_compiler()
        if not cc:
            self.problem.emit(NO_COMPILER_MSG)
            return
        try:
            wd = work_dir()
            src = wd / "main.cpp"
            src.write_text(source, encoding="utf-8", newline="\n")
            prelude = wd / "cpplearn_prelude.h"
            prelude.write_text(PRELUDE_H, encoding="utf-8", newline="\n")
            exe = wd / EXE_NAME
            if exe.exists():
                exe.unlink()
        except OSError as e:
            self.problem.emit(f"เขียนไฟล์ชั่วคราวไม่สำเร็จ: {e}")
            return

        self._run_after = run_after
        self._exe = exe
        self._wd = wd
        proc = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("LC_ALL", "C")        # ให้ g++ พิมพ์ error เป็นภาษาอังกฤษเสมอ
        env.insert("LANGUAGE", "C")
        cc_dir = str(Path(cc).parent)
        sep = ";" if IS_WINDOWS else ":"
        env.insert("PATH", cc_dir + sep + env.value("PATH"))
        proc.setProcessEnvironment(env)
        proc.setWorkingDirectory(str(wd))
        proc.finished.connect(self._on_compile_finished)
        proc.errorOccurred.connect(self._on_compile_error)
        self._cc = proc
        self._cc_cancelled = False
        self.compile_started.emit()
        self._cc_timer.start(COMPILE_TIMEOUT_MS)
        proc.start(cc, build_args(src, exe, prelude))

    def _on_compile_timeout(self) -> None:
        if self.is_compiling:
            self._cc_cancelled = True    # กัน compile_done ซ้ำหลัง kill
            self._cc.kill()
            self.problem.emit("คอมไพล์นานเกินไป จึงยกเลิก")

    def _on_compile_error(self, err) -> None:
        if err == QProcess.FailedToStart:
            self._cc_timer.stop()
            self.problem.emit("เรียกใช้ g++ ไม่สำเร็จ ตรวจว่าไฟล์ตัวคอมไพล์ไม่เสียหาย")

    def _on_compile_finished(self, code: int, _status) -> None:
        self._cc_timer.stop()
        if self._cc_cancelled:
            return
        raw = bytes(self._cc.readAllStandardError()).decode("utf-8", errors="replace")
        raw += bytes(self._cc.readAllStandardOutput()).decode("utf-8", errors="replace")
        diags = errors_th.parse_output(raw)
        ok = code == 0 and self._exe.exists()
        self.compile_done.emit(ok, diags, raw)
        if ok and self._run_after:
            self._run()

    # ---------- รัน ----------
    def _run(self) -> None:
        self._reason = "ok"
        self._out_chars = 0
        self._dec_out.reset()
        self._dec_err.reset()
        proc = QProcess(self)
        proc.setWorkingDirectory(str(self._wd))
        if IS_WINDOWS:
            try:  # ไม่ให้หน้าต่าง console ดำเด้งขึ้นมา
                def _no_window(args):
                    args.flags |= 0x08000000  # CREATE_NO_WINDOW
                proc.setCreateProcessArgumentsModifier(_no_window)
            except Exception:
                pass
        proc.readyReadStandardOutput.connect(lambda: self._drain(False))
        proc.readyReadStandardError.connect(lambda: self._drain(True))
        proc.finished.connect(self._on_run_finished)
        proc.errorOccurred.connect(self._on_run_error)
        self._proc = proc
        self._idle.start(self.idle_timeout_ms)
        proc.start(str(self._exe), [])
        # ต้องส่งสัญญาณหลัง start() เพราะผู้รับมักส่ง stdin ทันที (QProcess เก็บข้อมูลไว้ส่งเมื่อโปรเซสพร้อม)
        self.run_started.emit()

    def _drain(self, is_err: bool) -> None:
        proc = self._proc
        if proc is None:
            return
        data = bytes(proc.readAllStandardError() if is_err else proc.readAllStandardOutput())
        text = (self._dec_err if is_err else self._dec_out).decode(data).replace("\r", "")
        if not text:
            return
        self._out_chars += len(text)
        self.output.emit(text, is_err)
        if self._out_chars > OUTPUT_LIMIT_CHARS and self._reason == "ok":
            self._reason = "output_limit"
            proc.kill()

    def send_input(self, text: str) -> None:
        """ส่งข้อความ (UTF-8) เข้า stdin ของโปรแกรมที่กำลังรัน"""
        if self.is_running:
            self._proc.write(text.encode("utf-8"))
            self._idle.start(self.idle_timeout_ms)   # เริ่มนับเวลาใหม่

    def close_input(self) -> None:
        """ส่ง EOF (เหมือนกด Ctrl+Z / Ctrl+D)"""
        if self.is_running:
            self._proc.closeWriteChannel()

    def _on_idle_timeout(self) -> None:
        if self.is_running:
            self._reason = "timeout"
            self._proc.kill()

    def _on_run_error(self, err) -> None:
        if err == QProcess.FailedToStart:
            self._idle.stop()
            self.problem.emit("เปิดโปรแกรมที่คอมไพล์แล้วไม่สำเร็จ (อาจถูกโปรแกรมป้องกันไวรัสบล็อก)")

    def _on_run_finished(self, code: int, status) -> None:
        self._idle.stop()
        self._drain(False)
        self._drain(True)
        crashed = status == QProcess.CrashExit
        reason = self._reason
        if reason == "ok":
            if describe_exit(code, crashed):
                reason = "crash"
            elif crashed:
                reason = "crash"
        self.run_finished.emit(code, reason)

    # ---------- หยุด ----------
    def stop(self) -> None:
        """หยุดทุกอย่างที่กำลังทำอยู่ (ผู้ใช้กด Stop)"""
        self._idle.stop()
        self._cc_timer.stop()
        if self.is_compiling:
            self._cc_cancelled = True
            self._cc.kill()
            self._cc.waitForFinished(1000)
        if self.is_running:
            self._reason = "stopped"
            self._proc.kill()
            self._proc.waitForFinished(1000)
