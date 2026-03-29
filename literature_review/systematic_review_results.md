# Systematic Literature Review Results — DRAFT
## Date: 2026-02-25
## Conducted by: Claude (AI-assisted) — to be verified by Ibrahim D. Kukash
## Database: Web search (Google Scholar equivalent) — NOT Scopus/WoS

---

## Research Question
"Has anyone used machine learning to predict when dust forecasting models will fail, and has anyone integrated anthropogenic land-use signals into dust forecast error prediction?"

---

## Search Results Summary

| Search ID | Query Focus | Results Screened | Relevant Papers |
|-----------|-------------|-----------------|-----------------|
| S1 | ML for dust forecast error | ~10 | 3 |
| S2 | Meta-model for dust prediction | ~10 | 4 |
| S3 | Anthropogenic dust + model performance | ~10 | 3 |
| S4 | LLMs in atmospheric science | ~10 | 5 |
| S5 | CAMS dust evaluation + AERONET + ML | ~10 | 4 |
| S6 | Predict when forecast model fails | ~10 | 3 |
| **Total screened** | | **~60** | **~22 unique** |

**NOTE**: Exact result counts unavailable — web search does not return total hit counts like Scopus/WoS. Numbers above are approximate based on top-10 results per query.

---

## Papers Identified by Sub-Question

### SQ1: Has ML been used to predict dust forecast MODEL ERROR (not dust itself)?

| # | Paper | Year | What they did | Relation to our thesis |
|---|-------|------|---------------|----------------------|
| 1 | Correction of CAMS PM10 Reanalysis Improves AI-Based Dust Event Forecast (Remote Sensing, 17(2), 222) | 2025 | Used XGBoost to CORRECT CAMS PM10 bias, then fed corrected data into CNN for dust event forecasting. Features: temporal, NDVI, wind, AOD. | **Closest to our work.** But they CORRECT the output (bias correction), not PREDICT when it will fail (failure classification). Different goal. |
| 2 | ML for observation bias correction in dust data assimilation (ACP, 19, 10009) | 2019 | LSTM to separate dust from non-dust PM10 before assimilation. | Corrects observations, not forecasts. Preprocessing step, not meta-model. |
| 3 | ML-SDC ensemble for surface dust concentration, Northern China (Sci. Total Environ., 2025) | 2025 | Stacking ensemble (LSTM+CNN+SVM) combining multiple dust models. | Multi-model combination, not error prediction. Improves dust forecast but doesn't predict failure. |
| 4 | Comparative analysis CAMS vs AERONET Eastern Mediterranean, 19 years (ESPR, 2024) | 2024 | Evaluated CAMS AOD against AERONET. Found CAMS underestimates at high AOD (>0.5). | Pure evaluation, no ML. But confirms CAMS has systematic errors — supports our premise. |
| 5 | AOD analysis MENA using ML (Earth Sys. Environ., 2024) | 2024 | XGBoost to evaluate reanalysis AOD products over Middle East. | Evaluation + ML but not failure prediction. |

**FINDING: No paper found that uses ML to PREDICT WHEN a dust forecast model will fail (failure as a classification target). All existing work either (a) predicts dust directly, (b) corrects model bias, or (c) evaluates model performance retrospectively.**

### SQ2: Have anthropogenic land-use changes been linked to dust forecast performance?

| # | Paper | Year | What they did | Relation to our thesis |
|---|-------|------|---------------|----------------------|
| 6 | Land degradation drivers of anthropogenic sand and dust storms (CATENA, 2022) | 2022 | Reviewed drivers: agriculture, overgrazing, water misuse. Found "relationships between observed impacts and respective drivers poorly studied." | Supports our premise. Identifies the gap we aim to fill. |
| 7 | Anthropogenic dust emissions in Southwest Asia 2000-2020 (Lee et al., Atmos. Environ., 2025) | 2025 | Quantified anthropogenic dust trends in our exact study region. Found detectable signal. | **Key paper.** Proves the anthropogenic signal exists. But they did NOT link it to forecast error. |
| 8 | Ginoux 2012 — Global anthropogenic dust (Reviews of Geophysics) | 2012 | 25% of global dust is anthropogenic. MODIS-based classification. | Foundational. Establishes that anthropogenic dust is significant globally. |
| 9 | Historical footprints and future projections of global dust (npj Clim. Atmos. Sci., 2023) | 2023 | Bias-corrected CMIP6 for dust projections. Found models underestimate by 7-21%. | Relevant to Phase 4. Shows models have systematic dust bias under climate change. |
| 10 | CAMS global anthropogenic emissions dataset (ESSD, 2024) | 2024 | CAMS-GLOB-ANT: the emission inventory CAMS actually uses. | Relevant — shows what CAMS knows about. If anthropogenic dust sources aren't in this inventory, CAMS can't account for them. |

**FINDING: Anthropogenic dust sources are well-documented and quantified. Lee et al. 2025 proves the signal exists in our region. But NO paper links anthropogenic land-use changes to dust FORECAST ERROR. The connection between "land changed" and "model got worse" has not been tested.**

### SQ3: Have LLMs/NLP been used for environmental event extraction integrated into atmospheric models?

| # | Paper | Year | What they did | Relation to our thesis |
|---|-------|------|---------------|----------------------|
| 11 | AirGPT v1 — Conversational AI for atmospheric science (npj Clim. Atmos. Sci., 2025) | 2025 | LLM + RAG over atmospheric literature. Answers air quality questions. | Proves LLMs can work in atmospheric domain. But it's a Q&A system, not event extraction. |
| 12 | AirGPT v2 — Spatio-temporal LLM for air quality prediction (Information Fusion, 2025) | 2025 | Fine-tuned LLM for air quality forecasting using spatio-temporal fusion. | LLM AS a predictor, not for text extraction. Different use case. |
| 13 | Emission-GPT — LLM agent for emission inventory (arXiv, 2025) | 2025 | LLM + RAG + function calling for emission data analysis. | Closest to our GenAI approach. But focused on emission inventories, not event extraction from unstructured documents. |
| 14 | LLM for One Atmosphere benchmark (ES&T, 2025) | 2025 | Benchmarked 11 LLMs on atmospheric science tasks. Measured hallucination rates. | Useful reference for validating our LLM pipeline. Shows LLMs can handle atmospheric knowledge. |
| 15 | Structured information extraction from scientific text (Nature Comms, 2024) | 2024 | General LLM information extraction framework. | Methodological reference. Not atmospheric-specific. |
| 16 | LLM event extraction for habitat/environmental impact (U. Southampton, ongoing) | ongoing | PhD project on LLM event extraction from social media for environmental events. | Most similar to our approach. But focused on social media, not scientific/policy documents. Not published yet. |

**FINDING: LLMs are entering atmospheric science rapidly (2025 boom). Applications include Q&A systems (AirGPT), prediction (AirGPT v2), emission analysis (Emission-GPT). But NO paper uses LLMs to extract anthropogenic land-use events and integrate them as features in a dust forecast meta-model.**

### SQ-bonus: Does anyone predict WHEN ANY weather model will fail?

| # | Paper | Year | What they did | Relation to our thesis |
|---|-------|------|---------------|----------------------|
| 17 | CNN for forecast confidence estimation (referenced in ML weather survey, 2024) | 2024 | CNN assigns confidence score to medium-range forecasts based on atmospheric state at initialization. | **Same concept as our meta-model** but for general weather, not dust. Proves the approach is valid. |
| 18 | Probabilistic weather forecasting with ML (Nature, 2024) | 2024 | ML models that produce probability distributions, not just point forecasts. | Related but different — they build uncertainty INTO the forecast, not a separate failure predictor. |
| 19 | Bonavita 2024 — Limitations of ML weather prediction (GRL) | 2024 | Documented when ML weather models fail (extreme events, balance relationships). | Characterizes failure modes but doesn't predict them. |

**FINDING: The concept of predicting model failure exists in weather forecasting but is very new (2024). It has NOT been applied to dust/aerosol forecasting specifically.**

---

## PRISMA-Style Flow (Approximate)

```
Records identified from web searches (6 queries × ~10 results)
                    ↓
            ~60 results screened by title
                    ↓
        Duplicates removed: ~15
                    ↓
        Titles relevant: ~30
                    ↓
    Abstracts/summaries assessed: ~30
                    ↓
    Excluded (not relevant to RQ): ~11
                    ↓
    Papers included in review: ~19
                    ↓
    Full text accessed and read: 5
    Abstract/summary only: 14
```

**LIMITATION**: Most papers could only be assessed via abstract/search snippet. Full-text verification was possible for only ~5 open-access papers. Paywalled papers need verification through university library access.

---

## Gap Analysis — What's Missing in the Literature

| Gap | Evidence | Our thesis fills it? |
|-----|----------|---------------------|
| **No ML meta-model for dust forecast FAILURE prediction** | S1 search: all papers predict dust or correct bias, none predict failure | YES — Objective 2 |
| **No link between anthropogenic land-use and forecast ERROR** | S3 search: land-use → dust emission studied, but not → forecast error | YES — Objective 3 |
| **No LLM event extraction integrated into dust models** | S4 search: LLMs entering atmos science but not for this purpose | YES — Objective 3 |
| **No comparison of LLM vs traditional ML as meta-models for forecast verification** | Not found in any search | POSSIBLE addition |
| **No climate stress-test of dust meta-models** | PGW approach exists but not applied to dust failure prediction | YES — Objective 4 |

---

## Key Papers to Cite (Priority Reading List)

1. **MUST READ**: Lee et al. (2025) — Anthropogenic dust emissions Southwest Asia — proves signal exists in our region
2. **MUST READ**: CAMS PM10 correction paper (Remote Sensing, 2025) — closest existing work to ours
3. **MUST READ**: AirGPT (npj, 2025) — sets precedent for LLMs in atmospheric science
4. **MUST READ**: ML meta-analysis for dust (AAQR, 2022) — documents the gap we fill
5. **SHOULD READ**: Emission-GPT (arXiv, 2025) — methodological reference for our LLM pipeline
6. **SHOULD READ**: Probabilistic weather forecasting (Nature, 2024) — context for uncertainty quantification
7. **SHOULD READ**: Ginoux (2012) — foundational anthropogenic dust quantification
8. **SHOULD READ**: CAMS vs AERONET Eastern Mediterranean (ESPR, 2024) — validates CAMS has the errors we claim

---

## Caveats

1. This review used web search only — NOT Scopus or Web of Science
2. Full-text access was limited to open-access papers
3. ~14 papers assessed by abstract/snippet only — findings need full-text verification
4. Search was conducted in one session (2026-02-25) — not iterated
5. Non-English literature not covered
6. **This review should be repeated using Scopus + Web of Science through university library access before making novelty claims in the thesis**
