"""ทดสอบข้อความอธิบายอัตโนมัติของ Visualizer (ไม่พึ่ง Qt/gdb)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.visualizer.explain import explain  # noqa: E402
from app.visualizer.model import Frame, Snapshot, Var  # noqa: E402


def fr(func, line, level=0, args=(), locals_=()):
    return Frame(level, func, "a.cpp", line,
                 [Var(n, "int", v) for n, v in args], [Var(n, "int", v, changed=c) for n, v, c in locals_])


def snap(*frames):
    return Snapshot(list(frames))


def test_first_stop():
    s = snap(fr("main", 6))
    assert "main" in explain(None, s) and "6" in explain(None, s)


def test_exited():
    assert "จบ" in explain(snap(fr("main", 7)), Snapshot([], exited=True, exit_code=0))


def test_call_new_function():
    prev = snap(fr("main", 6))
    now = snap(fr("fact", 2, 0, args=[("n", "3")]), fr("main", 6, 1))
    t = explain(prev, now)
    assert "เรียก" in t and "fact(n=3)" in t and "ซ้อน" not in t


def test_recursive_call_mentions_self():
    prev = snap(fr("fact", 3, 0, args=[("n", "3")]), fr("main", 6, 1))
    now = snap(fr("fact", 2, 0, args=[("n", "2")]), fr("fact", 3, 1, args=[("n", "3")]), fr("main", 6, 2))
    t = explain(prev, now)
    assert "เรียกตัวเอง" in t and "2" in t


def test_return_to_caller():
    prev = snap(fr("fact", 4, 0, args=[("n", "1")]), fr("fact", 3, 1, args=[("n", "2")]), fr("main", 6, 2))
    now = snap(fr("fact", 3, 0, args=[("n", "2")]), fr("main", 6, 1))
    t = explain(prev, now)
    assert "fact" in t and "กลับ" in t


def test_variable_changed_shows_old_and_new():
    prev = snap(fr("main", 3, locals_=[("x", "1", False)]))
    now = snap(fr("main", 4, locals_=[("x", "5", True)]))
    t = explain(prev, now)
    assert "x" in t and "1" in t and "5" in t


def test_plain_step_when_nothing_changed():
    prev = snap(fr("main", 3, locals_=[("x", "1", False)]))
    now = snap(fr("main", 4, locals_=[("x", "1", False)]))
    t = explain(prev, now)
    assert "3" in t and "4" in t


def test_annotation_wins():
    now = snap(fr("main", 6))
    assert explain(None, now, "ข้อความเขียนมือ") == "ข้อความเขียนมือ"


def test_annotation_ignored_when_returning():
    prev = snap(fr("fact", 4, 0), fr("main", 6, 1))
    now = snap(fr("main", 6))
    assert "กลับ" in explain(prev, now, "ข้อความเขียนมือ")
