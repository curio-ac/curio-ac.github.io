"""Public-domain sources (US government works, commercial use allowed). Topics are strings: "usgs:<url>" / "nasa:<post id>"."""
import html as H, json, re, urllib.parse, urllib.request
UA = {"User-Agent": "CurioBot/0.1 (https://github.com/curio-ac/curio-ac.github.io)"}
LICENSE = {"usgs": "Public domain (USGS)", "nasa": "Public domain (NASA)", "wiki": "CC BY-SA 4.0"}
NAME = {"usgs": "USGS", "nasa": "NASA", "wiki": "Wikipedia"}
THIRD_PARTY = re.compile(r"©|copyright|courtesy of|ESA/|/ESA|ESO|Getty|Shutterstock|AP Photo|Reuters", re.I)


def get(url, j=False):
    b = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read()
    return json.loads(b) if j else b.decode("utf8", "ignore")


def text_of(h):
    h = re.sub(r"(?is)<(script|style|nav|footer|header|figure|aside)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>", "\n", h)
    return re.sub(r"[ \t]+", " ", H.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def kind(topic):
    return topic.split(":", 1)[0] if re.match(r"^(usgs|nasa):", topic) else "wiki"


def article(topic):
    k, ref = topic.split(":", 1)
    if k == "usgs":
        page = get(ref)
        title = text_of(re.search(r"(?is)<h1[^>]*>(.*?)</h1>", page).group(1))
        main = re.search(r"(?is)<main.*?</main>", page)
        body = text_of(main.group(0) if main else page)
        body = body.split("Related")[0]
        if THIRD_PARTY.search(body[:200]): pass
        return {"title": title, "text": body[:6000], "url": ref, "lead": None}
    if k == "nasa":
        p = get(f"https://science.nasa.gov/wp-json/wp/v2/posts/{ref}?_fields=title,content,link", j=True)
        return {"title": text_of(p["title"]["rendered"]), "text": text_of(p["content"]["rendered"])[:6000], "url": p["link"], "lead": None}


def usgs_topics(pages=12):
    out = []
    for n in range(pages):
        try:
            h = get(f"https://www.usgs.gov/science/faqs?page={n}")
        except Exception:
            break
        out += ["usgs:https://www.usgs.gov" + u.split("?")[0] for u in re.findall(r'href="(/faqs/[a-z0-9-]{12,}[^"]*)"', h)]
    return list(dict.fromkeys(out))


def nasa_topics(pages=6):
    out = []
    for n in range(1, pages + 1):
        try:
            out += [f"nasa:{p['id']}" for p in get(f"https://science.nasa.gov/wp-json/wp/v2/posts?per_page=50&page={n}&_fields=id", j=True)]
        except Exception:
            break
    return out


def nasa_images(query, n=6):
    """NASA Image Library, skipping anything credited to third parties."""
    try:
        items = get("https://images-api.nasa.gov/search?" + urllib.parse.urlencode({"q": query, "media_type": "image", "page_size": 25}), j=True)["collection"]["items"]
    except Exception:
        return []
    out = []
    for it in items:
        d = (it.get("data") or [{}])[0]; desc = d.get("description", "") + " " + d.get("photographer", "") + " " + d.get("secondary_creator", "")
        if THIRD_PARTY.search(desc) or not it.get("links"): continue
        url = it["links"][0]["href"].replace("~thumb", "~medium")
        out.append({"url": url, "w": None, "h": None, "license": "Public domain (NASA)", "artist": "NASA", "page": f"https://images.nasa.gov/details/{d.get('nasa_id','')}",
                    "desc": f"{d.get('title','')} — {re.sub(r'<[^>]+>','',d.get('description',''))[:200]}"})
        if len(out) >= n: break
    return out
