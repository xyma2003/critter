from enum import Enum
from PyQt6.QtCore import QTimer
import random


class AnimationState(Enum):
    IDLE_SLEEP = "idle_sleep"
    IDLE_WALK = "idle_walk"
    INTERACT_WASH = "interact_wash"
    INTERACT_WAG = "interact_wag"
    ALERT_RUN = "alert_run"


class AnimationManager:
    def __init__(self, pet_window):
        self.pet_window = pet_window
        self.current_state = AnimationState.IDLE_SLEEP
        self.state_timer = QTimer()
        self.state_timer.timeout.connect(self._switch_idle_state)

    def start(self):
        from config import Config
        self.state_timer.start(Config.IDLE_STATE_SWITCH_INTERVAL * 1000)

    def stop(self):
        self.state_timer.stop()

    def _switch_idle_state(self):
        # 在空闲状态之间随机切换
        idle_states = [AnimationState.IDLE_SLEEP, AnimationState.IDLE_WALK]
        new_state = random.choice(idle_states)
        self.set_state(new_state)

    def set_state(self, state: AnimationState):
        self.current_state = state
        self.pet_window.update_animation(state)

    def trigger_interact(self):
        # 单击触发交互动画
        interact_states = [AnimationState.INTERACT_WASH, AnimationState.INTERACT_WAG]
        interact_state = random.choice(interact_states)
        self.set_state(interact_state)

        # 2秒后返回空闲状态
        QTimer.singleShot(2000, lambda: self.set_state(AnimationState.IDLE_SLEEP))

    def trigger_alert(self):
        # 闹钟触发警报动画
        self.set_state(AnimationState.ALERT_RUN)
