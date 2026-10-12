"""Taqdimot videosiga o'zbekcha diktor ovozini qo'shadi.

Microsoft'ning o'zbekcha neyron ovozlari (Madina yoki Sardor) bilan narration.json dagi
matnlarni o'qitadi, har birini o'z sahnasiga joylaydi, gapirilayotganda musiqani
pasaytiradi va yakuniy MP4 hamda subtitr (.srt) faylini yaratadi. Internet kerak.

O'rnatish:   pip install edge-tts imageio-ffmpeg
Ishlatish:   python ovozlash.py --video ADTI-Talent-Hub-taqdimot.mp4
             python ovozlash.py --video ADTI-Talent-Hub-taqdimot.mp4 --ovoz sardor
"""

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
VOICES = {"madina": "uz-UZ-MadinaNeural", "sardor": "uz-UZ-SardorNeural"}
MAX_TEMPO = 1.2  # Matn sahnaga sig'masa, nutqni ko'pi bilan 20% tezlashtiramiz


def ffmpeg_exe():
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


async def synthesize(text, voice, rate, path):
    import edge_tts

    for attempt in range(3):
        try:
            await edge_tts.Communicate(text, voice, rate=rate).save(str(path))
            return
        except Exception:
            if attempt == 2:
                raise
            await asyncio.sleep(2 * (attempt + 1))


def to_wav(ff, src, dst):
    subprocess.run([ff, "-v", "error", "-y", "-i", str(src), "-ar", "48000", "-ac", "1", str(dst)], check=True)


def duration(path):
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def srt_time(seconds):
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def build_filter(clips, voice_gain):
    """clips: [(ffmpeg kirish raqami, boshlanish soniyasi, tezlik)]"""
    parts, labels = [], []
    for k, (index, start, tempo) in enumerate(clips):
        chain = f"[{index}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={voice_gain}"
        if tempo > 1.001:
            chain += f",atempo={tempo:.3f}"
        delay = int(start * 1000)
        chain += f",adelay={delay}|{delay}[v{k}]"
        parts.append(chain)
        labels.append(f"[v{k}]")
    parts += [
        f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0[voice]",
        "[voice]apad,asplit=2[key][vo]",
        "[0:a]aformat=sample_rates=48000:channel_layouts=stereo[bg]",
        # Diktor gapirganda musiqa va effektlar avtomatik pasayadi
        "[bg][key]sidechaincompress=threshold=0.02:ratio=8:attack=15:release=400[duck]",
        "[duck][vo]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[aout]",
    ]
    return ";".join(parts)


def main():
    parser = argparse.ArgumentParser(description="Taqdimot videosini o'zbekcha ovozlash")
    parser.add_argument("--video", default="ADTI-Talent-Hub-taqdimot.mp4", help="musiqali video (kirish)")
    parser.add_argument("--chiqish", help="natija fayli (standart: <video>-ovozli.mp4)")
    parser.add_argument("--ovoz", choices=sorted(VOICES), default="madina", help="diktor ovozi")
    parser.add_argument("--tezlik", default="+0%", help="nutq tezligi, masalan +5%% yoki -5%%")
    parser.add_argument("--baland", type=float, default=1.4, help="diktor ovozi balandligi (1.0 = o'zgarishsiz)")
    parser.add_argument("--matn", default=str(HERE / "narration.json"), help="diktor matni (JSON)")
    args = parser.parse_args()

    video = Path(args.video)
    if not video.exists():
        sys.exit(f"Video topilmadi: {video}. --video bilan yo'lini ko'rsating.")
    out = Path(args.chiqish) if args.chiqish else video.with_name(video.stem + "-ovozli.mp4")
    lines = json.loads(Path(args.matn).read_text(encoding="utf-8"))
    ff = ffmpeg_exe()

    clips, subtitles = [], []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        wavs = []
        for i, line in enumerate(lines, start=1):
            print(f"[{i}/{len(lines)}] {line['text'][:60]}...")
            mp3, wav = tmp / f"{i}.mp3", tmp / f"{i}.wav"
            asyncio.run(synthesize(line["text"], VOICES[args.ovoz], args.tezlik, mp3))
            to_wav(ff, mp3, wav)
            spoken = duration(wav)
            slot = line["end"] - line["start"]
            tempo = max(1.0, spoken / slot)
            if tempo > MAX_TEMPO:
                print(f"   Diqqat: matn sahnadan {spoken - slot:.1f} s uzun. Uni qisqartirish tavsiya etiladi.")
                tempo = MAX_TEMPO
            wavs.append(wav)
            clips.append((i, line["start"], tempo))
            subtitles.append((line["start"], line["start"] + spoken / tempo, line["text"]))

        cmd = [ff, "-v", "error", "-y", "-i", str(video)]
        for wav in wavs:
            cmd += ["-i", str(wav)]
        cmd += [
            "-filter_complex", build_filter(clips, args.baland),
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
            str(out),
        ]  # fmt: skip
        print("Video yig'ilmoqda...")
        subprocess.run(cmd, check=True)

    srt = out.with_suffix(".srt")
    srt.write_text(
        "\n".join(f"{n}\n{srt_time(a)} --> {srt_time(b)}\n{text}\n" for n, (a, b, text) in enumerate(subtitles, 1)),
        encoding="utf-8",
    )
    print(f"Tayyor: {out}\nSubtitr: {srt}")


if __name__ == "__main__":
    main()
