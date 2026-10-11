"""Talaba darajalari. Daraja faqat XP asosida hisoblanadi va hech qachon pasaymaydi."""

LEVELS = [
    (1, "Yangi boshlovchi", 0),
    (2, "Izlanuvchi", 500),
    (3, "Ixtirochi", 2000),
    (4, "Innovator", 5000),
    (5, "Afsona", 12000),
]


def level_for_xp(xp: int) -> dict:
    current = LEVELS[0]
    next_level = None
    for index, level in enumerate(LEVELS):
        if xp >= level[2]:
            current = level
            next_level = LEVELS[index + 1] if index + 1 < len(LEVELS) else None
    number, name, min_xp = current
    if next_level is None:
        progress = 1.0
    else:
        progress = round((xp - min_xp) / (next_level[2] - min_xp), 3)
    return {
        "number": number,
        "name": name,
        "min_xp": min_xp,
        "next_level_xp": next_level[2] if next_level else None,
        "next_level_name": next_level[1] if next_level else None,
        "remaining": next_level[2] - xp if next_level else 0,
        "progress": progress,
    }
