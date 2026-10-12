# -*- coding: utf-8 -*-
"""主应用：UI 装配 + 事件处理"""
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox

import customtkinter as ctk

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

from .builder import build_command, run_build
from .config_io import load_config as load_cfg_file
from .config_io import save_config as save_cfg_file
from .constants import (ACCENT, ACCENT_HOV, BG, BORDER, CARD,
                        CODE_BG, CODE_FG, CONFIG_PATH, DANGER, MUTED,
                        PAGE_META, PAGE_ORDER, SUCCESS, TEXT, TEXT_SUB)
from .constants import F
from .crop_dialog import CropDialog
from .icon import HAS_PIL, prepare_icon_image
from .python_env import probe_pyinstaller, pip_install_pyinstaller
from .python_env import resolve_python
from .utils import hex_to_rgba, open_folder
from .widgets import FeatureCard


ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")


class PyPackerApp(ctk.CTk):

    def __init__(self):
        super().__init__(fg_color=BG)
        F.init()

        self.title("PyPacker · Python 打包工作台")
        self._setup_window()

        self._init_vars()
        self._build_ui()
        self._bind_traces()

        self._load_config(CONFIG_PATH, silent=True)
        self.update_preview()
        self.show_home()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_log)
        self.after(200, self._dump_env_async)

    # ------------------------------------------------------------------ #
    def _setup_window(self):
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w = max(1020, min(1280, int(sw * 0.78)))
        h = max(720, min(880, int(sh * 0.88)))
        x = (sw - w) // 2
        y = max(0, (sh - h) // 2 - 20)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(980, 660)

    def _init_vars(self):
        self.var_script = tk.StringVar()
        self.var_name = tk.StringVar()
        self.var_dist = tk.StringVar()
        self.var_mode = tk.StringVar(value="onefile")
        self.var_console = tk.BooleanVar(value=False)
        # --clean 默认关闭：让后续打包复用缓存，速度提升明显
        self.var_clean = tk.BooleanVar(value=False)
        self.var_noconfirm = tk.BooleanVar(value=True)

        self.var_icon_src = tk.StringVar()
        self.var_icon_out = tk.StringVar()
        self.var_icon_mode = tk.StringVar(value="cover")
        self.var_icon_bg = tk.StringVar(value="#FFFFFF")
        self.var_icon_bg_trans = tk.BooleanVar(value=True)
        self.var_icon_pad = tk.IntVar(value=0)
        # 新增：是否把图标嵌入目标程序
        self.var_embed_icon = tk.BooleanVar(value=True)

        self.var_use_version = tk.BooleanVar(value=True)
        self.ver_vars = {
            "file_version": tk.StringVar(value="1.0.0.0"),
            "product_version": tk.StringVar(value="1.0.0.0"),
            "company": tk.StringVar(),
            "product_name": tk.StringVar(),
            "description": tk.StringVar(),
            "copyright": tk.StringVar(),
            "internal_name": tk.StringVar(),
            "original_filename": tk.StringVar(),
        }

        self.var_upx = tk.StringVar()
        self.var_no_upx = tk.BooleanVar(value=False)
        self.var_extra = tk.StringVar()

        self.var_status = tk.StringVar(value="就绪")

        self.log_queue = queue.Queue()
        self.proc = None
        self.building = False
        self.icon_crop = None
        self._preview_photo = None
        self._src_photo = None

        # 进度
        self._progress_val = 0.0

        # 日志缓冲（批量刷新，避免每行都刷 UI）
        self._log_buf = []
        self._log_flush_job = None

    # ------------------------------------------------------------------ #
    #  UI 装配
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        self.header = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0,
                                   height=72)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)

        self.header_home = ctk.CTkFrame(self.header, fg_color=CARD,
                                        corner_radius=0)
        self.header_detail = ctk.CTkFrame(self.header, fg_color=CARD,
                                          corner_radius=0)
        self._build_header_home(self.header_home)
        self._build_header_detail(self.header_detail)

        ctk.CTkFrame(self, fg_color=BORDER, height=1,
                     corner_radius=0).pack(fill="x")

        self.content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.content.pack(fill="both", expand=True)
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.home_page = ctk.CTkFrame(self.content, fg_color=BG,
                                      corner_radius=0)
        self.home_page.grid(row=0, column=0, sticky="nsew")

        self.detail_pages = {}
        for key in PAGE_ORDER:
            page = ctk.CTkFrame(self.content, fg_color=BG, corner_radius=0)
            page.grid(row=0, column=0, sticky="nsew")
            self.detail_pages[key] = page

        self._build_actionbar()

        self._build_home_page(self.home_page)
        self._build_basic_page(self.detail_pages["basic"])
        self._build_icon_page(self.detail_pages["icon"])
        self._build_version_page(self.detail_pages["version"])
        self._build_advanced_page(self.detail_pages["advanced"])
        self._build_log_page(self.detail_pages["log"])

    def _build_header_home(self, parent):
        inner = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=0)
        inner.pack(fill="both", expand=True, padx=24, pady=12)

        brand = ctk.CTkFrame(inner, fg_color=CARD, corner_radius=0)
        brand.pack(side="left")

        logo = tk.Canvas(brand, width=40, height=40, bg=CARD,
                         highlightthickness=0, bd=0)
        logo.pack(side="left")
        pts = [13, 0, 27, 0, 40, 0, 40, 13, 40, 27, 40, 40,
               27, 40, 13, 40, 0, 40, 0, 27, 0, 13, 0, 0]
        logo.create_polygon(pts, smooth=True, fill=ACCENT, outline=ACCENT)
        logo.create_text(20, 20, text="Py", fill="#ffffff",
                         font=ctk.CTkFont(family=F.family, size=15,
                                          weight="bold"))

        btxt = ctk.CTkFrame(brand, fg_color=CARD, corner_radius=0)
        btxt.pack(side="left", padx=(12, 0))
        ctk.CTkLabel(btxt, text="PyPacker",
                     font=ctk.CTkFont(family=F.family, size=17,
                                      weight="bold"),
                     text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(btxt, text="打包工作台", font=F.tiny,
                     text_color=MUTED).pack(anchor="w")

        right = ctk.CTkFrame(inner, fg_color=CARD, corner_radius=0)
        right.pack(side="right")
        ctk.CTkButton(right, text="加载配置", width=96, height=38,
                      font=F.body, fg_color="transparent", border_width=1,
                      border_color=BORDER, text_color=ACCENT,
                      hover_color="#eaf0ff",
                      command=self._load_config_dialog)\
            .pack(side="right", padx=(8, 0))
        ctk.CTkButton(right, text="保存配置", width=96, height=38,
                      font=F.body, fg_color="transparent", border_width=1,
                      border_color=BORDER, text_color=TEXT,
                      hover_color="#f3f6fb",
                      command=self._save_config_dialog).pack(side="right")

    def _build_header_detail(self, parent):
        inner = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=0)
        inner.pack(fill="both", expand=True, padx=24, pady=12)

        ctk.CTkButton(inner, text="←  返回", width=96, height=38,
                      font=F.body, fg_color="transparent",
                      text_color=ACCENT, hover_color="#eaf0ff",
                      command=self.show_home).pack(side="left")

        self.detail_title = ctk.CTkLabel(inner, text="", font=F.h2,
                                         text_color=TEXT, anchor="w")
        self.detail_title.pack(side="left", padx=(20, 0))

        self.detail_sub = ctk.CTkLabel(inner, text="", font=F.small,
                                       text_color=MUTED, anchor="w")
        self.detail_sub.pack(side="left", padx=(14, 0))

    def _build_actionbar(self):
        bar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=68)
        bar.pack(side="bottom", fill="x")
        bar.pack_propagate(False)

        ctk.CTkFrame(bar, fg_color=BORDER, height=1,
                     corner_radius=0).pack(fill="x", side="top")

        inner = ctk.CTkFrame(bar, fg_color=CARD, corner_radius=0)
        inner.pack(fill="both", expand=True, padx=24, pady=12)

        left = ctk.CTkFrame(inner, fg_color=CARD, corner_radius=0)
        left.pack(side="left")

        self.dot = tk.Canvas(left, width=14, height=14, bg=CARD,
                             highlightthickness=0, bd=0)
        self.dot.pack(side="left", pady=1)
        self._dot_id = self.dot.create_oval(3, 3, 11, 11, fill=MUTED,
                                            outline="")

        ctk.CTkLabel(left, textvariable=self.var_status, font=F.small,
                     text_color=TEXT_SUB).pack(side="left", padx=(8, 14))

        self.pbar = ctk.CTkProgressBar(left, width=160, height=6,
                                       progress_color=ACCENT,
                                       fg_color="#e9edf4", corner_radius=3)
        self.pbar.set(0)
        self.pbar.pack(side="left", pady=2)

        right = ctk.CTkFrame(inner, fg_color=CARD, corner_radius=0)
        right.pack(side="right")

        ctk.CTkButton(right, text="打开输出目录", width=118, height=40,
                      font=F.body, fg_color="transparent",
                      text_color=ACCENT, hover_color="#eaf0ff",
                      command=self.open_dist).pack(side="left", padx=(0, 10))

        self.btn_stop = ctk.CTkButton(right, text="停止", width=84, height=40,
                                      font=F.body_b, fg_color="#eef1f7",
                                      text_color=TEXT, hover_color="#e2e8f3",
                                      state="disabled",
                                      command=self.stop_build)
        self.btn_stop.pack(side="left", padx=(0, 10))

        self.btn_build = ctk.CTkButton(right, text="开始打包", width=124,
                                       height=40, font=F.body_b,
                                       fg_color=ACCENT,
                                       hover_color=ACCENT_HOV,
                                       command=self.start_build)
        self.btn_build.pack(side="left")

    # ------------------------------------------------------------------ #
    #  通用辅助
    # ------------------------------------------------------------------ #
    def _card(self, parent, title=None, desc=None):
        card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=14,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", pady=(0, 16))

        inner = ctk.CTkFrame(card, fg_color=CARD, corner_radius=0)
        inner.pack(fill="both", expand=True, padx=22, pady=18)

        if title:
            ctk.CTkLabel(inner, text=title, font=F.h2, text_color=TEXT,
                         anchor="w").pack(anchor="w")
            if desc:
                ctk.CTkLabel(inner, text=desc, font=F.small,
                             text_color=MUTED, anchor="w",
                             justify="left").pack(anchor="w", pady=(6, 0))

            ctk.CTkFrame(inner, fg_color=BORDER, height=1, corner_radius=0)\
                .pack(fill="x", pady=(14, 8))

        body = ctk.CTkFrame(inner, fg_color=CARD, corner_radius=0)
        body.pack(fill="both", expand=True)
        return card, body

    def _form_row(self, parent, label, widget_factory, hint=None,
                  label_w=100):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=7)
        row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(row, text=label, font=F.body, text_color=TEXT_SUB,
                     anchor="e", width=label_w)\
            .grid(row=0, column=0, sticky="e", padx=(0, 14))

        widget = widget_factory(row)
        widget.grid(row=0, column=1, sticky="ew")

        if hint:
            ctk.CTkLabel(row, text=hint, font=F.small, text_color=MUTED,
                         anchor="w")\
                .grid(row=0, column=2, sticky="w", padx=(12, 0))

        return row

    def _input_with_button(self, var, btn_text, command,
                           btn_w=76, height=40):
        def make(parent):
            box = ctk.CTkFrame(parent, fg_color="transparent")
            box.grid_columnconfigure(0, weight=1)

            entry = ctk.CTkEntry(box, textvariable=var, height=height,
                                 font=F.body, fg_color="#ffffff",
                                 border_color=BORDER, text_color=TEXT,
                                 corner_radius=8)
            entry.grid(row=0, column=0, sticky="ew")

            btn = ctk.CTkButton(box, text=btn_text, width=btn_w,
                                height=height, font=F.body,
                                fg_color="#eef1f7", text_color=TEXT,
                                hover_color="#e2e8f3",
                                corner_radius=8, command=command)
            btn.grid(row=0, column=1, padx=(10, 0))
            return box
        return make

    def _plain_entry(self, var, height=40):
        def make(parent):
            return ctk.CTkEntry(parent, textvariable=var, height=height,
                                font=F.body, fg_color="#ffffff",
                                border_color=BORDER, text_color=TEXT,
                                corner_radius=8)
        return make

    # ------------------------------------------------------------------ #
    #  首页
    # ------------------------------------------------------------------ #
    def _build_home_page(self, page):
        scroll = ctk.CTkScrollableFrame(page, fg_color=BG, corner_radius=0)
        scroll.pack(fill="both", expand=True)

        welcome = ctk.CTkFrame(scroll, fg_color=BG, corner_radius=0)
        welcome.pack(fill="x", padx=24, pady=(28, 20))

        ctk.CTkLabel(welcome, text="欢迎使用 PyPacker", font=F.display,
                     text_color=TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(welcome,
                     text="从下方选择一个模块开始配置，完成后点击右下角“开始打包”。",
                     font=F.body, text_color=MUTED, anchor="w")\
            .pack(anchor="w", pady=(8, 0))

        grid = ctk.CTkFrame(scroll, fg_color=BG, corner_radius=0)
        grid.pack(fill="x", padx=24, pady=(0, 24))

        cols = 3
        for c in range(cols):
            grid.grid_columnconfigure(c, weight=1, uniform="card")
        grid.grid_rowconfigure(0, weight=1, minsize=180)
        grid.grid_rowconfigure(1, weight=1, minsize=180)

        for i, key in enumerate(PAGE_ORDER):
            title, desc, accent, icon = PAGE_META[key]
            card = FeatureCard(grid, icon, title, desc, accent,
                               command=lambda k=key: self.show_page(k),
                               height=180)
            r, c = divmod(i, cols)
            padx_l = 0 if c == 0 else 8
            padx_r = 0 if c == cols - 1 else 8
            card.grid(row=r, column=c, sticky="nsew",
                      padx=(padx_l, padx_r), pady=(0, 16))

    def show_home(self):
        self.header_detail.pack_forget()
        self.header_home.pack(fill="x")
        self.home_page.tkraise()

    def show_page(self, key):
        title, sub, _, _ = PAGE_META[key]
        self.detail_title.configure(text=title)
        self.detail_sub.configure(text=sub)
        self.header_home.pack_forget()
        self.header_detail.pack(fill="x")
        self.detail_pages[key].tkraise()

    # ------------------------------------------------------------------ #
    #  基本设置页
    # ------------------------------------------------------------------ #
    def _build_basic_page(self, page):
        scroll = ctk.CTkScrollableFrame(page, fg_color=BG, corner_radius=0)
        scroll.pack(fill="both", expand=True)

        wrap = ctk.CTkFrame(scroll, fg_color=BG, corner_radius=0)
        wrap.pack(fill="x", padx=24, pady=24)

        _, body = self._card(
            wrap, "项目",
            "选择要打包的 Python 入口脚本，并指定程序名称与输出位置")

        self._form_row(body, "入口脚本",
                       self._input_with_button(self.var_script, "浏览",
                                               self.pick_script),
                       hint=".py 文件")
        self._form_row(body, "程序名称",
                       self._plain_entry(self.var_name),
                       hint="留空则使用脚本文件名")
        self._form_row(body, "输出目录",
                       self._input_with_button(self.var_dist, "选择",
                                               self.pick_dist),
                       hint="默认脚本旁 dist")

        _, mb = self._card(wrap, "打包模式", "决定最终产物的组织形式")

        for value, label, note in (
            ("onefile", "单文件  --onefile",
             "只生成一个 exe，便于分发；首次启动稍慢"),
            ("onedir", "文件夹  --onedir",
             "生成一个目录，启动速度快，推荐"),
        ):
            box = ctk.CTkFrame(mb, fg_color="#f8fafc",
                               border_width=1, border_color=BORDER,
                               corner_radius=10)
            box.pack(fill="x", pady=(0, 10))

            ctk.CTkRadioButton(box, text=label, variable=self.var_mode,
                               value=value, font=F.body, text_color=TEXT,
                               fg_color=ACCENT, hover_color=ACCENT_HOV,
                               border_color="#c8d0dd")\
                .pack(anchor="w", padx=16, pady=(12, 4))

            ctk.CTkLabel(box, text=note, font=F.small, text_color=MUTED,
                         anchor="w").pack(anchor="w", padx=44, pady=(0, 12))

        _, ob = self._card(wrap, "构建选项", "常规打包行为开关")

        for text, var in (
            ("显示控制台窗口（调试用；GUI 程序请取消勾选）", self.var_console),
            ("打包前清理缓存  --clean（会清空缓存，导致下次打包变慢）",
             self.var_clean),
            ("覆盖输出目录时不询问  --noconfirm", self.var_noconfirm),
        ):
            ctk.CTkCheckBox(ob, text=text, variable=var, font=F.body,
                            text_color=TEXT, fg_color=ACCENT,
                            hover_color=ACCENT_HOV, border_color="#c8d0dd",
                            corner_radius=6)\
                .pack(anchor="w", pady=6)

        ctk.CTkLabel(ob,
                     text="提示：关闭 --clean 可让后续打包复用缓存，速度提升明显。",
                     font=F.small, text_color=MUTED, anchor="w")\
            .pack(anchor="w", pady=(8, 0))

    # ------------------------------------------------------------------ #
    #  图标页
    # ------------------------------------------------------------------ #
    def _build_icon_page(self, page):
        scroll = ctk.CTkScrollableFrame(page, fg_color=BG, corner_radius=0)
        scroll.pack(fill="both", expand=True)

        wrap = ctk.CTkFrame(scroll, fg_color=BG, corner_radius=0)
        wrap.pack(fill="x", padx=24, pady=24)

        _, src_body = self._card(
            wrap, "图标源文件",
            "支持 PNG / JPG / BMP / WEBP 等常见格式")

        self._form_row(src_body, "源图片",
                       self._input_with_button(self.var_icon_src, "选择",
                                               self.pick_icon_src),
                       hint="建议正方形")
        self._form_row(src_body, "输出 ico",
                       self._input_with_button(self.var_icon_out, "另存",
                                               self.pick_icon_out),
                       hint="留空自动生成")

        _, ob = self._card(wrap, "生成选项", "控制图片到图标的转换方式")

        # ---- 缩放方式 ----
        mode_row = ctk.CTkFrame(ob, fg_color="transparent")
        mode_row.pack(fill="x", pady=7)
        mode_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(mode_row, text="缩放方式", font=F.body,
                     text_color=TEXT_SUB, anchor="e", width=100)\
            .grid(row=0, column=0, sticky="e", padx=(0, 14))
        self._mode_map = {
            "cover（居中裁剪铺满）": "cover",
            "contain（完整显示 + 留白）": "contain",
            "stretch（拉伸填满）": "stretch",
        }
        self.cmb_mode = ctk.CTkOptionMenu(
            mode_row, values=list(self._mode_map.keys()),
            font=F.body, dropdown_font=F.body,
            fg_color="#ffffff", text_color=TEXT,
            button_color="#eef1f7", button_hover_color="#e2e8f3",
            dropdown_fg_color="#ffffff", dropdown_text_color=TEXT,
            corner_radius=8, height=40,
            command=lambda v: self.update_preview())
        self.cmb_mode.set("cover（居中裁剪铺满）")
        self.cmb_mode.grid(row=0, column=1, sticky="ew")

        # ---- 内边距 ----
        pad_row = ctk.CTkFrame(ob, fg_color="transparent")
        pad_row.pack(fill="x", pady=7)
        pad_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(pad_row, text="内边距", font=F.body,
                     text_color=TEXT_SUB, anchor="e", width=100)\
            .grid(row=0, column=0, sticky="e", padx=(0, 14))
        pad_box = ctk.CTkFrame(pad_row, fg_color="transparent")
        pad_box.grid(row=0, column=1, sticky="w")
        self.entry_pad = ctk.CTkEntry(pad_box, width=88, height=40,
                                      textvariable=self.var_icon_pad,
                                      font=F.body, fg_color="#ffffff",
                                      border_color=BORDER, text_color=TEXT,
                                      corner_radius=8)
        self.entry_pad.pack(side="left")
        self.entry_pad.bind("<KeyRelease>",
                            lambda e: self.update_preview())
        ctk.CTkLabel(pad_box, text="像素（0 ~ 100）", font=F.small,
                     text_color=MUTED).pack(side="left", padx=10)

        # ---- 背景色 ----
        bg_row = ctk.CTkFrame(ob, fg_color="transparent")
        bg_row.pack(fill="x", pady=7)
        bg_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(bg_row, text="背景色", font=F.body,
                     text_color=TEXT_SUB, anchor="e", width=100)\
            .grid(row=0, column=0, sticky="e", padx=(0, 14))
        bg_box = ctk.CTkFrame(bg_row, fg_color="transparent")
        bg_box.grid(row=0, column=1, sticky="w")

        self.color_chip = tk.Canvas(bg_box, width=40, height=30,
                                    highlightthickness=1,
                                    highlightbackground=BORDER,
                                    bg=self.var_icon_bg.get(),
                                    cursor="hand2", bd=0)
        self.color_chip.pack(side="left")
        self.color_chip.bind("<Button-1>", lambda e: self.pick_bg_color())

        ctk.CTkCheckBox(bg_box, text="透明",
                        variable=self.var_icon_bg_trans, font=F.body,
                        text_color=TEXT, fg_color=ACCENT,
                        hover_color=ACCENT_HOV, border_color="#c8d0dd",
                        corner_radius=6,
                        command=self.update_preview)\
            .pack(side="left", padx=12)
        ctk.CTkLabel(bg_box, text="（仅“完整显示”模式生效）",
                     font=F.small, text_color=MUTED).pack(side="left")

        # ---- 裁剪区域 ----
        crop_row = ctk.CTkFrame(ob, fg_color="transparent")
        crop_row.pack(fill="x", pady=7)
        crop_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(crop_row, text="裁剪区域", font=F.body,
                     text_color=TEXT_SUB, anchor="e", width=100)\
            .grid(row=0, column=0, sticky="e", padx=(0, 14))
        crop_box = ctk.CTkFrame(crop_row, fg_color="transparent")
        crop_box.grid(row=0, column=1, sticky="w")
        ctk.CTkButton(crop_box, text="手动裁剪", width=96, height=36,
                      font=F.body, fg_color="transparent", border_width=1,
                      border_color=BORDER, text_color=TEXT,
                      hover_color="#f3f6fb",
                      command=self.open_crop_dialog).pack(side="left")
        ctk.CTkButton(crop_box, text="清除", width=64, height=36,
                      font=F.body, fg_color="transparent",
                      text_color=ACCENT, hover_color="#eaf0ff",
                      command=self.clear_crop).pack(side="left", padx=8)
        self.lbl_crop = ctk.CTkLabel(crop_box, text="未设置", font=F.small,
                                     text_color=MUTED)
        self.lbl_crop.pack(side="left", padx=6)

        # ---- 图标嵌入（新增） ----
        embed_row = ctk.CTkFrame(ob, fg_color="transparent")
        embed_row.pack(fill="x", pady=(12, 0))

        ctk.CTkCheckBox(
            embed_row,
            text="把图标嵌入目标程序（窗口 / 任务栏图标与 exe 一致）",
            variable=self.var_embed_icon,
            font=F.body, text_color=TEXT, fg_color=ACCENT,
            hover_color=ACCENT_HOV, border_color="#c8d0dd",
            corner_radius=6
        ).pack(anchor="w")

        ctk.CTkLabel(
            embed_row,
            text="勾选后，打包时会把 ico 转成 base64 注入目标程序，\n"
                 "运行时自动为 tkinter / Qt / wxPython 等常见 GUI 框架设置窗口图标。",
            font=F.small, text_color=MUTED, anchor="w",
            justify="left", wraplength=560
        ).pack(anchor="w", padx=(32, 0), pady=(4, 0))

        # ---- 预览 ----
        _, pb = self._card(wrap, "预览", "左侧为原图，右侧为 256px 图标效果")

        pv_row = ctk.CTkFrame(pb, fg_color="transparent")
        pv_row.pack()

        col_a = ctk.CTkFrame(pv_row, fg_color="transparent")
        col_a.pack(side="left", padx=(0, 20))
        ctk.CTkLabel(col_a, text="原图", font=F.small,
                     text_color=MUTED).pack(pady=(0, 8))
        self.canvas_src = tk.Canvas(col_a, width=160, height=160,
                                    bg="#f7f9fc", highlightthickness=1,
                                    highlightbackground=BORDER, bd=0)
        self.canvas_src.pack()

        col_b = ctk.CTkFrame(pv_row, fg_color="transparent")
        col_b.pack(side="left")
        ctk.CTkLabel(col_b, text="图标效果", font=F.small,
                     text_color=MUTED).pack(pady=(0, 8))
        self.canvas_preview = tk.Canvas(col_b, width=160, height=160,
                                        bg="#f7f9fc", highlightthickness=1,
                                        highlightbackground=BORDER, bd=0)
        self.canvas_preview.pack()

        ctk.CTkLabel(pb,
                     text="生成时会自动输出 16 / 24 / 32 / 48 / 64 / 128 / 256 全部尺寸",
                     font=F.small, text_color=MUTED, anchor="w")\
            .pack(anchor="w", pady=(18, 0))

    # ------------------------------------------------------------------ #
    #  版本信息页
    # ------------------------------------------------------------------ #
    def _build_version_page(self, page):
        scroll = ctk.CTkScrollableFrame(page, fg_color=BG, corner_radius=0)
        scroll.pack(fill="both", expand=True)

        wrap = ctk.CTkFrame(scroll, fg_color=BG, corner_radius=0)
        wrap.pack(fill="x", padx=24, pady=24)

        _, body = self._card(
            wrap, "版本资源",
            "这些信息会写入 Windows 可执行文件的属性面板（仅 Windows 生效）")

        ctk.CTkCheckBox(body, text="启用版本信息",
                        variable=self.var_use_version, font=F.body,
                        text_color=TEXT, fg_color=ACCENT,
                        hover_color=ACCENT_HOV, border_color="#c8d0dd",
                        corner_radius=6).pack(anchor="w", pady=(0, 12))

        rows = [
            ("file_version", "文件版本", "格式 1.0.0.0"),
            ("product_version", "产品版本", "格式 1.0.0.0"),
            ("company", "公司名称", "例如 Acme Studio"),
            ("product_name", "产品名称", "例如 My App"),
            ("description", "文件描述", "程序功能简述"),
            ("copyright", "版权信息", "Copyright © 2025"),
            ("internal_name", "内部名称", "内部标识符"),
            ("original_filename", "原始文件名", "MyApp.exe"),
        ]

        for key, label, hint in rows:
            self._form_row(
                body, label,
                (lambda k: lambda p: ctk.CTkEntry(
                    p, textvariable=self.ver_vars[k], height=40,
                    font=F.body, fg_color="#ffffff", border_color=BORDER,
                    text_color=TEXT, corner_radius=8))(key),
                hint=hint)

    # ------------------------------------------------------------------ #
    #  高级页
    # ------------------------------------------------------------------ #
    def _build_advanced_page(self, page):
        scroll = ctk.CTkScrollableFrame(page, fg_color=BG, corner_radius=0)
        scroll.pack(fill="both", expand=True)

        wrap = ctk.CTkFrame(scroll, fg_color=BG, corner_radius=0)
        wrap.pack(fill="x", padx=24, pady=24)

        _, d_body = self._card(
            wrap, "附加数据",
            "每行一条：源路径;目标目录。例：assets;assets  |  config.json;.")
        self.txt_add_data = ctk.CTkTextbox(
            d_body, height=110, fg_color="#f8fafc",
            border_color=BORDER, border_width=1,
            text_color=TEXT, font=F.mono, corner_radius=8)
        self.txt_add_data.pack(fill="x")

        _, h_body = self._card(
            wrap, "隐藏导入  --hidden-import",
            "每行一个模块名，用于 PyInstaller 未能自动发现的依赖")
        self.txt_hidden = ctk.CTkTextbox(
            h_body, height=110, fg_color="#f8fafc",
            border_color=BORDER, border_width=1,
            text_color=TEXT, font=F.mono, corner_radius=8)
        self.txt_hidden.pack(fill="x")

        _, e_body = self._card(
            wrap, "排除模块  --exclude-module",
            "每行一个模块名，可显著减小打包体积")
        self.txt_exclude = ctk.CTkTextbox(
            e_body, height=110, fg_color="#f8fafc",
            border_color=BORDER, border_width=1,
            text_color=TEXT, font=F.mono, corner_radius=8)
        self.txt_exclude.pack(fill="x")

        _, u_body = self._card(wrap, "UPX 压缩",
                               "指定 UPX 可执行文件所在目录以压缩产物")
        self._form_row(u_body, "UPX 目录",
                       self._input_with_button(self.var_upx, "浏览",
                                               self.pick_upx))

        ctk.CTkCheckBox(u_body, text="禁用 UPX  --noupx",
                        variable=self.var_no_upx, font=F.body,
                        text_color=TEXT, fg_color=ACCENT,
                        hover_color=ACCENT_HOV, border_color="#c8d0dd",
                        corner_radius=6).pack(anchor="w", pady=(12, 0))

        _, x_body = self._card(wrap, "额外参数",
                               "会原样追加到 PyInstaller 命令行末尾")
        ctk.CTkEntry(x_body, textvariable=self.var_extra, height=40,
                     font=F.body, fg_color="#ffffff", border_color=BORDER,
                     text_color=TEXT, corner_radius=8).pack(fill="x")
        ctk.CTkLabel(x_body,
                     text='例如：--collect-all pandas --add-binary "ffmpeg.exe;."',
                     font=F.small, text_color=MUTED, anchor="w")\
            .pack(anchor="w", pady=(8, 0))

    # ------------------------------------------------------------------ #
    #  日志页
    # ------------------------------------------------------------------ #
    def _build_log_page(self, page):
        wrap = ctk.CTkFrame(page, fg_color=CODE_BG, corner_radius=0)
        wrap.pack(fill="both", expand=True, padx=24, pady=24)

        self.txt_log = ctk.CTkTextbox(wrap, fg_color=CODE_BG,
                                      text_color=CODE_FG,
                                      font=F.mono, corner_radius=10,
                                      wrap="word", border_width=0)
        self.txt_log.pack(fill="both", expand=True)
        self.txt_log.configure(state="disabled")

    # ------------------------------------------------------------------ #
    #  事件 / 文件选择
    # ------------------------------------------------------------------ #
    def _bind_traces(self):
        for v in (self.var_icon_src, self.var_icon_mode,
                  self.var_icon_bg, self.var_icon_bg_trans):
            v.trace_add("write", lambda *a: self.update_preview())

    def pick_script(self):
        p = filedialog.askopenfilename(
            title="选择 Python 入口脚本",
            filetypes=[("Python 脚本", "*.py"), ("所有文件", "*.*")])
        if not p:
            return
        self.var_script.set(p)
        if not self.var_name.get().strip():
            self.var_name.set(os.path.splitext(os.path.basename(p))[0])
        if not self.var_dist.get().strip():
            self.var_dist.set(os.path.join(os.path.dirname(p), "dist"))
        if not self.ver_vars["original_filename"].get().strip():
            self.ver_vars["original_filename"].set(
                os.path.splitext(os.path.basename(p))[0] + ".exe")

    def pick_dist(self):
        p = filedialog.askdirectory(title="选择输出目录")
        if p:
            self.var_dist.set(p)

    def pick_icon_src(self):
        if not HAS_PIL:
            messagebox.showwarning("缺少依赖",
                                   "需要安装 Pillow 才能处理图片：\n\n"
                                   "pip install pillow")
            return
        p = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[
                ("图片文件",
                 "*.png;*.jpg;*.jpeg;*.bmp;*.webp;*.gif;*.tif;*.tiff;*.ico"),
                ("PNG",     "*.png"),
                ("JPEG",    "*.jpg;*.jpeg"),
                ("BMP",     "*.bmp"),
                ("WebP",    "*.webp"),
                ("GIF",     "*.gif"),
                ("ICO",     "*.ico"),
                ("所有文件", "*.*"),
            ])
        if p:
            self.var_icon_src.set(p)
            self.icon_crop = None
            self.lbl_crop.configure(text="未设置", text_color=MUTED)
            self.update_preview()

    def pick_icon_out(self):
        p = filedialog.asksaveasfilename(
            title="保存 ico 文件", defaultextension=".ico",
            filetypes=[("图标文件", "*.ico"), ("所有文件", "*.*")])
        if p:
            self.var_icon_out.set(p)

    def pick_upx(self):
        p = filedialog.askdirectory(title="选择 UPX 目录")
        if p:
            self.var_upx.set(p)

    def pick_bg_color(self):
        color = colorchooser.askcolor(color=self.var_icon_bg.get(),
                                      title="选择背景色")[1]
        if color:
            self.var_icon_bg.set(color.upper())
            self.color_chip.configure(bg=color)

    # ------------------------------------------------------------------ #
    #  裁剪 / 预览
    # ------------------------------------------------------------------ #
    def open_crop_dialog(self):
        src = self.var_icon_src.get().strip()
        if not src or not os.path.isfile(src):
            messagebox.showwarning("提示", "请先选择一张图片。")
            return
        if not HAS_PIL:
            messagebox.showwarning("缺少依赖",
                                   "需要安装 Pillow：pip install pillow")
            return
        try:
            dlg = CropDialog(self, src, self.icon_crop)
            self.wait_window(dlg)
        except Exception as e:
            messagebox.showerror("错误", f"打开图片失败：\n{e}")
            return

        self.icon_crop = dlg.result
        if self.icon_crop:
            l, t, r, b = self.icon_crop
            self.lbl_crop.configure(text=f"{l},{t} → {r},{b}",
                                    text_color=ACCENT)
        else:
            self.lbl_crop.configure(text="未设置", text_color=MUTED)
        self.update_preview()

    def clear_crop(self):
        self.icon_crop = None
        self.lbl_crop.configure(text="未设置", text_color=MUTED)
        self.update_preview()

    def current_mode(self):
        return self._mode_map.get(self.cmb_mode.get(), "cover")

    def current_bg(self):
        if self.var_icon_bg_trans.get():
            return (0, 0, 0, 0)
        return hex_to_rgba(self.var_icon_bg.get(), 255)

    def update_preview(self):
        if not hasattr(self, "canvas_src"):
            return
        self.canvas_src.delete("all")
        self.canvas_preview.delete("all")
        self._src_photo = None
        self._preview_photo = None

        src = self.var_icon_src.get().strip()
        if not src or not os.path.isfile(src):
            self.canvas_src.create_text(80, 80, text="未选择图片",
                                        fill=MUTED)
            self.canvas_preview.create_text(80, 80, text="—", fill=MUTED)
            return

        if not HAS_PIL:
            self.canvas_src.create_text(80, 80, text="缺少 Pillow",
                                        fill=DANGER)
            return

        try:
            img = Image.open(src).convert("RGBA")
        except Exception:
            self.canvas_src.create_text(80, 80, text="无法读取",
                                        fill=DANGER)
            return

        thumb = img.copy()
        thumb.thumbnail((152, 152))
        self._src_photo = ImageTk.PhotoImage(thumb)
        self.canvas_src.create_image(80, 80, image=self._src_photo)

        try:
            pad = int(self.var_icon_pad.get() or 0)
        except tk.TclError:
            pad = 0

        try:
            out = prepare_icon_image(src, self.current_mode(), 152,
                                     self.current_bg(), self.icon_crop, pad)
            self._preview_photo = ImageTk.PhotoImage(out)
            self.canvas_preview.create_image(80, 80,
                                             image=self._preview_photo)
        except Exception:
            self.canvas_preview.create_text(80, 80, text="生成失败",
                                            fill=DANGER)

    # ------------------------------------------------------------------ #
    #  收集 / 应用配置
    # ------------------------------------------------------------------ #
    def _collect_options(self):
        return {
            "script": self.var_script.get(),
            "name": self.var_name.get(),
            "dist": self.var_dist.get(),
            "mode": self.var_mode.get(),
            "console": self.var_console.get(),
            "clean": self.var_clean.get(),
            "noconfirm": self.var_noconfirm.get(),
            "icon_src": self.var_icon_src.get(),
            "icon_out": self.var_icon_out.get(),
            "icon_mode": self.current_mode(),
            "icon_bg": self.current_bg(),
            "icon_bg_hex": self.var_icon_bg.get(),
            "icon_bg_trans": self.var_icon_bg_trans.get(),
            "icon_pad": self.var_icon_pad.get(),
            "icon_crop": self.icon_crop,
            "embed_icon": self.var_embed_icon.get(),
            "use_version": self.var_use_version.get(),
            "version": {k: v.get() for k, v in self.ver_vars.items()},
            "add_data": self.txt_add_data.get("1.0", "end").strip(),
            "hidden": self.txt_hidden.get("1.0", "end").strip(),
            "exclude": self.txt_exclude.get("1.0", "end").strip(),
            "extra": self.var_extra.get(),
            "upx": self.var_upx.get(),
            "no_upx": self.var_no_upx.get(),
        }

    def collect_config(self):
        return {
            "script": self.var_script.get(),
            "name": self.var_name.get(),
            "dist": self.var_dist.get(),
            "mode": self.var_mode.get(),
            "console": self.var_console.get(),
            "clean": self.var_clean.get(),
            "noconfirm": self.var_noconfirm.get(),
            "icon_src": self.var_icon_src.get(),
            "icon_out": self.var_icon_out.get(),
            "icon_mode": self.cmb_mode.get(),
            "icon_bg": self.var_icon_bg.get(),
            "icon_bg_trans": self.var_icon_bg_trans.get(),
            "icon_pad": self.var_icon_pad.get(),
            "icon_crop": list(self.icon_crop) if self.icon_crop else None,
            "embed_icon": self.var_embed_icon.get(),
            "use_version": self.var_use_version.get(),
            "version": {k: v.get() for k, v in self.ver_vars.items()},
            "add_data": self.txt_add_data.get("1.0", "end").strip(),
            "hidden": self.txt_hidden.get("1.0", "end").strip(),
            "exclude": self.txt_exclude.get("1.0", "end").strip(),
            "extra": self.var_extra.get(),
            "upx": self.var_upx.get(),
            "no_upx": self.var_no_upx.get(),
        }

    def apply_config(self, cfg):
        g = cfg.get
        self.var_script.set(g("script", ""))
        self.var_name.set(g("name", ""))
        self.var_dist.set(g("dist", ""))
        self.var_mode.set(g("mode", "onefile"))
        self.var_console.set(bool(g("console", False)))
        self.var_clean.set(bool(g("clean", False)))
        self.var_noconfirm.set(bool(g("noconfirm", True)))

        self.var_icon_src.set(g("icon_src", ""))
        self.var_icon_out.set(g("icon_out", ""))
        mode = g("icon_mode", "cover（居中裁剪铺满）")
        if mode not in self._mode_map:
            mode = "cover（居中裁剪铺满）"
        self.cmb_mode.set(mode)
        self.var_icon_bg.set(g("icon_bg", "#FFFFFF"))
        self.var_icon_bg_trans.set(bool(g("icon_bg_trans", True)))
        try:
            self.var_icon_pad.set(int(g("icon_pad", 0) or 0))
        except (TypeError, ValueError):
            self.var_icon_pad.set(0)
        self.color_chip.configure(bg=self.var_icon_bg.get())

        crop = cfg.get("icon_crop")
        self.icon_crop = tuple(crop) if crop else None
        if self.icon_crop:
            l, t, r, b = self.icon_crop
            self.lbl_crop.configure(text=f"{l},{t} → {r},{b}",
                                    text_color=ACCENT)
        else:
            self.lbl_crop.configure(text="未设置", text_color=MUTED)

        self.var_embed_icon.set(bool(g("embed_icon", True)))

        self.var_use_version.set(bool(g("use_version", True)))
        for k, v in (cfg.get("version") or {}).items():
            if k in self.ver_vars:
                self.ver_vars[k].set(v)

        for widget, key in ((self.txt_add_data, "add_data"),
                            (self.txt_hidden, "hidden"),
                            (self.txt_exclude, "exclude")):
            widget.delete("1.0", "end")
            widget.insert("1.0", g(key, ""))

        self.var_extra.set(g("extra", ""))
        self.var_upx.set(g("upx", ""))
        self.var_no_upx.set(bool(g("no_upx", False)))

    def _load_config(self, path, silent=False):
        if not path or not os.path.isfile(path):
            if not silent:
                messagebox.showwarning("提示", "配置文件不存在。")
            return
        try:
            cfg = load_cfg_file(path)
            self.apply_config(cfg)
            if not silent:
                messagebox.showinfo("成功", "配置已加载。")
        except Exception as e:
            if not silent:
                messagebox.showerror("错误", f"读取配置失败：\n{e}")

    def _save_config(self, path):
        ok = save_cfg_file(path, self.collect_config())
        if not ok:
            messagebox.showerror("错误", "保存配置失败。")
        return ok

    def _save_config_dialog(self):
        p = filedialog.asksaveasfilename(
            title="保存配置", defaultextension=".json",
            filetypes=[("JSON 配置", "*.json")])
        if p and self._save_config(p):
            messagebox.showinfo("成功", "配置已保存。")

    def _load_config_dialog(self):
        p = filedialog.askopenfilename(
            title="加载配置",
            filetypes=[("JSON 配置", "*.json"), ("所有文件", "*.*")])
        if p:
            self._load_config(p)

    # ------------------------------------------------------------------ #
    #  打包
    # ------------------------------------------------------------------ #
    def start_build(self):
        if self.building:
            return

        opts = self._collect_options()
        script = opts["script"]
        if not script or not os.path.isfile(script):
            messagebox.showwarning("提示",
                                   "请选择一个有效的 Python 入口脚本。")
            self.show_page("basic")
            return

        if not HAS_PIL and opts["icon_src"]:
            messagebox.showwarning("提示",
                                   "处理图标需要 Pillow：pip install pillow")
            return

        py = resolve_python()
        if not py:
            messagebox.showerror(
                "未找到 Python 解释器",
                "PyPacker 打包成 exe 后，需要系统里安装 Python 3 才能继续打包。\n\n"
                "请安装 Python 并确保 python.exe 已加入 PATH 环境变量。\n\n"
                "提示：直接用源码运行 PyPacker（python main.py）\n"
                "不会有这个问题。")
            return

        ok, msg = probe_pyinstaller(py)
        if not ok:
            if not messagebox.askyesno(
                    "未检测到 PyInstaller",
                    "当前 Python 环境没有安装 PyInstaller。\n\n"
                    "使用解释器：\n%s\n\n"
                    "是否现在自动安装？" % py):
                return
            ok, err = pip_install_pyinstaller(py)
            if not ok:
                messagebox.showerror(
                    "安装失败",
                    "自动安装失败，请手动执行：\n\n"
                    "%s -m pip install pyinstaller\n\n%s" % (py, err))
                return

        # ---- 关键优化：固定缓存目录，让 PyInstaller 复用 build 缓存 ----
        script_dir = os.path.dirname(os.path.abspath(script))
        cachedir = os.path.join(script_dir, ".pypacker_cache")
        try:
            os.makedirs(cachedir, exist_ok=True)
            # 检查是否可写
            testfile = os.path.join(cachedir, ".write_test")
            with open(testfile, "w") as f:
                f.write("ok")
            os.remove(testfile)
        except Exception:
            # 脚本目录不可写 → 退回用户目录
            cachedir = os.path.join(os.path.expanduser("~"),
                                    ".pypacker", "cache")
            try:
                os.makedirs(cachedir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("错误", f"无法创建缓存目录：\n{e}")
                return

        try:
            cmd, dist, name = build_command(opts, cachedir)
        except Exception as e:
            messagebox.showerror("配置错误", str(e))
            return

        self.building = True
        self.btn_build.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self._set_status("正在打包…", ACCENT)
        self._start_progress()
        self.clear_log()
        self.show_page("log")

        self._log("=" * 72 + "\n")
        self._log("  PyPacker  开始打包\n")
        self._log("=" * 72 + "\n")
        self._log("  解释器   : %s\n" % py)
        self._log("  缓存目录 : %s\n" % cachedir)
        self._log("  输出目录 : %s\n" % dist)
        self._log("  程序名称 : %s\n" % name)
        if opts.get("embed_icon") and opts.get("icon_src"):
            self._log("  图标嵌入 : 已启用（窗口 / 任务栏图标自动设置）\n")
        self._log("\n")

        t = threading.Thread(
            target=self._run_build_thread,
            args=(cmd, script_dir),
            daemon=True)
        t.start()

    def _run_build_thread(self, cmd, cwd):
        self.proc = run_build(cmd, cwd, self.log_queue)

    def stop_build(self):
        if self.proc and self.proc.poll() is None:
            if messagebox.askyesno("确认", "确定要中止当前打包吗？"):
                try:
                    self.proc.terminate()
                except Exception:
                    pass

    def _poll_log(self):
        try:
            while True:
                kind, payload = self.log_queue.get_nowait()
                if kind == "log":
                    self._log(payload)
                elif kind == "progress":
                    self._set_progress(payload)
                elif kind == "done":
                    self._on_build_done(payload)
        except queue.Empty:
            pass
        self.after(100, self._poll_log)

    def _on_build_done(self, code):
        self.building = False
        self.proc = None
        self.btn_build.configure(state="normal")
        self.btn_stop.configure(state="disabled")

        # 先把缓冲区里的日志全部刷出去
        self._flush_log()

        if code == 0:
            self._set_progress(1.0)
            self.after(1500, self._reset_progress)
            self._set_status("打包完成", SUCCESS)
            self._log("\n" + "=" * 72 + "\n")
            self._log("  ✔  打包成功\n")
            self._log("=" * 72 + "\n")
            self._flush_log()
            if messagebox.askyesno("完成", "打包成功！\n是否打开输出目录？"):
                self.open_dist()
        else:
            self._set_status("打包失败（退出码 %s）" % code, DANGER)
            self._log("\n" + "=" * 72 + "\n")
            self._log("  ✘  打包失败，退出码 %s\n" % code)
            self._log("=" * 72 + "\n")
            self._flush_log()

    # ------------------------------------------------------------------ #
    #  状态 / 进度条
    # ------------------------------------------------------------------ #
    def _set_status(self, text, color):
        self.var_status.set(text)
        self.dot.itemconfigure(self._dot_id, fill=color)

    def _start_progress(self):
        self._progress_val = 0.0
        try:
            self.pbar.set(0)
        except Exception:
            pass

    def _set_progress(self, value):
        """真实进度：只前进不倒退"""
        try:
            value = float(value)
        except (TypeError, ValueError):
            return
        value = max(0.0, min(1.0, value))
        if value <= self._progress_val and value != 0.0:
            return
        self._progress_val = value
        try:
            self.pbar.set(value)
        except Exception:
            pass

    def _reset_progress(self):
        self._progress_val = 0.0
        try:
            self.pbar.set(0)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  日志（缓冲 + 批量刷新）
    # ------------------------------------------------------------------ #
    def _log(self, text):
        self._log_buf.append(text)
        if self._log_flush_job is None:
            self._log_flush_job = self.after(50, self._flush_log)

    def _flush_log(self):
        if self._log_flush_job is not None:
            try:
                self.after_cancel(self._log_flush_job)
            except Exception:
                pass
            self._log_flush_job = None

        if not self._log_buf:
            return
        text = "".join(self._log_buf)
        self._log_buf.clear()

        try:
            self.txt_log.configure(state="normal")
            self.txt_log.insert("end", text)
            total = int(self.txt_log.index("end-1c").split(".")[0])
            if total > 6000:
                self.txt_log.delete("1.0", f"{total - 5000}.0")
            self.txt_log.see("end")
            self.txt_log.configure(state="disabled")
        except Exception:
            pass

    def clear_log(self):
        self._log_buf.clear()
        if self._log_flush_job is not None:
            try:
                self.after_cancel(self._log_flush_job)
            except Exception:
                pass
            self._log_flush_job = None
        try:
            self.txt_log.configure(state="normal")
            self.txt_log.delete("1.0", "end")
            self.txt_log.configure(state="disabled")
        except Exception:
            pass

    def open_dist(self):
        script = self.var_script.get().strip()
        dist = self.var_dist.get().strip()
        if not dist and script:
            dist = os.path.join(os.path.dirname(os.path.abspath(script)),
                                "dist")
        if not dist or not os.path.isdir(dist):
            messagebox.showinfo("提示", "输出目录还不存在。")
            return
        open_folder(dist)

    # ------------------------------------------------------------------ #
    #  环境自检（异步）
    # ------------------------------------------------------------------ #
    def _dump_env_async(self):
        def work():
            try:
                py = resolve_python()
                lines = [
                    "=" * 72 + "\n",
                    "  PyPacker 环境自检\n",
                    "=" * 72 + "\n",
                    "  frozen            : %s\n" % getattr(sys, "frozen", False),
                    "  sys.executable    : %s\n" % sys.executable,
                    "  _base_executable  : %s\n" %
                        getattr(sys, "_base_executable", "(无)"),
                    "  解析到的解释器    : %s\n" % (py or "(未找到)"),
                    "=" * 72 + "\n\n",
                ]
                for line in lines:
                    self.log_queue.put(("log", line))
            except Exception as e:
                self.log_queue.put(("log", f"环境自检失败：{e}\n"))

        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------------ #
    def _on_close(self):
        if self.building:
            if not messagebox.askyesno("确认", "正在打包中，确定要退出吗？"):
                return
            self.stop_build()

        # 清理未完成的日志刷新任务
        if self._log_flush_job is not None:
            try:
                self.after_cancel(self._log_flush_job)
            except Exception:
                pass

        try:
            self._save_config(CONFIG_PATH)
        except Exception:
            pass
        self.destroy()


# --------------------------------------------------------------------------- #
def run():
    app = PyPackerApp()
    if not HAS_PIL:
        app.after(300, lambda: messagebox.showwarning(
            "缺少 Pillow",
            "未检测到 Pillow，图标相关功能不可用。\n\n"
            "安装命令：\n    pip install pillow"))
    app.mainloop()