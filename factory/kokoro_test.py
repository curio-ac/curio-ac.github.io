"""Kokoro trial: re-voice published English scripts with Kokoro and run them through our pronunciation gate."""
import glob, json, os, random, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from kokoro import KPipeline
import factory as F
from pron import check

VOICES = ["am_michael", "af_heart"]
random.seed(7)
files = random.sample(sorted(glob.glob("content/en/*.json")), 8)
os.makedirs("kokoro_out", exist_ok=True)
pipe = KPipeline(lang_code="a")
res = []
for i, f in enumerate(files):
    d = json.load(open(f)); text = " ".join(d["sentences"])
    v = VOICES[i % 2]
    a = np.concatenate([x for _, _, x in pipe(text, voice=v, speed=1.15)])
    pcm = (np.clip(a, -1, 1) * 32767).astype("<i2").tobytes()
    mp3 = f"kokoro_out/{i+1}-{v}.mp3"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", "-", "-b:a", "64k", mp3], input=pcm, check=True)
    tim = F.align(mp3, d["sentences"], "en"); F.trim(mp3, tim)
    w, heard = check(mp3, text, "en")
    r = {"file": mp3, "voice": v, "title": d["title"], "wer": round(w, 3), "pass": w <= F.MAX_WER, "text": text, "heard": heard}
    print(json.dumps(r, ensure_ascii=False)[:400], flush=True); res.append(r)
json.dump(res, open("kokoro_out/results.json", "w"), ensure_ascii=False, indent=1)
print("PASSED", sum(r["pass"] for r in res), "of", len(res))
