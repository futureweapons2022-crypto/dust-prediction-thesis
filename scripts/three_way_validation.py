"""
Three-Way Validation: MODIS vs AERONET vs CAMS
================================================
For each station, computes pairwise validation stats and generates scatter plots.

Comparisons:
1. MODIS (Combined DT+DB AOD 550nm) vs AERONET (AOD 550nm, daily avg)
2. CAMS (DOD 550nm, T+0 daily avg) vs AERONET (AOD 550nm, daily avg)
3. MODIS vs CAMS

Outputs:
- three_way_stats.csv          — stats table
- three_way_scatter_{station}.png — per-station scatter (3 panels)
- three_way_summary.png        — all stations combined figure
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Paths
DATA_DIR = Path(r"C:\Users\LENOVO\Desktop\THESIS\data")
OUT_DIR = DATA_DIR / "validation"
OUT_DIR.mkdir(exist_ok=True)

# ─── Load MODIS ───
print("Loading MODIS...")
modis = pd.read_csv(DATA_DIR / "modis" / "modis_aod_all_stations.csv")
modis['date'] = pd.to_datetime(modis['date'])
# Use Combined DT+DB product (better coverage than Deep Blue alone)
modis = modis[['date', 'station', 'modis_dtdb_aod550']].dropna(subset=['modis_dtdb_aod550'])
print(f"  MODIS rows (non-null): {len(modis)}")

# ─── Load Collocated (AERONET + CAMS) ───
print("Loading collocated AERONET-CAMS data...")
colloc = pd.read_csv(DATA_DIR / "collocated" / "collocated_all_stations.csv")
colloc['datetime'] = pd.to_datetime(colloc['datetime'])
colloc['date'] = colloc['datetime'].dt.date

# Daily average AERONET AOD 550nm
print("  Computing daily AERONET averages...")
aeronet_daily = (colloc.groupby(['station', 'date'])
                 .agg(aeronet_aod550=('aeronet_aod550', 'mean'),
                      aeronet_ae=('aeronet_ae', 'mean'),
                      n_aeronet_obs=('aeronet_aod550', 'count'))
                 .reset_index())
aeronet_daily['date'] = pd.to_datetime(aeronet_daily['date'])
print(f"  AERONET daily records: {len(aeronet_daily)}")

# Daily average CAMS DOD 550nm (T+0 only for fairest comparison)
print("  Computing daily CAMS T+0 averages...")
cams_t0 = colloc[colloc['lead_time_hours'] == 0].copy()
if len(cams_t0) == 0:
    # If no exact T+0, use shortest lead time per day
    print("  No exact T+0 found, using shortest lead time per day...")
    colloc['date_tmp'] = colloc['datetime'].dt.date
    idx = colloc.groupby(['station', 'date_tmp'])['lead_time_hours'].idxmin()
    cams_t0 = colloc.loc[idx].copy()

cams_daily = (cams_t0.groupby(['station', colloc.loc[cams_t0.index, 'datetime'].dt.date.rename('date')])
              if len(cams_t0) > 0 else None)

# Simpler approach: daily average CAMS from all lead times <= 12h
cams_short = colloc[colloc['lead_time_hours'] <= 12].copy()
cams_daily = (cams_short.groupby(['station', cams_short['datetime'].dt.date.rename('date')])
              .agg(cams_duaod550=('cams_duaod550', 'mean'),
                   n_cams_obs=('cams_duaod550', 'count'))
              .reset_index())
cams_daily['date'] = pd.to_datetime(cams_daily['date'])
print(f"  CAMS daily records: {len(cams_daily)}")

# ─── Merge all three ───
print("\nMerging datasets...")
# AERONET + CAMS (daily)
ac = pd.merge(aeronet_daily, cams_daily, on=['station', 'date'], how='inner')
# + MODIS
three = pd.merge(ac, modis, on=['station', 'date'], how='inner')
print(f"  Three-way matched records: {len(three)}")
print(f"  Stations: {three['station'].nunique()}")
print(f"  Per station:")
for st in sorted(three['station'].unique()):
    n = len(three[three['station'] == st])
    yr_min = three[three['station'] == st]['date'].dt.year.min()
    yr_max = three[three['station'] == st]['date'].dt.year.max()
    print(f"    {st}: {n} days ({yr_min}-{yr_max})")

# ─── Validation functions ───
def compute_stats(x, y, name_x, name_y):
    """Compute validation statistics between two arrays."""
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    n = len(x)
    if n < 10:
        return {'N': n, 'R': np.nan, 'bias': np.nan, 'RMSE': np.nan,
                'slope': np.nan, 'intercept': np.nan, 'EE_pct': np.nan}

    r, p = stats.pearsonr(x, y)
    bias = np.mean(y - x)
    rmse = np.sqrt(np.mean((y - x)**2))
    slope, intercept, _, _, _ = stats.linregress(x, y)

    # Expected Error envelope (MODIS): ±(0.05 + 0.15*AOD)
    ee_upper = x + 0.05 + 0.15 * x
    ee_lower = x - 0.05 - 0.15 * x
    within_ee = np.sum((y >= ee_lower) & (y <= ee_upper))
    ee_pct = 100.0 * within_ee / n

    return {'N': n, 'R': round(r, 3), 'bias': round(bias, 4),
            'RMSE': round(rmse, 4), 'slope': round(slope, 3),
            'intercept': round(intercept, 4), 'EE_pct': round(ee_pct, 1)}

# ─── Compute stats for all stations ───
print("\n" + "="*80)
print("THREE-WAY VALIDATION RESULTS")
print("="*80)

all_stats = []
stations = sorted(three['station'].unique())

for station in stations:
    df = three[three['station'] == station]

    # 1. MODIS vs AERONET
    s1 = compute_stats(df['aeronet_aod550'].values, df['modis_dtdb_aod550'].values,
                       'AERONET', 'MODIS')
    s1.update({'station': station, 'comparison': 'MODIS_vs_AERONET'})

    # 2. CAMS vs AERONET
    s2 = compute_stats(df['aeronet_aod550'].values, df['cams_duaod550'].values,
                       'AERONET', 'CAMS')
    s2.update({'station': station, 'comparison': 'CAMS_vs_AERONET'})

    # 3. MODIS vs CAMS
    s3 = compute_stats(df['cams_duaod550'].values, df['modis_dtdb_aod550'].values,
                       'CAMS', 'MODIS')
    s3.update({'station': station, 'comparison': 'MODIS_vs_CAMS'})

    all_stats.extend([s1, s2, s3])

stats_df = pd.DataFrame(all_stats)
stats_df = stats_df[['station', 'comparison', 'N', 'R', 'bias', 'RMSE', 'slope', 'intercept', 'EE_pct']]

# Print results
for comp in ['MODIS_vs_AERONET', 'CAMS_vs_AERONET', 'MODIS_vs_CAMS']:
    print(f"\n--- {comp.replace('_', ' ')} ---")
    sub = stats_df[stats_df['comparison'] == comp]
    print(sub.to_string(index=False))

# Save stats
stats_df.to_csv(OUT_DIR / "three_way_stats.csv", index=False)
print(f"\nStats saved to {OUT_DIR / 'three_way_stats.csv'}")

# ─── Scatter plots per station ───
print("\nGenerating scatter plots...")

# Color scheme
colors = {'MODIS_vs_AERONET': '#2196F3', 'CAMS_vs_AERONET': '#FF9800', 'MODIS_vs_CAMS': '#4CAF50'}

for station in stations:
    df = three[three['station'] == station]
    if len(df) < 10:
        print(f"  Skipping {station} (N={len(df)})")
        continue

    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))
    fig.suptitle(f'{station}', fontsize=14, fontweight='bold', y=1.02)

    pairs = [
        ('aeronet_aod550', 'modis_dtdb_aod550', 'AERONET AOD₅₅₀', 'MODIS AOD₅₅₀', 'MODIS vs AERONET', colors['MODIS_vs_AERONET']),
        ('aeronet_aod550', 'cams_duaod550', 'AERONET AOD₅₅₀', 'CAMS DOD₅₅₀', 'CAMS vs AERONET', colors['CAMS_vs_AERONET']),
        ('cams_duaod550', 'modis_dtdb_aod550', 'CAMS DOD₅₅₀', 'MODIS AOD₅₅₀', 'MODIS vs CAMS', colors['MODIS_vs_CAMS']),
    ]

    for ax, (xcol, ycol, xlabel, ylabel, title, color) in zip(axes, pairs):
        x = df[xcol].values
        y = df[ycol].values
        mask = np.isfinite(x) & np.isfinite(y)
        x, y = x[mask], y[mask]

        if len(x) < 10:
            ax.text(0.5, 0.5, 'Insufficient data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title(title)
            continue

        # Max for axis limits
        vmax = max(np.percentile(x, 99), np.percentile(y, 99)) * 1.1
        vmax = max(vmax, 0.5)  # minimum axis range

        # Scatter
        ax.scatter(x, y, alpha=0.3, s=12, c=color, edgecolors='none')

        # 1:1 line
        ax.plot([0, vmax], [0, vmax], 'k-', linewidth=1, label='1:1')

        # EE envelope (±0.05 ± 15%)
        xx = np.linspace(0, vmax, 100)
        ax.fill_between(xx, xx - 0.05 - 0.15*xx, xx + 0.05 + 0.15*xx,
                        alpha=0.15, color='gray', label='EE (±0.05±15%)')

        # Regression line
        slope, intercept, _, _, _ = stats.linregress(x, y)
        ax.plot(xx, slope*xx + intercept, '--', color='red', linewidth=1.2, label=f'Fit')

        # Stats text
        r, _ = stats.pearsonr(x, y)
        bias = np.mean(y - x)
        rmse = np.sqrt(np.mean((y - x)**2))
        ee_upper = x + 0.05 + 0.15 * x
        ee_lower = x - 0.05 - 0.15 * x
        ee_pct = 100.0 * np.sum((y >= ee_lower) & (y <= ee_upper)) / len(x)

        stats_text = (f'N = {len(x)}\n'
                      f'R = {r:.3f}\n'
                      f'Bias = {bias:+.3f}\n'
                      f'RMSE = {rmse:.3f}\n'
                      f'y = {slope:.2f}x {intercept:+.3f}\n'
                      f'EE% = {ee_pct:.1f}%')
        ax.text(0.05, 0.95, stats_text, transform=ax.transAxes, fontsize=8,
                verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle='round,pad=0.4', facecolor='white', alpha=0.85))

        ax.set_xlim(0, vmax)
        ax.set_ylim(0, vmax)
        ax.set_xlabel(xlabel, fontsize=10)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_title(title, fontsize=11, fontweight='bold')
        ax.set_aspect('equal')
        ax.legend(loc='lower right', fontsize=7)
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(OUT_DIR / f"three_way_scatter_{station}.png", dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {station}")

# ─── Summary figure: all stations, 3 panels ───
print("\nGenerating summary figure...")
fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))
fig.suptitle('Three-Way Validation — All Stations', fontsize=14, fontweight='bold', y=1.02)

station_colors = plt.cm.tab10(np.linspace(0, 1, len(stations)))
station_cmap = {st: station_colors[i] for i, st in enumerate(stations)}

pairs = [
    ('aeronet_aod550', 'modis_dtdb_aod550', 'AERONET AOD₅₅₀', 'MODIS AOD₅₅₀', 'MODIS vs AERONET'),
    ('aeronet_aod550', 'cams_duaod550', 'AERONET AOD₅₅₀', 'CAMS DOD₅₅₀', 'CAMS vs AERONET'),
    ('cams_duaod550', 'modis_dtdb_aod550', 'CAMS DOD₅₅₀', 'MODIS AOD₅₅₀', 'MODIS vs CAMS'),
]

for ax, (xcol, ycol, xlabel, ylabel, title) in zip(axes, pairs):
    for station in stations:
        df = three[three['station'] == station]
        x = df[xcol].values
        y = df[ycol].values
        mask = np.isfinite(x) & np.isfinite(y)
        x, y = x[mask], y[mask]
        short_name = station.replace('_', ' ').replace('ResearchCentre', 'RC').replace('Institute', 'Inst').replace('Airport SDSC', 'Apt')
        ax.scatter(x, y, alpha=0.25, s=8, c=[station_cmap[station]], edgecolors='none', label=short_name)

    # All data combined stats
    x_all = three[xcol].dropna().values
    y_all = three[ycol].dropna().values
    mask = np.isfinite(x_all) & np.isfinite(y_all)
    x_all, y_all = x_all[mask], y_all[mask]

    vmax = max(np.percentile(x_all, 99), np.percentile(y_all, 99)) * 1.1
    vmax = max(vmax, 0.5)

    # 1:1 + EE
    xx = np.linspace(0, vmax, 100)
    ax.plot([0, vmax], [0, vmax], 'k-', linewidth=1)
    ax.fill_between(xx, xx - 0.05 - 0.15*xx, xx + 0.05 + 0.15*xx,
                    alpha=0.12, color='gray')

    # Overall stats
    r, _ = stats.pearsonr(x_all, y_all)
    bias = np.mean(y_all - x_all)
    rmse = np.sqrt(np.mean((y_all - x_all)**2))
    slope, intercept, _, _, _ = stats.linregress(x_all, y_all)

    ax.plot(xx, slope*xx + intercept, '--', color='red', linewidth=1.2)

    stats_text = (f'N = {len(x_all)}\nR = {r:.3f}\nBias = {bias:+.3f}\n'
                  f'RMSE = {rmse:.3f}\ny = {slope:.2f}x {intercept:+.3f}')
    ax.text(0.05, 0.95, stats_text, transform=ax.transAxes, fontsize=8,
            verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='white', alpha=0.85))

    ax.set_xlim(0, vmax)
    ax.set_ylim(0, vmax)
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(title, fontsize=11, fontweight='bold')
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)

# One legend for all
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc='lower center', ncol=len(stations), fontsize=7,
           bbox_to_anchor=(0.5, -0.05), markerscale=2)

plt.tight_layout()
fig.savefig(OUT_DIR / "three_way_summary.png", dpi=150, bbox_inches='tight')
plt.close(fig)
print(f"Saved: three_way_summary.png")

# ─── Also save the merged three-way dataset ───
three.to_csv(OUT_DIR / "three_way_merged.csv", index=False)
print(f"\nMerged dataset saved: {OUT_DIR / 'three_way_merged.csv'} ({len(three)} rows)")

print("\nDone! Check data/validation/ for all outputs.")
