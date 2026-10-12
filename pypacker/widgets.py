# -*- coding: utf-8 -*-
"""自定义控件：首页功能卡片"""
import tkinter as tk

import customtkinter as ctk

from .constants import BORDER, CARD, MUTED, TEXT
from .constants import F
from .icon import draw_feature_icon
from .utils import lighten


class FeatureCard(ctk.CTkFrame):
    """首页功能卡片：图标 + 标题 + 描述
    悬停时只改边框颜色，不改尺寸，避免抖动。
    """

    def __init__(self, master, icon_name, title, desc, accent, command,
                 height=180):
        super().__init__(master, corner_radius=14, fg_color=CARD,
                         border_width=1, border_color=BORDER,
                         height=height)
        self.grid_propagate(False)
        self.pack_propagate(False)

        self._accent = accent
        self._command = command
        self._hover = False

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=18)

        # 图标底板
        icon_wrap = tk.Canvas(content, width=54, height=54, bg=CARD,
                              highlightthickness=0, bd=0)
        icon_wrap.pack(anchor="w")
        self._draw_round_rect(icon_wrap, 0, 0, 54, 54, 16,
                              fill=lighten(accent, 0.88))
        draw_feature_icon(icon_wrap, 27, 27, 30, icon_name, accent)

        self.icon_wrap = icon_wrap

        self.title_lbl = ctk.CTkLabel(content, text=title, font=F.h2,
                                      text_color=TEXT, anchor="w")
        self.title_lbl.pack(anchor="w", pady=(14, 4))

        self.desc_lbl = ctk.CTkLabel(content, text=desc, font=F.small,
                                     text_color=MUTED, anchor="w",
                                     justify="left", wraplength=200)
        self.desc_lbl.pack(anchor="w", fill="x")

        self._content = content

        # 所有子控件都参与 hover/click（内部做幂等判断，不会抖）
        for w in (self, content, icon_wrap, self.title_lbl, self.desc_lbl):
            w.bind("<Enter>", self._on_enter, add="+")
            w.bind("<Leave>", self._on_leave, add="+")
            w.bind("<Button-1>", self._on_click, add="+")

        self.bind("<Configure>", self._on_resize)

    @staticmethod
    def _draw_round_rect(canvas, x1, y1, x2, y2, r, **kw):
        r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
        pts = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]
        return canvas.create_polygon(pts, smooth=True, **kw)

    def _on_resize(self, e):
        try:
            self.desc_lbl.configure(wraplength=max(80, e.width - 56))
        except Exception:
            pass

    def _on_enter(self, _e=None):
        if self._hover:
            return
        self._hover = True
        self.configure(border_color=self._accent)

    def _on_leave(self, _e=None):
        if not self._hover:
            return
        self._hover = False
        self.configure(border_color=BORDER)

    def _on_click(self, _e=None):
        if self._command:
            self._command()