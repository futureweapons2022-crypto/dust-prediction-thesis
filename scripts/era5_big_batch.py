"""
ERA5 Big Batch — Fill gaps from the recent end.
Launches 6-month bulk requests to complement the main era5_optimized.py script.
"""

import cdsapi
import os
import time

CDS_URL = "https://cds.climate.copernicus.eu/api"
OUTPUT_DIR = r"C:\Users\LENOVO\Desktop\THESIS\data\era5"
AREA = [34, 45, 20, 60]
HOURS_6H = ["00:00", "06:00", "12:00", "18:00"]

SINGLE_LEVEL_VARS = [
    "10m_u_component_of_wind", "10m_v_component_of_wind", "instantaneous_10m_wind_gust",
    "2m_temperature", "skin_temperature",
    "2m_dewpoint_temperature", "total_precipitation", "evaporation", "total_column_water_vapour",
    "boundary_layer_height", "convective_available_potential_energy", "surface_pressure",
    "volumetric_soil_water_layer_1",
    "surface_solar_radiation_downwards", "surface_thermal_radiation_downwards",
    "low_cloud_cover", "high_cloud_cover",
    "leaf_area_index_low_vegetation", "forecast_albedo",
]

PRESSURE_LEVEL_VARS = [
    "geopotential", "u_component_of_wind", "v_component_of_wind",
    "temperature", "relative_humidity",
]
PRESSURE_LEVELS = ["500", "700", "850"]

# Jobs to run — (label, dataset, variables, date_range, filename)
JOBS = [
    # Complete 2024
    ("PL 2024 Q2 (Apr-Jun)", "reanalysis-era5-pressure-levels",
     PRESSURE_LEVEL_VARS, PRESSURE_LEVELS, "2024-04-01/2024-06-30", "era5_pl_all_2024q2.nc"),
    ("PL 2024 H2 (Jul-Dec)", "reanalysis-era5-pressure-levels",
     PRESSURE_LEVEL_VARS, PRESSURE_LEVELS, "2024-07-01/2024-12-31", "era5_pl_all_2024h2.nc"),
    ("SL 2024 H2 (Jul-Dec)", "reanalysis-era5-single-levels",
     SINGLE_LEVEL_VARS, None, "2024-07-01/2024-12-31", "era5_single_2024h2.nc"),
    # Fill 2023
    ("PL 2023 H1 (Jan-Jun)", "reanalysis-era5-pressure-levels",
     PRESSURE_LEVEL_VARS, PRESSURE_LEVELS, "2023-01-01/2023-06-30", "era5_pl_all_2023h1.nc"),
    ("PL 2023 H2 (Jul-Dec)", "reanalysis-era5-pressure-levels",
     PRESSURE_LEVEL_VARS, PRESSURE_LEVELS, "2023-07-01/2023-12-31", "era5_pl_all_2023h2.nc"),
    ("SL 2023 H1 (Jan-Jun)", "reanalysis-era5-single-levels",
     SINGLE_LEVEL_VARS, None, "2023-01-01/2023-06-30", "era5_single_2023h1.nc"),
    # Fill 2022
    ("PL 2022 H1 (Jan-Jun)", "reanalysis-era5-pressure-levels",
     PRESSURE_LEVEL_VARS, PRESSURE_LEVELS, "2022-01-01/2022-06-30", "era5_pl_all_2022h1.nc"),
    ("PL 2022 H2 (Jul-Dec)", "reanalysis-era5-pressure-levels",
     PRESSURE_LEVEL_VARS, PRESSURE_LEVELS, "2022-07-01/2022-12-31", "era5_pl_all_2022h2.nc"),
    ("SL 2022 H1 (Jan-Jun)", "reanalysis-era5-single-levels",
     SINGLE_LEVEL_VARS, None, "2022-01-01/2022-06-30", "era5_single_2022h1.nc"),
    ("SL 2022 H2 (Jul-Dec)", "reanalysis-era5-single-levels",
     SINGLE_LEVEL_VARS, None, "2022-07-01/2022-12-31", "era5_single_2022h2.nc"),
    # Fill 2021
    ("PL 2021 H1 (Jan-Jun)", "reanalysis-era5-pressure-levels",
     PRESSURE_LEVEL_VARS, PRESSURE_LEVELS, "2021-01-01/2021-06-30", "era5_pl_all_2021h1.nc"),
    ("PL 2021 H2 (Jul-Dec)", "reanalysis-era5-pressure-levels",
     PRESSURE_LEVEL_VARS, PRESSURE_LEVELS, "2021-07-01/2021-12-31", "era5_pl_all_2021h2.nc"),
    ("SL 2021 H1 (Jan-Jun)", "reanalysis-era5-single-levels",
     SINGLE_LEVEL_VARS, None, "2021-01-01/2021-06-30", "era5_single_2021h1.nc"),
    ("SL 2021 H2 (Jul-Dec)", "reanalysis-era5-single-levels",
     SINGLE_LEVEL_VARS, None, "2021-07-01/2021-12-31", "era5_single_2021h2.nc"),
    # Fill 2020
    ("PL 2020 H1 (Jan-Jun)", "reanalysis-era5-pressure-levels",
     PRESSURE_LEVEL_VARS, PRESSURE_LEVELS, "2020-01-01/2020-06-30", "era5_pl_all_2020h1.nc"),
    ("PL 2020 H2 (Jul-Dec)", "reanalysis-era5-pressure-levels",
     PRESSURE_LEVEL_VARS, PRESSURE_LEVELS, "2020-07-01/2020-12-31", "era5_pl_all_2020h2.nc"),
    ("SL 2020 H1 (Jan-Jun)", "reanalysis-era5-single-levels",
     SINGLE_LEVEL_VARS, None, "2020-01-01/2020-06-30", "era5_single_2020h1.nc"),
    ("SL 2020 H2 (Jul-Dec)", "reanalysis-era5-single-levels",
     SINGLE_LEVEL_VARS, None, "2020-07-01/2020-12-31", "era5_single_2020h2.nc"),
    # Fill 2019
    ("PL 2019 H1 (Jan-Jun)", "reanalysis-era5-pressure-levels",
     PRESSURE_LEVEL_VARS, PRESSURE_LEVELS, "2019-01-01/2019-06-30", "era5_pl_all_2019h1.nc"),
    ("PL 2019 H2 (Jul-Dec)", "reanalysis-era5-pressure-levels",
     PRESSURE_LEVEL_VARS, PRESSURE_LEVELS, "2019-07-01/2019-12-31", "era5_pl_all_2019h2.nc"),
    ("SL 2019 H1 (Jan-Jun)", "reanalysis-era5-single-levels",
     SINGLE_LEVEL_VARS, None, "2019-01-01/2019-06-30", "era5_single_2019h1.nc"),
    ("SL 2019 H2 (Jul-Dec)", "reanalysis-era5-single-levels",
     SINGLE_LEVEL_VARS, None, "2019-07-01/2019-12-31", "era5_single_2019h2.nc"),
    # Fill 2018
    ("PL 2018 H1 (Jan-Jun)", "reanalysis-era5-pressure-levels",
     PRESSURE_LEVEL_VARS, PRESSURE_LEVELS, "2018-01-01/2018-06-30", "era5_pl_all_2018h1.nc"),
    ("PL 2018 H2 (Jul-Dec)", "reanalysis-era5-pressure-levels",
     PRESSURE_LEVEL_VARS, PRESSURE_LEVELS, "2018-07-01/2018-12-31", "era5_pl_all_2018h2.nc"),
    ("SL 2018 H1 (Jan-Jun)", "reanalysis-era5-single-levels",
     SINGLE_LEVEL_VARS, None, "2018-01-01/2018-06-30", "era5_single_2018h1.nc"),
    ("SL 2018 H2 (Jul-Dec)", "reanalysis-era5-single-levels",
     SINGLE_LEVEL_VARS, None, "2018-07-01/2018-12-31", "era5_single_2018h2.nc"),
    # Fill 2017
    ("PL 2017 H1 (Jan-Jun)", "reanalysis-era5-pressure-levels",
     PRESSURE_LEVEL_VARS, PRESSURE_LEVELS, "2017-01-01/2017-06-30", "era5_pl_all_2017h1.nc"),
    ("PL 2017 H2 (Jul-Dec)", "reanalysis-era5-pressure-levels",
     PRESSURE_LEVEL_VARS, PRESSURE_LEVELS, "2017-07-01/2017-12-31", "era5_pl_all_2017h2.nc"),
    ("SL 2017 H1 (Jan-Jun)", "reanalysis-era5-single-levels",
     SINGLE_LEVEL_VARS, None, "2017-01-01/2017-06-30", "era5_single_2017h1.nc"),
    ("SL 2017 H2 (Jul-Dec)", "reanalysis-era5-single-levels",
     SINGLE_LEVEL_VARS, None, "2017-07-01/2017-12-31", "era5_single_2017h2.nc"),
    # Fill 2016 H2 (H1 already done by main script)
    ("PL 2016 H2 (Jul-Dec)", "reanalysis-era5-pressure-levels",
     PRESSURE_LEVEL_VARS, PRESSURE_LEVELS, "2016-07-01/2016-12-31", "era5_pl_all_2016h2.nc"),
    ("SL 2016 H2 (Jul-Dec)", "reanalysis-era5-single-levels",
     SINGLE_LEVEL_VARS, None, "2016-07-01/2016-12-31", "era5_single_2016h2.nc"),
]


def run_job(label, dataset, variables, levels, date_range, filename):
    filepath = os.path.join(OUTPUT_DIR, filename)

    if os.path.exists(filepath):
        print(f"[SKIP] {label} — already exists ({os.path.getsize(filepath)/(1024*1024):.1f} MB)", flush=True)
        return

    print(f"\n[START] {label} — {date_range}", flush=True)
    client = cdsapi.Client(url=CDS_URL, timeout=86400, retry_max=5, quiet=False)
    t0 = time.time()

    params = {
        "product_type": "reanalysis",
        "variable": variables,
        "date": date_range,
        "time": HOURS_6H,
        "area": AREA,
        "data_format": "netcdf",
    }
    if levels:
        params["pressure_level"] = levels

    try:
        client.retrieve(dataset, params, filepath)
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        elapsed = (time.time() - t0) / 60
        print(f"[DONE] {label} — {size_mb:.1f} MB in {elapsed:.0f} min", flush=True)
    except Exception as e:
        elapsed = (time.time() - t0) / 60
        print(f"[FAIL] {label} — {e} ({elapsed:.0f} min)", flush=True)
        if os.path.exists(filepath):
            os.remove(filepath)


if __name__ == "__main__":
    print(f"ERA5 Big Batch Download", flush=True)
    print(f"Jobs: {len(JOBS)}", flush=True)
    print(f"Output: {OUTPUT_DIR}", flush=True)
    print(f"{'='*60}\n", flush=True)

    for job in JOBS:
        label, dataset, variables, levels, date_range, filename = job
        run_job(label, dataset, variables, levels, date_range, filename)

    print(f"\n{'='*60}", flush=True)
    print("All jobs complete.", flush=True)
