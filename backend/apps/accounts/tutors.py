"""Tyutorlar: fakultetga biriktirish, Word jadvalidan yuklash va ANDTI ro'yxati."""

import re
import zipfile
from xml.dom import minidom

from django.db import transaction

from .models import Faculty, Tutor

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
STOP_WORDS = {"fakulteti", "fakultet", "va", "fak"}

# ANDTI rahbariyati bergan ro'yxat (Rahbarlar to'g'risida ma'lumot): fakultet qisqa nomi -> tyutorlar
ANDTI_TUTORS = {
    "AT": ["Yaxshiboyev Davronbek", "Norboyev Adaxamjon", "Abdurazzakova Merojxon", "Komilova Nargiza"],
    "MKM": ["Yuldashev Ma'rifjon", "Malikova Dilfuza", "Nurmatova Xurshidaxon", "Usarov Lutfillo"],
    "IBKT": ["Alijonov Ismoiljon", "To'xtasinov Nurillo", "Aslanov Faridbek"],
    "QMEE": ["Qobulov Dostonbek", "Olimjonova Dono", "Mamatqulov Boburjon", "Xankeldiyeva Feruza",
             "Uzaqbayev Isroiljon", "Abduqasimova Shoiraxon"],
    "IB": ["Musayeva Odinaxon", "Turgunov Qudratillo", "Qodirov Maqsudbek", "Mamasolieva Matlyubaxon",
           "Musayeva Xilolaxon", "Xasanov Faroxiddin", "Abdulazizov Ahrorbek", "Axmedova Ra'noxon"],
}  # fmt: skip


class TutorImportError(Exception):
    pass


def clean_name(name: str) -> str:
    """Ortiqcha bo'shliqlar va har xil apostroflarni bir xil ko'rinishga keltiradi."""
    name = re.sub(r"[’‘ʻʼ`´]", "'", name or "")
    return re.sub(r"\s+", " ", name).strip()[:150]


def _tokens(text: str) -> list[str]:
    text = clean_name(text).lower().replace("'", "").replace("x", "h")
    return [t for t in re.findall(r"[a-zа-яўқғҳ0-9]+", text) if t not in STOP_WORDS]


def match_faculty(name: str, faculties=None):
    """Matndagi fakultet nomini bazadagi fakultetga moslaydi (yozilishdagi farqlarga chidamli)."""
    faculties = list(faculties if faculties is not None else Faculty.objects.all())
    words = _tokens(name)
    if not words:
        return None
    best, best_score = None, 0.0
    for faculty in faculties:
        if clean_name(name).lower() in {faculty.short_name.lower(), faculty.name.lower()}:
            return faculty
        candidates = _tokens(faculty.name)
        hits = sum(1 for w in words if any(c[:5] == w[:5] for c in candidates))
        score = hits / len(words)
        if score > best_score:
            best, best_score = faculty, score
    return best if best_score >= 0.5 else None


def read_docx_rows(file) -> list[list[str]]:
    """Word fayldagi barcha jadval qatorlari."""
    try:
        with zipfile.ZipFile(file) as archive:
            xml = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise TutorImportError("Word (.docx) faylni o'qib bo'lmadi") from exc
    document = minidom.parseString(xml)

    def text(node):
        return "".join(t.firstChild.data for t in node.getElementsByTagNameNS(W, "t") if t.firstChild)

    rows = []
    for row in document.getElementsByTagNameNS(W, "tr"):
        rows.append([text(cell).strip() for cell in row.getElementsByTagNameNS(W, "tc")])
    return rows


@transaction.atomic
def import_rows(rows) -> dict:
    """Jadvaldan tyutorlarni qo'shadi: «Fakultet» va «F.I.Sh.» ustunlari sarlavhadan topiladi.

    «Lavozimi» ustuni bo'lsa, faqat «tyutor» qatorlari olinadi. Takror qo'shilmaydi.
    """
    if not rows:
        raise TutorImportError("Faylda jadval topilmadi")
    header = [h.lower() for h in rows[0]]

    def column(*keys):
        return next((i for i, h in enumerate(header) if any(k in h for k in keys)), None)

    faculty_col, name_col, role_col = column("fakultet"), column("f.i.sh", "fio", "ism"), column("lavozim")
    if faculty_col is None or name_col is None:
        raise TutorImportError("Jadval sarlavhasida «Fakultet» va «F.I.Sh.» ustunlari bo'lishi kerak")
    faculties = list(Faculty.objects.all())
    result = {"added": 0, "existing": 0, "unknown": []}
    for row in rows[1:]:
        if max(faculty_col, name_col) >= len(row):
            continue
        if role_col is not None and role_col < len(row) and row[role_col] and "tyutor" not in row[role_col].lower():
            continue
        name = clean_name(row[name_col])
        if not name:
            continue
        faculty = match_faculty(row[faculty_col], faculties)
        if faculty is None:
            if row[faculty_col] not in result["unknown"]:
                result["unknown"].append(row[faculty_col])
            continue
        _, created = Tutor.objects.get_or_create(faculty=faculty, full_name=name)
        result["added" if created else "existing"] += 1
    return result


def ensure_andti_tutors() -> int:
    """Asosiy OTM (ANDTI) fakultetlariga rahbariyat bergan tyutorlarni biriktiradi. Qo'shilganlar soni."""
    added = 0
    for short, names in ANDTI_TUTORS.items():
        faculty = Faculty.objects.filter(short_name=short).first()
        if faculty is None:
            continue
        for name in names:
            _, created = Tutor.objects.get_or_create(faculty=faculty, full_name=name)
            added += created
    return added


def summary():
    """Fakultetlar bo'yicha tyutorlar: [(fakultet, [tyutorlar])]."""
    tutors = Tutor.objects.filter(is_active=True).select_related("faculty").order_by("faculty__name", "full_name")
    grouped = {}
    for tutor in tutors:
        grouped.setdefault(tutor.faculty, []).append(tutor)
    return list(grouped.items())
