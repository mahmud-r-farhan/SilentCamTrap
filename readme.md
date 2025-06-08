# SilentCamTrap

SilentCamTrap is a personal security utility designed to discreetly capture an intruder's photo using the webcam and then shut down the Windows PC immediately. It is disguised as a harmless game executable (`PlayGame.exe`) to trick anyone who tries to open your computer without permission.

---

## How It Works

1. The user double-clicks the `PlayGame.exe` file, which looks like a normal game.
2. This executable is a small C program that silently launches a Python script in the background.
3. The Python script accesses the webcam, captures a photo without opening any preview window, and saves it to a predefined folder.
4. Immediately after capturing the image, the script shuts down the computer (`shutdown /s /t 0`).
5. The captured photo is saved with a timestamp in a folder (default is `intruder_logs`, but this can be customized).

---

## Why Use C and Python Together?

- **C** is used to create a lightweight, native Windows executable (`PlayGame.exe`). It runs fast and can be disguised as any program (like a game) without revealing any console windows or suspicious activity.
- **Python** is leveraged for its powerful and easy-to-use libraries, especially OpenCV, which handles webcam access and image capture with minimal code.
- By combining C and Python:
  - You get a seamless native-like executable interface.
  - Python handles the complex webcam capture and system commands.
  - The final experience is stealthy and effective.

---

## Setup & Usage

### Prerequisites
- Windows PC
- Python 3.x installed (for development/testing)
- GCC compiler (e.g., MinGW) installed (for compiling C)
- Python packages: OpenCV (`opencv-python`), PyInstaller

### Steps

1. **Clone or Download** the project files.

2. **Install Python dependencies**:

   ```bash
   pip install opencv-python pyinstaller

``

3.  **Compile the Python script** into an executable:
    
    ```bash
    pyinstaller --noconsole --onefile capture_shutdown.py
    
    ```
    
    This creates `capture_shutdown.exe` in the `dist` folder.
    
4.  **Move** `capture_shutdown.exe` to the main project folder.
    
5.  **Compile the C launcher**:
    
    ```bash
    gcc trap.c -o PlayGame.exe
    
    ```
    
6.  **Run `PlayGame.exe`** by double-clicking it.
    

----------

## Customization

-   Change the folder where photos are saved by editing the `folder` variable in `capture_shutdown.py`.
    
-   Use any folder path on your system, including external drives or hidden system directories.
    
-   Customize the icon of the executables for better disguise.
    

----------

## Security and Privacy

-   This tool is designed for personal use only.
    
-   The captured images are stored locally; no data is sent over the internet by default.
    
-   Always use responsibly and ensure compliance with local laws and privacy regulations.
    


----------

## Contact

For suggestions or help, contact:  dev@devplus.fun
