const path = require("path");
const { createWorker } = require("tesseract.js");
const ROOT = "/Users/macbook/Documents/Codex/2026-08-10/new-chat/hymn-center-2";
const img = process.argv[2];
const psm = process.argv[3] || "6";
(async () => {
  const worker = await createWorker("chi_sim+eng", 1, {
    langPath: path.join(ROOT, "data", "tessdata"),
    gzip: true,
    cachePath: path.join(ROOT, "data", "tessdata", ".cache"),
    corePath: path.join(ROOT, "node_modules", "tesseract.js-core"),
    logger: () => {},
  });
  await worker.setParameters({ tessedit_pageseg_mode: psm });
  const { data } = await worker.recognize(img);
  process.stdout.write(data.text || "");
  await worker.terminate();
})().catch((e) => { console.error("FAIL:", e && e.message); process.exit(1); });
