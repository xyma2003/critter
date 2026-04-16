# Architecture

**Analysis Date:** 2026-04-16

## Pattern Overview

**Overall:** Monolithic single-file GUI application with a two-window split (always-on-top floating pet + detachable main panel)

**Key Characteristics:**
- Two distinct window layers: `DesktopPet` (always-on-top, frameless, transparent) owns a `tk.Tk` root; `MainPanel` (normal window, can be covered) is a `tk.Toplevel`
- All application logic, UI construction, theming, data access, and AI integration live in `desktop_pet.py`
- No event bus or MVC separation — UI widgets hold state directly as instance attributes on their owning class
- Background work (news fetch, AI streaming) is done on daemon threads; GUI updates are scheduled back onto the main thread via `root.after(0, callback)`

## Layers

**Floating Pet Layer:**
- Purpose: Persistent always-on-top emoji that accepts clicks and drag
- Location: `desktop_pet.py`, class `DesktopPet` (line 1941)
- Contains: Animation loop (`_animate`), drag handling, bounce trigger, context menu, reference to `MainPanel`
- Depends on: `load_settings()`, `MainPanel`
- Used by: Entry point `__main__`

**Main Panel Layer:**
- Purpose: Full-featured 1024×620 panel with five tabs
- Location: `desktop_pet.py`, class `MainPanel` (line 192)
- Contains: Tab build methods, theme switching, chat session management, notes CRUD, news loading/rendering, settings persistence
- Depends on: `DesktopPet` (back-reference via `self.pet`), global utility functions, `THEMES` dict
- Used by: `DesktopPet.__init__` constructs it; `DesktopPet._on_release` calls `panel.open()`

**Utility / Data Layer:**
- Purpose: JSON I/O, news fetch, macOS notification, Claude translation helper
- Location: `desktop_pet.py`, lines 87–184 (module-level functions)
- Contains: `load_json`, `save_json`, `load_settings`, `save_settings`, `load_cache`, `save_cache`, `get_news`, `fetch_news_raw`, `parse_news`, `send_notification`, `_translate_titles_with_claude`
- Depends on: standard library only (`json`, `subprocess`, `time`, `re`, `os`)
- Used by: both `MainPanel` and `DesktopPet`

**Web Sub-application (separate process):**
- Purpose: HTTP API for the web-based pet variant
- Location: `web-pet/server.py`
- Contains: `NewsHandler` (GET `/news`, GET `/push`), cache helpers, macOS notification sender
- Depends on: same external `fetch_news.py` script at `~/.openclaw/workspace/skills/news-digest/scripts/fetch_news.py`
- Used by: `start.sh` launches it as a background process; `web-pet/index.html` fetches from it

## Data Flow

**Chat (AI Response Streaming):**

1. User types in `_welcome_input` or `_chat_input` and presses Return or the send button
2. `MainPanel._send_chat()` reads the text, switches to chat view if first message, adds user bubble
3. A placeholder "···" pet bubble is added; `_chat_thinking = True`
4. `threading.Thread(target=run, daemon=True).start()` calls `_stream_pet_ai(user_text)`
5. `_stream_pet_ai` opens a subprocess to `/opt/homebrew/bin/claude --print --output-format stream-json --include-partial-messages`
6. Each `text_delta` chunk calls `self.win.after(0, lambda t=t: self._on_stream_chunk(t))` to update the bubble on the main thread
7. On completion `self.win.after(0, lambda: self._on_stream_done(final_text))` re-enables the send button

**News Loading:**

1. User switches to the news tab (or clicks refresh)
2. `MainPanel._load_news_async(force)` shows an animated loading spinner and starts a daemon thread
3. The thread calls `get_news(force)` which checks `web-pet/news_cache.json` (TTL = 30 min); if stale it runs `fetch_news_raw()` → `subprocess.run(['python3', NEWS_SCRIPT])`
4. Google Trends titles are translated via `_translate_titles_with_claude` (another subprocess)
5. `self.win.after(0, lambda: self._render_news(sections, status))` renders the news grid back on the main thread

**Notes CRUD:**

1. Notes list reads `notes.json` on each tab interaction via `_notes_load_all()` → `load_json(NOTE_FILE, ...)`
2. Saves write atomically via `save_json()` → `json.dump` with `ensure_ascii=False`
3. No in-memory cache; every open/save hits disk

**State Management:**
- Theme state: `MainPanel._theme_mode` (string `'light'`/`'dark'`); theme change triggers `_recolor_widget` tree walk
- Chat session state: `MainPanel._chat_sessions` (in-memory list of dicts), `_current_session_id`; sessions are NOT persisted to disk
- Settings: `DesktopPet.settings` dict; persisted to `settings.json` on save actions
- News: `MainPanel._news_sections_cache` (in-memory); persisted raw text to `web-pet/news_cache.json`
- Pet animation state: float fields `_anim_frame`, `_bouncing`, `_bounce_frame`, `_hovering` on `DesktopPet`

## Key Abstractions

**THEMES dict:**
- Purpose: All color tokens for dark and light modes keyed by semantic name (`BG_WIN`, `FG_ACCENT`, etc.)
- Location: `desktop_pet.py` lines 26–67
- Pattern: `th = THEMES[self._theme_mode]` at the top of every build/recolor method; widget colors are set from `th['KEY']`

**Rounded Bubble (Canvas-based widget):**
- Purpose: Chat message bubbles with rounded corners drawn manually on `tk.Canvas`
- Location: `MainPanel._rounded_bubble()` (line 977), `MainPanel._update_bubble()` (line 1027)
- Pattern: Canvas items tagged `'bubble_bg'`; text item id stored as `canvas._text_id`; bubble color stored as `canvas._bubble_bg` for theme-aware recoloring

**Tab Frame Stack:**
- Purpose: Five content tabs stacked in a `grid` layout; `tkraise()` brings the active frame forward
- Location: `MainPanel._build()` lines 362–382, `MainPanel._switch_tab()` lines 425–449
- Pattern: `self._tab_frames[key].tkraise()` — no frame is destroyed between switches, preserving scroll state

**News Section Cache:**
- Purpose: Avoids re-fetching on column-count reflow; re-renders from `_news_sections_cache` on window resize
- Location: `MainPanel._news_canvas_last_cols` + `_news_sections_cache`, lines 1308–1316

## Entry Points

**Primary (`desktop_pet.py`):**
- Location: `desktop_pet.py` line 2055–2056
- Triggers: `python3 desktop_pet.py` (or via Finder / `~/start.sh`)
- Responsibilities: Instantiates `DesktopPet`, which sets up the transparent always-on-top window, the `MainPanel`, and calls `root.mainloop()`

**Web variant (`web-pet/server.py`):**
- Location: `web-pet/server.py` line 172–173
- Triggers: `python3 web-pet/server.py` or `./start.sh`
- Responsibilities: Starts HTTP server on port 8765 serving `index.html`, `/news`, `/push` endpoints

**Legacy minimal pet (`news_pet.py`):**
- Location: `news_pet.py` line 12 (`NewsPet`) + bottom-of-file run
- Triggers: `python3 news_pet.py`
- Responsibilities: Tiny frameless 70×70 emoji window with click-to-menu; news fetch only; no panel

## Error Handling

**Strategy:** Silent catch-and-continue — nearly all `try/except` blocks catch bare `Exception` and either return a default or pass silently

**Patterns:**
- `load_json` / `save_json`: return `default` on any exception, no logging
- `_stream_pet_ai`: catches all exceptions, sets `accumulated = f'呜，出了点小问题：{e}'` to display in bubble
- `send_notification`: called in `try/except` blocks at call sites
- `_fix_panel_window_level`: entire macOS Objective-C bridge wrapped in `try/except Exception: pass`

## Cross-Cutting Concerns

**Logging:** None — `log_message` in `web-pet/server.py` is overridden to suppress all HTTP logs; no application-level logger
**Validation:** No input validation beyond empty-string checks in notes save and chat send
**Authentication:** None
**Threading:** All background work via `threading.Thread(daemon=True)`; GUI updates via `widget.after(0, callback)` — no explicit lock used
**External Process Dependency:** Claude CLI at `/opt/homebrew/bin/claude` and news script at `~/.openclaw/workspace/skills/news-digest/scripts/fetch_news.py` are hard-coded paths; failures fall back silently

---

*Architecture analysis: 2026-04-16*
