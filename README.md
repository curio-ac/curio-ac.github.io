# Curio

פיד לימודי בסגנון טיקטוק.

- `content/videos.json` – הסרטונים (שקופיות טקסט + קישור למקור)
- `scripts/tts.mjs` – יצירת קריינות ב-ElevenLabs לכל שקופית → `audio/<id>-<n>.mp3`
- `.github/workflows/tts.yml` – מריץ את הסקריפט ב-GitHub Actions (מפתח ב-Secret בשם `ELEVENLABS_API_KEY`)
- `prototype.html` – אב-הטיפוס הראשון
