"""อ่านผลลัพธ์ของ GDB/MI (ข้อความที่ gdb ส่งกลับทีละบรรทัดเมื่อรันด้วย --interpreter=mi3)

ตัวอย่างบรรทัด: ``12^done,value="5"`` / ``*stopped,reason="end-stepping-range",frame={...}``
รายการแบบ ``[frame={..},frame={..}]`` ถูกแปลงเป็น list ของค่าอย่างเดียว (ทิ้งชื่อ key)
ฟังก์ชันนี้ไม่ throw: บรรทัดที่อ่านไม่ออกจะได้ ``Record(kind="unknown")``
"""
from __future__ import annotations

from dataclasses import dataclass, field

_PREFIX_KIND = {"^": "result", "*": "exec", "=": "notify", "~": "console", "@": "target", "&": "log"}
_ESCAPES = {"n": b"\n", "t": b"\t", "r": b"\r", '"': b'"', "\\": b"\\", "a": b"\a", "b": b"\b",
            "f": b"\f", "v": b"\v", "e": b"\x1b"}


@dataclass
class Record:
    kind: str                       # result|exec|notify|console|target|log|prompt|unknown
    cls: str = ""                   # done / error / running / stopped ...
    data: dict = field(default_factory=dict)
    token: int | None = None
    text: str = ""                  # ข้อความของ stream record หรือบรรทัดดิบที่อ่านไม่ออก


class _Reader:
    def __init__(self, s: str):
        self.s = s
        self.i = 0

    def peek(self) -> str:
        return self.s[self.i] if self.i < len(self.s) else ""

    def eat(self, ch: str) -> bool:
        if self.peek() == ch:
            self.i += 1
            return True
        return False

    def cstring(self) -> str:
        """อ่านสตริงในเครื่องหมายคำพูด (ต้องยืนอยู่ที่ตัว ") — octal escape คือไบต์ UTF-8"""
        self.i += 1
        buf = bytearray()
        s = self.s
        while self.i < len(s):
            c = s[self.i]
            if c == '"':
                self.i += 1
                break
            if c == "\\" and self.i + 1 < len(s):
                n = s[self.i + 1]
                if n in "01234567":
                    j = self.i + 1
                    while j < len(s) and j < self.i + 4 and s[j] in "01234567":
                        j += 1
                    buf.append(int(s[self.i + 1:j], 8) & 0xFF)
                    self.i = j
                    continue
                buf += _ESCAPES.get(n, n.encode("utf-8"))
                self.i += 2
                continue
            buf += c.encode("utf-8")
            self.i += 1
        return buf.decode("utf-8", errors="replace")

    def name(self) -> str:
        j = self.i
        while j < len(self.s) and self.s[j] not in "=,]}":
            j += 1
        out = self.s[self.i:j]
        self.i = j
        return out

    def value(self):
        c = self.peek()
        if c == '"':
            return self.cstring()
        if c == "{":
            self.i += 1
            d = self.results("}")
            self.eat("}")
            return d
        if c == "[":
            self.i += 1
            items = []
            while self.i < len(self.s) and self.peek() != "]":
                if self.peek() in '"{[':
                    items.append(self.value())
                else:                       # key=value ในลิสต์ → เก็บเฉพาะค่า
                    self.name()
                    self.eat("=")
                    items.append(self.value())
                self.eat(",")
            self.eat("]")
            return items
        raise ValueError("bad value")

    def results(self, end: str = "") -> dict:
        out: dict = {}
        while self.i < len(self.s) and self.peek() != end:
            key = self.name()
            if not self.eat("="):
                raise ValueError("expected =")
            out[key] = self.value()
            self.eat(",")
        return out


def parse_record(line: str) -> Record:
    raw = line.rstrip("\r\n")
    if raw.strip() == "(gdb)":
        return Record("prompt")
    try:
        i = 0
        while i < len(raw) and raw[i].isdigit():
            i += 1
        token = int(raw[:i]) if i else None
        kind = _PREFIX_KIND.get(raw[i:i + 1])
        if kind is None:
            return Record("unknown", text=raw)
        r = _Reader(raw[i + 1:])
        if kind in ("console", "target", "log"):
            return Record(kind, text=r.cstring() if r.peek() == '"' else raw[i + 1:], token=token)
        cls = r.name()
        data: dict = {}
        if r.eat(","):
            data = r.results()
        return Record(kind, cls, data, token)
    except (ValueError, IndexError):
        return Record("unknown", text=raw)
