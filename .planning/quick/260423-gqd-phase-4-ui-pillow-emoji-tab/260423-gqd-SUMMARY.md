---
phase: 260423-gqd
plan: 01
subsystem: ui/avatar
tags: [pillow, custom-image, pet-window, panel, settings-tab, pet-tab]
dependency_graph:
  requires: [260423-fma (mood system, Pet Tab layout finalized)]
  provides: [custom avatar upload, circular crop, avatar persistence, Settings Tab upload/reset UI]
  affects: [ui/pet_window.py, ui/panel.py, config.py]
tech_stack:
  added: [Pillow (PIL) for RGBA image processing, ImageDraw circular mask, ImageTk.PhotoImage]
  patterns: [graceful Pillow import fallback, _img_ref canvas anti-GC pattern]
key_files:
  created: []
  modified:
    - config.py
    - ui/pet_window.py
    - ui/panel.py
decisions:
  - Pillow imported lazily inside methods so app runs cleanly even without Pillow installed
  - 4x supersampling (size4 = size * 4) used for anti-aliased circular crop in floating window
  - canvas._img_ref / canvas._avatar_ref pattern used to prevent GC of PhotoImage objects
  - _pet_emoji_label fully removed and replaced with _pet_avatar_canvas (Canvas widget) throughout
metrics:
  duration: ~10 min
  completed: 2026-04-23
  tasks: 3
  files: 3
---

# Phase 260423-gqd Plan 01: Custom Pet Avatar (Pillow circular crop + upload/reset UI) Summary

**One-liner:** Pillow circular-crop avatar upload for floating window and Pet Tab with Settings Tab upload/reset buttons, graceful emoji fallback when no avatar or Pillow absent.

## Tasks Completed

| # | Task | Commit | Files Modified |
|---|------|--------|----------------|
| 1 | config.py add PET_AVATAR_FILE constant | a8b29dc | config.py |
| 2 | pet_window.py: _load_avatar, reload_avatar, _draw_pet | 9ed4b70 | ui/pet_window.py |
| 3 | panel.py: Pet Tab Canvas, Settings Tab upload/reset row, 3 new methods | 21b6346 | ui/panel.py |

## What Was Built

- **config.py** — `PET_AVATAR_FILE` constant pointing to `data/pet_avatar.png`
- **ui/pet_window.py** — `_load_avatar()` opens the file, applies 4x supersampled Pillow circular RGBA mask, returns `ImageTk.PhotoImage`; `reload_avatar()` public API for MainPanel to call; `_draw_pet()` replaces `_draw_emoji()` with conditional image-or-emoji rendering
- **ui/panel.py** — Pet Tab left-side avatar replaced with 60px `tk.Canvas`; `_refresh_pet_tab_avatar()` renders circular avatar or mood emoji fallback; `_upload_avatar()` launches file dialog, copies to `PET_AVATAR_FILE`, triggers reload; `_reset_avatar()` deletes the file and restores emoji; Settings Tab "宠物形象" card gains divider + "自定义头像" row with "上传图片" and "重置默认" buttons plus status label

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed three stale `_pet_emoji_label` references**
- **Found during:** Task 3 post-edit grep
- **Issue:** `__init__` initialized `self._pet_emoji_label = None`; `open()` had `if hasattr(self, '_pet_emoji_label'): self._pet_emoji_label.configure(...)` — both would be dead/misleading code after the label was replaced
- **Fix:** Changed `__init__` to initialize `self._pet_avatar_canvas = None`; replaced `open()` block with `self._refresh_pet_tab_avatar()`
- **Files modified:** ui/panel.py
- **Commit:** 21b6346 (included in Task 3 commit)

## Known Stubs

None — all data paths are wired. Avatar reads from `data/pet_avatar.png` on disk; fallback to mood emoji is intentional behavior when file absent.

## Success Criteria Check

- [x] config.py has PET_AVATAR_FILE constant
- [x] Floating window shows circular avatar when data/pet_avatar.png exists, emoji when absent
- [x] Settings Tab "宠物形象" card has upload + reset buttons
- [x] Pet Tab avatar Canvas syncs with floating window state
- [x] App starts without error even if Pillow unavailable (try/except ImportError returns None -> emoji fallback)

## Self-Check: PASSED

Files verified:
- config.py: FOUND PET_AVATAR_FILE at line 16
- ui/pet_window.py: FOUND _load_avatar, reload_avatar, _draw_pet, _avatar_photo
- ui/panel.py: FOUND _refresh_pet_tab_avatar, _upload_avatar, _reset_avatar, _pet_avatar_canvas, _avatar_status

Commits verified:
- a8b29dc: config.py
- 9ed4b70: pet_window.py
- 21b6346: panel.py
