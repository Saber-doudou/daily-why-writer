#!/usr/bin/env python3
"""达尔文实验：验证 _detect_ima_version() 修复前后的输出对比。

运行方式：
    python darwin_version_test.py

实验报告自动写入 .workbuddy/memory/darwin_experiment_log.tsv
"""
import re, json, sys, tempfile, shutil
from pathlib import Path

# ── 实验参数 ──────────────────────────────────────────
MEMORY_MD = Path(__file__).resolve().parent.parent / ".workbuddy" / "memory" / "MEMORY.md"
LOG_TSV = Path(__file__).resolve().parent.parent / ".workbuddy" / "memory" / "darwin_experiment_log.tsv"

# 头信息
R = {
    "1": "SeniorDeveloper",
    "2": "CodeReviewExpert",
    "3": "DarwinSynthetic",
}

# ── 被测函数（修复后版本） ────────────────────────────

def detect_version_new(content: str) -> str:
    """修复后：regex 兼容括号 + 降级搜索 + 满9进位"""
    if not content:
        return "1.0"
    section = re.search(r"## IMA 备份历史[^\n]*\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    if section:
        versions = re.findall(r"\bv(\d+\.\d+)\b", section.group(1))
    else:
        versions = re.findall(r"\bv(\d+\.\d+)\b", content)
    if versions:
        latest = max(versions, key=lambda v: [int(x) for x in v.split(".")])
        major, minor = [int(x) for x in latest.split(".")]
        minor += 1
        if minor >= 10:
            major += 1
            minor = 0
        return f"{major}.{minor}"
    return "1.0"


def detect_version_old(content: str) -> str:
    """修复前版本（原始 buggy 版本）"""
    if not content:
        return "3.0"
    section = re.search(r"## IMA 备份历史\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    if section:
        versions = re.findall(r"\bv(\d+\.\d+)\b", section.group(1))
        if versions:
            latest = max(versions, key=lambda v: [int(x) for x in v.split(".")])
            parts = latest.split(".")
            minor = int(parts[1]) + 1 if len(parts) > 1 else 1
            return f"{parts[0]}.{minor}"
    return "3.0"


# ── 测试用例 ──────────────────────────────────────────

TEST_CASES = [
    {
        "id": 1,
        "desc": "括号标题：## IMA 备份历史（最近5条）",
        "content": """
## 写作规范
略

## IMA 备份历史（最近5条）
| 版本 | note_id | 日期 | 说明 |
|------|---------|------|------|
| v3.8 | ... | 2026-06-22 | 自动备份 |
| v3.9 | ... | 2026-06-24 | 自动备份 |

## 关键教训
略
""",
        "expected_new": "4.0",
        "expected_old": "3.0",  # ← bug：括号卡死匹配，回退 3.0
    },
    {
        "id": 2,
        "desc": "标准标题：## IMA 备份历史（无括号）",
        "content": """
## IMA 备份历史
| 版本 | note_id | 日期 | 说明 |
|------|---------|------|------|
| v3.8 | ... | 2026-06-22 | 自动备份 |
| v3.9 | ... | 2026-06-24 | 自动备份 |
""",
        "expected_new": "4.0",
        "expected_old": "4.0",  # 旧版能匹配标准标题
    },
    {
        "id": 3,
        "desc": "v3.9 → 进位到 v4.0",
        "content": """
## IMA 备份历史
| 版本 | note_id | 日期 | 说明 |
|------|---------|------|------|
| v3.9 | ... | 2026-06-24 | 自动备份 |
""",
        "expected_new": "4.0",
        "expected_old": "3.10",  # ← bug：3.9 → 3.10
    },
    {
        "id": 4,
        "desc": "v3.10（异常值）→ 进位到 v4.0",
        "content": """
## IMA 备份历史
| 版本 | note_id | 日期 | 说明 |
|------|---------|------|------|
| v3.10 | ... | 2026-06-25 | 自动备份 |
""",
        "expected_new": "4.0",
        "expected_old": "3.11",  # ← bug：3.10 → 3.11 继续滚
    },
    {
        "id": 5,
        "desc": "v4.8 → v4.9（不触发进位）",
        "content": """
## IMA 备份历史
| 版本 | note_id | 日期 | 说明 |
|------|---------|------|------|
| v4.8 | ... | 2026-06-25 | 自动备份 |
""",
        "expected_new": "4.9",
        "expected_old": "4.9",  # 两者都可以
    },
    {
        "id": 6,
        "desc": "v4.9 → v5.0（跨大版本进位）",
        "content": """
## IMA 备份历史
| 版本 | note_id | 日期 | 说明 |
|------|---------|------|------|
| v4.9 | ... | 2026-06-25 | 自动备份 |
""",
        "expected_new": "5.0",
        "expected_old": "4.10",  # ← bug：4.9 → 4.10
    },
    {
        "id": 7,
        "desc": "空文件 / 无备份历史章节 → 降级全文搜索",
        "content": """
# 测试文件
文中有一处 v2.3 版本提到...
还有一处 v1.7 的较早记录...
""",
        "expected_new": "2.4",
        "expected_old": "3.0",  # ← bug：找不到表就回退 3.0
    },
    {
        "id": 8,
        "desc": "真实 MEMORY.md 快照（实时读取）",
        "content": "（从文件读取）",
        "is_file_snapshot": True,
        "expected_new": "4.2",  # MEMORY.md 最新 v4.1 → v4.2
        "expected_old": "3.11", # 旧版：3.10 → 3.11
    },
]


def run_test(tc: dict) -> dict:
    content = tc.get("content", "")
    if tc.get("is_file_snapshot"):
        if MEMORY_MD.exists():
            content = MEMORY_MD.read_text(encoding="utf-8")
        else:
            return {"id": tc["id"], "desc": tc["desc"], "error": "MEMORY.md 不存在"}

    new_result = detect_version_new(content)
    old_result = detect_version_old(content)

    new_pass = new_result == tc["expected_new"]
    old_pass = old_result == tc["expected_old"]

    return {
        "id": tc["id"],
        "desc": tc["desc"],
        "new": new_result,
        "new_exp": tc["expected_new"],
        "new_pass": new_pass,
        "old": old_result,
        "old_exp": tc["expected_old"],
        "old_pass": old_pass,
    }


# ── 报告 ──────────────────────────────────────────────

def print_report(results):
    print("=" * 90)
    print("  达尔文实验报告 — _detect_ima_version() 修复验证")
    print("=" * 90)
    print()
    print(f"{'#':>2} | {'描述':<30} | {'旧版出':>8} | {'旧版期':>8} | {'新版出':>8} | {'新版期':>8} | {'状态':>6}")
    print("-" * 90)
    new_ok = old_ok = 0
    for r in results:
        new_emoji = "✅" if r["new_pass"] else "❌"
        old_emoji = "✅" if r["old_pass"] else "❌"
        print(f"{r['id']:>2} | {r['desc']:<30} | {r['old']:>8} | {r['old_exp']:>8} | {r['new']:>8} | {r['new_exp']:>8} | 旧{old_emoji} 新{new_emoji}")
        if r["new_pass"]: new_ok += 1
        if r["old_pass"]: old_ok += 1
    print("-" * 90)
    print(f"  旧版通过: {old_ok}/8  |  新版通过: {new_ok}/8")
    print()

    # 汇总
    if new_ok == 8:
        print("  ✅ 修复全部通过！")
    else:
        print(f"  ⚠️ 新版有 {8 - new_ok} 个测试未通过:")
        for r in results:
            if not r["new_pass"]:
                print(f"    #{r['id']} {r['desc']}: 期望 {r['new_exp']}，实际 {r['new']}")


def log_results(results):
    """追加实验记录到 TSV"""
    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    new_ok = sum(1 for r in results if r["new_pass"])
    old_ok = sum(1 for r in results if r["old_pass"])

    LOG_TSV.parent.mkdir(parents=True, exist_ok=True)
    header = "timestamp\tround\tskill\told_score\tnew_score\tstatus\tdimension\tnote"
    row = f"{now}\t1\tl3_publish._detect_ima_version\t{old_ok}\t{new_ok}\t{'keep' if old_ok < new_ok or (old_ok == new_ok and new_ok == 8) else 'revert'}\t版本检测\t修复regex+降级+进位，8用例 旧{old_ok}/8 新{new_ok}/8"

    if not LOG_TSV.exists():
        LOG_TSV.write_text(header + "\n", encoding="utf-8")
    with open(LOG_TSV, "a", encoding="utf-8") as f:
        f.write(row + "\n")


if __name__ == "__main__":
    import datetime
    print(f"\n  实验时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  MEMORY.md: {MEMORY_MD}\n")

    results = [run_test(tc) for tc in TEST_CASES]
    print_report(results)
    log_results(results)
    print(f"\n  日志已追加到: {LOG_TSV}")
