import json, os, time, urllib.request
K = os.environ["GEMINI_API_KEY"]; G = "https://generativelanguage.googleapis.com/v1beta"
ms = json.load(urllib.request.urlopen(urllib.request.Request(f"{G}/models?pageSize=200", headers={"x-goog-api-key": K})))["models"]
names = [m["name"].split("/")[1] for m in ms if "generateContent" in m.get("supportedGenerationMethods", [])]
print("ALL:", names)
for n in [x for x in names if ("flash" in x or "gemma" in x) and not any(k in x for k in ("tts", "image", "live", "audio", "embed"))][:10]:
    t = time.time()
    body = {"contents": [{"parts": [{"text": "Return JSON {\"ok\": true}"}]}], "generationConfig": {"responseMimeType": "application/json"}}
    try:
        r = json.load(urllib.request.urlopen(urllib.request.Request(f"{G}/models/{n}:generateContent", data=json.dumps(body).encode(), headers={"x-goog-api-key": K, "Content-Type": "application/json"}), timeout=90))
        print(f"OK  {n} {time.time()-t:.1f}s", r["candidates"][0]["content"]["parts"][0]["text"][:40])
    except urllib.error.HTTPError as e:
        print(f"ERR {n} {e.code} {time.time()-t:.1f}s", e.read().decode()[:600].replace("\n", " "))
    except Exception as e:
        print(f"ERR {n} {time.time()-t:.1f}s {e}")
