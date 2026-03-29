"""
CAMS Supplementary Download — handles years 2020-2024.
Runs alongside submit_all_cams.py (which handles 2015-2019).
"""

import cdsapi
import calendar
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ADS_URL = "https://ads.atmosphere.copernicus.eu/api"
OUTPUT_DIR = r"C:\Users\LENOVO\Desktop\THESIS\data\cams"
TEMP_DIR = os.path.join(OUTPUT_DIR, "temp")
DATASET = "cams-global-atmospheric-composition-forecasts"

AREA = [34, 45, 20, 60]
LEADTIMES = [str(h) for h in range(0, 121, 3)]
MAX_WORKERS = 2

os.makedirs(TEMP_DIR, exist_ok=True)


def download_month(year, month):
    """Download a full month in ONE request."""
    label = f"{year}-{month:02d}"
    merged = os.path.join(OUTPUT_DIR, f"cams_duaod550_{year}{month:02d}.nc")
    if os.path.exists(merged):
        return (label, "skip-merged", 0)

    # Also check if all windows for this month already exist in temp
    num_days = calendar.monthrange(year, month)[1]
    windows = []
    d = 1
    while d <= num_days:
        d_end = min(d + 9, num_days)
        win_path = os.path.join(TEMP_DIR, f"cams_{year}{month:02d}_d{d:02d}-{d_end:02d}.nc")
        windows.append(win_path)
        d = d_end + 1
    if all(os.path.exists(w) for w in windows):
        return (label, "skip-temp", 0)

    # Download each window
    d = 1
    month_mb = 0
    while d <= num_days:
        d_end = min(d + 9, num_days)
        win_name = f"cams_{year}{month:02d}_d{d:02d}-{d_end:02d}.nc"
        win_path = os.path.join(TEMP_DIR, win_name)

        if os.path.exists(win_path):
            d = d_end + 1
            continue

        date_str = f"{year}-{month:02d}-{d:02d}/{year}-{month:02d}-{d_end:02d}"
        request = {
            "type": "forecast",
            "variable": "dust_aerosol_optical_depth_550nm",
            "date": date_str,
            "time": "00:00",
            "leadtime_hour": LEADTIMES,
            "area": AREA,
            "data_format": "netcdf",
        }

        client = cdsapi.Client(url=ADS_URL, timeout=1800, retry_max=5, quiet=True)
        try:
            client.retrieve(DATASET, request, win_path)
            size_mb = os.path.getsize(win_path) / (1024 * 1024)
            month_mb += size_mb
        except Exception as e:
            if os.path.exists(win_path):
                os.remove(win_path)
            return (label, f"FAIL at d{d:02d}: {e}", month_mb)

        d = d_end + 1

    return (label, "done", month_mb)


# --- Build task list for 2020-2024 only ---
tasks = []
for year in range(2020, 2025):
    for month in range(1, 13):
        merged = os.path.join(OUTPUT_DIR, f"cams_duaod550_{year}{month:02d}.nc")
        if not os.path.exists(merged):
            tasks.append((year, month))

print(f"CAMS Supplement (2020-2024)", flush=True)
print(f"={'='*49}", flush=True)
print(f"Months to download: {len(tasks)}", flush=True)
print(f"Max workers: {MAX_WORKERS}", flush=True)
print(f"={'='*49}\n", flush=True)

done = 0
failed = 0
skipped = 0
total_mb = 0

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(download_month, y, m): (y, m) for y, m in tasks}
    for future in as_completed(futures):
        label, status, size_mb = future.result()
        progress = done + failed + skipped + 1
        if "skip" in status:
            skipped += 1
        elif status == "done":
            done += 1
            total_mb += size_mb
            print(f"[{progress}/{len(tasks)}] [DONE] {label} — {size_mb:.1f} MB", flush=True)
        else:
            failed += 1
            print(f"[{progress}/{len(tasks)}] [FAIL] {label} — {status}", flush=True)

print(f"\n{'='*50}", flush=True)
print(f"Completed: {done} ({total_mb:.0f} MB)", flush=True)
print(f"Skipped:   {skipped}", flush=True)
print(f"Failed:    {failed}", flush=True)
print(f"{'='*50}", flush=True)
