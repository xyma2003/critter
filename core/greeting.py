import datetime
import random

from core.state_manager import _load_state, _save_state


def save_last_seen():
    """记录本次关闭时间，在应用退出时调用"""
    state = _load_state()
    state["last_seen"] = datetime.datetime.now().isoformat()
    _save_state(state)


def get_greeting() -> str:
    """
    根据当前时间段和上次关闭时间，返回合适的问候语。
    优先级：久别重逢 > 时间段问候
    """
    state = _load_state()
    now = datetime.datetime.now()

    # --- 久别重逢判断 ---
    last_seen_str = state.get("last_seen")
    if last_seen_str:
        try:
            last_seen = datetime.datetime.fromisoformat(last_seen_str)
            diff = now - last_seen
            if diff.days >= 7:
                return random.choice([
                    f"好久不见！都过了 {diff.days} 天了，你还记得我吗？",
                    f"哇，{diff.days} 天没见啦！我好想你~ 🐾",
                ])
            elif diff.days >= 1:
                return random.choice([
                    f"欢迎回来！昨天你离开后我一直等你呢 🐕",
                    f"你回来啦！已经 {diff.days} 天没见了，今天过得怎么样？",
                ])
            elif diff.seconds >= 4 * 3600:
                return random.choice([
                    "你终于回来了！我等了好久 🐾",
                    "欢迎回来！休息够了吗？",
                ])
        except Exception:
            pass

    # --- 时间段问候 ---
    hour = now.hour
    if 5 <= hour < 9:
        return random.choice([
            "早安！今天也要元气满满哦~ ☀️",
            "早上好！起这么早，辛苦了 🐾",
        ])
    elif 9 <= hour < 12:
        return random.choice([
            "上午好！今天的任务准备好了吗？",
            "工作顺利！有什么需要帮忙的尽管说 🐕",
        ])
    elif 12 <= hour < 14:
        return random.choice([
            "中午好！记得吃饭休息哦 🍱",
            "午饭时间到了，先去吃饭吧~",
        ])
    elif 14 <= hour < 18:
        return random.choice([
            "下午好！下午茶时间到了 ☕",
            "继续加油！有我陪着你 🐾",
        ])
    elif 18 <= hour < 21:
        return random.choice([
            "晚上好！今天辛苦了 🌙",
            "下班了吗？好好放松一下吧~",
        ])
    else:
        return random.choice([
            "这么晚还没睡？注意休息哦 🌙",
            "夜深了，早点休息，我也要打盹了 💤",
        ])
