"""ไอคอน SVG ในโค้ด เปลี่ยนสีตามธีมได้ (ไม่ต้องมีไฟล์รูปเพิ่ม)"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_STROKE = 'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'

_BODIES = {
    "explorer": f'<g {_STROKE}><path d="M5 3h9l5 5v13H5z"/><path d="M14 3v5h5"/></g>',
    "run": '<path d="M7 4l13 8-13 8z" fill="currentColor"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="1.5" fill="currentColor"/>',
    "save": f'<g {_STROKE}><path d="M5 3h12l3 3v15H5z"/><path d="M8 3v6h8V3M8 21v-7h8v7"/></g>',
    "print": f'<g {_STROKE}><path d="M7 9V3h10v6M7 17H4v-7h16v7h-3"/><rect x="7" y="14" width="10" height="7"/></g>',
    "folder": f'<g {_STROKE}><path d="M3 6h7l2 2h9v11H3z"/></g>',
    "file": f'<g {_STROKE}><path d="M6 3h8l4 4v14H6z"/></g>',
    "close": f'<g {_STROKE}><path d="M6 6l12 12M18 6L6 18"/></g>',
    "example": f'<g {_STROKE}><path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.6.6 1 1.4 1 2.5h6c0-1.1.4-1.9 1-2.5A6 6 0 0 0 12 3z"/></g>',
}


def _render(name: str, color: str, size: int) -> QImage:
    body = _BODIES[name]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" color="{color}">'
           f'{body}</svg>')
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    painter = QPainter(img)
    renderer.render(painter)
    painter.end()
    return img


def icon(name: str, color: str, size: int = 20) -> QIcon:
    return QIcon(QPixmap.fromImage(_render(name, color, size)))


def close_icon_files(normal: str, hover: str) -> tuple[str, str]:
    """เขียนไอคอนปุ่มปิดแท็บเป็นไฟล์ PNG (QSS ใช้ได้เฉพาะ url ของไฟล์) แล้วคืนพาธแบบ / ให้ใส่ใน url()"""
    from .compiler import work_dir
    d = Path(work_dir()) / "icons"
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for tag, color in (("normal", normal), ("hover", hover)):
        f = d / f"tab_close_{tag}_{color.lstrip('#')}.png"
        if not f.exists():
            _render("close", color, 16).save(str(f), "PNG")
        out.append(f.as_posix())
    return out[0], out[1]
