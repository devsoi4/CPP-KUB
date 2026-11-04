"""ภาพหน่วยความจำ: ตัวแปรเป็นกล่อง, array เป็นช่องเรียงกันพร้อมเลข index, struct เป็นกลุ่มกล่อง,
pointer เป็นลูกศรชี้ไปที่ตัวแปร (หรือกล่อง "heap" ถ้าชี้ออกนอกตัวแปรที่รู้จัก)

วาดทุกเฟรมของ call stack เรียงจากเฟรมในสุดลงมา เพื่อให้ลูกศรข้ามเฟรมได้
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from .. import theme
from ..editor import code_font
from .model import UNREADABLE_POINTEE, Snapshot, Var

BOX_W, BOX_H = 64.0, 30.0
GAP = 8.0
CAPTION_H = 16.0
MARGIN = 12.0
HEAP_GAP = 90.0
UNREADABLE_TEXT = "อ่านไม่ได้"


def _short(text: str, limit: int = 9) -> str:
    return text if len(text) <= limit else text[:limit - 1] + "…"


class MemoryView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._dark = False
        self._snap: Snapshot | None = None
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._font = code_font(10)
        self._reset_counts()

    # ---------- สาธารณะ ----------
    @property
    def box_count(self) -> int:
        return self._boxes

    @property
    def arrow_count(self) -> int:
        return self._arrows

    def clear(self) -> None:
        self._snap = None
        self._scene.clear()
        self._reset_counts()

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        if self._snap is not None:
            self.show_snapshot(self._snap)

    def show_snapshot(self, snap: Snapshot) -> None:
        self._snap = snap
        self._scene.clear()
        self._reset_counts()
        if snap.exited or not snap.frames:
            return
        self._pal = theme.palette(self._dark)
        self.setBackgroundBrush(QBrush(QColor(self._pal["bg"])))
        y = MARGIN
        max_x = MARGIN
        pending: list[tuple[Var, QRectF, int]] = []          # (pointer, กล่องของมัน, ลำดับลูกศร)
        for fr in snap.frames:
            title = self._scene.addSimpleText(f"{fr.func}()", self._font)
            title.setBrush(QBrush(QColor(self._pal["accent"])))
            title.setPos(MARGIN, y)
            y += CAPTION_H + 4
            for var in fr.args + fr.locals:
                w, h = self._draw(var, MARGIN, y, fr.level, pending, top=True)
                max_x = max(max_x, MARGIN + w)
                y += h + GAP
            y += GAP
        self._draw_arrows(pending, max_x, y)
        rect = self._scene.itemsBoundingRect().adjusted(-MARGIN, -MARGIN, MARGIN, MARGIN)
        self._scene.setSceneRect(rect)

    # ---------- ภายใน ----------
    def _reset_counts(self) -> None:
        self._boxes = 0
        self._arrows = 0
        self._rects: dict[tuple[int, str, int | None], QRectF] = {}

    def _pen(self, key: str, width: float = 1.2) -> QPen:
        return QPen(QColor(self._pal[key]), width)

    def _box(self, x: float, y: float, text: str, *, changed: bool = False, danger: bool = False,
             w: float = BOX_W) -> QRectF:
        rect = QRectF(x, y, w, BOX_H)
        fill = self._pal["changed"] if changed else self._pal["panel"]
        self._scene.addRect(rect, self._pen("danger" if danger else "border"), QBrush(QColor(fill)))
        label = self._scene.addSimpleText(_short(text), self._font)
        label.setBrush(QBrush(QColor(self._pal["danger" if danger else "text"])))
        br = label.boundingRect()
        label.setPos(x + (w - br.width()) / 2, y + (BOX_H - br.height()) / 2)
        self._boxes += 1
        return rect

    def _caption(self, x: float, y: float, text: str) -> None:
        t = self._scene.addSimpleText(_short(text, 14), self._font)
        t.setBrush(QBrush(QColor(self._pal["muted"])))
        f = QFont(self._font)
        f.setPointSize(max(7, f.pointSize() - 2))
        t.setFont(f)
        t.setPos(x, y)

    def _cell_text(self, var: Var) -> str:
        if var.unreadable:
            return UNREADABLE_TEXT
        if var.kind == "pointer":
            return "nullptr" if var.target == 0 else _short(hex(var.target) if var.target else var.value)
        return var.value

    def _draw(self, var: Var, x: float, y: float, level: int, pending, *, top: bool = False) -> tuple[float, float]:
        """วาดตัวแปรหนึ่งตัวที่ (x, y) คืน (กว้าง, สูง)"""
        self._caption(x, y, var.name)
        y0 = y + CAPTION_H
        if var.kind == "array":
            return self._draw_array(var, x, y0, level, pending, top)
        if var.kind == "struct":
            cx = x
            for m in var.children:
                w, _h = self._draw(m, cx, y0, level, pending)
                cx += w + GAP
            row_h = max((self._measure(m) for m in var.children), default=BOX_H)
            rect = QRectF(x - 3, y0 - 3, max(cx - x - GAP, BOX_W) + 6, row_h + 6)
            if top:
                self._rects[(level, var.name, None)] = rect
            return rect.width(), CAPTION_H + row_h + 6
        rect = self._box(x, y0, self._cell_text(var), changed=var.changed, danger=var.unreadable)
        if top:
            self._rects[(level, var.name, None)] = rect
        if var.kind == "pointer":
            pending.append((var, rect, level))
        return BOX_W, CAPTION_H + BOX_H

    def _measure(self, var: Var) -> float:
        """ความสูงที่ตัวแปรจะใช้ (ไว้จัดแถวของสมาชิก struct)"""
        if var.kind == "array":
            if var.children and var.children[0].kind in ("array", "struct"):
                return CAPTION_H + sum(self._measure(c) + GAP for c in var.children)
            return CAPTION_H + BOX_H + CAPTION_H
        if var.kind == "struct":
            return CAPTION_H + max((self._measure(c) for c in var.children), default=BOX_H) + 6
        return CAPTION_H + BOX_H

    def _draw_array(self, var: Var, x: float, y0: float, level: int, pending, top: bool) -> tuple[float, float]:
        if var.children and var.children[0].kind in ("array", "struct"):   # array ของ array/struct: ซ้อนเป็นแถว
            cy, width = y0, BOX_W
            for c in var.children:
                w, h = self._draw(c, x + 10, cy, level, pending)
                width = max(width, w + 10)
                cy += h + GAP
            if top:
                self._rects[(level, var.name, None)] = QRectF(x, y0, width, cy - y0)
            return width, CAPTION_H + cy - y0
        cx = x
        for i, c in enumerate(var.children):
            rect = self._box(cx, y0, self._cell_text(c), changed=c.changed, danger=c.unreadable)
            self._caption(cx + 2, y0 + BOX_H, f"[{i}]")
            if top:
                self._rects[(level, var.name, i)] = rect
            if c.kind == "pointer":
                pending.append((c, rect, level))
            cx += BOX_W + 2
        if var.more:
            self._box(cx, y0, f"… +{var.more}", w=BOX_W)
            cx += BOX_W + 2
        if top:
            self._rects[(level, var.name, None)] = QRectF(x, y0, max(cx - x, BOX_W), BOX_H)
        return max(cx - x, BOX_W), CAPTION_H + BOX_H + CAPTION_H

    def _draw_arrows(self, pending, max_x: float, bottom: float) -> None:
        heap_x = max_x + HEAP_GAP
        heap_y = MARGIN
        lane = 0
        for var, src, _level in pending:
            if var.unreadable or not var.target:
                continue
            target = None
            if var.points_to is not None:
                p = var.points_to
                target = self._rects.get((p.frame_level, p.var_name, p.index)) \
                    or self._rects.get((p.frame_level, p.var_name, None))
            if target is None:                                   # ชี้ออกนอก → กล่อง heap
                text = var.pointee if var.pointee is not None else "?"
                self._caption(heap_x, heap_y, f"heap {hex(var.target)}")
                target = self._box(heap_x, heap_y + CAPTION_H, text,
                                   danger=(var.pointee == UNREADABLE_POINTEE))
                heap_y += CAPTION_H + BOX_H + GAP
            self._arrow(src, target, lane)
            lane += 1

    def _arrow(self, src: QRectF, dst: QRectF, lane: int) -> None:
        start = QPointF(src.right(), src.center().y())
        end = QPointF(dst.right() if dst.left() < src.left() else dst.left(), dst.center().y())
        reach = 24.0 + 10.0 * (lane % 6)
        c1 = QPointF(start.x() + reach, start.y())
        c2 = QPointF(end.x() + (reach if end.x() >= dst.right() - 0.1 else -reach), end.y())
        path = QPainterPath(start)
        path.cubicTo(c1, c2, end)
        item = self._scene.addPath(path, self._pen("accent", 1.6))
        item.setZValue(2)
        direction = -1.0 if c2.x() > end.x() else 1.0            # ปลายลูกศรหันเข้าหากล่องเป้าหมาย
        head = QPolygonF([end, QPointF(end.x() + 8 * -direction, end.y() - 4),
                          QPointF(end.x() + 8 * -direction, end.y() + 4)])
        self._scene.addPolygon(head, self._pen("accent", 1.0), QBrush(QColor(self._pal["accent"]))).setZValue(2)
        self._arrows += 1
