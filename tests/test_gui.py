"""ทดสอบหน้าต่างหลักแบบ offscreen: รันจริง, ข้อมูลล่วงหน้า, error ไทย, ไฟล์ไทย, พิมพ์เป็น PDF"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEventLoop, QSettings, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app import compiler, printing, textio  # noqa: E402
from app.main_window import MainWindow  # noqa: E402

needs_gpp = pytest.mark.skipif(compiler.find_compiler() is None, reason="ไม่มี g++")


@pytest.fixture(scope="module")
def qapp(tmp_path_factory):
    app = QApplication.instance() or QApplication([])
    # ใช้ไฟล์ ini ชั่วคราวแทน registry ของเครื่องจริง (บน Windows setPath ของ NativeFormat ไม่มีผล)
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path_factory.mktemp("settings")))
    return app


@pytest.fixture
def win(qapp):
    QSettings("CPP-KUB", "CPP-KUB").clear()
    w = MainWindow()
    yield w
    for d in w.tabs.documents():
        d.editor.document().setModified(False)
    w.runner.stop()
    w.close()


def wait_until(cond, timeout_ms=15000):
    loop = QEventLoop()
    t = QTimer()
    t.setInterval(30)
    deadline = QTimer()
    deadline.setSingleShot(True)
    t.timeout.connect(lambda: cond() and loop.quit())
    deadline.timeout.connect(loop.quit)
    t.start()
    deadline.start(timeout_ms)
    loop.exec()
    t.stop()
    return cond()


def finished(w):
    return not w.runner.busy and w.a_run.isEnabled()


@needs_gpp
def test_default_program_runs_and_shows_thai(win):
    win.run_code()
    assert wait_until(lambda: finished(win) and "ทำงานจบ" in win.console.output.toPlainText())
    text = win.console.output.toPlainText()
    assert "สวัสดีชาวโลก!" in text and "คอมไพล์สำเร็จ" in text and "exit code 0" in text


@needs_gpp
def test_preset_input_is_delivered(win):
    win.load_example("t", dict(__import__("app.examples", fromlist=["EXAMPLES"]).EXAMPLES)["02 รับชื่อและทักทาย (cin)"])
    win.console.preset.setPlainText("สมหญิง")
    win.run_code()
    assert wait_until(lambda: finished(win) and "ทำงานจบ" in win.console.output.toPlainText())
    text = win.console.output.toPlainText()
    assert "สวัสดีครับ คุณสมหญิง" in text
    assert "ส่งข้อมูลนำเข้าล่วงหน้าให้โปรแกรม: สมหญิง" in text


@needs_gpp
def test_interactive_input_via_console_line(win):
    from app.examples import EXAMPLES
    win.load_example("t", dict(EXAMPLES)["03 บวกเลขสองจำนวน"])
    win.run_code()
    assert wait_until(lambda: "ใส่เลขตัวที่ 1:" in win.console.output.toPlainText())
    assert win.console.input.isEnabled()
    win.console.input.setText("40")
    win.console.send_btn.click()
    assert wait_until(lambda: "ใส่เลขตัวที่ 2:" in win.console.output.toPlainText())
    win.console.input.setText("2")
    win.console.send_btn.click()
    assert wait_until(lambda: finished(win) and "ทำงานจบ" in win.console.output.toPlainText())
    assert "40 + 2 = 42" in win.console.output.toPlainText()
    assert not win.console.input.isEnabled()


@needs_gpp
def test_error_example_fills_problem_list_and_marks_lines(win):
    from app.examples import EXAMPLES
    win.load_example("t", dict(EXAMPLES)["10 ตัวอย่างที่มี error (ฝึกอ่านข้อผิดพลาด)"])
    win.run_code()
    assert wait_until(lambda: finished(win) and win.problems.count() > 0)
    items = [win.problems.item(i).text() for i in range(win.problems.count())]
    assert any("ลืมใส่เครื่องหมาย ;" in t and "บรรทัด 6" in t for t in items), items
    assert any("'y'" in t for t in items)
    # คำเตือนที่เป็นผลข้างเคียงของ syntax error ต้องไม่ถูกแสดงปนกับ error
    assert all(t.startswith("✖") for t in items), items
    assert win.editor._error_lines.get(6) == "error" and win.editor._error_lines.get(7) == "error"
    assert "คอมไพล์ไม่ผ่าน" in win.console.output.toPlainText()
    assert not win.console.input.isEnabled()


@needs_gpp
def test_stop_button_stops_waiting_program(win):
    from app.examples import EXAMPLES
    win.load_example("t", dict(EXAMPLES)["03 บวกเลขสองจำนวน"])
    win.run_code()
    assert wait_until(lambda: "ใส่เลขตัวที่ 1:" in win.console.output.toPlainText())
    win.a_stop.trigger()
    assert wait_until(lambda: finished(win))
    assert "ผู้ใช้สั่งหยุด" in win.console.output.toPlainText()


def test_save_and_open_thai_file_utf8(tmp_path):
    p = tmp_path / "ทดสอบ.cpp"          # ชื่อไฟล์ภาษาไทยด้วย
    textio.write_source(p, 'cout << "ภาษาไทย";\r\n// หมายเหตุ\n')
    assert p.read_bytes().startswith(b"cout")          # ไม่มี BOM
    text, enc = textio.read_source(p)
    assert enc == "utf-8" and text == 'cout << "ภาษาไทย";\n// หมายเหตุ\n'


def test_reads_legacy_cp874_file(tmp_path):
    p = tmp_path / "old.cpp"
    p.write_bytes('// สวัสดี\r\n'.encode("cp874"))
    text, enc = textio.read_source(p)
    assert enc == "cp874" and text == "// สวัสดี\n"


def test_reads_utf8_bom_file(tmp_path):
    p = tmp_path / "bom.cpp"
    p.write_bytes(b"\xef\xbb\xbf" + "// ไทย\n".encode("utf-8"))
    text, enc = textio.read_source(p)
    assert enc == "utf-8-sig" and text == "// ไทย\n"


def test_pdf_export_has_thai_text(qapp, tmp_path):
    out = tmp_path / "code.pdf"
    printing.export_pdf(str(out), "โปรแกรมทดสอบ", 'int main() {\n  cout << "สวัสดี";\n}\n')
    data = out.read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 1500
    # ตรวจว่าตัวอักษรไทยถูกฝังเป็นฟอนต์จริง (ไม่ใช่ถูกแทนด้วยกล่อง/ข้ามไป)
    import shutil
    import subprocess
    # pdftotext ของ MSYS บน Windows ดึงอักษรไทยจาก PDF ของ Qt ไม่ได้ (เรนเดอร์จริงถูกต้อง) จึงตรวจเฉพาะระบบอื่น
    if sys.platform != "win32" and shutil.which("pdftotext"):
        txt = subprocess.run(["pdftotext", str(out), "-"], capture_output=True, text=True).stdout
        assert "สวัสดี" in txt and "int main()" in txt, txt


def test_editor_paste_normalizes_curly_quotes(win):
    from PySide6.QtCore import QMimeData
    md = QMimeData()
    md.setText("cout << “สวัสดี”;")
    win.editor.clear()
    win.editor.insertFromMimeData(md)
    assert win.editor.toPlainText() == 'cout << "สวัสดี";'


def _type_thai(editor, text):
    """จำลองคีย์บอร์ดไทย: แต่ละตัวอักษรมาเป็น key event ที่มี text (QTest.keyClicks ใช้กับตัวอักษรนอก Latin ไม่ได้)"""
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    for ch in text:
        for kind in (QEvent.KeyPress, QEvent.KeyRelease):
            QApplication.sendEvent(editor, QKeyEvent(kind, Qt.Key_unknown, Qt.NoModifier, ch))


def test_editor_types_thai_without_autoclose_interference(win):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    win.editor.clear()
    QTest.keyClicks(win.editor, 'cout << "')           # ASCII: " ถูกปิดอัตโนมัติ
    _type_thai(win.editor, "ทดสอบ ๑๒๓ สระ ก็ ผู้ ที่")   # วรรณยุกต์/สระลอยต้องไม่หาย
    assert win.editor.toPlainText() == 'cout << "ทดสอบ ๑๒๓ สระ ก็ ผู้ ที่"'
    # เคอร์เซอร์อยู่ก่อน " ที่ปิดอัตโนมัติ Enter จึงแทรกบรรทัดใหม่ตรงนั้น โดยข้อความไทยต้องครบ
    QTest.keyClick(win.editor, Qt.Key_Return)
    assert win.editor.toPlainText() == 'cout << "ทดสอบ ๑๒๓ สระ ก็ ผู้ ที่\n"'


def test_editor_accepts_thai_via_input_method_commit(win):
    from PySide6.QtGui import QInputMethodEvent
    win.editor.clear()
    ev = QInputMethodEvent()
    ev.setCommitString("สวัสดีครับ")
    QApplication.sendEvent(win.editor, ev)
    assert win.editor.toPlainText() == "สวัสดีครับ"


def test_console_input_line_accepts_thai(win):
    from PySide6.QtGui import QInputMethodEvent
    win.console.input.clear()
    ev = QInputMethodEvent()
    ev.setCommitString("สมชาย ใจดี")
    QApplication.sendEvent(win.console.input, ev)
    assert win.console.input.text() == "สมชาย ใจดี"


def test_console_problem_tab_title_counts(win):
    tabs = win.console.tabs
    names = [tabs.tabText(i) for i in range(tabs.count())]
    assert names == ["ผลลัพธ์", "ปัญหา", "ข้อมูลนำเข้าล่วงหน้า"]
    win.console.set_problem_count(3)
    assert tabs.tabText(1) == "ปัญหา (3)"
    win.console.set_problem_count(0)
    assert tabs.tabText(1) == "ปัญหา"
    win.console.show_problems()
    assert tabs.currentIndex() == 1


def test_console_preset_roundtrip(win):
    win.console.set_preset("a\nb", True)
    assert win.console.preset_text() == "a\nb" and win.console.preset_eof()
    win.console.set_preset("", False)
    assert win.console.preset_text() == "" and not win.console.preset_eof()


# ---------- แท็บหลายไฟล์ ----------
def _titles(w):
    return [d.title() for d in w.tabs.documents()]


def test_new_file_opens_second_tab(win):
    win.new_file()
    assert _titles(win) == ["ไม่มีชื่อ-1", "ไม่มีชื่อ-2"]
    assert win.doc is win.tabs.documents()[1]


def test_open_same_file_twice_activates_existing(win, tmp_path):
    f = tmp_path / "a.cpp"
    f.write_text("int main(){}", encoding="utf-8")
    win.open_path(f)
    win.new_file()
    n = win.tabs.count()
    win.open_path(tmp_path / "." / "a.cpp")
    assert win.tabs.count() == n and win.path == f


def test_lone_pristine_untitled_is_replaced_on_open(win, tmp_path):
    f = tmp_path / "b.cpp"
    f.write_text("// b", encoding="utf-8")
    win.open_path(f)
    assert _titles(win) == ["b.cpp"] and win.editor.toPlainText() == "// b"


def test_close_modified_tab_prompts_and_cancel_keeps_it(win, monkeypatch):
    win.editor.insertPlainText("x")
    doc = win.doc
    monkeypatch.setattr(win, "_ask_save", lambda d: "cancel")
    assert win.close_document(doc) is False
    assert win.tabs.documents() == [doc]
    monkeypatch.setattr(win, "_ask_save", lambda d: "discard")
    assert win.close_document(doc) is True


def test_closing_last_tab_creates_fresh_untitled(win):
    old = win.doc
    assert win.close_document(old) is True
    assert win.tabs.count() == 1 and win.doc is not old and win.doc.path is None


def test_per_tab_preset_swaps(win):
    win.console.set_preset("A", True)
    win.new_file()
    assert win.console.preset_text() == "" and not win.console.preset_eof()
    win.tabs.setCurrentIndex(0)
    assert win.console.preset_text() == "A" and win.console.preset_eof()


def test_open_missing_file_warns_not_raises(win, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: shown.append(a))
    n = win.tabs.count()
    win.open_path(tmp_path / "gone.cpp")
    assert shown and win.tabs.count() == n


def test_title_follows_active_tab(win, tmp_path):
    f = tmp_path / "ทดสอบ.cpp"
    f.write_text("", encoding="utf-8")
    win.open_path(f)
    assert "ทดสอบ.cpp" in win.windowTitle()
    win.new_file()
    assert "ไม่มีชื่อ-2" in win.windowTitle()


def test_save_clears_modified_marker(win, tmp_path, monkeypatch):
    win.editor.insertPlainText("x")
    assert win.tabs.tabText(0).startswith("● ")
    monkeypatch.setattr(win, "_choose_save_path", lambda doc: tmp_path / "s.cpp")
    assert win.save_file() is True
    assert win.tabs.tabText(0) == "s.cpp" and (tmp_path / "s.cpp").exists()


@needs_gpp
def test_run_uses_active_tab_and_marks_that_editor(win):
    first = win.doc
    win.new_file()
    second = win.doc
    second.editor.setPlainText("int main() { int x = ; }")
    win.run_code()
    assert wait_until(lambda: finished(win) and win.problems.count() > 0)
    assert second.editor._error_lines and not first.editor._error_lines
    assert win.console.tabs.tabText(1).startswith("ปัญหา (")


@needs_gpp
def test_close_running_tab_stops_runner_without_crash(win):
    from app.examples import EXAMPLES
    win.load_example("t", dict(EXAMPLES)["03 บวกเลขสองจำนวน"])
    running = win.doc
    win.run_code()
    assert wait_until(lambda: "ใส่เลขตัวที่ 1:" in win.console.output.toPlainText())
    win.new_file()
    assert win.close_document(running) is True
    assert wait_until(lambda: finished(win))
    assert win._run_doc is None


@needs_gpp
def test_run_finishing_after_close_does_not_crash(win):
    win.new_file()
    doc = win.doc
    win.run_code()
    win.close_document(doc)
    assert wait_until(lambda: finished(win))


# ---------- จำแท็บที่เปิดค้างไว้ ----------
def _close_clean(w):
    for d in w.tabs.documents():
        d.editor.document().setModified(False)
    w.close()


def test_session_restores_saved_paths_and_active(win, tmp_path):
    f1, f2 = tmp_path / "a.cpp", tmp_path / "b.cpp"
    for f in (f1, f2):
        f.write_text("// " + f.name, encoding="utf-8")
    win.open_path(f1)
    win.open_path(f2)
    win.open_path(f1)                       # ทำให้ a.cpp เป็นแท็บที่เปิดอยู่
    _close_clean(win)
    w2 = MainWindow()
    try:
        assert _titles(w2) == ["a.cpp", "b.cpp"] and w2.path == f1
    finally:
        _close_clean(w2)


def test_session_skips_missing_paths(win, tmp_path):
    f = tmp_path / "gone.cpp"
    f.write_text("x", encoding="utf-8")
    win.open_path(f)
    _close_clean(win)
    f.unlink()
    w2 = MainWindow()
    try:
        assert _titles(w2) == ["ไม่มีชื่อ-1"]
    finally:
        _close_clean(w2)


def test_session_does_not_restore_untitled_content(win):
    win.new_file()
    win.editor.insertPlainText("secret_text")
    _close_clean(win)
    w2 = MainWindow()
    try:
        assert _titles(w2) == ["ไม่มีชื่อ-1"] and "secret_text" not in w2.editor.toPlainText()
    finally:
        _close_clean(w2)


def test_session_restores_explorer_state(win, tmp_path):
    win.activity.explorer_btn.setChecked(False)
    win.explorer.set_folder(str(tmp_path))
    _close_clean(win)
    w2 = MainWindow()
    try:
        assert not w2.activity.explorer_btn.isChecked()
        assert w2.explorer.folder == str(tmp_path)
    finally:
        _close_clean(w2)


def test_preset_sent_belongs_to_run_tab_not_visible_tab(win, monkeypatch):
    sent = []
    monkeypatch.setattr(win.runner, "start", lambda src: None)
    monkeypatch.setattr(win.runner, "send_input", sent.append)
    monkeypatch.setattr(win.runner, "close_input", lambda: sent.append("EOF"))
    win.console.set_preset("5", True)
    win.run_code()
    win.new_file()                              # สลับไปแท็บอื่นระหว่างคอมไพล์
    win.console.set_preset("999", False)
    win._on_run_started()
    assert sent == ["5\n", "EOF"]
