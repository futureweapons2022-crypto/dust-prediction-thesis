"""
QA/QC Script for AERONET Ground Truth Data
============================================
Validates all AERONET CSV files (Level 2.0 and Level 1.5).
Checks: file integrity, missing values (-999), temporal coverage & gaps,
value ranges, station summary, quality tier comparison.

Output: data/qaqc_aeronet_summary.csv
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "aeronet")
OUT_DIR = os.path.join(BASE_DIR, "data")

# Only negatives are physically impossible for AOD
AOD_MIN = 0.0

# Key columns to check
AOD_COL = "AOD_500nm"
AE_COL = "440-870_Angstrom_Exponent"
MISSING_VALUE = -999.0


def load_aeronet_csv(filepath):
    """Load an AERONET CSV file with proper header handling."""
    # 7 header lines (HTML), CSV starts at line 8 (0-indexed: skiprows=7)
    df = pd.read_csv(filepath, skiprows=7, na_values=[-999, -999.0, "-999", "-999.000000"])

    # Fix trailing <br> in last column name
    cols = list(df.columns)
    if cols[-1].endswith("<br>"):
        cols[-1] = cols[-1].replace("<br>", "")
        df.columns = cols

    # Parse datetime
    df["datetime"] = pd.to_datetime(
        df["Date(dd:mm:yyyy)"] + " " + df["Time(hh:mm:ss)"],
        format="%d:%m:%Y %H:%M:%S",
        errors="coerce"
    )

    return df


def check_station(filepath, level):
    """Run QA/QC checks on a single AERONET station file."""
    fname = os.path.basename(filepath)
    result = {
        "file": fname,
        "level": level,
        "readable": False,
        "station_name": "",
        "latitude": np.nan,
        "longitude": np.nan,
        "elevation_m": np.nan,
        "n_observations": 0,
        "date_start": "",
        "date_end": "",
        "n_years": 0,
        "obs_per_year": "",
        "longest_gap_days": 0,
        "aod500_mean": np.nan,
        "aod500_median": np.nan,
        "aod500_max": np.nan,
        "aod500_min": np.nan,
        "ae_mean": np.nan,
        "pct_missing_aod500": 0.0,
        "pct_missing_ae": 0.0,
        "n_negative_aod": 0,
        "value_range_ok": False,
        "issues": [],
    }

    try:
        df = load_aeronet_csv(filepath)
        result["readable"] = True
    except Exception as e:
        result["issues"].append(f"Cannot read file: {e}")
        return result

    try:
        result["n_observations"] = len(df)

        # Station metadata
        if "AERONET_Site" in df.columns:
            result["station_name"] = df["AERONET_Site"].iloc[0]
        if "Site_Latitude(Degrees)" in df.columns:
            result["latitude"] = float(df["Site_Latitude(Degrees)"].iloc[0])
        if "Site_Longitude(Degrees)" in df.columns:
            result["longitude"] = float(df["Site_Longitude(Degrees)"].iloc[0])
        if "Site_Elevation(m)" in df.columns:
            result["elevation_m"] = float(df["Site_Elevation(m)"].iloc[0])

        # Temporal coverage
        valid_dt = df["datetime"].dropna().sort_values()
        if len(valid_dt) > 0:
            result["date_start"] = str(valid_dt.iloc[0])[:10]
            result["date_end"] = str(valid_dt.iloc[-1])[:10]

            years = valid_dt.dt.year.unique()
            result["n_years"] = len(years)

            # Observations per year
            yearly = valid_dt.dt.year.value_counts().sort_index()
            result["obs_per_year"] = "; ".join(
                f"{y}:{c}" for y, c in yearly.items()
            )

            # Longest gap
            if len(valid_dt) > 1:
                gaps = valid_dt.diff().dropna()
                max_gap = gaps.max()
                result["longest_gap_days"] = round(max_gap.total_seconds() / 86400, 1)

        # Missing value analysis (count original -999 entries)
        if AOD_COL in df.columns:
            total = len(df)
            missing_aod = df[AOD_COL].isna().sum()
            result["pct_missing_aod500"] = round(missing_aod / total * 100, 2)

            # Stats on valid AOD
            valid_aod = df[AOD_COL].dropna()
            if len(valid_aod) > 0:
                result["aod500_mean"] = round(float(valid_aod.mean()), 6)
                result["aod500_median"] = round(float(valid_aod.median()), 6)
                result["aod500_max"] = round(float(valid_aod.max()), 6)
                result["aod500_min"] = round(float(valid_aod.min()), 6)
                result["n_negative_aod"] = int((valid_aod < AOD_MIN).sum())
        else:
            result["issues"].append(f"Column '{AOD_COL}' not found")

        if AE_COL in df.columns:
            total = len(df)
            missing_ae = df[AE_COL].isna().sum()
            result["pct_missing_ae"] = round(missing_ae / total * 100, 2)

            valid_ae = df[AE_COL].dropna()
            if len(valid_ae) > 0:
                result["ae_mean"] = round(float(valid_ae.mean()), 6)
        else:
            result["issues"].append(f"Column '{AE_COL}' not found")

        # Value range check
        result["value_range_ok"] = (result["n_negative_aod"] == 0)
        if result["n_negative_aod"] > 0:
            result["issues"].append(f"{result['n_negative_aod']} negative AOD values (physically impossible)")

    except Exception as e:
        result["issues"].append(f"Error during checks: {e}")

    return result


def run_aeronet_qaqc():
    """Main QA/QC routine. Returns (results_list, issues_list, pass_bool)."""
    print("=" * 60)
    print("AERONET Ground Truth — QA/QC Report")
    print("=" * 60)

    results = []

    # Process Level 2.0
    l2_dir = os.path.join(DATA_DIR, "level2")
    l2_files = sorted([f for f in os.listdir(l2_dir) if f.endswith(".csv")])
    print(f"\nLevel 2.0: {len(l2_files)} station files")
    for f in l2_files:
        print(f"  Checking {f}...", end=" ")
        r = check_station(os.path.join(l2_dir, f), "L2.0")
        results.append(r)
        status = "OK" if len(r["issues"]) == 0 else f"ISSUES ({len(r['issues'])})"
        print(f"{r['n_observations']} obs — {status}")

    # Process Level 1.5
    l15_dir = os.path.join(DATA_DIR, "level15")
    l15_files = sorted([f for f in os.listdir(l15_dir) if f.endswith(".csv")])
    print(f"\nLevel 1.5: {len(l15_files)} station files")
    for f in l15_files:
        print(f"  Checking {f}...", end=" ")
        r = check_station(os.path.join(l15_dir, f), "L1.5")
        results.append(r)
        status = "OK" if len(r["issues"]) == 0 else f"ISSUES ({len(r['issues'])})"
        print(f"{r['n_observations']} obs — {status}")

    # Build summary DataFrame
    df = pd.DataFrame(results)
    summary_cols = [
        "file", "level", "station_name", "latitude", "longitude", "elevation_m",
        "n_observations", "date_start", "date_end", "n_years",
        "longest_gap_days", "aod500_mean", "aod500_median", "aod500_max",
        "pct_missing_aod500", "pct_missing_ae", "ae_mean",
        "n_negative_aod", "value_range_ok",
    ]
    df_out = df[[c for c in summary_cols if c in df.columns]]
    df_out.to_csv(os.path.join(OUT_DIR, "qaqc_aeronet_summary.csv"), index=False)

    # Print summary table
    print(f"\n--- Station Summary ---")
    print(f"{'Station':<25} {'Level':<6} {'Obs':>8} {'Years':>6} "
          f"{'AOD mean':>9} {'AOD max':>9} {'%miss':>6} {'Gap(d)':>7}")
    print("-" * 85)
    for r in results:
        print(f"{r['station_name']:<25} {r['level']:<6} {r['n_observations']:>8} "
              f"{r['n_years']:>6} {r['aod500_mean']:>9.4f} {r['aod500_max']:>9.4f} "
              f"{r['pct_missing_aod500']:>5.1f}% {r['longest_gap_days']:>7.1f}")

    # Quality tier comparison
    l2_results = [r for r in results if r["level"] == "L2.0"]
    l15_results = [r for r in results if r["level"] == "L1.5"]
    if l2_results and l15_results:
        l2_miss = np.mean([r["pct_missing_aod500"] for r in l2_results])
        l15_miss = np.mean([r["pct_missing_aod500"] for r in l15_results])
        l2_obs = np.mean([r["n_observations"] for r in l2_results])
        l15_obs = np.mean([r["n_observations"] for r in l15_results])
        print(f"\n--- Quality Tier Comparison ---")
        print(f"L2.0: avg {l2_obs:.0f} obs/station, {l2_miss:.2f}% missing AOD")
        print(f"L1.5: avg {l15_obs:.0f} obs/station, {l15_miss:.2f}% missing AOD")
        if abs(l2_miss - l15_miss) < 0.5:
            print("  Note: Both tiers have similar missing-data rates"
                  " (AOD -999 entries are converted to NaN)")
        elif l2_miss > l15_miss:
            print("  Note: L2.0 has more missing data (expected — stricter QC filtering)")
        else:
            print("  Warning: L1.5 has MORE missing data than L2.0 (unexpected)")

    # Collect all issues
    all_issues = []
    for r in results:
        for issue in r["issues"]:
            all_issues.append(f"  [{r['station_name']} ({r['level']})] {issue}")

    if all_issues:
        print(f"\n--- Issues Found ({len(all_issues)}) ---")
        for issue in all_issues:
            print(issue)
    else:
        print(f"\nNo issues found. All checks passed.")

    overall_pass = len(all_issues) == 0
    return results, all_issues, overall_pass


if __name__ == "__main__":
    results, issues, passed = run_aeronet_qaqc()
    print(f"\nOverall: {'PASS' if passed else 'FAIL'}")
    sys.exit(0 if passed else 1)
