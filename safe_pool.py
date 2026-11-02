#!/usr/bin/env python3
"""safe_pool.py — 安全池消耗登记与健康检查（R3 / P0-1）

解决一个真实漏洞：安全池的题如果被日常选题先写了，池子看着还有 8 题，
实际已经空了一格，而没人知道。本脚本用项目自己的 check_topic 做权威判定，
把「已被写过」的题自动标记为 consumed，并在池子见底时告警。

用法：
  python scripts/safe_pool.py --status                 # 看池子状态（默认也会先 sync）
  python scripts/safe_pool.py --sync                   # 只同步：扫描文章，标记已被写过的题
  python scripts/safe_pool.py --consume S02 --date 2026-10-28 --reason l4
  python scripts/safe_pool.py --status --json

退出码：0 正常｜1 池子告警（可用 < 3 或池空）｜2 用法/读取错误
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POOL_PATH = ROOT / "config" / "safe_topics.json"
CHECK_TOPIC = ROOT / "scripts" / "check_topic.py"
MIN_AVAILABLE = 3


def load_pool():
    return json.loads(POOL_PATH.read_text(encoding="utf-8"))


def save_pool(pool):
    POOL_PATH.write_text(json.dumps(pool, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_used(topic, python_exe):
    """复用 check_topic 的严格模式：退出码 1 = 已被写过，0 = 没用过，2 = 参数错。"""
    try:
        # --no-log：状态巡检不是选题探测，不写决策日志（10-27）
        r = subprocess.run([python_exe, str(CHECK_TOPIC), topic, "--no-log"],
                           capture_output=True, text=True, timeout=60)
        return r.returncode == 1
    except Exception:
        return None  # 判定失败时不改状态，避免误标


def sync(pool, python_exe, verbose=True):
    changed = []
    for t in pool.get("topics", []):
        if t.get("used_date"):
            continue
        used = is_used(t["topic"], python_exe)
        if used is None:
            if verbose:
                print(f"[WARN] {t['id']} 判定失败（check_topic 不可用），跳过")
            continue
        if used:
            t["used_date"] = datetime.now().strftime("%Y-%m-%d")
            t["status"] = "consumed"
            t["consumed_reason"] = "auto_detected_by_article_scan"
            changed.append(t["id"])
    if changed:
        save_pool(pool)
        if verbose:
            print(f"[sync] 已标记被写过的题: {', '.join(changed)}")
    elif verbose:
        print("[sync] 无新增消耗")
    return changed


def status(pool):
    topics = pool.get("topics", [])
    available = [t for t in topics if not t.get("used_date")]
    consumed = [t for t in topics if t.get("used_date")]
    print(f"安全池：共 {len(topics)} 题｜可用 {len(available)}｜已消耗 {len(consumed)}")
    for t in topics:
        mark = "✅" if not t.get("used_date") else "⛔"
        tail = f"（{t['used_date']} {t.get('consumed_reason','')}）" if t.get("used_date") else ""
        print(f"  {mark} {t['id']} {t['topic']}{tail}")
    if not available:
        print("[ALERT] 池空：暂停 L4 并立即报告，不允许连续两天为空", file=sys.stderr)
        return 1
    if len(available) < MIN_AVAILABLE:
        print(f"[ALERT] 可用题低于 {MIN_AVAILABLE}，7 天内必须补题", file=sys.stderr)
        return 1
    return 0


def consume(pool, topic_id, date_str, reason):
    for t in pool.get("topics", []):
        if t["id"] == topic_id:
            t["used_date"] = date_str
            t["status"] = "consumed"
            t["consumed_reason"] = reason
            save_pool(pool)
            print(f"[consume] {topic_id} 已标记为 {date_str} 消耗（{reason}）")
            return 0
    print(f"[consume] 找不到 {topic_id}", file=sys.stderr)
    return 2


def main():
    ap = argparse.ArgumentParser(description="安全池消耗登记与健康检查")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--sync", action="store_true")
    ap.add_argument("--consume", help="题目 id，如 S02")
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--reason", default="l4", choices=["l4", "manual", "auto_detected_by_article_scan"])
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        pool = load_pool()
    except Exception as e:
        print(f"[safe_pool] 读取失败: {e}", file=sys.stderr)
        return 2

    if args.consume:
        return consume(pool, args.consume, args.date, args.reason)

    if args.sync or args.status:
        sync(pool, args.python, verbose=not args.json)
        pool = load_pool()

    if args.status:
        if args.json:
            topics = pool.get("topics", [])
            print(json.dumps({
                "total": len(topics),
                "available": sum(1 for t in topics if not t.get("used_date")),
                "consumed": sum(1 for t in topics if t.get("used_date")),
                "topics": [{"id": t["id"], "topic": t["topic"], "used_date": t.get("used_date")}
                           for t in topics],
            }, ensure_ascii=False, indent=2))
        return status(pool)
    return 0


if __name__ == "__main__":
    sys.exit(main())
