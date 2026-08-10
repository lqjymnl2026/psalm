// 持久 OCR 服务：保持 tesseract worker 常驻，批量识别多张图片（提速）
// 用法: node ocr_server.js [port]   → POST /ocr {paths:[...]} → {texts:[...]}
const http = require("http");
const path = require("path");
const { createWorker } = require("tesseract.js");
const ROOT = path.resolve(__dirname, "..");
const PORT = Number(process.env.OCR_PORT || process.argv[2] || 8799);

let workerPromise = null;
function getWorker() {
  if (!workerPromise) {
    workerPromise = createWorker("chi_sim+eng", 1, {
      langPath: path.join(ROOT, "data", "tessdata"),
      gzip: true,
      cachePath: path.join(ROOT, "data", "tessdata", ".cache"),
      corePath: path.join(ROOT, "node_modules", "tesseract.js-core"),
      logger: () => {},
    });
  }
  return workerPromise;
}

const server = http.createServer((req, res) => {
  const respond = (code, obj) => {
    res.writeHead(code, { "Content-Type": "application/json" });
    res.end(JSON.stringify(obj));
  };
  if (req.method === "GET" && req.url === "/health") return respond(200, { ok: true });
  if (req.method === "POST" && req.url.startsWith("/ocr")) {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", async () => {
      try {
        const { paths } = JSON.parse(body);
        if (!Array.isArray(paths) || !paths.length) return respond(400, { error: "paths required" });
        const worker = await getWorker();
        await worker.setParameters({ tessedit_pageseg_mode: "4" });
        const out = [];
        for (const p of paths) {
          const { data } = await worker.recognize(p);
          out.push(data.text || "");
        }
        respond(200, { texts: out });
      } catch (e) {
        respond(500, { error: String((e && e.message) || e) });
      }
    });
    return;
  }
  respond(404, { error: "not found" });
});
server.listen(PORT, "127.0.0.1", () => {
  process.stdout.write("ocr-server ready on 127.0.0.1:" + PORT + "\n");
});
process.on("SIGTERM", () => process.exit(0));
