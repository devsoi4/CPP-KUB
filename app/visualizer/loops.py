"""หา loop (for/while/do) ในซอร์สของนักเรียน และนับว่ากำลังวนรอบที่เท่าไหร่ขณะเดินดีบัก

Python ล้วน: รับซอร์สกับ (ความลึกของ call stack, เลขบรรทัด) ในแต่ละก้าว ไม่พึ่ง Qt หรือ gdb
นับรอบด้วยจำนวนครั้งที่เดินกลับมาถึงบรรทัดหัว loop (for/while: ทุกครั้งที่ตรวจเงื่อนไข,
do-while: ทุกครั้งที่ถึงเงื่อนไข while ท้าย loop)
"""
from __future__ import annotations

import bisect
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class LoopInfo:
    line: int                # บรรทัดหัว loop (เริ่มที่ 1)
    end_line: int            # บรรทัดสุดท้ายของ loop
    kind: str                # for | while | do
    var: str | None          # ตัวแปรนับรอบ (เฉพาะ for)


@dataclass(frozen=True)
class LoopStatus:
    line: int
    kind: str
    var: str | None
    iteration: int


_FOR_INIT = re.compile(r"for\s*\(\s*(?:[A-Za-z_][\w:<>]*[\s*&]+)*?([A-Za-z_]\w*)\s*=")
_FOR_RANGE = re.compile(r"for\s*\([^;:)]*?([A-Za-z_]\w*)\s*:(?!:)")
_HEADER = re.compile(r"\b(for|while)\s*\(|\bdo\b")


def _mask(src: str) -> str:
    """แทนที่เนื้อใน comment / สตริง / อักขระ ด้วยช่องว่าง (คงบรรทัดและตำแหน่งเดิมไว้)"""
    out = list(src)
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                out[i] = " "
                i += 1
        elif c == "/" and i + 1 < n and src[i + 1] == "*":
            out[i] = out[i + 1] = " "
            i += 2
            while i < n and not (src[i] == "*" and i + 1 < n and src[i + 1] == "/"):
                if src[i] != "\n":
                    out[i] = " "
                i += 1
            if i < n:
                out[i] = " "
                if i + 1 < n:
                    out[i + 1] = " "
                i += 2
        elif c in "\"'":
            q = c
            i += 1
            while i < n and src[i] != q and src[i] != "\n":
                if src[i] == "\\" and i + 1 < n:
                    out[i] = " "
                    i += 1
                out[i] = " "
                i += 1
            i += 1
        else:
            i += 1
    return "".join(out)


def _match(text: str, pos: int, open_ch: str, close_ch: str) -> int:
    """ตำแหน่งของวงเล็บปิดที่คู่กับวงเล็บเปิดที่ pos (-1 ถ้าไม่พบ)"""
    depth = 0
    for i in range(pos, len(text)):
        if text[i] == open_ch:
            depth += 1
        elif text[i] == close_ch:
            depth -= 1
            if depth == 0:
                return i
    return -1


def _skip_ws(text: str, pos: int) -> int:
    while pos < len(text) and text[pos].isspace():
        pos += 1
    return pos


def find_loops(source: str) -> dict[int, LoopInfo]:
    """คืน {บรรทัดหัว loop: LoopInfo}"""
    text = _mask(source)
    starts = [0] + [m.end() for m in re.finditer("\n", text)]

    def line_of(pos: int) -> int:
        return bisect.bisect_right(starts, pos)

    loops: dict[int, LoopInfo] = {}
    tails: set[int] = set()                       # ตำแหน่ง "while" ท้าย do-while (ไม่ใช่หัว loop)
    for m in _HEADER.finditer(text):
        if m.start() in tails:
            continue
        kind = "do" if m.group(0).startswith("do") else m.group(1)
        head = line_of(m.start())
        if kind == "do":
            body = _skip_ws(text, m.end())
            if body < len(text) and text[body] == "{":
                body_end = _match(text, body, "{", "}")
            else:
                body_end = text.find(";", body)
            if body_end < 0:
                continue
            w = _skip_ws(text, body_end + 1)
            if not text.startswith("while", w):
                continue
            tails.add(w)
            paren = text.find("(", w)
            close = _match(text, paren, "(", ")") if paren >= 0 else -1
            semi = text.find(";", close) if close >= 0 else -1
            loops[head] = LoopInfo(head, line_of(semi if semi >= 0 else body_end), "do", None)
            continue
        close = _match(text, m.end() - 1, "(", ")")
        if close < 0:
            continue
        after = _skip_ws(text, close + 1)
        if after < len(text) and text[after] == "{":
            end = _match(text, after, "{", "}")
        else:
            end = text.find(";", after)
        if end < 0:
            continue
        var = None
        if kind == "for":
            header_text = text[m.start():close + 1]
            hit = _FOR_INIT.match(header_text) or _FOR_RANGE.match(header_text)
            var = hit.group(1) if hit else None
        loops[head] = LoopInfo(head, line_of(end), kind, var)
    return loops


class LoopTracker:
    """ติดตามรอบของ loop ที่กำลังทำงานอยู่ — เรียก update() ทุกครั้งที่หยุดที่บรรทัดใหม่"""

    def __init__(self, loops: dict[int, LoopInfo]):
        self.loops = loops
        self._state: dict[tuple[int, int], int] = {}      # (ความลึกเฟรม, บรรทัดหัว) → รอบ

    def reset(self) -> None:
        self._state.clear()

    def update(self, depth: int, line: int) -> list[LoopStatus]:
        for key in list(self._state):
            d, head = key
            info = self.loops[head]
            if d > depth or (d == depth and not info.line <= line <= info.end_line):
                del self._state[key]                       # ออกจาก loop หรือฟังก์ชันที่เรียกกลับไปแล้ว
        info = self.loops.get(line)
        if info is not None and info.kind != "do":
            key = (depth, line)
            self._state[key] = self._state.get(key, 0) + 1
        for head, info in self.loops.items():
            if info.kind == "do" and info.line <= line <= info.end_line:
                key = (depth, head)
                if key not in self._state:
                    self._state[key] = 1
                elif line == info.end_line:
                    self._state[key] += 1                  # ถึงเงื่อนไข while ท้าย = เริ่มรอบถัดไป
        return [LoopStatus(h, self.loops[h].kind, self.loops[h].var, it)
                for (d, h), it in sorted(self._state.items(), key=lambda kv: kv[0][1]) if d == depth]
