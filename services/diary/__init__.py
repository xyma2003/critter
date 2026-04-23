"""
services/diary — 宠物日记生成服务
调用 Claude CLI 生成当日宠物视角日记，返回纯文本。
"""
import subprocess
import datetime
from config import CLAUDE_CLI


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
        f"你是一只名叫{pet_name}的桌面小猫，性格{pet_personality}，"
        f"口头禅是{catchphrase_quoted}。\n"
        f"今天是{date_readable}，写一条今天的日记（100字以内），"
        f"用第一人称猫咪视角，内容基于：{interaction_str}。"
        f"当前心情状态：{stats_snap.get('mood_label', '一般')}。\n"
        f"语气可爱真实，不要太正式，像猫咪在自言自语。"
        f"直接输出日记正文，不加标题、不加日期前缀。"
    )

    try:
        result = subprocess.run(
            [CLAUDE_CLI, '--print', prompt],
            capture_output=True, text=True, timeout=30
        )
        text = result.stdout.strip()
        return text if text else None
    except Exception:
        return None
