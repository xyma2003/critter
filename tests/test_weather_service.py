"""
Unit tests for services.weather — all HTTP calls are mocked; zero live network.
"""
import time
import urllib.error
import urllib.request
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

import services.weather as svc
from services.weather import (
    WEATHER_TTL,
    code_to_emoji,
    fetch_weather,
    get_cached_data,
    is_cached,
    last_fetch_time,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the in-memory cache before each test."""
    svc._cache.clear()
    yield
    svc._cache.clear()


def _make_urlopen_mock(mock_bytes):
    """Helper: returns a patch target and a context-manager mock that returns mock_bytes."""
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=mock_bytes)))
    cm.__exit__ = MagicMock(return_value=False)
    mock_urlopen = MagicMock(return_value=cm)
    return mock_urlopen


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_parse_current(mock_wttr_bytes):
    """WTHR-01: fetch_weather returns dict with correct current-condition keys."""
    mock_urlopen = _make_urlopen_mock(mock_wttr_bytes)
    with patch('urllib.request.urlopen', mock_urlopen):
        data, from_cache, err = fetch_weather('Beijing')

    assert err is None
    assert from_cache is False
    assert data['temp_C'] == '18'
    assert data['feels_like_C'] == '17'
    assert data['desc_zh'] == '部分多云'
    assert data['code'] == 116
    assert len(data['forecast']) == 3


def test_chinese_city(mock_wttr_bytes):
    """WTHR-02: Chinese city name is URL-encoded before insertion into the wttr.in URL."""
    mock_urlopen = _make_urlopen_mock(mock_wttr_bytes)
    with patch('urllib.request.urlopen', mock_urlopen) as m:
        data, _, err = fetch_weather('上海')

    assert err is None
    assert data is not None
    # Verify the URL used contained the URL-encoded form of 上海
    call_args = m.call_args
    req_obj = call_args[0][0]  # first positional arg to urlopen
    assert '%E4%B8%8A%E6%B5%B7' in req_obj.full_url


def test_cache_hit(mock_wttr_bytes):
    """WTHR-06: Second call within TTL returns cached data without making an HTTP request."""
    mock_urlopen = _make_urlopen_mock(mock_wttr_bytes)
    with patch('urllib.request.urlopen', mock_urlopen) as m:
        data1, from_cache1, _ = fetch_weather('Beijing')
        data2, from_cache2, _ = fetch_weather('Beijing')

    assert m.call_count == 1
    assert from_cache1 is False
    assert from_cache2 is True
    assert data1 == data2


def test_cache_ttl(monkeypatch, mock_wttr_bytes):
    """WTHR-06: After TTL expires, a fresh HTTP request is made."""
    mock_urlopen = _make_urlopen_mock(mock_wttr_bytes)
    with patch('urllib.request.urlopen', mock_urlopen) as m:
        fetch_weather('Beijing')
        # Expire the cache by backdating its timestamp
        svc._cache['Beijing']['ts'] = time.time() - (WEATHER_TTL + 1)
        data, from_cache, err = fetch_weather('Beijing')

    assert m.call_count == 2
    assert from_cache is False
    assert err is None


def test_forecast_three_days(mock_wttr_bytes):
    """WTHR-05: forecast list has exactly 3 items, each with the required keys."""
    mock_urlopen = _make_urlopen_mock(mock_wttr_bytes)
    with patch('urllib.request.urlopen', mock_urlopen):
        data, _, _ = fetch_weather('Beijing')

    forecast = data['forecast']
    assert len(forecast) == 3
    for item in forecast:
        assert 'date' in item
        assert 'max_C' in item
        assert 'min_C' in item
        assert 'desc' in item
        assert 'code' in item


def test_cache_miss_on_force(mock_wttr_bytes):
    """force=True bypasses cache and always hits the network."""
    mock_urlopen = _make_urlopen_mock(mock_wttr_bytes)
    with patch('urllib.request.urlopen', mock_urlopen) as m:
        fetch_weather('Beijing', force=True)
        fetch_weather('Beijing', force=True)

    assert m.call_count == 2


def test_unknown_city_error():
    """fetch_weather for unknown city returns (None, False, '找不到城市：xyz')."""
    error_body = b'location not found: xyz'
    http_err = urllib.error.HTTPError(
        url='https://wttr.in/xyz?format=j1&lang=zh',
        code=500,
        msg='Internal Server Error',
        hdrs=None,  # type: ignore[arg-type]
        fp=BytesIO(error_body),
    )

    with patch('urllib.request.urlopen', side_effect=http_err):
        result = fetch_weather('xyz')

    assert result == (None, False, '找不到城市：xyz')


def test_code_to_emoji():
    """code_to_emoji returns the correct emoji for known codes and fallback for unknown."""
    assert code_to_emoji(113) == '☀️'
    assert code_to_emoji(200) == '⛈️'
    assert code_to_emoji(0) == '🌡️'
