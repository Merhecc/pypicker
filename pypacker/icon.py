# -*- coding: utf-8 -*-
"""图标处理：图片缩放/裁切/生成多尺寸 ico，以及首页卡片的矢量图标绘制。"""
import math

try:
    from PIL import Image
    HAS_PIL = True
    try:
        RESAMPLE = Image.Resampling.LANCZOS
    except AttributeError:
        RESAMPLE = Image.LANCZOS
except ImportError:
    HAS_PIL = False
    Image = None
    RESAMPLE = None

from .constants import ICO_SIZES


# --------------------------------------------------------------------------- #
#  图片 -> 图标
# --------------------------------------------------------------------------- #
def prepare_icon_image(src, mode="cover", size=256, bg=(0, 0, 0, 0),
                       crop=None, pad=0):
    """把任意图片处理成 size×size 的 RGBA 图像。

    mode:
        cover    —— 居中裁正方形后缩放（铺满、不变形、会裁掉边缘）
        contain  —— 完整显示，不足部分用背景色填充（不变形、不裁切）
        stretch  —— 强行拉伸到正方形（会变形）
    crop: (left, top, right, bottom) 原图像素坐标
    pad : 最终图标四周留出的透明内边距（像素）
    """
    if not HAS_PIL:
        raise RuntimeError("需要安装 Pillow：pip install pillow")

    img = Image.open(src).convert("RGBA")

    if crop:
        l, t, r, b = (int(v) for v in crop)
        l = max(0, min(l, img.width - 1))
        t = max(0, min(t, img.height - 1))
        r = max(l + 1, min(r, img.width))
        b = max(t + 1, min(b, img.height))
        img = img.crop((l, t, r, b))

    if img.width < 1 or img.height < 1:
        raise ValueError("无效的裁剪区域")

    size = int(size)
    pad = max(0, min(int(pad), size // 2 - 1))
    inner = max(1, size - 2 * pad)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    if mode == "stretch":
        resized = img.resize((inner, inner), RESAMPLE)
        canvas.paste(resized, (pad, pad), resized)

    elif mode == "contain":
        w, h = img.size
        s = min(inner / w, inner / h)
        nw = max(1, int(round(w * s)))
        nh = max(1, int(round(h * s)))
        resized = img.resize((nw, nh), RESAMPLE)
        plate = Image.new("RGBA", (inner, inner), bg)
        plate.paste(resized, ((inner - nw) // 2, (inner - nh) // 2), resized)
        canvas.paste(plate, (pad, pad), plate)

    else:  # cover
        w, h = img.size
        s = min(w, h)
        l, t = (w - s) // 2, (h - s) // 2
        img = img.crop((l, t, l + s, t + s))
        resized = img.resize((inner, inner), RESAMPLE)
        canvas.paste(resized, (pad, pad), resized)

    return canvas


def create_ico(src, dst, mode="cover", bg=(0, 0, 0, 0), crop=None, pad=0,
               sizes=None):
    """生成多尺寸 .ico 文件"""
    sizes = sizes or ICO_SIZES
    base = prepare_icon_image(src, mode, max(sizes), bg, crop, pad)
    base.save(dst, format="ICO", sizes=[(s, s) for s in sizes])
    return dst


# --------------------------------------------------------------------------- #
#  首页卡片矢量图标
# --------------------------------------------------------------------------- #
def draw_feature_icon(canvas, cx, cy, size, name, color):
    """在 Canvas 上以 (cx, cy) 为中心绘制 size 大小的矢量图标。"""
    r = size / 2.0
    w = max(1.6, size / 13.0)

    if name == "basic":
        canvas.create_polygon(
            cx - r * 0.6, cy - r,
            cx + r * 0.15, cy - r,
            cx + r * 0.6, cy - r * 0.45,
            cx + r * 0.6, cy + r,
            cx - r * 0.6, cy + r,
            outline=color, fill="", width=w, joinstyle="round")
        canvas.create_line(
            cx + r * 0.15, cy - r, cx + r * 0.15, cy - r * 0.45,
            cx + r * 0.6, cy - r * 0.45,
            fill=color, width=w, joinstyle="round", capstyle="round")
        for yy in (-r * 0.1, r * 0.2, r * 0.5):
            canvas.create_line(
                cx - r * 0.3, cy + yy, cx + r * 0.3, cy + yy,
                fill=color, width=w, capstyle="round")

    elif name == "icon":
        canvas.create_rectangle(
            cx - r * 0.85, cy - r * 0.7, cx + r * 0.85, cy + r * 0.7,
            outline=color, width=w)
        canvas.create_oval(
            cx - r * 0.5, cy - r * 0.45, cx - r * 0.15, cy - r * 0.1,
            outline=color, width=w)
        canvas.create_line(
            cx - r * 0.7, cy + r * 0.45,
            cx - r * 0.15, cy - r * 0.05,
            cx + r * 0.15, cy + r * 0.2,
            cx + r * 0.45, cy - r * 0.1,
            cx + r * 0.75, cy + r * 0.45,
            fill=color, width=w, joinstyle="round", capstyle="round")

    elif name == "version":
        canvas.create_oval(
            cx - r * 0.85, cy - r * 0.85, cx + r * 0.85, cy + r * 0.85,
            outline=color, width=w)
        canvas.create_oval(
            cx - r * 0.08, cy - r * 0.5, cx + r * 0.08, cy - r * 0.34,
            fill=color, outline="")
        canvas.create_line(
            cx, cy - r * 0.14, cx, cy + r * 0.5,
            fill=color, width=w, capstyle="round")

    elif name == "advanced":
        canvas.create_oval(
            cx - r * 0.68, cy - r * 0.68, cx + r * 0.68, cy + r * 0.68,
            outline=color, width=w)
        canvas.create_oval(
            cx - r * 0.22, cy - r * 0.22, cx + r * 0.22, cy + r * 0.22,
            outline=color, width=w)
        for i in range(8):
            a = i * math.pi / 4
            canvas.create_line(
                cx + math.cos(a) * r * 0.68,
                cy + math.sin(a) * r * 0.68,
                cx + math.cos(a) * r * 0.95,
                cy + math.sin(a) * r * 0.95,
                fill=color, width=w, capstyle="round")

    elif name == "log":
        canvas.create_rectangle(
            cx - r * 0.9, cy - r * 0.72, cx + r * 0.9, cy + r * 0.72,
            outline=color, width=w)
        canvas.create_line(
            cx - r * 0.55, cy - r * 0.35,
            cx - r * 0.15, cy,
            cx - r * 0.55, cy + r * 0.35,
            fill=color, width=w, joinstyle="round", capstyle="round")
        canvas.create_line(
            cx + r * 0.02, cy + r * 0.32, cx + r * 0.5, cy + r * 0.32,
            fill=color, width=w, capstyle="round")