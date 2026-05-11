from PyQt6.QtWidgets import QPushButton


class FeatureButton(QPushButton):
    """功能按钮 — 自动继承全局 QSS 主题，无硬编码颜色"""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setMinimumHeight(40)
