/* 赞美诗资料智能整理中心 · 前端 */
"use strict";

/* ---------------- 工具 ---------------- */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (k === "html") node.innerHTML = v;
    else if (v !== null && v !== undefined) node.setAttribute(k, v);
  }
  for (const c of [].concat(children)) {
    if (c === null || c === undefined) continue;
    node.append(c.nodeType ? c : document.createTextNode(c));
  }
  return node;
}

async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (state.token) headers["X-Admin-Token"] = state.token;
  const res = await fetch(path, { ...opts, headers });
  let data = null;
  try { data = await res.json(); } catch (e) { /* ignore */ }
  if (res.status === 401 && !path.startsWith("/api/login")) {
    localStorage.removeItem("hymn_token");
    state.token = "";
    showLogin();
    throw new Error((data && data.msg) || "需要登录");
  }
  if (!res.ok || (data && data.ok === false && !data.summary)) {
    throw new Error((data && data.msg) || `请求失败 ${res.status}`);
  }
  return data;
}

function toast(msg, type = "ok", ms = 3600) {
  const wrap = $("#toasts");
  const t = el("div", { class: `toast ${type}` }, msg);
  wrap.append(t);
  setTimeout(() => { t.remove(); }, ms);
}

const STATUS_LABELS = { pending: "待审核", candidate: "候选", shortlist: "初选", final: "终选", published: "最终出版", rejected: "淘汰", merged: "已合并" };
const STATUS_CLASS = { pending: "gray", candidate: "blue", shortlist: "gold", final: "green", published: "green", rejected: "red", merged: "gray" };

function statusChip(s) {
  const v = s.status || "pending";
  return `<span class="chip ${STATUS_CLASS[v]} status-chip">${STATUS_LABELS[v] || v}</span>`;
}
function stars(n, max = 5) {
  n = Math.round(Number(n) || 0);
  return "★".repeat(Math.max(0, Math.min(max, n))) + "☆".repeat(Math.max(0, max - Math.min(max, n)));
}
function starsHtml(n) {
  return `<span class="stars">${stars(n)}</span>`;
}
function chips(arr, cls = "") {
  return (arr || []).map((x) => `<span class="chip ${cls}">${esc(x)}</span>`).join("");
}
function flagsHtml(song) {
  return (song.flags || []).map((f) => {
    const cls = f.includes("重复") ? "red" : f.includes("不完整") ? "gold" : "gray";
    return `<span class="badge ${cls}">${esc(f)}</span>`;
  }).join("");
}
function short(s, n = 26) { s = s || ""; return s.length > n ? s.slice(0, n) + "…" : s; }
function fmtSize(b) { return b > 1024 * 1024 ? (b / 1024 / 1024).toFixed(1) + " MB" : b > 1024 ? (b / 1024).toFixed(1) + " KB" : b + " B"; }

/* ---------------- 全局状态 ---------------- */
const state = {
  stats: null, cats: { themes: [], scenarios: [], types: [], statuses: {} },
  settings: null, page: "dashboard",
  lib: { q: "", theme: "", scenario: "", type: "", status: "", rating: 0, source: "", needsReview: false, dup: false, sort: "number", page: 1, size: 50, total: 0 },
  selected: new Set(),
  reviewTab: "pending",
};

/* ---------------- 路由 ---------------- */
function navigate() {
  const h = (location.hash || "#/dashboard").replace(/^#\//, "");
  const page = h.split("?")[0] || "dashboard";
  state.page = page;
  $$(".nav-item").forEach((a) => a.classList.toggle("active", a.dataset.page === page));
  $$(".mn-item").forEach((a) => a.classList.toggle("active", a.dataset.page === page));
  const meta = {
    dashboard: ["工作台", "曲目总览与快速入口"],
    collection: ["曲目收集", "批量导入 Excel/CSV/PDF/Word/图片/音频 + 手工添加"],
    organize: ["智能整理", "AI/OCR 识别 · 自动分类 · 去重"],
    library: ["曲目库", "搜索 / 筛选 / 排序 / 编辑"],
    review: ["筛选审核", "评分 · 评论 · 入选 / 淘汰"],
    export: ["导出中心", "Excel / Word / PDF / CSV 一键导出"],
  }[page] || ["工作台", ""];
  $("#pageTitle").textContent = meta[0];
  $("#pageSub").textContent = meta[1];
  const renderer = { dashboard: renderDashboard, collection: renderCollection, organize: renderOrganize, library: renderLibrary, review: renderReview, export: renderExport }[page] || renderDashboard;
  renderer().catch((e) => { console.error(e); toast("页面加载失败：" + e.message, "err"); });
}

/* ---------------- 共享渲染 ---------------- */
function renderBars(items, color = "") {
  if (!items || !items.length) return `<div class="muted small">暂无数据</div>`;
  const max = Math.max(...items.map((i) => i[1]));
  return items.map(([label, v]) => `
    <div class="bar-row">
      <span class="bar-label">${esc(label)}</span>
      <div class="bar-track"><div class="bar-fill ${color}" style="width:${max ? (v / max) * 100 : 0}%"></div></div>
      <span class="bar-val">${v}</span>
    </div>`).join("");
}

function chipSelectHTML(name, options, selected = []) {
  return `<div class="chip-select" data-chipselect="${name}">
    ${options.map((o) => `<span class="chip-opt ${selected.includes(o) ? "on" : ""}" data-val="${esc(o)}">${esc(o)}</span>`).join("")}
  </div>`;
}
function bindChipSelect(container) {
  container.querySelectorAll("[data-chipselect]").forEach((box) => {
    box.addEventListener("click", (e) => {
      const opt = e.target.closest(".chip-opt");
      if (!opt) return;
      opt.classList.toggle("on");
    });
  });
}
function chipSelectValue(name) {
  const box = document.querySelector(`[data-chipselect="${name}"]`);
  if (!box) return [];
  return Array.from(box.querySelectorAll(".chip-opt.on")).map((o) => o.dataset.val);
}
function resetChipSelect(name) {
  const box = document.querySelector(`[data-chipselect="${name}"]`);
  if (box) box.querySelectorAll(".chip-opt.on").forEach((o) => o.classList.remove("on"));
}

/* ---------------- 工作台 ---------------- */
async function renderDashboard() {
  const d = await api("/api/bootstrap");
  state.cats = d.categories; state.settings = d.settings; state.stats = d.stats;
  updatePills(d);
  const st = d.stats, s = st.status;
  const selectedCount = ["candidate", "shortlist", "final", "published"].reduce((a, k) => a + (s[k] || 0), 0);
  const latest = st.imports[0];
  const cards = [
    { n: st.total, label: "总曲目", foot: `已合并 ${st.merged}`, c: "" },
    { n: st.needsReview, label: "待审核 / 待确认", foot: "AI 置信度不足或资料待补", c: "c-amber" },
    { n: st.duplicateGroups, label: "疑似重复组", foot: `涉及 ${st.duplicates} 首`, c: "c-red" },
    { n: selectedCount, label: "已入选", foot: `候选→出版`, c: "c-green" },
    { n: st.incomplete, label: "资料不完整", foot: "缺歌名或歌词", c: "c-gold" },
    { n: s.rejected || 0, label: "已淘汰", foot: "不入库", c: "c-red" },
    { n: st.avgRating, label: "平均评分", foot: "满分 5.0", c: "c-purple" },
  ];
  const stageFunnel = [
    ["候选", s.candidate || 0], ["初选", s.shortlist || 0], ["终选", s.final || 0], ["最终出版", s.published || 0],
  ];
  let importCard = `<div class="card card-pad section"><div class="card-title">最近导入
    <span class="sub">${latest ? `批次 ${esc(latest.batch)} · ${esc(latest.time)}` : "暂无导入记录"}</span></div>`;
  if (latest) {
    importCard += `<div class="import-summary">
      <div class="import-box ok"><div class="ib-num">${latest.ok}</div><div class="ib-label">✅ 识别成功</div></div>
      <div class="import-box warn"><div class="ib-num">${latest.needsReview}</div><div class="ib-label">⚠️ 需人工确认</div></div>
      <div class="import-box dup"><div class="ib-num">${latest.duplicates}</div><div class="ib-label">🔄 疑似重复</div></div>
      <div class="import-box bad"><div class="ib-num">${latest.incomplete}</div><div class="ib-label">❌ 资料不完整</div></div>
    </div>
    <div class="muted small">${esc(latest.files.join("、"))} · 共导入 ${latest.total} 首</div>
    <div class="mt12 flex">
      <button class="btn btn-sm btn-primary" data-goto="library">去曲目库查看</button>
      <button class="btn btn-sm" data-goto="organize">处理重复 / 整理</button>
    </div>`;
  } else {
    importCard += `<div class="muted small">还没有导入记录。可在“曲目收集”页拖入 Excel/CSV/PDF/Word/图片/音频文件。</div>`;
  }
  importCard += `</div>`;

  $("#content").innerHTML = `
    <div class="stats-grid">${cards.map((c) => `
      <div class="stat-card ${c.c}"><div class="num">${c.n}</div><div class="label">${c.label}</div><div class="foot">${c.foot}</div></div>`).join("")}
    </div>
    <div class="grid-3-2 section">
      ${d.categories && d.categories.hymnbook ? `
      <div class="card card-pad">
        <div class="card-title">圣诗分类（大类） <span class="sub">编定分类</span></div>
        ${renderBars((st.categories || []).slice(0, 8), "gold")}
        <div class="card-title mt16">细类分布 <span class="sub">Top 8</span></div>
        ${renderBars((st.subcategories || []).slice(0, 8), "green")}
      </div>` : `
      <div class="card card-pad">
        <div class="card-title">圣经主题分布 <span class="sub">Top 10</span></div>
        ${renderBars(st.themes.slice(0, 10))}
      </div>`}
      <div class="card card-pad">
      <div class="card card-pad">
        <div class="card-title">音乐类型</div>
        ${renderBars(st.types.slice(0, 8), "gold")}
        <div class="card-title mt16">崇拜场景 <span class="sub">Top 6</span></div>
        ${renderBars(st.scenarios.slice(0, 6), "green")}
      </div>
    </div>
    <div class="card card-pad section">
      <div class="card-title">编选进度（候选 → 最终出版）</div>
      <div class="progress mb8"><div class="bar" style="width:${st.total ? (selectedCount / st.total * 100).toFixed(1) : 0}%"></div></div>
      <div class="grid-2">${renderBars(stageFunnel, "gold")}</div>
    </div>
    ${importCard}
    ${(st.uploaders && st.uploaders.length) ? `
    <div class="card card-pad">
      <div class="card-title">上传人统计 <span class="sub">用于对接收集人</span></div>
      ${renderBars(st.uploaders.slice(0, 10), "gold")}
    </div>` : ""}
    <div class="card card-pad">
      <div class="card-title">快捷入口</div>
      <div class="flex flex-wrap">
        <button class="btn btn-primary" data-goto="collection">📥 批量导入</button>
        <button class="btn btn-gold" id="dashMobile">📱 手机快捷收集</button>
        <button class="btn" data-goto="organize">🧠 一键智能整理</button>
        <button class="btn" data-goto="review">✅ 去审核</button>
        <button class="btn btn-gold" data-goto="export">📤 导出中心</button>
      </div>
    </div>`;
  bindGoto();
}

function bindGoto() {
  document.querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click", () => { location.hash = "#/" + b.dataset.goto; }));
  const dm = $("#dashMobile");
  if (dm) dm.addEventListener("click", () => { location.href = "/mobile"; });
}

function updatePills(d) {
  const ocr = d.ocrAvailable;
  const ai = !!(d.settings && d.settings.openaiKey);
  const op = $("#ocrPill"), ap = $("#aiPill");
  const engs = (d.ocrEngines && d.ocrEngines.length) ? d.ocrEngines.join("+") : (d.ocrEngine || "");
  op.textContent = "OCR：" + (engs ? engs + "已就绪" : "未就绪");
  op.classList.toggle("ok", !!ocr);
  ap.textContent = "AI：" + (ai ? "已配置" : "本地引擎");
  ap.classList.toggle("ok", !!ai);
}

/* ---------------- 曲目收集 ---------------- */
async function renderCollection() {
  const d = await api("/api/bootstrap");
  state.cats = d.categories; state.settings = d.settings;
  updatePills(d);
  const lanUrls = (d.lanUrls || []);
  const lanTip = lanUrls.length
    ? `<div class="card card-pad section" style="border-color:#bcd8c6;background:#f0faf4">
        <div class="card-title">📱 手机收集 <span class="sub">手机与 Mac 连同一 WiFi</span></div>
        <div class="lan-tip">用手机浏览器打开下面地址，可直接<b>拍照上传</b>老赞美诗照片 / 录入新歌：<br>
        ${lanUrls.map((u) => `<b class="mono">${esc(u)}</b>`).join("<br>")}<br>
        <span class="muted">手机端支持：拍照上传 · 相册选择 · 手工新增</span><br>
        <span class="muted">💡 在手机浏览器点「分享 / 更多 → 添加到主屏幕」，即可像 App 一样全屏使用。</span></div>
      </div>`
    : `<div class="card card-pad section" style="background:#fffaf0">
        <div class="card-title">📱 手机收集</div>
        <div class="lan-tip muted">当前仅本机可访问。如需手机收集，请用 <span class="mono">./run.sh --lan</span> 或双击「启动-局域网.command」启动。</div>
      </div>`;
  $("#content").innerHTML = `
    ${lanTip}
    <div class="card card-pad section">
      <div class="card-title">批量导入
        <span class="sub">支持 Excel(.xlsx/.csv) · PDF · Word(.docx) · 图片 · 音频，可多选</span>
      </div>
      <label class="dropzone" id="dropzone" for="fileInput">
        <div class="dz-icon">📂</div>
        <div class="dz-title">拖拽文件到这里，或点击选择文件</div>
        <div class="dz-sub">Excel 列名自动识别（歌名/歌曲名称/title…）· PDF/Word 自动切分曲目 · 图片/音频进入“待人工确认”</div>
      </label>
      <div class="mob-upload-btns">
        <label class="btn btn-primary" for="cameraInput"><span class="bu-ico">📷</span>拍照上传诗歌</label>
        <label class="btn" for="galleryInput"><span class="bu-ico">🖼️</span>相册 / 文件</label>
      </div>
      <input type="file" id="fileInput" multiple class="vh"
        accept=".xlsx,.xlsm,.xls,.csv,.pdf,.docx,.doc,.jpg,.jpeg,.png,.bmp,.webp,.gif,.tif,.tiff,.mp3,.wav,.m4a,.aac,.flac,.ogg">
      <input type="file" id="cameraInput" class="vh" accept="image/*" capture="environment">
      <input type="file" id="galleryInput" multiple class="vh"
        accept=".xlsx,.xlsm,.xls,.csv,.pdf,.docx,.doc,.jpg,.jpeg,.png,.bmp,.webp,.gif,.tif,.tiff,.mp3,.wav,.m4a,.aac,.flac,.ogg">
      <div id="importProgress" class="mt12" hidden><span class="spin"></span>正在导入并智能整理，请稍候…</div>
      <div id="importResult" class="mt12"></div>
      <div class="mt12 flex flex-wrap small muted">
        <a class="btn btn-sm" href="/api/songs/template" download="赞美诗导入模板.xlsx">📄 下载导入模板</a>
        <a class="btn btn-sm" href="/files/samples/赞美诗导入示例.xlsx" download>示例 Excel</a>
        <a class="btn btn-sm" href="/files/samples/赞美诗集示例.pdf" download>示例 PDF</a>
        <span>提示：模板含「上传人 / 歌名 / 首句 / 歌词 / 作者 / 作曲 / 曲调 / 来源 / 备注 / 大类 / 细类」；上传人建议必填（用于对接），大类/细类留空会自动分类。</span>
      </div>
    </div>

    <div class="card card-pad section">
      <div class="card-title">＋ 手工新增曲目
        <button class="btn btn-gold btn-sm" id="btnMobileCollect" style="margin-left:auto">📱 快捷收集页</button>
        <button class="btn btn-primary btn-sm" id="btnOcrFill">📷 拍照识别填表</button>
      </div>
      <div class="card card-pad mb16" id="ocrPanel" hidden style="background:#f6f9ff">
        <div class="card-title">📷 拍照识别结果 <span class="sub" id="ocrEngineTag"></span>
          <button class="btn btn-sm btn-ghost" id="ocrDiscard">放弃</button>
        </div>
        <div class="flex flex-wrap" style="align-items:flex-start">
          <img id="ocrImg" class="ocr-img" alt="照片预览">
          <div style="flex:1;min-width:220px">
            <div class="hint" id="ocrNote"></div>
            <div class="mt8 small muted">识别到的文字（供核对）：</div>
            <pre id="ocrText" class="ocr-text"></pre>
          </div>
        </div>
        <div class="mt8 hint">已自动填入上方表单的<b>歌名 / 首句 / 歌词</b>，请核对或修改后点「保存曲目」。</div>
      </div>
      <div class="form-grid">
        <div class="form-group"><label>歌曲名称 *</label><input id="f_title" placeholder="例：奇异恩典"></div>
        <div class="form-group"><label>首句</label><input id="f_first" placeholder="例：奇异恩典，何等甘甜"></div>
        <div class="form-group"><label>编号</label><input id="f_number" placeholder="留空自动编号"></div>
        <div class="form-group"><label>作者（作词）</label><input id="f_lyricist" placeholder="例：John Newton"></div>
        <div class="form-group"><label>作曲</label><input id="f_composer" placeholder="例：NEW BRITAIN"></div>
        <div class="form-group"><label>译者</label><input id="f_translator"></div>
        <div class="form-group"><label>曲调</label><input id="f_tune"></div>
        <div class="form-group"><label>调性</label><input id="f_key" placeholder="例：G"></div>
        <div class="form-group"><label>格律 / 节拍</label><input id="f_meter" placeholder="例：8.6.8.6"></div>
        <div class="form-group"><label>来源</label><input id="f_source"></div>
        <div class="form-group full"><label>歌词</label><textarea id="f_lyrics" rows="4" placeholder="粘贴歌词，每句一行"></textarea></div>
        <div class="form-group full"><label>圣经主题</label>${chipSelectHTML("theme", state.cats.themes)}</div>
        <div class="form-group full"><label>崇拜场景</label>${chipSelectHTML("scenario", state.cats.scenarios)}</div>
        <div class="form-group full"><label>音乐类型</label>${chipSelectHTML("type", state.cats.types)}</div>
        <div class="form-group full"><label>备注</label><input id="f_comment"></div>
      </div>
      <div class="mt12 flex">
        <button class="btn btn-primary" id="saveManual">保存曲目</button>
        <button class="btn btn-ghost" id="clearManual">清空</button>
      </div>
    </div>`;

  bindChipSelect($("#content"));
  const dz = $("#dropzone"), fi = $("#fileInput");
  dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("drag"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("drag"));
  dz.addEventListener("drop", (e) => {
    e.preventDefault(); dz.classList.remove("drag");
    if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
  });
  fi.addEventListener("change", () => { if (fi.files.length) uploadFiles(fi.files); fi.value = ""; });

  $("#btnMobileCollect").addEventListener("click", () => { location.href = "/mobile"; });
  // 拍照/相册改为 <label for> 原生触发
  $("#btnOcrFill").addEventListener("click", () => $("#cameraInput").click());
  $("#ocrDiscard").addEventListener("click", () => {
    state.pendingPhoto = null;
    if (state.photoUrl) { URL.revokeObjectURL(state.photoUrl); state.photoUrl = null; }
    $("#ocrPanel").hidden = true;
  });
  $("#cameraInput").addEventListener("change", () => {
    const f = $("#cameraInput").files[0];
    $("#cameraInput").value = "";
    if (f) handleOcrPhoto(f);
  });
  $("#galleryInput").addEventListener("change", () => { if ($("#galleryInput").files.length) uploadFiles($("#galleryInput").files); $("#galleryInput").value = ""; });

  $("#saveManual").addEventListener("click", async () => {
    const title = $("#f_title").value.trim();
    if (!title) return toast("请填写歌曲名称", "warn");
    const body = {
      title, firstLine: $("#f_first").value.trim(), number: $("#f_number").value.trim(),
      lyricist: $("#f_lyricist").value.trim(), composer: $("#f_composer").value.trim(),
      translator: $("#f_translator").value.trim(), tune: $("#f_tune").value.trim(),
      key: $("#f_key").value.trim(), meter: $("#f_meter").value.trim(),
      source: $("#f_source").value.trim(), comment: $("#f_comment").value.trim(),
      lyrics: $("#f_lyrics").value, themes: chipSelectValue("theme"),
      scenarios: chipSelectValue("scenario"), musicTypes: chipSelectValue("type"),
      status: "pending",
    };
    if (state.pendingPhoto) body.attachment = state.pendingPhoto;
    const btn = $("#saveManual"); btn.disabled = true;
    try {
      const d = await api("/api/songs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      toast(`已保存《${d.song.title}》，AI 自动分类完成`);
      ["f_title", "f_first", "f_number", "f_lyricist", "f_composer", "f_translator", "f_tune", "f_key", "f_meter", "f_source", "f_comment", "f_lyrics"].forEach((i) => $("#" + i).value = "");
      resetChipSelect("theme"); resetChipSelect("scenario"); resetChipSelect("type");
      state.pendingPhoto = null;
      if (state.photoUrl) { URL.revokeObjectURL(state.photoUrl); state.photoUrl = null; }
      $("#ocrPanel").hidden = true;
    } catch (e) { toast(e.message, "err"); }
    btn.disabled = false;
  });
  $("#clearManual").addEventListener("click", () => {
    $("#content").querySelectorAll("input, textarea").forEach((i) => i.value = "");
    resetChipSelect("theme"); resetChipSelect("scenario"); resetChipSelect("type");
  });
}

async function handleOcrPhoto(file) {
  const prog = $("#importProgress"); prog.hidden = false;
  try {
    const fd = new FormData();
    fd.append("file", file, file.name);
    const d = await api("/api/ocr", { method: "POST", body: fd });
    state.pendingPhoto = d.attachment;
    if (d.parsed && (d.parsed.title || d.parsed.lyrics)) {
      $("#f_title").value = d.parsed.title || "";
      $("#f_first").value = d.parsed.firstLine || "";
      $("#f_lyrics").value = d.parsed.lyrics || "";
    }
    showOcrPanel(file, d);
    toast(d.parsed?.note || "识别完成", d.parsed?.title ? "ok" : "warn");
  } catch (e) {
    toast("识别失败：" + e.message, "err");
  }
  prog.hidden = true;
}

function showOcrPanel(file, d) {
  const panel = $("#ocrPanel");
  if (!panel) return;
  if (state.photoUrl) URL.revokeObjectURL(state.photoUrl);
  state.photoUrl = URL.createObjectURL(file);
  $("#ocrImg").src = state.photoUrl;
  $("#ocrEngineTag").textContent = "引擎：" + (d.engine || "—") + " · " + (d.lines?.length || 0) + " 行";
  $("#ocrNote").textContent = d.parsed?.note || "";
  $("#ocrText").textContent = d.text || "（未识别到文字）";
  panel.hidden = false;
  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function uploadFiles(files) {
  const prog = $("#importProgress"); prog.hidden = false;
  $("#importResult").innerHTML = "";
  try {
    const fd = new FormData();
    Array.from(files).forEach((f) => fd.append("files", f, f.name));
    const d = await api("/api/import", { method: "POST", body: fd });
    const s = d.summary;
    const items = (s.perFile || []).map((p) => `
      <tr><td>${esc(p.file)}</td><td>${p.songs ?? "-"}</td>
      <td class="muted small">${(p.warnings || []).map((w) => "⚠️ " + esc(w)).join("<br>") || "—"}</td></tr>`).join("");
    $("#importResult").innerHTML = `
      <div class="card card-pad">
        <div class="card-title">导入完成 · 批次 ${esc(s.batch)} <span class="sub">${esc(s.files)} 个文件 · 共 ${s.total} 首</span></div>
        <div class="import-summary">
          <div class="import-box ok"><div class="ib-num">${s.ok}</div><div class="ib-label">✅ 识别成功</div></div>
          <div class="import-box warn"><div class="ib-num">${s.needsReview}</div><div class="ib-label">⚠️ 需人工确认</div></div>
          <div class="import-box dup"><div class="ib-num">${s.duplicates}</div><div class="ib-label">🔄 疑似重复</div></div>
          <div class="import-box bad"><div class="ib-num">${s.incomplete}</div><div class="ib-label">❌ 资料不完整</div></div>
        </div>
        <div class="hint mb8">✅ ${s.total - s.needsReview - s.duplicates - s.incomplete} 首已识别成功；您只需重点处理 ⚠️ 需人工确认 ${s.needsReview} 首、🔄 疑似重复 ${s.duplicates} 首、❌ 资料不完整 ${s.incomplete} 首即可。</div>
        <table class="grid-table"><thead><tr><th>文件</th><th>识别数</th><th>提示</th></tr></thead><tbody>${items}</tbody></table>
        <div class="mt12 flex flex-wrap">
          <button class="btn btn-sm btn-primary" data-goto="library">去曲目库查看</button>
          <button class="btn btn-sm" data-goto="organize">处理疑似重复</button>
          <button class="btn btn-sm" data-goto="review">审核待确认</button>
          <button class="btn btn-sm btn-ghost" onclick="location.reload()">继续导入</button>
        </div>
      </div>`;
    bindGoto();
    refreshStats();
  } catch (e) {
    toast("导入失败：" + e.message, "err");
    $("#importResult").innerHTML = `<div class="card card-pad muted">导入失败：${esc(e.message)}</div>`;
  }
  prog.hidden = true;
}

/* ---------------- 智能整理 ---------------- */
async function renderOrganize() {
  const d = await api("/api/bootstrap");
  state.settings = d.settings; state.cats = d.categories;
  updatePills(d);
  const dups = await api("/api/duplicates");
  const needReview = await api("/api/songs?needsReview=1&size=100");
  $("#content").innerHTML = `
    <div class="card card-pad section">
      <div class="card-title">智能整理管线</div>
      <div class="flow-steps">
        <span class="flow-step"><span class="fs-num">1</span>OCR / AI 文本识别</span><span class="flow-arrow">→</span>
        <span class="flow-step"><span class="fs-num">2</span>标准化（歌名·作者·曲调）</span><span class="flow-arrow">→</span>
        <span class="flow-step"><span class="fs-num">3</span>自动分类（主题/场景/类型/难度）</span><span class="flow-arrow">→</span>
        <span class="flow-step"><span class="fs-num">4</span>疑似重复检测</span>
      </div>
      <div class="grid-3 mt12">
        <div class="card card-pad">
          <div class="card-title small">OCR 引擎</div>
          <div>${d.ocrAvailable ? "✅ OCR 已就绪（" + esc(((d.ocrEngines && d.ocrEngines.length) ? d.ocrEngines.join(" + ") : d.ocrEngine) || "Vision") + "，支持中文）" : "⚠️ OCR 未就绪"}</div>
          <div class="hint mt8">手机拍照后自动识别歌名与歌词并填入表单。${d.ocrAvailable ? "" : "可在本机安装 tesseract+chi_sim，或在设置中配置 AI 接口。"}</div>
        </div>
        <div class="card card-pad">
          <div class="card-title small">AI 识别引擎</div>
          <div>${state.settings.openaiKey ? "✅ 已配置 " + esc(state.settings.openaiKey) : "使用本地智能引擎（离线）"}</div>
          <div class="hint mt8">在“⚙️ 设置”中填入 OpenAI 兼容 API Key 可启用真实 AI 分类。</div>
        </div>
        <div class="card card-pad">
          <div class="card-title small">当前状态</div>
          <div>待确认 <b>${needReview.total}</b> 首 · 疑似重复 <b>${dups.groups.length}</b> 组</div>
        </div>
      </div>
      <div class="mt16 flex flex-wrap">
        <label class="flex"><input type="checkbox" id="orgUseAI" ${state.settings.openaiKey ? "" : "disabled"}> 使用 AI 接口</label>
        <label class="flex"><input type="checkbox" id="orgReclassify" checked> 重新分类</label>
        <label class="flex"><input type="checkbox" id="orgDedup" checked> 重新去重</label>
        <button class="btn btn-primary" id="orgAll">🔄 一键智能整理（全部）</button>
        <button class="btn" id="orgPending">仅整理待审核曲目</button>
      </div>
      <div id="orgResult" class="mt12"></div>
    </div>

    <div class="card card-pad section">
      <div class="card-title">疑似重复 · 人工确认 <span class="sub">匹配度 ≥ 80%</span>
        <button class="btn btn-sm" id="refreshDup">刷新</button></div>
      <div id="dupList"></div>
    </div>

    <div class="card card-pad section">
      <div class="card-title">待确认资料 <span class="sub">AI 置信度不足或资料不完整，共 ${needReview.total} 首</span>
        <button class="btn btn-sm" data-goto="review">去审核</button></div>
      <div id="needReviewList"></div>
    </div>`;
  bindGoto();
  renderDupList(dups.groups);
  renderNeedReview(needReview.items);

  $("#orgAll").addEventListener("click", () => runOrganize("all"));
  $("#orgPending").addEventListener("click", () => runOrganize("pending"));
  $("#refreshDup").addEventListener("click", async () => {
    const dd = await api("/api/duplicates");
    renderDupList(dd.groups);
    toast("已刷新");
  });
}

async function runOrganize(mode) {
  const btn = mode === "all" ? $("#orgAll") : $("#orgPending");
  btn.disabled = true; btn.innerHTML = '<span class="spin"></span>整理中…';
  try {
    const d = await api("/api/organize", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode, reclassify: $("#orgReclassify").checked, dedup: $("#orgDedup").checked, useAI: $("#orgUseAI").checked }) });
    $("#orgResult").innerHTML = `<div class="card card-pad" style="border-color:#bcd8c6;background:#f0faf4">
      ✅ 整理完成：处理 ${d.processed} 首 ｜ 疑似重复 ${d.duplicateGroups} 组 ｜ 待确认 ${d.needsReview} 首 ｜ 涉及重复 ${d.duplicates} 首</div>`;
    toast("智能整理完成");
    const dd = await api("/api/duplicates");
    renderDupList(dd.groups);
    refreshStats();
  } catch (e) { toast(e.message, "err"); }
  btn.disabled = false; btn.textContent = mode === "all" ? "🔄 一键智能整理（全部）" : "仅整理待审核曲目";
}

function renderDupList(groups) {
  const box = $("#dupList");
  if (!box) return;
  if (!groups.length) { box.innerHTML = `<div class="muted small">✅ 未发现疑似重复曲目</div>`; return; }
  box.innerHTML = groups.map((g) => `
    <div class="dup-group" data-group="${esc(g.group)}">
      <div class="dg-head">
        <b>组 ${esc(g.group)} · 最高匹配度 ${(g.maxScore * 100).toFixed(0)}%</b>
        <div class="flex">
          <button class="btn btn-sm btn-green" data-act="keep-both">保留两条（确认不重复）</button>
          <button class="btn btn-sm btn-ghost" data-act="not-duplicate">不是重复</button>
        </div>
      </div>
      <div class="dg-members">${g.members.map((m) => `
        <div class="dup-member">
          <div class="dm-title">${esc(m.title)} <span class="match">${(m.score * 100).toFixed(0)}%</span></div>
          <div class="dm-meta">${esc(m.id)}</div>
          <button class="btn btn-sm mt8" data-act="merge" data-keep="${esc(m.id)}">合并到这首</button>
        </div>`).join("")}
      </div>
    </div>`).join("");
  box.querySelectorAll("[data-act]").forEach((b) => b.addEventListener("click", async () => {
    const g = b.closest(".dup-group").dataset.group;
    const act = b.dataset.act;
    const body = { action: act === "merge" ? "merge" : act };
    if (act === "merge") body.keepId = b.dataset.keep;
    const d = await api(`/api/duplicates/${encodeURIComponent(g)}/resolve`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!d.ok) return toast(d.msg || "操作失败", "err");
    toast(act === "merge" ? "已合并" : "已确认", "ok");
    const dd = await api("/api/duplicates"); renderDupList(dd.groups);
    refreshStats();
  }));
}

function renderNeedReview(items) {
  const box = $("#needReviewList");
  if (!box) return;
  if (!items.length) { box.innerHTML = `<div class="muted small">✅ 没有待确认曲目</div>`; return; }
  box.innerHTML = `<table class="grid-table"><thead><tr><th>编号</th><th>歌名</th><th>主题</th><th>置信度</th><th>标记</th><th>操作</th></tr></thead><tbody>
    ${items.slice(0, 50).map((s) => `
      <tr><td>${esc(s.number || "-")}</td><td class="song-title">${esc(s.title || "(未命名)")}</td>
      <td>${chips(s.themes)}${chips(s.scenarios, "gold")}</td>
      <td>${Math.round((s.aiConfidence || 0) * 100)}%</td>
      <td>${flagsHtml(s)}</td>
      <td><button class="btn btn-sm" data-edit="${esc(s.id)}">编辑</button></td></tr>`).join("")}
  </tbody></table>`;
  box.querySelectorAll("[data-edit]").forEach((b) => b.addEventListener("click", () => openSongModal(b.dataset.edit)));
}

/* ---------------- 曲目库 ---------------- */
function filterOptionsHTML(selected = "") {
  const c = state.cats;
  const opt = (list) => list.map((x) => `<option value="${esc(x)}" ${x === selected ? "selected" : ""}>${esc(x)}</option>`).join("");
  return `
    ${(state.uploaders && state.uploaders.length) ? `<select id="flt_uploader" title="上传人"><option value="">上传人：全部</option>${state.uploaders.map((x) => `<option value="${esc(x)}">${esc(x)}</option>`).join("")}</select>` : ""}
    ${c.hymnbook ? `
    <select id="flt_category" title="大类"><option value="">大类：全部</option>${Object.keys(c.hymnbook).map((x) => `<option value="${esc(x)}">${esc(x)}</option>`).join("")}</select>
    <select id="flt_subcategory" title="细类"><option value="">细类：全部</option>${Object.entries(c.hymnbook).flatMap(([k, v]) => Object.keys(v).filter((x) => x !== "大类词").map((x) => `<option value="${esc(x)}">${esc(x)}</option>`)).join("")}</select>` : ""}
    <select id="flt_theme" title="圣经主题"><option value="">主题：全部</option>${opt(c.themes)}</select>
    <select id="flt_scenario" title="崇拜场景"><option value="">场景：全部</option>${opt(c.scenarios)}</select>
    <select id="flt_type" title="音乐类型"><option value="">类型：全部</option>${opt(c.types)}</select>
    <select id="flt_status" title="状态"><option value="">状态：全部</option>${Object.entries(STATUS_LABELS).map(([k, v]) => `<option value="${k}" ${k === selected ? "selected" : ""}>${v}</option>`).join("")}</select>
    <select id="flt_rating" title="最低评分"><option value="0">评分：不限</option><option value="4.5">≥ 4.5</option><option value="4">≥ 4.0</option><option value="3.5">≥ 3.5</option><option value="3">≥ 3.0</option></select>
    <select id="flt_sort" title="排序"><option value="number">按编号</option><option value="title">按歌名</option><option value="rating">按评分</option><option value="updated">最近更新</option></select>
    <label class="flex small"><input type="checkbox" id="flt_review"> 待确认</label>
    <label class="flex small"><input type="checkbox" id="flt_dup"> 疑似重复</label>`;
}

function readFilters() {
  return {
    q: ($("#libSearch") || {}).value || "", theme: $("#flt_theme")?.value || "", scenario: $("#flt_scenario")?.value || "",
    type: $("#flt_type")?.value || "", status: $("#flt_status")?.value || "", rating: $("#flt_rating")?.value || 0,
    sort: $("#flt_sort")?.value || "number", needsReview: $("#flt_review")?.checked || false, dup: $("#flt_dup")?.checked || false,
    category: $("#flt_category")?.value || "", subcategory: $("#flt_subcategory")?.value || "",
    uploader: $("#flt_uploader")?.value || "",
  };
}

async function renderLibrary() {
  const d = await api("/api/bootstrap");
  state.cats = d.categories;
  state.uploaders = (d.stats.uploaders || []).map((x) => x[0]);
  await loadLibrary();
}

async function loadLibrary() {
  if (!Number.isFinite(state.lib.page) || state.lib.page < 1) state.lib.page = 1;
  const f = readFilters();
  const qs = new URLSearchParams();
  Object.entries(f).forEach(([k, v]) => { if (v && v !== "0") qs.set(k, v); });
  qs.set("page", state.lib.page); qs.set("size", state.lib.size);
  const d = await api("/api/songs?" + qs.toString());
  state.lib.total = d.total;
  const pages = Math.max(1, Math.ceil(d.total / state.lib.size));
  if (state.lib.page > pages) state.lib.page = pages;
  const p = state.lib.page;
  $("#content").innerHTML = `
    <div class="card section">
      <div class="toolbar">
        <div class="search"><input id="libSearch" placeholder="搜索歌名 / 首句 / 作者 / 作曲 / 曲调…" value="${esc(state.lib.q)}"></div>
        ${filterOptionsHTML(f.status)}
        <button class="btn btn-sm" id="libApply">筛选</button>
      </div>
      <div class="toolbar" style="padding-top:0">
        <button class="btn btn-sm" id="bulkCandidate">加入候选库</button>
        <button class="btn btn-sm" id="bulkShortlist">初选</button>
        <button class="btn btn-sm" id="bulkFinal">终选</button>
        <button class="btn btn-sm btn-gold" id="bulkPublish">最终出版</button>
        <button class="btn btn-sm btn-danger" id="bulkReject">淘汰</button>
        <button class="btn btn-sm btn-danger" id="bulkDelete">删除</button>
        <button class="btn btn-sm" id="bulkExport">📤 导出选中 <span id="selCount">(${state.selected.size})</span></button>
        <span class="muted small">共 ${d.total} 首</span>
      </div>
      <div class="table-wrap">
      <table class="grid-table">
        <thead><tr>
          <th><input type="checkbox" id="checkAll"></th><th>编号</th><th>歌名</th><th>上传人</th><th>首句</th><th>作者/作曲</th><th>主题</th><th>难度</th><th>评分</th><th>状态</th><th>操作</th>
        </tr></thead>
        <tbody>${d.items.map((s) => `
          <tr>
            <td><input type="checkbox" class="row-check" value="${esc(s.id)}" ${state.selected.has(s.id) ? "checked" : ""}></td>
            <td>${esc(s.number || "-")}</td>
            <td class="song-title">${esc(s.title || "(未命名)")}${flagsHtml(s)}${s.title ? "" : ""}</td>
            <td>${s.uploader ? `<span class="chip blue">${esc(s.uploader)}</span>` : "—"}</td>
            <td class="muted">${esc(short(s.firstLine, 24))}</td>
            <td class="muted small">${esc(short(s.lyricist, 14))}${s.composer ? "<br>" + esc(short(s.composer, 14)) : ""}</td>
            <td>${s.category ? `<span class="chip gold">${esc(s.category)}·${esc(s.subcategory || "")}</span>` : chips((s.themes || []).slice(0, 2))}</td>
            <td class="small">${esc(s.difficultyStars || "")}</td>
            <td>${s.rating ? s.rating.toFixed(1) : "—"}</td>
            <td>${statusChip(s)}</td>
            <td><div class="row-actions">
              <button class="btn btn-sm" data-edit="${esc(s.id)}">编辑</button>
              <button class="btn btn-sm btn-danger" data-del="${esc(s.id)}">删</button>
            </div></td>
          </tr>`).join("") || `<tr><td colspan="10"><div class="empty"><div class="empty-ico">🔍</div>没有符合条件的曲目</div></td></tr>`}
        </tbody>
      </table>
      </div>
      <div class="pager">
        <span>第 ${p} / ${pages} 页 · 共 ${d.total} 首</span>
        <div class="pages">
          <button class="btn btn-sm" data-page="${p - 1}" ${p <= 1 ? "disabled" : ""}>上一页</button>
          <button class="btn btn-sm" data-page="${p + 1}" ${p >= pages ? "disabled" : ""}>下一页</button>
        </div>
      </div>
    </div>`;

  bindLibrary(d);
}

function bindLibrary(d) {
  const apply = () => { state.lib.q = $("#libSearch").value; state.lib.page = 1; loadLibrary(); };
  $("#libApply").addEventListener("click", apply);
  $("#libSearch").addEventListener("keydown", (e) => { if (e.key === "Enter") apply(); });
  document.querySelectorAll("[data-page]").forEach((b) => b.addEventListener("click", () => {
    const p = Number(b.dataset.page);
    if (!Number.isFinite(p) || p < 1) return;
    state.lib.page = p; loadLibrary();
  }));
  $("#checkAll").addEventListener("change", (e) => {
    $$(".row-check").forEach((c) => { c.checked = e.target.checked; if (e.target.checked) state.selected.add(c.value); else state.selected.delete(c.value); });
    $("#selCount").textContent = `(${state.selected.size})`;
  });
  document.querySelectorAll(".row-check").forEach((c) => c.addEventListener("change", () => {
    if (c.checked) state.selected.add(c.value); else state.selected.delete(c.value);
    $("#selCount").textContent = `(${state.selected.size})`;
  }));
  document.querySelectorAll("[data-edit]").forEach((b) => b.addEventListener("click", () => openSongModal(b.dataset.edit)));
  document.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", async () => {
    if (!confirm("确定删除该曲目？")) return;
    await api("/api/songs/" + b.dataset.del, { method: "DELETE" });
    toast("已删除"); loadLibrary(); refreshStats();
  }));
  const bulk = (status) => async () => {
    if (!state.selected.size) return toast("请先勾选曲目", "warn");
    await api("/api/songs/bulk", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids: [...state.selected], action: "status", value: status }) });
    toast(`已更新 ${state.selected.size} 首 → ${STATUS_LABELS[status]}`); state.selected.clear(); loadLibrary(); refreshStats();
  };
  $("#bulkCandidate").addEventListener("click", bulk("candidate"));
  $("#bulkShortlist").addEventListener("click", bulk("shortlist"));
  $("#bulkFinal").addEventListener("click", bulk("final"));
  $("#bulkPublish").addEventListener("click", bulk("published"));
  $("#bulkReject").addEventListener("click", bulk("rejected"));
  $("#bulkDelete").addEventListener("click", async () => {
    if (!state.selected.size) return toast("请先勾选曲目", "warn");
    if (!confirm(`确定删除选中的 ${state.selected.size} 首曲目？`)) return;
    await api("/api/songs/bulk", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids: [...state.selected], action: "delete" }) });
    toast("已删除"); state.selected.clear(); loadLibrary(); refreshStats();
  });
  $("#bulkExport").addEventListener("click", () => { location.hash = "#/export"; });
}

/* ---------------- 筛选审核 ---------------- */
async function renderReview() {
  const d = await api("/api/bootstrap");
  state.cats = d.categories;
  const tab = state.reviewTab || "pending";
  const qs = new URLSearchParams({ size: 200, sort: "number" });
  if (tab !== "all") qs.set("status", tab);
  if (tab === "published" || tab === "final" || tab === "shortlist" || tab === "candidate") { /* keep */ }
  const theme = $("#revTheme")?.value || "", scenario = $("#revScenario")?.value || "", type = $("#revType")?.value || "";
  if (theme) qs.set("theme", theme); if (scenario) qs.set("scenario", scenario); if (type) qs.set("type", type);
  const dd = await api("/api/songs?" + qs.toString());
  const tabs = [["pending", "待审核"], ["candidate", "候选"], ["shortlist", "初选"], ["final", "终选"], ["published", "最终出版"], ["rejected", "淘汰"], ["all", "全部"]];
  $("#content").innerHTML = `
    <div class="card section">
      <div class="toolbar">
        ${tabs.map(([k, v]) => `<button class="btn btn-sm ${tab === k ? "btn-primary" : ""}" data-tab="${k}">${v}</button>`).join("")}
        <span class="muted small">共 ${dd.total} 首</span>
      </div>
      <div class="toolbar" style="padding-top:0">
        <select id="revTheme"><option value="">主题：全部</option>${state.cats.themes.map((x) => `<option ${theme === x ? "selected" : ""}>${esc(x)}</option>`).join("")}</select>
        <select id="revScenario"><option value="">场景：全部</option>${state.cats.scenarios.map((x) => `<option ${scenario === x ? "selected" : ""}>${esc(x)}</option>`).join("")}</select>
        <select id="revType"><option value="">类型：全部</option>${state.cats.types.map((x) => `<option ${type === x ? "selected" : ""}>${esc(x)}</option>`).join("")}</select>
        <button class="btn btn-sm" id="revApply">筛选</button>
      </div>
      <div class="card-pad">
        <div class="review-grid">${dd.items.map((s) => reviewCard(s)).join("") || `<div class="empty"><div class="empty-ico">📭</div>这个列表还是空的</div>`}</div>
      </div>
    </div>`;
  document.querySelectorAll("[data-tab]").forEach((b) => b.addEventListener("click", () => { state.reviewTab = b.dataset.tab; renderReview(); }));
  $("#revApply").addEventListener("click", () => renderReview());
  bindReviewCards();
}

function reviewCard(s) {
  return `
    <div class="review-card" data-id="${esc(s.id)}">
      <div class="flex justify-between">
        <div class="rc-title">${esc(s.title || "(未命名)")} ${statusChip(s)}</div>
        <div class="muted small">${esc(s.number || "")}</div>
      </div>
      <div class="rc-meta">${s.uploader ? "👤 " + esc(s.uploader) + " · " : ""}${esc(s.lyricist || "")}${s.composer ? " · " + esc(s.composer) : ""}</div>
      ${s.category ? `<div><span class="chip gold">${esc(s.category)}·${esc(s.subcategory || "")}</span></div>` : ""}
      <div>${chips((s.themes || []).slice(0, 3))}${chips((s.scenarios || []).slice(0, 2), "gold")}</div>
      <div class="flex small muted">难度 ${esc(s.difficultyStars || "")} · 会众适唱 ${esc(s.singabilityStars || "")} · AI 置信 ${Math.round((s.aiConfidence || 0) * 100)}%</div>
      ${flagsHtml(s) ? `<div>${flagsHtml(s)}</div>` : ""}
      <div class="flex small"><span class="muted">评分</span>
        <span class="star-input" data-stars="${s.id}">${[1, 2, 3, 4, 5].map((i) => `<span data-v="${i}" class="${(s.rating || 0) >= i ? "on" : ""}">★</span>`).join("")}</span>
        <span class="muted" id="starVal-${esc(s.id)}">${s.rating ? s.rating.toFixed(1) : ""}</span>
      </div>
      <textarea class="review-comment" data-comment="${esc(s.id)}" placeholder="评审意见…">${esc(s.comment || "")}</textarea>
      <div class="rc-actions">
        ${s.status !== "candidate" ? `<button class="btn btn-sm" data-act="status" data-val="candidate">加入候选</button>` : ""}
        ${s.status !== "shortlist" ? `<button class="btn btn-sm" data-act="status" data-val="shortlist">初选</button>` : ""}
        ${s.status !== "final" ? `<button class="btn btn-sm" data-act="status" data-val="final">终选</button>` : ""}
        ${s.status !== "published" ? `<button class="btn btn-sm btn-gold" data-act="status" data-val="published">最终出版</button>` : ""}
        ${s.status !== "rejected" ? `<button class="btn btn-sm btn-danger" data-act="status" data-val="rejected">淘汰</button>` : ""}
        <button class="btn btn-sm btn-ghost" data-act="review" data-val="0">✓ 已确认</button>
        <button class="btn btn-sm btn-ghost" data-act="review" data-val="1">需修改</button>
      </div>
    </div>`;
}

function bindReviewCards() {
  document.querySelectorAll(".star-input").forEach((box) => {
    box.addEventListener("click", async (e) => {
      const sp = e.target.closest("span[data-v]"); if (!sp) return;
      const id = box.dataset.stars, v = Number(sp.dataset.v);
      box.querySelectorAll("span").forEach((x) => x.classList.toggle("on", Number(x.dataset.v) <= v));
      $("#starVal-" + id).textContent = v.toFixed(1);
      await api("/api/songs/" + id, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ rating: v, reclassify: false }) });
      toast(`已评分 ${v} 星`);
    });
  });
  document.querySelectorAll("[data-act]").forEach((b) => b.addEventListener("click", async () => {
    const card = b.closest(".review-card"); const id = card.dataset.id;
    const act = b.dataset.act, val = b.dataset.val;
    const body = { reclassify: false };
    if (act === "status") body.status = val;
    if (act === "review") body.needsReview = val === "1";
    const commentEl = card.querySelector("[data-comment]");
    if (commentEl && commentEl.value.trim()) body.comment = commentEl.value.trim();
    await api("/api/songs/" + id, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    toast(act === "status" ? `已设为「${STATUS_LABELS[val]}」` : val === "1" ? "已标记需修改" : "已确认", "ok");
    renderReview(); refreshStats();
  }));
}

/* ---------------- 导出中心 ---------------- */
async function renderExport() {
  const d = await api("/api/bootstrap");
  state.cats = d.categories;
  const ex = await api("/api/exports");
  const scope = state.exportScope || "all";
  $("#content").innerHTML = `
    <div class="card card-pad section">
      <div class="card-title">选择导出范围</div>
      <div class="export-scopes">
        <div class="scope-card ${scope === "all" ? "on" : ""}" data-scope="all"><div class="sc-name">全部曲目</div><div class="sc-desc">${d.stats.total} 首</div></div>
        <div class="scope-card ${scope === "report" ? "on" : ""}" data-scope="report"><div class="sc-name">📋 编选报告</div><div class="sc-desc">生成《编选总表》全格式</div></div>
        <div class="scope-card ${scope === "needsReview" ? "on" : ""}" data-scope="needsReview"><div class="sc-name">待审核</div><div class="sc-desc">${d.stats.needsReview} 首</div></div>
        <div class="scope-card ${scope === "selected" ? "on" : ""}" data-scope="selected"><div class="sc-name">选中曲目</div><div class="sc-desc">${state.selected.size} 首</div></div>
        <div class="scope-card ${scope === "status" ? "on" : ""}" data-scope="status"><div class="sc-name">按状态</div><div class="sc-desc">候选/初选/终选…</div></div>
        <div class="scope-card ${scope === "theme" ? "on" : ""}" data-scope="theme"><div class="sc-name">按主题</div><div class="sc-desc">如：救恩 / 十字架</div></div>
        <div class="scope-card ${scope === "scenario" ? "on" : ""}" data-scope="scenario"><div class="sc-name">按场景</div><div class="sc-desc">如：圣餐 / 婚礼</div></div>
        <div class="scope-card ${scope === "type" ? "on" : ""}" data-scope="type"><div class="sc-name">按类型</div><div class="sc-desc">如：传统圣诗</div></div>
        <div class="scope-card ${scope === "filter" ? "on" : ""}" data-scope="filter"><div class="sc-name">自定义筛选</div><div class="sc-desc">主题+场景+类型+评分</div></div>
      </div>
      <div id="scopeDetail" class="mt16"></div>
    </div>

    <div class="card card-pad section">
      <div class="card-title">导出格式与文件名</div>
      <div class="format-row" id="formatRow">
        <div class="format-opt ${scope === "report" ? "" : "on"}" data-format="xlsx"><div class="fo-ico">📊</div><div class="fo-name">Excel</div></div>
        <div class="format-opt" data-format="docx"><div class="fo-ico">📄</div><div class="fo-name">Word</div></div>
        <div class="format-opt" data-format="pdf"><div class="fo-ico">🖨️</div><div class="fo-name">PDF</div></div>
        <div class="format-opt" data-format="csv"><div class="fo-ico">🗂️</div><div class="fo-name">CSV</div></div>
      </div>
      <div class="mt12 form-group" style="max-width:420px">
        <label>文件名（可自定义，如：赞美诗第一版候选曲目）</label>
        <input id="exportName" placeholder="赞美诗编选总表">
      </div>
      <div class="mt12 flex">
        <button class="btn btn-gold" id="doExport">⚡ 生成并下载</button>
        <button class="btn" id="quickExcel">快捷：导出全部 Excel</button>
        <button class="btn" id="quickReport">快捷：编选报告</button>
      </div>
    </div>

    <div class="card card-pad section">
      <div class="card-title">已生成文件 <span class="sub">保存于 data/exports</span></div>
      <div id="exportList">${ex.exports.length ? ex.exports.map((f) => `
        <div class="file-row">
          <div><div class="fr-name">${esc(f.name)}</div><div class="fr-meta">${esc(f.format.toUpperCase())} · ${fmtSize(f.size)} · ${esc(f.time)} · ${f.count} 首</div></div>
          <a class="btn btn-sm btn-primary" href="/files/exports/${encodeURIComponent(f.name)}?token=${encodeURIComponent(state.token || "")}" download>下载</a>
        </div>`).join("") : `<div class="muted small">还没有导出文件</div>`}
      </div>
    </div>`;

  bindExport();
}

function exportScopeDetail() {
  const scope = state.exportScope || "all";
  const c = state.cats;
  let html = "";
  if (scope === "status") html = `<div class="form-group" style="max-width:300px"><label>状态</label><select id="exStatus">${Object.entries(STATUS_LABELS).filter(([k]) => k !== "merged").map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select></div>`;
  if (scope === "theme") html = `<div class="form-group" style="max-width:300px"><label>圣经主题</label><select id="exCat">${c.themes.map((x) => `<option>${esc(x)}</option>`).join("")}</select></div>`;
  if (scope === "scenario") html = `<div class="form-group" style="max-width:300px"><label>崇拜场景</label><select id="exCat">${c.scenarios.map((x) => `<option>${esc(x)}</option>`).join("")}</select></div>`;
  if (scope === "type") html = `<div class="form-group" style="max-width:300px"><label>音乐类型</label><select id="exCat">${c.types.map((x) => `<option>${esc(x)}</option>`).join("")}</select></div>`;
  if (scope === "filter") html = `<div class="flex flex-wrap">
      <div class="form-group"><label>主题</label><select id="exTheme"><option value="">全部</option>${c.themes.map((x) => `<option>${esc(x)}</option>`).join("")}</select></div>
      <div class="form-group"><label>场景</label><select id="exScenario"><option value="">全部</option>${c.scenarios.map((x) => `<option>${esc(x)}</option>`).join("")}</select></div>
      <div class="form-group"><label>类型</label><select id="exType"><option value="">全部</option>${c.types.map((x) => `<option>${esc(x)}</option>`).join("")}</select></div>
      <div class="form-group"><label>评分 ≥</label><select id="exRating"><option value="0">不限</option><option value="4.5">4.5</option><option value="4">4.0</option><option value="3">3.0</option></select></div>
    </div>`;
  if (scope === "needsReview" || scope === "selected" || scope === "all" || scope === "report") {
    html = `<div class="hint">${scope === "report" ? "将自动生成《编选总表》Excel / Word / PDF / CSV 四种格式（范围：候选→终选→出版）。" :
            scope === "needsReview" ? "导出所有待审核 / 待确认曲目。" :
            scope === "selected" ? "导出您最近在“曲目库”勾选的曲目。" :
            "导出全部曲目（不含已合并）。"}</div>`;
  }
  const detail = $("#scopeDetail");
  if (detail) detail.innerHTML = html;
}

function bindExport() {
  document.querySelectorAll("[data-scope]").forEach((c) => c.addEventListener("click", () => {
    state.exportScope = c.dataset.scope;
    document.querySelectorAll(".scope-card").forEach((x) => x.classList.toggle("on", x === c));
    exportScopeDetail();
    // 仅“编选报告”会生成全部格式，此时取消格式高亮；其他范围保留用户选择
    if (state.exportScope === "report") {
      document.querySelectorAll("[data-format]").forEach((f) => f.classList.remove("on"));
    }
  }));
  document.querySelectorAll("[data-format]").forEach((f) => f.addEventListener("click", () => {
    if (state.exportScope === "report") return;
    document.querySelectorAll("[data-format]").forEach((x) => x.classList.toggle("on", x === f));
  }));
  exportScopeDetail();

  const currentFormat = () => (document.querySelector("[data-format].on") || {}).dataset?.format || "xlsx";
  const buildBody = (name, format) => {
    const scope = state.exportScope || "all";
    const body = { scope, format, name: name || undefined, ids: [...state.selected] };
    if (scope === "status") body.status = $("#exStatus")?.value;
    if (scope === "theme" || scope === "scenario" || scope === "type") {
      body[scope === "theme" ? "theme" : scope === "scenario" ? "scenario" : "type"] = $("#exCat")?.value;
    }
    if (scope === "filter") body.filters = {
      theme: $("#exTheme")?.value || "", scenario: $("#exScenario")?.value || "",
      type: $("#exType")?.value || "", rating: Number($("#exRating")?.value || 0),
    };
    if (scope === "needsReview") body.filters = { needsReview: true };
    return body;
  };

  const generate = async (formatOverride) => {
    const scope = state.exportScope || "all";
    const fmt = scope === "report" ? (formatOverride || "all") : (formatOverride || currentFormat());
    const name = $("#exportName").value.trim();
    const btn = $("#doExport"); if (btn) btn.disabled = true;
    try {
      const d = await api("/api/export", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(buildBody(name, fmt)) });
      if (!d.ok) return toast(d.msg || "导出失败", "err");
      d.files.forEach((f) => {
        const a = document.createElement("a");
        a.href = "/files/exports/" + encodeURIComponent(f.name) + "?token=" + encodeURIComponent(state.token || "");
        a.download = f.name;
        document.body.append(a); a.click(); a.remove();
      });
      toast(`已生成 ${d.files.length} 个文件（${d.count} 首）`);
      renderExport();
    } catch (e) { toast(e.message, "err"); }
    if (btn) btn.disabled = false;
  };
  $("#doExport").addEventListener("click", () => generate());
  $("#quickExcel").addEventListener("click", () => { state.exportScope = "all"; renderExport(); setTimeout(() => generate("xlsx"), 100); });
  $("#quickReport").addEventListener("click", () => { state.exportScope = "report"; renderExport(); setTimeout(() => generate("all"), 100); });
}

/* ---------------- 曲目编辑弹窗 ---------------- */
let editingId = null;
async function openSongModal(id) {
  editingId = id;
  const d = await api("/api/songs/" + id);
  const s = d.song;
  $("#songModalTitle").textContent = `编辑 · ${s.title || "(未命名)"}`;
  $("#songModalBody").innerHTML = `
    <div class="form-grid">
      <div class="form-group"><label>歌曲名称 *</label><input id="m_title" value="${esc(s.title)}"></div>
      <div class="form-group"><label>编号</label><input id="m_number" value="${esc(s.number)}"></div>
      <div class="form-group"><label>上传人</label><input id="m_uploader" value="${esc(s.uploader || "")}" placeholder="用于对接"></div>
      <div class="form-group"><label>状态</label><select id="m_status">${Object.entries(STATUS_LABELS).filter(([k]) => k !== "merged").map(([k, v]) => `<option value="${k}" ${s.status === k ? "selected" : ""}>${v}</option>`).join("")}</select></div>
      <div class="form-group full"><label>首句</label><input id="m_first" value="${esc(s.firstLine)}"></div>
      <div class="form-group"><label>作者（作词）</label><input id="m_lyricist" value="${esc(s.lyricist)}"></div>
      <div class="form-group"><label>作曲</label><input id="m_composer" value="${esc(s.composer)}"></div>
      <div class="form-group"><label>译者</label><input id="m_translator" value="${esc(s.translator)}"></div>
      <div class="form-group"><label>曲调</label><input id="m_tune" value="${esc(s.tune)}"></div>
      <div class="form-group"><label>调性</label><input id="m_key" value="${esc(s.key)}"></div>
      <div class="form-group"><label>格律</label><input id="m_meter" value="${esc(s.meter)}"></div>
      <div class="form-group"><label>来源</label><input id="m_source" value="${esc(s.source)}"></div>
      <div class="form-group"><label>评分</label><input id="m_rating" type="number" min="0" max="5" step="0.1" value="${s.rating || ""}"></div>
      ${state.cats.hymnbook ? `
      <div class="form-group"><label>大类</label><select id="m_category"><option value="">（自动分类）</option>${Object.keys(state.cats.hymnbook).map((x) => `<option value="${esc(x)}" ${s.category === x ? "selected" : ""}>${esc(x)}</option>`).join("")}</select></div>
      <div class="form-group"><label>细类</label><select id="m_subcategory"><option value="">（自动分类）</option>${Object.values(state.cats.hymnbook).flatMap((v) => Object.keys(v).filter((x) => x !== "大类词")).map((x) => `<option value="${esc(x)}" ${s.subcategory === x ? "selected" : ""}>${esc(x)}</option>`).join("")}</select></div>` : ""}
      <div class="form-group full"><label>歌词</label><textarea id="m_lyrics" rows="5">${esc(s.lyrics)}</textarea></div>
      <div class="form-group full"><label>圣经主题</label>${chipSelectHTML("m_theme", state.cats.themes, s.themes || [])}</div>
      <div class="form-group full"><label>崇拜场景</label>${chipSelectHTML("m_scenario", state.cats.scenarios, s.scenarios || [])}</div>
      <div class="form-group full"><label>音乐类型</label>${chipSelectHTML("m_type", state.cats.types, s.musicTypes || [])}</div>
      <div class="form-group full"><label>备注 / 评审意见</label><input id="m_comment" value="${esc(s.comment)}"></div>
      <div class="form-group full">
        <label>附件（曲谱 / 音频 / 图片）</label>
        <div class="flex flex-wrap" id="attachList">${(s.attachments || []).map((a) => `
          <a class="chip blue" href="/files/uploads/${encodeURIComponent(a.name)}?token=${encodeURIComponent(state.token || "")}" download>📎 ${esc(a.name)}</a>`).join("") || `<span class="muted small">无附件</span>`}</div>
        <input type="file" id="m_attach" class="mt8">
      </div>
    </div>`;
  bindChipSelect($("#songModalBody"));
  $("#songModal").hidden = false;
  $("#m_attach").addEventListener("change", async (e) => {
    const f = e.target.files[0]; if (!f) return;
    const fd = new FormData(); fd.append("file", f, f.name);
    await api(`/api/songs/${id}/attachments`, { method: "POST", body: fd });
    toast("附件已上传"); openSongModal(id);
  });
}

async function saveSongModal() {
  if (!editingId) return;
  const body = {
    title: $("#m_title").value.trim(), number: $("#m_number").value.trim(), status: $("#m_status").value,
    firstLine: $("#m_first").value.trim(), lyricist: $("#m_lyricist").value.trim(), composer: $("#m_composer").value.trim(),
    translator: $("#m_translator").value.trim(), tune: $("#m_tune").value.trim(), key: $("#m_key").value.trim(),
    meter: $("#m_meter").value.trim(), source: $("#m_source").value.trim(), comment: $("#m_comment").value.trim(),
    lyrics: $("#m_lyrics").value, rating: Number($("#m_rating").value || 0),
    themes: chipSelectValue("m_theme"), scenarios: chipSelectValue("m_scenario"), musicTypes: chipSelectValue("m_type"),
    category: $("#m_category")?.value || "", subcategory: $("#m_subcategory")?.value || "",
    uploader: $("#m_uploader")?.value || "",
    reclassify: true,
  };
  const d = await api("/api/songs/" + editingId, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  toast(`已保存《${d.song.title}》`);
  $("#songModal").hidden = true;
  refreshStats();
  if (state.page === "library") loadLibrary();
  else if (state.page === "review") renderReview();
  else if (state.page === "organize") renderOrganize();
}

/* ---------------- 设置 ---------------- */
function openSettings() {
  const s = state.settings || {};
  $("#setBase").value = s.openaiBase || "https://api.openai.com/v1";
  $("#setKey").value = s.openaiKey || "";
  $("#setModel").value = s.openaiModel || "gpt-4o-mini";
  $("#settingsModal").hidden = false;
}

/* ---------------- 初始化 ---------------- */
function refreshStats() {
  api("/api/bootstrap").then((d) => { state.stats = d.stats; state.settings = d.settings; updatePills(d); }).catch(() => {});
}

function showLogin() {
  $("#content").innerHTML = `
    <div class="card card-pad" style="max-width:380px;margin:60px auto;text-align:center">
      <div style="font-size:42px">🔒</div>
      <h2 style="margin:10px 0">后台管理端</h2>
      <p class="muted small mb16">请输入管理密码</p>
      <input id="loginPwd" type="password" placeholder="管理密码" style="width:100%;padding:11px;border:1px solid var(--line);border-radius:9px;font-size:15px;outline:none">
      <button class="btn btn-primary w100 mt12" id="loginBtn" style="padding:11px">登 录</button>
      <div class="muted small mt12">📱 手机采集端无需密码：/mobile</div>
    </div>`;
  const go = async () => {
    const pwd = $("#loginPwd").value;
    try {
      const d = await fetch("/api/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password: pwd }) });
      const j = await d.json().catch(() => ({}));
      if (d.status !== 200 || !j.ok) { toast("密码错误", "err"); return; }
      state.token = j.token;
      localStorage.setItem("hymn_token", j.token);
      toast("登录成功");
      navigate();
    } catch (e) { toast("登录失败：" + e.message, "err"); }
  };
  $("#loginBtn").addEventListener("click", go);
  $("#loginPwd").addEventListener("keydown", (e) => { if (e.key === "Enter") go(); });
  $("#loginPwd").focus();
}

function bindGlobal() {
  window.addEventListener("hashchange", navigate);
  $("#btnSettings").addEventListener("click", openSettings);
  $("#btnQuickImport").addEventListener("click", () => { location.hash = "#/collection"; });
  document.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => { $("#" + b.dataset.close).hidden = true; }));
  $("#settingsSaveBtn").addEventListener("click", async () => {
    const body = {
      openaiBase: $("#setBase").value.trim(), openaiKey: $("#setKey").value.trim(),
      openaiModel: $("#setModel").value.trim(), openaiEnabled: !!$("#setKey").value.trim(),
    };
    const d = await api("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const oldp = $("#setOldPwd").value, newp = $("#setNewPwd").value;
    if (oldp || newp) {
      const r = await api("/api/password", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ old: oldp, new: newp }) });
      toast(r.msg || "密码已修改");
      $("#setOldPwd").value = ""; $("#setNewPwd").value = "";
    }
    state.settings = d.settings;
    $("#settingsModal").hidden = true;
    updatePills({ settings: d.settings });
    toast("设置已保存");
    if (state.page === "organize") renderOrganize();
  });
  $("#songSaveBtn").addEventListener("click", saveSongModal);
  document.addEventListener("click", (e) => {
    const c = e.target.closest("[data-edit]");
    if (c) openSongModal(c.dataset.edit);
  });
}

(async function init() {
  bindGlobal();
  // 注销所有 Service Worker：本地服务不需要离线缓存，避免旧代码被缓存导致功能失效
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.getRegistrations().then((rs) => rs.forEach((r) => r.unregister())).catch(() => {});
  }
  state.token = localStorage.getItem("hymn_token") || "";
  try {
    const a = await api("/api/auth/check");
    if (a && a.authed === false) { showLogin(); return; }
  } catch (e) { /* 服务未开 */ }
  try { await refreshStats(); } catch (e) { /* server maybe starting */ }
  navigate();
})();
