"""Chatterbox trial: expressive English voice, same scripts as the Kokoro trial, through our pronunciation gate."""
import glob, json, os, random, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, torch
from chatterbox.tts import ChatterboxTTS
import factory as F
from pron import check

random.seed(7)
files = random.sample(sorted(glob.glob("content/en/*.json")), 8)[:3]
os.makedirs("kokoro_out", exist_ok=True)
m = ChatterboxTTS.from_pretrained(device="cpu")
res = []
for i, f in enumerate(files):
    d = json.load(open(f)); text = " ".join(d["sentences"])
    for ex in (0.6, 0.85):
        wav = m.generate(text, exaggeration=ex, cfg_weight=0.35)
        pcm = (np.clip(wav.squeeze().numpy(), -1, 1) * 32767).astype("<i2").tobytes()
        mp3 = f"kokoro_out/cb{i+1}-ex{int(ex*100)}.mp3"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "s16le", "-ar", str(m.sr), "-ac", "1", "-i", "-", "-b:a", "64k", mp3], input=pcm, check=True)
        tim = F.align(mp3, d["sentences"], "en"); F.trim(mp3, tim)
        w, heard = check(mp3, text, "en")
        r = {"file": mp3, "ex": ex, "title": d["title"], "wer": round(w, 3), "pass": w <= F.MAX_WER}
        print(json.dumps(r), flush=True); res.append(r)
json.dump(res, open("kokoro_out/results.json", "w"), indent=1)
