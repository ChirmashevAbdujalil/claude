"""Boshlang'ich ma'lumotlar: nishonlar, ko'nikmalar, mukofotlar va (ixtiyoriy) demo ma'lumotlar.

python manage.py seed           # faqat ma'lumotnomalar
python manage.py seed --demo    # + demo fakultetlar, talabalar, challenge va tadbirlar
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Faculty, User
from apps.arena.models import Badge
from apps.community.models import Event
from apps.discovery.models import Challenge
from apps.opportunities.models import Opportunity, Reward
from apps.profiles.models import Skill

BADGES = [
    ("first-challenge", "Birinchi qadam", "Birinchi challenge muvaffaqiyatli yechildi", "🎯", 20),
    ("first-endorsement", "Tan olingan", "O'qituvchi birinchi ko'nikmangizni tasdiqladi", "✅", 20),
    ("streak-7", "Olovli hafta", "7 kun ketma-ket faollik", "🔥", 0),
    ("streak-30", "Temir iroda", "30 kun ketma-ket faollik", "💪", 100),
    ("streak-100", "Afsonaviy intizom", "100 kun ketma-ket faollik", "🏆", 300),
    ("level-2", "Izlanuvchi", "2-darajaga yetdingiz", "🔍", 0),
    ("level-3", "Ixtirochi", "3-darajaga yetdingiz", "💡", 0),
    ("level-4", "Innovator", "4-darajaga yetdingiz", "🚀", 0),
    ("level-5", "Afsona", "5-darajaga yetdingiz", "👑", 0),
    ("team-player", "Jamoa o'yinchisi", "Loyiha jamoasiga qabul qilindingiz", "🤝", 20),
    ("hackathon", "Hakaton qahramoni", "Hakaton yutug'i tasdiqlandi", "⚡", 50),
    ("inventor", "Ixtirochi", "Patent yoki ixtiro tasdiqlandi", "🧪", 100),
    ("startup-founder", "Startap asoschisi", "Loyihangiz startup bosqichiga chiqdi", "🦄", 200),
]

SKILLS = {
    Skill.Category.PROGRAMMING: [
        "Python",
        "JavaScript",
        "C++",
        "Ma'lumotlar bazalari",
        "Sun'iy intellekt",
        "Mobil ilovalar",
        "Kiberxavfsizlik",
    ],
    Skill.Category.ENGINEERING: [
        "Robototexnika",
        "Elektronika",
        "3D modellashtirish",
        "AutoCAD",
        "Energetika",
        "Avtomobilsozlik",
        "Mexanika",
    ],
    Skill.Category.DESIGN: ["UI/UX dizayn", "Grafik dizayn", "Video montaj"],
    Skill.Category.RESEARCH: ["Ilmiy maqola yozish", "Ma'lumotlar tahlili", "Matematik modellashtirish"],
    Skill.Category.LEADERSHIP: ["Jamoa boshqaruvi", "Notiqlik", "Loyiha boshqaruvi"],
    Skill.Category.LANGUAGES: ["Ingliz tili", "Rus tili", "Nemis tili"],
}

REWARDS = [
    ("Oshxona taloni", "Institut oshxonasida bir martalik tushlik", 50, 100),
    ("Texnik kitob", "Kutubxonadan tanlangan kitob sovg'a sifatida", 150, 30),
    ("Talent Hub futbolkasi", "Platformaning brendli futbolkasi", 300, 50),
    ("Onlayn kurs sertifikati", "Hamkor platformada pullik kurs", 800, 10),
    ("Rektor bilan choy", "Rektor bilan shaxsiy uchrashuv", 1500, 5),
]

DEMO_FACULTIES = [
    ("Kompyuter injiniringi (demo)", "KI"),
    ("Energetika (demo)", "EN"),
    ("Mashinasozlik (demo)", "MSH"),
    ("Avtomobilsozlik va transport (demo)", "AT"),
]


class Command(BaseCommand):
    help = "Boshlang'ich ma'lumotlarni yuklaydi"

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true", help="Demo fakultet, foydalanuvchi va kontent yaratish")

    @transaction.atomic
    def handle(self, *args, **options):
        for code, name, description, icon, bonus in BADGES:
            Badge.objects.update_or_create(
                code=code, defaults={"name": name, "description": description, "icon": icon, "xp_bonus": bonus}
            )
        for category, names in SKILLS.items():
            for name in names:
                Skill.objects.get_or_create(name=name, defaults={"category": category})
        for name, description, price, stock in REWARDS:
            Reward.objects.get_or_create(
                name=name, defaults={"description": description, "price": price, "stock": stock}
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Nishonlar: {len(BADGES)}, ko'nikmalar: {Skill.objects.count()}, mukofotlar: {Reward.objects.count()}"
            )
        )

        if options["demo"]:
            self._demo()

    def _demo(self):
        faculties = [
            Faculty.objects.get_or_create(short_name=short, defaults={"name": name})[0]
            for name, short in DEMO_FACULTIES
        ]
        teacher, created = User.objects.get_or_create(
            username="demo_teacher",
            defaults={
                "first_name": "Demo",
                "last_name": "O'qituvchi",
                "role": User.Role.TEACHER,
                "faculty": faculties[0],
            },
        )
        if created:
            teacher.set_password("demo12345")
            teacher.save()
        rector, created = User.objects.get_or_create(
            username="demo_rector",
            defaults={"first_name": "Demo", "last_name": "Rektorat", "role": User.Role.RECTOR, "is_staff": True},
        )
        if created:
            rector.set_password("demo12345")
            rector.save()
        for index in range(1, 9):
            student, created = User.objects.get_or_create(
                username=f"demo_student{index}",
                defaults={
                    "first_name": f"Talaba{index}",
                    "last_name": "Demo",
                    "faculty": faculties[index % len(faculties)],
                    "course": (index % 4) + 1,
                    "portfolio_slug": f"demo-student-{index}",
                },
            )
            if created:
                student.set_password("demo12345")
                student.save()

        now = timezone.now()
        Challenge.objects.get_or_create(
            title="Kunlik savol: Ohm qonuni",
            defaults={
                "description": "Kuchlanish 12 V, qarshilik 4 Om. Tok kuchi necha amper?",
                "kind": Challenge.Kind.DAILY,
                "difficulty": Challenge.Difficulty.EASY,
                "category": Skill.Category.ENGINEERING,
                "expected_answer": "3",
                "starts_at": now,
                "ends_at": now + timedelta(days=1),
                "created_by": teacher,
            },
        )
        Challenge.objects.get_or_create(
            title="Haftalik: Andijon uchun aqlli to'xtash joyi",
            defaults={
                "description": "Shahar markazidagi bo'sh to'xtash joylarini real vaqtda ko'rsatuvchi tizim "
                "arxitekturasini taklif qiling. Sxema va qisqa tushuntirish yuboring.",
                "kind": Challenge.Kind.WEEKLY,
                "difficulty": Challenge.Difficulty.MEDIUM,
                "category": Skill.Category.PROGRAMMING,
                "starts_at": now,
                "ends_at": now + timedelta(days=7),
                "created_by": teacher,
            },
        )
        Event.objects.get_or_create(
            title="Talent Hub Launch Hackathon",
            defaults={
                "description": "Platformaning rasmiy ochilishi: 24 soatlik hakaton.",
                "location": "Asosiy bino, aktlar zali",
                "starts_at": now + timedelta(days=14),
                "ends_at": now + timedelta(days=15),
                "xp_reward": 100,
                "capacity": 200,
                "created_by": rector,
            },
        )
        Opportunity.objects.get_or_create(
            title="Yozgi stajirovka: dasturiy ta'minot (demo)",
            defaults={
                "kind": Opportunity.Kind.INTERNSHIP,
                "organization": "Hamkor IT kompaniya (demo)",
                "description": "Python/Django bo'yicha 2 oylik pullik stajirovka.",
                "min_level": 2,
                "deadline": now + timedelta(days=30),
                "created_by": rector,
            },
        )
        self.stdout.write(self.style.SUCCESS("Demo ma'lumotlar yaratildi (parol: demo12345)"))
