"""Pronunciation check: a Hebrew speech-recognition model listens to the narration and we count misheard words."""
import re, difflib, os
_m = {}
NIQ = re.compile(r"[֑-ׇ]")


def norm(t):
    t = NIQ.sub("", t).lower()
    t = re.sub(r"(?<=\d),(?=\d)", "", t)          # 2,000 -> 2000
    t = re.sub(r"[^\w\s]", " ", t)                  # punctuation, maqaf, "ה-20" -> "ה 20"
    t = t.replace("יי", "י").replace("וו", "ו")        # spelling variants (לווייתן/לוויתן)
    return t.split()


def model(lang):
    if lang not in _m:
        from faster_whisper import WhisperModel
        name = os.environ.get("ASR_HE", "ivrit-ai/whisper-large-v3-turbo-ct2") if lang == "he" else "small"
        _m[lang] = WhisperModel(name, device="cpu", compute_type="int8")
    return _m[lang]


def transcribe(mp3, lang):
    segs, _ = model(lang).transcribe(mp3, language=lang, beam_size=1, vad_filter=False)
    return " ".join(s.text for s in segs)


def wer(ref, hyp):
    r, h = norm(ref), norm(hyp)
    sm = difflib.SequenceMatcher(None, r, h)
    err = sum(max(i2 - i1, j2 - j1) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal")
    return err / max(1, len(r))


def check(mp3, text, lang):
    hyp = transcribe(mp3, lang)
    return round(wer(text, hyp), 3), hyp
