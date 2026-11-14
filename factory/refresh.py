"""Re-process existing videos (no voice quota): trim click, visual layer, images per sentence."""
import glob, json, sys
sys.path.insert(0, "factory")
from factory import trim, fetch_images, wiki, plan_images, plan_visuals, fetch_geo, fetch_article
for f in glob.glob("content/*/*.json"):
    if f.endswith("index.json"): continue
    v = json.load(open(f, encoding="utf8")); lang = v["lang"]
    if not v.get("trimmed"):
        trim(f"audio/{lang}/{v['id']}.mp3", v["tim"]); v["trimmed"] = True
    if not v.get("vis") or "--force" in sys.argv:
        art = fetch_article(lang, v["source"]["title"])
        v["vis"] = plan_visuals(v["sentences"], art); v["geo"] = fetch_geo(lang, art["title"])
        if not v["geo"]:
            v["vis"] = [x if x.get("type") != "map" else {"type": "image"} for x in v["vis"]]
        v["images"], v["sent_img"] = plan_images(v["sentences"], fetch_images(lang, art["title"], art["lead"]), v["vis"])
    json.dump(v, open(f, "w", encoding="utf8"), ensure_ascii=False, indent=1); print("✅", v["id"], [x["type"] for x in v["vis"]], v["sent_img"])
