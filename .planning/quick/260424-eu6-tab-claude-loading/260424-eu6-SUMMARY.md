---
phase: quick
plan: 260424-eu6
subsystem: ui/weather-tab
tags: [weather, claude-cli, outfit-advice, loading-spinner, caching]
dependency_graph:
  requires: [services/weather, config.CLAUDE_CLI]
  provides: [_outfit_cache, _fetch_outfit_advice_async, outfit-advice-card]
  affects: [ui/panel.py, _render_current_weather]
tech_stack:
  added: []
  patterns: [background-thread-with-win.after-callback, braille-spinner-animation, in-memory-cache]
key_files:
  modified: [ui/panel.py]
decisions:
  - "Use self.win.after(0, callback) for thread-safe main-thread UI updates (consistent with existing pattern in _load_weather_async)"
  - "Cache key is f'{city}:{temp_C}' — same city+temp always returns same advice without re-calling Claude"
  - "Braille spinner (_FRAMES tuple) reuses same animation pattern as _render_weather_loading for consistency"
  - "Fallback text '今天天气不错，出门记得看看穿搭哦～' shown when Claude call fails — no crash"
metrics:
  duration_min: 4
  completed_date: "2026-04-24"
  tasks_completed: 2
  files_modified: 1
---

# Phase quick Plan 260424-eu6: Weather Tab Outfit Advice Summary

One-liner: 天气 Tab 穿搭建议卡片：Claude CLI 宠物口吻生成 + Braille spinner loading + city:temp_C 内存缓存

## What Was Built

Added a pet-voice outfit advice card to the weather tab's current conditions view. The card appears below the city label and above the forecast row. It displays a Braille spinner animation while Claude CLI generates a one-sentence recommendation, then replaces the spinner with the advice text. Results are cached in `_outfit_cache` by `city:temp_C` key so repeat views are instant.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | 添加 _outfit_cache 及 _fetch_outfit_advice_async 后台调用 | a161a4a | ui/panel.py |
| 2 | 在 _render_current_weather 插入穿搭建议卡片（含 loading 状态） | d01200a | ui/panel.py |

## Implementation Notes

### Task 1 — Cache + async caller
- `self._outfit_cache: dict = {}` added after `self._weather_fetching` in `__init__`
- `_fetch_outfit_advice_async(city, temp_C, desc_zh, on_done)` added after `_load_weather_async`
- Cache hit path: `self.win.after(0, lambda: on_done(cached_text))` — no subprocess spawned
- Cache miss path: spawns daemon thread, calls `claude --print --output-format json`, parses `result` field
- Thread-safe: all widget callbacks dispatched via `self.win.after(0, ...)` after checking `self.win.winfo_exists()`

### Task 2 — UI card with spinner
- `outfit_card` frame + `outfit_lbl` label inserted after city label pack, before `self._render_forecast(data)`
- Initial text `'⏳  生成中…'` replaced by spinner immediately via `_spin()` closure
- `_spinning[0]` flag stops the `after(100, _spin)` loop once advice arrives
- `_on_advice(text)` callback: sets `fg=th['FG_MAIN']` and advice text (or fallback if `text` is empty)
- `tk.TclError` caught in both `_spin` and `_on_advice` to handle widget-destroyed-before-callback edge case

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] root reference corrected from `self._root` to `self.win`**
- **Found during:** Task 1 implementation — plan specified `self._root` but the actual attribute in MainPanel is `self.win`
- **Issue:** Plan said "若是 `self.root` 则使用 `self.root`，grep 后确认" — confirmed via grep that the attribute is `self.win`
- **Fix:** Used `self.win.after(0, ...)` and `self.win.winfo_exists()` throughout both cache-hit path and thread callback
- **Files modified:** ui/panel.py
- **Commit:** a161a4a

## Verification

```
python3.11 -c "import ast; ast.parse(open('ui/panel.py').read()); print('syntax OK')"
# syntax OK
```

## Known Stubs

None — advice card fetches live data from Claude CLI; cache and fallback are both production-ready.

## Checkpoint Status

Plan execution paused at `checkpoint:human-verify` (Task 3). Tasks 1 and 2 are committed. Awaiting human verification that:
1. Outfit advice card renders below city label in weather tab
2. Braille spinner animates while Claude is generating
3. Advice text appears after ~5-15 seconds
4. Cache prevents duplicate calls on same city+temp refresh

## Self-Check: PASSED

- ui/panel.py: modified (a161a4a, d01200a)
- _outfit_cache in __init__: confirmed present
- _fetch_outfit_advice_async method: confirmed present
- outfit card insertion in _render_current_weather: confirmed present
- Both commits exist in git log
