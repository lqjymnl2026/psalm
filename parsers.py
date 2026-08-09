# -*- coding: utf-8 -*-
"""导入解析：Excel / CSV / PDF / Word / 图片 / 音频 → 曲目字典列表。"""
from __future__ import annotations

import csv
import io
import os
import re
import shutil
import subprocess
import tempfile
import json
import pathlib
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
}

_HEADER_CACHE = {}


def normalize_header(h: str) -> str:
    return re.sub(r"[\s\u3000·\.\-_]+", "", str(h or "")).lower()


def match_column(header: str):
    """返回标准字段名；找不到返回 None。"""
    key = normalize_header(header)
    if key in _HEADER_CACHE:
        return _HEADER_CACHE[key]
    result = None
    # 1) 精确匹配别名
    for field, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            if normalize_header(a) == key:
                result = field
                break
        if result:
            break
    # 2) 模糊匹配
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
    """headers: 原始表头列表; rows: 数据行列表 → [song dict]"""
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
    """返回 (songs, warnings)"""
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
            text = data.decode(enc)
            return text, enc
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8"


def _parse_csv_bytes(data: bytes):
    text, enc = _try_decode_csv(data)
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(text[:4096], delimiters=",;\t")
    except Exception:
        dialect = csv.excel
    reader = list(csv.reader(io.StringIO(text), dialect))
    if not reader:
        return [], ["CSV 没有数据"]
    headers = [_clean(x) for x in reader[0]]
    songs = _map_rows(headers, reader[1:])
    return songs, []


# ---------------------------------------------------------------- 曲目切分（PDF / Word 共用）
_TITLE_RE = re.compile(r"^\s*(?:第\s*)?(\d{1,4})\s*[、.．。)）\]\-\s:：]+\s*(\S.{0,40}?)\s*$")
_SONG_NO_RE = re.compile(r"^\s*(?:第\s*)?(\d{1,4})\s*[、.．。)）\]\-\s:：]+\s*(\S.{0,40})$")
_PAGE_RE = re.compile(r"^\s*(?:[-—]*\s*)?(\d{1,4})\s*(?:页)?\s*$")
_HYMNBOOK_RE = re.compile(r"(?:赞美诗|诗歌|圣诗|颂赞)[^0-9]{0,12}?(?:第\s*)?(\d{1,4})\s*首?[：:\s]*(\S{2,40})")


def _looks_like_title(s: str) -> bool:
    t = s.strip()
    if not t:
        return False
    if len(t) > 42:
        return False
    if re.fullmatch(r"[\d\s\-—.。、()（）页pP]{1,10}", t):
        return False
    if re.search(r"[\u4e00-\u9fffA-Za-z]", t) is None:
        return False
    if re.search(r"页\s*$", t) or re.search(r"^page\s*\d+", t, re.I):
        return False
    return True


def segment_hymn_text(text: str, source: str):
    """把整篇文本切分为 [{number, title, lyrics}]；返回 (songs, warnings)"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [l.rstrip() for l in text.split("\n")]
    entries = []
    current = None
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        m = _SONG_NO_RE.match(line) or _HYMNBOOK_RE.search(line)
        if m and _looks_like_title(m.group(2)):
            if current:
                entries.append(current)
            number = m.group(1)
            title = re.sub(r"[\s]+", " ", m.group(2)).strip(" \t-—。.，,")
            current = {"number": number, "title": title, "lyrics": ""}
            continue
        if current is not None:
            current["lyrics"] += (line + "\n")
        else:
            # 文本开头没有编号，尝试把第一行当作标题
            if _looks_like_title(line):
                current = {"number": "", "title": line[:40], "lyrics": ""}
    if current:
        entries.append(current)

    songs = []
    for e in entries:
        lyrics = e["lyrics"].strip()
        songs.append({
            "title": e["title"],
            "number": e["number"],
            "lyrics": lyrics,
            "firstLine": (lyrics.splitlines()[0].strip() if lyrics else ""),
            "source": source,
        })
    if not songs:
        return [], ["未识别出曲目编号，请人工拆分或改用 Excel 导入"]
    # 若存在带编号的曲目，则丢弃无编号的条目（通常为封面/书名行）
    if any(s.get("number") for s in songs):
        songs = [s for s in songs if s.get("number")]
    return songs, []


# ---------------------------------------------------------------- PDF
def parse_pdf_bytes(data: bytes, filename: str):
    import pdfplumber
    warnings = []
    pages_text = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for pg in pdf.pages:
            try:
                t = pg.extract_text() or ""
            except Exception as e:  # pragma: no cover
                warnings.append(f"第 {pg.page_number} 页解析失败: {e}")
                continue
            pages_text.append(t)
    full = "\n".join(pages_text)
    if not full.strip():
        return [], ["PDF 中没有可提取的文字（可能是扫描版，需 OCR）"]
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
    # 表格内容
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


# ---------------------------------------------------------------- 图片 OCR（可插拔）
def ocr_image(path: str):
    """优先 macOS Vision，其次系统 tesseract。返回文本；失败返回 None。"""
    v = ocr_image_vision(path)
    if v:
        return v[0]
    if not shutil.which("tesseract"):
        return None
    langs = "chi_sim+eng"
    try:
        out = subprocess.run(
            ["tesseract", path, "stdout", "-l", langs, "--psm", "6"],
            capture_output=True, timeout=120,
        )
        if out.returncode != 0:
            # 尝试纯英文
            out = subprocess.run(["tesseract", path, "stdout", "-l", "eng", "--psm", "6"],
                                 capture_output=True, timeout=120)
        return out.stdout.decode("utf-8", errors="replace") if out.returncode == 0 else None
    except Exception:
        return None


def parse_image_file(path: str, filename: str):
    """图片：保存后尝试 OCR；不可用则标记待人工。"""
    if ocr_available():
        text = ocr_image(path)
        if text and text.strip():
            songs, warnings = segment_hymn_text(text, filename)
            for s in songs:
                s["flags"] = ["OCR识别"]
            return songs, warnings
        return [], ["图片 OCR 未识别出文字，请人工补充"]
    return [], ["本机未安装 OCR（tesseract + chi_sim），图片已保存，请人工补充信息"]


# ---------------------------------------------------------------- 音频
def parse_audio_file(path: str, filename: str):
    return [], ["音频暂不支持离线转写，请人工补充歌名与歌词"]


# ---------------------------------------------------------------- 统一入口
def parse_upload(filename: str, data: bytes, dest_dir: str):
    """保存文件并解析。返回 (songs, warnings, attachment)"""
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
        songs, warns = parse_pdf_bytes(data, name)
        kind = "pdf"
    elif ext in ("docx", "doc"):
        songs, warns = parse_docx_bytes(data, name)
        kind = "word"
    elif ext in ("jpg", "jpeg", "png", "bmp", "webp", "gif", "tif", "tiff"):
        songs, warns = parse_image_file(path, name)
        kind = "image"
    elif ext in ("mp3", "wav", "m4a", "aac", "flac", "ogg", "wma"):
        songs, warns = parse_audio_file(path, name)
        kind = "audio"
    else:
        songs, warns = [], [f"暂不支持的文件类型 .{ext}"]
        kind = "other"

    return songs, warns, {"kind": kind, **attachment}


# ---------------------------------------------------------------- macOS Vision OCR
def ensure_ocr_tool():
    """确保编译好的 Vision OCR 工具存在。返回路径或 None。"""
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
    if shutil.which("tesseract"):
        return "tesseract"
    return ""


def ocr_available():
    return bool(ocr_engine_name())


def ocr_image_vision(path):
    """调用 macOS Vision（中文+英文）。返回 (text, lines) 或 None。"""
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


def parse_song_from_ocr(lines, source=""):
    """从 OCR 行（已按从上到下排序）启发式提取 歌名/首句/歌词。"""
    def is_noise(t):
        t = t.strip()
        if not t or len(t) < 2:
            return True
        if re.fullmatch(r"[\d\s\-.—·]{1,10}", t):
            return True
        if re.match(r"^(第\s*\d+\s*(首|页)|page\s*\d+|\d+\s*页)", t, re.I):
            return True
        return False

    rows = [l for l in lines if not is_noise(l.get("text", ""))]
    if not rows:
        return {"title": "", "firstLine": "", "lyrics": "", "number": "", "note": "未识别出文字"}
    number = ""
    m = re.search(r"第\s*(\d{1,4})\s*首", " ".join(l.get("text", "") for l in rows))
    if m:
        number = m.group(1)
    # 标题启发式：高度显著大于中位数的短行（通常标题字号更大）
    hs = sorted(l.get("h", 0) for l in rows)
    med = hs[len(hs) // 2] if hs else 0
    title = ""
    for l in rows:
        t = l.get("text", "").strip()
        if 2 <= len(t) <= 14 and l.get("h", 0) >= med * 1.1 and not re.search(r"[，。；：、？！…]", t):
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


def parse_ocr_text(text: str, source=""):
    """OCR 全文 → 若含编号结构则取第一首。返回 dict 或 None。"""
    songs, _warns = segment_hymn_text(text, source)
    if songs and songs[0].get("number"):
        s = songs[0]
        return {"title": s["title"], "firstLine": s.get("firstLine", ""),
                "lyrics": s.get("lyrics", ""), "number": s.get("number", ""),
                "note": "已自动提取（识别到编号" + s.get("number", "") + "），请核对后保存"}
    return None
