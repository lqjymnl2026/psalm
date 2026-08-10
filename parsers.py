# -*- coding: utf-8 -*-
"""导入解析：Excel / CSV / PDF / Word / 图片 / 音频 → 曲目字典列表。
识别策略：能提取什么就提取什么，重点保证「歌名 + 歌词」不丢。
PDF：文字层提取失败 → 逐页渲染图片 OCR（Vision → tesseract → AI）。
"""
from __future__ import annotations

import csv
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
from difflib import SequenceMatcher

# ---------------------------------------------------------------- 列名自动匹配
COLUMN_ALIASES = {
    "title":      ["歌名", "歌曲名称", "歌曲名", "曲名", "名称", "标题", "赞美诗名称", "赞美诗", "诗名", "title", "歌名(中英)", "歌名中英"],
    "firstLine":  ["首句", "首句歌词", "第一句", "歌词首句", "首行", "first line", "firstline"],
    "lyricist":   ["作者", "作词", "词作者", "作词者", "作词人", "lyricist", "作词家", "词"],
    "composer":   ["作曲", "曲作者", "作曲者", "作曲人", "composer", "曲作者者"],
    "translator": ["译者", "翻译", "翻译者", "译词", "translator"],
    "tune":       ["曲调", "调名", "tune", "曲牌", "旋律"],
    "key":        ["调性", "调", "key", "原调", "定调"],
    "meter":      ["格律", "节拍", "拍号", "meter", "metre", "诗歌体"],
    "source":     ["来源", "出处", "歌本", "诗集", "source", "选本", "曲集"],
    "theme":      ["主题", "题材", "分类", "theme", "圣经主题", "类别"],
    "lyrics":     ["歌词", "歌词全文", "正文", "text", "lyrics", "full lyrics", "歌词内容"],
    "rating":     ["评分", "星级", "rating", "星"],
    "status":     ["状态", "status", "阶段"],
    "number":     ["编号", "序号", "number", "曲号", "诗编号"],
    "comment":    ["备注", "说明", "comment", "注释"],
    "difficulty": ["难度", "difficulty"],
    "uploader":   ["上传人", "上传人姓名", "收集人", "姓名", "uploader", "上报人"],
    "category":   ["大类", "category", "分类一", "圣诗分类"],
    "subcategory": ["细类", "subcategory", "分类二", "细目"],
}

_HEADER_CACHE = {}


def normalize_header(h: str) -> str:
    return re.sub(r"[\s\u3000·\.\-_]+", "", str(h or "")).lower()


def match_column(header: str):
    key = normalize_header(header)
    if key in _HEADER_CACHE:
        return _HEADER_CACHE[key]
    result = None
    for field, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            if normalize_header(a) == key:
                result = field
                break
        if result:
            break
    if not result and key:
        best, best_r = None, 0.0
        for field, aliases in COLUMN_ALIASES.items():
            for a in aliases:
                r = SequenceMatcher(None, key, normalize_header(a)).ratio()
                if r > best_r:
                    best_r, best = r, field
        if best_r >= 0.62:
            result = best
    _HEADER_CACHE[key] = result
    return result


def _clean(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _map_rows(headers, rows):
    mapped = {}
    for i, h in enumerate(headers):
        f = match_column(h)
        if f:
            mapped[i] = f
    songs = []
    for row in rows:
        song = {}
        for i, f in mapped.items():
            v = _clean(row[i]) if i < len(row) else ""
            if v:
                song[f] = v
        if song:
            songs.append(song)
    return songs


# ---------------------------------------------------------------- Excel / CSV
def parse_excel_bytes(data: bytes, filename: str):
    name = filename.lower()
    if name.endswith(".csv"):
        return _parse_csv_bytes(data)
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return [], ["Excel 没有数据"]
    headers = [_clean(x) for x in rows[0]]
    songs = _map_rows(headers, rows[1:])
    return songs, []


def _try_decode_csv(data: bytes):
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8"


def _parse_csv_bytes(data: bytes):
    text, enc = _try_decode_csv(data)
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except Exception:
        dialect = csv.excel
    reader = list(csv.reader(io.StringIO(text), dialect))
    if not reader:
        return [], ["CSV 没有数据"]
    headers = [_clean(x) for x in reader[0]]
    songs = _map_rows(headers, reader[1:])
    return songs, []


# ---------------------------------------------------------------- 文本切分（宽松）
_SONG_NO_RE = re.compile(r"^\s*(?:第\s*)?(\d{1,4})\s*[、.．。)）\]\-\s:：]+\s*(\S.{0,40})$")
_HYMNBOOK_RE = re.compile(r"(?:赞美诗|诗歌|圣诗|颂赞)[^0-9]{0,12}?(?:第\s*)?(\d{1,4})\s*首?[：:\s]*(\S{2,40})")
_ANY_PUNCT = re.compile(r"[，。；：？！、…,.;:?!]")
_NOISE_RE = re.compile(r"^(第\s*\d{1,4}\s*(首|页)|page\s*\d+|\d{1,4}\s*页|目录|附录|序\s*$)", re.I)


def _is_noise_line(t: str) -> bool:
    t = t.strip()
    if not t:
        return True
    if re.fullmatch(r"[\d\s\-—.。·()（）]+", t):
        return True
    if _NOISE_RE.match(t):
        return True
    if re.search(r"^\d{1,3}\s*$", t):
        return True
    return False


def _is_title_candidate(t: str) -> bool:
    """歌名候选：短、无标点、含中英文文字。"""
    t = t.strip()
    if len(t) < 2 or len(t) > 20:
        return False
    if _ANY_PUNCT.search(t):
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z]", t))


def _looks_like_title(t: str) -> bool:
    t = t.strip()
    if not t or len(t) > 42:
        return False
    if re.fullmatch(r"[\d\s\-—.。、()（）页pP]{1,10}", t):
        return False
    if not re.search(r"[\u4e00-\u9fffA-Za-z]", t):
        return False
    return True


def _entry_to_song(e: dict, source: str) -> dict:
    lyrics = e.get("lyrics", "").strip()
    title = e.get("title", "").strip()
    number = e.get("number", "")
    lines = [l for l in lyrics.splitlines() if l.strip()]
    if not title and lines and _is_title_candidate(lines[0]) and len(lines[0].strip()) <= 16:
        # 无编号时，把第一行短句当作歌名并从歌词中移除
        title = lines[0].strip()
        lines = lines[1:]
        lyrics = "\n".join(lines).strip()
    first = lines[0].strip() if lines else ""
    return {"title": title, "number": number, "lyrics": lyrics, "firstLine": first, "source": source}


def _segment_by_titles(lines, source):
    """无编号时的宽松切分：短行（无标点）视为歌名，其后为歌词。"""
    entries = []
    current = None
    for raw in lines:
        t = raw.strip()
        if not t or _is_noise_line(t):
            continue
        if _is_title_candidate(t):
            if current and current["lyrics"].strip():
                entries.append(current)
            current = {"number": "", "title": t, "lyrics": ""}
        else:
            if current is None:
                current = {"number": "", "title": "", "lyrics": ""}
            current["lyrics"] += (raw.strip() + "\n")
    if current and (current["lyrics"].strip() or current["title"]):
        entries.append(current)
    return [_entry_to_song(e, source) for e in entries]


def segment_hymn_text(text: str, source: str):
    """把整篇文本切分为 [{number,title,lyrics}]。优先编号模式，其次标题行宽松模式。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [l.rstrip() for l in text.split("\n")]
    entries = []
    current = None
    for raw in lines:
        t = raw.strip()
        if not t:
            continue
        m = _SONG_NO_RE.match(t) or _HYMNBOOK_RE.search(t)
        if m and _looks_like_title(m.group(2)):
            if current:
                entries.append(current)
            current = {"number": m.group(1),
                       "title": re.sub(r"\s+", " ", m.group(2)).strip(" \t-—。.，,"),
                       "lyrics": ""}
            continue
        if current is not None:
            current["lyrics"] += (raw + "\n")
    if current:
        entries.append(current)
    songs = [_entry_to_song(e, source) for e in entries if e["title"] or e["lyrics"].strip()]
    numbered = [s for s in songs if s.get("number")]
    if numbered:
        return numbered, []
    if songs:
        return songs, []
    return _segment_by_titles(lines, source), []


# ---------------------------------------------------------------- PDF（含扫描版 OCR 回退）
def render_pdf_pages(data: bytes, scale: float = 2.2):
    """把 PDF 每页渲染为 PIL 图像（供 OCR 识别扫描版）。"""
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(data)
    imgs = []
    for page in pdf:
        try:
            bitmap = page.render(scale=scale)
            imgs.append(bitmap.to_pil().convert("RGB"))
        except Exception:
            continue
    return imgs


def parse_pdf_bytes(data: bytes, filename: str, settings=None):
    warnings = []
    pages_text = []
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for pg in pdf.pages:
                try:
                    pages_text.append(pg.extract_text() or "")
                except Exception:
                    pages_text.append("")
    except Exception:
        pages_text = [""]
    full = "\n".join(pages_text)
    ocr_used = False
    if len(full.strip()) < 30:
        # 文字层不足 → 疑似扫描版：渲染成图片再 OCR
        try:
            imgs = render_pdf_pages(data)
        except Exception:
            imgs = []
        ocr_parts = []
        for im in imgs:
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.close()
            try:
                im.save(tmp.name)
                text, engine, ai = recognize_image_full(tmp.name, settings)
                if text and text.strip():
                    ocr_parts.append(text.strip())
            finally:
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass
        if ocr_parts:
            full = "\n".join(ocr_parts)
            ocr_used = True
            warnings.append("扫描版 PDF：已通过 OCR 识别文字，请核对")
    if not full.strip():
        return [], ["PDF 无法识别文字（扫描版需 OCR：请安装 tesseract 或在设置中配置 AI 接口）"]
    if ocr_used:
        # 扫描版：每页按歌谱规则解析为一首
        songs = []
        for page_txt in ocr_parts:
            if not page_txt.strip():
                continue
            parsed = parse_ocr_plain_text(page_txt, filename)
            songs.append({"title": parsed["title"], "firstLine": parsed["firstLine"],
                          "lyrics": parsed["lyrics"], "source": filename,
                          "flags": ["PDF-OCR"]})
        return songs, warnings
    songs, seg_warn = segment_hymn_text(full, filename)
    warnings.extend(seg_warn)
    return songs, warnings


# ---------------------------------------------------------------- Word
def parse_docx_bytes(data: bytes, filename: str):
    import docx
    d = docx.Document(io.BytesIO(data))
    parts = []
    for p in d.paragraphs:
        t = p.text.strip()
        if t:
            parts.append(t)
    for table in d.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    full = "\n".join(parts)
    if not full.strip():
        return [], ["Word 文档中没有可提取的文字"]
    songs, warnings = segment_hymn_text(full, filename)
    return songs, warnings


# ---------------------------------------------------------------- macOS Vision OCR
def ensure_ocr_tool():
    tools = pathlib.Path(__file__).resolve().parent / "tools"
    tool = tools / "ocr_tool"
    src = tools / "ocr_tool.swift"
    if tool.exists() and src.exists() and tool.stat().st_mtime >= src.stat().st_mtime:
        return str(tool)
    swiftc = shutil.which("swiftc")
    if not swiftc or not src.exists():
        return None
    cache = tools / ".cache"
    cache.mkdir(exist_ok=True)
    try:
        subprocess.run([swiftc, "-O", f"-Xcc", f"-fmodules-cache-path={cache}",
                        str(src), "-o", str(tool)], capture_output=True, timeout=240)
    except Exception:
        return None
    return str(tool) if tool.exists() else None


def ocr_engine_name():
    if ensure_ocr_tool():
        return "Vision"
    if _tessjs_ready():
        return "tesseract.js"
    if shutil.which("tesseract"):
        return "tesseract"
    return ""


def _tessjs_ready():
    node = _find_node()
    script = pathlib.Path(__file__).resolve().parent / "tools" / "ocr_tessera.js"
    td = pathlib.Path(__file__).resolve().parent / "data" / "tessdata" / "chi_sim.traineddata.gz"
    return bool(node and script.exists() and td.exists() and _find_node_modules())


def ocr_available():
    return bool(ocr_engine_name())


def ocr_image_vision(path):
    """macOS Vision（中文+英文）。返回 (text, lines) 或 None。"""
    tool = ensure_ocr_tool()
    if not tool:
        return None
    try:
        out = subprocess.run([tool, path], capture_output=True, timeout=150)
        if out.returncode != 0:
            return None
        lines = json.loads(out.stdout.decode("utf-8"))
        if not lines:
            return None
        text = "\n".join(l.get("text", "") for l in lines if l.get("text"))
        return (text, lines) if text.strip() else None
    except Exception:
        return None


def _find_node():
    import glob
    cands = [os.environ.get("NODE_BIN", ""),
             "/Users/macbook/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"]
    cands += sorted(glob.glob(os.path.expanduser("~/.cache/codex-runtimes/*/dependencies/node/bin/node")), key=len)
    cands += [shutil.which("node") or ""]
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


def _find_node_modules():
    node = _find_node()
    if not node:
        return None
    cand = os.path.join(os.path.dirname(os.path.dirname(node)), "node_modules")
    return cand if os.path.isdir(cand) else None


def _preprocess_image_variant(path, scale_target=2200, contrast=None):
    """OCR 前预处理：EXIF 转正 + 缩放到指定大小 + 灰度 + 可选对比度。"""
    try:
        from PIL import Image, ImageOps, ImageEnhance
        im = Image.open(path)
        im = ImageOps.exif_transpose(im)  # 按 EXIF 转正
        im = im.convert("L")
        w, h = im.size
        m = max(w, h)
        if m > scale_target:
            sc = scale_target / m
            im = im.resize((int(w * sc), int(h * sc)), Image.LANCZOS)
        elif m < 900:
            sc = max(1.4, 900 / m)
            im = im.resize((int(w * sc), int(h * sc)), Image.LANCZOS)
        im = ImageOps.autocontrast(im)
        if contrast:
            im = ImageEnhance.Contrast(im).enhance(contrast)
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        im.save(tmp.name)
        return tmp.name
    except Exception:
        return path


def _preprocess_image(path):
    return _preprocess_image_variant(path, 2200, 1.5)


_OCR_PORT = int(os.environ.get("OCR_PORT", "8799"))
_ocr_server_proc = None
_ocr_server_checked = False


def _ocr_server_running():
    try:
        import urllib.request
        urllib.request.urlopen(f"http://127.0.0.1:{_OCR_PORT}/health", timeout=1)
        return True
    except Exception:
        return False


def _ensure_ocr_server():
    """确保持久 OCR 服务在跑（worker 常驻，批量识别快）。"""
    global _ocr_server_proc, _ocr_server_checked
    if _ocr_server_running():
        return _OCR_PORT
    node = _find_node()
    script = pathlib.Path(__file__).resolve().parent / "tools" / "ocr_server.js"
    mods = _find_node_modules()
    if not node or not script.exists() or not mods:
        return None
    env = dict(os.environ)
    env["NODE_PATH"] = mods
    try:
        _ocr_server_proc = subprocess.Popen([node, str(script)], env=env,
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        return None
    for _ in range(40):
        if _ocr_server_running():
            return _OCR_PORT
        import time
        time.sleep(0.25)
    return None


def ocr_image_tesseractjs_batch(paths):
    """批量识别多张预处理后的图片（持久服务）。返回 [text,...] 或 None。"""
    port = _ensure_ocr_server()
    if not port:
        return None
    import urllib.request
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/ocr",
                                     data=json.dumps({"paths": paths}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=900) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        texts = data.get("texts")
        return texts if isinstance(texts, list) else None
    except Exception:
        return None


def _run_tessjs_direct(pre, psm):
    node = _find_node()
    script = pathlib.Path(__file__).resolve().parent / "tools" / "ocr_tessera.js"
    mods = _find_node_modules()
    if not node or not script.exists() or not mods:
        return None
    env = dict(os.environ)
    env["NODE_PATH"] = mods
    try:
        out = subprocess.run([node, str(script), pre, psm], capture_output=True, timeout=300, env=env)
        return out.stdout.decode("utf-8", errors="replace").strip() or None
    except Exception:
        return None


def _pick_best_ocr_text(texts):
    """多通道识别结果中，取“歌名+首行歌词”最完整的一个。"""
    best, best_score = None, -1
    for t in texts:
        if not t:
            continue
        p = parse_ocr_plain_text(t, "")
        score = (2 if p.get("title") else 0) + len(_CJK_RE.findall(p.get("firstLine") or ""))
        if score > best_score:
            best, best_score = t, score
    return best


def ocr_image_tesseractjs(path):
    """tesseract.js（Node，离线 CPU，自带中文模型）。双通道识别取最优。返回文本或 None。"""
    if not (pathlib.Path(__file__).resolve().parent / "data" / "tessdata" / "chi_sim.traineddata.gz").exists():
        return None
    # 通道1：放大2400 + 无对比度 + PSM4（对歌谱小字最好）
    pre1 = _preprocess_image_variant(path, 2400, None)
    t1 = _run_tessjs_direct(pre1, "4")
    try: os.unlink(pre1)
    except OSError: pass
    # 通道2：放大2200 + 对比度1.5 + PSM3
    pre2 = _preprocess_image_variant(path, 2200, 1.5)
    t2 = _run_tessjs_direct(pre2, "3")
    try: os.unlink(pre2)
    except OSError: pass
    best = _pick_best_ocr_text([t1, t2])
    return best or (t1 or t2)


def ocr_image_tesseract(path):
    """tesseract（CPU，兼容无 GPU 环境；需安装 chi_sim）。"""
    if not shutil.which("tesseract"):
        return None
    try:
        out = subprocess.run(["tesseract", path, "stdout", "-l", "chi_sim+eng", "--psm", "6"],
                             capture_output=True, timeout=120)
        if out.returncode != 0:
            out = subprocess.run(["tesseract", path, "stdout", "-l", "eng", "--psm", "6"],
                                 capture_output=True, timeout=120)
        t = out.stdout.decode("utf-8", errors="replace").strip()
        return t or None
    except Exception:
        return None


# ---------------------------------------------------------------- AI 视觉识别（可选）
def ai_ocr_image(path, settings=None):
    """OpenAI 兼容视觉模型识别图片 → {title, firstLine, lyrics, number, note} 或 None。"""
    if not settings:
        return None
    key = (settings.get("openaiKey") or "").strip()
    base = (settings.get("openaiBase") or "https://api.openai.com/v1").rstrip("/")
    model = settings.get("openaiModel") or "gpt-4o-mini"
    if not key:
        return None
    import base64
    import urllib.request
    try:
        b64 = base64.b64encode(pathlib.Path(path).read_bytes()).decode("utf-8")
    except Exception:
        return None
    mime = "image/png"
    prompt = ("你是赞美诗资料整理助手。请识别这张赞美诗图片中的文字，只输出 JSON（不要输出其他内容）："
              '{"title":"歌名","firstLine":"歌词第一句","lyrics":"完整歌词，每句一行","number":"编号（没有则空字符串）"}')
    body = json.dumps({"model": model, "temperature": 0.1, "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
    ]}]}).encode("utf-8")
    req = urllib.request.Request(base + "/chat/completions", data=body, headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        obj = json.loads(data["choices"][0]["message"]["content"])
        return {"title": str(obj.get("title") or "").strip(),
                "firstLine": str(obj.get("firstLine") or "").strip(),
                "lyrics": str(obj.get("lyrics") or "").strip(),
                "number": str(obj.get("number") or "").strip(),
                "note": "由 AI 视觉识别，请核对后保存"}
    except Exception:
        return None


def recognize_image_full(path, settings=None):
    """四级识别：Vision → tesseract.js → tesseract → AI。返回 (text, engine, ai_parsed)。"""
    v = ocr_image_vision(path)
    if v:
        return v[0], "Vision", None
    t = ocr_image_tesseractjs(path)
    if t:
        return t, "tesseract.js", None
    c = ocr_image_tesseract(path)
    if c:
        return c, "tesseract", None
    if settings and settings.get("openaiKey"):
        ai = ai_ocr_image(path, settings)
        if ai and (ai.get("lyrics") or ai.get("title")):
            txt = "\n".join(x for x in [ai.get("title"), ai.get("lyrics")] if x)
            return txt, "AI", ai
    return "", "", None


def ocr_image(path):
    v = ocr_image_vision(path)
    if v:
        return v[0]
    return ocr_image_tesseract(path)


def parse_image_file(path, filename, settings=None):
    text, engine, ai = recognize_image_full(path, settings)
    if text and text.strip():
        if ai and ai.get("lyrics"):
            songs = [{"title": ai.get("title", ""), "firstLine": ai.get("firstLine", ""),
                      "lyrics": ai.get("lyrics", ""), "source": filename}]
        else:
            # 与拍照识别一致：歌名=曲谱前大字，首行=曲谱行后第一行文字
            parsed = parse_ocr_plain_text(text, filename)
            songs = [{"title": parsed["title"], "firstLine": parsed["firstLine"],
                      "lyrics": parsed["lyrics"], "source": filename}]
        for s in songs:
            s.setdefault("flags", []).append("OCR识别")
        return songs, []
    return [], ["图片 OCR 未识别出文字（可安装 tesseract，或在设置中配置 AI 接口）"]


# ---------------------------------------------------------------- 音频
def parse_audio_file(path, filename):
    return [], ["音频暂不支持离线转写，请人工补充歌名与歌词"]


# ---------------------------------------------------------------- 统一入口
def parse_upload(filename: str, data: bytes, dest_dir: str, settings=None):
    name = os.path.basename(filename)
    safe = re.sub(r"[^\w.\-（）()\u4e00-\u9fff]+", "_", name)
    path = os.path.join(dest_dir, f"{os.urandom(4).hex()}_{safe}")
    with open(path, "wb") as f:
        f.write(data)
    ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
    attachment = {"name": name, "path": path, "ext": ext}

    if ext in ("xlsx", "xlsm", "xls"):
        songs, warns = parse_excel_bytes(data, name)
        kind = "excel"
    elif ext == "csv":
        songs, warns = _parse_csv_bytes(data)
        kind = "csv"
    elif ext == "pdf":
        songs, warns = parse_pdf_bytes(data, name, settings)
        kind = "pdf"
    elif ext in ("docx", "doc"):
        songs, warns = parse_docx_bytes(data, name)
        kind = "word"
    elif ext in ("jpg", "jpeg", "png", "bmp", "webp", "gif", "tif", "tiff"):
        songs, warns = parse_image_file(path, name, settings)
        kind = "image"
    elif ext in ("mp3", "wav", "m4a", "aac", "flac", "ogg", "wma"):
        songs, warns = parse_audio_file(path, name)
        kind = "audio"
    else:
        songs, warns = [], [f"暂不支持的文件类型 .{ext}"]
        kind = "other"

    return songs, warns, {"kind": kind, **attachment}


# ---------------------------------------------------------------- OCR 结果解析（拍照填表用）
def parse_song_from_ocr(lines, source=""):
    def is_noise(t):
        t = t.strip()
        if not t or len(t) < 2:
            return True
        if re.fullmatch(r"[\d\s\-.—·]{1,10}", t):
            return True
        if re.match(r"^(第\s*\d+\s*(首|页)|page\s*\d+|\d+\s*页)", t, re.I):
            return True
        return False

    rows = [l for l in lines if not is_noise(l.get("text", "")) and not _is_notation_line(l.get("text", ""))]
    if not rows:
        return {"title": "", "firstLine": "", "lyrics": "", "number": "", "note": "未识别出文字"}
    number = ""
    m = re.search(r"第\s*(\d{1,4})\s*首", " ".join(l.get("text", "") for l in rows))
    if m:
        number = m.group(1)
    hs = sorted(l.get("h", 0) for l in rows)
    med = hs[len(hs) // 2] if hs else 0
    title = ""
    for l in rows:
        t = l.get("text", "").strip()
        if 2 <= len(t) <= 14 and l.get("h", 0) >= med * 1.1 and not _ANY_PUNCT.search(t):
            title = t
            break
    if not title and rows:
        t0 = rows[0].get("text", "").strip()
        if 2 <= len(t0) <= 16:
            title = t0
    lyrics_lines = [l.get("text", "").strip() for l in rows
                    if l.get("text", "").strip() != title and not is_noise(l.get("text", ""))]
    lyrics = "\n".join(lyrics_lines)
    if not title:
        note = "未可靠识别歌名，请手动核对"
    elif not lyrics:
        note = "识别到歌名但未识别到歌词，请手动补充"
    else:
        note = "已自动提取歌名与歌词，请核对后保存"
    return {"title": title, "firstLine": (lyrics_lines[0] if lyrics_lines else ""),
            "lyrics": lyrics, "number": number, "note": note}


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _is_notation_line(line):
    """简谱/五线谱的曲谱行或乱码行：中文字符占比过低。"""
    t = (line or "").strip()
    if not t:
        return True
    total = len(re.sub(r"\s", "", t))
    if total == 0:
        return True
    cjk = len(_CJK_RE.findall(t))
    if cjk / total < 0.25:
        return True
    if re.match(r"^\s*\d+\s*[=＝]", t):  # 调号行：1=F
        return True
    return False


def parse_ocr_plain_text(text: str, source=""):
    """纯文本 OCR 结果 → {title, firstLine, lyrics, number, note}。
    歌谱规则：歌名 = 曲谱行之前的大字（短、无标点）；
    首行歌词 = 第一个曲谱（数字）行之后的第一个文字行。"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # 找到第一个曲谱行（数字/符号行或调号行）
    first_nota = next((i for i, l in enumerate(lines) if _is_notation_line(l)), None)
    lyric_lines = [(i, l) for i, l in enumerate(lines) if not _is_notation_line(l)]

    # 首行歌词：第一个曲谱行之后的第一行文字
    after = [l for i, l in lyric_lines if first_nota is not None and i > first_nota]
    rest_all = [l for _, l in lyric_lines]
    first = after[0] if after else (rest_all[0] if rest_all else "")
    rest = after if after else rest_all

    # 歌名：曲谱行之前的第一行短文字（没有则取任意短行）
    before = [l for i, l in lyric_lines if first_nota is not None and i < first_nota]
    cands = before if before else rest_all
    title = ""
    for l in cands:
        if 2 <= len(l) <= 14 and not re.search(r"[，。；：？！、…,.;:?!]", l):
            title = l
            break
    if title and rest and rest[0] == title:
        rest = rest[1:]
    if first == title and rest:
        first = rest[0]
    lyrics = "\n".join(rest)
    if not title:
        note = "未识别到歌名，请手动填写（首行歌词已自动提取）" if first else "未识别出文字，请手动填写"
    elif not first:
        note = "识别到歌名但未识别到歌词，请手动补充"
    else:
        note = "已自动提取歌名与首行歌词，请核对后保存"
    return {"title": title, "firstLine": first, "lyrics": lyrics,
            "number": "", "note": note}


def parse_ocr_text(text: str, source=""):
    songs, _warns = segment_hymn_text(text, source)
    if songs and songs[0].get("number"):
        s = songs[0]
        return {"title": s["title"], "firstLine": s.get("firstLine", ""),
                "lyrics": s.get("lyrics", ""), "number": s.get("number", ""),
                "note": "已自动提取（识别到编号" + s.get("number", "") + "），请核对后保存"}
    return None
