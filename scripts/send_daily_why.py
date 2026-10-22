#!/usr/bin/env python3
"""
发送每日冷知识到微信文件传输助手
使用 uiautomation 库操作微信客户端

[重要变更 2026-04-23]
本脚本已从自动化流水线移除，不再被 automation-2 自动调用。
现作为手动工具保留，需要时手动运行。

自动化新流程：生成内容 → [配图可选] → 保存md → 完成
"""

import os
import re
import uiautomation as auto
import time
import sys
from pathlib import Path
from datetime import datetime, timedelta

# ========== 配置 ==========
WORKSPACE = Path(r"F:\WorkBuddy\daily-why")
IMAGES_DIR = WORKSPACE / "generated-images"

# 全局变量
wechat_window = None


def get_today_str():
    """返回今天的日期字符串 YYYY-MM-DD"""
    return datetime.now().strftime("%Y-%m-%d")


def get_yesterday_str():
    """返回昨天的日期字符串 YYYY-MM-DD"""
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")


def find_latest_md():
    """查找今天的 md 文件，如果没有则找昨天的"""
    today = get_today_str()
    yesterday = get_yesterday_str()

    today_file = WORKSPACE / "articles" / today[:7] / f"{today}-每日冷知识.md"
    if today_file.exists():
        print(f"  [OK] 找到今日文件: {today_file.name}")
        return today_file

    yesterday_file = WORKSPACE / "articles" / yesterday[:7] / f"{yesterday}-每日冷知识.md"
    if yesterday_file.exists():
        print(f"  [OK] 找到昨日文件: {yesterday_file.name}")
        return yesterday_file

    md_files = list(WORKSPACE.glob("articles/**/*-每日冷知识*.md"))
    if md_files:
        latest = max(md_files, key=lambda p: p.stat().st_mtime)
        print(f"  [OK] 找到最新文件: {latest.name}")
        return latest

    raise FileNotFoundError("未找到任何每日冷知识 md 文件")


def find_image_for_md(md_file):
    """查找与 md 文件对应的配图（支持多种命名格式）"""
    date_match = re.match(r"(\d{4}-\d{2}-\d{2})", md_file.name)
    if not date_match:
        return None
    date_str = date_match.group(1)

    # 支持的所有命名格式
    candidates = []

    # 格式1: A_fun_scientific_illustration__2026-04-23T*.png (Hunyuan旧格式)
    candidates.extend(IMAGES_DIR.glob(f"A_fun_scientific_illustration__{date_str}T*.png"))
    # 格式2: 每日冷知识_2026-04-23.png
    candidates.extend(IMAGES_DIR.glob(f"每日冷知识_{date_str}.png"))
    # 格式3: 每日冷知识_{date_str}*.png
    candidates.extend(IMAGES_DIR.glob(f"每日冷知识_{date_str}*.png"))
    # 格式4: {date_str}-*.png (今天用的格式: 2026-04-23-手指起皱.png)
    candidates.extend(IMAGES_DIR.glob(f"{date_str}-*.png"))
    # 格式5: {date_str}_*.png
    candidates.extend(IMAGES_DIR.glob(f"{date_str}_*.png"))
    # 格式6: *{date_str}*.png (兜底)
    candidates.extend(IMAGES_DIR.glob(f"*{date_str}*.png"))

    # 找最新且存在的一个
    valid = [p for p in candidates if p.exists()]
    if valid:
        # 按修改时间排序，返回最新的
        chosen = max(valid, key=lambda p: p.stat().st_mtime)
        print(f"  [OK] 找到配图: {chosen.name}")
        return chosen

    # 兜底：找24小时内最新的一张图
    if not IMAGES_DIR.exists():
        print("  [WARN] 配图目录不存在，将只发送文字")
        return None
    images = sorted(IMAGES_DIR.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    for img in images:
        age = datetime.now() - datetime.fromtimestamp(img.stat().st_mtime)
        if age.total_seconds() < 86400:
            print(f"  [OK] 使用最近生成的配图（24h内）: {img.name}")
            return img

    print("  [WARN] 未找到配图，将只发送文字")
    return None


def extract_text_from_md(md_file):
    """从 md 文件提取纯文字内容"""
    content = md_file.read_text(encoding="utf-8")
    lines = content.split("\n")
    text_lines = []

    for line in lines:
        if line.startswith("#"):
            continue
        if line.startswith("---"):
            continue
        if not line.strip():
            continue
        # 移除 markdown 格式
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"\*(.+?)\*", r"\1", line)
        line = re.sub(r"^[\-\*\+]\s+", "", line)
        line = re.sub(r"^>\s+", "", line)

        if line.strip():
            text_lines.append(line.strip())

    # 提取标题（支持 emoji 装饰前缀）
    title_match = re.search(r"#\s+(.+)", content)
    if not title_match:
        title_match = re.search(r"为什么[^\n]+", content)
    title = title_match.group(1).lstrip("🐙🌊❓😲🐱🔄💡🔥⚡🌈☀️🎵🧊🫀👁️🐻❄️🪞🤦 ").strip() if title_match else "今日冷知识"

    text = "🍶 今日冷知识\n\n"
    text += "\n".join(text_lines)
    return text


def find_wechat_with_retry(max_retries=3, wait_seconds=10):
    """带重试的微信窗口查找"""
    for attempt in range(1, max_retries + 1):
        print(f"  尝试 {attempt}/{max_retries} ...")

        try:
            wechat_window = auto.WindowControl(Name="微信", ClassName="WeChatMainWndForPC")
            if wechat_window.Exists(maxSearchSeconds=5):
                print("  [OK] 微信窗口已找到")
                return wechat_window
        except Exception as e:
            pass

        if attempt < max_retries:
            print(f"  [WARN] 微信未就绪，{wait_seconds}秒后重试...")
            time.sleep(wait_seconds)
        else:
            print("  [WARN] 微信重试耗尽，切换降级模式")

    return None


def find_file_transfer_assistant(wechat_window):
    """查找文件传输助手"""
    print("  搜索文件传输助手...")

    search_box = wechat_window.EditControl(Name="搜索")
    if search_box.Exists(maxSearchSeconds=2):
        search_box.Click()
        time.sleep(0.3)

    search_box = wechat_window.EditControl(Name="搜索")
    search_box.SendKeys("文件传输助手")
    time.sleep(1)

    list_item = wechat_window.ListItemControl(Name="文件传输助手")
    if list_item.Exists(maxSearchSeconds=5):
        list_item.Click()
        print("  [OK] 文件传输助手已打开")
        time.sleep(0.5)
        return True

    raise Exception("文件传输助手未找到")


def send_image(image_path):
    """发送图片"""
    print(f"  发送图片: {os.path.basename(image_path)}")

    img_btn = auto.ButtonControl(Name="图片")
    if not img_btn.Exists(maxSearchSeconds=2):
        img_btn = auto.ButtonControl(Name="图片文件")

    if not img_btn.Exists(maxSearchSeconds=2):
        attachment_btn = auto.ButtonControl(Name="附件")
        if attachment_btn.Exists(maxSearchSeconds=2):
            attachment_btn.Click()
            time.sleep(0.5)

    file_input = auto.EditControl(ClassName="ComboBoxEx32")
    if file_input.Exists(maxSearchSeconds=3):
        file_input.SendKeys(image_path)
        time.sleep(0.3)
        auto.SendKeys("{Enter}")
        time.sleep(0.5)

        send_btn = auto.ButtonControl(Name="打开")
        if send_btn.Exists(maxSearchSeconds=3):
            send_btn.Click()
            time.sleep(1.5)

        print("    [OK] 图片已发送")
    else:
        print("    [WARN] 文件输入框未找到，跳过图片")


def send_text(text):
    """发送文字消息"""
    print("  发送文字...")

    edit_control = wechat_window.EditControl(Name="输入")
    if not edit_control.Exists(maxSearchSeconds=2):
        edit_control = wechat_window.EditControl(SubName="输入")

    if edit_control.Exists(maxSearchSeconds=2):
        edit_control.Click()
        time.sleep(0.2)
        auto.SetClipboardText(text)
        auto.SendKeys("^v")
        time.sleep(0.3)

        send_btn = auto.ButtonControl(Name="发送")
        if send_btn.Exists(maxSearchSeconds=2):
            send_btn.Click()
            print("    [OK] 文字已发送")
        else:
            auto.SendKeys("{Enter}")
            time.sleep(0.3)
            print("    [OK] 文字已发送（回车）")
    else:
        raise Exception("消息输入框未找到")


def fallback_console_output(text_content, image_file, md_file):
    """微信不可用时的降级输出"""
    print()
    print("=" * 50)
    print("[降级模式] 微信未就绪，内容输出如下：")
    print("=" * 50)
    print()
    print("[文字内容]")
    print(text_content)
    if image_file:
        print()
        print(f"[配图路径] {image_file}")
    print()
    print("=" * 50)
    print("提示：请打开微信后手动复制发送，或重新运行本脚本")
    print("=" * 50)


def main():
    global wechat_window

    print("=" * 50)
    print("WeChat - Daily Why Sender (v2 - 增强版)")
    print("=" * 50)
    print()

    try:
        # 1. 查找 md 文件
        print("[1/4] 查找每日冷知识文件...")
        md_file = find_latest_md()

        # 2. 查找配图
        print("[2/4] 查找配图...")
        image_file = find_image_for_md(md_file)

        # 3. 提取文字内容
        print("[3/4] 提取文字内容...")
        text_content = extract_text_from_md(md_file)
        print(f"  文字长度: {len(text_content)} 字")

        # 4. 发送到微信
        print("[4/4] 发送到微信...")
        wechat_window = find_wechat_with_retry(max_retries=3, wait_seconds=10)

        if wechat_window is None:
            # 降级模式：输出到控制台
            fallback_console_output(text_content, image_file, md_file)
            return

        find_file_transfer_assistant(wechat_window)

        if image_file:
            send_image(str(image_file))
            time.sleep(1.5)

        send_text(text_content)

        print()
        print("[DONE] Daily Why 已发送到文件传输助手!")
        print(f"       内容: {md_file.name}")
        if image_file:
            print(f"       配图: {image_file.name}")

    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        print("请先生成今日冷知识内容")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
