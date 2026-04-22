# Phase 2: Weather Tab - Research

**Researched:** 2026-04-22
**Domain:** wttr.in API (stdlib urllib) + tkinter tab extension + JSON persistence
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WTHR-01 | 用户可以在天气 Tab 查看当前城市的实时天气（温度、天气状况、体感温度） | wttr.in ?format=j1 provides temp_C, FeelsLikeC, weatherDesc; lang_zh gives Chinese desc |
| WTHR-02 | 用户可以添加任意城市到天气列表（支持中英文城市名） | wttr.in accepts URL-encoded city names including Chinese (verified: 上海 returns valid data) |
| WTHR-03 | 用户可以删除已添加的城市 | StorageRepository.remove() pattern already in codebase; city list is a JSON collection |
| WTHR-04 | 天气数据通过 wttr.in 免费 API 获取，异步加载不阻塞 UI | threading.Thread + win.after(0, callback) pattern already used for news tab |
| WTHR-05 | 用户可以查看未来3天天气预报 | wttr.in j1 `weather` array always returns exactly 3 days with maxtempC/mintempC/date |
| WTHR-06 | 天气 Tab 有手动刷新按钮，数据缓存15分钟避免频繁请求 | Per-city timestamp cache dict in memory + optional JSON persistence; 900s TTL |
</phase_requirements>

## Summary

Phase 2 adds a Weather tab as the 6th entry in the existing `tab_defs` list in `MainPanel._build()`. The implementation follows the same structural pattern as the News tab: a toolbar with status/controls, a scrollable city list on the left, and a content panel on the right showing current conditions plus a 3-day forecast. All data is fetched via Python's `urllib.request` from `wttr.in`'s free JSON API (`?format=j1`) — no API key needed.

Persistence is a two-layer concern: the city list (names + order) is stored in a new `weather.json` file via the existing `save_json`/`load_json` functions; per-city weather data is cached in-memory (dict keyed by city name) with a 15-minute TTL, refreshed on demand. This avoids the complexity of a full `StorageRepository` while staying consistent with the project's JSON-first data pattern.

The critical async constraint (WTHR-04) is already solved by the project's established pattern: launch a `threading.Thread(daemon=True)` for network I/O, then post GUI updates back with `self.win.after(0, callback)`. The only new concern is managing concurrent fetches (e.g., user clicks Refresh while a fetch is already running) — use a per-city in-progress flag.

**Primary recommendation:** Create `services/weather/__init__.py` as the fetch/cache layer (mirroring `services/news`), add `WEATHER_FILE` to `config.py`, and build `_build_weather_tab()` in `ui/panel.py` following the news tab's canvas+scrollbar+inner_frame pattern.

---

## Project Constraints (from CLAUDE.md)

- **Tech Stack**: Python 3.11 + tkinter — zero third-party UI libraries. All HTTP via `urllib.request` (stdlib).
- **Python path**: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11`
- **Modular architecture**: New weather service goes in `services/weather/`, new constant in `config.py`, tab builder in `ui/panel.py`
- **Data storage**: JSON files; data access must be through repository/helper classes, not raw open() calls at the UI layer
- **No test framework present**: nyquist_validation applies but no existing test files; Wave 0 must create infrastructure
- **Naming**: tab builder method must be `_build_weather_tab(parent)` to match the established `_build_<tab>_tab(parent)` convention
- **Async pattern**: background I/O on `threading.Thread(daemon=True)`, GUI updates via `self.win.after(0, callback)`

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `urllib.request` | stdlib | HTTP GET to wttr.in | Already used in news fetch; project forbids third-party libs |
| `urllib.error` | stdlib | HTTPError / URLError handling | Companion to urllib.request |
| `ssl` | stdlib | HTTPS with disabled cert verify (same pattern as news) | wttr.in is HTTPS; project uses `ssl.CERT_NONE` pattern |
| `json` | stdlib | Parse API response; serialize city list | Already used everywhere |
| `threading` | stdlib | Non-blocking fetch | Same pattern as `_load_news_async` |
| `time` | stdlib | Cache TTL (compare to `time.time()`) | Same as news cache pattern |
| `tkinter` | stdlib | All UI widgets | Only UI framework allowed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `urllib.parse.quote` | stdlib | URL-encode city names with spaces/Chinese chars | Required — city names go directly in URL path |
| `datetime` | stdlib | Format forecast dates (YYYY-MM-DD → M/D display) | For WTHR-05 forecast date display |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `urllib.request` | `requests` (third-party) | requests is cleaner but violates zero-dependency constraint |
| wttr.in | OpenWeatherMap / AccuWeather | Require API keys; wttr.in is free, no registration |
| In-memory dict cache | Full StorageRepository | Weather data is ephemeral (stale in 15 min); persisting to disk adds complexity without benefit |

**Installation:** None — stdlib only.

---

## wttr.in API Reference

**Verified live against the actual API (2026-04-22).**

### Endpoint
```
GET https://wttr.in/{city}?format=j1&lang=zh
```
- `{city}`: any city name, URL-encoded (supports Chinese: `上海` → `%E4%B8%8A%E6%B5%B7`)
- `format=j1`: returns structured JSON (not HTML)
- `lang=zh`: adds `lang_zh` key to `current_condition` with Chinese weather description

### Current Conditions (`current_condition[0]`)
| Key | Type | Example | Notes |
|-----|------|---------|-------|
| `temp_C` | string | `"18"` | Current temperature in Celsius |
| `FeelsLikeC` | string | `"18"` | Feels-like temperature |
| `weatherDesc` | list[dict] | `[{"value": "Sunny"}]` | English description |
| `lang_zh` | list[dict] | `[{"value": "晴"}]` | Chinese description (requires `lang=zh`) |
| `weatherCode` | string | `"113"` | Numeric code for emoji mapping |
| `humidity` | string | `"45"` | Humidity % |

### 3-Day Forecast (`weather` array, always 3 items)
| Key | Type | Example | Notes |
|-----|------|---------|-------|
| `date` | string | `"2026-04-22"` | ISO date string |
| `maxtempC` | string | `"24"` | High temp |
| `mintempC` | string | `"13"` | Low temp |
| `hourly[4]` | dict | midday hour | Use `weatherDesc` from hourly[4] for midday condition |

### Error Handling
- **Unknown city**: HTTP 500, body is plain text `"location not found: ..."` — raises `urllib.error.HTTPError` with `code=500`
- **Network timeout**: `urllib.error.URLError` — set `timeout=10`
- **Empty/malformed JSON**: `json.JSONDecodeError`

---

## Architecture Patterns

### Recommended Project Structure
```
config.py                    # Add: WEATHER_FILE constant
services/
└── weather/
    └── __init__.py          # fetch_weather(city), WttrCache
ui/
└── panel.py                 # _build_weather_tab(), _load_weather_async(), etc.
data/
└── (no new module needed — use load_json/save_json directly for city list)
```

### Pattern 1: Weather Service Module (mirrors services/news)
**What:** Isolated fetch + cache layer; UI calls fetch, service handles TTL
**When to use:** Any network data access

```python
# services/weather/__init__.py
import json, time, urllib.request, urllib.error, urllib.parse, ssl, threading

WEATHER_TTL = 15 * 60  # 900 seconds

_cache = {}          # {city_name: {'data': {...}, 'ts': float}}
_locks = {}          # {city_name: threading.Lock()}  — prevent duplicate fetches


def _get_lock(city):
    if city not in _locks:
        _locks[city] = threading.Lock()
    return _locks[city]


def _build_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch_weather(city, force=False):
    """
    Returns (data_dict, from_cache: bool, error_msg: str | None).
    data_dict keys: temp_C, feels_like_C, desc_zh, code, forecast (list of 3 dicts).
    """
    cached = _cache.get(city)
    if cached and not force and (time.time() - cached['ts'] < WEATHER_TTL):
        return cached['data'], True, None

    encoded = urllib.parse.quote(city, safe='')
    url = f'https://wttr.in/{encoded}?format=j1&lang=zh'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Critter/1.0'})
        ctx = _build_ctx()
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            raw = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        if 'location not found' in body.lower():
            return None, False, f'找不到城市：{city}'
        return None, False, f'HTTP {e.code}: {e.reason}'
    except urllib.error.URLError as e:
        return None, False, f'网络错误：{e.reason}'
    except json.JSONDecodeError:
        return None, False, '解析失败'

    cc = raw['current_condition'][0]
    forecast = []
    for day in raw.get('weather', [])[:3]:
        mid_desc = ''
        hourly = day.get('hourly', [])
        if len(hourly) > 4:
            lang_list = hourly[4].get('lang_zh') or hourly[4].get('weatherDesc') or []
        else:
            lang_list = day.get('hourly', [{}])[0].get('lang_zh') or []
        if lang_list:
            mid_desc = lang_list[0].get('value', '')
        forecast.append({
            'date': day['date'],
            'max_C': day['maxtempC'],
            'min_C': day['mintempC'],
            'desc': mid_desc,
        })

    lang_zh = cc.get('lang_zh') or []
    desc_zh = lang_zh[0].get('value', '') if lang_zh else (
        (cc.get('weatherDesc') or [{}])[0].get('value', ''))

    data = {
        'temp_C': cc['temp_C'],
        'feels_like_C': cc['FeelsLikeC'],
        'desc_zh': desc_zh,
        'code': int(cc.get('weatherCode', 0)),
        'forecast': forecast,
    }
    _cache[city] = {'data': data, 'ts': time.time()}
    return data, False, None


def is_cached(city):
    c = _cache.get(city)
    return bool(c and (time.time() - c['ts'] < WEATHER_TTL))


def last_fetch_time(city):
    c = _cache.get(city)
    return c['ts'] if c else None
```

### Pattern 2: City List Persistence (reuse load_json/save_json)
**What:** City names stored as a JSON array in `weather.json`
**When to use:** Simple ordered list — StorageRepository is overkill here

```python
# In ui/panel.py (or a helper)
from config import WEATHER_FILE
from data.settings import load_json, save_json

def _load_city_list():
    return load_json(WEATHER_FILE, [])

def _save_city_list(cities):
    save_json(WEATHER_FILE, cities)
```

### Pattern 3: Tab Registration (existing _build loop)
**What:** Add the 6th tab entry to `tab_defs` in `_build()`
**When to use:** Exact same pattern as all 5 existing tabs

```python
# In _build(), add to tab_defs list:
tab_defs = [
    ('home',     '🏠', '主页'),
    ('news',     '📰', '新闻'),
    ('pet',      '🐾', '宠物'),
    ('notes',    '📝', '便签'),
    ('weather',  '🌤', '天气'),   # NEW — 6th entry
    ('settings', '⚙️', '设置'),
]

# Add frame build call:
self._tab_frames['weather'] = self._build_weather_tab(self._content_host)
```

### Pattern 4: Async Fetch with win.after
**What:** Non-blocking fetch; result posted back to main thread
**When to use:** Any network operation in a tab — exactly mirrors `_load_news_async`

```python
def _load_weather_async(self, city, force=False):
    def run():
        data, from_cache, err = fetch_weather(city, force=force)
        if self.win and self.win.winfo_exists():
            self.win.after(0, lambda: self._on_weather_loaded(city, data, err))
    threading.Thread(target=run, daemon=True).start()
```

### Pattern 5: Weather Code to Emoji
**What:** Map wttr.in numeric code to display emoji; avoids rendering weather icon URLs
**When to use:** All current condition and forecast displays

```python
WEATHER_EMOJI = {
    113: '☀️', 116: '⛅', 119: '☁️', 122: '☁️',
    143: '🌫️', 176: '🌦️', 179: '🌨️', 200: '⛈️',
    248: '🌫️', 260: '🌫️', 263: '🌦️', 266: '🌧️',
    293: '🌦️', 296: '🌧️', 302: '🌧️', 308: '🌧️',
    317: '🌨️', 320: '🌨️', 323: '🌨️', 326: '🌨️',
    338: '❄️', 353: '🌦️', 356: '🌧️', 368: '🌨️',
    371: '❄️', 386: '⛈️', 389: '⛈️', 395: '⛈️',
}

def code_to_emoji(code):
    return WEATHER_EMOJI.get(int(code), '🌡️')
```

### Pattern 6: UI Layout — Two-Column Within Tab
**What:** Left sidebar = city list; Right panel = current + forecast
**When to use:** WTHR-01 + WTHR-02 + WTHR-05 all need to display simultaneously

```
┌──────────────────────────────────────────────────────┐
│ 天气  [城市输入框] [添加]   [↻ 刷新]  [状态文字]       │  toolbar (44px)
├────────────────┬─────────────────────────────────────┤
│ 城市列表        │  当前天气区                           │
│ ──────────     │  ☀️  18°C  · 晴  · 体感 18°C          │
│ ● 北京   ×     │                                       │
│   上海   ×     │  3天预报                               │
│   Tokyo  ×     │  ┌──────┬──────┬──────┐              │
│                │  │ 今天 │ 明天 │后天  │              │
│  [空列表提示]   │  │ ⛅   │ ☀️   │ ☁️   │              │
│                │  │24/13 │27/13 │27/15 │              │
│                │  └──────┴──────┴──────┘              │
└────────────────┴─────────────────────────────────────┘
```

Left panel ~180px wide (fixed); right panel fills remainder.

### Anti-Patterns to Avoid
- **Blocking fetch on main thread**: Never call `fetch_weather()` directly in a button handler or `<Button-1>` binding — always wrap in `threading.Thread`
- **One StorageRepository per city**: The city list is a plain ordered array, not a collection of item dicts — don't force the bookmark pattern here
- **Destroying and recreating the weather tab frame**: Use `pack_forget`/`pack` or update widget text in-place; destroying the frame loses the city list widget references
- **URL without encoding**: `urllib.parse.quote(city, safe='')` is required — spaces and Chinese chars in the URL path cause 404 or garbled responses
- **Concurrent duplicate fetches**: Guard with `_fetching_cities: set` in MainPanel state; skip a fetch if the city is already being fetched

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP request | Custom socket code | `urllib.request.urlopen` | stdlib, already used in project |
| URL encoding city names | Manual `%xx` replacement | `urllib.parse.quote(city, safe='')` | Handles Unicode correctly |
| SSL for HTTPS | Skip SSL or write custom | `ssl.create_default_context()` with `CERT_NONE` | Same pattern as existing fetch_news |
| Concurrent fetch guard | Complex thread pool | Simple `set` flag (`_weather_fetching`) | Single fetch per city is enough |
| Weather condition icon | Download PNG, embed in tkinter | Weather code → emoji dict | Emoji renders natively in tkinter without Pillow; no download needed |
| Cache expiry | Custom cache class | `time.time()` comparison against stored timestamp | Matches news cache pattern exactly |

**Key insight:** wttr.in returns all needed data (current + 3-day forecast) in a single request. No second API call for forecast. The emoji approach avoids all image rendering complexity.

---

## Common Pitfalls

### Pitfall 1: Chinese City Name Encoding
**What goes wrong:** `urllib.request.urlopen('https://wttr.in/上海?format=j1')` — Python's urlopen does NOT auto-encode the path; the raw Unicode characters cause a `UnicodeEncodeError` or a malformed request
**Why it happens:** `urllib.request` requires an ASCII-safe URL; the URL must be pre-encoded
**How to avoid:** Always apply `urllib.parse.quote(city, safe='')` before inserting into the URL string
**Warning signs:** `UnicodeEncodeError` or HTTP 404 for valid Chinese city names

### Pitfall 2: `weatherDesc` is a List, Not a String
**What goes wrong:** `cc['weatherDesc']` returns `[{"value": "Sunny"}]`, not `"Sunny"` — direct string use causes `TypeError`
**Why it happens:** wttr.in wraps all string fields in list-of-dict for localisation
**How to avoid:** Always extract with `(cc.get('weatherDesc') or [{}])[0].get('value', '')`
**Warning signs:** TypeError on string operations, empty display strings

### Pitfall 3: Stale City Selection After Delete
**What goes wrong:** User deletes the currently-selected city; right panel still shows that city's data with no error shown
**Why it happens:** `_selected_city` instance attribute still holds the deleted name
**How to avoid:** In the delete handler, if `self._weather_selected == deleted_city`, auto-select the first remaining city (or show an empty state if the list is empty)
**Warning signs:** Right panel shows weather for a city that no longer appears in the list

### Pitfall 4: Rapid Refresh Clicks Triggering Multiple Fetches
**What goes wrong:** User clicks Refresh multiple times quickly; multiple threads call wttr.in, last response "wins" but intermediate responses may corrupt UI
**Why it happens:** Each click launches a new thread; no guard
**How to avoid:** Track `_weather_fetching: set[str]`; in `_load_weather_async`, skip if city already in set; remove from set in `_on_weather_loaded`
**Warning signs:** Flickering weather display, intermittent "wrong city" data shown

### Pitfall 5: 500 Response Parsed as JSON
**What goes wrong:** `json.loads(resp.read())` on a 500 response — `urllib.urlopen` raises `HTTPError` for 4xx/5xx, not returning the response body in the normal flow
**Why it happens:** Developers sometimes forget that urlopen raises on non-200 status
**How to avoid:** Always wrap `urlopen` in `except urllib.error.HTTPError as e`; read `e.read()` for error body if needed
**Warning signs:** Unhandled `HTTPError` exceptions in the background thread that silently kill the thread

### Pitfall 6: `_switch_tab` Does Not Trigger Weather Load
**What goes wrong:** User opens the Weather tab for the first time; cities were loaded from JSON but weather data was never fetched
**Why it happens:** The news tab lazy-loads on first switch via `_switch_tab` checking `_news_loaded`; need same pattern for weather
**How to avoid:** Add `_weather_loaded = False` flag; in `_switch_tab` when `key == 'weather'`, trigger first load of all cities if not already loaded
**Warning signs:** Empty weather panel on first tab open despite cities being in the list

---

## Code Examples

Verified by live API test (2026-04-22):

### Fetching Current Conditions and Forecast
```python
import urllib.request, urllib.error, urllib.parse, json, ssl

def fetch_weather(city):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    encoded = urllib.parse.quote(city, safe='')
    url = f'https://wttr.in/{encoded}?format=j1&lang=zh'
    req = urllib.request.Request(url, headers={'User-Agent': 'Critter/1.0'})

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            raw = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        if 'location not found' in body.lower():
            return None, f'找不到城市：{city}'
        return None, f'请求失败 ({e.code})'
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        return None, str(e)

    cc = raw['current_condition'][0]
    lang_zh = (cc.get('lang_zh') or [{}])[0].get('value', '')
    if not lang_zh:
        lang_zh = (cc.get('weatherDesc') or [{}])[0].get('value', '')

    return {
        'temp_C':       cc['temp_C'],
        'feels_like_C': cc['FeelsLikeC'],
        'desc':         lang_zh,
        'code':         int(cc.get('weatherCode', 0)),
        'forecast': [
            {
                'date':  day['date'],
                'max_C': day['maxtempC'],
                'min_C': day['mintempC'],
                'desc':  (day.get('hourly') or [{}])[4 if len(day.get('hourly', [])) > 4 else 0]
                         .get('lang_zh', [{}])[0].get('value', ''),
            }
            for day in raw.get('weather', [])[:3]
        ],
    }, None
```

### City List Persistence
```python
# config.py addition:
WEATHER_FILE = os.path.expanduser("~/.openclaw/workspace/desktop-pet/weather.json")

# In MainPanel:
from config import WEATHER_FILE
from data.settings import load_json, save_json

self._weather_cities = load_json(WEATHER_FILE, [])   # list of city name strings
self._weather_selected = self._weather_cities[0] if self._weather_cities else None

def _weather_add_city(self, city):
    city = city.strip()
    if not city or city in self._weather_cities:
        return
    self._weather_cities.append(city)
    save_json(WEATHER_FILE, self._weather_cities)
    self._rebuild_city_list()
    self._load_weather_async(city)

def _weather_delete_city(self, city):
    if city in self._weather_cities:
        self._weather_cities.remove(city)
    save_json(WEATHER_FILE, self._weather_cities)
    if self._weather_selected == city:
        self._weather_selected = self._weather_cities[0] if self._weather_cities else None
    self._rebuild_city_list()
    self._render_current_weather()
```

### 15-Minute Cache with Refresh Button Guard
```python
# services/weather/__init__.py
_cache = {}   # {city: {'data': dict, 'ts': float}}
WEATHER_TTL = 900  # 15 minutes

def fetch_weather(city, force=False):
    cached = _cache.get(city)
    if cached and not force and (time.time() - cached['ts'] < WEATHER_TTL):
        return cached['data'], True, None
    # ... fetch from wttr.in ...
    _cache[city] = {'data': data, 'ts': time.time()}
    return data, False, None
```

### Forecast Date Formatting
```python
from datetime import datetime

def _fmt_forecast_date(iso_date, index):
    """'2026-04-22' → '今天', '明天', or '04/24'"""
    if index == 0: return '今天'
    if index == 1: return '明天'
    try:
        dt = datetime.strptime(iso_date, '%Y-%m-%d')
        return dt.strftime('%-m/%-d')   # '4/24' on macOS
    except ValueError:
        return iso_date[5:]  # fallback: '04-24'
```

---

## State of the Art

| Old Approach | Current Approach | Notes |
|--------------|------------------|-------|
| WeatherAPI / OpenWeatherMap (requires key) | wttr.in (no key) | wttr.in is the standard free option for personal tools |
| Downloading weather icon PNG images | weatherCode → emoji dict | Emoji renders in tkinter natively; no Pillow needed |
| Separate forecast API call | Single j1 endpoint | wttr.in j1 includes both current + 3-day in one request |

---

## Open Questions

1. **Chinese city name resolution accuracy**
   - What we know: `上海` resolves to "Pootung" (浦东) — the wttr.in location resolver maps it to the nearest area name, which may differ from what the user typed
   - What's unclear: Whether ambiguous Chinese city names (e.g., `南京`, `武汉`) resolve correctly
   - Recommendation: Show the resolved `nearest_area.areaName` in the UI alongside the user's input name; users can see what was actually matched

2. **City list ordering after delete**
   - What we know: `_weather_cities` is a plain Python list; deletion is `list.remove()`
   - What's unclear: Should deleted city's slot be filled by next city automatically, or should empty state be shown?
   - Recommendation: Auto-select the next city in the list if one exists; show empty-state placeholder if list becomes empty

3. **Tab position (5th vs 6th slot)**
   - What we know: Current order is home/news/pet/notes/settings; nav bar has room for more items
   - What's unclear: Whether inserting before settings (5th) or after (6th) is preferred
   - Recommendation: Insert before settings so settings remains last — conventional placement. Final order: home/news/pet/notes/weather/settings

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `urllib.request` | Weather fetch | Yes | stdlib 3.11 | — |
| `urllib.parse` | URL encode city | Yes | stdlib 3.11 | — |
| `ssl` | HTTPS connection | Yes | stdlib 3.11 | — |
| `threading` | Async fetch | Yes | stdlib 3.11 | — |
| `wttr.in` API | All weather data | Yes (verified live) | — | No fallback — show error message |
| Network access | wttr.in requests | Yes | — | Graceful error display |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** N/A.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None detected — Wave 0 must install pytest |
| Config file | None — Wave 0 creates `pytest.ini` or `pyproject.toml` |
| Quick run command | `python3.11 -m pytest tests/ -x -q` |
| Full suite command | `python3.11 -m pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WTHR-01 | fetch_weather returns temp_C, feels_like_C, desc fields | unit | `python3.11 -m pytest tests/test_weather_service.py::test_parse_current -x` | Wave 0 |
| WTHR-02 | Chinese city name (上海) fetches valid data | unit (mock) | `python3.11 -m pytest tests/test_weather_service.py::test_chinese_city -x` | Wave 0 |
| WTHR-03 | delete_city removes from list and saves to JSON | unit | `python3.11 -m pytest tests/test_weather_service.py::test_city_persistence -x` | Wave 0 |
| WTHR-04 | fetch_weather blocks < 0.01s when cache hit | unit | `python3.11 -m pytest tests/test_weather_service.py::test_cache_hit -x` | Wave 0 |
| WTHR-05 | fetch_weather returns 3-item forecast list | unit | `python3.11 -m pytest tests/test_weather_service.py::test_forecast_three_days -x` | Wave 0 |
| WTHR-06 | Second call within 15 min returns cached data without HTTP request | unit | `python3.11 -m pytest tests/test_weather_service.py::test_cache_ttl -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python3.11 -m pytest tests/test_weather_service.py -x -q`
- **Per wave merge:** `python3.11 -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/__init__.py` — make tests a package
- [ ] `tests/test_weather_service.py` — covers WTHR-01 through WTHR-06 (mock urllib to avoid live network in tests)
- [ ] `tests/conftest.py` — shared fixtures (mock HTTP response fixture)
- [ ] Framework install: `python3.11 -m pip install pytest` — if not detected

*(Note: WTHR-04's "does not block UI" aspect is an integration concern — the unit test covers the cache-hit path which is the synchronous code path. The async thread dispatch is tested via manual smoke test.)*

---

## Sources

### Primary (HIGH confidence)
- Live API test against `https://wttr.in/Beijing?format=j1` — verified response structure, field names, types (2026-04-22)
- Live API test against `https://wttr.in/上海?format=j1` — verified Chinese city name support
- Live API test for unknown city — verified HTTP 500 + `location not found` body
- `ui/panel.py` — verified tab registration pattern (`tab_defs`, `_build_<tab>_tab`, `_switch_tab`)
- `data/storage/__init__.py` — verified StorageRepository interface
- `config.py` — verified THEMES keys and existing constant pattern
- `services/news/__init__.py` — verified async load + cache pattern to replicate

### Secondary (MEDIUM confidence)
- wttr.in documentation at `https://github.com/chubin/wttr.in` — general API description (not re-fetched; live API test is primary source)

### Tertiary (LOW confidence)
- weatherCode enumeration — derived from live API responses and community documentation; not re-verified against official wttr.in spec

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all stdlib, verified against live API
- Architecture: HIGH — directly extends verified existing patterns in codebase
- Pitfalls: HIGH — pitfalls 1-5 verified by live API tests and code inspection; pitfall 6 verified by code reading
- wttr.in API field names: HIGH — verified live

**Research date:** 2026-04-22
**Valid until:** 2026-05-22 (wttr.in is stable; tkinter patterns are stable)
