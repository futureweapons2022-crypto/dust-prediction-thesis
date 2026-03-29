"""
ERA5 BULK download — pack maximum fields per request to minimize queue slots.
Run this ALONGSIDE the existing submit_all_era5.py (which can be killed).
Saves to a separate folder to avoid conflicts, then merge later.

Field budget: 120,000 max per request
- Pressure-levels: 5 vars × 3 levels × 4 times × 5 years = 109,560 fields → 2 requests
- Single-levels:  19 vars × 1 level × 4 times × 4 years = 111,036 fields → 3 requests
Total: 5 requests instead of 720
"""

import cdsapi
import os
import time

CDS_URL = "https://cds.climate.copernicus.eu/api"
OUTPUT_DIR = r"C:\Users\LENOVO\Desktop\THESIS\data\era5_bulk"
AREA = [34, 45, 20, 60]
HOURS_6H = ["00:00", "06:00", "12:00", "18:00"]

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


def make_days_and_months(year_start, year_end):
    """Generate year, month, day lists for the API."""
    years = [str(y) for y in range(year_start, year_end + 1)]
    months = [f"{m:02d}" for m in range(1, 13)]
    days = [f"{d:02d}" for d in range(1, 32)]
    return years, months, days


def download_pressure_bulk(year_start, year_end):
    """Download ALL pressure-level vars for a multi-year range in ONE request."""
    label = f"PL_{year_start}-{year_end}"
    filename = f"era5_pressure_levels_{year_start}_{year_end}.nc"
    filepath = os.path.join(OUTPUT_DIR, filename)

    if os.path.exists(filepath):
        print(f"[SKIP] {label} — already exists", flush=True)
        return

    years, months, days = make_days_and_months(year_start, year_end)

    # Field count check
    n_days = sum(366 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 365
                 for y in range(year_start, year_end + 1))
    fields = len(PRESSURE_LEVEL_VARS) * len(PRESSURE_LEVELS) * 4 * n_days
    print(f"[SUBMIT] {label} — {fields:,} fields, {len(years)} years", flush=True)

    client = cdsapi.Client(url=CDS_URL, timeout=86400, retry_max=3, quiet=True)
    t0 = time.time()

    try:
        client.retrieve("reanalysis-era5-pressure-levels", {
            "product_type": "reanalysis",
            "variable": PRESSURE_LEVEL_VARS,
            "pressure_level": PRESSURE_LEVELS,
            "year": years,
            "month": months,
            "day": days,
            "time": HOURS_6H,
            "area": AREA,
            "data_format": "netcdf",
        }, filepath)
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        elapsed = (time.time() - t0) / 60
        print(f"[DONE] {label} — {size_mb:.1f} MB in {elapsed:.0f} min", flush=True)
    except Exception as e:
        elapsed = (time.time() - t0) / 60
        print(f"[FAIL] {label} after {elapsed:.0f} min — {e}", flush=True)
        if os.path.exists(filepath):
            os.remove(filepath)


def download_single_bulk(year_start, year_end):
    """Download ALL single-level vars for a multi-year range in ONE request."""
    label = f"SL_{year_start}-{year_end}"
    filename = f"era5_single_levels_{year_start}_{year_end}.nc"
    filepath = os.path.join(OUTPUT_DIR, filename)

    if os.path.exists(filepath):
        print(f"[SKIP] {label} — already exists", flush=True)
        return

    years, months, days = make_days_and_months(year_start, year_end)

    n_days = sum(366 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 365
                 for y in range(year_start, year_end + 1))
    fields = len(SINGLE_LEVEL_VARS) * 4 * n_days
    print(f"[SUBMIT] {label} — {fields:,} fields, {len(years)} years", flush=True)

    client = cdsapi.Client(url=CDS_URL, timeout=86400, retry_max=3, quiet=True)
    t0 = time.time()

    try:
        client.retrieve("reanalysis-era5-single-levels", {
            "product_type": "reanalysis",
            "variable": SINGLE_LEVEL_VARS,
            "year": years,
            "month": months,
            "day": days,
            "time": HOURS_6H,
            "area": AREA,
            "data_format": "netcdf",
        }, filepath)
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        elapsed = (time.time() - t0) / 60
        print(f"[DONE] {label} — {size_mb:.1f} MB in {elapsed:.0f} min", flush=True)
    except Exception as e:
        elapsed = (time.time() - t0) / 60
        print(f"[FAIL] {label} after {elapsed:.0f} min — {e}", flush=True)
        if os.path.exists(filepath):
            os.remove(filepath)


# === Submit all 5 requests ===
# Using ThreadPoolExecutor to submit all at once so they queue on CDS simultaneously

from concurrent.futures import ThreadPoolExecutor, as_completed

tasks = [
    # 1 year each — CDS "cost limit" rejected multi-year requests
    ("pressure", 2015, 2015),
    ("pressure", 2016, 2016),
    ("pressure", 2017, 2017),
    ("pressure", 2018, 2018),
    ("pressure", 2019, 2019),
    ("pressure", 2020, 2020),
    ("pressure", 2021, 2021),
    ("pressure", 2022, 2022),
    ("pressure", 2023, 2023),
    ("pressure", 2024, 2024),
    ("single", 2015, 2015),
    ("single", 2016, 2016),
    ("single", 2017, 2017),
    ("single", 2018, 2018),
    ("single", 2019, 2019),
    ("single", 2020, 2020),
    ("single", 2021, 2021),
    ("single", 2022, 2022),
    ("single", 2023, 2023),
    ("single", 2024, 2024),
]

print(f"Submitting {len(tasks)} bulk ERA5 requests...", flush=True)
print(f"Output: {OUTPUT_DIR}", flush=True)
print("=" * 50, flush=True)

with ThreadPoolExecutor(max_workers=20) as executor:
    futures = {}
    for dtype, y1, y2 in tasks:
        if dtype == "pressure":
            f = executor.submit(download_pressure_bulk, y1, y2)
        else:
            f = executor.submit(download_single_bulk, y1, y2)
        futures[f] = f"{dtype}_{y1}-{y2}"

    for future in as_completed(futures):
        label = futures[future]
        try:
            future.result()
        except Exception as e:
            print(f"[ERROR] {label}: {e}", flush=True)

print("\n" + "=" * 50, flush=True)
print("All bulk requests completed or failed.", flush=True)
