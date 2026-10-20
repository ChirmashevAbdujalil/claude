"""So'rovnomadagi «Fayl yuklash» savoli: fayl turini ichidan tekshirish, yopiq saqlash va javobga biriktirish.

Fayl turi nomidagi kengaytmaga emas, birinchi baytlariga qarab aniqlanadi: .pdf deb nomlangan dastur yoki
rasm niqobidagi HTML qabul qilinmaydi. Fayllar MEDIA_URL orqali berilmaydi (PRIVATE_MEDIA_ROOT), ularni faqat
rahbariyat ruxsat tekshiriladigan sahifa orqali ko'radi.
"""

import os
import re
import uuid
import zipfile
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from django.core.files.storage import FileSystemStorage

MB = 1024 * 1024
MAX_FILES = 10
MAX_FILE_MB = 20
DEFAULT_FILE_MB = 10
SIZE_CHOICES = (2, 5, 10, 15, 20)
MAX_TOTAL_MB = 100  # bitta yuborishdagi barcha fayllar
MAX_REQUEST_BYTES = (MAX_TOTAL_MB + 3) * MB
IP_HOURLY_LIMIT = 120  # bitta manzildan soatiga yuklanadigan fayllar soni

TYPES = {
    "pdf": {"label": "PDF", "icon": "📕", "ext": ("pdf",), "accept": ".pdf,application/pdf"},
    "image": {
        "label": "Rasm",
        "icon": "🖼",
        "ext": ("jpg", "jpeg", "png", "webp", "heic", "heif"),
        "accept": "image/*,.heic,.heif",
    },
    "word": {"label": "Word", "icon": "📘", "ext": ("doc", "docx"), "accept": ".doc,.docx"},
    "excel": {"label": "Excel", "icon": "📗", "ext": ("xls", "xlsx"), "accept": ".xls,.xlsx"},
    "slides": {"label": "PowerPoint", "icon": "📙", "ext": ("ppt", "pptx"), "accept": ".ppt,.pptx"},
}
CONTENT_TYPES = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "heic": "image/heic",
    "heif": "image/heif",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
# Brauzer o'zi xavfsiz ko'rsata oladigan turlar: qolganlari faqat yuklab olinadi
INLINE = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
OOXML = {"word": "word/document.xml", "excel": "xl/workbook.xml", "slides": "ppt/presentation.xml"}
OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
HEIF_BRANDS = {b"heic", b"heix", b"hevc", b"heim", b"heis", b"mif1", b"msf1", b"heif"}


class PrivateStorage(FileSystemStorage):
    """PRIVATE_MEDIA_ROOT dagi fayllar: sozlama o'zgarsa (testlarda), joy ham o'zgaradi."""

    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        return None


def private_storage():
    return PrivateStorage()


def upload_to(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"surveys/{instance.response.survey_id}/{instance.response_id}/{uuid.uuid4().hex}.{ext}"


@dataclass
class Upload:
    """Tekshiruvdan o'tgan, hali saqlanmagan fayl."""

    file: object
    name: str
    ext: str
    size: int
    category: str
    content_type: str


def accept_for(types) -> str:
    return ",".join(TYPES[t]["accept"] for t in (types or TYPES) if t in TYPES)


def describe(types) -> str:
    return ", ".join(TYPES[t]["label"] for t in (types or TYPES) if t in TYPES)


def human_size(size: int) -> str:
    if size >= MB:
        return f"{size / MB:.1f} MB".replace(".0 MB", " MB")
    return f"{max(1, round(size / 1024))} KB"


def clean_name(name: str) -> str:
    """Asl nom faqat ko'rsatish uchun: yo'l qismlari va boshqaruv belgilari olib tashlanadi."""
    name = os.path.basename(str(name or "").replace("\\", "/"))
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip().strip(".") or "fayl"
    if len(name) > 150:
        stem, dot, ext = name.rpartition(".")
        name = (stem[: 140 - len(ext)] + dot + ext) if dot and len(ext) <= 8 else name[:150]
    return name


def sniff(upload, ext: str) -> str | None:
    """Faylning haqiqiy turi (TYPES kaliti) yoki None. Kengaytma ham shu turga mos bo'lishi kerak."""
    upload.seek(0)
    head = upload.read(16)
    upload.seek(0)
    category = None
    if head.startswith(b"%PDF-"):
        category = "pdf"
    elif head.startswith(b"\xff\xd8\xff") or head.startswith(b"\x89PNG\r\n\x1a\n"):
        category = "image"
    elif head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        category = "image"
    elif head[4:8] == b"ftyp" and head[8:12] in HEIF_BRANDS:
        category = "image"
    elif head.startswith(OLE):  # eski .doc/.xls/.ppt: ichki tuzilma bir xil, kengaytmaga tayaniladi
        category = next((c for c in ("word", "excel", "slides") if ext in TYPES[c]["ext"]), None)
    elif head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(upload) as archive:
                names = set(archive.namelist())
        except (zipfile.BadZipFile, OSError, ValueError):
            names = set()
        finally:
            upload.seek(0)
        category = next((c for c, marker in OOXML.items() if marker in names), None)
    if category is None or ext not in TYPES[category]["ext"]:
        return None
    return category


def content_type_of(category: str, ext: str, upload) -> str:
    if category == "image":
        upload.seek(0)
        head = upload.read(16)
        upload.seek(0)
        if head.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if head.startswith(b"\x89PNG"):
            return "image/png"
        if head[:4] == b"RIFF":
            return "image/webp"
        return "image/heic"
    return CONTENT_TYPES.get(ext, "application/octet-stream")


def clean(question, uploads) -> tuple[list[Upload] | None, str | None]:
    """(tekshirilgan fayllar, xato). Fayl tanlanmagan bo'lsa (None, None)."""
    uploads = [u for u in uploads if getattr(u, "size", 0)]
    if not uploads:
        return None, None
    if len(uploads) > question.max_files:
        return None, f"Ko'pi bilan {question.max_files} ta fayl yuklang"
    allowed = question.file_types or list(TYPES)
    cleaned = []
    for upload in uploads:
        name = clean_name(upload.name)
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if upload.size > question.max_file_mb * MB:
            return (
                None,
                f"«{name}» hajmi {human_size(upload.size)}: har bir fayl {question.max_file_mb} MB dan oshmasin",
            )
        category = sniff(upload, ext)
        if category is None:
            return None, f"«{name}» faylini ochib bo'lmadi yoki turi mos emas. Ruxsat: {describe(allowed)}"
        if category not in allowed:
            return None, f"«{name}»: bu savolga faqat {describe(allowed)} yuklanadi"
        cleaned.append(Upload(upload, name, ext, upload.size, category, content_type_of(category, ext, upload)))
    return cleaned, None


def request_limit(questions) -> int:
    """Bitta yuborishda kutiladigan eng katta hajm (baytda): fayl savollari chegarasi + matnlar uchun zaxira."""
    total = sum(q.max_files * q.max_file_mb * MB for q in questions if q.kind == "file")
    return min(total, MAX_TOTAL_MB * MB) + 3 * MB


def over_ip_limit(ip: str, count: int) -> bool:
    """Bir manzildan juda ko'p fayl yuklanishini to'xtatadi (ro'yxatdan o'tmaganlar uchun spamdan himoya)."""
    if not ip or not count:
        return False
    key = f"sv-uploads:{ip}"
    used = cache.get(key, 0)
    if used + count > IP_HOURLY_LIMIT:
        return True
    cache.set(key, used + count, 3600)
    return False


def split(answers) -> tuple[dict, dict]:
    """Javoblardan tekshirilgan fayllarni ajratadi: javobda fayl nomlari qoladi."""
    plain, uploads = {}, {}
    for key, value in answers.items():
        if isinstance(value, list) and value and isinstance(value[0], Upload):
            uploads[key] = value
            plain[key] = [u.name for u in value]
        else:
            plain[key] = value
    return plain, uploads


def attach(response, uploads) -> list:
    from .models import ResponseFile

    saved = []
    for key, items in uploads.items():
        for upload in items:
            record = ResponseFile(
                response=response,
                question_id=int(key),
                name=upload.name,
                size=upload.size,
                category=upload.category,
                content_type=upload.content_type,
            )
            upload.file.seek(0)
            record.file.save(upload.name, upload.file, save=False)
            record.save()
            saved.append(record)
    return saved
