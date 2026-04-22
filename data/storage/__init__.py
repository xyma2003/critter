"""
data/storage — StorageRepository：书签 / 稍后再看 持久化层
"""
import sys
from datetime import datetime, timezone

from data.settings import load_json, save_json

_SAVED_AT_FORMATS = ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S')


def _parse_saved_at(item):
    """将 saved_at 字符串解析为 datetime，解析失败时返回 epoch（并打印警告）。"""
    raw = item.get('saved_at', '')
    for fmt in _SAVED_AT_FORMATS:
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    print(f'[storage] WARNING: unparseable saved_at {raw!r} for item id={item.get("id")}',
          file=sys.stderr)
    return datetime.fromtimestamp(0, tz=timezone.utc)


class StorageRepository:
    """
    Encapsulates JSON I/O for named collections.
    Current backend: single JSON file at self._path.
    Interface is intentionally backend-agnostic so it can be
    swapped for SQLite or any other store later.

    Storage format:
        {
          "bookmarks": [...],
          "read_later": [...]
        }
    Each item dict must contain at minimum: id, title, link, source, saved_at.
    """

    def __init__(self, path):
        self._path = path

    def _load(self):
        return load_json(self._path, {})

    def _save(self, data):
        save_json(self._path, data)

    def add(self, collection, item):
        """
        Add item to collection.
        item must be a dict with keys: id, title, link, source, saved_at.
        If an item with the same id already exists it is silently replaced.
        Returns True on success, False on error.
        """
        required = {'id', 'title', 'link', 'source', 'saved_at'}
        missing = required - set(item.keys())
        if missing:
            print(f'[storage] WARNING: add() called with missing keys {missing}', file=sys.stderr)
        try:
            data = self._load()
            items = data.get(collection, [])
            items = [x for x in items if x.get('id') != item.get('id')]
            items.append(item)
            data[collection] = items
            self._save(data)
            return True
        except Exception:
            return False

    def remove(self, collection, item_id):
        """
        Remove item by id from collection.
        No-op if item_id not found.
        Returns True on success, False on error.
        """
        try:
            data = self._load()
            items = data.get(collection, [])
            data[collection] = [x for x in items if x.get('id') != item_id]
            self._save(data)
            return True
        except Exception:
            return False

    def list_items(self, collection):
        """
        Return list of item dicts for collection (newest-first by saved_at).
        Returns empty list if collection does not exist or file missing.
        """
        try:
            data = self._load()
            items = data.get(collection, [])
            return sorted(items, key=_parse_saved_at, reverse=True)
        except Exception:
            return []
