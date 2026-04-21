<!-- GSD:project-start source:PROJECT.md -->
## Project

**Critter**

Critter 是一个 macOS 桌面宠物应用，常驻桌面右下角作为悬浮 emoji 小猫，点击后展开一个 1024×620 的主面板。主面板包含 AI 对话、热点新闻、宠物互动、便签和设置五个功能区，使用 Python 3.11 + tkinter 构建，支持深色/浅色主题切换。

**Core Value:** 宠物始终在桌面陪伴——悬浮窗随时可见、可交互，让用户感受到有个小伙伴在场。

### Constraints

- **Tech Stack**: Python 3.11 + tkinter — 不引入第三方 UI 库，保持零依赖安装
- **Python Path**: 必须用 `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11`，系统 tkinter 有 bug
- **模块化架构**: 代码已拆分为 `config.py`、`data/`、`services/`、`ui/` 四个模块，入口为 `main.py`
- **数据存储**: 用 JSON 文件，数据访问必须通过 Repository 类封装
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.11.9 - All application logic, GUI, subprocess orchestration
## Runtime
- CPython 3.11.9 at `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11`
- None — project uses only Python standard library; no `requirements.txt`, no virtual environment
## Frameworks
- `tkinter` (stdlib) — entire desktop UI: windows, canvas drawing, scrolled text, menus, animations
- `tkinter.scrolledtext` (stdlib) — used for scrolled text areas
- Not applicable — no test framework present
- No build step; runs directly with `python3.11 main.py`
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
- `NOTE_FILE`   → `~/.openclaw/workspace/desktop-pet/notes.json`
- `SETTINGS_FILE` → `~/.openclaw/workspace/desktop-pet/settings.json`
- `CACHE_TTL`   → `1800` seconds (30 min)
- No build config files
## Platform Requirements
- macOS only (uses `ctypes` against `/usr/lib/libobjc.dylib`, `osascript`, and `open`)
- Python 3.11+
- Claude CLI installed at `/opt/homebrew/bin/claude` (Homebrew on Apple Silicon)
- `tkinter` must be available (included with standard macOS Python installations)
- No deployment target — local desktop application
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
- Modular architecture: `config.py` (themes/constants), `data/` (storage), `services/` (news/AI), `ui/` (windows)
- No event bus or MVC separation — UI widgets hold state directly as instance attributes on their owning class
- Background work (news fetch, AI streaming) is done on daemon threads; GUI updates are scheduled back onto the main thread via `root.after(0, callback)`
## Layers
- Purpose: Persistent always-on-top emoji that accepts clicks and drag
- Location: `ui/pet_window.py`, class `DesktopPet`
- Contains: Animation loop (`_animate`), drag handling, bounce trigger, context menu, reference to `MainPanel`
- Depends on: `data/settings.py`, `config.py`, `MainPanel`
- Used by: Entry point `main.py`
- Purpose: Full-featured 1024×620 panel with five tabs
- Location: `ui/panel.py`, class `MainPanel`
- Contains: Tab build methods, theme switching, chat session management, notes CRUD, news loading/rendering, settings persistence
- Depends on: `DesktopPet` (back-reference via `self.pet`), `config.py`, `data/`, `services/`
- Used by: `DesktopPet.__init__` constructs it; `DesktopPet._on_release` calls `panel.open()`
- Purpose: News fetching, caching, parsing, translation
- Location: `services/news.py`, `services/ai.py`
- Purpose: JSON I/O, pet stats, bookmarks
- Location: `data/settings.py`, `data/pet_stats.py`, `data/repository.py`
## Data Flow
- Theme state: `MainPanel._theme_mode` (string `'light'`/`'dark'`); theme change triggers `_recolor_widget` tree walk
- Chat session state: `MainPanel._chat_sessions` (in-memory list of dicts), `_current_session_id`; sessions are NOT persisted to disk
- Settings: `DesktopPet.settings` dict; persisted to `settings.json` on save actions
- News: `MainPanel._news_sections_cache` (in-memory); cached to `news_cache.json`
- Pet animation state: float fields `_anim_frame`, `_bouncing`, `_bounce_frame`, `_hovering` on `DesktopPet`
## Key Abstractions
- Purpose: All color tokens for dark and light modes keyed by semantic name (`BG_WIN`, `FG_ACCENT`, etc.)
- Location: `config.py`, `THEMES` dict
- Pattern: `th = THEMES[self._theme_mode]` at the top of every build/recolor method
- Purpose: Chat message bubbles with rounded corners drawn manually on `tk.Canvas`
- Location: `MainPanel._rounded_bubble()`, `MainPanel._update_bubble()`
- Pattern: Canvas items tagged `'bubble_bg'`; text item id stored as `canvas._text_id`
- Purpose: Five content tabs stacked in a `grid` layout; `tkraise()` brings the active frame forward
- Location: `MainPanel._build()`, `MainPanel._switch_tab()`
- Pattern: `self._tab_frames[key].tkraise()` — no frame is destroyed between switches
## Entry Points
- Location: `main.py`
- Triggers: `python3.11 main.py`
- Responsibilities: Instantiates `DesktopPet`, which sets up the transparent always-on-top window, the `MainPanel`, and calls `root.mainloop()`
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
