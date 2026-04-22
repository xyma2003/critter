---
phase: 02-weather-tab
plan: "01"
subsystem: weather-service
tags: [weather, service, cache, unit-tests, wttr.in]
dependency_graph:
  requires: []
  provides: [services/weather, WEATHER_FILE, test-infrastructure]
  affects: [config.py, services/weather/__init__.py, tests/]
tech_stack:
  added: [pytest-9.0.3]
  patterns: [fetch/cache service layer, urllib+ssl CERT_NONE, in-memory TTL cache, TDD red-green]
key_files:
  created:
    - services/weather/__init__.py
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_weather_service.py
  modified:
    - config.py
decisions:
  - "Used in-memory _cache dict (not StorageRepository) — weather data expires in 15 min, persisting is unnecessary complexity"
  - "get_cached_data() public function added so callers never import _cache directly"
  - "code_to_emoji fallback is '🌡️' for any unknown weatherCode"
metrics:
  duration: "~15 min"
  completed: "2026-04-22"
  tasks_completed: 2
  files_created: 4
  files_modified: 1
---

# Phase 02 Plan 01: Weather Service Module Summary

**One-liner:** wttr.in fetch/cache service with 900s TTL, URL-encoded city support, emoji code map, and 8 mocked unit tests — zero live network in tests.

## What Was Built

### Task 1: WEATHER_FILE constant + services/weather module

Added `WEATHER_FILE` to `config.py` following the `BOOKMARKS_FILE` pattern.

Created `services/weather/__init__.py` with:
- `WEATHER_TTL = 900` (15 min)
- `WEATHER_EMOJI` dict mapping all wttr.in codes 113–395 to display emojis
- `code_to_emoji(code)` — returns emoji or `'🌡️'` fallback
- `fetch_weather(city, force=False)` — returns `(data_dict | None, from_cache: bool, error: str | None)`
  - Uses `urllib.parse.quote(city, safe='')` for URL encoding
  - SSL context with `CERT_NONE` (matches existing news pattern)
  - Handles `HTTPError` (unknown city → `'找不到城市：{city}'`), `URLError`, `JSONDecodeError`
  - Returns 3-day forecast with `code` key per item
- `is_cached(city)` — TTL-aware check
- `last_fetch_time(city)` — raw timestamp or None
- `get_cached_data(city)` — public accessor; callers never touch `_cache` directly

### Task 2: Unit tests (mocked network)

Created test infrastructure:
- `tests/__init__.py` — package marker
- `tests/conftest.py` — `MOCK_WTTR_RESPONSE` and `mock_wttr_bytes` fixture
- `tests/test_weather_service.py` — 8 tests, all passing, zero live HTTP

| Test | WTHR Req | What it validates |
|------|----------|-------------------|
| `test_parse_current` | WTHR-01 | temp_C, feels_like_C, desc_zh, code, forecast |
| `test_chinese_city` | WTHR-02 | 上海 → %E4%B8%8A%E6%B5%B7 in URL |
| `test_cache_hit` | WTHR-06 | second call returns from_cache=True, urlopen called once |
| `test_cache_ttl` | WTHR-06 | expired cache triggers fresh fetch (urlopen called twice) |
| `test_forecast_three_days` | WTHR-05 | 3-item forecast, all keys present |
| `test_cache_miss_on_force` | WTHR-06 | force=True always hits network |
| `test_unknown_city_error` | WTHR-01 | HTTPError 500 → (None, False, '找不到城市：xyz') |
| `test_code_to_emoji` | — | known codes and fallback |

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: config + service | d077012 | config.py, services/weather/__init__.py |
| Task 2: unit tests | 6698923 | tests/__init__.py, tests/conftest.py, tests/test_weather_service.py |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — this plan is a pure service layer with no UI. No stubs exist.

## Self-Check: PASSED

File existence:
- FOUND: services/weather/__init__.py
- FOUND: config.py (WEATHER_FILE added)
- FOUND: tests/__init__.py
- FOUND: tests/conftest.py
- FOUND: tests/test_weather_service.py

Commits exist:
- FOUND: d077012
- FOUND: 6698923

Test result: 8 passed in 0.03s
