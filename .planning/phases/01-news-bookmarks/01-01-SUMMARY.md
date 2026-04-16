---
phase: "01-news-bookmarks"
plan: "01"
subsystem: "storage"
tags: ["storage", "repository", "bookmarks", "persistence", "json"]
dependency_graph:
  requires: []
  provides: ["StorageRepository", "BOOKMARKS_FILE", "MainPanel._storage"]
  affects: ["desktop_pet.py"]
tech_stack:
  added: []
  patterns: ["Repository pattern (JSON backend, swappable to SQLite)"]
key_files:
  created: []
  modified: ["desktop_pet.py"]
decisions:
  - "Single JSON file at BOOKMARKS_FILE with top-level collection keys ('bookmarks', 'read_later')"
  - "list_items returns newest-first sorted by saved_at string (ISO8601 sort-safe)"
  - "add() silently replaces duplicate ids to keep the operation idempotent"
  - "StorageRepository delegates all I/O to existing load_json/save_json utilities for consistent error handling"
metrics:
  duration: "~5 minutes"
  completed: "2026-04-16"
  tasks_completed: 2
  files_modified: 1
---

# Phase 01 Plan 01: StorageRepository Persistence Layer Summary

## One-liner

JSON-backed StorageRepository class with add/remove/list_items API wired into MainPanel, enabling bookmark and read-later persistence via a swappable abstraction layer.

## What Was Built

### BOOKMARKS_FILE constant (desktop_pet.py line 24)

Added module-level constant following the existing path-constant pattern:

```python
BOOKMARKS_FILE = os.path.expanduser("~/.openclaw/workspace/desktop-pet/bookmarks.json")
```

### StorageRepository class (desktop_pet.py lines 103-174)

New class placed after `save_json` with the standard major-section box comment. Provides three public methods:

- `add(collection, item)` — upserts item (by id) into named collection; returns bool
- `remove(collection, item_id)` — removes item by id; no-op if not found; returns bool
- `list_items(collection)` — returns all items newest-first by `saved_at`; empty list on missing file

Both `bookmarks` and `read_later` collections are supported by convention as top-level JSON keys.

### MainPanel wiring (desktop_pet.py line 295)

Added to `MainPanel.__init__` after `self._current_session_id = None`:

```python
self._storage = StorageRepository(BOOKMARKS_FILE)
```

## Key Design Choices

| Choice | Rationale |
|--------|-----------|
| Single JSON file with collection keys | Minimal I/O, atomic writes, easy to inspect/backup |
| Delegates to load_json/save_json | Reuses existing error-handling pattern (silent failures) |
| Newest-first sort on list_items | ISO8601 saved_at strings are lexicographically sort-safe |
| Idempotent add (replace by id) | Prevents duplicate entries if user bookmarks same article twice |
| Backend-agnostic interface | `add/remove/list_items` contract stays stable when swapping to SQLite |

## Exact Line Numbers

| Artifact | Line |
|----------|------|
| `BOOKMARKS_FILE` constant | 24 |
| `class StorageRepository` | 107 |
| `self._storage = StorageRepository(BOOKMARKS_FILE)` in MainPanel | 295 |

## Tasks Completed

| Task | Description | Commit | Result |
|------|-------------|--------|--------|
| 1 | Add BOOKMARKS_FILE constant and StorageRepository class | 3969686 | desktop_pet.py |
| 2 | Smoke-test StorageRepository round-trip | (no code change) | All assertions passed |

## Verification Results

- Static parse check: PASS (class, methods, constant, wiring all present)
- Syntax check: PASS (`py_compile.compile` no errors)
- Full round-trip test: PASS (add, idempotent re-add, separate collection, remove, disk persistence all verified)
- Final structural grep: 3 lines found (constant line 24, class line 107, wiring line 295)

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. StorageRepository is fully implemented. bookmarks.json will be created on first write (no stub data).

## Self-Check: PASSED

- desktop_pet.py modified: FOUND
- Commit 3969686: confirmed via git log
- BOOKMARKS_FILE at line 24: confirmed
- class StorageRepository at line 107: confirmed
- self._storage = StorageRepository at line 295: confirmed
