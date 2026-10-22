#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
memory_decay.py —— 铁律衰减与淘汰门禁（v3 闸门 4）

背景（v3 方案 2026-09-08，Master 裁定）：
    外部经验：Procedural 记忆保留门槛最高，但须做有效性复审
    （AWS AgentCore）；衰减评分 = 0.3*recency + 0.3*access_freq
    + 0.2*freshness + 0.2*type_weight（happyin）。
    Master 拍板日更项目加速版：**10 天未触发 → 降级；20 天 → 下沉**；
    **被引用或对应错误再犯 → 立即升回最高**（外部只有 Refresh-on-Read，
    "再犯即升"是本项目新增的负反馈）。

作用：
    扫描 topics/iron_rules.md，按 last_accessed 计算闲置天数，
    输出每条的状态与建议动作。默认只读报告，不改文件。

用法：
    python memory_decay.py                    # 报告当前状态
    python memory_decay.py --json             # 机器可读
    python memory_decay.py --touch §04        # 记录被引用（Refresh-on-Read）
    python memory_decay.py --boost §04        # 再犯即升：升回最高优先级
    python memory_decay.py --apply            # 把到期判定写入分片元数据（只动 topics，不改 MEMORY.md）
                                                # 改前自动快照；MEMORY.md 常驻/索引由 AI 按 decay 标记人工校准

退出码：
    0 = 无需处置（或有处置但 --apply 成功）
    1 = 存在待处置项且未 --apply（供门禁接入）

v1.1 2026-09-08  --apply 落地：到期判定写入元数据行 `- decay: 状态(闲置X天) ｜ 判定日期 ｜ 人工动作`；
                  幂等（重复判定只更新日期）；touch/boost 复活时清除 decay 标记
v1.0 2026-09-08
"""
import argparse
import io
import json
import os
import re
import shutil
import sys
from datetime import datetime, date

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(BASE, ".workbuddy", "memory", "topics", "iron_rules.md")

DEMOTE_DAYS = 10   # 未触发 → 从常驻降为索引行
SINK_DAYS = 20     # 未触发 → 下沉（主文件删行，仅留指针）
BOOST_ACCESS = 5   # "再犯即升"/"被引用"时的计数加成

SEC_RE = re.compile(r"^## (§\d+)\s+(.+)$", re.M)
# 容忍 pin 被加粗（如 `**pin: true**（低频高代价））与行尾说明文字
META_RE = re.compile(r"^-\s*owner:\s*(\S+)\s*｜\s*type:\s*(\S+)\s*｜\s*\*{0,2}pin\*{0,2}:\s*(\w+)", re.M)
TRIG_RE = re.compile(r"^-\s*trigger:\s*(.+)$", re.M)
DATE_RE = re.compile(r"^-\s*created:\s*(\S+)\s*｜\s*last_accessed:\s*(\S+)\s*｜\s*access_count:\s*(\d+)", re.M)
# apply 写入的判定标记行：`- decay: 待降级(闲置11天) ｜ 判定 2026-09-18 ｜ 人工：...`
DECAY_RE = re.compile(r"^-\s*decay:.*\n?", re.M)


def parse_date(s):
    s = (s or "").strip()
    if not s or s in ("—", "-", "unknown"):
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def load_rules(path=RULES_PATH):
    if not os.path.exists(path):
        return []
    text = io.open(path, encoding="utf-8").read()
    marks = list(SEC_RE.finditer(text))
    rules = []
    for i, m in enumerate(marks):
        body = text[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(text)]
        mm = META_RE.search(body)
        mt = TRIG_RE.search(body)
        md = DATE_RE.search(body)
        rules.append({
            "id": m.group(1),
            "title": m.group(2).strip(),
            "owner": (mm.group(1).strip() if mm else "unknown"),
            "type": (mm.group(2).strip() if mm else "procedural"),
            "pin": (bool(mm) and mm.group(3).strip().lower() == "true"),
            "trigger": (mt.group(1).strip() if mt else ""),
            "created": (md.group(1) if md else None),
            "last_accessed": parse_date(md.group(2)) if md else None,
            "access_count": (int(md.group(3)) if md else 0),
        })
    return rules


def score_of(r, today):
    """衰减评分（改造自 AWS/happyin 公式），仅用于排序参考，不直接决定动作。"""
    if not r["last_accessed"]:
        return 0.0
    age = (today - r["last_accessed"]).days
    recency = 1.0 / (1 + age / 30.0)
    access_freq = min(r["access_count"] / 10.0, 1.0)
    freshness = 1.0 / (1 + max(age, 0) / 7.0)
    type_w = 1.0 if r["type"] == "procedural" else 0.5
    return round(0.3 * recency + 0.3 * access_freq + 0.2 * freshness + 0.2 * type_w, 3)


def evaluate(r, today):
    """返回 (状态, 建议动作, 闲置天数)。"""
    if r["pin"]:
        return "常驻(pin)", "保持（低频高代价，豁免衰减）", None
    if not r["last_accessed"]:
        return "未知", "补充 last_accessed 后再判定", None
    days = (today - r["last_accessed"]).days
    if days >= SINK_DAYS:
        return "待下沉", f"闲置 {days} 天 ≥ {SINK_DAYS}：主文件删行，仅留指针", days
    if days >= DEMOTE_DAYS:
        return "待降级", f"闲置 {days} 天 ≥ {DEMOTE_DAYS}：常驻 → 触发索引行", days
    return "活跃", "保持", days


def report(rules, today, as_json=False):
    rows = []
    for r in rules:
        st, act, days = evaluate(r, today)
        rows.append({**r, "status": st, "action": act, "idle_days": days,
                     "score": score_of(r, today),
                     "last_accessed": r["last_accessed"].isoformat() if r["last_accessed"] else None})
    todo = [x for x in rows if x["status"] in ("待降级", "待下沉")]

    if as_json:
        print(json.dumps({"today": today.isoformat(), "total": len(rows),
                          "todo": len(todo), "rules": rows},
                         ensure_ascii=False, indent=2))
        return todo

    print("=" * 68)
    print(f"铁律衰减报告　{today.isoformat()}　（降级 {DEMOTE_DAYS} 天 / 下沉 {SINK_DAYS} 天）")
    print("=" * 68)
    print(f"{'ID':<5}{'状态':<12}{'闲置':>4}  {'分':<6}{'owner':<9}{'标题'}")
    print("-" * 68)
    for x in sorted(rows, key=lambda v: (v["status"] != "待下沉", v["status"] != "待降级",
                                         -(v["idle_days"] or 0))):
        idl = f"{x['idle_days']}d" if x["idle_days"] is not None else "-"
        print(f"{x['id']:<5}{x['status']:<12}{idl:>5}  {x['score']:<6}{x['owner']:<9}{x['title'][:26]}")
    print("-" * 68)
    if todo:
        print(f"待处置 {len(todo)} 条：")
        for x in todo:
            print(f"  {x['id']} {x['title'][:20]} → {x['action']}")
    else:
        print("✅ 无需处置：全部活跃或 pin 豁免")
    print("=" * 68)
    return todo


def _edit_block(path, rid, transform, label):
    """按 rid（如 §04）定位分片块，transform(part)->part 就地改写。

    统一走这里：读文件 → 改前 .bak 快照 → 分块定位 → 改写 → 写回。
    返回 0 成功 / 1 未找到或未命中。
    """
    text = io.open(path, encoding="utf-8").read()
    if rid not in text:
        print(f"❌ 未找到 {rid}")
        return 1
    shutil.copy(path, path + f".bak-{datetime.now():%Y%m%d-%H%M%S}")
    out, hit = [], False
    for part in re.split(r"(?=^## §\d+)", text, flags=re.M):
        if part.startswith(f"## {rid}"):
            new = transform(part)
            if new is not None:
                part, hit = new, True
        out.append(part)
    if not hit:
        print(f"❌ {rid} 无匹配元数据，未修改")
        return 1
    io.open(path, "w", encoding="utf-8").write("".join(out))
    print(f"✅ {rid} {label}（快照 .bak-* 已留）")
    return 0


def touch(rid, boost=False, path=RULES_PATH):
    """--touch：记录被引用；--boost：再犯即升（计数加成 + 重置计时 + 清除 decay 标记）。"""
    today = date.today().isoformat()

    def tf(part):
        dm = DATE_RE.search(part)
        if not dm:
            return None
        cnt = int(dm.group(3)) + (BOOST_ACCESS if boost else 1)
        new = f"- created: {dm.group(1)} ｜ last_accessed: {today} ｜ access_count: {cnt}"
        part = part[:dm.start()] + new + part[dm.end():]
        # 复活：清除此前 apply 写入的 decay 标记（被引用 = 该条仍活跃，旧判定作废）
        part = DECAY_RE.sub("", part)
        return part

    label = "已升回最高（再犯即升，清除 decay 标记）" if boost else \
            "已记录引用（last_accessed=今天，清除 decay 标记）"
    return _edit_block(path, rid, tf, label)


def apply(rules, today, path=RULES_PATH):
    """--apply：把到期判定写入分片元数据。

    设计（Master 2026-09-08 拍板「只动 topics 元数据」）：
    - 只改 topics/iron_rules.md；MEMORY.md 的常驻/索引由 AI 按本文件中的 decay 标记人工校准
      （脚本不解析主文件结构，避免误删常驻内容）
    - 对每条「待降级/待下沉」写入 `- decay: 状态(闲置X天) ｜ 判定 日期 ｜ 人工：...`，旧标记先删后插 → 幂等
    - 全文永不删除（EXP-012：遗忘 = 归档，非删除）
    """
    todo = []
    for r in rules:
        st, act, days = evaluate(r, today)
        if st in ("待降级", "待下沉"):
            todo.append((r["id"], st, act, days))
    if not todo:
        print("✅ 无待处置条目，apply 无事可做")
        return 0

    n_ok = 0
    for rid, st, act, days in todo:
        hint = "常驻→降为触发索引行" if st == "待降级" else "移除索引/常驻，仅留本 topics 指针"
        line = f"- decay: {st}(闲置{days}天) ｜ 判定 {today} ｜ 人工：MEMORY.md 该条{hint}"

        def tf(part, _line=line):
            dm = DATE_RE.search(part)
            if not dm:
                return None
            part = DECAY_RE.sub("", part)   # 删旧标记（幂等；状态变化时旧标记不残留）
            dm = DATE_RE.search(part)       # DATE 行在 decay 行前，不受 sub 影响
            return part[:dm.end()] + "\n" + _line + part[dm.end():]

        if _edit_block(path, rid, tf, f"已写入 {st} 标记") == 0:
            n_ok += 1
    print(f"✅ apply 完成：{n_ok}/{len(todo)} 条已打标")
    return 0


def main():
    ap = argparse.ArgumentParser(description="铁律衰减与淘汰门禁")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--touch", metavar="ID", help="记录被引用（Refresh-on-Read）")
    ap.add_argument("--boost", metavar="ID", help="再犯即升：升回最高优先级")
    ap.add_argument("--apply", action="store_true",
                    help="把到期判定写入分片元数据（只动 topics/iron_rules.md，MEMORY.md 由人工按标记校准）")
    ap.add_argument("--path", default=RULES_PATH, help="指定分片路径（测试用）")
    args = ap.parse_args()

    if args.touch:
        return touch(args.touch, path=args.path)
    if args.boost:
        return touch(args.boost, boost=True, path=args.path)
    if args.apply:
        rules = load_rules(args.path)
        if not rules:
            print(f"❌ 未解析到铁律条目：{args.path}")
            return 2
        return apply(rules, date.today(), args.path)

    rules = load_rules(args.path)
    if not rules:
        print(f"❌ 未解析到铁律条目：{args.path}")
        return 2
    todo = report(rules, date.today(), args.json)
    if todo and not args.apply and not args.json:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
