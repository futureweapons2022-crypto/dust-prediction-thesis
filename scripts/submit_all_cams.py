"""
Submit ALL CAMS requests in parallel using multiple workers.
Each worker submits a request and waits for it to complete + download.
Multiple workers = multiple requests in the ADS queue simultaneously.
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
MAX_WORKERS = 2  # Reduced — ADS drops connections at higher concurrency

os.makedirs(TEMP_DIR, exist_ok=True)


def download_window(year, month, d_start, d_end):
    """Download a single 10-day window. Returns (label, success, size_mb)."""
    label = f"{year}-{month:02d} d{d_start:02d}-{d_end:02d}"
    win_name = f"cams_{year}{month:02d}_d{d_start:02d}-{d_end:02d}.nc"
    win_path = os.path.join(TEMP_DIR, win_name)

    if os.path.exists(win_path):
        return (label, "skip", 0)

    date_str = f"{year}-{month:02d}-{d_start:02d}/{year}-{month:02d}-{d_end:02d}"
    request = {
        "type": "forecast",
        "variable": "dust_aerosol_optical_depth_550nm",
        "date": date_str,
        "time": "00:00",
        "leadtime_hour": LEADTIMES,
        "area": AREA,
        "data_format": "netcdf",
    }

    # Each thread gets its own client
    client = cdsapi.Client(url=ADS_URL, timeout=1800, retry_max=5, quiet=True)
    try:
        client.retrieve(DATASET, request, win_path)
        size_mb = os.path.getsize(win_path) / (1024 * 1024)
        return (label, "done", size_mb)
    except Exception as e:
        if os.path.exists(win_path):
            os.remove(win_path)
        return (label, f"FAIL: {e}", 0)


# --- Build list of all windows to download ---
tasks = []
for year in range(2015, 2025):
    for month in range(1, 13):
        # Skip if final merged file exists
        merged = os.path.join(OUTPUT_DIR, f"cams_duaod550_{year}{month:02d}.nc")
        if os.path.exists(merged):
            continue

        num_days = calendar.monthrange(year, month)[1]
        d = 1
        while d <= num_days:
            d_end = min(d + 9, num_days)
            tasks.append((year, month, d, d_end))
            d = d_end + 1

print(f"Total windows to download: {len(tasks)}", flush=True)
print(f"Already merged months: {120 - len(set((y,m) for y,m,_,_ in tasks))}", flush=True)
print(f"Launching {MAX_WORKERS} parallel workers...\n", flush=True)

# --- Submit all in parallel ---
done = 0
failed = 0
skipped = 0

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {
        executor.submit(download_window, y, m, ds, de): (y, m, ds, de)
        for y, m, ds, de in tasks
    }

    for future in as_completed(futures):
        label, status, size_mb = future.result()
        done_total = done + failed + skipped + 1
        if status == "skip":
            skipped += 1
        elif status == "done":
            done += 1
            print(f"[{done_total}/{len(tasks)}] [DONE] {label} — {size_mb:.1f} MB", flush=True)
        else:
            failed += 1
            print(f"[{done_total}/{len(tasks)}] [FAIL] {label} — {status}", flush=True)

print(f"\n{'='*50}", flush=True)
print(f"Completed: {done}", flush=True)
print(f"Skipped:   {skipped}", flush=True)
print(f"Failed:    {failed}", flush=True)
print(f"{'='*50}", flush=True)
