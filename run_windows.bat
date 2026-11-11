@echo off
chcp 65001 >nul
title MathNote Studio - Khoi dong tren Windows
cd /d "%~dp0"

python -c "import PySide6, fitz" 2>nul
if %errorlevel% neq 0 (
    echo [MathNote Studio] Dang cai dat thu vien can thiet cho lan chay dau tien...
    pip install -r requirements.txt
)

start "" pythonw main.py
