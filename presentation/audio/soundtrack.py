"""Taqdimot videosi uchun fon musiqasi va ovoz effektlarini noldan sintez qiladi.

Hech qanday tayyor audio fayl ishlatilmaydi: hamma tovush matematik usulda yaratiladi,
shuning uchun mualliflik huquqi muammosi yo'q.

Ishlatish:  python soundtrack.py [chiqish.wav]
Kerak:      numpy, scipy
"""

import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

SR = 48_000
DURATION = 116.0
rng = np.random.default_rng(7)


def silence(seconds):
    return np.zeros((int(seconds * SR), 2))


def env_adsr(n, attack, release):
    """Yumshoq kirish va chiqish konverti (soniyalarda)."""
    e = np.ones(n)
    a, r = min(int(attack * SR), n), min(int(release * SR), n)
    if a:
        e[:a] = np.linspace(0, 1, a)
    if r:
        e[n - r :] *= np.linspace(1, 0, r)
    return e


def decay(n, seconds):
    return np.exp(-np.arange(n) / (seconds * SR))


def stereo(mono, pan=0.0):
    left, right = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    return np.stack([mono * left, mono * right], axis=1)


def lowpass(x, cutoff, order=2):
    return sosfilt(butter(order, cutoff, "low", fs=SR, output="sos"), x, axis=0)


def bandpass(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], "band", fs=SR, output="sos"), x, axis=0)


def note(name):
    """'A4' -> chastota."""
    names = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}
    base, octave = name[:-1], int(name[-1])
    semis = names[base[0]] + (1 if base.endswith("#") else 0) + (octave - 4) * 12
    return 440.0 * 2 ** (semis / 12)


# ---------------------------------------------------------------- ovoz effektlari


def whoosh(length=0.9, pan_from=-0.8, pan_to=0.8, gain=0.5):
    n = int(length * SR)
    noise = rng.standard_normal(n)
    low, high = lowpass(noise, 700), bandpass(noise, 1500, 6000)
    t = np.linspace(0, 1, n)
    mix = low * (1 - t) + high * t * 0.8
    shape = np.sin(np.pi * np.clip(t / 0.95, 0, 1)) ** 2
    mono = mix * shape * gain
    pan = np.linspace(pan_from, pan_to, n)
    left, right = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    return np.stack([mono * left, mono * right], axis=1)


def pop(freq=700, gain=0.35, pan=0.0):
    n = int(0.18 * SR)
    t = np.arange(n) / SR
    f = freq * (1 + 0.8 * np.exp(-t / 0.012))
    phase = 2 * np.pi * np.cumsum(f) / SR
    mono = np.sin(phase) * decay(n, 0.045) * gain
    return stereo(mono, pan)


def tick(freq=2200, gain=0.18, pan=0.0):
    n = int(0.05 * SR)
    t = np.arange(n) / SR
    mono = np.sin(2 * np.pi * freq * t) * decay(n, 0.008) * gain
    return stereo(mono, pan)


def bell(freq, length=1.2, gain=0.25, pan=0.0):
    n = int(length * SR)
    t = np.arange(n) / SR
    partials = [(1, 1.0, 0.6), (2.0, 0.45, 0.35), (2.76, 0.25, 0.25), (5.4, 0.12, 0.1)]
    mono = sum(a * np.sin(2 * np.pi * freq * r * t) * decay(n, d) for r, a, d in partials)
    mono *= env_adsr(n, 0.002, 0.05) * gain
    return stereo(mono, pan)


def coin(gain=0.3):
    out = silence(0.7)
    for i, f in enumerate([note("B5"), note("E6")]):
        n = int(0.6 * SR)
        t = np.arange(n) / SR
        tone = (np.sin(2 * np.pi * f * t) + 0.3 * np.sign(np.sin(2 * np.pi * f * t))) * decay(n, 0.18 if i else 0.05)
        start = int(i * 0.08 * SR)
        out[start : start + n] += stereo(tone * gain * 0.6)[: len(out) - start]
    return out


def success(gain=0.28):
    out = silence(1.6)
    for i, name in enumerate(["C6", "E6", "G6", "C7"]):
        b = bell(note(name), 1.2, gain, pan=-0.3 + i * 0.2)
        start = int(i * 0.07 * SR)
        out[start : start + len(b)] += b
    return out


def shimmer(gain=0.18, count=14, spread=1.2):
    out = silence(spread + 1.5)
    scale = ["C6", "D6", "E6", "G6", "A6", "C7", "D7", "E7"]
    for i in range(count):
        b = bell(note(scale[rng.integers(len(scale))]), 1.0, gain * rng.uniform(0.5, 1), pan=rng.uniform(-0.8, 0.8))
        start = int(rng.uniform(0, spread) * SR)
        out[start : start + len(b)] += b[: len(out) - start]
    return out


def impact(gain=0.7):
    n = int(2.2 * SR)
    t = np.arange(n) / SR
    f = 40 + 60 * np.exp(-t / 0.08)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * decay(n, 0.5)
    hit = lowpass(rng.standard_normal(n), 1800) * decay(n, 0.06) * 0.5
    tail = lowpass(rng.standard_normal(n), 900) * decay(n, 0.9) * 0.08
    return stereo((body + hit + tail) * gain)


def riser(length=5.0, gain=0.12):
    n = int(length * SR)
    t = np.linspace(0, 1, n)
    f = 220 * 2 ** (2 * t)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.5 * np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR)
    air = bandpass(rng.standard_normal(n), 2000, 8000) * 0.3
    mono = (tone * 0.5 + air) * t**2 * env_adsr(n, 0.01, 0.25) * gain
    return stereo(mono)


# ---------------------------------------------------------------- musiqa

BPM = 100
BEAT = 60 / BPM
BAR = BEAT * 4
# vi - IV - I - V (C major): ko'tarinki, ilhomlantiruvchi ketma-ketlik
CHORDS = [
    ["A2", "A3", "C4", "E4"],
    ["F2", "F3", "A3", "C4"],
    ["C3", "G3", "C4", "E4"],
    ["G2", "G3", "B3", "D4"],
]


def pad_voice(freq, n):
    t = np.arange(n) / SR
    out = np.zeros(n)
    for detune in (-0.12, 0.0, 0.12):
        f = freq * 2 ** (detune / 12)
        for h, a in ((1, 1.0), (2, 0.35), (3, 0.15), (4, 0.06)):
            out += a * np.sin(2 * np.pi * f * h * t + rng.uniform(0, 6.28))
    return out / 3


def music():
    total = int(DURATION * SR)
    track = np.zeros((total, 2))
    chord_len = BAR * 2

    # Pad: har bir akkord 2 taktdan, bir-biriga silliq o'tadi
    t0, i = 0.0, 0
    while t0 < DURATION:
        chord = CHORDS[i % len(CHORDS)]
        n = int((chord_len + 1.2) * SR)
        mono = sum(pad_voice(note(nm), n) for nm in chord) * env_adsr(n, 1.0, 1.4)
        mono = lowpass(mono, 1400) * 0.05
        start = int(t0 * SR)
        seg = np.stack([mono, np.roll(mono, 240)], axis=1)  # kenglik uchun
        end = min(start + n, total)
        track[start:end] += seg[: end - start]
        t0 += chord_len
        i += 1

    # Arpedjio: sakkizlik notalar, 7.5-soniyadan boshlanadi
    t, step = 7.5, 0
    while t < DURATION - 6:
        chord = CHORDS[int(t // chord_len) % len(CHORDS)]
        pattern = [chord[1], chord[2], chord[3], chord[2]]
        f = note(pattern[step % 4]) * 2
        n = int(0.5 * SR)
        tt = np.arange(n) / SR
        pluck = (np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(4 * np.pi * f * tt)) * decay(n, 0.16)
        start = int(t * SR)
        end = min(start + n, total)
        track[start:end] += stereo(pluck * 0.045, pan=0.35 if step % 2 else -0.35)[: end - start]
        t += BEAT / 2
        step += 1

    # Yengil ritm: kick va hi-hat, 26.5-soniyadan (talaba yo'li) 106-soniyagacha
    beat_t = 26.5
    k = 0
    while beat_t < 106:
        if k % 2 == 0:
            n = int(0.3 * SR)
            tt = np.arange(n) / SR
            f = 45 + 70 * np.exp(-tt / 0.03)
            kick = np.sin(2 * np.pi * np.cumsum(f) / SR) * decay(n, 0.12) * 0.22
            start = int(beat_t * SR)
            track[start : start + n] += stereo(kick)[: total - start]
        hat_t = beat_t + BEAT / 2
        n = int(0.06 * SR)
        hat = bandpass(rng.standard_normal(n), 7000, 14000) * decay(n, 0.012) * 0.06
        start = int(hat_t * SR)
        if start + n < total:
            track[start : start + n] += stereo(hat, pan=0.2)
        beat_t += BEAT
        k += 1

    # Umumiy dinamika: boshida va oxirida tinchroq
    curve = np.interp(
        np.arange(total) / SR,
        [0, 3, 7.5, 26.5, 104, 108, 113, DURATION],
        [0.0, 0.7, 0.8, 1.0, 1.0, 0.85, 0.6, 0.0],
    )
    return track * curve[:, None]


# ---------------------------------------------------------------- vaqt jadvali (video.html bilan bir xil)

SCENE_ENDS = [7.5, 16.5, 26.5, 45, 57, 69, 79, 91, 99, 108]
HEADERS = [7.9, 16.9, 26.9, 45.4, 57.4, 69.4, 79.4, 91.4, 99.4]


def events():
    ev = []
    add = lambda t, sound, gain=1.0: ev.append((t, sound, gain))  # noqa: E731

    for end in SCENE_ENDS:
        add(end - 0.45, whoosh(), 0.9)
    for t in HEADERS:
        add(t, pop(520, 0.22))

    # 1. Kirish
    add(0.35, impact())
    add(0.9, shimmer(0.16, 16, 1.6))
    add(1.6, whoosh(0.7, 0.6, -0.6, 0.25))
    add(3.0, bell(note("E6"), 1.5, 0.12))

    # 2. Muammo
    add(8.2, shimmer(0.05, 30, 1.2))
    for i in range(3):
        add(9.4 + i * 1.1, pop(600 + i * 60, 0.3, -0.4))
    stars = ["C6", "D6", "E6", "G6", "A6", "C7", "D7", "E7", "G7", "A7"]
    for i, s in enumerate(stars):
        add(12.6 + i * 0.15, bell(note(s), 1.0, 0.1, pan=0.6))

    # 3. Yechim
    for i, f in enumerate([note("C5"), note("E5"), note("G5")]):
        add(17.6 + i * 1.2, bell(f, 1.4, 0.22, pan=-0.5 + i * 0.5))
        add(17.6 + i * 1.2, pop(400 + i * 80, 0.25))
    add(18.4, whoosh(0.6, -0.3, 0.1, 0.18))
    add(19.6, whoosh(0.6, 0.1, 0.4, 0.18))
    add(21.0, whoosh(1.0, 0.6, -0.6, 0.15))
    add(21.6, coin(0.22))

    # 4. Talaba yo'li
    for i in range(4):
        add(27.6 + i * 0.25, tick(1800 + i * 200, 0.15, -0.5))
    add(28.4, whoosh(0.6, 0.8, 0.4, 0.25))
    for t in (29.2, 33, 37, 41):
        add(t, pop(760, 0.25, -0.5))
    add(33, whoosh(0.4, 0.6, 0.2, 0.2))
    add(37.0, whoosh(0.7, 0.4, 0.8, 0.25))
    add(37.3, whoosh(0.8, 0.8, 0.2, 0.25))
    add(38.3, coin(0.32))
    add(38.35, shimmer(0.09, 10, 0.6))
    add(39.0, success(0.26))
    add(41.0, whoosh(0.5, 0.2, 0.6, 0.2))

    # 5. Motivatsiya
    for i, s in enumerate(["C5", "D5", "E5", "G5", "C6"]):
        add(46.6 + i * 0.35, bell(note(s), 0.8, 0.16, pan=-0.6))
    add(48.2, pop(650, 0.25, 0.4))
    add(48.8, coin(0.28))
    add(49.4, success(0.2))
    add(49.6, whoosh(0.8, 0.8, 0.3, 0.22))

    # 6. Imkoniyatlar
    for i, s in enumerate(["C5", "E5", "G5", "A5", "C6", "E6"]):
        add(58.4 + i * 0.55, pop(500 + i * 50, 0.24, -0.6 + (i % 3) * 0.6))
        add(58.4 + i * 0.55, bell(note(s), 0.7, 0.07, pan=-0.6 + (i % 3) * 0.6))

    # 7. O'qituvchi
    add(70.0, whoosh(0.8, 0.9, 0.3, 0.25))
    for i in range(3):
        add(72 + i * 1.4, pop(620 + i * 40, 0.28, -0.5))
    add(72.05, shimmer(0.06, 6, 0.4))

    # 8. Rektorat
    add(80.0, whoosh(0.8, 0.9, 0.3, 0.25))
    for i in range(3):
        add(81 + i * 0.5, pop(560 + i * 60, 0.25, -0.5))
    for k in range(5):
        add(81.3 + 1.5 * (k + 0.5) / 5, tick(2600, 0.14, -0.5))

    # 9. Ishonch
    for i, s in enumerate(["G5", "A5", "C6", "D6", "E6"]):
        add(92.3 + i * 0.45, pop(520 + i * 40, 0.22, -0.8 + i * 0.4))
        add(92.3 + i * 0.45, bell(note(s), 0.6, 0.06, pan=-0.8 + i * 0.4))

    # 10. Yo'l xaritasi
    add(100.3, riser(5.0, 0.1))
    for i, s in enumerate(["C5", "E5", "G5", "C6"]):
        add(100.4 + i * 1.15, bell(note(s), 1.3, 0.22, pan=-0.75 + i * 0.5))

    # 11. Yakun
    add(108.25, impact(0.6))
    add(108.6, shimmer(0.14, 18, 1.8))
    add(109.2, bell(note("C6"), 2.5, 0.12))
    add(109.25, bell(note("G6"), 2.5, 0.08))
    return ev


def build():
    total = int(DURATION * SR)
    mix = music()
    for t, sound, gain in events():
        start = int(t * SR)
        end = min(start + len(sound), total)
        mix[start:end] += sound[: end - start] * gain
    # Yumshoq limiter va normallashtirish
    mix = np.tanh(mix * 1.3) / np.tanh(1.3)
    mix *= 0.89 / max(np.abs(mix).max(), 1e-9)
    fade = int(0.5 * SR)
    mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return mix


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "soundtrack.wav"
    wavfile.write(out, SR, (build() * 32767).astype(np.int16))
    print("Tayyor:", out)
