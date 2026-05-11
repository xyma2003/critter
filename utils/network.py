import requests
from typing import Optional


class NetworkUtils:
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    @staticmethod
    def get(url: str, headers: Optional[dict] = None, timeout: int = 10) -> Optional[str]:
        try:
            merged_headers = {**NetworkUtils.DEFAULT_HEADERS, **(headers or {})}
            response = requests.get(url, headers=merged_headers, timeout=timeout)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            return response.text
        except Exception as e:
            print(f"网络请求失败: {url}, 错误: {e}")
            return None
