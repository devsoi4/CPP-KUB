"""หน้าต่างหลักของ CppLearn"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDockWidget, QFileDialog, QLabel, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QSplitter, QToolBar,
)

from . import printing, textio
from .compiler import Runner, describe_exit, find_compiler
from .console import ConsoleWidget
from .editor import CodeEditor
from .examples import DEFAULT_CODE, EXAMPLES

APP_NAME = "Cpp-Kub"
FILTER = "ไฟล์ C++ (*.cpp *.cc *.cxx *.h *.hpp);;ทุกไฟล์ (*)"

DARK_QSS = """
QWidget { background:#0d1117; color:#e6edf3; }
QPlainTextEdit, QLineEdit, QListWidget, QComboBox { background:#0d1117; border:1px solid #30363d; }
QMenuBar, QMenu, QToolBar, QDockWidget { background:#161b22; }
QMenu::item:selected, QPushButton:hover { background:#1f6feb; }
QPushButton { background:#21262d; border:1px solid #30363d; padding:4px 10px; border-radius:4px; }
QPushButton:disabled { color:#6e7681; }
QTabBar::tab { background:#161b22; padding:6px 12px; }
QTabBar::tab:selected { background:#0d1117; border-bottom:2px solid #1f6feb; }
QSplitter::handle { background:#30363d; }
"""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings(APP_NAME, APP_NAME)
        self.path: Path | None = None
        self.dark = self.settings.value("dark", False, type=bool)

        self.editor = CodeEditor()
        self.editor.setPlainText(DEFAULT_CODE)
        self.editor.document().setModified(False)
        self.console = ConsoleWidget()
        self.runner = Runner(self)

        split = QSplitter(Qt.Vertical)
        split.addWidget(self.editor)
        split.addWidget(self.console)
        split.setSizes([480, 300])
        self.setCentralWidget(split)

        self.problems = QListWidget()
        self.problems.setWordWrap(True)
        self.problems.setResizeMode(QListWidget.Adjust)
        self.problems.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.problems.itemActivated.connect(self._goto_problem)
        self.problems.itemClicked.connect(self._goto_problem)
        dock = QDockWidget("ปัญหาที่พบ (อธิบายเป็นภาษาไทย)", self)
        dock.setWidget(self.problems)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        dock.setMinimumWidth(320)

        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._connect_signals()

        size = self.settings.value("font_size", 13, type=int)
        self.editor.set_font_size(size)
        self.console.set_font_size(max(10, size - 1))
        self._apply_theme()
        self.resize(1200, 760)
        self._update_title()
        cc = find_compiler()
        self.statusBar().showMessage(
            f"พร้อมใช้งาน — คอมไพเลอร์: {cc}" if cc else "⚠ ไม่พบตัวคอมไพล์ g++ (ดูวิธีแก้ในปุ่ม รัน)")

    # ---------- สร้างเมนู/ปุ่ม ----------
    def _act(self, text, slot, shortcut=None, tip=None) -> QAction:
        a = QAction(text, self)
        a.triggered.connect(slot)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if tip:
            a.setToolTip(tip)
        return a

    def _build_actions(self) -> None:
        self.a_new = self._act("ไฟล์ใหม่", self.new_file, "Ctrl+N")
        self.a_open = self._act("เปิดไฟล์...", self.open_file, "Ctrl+O")
        self.a_save = self._act("บันทึก", self.save_file, "Ctrl+S")
        self.a_save_as = self._act("บันทึกเป็น...", self.save_file_as, "Ctrl+Shift+S")
        self.a_print = self._act("พิมพ์โค้ด...", self.print_code, "Ctrl+P")
        self.a_print_out = self._act("พิมพ์ผลลัพธ์...", self.print_output)
        self.a_pdf = self._act("ส่งออกโค้ดเป็น PDF...", self.export_code_pdf)
        self.a_quit = self._act("ออกจากโปรแกรม", self.close, "Ctrl+Q")
        self.a_run = self._act("▶ รัน (F5)", self.run_code, "F5", "คอมไพล์และรันโปรแกรม")
        self.a_stop = self._act("■ หยุด", self.runner.stop, "Shift+F5", "หยุดโปรแกรมที่กำลังรัน")
        self.a_stop.setEnabled(False)
        self.a_zoom_in = self._act("ขยายตัวอักษร", lambda: self._zoom(+1), "Ctrl+=")
        self.a_zoom_out = self._act("ลดตัวอักษร", lambda: self._zoom(-1), "Ctrl+-")
        self.a_dark = self._act("ธีมมืด", self._toggle_dark)
        self.a_dark.setCheckable(True)
        self.a_dark.setChecked(self.dark)
        self.a_clear = self._act("ล้างหน้าต่างผลลัพธ์", self.console.clear)
        self.a_about = self._act("เกี่ยวกับโปรแกรม", self._about)

    def _build_menus(self) -> None:
        mb = self.menuBar()
        m = mb.addMenu("ไฟล์")
        for a in (self.a_new, self.a_open, self.a_save, self.a_save_as):
            m.addAction(a)
        m.addSeparator()
        for a in (self.a_print, self.a_print_out, self.a_pdf):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_quit)
        m = mb.addMenu("แก้ไข")
        m.addAction("เลิกทำ", self.editor.undo, QKeySequence.Undo)
        m.addAction("ทำซ้ำ", self.editor.redo, QKeySequence.Redo)
        m.addSeparator()
        m.addAction("ตัด", self.editor.cut, QKeySequence.Cut)
        m.addAction("คัดลอก", self.editor.copy, QKeySequence.Copy)
        m.addAction("วาง", self.editor.paste, QKeySequence.Paste)
        m.addAction("เลือกทั้งหมด", self.editor.selectAll, QKeySequence.SelectAll)
        m = mb.addMenu("รัน")
        m.addAction(self.a_run)
        m.addAction(self.a_stop)
        m.addAction(self.a_clear)
        m = mb.addMenu("ตัวอย่างโค้ด")
        for title, code in EXAMPLES:
            m.addAction(title, lambda c=code, t=title: self.load_example(t, c))
        m = mb.addMenu("มุมมอง")
        for a in (self.a_zoom_in, self.a_zoom_out, self.a_dark):
            m.addAction(a)
        mb.addMenu("ช่วยเหลือ").addAction(self.a_about)

    def _build_toolbar(self) -> None:
        tb = QToolBar("เครื่องมือ")
        tb.setMovable(False)
        self.addToolBar(tb)
        tb.addAction(self.a_run)
        tb.addAction(self.a_stop)
        tb.addSeparator()
        tb.addWidget(QLabel("  ตัวอย่าง: "))
        self.example_box = QComboBox()
        self.example_box.addItem("— เลือกตัวอย่างโค้ด —")
        for title, _ in EXAMPLES:
            self.example_box.addItem(title)
        self.example_box.activated.connect(self._example_chosen)
        tb.addWidget(self.example_box)
        tb.addSeparator()
        tb.addAction(self.a_save)
        tb.addAction(self.a_print)

    def _connect_signals(self) -> None:
        r = self.runner
        r.compile_started.connect(self._on_compile_started)
        r.compile_done.connect(self._on_compile_done)
        r.problem.connect(self._on_problem)
        r.run_started.connect(self._on_run_started)
        r.output.connect(self.console.append_out)
        r.run_finished.connect(self._on_run_finished)
        self.console.input_submitted.connect(r.send_input)
        self.console.eof_requested.connect(r.close_input)
        self.editor.document().modificationChanged.connect(self._update_title)

    # ---------- คอมไพล์/รัน ----------
    def run_code(self) -> None:
        self.console.clear()
        self.problems.clear()
        self.editor.clear_diagnostics()
        self.runner.start(self.editor.toPlainText())

    def _set_busy(self, busy: bool) -> None:
        self.a_run.setEnabled(not busy)
        self.a_stop.setEnabled(busy)

    def _on_compile_started(self) -> None:
        self._set_busy(True)
        self.statusBar().showMessage("กำลังคอมไพล์...")
        self.console.append_info("⏳ กำลังคอมไพล์...")

    def _on_problem(self, msg: str) -> None:
        self._set_busy(False)
        self.console.set_input_enabled(False)
        self.statusBar().showMessage("เกิดปัญหา")
        self.console.append_info(msg, "err")
        QMessageBox.warning(self, APP_NAME, msg)

    def _on_compile_done(self, ok: bool, diags, raw: str) -> None:
        from .errors_th import format_report
        marks: dict[int, str] = {}
        # คำเตือนที่ g++ ออกมาพร้อม error มักเป็นผลข้างเคียงของ error (เช่น "ตัวแปรไม่ได้ใช้" ทั้งที่ใช้อยู่)
        # จึงแสดงเฉพาะ error ก่อน แล้วค่อยโชว์คำเตือนเมื่อแก้ error หมดแล้ว
        if any(d.kind == "error" for d in diags):
            diags = [d for d in diags if d.kind == "error"]
        for d in diags:
            if d.kind == "note":
                continue
            if d.line and marks.get(d.line) != "error":
                marks[d.line] = d.kind
            where = f"บรรทัด {d.line}: " if d.line else "ลิงก์: "
            text = where + (d.thai or d.message)
            item = QListWidgetItem(("✖ " if d.kind == "error" else "⚠ ") + text)
            item.setToolTip(d.message)
            item.setData(Qt.UserRole, d.line)
            self.problems.addItem(item)
        self.editor.set_diagnostics(marks)
        n_err = sum(d.kind == "error" for d in diags)
        n_warn = sum(d.kind == "warning" for d in diags)
        if ok:
            msg = "✔ คอมไพล์สำเร็จ" + (f" (มีคำเตือน {n_warn} รายการ)" if n_warn else "")
            self.console.append_info(msg, "ok")
            if n_warn:
                self.console.append_block(format_report(diags), "warn")
            self.console.append_info("▶ เริ่มรันโปรแกรม", "info")
        else:
            self._set_busy(False)
            self.statusBar().showMessage(f"คอมไพล์ไม่ผ่าน ({n_err} ข้อผิดพลาด)")
            self.console.append_info(f"✖ คอมไพล์ไม่ผ่าน — พบข้อผิดพลาด {n_err} รายการ", "err")
            report = format_report(diags) or raw
            self.console.append_block(report, "err")
            first = next((d for d in diags if d.kind == "error" and d.line), None)
            if first:
                self.editor.goto_line(first.line)

    def _on_run_started(self) -> None:
        self.statusBar().showMessage("กำลังรันโปรแกรม...")
        self.console.set_input_enabled(True)
        preset = self.console.preset_text()
        if preset.strip():
            data = preset if preset.endswith("\n") else preset + "\n"
            shown = " ⏎ ".join(data.rstrip("\n").split("\n"))
            if len(shown) > 80:
                shown = shown[:80] + "…"
            self.console.append_info(f"📥 ส่งข้อมูลนำเข้าล่วงหน้าให้โปรแกรม: {shown}", "echo")
            self.runner.send_input(data)
            if self.console.preset_auto_eof.isChecked():
                self.runner.close_input()

    def _on_run_finished(self, code: int, reason: str) -> None:
        self._set_busy(False)
        self.console.set_input_enabled(False)
        crashed_text = describe_exit(code, reason == "crash")
        if reason == "timeout":
            secs = self.runner.idle_timeout_ms // 1000
            self.console.append_info(
                f"⏱ หยุดโปรแกรม: ไม่มีความเคลื่อนไหวเกิน {secs} วินาที "
                "(อาจวนลูปไม่รู้จบ หรือรอข้อมูลที่ไม่ได้ส่งเข้ามา)", "warn")
            self.statusBar().showMessage("หยุดเพราะหมดเวลา")
        elif reason == "output_limit":
            self.console.append_info("⛔ หยุดโปรแกรม: พิมพ์ข้อความมากเกินไป "
                                     "(อาจมีลูปที่พิมพ์ไม่รู้จบ)", "warn")
            self.statusBar().showMessage("หยุดเพราะพิมพ์มากเกินไป")
        elif reason == "stopped":
            self.console.append_info("■ ผู้ใช้สั่งหยุดโปรแกรม", "warn")
            self.statusBar().showMessage("หยุดแล้ว")
        elif reason == "crash" or crashed_text:
            self.console.append_info("💥 โปรแกรมหยุดทำงานผิดปกติ", "err")
            if crashed_text:
                self.console.append_block("   → " + crashed_text, "err")
            self.statusBar().showMessage("โปรแกรมหยุดผิดปกติ")
        else:
            kind = "ok" if code == 0 else "warn"
            self.console.append_info(f"● โปรแกรมทำงานจบ (exit code {code})", kind)
            self.statusBar().showMessage("ทำงานเสร็จสิ้น")

    def _goto_problem(self, item: QListWidgetItem) -> None:
        line = item.data(Qt.UserRole)
        if line:
            self.editor.goto_line(int(line))

    # ---------- ไฟล์ ----------
    def _update_title(self, *_args) -> None:
        name = self.path.name if self.path else "ไม่มีชื่อ"
        star = " *" if self.editor.document().isModified() else ""
        self.setWindowTitle(f"{name}{star} — {APP_NAME}")

    def _confirm_discard(self) -> bool:
        if not self.editor.document().isModified():
            return True
        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME)
        box.setText("ไฟล์นี้ยังไม่ได้บันทึก ต้องการบันทึกก่อนหรือไม่?")
        save = box.addButton("บันทึก", QMessageBox.AcceptRole)
        box.addButton("ไม่บันทึก", QMessageBox.DestructiveRole)
        cancel = box.addButton("ยกเลิก", QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is cancel:
            return False
        if clicked is save:
            return self.save_file()
        return True

    def _load_text(self, text: str, path: Path | None) -> None:
        self.runner.stop()
        self.editor.setPlainText(text)
        self.editor.document().setModified(False)
        self.editor.clear_diagnostics()
        self.problems.clear()
        self.console.clear()
        self.path = path
        self._update_title()

    def new_file(self) -> None:
        if self._confirm_discard():
            self._load_text("#include <iostream>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}\n", None)

    def load_example(self, title: str, code: str) -> None:
        if self._confirm_discard():
            self._load_text(code, None)
            self.statusBar().showMessage(f"โหลดตัวอย่าง: {title}")

    def _example_chosen(self, index: int) -> None:
        if index > 0:
            title, code = EXAMPLES[index - 1]
            self.load_example(title, code)
        self.example_box.setCurrentIndex(0)

    def open_file(self) -> None:
        if not self._confirm_discard():
            return
        start = self.settings.value("last_dir", str(Path.home()))
        name, _ = QFileDialog.getOpenFileName(self, "เปิดไฟล์", start, FILTER)
        if not name:
            return
        try:
            text, enc = textio.read_source(name)
        except OSError as e:
            QMessageBox.warning(self, APP_NAME, f"เปิดไฟล์ไม่สำเร็จ: {e}")
            return
        self.settings.setValue("last_dir", str(Path(name).parent))
        self._load_text(text, Path(name))
        if enc not in ("utf-8", "utf-8-sig"):
            self.statusBar().showMessage(f"อ่านไฟล์ด้วย {enc} — เมื่อบันทึกจะแปลงเป็น UTF-8 ให้อัตโนมัติ")

    def save_file(self) -> bool:
        if self.path is None:
            return self.save_file_as()
        return self._write(self.path)

    def save_file_as(self) -> bool:
        start = self.settings.value("last_dir", str(Path.home()))
        suggested = str(Path(start) / (self.path.name if self.path else "program.cpp"))
        name, _ = QFileDialog.getSaveFileName(self, "บันทึกเป็น", suggested, FILTER)
        if not name:
            return False
        if not Path(name).suffix:
            name += ".cpp"
        self.settings.setValue("last_dir", str(Path(name).parent))
        return self._write(Path(name))

    def _write(self, path: Path) -> bool:
        try:
            textio.write_source(path, self.editor.toPlainText())
        except OSError as e:
            QMessageBox.warning(self, APP_NAME, f"บันทึกไฟล์ไม่สำเร็จ: {e}")
            return False
        self.path = path
        self.editor.document().setModified(False)
        self._update_title()
        self.statusBar().showMessage(f"บันทึกแล้ว: {path}")
        return True

    # ---------- พิมพ์ ----------
    def _doc_title(self) -> str:
        return self.path.name if self.path else "โปรแกรมภาษา C++"

    def print_code(self) -> None:
        if printing.print_text(self, self._doc_title(), self.editor.toPlainText()):
            self.statusBar().showMessage("ส่งงานพิมพ์แล้ว")

    def print_output(self) -> None:
        text = self.console.output.toPlainText()
        if not text.strip():
            QMessageBox.information(self, APP_NAME, "ยังไม่มีผลลัพธ์ให้พิมพ์ ลองรันโปรแกรมก่อน")
            return
        printing.print_text(self, "ผลลัพธ์ของ " + self._doc_title(), text, line_numbers=False)

    def export_code_pdf(self) -> None:
        base = (self.path.with_suffix(".pdf").name if self.path else "program.pdf")
        start = str(Path(self.settings.value("last_dir", str(Path.home()))) / base)
        name, _ = QFileDialog.getSaveFileName(self, "ส่งออกเป็น PDF", start, "PDF (*.pdf)")
        if name:
            printing.export_pdf(name, self._doc_title(), self.editor.toPlainText())
            self.statusBar().showMessage(f"ส่งออกแล้ว: {name}")

    # ---------- มุมมอง ----------
    def _zoom(self, delta: int) -> None:
        size = max(8, min(40, self.editor.font_size() + delta))
        self.editor.set_font_size(size)
        self.console.set_font_size(max(10, size - 1))
        self.settings.setValue("font_size", size)

    def _toggle_dark(self) -> None:
        self.dark = self.a_dark.isChecked()
        self.settings.setValue("dark", self.dark)
        self._apply_theme()

    def _apply_theme(self) -> None:
        QApplication.instance().setStyleSheet(DARK_QSS if self.dark else "")
        self.editor.set_dark(self.dark)
        self.console.set_dark(self.dark)

    def _about(self) -> None:
        QMessageBox.about(
            self, APP_NAME,
            "<b>Cpp-Kub</b> — โปรแกรมเขียน C++ สำหรับการเรียนการสอน<br><br>"
            "• พิมพ์โค้ดและข้อมูลนำเข้าเป็นภาษาไทยได้ (UTF-8)<br>"
            "• อธิบายข้อผิดพลาดของคอมไพเลอร์เป็นภาษาไทย<br>"
            "• พิมพ์โค้ดและผลลัพธ์ หรือส่งออกเป็น PDF ได้ <br>"
            "• ใช้งานออฟไลน์ได้ทั้งหมด <br>"
            "• By : Cerebrega.com <br>"
            "• Mail : info@cerebrega.com")

    def closeEvent(self, e) -> None:
        if self._confirm_discard():
            self.runner.stop()
            e.accept()
        else:
            e.ignore()
