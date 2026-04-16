# Testing Patterns

**Analysis Date:** 2026-04-16

## Test Framework

**Runner:** None detected.

No test files (`test_*.py`, `*_test.py`, `*.test.*`) exist anywhere in the project. No test framework configuration files (`pytest.ini`, `setup.cfg [tool:pytest]`, `pyproject.toml`, `unittest` discover config) are present.

**Assertion Library:** None.

**Run Commands:**
```bash
# No test commands defined. The project has no test suite.
```

## Test File Organization

**Location:** Not applicable — no tests exist.

**Naming:** Not applicable.

## Test Structure

No test structure exists. The project is entirely untested.

## Mocking

**Framework:** None.

No mocking is used anywhere. The project calls live external processes (`subprocess`) and reads/writes real files directly.

## Fixtures and Factories

**Test Data:** None.

**Location:** Not applicable.

## Coverage

**Requirements:** None enforced.

**Coverage tools:** Not installed or configured.

## Test Types

**Unit Tests:** Not present.

**Integration Tests:** Not present.

**E2E Tests:** Not present.

## Manual Testing Approach

All testing is manual. The app is launched directly:

```bash
python3 ~/.openclaw/workspace/desktop-pet/desktop_pet.py
# or via
~/.openclaw/workspace/desktop-pet/start.sh
```

Key behaviors that require manual verification:
- Floating pet window stays topmost (`-topmost True`, transparent background)
- Left-click on pet opens `MainPanel` (`Critter` window)
- Tab switching between home, news, pet, notes, settings
- AI chat streaming via `claude --print --output-format stream-json`
- News fetch via `python3 NEWS_SCRIPT` subprocess
- News caching logic (`CACHE_TTL = 30 * 60` seconds)
- Theme switching between light and dark (`_apply_theme`)
- Notes CRUD persisted to `notes.json`
- Settings persisted to `settings.json`

## Critical Untested Areas

**All logic is untested.** The highest-risk areas are:

- `parse_news(text)` in `desktop_pet.py` — regex parsing of news script output. Format changes will silently break the news tab.
- `get_news(force)` cache TTL logic — time-based branching with no test.
- `_stream_pet_ai(user_text)` — subprocess streaming with JSON parsing. Any format change in Claude CLI output breaks the chat feature.
- `_recolor_widget(widget, th)` — recursive theme remapping. Color value collisions between themes can cause silent miscoloring.
- `_save_current_session` / `_load_session` — chat bubble serialization reads widget state directly; fragile if widget tree changes.
- `_translate_titles_with_claude(titles)` — Claude CLI output parsing. Falls back to original titles on any failure, making failures invisible.
- File I/O in `load_json` / `save_json` — both silently return defaults or `pass` on failure, hiding disk errors.

## Adding Tests

If a test suite is added in the future, the recommended approach:

**Framework:** `pytest` (install with `pip install pytest`)

**Test directory:** Create `tests/` at project root.

**Pure-logic targets first** (no tkinter, no subprocess needed):
- `parse_news(text)` — test with fixture strings
- `get_news()` cache TTL branching — mock `time.time()` and file reads
- Note ID generation and save/load round-trip

**Example test skeleton for `parse_news`:**
```python
# tests/test_parse_news.py
from desktop_pet import parse_news

def test_parse_news_single_section():
    text = "=== 百度热点 ===\n1. 某条新闻标题\n🔗 https://example.com\n"
    sections = parse_news(text)
    assert len(sections) == 1
    assert sections[0]['source'] == '百度热点'
    assert sections[0]['items'][0]['title'] == '某条新闻标题'
    assert sections[0]['items'][0]['link'] == 'https://example.com'
```

**Run command once tests exist:**
```bash
cd ~/.openclaw/workspace/desktop-pet && python -m pytest tests/ -v
```

---

*Testing analysis: 2026-04-16*
