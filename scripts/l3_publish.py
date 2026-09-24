#!/usr/bin/env python3
"""
L3 Publish v3.24 — daily-why 自包含发布脚本
零 AI 依赖，一条命令跑完：匹配检查、IMA 备份、GitHub 推送、执行日志归档

Usage:
    python l3_publish.py [YYYY-MM-DD] [--dry-run] [--force] [--no-git] [--no-ima] [--skip-match] [--skip-archive] [--no-verify] [--retry]
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import os
from datetime import datetime
from pathlib import Path

# ── 常量 ──────────────────────────────────────────────

VERSION = "v3.23"              # 09-17 v3.23：① 修复 #58——改进点提取器两处断裂，且是同一防线第 2 次复发（v3.9 记「已根治」、v3.21 记「已修好」均失准，根因是回归样本全为同一格式=采样偏差）。闸门①「标题锚点」原要求关键词紧跟「## +可选序号」，09-17 标题 `## 一、四 AI 核心差距与采纳/拒绝决策`（关键词在中部）零命中，现改为「标题任意位置含关键词即可」并把「改写要点」纳入关键词；闸门②「章节选取」原用 re.search 只取首个命中章节，撞上「核心差距」表格章节（8 行表格 0 列表项）即空手而归、错过后面真正的改写要点列表，现改 re.finditer 遍历全部命中章节取首个非空列表；闸门③新增最高优先「契约锚点」模式（纯 `## 改进点`，L2 SKILL v3.4 强制），在生产侧立契约，终结「L2 自由命名 vs L3 硬正则」的格式漂移（历史第 5 次分叉：→/到/三、采纳清单/v2 → v3 改进点/一、四 AI 核心差距），依据 EXP-003 指令文件法则 + EXP-004 约束优于指令。② 新增 #58 兜底——`--verify-report` 子模式机械校验发布报告 AI 补充区（判 FAIL 的报告必须声明人工补验且 ≥3 行判定表格，否则 exit 1），把「记得人工补验」从人肉防线变成可校验事实（EXP-014）。③ 修复 #59——`scripts/config.json` 因含 IMA KB ID 被 repo .gitignore 有意忽略却仍留在 git_add_files + 复制清单，git add 被拒且 capture_output=True 吞掉返回码 → 静默失败；双向自检只查「有无复制源」、反向灰区算 tracked-whitelist（未跟踪=隐身），两头都不报 → 报「白名单全覆盖」假绿。现从两份清单移除，并对 git add 逐项回读校验（被拒/未跟踪即 warn 点名）。09-16 v3.22：① 修复 #57a——报告 checksum 校验口径与写入口径差 1 个换行（写入侧 script_zone = join(lines) 不含 checksum 行前分隔换行，校验侧 text[:cut] 却含），导致每次渲染 md5 必不等、恒报「脚本区已被手工改动」并全量覆盖（09-15 报告实测 recorded 与 head[:-1] 精确相等、与 head 不等；与版本号是否变化无关，AI 补充区丢失是必然而非偶发）；现抽公共指纹函数 _script_zone_digest 供两侧共用（rstrip 归一化）+ 写入后回读自校验；② 修复 #57b——render_report 改为只重写 checksum 标记之前的脚本区，标记之后的 AI 补充区无条件原样保留（业界经验：SilverModel User Code Blocks / cddl-codegen keep-marker 一致指出「工具无法反推自己上次的输出」，故弃用「检测篡改」改用「标记界定所有权」；EXP-004 约束优于指令）；③ 修复 #56——check_version_consistency 由单口径升级为 frontmatter/标题/末条 *Version: 三口径全比（此前 writer 日志区 v3.5、audit 脚注区 v1.6、publish frontmatter v3.20 三处漂移全部漏判，均为人工核对才发现；且原实现取首条 *Version: 而非末条）。09-16 v3.21：① 修复 #54——学习总结检索由固定名 学习总结.md 改为前缀 glob（学习总结*.md），多份命中取字典序首个并告警；L2 实际命名带话题后缀（学习总结-熊猫第六指.md），固定名零命中会让 Phase 1 匹配度检查整段被绕过（09-15 实测，靠 AI 人工补验兜住，EXP-004/EXP-014）；② 修复 #55——git_add_files 中 scripts/code_review_check.py 与 docs/code-review-standard.md（09-15 代码审查体系新增）补入 extra_sync G 组，消「无复制源」告警，源改动恢复同步进 repo。09-15 v3.20：话题提取跳空行对齐 check_topic（P3 审查 P1-3 双源漂移：首行为空行时旧实现返回 None → 去重 fail-open 放行，存在静默绕过窗口；Master 确认当轮修复）+ dedup_selftest R4 回归用例；09-15 v3.19：dedup 卡点默认反转 enforce（Silent Fail-Open 根治：判定明确=重复时默认硬拦 exit 1，DAILY_WHY_DEDUP_RELAX=1 显式豁免降软 warn，检测器自身故障 fail-open 保留；依据 v3.13 SKILL bash 前缀注入在 Windows 不生效的 EXP-014 实证，外部经验 Praesidia/readysolutions fail-closed 共识）+ check_topic 排除 _废弃 后缀并修复无#标题提取盲区（#51）+ prepare_topics full/compact 同源派生断言 + 新增 dedup_selftest.py 双向自检（入 extra_sync/git_add_files）；v3.18：灰区告警豁免清单落地（config.git_gray_exemptions 8 项=达尔文 09-04 实验一次性产物，Master 授权查证后决策；外部经验一致：实验产物不入同步通道；豁免走配置+留理由，EXP-004）；v3.17：沙箱网络隔离 push 失败处置固化（SKILL 边界条件表新增：commit 已生成 → 沙箱外 push + api.github.com 核验 remote sha → 补推结论写报告 AI 补充区）；v3.16：引用机械门禁（正文含引用且 quote_checks 空 → 硬阻断）；CHANGELOG 补记 v3.15；去重自匹配修复 v3.14；去重硬卡点 v3.13 补记机制落地（补 09-07/08/09 三波欠账 + L3 SKILL 加「重大改造必更新 CHANGELOG」步骤 + git_add_files 纳入 CHANGELOG.md 真进 GitHub）；顺带修 S1(topics_context 当日写入时序约定) / S2(date_str 缺失静默退化改 warn)；v3.14 去重卡点自匹配修复（check_topic --exclude-date）；v3.13 去重硬卡点接入 L3 + 09-08 记忆治理 v3 落地
MIN_A_CONTENT_CHARS = 50   # A 段最少有效字符数
MAX_IMPROVEMENTS_CHECK = 10  # 最多检查的改进点数量
# 09-17 v3.23（#58 兜底）：--verify-report 要求判 FAIL 的报告至少落盘这么多行人工补验判定
MIN_REPORT_VERIFY_ROWS = 3

# 发布报告「脚本生成区」结束标记（09-16 v3.22 新增，修复 #57）。
# 所有权边界：该标记之前的内容归脚本所有（每次渲染无条件重写），标记之后的内容
# 归 AI 所有（无条件原样保留）。标记里的指纹只用于「脚本区是否被人工改动」的告警，
# 不再作为覆盖范围的判定依据——依据 cddl-codegen 的结论：生成器无法反推自己上次
# 写了什么，因此「检测篡改」这条路本身不可靠，正确做法是「标记界定所有权」
# （SilverModel 的 User Code Blocks 是同一思路，checksum 与保留块是两套互补机制）。
CHECKSUM_MARK = "<!-- checksum:"

# 网络类错误关键字（09-01 修复：此前网络失败被误标为 rebase 冲突，误导排查方向）
NETWORK_ERROR_HINTS = (
    "unable to access",
    "could not connect",
    "failed to connect",
    "timed out",
    "connection timed out",
    "could not resolve host",
    "connection refused",
    "network is unreachable",
    "operation timed out",
)

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


def classify_git_error(stderr):
    """区分 git 错误类型：network / conflict / other（09-01 修复）。
    此前所有 pull 非零一律报「rebase 冲突」并执行 --abort，网络失败也被归入此桶。"""
    s = (stderr or "").lower()
    for hint in NETWORK_ERROR_HINTS:
        if hint in s:
            return "network", (stderr or "").strip()[:200]
    if "conflict" in s or "could not apply" in s or "could not rebase" in s:
        return "conflict", (stderr or "").strip()[:200]
    return "other", (stderr or "").strip()[:200]


def github_reachable(timeout=8):
    """探活 github.com（网络层连通性）。返回 True/False。"""
    try:
        r = subprocess.run(
            ["curl", "-s", "-o", "NUL", "-w", "%{http_code}",
             "--connect-timeout", str(timeout), "--max-time", str(timeout + 2),
             "https://github.com"],
            capture_output=True, text=True, timeout=timeout + 5
        )
        return r.returncode == 0 and r.stdout.strip() == "200"
    except (subprocess.TimeoutExpired, OSError):
        return False


def git_pull_rebase_push(repo, timeout, retries=3, backoff=(10, 30, 60)):
    """git pull --rebase + push，带网络探活与退避重试（09-01 增强）。
    返回 (success, error_msg, kind)；kind ∈ ok/network/conflict/other。
    - 网络失败：探活确认网络可达后按 backoff 退避重试 retries 次，均失败才报人工介入；
    - 真冲突：abort 后报告，不重试。
    """
    for attempt in range(retries + 1):
        if attempt > 0:
            if not github_reachable():
                return False, "网络失败（不可重试）：github.com 探活失败，请检查网络/VPN", "network"
            time.sleep(backoff[min(attempt - 1, len(backoff) - 1)])

        r_pull = subprocess.run(
            ["git", "-c", "credential.helper=wincred", "pull", "--rebase", "origin", "main"],
            cwd=str(repo), capture_output=True, text=True
        )
        if r_pull.returncode != 0:
            kind, err_msg = classify_git_error(r_pull.stderr)
            if kind == "network" and attempt < retries:
                continue  # 退避重试
            if kind == "network":
                return False, f"网络失败（已退避重试 {retries} 次仍不可达）: {err_msg}", "network"
            # 真冲突或其他：abort 后报告（仅冲突类执行 abort）
            subprocess.run(
                ["git", "-c", "credential.helper=wincred", "rebase", "--abort"],
                cwd=str(repo), capture_output=True
            )
            return False, f"rebase 冲突: {err_msg}", "conflict"
        break  # pull 成功

    r_push = subprocess.run(
        ["git", "-c", "credential.helper=wincred", "push", "origin", "main"],
        cwd=str(repo), capture_output=True, text=True,
        timeout=timeout
    )
    if r_push.returncode != 0:
        kind, err_msg = classify_git_error(r_push.stderr)
        # 09-24 增强：直连失败时尝试代理 fallback（部分环境直连阻断但代理可用）
        if kind == "network":
            r_proxy = subprocess.run(
                ["git", "-c", "http.proxy=http://127.0.0.1:2704",
                 "-c", "credential.helper=wincred", "push", "origin", "main"],
                cwd=str(repo), capture_output=True, text=True,
                timeout=timeout
            )
            if r_proxy.returncode == 0:
                return True, "", "ok"
            kind, err_msg = classify_git_error(r_proxy.stderr)
        return False, f"push 失败: {err_msg}", kind
    return True, "", "ok"


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
    p = argparse.ArgumentParser(description=f"L3 Publish {VERSION} — daily-why 发布脚本")
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
    p.add_argument("--retry", action="store_true",
                   help="仅重推已提交 commit（09-01 新增：人工补推必须走脚本，禁止裸 git push）")
    p.add_argument("--verify-report", action="store_true",
                   help="仅校验发布报告的人工补验是否真的落盘（09-17 v3.23 新增，#58 兜底；"
                        "判 FAIL 的报告须有声明 + ≥3 行判定表格，否则 exit 1）")
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

    # 学习总结（09-16 修复 #54：L2 实际产出命名为「学习总结-{话题}.md」，
    # 固定名 学习总结.md 检索会零命中 → Phase 1 匹配度检查整段被绕过（09-15 实测）。
    # 改为前缀 glob；多份命中取字典序首个并告警，避免静默取错文件）
    candidates = sorted(feed_dir.glob("学习总结*.md"))
    if candidates:
        result["learning_summary"] = candidates[0]
        if len(candidates) > 1:
            print(f"[Phase 0] ⚠️ 学习总结多份命中（{len(candidates)} 份），"
                  f"取 {candidates[0].name}；如非预期请手工清理 feed_dir")

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


# ── Phase 0: 话题去重硬卡点（09-09 新增）─────────────────────
# 把"话题去重"从 AI 软约束升级为代码硬卡点，防止重复选题落盘发布。
# 设计原则（呼应铁律 EXP-004 约束优于指令 / EXP-014 可观测性）：
#   1. fail-open：check_topic 自身故障（异常/超时/缺失/参数错）→ 放行+warn，绝不拖垮发布。
#   2. 默认硬拦截（09-15 v3.19 反转，根治 Silent Fail-Open：判定明确=重复时仅 warn 等于不拦）。
#      豁免须显式：DAILY_WHY_DEDUP_RELAX=1 降级为软 warn；旧 DAILY_WHY_DEDUP_ENFORCE 不再读取。
#      依据：v3.13 曾靠 SKILL.md 以 bash 前缀语法注入 ENFORCE，Windows 执行环境不生效（EXP-014
#      实证「文档注入≠运行时生效」），故改代码默认值——卡点的默认值就是它的真实行为。
#   3. 紧急总开关：DAILY_WHY_DEDUP_OFF=1 整体关闭。
#   4. 话题提取：读文章首行去 emoji（兼容无 '#' 标题新格式），传 check_topic.py 严格模式。

_EMOJI_RE = re.compile(
    r'[\U0001F000-\U0001FFFF\U00002700-\U000027BF\U0000FE00-\U0000FE0F'
    r'\U0000200D\U00002600-\U000026FF\U00002300-\U000023FF\U00002B50'
    r'\U0000231A-\U0000231B\U00002934-\U00002935\U000025AA-\U000025FE'
    r'\U00002B05-\U00002B07\U00002B1B-\U00002B1C\U00003030\U0000303D'
    r'\U00003297\U00003299\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF'
    r'\U00002702-\U000027B0]+'
)


def _extract_topic_from_file(path):
    """读文章首个非空行，去 emoji / markdown 标记，作为话题传给 check_topic。

    09-15 v3.20：对齐 check_topic 提取策略（跳过空行取首个非空行），消除双源漂移
    （P3 审查 P1-3，Master 确认修复）。旧实现只取 splitlines()[0]，文章首行为空行时
    返回 None → 去重 fail-open 放行，存在静默绕过窗口。
    """
    try:
        first = ""
        for raw in path.read_text(encoding="utf-8").splitlines():
            if raw.strip():
                first = raw.strip()
                break
    except Exception:
        return None
    if not first:
        return None
    first = _EMOJI_RE.sub("", first).strip()
    first = re.sub(r"^#+\s*", "", first)  # 去 markdown 标题
    return first or None


def dedup_gate_check(articles, res, date_str=None):
    """Phase 0 话题去重卡点：对当日待发布文章跑 check_topic.py 严格模式。

    09-09 修复：check_topic 必须传 --exclude-date {date_str}，排除当日自身文章，
    否则初版/优化版互相精确匹配 → 恒判重复 → 硬卡点 100% 误杀（v3.13 首跑即暴雷）。

    返回 True 表示已硬拦截（enforce 模式命中重复），调用方应中止发布。
    """
    if os.environ.get("DAILY_WHY_DEDUP_OFF") == "1":
        res.skip(0, "去重卡点已被 DAILY_WHY_DEDUP_OFF 关闭")
        return False

    ck = Path(__file__).resolve().parent / "check_topic.py"
    if not ck.exists():
        res.warn(0, "check_topic.py 缺失，去重卡点跳过（fail-open）")
        return False

    py = sys.executable or "python"
    # 09-15 v3.19：默认硬拦截；DAILY_WHY_DEDUP_RELAX=1 显式豁免降级软 warn（Silent Fail-Open 根治）
    enforce = os.environ.get("DAILY_WHY_DEDUP_RELAX") != "1"
    blocked = False
    seen = set()
    for key in ("v1", "v2"):
        f = articles.get(key)
        if not f or f in seen:
            continue
        seen.add(f)
        topic = _extract_topic_from_file(f)
        if not topic:
            res.warn(0, f"无法从 {f.name} 提取话题，去重跳过（fail-open）")
            continue
        cmd = [py, str(ck), topic]
        if date_str:
            cmd += ["--exclude-date", date_str]
        else:
            res.warn(0, "dedup_gate_check 未收到 date_str，去重不排除当日自身（潜在自匹配误杀风险）")
        try:
            r = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=30, encoding="utf-8",
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            res.warn(0, f"check_topic 执行异常({e})，去重跳过（fail-open）")
            continue
        if r.returncode == 1:
            detail = (r.stdout or r.stderr).strip()
            if enforce:
                res.fail(0, f"去重拦截：{f.name} 话题「{topic}」已存在 → {detail}")
                blocked = True
            else:
                res.warn(0, f"去重命中（软告警，未阻断）：{f.name} 话题「{topic}」→ {detail}")
        elif r.returncode == 2:
            res.warn(0, f"check_topic 参数错误，去重跳过（fail-open）：{(r.stderr or '').strip()}")
        else:
            res.ok(0, f"去重通过：{f.name} 话题「{topic}」")
    return blocked


# ── Phase 1: 匹配度检查 ─────────────────────────────

def _extract_improvements(text, patterns, bullet_re):
    """按 pattern 优先级 + 章节顺序提取改进点列表（09-17 v3.23 新增，修复 #58 闸门②）。

    【为什么需要遍历同一 pattern 的全部命中章节】
    09-17 原实现用 `re.search(pat, text)` 只取**首个**命中章节。当日首个命中是
    `## 一、四 AI 核心差距与采纳/拒绝决策`，其正文是 8 行 markdown 表格、0 个列表项，
    于是 improvements 为空、循环直接结束，后面真正含 6 项编号列表的
    `## 三、v2 改写要点` 从未被尝试（只要关键词表补上「改写要点」即可提出 6 条）。
    现改为 re.finditer 遍历全部命中章节，返回首个非空列表。

    返回 (items, source_heading)：source_heading 为该条目所在章节标题原文，
    渲染进发布报告供人工复核（EXP-014 可观测性即诚实性）。
    """
    for pat in patterns:
        for m in re.finditer(pat, text, re.MULTILINE | re.DOTALL):
            items = re.findall(bullet_re, m.group(1), re.MULTILINE)
            # 过滤破折号残段与空串噪音
            items = [x.strip() for x in items if x.strip() and x.strip() != "-"]
            if items:
                heading = " ".join((m.group(0).splitlines() or [""])[0]
                                   .lstrip("#").strip().split())
                return items, heading
    return [], None


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
    #
    # 09-03 修复（A-1）：原实现用单一硬编码正则 `^## v1 → v2 改进点`，而 L2 学习总结
    # 的章节标题由 AI 自由生成，两者无契约 —— 09-01 用「到」、09-03 用「三、采纳清单」
    # 均失配 → improvements 恒为空 → content.ok 硬编码 True → AI 在 Step 2 看到
    # 「改进点 0 条」顺势判定「无可验证内容」并跳过语义验证，L2 的改进全部绕过发布前门。
    # 现改为：① 多模式回退匹配（v1→v2 前缀优先，其次纯中文标题）；② 零命中即判该
    # 维度失败，不再静默恒真。
    # 依据橙皮书 EXP-004（约束优于指令：用校验代替建议）+ EXP-014（报告诚实性）。
    #
    # 09-17 v3.23 修复 #58（同一道防线第 2 次复发，两次都只修了「一半」）：
    #   闸门①「标题锚点位置」——原 pattern 要求关键词紧跟「## + 可选中文序号」，
    #     09-17 标题为 `## 一、四 AI 核心差距与采纳/拒绝决策`（关键词「核心差距」在
    #     **中部**，且与「采纳」以「与」并列）→ 两条 pattern 全不匹配 → 零命中。
    #     现 pattern 2 改为「标题任意位置含关键词即可」，并把「改写要点」纳入关键词。
    #   闸门②「章节选取」——原实现用 re.search 只取**首个**命中章节；09-17 首个命中
    #     章节正文是 8 行 markdown 表格 0 个列表项，空手而归后循环即结束，后面
    #     `## 三、v2 改写要点`（6 项编号列表，本可抽出）从未被尝试。现改
    #     _extract_improvements 用 re.finditer 遍历全部命中章节，取首个非空列表。
    #   闸门③「契约锚点」——新增最高优先 pattern 0，匹配 L2 SKILL v3.4 起强制的固定
    #     标题 `## 改进点`（无编号无修饰）。这是**在生产侧立契约**，从源头终结
    #     「L2 自由命名 vs L3 硬正则」的格式漂移（历史第 5 次分叉：→ / 到 /
    #     三、采纳清单 / v2 → v3 改进点 / 一、四 AI 核心差距）。继续在消费侧堆正则是
    #     治标（EXP-003 指令文件法则 + EXP-004 约束优于指令）。
    #
    # 匹配原则：只认「改进点/采纳清单/优化点/核心差距/改写要点」类标题；「质量概览」
    # 等只含表格与结论、不含改进列表的章节必须排除（09-03 实证：误抓概览会取到噪音）。
    # 注意「各AI亮点采纳」/「采纳项落地校验」含「采纳」但非改进列表，故关键词用
    # 「采纳清单/采纳要点」而非裸「采纳」，避免把 AI 贡献章节误当改进点。
    IMPROVEMENT_HEADING_PATTERNS = (
        # 模式0（09-17 v3.23 新增，契约锚点，最高优先）：L2 SKILL v3.4 强制的固定标题
        r"^##\s*改进点\s*$\n(.*?)(?=^##\s|\Z)",
        # 模式1：带 v1→v2 前缀（历史主流格式，06-15 至 09-16）
        r"^##\s*(?:[一二三四五六七八九十]+[、.]\s*)?"
        r"v1\s*(?:→|到|->|～)\s*v2\s*(?:改进点|优化点|采纳清单|核心差距|改写要点)"
        r"[^\n]*\n(.*?)(?=^##\s|\Z)",
        # 模式2（09-17 v3.23 放宽位置 + 显式支持 2 至 4 级标题）：标题**任意位置**
        # 含关键词即可。两点说明：
        #   ① 位置放宽：原要求关键词紧跟「## + 可选中文序号」，09-17 的
        #      `## 一、四 AI 核心差距与采纳/拒绝决策`（关键词在中部）因此零命中。
        #   ② 层级显式化：原 pattern 写成 `^##\s*(?:序号)?关键词…`，`\s*` 后必须紧跟
        #      关键词，实际上把 `###` 级标题挡在门外（`### 核心差距` 在 `##` 之后是
        #      `#`，既不匹配 `\s*` 也不匹配关键词）。放宽位置后 `[^\n]*` 会顺带吃掉
        #      第三个 `#`，导致 `###`/`####` 被**隐式**纳入，实测 06-19 / 07-06 / 07-29
        #      三份旧文件由「0 条」变「10 条」。这些 `### 核心差距` 子章节本身确实是
        #      AI 指出的差距清单（语义等同改进点），纳入属**覆盖率提升**而非误抓，
        #      故不退回隐式行为，改写为 `^#{2,4}` 使其**显式且有据**，避免下次有人
        #      看到 `###` 被匹配而误判为回归。
        #      防误抓仍靠关键词白名单收窄（见上方匹配原则），不靠标题层级。
        r"^#{2,4}\s*(?:[一二三四五六七八九十]+[、.]\s*)?[^\n]*"
        r"(?:采纳清单|改进点|优化点|核心差距|改写要点|采纳要点)"
        r"[^\n]*\n(.*?)(?=^#{1,4}\s|\Z)",
    )
    # bullet 提取：列表符号后必须有空白，避免把 `**加粗**` / `---` 误当列表项
    BULLET_RE = r"(?:^[-*]\s+|^\d+[.、]\s+)(.+)"
    if summary_path:
        summary_text = summary_path.read_text(encoding="utf-8")
        improvements, src_heading = _extract_improvements(
            summary_text, IMPROVEMENT_HEADING_PATTERNS, BULLET_RE)
        check_count = min(len(improvements), MAX_IMPROVEMENTS_CHECK)
        # 只做存在性检查（有改进点列表即可），语义验证交给 AI
        report["content"] = {
            # 零命中 = 提取失败（非「确实没有改进点」），判失败并告警
            "ok": bool(improvements),
            "improvements": improvements[:MAX_IMPROVEMENTS_CHECK],
            "total": check_count,
            "source": src_heading,
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
            _note = '' if c['ok'] else '（零命中 = 提取失败，AI 须人工读学习总结补验）'
            print(f"  内容改进:   {'✅' if c['ok'] else '❌'}  🤖 待 AI 验证  "
                  f"改进点={c['total']}条{_note}")
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

    # 1.4 review.json schema 机械校验（09-07 新增，A 方案「换判定主体」的脚本层）
    #
    # 背景：09-02 至 09-07 漏判率连续四天 100%（4/4、2/2、3/3、3/3）。期间
    # v2.5 / v2.6 / v2.7 三轮 prompt 补丁**全部只改文本、无执行校验** → 实战零改善。
    # v2.8 引入 Step 5.9 对照检查（gap_checks），本段负责机械校验「审校到底做没做」。
    #
    # 当前策略：**warn 不阻断**（新校验器未经实战，直接阻断有回归风险）。
    # 观察一周后由 Master 决定是否升级为阻断。
    _date_m = re.search(r"(\d{4}-\d{2}-\d{2})", v2_path.name)
    if _date_m:
        _d = _date_m.group(1)
        _base = Path(CFG["base_dir"])
        _scripts_dir = Path(__file__).resolve().parent
        if str(_scripts_dir) not in sys.path:
            sys.path.insert(0, str(_scripts_dir))
        try:
            import validate_review as _vr
        except ImportError:
            _vr = None
            res.warn(1, "review schema 校验器不可用（validate_review.py 导入失败）")
        if _vr:
            # 09-09 引用门禁：定位当日文章正文（优先优化版），供 validate_review 检测正文引用
            _arts_dir = _base / "articles"
            _article_path = None
            for _pat in (f"{_d}-优化版-每日冷知识-*.md", f"{_d}-每日冷知识-*.md"):
                _cands = sorted(_arts_dir.rglob(_pat)) if _arts_dir.exists() else []
                if _cands:
                    _article_path = _cands[-1]   # 取最新一篇（articles/YYYY-MM 子目录下递归查找）
                    break
            if _article_path is None:
                res.warn(1, "未找到当日文章正文，引用门禁 fail-open 跳过（请确认 articles/ 下存在当日文件）")
            for _tag, _rp in (("v1", _base / "review" / f"{_d}_review.json"),
                              ("v2", _base / "review" / f"{_d}_v2_review.json")):
                if not _rp.exists():
                    continue
                try:
                    _v = _vr.validate(_rp, article_path=_article_path)
                except Exception as _e:      # 校验器自身异常不得影响发布主流程
                    res.warn(1, f"[review schema {_tag}] 校验器异常: {_e}")
                    continue
                report.setdefault("review_schema", {})[_tag] = {
                    "ok": _v["ok"],
                    "errors": _v["errors"],
                    "warnings": _v["warnings"],
                    "stats": _v["stats"],
                }
                # 09-09 引用门禁：命中「正文有引用但 quote_checks 空」→ 硬阻断 L3 发布
                # （与 dedup_gate_check 同构：检测到即 sys.exit(1)，逼回 Reviewer 补 quote_checks）
                if _v.get("blocking"):
                    for _b in _v["blocking"][:3]:
                        res.fail(1, f"[review schema {_tag}] 引用门禁未过: {_b}")
                    res.fail(1, f"[review schema {_tag}] 引用门禁未过，L3 终止发布（回到 Reviewer 补 quote_checks 后重试）")
                    sys.exit(1)
                _ne, _nw = len(_v["errors"]), len(_v["warnings"])
                if _ne:
                    for _e in _v["errors"][:3]:
                        res.warn(1, f"[review schema {_tag}] {_e}")
                    if _ne > 3:
                        res.warn(1, f"[review schema {_tag}] 另有 {_ne - 3} 项错误")
                elif _nw:
                    res.ok(1, f"review schema {_tag} 校验通过（{_nw} 项提示）")
                    # 提示内容也落日志，否则只有数量、事后无法复盘（EXP-014 可观测性）
                    for _w in _v["warnings"][:2]:
                        res.ok(1, f"  ↳ {_tag} 提示: {_w}")
                else:
                    res.ok(1, f"review schema {_tag} 校验通过（无异常）")

    report["ok"] = all_ok

    # 09-03 修复（A-3）：Phase 1 此前全程只 print 不调 res.*，l3_run.log 无任何
    # Phase 1 行，成功路径完全无痕，事后无法区分「跑了且通过」与「根本没跑」。
    # 现统一落一行摘要日志（橙皮书 EXP-014：可观测性即诚实性）。
    if all_ok:
        res.ok(1, f"匹配度检查 PASS（结构 ✅ 内容改进={c.get('total', 0)}条 "
                  f"审核 P0={a.get('p0')} P1={a.get('p1')} "
                  f"规则 {rule_info['forbidden_last']}/{rule_info['checklist_last']}）")
    else:
        res.warn(1, f"匹配度检查 FAIL（结构 {'✅' if s['ok'] else '❌'} "
                    f"内容改进={c.get('total', 0)}条 "
                    f"审核 P0={a.get('p0')} P1={a.get('p1')} "
                    f"规则 {rule_info['forbidden_last']}/{rule_info['checklist_last']}）")
    return report


# ── Phase 2: IMA 云端备份 ────────────────────────────

def _detect_ima_version():
    """从 topics/ima_history.md 取最新备份版本号 → 进位（minor 满 9 进 1）

    十进制版本语义：3.9 → 4.0（不是 3.10）。

    09-03 修复（A-2）：删除「章节缺失 → 全文搜索」的降级路径。
    09-07 重构（记忆分片）：写入目标从 MEMORY.md 迁移到 topics/ima_history.md
    （切断对 MEMORY.md 的自动写入，防注入超限）。检测逻辑：
    1) 优先找「## IMA 备份历史」章节块，只在该块内取版本；
    2) 章节未建立时（迁移初期）取全文 vN.N —— 分片正文当前仅含备份序列
       v3.7 至 v4.1，无其他版本号，安全；major>=1000 护栏保留。
    章节缺失且全文无版本号 → 返回 "1.0"（宁从头编号，也不猜 —— EXP-014）。
    """
    hist = Path(CFG.get("ima_history_path", ""))
    if not hist.exists():
        return "1.0"

    content = hist.read_text(encoding="utf-8")

    # 优先：只从 IMA 备份历史章节取（兼容「最近5条」等后缀）
    section = re.search(r"## IMA 备份历史[^\n]*\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    scope = section.group(1) if section else content

    versions = re.findall(r"\bv(\d+\.\d+)\b", scope)
    if not versions:
        return "1.0"

    latest = max(versions, key=lambda v: [int(x) for x in v.split(".")])
    major, minor = [int(x) for x in latest.split(".")]
    # 合理性护栏：备份版本不应出现荒谬量级（> 1000 说明混入了非备份版本号）
    if major >= 1000:
        return "1.0"
    minor += 1
    if minor >= 10:
        major += 1
        minor = 0
    return f"{major}.{minor}"


def _append_ima_history(note_id, version, date_str):
    """追加一行到 topics/ima_history.md 的 IMA 备份历史表。

    09-07 重构（记忆分片）：写入目标从 MEMORY.md 迁移到 topics/ima_history.md
    （切断对 MEMORY.md 的自动写入 —— 防注入超限的唯一自动增长源）。
    08-31 修复保留：在 `## IMA 备份历史` 标题行后插入；标题缺失则自愈新建章节。
    返回 bool 供调用方校验，失败不静默。
    """
    hist = Path(CFG.get("ima_history_path", ""))
    if not hist.exists():
        return False
    content = hist.read_text(encoding="utf-8")
    new_row = f"- v{version} | note_id={note_id} | {date_str} | l3_publish.py 自动备份"
    pattern = r"(## IMA 备份历史[^\n]*\n)"
    m = re.search(pattern, content)
    if m:
        content = content.replace(m.group(1), m.group(1) + new_row + "\n", 1)
    else:
        # 自愈：标题行缺失则新建章节（topics/ima_history.md 迁移初期无此标题）
        if not content.endswith("\n"):
            content += "\n"
        content += f"\n## IMA 备份历史\n{new_row}\n"
    hist.write_text(content, encoding="utf-8")
    return True


def phase2_ima(date_str, dry_run, force, res):
    if dry_run:
        res.skip(2, f"将上传: daily-why 备份{date_str}")
        return "dry-run"

    if not confirm("即将上传配置到 IMA 云端，确认？", force):
        res.skip(2, "用户取消 IMA 备份")
        return "skip"

    # 预检测版本号，显式传给 ima_archive.py 避免版本撞车
    version = _detect_ima_version()
    if version == "1.0":
        # 章节缺失/混入异常 → 重置为 1.0。此时必须显式告警，否则 AI 会把
        # 「IMA 版本回到 v1.0」当成正常进位而忽视（09-03 教训：v2027.x → v3.7
        # 的暴跌曾被视为正常）。
        res.warn(2, "topics/ima_history.md 无有效备份版本号，备份版本重置为 v1.0，"
                    "请人工确认 topics/ima_history.md 与真实备份序列")

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

        # 追加到 topics/ima_history.md 的备份历史表（防止版本号撞车；09-07 起不再写 MEMORY.md）
        if note_id:
            if not _append_ima_history(note_id, version, date_str):
                res.warn(2, "topics/ima_history.md 追加失败（文件缺失或写入异常），请人工补记")

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
    # 09-07 新增 GAP_PATTERNS.md（A 方案数据层，reviewer_prompt v2.8 Step 5.9 依赖）
    refs = ["references/FORBIDDEN.md", "references/CHECKLIST.md",
            "references/FEEDBACK_LOG.md", "references/GAP_PATTERNS.md"]
    # Reviewer 独立审校 prompt（v2.0 主路径资产，纳入推送）
    reviewer_prompt = src_base / "reviewer_prompt.md"
    # L3 发布技能文件
    publish_skill = Path("C:/Users/admin/.workbuddy/skills/daily-why-publish/SKILL.md")
    l3_script = Path(CFG["scripts_dir"]) / "l3_publish.py"
    # 09-17 v3.23（修复 #59）：scripts/config.json 不再复制进 repo。该文件含 IMA KB ID，
    # repo .gitignore:2 有意忽略它（commit ea6465e「security: gitignore scripts/config.json」），
    # 复制进去只会留一个「未跟踪且被忽略」的残留副本、对 clone 者不可见，属死操作；
    # 且它留在 git_add_files 会触发 git add 被拒 + 静默失败（详见下方 add 回读校验）。

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
        # 09-15 v3.19：去重防线双向自检脚本（达尔文棘轮资产化，#45 教训制度化）
        (scripts_dir / "dedup_selftest.py", "dedup_selftest.py"),
        (scripts_dir / "topic_utils.py", "topic_utils.py"),
        (scripts_dir / "full_selfcheck.py", "full_selfcheck.py"),
        (scripts_dir / "message_handler.py", "message_handler.py"),
        (project_dir / "config" / "topic_candidates.json", "topic_candidates.json"),
        # C 组补全（09-01 验收审查 S-1）：format_checker/validate_article/prepare_topics/
        # update_history 4 文件长期不在同步清单（6 月整体提交进 repo 后 3 个月未同步，
        # 仓库 validate/prepare_topics/update_history 已漂移为旧版）。现纳入复制，
        # 与 git_add_files 同步补入（双向自检见下）。
        (scripts_dir / "format_checker.py", "format_checker.py"),
        (scripts_dir / "validate_article.py", "validate_article.py"),
        # 09-07 新增：review.json schema 校验器（A 方案脚本层，校验 gap_checks 等强制输出物）
        (scripts_dir / "validate_review.py", "scripts/validate_review.py"),
        (scripts_dir / "prepare_topics.py", "prepare_topics.py"),
        (scripts_dir / "update_history.py", "update_history.py"),
        (project_dir / "config" / "version.json", "version.json"),
        (project_dir / "config" / "writing_rules.json", "writing_rules.json"),
        # D 组补全（09-01 灰区清零）：v3.0/v3.1 整体提交进 repo 但白名单遗漏的在用文件
        (src_base / "CODE_REVIEW_GUIDE.md", "CODE_REVIEW_GUIDE.md"),
        (src_base / "references" / "EXAMPLES.md", "references/EXAMPLES.md"),
        (scripts_dir / "auto_fix.py", "auto_fix.py"),
        (scripts_dir / "case_matcher.py", "case_matcher.py"),
        # E 组补全（09-07 决策3）：记忆治理脚本纳入同步（方案 C v2 落地产物；
        # Master 拍板「加入 git 同步」，双向自检要求 git_add_files 与 extra_sync 逐项对齐）
        (scripts_dir / "check_memory_size.py", "scripts/check_memory_size.py"),
        (scripts_dir / "restructure_memory.py", "scripts/restructure_memory.py"),
        # F 组（09-08 v3 闸门 4）：铁律衰减与淘汰门禁（10 天降级 / 20 天下沉 / 再犯即升）
        (scripts_dir / "memory_decay.py", "scripts/memory_decay.py"),
        # 零损失校验：记忆下沉后核对被删事实能否在 topics/ 找回（v3 闸门 0）
        (scripts_dir / "verify_memory_migration.py", "scripts/verify_memory_migration.py"),
        # 写入准入：写 MEMORY.md 前先算账，回答「加 N 字符后总量与该区是否还放得下」（v3 闸门 5）
        (scripts_dir / "memory_budget.py", "scripts/memory_budget.py"),
        # 09-09 v3.16 修复：CHANGELOG.md 此前仅入 git_add_files 漏加复制源，
        # 导致自身从未进 repo（09-09 审计发现）。现补复制（EXP-004：约束要对齐真问题）
        (project_dir / "CHANGELOG.md", "CHANGELOG.md"),
        # G 组补全（09-16 修复 #55）：09-15 代码审查体系 v4.9 新增的两项已进
        # git_add_files 却漏配复制源 → 源改动永远同步不到 repo（同 v3.4 老毛病复发）。
        # 教训：新增产出物入 git_add_files 时必须同步补复制清单（EXP-004）
        (scripts_dir / "code_review_check.py", "scripts/code_review_check.py"),
        (project_dir / "docs" / "code-review-standard.md", "docs/code-review-standard.md"),
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

    # 反向自检（09-01 S-1 升级）：repo 中已被 git 跟踪但不在 git_add_files 的文件
    # （灰区）——它们不在 files_to_copy 复制范围，源改动永远不会同步进 repo，
    # 版本随工作区演进而陈旧（历史实证：format_checker 等 4 文件 6 月整体提交后
    # 3 个月未同步，repo 版本漂移）。双向自检 = 白名单内缺失 + 白名单外灰区都暴露。
    r_ls = subprocess.run(
        ["git", "ls-files"], cwd=str(repo), capture_output=True, text=True
    )
    tracked = {f for f in (r_ls.stdout or "").splitlines() if f.strip()}
    whitelist = set(CFG.get("git_add_files", []))
    # .gitignore 为仓库私有文件（git 约定），无需从工作区同步，豁免
    # 09-11 v3.18：新增灰区豁免清单（config.git_gray_exemptions）——达尔文 09-04
    # 实验一次性产物已归档+双备份、无后续改动，「源改动同步」语义不适用，进白名单
    # 属死条目（死文件判据）；每周重复同一条灰区告警属噪音，会诱发告警疲劳（EXP-014）。
    # 豁免必须走配置文件并留理由，禁止口头豁免（EXP-004 约束优于指令）。
    exemptions = set(CFG.get("git_gray_exemptions", []))
    gray = sorted(tracked - whitelist - {".gitignore"} - exemptions)
    if gray:
        res.warn(3, f"repo 有 {len(gray)} 个文件不在 git_add_files（灰区，改动不会同步）: "
                    f"{', '.join(gray)}")
    else:
        res.ok(3, "同步清单双向自检通过（白名单全覆盖，无灰区文件）")

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
        #
        # ⚠️ 09-07 P0 修复（常驻缺陷 38）：禁止用本地 origin/main 判 ahead。
        # 实证：origin/main 引用变 [gone] 时，`git rev-list --count origin/main..HEAD`
        # 报错且错误信息进 stderr，stdout 为空 → int("") → 0 → 判「无新变更，跳过」
        # → 已提交的 commit 永远推不上去，而日志看起来完全正常。
        # 09-07 实测：本地 bcc6dca 未推送、远端停在 3cb3e1f，正是走这条路径。
        #
        # 改用权威校验 verify_remote_sync()：其内含 ls-remote 取远端真值，并调用
        # force_write_remote_ref() 自愈写 loose ref，可正确处理 [gone] 场景。
        vstatus, vmsg = verify_remote_sync(repo, CFG.get("git_verify_timeout", 20))
        if vstatus == "mismatch":
            # 远端确实落后于本地 → 补推已提交但未推送的 commit
            push_timeout = CFG.get("git_push_timeout", 30)
            # 09-01 增强：函数内置网络探活+退避重试，外层不再二次调用
            success, err_msg, _ = git_pull_rebase_push(repo, push_timeout)
            if not success:
                res.fail(3, err_msg)
                return "push_fail"
            r = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(repo), capture_output=True, text=True
            )
            commit_hash = r.stdout.strip() if r.returncode == 0 else "unknown"
            return report_git_result(res, repo, f"补推已提交 commit={commit_hash}", verify)
        if vstatus == "unverified":
            # 网络不通/远端不可判：绝不能当「无新变更」静默跳过（09-07 头号教训：
            # 假绿比报错更危险 —— 今日 bcc6dca 未推送却显示「无变更，跳过」）
            res.warn(3, f"远端状态未核验，无法确定是否存在未推送 commit: {vmsg}")
            return "unverified"
        if vstatus == "ok_unfixed":
            res.warn(3, f"远端核验一致，但本地 origin/main 引用未能同步: {vmsg}")
            return "no_changes"
        res.skip(3, "无新变更（远端 ls-remote 核验一致），跳过")
        return "no_changes"

    changed_count = len(r.stdout.strip().splitlines())

    if dry_run:
        res.skip(3, f"将提交 {changed_count} 个文件变更")
        return "dry-run"

    if not confirm(f"即将推送 {changed_count} 个文件到 GitHub，确认？", force):
        res.skip(3, "用户取消推送")
        return "skip"

    # Step 3.3: git add（只 add 规则文件）
    #
    # 09-17 v3.23（修复 #59）：原实现 `subprocess.run(["git","add",f], capture_output=True)`
    # 把返回码与 stderr **全部丢弃**。被 .gitignore 忽略的文件会静默 add 失败
    # （实测 scripts/config.json：git add 报 "paths are ignored"、rc=1，而 Phase 3 依旧
    # 打印「白名单全覆盖，无灰区文件」）。现逐项回读校验：add 返回非 0 或 add 后仍未被
    # git 跟踪，即告警点名。EXP-014：可观测性即诚实性，工具报「已处理」不等于真处理。
    add_files = CFG.get("git_add_files", ["SKILL.md"])
    add_failed = []
    for f in add_files:
        fp = repo / f
        if not fp.exists():
            continue
        r_add = subprocess.run(["git", "add", f], cwd=str(repo),
                               capture_output=True, text=True)
        if r_add.returncode != 0:
            first_err = ((r_add.stderr or "").strip().splitlines() or [""])[0][:60]
            add_failed.append(f"{f}（add 被拒：{first_err or 'rc!=0'}）")
            continue
        r_chk = subprocess.run(["git", "ls-files", "--error-unmatch", f],
                               cwd=str(repo), capture_output=True, text=True)
        if r_chk.returncode != 0:
            add_failed.append(f"{f}（add 后仍未被 git 跟踪，疑似被 .gitignore 忽略）")
    if add_failed:
        res.warn(3, f"git add 未生效 {len(add_failed)} 项（改动不会进 GitHub）: "
                    f"{'; '.join(add_failed[:5])}")

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

    # git pull --rebase + push（含重试；09-01 增强：探活 + 退避重试内聚到函数内）
    push_timeout = CFG.get("git_push_timeout", 30)
    success, err_msg, _ = git_pull_rebase_push(repo, push_timeout)
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

def _script_zone_digest(script_zone_text):
    """脚本生成区的唯一指纹函数（写入侧与校验侧必须共用同一口径）。

    09-16 v3.22 修复 #57a：原实现两侧口径差 1 个换行——
      写入侧 script_zone 是 join(lines) 的结果，不含 checksum 行前那个分隔换行；
      校验侧 text[:cut] 却含该换行。
    于是每次渲染 md5 必然不等，check_report_tampered 恒报「已被手工改动」，
    与版本号是否变化无关（09-15 报告实测：recorded 与 head[:-1] 精确相等、
    与 head 不等）。AI 补充区被覆盖是必然结果，不是偶发。

    归一规则：先把尾部换行压成**恰好 1 个**，再取 md5。
    这样写入侧（script_zone，通常已以换行结尾）与校验侧（文件里的 text[:cut]，
    比 script_zone 多一个分隔换行）得到同一结果。
    注意不能用 rstrip 把尾部换行剥光：那会连 script_zone 自身那个换行也去掉，
    反而不等于旧记录值（09-16 实测 recorded 与 rstrip 版不等、与「压成 1 个」版相等）。
    该规则与 v3.22 之前写入的历史报告**天然兼容**，无需额外兼容分支。
    """
    return hashlib.md5((script_zone_text.rstrip("\n") + "\n").encode("utf-8")).hexdigest()


def _report_script_zone_md5(text):
    """对既有报告文件中的脚本生成区（checksum 标记之前的内容）计算指纹，
    用于「是否被人工改动」的告警。口径与写入侧 _script_zone_digest 一致（#57a），
    其归一规则同时兼容 v3.22 之前写入的历史报告，故无需额外兼容分支。"""
    cut = text.find(CHECKSUM_MARK)
    if cut != -1:
        text = text[:cut]
    return _script_zone_digest(text)


def _extract_preserved_tail(report_path):
    """提取既有报告中 checksum 标记之后的全部内容（AI 补充区），供渲染时原样保留。

    09-16 v3.22 修复 #57b：此前 render_report 全量 write_text，脚本区一有变化
    （典型：版本号演进）就把 AI 补充区一起覆盖（09-15 实测首轮 5 条判定 + 规则
    查证 + 处置意见被清空，只能重建）。现按「标记界定所有权」：标记之前归脚本、
    标记之后归 AI，二者互不侵占。
    返回 None 表示无标记或读取失败，调用方届时走首次渲染的空白模板。
    """
    if not report_path.exists():
        return None
    try:
        text = report_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(r"<!-- checksum: [0-9a-f]{32} -->", text)
    if not m:
        return None
    nl = text.find("\n", m.end())
    if nl == -1:
        return None
    return text[nl:]


def check_report_tampered(report_path, res):
    """渲染前校验既有报告的脚本生成区是否被手工改动（09-01 修复：
    今日报告被 AI 手工补写「15:58 重试成功」导致 errors=0 与 l3_run.log 矛盾）。

    09-16 v3.22（#57）：口径统一后此处命中即「脚本区真被人工改动」。
    按 cddl-codegen「never silent（绝不静默）」原则，覆盖前把旧文件另存一份并在
    告警里给出路径，避免静默丢失；标记之后的 AI 补充区无论如何都会保留
    （见 _extract_preserved_tail）。
    """
    if not report_path.exists():
        return
    try:
        text = report_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    m = re.search(r"<!-- checksum: ([0-9a-f]{32}) -->", text)
    if not m:
        res.warn(4, f"发布报告 {report_path.name} 无 checksum 标记（旧版生成），本次渲染后首次写入")
        return
    if m.group(1) != _report_script_zone_md5(text):
        note = ""
        backup_dir = report_path.parent / ".overwritten"
        dest = backup_dir / (f"{report_path.stem}."
                             f"{datetime.now().strftime('%Y%m%d-%H%M%S')}{report_path.suffix}")
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(report_path, dest)
            note = f"，旧版已备份至 {dest.relative_to(report_path.parent)}"
        except OSError as e:
            note = f"，旧版备份失败（{e}）"
        res.warn(4, f"发布报告 {report_path.name} 脚本生成区已被手工改动（checksum 不匹配），"
                    f"本次将重写脚本区、保留 AI 补充区{note}")


def render_report(date_str, v1_meta, v2_meta, ima_result, git_result, res, match_report=None):
    """渲染发布报告到 deliverables/{date}-发布报告.md（08-31 起替代 AI 手写，
    杜绝字数/得分/commit 失真。骨架全部由脚本数据生成，语义验证表留 AI 补充区；
    09-01 起脚本生成区写入 checksum 标记，防人工改动）"""
    try:
        deliverables = Path(CFG["base_dir"]) / "deliverables"
        deliverables.mkdir(parents=True, exist_ok=True)
        report_path = deliverables / f"{date_str}-发布报告.md"

        check_report_tampered(report_path, res)

        lines = [f"# 发布报告 — {date_str} {v1_meta['topic']}", ""]
        # 基本信息
        lines.append("## 基本信息")
        lines.append(f"- 话题：{v1_meta['topic']}")
        lines.append(f"- 分类：{v1_meta['category']}")
        lines.append(f"- 初版：{v1_meta['chinese_chars']} 字，{v1_meta['q_count']} 个Q")
        if v2_meta:
            lines.append(f"- 优化版：{v2_meta['chinese_chars']} 字，{v2_meta['q_count']} 个Q")
        lines.append(f"- 注：字数为全文口径（含标题与结尾表格），09-01 起与 validate_article.py 统一（上限 690）")
        lines.append("")
        # 执行结果（来自 Result.phases，脚本收集，非 AI 手写）
        lines.append("## 执行结果（脚本逐 Phase 记录）")
        for phase, status, msg in res.phases:
            lines.append(f"- Phase {phase} {status} {msg}")
        lines.append("")
        # 匹配度检查（09-02 方案A：脚本生成，位于 checksum 保护区，防 AI 手工篡改）
        if match_report:
            s = match_report.get("structure", {})
            c = match_report.get("content", {})
            a = match_report.get("audit", {})
            ru = match_report.get("rules", {})
            lines.append("## 匹配度检查（脚本生成，checksum 保护区）")
            lines.append(f"- 结构一致性: {'✅' if s.get('ok') else '❌'}  "
                         f"话题={'✅' if s.get('topic_match') else '❌'} "
                         f"分类={'✅' if s.get('category_match') else '❌'} "
                         f"Q数={s.get('q_count', '?')} {s.get('acf', '')}")
            if c.get("skipped"):
                lines.append("- 内容改进: ⏭️ 跳过（无学习总结）")
            elif c.get("total", 0) > 0:
                lines.append(f"- 内容改进: 🤖 待 AI 语义验证 改进点={c.get('total', 0)}条"
                             f"（来源章节：{c.get('source') or '?'}）")
            else:
                lines.append("- 内容改进: ❌ 提取失败：0 条（未命中任何改进点章节）"
                             "→ 须走 SOP Step 2.5 人工补验，并跑 "
                             "`l3_publish.py --verify-report` 校验补验是否落盘")
            if a.get("status") == "ok":
                lines.append(f"- 审核一致性: {'✅' if a.get('ok') else '❌'} "
                             f"P0={a.get('p0', '?')} P1={a.get('p1', '?')} 得分={a.get('score', '?')}")
            else:
                lines.append(f"- 审核一致性: ❌ {a.get('error', '')}")
            lines.append(f"- 规则同步: {'✅' if ru.get('ok') else '❌'} "
                         f"{ru.get('forbidden_last', '?')} / {ru.get('checklist_last', '?')}")
            lines.append(f"- 总体判定: {'✅ PASS' if match_report.get('ok') else '❌ FAIL'}")
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
        # ── 脚本生成区结束（09-16 v3.22 修复 #57）────────────────────
        # 所有权边界：CHECKSUM_MARK 之前归脚本（每次渲染无条件重写），之后归 AI
        # （无条件原样保留）。指纹函数与校验侧共用，口径归一（#57a）。
        script_zone = "\n".join(lines)
        checksum_line = f"{CHECKSUM_MARK} {_script_zone_digest(script_zone)} -->"

        preserved = _extract_preserved_tail(report_path)
        if preserved is not None and preserved.strip():
            content = script_zone + "\n" + checksum_line + preserved
            kept = len([ln for ln in preserved.splitlines() if ln.strip()])
            res.ok(4, f"发布报告已更新：脚本区重写，边界之后 {kept} 行 AI 补充区原样保留")
        else:
            content = (
                script_zone + "\n" + checksum_line + "\n"
                "\n## AI 语义验证补充区（由执行 AI 填充）\n"
                "\n<!-- 在此追加 Step 2 语义验证：改进点 | 判定 | 证据（行号）。"
                "禁止改动上方由脚本生成的部分。 -->\n\n"
            )
            res.ok(4, "发布报告已渲染（首次生成，AI 补充区为空白模板）")

        report_path.write_text(content, encoding="utf-8")

        # 09-16 v3.22 自校验（#57a 配套，EXP-014 可观测性即诚实性）：
        # 写完立即回读并用校验侧函数复算。若不等，说明写入口径与校验口径再次
        # 漂移，属脚本自身缺陷，直接报出来，而不是留给用户当成「有人手改」。
        try:
            back = report_path.read_text(encoding="utf-8", errors="replace")
            if _report_script_zone_md5(back) != _script_zone_digest(script_zone):
                res.warn(4, "发布报告 checksum 自校验未通过（写入与校验口径不一致），"
                            "属脚本自身缺陷，请报修（EXP-014）")
        except OSError:
            pass
        return str(report_path)
    except OSError as e:
        res.warn(4, f"发布报告渲染失败（不影响发布）: {e}")
        return None


def verify_report_supplement(date_str):
    """校验发布报告 AI 补充区是否真的完成了人工补验（09-17 v3.23 新增，#58 兜底）。

    【要解决的问题】Phase 1 判 FAIL 后靠 SOP Step 2.5「人工补验」兜住，属**人肉防线**：
    AI 忘了补验时，脚本与报告都无从判断，而这个 FAIL 会被后续读报告的人当成已知噪音
    放过（与常驻缺陷 #47「引用空校验静默放过」同构，EXP-014 可观测性缺口）。
    本命令把「记得补验」从口头承诺变成可机械校验的事实（EXP-004 约束优于指令）。

    【规则】报告含 `总体判定: ❌ FAIL` 时，checksum 标记之后的 AI 补充区必须：
      ① 明确声明为人工补验（含「人工补验 / 脚本提取失败 / 提取器未命中」之一）；
      ② 至少 MIN_REPORT_VERIFY_ROWS 行判定表格（`| … | ✅/⚠️/❌ | …`）。
    未判 FAIL 的报告直接通过（无需补验）。

    返回 exit code：0 通过 / 1 未通过。SOP 要求补验后必跑本命令并把输出贴进报告，
    禁止仅口头声称「已补验」。
    """
    report_path = Path(CFG["base_dir"]) / "deliverables" / f"{date_str}-发布报告.md"
    if not report_path.exists():
        print(f"❌ 报告不存在：{report_path}")
        return 1
    text = report_path.read_text(encoding="utf-8", errors="replace")
    if "总体判定: ❌ FAIL" not in text:
        print(f"✅ {report_path.name}：未判 FAIL，无需人工补验（跳过校验）")
        return 0
    m = re.search(r"<!-- checksum: [0-9a-f]{32} -->", text)
    tail = text[m.end():] if m else ""
    if not tail.strip():
        print(f"❌ {report_path.name}：判 FAIL 但 checksum 之后无 AI 补充区"
              f"（人工补验疑似未执行）")
        return 1
    rows = [ln for ln in tail.splitlines()
            if re.match(r"^\|.*\|\s*(?:✅|⚠️|❌)", ln.strip())]
    declared = bool(re.search(r"人工补验|脚本提取失败|提取器未命中", tail))
    problems = []
    if not declared:
        problems.append("补充区未声明为人工补验")
    if len(rows) < MIN_REPORT_VERIFY_ROWS:
        problems.append(f"判定表格仅 {len(rows)} 行（要求 ≥ {MIN_REPORT_VERIFY_ROWS}）")
    if problems:
        print(f"❌ {report_path.name}：人工补验校验未通过 → {'；'.join(problems)}")
        return 1
    print(f"✅ {report_path.name}：人工补验已落盘（判定 {len(rows)} 行 + 已声明为人工补验）")
    return 0


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


def check_version_consistency(res):
    """09-01 新增（版本号易腐根治，验收 S-2）；09-16 v3.22 升级（修复 #56）。

    读 config/version.json 唯一权威源，校验各技能 SKILL.md 的实际版本号。
    不一致 warn（不阻断发布）。

    【#56 背景】原实现按 version_field 走单口径（frontmatter / title /
    title_and_footer）。实测三处漂移全部漏判，且都是人工核对才发现：
      - writer 变更日志物理尾部滞留在 v3.3（该口径只看 frontmatter）；
      - audit 脚注历史串漏记 v1.6（该口径只看标题）；
      - publish frontmatter 漏升 v3.21（title_and_footer 恰好不查 frontmatter）。
    另外 title_and_footer 用 re.search 取**首条** `*Version:`，而变更日志是正序
    列表，首条永远是历史上最早那条（writer 有 43 条，套上去会取到 v3.1）。

    【现口径】不再依赖 version_field 的单一口径：凡文件里能取到版本的位置
    （frontmatter / 标题 / 末条变更日志）**全部**必须等于权威源，任一不符即 warn
    并指出具体是哪个口径。title_and_footer 原有的脚本常量校验保留（L3 线额外
    比对 l3_publish.py 的 VERSION）。依据 EXP-004：能机械校验的约束别停留在文档。
    """
    base_dir = Path(CFG.get("base_dir", "F:/WorkBuddy/daily-why"))
    vp = base_dir / "config" / "version.json"
    if not vp.exists():
        res.warn(0, "[版本] config/version.json 缺失（版本号权威源不存在，跳过校验）")
        return
    try:
        vdata = json.loads(vp.read_text(encoding="utf-8"))
    except Exception as e:
        res.warn(0, f"[版本] config/version.json 读取失败: {e}")
        return
    skills = vdata.get("skills", {})
    if not skills:
        res.warn(0, "[版本] version.json 无 skills 条目")
        return
    for name, info in skills.items():
        expected = info.get("version", "")
        fpath = info.get("file", "")
        if not fpath or not Path(fpath).exists():
            res.warn(0, f"[版本] {name}: SKILL 文件不存在 {fpath}")
            continue
        content = Path(fpath).read_text(encoding="utf-8")

        probes = []  # [(口径名, 实际值)]
        m_fm = re.search(r"^version:\s*(\S+)", content, re.MULTILINE)
        if m_fm:
            probes.append(("frontmatter", m_fm.group(1)))
        m_ti = re.search(r"^#\s+\S+\s*([vV]\d[\w.-]*)", content, re.MULTILINE)
        if m_ti:
            probes.append(("标题", m_ti.group(1)))
        foot = re.findall(r"\*Version:\s*([vV]\d[\w.-]*)", content)
        if foot:
            # 取末条：变更日志正序排列，物理尾部才是当前最新版
            probes.append(("日志末条", foot[-1]))
        if info.get("version_field") == "title_and_footer":
            l3 = Path(CFG["scripts_dir"]) / "l3_publish.py"
            if l3.exists():
                m_v = re.search(r'VERSION\s*=\s*"([^"]+)"', l3.read_text(encoding="utf-8"))
                if m_v:
                    probes.append(("脚本常量", m_v.group(1)))

        if not probes:
            res.warn(0, f"[版本] {name}: 各口径均取不到版本号（文件结构可能已变，请检查）")
            continue

        shown = " / ".join(f"{k}:{v}" for k, v in probes)
        bad = [f"{k}={v}" for k, v in probes if v != expected]
        if bad:
            res.warn(0, f"[版本] {name}: 权威源={expected} 实际({shown})"
                        f"（不一致口径：{', '.join(bad)}！改版本号前必须先改 config/version.json）")
        else:
            res.ok(0, f"[版本] {name}: {shown} 与权威源 {expected} 全部一致")


def check_memory_health(res):
    """Phase 0 记忆体积门禁（09-07 新增，记忆分片重构配套）：warn 不阻断。

    复用 scripts/check_memory_size.py 的目标表（工作空间/用户级 MEMORY.md 字符上限
    + automation memory.md 行数上限）。EXP-004：约束优于指令，体积必须机械校验。
    策略与 validate_review.py（Phase 1.4）一致：新门禁先 warn 观察一周，无误报后升阻断。
    try/except 全包：门禁自身故障不得影响发布主流程。
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import check_memory_size as _cms
        for name, path, limit, warn_at, metric in _cms.DEFAULT_TARGETS:
            r = _cms.check_one(name, path, limit, warn_at, metric)
            if r.get("error"):
                continue
            unit = r.get("unit", "字符")
            tag = "[记忆]"
            if r.get("over"):
                res.warn(0, f"{tag} {name} 超限: {r['chars']} / {limit} {unit}，"
                            "须先压缩或分片（记忆只准经 topics/ 分片全文下沉，禁止删历史）")
            elif r.get("warn"):
                res.warn(0, f"{tag} {name} 接近上限: {r['chars']} / {limit} {unit}，"
                            "本次写入请只做合并索引，勿增新段")
            else:
                res.ok(0, f"{tag} {name} 合规 ({r['chars']} {unit})")

            # v3 闸门 2/3（09-08 新增）：分区配额 + 单行长度。
            # 背景：总量合规不等于各区合规，09-08 实测 0.72x 时架构区已超配额 133。
            # 只报不阻断，与总量门禁同一策略（先 warn 观察）。
            for s in r.get("section_issues", []):
                res.warn(0, f"{tag} 分区超配额: {s['section']} {s['chars']}/{s['quota']} 字符"
                            f"（超 {s['over']}）→ 须把该区细节下沉到 topics/ 分片，主文件只留指针行")
            for ln in r.get("long_lines", []):
                res.warn(0, f"{tag} 超长行 L{ln['line']}: {ln['chars']} 字符"
                            f"（上限 {_cms.MAX_LINE_CHARS}）→ 须拆行或下沉，禁止把内容压进更长的单行")
    except Exception as e:  # noqa: BLE001 门禁故障不阻断发布
        res.warn(0, f"[记忆] 体积门禁执行异常（不阻断）: {e}")


# ── Main ─────────────────────────────────────────────

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    args = parse_args()
    res = Result()

    # --verify-report 模式（09-17 v3.23 新增，#58 兜底）：
    # Phase 1 判 FAIL 的报告必须真的有 AI 人工补验落盘。SOP Step 2.5 完成后必跑本命令，
    # 禁止仅口头声称「已人工补验」——那是人肉防线，没有机械校验就等于没有防线（EXP-014）。
    if args.verify_report:
        if args.date:
            vd = args.date
        else:
            vd, _ = detect_latest_date()
            vd = vd or datetime.now().strftime("%Y-%m-%d")
        sys.exit(verify_report_supplement(vd))

    # --retry 模式（09-01 新增 P5）：仅重推已提交 commit。
    # 背景：今日 15:58 网络失败后人工裸 git push 导致 l3_run.log 断裂、发布报告被手工改写。
    # 约束：任何补推必须走本脚本（探活+退避重试+远端核验+日志留痕），禁止裸 git push。
    if args.retry:
        repo = Path(CFG["git_repo_path"])
        if not (repo / ".git").exists():
            res.fail(0, f"git 仓库不存在: {repo}")
            res.summary()
            sys.exit(1)
        # 安全守卫：--retry 只允许在 main 分支执行（避免在优化/其他分支误推）
        cur = subprocess.run(["git", "branch", "--show-current"], cwd=str(repo),
                             capture_output=True, text=True)
        if (cur.stdout or "").strip() != "main":
            res.fail(0, f"--retry 仅允许在 main 分支执行（当前分支: {(cur.stdout or '').strip() or '(detached)'}）。"
                        "请先 checkout main 再重试")
            res.summary()
            sys.exit(1)
        res.ok(0, "--retry 模式：仅重推已提交 commit（走完整脚本留日志）")
        push_timeout = CFG.get("git_push_timeout", 90)
        success, err_msg, kind = git_pull_rebase_push(repo, push_timeout)
        if not success:
            res.fail(3, err_msg)
            res.summary()
            sys.exit(1)
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo), capture_output=True, text=True
        )
        commit_hash = r.stdout.strip() if r.returncode == 0 else "unknown"
        report_git_result(res, repo, f"补推已提交 commit={commit_hash}", verify=not args.no_verify)
        res.summary()
        sys.exit(0 if res.errors == 0 else 1)

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
    print(f"  L3 Publish {VERSION} — daily-why")
    print(f"  目标日期: {date_str}")
    if args.dry_run:
        print("  模式: --dry-run（只检查不执行）")
    print("=" * 50)

    # Phase 0: 幂等性检查
    if check_idempotency(date_str, args.force):
        res.warn(0, f"{date_str} 已发布过，跳过（使用 --force 强制重新执行）")
        res.summary()
        sys.exit(0)

    # Phase 0: 版本号一致性校验（09-01 S-2：权威源 config/version.json）
    check_version_consistency(res)

    # Phase 0: 记忆体积门禁（09-07 新增：warn 不阻断，观察一周后评估升阻断）
    check_memory_health(res)

    # Phase 0: 扫描文件
    articles = scan_articles(date_str)

    # Phase 0: 话题去重硬卡点（09-09 新增：默认软模式 warn 不阻断）
    if dedup_gate_check(articles, res, date_str):
        res.summary()
        sys.exit(1)

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

    # Phase 1: 匹配度检查（09-02 方案A：默认开启，结果渲染进报告 checksum 保护区；
    # --skip-match 仅作手动逃生阀，SKILL.md Step 3 不再默认传入）
    match_pass = True
    match_report = None
    if args.skip_match:
        res.skip(1, "--skip-match 手动跳过匹配度检查（逃生阀）")
    elif articles["v2"] is None:
        res.skip(1, "无优化版，跳过匹配度检查")
    elif articles["learning_summary"] is None:
        res.skip(1, "无学习总结，跳过匹配度检查")
    else:
        match_report = phase1_match_check(
            articles["v1"], articles["v2"], articles["learning_summary"],
            args.dry_run, res
        )
        match_pass = match_report["ok"]
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
        report_path = render_report(date_str, v1_meta, v2_meta, ima_result, git_result, res, match_report=match_report)
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
