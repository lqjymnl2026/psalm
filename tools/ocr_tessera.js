// OCR via tesseract.js（Node，离线模型在 data/tessdata）
// 用法: node ocr_tessera.js <图片路径> [PSM] [--json]
//   --json → 输出带坐标的行数组 [{text,x,y,w,h,conf}]
const path = require("path");
const { createWorker } = require("tesseract.js");
const ROOT = path.resolve(__dirname, "..");
const langPath = path.join(ROOT, "data", "tessdata");
const img = process.argv[2];
const psm = process.argv[3] || "4";
const wantJson = process.argv.includes("--json");
if (!img) { console.error("usage: ocr_tessera.js <image> [psm] [--json]"); process.exit(2); }
(async () => {
  const worker = await createWorker("chi_sim+eng", 1, {
    langPath,
    gzip: true,
    cachePath: path.join(ROOT, "data", "tessdata", ".cache"),
    corePath: path.join(ROOT, "node_modules", "tesseract.js-core"),
    logger: () => {},
  });
  await worker.setParameters({ tessedit_pageseg_mode: psm });
  // 必须开启 blocks 输出才有行坐标
  const { data } = await worker.recognize(img, {}, { blocks: true });
  if (wantJson) {
    const out = [];
    const words = [];
    const push = (l) => {
      if (l && l.text && l.text.trim()) {
        out.push({
          text: l.text.trim(),
          x: l.bbox ? l.bbox.x0 : 0,
          y: l.bbox ? l.bbox.y0 : 0,
          w: l.bbox ? l.bbox.x1 - l.bbox.x0 : 0,
          h: l.bbox ? l.bbox.y1 - l.bbox.y0 : 0,
          conf: l.confidence || 0,
        });
      }
    };
    const wpush = (l) => {
      if (l && l.text && l.text.trim()) {
        words.push({
          text: l.text.trim(),
          x: l.bbox ? l.bbox.x0 : 0,
          y: l.bbox ? l.bbox.y0 : 0,
          w: l.bbox ? l.bbox.x1 - l.bbox.x0 : 0,
          h: l.bbox ? l.bbox.y1 - l.bbox.y0 : 0,
          conf: l.confidence || 0,
        });
      }
    };
    (data.lines || []).forEach(push);
    if (data.blocks) {
      data.blocks.forEach((b) => {
        (b.lines || []).forEach(push);
        (b.paragraphs || []).forEach((p) => (p.lines || []).forEach((ln) => {
          push(ln);
          (ln.words || []).forEach(wpush);
        }));
      });
    }
    out.sort((a, b) => (a.y - b.y) || (a.x - b.x));
    process.stdout.write(JSON.stringify({ text: data.text || "", lines: out, words }));
  } else {
    process.stdout.write(data.text || "");
  }
  await worker.terminate();
})().catch((e) => { console.error("OCR_FAIL:", e && e.message); process.exit(1); });
