@echo off
chcp 65001 >nul
title KIEM TRA QUOTA VA TU DONG TAO ACC TOKEN HARBOR
cd /d "%~dp0"
echo =================================================================
echo   TOKEN HARBOR - AUTO QUOTA WATCHDOG VA ACCOUNT CREATOR
echo =================================================================
echo.
python check_and_rotate.py --threshold 30
echo.
echo =================================================================
echo   HOAN TAT! Nhan phim bat ky de dong cua so...
echo =================================================================
pause >nul
