// בונה dist/index.html עצמאי: התבנית + התוכן + הקריינות מוטמעת (לתצוגה מקדימה).
import fs from "node:fs";
const videos = JSON.parse(fs.readFileSync("content/videos.json", "utf8"))
  .filter(v => fs.existsSync(`audio/${v.id}.mp3`))
  .map(v => ({ ...v, tim: JSON.parse(fs.readFileSync(`audio/${v.id}.json`, "utf8")) }));
const aud = Object.fromEntries(videos.map(v => [v.id, "data:audio/mpeg;base64," + fs.readFileSync(`audio/${v.id}.mp3`).toString("base64")]));
const html = fs.readFileSync("app/template.html", "utf8")
  .replace("/*DATA*/", () => `const V=${JSON.stringify(videos)};\nconst AUD=${JSON.stringify(aud)};`);
fs.mkdirSync("dist", { recursive: true });
fs.writeFileSync("dist/index.html", html);
console.log(`dist/index.html: ${videos.length} סרטונים, ${(html.length / 1e6).toFixed(1)}MB`);
