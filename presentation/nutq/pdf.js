// nutq.html ni A4 PDF ga aylantiradi va sahifa to'lib ketmaganini tekshiradi.
// Ishlatish: python build.py && node pdf.js [chiqish.pdf]
const path = require("path");
const { chromium } = require(process.env.PLAYWRIGHT_PATH || "playwright");

const out = path.resolve(process.argv[2] || path.join(__dirname, "ANDTI-Talent-Hub-nutq.pdf"));

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  const page = await browser.newPage();
  await page.goto("file://" + path.join(__dirname, "nutq.html"));
  await page.evaluate(() => document.fonts.ready);
  const overflow = await page.evaluate(() =>
    [...document.querySelectorAll(".page")]
      .map((p, i) => {
        const limit = p.getBoundingClientRect().bottom - 20 * 3.78; // footer zonasi
        const last = [...p.children].filter((c) => !["FOOTER"].includes(c.tagName) && !c.classList.contains("final"));
        const bottom = Math.max(...last.map((c) => c.getBoundingClientRect().bottom));
        return bottom > limit ? `${i + 1}-sahifa ${Math.round(bottom - limit)}px oshib ketdi` : null;
      })
      .filter(Boolean)
  );
  if (overflow.length) console.warn("OGOHLANTIRISH:", overflow.join("; "));
  await page.pdf({ path: out, format: "A4", printBackground: true, preferCSSPageSize: true });
  await browser.close();
  console.log("PDF:", out);
})();
