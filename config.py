"""
config.py — 路径常量、主题字典、全局颜色常量
"""
import os

# ── 文件路径常量 ──────────────────────────────────────
NEWS_SCRIPT       = os.path.expanduser("~/.openclaw/workspace/skills/news-digest/scripts/fetch_news.py")
CACHE_FILE        = os.path.expanduser("~/.openclaw/workspace/desktop-pet/news_cache.json")
NOTE_FILE         = os.path.expanduser("~/.openclaw/workspace/desktop-pet/notes.json")
SETTINGS_FILE     = os.path.expanduser("~/.openclaw/workspace/desktop-pet/settings.json")
BOOKMARKS_FILE    = os.path.expanduser("~/.openclaw/workspace/desktop-pet/bookmarks.json")
USER_PROFILE_FILE    = os.path.expanduser("~/.openclaw/workspace/desktop-pet/user_profile.json")
CHAT_HISTORY_FILE    = os.path.expanduser("~/.openclaw/workspace/desktop-pet/chat_history.json")
PET_STATS_FILE    = os.path.expanduser("~/.openclaw/workspace/desktop-pet/pet_stats.json")
CACHE_TTL         = 30 * 60   # 30 分钟
CLAUDE_CLI        = '/opt/homebrew/bin/claude'

# ── 颜色主题 ──────────────────────────────────────────
THEMES = {
    "dark": {
        "BG_WIN":     "#1a1a1a",
        "BG_SIDEBAR": "#141414",
        "BG_CONTENT": "#1e1e1e",
        "BG_CARD":    "#262626",
        "BG_TOOLBAR": "#141414",
        "BG_HOVER":   "#2e2e2e",
        "BG_SEL":     "#1e3a52",
        "FG_MAIN":    "#e8e8e8",
        "FG_DIM":     "#909090",
        "FG_MUTED":   "#b0b0b0",
        "FG_ACCENT":  "#4fc3f7",
        "FG_GREEN":   "#81c784",
        "FG_YELLOW":  "#ffd54f",
        "FG_RED":     "#ef5350",
        "BORDER":     "#333333",
        "DIVIDER":    "#2a2a2a",
        "BG_BTN":     "#1565c0",
        "ACCENT_BAR": "#4fc3f7",
    },
    "light": {
        "BG_WIN":     "#ffffff",
        "BG_SIDEBAR": "#f5f5f5",
        "BG_CONTENT": "#ffffff",
        "BG_CARD":    "#ffffff",
        "BG_TOOLBAR": "#fafafa",
        "BG_HOVER":   "#f0f7ff",
        "BG_SEL":     "#e3f2fd",
        "FG_MAIN":    "#1a1a1a",
        "FG_DIM":     "#555555",
        "FG_MUTED":   "#888888",
        "FG_ACCENT":  "#0078d4",
        "FG_GREEN":   "#2e7d32",
        "FG_YELLOW":  "#f57f17",
        "FG_RED":     "#c62828",
        "BORDER":     "#e8e8e8",
        "DIVIDER":    "#efefef",
        "BG_BTN":     "#0078d4",
        "ACCENT_BAR": "#0078d4",
    },
}
