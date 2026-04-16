# Codebase Structure

**Analysis Date:** 2026-04-16

## Directory Layout

```
desktop-pet/
├── desktop_pet.py          # Main application (2056 lines) — floating pet + main panel
├── news_pet.py             # Legacy minimal news pet (183 lines)
├── start.sh                # Shell launcher for web-pet server
├── settings.json           # Persisted user settings (runtime-written)
├── notes.json              # Persisted notes data (runtime-written)
├── web-pet/
│   ├── server.py           # HTTP server for web variant (173 lines)
│   ├── index.html          # Web-based pet UI
│   └── news_cache.json     # Shared news cache (runtime-written, TTL 30 min)
├── NewsPet.app/            # macOS .app bundle (not tracked in git content)
│   └── Contents/MacOS/
├── .planning/
│   └── codebase/           # GSD mapping documents (this directory)
└── .git/
```

## Directory Purposes

**Root (`desktop-pet/`):**
- Purpose: Everything lives at the root; no src/ subdirectory
- Key files: `desktop_pet.py` is the sole runnable entry point for the main app

**`web-pet/`:**
- Purpose: Standalone web-based alternative to the native Tkinter pet
- Contains: HTTP server, single-page HTML UI, shared `news_cache.json`
- Key files: `web-pet/server.py`, `web-pet/index.html`

**`NewsPet.app/`:**
- Purpose: macOS application bundle wrapper
- Generated: Likely hand-crafted or produced by `py2app`
- Committed: Yes (present in repo)

**`.planning/codebase/`:**
- Purpose: GSD architecture and convention reference documents
- Generated: Yes (by Claude agents)
- Committed: No (not yet tracked)

## Key File Locations

**Entry Points:**
- `desktop_pet.py` (line 2055): `DesktopPet().run()` — start the native Tkinter app
- `web-pet/server.py` (line 172): HTTP server entry
- `start.sh`: Shell script that launches `web-pet/server.py` and opens the browser
- `news_pet.py`: Legacy standalone minimal pet (not imported by main app)

**Configuration:**
- `settings.json`: Runtime user preferences (`pet_emoji`, `pet_size`, `auto_refresh_min`, `notify_on_refresh`)
- `notes.json`: User notes storage (`{"notes": [{id, content, updated}]}`)
- `web-pet/news_cache.json`: Shared news fetch cache (`{content: str, timestamp: float}`)

**Core Logic (all within `desktop_pet.py`):**
- Lines 26–81: `THEMES` dict and legacy color constants
- Lines 87–184: Module-level utility functions (`load_json`, `save_json`, `get_news`, `parse_news`, `send_notification`, `_translate_titles_with_claude`)
- Lines 192–1935: `MainPanel` class — all five tabs and theme system
- Lines 1941–2056: `DesktopPet` class — floating widget, animation, drag, context menu

**External Dependency (outside repo):**
- `~/.openclaw/workspace/skills/news-digest/scripts/fetch_news.py`: News fetch script (called via `subprocess.run`)
- `/opt/homebrew/bin/claude`: Claude CLI binary (called via `subprocess.Popen` for chat and translation)

## Naming Conventions

**Files:**
- Snake case: `desktop_pet.py`, `news_pet.py`, `server.py`
- Data files: lowercase with underscores, `.json` extension

**Classes:**
- PascalCase: `DesktopPet`, `MainPanel`, `NewsPet`, `NewsHandler`

**Methods:**
- Public: camelCase-ish snake_case — `open()`, `run()`, `trigger_bounce()`, `set_emoji()`
- Private UI builders: `_build_home_tab`, `_build_news_tab`, `_build_pet_tab`, `_build_notes_tab`, `_build_settings_tab`
- Private helpers: `_on_press`, `_on_drag`, `_on_release`, `_animate`, `_switch_tab`, `_apply_theme`
- Async runners: `_load_news_async`, `_stream_pet_ai`

**Constants:**
- UPPER_SNAKE for module-level: `NEWS_SCRIPT`, `CACHE_FILE`, `NOTE_FILE`, `SETTINGS_FILE`, `CACHE_TTL`, `BG_DARK`, `FG_ACCENT`
- Class constants: `ANIM_INTERVAL`, `WIN_W`, `WIN_H`, `NAV_W`, `GREETINGS`

**Theme keys:**
- Prefixed by type: `BG_` for backgrounds, `FG_` for foregrounds, `BORDER`, `DIVIDER`, `ACCENT_BAR`

## Where to Add New Code

**New Tab:**
- Add tab definition tuple to `tab_defs` list in `MainPanel._build()` (around line 362)
- Implement `_build_<name>_tab(self, parent) -> tk.Frame` following the pattern of existing tab builders
- Frame is returned and registered in `self._tab_frames[key]`
- All content must use `th = THEMES[self._theme_mode]` for colors to support theme switching

**New Utility Function:**
- Add at module level in `desktop_pet.py` in the `工具函数` section (after line 86)
- Follow the `load_json` / `save_json` pattern: catch `Exception`, return a safe default

**New Persisted Data:**
- Define a module-level `<NAME>_FILE` path constant near the top of `desktop_pet.py`
- Use `load_json(path, default)` / `save_json(path, data)` for reads and writes

**New Background Task:**
- Follow the pattern in `_load_news_async` / `_stream_pet_ai`:
  - Define a `run()` inner function containing the blocking work
  - Schedule GUI updates with `self.win.after(0, callback)` — never touch widgets directly from the thread
  - Start with `threading.Thread(target=run, daemon=True).start()`

**New Settings Field:**
- Add a default value in `load_settings()` default dict (line 102)
- Read from `self.pet.settings.get('key', default)` in any class
- Save with `save_settings(self.pet.settings)` after mutating the dict

**New Web API Endpoint:**
- Add an `elif parsed.path == '/endpoint':` branch in `NewsHandler.do_GET` in `web-pet/server.py`

## Special Directories

**`NewsPet.app/`:**
- Purpose: macOS app bundle for drag-to-Applications install
- Generated: Partially (bundle structure is manual, not from a build tool)
- Committed: Yes

**`__pycache__/`:**
- Purpose: Python bytecode cache
- Generated: Yes (by Python interpreter)
- Committed: No (standard `.gitignore` exclusion)

**`.planning/`:**
- Purpose: GSD planning and mapping documents
- Generated: Yes (by Claude agents)
- Committed: Not currently tracked

---

*Structure analysis: 2026-04-16*
