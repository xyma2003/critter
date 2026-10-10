"""Keep normal Qt quit requests reviewable before the event loop exits."""

from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QApplication


class CritterApplication(QApplication):
    def __init__(self, args):
        super().__init__(args)
        self.confirm_exit = None
        self._checking_exit = False

    def event(self, event):
        if event.type() == QEvent.Type.Quit and self.confirm_exit is not None:
            if self._checking_exit:
                event.ignore()
                return True
            self._checking_exit = True
            try:
                allowed = self.confirm_exit()
            finally:
                self._checking_exit = False
            if not allowed:
                event.ignore()
                return True
        return super().event(event)
