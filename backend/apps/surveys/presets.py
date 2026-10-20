"""Tayyor so'rovnomalar: ANDTI rahbariyati bergan savollar (Google Forms'dan ko'chirilgan).

Ma'lumot oddiy lug'atlarda: migratsiya ham, shablonlar ro'yxati ham shu yerdan oladi.
F.I.Sh. savoli alohida berilmaydi: uni so'rovnoma boshidagi «Siz haqingizda» bloki (F.I.Sh., fakultet, tyutor,
kurs, guruh) so'raydi.
"""

ANDTI_TALENT_TITLE = "🎯 «ANDTI TALENT» — Institut talabalari qobiliyatlarini aniqlash so'rovnomasi"
OLD_TITLES = ["🎯 «ANDTI TALENT» — 1-bosqich: talabalar qobiliyatlarini aniqlash so'rovnomasi"]


def _q(kind, title, *, required=True, options=(), help_text="", allow_other=False, to_profile=False):
    return {
        "kind": kind,
        "title": title,
        "required": required,
        "options": list(options),
        "help_text": help_text,
        "allow_other": allow_other,
        "to_profile": to_profile,
    }


def _long(title, help_text=""):
    return _q("long", title, help_text=help_text)


SKILLS = [
    "💻 Dasturlash", "🌐 Web-dizayn", "📱 Mobil ilova yaratish", "🤖 Sun'iy intellekt", "🎨 Grafik dizayn",
    "🎬 Video montaj", "📷 Fotografiya", "🎙 Boshlovchilik", "🎤 Notiqlik", "✍️ Maqola yozish", "📰 Jurnalistika",
    "📱 SMM", "📢 Reklama/marketing", "🎵 Qo'shiq aytish", "🎸 Musiqa asboblari chalish (gitara yoki boshqalar)",
    "🎭 Aktyorlik", "💃 Raqs", "🏃 Yengil atletika", "⚽ Futbol", "🏀 Basketbol", "🏐 Voleybol", "🥋 Yakkakurashlar",
    "♟ Shaxmat", "🧠 Zakovat/intellektual o'yinlar", "🔬 Ilmiy-tadqiqot", "📐 Chizma/chizmachilik", "🛠 Mexanika",
    "⚡ Elektronika", "🔧 Texnika ta'mirlash", "🚗 Avtomobil texnikasi", "🏗 Qurilish sohalari",
    "📊 Excel/ma'lumotlar bilan ishlash", "💰 Biznes/tadbirkorlik", "💡 Startap yaratish", "🗣 Chet tillari",
    "🤝 Jamoa bilan ishlash", "👥 Liderlik", "🧑‍🏫 Boshqalarga dars berish", "❤️ Volontyorlik", "🌱 Ekologik loyihalar",
]  # fmt: skip

ANDTI_TALENT = {
    "survey": {
        "title": ANDTI_TALENT_TITLE,
        "description": (
            "Bu oddiy so'rovnoma emas — bu sizning ANDTI'dagi imkoniyatlaringizga olib boruvchi ilk qadam. "
            "Javoblaringiz asosida qobiliyatingizga mos klub, loyiha va tadbirlarga taklif qilamiz."
        ),
        "talent_census": True,
        "xp_reward": 50,
        "thank_you": (
            "Rahmat! Javoblaringiz «ANDTI TALENT» jamoasiga yetib bordi. Qobiliyatingizga mos klub va loyihalar "
            "bo'yicha siz bilan bog'lanamiz."
        ),
    },
    "questions": [
        _q("section", "Umumiy ma'lumotlar", required=False),
        _q(
            "dropdown",
            "Ta'lim yo'nalishingiz",
            options=[
                "Iqtisodiyot",
                "Moliya va moliyaviy texnologiyalar",
                "Bank ishi",
                "Buxgalteriya hisobi",
                "Menejment",
                "Marketing",
            ],
        ),
        _q(
            "multiple",
            "Qaysi tillarni bilasiz?",
            required=False,
            options=["O'zbek", "Ingliz", "Rus", "Turk", "Koreys", "Arab", "Nemis", "Xitoy"],
            allow_other=True,
            help_text="Bir nechtasini belgilashingiz mumkin",
        ),
        _long("Institut sizga o'z qobiliyatingizni namoyish qilish uchun imkoniyat bersa, nima qilgan bo'lardingiz?"),
        _q(
            "single",
            "Institut yotoqxonasida (TTJ) turasizmi yoki qatnab o'qiysizmi?",
            options=["TTJ da turaman", "Uydan qatnayman"],
            allow_other=True,
        ),
        _q("section", "Qobiliyat va tajriba", required=False, help_text="O'zingizda bor narsalarni belgilang"),
        _q(
            "multiple",
            "Sizning qanday qobiliyatlaringiz bor?",
            options=SKILLS,
            allow_other=True,
            to_profile=True,
            help_text="Bir nechtasini belgilang. Ro'yxatda yo'q bo'lsa, «Boshqa» qatoriga yozing",
        ),
        _long(
            "👆 Yuqorida belgilagan qobiliyatlaringiz bo'yicha qanday tajribaga egasiz va qobiliyatingiz darajasida "
            "nimalar qila olasiz?"
        ),
        _q("short", "Sizda qanday real tajriba bor?", help_text="Masalan: ish joyi, loyiha, to'garak yoki tanlov"),
        _q(
            "multiple",
            "Kommunikatsiya va liderlik: qaysilari qo'lingizdan keladi?",
            options=[
                "Odamlar oldida bemalol gapira olaman",
                "Notanish odamlar bilan tez muloqotga kirisha olaman",
                "Jamoani boshqara olaman",
                "Tadbirlar tashkil qila olaman",
                "Odamlarni bir maqsad atrofida birlashtira olaman",
                "Bahs-munozarada o'z fikrimni himoya qila olaman",
                "Mikrofon oldida chiqish qilishdan qo'rqmayman",
                "Kamera oldida bemalol gapira olaman",
                "Mas'uliyatni o'z zimmamga olishdan qo'rqmayman",
            ],
            help_text="Bir nechtasini tanlashingiz mumkin",
        ),
        _q("short", "Qaysi sport turlarida tajribangiz bor?", help_text="Bo'lmasa, «yo'q» deb yozing"),
        _q("section", "Faollik va qiziqishlar", required=False),
        _q(
            "multiple",
            "Qanday ijtimoiy faollik ishlarida qatnashgansiz?",
            options=[
                "Volontyor bo'lganman",
                "Yoshlar tashkilotida ishlaganman",
                "Tadbir tashkil qilganman",
                "Mahalla tadbirlarida qatnashganman",
                "Xayriya ishlarida qatnashganman",
                "Ekologik aksiyalarda qatnashganman",
                "Jamoatchilik loyihalarida qatnashganman",
                "Liderlik qilganman",
            ],
            allow_other=True,
        ),
        _q(
            "multiple",
            "Institutda qaysi yo'nalishda faol bo'lishni xohlaysiz?",
            options=[
                "Yoshlar bilan ishlash",
                "Volontyorlik",
                "Media (matbuot) ishlarida",
                "IT",
                "Sport",
                "Madaniyat",
                "Ilm-fan",
                "Innovatsiya",
                "Ekologiya",
                "Xalqaro loyihalar",
                "Talabalar tashkilotlari",
            ],
            allow_other=True,
        ),
        _q(
            "section",
            "O'zingiz haqingizda",
            required=False,
            help_text="Bu savollarda to'g'ri yoki noto'g'ri javob yo'q: o'zingizcha, samimiy yozing",
        ),
        _long("Odamlar sizdan odatda qaysi ishni yaxshi bajara olishingiz sababli yordam so'rashadi?"),
        _long("Siz hech kim o'rgatmasdan mustaqil o'rgangan narsangiz nima?"),
        _long("Sizga 1 hafta va barcha kerakli resurslar berilsa, institut uchun nima yaratgan bo'lardingiz?"),
        _long("O'zingizdagi boshqalardan farq qiladigan qobiliyat nima deb o'ylaysiz?"),
        _long("Qaysi ishni bajarayotganda vaqt qanday o'tganini sezmay qolasiz?"),
        _long("Hozirgacha erishgan eng katta yutug'ingiz nima?"),
        _long("Hali hech kim bilmaydigan, lekin sizda bor qobiliyat nima?"),
        _q("section", "Yakun", required=False),
        _long("Qo'shimcha takliflaringiz"),
        _q(
            "short",
            "Siz bilan bog'lanishimiz uchun Telegram username yoki telefon raqamingizni yozib qoldiring",
            help_text="Masalan: @username yoki +998 90 123 45 67",
        ),
    ],
}
