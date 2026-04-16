# Technology Stack

**Analysis Date:** 2026-04-16

## Languages

**Primary:**
- Python 3.11.9 - All application logic, GUI, HTTP server, subprocess orchestration

**Secondary:**
- HTML5 + CSS3 + Vanilla JavaScript - Web-based pet variant (`web-pet/index.html`)

## Runtime

**Environment:**
- CPython 3.11.9 (invoked via `python3` at `/usr/local/bin/python3`)

**Package Manager:**
- None — project uses only Python standard library; no `requirements.txt`, no virtual environment

## Frameworks

**GUI (Desktop App):**
- `tkinter` (stdlib) — entire desktop UI: windows, canvas drawing, scrolled text, menus, animations
- `tkinter.scrolledtext` (stdlib) — used for scrolled text areas

**HTTP Server (Web Variant):**
- `http.server.SimpleHTTPRequestHandler` (stdlib) — serves `index.html` and JSON API endpoints
- `socketserver.TCPServer` (stdlib) with `allow_reuse_address = True` — listens on port `8765`

**Testing:**
- Not applicable — no test framework present

**Build/Dev:**
- No build step; runs directly with `python3 desktop_pet.py`
- `start.sh` — bash launcher for the web-pet variant (starts `server.py`, opens browser)

## Key Dependencies

**Critical:**
- `ctypes` (stdlib) — loads `/usr/lib/libobjc.dylib` to call macOS Objective-C runtime APIs directly for window-level management
- `subprocess` (stdlib) — spawns the Claude CLI process (`/opt/homebrew/bin/claude`) for streaming AI chat, runs `osascript` for macOS notifications, opens URLs via `open`, and executes the external news fetch script
- `threading` (stdlib) — background threads for news fetching, AI streaming, and news push notifications
- `math` (stdlib) — sine-based bounce and floating animation math
- `json` (stdlib) — read/write `settings.json`, `notes.json`, `news_cache.json`
- `re` (stdlib) — news text parsing, Google Trends RSS extraction, Baidu/Weibo scraping
- `urllib.request`, `ssl` (stdlib) — HTTP fetching in `fetch_news.py` (no third-party HTTP library)

**Infrastructure:**
- Claude CLI `2.1.104` at `/opt/homebrew/bin/claude` — used for AI chat streaming (`--output-format stream-json --include-partial-messages`) and batch translation of English news headlines
- `osascript` (macOS system) — sends native macOS notifications via `display notification`
- `open` (macOS system) — opens news URLs in the default browser

## Configuration

**Environment:**
- No `.env` file; configuration is stored in `settings.json`
- `settings.json` at `/Users/maxinyue09/.openclaw/workspace/desktop-pet/settings.json` holds:
  - `auto_refresh_min` (integer, default `30`)
  - `notify_on_refresh` (boolean, default `false`)
  - `pet_emoji` (string, default `"🐱"`)
  - `pet_size` (integer, default `76`)

**Runtime paths (hardcoded at top of `desktop_pet.py`):**
- `NEWS_SCRIPT` → `~/.openclaw/workspace/skills/news-digest/scripts/fetch_news.py`
- `CACHE_FILE`  → `~/.openclaw/workspace/desktop-pet/web-pet/news_cache.json`
- `NOTE_FILE`   → `~/.openclaw/workspace/desktop-pet/notes.json`
- `SETTINGS_FILE` → `~/.openclaw/workspace/desktop-pet/settings.json`
- `CACHE_TTL`   → `1800` seconds (30 min)
- Web server port hardcoded as `PORT = 8765` in `web-pet/server.py`

**Build:**
- No build config files

## Platform Requirements

**Development:**
- macOS only (uses `ctypes` against `/usr/lib/libobjc.dylib`, `osascript`, and `open`)
- Python 3.11+
- Claude CLI installed at `/opt/homebrew/bin/claude` (Homebrew on Apple Silicon)
- `tkinter` must be available (included with standard macOS Python installations)

**Production:**
- No deployment target — local desktop application
- Web variant accessible at `http://localhost:8765` when `web-pet/server.py` is running

---

*Stack analysis: 2026-04-16*
