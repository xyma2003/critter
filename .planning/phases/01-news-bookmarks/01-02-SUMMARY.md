---
phase: "01-news-bookmarks"
plan: "02"
subsystem: "news-ui"
tags: ["bookmarks", "read-later", "view-switch", "collection-view", "news-tab"]
dependency_graph:
  requires: ["01-01"]
  provides: ["_switch_news_view", "_build_collection_view", "per-card-action-buttons"]
  affects: ["desktop_pet.py"]
tech_stack:
  added: []
  patterns: ["In-tab view switching (hide/show canvas)", "Per-item toggle icon buttons", "Stable item ID via hashlib MD5"]
key_files:
  created: []
  modified: ["desktop_pet.py"]
decisions:
  - "_make_item_id defined once before the section loop to avoid re-definition on every iteration"
  - "bm_btn and rl_btn packed RIGHT before title_lbl fill=X to ensure correct layout order"
  - "Divider line moved after action button packing to maintain card visual structure"
  - "import hashlib and import time placed as module-alias imports inside _render_news to avoid module-scope pollution"
metrics:
  duration: "~15 minutes"
  completed: "2026-04-16"
  tasks_completed: 2
  files_modified: 1
---

# Phase 01 Plan 02: News Bookmarks UI Summary

## One-liner

View-switch sub-toolbar (热点/收藏/稍后再看), per-card bookmark/read-later toggle buttons, and scrollable collection list with delete — all wired to StorageRepository.

## What Was Built

### Self._news_current_view state (desktop_pet.py line 296)

Added to `MainPanel.__init__` immediately after `self._storage`:
```python
self._news_current_view = 'feed'   # 'feed' | 'bookmarks' | 'read_later'
```

### View-switch sub-toolbar (desktop_pet.py lines 1371-1385)

Added to `_build_news_tab` after the main toolbar divider. Three `tk.Label` buttons — 热点, 收藏, 稍后再看 — each bound to `_switch_news_view`. Active button uses `FG_ACCENT` + bold; others use `FG_MUTED`.

Also added:
- `self._news_tab_body = frame` (line 1269) — anchor for collection frames
- `self._news_canvas_sb` captures the scrollbar (line 1388) — needed by `_switch_news_view` to hide/show

### _switch_news_view method (desktop_pet.py lines 1429-1453)

Updates `_news_view_btns` highlight styles, then:
- `feed`: hides `_news_collection_frame`, re-packs canvas + scrollbar
- `bookmarks`/`read_later`: hides canvas + scrollbar, calls `_build_collection_view`

### _build_collection_view method (desktop_pet.py lines 1455-1530)

Renders a scrollable list of saved items inside `_news_tab_body`. Each row shows title, source, saved date, and a `✕` delete button. Delete calls `self._storage.remove(col, iid)` then rebuilds the view. Empty-state label shown when no items exist.

### Per-item action buttons in _render_news (desktop_pet.py lines ~1649-1775)

- `_make_item_id(item)` helper defined once before the section loop (line 1649) — MD5 hash of title+source, truncated to 12 chars
- Each item row gets `bm_btn` (🔖/📌) and `rl_btn` (⏰/✅) packed `side=tk.RIGHT`
- Initial icon state checked via `self._storage.list_items()` at render time
- `_toggle_bookmark` and `_toggle_read_later` closures call `self._storage.add/remove`
- `_enter`/`_leave` hover closures updated to include `bm_btn` and `rl_btn` background changes

## Exact Line Numbers

| Artifact | Line |
|----------|------|
| `self._news_current_view` state | 296 |
| `self._news_tab_body = frame` in `_build_news_tab` | 1269 |
| View-switch sub-toolbar | 1371-1385 |
| `self._news_canvas_sb` assignment | 1388 |
| `def _switch_news_view` | 1429 |
| `def _build_collection_view` | 1455 |
| `_make_item_id` helper | 1649 |
| Per-item bookmark/read-later buttons | ~1707-1751 |

## Tasks Completed

| Task | Description | Commit | Result |
|------|-------------|--------|--------|
| 1 | Add view-switch state and _switch_news_view + _build_collection_view | f5477f1 | desktop_pet.py |
| 2 | Add bookmark and read-later buttons to _render_news item rows | 0df44ce | desktop_pet.py |

## Verification Results

- Task 1 automated verify: PASS (all 7 assertions)
- Task 2 automated verify: PASS (all 6 assertions)
- Full structural grep: all 5 key symbols found at correct locations
- All 4 StorageRepository call variants confirmed: add bookmarks, add read_later, remove (collection), list_items
- Syntax check: PASS

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. All collection views are wired to live StorageRepository data. Empty-state labels are shown for empty collections (not stubs — they reflect real state).

## Self-Check: PASSED

- desktop_pet.py modified: FOUND
- Commit f5477f1 (Task 1): confirmed
- Commit 0df44ce (Task 2): confirmed
- _switch_news_view at line 1429: confirmed
- _build_collection_view at line 1455: confirmed
- _make_item_id at line 1649: confirmed
- syntax check: PASS
