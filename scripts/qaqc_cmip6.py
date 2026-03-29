"""
QA/QC Script for CMIP6 Climate Projections
============================================
Validates all CMIP6 NetCDF files for dust AOD (od550dust).
Checks: file integrity, model inventory, temporal coverage, value ranges,
multi-file consistency, domain extraction, model agreement.

Output: data/qaqc_cmip6_summary.csv
"""

import os
import sys
import numpy as np
import pandas as pd
import netCDF4 as nc

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "cmip6")
OUT_DIR = os.path.join(BASE_DIR, "data")

# Expected models and experiments
EXPECTED_MODELS = ["GISS-E2-1-G", "GISS-E2-1-H", "MIROC-ES2L", "MIROC6", "MRI-ESM2-0"]
EXPECTED_EXPERIMENTS = ["historical", "ssp245", "ssp585"]

# Arabian Gulf region for extraction
AG_LAT_MIN, AG_LAT_MAX = 20.0, 34.0
AG_LON_MIN, AG_LON_MAX = 45.0, 60.0

# Value range — only negatives are physically impossible
VALUE_MIN = 0.0


def get_model_files():
    """Scan CMIP6 directory and return structured inventory."""
    inventory = {}
    for model in EXPECTED_MODELS:
        inventory[model] = {}
        for exp in EXPECTED_EXPERIMENTS:
            exp_dir = os.path.join(DATA_DIR, model, exp)
            if os.path.isdir(exp_dir):
                files = sorted([f for f in os.listdir(exp_dir) if f.endswith(".nc")])
                inventory[model][exp] = files
            else:
                inventory[model][exp] = []
    return inventory


def check_file(filepath):
    """Check a single CMIP6 NetCDF file."""
    fname = os.path.basename(filepath)
    result = {
        "file": fname,
        "readable": False,
        "n_timesteps": 0,
        "date_start": "",
        "date_end": "",
        "n_lat": 0, "n_lon": 0,
        "lat_range": "",
        "lon_range": "",
        "dod_min": np.nan, "dod_max": np.nan, "dod_mean": np.nan,
        "n_negative": 0,
        "nan_pct": 0.0,
        "ag_mean_dod": np.nan,
        "issues": [],
    }

    try:
        ds = nc.Dataset(filepath, "r")
        result["readable"] = True
    except Exception as e:
        result["issues"].append(f"Cannot open: {e}")
        return result

    try:
        # Dimensions
        lat = ds.variables["lat"][:]
        lon = ds.variables["lon"][:]
        result["n_lat"] = len(lat)
        result["n_lon"] = len(lon)
        result["lat_range"] = f"[{float(lat.min()):.1f}, {float(lat.max()):.1f}]"
        result["lon_range"] = f"[{float(lon.min()):.1f}, {float(lon.max()):.1f}]"

        # Time
        time_var = ds.variables["time"]
        times = nc.num2date(time_var[:], time_var.units, calendar=getattr(time_var, 'calendar', 'standard'))
        result["n_timesteps"] = len(times)
        result["date_start"] = str(times[0])[:10]
        result["date_end"] = str(times[-1])[:10]

        # Check for temporal gaps (monthly data — expect ~30 day intervals)
        if len(times) > 1:
            # For monthly data, check year-month continuity
            ym_list = []
            for t in times:
                try:
                    ym_list.append(t.year * 12 + t.month)
                except AttributeError:
                    pass
            if ym_list:
                diffs = np.diff(ym_list)
                gaps = np.where(diffs > 1)[0]
                if len(gaps) > 0:
                    for g in gaps[:5]:  # Report first 5 gaps
                        result["issues"].append(
                            f"Monthly gap at index {g}: jump of {diffs[g]} months"
                        )

        # Value range check — read od550dust
        dod_var = ds.variables["od550dust"]
        # Read in slices to manage memory for large files
        data = dod_var[:]

        valid = data[~np.isnan(data)]
        # Handle masked arrays
        if hasattr(data, 'mask'):
            valid = data.compressed()

        if len(valid) > 0:
            result["dod_min"] = float(np.min(valid))
            result["dod_max"] = float(np.max(valid))
            result["dod_mean"] = float(np.mean(valid))
            result["n_negative"] = int(np.sum(valid < VALUE_MIN))

            if result["n_negative"] > 0:
                result["issues"].append(f"{result['n_negative']} negative values (physically impossible)")

        total_size = data.size
        if hasattr(data, 'mask'):
            nan_count = int(data.mask.sum())
        else:
            nan_count = int(np.isnan(data).sum())
        result["nan_pct"] = round(nan_count / total_size * 100, 2) if total_size > 0 else 0

        # Extract Arabian Gulf region mean
        lat_mask = (lat >= AG_LAT_MIN) & (lat <= AG_LAT_MAX)
        lon_mask = (lon >= AG_LON_MIN) & (lon <= AG_LON_MAX)
        if lat_mask.sum() > 0 and lon_mask.sum() > 0:
            ag_data = data[:, lat_mask, :][:, :, lon_mask]
            if hasattr(ag_data, 'compressed'):
                ag_valid = ag_data.compressed()
            else:
                ag_valid = ag_data[~np.isnan(ag_data)]
            if len(ag_valid) > 0:
                result["ag_mean_dod"] = round(float(np.mean(ag_valid)), 6)
        else:
            result["issues"].append("Could not extract Arabian Gulf region")

    except Exception as e:
        result["issues"].append(f"Error: {e}")
    finally:
        ds.close()

    return result


def check_multi_file_continuity(model, exp, files):
    """Check that multiple files for the same model/experiment have no temporal gaps."""
    if len(files) <= 1:
        return []

    issues = []
    exp_dir = os.path.join(DATA_DIR, model, exp)
    prev_end = None

    for f in sorted(files):
        try:
            ds = nc.Dataset(os.path.join(exp_dir, f), "r")
            time_var = ds.variables["time"]
            times = nc.num2date(time_var[:], time_var.units,
                                calendar=getattr(time_var, 'calendar', 'standard'))
            start = times[0]
            end = times[-1]

            if prev_end is not None:
                # Check gap between files
                try:
                    prev_ym = prev_end.year * 12 + prev_end.month
                    start_ym = start.year * 12 + start.month
                    gap_months = start_ym - prev_ym
                    if gap_months > 1:
                        issues.append(
                            f"Gap between files: {prev_end} to {start} ({gap_months} months)"
                        )
                    elif gap_months < 1:
                        issues.append(
                            f"Overlap between files: {prev_end} to {start}"
                        )
                except AttributeError:
                    pass

            prev_end = end
            ds.close()
        except Exception as e:
            issues.append(f"Error reading {f}: {e}")

    return issues


def run_cmip6_qaqc():
    """Main QA/QC routine. Returns (results_list, issues_list, pass_bool)."""
    print("=" * 60)
    print("CMIP6 Climate Projections (od550dust) — QA/QC Report")
    print("=" * 60)

    inventory = get_model_files()

    # Model inventory check
    print(f"\n--- Model Inventory ---")
    print(f"{'Model':<20} {'historical':>12} {'ssp245':>12} {'ssp585':>12}")
    print("-" * 58)
    missing_combos = []
    for model in EXPECTED_MODELS:
        row = f"{model:<20}"
        for exp in EXPECTED_EXPERIMENTS:
            n = len(inventory[model].get(exp, []))
            marker = f"{n} files" if n > 0 else "MISSING"
            row += f"{marker:>12}"
            if n == 0:
                missing_combos.append(f"{model}/{exp}")
        print(row)

    if missing_combos:
        print(f"\nMissing combinations: {', '.join(missing_combos)}")

    # Check all files
    results = []
    all_issues = []

    for model in EXPECTED_MODELS:
        for exp in EXPECTED_EXPERIMENTS:
            files = inventory[model].get(exp, [])
            if not files:
                continue

            exp_dir = os.path.join(DATA_DIR, model, exp)
            print(f"\n  {model}/{exp} ({len(files)} files):")

            for f in sorted(files):
                filepath = os.path.join(exp_dir, f)
                print(f"    Checking {f}...", end=" ")
                r = check_file(filepath)
                r["model"] = model
                r["experiment"] = exp
                results.append(r)

                status = "OK" if not r["issues"] else f"ISSUES ({len(r['issues'])})"
                print(f"{r['n_timesteps']} months, {r['date_start']}–{r['date_end']} — {status}")

            # Multi-file continuity check
            if len(files) > 1:
                cont_issues = check_multi_file_continuity(model, exp, files)
                if cont_issues:
                    print(f"    Multi-file continuity issues:")
                    for ci in cont_issues:
                        print(f"      {ci}")
                        all_issues.append(f"  [{model}/{exp}] {ci}")

    # Build summary DataFrame
    df = pd.DataFrame(results)
    summary_cols = [
        "model", "experiment", "file", "readable", "n_timesteps",
        "date_start", "date_end", "n_lat", "n_lon",
        "dod_min", "dod_max", "dod_mean", "ag_mean_dod",
        "n_negative", "nan_pct",
    ]
    df_out = df[[c for c in summary_cols if c in df.columns]]
    df_out.to_csv(os.path.join(OUT_DIR, "qaqc_cmip6_summary.csv"), index=False)

    # Model agreement for historical period (Arabian Gulf mean DOD)
    hist_results = [r for r in results if r.get("experiment") == "historical"]
    if hist_results:
        print(f"\n--- Model Agreement (Historical, Arabian Gulf mean DOD) ---")
        for r in hist_results:
            print(f"  {r.get('model', 'unknown'):<20} AG mean DOD: {r['ag_mean_dod']:.6f}"
                  if not np.isnan(r['ag_mean_dod']) else
                  f"  {r.get('model', 'unknown'):<20} AG mean DOD: N/A")

        ag_means = [r["ag_mean_dod"] for r in hist_results if not np.isnan(r["ag_mean_dod"])]
        if len(ag_means) > 1:
            print(f"  Range: {min(ag_means):.6f} – {max(ag_means):.6f}")
            print(f"  Std:   {np.std(ag_means):.6f}")
            print(f"  CV:    {np.std(ag_means)/np.mean(ag_means)*100:.1f}%")

    # Collect all issues from file checks
    for r in results:
        for issue in r["issues"]:
            all_issues.append(f"  [{r.get('model','?')}/{r.get('experiment','?')}/{r['file']}] {issue}")

    # Summary
    print(f"\n--- Summary ---")
    print(f"Models found:        {len(set(r.get('model') for r in results))}/{len(EXPECTED_MODELS)}")
    print(f"Files checked:       {len(results)}")
    print(f"All readable:        {all(r['readable'] for r in results)}")
    print(f"Missing combos:      {len(missing_combos)} ({', '.join(missing_combos) if missing_combos else 'none'})")

    if all_issues:
        print(f"\n--- Issues Found ({len(all_issues)}) ---")
        for issue in all_issues:
            print(issue)
    else:
        print(f"\nNo issues found. All checks passed.")

    overall_pass = len(all_issues) == 0
    return results, all_issues, overall_pass


if __name__ == "__main__":
    results, issues, passed = run_cmip6_qaqc()
    print(f"\nOverall: {'PASS' if passed else 'FAIL'}")
    sys.exit(0 if passed else 1)
