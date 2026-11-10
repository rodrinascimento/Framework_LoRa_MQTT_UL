# -*- mode: python ; coding: utf-8 -*-
# Gera o executável único do Framework LoRa:
#     pyinstaller --noconfirm framework_lora.spec
# Saída: dist/FrameworkLoRa.exe (Windows) ou dist/FrameworkLoRa (Linux/macOS)

a = Analysis(
    ["app_framework_lora.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=["serial.tools.list_ports", "openpyxl", "matplotlib.backends.backend_qtagg"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
              "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtPdf",
              "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="FrameworkLoRa",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
