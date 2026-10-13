// video.html ni kadrma-kadr suratga olib, ffmpeg orqali MP4 ga yig'adi.
// Ishlatish: node render.js [chiqish.mp4] [fps]   (boshqa sahifa uchun: VIDEO_PAGE=pitch.html)
//   PLAYWRIGHT_PATH, CHROMIUM_PATH, FFMPEG_PATH muhit o'zgaruvchilari bilan yo'llarni almashtirish mumkin.
const path = require("path");
const { spawn } = require("child_process");
const { chromium } = require(process.env.PLAYWRIGHT_PATH || "playwright");

const out = path.resolve(process.argv[2] || "andti-talent-hub.mp4");
const fps = Number(process.argv[3] || 30);
const ffmpegPath = process.env.FFMPEG_PATH || "ffmpeg";

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await page.goto("file://" + path.join(__dirname, process.env.VIDEO_PAGE || "video.html") + "?render=1");
  await page.evaluate(() => window.ready);
  const duration = await page.evaluate(() => window.DURATION);
  const total = Math.round(duration * fps);

  const ffmpeg = spawn(ffmpegPath, [
    "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(fps), "-i", "-",
    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out,
  ], { stdio: ["pipe", "inherit", "inherit"] });
  const finished = new Promise((resolve, reject) => {
    ffmpeg.on("close", (code) => (code === 0 ? resolve() : reject(new Error("ffmpeg kodi: " + code))));
  });

  for (let i = 0; i < total; i++) {
    await page.evaluate((t) => window.seek(t), i / fps);
    const frame = await page.screenshot({ type: "jpeg", quality: 92 });
    if (!ffmpeg.stdin.write(frame)) await new Promise((r) => ffmpeg.stdin.once("drain", r));
    if (i % (fps * 5) === 0) process.stdout.write(`\r${Math.round((i / total) * 100)}%  (${i}/${total})`);
  }
  ffmpeg.stdin.end();
  await finished;
  await browser.close();
  console.log("\nTayyor: " + out);
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
