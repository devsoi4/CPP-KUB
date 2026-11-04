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


# ---------- แถบข้าง ----------
def _group(explorer, title):
    root = explorer.tree.invisibleRootItem()
    return next(root.child(i) for i in range(root.childCount()) if root.child(i).text(0).startswith(title))


def test_explorer_lists_all_examples(qapp):
    from app.examples import EXAMPLES
    from app.sidebar import Explorer
    ex = Explorer()
    g = _group(ex, "ตัวอย่างโค้ด")
    assert [g.child(i).text(0) for i in range(g.childCount())] == [t for t, _ in EXAMPLES]


def test_example_click_emits_title(qapp):
    from app.examples import EXAMPLES
    from app.sidebar import Explorer
    ex = Explorer()
    got = []
    ex.example_requested.connect(got.append)
    item = _group(ex, "ตัวอย่างโค้ด").child(1)
    ex.tree.itemClicked.emit(item, 0)
    assert got == [EXAMPLES[1][0]]


def test_open_documents_click_emits_document(qapp):
    from app.sidebar import Explorer
    ex = Explorer()
    a, b = Document(untitled_no=1), Document(untitled_no=2)
    ex.set_documents([a, b], b)
    g = _group(ex, "ไฟล์ที่เปิดอยู่")
    assert [g.child(i).text(0) for i in range(2)] == ["ไม่มีชื่อ-1", "ไม่มีชื่อ-2"]
    got = []
    ex.document_requested.connect(got.append)
    ex.tree.itemClicked.emit(g.child(0), 0)
    assert got == [a]


def test_folder_lists_only_cpp_files(qapp, tmp_path):
    from app.sidebar import Explorer
    for n in ("a.cpp", "b.h", "c.txt", "ทดสอบ.cpp"):
        (tmp_path / n).write_text("", encoding="utf-8")
    ex = Explorer()
    ex.set_folder(str(tmp_path))
    g = _group(ex, "โฟลเดอร์งาน")
    assert sorted(g.child(i).text(0) for i in range(g.childCount())) == sorted(["a.cpp", "b.h", "ทดสอบ.cpp"])
    got = []
    ex.open_path_requested.connect(got.append)
    ex.tree.itemClicked.emit(g.child(0), 0)
    assert got and Path(got[0]).parent == tmp_path


def test_missing_folder_is_empty_not_error(qapp, tmp_path):
    from app.sidebar import Explorer
    ex = Explorer()
    ex.set_folder(str(tmp_path / "gone"))
    assert _group(ex, "โฟลเดอร์งาน").childCount() == 0


def test_activity_toggle_emits(qapp):
    from app.sidebar import ActivityBar
    bar = ActivityBar()
    got = []
    bar.explorer_toggled.connect(got.append)
    bar.explorer_btn.click()
    assert got == [False]       # เริ่มต้นเปิดอยู่ คลิกแล้วปิด
