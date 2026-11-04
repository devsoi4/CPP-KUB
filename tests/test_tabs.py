"""ทดสอบแท็บเอกสาร (Document/DocumentTabs) และแถบข้าง (Explorer)"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.document import Document  # noqa: E402
from app.tabs import DocumentTabs  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tabs(qapp):
    t = DocumentTabs()
    t.resize(600, 300)
    t.show()
    return t


def make(tabs, path=None, text=""):
    doc = Document(path=path, untitled_no=tabs.next_untitled_number() if path is None else 0)
    if text:
        doc.editor.setPlainText(text)
        doc.editor.document().setModified(False)
    tabs.add_document(doc)
    return doc


def test_add_and_current(tabs):
    a = make(tabs)
    b = make(tabs)
    assert tabs.documents() == [a, b]
    assert tabs.current_document() is b
    assert a.title() == "ไม่มีชื่อ-1" and b.title() == "ไม่มีชื่อ-2"


def test_modified_marker_in_title(tabs):
    a = make(tabs)
    assert not tabs.tabText(0).startswith("● ")
    a.editor.insertPlainText("x")      # setPlainText รีเซ็ตสถานะแก้ไข จึงใช้การพิมพ์แทรกแบบผู้ใช้
    assert tabs.tabText(0).startswith("● ")


def test_find_by_path_matches_relative_and_resolved(tabs, tmp_path):
    f = tmp_path / "x.cpp"
    f.write_text("int main(){}", encoding="utf-8")
    doc = make(tabs, path=f)
    assert tabs.find_by_path(tmp_path / "." / "x.cpp") is doc
    assert tabs.find_by_path(tmp_path / "y.cpp") is None


def test_untitled_numbers_increase(tabs):
    make(tabs)
    assert tabs.next_untitled_number() == 2


def test_close_button_emits_close_requested_not_removal(tabs):
    a = make(tabs)
    got = []
    tabs.close_requested.connect(got.append)
    tabs.tabCloseRequested.emit(0)
    assert got == [a] and tabs.count() == 1
    tabs.remove_document(a)
    assert tabs.count() == 0


def test_middle_click_requests_close(tabs):
    a = make(tabs)
    got = []
    tabs.close_requested.connect(got.append)
    bar = tabs.tabBar()
    QTest.mouseClick(bar, Qt.MiddleButton, Qt.NoModifier, bar.tabRect(0).center())
    assert got == [a]


def test_running_marker(tabs):
    a = make(tabs)
    tabs.set_running(a)
    assert tabs.tabText(0).startswith("▶ ")
    tabs.set_running(None)
    assert not tabs.tabText(0).startswith("▶ ")


def test_thai_filename_title_and_tooltip(tabs, tmp_path):
    f = tmp_path / "ทดสอบ.cpp"
    f.write_text("", encoding="utf-8")
    make(tabs, path=f)
    assert "ทดสอบ.cpp" in tabs.tabText(0)
    assert str(f) in tabs.tabToolTip(0)


def test_current_document_changed_signal(tabs):
    a = make(tabs)
    b = make(tabs)
    got = []
    tabs.current_document_changed.connect(got.append)
    tabs.setCurrentIndex(0)
    assert got == [a]
    tabs.remove_document(a)
    tabs.remove_document(b)
    assert got[-1] is None
