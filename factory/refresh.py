"""Re-process existing videos (no voice quota): trim click, re-plan images per sentence."""
import glob, json, sys
sys.path.insert(0, "factory")
from factory import trim, fetch_images, wiki, plan_images
for f in glob.glob("content/*/*.json"):
    if f.endswith("index.json"): continue
    v = json.load(open(f, encoding="utf8")); lang = v["lang"]
    if not v.get("trimmed"):
        trim(f"audio/{lang}/{v['id']}.mp3", v["tim"]); v["trimmed"] = True
    if not v.get("sent_img"):
        lead = wiki(lang, action="query", prop="pageimages", titles=v["source"]["title"], piprop="name")["query"]["pages"][0].get("pageimage")
        v["images"], v["sent_img"] = plan_images(v["sentences"], fetch_images(lang, v["source"]["title"], lead))
    json.dump(v, open(f, "w", encoding="utf8"), ensure_ascii=False, indent=1); print("✅", v["id"], v["sent_img"])
