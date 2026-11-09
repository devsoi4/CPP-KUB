"""หน้าต่างหลักของ CPP-KUB: แท็บเอกสารหลายไฟล์ + Explorer + แผงผลลัพธ์/ปัญหา"""
from __future__ import annotations

import html
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QListWidgetItem, QMainWindow, QMessageBox,
    QSizePolicy, QSplitter, QToolBar, QVBoxLayout, QWidget,
)

from . import icons, printing, textio, theme
from .compiler import Runner, describe_exit, find_compiler
from .console import ConsoleWidget
from .document import Document
from .examples import DEFAULT_CODE, EXAMPLES, annotations_for
from .sidebar import ActivityBar, Explorer
from .tabs import DocumentTabs
from .toast import Toast
from .visualizer.explain import explain
from .visualizer.loops import LoopTracker, find_loops
from .visualizer.model import describe_signal
from .visualizer.panel import VisualizerPanel
from .visualizer.session import DebugSession

APP_NAME = "CPP-KUB"
FILTER = "ไฟล์ C++ (*.cpp *.cc *.cxx *.h *.hpp);;ทุกไฟล์ (*)"


def _card(w: QWidget) -> QFrame:
    """ห่อ widget ด้วยการ์ดมุมมน — เว้นขอบใน 4px เพื่อไม่ให้มุมเหลี่ยมของ widget ลูกโผล่พ้นมุมโค้ง"""
    card = QFrame()
    card.setObjectName("Card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(4, 4, 4, 4)
    lay.addWidget(w)
    return card


NEW_TEMPLATE = "#include <iostream>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}\n"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings(APP_NAME, APP_NAME)
        self.dark = self.settings.value("dark", False, type=bool)
        self._font_size = self.settings.value("font_size", 14, type=int)
        self._presenting = False
        self._pre_present: dict = {}
        self._prev_snap = None
        self._step_no = 0
        self._annotations: dict[int, str] = {}
        self._run_doc: Document | None = None      # เอกสารที่รันล่าสุด (ใช้ระบายสีบรรทัด/กระโดดไปบรรทัดที่ผิด)
        self._run_preset: tuple[str, bool] = ("", False)
        self._shown_doc: Document | None = None    # เอกสารที่เจ้าของข้อมูลล่วงหน้าตอนนี้อยู่ในแผงล่าง

        self.tabs = DocumentTabs()
        self.console = ConsoleWidget()
        self.problems = self.console.problems
        self.runner = Runner(self)
        self.debug_session = DebugSession(self.runner, self)
        self.visualizer = VisualizerPanel()
        self.visualizer.hide()
        self._debugging = False
        self._debug_doc: Document | None = None
        self._debug_signal: str | None = None
        self._loop_tracker = LoopTracker({})
        self.explorer = Explorer()
        self.activity = ActivityBar()

        self.tabs.setObjectName("DocTabs")
        self.explorer_card = _card(self.explorer)
        # Visualizer ไม่ห่อการ์ด (เทสต์/โค้ดซ่อน-แสดงตัวมันเองโดยตรง) จึงให้ตัวมันวาดพื้นการ์ดเอง
        self.visualizer.setAttribute(Qt.WA_StyledBackground, True)
        self.visualizer.layout().setContentsMargins(4, 4, 4, 4)
        right = QSplitter(Qt.Vertical)
        right.setObjectName("ShellSplit")
        right.setHandleWidth(8)
        right.addWidget(_card(self.tabs))
        right.addWidget(_card(self.console))
        right.setSizes([480, 300])
        right.setCollapsible(0, False)
        self.main_split = QSplitter(Qt.Horizontal)
        self.main_split.setObjectName("ShellSplit")
        self.main_split.setHandleWidth(8)
        self.main_split.addWidget(self.explorer_card)
        self.main_split.addWidget(right)
        self.main_split.addWidget(self.visualizer)
        self.main_split.setSizes([240, 720, 340])
        self.main_split.setCollapsible(1, False)
        central = QWidget()
        central.setObjectName("Shell")
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 8, 2)
        lay.setSpacing(0)
        lay.addWidget(self.activity)
        lay.addWidget(self.main_split, 1)
        self.setCentralWidget(central)

        self._status_msg, self._status_kind = "", "idle"
        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.RichText)
        self.statusBar().addWidget(self.status_label, 1)
        self.statusBar().setSizeGripEnabled(False)
        self.pos_label = QLabel("")
        self.enc_label = QLabel("")
        self.statusBar().addPermanentWidget(self.pos_label)
        self.statusBar().addPermanentWidget(self.enc_label)

        self.toast = Toast(central)
        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._connect_signals()

        self.console.set_font_size(max(10, self._font_size - 1))
        self.visualizer.set_zoom(self._font_size)
        self._apply_theme()
        self.resize(1280, 780)
        if not self._restore_session():
            self._add_doc(DEFAULT_CODE)
        cc = find_compiler()
        if cc:
            self._status("พร้อมแล้ว — กดปุ่ม ▶ รัน (F5) เพื่อเริ่ม", "ok")
            QTimer.singleShot(700, self._welcome_once)
        else:
            self._status("ไม่พบตัวคอมไพล์ g++ (ดูวิธีแก้ในปุ่ม รัน)", "error")

    # ---------- เอกสารปัจจุบัน (ให้โค้ด/เทสต์เดิมใช้ win.editor, win.path ได้) ----------
    @property
    def doc(self) -> Document | None:
        return self.tabs.current_document()

    @property
    def editor(self):
        return self.doc.editor

    @property
    def path(self) -> Path | None:
        return self.doc.path if self.doc else None

    @path.setter
    def path(self, value: Path | None) -> None:
        self.doc.path = value
        self.tabs.refresh_tab(self.doc)
        self._update_title()

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
        self.a_save = self._act("บันทึก", self.save_file, "Ctrl+S", "บันทึก (Ctrl+S)")
        self.a_save_as = self._act("บันทึกเป็น...", self.save_file_as, "Ctrl+Shift+S")
        self.a_close_tab = self._act("ปิดแท็บ", lambda: self.doc and self.close_document(self.doc), "Ctrl+W")
        self.a_print = self._act("พิมพ์โค้ด...", self.print_code, "Ctrl+P", "พิมพ์โค้ด (Ctrl+P)")
        self.a_print_out = self._act("พิมพ์ผลลัพธ์...", self.print_output)
        self.a_pdf = self._act("ส่งออกโค้ดเป็น PDF...", self.export_code_pdf)
        self.a_quit = self._act("ออกจากโปรแกรม", self.close, "Ctrl+Q")
        self.a_run = self._act("รัน", self.run_code, "F5", "คอมไพล์และรันโปรแกรม (F5)")
        self.a_stop = self._act("หยุด", self.stop_run, "Shift+F5", "หยุดโปรแกรมที่กำลังรัน (Shift+F5)")
        self.a_stop.setEnabled(False)
        self.a_debug = self._act("ดูทีละบรรทัด", self.start_debug, "F9",
                                 "เริ่มดีบัก (F9): เดินโปรแกรมทีละบรรทัดและดูค่าตัวแปร")
        self.a_step_over = self._act("ข้ามบรรทัด (F10)", lambda: self._debug_step(self.debug_session.step_over),
                                     "F10", "ทำบรรทัดนี้แล้วไปบรรทัดถัดไป (ไม่เข้าไปในฟังก์ชัน)")
        self.a_step_into = self._act("เข้าฟังก์ชัน (F11)", lambda: self._debug_step(self.debug_session.step_into),
                                     "F11", "เข้าไปในฟังก์ชันที่บรรทัดนี้เรียก")
        self.a_step_out = self._act("ออกจากฟังก์ชัน (Shift+F11)",
                                    lambda: self._debug_step(self.debug_session.step_out),
                                    "Shift+F11", "รันจนจบฟังก์ชันนี้แล้วกลับไปที่ผู้เรียก")
        self.a_continue = self._act("ทำต่อ (F8)", lambda: self._debug_step(self.debug_session.resume), "F8",
                                    "รันต่อไปจนจบโปรแกรม")
        for a in (self.a_step_over, self.a_step_into, self.a_step_out, self.a_continue):
            a.setEnabled(False)
        self.a_next_tab = self._act("แท็บถัดไป", lambda: self._cycle_tab(+1), "Ctrl+Tab")
        self.a_prev_tab = self._act("แท็บก่อนหน้า", lambda: self._cycle_tab(-1), "Ctrl+Shift+Tab")
        self.a_toggle_explorer = self._act("แสดง/ซ่อน Explorer", self.activity.explorer_btn.toggle, "Ctrl+B")
        self.a_zoom_in = self._act("ขยายตัวอักษร", lambda: self._zoom(+1), "Ctrl+=")
        self.a_zoom_out = self._act("ลดตัวอักษร", lambda: self._zoom(-1), "Ctrl+-")
        self.a_present = self._act("โหมดนำเสนอ", self._toggle_presentation, "F12",
                                   "ซ่อนเมนู/แถบข้างและขยายตัวอักษรสำหรับฉายจอ (F12)")
        self.a_present.setCheckable(True)
        self.a_dark = self._act("ธีมมืด", self._toggle_dark, tip="สลับธีมสว่าง/มืด")
        self.a_dark.setCheckable(True)
        self.a_dark.setChecked(self.dark)
        self.a_clear = self._act("ล้างหน้าต่างผลลัพธ์", self.console.clear)
        self.a_about = self._act("เกี่ยวกับโปรแกรม", self._about)
        # เพิ่มเข้าหน้าต่างด้วย: คีย์ลัดต้องทำงานแม้เมนู/แถบเครื่องมือถูกซ่อน (โหมดนำเสนอ) หรือไม่ได้อยู่ในเมนู
        for a in (self.a_next_tab, self.a_prev_tab, self.a_run, self.a_stop, self.a_debug, self.a_step_over,
                  self.a_step_into, self.a_step_out, self.a_continue, self.a_save, self.a_present,
                  self.a_zoom_in, self.a_zoom_out, self.a_new, self.a_open, self.a_close_tab):
            self.addAction(a)

    def _build_menus(self) -> None:
        mb = self.menuBar()
        m = mb.addMenu("ไฟล์")
        for a in (self.a_new, self.a_open, self.a_save, self.a_save_as, self.a_close_tab):
            m.addAction(a)
        m.addSeparator()
        for a in (self.a_print, self.a_print_out, self.a_pdf):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_quit)
        m = mb.addMenu("แก้ไข")
        m.addAction("เลิกทำ", lambda: self.editor.undo(), QKeySequence.Undo)
        m.addAction("ทำซ้ำ", lambda: self.editor.redo(), QKeySequence.Redo)
        m.addSeparator()
        m.addAction("ตัด", lambda: self.editor.cut(), QKeySequence.Cut)
        m.addAction("คัดลอก", lambda: self.editor.copy(), QKeySequence.Copy)
        m.addAction("วาง", lambda: self.editor.paste(), QKeySequence.Paste)
        m.addAction("เลือกทั้งหมด", lambda: self.editor.selectAll(), QKeySequence.SelectAll)
        m = mb.addMenu("รัน")
        m.addAction(self.a_run)
        m.addAction(self.a_stop)
        m.addAction(self.a_clear)
        m = mb.addMenu("ดีบัก")
        for a in (self.a_debug, self.a_step_over, self.a_step_into, self.a_step_out, self.a_continue):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_stop)
        m = mb.addMenu("ตัวอย่างโค้ด")
        for title, code in EXAMPLES:
            m.addAction(title, lambda c=code, t=title: self.load_example(t, c))
        m = mb.addMenu("มุมมอง")
        for a in (self.a_toggle_explorer, self.a_zoom_in, self.a_zoom_out, self.a_present, self.a_dark):
            m.addAction(a)
        mb.addMenu("ช่วยเหลือ").addAction(self.a_about)

    def _build_toolbar(self) -> None:
        self.toolbar = QToolBar("เครื่องมือ")
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(self.toolbar)
        self.toolbar.addAction(self.a_run)
        self.toolbar.addAction(self.a_stop)
        self.toolbar.addAction(self.a_debug)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.a_save)
        spacer = QWidget()
        spacer.setStyleSheet("background:transparent;")
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(spacer)
        self.toolbar.addAction(self.a_present)
        self.toolbar.addAction(self.a_dark)
        self.toolbar.widgetForAction(self.a_run).setObjectName("RunButton")
        self.toolbar.widgetForAction(self.a_stop).setObjectName("StopButton")
        self.toolbar.setIconSize(QSize(22, 22))
        for a in (self.a_save, self.a_present, self.a_dark):
            self.toolbar.widgetForAction(a).setToolButtonStyle(Qt.ToolButtonIconOnly)

    def _refresh_icons(self) -> None:
        p = theme.palette(self.dark)
        for action, name, color in ((self.a_run, "run", p["run_text"]), (self.a_stop, "stop", p["danger"]),
                                    (self.a_save, "save", p["text"]), (self.a_print, "print", p["text"]),
                                    (self.a_present, "present", p["text"]), (self.a_debug, "bug", p["text"]), (self.a_dark, "moon", p["text"])):
            action.setIcon(icons.icon(name, color))

    def _connect_signals(self) -> None:
        r = self.runner
        r.compile_started.connect(self._on_compile_started)
        r.compile_done.connect(self._on_compile_done)
        r.problem.connect(self._on_problem)
        r.run_started.connect(self._on_run_started)
        r.output.connect(self.console.append_out)
        r.run_finished.connect(self._on_run_finished)
        self.visualizer.frame_selected.connect(self._on_debug_frame_selected)
        v = self.visualizer
        v.step_over_requested.connect(self.a_step_over.trigger)     # trigger() ไม่ทำอะไรเมื่อ action ถูกปิดอยู่
        v.step_into_requested.connect(self.a_step_into.trigger)
        v.step_out_requested.connect(self.a_step_out.trigger)
        v.stop_requested.connect(self.stop_run)
        v.restart_requested.connect(self.restart_debug)
        d = self.debug_session
        d.stopped.connect(self._on_debug_stopped)
        d.output.connect(self.console.append_out)
        d.finished.connect(self._on_debug_finished)
        d.failed.connect(self._on_debug_failed)
        d.step_error.connect(self._on_debug_step_error)
        self.console.input_submitted.connect(r.send_input)
        self.console.eof_requested.connect(r.close_input)
        self.problems.itemActivated.connect(self._goto_problem)
        self.problems.itemClicked.connect(self._goto_problem)

        self.tabs.current_document_changed.connect(self._on_doc_changed)
        self.tabs.close_requested.connect(self.close_document)
        self.tabs.modified_changed.connect(lambda _d: self._update_title())
        self.tabs.tabBar().tabMoved.connect(lambda *_: self._sync_explorer())

        self.activity.explorer_toggled.connect(self.explorer_card.setVisible)
        self.explorer.document_requested.connect(self._activate_doc)
        self.explorer.example_requested.connect(self._open_example_by_title)
        self.explorer.open_path_requested.connect(lambda p: self.open_path(Path(p)))
        self.explorer.choose_folder_requested.connect(self.choose_folder)

    # ---------- แท็บ/เอกสาร ----------
    def _add_doc(self, text: str, path: Path | None = None, encoding: str = "utf-8") -> Document:
        doc = Document(path=path, untitled_no=0 if path else self.tabs.next_untitled_number(),
                       encoding=encoding)
        doc.editor.setPlainText(text)
        doc.editor.document().setModified(False)
        doc.editor.set_font_size(self._font_size)
        doc.editor.set_dark(self.dark)
        doc.editor.cursorPositionChanged.connect(lambda d=doc: self._on_cursor(d))
        self.tabs.add_document(doc)
        self._sync_explorer()
        return doc

    def _reusable_doc(self) -> Document | None:
        """แท็บ "ไม่มีชื่อ" ที่ยังไม่ถูกแก้และเป็นแท็บเดียว จะถูกใช้แทนเมื่อเปิดไฟล์/ตัวอย่าง (เหมือน VS Code)"""
        docs = self.tabs.documents()
        if len(docs) == 1:
            d = docs[0]
            if d.path is None and not d.is_modified() and d is not self._run_doc:
                return d
        return None

    def _open_text(self, text: str, path: Path | None, encoding: str = "utf-8") -> Document:
        doc = self._reusable_doc()
        if doc is None:
            return self._add_doc(text, path, encoding)
        doc.editor.setPlainText(text)
        doc.editor.document().setModified(False)
        doc.editor.clear_diagnostics()
        doc.path, doc.encoding, doc.preset, doc.preset_eof = path, encoding, "", False
        self.console.set_preset("", False)
        self.console.clear()
        self.problems.clear()
        self.console.set_problem_count(0)
        self.tabs.refresh_tab(doc)
        self._update_title()
        self._update_status_doc()
        self._sync_explorer()
        return doc

    def _activate_doc(self, doc: Document) -> None:
        i = self.tabs.indexOf(doc.editor)
        if i >= 0:
            self.tabs.setCurrentIndex(i)

    def _cycle_tab(self, step: int) -> None:
        n = self.tabs.count()
        if n > 1:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + step) % n)

    def _sync_explorer(self) -> None:
        self.explorer.set_documents(self.tabs.documents(), self.doc)

    def _on_doc_changed(self, doc: Document | None) -> None:
        prev = self._shown_doc
        if prev is not None and prev in self.tabs.documents():
            prev.preset, prev.preset_eof = self.console.preset_text(), self.console.preset_eof()
        self._shown_doc = doc
        if doc is not None:
            self.console.set_preset(doc.preset, doc.preset_eof)
            doc.editor.setFocus()
        self._update_title()
        self._update_status_doc()
        self._sync_explorer()

    def _on_cursor(self, doc: Document) -> None:
        if doc is self.doc:
            self._update_status_doc()

    def _update_status_doc(self) -> None:
        doc = self.doc
        if doc is None:
            self.pos_label.setText("")
            self.enc_label.setText("")
            return
        cur = doc.editor.textCursor()
        self.pos_label.setText(f"บรรทัด {cur.blockNumber() + 1}, คอลัมน์ {cur.positionInBlock() + 1}")
        self.enc_label.setText(f"{doc.encoding.upper()} · C++")

    # ---------- คอมไพล์/รัน ----------
    def run_code(self) -> None:
        doc = self.doc
        if doc is None or self.runner.busy:
            return
        self._run_doc = doc
        self._run_preset = (self.console.preset_text(), self.console.preset_eof())   # ของแท็บที่กดรัน ไม่ใช่แท็บที่เห็นตอนเริ่มรันจริง
        self.tabs.set_running(doc)
        self.console.clear()
        self.problems.clear()
        self.console.set_problem_count(0)
        doc.editor.clear_diagnostics()
        self.runner.start(doc.editor.toPlainText())

    def stop_run(self) -> None:
        """หยุดคอมไพล์/โปรแกรมที่รันอยู่ — Runner.stop() ไม่ส่งสัญญาณเมื่อยกเลิกระหว่างคอมไพล์ จึงต้องปิดสถานะ busy เอง"""
        if self._debugging:
            self.runner.stop()
            self.debug_session.stop()
            self._end_debug()
            return
        was_compiling = self.runner.is_compiling
        self.runner.stop()
        if was_compiling:
            self._on_run_finished(-1, "stopped")

    def _set_busy(self, busy: bool) -> None:
        self.a_run.setEnabled(not busy)
        self.a_debug.setEnabled(not busy)
        self.a_stop.setEnabled(busy)
        if not busy:
            self.tabs.set_running(None)

    def _on_compile_started(self) -> None:
        self._set_busy(True)
        self.tabs.set_running(self._run_doc)
        self._status("กำลังคอมไพล์...", "busy")
        self.console.append_info("⏳ กำลังคอมไพล์...")

    def _on_problem(self, msg: str) -> None:
        if self._debugging:
            self.debug_session.stop(quiet=True)
            self._end_debug()
        self._set_busy(False)
        self.console.set_input_enabled(False)
        self._status("เกิดปัญหา", "error")
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
        self.console.set_problem_count(self.problems.count())
        run_doc = self._run_doc
        if run_doc is not None:
            run_doc.editor.set_diagnostics(marks)
        n_err = sum(d.kind == "error" for d in diags)
        n_warn = sum(d.kind == "warning" for d in diags)
        if ok:
            msg = "✔ คอมไพล์สำเร็จ" + (f" (มีคำเตือน {n_warn} รายการ)" if n_warn else "")
            self.console.append_info(msg, "ok")
            self.toast.show_message(msg.lstrip("✔ "), "warn" if n_warn else "ok")
            if n_warn:
                self.console.append_block(format_report(diags), "warn")
            self.console.append_info("🐞 เริ่มดีบัก" if self._debugging else "▶ เริ่มรันโปรแกรม", "info")
        else:
            self._set_busy(False)
            self._status(f"คอมไพล์ไม่ผ่าน ({n_err} ข้อผิดพลาด)", "error")
            self.toast.show_message(f"คอมไพล์ไม่ผ่าน — พบข้อผิดพลาด {n_err} รายการ", "error", 4200)
            self.console.append_info(f"✖ คอมไพล์ไม่ผ่าน — พบข้อผิดพลาด {n_err} รายการ", "err")
            report = format_report(diags) or raw
            self.console.append_block(report, "err")
            first = next((d for d in diags if d.kind == "error" and d.line), None)
            if first and run_doc is not None:
                run_doc.editor.goto_line(first.line)
            if self._debugging:
                self._end_debug()

    # ---------- ดีบัก (Visualizer) ----------
    def start_debug(self) -> None:
        doc = self.doc
        if doc is None or self.runner.busy or self._debugging:
            return
        self._debugging = True
        self._debug_doc = doc
        self._debug_signal = None
        self._run_doc = doc
        self.tabs.set_running(doc)
        self.console.clear()
        self.problems.clear()
        self.console.set_problem_count(0)
        doc.editor.clear_diagnostics()
        doc.editor.set_debug_mode(True)
        self._loop_tracker = LoopTracker(find_loops(doc.editor.toPlainText()))
        self._prev_snap, self._step_no = None, 0
        self._annotations = annotations_for(doc.editor.toPlainText())
        self._update_debug_actions()
        self.debug_session.start(doc.editor.toPlainText(), self.console.preset_text())

    def restart_debug(self) -> None:
        """เริ่มดีบักใหม่ตั้งแต่ต้น (หยุดรอบเดิมก่อน)"""
        if not self._debugging:
            return
        self.stop_run()
        QTimer.singleShot(150, self.start_debug)

    def _debug_step(self, step) -> None:
        step()
        self._update_debug_actions()

    def _update_debug_actions(self) -> None:
        s = self.debug_session
        live = self._debugging and s.active and not s.busy
        for a in (self.a_step_over, self.a_step_into, self.a_step_out, self.a_continue):
            a.setEnabled(live)
        self.visualizer.set_stepping_enabled(live)

    def _on_debug_stopped(self, snap) -> None:
        doc = self._debug_doc
        if doc is None:
            return
        self.visualizer.show_snapshot(snap)
        self.visualizer.show()
        self._step_no += 1
        self.visualizer.set_step(self._step_no)
        self.visualizer.set_explanation(
            explain(self._prev_snap, snap, None if snap.exited else self._annotations.get(snap.line)))
        self._prev_snap = snap
        if snap.exited or not snap.frames:
            doc.editor.set_debug_line(None)
            self.visualizer.set_loops([], {})
        else:
            doc.editor.set_debug_line(snap.line)
            top = snap.frames[0]
            values = {v.name: v.value for v in top.args + top.locals}
            self.visualizer.set_loops(self._loop_tracker.update(len(snap.frames), snap.line), values)
            self._status(f"หยุดที่บรรทัด {snap.line} ใน {snap.func}()", "busy")
        if snap.signal:
            self._debug_signal = snap.signal
            why = describe_signal(snap.signal)
            self.console.append_info(f"💥 โปรแกรมหยุดทำงานผิดปกติ ({snap.signal})", "err")
            if why:
                self.console.append_block("   → " + why, "err")
        self._update_debug_actions()

    def _on_debug_step_error(self, msg: str) -> None:
        self.console.append_info(f"gdb ทำคำสั่งนี้ไม่ได้: {msg}", "warn")
        self._update_debug_actions()

    def _on_debug_frame_selected(self, line: int) -> None:
        if self._debugging and self._debug_doc is not None:
            self._debug_doc.editor.set_debug_line(line)

    def _on_debug_finished(self, code: int, reason: str) -> None:
        if reason == "ok":
            self.console.append_info(f"● โปรแกรมทำงานจบ (exit code {code})", "ok" if code == 0 else "warn")
        elif reason == "crash":
            if self._debug_signal is None:
                self.console.append_info("💥 โปรแกรมหยุดทำงานผิดปกติ", "err")
                why = describe_exit(code, True)
                if why:
                    self.console.append_block("   → " + why, "err")
        elif reason == "stopped":
            self.console.append_info("■ หยุดดีบัก", "warn")
        elif reason == "timeout":
            secs = self.debug_session.run_timeout_ms // 1000
            self.console.append_info(
                f"⏱ หยุดโปรแกรม: ไม่มีความเคลื่อนไหวเกิน {secs} วินาที (อาจวนลูปไม่รู้จบ)", "warn")
        elif reason == "step_limit":
            self.console.append_info("หยุดดีบัก: เดินครบ 100,000 ขั้นแล้ว (อาจมีลูปไม่รู้จบ)", "warn")
        elif reason == "gdb_died":
            self.console.append_info("ตัวดีบั๊ก (gdb) หยุดทำงานกะทันหัน", "err")
        self._end_debug()

    def _on_debug_failed(self, msg: str) -> None:
        self.console.append_info(msg, "err")
        self._status("เริ่มดีบักไม่ได้", "error")
        self._end_debug()

    def _end_debug(self) -> None:
        if not self._debugging:
            return
        self._debugging = False
        doc, self._debug_doc = self._debug_doc, None
        if doc is not None:
            doc.editor.set_debug_mode(False)
        self.visualizer.clear()
        self.visualizer.hide()
        self._loop_tracker.reset()
        self._prev_snap, self._step_no = None, 0
        self._set_busy(False)
        self._update_debug_actions()
        self._status("จบการดีบัก", "idle")

    def _on_run_started(self) -> None:
        self._status("กำลังรันโปรแกรม...", "busy")
        self.console.set_input_enabled(True)
        preset, auto_eof = self._run_preset
        if preset.strip():
            data = preset if preset.endswith("\n") else preset + "\n"
            shown = " ⏎ ".join(data.rstrip("\n").split("\n"))
            if len(shown) > 80:
                shown = shown[:80] + "…"
            self.console.append_info(f"📥 ส่งข้อมูลนำเข้าล่วงหน้าให้โปรแกรม: {shown}", "echo")
            self.runner.send_input(data)
            if auto_eof:
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
            self._status("หยุดเพราะหมดเวลา", "warn")
        elif reason == "output_limit":
            self.console.append_info("⛔ หยุดโปรแกรม: พิมพ์ข้อความมากเกินไป "
                                     "(อาจมีลูปที่พิมพ์ไม่รู้จบ)", "warn")
            self._status("หยุดเพราะพิมพ์มากเกินไป", "warn")
        elif reason == "stopped":
            self.console.append_info("■ ผู้ใช้สั่งหยุดโปรแกรม", "warn")
            self._status("หยุดแล้ว", "idle")
        elif reason == "crash" or crashed_text:
            self.console.append_info("💥 โปรแกรมหยุดทำงานผิดปกติ", "err")
            if crashed_text:
                self.console.append_block("   → " + crashed_text, "err")
            self._status("โปรแกรมหยุดผิดปกติ", "error")
        else:
            kind = "ok" if code == 0 else "warn"
            self.console.append_info(f"● โปรแกรมทำงานจบ (exit code {code})", kind)
            self._status("ทำงานเสร็จสิ้น", "ok")
            if code == 0:
                self.toast.show_message("โปรแกรมทำงานจบเรียบร้อย", "ok", 2200)

    def _goto_problem(self, item: QListWidgetItem) -> None:
        line = item.data(Qt.UserRole)
        doc = self._run_doc
        if line and doc is not None and doc in self.tabs.documents():
            self._activate_doc(doc)
            doc.editor.goto_line(int(line))

    # ---------- ไฟล์ ----------
    def _update_title(self, *_args) -> None:
        doc = self.doc
        if doc is None:
            self.setWindowTitle(APP_NAME)
            return
        star = " *" if doc.is_modified() else ""
        self.setWindowTitle(f"{doc.title()}{star} — {APP_NAME}")

    def _ask_save(self, doc: Document) -> str:
        """ถามผู้ใช้ว่าจะบันทึกก่อนปิดหรือไม่ คืน "save" / "discard" / "cancel" """
        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME)
        box.setText(f"ไฟล์ “{doc.title()}” ยังไม่ได้บันทึก ต้องการบันทึกก่อนหรือไม่?")
        save = box.addButton("บันทึก", QMessageBox.AcceptRole)
        discard = box.addButton("ไม่บันทึก", QMessageBox.DestructiveRole)
        box.addButton("ยกเลิก", QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save:
            return "save"
        if clicked is discard:
            return "discard"
        return "cancel"

    def _confirm_discard(self, doc: Document) -> bool:
        if not doc.is_modified():
            return True
        self._activate_doc(doc)
        choice = self._ask_save(doc)
        if choice == "cancel":
            return False
        if choice == "save":
            return self._save_doc(doc)
        return True

    def close_document(self, doc: Document) -> bool:
        if not self._confirm_discard(doc):
            return False
        if doc is self._run_doc:
            self.stop_run()
            self._run_doc = None
            self.tabs.set_running(None)
        self.tabs.remove_document(doc)
        doc.editor.setParent(None)
        if self.tabs.count() == 0:
            self._add_doc(NEW_TEMPLATE)
        self._sync_explorer()
        return True

    def new_file(self) -> None:
        self._add_doc(NEW_TEMPLATE)

    def load_example(self, title: str, code: str) -> None:
        self._open_text(code, None)
        self._status(f"โหลดตัวอย่าง: {title}", "idle")

    def _open_example_by_title(self, title: str) -> None:
        code = dict(EXAMPLES).get(title)
        if code is not None:
            self.load_example(title, code)

    def open_file(self) -> None:
        start = self.settings.value("last_dir", str(Path.home()))
        names, _ = QFileDialog.getOpenFileNames(self, "เปิดไฟล์", start, FILTER)
        for name in names:
            self.open_path(Path(name))

    def open_path(self, path: Path) -> None:
        path = Path(path)
        existing = self.tabs.find_by_path(path)
        if existing is not None:
            self._activate_doc(existing)
            return
        try:
            text, enc = textio.read_source(path)
        except OSError as e:
            QMessageBox.warning(self, APP_NAME, f"เปิดไฟล์ไม่สำเร็จ: {e}")
            return
        self.settings.setValue("last_dir", str(path.parent))
        self._open_text(text, path, enc)
        if enc not in ("utf-8", "utf-8-sig"):
            self._status(f"อ่านไฟล์ด้วย {enc} — เมื่อบันทึกจะแปลงเป็น UTF-8 ให้อัตโนมัติ", "warn")

    def save_file(self) -> bool:
        return self._save_doc(self.doc)

    def save_file_as(self) -> bool:
        return self._save_as(self.doc)

    def _save_doc(self, doc: Document) -> bool:
        if doc.path is None:
            return self._save_as(doc)
        return self._write(doc, doc.path)

    def _choose_save_path(self, doc: Document) -> Path | None:
        start = self.settings.value("last_dir", str(Path.home()))
        suggested = str(Path(start) / (doc.path.name if doc.path else "program.cpp"))
        name, _ = QFileDialog.getSaveFileName(self, "บันทึกเป็น", suggested, FILTER)
        if not name:
            return None
        p = Path(name)
        return p if p.suffix else p.with_suffix(".cpp")

    def _save_as(self, doc: Document) -> bool:
        path = self._choose_save_path(doc)
        if path is None:
            return False
        self.settings.setValue("last_dir", str(path.parent))
        return self._write(doc, path)

    def _write(self, doc: Document, path: Path) -> bool:
        try:
            textio.write_source(path, doc.editor.toPlainText())
        except OSError as e:
            QMessageBox.warning(self, APP_NAME, f"บันทึกไฟล์ไม่สำเร็จ: {e}")
            return False
        doc.path, doc.encoding = path, "utf-8"
        doc.editor.document().setModified(False)
        self.tabs.refresh_tab(doc)
        self._update_title()
        self._update_status_doc()
        self._sync_explorer()
        self._status(f"บันทึกแล้ว: {path}", "ok")
        self.toast.show_message(f"บันทึก {path.name} แล้ว", "ok")
        return True

    def choose_folder(self) -> None:
        start = self.settings.value("explorer/folder", self.settings.value("last_dir", str(Path.home())))
        name = QFileDialog.getExistingDirectory(self, "เลือกโฟลเดอร์งาน", start)
        if name:
            self.explorer.set_folder(name)
            self.settings.setValue("explorer/folder", name)

    # ---------- พิมพ์ ----------
    def _doc_title(self) -> str:
        return self.path.name if self.path else "โปรแกรมภาษา C++"

    def print_code(self) -> None:
        if printing.print_text(self, self._doc_title(), self.editor.toPlainText()):
            self._status("ส่งงานพิมพ์แล้ว", "ok")

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
            self._status(f"ส่งออกแล้ว: {name}", "ok")
            self.toast.show_message("ส่งออก PDF แล้ว", "ok")

    # ---------- มุมมอง ----------
    def _zoom(self, delta: int) -> None:
        self._set_font_size(self._font_size + delta, persist=not self._presenting)

    def _set_font_size(self, size: int, persist: bool = True) -> None:
        self._font_size = max(8, min(40, size))
        for d in self.tabs.documents():
            d.editor.set_font_size(self._font_size)
        self.console.set_font_size(max(10, self._font_size - 1))
        self.visualizer.set_zoom(self._font_size)
        if persist:
            self.settings.setValue("font_size", self._font_size)

    PRESENT_BOOST = 6

    def _toggle_presentation(self) -> None:
        """โหมดนำเสนอ: ซ่อนเมนู/แถบข้าง/แถบสถานะ และขยายตัวอักษรเพื่อฉายจอ — ไม่บันทึกขนาดลงการตั้งค่า"""
        on = not self._presenting
        self._presenting = on
        self.a_present.setChecked(on)
        if on:
            self._pre_present = {"font": self._font_size}
            self.menuBar().hide()
            self.statusBar().hide()
            self.activity.hide()
            self.explorer_card.hide()
            self._set_font_size(self._font_size + self.PRESENT_BOOST, persist=False)
        else:
            self.menuBar().show()
            self.statusBar().show()
            self.activity.show()
            self.explorer_card.setVisible(self.activity.explorer_btn.isChecked())
            self._set_font_size(self._pre_present.get("font", self._font_size), persist=False)

    def _welcome_once(self) -> None:
        if not self.settings.value("seen_welcome", False, type=bool):
            self.settings.setValue("seen_welcome", True)
            self.toast.show_message("เริ่มต้น: เลือกโค้ดจากเมนู “ตัวอย่างโค้ด” แล้วกดปุ่ม รัน", "info", 6000)

    def _toggle_dark(self) -> None:
        self.dark = self.a_dark.isChecked()
        self.settings.setValue("dark", self.dark)
        central = self.centralWidget()
        veil = QLabel(central)       # ภาพนิ่งของธีมเก่า แล้วเฟดหายเพื่อให้การสลับธีมนุ่มนวล
        veil.setPixmap(central.grab())
        veil.setGeometry(central.rect())
        veil.show()
        self._apply_theme()
        fx = QGraphicsOpacityEffect(veil)
        veil.setGraphicsEffect(fx)
        anim = QPropertyAnimation(fx, b"opacity", veil)
        anim.setDuration(240)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(veil.deleteLater)
        anim.start()
        self._theme_anim = anim

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        if self.toast.isVisible():
            self.toast.reposition()

    def _apply_theme(self) -> None:
        QApplication.instance().setStyleSheet(theme.build_qss(self.dark))
        for d in self.tabs.documents():
            d.editor.set_dark(self.dark)
        self.console.set_dark(self.dark)
        self.explorer.set_dark(self.dark)
        self.activity.set_dark(self.dark)
        self.visualizer.set_dark(self.dark)
        self._refresh_icons()
        self._status(self._status_msg, self._status_kind)
        # ตั้ง objectName หลังสร้างปุ่มแล้ว ต้อง polish ใหม่เพื่อให้ stylesheet มีผล
        for a in (self.a_run, self.a_stop):
            w = self.toolbar.widgetForAction(a)
            w.style().unpolish(w)
            w.style().polish(w)

    _STATUS_COLORS = dict(idle="muted", busy="accent", ok="ok", warn="warn", error="danger")

    def _status(self, msg: str, kind: str = "idle") -> None:
        """ข้อความในแถบสถานะ พร้อมจุดสีบอกสถานะ: idle/busy/ok/warn/error"""
        self._status_msg, self._status_kind = msg, kind
        color = theme.palette(self.dark)[self._STATUS_COLORS.get(kind, "muted")]
        self.statusBar().clearMessage()
        self.status_label.setText(f'<span style="color:{color}">●</span>&nbsp;&nbsp;{html.escape(msg)}')

    def _about(self) -> None:
        QMessageBox.about(
            self, APP_NAME,
            "<b>CPP-KUB</b> — โปรแกรมเขียน C++ สำหรับการเรียนการสอน<br><br>"
            "• พิมพ์โค้ดและข้อมูลนำเข้าเป็นภาษาไทยได้ (UTF-8)<br>"
            "• อธิบายข้อผิดพลาดของคอมไพเลอร์เป็นภาษาไทย<br>"
            "• พิมพ์โค้ดและผลลัพธ์ หรือส่งออกเป็น PDF ได้ <br>"
            "• ใช้งานออฟไลน์ได้ทั้งหมด <br>"
            "• By : Cerebrega.com <br>"
            "• Mail : info@cerebrega.com")

    # ---------- จำแท็บที่เปิดค้างไว้ ----------
    def _save_session(self) -> None:
        """จำเฉพาะไฟล์ที่บันทึกแล้ว (เนื้อหา "ไม่มีชื่อ" ที่ยังไม่บันทึกจะไม่ถูกเก็บ)"""
        docs = [d for d in self.tabs.documents() if d.path is not None]
        cur = self.doc
        self.settings.setValue("session/paths", [str(d.path) for d in docs])
        self.settings.setValue("session/active", str(cur.path) if cur is not None and cur.path else "")
        self.settings.setValue("explorer/visible", self.activity.explorer_btn.isChecked())   # ปุ่มคงสถานะจริงแม้กำลังซ่อนในโหมดนำเสนอ
        self.settings.setValue("explorer/folder", self.explorer.folder or "")

    def _restore_session(self) -> bool:
        """เปิดไฟล์ที่เคยเปิดค้างไว้ (ข้ามไฟล์ที่หายไปแล้ว) คืน True ถ้าเปิดได้อย่างน้อยหนึ่งไฟล์"""
        if not self.settings.value("explorer/visible", True, type=bool):
            self.activity.explorer_btn.setChecked(False)
        folder = self.settings.value("explorer/folder", "", type=str)
        if folder:
            self.explorer.set_folder(folder)
        paths = self.settings.value("session/paths", [], type=list)
        for p in paths:
            path = Path(p)
            if path.is_file():
                self.open_path(path)
        active = self.settings.value("session/active", "", type=str)
        if active and (doc := self.tabs.find_by_path(Path(active))) is not None:
            self._activate_doc(doc)
        return self.tabs.count() > 0

    def closeEvent(self, e) -> None:
        self._save_session()
        for doc in list(self.tabs.documents()):
            if not self._confirm_discard(doc):
                e.ignore()
                return
        self.debug_session.stop(quiet=True)
        self.runner.stop()
        e.accept()
