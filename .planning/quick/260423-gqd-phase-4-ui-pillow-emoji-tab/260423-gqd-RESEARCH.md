# Phase 4: Custom Pet Image — Research

**Researched:** 2026-04-23
**Domain:** tkinter Canvas image rendering, Pillow circular crop, file upload UI, cross-widget live update
**Confidence:** HIGH

---

## Summary

Phase 4 adds user-uploadable pet avatars: a PNG circular crop stored at a fixed path, rendered in the DesktopPet floating window replacing the emoji, and also shown in the Pet Tab header. The Settings Tab gets an upload button and a reset button.

The existing codebase in `ui/pet_window.py` uses `canvas.create_text` with `('Apple Color Emoji', font_size)` to render the pet emoji. The switch to image rendering is a clean drop-in: `canvas.delete('all')` already runs every frame in `_draw_emoji`, so simply replacing `create_text` with `create_image` while holding an instance-level `ImageTk.PhotoImage` reference is sufficient. No animation loop restructuring is needed.

Pillow 12.2.0 is installed at the project's Python path (`/Library/Frameworks/Python.framework/Versions/3.11`). The 4x-supersample circular crop pipeline works correctly. `tkinter.filedialog.askopenfilename` is available. All patterns verified by running code.

**Primary recommendation:** Add `PET_AVATAR_FILE` constant to `config.py`, load/reload via a helper in `DesktopPet`, and propagate refresh via a `reload_avatar()` method that `MainPanel` calls after saving.

---

## Current State of `_draw_emoji` (pet_window.py lines 159–167)

```python
def _draw_emoji(self, offset_y):
    self.canvas.delete('all')
    emoji = self.settings.get('pet_emoji', '🐱')
    font_size = max(20, int(self.w * 0.6))
    cx = self.w // 2
    cy = self.h // 2 + offset_y
    self.canvas.create_text(cx, cy, text=emoji,
                            font=('Apple Color Emoji', font_size),
                            anchor='center')
```

`_animate()` calls `_draw_emoji(offset_y)` every 50 ms. The `canvas.delete('all')` + redraw pattern already handles clearing; switching from `create_text` to `create_image` just changes that one call.

---

## Architecture Patterns

### Pattern 1: Conditional render — image when avatar exists, emoji as fallback

`_draw_emoji` becomes `_draw_pet`:

```python
def _draw_pet(self, offset_y):
    self.canvas.delete('all')
    cx = self.w // 2
    cy = self.h // 2 + offset_y
    if self._avatar_photo:
        self.canvas.create_image(cx, cy, image=self._avatar_photo, anchor='center')
        # Keep reference alive — canvas.delete('all') does NOT destroy PhotoImage
        self.canvas._avatar_ref = self._avatar_photo
    else:
        emoji = self.settings.get('pet_emoji', '🐱')
        font_size = max(20, int(self.w * 0.6))
        self.canvas.create_text(cx, cy, text=emoji,
                                font=('Apple Color Emoji', font_size),
                                anchor='center')
```

`self._avatar_photo` is a `ImageTk.PhotoImage | None` held on the instance. Set it in `__init__` via `self._avatar_photo = self._load_avatar()`.

### Pattern 2: Load avatar helper

```python
def _load_avatar(self):
    """Load pet_avatar.png -> circular-cropped ImageTk.PhotoImage, or None."""
    from config import PET_AVATAR_FILE
    try:
        from PIL import Image, ImageDraw, ImageTk
    except ImportError:
        return None
    if not os.path.exists(PET_AVATAR_FILE):
        return None
    size = self.w                    # canvas size (default 200)
    size4 = size * 4                 # 4x supersample
    src = Image.open(PET_AVATAR_FILE).convert('RGBA')
    src = src.resize((size4, size4), Image.LANCZOS)
    mask = Image.new('L', (size4, size4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size4, size4), fill=255)
    src.putalpha(mask)
    result = src.resize((size, size), Image.LANCZOS)
    return ImageTk.PhotoImage(result)  # must be called after Tk root exists
```

Call from `__init__` AFTER `self.canvas.pack()` (Tk root already exists at that point).

### Pattern 3: `reload_avatar()` public method on `DesktopPet`

```python
def reload_avatar(self):
    """Called by MainPanel after saving a new avatar or resetting."""
    self._avatar_photo = self._load_avatar()
```

`MainPanel` calls `self.pet.reload_avatar()` after file copy + save.

### Pattern 4: Pillow 4x circular crop (verified working)

```python
from PIL import Image, ImageDraw, ImageTk

def make_circular_avatar(src_path: str, output_size: int) -> ImageTk.PhotoImage:
    size4 = output_size * 4
    img = Image.open(src_path).convert('RGBA')
    img = img.resize((size4, size4), Image.LANCZOS)
    mask = Image.new('L', (size4, size4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size4, size4), fill=255)
    img.putalpha(mask)
    img = img.resize((output_size, output_size), Image.LANCZOS)
    return ImageTk.PhotoImage(img)   # requires Tk root to exist
```

Verified: `PIL.Image.LANCZOS` is correct for Pillow 12.x (not `Image.ANTIALIAS` which was removed in Pillow 10).

### Pattern 5: Settings Tab — upload row

```python
from tkinter import filedialog
import shutil

def _upload_avatar(self):
    path = filedialog.askopenfilename(
        title='选择宠物图片',
        filetypes=[('图片', '*.png *.jpg *.jpeg *.webp'), ('所有文件', '*.*')]
    )
    if not path:
        return
    from config import PET_AVATAR_FILE
    shutil.copy(path, PET_AVATAR_FILE)
    self.pet.reload_avatar()
    self._refresh_pet_tab_avatar()   # update 60px circle in pet tab header
    self._avatar_status.configure(text='✅ 头像已更新')
    self.win.after(2000, lambda: self._avatar_status.configure(text=''))
```

Must run on the main thread — it is a button callback, so this is automatic.

### Pattern 6: Pet Tab — 60px circular avatar in header

Replace `self._pet_emoji_label` (currently a `tk.Label` with emoji font-72) with a Canvas:

```python
self._pet_avatar_canvas = tk.Canvas(
    left, width=60, height=60,
    bg=th['BG_CONTENT'], highlightthickness=0, bd=0
)
self._pet_avatar_canvas.pack(pady=(20, 4))
self._refresh_pet_tab_avatar()   # call to draw either image or emoji
```

Refresh method:

```python
def _refresh_pet_tab_avatar(self):
    if not (hasattr(self, '_pet_avatar_canvas') and
            self._pet_avatar_canvas.winfo_exists()):
        return
    c = self._pet_avatar_canvas
    c.delete('all')
    from config import PET_AVATAR_FILE
    try:
        from PIL import Image, ImageDraw, ImageTk
        if os.path.exists(PET_AVATAR_FILE):
            size4 = 240
            img = Image.open(PET_AVATAR_FILE).convert('RGBA')
            img = img.resize((size4, size4), Image.LANCZOS)
            mask = Image.new('L', (size4, size4), 0)
            ImageDraw.Draw(mask).ellipse((0,0,size4,size4), fill=255)
            img.putalpha(mask)
            img = img.resize((60, 60), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            c.create_image(30, 30, image=photo, anchor='center')
            c._img_ref = photo   # keep reference
            return
    except Exception:
        pass
    # Fallback: emoji
    c.create_text(30, 30, text=self.stats.mood_emoji(),
                  font=('Apple Color Emoji', 40), anchor='center')
```

### Pattern 7: Reset to default

```python
def _reset_avatar(self):
    from config import PET_AVATAR_FILE
    if os.path.exists(PET_AVATAR_FILE):
        os.remove(PET_AVATAR_FILE)
    self.pet.reload_avatar()          # sets _avatar_photo = None
    self._refresh_pet_tab_avatar()    # reverts to emoji
    self._avatar_status.configure(text='✅ 已恢复默认')
    self.win.after(2000, lambda: self._avatar_status.configure(text=''))
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Image loading + format conversion | Custom format parser | `PIL.Image.open().convert('RGBA')` |
| Anti-aliased circular mask | Manual pixel-by-pixel | `ImageDraw.ellipse` on L mask + `putalpha` |
| File browser dialog | Custom file picker | `tkinter.filedialog.askopenfilename` |
| File copy | Manual read/write | `shutil.copy(src, dst)` |

---

## Config Constant to Add

Add to `config.py`:

```python
PET_AVATAR_FILE = os.path.expanduser("~/.openclaw/workspace/desktop-pet/data/pet_avatar.png")
```

Using `data/pet_avatar.png` (under `data/`) keeps user data co-located with other data files and out of the module tree.

---

## Common Pitfalls

### Pitfall 1: ImageTk.PhotoImage garbage collection
**What goes wrong:** The image disappears (blank canvas) shortly after creation.
**Why it happens:** Python GC collects the `PhotoImage` object when no Python reference holds it; tkinter's internal reference is not counted by CPython.
**How to avoid:** Always store `self._avatar_photo` on the instance AND do `canvas._img_ref = photo` as a belt-and-suspenders backup after every `canvas.create_image` call.
**Warning signs:** Image shows briefly then disappears; no exception thrown.

### Pitfall 2: `Image.ANTIALIAS` removed in Pillow 10+
**What goes wrong:** `AttributeError: module 'PIL.Image' has no attribute 'ANTIALIAS'`
**Why it happens:** Pillow 10 removed the deprecated `ANTIALIAS` alias.
**How to avoid:** Use `Image.LANCZOS` — Pillow 12.2.0 is installed here, always use `LANCZOS`.

### Pitfall 3: `ImageTk.PhotoImage` before Tk root
**What goes wrong:** `RuntimeError: Too early to create image: no default root window`
**Why it happens:** `PhotoImage` requires a Tk root to exist.
**How to avoid:** Call `_load_avatar()` only after `self.canvas.pack()` in `DesktopPet.__init__`, and call `_refresh_pet_tab_avatar()` only inside `_build_pet_tab` (window already open).

### Pitfall 4: Breaking `_sync_pet_ui` which calls `_pet_emoji_label.configure(text=...)`
**What goes wrong:** `AttributeError` on `configure(text=...)` if `_pet_emoji_label` is replaced with a Canvas.
**Why it happens:** `_sync_pet_ui` currently updates `self._pet_emoji_label.configure(text=mood_em)` (line 1777).
**How to avoid:** After replacing `_pet_emoji_label` with a Canvas, update `_sync_pet_ui` to call `_refresh_pet_tab_avatar()` instead of configuring `_pet_emoji_label`. Alternatively, keep `_pet_emoji_label` as a hidden fallback label below the canvas — simpler is to just update `_sync_pet_ui`.

### Pitfall 5: macOS Retina / canvas pixel doubling
**What goes wrong:** Image appears blurry or half-sized on Retina displays.
**Why it happens:** macOS Retina has 2x physical pixels per logical pixel; tkinter canvas uses logical pixels.
**How to avoid:** For the 200px DesktopPet canvas, render at `self.w` logical pixels — Retina scaling is handled by the OS compositor for the canvas widget. The 4x supersampling helps with edge quality. No explicit doubling is needed for `canvas.create_image`.

### Pitfall 6: `filedialog` returning empty string on cancel
**What goes wrong:** `shutil.copy('', dst)` raises `FileNotFoundError`.
**Why it happens:** `askopenfilename` returns `''` (empty string) on cancel.
**How to avoid:** Always guard: `if not path: return`.

---

## Standard Stack

| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| Pillow (`PIL`) | 12.2.0 | Image open, resize, circular mask, RGBA | Installed at Python 3.11 path — verified |
| `tkinter.filedialog` | stdlib | File picker dialog | Available — verified |
| `shutil` | stdlib | File copy | stdlib, always available |
| `os` | stdlib | File existence check, remove | already imported in pet_window.py |

---

## Files to Modify

| File | Change |
|------|--------|
| `config.py` | Add `PET_AVATAR_FILE` constant |
| `ui/pet_window.py` | Add `_load_avatar()`, `reload_avatar()`, change `_draw_emoji` → `_draw_pet` |
| `ui/panel.py` `_build_pet_tab` | Replace `_pet_emoji_label` tk.Label with Canvas + `_refresh_pet_tab_avatar()` |
| `ui/panel.py` `_sync_pet_ui` | Update to call `_refresh_pet_tab_avatar()` instead of `_pet_emoji_label.configure` |
| `ui/panel.py` `_build_settings_tab` | Add upload row + reset button inside `宠物形象` card |
| `ui/panel.py` | Add `_upload_avatar()`, `_reset_avatar()`, `_refresh_pet_tab_avatar()` methods |

---

## Exact `_sync_pet_ui` Lines to Change

Lines 1776–1777 in `panel.py`:

```python
# CURRENT:
if hasattr(self, '_pet_emoji_label') and self._pet_emoji_label.winfo_exists():
    self._pet_emoji_label.configure(text=mood_em)

# REPLACE WITH:
self._refresh_pet_tab_avatar()
```

The avatar canvas should reflect current mood emoji when no custom avatar is set, so `_refresh_pet_tab_avatar` always reads `self.stats.mood_emoji()` fresh — no stale state.

---

## Settings Tab UI Layout

Inside the existing `card1 = _section('宠物形象')` card, after the emoji row:

```
[divider line]
[row: "自定义头像"  | [上传图片 btn]  [重置默认 btn]  [status label] ]
```

Use `tk.Label` styled as buttons (consistent with rest of settings tab pattern). The status label is inline (not a separate `_settings_status`) to avoid overwriting the save-settings status.

---

## Environment Availability

| Dependency | Required By | Available | Version |
|------------|-------------|-----------|---------|
| Pillow | Circular crop, image load | Yes | 12.2.0 |
| tkinter.filedialog | Upload dialog | Yes | stdlib |
| shutil | File copy | Yes | stdlib |

No missing dependencies.

---

## Sources

- Verified by running code against `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11`
- Pillow 12.2.0 `Image.LANCZOS` — confirmed active (ANTIALIAS removed in Pillow 10)
- `canvas.create_image` / `canvas.create_text` coexistence — verified via test
- `ImageTk.PhotoImage` GC behavior — verified (RuntimeError without root, confirmed GC pattern)
- Source code read: `ui/pet_window.py` (full), `ui/panel.py` lines 1664–2612, `config.py`, `data/pet/__init__.py`
