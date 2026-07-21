from langchain_core.tools import tool
from typing import Optional
import sys
import os

# 添加父目录到路径，以便导入features
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from features.news_push.news_feature import NewsFeature
from features.timer.timer_feature import TimerFeature


# 全局功能实例（默认实例；MainPanel 启动时会用 set_features 注入真正的实例，
# 这样 AI agent 调用 set_timer 时能正确触发 pet_window 动画）
_news_feature: Optional[NewsFeature] = NewsFeature()
_timer_feature: Optional[TimerFeature] = TimerFeature()


def set_features(news: NewsFeature, timer: TimerFeature) -> None:
    """Inject the live feature instances used by MainPanel.

    Called from MainPanel.__init__ after it sets pet_window_ref on its own
    TimerFeature/NewsFeature instances. Without this, the AI agent's set_timer
    tool would hit a separate TimerFeature whose pet_window_ref is None, so
    the alarm animation would never fire.
    """
    global _news_feature, _timer_feature
    _news_feature = news
    _timer_feature = timer


@tool
def get_news() -> dict:
    """获取今日热点新闻，包括百度热搜、今日头条热榜。

    Returns:
        dict: 包含成功状态、新闻内容和数据的字典
    """
    result = _news_feature.execute()
    return result


@tool
def set_timer(minutes: int = 10) -> dict:
    """设置倒计时闹钟。时间到了会触发边牧放大并全屏跑动提醒。

    Args:
        minutes: 倒计时的分钟数，默认10分钟

    Returns:
        dict: 包含成功状态和消息的字典
    """
    return _timer_feature.execute(minutes=minutes)


def get_all_tools():
    """返回所有可用的工具列表"""
    return [get_news, set_timer]


def get_timer_feature():
    """获取timer feature实例，用于设置pet_window引用"""
    return _timer_feature
