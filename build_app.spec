# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置 —— 小学一年级成语测试（电脑版）

用法（在工程目录下执行）：
    pyinstaller build_app.spec --noconfirm

产物： dist/成语学习助手/成语学习助手.exe  （整个文件夹一起拷贝走即可用）
"""

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ---------------------------------------------------------------------------
# 只读资源：中文字体目录 + 成语题库
#   打包后统一解压到程序内部的资源目录（运行时 _MEIPASS），由 main.py 的
#   BUNDLE_DIR 定位；字体和题库都不会因为换电脑而丢失。
# ---------------------------------------------------------------------------
datas = [
    ("fonts", "fonts"),          # fonts/zh_regular.ttf、fonts/zh_bold.ttf
    ("idiom.json", "."),         # 成语题库
]

# KivyMD 自带字体与主题数据
datas += collect_data_files("kivymd")

# ---------------------------------------------------------------------------
# 隐式依赖：语音朗读库与 KivyMD 子模块（静态分析扫不到，必须手动声明）
# ---------------------------------------------------------------------------
hiddenimports = [
    "pyttsx3",
    "pyttsx3.drivers",
    "pyttsx3.drivers.sapi5",     # Windows 语音引擎驱动
    "pyttsx3.drivers.dummy",
    "comtypes",
    "comtypes.client",
]
hiddenimports += collect_submodules("kivymd")

# 与界面无关、且体积较大的可选模块，排除以减小体积
# pkg_resources / setuptools：程序并未使用，留着反而会因新版 setuptools
#   缺少 appdirs 而在启动时报错，故整体排除。
excludes = [
    "tkinter",
    "matplotlib",
    "pkg_resources",
    "setuptools",
    "pip",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="IdiomApp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                   # Kivy DLLs may break after compression
    console=False,               # No black cmd window on launch
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="IdiomApp",
)
