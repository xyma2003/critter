from PyQt6.QtCore import Qt, QPoint


class EventHandler:
    def __init__(self, pet_window):
        self.pet_window = pet_window
        self.drag_position = QPoint()

    def handle_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.pet_window.frameGeometry().topLeft()

    def handle_mouse_move(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.pet_window.move(event.globalPosition().toPoint() - self.drag_position)
            # Sync speech bubble position if visible
            if hasattr(self.pet_window, 'speech_bubble') and self.pet_window.speech_bubble.isVisible():
                self.pet_window.speech_bubble.reposition_to(self.pet_window)

    def handle_single_click(self):
        """单击：触发交互动画"""
        self.pet_window.animation_manager.trigger_interact()
