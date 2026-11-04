"""ทดสอบแผงตัวช่วยมองเห็น (offscreen, ไม่ต้องมี gdb)"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.visualizer.model import Frame, Snapshot, Var  # noqa: E402
from app.visualizer.panel import VisualizerPanel  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(qapp):
    return VisualizerPanel()


def make_snapshot():
    a = Var("a", "int [3]", "{10, 20, 30}", kind="array",
            children=[Var(f"[{i}]", "int", str(10 * (i + 1))) for i in range(3)])
    big = Var("big", "int [200]", "{0 <repeats 200 times>}", kind="array", more=150,
              children=[Var(f"[{i}]", "int", "0") for i in range(50)])
    bad = Var("bad", "int *", "<error: Cannot access memory at address 0x1>", kind="pointer", unreadable=True)
    frame = Frame(0, "main", "main.cpp", 5, args=[Var("argc", "int", "1")],
                  locals=[Var("sum", "int", "10", changed=True), Var("k", "int", "1"), a, big, bad])
    return Snapshot([frame])


def top(panel):
    t = panel.variables
    return [t.topLevelItem(i) for i in range(t.topLevelItemCount())]


def test_top_level_rows_args_then_locals(panel):
    panel.show_snapshot(make_snapshot())
    items = top(panel)
    assert [i.text(0) for i in items] == ["argc", "sum", "k", "a", "big", "bad"]
    assert (items[1].text(1), items[1].text(2)) == ("int", "10")


def test_array_expands_to_children(panel):
    panel.show_snapshot(make_snapshot())
    a = top(panel)[3]
    assert a.childCount() == 3
    assert [a.child(i).text(0) for i in range(3)] == ["[0]", "[1]", "[2]"]
    assert a.child(2).text(2) == "30"


def test_changed_row_is_highlighted(panel):
    panel.show_snapshot(make_snapshot())
    items = top(panel)
    assert items[1].background(2).style() != Qt.NoBrush      # sum (เปลี่ยนค่า)
    assert items[2].background(2).style() == Qt.NoBrush      # k


def test_unreadable_shown_in_thai(panel):
    panel.show_snapshot(make_snapshot())
    assert top(panel)[5].text(2) == "อ่านไม่ได้"


def test_more_elements_row(panel):
    panel.show_snapshot(make_snapshot())
    big = top(panel)[4]
    assert big.childCount() == 51
    assert "150" in big.child(50).text(0)


def test_clear_empties_tree(panel):
    panel.show_snapshot(make_snapshot())
    panel.clear()
    assert panel.variables.topLevelItemCount() == 0 and panel.info_label.text() == ""


def test_exited_snapshot_shows_exit_code(panel):
    panel.show_snapshot(make_snapshot())
    panel.show_snapshot(Snapshot([], exited=True, exit_code=0))
    assert panel.variables.topLevelItemCount() == 0
    assert "0" in panel.info_label.text() and "จบ" in panel.info_label.text()


def test_signal_snapshot_explains_crash(panel):
    s = make_snapshot()
    s.signal = "SIGSEGV"
    panel.show_snapshot(s)
    assert "SIGSEGV" in panel.info_label.text()


def test_set_dark_rerenders_without_error(panel):
    panel.show_snapshot(make_snapshot())
    panel.set_dark(True)
    assert panel.variables.topLevelItemCount() == 6
