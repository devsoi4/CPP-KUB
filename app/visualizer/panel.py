"""แผง "ตัวช่วยมองเห็นการทำงาน" ด้านขวาของตัวแก้ไข: ตารางตัวแปร (งานถัดไปเพิ่ม call stack/ภาพหน่วยความจำ)"""
from __future__ import annotations

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QLabel, QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

from .. import theme
from ..compiler import describe_exit
from .model import Frame, Snapshot, Var

UNREADABLE_TEXT = "อ่านไม่ได้"


class VisualizerPanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("VisualizerPanel")
        self._dark = False
        self._snapshot: Snapshot | None = None
        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        self.variables = QTreeWidget()
        self.variables.setHeaderLabels(["ชื่อ", "ชนิด", "ค่า"])
        self.variables.setRootIsDecorated(True)
        self.variables.setUniformRowHeights(True)
        self.split = QSplitter(Qt.Vertical)
        self.split.addWidget(self.variables)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.info_label)
        lay.addWidget(self.split, 1)

    # ---------- สาธารณะ ----------
    def show_snapshot(self, snap: Snapshot) -> None:
        self._snapshot = snap
        self.variables.clear()
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
        if snap.frames:
            self._populate(snap.frames[0])

    def clear(self) -> None:
        self._snapshot = None
        self.variables.clear()
        self.info_label.setText("")

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        if self._snapshot is not None:
            self.show_snapshot(self._snapshot)

    # ---------- ภายใน ----------
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
