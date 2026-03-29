"""
Tier 3 AERONET Station Analysis (Level 1.5)
=============================================
Analyze Riyadh_Airport_SDSC, Kuwait_University_2, Khalifa_University
Same statistics as the Tier 1-2 analysis in the worklog.
"""

import pandas as pd
import numpy as np
import os

DATA_DIR = r"C:\Users\LENOVO\Desktop\THESIS\data\aeronet\level15"

STATIONS = [
    "Riyadh_Airport_SDSC_AOD15_allpoints.csv",
    "Kuwait_University_2_AOD15_allpoints.csv",
    "Khalifa_University_AOD15_allpoints.csv",
]


def parse_aeronet(filepath):
    df = pd.read_csv(filepath, skiprows=7, na_values=["-999.", "-999.000000"])
    df.columns = df.columns.str.strip()
    last_col = df.columns[-1]
    if df[last_col].dtype == object:
        df[last_col] = df[last_col].str.replace("<br>", "", regex=False)

    df["datetime"] = pd.to_datetime(
        df["Date(dd:mm:yyyy)"] + " " + df["Time(hh:mm:ss)"],
        format="%d:%m:%Y %H:%M:%S",
    )

    # AOD 500nm
    aod_col = [c for c in df.columns if "AOD_500nm" in c and "Triplet" not in c and "Exact" not in c]
    df["AOD_500"] = pd.to_numeric(df[aod_col[0]], errors="coerce") if aod_col else np.nan

    # Angstrom exponent 440-870
    ae_col = [c for c in df.columns if "440-870_Angstrom_Exponent" in c and "Triplet" not in c]
    df["AE_440_870"] = pd.to_numeric(df[ae_col[0]], errors="coerce") if ae_col else np.nan

    return df


print("=" * 80)
print("TIER 3 AERONET STATION ANALYSIS (Level 1.5)")
print("=" * 80)

for fname in STATIONS:
    filepath = os.path.join(DATA_DIR, fname)
    station_name = fname.split("_AOD")[0].replace("_", " ")

    print(f"\n{'-' * 70}")
    print(f"  {station_name}")
    print(f"{'-' * 70}")

    df = parse_aeronet(filepath)

    # Filter valid AOD
    valid = df[df["AOD_500"].notna()].copy()
    total_rows = len(df)
    valid_rows = len(valid)

    print(f"\n  Total rows:     {total_rows:,}")
    print(f"  Valid AOD_500:  {valid_rows:,} ({valid_rows/total_rows*100:.1f}%)")

    if valid_rows == 0:
        print("  NO VALID DATA")
        continue

    # Period
    first = valid["datetime"].min()
    last = valid["datetime"].max()
    print(f"  Period:         {first.strftime('%Y-%m-%d')} to {last.strftime('%Y-%m-%d')}")

    # Basic stats
    aod = valid["AOD_500"]
    print(f"\n  AOD_500nm Statistics:")
    print(f"    Mean:     {aod.mean():.3f}")
    print(f"    Median:   {aod.median():.3f}")
    print(f"    Std:      {aod.std():.3f}")
    print(f"    Min:      {aod.min():.3f}")
    print(f"    Max:      {aod.max():.3f}")
    print(f"    P25:      {aod.quantile(0.25):.3f}")
    print(f"    P75:      {aod.quantile(0.75):.3f}")
    print(f"    P95:      {aod.quantile(0.95):.3f}")
    print(f"    P99:      {aod.quantile(0.99):.3f}")

    # Dust fraction (Angstrom < 0.5)
    ae_valid = valid[valid["AE_440_870"].notna()]
    if len(ae_valid) > 0:
        dust = ae_valid[ae_valid["AE_440_870"] < 0.5]
        dust_pct = len(dust) / len(ae_valid) * 100
        print(f"\n  Dust Identification (AE < 0.5):")
        print(f"    Valid AE measurements: {len(ae_valid):,}")
        print(f"    Dust-dominated:        {len(dust):,} ({dust_pct:.1f}%)")
    else:
        print(f"\n  Dust Identification: No valid AE data")

    # High AOD events (>0.8 threshold from proposal)
    high_aod = valid[valid["AOD_500"] > 0.8]
    high_pct = len(high_aod) / valid_rows * 100
    print(f"\n  High AOD Events (AOD > 0.8):")
    print(f"    Count:  {len(high_aod):,} ({high_pct:.1f}% of measurements)")

    # Extreme events (>1.5)
    extreme = valid[valid["AOD_500"] > 1.5]
    print(f"    Extreme (AOD > 1.5): {len(extreme):,} ({len(extreme)/valid_rows*100:.2f}%)")

    # Monthly breakdown
    valid["month"] = valid["datetime"].dt.month
    valid["year"] = valid["datetime"].dt.year
    monthly_mean = valid.groupby("month")["AOD_500"].agg(["mean", "count"])

    print(f"\n  Monthly AOD_500 (mean | count):")
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    peak_month = None
    peak_val = 0
    for m in range(1, 13):
        if m in monthly_mean.index:
            mean_val = monthly_mean.loc[m, "mean"]
            count = int(monthly_mean.loc[m, "count"])
            bar = "#" * int(mean_val * 20)
            print(f"    {month_names[m-1]}: {mean_val:.3f} ({count:>6,}) {bar}")
            if mean_val > peak_val:
                peak_val = mean_val
                peak_month = month_names[m-1]
        else:
            print(f"    {month_names[m-1]}: —")

    print(f"    Peak: {peak_month} ({peak_val:.2f})")

    # Yearly breakdown
    yearly = valid.groupby("year")["AOD_500"].agg(["mean", "count"])
    print(f"\n  Yearly AOD_500 (mean | count):")
    for y, row in yearly.iterrows():
        print(f"    {y}: {row['mean']:.3f} ({int(row['count']):>6,})")

print(f"\n{'=' * 80}")
print("ANALYSIS COMPLETE")
print(f"{'=' * 80}")
