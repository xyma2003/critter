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

try:
    from PIL import Image, ImageDraw, ImageTk
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

from config import THEMES, FG_MAIN, FG_ACCENT
from data.settings import load_settings
from ui.panel import MainPanel


class DesktopPet:
    ANIM_INTERVAL = 50

    # 小猫配色
    _CAT_PALETTES = {
        'orange': dict(body='#f5a623', belly='#fde8c0', ear_in='#f08080',
                       stripe='#d4881e', eye='#2d8a4e', nose='#e87d9e',
                       whisker='#c8b89a', mouth='#c0506a'),
        'gray':   dict(body='#9e9e9e', belly='#e0e0e0', ear_in='#f48fb1',
                       stripe='#757575', eye='#5c6bc0', nose='#e87d9e',
                       whisker='#bdbdbd', mouth='#9e6070'),
        'white':  dict(body='#f0f0f0', belly='#ffffff', ear_in='#f48fb1',
                       stripe='#cccccc', eye='#42a5f5', nose='#e87d9e',
                       whisker='#cccccc', mouth='#b06080'),
        'black':  dict(body='#3a3a3a', belly='#6a6a6a', ear_in='#f08080',
                       stripe='#222222', eye='#ffca28', nose='#e87d9e',
                       whisker='#888888', mouth='#c06070'),
    }

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

        # 小猫动画状态
        self._drag_x = self._drag_y = 0
        self._dragging = False
        self._press_time = 0
        self._hovering = False
        self._anim_frame = 0
        self._bouncing = False
        self._bounce_frame = 0
        self._blink_timer = 0
        self._BLINK_INTERVAL = 80   # frames between blinks
        self._cat_mood = 'normal'   # 'normal' | 'happy' | 'sleepy' | 'excited'
        self._mood_timer = 0        # frames remaining for temp mood

        # Pillow 帧动画状态（需在 canvas.pack() 后初始化）
        if _PIL_AVAILABLE:
            self._cat_frames = self._generate_cat_frames()
            self._idle_frame_idx = 0
            self._blink_cooldown = 80   # 距下次眨眼的帧数
            self._blink_active = False  # 正在显示眨眼帧
            self._blink_duration = 0   # 眨眼帧剩余显示帧数
            self._cat_image_id = None  # canvas image item id
        else:
            self._cat_frames = None

        self.canvas.bind('<ButtonPress-1>',    self._on_press)
        self.canvas.bind('<B1-Motion>',        self._on_drag)
        self.canvas.bind('<ButtonRelease-1>',  self._on_release)
        self.canvas.bind('<Enter>',            lambda e: setattr(self, '_hovering', True))
        self.canvas.bind('<Leave>',            lambda e: setattr(self, '_hovering', False))
        self.canvas.bind('<Button-2>',         self._show_menu)
        self.canvas.bind('<Control-Button-1>', self._show_menu)

        self.panel = MainPanel(self)

        self._menu = tk.Menu(self.root, tearoff=0,
                              bg='#2d2d2d', fg=FG_MAIN,
                              activebackground='#3d3d3d',
                              activeforeground=FG_ACCENT,
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
        try:
            objc = ctypes.cdll.LoadLibrary('/usr/lib/libobjc.dylib')
            objc.objc_getClass.restype = ctypes.c_void_p
            objc.objc_getClass.argtypes = [ctypes.c_char_p]
            objc.sel_registerName.restype = ctypes.c_void_p
            objc.sel_registerName.argtypes = [ctypes.c_char_p]

            def sel(name):
                return objc.sel_registerName(name.encode())

            def msg0(obj, sel_name):
                objc.objc_msgSend.restype = ctypes.c_void_p
                objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
                return objc.objc_msgSend(obj, sel(sel_name))

            NSApp = msg0(objc.objc_getClass(b'NSApplication'), 'sharedApplication')
            windows = msg0(NSApp, 'windows')
            objc.objc_msgSend.restype = ctypes.c_long
            objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            count = objc.objc_msgSend(windows, sel('count'))

            for i in range(count):
                objc.objc_msgSend.restype = ctypes.c_void_p
                objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
                w = objc.objc_msgSend(windows, sel('objectAtIndex:'), ctypes.c_ulong(i))
                objc.objc_msgSend.restype = ctypes.c_ulong
                objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
                if objc.objc_msgSend(w, sel('styleMask')) == 14:
                    return objc, sel, w
        except Exception:
            pass
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
            objc.objc_msgSend.restype = None
            objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
            objc.objc_msgSend(w, sel('setLevel:'), ctypes.c_long(1000))

            # 让窗口出现在所有 Space（包括全屏应用的 Space）
            # NSWindowCollectionBehaviorCanJoinAllSpaces = 1 << 0
            # NSWindowCollectionBehaviorStationary = 1 << 4
            collection_behavior = (1 << 0) | (1 << 4)
            objc.objc_msgSend.restype = None
            objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
            objc.objc_msgSend(w, sel('setCollectionBehavior:'), ctypes.c_ulong(collection_behavior))

            objc.objc_msgSend.restype = ctypes.c_void_p
            objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            objc.objc_msgSend(w, sel('display'))
        except Exception:
            pass

    def _keep_on_top(self):
        """每 2 秒重置 level，防止全屏切换后被压到底层。"""
        result = self._get_nswindow()
        if result:
            objc, sel, w = result
            try:
                objc.objc_msgSend.restype = None
                objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
                objc.objc_msgSend(w, sel('setLevel:'), ctypes.c_long(1000))
            except Exception:
                pass
        self.root.after(2000, self._keep_on_top)

    def set_emoji(self, em):
        """MainPanel 调用此方法反映心情；映射到小猫表情状态。"""
        mood_map = {
            '😊': 'happy',   '🙂': 'normal',   '😐': 'normal',
            '😔': 'sleepy',  '😞': 'sleepy',   '😴': 'sleepy',
            '😋': 'happy',   '😹': 'excited',  '😸': 'happy',
            '😺': 'happy',   '😍': 'excited',  '🎉': 'excited',
        }
        self._cat_mood = mood_map.get(em, 'normal')
        self._mood_timer = 20   # hold for 20 frames then back to normal

    def trigger_bounce(self):
        self._bouncing = True
        self._bounce_frame = 0
        self._cat_mood = 'excited'
        self._mood_timer = 16

    def _generate_cat_frames(self):
        """生成3D卡通浣熊帧：灰棕条纹身体、白色胸腹、眼罩纹、举手站姿、环纹尾巴。"""
        if not _PIL_AVAILABLE:
            return None
        import math as _math
        size = self.w
        s = size / 200

        def make_frame(body_offset_x=0, eye_mode='normal'):
            sz2 = size * 3
            s2 = sz2 / 200
            def sc(v): return max(1, int(v * s2))

            img = Image.new('RGBA', (sz2, sz2), (0, 0, 0, 0))
            d = ImageDraw.Draw(img, 'RGBA')
            cx = sz2 // 2 + body_offset_x * 3

            # ── 颜色 ──
            fur_gray    = (160, 148, 130, 255)   # 主体灰棕
            fur_light   = (210, 200, 185, 255)   # 高光
            fur_dark    = (100,  88,  72, 255)   # 深棕条纹/眼罩
            white_fur   = (245, 242, 235, 255)   # 脸部/胸腹白毛
            white_light = (255, 255, 255, 255)   # 纯白高光
            nose_color  = (210, 100,  90, 255)   # 粉红鼻
            mouth_color = (130,  60,  50, 255)
            outline     = (60,   45,  30, 255)
            eye_brown   = (120,  70,  30, 255)   # 虹膜棕色
            black       = (20,   12,   5, 255)
            tail_ring   = (80,   68,  52, 255)   # 尾巴深环

            # ── 布局 ──
            head_r  = sc(50)
            head_cy = sc(68)
            body_ry = sc(38)
            body_rx = sc(42)
            body_cy = head_cy + head_r + body_ry - sc(18)

            def shaded_ellipse(x, y, rx, ry, base, light, ol=outline, lw=2):
                d.ellipse([x-rx, y-ry, x+rx, y+ry], fill=base, outline=ol, width=sc(lw))
                hlx, hly = int(rx*0.5), int(ry*0.45)
                d.ellipse([x-hlx, y-hly-sc(3), x+sc(3), y+sc(3)], fill=light)

            # ══ 1. 尾巴（身体后面，先画在最底层） ══
            # 从身体右下角弯出来的环纹尾巴
            tail_cx = cx + body_rx - sc(8)
            tail_cy = body_cy + body_ry - sc(12)
            # 尾巴主体弯曲：用一系列椭圆模拟
            tail_r = sc(14)
            for i, (tx_off, ty_off, tr) in enumerate([
                (sc(20), sc(10),  sc(13)),
                (sc(38), sc(2),   sc(12)),
                (sc(48), sc(-14), sc(11)),
                (sc(44), sc(-30), sc(10)),
            ]):
                ring = (i % 2 == 0)
                fill = tail_ring if ring else fur_gray
                d.ellipse([tail_cx+tx_off-tr, tail_cy+ty_off-tr,
                           tail_cx+tx_off+tr, tail_cy+ty_off+tr],
                          fill=fill, outline=outline, width=sc(2))

            # ══ 2. 身体（圆胖椭圆） ══
            shaded_ellipse(cx, body_cy, body_rx, body_ry, fur_gray, fur_light)
            # 身体横条纹（3条深色弧线）
            for y_off in [-sc(12), sc(2), sc(16)]:
                by = body_cy + y_off
                d.arc([cx - body_rx + sc(6), by - sc(8),
                       cx + body_rx - sc(6), by + sc(8)],
                      start=200, end=340, fill=fur_dark, width=sc(3))
            # 胸腹白毛椭圆
            d.ellipse([cx - sc(24), body_cy - sc(28),
                       cx + sc(24), body_cy + body_ry - sc(4)],
                      fill=white_fur)

            # ══ 3. 举起的手臂（在身体前面，手掌朝前） ══
            for sign in (-1, 1):
                # 上臂：从肩部斜向上
                arm_sx = cx + sign * (body_rx - sc(8))
                arm_sy = body_cy - sc(20)
                arm_ex = cx + sign * (body_rx + sc(18))
                arm_ey = body_cy - sc(48)
                # 上臂椭圆
                arm_cx = (arm_sx + arm_ex) // 2
                arm_cy = (arm_sy + arm_ey) // 2
                shaded_ellipse(arm_cx, arm_cy, sc(13), sc(22), fur_gray, fur_light)
                # 手掌（圆形，正面朝向）
                paw_x = arm_ex
                paw_y = arm_ey - sc(4)
                shaded_ellipse(paw_x, paw_y, sc(14), sc(12), white_fur, white_light, outline)
                # 手指分割线（3条）
                for fi in [-sc(5), 0, sc(5)]:
                    d.line([paw_x + fi, paw_y - sc(8),
                            paw_x + fi, paw_y - sc(2)],
                           fill=outline, width=sc(1))

            # ══ 4. 圆头 ══
            shaded_ellipse(cx, head_cy, head_r, head_r, fur_gray, fur_light)

            # 脸部白色区域（鼻吻部）
            d.ellipse([cx - sc(32), head_cy - sc(10),
                       cx + sc(32), head_cy + sc(32)],
                      fill=white_fur)

            # ══ 5. 圆耳朵 ══
            ear_r  = sc(18)
            ear_lx = cx - sc(32)
            ear_rx = cx + sc(32)
            ear_cy = head_cy - head_r + sc(16)
            for ex in [ear_lx, ear_rx]:
                shaded_ellipse(ex, ear_cy, ear_r, ear_r, fur_gray, fur_light)
                # 耳内白色
                d.ellipse([ex - sc(10), ear_cy - sc(10),
                           ex + sc(10), ear_cy + sc(10)], fill=white_fur)

            # ══ 6. 眼罩纹（深棕色，覆盖眼睛区域） ══
            mask_y = head_cy - sc(12)
            for sign, ex in [(-1, cx - sc(20)), (1, cx + sc(20))]:
                d.ellipse([ex - sc(18), mask_y - sc(12),
                           ex + sc(18), mask_y + sc(14)],
                          fill=fur_dark)

            # ══ 7. 眼睛 ══
            eye_lx = cx - sc(20)
            eye_rx = cx + sc(20)
            eye_y  = head_cy - sc(10)
            er = sc(14)

            for ex in [eye_lx, eye_rx]:
                ey = eye_y
                if eye_mode in ('blink', 'sleepy'):
                    d.arc([ex - er, ey - sc(5), ex + er, ey + sc(5)],
                          start=0, end=180, fill=white_light, width=sc(4))
                elif eye_mode == 'happy':
                    d.arc([ex - er, ey - sc(10), ex + er, ey + sc(10)],
                          start=180, end=360, fill=white_light, width=sc(6))
                else:
                    # 白色巩膜
                    d.ellipse([ex-er, ey-er, ex+er, ey+er],
                              fill=white_light, outline=outline, width=sc(1))
                    # 棕色虹膜
                    ir = sc(10)
                    d.ellipse([ex-ir, ey-ir, ex+ir, ey+ir], fill=eye_brown)
                    # 黑色瞳孔
                    pr = sc(6)
                    if eye_mode == 'excited':
                        pr = sc(9)
                    d.ellipse([ex-pr, ey-pr, ex+pr, ey+pr], fill=black)
                    # 高光
                    d.ellipse([ex+sc(2), ey-sc(8), ex+sc(8), ey-sc(2)], fill=white_light)
                    d.ellipse([ex-sc(7), ey-sc(6), ex-sc(3), ey-sc(2)],
                              fill=(255,255,255,180))

            # ══ 8. 鼻子 + 嘴 ══
            nx, ny = cx, head_cy + sc(16)
            # 椭圆鼻
            d.ellipse([nx - sc(8), ny - sc(5), nx + sc(8), ny + sc(5)],
                      fill=nose_color, outline=outline, width=sc(1))
            if eye_mode == 'excited':
                d.ellipse([nx - sc(12), ny + sc(4), nx + sc(12), ny + sc(16)],
                          fill=(180, 50, 40, 255), outline=outline, width=sc(1))
                d.ellipse([nx - sc(8), ny + sc(6), nx + sc(8), ny + sc(14)],
                          fill=(220, 80, 70, 255))
            else:
                d.line([nx - sc(10), ny + sc(8), nx, ny + sc(6)],
                       fill=mouth_color, width=sc(2))
                d.line([nx, ny + sc(6), nx + sc(10), ny + sc(8)],
                       fill=mouth_color, width=sc(2))

            # ══ 9. 胡须 ══
            for sign in (-1, 1):
                for i, (wy_off, tilt) in enumerate([(0, sign*sc(2)), (sc(8), 0), (sc(16), -sign*sc(1))]):
                    wx0 = nx + sign * sc(10)
                    wx1 = nx + sign * sc(42)
                    wy  = ny + sc(2) + wy_off
                    d.line([wx0, wy, wx1, wy + tilt],
                           fill=(200, 190, 170, 150), width=max(1, sc(1)))

            # ══ 10. 短腿 + 脚掌 ══
            leg_top = body_cy + body_ry - sc(8)
            for sign in (-1, 1):
                lx = cx + sign * sc(22)
                shaded_ellipse(lx, leg_top + sc(12), sc(16), sc(20), fur_gray, fur_light)
                # 脚掌（深色条纹）
                shaded_ellipse(lx, leg_top + sc(30), sc(18), sc(10), white_fur, white_light, outline)
                for px_off in [-sc(6), 0, sc(6)]:
                    d.ellipse([lx+px_off-sc(3), leg_top+sc(22)-sc(3),
                               lx+px_off+sc(3), leg_top+sc(22)+sc(3)],
                              fill=fur_dark)

            return img.resize((size, size), Image.LANCZOS)

        sc_outer = lambda v: max(1, int(v * s))

        raw = {
            'idle':    [make_frame(body_offset_x=ox) for ox in [0, sc_outer(2), 0, -sc_outer(2)]],
            'blink':   [make_frame(eye_mode='blink')],
            'happy':   [make_frame(eye_mode='happy')],
            'excited': [make_frame(eye_mode='excited')],
            'sleepy':  [make_frame(eye_mode='sleepy')],
        }

        frames = {}
        for key, imgs in raw.items():
            frames[key] = [ImageTk.PhotoImage(img) for img in imgs]
        return frames

    def _draw_cat_pillow(self, offset_y):
        """使用预生成 Pillow 帧渲染猫，替代 Canvas 向量绘制。"""
        mood = self._cat_mood
        if self._mood_timer > 0:
            self._mood_timer -= 1
        else:
            mood = 'normal'
            self._cat_mood = 'normal'

        # 眨眼计时
        self._blink_timer += 1
        if self._blink_active:
            self._blink_duration -= 1
            if self._blink_duration <= 0:
                self._blink_active = False
                self._blink_cooldown = random.randint(60, 100)  # 3-5秒@50ms
        else:
            if self._blink_cooldown > 0:
                self._blink_cooldown -= 1
            else:
                self._blink_active = True
                self._blink_duration = 4  # 眨眼持续 4 帧

        # 选择帧
        if self._blink_active or mood == 'sleepy':
            frames = self._cat_frames.get('blink') or self._cat_frames['idle']
            frame = frames[0]
        elif mood == 'happy':
            frames = self._cat_frames.get('happy') or self._cat_frames['idle']
            frame = frames[0]
        elif mood == 'excited':
            frames = self._cat_frames.get('excited') or self._cat_frames['idle']
            frame = frames[0]
        else:
            # idle 4 帧循环（每 6 个 anim_frame 切换一帧）
            idle_idx = (self._anim_frame // 6) % 4
            frame = self._cat_frames['idle'][idle_idx]

        # 渲染到 Canvas（每帧重建，避免 delete('all') 后 id 失效）
        self.canvas.delete('all')
        cx = self.w // 2
        cy = self.h // 2 + offset_y
        self._cat_image_id = self.canvas.create_image(cx, cy, image=frame, anchor='center')
        # 保持引用防止 GC 导致图像消失
        self.canvas._pillow_frame_ref = frame

    def _draw_cat(self, offset_y, scale):
        """每帧重绘小猫。scale 以 1.0 为基准。"""
        self.canvas.delete('all')
        c = self._CAT_PALETTES.get(
            self.settings.get('cat_color', 'orange'),
            self._CAT_PALETTES['orange'])

        # 坐标系：以窗口中心为参考，s 是缩放因子
        s = scale * (self.w / 120)
        ox = self.w / 2
        oy = self.h / 2 + offset_y

        def p(x, y):
            """原型坐标（120×120 画布，中心 60,68）→ 实际坐标"""
            return ox + (x - 60) * s, oy + (y - 68) * s

        t = self._anim_frame / 60.0
        breath = math.sin(2 * math.pi * t * 0.4) * 1.5 * s
        tail_a = math.sin(2 * math.pi * t * 0.6) * 28
        whisker_w = math.sin(2 * math.pi * t * 0.3) * 1.5 * s

        # ── 尾巴 ────────────────────────────────────────
        tx0, ty0 = p(82, 82)
        ctrl_x = ox + (82 + 28 + math.sin(math.radians(tail_a)) * 18 - 60) * s
        ctrl_y = oy + (82 - 30 + math.cos(math.radians(tail_a)) * 10 - 68) * s
        tip_x  = ox + (82 + 12 + math.sin(math.radians(tail_a)) * 32 - 60) * s
        tip_y  = oy + (82 - 52 + math.cos(math.radians(tail_a)) * 8  - 68) * s
        pts = []
        for i in range(11):
            tt = i / 10
            bx = (1-tt)**2*tx0 + 2*(1-tt)*tt*ctrl_x + tt**2*tip_x
            by = (1-tt)**2*ty0 + 2*(1-tt)*tt*ctrl_y + tt**2*tip_y
            pts.extend([bx, by])
        tw = max(2, int(7 * s))
        self.canvas.create_line(pts, fill=c['body'], width=tw,
                                capstyle=tk.ROUND, smooth=True)
        r_tip = max(2, int(5 * s))
        self.canvas.create_oval(tip_x - r_tip, tip_y - r_tip,
                                tip_x + r_tip, tip_y + r_tip,
                                fill=c['belly'], outline='')

        # ── 身体 ────────────────────────────────────────
        bx1, by1 = p(24, 38)
        bx2, by2 = p(96, 98)
        self.canvas.create_oval(bx1, by1 + breath, bx2, by2 + breath,
                                fill=c['body'], outline='')
        px1, py1 = p(44, 54)
        px2, py2 = p(76, 86)
        self.canvas.create_oval(px1, py1 + breath, px2, py2 + breath,
                                fill=c['belly'], outline='')

        # ── 头 ──────────────────────────────────────────
        hcx, hcy = p(60, 34)
        hw = int(26 * s)
        self.canvas.create_oval(hcx - hw, hcy - hw + breath * 0.5,
                                hcx + hw, hcy + hw + breath * 0.5,
                                fill=c['body'], outline='')

        # ── 耳朵 ────────────────────────────────────────
        hb = breath * 0.5
        # 左耳外
        self.canvas.create_polygon(
            *p(38, 16), *p(50, -4), *p(56, 16),
            fill=c['body'], outline='')
        self.canvas.create_polygon(
            *(x + (0 if i % 2 == 0 else hb) for i, x in enumerate(
                [*p(40, 14), *p(49, -1), *p(53, 14)])),
            fill=c['ear_in'], outline='')
        # 右耳外
        self.canvas.create_polygon(
            *p(82, 16), *p(70, -4), *p(64, 16),
            fill=c['body'], outline='')
        self.canvas.create_polygon(
            *(x + (0 if i % 2 == 0 else hb) for i, x in enumerate(
                [*p(80, 14), *p(71, -1), *p(67, 14)])),
            fill=c['ear_in'], outline='')

        # ── 头顶条纹 ────────────────────────────────────
        for dx in [-8, 0, 8]:
            x1, y1 = p(60 + dx, 8)
            x2, y2 = p(62 + dx, 18)
            self.canvas.create_line(x1, y1 + hb, x2, y2 + hb,
                                    fill=c['stripe'],
                                    width=max(1, int(2 * s)),
                                    capstyle=tk.ROUND)

        # ── 眼睛 ────────────────────────────────────────
        self._blink_timer += 1
        blinking = (self._blink_timer % self._BLINK_INTERVAL) < 4
        mood = self._cat_mood
        if self._mood_timer > 0:
            self._mood_timer -= 1
        else:
            mood = 'normal'
            self._cat_mood = 'normal'

        ex_l, ey_l = p(50, 34)
        ex_r, ey_r = p(70, 34)
        ey_l += hb; ey_r += hb
        er = max(3, int(7 * s))

        if blinking or mood == 'sleepy':
            # 眯眼弧线
            for ex, ey in [(ex_l, ey_l), (ex_r, ey_r)]:
                self.canvas.create_arc(ex - er, ey - er * 0.4,
                                       ex + er, ey + er * 0.8,
                                       start=0, extent=180,
                                       style=tk.ARC,
                                       outline=c['eye'],
                                       width=max(1, int(2 * s)))
        elif mood == 'happy':
            # 弯弯眼（上弧）
            for ex, ey in [(ex_l, ey_l), (ex_r, ey_r)]:
                self.canvas.create_arc(ex - er, ey - er,
                                       ex + er, ey + er * 0.5,
                                       start=0, extent=-180,
                                       style=tk.ARC,
                                       outline=c['eye'],
                                       width=max(1, int(2 * s)))
        elif mood == 'excited':
            # 大圆眼
            er2 = int(er * 1.3)
            for ex, ey in [(ex_l, ey_l), (ex_r, ey_r)]:
                self.canvas.create_oval(ex - er2, ey - er2, ex + er2, ey + er2,
                                        fill='white', outline='')
                self.canvas.create_oval(ex - int(er2 * 0.6), ey - int(er2 * 0.7),
                                        ex + int(er2 * 0.6), ey + int(er2 * 0.5),
                                        fill=c['eye'], outline='')
                self.canvas.create_oval(ex - int(er2 * 0.3), ey - int(er2 * 0.4),
                                        ex + int(er2 * 0.3), ey + int(er2 * 0.2),
                                        fill='#1a1a2e', outline='')
                self.canvas.create_oval(ex + int(er2 * 0.1), ey - int(er2 * 0.3),
                                        ex + int(er2 * 0.4), ey,
                                        fill='white', outline='')
        else:
            # 普通圆眼
            for ex, ey in [(ex_l, ey_l), (ex_r, ey_r)]:
                self.canvas.create_oval(ex - er, ey - er, ex + er, ey + er,
                                        fill='white', outline='')
                ep = int(er * 0.6)
                self.canvas.create_oval(ex - ep, ey - ep, ex + ep, ey + ep,
                                        fill=c['eye'], outline='')
                ep2 = int(er * 0.3)
                self.canvas.create_oval(ex - ep2, ey - ep2, ex + ep2, ey + ep2,
                                        fill='#1a1a2e', outline='')
                self.canvas.create_oval(ex + int(er * 0.1), ey - int(er * 0.3),
                                        ex + int(er * 0.4), ey,
                                        fill='white', outline='')

        # ── 鼻子 + 嘴 ───────────────────────────────────
        nx, ny = p(60, 42)
        ny += hb
        ns = max(2, int(3 * s))
        self.canvas.create_polygon(nx - ns, ny, nx + ns, ny, nx, ny + ns * 1.2,
                                   fill=c['nose'], outline='')
        self.canvas.create_line(nx, ny + ns * 1.2,
                                nx - int(6 * s), ny + int(5 * s) + ns * 1.2,
                                fill=c['mouth'], width=max(1, int(s)))
        self.canvas.create_line(nx, ny + ns * 1.2,
                                nx + int(6 * s), ny + int(5 * s) + ns * 1.2,
                                fill=c['mouth'], width=max(1, int(s)))

        # ── 胡须 ────────────────────────────────────────
        for sign in (-1, 1):
            for i, (wdx, wdy) in enumerate([(-22, -3), (-20, 2), (-18, 7)]):
                x1, y1 = p(60 + sign * 8, 44 + wdy * 0.3)
                x2 = x1 + sign * abs(wdx) * s
                y2 = y1 + wdy * s * 0.4 + (whisker_w if i == 1 else 0)
                y1 += hb; y2 += hb
                self.canvas.create_line(x1, y1, x2, y2,
                                        fill=c['whisker'],
                                        width=max(1, int(s)))

        # ── 爪子 ────────────────────────────────────────
        for pdx in (-14, 14):
            px1, py1 = p(60 + pdx - 8, 96)
            px2, py2 = p(60 + pdx + 8, 108)
            self.canvas.create_oval(px1, py1 + breath, px2, py2 + breath,
                                    fill=c['body'], outline='')

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

        self._draw_emoji(offset_y)
        self._anim_frame += 1
        self.root.after(self.ANIM_INTERVAL, self._animate)

    def _draw_emoji(self, offset_y):
        self.canvas.delete('all')
        emoji = self.settings.get('pet_emoji', '🐱')
        font_size = max(20, int(self.w * 0.6))
        cx = self.w // 2
        cy = self.h // 2 + offset_y
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