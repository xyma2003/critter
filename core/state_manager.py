import datetime
import json
import os

_STATE_FILE = os.path.expanduser("~/.desktop-pet-state.json")


def _load_state() -> dict:
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    try:
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def save_field(key: str, value) -> None:
    state = _load_state()
    state[key] = value
    _save_state(state)


def load_field(key: str, default=None):
    return _load_state().get(key, default)


# --- Chat History ---

def save_chat_history(messages: list) -> None:
    save_field("chat_history", messages)


def load_chat_history(limit: int = 50) -> list:
    msgs = _load_state().get("chat_history", [])
    if not isinstance(msgs, list):
        return []
    return msgs[-limit:]


# --- Timer State ---

def save_timer_state(end_time_iso: str, is_active: bool) -> None:
    save_field("timer", {"end_time": end_time_iso, "is_active": is_active})


def load_timer_state() -> dict | None:
    state = _load_state().get("timer")
    if not isinstance(state, dict):
        return None
    return state


# --- Window Position ---

def save_window_position(x: int, y: int) -> None:
    save_field("window_position", {"x": x, "y": y})


def load_window_position() -> tuple[int, int] | None:
    pos = _load_state().get("window_position")
    if not isinstance(pos, dict):
        return None
    try:
        return (int(pos["x"]), int(pos["y"]))
    except Exception:
        return None


# --- News Cache ---

def save_news_cache(items: list) -> None:
    save_field("news_cache", {
        "items": items,
        "last_fetch": datetime.datetime.now().isoformat()
    })


def load_news_cache() -> tuple[list, bool]:
    from config import Config
    try:
        cache = _load_state().get("news_cache", {})
        items = cache.get("items", [])
        last_fetch_str = cache.get("last_fetch", "")
        if not isinstance(items, list) or not last_fetch_str:
            return [], False
        last_fetch = datetime.datetime.fromisoformat(last_fetch_str)
        is_fresh = (datetime.datetime.now() - last_fetch).total_seconds() < Config.NEWS_CACHE_DURATION
        return items, is_fresh
    except Exception:
        return [], False


# --- Pet Stats ---

def save_pet_stats(hunger: float, energy: float, mood: float) -> None:
    save_field("pet_stats", {"hunger": hunger, "energy": energy, "mood": mood})


def load_pet_stats() -> dict | None:
    stats = _load_state().get("pet_stats")
    if not isinstance(stats, dict):
        return None
    try:
        return {
            "hunger": float(stats["hunger"]),
            "energy": float(stats["energy"]),
            "mood":   float(stats["mood"]),
        }
    except Exception:
        return None


# --- Notes ---

def save_notes(notes: list) -> None:
    save_field("notes", notes)


def load_notes() -> list:
    notes = _load_state().get("notes", [])
    return notes if isinstance(notes, list) else []


# --- Chat Sessions ---

def save_chat_sessions(sessions: list) -> None:
    save_field("chat_sessions", sessions)


def load_chat_sessions() -> list:
    sessions = _load_state().get("chat_sessions", [])
    return sessions if isinstance(sessions, list) else []


# --- Theme ---

def save_theme(mode: str) -> None:
    save_field("theme", mode)


def load_theme() -> str:
    mode = _load_state().get("theme", "light")
    return mode if mode in ("light", "dark") else "light"


# --- App Settings (pet name, personality, etc.) ---

def save_settings(settings: dict) -> None:
    save_field("settings", settings)


def load_settings() -> dict:
    defaults = {
        "pet_name":        "边牧",
        "pet_personality": "活泼",
        "pet_catchphrase": "汪~",
        "pet_emoji":       "🐕",
        "auto_refresh_min": 30,
    }
    saved = _load_state().get("settings", {})
    if not isinstance(saved, dict):
        return defaults
    return {**defaults, **saved}
