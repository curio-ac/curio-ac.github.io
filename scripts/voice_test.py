"""בדיקת קולות: מייצר את סרטון התמנון בכמה מנועי קול, לעברית ולאנגלית.
שימוש: python scripts/voice_test.py <engine>   (gemini | piper | chatterbox | kokoro)
פלט: samples/<lang>-<engine>.wav
"""
import base64, json, os, re, sys, urllib.request, wave

HE = "לתמנון יש שלושה לבבות. וגם דם כחול. שני לבבות מזרימים דם לזימים, והשלישי לשאר הגוף. הדם כחול כי הוא נושא חמצן בעזרת נחושת, ולא בעזרת ברזל כמו אצלנו. כשני שלישים מתאי העצב שלו נמצאים בזרועות. כל זרוע חושבת קצת בעצמה."
EN = "An octopus has three hearts. And blue blood. Two hearts pump blood to the gills, and the third to the rest of the body. The blood is blue because it carries oxygen using copper, not iron like ours. About two thirds of its neurons are in its arms. Each arm kind of thinks for itself."
os.makedirs("samples", exist_ok=True)
engine = sys.argv[1]


def save_pcm(path, pcm, rate):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)


def save_float(path, samples, rate):
    import numpy as np
    save_pcm(path, (np.clip(np.asarray(samples).flatten(), -1, 1) * 32767).astype("<i2").tobytes(), rate)


if engine == "gemini":
    key = os.environ["GEMINI_API_KEY"]
    models = ["gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts"]
    for lang, text, voice in [("he", HE, "Kore"), ("en", EN, "Kore"), ("he", HE, "Puck"), ("en", EN, "Puck")]:
        style = "Read this like an energetic, fast-paced TikTok science narrator:" if lang == "en" else "קרא את זה כמו קריין טיקטוק אנרגטי ומהיר של מדע:"
        body = {"contents": [{"parts": [{"text": f"{style}\n{text}"}]}],
                "generationConfig": {"responseModalities": ["AUDIO"],
                                     "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
        for m in models:
            req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                                         data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
            try:
                res = json.load(urllib.request.urlopen(req, timeout=120))
                pcm = base64.b64decode(res["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
                save_pcm(f"samples/{lang}-gemini-{voice.lower()}.wav", pcm, 24000)
                print(f"✅ {lang} gemini {voice} ({m})"); break
            except urllib.error.HTTPError as e:
                print(f"   {m}: {e.code} {e.read()[:200]}")

elif engine == "piper":
    from phonikud_tts import Phonikud, phonemize, Piper
    ph = Phonikud("phonikud-1.0.int8.onnx")
    piper = Piper("tts-model.onnx", "tts-model.config.json")
    samples, rate = piper.create(phonemize(ph.add_diacritics(HE)), is_phonemes=True)
    save_float("samples/he-piper.wav", samples, rate); print("✅ he piper")

elif engine == "chatterbox":
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    from phonikud_onnx import Phonikud
    from phonikud import lexicon
    model = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
    he = re.sub(fr"[{lexicon.NON_STANDARD_DIAC}]", "", Phonikud("phonikud-1.0.int8.onnx").add_diacritics(HE))
    for lang, text in [("he", he), ("en", EN)]:
        wav = model.generate(text, language_id=lang, audio_prompt_path="female1.wav")
        save_float(f"samples/{lang}-chatterbox.wav", wav.squeeze().numpy(), model.sr); print(f"✅ {lang} chatterbox")

elif engine == "kokoro":
    import numpy as np
    from kokoro import KPipeline
    p = KPipeline(lang_code="a")
    for voice in ["af_heart", "am_michael"]:
        audio = np.concatenate([a for _, _, a in p(EN, voice=voice, speed=1.1)])
        save_float(f"samples/en-kokoro-{voice}.wav", audio, 24000); print(f"✅ en kokoro {voice}")
