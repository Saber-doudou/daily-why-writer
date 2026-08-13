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
    same = full.get("topic_summaries") == comp.get("topic_summaries")
    dup = len(set(comp.get("topic_summaries", []))) != len(comp.get("topic_summaries", []))
    check("话题库 full/compact 一致且无重复", same and not dup,
          f"full={full.get('total_count')}/{len(full.get('topic_summaries',[]))}, compact={comp.get('total_count')}/{len(comp.get('topic_summaries',[]))}, 一致={same}, 重复={dup}")
except Exception as e:
    check("话题库", False, str(e))

# ── 5. 素材池结构 ──
try:
    tc = json.loads((WS/"config/topic_candidates.json").read_text(encoding="utf-8"))
    cands = tc.get("candidates", [])
    enums = {"initial", "external", "l2", "rejected"}
    badsrc = [c.get("source") for c in cands if c.get("source") not in enums]
    missfield = [i for i, c in enumerate(cands) if not all(k in c for k in ("topic", "category", "why_hot", "evidence", "source"))]
    check("素材池结构", not badsrc and not missfield and 15 <= len(cands) <= 30,
          f"{len(cands)} 条, 非法source={badsrc}, 缺字段索引={missfield}")
except Exception as e:
    check("素材池", False, str(e))

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
check("SKILL.md 含 v1.1 同步审校", "v1.1 同步式审校" in skill_text)
check("SKILL.md 含执行权威标注", "执行权威" in skill_text)
check("SKILL.md 含外部源拉取", "外部源拉取" in skill_text or "外部拉取" in skill_text)
check("SKILL.md 无区间 ~", not re.search(r"FP-\d+~\d+", skill_text), "FP-XX~XX 区间写法已清除")

# ── 10. generate_prompt.py 关键内容 ──
gp = (WS/"scripts/generate_prompt.py").read_text(encoding="utf-8")
check("generate_prompt.py 含外部源拉取", "外部源拉取" in gp or "外部拉取" in gp)
check("generate_prompt.py 阶段2 禁 spawn", "禁止" in gp and "spawn" in gp)
check("generate_prompt.py 无 re-spawn 执行指令", not re.search(r"(?<!不)(?<!禁止)(?<!绝不)re-spawn", gp))

# ── 11. 运行 generate_prompt.py --check ──
r = subprocess.run([PY, str(WS/"scripts/generate_prompt.py"), "--check"], capture_output=True, text=True, encoding="utf-8", errors="replace")
check("generate_prompt.py --check 0 警告", r.returncode == 0 and "警告" not in r.stdout and "warning" not in r.stdout.lower(),
      f"exit={r.returncode} out={r.stdout.strip()[-120:] if r.stdout else ''}")

# ── 12. check_topic.py 抽查 ──
def run_ct(topic, *args):
    r = subprocess.run([PY, str(WS/"scripts/check_topic.py"), *args, topic], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
rc1, _ = run_ct("为什么蛇没有脚还能爬行？")
rc2, _ = run_ct("为什么猫头鹰飞起来没有声音")
rc3, _ = run_ct("为什么香蕉是弯的？", "--angle")
check("check_topic 三态正确", rc1 == 0 and rc2 == 1 and rc3 == 0, f"全新={rc1} 重复={rc2} 角度+--angle={rc3}")

# ── 13. memory 提取验证（专项） ──
sys.path.insert(0, str(WS/"scripts"))
from topic_utils import extract_topics_from_memory
mem = extract_topics_from_memory(Path(r"F:\WorkBuddy\daily-why\.workbuddy\automations\automation-1778312519754\memory.md"))
check("memory 新格式提取 ≥70", len(mem) >= 70, f"提取 {len(mem)} 条")

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
