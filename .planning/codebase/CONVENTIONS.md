# Coding Conventions

**Analysis Date:** 2026-04-16

## Naming Patterns

**Files:**
- `snake_case.py` for all Python files: `desktop_pet.py`, `news_pet.py`, `server.py`
- Single-responsibility files — each file is one self-contained app or server

**Classes:**
- `PascalCase`: `DesktopPet`, `MainPanel`, `NewsPet`, `NewsHandler`, `ReusableTCPServer`
- Class-level constants in `UPPER_SNAKE_CASE`: `ANIM_INTERVAL`, `WIN_W`, `WIN_H`, `NAV_W`

**Methods:**
- Public methods: `snake_case` — `open()`, `run()`, `trigger_bounce()`, `set_emoji()`
- Private methods: leading underscore `_snake_case` — `_build()`, `_switch_tab()`, `_animate()`, `_on_press()`
- Tab-builder methods follow pattern `_build_<tab>_tab(parent)`: `_build_home_tab`, `_build_news_tab`, `_build_pet_tab`, `_build_notes_tab`, `_build_settings_tab`
- Event handlers follow pattern `_on_<event>`: `_on_press`, `_on_drag`, `_on_release`, `_on_chat_enter`, `_on_stream_chunk`, `_on_stream_done`
- Async loader methods follow pattern `_load_<resource>_async`: `_load_news_async`

**Variables:**
- Instance attributes: `snake_case` with `self.` prefix
- Private instance state: leading underscore `self._news_loaded`, `self._chat_thinking`, `self._theme_mode`
- Local variables in event closures: `snake_case`, often `w` for widget, `e` for event, `b` for button, `th` for theme dict
- Module-level constants: `UPPER_SNAKE_CASE` — `CACHE_TTL`, `BG_DARK`, `FG_ACCENT`

**Closures / nested functions inside methods:**
- Functional, descriptive names: `_draw_pill`, `_draw_send_btn_w`, `_refresh_wib`, `_on_canvas_resize`, `run`, `_tick`, `_render`
- Inner-loop event handlers use short names: `_enter`, `_leave`, `_click`

**Theme dict:**
- Theme keys are `UPPER_SNAKE_CASE` strings: `'BG_WIN'`, `'FG_MAIN'`, `'BORDER'`, `'ACCENT_BAR'`
- Theme dict variable always named `th` locally: `th = THEMES[self._theme_mode]`

## Code Style

**Formatting:**
- No formatter config file detected (no `.prettierrc`, `pyproject.toml`, or `black` config)
- 4-space indentation throughout
- Lines generally kept under ~100 characters; longer lines used for widget configuration chains
- Blank lines separate logical blocks within methods
- Two blank lines between top-level functions; one blank line between methods in a class

**Section comments:**
- Major sections marked with box-style comments using `═` characters:
  ```python
  # ══════════════════════════════════════════════════════
  #  Tab: 主页（问候 + 聊天）
  # ══════════════════════════════════════════════════════
  ```
- Minor sub-sections use `──` dashes:
  ```python
  # ── 构建整体骨架 ──────────────────────────────────────
  ```

**Linting:**
- No `.flake8`, `.pylintrc`, or `ruff.toml` detected; no enforced linter

## Import Organization

**Order in `desktop_pet.py`:**
1. Standard library imports (all in one block, alphabetical by category):
   `tkinter`, `threading`, `json`, `time`, `os`, `re`, `math`, `subprocess`, `random`, `ctypes`

No third-party or local imports — entire project uses only stdlib.

## Error Handling

**Primary pattern:** Broad `except Exception` with silent suppression via `pass`:
```python
def save_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
```

**AI call errors** capture the exception and surface it to the user as a friendly message:
```python
except Exception as e:
    accumulated = f'呜，出了点小问题：{e}'
```

**macOS Objective-C bridge** always wrapped in `try/except Exception: pass` — failure is non-fatal:
```python
try:
    # ctypes / objc calls
    ...
except Exception:
    pass
```

**Pattern for UI callbacks:** Guard with `winfo_exists()` before acting:
```python
if self.win and self.win.winfo_exists():
    self.win.after(0, lambda: self._on_stream_done(final))
```

**No logging** — errors are either silently swallowed or displayed inline in UI status labels. There is no `logging` module usage anywhere.

## UI Patterns

**Widget construction pattern:** All UI built imperatively with tkinter. No data-binding framework. Standard pattern:
```python
th = THEMES[self._theme_mode]
frame = tk.Frame(parent, bg=th['BG_CONTENT'])
toolbar = tk.Frame(frame, bg=th['BG_TOOLBAR'], height=44)
toolbar.pack(fill=tk.X)
toolbar.pack_propagate(False)
tk.Label(toolbar, text='标题', bg=th['BG_TOOLBAR'], fg=th['FG_MAIN'],
         font=('PingFang SC', 13, 'bold')).pack(side=tk.LEFT, padx=16)
```

**Tab system:** All tab frames built once at `_build()` time and stacked via `.grid()` at position `(0,0)`. Visibility toggled with `.tkraise()`:
```python
for frame in self._tab_frames.values():
    frame.grid(row=0, column=0, sticky='nsew')
self._switch_tab('home')
```

**Hover effects:** All interactive widgets use `<Enter>`/`<Leave>` bindings to change `fg` or `bg`. Pattern:
```python
btn.bind('<Enter>', lambda e, b=btn: b.configure(bg=th['BG_HOVER']))
btn.bind('<Leave>', lambda e, b=btn: b.configure(bg=th['BG_WIN']))
```

**Custom rounded shapes:** Drawn on `tk.Canvas` using overlapping arcs and rectangles (no PIL/Pillow). Used for chat bubbles and pill-shaped input bars. See `_rounded_bubble()` and `_draw_pill()` in `desktop_pet.py`.

**Scrollable areas:** Pattern is Canvas + inner Frame + Scrollbar:
```python
canvas = tk.Canvas(frame, bg=th['BG_CONTENT'], highlightthickness=0)
sb = tk.Scrollbar(frame, orient='vertical', command=canvas.yview)
canvas.configure(yscrollcommand=sb.set)
inner = tk.Frame(canvas, bg=th['BG_CONTENT'])
win_id = canvas.create_window((0, 0), window=inner, anchor='nw')
inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
canvas.bind('<Configure>', lambda e: canvas.itemconfig(win_id, width=e.width))
```

**Mouse-wheel scrolling:**
```python
def _scroll(e):
    if abs(e.delta) <= 10:
        canvas.yview_scroll(-e.delta, 'units')
    else:
        canvas.yview_scroll(-1 * (e.delta // 120), 'units')
canvas.bind('<MouseWheel>', _scroll)
```

**Theme switching:** `_recolor_widget()` recursively walks widget tree and remaps known colors from any theme to the target theme using dict lookups. Call after changing `self._theme_mode`.

**Status feedback:** Inline `tk.Label` widgets (e.g., `self._news_status`, `self._settings_status`) are updated with text after async operations. Cleared with `.after(2000, _clear)` when ephemeral.

**Fonts used:**
- UI text: `('PingFang SC', SIZE)` or `('PingFang SC', SIZE, 'bold')`
- Emoji display: `('Apple Color Emoji', SIZE)`
- All sizes are integers passed directly

## Threading Patterns

**Rule:** All background I/O (news fetching, Claude AI streaming, push notifications) runs in daemon threads. All UI updates must happen on the main thread via `self.win.after(0, callback)`.

**Background task pattern:**
```python
def _load_news_async(self, force=False):
    def run():
        content, cached, ts = get_news(force=force)
        sections = parse_news(content)
        # ... process ...
        if self.win and self.win.winfo_exists():
            self.win.after(0, lambda: self._render_news(sections, status))
    threading.Thread(target=run, daemon=True).start()
```

**AI streaming pattern** (`_stream_pet_ai`): Runs in a daemon thread. Calls `subprocess.Popen` with `stream-json` output. For each parsed JSON event, posts a UI update via `self.win.after(0, lambda t=t: self._on_stream_chunk(t))`. Final result posted via `self.win.after(0, lambda: self._on_stream_done(final))`.

**Animation loop:** Driven by `root.after(ANIM_INTERVAL, self._animate)` — 50 ms interval (20 fps). No threads used for animation. The loading spinner in `_show_news_loading` uses `cv.after(16, _animate)` — ~60 fps.

**Guard pattern before all `after` callbacks:**
```python
if self.win and self.win.winfo_exists():
    self.win.after(0, ...)
```

**No locks used.** State variables like `self._chat_thinking` act as soft mutex flags (boolean guards) to prevent double-sending.

## Module Design

**Exports:** No `__all__` defined. Files are scripts run directly, not imported as libraries.

**Entry point:**
```python
if __name__ == '__main__':
    DesktopPet().run()
```

**Utility functions** live at module level before class definitions in `desktop_pet.py`: `load_json`, `save_json`, `load_settings`, `save_settings`, `load_cache`, `save_cache`, `fetch_news_raw`, `get_news`, `parse_news`, `send_notification`, `_translate_titles_with_claude`.

**Private module-level helper** indicated by leading underscore: `_translate_titles_with_claude`.

---

*Convention analysis: 2026-04-16*
