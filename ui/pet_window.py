"""
ui/pet_window.py — DesktopPet 悬浮宠物窗口（永远置顶）
"""
import tkinter as tk
import threading
import json
import time
import os
import math
import subprocess
import random
import ctypes

from config import THEMES
from data.settings import load_settings
from ui.panel import MainPanel
from utils.objc import load_objc, get_all_ns_windows, get_style_mask, set_window_level, set_collection_behavior


class DesktopPet:
    ANIM_INTERVAL = 50

    def __init__(self):
        self.settings = load_settings()
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg='systemTransparent')

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.w = self.h = self.settings.get('pet_size', 200)
        self.x = sw - self.w - 28
        self.y = sh - self.h - 200
        self.root.geometry(f'{self.w}x{self.h}+{self.x}+{self.y}')

        self.canvas = tk.Canvas(self.root, width=self.w, height=self.h,
                                bg='systemTransparent', highlightthickness=0)
        self.canvas.pack()
        self._avatar_photo = self._load_avatar()

        # 小猫动画状态
        self._drag_x = self._drag_y = 0
        self._dragging = False
        self._press_time = 0
        self._hovering = False
        self._anim_frame = 0
        self._bouncing = False
        self._bounce_frame = 0
        self.canvas.bind('<ButtonPress-1>',    self._on_press)
        self.canvas.bind('<B1-Motion>',        self._on_drag)
        self.canvas.bind('<ButtonRelease-1>',  self._on_release)
        self.canvas.bind('<Enter>',            lambda e: setattr(self, '_hovering', True))
        self.canvas.bind('<Leave>',            lambda e: setattr(self, '_hovering', False))
        self.canvas.bind('<Button-2>',         self._show_menu)
        self.canvas.bind('<Control-Button-1>', self._show_menu)

        self.panel = MainPanel(self)

        self._menu = tk.Menu(self.root, tearoff=0,
                              bg='#2d2d2d', fg='#e0e0e0',
                              activebackground='#3d3d3d',
                              activeforeground='#4fc3f7',
                              font=('PingFang SC', 13))
        self._menu.add_command(label='🏠 打开主面板', command=self.panel.open)
        self._menu.add_separator()
        self._menu.add_command(label='❌ 退出',       command=self.root.quit)

        self._animate()
        self.root.after(200, self._fix_pet_transparent)
        # 每 2 秒重新强制置顶，防止全屏应用切换时被遮挡
        self.root.after(2000, self._keep_on_top)

    def _get_nswindow(self):
        """找到宠物对应的 NSWindow（styleMask==14），返回 (objc, sel, w) 或 None。"""
        result = load_objc()
        if not result:
            return None
        objc, sel, msg0 = result
        for w in get_all_ns_windows(objc, sel, msg0):
            if get_style_mask(objc, sel, w) == 14:
                return objc, sel, w
        return None

    def _fix_pet_transparent(self):
        """设置透明背景 + NSScreenSaverWindowLevel 置顶（高于全屏应用）。"""
        result = self._get_nswindow()
        if not result:
            return
        objc, sel, w = result
        try:
            # 透明背景
            NSColor_cls = objc.objc_getClass(b'NSColor')
            objc.objc_msgSend.restype = ctypes.c_void_p
            objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            clear = objc.objc_msgSend(NSColor_cls, sel('clearColor'))

            objc.objc_msgSend.restype = None
            objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool]
            objc.objc_msgSend(w, sel('setOpaque:'), ctypes.c_bool(False))

            objc.objc_msgSend.restype = None
            objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
            objc.objc_msgSend(w, sel('setBackgroundColor:'), clear)

            # NSScreenSaverWindowLevel=1000，高于全屏应用（kCGFloatingWindowLevel=5）
            set_window_level(objc, sel, w, 1000)

            # 让窗口出现在所有 Space（包括全屏应用的 Space）
            # NSWindowCollectionBehaviorCanJoinAllSpaces = 1 << 0
            # NSWindowCollectionBehaviorStationary = 1 << 4
            set_collection_behavior(objc, sel, w, (1 << 0) | (1 << 4))

            objc.objc_msgSend.restype = ctypes.c_void_p
            objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            objc.objc_msgSend(w, sel('display'))
        except Exception:
            pass

    def _keep_on_top(self):
        """每 2 秒重置 level，防止全屏切换后被压到底层。"""
        if not (self.root and self.root.winfo_exists()):
            return
        result = self._get_nswindow()
        if result:
            objc, sel, w = result
            try:
                set_window_level(objc, sel, w, 1000)
            except Exception:
                pass
        self.root.after(2000, self._keep_on_top)

    def set_emoji(self, em):
        """MainPanel 调用此方法更新悬浮窗显示的 emoji。"""
        self.settings['pet_emoji'] = em
        self.canvas.event_generate('<<EmojiChanged>>')

    def trigger_bounce(self):
        self._bouncing = True
        self._bounce_frame = 0

    def _animate(self):
        t = (self._anim_frame % 72) / 72

        if self._bouncing:
            p = self._bounce_frame / 10
            offset_y = int(-14 * math.sin(p * math.pi) * (self.w / 96))
            self._bounce_frame += 1
            if self._bounce_frame > 10:
                self._bouncing = False
        elif self._hovering:
            offset_y = int(-3 * (self.w / 96))
        else:
            offset_y = int(-4 * math.sin(2 * math.pi * t) * (self.w / 96))

        self._draw_pet(offset_y)
        self._anim_frame += 1
        self.root.after(self.ANIM_INTERVAL, self._animate)

    def _load_avatar(self):
        """加载 pet_avatar.png -> 圆形裁剪 ImageTk.PhotoImage，失败返回 None。"""
        from config import PET_AVATAR_FILE
        try:
            from PIL import Image, ImageDraw, ImageTk
        except ImportError:
            return None
        if not os.path.exists(PET_AVATAR_FILE):
            return None
        size = self.w
        size4 = size * 4
        src = Image.open(PET_AVATAR_FILE).convert('RGBA')
        src = src.resize((size4, size4), Image.LANCZOS)
        mask = Image.new('L', (size4, size4), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size4, size4), fill=255)
        src.putalpha(mask)
        result = src.resize((size, size), Image.LANCZOS)
        return ImageTk.PhotoImage(result)

    def reload_avatar(self):
        """由 MainPanel 在保存/重置头像后调用。"""
        self._avatar_photo = self._load_avatar()

    def _draw_pet(self, offset_y):
        self.canvas.delete('all')
        cx = self.w // 2
        cy = self.h // 2 + offset_y
        if self._avatar_photo:
            self.canvas.create_image(cx, cy, image=self._avatar_photo, anchor='center')
            self.canvas._avatar_ref = self._avatar_photo   # 防止 GC
        else:
            emoji = self.settings.get('pet_emoji', '🐱')
            font_size = max(20, int(self.w * 0.6))
            self.canvas.create_text(cx, cy, text=emoji,
                                    font=('Apple Color Emoji', font_size),
                                    anchor='center')

    def _on_press(self, e):
        self._drag_x, self._drag_y = e.x, e.y
        self._dragging = False
        self._press_time = time.time()

    def _on_drag(self, e):
        self._dragging = True
        self.x = self.root.winfo_x() + e.x - self._drag_x
        self.y = self.root.winfo_y() + e.y - self._drag_y
        self.root.geometry(f'+{self.x}+{self.y}')

    def _on_release(self, e):
        if not self._dragging and (time.time() - self._press_time) < 0.4:
            self.trigger_bounce()
            self.panel.open()
        self._dragging = False

    def _show_menu(self, e):
        self._menu.tk_popup(e.x_root, e.y_root)

    def run(self):
        self.root.mainloop()