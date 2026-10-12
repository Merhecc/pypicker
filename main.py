# -*- coding: utf-8 -*-
"""PyPacker 启动入口"""
import sys
import os

# 把项目根目录加入 sys.path，支持直接双击 / python main.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pypacker.app import run


if __name__ == "__main__":
    run()