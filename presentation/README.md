# ANDTI Talent Hub: taqdimot videosi

16:9 (1920×1080), taxminan 150 soniyali animatsion video, o'zbekcha matnlar, fon musiqasi va ovoz effektlari bilan. Diktor ovozi `audio/ovozlash.py` orqali qo'shiladi.

- `video.html`: videoning o'zi. Brauzerda ochsangiz, animatsiya avtomatik aylanib o'ynaydi.
- `render.js`: sahifani kadrma-kadr suratga olib, MP4 ga yig'adi.
- `assets/`: platforma skrinshotlari, logo va GSAP kutubxonasi.

## MP4 ga yig'ish

Kerak bo'ladi: Node.js, Playwright (`npm i playwright` va `npx playwright install chromium`) va ffmpeg.

```bash
cd presentation
node render.js andti-talent-hub.mp4 30
```

Shrift (Manrope) Google Fonts'dan yuklanadi, shuning uchun internet kerak.

Matn yoki vaqtlarni o'zgartirish uchun `video.html` ichidagi `S` ro'yxati (sahna boshlanish/tugash soniyalari)
va `tl` timeline'idagi animatsiyalarni tahrirlang.

## Ovoz: musiqa, effektlar va diktor

`audio/` papkasida:

- `soundtrack.py`: fon musiqasi va ovoz effektlarini noldan sintez qiladi (tayyor audio ishlatilmaydi,
  mualliflik huquqi muammosi yo'q). `python soundtrack.py soundtrack.wav`, kerak: `numpy`, `scipy`.
- `narration.json`: o'zbekcha diktor matni, har bir gap qaysi soniyada boshlanib, qachongacha sig'ishi kerakligi bilan.
- `ovozlash.py`: Microsoft'ning o'zbekcha neyron ovozi (Madina yoki Sardor) bilan matnni o'qitib, videoga joylaydi.
  Diktor gapirganda musiqa avtomatik pasayadi, qo'shimcha `.srt` subtitr ham chiqadi.

Musiqani videoga qo'shish:

```bash
ffmpeg -i andti-talent-hub.mp4 -i soundtrack.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest ANDTI-Talent-Hub-taqdimot.mp4
```

Diktor ovozini qo'shish (internet kerak):

```bash
pip install edge-tts imageio-ffmpeg
python audio/ovozlash.py --video ANDTI-Talent-Hub-taqdimot.mp4               # Madina (ayol ovozi)
python audio/ovozlash.py --video ANDTI-Talent-Hub-taqdimot.mp4 --ovoz sardor # Sardor (erkak ovozi)
```

Matnni o'zgartirsangiz, har bir gap `start`–`end` oralig'iga sig'ishi kerak (taxminan 14 belgi/soniya).
Sig'masa, skript nutqni 20% gacha tezlashtiradi va ogohlantiradi.

### Internetsiz diktor (qozoqcha neyron ovoz bilan)

O'zbekcha ochiq neyron TTS modeli topilmagani uchun `diktor_offline.py` tovushlari o'zbek tiliga eng yaqin
qozoqcha Piper modelidan foydalanadi. Matn `uz_g2p.py` qoidalari bilan IPA tovushlarga o'giriladi, model esa
shu tovushlarni o'qiydi. Nutq tushunarli, lekin qozoqcha talaffuz sezilib turadi. Haqiqiy o'zbekcha ovoz uchun
yuqoridagi `ovozlash.py` (Microsoft Madina/Sardor) yoki jonli diktor yozuvi afzal.

```bash
pip install numpy onnxruntime imageio-ffmpeg
# Model: vits-piper-kk_KZ-issai-high (ISSAI KazakhTTS, CC-BY-4.0)
curl -LO https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-kk_KZ-issai-high.tar.bz2
tar xjf vits-piper-kk_KZ-issai-high.tar.bz2
python audio/diktor_offline.py --model-dir vits-piper-kk_KZ-issai-high --chiqish diktor.wav \
    --video ANDTI-Talent-Hub-taqdimot.mp4          # --ovoz ayol | ayol2 | ayol3 | ayol4 | erkak | erkak2
```

Ovoz modeli: [ISSAI KazakhTTS](https://github.com/IS2AI/Kazakh_TTS) (CC-BY-4.0), Piper formatida
[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) orqali.
