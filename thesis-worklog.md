# Thesis Working Log — IMGAIA
## "An Integrated Meta-Modeling and Generative-AI Approach to Identify Dust Prediction Errors"
### Ibrahim Deeb Kukash | University of Sharjah | Supervisor: Dr. Mohamed Abdallah

> This document is a living reference for all data decisions, downloads, analysis steps, and rationale.
> Updated as work progresses. Use this when writing thesis chapters.

---

## 1. Thesis Overview

**Core Idea**: Build a meta-model that predicts WHEN dust forecasting models will fail, rather than predicting dust directly.

**Study Domain**: Arabian Gulf region (45°E–60°E, 20°N–34°N)
**Countries covered**: UAE, Qatar, Bahrain, Kuwait, eastern Saudi Arabia, southern Iraq, Oman

### 1.1 The Five Objectives (Deliverables)

| # | Objective | Phase | Timeline |
|---|-----------|-------|----------|
| 1 | Systematic benchmarking of CAMS vs AI weather emulators for dust prediction | Phase 1 | January 2026 |
| 2 | Meta-model development (RF, XGBoost, NN) to predict forecast failure | Phase 2 | February 2026 |
| 3 | Anthropogenic signal integration via generative AI (marsh drainage, agricultural collapse) | Phase 3 | March 2026 |
| 4 | Climate robustness assessment using CMIP6 projections (SSP2-4.5, SSP5-8.5) through 2050 | Phase 4 | April 2026 |
| 5 | Operational guidelines for forecasting centers | Phase 5 | May 2026 |

### 1.2 Data Requirements Summary

| Dataset | Source | Account Needed? | Status |
|---------|--------|-----------------|--------|
| Ground truth AOD | AERONET | No | **DOWNLOADED** (2026-02-24) — 8 stations, all-points, 634 MB total |
| UAE PM10/PM2.5 | DCL / EAD | Internal access? | Not started |
| CAMS dust forecasts | Copernicus ADS | Yes (free) | **DOWNLOADING** — 12 merged months + 63 temp windows (~25%) |
| AI model outputs | Various (GraphCast, etc.) | TBD | Needs research |
| ERA5 reanalysis | Copernicus CDS | Yes (free) | **DOWNLOADING** — 12/240 requests done (~5%) |
| CMIP6 projections | ESGF | Yes (free) | Not started |
| Historical documents | UNEP, FAO, news archives | No | Not started |

### 1.3 Data Coverage & Resolution (verified 2026-03-11)

| Dataset | Region | Resolution | Grid Size | Time Coverage |
|---------|--------|-----------|-----------|---------------|
| **AERONET** | 8 point locations (UAE, Kuwait, Saudi) | **Point data** (exact lat/lon) | N/A | 2015–2026 |
| **CAMS** | 20°–34°N, 45.2°–60°E (Arabian Gulf) | **0.40° × 0.40°** (~44 km) | 36 × 38 | 2015–2024 |
| **ERA5 (pressure level)** | 20°–34°N, 45°–60°E (Arabian Gulf) | **0.25° × 0.25°** (~28 km) | 57 × 61 | 2015–2024 |
| **ERA5 (single level)** | 20°–34°N, 45°–60°E (Arabian Gulf) | **0.25° × 0.25°** (~28 km) | 57 × 61 | 2015–2024 |
| **CMIP6** | **GLOBAL** (not cropped to study domain) | **1.1°–2.8°** (varies by model) | varies | 1850–2100 |

**CMIP6 Model-by-Model Resolution:**

| Model | Resolution | ~km | Notes |
|-------|-----------|-----|-------|
| MRI-ESM2-0 | 1.11° × 1.12° | ~120 km | Finest CMIP6 grid |
| MIROC6 | 1.39° × 1.41° | ~155 km | |
| GISS-E2-1-G | 2.00° × 2.50° | ~220 km | |
| GISS-E2-1-H | 2.00° × 2.50° | ~220 km | |
| MIROC-ES2L | 2.77° × 2.81° | ~310 km | Coarsest — only a few grid cells over Arabian Gulf |

**Notes:**
- CAMS and ERA5 cover the same study domain. ERA5 is finer (0.25° vs 0.40°) — regrid to CAMS resolution for feature engineering.
- CMIP6 is global — crop to study domain before use. Coarse resolution means climate trend analysis only, not spatial detail.
- AERONET is point data — matched to nearest CAMS/ERA5 grid cell during collocation.
- ERA5 single-level files are downloaded as ZIP archives (contain `data_stream-oper_stepType-instant.nc` + `data_stream-oper_stepType-accum.nc`) — must extract before processing.

---

## 2. AERONET Station Audit

**Date of audit**: 2026-02-24
**Method**: Checked every AERONET station within study domain (45°E–60°E, 20°N–34°N) via the AERONET web interface (https://aeronet.gsfc.nasa.gov). Verified data availability, operational dates, and Level 2.0 day counts individually for each station.

**Study period requirement**: 2015–2024 (as defined in thesis proposal Section 1.4)

### 2.1 Classification Criteria

Stations were classified into three tiers based on the following criteria:

**Tier 1 — Primary Stations** (used for main benchmarking & meta-model training)
- Must have Level 2.0 data (quality-assured, cloud-screened, final calibration)
- Must have significant temporal overlap with the 2015–2024 study period
- Must have ≥3 years of Level 2.0 data within the study period
- Rationale: Level 2.0 is the gold standard for AERONET validation studies. These stations provide the core forecast-observation pairs for Objective 1 (benchmarking) and Objective 2 (meta-model training).

**Tier 2 — Secondary Stations** (used for geographic diversity & supplementary benchmarking)
- Must have Level 2.0 data
- Overlap with study period may be partial (ended before 2024 is OK)
- Must have ≥1 year of Level 2.0 data within the study period
- Rationale: These stations extend spatial coverage beyond UAE to other Gulf countries, enabling assessment of whether model errors are regionally consistent or location-dependent.

**Tier 3 — Cross-Check Stations** (used for spatial verification & recent-period validation)
- Level 1.5 data is acceptable (cloud-screened, pre-final calibration)
- May be too new for Level 2.0 processing
- Any temporal coverage within or near the study period
- Rationale: Level 1.5 data is widely used in published atmospheric studies. These stations add spatial density and cover the most recent years (2022–2026), allowing cross-verification of model behavior in locations/periods not covered by Tier 1–2.

**Excluded** — Stations that ended operations before 2015 or have negligible data.

### 2.2 Full Station Inventory

#### Tier 1 — Primary Stations

| Station | Location | Lat | Lon | Active Period | L2 Days (Years) | Notes |
|---------|----------|-----|-----|---------------|-----------------|-------|
| **Mezaira** | UAE (western desert) | 23.105°N | 53.755°E | 2004–2026 | 3144 (8.6 yr) | **Best station in domain.** Continuous operation, desert environment representative of major dust source region. Still active as of Feb 2026. |
| **Masdar_Institute** | UAE (Abu Dhabi) | 24.442°N | 54.617°E | 2012–2024 | 1960 (5.4 yr) | Urban/suburban Abu Dhabi. Good coverage 2012–2024. Gap noted in 2023. Represents populated coastal Gulf. |

#### Tier 2 — Secondary Stations

| Station | Location | Lat | Lon | Active Period | L2 Days (Years) | Notes |
|---------|----------|-----|-----|---------------|-----------------|-------|
| **Kuwait_University** | Kuwait (urban) | 29.325°N | 47.971°E | 2006–2021 | 1112 (3.0 yr) | Northern Gulf representation. Critical for assessing model performance closer to Iraqi dust sources. Data gaps in 2013–2014. Ended June 2021. |
| **Shagaya_Park** | Kuwait (desert) | 29.209°N | 47.061°E | 2015–2020 | 1110 (3.0 yr) | Desert site in western Kuwait. Perfect temporal overlap with study period start. Excellent L2 yield (61% of operational days). Ended Aug 2020. |
| **DEWA_ResearchCentre** | UAE (Dubai) | 24.767°N | 55.369°E | 2018–2025 | 391 (1.0 yr) | Dubai representation. Active but low L2 yield (4%). Recent data (2018+) useful for most recent model versions. |

#### Tier 3 — Cross-Check Stations (Level 1.5)

| Station | Location | Lat | Lon | Active Period | L2 Status | Notes |
|---------|----------|-----|-----|---------------|-----------|-------|
| **Riyadh_Airport_SDSC** | Saudi Arabia (Riyadh) | 24.926°N | 46.722°E | 2022–2026 | 0 L2 days | Only Saudi station in domain with recent data. L1.5 expected to be available. Critical for geographic diversity — extends coverage westward toward dust source regions. |
| **Kuwait_University_2** | Kuwait (urban) | 29.258°N | 47.897°E | 2024–2026 | 0 L2 days | Replacement for Kuwait_University. L1.5 data covers most recent period. Provides continuity for Kuwait after KU ended in 2021. |
| **Khalifa_University** | UAE (Abu Dhabi) | 24.418°N | 54.501°E | 2025–2026 | 0 L2 days | Very new. L1.5 may have a few months. Useful for 2025 cross-checks only. |

#### Excluded Stations (with justification)

| Station | Location | Period | Why Excluded |
|---------|----------|--------|--------------|
| Solar_Village | Saudi Arabia (Riyadh) | 1999–2015 | Ended Oct 2015 — only marginal overlap with study period. Was the region's best long-term station but no longer active. |
| Bahrain | Bahrain | 1998–2007 | Ended 9 years before study period starts. |
| Abu_Dhabi | UAE | 2004–2005 | Only 18 L2 days. Ended 2005. |
| Muscat | Oman | 2006 | Only 55 L2 days in a 3-month period. |
| Hamim | UAE (deep desert) | 1994–2007 | Ended 2007. Would have been excellent if still running — deep desert site. |
| Al_Dhafra | UAE | 2001 | Only 1 year of operation. |
| Dhadnah | UAE (east coast) | 2004–2010 | Ended 2010. Had 4.2yr L2 — would be useful if still active. East coast location (Fujairah) unique. |
| Al_Khaznah | UAE | 2004 | Only 98 L2 days in 7 months. |
| SMART / SMART_POL | UAE (Al Ain) | 2004 | Only 53 L2 days. Short campaign. |
| MAARCO | UAE | 2004 | Only 52 L2 days. Short campaign. |
| Umm_Al_Quwain | UAE | 2001–2004 | Ended 2004. |
| Saih_Salam | UAE | 2004 | Only 109 L2 days. Short campaign. |
| Kuwait_Airport | Kuwait | 2009 | Only 16 L2 days in 1 month. |
| Abu_Al_Bukhoosh | UAE (offshore) | Unknown | Offshore platform — not checked in detail. Likely short campaign. |
| Dalma | UAE (island) | Unknown | Island station — not checked. Likely short campaign. |
| Sir_Bu_Nuair | UAE (island) | Unknown | Offshore island — not checked. Likely short campaign. |
| Zakum_Field | UAE (offshore) | Unknown | Offshore oil field — not checked. Likely short campaign. |
| Al_Qlaa | UAE | Unknown | Not checked — early 2000s campaign based on pattern. |
| Masdar_Institute_2 | UAE | Unknown | Duplicate coordinates with Masdar_Institute. Likely instrument replacement. |
| University_of_Nizwa | Oman | Unknown | Not checked — marginal location (inland Oman). |
| Kuwait_Inst_Sci_Res | Kuwait | Unknown | Not checked in detail. |

### 2.3 Geographic Coverage Assessment

```
Study Domain Map (simplified):

         45°E        50°E        55°E        60°E
   34°N  ┌───────────┬───────────┬───────────┐
         │           │   IRAQ    │           │
   32°N  │           │           │   IRAN    │
         │           │ (dried    │           │
   30°N  │        ┌──┤ marshes)  │           │
         │ KUWAIT │KU│           │           │
         │  [SHP] │  │           │           │
   28°N  │ [KU2]──┘  │           │           │
         │           │           │           │
   26°N  │    BAHRAIN │  QATAR   │           │
         │    (dead)  │ (none!)  │           │
   24°N  │  [RYD]    │  [MZR]   │[MAS][DEWA]│
         │ S.ARABIA  │   UAE    [KU] │       │
   22°N  │           │           │   OMAN   │
         │           │           │           │
   20°N  └───────────┴───────────┴───────────┘

Legend:
  [MZR] = Mezaira (Tier 1)         [MAS] = Masdar_Institute (Tier 1)
  [KU]  = Kuwait_University (T2)   [SHP] = Shagaya_Park (T2)
  [DEWA]= DEWA_ResearchCentre (T2) [RYD] = Riyadh_Airport (T3)
  [KU2] = Kuwait_University_2 (T3) [KLF] = Khalifa_University (T3)
```

**Spatial gaps identified:**
- **Qatar**: Zero AERONET stations. Significant gap.
- **Bahrain**: Station dead since 2007.
- **Southern Iraq**: No stations at all (conflict zone). This is WHERE the anthropogenic dust sources are.
- **Eastern Saudi Arabia**: Riyadh station is the only recent option, and it has no L2 yet.
- **Oman**: Muscat dead since 2006. University_of_Nizwa not assessed.

**Implication for thesis**: The spatial distribution is heavily UAE-biased. Kuwait provides the only non-UAE coverage with quality data. This limitation should be acknowledged in Chapter 3 (Methodology) and discussed as a constraint on spatial generalization claims.

### 2.4 Data Download Log

**Date downloaded**: 2026-02-24
**Resolution choice**: **All Points** (AVG=10), NOT daily averages.
**Rationale for all-points**: CAMS provides 6-hourly forecasts, ERA5 is hourly — daily averages would wash out sub-daily dust storm signatures. All-points (~15-min resolution) allows matching with specific forecast hours and capturing intra-day events. Daily averages can always be computed from all-points, but not the reverse.

**Download URL pattern (Level 2.0)**: `https://aeronet.gsfc.nasa.gov/cgi-bin/print_web_data_v3?site={STATION}&year=2015&month=1&day=1&year2=2026&month2=12&day2=31&AOD20=1&AVG=10`
**Download URL pattern (Level 1.5)**: Same but `AOD15=1` instead of `AOD20=1`, and start year adjusted per station.

| Station | Tier | Level | File | Rows | Size | Period Requested |
|---------|------|-------|------|------|------|------------------|
| Mezaira | 1 | 2.0 | `Mezaira_AOD20_allpoints.csv` | 176,016 | 183 MB | 2015–2026 |
| Masdar_Institute | 1 | 2.0 | `Masdar_Institute_AOD20_allpoints.csv` | 113,450 | 120 MB | 2015–2026 |
| Shagaya_Park | 2 | 2.0 | `Shagaya_Park_AOD20_allpoints.csv` | 101,212 | 107 MB | 2015–2026 |
| Kuwait_University | 2 | 2.0 | `Kuwait_University_AOD20_allpoints.csv` | 61,164 | 65 MB | 2015–2026 |
| DEWA_ResearchCentre | 2 | 2.0 | `DEWA_ResearchCentre_AOD20_allpoints.csv` | 40,134 | 43 MB | 2015–2026 |
| Riyadh_Airport_SDSC | 3 | 1.5 | `Riyadh_Airport_SDSC_AOD15_allpoints.csv` | 76,943 | 82 MB | 2022–2026 |
| Kuwait_University_2 | 3 | 1.5 | `Kuwait_University_2_AOD15_allpoints.csv` | 30,600 | 33 MB | 2024–2026 |
| Khalifa_University | 3 | 1.5 | `Khalifa_University_AOD15_allpoints.csv` | 2,928 | 3.1 MB | 2025–2026 |
| **TOTAL** | | | | **~602,000** | **634 MB** | |

**File locations**:
- Level 2.0: `C:\Users\LENOVO\Desktop\THESIS\data\aeronet\level2\`
- Level 1.5: `C:\Users\LENOVO\Desktop\THESIS\data\aeronet\level15\`

**Note**: Initially downloaded daily averages (AVG=20) but replaced with all-points (AVG=10) after realizing daily averages lose sub-daily dust event resolution. Daily files deleted.

### 2.5 AERONET Data Dictionary

The downloaded files are HTML-formatted CSV (AERONET's standard output). First 7 lines are header/metadata, line 8 is the column header, data starts line 9. Each row = one sun photometer measurement (~15 min intervals during daylight).

**Key columns for this thesis:**

| Column | Example | Role in Thesis |
|--------|---------|----------------|
| `AERONET_Site` | Mezaira | Station identifier |
| `Date(dd:mm:yyyy)` | 10:03:2015 | Date (NOTE: dd:mm:yyyy format, not US format) |
| `Time(hh:mm:ss)` | 08:23:15 | UTC time of measurement |
| `Day_of_Year` | 69 | Day number (1–365) |
| **`AOD_500nm`** | 0.703587 | **PRIMARY variable** — Aerosol Optical Depth at 500nm. This is what we compare against CAMS `duaod550` (dust AOD at 550nm). Interpolation needed for wavelength match. |
| `AOD_440nm` | 0.716470 | Used with 870nm for Angstrom exponent |
| `AOD_870nm` | 0.648150 | Used with 440nm for Angstrom exponent |
| **`440-870_Angstrom_Exponent`** | 0.147 | **DUST IDENTIFIER** — Low (<0.5) = coarse particles (dust). High (>1.0) = fine particles (pollution/smoke). Critical for confirming dust events vs other aerosol types. |
| `Precipitable_Water(cm)` | 1.595715 | Atmospheric moisture — potential meta-model feature |
| `N[AOD_500nm]` | 59 | Number of individual triplet measurements in this average. Higher = more reliable. Use as quality filter. |
| `Data_Quality_Level` | lev20 | Confirms Level 2.0 quality |
| `AERONET_Instrument_Number` | 815 | Physical instrument ID (useful for detecting calibration changes) |
| `Site_Latitude(Degrees)` | 23.104520 | Station latitude |
| `Site_Longitude(Degrees)` | 53.754660 | Station longitude |
| `Site_Elevation(m)` | 201.0 | Station elevation |

**Missing data marker**: `-999.` means no measurement at that wavelength (instrument doesn't have that filter or data failed QC).

**Important notes for processing**:
- Timestamp is UTC, not local time (UAE = UTC+4, Kuwait = UTC+3)
- AERONET only measures during daytime (needs direct sunlight) — no nighttime data
- AOD_500nm from AERONET is TOTAL column AOD (all aerosol types), while CAMS `duaod550` is DUST-ONLY AOD. The Angstrom exponent is needed to filter/estimate the dust fraction.
- The `<br>` HTML tags at end of each line need to be stripped during data parsing

---

## 3. Account Registrations

| Service | URL | Purpose | Status | Date |
|---------|-----|---------|--------|------|
| Copernicus CDS | https://cds.climate.copernicus.eu | ERA5 reanalysis + CMIP6 | **REGISTERED** | 2026-02-24 |
| Copernicus ADS | https://ads.atmosphere.copernicus.eu | CAMS forecasts | **REGISTERED** (policies accepted) | 2026-02-24 |
| NASA Earthdata | https://urs.earthdata.nasa.gov | MODIS, VIIRS satellite data | NOT STARTED | — |
| ESGF | https://esgf-node.llnl.gov | CMIP6 raw data | NOT STARTED | — |

**Note**: CDS and ADS share a single Copernicus account (one registration covers both). However, they use **separate API endpoints**:
- CDS: `https://cds.climate.copernicus.eu/api` (ERA5, CMIP6)
- ADS: `https://ads.atmosphere.copernicus.eu/api` (CAMS forecasts)
- Same API key works on both: stored in `~/.cdsapirc` (pointing to CDS by default)
- **Important**: Each dataset may require its own license acceptance on the download page before API access works. General site policies + dataset-specific license are separate.

---

## 4. Analysis Log

*(Will be updated as we perform each step)*

### 4.1 AERONET Data Quality Assessment
- [x] Download complete for all stations (2026-02-24, all-points, 634 MB total)
- [x] Temporal coverage plot (station x year heatmap) — **DONE** (2026-02-25, `figures/aeronet_temporal_coverage.png`)
- [x] Seasonal data availability check — **DONE** (2026-02-25, see below)
- [x] AOD statistics summary — **All 5 L2 stations analyzed** (2026-02-24)
- [x] Tier 3 station analysis — **DONE** (2026-02-25, see below)
- [x] Dust classification thresholds — **RESOLVED** (2026-03-11, see Decision 7). Multi-threshold approach: AE<0.4 (pure dust), AE<0.6 (standard), AE<0.75 (mixed). Citations: Eck et al. (2008), Dubovik et al. (2002), Di Tomaso et al. (2022), Basart et al. (2009).

**All-Station Summary (2026-02-24)**:

| Station | Period | Valid AOD | Mean | Median | Std | Max | Dust% | High AOD% | Peak Month |
|---------|--------|-----------|------|--------|-----|-----|-------|-----------|------------|
| Mezaira | 2015–2023 | 176,003 | 0.361 | 0.234 | 0.371 | 4.134 | 42.3% | 3.0% | Jul (0.61) |
| Masdar | 2015–2022 | 113,382 | 0.361 | 0.332 | 0.184 | 2.316 | 35.3% | 2.1% | Jul (0.57) |
| Shagaya | 2015–2019 | 101,196 | 0.311 | 0.277 | 0.199 | 2.147 | 30.4% | 2.5% | May (0.43) |
| Kuwait_U | 2019–2021 | 61,154 | 0.327 | 0.296 | 0.183 | 2.952 | 22.8% | 1.6% | May (0.42) |
| DEWA | 2018–2020 | 40,122 | 0.353 | 0.318 | 0.194 | 1.468 | 25.2% | 2.5% | Jul (0.59) |

**Key findings**:
- UAE stations (Mezaira, Masdar, DEWA) peak in **July** — summer Shamal
- Kuwait stations (Shagaya, KU) peak in **May** — earlier Shamal, closer to Iraqi dust sources
- Mezaira has highest dust fraction (42%) — desert site, representative of source region
- Kuwait has lower dust fraction (23-30%) — more mixed aerosol environment
- No station reaches 2024 at Level 2.0

**Temporal overlap map**:
```
              15  16  17  18  19  20  21  22  23  24
Mezaira      [X] [X] [X] [X] [X] [X] [X] [X] [X]  .
Masdar       [X] [X] [X] [X] [X] [X] [X] [X]  .   .
Shagaya      [X] [X] [X] [X] [X]  .   .   .   .   .
Kuwait_U      .   .   .   .  [X] [X] [X]  .   .   .
DEWA          .   .   .  [X] [X] [X]  .   .   .   .
```
- **2019 is the ONLY year all 5 stations overlap** (but thin data for Mezaira & Masdar that year)
- Suggested training period: 2015–2020 (best multi-station coverage)
- Suggested test period: 2021–2022 (temporal hold-out with Mezaira + Masdar + Kuwait_U)
- 2023+: Very limited L2 ground truth — Tier 3 (L1.5) stations needed for recent years

**Data gap warnings**:
- Masdar: thin in 2015 (3.6K), 2019 (1K), 2021 (6.9K), 2022 (1.6K)
- Mezaira: thin in 2019 (8K), 2023 ends May (4K)
- DEWA: only ~1.5 years of good data (2018-late to 2020-early)
- Shagaya: good 2017-2019, thin 2015-2016

**Seasonal Shamal Coverage Assessment (2026-02-25)**:

| Station | Jun-Aug obs | Summer mean AOD | Overall mean AOD | Summer uplift | Years with summer |
|---------|-------------|-----------------|------------------|---------------|-------------------|
| Mezaira | 49,990 | 0.525 | 0.361 | +45% | 2015–2018, 2020–2022 |
| Masdar | 28,109 | 0.466 | 0.361 | +29% | 2015–2018, 2020, 2022 |
| Shagaya | 32,901 | 0.315 | 0.311 | +1% | 2015–2019 |
| Kuwait_U | 14,840 | 0.322 | 0.327 | flat | 2019–2020 |
| DEWA | 10,798 | 0.518 | 0.353 | +47% | 2019 only |
| Riyadh_SDSC | 18,049 | 0.334 | 0.299 | +12% | 2023–2025 |
| Kuwait_U2 | 8,545 | 0.369 | 0.304 | +21% | 2024–2025 |
| Khalifa_U | 0 | — | 0.285 | — | NONE |

**Key seasonal findings**:
- UAE stations (Mezaira, Masdar, DEWA) show strong summer AOD uplift (+29% to +47%) — summer Shamal signal is clear
- Kuwait stations show flat or minimal summer uplift — different dust regime, peaks in May not Jul-Aug
- Mezaira and Masdar both **missing summer 2019** — the only year all 5 L2 stations overlap
- Khalifa_U has **zero summer observations** — essentially useless for Shamal analysis
- Riyadh_SDSC covers 2023–2025 summers — fills the gap where L2 stations drop off

**Tier 3 Station Summary (2026-02-25)**:

| Station | Period | Valid AOD | Mean | Median | Std | Max | Dust% | High AOD% | Peak Month |
|---------|--------|-----------|------|--------|-----|-----|-------|-----------|------------|
| Riyadh_SDSC | 2022–2026 | 76,926 | 0.299 | 0.280 | 0.144 | 2.761 | 27.1% | 0.6% | May (0.41) |
| Kuwait_U2 | 2024–2026 | 30,591 | 0.304 | 0.274 | 0.169 | 1.560 | 25.2% | 1.4% | Aug (0.60) |
| Khalifa_U | 2025–2026 | 2,917 | 0.285 | 0.251 | 0.157 | 1.044 | 15.1% | 1.5% | Dec (0.31) |

**Tier 3 assessment**:
- **Riyadh_SDSC is the best Tier 3 station** — 77K obs, covers 2022–2025, adds Saudi Arabia geographic diversity. Peak in May consistent with northern Gulf pattern.
- **Kuwait_U2 is useful** — 31K obs, covers 2024–2025, provides Kuwait continuity after KU ended 2021.
- **Khalifa_U is near-useless** — only 2.9K obs, no summer data, peak in Dec (no dust signal). Consider dropping from analysis.

### 4.2 CAMS Forecast Data
- [x] Account created (Copernicus — shared CDS/ADS account)
- [x] API access configured (`~/.cdsapirc` + ADS endpoint)
- [x] Test download script written (7-day test: 2024-01-01 to 2024-01-07)
- [x] Test download verified — working
- [x] Full download complete — **DONE** (20 half-year files, 2015h1–2024h2)
- [x] Duplicate monthly files removed (2026-03-11) — only half-year files remain
- [x] Collocation with AERONET stations — **DONE** (2026-03-11, see section 4.2.1)

**CAMS Download Status (2026-02-27)**:
- Script: `scripts/submit_all_cams.py` (2 workers, 10-day windows, ADS endpoint)
- Merged months: 12/120 (Jan 2015 – Jan 2016)
- Temp windows: 63 downloaded (up to Jun 2017)
- Overall: ~25% complete
- Supplementary big request: `cams_duaod550_2024h1.nc` (Jan-Jun 2024, 6 months in 1 request) — queued on ADS
- **Bottleneck**: ADS queue congestion. ~30-60 min per request in queue.
- **Lesson learned**: 10-day window chunking is suboptimal — each window waits in queue separately. Monthly or 6-month requests reduce total queue waits. Max request cost limit is lower than documented field limits — 6 months works, 1 year rejected.
- After merge: run `scripts/merge_cams.py` to combine temp windows into monthly files

**CAMS API troubleshooting log**:
1. First attempt: Used CDS endpoint → 404 (CAMS data is on ADS, not CDS)
2. Second attempt: Used ADS endpoint → 403 (general site policies not accepted)
3. Third attempt: After accepting site policies → 403 (dataset-specific license not accepted)
4. Fourth attempt: After accepting dataset license → **SUCCESS** (2026-02-24)

**CAMS Test Download Results (2026-02-24)**:
- File: `cams_test_7days.nc` (87.3 KB)
- Dataset: `cams-global-atmospheric-composition-forecasts`
- Variable: `duaod550` — Dust Aerosol Optical Depth at 550nm
- Grid resolution: **0.4° × 0.4°** (36 lat × 38 lon = 1,368 grid cells over study domain)
- Dimensions: `(forecast_period=2, forecast_reference_time=7, latitude=36, longitude=38)`
- `forecast_period`: 0h (analysis/initialization) and 24h (day-ahead forecast)
- `forecast_reference_time`: One per day (00:00 UTC initialization)
- Test period stats: Min=0.00005, Max=0.59, Mean=0.073 (winter — low dust as expected)
- Source: ECMWF (GRIB converted to NetCDF via cfgrib)

**Important notes for collocation**:
- CAMS `duaod550` is dust-only AOD at 550nm; AERONET `AOD_500nm` is total AOD at 500nm
- Wavelength mismatch: 550nm vs 500nm — needs Angstrom exponent interpolation
- Aerosol type mismatch: dust-only vs total — needs Angstrom filtering (AE<0.5 = dust-dominated)
- Spatial matching: Nearest 0.4° grid cell to each AERONET station coordinates
- Temporal matching: Match CAMS forecast_reference_time + lead time to AERONET measurement time (±3h window typical in literature)

### 4.3 ERA5 Features
- [x] Variable list finalized (19 single-level + 5 pressure-level at 500/700/850 hPa)
- [x] Download script written (`scripts/era5_optimized.py`)
- [x] Data downloaded — **DONE** (250 files, ~4.9 GB)
- [ ] Feature engineering complete
- **NOTE**: Single-level files are ZIP archives containing 2 NetCDFs each (`stepType-instant.nc` + `stepType-accum.nc`). Must extract before use.
- **Cost limit discovery**: CDS rejects requests >6 months despite 120K field limit documentation. Actual cost model includes area size and format conversion. 6 months accepted, 1 year rejected.
- 6-hourly (00, 06, 12, 18 UTC), area [34, 45, 20, 60]

**ERA5 Variables**:
- Single-level (19): 10m wind u/v, 10m gust, 2m temp, skin temp, 2m dewpoint, precip, evaporation, TCWV, BLH, CAPE, surface pressure, soil moisture L1, solar/thermal radiation down, low/high cloud cover, LAI, albedo
- Pressure-level (5 × 3 levels): geopotential, u-wind, v-wind, temperature, relative humidity at 500/700/850 hPa

### 4.4 AI-GAMFS — AI Aerosol Forecasting Model (Identified 2026-02-27)

**What it is**: AI-driven Global Aerosol-Meteorology Forecasting System. A deep learning model (Vision Transformer + U-Net) that predicts dust AOD at 550nm (`DUEXTTAU`) — the exact same variable as CAMS `duaod550`. Published Dec 2024 (arXiv:2412.02498), developed by Chinese Academy of Meteorological Sciences.

**Why it matters**: The thesis proposal names GraphCast, Pangu-Weather, FuXi, GenCast as AI comparisons — but **none of them predict dust or any aerosol variable**. They're pure weather models. AI-GAMFS is the only open-source AI model that directly predicts dust AOD globally.

**Availability — FULLY OPEN SOURCE (MIT License)**:
- Code: https://github.com/zhangxutao3/AI-GAMFS
- Weights: HuggingFace (`zhangxutao/AI-GAMFS`) + Zenodo (DOI: 10.5281/zenodo.17608734)
- 4 models: `gamfs_3h/6h/9h/12h_traced.pt` (~4.85 GB each, ~19.4 GB total)
- Requirements: Python 3.11, PyTorch 2.6 + CUDA, GPU with 26+ GB VRAM

**Output variables (16 total)**:
- **`DUEXTTAU`** — Dust extinction AOT at 550nm (= CAMS duaod550)
- `DUSMASS` — Dust surface mass concentration
- `TOTEXTTAU` — Total AOD at 550nm
- Plus: black carbon, organic carbon, sulfate, sea salt (AOD + mass each)
- 4 meteorological: temperature, u-wind, v-wind, sea level pressure

**Resolution**: 0.5° × 0.625° (~50 km), 3-hourly, 5-day forecasts
**Comparison**: CAMS is 0.4° × 0.4° (~40 km) — slightly finer

**How hindcasting works**:
- AI-GAMFS needs GEOS-FP initialization data (NASA) to make a forecast
- GEOS-FP archive available at `portal.nccs.nasa.gov/datashare/gmao/geos-fp/das/`
- **Archive covers Y2014 through Y2026** — full study period available
- Feed it atmosphere state from any past date → it produces a 5-day forecast blind to what actually happened → compare against AERONET observations
- Each forecast takes ~36 seconds on GPU
- 10 years daily = ~3,650 runs = ~36 hours total GPU time

**Operational status**: Running at China's NMC since 2025, on WMO early warning platform. But platform is not publicly accessible — must run model locally.

**Benchmarking plan**:

| System | Type | Dust AOD var | Resolution | Approach |
|--------|------|-------------|------------|----------|
| CAMS | Physics-based forecast | `duaod550` (550nm) | 0.4° | Download archived forecasts |
| AI-GAMFS | AI forecast (hindcast) | `DUEXTTAU` (550nm) | 0.5° | Run locally on past GEOS-FP data |
| AERONET | Ground truth | `AOD_500nm` | Point | Already downloaded |

### 4.2.1 CAMS-AERONET Collocation Results (2026-03-11)

**Script**: `scripts/collocate_cams_aeronet.py` (vectorized, multi-threshold)
**Output**: `data/collocated/collocated_all_stations.csv` (543,254 rows)

| Station | Level | Period | Collocations | Pure Dust (AE<0.4) |
|---------|-------|--------|-------------|-------------------|
| Mezaira | L2 | 2015-03 to 2023-05 | 176,003 | 55,049 |
| Masdar_Institute | L2 | 2015-03 to 2022-08 | 113,382 | 27,346 |
| Shagaya_Park | L2 | 2015-08 to 2019-10 | 101,196 | 22,767 |
| Kuwait_University | L2 | 2019-02 to 2021-05 | 61,154 | 9,979 |
| DEWA_ResearchCentre | L2 | 2018-09 to 2020-01 | 40,122 | 6,899 |
| Riyadh_Airport_SDSC | L1.5 | 2022-11 to 2025-01 | 47,335 | 7,413 |
| Kuwait_University_2 | L1.5 | 2024-04 to 2025-01 | 4,062 | 573 |
| Khalifa_University | L1.5 | — | 0 | 0 (no CAMS overlap) |

**CAMS Benchmarking Metrics (Pure Dust, AE < 0.4):**

| Station | n | ME (bias) | MAE | RMSE | R |
|---------|---|-----------|-----|------|---|
| Masdar_Institute | 27,346 | -0.12 | 0.14 | 0.20 | 0.70 |
| DEWA_ResearchCentre | 6,899 | -0.14 | 0.17 | 0.21 | 0.68 |
| Shagaya_Park | 22,767 | -0.05 | 0.14 | 0.20 | 0.61 |
| Mezaira | 55,049 | -0.11 | 0.17 | 0.25 | 0.52 |
| Riyadh_Airport_SDSC | 7,413 | +0.08 | 0.16 | 0.20 | 0.52 |
| Kuwait_University | 9,979 | +0.03 | 0.24 | 0.33 | 0.26 |
| Kuwait_University_2 | 573 | +0.29 | 0.31 | 0.39 | 0.19 |

**Preliminary observations (NOT conclusions — need MODIS verification first):**
- UAE stations: CAMS underestimates (negative bias). R = 0.52–0.70.
- Kuwait/Riyadh: CAMS overestimates (positive bias). Kuwait_U correlation very low (R=0.26).
- Kuwait_U low correlation persists even after AE dust filtering — not just a pollution issue.
- During 2019 (only overlap year for Kuwait_U and Shagaya), both stations show poor R (~0.2).
- **Before drawing conclusions, need satellite AOD (MODIS) as independent third layer to verify whether the issue is CAMS or AERONET instrumentation.** Instrument QC checks (variability, repeated values, N-triplets) showed no anomalies, but independent verification is required.

**Lead time degradation (pure dust):**
- 3h: MAE=0.156, 6h: 0.158, 9h: 0.159, 12h: 0.176, 15h: 0.205
- Error roughly doubles from short-range to 4-day forecasts.

### 4.2.2 MODIS Satellite Verification — IN PROGRESS

**Purpose**: Independent third-layer check. If AERONET and CAMS disagree at a station (especially Kuwait), MODIS tells us who's right.
- MODIS total AOD vs AERONET total AOD = same variable, direct comparison.
- No dust filtering needed for this comparison.

**Product**: MOD08_D3 v061 (MODIS/Terra Atmosphere Daily L3 Global 1Deg CMG)
**Variable**: `Deep_Blue_Aerosol_Optical_Depth_550_Land_Mean` (works over desert)
**Also**: `AOD_550_Dark_Target_Deep_Blue_Combined_Mean` (merged DT+DB)
**Resolution**: 1° x 1° (coarse but sufficient for station-level verification)
**Access**: OPeNDAP via LAADS DAAC — extracts sub-region per day without downloading full 184 MB files.
**Script**: `scripts/download_modis_aod.py` (written, needs optimization for file list fetching speed)
**NASA Earthdata account**: registered (username: daone2028, email: ikukash@yahoo.com)
**Status**: Script written and tested. OPeNDAP extraction confirmed working. Full 2015-2024 download not yet run — file list API calls are slow (~0.6s each × 3650 days). Need to optimize by caching file lists or using CMR bulk search.

### 4.5 Benchmarking (Objective 1)
- [x] CAMS vs observations metrics calculated — **DONE** (2026-03-11, see 4.2.1)
- [x] AI model identified — **AI-GAMFS** (2026-02-27)
- [ ] AI-GAMFS hindcasts generated (needs GPU access)
- [ ] AI vs observations metrics calculated
- [ ] Stratified analysis (season, direction, intensity)
- [ ] Failure mode characterization

### 4.6 Meta-Model (Objective 2)
- [ ] Training dataset assembled
- [ ] Random Forest trained
- [ ] XGBoost trained
- [ ] Neural Network trained
- [ ] SHAP analysis complete
- [ ] Temporal cross-validation results

### 4.7 Anthropogenic Signals (Objective 3)
- [ ] Document sources identified
- [ ] LLM extraction pipeline built
- [ ] Events geocoded
- [ ] Satellite validation (MODIS NDVI, JRC water)
- [ ] Integration into meta-model
- [ ] Improvement quantified

### 4.8 Climate Robustness (Objective 4)
- [ ] CMIP6 data downloaded
- [ ] PGW synthetic datasets generated
- [ ] Meta-model applied to future scenarios
- [ ] Failure trend estimation
- [ ] Threshold identification

---

## 5. Key Decisions & Rationale

*(Record every important choice and WHY)*

### Decision 1: AERONET Station Selection (2026-02-24)
**Decision**: Use 5 stations with Level 2.0 data as primary/secondary, 3 stations with Level 1.5 as cross-checks.
**Rationale**: Level 2.0 ensures quality-assured, cloud-screened, final-calibration data suitable for model verification. The domain has severe station mortality — most stations from the 2000s are defunct. Only Mezaira has continuous long-term coverage. Level 1.5 stations add spatial coverage (Saudi Arabia) and temporal continuity (recent years) at acceptable quality for cross-verification but not primary training.
**Impact on thesis**: Spatial generalization claims must be limited. Acknowledge UAE-heavy bias. Consider supplementing with satellite AOD (MODIS, VIIRS) for broader spatial coverage.

### Decision 2: All-Points vs Daily Averages (2026-02-24)
**Decision**: Download all-points data (~15-min resolution) instead of daily averages.
**Rationale**: Three reasons drove this change:
1. CAMS forecasts are 6-hourly and ERA5 is hourly — daily averages can't be matched to specific forecast windows
2. Dust storms are sub-daily events lasting hours — daily averaging smooths out the exact peaks and misses that models get wrong, which is precisely what we need to detect for the meta-model
3. All-points can always be aggregated to daily/6-hourly/any resolution later, but daily averages cannot be disaggregated back
**Impact on thesis**: ~600K data points instead of ~6.7K. Much larger dataset for ML training. Enables time-of-day analysis (do models fail more in morning vs afternoon?). File sizes larger (634 MB total) but manageable.

### Decision 3: CAMS Lead Times — All 3-Hourly (2026-02-24)
**Decision**: Download CAMS forecasts at ALL 3-hourly lead times (0, 3, 6, 9, ... 120h) instead of only 0, 24, 48, 72, 120h.
**Rationale**: The initial download only had lead times valid at 00:00 UTC — which is nighttime in the Gulf (UTC+3 to UTC+4). AERONET is a sun photometer and only measures during daytime. With only nighttime-valid forecasts, there would be almost zero matching observation-forecast pairs. The study domain spans UTC+3 (Kuwait, Saudi, Qatar) to UTC+4 (UAE, Oman), with daytime roughly 02:00–15:00 UTC. All 3-hourly steps ensure coverage of the full diurnal cycle across all countries.
**Impact on thesis**: Larger CAMS files (~41 lead times vs 5) but enables proper temporal collocation with AERONET. Critical for valid benchmarking results.

### Decision 4: Copernicus API Architecture (2026-02-24)
**Decision**: Use ADS endpoint (`ads.atmosphere.copernicus.eu/api`) for CAMS data, CDS endpoint (`cds.climate.copernicus.eu/api`) for ERA5/CMIP6. Same API key, different base URLs.
**Rationale**: Discovered through trial-and-error that Copernicus merged user accounts but keeps separate data stores. The `~/.cdsapirc` file points to CDS by default. CAMS downloads require overriding the URL to ADS in the API client constructor.
**Impact on thesis**: Download scripts need to specify the correct endpoint per dataset. Document this for reproducibility.

### Decision 5: Download Request Sizing Strategy (2026-02-27)
**Decision**: Use 6-month single requests instead of 10-day windowed chunks. Stay under ~50% of CDS/ADS cost limits per request.
**Rationale**: Discovered through trial-and-error that:
1. **Queue wait is the bottleneck, not transfer speed** — each request waits 30–120 min in queue regardless of size. 100 small requests = 100 queue waits. 1 big request = 1 queue wait.
2. **CDS cost limits ≠ documented field limits** — documentation says 120K fields max, but actual cost model factors in area size and NetCDF conversion. 1-year requests rejected (403 "cost limits exceeded"), 6-month requests accepted.
3. **Orphaned requests waste queue slots** — killing client-side download processes leaves server-side requests running. These get processed but nobody downloads the result. Found 33 orphaned requests clogging the queue from killed processes.
4. **Per-user concurrent limits exist but are undocumented** — Copernicus Data Space has 4 concurrent limit. CDS/ADS limits are "dynamically managed." Safer to keep active requests low (2-3 per service).
**Impact on thesis**: Download timeline shortened by reducing total queue waits. Future requests should target 6-month windows. Never kill download processes mid-queue — let them finish or cancel via the web dashboard.

### Decision 6: AI-GAMFS as the AI Benchmark Model (2026-02-27)
**Decision**: Use AI-GAMFS for the AI vs physics-based model comparison (Objective 1), replacing the originally proposed GraphCast/Pangu-Weather/FuXi/GenCast.
**Rationale**: The four AI models named in the proposal (GraphCast, Pangu-Weather, FuXi, GenCast) predict ZERO aerosol variables — they are pure weather models (temperature, wind, pressure, humidity only). They cannot be benchmarked against CAMS for dust prediction because they don't predict dust. AI-GAMFS is the only open-source AI model that directly predicts dust AOD at 550nm globally. It is fully available (MIT license, code + weights on GitHub/HuggingFace/Zenodo), operational since 2025 at China's NMC, and NASA GEOS-FP initialization data covers the full 2014-2026 period for hindcasting.
**Impact on thesis**: Enables direct apple-to-apple comparison — CAMS `duaod550` vs AI-GAMFS `DUEXTTAU` vs AERONET observations, same variable (dust AOD 550nm), same region, same period. Requires GPU access (26+ GB VRAM) for ~36 hours total computation. Discuss with supervisor Dr. Mohamed for approval.

### Decision 7: Dust Identification — Multi-Threshold AE Approach (2026-03-11)
**Decision**: Replace the single AE < 0.5 threshold with a multi-threshold approach using three levels, following Di Tomaso et al. (2022):
- **AE < 0.4** — "pure dust" (primary analysis)
- **AE < 0.6** — "standard dust" (sensitivity check)
- **AE < 0.75** — "mixed dust / long-range transport" (upper bound)

Report results at all three thresholds. Use AE < 0.4 as the default for benchmarking metrics.

**Rationale**: The original script used AE < 0.5, which has no published citation. The literature uses 0.4 and 0.6 as standard thresholds:
- **Dubovik et al. (2002)**, J. Atmos. Sci., 59(3), 590–608 — foundational paper classifying aerosol types from AERONET. Uses AE ≤ 0.6 with AOD_1020 ≥ 0.3 for dust.
- **Eck et al. (2008)**, JGR, 113, D01204 — **directly studies the Arabian Gulf and UAE**. Uses AE < 0.4 for dust-dominated conditions. Reports average AE at inland desert sites of 0.50–0.57, pure dust events below 0.4.
- **Di Tomaso et al. (2022)**, Earth Syst. Sci. Data, 14, 2785–2816 — MONARCH reanalysis paper. Explicitly defines DOD-dust1 (AE < 0.4), DOD-dust2 (AE < 0.6), DOD-mixed1 (AE < 0.75) as three tiers.
- **Basart et al. (2009)**, ACP, 9, 8265–8282 — BSC/SDS-WAS methodology. Pure Saharan dust: AE < 0.3. General desert dust: AE < 0.75.
- **Kim et al. (2011)**, ACP, 11, 10733–10741 — strictest threshold: AE ≤ 0.2 with AOD_440 ≥ 0.4 for pure dust over North Africa and Arabian Peninsula.

**Impact on thesis**: Presenting results at multiple thresholds demonstrates sensitivity analysis and is more rigorous than a single arbitrary cutoff. The multi-threshold approach is publishable and defensible.

**NOTE — New rule (2026-03-11)**: Every threshold, parameter, or methodological choice in this thesis must have a citation recorded in this worklog at the time of the decision. No uncited numbers.

---

## 6. Python Environment

**Python version**: 3.11.9 (Windows)
**Setup date**: 2026-02-24

| Package | Version | Purpose |
|---------|---------|---------|
| pandas | 2.3.3 | Data manipulation |
| numpy | 2.3.5 | Numerical computing |
| matplotlib | 3.10.7 | Plotting |
| seaborn | 0.13.2 | Statistical visualization |
| scikit-learn | 1.7.2 | ML models (RF, etc.) |
| scipy | 1.16.3 | Statistical tests |
| xarray | 2026.2.0 | NetCDF handling (CAMS, ERA5) |
| netCDF4 | 1.7.4 | NetCDF file I/O |
| xgboost | 3.2.0 | XGBoost classifier |
| cdsapi | 0.7.7 | Copernicus data download |
| shap | 0.50.0 | Model interpretability |
| cartopy | 0.25.0 | Geographic plotting |
| jupyter | — | Interactive analysis |

---

## 7. File Structure

```
C:\Users\LENOVO\Desktop\THESIS\
├── Thesis_Proposal_IMGAIA.pdf      # Original proposal
├── Thesis_Proposal_IMGAIA.docx     # Editable proposal
├── thesis-worklog.md               # THIS FILE — master reference
├── data\
│   ├── aeronet\
│   │   ├── level2\                 # ✅ DOWNLOADED (5 files, 518 MB)
│   │   │   ├── Mezaira_AOD20_allpoints.csv              (183 MB, 176K rows)
│   │   │   ├── Masdar_Institute_AOD20_allpoints.csv     (120 MB, 113K rows)
│   │   │   ├── Shagaya_Park_AOD20_allpoints.csv         (107 MB, 101K rows)
│   │   │   ├── Kuwait_University_AOD20_allpoints.csv    (65 MB, 61K rows)
│   │   │   └── DEWA_ResearchCentre_AOD20_allpoints.csv  (43 MB, 40K rows)
│   │   └── level15\                # ✅ DOWNLOADED (3 files, 118 MB)
│   │       ├── Riyadh_Airport_SDSC_AOD15_allpoints.csv  (82 MB, 77K rows)
│   │       ├── Kuwait_University_2_AOD15_allpoints.csv  (33 MB, 31K rows)
│   │       └── Khalifa_University_AOD15_allpoints.csv   (3.1 MB, 2.9K rows)
│   ├── cams\                       # ✅ Test download success (87 KB), full download pending
│   │   └── cams_test_7days.nc                             (87 KB, 7 days)
│   ├── era5\                       # Pending (needs Copernicus account)
│   ├── cmip6\                      # Pending (Phase 4)
│   └── satellite\                  # Pending (MODIS, VIIRS)
├── scripts\                        # To be created
├── figures\                        # To be created
└── chapters\                       # To be created
```

---

## 8. References Used in This Log

- AERONET V3 Web Service: https://aeronet.gsfc.nasa.gov
- Copernicus CDS: https://cds.climate.copernicus.eu
- Copernicus ADS: https://ads.atmosphere.copernicus.eu
- Thesis Proposal: Kukash, I. D. (2025). "An Integrated Meta-Modeling and Generative-AI Approach..." University of Sharjah.

---

*Last updated: 2026-03-11 (session 4 — full collocation 543K rows, multi-threshold dust classification with citations, CAMS benchmarking metrics, MODIS third-layer verification initiated, data coverage table added, duplicate CAMS files cleaned, Decision 7 added)*
