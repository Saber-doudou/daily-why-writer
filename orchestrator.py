#!/usr/bin/env python3
"""
orchestrator.py — 多Agent工作流编排器
协调内容生成和审核发布两个阶段的工作流。

设计原则：
  - 阶段1（内容生成）：选题→查证→写作→自检
  - 阶段2（审核发布）：审核→判例匹配→修正→更新历史
  - 中间状态通过文件传递，便于调试和恢复

用法：
    python orchestrator.py                    # 运行完整工作流
    python orchestrator.py --phase1           # 只运行阶段1（内容生成）
    python orchestrator.py --phase2           # 只运行阶段2（审核发布）
    python orchestrator.py --resume           # 从上次中断处恢复
    python orchestrator.py --dry-run          # 模拟运行，不实际执行
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any

# Windows GBK 兼容
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")


WORKSPACE = Path(r"F:\WorkBuddy\daily-why")
PYTHON_PATH = r"C:/Users/admin/.workbuddy/binaries/python/versions/3.13.12/python.exe"


class Orchestrator:
    """多Agent工作流编排器"""

    def __init__(self, workspace: Path, dry_run: bool = False):
        self.workspace = workspace
        self.dry_run = dry_run
        self.state_file = workspace / "orchestrator-state.json"
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.article_file = workspace / f"{self.today}-每日冷知识.md"

    def load_state(self) -> Dict[str, Any]:
        """加载编排器状态"""
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                return self.create_initial_state()
        return self.create_initial_state()

    def create_initial_state(self) -> Dict[str, Any]:
        """创建初始状态"""
        return {
            "date": self.today,
            "phase": "pending",
            "phase1_status": "pending",
            "phase2_status": "pending",
            "article_file": str(self.article_file),
            "started_at": None,
            "completed_at": None,
            "errors": []
        }

    def save_state(self, state: Dict[str, Any]):
        """保存编排器状态"""
        self.state_file.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def check_article_exists(self) -> bool:
        """检查今天的文章是否已存在"""
        return self.article_file.exists()

    def run_phase1(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        阶段1：内容生成
        - 选题
        - 查证
        - 写作
        - 自检

        注意：这个阶段由 automation Agent 执行，这里只提供编排逻辑
        """
        print("=" * 60)
        print("📝 阶段1：内容生成（Content Generation Phase）")
        print("=" * 60)

        state["phase"] = "phase1"
        state["phase1_status"] = "in_progress"
        state["started_at"] = datetime.now().isoformat()

        if self.dry_run:
            print("[DRY-RUN] 模拟运行阶段1")
            state["phase1_status"] = "completed"
            return state

        # 阶段1的实际工作由 automation Agent 执行
        # 这里只记录状态
        print("[orchestrator] 阶段1工作由 automation Agent 执行")
        print("[orchestrator] 等待 Agent 完成内容生成...")

        return state

    def run_phase2(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        阶段2：审核发布
        - 质量审核
        - 判例匹配（如果需要）
        - 修正（如果需要）
        - 历史更新
        """
        print("=" * 60)
        print("🔍 阶段2：审核发布（Quality Review Phase）")
        print("=" * 60)

        state["phase"] = "phase2"
        state["phase2_status"] = "in_progress"

        if self.dry_run:
            print("[DRY-RUN] 模拟运行阶段2")
            state["phase2_status"] = "completed"
            state["completed_at"] = datetime.now().isoformat()
            return state

        # 检查文章是否存在
        if not self.article_file.exists():
            error = f"文章文件不存在: {self.article_file}"
            print(f"[ERROR] {error}")
            state["errors"].append(error)
            state["phase2_status"] = "failed"
            return state

        # 运行 validate_article.py
        print("[orchestrator] 运行质量审核...")
        # 这里的实际执行由 automation Agent 完成

        return state

    def run_workflow(self, phase: Optional[str] = None):
        """运行工作流"""
        print("🚀 Daily Why 多Agent工作流编排器")
        print(f"📅 日期: {self.today}")
        print(f"📁 工作空间: {self.workspace}")
        print()

        # 加载状态
        state = self.load_state()

        # 检查是否已完成
        if state.get("phase2_status") == "completed":
            print("✅ 今天的文章已完成，跳过执行")
            return

        # 检查文章是否已存在
        if self.check_article_exists():
            print(f"📄 今天的文章已存在: {self.article_file}")
            if phase is None or phase == "phase2":
                # 文章已存在，阶段1视为已完成
                if state.get("phase1_status") != "completed":
                    state["phase1_status"] = "completed"
                    print("✅ 阶段1标记为已完成（文章已存在）")
                # 直接进入阶段2
                state = self.run_phase2(state)
            else:
                print("⏭️ 跳过阶段1，文章已存在")
        else:
            # 运行阶段1
            if phase is None or phase == "phase1":
                state = self.run_phase1(state)

        # 保存状态
        self.save_state(state)

        print()
        print("=" * 60)
        print("📊 工作流状态")
        print(f"  阶段1: {state.get('phase1_status', 'pending')}")
        print(f"  阶段2: {state.get('phase2_status', 'pending')}")
        if state.get("errors"):
            print(f"  错误: {len(state['errors'])} 个")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Daily Why 多Agent工作流编排器")
    parser.add_argument("--phase1", action="store_true",
                        help="只运行阶段1（内容生成）")
    parser.add_argument("--phase2", action="store_true",
                        help="只运行阶段2（审核发布）")
    parser.add_argument("--resume", action="store_true",
                        help="从上次中断处恢复")
    parser.add_argument("--dry-run", action="store_true",
                        help="模拟运行，不实际执行")
    parser.add_argument("--status", action="store_true",
                        help="显示当前状态")

    args = parser.parse_args()

    # 创建编排器
    orchestrator = Orchestrator(WORKSPACE, dry_run=args.dry_run)

    if args.status:
        state = orchestrator.load_state()
        print("📊 当前状态:")
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return

    # 确定要运行的阶段
    phase = None
    if args.phase1:
        phase = "phase1"
    elif args.phase2:
        phase = "phase2"

    # 运行工作流
    orchestrator.run_workflow(phase)


if __name__ == "__main__":
    main()
