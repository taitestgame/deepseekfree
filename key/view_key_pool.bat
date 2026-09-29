@echo off
chcp 65001 >nul
title KHO LUU TRU KEY & CHU KY RESET 7 NGAY
cd /d "%~dp0"
python "check_and_rotate.py" --pool
echo.
echo Nhan phim bat ky de dong cua so...
pause >nul
