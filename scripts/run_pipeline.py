#!/usr/bin/env python3
"""
run_pipeline.py — 编排器：串联 prepare → validate → update → send
替代 automation-2 prompt 中的多步指令，减少 AI token 消耗。

设计思路：
  Phase B 的核心目标是把 prompt 中的"机械操作"移到 Python 脚本中。
  AI 只需要做一件事：生成内容。
  其余的扫描话题、验证格式、更新记忆、发送消息全部由脚本完成。

流程：
  1. prepare_topics.py  → 生成 topics_context.json（AI 读这个文件选话题）
  2. [AI 生成文章]       → AI 的唯一任务
  3. validate_article.py → 验证文章格式
  4. update_history.py   → 更新 memory.md
  5. send_daily_why.py   → 发送到微信（可选，现在默认跳过）

用法：
  # 全流程（不含 AI 生成）
  python run_pipeline.py prepare            # 步骤1：生成话题上下文
  python run_pipeline.py validate           # 步骤3：验证最新文章
  python run_pipeline.py update             # 步骤4：更新记忆
  python run_pipeline.py send               # 步骤5：发送
  python run_pipeline.py validate-update    # 步骤3+4：验证+更新
  python run_pipeline.py status             # 查看当前状态
  python run_pipeline.py new-prompt         # 生成精简版 prompt

  # 完整流程（编排器）
  python run_pipeline.py --all              # 准备 → 验证 → 更新
"""

import sys
import re
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime


WORKSPACE = Path(r"F:\WorkBuddy\daily-why")
PYTHON = sys.executable  # 使用当前 Python 解释器


def run_script(script_name: str, extra_args: list = None, capture: bool = True) -> dict:
    """运行子脚本并返回结果"""
    script_path = WORKSPACE / "scripts" / script_name
    cmd = [PYTHON, str(script_path)]
    if extra_args:
        cmd.extend(extra_args)

    print(f"\n{'='*50}")
    print(f"▶ 运行: {script_name} {' '.join(extra_args or [])}")
    print(f"{'='*50}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            encoding="utf-8",
            timeout=60,
            cwd=str(WORKSPACE),
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(f"[STDERR] {result.stderr}", file=sys.stderr)
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "returncode": -1, "error": "timeout"}
    except Exception as e:
        return {"success": False, "returncode": -1, "error": str(e)}


def step_prepare():
    """步骤1：准备话题上下文"""
    result = run_script("prepare_topics.py", ["--limit", "50"])
    if result["success"]:
        topics_file = WORKSPACE / "config" / "topics_context.json"
        if topics_file.exists():
            data = json.loads(topics_file.read_text(encoding="utf-8"))
            print(f"\n✅ 话题上下文已生成: {data['total_count']} 个历史话题")
            return True
    print(f"\n❌ 话题准备失败")
    return False


def step_validate(filepath: str = None):
    """步骤3：验证文章"""
    args = []
    if filepath:
        args.append(filepath)
    else:
        args.append("--latest")
    result = run_script("validate_article.py", args)
    return result["success"]


def step_update(filepath: str = None):
    """步骤4：更新记忆"""
    args = []
    if filepath:
        args.append(filepath)
    result = run_script("update_history.py", args)
    return result["success"]


def step_send():
    """步骤5：发送到微信（现在默认跳过）"""
    print("\n⚠️  微信发送已从自动化移除（2026-04-23 决策）")
    print("   如需手动发送，请运行: python send_daily_why.py")
    return True


def step_status():
    """查看当前状态"""
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n{'='*50}")
    print(f"Daily Why Pipeline 状态 ({today})")
    print(f"{'='*50}")

    # 今日文件
    today_file = WORKSPACE / "articles" / today[:7] / f"{today}-每日冷知识.md"
    if today_file.exists():
        print(f"  ✅ 今日文章: {today_file.name}")
    else:
        print(f"  ❌ 今日文章: 未生成")

    # topics_context.json
    topics_file = WORKSPACE / "config" / "topics_context.json"
    if topics_file.exists():
        data = json.loads(topics_file.read_text(encoding="utf-8"))
        age = datetime.now() - datetime.fromisoformat(data["generated_at"])
        print(f"  ✅ 话题上下文: {data['total_count']} 个话题 ({age.days}天前生成)")
    else:
        print(f"  ❌ 话题上下文: 未生成")

    # memory.md
    from update_history import find_memory_file
    try:
        memory_path = find_memory_file()
        content = memory_path.read_text(encoding="utf-8")
        record_count = len(re.findall(r"^## \d{4}-\d{2}-\d{2}", content, re.MULTILINE))
        print(f"  ✅ Memory 记录: {record_count} 条 ({memory_path.parent.name})")
    except Exception:
        print(f"  ❌ Memory: 未找到")

    # send_daily_why.py
    send_script = WORKSPACE / "scripts" / "send_daily_why.py"
    print(f"  ℹ️  微信发送: 已从自动化移除（手动可用）")

    print(f"\n{'='*50}")


def generate_new_prompt():
    """生成精简版 prompt（Phase B 核心产出）"""
    today = datetime.now().strftime("%Y-%m-%d")

    prompt = f"""生成一篇"每日一个为什么"冷知识文章。

## 步骤
1. 读取 `F:/WorkBuddy/daily-why/config/topics_context.json`，选择一个未用过的话题
2. 按下方结构和格式生成文章
3. 保存到 `F:/WorkBuddy/daily-why/articles/{{年月}}/{{日期}}-每日冷知识.md`
4. 运行 `python F:/WorkBuddy/daily-why/scripts/validate_article.py` 验证格式
5. 运行 `python F:/WorkBuddy/daily-why/scripts/update_history.py` 更新记忆

## 内容结构（必须按此顺序）
1. **故事化开头**：用一个场景或生活化小故事切入，引出话题
2. **疑问驱动解释**：围绕核心问题，用3-4个递进式问题引导读者思考并给出答案
3. **趣味反转结尾**：在结尾揭示一个令人意外的反转或彩蛋

## 排版格式要求
- 标题用 emoji 装饰（如 🐙 🌊 ❓ 😲）
- 适当使用分隔线 `---` 分区
- 引用块 `>` 用于故事场景描写和反转金句
- 加粗 `**` 突出关键概念
- 列表用于问题展示
- 结尾附风格说明表格

## 内容规范
- 字数：200-400字
- 话题来源：自然科学/生活常识/人体奥秘/宇宙探索
- 语言：轻松愉快、生动有趣、互动性强、有记忆点
- 避免过于学术化表达，增强场景感和代入感
- **已用话题见 topics_context.json，避免重复！**
"""

    # 尝试读取最新话题摘要
    topics_file = WORKSPACE / "config" / "topics_context.json"
    if topics_file.exists():
        data = json.loads(topics_file.read_text(encoding="utf-8"))
        recent = data["topic_summaries"][:10]
        prompt += f"\n## 最近话题（绝对不要重复）\n"
        for t in recent:
            prompt += f"- {t}\n"

    print(prompt)
    print(f"\n{'='*50}")
    print(f"提示：以上 prompt 比原版精简约 60%（移除了硬编码话题列表和格式规则）")
    print(f"AI 只需关注内容生成，格式验证和记忆更新由脚本自动完成")
    print(f"{'='*50}")


def main():
    parser = argparse.ArgumentParser(description="Daily Why Pipeline 编排器")
    parser.add_argument("command", nargs="?",
                        choices=["prepare", "validate", "update", "send",
                                 "validate-update", "status", "new-prompt"],
                        default="status",
                        help="要执行的步骤")
    parser.add_argument("--all", action="store_true",
                        help="执行完整流程（准备→验证→更新）")
    parser.add_argument("--file", help="指定文章文件路径")
    args = parser.parse_args()

    print(f"\n{'#'*50}")
    print(f"# Daily Why Pipeline v1.0 (Phase B)")
    print(f"# {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*50}")

    if args.all:
        # 完整流程
        step_prepare()
        step_validate(args.file)
        step_update(args.file)
        step_status()
    elif args.command == "prepare":
        step_prepare()
    elif args.command == "validate":
        step_validate(args.file)
    elif args.command == "update":
        step_update(args.file)
    elif args.command == "send":
        step_send()
    elif args.command == "validate-update":
        step_validate(args.file)
        step_update(args.file)
    elif args.command == "status":
        step_status()
    elif args.command == "new-prompt":
        generate_new_prompt()
    else:
        step_status()


if __name__ == "__main__":
    main()
