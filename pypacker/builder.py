# -*- coding: utf-8 -*-
"""PyInstaller 命令构建 + 执行（含真实进度解析 + 环境隔离）"""
import os
import shlex
import subprocess
import sys

from .icon_embed import generate_runtime_hook
from .icon import create_ico
from .python_env import resolve_python
from .utils import no_window_kwargs
from .version_info import make_version_file


# --------------------------------------------------------------------------- #
#  环境变量清理
# --------------------------------------------------------------------------- #
#  PyPacker.exe 自己是被 PyInstaller 打过的，运行时会在环境变量里注入
#  _MEIPASS / TCL_LIBRARY / TK_LIBRARY / PYTHONHOME 等。
#  这些变量会被子进程（python.exe -m PyInstaller）继承，导致 PyInstaller
#  去错误的临时目录找 tcl/tk 数据，打出来的 exe 就会报
#  "Tk data directory not found"。
#
#  解决：启动子进程前把这些变量统统清掉。
# --------------------------------------------------------------------------- #
_POLLUTED_KEYS = (
    # PyInstaller 运行时注入
    "_MEIPASS", "_MEIPASS2",
    "_PYI_APPLICATION_HOME_DIR",
    "_PYI_ARCHIVE_FILE",
    "_PYI_PARENT_PROCESS_LEVEL",
    "_PYI_SPLASH_IPC",
    # Python 路径污染
    "PYTHONHOME", "PYTHONPATH",
    # Tcl/Tk 数据目录污染
    "TCL_LIBRARY", "TK_LIBRARY",
    "TIX_LIBRARY",
    # 其他可能干扰 PyInstaller 的
    "PYTHONSTARTUP",
    "PYTHONEXECUTABLE",
)


def _clean_env():
    """返回一份干净的、可传给子进程的环境变量。"""
    env = os.environ.copy()
    for key in _POLLUTED_KEYS:
        env.pop(key, None)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


# --------------------------------------------------------------------------- #
#  阶段 → 进度映射
# --------------------------------------------------------------------------- #
_STAGE_MAP = [
    ("Analyzing",                       0.05),
    ("Processing module hooks",         0.10),
    ("Loading module hooks",            0.18),
    ("Looking for ctypes",              0.42),
    ("Analyzing run-time hooks",        0.48),
    ("Looking for dynamic libraries",   0.55),
    ("Looking for eggs",                0.60),
    ("Building PYZ",                    0.68),
    ("Building PKG",                    0.78),
    ("Building EXE",                    0.88),
    ("Building COLLECT",                0.92),
    ("Copying bootloader",              0.94),
    ("Copying",                         0.95),
    ("completed successfully",          1.00),
]


def _parse_stage(line, current):
    for keyword, value in _STAGE_MAP:
        if keyword in line and value > current:
            return value
    return current


# --------------------------------------------------------------------------- #
#  命令构建
# --------------------------------------------------------------------------- #
def build_command(opts, tmpdir):
    py = resolve_python()
    if not py:
        raise RuntimeError(
            "未找到 Python 解释器。\n\n"
            "PyPacker 打包成 exe 后，需要系统里安装 Python 3 才能继续打包。\n"
            "请安装 Python 并确保 python.exe 已加入 PATH 环境变量。")

    script = opts["script"]
    name = opts.get("name") or os.path.splitext(os.path.basename(script))[0]
    dist = opts.get("dist") or \
        os.path.join(os.path.dirname(os.path.abspath(script)), "dist")

    cmd = [py, "-m", "PyInstaller"]

    if opts.get("noconfirm", True):
        cmd.append("--noconfirm")
    if opts.get("clean", False):
        cmd.append("--clean")

    cmd.append("--onefile" if opts.get("mode") == "onefile" else "--onedir")
    cmd.append("--console" if opts.get("console") else "--windowed")

    cmd += ["--name", name,
            "--distpath", dist,
            "--workpath", os.path.join(tmpdir, "build"),
            "--specpath", os.path.join(tmpdir, "spec")]

    # ---- 关键：自动收集 tkinter / customtkinter 的全部资源 ----
    #  解决 "Tk data directory not found" 错误。
    #  因为用了干净的环境变量，这次能找到正确的 tcl/tk 数据目录。
    cmd += ["--collect-all", "tkinter"]
    cmd += ["--collect-all", "customtkinter"]

    icon_src = (opts.get("icon_src") or "").strip()
    icon_out_for_hook = None

    if icon_src and os.path.isfile(icon_src):
        icon_out = (opts.get("icon_out") or "").strip() or \
            os.path.join(tmpdir, "app_icon.ico")
        create_ico(icon_src, icon_out,
                   mode=opts.get("icon_mode", "cover"),
                   bg=opts.get("icon_bg", (0, 0, 0, 0)),
                   crop=opts.get("icon_crop"),
                   pad=int(opts.get("icon_pad") or 0))
        cmd += ["--icon", icon_out]
        icon_out_for_hook = icon_out

    # ---- 把图标以 base64 形式嵌入目标程序，运行时自动设置窗口/任务栏图标 ----
    if opts.get("embed_icon") and icon_out_for_hook:
        from .icon_embed import generate_runtime_hook
        hook_path = os.path.join(tmpdir, "_pypacker_icon_hook.py")
        try:
            generate_runtime_hook(icon_out_for_hook, hook_path)
            cmd += ["--runtime-hook", hook_path]
        except Exception:
            pass

    if opts.get("use_version") and sys.platform.startswith("win"):
        ver = dict(opts.get("version") or {})
        ver.setdefault("original_filename", name + ".exe")
        if not ver.get("original_filename"):
            ver["original_filename"] = name + ".exe"
        if not ver.get("internal_name"):
            ver["internal_name"] = name
        vpath = os.path.join(tmpdir, "version_info.txt")
        make_version_file(vpath, ver)
        cmd += ["--version-file", vpath]

    for line in (opts.get("add_data") or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ";" in line:
            s, d = line.split(";", 1)
        else:
            s, d = line, "."
        cmd += ["--add-data",
                f"{s.strip()}{os.pathsep}{d.strip() or '.'}"]

    for line in (opts.get("hidden") or "").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            cmd += ["--hidden-import", line]

    for line in (opts.get("exclude") or "").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            cmd += ["--exclude-module", line]

    if opts.get("no_upx"):
        cmd.append("--noupx")
    elif (opts.get("upx") or "").strip():
        cmd += ["--upx-dir", opts["upx"].strip()]

    extra = (opts.get("extra") or "").strip()
    if extra:
        try:
            if sys.platform.startswith("win"):
                parts = shlex.split(extra, posix=False)
                parts = [p[1:-1] if len(p) > 1 and p[0] == p[-1] == '"'
                         else p for p in parts]
            else:
                parts = shlex.split(extra)
            cmd += parts
        except ValueError as e:
            raise ValueError(f"额外参数解析失败：{e}")

    cmd.append(os.path.abspath(script))
    return cmd, dist, name


# --------------------------------------------------------------------------- #
#  执行（带真实进度 + 干净环境）
# --------------------------------------------------------------------------- #
def run_build(cmd, cwd, log_queue):
    """
    在子进程里执行 PyInstaller。
    log_queue 收到的消息：
        ("log",      日志行)
        ("progress", 0.00 ~ 1.00 的进度值)
        ("done",     退出码)
    """
    env = _clean_env()          # ← 关键：清掉污染的环境变量

    shown = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    log_queue.put(("log", "\n$ " + shown + "\n\n"))

    try:
        proc = subprocess.Popen(
            cmd, cwd=cwd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            universal_newlines=True, encoding="utf-8", errors="replace",
            bufsize=1,
            **no_window_kwargs())
    except Exception as e:
        log_queue.put(("log", f"\n启动失败：{e}\n"))
        log_queue.put(("done", -1))
        return None

    progress = 0.01
    log_queue.put(("progress", progress))

    try:
        for line in proc.stdout:
            if "\r" in line:
                line = line.split("\r")[-1]

            log_queue.put(("log", line))

            new_progress = _parse_stage(line, progress)
            if new_progress != progress:
                progress = new_progress
                log_queue.put(("progress", progress))
    except Exception:
        pass

    code = proc.wait()
    if code == 0:
        log_queue.put(("progress", 1.0))
    log_queue.put(("done", code))
    return proc