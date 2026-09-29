@echo off
chcp 65001 >nul
title CAI DAT TU DONG - DEEPSEEKFREE IDE VA KEY MANAGER
cd /d "%~dp0"

echo =================================================================
echo   🚀 CHUONG TRINH CAI DAT TU DONG: DEEPSEEKFREE (IDE + KEY)
echo =================================================================
echo.

:: 1. Kiem tra Python
echo [*] Buoc 1/4: Kiem tra moi truong Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] CHUA CAI DAT PYTHON!
    echo     Vui long tai va cai dat Python 3.10+ tai: https://www.python.org/downloads/
    echo     (Nho tich chon "Add python.exe to PATH" khi cai dat)
    pause
    exit /b 1
)
python -c "import sys; print(f'    -> Python da san sang: {sys.version.split()[0]}')"

:: 2. Cai dat thu vien Python cho tool Key
echo.
echo [*] Buoc 2/4: Cai dat thu vien Python cho Tool Key...
pip install -r key\requirements.txt
if %errorlevel% neq 0 (
    echo [!] Co the mot so goi can cai dat them, tiep tuc...
)

:: 3. Kiem tra Node.js & npm
echo.
echo [*] Buoc 3/4: Kiem tra moi truong Node.js...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] CHUA CAI DAT NODE.JS!
    echo     Vui long tai va cai dat Node.js LTS tai: https://nodejs.org/
    pause
    exit /b 1
)
node -e "console.log('    -> Node.js da san sang: ' + process.version)"

:: 4. Thiet lap thu muc IDE va cai dat packages
echo.
echo [*] Buoc 4/4: Thiet lap IDE Halyard va ap dung ban va...
set "HALYARD_DIR=%USERPROFILE%\.halyard"
if not exist "%HALYARD_DIR%" mkdir "%HALYARD_DIR%"

copy /y "ide\package.json" "%HALYARD_DIR%\package.json" >nul

echo     -> Dang tai va cai dat packages IDE (npm install)...
cd /d "%HALYARD_DIR%"
call npm install
cd /d "%~dp0"

echo     -> Dang ap dung ban va (HACK CO LO, Browse C:\, Skill Filter)...
node "ide\apply_patches.js"

:: 5. Khoi tao Key ban dau
echo.
echo [*] Buoc cuoi: Khoi tao va kiem tra Key Token Harbor...
python "key\check_and_rotate.py"

echo.
echo =================================================================
echo   🎉 CAI DAT HOAN TAT 100%!
echo   👉 De su dung, chi can chay file: start.bat
echo =================================================================
pause
