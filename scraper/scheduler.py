"""
Scheduler for controlling LinkedIn scraper execution based on timezone.
Runs:
- Weekdays: Hourly between 08:00–19:00 in CET, EST, and PST
- Weekends: Twice daily at 09:00 and 16:00 local time
"""

import asyncio
import pytz
from datetime import datetime
import time
import subprocess

# Define when to run
WEEKDAY_HOURS = list(range(8, 20))
WEEKEND_RUN_HOURS = [9, 16]
ZONES = ["Europe/Berlin", "America/New_York", "America/Los_Angeles"]

def should_run_now():
    now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
    for zone in ZONES:
        now_local = now_utc.astimezone(pytz.timezone(zone))
        weekday = now_local.weekday()
        hour = now_local.hour

        if weekday < 5 and hour in WEEKDAY_HOURS:
            print(f"[✓] Match: {zone} {hour}:00 (Weekday)")
            return True
        elif weekday >= 5 and hour in WEEKEND_RUN_HOURS:
            print(f"[✓] Match: {zone} {hour}:00 (Weekend)")
            return True
    return False

async def main_loop():
    while True:
        if should_run_now():
            print("[🔁] Running scraper...")
            subprocess.run(["python", "scraper/linkedin_scraper.py"])
        else:
            print("[⏳] Outside run window. Sleeping...")

        await asyncio.sleep(3600)  # Check again in 1 hour

if __name__ == "__main__":
    asyncio.run(main_loop())
