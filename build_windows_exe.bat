@echo off
chcp 65001 >nul
title MathNote Studio - Dong goi file .EXE doc lap cho Windows
cd /d "%~dp0"

echo [1/2] Cai dat PyInstaller va cac thu vien...
pip install -r requirements.txt pyinstaller

echo [2/2] Dang dong goi MathNoteStudio.exe...
pyinstaller --noconfirm --windowed --onefile --name "MathNoteStudio" --add-data "assets;assets" main.py

echo.
echo Hoan tat! File chay doc lap nam tai: dist\MathNoteStudio.exe
pause
