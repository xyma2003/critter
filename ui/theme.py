"""
ui/theme.py — PyQt6 全局主题 stylesheet
替代 Critter 的 THEMES dict + tkinter canvas 颜色遍历
"""
from PyQt6.QtWidgets import QApplication

LIGHT_QSS = """
QWidget {
    background-color: #ffffff;
    color: #1a1a1a;
    font-family: "PingFang SC", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog {
    background-color: #f5f5f5;
}
/* 左侧导航栏 */
QWidget#nav_bar {
    background-color: #f5f5f5;
    border-right: 1px solid #e8e8e8;
}
QPushButton#nav_btn {
    background-color: transparent;
    color: #555555;
    border: none;
    border-radius: 8px;
    padding: 8px 4px;
    font-size: 11px;
    text-align: center;
}
QPushButton#nav_btn:hover {
    background-color: #f0f7ff;
    color: #0078d4;
}
QPushButton#nav_btn:checked {
    background-color: #e3f2fd;
    color: #0078d4;
    font-weight: bold;
}
/* 内容区 */
QWidget#content_area {
    background-color: #ffffff;
}
/* 卡片 */
QFrame#card {
    background-color: #ffffff;
    border: 1px solid #e8e8e8;
    border-radius: 8px;
}
/* 输入框 */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #e8e8e8;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #e3f2fd;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #0078d4;
}
/* 按钮 */
QPushButton {
    background-color: #0078d4;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #106ebe;
}
QPushButton:pressed {
    background-color: #005a9e;
}
QPushButton#secondary_btn {
    background-color: #f5f5f5;
    color: #1a1a1a;
    border: 1px solid #e8e8e8;
}
QPushButton#secondary_btn:hover {
    background-color: #f0f7ff;
    border-color: #0078d4;
    color: #0078d4;
}
/* 滚动条 */
QScrollBar:vertical {
    background: #f5f5f5;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #d0d0d0;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
/* 标签 */
QLabel#title {
    font-size: 16px;
    font-weight: bold;
    color: #1a1a1a;
}
QLabel#subtitle {
    font-size: 12px;
    color: #888888;
}
QLabel#accent {
    color: #0078d4;
}
/* 进度条 */
QProgressBar {
    background-color: #e8e8e8;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #0078d4;
    border-radius: 4px;
}
/* 分隔线 */
QFrame[frameShape="4"], QFrame[frameShape="5"] {
    color: #efefef;
}
/* 工具栏区域 */
QWidget#toolbar {
    background-color: #fafafa;
    border-bottom: 1px solid #e8e8e8;
}
"""

DARK_QSS = """
QWidget {
    background-color: #1e1e1e;
    color: #e8e8e8;
    font-family: "PingFang SC", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog {
    background-color: #1a1a1a;
}
QWidget#nav_bar {
    background-color: #141414;
    border-right: 1px solid #333333;
}
QPushButton#nav_btn {
    background-color: transparent;
    color: #909090;
    border: none;
    border-radius: 8px;
    padding: 8px 4px;
    font-size: 11px;
    text-align: center;
}
QPushButton#nav_btn:hover {
    background-color: #2e2e2e;
    color: #4fc3f7;
}
QPushButton#nav_btn:checked {
    background-color: #1e3a52;
    color: #4fc3f7;
    font-weight: bold;
}
QWidget#content_area {
    background-color: #1e1e1e;
}
QFrame#card {
    background-color: #262626;
    border: 1px solid #333333;
    border-radius: 8px;
}
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #262626;
    color: #e8e8e8;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #1e3a52;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #4fc3f7;
}
QPushButton {
    background-color: #1565c0;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #1976d2;
}
QPushButton:pressed {
    background-color: #0d47a1;
}
QPushButton#secondary_btn {
    background-color: #262626;
    color: #e8e8e8;
    border: 1px solid #333333;
}
QPushButton#secondary_btn:hover {
    background-color: #2e2e2e;
    border-color: #4fc3f7;
    color: #4fc3f7;
}
QScrollBar:vertical {
    background: #1e1e1e;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #444444;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QLabel#title {
    font-size: 16px;
    font-weight: bold;
    color: #e8e8e8;
}
QLabel#subtitle {
    font-size: 12px;
    color: #909090;
}
QLabel#accent {
    color: #4fc3f7;
}
QProgressBar {
    background-color: #333333;
    border-radius: 4px;
    height: 8px;
}
QProgressBar::chunk {
    background-color: #4fc3f7;
    border-radius: 4px;
}
QFrame[frameShape="4"], QFrame[frameShape="5"] {
    color: #2a2a2a;
}
QWidget#toolbar {
    background-color: #141414;
    border-bottom: 1px solid #2a2a2a;
}
"""


def apply_theme(app: QApplication, mode: str) -> None:
    """应用全局主题 stylesheet。mode: 'light' | 'dark'"""
    qss = DARK_QSS if mode == "dark" else LIGHT_QSS
    app.setStyleSheet(qss)
