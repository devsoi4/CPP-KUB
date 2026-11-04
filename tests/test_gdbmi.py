"""ทดสอบตัวอ่านผลลัพธ์ GDB/MI (ไม่ต้องมี gdb)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.visualizer.gdbmi import parse_record  # noqa: E402


def test_result_with_token():
    r = parse_record('12^done,value="5"')
    assert (r.kind, r.cls, r.token, r.data) == ("result", "done", 12, {"value": "5"})


def test_exec_stopped_with_tuple():
    r = parse_record('*stopped,reason="end-stepping-range",frame={func="main",line="7"},thread-id="1"')
    assert r.kind == "exec"
    assert r.cls == "stopped"
    assert r.data["frame"] == {"func": "main", "line": "7"}
    assert r.data["thread-id"] == "1"


def test_list_of_key_values_becomes_list_of_values():
    r = parse_record('^done,stack=[frame={level="0",func="f"},frame={level="1",func="main"}]')
    assert r.data["stack"] == [{"level": "0", "func": "f"}, {"level": "1", "func": "main"}]


def test_list_of_tuples_and_strings_and_empties():
    r = parse_record('^done,variables=[{name="a",value="1"},{name="b",value="2"}]')
    assert r.data["variables"] == [{"name": "a", "value": "1"}, {"name": "b", "value": "2"}]
    assert parse_record('^done,names=["a","b"]').data["names"] == ["a", "b"]
    assert parse_record("^done,x=[],y={}").data == {"x": [], "y": {}}


def test_console_stream():
    r = parse_record('~"hello\n"')
    assert (r.kind, r.text) == ("console", "hello\n")


def test_octal_escapes_decode_as_utf8():
    assert parse_record(r'~"\340\270\252"').text == "ส"
    assert parse_record(r'^done,value="\340\270\252\340\270\27"').data["value"].startswith("ส")


def test_error_message_with_quotes():
    r = parse_record('^error,msg="No symbol \\"x\\" in current context."')
    assert r.cls == "error"
    assert r.data["msg"] == 'No symbol "x" in current context.'


def test_prompt_and_garbage_never_raise():
    assert parse_record("(gdb) ").kind == "prompt"
    r = parse_record("garbage((")
    assert (r.kind, r.text) == ("unknown", "garbage((")
    assert parse_record('^done,value="unterminated').kind in ("result", "unknown")
