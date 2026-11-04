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


# ---------- call stack + ป้ายรอบ loop (งานที่ 9) ----------
from app.visualizer.loops import LoopStatus  # noqa: E402


def make_recursion_snapshot():
    fact2 = Frame(0, "fact", "main.cpp", 4, args=[Var("n", "int", "2")], locals=[])
    fact3 = Frame(1, "fact", "main.cpp", 4, args=[Var("n", "int", "3")], locals=[])
    main = Frame(2, "main", "main.cpp", 7, args=[], locals=[Var("result", "int", "0")])
    return Snapshot([fact2, fact3, main])


def test_stack_rows_innermost_first(panel):
    panel.show_snapshot(make_recursion_snapshot())
    assert panel.stack.count() == 3
    assert "fact" in panel.stack.item(0).text() and "n=2" in panel.stack.item(0).text()
    assert "n=3" in panel.stack.item(1).text()
    assert "main" in panel.stack.item(2).text() and "บรรทัด 7" in panel.stack.item(2).text()
    assert panel.stack.currentRow() == 0


def test_selecting_frame_switches_variables_and_emits_line(panel):
    seen = []
    panel.frame_selected.connect(seen.append)
    panel.show_snapshot(make_recursion_snapshot())
    assert seen == []                                   # การแสดง snapshot เองไม่ใช่การคลิกของผู้ใช้
    panel.stack.setCurrentRow(2)
    assert seen == [7]
    assert [i.text(0) for i in top(panel)] == ["result"]
    panel.stack.setCurrentRow(1)
    assert [i.text(0) for i in top(panel)] == ["n"] and top(panel)[0].text(2) == "3"


def test_new_snapshot_resets_to_innermost_frame(panel):
    panel.show_snapshot(make_recursion_snapshot())
    panel.stack.setCurrentRow(2)
    panel.show_snapshot(make_recursion_snapshot())
    assert panel.stack.currentRow() == 0 and top(panel)[0].text(2) == "2"


def test_clear_empties_stack(panel):
    panel.show_snapshot(make_recursion_snapshot())
    panel.clear()
    assert panel.stack.count() == 0 and panel.loop_label.isHidden()


def test_loop_badge_for_with_variable(panel):
    panel.set_loops([LoopStatus(5, "for", "i", 2)], {"i": "1"})
    assert not panel.loop_label.isHidden()
    assert "รอบที่ 2" in panel.loop_label.text() and "i = 1" in panel.loop_label.text()


def test_loop_badge_while_and_nested(panel):
    panel.set_loops([LoopStatus(3, "for", "i", 1), LoopStatus(4, "while", None, 3)], {"i": "0"})
    text = panel.loop_label.text()
    assert "รอบที่ 1" in text and "รอบที่ 3" in text and "›" in text


def test_loop_badge_hidden_when_no_loop(panel):
    panel.set_loops([LoopStatus(5, "for", "i", 2)], {"i": "1"})
    panel.set_loops([], {})
    assert panel.loop_label.isHidden()


def test_loop_badge_unknown_variable_value(panel):
    panel.set_loops([LoopStatus(5, "for", "i", 1)], {})
    assert "i = ?" in panel.loop_label.text()


def test_exited_snapshot_clears_stack(panel):
    panel.show_snapshot(make_recursion_snapshot())
    panel.show_snapshot(Snapshot([], exited=True, exit_code=0))
    assert panel.stack.count() == 0


def test_panel_embeds_memory_view(panel):
    panel.show_snapshot(make_snapshot())
    assert panel.memory.box_count > 0
    panel.show_snapshot(Snapshot([], exited=True, exit_code=0))
    assert panel.memory.box_count == 0
    panel.show_snapshot(make_snapshot())
    panel.clear()
    assert panel.memory.box_count == 0


def test_panel_explains_sigfpe_and_sigabrt_in_thai(panel):
    for sig in ("SIGFPE", "SIGABRT"):
        s = make_snapshot()
        s.signal = sig
        panel.show_snapshot(s)
        assert sig in panel.info_label.text() and "—" in panel.info_label.text()
