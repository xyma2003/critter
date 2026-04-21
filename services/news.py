"""
services/news.py — 新闻抓取、缓存、解析、通知
"""
import json
import re
import subprocess
import time

from config import CACHE_FILE, CACHE_TTL, NEWS_SCRIPT
from data.settings import save_json


def load_cache():
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('content'), data.get('timestamp', 0)
    except Exception:
        return None, 0


def save_cache(content):
    save_json(CACHE_FILE, {'content': content, 'timestamp': time.time()})


def fetch_news_raw():
    result = subprocess.run(['python3', NEWS_SCRIPT],
                            capture_output=True, text=True, timeout=30)
    return result.stdout


def get_news(force=False):
    cached_content, cached_time = load_cache()
    if cached_content and (time.time() - cached_time < CACHE_TTL) and not force:
        return cached_content, True, int(cached_time)
    content = fetch_news_raw()
    save_cache(content)
    return content, False, int(time.time())


def parse_news(text):
    sections = []
    current = None
    for line in text.split('\n'):
        if line.startswith('==='):
            if current:
                sections.append(current)
            current = {'source': line.replace('===', '').strip(), 'items': []}
        elif re.match(r'^\d+\.', line) and current is not None:
            title = re.sub(r'^\d+\.\s*', '', line).strip()
            current['items'].append({'title': title, 'link': None})
        elif '🔗' in line and current and current['items']:
            current['items'][-1]['link'] = line.replace('🔗', '').strip()
    if current:
        sections.append(current)
    return sections


def send_notification(title, body):
    safe_t = title.replace('"', '\\"').replace("'", "\\'")
    safe_b = body.replace('"', '\\"').replace("'", "\\'")
    script = f'display notification "{safe_b}" with title "{safe_t}" sound name "Blow"'
    subprocess.run(['osascript', '-e', script], timeout=5)
