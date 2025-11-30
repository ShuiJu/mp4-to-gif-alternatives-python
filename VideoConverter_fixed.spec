# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_all

# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 收集所有依赖的数据和隐藏导入
flask_datas, flask_binaries, flask_hiddenimports = collect_all('flask')
waitress_datas, waitress_binaries, waitress_hiddenimports = collect_all('waitress')
psutil_datas, psutil_binaries, psutil_hiddenimports = collect_all('psutil')
jinja2_datas, jinja2_binaries, jinja2_hiddenimports = collect_all('jinja2')
werkzeug_datas, werkzeug_binaries, werkzeug_hiddenimports = collect_all('werkzeug')

block_cipher = None

a = Analysis(
    ['main.py', 'webui.py', 'converter.py', 'utils.py'],  # 显式包含所有自定义模块
    pathex=[
        current_dir,  # 使用当前目录
        os.path.join(current_dir, 'templates'),
        os.path.join(current_dir, 'static')
    ],
    binaries=[],
    datas=[
        ('templates/*.html', 'templates'),
        ('static/*.css', 'static'),
        ('static/*.js', 'static')
    ] + flask_datas + waitress_datas + psutil_datas + jinja2_datas + werkzeug_datas,
    hiddenimports=[
        'webui',
        'converter', 
        'utils',
        'flask',
        'waitress', 
        'psutil',
        'jinja2',
        'werkzeug',
        'itsdangerous',
        'click',
        'markupsafe',
        'blinker',
        'flask.cli',
        'werkzeug.middleware.proxy_fix',
        'jinja2.ext',
        'subprocess',
        'threading',
        'queue',
        'json',
        'tempfile',
        'argparse'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='VideoConverter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
