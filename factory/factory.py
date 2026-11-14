"""Curio factory: Wikipedia -> script -> fact-check -> voice -> word timings -> images.
Usage: python factory/factory.py --lang he --count 5
Outputs: content/<lang>/<id>.json + audio/<lang>/<id>.mp3 ; updates content/<lang>/index.json
"""
import argparse, base64, hashlib, json, os, re, subprocess, sys, time, urllib.parse, urllib.request

UA = {"User-Agent": "CurioBot/0.1 (https://github.com/o2hoffman-hash/Curio)"}
KEY = os.environ.get("GEMINI_API_KEY", "")
G = "https://generativelanguage.googleapis.com/v1beta"
CATS = ["space", "biology", "history", "math", "geography", "physics", "chemistry", "language", "psychology", "art", "economics", "technology", "medicine"]
VOICE = os.environ.get("VOICE", "Puck")
THINK = True


class Quota(Exception):
    pass


def http(url, body=None, headers=None, timeout=120):
    h = dict(UA, **(headers or {}))
    data = None
    if body is not None:
        data = json.dumps(body).encode(); h["Content-Type"] = "application/json"
    for attempt in range(3):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=timeout))
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode("utf8", "ignore")
            if e.code == 429:
                if "PerDay" in msg or "per day" in msg.lower() or attempt == 2:
                    raise Quota(msg)
                time.sleep(30); continue
            if e.code >= 500 and attempt < 2:
                time.sleep(20 * (attempt + 1)); continue
            raise RuntimeError(f"{e.code} {msg}")
        except (TimeoutError, OSError) as e:
            if attempt == 2:
                raise RuntimeError(f"timeout/network: {e}")
            time.sleep(10)


# ---------- Gemini ----------
def pick_model(kind):
    env = os.environ.get("TTS_MODEL" if kind == "tts" else "TEXT_MODEL")
    if env:
        return env
    names = [m["name"].split("/")[1] for m in http(f"{G}/models?pageSize=200", headers={"x-goog-api-key": KEY})["models"]
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    def ver(n):
        m = re.search(r"(\d+)\.(\d+)", n); return (int(m[1]), int(m[2])) if m else (0, 0)
    if kind == "tts":
        c = [n for n in names if "tts" in n and "flash" in n and "lite" not in n]
    else:
        c = [n for n in names if "flash" in n and not re.search(r"tts|image|live|audio|lite|thinking|exp", n)]
    c.sort(key=lambda n: (ver(n), "preview" not in n), reverse=True)
    if not c:
        sys.exit(f"no {kind} model found in {names}")
    return c[0]


def gen_json(model, prompt):
    global THINK
    cfg = {"responseMimeType": "application/json", "temperature": 0.7}
    if THINK:
        cfg["thinkingConfig"] = {"thinkingLevel": "low"}
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": cfg}
    try:
        res = http(f"{G}/models/{model}:generateContent", body, {"x-goog-api-key": KEY}, timeout=300)
    except RuntimeError as e:
        if THINK and str(e).startswith("400"):
            THINK = False; return gen_json(model, prompt)
        raise
    return json.loads(res["candidates"][0]["content"]["parts"][0]["text"])


def tts(model, text, lang, out_mp3):
    style = ("Read this like an energetic, fast-paced TikTok science narrator. Keep it punchy, no pauses between sentences:"
             if lang == "en" else "קרא את זה כמו קריין טיקטוק אנרגטי ומהיר של מדע, בלי הפסקות בין משפטים:")
    body = {"contents": [{"parts": [{"text": f"{style}\n{text}"}]}],
            "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}}}
    res = http(f"{G}/models/{model}:generateContent", body, {"x-goog-api-key": KEY}, timeout=180)
    pcm = base64.b64decode(res["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", "-",
                    "-af", "silenceremove=start_periods=1:start_threshold=-45dB", "-b:a", "64k", out_mp3], input=pcm, check=True)


# ---------- Wikipedia ----------
def wiki(lang, **params):
    params.update(format="json", formatversion=2)
    return http(f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params))


def fetch_article(lang, query):
    hits = wiki(lang, action="query", list="search", srsearch=query, srlimit=1)["query"]["search"]
    if not hits:
        return None
    title = hits[0]["title"]
    page = wiki(lang, action="query", prop="extracts|pageimages", titles=title, explaintext=1, exchars=6000, piprop="name", redirects=1)["query"]["pages"][0]
    return {"title": page["title"], "text": page.get("extract", ""), "lead": page.get("pageimage"),
            "url": f"https://{lang}.wikipedia.org/wiki/" + urllib.parse.quote(page["title"].replace(" ", "_"))}


BAD_IMG = re.compile(r"logo|icon|flag|symbol|commons-|wikiquote|wiktionary|edit-|ambox|question_book|disambig|\.svg$", re.I)


def fetch_images(lang, title, lead, n=4):
    files = [f["title"] for f in wiki(lang, action="query", prop="images", titles=title, imlimit=40)["query"]["pages"][0].get("images", [])]
    if lead:
        lead_t = ("File:" if lang == "en" else "קובץ:") + lead
        files = [lead_t] + [f for f in files if f.split(":", 1)[1] != lead]
    files = [f for f in files if not BAD_IMG.search(f)][:15]
    if not files:
        return []
    pages = wiki(lang, action="query", prop="imageinfo", titles="|".join(files), iiprop="url|size|mime|extmetadata", iiurlwidth=720)["query"]["pages"]
    order = {f: i for i, f in enumerate(files)}
    out = []
    for p in sorted(pages, key=lambda p: order.get(p["title"], 99)):
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("mime") not in ("image/jpeg", "image/png") or ii.get("width", 0) < 400 or "/wikipedia/commons/" not in ii.get("thumburl", ""):
            continue  # only free-licensed Commons media
        md = ii.get("extmetadata", {})
        artist = re.sub(r"<[^>]+>", "", md.get("Artist", {}).get("value", ""))[:80].strip()
        out.append({"url": ii["thumburl"], "license": md.get("LicenseShortName", {}).get("value", ""), "artist": artist, "page": ii.get("descriptionurl")})
        if len(out) >= n:
            break
    return out


# ---------- script + fact check ----------
def write_script(model, lang, art):
    lname = "Hebrew" if lang == "he" else "English"
    words = "45-65" if lang == "he" else "55-75"
    return gen_json(model, f"""You write scripts for Curio, a TikTok-style educational video feed. Write in {lname}.
SOURCE (Wikipedia article "{art['title']}"):
\"\"\"{art['text']}\"\"\"

Rules:
- Use ONLY facts explicitly stated in SOURCE. Never add numbers, names or claims that are not in SOURCE.
- 5-7 short sentences, {words} words total, ~20-25 seconds when read fast.
- Sentence 1 is the hook: the single most surprising fact, under 10 words, makes people stop scrolling.
- Energetic, conversational, simple words. No "Did you know", no greetings, no questions to "like and follow".
- Each sentence adds a new fact; the last sentence is a satisfying payoff or twist.
- Write numbers as digits.
Return JSON: {{"title": short catchy title ({lname}, max 5 words), "category": one of {CATS}, "emoji": one emoji, "sentences": [..]}}""")


def fact_check(model, lang, art, sentences):
    res = gen_json(model, f"""You are a strict fact-checker. SOURCE:
\"\"\"{art['text']}\"\"\"
For each SENTENCE decide if every factual claim in it is directly supported by SOURCE (paraphrase is fine; extra facts, wrong numbers or exaggeration are NOT).
SENTENCES: {json.dumps(sentences, ensure_ascii=False)}
Return JSON: {{"verdicts": [{{"supported": true/false, "reason": "short"}}]}} in the same order.""")
    v = res.get("verdicts", [])
    return len(v) == len(sentences) and all(x.get("supported") for x in v), v


# ---------- niqqud + alignment ----------
_nq = None
def niqqud(text):
    global _nq
    if os.environ.get("NIQQUD", "1") != "1":
        return text
    if _nq is None:
        from phonikud_onnx import Phonikud
        _nq = Phonikud("phonikud-1.0.int8.onnx")
    from phonikud import lexicon
    return re.sub(fr"[{lexicon.NON_STANDARD_DIAC}]", "", _nq.add_diacritics(text))


_wm = None
def align(mp3, sentences, lang):
    global _wm
    import stable_whisper
    if _wm is None:
        _wm = stable_whisper.load_model(os.environ.get("WHISPER", "small"), device="cpu")
    text = " ".join(sentences)
    res = _wm.align(mp3, text, language=lang)
    w = [[x.word.strip(), round(x.start, 3), round(x.end, 3)] for s in res.segments for x in s.words if x.word.strip()]
    b, n = [], 0
    for s in sentences:
        b.append(n); n += len(s.split())
    if n != len(w):  # tokenization mismatch: rebuild words from text, map times proportionally
        toks = text.split(); T = w[-1][2] if w else 20
        w = [[t, round(i * T / len(toks), 3), round((i + 1) * T / len(toks), 3)] for i, t in enumerate(toks)]
    return {"w": w, "b": b}


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True); ap.add_argument("--count", type=int, default=5)
    a = ap.parse_args(); lang = a.lang
    os.makedirs(f"content/{lang}", exist_ok=True); os.makedirs(f"audio/{lang}", exist_ok=True)
    topics = json.load(open(f"factory/topics/{lang}.json", encoding="utf8"))
    idx_path = f"content/{lang}/index.json"
    index = json.load(open(idx_path)) if os.path.exists(idx_path) else {"done": [], "rejected": []}
    todo = [t for t in topics if t not in index["done"] and t not in index["rejected"]][:a.count]
    text_m, tts_m = pick_model("text"), pick_model("tts")
    print(f"models: text={text_m} tts={tts_m} | {len(todo)} topics", flush=True)
    stats = {"made": 0, "rejected": 0, "calls": 0}
    for topic in todo:
        try:
            art = fetch_article(lang, topic)
            if not art or len(art["text"]) < 800:
                print(f"✗ {topic}: article too short"); index["rejected"].append(topic); continue
            sc = write_script(text_m, lang, art); stats["calls"] += 1
            ok, verdicts = fact_check(text_m, lang, art, sc["sentences"]); stats["calls"] += 1
            if not ok:
                print(f"✗ {topic}: failed fact-check {[v.get('reason') for v in verdicts if not v.get('supported')]}")
                index["rejected"].append(topic); stats["rejected"] += 1; continue
            vid = lang + "-" + hashlib.md5(art["title"].encode()).hexdigest()[:8]
            mp3 = f"audio/{lang}/{vid}.mp3"
            spoken = " ".join(sc["sentences"])
            tts(tts_m, niqqud(spoken) if lang == "he" else spoken, lang, mp3); stats["calls"] += 1
            tim = align(mp3, sc["sentences"], lang)
            imgs = fetch_images(lang, art["title"], art["lead"])
            json.dump({"id": vid, "lang": lang, "title": sc["title"], "cat": sc["category"] if sc["category"] in CATS else "history",
                       "emoji": sc.get("emoji", "✨"), "sentences": sc["sentences"], "tim": tim, "images": imgs,
                       "source": {"title": art["title"], "url": art["url"], "license": "CC BY-SA 4.0"},
                       "ai": {"script": text_m, "voice": f"{tts_m}/{VOICE}", "fact_check": "passed"},
                       "created": time.strftime("%Y-%m-%d")},
                      open(f"content/{lang}/{vid}.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
            index["done"].append(topic); stats["made"] += 1
            print(f"✅ {topic} → {vid} ({tim['w'][-1][2] if tim['w'] else '?'}s, {len(imgs)} images)", flush=True)
        except Quota as e:
            print(f"⛔ daily quota reached: {e}"); break
        except Exception as e:
            print(f"⚠️ {topic}: {e}")
        finally:
            json.dump(index, open(idx_path, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(f"\nSUMMARY {lang}: {stats}")


if __name__ == "__main__":
    main()
