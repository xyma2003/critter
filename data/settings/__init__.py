"""
data/settings — JSON 持久化工具函数 + settings 加载/保存
"""
import json
import os

from config import SETTINGS_FILE


def load_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_settings():
    return load_json(SETTINGS_FILE, {
        'auto_refresh_min': 30,
        'notify_on_refresh': False,
        'pet_emoji': '🐱',
        'pet_size': 96,
    })


def save_settings(s):
    save_json(SETTINGS_FILE, s)
