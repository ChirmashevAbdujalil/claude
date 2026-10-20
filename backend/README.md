# ANDTI Talent Hub: backend

Python, Django va Django REST Framework. Ikki qismdan iborat:

- **Veb-interfeys** (Django template'lar): talabalar, o'qituvchilar va rahbariyat uchun to'liq sayt. Telegram Mini App ichida ham ishlaydi.
- **REST API** (`/api/v1/`): mobil ilova va tashqi integratsiyalar uchun.

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

- Sayt: http://localhost:8000/
- API hujjatlari (Swagger): http://localhost:8000/api/docs/
- Admin panel: http://localhost:8000/admin/
- Demo foydalanuvchilar (parol: `demo12345`):
  - `demo_student1`: talaba, loyiha asoschisi, reytingda 1-o'rin
  - `demo_teacher`: o'qituvchi, tekshiruv navbatida yechim va yutuq bor
  - `demo_rector`: rektorat, statistika paneli va admin panel

Docker bilan (PostgreSQL bilan birga), repozitoriy ildizida:

```bash
cp backend/.env.example backend/.env   # DJANGO_DEBUG=0 va DJANGO_SECRET_KEY ni to'ldiring
POSTGRES_PASSWORD=maxfiy docker compose up --build
```

## Fakultetlar va brend

`python manage.py seed` institutning 5 ta fakultetini yaratadi:

| Fakultet | Qisqa nomi |
|---|---|
| Iqtisodiyot va boshqaruv fakulteti | IB |
| Intellektual boshqaruv va kompyuter tizimlari fakulteti | IBKT |
| Qurilish muhandisligi va elektroenergetika fakulteti | QMEE |
| Mexanika va kimyo muhandisligi fakulteti | MKM |
| Avtomobilsozlik va transport fakulteti | AT |

Qisqa nomlar reyting va ro'yxatlarda ko'rinadi, ularni admin panelda o'zgartirish mumkin. Oldingi versiyadagi demo fakultetlar `seed` ishga tushganda haqiqiylariga avtomatik ko'chiriladi.

Logotip fayllari `apps/web/static/web/img/` papkasida. Brend rangi (`#062d3b`) `app.css` faylidagi `--brand` va `--primary` o'zgaruvchilarida.

## Veb-interfeys

| Sahifa | Manzil | Kim uchun |
|---|---|---|
| Landing | `/` | Hamma |
| Ro'yxatdan o'tish | `/register/` | Talabalar o'zlari ro'yxatdan o'tadi (`REGISTRATION_OPEN=0` bilan yopiladi) |
| Boshlang'ich sozlash | `/welcome/` | 3 qadam: fakultet va kurs → ko'nikmalar → birinchi challenge |
| Qanday ball olaman? | `/how-it-works/` | Ball, daraja va nishon qoidalari (koddagi qiymatlardan avtomatik) |
| Bildirishnomalar | `/notifications/` | Saytda 🔔 va Telegram botga xabar |
| Kirish | `/login/` (Telegram Mini App ichida avtomatik) | Hamma |
| Bosh sahifa | `/app/` | Daraja kartasi, bugungi challenge, tadbirlar, loyihalar |
| Challenge'lar | `/challenges/` | Yechim yuborish, kunlik savollar avtomatik tekshiriladi |
| Arena | `/arena/` | Reyting (podium), fakultetlar ligasi, nishonlar, ball tarixi |
| Profil | `/profile/` | Ko'nikmalar radari, yutuqlar, tahrirlash |
| Rezyume | `/profile/resume/` | AI yozgan xulosa (o'zbekcha/inglizcha) va QR kodli PDF rezyume. Portfolio'dan ham yuklanadi: `/u/<slug>/resume.pdf` |
| Portfolio | `/u/<slug>/` | Ommaviy sahifa. O'qituvchi shu yerda ko'nikmani tasdiqlaydi va «uchqun» belgisi qo'yadi |
| Loyihalar | `/projects/` | Yaratish, qo'shilish, bosqichlar, jamoadosh tavsiyasi |
| Imkoniyatlar | `/opportunities/` | Ariza topshirish. Hamkorlar e'lon joylaydi |
| Tangalarim | `/coins/` | Tanga nima beradi, qanday yig'iladi, nimaga sarflanadi, keyingi maqsad va savol-javob |
| Do'kon | `/shop/` | Tangalarni sovg'aga almashtirish. Homiy sovg'alarida homiy logotipi chiqadi |
| Homiylar | `/homiylar/` | Ommaviy sahifa: homiylar, ular bergan sovg'alar va «Homiy bo'ling» taklifi (`SPONSOR_CONTACT`) |
| Lenta | `/feed/` | Postlar, layk, izohlar |
| Tadbirlar | `/events/` | Ro'yxatdan o'tish, tashkilotchi uchun QR kod, `/events/check-in/` |
| AI Mentor | `/ai/` | Uch rejimli chat |
| Tekshiruv | `/review/` | O'qituvchi: yechim va yutuqlarni baholash |
| Statistika | `/insights/` | Dekanat va rektorat |
| Natijalar | `/natijalar/` | Ommaviy sahifa (login shart emas): o'sish va haftalik faollik grafiklari, qaytib keluvchilar, fakultetlar qamrovi, ball manbalari va QR kod. Faqat umumlashgan raqamlar, 5 daqiqa keshlanadi. Pitch va hakamlar uchun |

Dizayn tizimi bitta faylda: `apps/web/static/web/css/app.css`. Unda ranglar, tugmalar, kartalar va formalar bor, build bosqichi kerak emas. Sayt mobil qurilmalarga moslashgan, yorug' va qorong'i rejimni qo'llab-quvvatlaydi. Telegram ichida ochilganda Telegram mavzusiga moslashadi.

Telegram Mini App ulash: @BotFather'da bot yarating, `TELEGRAM_BOT_TOKEN` ni `.env` ga yozing va botning Menu Button havolasini saytingiz manziliga (`https://.../app/`) qo'ying.

## Talabaga yo'l ko'rsatish

- **Keyingi qadam**: bosh sahifada talabaning holatiga qarab bitta asosiy tavsiya chiqadi (ko'nikma qo'shish, kunlik savol, xavf ostidagi streak, jamoa so'rovlari, tadbir). Mantiq `apps/web/guidance.py` faylida.
- **Profil to'liqligi**: 6 bandli ro'yxat va foiz.
- **Holat chizig'i**: yechim, yutuq va arizada «Yuborildi → Tekshirilmoqda → Natija».

## SaaS: bir nechta OTM uchun

Platforma bitta serverda bir nechta OTMga xizmat qiladi. Har bir OTMning foydalanuvchilari, fakultetlari,
topshiriqlari, loyihalari, tadbirlari, do'koni va statistikasi boshqalaridan to'liq ajratilgan.

- **Qaysi OTM?** So'rov manzilidan aniqlanadi: `tatu.talenthub.uz` (subdomen) yoki OTMning o'z domeni.
  `SAAS_BASE_DOMAIN` bo'sh bo'lsa, platforma bitta OTM (`DEFAULT_INSTITUTION_*`) uchun ishlaydi.
- **Ajratish qanday ishlaydi?** `apps/tenants/` ichida: middleware joriy OTMni o'rnatadi, modellar
  menejeri (`TenantManager`) har bir so'rovni shu OTM bilan avtomatik cheklaydi. Kod biror joyda filtrni
  unutsa ham boshqa OTM ma'lumoti ko'rinmaydi. Login, portfolio manzili va Telegram ID butun platforma bo'yicha noyob.
- **Tariflar** (`apps/tenants/plans.py`): Pilot (bepul, 300 talaba), Standart, Premium. Tarif talabalar limiti va
  imkoniyatlarni belgilaydi: AI Mentor, AI rezyume, homiylar, o'z logotipi va ranglari, OTMlararo liga.
  Narxlar taxminiy, ularni o'zingiz o'zgartirasiz.

| Sahifa | Manzil | Kim uchun |
|---|---|---|
| Taqdimot, tariflar, ulanish arizasi | `/saas/` | OTMlar (ommaviy) |
| Platforma paneli: OTMlar, MRR, arizalarni tasdiqlash | `/platform/` | Platforma egasi (superuser) |
| OTM sozlamalari: logotip, ranglar, fakultetlar, tarif | `/settings/otm/` | Rektorat / OTM administratori |
| OTMlararo liga | `/arena/otm-ligasi/` | Hamma |

Yangi OTM ulashning uch yo'li bor, hammasida OTM bilan birga uning administratori (rektorat) hisobi yaratiladi
va parol bir marta ko'rsatiladi:

1. **Admin panel:** `/admin/` → OTMlar → «OTM qo'shish». Pilot tarifida muddat bo'sh qoldirilsa, 90 kun qo'yiladi.
   Parol yo'qolsa, ro'yxatda OTMni belgilab «Administrator parolini yangilash» amalini tanlang.
2. **Ariza:** OTM `/saas/` sahifasidan ariza qoldiradi, siz `/platform/` yoki admin paneldan tasdiqlaysiz.
3. **Buyruq:**

```bash
python manage.py create_institution "Toshkent axborot texnologiyalari universiteti" TATU --slug tatu --plan standart
python manage.py seed --demo --institution tatu   # ixtiyoriy: demo ma'lumotlar
```

Lokal sinov: `http://tatu.localhost:8000` (Chrome va Firefox `*.localhost` ni o'z kompyuteringizga yo'naltiradi).

Serverga joylashtirish: DNS'da `*.talenthub.uz` yozuvini serverga yo'naltiring, `.env` da
`SAAS_BASE_DOMAIN=talenthub.uz` va `DJANGO_ALLOWED_HOSTS=.talenthub.uz,talenthub.uz` qiling, wildcard SSL sertifikati oling.
Telegram bot hozircha butun platforma uchun bitta.

### Obuna to'lovi: Payme va Click

OTM rektorati `/settings/otm/` sahifasida tarif va muddatni (1, 3, 6 yoki 12 oy; yillik to'lovda 2 oy bepul)
tanlab hisob yaratadi va Payme yoki Click orqali to'laydi. To'lov tasdiqlangach, tarif va `paid_until` avtomatik
yangilanadi, muddat joriy obuna tugaydigan kundan boshlab uzaytiriladi. To'lov qaytarilsa (Payme `CancelTransaction`),
OTMning oldingi tarifi va muddati tiklanadi.

| Tizim | Kabinetga yoziladigan manzil | `.env` |
|---|---|---|
| Payme (Merchant API) | `https://<domen>/billing/payme/`, hisob maydoni: `order_id` | `PAYME_MERCHANT_ID`, `PAYME_KEY`, `PAYME_TEST` |
| Click (SHOP API) | Prepare: `https://<domen>/billing/click/prepare/`, Complete: `https://<domen>/billing/click/complete/` | `CLICK_SERVICE_ID`, `CLICK_MERCHANT_ID`, `CLICK_SECRET_KEY` |

Kodlar `apps/billing/` ichida: `payme.py` (JSON-RPC, 12 soatlik timeout, idempotent), `click.py` (MD5 imzo tekshiruvi),
`services.py` (hisob, to'lov, qaytarish). Barcha to'lovlar `/admin/` va `/platform/` panelida ko'rinadi.
Ishga tushirishdan oldin Payme sinov kassasida (test.paycom.uz) kabinetdagi barcha sinov ssenariylaridan o'ting.

Muddati o'tgan OTMlarni 3 kunlik imtiyozdan keyin to'xtatish uchun buyruqni har kuni ishga tushiring (cron):

```bash
python manage.py check_subscriptions            # --dry-run: faqat ro'yxatni ko'rsatadi
```

## Iqtidorli talabalar bilan ishlash (`apps/talent/`)

Rektorat topshirig'i asosida: iqtidorli talabalar bilan ishlashni tartibga solish, samarali yo'lga qo'yish va har
bir talabani iqtidoriga qarab to'g'ri yo'naltirish.

| Modul | Manzil | Kim uchun |
|---|---|---|
| **Iqtidorlar reyestri**: holat zanjiri, filtrlar, «E'tiborga loyiq» tavsiyalari | `/iqtidorlar/` | Dekanat (o'z fakulteti), rektorat |
| **Iqtidor kartasi**: mentor biriktirish, rivojlanish rejasi, natijalar, diagnostika | `/iqtidorlar/<id>/` | Rahbariyat, mentor, talabaning o'zi |
| **Shogirdlarim**: biriktirilgan talabalar, reja va kechikkan maqsadlar | `/shogirdlarim/` | O'qituvchi (mentor) |
| **Mening yo'lim**: yo'nalish, mentor, reja, mos imkoniyatlar | `/mening-yolim/` | Talaba |
| **Iqtidor diagnostikasi**: 10 savol + platformadagi faollik | `/mening-yolim/test/` | Talaba |
| **Hisobot** (PDF, Excel/CSV): fakultetlar, yo'nalishlar, mentorlar, natijalar | `/iqtidorlar/hisobot/` | Rektorat |

- **Holat zanjiri:** Aniqlangan → Mentor biriktirilgan → Rivojlanmoqda (rejasi bor) → Natijaga erishgan
  (olimpiada, hakaton, maqola yoki patent tasdiqlangan). Holat haqiqiy ishdan avtomatik hisoblanadi.
- **Avtomatik reyestr:** o'qituvchi «uchqun» belgisini qo'ysa yoki olimpiada, hakaton, maqola, patent tasdiqlansa,
  talaba reyestrga o'zi tushadi.
- **Yo'naltirish:** diagnostika yo'nalishni javoblar (70%) va ko'nikma, yutuq, yechimlar (30%) asosida aniqlaydi.
  Yangi imkoniyat e'lon qilinganda yo'nalishi mos talabalarga sayt va Telegram orqali xabar boradi;
  imkoniyatlar ro'yxatida «🎯 Sizga mos» belgisi chiqadi.
- **Eslatmalar:** muddati 3 kun qolgan va o'tgan maqsadlar, 14 kundan beri mentorsiz qolgan iqtidorlar
  (dushanba kunlari dekanga). Har kuni ishga tushiring:

```bash
python manage.py talent_reminders
```

## So'rovnomalar (`apps/surveys/`)

Google Forms kabi so'rovnoma tizimi: rahbariyat maxsus konstruktorda so'rovnoma tuzadi, talabalar havola yoki QR kod
orqali javob beradi. Asosiy vazifasi: butun institut bo'yicha iqtidorli talabalarni ommaviy ro'yxatga olish.

| Sahifa | Manzil | Kim uchun |
|---|---|---|
| **Ro'yxat va shablonlar**: «Iqtidorlarni ro'yxatga olish», «Tadbir bo'yicha fikr», bo'sh so'rovnoma | `/sorovnomalar/` | Rahbariyat; talaba ochiq so'rovnomalarni ko'radi |
| **Konstruktor**: savol qo'shish, tartiblash, nusxalash, majburiy belgisi, sozlamalar, e'lon qilish | `/sorovnomalar/<id>/tahrir/` | Muallif, rektorat va admin |
| **Ommaviy to'ldirish sahifasi** (login shart emas, telefonga moslashgan) | `/s/<kalit>/` | Har qanday talaba |
| **Natijalar**: grafiklar, fakultet va kurs kesimi, javoblar jadvali, filtrlar | `/sorovnomalar/<id>/natijalar/` | Rahbariyat (dekan boshqalar tuzgan so'rovnomada o'z fakultetini ko'radi) |
| **Excel (.xlsx)**: umumiy natija grafiklar bilan, barcha javoblar (filtr, qotirilgan sarlavha), kesimlar, klublar; CSV ham bor | `.../natijalar.xlsx`, `.../eksport.csv` | Rahbariyat |
| **QR plakat** (A4, chop etish uchun) | `.../plakat/` | Rahbariyat |

- **12 xil savol turi:** qisqa va batafsil javob, bitta va bir nechta variant, ro'yxatdan tanlash, baholash shkalasi
  (1–10), raqam, sana, elektron pochta, telefon, iqtidor yo'nalishi va bo'lim sarlavhasi. Variantlarda «Boshqa» bor.
- **Iqtidorlar reyestriga bir bosishda:** javob bergan talabalarni belgilab reyestrga qo'shasiz, yo'nalishi
  «Iqtidor yo'nalishi» savolidan olinadi (manba: «So'rovnoma»).
- **Kim javob beradi:** havolasi bor har qanday talaba, ro'yxatdan o'tmasdan va profilsiz. Talaba ma'lumotlari
  (F.I.Sh., fakultet, kurs, guruh, telefon) formada so'raladi; platformaga kirgan talabada profildan to'ldiriladi.
- **Guruh majburiy va bir xil formatda:** `K-21-05` (harf(lar), chiziqcha, ikki raqam, chiziqcha, ikki raqam).
  Talaba yozayotganda avtomatik formatlanadi: «k2105», «К 21 05» → `K-21-05`. Natijalarda guruh bo'yicha filtr va
  kesishma jadvalda «Guruh» kesimi bor.
- **Takrorlanmaslik:** har kim bir marta javob beradi (akkaunt yoki brauzer bo'yicha); botlar uchun tuzoq maydon.
- **Avtomatik akkaunt:** platformada akkaunti yo'q talaba so'rovnomani yuborishi bilan unga talaba akkaunti
  ochiladi: login ism-familiyadan (kirill ham lotinga o'giriladi), parol tasodifiy (masalan `kmr7-4tqx`). Shu talaba
  boshqa so'rovnomani to'ldirsa, telefon yoki ism-fakultet-kurs bo'yicha o'sha akkauntga bog'lanadi.
- **Login va parollar** (`/akkauntlar/`): jadval, filtrlar, nusxalash, «Yangi parol»; Word'da ikki xil fayl:
  fakultetlar bo'yicha jadval («Oldim (imzo)» ustuni bilan) va qirqib beriladigan kartochkalar. Dekan faqat
  o'z fakultetini ko'radi, har bir yuklab olish harakatlar jurnaliga yoziladi.
- **Xavfsizlik:** boshlang'ich parol faqat talaba birinchi marta kirguncha saqlanadi; birinchi kirishda talaba
  o'z parolini o'rnatadi va boshlang'ich parol ro'yxatdan o'chadi.
- **Fakultetlar bo'yicha ro'yxatga olish** (natijalar → «Umumiy natija» tepasida): har bir fakultetdan nechta talaba
  javob bergan, akkaunt ochilgan, tizimga kirgan va bugun qo'shilgan; reyting (🥇🥈🥉) va hali javob bermagan
  fakultetlar ogohlantirishi. OTM sozlamalarida fakultet kontingenti kiritilsa, qamrov foizi ham ko'rinadi
  (masalan, 120 / 800 · 15%). Excel faylda alohida «Fakultetlar» varag'i.
- **Tyutorlar** (`/settings/otm/tyutorlar/`): har bir tyutor o'z fakultetiga biriktiriladi (ANDTIning 25 tyutori
  migratsiyada avtomatik qo'shiladi). Ro'yxatni qo'lda to'ldirish yoki Word jadvalidan («Fakultet nomi»,
  «Lavozimi», «F.I.Sh» ustunlari) yuklash mumkin. Talaba so'rovnomada fakultetini tanlagach, faqat shu fakultet
  tyutorlari ichidan o'z tyutorini belgilaydi (fakultetda tyutor bo'lsa, majburiy). Natijalarda «Tyutorlar
  kesimida» bo'limi chiqadi: har bir tyutor guruhidan nechta talaba javob bergani, eng faol tyutor va javobi yo'q
  tyutorlar. Shuningdek tyutor filtri, kesishma jadvalda «Tyutor» o'lchovi va Excel'da «Tyutorlar» varag'i bor.
- **Tyutorlar havolalari** (`/sorovnomalar/<id>/tyutorlar/`): har bir tyutorga shaxsiy havola (`/s/<token>/?t=<id>`),
  QR kod, tayyor Telegram xabari va o'z QR plakati. Talaba shu havolani ochsa, fakultet va tyutor oldindan
  tanlangan bo'ladi.
- **Fayl yuklash savoli** (konstruktorda «📎 Fayl yuklash»): qaysi turlar qabul qilinishi (PDF, rasm, Word, Excel,
  PowerPoint), fayllar soni (1–10) va bitta fayl hajmi (2–20 MB) belgilanadi. Talaba faylni tanlaydi, sudrab
  tashlaydi yoki telefonda suratga oladi; yuklanish foizi ko'rinib turadi. Fayl turi nomidan emas, ichidan
  tekshiriladi. Fayllar `PRIVATE_MEDIA_ROOT` papkasida (standart: `backend/private_media/`) saqlanadi: ularga
  `/media/` orqali kirib bo'lmaydi, faqat rahbariyat ko'radi (dekan o'z fakultetinikini). Natijalarda fayllar
  statistikasi va ko'rinishlari, javob sahifasida «Ko'rish/Yuklab olish», shuningdek fakultet → talaba papkalari
  bilan ZIP yuklab olish bor (filtrlar hisobga olinadi, jurnalga yoziladi). Bitta yuborishda jami 100 MB gacha,
  bir manzildan soatiga 120 tagacha fayl. Server oldida nginx bo'lsa, `client_max_body_size 105m;` qo'ying.
  Docker'da fayllar `private_media` volume'ida saqlanadi.
- **Login-parollar tyutorlar kesimida:** akkauntda talabaning tyutori saqlanadi (so'nggi javobi bo'yicha).
  «Login va parollar» sahifasida tyutor filtri bor, «Word: tyutorlar bo'yicha» faylida esa har bir tyutorga
  alohida varaq chiqadi: tyutor o'z guruhlaridagi talabalarga login va parollarni tarqatadi.
- **Chuqur tahlil** (natijalar → «🔎 Tahlil»): avtomatik xulosalar, 21 kunlik javoblar dinamikasi, javoblar
  to'liqligi va kesishma jadval (istalgan savol × fakultet, kurs yoki boshqa savol; issiqlik rangi va ★ eng kuchli
  variant). Grafikdagi istalgan variantni bossangiz, butun sahifa, javoblar ro'yxati va Excel faqat shu javobni
  berganlar bo'yicha qayta hisoblanadi; bir nechta shartni birlashtirish mumkin.
- **Klublar** (natijalar → «👥 Klublar»): tanlangan savol (masalan, iqtidor yo'nalishi yoki ko'nikma) bo'yicha bir xil
  javob bergan talabalar shu javob nomi bilan klubga yig'iladi. Sardor avtomatik taklif qilinadi, mentor va Telegram
  guruh biriktiriladi, a'zolarga xabar yuboriladi, ro'yxat Excel'da yuklanadi, hammasi bir bosishda iqtidorlar
  reyestriga qo'shiladi. A'zolar o'z klub sahifasini (`/klub/<id>/`) va «Mening klublarim»ni ko'radi.
- **Rag'bat:** platformaga kirib javob bergan talabaga XP (bir marta). E'lon qilishda barcha talabalarga
  bildirishnoma yuborish mumkin.

## Harakatlar jurnali (audit log)

Kim, qachon, qayerdan (IP) va nimani o'zgartirgani `apps/audit/` da avtomatik yoziladi. Rektorat uni
`/settings/otm/jurnal/` sahifasida ko'radi: filtrlar, CSV (Excel) eksport va yaxlitlikni tekshirish tugmasi bilan.
Platforma egasi barcha OTMlar jurnalini `/admin/` da ko'radi.

- **Nima yoziladi:** xodimlarning (o'qituvchi, dekanat, rektorat, administrator) muhim o'zgarishlari, ya'ni OTM
  sozlamalari, foydalanuvchilar, rollar, bloklash, parol almashtirish, topshiriqlar, yechim baholari, yutuqlar,
  qo'lda berilgan ball, do'kon, homiylar, tadbirlar va to'lovlar. Har o'zgarishda eski va yangi qiymat saqlanadi.
  Tizimga kirish, chiqish va muvaffaqiyatsiz kirish urinishlari ham yoziladi. Payme, Click va obuna nazorati
  «Tizim» nomidan yoziladi.
- **Nima yozilmaydi:** talabalarning kundalik harakatlari va parollar (faqat «parol o'zgartirildi» degan fakt).
- **O'zgartirib bo'lmaydi:** yozuvni tahrirlash va o'chirish kodda taqiqlangan. Har yozuv OTM bo'yicha oldingisining
  SHA-256 xeshi bilan zanjirlanadi, shuning uchun bazada qo'lda o'zgartirish ham aniqlanadi:

```bash
python manage.py verify_audit_log   # butun bo'lsa: "Jurnal butun: N ta yozuv tekshirildi"
```

Server proksi (nginx) ortida bo'lsa, haqiqiy IP uchun `.env` ga `AUDIT_TRUST_X_FORWARDED_FOR=1` yozing.

## Bildirishnomalar va Telegram bot

Muhim hodisalarda (yechim tekshirildi, yutuq tasdiqlandi, nishon olindi, jamoaga qabul qilindi, izoh yozildi) bildirishnoma saytda saqlanadi. Talaba Telegram orqali kirgan bo'lsa, botga ham xabar boradi.

Botni ulash (sayt `https` manzilda ishlayotgan bo'lishi kerak):

1. @BotFather'da bot yarating va tokenni oling.
2. `.env` fayliga yozing: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` (uzun tasodifiy satr), `SITE_URL=https://...`
3. `python manage.py telegram_setup`: webhook va «Platforma» menyu tugmasi sozlanadi.

## AI tekshiruv yordamchisi

O'qituvchi tekshiruv sahifasida «AI'dan baho va izoh taklifini olish» tugmasini bosadi. AI baho, izoh, kuchli tomonlar va yaxshilash yo'llarini taklif qiladi, ular formaga oldindan yoziladi. Yakuniy qarorni o'qituvchi qabul qiladi. AI'ga talabaning ismi yuborilmaydi.

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
    ├── ai/            # AI Mentor, g'oya tekshiruvchi, karyera maslahatchisi, tekshiruv yordamchisi (Claude API)
    ├── notifications/ # bildirishnomalar va Telegram bot
    ├── surveys/       # so'rovnomalar: konstruktor, ommaviy to'ldirish, natijalar, iqtidorlarni ro'yxatga olish
    └── web/           # veb-interfeys: template'lar, dizayn tizimi, view'lar
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
