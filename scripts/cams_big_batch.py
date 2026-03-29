"""
CAMS Big Batch — Download dust AOD in 6-month chunks instead of 10-day windows.
Same variable, same area, same leadtimes — just bigger date ranges.
"""

import cdsapi
import os
import time

ADS_URL = "https://ads.atmosphere.copernicus.eu/api"
OUTPUT_DIR = r"C:\Users\LENOVO\Desktop\THESIS\data\cams"
AREA = [34, 45, 20, 60]
LEADTIMES = [str(h) for h in range(0, 121, 3)]  # 0 to 120h, every 3h = 41 steps

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Build jobs: 6-month chunks from 2015 to 2024
JOBS = []
for year in range(2015, 2025):
    JOBS.append((f"CAMS {year} H1 (Jan-Jun)", f"{year}-01-01/{year}-06-30", f"cams_duaod550_{year}h1.nc"))
    JOBS.append((f"CAMS {year} H2 (Jul-Dec)", f"{year}-07-01/{year}-12-31", f"cams_duaod550_{year}h2.nc"))


def run_job(label, date_range, filename):
    filepath = os.path.join(OUTPUT_DIR, filename)

    if os.path.exists(filepath):
        print(f"[SKIP] {label} — already exists ({os.path.getsize(filepath)/(1024*1024):.1f} MB)", flush=True)
        return

    print(f"\n[START] {label} — {date_range}", flush=True)
    client = cdsapi.Client(url=ADS_URL, timeout=86400, retry_max=5, quiet=False)
    t0 = time.time()

    try:
        client.retrieve("cams-global-atmospheric-composition-forecasts", {
            "type": "forecast",
            "variable": "dust_aerosol_optical_depth_550nm",
            "date": date_range,
            "time": "00:00",
            "leadtime_hour": LEADTIMES,
            "area": AREA,
            "data_format": "netcdf",
        }, filepath)
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        elapsed = (time.time() - t0) / 60
        print(f"[DONE] {label} — {size_mb:.1f} MB in {elapsed:.0f} min", flush=True)
    except Exception as e:
        elapsed = (time.time() - t0) / 60
        print(f"[FAIL] {label} — {e} ({elapsed:.0f} min)", flush=True)
        if os.path.exists(filepath):
            os.remove(filepath)


if __name__ == "__main__":
    print(f"CAMS Big Batch Download", flush=True)
    print(f"Jobs: {len(JOBS)} (6-month chunks)", flush=True)
    print(f"Output: {OUTPUT_DIR}", flush=True)
    print(f"{'='*60}\n", flush=True)

    for job in JOBS:
        label, date_range, filename = job
        run_job(label, date_range, filename)

    print(f"\n{'='*60}", flush=True)
    print("All jobs complete.", flush=True)
