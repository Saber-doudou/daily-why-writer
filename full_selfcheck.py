#!/usr/bin/env python3
"""daily-why 全盘自检脚本 — 检查脚本语法/JSON/引用/数据完整性，输出报告"""
import ast
import json
import re
import sys
import subprocess
from pathlib import Path

WS = Path(r"F:\WorkBuddy\daily-why")
SKILL = Path(r"C:\Users\admin\.workbuddy\skills\daily-why-writer")
PY = r"C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe"

report = []

def check(name, ok, detail=""):
    report.append((name, "PASS" if ok else "FAIL", detail))

# ── 1. scripts/*.py 语法 ──
py_files = sorted(WS.glob("scripts/*.py"))
bad = []
for f in py_files:
    try:
        ast.parse(f.read_text(encoding="utf-8"))
    except SyntaxError as e:
        bad.append(f"{f.name}: {e}")
check("scripts/*.py 语法", not bad, f"{len(py_files)} 个文件, 异常: {bad}" if bad else f"{len(py_files)} 个文件全部通过")

# ── 2. config/*.json 合法性 ──
json_files = sorted(WS.glob("config/*.json"))
bad = []
for f in json_files:
    try:
        json.loads(f.read_text(encoding="utf-8"))
    except Exception as e:
        bad.append(f"{f.name}: {e}")
check("config/*.json 合法", not bad, f"{len(json_files)} 个文件, 异常: {bad}" if bad else f"{len(json_files)} 个文件全部通过")

# ── 3. skill references 完整性 ──
refs = ["references/CHECKLIST.md", "references/FORBIDDEN.md", "references/FEEDBACK_LOG.md",
        "references/FEEDBACK_ARCHIVE.md", "references/EXAMPLES.md", "CODE_REVIEW_GUIDE.md",
        "reviewer_prompt.md"]
missing = [r for r in refs if not (SKILL / r).exists()]
check("skill references 存在", not missing, f"缺失: {missing}" if missing else "全部存在")
# writing_rules.json 属于项目 config/（validate_article.py 引用路径），单独验证
rules_ok = (WS / "config" / "writing_rules.json").exists()
check("writing_rules.json (config/) 存在", rules_ok, f"config/writing_rules.json 存在={rules_ok}")

# ── 4. 话题库一致性 ──
try:
    full = json.loads((WS/"config/topics_context.json").read_text(encoding="utf-8"))
    comp = json.loads((WS/"config/topics_context_compact.json").read_text(encoding="utf-8"))
    # full 为 dict 数组（含详情），compact 为字符串数组（精简版），结构不同不可直接 ==
    # 提取话题文本集合对比一致性，并检查 compact 无重复
    def _topic_texts(items):
        out = []
        for it in items:
            if isinstance(it, dict):
                out.append(it.get("topic") or it.get("title") or "")
            else:
                out.append(str(it))
        return [t for t in out if t]
    f_topics, c_topics = _topic_texts(full.get("topic_summaries", [])), _topic_texts(comp.get("topic_summaries", []))
    same = set(f_topics) >= set(c_topics)  # compact 是 full 的子集即可（compact 可能滞后）
    dup = len(set(c_topics)) != len(c_topics)
    check("话题库 full/compact 一致且无重复", same and not dup,
          f"full={len(f_topics)} 条, compact={len(c_topics)} 条, 一致={same}, 重复={dup}")
except Exception as e:
    check("话题库", False, str(e))

# ── 5. 素材池结构 ──
# 10-27 二次改造：判据不再硬编码在自检里，改为读 topic_candidates.json 的 field_spec，
# 与 scripts/topic_candidates.py 共用同一份规则（避免「代码一套、数据一套」再分叉）。
# 背景：原判据要求全部条目含 5 字段且总数 ≤80，与文件 purpose「理论上只增不减」矛盾，
# 且 rejected 天然不带 category/evidence；现按 source 分层，由数据文件自己声明。
try:
    sys.path.insert(0, str(WS/"scripts"))
    import topic_candidates as _TCD
    _tc = json.loads((WS/"config/topic_candidates.json").read_text(encoding="utf-8"))
    _cands = _tc.get("candidates", [])
    _miss = _TCD.validate_pool(_tc)
    # evidence 为质量字段而非结构字段：缺失不改判失败，但必须在报告里点名，
    # 避免「放宽判据 = 信息消失」。历史 5 条无原始证据不可回填。
    _no_ev = [i for i, c in enumerate(_cands)
              if c.get("source") != "rejected" and "evidence" not in c]
    _spec_src = "数据文件 field_spec" if "field_spec" in _tc else "内置默认（数据文件缺 field_spec）"
    check("素材池结构", not _miss and len(_cands) >= 15,
          f"{len(_cands)} 条, 不合规 {len(_miss)} 条{_miss[:6] if _miss else ''}, "
          f"缺 evidence {len(_no_ev)} 条{_no_ev if _no_ev else ''}｜规则来源={_spec_src}")
except Exception as e:
    check("素材池", False, str(e))

# ── 5b. 素材池回捞工具自测（10-27 新增） ──
# 回捞的数据源是决策日志，日志里混着标题复查、严格模式、判重复、往日期和截断标记行。
# 过滤条件写错的后果是把成稿主题或重复话题回灌进池子，下游兜底取到就是废票。
try:
    _r = subprocess.run([PY, str(WS/"scripts/topic_candidates.py"), "--selftest"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    _tail = [l for l in (_r.stdout or "").splitlines() if "自检" in l]
    check("topic_candidates 自测", _r.returncode == 0, _tail[-1] if _tail else f"exit={_r.returncode}")
except Exception as e:
    check("topic_candidates 自测", False, str(e))

# ── 5c. R3.8 推送门回归夹具（10-29 新增）──
# D1 探活重试/不当裁判 + D2 dirty 类不谎报冲突不 abort，纯 mock 无副作用。
# 把「防复发」钉进高频自检（EXP-004 约束优于指令）。
try:
    _r = subprocess.run([PY, str(WS/"scripts/git_push_selftest.py")],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    _tail = [l for l in (_r.stdout or "").splitlines() if "自检" in l]
    check("git_push_selftest R3.8 推送门", _r.returncode == 0, _tail[-1] if _tail else f"exit={_r.returncode}")
except Exception as e:
    check("git_push_selftest R3.8 推送门", False, str(e))

# ── 5d. 交付链路四方一致（10-29 新增，防 #67 复发）──
# 把「该进清单的有没有进 / 清单里的有没有真送到镜像」变成高频自检能抓到的问题。
# 默认只查本地镜像，不查远端（网络不通不得判红，10-28 D1 教训）。
try:
    _r = subprocess.run([PY, str(WS/"scripts/delivery_check.py")],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    _tail = [l for l in (_r.stdout or "").splitlines() if "四方一致" in l or "❌" in l]
    check("delivery_check 四方一致", _r.returncode == 0, _tail[-1] if _tail else f"exit={_r.returncode}")
except Exception as e:
    check("delivery_check 四方一致", False, str(e))

# ── 5e. delivery_check 反向夹具（防「一修就松」把 #67 检查放宽没了）──
try:
    _r = subprocess.run([PY, str(WS/"scripts/delivery_check.py"), "--selftest"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    _tail = [l for l in (_r.stdout or "").splitlines() if "PASS" in l or "FAIL" in l]
    check("delivery_check 反向夹具", _r.returncode == 0, _tail[-1] if _tail else f"exit={_r.returncode}")
except Exception as e:
    check("delivery_check 反向夹具", False, str(e))

# ── 6. 文章数据完整性 ──
arts = sorted(WS.glob("articles/**/*-每日冷知识*.md"))
arts_md = sorted(WS.glob("articles/**/*.md"))
check("articles 文章存在", len(arts) > 100, f"每日冷知识 {len(arts)} 篇, 全部md {len(arts_md)} 个")
# 最近 3 篇抽查结构
recent = arts[-3:]
for a in recent:
    c = a.read_text(encoding="utf-8")
    has_a = bool(re.search(r"^>", c, re.M))
    has_q = len(re.findall(r"\*\*Q[123][：:]", c)) >= 2
    has_f = "冷知识反转" in c
    has_tbl = "|" in c and "核心机制" in c
    check(f"文章结构 {a.name[:20]}", has_a and has_q and has_f and has_tbl,
          f"A={has_a} Q={has_q} F={has_f} 表={has_tbl}")

# ── 7. 投喂素材目录 ──
feed_dirs = sorted([d for d in (WS/"投喂素材").iterdir() if d.is_dir()])
missing_txt = []
for d in feed_dirs:
    for name in ("ds.txt", "ima.txt", "千问.txt", "豆包.txt"):
        if not (d / name).exists():
            missing_txt.append(f"{d.name}/{name}")
check("投喂素材目录 4 空文件", not missing_txt, f"{len(feed_dirs)} 个目录, 缺失: {missing_txt[:5]}" if missing_txt else f"{len(feed_dirs)} 个目录完整")

# ── 8. 备份目录 ──
baks = sorted(WS.glob("备份/*20260813*"))
check("今日备份文件存在", len(baks) >= 3, f"{len(baks)} 个: {[b.name for b in baks]}")

# ── 9. SKILL.md 关键内容抽查 ──
skill_text = (SKILL/"SKILL.md").read_text(encoding="utf-8")
check("SKILL.md 含 v2.0 独立审校", "v2.0 独立 Reviewer" in skill_text or "v2.0 独立审校" in skill_text)
check("SKILL.md 无 v1.1 同步审校残留", "同步审校模式" not in skill_text and "v1.1 同步式审校" not in skill_text, "v1.1 已升级为 v2.0")
check("SKILL.md 含执行权威标注", "执行权威" in skill_text)
check("SKILL.md 含外部源拉取", "外部源拉取" in skill_text or "外部拉取" in skill_text)
check("SKILL.md 无区间 ~", not re.search(r"FP-\d+~\d+", skill_text), "FP-XX~XX 区间写法已清除")

# ── 10. generate_prompt.py 关键内容 ──
gp = (WS/"scripts/generate_prompt.py").read_text(encoding="utf-8")
check("generate_prompt.py 含外部源拉取", "外部源拉取" in gp or "外部拉取" in gp)
check("generate_prompt.py 含独立 Reviewer 审校", "独立 Reviewer" in gp)
check("generate_prompt.py 阶段2 熔断链", "熔断" in gp and "spawn" in gp)
check("generate_prompt.py 无 re-spawn 执行指令", not re.search(r"(?<!不)(?<!禁止)(?<!绝不)re-spawn", gp))

# ── 10.5 automation prompt 关键标记（10-27 新增） ──
# 背景：10-27 推平台时直接手改文本（v2.0→v2.1；schema_version 宽限窗口改到 10-29 硬失败），
# 但没有回写 generate_prompt.py —— 结果「生成器产出」与「线上 prompt」分叉，下次任何人
# 跑 --update-automation 都会把线上覆盖回旧版。此类漂移肉眼看不出来，只能靠标记守门。
_marks = {
    "v2.1 版本头": "（v2.1，spawn",
    "证据卡步骤 4.5": "4.5 **证据卡 + 门禁",
    "成稿证据核对 9.5": "9.5 **成稿证据核对",
    "schema_version 宽限 10-29": "10-29 之后的文件缺此字段判 FAIL，10-27 至 10-28 仅警告",
    "GAP_PATTERNS 路径": "references/GAP_PATTERNS.md",
}
_pf = WS/"config/automation-prompt-latest.txt"
if _pf.exists():
    _pt = _pf.read_text(encoding="utf-8")
    _bad = [k for k, v in _marks.items() if v not in _pt]
    check("automation prompt 标记齐备", not _bad, f"缺失={_bad}" if _bad else f"{len(_marks)}/{len(_marks)} 项齐备")
    # 同一批标记必须同时出现在生成器里，否则下次重生成即回退
    _gbad = [k for k, v in _marks.items() if v not in gp]
    check("generate_prompt 已回写同批标记", not _gbad, f"生成器缺失={_gbad}" if _gbad else f"{len(_marks)}/{len(_marks)} 项齐备")
else:
    check("automation prompt 标记齐备", False, "config/automation-prompt-latest.txt 不存在")
    check("generate_prompt 已回写同批标记", False, "无法校验")

# ── 11. 运行 generate_prompt.py --check ──
r = subprocess.run([PY, str(WS/"scripts/generate_prompt.py"), "--check"], capture_output=True, text=True, encoding="utf-8", errors="replace")
check("generate_prompt.py --check 0 警告", r.returncode == 0 and "警告" not in r.stdout and "warning" not in r.stdout.lower(),
      f"exit={r.returncode} out={r.stdout.strip()[-120:] if r.stdout else ''}")

# ── 12. check_topic.py 抽查 ──
def run_ct(topic, *args):
    # --no-log：自检话题不写决策日志，避免污染素材池回捞的数据源（10-27）
    r = subprocess.run([PY, str(WS/"scripts/check_topic.py"), *args, topic, "--no-log"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
# 2026-10-13 修复（T5 配套）：rc1 原用「为什么蛇没有脚还能爬行？」，随话题库增长
# 与「蛇没有脚还能爬得飞快」字符包含率达 75% ≥70% 阈值，基线即误判重复（实测 FAIL）。
# 根因是测试话题未随库内容更新，非检测器缺陷；换用零候选话题「煮粥溢锅」。
rc1, _ = run_ct("为什么煮粥时火太大会溢锅？")
rc2, _ = run_ct("为什么猫头鹰飞起来没有声音")
rc3, _ = run_ct("为什么香蕉是弯的？", "--angle")
check("check_topic 三态正确", rc1 == 0 and rc2 == 1 and rc3 == 0, f"全新={rc1} 重复={rc2} 角度+--angle={rc3}")

# ── 13. memory 提取验证（专项） ──
# 10-27 修复：原为绝对阈值 ≥70 条，但 08-31 及更早记录已按零损失切割归档到
# archive/自动化执行记忆归档-*.md，主文件只剩 09-01 起的 35 个唯一日期，阈值恒不可达
# （与提取器能力无关，实测提取器对唯一日期覆盖率 100%）。改为覆盖率判据，
# 这样测的是「提取器能不能吃下这个文件」而不是「文件刚好有多长」。
sys.path.insert(0, str(WS/"scripts"))
from topic_utils import extract_topics_from_memory
_mem_path = Path(r"F:\WorkBuddy\daily-why\.workbuddy\automations\automation-1778312519754\memory.md")
mem = extract_topics_from_memory(_mem_path)
_hd = re.findall(r"^## (\d{4}-\d{2}-\d{2})", _mem_path.read_text(encoding="utf-8"), re.MULTILINE)
_uniq = len(set(_hd))
_cov = (len(mem) / _uniq) if _uniq else 0.0
check("memory 新格式提取覆盖率 ≥90%", _cov >= 0.9,
      f"提取 {len(mem)} 条 / 唯一日期 {_uniq} 个 = {_cov:.0%}")

# 输出报告
print("=" * 70)
print("DAILY-WHY 全盘自检报告")
print("=" * 70)
fails = 0
for name, status, detail in report:
    mark = "✅" if status == "PASS" else "❌"
    if status != "PASS":
        fails += 1
    print(f"{mark} {name}: {detail}")
print("=" * 70)
print(f"总计 {len(report)} 项, 通过 {len(report)-fails} 项, 失败 {fails} 项")
sys.exit(1 if fails else 0)
