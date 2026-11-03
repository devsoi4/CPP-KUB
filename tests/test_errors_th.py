import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import errors_th  # noqa: E402
from app.examples import EXAMPLES  # noqa: E402

needs_gpp = pytest.mark.skipif(shutil.which("g++") is None, reason="ไม่มี g++")


def test_explain_missing_semicolon():
    assert "ลืมใส่เครื่องหมาย ;" in errors_th.explain("expected ';' before 'cout'")


def test_explain_undeclared_names_variable():
    out = errors_th.explain("'y' was not declared in this scope")
    assert "'y'" in out and "ไม่รู้จัก" in out


def test_explain_cout_hint_mentions_namespace():
    out = errors_th.explain("'cout' was not declared in this scope")
    assert "using namespace std" in out


def test_did_you_mean_is_used():
    out = errors_th.explain("'cuot' was not declared in this scope; did you mean 'cout'?")
    assert "'cout'" in out


def test_curly_braces_in_template_do_not_crash():
    # ข้อความที่มี {} ในคำอธิบายต้องไม่ทำให้ format พัง
    out = errors_th.explain("expected unqualified-id before 'return'")
    assert "{" in out and "}" in out


def test_warning_unused_variable():
    out = errors_th.explain("unused variable 'tmp' [-Wunused-variable]", "warning")
    assert "'tmp'" in out


def test_unknown_message_uses_fallback():
    assert errors_th.explain("some brand new gcc message", "error") == errors_th.FALLBACK["error"]


def test_parse_output_extracts_line_and_kind():
    raw = ("main.cpp: In function 'int main()':\n"
           "main.cpp:5:14: error: expected ';' before 'cout'\n"
           "main.cpp:6:5: warning: unused variable 'z' [-Wunused-variable]\n")
    d = errors_th.parse_output(raw)
    assert [(x.line, x.kind) for x in d] == [(5, "error"), (6, "warning")]


def test_parse_normalizes_curly_quotes():
    raw = "main.cpp:3:5: error: ‘y’ was not declared in this scope\n"
    d = errors_th.parse_output(raw)
    assert "ไม่รู้จัก" in d[0].thai


def test_parse_linker_error():
    d = errors_th.parse_output("/usr/bin/ld: x.o: undefined reference to `foo()'\n")
    assert d and d[0].kind == "error" and "foo()" in d[0].thai


def test_report_is_thai_and_skips_notes():
    d = errors_th.parse_output("main.cpp:2:1: error: expected '}' at end of input\n"
                               "main.cpp:1:1: note: to match this '{'\n")
    rep = errors_th.format_report(d)
    assert "ข้อผิดพลาด" in rep and "บรรทัดที่ 2" in rep and "note" not in rep


@needs_gpp
def test_real_gpp_error_example_is_translated():
    """ใช้ g++ จริงคอมไพล์ตัวอย่างข้อ 10 แล้วตรวจว่าได้คำอธิบายไทยที่ถูกบรรทัด"""
    code = dict(EXAMPLES)["10 ตัวอย่างที่มี error (ฝึกอ่านข้อผิดพลาด)"]
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "main.cpp"
        src.write_text(code, encoding="utf-8")
        p = subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-fsyntax-only", str(src)],
                           capture_output=True, text=True, env={**os.environ, "LC_ALL": "C"})
    diags = [d for d in errors_th.parse_output(p.stderr) if d.kind == "error"]
    assert diags, p.stderr
    # g++ รายงานที่บรรทัด 6 (บรรทัดถัดจากที่ลืม ;) คำอธิบายต้องชี้กลับไปบรรทัดที่ 5
    assert diags[0].line == 6
    assert "ลืมใส่เครื่องหมาย ;" in diags[0].thai and "บรรทัดที่ 5" in diags[0].thai
    assert any(d.line == 7 and "'y'" in d.thai for d in diags)


@needs_gpp
def test_every_non_error_example_compiles_cleanly():
    """ตัวอย่างข้อ 1-9 ต้องคอมไพล์ผ่านด้วย g++ จริง ไม่มี warning"""
    bad = []
    for title, code in EXAMPLES:
        if title.startswith("10"):
            continue
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "main.cpp"
            src.write_text(code, encoding="utf-8")
            p = subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-fsyntax-only", str(src)],
                               capture_output=True, text=True)
        if p.returncode != 0 or p.stderr.strip():
            bad.append((title, p.stderr))
    assert not bad, bad
