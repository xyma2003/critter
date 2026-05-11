from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseFeature(ABC):
    @abstractmethod
    def get_name(self) -> str:
        """返回功能的唯一标识名称"""
        pass

    @abstractmethod
    def get_button_text(self) -> str:
        """返回主页按钮上显示的文本"""
        pass

    @abstractmethod
    def execute(self) -> dict:
        """
        执行功能逻辑
        返回格式: {
            'success': bool,
            'message': str,  # 显示在对话列表中的消息
            'data': Any,  # 可选，额外数据
        }
        """
        pass

    def on_result(self, result: dict, pet_window: Optional[Any] = None):
        """
        处理执行结果的回调（可选）
        用于触发特殊效果，如闹钟触发宠物动画
        :param result: execute()返回的结果
        :param pet_window: 宠物窗口实例，用于触发动画
        """
        pass
