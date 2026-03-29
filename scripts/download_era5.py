"""
Download ERA5 Reanalysis for Meta-Model Features — Monthly Batches
===================================================================
Two datasets:
  1. reanalysis-era5-single-levels (surface + column variables)
  2. reanalysis-era5-pressure-levels (850, 700, 500 hPa)

Domain: 20N–34N, 45E–60E (Arabian Gulf)
Period: 2015-01 to 2024-12
Temporal: Hourly (all 24 hours) — needed for matching with AERONET/CAMS
Grid: 0.25° x 0.25° (ERA5 native)

Uses CDS endpoint (not ADS). Same API key from ~/.cdsapirc.
Saves one .nc file per month per dataset type. Resumable.
Auto-dismisses orphaned server jobs on interrupt.
"""

import cdsapi
import calendar
import os
import time
import signal
import sys
import logging

# --- Configuration ---
CDS_URL = "https://cds.climate.copernicus.eu/api"
OUTPUT_DIR = r"C:\Users\LENOVO\Desktop\THESIS\data\era5"

START_YEAR = 2015
END_YEAR = 2024

# Study domain: N, W, S, E
AREA = [34, 45, 20, 60]

# All hours — needed for AERONET temporal matching
HOURS = [f"{h:02d}:00" for h in range(24)]

# =========================================================
# SINGLE-LEVEL VARIABLES (17 variables)
# =========================================================
SINGLE_LEVEL_VARS = [
    # Wind
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "instantaneous_10m_wind_gust",
    # Thermal
    "2m_temperature",
    "skin_temperature",
    # Moisture
    "2m_dewpoint_temperature",
    "total_precipitation",
    "evaporation",
    "total_column_water_vapour",
    # Stability / Synoptic
    "boundary_layer_height",
    "convective_available_potential_energy",
    "surface_pressure",
    # Soil
    "volumetric_soil_water_layer_1",
    # Radiation / Cloud
    "surface_solar_radiation_downwards",
    "surface_thermal_radiation_downwards",
    "low_cloud_cover",
    "high_cloud_cover",
    # Land surface
    "leaf_area_index_low_vegetation",
    "forecast_albedo",
]

# =========================================================
# PRESSURE-LEVEL VARIABLES (4 vars x 3 levels = 12 fields)
# =========================================================
PRESSURE_LEVEL_VARS = [
    "geopotential",
    "u_component_of_wind",
    "v_component_of_wind",
    "temperature",
    "relative_humidity",
]

PRESSURE_LEVELS = ["500", "700", "850"]

# --- Setup ---
os.makedirs(OUTPUT_DIR, exist_ok=True)

client = cdsapi.Client(timeout=600, retry_max=3)

# Track active request IDs for cleanup
active_request_ids = []


class RequestIDCapture(logging.Handler):
    def emit(self, record):
        msg = record.getMessage()
        if "Request ID is" in msg:
            rid = msg.split("Request ID is ")[-1].strip()
            if rid not in active_request_ids:
                active_request_ids.append(rid)


logging.getLogger("cdsapi").addHandler(RequestIDCapture())


def dismiss_request(request_id):
    try:
        r = client.session.delete(
            f"{CDS_URL}/retrieve/v1/jobs/{request_id}",
            headers={"PRIVATE-TOKEN": client.key},
        )
        if r.status_code == 200:
            print(f"  [CLEANUP] Dismissed {request_id[:12]}...", flush=True)
    except Exception:
        pass


def cleanup_and_exit(signum=None, frame=None):
    print("\n[INTERRUPT] Cleaning up active server requests...", flush=True)
    for rid in active_request_ids:
        dismiss_request(rid)
    print("[INTERRUPT] Done. Re-run script to resume.", flush=True)
    sys.exit(1)


signal.signal(signal.SIGINT, cleanup_and_exit)
signal.signal(signal.SIGTERM, cleanup_and_exit)


def safe_retrieve(dataset, request, output_path, label=""):
    """Download with retry and auto-cleanup of failed server jobs."""
    before = list(active_request_ids)
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            client.retrieve(dataset, request, output_path)
            # Success — remove from tracking
            new_ids = [r for r in active_request_ids if r not in before]
            for rid in new_ids:
                active_request_ids.remove(rid)
            return True
        except Exception as e:
            print(f"  {label} attempt {attempt}/{max_retries} FAILED — {e}", flush=True)
            if os.path.exists(output_path):
                os.remove(output_path)
            # Dismiss failed server-side jobs
            new_ids = [r for r in active_request_ids if r not in before]
            for rid in new_ids:
                dismiss_request(rid)
                active_request_ids.remove(rid)
            if attempt < max_retries:
                print(f"  retrying in 15s...", flush=True)
                time.sleep(15)
    return False


# --- Download loop ---
downloaded = 0
skipped = 0
failed = []

for year in range(START_YEAR, END_YEAR + 1):
    for month in range(1, 13):
        month_str = f"{year}-{month:02d}"
        num_days = calendar.monthrange(year, month)[1]
        days = [f"{d:02d}" for d in range(1, num_days + 1)]

        # ---- Single levels ----
        sl_file = f"era5_single_{year}{month:02d}.nc"
        sl_path = os.path.join(OUTPUT_DIR, sl_file)

        if os.path.exists(sl_path):
            size_mb = os.path.getsize(sl_path) / (1024 * 1024)
            print(f"[SKIP] {month_str} single-levels — exists ({size_mb:.1f} MB)", flush=True)
        else:
            print(f"[DOWN] {month_str} single-levels ({len(SINGLE_LEVEL_VARS)} vars, {num_days} days)...", flush=True)

            request_sl = {
                "product_type": "reanalysis",
                "variable": SINGLE_LEVEL_VARS,
                "year": str(year),
                "month": f"{month:02d}",
                "day": days,
                "time": HOURS,
                "area": AREA,
                "data_format": "netcdf",
            }

            ok = safe_retrieve(
                "reanalysis-era5-single-levels",
                request_sl,
                sl_path,
                label=f"{month_str} SL",
            )
            if ok:
                size_mb = os.path.getsize(sl_path) / (1024 * 1024)
                print(f"[DONE] {month_str} single-levels — {size_mb:.1f} MB", flush=True)
                downloaded += 1
            else:
                failed.append(f"{month_str}-SL")

            time.sleep(3)

        # ---- Pressure levels ----
        pl_file = f"era5_pressure_{year}{month:02d}.nc"
        pl_path = os.path.join(OUTPUT_DIR, pl_file)

        if os.path.exists(pl_path):
            size_mb = os.path.getsize(pl_path) / (1024 * 1024)
            print(f"[SKIP] {month_str} pressure-levels — exists ({size_mb:.1f} MB)", flush=True)
        else:
            print(f"[DOWN] {month_str} pressure-levels ({len(PRESSURE_LEVEL_VARS)} vars x {len(PRESSURE_LEVELS)} levels, {num_days} days)...", flush=True)

            request_pl = {
                "product_type": "reanalysis",
                "variable": PRESSURE_LEVEL_VARS,
                "pressure_level": PRESSURE_LEVELS,
                "year": str(year),
                "month": f"{month:02d}",
                "day": days,
                "time": HOURS,
                "area": AREA,
                "data_format": "netcdf",
            }

            ok = safe_retrieve(
                "reanalysis-era5-pressure-levels",
                request_pl,
                pl_path,
                label=f"{month_str} PL",
            )
            if ok:
                size_mb = os.path.getsize(pl_path) / (1024 * 1024)
                print(f"[DONE] {month_str} pressure-levels — {size_mb:.1f} MB", flush=True)
                downloaded += 1
            else:
                failed.append(f"{month_str}-PL")

            time.sleep(3)

# --- Summary ---
print("\n" + "=" * 50, flush=True)
print(f"Download complete.", flush=True)
print(f"  Downloaded: {downloaded}", flush=True)
print(f"  Skipped:    {skipped}", flush=True)
print(f"  Failed:     {len(failed)}", flush=True)
if failed:
    print(f"  Failed: {', '.join(failed)}", flush=True)
print("=" * 50, flush=True)
