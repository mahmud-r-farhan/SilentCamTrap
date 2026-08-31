#!/usr/bin/env bash
# ============================================================
#  SilentCamTrap - Linux/macOS PyInstaller Build Script
#  Output: dist/SteamGame  (windowless, game icon)
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[*] Checking Python 3..."
python3 --version || { echo "[ERROR] Python3 not found"; exit 1; }

echo "[*] Installing / upgrading requirements..."
pip3 install -r requirements.txt --quiet

echo "[*] Cleaning previous build artifacts..."
rm -rf build dist __pycache__

echo "[*] Building executable with PyInstaller..."
pyinstaller --clean silentcamtrap.spec

echo ""
echo "[OK] Build succeeded!"
echo "     Output: dist/SteamGame"
echo ""
echo "Deploy dist/SteamGame + config.json to the target machine."
