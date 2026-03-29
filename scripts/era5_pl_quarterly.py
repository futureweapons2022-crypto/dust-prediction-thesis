"""
ERA5 Pressure-Level Quarterly — Fix for half-year PL requests that exceed API cost limits.
Uses 3-month chunks which stay under the Copernicus size cap (~35 MB each).
Auto-splits to monthly if quarterly still fails.
"""

import cdsapi
import os
import time
import glob

CDS_URL = "https://cds.climate.copernicus.eu/api"
OUTPUT_DIR = r"C:\Users\LENOVO\Desktop\THESIS\data\era5"
AREA = [34, 45, 20, 60]
HOURS_6H = ["00:00", "06:00", "12:00", "18:00"]

PRESSURE_LEVEL_VARS = [
    "geopotential", "u_component_of_wind", "v_component_of_wind",
    "temperature", "relative_humidity",
]
PRESSURE_LEVELS = ["500", "700", "850"]

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Scan what PL files already exist (monthly or big chunks)
existing = set()
for f in glob.glob(os.path.join(OUTPUT_DIR, "era5_pl_all_*.nc")):
    existing.add(os.path.basename(f))

# Build quarterly PL jobs for 2016 Q4 through 2024 Q4
# Skip anything already covered by existing files
QUARTERS = [
    ("Q1", "01-01", "03-31"),
    ("Q2", "04-01", "06-30"),
    ("Q3", "07-01", "09-30"),
    ("Q4", "10-01", "12-31"),
]

MONTHS_IN_QUARTER = {
    "Q1": [(1, 31), (2, 28), (3, 31)],
    "Q2": [(4, 30), (5, 31), (6, 30)],
    "Q3": [(7, 31), (8, 31), (9, 30)],
    "Q4": [(10, 31), (11, 30), (12, 31)],
}


def quarter_covered(year, qname):
    """Check if this quarter is already covered by existing files."""
    qfile = f"era5_pl_all_{year}{qname.lower()}.nc"
    if qfile in existing:
        return True
    # Check if half-year file covers it
    if qname in ("Q1", "Q2"):
        if f"era5_pl_all_{year}h1.nc" in existing:
            return True
    else:
        if f"era5_pl_all_{year}h2.nc" in existing:
            return True
    # Check if all monthly files exist for this quarter
    months = MONTHS_IN_QUARTER[qname]
    all_monthly = all(
        f"era5_pl_all_{year}{m:02d}.nc" in existing for m, _ in months
    )
    if all_monthly:
        return True
    return False


def is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def run_request(label, date_range, filename):
    """Try a single CDS request. Returns True on success, False on failure."""
    filepath = os.path.join(OUTPUT_DIR, filename)

    if os.path.exists(filepath):
        print(f"[SKIP] {label} — already exists ({os.path.getsize(filepath)/(1024*1024):.1f} MB)", flush=True)
        return True

    print(f"\n[START] {label} — {date_range}", flush=True)
    client = cdsapi.Client(url=CDS_URL, timeout=86400, retry_max=5, quiet=False)
    t0 = time.time()

    params = {
        "product_type": "reanalysis",
        "variable": PRESSURE_LEVEL_VARS,
        "pressure_level": PRESSURE_LEVELS,
        "date": date_range,
        "time": HOURS_6H,
        "area": AREA,
        "data_format": "netcdf",
    }

    try:
        client.retrieve("reanalysis-era5-pressure-levels", params, filepath)
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        elapsed = (time.time() - t0) / 60
        print(f"[DONE] {label} — {size_mb:.1f} MB in {elapsed:.0f} min", flush=True)
        return True
    except Exception as e:
        elapsed = (time.time() - t0) / 60
        err = str(e)
        print(f"[FAIL] {label} — {err} ({elapsed:.0f} min)", flush=True)
        if os.path.exists(filepath):
            os.remove(filepath)
        return False


def run_quarter(year, qname, q_start, q_end):
    """Try quarterly chunk first. If it fails with cost limits, auto-split to monthly."""
    date_range = f"{year}-{q_start}/{year}-{q_end}"
    filename = f"era5_pl_all_{year}{qname.lower()}.nc"
    label = f"PL {year} {qname}"

    success = run_request(label, date_range, filename)

    if not success:
        print(f"[AUTO-SPLIT] {label} failed — splitting into monthly requests", flush=True)
        months = MONTHS_IN_QUARTER[qname]
        for m, last_day in months:
            # Fix Feb for leap years
            if m == 2 and is_leap(year):
                last_day = 29
            m_label = f"PL {year}-{m:02d}"
            m_date = f"{year}-{m:02d}-01/{year}-{m:02d}-{last_day:02d}"
            m_file = f"era5_pl_all_{year}{m:02d}.nc"
            run_request(m_label, m_date, m_file)


if __name__ == "__main__":
    # Build job list — 2016 Q4 through 2024 Q4, skipping what exists
    jobs = []
    for year in range(2016, 2025):
        for qname, q_start, q_end in QUARTERS:
            # Skip 2016 Q1-Q3 (covered by monthly script)
            if year == 2016 and qname in ("Q1", "Q2", "Q3"):
                continue
            if not quarter_covered(year, qname):
                jobs.append((year, qname, q_start, q_end))

    print(f"ERA5 PL Quarterly Download (with auto-split)", flush=True)
    print(f"Jobs: {len(jobs)} quarters to fill", flush=True)
    print(f"Already covered quarters skipped", flush=True)
    print(f"Output: {OUTPUT_DIR}", flush=True)
    print(f"{'='*60}\n", flush=True)

    if not jobs:
        print("Nothing to download — all PL data already exists!", flush=True)
    else:
        for year, qname, q_start, q_end in jobs:
            run_quarter(year, qname, q_start, q_end)

    print(f"\n{'='*60}", flush=True)
    print("All PL quarterly jobs complete.", flush=True)
