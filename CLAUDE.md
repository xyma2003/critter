<!-- GSD:project-start source:PROJECT.md -->
## Project

**Critter**

Critter 是一个 macOS 桌面宠物应用，常驻桌面右下角作为悬浮 emoji 小猫，点击后展开一个 1024×620 的主面板。主面板包含 AI 对话、热点新闻、宠物互动、便签和设置五个功能区，使用 Python 3.11 + tkinter 构建，支持深色/浅色主题切换。

**Core Value:** 宠物始终在桌面陪伴——悬浮窗随时可见、可交互，让用户感受到有个小伙伴在场。

### Constraints

- **Tech Stack**: Python 3.11 + tkinter — 不引入第三方 UI 库，保持零依赖安装
- **Python Path**: 必须用 `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11`，系统 tkinter 有 bug
- **单文件架构**: 当前所有代码在 `desktop_pet.py`，新功能继续在此文件扩展，不拆分模块（避免打破现有启动方式）
- **数据存储**: 当前里程碑用 JSON 文件，但新增数据访问必须通过 Repository 类封装
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.11.9 - All application logic, GUI, HTTP server, subprocess orchestration
- HTML5 + CSS3 + Vanilla JavaScript - Web-based pet variant (`web-pet/index.html`)
## Runtime
- CPython 3.11.9 (invoked via `python3` at `/usr/local/bin/python3`)
- None — project uses only Python standard library; no `requirements.txt`, no virtual environment
## Frameworks
- `tkinter` (stdlib) — entire desktop UI: windows, canvas drawing, scrolled text, menus, animations
- `tkinter.scrolledtext` (stdlib) — used for scrolled text areas
- `http.server.SimpleHTTPRequestHandler` (stdlib) — serves `index.html` and JSON API endpoints
- `socketserver.TCPServer` (stdlib) with `allow_reuse_address = True` — listens on port `8765`
- Not applicable — no test framework present
- No build step; runs directly with `python3 desktop_pet.py`
- `start.sh` — bash launcher for the web-pet variant (starts `server.py`, opens browser)
## Key Dependencies
- `ctypes` (stdlib) — loads `/usr/lib/libobjc.dylib` to call macOS Objective-C runtime APIs directly for window-level management
- `subprocess` (stdlib) — spawns the Claude CLI process (`/opt/homebrew/bin/claude`) for streaming AI chat, runs `osascript` for macOS notifications, opens URLs via `open`, and executes the external news fetch script
- `threading` (stdlib) — background threads for news fetching, AI streaming, and news push notifications
- `math` (stdlib) — sine-based bounce and floating animation math
- `json` (stdlib) — read/write `settings.json`, `notes.json`, `news_cache.json`
- `re` (stdlib) — news text parsing, Google Trends RSS extraction, Baidu/Weibo scraping
- `urllib.request`, `ssl` (stdlib) — HTTP fetching in `fetch_news.py` (no third-party HTTP library)
- Claude CLI `2.1.104` at `/opt/homebrew/bin/claude` — used for AI chat streaming (`--output-format stream-json --include-partial-messages`) and batch translation of English news headlines
- `osascript` (macOS system) — sends native macOS notifications via `display notification`
- `open` (macOS system) — opens news URLs in the default browser
## Configuration
- No `.env` file; configuration is stored in `settings.json`
- `settings.json` at `/Users/maxinyue09/.openclaw/workspace/desktop-pet/settings.json` holds:
- `NEWS_SCRIPT` → `~/.openclaw/workspace/skills/news-digest/scripts/fetch_news.py`
- `CACHE_FILE`  → `~/.openclaw/workspace/desktop-pet/web-pet/news_cache.json`
- `NOTE_FILE`   → `~/.openclaw/workspace/desktop-pet/notes.json`
- `SETTINGS_FILE` → `~/.openclaw/workspace/desktop-pet/settings.json`
- `CACHE_TTL`   → `1800` seconds (30 min)
- Web server port hardcoded as `PORT = 8765` in `web-pet/server.py`
- No build config files
## Platform Requirements
- macOS only (uses `ctypes` against `/usr/lib/libobjc.dylib`, `osascript`, and `open`)
- Python 3.11+
- Claude CLI installed at `/opt/homebrew/bin/claude` (Homebrew on Apple Silicon)
- `tkinter` must be available (included with standard macOS Python installations)
- No deployment target — local desktop application
- Web variant accessible at `http://localhost:8765` when `web-pet/server.py` is running
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- `snake_case.py` for all Python files: `desktop_pet.py`, `news_pet.py`, `server.py`
- Single-responsibility files — each file is one self-contained app or server
- `PascalCase`: `DesktopPet`, `MainPanel`, `NewsPet`, `NewsHandler`, `ReusableTCPServer`
- Class-level constants in `UPPER_SNAKE_CASE`: `ANIM_INTERVAL`, `WIN_W`, `WIN_H`, `NAV_W`
- Public methods: `snake_case` — `open()`, `run()`, `trigger_bounce()`, `set_emoji()`
- Private methods: leading underscore `_snake_case` — `_build()`, `_switch_tab()`, `_animate()`, `_on_press()`
- Tab-builder methods follow pattern `_build_<tab>_tab(parent)`: `_build_home_tab`, `_build_news_tab`, `_build_pet_tab`, `_build_notes_tab`, `_build_settings_tab`
- Event handlers follow pattern `_on_<event>`: `_on_press`, `_on_drag`, `_on_release`, `_on_chat_enter`, `_on_stream_chunk`, `_on_stream_done`
- Async loader methods follow pattern `_load_<resource>_async`: `_load_news_async`
- Instance attributes: `snake_case` with `self.` prefix
- Private instance state: leading underscore `self._news_loaded`, `self._chat_thinking`, `self._theme_mode`
- Local variables in event closures: `snake_case`, often `w` for widget, `e` for event, `b` for button, `th` for theme dict
- Module-level constants: `UPPER_SNAKE_CASE` — `CACHE_TTL`, `BG_DARK`, `FG_ACCENT`
- Functional, descriptive names: `_draw_pill`, `_draw_send_btn_w`, `_refresh_wib`, `_on_canvas_resize`, `run`, `_tick`, `_render`
- Inner-loop event handlers use short names: `_enter`, `_leave`, `_click`
- Theme keys are `UPPER_SNAKE_CASE` strings: `'BG_WIN'`, `'FG_MAIN'`, `'BORDER'`, `'ACCENT_BAR'`
- Theme dict variable always named `th` locally: `th = THEMES[self._theme_mode]`
## Code Style
- No formatter config file detected (no `.prettierrc`, `pyproject.toml`, or `black` config)
- 4-space indentation throughout
- Lines generally kept under ~100 characters; longer lines used for widget configuration chains
- Blank lines separate logical blocks within methods
- Two blank lines between top-level functions; one blank line between methods in a class
- Major sections marked with box-style comments using `═` characters:
- Minor sub-sections use `──` dashes:
- No `.flake8`, `.pylintrc`, or `ruff.toml` detected; no enforced linter
## Import Organization
## Error Handling
## UI Patterns
- UI text: `('PingFang SC', SIZE)` or `('PingFang SC', SIZE, 'bold')`
- Emoji display: `('Apple Color Emoji', SIZE)`
- All sizes are integers passed directly
## Threading Patterns
## Module Design
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- Two distinct window layers: `DesktopPet` (always-on-top, frameless, transparent) owns a `tk.Tk` root; `MainPanel` (normal window, can be covered) is a `tk.Toplevel`
- All application logic, UI construction, theming, data access, and AI integration live in `desktop_pet.py`
- No event bus or MVC separation — UI widgets hold state directly as instance attributes on their owning class
- Background work (news fetch, AI streaming) is done on daemon threads; GUI updates are scheduled back onto the main thread via `root.after(0, callback)`
## Layers
- Purpose: Persistent always-on-top emoji that accepts clicks and drag
- Location: `desktop_pet.py`, class `DesktopPet` (line 1941)
- Contains: Animation loop (`_animate`), drag handling, bounce trigger, context menu, reference to `MainPanel`
- Depends on: `load_settings()`, `MainPanel`
- Used by: Entry point `__main__`
- Purpose: Full-featured 1024×620 panel with five tabs
- Location: `desktop_pet.py`, class `MainPanel` (line 192)
- Contains: Tab build methods, theme switching, chat session management, notes CRUD, news loading/rendering, settings persistence
- Depends on: `DesktopPet` (back-reference via `self.pet`), global utility functions, `THEMES` dict
- Used by: `DesktopPet.__init__` constructs it; `DesktopPet._on_release` calls `panel.open()`
- Purpose: JSON I/O, news fetch, macOS notification, Claude translation helper
- Location: `desktop_pet.py`, lines 87–184 (module-level functions)
- Contains: `load_json`, `save_json`, `load_settings`, `save_settings`, `load_cache`, `save_cache`, `get_news`, `fetch_news_raw`, `parse_news`, `send_notification`, `_translate_titles_with_claude`
- Depends on: standard library only (`json`, `subprocess`, `time`, `re`, `os`)
- Used by: both `MainPanel` and `DesktopPet`
- Purpose: HTTP API for the web-based pet variant
- Location: `web-pet/server.py`
- Contains: `NewsHandler` (GET `/news`, GET `/push`), cache helpers, macOS notification sender
- Depends on: same external `fetch_news.py` script at `~/.openclaw/workspace/skills/news-digest/scripts/fetch_news.py`
- Used by: `start.sh` launches it as a background process; `web-pet/index.html` fetches from it
## Data Flow
- Theme state: `MainPanel._theme_mode` (string `'light'`/`'dark'`); theme change triggers `_recolor_widget` tree walk
- Chat session state: `MainPanel._chat_sessions` (in-memory list of dicts), `_current_session_id`; sessions are NOT persisted to disk
- Settings: `DesktopPet.settings` dict; persisted to `settings.json` on save actions
- News: `MainPanel._news_sections_cache` (in-memory); persisted raw text to `web-pet/news_cache.json`
- Pet animation state: float fields `_anim_frame`, `_bouncing`, `_bounce_frame`, `_hovering` on `DesktopPet`
## Key Abstractions
- Purpose: All color tokens for dark and light modes keyed by semantic name (`BG_WIN`, `FG_ACCENT`, etc.)
- Location: `desktop_pet.py` lines 26–67
- Pattern: `th = THEMES[self._theme_mode]` at the top of every build/recolor method; widget colors are set from `th['KEY']`
- Purpose: Chat message bubbles with rounded corners drawn manually on `tk.Canvas`
- Location: `MainPanel._rounded_bubble()` (line 977), `MainPanel._update_bubble()` (line 1027)
- Pattern: Canvas items tagged `'bubble_bg'`; text item id stored as `canvas._text_id`; bubble color stored as `canvas._bubble_bg` for theme-aware recoloring
- Purpose: Five content tabs stacked in a `grid` layout; `tkraise()` brings the active frame forward
- Location: `MainPanel._build()` lines 362–382, `MainPanel._switch_tab()` lines 425–449
- Pattern: `self._tab_frames[key].tkraise()` — no frame is destroyed between switches, preserving scroll state
- Purpose: Avoids re-fetching on column-count reflow; re-renders from `_news_sections_cache` on window resize
- Location: `MainPanel._news_canvas_last_cols` + `_news_sections_cache`, lines 1308–1316
## Entry Points
- Location: `desktop_pet.py` line 2055–2056
- Triggers: `python3 desktop_pet.py` (or via Finder / `~/start.sh`)
- Responsibilities: Instantiates `DesktopPet`, which sets up the transparent always-on-top window, the `MainPanel`, and calls `root.mainloop()`
- Location: `web-pet/server.py` line 172–173
- Triggers: `python3 web-pet/server.py` or `./start.sh`
- Responsibilities: Starts HTTP server on port 8765 serving `index.html`, `/news`, `/push` endpoints
- Location: `news_pet.py` line 12 (`NewsPet`) + bottom-of-file run
- Triggers: `python3 news_pet.py`
- Responsibilities: Tiny frameless 70×70 emoji window with click-to-menu; news fetch only; no panel
## Error Handling
- `load_json` / `save_json`: return `default` on any exception, no logging
- `_stream_pet_ai`: catches all exceptions, sets `accumulated = f'呜，出了点小问题：{e}'` to display in bubble
- `send_notification`: called in `try/except` blocks at call sites
- `_fix_panel_window_level`: entire macOS Objective-C bridge wrapped in `try/except Exception: pass`
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
