#!/usr/bin/env python3
"""
Critter — 桌面宠物
入口：/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 main.py
"""
import sys
import os

# 确保模块根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.pet_window import DesktopPet

if __name__ == '__main__':
    DesktopPet().run()
