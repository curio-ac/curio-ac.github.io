"""Re-process existing videos without using any AI quota: trim start click + fetch more images."""
import glob, json, sys
sys.path.insert(0, "factory")
from factory import trim, fetch_images, wiki
for f in glob.glob("content/*/*.json"):
    if f.endswith("index.json"): continue
    v = json.load(open(f, encoding="utf8")); lang = v["lang"]
    if not v.get("trimmed"):
        trim(f"audio/{lang}/{v['id']}.mp3", v["tim"]); v["trimmed"] = True
    lead = wiki(lang, action="query", prop="pageimages", titles=v["source"]["title"], piprop="name")["query"]["pages"][0].get("pageimage")
    v["images"] = fetch_images(lang, v["source"]["title"], lead) or v["images"]
    json.dump(v, open(f, "w", encoding="utf8"), ensure_ascii=False, indent=1); print("✅", v["id"], len(v["images"]), "images")
