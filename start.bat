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

:: Nap Key vao bien moi truong cua phien khoi dong
if exist "key\key_acc1.txt" (
    for /f "usebackq eol=# delims=" %%k in ("key\key_acc1.txt") do (
        set "HALYARD_API_KEY=%%k"
        set "TOKENHARBOR_API_KEY=%%k"
    )
)

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

echo     -> May chu IDE khoi dong tai: http://127.0.0.1:3080
echo     -> Tu dong mo trinh duyet sau 3 giay...

start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:3080"

echo.
echo =================================================================
echo   ✅ MAY CHU IDE HALYARD DANG HOAT DONG!
echo   💡 Cua so nay duy tri may chu IDE tren cong 3080.
echo   (Nhan Ctrl+C de dung may chu hoac dong cua so nay)
echo =================================================================
echo.
node "%HALYARD_BIN%" verbose
