"""Tarif rejalari. Narxlar taxminiy: platforma egasi o'z bozoriga qarab o'zgartiradi."""

PLANS = {
    "pilot": {
        "name": "Pilot",
        "price": 0,
        "students": 300,
        "features": {"league"},
        "note": "3 oylik bepul sinov: 1-2 fakultet uchun",
    },
    "standart": {
        "name": "Standart",
        "price": 1_500_000,
        "students": 3000,
        "features": {"league", "sponsors", "branding", "resume_ai"},
        "note": "Butun OTM uchun: homiylar, o'z logotipi va ranglari, AI rezyume",
    },
    "premium": {
        "name": "Premium",
        "price": 3_500_000,
        "students": None,
        "features": {"league", "sponsors", "branding", "resume_ai", "ai"},
        "note": "Cheklovsiz talabalar, AI Mentor va AI tekshiruv yordamchisi",
    },
}

FEATURE_LABELS = {
    "league": "OTMlararo liga",
    "sponsors": "Homiylar va homiy sovg'alari",
    "branding": "O'z logotipi va brend ranglari",
    "resume_ai": "AI rezyume",
    "ai": "AI Mentor va AI tekshiruv yordamchisi",
}

CHOICES = [(key, plan["name"]) for key, plan in PLANS.items()]
