---
phase: quick
plan: 260424-g7w
subsystem: ui/notes
tags: [markdown, wysiwyg, tkinter, split-pane, toolbar]
dependency_graph:
  requires: [260424-eg2]
  provides: [NOTES-WYSIWYG-01]
  affects: [ui/panel.py]
tech_stack:
  added: []
  patterns: [split-pane editor, inline format toolbar, KeyRelease live preview]
key_files:
  modified: [ui/panel.py]
  created: []
decisions:
  - Reuse self._notes_text as the left editor widget (pack with in_= parameter) to preserve _notes_open_readonly compatibility
  - Split-pane container destroyed and rebuilt on every editor open to guarantee theme/content refresh
  - _notes_preview is a fresh tk.Text per editor open (not reused) — simpler lifecycle, no stale state
metrics:
  duration: ~5 minutes
  completed: "2026-04-24T03:45:32Z"
  tasks_completed: 1
  files_modified: 1
---

# Phase quick Plan 260424-g7w: Markdown WYSIWYG Split-Pane Notes Editor Summary

Replaced the toggle-preview edit mode with a persistent left-right WYSIWYG split-pane layout featuring a 7-button format toolbar and real-time KeyRelease preview rendering.

## What Was Built

### Methods Modified

| Method | Change |
|--------|--------|
| `_build_notes_tab` | Removed `_notes_preview_btn` creation (lines ~2157-2162); replaced `_notes_previewing = False` with `_notes_edit_pane = None` and `_notes_preview = None` |
| `_notes_open_editor` | Full rewrite: now builds left/right split-pane inside `_notes_edit_pane`, creates 7-button format toolbar, wires `KeyRelease` to live preview |
| `_notes_show_list` | Removed `_notes_preview_btn.pack_forget()` and `_notes_previewing = False`; added `_notes_edit_pane` destroy/cleanup |
| `_notes_open_readonly` | Removed `_notes_preview_btn.pack_forget()`; added `_notes_edit_pane` destroy/cleanup before re-packing `self._notes_text` |

### Methods Added

| Method | Purpose |
|--------|---------|
| `_notes_toolbar_wrap(prefix, suffix, placeholder)` | Format toolbar click handler — wraps selected text with prefix+suffix, or inserts placeholder at cursor if no selection; triggers `KeyRelease` to refresh preview |

### Methods Deleted

| Method | Reason |
|--------|--------|
| `_notes_toggle_preview` | Replaced by always-visible split-pane preview |

### New Instance Attributes

| Attribute | Type | Purpose |
|-----------|------|---------|
| `self._notes_edit_pane` | `tk.Frame \| None` | The split-pane container frame; destroyed and rebuilt each time `_notes_open_editor` is called |
| `self._notes_preview` | `tk.Text \| None` | The right-side read-only preview widget; destroyed with `_notes_edit_pane` |

### Deleted Attributes/References

| Attribute/Reference | Where removed |
|--------------------|---------------|
| `self._notes_previewing` | Removed from `_build_notes_tab` initialization and from `_notes_show_list` |
| `self._notes_preview_btn` | Widget creation removed from `_build_notes_tab`; all `.pack()` / `.pack_forget()` calls removed |

## Split-Pane Layout

```
self._notes_body
└── self._notes_edit_pane  (tk.Frame, fill=BOTH expand=True)
    ├── left  (tk.Frame, side=LEFT, fill=BOTH expand=True)
    │   ├── fmt_bar  (height=36, fill=X) — 7 format buttons: B I U H1 H2 • 1.
    │   └── self._notes_text  (pack in_=left, fill=BOTH expand=True)
    ├── divider  (tk.Frame, width=1, bg=DIVIDER, fill=Y)
    └── right  (tk.Frame, side=LEFT, fill=BOTH expand=True)
        └── self._notes_preview  (tk.Text, DISABLED, fill=BOTH expand=True)
```

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- ui/panel.py: FOUND
- commit 7a16860: FOUND
- _notes_toolbar_wrap method: PASS
- _notes_toggle_preview deleted: PASS
- _notes_edit_pane in code: PASS
- _notes_preview_btn removed: PASS
- _notes_previewing removed: PASS
- py_compile: PASS
