"""แผง "ตัวช่วยมองเห็นการทำงาน" ด้านขวาของตัวแก้ไข: ตารางตัวแปร (งานถัดไปเพิ่ม call stack/ภาพหน่วยความจำ)"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QLabel, QListWidget, QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .. import theme
from ..compiler import describe_exit
from .loops import LoopStatus
from .model import Frame, Snapshot, Var

UNREADABLE_TEXT = "อ่านไม่ได้"


class VisualizerPanel(QWidget):
    frame_selected = Signal(int)          # ผู้ใช้คลิกเฟรมใน call stack → ส่งเลขบรรทัดของเฟรมนั้น

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
        self.split.addWidget(self.stack)
        self.split.addWidget(self.variables)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.info_label)
        lay.addWidget(self.loop_label)
        lay.addWidget(self.split, 1)

    # ---------- สาธารณะ ----------
    def show_snapshot(self, snap: Snapshot) -> None:
        self._snapshot = snap
        self.variables.clear()
        self.stack.clear()
        if snap.exited:
            self.info_label.setText(f"โปรแกรมจบด้วยรหัส {snap.exit_code}")
            return
        if snap.signal:
            why = describe_exit(11, True) if snap.signal == "SIGSEGV" else None
            self.info_label.setText(f"โปรแกรมหยุดผิดปกติ ({snap.signal})" + (f" — {why}" if why else ""))
        elif snap.frames:
            self.info_label.setText(f"บรรทัด {snap.line} · {snap.func}()")
        else:
            self.info_label.setText("")
        self.stack.blockSignals(True)
        self.stack.clear()
        for fr in snap.frames:
            args = ", ".join(f"{v.name}={v.value}" for v in fr.args)
            self.stack.addItem(f"{fr.func}({args})  บรรทัด {fr.line}")
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
        self.info_label.setText("")
        self.set_loops([], {})

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
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
        if var.changed:
            brush = QBrush(QColor(theme.palette(self._dark)["changed"]))
            for col in range(3):
                item.setBackground(col, brush)
        if var.unreadable:
            danger = QBrush(QColor(theme.palette(self._dark)["danger"]))
            item.setForeground(2, danger)
        for child in var.children:
            self._add(item, child)
        if var.more:
            QTreeWidgetItem(item, [f"… อีก {var.more} ช่อง", "", ""])
