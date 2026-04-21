"""
services/chat_history — 聊天 session 持久化
存储格式（chat_history.json）：
  [
    {
      "id": 1714000000000,
      "title": "第一条用户消息前20字",
      "bubbles": [["user", "..."], ["pet", "..."]]
    },
    ...
  ]
最多保留最近 MAX_SESSIONS 条，超出时删除最旧的。
"""
import os

from config import CHAT_HISTORY_FILE
from data.settings import load_json, save_json

MAX_SESSIONS = 50


def load_sessions():
    """从磁盘加载所有 sessions，返回列表（按 id 升序）。"""
    return load_json(CHAT_HISTORY_FILE, [])


def save_session(session):
    """
    写入或更新一条 session。
    session 必须包含 id、title、bubbles 字段。
    bubbles 为空时不写入（避免保存空对话）。
    """
    if not session.get('bubbles'):
        return
    sessions = load_sessions()
    sessions = [s for s in sessions if s['id'] != session['id']]
    sessions.append(session)
    sessions.sort(key=lambda s: s['id'])
    if len(sessions) > MAX_SESSIONS:
        sessions = sessions[-MAX_SESSIONS:]
    save_json(CHAT_HISTORY_FILE, sessions)


def delete_session(session_id):
    """删除指定 session。"""
    sessions = load_sessions()
    sessions = [s for s in sessions if s['id'] != session_id]
    save_json(CHAT_HISTORY_FILE, sessions)
