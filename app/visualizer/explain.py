"""คำอธิบายภาษาไทยของ "ก้าวล่าสุด" ใต้ตัวแปรในแผง Visualizer — สร้างจาก Snapshot ก่อนหน้ากับปัจจุบัน

ไม่พึ่ง Qt/gdb จึงทดสอบได้ตรงๆ ถ้ามีคำอธิบายเขียนมือของบรรทัดนั้น (annotation) จะใช้แทนข้อความอัตโนมัติ
"""
from __future__ import annotations

from .model import Frame, Snapshot


def _call_text(fr: Frame) -> str:
    return f"{fr.func}(" + ", ".join(f"{v.name}={v.value}" for v in fr.args) + ")"


def _vars(fr: Frame) -> dict[str, str]:
    return {v.name: v.value for v in fr.args + fr.locals}


def explain(prev: Snapshot | None, now: Snapshot, annotation: str | None = None) -> str:
    if now.exited:
        return "โปรแกรมทำงานจบแล้ว"
    if not now.frames:
        return ""
    returning = prev is not None and len(now.frames) < len(prev.frames)
    if annotation and not returning:     # ตอนย้อนกลับจากฟังก์ชัน คำอธิบายของบรรทัดจะผิดความหมาย ใช้ข้อความอัตโนมัติแทน
        return annotation
    top = now.frames[0]
    if prev is None or not prev.frames:
        return f"เริ่มทำงานที่ {top.func}() บรรทัด {top.line}"
    ptop = prev.frames[0]
    if len(now.frames) > len(prev.frames):
        depth = sum(1 for f in now.frames if f.func == top.func)
        text = f"เรียกฟังก์ชัน {_call_text(top)}"
        if depth > 1:
            text += f" — ฟังก์ชันเรียกตัวเอง (ซ้อนอยู่ {depth} ชั้น)"
        return text
    if len(now.frames) < len(prev.frames):
        return f"{ptop.func}() ทำงานเสร็จ กลับมาที่ {top.func}() บรรทัด {top.line}"
    if ptop.func == top.func:
        before = _vars(ptop)
        changed = [(v.name, before.get(v.name), v.value) for v in top.args + top.locals
                   if v.changed and before.get(v.name) not in (None, v.value)]
        if changed:
            return "; ".join(f"ตัวแปร {n} เปลี่ยนจาก {a} เป็น {b}" for n, a, b in changed[:3])
    return f"ทำบรรทัด {ptop.line} เสร็จ แล้วไปบรรทัด {top.line}"
