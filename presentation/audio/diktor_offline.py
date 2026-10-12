"""Internetsiz o'zbekcha diktor ovozi: Piper (VITS) modeli + o'zbekcha G2P.

O'zbekcha tayyor neyron model bo'lmagani uchun tovushlari o'zbek tiliga eng yaqin bo'lgan
qozoqcha ISSAI modelidan (CC-BY-4.0) foydalanadi: matn uz_g2p.py orqali IPA tovushlarga
o'giriladi va model shu tovushlarni o'qiydi. Natijada o'zbekcha nutq biroz qozoqcha
talaffuz bilan chiqadi. Microsoft'ning haqiqiy o'zbekcha ovozi uchun ovozlash.py ni ishlating.

Model: https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-kk_KZ-issai-high.tar.bz2

Ishlatish:
    python diktor_offline.py --model-dir vits-piper-kk_KZ-issai-high --chiqish diktor.wav
Kerak: numpy, onnxruntime
"""

import argparse
import json
import subprocess
import wave
from pathlib import Path

import numpy as np
import onnxruntime as ort
from uz_g2p import phonemize, sentences

HERE = Path(__file__).resolve().parent
SPEAKERS = {"ayol": 3, "ayol2": 2, "ayol3": 4, "ayol4": 5, "erkak": 0, "erkak2": 1}
OUT_RATE = 48_000


class Voice:
    def __init__(self, model_dir, speaker):
        model_dir = Path(model_dir)
        onnx = next(model_dir.glob("*.onnx"))
        self.config = json.loads(onnx.with_suffix(".onnx.json").read_text(encoding="utf-8"))
        self.ids = {k: v[0] for k, v in self.config["phoneme_id_map"].items()}
        self.rate = self.config["audio"]["sample_rate"]
        self.session = ort.InferenceSession(str(onnx), providers=["CPUExecutionProvider"])
        self.speaker = speaker
        self.noise, self.noise_w = 0.6, 0.7

    def to_ids(self, phonemes):
        seq = [self.ids["^"], self.ids["_"]]
        for ch in phonemes:
            if ch in self.ids:
                seq += [self.ids[ch], self.ids["_"]]
        return seq + [self.ids["$"]]

    def say(self, phonemes, length_scale=1.0):
        ids = np.array([self.to_ids(phonemes)], dtype=np.int64)
        inputs = {
            "input": ids,
            "input_lengths": np.array([ids.shape[1]], dtype=np.int64),
            "scales": np.array([self.noise, length_scale, self.noise_w], dtype=np.float32),
            "sid": np.array([self.speaker], dtype=np.int64),
        }
        audio = self.session.run(None, inputs)[0].squeeze().astype(np.float32)
        return audio


def resample(x, src, dst):
    if src == dst:
        return x
    n = int(round(len(x) * dst / src))
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


def synth_line(voice, text, length_scale):
    pieces = []
    for sentence in sentences(text):
        audio = voice.say(phonemize(sentence), length_scale)
        pieces += [audio, np.zeros(int(0.22 * voice.rate), dtype=np.float32)]
    return resample(np.concatenate(pieces[:-1]), voice.rate, OUT_RATE)


def main():
    parser = argparse.ArgumentParser(description="Diktor ovozini internetsiz yaratish")
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--ovoz", choices=sorted(SPEAKERS), default="ayol")
    parser.add_argument("--tezlik", type=float, default=1.0, help="1.0 = me'yoriy, 0.9 = tezroq, 1.1 = sekinroq")
    parser.add_argument("--matn", default=str(HERE / "narration.json"))
    parser.add_argument("--chiqish", default="diktor.wav", help="butun video uzunligidagi ovoz yo'lagi (WAV)")
    parser.add_argument("--uzunlik", type=float, default=150.0, help="video uzunligi, soniya")
    parser.add_argument("--video", help="musiqali video: berilsa, diktor ovozi unga aralashtiriladi")
    parser.add_argument("--video-chiqish", help="natija video (standart: <video>-diktorli.mp4)")
    args = parser.parse_args()

    voice = Voice(args.model_dir, SPEAKERS[args.ovoz])
    lines = json.loads(Path(args.matn).read_text(encoding="utf-8"))
    track = np.zeros(int(args.uzunlik * OUT_RATE), dtype=np.float32)
    for i, line in enumerate(lines, 1):
        slot = line["end"] - line["start"]
        scale = args.tezlik
        audio = synth_line(voice, line["text"], scale)
        # Sahnaga sig'masa, biroz tezroq o'qitamiz (ko'pi bilan 20%)
        if len(audio) / OUT_RATE > slot:
            scale = max(scale * slot / (len(audio) / OUT_RATE), scale * 0.8)
            audio = synth_line(voice, line["text"], scale)
        start = int(line["start"] * OUT_RATE)
        end = min(start + len(audio), len(track))
        track[start:end] += audio[: end - start]
        print(f"[{i}/{len(lines)}] {len(audio) / OUT_RATE:.1f} s / {slot:.1f} s  {line['text'][:50]}...")

    peak = np.abs(track).max() or 1.0
    track = track / peak * 0.9
    with wave.open(args.chiqish, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(OUT_RATE)
        w.writeframes((track * 32767).astype(np.int16).tobytes())
    print("Tayyor:", args.chiqish)
    if args.video:
        mix_into_video(args.video, args.chiqish, args.video_chiqish)


def mix_into_video(video, voice_wav, out=None):
    """Diktorni musiqali videoga qo'shadi: gapirganda musiqa avtomatik pasayadi."""
    from ovozlash import ffmpeg_exe

    video = Path(video)
    out = Path(out) if out else video.with_name(video.stem + "-diktorli.mp4")
    graph = ";".join(
        [
            "[1:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.85,apad[v]",
            "[v]asplit=2[key][vo]",
            "[0:a]aformat=sample_rates=48000:channel_layouts=stereo[bg]",
            "[bg][key]sidechaincompress=threshold=0.02:ratio=8:attack=15:release=400[duck]",
            "[duck][vo]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]",
        ]
    )
    cmd = [ffmpeg_exe(), "-v", "error", "-y", "-i", str(video), "-i", str(voice_wav), "-filter_complex", graph]
    cmd += ["-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
    subprocess.run(cmd + [str(out)], check=True)
    print("Video tayyor:", out)


if __name__ == "__main__":
    main()
