---
phase: quick
plan: 260424-eg2
subsystem: ui/notes
tags: [markdown, tkinter, notes, preview, rendering]
dependency_graph:
  requires: []
  provides: [_strip_markdown, _render_markdown_in_widget, notes-preview-toggle]
  affects: [ui/panel.py, notes-tab]
tech_stack:
  added: []
  patterns: [tkinter Text widget tags for styled rendering, re.sub for markdown stripping]
key_files:
  created: []
  modified:
    - ui/panel.py
decisions:
  - Used re.MULTILINE for block-level patterns (headings/lists) so they only match line-starts
  - _notes_open_readonly auto-renders markdown; no preview button shown (diary is always rendered)
  - _notes_toggle_preview saves content before rendering, restores via _notes_open_editor on exit
metrics:
  duration: ~8 minutes
  completed_date: "2026-04-24T02:29:17Z"
  tasks_completed: 2
  files_modified: 1
---

# Quick Task 260424-eg2: Markdown Rendering in Notes Tab Summary

**One-liner:** Markdown preview in notes tab via tkinter Text widget tags — h1/h2/h3/bold/italic/bullet rendered in-place, diary auto-rendered, card summaries stripped of Markdown symbols.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | _strip_markdown() + _render_markdown_in_widget() helpers | 1168f98 | ui/panel.py |
| 2 | Preview/edit toggle button + card summary stripping | 8db328f | ui/panel.py |

## What Was Built

### `_strip_markdown(text: str) -> str`
Pure-text extractor using `re.sub`. Removes `**bold**`, `*italic*`, `__bold__`, `_italic_`, `# headings` (1-3 levels), and `- / *` list prefixes. Used for card summary display.

### `_render_markdown_in_widget(widget, text: str)`
Renders Markdown into a `tk.Text` widget using tags:
- `h1`: PingFang SC 18pt bold, FG_ACCENT color
- `h2`: PingFang SC 15pt bold, FG_ACCENT color
- `h3`: PingFang SC 13pt bold, FG_ACCENT color
- `bold`: PingFang SC 13pt bold
- `italic`: PingFang SC 13pt italic
- `bullet`: lmargin1=24, lmargin2=32 (• prefix added)
- Inline bold/italic parsed with `re.split` within non-heading lines
- Sets widget state=DISABLED after rendering (read-only preview)

### Preview/Edit Toggle Button
- `👁 预览` button added to notes toolbar (right-aligned, next to 💾 保存)
- Only visible in edit mode; hidden in list and diary-readonly modes
- Clicking toggles `_notes_previewing` state:
  - ON: reads current text, calls `_render_markdown_in_widget`, hides Save button, shows `✏️ 编辑`
  - OFF: resets to `👁 预览`, calls `_notes_open_editor` to restore editable content

### Diary Auto-Render
`_notes_open_readonly` now calls `_render_markdown_in_widget` instead of setting state=DISABLED manually. Diary entries always display with Markdown styling.

### Card Summary Stripping
`_make_card` now runs `_strip_markdown` before truncating to 20 chars, so card previews never show `**`, `*`, `#`, or `-` symbols.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- ui/panel.py modified and syntactically valid (import check passed)
- Commit 1168f98 exists: `_strip_markdown` + `_render_markdown_in_widget` added after `_notes_delete`
- Commit 8db328f exists: preview button, toggle method, auto-render diary, card stripping
- Python syntax: `import ui.panel` completes without error
