"""
AERONET Temporal Coverage Heatmap
==================================
Generates a station x month heatmap showing valid AOD_500nm measurement
counts across all 8 AERONET stations (Tier 1-3), 2015–2026.

Output: THESIS/figures/aeronet_temporal_coverage.png
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import os

DATA_DIR = r"C:\Users\LENOVO\Desktop\THESIS\data\aeronet"
FIG_DIR = r"C:\Users\LENOVO\Desktop\THESIS\figures"

# Station definitions: (filename, tier, level folder)
STATIONS = [
    ("Mezaira_AOD20_allpoints.csv", "Tier 1", "level2"),
    ("Masdar_Institute_AOD20_allpoints.csv", "Tier 1", "level2"),
    ("Kuwait_University_AOD20_allpoints.csv", "Tier 2", "level2"),
    ("Shagaya_Park_AOD20_allpoints.csv", "Tier 2", "level2"),
    ("DEWA_ResearchCentre_AOD20_allpoints.csv", "Tier 2", "level2"),
    ("Riyadh_Airport_SDSC_AOD15_allpoints.csv", "Tier 3", "level15"),
    ("Kuwait_University_2_AOD15_allpoints.csv", "Tier 3", "level15"),
    ("Khalifa_University_AOD15_allpoints.csv", "Tier 3", "level15"),
]


def parse_aeronet(filepath):
    """Parse AERONET HTML-CSV file, return DataFrame with datetime and AOD_500nm."""
    df = pd.read_csv(
        filepath,
        skiprows=7,
        parse_dates=False,
        na_values=["-999.", "-999.000000"],
    )
    # Strip <br> from last column and whitespace from column names
    df.columns = df.columns.str.strip()
    last_col = df.columns[-1]
    if df[last_col].dtype == object:
        df[last_col] = df[last_col].str.replace("<br>", "", regex=False)

    # Parse date (dd:mm:yyyy) and time
    df["datetime"] = pd.to_datetime(
        df["Date(dd:mm:yyyy)"] + " " + df["Time(hh:mm:ss)"],
        format="%d:%m:%Y %H:%M:%S",
    )
    df["year_month"] = df["datetime"].dt.to_period("M")

    # Find AOD_500nm column
    aod_col = [c for c in df.columns if "AOD_500nm" in c and "Triplet" not in c and "Exact" not in c]
    if aod_col:
        df["AOD_500"] = pd.to_numeric(df[aod_col[0]], errors="coerce")
    else:
        df["AOD_500"] = np.nan

    return df


# --- Parse all stations ---
print("Parsing AERONET files...")
station_data = {}
for fname, tier, level_dir in STATIONS:
    filepath = os.path.join(DATA_DIR, level_dir, fname)
    station_name = fname.split("_AOD")[0].replace("_", " ")
    label = f"{station_name} ({tier})"
    print(f"  {label}...", end=" ")
    df = parse_aeronet(filepath)
    valid = df["AOD_500"].notna()
    print(f"{valid.sum():,} valid AOD rows")
    station_data[label] = df[valid]

# --- Build monthly count matrix ---
# Full month range: Jan 2015 to Dec 2025 (cover all possible data)
all_months = pd.period_range("2015-01", "2025-12", freq="M")

counts = pd.DataFrame(index=station_data.keys(), columns=all_months, dtype=float)
counts[:] = 0

for label, df in station_data.items():
    monthly = df.groupby("year_month").size()
    for m, c in monthly.items():
        if m in counts.columns:
            counts.loc[label, m] = c

counts = counts.astype(float)

# --- Trim trailing empty columns ---
# Find last month with any data
last_with_data = counts.columns[counts.sum(axis=0) > 0][-1]
counts = counts.loc[:, :last_with_data]

# --- Plot ---
fig, ax = plt.subplots(figsize=(18, 6))

# Custom colormap: white (0) -> light blue -> dark blue
cmap = mcolors.LinearSegmentedColormap.from_list(
    "aeronet", ["#FFFFFF", "#D4E6F1", "#2E86C1", "#1B4F72"], N=256
)
cmap.set_bad(color="#F0F0F0")

# Replace 0 with NaN for better visual (white = truly no data)
plot_data = counts.copy()
plot_data[plot_data == 0] = np.nan

im = ax.imshow(
    plot_data.values.astype(float),
    aspect="auto",
    cmap=cmap,
    interpolation="nearest",
)

# Y-axis: station names
ax.set_yticks(range(len(counts.index)))
ax.set_yticklabels(counts.index, fontsize=10)

# X-axis: year labels at January of each year
month_labels = counts.columns
jan_positions = [i for i, m in enumerate(month_labels) if m.month == 1]
jan_years = [month_labels[i].year for i in jan_positions]
ax.set_xticks(jan_positions)
ax.set_xticklabels(jan_years, fontsize=10)

# Minor ticks for month grid
ax.set_xticks(range(len(month_labels)), minor=True)
ax.tick_params(axis="x", which="minor", length=0)

# Grid lines at year boundaries
for pos in jan_positions:
    ax.axvline(pos - 0.5, color="#CCCCCC", linewidth=0.5, linestyle="-")

# Horizontal lines between stations
for i in range(len(counts.index) - 1):
    ax.axhline(i + 0.5, color="#CCCCCC", linewidth=0.5)

# Tier separators (thicker lines)
# Tier 1: indices 0-1, Tier 2: 2-4, Tier 3: 5-7
ax.axhline(1.5, color="#333333", linewidth=1.5)
ax.axhline(4.5, color="#333333", linewidth=1.5)

# Tier labels on the right
ax.text(len(month_labels) + 0.5, 0.5, "Tier 1\n(L2.0)", fontsize=8,
        va="center", ha="left", fontweight="bold", color="#1B4F72")
ax.text(len(month_labels) + 0.5, 3.0, "Tier 2\n(L2.0)", fontsize=8,
        va="center", ha="left", fontweight="bold", color="#2E86C1")
ax.text(len(month_labels) + 0.5, 6.0, "Tier 3\n(L1.5)", fontsize=8,
        va="center", ha="left", fontweight="bold", color="#85C1E9")

# Annotate cells with count values (only for cells with data, small font)
for i in range(plot_data.shape[0]):
    for j in range(plot_data.shape[1]):
        val = plot_data.iloc[i, j]
        if not np.isnan(val) and val > 0:
            # Use white text on dark cells, black on light
            text_color = "white" if val > counts.max().max() * 0.5 else "#333333"
            # Only show count if cell is wide enough (skip for readability)
            if len(month_labels) <= 132:  # always true for our range
                ax.text(j, i, f"{int(val):,}" if val < 10000 else f"{val/1000:.0f}k",
                        ha="center", va="center", fontsize=4.5, color=text_color)

# Colorbar
cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.08)
cbar.set_label("Valid AOD_500nm measurements per month", fontsize=10)

# Title
ax.set_title(
    "AERONET Station Temporal Coverage — Arabian Gulf Study Domain (2015–2025)\n"
    "Valid AOD_500nm measurements per month",
    fontsize=13, fontweight="bold", pad=12,
)

plt.tight_layout()

# Save
outpath = os.path.join(FIG_DIR, "aeronet_temporal_coverage.png")
fig.savefig(outpath, dpi=200, bbox_inches="tight", facecolor="white")
print(f"\nSaved: {outpath}")
plt.close()
