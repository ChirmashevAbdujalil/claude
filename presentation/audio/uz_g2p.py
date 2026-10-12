"""O'zbekcha (lotin) matnni Piper/VITS modeli tushunadigan IPA tovushlarga o'giradi.

O'zbek yozuvi deyarli fonetik, shuning uchun oddiy qoidalar yetarli. Natija qozoqcha Piper
modeli o'rgangan tovushlar to'plamiga moslangan (masalan, g' -> ʀ, o' -> ɵ, x -> x).
Urg'u o'zbek tilidagidek so'zning oxirgi bo'g'iniga qo'yiladi.
"""

import re

# Maxsus so'zlar: qisqartmalar va chet so'zlar
SPECIAL = {
    "andti": "ˈændeteɪ",
    "talent": "tˈælent",
    "hub": "hˈæb",
    "telegram": "teleɡɾˈæm",
    "telegramda": "teleɡɾæmdˈæ",
}

BACK = {"q", "ʀ", "x"}  # yonida "a" va "i" orqaroq aytiladi
# Unlilar: (oddiy holat, q/g'/x yonida). Qiymatlar Whisper bilan o'lchab tanlangan.
VOWEL_MAP = {"a": ("æ", "ɑ"), "i": ("ɪ", "ə"), "o": ("o", "o"), "u": ("u", "u"), "e": ("e", "e"), "ɵ": ("ɵ", "ɵ")}
STRESS = True

DIGRAPHS = [("o'", "ɵ"), ("g'", "ʀ"), ("sh", "ʃ"), ("ch", "C"), ("ng", "ŋ")]
LETTERS = {
    "a": "a", "b": "b", "d": "d", "e": "e", "f": "f", "g": "ɡ", "h": "h", "i": "i", "j": "J",
    "k": "k", "l": "l", "m": "m", "n": "n", "o": "o", "p": "p", "q": "q", "r": "ɾ", "s": "s",
    "t": "t", "u": "u", "v": "v", "x": "x", "y": "j", "z": "z", "'": "ʔ",
}  # fmt: skip


def _letters(word):
    """So'zni harf-tovushlarga bo'ladi (C = ch, J = j, keyin kengaytiriladi)."""
    out, i = [], 0
    while i < len(word):
        for pair, sound in DIGRAPHS:
            if word.startswith(pair, i):
                # "ng" undoshdan oldin yoki so'z oxirida ŋ, unlidan oldin n+g ham bo'lishi mumkin
                out.append(sound)
                i += len(pair)
                break
        else:
            ch = word[i]
            if ch in LETTERS:
                out.append(LETTERS[ch])
            i += 1
    return out


def _word(word):
    if word in SPECIAL:
        return SPECIAL[word]
    sounds = _letters(word)
    result = []
    for k, s in enumerate(sounds):
        prev = sounds[k - 1] if k else ""
        nxt = sounds[k + 1] if k + 1 < len(sounds) else ""
        near_back = prev in BACK or nxt in BACK
        if s in VOWEL_MAP:
            result.append(VOWEL_MAP[s][1 if near_back else 0])
        elif s == "C":
            result.append("tʃ")
        elif s == "J":
            result.append("dʒ")
        elif s == "ʔ":
            if k and k + 1 < len(sounds):
                result.append("ʔ")
        else:
            result.append(s)
    # Urg'u: oxirgi unlidan oldin
    text = "".join(result)
    vowel_positions = [m.start() for m in re.finditer("[aæɑəɪieouʊɵ]", text)]
    if STRESS and len(vowel_positions) > 1:
        pos = vowel_positions[-1]
        # urg'u belgisini bo'g'in boshiga emas, unlining oldiga qo'yamiz (espeak/piper uslubi)
        text = text[:pos] + "ˈ" + text[pos:]
    return text


def phonemize(text):
    text = text.lower().replace("ʻ", "'").replace("ʼ", "'").replace("‘", "'").replace("’", "'")
    text = text.replace("«", "").replace("»", "").replace('"', "")
    tokens = re.findall(r"[a-z']+|[.,!?:;]", text)
    out = []
    for tok in tokens:
        if tok in ".,!?:;":
            if out:
                out[-1] += tok
            continue
        word = tok.strip("'")
        if word:
            out.append(_word(word))
    return " ".join(out)


def sentences(text):
    """Matnni gaplarga bo'ladi (har biri alohida sintez qilinadi)."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


if __name__ == "__main__":
    import sys

    print(phonemize(" ".join(sys.argv[1:])))
