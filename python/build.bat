@echo off
REM ============================================================
REM  SilentCamTrap - Windows PyInstaller Build Script
REM  Output: dist\SteamGame.exe  (windowless, game icon)
REM ============================================================

setlocal

echo [*] Checking Python and pip...
python --version >nul 2>&1 || (echo [ERROR] Python not found && exit /b 1)

echo [*] Installing / upgrading requirements...
pip install -r requirements.txt --quiet

echo [*] Cleaning previous build artifacts...
if exist build  rmdir /s /q build
if exist dist   rmdir /s /q dist

echo [*] Building executable with PyInstaller...
pyinstaller --clean silentcamtrap.spec

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Build failed!
    exit /b 1
)

echo.
echo [OK] Build succeeded!
echo      Output: dist\SteamGame.exe
echo.
echo Deploy dist\SteamGame.exe + config.json to the target machine.

endlocal
