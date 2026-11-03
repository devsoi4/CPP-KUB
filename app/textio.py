"""อ่าน/เขียนไฟล์ซอร์สที่มีภาษาไทย (UTF-8 เป็นหลัก รองรับไฟล์เก่าที่เซฟเป็น TIS-620/cp874)"""
from __future__ import annotations

from pathlib import Path


def read_source(path: str | Path) -> tuple[str, str]:
    """คืน (ข้อความ, ชื่อ encoding ที่ใช้อ่าน)"""
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", errors="replace").replace("\r\n", "\n"), "utf-8-sig"
    for enc in ("utf-8", "cp874"):   # cp874 = Windows Thai (เหมือน TIS-620)
        try:
            return raw.decode(enc).replace("\r\n", "\n"), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1").replace("\r\n", "\n"), "latin-1"


def write_source(path: str | Path, text: str) -> None:
    """เขียนเป็น UTF-8 (ไม่มี BOM) ขึ้นบรรทัดใหม่แบบ \\n เสมอ"""
    Path(path).write_text(text, encoding="utf-8", newline="\n")
