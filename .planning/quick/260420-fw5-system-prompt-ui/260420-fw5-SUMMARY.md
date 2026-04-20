---
phase: 260420-fw5-system-prompt-ui
plan: 01
subsystem: settings-ui, pet-tab, ai-chat
tags: [settings, personalization, system-prompt, tkinter]
dependency_graph:
  requires: []
  provides: [pet_name, pet_personality, pet_catchphrase settings persistence and AI injection]
  affects: [_build_settings_tab, _save_settings, _build_pet_tab, _stream_pet_ai]
tech_stack:
  added: []
  patterns: [Label-button radio group for personality selection, StringVar-backed Entry for text input]
key_files:
  created: []
  modified:
    - desktop_pet.py
decisions:
  - _update_personality_btns defined before the for-loop so initial state can be set after all buttons are created
  - pet_name display label stored as self._pet_name_display_lbl so _save_settings can refresh it without rebuilding the tab
metrics:
  duration: "~8 minutes"
  completed: "2026-04-20T03:30:41Z"
  tasks_completed: 2
  files_modified: 1
---

# Phase 260420-fw5 Plan 01: System Prompt UI Summary

宠物自定义设置三项（名字、性格、口头禅）通过 settings.json 持久化，在宠物 Tab 展示名字，在 AI 对话 system prompt 中动态注入三者。

## What Was Built

Added three pet customization fields to the Critter desktop pet app:

1. **Settings Tab "宠物性格" section** — new card below the existing emoji picker with:
   - Name entry (tk.Entry bound to `self._pet_name_var`, default "小猫")
   - 5-option personality radio-style Label buttons (温柔/活泼/傲娇/淡定/搞笑, selected option highlighted with accent color)
   - Catchphrase entry (tk.Entry bound to `self._catchphrase_var`, default "喵~")

2. **Pet Tab name label** — `self._pet_name_display_lbl` inserted between mood label and action buttons; shows current pet_name from settings.

3. **AI system prompt injection** — `_stream_pet_ai` now reads pet_name, pet_personality, pet_catchphrase from `self.pet.settings` and builds a richer system prompt: `你是一只可爱的桌面宠物 {emoji}，名字叫{pet_name}，性格{pet_personality}，说话简短可爱，偶尔使用你的口头禅"{pet_catchphrase}"...`

4. **Save logic** — `_save_settings` writes all three keys to settings.json and refreshes the pet tab name label if it exists.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 40e286e | feat(260420-fw5-01): add 宠物性格 section in settings tab |
| Task 2 | f368da3 | feat(260420-fw5-01): save name/personality/catchphrase + pet tab label + AI system prompt |

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. All three fields are fully wired: UI -> save -> settings.json -> AI system prompt.

## Self-Check: PASSED

- desktop_pet.py exists and passes AST syntax check
- Commits 40e286e and f368da3 present in git log
- settings.json readable; pet_name/pet_personality/pet_catchphrase keys will be written on first save
