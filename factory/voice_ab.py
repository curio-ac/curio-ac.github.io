"""A/B test of Hebrew pronunciation strategies on one script, scored by pron.check (word error rate)."""
import json, os, sys
sys.path.insert(0, "factory")
import factory as F
from pron import check
TEXT = " ".join(json.load(open(sys.argv[1], encoding="utf8"))["sentences"])
os.makedirs("samples/ab", exist_ok=True)
F.TTS_MODELS[:] = [os.environ.get("TTS_MODEL", "gemini-3.8-flash-tts")]
speech = F.gen_json(None, f"""Prepare this Hebrew narration for a text-to-speech engine. Return JSON {{"partial": ..., "plain": ...}}:
- "plain": identical text, but every number written out in Hebrew words with the correct grammatical gender (e.g. 3 לבבות -> שלושה לבבות).
- "partial": same as plain, plus niqqud ONLY on words whose pronunciation is ambiguous without vowels (and on foreign names). Leave all other words unvocalized.
TEXT: {TEXT}""")
variants = {"full_niqqud": F.niqqud(TEXT), "partial_niqqud": speech["partial"], "plain_words": speech["plain"]}
res = {}
for k, t in variants.items():
    mp3 = f"samples/ab/{k}.mp3"
    F.tts(F.TTS_MODELS[0], t, "he", mp3)
    w, hyp = check(mp3, speech["plain"], "he")
    res[k] = {"wer": w, "input": t, "heard": hyp}
    print(f"{k}: WER={w}")
json.dump({"model": F.TTS_MODELS[0], "text": TEXT, "results": res}, open("samples/ab/results.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
