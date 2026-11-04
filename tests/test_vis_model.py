"""ทดสอบโมเดลข้อมูลของ Visualizer (ไม่ต้องมี gdb)"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.visualizer.model import (  # noqa: E402
    MAX_ELEMENTS, Frame, Snapshot, Var, build_frame, build_var, classify, mark_changes, parse_value_text,
)


def test_classify():
    assert classify("int", "5") == "scalar"
    assert classify("int *", "0x61ff08") == "pointer"
    assert classify("int [3]", "{1, 2, 3}") == "array"
    assert classify("Point", "{x = 1, y = 2}") == "struct"
    assert classify("std::string", "{...}") == "scalar"
    assert classify("std::vector<int>", "{...}") == "scalar"


def test_array_children():
    kids, more = parse_value_text("int [3]", "{10, 20, 30}")
    assert [k.name for k in kids] == ["[0]", "[1]", "[2]"]
    assert [k.value for k in kids] == ["10", "20", "30"]
    assert {k.type for k in kids} == {"int"}
    assert more == 0


def test_array_repeats_expand():
    kids, more = parse_value_text("int [5]", "{0 <repeats 5 times>}")
    assert [k.value for k in kids] == ["0"] * 5 and more == 0
    kids, _ = parse_value_text("int [4]", "{7, 0 <repeats 3 times>}")
    assert [k.value for k in kids] == ["7", "0", "0", "0"]


def test_2d_array_children_are_arrays():
    kids, _ = parse_value_text("int [2][2]", "{{1, 2}, {3, 4}}")
    assert len(kids) == 2
    assert all(k.kind == "array" and k.type == "int [2]" for k in kids)
    assert [c.value for c in kids[1].children] == ["3", "4"]


def test_large_array_capped():
    kids, more = parse_value_text("int [200]", "{0 <repeats 200 times>}")
    assert len(kids) == MAX_ELEMENTS == 50
    assert more == 150


def test_huge_array_is_fast():
    t = time.time()
    kids, more = parse_value_text("int [10000]", "{0 <repeats 10000 times>}")
    assert len(kids) == 50 and more == 9950
    assert time.time() - t < 1


def test_struct_children_and_nesting():
    kids, _ = parse_value_text("Point", "{x = 1, y = 2}")
    assert [(k.name, k.value) for k in kids] == [("x", "1"), ("y", "2")]
    kids, _ = parse_value_text("Outer", "{a = {b = 1}, c = 3}")
    assert kids[0].name == "a" and kids[0].kind == "struct"
    assert kids[0].children[0].name == "b" and kids[1].value == "3"


def test_build_var_pointer_target():
    assert build_var({"name": "p", "type": "int *", "value": "0x61ff08"}).target == 0x61FF08
    assert build_var({"name": "p", "type": "int *", "value": "0x0"}).target == 0
    assert build_var({"name": "s", "type": "char *", "value": '0x404000 "hi"'}).target == 0x404000


def test_build_var_unreadable():
    v = build_var({"name": "p", "type": "int *", "value": "<error: Cannot access memory at address 0x1>"})
    assert v.unreadable is True
    assert build_var({"name": "x", "type": "int", "value": "<optimized out>"}).unreadable is True
    assert build_var({"name": "x", "type": "int", "value": "5"}).unreadable is False


def test_build_var_array_has_children_and_more():
    v = build_var({"name": "a", "type": "int [200]", "value": "{0 <repeats 200 times>}"})
    assert v.kind == "array" and len(v.children) == 50 and v.more == 150


def test_build_frame_splits_args_and_locals():
    f = build_frame(
        {"level": "1", "func": "fact", "file": "main.cpp", "line": "4"},
        [{"name": "n", "type": "int", "value": "3", "arg": "1"}, {"name": "r", "type": "int", "value": "0"}],
    )
    assert (f.level, f.func, f.file, f.line) == (1, "fact", "main.cpp", 4)
    assert [v.name for v in f.args] == ["n"] and [v.name for v in f.locals] == ["r"]


def _snap(sum_value, a1, depth=1):
    frames = []
    for lvl in range(depth):
        frames.append(Frame(lvl, "main" if lvl == depth - 1 else "f", "main.cpp", 5, [], [
            Var("sum", "int", sum_value),
            Var("a", "int [3]", "{...}", kind="array",
                children=[Var("[0]", "int", "10"), Var("[1]", "int", a1), Var("[2]", "int", "30")]),
            Var("k", "int", "1"),
        ]))
    return Snapshot(frames)


def test_mark_changes_scalars_and_elements():
    prev, cur = _snap("0", "20"), _snap("10", "99")
    mark_changes(prev, cur)
    loc = {v.name: v for v in cur.frames[0].locals}
    assert loc["sum"].changed and loc["a"].children[1].changed
    assert not loc["k"].changed and not loc["a"].children[0].changed
    assert loc["a"].changed


def test_mark_changes_no_prev():
    cur = _snap("10", "99")
    mark_changes(None, cur)
    assert not any(v.changed for v in cur.frames[0].locals)


def test_mark_changes_new_recursion_frame_keeps_old_frames_unchanged():
    prev, cur = _snap("0", "20", depth=1), _snap("0", "20", depth=2)
    mark_changes(prev, cur)
    main_frame = cur.frames[1]       # main อยู่ล่างสุดทั้งสองครั้ง
    assert not any(v.changed for v in main_frame.locals)


def test_snapshot_properties():
    s = _snap("0", "20")
    assert (s.line, s.func, s.file) == (5, "main", "main.cpp")
    assert (Snapshot([]).line, Snapshot([]).func) == (0, "")
