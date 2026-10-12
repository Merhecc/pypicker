# -*- coding: utf-8 -*-
"""把 ico 转成 base64，并生成 PyInstaller runtime hook 脚本。

策略：
    1. hook 被 PyInstaller 加载时，先写日志确认，再延迟执行 patch
    2. patch tkinter / customtkinter / Qt / wx 的窗口构造
    3. 每个窗口创建后，在多个时间点（idle / 50 / 200 / 500 / 1000ms）反复设置图标
    4. Windows 上用 LoadImageW + WM_SETICON 直接设置窗口 HICON（绕过所有框架）
    5. 完整日志写入 %TEMP%\\pypacker_icon_hook.log
"""
import base64
import os


_HOOK_TEMPLATE = r'''# -*- coding: utf-8 -*-
"""PyPacker 自动生成的运行时 hook，请勿手动修改。"""
import base64
import os
import sys
import tempfile


_ICON_B64 = """__ICON_B64__"""
_ICON_NAME = "_pypacker_embedded.ico"


# --------------------------------------------------------------------------- #
#  日志（同时写多个位置，确保至少一个能成功）
# --------------------------------------------------------------------------- #
def _log(msg):
    import time
    line = "[%s] %s\n" % (time.strftime("%H:%M:%S"), msg)
    targets = [
        os.path.join(tempfile.gettempdir(), "pypacker_icon_hook.log"),
        os.path.join(os.path.expanduser("~"), "pypacker_icon_hook.log"),
    ]
    for p in targets:
        try:
            with open(p, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass


_log("=" * 60)
_log("hook 开始加载")
_log("frozen     = %s" % getattr(sys, "frozen", False))
_log("_MEIPASS   = %s" % getattr(sys, "_MEIPASS", None))
_log("executable = %s" % sys.executable)


# --------------------------------------------------------------------------- #
#  主动设置 TCL/TK 环境变量（因为我们的 hook 早于官方 hook）
# --------------------------------------------------------------------------- #
def _setup_tcl_tk_env():
    if not getattr(sys, "frozen", False):
        return
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        return
    pairs = [
        ("TCL_LIBRARY", ["_tcl_data", "tcl", "tcl8.6", "tcl8"]),
        ("TK_LIBRARY",  ["_tk_data", "tk", "tk8.6", "tk8"]),
    ]
    for env_name, cands in pairs:
        if os.environ.get(env_name):
            continue
        for cand in cands:
            p = os.path.join(base, cand)
            if os.path.isdir(p):
                os.environ[env_name] = p
                _log("设置 %s = %s" % (env_name, p))
                break


_setup_tcl_tk_env()


# --------------------------------------------------------------------------- #
#  还原 ico
# --------------------------------------------------------------------------- #
def _ensure_icon_file():
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        base = os.path.join(tempfile.gettempdir(), "_pypacker_runtime")
        try:
            os.makedirs(base, exist_ok=True)
        except Exception as e:
            _log("mkdir 失败：%s" % e)
            return None

    path = os.path.join(base, _ICON_NAME)
    if not os.path.exists(path):
        try:
            data = base64.b64decode(_ICON_B64)
            with open(path, "wb") as f:
                f.write(data)
            _log("ico 写入成功：%s（%d 字节）" % (path, len(data)))
        except Exception as e:
            _log("b64 解码失败：%s" % e)
            return None
    else:
        _log("ico 已存在：%s" % path)
    return path


_ICON_PATH = _ensure_icon_file()
_log("_ICON_PATH = %s" % _ICON_PATH)


# --------------------------------------------------------------------------- #
#  Windows API 直接设置 HICON（终极兜底）
# --------------------------------------------------------------------------- #
def _apply_win_icon(win):
    if not sys.platform.startswith("win") or not _ICON_PATH:
        return
    try:
        import ctypes
        user32 = ctypes.windll.user32

        try:
            hwnd = int(win.winfo_id())
        except Exception:
            return

        # 向上找顶层窗口
        try:
            parent = user32.GetParent(hwnd)
            while parent:
                hwnd = parent
                parent = user32.GetParent(hwnd)
        except Exception:
            pass

        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        LR_DEFAULTSIZE = 0x00000040

        hicon = user32.LoadImageW(
            None, _ICON_PATH, IMAGE_ICON, 0, 0,
            LR_LOADFROMFILE | LR_DEFAULTSIZE)
        if not hicon:
            _log("LoadImageW 失败")
            return

        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)
        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)
        _log("WinAPI 设置成功 hwnd=%s" % hwnd)
    except Exception as e:
        _log("WinAPI 失败：%s" % e)


# --------------------------------------------------------------------------- #
#  Tk 图标设置（用多种方式）
# --------------------------------------------------------------------------- #
def _apply_tk_icon(win):
    if not _ICON_PATH:
        return
    try:
        from tkinter import PhotoImage
    except Exception:
        return

    # 方式 1：iconphoto（推荐）
    try:
        img = PhotoImage(file=_ICON_PATH)
        # 关键：保留引用，防止被 GC
        if not hasattr(win, "_pypacker_icon_refs"):
            win._pypacker_icon_refs = []
        win._pypacker_icon_refs.append(img)
        win.wm_iconphoto(True, img)
        _log("iconphoto 成功：%s" % win)
    except Exception as e:
        _log("iconphoto 失败：%s" % e)

    # 方式 2：iconbitmap
    try:
        win.iconbitmap(_ICON_PATH)
        _log("iconbitmap 成功：%s" % win)
    except Exception as e:
        _log("iconbitmap 失败：%s" % e)

    # 方式 3：WinAPI 兜底
    _apply_win_icon(win)


# --------------------------------------------------------------------------- #
#  Tk / customtkinter
# --------------------------------------------------------------------------- #
def _patch_tkinter():
    try:
        import tkinter
    except ImportError:
        _log("tkinter 未安装")
        return
    except Exception as e:
        _log("导入 tkinter 失败：%s" % e)
        return

    _log("tkinter 导入成功")

    if not _ICON_PATH:
        return

    def _schedule(win):
        """在多个时间点反复设置图标。"""
        def _set():
            try:
                _apply_tk_icon(win)
            except Exception as e:
                _log("应用图标失败：%s" % e)

        try:
            win.after_idle(_set)
        except Exception:
            pass
        for delay in (30, 100, 300, 800, 1500):
            try:
                win.after(delay, _set)
            except Exception:
                pass

    def _wrap_init(cls, name):
        if getattr(cls, "_pypacker_patched", False):
            return
        orig = cls.__init__

        def _init(self, *a, **kw):
            orig(self, *a, **kw)
            _log("窗口创建：%s" % name)
            _schedule(self)

        cls.__init__ = _init
        cls._pypacker_patched = True

    _wrap_init(tkinter.Tk, "tkinter.Tk")
    _wrap_init(tkinter.Toplevel, "tkinter.Toplevel")

    try:
        import customtkinter
        if hasattr(customtkinter, "CTk"):
            _wrap_init(customtkinter.CTk, "customtkinter.CTk")
        if hasattr(customtkinter, "CTkToplevel"):
            _wrap_init(customtkinter.CTkToplevel, "customtkinter.CTkToplevel")
    except ImportError:
        pass
    except Exception as e:
        _log("patch customtkinter 失败：%s" % e)

    # 拦截 mainloop：主循环启动前对所有已创建窗口再设一次
    try:
        _orig_mainloop = tkinter.Misc.mainloop

        def _mainloop(self, *a, **kw):
            _log("mainloop 即将启动，重新设置图标")
            try:
                _apply_tk_icon(self)
            except Exception:
                pass
            return _orig_mainloop(self, *a, **kw)

        tkinter.Misc.mainloop = _mainloop
    except Exception as e:
        _log("patch mainloop 失败：%s" % e)


# --------------------------------------------------------------------------- #
#  Qt（PyQt5 / PyQt6 / PySide2 / PySide6）
# --------------------------------------------------------------------------- #
def _patch_qt():
    if not _ICON_PATH:
        return

    targets = [
        ("PyQt5.QtWidgets",   "QApplication", "PyQt5.QtGui",   "QIcon"),
        ("PyQt6.QtWidgets",   "QApplication", "PyQt6.QtGui",   "QIcon"),
        ("PySide2.QtWidgets", "QApplication", "PySide2.QtGui", "QIcon"),
        ("PySide6.QtWidgets", "QApplication", "PySide6.QtGui", "QIcon"),
    ]

    for modname, clsname, guimod, iconname in targets:
        try:
            widgets = __import__(modname, fromlist=[clsname])
            gui = __import__(guimod, fromlist=[iconname])
            App = getattr(widgets, clsname)
            Icon = getattr(gui, iconname)
        except Exception:
            continue

        if getattr(App, "_pypacker_patched", False):
            continue

        def _make(_orig, _Icon, _path, _tag):
            def _init(self, *a, **kw):
                _orig(self, *a, **kw)
                try:
                    self.setWindowIcon(_Icon(_path))
                    _log("Qt setWindowIcon 成功：%s" % _tag)
                except Exception as e:
                    _log("Qt setWindowIcon 失败：%s" % e)
            return _init

        App.__init__ = _make(App.__init__, Icon, _ICON_PATH, modname)
        App._pypacker_patched = True


# --------------------------------------------------------------------------- #
#  wxPython
# --------------------------------------------------------------------------- #
def _patch_wx():
    if not _ICON_PATH:
        return
    try:
        import wx
    except ImportError:
        return

    if getattr(wx.Frame, "_pypacker_patched", False):
        return

    _orig = wx.Frame.__init__

    def _init(self, *a, **kw):
        _orig(self, *a, **kw)
        try:
            self.SetIcon(wx.Icon(_ICON_PATH))
            _log("wx SetIcon 成功")
        except Exception as e:
            _log("wx SetIcon 失败：%s" % e)

    wx.Frame.__init__ = _init
    wx.Frame._pypacker_patched = True


# --------------------------------------------------------------------------- #
_patch_tkinter()
_patch_qt()
_patch_wx()
_log("hook 初始化结束")
'''


# --------------------------------------------------------------------------- #
#  对外接口
# --------------------------------------------------------------------------- #
def ico_to_base64(ico_path):
    with open(ico_path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def generate_runtime_hook(ico_path, output_path):
    b64 = ico_to_base64(ico_path)
    content = _HOOK_TEMPLATE.replace("__ICON_B64__", b64)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path