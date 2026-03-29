"""
Phase 2 Step 1: Feature Engineering for Meta-Model
====================================================
Merges collocated CAMS-AERONET errors with ERA5 meteorological features.
Produces a single ML-ready CSV.

Each row = one (station, date, lead_time) combination.
ERA5 features are the same for a given (station, date).
CAMS forecast + error vary by lead time.

Target: Binary classification (Reliable / Unreliable)
  - Unreliable = abs_error > 1.5 * station climatological std dev
"""

import pandas as pd
import numpy as np
import xarray as xr
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

DATA_DIR = Path(r"C:\Users\LENOVO\Desktop\THESIS\data")
ERA5_DIR = DATA_DIR / "era5"
OUT_DIR = DATA_DIR / "meta_model"
OUT_DIR.mkdir(exist_ok=True)

STATION_COORDS = {
    'DEWA_ResearchCentre': (24.767, 55.369),
    'Kuwait_University': (29.326, 47.972),
    'Kuwait_University_2': (29.326, 47.972),
    'Masdar_Institute': (24.442, 54.617),
    'Mezaira': (23.145, 53.779),
    'Riyadh_Airport_SDSC': (24.712, 46.725),
    'Shagaya_Park': (29.204, 47.070),
}

# ─── Step 1: Load and aggregate collocated data per (station, date, lead_time) ───
print("Loading collocated CAMS-AERONET data...")
colloc = pd.read_csv(DATA_DIR / "collocated" / "collocated_all_stations.csv")
colloc['datetime'] = pd.to_datetime(colloc['datetime'])
colloc['date'] = colloc['datetime'].dt.date

print(f"  Raw rows: {len(colloc)}")

# Average multiple AERONET obs on the same day at the same lead time
# (e.g., 10 AERONET readings at noon all matched to CAMS lead_time=12h)
grouped = (colloc.groupby(['station', 'date', 'lead_time_hours'])
           .agg(
               aeronet_aod550=('aeronet_aod550', 'mean'),
               aeronet_ae=('aeronet_ae', 'mean'),
               cams_duaod550=('cams_duaod550', 'mean'),
               error=('error', 'mean'),
               abs_error=('abs_error', 'mean'),
               is_dust=('is_dust', 'mean'),
               n_obs=('aeronet_aod550', 'count'),
           )
           .reset_index())

grouped['date'] = pd.to_datetime(grouped['date'])
grouped['year'] = grouped['date'].dt.year
grouped['month'] = grouped['date'].dt.month

print(f"  Grouped (station, date, lead_time) rows: {len(grouped)}")
print(f"  Stations: {grouped['station'].nunique()}")

# ─── Step 2: Compute target variable ───
print("\nComputing target (unreliable flag)...")
clim_std = grouped.groupby('station')['error'].std().to_dict()
print("  Climatological std dev per station:")
for st, sd in sorted(clim_std.items()):
    print(f"    {st}: {sd:.4f}")

grouped['clim_std'] = grouped['station'].map(clim_std)
grouped['unreliable'] = (grouped['abs_error'] > 1.5 * grouped['clim_std']).astype(int)

print(f"\n  Unreliable rate: {grouped['unreliable'].mean()*100:.1f}%")
for st in sorted(grouped['station'].unique()):
    sub = grouped[grouped['station'] == st]
    print(f"    {st}: {sub['unreliable'].mean()*100:.1f}% ({sub['unreliable'].sum()}/{len(sub)})")

# ─── Step 3: Load pre-extracted ERA5 features (from first run) ───
# The ERA5 features only depend on (station, date), not lead_time.
# Reuse the extraction logic but cache per (station, date).
print("\nExtracting ERA5 features (per station per day)...")

def find_nearest_idx(arr, val):
    return int(np.abs(arr - val).argmin())

def extract_era5_for_station(station, lat, lon, dates):
    results = []
    date_groups = {}
    for d in dates:
        key = f"{d.year}{d.month:02d}"
        if key not in date_groups:
            date_groups[key] = []
        date_groups[key].append(d)

    for ym, month_dates in sorted(date_groups.items()):
        pl_path = ERA5_DIR / f"era5_pl_all_{ym}.nc"
        sl_inst_path = ERA5_DIR / f"era5_sl_instant_{ym}.nc"
        sl_accum_path = ERA5_DIR / f"era5_sl_accum_{ym}.nc"

        if not pl_path.exists() or not sl_inst_path.exists():
            continue

        try:
            ds_pl = xr.open_dataset(pl_path)
            ds_sl = xr.open_dataset(sl_inst_path)
            ds_acc = xr.open_dataset(sl_accum_path) if sl_accum_path.exists() else None

            lat_idx = find_nearest_idx(ds_pl.latitude.values, lat)
            lon_idx = find_nearest_idx(ds_pl.longitude.values, lon)
            lat_idx_sl = find_nearest_idx(ds_sl.latitude.values, lat)
            lon_idx_sl = find_nearest_idx(ds_sl.longitude.values, lon)

            for d in month_dates:
                row = {'station': station, 'date': d}
                target_time = np.datetime64(f"{d.strftime('%Y-%m-%d')}T12:00:00")
                time_idx = find_nearest_idx(ds_pl.valid_time.values.astype('datetime64[ns]'), target_time)

                for level in [850, 700, 500]:
                    level_pos = find_nearest_idx(ds_pl.pressure_level.values, level)
                    u = float(ds_pl['u'].values[time_idx, level_pos, lat_idx, lon_idx])
                    v = float(ds_pl['v'].values[time_idx, level_pos, lat_idx, lon_idx])
                    t = float(ds_pl['t'].values[time_idx, level_pos, lat_idx, lon_idx])
                    r = float(ds_pl['r'].values[time_idx, level_pos, lat_idx, lon_idx])
                    z = float(ds_pl['z'].values[time_idx, level_pos, lat_idx, lon_idx])
                    row[f'u_{level}'] = u
                    row[f'v_{level}'] = v
                    row[f'ws_{level}'] = np.sqrt(u**2 + v**2)
                    row[f'wd_{level}'] = (270 - np.degrees(np.arctan2(v, u))) % 360
                    row[f't_{level}'] = t
                    row[f'rh_{level}'] = r
                    row[f'z_{level}'] = z

                row['wind_shear_850_500'] = row['ws_500'] - row['ws_850']
                row['wind_shear_850_700'] = row['ws_700'] - row['ws_850']
                row['temp_gradient_850_500'] = (row['t_500'] - row['t_850']) / (row['z_500'] - row['z_850'] + 1e-6) * 1000
                row['temp_gradient_850_700'] = (row['t_700'] - row['t_850']) / (row['z_700'] - row['z_850'] + 1e-6) * 1000

                time_idx_sl = find_nearest_idx(ds_sl.valid_time.values.astype('datetime64[ns]'), target_time)
                for var in ['u10', 'v10', 'i10fg', 't2m', 'skt', 'd2m', 'tcwv', 'blh', 'cape', 'sp', 'swvl1', 'lcc', 'hcc', 'lai_lv', 'fal']:
                    if var in ds_sl:
                        row[var] = float(ds_sl[var].values[time_idx_sl, lat_idx_sl, lon_idx_sl])

                row['ws10'] = np.sqrt(row.get('u10',0)**2 + row.get('v10',0)**2)
                row['wd10'] = (270 - np.degrees(np.arctan2(row.get('v10',0), row.get('u10',0)))) % 360
                row['humidity_deficit'] = row.get('t2m',0) - row.get('d2m',0)
                row['skt_t2m_diff'] = row.get('skt',0) - row.get('t2m',0)

                if ds_acc is not None:
                    time_idx_acc = find_nearest_idx(ds_acc.valid_time.values.astype('datetime64[ns]'), target_time)
                    lat_idx_acc = find_nearest_idx(ds_acc.latitude.values, lat)
                    lon_idx_acc = find_nearest_idx(ds_acc.longitude.values, lon)
                    for var in ['tp', 'e', 'ssrd', 'strd']:
                        if var in ds_acc:
                            row[var] = float(ds_acc[var].values[time_idx_acc, lat_idx_acc, lon_idx_acc])

                results.append(row)

            ds_pl.close()
            ds_sl.close()
            if ds_acc is not None:
                ds_acc.close()
        except Exception as ex:
            print(f"    Error {ym} {station}: {ex}")
            continue

    return results

# Get unique dates per station
unique_dates = grouped.groupby('station')['date'].apply(lambda x: sorted(x.unique())).to_dict()

all_era5 = []
for station, (lat, lon) in STATION_COORDS.items():
    if station not in unique_dates:
        continue
    dates_py = [pd.Timestamp(d).to_pydatetime() for d in unique_dates[station]]
    print(f"  {station}: {len(dates_py)} unique dates...", end=" ", flush=True)
    rows = extract_era5_for_station(station, lat, lon, dates_py)
    all_era5.extend(rows)
    print(f"got {len(rows)}")

era5_df = pd.DataFrame(all_era5)
era5_df['date'] = pd.to_datetime(era5_df['date'])
print(f"\nERA5 daily features: {len(era5_df)} rows")

# ─── Step 4: Merge — each (station, date, lead_time) row gets ERA5 features ───
print("\nMerging: (station, date, lead_time) x ERA5...")
merged = pd.merge(grouped, era5_df, on=['station', 'date'], how='inner')
print(f"  Merged rows: {len(merged)}")

# ─── Step 5: Add temporal features ───
print("Adding temporal + spatial features...")
merged['month_sin'] = np.sin(2 * np.pi * merged['month'] / 12)
merged['month_cos'] = np.cos(2 * np.pi * merged['month'] / 12)
merged['day_of_year'] = merged['date'].dt.dayofyear
merged['doy_sin'] = np.sin(2 * np.pi * merged['day_of_year'] / 365)
merged['doy_cos'] = np.cos(2 * np.pi * merged['day_of_year'] / 365)

# Recent dust activity: 7-day rolling of CAMS per station (use daily mean across lead times)
print("Computing recent dust activity (7-day rolling)...")
daily_cams = merged.groupby(['station', 'date'])['cams_duaod550'].mean().reset_index(name='cams_daily_mean')
daily_cams = daily_cams.sort_values(['station', 'date'])
daily_cams['cams_7d_mean'] = daily_cams.groupby('station')['cams_daily_mean'].transform(
    lambda x: x.rolling(7, min_periods=1).mean())
daily_cams['cams_7d_std'] = daily_cams.groupby('station')['cams_daily_mean'].transform(
    lambda x: x.rolling(7, min_periods=1).std().fillna(0))
merged = pd.merge(merged, daily_cams[['station', 'date', 'cams_7d_mean', 'cams_7d_std']],
                   on=['station', 'date'], how='left')

# Spatial
merged['lat'] = merged['station'].map({k: v[0] for k, v in STATION_COORDS.items()})
merged['lon'] = merged['station'].map({k: v[1] for k, v in STATION_COORDS.items()})

# ─── Summary ───
print(f"\n{'='*60}")
print(f"FINAL DATASET SUMMARY")
print(f"{'='*60}")
print(f"Total rows: {len(merged)}")
print(f"Stations: {merged['station'].nunique()}")
print(f"Date range: {merged['date'].min().strftime('%Y-%m-%d')} to {merged['date'].max().strftime('%Y-%m-%d')}")
print(f"Lead times: {sorted(merged['lead_time_hours'].unique())}")
print(f"Features: {len(merged.columns)} columns")
print(f"Target (unreliable): {merged['unreliable'].sum()} / {len(merged)} = {merged['unreliable'].mean()*100:.1f}%")

# Train/test split preview
train = merged[merged['year'] <= 2020]
test = merged[merged['year'] >= 2021]
print(f"\nTrain (2015-2020): {len(train)} rows, unreliable={train['unreliable'].mean()*100:.1f}%")
print(f"Test  (2021-2024): {len(test)} rows, unreliable={test['unreliable'].mean()*100:.1f}%")

print(f"\nPer station:")
for st in sorted(merged['station'].unique()):
    sub = merged[merged['station'] == st]
    tr = sub[sub['year'] <= 2020]
    te = sub[sub['year'] >= 2021]
    print(f"  {st}: {len(sub)} rows ({len(tr)} train / {len(te)} test), "
          f"{sub['date'].dt.year.min()}-{sub['date'].dt.year.max()}, "
          f"unreliable={sub['unreliable'].mean()*100:.1f}%")

# ─── Save ───
out_path = OUT_DIR / "meta_features.csv"
merged.to_csv(out_path, index=False)
print(f"\nSaved to {out_path}")

# Feature list (exclude target, identifiers, raw errors)
exclude = {'station', 'date', 'year', 'month', 'day_of_year',
           'aeronet_aod550', 'aeronet_ae', 'error', 'abs_error',
           'clim_std', 'unreliable', 'n_obs'}
feature_cols = sorted([c for c in merged.columns if c not in exclude])
print(f"\nFeature columns ({len(feature_cols)}):")
for c in feature_cols:
    print(f"  {c}")

with open(OUT_DIR / "feature_columns.txt", 'w') as f:
    f.write('\n'.join(feature_cols))

print("\nDone!")
