"""ทดสอบภาพหน่วยความจำ (offscreen, ไม่ต้องมี gdb)"""
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.visualizer.memory_view import MemoryView  # noqa: E402
from app.visualizer.model import UNREADABLE_POINTEE, Frame, PointsTo, Snapshot, Var  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def view(qapp):
    v = MemoryView()
    v.resize(600, 400)
    return v


def array_var(name, n, **kw):
    return Var(name, f"int [{n}]", "{...}", kind="array",
               children=[Var(f"[{i}]", "int", str(i)) for i in range(n)], **kw)


def pointer(name, target, **kw):
    return Var(name, "int *", hex(target), kind="pointer", target=target, **kw)


def pointer_snapshot():
    x = Var("x", "int", "5")
    a = array_var("a", 3)
    p = pointer("p", 0x100, points_to=PointsTo(0, "x", None))
    q = pointer("q", 0x208, points_to=PointsTo(0, "a", 2))
    n = pointer("n", 0)
    r = pointer("r", 0x900, pointee="7")
    return Snapshot([Frame(0, "main", "main.cpp", 9, [], [x, a, p, q, n, r])])


def test_boxes_and_arrows_for_pointers(view):
    view.show_snapshot(pointer_snapshot())
    # x=1, a[0..2]=3, pointers p,q,n,r=4, กล่อง heap ของ r=1
    assert view.box_count == 9
    assert view.arrow_count == 3                      # p→x, q→a[2], r→heap (n เป็น nullptr ไม่มีลูกศร)


def test_changed_scalar_still_counted(view):
    s = Snapshot([Frame(0, "main", "main.cpp", 1, [], [Var("sum", "int", "10", changed=True)])])
    view.show_snapshot(s)
    assert view.box_count == 1 and view.arrow_count == 0


def test_large_array_is_capped_and_fast(view):
    big = Var("big", "int [10000]", "{...}", kind="array", more=9950,
              children=[Var(f"[{i}]", "int", "0") for i in range(50)])
    t = time.time()
    view.show_snapshot(Snapshot([Frame(0, "main", "main.cpp", 1, [], [big])]))
    assert view.box_count == 51                       # 50 ช่อง + กล่อง "…"
    assert time.time() - t < 1


def test_unreadable_pointer_has_no_arrow_and_does_not_raise(view):
    bad = Var("bad", "int *", "<error: Cannot access memory at address 0x1>", kind="pointer", unreadable=True)
    view.show_snapshot(Snapshot([Frame(0, "main", "main.cpp", 1, [], [bad])]))
    assert view.box_count == 1 and view.arrow_count == 0


def test_unreadable_pointee_still_draws_heap_box(view):
    r = pointer("r", 0x900, pointee=UNREADABLE_POINTEE)
    view.show_snapshot(Snapshot([Frame(0, "main", "main.cpp", 1, [], [r])]))
    assert view.box_count == 2 and view.arrow_count == 1


def test_struct_members_are_boxes(view):
    pt = Var("pt", "Point", "{x = 1, y = 2}", kind="struct",
             children=[Var("x", "int", "1"), Var("y", "int", "2")])
    view.show_snapshot(Snapshot([Frame(0, "main", "main.cpp", 1, [], [pt])]))
    assert view.box_count == 2


def test_pointer_to_struct_member_variable_arrow(view):
    pt = Var("pt", "Point", "{x = 1, y = 2}", kind="struct",
             children=[Var("x", "int", "1"), Var("y", "int", "2")])
    p = pointer("p", 0x10, points_to=PointsTo(0, "pt", None))
    view.show_snapshot(Snapshot([Frame(0, "main", "main.cpp", 1, [], [pt, p])]))
    assert view.arrow_count == 1


def test_pointer_across_frames(view):
    inner = Frame(0, "f", "main.cpp", 3, [pointer("p", 0x10, points_to=PointsTo(1, "x", None))], [])
    outer = Frame(1, "main", "main.cpp", 9, [], [Var("x", "int", "1")])
    view.show_snapshot(Snapshot([inner, outer]))
    assert view.box_count == 2 and view.arrow_count == 1


def test_clear_resets_counts(view):
    view.show_snapshot(pointer_snapshot())
    view.clear()
    assert (view.box_count, view.arrow_count) == (0, 0)


def test_exited_snapshot_draws_nothing(view):
    view.show_snapshot(pointer_snapshot())
    view.show_snapshot(Snapshot([], exited=True, exit_code=0))
    assert (view.box_count, view.arrow_count) == (0, 0)


def test_set_dark_rerenders_same_counts(view):
    view.show_snapshot(pointer_snapshot())
    view.set_dark(True)
    assert (view.box_count, view.arrow_count) == (9, 3)


def test_2d_array_and_array_of_structs_render(view):
    grid = Var("grid", "int [2][2]", "{...}", kind="array",
               children=[array_var("[0]", 2), array_var("[1]", 2)])
    pts = Var("pts", "Point [2]", "{...}", kind="array", children=[
        Var("[0]", "Point", "{...}", kind="struct", children=[Var("x", "int", "1"), Var("y", "int", "2")]),
        Var("[1]", "Point", "{...}", kind="struct", children=[Var("x", "int", "3"), Var("y", "int", "4")]),
    ])
    view.show_snapshot(Snapshot([Frame(0, "main", "main.cpp", 1, [], [grid, pts])]))
    assert view.box_count == 4 + 4


def test_pointer_into_2d_array_row_does_not_crash(view):
    grid = Var("grid", "int [2][2]", "{...}", kind="array",
               children=[array_var("[0]", 2), array_var("[1]", 2)])
    p = pointer("p", 0x10, points_to=PointsTo(0, "grid", 1))
    view.show_snapshot(Snapshot([Frame(0, "main", "main.cpp", 1, [], [grid, p])]))
    assert view.arrow_count == 1
