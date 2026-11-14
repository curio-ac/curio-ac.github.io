"""Topic engine: keeps a queue of educational Wikipedia topics per language, refilled automatically.
Sources: en Vital articles (core knowledge) + Featured articles; Hebrew via interlanguage links + he featured articles."""
import json, os, random, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from factory import wiki

SKIP = re.compile(r"^(List of|Index of|Outline of|Timeline of|\d{1,4}( BC)?$|Wikipedia:|Category:|Portal:|Template:|Help:)|disambiguation|רשימת|^\d+$", re.I)


def links(lang, title, limit=3000):
    out, cont = [], {}
    while len(out) < limit:
        r = wiki(lang, action="query", prop="links", titles=title, plnamespace=0, pllimit="max", **cont)
        out += [l["title"] for l in r["query"]["pages"][0].get("links", [])]
        if "continue" not in r: break
        cont = {"plcontinue": r["continue"]["plcontinue"]}
    return out


def category(lang, cat, limit=3000):
    out, cont = [], {}
    while len(out) < limit:
        try:
            r = wiki(lang, action="query", list="categorymembers", cmtitle=cat, cmnamespace=0, cmlimit="max", **cont)
        except Exception:
            break
        out += [m["title"] for m in r["query"].get("categorymembers", [])]
        if "continue" not in r: break
        cont = {"cmcontinue": r["continue"]["cmcontinue"]}
    return out


def to_lang(titles, lang):
    out = []
    for i in range(0, len(titles), 50):
        r = wiki("en", action="query", prop="langlinks", titles="|".join(titles[i:i + 50]), lllang=lang, lllimit="max")
        out += [p["langlinks"][0]["title"] for p in r["query"]["pages"] if p.get("langlinks")]
    return out


def candidates(lang):
    vital = links("en", "Wikipedia:Vital articles")
    featured = category("en", "Category:Featured articles", 2000)
    random.shuffle(featured)
    en = vital + featured[:800]
    if lang == "en":
        pool = en
    else:
        pool = to_lang(en[:1500], lang) + category(lang, "קטגוריה:ערכים מומלצים", 1500)
    seen, out = set(), []
    for t in pool:
        if t not in seen and not SKIP.search(t):
            seen.add(t); out.append(t)
    return out


def refill(lang, index, minimum=150):
    """Returns the queue (pending topics), topping it up from Wikipedia when it runs low."""
    path = f"factory/queue/{lang}.json"
    os.makedirs("factory/queue", exist_ok=True)
    q = json.load(open(path, encoding="utf8")) if os.path.exists(path) else json.load(open(f"factory/topics/{lang}.json", encoding="utf8"))
    used = set(index["done"]) | set(index["rejected"]) | set(index.get("exhausted", []))
    q = [t for t in q if t not in used]
    if len(q) < minimum:
        new = [t for t in candidates(lang) if t not in used and t not in q]
        random.shuffle(new)
        q += new
        print(f"🧭 topic queue refilled: +{len(new)} → {len(q)}")
    json.dump(q, open(path, "w", encoding="utf8"), ensure_ascii=False, indent=0)
    return q
