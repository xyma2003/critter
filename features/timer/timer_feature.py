from features.base_feature import BaseFeature
from .countdown import CountdownTimer
from config import Config


class TimerFeature(BaseFeature):
    def __init__(self):
        self.countdown = CountdownTimer()
        self.countdown.timeout_signal.connect(self._on_timeout)
        self.pet_window_ref = None

    def get_name(self) -> str:
        return "timer"

    def get_button_text(self) -> str:
        return f"定一个{Config.DEFAULT_TIMER_MINUTES}分钟的闹钟"

    def execute(self, minutes: int = None) -> dict:
        minutes = minutes if minutes is not None else Config.DEFAULT_TIMER_MINUTES
        self.countdown.start(minutes)
        return {
            'success': True,
            'message': f'已设置{minutes}分钟倒计时，时间到了我会提醒你！',
            'data': {'minutes': minutes}
        }

    def _on_timeout(self):
        # 闹钟时间到，触发宠物动画
        if self.pet_window_ref:
            self.pet_window_ref.trigger_alert_animation()

    def on_result(self, result: dict, pet_window=None):
        # 保存宠物窗口引用
        self.pet_window_ref = pet_window
