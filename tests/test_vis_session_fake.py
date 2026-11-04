"""ทดสอบลำดับการทำงานของ DebugSession ด้วย gdb ปลอม (สคริปต์ Python ตอบเป็น GDB/MI) — ไม่ต้องมี gdb จริง

ใช้ g++ จริงคอมไพล์ แล้วให้ find_gdb() ชี้ไปที่ตัวห่อของ gdb ปลอม
"""
import os
import stat
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from app import compiler  # noqa: E402
from app.compiler import Runner  # noqa: E402
from app.visualizer import session as session_mod  # noqa: E402
from test_vis_session import LOOP_SRC, Rec, qapp, wait_until  # noqa: E402,F401

FAKE_GDB = r'''
import os, re, sys
step = {"n": 0}
def out(s):
    sys.stdout.write(s + "\n"); sys.stdout.flush()
def stop(line):
    out('*stopped,reason="end-stepping-range",frame={func="main",file="main.cpp",line="%d"}' % line)
for raw in sys.stdin:
    m = re.match(r"(\d+)(.*)", raw.strip())
    if not m:
        continue
    tok, cmd = m.group(1), m.group(2)
    if os.environ.get("FAKE_GDB_LOG"):
        open(os.environ["FAKE_GDB_LOG"], "a", encoding="utf-8").write(cmd + "\n")
    if cmd.startswith("-exec-run"):
        out(tok + "^running")
        if os.environ.get("FAKE_GDB_SILENT"):
            continue
        out('*stopped,reason="breakpoint-hit",frame={func="main",file="main.cpp",line="3"}')
    elif cmd.startswith("-exec-continue") and os.environ.get("FAKE_GDB_WIN_CRASH"):
        # Windows: SIGSEGV แจ้ง 2 รอบ (first/second chance) แล้วรอบที่ 3 โปรแกรมจึงจบ
        out(tok + "^running")
        step["n"] += 1
        if step["n"] <= 2:
            out('*stopped,reason="signal-received",signal-name="SIGSEGV",frame={func="main",file="main.cpp",line="3"}')
        else:
            out('*stopped,reason="exited-signalled",signal-name="SIGSEGV"')
    elif cmd.startswith("-exec-next") or cmd.startswith("-exec-continue"):
        out(tok + "^running")
        step["n"] += 1
        if step["n"] >= 3 or cmd.startswith("-exec-continue"):
            out('*stopped,reason="exited-normally"')
        else:
            stop(3 + step["n"])
    elif cmd.startswith("-exec-finish") and os.environ.get("FAKE_GDB_ERROR_FINISH"):
        out(tok + '^error,msg="Cannot finish"')
    elif cmd.startswith("-stack-list-frames"):
        if os.environ.get("FAKE_GDB_HANG_FRAMES"):
            continue
        line = 3 + step["n"]
        out(tok + '^done,stack=[frame={level="0",func="main",file="main.cpp",line="%d"},'
            'frame={level="1",func="__libc_start_main",file="crt.c",line="9"}]' % line)
    elif cmd.startswith("-stack-list-variables"):
        out(tok + '^done,variables=[{name="sum",value="%d"},{name="a",value="{1, 2, 3}"},{name="p",value="0x900"},{name="q",value="0x61ff14"}]' % step["n"])
    elif "whatis a" in cmd:
        out('~"type = int [3]\\n"'); out(tok + "^done")
    elif "whatis p" in cmd or "whatis q" in cmd:
        out('~"type = int *\\n"'); out(tok + "^done")
    elif "whatis" in cmd:
        out('~"type = int\\n"'); out(tok + "^done")
    elif "&sum" in cmd:
        out(tok + '^done,value="(int *) 0x61ff08"')
    elif "&a" in cmd:
        out(tok + '^done,value="(int (*)[3]) 0x61ff10"')
    elif "&p" in cmd:
        out(tok + '^done,value="(int **) 0x61ff20"')
    elif "&q" in cmd:
        out(tok + '^done,value="(int **) 0x61ff28"')
    elif "sizeof(p)" in cmd or "sizeof(q)" in cmd:
        out(tok + '^done,value="8"')
    elif '"*p"' in cmd:
        out(tok + '^done,value="7"')
    elif "sizeof(sum)" in cmd:
        out(tok + '^done,value="4"')
    elif "sizeof(a)" in cmd:
        out(tok + '^done,value="12"')
    else:
        out(tok + "^done")
'''


@pytest.fixture
def fake_gdb(tmp_path, monkeypatch):
    script = tmp_path / "fake_gdb.py"
    script.write_text(FAKE_GDB, encoding="utf-8")
    if sys.platform == "win32":
        wrapper = tmp_path / "fake_gdb.bat"
        wrapper.write_text(f'@"{sys.executable}" "{script}"\r\n', encoding="utf-8")
    else:
        wrapper = tmp_path / "fake_gdb.sh"
        wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}"\n', encoding="utf-8")
        wrapper.chmod(wrapper.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(session_mod, "find_gdb", lambda: str(wrapper))
    return wrapper


needs_gpp = pytest.mark.skipif(compiler.find_compiler() is None, reason="ไม่มี g++")


@needs_gpp
def test_start_stops_at_main_with_variables(qapp, fake_gdb):
    r = Rec(Runner())
    try:
        s = r.start(LOOP_SRC)
        assert (s.line, s.func) == (3, "main")
        assert [f.func for f in s.frames] == ["main"]          # เฟรมของไลบรารีถูกกรองออก
        sm = next(v for v in s.frames[0].locals if v.name == "sum")
        assert (sm.type, sm.address, sm.size) == ("int", 0x61FF08, 4)
        a = next(v for v in s.frames[0].locals if v.name == "a")
        assert a.kind == "array" and [c.value for c in a.children] == ["1", "2", "3"]
        assert (a.address, a.size) == (0x61FF10, 12)
    finally:
        r.session.stop()


@needs_gpp
def test_step_changes_marked_then_exit(qapp, fake_gdb):
    r = Rec(Runner())
    try:
        r.start(LOOP_SRC)
        s = r.step("step_over")
        assert s.line == 4
        assert next(v for v in s.frames[0].locals if v.name == "sum").changed is True
        r.step("step_over")
        r.session.step_over()
        assert wait_until(lambda: r.fin)
        assert r.snaps[-1].exited is True and r.snaps[-1].frames == []
        assert r.fin[-1] == (0, "ok")
        assert r.session.active is False
    finally:
        r.session.stop()


@needs_gpp
def test_ignores_step_while_busy_and_stop_reports_stopped(qapp, fake_gdb):
    r = Rec(Runner())
    r.start(LOOP_SRC)
    r.session.stop()
    assert r.fin[-1] == (-1, "stopped") and r.session.active is False
    r.session.step_over()                                       # หลังหยุดแล้วต้องไม่ทำอะไร/ไม่พัง
    assert len(r.snaps) == 1


@needs_gpp
def test_gdb_that_dies_at_startup_reports_its_error(qapp, tmp_path, monkeypatch):
    script = tmp_path / "dead_gdb.py"
    script.write_text('import sys\nsys.stderr.write("error while loading shared libraries: libpython3.9.dll\n")\nsys.exit(127)\n',
                      encoding="utf-8")
    if sys.platform == "win32":
        wrapper = tmp_path / "dead_gdb.bat"
        wrapper.write_text(f'@"{sys.executable}" "{script}"\r\n', encoding="utf-8")
    else:
        wrapper = tmp_path / "dead_gdb.sh"
        wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}"\n', encoding="utf-8")
        wrapper.chmod(wrapper.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(session_mod, "find_gdb", lambda: str(wrapper))
    r = Rec(Runner())
    r.session.start(LOOP_SRC)
    assert wait_until(lambda: r.failed)
    assert "libpython3.9.dll" in r.failed[0]
    assert r.fin == [] and r.session.active is False


@needs_gpp
def test_pointers_resolved_and_heap_pointee_read(qapp, fake_gdb):
    from app.visualizer.model import PointsTo
    r = Rec(Runner())
    try:
        s = r.start(LOOP_SRC)
        by = {v.name: v for v in s.frames[0].locals}
        assert by["p"].kind == "pointer" and by["p"].target == 0x900
        assert by["p"].points_to is None and by["p"].pointee == "7"          # ชี้ heap/ที่ไม่รู้จัก → อ่านค่าที่ชี้
        assert by["q"].points_to == PointsTo(0, "a", 1)                      # 0x61ff14 = a[1] (a เริ่มที่ 0x61ff10 ช่องละ 4 ไบต์)
    finally:
        r.session.stop()


# ---------- แก้ตามผลตรวจทั้ง branch ----------
@needs_gpp
def test_startup_commands_redirect_with_set_args_and_use_utf8(qapp, fake_gdb, tmp_path, monkeypatch):
    log = tmp_path / "cmds.log"
    monkeypatch.setenv("FAKE_GDB_LOG", str(log))
    r = Rec(Runner())
    try:
        r.start(LOOP_SRC)
        cmds = log.read_text(encoding="utf-8").splitlines()
    finally:
        r.session.stop()
    assert any(c.startswith("-gdb-set args <") and "2>&1" in c for c in cmds)
    assert not any(c.startswith("-exec-arguments") for c in cmds)
    for want in ("-gdb-set host-charset UTF-8", "-gdb-set target-charset UTF-8", "-gdb-set print elements 200"):
        assert want in cmds


@needs_gpp
def test_gdb_silent_at_startup_reports_failed_not_timeout(qapp, fake_gdb, monkeypatch):
    monkeypatch.setenv("FAKE_GDB_SILENT", "1")
    r = Rec(Runner())
    r.session.run_timeout_ms = 1500
    r.session.start(LOOP_SRC)
    assert wait_until(lambda: r.failed)
    assert "gdb" in r.failed[0] and r.fin == [] and r.session.active is False


@needs_gpp
def test_hang_while_collecting_snapshot_times_out(qapp, fake_gdb, monkeypatch):
    monkeypatch.setenv("FAKE_GDB_HANG_FRAMES", "1")
    r = Rec(Runner())
    r.session.run_timeout_ms = 1500
    r.session.start(LOOP_SRC)
    assert wait_until(lambda: r.fin)
    assert r.fin == [(-1, "timeout")] and r.failed == []


@needs_gpp
def test_exec_error_frees_the_session(qapp, fake_gdb, monkeypatch):
    monkeypatch.setenv("FAKE_GDB_ERROR_FINISH", "1")
    r = Rec(Runner())
    errors = []
    r.session.step_error.connect(errors.append)
    try:
        r.start(LOOP_SRC)
        r.session.step_out()
        assert wait_until(lambda: errors)
        assert "Cannot finish" in errors[0]
        assert r.session.busy is False and r.session.active is True
        r.step("step_over")                                  # ยังเดินต่อได้
    finally:
        r.session.stop()


@needs_gpp
def test_second_chance_signal_is_skipped_and_resume_ends_as_crash(qapp, fake_gdb, monkeypatch):
    monkeypatch.setenv("FAKE_GDB_WIN_CRASH", "1")
    r = Rec(Runner())
    try:
        r.start(LOOP_SRC)
        r.session.resume()
        assert wait_until(lambda: any(sn.signal for sn in r.snaps))
        r.session.resume()                                   # กดครั้งเดียวต้องจบ ไม่หยุดซ้ำที่ SIGSEGV เดิม
        assert wait_until(lambda: r.fin)
        assert r.fin == [(0, "crash")]
        assert sum(1 for sn in r.snaps if sn.signal) == 1
    finally:
        r.session.stop()


@needs_gpp
def test_unwritable_work_dir_reports_failed(qapp, fake_gdb, monkeypatch):
    def boom():
        raise OSError("disk full")
    monkeypatch.setattr(session_mod, "work_dir", boom)
    r = Rec(Runner())
    r.session.start(LOOP_SRC)
    assert wait_until(lambda: r.failed)
    assert "disk full" in r.failed[0] and r.session.active is False
