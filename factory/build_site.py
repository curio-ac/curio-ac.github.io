"""Builds the live app into site/: index.html + feed.js (all videos) + audio files. Images stay on Wikimedia."""
import glob, json, os, shutil, subprocess
os.makedirs("site", exist_ok=True)
open("site/world.js", "w").write("window.WORLD=" + json.dumps(open("app/world.txt").read()) + ";")
shutil.copy("app/template.html", "site/index.html")
json.dump({"name": "Curio", "short_name": "Curio", "start_url": ".", "display": "standalone", "background_color": "#000000",
           "theme_color": "#000000", "icons": [{"src": "icon.png", "sizes": "512x512", "type": "image/png"}]}, open("site/manifest.json", "w"))
# app icon: rendered from SVG with ffmpeg-free fallback (ImageMagick on runner)
svg = '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512"><rect width="512" height="512" fill="#F5E62E"/><path d="M347 175 A128 128 0 1 0 347 337" fill="none" stroke="#000" stroke-width="68"/></svg>'
open("site/icon.svg", "w").write(svg)
try:
    subprocess.run(["convert", "-background", "none", "site/icon.svg", "site/icon.png"], check=False)
except FileNotFoundError:
    print("no imagemagick; icon.png skipped")
open("site/.nojekyll", "w").close()
print("site built (app shell only; videos load from the content server)")
