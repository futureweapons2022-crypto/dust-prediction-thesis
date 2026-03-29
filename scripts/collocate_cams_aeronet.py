"""
Collocate CAMS dust AOD forecasts with AERONET ground truth
============================================================
For each AERONET AOD measurement, find the matching CAMS forecast:
  - Spatial: nearest CAMS grid cell (0.4 deg resolution)
  - Temporal: nearest CAMS valid_time within +/- 1.5 hours
  - Uses the shortest lead time when multiple forecasts share a valid_time

Corrections applied:
  1. Wavelength interpolation: AERONET AOD_500 -> AOD_550 using Angstrom exponent
     AOD_550 = AOD_500 * (550/500)^(-AE_440_870)
  2. Dust filtering: multi-threshold Angstrom exponent classification
     CAMS duaod550 is dust-only; AERONET is total AOD. Comparing only during
     dust-dominated conditions (low AE) makes the comparison physically valid.

     Three thresholds following Di Tomaso et al. (2022, ESSD):
       - AE < 0.4: "pure dust" — Dubovik et al. (2002), Eck et al. (2008, Arabian Gulf)
       - AE < 0.6: "standard dust" — Dubovik et al. (2002), Toledano et al. (2007)
       - AE < 0.75: "mixed dust" — Basart et al. (2009), Di Tomaso et al. (2022)

Output: one CSV per station + one combined CSV in data/collocated/
  Reports stats for: all data, dust-only (AE < 0.5), and interpolated AOD_550
"""

import pandas as pd
import numpy as np
import xarray as xr
import os
import glob

# --- Paths ---
BASE = r"C:\Users\LENOVO\Desktop\THESIS"
CAMS_DIR = os.path.join(BASE, "data", "cams")
AERONET_DIR = os.path.join(BASE, "data", "aeronet")
OUTPUT_DIR = os.path.join(BASE, "data", "collocated")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Station definitions ---
STATIONS = [
    # Level 2.0
    {"name": "DEWA_ResearchCentre", "lat": 24.766847, "lon": 55.369125,
     "file": "level2/DEWA_ResearchCentre_AOD20_allpoints.csv", "level": "L2"},
    {"name": "Kuwait_University", "lat": 29.325, "lon": 47.971,
     "file": "level2/Kuwait_University_AOD20_allpoints.csv", "level": "L2"},
    {"name": "Masdar_Institute", "lat": 24.4416, "lon": 54.6166,
     "file": "level2/Masdar_Institute_AOD20_allpoints.csv", "level": "L2"},
    {"name": "Mezaira", "lat": 23.10452, "lon": 53.75466,
     "file": "level2/Mezaira_AOD20_allpoints.csv", "level": "L2"},
    {"name": "Shagaya_Park", "lat": 29.209072, "lon": 47.060528,
     "file": "level2/Shagaya_Park_AOD20_allpoints.csv", "level": "L2"},
    # Level 1.5
    {"name": "Khalifa_University", "lat": 24.418008, "lon": 54.501108,
     "file": "level15/Khalifa_University_AOD15_allpoints.csv", "level": "L1.5"},
    {"name": "Kuwait_University_2", "lat": 29.2576, "lon": 47.897,
     "file": "level15/Kuwait_University_2_AOD15_allpoints.csv", "level": "L1.5"},
    {"name": "Riyadh_Airport_SDSC", "lat": 24.925833, "lon": 46.72171,
     "file": "level15/Riyadh_Airport_SDSC_AOD15_allpoints.csv", "level": "L1.5"},
]

MAX_TIME_DELTA = pd.Timedelta("1.5h")

# Dust classification thresholds (Di Tomaso et al., 2022; Eck et al., 2008; Basart et al., 2009)
DUST_THRESHOLDS = {
    "pure_dust": 0.4,    # AE < 0.4 — Dubovik et al. (2002), Eck et al. (2008, Arabian Gulf)
    "standard_dust": 0.6, # AE < 0.6 — Dubovik et al. (2002), Toledano et al. (2007)
    "mixed_dust": 0.75,   # AE < 0.75 — Basart et al. (2009), Di Tomaso et al. (2022)
}


def parse_aeronet(filepath):
    """Parse AERONET CSV, return DataFrame with datetime, AOD_500, AE_440_870."""
    df = pd.read_csv(filepath, skiprows=7, na_values=["-999.", "-999.000000"])
    df.columns = df.columns.str.strip()

    last_col = df.columns[-1]
    if df[last_col].dtype == object:
        df[last_col] = df[last_col].str.replace("<br>", "", regex=False)

    df["datetime"] = pd.to_datetime(
        df["Date(dd:mm:yyyy)"] + " " + df["Time(hh:mm:ss)"],
        format="%d:%m:%Y %H:%M:%S",
    )

    aod_col = [c for c in df.columns if "AOD_500nm" in c
               and "Triplet" not in c and "Exact" not in c]
    df["AOD_500"] = pd.to_numeric(df[aod_col[0]], errors="coerce") if aod_col else np.nan

    ae_col = [c for c in df.columns if "440-870_Angstrom_Exponent" in c
              and "Triplet" not in c]
    df["AE_440_870"] = pd.to_numeric(df[ae_col[0]], errors="coerce") if ae_col else np.nan

    # Interpolate AOD to 550nm: AOD_550 = AOD_500 * (550/500)^(-AE)
    df["AOD_550"] = df["AOD_500"] * (550.0 / 500.0) ** (-df["AE_440_870"])

    # Flag dust-dominated observations using multi-threshold approach
    df["is_pure_dust"] = df["AE_440_870"] < DUST_THRESHOLDS["pure_dust"]       # AE < 0.4
    df["is_standard_dust"] = df["AE_440_870"] < DUST_THRESHOLDS["standard_dust"] # AE < 0.6
    df["is_mixed_dust"] = df["AE_440_870"] < DUST_THRESHOLDS["mixed_dust"]      # AE < 0.75
    df["is_dust"] = df["is_pure_dust"]  # Default: pure dust (AE < 0.4) for primary analysis

    return df[["datetime", "AOD_500", "AOD_550", "AE_440_870",
              "is_pure_dust", "is_standard_dust", "is_mixed_dust", "is_dust"]].dropna(subset=["AOD_500"])


def build_cams_lookup(ds, stn_lat, stn_lon):
    """
    Build a flat DataFrame of all CAMS valid_times at the nearest grid cell.
    Returns DataFrame with columns: valid_time, cams_duaod550, lead_time_hours, forecast_date
    When multiple forecasts share a valid_time, keep the shortest lead time.

    Vectorized version — uses numpy broadcasting instead of nested Python loops.
    """
    # Extract at nearest grid cell using xarray (handles dimension order)
    cell = ds["duaod550"].sel(
        latitude=stn_lat, longitude=stn_lon, method="nearest"
    )
    nearest_lat = float(cell.latitude)
    nearest_lon = float(cell.longitude)

    # Get values as 2D numpy array: (forecast_period, forecast_reference_time)
    values = cell.values  # shape: (n_periods, n_ref_times)
    ref_times = pd.DatetimeIndex(ds["forecast_reference_time"].values)
    periods = ds["forecast_period"].values  # timedelta64 array

    # Vectorized: compute valid_times and lead_hours using broadcasting
    # ref_times shape: (n_ref,), periods shape: (n_periods,)
    lead_hours = periods / np.timedelta64(1, "h")  # (n_periods,)

    # Build 2D grids: (n_periods, n_ref_times)
    ref_grid = np.tile(ref_times.values, (len(periods), 1))           # (n_p, n_r)
    period_grid = np.tile(periods[:, np.newaxis], (1, len(ref_times))) # (n_p, n_r)
    valid_grid = ref_grid + period_grid                                # (n_p, n_r)
    lead_grid = np.tile(lead_hours[:, np.newaxis], (1, len(ref_times)))# (n_p, n_r)

    # Flatten everything
    valid_flat = valid_grid.ravel()
    lead_flat = lead_grid.ravel()
    ref_flat = ref_grid.ravel()
    val_flat = values.ravel()

    # Remove NaN values
    mask = ~np.isnan(val_flat)
    if not mask.any():
        return pd.DataFrame(), nearest_lat, nearest_lon

    cams_df = pd.DataFrame({
        "valid_time": valid_flat[mask],
        "cams_duaod550": val_flat[mask],
        "lead_time_hours": lead_flat[mask],
        "forecast_date": ref_flat[mask],
    })

    # When multiple forecasts have the same valid_time, keep shortest lead time
    cams_df = cams_df.sort_values(["valid_time", "lead_time_hours"])
    cams_df = cams_df.drop_duplicates(subset="valid_time", keep="first")
    cams_df = cams_df.sort_values("valid_time").reset_index(drop=True)

    return cams_df, nearest_lat, nearest_lon


def collocate_station(station_info, cams_files):
    """Match AERONET measurements to CAMS forecasts for one station."""
    name = station_info["name"]
    stn_lat = station_info["lat"]
    stn_lon = station_info["lon"]

    aeronet_path = os.path.join(AERONET_DIR, station_info["file"])
    aeronet = parse_aeronet(aeronet_path)
    if len(aeronet) == 0:
        print(f"  {name}: no valid AERONET data")
        return pd.DataFrame()

    print(f"  {name}: {len(aeronet):,} AERONET obs "
          f"({aeronet['datetime'].min().strftime('%Y-%m')} to "
          f"{aeronet['datetime'].max().strftime('%Y-%m')})")

    # Build full CAMS lookup table across all months
    cams_parts = []
    nearest_lat = nearest_lon = None

    for cams_path in sorted(cams_files):
        ds = xr.open_dataset(cams_path)
        part, nlat, nlon = build_cams_lookup(ds, stn_lat, stn_lon)
        ds.close()
        if len(part) > 0:
            cams_parts.append(part)
            nearest_lat = nlat
            nearest_lon = nlon

    if not cams_parts:
        print(f"  {name}: no CAMS data at grid cell")
        return pd.DataFrame()

    cams_all = pd.concat(cams_parts, ignore_index=True)
    cams_all = cams_all.sort_values("valid_time").reset_index(drop=True)

    # Use merge_asof for fast temporal matching
    aeronet_sorted = aeronet.sort_values("datetime").reset_index(drop=True)

    merged = pd.merge_asof(
        aeronet_sorted,
        cams_all,
        left_on="datetime",
        right_on="valid_time",
        tolerance=MAX_TIME_DELTA,
        direction="nearest",
    )

    # Keep only matched rows
    matched = merged.dropna(subset=["cams_duaod550"]).copy()

    if len(matched) == 0:
        print(f"  {name}: no collocations in available CAMS period")
        return pd.DataFrame()

    matched["time_delta_minutes"] = (
        (matched["datetime"] - matched["valid_time"]).abs().dt.total_seconds() / 60
    )

    # Error using raw AOD_500 (for reference)
    matched["error_raw"] = matched["cams_duaod550"] - matched["AOD_500"]

    # Error using interpolated AOD_550 (wavelength-corrected)
    matched["error_550"] = matched["cams_duaod550"] - matched["AOD_550"]
    matched["abs_error_550"] = matched["error_550"].abs()

    # Build output
    result = pd.DataFrame({
        "station": name,
        "level": station_info["level"],
        "datetime": matched["datetime"],
        "lat": stn_lat,
        "lon": stn_lon,
        "grid_lat": nearest_lat,
        "grid_lon": nearest_lon,
        "aeronet_aod500": matched["AOD_500"],
        "aeronet_aod550": matched["AOD_550"],
        "aeronet_ae": matched["AE_440_870"],
        "is_pure_dust": matched["is_pure_dust"],
        "is_standard_dust": matched["is_standard_dust"],
        "is_mixed_dust": matched["is_mixed_dust"],
        "is_dust": matched["is_dust"],
        "cams_duaod550": matched["cams_duaod550"],
        "lead_time_hours": matched["lead_time_hours"],
        "forecast_date": matched["forecast_date"],
        "time_delta_minutes": matched["time_delta_minutes"],
        "error_raw": matched["error_raw"],
        "error": matched["error_550"],
        "abs_error": matched["abs_error_550"],
    })

    print(f"  {name}: {len(result):,} collocations "
          f"({matched['datetime'].min().strftime('%Y-%m')} to "
          f"{matched['datetime'].max().strftime('%Y-%m')})")
    return result


# --- Main ---
print("=" * 70)
print("CAMS-AERONET COLLOCATION")
print("=" * 70)

cams_files = sorted(glob.glob(os.path.join(CAMS_DIR, "cams_duaod550_*.nc")))
print(f"\nCAMS monthly files available: {len(cams_files)}")
for f in cams_files:
    print(f"  {os.path.basename(f)}")

all_results = []

print(f"\nCollocating {len(STATIONS)} stations...\n")
for stn in STATIONS:
    result = collocate_station(stn, cams_files)
    if len(result) > 0:
        out_path = os.path.join(OUTPUT_DIR, f"collocated_{stn['name']}.csv")
        result.to_csv(out_path, index=False)
        all_results.append(result)

if all_results:
    combined = pd.concat(all_results, ignore_index=True)
    combined_path = os.path.join(OUTPUT_DIR, "collocated_all_stations.csv")
    combined.to_csv(combined_path, index=False)

    def print_stats(label, subset):
        """Print ME, MAE, RMSE, R for a subset."""
        if len(subset) == 0:
            print(f"  {label}: no data")
            return
        me = subset["error"].mean()
        mae = subset["abs_error"].mean()
        rmse = np.sqrt((subset["error"] ** 2).mean())
        cols = subset[["aeronet_aod550", "cams_duaod550"]].dropna()
        r = cols.corr().iloc[0, 1] if len(cols) > 2 else np.nan
        print(f"  {label}")
        print(f"    n={len(subset):,}  ME={me:+.4f}  MAE={mae:.4f}  RMSE={rmse:.4f}  R={r:.3f}")

    has_ae = combined[combined["aeronet_ae"].notna()]

    print(f"\n{'=' * 70}")
    print(f"COLLOCATION SUMMARY")
    print(f"{'=' * 70}")
    print(f"Total collocations: {len(combined):,}")
    print(f"  With valid AE (can interpolate to 550nm): {len(has_ae):,}")
    for label, col in [("Pure dust (AE<0.4)", "is_pure_dust"),
                        ("Standard dust (AE<0.6)", "is_standard_dust"),
                        ("Mixed dust (AE<0.75)", "is_mixed_dust")]:
        n = combined[col].sum()
        pct = n / len(has_ae) * 100 if len(has_ae) > 0 else 0
        print(f"  {label}: {n:,} ({pct:.1f}% of AE-valid)")

    # --- Comparison: raw 500nm vs corrected 550nm ---
    print(f"\n--- Effect of wavelength correction ---")
    raw_me = combined["error_raw"].mean()
    raw_mae = combined["error_raw"].abs().mean()
    print(f"  Raw (CAMS 550 vs AERONET 500):          ME={raw_me:+.4f}  MAE={raw_mae:.4f}")
    corr = has_ae["error"].mean()
    corr_mae = has_ae["abs_error"].mean()
    print(f"  Corrected (CAMS 550 vs AERONET 550):    ME={corr:+.4f}  MAE={corr_mae:.4f}")

    # --- All data with AOD_550 ---
    print(f"\n--- All data (CAMS dust AOD vs AERONET total AOD at 550nm) ---")
    print_stats("Overall", has_ae)
    print(f"\n  Per station:")
    for name, grp in has_ae.groupby("station"):
        g = grp
        me = g["error"].mean()
        mae = g["abs_error"].mean()
        rmse = np.sqrt((g["error"] ** 2).mean())
        cols = g[["aeronet_aod550", "cams_duaod550"]].dropna()
        r = cols.corr().iloc[0, 1] if len(cols) > 2 else np.nan
        print(f"    {name:25s}  n={len(g):>6,}  ME={me:+.4f}  MAE={mae:.4f}  RMSE={rmse:.4f}  R={r:.3f}")

    # --- Multi-threshold dust analysis ---
    for label, col, ae_val in [
        ("Pure dust (AE < 0.4) — Eck et al. (2008), Dubovik et al. (2002)", "is_pure_dust", 0.4),
        ("Standard dust (AE < 0.6) — Dubovik et al. (2002), Di Tomaso et al. (2022)", "is_standard_dust", 0.6),
        ("Mixed dust (AE < 0.75) — Basart et al. (2009)", "is_mixed_dust", 0.75),
    ]:
        dust = combined[combined[col] == True]
        print(f"\n--- {label} ---")
        print_stats("Overall", dust)
        if len(dust) > 0:
            print(f"\n  Per station:")
            for name, grp in dust.groupby("station"):
                me = grp["error"].mean()
                mae = grp["abs_error"].mean()
                rmse = np.sqrt((grp["error"] ** 2).mean())
                cols = grp[["aeronet_aod550", "cams_duaod550"]].dropna()
                r = cols.corr().iloc[0, 1] if len(cols) > 2 else np.nan
                print(f"    {name:25s}  n={len(grp):>6,}  ME={me:+.4f}  MAE={mae:.4f}  RMSE={rmse:.4f}  R={r:.3f}")

    # Lead time analysis (pure dust — primary threshold)
    pure_dust = combined[combined["is_pure_dust"] == True]
    if len(pure_dust) > 0:
        print(f"\n--- Lead time analysis (pure dust, AE < 0.4) ---")
        lt_stats = pure_dust.groupby("lead_time_hours")["abs_error"].agg(["mean", "count"])
        for lt, row in lt_stats.iterrows():
            if row["count"] >= 10:
                bar = "#" * int(row["mean"] * 20)
                print(f"  {lt:5.0f}h: MAE={row['mean']:.4f} (n={int(row['count']):>5}) {bar}")

    print(f"\nSaved: {combined_path}")
    print(f"{'=' * 70}")
else:
    print("\nNo collocations found across any station.")
