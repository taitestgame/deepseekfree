@echo off
chcp 65001 >nul
title EP TAO ACC MOI VA XAC MINH FULL - TOKEN HARBOR
cd /d "%~dp0"
echo =================================================================
echo   EP TAO TAI KHOAN MOI DU PHONG VA DO TOC DO BENCHMARK
echo =================================================================
echo.
python check_and_rotate.py --force
echo.
echo =================================================================
echo   HOAN TAT! Nhan phim bat ky de dong cua so...
echo =================================================================
pause >nul
