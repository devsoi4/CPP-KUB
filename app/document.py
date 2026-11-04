"""เอกสารหนึ่งแท็บ: ตัวแก้ไขโค้ด + พาธไฟล์ + ข้อมูลนำเข้าล่วงหน้าของไฟล์นั้น"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QObject

from .editor import CodeEditor


def _norm(p: Path) -> str:
    return os.path.normcase(str(Path(p).resolve()))


class Document(QObject):
    def __init__(self, path: Path | None = None, untitled_no: int = 0, encoding: str = "utf-8"):
        super().__init__()
        self.editor = CodeEditor()
        self.path = path
        self.untitled_no = untitled_no
        self.encoding = encoding
        self.preset = ""
        self.preset_eof = False

    def title(self) -> str:
        return self.path.name if self.path else f"ไม่มีชื่อ-{self.untitled_no}"

    def is_modified(self) -> bool:
        return self.editor.document().isModified()

    def matches(self, path: Path) -> bool:
        return self.path is not None and _norm(self.path) == _norm(path)
