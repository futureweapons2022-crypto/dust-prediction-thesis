"""
Download CAMS Global Dust AOD Forecasts — 10-Day Batches
=========================================================
Dataset: cams-global-atmospheric-composition-forecasts
Variable: duaod550 (Dust Aerosol Optical Depth at 550nm)
Domain: 20N–34N, 45E–60E (Arabian Gulf)
Period: 2015-01 to 2024-12
Lead times: 0–120h every 3h (41 steps)
Init time: 00:00 UTC
Grid: 0.4° x 0.4° (default)

Strategy: Split each month into ~10-day windows. Download each window,
then merge into one .nc file per month. Resumable at window level.

Auto-dismisses orphaned server-side jobs on interrupt/failure to prevent
queue blockage.
"""

import cdsapi
import calendar
import os
import time
import signal
import sys
import xarray as xr

# --- Configuration ---
ADS_URL = "https://ads.atmosphere.copernicus.eu/api"
OUTPUT_DIR = r"C:\Users\LENOVO\Desktop\THESIS\data\cams"
TEMP_DIR = os.path.join(OUTPUT_DIR, "temp")
DATASET = "cams-global-atmospheric-composition-forecasts"

START_YEAR = 2015
END_YEAR = 2024

AREA = [34, 45, 20, 60]  # N, W, S, E
LEADTIMES = [str(h) for h in range(0, 121, 3)]  # 41 steps

# --- Setup ---
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

client = cdsapi.Client(url=ADS_URL, timeout=300, retry_max=3)

# Track active request IDs so we can dismiss them on exit
active_request_ids = []


def dismiss_request(request_id):
    """Dismiss a server-side job so it doesn't block the queue."""
    try:
        r = client.session.delete(
            f"{ADS_URL}/retrieve/v1/jobs/{request_id}",
            headers={"PRIVATE-TOKEN": client.key},
        )
        if r.status_code == 200:
            print(f"  [CLEANUP] Dismissed server job {request_id[:12]}...", flush=True)
    except Exception:
        pass


def cleanup_and_exit(signum=None, frame=None):
    """On interrupt, dismiss any active server-side requests before exiting."""
    print("\n[INTERRUPT] Cleaning up active server requests...", flush=True)
    for rid in active_request_ids:
        dismiss_request(rid)
    print("[INTERRUPT] Done. Re-run script to resume.", flush=True)
    sys.exit(1)


# Register signal handlers for clean shutdown
signal.signal(signal.SIGINT, cleanup_and_exit)
signal.signal(signal.SIGTERM, cleanup_and_exit)


import logging

class RequestIDCapture(logging.Handler):
    """Logging handler that captures CAMS request IDs."""
    def emit(self, record):
        msg = record.getMessage()
        if "Request ID is" in msg:
            rid = msg.split("Request ID is ")[-1].strip()
            if rid not in active_request_ids:
                active_request_ids.append(rid)

# Attach to cdsapi logger
_handler = RequestIDCapture()
logging.getLogger("cdsapi").addHandler(_handler)


def retrieve_with_tracking(dataset, request, output_path):
    """Wrapper around client.retrieve that tracks request IDs for cleanup."""
    before = list(active_request_ids)
    client.retrieve(dataset, request, output_path)
    # Request completed — remove its ID from the active list
    new_ids = [r for r in active_request_ids if r not in before]
    for rid in new_ids:
        active_request_ids.remove(rid)


# --- Helper: split month into 10-day windows ---
def month_windows(year, month):
    """Return list of (start_day, end_day) tuples for ~10-day windows."""
    num_days = calendar.monthrange(year, month)[1]
    windows = []
    d = 1
    while d <= num_days:
        end = min(d + 9, num_days)
        windows.append((d, end))
        d = end + 1
    return windows


# --- Download loop ---
downloaded = 0
skipped = 0
failed = []

for year in range(START_YEAR, END_YEAR + 1):
    for month in range(1, 13):
        month_str = f"{year}-{month:02d}"
        filename = f"cams_duaod550_{year}{month:02d}.nc"
        filepath = os.path.join(OUTPUT_DIR, filename)

        if os.path.exists(filepath):
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            print(f"[SKIP] {month_str} — already exists ({size_mb:.1f} MB)", flush=True)
            skipped += 1
            continue

        windows = month_windows(year, month)
        num_days = calendar.monthrange(year, month)[1]
        print(f"[DOWN] {month_str} ({num_days} days, {len(windows)} windows)", flush=True)

        window_files = []
        all_ok = True

        for wi, (d_start, d_end) in enumerate(windows):
            win_name = f"cams_{year}{month:02d}_d{d_start:02d}-{d_end:02d}.nc"
            win_path = os.path.join(TEMP_DIR, win_name)
            window_files.append(win_path)

            if os.path.exists(win_path):
                print(f"  win {wi+1}/{len(windows)}: days {d_start}-{d_end} — already downloaded", flush=True)
                continue

            date_str = f"{year}-{month:02d}-{d_start:02d}/{year}-{month:02d}-{d_end:02d}"
            n_days = d_end - d_start + 1
            print(f"  win {wi+1}/{len(windows)}: days {d_start}-{d_end} ({n_days}d x 41 lt)...", flush=True)

            request = {
                "type": "forecast",
                "variable": "dust_aerosol_optical_depth_550nm",
                "date": date_str,
                "time": "00:00",
                "leadtime_hour": LEADTIMES,
                "area": AREA,
                "data_format": "netcdf",
            }

            max_retries = 3
            success = False
            for attempt in range(1, max_retries + 1):
                try:
                    retrieve_with_tracking(DATASET, request, win_path)
                    size_mb = os.path.getsize(win_path) / (1024 * 1024)
                    print(f"  win {wi+1}/{len(windows)}: done ({size_mb:.1f} MB)", flush=True)
                    success = True
                    break
                except Exception as e:
                    print(f"  win {wi+1}/{len(windows)}: attempt {attempt}/{max_retries} FAILED — {e}", flush=True)
                    if os.path.exists(win_path):
                        os.remove(win_path)
                    # Dismiss the failed request on the server
                    for rid in list(active_request_ids):
                        dismiss_request(rid)
                        active_request_ids.remove(rid)
                    if attempt < max_retries:
                        print(f"  retrying in 15s...", flush=True)
                        time.sleep(15)

            if not success:
                all_ok = False
                break

            time.sleep(3)

        # Merge windows if all succeeded
        if all_ok and all(os.path.exists(f) for f in window_files):
            try:
                print(f"  merging {len(windows)} windows...", flush=True)
                datasets = [xr.open_dataset(f) for f in window_files]
                merged = xr.concat(datasets, dim="forecast_reference_time")
                merged = merged.sortby("forecast_reference_time")
                merged.to_netcdf(filepath)
                for ds in datasets:
                    ds.close()
                merged.close()
                size_mb = os.path.getsize(filepath) / (1024 * 1024)
                print(f"[DONE] {month_str} — {size_mb:.1f} MB", flush=True)
                downloaded += 1

                # Clean up temp windows
                for f in window_files:
                    os.remove(f)

            except Exception as e:
                print(f"[FAIL] {month_str} merge — {e}", flush=True)
                failed.append(month_str)
                if os.path.exists(filepath):
                    os.remove(filepath)
        else:
            failed.append(month_str)

        time.sleep(3)

# --- Summary ---
print("\n" + "=" * 50, flush=True)
print(f"Download complete.", flush=True)
print(f"  Downloaded: {downloaded}", flush=True)
print(f"  Skipped:    {skipped}", flush=True)
print(f"  Failed:     {len(failed)}", flush=True)
if failed:
    print(f"  Failed months: {', '.join(failed)}", flush=True)
print("=" * 50, flush=True)
