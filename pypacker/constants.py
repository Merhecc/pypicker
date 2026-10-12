# -*- coding: utf-8 -*-
"""主题常量、字体、页面元数据"""
import os

import customtkinter as ctk


# --------------------------------------------------------------------------- #
#  颜色
# --------------------------------------------------------------------------- #
BG          = "#f4f6fb"
CARD        = "#ffffff"
BORDER      = "#e6eaf2"
TEXT        = "#0f172a"
TEXT_SUB    = "#475569"
MUTED       = "#94a3b8"
ACCENT      = "#3b6ef5"
ACCENT_HOV  = "#2b5ce0"
SUCCESS     = "#10b981"
DANGER      = "#ef4444"
CODE_BG     = "#0f172a"
CODE_FG     = "#cbd5e1"

C_BASIC     = "#3b6ef5"
C_ICON      = "#8b5cf6"
C_VERSION   = "#10b981"
C_ADV       = "#f59e0b"
C_LOG       = "#06b6d4"


# --------------------------------------------------------------------------- #
#  图标尺寸
# --------------------------------------------------------------------------- #
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


# --------------------------------------------------------------------------- #
#  配置文件路径
# --------------------------------------------------------------------------- #
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".pypacker.json")


# --------------------------------------------------------------------------- #
#  页面元数据
# --------------------------------------------------------------------------- #
PAGE_META = {
    "basic":    ("基本设置", "选择入口脚本、程序名称与打包模式",  C_BASIC,   "basic"),
    "icon":     ("图标",     "把 PNG / JPG 裁剪转换为多尺寸 ICO", C_ICON,    "icon"),
    "version":  ("版本信息", "写入 Windows 可执行文件的版本资源", C_VERSION, "version"),
    "advanced": ("高级",     "附加数据、隐藏导入、排除模块与 UPX", C_ADV,     "advanced"),
    "log":      ("打包日志", "查看 PyInstaller 的实时输出",      C_LOG,     "log"),
}

PAGE_ORDER = ["basic", "icon", "version", "advanced", "log"]


# --------------------------------------------------------------------------- #
#  字体（延迟初始化）
# --------------------------------------------------------------------------- #
class F:
    """全局字体。需在 CTk 根窗口创建后调用 F.init() 初始化。"""
    family = "Microsoft YaHei UI"
    mono_family = "Consolas"

    display = None
    h1 = None
    h2 = None
    body = None
    body_b = None
    small = None
    tiny = None
    mono = None

    _inited = False

    @classmethod
    def init(cls):
        if cls._inited:
            return

        try:
            import tkinter.font as tkfont
            fams = set(tkfont.families())
        except Exception:
            fams = set()

        for name in ("Microsoft YaHei UI", "Microsoft YaHei",
                     "PingFang SC", "Noto Sans CJK SC",
                     "Source Han Sans SC", "WenQuanYi Micro Hei",
                     "Segoe UI"):
            if name in fams:
                cls.family = name
                break

        for name in ("JetBrains Mono", "Cascadia Mono", "Consolas",
                     "Menlo", "DejaVu Sans Mono", "Courier New"):
            if name in fams:
                cls.mono_family = name
                break

        f = cls.family
        m = cls.mono_family

        cls.display = ctk.CTkFont(family=f, size=26, weight="bold")
        cls.h1      = ctk.CTkFont(family=f, size=20, weight="bold")
        cls.h2      = ctk.CTkFont(family=f, size=15, weight="bold")
        cls.body    = ctk.CTkFont(family=f, size=14)
        cls.body_b  = ctk.CTkFont(family=f, size=14, weight="bold")
        cls.small   = ctk.CTkFont(family=f, size=13)
        cls.tiny    = ctk.CTkFont(family=f, size=12)
        cls.mono    = ctk.CTkFont(family=m, size=13)

        cls._inited = True