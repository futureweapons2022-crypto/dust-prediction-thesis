"""
Submit ALL ERA5 requests in parallel — split into manageable chunks.
- Single-levels: 19 vars, full month, but only 6-hourly (00,06,12,18) to reduce size
  (can interpolate to hourly later if needed, or download hourly in smaller variable groups)
- Pressure-levels: split into individual variables per month (5 requests per month)
"""

import cdsapi
import calendar
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

CDS_URL = "https://cds.climate.copernicus.eu/api"
OUTPUT_DIR = r"C:\Users\LENOVO\Desktop\THESIS\data\era5"
AREA = [34, 45, 20, 60]
# 6-hourly to keep request size manageable
HOURS_6H = ["00:00", "06:00", "12:00", "18:00"]
MAX_WORKERS = 4

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

os.makedirs(OUTPUT_DIR, exist_ok=True)


def download_single_levels(year, month):
    """Download single-level variables for one month (6-hourly)."""
    label = f"{year}-{month:02d} single"
    filename = f"era5_single_{year}{month:02d}.nc"
    filepath = os.path.join(OUTPUT_DIR, filename)

    if os.path.exists(filepath):
        return (label, "skip", 0)

    num_days = calendar.monthrange(year, month)[1]
    client = cdsapi.Client(timeout=600, retry_max=2, quiet=True)

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
        return (label, "done", size_mb)
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return (label, f"FAIL: {e}", 0)


def download_pressure_var(year, month, variable):
    """Download one pressure-level variable for one month (6-hourly, 3 levels)."""
    var_short = variable.split("_")[0]  # geopotential, u, v, temperature, relative
    label = f"{year}-{month:02d} PL-{var_short}"
    filename = f"era5_pl_{var_short}_{year}{month:02d}.nc"
    filepath = os.path.join(OUTPUT_DIR, filename)

    if os.path.exists(filepath):
        return (label, "skip", 0)

    num_days = calendar.monthrange(year, month)[1]
    client = cdsapi.Client(timeout=600, retry_max=2, quiet=True)

    try:
        client.retrieve("reanalysis-era5-pressure-levels", {
            "product_type": "reanalysis",
            "variable": [variable],
            "pressure_level": PRESSURE_LEVELS,
            "year": str(year),
            "month": f"{month:02d}",
            "day": [f"{d:02d}" for d in range(1, num_days + 1)],
            "time": HOURS_6H,
            "area": AREA,
            "data_format": "netcdf",
        }, filepath)
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        return (label, "done", size_mb)
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return (label, f"FAIL: {e}", 0)


# --- Build task list ---
tasks = []

for year in range(2015, 2025):
    for month in range(1, 13):
        # Single levels: 1 request per month
        sl_file = os.path.join(OUTPUT_DIR, f"era5_single_{year}{month:02d}.nc")
        if not os.path.exists(sl_file):
            tasks.append(("single", year, month, None))

        # Pressure levels: 1 request per variable per month
        for var in PRESSURE_LEVEL_VARS:
            var_short = var.split("_")[0]
            pl_file = os.path.join(OUTPUT_DIR, f"era5_pl_{var_short}_{year}{month:02d}.nc")
            if not os.path.exists(pl_file):
                tasks.append(("pressure", year, month, var))

print(f"Total ERA5 requests to submit: {len(tasks)}", flush=True)
print(f"  Single-level months: {sum(1 for t in tasks if t[0]=='single')}", flush=True)
print(f"  Pressure-level files: {sum(1 for t in tasks if t[0]=='pressure')}", flush=True)
print(f"Launching {MAX_WORKERS} parallel workers...\n", flush=True)

done = 0
failed = 0
skipped = 0


def run_task(task):
    dtype, year, month, var = task
    if dtype == "single":
        return download_single_levels(year, month)
    else:
        return download_pressure_var(year, month, var)


with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(run_task, t): t for t in tasks}

    for future in as_completed(futures):
        label, status, size_mb = future.result()
        total = done + failed + skipped + 1
        if status == "skip":
            skipped += 1
        elif status == "done":
            done += 1
            print(f"[{total}/{len(tasks)}] [DONE] {label} — {size_mb:.1f} MB", flush=True)
        else:
            failed += 1
            print(f"[{total}/{len(tasks)}] [FAIL] {label} — {status}", flush=True)

print(f"\n{'='*50}", flush=True)
print(f"Completed: {done}", flush=True)
print(f"Skipped:   {skipped}", flush=True)
print(f"Failed:    {failed}", flush=True)
print(f"{'='*50}", flush=True)
