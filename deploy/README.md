# iqtidorasti.uz ni ahost.uz serveriga joylash

Loyiha ikki xil hostingda ishlaydi. Qaysi biri sizda ekanini ahost.uz kabinetidan bilasiz:

| | **A. VPS (tavsiya)** | **B. Oddiy hosting (cPanel)** |
|---|---|---|
| Nima | Alohida server, `root` huquqi, Ubuntu | Umumiy server, cPanel paneli, «Setup Python App» |
| Baza | PostgreSQL | MySQL (yoki SQLite) |
| Katta fayl yuklash, ko'p talaba | Muammosiz | Hosting cheklovlariga bog'liq |
| O'rnatish | Bitta skript: `install_vps.sh` | Panel orqali, qo'lda (20–30 daqiqa) |

1000+ talaba bir vaqtda so'rovnoma to'ldirsa, **VPS** (kamida 2 GB RAM, 2 yadro) ishonchliroq.

---

## 0. Domen (ikkala holatda ham)

Domen boshqaruv panelida (iqtidorasti.uz qayerdan olingan bo'lsa) DNS yozuvlari:

| Turi | Nomi | Qiymati |
|---|---|---|
| A | `@` (iqtidorasti.uz) | serveringiz IP manzili |
| A | `www` | serveringiz IP manzili |

Yoki domen NS yozuvlarini ahost.uz bergan nameserver'larga yo'naltiring. DNS 15 daqiqadan 24 soatgacha tarqaladi.
Tekshirish: `ping iqtidorasti.uz` serveringiz IP sini ko'rsatishi kerak.

---

## A. VPS (Ubuntu 22.04 yoki 24.04)

1. Serverga ulaning: `ssh root@SERVER_IP`
2. Skriptni yuklab, ishga tushiring (EMAIL — SSL sertifikati uchun):
   ```bash
   apt-get update && apt-get install -y git
   git clone --branch claude/salom-dasturchi-startuper-48z19p https://github.com/ChirmashevAbdujalil/claude.git /root/claude
   EMAIL=siz@pochta.uz bash /root/claude/deploy/install_vps.sh
   ```
   Repozitoriy yopiq (private) bo'lsa, GitHub'da token yarating va
   `REPO=https://TOKEN@github.com/ChirmashevAbdujalil/claude.git` qilib bering. Yoki `claude.bundle` faylini serverga
   yuklab, `REPO=/root/claude.bundle` deb ishga tushiring.
3. Skript o'zi bajaradi:
   - Python, PostgreSQL, nginx va certbot'ni o'rnatadi;
   - `/srv/iqtidorasti` papkasiga kodni ko'chiradi;
   - `.env` faylini yaratadi: maxfiy kalit va baza paroli tasodifiy, faqat shu serverda saqlanadi;
   - baza, migratsiya, statik fayllar va boshlang'ich ma'lumotlarni (fakultetlar, tyutorlar) tayyorlaydi;
   - gunicorn'ni tizim xizmati (systemd) qilib, server qayta yonganda o'zi ishga tushadigan qiladi;
   - nginx va SSL'ni (https, www → asosiy domenga yo'naltirish) sozlaydi;
   - har kuni 03:30 da baza va fayllarning zaxira nusxasini oladi (14 kun saqlanadi).
4. Administrator (rektorat) akkauntini yarating:
   ```bash
   cd /srv/iqtidorasti/app/backend
   sudo -u iqtidor /srv/iqtidorasti/venv/bin/python manage.py createsuperuser
   ```
5. `https://iqtidorasti.uz/login/` ga kiring:
   - **OTM sozlamalari:** logotip, fakultetlar soni va mas'ul shaxs blokini tekshiring;
   - **Tyutorlar:** tyutorlarga login oching;
   - **So'rovnomalar → Yangi:** «🎯 «ANDTI TALENT»» shablonidan so'rovnoma yarating.

**Yangilash** (yangi versiya chiqqanda): `sudo bash /srv/iqtidorasti/app/deploy/update.sh`
(avval zaxira nusxa oladi, keyin kod, migratsiya, statik fayllar va qayta ishga tushirish).

**Foydali buyruqlar:**

| Nima | Buyruq |
|---|---|
| Sayt holati | `systemctl status iqtidorasti` |
| Jurnal (xatolar) | `journalctl -u iqtidorasti -n 100` yoki `/srv/iqtidorasti/logs/django.log` |
| Qayta ishga tushirish | `systemctl restart iqtidorasti` |
| Zaxira nusxalar | `/srv/iqtidorasti/backups/` |
| Bazani tiklash | `sudo -u postgres pg_restore -c -d iqtidorasti FAYL.dump` |

---

## B. Oddiy hosting (cPanel, «Setup Python App»)

> Talab: Python **3.10 yoki yangiroq**. Panelda faqat 3.9 bo'lsa, Django 5 ishlamaydi: VPS kerak bo'ladi.

1. **Domen va SSL.** cPanel → *Domains*: `iqtidorasti.uz` qo'shing. *SSL/TLS Status* → *Run AutoSSL*. *Domains* →
   *Force HTTPS Redirect* ni yoqing.
2. **Kod.**
   - *Git Version Control* bo'lsa: repozitoriyni `~/iqtidorasti` ga klonlang.
   - Bo'lmasa: *File Manager* orqali `claude-kod.zip` ni yuklab, oching.
   - Kerakli papka: `~/iqtidorasti/backend`.
3. **Baza.**
   - *MySQL Databases*: baza va foydalanuvchi yarating, foydalanuvchiga **ALL PRIVILEGES** bering.
   - Masalan: `user_iqtidor` bazasi, `user_iqtidor` foydalanuvchisi.
4. **Python ilova.** *Setup Python App* → *Create Application*:
   - Python version: 3.10+ (eng yangisi);
   - Application root: `iqtidorasti/backend`;
   - Application URL: `iqtidorasti.uz`;
   - Application startup file: `passenger_wsgi.py`, Entry point: `application`.
5. **Kutubxonalar.** Panel ko'rsatgan `source .../activate && cd ...` buyrug'ini *Terminal*ga nusxalang, keyin:
   ```bash
   pip install -r requirements.txt PyMySQL
   ```
6. **`.env` fayli.**
   - `backend` papkasida `deploy/env.production.example` dan nusxa olib, `.env` deb saqlang.
   - To'ldiring: `DJANGO_SECRET_KEY`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`.
   - `POSTGRES_DB` qatorini **bo'sh** qoldiring.
   - `AUDIT_TRUST_X_FORWARDED_FOR=0` qiling.
7. **Bazani tayyorlash** (o'sha terminalda):
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py seed
   python manage.py createsuperuser
   ```
8. *Setup Python App* → **Restart**. `https://iqtidorasti.uz` ni oching.

**Yangilash:**
- Kodni yangilang: *Git Version Control* → *Pull* yoki yangi zip.
- Terminalda: `pip install -r requirements.txt`, `python manage.py migrate`, `python manage.py collectstatic --noinput`.
- Panelda **Restart**.

**Zaxira:** cPanel → *Backup* (baza va `media`, `private_media` papkalari).

---

## Muhim eslatmalar

- **`.env` faylini hech kimga yubormang va GitHub'ga qo'ymang**: unda maxfiy kalit va baza paroli bor.
- **Mahalliy ma'lumotlar ko'chmaydi.** Kompyuteringizdagi `db.sqlite3` da sinov ma'lumotlari (demo javoblar,
  sinov akkauntlari) bor, serverda toza bazadan boshlash to'g'ri.
- **«ANDTI TALENT» so'rovnomasi va tyutorlar.** Tyutorlar `seed` bilan o'zi qo'shiladi. So'rovnomani esa yangi
  bazada shablondan bir bosishda yaratasiz.
- **Telegram bot** (ixtiyoriy): `.env` ga `TELEGRAM_BOT_TOKEN` va `TELEGRAM_WEBHOOK_SECRET` yozib,
  `python manage.py telegram_setup` ni ishga tushiring.
- **HTTPS ishlayotganiga ishonch hosil qilgach,** `.env` ga `DJANGO_HSTS_SECONDS=31536000` qo'shib qayta ishga
  tushiring: brauzerlar saytni doim https orqali ochadi.
- **Fayl yuklash cheklovi.** So'rovnomaga fayl yuklashda bitta yuborish 100 MB gacha. VPS'da nginx shunga
  sozlangan; cPanel'da hosting cheklovi kichikroq bo'lishi mumkin.
