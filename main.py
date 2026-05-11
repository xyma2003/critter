#!/usr/bin/env python3
"""
Critter — 合并版桌面宠物（PyQt6 + LangGraph + Critter 功能）
"""
import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from config import Config
from core.pet_window import PetWindow
from core.main_panel import MainPanel
from core.greeting import get_greeting
from core.state_manager import (
    load_window_position, save_window_position,
    load_timer_state, save_timer_state,
    load_theme,
)
from ui.theme import apply_theme
from utils.screen_utils import ScreenUtils


def main():
    if Config.ANTHROPIC_API_KEY:
        os.environ["ANTHROPIC_API_KEY"] = Config.ANTHROPIC_API_KEY

    app = QApplication(sys.argv)
    apply_theme(app, load_theme())

    pet_window = PetWindow()
    main_panel = MainPanel(pet_window)
    pet_window.set_main_panel(main_panel)

    # 恢复窗口位置
    saved_pos = load_window_position()
    if saved_pos:
        sx, sy = saved_pos
        sw, sh = ScreenUtils.get_screen_size()
        pw, ph = Config.PET_SIZE
        sx = max(0, min(sx, sw - pw))
        sy = max(0, min(sy, sh - ph))
        pet_window.move(sx, sy)

    # 恢复定时器
    timer_state = load_timer_state()
    if timer_state and timer_state.get("is_active"):
        try:
            end_dt = datetime.datetime.fromisoformat(timer_state["end_time"])
            remaining = int((end_dt - datetime.datetime.now()).total_seconds())
            if remaining > 0:
                main_panel._timer_feature.countdown.remaining_seconds = remaining
                main_panel._timer_feature.countdown.timer.start(1000)
            else:
                save_timer_state("", is_active=False)
        except Exception:
            pass

    pet_window.show()

    greeting = get_greeting()
    QTimer.singleShot(800, lambda: pet_window.show_bubble(greeting, duration_ms=5000))

    def on_quit():
        pos = pet_window.pos()
        save_window_position(pos.x(), pos.y())

    app.aboutToQuit.connect(on_quit)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
