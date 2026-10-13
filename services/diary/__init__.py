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
from copy import deepcopy
from config import CLAUDE_CLI
from PyQt6.QtCore import QThread, pyqtSignal


class DiaryWorker(QThread):
    """QThread worker for generating diary without blocking the UI."""
    result_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, stats_snap, counts, pet_name, pet_personality, pet_catchphrase, date_str):
        super().__init__()
        self._args = (deepcopy(stats_snap), deepcopy(counts), pet_name,
                      pet_personality, pet_catchphrase, date_str)

    def run(self):
        try:
            text = generate_diary(*self._args)
            if text:
                self.result_ready.emit(text)
            else:
                self.error_occurred.emit("生成失败，请检查 AI 配置与连接后重试。")
        except Exception as e:
            self.error_occurred.emit(f"生成失败: {e}")


def build_diary_prompt(stats_snap, counts, pet_name, pet_personality, pet_catchphrase, date_str):
    """Describe recorded evidence, without inferring an unobserved day's events."""
    # 将日期格式化为可读形式
    try:
        d = datetime.date.fromisoformat(date_str)
        date_readable = f"{d.year}年{d.month}月{d.day}日"
    except Exception:
        date_readable = date_str

    interaction_str = "、".join(
        f"{label} {counts.get(kind, 0)} 次"
        for kind, label in (("feed", "喂食"), ("play", "玩耍"),
                            ("pet", "抚摸"), ("rest", "休息"))
    )
    empty_hint = ""
    if not any(counts.get(kind, 0) for kind in ("feed", "play", "pet", "rest")):
        empty_hint = "当天未记录到这四类互动。可以写当前感受，不要编造互动经历。\n"

    catchphrase_quoted = '\u201c' + pet_catchphrase + '\u201d'
    return (
        f"你是一只名叫{pet_name}的桌面宠物，性格{pet_personality}，"
        f"口头禅是{catchphrase_quoted}。\n"
        f"请为{date_readable}写一条日记（100字以内），用第一人称宠物视角。\n"
        f"本地已记录的当日互动次数（截至点击生成时）：{interaction_str}。\n"
        "仅统计喂食、玩耍、抚摸、休息按钮触发的互动；聊天和自动衰减不计入。"
        "旧版未保存的互动无法补回，未记录不代表没有发生。"
        "不得编造次数、未记录的活动或具体时间，也不要把零记录写成主人没有陪伴。\n"
        f"{empty_hint}"
        f"生成时的当前心情快照：{stats_snap.get('mood_label', '一般')}；"
        "这不是全天心情变化记录。\n"
        f"语气可爱真实，不要太正式，像宠物在自言自语。"
        f"直接输出日记正文，不加标题、不加日期前缀。"
    )


def generate_diary(stats_snap, counts, pet_name, pet_personality, pet_catchphrase, date_str):
    """Generate from a dated snapshot; return text or None on provider failure."""
    prompt = build_diary_prompt(stats_snap, counts, pet_name, pet_personality,
                               pet_catchphrase, date_str)
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
            text = (resp.choices[0].message.content or "").strip()
            return text if text else None
        except Exception:
            return None

    # Claude CLI fallback
    try:
        result = subprocess.run(
            [CLAUDE_CLI, '--print', prompt],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode:
            return None
        text = result.stdout.strip()
        return text if text else None
    except Exception:
        return None
