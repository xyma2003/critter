---
phase: 02-weather-tab
plan: "02"
subsystem: weather-ui
tags: [weather, ui, tkinter, async, panel, tab]
dependency_graph:
  requires: [02-01]
  provides: [weather-tab-ui, _build_weather_tab, city-list-sidebar, current-conditions-card]
  affects: [ui/panel.py, weather.json]
tech_stack:
  added: []
  patterns: [lazy-load tab init, daemon-thread + win.after(0) dispatch, _weather_fetching dedup set, get_cached_data public API]
key_files:
  created: []
  modified:
    - ui/panel.py
decisions:
  - "Used _weather_fetching set() to guard against duplicate concurrent fetches for the same city"
  - "_render_current_weather uses get_cached_data(city) public service API — no direct _cache import in panel.py (established in Plan 01)"
  - "City list persistence loads lazily on first tab switch (mirrors _news_loaded pattern)"
metrics:
  duration: "~20 min"
  completed: "2026-04-22"
  tasks_completed: 2
  files_created: 0
  files_modified: 1
---

# Phase 02 Plan 02: Weather Tab UI Summary

**One-liner:** Weather tab with city sidebar (add/delete/select), async wttr.in fetch via daemon thread + win.after(0) dispatch, and current conditions card (emoji, temp, desc_zh, feels_like).

## What Was Built

### Task 1: Register weather tab in nav bar and _build() method

- Added `WEATHER_FILE` to `from config import` line
- Added `from services.weather import fetch_weather, is_cached, last_fetch_time, get_cached_data, code_to_emoji`
- Added 4 instance attributes to `__init__`: `_weather_cities`, `_weather_selected`, `_weather_loaded`, `_weather_fetching`
- Inserted `('weather', '🌤', '天气')` into `tab_defs` between 便签 and 设置 (now 6 tabs)
- Added `self._tab_frames['weather'] = self._build_weather_tab(self._content_host)` in `_build()`
- Added weather lazy-load block in `_switch_tab`: on first visit, loads `weather.json`, sets selected city, rebuilds list, triggers async fetch for all cities

### Task 2: Implement _build_weather_tab and all helpers

Created 7 methods in `MainPanel`:

| Method | Responsibility |
|--------|---------------|
| `_build_weather_tab(parent)` | Builds toolbar (添加 btn + city entry), 180px left sidebar, right content panel |
| `_rebuild_city_list()` | Clears and redraws city list rows with selection highlight, accent bar, × delete button, hover states |
| `_weather_add_city(city)` | Dedup check, appends to list, saves to weather.json, triggers async fetch |
| `_weather_delete_city(city)` | Removes from list, saves to weather.json, auto-selects next city |
| `_load_weather_async(city, force)` | Dedup guard via `_weather_fetching` set, daemon thread fetch, `win.after(0, ...)` dispatch |
| `_on_weather_loaded(city, data, err)` | Updates status label, renders weather if selected city matches |
| `_render_current_weather()` | Renders current conditions card: emoji (code_to_emoji), temp °C, desc_zh, 体感 feels_like_C |

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: nav registration + attrs | 8359d21 | ui/panel.py |
| Task 2: all 7 weather methods | db8cf70 | ui/panel.py |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. The weather tab is fully wired:
- City list loads from `weather.json` via `load_json(WEATHER_FILE, [])`
- Async fetch writes to in-memory `_cache` via `fetch_weather()`
- `_render_current_weather` reads via `get_cached_data()` — no stub data

## Self-Check: PASSED

Files modified:
- FOUND: ui/panel.py (syntax OK, 7 methods present)

Commits exist:
- FOUND: 8359d21 (feat: register weather tab)
- FOUND: db8cf70 (feat: implement weather tab UI)

Verification results:
- Method count: 7 (PASS)
- WEATHER_FILE: import + 4 usages (PASS)
- _weather_fetching: 4 occurrences — init, guard check, add, discard (PASS)
- No direct _cache import: PASS
- Weather service tests: 8 passed (PASS)
