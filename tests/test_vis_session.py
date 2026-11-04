"""ทดสอบ DebugSession กับ gdb จริง (ข้ามอัตโนมัติถ้าไม่มี gdb)"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app import compiler  # noqa: E402
from app.compiler import NO_GDB_MSG, Runner  # noqa: E402
from app.visualizer import session as session_mod  # noqa: E402
from app.visualizer.session import DebugSession  # noqa: E402

def _gdb_runs() -> bool:
    """มี gdb และรันได้จริง (gdb.exe ที่ขาด DLL เช่น libpython จะรันไม่ขึ้น)"""
    import subprocess
    gdb = compiler.find_gdb()
    if gdb is None:
        return False
    try:
        return subprocess.run([gdb, "--version"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


needs_gdb = pytest.mark.skipif(
    not (compiler.find_compiler() and _gdb_runs()), reason="ไม่มี gdb ที่รันได้ หรือไม่มี g++")

LOOP_SRC = """#include <iostream>
int main() {
    int a[3] = {10, 20, 30};
    int sum = 0;
    for (int i = 0; i < 3; i++) {
        sum += a[i];
    }
    std::cout << sum << "\\n";
    return 0;
}
"""

POINTER_SRC = """#include <iostream>
int main() {
    int x = 5;
    int *p = &x;
    *p = 9;
    std::cout << x << "\\n";
    return 0;
}
"""

FACT_SRC = """#include <iostream>
int fact(int n) {
    if (n <= 1) return 1;
    return n * fact(n - 1);
}
int main() {
    std::cout << fact(3) << "\\n";
    return 0;
}
"""

CRASH_SRC = """int main() {
    int *p = nullptr;
    *p = 1;
    return 0;
}
"""

THAI_SRC = """#include <iostream>
int main() {
    std::cout << "สวัสดี\\n";
    return 0;
}
"""


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def wait_until(cond, timeout_ms=30000):
    loop = QEventLoop()
    t = QTimer()
    t.setInterval(30)
    deadline = QTimer()
    deadline.setSingleShot(True)
    t.timeout.connect(lambda: cond() and loop.quit())
    deadline.timeout.connect(loop.quit)
    t.start()
    deadline.start(timeout_ms)
    loop.exec()
    t.stop()
    return cond()


class Rec:
    """เก็บสัญญาณทั้งหมดของ session"""

    def __init__(self, runner):
        self.session = DebugSession(runner)
        self.snaps, self.out, self.fin, self.failed = [], "", [], []
        s = self.session
        s.stopped.connect(self.snaps.append)
        s.output.connect(lambda t: setattr(self, "out", self.out + t))
        s.finished.connect(lambda c, r: self.fin.append((c, r)))
        s.failed.connect(self.failed.append)

    def start(self, src, preset=""):
        self.session.start(src, preset)
        assert wait_until(lambda: self.snaps or self.failed), "ไม่ได้หยุดที่ main"
        return self.snaps[-1]

    def step(self, name, n=1):
        for _ in range(n):
            before = len(self.snaps)
            getattr(self.session, name)()
            assert wait_until(lambda: len(self.snaps) > before), f"{name} ไม่หยุด"
        return self.snaps[-1]


@pytest.fixture
def rec(qapp):
    r = Rec(Runner())
    yield r
    r.session.stop()


def local(snap, name, frame=0):
    f = snap.frames[frame]
    return next(v for v in f.args + f.locals if v.name == name)


def test_no_gdb_emits_failed(qapp, monkeypatch):
    monkeypatch.setattr(session_mod, "find_gdb", lambda: None)
    r = Rec(Runner())
    r.session.start(LOOP_SRC)
    assert r.failed == [NO_GDB_MSG]
    assert r.session.active is False


@needs_gdb
def test_loop_stepping(rec):
    s = rec.start(LOOP_SRC)
    assert (s.line, s.func) == (3, "main")
    s = rec.step("step_over", 2)
    assert s.line == 5
    a = local(s, "a")
    assert a.kind == "array" and [c.value for c in a.children] == ["10", "20", "30"]
    s = rec.step("step_over", 2)
    sm = local(s, "sum")
    assert sm.value == "10" and sm.changed is True
    rec.session.resume()
    assert wait_until(lambda: rec.fin)
    assert rec.fin[-1] == (0, "ok")
    assert "60" in rec.out


@needs_gdb
def test_pointer_target(rec):
    rec.start(POINTER_SRC)
    s = rec.step("step_over", 2)
    assert s.line == 5
    p, x = local(s, "p"), local(s, "x")
    assert p.kind == "pointer" and p.target == x.address


@needs_gdb
def test_recursion_stack(rec):
    rec.start(FACT_SRC)
    rec.step("step_over", 0)
    s = rec.step("step_into")
    assert [f.func for f in s.frames] == ["fact", "main"]
    assert local(s, "n").value == "3"
    rec.step("step_over")
    s = rec.step("step_into")
    assert len(s.frames) == 3 and local(s, "n").value == "2"


@needs_gdb
def test_crash_reports_signal(rec):
    rec.start(CRASH_SRC)
    rec.session.resume()
    assert wait_until(lambda: any(sn.signal for sn in rec.snaps))
    rec.session.resume()
    assert wait_until(lambda: rec.fin)
    assert rec.fin[-1][1] == "crash"


@needs_gdb
def test_thai_output(rec):
    rec.start(THAI_SRC)
    rec.session.resume()
    assert wait_until(lambda: rec.fin)
    assert rec.out == "สวัสดี\n"


@needs_gdb
def test_preset_input_feeds_cin(rec):
    src = '#include <iostream>\nint main() {\n    int n;\n    std::cin >> n;\n    std::cout << n * 2;\n}\n'
    rec.start(src, preset="21\n")
    rec.session.resume()
    assert wait_until(lambda: rec.fin)
    assert rec.out.strip() == "42"


@needs_gdb
def test_stop_kills_gdb(rec):
    rec.start(LOOP_SRC)
    rec.session.stop()
    assert rec.session.active is False
    assert rec.fin[-1] == (-1, "stopped")


@needs_gdb
def test_runaway_continue_is_killed(rec):
    rec.session.run_timeout_ms = 1500
    rec.start("int main() { for (;;) {} }\n")
    rec.session.resume()
    assert wait_until(lambda: rec.fin)
    assert rec.fin[-1][1] == "timeout"
