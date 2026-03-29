"""
QA/QC Script for ERA5 Reanalysis Data
======================================
Validates all ERA5 pressure-level and single-level NetCDF files.
Single-level files are ZIP archives containing two NetCDFs (instant + accumulated).

Checks: file integrity, variable completeness, temporal continuity,
value ranges, spatial grid, NaN coverage.

Output: data/qaqc_era5_summary.csv
"""

import os
import sys
import zipfile
import tempfile
import numpy as np
import pandas as pd
import netCDF4 as nc
from datetime import datetime

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "era5")
OUT_DIR = os.path.join(BASE_DIR, "data")

# Expected domain (same as CAMS)
EXPECTED_LAT_MIN, EXPECTED_LAT_MAX = 20.0, 34.0
EXPECTED_LON_MIN, EXPECTED_LON_MAX = 45.0, 60.0
EXPECTED_LAT_SIZE = 57
EXPECTED_LON_SIZE = 61

# Expected variables
PL_VARS = ["z", "u", "v", "t", "r"]
PL_LEVELS = [500, 700, 850]
SL_INSTANT_VARS = ["u10", "v10", "i10fg", "t2m", "skt", "d2m", "tcwv",
                    "blh", "cape", "sp", "swvl1", "lcc", "hcc", "lai_lv", "fal"]
SL_ACCUM_VARS = ["tp", "e", "ssrd", "strd"]

# Physical range checks (variable: (min, max, description))
# None means no bound check on that side
RANGE_CHECKS = {
    # Temperatures in Kelvin
    "t2m": (180, 340, "2m temperature (K)"),
    "skt": (180, 370, "Skin temperature (K)"),
    "d2m": (170, 330, "2m dewpoint (K)"),
    "t": (180, 340, "Temperature at PL (K)"),
    # Wind in m/s
    "u10": (-100, 100, "10m u-wind (m/s)"),
    "v10": (-100, 100, "10m v-wind (m/s)"),
    "u": (-150, 150, "u-wind at PL (m/s)"),
    "v": (-150, 150, "v-wind at PL (m/s)"),
    # Relative humidity in %
    "r": (0, 110, "Relative humidity (%)"),
    # Pressure in Pa
    "sp": (50000, 110000, "Surface pressure (Pa)"),
    # Precipitation (accumulated, can be 0 but not negative in most cases)
    "tp": (0, None, "Total precipitation (m)"),
    # Radiation (accumulated, J/m2, should be non-negative for downward)
    "ssrd": (0, None, "Surface solar radiation down (J/m2)"),
    "strd": (0, None, "Surface thermal radiation down (J/m2)"),
    # Cloud cover 0-1
    "lcc": (-0.01, 1.01, "Low cloud cover (0-1)"),
    "hcc": (-0.01, 1.01, "High cloud cover (0-1)"),
    # Soil moisture (m3/m3)
    "swvl1": (0, 1, "Soil moisture L1 (m3/m3)"),
    # CAPE (J/kg)
    "cape": (0, None, "CAPE (J/kg)"),
    # LAI (m2/m2)
    "lai_lv": (0, None, "Leaf area index (m2/m2)"),
    # Albedo (0-1)
    "fal": (-0.01, 1.01, "Forecast albedo (0-1)"),
}


def get_pl_files():
    """Return sorted list of pressure-level monthly files."""
    files = []
    for f in sorted(os.listdir(DATA_DIR)):
        if f.startswith("era5_pl_all_") and f.endswith(".nc") and len(f) == len("era5_pl_all_YYYYMM.nc"):
            files.append(f)
    return files


def get_sl_files():
    """Return sorted list of single-level monthly files (ZIP format)."""
    files = []
    for f in sorted(os.listdir(DATA_DIR)):
        if f.startswith("era5_single_") and f.endswith(".nc"):
            # Only monthly files (YYYYMM), skip half-year (YYYYhN)
            stem = f.replace("era5_single_", "").replace(".nc", "")
            if len(stem) == 6 and stem.isdigit():
                files.append(f)
    return files


def check_domain(lat, lon):
    """Check lat/lon grid matches expected domain."""
    issues = []
    if len(lat) != EXPECTED_LAT_SIZE:
        issues.append(f"Lat size {len(lat)} != expected {EXPECTED_LAT_SIZE}")
    if len(lon) != EXPECTED_LON_SIZE:
        issues.append(f"Lon size {len(lon)} != expected {EXPECTED_LON_SIZE}")
    if not np.isclose(lat.min(), EXPECTED_LAT_MIN, atol=0.5):
        issues.append(f"Lat min {lat.min():.2f} != expected ~{EXPECTED_LAT_MIN}")
    if not np.isclose(lat.max(), EXPECTED_LAT_MAX, atol=0.5):
        issues.append(f"Lat max {lat.max():.2f} != expected ~{EXPECTED_LAT_MAX}")
    if not np.isclose(lon.min(), EXPECTED_LON_MIN, atol=0.5):
        issues.append(f"Lon min {lon.min():.2f} != expected ~{EXPECTED_LON_MIN}")
    if not np.isclose(lon.max(), EXPECTED_LON_MAX, atol=0.5):
        issues.append(f"Lon max {lon.max():.2f} != expected ~{EXPECTED_LON_MAX}")
    return issues


def check_variable_range(data, varname):
    """Check if variable values are within physical bounds."""
    issues = []
    if varname not in RANGE_CHECKS:
        return issues

    vmin, vmax, desc = RANGE_CHECKS[varname]
    valid = data[~np.isnan(data)]
    if len(valid) == 0:
        return [f"{varname}: ALL NaN"]

    actual_min = float(np.min(valid))
    actual_max = float(np.max(valid))

    if vmin is not None and actual_min < vmin:
        issues.append(f"{varname} below minimum: {actual_min:.4f} < {vmin} ({desc})")
    if vmax is not None and actual_max > vmax:
        issues.append(f"{varname} above maximum: {actual_max:.4f} > {vmax} ({desc})")

    return issues


def check_pl_file(filepath):
    """QA/QC a single pressure-level file."""
    fname = os.path.basename(filepath)
    result = {
        "file": fname,
        "type": "pressure-level",
        "readable": False,
        "n_timesteps": 0,
        "date_start": "",
        "date_end": "",
        "n_vars": 0,
        "vars_complete": False,
        "n_levels": 0,
        "levels_correct": False,
        "domain_correct": False,
        "lat_size": 0,
        "lon_size": 0,
        "total_nan_pct": 0.0,
        "issues": [],
    }

    try:
        ds = nc.Dataset(filepath, "r")
        result["readable"] = True
    except Exception as e:
        result["issues"].append(f"Cannot open: {e}")
        return result

    try:
        # Time
        vt = ds.variables["valid_time"]
        n_times = len(vt)
        result["n_timesteps"] = n_times
        times = nc.num2date(vt[:], vt.units)
        result["date_start"] = str(times[0])[:10]
        result["date_end"] = str(times[-1])[:10]

        # Expected ~124 timesteps for a month (31 days × 4 per day)
        if n_times < 112:  # 28 days × 4
            result["issues"].append(f"Few timesteps: {n_times} (expected ~120-124)")

        # Variables
        data_vars = [v for v in ds.variables if v not in
                     ["valid_time", "latitude", "longitude", "number", "expver", "pressure_level"]]
        result["n_vars"] = len(data_vars)
        missing_vars = [v for v in PL_VARS if v not in data_vars]
        result["vars_complete"] = len(missing_vars) == 0
        if missing_vars:
            result["issues"].append(f"Missing variables: {missing_vars}")

        # Pressure levels
        if "pressure_level" in ds.variables:
            levels = ds.variables["pressure_level"][:]
            result["n_levels"] = len(levels)
            result["levels_correct"] = (sorted(levels) == sorted(PL_LEVELS))
            if not result["levels_correct"]:
                result["issues"].append(f"Levels mismatch: got {list(levels)}, expected {PL_LEVELS}")

        # Domain
        lat = ds.variables["latitude"][:]
        lon = ds.variables["longitude"][:]
        result["lat_size"] = len(lat)
        result["lon_size"] = len(lon)
        domain_issues = check_domain(lat, lon)
        result["domain_correct"] = len(domain_issues) == 0
        result["issues"].extend(domain_issues)

        # Value range checks + NaN count
        total_cells = 0
        total_nan = 0
        for v in PL_VARS:
            if v in ds.variables:
                data = ds.variables[v][:]
                total_cells += data.size
                total_nan += int(np.isnan(data).sum())
                range_issues = check_variable_range(data, v)
                result["issues"].extend(range_issues)

        if total_cells > 0:
            result["total_nan_pct"] = round(total_nan / total_cells * 100, 4)

    except Exception as e:
        result["issues"].append(f"Error during checks: {e}")
    finally:
        ds.close()

    return result


def check_sl_file(filepath):
    """QA/QC a single-level file (ZIP containing instant + accum NetCDFs)."""
    fname = os.path.basename(filepath)
    result = {
        "file": fname,
        "type": "single-level",
        "readable": False,
        "n_timesteps": 0,
        "date_start": "",
        "date_end": "",
        "n_vars": 0,
        "vars_complete": False,
        "n_levels": 0,
        "levels_correct": True,  # N/A for SL
        "domain_correct": False,
        "lat_size": 0,
        "lon_size": 0,
        "total_nan_pct": 0.0,
        "issues": [],
    }

    # Check it's a valid ZIP
    if not zipfile.is_zipfile(filepath):
        result["issues"].append("Not a valid ZIP file")
        return result

    tmpdir = tempfile.mkdtemp()
    try:
        z = zipfile.ZipFile(filepath)
        contents = z.namelist()

        # Expect two files inside
        instant_name = None
        accum_name = None
        for name in contents:
            if "instant" in name:
                instant_name = name
            elif "accum" in name:
                accum_name = name

        if not instant_name:
            result["issues"].append("Missing instant NetCDF inside ZIP")
        if not accum_name:
            result["issues"].append("Missing accumulated NetCDF inside ZIP")
        if not instant_name and not accum_name:
            return result

        result["readable"] = True
        all_found_vars = []
        total_cells = 0
        total_nan = 0

        # Check instant file
        if instant_name:
            outpath = os.path.join(tmpdir, "instant.nc")
            with open(outpath, "wb") as f:
                f.write(z.read(instant_name))
            ds = nc.Dataset(outpath, "r")

            vt = ds.variables["valid_time"]
            n_times = len(vt)
            result["n_timesteps"] = n_times
            times = nc.num2date(vt[:], vt.units)
            result["date_start"] = str(times[0])[:10]
            result["date_end"] = str(times[-1])[:10]

            if n_times < 112:
                result["issues"].append(f"Few timesteps: {n_times}")

            lat = ds.variables["latitude"][:]
            lon = ds.variables["longitude"][:]
            result["lat_size"] = len(lat)
            result["lon_size"] = len(lon)
            domain_issues = check_domain(lat, lon)
            result["domain_correct"] = len(domain_issues) == 0
            result["issues"].extend(domain_issues)

            data_vars = [v for v in ds.variables if v not in
                         ["valid_time", "latitude", "longitude", "number", "expver"]]
            all_found_vars.extend(data_vars)

            for v in data_vars:
                data = ds.variables[v][:]
                total_cells += data.size
                total_nan += int(np.isnan(data).sum())
                range_issues = check_variable_range(data, v)
                result["issues"].extend(range_issues)

            ds.close()
            os.remove(outpath)

        # Check accumulated file
        if accum_name:
            outpath = os.path.join(tmpdir, "accum.nc")
            with open(outpath, "wb") as f:
                f.write(z.read(accum_name))
            ds = nc.Dataset(outpath, "r")

            data_vars = [v for v in ds.variables if v not in
                         ["valid_time", "latitude", "longitude", "number", "expver"]]
            all_found_vars.extend(data_vars)

            for v in data_vars:
                data = ds.variables[v][:]
                total_cells += data.size
                total_nan += int(np.isnan(data).sum())
                range_issues = check_variable_range(data, v)
                result["issues"].extend(range_issues)

            ds.close()
            os.remove(outpath)

        z.close()

        # Check variable completeness
        result["n_vars"] = len(all_found_vars)
        all_expected = SL_INSTANT_VARS + SL_ACCUM_VARS
        missing = [v for v in all_expected if v not in all_found_vars]
        result["vars_complete"] = len(missing) == 0
        if missing:
            result["issues"].append(f"Missing variables: {missing}")

        if total_cells > 0:
            result["total_nan_pct"] = round(total_nan / total_cells * 100, 4)

    except Exception as e:
        result["issues"].append(f"Error: {e}")
    finally:
        # Clean up tmpdir
        for f in os.listdir(tmpdir):
            os.remove(os.path.join(tmpdir, f))
        os.rmdir(tmpdir)

    return result


def check_temporal_continuity(results):
    """Check that months are continuous with no gaps."""
    issues = []
    # Sort by filename (which sorts by date)
    sorted_results = sorted(results, key=lambda r: r["file"])

    for i in range(1, len(sorted_results)):
        prev = sorted_results[i - 1]
        curr = sorted_results[i]
        if prev["date_end"] and curr["date_start"]:
            # Just check months are consecutive
            prev_end = prev["date_end"]
            curr_start = curr["date_start"]
            # Extract YYYYMM from filename
            prev_ym = prev["file"].split("_")[-1].replace(".nc", "")
            curr_ym = curr["file"].split("_")[-1].replace(".nc", "")
            if prev_ym.isdigit() and curr_ym.isdigit():
                prev_y, prev_m = int(prev_ym[:4]), int(prev_ym[4:])
                curr_y, curr_m = int(curr_ym[:4]), int(curr_ym[4:])
                expected_y = prev_y + (1 if prev_m == 12 else 0)
                expected_m = 1 if prev_m == 12 else prev_m + 1
                if curr_y != expected_y or curr_m != expected_m:
                    issues.append(f"Gap between {prev['file']} and {curr['file']}")

    return issues


def run_era5_qaqc():
    """Main QA/QC routine."""
    print("=" * 60)
    print("ERA5 Reanalysis — QA/QC Report")
    print("=" * 60)

    pl_files = get_pl_files()
    sl_files = get_sl_files()
    print(f"\nFound {len(pl_files)} pressure-level files")
    print(f"Found {len(sl_files)} single-level files")

    all_results = []
    all_issues = []

    # --- Pressure-level files ---
    print(f"\n--- Pressure-Level Files ---")
    pl_results = []
    for f in pl_files:
        filepath = os.path.join(DATA_DIR, f)
        print(f"  {f}...", end=" ", flush=True)
        r = check_pl_file(filepath)
        pl_results.append(r)
        status = "OK" if len(r["issues"]) == 0 else f"ISSUES ({len(r['issues'])})"
        print(status)

    # PL temporal continuity
    pl_gaps = check_temporal_continuity(pl_results)
    if pl_gaps:
        for g in pl_gaps:
            all_issues.append(f"[PL] {g}")
        print(f"  Temporal gaps: {len(pl_gaps)}")
    else:
        print(f"  Temporal continuity: OK")

    all_results.extend(pl_results)

    # --- Single-level files ---
    print(f"\n--- Single-Level Files ---")
    sl_results = []
    for f in sl_files:
        filepath = os.path.join(DATA_DIR, f)
        print(f"  {f}...", end=" ", flush=True)
        r = check_sl_file(filepath)
        sl_results.append(r)
        status = "OK" if len(r["issues"]) == 0 else f"ISSUES ({len(r['issues'])})"
        print(status)

    # SL temporal continuity
    sl_gaps = check_temporal_continuity(sl_results)
    if sl_gaps:
        for g in sl_gaps:
            all_issues.append(f"[SL] {g}")
        print(f"  Temporal gaps: {len(sl_gaps)}")
    else:
        print(f"  Temporal continuity: OK")

    all_results.extend(sl_results)

    # --- Summary ---
    print(f"\n{'=' * 60}")
    print(f"SUMMARY")
    print(f"{'=' * 60}")

    pl_ok = sum(1 for r in pl_results if len(r["issues"]) == 0)
    sl_ok = sum(1 for r in sl_results if len(r["issues"]) == 0)
    print(f"Pressure-level: {pl_ok}/{len(pl_results)} files clean")
    print(f"Single-level:   {sl_ok}/{len(sl_results)} files clean")

    # Check completeness
    print(f"\nAll PL readable:      {all(r['readable'] for r in pl_results)}")
    print(f"All PL vars complete: {all(r['vars_complete'] for r in pl_results)}")
    print(f"All PL levels correct:{all(r['levels_correct'] for r in pl_results)}")
    print(f"All PL domain correct:{all(r['domain_correct'] for r in pl_results)}")

    print(f"All SL readable:      {all(r['readable'] for r in sl_results)}")
    print(f"All SL vars complete: {all(r['vars_complete'] for r in sl_results)}")
    print(f"All SL domain correct:{all(r['domain_correct'] for r in sl_results)}")

    # Date coverage
    if pl_results:
        pl_start = min(r["date_start"] for r in pl_results if r["date_start"])
        pl_end = max(r["date_end"] for r in pl_results if r["date_end"])
        print(f"\nPL date coverage: {pl_start} to {pl_end}")
    if sl_results:
        sl_start = min(r["date_start"] for r in sl_results if r["date_start"])
        sl_end = max(r["date_end"] for r in sl_results if r["date_end"])
        print(f"SL date coverage: {sl_start} to {sl_end}")

    # NaN summary
    pl_nan = [r["total_nan_pct"] for r in pl_results]
    sl_nan = [r["total_nan_pct"] for r in sl_results]
    if pl_nan:
        print(f"\nPL NaN%: mean={np.mean(pl_nan):.4f}%, max={np.max(pl_nan):.4f}%")
    if sl_nan:
        print(f"SL NaN%: mean={np.mean(sl_nan):.4f}%, max={np.max(sl_nan):.4f}%")

    # Collect all issues
    for r in all_results:
        for issue in r["issues"]:
            all_issues.append(f"[{r['file']}] {issue}")

    if all_issues:
        print(f"\n--- Issues Found ({len(all_issues)}) ---")
        for issue in all_issues:
            print(f"  {issue}")
    else:
        print(f"\nNo issues found. All checks passed.")

    # Save summary CSV
    df = pd.DataFrame(all_results)
    csv_cols = ["file", "type", "readable", "n_timesteps", "date_start", "date_end",
                "n_vars", "vars_complete", "n_levels", "levels_correct",
                "domain_correct", "lat_size", "lon_size", "total_nan_pct"]
    df["n_issues"] = df["issues"].apply(len)
    csv_cols.append("n_issues")
    df[csv_cols].to_csv(os.path.join(OUT_DIR, "qaqc_era5_summary.csv"), index=False)
    print(f"\nSummary saved to: data/qaqc_era5_summary.csv")

    overall_pass = len(all_issues) == 0
    return all_results, all_issues, overall_pass


if __name__ == "__main__":
    results, issues, passed = run_era5_qaqc()
    print(f"\nOverall: {'PASS' if passed else 'FAIL'}")
    sys.exit(0 if passed else 1)
