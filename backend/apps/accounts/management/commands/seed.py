"""Boshlang'ich ma'lumotlar: nishonlar, ko'nikmalar, mukofotlar va (ixtiyoriy) demo ma'lumotlar.

python manage.py seed           # faqat ma'lumotnomalar
python manage.py seed --demo    # + demo fakultetlar, talabalar, challenge va tadbirlar
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Faculty, User
from apps.arena import services as arena
from apps.arena.models import Badge
from apps.community.models import Event, Post
from apps.discovery import services as discovery_services
from apps.discovery.models import Challenge, TalentFlag
from apps.opportunities import services as opportunity_services
from apps.opportunities.models import Opportunity, Redemption, Reward, Sponsor
from apps.profiles.models import Achievement, Skill, UserSkill
from apps.projects import services as project_services
from apps.projects.models import Project, ProjectMember
from apps.surveys import services as survey_services
from apps.surveys.models import Survey
from apps.talent import diagnostics as talent_diagnostics
from apps.talent import services as talent_services
from apps.talent.models import DevelopmentGoal, TalentProfile
from apps.talent.tracks import Track
from apps.tenants.context import activate, default_institution
from apps.tenants.models import Institution

BADGES = [
    ("welcome", "Xush kelibsiz", "Boshlang'ich sozlashni yakunladingiz", "👋", 20),
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
    ("Oshxona taloni", "Institut oshxonasida bir martalik tushlik", 50, 100, "🍽️"),
    ("Texnik kitob", "Kutubxonadan tanlangan kitob sovg'a sifatida", 150, 30, "📚"),
    ("Talent Hub futbolkasi", "Platformaning brendli futbolkasi", 300, 50, "👕"),
    ("Onlayn kurs sertifikati", "Hamkor platformada pullik kurs", 800, 10, "🎓"),
    ("Rektor bilan choy", "Rektor bilan shaxsiy uchrashuv", 1500, 5, "☕"),
]

DEMO_STUDENTS = [
    (
        "Aziza",
        "Rahimova",
        "Robototexnika va IoT ishqibozi. Aqlli qishloq xo'jaligi ustida ishlayman.",
        [("Python", 4), ("Elektronika", 4), ("Robototexnika", 5)],
        2340,
    ),
    (
        "Jasur",
        "Toshmatov",
        "Elektronika muhandisi, Arduino va datchiklar bilan ishlayman.",
        [("Elektronika", 5), ("C++", 3)],
        1850,
    ),
    (
        "Madina",
        "Yusupova",
        "Shahar infratuzilmasi va ma'lumotlar tahlili.",
        [("Ma'lumotlar tahlili", 4), ("Python", 3), ("Ingliz tili", 4)],
        1320,
    ),
    ("Bekzod", "Aliyev", "Tarmoq texnologiyalari va kiberxavfsizlik.", [("Kiberxavfsizlik", 4), ("Python", 2)], 980),
    (
        "Dilnoza",
        "Qodirova",
        "Matematik modellashtirish, olimpiada ishtirokchisi.",
        [("Matematik modellashtirish", 5), ("Ilmiy maqola yozish", 3)],
        760,
    ),
    (
        "Sardor",
        "Ergashev",
        "Avtomobil dizayni va 3D modellashtirish.",
        [("3D modellashtirish", 4), ("AutoCAD", 4)],
        540,
    ),
    ("Nilufar", "Saidova", "UI/UX dizayner, mobil ilovalar.", [("UI/UX dizayn", 4), ("Grafik dizayn", 3)], 310),
    ("Otabek", "Nazarov", "Energetika va quyosh panellari.", [("Energetika", 3)], 120),
]

# Andijon davlat texnika instituti fakultetlari (qisqa nomlarni admin panelda o'zgartirish mumkin)
FACULTIES = [
    ("Iqtisodiyot va boshqaruv fakulteti", "IB"),
    ("Intellektual boshqaruv va kompyuter tizimlari fakulteti", "IBKT"),
    ("Qurilish muhandisligi va elektroenergetika fakulteti", "QMEE"),
    ("Mexanika va kimyo muhandisligi fakulteti", "MKM"),
    ("Avtomobilsozlik va transport fakulteti", "AT"),
]

# Boshqa OTMlar uchun demo fakultetlar
GENERIC_FACULTIES = [
    ("Axborot texnologiyalari fakulteti (demo)", "AT"),
    ("Muhandislik fakulteti (demo)", "MF"),
    ("Iqtisodiyot fakulteti (demo)", "IF"),
]

# Oldingi versiyadagi demo fakultetlar → haqiqiy fakultet (qisqa nomi bo'yicha)
LEGACY_DEMO_FACULTIES = {"KI": "IBKT", "EN": "QMEE", "MSH": "MKM", "AT": "AT"}


class Command(BaseCommand):
    help = "Boshlang'ich ma'lumotlarni yuklaydi"

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true", help="Demo fakultet, foydalanuvchi va kontent yaratish")
        parser.add_argument(
            "--institution",
            default=settings.DEFAULT_INSTITUTION_SLUG,
            help="Qaysi OTM uchun (manzili, masalan: tatu). Standart: asosiy OTM",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        slug = options["institution"]
        institution = (
            default_institution()
            if slug == settings.DEFAULT_INSTITUTION_SLUG
            else Institution.objects.filter(slug=slug).first()
        )
        if institution is None:
            raise CommandError(
                f"«{slug}» manzilli OTM topilmadi. Avval admin paneldan yoki create_institution bilan yarating."
            )
        # Nishonlar va ko'nikmalar barcha OTMlar uchun umumiy
        for code, name, description, icon, bonus in BADGES:
            Badge.objects.update_or_create(
                code=code, defaults={"name": name, "description": description, "icon": icon, "xp_bonus": bonus}
            )
        for category, names in SKILLS.items():
            for name in names:
                Skill.objects.get_or_create(name=name, defaults={"category": category})
        with activate(institution):
            self._institution_data(institution, options["demo"])

    def _institution_data(self, institution, demo):
        self.institution = institution
        self.prefix = "demo" if institution.is_default else institution.slug
        for name, description, price, stock, emoji in REWARDS:
            reward, created = Reward.objects.get_or_create(
                name=name, defaults={"description": description, "price": price, "stock": stock, "emoji": emoji}
            )
            if not created and reward.emoji == "🎁":
                Reward.objects.filter(pk=reward.pk).update(emoji=emoji)
        self.stdout.write(
            self.style.SUCCESS(
                f"{institution.short_name}: nishonlar {len(BADGES)}, ko'nikmalar {Skill.objects.count()}, "
                f"mukofotlar {Reward.objects.count()}"
            )
        )

        if institution.is_default:
            self._faculties()
        elif demo and not Faculty.objects.exists():
            for name, short in GENERIC_FACULTIES:
                Faculty.objects.create(name=name, short_name=short)
        if demo:
            self._demo()

    def _faculties(self):
        """Haqiqiy fakultetlarni yaratadi; eski demo fakultetlarni ularga ko'chiradi."""
        names = dict((short, name) for name, short in FACULTIES)
        for legacy in Faculty.objects.filter(name__endswith="(demo)"):
            target_short = LEGACY_DEMO_FACULTIES.get(legacy.short_name)
            if target_short is None:
                continue
            target = Faculty.objects.filter(short_name=target_short).exclude(pk=legacy.pk).first()
            if target is None:
                # Shu fakultetni o'zini haqiqiy nomga o'zgartiramiz: barcha bog'lanishlar saqlanadi
                legacy.name, legacy.short_name = names[target_short], target_short
                legacy.save()
                continue
            for model in (User, Challenge):
                model.objects.filter(faculty=legacy).update(faculty=target)
            legacy.delete()
        for name, short in FACULTIES:
            faculty = Faculty.objects.filter(short_name=short).first() or Faculty.objects.filter(name=name).first()
            if faculty is None:
                Faculty.objects.create(name=name, short_name=short)
            elif faculty.name != name or faculty.short_name != short:
                faculty.name, faculty.short_name = name, short
                faculty.save()
        self.stdout.write(self.style.SUCCESS(f"Fakultetlar: {Faculty.objects.count()}"))

    def _demo(self):
        if self.institution.is_default:
            faculties = [Faculty.objects.get(short_name=short) for _, short in FACULTIES]
        else:
            faculties = list(Faculty.objects.all()) or [Faculty.objects.create(name="Umumiy fakultet", short_name="UF")]
        prefix = self.prefix
        teacher, created = User.objects.get_or_create(
            username=f"{prefix}_teacher",
            defaults={
                "first_name": "Demo",
                "last_name": "O'qituvchi",
                "role": User.Role.TEACHER,
                "onboarded_at": timezone.now(),
                "faculty": faculties[0],
            },
        )
        if created:
            teacher.set_password("demo12345")
            teacher.save()
        rector, created = User.objects.get_or_create(
            username=f"{prefix}_rector",
            defaults={
                "first_name": "Demo",
                "last_name": "Rektorat",
                "role": User.Role.RECTOR,
                "onboarded_at": timezone.now(),
                "is_staff": True,
            },
        )
        if created:
            rector.set_password("demo12345")
            rector.save()
        students = []
        for index, (first, last, bio, skills, xp) in enumerate(DEMO_STUDENTS, start=1):
            student, created = User.objects.get_or_create(
                username=f"{prefix}_student{index}",
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "bio": bio,
                    "faculty": faculties[index % len(faculties)],
                    "course": (index % 4) + 1,
                    "portfolio_slug": f"{prefix}-student-{index}",
                    "onboarded_at": timezone.now(),
                },
            )
            students.append(student)
            if not created:
                continue
            student.set_password("demo12345")
            student.save()
            for name, level in skills:
                UserSkill.objects.get_or_create(
                    user=student, skill=Skill.objects.get(name=name), defaults={"level": level}
                )
            arena.award(student, arena.Reason.MANUAL, xp, note="Demo ball")
            today = timezone.localdate()
            for offset in range(index % 5 + 1, 0, -1):
                arena.touch_streak(student, today - timedelta(days=offset - 1))

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
        self._demo_activity(teacher, students)
        self._demo_sponsors(students)
        self._demo_talent(teacher, rector, students)
        self._demo_surveys(rector, students, faculties)
        self.stdout.write(self.style.SUCCESS("Demo ma'lumotlar yaratildi (parol: demo12345)"))

    def _demo_talent(self, teacher, rector, students):
        """Iqtidorlar reyestri: to'rt xil holatdagi talabalar, mentor, reja va diagnostika."""
        if len(students) < 4 or DevelopmentGoal.objects.filter(title__startswith="Respublika dasturlash").exists():
            return
        today = timezone.localdate()
        # Holat zanjiri to'liq ko'rinishi uchun: natijasi hali yo'q talabalar birinchi
        fresh = [s for s in students if not talent_services.results([s.pk]).exists()]
        ordered = fresh + [s for s in students if s not in fresh]
        aziza, jasur, madina, bekzod = ordered[:4]

        def answers_for(track):
            chosen = {}
            for key, _, options in talent_diagnostics.QUESTIONS:
                chosen[key] = max(options, key=lambda option: option[2].get(track, 0))[0]
            return chosen

        for student, track in ((aziza, Track.IT), (jasur, Track.INVENTION), (madina, Track.RESEARCH)):
            talent_services.save_diagnostic(student, answers_for(track))

        profile, _ = talent_services.ensure_profile(
            aziza, source=TalentProfile.Source.FLAG, track=Track.IT, by=teacher,
            note="Murakkab algoritmik masalalarni mustaqil yechadi",
        )  # fmt: skip
        talent_services.assign_mentor(profile, teacher, by=rector)
        for title, kind, days, status, progress in [
            ("Respublika dasturlash olimpiadasiga tayyorlanish", "olympiad", 20, "in_progress", 60),
            ("GitHub'da portfolio loyihasini e'lon qilish", "project", -10, "done", 100),
            ("IELTS 6.5 sertifikati", "certificate", 75, "planned", 10),
        ]:
            goal = DevelopmentGoal(profile=profile, title=title, kind=kind, due_date=today + timedelta(days=days),
                                   status=status, progress=progress)  # fmt: skip
            goal.mentor_comment = "Haftalik uchrashuvda ko'rib chiqamiz"
            talent_services.save_goal(goal, by=teacher)

        note = "Aqlli sug'orish qurilmasi prototipini yasagan"
        profile, _ = talent_services.ensure_profile(
            jasur, source=TalentProfile.Source.FLAG, track=Track.INVENTION, by=teacher, note=note
        )
        talent_services.assign_mentor(profile, teacher, by=rector)
        talent_services.save_goal(
            DevelopmentGoal(profile=profile, title="Ixtiroga patent arizasini topshirish", kind="patent",
                            due_date=today - timedelta(days=5), status="in_progress", progress=40),
            by=teacher,
        )  # fmt: skip
        Achievement.objects.get_or_create(
            user=jasur, title="«Yosh ixtirochilar» viloyat tanlovi g'olibi (demo)",
            defaults={"kind": Achievement.Kind.PATENT, "achieved_on": today - timedelta(days=12),
                      "status": Achievement.Status.APPROVED, "reviewed_by": teacher},
        )  # fmt: skip

        talent_services.ensure_profile(madina, source=TalentProfile.Source.RATING, track=Track.RESEARCH, by=rector)
        profile, _ = talent_services.ensure_profile(bekzod, source=TalentProfile.Source.MANUAL, track=Track.OLYMPIAD,
                                                    by=rector)  # fmt: skip
        talent_services.assign_mentor(profile, teacher, by=rector)
        Opportunity.objects.filter(title__endswith="(demo)", tracks=[]).update(tracks=[Track.IT, Track.INVENTION])

    def _demo_surveys(self, rector, students, faculties):
        """Iqtidorlarni ro'yxatga olish so'rovnomasi: platformadagi va anonim javoblar bilan."""
        title = "Iqtidorli talabalarni ro'yxatga olish (demo)"
        if Survey.objects.filter(title=title).exists():
            return
        survey = survey_services.create_survey(rector, "census")
        survey.title = title
        survey.closes_at = timezone.now() + timedelta(days=21)
        survey.save()
        survey_services.publish(survey)
        by_title = {q.title: q for q in survey.questions.all()}
        track_q = next(q for q in by_title.values() if q.kind == "track")
        level_q = by_title["Eng yuqori natijangiz qaysi darajada?"]
        did_q = by_title["Qaysi faoliyatlarda qatnashgansiz?"]
        scale_q = by_title["O'z salohiyatingizni qanday baholaysiz?"]
        mentor_q = by_title["Mentor (ustoz) bilan ishlashni xohlaysizmi?"]
        story_q = by_title["Eng katta yutug'ingiz yoki loyihangiz haqida yozing"]
        demo = [
            (Track.IT, "Respublika", ["Hakaton yoki IT tanlov", "Fan olimpiadasi"], 5, "Ha, albatta",
             "Viloyat hakatonida «Aqlli navbat» ilovasi bilan 2-o'rin oldim"),
            (Track.INVENTION, "Viloyat", ["Ixtiro yoki patent"], 4, "Ha, albatta",
             "Quyosh panelli sug'orish qurilmasi prototipini yasadim"),
            (Track.RESEARCH, "OTM ichida", ["Ilmiy maqola yoki tezis"], 4, "Ha, imkon bo'lsa",
             "Kafedra konferensiyasida tezis bilan chiqdim"),
            (Track.STARTUP, "Hali qatnashmaganman", ["Startap tanlovi"], 3, "Ha, albatta",
             "Talabalar uchun ijara xonalari platformasi g'oyasi bor"),
            (Track.OLYMPIAD, "Respublika", ["Fan olimpiadasi"], 5, "Ha, imkon bo'lsa",
             "Matematika fan olimpiadasida respublika bosqichi 3-o'rin"),
            (Track.CREATIVE, "OTM ichida", ["Ijodiy tanlov"], 3, "Hozircha yo'q", ""),
        ]  # fmt: skip
        anonymous = ["Sardorbek Qodirov", "Nilufar Ergasheva"]
        people = [(s, s.get_full_name() or s.username) for s in students[:4]] + [(None, n) for n in anonymous]
        rows = zip(people[: len(demo)], demo[: len(people)], strict=True)
        for index, ((student, name), (track, level, did, score, mentor, story)) in enumerate(rows):
            answers = {str(track_q.pk): track, str(level_q.pk): level, str(did_q.pk): did,
                       str(scale_q.pk): score, str(mentor_q.pk): mentor}  # fmt: skip
            if story:
                answers[str(story_q.pk)] = story
            survey_services.submit(
                survey,
                answers=answers,
                identity={"full_name": name, "faculty": faculties[index % len(faculties)], "course": 1 + index % 4,
                          "group": f"{210 + index}-21", "phone": f"+998 90 12{index} 45 67"},
                user=student,
                browser_key=f"demo-{index}" if student is None else "",
            )  # fmt: skip

    def _demo_sponsors(self, students):
        """Demo homiylar: nomlari to'qima, «(demo)» belgisi bilan. Haqiqiy homiylar admin paneldan qo'shiladi."""
        demo = [
            (
                "TexnoSoft (demo)",
                "texnosoft-demo",
                "Dasturiy ta'minot kompaniyasi: kitob va kurslar orqali o'qishni rag'batlantiradi.",
                ["Texnik kitob", "Onlayn kurs sertifikati"],
            ),
            (
                "Andijon Mexanika Zavodi (demo)",
                "mexanika-zavodi-demo",
                "Ishlab chiqarish korxonasi: faol talabalarga brendli kiyim va tushlik sovg'a qiladi.",
                ["Talent Hub futbolkasi", "Oshxona taloni"],
            ),
        ]
        for order, (name, slug, description, rewards) in enumerate(demo):
            if not self.institution.is_default:
                slug = f"{self.institution.slug}-{slug}"
            sponsor, _ = Sponsor.objects.get_or_create(
                slug=slug, defaults={"name": name, "description": description, "order": order}
            )
            Reward.objects.filter(name__in=rewards, sponsor__isnull=True).update(sponsor=sponsor)
        # Homiylar sahifasi bo'sh ko'rinmasligi uchun bir nechta talaba homiy sovg'asini oladi
        if not Redemption.objects.exists():
            for student, reward_name in [
                (students[2], "Oshxona taloni"),
                (students[4], "Oshxona taloni"),
                (students[1], "Texnik kitob"),
            ]:
                reward = Reward.objects.filter(name=reward_name).first()
                if reward:
                    try:
                        opportunity_services.redeem(reward, student)
                    except opportunity_services.OpportunityError:
                        pass

    def _demo_activity(self, teacher, students):
        """Loyiha, postlar, yutuqlar va tekshiruv navbati: sahifalar bo'sh ko'rinmasligi uchun."""
        if Project.objects.filter(title="Aqlli issiqxona").exists():
            return
        leader, partner, solver, achiever = students[0], students[1], students[2], students[3]
        project = project_services.create_project(
            leader,
            title="Aqlli issiqxona",
            description="Harorat, namlik va sug'orishni avtomatik boshqaradigan IoT tizimi. "
            "Datchiklar ma'lumoti Telegram bot orqali fermerga yuboriladi.",
            problem="Andijon fermerlari issiqxonada qo'lda nazorat qiladi: hosilning 20% gacha qismi yo'qoladi.",
            skills_needed=list(Skill.objects.filter(name__in=["Elektronika", "Python", "UI/UX dizayn"])),
        )
        ProjectMember.objects.create(project=project, user=partner, role="Elektronika muhandisi", status="active")
        project_services.advance_stage(project, leader)

        Achievement.objects.create(
            user=leader,
            kind=Achievement.Kind.HACKATHON,
            title="AI Hackathon Andijon 2026: 1-o'rin",
            achieved_on=timezone.localdate() - timedelta(days=40),
            proof_url="https://example.com/diplom",
            status=Achievement.Status.APPROVED,
            reviewed_by=teacher,
            xp_awarded=300,
        )
        Achievement.objects.create(
            user=achiever,
            kind=Achievement.Kind.CERTIFICATE,
            title="Cisco CCNA sertifikati",
            achieved_on=timezone.localdate() - timedelta(days=10),
            proof_url="https://example.com/ccna",
        )
        weekly = Challenge.objects.filter(kind=Challenge.Kind.WEEKLY).first()
        if weekly:
            discovery_services.submit(
                weekly,
                solver,
                answer="Har bir to'xtash joyiga ultratovush datchigi, LoRaWAN orqali markaziy serverga, "
                "natija xaritada real vaqtda ko'rsatiladi.",
            )
        for author, text in [
            (leader, "Aqlli issiqxonamiz prototip bosqichiga chiqdi! 🌱 Datchiklar 3 kundan beri uzluksiz ishlayapti."),
            (partner, "Arduino uchun namlik datchigini kalibrlashni o'rgandim. Kimga kerak bo'lsa yordam beraman 🔧"),
            (students[4], "Respublika matematika olimpiadasida 2-o'rin! 🥈 Ustozimga katta rahmat."),
        ]:
            Post.objects.create(author=author, text=text, project=project if author == leader else None)
        TalentFlag.objects.get_or_create(
            student=leader,
            flagged_by=teacher,
            area=Skill.Category.ENGINEERING,
            defaults={"note": "Laboratoriya ishida mustaqil ravishda yangi sxema taklif qildi."},
        )
