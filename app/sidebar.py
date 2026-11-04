"""แถบไอคอนด้านซ้าย (Activity bar) และแผง Explorer: ไฟล์ที่เปิดอยู่ / ตัวอย่างโค้ด / โฟลเดอร์งาน"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QPushButton, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from . import icons, theme
from .document import Document
from .examples import EXAMPLES

CODE_SUFFIXES = {".cpp", ".cc", ".cxx", ".h", ".hpp"}
_KIND = Qt.UserRole
_PAYLOAD = Qt.UserRole + 1


class ActivityBar(QWidget):
    explorer_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("ActivityBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(48)
        self.explorer_btn = QToolButton()
        self.explorer_btn.setCheckable(True)
        self.explorer_btn.setChecked(True)
        self.explorer_btn.setToolTip("แสดง/ซ่อน Explorer (Ctrl+B)")
        self.explorer_btn.toggled.connect(self.explorer_toggled.emit)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 2, 4, 6)
        lay.addWidget(self.explorer_btn)
        lay.addStretch(1)
        self.explorer_btn.setFixedSize(38, 38)
        self.explorer_btn.setIconSize(QSize(22, 22))
        self._dark = False
        self.explorer_btn.toggled.connect(self._refresh_icon)
        self._refresh_icon()

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        self._refresh_icon()

    def _refresh_icon(self, *_) -> None:
        p = theme.palette(self._dark)
        # ปุ่มที่เปิดอยู่ใช้สี accent ให้รู้ว่าแผงไหนกำลังแสดง
        color = p["accent"] if self.explorer_btn.isChecked() else p["muted"]
        self.explorer_btn.setIcon(icons.icon("explorer", color, 22))


class Explorer(QWidget):
    open_path_requested = Signal(str)
    example_requested = Signal(str)
    document_requested = Signal(object)
    choose_folder_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Explorer")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumWidth(180)
        self._dark = False
        self._docs: list[Document] = []
        self._current: Document | None = None
        self._folder: str | None = None

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setEditTriggers(QTreeWidget.NoEditTriggers)
        self.tree.itemClicked.connect(self._clicked)
        self.choose_btn = QPushButton("เลือกโฟลเดอร์งาน...")
        self.choose_btn.setObjectName("GhostButton")
        self.choose_btn.clicked.connect(self.choose_folder_requested.emit)

        self._g_docs = self._group("ไฟล์ที่เปิดอยู่")
        self._g_examples = self._group("ตัวอย่างโค้ด")
        self._g_folder = self._group("โฟลเดอร์งาน")
        for title, _ in EXAMPLES:
            self._add(self._g_examples, title, "example", title)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 6, 4, 4)
        lay.setSpacing(6)
        lay.addWidget(self.tree, 1)
        lay.addWidget(self.choose_btn)
        self._refresh_icons()

    @property
    def folder(self) -> str | None:
        return self._folder

    # ---------- สร้างรายการ ----------
    def _group(self, title: str) -> QTreeWidgetItem:
        g = QTreeWidgetItem(self.tree, [title])
        g.setFlags(Qt.ItemIsEnabled)
        f = g.font(0)
        f.setBold(True)
        f.setPointSizeF(f.pointSizeF() * 0.9)
        f.setLetterSpacing(QFont.PercentageSpacing, 104)
        g.setFont(0, f)
        g.setExpanded(True)
        return g

    def _add(self, group, text, kind, payload, tip: str | None = None) -> QTreeWidgetItem:
        it = QTreeWidgetItem(group, [text])
        it.setData(0, _KIND, kind)
        it.setData(0, _PAYLOAD, payload)
        if tip:
            it.setToolTip(0, tip)
        return it

    def _refresh_icons(self) -> None:
        c = theme.palette(self._dark)["muted"]
        for group, name in ((self._g_docs, "file"), (self._g_examples, "example"), (self._g_folder, "file")):
            group.setForeground(0, QBrush(QColor(c)))     # หัวข้อกลุ่มสีจาง ให้รายการเด่นกว่า
            ic = icons.icon(name, c, 16)
            for i in range(group.childCount()):
                group.child(i).setIcon(0, ic)
        self._g_folder.setIcon(0, icons.icon("folder", c, 16))

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        self._refresh_icons()

    # ---------- ข้อมูล ----------
    def set_documents(self, docs: list[Document], current: Document | None) -> None:
        self._docs, self._current = list(docs), current
        self._g_docs.takeChildren()
        for d in docs:
            it = self._add(self._g_docs, d.title(), "doc", d, str(d.path) if d.path else None)
            if d is current:
                f = it.font(0)
                f.setWeight(QFont.Bold)
                it.setFont(0, f)
        self._refresh_icons()

    def set_folder(self, path: str | None) -> None:
        self._folder = path
        self._g_folder.takeChildren()
        label = "โฟลเดอร์งาน"
        folder = Path(path) if path else None
        if folder is not None:
            label += f" — {folder.name or folder}"
            try:
                files = sorted((p for p in folder.iterdir()
                                if p.is_file() and p.suffix.lower() in CODE_SUFFIXES),
                               key=lambda p: p.name.lower())
            except OSError:
                files = []
            for p in files:
                self._add(self._g_folder, p.name, "file", str(p), str(p))
        self._g_folder.setText(0, label)
        self._refresh_icons()

    # ---------- การคลิก ----------
    def _clicked(self, item: QTreeWidgetItem, _col: int = 0) -> None:
        kind, payload = item.data(0, _KIND), item.data(0, _PAYLOAD)
        if kind == "doc":
            self.document_requested.emit(payload)
        elif kind == "example":
            self.example_requested.emit(payload)
        elif kind == "file":
            self.open_path_requested.emit(payload)
