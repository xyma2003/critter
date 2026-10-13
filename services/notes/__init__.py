"""
services/notes — 便签 CRUD，通过 state_manager 持久化
"""
import time
import uuid
from collections import Counter

from core.state_manager import load_notes, save_notes


def _new_id(used_ids):
    note_id = uuid.uuid4().hex
    while note_id in used_ids:
        note_id = uuid.uuid4().hex
    used_ids.add(note_id)
    return note_id


def load_all():
    """Keep unique legacy IDs; repair ambiguous groups without losing notes."""
    notes = load_notes()
    counts = Counter(note['id'] for note in notes)
    used_ids = set(counts)
    changed = False
    for note in notes:
        if counts[note['id']] > 1:
            # Replace every ID in a duplicate group. A stale, ambiguous ID
            # must not keep targeting the first note after the repair.
            note['id'] = _new_id(used_ids)
            changed = True
    if changed:
        # Failed saves remain in state_manager's pending queue, so the repaired
        # IDs stay stable during this session and can be retried from the UI.
        save_notes(notes)
    return notes


def save_all(notes):
    return save_notes(notes)


def create(content, title=''):
    """新建便签，返回新建的 note dict。"""
    notes = load_all()
    now = int(time.time())
    note = {'id': _new_id({n['id'] for n in notes}),
            'title': title, 'content': content, 'updated': now}
    notes.append(note)
    save_all(notes)
    return note


def update(note_id, content, title=''):
    """更新便签内容，返回是否成功。"""
    notes = load_all()
    now = int(time.time())
    for n in notes:
        if n['id'] == note_id:
            n['content'] = content
            n['title'] = title
            n['updated'] = now
            save_all(notes)
            return True
    return False


def delete(note_id):
    """删除便签，返回剩余 notes 列表。"""
    notes = load_all()
    remaining = [n for n in notes if n['id'] != note_id]
    if len(remaining) != len(notes):
        save_all(remaining)
    return remaining


def create_diary(content, date_str):
    """创建日记便签，使用独立 ID，保留 kind='diary' 和日期字段。"""
    notes = load_all()
    now = int(time.time())
    note = {
        'id': _new_id({n['id'] for n in notes}),
        'content': content,
        'updated': now,
        'kind': 'diary',
        'date': date_str,   # 'YYYY-MM-DD'
    }
    notes.append(note)
    save_all(notes)
    return note
