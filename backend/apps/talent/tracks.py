"""Iqtidor yo'nalishlari va platformadagi boshqa ma'lumotlardan yo'nalishga o'tish jadvallari."""

from django.db import models


class Track(models.TextChoices):
    RESEARCH = "research", "Ilmiy tadqiqot"
    OLYMPIAD = "olympiad", "Fan olimpiadalari"
    INVENTION = "invention", "Ixtirochilik va muhandislik"
    IT = "it", "IT va dasturlash"
    STARTUP = "startup", "Startap va tadbirkorlik"
    CREATIVE = "creative", "Dizayn va ijod"


ICONS = {
    Track.RESEARCH: "🔬",
    Track.OLYMPIAD: "🏅",
    Track.INVENTION: "⚙️",
    Track.IT: "💻",
    Track.STARTUP: "🚀",
    Track.CREATIVE: "🎨",
}

DESCRIPTIONS = {
    Track.RESEARCH: "Savol qo'yish, tajriba o'tkazish va natijani ilmiy maqolaga aylantirish sizga yaqin.",
    Track.OLYMPIAD: "Murakkab masalani tez va aniq yechish: fan olimpiadalari va intellektual musobaqalar.",
    Track.INVENTION: "Qo'l bilan yasash, qurilma va texnologiyani takomillashtirish, ixtiro va patent.",
    Track.IT: "Dastur, sayt, ilova va sun'iy intellekt orqali muammolarni hal qilish.",
    Track.STARTUP: "G'oyani mahsulotga, mahsulotni biznesga aylantirish va jamoani boshqarish.",
    Track.CREATIVE: "Vizual fikrlash: dizayn, 3D modellash, media va taqdimotlar.",
}

# Har bir yo'nalish uchun birinchi qadamlar (diagnostika natijasida ko'rsatiladi)
FIRST_STEPS = {
    Track.RESEARCH: ["Kafedradagi ilmiy to'garakka yoziling", "Bitta tezis yoki maqola rejasini tuzing"],
    Track.OLYMPIAD: ["Kunlik savollarni o'tkazib yubormang", "Fan olimpiadasiga tayyorlov rejasini tuzing"],
    Track.INVENTION: ["Muhandislik loyihasini boshlang yoki jamoaga qo'shiling", "Ixtiro g'oyangizni yozib qo'ying"],
    Track.IT: ["Hakatonda qatnashing", "GitHub'da portfolio loyihasini e'lon qiling"],
    Track.STARTUP: ["Loyihalar bo'limida g'oyangizni e'lon qiling", "Startap tanlovi yoki grantga ariza bering"],
    Track.CREATIVE: ["Portfolio uchun 3 ta ish tayyorlang", "Tadbirlar uchun dizayn jamoasiga qo'shiling"],
}

# Ko'nikma yo'nalishi (Skill.Category) -> iqtidor yo'nalishi
FROM_SKILL = {
    "programming": Track.IT,
    "engineering": Track.INVENTION,
    "design": Track.CREATIVE,
    "research": Track.RESEARCH,
    "leadership": Track.STARTUP,
    "languages": Track.RESEARCH,
}

# Yutuq turi (Achievement.Kind) -> yo'nalish
FROM_ACHIEVEMENT = {
    "olympiad": Track.OLYMPIAD,
    "hackathon": Track.IT,
    "publication": Track.RESEARCH,
    "patent": Track.INVENTION,
    "art": Track.CREATIVE,
}

# Natija hisoblanadigan yutuqlar (reyestrda «Natijaga erishgan» holati uchun)
RESULT_KINDS = {"olympiad", "hackathon", "publication", "patent"}

# Imkoniyat turi (Opportunity.Kind) -> mos yo'nalishlar (imkoniyatda yo'nalish tanlanmagan bo'lsa)
FROM_OPPORTUNITY = {
    "grant": [Track.RESEARCH, Track.STARTUP],
    "olympiad": [Track.OLYMPIAD],
    "hackathon": [Track.IT, Track.STARTUP, Track.INVENTION],
    "internship": [Track.IT, Track.INVENTION],
    "vacancy": [Track.IT],
    "freelance": [Track.IT, Track.CREATIVE],
    "industry_case": [Track.INVENTION, Track.STARTUP],
    "exchange": [Track.RESEARCH],
}


def label(track: str) -> str:
    return dict(Track.choices).get(track, "Belgilanmagan")


def icon(track: str) -> str:
    return ICONS.get(track, "✨")
