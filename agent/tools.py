from langchain_core.tools import tool
from typing import Optional
import sys
import os

# 添加父目录到路径，以便导入features
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from features.news_push.news_feature import NewsFeature
from features.timer.timer_feature import TimerFeature


# 全局功能实例
_news_feature = NewsFeature()
_timer_feature = TimerFeature()


@tool
def get_news() -> dict:
    """获取今日热点新闻，包括百度热搜、微博热搜、Google热搜。
    
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
