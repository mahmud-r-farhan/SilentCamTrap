import cv2
import os
import time
from datetime import datetime

folder = "intruder_logs"
os.makedirs(folder, exist_ok=True)

cap = cv2.VideoCapture(0)
ret, frame = cap.read()

if ret:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(folder, f"intruder_{timestamp}.jpg")
    cv2.imwrite(filename, frame)

cap.release()
time.sleep(1)

# Shutdown Windows immediately
os.system("shutdown /s /t 0")
# Note: This script will shut down the computer immediately after capturing an image.
# Ensure you have saved all your work before running this script.
# If you want to test the script without shutting down, comment out the shutdown line.
# Follow for more: https://github.com/mahmud-r-farhan
