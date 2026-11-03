"""พิมพ์โค้ด/ผลลัพธ์ออกเครื่องพิมพ์หรือส่งออกเป็น PDF (ภาษาไทยแสดงถูกต้อง)"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtGui import QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QWidget

from .editor import code_font


def build_document(title: str, text: str, *, line_numbers: bool = True) -> QTextDocument:
    """สร้างเอกสารสำหรับพิมพ์: หัวกระดาษ + เลขบรรทัด + ฟอนต์ที่รองรับภาษาไทย"""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    width = len(str(max(1, len(lines))))
    body = "\n".join(
        (f"{i:>{width}}  {ln}" if line_numbers else ln) for i, ln in enumerate(lines, start=1)
    )
    stamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    doc = QTextDocument()
    doc.setDefaultFont(code_font(10))
    doc.setPlainText(f"{title}    (พิมพ์เมื่อ {stamp})\n{'-' * 60}\n{body}")
    return doc


def _make_printer() -> QPrinter:
    printer = QPrinter(QPrinter.HighResolution)
    printer.setPageSize(QPageSize(QPageSize.A4))
    return printer


def print_text(parent: QWidget, title: str, text: str, *, line_numbers: bool = True) -> bool:
    """เปิดหน้าต่างเลือกเครื่องพิมพ์แล้วพิมพ์ คืน True ถ้าผู้ใช้สั่งพิมพ์"""
    printer = _make_printer()
    dialog = QPrintDialog(printer, parent)
    dialog.setWindowTitle("พิมพ์")
    if dialog.exec() != QPrintDialog.Accepted:
        return False
    build_document(title, text, line_numbers=line_numbers).print_(printer)
    return True


def export_pdf(path: str, title: str, text: str, *, line_numbers: bool = True) -> None:
    printer = _make_printer()
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(path)
    build_document(title, text, line_numbers=line_numbers).print_(printer)
