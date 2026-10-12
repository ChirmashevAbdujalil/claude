# ADTI Talent Hub: taqdimot videosi

16:9 (1920×1080), taxminan 116 soniyali animatsion video. Ovozsiz, o'zbekcha matnlar bilan.

- `video.html`: videoning o'zi. Brauzerda ochsangiz, animatsiya avtomatik aylanib o'ynaydi.
- `render.js`: sahifani kadrma-kadr suratga olib, MP4 ga yig'adi.
- `assets/`: platforma skrinshotlari, logo va GSAP kutubxonasi.

## MP4 ga yig'ish

Kerak bo'ladi: Node.js, Playwright (`npm i playwright` va `npx playwright install chromium`) va ffmpeg.

```bash
cd presentation
node render.js adti-talent-hub.mp4 30
```

Shrift (Manrope) Google Fonts'dan yuklanadi, shuning uchun internet kerak.

Matn yoki vaqtlarni o'zgartirish uchun `video.html` ichidagi `S` ro'yxati (sahna boshlanish/tugash soniyalari)
va `tl` timeline'idagi animatsiyalarni tahrirlang.
