# -*- coding: utf-8 -*-
"""本地智能引擎：自动分类 + 去重相似度。完全离线可用。"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

try:
    import zhconv
except Exception:  # pragma: no cover
    zhconv = None


def t2s(s: str) -> str:
    """繁体转简体（尽力而为）。"""
    if not s:
        return s or ""
    if zhconv is not None:
        try:
            return zhconv.convert(s, "zh-cn")
        except Exception:
            return s
    return s


# ---------------------------------------------------------------- 圣经主题
THEMES = {
    "敬拜": ["敬拜", "俯伏", "屈膝", "尊崇", "称颂", "颂赞", "荣耀归于", "worship"],
    "赞美": ["赞美", "歌颂", "颂扬", "赞歌", "哈利路亚", "称颂", "颂赞", "荣耀"],
    "感恩": ["感恩", "感谢", "谢恩", "称谢", "赐福", "施恩", "恩惠", "感谢神", "谢主"],
    "救恩": ["救恩", "拯救", "救主", "救赎", "得救", "救世", "拯救者", "salvation", "redeem", "失丧", "寻回"],
    "恩典": ["恩典", "恩惠", "怜悯", "奇异恩典", "主恩", "grace", "慈恩"],
    "十字架": ["十字架", "十架", "受难", "钉十", "各各他", "髑髅地", "cross"],
    "宝血": ["宝血", "流血", "洗净", "赦罪", "赎罪", "洁净"],
    "复活": ["复活", "复生", "空坟墓", "坟墓已空", "resurrection", "risen", "清晨"],
    "信心": ["信心", "信靠", "坚信", "倚靠", "faith", "trust"],
    "盼望": ["盼望", "指望", "等候", "将来", "hope"],
    "爱": ["慈爱", "怜爱", "仁爱", "相爱", "爱主", "love", "挚爱"],
    "圣洁": ["圣洁", "至圣", "圣哉", "holy"],
    "悔改": ["悔改", "认罪", "回转", "归向", "赦免", "罪人", "罪恶", "罪孽", "罪愆"],
    "祷告": ["祷告", "祈祷", "祈求", "恳求", "默祷", "prayer", "求主"],
    "圣灵": ["圣灵", "灵风", "圣灵的", "spirit"],
    "教会": ["教会", "团契", "圣徒", "肢体", "church", "合一", "弟兄"],
    "宣教": ["宣教", "传福音", "福音", "万民", "普世", "差遣", "列邦", "万国", "mission"],
    "再来": ["再来", "再临", "降临", "迎接主", "主必快来", "parousia"],
    "永生": ["永生", "天堂", "天家", "天国", "乐园", "永远", "永恒", "新天新地", "heaven", "eternal"],
}

# ---------------------------------------------------------------- 崇拜场景
SCENARIOS = {
    "普通主日": ["主日", "礼拜", "崇拜", "聚会", "同心"],
    "开始礼拜": ["开始", "宣召", "序乐", "进堂", "开篇"],
    "结束礼拜": ["结束", "殿乐", "退堂", "差遣", "祝福", "阿们", "阿门"],
    "圣餐": ["圣餐", "掰饼", "举杯", "主的晚餐", "纪念主", "饼杯", "擘饼"],
    "洗礼": ["洗礼", "受洗", "浸礼", "重生"],
    "婚礼": ["婚礼", "婚约", "嫁娶", "盟约", "夫妻", "完全的爱", "婚礼颂"],
    "葬礼": ["葬礼", "追思", "离世", "诀别", "丧礼", "安息主怀"],
    "布道": ["布道", "传道", "决志", "呼召", "福音", "见证"],
    "祷告会": ["祷告会", "同心合意", "恳求", "祈求"],
    "青年": ["青年", "年少", "少年", "青春"],
    "儿童": ["儿童", "孩童", "小孩", "小小", "摇篮"],
    "诗班": ["诗班", "唱诗班", "合唱", "四部", "和声"],
    "安息日": ["安息日", "守日"],
    "圣诞": ["圣诞", "降生", "伯利恒", "马槽", "平安夜", "以马内利", "天使", "博士", "圣诞夜"],
    "复活节": ["复活节", "复活", "复生", "空坟墓", "坟墓已空"],
}

# ---------------------------------------------------------------- 音乐类型
MUSIC_TYPES = {
    "传统圣诗": ["圣诗", "赞美诗", "hymn", "传统"],
    "现代敬拜": ["现代", "敬拜", "颂赞", "worship", "新歌"],
    "福音诗歌": ["福音", "布道", "gospel", "见证", "决志"],
    "儿童诗歌": ["儿童", "孩童", "小小"],
    "诗班": ["诗班", "合唱", "cantata", "anthem", "和声"],
    "四声部": ["四声部", "四部", "satb", "和声", "声部"],
    "独唱": ["独唱", "solo"],
    "会众诗歌": ["会众", "众唱", "齐唱", "congregation"],
    "安静默想": ["默想", "安静", "静默", "沉思", "灵修", "晚祷"],
    "奋兴": ["奋兴", "复兴", "火热", "奋起"],
    "宣教": ["宣教", "差遣", "万民", "普世", "mission", "列邦"],
}

_NS = re.compile(r"[\s\W_]+", re.UNICODE)
_CJK = re.compile(r"[^\u4e00-\u9fff]", re.UNICODE)


def normalize_text(s: str) -> str:
    s = t2s(s or "").lower()
    s = _NS.sub("", s)
    return s


def _bigram_jaccard(a: str, b: str) -> float:
    def grams(x: str):
        if len(x) < 2:
            return {x} if x else set()
        return {x[i:i + 2] for i in range(len(x) - 1)}
    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def _count_hits(text: str, kws) -> int:
    t = t2s(text or "").lower()
    n = 0
    for kw in kws:
        k = t2s(kw).lower()
        if k and k in t:
            n += 1
    return n


def classify_category(song: dict, categories: dict):
    """按「编定圣诗分类」配置计算 (大类, 细类)。categories: {大类: {细类:[关键词], "大类词":[关键词]}}"""
    if not categories:
        return "", ""
    blob = " ".join([song.get("title", ""), song.get("firstLine", ""), song.get("lyrics", ""),
                     song.get("lyricist", ""), song.get("composer", ""), song.get("source", ""), song.get("tune", "")])
    title = song.get("title", "") or ""
    best = ("", "", 0.0)
    for cat, items in categories.items():
        cat_hits = _count_hits(blob, items.get("大类词") or []) * 0.6
        for sub, kws in items.items():
            if sub == "大类词":
                continue
            hits = _count_hits(blob, kws) + 1.5 * _count_hits(title, kws)
            score = hits + cat_hits
            if score > best[2]:
                best = (cat, sub, score)
    return best[0], best[1]


def classify(song: dict, categories=None) -> dict:
    """返回 themes / scenarios / musicTypes / difficulty / singability / confidence / needsReview / category / subcategory"""
    category, subcategory = classify_category(song, categories) if categories else ("", "")
    title = song.get("title") or ""
    first = song.get("firstLine") or ""
    lyrics = song.get("lyrics") or ""
    lyricist = song.get("lyricist") or ""
    composer = song.get("composer") or ""
    source = song.get("source") or ""
    tune = song.get("tune") or ""
    blob = " ".join([title, first, lyrics, lyricist, composer, source, tune])

    def rank(table):
        scored = []
        for cat, kws in table.items():
            hits = _count_hits(blob, kws)
            if title:
                hits += 2 * _count_hits(title, kws)
            if first:
                hits += _count_hits(first, kws)
            if hits > 0:
                scored.append((hits, cat))
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored]

    themes = rank(THEMES)[:3]
    scenarios = rank(SCENARIOS)[:3]
    mtypes = rank(MUSIC_TYPES)[:2]
    if not mtypes:
        mtypes = ["传统圣诗"]
    # ---- 常识补充规则 ----
    if ("救恩" in themes or "悔改" in themes or "宣教" in themes) and "布道" not in scenarios:
        scenarios = (scenarios + ["布道"])[:3]
    if not scenarios and set(themes) & {"敬拜", "赞美", "圣洁"}:
        scenarios = ["普通主日"]
    if not themes and "圣诞" in scenarios:
        themes = ["敬拜"]

    lines = [l for l in (lyrics or "").splitlines() if l.strip()]
    difficulty = 3
    if lines:
        total = len("".join(lines))
        avg = sum(len(l) for l in lines) / len(lines)
        uniq = len(set("".join(lines))) / max(1, total)
        score = 1.0
        if total > 700:
            score += 1.0
        elif total > 350:
            score += 0.5
        if avg > 13:
            score += 1.2
        elif avg > 9:
            score += 0.6
        if uniq > 0.5:
            score += 0.8
        if len(lines) > 10:
            score += 0.5
        if len(lines) <= 4:
            score -= 0.5
        difficulty = max(1, min(5, round(score)))

    sing = 6 - difficulty
    if lines and max(len(l) for l in lines) <= 9:
        sing += 1
    if lines and len(lines) <= 6:
        sing += 1
    sing = max(1, min(5, sing))

    confidence = 0.0
    if themes or scenarios:
        confidence = 0.5 + 0.16 * len(themes) + 0.12 * len(scenarios) + 0.1 * len(mtypes)
        confidence = min(0.98, confidence)
    needs_review = not (themes and scenarios and mtypes) or confidence < 0.72

    return {
        "themes": themes,
        "scenarios": scenarios,
        "musicTypes": mtypes,
        "difficulty": difficulty,
        "difficultyStars": "★" * difficulty + "☆" * (5 - difficulty),
        "singability": sing,
        "singabilityStars": "★" * sing + "☆" * (5 - sing),
        "confidence": round(confidence, 2),
        "needsReview": bool(needs_review),
        "category": category,
        "subcategory": subcategory,
    }


# ---------------------------------------------------------------- 去重
def title_similarity(a: str, b: str) -> float:
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    # 中文部分相同（如“奇异恩典” vs “奇异恩典 Amazing Grace”）
    cja, cjb = _CJK.sub("", na), _CJK.sub("", nb)
    if cja and cjb and cja == cjb:
        return 0.88
    if na in nb or nb in na:
        return 0.6 + 0.4 * (min(len(na), len(nb)) / max(len(na), len(nb)))
    sm = SequenceMatcher(None, na, nb).ratio()
    bj = _bigram_jaccard(na, nb)
    return round(max(sm, bj), 4)


def lyric_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return 0.0
    if len(na) < 6 or len(nb) < 6:
        return round(SequenceMatcher(None, na, nb).ratio(), 4)
    # 短文本完整包含在长文本中 → 强烈重复信号
    short, long = (na, nb) if len(na) <= len(nb) else (nb, na)
    if short in long:
        return round(0.7 + 0.3 * (len(short) / len(long)), 4)
    sm = SequenceMatcher(None, na, nb).ratio()
    bj = _bigram_jaccard(na, nb)

    def first_lines(s, n):
        ls = [l for l in s.splitlines() if l.strip()][:n]
        return normalize_text("".join(ls))
    la, lb = [l for l in a.splitlines() if l.strip()], [l for l in b.splitlines() if l.strip()]
    n = max(1, min(len(la), len(lb), 2))
    head = SequenceMatcher(None, first_lines(a, n), first_lines(b, n)).ratio()
    return round(max(sm, bj, head), 4)


def combined_similarity(a: dict, b: dict) -> float:
    t = title_similarity(a.get("title", ""), b.get("title", ""))
    lyr = lyric_similarity(a.get("lyrics", ""), b.get("lyrics", ""))
    if lyr > 0:
        return round(0.55 * t + 0.45 * lyr, 4)
    return t


def find_duplicates(songs: list, dup_th=0.80, group_prefix="D"):
    """
    贪心聚类疑似重复。
    返回 [{group, members:[{id,title,score}], maxScore}]
    """
    active = [s for s in songs if s.get("status") != "merged"]
    groups = []
    used = set()
    gi = 1
    for i, a in enumerate(active):
        if a["id"] in used:
            continue
        members = [{"id": a["id"], "title": a.get("title", ""), "score": 1.0}]
        for j, b in enumerate(active):
            if i == j or b["id"] in used:
                continue
            sc = combined_similarity(a, b)
            if sc >= dup_th:
                members.append({"id": b["id"], "title": b.get("title", ""), "score": sc})
        if len(members) > 1:
            members.sort(key=lambda m: -m["score"])
            groups.append({"group": f"{group_prefix}{gi:03d}", "members": members, "maxScore": members[1]["score"]})
            gi += 1
            for m in members:
                used.add(m["id"])
    return groups
