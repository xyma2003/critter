"""Shared cream and sage theme for the Critter desktop app."""
from PyQt6.QtWidgets import QApplication


LIGHT = {
    "bg": "#F7F6F2", "bg_nav": "#EFEFE7", "bg_card": "#FFFFFF",
    "bg_toolbar": "#F7F6F2", "bg_hover": "#E8ECE2", "bg_sel": "#E1E8D9",
    "fg_main": "#263229", "fg_dim": "#626B61", "fg_muted": "#6B7269",
    "accent": "#52684A", "accent_dark": "#3E5238", "accent_light": "#E1E8D9",
    "text_accent": "#FFFFFF", "border": "#DDE1D7", "divider": "#E6E8DF",
    "bubble_user": "#52684A", "bubble_pet": "#FFFFFF",
    "text_user": "#FFFFFF", "text_pet": "#263229",
    "green": "#46703D", "red": "#A9423B",
}

DARK = {
    "bg": "#202620", "bg_nav": "#1A211B", "bg_card": "#2A332B",
    "bg_toolbar": "#202620", "bg_hover": "#354236", "bg_sel": "#3B4B38",
    "fg_main": "#EDF1E9", "fg_dim": "#BEC8B9", "fg_muted": "#A7B39F",
    "accent": "#B6CDA5", "accent_dark": "#CCDCBE", "accent_light": "#3B4B38",
    "text_accent": "#202B1B", "border": "#455242", "divider": "#374234",
    "bubble_user": "#B6CDA5", "bubble_pet": "#2A332B",
    "text_user": "#202B1B", "text_pet": "#EDF1E9",
    "green": "#B6CDA5", "red": "#F2A39C",
}

_CURRENT = LIGHT


def current() -> dict:
    return _CURRENT


def _make_qss(c: dict) -> str:
    return f"""
QWidget {{
    background-color: {c['bg']};
    color: {c['fg_main']};
    font-family: "PingFang SC", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog, QWidget#content_area {{ background-color: {c['bg']}; }}
QLabel {{ background-color: transparent; border: none; }}

/* App identity and navigation */
QWidget#nav_bar {{
    background-color: {c['bg_nav']};
    border-right: 1px solid {c['border']};
}}
QLabel#brand {{ font-size: 24px; font-weight: 700; }}
QLabel#nav_caption {{ font-size: 11px; color: {c['fg_muted']}; }}
QWidget#pet_identity {{
    background-color: {c['bg_card']};
    border: 1px solid {c['border']};
    border-radius: 14px;
}}
QLabel#pet_avatar {{ font-size: 36px; }}
QLabel#pet_name {{ font-size: 16px; font-weight: 600; }}
QPushButton#nav_btn {{
    background-color: transparent;
    color: {c['fg_dim']};
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 8px 14px;
    font-size: 13px;
    font-weight: 500;
    text-align: left;
}}
QPushButton#nav_btn:hover {{ background-color: {c['bg_hover']}; color: {c['fg_main']}; }}
QPushButton#nav_btn:checked {{
    background-color: {c['bg_sel']};
    color: {c['accent']};
    font-weight: 600;
}}
QPushButton#nav_btn:focus {{ border-color: {c['accent']}; }}

/* Consistent page and card surfaces */
QWidget#toolbar {{
    background-color: {c['bg_toolbar']};
    border-bottom: 1px solid {c['divider']};
}}
QFrame#card, QFrame#intro_card {{
    background-color: {c['bg_card']};
    border: 1px solid {c['border']};
    border-radius: 14px;
}}
QFrame#intro_card {{ background-color: {c['accent_light']}; }}
QLabel#title {{ font-size: 22px; font-weight: 600; }}
QLabel#section_title {{ font-size: 15px; font-weight: 600; }}
QLabel#subtitle {{ font-size: 12px; color: {c['fg_muted']}; }}
QLabel#status_label {{ font-size: 12px; color: {c['fg_dim']}; }}
QLabel#accent {{ color: {c['accent']}; font-weight: 600; }}

/* Inputs and actions */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {c['bg_card']};
    color: {c['fg_main']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    padding: 10px 12px;
    selection-background-color: {c['accent']};
    selection-color: {c['text_accent']};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border-color: {c['accent']}; }}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
    background-color: {c['bg_nav']};
    color: {c['fg_muted']};
}}
QPushButton {{
    background-color: {c['accent']};
    color: {c['text_accent']};
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 9px 16px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton:hover, QPushButton:pressed {{ background-color: {c['accent_dark']}; }}
QPushButton:focus {{ border-color: {c['fg_main']}; }}
QPushButton:disabled {{ background-color: {c['border']}; color: {c['fg_muted']}; }}
QPushButton#secondary_btn {{
    background-color: {c['bg_card']};
    color: {c['fg_main']};
    border: 1px solid {c['border']};
    padding: 8px 14px;
    font-weight: 500;
}}
QPushButton#secondary_btn:hover, QPushButton#secondary_btn:checked {{
    background-color: {c['bg_sel']};
    border-color: {c['accent']};
    color: {c['accent']};
}}
QPushButton#secondary_btn:focus {{ border-color: {c['accent']}; }}
QPushButton#secondary_btn:disabled {{
    background-color: {c['bg_nav']};
    color: {c['fg_muted']};
    border-color: {c['border']};
}}

/* Message colors remain owned by the active application theme. */
QScrollArea#chat_list, QWidget#chat_container, QWidget#chat_bubble_row {{
    background-color: transparent;
    border: none;
}}
QLabel#chat_bubble {{
    background-color: {c['bubble_pet']};
    color: {c['text_pet']};
    border: 1px solid {c['border']};
    border-radius: 14px;
    padding: 12px 16px;
    font-size: 14px;
}}
QLabel#chat_bubble[role="user"] {{
    background-color: {c['bubble_user']};
    color: {c['text_user']};
    border-color: {c['bubble_user']};
}}

/* Scrollbars and supporting controls */
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 7px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {c['border']};
    border-radius: 3px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: {c['fg_muted']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 7px; }}
QScrollBar::handle:horizontal {{
    background: {c['border']};
    border-radius: 3px;
    min-width: 28px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}
QProgressBar {{
    background-color: {c['bg_hover']};
    color: {c['fg_main']};
    border: none;
    border-radius: 5px;
    height: 10px;
    text-align: center;
}}
QProgressBar::chunk {{ background-color: {c['accent']}; border-radius: 5px; }}
QFrame[frameShape="4"], QFrame[frameShape="5"] {{ color: {c['divider']}; }}
QMenu {{
    background-color: {c['bg_card']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    padding: 5px;
}}
QMenu::item {{ padding: 8px 20px; border-radius: 6px; color: {c['fg_main']}; }}
QMenu::item:selected {{ background-color: {c['bg_hover']}; color: {c['accent']}; }}
QMenu::separator {{ height: 1px; background: {c['divider']}; margin: 4px 8px; }}
QDialogButtonBox QPushButton {{ min-width: 80px; }}
QToolTip {{
    background-color: {c['bg_card']};
    color: {c['fg_main']};
    border: 1px solid {c['border']};
    padding: 6px 8px;
}}
"""


def apply_theme(app: QApplication, mode: str) -> None:
    """Apply the shared palette, including existing chat bubbles."""
    global _CURRENT
    _CURRENT = DARK if mode == "dark" else LIGHT
    app.setStyleSheet(_make_qss(_CURRENT))
