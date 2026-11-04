"""แท็บเอกสารแบบ VS Code: ปุ่มปิด, จุด ● เมื่อยังไม่บันทึก, ▶ เมื่อกำลังรัน"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabWidget

from .document import Document


class DocumentTabs(QTabWidget):
    current_document_changed = Signal(object)   # Document หรือ None
    close_requested = Signal(object)            # Document
    modified_changed = Signal(object)           # Document

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        self._docs: dict[int, Document] = {}   # id(editor) -> Document
        self._running: Document | None = None
        self._untitled_counter = 0
        self.tabCloseRequested.connect(lambda i: self._request_close(i))
        self.currentChanged.connect(lambda _i: self.current_document_changed.emit(self.current_document()))

    # ---------- เข้าถึงเอกสาร ----------
    def _doc_at(self, index: int) -> Document | None:
        w = self.widget(index)
        return self._docs.get(id(w)) if w is not None else None

    def documents(self) -> list[Document]:
        return [d for i in range(self.count()) if (d := self._doc_at(i))]

    def current_document(self) -> Document | None:
        return self._doc_at(self.currentIndex())

    def find_by_path(self, path: Path) -> Document | None:
        return next((d for d in self.documents() if d.matches(path)), None)

    def next_untitled_number(self) -> int:
        self._untitled_counter += 1
        return self._untitled_counter

    def _index_of(self, doc: Document) -> int:
        return self.indexOf(doc.editor)

    # ---------- เพิ่ม/ลบ ----------
    def add_document(self, doc: Document, activate: bool = True) -> int:
        self._docs[id(doc.editor)] = doc
        i = self.addTab(doc.editor, "")
        doc.editor.document().modificationChanged.connect(lambda _m, d=doc: self._on_modified(d))
        self.refresh_tab(doc)
        if activate:
            self.setCurrentIndex(i)
        return i

    def remove_document(self, doc: Document) -> None:
        i = self._index_of(doc)
        if i >= 0:
            self.removeTab(i)
        self._docs.pop(id(doc.editor), None)
        if self._running is doc:
            self._running = None

    def _request_close(self, index: int) -> None:
        doc = self._doc_at(index)
        if doc:
            self.close_requested.emit(doc)

    def _on_modified(self, doc: Document) -> None:
        self.refresh_tab(doc)
        self.modified_changed.emit(doc)

    # ---------- ป้ายแท็บ ----------
    def refresh_tab(self, doc: Document) -> None:
        i = self._index_of(doc)
        if i < 0:
            return
        prefix = "▶ " if doc is self._running else ("● " if doc.is_modified() else "")
        self.setTabText(i, prefix + doc.title())
        self.setTabToolTip(i, str(doc.path) if doc.path else doc.title())

    def set_running(self, doc: Document | None) -> None:
        old, self._running = self._running, doc
        for d in (old, doc):
            if d is not None:
                self.refresh_tab(d)
