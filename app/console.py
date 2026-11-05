"""หน้าต่างผลลัพธ์ (stdout/stderr) + ช่องพิมพ์ข้อมูลนำเข้า (stdin) รองรับภาษาไทย"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QPlainTextEdit, QPushButton, QTabWidget,
    QVBoxLayout, QWidget,
)

from . import theme
from .editor import code_font


def _colors(dark: bool) -> dict[str, str]:
    p = theme.palette(dark)
    return dict(out=p["text"], err=p["danger"], info=p["accent"], echo=p["echo"],
                ok=p["ok"], warn=p["warn"])


class EmptyHintList(QListWidget):
    """QListWidget ที่วาดข้อความกลางพื้นที่เมื่อไม่มีรายการ (empty state)"""

    def __init__(self, hint: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.hint = hint

    def paintEvent(self, e) -> None:
        super().paintEvent(e)
        if self.count() == 0:
            p = QPainter(self.viewport())
            p.setPen(QColor(theme.palette(self.property("dark") is True)["muted"]))
            p.drawText(self.viewport().rect(), Qt.AlignCenter | Qt.TextWordWrap, self.hint)


class ConsoleWidget(QWidget):
    input_submitted = Signal(str)
    eof_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.dark = False

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(code_font(12))
        self.output.setMaximumBlockCount(20000)
        self.output.setPlaceholderText("▶  กด F5 เพื่อรันโปรแกรม — ผลลัพธ์จะแสดงที่นี่\n🐞  กด F9 เพื่อดีบักและดูค่าตัวแปรทีละบรรทัด")

        self.input = QLineEdit()
        self.input.setFont(code_font(12))
        self.input.setPlaceholderText("พิมพ์ข้อมูลที่โปรแกรมรออยู่ (cin) แล้วกด Enter — พิมพ์ภาษาไทยได้")
        self.input.returnPressed.connect(self._submit)
        self.send_btn = QPushButton("ส่ง")
        self.send_btn.setObjectName("SendButton")
        self.send_btn.clicked.connect(self._submit)
        self.eof_btn = QPushButton("จบข้อมูล (EOF)")
        self.eof_btn.setToolTip("ใช้กับ while (cin >> x) เพื่อบอกว่าไม่มีข้อมูลเพิ่มแล้ว")
        self.eof_btn.clicked.connect(self.eof_requested.emit)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(QLabel("ป้อนข้อมูล"))
        row.addWidget(self.input, 1)
        row.addWidget(self.send_btn)
        row.addWidget(self.eof_btn)

        run_tab = QWidget()
        lay = QVBoxLayout(run_tab)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)
        lay.addWidget(self.output, 1)
        lay.addLayout(row)

        self.preset = QPlainTextEdit()
        self.preset.setFont(code_font(12))
        self.preset.setPlaceholderText(
            "ใส่ข้อมูลนำเข้าทั้งหมดไว้ล่วงหน้าที่นี่ (บรรทัดละค่า)\n"
            "เมื่อกดรัน โปรแกรมจะได้รับข้อมูลนี้ให้อัตโนมัติ — สะดวกเวลาทดสอบซ้ำหลายรอบ")
        self.preset_auto_eof = QPushButton("ส่ง EOF หลังข้อมูลล่วงหน้า")
        self.preset_auto_eof.setCheckable(True)
        self.preset_auto_eof.setToolTip("เปิดเมื่อโค้ดอ่านข้อมูลด้วย while (cin >> x)")
        preset_tab = QWidget()
        pl = QVBoxLayout(preset_tab)
        pl.setContentsMargins(8, 8, 8, 8)
        pl.setSpacing(8)
        pl.addWidget(self.preset, 1)
        pl.addWidget(self.preset_auto_eof)

        self.problems = EmptyHintList("✔  ไม่พบปัญหา\nข้อผิดพลาดและคำเตือนของคอมไพเลอร์จะแสดงที่นี่")
        self.problems.setWordWrap(True)
        self.problems.setResizeMode(QListWidget.Adjust)
        self.problems.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("PanelTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(run_tab, "ผลลัพธ์")
        self.tabs.addTab(self.problems, "ปัญหา")
        self.tabs.addTab(preset_tab, "ข้อมูลนำเข้าล่วงหน้า")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.tabs)
        self.set_input_enabled(False)

    # ---------- สถานะ ----------
    def set_dark(self, dark: bool) -> None:
        self.dark = dark
        self.problems.setProperty("dark", dark)
        self.problems.viewport().update()

    def set_input_enabled(self, enabled: bool) -> None:
        for w in (self.input, self.send_btn, self.eof_btn):
            w.setEnabled(enabled)
        if enabled:
            self.tabs.setCurrentIndex(0)
            self.input.setFocus()

    def preset_text(self) -> str:
        return self.preset.toPlainText()

    def preset_eof(self) -> bool:
        return self.preset_auto_eof.isChecked()

    def set_preset(self, text: str, eof: bool) -> None:
        self.preset.setPlainText(text)
        self.preset_auto_eof.setChecked(eof)

    def set_problem_count(self, n: int) -> None:
        self.tabs.setTabText(1, f"ปัญหา ({n})" if n else "ปัญหา")

    def show_problems(self) -> None:
        self.tabs.setCurrentIndex(1)

    def set_font_size(self, size: int) -> None:
        for w in (self.output, self.input, self.preset, self.problems):
            w.setFont(code_font(size))

    # ---------- แสดงข้อความ ----------
    def clear(self) -> None:
        self.output.clear()

    def _append(self, text: str, color_key: str, *, bold: bool = False) -> None:
        colors = _colors(self.dark)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(colors[color_key]))
        if bold:
            fmt.setFontWeight(QFont.Bold)
        cur = self.output.textCursor()
        cur.movePosition(QTextCursor.End)
        cur.insertText(text, fmt)
        self.output.setTextCursor(cur)
        self.output.ensureCursorVisible()

    def append_out(self, text: str, is_err: bool = False) -> None:
        self._append(text, "err" if is_err else "out")

    def append_echo(self, text: str) -> None:
        """แสดงข้อมูลที่ส่งเข้าโปรแกรม (สีม่วง) เพื่อให้นักเรียนเห็นว่าป้อนอะไรไป"""
        self._append(text, "echo")

    def append_info(self, text: str, kind: str = "info") -> None:
        """ข้อความจากตัว IDE เอง (ไม่ใช่ผลลัพธ์ของโปรแกรม) — ขึ้นบรรทัดใหม่ให้เสมอ"""
        if self.output.toPlainText() and not self.output.toPlainText().endswith("\n"):
            self._append("\n", "out")
        self._append(text + "\n", kind, bold=True)

    def append_block(self, text: str, kind: str = "out") -> None:
        if self.output.toPlainText() and not self.output.toPlainText().endswith("\n"):
            self._append("\n", "out")
        self._append(text + "\n", kind)

    # ---------- ส่งข้อมูลเข้าโปรแกรม ----------
    def _submit(self) -> None:
        text = self.input.text()
        self.input.clear()
        self._append(text + "\n", "echo")
        self.input_submitted.emit(text + "\n")
