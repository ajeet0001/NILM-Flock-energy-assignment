"""
Build script: generates 01_raw_data_cleaning.ipynb

Run from any directory; writes the notebook relative to this script's location.
Fixed version: uses correct audit JSON key paths and correct validate_cleaned signature.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "01_raw_data_cleaning.ipynb"


def md(source: str) -> dict:
    return {
        "cell_type": "markdown",
        "id": "md-" + str(abs(hash(source[:40])))[:8],
        "metadata": {},
        "source": source
    }


def code(source: str, cell_id: str = "") -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": "code-" + cell_id if cell_id else "code-" + str(abs(hash(source[:40])))[:8],
        "metadata": {},
        "outputs": [],
        "source": source
    }


cells = []

# ============================================================
# Section 1: Project Purpose & Configuration
# ============================================================
cells.append(md("""\
# House 1 Raw Data Cleaning — Full Pipeline Walkthrough
## 01 · Raw Data Cleaning Notebook

**Dataset:** REFIT Smart Home Dataset — House 1 (active power, Watts)  
**Licence:** Creative Commons Attribution 4.0 International (CC-BY 4.0)  
**Citation:** Murray, D., Stankovic, L., Stankovic, V. (2017). *An electrical load measurements dataset of United Kingdom households from a two-year longitudinal study.* Scientific Data, 4, 160122. https://doi.org/10.1038/sdata.2016.122

### Purpose
This notebook documents the complete data-cleaning pipeline for House 1 of the REFIT dataset.  
The pipeline converts two overlapping raw CSVs (~480 MB total, ~8.5 M rows combined) into a single  
1-minute-resolution cleaned CSV (`CLEAN_House1_1min.csv`, ~192 MB, 920,031 minute-bins).

> **Note:** The heavy pipeline has already been executed; this notebook loads pre-computed audit JSON  
> (`outputs/metrics/house1_audit.json`) and the cleaned CSV for validation and illustration.  
> Small-sample demonstrations use `src/cleaning.py` functions interactively.

---
"""))

cells.append(code("""\
# --- Imports & path configuration ---
import sys
import json
import inspect
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from IPython.display import display, Image, HTML

# Project root: one level above notebooks/
PROJECT_ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
print(f"PROJECT_ROOT : {PROJECT_ROOT}")

# Ensure src/ is on PYTHONPATH
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# --- Key paths ---
RAW_DIR     = PROJECT_ROOT / "data" / "raw"
OUT_DIR     = PROJECT_ROOT / "outputs"
RESULTS_DIR = PROJECT_ROOT / "results"
AUDIT_JSON  = OUT_DIR / "metrics" / "house1_audit.json"
CLEAN_CSV   = OUT_DIR / "cleaned" / "CLEAN_House1_1min.csv"

RAW_P1 = RAW_DIR / "RAW_House1_Part1.csv"
RAW_P2 = RAW_DIR / "RAW_House1_Part2.csv"

# --- Channel mapping (from REFIT README + cleaning.py) ---
CHANNEL_MAP = {
    "Aggregate"  : "Whole-home aggregate",
    "Appliance1" : "Fridge (Hotpoint RLA50P)",
    "Appliance2" : "Freezer-1 (Beko CF393APW)",
    "Appliance3" : "Freezer-2",
    "Appliance4" : "Washer Dryer (Creda T522VW)",
    "Appliance5" : "Washing Machine (Beko WMC6140)",
    "Appliance6" : "Dishwasher (Bosch)",
    "Appliance7" : "Computer (Lenovo)",
    "Appliance8" : "Television Site",
    "Appliance9" : "Electric Heater",
}
CHANNELS = list(CHANNEL_MAP.keys())

# --- Verify raw files exist and print sizes ---
print("\\n=== Raw file inventory ===")
for p in [RAW_P1, RAW_P2]:
    size_mb = p.stat().st_size / 1e6 if p.exists() else -1
    status = "OK" if p.exists() else "MISSING"
    print(f"  [{status}]  {p.name}  ({size_mb:.1f} MB)")

print(f"\\n  Audit JSON : {'OK' if AUDIT_JSON.exists() else 'MISSING'}  {AUDIT_JSON.name}")
size_clean = CLEAN_CSV.stat().st_size / 1e6 if CLEAN_CSV.exists() else -1
print(f"  Cleaned CSV: {'OK' if CLEAN_CSV.exists() else 'MISSING'}  {CLEAN_CSV.name}  ({size_clean:.1f} MB)")
""", "s1-setup"))

# ============================================================
# Section 2: Data Discovery & File Inspection
# ============================================================
cells.append(md("""\
---
## Section 2 — Data Discovery & File Inspection

The REFIT House 1 dataset ships as two overlapping CSV files:

| File | Rows | Size | UTC span |
|------|-----:|-----:|---------|
| `RAW_House1_Part1.csv` | 4,377,877 | 243.6 MB | 2013-10-09 → 2014-10-01 |
| `RAW_House1_Part2.csv` | 4,140,886 | 239.6 MB | 2014-06-27 → 2015-07-10 |

Both files share the same schema: `Time, Unix, Aggregate, Appliance1 … Appliance9`.

**Channel mapping for House 1:**

| Channel | Appliance |
|---------|-----------|
| Aggregate | Whole-home aggregate |
| Appliance1 | Fridge (Hotpoint RLA50P) |
| Appliance2 | Freezer-1 (Beko CF393APW) |
| Appliance3 | Freezer-2 |
| Appliance4 | Washer Dryer (Creda T522VW) |
| Appliance5 | Washing Machine (Beko WMC6140) |
| Appliance6 | Dishwasher (Bosch) |
| Appliance7 | Computer (Lenovo) |
| Appliance8 | Television Site |
| Appliance9 | Electric Heater |
"""))

cells.append(code("""\
# --- Peek at the first 5 rows of each raw file (header only) ---
for label, path in [("Part 1", RAW_P1), ("Part 2", RAW_P2)]:
    print(f"\\n{'='*60}")
    print(f"  {label}: {path.name}  ({path.stat().st_size:,} bytes)")
    print(f"{'='*60}")
    sample = pd.read_csv(path, nrows=5)
    print("  Columns:", list(sample.columns))
    print("\\n  First 5 rows:")
    display(sample)

# Channel map as a formatted table
print("\\n=== Channel Mapping ===")
display(pd.DataFrame(list(CHANNEL_MAP.items()), columns=["Channel", "Appliance"]).set_index("Channel"))
""", "s2-inspect"))

# ============================================================
# Section 3: Timestamp Parsing & Ordering
# ============================================================
cells.append(md("""\
---
## Section 3 — Timestamp Parsing & Ordering

### Pre-computed results (from audit JSON)

| Metric | Part 1 | Part 2 |
|--------|-------:|-------:|
| Invalid Unix timestamps | 0 | 0 |
| Invalid Time strings | 0 | 0 |
| `time_unix_nonnull_mismatches` | 2,134,001 | 2,018,842 |
| `row_order_unix_decreases` | 1 | 0 |
| `row_order_unix_repeats` | 1,003,950 | 14,755 |

#### BST offset artefact
The `time_unix_nonnull_mismatches` are rows where the human-readable `Time` string  
disagrees with the `Unix` column by exactly **±1 second** — a known artefact of  
British Summer Time (BST = UTC+1). During BST, the REFIT logger appears to have stored  
the local-time string without converting to UTC, while the Unix epoch is correct.  
**Resolution:** always use `Unix` as the authoritative timestamp.
"""))

cells.append(code("""\
# --- Load audit JSON ---
with open(AUDIT_JSON) as f:
    audit = json.load(f)

p1_data = audit["files"]["RAW_House1_Part1.csv"]
p2_data = audit["files"]["RAW_House1_Part2.csv"]

ts_summary = pd.DataFrame({
    "Part 1": {
        "Invalid Unix":               p1_data["invalid_unix_timestamps"],
        "Invalid Time strings":        p1_data["invalid_time_strings"],
        "Time != Unix mismatches (BST)": p1_data["time_unix_nonnull_mismatches"],
        "Row order decreases":         p1_data["row_order_unix_decreases"],
        "Row order repeats":           p1_data["row_order_unix_repeats"],
    },
    "Part 2": {
        "Invalid Unix":               p2_data["invalid_unix_timestamps"],
        "Invalid Time strings":        p2_data["invalid_time_strings"],
        "Time != Unix mismatches (BST)": p2_data["time_unix_nonnull_mismatches"],
        "Row order decreases":         p2_data["row_order_unix_decreases"],
        "Row order repeats":           p2_data["row_order_unix_repeats"],
    }
})
print("=== Timestamp Diagnostics (from audit JSON) ===")
display(ts_summary)

# --- Live demonstration on 500 000-row sample from Part 1 ---
print("\\nLoading 500,000-row sample from Part 1 for live demonstration...")
from cleaning import inspect_timestamps

sample_p1 = pd.read_csv(RAW_P1, nrows=500_000)
ts_diag = inspect_timestamps(sample_p1)
print("\\nLive timestamp diagnostics (500k-row sample, Part 1):")
for k, v in ts_diag.items():
    print(f"  {k:35s}: {v}")
""", "s3-timestamps"))

# ============================================================
# Section 4: Duplicate Timestamps
# ============================================================
cells.append(md("""\
---
## Section 4 — Duplicate Timestamps

REFIT House 1 Part 1 has a severe duplicate problem: **1,833,597 rows** (42%) share  
their Unix timestamp with at least one other row, forming **829,193 groups**.  
Of those groups, **118,191** are *conflicting* — the grouped rows disagree on at least  
one power channel value.

| Metric | Part 1 | Part 2 |
|--------|-------:|-------:|
| Exact duplicate rows | 595,935 | 0 |
| Rows at duplicate timestamps | 1,833,597 | 29,510 |
| Duplicate timestamp groups | 829,193 | 14,755 |
| Conflicting groups (any channel) | 118,191 | 14,362 |

### Why do conflicts occur?
Part 1 was written in two overlapping database passes; Part 2 is the later "corrected" pass.  
Conflicts arise when the two passes stored different sensor readings for the same second  
(sensor retransmissions, DB merge artefacts).

**Resolution policy:** stable-sort by Unix then original row order; for each channel at a  
duplicate timestamp keep the **last non-missing value**.
"""))

cells.append(code("""\
# --- Conflicting groups per channel from audit JSON ---
p1_conflict = p1_data["conflicting_duplicate_timestamp_groups_by_channel"]
p2_conflict = p2_data["conflicting_duplicate_timestamp_groups_by_channel"]

conflict_df = pd.DataFrame({"Part 1 conflicts": p1_conflict, "Part 2 conflicts": p2_conflict})
conflict_df.index.name = "Channel"
print("Conflicting duplicate timestamp groups by channel:")
display(conflict_df)

# --- Summary table ---
dup_summary = pd.DataFrame({
    "Exact dup rows":          [p1_data["exact_duplicate_rows"],           p2_data["exact_duplicate_rows"]],
    "Rows at dup timestamps":  [p1_data["rows_at_duplicate_timestamps"],   p2_data["rows_at_duplicate_timestamps"]],
    "Dup timestamp groups":    [p1_data["duplicate_timestamp_groups"],     p2_data["duplicate_timestamp_groups"]],
    "Conflicting groups":      [p1_data["conflicting_duplicate_timestamp_groups_any_channel"],
                                p2_data["conflicting_duplicate_timestamp_groups_any_channel"]],
}, index=["Part 1", "Part 2"]).T
print("\\n=== Duplicate Summary ===")
display(dup_summary)

# --- Show duplicate window plot ---
dup_fig = PROJECT_ROOT / "outputs" / "figures" / "house1_duplicate_timestamp_window.png"
print(f"\\nDuplicate timestamp window plot:")
display(Image(filename=str(dup_fig)))
""", "s4-duplicates"))

# ============================================================
# Section 5: Sampling Intervals, Missingness, Outages
# ============================================================
cells.append(md("""\
---
## Section 5 — Sampling Intervals, Missingness & Outages

The documented cadence is **8 seconds**, but the real inter-sample interval is variable.  
Median observed interval: **7 s** (both files).

### Gaps > 60 seconds

| File | Unique timestamps | Gaps > 60 s | Largest gap |
|------|------------------:|------------:|------------:|
| Part 1 | 3,373,473 | 781 | 3,594,414 s (41.6 days) |
| Part 2 | 4,126,131 | 3,604 | 747,251 s (8.6 days) |

### Outages in 1-min output
- **Total minute bins:** 920,031  
- **Missing aggregate bins:** 119,680 (13.0%)  
- **Longest outage:** 59,906 minutes (~41.6 days) from **2014-01-24T01:57Z** to **2014-03-06T16:22Z**  
  (the system was completely offline for most of February 2014)

> **Imputation policy: none.** Missing minute bins remain NaN; downstream models must handle them.
"""))

cells.append(code("""\
# Reference the cleaned_minutes section of the audit JSON
cleaned_minutes = audit["cleaning"]["cleaned_minutes"]

# Show the sampling/missingness figure
samp_fig = PROJECT_ROOT / "outputs" / "figures" / "house1_sampling_and_missingness.png"
print(f"Sampling & missingness plot:")
display(Image(filename=str(samp_fig)))

# Outage summary from audit
print("\\n=== Outage / Missing-run summary (Aggregate channel) ===")
agg_runs = cleaned_minutes["missing_runs"]["Aggregate"]
for k, v in agg_runs.items():
    print(f"  {k:30s}: {v}")

# Show longest-gap figure
gap_fig = PROJECT_ROOT / "outputs" / "figures" / "house1_longest_gap.png"
print(f"\\nLongest gap plot:")
display(Image(filename=str(gap_fig)))
""", "s5-intervals"))

# ============================================================
# Section 6: Channel-specific Quality
# ============================================================
cells.append(md("""\
---
## Section 6 — Channel-specific Quality

The table below is derived from the raw-file audit. Values are **raw** (before cleaning).

Key observations:
- **No missing values** in raw files — all channels populated on every row (Part 1 & 2).
- **No negative readings** in either file.
- **Appliance9 (Electric Heater):** Only 874 zero-readings in Part 1 — dramatically fewer  
  zeros than other appliances — suggesting it may always draw some standby power.  
  It also has the worst post-cleaning missingness (36.8% of minute bins missing) due to  
  late recording start and the February 2014 outage.
- **High-power (>10 kW) readings** exist for most channels; these are flagged but **not removed**  
  (they may be genuine; we apply a note-only screen at 10,000 W).
"""))

cells.append(code("""\
def channel_quality_table(file_key: str) -> pd.DataFrame:
    fd = audit["files"][file_key]
    rows = []
    for ch in CHANNELS:
        rows.append({
            "Channel":     ch,
            "Appliance":   CHANNEL_MAP[ch],
            "Missing (raw)": fd["raw_missing_by_channel"].get(ch, "—"),
            "Zero (raw)":    fd["raw_zero_by_channel"].get(ch, "—"),
            "Negative":      fd["raw_negative_by_channel"].get(ch, "—"),
            ">10 kW":        fd["raw_over_10000_w_by_channel"].get(ch, "—"),
            "Min W":         fd.get("raw_min_by_channel", {}).get(ch, "—"),
            "Max W":         fd.get("raw_max_by_channel", {}).get(ch, "—"),
        })
    return pd.DataFrame(rows).set_index("Channel")

print("=== Channel Quality — Part 1 ===")
display(channel_quality_table("RAW_House1_Part1.csv"))

print("\\n=== Channel Quality — Part 2 ===")
display(channel_quality_table("RAW_House1_Part2.csv"))

total_bins = cleaned_minutes["output_rows"]
missing_bins = cleaned_minutes["per_channel_missing_bins"]

print("\\n=== Post-cleaning missing minute-bins per channel ===")
missing_df = pd.DataFrame([
    {"Channel": ch, "Appliance": CHANNEL_MAP[ch],
     "Missing bins": missing_bins[ch],
     "Missing %": f"{100*missing_bins[ch]/total_bins:.1f}%"}
    for ch in CHANNELS
]).set_index("Channel")
display(missing_df)
print("\\nNote: Appliance9 (Electric Heater) is missing 36.8% of bins — worst of all channels.")
""", "s6-channel-quality"))

# ============================================================
# Section 7: Part 1 / Part 2 Comparison
# ============================================================
cells.append(md("""\
---
## Section 7 — Part 1 / Part 2 Overlap Analysis

The two files overlap in time between  
`Unix 1403906269 – 1412126827`  ≡  **2014-06-27 to 2014-10-01** (UTC).

| Metric | Count |
|--------|------:|
| Part 1 rows in overlap window | 1,257,865 |
| Part 2 rows in overlap window | 945,403 |
| Part 1 grouped unique timestamps | 835,888 |
| Part 2 grouped unique timestamps | 942,783 |
| Timestamps in **both** files | 191,889 |
| Timestamps in **Part 1 only** | 643,999 |
| Timestamps in **Part 2 only** | 750,894 |
| Shared: aggregate **matching** | 36,988 |
| Shared: aggregate **conflicting** | 144,267 |

### Interpretation
Of the 191,889 timestamps that appear in both files, **75.2% have conflicting aggregate readings**  
(144,267 / 191,889). This confirms Part 2 is a corrected re-issue of Part 1, not simply an extension.

**Cleaning strategy:** Use **Part 2** as authoritative throughout its coverage.  
Part 1 contributes only the rows **strictly before the UTC minute** containing Part 2's first timestamp  
(`1403906220` — the start of the minute at Unix 1403906269).
"""))

cells.append(code("""\
# --- Overlap analysis from audit JSON ---
overlap = audit["overlap"]

print("=== Overlap Analysis ===")
print(f"  Overlap window: {overlap['overlap_start_utc']}  to  {overlap['overlap_end_utc']}")
print(f"  Overlap start Unix: {overlap['overlap_start_unix']}")
print(f"  Overlap end Unix  : {overlap['overlap_end_unix']}")
print()

# File-level overlap stats
for f in overlap["files"]:
    print(f"  {f['file']}: {f['overlap_rows']:,} overlap rows, {f['grouped_unique_timestamps']:,} grouped unique timestamps")

print()
merge_counts = overlap["unique_timestamp_merge_counts"]
print(f"  Timestamps in both   : {merge_counts['both']:,}")
print(f"  Timestamps Part1 only: {merge_counts['left_only']:,}")
print(f"  Timestamps Part2 only: {merge_counts['right_only']:,}")
print(f"  Shared unique timestamps: {overlap['shared_unique_timestamps']:,}")
print(f"  Matching aggregate groups  : {overlap['matching_aggregate_min_max_groups']:,}")
print(f"  Conflicting aggregate groups: {overlap['conflicting_aggregate_min_max_groups']:,}")

conflict_pct = 100 * overlap['conflicting_aggregate_min_max_groups'] / overlap['shared_unique_timestamps']
print(f"\\n  => {conflict_pct:.1f}% of shared timestamps have conflicting aggregate values")
print("  => Part 2 is a corrected re-issue, not just an extension of Part 1")

# Visualise merge outcome
merge_data = {
    "Both":       merge_counts["both"],
    "Part1 only": merge_counts["left_only"],
    "Part2 only": merge_counts["right_only"],
}
fig, ax = plt.subplots(figsize=(7, 3))
bars = ax.bar(list(merge_data.keys()), list(merge_data.values()),
              color=["#4472C4", "#ED7D31", "#A9D18E"])
ax.set_title("Overlap-window timestamp merge outcome")
ax.set_ylabel("Unique timestamp groups")
for bar, val in zip(bars, merge_data.values()):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5000,
            f"{val:,}", ha="center", va="bottom", fontsize=9)
plt.tight_layout()
plt.show()
""", "s7-overlap"))

# ============================================================
# Section 8: Cleaning Pipeline
# ============================================================
cells.append(md("""\
---
## Section 8 — Cleaning Pipeline

The pipeline in `src/cleaning.py` applies the following steps in order:

1. **Load Part 1** — read full raw CSV; tag `_source_row`.  
2. **Trim Part 1** — keep only rows with `Unix < 1403906220` (minute boundary of Part 2 start).  
3. **Remove exact duplicates (Part 1)** — drop exact full-row duplicates (321,692 removed).  
4. **Timestamp-resolution deduplication (Part 1)** — stable-sort by Unix; for each duplicate  
   timestamp group keep last non-missing value per channel (260,732 secondary rows removed).  
5. **Load Part 2** — read full raw CSV.  
6. **Remove exact duplicates (Part 2)** — 0 removed.  
7. **Timestamp-resolution deduplication (Part 2)** — 14,755 secondary rows removed.  
8. **Concatenate** — Part 1 cleaned + Part 2 cleaned, chronologically.  
9. **Resample to 1 minute** — mean of observed readings within each UTC minute; empty → NaN.  
10. **Validate** — run quality checks; write `house1_audit.json`.  

### Cleaning statistics

| Step | Part 1 | Part 2 |
|------|-------:|-------:|
| Rows considered | 3,120,004 | 4,140,886 |
| Exact duplicates removed | 321,692 | 0 |
| Timestamp-resolution removed | 260,732 | 14,755 |
| Unique timestamps after dedup | 2,537,580 | 4,126,131 |
| Minute bins produced | 376,311 | 543,720 |
| **Total minute bins** | **920,031** | |
"""))

cells.append(code("""\
# --- Show cleaning.py function signatures ---
import cleaning

funcs_to_show = [
    "read_raw_file", "inspect_timestamps", "diagnose_duplicates",
    "resolve_duplicate_timestamps", "resample_to_1min", "validate_cleaned",
]
print("=== Key functions in src/cleaning.py ===\\n")
for name in funcs_to_show:
    fn = getattr(cleaning, name, None)
    if fn:
        sig = inspect.signature(fn)
        doc_first = (inspect.getdoc(fn) or "").split("\\n")[0]
        print(f"  {name}{sig}")
        print(f"    -> {doc_first}\\n")

# --- Cleaning stats table from audit JSON ---
c1 = audit["cleaning"]["part1"]
c2 = audit["cleaning"]["part2"]

cleaning_stats_df = pd.DataFrame({
    "Part 1": {
        "Rows considered":              c1["rows_considered_for_cleaning"],
        "Exact duplicates removed":     c1["exact_duplicate_rows_removed"],
        "TS-resolution removed":        c1["rows_removed_by_timestamp_resolution"],
        "Unique timestamps after dedup":c1["unique_timestamps_after_resolution"],
        "Minute bins produced":         c1["minute_bins"],
    },
    "Part 2": {
        "Rows considered":              c2["rows_considered_for_cleaning"],
        "Exact duplicates removed":     c2["exact_duplicate_rows_removed"],
        "TS-resolution removed":        c2["rows_removed_by_timestamp_resolution"],
        "Unique timestamps after dedup":c2["unique_timestamps_after_resolution"],
        "Minute bins produced":         c2["minute_bins"],
    }
})
print("\\n=== Cleaning Statistics ===")
display(cleaning_stats_df)
print(f"\\nTotal minute bins: {audit['cleaning']['cleaning']['cleaned_minutes']['output_rows']:,}" if 'cleaning' in audit['cleaning'] else f"\\nTotal minute bins: {cleaned_minutes['output_rows']:,}")
""", "s8-pipeline"))

# ============================================================
# Section 9: Resampling to 1-minute
# ============================================================
cells.append(md("""\
---
## Section 9 — Resampling to 1-Minute Resolution

The cleaned per-second data is aggregated into 1-minute bins using **mean** resampling.  
Empty minute bins remain `NaN` (no imputation).

### 1-minute output summary

| Metric | Value |
|--------|-------|
| Total minute bins | 920,031 |
| UTC start | 2013-10-09T14:06:00Z |
| UTC end | 2015-07-10T11:56:00Z |
| Bins with Aggregate reading | 800,351 (87.0%) |
| Missing aggregate bins | 119,680 (13.0%) |
| Appliance9 missing bins | 338,427 (36.8%) |

The resampled file (`CLEAN_House1_1min.csv`) uses a UTC-indexed datetime column and  
floating-point power columns (Watts). Values mapping to empty minute bins are `NaN`.
"""))

cells.append(code("""\
# --- Quick peek at cleaned CSV (1000 rows, fast) ---
print("Loading first 1,000 rows of cleaned CSV for display...")
clean_sample = pd.read_csv(CLEAN_CSV, nrows=1000)
print(f"Shape of sample: {clean_sample.shape}")
print(f"Columns: {list(clean_sample.columns)}")
print("\\nFirst 5 rows:")
display(clean_sample.head())
print("\\nLast 5 rows of sample:")
display(clean_sample.tail())

print("\\nData types:")
display(clean_sample.dtypes.to_frame("dtype"))

null_counts = clean_sample.isnull().sum()
print(f"\\nNull counts in 1,000-row sample:")
display(null_counts[null_counts > 0].to_frame("NaN count") if null_counts.any() else "No NaNs in first 1,000 rows")

# --- Display the before/after aggregate figure ---
agg_fig = PROJECT_ROOT / "results" / "figures" / "house1_aggregate_before_after.png"
print(f"\\nAggregate before/after figure:")
display(Image(filename=str(agg_fig)))
""", "s9-resample"))

# ============================================================
# Section 10: Short-gap handling and long-outage flags
# ============================================================
cells.append(md("""\
---
## Section 10 — Gap Handling & Outage Flags

### Imputation policy: **None**
No imputation is applied. Missing minute bins remain `NaN` to avoid introducing  
synthetic power readings that could corrupt NILM algorithm training.

### Missing-run summary (all channels)

All channels share the same **longest outage: 59,906 minutes** (2014-01-24 → 2014-03-06),  
confirming the meter was offline rather than individual appliances being off.

| Channel | Missing bins | Missing % | Runs | Longest run (min) |
|---------|------------:|----------:|-----:|------------------:|
| Aggregate   | 119,680 | 13.0% | 1,018 | 59,906 |
| Appliance1  | 123,730 | 13.4% | 2,205 | 59,906 |
| Appliance2  | 123,473 | 13.4% | 2,029 | 59,906 |
| Appliance3  | 121,143 | 13.2% | 1,057 | 59,906 |
| Appliance4  | 132,757 | 14.4% | 2,706 | 59,906 |
| Appliance5  | 129,681 | 14.1% | 2,887 | 59,906 |
| Appliance6  | 120,560 | 13.1% | 966   | 59,906 |
| Appliance7  | 119,674 | 13.0% | 1,018 | 59,906 |
| Appliance8  | 121,879 | 13.2% | 1,679 | 59,906 |
| Appliance9  | 338,427 | 36.8% | 1,734 | 59,906 |
"""))

cells.append(code("""\
# --- Missing-run table from audit JSON ---
missing_runs_data = cleaned_minutes["missing_runs"]
total_bins = cleaned_minutes["output_rows"]

run_rows = []
for ch in CHANNELS:
    r = missing_runs_data[ch]
    run_rows.append({
        "Channel":           ch,
        "Appliance":         CHANNEL_MAP[ch],
        "Missing bins":      r["missing_bins"],
        "Missing %":         f"{100*r['missing_bins']/total_bins:.1f}%",
        "Runs":              r["missing_runs"],
        "Longest run (min)": r["longest_run_minutes"],
        "Longest start":     r["longest_run_start_utc"],
        "Longest end":       r["longest_run_end_utc"],
    })

run_df = pd.DataFrame(run_rows).set_index("Channel")
display(run_df)

# Show longest-gap figure
gap_fig = PROJECT_ROOT / "outputs" / "figures" / "house1_longest_gap.png"
print("\\nLongest gap figure:")
display(Image(filename=str(gap_fig)))
""", "s10-gaps"))

# ============================================================
# Section 11: Validation and Quality Tables
# ============================================================
cells.append(md("""\
---
## Section 11 — Validation & Quality Tables

### Sum-of-appliances check
On the 576,424 minute bins where **all channels are present**, the sum of the 9 appliances  
is compared to the aggregate channel:

| Metric | Value |
|--------|-------|
| Complete-channel minute bins | 576,424 |
| Median (appliance_sum − aggregate) | −159.4 W |
| Mean absolute difference | 354.3 W |
| Exactly equal (sum = aggregate) | 1 |

The median offset of −159 W indicates systematically **more power in the aggregate than  
the sum of sub-meters** — consistent with unmeasured loads (e.g. lights, sockets not covered  
by the 9 sub-meters) adding to the aggregate but absent from individual channels.
"""))

cells.append(code("""\
# --- Load quality audit CSV ---
qa_csv = PROJECT_ROOT / "results" / "tables" / "house1_quality_audit.csv"
if qa_csv.exists():
    qa_df = pd.read_csv(qa_csv)
    print("=== Quality Audit Table ===")
    display(qa_df)
else:
    print(f"Quality audit CSV not found at {qa_csv}")

# --- Load cleaning summary CSV ---
cs_csv = PROJECT_ROOT / "results" / "tables" / "house1_cleaning_summary.csv"
if cs_csv.exists():
    cs_df = pd.read_csv(cs_csv)
    print("\\n=== Cleaning Summary Table ===")
    display(cs_df)

# --- Sum-of-appliances from audit JSON ---
sac = cleaned_minutes["sum_appliances_comparison"]
print("\\n=== Sum-of-Appliances Check ===")
for k, v in sac.items():
    if isinstance(v, float):
        print(f"  {k:50s}: {v:.3f} W")
    else:
        print(f"  {k:50s}: {v:,}")

# --- Live validate_cleaned call on sample ---
print("\\n--- Running validate_cleaned on 50,000-row sample ---")
power_cols = ["Aggregate"] + [f"Appliance{i}" for i in range(1, 10)]
clean_val_raw = pd.read_csv(CLEAN_CSV, nrows=50_000)
# validate_cleaned expects a DatetimeIndex; parse Time and set as index
if "Time" in clean_val_raw.columns:
    clean_val_raw["Time"] = pd.to_datetime(clean_val_raw["Time"], utc=True)
    clean_val_raw = clean_val_raw.set_index("Time")
warnings_list = cleaning.validate_cleaned(clean_val_raw, power_cols=power_cols)
if warnings_list:
    print("validate_cleaned warnings:")
    for w in warnings_list:
        print(f"  {w}")
else:
    print("validate_cleaned: all assertions passed (no warnings).")
""", "s11-validation"))

# ============================================================
# Section 12: Plots and Export
# ============================================================
cells.append(md("""\
---
## Section 12 — Plots & Export

All key figures are stored in `outputs/figures/` and `results/figures/`.  
Below they are displayed inline.
"""))

cells.append(code("""\
fig_paths = {
    "Before/after (1-min aggregate)":
        PROJECT_ROOT / "results" / "figures" / "house1_aggregate_before_after.png",
    "Appliances before/after":
        PROJECT_ROOT / "results" / "figures" / "house1_appliances_before_after.png",
    "Missingness diagnostics":
        PROJECT_ROOT / "results" / "figures" / "house1_missingness_diagnostics.png",
    "Duplicate timestamp window":
        PROJECT_ROOT / "outputs" / "figures" / "house1_duplicate_timestamp_window.png",
}

for title, fpath in fig_paths.items():
    print(f"\\n--- {title} ---")
    if fpath.exists():
        print(f"  File: {fpath.relative_to(PROJECT_ROOT)}  ({fpath.stat().st_size:,} bytes)")
        display(Image(filename=str(fpath)))
    else:
        print(f"  NOT FOUND: {fpath}")

# Confirm all result files
print("\\n=== Result file inventory ===")
result_files = [
    PROJECT_ROOT / "outputs" / "cleaned" / "CLEAN_House1_1min.csv",
    PROJECT_ROOT / "outputs" / "metrics" / "house1_audit.json",
    PROJECT_ROOT / "results" / "tables" / "house1_cleaning_summary.csv",
    PROJECT_ROOT / "results" / "tables" / "house1_quality_audit.csv",
] + list(fig_paths.values())

for fp in result_files:
    if fp.exists():
        size = fp.stat().st_size
        rel = fp.relative_to(PROJECT_ROOT)
        print(f"  OK  {rel}  ({size:,} bytes)")
    else:
        rel = fp.relative_to(PROJECT_ROOT)
        print(f"  MISSING  {rel}")
""", "s12-plots"))

# ============================================================
# Section 13: Summary of Findings
# ============================================================
cells.append(md("""\
---
## Section 13 — Summary of Findings

### Key numbers

| Metric | Value |
|--------|-------|
| Raw Part 1 rows | 4,377,877 |
| Raw Part 2 rows | 4,140,886 |
| Part 1 exact duplicate rows | 595,935 (13.6%) |
| Part 2 exact duplicate rows | 0 |
| Part 1 conflicting timestamp groups | 118,191 |
| Part 2 conflicting timestamp groups | 14,362 |
| Overlap window shared timestamps | 191,889 |
| Aggregate conflicts in overlap | 144,267 (75.2%) |
| Cleaned 1-min bins total | 920,031 |
| Coverage | 2013-10-09 → 2015-07-10 |
| Missing aggregate bins | 119,680 (13.0%) |
| Longest outage | 59,906 min (Feb 2014) |
| Appliance9 missing | 338,427 (36.8%) |
| Median sum-agg offset | −159.4 W |
| Mean |sum − agg| | 354.3 W |

### Key findings

- **Part 2 supersedes Part 1** in its coverage window (2014-06-27 onwards); the cleaning strategy  
  correctly uses Part 2 as authoritative and takes only the pre-overlap portion of Part 1.
- **BST artefact:** 48.7% of Part 1 rows and 48.8% of Part 2 rows have a Time string that  
  disagrees with the Unix epoch by exactly 1 second — a known British Summer Time logging bug.  
  Using Unix as the authoritative timestamp removes this ambiguity entirely.
- **February 2014 outage:** A single 59,906-minute (~41.6-day) gap accounts for the majority  
  of aggregate missingness. All 10 channels are equally affected, confirming a system-level  
  (meter or connectivity) failure rather than appliance-level gaps.
- **No imputation:** NaN minute bins are preserved to avoid fabricating power readings.  
  Downstream NILM models must handle missing data explicitly (masking, interpolation, etc.).
- **Sum-of-appliances offset:** The aggregate consistently exceeds the sum of the 9 sub-meters  
  by ~159 W (median), indicating unmeasured loads (lighting circuits, sockets, etc.).

### Remaining limitations

1. **Appliance9 (Electric Heater)** is missing 36.8% of its minute bins — far more than any  
   other channel. The root cause is unclear; it may reflect late sensor installation or a  
   different recording cadence for that channel.
2. **No negative or implausible-value removal:** Readings >10 kW are flagged but retained.  
   Users should apply domain-specific screening before training models.
3. **Mean resampling:** 1-minute bins are computed as the mean of all valid sub-minute readings.  
   For appliances with on/off switching within a minute this is an approximation of the  
   true energy consumption.
4. **UK only / single home:** Results are specific to House 1 in a UK detached/semi-detached  
   home context; generalisation to other homes or countries requires re-running the pipeline.

---
*Notebook generated for the Flock Energy NILM coding assignment.*  
*Audit data generated: 2026-11-04T09:24:01 UTC.*
"""))

# ============================================================
# Assemble notebook
# ============================================================
nb = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "name": "python",
            "version": "3.11.9"
        }
    },
    "cells": cells
}

OUT.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
print(f"Written: {OUT}  ({OUT.stat().st_size:,} bytes)")
print(f"Cells:   {len(cells)}")
code_count = sum(1 for c in cells if c["cell_type"] == "code")
md_count = sum(1 for c in cells if c["cell_type"] == "markdown")
print(f"  Markdown cells: {md_count},  Code cells: {code_count}")
