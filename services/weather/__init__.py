"""
services/weather — wttr.in 天气抓取与内存缓存层

Public API:
    fetch_weather(city, force=False) -> (data_dict | None, from_cache: bool, error: str | None)
    is_cached(city) -> bool
    last_fetch_time(city) -> float | None
    get_cached_data(city) -> dict | None
    code_to_emoji(code) -> str
    WEATHER_TTL: int (900 seconds)
"""
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

# ── Constants ─────────────────────────────────────────────────────────────────

WEATHER_TTL: int = 900  # 15 minutes

WEATHER_EMOJI: dict[int, str] = {
    113: '☀️', 116: '⛅', 119: '☁️', 122: '☁️',
    143: '🌫️', 176: '🌦️', 179: '🌨️', 200: '⛈️',
    248: '🌫️', 260: '🌫️', 263: '🌦️', 266: '🌧️',
    293: '🌦️', 296: '🌧️', 302: '🌧️', 308: '🌧️',
    317: '🌨️', 320: '🌨️', 323: '🌨️', 326: '🌨️',
    338: '❄️', 353: '🌦️', 356: '🌧️', 368: '🌨️',
    371: '❄️', 386: '⛈️', 389: '⛈️', 395: '⛈️',
}

# ── In-memory cache ───────────────────────────────────────────────────────────

_cache: dict = {}  # {city_name: {'data': dict, 'ts': float}}


# ── Helpers ───────────────────────────────────────────────────────────────────

def code_to_emoji(code: int) -> str:
    """Return the weather emoji for a wttr.in weatherCode, or '🌡️' as fallback."""
    return WEATHER_EMOJI.get(int(code), '🌡️')


def _build_ssl_ctx() -> ssl.SSLContext:
    """SSL context for wttr.in calls. Use default verification."""
    return ssl.create_default_context()


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_weather(city: str, force: bool = False) -> tuple:
    """Fetch weather for *city* from wttr.in.

    Returns:
        (data_dict, from_cache, error_msg)
        data_dict is None on error; from_cache is True only on a valid cache hit.

    data_dict keys:
        temp_C (str), feels_like_C (str), desc_zh (str), code (int),
        forecast (list of 3 dicts with date, max_C, min_C, desc, code)
    """
    cached = _cache.get(city)
    if cached and not force and (time.time() - cached['ts'] < WEATHER_TTL):
        return cached['data'], True, None

    encoded = urllib.parse.quote(city, safe='')
    url = f'https://wttr.in/{encoded}?format=j1&lang=zh'
    req = urllib.request.Request(url, headers={'User-Agent': 'Critter/1.0'})
    try:
        with urllib.request.urlopen(req, context=_build_ssl_ctx(), timeout=10) as resp:
            raw = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        if 'location not found' in body.lower():
            return None, False, f'找不到城市：{city}'
        return None, False, f'请求失败 ({e.code})'
    except urllib.error.URLError as e:
        return None, False, f'网络错误：{e.reason}'
    except json.JSONDecodeError:
        return None, False, '解析失败'

    cc = raw['current_condition'][0]

    # Chinese description — prefer lang_zh, fall back to English weatherDesc
    lang_zh_list = cc.get('lang_zh') or []
    desc_zh = (lang_zh_list[0].get('value', '') if lang_zh_list
               else (cc.get('weatherDesc') or [{}])[0].get('value', ''))

    # 3-day forecast
    forecast = []
    for day in raw.get('weather', [])[:3]:
        hourly = day.get('hourly', [])
        idx = 4 if len(hourly) > 4 else (len(hourly) - 1 if hourly else 0)
        if hourly and idx >= 0:
            lang_list = hourly[idx].get('lang_zh') or hourly[idx].get('weatherDesc') or []
            day_code = int(hourly[idx].get('weatherCode', 0))
        else:
            lang_list = []
            day_code = 0
        day_desc = lang_list[0].get('value', '') if lang_list else ''
        forecast.append({
            'date':  day['date'],
            'max_C': day['maxtempC'],
            'min_C': day['mintempC'],
            'desc':  day_desc,
            'code':  day_code,
        })

    data = {
        'temp_C':       cc['temp_C'],
        'feels_like_C': cc['FeelsLikeC'],
        'desc_zh':      desc_zh,
        'code':         int(cc.get('weatherCode', 0)),
        'forecast':     forecast,
    }
    _cache[city] = {'data': data, 'ts': time.time()}
    return data, False, None


def is_cached(city: str) -> bool:
    """Return True if *city* has a valid (non-expired) cache entry."""
    c = _cache.get(city)
    return bool(c and (time.time() - c['ts'] < WEATHER_TTL))


def last_fetch_time(city: str) -> float | None:
    """Return the timestamp of the last successful fetch, or None."""
    c = _cache.get(city)
    return c['ts'] if c else None


def get_cached_data(city: str) -> dict | None:
    """Public accessor: return the cached data dict for *city*, or None.

    Callers should use this instead of importing _cache directly.
    """
    c = _cache.get(city)
    return c['data'] if c else None
