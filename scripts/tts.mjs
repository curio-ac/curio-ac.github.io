// מייצר קריינות רציפה אחת לכל סרטון ב-content/videos.json (ElevenLabs, עם תזמון לכל מילה).
// פלט: audio/<id>.mp3 + audio/<id>.json (מילים עם זמני התחלה/סיום + גבולות שקופיות).
// סרטונים שכבר יש להם קבצים מדולגים, כך שלא מבזבזים קרדיטים פעמיים.
import fs from "node:fs";

const KEY = process.env.ELEVENLABS_API_KEY;
if (!KEY) { console.log("⚠️  ELEVENLABS_API_KEY לא מוגדר - מדלג."); process.exit(0); }

const API = "https://api.elevenlabs.io/v1";
const H = { "xi-api-key": KEY, "Content-Type": "application/json" };
const VOICE = process.env.VOICE_ID || "EXAVITQu4vr4xnSDxMaL"; // Sarah
const MODEL = process.env.MODEL_ID || "eleven_v4";
const SPEED = +(process.env.SPEED || 1.15);
const videos = JSON.parse(fs.readFileSync("content/videos.json", "utf8"));
fs.mkdirSync("audio", { recursive: true });

async function tts(text) {
  const attempts = [{ speed: SPEED }, null]; // אם המודל לא תומך במהירות - בלי
  for (const vs of attempts) {
    const body = { text, model_id: MODEL, language_code: "he" };
    if (vs) body.voice_settings = vs;
    const r = await fetch(`${API}/text-to-speech/${VOICE}/with-timestamps?output_format=mp3_44100_64`, { method: "POST", headers: H, body: JSON.stringify(body) });
    if (r.ok) return r.json();
    const err = await r.text();
    if (!vs || r.status === 401 || /quota|credit/i.test(err)) throw new Error(`${r.status} ${err}`);
    console.log(`   ניסיון עם speed נכשל (${r.status}): ${err.slice(0, 200)}`);
  }
}

function words(al) {
  const out = []; let cur = null;
  al.characters.forEach((c, i) => {
    if (/\s/.test(c)) { if (cur) out.push(cur); cur = null; return; }
    if (!cur) cur = [c, al.character_start_times_seconds[i], al.character_end_times_seconds[i]];
    else { cur[0] += c; cur[2] = al.character_end_times_seconds[i]; }
  });
  if (cur) out.push(cur);
  return out.map(([w, s, e]) => [w, +s.toFixed(3), +e.toFixed(3)]);
}

let made = 0, used = 0;
for (const v of videos) {
  if (fs.existsSync(`audio/${v.id}.mp3`) && fs.existsSync(`audio/${v.id}.json`)) continue;
  const text = v.slides.join(" ");
  const res = await tts(text);
  const w = words(res.alignment);
  // גבולות שקופיות לפי מספר מילים
  const b = []; let n = 0;
  for (const s of v.slides) { b.push(n); n += s.trim().split(/\s+/).length; }
  if (n !== w.length) console.log(`   ⚠️ ${v.id}: ${w.length} מילים בתזמון מול ${n} בטקסט`);
  fs.writeFileSync(`audio/${v.id}.mp3`, Buffer.from(res.audio_base64, "base64"));
  fs.writeFileSync(`audio/${v.id}.json`, JSON.stringify({ w, b }));
  made++; used += text.length;
  console.log(`✅ ${v.id} (${w.at(-1)?.[2]}s)`);
}
console.log(`\nסיום: ${made} סרטונים, כ-${used} תווים.`);
