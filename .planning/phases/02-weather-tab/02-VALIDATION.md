# Phase 02-weather-tab — Validation Architecture

_Generated from 02-RESEARCH.md § Validation Architecture_

---

## Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (Wave 0 installs if absent) |
| Config file | None — Wave 0 creates `tests/__init__.py` + `tests/conftest.py` |
| Quick run command | `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -m pytest tests/ -x -q` |
| Full suite command | `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -m pytest tests/ -v` |

---

## Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File |
|--------|----------|-----------|-------------------|------|
| WTHR-01 | fetch_weather returns temp_C, feels_like_C, desc_zh, code, forecast | unit (mock) | `python3.11 -m pytest tests/test_weather_service.py::test_parse_current -x` | tests/test_weather_service.py |
| WTHR-02 | Chinese city name (上海) fetches valid data; URL-encoded correctly | unit (mock) | `python3.11 -m pytest tests/test_weather_service.py::test_chinese_city -x` | tests/test_weather_service.py |
| WTHR-03 | delete_city removes from list and saves to JSON | human-verify (checkpoint in 02-03) | n/a — UI interaction | — |
| WTHR-04 | fetch_weather returns immediately (< 0.01s) on cache hit | unit (mock) | `python3.11 -m pytest tests/test_weather_service.py::test_cache_hit -x` | tests/test_weather_service.py |
| WTHR-05 | fetch_weather returns 3-item forecast list with date, max_C, min_C, desc, code | unit (mock) | `python3.11 -m pytest tests/test_weather_service.py::test_forecast_three_days -x` | tests/test_weather_service.py |
| WTHR-06 | Second call within 15 min returns cached data without HTTP request | unit (mock) | `python3.11 -m pytest tests/test_weather_service.py::test_cache_ttl -x` | tests/test_weather_service.py |

---

## Test Files

| File | Purpose | Created By |
|------|---------|------------|
| `tests/__init__.py` | Makes tests a Python package | Plan 01, Task 2 |
| `tests/conftest.py` | Shared pytest fixtures (MOCK_WTTR_RESPONSE, mock_wttr_bytes) | Plan 01, Task 2 |
| `tests/test_weather_service.py` | 8 unit tests covering all 6 WTHR service requirements | Plan 01, Task 2 |

---

## Test Cases in test_weather_service.py

| Test | Covers | Mock Strategy |
|------|--------|---------------|
| `test_parse_current` | WTHR-01 field parsing | `patch('urllib.request.urlopen')` → MOCK_WTTR_RESPONSE |
| `test_chinese_city` | WTHR-02 URL encoding | mock urlopen; assert URL contains `%E4%B8%8A%E6%B5%B7` |
| `test_cache_hit` | WTHR-04/WTHR-06 cache | call twice; assert urlopen.call_count == 1 |
| `test_cache_ttl` | WTHR-06 TTL expiry | monkeypatch ts to time.time()-901; assert urlopen.call_count == 2 |
| `test_forecast_three_days` | WTHR-05 forecast length | assert len(result['forecast']) == 3; each item has date, max_C, min_C, desc, code |
| `test_cache_miss_on_force` | WTHR-06 force bypass | call twice with force=True; assert urlopen.call_count == 2 |
| `test_unknown_city_error` | WTHR-01 error handling | mock HTTPError(500, body='location not found: xyz') |
| `test_code_to_emoji` | code_to_emoji function | pure function; no mock needed |

---

## Sampling Rate

- **Per task commit:** `python3.11 -m pytest tests/test_weather_service.py -x -q`
- **Per wave merge:** `python3.11 -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

---

## Wave 0 Gaps (created by Plan 01, Task 2)

- [x] `tests/__init__.py` — make tests a package
- [x] `tests/conftest.py` — shared fixtures (MOCK_WTTR_RESPONSE, mock_wttr_bytes fixture)
- [x] `tests/test_weather_service.py` — 8 tests; zero live HTTP calls
- [x] Framework install: `python3.11 -m pip install pytest` — if not already present

---

## Notes

- WTHR-04's "does not block UI" aspect is an integration concern. The unit test covers the
  cache-hit synchronous path. The async thread dispatch is verified by the human-verify
  checkpoint in Plan 03, Task 3.
- WTHR-03 (city delete) is a UI operation with no service-layer logic; it is covered by the
  Plan 03 human-verify checkpoint rather than a unit test.
