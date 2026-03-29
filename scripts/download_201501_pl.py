"""Download the single missing file: era5_pl_all_201501.nc"""

import cdsapi
import os

OUTPUT_DIR = r"C:\Users\LENOVO\Desktop\THESIS\data\era5"
filepath = os.path.join(OUTPUT_DIR, "era5_pl_all_201501.nc")

if os.path.exists(filepath):
    print("File already exists, nothing to do.")
else:
    print("Downloading era5_pl_all_201501.nc ...")
    client = cdsapi.Client(url="https://cds.climate.copernicus.eu/api", timeout=86400, retry_max=3)
    client.retrieve("reanalysis-era5-pressure-levels", {
        "product_type": "reanalysis",
        "variable": ["geopotential", "u_component_of_wind", "v_component_of_wind", "temperature", "relative_humidity"],
        "pressure_level": ["500", "700", "850"],
        "year": "2015",
        "month": "01",
        "day": [f"{d:02d}" for d in range(1, 32)],
        "time": ["00:00", "06:00", "12:00", "18:00"],
        "area": [34, 45, 20, 60],
        "data_format": "netcdf",
    }, filepath)
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"Done — {size_mb:.1f} MB saved to {filepath}")
