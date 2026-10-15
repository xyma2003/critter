from enum import Enum
from PyQt6.QtCore import QObject, QTimer
import random


class AnimationState(Enum):
    IDLE_SLEEP = "idle_sleep"
    IDLE_WALK = "idle_walk"
    INTERACT_WASH = "interact_wash"
    INTERACT_WAG = "interact_wag"
    ALERT_RUN = "alert_run"


class AnimationManager(QObject):
    INTERACTION_DURATION_MS = 2000
    IDLE_STATES = (AnimationState.IDLE_SLEEP, AnimationState.IDLE_WALK)
    INTERACTION_STATES = (AnimationState.INTERACT_WASH, AnimationState.INTERACT_WAG)

    def __init__(self, pet_window):
        super().__init__(pet_window if isinstance(pet_window, QObject) else None)
        self.pet_window = pet_window
        self.current_state = AnimationState.IDLE_SLEEP
        self._stopped = False
        self.state_timer = QTimer(self)
        self.state_timer.timeout.connect(self._switch_idle_state)
        # Reuse one timer: another click extends this interaction instead of
        # leaving an earlier singleShot callback that can end it prematurely.
        self.interaction_timer = QTimer(self)
        self.interaction_timer.setSingleShot(True)
        self.interaction_timer.timeout.connect(self._finish_interaction)

    def start(self):
        from config import Config
        self._stopped = False
        self.state_timer.start(Config.IDLE_STATE_SWITCH_INTERVAL * 1000)

    def stop(self):
        self._stopped = True
        self.state_timer.stop()
        self.interaction_timer.stop()

    def _switch_idle_state(self):
        if (self._stopped or self.current_state not in self.IDLE_STATES
                or self.interaction_timer.isActive()):
            return
        self.set_state(random.choice(self.IDLE_STATES))

    def _apply_state(self, state):
        if self.current_state != state:
            self.current_state = state
            self.pet_window.update_animation(state)

    def set_state(self, state: AnimationState):
        if not isinstance(state, AnimationState):
            raise TypeError("动画状态必须是 AnimationState")
        if self._stopped:
            return
        # An alarm stays visible until explicitly dismissed. Neither an idle
        # tick nor a pet interaction can replace it.
        if self.current_state == AnimationState.ALERT_RUN and state != AnimationState.ALERT_RUN:
            return
        if state == AnimationState.ALERT_RUN:
            self.interaction_timer.stop()
        self._apply_state(state)

    def trigger_interact(self, state: AnimationState | None = None):
        """Show a brief reaction, optionally chosen by a panel action."""
        if self._stopped or self.current_state == AnimationState.ALERT_RUN:
            return
        if state is None:
            state = random.choice(self.INTERACTION_STATES)
        if state not in (*self.IDLE_STATES, *self.INTERACTION_STATES):
            raise ValueError("短暂互动只能使用休息、走动、洗脸或摇尾巴状态")
        self.set_state(state)
        self.interaction_timer.start(self.INTERACTION_DURATION_MS)

    def _finish_interaction(self):
        if not self._stopped and self.current_state != AnimationState.ALERT_RUN:
            self.set_state(AnimationState.IDLE_SLEEP)

    def trigger_alert(self):
        self.set_state(AnimationState.ALERT_RUN)

    def stop_alert(self):
        """Dismiss the alarm explicitly and return to the resting animation."""
        if not self._stopped and self.current_state == AnimationState.ALERT_RUN:
            self.interaction_timer.stop()
            self._apply_state(AnimationState.IDLE_SLEEP)
