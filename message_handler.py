#!/usr/bin/env python3
"""
message_handler.py — Agent间消息处理模块
处理内容生成Agent和审核发布Agent之间的消息传递。

⚠️ 历史遗留：非当前默认执行路径（v2.0 独立 Reviewer 审校使用 spawn 独立 agent + 文件落盘 review/{date}_review.json，不依赖本消息通道；本文件仅作参考保留）

用法：
    python message_handler.py send --from content-generator --to quality-reviewer --message '{"type":"article_draft",...}'
    python message_handler.py receive --agent quality-reviewer --message '{"type":"article_draft",...}'
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any


class MessageHandler:
    """Agent间消息处理器"""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.messages_dir = workspace / "messages"
        self.messages_dir.mkdir(exist_ok=True)

    def send_message(self, from_agent: str, to_agent: str, message: Dict[str, Any]) -> str:
        """发送消息到目标Agent

        Args:
            from_agent: 发送方Agent名称
            to_agent: 接收方Agent名称
            message: 消息内容

        Returns:
            消息ID
        """
        # 生成消息ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        message_id = f"{from_agent}_to_{to_agent}_{timestamp}"

        # 构建完整消息
        full_message = {
            "id": message_id,
            "from": from_agent,
            "to": to_agent,
            "timestamp": datetime.now().isoformat(),
            "content": message
        }

        # 保存消息到文件
        message_file = self.messages_dir / f"{message_id}.json"
        message_file.write_text(json.dumps(full_message, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"[message_handler] 消息已发送: {message_id}")
        print(f"[message_handler] 发送方: {from_agent}")
        print(f"[message_handler] 接收方: {to_agent}")
        print(f"[message_handler] 消息类型: {message.get('type', 'unknown')}")

        return message_id

    def receive_message(self, agent_name: str, message_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """接收消息

        Args:
            agent_name: 接收方Agent名称
            message_id: 消息ID（可选，如果指定则接收特定消息）

        Returns:
            消息内容，如果没有消息则返回None
        """
        if message_id:
            # 接收特定消息
            message_file = self.messages_dir / f"{message_id}.json"
            if message_file.exists():
                message = json.loads(message_file.read_text(encoding="utf-8"))
                if message.get("to") == agent_name:
                    print(f"[message_handler] 接收到消息: {message_id}")
                    return message.get("content")
                else:
                    print(f"[message_handler] 消息 {message_id} 不是发送给 {agent_name} 的")
                    return None
            else:
                print(f"[message_handler] 消息 {message_id} 不存在")
                return None
        else:
            # 接收最新的未处理消息
            messages = list(self.messages_dir.glob("*.json"))
            messages.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            for message_file in messages:
                message = json.loads(message_file.read_text(encoding="utf-8"))
                if message.get("to") == agent_name:
                    print(f"[message_handler] 接收到最新消息: {message_file.stem}")
                    return message.get("content")

            print(f"[message_handler] 没有发送给 {agent_name} 的消息")
            return None

    def list_messages(self, agent_name: Optional[str] = None) -> list:
        """列出消息

        Args:
            agent_name: Agent名称（可选，如果指定则只列出该Agent的消息）

        Returns:
            消息列表
        """
        messages = []
        for message_file in self.messages_dir.glob("*.json"):
            message = json.loads(message_file.read_text(encoding="utf-8"))
            if agent_name is None or message.get("from") == agent_name or message.get("to") == agent_name:
                messages.append({
                    "id": message.get("id"),
                    "from": message.get("from"),
                    "to": message.get("to"),
                    "timestamp": message.get("timestamp"),
                    "type": message.get("content", {}).get("type", "unknown")
                })

        return messages

    def clear_messages(self, agent_name: Optional[str] = None):
        """清除消息

        Args:
            agent_name: Agent名称（可选，如果指定则只清除该Agent的消息）
        """
        cleared = 0
        for message_file in self.messages_dir.glob("*.json"):
            message = json.loads(message_file.read_text(encoding="utf-8"))
            if agent_name is None or message.get("from") == agent_name or message.get("to") == agent_name:
                message_file.unlink()
                cleared += 1

        print(f"[message_handler] 已清除 {cleared} 条消息")


def main():
    parser = argparse.ArgumentParser(description="Agent间消息处理工具")
    subparsers = parser.add_subparsers(dest="command", help="命令")

    # send 命令
    send_parser = subparsers.add_parser("send", help="发送消息")
    send_parser.add_argument("--from", dest="from_agent", required=True, help="发送方Agent名称")
    send_parser.add_argument("--to", required=True, help="接收方Agent名称")
    send_parser.add_argument("--message", required=True, help="消息内容（JSON格式）")

    # receive 命令
    receive_parser = subparsers.add_parser("receive", help="接收消息")
    receive_parser.add_argument("--agent", required=True, help="接收方Agent名称")
    receive_parser.add_argument("--message-id", help="消息ID（可选）")

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出消息")
    list_parser.add_argument("--agent", help="Agent名称（可选）")

    # clear 命令
    clear_parser = subparsers.add_parser("clear", help="清除消息")
    clear_parser.add_argument("--agent", help="Agent名称（可选）")

    args = parser.parse_args()

    # 创建消息处理器
    workspace = Path(r"F:\WorkBuddy\daily-why")
    handler = MessageHandler(workspace)

    if args.command == "send":
        try:
            message = json.loads(args.message)
            message_id = handler.send_message(args.from_agent, args.to, message)
            print(f"消息ID: {message_id}")
        except json.JSONDecodeError as e:
            print(f"错误: 消息格式无效 - {e}")

    elif args.command == "receive":
        message = handler.receive_message(args.agent, args.message_id)
        if message:
            print(f"消息内容:")
            print(json.dumps(message, ensure_ascii=False, indent=2))

    elif args.command == "list":
        messages = handler.list_messages(args.agent)
        print(f"共 {len(messages)} 条消息:")
        for msg in messages:
            print(f"  {msg['id']}: {msg['from']} -> {msg['to']} ({msg['type']})")

    elif args.command == "clear":
        handler.clear_messages(args.agent)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
