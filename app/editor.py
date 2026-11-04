"""ตัวแก้ไขโค้ด C++: เลขบรรทัด, ไฮไลต์สี, ย่อหน้าอัตโนมัติ, รองรับพิมพ์ภาษาไทย"""
from __future__ import annotations

import re

from PySide6.QtCore import QRect, QRegularExpression, QSize, Qt
from PySide6.QtGui import (
    QColor, QFont, QFontDatabase, QPainter, QSyntaxHighlighter, QTextCharFormat,
    QTextFormat, QTextCursor,
)
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from . import theme

KEYWORDS = (
    "alignas alignof auto bool break case catch char class const constexpr continue "
    "default delete do double else enum explicit extern false float for friend goto if "
    "inline int long mutable namespace new noexcept nullptr operator private protected "
    "public register return short signed sizeof static struct switch template this "
    "throw true try typedef typename union unsigned using virtual void volatile while "
    "override final"
).split()
TYPES = "string vector map set pair queue stack array cout cin cerr endl size_t".split()

# ฟอนต์ที่มีทั้งอักษรละตินความกว้างคงที่และรองรับภาษาไทยในเครื่อง Windows/Mac/Linux
FONT_CANDIDATES = [
    "Sarabun", "TH Sarabun New", "Noto Sans Mono Thai", "Cascadia Mono", "Consolas",
    "Tahoma", "Leelawadee UI", "Menlo", "DejaVu Sans Mono",
]


def code_font(size: int = 13) -> QFont:
    """เลือกฟอนต์ที่เครื่องมีอยู่จริง และตั้ง fallback ให้แสดงภาษาไทยได้"""
    available = set(QFontDatabase.families())
    # ฟอนต์โค้ดหลักมาก่อน แล้วตามด้วยฟอนต์ที่มีอักษรไทยเพื่อใช้เมื่อพบตัวอักษรไทย
    families = [f for f in ("Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono", "Courier New")
                if f in available]
    families += [f for f in ("Leelawadee UI", "Tahoma", "Noto Sans Thai", "Sarabun", "TH Sarabun New",
                             "Noto Sans Mono Thai", "Thonburi") if f in available]
    font = QFont()
    if families:
        font.setFamilies(families)
    else:
        font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
    font.setPointSize(size)
    font.setStyleHint(QFont.Monospace)
    return font


def _fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Bold)
    f.setFontItalic(italic)
    return f


class CppHighlighter(QSyntaxHighlighter):
    def __init__(self, doc, dark: bool = False):
        super().__init__(doc)
        self.set_theme(dark)

    def set_theme(self, dark: bool) -> None:
        c = theme.palette(dark)
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []
        kw = QRegularExpression(r"\b(" + "|".join(KEYWORDS) + r")\b")
        ty = QRegularExpression(r"\b(" + "|".join(TYPES) + r")\b")
        self._rules.append((ty, _fmt(c["ty"])))
        self._rules.append((kw, _fmt(c["kw"], bold=True)))
        self._rules.append((QRegularExpression(r"\b[A-Za-z_]\w*(?=\s*\()"), _fmt(c["fn"])))
        self._rules.append((QRegularExpression(r"\b\d+(\.\d+)?([eE][+-]?\d+)?[fFlLuU]*\b"), _fmt(c["num"])))
        self._rules.append((QRegularExpression(r"^\s*#\s*\w+"), _fmt(c["pp"], bold=True)))
        self._rules.append((QRegularExpression(r'"(\\.|[^"\\])*"'), _fmt(c["st"])))
        self._rules.append((QRegularExpression(r"'(\\.|[^'\\])*'"), _fmt(c["st"])))
        self._rules.append((QRegularExpression(r"//[^\n]*"), _fmt(c["cm"], italic=True)))
        self._comment_fmt = _fmt(c["cm"], italic=True)
        self._cstart = QRegularExpression(r"/\*")
        self._cend = QRegularExpression(r"\*/")
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        for rx, fmt in self._rules:
            it = rx.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)
        # คอมเมนต์หลายบรรทัด /* ... */
        self.setCurrentBlockState(0)
        start = 0
        if self.previousBlockState() != 1:
            m = self._cstart.match(text)
            start = m.capturedStart() if m.hasMatch() else -1
        while start >= 0:
            m = self._cend.match(text, start)
            if m.hasMatch():
                length = m.capturedEnd() - start
                self.setFormat(start, length, self._comment_fmt)
                nxt = self._cstart.match(text, start + length)
                start = nxt.capturedStart() if nxt.hasMatch() else -1
            else:
                self.setCurrentBlockState(1)
                self.setFormat(start, len(text) - start, self._comment_fmt)
                break


class _LineNumberArea(QWidget):
    def __init__(self, editor: "CodeEditor"):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self.editor.line_number_width(), 0)

    def paintEvent(self, event) -> None:
        self.editor.paint_line_numbers(event)


class CodeEditor(QPlainTextEdit):
    PAIRS = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'"}

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.dark = False
        self.setFont(code_font(13))
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.setAcceptDrops(True)
        self._error_lines: dict[int, str] = {}   # เลขบรรทัด → "error"/"warning"
        self._debug_line: int | None = None      # บรรทัด (เริ่มที่ 1) ที่ดีบักเกอร์หยุดอยู่
        self._area = _LineNumberArea(self)
        self.highlighter = CppHighlighter(self.document())
        self.blockCountChanged.connect(self._update_margin)
        self.updateRequest.connect(self._update_area)
        self.cursorPositionChanged.connect(self._refresh_extra)
        self._update_margin()
        self._refresh_extra()

    # ---------- ตั้งค่า ----------
    def set_font_size(self, size: int) -> None:
        self.setFont(code_font(max(8, min(40, size))))
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self._update_margin()

    def font_size(self) -> int:
        return self.font().pointSize()

    def set_dark(self, dark: bool) -> None:
        self.dark = dark
        self.highlighter.set_theme(dark)
        self._refresh_extra()
        self._area.update()

    def set_diagnostics(self, lines: dict[int, str]) -> None:
        self._error_lines = dict(lines)
        self._refresh_extra()
        self._area.update()

    def clear_diagnostics(self) -> None:
        self.set_diagnostics({})

    # ---------- ตัวช่วยมองเห็นการทำงาน (ดีบัก) ----------
    @property
    def debug_line(self) -> int | None:
        return self._debug_line

    def set_debug_line(self, line: int | None) -> None:
        self._debug_line = line
        if line is not None:
            block = self.document().findBlockByNumber(max(0, line - 1))
            if block.isValid():
                self.setTextCursor(QTextCursor(block))
                self.centerCursor()
        self._refresh_extra()
        self._area.update()

    def set_debug_mode(self, on: bool) -> None:
        self.setReadOnly(on)
        if not on:
            self.set_debug_line(None)

    def goto_line(self, line: int) -> None:
        block = self.document().findBlockByNumber(max(0, line - 1))
        if block.isValid():
            cur = QTextCursor(block)
            self.setTextCursor(cur)
            self.centerCursor()
            self.setFocus()

    # ---------- เลขบรรทัด ----------
    def line_number_width(self) -> int:
        digits = max(2, len(str(self.blockCount())))
        return 26 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_margin(self, *_):
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def _update_area(self, rect, dy):
        if dy:
            self._area.scroll(0, dy)
        else:
            self._area.update(0, rect.y(), self._area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_margin()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        cr = self.contentsRect()
        self._area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_width(), cr.height()))

    def paint_line_numbers(self, event) -> None:
        c = theme.palette(self.dark)
        p = QPainter(self._area)
        p.fillRect(event.rect(), QColor(c["bg"]))
        block = self.firstVisibleBlock()
        num = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        cur = self.textCursor().blockNumber()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                kind = self._error_lines.get(num + 1)
                if num + 1 == self._debug_line:
                    p.setPen(QColor(c["accent"]))
                    p.drawText(2, top, 14, self.fontMetrics().height(), Qt.AlignCenter, "▶")
                elif kind == "error":
                    p.setPen(QColor(c["danger"]))
                    p.drawText(2, top, 14, self.fontMetrics().height(), Qt.AlignCenter, "●")
                elif kind == "warning":
                    p.setPen(QColor(c["warn"]))
                    p.drawText(2, top, 14, self.fontMetrics().height(), Qt.AlignCenter, "●")
                active = num == cur
                p.setPen(QColor(c["text"] if active else c["gutter_text"]))
                p.drawText(0, top, self._area.width() - 12, self.fontMetrics().height(),
                           Qt.AlignRight, str(num + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            num += 1

    # ---------- ไฮไลต์บรรทัดปัจจุบัน + บรรทัดที่ผิด ----------
    def _refresh_extra(self) -> None:
        extras: list[QTextEdit.ExtraSelection] = []
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(QColor(theme.palette(self.dark)["line_hl"]))
        sel.format.setProperty(QTextFormat.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        extras.append(sel)
        for line, kind in self._error_lines.items():
            block = self.document().findBlockByNumber(line - 1)
            if not block.isValid():
                continue
            s = QTextEdit.ExtraSelection()
            if kind == "error":
                s.format.setBackground(QColor(248, 81, 73, 60))
            else:
                s.format.setBackground(QColor(210, 153, 34, 50))
            s.format.setProperty(QTextFormat.FullWidthSelection, True)
            s.cursor = QTextCursor(block)
            extras.append(s)
        if self._debug_line is not None:
            block = self.document().findBlockByNumber(self._debug_line - 1)
            if block.isValid():
                s = QTextEdit.ExtraSelection()
                s.format.setBackground(QColor(theme.palette(self.dark)["debug_line"]))
                s.format.setProperty(QTextFormat.FullWidthSelection, True)
                s.cursor = QTextCursor(block)
                extras.append(s)
        self.setExtraSelections(extras)

    # ---------- การพิมพ์ ----------
    def keyPressEvent(self, e) -> None:
        key, text = e.key(), e.text()
        cur = self.textCursor()
        mods = e.modifiers()

        if mods & Qt.ControlModifier and key in (Qt.Key_Plus, Qt.Key_Equal):
            self.set_font_size(self.font_size() + 1)
            return
        if mods & Qt.ControlModifier and key == Qt.Key_Minus:
            self.set_font_size(self.font_size() - 1)
            return

        if key == Qt.Key_Tab and not cur.hasSelection():
            cur.insertText("    ")
            return
        if key == Qt.Key_Backtab or (key == Qt.Key_Tab and cur.hasSelection()):
            self._indent_selection(dedent=(key == Qt.Key_Backtab))
            return

        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._smart_newline()
            return

        # ปิดวงเล็บ/เครื่องหมายคำพูดอัตโนมัติ (เฉพาะอักขระ ASCII จึงไม่กระทบการพิมพ์ภาษาไทย)
        if text in self.PAIRS and not (mods & Qt.ControlModifier):
            closing = self.PAIRS[text]
            if cur.hasSelection():
                cur.insertText(text + cur.selectedText() + closing)
                return
            nxt = self._char_after(cur)
            if text in "\"'" and nxt == text:
                cur.movePosition(QTextCursor.Right)
                self.setTextCursor(cur)
                return
            if text in "\"'" and self._char_before(cur).isalnum():
                super().keyPressEvent(e)
                return
            cur.insertText(text + closing)
            cur.movePosition(QTextCursor.Left)
            self.setTextCursor(cur)
            return
        if text in (")", "]", "}") and self._char_after(cur) == text:
            cur.movePosition(QTextCursor.Right)
            self.setTextCursor(cur)
            return
        if key == Qt.Key_Backspace and not cur.hasSelection():
            b, a = self._char_before(cur), self._char_after(cur)
            if b in self.PAIRS and self.PAIRS[b] == a:
                cur.deleteChar()
                cur.deletePreviousChar()
                return
        super().keyPressEvent(e)

    def _char_after(self, cur: QTextCursor) -> str:
        pos = cur.position()
        doc = self.document()
        return doc.characterAt(pos) if pos < doc.characterCount() - 1 else ""

    def _char_before(self, cur: QTextCursor) -> str:
        pos = cur.position()
        return self.document().characterAt(pos - 1) if pos > 0 else ""

    def _smart_newline(self) -> None:
        cur = self.textCursor()
        line = cur.block().text()
        before = line[: cur.positionInBlock()]
        indent = re.match(r"\s*", line).group(0)
        stripped = before.rstrip()
        extra = "    " if stripped.endswith("{") else ""
        between = stripped.endswith("{") and self._char_after(cur) == "}"
        cur.beginEditBlock()
        cur.insertText("\n" + indent + extra)
        if between:
            pos = cur.position()
            cur.insertText("\n" + indent)
            cur.setPosition(pos)
        cur.endEditBlock()
        self.setTextCursor(cur)

    def _indent_selection(self, dedent: bool) -> None:
        cur = self.textCursor()
        start, end = cur.selectionStart(), cur.selectionEnd()
        doc = self.document()
        first = doc.findBlock(start).blockNumber()
        last = doc.findBlock(end).blockNumber()
        if end > start and doc.findBlock(end).position() == end:
            last -= 1
        cur.beginEditBlock()
        for n in range(first, max(first, last) + 1):
            blk = doc.findBlockByNumber(n)
            c = QTextCursor(blk)
            if dedent:
                t = blk.text()
                k = min(4, len(t) - len(t.lstrip(" ")))
                for _ in range(k):
                    c.deleteChar()
            else:
                c.insertText("    ")
        cur.endEditBlock()

    # ---------- วางข้อความ ----------
    def insertFromMimeData(self, source) -> None:
        # แปลงเครื่องหมายคำพูดโค้งที่ติดมาจาก Word/เว็บ ให้เป็น ASCII (ต้นเหตุ error ที่พบบ่อยของนักเรียน)
        if source.hasText():
            t = (source.text()
                 .replace("“", '"').replace("”", '"')
                 .replace("‘", "'").replace("’", "'")
                 .replace(" ", " ").replace("​", ""))
            self.insertPlainText(t)
        else:
            super().insertFromMimeData(source)
