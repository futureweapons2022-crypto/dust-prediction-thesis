"""
QA/QC Script for CAMS Dust AOD Forecasts
=========================================
Validates all half-year CAMS NetCDF files for the Arabian Gulf domain.
Checks: file integrity, temporal completeness, forecast steps, value ranges,
spatial completeness, and domain bounds.

Output: data/qaqc_cams_summary.csv
"""

import os
import sys
import numpy as np
import pandas as pd
import netCDF4 as nc
from datetime import datetime, timedelta

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "cams")
OUT_DIR = os.path.join(BASE_DIR, "data")

# Expected domain
EXPECTED_LAT_MIN, EXPECTED_LAT_MAX = 20.0, 34.0
EXPECTED_LON_MIN, EXPECTED_LON_MAX = 45.2, 60.0
EXPECTED_RESOLUTION = 0.4
EXPECTED_STEPS = 41  # 0 to 120h in 3h increments
EXPECTED_STEP_VALUES = np.arange(0, 123, 3, dtype=float)  # 0, 3, 6, ..., 120
VALUE_MIN = 0.0  # Negative DOD is physically impossible


def get_half_year_files():
    """Return sorted list of half-year CAMS files."""
    files = []
    for f in sorted(os.listdir(DATA_DIR)):
        if f.startswith("cams_duaod550_") and f.endswith(".nc") and "h" in f.split("_")[-1]:
            files.append(f)
    return files


def check_file(filepath):
    """Run all QA/QC checks on a single CAMS file. Returns dict of results."""
    fname = os.path.basename(filepath)
    result = {
        "file": fname,
        "readable": False,
        "n_days": 0,
        "n_steps": 0,
        "steps_correct": False,
        "lat_min": np.nan, "lat_max": np.nan,
        "lon_min": np.nan, "lon_max": np.nan,
        "domain_correct": False,
        "lat_res": np.nan, "lon_res": np.nan,
        "resolution_correct": False,
        "dod_min": np.nan, "dod_max": np.nan, "dod_mean": np.nan,
        "n_negative": 0,
        "value_range_ok": False,
        "nan_count": 0, "nan_pct": 0.0,
        "total_cells": 0,
        "date_start": "", "date_end": "",
        "issues": [],
    }

    try:
        ds = nc.Dataset(filepath, "r")
        result["readable"] = True
    except Exception as e:
        result["issues"].append(f"Cannot open file: {e}")
        return result

    try:
        # --- Temporal completeness ---
        frt = ds.variables["forecast_reference_time"]
        n_days = len(frt)
        result["n_days"] = n_days

        # Convert times to dates
        times = nc.num2date(frt[:], frt.units)
        result["date_start"] = str(times[0])[:10]
        result["date_end"] = str(times[-1])[:10]

        # Check for gaps: consecutive days should differ by 1 day
        if n_days > 1:
            deltas = np.diff([t.toordinal() if hasattr(t, 'toordinal') else 0 for t in times])
            gaps = np.where(deltas > 1)[0]
            if len(gaps) > 0:
                for g in gaps:
                    result["issues"].append(
                        f"Temporal gap: {times[g]} to {times[g+1]} ({deltas[g]} days)"
                    )

        # Half-year should have ~181-184 days
        if n_days < 175:
            result["issues"].append(f"Fewer days than expected for half-year: {n_days}")

        # --- Forecast steps ---
        fp = ds.variables["forecast_period"]
        steps = fp[:]
        result["n_steps"] = len(steps)
        result["steps_correct"] = (
            len(steps) == EXPECTED_STEPS and
            np.allclose(steps, EXPECTED_STEP_VALUES)
        )
        if not result["steps_correct"]:
            result["issues"].append(
                f"Forecast steps mismatch: got {len(steps)} steps, "
                f"range {steps.min()}-{steps.max()}"
            )

        # --- Domain check ---
        lat = ds.variables["latitude"][:]
        lon = ds.variables["longitude"][:]
        result["lat_min"] = float(lat.min())
        result["lat_max"] = float(lat.max())
        result["lon_min"] = float(lon.min())
        result["lon_max"] = float(lon.max())

        result["domain_correct"] = (
            np.isclose(lat.min(), EXPECTED_LAT_MIN, atol=0.1) and
            np.isclose(lat.max(), EXPECTED_LAT_MAX, atol=0.1) and
            np.isclose(lon.min(), EXPECTED_LON_MIN, atol=0.1) and
            np.isclose(lon.max(), EXPECTED_LON_MAX, atol=0.1)
        )
        if not result["domain_correct"]:
            result["issues"].append(
                f"Domain mismatch: lat [{lat.min()}, {lat.max()}], "
                f"lon [{lon.min()}, {lon.max()}]"
            )

        # Resolution
        if len(lat) > 1:
            result["lat_res"] = float(np.abs(np.diff(lat)).mean())
        if len(lon) > 1:
            result["lon_res"] = float(np.abs(np.diff(lon)).mean())
        result["resolution_correct"] = (
            np.isclose(result["lat_res"], EXPECTED_RESOLUTION, atol=0.05) and
            np.isclose(result["lon_res"], EXPECTED_RESOLUTION, atol=0.05)
        )

        # --- T+0 check ---
        dod_var = ds.variables["duaod550"]
        data = dod_var[:]  # shape: (steps, days, lat, lon)
        t0_data = data[0, :, :, :]  # First step = T+0
        t0_nan_pct = np.isnan(t0_data).sum() / t0_data.size * 100
        t0_has_data = t0_nan_pct < 100
        result["t0_has_data"] = t0_has_data
        result["t0_nan_pct"] = round(t0_nan_pct, 2)

        # --- Value range check ---

        result["total_cells"] = data.size
        result["nan_count"] = int(np.isnan(data).sum())
        result["nan_pct"] = round(result["nan_count"] / data.size * 100, 4)

        # Mask NaNs for stats
        valid = data[~np.isnan(data)]
        if len(valid) > 0:
            result["dod_min"] = float(np.min(valid))
            result["dod_max"] = float(np.max(valid))
            result["dod_mean"] = float(np.mean(valid))
            result["n_negative"] = int(np.sum(valid < VALUE_MIN))

            if result["n_negative"] > 0:
                result["issues"].append(f"{result['n_negative']} negative values (physically impossible)")

        result["value_range_ok"] = (result["n_negative"] == 0)

    except Exception as e:
        result["issues"].append(f"Error during checks: {e}")
    finally:
        ds.close()

    return result


def seasonal_stats(filepath):
    """Compute seasonal DOD statistics for a file."""
    try:
        ds = nc.Dataset(filepath, "r")
        frt = ds.variables["forecast_reference_time"]
        times = nc.num2date(frt[:], frt.units)
        data = ds.variables["duaod550"][:]  # (steps, days, lat, lon)

        # Use T+24h (step index 8) as representative forecast
        t24_data = data[8, :, :, :]  # (days, lat, lon)

        season_map = {12: "DJF", 1: "DJF", 2: "DJF",
                      3: "MAM", 4: "MAM", 5: "MAM",
                      6: "JJA", 7: "JJA", 8: "JJA",
                      9: "SON", 10: "SON", 11: "SON"}

        stats = []
        months = np.array([t.month for t in times])
        for season in ["DJF", "MAM", "JJA", "SON"]:
            mask = np.array([season_map[m] == season for m in months])
            if mask.sum() == 0:
                continue
            subset = t24_data[mask, :, :]
            valid = subset[~np.isnan(subset)]
            if len(valid) > 0:
                stats.append({
                    "file": os.path.basename(filepath),
                    "season": season,
                    "mean_dod": round(float(np.mean(valid)), 6),
                    "max_dod": round(float(np.max(valid)), 6),
                    "min_dod": round(float(np.min(valid)), 6),
                    "n_days": int(mask.sum()),
                })
        ds.close()
        return stats
    except Exception:
        return []


def run_cams_qaqc():
    """Main QA/QC routine. Returns (results_list, issues_list, pass_bool)."""
    print("=" * 60)
    print("CAMS Dust AOD (duaod550) — QA/QC Report")
    print("=" * 60)

    files = get_half_year_files()
    print(f"\nFound {len(files)} half-year files in {DATA_DIR}")

    if len(files) == 0:
        print("ERROR: No half-year CAMS files found!")
        return [], ["No files found"], False

    # Run checks on each file
    results = []
    all_seasonal = []
    for f in files:
        filepath = os.path.join(DATA_DIR, f)
        print(f"  Checking {f}...", end=" ")
        r = check_file(filepath)
        results.append(r)

        status = "OK" if len(r["issues"]) == 0 else f"ISSUES ({len(r['issues'])})"
        print(status)

        # Seasonal stats
        ss = seasonal_stats(filepath)
        all_seasonal.extend(ss)

    # Build summary DataFrame
    df = pd.DataFrame(results)
    summary_cols = [
        "file", "readable", "n_days", "date_start", "date_end",
        "n_steps", "steps_correct", "domain_correct", "resolution_correct",
        "dod_min", "dod_max", "dod_mean", "n_negative",
        "value_range_ok", "nan_count", "nan_pct",
    ]
    df_summary = df[summary_cols]
    df_summary.to_csv(os.path.join(OUT_DIR, "qaqc_cams_summary.csv"), index=False)

    # Print summary
    print(f"\n--- Summary ---")
    print(f"Files checked:       {len(results)}")
    print(f"All readable:        {all(r['readable'] for r in results)}")
    print(f"All steps correct:   {all(r['steps_correct'] for r in results)}")
    print(f"All domain correct:  {all(r['domain_correct'] for r in results)}")
    print(f"All resolution OK:   {all(r['resolution_correct'] for r in results)}")
    print(f"All value range OK:  {all(r['value_range_ok'] for r in results)}")

    # Overall DOD stats
    all_mins = [r["dod_min"] for r in results if not np.isnan(r["dod_min"])]
    all_maxs = [r["dod_max"] for r in results if not np.isnan(r["dod_max"])]
    all_means = [r["dod_mean"] for r in results if not np.isnan(r["dod_mean"])]
    if all_mins:
        print(f"DOD range overall:   [{min(all_mins):.6f}, {max(all_maxs):.6f}]")
        print(f"DOD mean overall:    {np.mean(all_means):.6f}")

    total_nan = sum(r["nan_count"] for r in results)
    total_cells = sum(r["total_cells"] for r in results)
    print(f"Total NaN cells:     {total_nan} / {total_cells} ({total_nan/total_cells*100:.4f}%)")

    # Date coverage
    dates = [(r["date_start"], r["date_end"]) for r in results if r["date_start"]]
    if dates:
        print(f"Date coverage:       {dates[0][0]} to {dates[-1][1]}")

    # Print seasonal stats
    if all_seasonal:
        print(f"\n--- Seasonal Statistics (T+24h) ---")
        df_season = pd.DataFrame(all_seasonal)
        for season in ["DJF", "MAM", "JJA", "SON"]:
            sub = df_season[df_season["season"] == season]
            if len(sub) > 0:
                print(f"  {season}: mean={sub['mean_dod'].mean():.4f}, "
                      f"max={sub['max_dod'].max():.4f}, "
                      f"n_files={len(sub)}")

    # Collect all issues
    all_issues = []
    for r in results:
        for issue in r["issues"]:
            all_issues.append(f"  [{r['file']}] {issue}")

    if all_issues:
        print(f"\n--- Issues Found ({len(all_issues)}) ---")
        for issue in all_issues:
            print(issue)
    else:
        print(f"\nNo issues found. All checks passed.")

    overall_pass = len(all_issues) == 0
    return results, all_issues, overall_pass


if __name__ == "__main__":
    results, issues, passed = run_cams_qaqc()
    print(f"\nOverall: {'PASS' if passed else 'FAIL'}")
    sys.exit(0 if passed else 1)
