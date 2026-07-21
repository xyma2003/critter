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


