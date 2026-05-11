from PyQt6.QtWidgets import QApplication


class ScreenUtils:
    @staticmethod
    def get_screen_size():
        screen = QApplication.primaryScreen()
        geometry = screen.geometry()
        return geometry.width(), geometry.height()

    @staticmethod
    def is_position_in_screen(x: int, y: int, width: int, height: int) -> bool:
        screen_width, screen_height = ScreenUtils.get_screen_size()
        return 0 <= x <= screen_width - width and 0 <= y <= screen_height - height
