"""Builds the live app into site/: index.html + feed.js (all videos) + audio files. Images stay on Wikimedia."""
import glob, json, os, shutil, subprocess
os.makedirs("site", exist_ok=True)
open("site/world.js", "w").write("window.WORLD=" + json.dumps(open("app/world.txt").read()) + ";")
shutil.copy("app/template.html", "site/index.html")
json.dump({"name": "Curio", "short_name": "Curio", "start_url": ".", "display": "standalone", "background_color": "#000000",
           "theme_color": "#000000", "icons": [{"src": "icon.png", "sizes": "512x512", "type": "image/png"}]}, open("site/manifest.json", "w"))
# app icon: rendered from SVG with ffmpeg-free fallback (ImageMagick on runner)
svg = '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512"><rect width="512" height="512" fill="#2F5BFF"/><path d="M347 175 A128 128 0 1 0 347 337" fill="none" stroke="#fff" stroke-width="68"/><circle cx="262" cy="256" r="34" fill="#fff"/></svg>'
open("site/icon.svg", "w").write(svg)
shutil.copy("app/icon.png", "site/icon.png")  # drawn once (Pillow); ImageMagick dropped the arc
open("site/.nojekyll", "w").close()
print("site built (app shell only; videos load from the content server)")
