#!/usr/bin/env bash
# ============================================================
#  SilentCamTrap Server - Linux/macOS Start Script
# ============================================================

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[*] Checking Node.js..."
node --version || { echo "[ERROR] Node.js not found. Install from https://nodejs.org"; exit 1; }

if [ ! -d "node_modules" ]; then
    echo "[*] Installing npm dependencies..."
    npm install
fi

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "[*] Creating .env from .env.example..."
        cp .env.example .env
        echo "[!] IMPORTANT: Edit .env to set your credentials before first use!"
    fi
fi

echo "[*] Starting SilentCamTrap server..."
exec node src/server.js
