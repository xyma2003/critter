"""Conversation selection and persistence through the shared local store.

A session keeps full message metadata as well as legacy ``bubbles``. The active
session, its flat compatibility history, and the session list are committed
atomically. Failed writes retain the same in-memory/pending semantics as notes.
"""
from collections import Counter
from copy import deepcopy
import uuid

from core.state_manager import _flush, _lock, _read_current, _runtime

_ACTIVE = "active_chat_session_id"


def _valid_id(value):
    return (isinstance(value, int) and not isinstance(value, bool)) or (
        isinstance(value, str) and bool(value))


def _messages(value):
    if not isinstance(value, list):
        return []
    return [deepcopy(message) for message in value
            if isinstance(message, dict)
            and message.get("role") in ("user", "pet", "assistant")
            and isinstance(message.get("content"), str)]


def session_messages(session):
    """Read full metadata when available; legacy bubbles have no success flag."""
    if not isinstance(session, dict):
        return []
    if isinstance(session.get("messages"), list):
        return _messages(session["messages"])
    bubbles = session.get("bubbles", [])
    if not isinstance(bubbles, list):
        return []
    return [{"role": bubble[0], "content": bubble[1]} for bubble in bubbles
            if isinstance(bubble, (list, tuple)) and len(bubble) == 2
            and bubble[0] in ("user", "pet", "assistant")
            and isinstance(bubble[1], str)]


def _valid_session(session):
    return (isinstance(session, dict) and _valid_id(session.get("id"))
            and bool(session_messages(session)))


def _new_id(used):
    candidate = uuid.uuid4().hex
    while candidate in used:
        candidate = uuid.uuid4().hex
    used.add(candidate)
    return candidate


def _pairs(messages):
    return [("assistant" if message["role"] == "pet" else message["role"],
             message["content"]) for message in messages]


def _matches_tail(session, messages):
    existing = session_messages(session)
    return bool(messages) and len(existing) >= len(messages) and (
        _pairs(existing[-len(messages):]) == _pairs(messages))


def _read():
    """Return a copy, repairing ambiguous IDs without dropping unknown records."""
    runtime = _runtime()
    read_error = None
    try:
        disk_state = _read_current(runtime)
    except OSError as error:
        read_error = f"无法读取本地数据，已停止写入：{error}"
        runtime.error = read_error
        if not runtime.readable:
            return None
        disk_state = runtime.last_good
    state = deepcopy({**disk_state, **runtime.pending})

    def commit(values):
        # Match the shared store's pending/retry semantics, using this one
        # locked read. A second read after a transient failure could otherwise
        # overwrite records that were missing from the fallback snapshot.
        runtime.pending.update(deepcopy(values))
        if read_error is not None:
            return False
        return _flush(runtime, disk_state)

    raw = state.get("chat_sessions", [])
    # Preserve an unexpected old field value too; it is not a valid selectable
    # session, but a subsequent save must not silently erase its contents.
    sessions = deepcopy(raw if isinstance(raw, list) else [raw])
    valid = [session for session in sessions if _valid_session(session)]
    counts = Counter(session["id"] for session in valid)
    used = {session["id"] for session in sessions
            if isinstance(session, dict) and _valid_id(session.get("id"))}
    replacements = []
    for session in valid:
        old_id = session["id"]
        if counts[old_id] > 1:
            session["id"] = _new_id(used)
            replacements.append((old_id, session))
    repairs = {"chat_sessions": sessions} if replacements else {}
    if _ACTIVE in state and any(old == state[_ACTIVE] for old, _ in replacements):
        flat = _messages(state.get("chat_history", []))
        matching = [session for old, session in replacements
                    if old == state[_ACTIVE] and _matches_tail(session, flat)]
        # An ambiguous pointer must not silently select the first conversation.
        state[_ACTIVE] = matching[0]["id"] if len(matching) == 1 else None
        repairs[_ACTIVE] = state[_ACTIVE]
    return state, sessions, repairs, commit


def _canonical(session, messages=None):
    result = deepcopy(session)
    result["messages"] = session_messages(session) if messages is None else _messages(messages)
    result["bubbles"] = [[message["role"], message["content"]]
                         for message in result["messages"]]
    if not isinstance(result.get("title"), str) or not result["title"]:
        result["title"] = next((message["content"][:20] for message in result["messages"]
                                if message["role"] == "user"), "未命名对话")
    return result


def _save_current(commit, sessions, session_id, messages):
    return commit({"chat_sessions": sessions, _ACTIVE: session_id,
                   "chat_history": deepcopy(messages[-50:])})


def load_sessions():
    """Return selectable sessions in storage order, keeping all older records."""
    with _lock:
        transaction = _read()
        if transaction is None:
            return []
        _, sessions, repairs, commit = transaction
        if repairs:
            commit(repairs)
        return [deepcopy(session) for session in sessions if _valid_session(session)]


def restore_current_session():
    """Restore a selection, or migrate the old flat history exactly once.

    Missing selection is legacy state; explicit None is a deliberate draft.
    The latter must never fall back to a previously deleted conversation.
    """
    with _lock:
        transaction = _read()
        if transaction is None:
            return None, []
        state, sessions, repairs, commit = transaction
        flat = _messages(state.get("chat_history", []))
        valid = [session for session in sessions if _valid_session(session)]
        if _ACTIVE in state:
            current = next((session for session in valid
                            if _valid_id(state[_ACTIVE]) and session["id"] == state[_ACTIVE]), None)
            if current is not None:
                if repairs:
                    commit(repairs)
                return deepcopy(current), session_messages(current)
            if state[_ACTIVE] is not None:
                # A dangling reference is a draft, not permission to choose an
                # unrelated saved conversation. Keep its readable flat history.
                repairs[_ACTIVE] = None
            if repairs:
                commit(repairs)
            return None, flat

        matching = [session for session in valid if _matches_tail(session, flat)]
        if len(matching) == 1:
            current = matching[0]
            messages = session_messages(current)
            # The flat history retained ts/include_in_context in older versions.
            # Recover those flags only for a verified matching suffix.
            start = len(messages) - len(flat)
            messages[start:] = [{**old, **recent} for old, recent in zip(messages[start:], flat)]
            current = _canonical(current, messages)
            sessions = [current if item is matching[0] else item for item in sessions]
        elif any(message["role"] == "user" for message in flat):
            used = {session["id"] for session in sessions
                    if isinstance(session, dict) and _valid_id(session.get("id"))}
            current = _canonical({"id": _new_id(used), "title": "", "messages": flat})
            sessions.append(current)
        elif not flat and valid:
            previous = valid[-1]
            current = _canonical(previous)
            sessions = [current if item is previous else item for item in sessions]
        else:
            # No user conversation to migrate. Recording None also makes the
            # decision stable if older sessions are added later.
            _save_current(commit, sessions, None, flat)
            return None, flat
        messages = session_messages(current)
        _save_current(commit, sessions, current["id"], messages)
        return deepcopy(current), messages


def save_session(session):
    """Upsert a conversation and its selection/history in one atomic save."""
    if not _valid_session(session):
        return False
    with _lock:
        transaction = _read()
        if transaction is None:
            return False
        _, sessions, _, commit = transaction
        old = next((item for item in sessions
                    if _valid_session(item) and item["id"] == session["id"]), None)
        current = _canonical({**(old or {}), **deepcopy(session)})
        if old is None:
            sessions.append(current)
        else:
            sessions = [current if item is old else item for item in sessions]
        return _save_current(commit, sessions, current["id"], current["messages"])


def activate_session(session_id):
    """Select an existing conversation; missing IDs leave the selection alone."""
    if not _valid_id(session_id):
        return None
    with _lock:
        transaction = _read()
        if transaction is None:
            return None
        _, sessions, repairs, commit = transaction
        old = next((item for item in sessions
                    if _valid_session(item) and item["id"] == session_id), None)
        if old is None:
            if repairs:
                commit(repairs)
            return None
        current = _canonical(old)
        sessions = [current if item is old else item for item in sessions]
        _save_current(commit, sessions, current["id"], current["messages"])
        return deepcopy(current), session_messages(current)


def start_new_session(messages=None):
    """Persist an explicit draft while retaining every saved conversation."""
    with _lock:
        transaction = _read()
        if transaction is None:
            return False
        _, sessions, _, commit = transaction
        return _save_current(commit, sessions, None, _messages(messages or []))


def delete_session(session_id):
    """Delete one conversation; deleting the active one clears its flat copy."""
    if not _valid_id(session_id):
        return False
    with _lock:
        transaction = _read()
        if transaction is None:
            return False
        state, sessions, repairs, commit = transaction
        target = next((item for item in sessions
                       if _valid_session(item) and item["id"] == session_id), None)
        if target is None:
            if repairs:
                commit(repairs)
            return False
        remaining = [item for item in sessions if item is not target]
        if state.get(_ACTIVE) == session_id:
            return _save_current(commit, remaining, None, [])
        return commit({**repairs, "chat_sessions": remaining})
