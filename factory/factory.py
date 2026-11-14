"""Curio factory: Wikipedia -> script -> fact-check -> voice -> word timings -> images.
Usage: python factory/factory.py --lang he --count 5
Outputs: content/<lang>/<id>.json + audio/<lang>/<id>.mp3 ; updates content/<lang>/index.json
"""
import argparse, random, base64, hashlib, json, os, re, subprocess, sys, time, urllib.parse, urllib.request

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
                    raise Quota(url.split("/models/")[-1].split(":")[0] + " " + re.sub(r"\s+", " ", msg)[-200:])
                time.sleep(30); continue
            if e.code >= 500 and attempt < 2:
                time.sleep(20 * (attempt + 1)); continue
            raise RuntimeError(f"{e.code} {msg}")
        except (TimeoutError, OSError) as e:
            if attempt == 1:
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


TTS_MODELS = os.environ.get("TTS_MODELS", "gemini-3.8-flash-tts,gemini-3.1-flash-tts-preview,gemini-2.5-flash-preview-tts,gemini-2.5-pro-preview-tts").split(",")
TEXT_MODELS = os.environ.get("TEXT_MODELS", "gemini-3.5-flash,gemini-3.1-flash-lite,gemini-flash-lite-latest").split(",")


def gen_json(model, prompt):
    """model arg ignored: walks TEXT_MODELS, dropping a model that times out / is overloaded / out of quota."""
    while TEXT_MODELS:
        try:
            return _gen_json(TEXT_MODELS[0], prompt)
        except (Quota, RuntimeError) as e:
            if isinstance(e, RuntimeError) and not re.match(r"(timeout|503|429)", str(e)):
                raise
            print(f"   ↪ {TEXT_MODELS[0]} unavailable ({str(e)[:60]}), switching model", flush=True)
            TEXT_MODELS.pop(0)
    raise Quota("all text models exhausted")


def _gen_json(model, prompt):
    global THINK
    parts = prompt if isinstance(prompt, list) else [{"text": prompt}]
    cfg = {"responseMimeType": "application/json", "temperature": 0.7}
    if THINK:
        cfg["thinkingConfig"] = {"thinkingLevel": "low"}
    body = {"contents": [{"parts": parts}], "generationConfig": cfg}
    try:
        res = http(f"{G}/models/{model}:generateContent", body, {"x-goog-api-key": KEY}, timeout=90)
    except RuntimeError as e:
        if THINK and str(e).startswith("400"):
            THINK = False; return _gen_json(model, prompt)
        raise
    return json.loads(res["candidates"][0]["content"]["parts"][0]["text"])


def tts(model, text, lang, out_mp3):
    # text only - no style instructions (the model reads them aloud)
    body = {"contents": [{"parts": [{"text": text}]}],
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


def fetch_images(lang, title, lead, n=15):
    files = [f["title"] for f in wiki(lang, action="query", prop="images", titles=title, imlimit=40)["query"]["pages"][0].get("images", [])]
    if lead:
        lead_t = ("File:" if lang == "en" else "קובץ:") + lead
        files = [lead_t] + [f for f in files if f.split(":", 1)[1] != lead]
    files = [f for f in files if not BAD_IMG.search(f)][:25]
    if not files:
        return []
    pages = wiki(lang, action="query", prop="imageinfo", titles="|".join(files), iiprop="url|size|mime|extmetadata", iiurlwidth=720)["query"]["pages"]
    order = {f: i for i, f in enumerate(files)}
    out = []
    for p in sorted(pages, key=lambda p: order.get(p["title"], 99)):
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("mime") not in ("image/jpeg", "image/png") or ii.get("width", 0) < 400 or "/wikipedia/commons/" not in ii.get("thumburl", ""):
            continue  # only free-licensed Commons media
        out.append(img_meta(ii, p["title"]))
        if len(out) >= n:
            break
    return out


def img_meta(ii, title):
    md = ii.get("extmetadata", {}); strip = lambda h: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h)).strip()
    desc = strip(md.get("ImageDescription", {}).get("value", ""))[:220]
    name = re.sub(r"\.\w+$", "", title.split(":", 1)[-1]).replace("_", " ")
    return {"url": ii["thumburl"], "w": ii.get("thumbwidth"), "h": ii.get("thumbheight"), "license": md.get("LicenseShortName", {}).get("value", ""),
            "artist": strip(md.get("Artist", {}).get("value", ""))[:80], "page": ii.get("descriptionurl"), "desc": f"{name} — {desc}"[:260]}


def commons_search(q, n=6):
    try:
        r = http("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(dict(
            action="query", format="json", formatversion=2, generator="search", gsrnamespace=6, gsrsearch=f"{q} filetype:bitmap",
            gsrlimit=12, prop="imageinfo", iiprop="url|size|mime|extmetadata", iiurlwidth=720)))
    except Exception as e:
        print("   commons search failed", e); return []
    out = []
    for p in sorted(r.get("query", {}).get("pages", []), key=lambda p: p.get("index", 99)):
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("mime") in ("image/jpeg", "image/png") and ii.get("width", 0) >= 500 and not BAD_IMG.search(p["title"]):
            out.append(img_meta(ii, p["title"]))
        if len(out) >= n: break
    return out


def thumb_b64(url):
    try:
        small = re.sub(r"/\d+px-", "/330px-", url)
        return base64.b64encode(urllib.request.urlopen(urllib.request.Request(small, headers=UA), timeout=30).read()).decode()
    except Exception:
        return None


def plan_images(sentences, pool, vis=None):
    """Pick, for every sentence, an image that shows what the sentence says (or None). Returns (images, sent_img)."""
    def ask(idx_sents, cands):
        listing = "\n".join(f"{i}: {pool[i]['desc']}" for i in cands)
        sents = "\n".join(f"{k}: {sentences[k]}" for k in idx_sents)
        res = gen_json(None, f"""Educational short video. For each SENTENCE pick the CANDIDATE image that best shows what the sentence says,
so the viewer SEES what they HEAR. Prefer an image that shows the specific content; an image of the sentence's main subject is acceptable. Unrelated or misleading = null.
If null, give a short English search query for Wikimedia Commons that would find a real photo/diagram illustrating that sentence.
SENTENCES:\n{sents}\nCANDIDATES:\n{listing}
Return JSON: {{"plan": [{{"sentence": n, "image": candidate number or null, "search": "query or null"}}]}}""")
        res = {"plan": res} if isinstance(res, list) else res
        return {int(x["sentence"]): x for x in res.get("plan", []) if isinstance(x, dict) and str(x.get("sentence", "")).isdigit() or isinstance(x.get("sentence"), int)}
    plan = ask(range(len(sentences)), range(len(pool)))
    pick = {k: (plan.get(k, {}).get("image")) for k in range(len(sentences))}
    missing = [k for k in pick if pick[k] is None and plan.get(k, {}).get("search")]
    if missing:
        start = len(pool)
        for k in missing:
            pool.extend(commons_search(plan[k]["search"], 4))
        if len(pool) > start:
            plan2 = ask(missing, range(start, len(pool)))
            for k in missing:
                pick[k] = plan2.get(k, {}).get("image")
    for k, v in list(pick.items()):
        if not isinstance(v, int) or not 0 <= v < len(pool):
            pick[k] = None
    # vision check: does the image really show it?
    chosen = [k for k in pick if pick[k] is not None]
    parts = [{"text": "For each numbered SENTENCE + IMAGE pair, answer whether the image clearly and correctly illustrates what the sentence says "
                      "or at least shows its main subject. Answer false only if the image is unrelated or would mislead/confuse a learner. If a TARGET is given, also return its bounding box [ymin,xmin,ymax,xmax] (0-1000). "
                      "Return JSON {\"ok\": {\"<n>\": true/false}, \"box\": {\"<n>\": [ymin,xmin,ymax,xmax]}}"}]
    sent_ok = []
    for k in chosen:
        b = thumb_b64(pool[pick[k]]["url"])
        if b:
            tg = (vis or [{}] * len(sentences))[k].get("target") if (vis or [{}] * len(sentences))[k].get("type") == "focus" else None
            parts += [{"text": f"SENTENCE {k}: {sentences[k]}" + (f"  TARGET: {tg}" if tg else "")}, {"inlineData": {"mimeType": "image/png" if pool[pick[k]]["url"].lower().endswith("png") else "image/jpeg", "data": b}}]
            sent_ok.append(k)
    boxes = {}
    if sent_ok:
        r = gen_json(None, parts)
        r = r if isinstance(r, dict) else {"ok": r}
        ok, boxes = r.get("ok", {}) or {}, r.get("box", {}) or {}
        if isinstance(ok, list): ok = {str(k): ok[i] for i, k in enumerate(sent_ok) if i < len(ok)}
        if isinstance(boxes, list): boxes = {str(k): boxes[i] for i, k in enumerate(sent_ok) if i < len(boxes)}
        for k in sent_ok:
            if ok.get(str(k)) is False:
                pick[k] = None
    if vis:
        for k, v in enumerate(vis):
            b = boxes.get(str(k))
            if v.get("type") == "focus":
                if pick[k] is not None and isinstance(b, list) and len(b) == 4:
                    v["box"] = [max(0, min(1000, int(x))) for x in b]
                else:
                    vis[k] = {"type": "image"}
    used = []
    for k in range(len(sentences)):
        if pick[k] is not None and pick[k] not in used:
            used.append(pick[k])
    images = [pool[i] for i in used]
    return images, [used.index(pick[k]) if pick[k] is not None else None for k in range(len(sentences))]


# ---------- visual information layer ----------
REFS = {"length": {"bus": 12, "human": 1.7, "football_field": 105, "eiffel_tower": 330},
        "mass": {"car": 1500, "elephant": 6000, "human": 70}}


def plan_visuals(sentences, art):
    """One visual per sentence; every number must literally appear in SOURCE, else it falls back to an image."""
    res = gen_json(None, f"""You design the on-screen visual for each sentence of a short educational video, so the EYE gets information too.
SOURCE:\n\"\"\"{art['text'][:5000]}\"\"\"
SENTENCES:\n""" + "\n".join(f"{k}: {x}" for k, x in enumerate(sentences)) + """
For each sentence choose ONE visual:
- {"type":"stat","value":number,"unit":"short unit","label":"2-3 words in the sentence language"}  — a key number from the sentence
- {"type":"compare","value":number,"dim":"length"|"mass","unit_value_in":"m"|"kg"} — when a size/weight is mentioned and a scale comparison helps (value converted to metres or kg)
- {"type":"map"} — when the sentence is about WHERE something is
- {"type":"timeline","year":number} — when the sentence is about WHEN (negative for BCE)
- {"type":"focus","target":"short English name of the visible part/thing to highlight in a photo"} — when the sentence names a visible part (e.g. "the tongue")
- {"type":"image"} — otherwise
Every number MUST appear in SOURCE (copied exactly, or a pure unit conversion). Use at most 3 non-image visuals per video, never two of the same type in a row.
Return JSON: {"visuals":[...one per sentence...]}""")
    vis = [x if isinstance(x, dict) else {"type": "image"} for x in ((res if isinstance(res, list) else res.get("visuals")) or [])][:len(sentences)]
    vis += [{"type": "image"}] * (len(sentences) - len(vis))
    digits = re.sub(r"[,\s]", "", art["text"])
    for k, v in enumerate(vis):
        t = v.get("type")
        if t in ("stat", "compare", "timeline"):
            num = v.get("year") if t == "timeline" else v.get("value")
            try:
                n = float(num)
            except (TypeError, ValueError):
                vis[k] = {"type": "image"}; continue
            raw = (str(int(abs(n))) if n == int(n) else str(abs(n)))
            if t != "compare" and raw not in digits:  # deterministic check: the number is in the source
                print(f"   ✂ visual {k} dropped: {raw} not in source"); vis[k] = {"type": "image"}
            if t == "compare" and v.get("dim") not in REFS:
                vis[k] = {"type": "image"}
    return vis


def fetch_geo(lang, title):
    try:
        q = wiki(lang, action="query", prop="pageprops", titles=title, ppprop="wikibase_item")["query"]["pages"][0]["pageprops"]["wikibase_item"]
        c = http(f"https://www.wikidata.org/wiki/Special:EntityData/{q}.json")["entities"][q]["claims"].get("P625")
        v = c[0]["mainsnak"]["datavalue"]["value"]
        return [round(v["latitude"], 3), round(v["longitude"], 3)]
    except Exception:
        return None


# ---------- script + fact check ----------
def write_script(model, lang, art, fix="", prev=None):
    lname = "Hebrew" if lang == "he" else "English"
    words = "45-65" if lang == "he" else "55-75"
    prev_txt = ("Earlier videos about this article already covered: " + "; ".join(prev) + '. Pick DIFFERENT facts and a different hook. If SOURCE has no other surprising facts, return {"skip": true}.') if prev else ""
    fix_txt = ("A fact-checker rejected these sentences of your previous draft. Rewrite the script so every claim is strictly supported (drop unsupported adjectives/details):" + chr(10) + fix) if fix else ""
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
{fix_txt}
{prev_txt}
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


def trim(mp3, tim):
    """Cut model noise: start 0.08s before the first word, end 0.3s after the last; shift timings."""
    if not tim["w"]:
        return
    st = max(0.0, tim["w"][0][1] - 0.08); end = tim["w"][-1][2] + 0.3; d = end - st; tmp = mp3 + ".tmp.mp3"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{st:.3f}", "-i", mp3, "-t", f"{d:.3f}",
                    "-af", f"afade=t=in:d=0.03,afade=t=out:st={d-0.15:.3f}:d=0.15", "-b:a", "64k", tmp], check=True)
    os.replace(tmp, mp3)
    tim["w"] = [[w, round(max(0, a - st), 3), round(max(0, b - st), 3)] for w, a, b in tim["w"]]


def local_tts(text, lang, mp3):
    """Open-source fallback voice (no quota): Phonikud+Piper for Hebrew, Kokoro for English."""
    import numpy as np
    if lang == "he":
        from phonikud_tts import Phonikud as PK, phonemize, Piper
        samples, rate = Piper("tts-model.onnx", "tts-model.config.json").create(phonemize(PK("phonikud-1.0.int8.onnx").add_diacritics(text)), is_phonemes=True)
    else:
        from kokoro import KPipeline
        samples = np.concatenate([a for _, _, a in KPipeline(lang_code="a")(text, voice="am_michael", speed=1.15)]); rate = 24000
    pcm = (np.clip(np.asarray(samples).flatten(), -1, 1) * 32767).astype("<i2").tobytes()
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "s16le", "-ar", str(rate), "-ac", "1", "-i", "-", "-b:a", "64k", mp3], input=pcm, check=True)


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True); ap.add_argument("--count", type=int, default=5)
    a = ap.parse_args(); lang = a.lang
    os.makedirs(f"content/{lang}", exist_ok=True); os.makedirs(f"audio/{lang}", exist_ok=True)
    idx_path = f"content/{lang}/index.json"
    index = json.load(open(idx_path)) if os.path.exists(idx_path) else {"done": [], "rejected": []}
    index.setdefault("angles", {}); index.setdefault("exhausted", [])
    from topics import refill
    queue = refill(lang, index)
    again = [t for t in index["done"] if t not in index["exhausted"] and len(index["angles"].get(t, [1])) < 3]
    n_again = min(len(again), a.count // 3)
    todo = queue[:a.count - n_again] + random.sample(again, n_again)
    text_m, tts_m = TEXT_MODELS[0], TTS_MODELS[0]
    print(f"models: text={text_m} tts={tts_m} | {len(todo)} topics", flush=True)
    stats = {"made": 0, "rejected": 0, "calls": 0}
    for topic in todo:
        try:
            art = fetch_article(lang, topic)
            if not art or len(art["text"]) < 800:
                print(f"✗ {topic}: article too short"); index["rejected"].append(topic); continue
            prev = index["angles"].get(topic, [])
            sc = write_script(text_m, lang, art, prev=prev); stats["calls"] += 1
            if sc.get("skip") or not sc.get("sentences"):
                print(f"↷ {topic}: no new angle"); index["exhausted"].append(topic); continue
            for attempt in range(3):
                ok, verdicts = fact_check(text_m, lang, art, sc["sentences"]); stats["calls"] += 1
                if ok or attempt == 2:
                    break
                bad = [f"- \"{s}\": {v.get('reason')}" for s, v in zip(sc["sentences"], verdicts) if not v.get("supported")]
                print(f"   ↻ {topic}: fixing {len(bad)} sentence(s)", flush=True)
                sc = write_script(text_m, lang, art, "\n".join(bad)); stats["calls"] += 1
            if not ok:
                print(f"✗ {topic}: failed fact-check {[v.get('reason') for v in verdicts if not v.get('supported')]}")
                index["rejected"].append(topic); stats["rejected"] += 1; continue
            vid = lang + "-" + hashlib.md5((art["title"] + (str(len(prev)) if prev else "")).encode()).hexdigest()[:8]
            mp3 = f"audio/{lang}/{vid}.mp3"
            spoken = " ".join(sc["sentences"])
            voice = None
            while TTS_MODELS:
                try:
                    tts(TTS_MODELS[0], niqqud(spoken) if lang == "he" else spoken, lang, mp3); stats["calls"] += 1; voice = f"{TTS_MODELS[0]}/{VOICE}"; break
                except (Quota, RuntimeError) as e:
                    if isinstance(e, RuntimeError) and not re.match(r"(timeout|503|429|404)", str(e)):
                        raise
                    print(f"   ↪ tts {TTS_MODELS[0]} unavailable, switching", flush=True); TTS_MODELS.pop(0)
            if not voice:
                local_tts(spoken, lang, mp3); voice = "open-source (piper)" if lang == "he" else "open-source (kokoro)"
            tim = align(mp3, sc["sentences"], lang)
            trim(mp3, tim)
            vis = plan_visuals(sc["sentences"], art); geo = fetch_geo(lang, art["title"]); stats["calls"] += 1
            if not geo:
                vis = [v if v.get("type") != "map" else {"type": "image"} for v in vis]
            imgs, sent_img = plan_images(sc["sentences"], fetch_images(lang, art["title"], art["lead"]), vis); stats["calls"] += 2
            json.dump({"id": vid, "lang": lang, "title": sc["title"], "cat": sc["category"] if sc["category"] in CATS else "history",
                       "emoji": sc.get("emoji", "✨"), "sentences": sc["sentences"], "tim": tim, "images": imgs, "sent_img": sent_img, "vis": vis, "geo": geo,
                       "source": {"title": art["title"], "url": art["url"], "license": "CC BY-SA 4.0"},
                       "ai": {"script": text_m, "voice": voice, "fact_check": "passed"},
                       "created": time.strftime("%Y-%m-%d"), "trimmed": True},
                      open(f"content/{lang}/{vid}.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
            if topic not in index["done"]: index["done"].append(topic)
            index["angles"].setdefault(topic, []).append(f'{sc["title"]}: {sc["sentences"][0]}'); stats["made"] += 1
            q_path = f"factory/queue/{lang}.json"
            if os.path.exists(q_path):
                json.dump([t for t in json.load(open(q_path, encoding="utf8")) if t != topic], open(q_path, "w", encoding="utf8"), ensure_ascii=False, indent=0)
            print(f"✅ {topic} → {vid} ({tim['w'][-1][2] if tim['w'] else '?'}s, images per sentence: {sent_img})", flush=True)
        except Quota as e:
            print(f"⛔ daily quota reached: {e}"); break
        except Exception as e:
            print(f"⚠️ {topic}: {e}")
        finally:
            json.dump(index, open(idx_path, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(f"\nSUMMARY {lang}: {stats}")


if __name__ == "__main__":
    main()
