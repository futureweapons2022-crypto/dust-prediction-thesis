"""
Merge CAMS 10-day temp windows into monthly files.
Run this periodically or after submit_all_cams.py finishes.
Only merges months where ALL windows are present.
"""

import os
import calendar
import xarray as xr

OUTPUT_DIR = r"C:\Users\LENOVO\Desktop\THESIS\data\cams"
TEMP_DIR = os.path.join(OUTPUT_DIR, "temp")

merged_count = 0
incomplete = 0

for year in range(2015, 2025):
    for month in range(1, 13):
        filename = f"cams_duaod550_{year}{month:02d}.nc"
        filepath = os.path.join(OUTPUT_DIR, filename)

        if os.path.exists(filepath):
            continue

        # Find all windows for this month
        num_days = calendar.monthrange(year, month)[1]
        windows = []
        d = 1
        while d <= num_days:
            d_end = min(d + 9, num_days)
            windows.append((d, d_end))
            d = d_end + 1

        # Check if all windows exist
        window_files = []
        all_present = True
        for d_start, d_end in windows:
            win_name = f"cams_{year}{month:02d}_d{d_start:02d}-{d_end:02d}.nc"
            win_path = os.path.join(TEMP_DIR, win_name)
            if os.path.exists(win_path):
                window_files.append(win_path)
            else:
                all_present = False
                break

        if not all_present:
            present = len(window_files)
            total = len(windows)
            if present > 0:
                print(f"[WAIT] {year}-{month:02d}: {present}/{total} windows", flush=True)
                incomplete += 1
            continue

        # Merge
        try:
            print(f"[MERGE] {year}-{month:02d} ({len(windows)} windows)...", end=" ", flush=True)
            datasets = [xr.open_dataset(f) for f in window_files]
            merged = xr.concat(datasets, dim="forecast_reference_time")
            merged = merged.sortby("forecast_reference_time")
            merged.to_netcdf(filepath)
            for ds in datasets:
                ds.close()
            merged.close()
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            print(f"{size_mb:.1f} MB", flush=True)
            merged_count += 1

            # Clean up temp files
            for f in window_files:
                os.remove(f)
        except Exception as e:
            print(f"FAILED — {e}", flush=True)
            if os.path.exists(filepath):
                os.remove(filepath)

print(f"\nMerged: {merged_count} months", flush=True)
print(f"Incomplete: {incomplete} months (still downloading)", flush=True)
