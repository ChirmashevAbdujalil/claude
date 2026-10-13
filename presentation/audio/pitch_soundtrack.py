"""Pitch videosi (pitch.html) uchun fon musiqasi va ovoz effektlari.

Tovushlar soundtrack.py dagi sintezatorlardan olinadi; bu yerda faqat yangi vaqt jadvali.
Ishlatish:  python pitch_soundtrack.py [chiqish.wav]
"""

import sys

import numpy as np
from scipy.io import wavfile
from soundtrack import (
    BAR,
    BEAT,
    CHORDS,
    SR,
    bandpass,
    bell,
    coin,
    decay,
    env_adsr,
    impact,
    lowpass,
    note,
    pad_voice,
    pop,
    riser,
    rng,
    shimmer,
    stereo,
    success,
    tick,
    whoosh,
)

DURATION = 178.0
# pitch.html dagi sahnalar bilan bir xil
SCENE_ENDS = [7, 17, 29, 40, 53, 66, 80, 91, 102, 112, 125, 135, 149, 158, 168]
HEADERS = [17.4, 29.4, 40.4, 53.4, 66.4, 80.4, 91.4, 102.4, 112.4, 125.4, 135.4, 149.4, 158.4]


def music():
    total = int(DURATION * SR)
    track = np.zeros((total, 2))
    chord_len = BAR * 2
    t0, i = 0.0, 0
    while t0 < DURATION:
        chord = CHORDS[i % len(CHORDS)]
        n = int((chord_len + 1.2) * SR)
        mono = sum(pad_voice(note(nm), n) for nm in chord) * env_adsr(n, 1.0, 1.4)
        mono = lowpass(mono, 1400) * 0.05
        start = int(t0 * SR)
        end = min(start + n, total)
        track[start:end] += np.stack([mono, np.roll(mono, 240)], axis=1)[: end - start]
        t0 += chord_len
        i += 1

    # Arpedjio: rektor so'zidan keyin boshlanadi
    t, step = 17.0, 0
    while t < DURATION - 6:
        chord = CHORDS[int(t // chord_len) % len(CHORDS)]
        pattern = [chord[1], chord[2], chord[3], chord[2]]
        f = note(pattern[step % 4]) * 2
        n = int(0.5 * SR)
        tt = np.arange(n) / SR
        pluck = (np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(4 * np.pi * f * tt)) * decay(n, 0.16)
        start = int(t * SR)
        end = min(start + n, total)
        track[start:end] += stereo(pluck * 0.042, pan=0.35 if step % 2 else -0.35)[: end - start]
        t += BEAT / 2
        step += 1

    # Ritm: yechimdan yo'l xaritasigacha
    beat_t, k = 29.0, 0
    while beat_t < 166:
        if k % 2 == 0:
            n = int(0.3 * SR)
            tt = np.arange(n) / SR
            f = 45 + 70 * np.exp(-tt / 0.03)
            kick = np.sin(2 * np.pi * np.cumsum(f) / SR) * decay(n, 0.12) * 0.2
            start = int(beat_t * SR)
            track[start : start + n] += stereo(kick)[: total - start]
        n = int(0.06 * SR)
        hat = bandpass(rng.standard_normal(n), 7000, 14000) * decay(n, 0.012) * 0.055
        start = int((beat_t + BEAT / 2) * SR)
        if start + n < total:
            track[start : start + n] += stereo(hat, pan=0.2)
        beat_t += BEAT
        k += 1

    curve = np.interp(
        np.arange(total) / SR,
        [0, 3, 7, 16.5, 29, 164, 168, 173, DURATION],
        [0.0, 0.7, 0.55, 0.7, 1.0, 1.0, 0.85, 0.6, 0.0],
    )
    return track * curve[:, None]


def buzz(gain=0.2):
    """Xato signali: past chastotali qisqa titrash."""
    n = int(0.5 * SR)
    tt = np.arange(n) / SR
    tone = np.sign(np.sin(2 * np.pi * 110 * tt)) * 0.5 + np.sin(2 * np.pi * 220 * tt) * 0.5
    return stereo(lowpass(tone, 900) * env_adsr(n, 0.01, 0.15) * gain)


def events():
    ev = []
    add = lambda t, sound, gain=1.0: ev.append((t, sound, gain))  # noqa: E731

    for end in SCENE_ENDS:
        add(end - 0.45, whoosh(), 0.85)
    for t in HEADERS:
        add(t, pop(520, 0.2))

    # 1. Kirish
    add(0.35, impact())
    add(0.9, shimmer(0.16, 16, 1.6))
    add(1.5, whoosh(0.7, 0.6, -0.6, 0.25))
    add(3.1, bell(note("E6"), 1.5, 0.12))

    # 2. Rektor so'zi
    add(7.3, bell(note("A4"), 2.5, 0.14))
    add(7.6, riser(5.0, 0.05))
    add(12.6, bell(note("E5"), 1.6, 0.1, pan=-0.4))

    # 3. Muammo
    for i in range(3):
        add(17.9 + i * 0.2, pop(700 + i * 50, 0.2, 0.6))
        add(18.8 + i * 1.6, pop(560, 0.28, -0.5 + i * 0.5))
        add(19.6 + i * 1.6, buzz(0.16))
    add(24.4, impact(0.3))

    # 4. Yechim
    add(30.4, riser(5.2, 0.08))
    for i, s in enumerate(["C5", "E5", "G5", "C6"]):
        add(30.3 + i * 1.4, bell(note(s), 1.3, 0.2, pan=-0.6 + i * 0.4))
        add(30.3 + i * 1.4, pop(420 + i * 60, 0.22))
    for i in range(4):
        add(36.3 + i * 0.2, tick(1800 + i * 200, 0.12))

    # 5. Diagnostika
    add(41.0, whoosh(0.8, 0.8, 0.2, 0.25))
    for i in range(3):
        add(41.6 + i * 0.3, tick(1600 + i * 300, 0.12, -0.5))
    add(45.6, whoosh(0.6, 0.6, 0.9, 0.2))
    for k in range(18):
        add(46.4 + k * 0.1, tick(1400 + k * 60, 0.05, 0.5))
    add(48.8, success(0.28))
    add(48.85, coin(0.22))

    # 6. Reyestr
    for i, s in enumerate(["C5", "E5", "G5", "C6"]):
        add(55.8 + i * 1.1, bell(note(s), 1.0, 0.16, pan=-0.6 + i * 0.4))
    for i in range(3):
        add(58.6 + i * 0.6, pop(600 + i * 60, 0.24, -0.6))
    add(59.2, whoosh(0.9, 0.9, 0.3, 0.25))

    # 7. Mentor va reja: bildirishnomalar
    add(67.0, whoosh(0.9, 0.9, 0.3, 0.25))
    for i in range(3):
        add(70.4 + i * 2.2, pop(880, 0.26, -0.6))
        add(70.45 + i * 2.2, bell(note("A6"), 0.5, 0.08, pan=-0.6))

    # 8. Moslash
    add(81.0, whoosh(0.7, -0.8, -0.3, 0.22))
    for i in range(6):
        add(81.8 + i * 0.12, pop(500 + i * 40, 0.16, -0.2 + i * 0.12))
    add(83.8, whoosh(1.2, -0.4, 0.5, 0.2))
    for i, s in enumerate(["E6", "G6", "C7"]):
        add(84.7 + i * 0.25, bell(note(s), 0.7, 0.12, pan=0.2 + i * 0.2))
    add(85.8, whoosh(0.9, 0.9, 0.5, 0.25))
    add(86.8, success(0.26))
    add(86.85, shimmer(0.08, 10, 0.6))

    # 9. Motivatsiya
    for i in range(3):
        add(92.4 + i * 0.7, pop(620 + i * 40, 0.24, -0.6))
    add(92.6, whoosh(0.9, 0.9, 0.3, 0.22))
    add(95.0, coin(0.3))
    add(96.3, coin(0.26))
    add(97.6, success(0.26))
    add(97.65, shimmer(0.1, 12, 0.8))

    # 10. AI
    for i, s in enumerate(["G5", "C6", "E6"]):
        add(103.2 + i * 1.4, pop(560 + i * 60, 0.24, -0.6 + i * 0.6))
        add(103.25 + i * 1.4, bell(note(s), 0.8, 0.1, pan=-0.6 + i * 0.6))

    # 11. Hisobot
    add(113.2, whoosh(0.8, 0.6, 0.2, 0.22))
    for i in range(4):
        add(113.6 + i * 0.5, tick(2000 + i * 150, 0.14, -0.6))
    add(117.6, whoosh(1.0, 0.9, 0.5, 0.28))
    add(118.6, pop(380, 0.2, 0.6))
    add(119.2, coin(0.24))

    # 12. Ishonch: zanjir, buzish urinishi, tasdiq
    for i in range(5):
        add(126.0 + i * 0.35, pop(500 + i * 50, 0.2, -0.8 + i * 0.4))
        add(126.4 + i * 0.35, tick(2400, 0.08, -0.8 + i * 0.4))
    add(129.2, buzz(0.3))
    add(129.6, buzz(0.2))
    add(130.2, success(0.28))
    for i in range(4):
        add(131.4 + i * 0.2, pop(600 + i * 40, 0.18, -0.6 + i * 0.4))

    # 13. SaaS
    add(136.2, whoosh(0.8, 0.9, 0.3, 0.22))
    add(137.2, whoosh(0.8, 0.9, 0.5, 0.22))
    for i in range(3):
        add(140.6 + i * 0.5, pop(540 + i * 60, 0.24, -0.6 + i * 0.6))
    add(142.4, success(0.22))
    add(144.4, coin(0.26))
    add(144.8, coin(0.24))

    # 14. MVP
    for k in range(16):
        add(150.2 + k * 0.1, tick(1500 + k * 70, 0.06))
    add(151.9, impact(0.3))
    for i in range(10):
        add(152.6 + i * 0.12, bell(note(["C5", "D5", "E5", "G5", "A5"][i % 5]) * (2 if i > 4 else 1), 0.5, 0.05))

    # 15. Yo'l xaritasi
    add(159.0, riser(5.0, 0.1))
    for i, s in enumerate(["C5", "E5", "G5", "C6"]):
        add(159.1 + i * 1.2, bell(note(s), 1.3, 0.22, pan=-0.75 + i * 0.5))

    # 16. Yakun
    add(168.25, impact(0.6))
    add(168.6, shimmer(0.14, 18, 1.8))
    add(169.2, bell(note("C6"), 2.5, 0.12))
    add(169.25, bell(note("G6"), 2.5, 0.08))
    add(170.6, success(0.24))
    return ev


def build():
    total = int(DURATION * SR)
    mix = music()
    for t, sound, gain in events():
        start = int(t * SR)
        end = min(start + len(sound), total)
        mix[start:end] += sound[: end - start] * gain
    mix = np.tanh(mix * 1.3) / np.tanh(1.3)
    mix *= 0.89 / max(np.abs(mix).max(), 1e-9)
    fade = int(0.5 * SR)
    mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return mix


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "pitch_soundtrack.wav"
    wavfile.write(out, SR, (build() * 32767).astype(np.int16))
    print("Tayyor:", out)
