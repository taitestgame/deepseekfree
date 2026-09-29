@echo off
chcp 65001 >nul
title PUSH CODE LEN GITHUB
cd /d "%~dp0"
echo =================================================================
echo   DANG PUSH KHO MA NGUON LEN GITHUB: taitestgame/deepseekfree
echo =================================================================
echo.
git add -A
git commit -m "Auto sync and update deepseekfree"
git push origin main
echo.
echo =================================================================
echo   HOAN TAT! Nhan phim bat ky de dong cua so...
echo =================================================================
pause >nul
