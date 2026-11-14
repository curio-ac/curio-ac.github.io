"""Audit every published video against today's bar; pull the ones that fail out of the feed (they get re-recorded by the factory)."""
import glob, json, os, sys
sys.path.insert(0, "factory")
from factory import rebuild_feed, MAX_WER, HE_TTS
from pron import check
pulled = 0
for f in sorted(glob.glob("content/*/*.json")):
    if f.endswith(("index.json", "feed.json")): continue
    v = json.load(open(f, encoding="utf8")); lang = v["lang"]
    if v.get("hidden"): continue
    if v.get("pron_wer") is None:
        v["pron_wer"], _ = check(f"audio/{lang}/{v['id']}.mp3", " ".join(v["sentences"]), lang)
    voice = v.get("ai", {}).get("voice", "")
    reasons = []
    if v["pron_wer"] > MAX_WER: reasons.append(f"pronunciation {round(v['pron_wer']*100,1)}%")
    if lang == "he" and not any(voice.startswith(m) for m in HE_TTS): reasons.append(f"voice {voice}")
    if reasons:
        v["hidden"] = True; v["needs_voice"] = True; v["hidden_reason"] = reasons; pulled += 1
    print(("⛔ " if reasons else "✅ ") + v["id"], round(v["pron_wer"] * 100, 1), "%", "; ".join(reasons), flush=True)
    json.dump(v, open(f, "w", encoding="utf8"), ensure_ascii=False, indent=1)
rebuild_feed()
print(f"pulled from feed: {pulled}")
