"""Iqtidor diagnostikasi: qiziqish va uslub savollari + platformadagi haqiqiy faollik.

Natija ikki manbadan olinadi:
- savolnoma (70%): talaba o'zi haqida nima deydi;
- dalillar (30%): ko'nikmalari, tasdiqlangan yutuqlari va yechgan topshiriqlari nimani ko'rsatadi.
Shunda yo'nalish faqat o'z-o'zini baholashga emas, real ishga ham tayanadi.
"""

from collections import Counter

from apps.discovery.models import Submission
from apps.profiles.models import Achievement, UserSkill

from .tracks import FROM_ACHIEVEMENT, FROM_SKILL, Track

R, OL, INV, IT, S, C = Track.RESEARCH, Track.OLYMPIAD, Track.INVENTION, Track.IT, Track.STARTUP, Track.CREATIVE

# (kalit, savol, [(variant kaliti, matn, {yo'nalish: ball})])
QUESTIONS = [
    (
        "free_time",
        "Bo'sh vaqtingizda ko'proq nima qilishni yoqtirasiz?",
        [
            ("read", "Ilmiy maqola yoki ommabop fan kitoblarini o'qish", {R: 3, OL: 1}),
            ("solve", "Murakkab masala va boshqotirmalar yechish", {OL: 3, R: 1}),
            ("build", "Biror qurilma yasash yoki ta'mirlash", {INV: 3}),
            ("code", "Dastur yoki sayt yozish", {IT: 3}),
            ("business", "Pul ishlash g'oyalarini o'ylash, savdo qilish", {S: 3}),
            ("draw", "Chizish, dizayn, video yoki foto", {C: 3}),
        ],
    ),
    (
        "problem",
        "Yangi muammoga duch kelsangiz, birinchi navbatda nima qilasiz?",
        [
            ("why", "Nima uchun shunday bo'lganini chuqur o'rganaman", {R: 3}),
            ("formula", "Uni aniq masala ko'rinishiga keltirib yechaman", {OL: 3}),
            ("prototype", "Tezda sinov variantini yasab ko'raman", {INV: 2, IT: 1}),
            ("automate", "Uni avtomatlashtiradigan dastur haqida o'ylayman", {IT: 3}),
            ("people", "Bu muammo boshqalarda ham bormi, unga kim pul to'laydi deb o'ylayman", {S: 3}),
            ("visual", "Avval chizib, sxema qilib ko'raman", {C: 2, INV: 1}),
        ],
    ),
    (
        "subject",
        "Qaysi fanlar sizga eng oson va qiziq?",
        [
            ("math", "Matematika, fizika", {OL: 2, R: 1, INV: 1}),
            ("chem", "Kimyo, biologiya, ekologiya", {R: 3}),
            ("tech", "Chizmachilik, mexanika, elektrotexnika", {INV: 3}),
            ("cs", "Informatika, dasturlash", {IT: 3}),
            ("econ", "Iqtisodiyot, menejment", {S: 3}),
            ("art", "San'at, adabiyot, dizayn", {C: 3}),
        ],
    ),
    (
        "team",
        "Jamoada odatda qaysi rolni olasiz?",
        [
            ("leader", "Yetakchi: vazifalarni taqsimlayman", {S: 3}),
            ("thinker", "G'oya beruvchi va tahlilchi", {R: 2, OL: 1}),
            ("maker", "Asosiy ishni bajaruvchi: yasayman yoki kod yozaman", {INV: 1, IT: 2}),
            ("designer", "Taqdimot va ko'rinish uchun mas'ul", {C: 3}),
            ("solo", "Yakka ishlashni afzal ko'raman", {OL: 2, R: 1}),
        ],
    ),
    (
        "proud",
        "Qaysi natija sizni eng ko'p xursand qilardi?",
        [
            ("article", "Xalqaro jurnalda maqolam chiqishi", {R: 3}),
            ("medal", "Respublika olimpiadasida oltin medal", {OL: 3}),
            ("patent", "OL'z ixtiromga patent olish", {INV: 3}),
            ("app", "Minglab odam ishlatadigan ilova yaratish", {IT: 3}),
            ("company", "OL'z kompaniyamni ochish", {S: 3}),
            ("exhibition", "Ishlarim ko'rgazmada namoyish etilishi", {C: 3}),
        ],
    ),
    (
        "pace",
        "Qanday ish uslubi sizga mos?",
        [
            ("deep", "Bitta mavzuni oylab chuqur o'rganish", {R: 3}),
            ("sprint", "Vaqt cheklangan musobaqa, tez fikrlash", {OL: 2, IT: 1}),
            ("hands", "Ustaxona yoki laboratoriyada amaliy ish", {INV: 3}),
            ("iterate", "Tez-tez sinab, xatodan o'rganib takomillashtirish", {IT: 2, S: 1}),
            ("variety", "Har kuni yangi odamlar va vazifalar", {S: 3}),
            ("create", "Erkin ijod, qat'iy qoidalarsiz", {C: 3}),
        ],
    ),
    (
        "event",
        "Qaysi tadbirga borishni tanlardingiz?",
        [
            ("conf", "Ilmiy konferensiya", {R: 3}),
            ("olymp", "Fan olimpiadasi", {OL: 3}),
            ("expo", "Texnika va ixtirolar ko'rgazmasi", {INV: 3}),
            ("hack", "48 soatlik hakaton", {IT: 3}),
            ("pitch", "Startap pitch kuni va investorlar uchrashuvi", {S: 3}),
            ("design", "Dizayn yoki media festivali", {C: 3}),
        ],
    ),
    (
        "tool",
        "Qaysi vosita bilan ishlash sizga yoqadi?",
        [
            ("lab", "Laboratoriya jihozlari va mikroskop", {R: 3}),
            ("paper", "Qog'oz, qalam va formulalar", {OL: 3}),
            ("cad", "AutoCAD, SolidWorks, Arduino", {INV: 3}),
            ("ide", "Kod muharriri, terminal", {IT: 3}),
            ("excel", "Excel, taqdimot, biznes-reja", {S: 3}),
            ("figma", "Figma, Photoshop, Blender", {C: 3}),
        ],
    ),
    (
        "future",
        "5 yildan keyin o'zingizni kim sifatida ko'rasiz?",
        [
            ("scientist", "Olim yoki magistr/PhD talabasi", {R: 3}),
            ("champion", "Musobaqalar g'olibi, kuchli mutaxassis", {OL: 2, IT: 1}),
            ("engineer", "Yirik zavod yoki loyihada bosh muhandis", {INV: 3}),
            ("developer", "Xalqaro IT kompaniyada dasturchi", {IT: 3}),
            ("founder", "OL'z biznesim egasi", {S: 3}),
            ("artist", "Dizayner yoki kreativ direktor", {C: 3}),
        ],
    ),
    (
        "motivation",
        "Sizni eng ko'p nima harakatlantiradi?",
        [
            ("truth", "Haqiqatni bilish, kashfiyot", {R: 3}),
            ("win", "G'alaba va birinchi bo'lish", {OL: 3}),
            ("useful", "Odamlarga foydali narsa yasash", {INV: 2, IT: 1}),
            ("scale", "Texnologiya bilan katta muammoni hal qilish", {IT: 2, S: 1}),
            ("freedom", "Moliyaviy erkinlik va mustaqillik", {S: 3}),
            ("beauty", "Go'zallik va o'zini ifoda etish", {C: 3}),
        ],
    ),
]

QUESTION_WEIGHT = 0.7
EVIDENCE_WEIGHT = 0.3


def option_map():
    return {key: {opt: weights for opt, _, weights in options} for key, _, options in QUESTIONS}


def validate(answers: dict) -> dict:
    """Faqat ma'lum savol va variantlarni qoldiradi. Barcha savolga javob bo'lmasa ValueError."""
    options = option_map()
    clean = {key: answers.get(key) for key in options if answers.get(key) in options[key]}
    if len(clean) != len(options):
        raise ValueError("Barcha savollarga javob bering")
    return clean


def _questionnaire(answers: dict) -> dict:
    options = option_map()
    totals = Counter()
    for key, choice in answers.items():
        totals.update(options[key][choice])
    best = max(totals.values(), default=0) or 1
    return {track: totals.get(track, 0) / best for track in Track.values}


def _evidence(user) -> dict:
    totals = Counter()
    for category, level in UserSkill.objects.filter(user=user).values_list("skill__category", "level"):
        track = FROM_SKILL.get(category)
        if track:
            totals[track] += level or 1
    for kind in Achievement.objects.filter(user=user, status=Achievement.Status.APPROVED).values_list(
        "kind", flat=True
    ):
        track = FROM_ACHIEVEMENT.get(kind)
        if track:
            totals[track] += 5
    accepted = Submission.objects.filter(user=user, status=Submission.Status.ACCEPTED).count()
    if accepted:
        totals[Track.OLYMPIAD] += min(accepted, 10)
    best = max(totals.values(), default=0)
    return {track: (totals.get(track, 0) / best if best else 0) for track in Track.values}


def score(user, answers: dict) -> tuple[dict, str, str]:
    """(yo'nalishlar bo'yicha 0..100 ball, birinchi yo'nalish, ikkinchi yo'nalish)."""
    asked = _questionnaire(answers)
    evidence = _evidence(user)
    has_evidence = any(evidence.values())
    weight = EVIDENCE_WEIGHT if has_evidence else 0
    scores = {track: round(100 * ((1 - weight) * asked[track] + weight * evidence[track])) for track in Track.values}
    ranked = sorted(Track.values, key=lambda t: (-scores[t], Track.values.index(t)))
    return scores, ranked[0], ranked[1]
