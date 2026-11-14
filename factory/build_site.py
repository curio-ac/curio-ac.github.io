"""Builds the live app into site/: index.html + feed.js (all videos) + audio files. Images stay on Wikimedia."""
import glob, json, os, shutil, subprocess
os.makedirs("site", exist_ok=True)
V = []
for f in sorted(glob.glob("content/*/*.json")):
    if f.endswith("index.json"): continue
    v = json.load(open(f, encoding="utf8")); mp3 = f"audio/{v['lang']}/{v['id']}.mp3"
    if os.path.exists(mp3):
        V.append(v)
V.sort(key=lambda v: v.get("created", ""), reverse=True)
aud = {v["id"]: f"audio/{v['lang']}/{v['id']}.mp3" for v in V}
open("site/feed.js", "w", encoding="utf8").write(
    "const V=" + json.dumps(V, ensure_ascii=False, separators=(",", ":")) + ";\nconst AUD=" + json.dumps(aud) +
    ";\nwindow.WORLD=" + json.dumps(open("app/world.txt").read()) + ";")
html = open("app/template.html", encoding="utf8").read().replace("<script>\n/*DATA*/\n/*WORLD*/", '<script src="feed.js"></script>\n<script>')
open("site/index.html", "w", encoding="utf8").write(html)
shutil.copytree("audio", "site/audio", dirs_exist_ok=True)
json.dump({"name": "Curio", "short_name": "Curio", "start_url": ".", "display": "standalone", "background_color": "#1a0b3d",
           "theme_color": "#1a0b3d", "icons": [{"src": "icon.png", "sizes": "512x512", "type": "image/png"}]}, open("site/manifest.json", "w"))
# app icon: rendered from SVG with ffmpeg-free fallback (ImageMagick on runner)
svg = '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512"><rect width="512" height="512" rx="110" fill="#1a0b3d"/><text x="256" y="330" font-family="Arial Black,Arial" font-weight="900" font-size="230" text-anchor="middle" fill="#fff">c<tspan fill="#ffd166">o</tspan></text></svg>'
open("site/icon.svg", "w").write(svg)
subprocess.run(["convert", "site/icon.svg", "site/icon.png"], check=False)
open("site/.nojekyll", "w").close()
print(f"site: {len(V)} videos")
