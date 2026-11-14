"""Builds dist/preview.html: one self-contained file (audio + images embedded) for previewing."""
import base64, glob, json, os, urllib.request
UA = {"User-Agent": "CurioBot/0.1 (https://github.com/o2hoffman-hash/Curio)"}
V, AUD, IMG = [], {}, {}
for f in sorted(glob.glob("content/*/*.json")):
    if f.endswith("index.json"): continue
    v = json.load(open(f, encoding="utf8")); mp3 = f"audio/{v['lang']}/{v['id']}.mp3"
    if not os.path.exists(mp3): continue
    AUD[v["id"]] = "data:audio/mpeg;base64," + base64.b64encode(open(mp3, "rb").read()).decode()
    for im in v.get("images", []):
        try:
            d = urllib.request.urlopen(urllib.request.Request(im["url"], headers=UA), timeout=30).read()
            IMG[im["url"]] = ("data:image/png;base64," if im["url"].lower().endswith("png") else "data:image/jpeg;base64,") + base64.b64encode(d).decode()
        except Exception as e:
            print("img fail", im["url"], e)
    V.append(v)
html = open("app/template.html", encoding="utf8").read().replace("/*DATA*/", "const V=" + json.dumps(V, ensure_ascii=False) + ";\nconst AUD=" + json.dumps(AUD) + ";\nwindow.IMG=" + json.dumps(IMG) + ";").replace("/*WORLD*/", "window.WORLD=" + json.dumps(open("app/world.txt").read()) + ";")
os.makedirs("dist", exist_ok=True); open("dist/preview.html", "w", encoding="utf8").write(html)
print(f"preview: {len(V)} videos, {len(IMG)} images, {len(html)/1e6:.1f}MB")
