# -*- coding: utf-8 -*-
"""通用工具函数"""
import os
import re
import subprocess
import sys


# --------------------------------------------------------------------------- #
#  子进程隐藏窗口（Windows）
# --------------------------------------------------------------------------- #
_CREATE_NO_WINDOW = 0x08000000


def no_window_kwargs():
    """Windows 上让子进程不弹控制台窗口，其它平台返回空 dict。
    用于所有 subprocess 调用，避免打包时黑窗口一闪而过。"""
    if sys.platform.startswith("win"):
        return {"creationflags": _CREATE_NO_WINDOW}
    return {}


# --------------------------------------------------------------------------- #
#  颜色
# --------------------------------------------------------------------------- #
def lighten(hex_color, amount=0.88):
    """把颜色向白色方向混合，amount 越大越接近白色。"""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = int(r * (1 - amount) + 255 * amount)
    g = int(g * (1 - amount) + 255 * amount)
    b = int(b * (1 - amount) + 255 * amount)
    return "#%02x%02x%02x" % (r, g, b)


def hex_to_rgba(s, alpha=255):
    s = str(s).lstrip("#")
    try:
        if len(s) == 8:
            return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4, 6))
        if len(s) == 6:
            r, g, b = (int(s[i:i + 2], 16) for i in (0, 2, 4))
            return (r, g, b, alpha)
    except ValueError:
        pass
    return (255, 255, 255, alpha)


# --------------------------------------------------------------------------- #
#  版本号
# --------------------------------------------------------------------------- #
def parse_version(text):
    """'1.2.3.4' -> (1, 2, 3, 4)，不足 4 位补 0。"""
    nums = [int(x) for x in re.findall(r"\d+", str(text))][:4]
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums)


# --------------------------------------------------------------------------- #
#  打开文件夹
# --------------------------------------------------------------------------- #
def open_folder(path):
    if not path or not os.path.exists(path):
        return False
    try:
        kw = no_window_kwargs()
        if sys.platform.startswith("win"):
            os.startfile(path)                       # noqa
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path], **kw)
        else:
            subprocess.Popen(["xdg-open", path], **kw)
        return True
    except Exception:
        return False