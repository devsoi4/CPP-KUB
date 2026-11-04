"""ทดสอบ Runner กับ g++ จริง (Qt แบบ offscreen) รวมถึงการรับ-ส่งภาษาไทย"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app import compiler  # noqa: E402
from app.compiler import Runner, describe_exit  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def run_program(qapp, source, *, send=None, on_prompt=None, idle_ms=4000, eof_after=None, preset=None):
    """รันซอร์สจริง คืน dict ผลลัพธ์ทั้งหมด
    on_prompt = (ข้อความที่รอให้เห็นใน stdout, ข้อมูลที่จะส่งเมื่อเห็น)"""
    r = Runner()
    r.idle_timeout_ms = idle_ms
    res = dict(out="", err="", ok=None, diags=[], raw="", reason=None, code=None, problem=None)
    loop = QEventLoop()
    sent = {"done": False}

    def on_output(text, is_err):
        res["err" if is_err else "out"] += text
        if on_prompt and not sent["done"] and on_prompt[0] in res["out"]:
            sent["done"] = True
            r.send_input(on_prompt[1])
            if eof_after:
                r.close_input()

    r.compile_done.connect(lambda ok, d, raw: res.update(ok=ok, diags=d, raw=raw)
                           or (None if ok else loop.quit()))
    r.problem.connect(lambda m: res.update(problem=m) or loop.quit())
    r.output.connect(on_output)
    r.run_started.connect(lambda: send and r.send_input(send))
    r.run_finished.connect(lambda c, why: res.update(code=c, reason=why) or loop.quit())
    QTimer.singleShot(40000, loop.quit)  # กันค้าง
    r.start(source)
    loop.exec()
    r.stop()
    return res


@pytest.mark.skipif(compiler.find_compiler() is None, reason="ไม่มี g++")
class TestRunnerWithGpp:
    def test_thai_output(self, qapp):
        res = run_program(qapp, '#include <iostream>\nint main(){ std::cout << "สวัสดีชาวโลก ๑๒๓\\n"; }\n')
        assert res["ok"] and res["reason"] == "ok" and res["code"] == 0
        assert res["out"] == "สวัสดีชาวโลก ๑๒๓\n"

    def test_thai_input_round_trip(self, qapp):
        src = ('#include <iostream>\n#include <string>\nusing namespace std;\n'
               'int main(){ string n; cin >> n; cout << "สวัสดี " << n << endl; }\n')
        res = run_program(qapp, src, send="สมชาย\n")
        assert res["out"] == "สวัสดี สมชาย\n"

    def test_prompt_visible_before_input_is_typed(self, qapp):
        """ถ้า stdout ถูก buffer ข้อความถามจะไม่โผล่ก่อนรับ input แล้วโปรแกรมจะค้างจนหมดเวลา"""
        src = ('#include <cstdio>\n#include <iostream>\nusing namespace std;\n'
               'int main(){ int x; printf("ใส่เลข: "); scanf("%d", &x); printf("ได้ %d\\n", x*2); }\n')
        res = run_program(qapp, src, on_prompt=("ใส่เลข:", "21\n"), idle_ms=3000)
        assert res["reason"] == "ok", res
        assert "ได้ 42" in res["out"]

    def test_eof_closes_input(self, qapp):
        src = ('#include <iostream>\nusing namespace std;\n'
               'int main(){ cout << "พร้อม" << endl; int x, s = 0; while (cin >> x) s += x; '
               'cout << "sum=" << s << endl; }\n')
        res = run_program(qapp, src, on_prompt=("พร้อม", "1 2 3\n4\n"), eof_after=True, idle_ms=4000)
        assert res["reason"] == "ok" and "sum=10" in res["out"]

    def test_compile_error_is_reported_in_thai(self, qapp):
        res = run_program(qapp, '#include <iostream>\nint main(){ int x = 1\n std::cout << x; }\n')
        assert res["ok"] is False
        errs = [d for d in res["diags"] if d.kind == "error"]
        assert errs and "ลืมใส่เครื่องหมาย ;" in errs[0].thai

    def test_infinite_loop_is_stopped(self, qapp):
        res = run_program(qapp, 'int main(){ volatile int i = 0; while (true) { i = i + 1; } }\n', idle_ms=1000)
        assert res["reason"] == "timeout"

    def test_output_flood_is_stopped_and_output_kept(self, qapp):
        src = '#include <iostream>\nint main(){ while (true) std::cout << "วนไม่หยุด\\n"; }\n'
        res = run_program(qapp, src, idle_ms=20000)
        assert res["reason"] == "output_limit"
        assert res["out"].startswith("วนไม่หยุด\n")  # ไม่มีตัวอักษรไทยแหว่งตรงรอยต่อ chunk
        assert "�" not in res["out"]

    def test_segfault_is_described(self, qapp):
        res = run_program(qapp, 'int main(){ int* p = nullptr; *p = 1; return 0; }\n')
        assert res["reason"] == "crash"
        assert describe_exit(res["code"], True) is not None

    def test_nonzero_exit_code_is_not_a_crash(self, qapp):
        res = run_program(qapp, 'int main(){ return 3; }\n')
        assert res["reason"] == "ok" and res["code"] == 3

    def test_stderr_is_separate(self, qapp):
        src = '#include <iostream>\nint main(){ std::cerr << "ผิดพลาด\\n"; std::cout << "ปกติ\\n"; }\n'
        res = run_program(qapp, src)
        assert res["err"] == "ผิดพลาด\n" and res["out"] == "ปกติ\n"


def test_work_dir_is_ascii_and_writable():
    wd = compiler.work_dir()
    assert str(wd).isascii() and wd.is_dir()


def test_describe_exit_windows_codes():
    assert "stack overflow" in describe_exit(0xC00000FD, True)
    assert "access violation" in describe_exit(0xC0000005, True)
    assert describe_exit(0, False) is None
    assert describe_exit(3, False) is None


def test_find_gdb_prefers_bundled(tmp_path, monkeypatch):
    exe = "gdb.exe" if compiler.IS_WINDOWS else "gdb"
    (tmp_path / "compiler" / "bin").mkdir(parents=True)
    (tmp_path / "compiler" / "bin" / exe).write_text("x")
    monkeypatch.setattr(compiler, "app_dir", lambda: tmp_path)
    assert compiler.find_gdb() == str(tmp_path / "compiler" / "bin" / exe)


def test_find_gdb_none(tmp_path, monkeypatch):
    monkeypatch.setattr(compiler, "app_dir", lambda: tmp_path)
    monkeypatch.setattr(compiler.shutil, "which", lambda name: None)
    assert compiler.find_gdb() is None


def test_build_args_has_O0(tmp_path):
    assert "-O0" in compiler.build_args(tmp_path / "a.cpp", tmp_path / "a.exe", tmp_path / "p.h")


def test_runner_exe_path_none_before_compile(qapp):
    assert Runner().exe_path is None
