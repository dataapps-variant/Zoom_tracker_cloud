"""
==========================================================================
ZOOM AUTO TRACKER - Runs on Startup, Works Automatically
==========================================================================

HOW IT WORKS:
1. Add this script to Windows Startup folder (one-time setup)
2. It runs silently in background
3. Automatically starts webhook during meeting hours
4. Automatically generates report after meeting
5. You do NOTHING - just check reports folder!

SETUP (one-time):
1. Press Win+R, type: shell:startup
2. Create shortcut to this script in that folder
3. Done! It will auto-run when PC starts.
"""

import subprocess
import time
import os
import sys
from datetime import datetime, timedelta
import threading

# =============================================================================
# CONFIGURATION - EDIT THESE!
# =============================================================================

# Meeting schedule (24-hour format)
MEETING_START_HOUR = 9      # 9:00 AM
MEETING_START_MINUTE = 0
MEETING_END_HOUR = 13       # 1:00 PM (adjust to your meeting end time)
MEETING_END_MINUTE = 0

# Which days to run (0=Monday, 6=Sunday)
MEETING_DAYS = [0, 1, 2, 3, 4, 5]  # Monday to Saturday

# How many minutes before meeting to start webhook
START_BUFFER_MINUTES = 5

# How many hours after meeting to generate report (for QOS data availability)
REPORT_DELAY_HOURS = 2

# Paths
SCRIPT_DIR = r"C:\Users\shash\Downloads\zoom+tracker"
NGROK_PATH = os.path.join(SCRIPT_DIR, "ngrok.exe")
WEBHOOK_SCRIPT = os.path.join(SCRIPT_DIR, "zoom_webhook_listener.py")
REPORT_SCRIPT = os.path.join(SCRIPT_DIR, "generate_daily_report.py")

# =============================================================================
# DO NOT EDIT BELOW
# =============================================================================

class ZoomAutoTracker:
    def __init__(self):
        self.webhook_process = None
        self.ngrok_process = None
        self.is_running = False
        self.today_report_generated = False
        self.last_meeting_date = None

    def log(self, msg):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {msg}")

        # Also write to log file
        log_file = os.path.join(SCRIPT_DIR, "auto_tracker.log")
        with open(log_file, 'a') as f:
            f.write(f"[{timestamp}] {msg}\n")

    def is_meeting_day(self):
        return datetime.now().weekday() in MEETING_DAYS

    def is_meeting_time(self):
        now = datetime.now()
        start_time = now.replace(hour=MEETING_START_HOUR, minute=MEETING_START_MINUTE, second=0)
        end_time = now.replace(hour=MEETING_END_HOUR, minute=MEETING_END_MINUTE, second=0)

        # Start webhook a few minutes early
        start_time -= timedelta(minutes=START_BUFFER_MINUTES)

        return start_time <= now <= end_time

    def is_report_time(self):
        now = datetime.now()
        report_time = now.replace(hour=MEETING_END_HOUR + REPORT_DELAY_HOURS, minute=0, second=0)

        # Generate report in a 30-minute window after report_time
        return report_time <= now <= report_time + timedelta(minutes=30)

    def start_webhook(self):
        if self.is_running:
            return

        self.log("Starting webhook and ngrok...")

        try:
            # Start ngrok
            self.ngrok_process = subprocess.Popen(
                [NGROK_PATH, "http", "5000"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=SCRIPT_DIR
            )
            time.sleep(3)  # Wait for ngrok to start

            # Start webhook
            self.webhook_process = subprocess.Popen(
                [sys.executable, WEBHOOK_SCRIPT],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=SCRIPT_DIR
            )

            self.is_running = True
            self.last_meeting_date = datetime.now().date()
            self.log("Webhook started successfully!")

        except Exception as e:
            self.log(f"Error starting webhook: {e}")

    def stop_webhook(self):
        if not self.is_running:
            return

        self.log("Stopping webhook and ngrok...")

        try:
            if self.webhook_process:
                self.webhook_process.terminate()
                self.webhook_process = None

            if self.ngrok_process:
                self.ngrok_process.terminate()
                self.ngrok_process = None

            # Also kill any remaining processes
            os.system("taskkill /IM ngrok.exe /F >nul 2>&1")

            self.is_running = False
            self.log("Webhook stopped!")

        except Exception as e:
            self.log(f"Error stopping webhook: {e}")

    def generate_report(self):
        if self.today_report_generated:
            return

        if self.last_meeting_date != datetime.now().date():
            return  # No meeting today

        self.log("Generating daily report...")

        try:
            date_str = datetime.now().strftime("%Y-%m-%d")
            result = subprocess.run(
                [sys.executable, REPORT_SCRIPT, "--date", date_str],
                cwd=SCRIPT_DIR,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                self.log(f"Report generated for {date_str}!")
                self.today_report_generated = True
            else:
                self.log(f"Report generation failed: {result.stderr}")

        except Exception as e:
            self.log(f"Error generating report: {e}")

    def run(self):
        self.log("=" * 50)
        self.log("Zoom Auto Tracker Started")
        self.log(f"Meeting days: {MEETING_DAYS}")
        self.log(f"Meeting time: {MEETING_START_HOUR}:{MEETING_START_MINUTE:02d} - {MEETING_END_HOUR}:{MEETING_END_MINUTE:02d}")
        self.log("=" * 50)

        while True:
            try:
                # Reset daily flags at midnight
                if datetime.now().hour == 0 and datetime.now().minute == 0:
                    self.today_report_generated = False

                # Check if it's a meeting day
                if self.is_meeting_day():

                    # Start webhook during meeting time
                    if self.is_meeting_time():
                        if not self.is_running:
                            self.start_webhook()
                    else:
                        if self.is_running:
                            self.stop_webhook()

                    # Generate report after meeting
                    if self.is_report_time():
                        self.generate_report()

                # Sleep for 1 minute before checking again
                time.sleep(60)

            except KeyboardInterrupt:
                self.log("Shutting down...")
                self.stop_webhook()
                break
            except Exception as e:
                self.log(f"Error: {e}")
                time.sleep(60)


if __name__ == "__main__":
    tracker = ZoomAutoTracker()
    tracker.run()
