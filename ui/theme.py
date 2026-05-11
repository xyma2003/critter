"""
ui/theme.py — 可爱温暖风格 PyQt6 全局主题
"""
from PyQt6.QtWidgets import QApplication

# ── 颜色常量（供其他组件直接引用）────────────────────────
LIGHT = {
    "bg":          "#FFF8F0",
    "bg_nav":      "#FFF0E0",
    "bg_card":     "#FFFFFF",
    "bg_toolbar":  "#FFF4E8",
    "bg_hover":    "#FFE8D0",
    "bg_sel":      "#FFD8B0",
    "fg_main":     "#3D2B1F",
    "fg_dim":      "#8C6E5A",
    "fg_muted":    "#B8967E",
    "accent":      "#FF8C42",
    "accent_dark": "#E07020",
    "accent_light":"#FFD0A0",
    "border":      "#F0D8C0",
    "divider":     "#F5E8D8",
    "bubble_user": "#FF8C42",
    "bubble_pet":  "#FFFFFF",
    "text_user":   "#FFFFFF",
    "text_pet":    "#3D2B1F",
    "green":       "#5B9E6A",
    "red":         "#D95B5B",
}

DARK = {
    "bg":          "#2A2420",
    "bg_nav":      "#221E1A",
    "bg_card":     "#352E28",
    "bg_toolbar":  "#221E1A",
    "bg_hover":    "#3D3530",
    "bg_sel":      "#4A3C34",
    "fg_main":     "#F5E8DC",
    "fg_dim":      "#C0A090",
    "fg_muted":    "#907060",
    "accent":      "#FF9A55",
    "accent_dark": "#E07535",
    "accent_light":"#5A3820",
    "border":      "#4A3C30",
    "divider":     "#3A3028",
    "bubble_user": "#E07535",
    "bubble_pet":  "#3D3530",
    "text_user":   "#FFFFFF",
    "text_pet":    "#F5E8DC",
    "green":       "#6DB87A",
    "red":         "#E07070",
}

_CURRENT = LIGHT


def current() -> dict:
    return _CURRENT


def _make_qss(c: dict) -> str:
    return f"""
/* ── 基础 ── */
QWidget {{
    background-color: {c['bg']};
    color: {c['fg_main']};
    font-family: "PingFang SC", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog {{
    background-color: {c['bg']};
}}

/* ── 导航栏 ── */
QWidget#nav_bar {{
    background-color: {c['bg_nav']};
    border-right: 1px solid {c['border']};
}}
QPushButton#nav_btn {{
    background-color: transparent;
    color: {c['fg_dim']};
    border: none;
    border-radius: 10px;
    padding: 6px 4px;
    font-size: 11px;
    text-align: center;
}}
QPushButton#nav_btn:hover {{
    background-color: {c['bg_hover']};
    color: {c['accent']};
}}
QPushButton#nav_btn:checked {{
    background-color: {c['bg_sel']};
    color: {c['accent']};
    font-weight: bold;
}}

/* ── 内容区 ── */
QWidget#content_area {{
    background-color: {c['bg']};
}}

/* ── 工具栏 ── */
QWidget#toolbar {{
    background-color: {c['bg_toolbar']};
    border-bottom: 1px solid {c['border']};
}}

/* ── 卡片 ── */
QFrame#card {{
    background-color: {c['bg_card']};
    border: 1px solid {c['border']};
    border-radius: 12px;
}}
QFrame#card:hover {{
    border-color: {c['accent_light']};
}}

/* ── 输入框 ── */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {c['bg_card']};
    color: {c['fg_main']};
    border: 1.5px solid {c['border']};
    border-radius: 8px;
    padding: 8px 12px;
    selection-background-color: {c['accent_light']};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {c['accent']};
    background-color: {c['bg_card']};
}}

/* ── 主要按钮 ── */
QPushButton {{
    background-color: {c['accent']};
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {c['accent_dark']};
}}
QPushButton:pressed {{
    background-color: {c['accent_dark']};
    padding: 9px 15px 7px 17px;
}}
QPushButton:disabled {{
    background-color: {c['border']};
    color: {c['fg_muted']};
}}

/* ── 次要按钮 ── */
QPushButton#secondary_btn {{
    background-color: {c['bg_card']};
    color: {c['fg_dim']};
    border: 1.5px solid {c['border']};
    border-radius: 8px;
    padding: 6px 14px;
}}
QPushButton#secondary_btn:hover {{
    background-color: {c['bg_hover']};
    border-color: {c['accent']};
    color: {c['accent']};
}}

/* ── 滚动条 ── */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {c['border']};
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c['accent_light']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    height: 6px;
}}
QScrollBar::handle:horizontal {{
    background: {c['border']};
    border-radius: 3px;
}}

/* ── 标签层级 ── */
QLabel#title {{
    font-size: 16px;
    font-weight: 600;
    color: {c['fg_main']};
}}
QLabel#subtitle {{
    font-size: 12px;
    color: {c['fg_muted']};
}}
QLabel#accent {{
    color: {c['accent']};
    font-weight: 500;
}}

/* ── 进度条 ── */
QProgressBar {{
    background-color: {c['bg_hover']};
    border: none;
    border-radius: 5px;
    height: 10px;
    text-align: center;
    font-size: 0px;
}}
QProgressBar::chunk {{
    background-color: {c['accent']};
    border-radius: 5px;
}}

/* ── 分隔线 ── */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    color: {c['divider']};
}}

/* ── 菜单 ── */
QMenu {{
    background-color: {c['bg_card']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 8px 20px;
    border-radius: 6px;
    color: {c['fg_main']};
}}
QMenu::item:selected {{
    background-color: {c['bg_hover']};
    color: {c['accent']};
}}
QMenu::separator {{
    height: 1px;
    background: {c['divider']};
    margin: 4px 8px;
}}

/* ── 对话框 ── */
QDialog {{
    background-color: {c['bg']};
    border-radius: 12px;
}}
QDialogButtonBox QPushButton {{
    min-width: 80px;
}}
"""


def apply_theme(app: QApplication, mode: str) -> None:
    """应用全局主题。mode: 'light' | 'dark'"""
    global _CURRENT
    _CURRENT = DARK if mode == "dark" else LIGHT
    app.setStyleSheet(_make_qss(_CURRENT))
