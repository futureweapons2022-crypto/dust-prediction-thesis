# Dust AOD Prediction — Arabian Gulf Region

Master's thesis research at the University of Sharjah.

## Overview

This project builds a meta-model that predicts **when CAMS dust forecasts will fail** over the Arabian Gulf region. Instead of replacing existing forecasts, it identifies conditions under which they become unreliable — giving decision-makers advance warning.

## Key Results

- **Three-way validation** between CAMS, AERONET, and MODIS satellite observations
- **XGBoost meta-model** achieves AUC = 0.87, F1 = 0.64 in predicting forecast failures
- **RAG system** for mining scientific literature on anthropogenic dust sources

## Project Structure

```
scripts/          # All Python code
  ├── download_*.py         # Data acquisition (CAMS, ERA5, MODIS, CMIP6)
  ├── qaqc_*.py             # Quality control pipelines
  ├── collocate_*.py        # Data collocation
  ├── three_way_validation.py  # Phase 1: Benchmarking
  ├── train_meta_model.py   # Phase 2: XGBoost meta-model
  ├── build_rag.py          # Phase 3: Literature RAG system
  └── query_rag.py          # Phase 3: RAG query interface
figures/          # Generated plots and visualizations
literature_review/ # Literature review materials
```

## Data Sources

- **CAMS** (Copernicus Atmosphere Monitoring Service) — dust AOD forecasts
- **AERONET** — ground-based aerosol observations
- **MODIS** — satellite aerosol optical depth
- **ERA5** — meteorological reanalysis
- **CMIP6** — climate projections

## Tech Stack

Python, XGBoost, SHAP, Pandas, NumPy, ChromaDB, Docling, Pyodide

## Author

Ibrahim Kukash — Dubai Municipality, Central Lab (Studies & Business Development)
