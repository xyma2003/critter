---
phase: 02-weather-tab
plan: "03"
subsystem: weather-ui
tags: [weather, ui, tkinter, forecast, refresh, panel]
dependency_graph:
  requires: [02-02]
  provides: [weather-forecast-cards, weather-refresh-button, _render_forecast, _fmt_forecast_date]
  affects: [ui/panel.py]
tech_stack:
  added: []
  patterns: [per-day weather code emoji lookup, _weather_fetching dedup guard on refresh, force=True cache bypass]
key_files:
  created: []
  modified:
    - ui/panel.py
decisions:
  - "day.get('code', 0) used per forecast day so each card shows its actual weather condition, not a shared fallback (WTHR-05)"
  - "_do_refresh inner closure checks _weather_fetching before calling _load_weather_async to prevent duplicate concurrent fetches (WTHR-06)"
  - "force=True passed on manual refresh to bypass 15-min WEATHER_TTL cache in services/weather/__init__.py"
  - "_render_forecast(data) called at end of _render_current_weather so forecast always redraws with current conditions"
metrics:
  duration: "~5 min"
  completed: "2026-04-22"
  tasks_completed: 2
  files_created: 0
  files_modified: 1
---

# Phase 02 Plan 03: Forecast Cards and Refresh Button Summary

**One-liner:** 3-day forecast cards with per-day condition emojis and a Refresh button (duplicate-fetch guard + force=True cache bypass) completing Phase 2 weather tab.

## What Was Built

### Task 1: Add _render_forecast and wire into _render_current_weather

Added 2 methods to `MainPanel` in `ui/panel.py`:

| Method | Responsibility |
|--------|---------------|
| `_render_forecast(data)` | Renders 3-day forecast section below current conditions card: header label, row of 3 cards each showing date label, weather emoji, condition description, high/low temps |
| `_fmt_forecast_date(iso_date, index)` | Formats ISO date string — index 0 → '今天', index 1 → '明天', index 2+ → '%-m/%-d' |

- `day.get('code', 0)` used for per-day emoji so each forecast card shows its own weather condition
- `_render_forecast(data)` called at end of `_render_current_weather` after the city label line

### Task 2: Add Refresh button with 15-min cache guard to weather toolbar

- `↻ 刷新` `tk.Label` added to weather toolbar (packed `side=tk.RIGHT`)
- `_do_refresh()` inner closure: checks `city in self._weather_fetching` before calling `_load_weather_async(city, force=True)` to prevent concurrent duplicate fetches
- `force=True` bypasses the 15-minute `WEATHER_TTL` cache in the service layer
- Hover states toggle `fg` between `FG_ACCENT` and `FG_MAIN`
- Reference stored as `self._weather_refresh_btn`

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: _render_forecast + _fmt_forecast_date | 764c386 | ui/panel.py |
| Task 2: Refresh button with cache guard | 63eac5e | ui/panel.py |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. All forecast data comes from `data['forecast']` populated by the live `fetch_weather()` call — no hardcoded or mock data.

## Checkpoint Status

Task 3 (`type="checkpoint:human-verify"`) reached. Awaiting human verification of the complete weather tab in the running application.

## Self-Check: PASSED

Files modified:
- FOUND: ui/panel.py (syntax OK)

Commits exist:
- FOUND: 764c386 (feat(02-03): add _render_forecast and _fmt_forecast_date methods)
- FOUND: 63eac5e (feat(02-03): add Refresh button with 15-min cache guard to weather toolbar)

Verification results:
- Method count grep: 3 (def _render_forecast + def _fmt_forecast_date + _weather_refresh_btn assignment) — PASS
- day.get('code', 0) present in _render_forecast — PASS
- force=True in weather refresh context — PASS
- Weather service tests: 8/8 passed — PASS
- Syntax: OK — PASS
