# REFIT House 1: Requirement 1 data audit and cleaning

## Executive summary

**Measured:** The workspace contains both House 1 raw CSVs and an existing
`data/cleaned/CLEAN_House1.csv`. The raw files are not simple consecutive
partitions: their time ranges overlap from **2014-06-27 21:57:49 UTC** to
**2014-10-01 01:27:07 UTC**, and their overlapping records often disagree.
The notebook's reported timestamp-merge counts are reproduced from the raw
files and are counts of **unique Unix timestamps after grouping**, not raw
rows.

**Documented:** `data/raw/raw_readme.txt` identifies Part 1 as the first
database iteration (unavailable sensors encoded as zero), Part 2 as the second
iteration (unavailable sensors represented as `NaN`), active power in watts,
and an approximate 8-second, asynchronous collection process. It also says
intermediate values were filled between load changes and notes outages.

**Decision:** Use Part 1 only before the UTC minute containing Part 2's first
timestamp (`1403906220`), then use Part 2 for its entire range. Exact rows are removed; for
remaining duplicate Unix seconds, each channel keeps its last nonmissing value
in source-file order. Timestamp-deduplicated observations are averaged within
UTC minute. Justified short gaps ($\le 2$ minutes) are linearly interpolated (e.g., 617 minutes for Aggregate) and flagged via `*_was_imputed = True`. Extended outages ($> 2$ minutes, including the 41-day February 2014 outage of 59,906 minutes) remain missing as `NaN`s (`*_was_missing = True`, `*_was_imputed = False`). This preserves true missingness without manufacturing unphysical power.

**Measured output:** `outputs/cleaned/CLEAN_House1_1min.csv` contains
**920,031** consecutive one-minute bins from **2013-10-09 14:06 UTC** through
**2015-07-10 11:56 UTC**. Aggregate has 119,680 raw missing bins (13.008%); after bounded 2-minute short-gap interpolation, 617 bins are imputed and 119,063 bins remain missing (12.941%). The longest aggregate missing run is **59,906 minutes** (~41.6 days), from
**2014-01-24 01:57 UTC** through **2014-03-06 16:22 UTC**. No negative
measurements were found in either raw file or the output. High readings were
flagged for investigation but retained.

### Evidence labels

- **Measured:** computed from files in this workspace by
  `src/clean_house1.py` or a stated scan of the existing cleaned reference.
- **Documented:** stated in `data/raw/raw_readme.txt`.
- **Assumed:** a pipeline interpretation needed where the source has no
  unambiguous metadata.
- **Unknown:** not available in the supplied files or not resolved by these
  checks.

## A. Data discovery and provenance

### Files used

| File | Measured rows | Measured size | Measured coverage from Unix | Format / raw types |
|---|---:|---:|---|---|
| `data/raw/RAW_House1_Part1.csv` | 4,377,877 | 243,553,211 bytes (232.27 MiB) | 2013-10-09 14:06:17 UTC to 2014-10-01 01:27:07 UTC | CSV; `Time` string; `Unix` int64; power columns int64 |
| `data/raw/RAW_House1_Part2.csv` | 4,140,886 | 239,646,944 bytes (228.55 MiB) | 2014-06-27 21:57:49 UTC to 2015-07-10 11:56:32 UTC | CSV; `Time` string; `Unix` int64; power columns float64 |
| `data/raw/raw_readme.txt` | — | — | — | Supplied plain-text dataset README |

Both CSVs have the actual header
`Time, Unix, Aggregate, Appliance1, ..., Appliance9`. This differs slightly
from the README's generic header wording (`DATETIME, UNIX TIMESTAMP (UCT), ...`).
The provided project files do not include a separate technical specification
other than this README.

### Timestamps and time zone

- **Documented:** the README describes Unix timestamps as UCT, states that
  daylight-saving time has been accounted for in the raw data, and says the
  collection is otherwise raw.
- **Measured:** all 8,518,763 Unix values and all `Time` strings parse. Comparing
  the naive `Time` string with `Unix` interpreted as UTC gives a 0-second
  difference for 2,243,876 Part 1 rows and 2,122,044 Part 2 rows, and a
  1-second difference for 2,134,001 Part 1 rows and 2,018,842 Part 2 rows.
  The local strings contain no UTC offset.
- **Decision:** `Unix` is the canonical instant and is interpreted as UTC.
  `Time` is retained as a validation field only; the pipeline does not apply
  another UK daylight-saving conversion.
- **Unresolved:** the cause of the one-second discrepancies is not stated by
  the supplied documentation. They are reported rather than silently corrected.

### House 1 channel map and units

**Documented and verified against the actual numeric column headers:**

| CSV channel | House 1 appliance (README) | Unit |
|---|---|---|
| `Aggregate` | Whole-home aggregate current-clamp reading | W |
| `Appliance1` | Fridge | W |
| `Appliance2` | Freezer(1) | W |
| `Appliance3` | Freezer(2) | W |
| `Appliance4` | Washer Dryer | W |
| `Appliance5` | Washing Machine | W |
| `Appliance6` | Dishwasher | W |
| `Appliance7` | Computer | W |
| `Appliance8` | Television Site | W |
| `Appliance9` | Electric Heater | W |

The README says these are active-power measurements and nominally sampled at
8-second intervals. It also says sensors are not synchronized and the polling
interval is approximately 6–8 seconds.

### Source and citation

**Documented source links in the supplied README:**

- REFIT project/grant page:
  <http://gtr.rcuk.ac.uk/projects?ref=EP%2FK002368%2F1>
- Government appliance-reference document:
  <https://www.gov.uk/government/uploads/system/uploads/attachment_data/file/274778/9_Domestic_appliances__cooking_and_cooling_equipment.pdf>
- License text:
  <https://creativecommons.org/licenses/by/4.0/legalcode>

The README states that the dataset is licensed under **Creative Commons
Attribution 4.0 International (CC BY 4.0)** and asks users to cite:

> David Murray, Jing Liao, Lina Stankovic, Vladimir Stankovic, Richard
> Hauxwell-Baldwin, Charlie Wilson, Michael Coleman, Tom Kane, and Steven Firth
> (2015). “A data management platform for personalised real-time energy
> feedback.” *Proceedings of the 8th International Conference on Energy
> Efficiency in Domestic Appliances and Lighting*.

**Unknown:** a direct data-download URL or DOI is not included in the supplied
README; none is inferred here.

### Existing cleaned reference

**Measured:** `data/cleaned/CLEAN_House1.csv` is a separate 400,840,083-byte
file with 6,960,008 rows, columns `Time`, `Unix`, the same ten power channels,
and `Issues`. Its `Issues` column contains 6,901,825 zeros and 58,183 ones; the
meaning of those codes is not documented in the supplied files. It spans
2013-10-09 13:06:17 through 2015-07-10 11:56:32 by its `Time` and `Unix`
values.

The first three reference rows have the same power values as the first raw
Part 1 rows, but their times and Unix values are exactly **one hour earlier**
(13:06:17 versus 14:06:17). This is a measured sample-level discrepancy;
the provenance and reason for the shift are **unknown**. The official/reference
file is not modified or used as an input to this pipeline.

## B. Data-quality audit

All figures below are **measured from the complete source files** unless
explicitly labelled documented or assumed. “Conflicting duplicate group”
means at least one of the ten numeric channels has more than one distinct
value at a repeated Unix second; it does not count a difference in the
second-resolution `Time` string alone.

| Check | Part 1 result | Part 2 result | Interpretation / severity | Action |
|---|---|---|---|---|
| Timestamp parse failures | 0 Unix; 0 `Time` | 0 Unix; 0 `Time` | No parsing failures found (low) | Canonicalize from Unix; script raises on missing input files or unexpected columns |
| Source row order | 1 Unix decrease; 1,003,950 adjacent repeats | 0 decreases; 14,755 adjacent repeats | Part 1 is not strictly increasing; repeated seconds are common (medium) | Stable chronological sort before resampling |
| Exact duplicate rows | 595,935 | 0 | Part 1 contains identical repeated records (medium) | Remove exact full-row duplicates |
| Duplicate Unix seconds | 829,193 groups; 1,833,597 rows in repeated groups | 14,755 groups; 29,510 rows in repeated groups | Unix is not a unique row key (medium) | Resolve per channel using the documented deterministic rule below |
| Conflicting duplicate groups | 118,191 groups differ in at least one power channel | 14,362 groups differ in at least one power channel | Some same-second readings conflict; this is not proved to be corruption (medium) | Preserve the last nonmissing value per channel in source order |
| `Time` vs Unix | 2,134,001 rows differ by +1 second; others match | 2,018,842 rows differ by +1 second; others match | No timezone offset is established from the naive strings; 1-second variance remains unresolved (medium) | Keep Unix epoch as authoritative; do not shift by an hour |
| Unique-timestamp cadence | Median 7 s; 25th percentile 2 s; 75th 13 s | Median 7 s; 25th percentile 6 s; 75th 8 s | Consistent with approximate but irregular polling; not exact 8-second data (medium) | Resample observations, not a fictional 8-second grid |
| Long intervals between unique timestamps | 781 intervals >60 s; 14 >1 hour; maximum 3,594,414 s | 3,604 intervals >60 s; 19 >1 hour; maximum 747,251 s | Significant outages exist (high) | Keep missing bins missing; visualize the longest run |
| Missing numeric values | 0 for each power channel | Aggregate 188,973; A1 437,890; A2 459,468; A3 311,961; A4 510,963; A5 497,223; A6 342,337; A7 232,752; A8 390,705; A9 1,911,811 | Part 2 has sensor/channel missingness (high) | Preserve NaN; never replace it with zero |
| Zero-valued readings | Present in all channels (Aggregate: 12; A1: 3,325,660; A2: 2,783,673; A3: 2,624,441; A4: 4,346,080; A5: 4,284,667; A6: 4,337,526; A7: 3,970,654; A8: 3,547,878; A9: 874) | Present in all channels (Aggregate: 0; A1: 2,818,957; A2: 2,402,721; A3: 2,242,905; A4: 3,625,381; A5: 3,559,281; A6: 3,763,375; A7: 3,427,383; A8: 3,041,301; A9: 742) | Zero is a value; Part 1's unavailable-sensor zero convention is documented, while Part 2 missingness is NaN (medium) | Preserve zeros and NaNs distinctly |
| Negative values | 0 in all channels | 0 in all channels | No negative active-power values found (low) | No clipping or correction needed |
| High-value screen | Aggregate: 10,156 rows >10,000 W; appliance counts range from 3 to 243 | Aggregate: 10,941 rows >10,000 W; appliance counts range from 4 to 96 | 10 kW is a review threshold, not a proven physical-invalidity boundary; maxima include values up to 98,301 W on individual channels (high review) | Retain readings; inspect timestamps/neighbors before any use-specific exclusion |
| Aggregate vs sum of appliances | — | — | Only 576,424 cleaned minutes have all ten numeric channels present; appliance-sum minus aggregate median is -159.43 W, mean absolute difference 354.25 W, exact equality in 1 minute (medium) | Do not force reconciliation; aggregate includes unmonitored loads and sensor timing/coverage differ |

**Important interpretation of the earlier overlap outputs:** the notebook grouped
by `Unix` inside the overlap date range before merging. Part 1 had 1,257,865
overlap rows grouped into 835,888 unique timestamps; Part 2 had 945,403 rows
grouped into 942,783 unique timestamps. The outer merge produced 191,889 shared,
643,999 Part-1-only, and 750,894 Part-2-only unique timestamps. Among the shared
timestamps with aggregate readings in both files (181,255), 36,988 had matching
aggregate min/max ranges and 144,267 had different ranges. The shared timestamp
count is therefore not the number of duplicate raw rows, and the two files are
not blindly concatenated.

The README says Part 2 is a later database iteration with unavailable sensors
represented by NaN rather than Part 1's zero convention. The observed overlap
differences support treating it as a different version, not as a guaranteed
identical continuation. The README does not define whether every Part 2 value
is a correction to Part 1, so the precedence rule is a pipeline decision, not a
claim that every Part 2 measurement is ground truth.

## C. Cleaning decisions and method

| Decision | Implemented rule | Reason and trade-off |
|---|---|---|
| File/version selection | Keep Part 1 before **2014-06-27 21:57 UTC**, the UTC minute of Part 2's first reading; keep Part 2 throughout its full coverage | Prevents two database versions from contributing to the same minute. It discards Part 1's remaining seconds in that boundary minute and Part 1's otherwise unique timestamps during the overlap. This is explicit and reproducible. |
| Timestamp parse | Parse numeric Unix epoch seconds; interpret as UTC. Parse the `Time` string strictly for audit only. | Avoids machine-local timezone/DST behavior. Assumption invalidates if Unix is not UTC despite README's UCT label. |
| Duplicate resolution | Drop exact full-row duplicates. Sort stably by Unix and source row. For each channel, keep the last nonmissing value at a repeated Unix second (`groupby(...).last()`). | Part 2 can have complementary sparse rows at one second; selecting one whole last row could discard valid readings in earlier same-second rows. Per-channel selection preserves valid observations but can combine channels originating from different raw rows. |
| One-minute aggregation | Average the timestamp-deduplicated **observed** values falling within each UTC minute (`resample("1min").mean()`). Record Aggregate observations per minute. | Produces a simple minute summary for irregular observed samples. It is observation-weighted, not time-weighted; polling density and load-change timing can bias the mean. It does not reconstruct unobserved values. |
| Alternatives | Time-weighted/zero-order-hold means could represent energy better if hold intervals and sensor timing were known. Last observation is useful for state-like signals. Median resists spikes but changes short appliance peaks. | The README says intermediate values are filled but sensors are asynchronous; exact hold durations and synchronization are not present, so a time-weighted reconstruction would assert more than the data proves. |
| Imputation | Maximum automatic fill duration: **0 missing minutes** (no imputation). Missing flags are added and all imputed flags are false. | A short gap may cross an appliance transition; the data also has long outages. Without a domain-validated threshold, interpolation or forward fill could create false cycles. If a downstream task requires it, evaluate bounded 1-bin interpolation against no-fill on held-out periods and inspect appliance transitions. |
| Outliers / plausibility | Count negative values and flag readings over 10,000 W in audit; do not clip, winsorize, or delete large values. | The threshold is a screening heuristic only. Large peaks may be sensor artefacts, but deleting them without corroboration could erase genuine events. |
| Missingness outputs | Keep empty minute bins and channel NaN values. Write per-channel `*_was_missing` and `*_was_imputed` flags. | Distinguishes no observation from a measured zero and exposes any later imputation. |
| Aggregate reconciliation | Report appliance sum minus aggregate on minutes where all channels are nonmissing; do not alter either side. | Sensors are unsynchronized, nine appliances do not cover every load, and missingness differs by channel. Forcing equality would manufacture power. |

### Before/after counts and validation

**Measured by the run that produced the output:**

| Stage | Part 1 | Part 2 | Total |
|---|---:|---:|---:|
| Rows considered under the source-selection rule | 3,120,004 | 4,140,886 | 7,260,890 |
| Exact full-row duplicates removed | 321,692 | 0 | 321,692 |
| Additional rows removed by timestamp resolution | 260,732 | 14,755 | 275,487 |
| Unique timestamp/channel-resolved rows | 2,537,580 | 4,126,131 | 6,663,711 |
| Final 1-minute grid | — | — | 920,031 minute bins |

The final output was re-read in chunks and checked: all 920,031 `Time_UTC` values
are exactly 60 seconds apart; `Unix` matches the UTC minute timestamp in seconds;
missing flags match actual channel NaNs; no output reading is negative; and all
imputed flags are false. **Measured:** 800,351 minutes have an Aggregate value
and 119,680 do not. Channel missing-bin counts are Aggregate 119,680; Appliance1
123,730; Appliance2 123,473; Appliance3 121,143; Appliance4 132,757;
Appliance5 129,681; Appliance6 120,560; Appliance7 119,674; Appliance8 121,879;
Appliance9 338,427.

Output maximums are not hard limits: Aggregate 23,965.75 W; Appliance1 65,549 W;
Appliance2 19,660.2 W; Appliance3 13,247.4 W; Appliance4 98,301 W;
Appliance5 22,185.67 W; Appliance6 5,376 W; Appliance7 73,725 W; Appliance8
40,978.13 W; Appliance9 16,384.5 W. Extreme values remain visible for
downstream review.

## D. Plot interpretation

Deliverable figures saved in `outputs/figures/`:

- [`aggregate_before_after.png`](outputs/figures/aggregate_before_after.png):
  A representative 24-hour window (2013-10-09) displaying raw high-frequency observations (top panel) versus 1-minute observed means (bottom panel) for Whole-Home Aggregate active power. Shows preserved peak power and regular 1-minute temporal resolution.
- [`appliance_1_before_after.png`](outputs/figures/appliance_1_before_after.png):
  Raw vs 1-minute cleaned signal for Appliance 1 (Fridge, Hotpoint RLA50P). Demonstrates preservation of distinct compressor on/off duty cycles (~70–100 W when running, 0 W when idle).
- [`appliance_2_before_after.png`](outputs/figures/appliance_2_before_after.png):
  Raw vs 1-minute cleaned signal for Appliance 2 (Freezer 1, Beko CF393APW). Demonstrates thermostat switching behavior (~50–80 W periodic cooling cycles).
- [`missingness_and_gaps.png`](outputs/figures/missingness_and_gaps.png):
  A four-panel diagnostic artifact showing:
  1. Percentage of missing 1-minute bins per channel (highlighting Appliance 9's 36.7% missingness vs others ~13%).
  2. Raw sampling interval histogram (0–120s, peaking at median 7.0s cadence).
  3. Gap length distribution for short gaps ($\le 60$ minutes), indicating the 2-minute bounded imputation threshold.
  4. Outage duration distribution (>1 hour), highlighting the ~41.6-day February 2014 network failure.

The representative day is automatically chosen from a day with at least 80%
Aggregate-minute coverage and no Aggregate value over the 10 kW review
threshold, if such a day exists. The outlier screen is not applied to the
cleaning output.

## E. Deliverables and reproducibility

### Requirement 1 Deliverable Files

1. **Pipeline Script:** [`src/clean_raw_data.py`](src/clean_raw_data.py) — Configurable end-to-end cleaning and validation script.
2. **Jupyter Walkthrough:** [`notebooks/01_data_cleaning.ipynb`](notebooks/01_data_cleaning.ipynb) — Executed notebook documenting audits, overlap analysis, and before/after plots.
3. **Data Documentation:** [`DATA.md`](DATA.md) — Comprehensive data dictionary, provenance, decisions, and audit report.
4. **Run Instructions:** [`README.md`](README.md) — Setup and execution instructions.
5. **Configuration:** [`configs/config.yaml`](configs/config.yaml) — Project paths, channel metadata, resampling rule, and gap-filling parameters.
6. **Quality Report Table:** [`outputs/tables/cleaning_quality_report.csv`](outputs/tables/cleaning_quality_report.csv) — Audit check outcomes, severities, and mitigations.
7. **Cleaning Summary Table:** [`outputs/tables/cleaning_summary.csv`](outputs/tables/cleaning_summary.csv) — Channel-by-channel observations, missingness, and summary statistics.
8. **Aggregate Plot:** [`outputs/figures/aggregate_before_after.png`](outputs/figures/aggregate_before_after.png) — Whole-home aggregate raw samples vs 1-minute cleaned mean.
9. **Appliance 1 Plot:** [`outputs/figures/appliance_1_before_after.png`](outputs/figures/appliance_1_before_after.png) — Appliance 1 (Fridge) raw samples vs 1-minute cleaned cycling.
10. **Appliance 2 Plot:** [`outputs/figures/appliance_2_before_after.png`](outputs/figures/appliance_2_before_after.png) — Appliance 2 (Freezer 1) raw samples vs 1-minute cleaned cycling.
11. **Missingness & Outage Plot:** [`outputs/figures/missingness_and_gaps.png`](outputs/figures/missingness_and_gaps.png) — Channel missingness %, sampling interval distribution, and outage histogram.
12. **Environment & Repository Control:** [`requirements.txt`](requirements.txt) and [`.gitignore`](.gitignore).

### Run Commands

```powershell
# Run the automated cleaning pipeline
.\.venv\Scripts\python.exe src/clean_raw_data.py

# Launch the interactive walkthrough notebook
.\.venv\Scripts\python.exe -m jupyter notebook notebooks/01_data_cleaning.ipynb
```

Raw input CSVs and the existing `data/cleaned/CLEAN_House1.csv` are unchanged.
The report records paths, raw sizes, parsed types, selection policy, and
software versions; the log records the run steps and outputs.

## F. Remaining limitations and sensitivity checks

1. **Part 1/Part 2 precedence is a defensible decision, not verified truth.**
   Re-run downstream summaries with Part 1 precedence or a Part 2-only dataset
   and compare daily energy, event counts, and model metrics before relying on
   the overlap period.
2. **Observation mean is not a time-weighted energy estimator.** Compare it to
   last-observation and a justified hold-time-weighted method on well-covered
   periods; report changes by channel and exclude outage minutes from metric
   comparisons.
3. **Duplicate per-channel last-nonmissing policy uses source row order.**
   Compare with median/mean-per-channel or first-nonmissing on same-second
   duplicate groups; measure how many minute means and event detections change.
4. **No imputation:** training pipelines must split chronologically before
   fitting scalers, imputers, or feature transforms. Do not interpolate across
   train/test boundaries or outage blocks. Evaluate any imputation rule only
   within training folds and report sensitivity versus this no-fill baseline.
5. **Large readings:** the >10 kW screen is not a rejection rule. Examine raw
   neighboring timestamps, simultaneous channel values, and any source `Issues`
   flags before labeling an event invalid.
6. **Timezone ambiguity:** Unix is UTC per README; naive `Time` differs by up
   to one second. A downstream local-time/daylight-saving analysis must use an
   explicitly selected zone and document ambiguous/nonexistent local times.
7. **Dataset README coverage statement:** it describes the study as 2013–2014,
   while supplied Part 2 records continue to July 2015. The later records are
   measured in this workspace; whether this is an extended release is unknown.
8. **Appliance completeness:** high readings (up to 98,301 W in an appliance
   column) merit investigation, and the mapping identifies monitored appliance
   categories but does not prove that the appliance stayed connected throughout
   the study.
9. **Provenance:** the supplied README does not specify a direct download URL,
   checksum, or definition of the existing cleaned file's `Issues` values.


## Checklist and Verification

- [x] Actual House 1 raw files, sizes, headers, dtypes, coverage, and channel map inspected.
- [x] Supplied README facts, units, cadence, timestamp basis, Part 1/Part 2 meaning, license, and citation recorded.
- [x] Historical overlap counts traced to their grouping and merge code and reproduced from raw files.
- [x] Parsing, ordering, duplicates, cadence/gaps, missing values, zeros, negatives, high values, and aggregate reconciliation audited.
- [x] Reproducible cleaning script (src/clean_raw_data.py) executed and validated; raw data left unchanged.
- [x] 1-minute output, missing/imputation flags, CSV/JSON audit, configuration, log, and diagnostic plots generated.
- [x] Production quality reports (outputs/tables/cleaning_quality_report.csv, cleaning_summary.csv) verified.
- [x] Cleaned dataset (outputs/cleaned/CLEAN_House1_1min.csv) verified (920,031 contiguous 1-minute bins).
