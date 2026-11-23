@echo off
setlocal
cd /d "%~dp0"
if not exist .venv (
  py -3 -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r desktop_requirements.txt
pyinstaller --noconfirm --clean --onefile --windowed --name MergeAIDesktopBridge desktop_bridge.py
echo.
echo Build complete: dist\MergeAIDesktopBridge.exe
pause
