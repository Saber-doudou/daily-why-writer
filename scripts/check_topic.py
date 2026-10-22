#!/usr/bin/env python3
"""
check_topic.py — 话题去重校验脚本（机械性防护网）

用法：
    python check_topic.py "为什么xxx？"
    python check_topic.py --topic "为什么xxx？"
    python check_topic.py --file 2026-06-08-每日冷知识.md
    python check_topic.py --angle "为什么xxx？"              # 角度模式：相似度 0.50 到 0.70 之间放行并提示（列出全部候选）
    python check_topic.py --threshold 0.60 "为什么xxx？"      # 自定义重复阈值（默认 0.70）
    python check_topic.py --angle --threshold 0.60 "为什么xxx？"

退出码：
    0 = 通过（话题未使用过；角度模式下相似度 0.50 到阈值之间的"角度相关"话题放行，
        但输出含"⚠️ 角度相关"提示及全部候选列表，需人工逐个确认写作角度与已有话题不同）
    1 = 重复（话题已存在：精确匹配 / 语义相似 / 概念重叠；
        概念重叠为硬重复，--angle 不可覆盖，与字符包含率 ≥70% 同等效力）
    2 = 参数错误

设计原则：
    - 纯机械比对，不依赖 AI 判断力
    - 四层检测：精确匹配 + 关键词交集 + 概念重叠（检查 4，2026-10-13 新增）
    - 同时检查 topics_context.json 和已有文章文件
    - 角度模式（--angle）：相似度落在 [0.50, 阈值) 区间的候选属于"同一现象的不同角度"，
      放行并提示；未开启时该区间仍判重复，保持原严格行为
    - 概念文件缺失或为空 → 降级为现状行为 + stderr 醒目警告（不静默 fail-open）

2026-10-13 整改（依据 deliverables/2026-10-13-check_topic整改任务书.md，事件复盘：
10-13「牛排血水」候选 50.0% 漏判、被 66.7%「雪」top-1 报告掩蔽）：
    - T1 概念重叠检测：config/topic_concepts.json，generic（大类词，仅提示）/ specific
      （现象词）两层；命中同一 concept 且双方 specific 各 ≥1 **且双方 generic 各 ≥1**
      （同主体才拦；F1 2026-10-13 补充：单字 specific「咸/盐」曾误拦「汗水咸/融雪盐」）
      → 硬重复。机制词（如肌红蛋白）禁止入表：同机制不同现象必须放行。
    - T2 角度模式全候选报告：≥0.50 候选全部输出（分数降序，至少前 5 条并给出总数），
      不再只报 top-1；ASCII 引号 " ' 加入剥离集（修复 0x22 残留虚增公共字符：
      10-13 两篇牛排标题各虚增 1 个公共字符，66.7% 实为 62.5%）。
    - T4 去重决策日志：每次判定追加 JSONL 到 logs/check_topic_decisions.jsonl，
      使漏判率/误杀率可度量；不影响退出码与现有输出格式。
"""

import re
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# 疑问前缀，提取关键词前先去掉
QUESTION_PREFIXES = ["为什么", "怎么", "什么", "为何", "为啥"]

# ⚠️ 已废弃勿用（2026-10-13 T5 锁行为标记）：本常量定义了却从未被使用，
# 且与 extract_core_chars 的内联 stop_chars 不一致（多一个「不」）。
# 「不」保留在 core 字符中是检测灵敏度的一部分（牛排用例 50.0% 依赖它：
# 若把「不」并入停用字表，A1 会跌到 42.9%、A2 从 62.5% 跌到 57.1%，灵敏度被无声削弱）。
# 禁止把本表「统一」进内联停用字表 —— dedup_selftest 锁行为测试会拦截该回退。
STOP_WORDS = frozenset([
    "的", "了", "会", "是", "在", "都", "就", "也", "还",
    "和", "与", "或", "有", "没", "不", "能", "可以",
    "总是", "竟然", "居然", "到底", "究竟",
    "人", "我们", "自己", "一个",
])

# 交集比例阈值（核心字符包含率 ≥70% → 判重复）
# 60% 会误杀"海水蓝 vs 海水咸"（通用字"海""水"拉高比例）
OVERLAP_THRESHOLD = 0.70

# 角度相关下限：相似度落在 [ANGLE_THRESHOLD, OVERLAP_THRESHOLD) 区间的话题
# 属于"同一现象的不同角度"（如"猫头鹰飞起来没声音"vs"猫头鹰晚上能看清猎物"）。
# 开启 --angle 时该区间放行（退出码 0）并输出提示，未开启时仍判重复（退出码 1）。
ANGLE_THRESHOLD = 0.50

# ── T1 概念重叠检测 ──
# 概念表路径（相对 workspace/config/）；schema：
#   {"concepts": {"家族名": {"generic": [大类词], "specific": [现象词]}}}
CONCEPTS_FILE = "topic_concepts.json"

# ── T2 角度模式全候选报告 ──
# 至少展示的角度候选条数（不足则全列）
ANGLE_REPORT_MIN = 5

# ── T4 去重决策日志 ──
DECISION_LOG_FILE = "check_topic_decisions.jsonl"
DECISION_LOG_MAX_BYTES = 5 * 1024 * 1024   # 超过 5MB 自动截断
DECISION_LOG_KEEP_BYTES = 2 * 1024 * 1024  # 截断时保留的尾部字节预算（按行边界对齐，F2）
DECISION_LOG_MIN_SCORE = 0.3               # matches 只记 ≥0.3 的候选（F2：零分噪声无度量价值）


def normalize_topic(text: str) -> str:
    """标准化话题文本：去 emoji、去首尾空白、统一全角半角"""
    text = re.sub(
        r'[\U0001F000-\U0001FFFF\U00002700-\U000027BF\U0000FE00-\U0000FE0F'
        r'\U0000200D\U00002600-\U000026FF\U00002300-\U000023FF\U00002B50'
        r'\U0000231A-\U0000231B\U00002934\U00002935\U000025AA-\U000025FE'
        r'\U00002B05-\U00002B07\U00002B1B-\U00002B1C\U00003030\U0000303D'
        r'\U00003297\U00003299\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF'
        r'\U00002702-\U000027B0]+',
        '', text
    )
    text = text.strip().replace('\u3000', '')
    return text


def extract_core_chars(text: str) -> str:
    """
    提取话题的核心字符（去前缀、去标点、去停用字）。

    用于字符级语义相似度检测。

    2026-10-13 T2：ASCII 引号 " ' 加入剥离集。此前 0x22/0x27 残留在 core 中，
    使含引号的话题各虚增公共字符（10-13 两篇牛排标题的 66.7% 实为 62.5%）。
    """
    normalized = normalize_topic(text)

    # 去掉疑问前缀
    for prefix in QUESTION_PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break

    # 去标点和空白（含全角/半角引号）
    normalized = re.sub(
        r"""[？?！!。，,、；;："'“”‘’\u3000\s]+""",
        '', normalized
    )

    # 去停用单字（的/了/会/是/在/都/就/也/还/和/与/或/有/没/不/能/人）
    # 注意：与 STOP_WORDS 常量故意保持不一致——「不」必须保留（见该常量注释）
    stop_chars = set("的了会是在都就也还和与或有没能人可以")
    chars = [c for c in normalized if c not in stop_chars]

    return ''.join(chars)


def check_semantic_similarity(new_topic: str, existing_topic: str,
                              threshold: float = OVERLAP_THRESHOLD) -> tuple[bool, float, str]:
    """
    字符级包含率检测：短文本的字是否都在长文本中出现。

    原理：去掉"为什么"前缀和停用字后，如果新话题的大部分字
    都在已有话题中出现过，说明它们在说同一件事。

    参数:
        threshold: 判重复的相似度阈值（默认 OVERLAP_THRESHOLD，可被 --threshold 覆盖）

    返回: (is_similar: bool, score: float, detail: str)
        is_similar=True 表示相似度 ≥ threshold（判重复）；
        score 落在 [ANGLE_THRESHOLD, threshold) 区间时由调用方决定是否角度放行。
    """
    core_new = extract_core_chars(new_topic)
    core_existing = extract_core_chars(existing_topic)

    if len(core_new) < 3 or len(core_existing) < 3:
        return False, 0.0, "核心字符不足"

    set_new = set(core_new)
    set_existing = set(core_existing)

    # 短的一方做分母
    if len(set_new) <= len(set_existing):
        smaller, larger = set_new, set_existing
        smaller_text = core_new
    else:
        smaller, larger = set_existing, set_new
        smaller_text = core_existing

    if not smaller:
        return False, 0.0, "无有效字符"

    common = smaller & larger
    ratio = len(common) / len(smaller)

    if ratio >= threshold:
        return True, ratio, (
            f"字符包含率 {ratio:.0%}: "
            f"「{core_new}」vs「{core_existing}」交集 {common}"
        )

    return False, ratio, f"字符包含率 {ratio:.0%} < {threshold:.0%}"


# ─────────────────────────────────────────────────────────────
# T1 概念重叠检测（2026-10-13 新增，检查 4）
# ─────────────────────────────────────────────────────────────

def load_concepts(workspace: Path) -> dict:
    """加载概念表 {workspace}/config/topic_concepts.json（T1）。

    文件缺失 / JSON 损坏 / 无 concepts 键或为空 → 返回 {} 并向 stderr 输出
    醒目警告：概念层失效必须可见，禁止静默降级（Silent Fail-Open 防线）。
    字符级检测不受影响，仍按现状执行。
    """
    path = Path(workspace) / "config" / CONCEPTS_FILE
    if not path.exists():
        print(f"[check_topic] ⚠️ 概念表缺失: {path} — 概念重叠检测（检查4）降级关闭，"
              f"仅字符级检测生效", file=sys.stderr)
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[check_topic] ⚠️ 概念表解析失败: {path} — {e} — "
              f"概念重叠检测（检查4）降级关闭", file=sys.stderr)
        return {}
    concepts = data.get("concepts") if isinstance(data, dict) else None
    if not concepts:
        print(f"[check_topic] ⚠️ 概念表为空: {path} — 概念重叠检测（检查4）降级关闭",
              file=sys.stderr)
        return {}
    return concepts


def extract_concept_hits(text: str, concepts: dict) -> dict:
    """提取文本命中的概念（T1）。

    返回 {concept_name: {"generic": [命中词...], "specific": [命中词...]}}，
    仅保留有命中的概念。匹配方式为子串包含（中文无分词，子串匹配零依赖）。
    """
    hits = {}
    for name, spec in concepts.items():
        if not isinstance(spec, dict):
            continue
        generic = [w for w in spec.get("generic", []) if w and w in text]
        specific = [w for w in spec.get("specific", []) if w and w in text]
        if generic or specific:
            hits[name] = {"generic": generic, "specific": specific}
    return hits


def check_concept_overlap(new_topic: str, all_existing: list,
                          concepts: dict) -> tuple[bool, str]:
    """概念重叠检测（T1 检查 4；判定规则为 2026-10-13 修正版，F1 补充 generic 共现条件）。

    规则：
      - 新话题与某已有话题命中同一 concept，且双方 specific 各 ≥1，
        **且双方 generic 各 ≥1**（同主体才拦）→ 硬重复
        （exit 1，--angle 不可覆盖，与字符包含率 ≥70% 同等效力）；
      - 仅 generic 命中 → 不提示不拦（同大类是常态，避免噪音）；
      - 机制词禁止入表（维护纪律）：同机制不同现象（如真空包装绽色 vs 血水）
        必须放行，故 specific 只收现象词。

    F1（2026-10-13）：单字 specific（咸/盐）在中文子串匹配下精度不足——「汗水为什么
    是咸的」与「海水是咸的」共享的是属性词而非主体词，曾遭误拦且拦截理由误导。
    generic 共现条件把这条边界机械化：汗水/融雪不含 generic 词 → 不拦；
    「大海里的盐」与「海水」主体互通（大海/海水 互为 generic）→ 仍拦。
    已知取舍：不含量化主词的措辞（如「海里的盐」）会漏拦，属精度优先的定向交换。

    返回: (is_duplicate: bool, detail: str)
    """
    if not concepts:
        return False, ""
    new_hits = extract_concept_hits(new_topic, concepts)
    if not new_hits:
        return False, ""
    for source, existing_topic, meta in all_existing:
        ex_hits = extract_concept_hits(existing_topic, concepts)
        for name, nh in new_hits.items():
            if not nh["specific"]:
                continue  # 新侧仅 generic 命中 → 不拦
            eh = ex_hits.get(name)
            # F1：specific 双侧命中 + generic 双侧命中（同主体）才判硬重复
            if eh and eh["specific"] and nh["generic"] and eh["generic"]:
                meta_str = f"（{meta}）" if meta else ""
                return True, (
                    f"概念重叠 [{source}]{meta_str}: \"{existing_topic}\" — "
                    f"概念[{name}] 双侧命中"
                    f"（主词: 新话题 {'/'.join(nh['generic'])} vs "
                    f"已有 {'/'.join(eh['generic'])}；"
                    f"现象词: 新话题 {'/'.join(nh['specific'])} vs "
                    f"已有 {'/'.join(eh['specific'])}），判重复"
                    f"（概念硬重复，--angle 不可覆盖）"
                )
    return False, ""


# ─────────────────────────────────────────────────────────────
# T2 角度模式全候选报告
# ─────────────────────────────────────────────────────────────

def format_angle_candidates(angle_matches: list) -> str:
    """角度候选全量报告（T2）：≥0.50 按分数降序，至少前 ANGLE_REPORT_MIN 条 + 总数。

    修复前只报 top-1：10-13 牛排 50.0% 被雪 66.7% 掩盖，执行人看到的信息本身残缺。
    """
    total = len(angle_matches)
    shown = angle_matches[:ANGLE_REPORT_MIN]
    lines = [f"共 {total} 个候选（相似度 ≥{ANGLE_THRESHOLD:.0%}，按分数降序展示前 {len(shown)} 个）："]
    for i, (source, existing_topic, meta, score) in enumerate(shown, 1):
        meta_str = f"（{meta}）" if meta else ""
        lines.append(f"{i}. {score:.0%} [{source}]{meta_str}: \"{existing_topic}\"")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# T4 去重决策日志
# ─────────────────────────────────────────────────────────────

def _truncate_decision_log(log_path: Path) -> None:
    """F2：按字节预算截断——超过 5MB 时从尾部保留约 2MB（按行边界对齐）+ 标记行。

    修复前按行数截断（保留 2000 行）：单条含全量 matches 时 2000 行 ≈ 26MB，
    截断后文件仍超 5MB，且此后每次调用都全文件读取 + 重写。
    """
    lines = log_path.read_text(encoding="utf-8").splitlines()
    kept: list[str] = []
    size = 0
    for line in reversed(lines):
        line_size = len(line.encode("utf-8")) + 1  # +1 为换行符
        if kept and size + line_size > DECISION_LOG_KEEP_BYTES:
            break
        kept.append(line)
        size += line_size
    kept.reverse()
    marker = (f"[truncated] 超过 {DECISION_LOG_MAX_BYTES // (1024 * 1024)}MB "
              f"自动截断，仅保留最近约 {DECISION_LOG_KEEP_BYTES // (1024 * 1024)}MB")
    log_path.write_text(marker + "\n" + "\n".join(kept) + "\n", encoding="utf-8")


def log_decision(topic: str, mode: str, threshold: float, exclude_date,
                 verdict: str, matches: list, workspace) -> None:
    """每次判定追加 JSONL 到 {workspace}/logs/check_topic_decisions.jsonl（T4）。

    schema：{ts, mode, threshold, exclude_date, topic, verdict, matches[{source, topic, score}]}
    目的：漏判率/误杀率可度量（blogcog 经验：不要只统计拦了多少）；事件复盘可查
    「门为何放行」。

    F2（2026-10-13）：① matches 只记 score ≥ DECISION_LOG_MIN_SCORE 的候选
    （实测 78% 为 score=0.0 噪声，对度量零贡献，单条最大 19,765 字符）；
    ② 截断改字节预算（_truncate_decision_log），修复「按行数截断永不压回 5MB 以下」。

    任何日志失败仅 stderr 警告，不影响退出码与输出格式。
    """
    try:
        log_dir = Path(workspace) / "logs"
        log_dir.mkdir(exist_ok=True)
        log_path = log_dir / DECISION_LOG_FILE
        if log_path.exists() and log_path.stat().st_size > DECISION_LOG_MAX_BYTES:
            _truncate_decision_log(log_path)
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "mode": mode,
            "threshold": threshold,
            "exclude_date": exclude_date,
            "topic": topic,
            "verdict": verdict,
            "matches": [
                {"source": s, "topic": t, "score": round(sc, 4)}
                for s, t, _m, sc in matches
                if sc >= DECISION_LOG_MIN_SCORE
            ],
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[check_topic] ⚠️ 决策日志写入失败（不影响判定）: {e}", file=sys.stderr)


def extract_topic_from_article(filepath: Path) -> str | None:
    """从文章文件提取标题（首个非空行，去 '#' 前缀；emoji 由 normalize_topic 去除）。

    09-15 修复（缺陷 #51）：原实现只认 '#' 开头的行，而新格式文章首行是
    「emoji + 标题」（无 '#'，如 09-08 蜂蜜文「🍯 为什么蜂蜜能放几千年都不坏？」），
    导致此类文章在文件扫描路径上是去重盲区（仅靠 memory.md 兜底）。
    现对齐 l3_publish._extract_topic_from_file 的首行策略。
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue  # 跳过空行，取首个非空行
                return line.lstrip('#').strip() or None
    except Exception:
        pass
    return None


def check_topic(topic: str, workspace: Path, threshold: float = OVERLAP_THRESHOLD,
                angle_mode: bool = False,
                exclude_date: str | None = None) -> tuple[bool, str]:
    """
    检查话题是否已使用过（四层检测：精确匹配 + 语义相似 + 概念重叠）。

    参数:
        topic: 待校验话题
        workspace: 工作目录（含 config/topics_context.json 与 articles/）
        threshold: 判重复的相似度阈值（默认 0.70，可被 --threshold 覆盖）
        angle_mode: 角度模式；开启后相似度落在 [ANGLE_THRESHOLD, threshold) 区间的话题放行，
                    返回 False 且 detail 含"⚠️ 角度相关"提示及全部候选列表。
                    概念重叠（检查 4）为硬重复，angle_mode 不可覆盖。
        exclude_date: 排除该日期（YYYY-MM-DD）的自身记录，避免「自己匹配自己」。
                     09-09 修复：L3 去重卡点校验当日文章时，articles/ 中当日文件与
                     topics_context 当日条目均须排除，否则恒判重复。
                     已知边界：topic_summaries 为字符串列表（无 date 字段），无法按
                     exclude_date 排除；依赖时序假设（topics_context 刷新先于当日
                     文章写入），T3 成稿标题复查与该假设兼容。

    返回: (is_duplicate: bool, detail: str)
    """
    normalized = normalize_topic(topic)
    if not normalized:
        return False, "话题为空"

    mode = "angle" if angle_mode else "strict"
    evaluated = []  # [(source, topic, meta, score)] 已评估候选（T4 决策日志用）

    def _finish(is_dup: bool, detail: str) -> tuple[bool, str]:
        log_decision(topic, mode, threshold, exclude_date,
                     "duplicate" if is_dup else "pass", evaluated, workspace)
        return is_dup, detail

    all_existing = []  # 收集所有已有话题用于语义/概念检测

    # === 检查 1: topics_context.json ===
    context_file = Path(workspace) / "config" / "topics_context.json"
    if context_file.exists():
        try:
            with open(context_file, 'r', encoding='utf-8') as f:
                context = json.load(f)

            # 注意：topic_summaries 为字符串列表（无 date 字段），无法按 exclude_date 排除当日自身。
            # 依赖时序假设：L3 发布流程在 dedup_gate_check 之后才将当日话题写入 topics_context，
            # 故查重时 topic_summaries 不含当日条目。若改为「先写后查」，须给 topic_summaries 条目补 date 字段并加排除逻辑。
            # 精确匹配 + 收集话题
            for existing in context.get("topic_summaries", []):
                norm_existing = normalize_topic(existing)
                if norm_existing == normalized:
                    evaluated.append(("topic_summaries", existing, None, 1.0))
                    return _finish(True, f"精确匹配 topic_summaries: \"{existing}\"")
                all_existing.append(("topic_summaries", existing, None))

            for entry in context.get("topics", []):
                entry_topic = entry.get("topic", "")
                if exclude_date and str(entry.get("date", "")) == exclude_date:
                    continue  # 排除当日自身条目
                norm_entry = normalize_topic(entry_topic)
                if norm_entry == normalized:
                    evaluated.append(("topics", entry_topic, entry.get("date"), 1.0))
                    return _finish(True, (
                        f"精确匹配 topics 数组: \"{entry_topic}\""
                        f"（{entry.get('date', '?')}，{entry.get('file', '?')}）"
                    ))
                all_existing.append(("topics", entry_topic, entry.get("date")))

        except Exception as e:
            print(f"[check_topic] ⚠️ 读取 topics_context.json 失败: {e}", file=sys.stderr)

    # === 检查 2: 扫描已有文章文件 ===
    for md_file in sorted(Path(workspace).glob("articles/**/*-每日冷知识*.md")):
        if exclude_date and md_file.name.startswith(exclude_date):
            continue  # 排除当日自身文章（初版/优化版互不匹配）
        if "_废弃" in md_file.name:
            continue  # 软删除标记（09-15）：Azure 教训——标记必须被读取方识别，否则等于没删
        file_topic = extract_topic_from_article(md_file)
        if file_topic:
            if normalize_topic(file_topic) == normalized:
                evaluated.append(("file", file_topic, md_file.name, 1.0))
                return _finish(True, f"精确匹配文章文件: {md_file.name}")
            all_existing.append(("file", file_topic, md_file.name))

    # === 检查 3: 语义相似度检测 ===
    angle_matches = []  # 角度相关候选（相似度落在 [ANGLE_THRESHOLD, threshold) 区间）
    for source, existing_topic, meta in all_existing:
        is_sim, score, detail = check_semantic_similarity(topic, existing_topic, threshold)
        evaluated.append((source, existing_topic, meta, score))
        if is_sim:
            meta_str = f"（{meta}）" if meta else ""
            return _finish(True, (
                f"语义相似 [{source}]{meta_str}: \"{existing_topic}\" — {detail}"
            ))
        if score >= ANGLE_THRESHOLD:
            angle_matches.append((source, existing_topic, meta, score))

    # === 检查 4: 概念重叠检测（T1，2026-10-13 新增）===
    # 位置：检查 3 之后、角度报告之前。命中即硬重复，--angle 不可覆盖。
    concepts = load_concepts(workspace)
    is_concept_dup, concept_detail = check_concept_overlap(topic, all_existing, concepts)
    if is_concept_dup:
        return _finish(True, concept_detail)

    # 角度相关候选：相似度落在 [ANGLE_THRESHOLD, threshold) 区间
    # --angle 开启 → 放行并输出全部候选提示（由上层逐个确认）
    # --angle 未开启 → 仍判重复（严格模式），同样列出全部候选
    if angle_matches:
        angle_matches.sort(key=lambda x: x[3], reverse=True)
        candidate_report = format_angle_candidates(angle_matches)
        if angle_mode:
            return _finish(False, (
                f"⚠️ 角度相关，请逐个确认写作角度与下列已有话题不同\n{candidate_report}"
            ))
        return _finish(True, (
            f"语义相似 [角度相关区间] {candidate_report}\n"
            f"若确认写作角度不同请用 --angle 模式放行"
        ))

    return _finish(False, "话题未使用过，可以写作")


def main():
    parser = argparse.ArgumentParser(description="话题去重校验")
    parser.add_argument("topic_positional", nargs='?', help="要校验的话题（位置参数）")
    parser.add_argument("--topic", "-t", help="要校验的话题")
    parser.add_argument("--file", "-f", help="从文章文件提取话题并校验")
    parser.add_argument("--threshold", type=float, default=OVERLAP_THRESHOLD,
                        help=f"语义相似重复阈值（默认 {OVERLAP_THRESHOLD}）")
    parser.add_argument("--angle", action="store_true",
                        help="角度模式：相似度 0.50 到阈值之间的角度相关话题放行并输出提示（全部候选）")
    parser.add_argument("--workspace", "-w", default=r"F:\WorkBuddy\daily-why",
                        help="工作目录路径")
    parser.add_argument("--exclude-date", default=None,
                        help="排除该日期(YYYY-MM-DD)的自身记录，避免自匹配（L3 去重卡点必传）")
    args = parser.parse_args()

    if args.threshold <= 0 or args.threshold > 1:
        print("[check_topic] ❌ 阈值必须在 0 到 1 之间", file=sys.stderr)
        sys.exit(2)
    if args.angle and args.threshold <= ANGLE_THRESHOLD:
        print(f"[check_topic] ⚠️ 阈值 {args.threshold} 不大于角度下限 {ANGLE_THRESHOLD}，"
              f"角度模式将不会放行任何话题", file=sys.stderr)

    # 确定话题来源
    topic = args.topic or args.topic_positional
    if args.file:
        filepath = Path(args.workspace) / args.file
        topic = extract_topic_from_article(filepath)
        if not topic:
            print(f"[check_topic] ❌ 无法从文件提取话题: {args.file}", file=sys.stderr)
            sys.exit(2)

    if not topic:
        print("[check_topic] ❌ 未提供话题。用法: check_topic.py \"为什么xxx？\"", file=sys.stderr)
        sys.exit(2)

    workspace = Path(args.workspace)
    is_dup, detail = check_topic(topic, workspace,
                                 threshold=args.threshold, angle_mode=args.angle,
                                 exclude_date=args.exclude_date)

    if is_dup:
        print(f"[check_topic] ❌ 重复: {detail}")
        sys.exit(1)
    else:
        print(f"[check_topic] ✅ 通过: {detail}")
        sys.exit(0)


if __name__ == "__main__":
    main()
