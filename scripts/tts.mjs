// מייצר קריינות לכל שקופית ב-content/videos.json בעזרת ElevenLabs.
// קבצים שכבר קיימים ב-audio/ מדולגים, כך שלא מבזבזים קרדיטים פעמיים.
import fs from "node:fs";

const KEY = process.env.ELEVENLABS_API_KEY;
if (!KEY) { console.log("⚠️  ELEVENLABS_API_KEY לא מוגדר - מדלג."); process.exit(0); }

const API = "https://api.elevenlabs.io/v1";
const H = { "xi-api-key": KEY, "Content-Type": "application/json" };
const videos = JSON.parse(fs.readFileSync("content/videos.json", "utf8"));
fs.mkdirSync("audio", { recursive: true });

// --- בחירת קול ---
let voiceId = process.env.VOICE_ID;
if (!voiceId) {
  const r = await fetch(`${API}/voices`, { headers: H });
  if (!r.ok) throw new Error(`voices: ${r.status} ${await r.text()}`);
  const { voices } = await r.json();
  console.log("קולות זמינים:\n" + voices.map(v => `  ${v.voice_id}  ${v.name}  ${JSON.stringify(v.labels || {})}`).join("\n"));
  const pref = ["Sarah", "Rachel", "Aria", "Laura", "Jessica"];
  const v = pref.map(n => voices.find(x => x.name?.startsWith(n))).find(Boolean) || voices[0];
  voiceId = v.voice_id;
  console.log(`🎙️  קול שנבחר: ${v.name} (${voiceId})`);
}

// --- בחירת מודל: הראשון מהרשימה שעובד ---
const models = (process.env.MODEL_ID ? [process.env.MODEL_ID] : []).concat(["eleven_v4", "eleven_v3", "eleven_multilingual_v2"]);
let model = null;

async function tts(text) {
  const tryModels = model ? [model] : models;
  for (const m of tryModels) {
    const r = await fetch(`${API}/text-to-speech/${voiceId}?output_format=mp3_44100_64`, {
      method: "POST", headers: H,
      body: JSON.stringify({ text, model_id: m, language_code: "he" }),
    });
    if (r.ok) { if (!model) { model = m; console.log(`🧠 מודל: ${m}`); } return Buffer.from(await r.arrayBuffer()); }
    const err = await r.text();
    if (model || r.status === 401 || /quota|credit/i.test(err)) throw new Error(`${r.status} ${err}`);
    console.log(`   מודל ${m} נכשל (${r.status}), מנסה הבא...`);
  }
  throw new Error("אף מודל לא עבד");
}

let made = 0, used = 0;
for (const v of videos) {
  for (let i = 0; i < v.slides.length; i++) {
    const f = `audio/${v.id}-${i}.mp3`;
    if (fs.existsSync(f)) continue;
    fs.writeFileSync(f, await tts(v.slides[i]));
    made++; used += v.slides[i].length;
    console.log(`✅ ${f}`);
  }
}
console.log(`\nסיום: ${made} קבצים חדשים, כ-${used} תווים.`);
