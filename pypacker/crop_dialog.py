# -*- coding: utf-8 -*-
"""可视化裁剪对话框"""
import tkinter as tk

import customtkinter as ctk

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

from .constants import (ACCENT, ACCENT_HOV, BG, BORDER, MUTED, TEXT)
from .constants import F
from .icon import RESAMPLE, HAS_PIL


class CropDialog(ctk.CTkToplevel):
    """拖拽鼠标选择裁剪区域（按住 Shift 锁定正方形）"""

    def __init__(self, master, image_path, initial=None):
        super().__init__(master, fg_color=BG)
        self.title("裁剪图片 —— 拖动鼠标选择区域，按住 Shift 锁定正方形")
        self.transient(master)
        self.grab_set()
        self.resizable(False, False)

        self.result = None
        self.start = None
        self.box = None

        self.src = Image.open(image_path).convert("RGBA")
        w, h = self.src.size

        max_w, max_h = 660, 460
        self.scale = min(1.0, max_w / max(w, 1), max_h / max(h, 1))
        self.dw = max(1, int(w * self.scale))
        self.dh = max(1, int(h * self.scale))

        disp = self.src.resize((self.dw, self.dh), RESAMPLE)

        # 棋盘格底纹，方便看透明区域
        board = Image.new("RGBA", (self.dw, self.dh), (255, 255, 255, 255))
        cell = 10
        for y in range(0, self.dh, cell):
            for x in range(0, self.dw, cell):
                if ((x // cell) + (y // cell)) % 2:
                    board.paste((228, 232, 238, 255),
                                (x, y, min(x + cell, self.dw),
                                 min(y + cell, self.dh)))
        board.alpha_composite(disp)
        self._photo = ImageTk.PhotoImage(board)

        wrap = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        wrap.pack(fill="both", expand=True, padx=18, pady=16)

        stage = ctk.CTkFrame(wrap, fg_color=BORDER, corner_radius=8)
        stage.pack()
        self.canvas = tk.Canvas(stage, width=self.dw, height=self.dh,
                                highlightthickness=0, bd=0,
                                bg="#ffffff", cursor="crosshair")
        self.canvas.pack(padx=1, pady=1)
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
        self.sel_id = self.canvas.create_rectangle(
            0, 0, 0, 0, outline=ACCENT, width=2, dash=(6, 4),
            state="hidden")

        self.lbl = ctk.CTkLabel(wrap, text="未选择区域（默认使用整张图片）",
                                font=F.small, text_color=MUTED)
        self.lbl.pack(pady=(12, 10))

        btns = ctk.CTkFrame(wrap, fg_color=BG, corner_radius=0)
        btns.pack(fill="x")
        ctk.CTkButton(btns, text="全选", width=70, height=34, font=F.body,
                      fg_color="transparent", border_width=1,
                      border_color=BORDER, text_color=TEXT,
                      hover_color="#f3f6fb",
                      command=self._select_all).pack(side="left")
        ctk.CTkButton(btns, text="清除", width=70, height=34, font=F.body,
                      fg_color="transparent", border_width=1,
                      border_color=BORDER, text_color=TEXT,
                      hover_color="#f3f6fb",
                      command=self._clear).pack(side="left", padx=8)
        ctk.CTkButton(btns, text="确定", width=80, height=34, font=F.body_b,
                      fg_color=ACCENT, hover_color=ACCENT_HOV,
                      command=self._ok).pack(side="right")
        ctk.CTkButton(btns, text="取消", width=80, height=34, font=F.body,
                      fg_color="#eef1f7", text_color=TEXT,
                      hover_color="#e2e8f3",
                      command=self.destroy).pack(side="right", padx=8)

        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        if initial:
            l, t, r, b = initial
            self.box = (l * self.scale, t * self.scale,
                        r * self.scale, b * self.scale)
            self._draw()

        self.update_idletasks()
        px, py = master.winfo_rootx(), master.winfo_rooty()
        pw, ph = master.winfo_width(), master.winfo_height()
        x = px + (pw - self.winfo_width()) // 2
        y = py + (ph - self.winfo_height()) // 2
        self.geometry("+%d+%d" % (max(0, x), max(0, y)))

    def _clamp(self, x, y):
        return max(0, min(x, self.dw)), max(0, min(y, self.dh))

    def _on_press(self, e):
        x, y = self._clamp(e.x, e.y)
        self.start = (x, y)
        self.box = (x, y, x, y)
        self._draw()

    def _on_drag(self, e):
        if not self.start:
            return
        x0, y0 = self.start
        x1, y1 = e.x, e.y
        if e.state & 0x0001:                       # Shift 锁定正方形
            sz = min(abs(x1 - x0), abs(y1 - y0))
            x1 = x0 + (sz if x1 >= x0 else -sz)
            y1 = y0 + (sz if y1 >= y0 else -sz)
        x1, y1 = self._clamp(x1, y1)
        self.box = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        self._draw()

    def _on_release(self, _e):
        self.start = None
        if self.box and (self.box[2] - self.box[0] < 3
                         or self.box[3] - self.box[1] < 3):
            self._clear()

    def _draw(self):
        if not self.box:
            self.canvas.itemconfigure(self.sel_id, state="hidden")
            return
        self.canvas.coords(self.sel_id, *self.box)
        self.canvas.itemconfigure(self.sel_id, state="normal")
        s = self.scale
        l, t, r, b = (int(v / s) for v in self.box)
        self.lbl.configure(
            text="裁剪区域：x=%d  y=%d  宽=%d  高=%d（原图像素）"
                 % (l, t, r - l, b - t),
            text_color=ACCENT)

    def _select_all(self):
        self.box = (0, 0, self.dw, self.dh)
        self._draw()

    def _clear(self):
        self.box = None
        self.canvas.itemconfigure(self.sel_id, state="hidden")
        self.lbl.configure(text="未选择区域（默认使用整张图片）",
                           text_color=MUTED)

    def _ok(self):
        if self.box:
            s = self.scale
            self.result = tuple(int(v / s) for v in self.box)
        else:
            self.result = None
        self.destroy()