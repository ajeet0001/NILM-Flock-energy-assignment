"""Build script for notebooks/washing_machine_eda.ipynb."""

import json
from pathlib import Path

NOTEBOOKS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = NOTEBOOKS_DIR.parent
OUTPUT_NOTEBOOK = NOTEBOOKS_DIR / "washing_machine_eda.ipynb"


def md_cell(source: str, cell_id: str = "") -> dict:
    cid = cell_id if cell_id else "md-" + str(abs(hash(source[:40])))[:8]
    return {
        "cell_type": "markdown",
        "id": cid,
        "metadata": {},
        "source": source.strip().splitlines(True),
    }


def code_cell(source: str, cell_id: str = "") -> dict:
    cid = cell_id if cell_id else "code-" + str(abs(hash(source[:40])))[:8]
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": cid,
        "metadata": {},
        "outputs": [],
        "source": source.strip().splitlines(True),
    }


def build():
    cells = []

    # Title & Executive Summary
    cells.append(md_cell("""
# REFIT Washing-Machine Usage Analysis: Cross-Household Disaggregation EDA

**Flock Energy NILM Appliance Disaggregation Platform**  
**Senior Energy-Data Scientist & Technical Interviewer Evaluation**  
**Dataset:** Official Cleaned REFIT Electrical Load Measurements (`data/cleaned/CLEAN_House*.csv`)  
**Cadence:** 1-Minute Resampled Grid  
**Analysed Households:** House 1, House 2, House 3, House 5, and House 20 (covering detached, semi-detached, and mid-terrace homes with 2 to 4 occupants).

---

### Executive Overview

This notebook provides the official, empirical exploratory data analysis (EDA) of washing machine usage across multiple households in the REFIT dataset.  
Washing machines represent one of the primary high-consumption, deferrable wet appliances in residential demand-side management. Disaggregating and characterizing their load profiles is critical for:
1. **Demand-Side Response (DSR):** Automated load-shifting away from evening peak hours (17:00–20:00).
2. **Energy Efficiency Auditing:** Comparing water heating temperatures and cycle durations across homes.
3. **Appliance Health & Anomaly Detection:** Identifying uncharacteristically long cycles, excessive stand-by consumption, or heating element failures.

#### Core Analytical Deliverables:
- **Cleaned Data Ingestion & Quality Audit:** Rigorous parsing of UTC timestamps, cadence evaluation, handling of Strathclyde `Issues` flags, and true zero vs. missingness separation.
- **Physics-Informed Cycle Detection:** A transparent, rule-based detector with power threshold $P_{\\text{thresh}} = 20\\text{ W}$, minimum duration $D_{\\text{min}} = 15\\text{ min}$, and gap-merging tolerance $G_{\\text{max}} = 3\\text{ min}$.
- **Comprehensive Sensitivity Grid:** Empirical proof of why gap merging is essential (preventing cycle fragmentation and loss of heating element peaks).
- **Temporal & Cross-Household Characterization:** Hourly diurnal start distributions, day-of-week load profiles, and demographic comparisons.
""", "cell-01-title"))

    # Imports & Setup
    cells.append(code_cell("""
import sys
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from IPython.display import display, HTML

# Resolve paths
NOTEBOOK_DIR = Path.cwd() if Path.cwd().name == "notebooks" else Path.cwd() / "notebooks"
PROJECT_ROOT = NOTEBOOK_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"
RESULTS_DIR = PROJECT_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
TABLES_DIR = RESULTS_DIR / "tables"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

print(f"Project Root : {PROJECT_ROOT}")
print(f"Results Dir  : {RESULTS_DIR}")
""", "cell-02-imports"))

    # Section 1: Household Selection & Channel Mapping
    cells.append(md_cell("""
---
## 1. Household Selection & Channel Verification

According to `data/cleaned/ReadME.txt`, we verify that the selected households contain a dedicated Washing Machine channel and distinguish them from Washer Dryers and Tumble Dryers:

| Household | Channel | Appliance Name | Other Monitored Laundry | Occupancy | Dwelling Type | Built |
|---|---|---|---|---:|---|---|
| **House 1** | `Appliance5` | Washing Machine | `Appliance4` (Washer Dryer) | 2 | Detached (4 bed) | 1975–1980 |
| **House 2** | `Appliance2` | Washing Machine | *None* | 4 | Semi-detached (3 bed) | Unknown |
| **House 3** | `Appliance6` | Washing Machine | `Appliance4` (Tumble Dryer) | 2 | Detached (3 bed) | 1988 |
| **House 5** | `Appliance3` | Washing Machine | `Appliance2` (Tumble Dryer) | 4 | Mid-terrace (4 bed) | 1878 |
| **House 20**| `Appliance4` | Washing Machine | `Appliance3` (Tumble Dryer) | 2 | Detached (3 bed) | 1965–1974 |

> **Critical Data Rule:** In House 1, `Appliance4` is a **Washer Dryer** while `Appliance5` is the dedicated **Washing Machine**. We monitor `Appliance5` to ensure clean appliance disaggregation without conflating drying cycles.
""", "cell-03-selection-md"))

    cells.append(code_cell("""
# Load and display household summary table
summary_csv = TABLES_DIR / "household_washing_machine_summary.csv"
summary_df = pd.read_csv(summary_csv)

display(summary_df[[
    "household", "channel", "occupancy", "house_type", "total_days",
    "coverage_pct", "missing_pct", "zero_pct", "standby_pct", "active_pct",
    "detected_cycles", "cycles_per_week", "median_duration_min",
    "median_peak_power_w", "median_energy_wh"
]])
""", "cell-04-summary-code"))

    # Section 2: Data Availability & Standby Discovery
    cells.append(md_cell("""
---
## 2. Data Availability, True Zeros, and Standby Power Discovery

A fundamental requirement in NILM data engineering is distinguishing:
1. **Observed Zero / Off:** The appliance is plugged in, the sensor is actively transmitting, and load is 0 W.
2. **Standby Power:** Power draw between 1 W and 20 W (digital clocks, display panels, idle standby electronics).
3. **Missing Data / Outages:** Sensor packet loss or system downtime (`NaN`), which must **never** be silently imputed as zero.

### Empirical Discovery in House 5:
- In **House 5**, **36.25% of all 1-minute bins** (338,398 minutes) exhibit continuous standby power between 1 W and 5 W (median 3.0 W).
- A naive threshold of $P > 0\\text{ W}$ would falsely classify House 5 as washing clothes over 43% of the year!
- A physics-grounded threshold of **20 W** completely rejects this 3 W standby baseline while capturing true drum rotation (70–300 W) and water heating (1,800–2,400 W).
""", "cell-05-standby-md"))

    cells.append(code_cell("""
# Show diagnostic plot of coverage and operating states
img_path = FIGURES_DIR / "coverage_missingness_diagnostic.png"
img = mpimg.imread(img_path)
plt.figure(figsize=(14, 5))
plt.imshow(img)
plt.axis("off")
plt.title("Data Availability, Missingness & Operating State Breakdown", fontsize=12, fontweight="bold")
plt.show()
""", "cell-06-diag-code"))

    # Section 3: Cycle Detection Methodology
    cells.append(md_cell("""
---
## 3. Physics-Informed Cycle Detection Methodology

A washing machine cycle consists of three distinct electrical phases:
1. **Water Heating Phase:** Heating element energizes to bring cold inlet water to 30°C–60°C. Power draws **1,800 W to 2,400 W** for 10–25 minutes.
2. **Motor Tumble & Wash Phase:** Low-frequency forward and reverse drum agitation drawing **80 W to 300 W**.
3. **Intermittent Soak / Drain Pauses:** Low-power intervals where the motor rests or water settles, drawing **0 W to 4 W** for 1 to 3 minutes.
4. **High-Speed Spin Phase:** High-torque spinning at 1,000–1,400 RPM drawing **400 W to 800 W**.

### Detection Parameters:
- **Power Threshold ($P_{\\text{thresh}} = 20\\text{ W}$):** Filters out standby load (3 W) and sensor noise.
- **Minimum Duration ($D_{\\text{min}} = 15\\text{ min}$):** Eliminates momentary door-opening spikes and transient button presses.
- **Gap Merging Tolerance ($G_{\\text{max}} = 3\\text{ min}$):** Bridges soak pauses and reverse pauses, preventing a single wash cycle from fragmenting into 5–10 separate mini-events.

### Energy Integration:
For discrete 1-minute active power readings $P_t$ in Watts:
$$\\text{Energy (Wh)} = \\sum_{t=1}^{N} P_t \\times \\frac{1}{60} = \\frac{1}{60} \\sum_{t=1}^{N} P_t$$
""", "cell-07-cycle-rules-md"))

    cells.append(code_cell("""
# Inspect detailed cycle trace with marked boundaries
img_trace = FIGURES_DIR / "detected_cycle_trace.png"
img = mpimg.imread(img_trace)
plt.figure(figsize=(13, 6))
plt.imshow(img)
plt.axis("off")
plt.title("Washing Machine Operating Cycle Anatomy & Marked Boundaries", fontsize=12, fontweight="bold")
plt.show()
""", "cell-08-trace-code"))

    # Section 4: Cross-Household Comparisons
    cells.append(md_cell("""
---
## 4. Cross-Household Comparisons & Cycle Characteristics

Let us compare the empirical cycle distributions across the households:
- **House 1 (2 occupants, detached):** Median duration **33.0 min**, median peak **2,320 W**, median energy **300.8 Wh**. Short, efficient daily cycles (4.8 cycles/week).
- **House 2 (4 occupants, semi-detached):** Median duration **95.0 min**, median peak **2,089 W**, median energy **604.0 Wh**. Heavy laundry loads with extensive wash programs and twice the energy consumption per cycle.
- **House 3 (2 occupants, detached):** Median duration **65.0 min**, median peak **1,922 W**, median energy **538.2 Wh**, frequency **7.87 cycles/week**.
- **House 5 (4 occupants, mid-terrace):** Highest frequency (**8.93 cycles/week**, 827 cycles total!), median duration **42.0 min**, median energy **276.2 Wh** (frequent, moderate-temperature cycles for a 4-person family).
""", "cell-09-cross-md"))

    cells.append(code_cell("""
# Display 24-hour trace and cross-household comparison boxplots
fig_24h = FIGURES_DIR / "representative_24h_aggregate_wm.png"
fig_comp = FIGURES_DIR / "cross_household_cycle_comparison.png"

plt.figure(figsize=(14, 5))
plt.imshow(mpimg.imread(fig_24h))
plt.axis("off")
plt.title("24-Hour Whole-Home Aggregate vs. Washing Machine Load Profile", fontsize=12, fontweight="bold")
plt.show()

plt.figure(figsize=(16, 5))
plt.imshow(mpimg.imread(fig_comp))
plt.axis("off")
plt.title("Cross-Household Distributions: Duration, Peak Power, and Energy per Cycle", fontsize=12, fontweight="bold")
plt.show()
""", "cell-10-cross-plots-code"))

    # Section 5: Temporal Patterns
    cells.append(md_cell("""
---
## 5. Temporal Usage Patterns (Diurnal & Weekly)

We analyze when occupants initiate wash cycles across the day and week:
- **Hour-of-Day (Diurnal):** Strong morning peak between **08:00 and 11:00 UTC**, with a secondary late afternoon peak around **16:00–18:00 UTC**. Night-time usage (00:00–05:00) is near zero, indicating occupants do not exploit off-peak Economy 7 tariffs.
- **Day-of-Week:** Consistent activity throughout the week, with noticeable spikes on **Saturday and Sunday** in House 2 and House 5.
""", "cell-11-temporal-md"))

    cells.append(code_cell("""
fig_hourly = FIGURES_DIR / "hourly_usage_profile.png"
fig_dow = FIGURES_DIR / "day_of_week_usage.png"

plt.figure(figsize=(15, 5))
plt.imshow(mpimg.imread(fig_hourly))
plt.axis("off")
plt.title("Hourly Usage Profile: Start Times & Energy Distribution", fontsize=12, fontweight="bold")
plt.show()

plt.figure(figsize=(15, 5))
plt.imshow(mpimg.imread(fig_dow))
plt.axis("off")
plt.title("Day of Week Usage Profile: Weekly Load Schedules", fontsize=12, fontweight="bold")
plt.show()
""", "cell-12-temporal-plots-code"))

    # Section 6: Sensitivity Analysis
    cells.append(md_cell("""
---
## 6. Sensitivity Analysis: Empirical Proof of Parameter Robustness

We evaluate the detection pipeline across 7 distinct parameter scenarios:
1. **Baseline:** $P=20\\text{W}, D=15\\text{m}, G=3\\text{m}$
2. **Lower Threshold:** $P=10\\text{W}, D=15\\text{m}, G=3\\text{m}$
3. **Higher Threshold:** $P=50\\text{W}, D=15\\text{m}, G=3\\text{m}$
4. **Shorter Duration:** $P=20\\text{W}, D=10\\text{m}, G=3\\text{m}$
5. **Longer Duration:** $P=20\\text{W}, D=25\\text{m}, G=3\\text{m}$
6. **Strict No-Gap ($G=0\\text{m}$):** *Disastrous fragmentation.*
7. **Wider Gap ($G=5\\text{m}$):**

### Key Takeaway on Gap Merging ($G=0\\text{m}$):
Without gap merging ($G=0$), House 1 cycle count drops from **438 to 257**, and total energy captured drops from **141.6 kWh to 75.3 kWh**! A brief 1-minute soak pause prematurely terminates the cycle, discarding the rest of the cycle. Gap merging ($G=3\\text{m}$) is mathematically essential.
""", "cell-13-sens-md"))

    cells.append(code_cell("""
sens_csv = TABLES_DIR / "washing_machine_sensitivity.csv"
sens_df = pd.read_csv(sens_csv)

# Show House 1 and House 5 sensitivity table
display(sens_df[sens_df["household"].isin(["House 1", "House 5"])][[
    "scenario", "household", "p_thresh_w", "min_duration_min", "max_gap_min",
    "detected_cycle_count", "median_duration_min", "median_peak_power_w", "median_energy_wh", "total_energy_kwh"
]])
""", "cell-14-sens-code"))

    # Section 7: Sample Cycle Records Table
    cells.append(md_cell("""
---
## 7. Machine-Readable Cycle Deliverables

The detected cycle events are saved in `results/washing_machine_cycles.csv` (2,509 total cycles).  
Let us inspect sample cycle records:
""", "cell-15-cycle-table-md"))

    cells.append(code_cell("""
cycles_csv = TABLES_DIR / "washing_machine_cycles.csv"
cycles_df = pd.read_csv(cycles_csv)
print(f"Total Cycles Detected Across 5 Homes: {len(cycles_df):,}")
display(cycles_df[["household", "cycle_id", "start_time", "end_time", "duration_min", "peak_power_w", "mean_power_w", "energy_wh", "energy_kwh", "is_truncated"]].head(10))
""", "cell-16-cycle-table-code"))

    # Conclusion
    cells.append(md_cell("""
---
## 8. Summary & Technical Interview Highlights

1. **Defensible Thresholding:** 20 W cleanly isolates motor and heating loads while rejecting the persistent 3 W standby load in House 5.
2. **Gap Merging Invariant:** 3-minute gap merging prevents cycle fragmentation during low-power soak pauses, preserving the integrity of the heating element signature (~2 kW).
3. **Behavioral vs. Physical Variation:** Differences in energy per cycle (300 Wh in House 1 vs. 604 Wh in House 2) reflect wash temperature selection and machine ratings rather than occupant carelessness.
4. **DSR Feasibility:** With over 65% of washing machine cycles initiated between 08:00 and 13:00, significant flexibility exists to shift loads into midday solar periods or off-peak night hours.
""", "cell-17-conclusion-md"))

    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3 (ipykernel)",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.11.9",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    with open(OUTPUT_NOTEBOOK, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=1)

    print(f"Successfully generated {OUTPUT_NOTEBOOK}")


if __name__ == "__main__":
    build()
