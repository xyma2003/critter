#!/usr/bin/env python3
"""
Critter — 合并版桌面宠物（PyQt6 + LangGraph + Critter 功能）
"""
import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import QTimer, Qt

from config import Config
from core.application import CritterApplication
from core.pet_window import PetWindow
from core.main_panel import MainPanel
from core.greeting import get_greeting
from core.state_manager import (
    load_window_position, save_fields,
    load_timer_state, save_timer_state,
    load_theme,
    initialize_storage, get_storage_status, retry_pending_saves, acknowledge_recovery,
)
from ui.theme import apply_theme
from utils.screen_utils import ScreenUtils


def main():
    if Config.ANTHROPIC_API_KEY:
        os.environ["ANTHROPIC_API_KEY"] = Config.ANTHROPIC_API_KEY

    app = CritterApplication(sys.argv)
    # Do not build the panel (which writes a welcome message) before an
    # existing file has been read or safely backed up.
    while not initialize_storage():
        status = get_storage_status()
        dialog = QMessageBox(QMessageBox.Icon.Critical, "无法打开本地数据", "")
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.setText("现有数据暂时无法读取，Critter 尚未启动，也没有覆盖原文件。\n"
                       "请检查文件与目录权限，再重试。")
        dialog.setDetailedText(f"数据文件：{status.path}\n{status.error}")
        dialog.setStandardButtons(QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Close)
        dialog.setDefaultButton(QMessageBox.StandardButton.Close)
        if dialog.exec() != QMessageBox.StandardButton.Retry:
            return 1
    app.setQuitOnLastWindowClosed(False)
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

    def confirm_recovery_before_exit():
        status = get_storage_status()
        if status.recovery_backup:
            # Corruption can first be discovered during the final write, before
            # the panel's periodic notice has had a chance to show it.
            dialog = QMessageBox(QMessageBox.Icon.Warning, "已保留损坏数据的备份", "", parent=main_panel)
            dialog.setTextFormat(Qt.TextFormat.PlainText)
            recovery = ("继续使用本次会话中最后读到的数据；损坏文件中的其他内容未恢复。"
                        if status.recovered_from_memory else "原内容未恢复，应用从空状态继续。")
            dialog.setText("发现损坏的本地数据，已保留原始备份。" + recovery + "\n"
                           f"备份位置：{status.recovery_backup}")
            proceed = dialog.addButton("我已知悉，继续退出", QMessageBox.ButtonRole.AcceptRole)
            cancel = dialog.addButton("返回应用", QMessageBox.ButtonRole.RejectRole)
            dialog.setDefaultButton(cancel)
            dialog.setEscapeButton(cancel)
            dialog.exec()
            if dialog.clickedButton() is not proceed:
                main_panel.show()
                return False
            acknowledge_recovery()
        return True

    def confirm_exit():
        pos = pet_window.pos()
        saved = save_fields({
            "window_position": {"x": pos.x(), "y": pos.y()},
            "last_seen": datetime.datetime.now().isoformat(),
        })
        if saved:
            return confirm_recovery_before_exit()
        while True:
            status = get_storage_status()
            dialog = QMessageBox(QMessageBox.Icon.Warning, "还有更改尚未保存", "", parent=main_panel)
            dialog.setTextFormat(Qt.TextFormat.PlainText)
            dialog.setText("部分修改只保留在当前会话。现在退出会丢失这些修改；上次保存的数据仍在。")
            dialog.setDetailedText(f"数据文件：{status.path}\n未保存字段：{', '.join(status.pending_fields)}\n{status.error}")
            retry = dialog.addButton("重试保存", QMessageBox.ButtonRole.AcceptRole)
            discard = dialog.addButton("不保存并退出", QMessageBox.ButtonRole.DestructiveRole)
            cancel = dialog.addButton("取消退出", QMessageBox.ButtonRole.RejectRole)
            dialog.setDefaultButton(cancel)
            dialog.setEscapeButton(cancel)
            dialog.exec()
            if dialog.clickedButton() is discard:
                return confirm_recovery_before_exit()
            if dialog.clickedButton() is not retry:
                return False
            if retry_pending_saves():
                return confirm_recovery_before_exit()

    app.confirm_exit = confirm_exit
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
