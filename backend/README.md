# ADTI Talent Hub: backend

Python, Django va Django REST Framework asosidagi API. Veb-ilova va Telegram Mini App shu API bilan ishlaydi.

## Tez ishga tushirish

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # DJANGO_DEBUG=1 qoldiring
python manage.py migrate
python manage.py seed --demo     # nishonlar, ko'nikmalar, mukofotlar va demo ma'lumotlar
python manage.py createsuperuser
python manage.py runserver
```

- API hujjatlari (Swagger): http://localhost:8000/api/docs/
- Admin panel: http://localhost:8000/admin/
- Demo foydalanuvchilar: `demo_student1` … `demo_student8`, `demo_teacher`, `demo_rector` (parol: `demo12345`)

Docker bilan (PostgreSQL bilan birga), repozitoriy ildizida:

```bash
cp backend/.env.example backend/.env   # DJANGO_DEBUG=0 va DJANGO_SECRET_KEY ni to'ldiring
POSTGRES_PASSWORD=maxfiy docker compose up --build
```

## Testlar va sifat tekshiruvi

```bash
pytest                 # barcha testlar
ruff check .           # linter
ruff format .          # formatlash
```

Testlar Claude API'ga murojaat qilmaydi: AI Mentor soxta mijoz bilan tekshiriladi.

## Arxitektura

```
backend/
├── config/            # sozlamalar, URL'lar
└── apps/
    ├── accounts/      # foydalanuvchi, rollar, fakultet, Telegram orqali kirish
    ├── profiles/      # Talent Passport: ko'nikmalar, tasdiqlar, yutuqlar, portfolio
    ├── arena/         # ball iqtisodiyoti: XP, tangalar, darajalar, nishonlar, streak, reyting, liga
    ├── discovery/     # challenge'lar, yechimlar, o'qituvchining «uchqun» belgisi
    ├── projects/      # loyihalar, jamoa, bosqichlar, jamoadosh tavsiyasi
    ├── opportunities/ # grant, vakansiya, stajirovka, mukofotlar do'koni
    ├── community/     # lenta, izohlar, tadbirlar va QR check-in
    ├── insights/      # rektorat va dekanat dashboardi
    └── ai/            # AI Mentor, g'oya tekshiruvchi, karyera maslahatchisi (Claude API)
```

Har bir modulda biznes qoidalari `services.py` faylida jamlangan. View'lar faqat so'rovni qabul qilib, servisni chaqiradi.

### Ball iqtisodiyoti qoidalari

- XP va tangalar faqat `apps/arena/services.py` orqali o'zgaradi. Har bir o'zgarish `PointTransaction` jurnaliga yoziladi.
- Bir manba uchun ball faqat bir marta beriladi: `(foydalanuvchi, sabab, manba)` noyob.
- Kunlik XP limiti bor (`ARENA_DAILY_XP_CAP`). O'qituvchi tasdiqlagan yutuqlar limitga kirmaydi.
- Har 10 XP uchun 2 tanga beriladi. Tangalar mukofotlar do'konida sarflanadi.
- Talaba o'z yutug'i yoki yechimini tasdiqlay olmaydi.

| Harakat | XP |
|---|---|
| Kunlik / haftalik / oylik challenge | 10 / 50 / 300 (o'qituvchi bahosiga qarab) |
| O'qituvchi tasdiqlagan ko'nikma | 30 |
| Tadbirda qatnashish (QR) | tadbirga qarab, odatda 20 |
| Loyiha bosqichini o'tish | har bir faol a'zoga 100 |
| Yutuq (olimpiada, hakaton, maqola, patent...) | 50–600, o'qituvchi o'zgartira oladi |
| 7 kunlik streak | 50 |

## Asosiy API endpoint'lar

Barcha yo'llar `/api/v1/` bilan boshlanadi. Avtorizatsiya: `Authorization: Bearer <access token>`.

| Bo'lim | Endpoint |
|---|---|
| Kirish | `POST auth/telegram/` (Mini App initData), `POST auth/token/`, `POST auth/token/refresh/` |
| Profil | `GET/PATCH me/`, `GET faculties/`, `GET portfolio/<slug>/` (ommaviy) |
| Ko'nikmalar | `GET skills/`, `me/skills/` (CRUD), `GET me/skills/map/`, `POST user-skills/<id>/endorse/` |
| Yutuqlar | `achievements/` (CRUD), `POST achievements/<id>/review/` |
| Arena | `GET arena/me/`, `arena/badges/`, `arena/transactions/`, `arena/leaderboard/?period=week`, `arena/league/` |
| Challenge'lar | `challenges/` (CRUD), `POST challenges/<id>/submit/`, `submissions/`, `POST submissions/<id>/review/`, `talent-flags/` |
| Loyihalar | `projects/` (CRUD), `POST projects/<id>/join/`, `approve/`, `advance/`, `GET projects/<id>/recommendations/` |
| Imkoniyatlar | `opportunities/` (CRUD), `POST opportunities/<id>/apply/`, `me/applications/` |
| Do'kon | `GET rewards/`, `POST rewards/<id>/redeem/`, `me/redemptions/` |
| Hamjamiyat | `posts/`, `POST posts/<id>/like/`, `posts/<id>/comments/`, `events/`, `POST events/<id>/register/`, `GET events/<id>/qr/`, `POST events/check-in/` |
| Statistika | `GET insights/dashboard/` (dekanat, rektorat) |
| AI | `ai/conversations/`, `POST ai/conversations/<id>/messages/`, `GET ai/quota/` |

To'liq ro'yxat, so'rov va javob sxemalari Swagger sahifasida.

## AI Mentor

- Model: `ANTHROPIC_MODEL` (standart `claude-opus-5-5`). Kalit `ANTHROPIC_API_KEY` orqali beriladi.
- Uch rejim: `mentor` (o'quv yo'l xaritasi), `idea_check` (startup g'oyasini tahlil), `career` («Kelajakdagi men»).
- AI'ga talabaning ismi va kontaktlari yuborilmaydi: faqat fakultet, kurs, daraja, ko'nikmalar va tasdiqlangan yutuqlar.
- Tizim ko'rsatmalari keshlanadi (prompt caching). Bu xarajatni kamaytiradi.
- Model so'rovni rad etsa, server tomonidagi zaxira model (`fallbacks: "default"`) ishga tushadi.
- Har bir talaba uchun kunlik xabar limiti bor (`AI_DAILY_MESSAGE_LIMIT`).
