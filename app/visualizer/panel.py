"""แผง "ตัวช่วยมองเห็นการทำงาน" ด้านขวาของตัวแก้ไข: ตารางตัวแปร (งานถัดไปเพิ่ม call stack/ภาพหน่วยความจำ)"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .. import theme
from .loops import LoopStatus
from .memory_view import MemoryView
from .model import Frame, Snapshot, Var, describe_signal

UNREADABLE_TEXT = "อ่านไม่ได้"


class VisualizerPanel(QWidget):
    frame_selected = Signal(int)          # ผู้ใช้คลิกเฟรมใน call stack → ส่งเลขบรรทัดของเฟรมนั้น
    step_over_requested = Signal()
    step_into_requested = Signal()
    step_out_requested = Signal()
    stop_requested = Signal()
    restart_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("VisualizerPanel")
        self._dark = False
        self._snapshot: Snapshot | None = None
        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        self.loop_label = QLabel("")
        self.loop_label.setObjectName("LoopBadge")
        self.loop_label.setStyleSheet("font-weight:600; padding:4px 8px;")
        self.loop_label.hide()
        self.stack = QListWidget()
        self.stack.currentRowChanged.connect(self._on_stack_row)
        self.variables = QTreeWidget()
        self.variables.setHeaderLabels(["ชื่อ", "ชนิด", "ค่า"])
        self.variables.setRootIsDecorated(True)
        self.variables.setUniformRowHeights(True)
        self.split = QSplitter(Qt.Vertical)
        self.split.addWidget(self._section("Call stack", self.stack))
        self.memory = MemoryView()
        self.split.addWidget(self._section("ตัวแปรในเฟรมปัจจุบัน", self.variables))
        self.split.addWidget(self.memory)
        self.explain_label = QLabel("")
        self.explain_label.setObjectName("ExplainBox")
        self.explain_label.setWordWrap(True)
        self.explain_label.hide()
        # แถบปุ่มท้ายแผง (ใหญ่ อ่านชัด) + ตัวนับขั้น
        self.btn_over = self._button("ข้ามบรรทัด  F10", self.step_over_requested)
        self.btn_into = self._button("เข้าฟังก์ชัน  F11", self.step_into_requested)
        self.btn_out = self._button("ออกจากฟังก์ชัน", self.step_out_requested)
        self.btn_stop = self._button("หยุดเล่น", self.stop_requested)
        self.btn_restart = self._button("เริ่มใหม่", self.restart_requested)
        self.step_label = QLabel("")
        self.step_label.setObjectName("StepCounter")
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 6, 8, 8)
        bar.setSpacing(6)
        for b in (self.btn_over, self.btn_into, self.btn_out, self.btn_stop, self.btn_restart):
            bar.addWidget(b)
        bar.addStretch(1)
        bar.addWidget(self.step_label)
        self.set_stepping_enabled(False)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.info_label)
        lay.addWidget(self.loop_label)
        lay.addWidget(self.split, 1)
        lay.addWidget(self.explain_label)
        lay.addLayout(bar)

    @staticmethod
    def _section(title: str, widget: QWidget) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        head = QLabel(title)
        head.setObjectName("SectionTitle")
        lay.addWidget(head)
        lay.addWidget(widget, 1)
        return box

    def _button(self, text: str, signal) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName("StepButton")
        b.clicked.connect(lambda: signal.emit())
        return b

    def set_stepping_enabled(self, enabled: bool) -> None:
        """ปุ่มก้าวเดินใช้ได้เมื่อโปรแกรมหยุดรอ (หยุดเล่น/เริ่มใหม่ ใช้ได้ตลอดที่ดีบักอยู่)"""
        for b in (self.btn_over, self.btn_into, self.btn_out):
            b.setEnabled(enabled)

    def set_step(self, n: int) -> None:
        self.step_label.setText(f"ขั้นที่ {n}" if n > 0 else "")

    def set_explanation(self, text: str) -> None:
        self.explain_label.setText(text)
        self.explain_label.setVisible(bool(text))

    # ---------- สาธารณะ ----------
    def show_snapshot(self, snap: Snapshot) -> None:
        self._snapshot = snap
        self.variables.clear()
        self.stack.clear()
        self.memory.show_snapshot(snap)
        if snap.exited:
            self.info_label.setText(f"โปรแกรมจบด้วยรหัส {snap.exit_code}")
            return
        if snap.signal:
            why = describe_signal(snap.signal)
            self.info_label.setText(f"โปรแกรมหยุดผิดปกติ ({snap.signal})" + (f" — {why}" if why else ""))
        elif snap.frames:
            self.info_label.setText(f"บรรทัด {snap.line} · {snap.func}()")
        else:
            self.info_label.setText("")
        self.stack.blockSignals(True)
        self.stack.clear()
        for i, fr in enumerate(snap.frames):
            args = ", ".join(f"{v.name}={v.value}" for v in fr.args)
            here = "    ◄ อยู่ที่นี่" if i == 0 else ""
            item = QListWidgetItem(f"{fr.func}({args})  บรรทัด {fr.line}{here}")
            color = QColor(theme.frame_color(self._dark, len(snap.frames) - 1 - i))   # main = 0 ตรงกับภาพหน่วยความจำ
            item.setForeground(QBrush(color))
            tint = QColor(color)
            tint.setAlpha(46)
            item.setBackground(QBrush(tint))
            f = item.font()
            f.setBold(i == 0)
            item.setFont(f)
            self.stack.addItem(item)
        if snap.frames:
            self.stack.setCurrentRow(0)
        self.stack.blockSignals(False)
        if snap.frames:
            self._populate(snap.frames[0])

    def set_loops(self, statuses: list[LoopStatus], values: dict[str, str]) -> None:
        """แสดงป้าย "วนรอบที่ N · i = ค่า" (loop ซ้อนกันคั่นด้วย ›) ซ่อนเมื่อไม่ได้อยู่ใน loop"""
        if not statuses:
            self.loop_label.setText("")
            self.loop_label.hide()
            return
        parts = []
        for s in statuses:
            text = f"วนรอบที่ {s.iteration}"
            if s.var:
                text += f" · {s.var} = {values.get(s.var, '?')}"
            parts.append(text)
        self.loop_label.setText(" › ".join(parts))
        self.loop_label.show()

    def clear(self) -> None:
        self._snapshot = None
        self.variables.clear()
        self.stack.clear()
        self.memory.clear()
        self.info_label.setText("")
        self.set_loops([], {})
        self.set_explanation("")
        self.set_step(0)

    def set_zoom(self, font_size: int) -> None:
        """ขยายภาพหน่วยความจำ/ตารางตัวแปร/call stack ตามขนาดตัวอักษรของตัวแก้ไข (ฐาน 13pt = ปกติ)"""
        self.memory.set_scale(font_size / 13)
        for w in (self.variables, self.stack):
            f = w.font()
            f.setPointSize(max(8, round(font_size * 0.85)))
            w.setFont(f)
        for w in (self.explain_label, self.btn_over, self.btn_into, self.btn_out, self.btn_stop, self.btn_restart):
            f = w.font()
            f.setPointSize(max(9, round(font_size * 0.9)))
            w.setFont(f)

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        self.memory.set_dark(dark)
        if self._snapshot is not None:
            self.show_snapshot(self._snapshot)

    # ---------- ภายใน ----------
    def _on_stack_row(self, row: int) -> None:
        snap = self._snapshot
        if snap is None or not 0 <= row < len(snap.frames):
            return
        self.variables.clear()
        self._populate(snap.frames[row])
        self.frame_selected.emit(snap.frames[row].line)

    def _populate(self, frame: Frame) -> None:
        for var in frame.args + frame.locals:
            self._add(self.variables.invisibleRootItem(), var)
        for i in range(self.variables.topLevelItemCount()):
            item = self.variables.topLevelItem(i)
            if item.childCount():
                item.setExpanded(True)
        for col in range(3):
            self.variables.resizeColumnToContents(col)

    def _add(self, parent: QTreeWidgetItem, var: Var) -> None:
        shown = UNREADABLE_TEXT if var.unreadable else var.value
        if var.kind in ("array", "struct") and var.children:
            shown = ""                     # ค่าของลูกแสดงในแถวลูกอยู่แล้ว
        item = QTreeWidgetItem(parent, [var.name, var.type, shown])
        colors = theme.type_colors(self._dark, theme.type_category(var.type, var.value, var.kind))
        if colors:                                         # ชื่อชนิดใช้สีเดียวกับกล่องในภาพ
            item.setForeground(1, QBrush(QColor(colors[1])))
            bold = item.font(1)
            bold.setBold(True)
            item.setFont(1, bold)
        if var.changed:
            brush = QBrush(QColor(theme.changed_colors(self._dark)[0]))
            for col in range(3):
                item.setBackground(col, brush)
                if self._dark:
                    item.setForeground(col, QBrush(QColor("#ffffff")))
        if var.unreadable:
            danger = QBrush(QColor(theme.palette(self._dark)["danger"]))
            item.setForeground(2, danger)
        for child in var.children:
            self._add(item, child)
        if var.more:
            QTreeWidgetItem(item, [f"… อีก {var.more} ช่อง", "", ""])
