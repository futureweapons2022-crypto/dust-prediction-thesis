"""
Download MODIS Deep Blue AOD (550nm) from MOD08_D3 via OPeNDAP
===============================================================
Extracts daily 1° grid cell values at each AERONET station location.
Purpose: Third-layer verification of AERONET readings independent of CAMS.

Product: MOD08_D3 v061 (MODIS/Terra Atmosphere Daily L3 Global 1Deg CMG)
Variables:
  - Deep_Blue_Aerosol_Optical_Depth_550_Land_Mean (works over desert)
  - AOD_550_Dark_Target_Deep_Blue_Combined_Mean (merged product)
Grid: 1° x 1°, global (180 lat x 360 lon)
Scale factor: 0.001 (raw integer / 1000 = AOD)
Fill value: -9999

References:
  - Hsu et al. (2013) for Deep Blue algorithm over bright surfaces
  - Levy et al. (2013) for Dark Target algorithm
  - Sayer et al. (2019) for combined DT+DB product
"""

import requests
import numpy as np
import pandas as pd
import os
import json
import time
from datetime import datetime, timedelta

# --- Config ---
BASE = r"C:\Users\LENOVO\Desktop\THESIS"
OUTPUT_DIR = os.path.join(BASE, "data", "modis")
os.makedirs(OUTPUT_DIR, exist_ok=True)

EARTHDATA_USER = "daone2028"
EARTHDATA_PASS = "Realmadrid77@77"

STATIONS = {
    "Kuwait_University":    {"lat": 29.325, "lon": 47.971},
    "Shagaya_Park":         {"lat": 29.209, "lon": 47.061},
    "Kuwait_University_2":  {"lat": 29.258, "lon": 47.897},
    "Mezaira":              {"lat": 23.105, "lon": 53.755},
    "Masdar_Institute":     {"lat": 24.442, "lon": 54.617},
    "DEWA_ResearchCentre":  {"lat": 24.767, "lon": 55.369},
    "Riyadh_Airport_SDSC":  {"lat": 24.926, "lon": 46.722},
}

VARIABLES = {
    "db_aod550": "Deep_Blue_Aerosol_Optical_Depth_550_Land_Mean",
    "dtdb_aod550": "AOD_550_Dark_Target_Deep_Blue_Combined_Mean",
}

SCALE_FACTOR = 0.001
FILL_VALUE = -9999

# Sub-region covering all stations: lat 20-34N, lon 45-60E
Y1, Y2 = 55, 69    # lat 34N to 20N
X1, X2 = 225, 240   # lon 45E to 60E

START_YEAR = 2015
END_YEAR = 2024


def latlon_to_subgrid(lat, lon):
    y_global = 89 - int(np.floor(lat))
    x_global = int(np.floor(lon)) + 180
    return y_global - Y1, x_global - X1


def parse_opendap_ascii(text, ny, nx):
    arr = np.full((ny, nx), np.nan)
    for line in text.strip().split("\n"):
        if "[" in line and "," in line:
            try:
                bracket = line.index("[")
                close = line.index("]")
                row = int(line[bracket+1:close])
                vals = line.split(",")[1:]
                for col, v in enumerate(vals):
                    raw = int(v.strip())
                    if raw != FILL_VALUE:
                        arr[row, col] = raw * SCALE_FACTOR
            except (ValueError, IndexError):
                continue
    return arr


def extract_day(session, year, doy, fname):
    opendap_base = (
        f"https://ladsweb.modaps.eosdis.nasa.gov/opendap/RemoteResources/laads/"
        f"allData/61/MOD08_D3/{year}/{doy}/{fname}"
    )

    ny = Y2 - Y1 + 1
    nx = X2 - X1 + 1
    grids = {}

    for short_name, full_name in VARIABLES.items():
        url = f"{opendap_base}.ascii?{full_name}[{Y1}:{Y2}][{X1}:{X2}]"
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 200:
                grids[short_name] = parse_opendap_ascii(resp.text, ny, nx)
            else:
                grids[short_name] = np.full((ny, nx), np.nan)
        except Exception:
            grids[short_name] = np.full((ny, nx), np.nan)

    return grids


def main():
    session = requests.Session()
    session.auth = (EARTHDATA_USER, EARTHDATA_PASS)

    # Load cached filenames
    cache_path = os.path.join(OUTPUT_DIR, "mod08d3_filenames.json")
    with open(cache_path) as f:
        fname_cache = json.load(f)
    print(f"Loaded {len(fname_cache)} cached filenames")

    # Pre-compute sub-grid indices
    stn_idx = {}
    for name, coords in STATIONS.items():
        sy, sx = latlon_to_subgrid(coords["lat"], coords["lon"])
        stn_idx[name] = (sy, sx)
        print(f"  {name}: ({coords['lat']:.1f}N, {coords['lon']:.1f}E) -> subgrid[{sy},{sx}]")

    all_rows = []

    for year in range(START_YEAR, END_YEAR + 1):
        print(f"\n{'='*50}")
        print(f"Year {year}")
        print(f"{'='*50}")

        # Check for existing checkpoint
        ckpt = os.path.join(OUTPUT_DIR, f"modis_aod_{year}.csv")
        if os.path.exists(ckpt):
            df_ckpt = pd.read_csv(ckpt)
            all_rows.extend(df_ckpt.to_dict("records"))
            print(f"  Loaded checkpoint: {len(df_ckpt)} rows")
            continue

        # Get files for this year from cache
        year_files = {}
        for key, fname in fname_cache.items():
            y, d = key.split("_")
            if int(y) == year:
                year_files[d] = fname

        print(f"  {len(year_files)} days to process")
        year_rows = []
        errors = 0

        for i, (doy, fname) in enumerate(sorted(year_files.items())):
            date = datetime(year, 1, 1) + timedelta(days=int(doy) - 1)

            grids = extract_day(session, year, doy, fname)

            for stn_name, (sy, sx) in stn_idx.items():
                row = {
                    "date": date.strftime("%Y-%m-%d"),
                    "station": stn_name,
                    "modis_db_aod550": grids["db_aod550"][sy, sx],
                    "modis_dtdb_aod550": grids["dtdb_aod550"][sy, sx],
                }
                year_rows.append(row)

            if (i + 1) % 50 == 0:
                last_n = len(STATIONS) * 50
                valid_db = sum(1 for r in year_rows[-last_n:] if not np.isnan(r["modis_db_aod550"]))
                print(f"  {date.strftime('%Y-%m-%d')} ({i+1}/{len(year_files)}) "
                      f"valid: {valid_db}/{last_n}")

            time.sleep(0.05)

        # Save yearly
        df_year = pd.DataFrame(year_rows)
        df_year.to_csv(ckpt, index=False)
        valid = df_year["modis_db_aod550"].notna().sum()
        total = len(df_year)
        print(f"  Saved {total} rows ({valid} valid Deep Blue, {valid/total*100:.0f}%)")
        all_rows.extend(year_rows)

    # Save combined
    df_all = pd.DataFrame(all_rows)
    out_path = os.path.join(OUTPUT_DIR, "modis_aod_all_stations.csv")
    df_all.to_csv(out_path, index=False)

    print(f"\n{'='*50}")
    print(f"DONE: {len(df_all)} total rows")
    print(f"Valid Deep Blue: {df_all['modis_db_aod550'].notna().sum()} "
          f"({df_all['modis_db_aod550'].notna().mean()*100:.1f}%)")
    print(f"Valid Combined:  {df_all['modis_dtdb_aod550'].notna().sum()} "
          f"({df_all['modis_dtdb_aod550'].notna().mean()*100:.1f}%)")
    print(f"Saved to: {out_path}")


if __name__ == "__main__":
    main()
