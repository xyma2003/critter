"""
services/notes — 便签 CRUD，持久化到 notes.json
"""
import time

from config import NOTE_FILE
from data.settings import load_json, save_json


def load_all():
    return load_json(NOTE_FILE, {'notes': []}).get('notes', [])


def save_all(notes):
    save_json(NOTE_FILE, {'notes': notes})


def create(content):
    """新建便签，返回新建的 note dict。"""
    notes = load_all()
    now = int(time.time())
    note = {'id': now, 'content': content, 'updated': now}
    notes.append(note)
    save_all(notes)
    return note


def update(note_id, content):
    """更新便签内容，返回是否成功。"""
    notes = load_all()
    now = int(time.time())
    for n in notes:
        if n['id'] == note_id:
            n['content'] = content
            n['updated'] = now
            save_all(notes)
            return True
    return False


def delete(note_id):
    """删除便签，返回剩余 notes 列表。"""
    notes = load_all()
    notes = [n for n in notes if n['id'] != note_id]
    save_all(notes)
    return notes


def create_diary(content, date_str):
    """创建日记便签，带 kind='diary' 和 date 字段。id 用时间戳，避免重复。"""
    notes = load_all()
    now = int(time.time())
    note = {
        'id': now,
        'content': content,
        'updated': now,
        'kind': 'diary',
        'date': date_str,   # 'YYYY-MM-DD'
    }
    notes.append(note)
    save_all(notes)
    return note
