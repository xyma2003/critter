import json
import pytest

MOCK_WTTR_RESPONSE = {
    "current_condition": [{
        "temp_C": "18",
        "FeelsLikeC": "17",
        "weatherCode": "116",
        "lang_zh": [{"value": "部分多云"}],
        "weatherDesc": [{"value": "Partly cloudy"}],
        "humidity": "60",
    }],
    "weather": [
        {
            "date": "2026-04-22",
            "maxtempC": "22",
            "mintempC": "14",
            "hourly": [
                {}, {}, {}, {},
                {"lang_zh": [{"value": "多云"}], "weatherDesc": [{"value": "Cloudy"}], "weatherCode": "119"},
            ],
        },
        {
            "date": "2026-04-23",
            "maxtempC": "25",
            "mintempC": "15",
            "hourly": [
                {}, {}, {}, {},
                {"lang_zh": [{"value": "晴"}], "weatherDesc": [{"value": "Sunny"}], "weatherCode": "113"},
            ],
        },
        {
            "date": "2026-04-24",
            "maxtempC": "23",
            "mintempC": "13",
            "hourly": [
                {}, {}, {}, {},
                {"lang_zh": [{"value": "阵雨"}], "weatherDesc": [{"value": "Showers"}], "weatherCode": "296"},
            ],
        },
    ],
}

@pytest.fixture
def mock_wttr_bytes():
    return json.dumps(MOCK_WTTR_RESPONSE).encode('utf-8')
