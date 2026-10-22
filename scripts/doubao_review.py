#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
doubao_review.py - 豆包审阅辅助脚本

职责：把"豆包审阅"环节中的机械操作（定位文章、判断工作日、探测路径、
检查投喂状态、初始化文件夹）全部脚本化，让豆包 AI 只专注于审阅内容本身。

用法：
    python doubao_review.py --find-today       # 定位今日文章，输出JSON
    python doubao_review.py --status            # 检查今日投喂素材状态
    python doubao_review.py --init              # 初始化今日投喂素材文件夹
    python doubao_review.py --info              # 输出今日文章元信息
    python doubao_review.py --all               # 完整预检（探测+工作日+定位+状态）
    python doubao_review.py --workspace "D:/xxx"  # 指定项目路径（覆盖默认）

设计原则：
  - 路径探测失败 -> 立即退出，不执行任何写入
  - 周末 -> 明确提示无文章，不报错
  - 所有输出为 JSON，便于豆包 AI 解析
  - 退出码：0=成功，1=未找到项目，2=周末，3=文章不存在，4=参数错误
"""

import sys
import json
import argparse
import glob
from pathlib import Path
from datetime import datetime

# Windows GBK 兼容
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

# 默认项目路径（绑定这台电脑）
DEFAULT_WORKSPACE = r"F:\WorkBuddy\daily-why"

# 投喂素材中的四个AI文件名
AI_FILES = ["ds.txt", "ima.txt", "千问.txt", "豆包.txt"]


def output(data: dict, exit_code: int = 0):
    """统一JSON输出并退出"""
    print(json.dumps(data, ensure_ascii=False, indent=2))
    sys.exit(exit_code)


def detect_workspace(custom_path: str = None) -> Path:
    """
    探测项目路径。
    优先使用自定义路径，否则使用默认路径。
    探测失败 → 输出错误并退出（退出码1）。
    """
    workspace = Path(custom_path) if custom_path else Path(DEFAULT_WORKSPACE)

    if not workspace.exists():
        output({
            "status": "error",
            "error": "workspace_not_found",
            "message": f"未找到 daily-why 项目目录：{workspace}",
            "hint": "当前可能不是工作电脑。请用 --workspace 指定正确的项目路径，或在绑定了 F:\\WorkBuddy\\daily-why 的电脑上运行。",
            "checked_path": str(workspace)
        }, exit_code=1)

    if not (workspace / "articles").exists():
        output({
            "status": "error",
            "error": "invalid_workspace",
            "message": f"目录存在但缺少 articles 子目录，可能不是有效的 daily-why 项目：{workspace}",
            "checked_path": str(workspace)
        }, exit_code=1)

    return workspace


def is_workday(d: datetime = None) -> bool:
    """判断是否为工作日（周一=0 到 周五=4）"""
    d = d or datetime.now()
    return d.weekday() < 5


def get_date_strings(d: datetime = None):
    """返回常用日期格式：(YYYY-MM-DD, YYYY-MM, YYYYMMDD)"""
    d = d or datetime.now()
    return (
        d.strftime("%Y-%m-%d"),
        d.strftime("%Y-%m"),
        d.strftime("%Y%m%d")
    )


def find_today_article(workspace: Path) -> dict:
    """
    定位今日文章。
    匹配模式：articles/YYYY-MM/YYYY-MM-DD-每日冷知识*.md
    返回文章信息 dict，找不到则返回 None。
    """
    date_ymd, date_ym, _ = get_date_strings()
    pattern = str(workspace / "articles" / date_ym / f"{date_ymd}-每日冷知识*.md")
    matches = glob.glob(pattern)

    if not matches:
        return None

    # 取第一个匹配（正常情况下只有一篇）
    article_path = Path(matches[0])
    return {
        "path": str(article_path),
        "filename": article_path.name,
        "exists": True,
        "size_bytes": article_path.stat().st_size
    }


def get_article_info(article_path: str) -> dict:
    """提取文章元信息：标题、字数、Q数等"""
    path = Path(article_path)
    if not path.exists():
        return {"error": "file_not_found", "path": str(path)}

    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # 提取标题（第一个 # 开头的行）
    title = ""
    for line in lines:
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            break

    # 统计字数（去掉markdown标记后的中文字符+英文单词近似）
    # 简单统计：非空白字符数
    char_count = sum(1 for c in content if not c.isspace())

    # 统计Q数
    q_count = content.count("**Q1") + content.count("**Q2") + content.count("**Q3") + content.count("**Q4")

    return {
        "path": str(path),
        "title": title,
        "char_count": char_count,
        "q_count": q_count,
        "line_count": len(lines),
        "size_bytes": path.stat().st_size
    }


def check_feed_status(workspace: Path) -> dict:
    """
    检查今日投喂素材文件夹状态。
    返回每个AI文件的填充状态（空/已填充/不存在）。
    """
    _, _, date_compact = get_date_strings()
    feed_dir = workspace / "投喂素材" / date_compact

    result = {
        "feed_dir": str(feed_dir),
        "feed_dir_exists": feed_dir.exists(),
        "files": {}
    }

    if not feed_dir.exists():
        result["message"] = "投喂素材文件夹尚未创建"
        return result

    for filename in AI_FILES:
        fpath = feed_dir / filename
        if not fpath.exists():
            result["files"][filename] = {"status": "missing", "size_bytes": 0}
        elif fpath.stat().st_size == 0:
            result["files"][filename] = {"status": "empty", "size_bytes": 0}
        else:
            result["files"][filename] = {
                "status": "filled",
                "size_bytes": fpath.stat().st_size
            }

    # 汇总
    filled = sum(1 for v in result["files"].values() if v["status"] == "filled")
    result["summary"] = {
        "total": len(AI_FILES),
        "filled": filled,
        "empty_or_missing": len(AI_FILES) - filled
    }
    return result


def init_feed_folder(workspace: Path) -> dict:
    """
    初始化今日投喂素材文件夹。
    创建目录和4个空txt文件（如果不存在）。
    """
    _, _, date_compact = get_date_strings()
    feed_dir = workspace / "投喂素材" / date_compact

    created_dir = False
    created_files = []

    if not feed_dir.exists():
        feed_dir.mkdir(parents=True, exist_ok=True)
        created_dir = True

    for filename in AI_FILES:
        fpath = feed_dir / filename
        if not fpath.exists():
            fpath.touch()
            created_files.append(filename)

    return {
        "status": "ok",
        "feed_dir": str(feed_dir),
        "created_dir": created_dir,
        "created_files": created_files,
        "message": f"投喂素材文件夹已就绪：{feed_dir}"
    }


def cmd_find_today(workspace: Path):
    """--find-today: 定位今日文章"""
    article = find_today_article(workspace)
    date_ymd, _, _ = get_date_strings()

    if article is None:
        output({
            "status": "not_found",
            "date": date_ymd,
            "message": f"今日（{date_ymd}）文章不存在",
            "article": None
        }, exit_code=3)
    else:
        output({
            "status": "found",
            "date": date_ymd,
            "article": article
        }, exit_code=0)


def cmd_status(workspace: Path):
    """--status: 检查投喂状态"""
    result = check_feed_status(workspace)
    result["status"] = "ok"
    output(result, exit_code=0)


def cmd_init(workspace: Path):
    """--init: 初始化投喂文件夹"""
    result = init_feed_folder(workspace)
    output(result, exit_code=0)


def cmd_info(workspace: Path):
    """--info: 文章元信息"""
    article = find_today_article(workspace)
    if article is None:
        output({
            "status": "not_found",
            "message": "今日文章不存在，无法提取元信息"
        }, exit_code=3)
    info = get_article_info(article["path"])
    info["status"] = "ok"
    output(info, exit_code=0)


def cmd_all(workspace: Path):
    """--all: 完整预检"""
    date_ymd, _, _ = get_date_strings()
    now = datetime.now()

    result = {
        "status": "ok",
        "timestamp": now.isoformat(),
        "date": date_ymd,
        "weekday": now.strftime("%A"),
        "workspace": str(workspace)
    }

    # 工作日检查
    if not is_workday(now):
        result["workday"] = False
        result["message"] = f"今日是 {now.strftime('%A')}，周末无文章。脚本正常退出，不执行任何操作。"
        output(result, exit_code=2)

    result["workday"] = True

    # 文章定位
    article = find_today_article(workspace)
    result["article"] = article
    if article is None:
        result["article_status"] = "not_found"
    else:
        result["article_status"] = "found"
        # 附加元信息
        info = get_article_info(article["path"])
        result["article_info"] = info

    # 投喂状态
    feed = check_feed_status(workspace)
    result["feed_status"] = feed

    # 豆包.txt 单独标记
    doubao_status = feed.get("files", {}).get("豆包.txt", {}).get("status", "missing")
    result["doubao_filled"] = doubao_status == "filled"
    result["doubao_status"] = doubao_status

    output(result, exit_code=0)


def main():
    parser = argparse.ArgumentParser(
        description="豆包审阅辅助脚本 — 定位文章、检查状态、初始化投喂文件夹",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
退出码说明：
  0 = 成功
  1 = 未找到项目目录（可能不是工作电脑）
  2 = 周末无文章
  3 = 今日文章不存在
  4 = 参数错误
        """
    )
    parser.add_argument("--find-today", action="store_true",
                        help="定位今日文章，输出JSON")
    parser.add_argument("--status", action="store_true",
                        help="检查今日投喂素材文件夹状态")
    parser.add_argument("--init", action="store_true",
                        help="初始化今日投喂素材文件夹（创建目录和空文件）")
    parser.add_argument("--info", action="store_true",
                        help="输出今日文章元信息（标题、字数、Q数）")
    parser.add_argument("--all", action="store_true",
                        help="完整预检（探测+工作日+定位+状态）")
    parser.add_argument("--workspace", type=str, default=None,
                        help="指定项目路径（默认：F:/WorkBuddy/daily-why）")

    args = parser.parse_args()

    # 至少需要一个操作
    if not any([args.find_today, args.status, args.init, args.info, args.all]):
        parser.print_help()
        sys.exit(4)

    # 第一步：探测项目路径（失败立即退出，不执行任何写入）
    workspace = detect_workspace(args.workspace)

    # 执行操作
    if args.all:
        cmd_all(workspace)
    elif args.find_today:
        cmd_find_today(workspace)
    elif args.status:
        cmd_status(workspace)
    elif args.init:
        cmd_init(workspace)
    elif args.info:
        cmd_info(workspace)


if __name__ == "__main__":
    main()
