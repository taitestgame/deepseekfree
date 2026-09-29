@echo off
chcp 65001 >nul
title KHOI DONG DEEPSEEKFREE IDE
cd /d "%~dp0"

echo =================================================================
echo   🚀 DANG KHOI DONG DEEPSEEKFREE (IDE + KEY WATCHDOG)
echo =================================================================
echo.

:: 1. Kiem tra Quota va cap nhat key moi neu can
echo [*] Buoc 1/2: Kiem tra han muc Quota Token Harbor...
python "key\check_and_rotate.py"

:: 2. Khoi dong IDE Halyard
echo.
echo [*] Buoc 2/2: Khoi dong may chu IDE Halyard...
set "HALYARD_DIR=%USERPROFILE%\.halyard"
set "HALYARD_BIN=%HALYARD_DIR%\node_modules\@tokenharbor\halyard\bin\halyard.mjs"

if not exist "%HALYARD_BIN%" (
    echo [X] Khong tim thay ma nguon Halyard! Vui long chay setup.bat truoc.
    pause
    exit /b 1
)

echo     -> May chu IDE dang chay tren: http://127.0.0.1:3080
echo     -> Tu dong mo trinh duyet sau 2 giay...

start "" /B node "%HALYARD_BIN%" verbose
timeout /t 2 >nul
start http://127.0.0.1:3080

echo.
echo =================================================================
echo   ✅ IDE DA KHOI DONG HOAN TAT!
echo   💡 Cua so nay duy tri tien trinh chay ngam cua IDE.
echo   (Nhan Ctrl+C hoac dong cua so de tat IDE)
echo =================================================================
echo.
node "%HALYARD_BIN%" verbose
