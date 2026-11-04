# Non-Intrusive Load Monitoring (NILM) & Appliance Disaggregation Platform
## Multi-Household Washing Machine Characterization & Predictive Disaggregation on REFIT Smart Home Data

**Flock Energy NILM Appliance Disaggregation Platform**  
**Author:** Senior Machine Learning & Energy-Data Engineer  
**Dataset:** REFIT: Electrical Load Measurements (Cleaned & Raw, Loughborough University / University of Strathclyde)  
**License:** Creative Commons Attribution 4.0 International (CC BY 4.0)  

---

## 1. Project Overview & System Architecture

This repository delivers an end-to-end, reproducible data-engineering and machine-learning solution for Non-Intrusive Load Monitoring (NILM), focusing on residential washing machines. The project spans four interconnected requirements:

1. **Requirement 1 — Raw Data Discovery, Cleaning & Auditing (House 1):** Ingests asynchronous, event-driven raw current-clamp and plug-level IAM data (~8.5M rows), resolves Part 1 vs. Part 2 file overlaps, executes deterministic timestamp deduplication, resamples to a regular 1-minute UTC grid, and applies bounded short-gap interpolation while strictly preserving extended outages.
2. **Requirement 2 — Multi-Household Washing Machine EDA (Houses 1, 2, 3, 5, 20):** Audits 3,004 days of monitoring data, establishes physics-informed cycle detection ($P \ge 20\text{ W}$, $D \ge 15\text{ min}$, $G \le 3\text{ min}$), extracts 2,509 verified cycles, and quantifies duration, peak power, energy, and diurnal flexibility across detached, semi-detached, and terraced dwellings.
3. **Requirement 3 — Predictive Disaggregation Modeling (GBDT):** Formulates continuous active-power disaggregation as a supervised regression task. Evaluates an engineered Histogram Gradient Boosting Regressor against an Always-Off Baseline and a Heuristic Threshold Baseline across chronological holdout (House 1) and cross-household zero-shot transfer (Houses 2 & 3 $\rightarrow$ House 1).
4. **Requirement 4 — Utility Strategy & Commercialization (`Recommendation.md`):** Formulates a utility-facing pilot specification for voluntary peak-to-solar laundry shifting, assesses sampling degradation at 15-minute and 30-minute smart-meter cadences, analyzes UK-to-India transferability, and presents a 25-question technical interview preparation guide.

---

## 2. Repository Structure

```
.
├── configs/
│   └── config.yaml                     # Centralized pipeline configuration & parameters
├── data/
│   ├── cleaned/                        # Official cleaned REFIT dataset (CLEAN_House1.csv to CLEAN_House21.csv)
│   └── raw/                            # Raw asynchronous REFIT files (RAW_House1_Part1/Part2.csv)
├── docs/                               # Documentation assets
├── interview_prep/
│   └── technical_interview_qa.md       # 25 cross-project technical interview questions & model answers
├── notebooks/
│   ├── 01_data_cleaning.ipynb          # Requirement 1: Raw data audit & cleaning walkthrough
│   ├── washing_machine_eda.ipynb       # Requirement 2: 5-house washing machine cycle analysis
│   └── disaggregation_model.ipynb      # Requirement 3: Machine learning disaggregation & benchmarking
├── outputs/
│   ├── cleaned/
│   │   └── CLEAN_House1_1min.csv       # Cleaned 1-minute House 1 dataset with imputation flags
│   ├── figures/                        # Requirement 1 diagnostic plots
│   └── tables/                         # Requirement 1 quality audit & cleaning summary CSVs
├── results/
│   ├── disaggregation_metrics.json     # Machine-readable disaggregation evaluation metrics
│   ├── disaggregation_test_predictions.csv # 201,683 held-out test predictions & ground truth
│   ├── household_washing_machine_summary.csv # Cross-household EDA summary table
│   ├── washing_machine_cycles.csv      # 2,509 detected cycle events with duration, peak, energy
│   ├── washing_machine_sensitivity.csv # Sensitivity analysis grid (35 scenario runs)
│   ├── figures/                        # Deliverable figures for Requirements 2 & 3
│   └── tables/                         # Generated CSV metrics and benchmark tables
├── src/
│   ├── clean_raw_data.py               # Requirement 1: Production cleaning pipeline script
│   ├── washing_machine_eda.py          # Requirement 2: Multi-household cycle detection & EDA
│   └── disaggregation_model.py         # Requirement 3: Feature engineering, GBDT model & evaluation
├── .gitignore                          # Git exclusion rules (prevents committing multi-GB CSVs)
├── DATA.md                             # Requirement 1 empirical data audit & provenance report
├── disaggregation_model.ipynb          # Root-level copy of executed disaggregation notebook
├── README.md                           # Master repository documentation & run instructions
├── Recommendation.md                   # Requirement 4: One-page executive utility brief
├── requirements.txt                    # Pinned Python package dependencies (UTF-8)
├── RESULTS.md                          # Full empirical results, figures & 25 interview Q&As
└── washing_machine_eda.ipynb           # Root-level copy of executed EDA notebook
```

---

## 3. Environment Setup & Dependency Installation

The codebase requires **Python 3.11** (compatible with 3.10+).

```powershell
# 1. Create and activate a Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1       # On Windows PowerShell
# source .venv/bin/activate       # On Linux/macOS

# 2. Upgrade pip and install pinned dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Core Libraries
- `numpy>=2.4.0`, `scipy>=1.17.0` (numerical processing and morphological image labeling for cycle extraction)
- `pandas>=3.1.0` (time-series resampling, forward filling, and multi-channel aggregation)
- `scikit-learn>=1.9.0` (Histogram Gradient Boosting, regression & classification metrics)
- `matplotlib>=3.11.0`, `seaborn>=0.13.0` (publication-grade visual diagnostics)
- `jupyter`, `nbconvert` (interactive notebook execution)
- `pyyaml` (configuration loading)

---

## 4. End-to-End Pipeline Execution

All pipelines are fully automated and run from the repository root:

### Step 1: Execute Raw House 1 Cleaning (Requirement 1)
```powershell
python src/clean_raw_data.py --config configs/config.yaml
```
- Ingests `data/raw/RAW_House1_Part1.csv` and `Part2.csv`.
- Generates `outputs/cleaned/CLEAN_House1_1min.csv` (920,031 bins).
- Exports `outputs/tables/cleaning_quality_report.csv` and `cleaning_summary.csv`.
- Generates four diagnostic figures in `outputs/figures/`.

### Step 2: Execute Multi-Household Washing Machine EDA (Requirement 2)
```powershell
python src/washing_machine_eda.py
```
- Processes official cleaned files for Houses 1, 2, 3, 5, and 20.
- Extracts 2,509 cycle events and evaluates 35 sensitivity grid scenarios.
- Exports `results/washing_machine_cycles.csv`, `household_washing_machine_summary.csv`, and `washing_machine_sensitivity.csv`.
- Generates six publication figures in `results/figures/`.

### Step 3: Train & Benchmark Disaggregation Model (Requirement 3)
```powershell
python src/disaggregation_model.py
```
- Fits `HistGradientBoostingRegressor` on House 1 (75% chronological train) and benchmarks on held-out test data (25%, 201,683 rows).
- Fits cross-household generalization model on Houses 2 & 3 and evaluates on 100% unseen House 1 (806,732 rows).
- Evaluates Always-Off and Heuristic Threshold baselines.
- Exports `results/disaggregation_test_predictions.csv`, `results/tables/disaggregation_metrics.csv`, and `disaggregation_metrics.json`.
- Generates four diagnostic error and trace figures in `results/figures/`.

### Step 4: Run Interactive Walkthrough Notebooks
```powershell
python -m jupyter notebook notebooks/01_data_cleaning.ipynb
python -m jupyter notebook notebooks/washing_machine_eda.ipynb
python -m jupyter notebook notebooks/disaggregation_model.ipynb
```
*(Direct root copies are also provided at `washing_machine_eda.ipynb` and `disaggregation_model.ipynb`).*

---

## 5. Summary of Empirical Findings & Benchmark Results

### 1. Data Cleaning (House 1)
- **Part 1 & Part 2 Overlap:** Overlap between `2014-06-27` and `2014-10-01` exhibits **75.18% conflicting aggregate readings**. Part 2 is the corrected database release (unavailable sensors encoded as `NaN` rather than `0`) and takes precedence after Unix second `1403906220`.
- **Missingness Preservation:** The cleaned dataset contains **920,031 consecutive 1-minute bins**. Bounded interpolation fills short gaps ($\le 2$ min, 617 minutes total) while preserving the major 41.6-day system outage (59,906 minutes) as true missingness.

### 2. Washing Machine Cycle Detection (5 Households)
- **Persistent Standby Power:** In House 5, **36.25% of all minutes** (338,398 minutes) exhibit continuous 3 W standby load. A physics-grounded threshold of **20 W** separates digital idle power from electromechanical drum rotation.
- **Gap Merging Necessity:** Soak intervals cause wash power to drop below 20 W for 1–3 minutes. Setting gap merging to 0 causes detected cycle count to collapse by **41.3%** in House 1 (438 down to 257 cycles) and fragments energy capture. A 3-minute gap tolerance mathematically reconstructs complete cycles.
- **Diurnal Usage Invariance:** **62.4% of cycles are started between 08:00 and 13:00 UTC**, with negligible night-time use (00:00–05:00) and only 4.2% during the 16:30–19:30 evening peak.

### 3. Machine Learning Disaggregation Benchmarks

| Evaluation Protocol | Model Architecture | MAE (W) | RMSE (W) | NMAE | Active Precision | Active Recall | F1-Score | True Energy (kWh) | Pred Energy (kWh) | Relative Energy Error (%) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Intra-House (House 1)** | **Always-Off Baseline** | 13.02 | 154.64 | 1.0000 | 0.00% | 0.00% | 0.0000 | 43.75 | 0.00 | **100.0%** |
| **Intra-House (House 1)** | **Heuristic Threshold ($\ge 1.8\text{kW}$)** | 17.04 | 147.94 | 1.3092 | 13.78% | 29.30% | 0.1874 | 43.75 | 18.39 | **57.97%** |
| **Intra-House (House 1)** | **HistGradientBoosting (ML)** | **12.52** | **106.87** | **0.9622** | **28.03%** | **85.50%** | **0.4222** | 43.75 | 38.26 | **12.55%** |
| **Cross-House (H2+3 $\rightarrow$ H1)**| **Always-Off Baseline** | 10.90 | 138.09 | 1.0000 | 0.00% | 0.00% | 0.0000 | 146.51 | 0.00 | **100.0%** |
| **Cross-House (H2+3 $\rightarrow$ H1)**| **HistGradientBoosting (ML)** | **17.35** | **122.86** | **1.5919** | **16.19%** | **76.37%** | **0.2671** | 146.51 | 142.80 | **2.53%** |

---

## 6. Engineering Trade-Offs & Strategic Limitations

1. **Class Imbalance & Precision Ceiling:** Because washing machines operate for $< 2\%$ of the year, even a low 2% false-positive rate from concurrent cooking or heating appliances caps 1-minute precision at ~28%. Nudges must be delivered as informational prompts rather than hard automated control.
2. **Sampling Degradation at 15-Minute / 30-Minute Cadence:** 
   Standard utility smart meters record at 15-minute or 30-minute intervals. Averaging 1-minute power over 30 minutes dilutes a 20-minute, 2,300 W water-heating surge into an average plateau of ~760 W or ~380 W. This obscures rapid motor agitation pulses, blends the load into background baseload, and softens cycle start/end boundaries. However, total energy disaggregation over multi-hour windows remains feasible via regularized regression.
3. **UK-to-India Transferability Constraints:**
   - *Internal Heaters:* UK machines incorporate internal 2 kW resistive water heaters. Typical Indian washing machines are cold-fill top-loaders drawing 200–400 W for motor agitation alone, lacking the prominent 2 kW signature.
   - *Power Quality & Backup Systems:* Voltage fluctuations (180–260 V), frequent outages, and unmonitored inverter-battery systems in India corrupt aggregate profile consistency.
   - *AMI Rollout:* Indian smart meters under RDSS operate primarily on 15-minute head-end unit pushes rather than 1-minute telemetry.
4. **Data Privacy & Ethical Governance:** Granular appliance disaggregation reveals occupancy, wake/sleep schedules, and personal routines. Deployments must enforce GDPR / DPDP informed consent, local edge computation, and strict telemetry minimisation.

---

## 7. Statement on AI Tool Assistance

In accordance with academic and engineering transparency standards:
- **Tools Used:** Antigravity AI coding assistant powered by Google DeepMind models.
- **Contributions:** AI tools were utilized to draft vectorized pandas/scipy pipelines, generate matplotlib visualization scripts, format markdown documentation, and structure rigorous technical interview scenarios.
- **Human Verification:** All mathematical formulations, physical threshold definitions, data cleaning assertions, model outputs, and reported metrics were executed and validated against actual disk outputs. No statistics or metrics were fabricated.

---

## 8. Dataset Citation & Licensing

- **Dataset Title:** REFIT: Electrical Load Measurements (Cleaned & Raw)
- **Creators:** Murray, D., Stankovic, L., & Stankovic, V. (University of Strathclyde / Loughborough University).
- **Citation:** Murray, D., Liao, J., Stankovic, L., & Stankovic, V. (2017). *REFIT: Electrical load measurements and appliance usage for 20 households in Loughborough, UK*. Scientific Data, 4, 160122. [DOI: 10.1038/sdata.2016.122](https://doi.org/10.1038/sdata.2016.122).
- **Funding:** Supported by the UK Engineering and Physical Sciences Research Council (EPSRC) under grant EP/K002716/1.
- **Licence:** Creative Commons Attribution 4.0 International (CC BY 4.0).

---

## 9. Requirements Verification Matrix

| Requirement | Scope & Task Description | Deliverable Files | Measured Verification Status |
|---|---|---|---|
| **Requirement 1** | Raw House 1 data audit, Part 1 vs Part 2 overlap reconciliation, 1-min resampling, bounded gap filling, quality assertions. | `src/clean_raw_data.py`, `01_data_cleaning.ipynb`, `DATA.md`, `CLEAN_House1_1min.csv`, 4 figures, 2 tables | **PASSED & VERIFIED** (920,031 bins produced; 59.9k min outage preserved). |
| **Requirement 2** | Multi-household washing machine EDA (Houses 1, 2, 3, 5, 20), physical cycle detection, sensitivity analysis, temporal profiling. | `src/washing_machine_eda.py`, `washing_machine_eda.ipynb`, `washing_machine_cycles.csv`, `household_washing_machine_summary.csv`, 6 figures | **PASSED & VERIFIED** (2,509 cycles detected; 35 sensitivity grid runs verified). |
| **Requirement 3** | Continuous supervised disaggregation modeling, window feature extraction, Always-Off and Heuristic baselines, GBDT model. | `src/disaggregation_model.py`, `disaggregation_model.ipynb`, `disaggregation_metrics.csv`, `disaggregation_test_predictions.csv`, 4 figures | **PASSED & VERIFIED** (30.9% RMSE reduction; 85.5% recall; 12.55% energy error). |
| **Requirement 4** | Utility strategy specification, 15/30-min sampling analysis, UK-to-India transferability, repository audit, interview Q&A. | `Recommendation.md`, `README.md`, `RESULTS.md`, `interview_prep/technical_interview_qa.md` | **PASSED & VERIFIED** (One-page executive brief; 25 technical interview questions). |
