from PyQt6.QtCore import QTimer, QPoint


class EventHandler:
    def __init__(self, pet_window):
        self.pet_window = pet_window
        self.drag_position = QPoint()
        self.click_timer = QTimer()
        self.click_timer.setSingleShot(True)
        self.click_timer.timeout.connect(self._on_single_click)
        self.click_count = 0

    def handle_mouse_press(self, event):
        if event.button() == 1:  # 左键
            self.drag_position = event.globalPosition().toPoint() - self.pet_window.frameGeometry().topLeft()
            self.click_count += 1

            if self.click_count == 1:
                # 启动单击定时器
                self.click_timer.start(300)
            elif self.click_count == 2:
                # 双击
                self.click_timer.stop()
                self.click_count = 0
                self._on_double_click()

    def handle_mouse_move(self, event):
        if event.buttons() == 1:  # 左键拖动
            self.pet_window.move(event.globalPosition().toPoint() - self.drag_position)

    def _on_single_click(self):
        if self.click_count == 1:
            # 触发交互动画
            self.pet_window.animation_manager.trigger_interact()
        self.click_count = 0

    def _on_double_click(self):
        # 显示主面板
        self.pet_window.show_main_panel()
