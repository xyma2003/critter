import datetime
from copy import deepcopy
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import tempfile
import threading
import uuid
from config import STATE_FILE

_STATE_FILE = STATE_FILE
_lock = threading.RLock()


@dataclass(frozen=True)
class StorageStatus:
    path: str
    pending_fields: tuple[str, ...] = ()
    error: str | None = None
    recovery_backup: str | None = None
    recovered_from_memory: bool = False


@dataclass
class _Runtime:
    pending: dict = field(default_factory=dict)
    last_good: dict = field(default_factory=dict)
    readable: bool = False
    error: str | None = None
    recovery_backup: str | None = None
    corrupt_bytes: bytes | None = None
    backup_path: str | None = None
    recovered_from_memory: bool = False


_runtimes: dict[str, _Runtime] = {}


def _runtime() -> _Runtime:
    return _runtimes.setdefault(os.fspath(_STATE_FILE), _Runtime())


def get_state_file() -> str:
    """Return the actual storage location for display and backups."""
    return _STATE_FILE


def get_storage_status() -> StorageStatus:
    """A read-only snapshot, safe to poll from the UI without doing file I/O."""
    with _lock:
        runtime = _runtime()
        return StorageStatus(get_state_file(), tuple(runtime.pending), runtime.error,
                             runtime.recovery_backup, runtime.recovered_from_memory)


def acknowledge_recovery() -> None:
    """Dismiss the recovery notice; never delete the backup."""
    with _lock:
        _runtime().recovery_backup = None


def _read_disk(runtime: _Runtime) -> dict:
    # An unreadable existing file is not an empty store. Let callers block
    # writes until it can be read, rather than replacing unknown old records.
    try:
        with open(_STATE_FILE, "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        return {}
    try:
        state = json.loads(raw.decode("utf-8"))
        if not isinstance(state, dict):
            raise ValueError("状态文件最外层必须是对象")
        return state
    except (UnicodeDecodeError, ValueError):
        if (raw == runtime.corrupt_bytes and runtime.backup_path
                and Path(runtime.backup_path).is_file()):
            return deepcopy(runtime.last_good)
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = f"{_STATE_FILE}.corrupt-{stamp}-{uuid.uuid4().hex}.bak"
        created = False
        try:
            with open(backup, "xb", opener=lambda path, flags: os.open(path, flags, 0o600)) as f:
                created = True
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
        except OSError as error:
            if created:
                try:
                    os.unlink(backup)
                except OSError:
                    pass
            raise OSError(f"数据损坏且无法保留备份，已停止写入：{error}") from error
        runtime.corrupt_bytes = raw
        runtime.backup_path = backup
        runtime.recovery_backup = backup
        runtime.recovered_from_memory = runtime.readable
        # If corruption happens while running, the last readable snapshot is
        # still useful. Never discard those known records to save a new field.
        return deepcopy(runtime.last_good)


def _read_current(runtime: _Runtime) -> dict:
    state = _read_disk(runtime)
    runtime.last_good = deepcopy(state)
    runtime.readable = True
    return state


def initialize_storage() -> bool:
    """Check storage before constructing UI that may write initial values."""
    with _lock:
        runtime = _runtime()
        try:
            _read_current(runtime)
        except OSError as error:
            runtime.error = f"无法读取本地数据：{error}"
            return False
        if not runtime.pending:
            runtime.error = None
        return True


def _load_state() -> dict:
    with _lock:
        runtime = _runtime()
        try:
            state = _read_current(runtime)
        except OSError as error:
            runtime.error = f"无法读取本地数据：{error}"
            state = runtime.last_good
        # Callers such as notes mutate returned lists in place. Do not expose
        # the pending queue or the last successful read to those mutations.
        return deepcopy({**state, **runtime.pending})


def _atomic_write(state: dict) -> None:
    # Serialize before touching the destination; partial JSON must never
    # truncate the last successful save. Keep the temp file on the same disk.
    payload = json.dumps(state, ensure_ascii=False, indent=2, allow_nan=False)
    path = Path(_STATE_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        except OSError:
            # Cleanup failure cannot undo a successful replacement. A leftover
            # temp file is never read as state on the next launch.
            pass


def _flush(runtime: _Runtime, state: dict) -> bool:
    merged = {**state, **runtime.pending}
    try:
        _atomic_write(merged)
    except (OSError, TypeError, ValueError) as error:
        runtime.error = f"保存失败，修改暂留在当前会话：{error}"
        return False
    runtime.last_good = deepcopy(merged)
    runtime.pending.clear()
    runtime.error = None
    return True


def save_fields(values: dict) -> bool:
    """Merge field updates under one in-process lock and commit them together.

    Failed writes stay in memory for explicit retry (or the next save). If an
    existing file has never been readable, refuse updates instead of queuing
    values derived from an empty fallback. This is not a multi-process lock.
    """
    with _lock:
        runtime = _runtime()
        try:
            state = _read_current(runtime)
        except OSError as error:
            runtime.error = f"无法读取本地数据，已停止写入：{error}"
            if runtime.readable:
                runtime.pending.update(deepcopy(values))
            return False
        runtime.pending.update(deepcopy(values))
        return _flush(runtime, state)


def retry_pending_saves() -> bool:
    with _lock:
        runtime = _runtime()
        try:
            state = _read_current(runtime)
        except OSError as error:
            runtime.error = f"无法读取本地数据，已停止写入：{error}"
            return False
        if runtime.pending:
            return _flush(runtime, state)
        runtime.error = None
        return True


def _save_state(state: dict) -> bool:
    """Compatibility helper; prefer save_field(s) to avoid stale snapshots."""
    return save_fields(state)


def save_field(key: str, value) -> bool:
    return save_fields({key: value})


def load_field(key: str, default=None):
    return _load_state().get(key, default)


# --- Chat History ---

def save_chat_history(messages: list) -> bool:
    return save_field("chat_history", messages)


def load_chat_history(limit: int = 50) -> list:
    msgs = _load_state().get("chat_history", [])
    if not isinstance(msgs, list):
        return []
    return msgs[-limit:]


# --- Timer State ---

def save_timer_state(end_time_iso: str, is_active: bool) -> bool:
    return save_field("timer", {"end_time": end_time_iso, "is_active": is_active})


def load_timer_state() -> dict | None:
    state = _load_state().get("timer")
    if not isinstance(state, dict):
        return None
    return state


# --- Window Position ---

def save_window_position(x: int, y: int) -> bool:
    return save_field("window_position", {"x": x, "y": y})


def load_window_position() -> tuple[int, int] | None:
    pos = _load_state().get("window_position")
    if not isinstance(pos, dict):
        return None
    try:
        return (int(pos["x"]), int(pos["y"]))
    except Exception:
        return None


# --- News Cache ---

def save_news_cache(items: list) -> bool:
    return save_field("news_cache", {
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

def save_pet_stats(hunger: float, energy: float, mood: float) -> bool:
    return save_field("pet_stats", {"hunger": hunger, "energy": energy, "mood": mood})


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

def save_notes(notes: list) -> bool:
    return save_field("notes", notes)


def load_notes() -> list:
    notes = _load_state().get("notes", [])
    return notes if isinstance(notes, list) else []


# --- Chat Sessions ---

def save_chat_sessions(sessions: list) -> bool:
    return save_field("chat_sessions", sessions)


def load_chat_sessions() -> list:
    sessions = _load_state().get("chat_sessions", [])
    return sessions if isinstance(sessions, list) else []


# --- Theme ---

def save_theme(mode: str) -> bool:
    return save_field("theme", mode)


def load_theme() -> str:
    mode = _load_state().get("theme", "light")
    return mode if mode in ("light", "dark") else "light"


# --- App Settings (pet name, personality, etc.) ---

def save_settings(settings: dict) -> bool:
    return save_field("settings", settings)


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
