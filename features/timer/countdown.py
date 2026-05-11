import datetime

from PyQt6.QtCore import QTimer, QObject, pyqtSignal

from core.state_manager import save_timer_state


class CountdownTimer(QObject):
    timeout_signal = pyqtSignal()
    tick_signal = pyqtSignal(int)  # 剩余秒数

    def __init__(self):
        super().__init__()
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_tick)
        self.remaining_seconds = 0

    def start(self, minutes: int):
        self.remaining_seconds = minutes * 60
        self.timer.start(1000)  # 每秒触发一次
        self.tick_signal.emit(self.remaining_seconds)
        end_time = datetime.datetime.now() + datetime.timedelta(seconds=self.remaining_seconds)
        save_timer_state(end_time.isoformat(), is_active=True)

    def _on_tick(self):
        self.remaining_seconds -= 1
        self.tick_signal.emit(self.remaining_seconds)

        if self.remaining_seconds <= 0:
            self.timer.stop()
            self.timeout_signal.emit()
            save_timer_state("", is_active=False)

    def stop(self):
        self.timer.stop()
        self.remaining_seconds = 0
        save_timer_state("", is_active=False)
