# ANDTI Talent Hub

Andijon davlat texnika instituti iqtidorli talabalarini bir joyga jamlovchi, ularni kashf qiluvchi va rivojlantiruvchi platforma.

**Kashf qilish → Rivojlantirish → Imkoniyatga ulash**

## Tarkib

- [`backend/`](backend/README.md): Python, Django REST API. Ishga tushirish, arxitektura va endpoint'lar shu yerda
- [`docs/LOYIHA_STRUKTURASI.md`](docs/LOYIHA_STRUKTURASI.md): modullar, rollar, ball iqtisodiyoti, arxitektura, yo'l xaritasi

## Tez boshlash

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
python manage.py migrate && python manage.py seed --demo
python manage.py runserver   # http://localhost:8000/api/docs/
```
