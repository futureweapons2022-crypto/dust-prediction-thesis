"""
ERA5 Optimized Download — combines all pressure-level vars per monthly request.
Reduces total from 720 requests to 240 (120 PL + 120 SL).

Field counts per request:
- Pressure-levels: 5 vars × 3 levels × ~30 days × 4 times ≈ 1,800 fields (safe)
- Single-levels:  19 vars × ~30 days × 4 times ≈ 2,280 fields (already proven to work)
"""

import cdsapi
import calendar
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

CDS_URL = "https://cds.climate.copernicus.eu/api"
OUTPUT_DIR = r"C:\Users\LENOVO\Desktop\THESIS\data\era5"
AREA = [34, 45, 20, 60]
HOURS_6H = ["00:00", "06:00", "12:00", "18:00"]
MAX_WORKERS = 2  # CDS is congested — reduce to avoid dropped connections

SINGLE_LEVEL_VARS = [
    "10m_u_component_of_wind", "10m_v_component_of_wind", "instantaneous_10m_wind_gust",
    "2m_temperature", "skin_temperature",
    "2m_dewpoint_temperature", "total_precipitation", "evaporation", "total_column_water_vapour",
    "boundary_layer_height", "convective_available_potential_energy", "surface_pressure",
    "volumetric_soil_water_layer_1",
    "surface_solar_radiation_downwards", "surface_thermal_radiation_downwards",
    "low_cloud_cover", "high_cloud_cover",
    "leaf_area_index_low_vegetation", "forecast_albedo",
]

PRESSURE_LEVEL_VARS = [
    "geopotential", "u_component_of_wind", "v_component_of_wind",
    "temperature", "relative_humidity",
]
PRESSURE_LEVELS = ["500", "700", "850"]

# Individual PL var short names (for checking old files)
PL_VAR_SHORTS = [v.split("_")[0] for v in PRESSURE_LEVEL_VARS]

os.makedirs(OUTPUT_DIR, exist_ok=True)


def pl_already_done(year, month):
    """Check if pressure-level data exists (combined OR all 5 individual files)."""
    combined = os.path.join(OUTPUT_DIR, f"era5_pl_all_{year}{month:02d}.nc")
    if os.path.exists(combined):
        return True
    # Check if all 5 individual var files exist (from old script)
    individual = all(
        os.path.exists(os.path.join(OUTPUT_DIR, f"era5_pl_{vs}_{year}{month:02d}.nc"))
        for vs in PL_VAR_SHORTS
    )
    return individual


def download_pressure_all(year, month):
    """Download ALL pressure-level vars for one month in ONE request."""
    label = f"PL-{year}-{month:02d}"

    if pl_already_done(year, month):
        return (label, "skip", 0)

    filename = f"era5_pl_all_{year}{month:02d}.nc"
    filepath = os.path.join(OUTPUT_DIR, filename)

    num_days = calendar.monthrange(year, month)[1]
    fields = len(PRESSURE_LEVEL_VARS) * len(PRESSURE_LEVELS) * num_days * 4
    client = cdsapi.Client(url=CDS_URL, timeout=86400, retry_max=3, quiet=True)
    t0 = time.time()

    try:
        client.retrieve("reanalysis-era5-pressure-levels", {
            "product_type": "reanalysis",
            "variable": PRESSURE_LEVEL_VARS,
            "pressure_level": PRESSURE_LEVELS,
            "year": str(year),
            "month": f"{month:02d}",
            "day": [f"{d:02d}" for d in range(1, num_days + 1)],
            "time": HOURS_6H,
            "area": AREA,
            "data_format": "netcdf",
        }, filepath)
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        elapsed = (time.time() - t0) / 60
        return (label, "done", size_mb)
    except Exception as e:
        elapsed = (time.time() - t0) / 60
        if os.path.exists(filepath):
            os.remove(filepath)
        return (label, f"FAIL ({elapsed:.0f}min): {e}", 0)


def download_single_levels(year, month):
    """Download single-level variables for one month (6-hourly)."""
    label = f"SL-{year}-{month:02d}"
    filename = f"era5_single_{year}{month:02d}.nc"
    filepath = os.path.join(OUTPUT_DIR, filename)

    if os.path.exists(filepath):
        return (label, "skip", 0)

    num_days = calendar.monthrange(year, month)[1]
    client = cdsapi.Client(url=CDS_URL, timeout=86400, retry_max=3, quiet=True)
    t0 = time.time()

    try:
        client.retrieve("reanalysis-era5-single-levels", {
            "product_type": "reanalysis",
            "variable": SINGLE_LEVEL_VARS,
            "year": str(year),
            "month": f"{month:02d}",
            "day": [f"{d:02d}" for d in range(1, num_days + 1)],
            "time": HOURS_6H,
            "area": AREA,
            "data_format": "netcdf",
        }, filepath)
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        elapsed = (time.time() - t0) / 60
        return (label, "done", size_mb)
    except Exception as e:
        elapsed = (time.time() - t0) / 60
        if os.path.exists(filepath):
            os.remove(filepath)
        return (label, f"FAIL ({elapsed:.0f}min): {e}", 0)


# --- Build task list ---
tasks = []
for year in range(2015, 2025):
    for month in range(1, 13):
        if not pl_already_done(year, month):
            tasks.append(("pressure", year, month))
        sl_file = os.path.join(OUTPUT_DIR, f"era5_single_{year}{month:02d}.nc")
        if not os.path.exists(sl_file):
            tasks.append(("single", year, month))

print(f"ERA5 Optimized Download", flush=True)
print(f"={'='*49}", flush=True)
print(f"Total requests to submit: {len(tasks)}", flush=True)
print(f"  Pressure-level (combined): {sum(1 for t in tasks if t[0]=='pressure')}", flush=True)
print(f"  Single-level:              {sum(1 for t in tasks if t[0]=='single')}", flush=True)
print(f"Max workers: {MAX_WORKERS}", flush=True)
print(f"Output: {OUTPUT_DIR}", flush=True)
print(f"={'='*49}\n", flush=True)

done = 0
failed = 0
skipped = 0
total_mb = 0


def run_task(task):
    dtype, year, month = task
    if dtype == "pressure":
        return download_pressure_all(year, month)
    else:
        return download_single_levels(year, month)


with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(run_task, t): t for t in tasks}

    for future in as_completed(futures):
        label, status, size_mb = future.result()
        progress = done + failed + skipped + 1
        if status == "skip":
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
