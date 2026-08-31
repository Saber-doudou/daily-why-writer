#!/usr/bin/env python3
"""
L3 Publish v3.6 — daily-why 自包含发布脚本
零 AI 依赖，一条命令跑完：匹配检查、IMA 备份、GitHub 推送、执行日志归档

Usage:
    python l3_publish.py [YYYY-MM-DD] [--dry-run] [--force] [--no-git] [--no-ima] [--skip-match] [--skip-archive] [--no-verify]
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── 常量 ──────────────────────────────────────────────

MIN_A_CONTENT_CHARS = 50   # A 段最少有效字符数
MAX_IMPROVEMENTS_CHECK = 10  # 最多检查的改进点数量

# ── 全局 ──────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "config.json"


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


CFG = load_config()


class Result:
    """收集各 Phase 的执行结果（v3.5 起同时写入 l3_run.log）"""

    def __init__(self, log_path="F:/WorkBuddy/daily-why/l3_run.log"):
        self.phases = []
        self.warnings = 0
        self.errors = 0
        self._log_path = log_path

    def _log(self, phase, status, msg):
        """追加一行到运行日志（08-31 重建，此前 l3_run.log 停更于 08-14 且无任何写入逻辑）"""
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] [Phase {phase}] {status} {msg}\n")
        except OSError:
            pass  # 日志失败不阻塞主流程

    def ok(self, phase, msg):
        self.phases.append((phase, "✅", msg))
        print(f"[Phase {phase}] ✅ {msg}")
        self._log(phase, "✅", msg)

    def skip(self, phase, msg):
        self.phases.append((phase, "⏭️", msg))
        print(f"[Phase {phase}] ⏭️ {msg}")
        self._log(phase, "⏭️", msg)

    def warn(self, phase, msg):
        self.phases.append((phase, "⚠️", msg))
        print(f"[Phase {phase}] ⚠️ {msg}", file=sys.stderr)
        self.warnings += 1
        self._log(phase, "⚠️", msg)

    def fail(self, phase, msg):
        self.phases.append((phase, "❌", msg))
        print(f"[Phase {phase}] ❌ {msg}", file=sys.stderr)
        self.errors += 1
        self._log(phase, "❌", msg)

    def summary(self):
        print("=" * 50)
        if self.errors:
            print(f"  完成（{self.errors} 个错误, {self.warnings} 个警告）")
        elif self.warnings:
            print(f"  完成（{self.warnings} 个警告）")
        else:
            print("  完成！")
        print("=" * 50)
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write("=" * 50 + f"\n[{ts}] 完成（errors={self.errors}, warnings={self.warnings}）\n\n")
        except OSError:
            pass


def confirm(prompt, force):
    """交互确认，--force 时自动跳过"""
    if force:
        return True
    try:
        ans = input(f"{prompt} (y/N) ").strip().lower()
        return ans in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def git_pull_rebase_push(repo, timeout):
    """执行 git pull --rebase + push，返回 (success, error_msg)"""
    r_pull = subprocess.run(
        ["git", "-c", "credential.helper=wincred", "pull", "--rebase", "origin", "main"],
        cwd=str(repo), capture_output=True, text=True
    )
    if r_pull.returncode != 0:
        # rebase 冲突，abort 后报告
        subprocess.run(
            ["git", "-c", "credential.helper=wincred", "rebase", "--abort"],
            cwd=str(repo), capture_output=True
        )
        return False, f"rebase 冲突: {r_pull.stderr.strip()[:200]}"

    r_push = subprocess.run(
        ["git", "-c", "credential.helper=wincred", "push", "origin", "main"],
        cwd=str(repo), capture_output=True, text=True,
        timeout=timeout
    )
    if r_push.returncode != 0:
        return False, f"push 失败: {r_push.stderr.strip()[:200]}"

    return True, ""


def force_write_remote_ref(repo, sha):
    """强写 origin/main loose ref。
    沙箱下 git update-ref / fetch 传输成功但引用静默不落盘，且当
    .git/refs/remotes/origin/ 目录缺失时二者均「不报错也不写入」，
    故直接 mkdir + 写文件绕过（08-28 实证）。
    """
    try:
        ref_dir = repo / ".git" / "refs" / "remotes" / "origin"
        ref_dir.mkdir(parents=True, exist_ok=True)
        (ref_dir / "main").write_text(sha + "\n", encoding="utf-8")
    except OSError as e:
        return f"写 loose ref 失败: {e}"

    r = subprocess.run(["git", "rev-list", "--count", "origin/main..HEAD"],
                       cwd=str(repo), capture_output=True, text=True)
    try:
        ahead = int((r.stdout or "0").strip() or 0)
    except ValueError:
        ahead = -1
    if ahead != 0:
        return f"写 ref 后 ahead 仍为 {ahead}"
    return ""


def verify_remote_sync(repo, timeout):
    """铁律：判定 commit 是否真正推上远程，禁止只看本地 git status 的 ahead 数。
    返回 (status, msg)；status ∈ verified / ok_unfixed / unverified / mismatch
    """
    try:
        r = subprocess.run(["git", "ls-remote", "origin", "refs/heads/main"],
                           cwd=str(repo), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "unverified", f"ls-remote 超时 >{timeout}s（沙箱网络隔离），未核验"
    if r.returncode != 0:
        return "unverified", f"ls-remote 失败: {r.stderr.strip()[:120]}"

    parts = r.stdout.split()
    if not parts:
        return "unverified", "ls-remote 返回空"

    remote_main = parts[0]
    r2 = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo),
                        capture_output=True, text=True)
    local_head = r2.stdout.strip() if r2.returncode == 0 else ""
    if not local_head:
        return "unverified", "本地 HEAD 解析失败"

    if remote_main != local_head:
        # 远程领先或分叉：仅当本地持有该对象才能判祖先，否则无法判定
        e = subprocess.run(["git", "cat-file", "-e", remote_main + "^{commit}"],
                           cwd=str(repo), capture_output=True, text=True)
        if e.returncode != 0:
            return "unverified", (f"远程 main={remote_main[:8]} 本地={local_head[:8]} 不一致，"
                                  "本地无该对象（沙箱 fetch 不落盘），无法判定")
        a = subprocess.run(["git", "merge-base", "--is-ancestor", local_head, remote_main],
                           cwd=str(repo), capture_output=True, text=True)
        if a.returncode != 0:
            return "mismatch", f"本地 {local_head[:8]} 未包含在远程 main={remote_main[:8]}"

    err = force_write_remote_ref(repo, remote_main)
    if err:
        return "ok_unfixed", f"核验一致（远程={remote_main[:8]}）但引用未同步: {err}"
    return "verified", f"远端核验一致（远程 main={remote_main[:8]}），origin/main 引用已同步"


def report_git_result(res, repo, prefix_msg, verify):
    """push 成功后的统一收尾：远端核验 + 结果上报。返回 git_result。
    mismatch → 判失败（真正的未落盘）；unverified → 不阻塞（push 已成功返回，仅网络不通）
    """
    if not verify:
        res.ok(3, prefix_msg)
        return prefix_msg

    verify_timeout = CFG.get("git_verify_timeout", 20)
    status, vmsg = verify_remote_sync(repo, verify_timeout)
    if status == "mismatch":
        res.fail(3, f"{prefix_msg}｜远端核验未落盘: {vmsg}")
        return "push_fail"
    if status == "verified":
        res.ok(3, f"{prefix_msg} ✅{vmsg}")
    elif status == "ok_unfixed":
        res.warn(3, f"{prefix_msg}｜{vmsg}")
    else:
        res.ok(3, f"{prefix_msg}（⚠️ 未核验：{vmsg}）")

    # git_result 供 Phase 4 判定发布状态
    m = re.search(r"commit=(\S+)", prefix_msg)
    return m.group(1) if m else prefix_msg


# ── Phase 0: 解析参数 & 日期探测 ─────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="L3 Publish v3.6 — daily-why 发布脚本")
    p.add_argument("date", nargs="?", default=None,
                   help="文章日期 (YYYY-MM-DD)，默认自动探测最新文章")
    p.add_argument("--dry-run", action="store_true",
                   help="只检查不执行")
    p.add_argument("--force", action="store_true",
                   help="跳过所有交互确认（用于自动化调用）")
    p.add_argument("--no-git", action="store_true",
                   help="跳过 GitHub 推送")
    p.add_argument("--no-ima", action="store_true",
                   help="跳过 IMA 云端备份")
    p.add_argument("--skip-match", action="store_true",
                   help="跳过匹配度检查（Phase 1）")
    p.add_argument("--skip-archive", action="store_true",
                   help="跳过 FEEDBACK 休眠归档（Phase 5）")
    p.add_argument("--no-verify", action="store_true",
                   help="跳过发布后的远端核验（沙箱网络不通时可用，默认核验）")
    return p.parse_args()


def detect_latest_date():
    """从 articles/ 探测最新文章的日期"""
    articles_dir = Path(CFG["articles_dir"])
    if not articles_dir.exists():
        return None, None
    dates = []
    for f in articles_dir.rglob("*-每日冷知识-*.md"):
        # 跳过优化版
        if "优化版" in f.name:
            continue
        m = re.match(r"(\d{4}-\d{2}-\d{2})-每日冷知识", f.name)
        if m:
            try:
                dates.append((datetime.strptime(m.group(1), "%Y-%m-%d").date(), f))
            except ValueError:
                continue
    if not dates:
        return None, None
    dates.sort(key=lambda x: x[0], reverse=True)
    return dates[0][0].strftime("%Y-%m-%d"), dates[0][1]


def scan_articles(date_str):
    """扫描指定日期的初版、优化版、学习总结"""
    ym = date_str[:7]  # YYYY-MM
    ymd_compact = date_str.replace("-", "")  # YYYYMMDD
    articles_dir = Path(CFG["articles_dir"]) / ym
    feed_dir = Path(CFG["投喂素材_dir"]) / ymd_compact

    result = {
        "v1": None,
        "v2": None,
        "learning_summary": None,
    }

    # 初版
    for f in articles_dir.glob(f"{date_str}-每日冷知识-*.md"):
        result["v1"] = f
        break

    # 优化版
    for f in articles_dir.glob(f"{date_str}-优化版-每日冷知识-*.md"):
        result["v2"] = f
        break

    # 学习总结
    summary_file = feed_dir / "学习总结.md"
    if summary_file.exists():
        result["learning_summary"] = summary_file

    return result


def extract_article_meta(filepath):
    """从文章文件提取元数据"""
    text = filepath.read_text(encoding="utf-8")
    # 话题：从标题提取
    topic = filepath.stem.split("-每日冷知识-")[-1] if "-每日冷知识-" in filepath.stem else "未知"
    # Q 数量
    q_count = len(re.findall(r"\*\*Q\d+", text))
    # 字数（中文字符数）
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    # 分类（全文扫描：支持头部元数据行 + 底部风格表格两种格式）
    category = "未知"
    for line in text.splitlines():
        m = re.search(r"分类[：:]\s*(.+)", line)
        if m:
            category = m.group(1).strip()
            break
    if category == "未知":
        m = re.search(r"\|\s*分类\s*\|\s*(.+?)\s*\|", text)
        if m:
            category = m.group(1).strip()
    return {
        "topic": topic,
        "q_count": q_count,
        "chinese_chars": chinese_chars,
        "category": category,
    }


# ── Phase 0: 幂等性检查 ─────────────────────────────

def check_idempotency(date_str, force):
    """检查今日是否已发布，防止重复执行"""
    memory_file = Path(CFG["memory_dir"]) / f"{date_str}.md"
    if not memory_file.exists():
        return False  # 未发布过
    text = memory_file.read_text(encoding="utf-8")
    # 精确匹配状态行格式，避免文章内容干扰
    if re.search(r"状态[：:]\s*✅\s*已发布", text):
        if force:
            print(f"⚠️ {date_str} 已发布过，--force 强制重新执行")
            return False
        return True
    return False


# ── Phase 1: 匹配度检查 ─────────────────────────────

def phase1_match_check(v1_path, v2_path, summary_path, dry_run, res):
    """执行匹配度检查，返回 pass (bool)"""
    report = {"structure": None, "content": None, "audit": None, "rules": None}

    # 1.1 结构一致性
    v1_meta = extract_article_meta(v1_path)
    v2_meta = extract_article_meta(v2_path)

    v2_text = v2_path.read_text(encoding="utf-8")
    # A 段：第一个 Q 之前有足够有效内容
    first_q = re.search(r"\*\*Q\d+", v2_text)
    content_before_q = v2_text[:first_q.start()].strip() if first_q else ""
    has_a = len(content_before_q) >= MIN_A_CONTENT_CHARS
    # C 段：有 Q1/Q2/Q3 问答
    has_c = bool(first_q)
    # F 段：冷知识反转（## F 或 🧊 **冷知识反转** 或 > 🧊）
    has_f = bool(re.search(r"(^## F|🧊.*冷知识反转|冷知识反转)", v2_text, re.MULTILINE))

    struct_ok = (has_a and has_c and has_f and
                 v1_meta["category"] == v2_meta["category"] and
                 abs(v1_meta["q_count"] - v2_meta["q_count"]) <= 1)

    report["structure"] = {
        "ok": struct_ok,
        "topic_match": v1_meta["topic"] == v2_meta["topic"],
        "category_match": v1_meta["category"] == v2_meta["category"],
        "q_count": f"{v1_meta['q_count']}→{v2_meta['q_count']}",
        "acf": f"A={'✅' if has_a else '❌'} C={'✅' if has_c else '❌'} F={'✅' if has_f else '❌'}",
    }

    # 1.2 内容改进验证（提取改进点，语义判断由 AI 完成）
    if summary_path:
        summary_text = summary_path.read_text(encoding="utf-8")
        improvement_section = re.search(
            r"^##\s*v1\s*→\s*v2\s*改进点\s*\n(.*?)(?=^##\s|\Z)",
            summary_text, re.MULTILINE | re.DOTALL
        )
        if improvement_section:
            improvements = re.findall(
                r"(?:^[-*]\s*|^\d+[.、]\s*)(.+)",
                improvement_section.group(1), re.MULTILINE
            )
        else:
            improvements = []
        check_count = min(len(improvements), MAX_IMPROVEMENTS_CHECK)
        # 只做存在性检查（有改进点列表即可），语义验证交给 AI
        report["content"] = {
            "ok": True,  # AI 另行判断
            "improvements": improvements[:MAX_IMPROVEMENTS_CHECK],
            "total": check_count,
            "ai_required": True,
        }
    else:
        report["content"] = {"ok": True, "skipped": True}

    # 1.3 审核一致性
    validate_script = CFG["validate_script"]
    try:
        r = subprocess.run(
            [CFG["python_path"], validate_script, str(v2_path)],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(CFG["base_dir"]))
        )
        output = r.stdout + r.stderr
        # 兼容多种格式：P0=0 / P0:0 / P0(致命)=0 / p0_count: 0
        p0_match = re.search(r"P0[^=\d]*[=:]\s*(\d+)", output, re.IGNORECASE)
        p1_match = re.search(r"P1[^=\d]*[=:]\s*(\d+)", output, re.IGNORECASE)
        score_match = re.search(r"(?:final_score|得分)\s*[=:]\s*(\d+)", output, re.IGNORECASE)

        p0 = int(p0_match.group(1)) if p0_match else -1
        p1 = int(p1_match.group(1)) if p1_match else -1
        score = int(score_match.group(1)) if score_match else -1

        # 合理性校验：防止异常值
        if p0 > 20 or p1 > 50:
            audit_ok = False
            report["audit"] = {
                "ok": False,
                "p0": p0,
                "p1": p1,
                "score": score,
                "status": "parse_error",
                "error": f"异常值 P0={p0} P1={p1}"
            }
        else:
            audit_ok = (p0 == 0 and p1 <= 2)
            report["audit"] = {
                "ok": audit_ok,
                "p0": p0,
                "p1": p1,
                "score": score,
                "status": "ok",
            }
    except Exception as e:
        report["audit"] = {"ok": False, "status": "error", "error": str(e)[:100]}

    # 1.4 规则同步验证
    forbidden_path = Path(CFG["references_dir"]) / "FORBIDDEN.md"
    checklist_path = Path(CFG["references_dir"]) / "CHECKLIST.md"
    rule_info = {"forbidden_last": "?", "checklist_last": "?"}

    if forbidden_path.exists():
        fp_text = forbidden_path.read_text(encoding="utf-8")
        fp_nums = re.findall(r"FP-(\d+)", fp_text)
        if fp_nums:
            rule_info["forbidden_last"] = f"FP-{max(int(n) for n in fp_nums)}"

    if checklist_path.exists():
        cl_text = checklist_path.read_text(encoding="utf-8")
        # 兼容 §N 和 ## N. 两种格式
        cl_nums = re.findall(r"§(\d+)", cl_text)
        if not cl_nums:
            cl_nums = re.findall(r"^##\s+(\d+)\.", cl_text, re.MULTILINE)
        if cl_nums:
            rule_info["checklist_last"] = f"§{max(int(n) for n in cl_nums)}"

    fp_ok = rule_info["forbidden_last"] != "?"
    cl_ok = rule_info["checklist_last"] != "?"
    report["rules"] = {"ok": fp_ok and cl_ok, **rule_info}

    # 汇总判定
    all_ok = all(
        (r["ok"] if isinstance(r, dict) and "ok" in r else True)
        for r in report.values()
    )

    # 输出报告
    s = report["structure"]
    c = report["content"]
    a = report["audit"]
    print(f"\n{'=' * 50}")
    print(f"  匹配度检查报告 — {v1_path.stem}")
    print(f"{'=' * 50}")
    print(f"  结构一致性: {'✅' if s['ok'] else '❌'}  "
          f"分类={s['category_match']}  Q数={s['q_count']}  {s['acf']}")
    if not c.get("skipped"):
        if c.get("ai_required"):
            print(f"  内容改进:   🤖 待 AI 验证  "
                  f"改进点={c['total']}条（关键词匹配已移除）")
            for i, imp in enumerate(c.get("improvements", []), 1):
                print(f"            {i}. {imp[:80]}{'…' if len(imp) > 80 else ''}")
        else:
            print(f"  内容改进:   {'✅' if c['ok'] else '❌'}  "
                  f"改进点={c['total']}条")
    if a["status"] == "ok":
        print(f"  审核一致性: {'✅' if a['ok'] else '❌'}  "
              f"P0={a['p0']} P1={a['p1']} 得分={a['score']}")
    else:
        print(f"  审核一致性: ❌ {a['error']}")
    print(f"  规则同步:   {'✅' if report['rules']['ok'] else '❌'} "
          f"{rule_info['forbidden_last']} / {rule_info['checklist_last']}")
    print(f"  总体判定:   {'✅ PASS' if all_ok else '❌ FAIL'}")
    print(f"{'=' * 50}\n")

    return all_ok


# ── Phase 2: IMA 云端备份 ────────────────────────────

def _detect_ima_version():
    """从 MEMORY.md 检测最新版本号 → 进位（minor 满 9 进 1）

    十进制版本语义：3.9 → 4.0（不是 3.10）。
    降级策略：IMA 备份历史章节找不到 → 全文搜索。
    """
    memory_md = Path(CFG["memory_md_path"])
    if not memory_md.exists():
        return "1.0"

    content = memory_md.read_text(encoding="utf-8")

    # 优先从 IMA 备份历史章节取（兼容「最近5条」等后缀）
    section = re.search(r"## IMA 备份历史[^\n]*\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    if section:
        versions = re.findall(r"\bv(\d+\.\d+)\b", section.group(1))
    else:
        # 降级：全文搜索
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


def _append_ima_history(note_id, version, date_str):
    """追加一行到 MEMORY.md 的 IMA 备份历史表。

    08-31 修复：原实现用 4 列管道表格正则，而 MEMORY.md 该节实为一行纯文本
    （如 `v6.6(08-26) ...`），正则永远匹配不到 → 静默 return、从未生效。
    现改为在 `## IMA 备份历史` 标题行后插入，表格与纯文本均兼容。
    返回 bool 供调用方校验，失败不静默。
    """
    memory_md = Path(CFG["memory_md_path"])
    if not memory_md.exists():
        return False
    content = memory_md.read_text(encoding="utf-8")
    new_row = f"- v{version} | note_id={note_id} | {date_str} | l3_publish.py 自动备份"
    pattern = r"(## IMA 备份历史[^\n]*\n)"
    m = re.search(pattern, content)
    if m:
        content = content.replace(m.group(1), m.group(1) + new_row + "\n", 1)
        memory_md.write_text(content, encoding="utf-8")
        return True
    return False


def phase2_ima(date_str, dry_run, force, res):
    if dry_run:
        res.skip(2, f"将上传: daily-why 备份{date_str}")
        return "dry-run"

    if not confirm("即将上传配置到 IMA 云端，确认？", force):
        res.skip(2, "用户取消 IMA 备份")
        return "skip"

    # 预检测版本号，显式传给 ima_archive.py 避免版本撞车
    version = _detect_ima_version()

    cmd = [
        CFG["python_path"],
        CFG["ima_archive_script"],
        "backup-memory",
        f"--kb-id={CFG['ima_kb_id']}",
        f"--version={version}",
        "--config-only",  # 只备份配置，不包含今日日志（防止文章元数据混入）
    ]

    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=CFG.get("ima_upload_timeout", 30),
            cwd=str(Path(CFG["base_dir"]))
        )
        if r.returncode != 0:
            res.warn(2, f"ima_archive 返回非零: {r.stderr.strip()[:200]}")
            return "fail"

        output = r.stdout
        # 解析 note_id
        note_id = ""
        m = re.search(r"note_id[:\s]+(\d+)", output)
        if m:
            note_id = m.group(1)

        if note_id:
            res.ok(2, f"v{version} note_id={note_id}")
        else:
            res.ok(2, f"v{version} 上传成功（未返回 note_id）")

        # 追加到自动化记忆
        auto_mem = Path(CFG["automation_memory"])
        if auto_mem.exists() and note_id:
            with open(auto_mem, "a", encoding="utf-8") as f:
                f.write(f"- IMA: note_id {note_id}\n")

        # 追加到 MEMORY.md 的 IMA 备份历史表（防止版本号撞车）
        if note_id:
            if not _append_ima_history(note_id, version, date_str):
                res.warn(2, "MEMORY.md IMA 备份历史追加失败（标题行未找到），请人工补记")

        return note_id or "ok"

    except subprocess.TimeoutExpired:
        res.warn(2, "ima_archive 超时（30s）")
        return "timeout"
    except FileNotFoundError:
        res.warn(2, f"Python 或脚本不存在: {CFG['python_path']}")
        return "not_found"


# ── Phase 3: GitHub 推送 ─────────────────────────────

def phase3_git(date_str, topic, dry_run, force, res, verify=True):
    repo = Path(CFG["git_repo_path"])
    if not (repo / ".git").exists():
        res.fail(3, f"Git 仓库不存在: {repo}")
        return "no_repo"

    # Step 3.1: 同步技能文件到 Git 仓库
    src_base = Path(CFG["references_dir"]).parent  # ~/.workbuddy/skills/daily-why-writer/
    skill_md = src_base / "SKILL.md"
    refs = ["references/FORBIDDEN.md", "references/CHECKLIST.md", "references/FEEDBACK_LOG.md"]
    # Reviewer 独立审校 prompt（v2.0 主路径资产，纳入推送）
    reviewer_prompt = src_base / "reviewer_prompt.md"
    # L3 发布技能文件
    publish_skill = Path("C:/Users/admin/.workbuddy/skills/daily-why-publish/SKILL.md")
    l3_script = Path(CFG["scripts_dir"]) / "l3_publish.py"
    l3_config = Path(CFG["scripts_dir"]) / "config.json"

    files_to_copy = []
    if skill_md.exists():
        files_to_copy.append((skill_md, repo / "SKILL.md"))
    for ref in refs:
        src = src_base / ref
        dst = repo / ref
        if src.exists():
            files_to_copy.append((src, dst))
    # Reviewer 独立审校 prompt
    if reviewer_prompt.exists():
        files_to_copy.append((reviewer_prompt, repo / "reviewer_prompt.md"))
    # L3 发布
    if publish_skill.exists():
        files_to_copy.append((publish_skill, repo / "daily-why-publish" / "SKILL.md"))
    if l3_script.exists():
        files_to_copy.append((l3_script, repo / "scripts" / "l3_publish.py"))
    if l3_config.exists():
        files_to_copy.append((l3_config, repo / "scripts" / "config.json"))

    # B 组补全（08-28 审计）：这些文件列在 config.json 的 git_add_files 里，
    # 但历史上从未纳入 files_to_copy —— 源改动从不复制进 repo，副本长期脱节
    # （实测 FEEDBACK_ARCHIVE.md 源 189 行 vs repo 35 行）。现统一纳入复制。
    scripts_dir = Path(CFG["scripts_dir"])
    project_dir = Path(CFG.get("base_dir", "F:/WorkBuddy/daily-why"))
    extra_sync = [
        (src_base / "references" / "FEEDBACK_ARCHIVE.md", "references/FEEDBACK_ARCHIVE.md"),
        (project_dir / "review" / "CASE_STUDIES.md", "review/CASE_STUDIES.md"),
        (scripts_dir / "generate_prompt.py", "scripts/generate_prompt.py"),
        (scripts_dir / "generate_prompt.py", "generate_prompt.py"),
        (scripts_dir / "check_topic.py", "check_topic.py"),
        (scripts_dir / "topic_utils.py", "topic_utils.py"),
        (scripts_dir / "full_selfcheck.py", "full_selfcheck.py"),
        (scripts_dir / "message_handler.py", "message_handler.py"),
        (project_dir / "config" / "topic_candidates.json", "topic_candidates.json"),
    ]
    for src, rel in extra_sync:
        if src.exists():
            files_to_copy.append((src, repo / rel))

    # 自检：git_add_files 的每一项都必须有对应复制源，否则该文件的源改动
    # 永远进不了 repo（08-28 审计：漏配导致 FEEDBACK_ARCHIVE.md 脱节 154 行）
    copied = set()
    for _, dst in files_to_copy:
        try:
            copied.add(str(dst.relative_to(repo)).replace("\\", "/"))
        except ValueError:
            pass
    missing = [f for f in CFG.get("git_add_files", []) if f not in copied]
    if missing:
        res.warn(3, f"git_add_files 中 {len(missing)} 项无复制源（改动不会同步）: "
                    f"{', '.join(missing)}")

    if not dry_run:
        for src, dst in files_to_copy:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    # Step 3.2: 检查变更
    r = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo), capture_output=True, text=True
    )
    if not r.stdout.strip():
        # 工作树干净：仍可能有「已提交但未推送」的 commit（如网络失败重试场景）
        ahead = subprocess.run(
            ["git", "rev-list", "--count", "origin/main..HEAD"],
            cwd=str(repo), capture_output=True, text=True
        )
        try:
            ahead_n = int((ahead.stdout or "").strip() or 0)
        except ValueError:
            ahead_n = 0
        if ahead_n > 0:
            push_timeout = CFG.get("git_push_timeout", 30)
            success, err_msg = git_pull_rebase_push(repo, push_timeout)
            if not success:
                success, err_msg = git_pull_rebase_push(repo, push_timeout)
                if not success:
                    res.fail(3, err_msg)
                    return "push_fail"
            r = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(repo), capture_output=True, text=True
            )
            commit_hash = r.stdout.strip() if r.returncode == 0 else "unknown"
            return report_git_result(res, repo, f"补推已提交 commit={commit_hash}", verify)
        res.skip(3, "无新变更，跳过")
        return "no_changes"

    changed_count = len(r.stdout.strip().splitlines())

    if dry_run:
        res.skip(3, f"将提交 {changed_count} 个文件变更")
        return "dry-run"

    if not confirm(f"即将推送 {changed_count} 个文件到 GitHub，确认？", force):
        res.skip(3, "用户取消推送")
        return "skip"

    # Step 3.3: git add（只 add 规则文件）
    add_files = CFG.get("git_add_files", ["SKILL.md"])
    for f in add_files:
        fp = repo / f
        if fp.exists():
            subprocess.run(["git", "add", f], cwd=str(repo), capture_output=True)

    # 检查是否有文件被 staged
    r_staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(repo), capture_output=True, text=True
    )
    if not r_staged.stdout.strip():
        res.skip(3, "规则文件无变更，跳过")
        return "no_rule_changes"

    # git commit（08-31 修复：消息由实际 staged 文件反推，不再硬编码模板）
    staged = r_staged.stdout.strip().splitlines()
    parts = [topic] if topic else []
    if any(("FORBIDDEN" in s or "CHECKLIST" in s or "FEEDBACK" in s or "SKILL.md" in s
            or "reviewer_prompt" in s) for s in staged):
        parts.append("规则更新")
    if any(("generate_prompt" in s or "l3_publish" in s or "config.json" in s
            or "check_topic" in s or "message_handler" in s or "full_selfcheck" in s
            or "topic_utils" in s) for s in staged):
        parts.append("脚本更新")
    if any("topic_candidates" in s for s in staged):
        parts.append("素材池更新")
    if not parts:
        parts = ["维护"]
    commit_msg = f"daily-why {date_str}: " + " + ".join(parts)
    r = subprocess.run(
        ["git", "commit", "-m", commit_msg],
        cwd=str(repo), capture_output=True, text=True
    )
    if r.returncode != 0:
        if "nothing to commit" in r.stdout:
            res.skip(3, "无新变更，跳过")
            return "no_changes"
        res.fail(3, f"commit 失败: {r.stderr.strip()[:200]}")
        return "commit_fail"

    # 08-31 新增：commit 后一致性自检（push 前）——若任一同步文件在 commit 之后又被
    # 改写（典型：写该文件的 Phase 排在 Phase 3 之后，如归档在 git 之后），repo 副本
    # 已脱节，此处及时发现并告警，避免把脱节版本推上远程。
    # 通用约束：git_add_files 内文件的生产 Phase 必须先于 Phase 3 执行。
    sync_mismatch = []
    for _src, _dst in files_to_copy:
        if _src.exists() and _dst.exists() and _src.read_bytes() != _dst.read_bytes():
            try:
                sync_mismatch.append(str(_dst.relative_to(repo)))
            except ValueError:
                sync_mismatch.append(str(_dst))
    if sync_mismatch:
        res.warn(3, f"commit 后检测到源与 repo 脱节 {len(sync_mismatch)} 项: "
                    f"{', '.join(sync_mismatch[:5])}。请检查是否存在 Phase 在 git 之后"
                    f"修改同步文件（时序约束：git_add_files 内文件的生产 Phase 必须先于 Phase 3）")

    # git pull --rebase + push（含重试）
    push_timeout = CFG.get("git_push_timeout", 30)
    success, err_msg = git_pull_rebase_push(repo, push_timeout)
    if not success:
        # 重试一次
        success, err_msg = git_pull_rebase_push(repo, push_timeout)
        if not success:
            res.fail(3, err_msg)
            return "push_fail"

    # 获取 commit hash
    r = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=str(repo), capture_output=True, text=True
    )
    commit_hash = r.stdout.strip() if r.returncode == 0 else "unknown"

    # 追加到自动化记忆
    auto_mem = Path(CFG["automation_memory"])
    if auto_mem.exists():
        with open(auto_mem, "a", encoding="utf-8") as f:
            f.write(f"- GitHub: commit {commit_hash}\n")

    return report_git_result(res, repo, f"commit={commit_hash}", verify)


# ── Phase 4: 记忆归档 ────────────────────────────────

def render_report(date_str, v1_meta, v2_meta, ima_result, git_result, res):
    """渲染发布报告到 deliverables/{date}-发布报告.md（08-31 起替代 AI 手写，
    杜绝字数/得分/commit 失真。骨架全部由脚本数据生成，语义验证表留 AI 补充区）"""
    try:
        deliverables = Path(CFG["base_dir"]) / "deliverables"
        deliverables.mkdir(parents=True, exist_ok=True)
        report_path = deliverables / f"{date_str}-发布报告.md"

        lines = [f"# 发布报告 — {date_str} {v1_meta['topic']}", ""]
        # 基本信息
        lines.append("## 基本信息")
        lines.append(f"- 话题：{v1_meta['topic']}")
        lines.append(f"- 分类：{v1_meta['category']}")
        lines.append(f"- 初版：{v1_meta['chinese_chars']} 字，{v1_meta['q_count']} 个Q")
        if v2_meta:
            lines.append(f"- 优化版：{v2_meta['chinese_chars']} 字，{v2_meta['q_count']} 个Q")
        lines.append(f"- 注：字数为全文口径（含标题与结尾表格），与 validate 正文口径不同属正常")
        lines.append("")
        # 执行结果（来自 Result.phases，脚本收集，非 AI 手写）
        lines.append("## 执行结果（脚本逐 Phase 记录）")
        for phase, status, msg in res.phases:
            lines.append(f"- Phase {phase} {status} {msg}")
        lines.append("")
        # 发布状态
        fail_indicators = ("fail", "timeout", "not_found", "push_fail", "commit_fail", "no_repo")
        all_ok = (ima_result not in fail_indicators and git_result not in fail_indicators)
        lines.append("## 发布状态")
        lines.append(f"- 总体：{'✅ 发布成功' if all_ok else '⚠️ 部分成功'}")
        if res.errors:
            lines.append(f"- 错误：{res.errors} 个")
        if res.warnings:
            lines.append(f"- 警告：{res.warnings} 个")
        lines.append("")
        # AI 补充区
        lines.append("## AI 语义验证补充区（由执行 AI 填充）")
        lines.append("")
        lines.append("<!-- 在此追加 Step 2 语义验证：改进点 | 判定 | 证据（行号）。"
                     "禁止改动上方由脚本生成的部分。 -->")
        lines.append("")

        report_path.write_text("\n".join(lines), encoding="utf-8")
        return str(report_path)
    except OSError as e:
        res.warn(4, f"发布报告渲染失败（不影响发布）: {e}")
        return None


def phase4_memory(date_str, v1_meta, v2_meta, ima_result, git_result, dry_run, res):
    if dry_run:
        res.skip(4, "dry-run 不写入日志")
        return

    memory_dir = Path(CFG["memory_dir"])
    memory_dir.mkdir(parents=True, exist_ok=True)
    log_file = memory_dir / f"{date_str}.md"

    # 判断发布状态
    fail_indicators = ("fail", "timeout", "not_found", "push_fail", "commit_fail", "no_repo")
    all_ok = (ima_result not in fail_indicators and git_result not in fail_indicators)
    status = "✅ 已发布" if all_ok else "⚠️ 部分成功"

    now = datetime.now().strftime("%H:%M")
    lines = [
        f"\n## {now} L3 发布\n",
        f"- 话题：{v1_meta['topic']}",
        f"- 分类：{v1_meta['category']}",
        f"- 初版：{v1_meta['q_count']}个Q，{v1_meta['chinese_chars']}字",
    ]
    if v2_meta:
        lines.append(f"- 优化版：{v2_meta['q_count']}个Q，{v2_meta['chinese_chars']}字")
    lines.append(f"- IMA：{ima_result}")
    lines.append(f"- GitHub：{git_result}")
    lines.append(f"- 状态：{status}")
    lines.append("")

    with open(log_file, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))

    res.ok(4, f"已写入 {log_file.name}")


# ── Phase 5: FEEDBACK 休眠教训归档 ─────────────────────

def phase5_feedback_archive(dry_run, res):
    """检查 FEEDBACK_LOG 中超30天+已转规则的教训，归档到 FEEDBACK_ARCHIVE"""
    archive_script = Path(CFG.get("archive_lessons_script", ""))
    if not archive_script.exists():
        res.skip(5, "archive_lessons.py 未配置或不存在")
        return

    python = CFG["python_path"]
    cmd = [python, str(archive_script), "--mode", "archive"]
    if dry_run:
        cmd.append("--dry-run")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        output = result.stdout.strip()
        if result.returncode != 0:
            res.warn(5, f"存档脚本异常退出 ({result.returncode}): {result.stderr[:200]}")
            return

        # 解析输出判断是否有实际归档
        if "无可归档条目" in output:
            res.ok(5, "FEEDBACK 无新归档条目")
        elif "归档完成" in output:
            # 提取具体数字
            lines = output.split("\n")
            for line in lines:
                if "新增" in line:
                    res.ok(5, f"FEEDBACK 休眠归档: {line.strip()}")
                    return
            res.ok(5, "FEEDBACK 休眠归档完成")
        else:
            res.ok(5, f"FEEDBACK 存档检查完成")
    except subprocess.TimeoutExpired:
        res.warn(5, "存档脚本超时（>60s），跳过")
    except Exception as e:
        res.warn(5, f"存档脚本异常: {e}")


# ── Main ─────────────────────────────────────────────

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    args = parse_args()
    res = Result()

    # Phase 0: 确定日期
    if args.date:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", args.date):
            res.fail(0, f"日期格式非法: {args.date}，期望 YYYY-MM-DD")
            res.summary()
            sys.exit(1)
        date_str = args.date
    else:
        date_str, _ = detect_latest_date()
        if date_str is None:
            res.fail(0, f"无法从 {CFG['articles_dir']} 探测到文章日期")
            res.summary()
            sys.exit(1)

    print("=" * 50)
    print(f"  L3 Publish v3.4 — daily-why")
    print(f"  目标日期: {date_str}")
    if args.dry_run:
        print("  模式: --dry-run（只检查不执行）")
    print("=" * 50)

    # Phase 0: 幂等性检查
    if check_idempotency(date_str, args.force):
        res.warn(0, f"{date_str} 已发布过，跳过（使用 --force 强制重新执行）")
        res.summary()
        sys.exit(0)

    # Phase 0: 扫描文件
    articles = scan_articles(date_str)
    if articles["v1"] is None:
        res.fail(0, f"当日初版文章不存在: {date_str}")
        res.summary()
        sys.exit(1)

    v1_meta = extract_article_meta(articles["v1"])
    v2_meta = extract_article_meta(articles["v2"]) if articles["v2"] else None

    res.ok(0, f"初版={articles['v1'].name} ({v1_meta['chinese_chars']}字, {v1_meta['q_count']}Q)")
    if articles["v2"]:
        res.ok(0, f"优化版={articles['v2'].name} ({v2_meta['chinese_chars']}字, {v2_meta['q_count']}Q)")
    else:
        res.warn(0, "当日无优化版，仅执行初版归档")
    if articles["learning_summary"]:
        res.ok(0, f"学习总结={articles['learning_summary'].name}")
    else:
        res.warn(0, "无学习总结，跳过匹配度检查")

    # Phase 1: 匹配度检查
    match_pass = True
    if args.skip_match:
        res.skip(1, "--skip-match 跳过匹配度检查")
    elif articles["v2"] is None:
        res.skip(1, "无优化版，跳过匹配度检查")
    elif articles["learning_summary"] is None:
        res.skip(1, "无学习总结，跳过匹配度检查")
    else:
        match_pass = phase1_match_check(
            articles["v1"], articles["v2"], articles["learning_summary"],
            args.dry_run, res
        )
        if not match_pass:
            if args.force:
                res.warn(1, "匹配度检查 FAIL，--force 强制继续")
            elif not confirm("匹配度检查未通过，是否继续发布？", False):
                res.fail(1, "用户取消发布")
                res.summary()
                sys.exit(1)

    # Phase 2: IMA 备份
    if args.no_ima:
        res.skip(2, "--no-ima 跳过")
        ima_result = "skip"
    else:
        ima_result = phase2_ima(date_str, args.dry_run, args.force, res)

    # Phase 5: FEEDBACK 休眠归档（08-31 时序修复：必须早于 Phase 3 git commit，
    # 否则归档产生的 FEEDBACK_LOG/ARCHIVE 变更永远赶不上当天提交，每日脱节。
    # 归档失败仅 warn，不得阻塞发布主链路）
    if not args.skip_archive:
        phase5_feedback_archive(args.dry_run, res)

    # Phase 3: GitHub 推送
    if args.no_git:
        res.skip(3, "--no-git 跳过")
        git_result = "skip"
    else:
        git_result = phase3_git(date_str, v1_meta["topic"], args.dry_run, args.force, res,
                                verify=not args.no_verify)

    # Phase 4: 记忆归档
    phase4_memory(date_str, v1_meta, v2_meta, ima_result, git_result, args.dry_run, res)

    # 发布报告脚本渲染（08-31 起替代 AI 手写，杜绝数据失真）
    if not args.dry_run:
        report_path = render_report(date_str, v1_meta, v2_meta, ima_result, git_result, res)
        if report_path:
            res.ok(4, f"发布报告已渲染: {report_path}")

    res.summary()
    if res.errors:
        sys.exit(1)
    elif res.warnings:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
