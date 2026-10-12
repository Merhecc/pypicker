# -*- coding: utf-8 -*-
"""Python 解释器解析 + PyInstaller 探测（带环境隔离）"""
import os
import shutil
import subprocess
import sys

from .utils import no_window_kwargs


_PY_CACHE = {"path": None, "checked": False}

# 与 builder 里保持一致的污染变量清单
_POLLUTED_KEYS = (
    "_MEIPASS", "_MEIPASS2",
    "_PYI_APPLICATION_HOME_DIR",
    "_PYI_ARCHIVE_FILE",
    "_PYI_PARENT_PROCESS_LEVEL",
    "_PYI_SPLASH_IPC",
    "PYTHONHOME", "PYTHONPATH",
    "TCL_LIBRARY", "TK_LIBRARY", "TIX_LIBRARY",
    "PYTHONSTARTUP", "PYTHONEXECUTABLE",
)


def _clean_env():
    env = os.environ.copy()
    for key in _POLLUTED_KEYS:
        env.pop(key, None)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def resolve_python():
    if not getattr(sys, "frozen", False):
        return sys.executable

    if _PY_CACHE["checked"]:
        return _PY_CACHE["path"]

    nowin = no_window_kwargs()
    env = _clean_env()
    result = None

    base = getattr(sys, "_base_executable", None)
    if base:
        name = os.path.basename(base).lower()
        if "python" in name:
            if os.path.isfile(base):
                result = base
            else:
                d = os.path.dirname(base)
                for cand in ("python.exe", "python3.exe"):
                    p = os.path.join(d, cand)
                    if os.path.isfile(p):
                        result = p
                        break

    if not result:
        for name in ("python.exe", "python3.exe", "python", "python3"):
            p = shutil.which(name)
            if not p:
                continue
            if os.path.basename(p).lower().startswith("pypacker"):
                continue
            try:
                r = subprocess.run(
                    [p, "-c", "import sys;print(sys.version_info[0])"],
                    capture_output=True, text=True, timeout=5,
                    env=env, **nowin)
                if r.returncode == 0 and r.stdout.strip() == "3":
                    result = p
                    break
            except Exception:
                continue

    if not result:
        for launcher in ("py", "py.exe"):
            p = shutil.which(launcher)
            if not p:
                continue
            try:
                r = subprocess.run(
                    [p, "-3", "-c",
                     "import sys;print(sys.version_info[0])"],
                    capture_output=True, text=True, timeout=5,
                    env=env, **nowin)
                if r.returncode == 0 and r.stdout.strip() == "3":
                    result = p
                    break
            except Exception:
                pass

    _PY_CACHE["path"] = result
    _PY_CACHE["checked"] = True
    return result


def probe_pyinstaller(py):
    if not py:
        return False, "未找到 Python 解释器"
    try:
        r = subprocess.run(
            [py, "-c",
             "import PyInstaller,sys;print(PyInstaller.__version__)"],
            capture_output=True, text=True, timeout=20,
            env=_clean_env(), **no_window_kwargs())
        if r.returncode == 0:
            return True, "PyInstaller " + r.stdout.strip()
        return False, (r.stderr or r.stdout).strip()[-200:]
    except Exception as e:
        return False, str(e)


def pip_install_pyinstaller(py):
    if not py:
        return False, "未找到 Python 解释器"
    try:
        r = subprocess.run(
            [py, "-m", "pip", "install", "pyinstaller"],
            capture_output=True, text=True,
            env=_clean_env(), **no_window_kwargs())
        if r.returncode == 0:
            return True, ""
        return False, r.stderr[-800:]
    except Exception as e:
        return False, str(e)