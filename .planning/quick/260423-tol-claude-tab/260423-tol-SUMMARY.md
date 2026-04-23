---
phase: 260423-tol
plan: 01
subsystem: notes-diary
tags: [diary, notes, pet-interaction, claude-cli, ui]
dependency_graph:
  requires: [services/notes, services/ai, ui/panel, data/pet, config]
  provides: [services/diary, diary-counts-persistence, diary-card-ui]
  affects: [ui/panel.py, services/notes/__init__.py, config.py]
tech_stack:
  added: [services/diary/__init__.py]
  patterns: [background-thread-generation, threaded-ui-refresh, kind-field-polymorphism]
key_files:
  created:
    - services/diary/__init__.py
  modified:
    - config.py
    - services/notes/__init__.py
    - ui/panel.py
decisions:
  - "Diary counts stored in separate diary_counts.json (not pet_stats.json) for isolation"
  - "Diary generation runs on daemon thread to avoid blocking tkinter main loop"
  - "Diary cards use kind='diary' field for polymorphic rendering in _make_card"
  - "Readonly view reuses edit layout frame but sets Text widget to DISABLED state"
  - "Curly quote characters in prompt built with unicode escapes to avoid f-string syntax error"
metrics:
  duration_seconds: 646
  completed_date: "2026-04-23"
  tasks_completed: 3
  tasks_total: 4
  files_modified: 4
  files_created: 1
---

# Phase 260423-tol Plan 01: Pet Diary Summary

**One-liner:** Pet-perspective daily diary auto-generated via Claude CLI, stored as `kind='diary'` notes with distinctive blue card UI and read-only view in the Notes tab.

## What Was Built

Daily interaction counting (feed/play/rest/pet) persists to `diary_counts.json`. Every time the Notes tab is opened (or switched to), `_check_and_generate_diary()` fires in a background thread — if today's diary doesn't exist, it calls Claude CLI to produce a ~100-character first-person cat diary based on interaction counts and current mood. The diary is saved via `notes_service.create_diary()` with `kind='diary'` and `date` fields, then the Notes list refreshes. Diary cards render with a blue `BG_SEL` background, 2px `FG_ACCENT` border, and "📖 宠物日记" header. Clicking a diary card opens a read-only full-text view instead of the editor.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Interaction count persistence + diary trigger detection | 96ea0dd |
| 2 | Diary generation service (Claude CLI) | dd29c5f |
| 3 | Diary card special style + readonly view | 718d526 |
| 4 | Human verify (checkpoint — awaiting) | — |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed f-string syntax error from curly quotes in diary prompt**
- **Found during:** Task 2 verification
- **Issue:** The plan's prompt string used curly quotes `"` and `"` inside double-quoted f-strings, causing a SyntaxError (`invalid syntax. Perhaps you forgot a comma?`)
- **Fix:** Replaced inline curly quotes with `'\u201c' + pet_catchphrase + '\u201d'` built before the prompt string
- **Files modified:** services/diary/__init__.py
- **Commit:** dd29c5f

## Known Stubs

None — diary generation calls real Claude CLI and returns live text. Interaction counts read real button press state from diary_counts.json.

## Self-Check: PASSED

Files verified:
- services/diary/__init__.py: EXISTS
- DIARY_COUNTS_FILE constant in config.py: EXISTS
- create_diary() in services/notes/__init__.py: EXISTS
- _notes_open_readonly in ui/panel.py: EXISTS

Commits verified:
- 96ea0dd: EXISTS
- dd29c5f: EXISTS
- 718d526: EXISTS
