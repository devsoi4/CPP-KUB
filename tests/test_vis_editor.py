"""ทดสอบตัวทำเครื่องหมายบรรทัดที่กำลังดีบักในตัวแก้ไข + โทเคนสีใหม่ของธีม"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app import theme  # noqa: E402
from app.editor import CodeEditor  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def ed(qapp):
    e = CodeEditor()
    e.setPlainText("a\nb\nc\nd\n")
    return e


def _debug_selections(e):
    want = QColor(theme.palette(e.dark)["debug_line"])
    return [s for s in e.extraSelections() if s.format.background().color() == want]


def test_set_debug_line_adds_highlight(ed):
    ed.set_debug_line(3)
    assert ed.debug_line == 3
    sels = _debug_selections(ed)
    assert len(sels) == 1 and sels[0].cursor.blockNumber() == 2


def test_clear_debug_line(ed):
    ed.set_debug_line(3)
    ed.set_debug_line(None)
    assert ed.debug_line is None and _debug_selections(ed) == []


def test_debug_line_follows_theme(ed):
    ed.set_debug_line(2)
    ed.set_dark(True)
    assert len(_debug_selections(ed)) == 1


def test_debug_mode_toggles_read_only_and_clears_marker(ed):
    ed.set_debug_mode(True)
    assert ed.isReadOnly()
    ed.set_debug_line(2)
    ed.set_debug_mode(False)
    assert not ed.isReadOnly() and ed.debug_line is None


def test_debug_line_out_of_range_is_ignored_safely(ed):
    ed.set_debug_line(99)
    assert _debug_selections(ed) == []


@pytest.mark.parametrize("dark", [False, True])
def test_theme_has_debug_tokens(dark):
    p = theme.palette(dark)
    assert "debug_line" in p and "changed" in p
