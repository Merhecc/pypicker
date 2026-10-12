# -*- coding: utf-8 -*-
"""配置文件的读写"""
import json
import os


def load_config(path):
    """读取 JSON 配置，返回 dict；失败抛异常。"""
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(path, data):
    """写入 JSON 配置，返回 True/False。"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False