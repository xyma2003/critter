"""
services/diary — 宠物日记生成服务
调用 LLM 生成当日宠物视角日记，返回纯文本。

支持两种 backend：
- SiliconFlow (OpenAI-compatible)：设 OPENAI_API_KEY 环境变量
- Claude CLI：fallback（如果 Claude CLI 在 PATH 中）
"""
import os
import subprocess
import datetime
from config import CLAUDE_CLI
from PyQt6.QtCore import QThread, pyqtSignal


class DiaryWorker(QThread):
    """QThread worker for generating diary without blocking the UI."""
    result_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, stats_snap, counts, pet_name, pet_personality, pet_catchphrase, date_str):
        super().__init__()
        self._args = (stats_snap, counts, pet_name, pet_personality, pet_catchphrase, date_str)

    def run(self):
        try:
            text = generate_diary(*self._args)
            if text:
                self.result_ready.emit(text)
            else:
                self.error_occurred.emit("生成失败，请检查 Claude CLI 是否可用。")
        except Exception as e:
            self.error_occurred.emit(f"生成失败: {e}")


def generate_diary(stats_snap, counts, pet_name, pet_personality, pet_catchphrase, date_str):
    """
    生成宠物视角的每日日记。

    stats_snap: {'mood': float, 'hunger': float, 'energy': float, 'mood_label': str}
    counts:     {'feed': int, 'play': int, 'rest': int, 'pet': int}
    返回日记文本字符串，失败返回 None。
    """
    # 将日期格式化为可读形式
    try:
        d = datetime.date.fromisoformat(date_str)
        date_readable = f"{d.month}月{d.day}日"
    except Exception:
        date_readable = date_str

    # 组装互动描述
    interaction_lines = []
    if counts.get('feed', 0) > 0:
        interaction_lines.append(f"被喂食了 {counts['feed']} 次")
    if counts.get('play', 0) > 0:
        interaction_lines.append(f"玩耍了 {counts['play']} 次")
    if counts.get('rest', 0) > 0:
        interaction_lines.append(f"休息了 {counts['rest']} 次")
    if counts.get('pet', 0) > 0:
        interaction_lines.append(f"被抚摸了 {counts['pet']} 次")

    if not interaction_lines:
        interaction_lines.append("今天好像没有太多互动")

    interaction_str = "、".join(interaction_lines)

    catchphrase_quoted = '\u201c' + pet_catchphrase + '\u201d'
    prompt = (
        f"你是一只名叫{pet_name}的桌面宠物，性格{pet_personality}，"
        f"口头禅是{catchphrase_quoted}。\n"
        f"今天是{date_readable}，写一条今天的日记（100字以内），"
        f"用第一人称宠物视角，内容基于：{interaction_str}。"
        f"当前心情状态：{stats_snap.get('mood_label', '一般')}。\n"
        f"语气可爱真实，不要太正式，像宠物在自言自语。"
        f"直接输出日记正文，不加标题、不加日期前缀。"
    )

    # SiliconFlow (OpenAI-compatible) backend — preferred when OPENAI_API_KEY is set
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=openai_key,
                base_url=os.environ.get("OPENAI_API_BASE", "https://api.siliconflow.cn/v1"),
            )
            resp = client.chat.completions.create(
                model=os.environ.get("OPENAI_MODEL", "Qwen/Qwen3-32B"),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.7,
            )
            text = resp.choices[0].message.content.strip()
            return text if text else None
        except Exception:
            return None

    # Claude CLI fallback
    try:
        result = subprocess.run(
            [CLAUDE_CLI, '--print', prompt],
            capture_output=True, text=True, timeout=30
        )
        text = result.stdout.strip()
        return text if text else None
    except Exception:
        return None
