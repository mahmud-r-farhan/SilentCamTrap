@echo off
REM ============================================================
REM  SilentCamTrap Server - Windows Start Script
REM ============================================================
setlocal
cd /d "%~dp0"

echo [*] Checking Node.js...
node --version >nul 2>&1 || (echo [ERROR] Node.js not found. Install from https://nodejs.org && exit /b 1)

if not exist node_modules (
    echo [*] Installing npm dependencies...
    npm install
)

if not exist .env (
    if exist .env.example (
        echo [*] Creating .env from .env.example...
        copy .env.example .env >nul
        echo [!] IMPORTANT: Edit .env to set your credentials before first use!
    )
)

echo [*] Starting SilentCamTrap server...
node src/server.js

endlocal
