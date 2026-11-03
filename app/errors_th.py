"""แปลข้อความ error/warning ของ g++ เป็นภาษาไทยที่นักเรียนอ่านเข้าใจ"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ตัวอย่าง: main.cpp:5:10: error: expected ';' before 'return'
DIAG_RE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):(?:(?P<col>\d+):)?\s*"
    r"(?P<kind>error|warning|note|fatal error):\s*(?P<msg>.*)$"
)

# (pattern, คำอธิบายไทย) — ใช้ {1}, {2} แทนกลุ่มที่จับได้
# กฎเฉพาะต้องมาก่อนกฎกว้าง เพราะใช้กฎแรกที่ตรง
# {prev} = บรรทัดก่อนหน้า (g++ มักรายงาน ; ที่ลืมที่บรรทัดถัดไป)
RULES: list[tuple[str, str]] = [
    (r"expected ',' or ';' before (.+)|expected '(;)' before (.+)",
     "ลืมใส่เครื่องหมาย ; ท้ายคำสั่งหรือเปล่า? g++ มักชี้ที่บรรทัดถัดไป ให้ตรวจ {prev} ก่อน"),
    (r"'(cout|cin|endl|string|vector|map|set)' was not declared in this scope",
     "ไม่รู้จัก '{1}' — ลืมเขียน using namespace std; หรือลืม #include ที่เกี่ยวข้อง "
     "(เช่น #include <iostream> หรือ <string>)"),
    (r"'(.+)' was not declared in this scope; did you mean '(.+)'\?",
     "ไม่รู้จัก '{1}' — คุณอาจหมายถึง '{2}' (C++ แยกตัวพิมพ์เล็ก-ใหญ่)"),
    (r"expected '(;)' at end of (.+)",
     "ลืมใส่เครื่องหมาย ; ท้ายคำสั่ง"),
    (r"expected primary-expression before (.+)",
     "ตรงนี้ขาดค่าหรือตัวแปรที่ควรมี หรือพิมพ์เครื่องหมายเกินมา"),
    (r"expected '(\)|\(|\{|\}|\]|\[)'(.*)",
     "วงเล็บ {1} ไม่ครบคู่ ตรวจว่าเปิดและปิดวงเล็บครบหรือไม่"),
    (r"'(.+)' was not declared in this scope",
     "ไม่รู้จัก '{1}' — ยังไม่ได้ประกาศตัวแปร/ฟังก์ชันนี้ พิมพ์ชื่อผิด (C++ แยกตัวพิมพ์เล็ก-ใหญ่) "
     "หรือลืม #include"),
    (r"'(.+)' does not name a type",
     "'{1}' ไม่ใช่ชนิดข้อมูล อาจพิมพ์ชนิดข้อมูลผิด หรือลืม #include / using namespace std;"),
    (r"no match for 'operator(.+)' \(operand types are '(.+)' and '(.+)'\)",
     "ใช้ตัวดำเนินการ {1} กับข้อมูลชนิด '{2}' และ '{3}' ไม่ได้ ตรวจชนิดของตัวแปรอีกครั้ง"),
    (r"invalid conversion from '(.+)' to '(.+)'",
     "แปลงข้อมูลชนิด '{1}' ไปเป็น '{2}' โดยตรงไม่ได้"),
    (r"cannot convert '(.+)' to '(.+)'",
     "แปลง '{1}' ไปเป็น '{2}' ไม่ได้ ตรวจชนิดของค่าที่ส่งหรือกำหนด"),
    (r"redeclaration of '(.+)'|redefinition of '(.+)'",
     "ประกาศตัวแปร/ฟังก์ชันชื่อนี้ซ้ำ ใช้ชื่อเดียวกันสองครั้งในขอบเขตเดียวกันไม่ได้"),
    (r"conflicting declaration '(.+)'",
     "ประกาศชื่อนี้ขัดแย้งกับที่ประกาศไว้ก่อนหน้า"),
    (r"too few arguments to function(.*)",
     "ส่งค่าให้ฟังก์ชันน้อยเกินไป ตรวจจำนวนพารามิเตอร์ที่ฟังก์ชันต้องการ"),
    (r"too many arguments to function(.*)",
     "ส่งค่าให้ฟังก์ชันมากเกินไป ตรวจจำนวนพารามิเตอร์ที่ฟังก์ชันต้องการ"),
    (r"no matching function for call to '(.+)'",
     "ไม่พบฟังก์ชัน '{1}' ที่รับค่าแบบนี้ ตรวจชื่อ จำนวน และชนิดของค่าที่ส่ง"),
    (r"expected unqualified-id before (.+)",
     "มีสิ่งที่ไม่ควรอยู่ตรงนี้ ลองตรวจว่ามีวงเล็บ {{ }} หรือ ; เกินมา/ขาดไปก่อนหน้านี้หรือไม่"),
    (r"expected declaration before '\}' token",
     "มีวงเล็บปีกกา } เกินมา ตรวจว่าเปิด { ครบคู่หรือไม่"),
    (r"expected '\}' at end of input",
     "ขาดวงเล็บปีกกา } ปิดท้าย ตรวจว่าเปิด { กับปิด } ครบคู่หรือไม่"),
    (r"stray '(.+)' in program",
     "พบอักขระแปลกปลอม '{1}' ในโค้ด มักเกิดจากพิมพ์เครื่องหมายคำพูดแบบโค้ง “ ” "
     "หรือคัดลอกมาจากเว็บ/Word ให้พิมพ์ \" ใหม่ด้วยตัวเอง"),
    (r"missing terminating (.+) character",
     "เปิดเครื่องหมายคำพูดแล้วไม่ได้ปิด ตรวจ \" หรือ ' ให้ครบคู่"),
    (r"unterminated comment",
     "เปิดคอมเมนต์ /* แล้วไม่ได้ปิดด้วย */"),
    (r"([\w./\\-]+): No such file or directory",
     "ไม่พบไฟล์ '{1}' ตรวจชื่อไฟล์ใน #include ว่าสะกดถูกหรือไม่"),
    (r"invalid operands of types '(.+)' and '(.+)' to binary 'operator(.+)'",
     "ใช้ตัวดำเนินการ {3} กับชนิด '{1}' และ '{2}' ไม่ได้"),
    (r"assignment of read-only variable '(.+)'",
     "'{1}' เป็น const แก้ไขค่าไม่ได้"),
    (r"lvalue required as left operand of assignment",
     "ฝั่งซ้ายของ = ต้องเป็นตัวแปร ไม่ใช่ค่าคงที่/นิพจน์ (หรือคุณตั้งใจเขียน == ?)"),
    (r"return-statement with no value, in function returning '(.+)'",
     "ฟังก์ชันนี้ต้องคืนค่าชนิด '{1}' แต่ return ไม่มีค่า"),
    (r"'main' must return 'int'",
     "ฟังก์ชัน main ต้องคืนค่าเป็น int"),
    (r"jump to case label",
     "มีการประกาศตัวแปรใน case โดยไม่มีวงเล็บ { } ครอบ ลองใส่ { } ครอบ case นั้น"),
    (r"array used as initializer|array subscript is not an integer",
     "ดัชนีของ array ต้องเป็นจำนวนเต็มเท่านั้น"),
    (r"ISO C\+\+ forbids variable length array",
     "ขนาดของ array ควรเป็นค่าคงที่ ถ้าต้องการขนาดไม่แน่นอนให้ใช้ vector"),
    (r"narrowing conversion of '(.+)' from '(.+)' to '(.+)'",
     "การแปลง '{2}' เป็น '{3}' อาจทำให้ข้อมูลสูญหาย"),
    # ---- warning ----
    (r"unused variable '(.+)'",
     "ประกาศตัวแปร '{1}' แล้วไม่ได้ใช้งาน ลบออกหรือนำไปใช้"),
    (r"unused parameter '(.+)'",
     "พารามิเตอร์ '{1}' ไม่ได้ถูกใช้ในฟังก์ชัน"),
    (r"'(.+)' may be used uninitialized|'(.+)' is used uninitialized",
     "ใช้ตัวแปร '{1}' ก่อนกำหนดค่าเริ่มต้น ค่าที่ได้อาจเป็นขยะ ให้ตั้งค่า เช่น int x = 0;"),
    (r"comparison of integer expressions of different signedness: '(.+)' and '(.+)'",
     "เปรียบเทียบจำนวนเต็มมีเครื่องหมาย ('{1}') กับไม่มีเครื่องหมาย ('{2}') "
     "มักพบตอนเทียบ int กับ .size() ลองใช้ชนิดเดียวกัน"),
    (r"suggest parentheses around assignment used as truth value",
     "ใช้ = (กำหนดค่า) ในเงื่อนไข คุณอาจตั้งใจเขียน == (เปรียบเทียบ) ?"),
    (r"this '(.+)' clause does not guard",
     "คำสั่งหลัง {1} ไม่ได้อยู่ใน {1} จริง ๆ ตรวจการย่อหน้าและวงเล็บ { }"),
    (r"control reaches end of non-void function",
     "ฟังก์ชันนี้ต้องคืนค่า แต่บางเส้นทางไปจบโดยไม่มี return"),
    (r"empty body in an 'if' statement|suggest braces around empty body",
     "มี ; ท้ายเงื่อนไข ทำให้ if/for/while ไม่ทำอะไร ลองลบ ; ออก"),
    (r"format '(.+)' expects argument of type '(.+)', but argument (\d+) has type '(.+)'",
     "รูปแบบ {1} ต้องการข้อมูลชนิด '{2}' แต่ส่งชนิด '{4}' ไป"),
    (r"unused result|ignoring return value",
     "ฟังก์ชันคืนค่าแต่คุณไม่ได้นำค่าไปใช้"),
    (r"array subscript '?(.+?)'? is above array bounds|array subscript (.+) is outside array bounds",
     "เข้าถึง array เกินขอบเขต ดัชนีต้องอยู่ระหว่าง 0 ถึงขนาด-1"),
    (r"division by zero",
     "หารด้วยศูนย์ โปรแกรมจะผิดพลาดตอนรัน"),
    (r"overflow in conversion|integer overflow",
     "ค่าเกินขอบเขตของชนิดข้อมูล ลองใช้ long long"),
    # ---- linker ----
    (r"undefined reference to [`']main'?",
     "ไม่พบฟังก์ชัน main() ในโปรแกรม ตรวจว่าเขียน int main() ครบหรือไม่"),
    (r"undefined reference to [`'](.+?)'",
     "ลิงก์ไม่สำเร็จ: ประกาศ '{1}' ไว้แต่ไม่ได้เขียนตัวฟังก์ชัน (หรือสะกดชื่อไม่ตรงกัน)"),
    (r"multiple definition of [`'](.+?)'",
     "นิยาม '{1}' ซ้ำกันหลายที่"),
]

_COMPILED = [(re.compile(p), t) for p, t in RULES]

# ข้อความรองเมื่อไม่มีกฎตรงกัน
FALLBACK = {
    "error": "พบข้อผิดพลาดในโค้ด ลองอ่านข้อความภาษาอังกฤษด้านล่างและตรวจบรรทัดที่ระบุ "
             "(บางครั้งต้นเหตุอยู่ที่บรรทัดก่อนหน้า)",
    "warning": "คำเตือน: โค้ดคอมไพล์ผ่านแต่อาจทำงานไม่ตรงที่ตั้งใจ",
    "note": "",
}


@dataclass
class Diagnostic:
    file: str
    line: int
    col: int
    kind: str          # error | warning | note
    message: str       # ข้อความต้นฉบับภาษาอังกฤษ
    thai: str          # คำอธิบายภาษาไทย

    @property
    def is_error(self) -> bool:
        return self.kind == "error"


def explain(message: str, kind: str = "error", line: int = 0) -> str:
    """คืนคำอธิบายภาษาไทยสำหรับข้อความ g++ หนึ่งข้อความ (line ใช้ระบุ 'บรรทัดก่อนหน้า')"""
    prev = f"บรรทัดที่ {line - 1}" if line > 1 else "บรรทัดก่อนหน้า"
    for rx, template in _COMPILED:
        m = rx.search(message)
        if m:
            groups = [g if g is not None else "" for g in m.groups()]
            text = template.replace("{prev}", prev)
            for i, g in enumerate(groups, start=1):
                text = text.replace("{%d}" % i, g)
            return text.replace("{{", "{").replace("}}", "}")
    return FALLBACK.get(kind, "")


def parse_output(stderr: str) -> list[Diagnostic]:
    """แยกผลลัพธ์ของ g++ ออกเป็นรายการ Diagnostic"""
    result: list[Diagnostic] = []
    # g++ บางระบบใช้เครื่องหมายคำพูดโค้ง ‘ ’ ให้ทำเป็น ' ธรรมดาก่อนจับรูปแบบ
    stderr = stderr.replace("‘", "'").replace("’", "'")
    for raw in stderr.splitlines():
        m = DIAG_RE.match(raw.strip())
        if not m:
            # บรรทัด linker เช่น "undefined reference to ..."
            if "undefined reference" in raw or "multiple definition" in raw:
                result.append(Diagnostic("", 0, 0, "error", raw.strip(),
                                         explain(raw, "error")))
            continue
        kind = m.group("kind").replace("fatal ", "")
        msg = m.group("msg")
        line_no = int(m.group("line"))
        result.append(Diagnostic(
            file=m.group("file"),
            line=line_no,
            col=int(m.group("col") or 0),
            kind=kind,
            message=msg,
            thai=explain(msg, kind, line_no),
        ))
    return result


def format_report(diags: list[Diagnostic], *, show_notes: bool = False) -> str:
    """สร้างข้อความสรุปภาษาไทยไว้แสดงในหน้าต่าง Console"""
    lines: list[str] = []
    for d in diags:
        if d.kind == "note" and not show_notes:
            continue
        icon = {"error": "✖ ข้อผิดพลาด", "warning": "⚠ คำเตือน"}.get(d.kind, "ℹ หมายเหตุ")
        where = f"บรรทัดที่ {d.line}" if d.line else "ขั้นตอนลิงก์"
        lines.append(f"{icon} ({where})")
        if d.thai:
            lines.append(f"   → {d.thai}")
        lines.append(f"   [{d.message}]")
        lines.append("")
    return "\n".join(lines).rstrip()
