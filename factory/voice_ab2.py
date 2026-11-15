"""Which Hebrew voices pass the pronunciation gate with the new text prep (numbers as words, no niqqud)?"""
import glob, json, os, sys
sys.path.insert(0, "factory")
import factory as F
from pron import check
vids = [json.load(open(f, encoding="utf8")) for f in sorted(glob.glob("content/he/*.json")) if not f.endswith(("index.json", "feed.json"))]
vids = [v for v in vids if v.get("hidden")][:3]
os.makedirs("samples/ab2", exist_ok=True)
engines = ["gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts", "piper"]
res = {e: [] for e in engines}
for v in vids:
    shown = " ".join(v["sentences"]); spoken = F.speech_text("he", v["sentences"])
    for e in engines:
        mp3 = f"samples/ab2/{v['id']}-{e}.mp3"
        try:
            F.local_tts(spoken, "he", mp3) if e == "piper" else F.tts(e, spoken, "he", mp3)
            w, heard = check(mp3, shown, "he"); res[e].append(w); print(f"{v['id']} {e}: {round(w*100,1)}%", flush=True)
        except Exception as ex:
            print(f"{v['id']} {e}: ERROR {str(ex)[:120]}", flush=True)
summary = {e: (round(sum(x)/len(x)*100, 1) if x else None) for e, x in res.items()}
print("AVERAGE:", summary)
json.dump({"videos": [v["id"] for v in vids], "per_engine": res, "avg_percent": summary}, open("samples/ab2/results.json", "w"), indent=1)
