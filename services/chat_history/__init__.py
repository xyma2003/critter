"""
services/chat_history — 聊天 session 持久化（通过 state_manager 统一存储）
"""
from config import Config
from core.state_manager import load_chat_sessions, save_chat_sessions

MAX_SESSIONS = Config.MAX_CHAT_SESSIONS


def load_sessions():
    """加载所有 sessions，返回列表（按 id 升序）。"""
    return sorted(load_chat_sessions(), key=lambda s: s.get('id', 0))


def save_session(session):
    """写入或更新一条 session。bubbles 为空时不写入。"""
    if not session.get('bubbles'):
        return
    sessions = load_sessions()
    sessions = [s for s in sessions if s['id'] != session['id']]
    sessions.append(session)
    sessions.sort(key=lambda s: s['id'])
    if len(sessions) > MAX_SESSIONS:
        sessions = sessions[-MAX_SESSIONS:]
    save_chat_sessions(sessions)


def delete_session(session_id):
    """删除指定 session。"""
    sessions = load_sessions()
    sessions = [s for s in sessions if s['id'] != session_id]
    save_chat_sessions(sessions)
