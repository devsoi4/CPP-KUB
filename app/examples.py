"""โค้ดตัวอย่างสำหรับบทเรียนเบื้องต้น (ใช้ออฟไลน์ได้)"""

EXAMPLES: list[tuple[str, str]] = [
    ("01 สวัสดีชาวโลก", '''#include <iostream>
using namespace std;

int main() {
    cout << "สวัสดีชาวโลก!" << endl;
    cout << "ยินดีต้อนรับสู่การเขียนโปรแกรมภาษา C++" << endl;
    return 0;
}
'''),
    ("02 รับชื่อและทักทาย (cin)", '''#include <iostream>
#include <string>
using namespace std;

int main() {
    string name;
    cout << "คุณชื่ออะไร: ";
    cin >> name;
    cout << "สวัสดีครับ คุณ" << name << endl;
    return 0;
}
'''),
    ("03 บวกเลขสองจำนวน", '''#include <iostream>
using namespace std;

int main() {
    int a, b;
    cout << "ใส่เลขตัวที่ 1: ";
    cin >> a;
    cout << "ใส่เลขตัวที่ 2: ";
    cin >> b;
    cout << a << " + " << b << " = " << a + b << endl;
    return 0;
}
'''),
    ("04 เงื่อนไข if-else (เกรด)", '''#include <iostream>
using namespace std;

int main() {
    int score;
    cout << "ใส่คะแนน (0-100): ";
    cin >> score;

    if (score >= 80) {
        cout << "เกรด A" << endl;
    } else if (score >= 70) {
        cout << "เกรด B" << endl;
    } else if (score >= 60) {
        cout << "เกรด C" << endl;
    } else {
        cout << "ต้องพยายามอีกนิด" << endl;
    }
    return 0;
}
'''),
    ("05 วนซ้ำ for (สูตรคูณ)", '''#include <iostream>
using namespace std;

int main() {
    int n;
    cout << "สูตรคูณแม่: ";
    cin >> n;
    for (int i = 1; i <= 12; i++) {
        cout << n << " x " << i << " = " << n * i << endl;
    }
    return 0;
}
'''),
    ("06 วาดสามเหลี่ยมดาว", '''#include <iostream>
using namespace std;

int main() {
    int rows;
    cout << "จำนวนแถว: ";
    cin >> rows;
    for (int i = 1; i <= rows; i++) {
        for (int j = 1; j <= i; j++) {
            cout << "*";
        }
        cout << endl;
    }
    return 0;
}
'''),
    ("07 อาร์เรย์และค่าเฉลี่ย", '''#include <iostream>
using namespace std;

int main() {
    int n;
    cout << "มีกี่คน: ";
    cin >> n;

    double scores[100];
    double sum = 0;
    for (int i = 0; i < n; i++) {
        cout << "คะแนนคนที่ " << i + 1 << ": ";
        cin >> scores[i];
        sum += scores[i];
    }
    cout << "ค่าเฉลี่ย = " << sum / n << endl;
    return 0;
}
'''),
    ("08 ฟังก์ชัน (แฟกทอเรียล)", '''#include <iostream>
using namespace std;

long long factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

int main() {
    int n;
    cout << "ใส่จำนวนเต็ม: ";
    cin >> n;
    cout << n << "! = " << factorial(n) << endl;
    return 0;
}
'''),
    ("09 ข้อความภาษาไทยกับ string", '''#include <iostream>
#include <string>
using namespace std;

int main() {
    string text = "สวัสดี";
    cout << "ข้อความ: " << text << endl;
    // ภาษาไทยใน string เก็บแบบ UTF-8: ตัวอักษรไทย 1 ตัว = 3 ไบต์
    cout << "size() ได้ " << text.size() << " ไบต์ (ไม่ใช่ 6 ตัวอักษร)" << endl;
    return 0;
}
'''),
    ("10 ตัวอย่างที่มี error (ฝึกอ่านข้อผิดพลาด)", '''#include <iostream>
using namespace std;

int main() {
    int x = 10
    cout << "ค่า x คือ " << x << endl;
    cout << y << endl;
    return 0;
}
'''),
]

DEFAULT_CODE = EXAMPLES[0][1]

# คำอธิบายเขียนมือใต้ตัวแปรตอนดีบัก: ชื่อตัวอย่าง → {เลขบรรทัด: ข้อความ} (ใช้แทนข้อความอัตโนมัติ เมื่อโค้ดตรงกับตัวอย่างเป๊ะ)
ANNOTATIONS: dict[str, dict[int, str]] = {
    "08 ฟังก์ชัน (แฟกทอเรียล)": {
        5: "ถ้า n เหลือ 1 หรือน้อยกว่า จะหยุดเรียกตัวเองและส่งค่า 1 กลับไป (เงื่อนไขหยุด)",
        6: "ต้องรู้ factorial(n - 1) ก่อนจึงจะคูณกับ n ได้ จึงเรียกตัวเองอีกครั้ง",
    },
}


def annotations_for(code: str) -> dict[int, str]:
    """คำอธิบายเขียนมือของโค้ดนี้ (ว่างถ้าไม่ใช่ตัวอย่างที่มีคำอธิบาย)"""
    for title, src in EXAMPLES:
        if src == code:
            return ANNOTATIONS.get(title, {})
    return {}
