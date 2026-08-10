// OCR via tesseract.js（Node，离线模型在 data/tessdata）
// 用法: node ocr_tessera.js <图片路径> [langPath]
const path = require("path");
const { createWorker } = require("tesseract.js");
const ROOT = path.resolve(__dirname, "..");
const langPath = process.argv[3] || path.join(ROOT, "data", "tessdata");
const img = process.argv[2];
if (!img) { console.error("usage: ocr_tessera.js <image> [langPath]"); process.exit(2); }
(async () => {
  const worker = await createWorker("chi_sim+eng", 1, {
    langPath,
    gzip: true,
    cachePath: path.join(ROOT, "data", "tessdata", ".cache"),
    corePath: path.join(ROOT, "node_modules", "tesseract.js-core"),
    logger: () => {},
  });
  const { data } = await worker.recognize(img);
  process.stdout.write(data.text || "");
  await worker.terminate();
})().catch((e) => { console.error("OCR_FAIL:", e && e.message); process.exit(1); });
