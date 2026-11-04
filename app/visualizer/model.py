"""โมเดลข้อมูลของ Visualizer: Snapshot ของโปรแกรม ณ จุดที่หยุด (เฟรม + ตัวแปร) สร้างจากผลลัพธ์ของ gdb

ไม่พึ่ง Qt หรือ gdb — รับแค่ dict/ข้อความที่ผ่าน gdbmi มาแล้ว จึงทดสอบได้ตรงๆ
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_ELEMENTS = 50          # แสดง array สูงสุดกี่ช่อง ที่เหลือสรุปเป็น "… อีก N ช่อง"
UNREADABLE_POINTEE = "อ่านไม่ได้"   # Var.pointee เมื่ออ่านค่าที่ pointer ชี้อยู่ไม่ได้
STD_VALUE_LIMIT = 80       # ชนิด std:: แสดงเป็นข้อความดิบ ตัดที่ความยาวนี้

_REPEATS = re.compile(r"^(.*) <repeats (\d+) times>$", re.S)
_HEX_PREFIX = re.compile(r"^(0x[0-9a-fA-F]+)")
_OCTAL_RUN = re.compile(r"(?:\\[0-7]{3})+")


@dataclass(frozen=True)
class PointsTo:
    """pointer ชี้ไปที่ตัวแปร var_name ในเฟรม frame_level (index = ช่องของ array ถ้าชี้เข้าไปในช่อง)"""
    frame_level: int
    var_name: str
    index: int | None = None


@dataclass
class Var:
    name: str
    type: str
    value: str
    kind: str = "scalar"                 # scalar | array | pointer | struct
    address: int | None = None
    size: int | None = None
    children: list["Var"] = field(default_factory=list)
    target: int | None = None            # pointer: ที่อยู่ที่เก็บอยู่ (0 = nullptr)
    changed: bool = False
    pointee: str | None = None
    unreadable: bool = False
    more: int = 0                        # จำนวนช่องที่ไม่ได้แสดงเพราะเกิน MAX_ELEMENTS
    points_to: PointsTo | None = None    # pointer: ตัวแปรที่ชี้ไปหา (None = nullptr / heap / ไม่รู้)


@dataclass
class Frame:
    level: int
    func: str
    file: str
    line: int
    args: list[Var] = field(default_factory=list)
    locals: list[Var] = field(default_factory=list)


@dataclass
class Snapshot:
    frames: list[Frame]                  # frames[0] = เฟรมในสุด (ที่กำลังทำงาน)
    exited: bool = False
    exit_code: int | None = None
    signal: str | None = None

    @property
    def line(self) -> int:
        return self.frames[0].line if self.frames else 0

    @property
    def func(self) -> str:
        return self.frames[0].func if self.frames else ""

    @property
    def file(self) -> str:
        return self.frames[0].file if self.frames else ""


# ---------- แยกข้อความค่าของ gdb ----------
def _split_top(text: str) -> list[str]:
    """แยกด้วยเครื่องหมายจุลภาคระดับนอกสุด (ไม่นับที่อยู่ใน {} หรือสตริง/อักขระ)"""
    parts: list[str] = []
    depth = 0
    quote = ""
    start = 0
    i = 0
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\":
                i += 1
            elif c == quote:
                quote = ""
        elif c in "\"'":
            quote = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == "," and depth == 0:
            parts.append(text[start:i].strip())
            start = i + 1
        i += 1
    last = text[start:].strip()
    if last or parts:
        parts.append(last)
    return parts


def _braced_inner(text: str) -> str | None:
    t = text.strip()
    if t.startswith("{") and t.endswith("}"):
        return t[1:-1]
    return None


def _decode_octal(text: str) -> str:
    """gdb พิมพ์ไบต์ที่ไม่ใช่ ASCII ในสตริงเป็น escape แบบ octal (ตัวอย่าง: แบ็กสแลชตามด้วยเลข 3 หลัก) — ถอดเป็น UTF-8 """
    def one(m: re.Match) -> str:
        raw = bytes(int(part, 8) for part in m.group(0).split("\\")[1:])
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return m.group(0)
    return _OCTAL_RUN.sub(one, text)


_SIGNAL_CODES = {"SIGSEGV": 11, "SIGFPE": 8, "SIGABRT": 6}


def describe_signal(name: str | None) -> str | None:
    """คำอธิบายภาษาไทยของ signal ที่ทำให้โปรแกรมหยุด (None ถ้าไม่รู้จัก)"""
    code = _SIGNAL_CODES.get(name or "")
    if code is None:
        return None
    from ..compiler import describe_exit
    return describe_exit(code, True)


def classify(type_str: str, value: str) -> str:
    t = type_str.strip()
    if t.startswith("std::"):
        return "scalar"
    if t.endswith("*"):
        return "pointer"
    braced = value.strip().startswith("{")
    if "[" in t and braced:
        return "array"
    if braced:
        if not t:                        # ไม่รู้ชนิด (สมาชิก struct): ดูจากรูปแบบ "ชื่อ = ค่า"
            inner = _braced_inner(value) or ""
            first = _split_top(inner)[:1]
            return "struct" if first and re.match(r"^[\w<>:~]+ = ", first[0]) else "array"
        return "struct"
    return "scalar"


def _make(name: str, type_str: str, value: str) -> Var:
    value = _decode_octal(value)
    kind = classify(type_str, value)
    v = Var(name, type_str, value, kind)
    if kind == "pointer":
        m = _HEX_PREFIX.match(value.strip())
        if m:
            v.target = int(m.group(1), 16)
    elif kind in ("array", "struct"):
        v.children, v.more = parse_value_text(type_str, value) if type_str else _parse_untyped(value, kind)
    elif type_str.startswith("std::") and len(value) > STD_VALUE_LIMIT:
        v.value = value[:STD_VALUE_LIMIT] + "…"
    if value.startswith(("<error", "<optimized out>", "<unavailable")) or "<error:" in value:
        v.unreadable = True
    return v


def _parse_untyped(value: str, kind: str) -> tuple[list[Var], int]:
    return _children("", value, as_array=(kind == "array"))


def parse_value_text(type_str: str, text: str) -> tuple[list[Var], int]:
    """แตกค่าแบบ ``{1, 2, 3}`` / ``{x = 1, y = 2}`` เป็นตัวแปรลูก คืน (ลูก, จำนวนช่องที่ถูกตัดทิ้ง)"""
    return _children(type_str, text, as_array="[" in type_str)


def _element_type(type_str: str) -> str:
    """``int [2][3]`` → ``int [3]``; ``int [4]`` → ``int``"""
    if not type_str:
        return ""
    t = re.sub(r"\[\d*\]", "", type_str, count=1)
    return re.sub(r"\s*\[", " [", t).strip()


def _children(type_str: str, text: str, as_array: bool) -> tuple[list[Var], int]:
    inner = _braced_inner(text)
    if inner is None:
        return [], 0
    items = _split_top(inner)
    if not as_array:
        out: list[Var] = []
        for item in items:
            name, sep, val = item.partition(" = ")
            if sep:
                out.append(_make(name.strip(), "", val.strip()))
        return out, 0
    elem_type = _element_type(type_str)
    kids: list[Var] = []
    total = 0
    for item in items:
        if item == "...":                # gdb ตัดรายการยาว (print elements) — ไม่นับ
            continue
        m = _REPEATS.match(item)
        val, count = (m.group(1), int(m.group(2))) if m else (item, 1)
        for _ in range(min(count, MAX_ELEMENTS - len(kids)) if len(kids) < MAX_ELEMENTS else 0):
            kids.append(_make(f"[{len(kids)}]", elem_type, val))
        total += count
    return kids, max(0, total - len(kids))


def build_var(mi: dict) -> Var:
    return _make(mi.get("name", ""), mi.get("type", ""), mi.get("value", ""))


def build_frame(frame: dict, variables: list[dict]) -> Frame:
    f = Frame(
        level=int(frame.get("level", 0)),
        func=frame.get("func", ""),
        file=frame.get("file", frame.get("fullname", "")),
        line=int(frame.get("line", 0) or 0),
    )
    for mi in variables:
        (f.args if mi.get("arg") == "1" else f.locals).append(build_var(mi))
    return f


# ---------- ตัวแปรที่เปลี่ยนค่า ----------
def _mark_var(prev: Var | None, cur: Var) -> bool:
    if prev is None:
        return False
    child_changed = False
    for i, c in enumerate(cur.children):
        p = prev.children[i] if i < len(prev.children) else None
        child_changed |= _mark_var(p, c)
    cur.changed = cur.value != prev.value or child_changed
    return cur.changed


def mark_changes(prev: Snapshot | None, cur: Snapshot) -> None:
    """ตั้ง Var.changed ให้ตัวแปรที่ค่าต่างจาก snapshot ก่อนหน้า (จับคู่เฟรมนับจากล่างสุด + ชื่อฟังก์ชัน)"""
    if prev is None:
        return

    def key(snap: Snapshot, i: int) -> tuple[int, str]:
        return len(snap.frames) - 1 - i, snap.frames[i].func

    old = {key(prev, i): {v.name: v for v in prev.frames[i].args + prev.frames[i].locals}
           for i in range(len(prev.frames))}
    for i, fr in enumerate(cur.frames):
        before = old.get(key(cur, i))
        if before is None:
            continue
        for v in fr.args + fr.locals:
            _mark_var(before.get(v.name), v)


# ---------- pointer ชี้ไปที่ไหน ----------
def _walk(var: Var):
    yield var
    for c in var.children:
        yield from _walk(c)


def _locate(snap: Snapshot, target: int) -> PointsTo | None:
    for fr in snap.frames:
        for v in fr.args + fr.locals:
            if v.address is None or v.size is None or not v.address <= target < v.address + max(v.size, 1):
                continue
            if v.kind == "array" and v.children:
                stride = max(1, v.size // (len(v.children) + v.more))
                idx = (target - v.address) // stride
                return PointsTo(fr.level, v.name, idx if idx < len(v.children) else None)
            return PointsTo(fr.level, v.name, None)
    return None


def resolve_pointer_targets(snap: Snapshot) -> None:
    """ตั้ง Var.points_to ให้ pointer ทุกตัว (รวมที่อยู่ในสมาชิก struct / ช่อง array) ที่ชี้เข้าตัวแปรที่เรารู้ที่อยู่"""
    for fr in snap.frames:
        for top in fr.args + fr.locals:
            for v in _walk(top):
                if v.kind == "pointer" and v.target:
                    v.points_to = _locate(snap, v.target)
