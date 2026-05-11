"""
config.py — 合并版配置（PyQt6 + LangGraph + Critter 功能）
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── 文件路径 ──────────────────────────────────────────────
_BASE = os.path.expanduser("~/.openclaw/workspace/desktop-pet")

STATE_FILE        = os.path.expanduser("~/.desktop-pet-state.json")
PET_AVATAR_FILE   = os.path.join(_BASE, "data", "pet_avatar.png")
DIARY_COUNTS_FILE = os.path.join(_BASE, "diary_counts.json")
PET_LOG_FILE      = os.path.join(_BASE, "pet_log.json")
CLAUDE_CLI        = '/opt/homebrew/bin/claude'

# ── PyQt6 宠物 & 动画 ─────────────────────────────────────
class Config:
    # 宠物外观
    DEFAULT_PET             = "border_collie"
    PET_SIZE                = (150, 150)
    PET_SCALE_ALERT         = 2.0

    # 动画
    IDLE_STATE_SWITCH_INTERVAL = 30   # 秒
    ANIMATION_FPS           = 30
    ALERT_RUN_SPEED         = 15      # 像素/帧

    # 主面板
    MAIN_PANEL_WIDTH        = 900
    MAIN_PANEL_HEIGHT       = 700

    # AI
    ENABLE_AI_AGENT         = True
    AI_MODEL                = "claude-sonnet-4-5"
    ANTHROPIC_API_KEY       = os.getenv("ANTHROPIC_API_KEY", "")

    # 功能开关
    ENABLED_FEATURES        = ["news_push", "timer"]

    # 新闻
    NEWS_SOURCES = {
        "baidu":  "https://top.baidu.com/board?tab=realtime",
        "weibo":  "https://s.weibo.com/top/summary",
        "google": "https://trends.google.com/trending",
    }
    NEWS_CACHE_DURATION     = 1800    # 秒

    # 定时器
    DEFAULT_TIMER_MINUTES   = 10

    # 宠物默认人设
    DEFAULT_PET_NAME        = '边牧'
    DEFAULT_PET_PERSONALITY = '活泼'
    DEFAULT_PET_CATCHPHRASE = '汪~'
    DEFAULT_PET_EMOJI       = '🐕'

    # 主题
    DEFAULT_THEME           = 'light'   # 'light' | 'dark'

    # 聊天历史
    MAX_CHAT_SESSIONS       = 50

    # Agent 触发关键词（包含这些词时走 LangGraph，否则走 Claude CLI）
    AGENT_TRIGGER_KEYWORDS  = ['帮我', '帮忙', '设置', '定一个', '查询', '查一下', '搜索']


# ── tkinter THEMES（保留，供 services/ 代码引用颜色时查询）────
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
