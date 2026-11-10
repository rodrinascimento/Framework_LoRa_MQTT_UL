@echo off
REM Gera dist\FrameworkLoRa.exe no Windows.
REM Requisitos: Python 3.10+ instalado e no PATH.
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python -m pytest -q tests\test_core.py || goto :erro
pyinstaller --noconfirm framework_lora.spec || goto :erro
echo.
echo Executavel gerado em dist\FrameworkLoRa.exe
pause
exit /b 0
:erro
echo Falha na geracao do executavel.
pause
exit /b 1
