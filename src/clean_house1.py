"""Audit and resample REFIT House 1 raw data without modifying source files."""

from __future__ import annotations

import json
import logging
import platform
import sys
from datetime import timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
CLEAN_DIR = OUTPUT_DIR / "cleaned"
METRICS_DIR = OUTPUT_DIR / "metrics"
FIGURES_DIR = OUTPUT_DIR / "figures"

RAW_FILES = (
    "RAW_House1_Part1.csv",
    "RAW_House1_Part2.csv",
)
TIMESTAMP_COLUMNS = ("Time", "Unix")
POWER_COLUMNS = ("Aggregate", *(f"Appliance{i}" for i in range(1, 10)))
RAW_COLUMNS = (*TIMESTAMP_COLUMNS, *POWER_COLUMNS)
OVERLAP_START = 1_403_906_269
OVERLAP_END = 1_412_126_827
HIGH_POWER_SCREEN_W = 10_000
RESAMPLE_RULE = "1min"
IMPUTATION_POLICY = "none"

HOUSE1_CHANNELS = {
    "Aggregate": "Whole-home aggregate",
    "Appliance1": "Fridge",
    "Appliance2": "Freezer(1)",
    "Appliance3": "Freezer(2)",
    "Appliance4": "Washer Dryer",
    "Appliance5": "Washing Machine",
    "Appliance6": "Dishwasher",
    "Appliance7": "Computer",
    "Appliance8": "Television Site",
    "Appliance9": "Electric Heater",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(OUTPUT_DIR / "cleaning.log", mode="w", encoding="utf-8"),
    ],
)
LOGGER = logging.getLogger("house1_cleaning")


def ensure_output_directories() -> None:
    for directory in (OUTPUT_DIR, CLEAN_DIR, METRICS_DIR, FIGURES_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def read_raw_file(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, usecols=RAW_COLUMNS, low_memory=False)
    if tuple(frame.columns) != RAW_COLUMNS:
        raise ValueError(f"Unexpected columns in {path.name}: {frame.columns.tolist()}")
    frame["_source_row"] = np.arange(len(frame), dtype=np.int64)
    frame["Unix"] = pd.to_numeric(frame["Unix"], errors="coerce")
    for column in POWER_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def interval_summary(unix_values: np.ndarray) -> dict[str, object]:
    unique_unix = np.unique(unix_values[np.isfinite(unix_values)]).astype(np.int64)
    if len(unique_unix) < 2:
        return {
            "unique_timestamps": int(len(unique_unix)),
            "positive_intervals": 0,
            "interval_quantiles_seconds": {},
            "intervals_over_8_seconds": 0,
            "intervals_over_60_seconds": 0,
            "intervals_over_1_hour": 0,
            "largest_gap_seconds": None,
        }

    intervals = np.diff(unique_unix)
    positive = intervals[intervals > 0]
    quantiles = (
        pd.Series(positive)
        .quantile([0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 0.999, 1.0])
        .to_dict()
    )
    return {
        "unique_timestamps": int(len(unique_unix)),
        "positive_intervals": int(len(positive)),
        "interval_quantiles_seconds": {
            str(key): float(value) for key, value in quantiles.items()
        },
        "intervals_over_8_seconds": int((positive > 8).sum()),
        "intervals_over_60_seconds": int((positive > 60).sum()),
        "intervals_over_1_hour": int((positive > 3600).sum()),
        "largest_gap_seconds": int(positive.max()),
    }


def audit_file(path: Path) -> dict[str, object]:
    frame = read_raw_file(path)
    numeric_unix = frame["Unix"]
    valid_unix = numeric_unix.dropna()
    parsed_time = pd.to_datetime(
        frame["Time"], format="%Y-%m-%d %H:%M:%S", errors="coerce"
    )
    epoch_time = pd.to_datetime(numeric_unix, unit="s", utc=True, errors="coerce")
    time_epoch_delta = (
        parsed_time - epoch_time.dt.tz_localize(None)
    ).dt.total_seconds()
    row_delta = numeric_unix.diff()
    duplicate_rows = frame.duplicated(subset=RAW_COLUMNS, keep="first")
    repeated_timestamp_rows = frame["Unix"].duplicated(keep=False)
    duplicate_groups = frame.loc[repeated_timestamp_rows].groupby(
        "Unix", sort=False
    )[list(POWER_COLUMNS)].nunique(dropna=False)
    conflicting_groups_by_channel = {
        column: int((duplicate_groups[column] > 1).sum())
        for column in POWER_COLUMNS
    }
    numeric = frame[list(POWER_COLUMNS)]
    interval_stats = interval_summary(valid_unix.to_numpy(dtype=np.float64))

    result: dict[str, object] = {
        "file": path.name,
        "path": str(path.resolve()),
        "bytes": int(path.stat().st_size),
        "format": "CSV",
        "rows": int(len(frame)),
        "columns": list(frame.columns.drop("_source_row")),
        "dtypes": {
            column: str(frame[column].dtype)
            for column in frame.columns.drop("_source_row")
        },
        "invalid_unix_timestamps": int(numeric_unix.isna().sum()),
        "invalid_time_strings": int(parsed_time.isna().sum()),
        "time_unix_delta_seconds": {
            str(key): int(value)
            for key, value in time_epoch_delta.value_counts(dropna=False).items()
        },
        "time_unix_nonnull_mismatches": int(
            (time_epoch_delta.notna() & time_epoch_delta.ne(0)).sum()
        ),
        "row_order_unix_decreases": int((row_delta < 0).sum()),
        "row_order_unix_repeats": int((row_delta == 0).sum()),
        "exact_duplicate_rows": int(duplicate_rows.sum()),
        "rows_at_duplicate_timestamps": int(repeated_timestamp_rows.sum()),
        "duplicate_timestamp_groups": int(
            frame.loc[repeated_timestamp_rows, "Unix"].nunique()
        ),
        "conflicting_duplicate_timestamp_groups_by_channel": (
            conflicting_groups_by_channel
        ),
        "conflicting_duplicate_timestamp_groups_any_channel": int(
            (duplicate_groups > 1).any(axis=1).sum()
        ),
        "raw_missing_by_channel": {
            column: int(numeric[column].isna().sum()) for column in POWER_COLUMNS
        },
        "raw_zero_by_channel": {
            column: int(numeric[column].eq(0).sum()) for column in POWER_COLUMNS
        },
        "raw_negative_by_channel": {
            column: int(numeric[column].lt(0).sum()) for column in POWER_COLUMNS
        },
        "raw_over_10000_w_by_channel": {
            column: int(numeric[column].gt(HIGH_POWER_SCREEN_W).sum())
            for column in POWER_COLUMNS
        },
        "raw_min_by_channel": {
            column: None if numeric[column].notna().sum() == 0
            else float(numeric[column].min())
            for column in POWER_COLUMNS
        },
        "raw_max_by_channel": {
            column: None if numeric[column].notna().sum() == 0
            else float(numeric[column].max())
            for column in POWER_COLUMNS
        },
        "unix_min": int(valid_unix.min()),
        "unix_max": int(valid_unix.max()),
        "utc_min": pd.to_datetime(int(valid_unix.min()), unit="s", utc=True).isoformat(),
        "utc_max": pd.to_datetime(int(valid_unix.max()), unit="s", utc=True).isoformat(),
        "intervals": interval_stats,
    }
    del frame
    return result


def overlap_audit(paths: list[Path]) -> tuple[dict[str, object], pd.DataFrame]:
    summaries: list[pd.DataFrame] = []
    range_rows: list[dict[str, object]] = []
    for path in paths:
        frame = read_raw_file(path)
        overlap = frame.loc[
            frame["Unix"].between(OVERLAP_START, OVERLAP_END),
            ["Unix", "Aggregate"],
        ]
        summary = overlap.groupby("Unix", sort=False).agg(
            rows=("Aggregate", "size"),
            aggregate_min=("Aggregate", "min"),
            aggregate_max=("Aggregate", "max"),
        )
        summaries.append(summary)
        range_rows.append({
            "file": path.name,
            "overlap_rows": int(len(overlap)),
            "grouped_unique_timestamps": int(len(summary)),
        })
        del frame

    left = summaries[0].add_suffix("_part1")
    right = summaries[1].add_suffix("_part2")
    comparison = (
        left.reset_index()
        .merge(
            right.reset_index(),
            on="Unix",
            how="outer",
            indicator=True,
        )
        .set_index("Unix")
    )
    counts = comparison["_merge"].value_counts()
    shared = comparison.loc[comparison["_merge"].eq("both")]
    both_aggregate = shared.dropna(
        subset=[
            "aggregate_min_part1",
            "aggregate_max_part1",
            "aggregate_min_part2",
            "aggregate_max_part2",
        ]
    )
    aggregate_matches = (
        both_aggregate["aggregate_min_part1"].eq(
            both_aggregate["aggregate_min_part2"]
        )
        & both_aggregate["aggregate_max_part1"].eq(
            both_aggregate["aggregate_max_part2"]
        )
    )
    comparison.index.name = "Unix"
    comparison.reset_index().to_csv(
        METRICS_DIR / "house1_overlap_timestamp_comparison.csv", index=False
    )
    report = {
        "overlap_start_unix": OVERLAP_START,
        "overlap_end_unix": OVERLAP_END,
        "overlap_start_utc": pd.to_datetime(
            OVERLAP_START, unit="s", utc=True
        ).isoformat(),
        "overlap_end_utc": pd.to_datetime(
            OVERLAP_END, unit="s", utc=True
        ).isoformat(),
        "files": range_rows,
        "unique_timestamp_merge_counts": {
            key: int(counts.get(key, 0))
            for key in ("both", "left_only", "right_only")
        },
        "shared_unique_timestamps": int(len(shared)),
        "shared_with_aggregate_values_in_both": int(len(both_aggregate)),
        "matching_aggregate_min_max_groups": int(aggregate_matches.sum()),
        "conflicting_aggregate_min_max_groups": int((~aggregate_matches).sum()),
    }
    return report, comparison.reset_index()


def clean_file(
    path: Path, keep_before_unix: int | None
) -> tuple[pd.DataFrame, dict[str, object], np.ndarray]:
    frame = read_raw_file(path)
    valid = frame["Unix"].notna()
    invalid_rows = int((~valid).sum())
    frame = frame.loc[valid].copy()
    frame["Unix"] = frame["Unix"].astype(np.int64)
    if keep_before_unix is not None:
        frame = frame.loc[frame["Unix"] < keep_before_unix].copy()

    considered_rows = int(len(frame))
    exact_duplicates = int(frame.duplicated(subset=RAW_COLUMNS).sum())
    frame = frame.drop_duplicates(subset=RAW_COLUMNS, keep="last")
    frame = frame.sort_values(["Unix", "_source_row"], kind="mergesort")
    duplicate_timestamp_rows = int(frame["Unix"].duplicated(keep=False).sum())
    duplicate_epoch = None
    duplicate_count = 0
    if duplicate_timestamp_rows:
        counts = frame.loc[frame["Unix"].duplicated(keep=False), "Unix"].value_counts()
        duplicate_epoch = int(counts.index[0])
        duplicate_count = int(counts.iloc[0])
    frame = frame.sort_values(["Unix", "_source_row"], kind="mergesort")
    resolved = frame.groupby("Unix", sort=False)[list(POWER_COLUMNS)].last()
    resolved.index = pd.to_datetime(resolved.index, unit="s", utc=True)
    resolved.index.name = "timestamp_utc"
    selected_unix = resolved.index.view("int64") // 1_000_000_000
    powers = resolved
    means = powers.resample(RESAMPLE_RULE).mean()
    sample_counts = powers.resample(RESAMPLE_RULE).count()
    result = means.copy()
    result.insert(0, "samples_in_minute", sample_counts["Aggregate"].astype("int32"))
    for column in POWER_COLUMNS:
        result[f"{column}_was_missing"] = means[column].isna()
        result[f"{column}_was_imputed"] = False

    stats = {
        "file": path.name,
        "rows_considered_for_cleaning": considered_rows,
        "invalid_unix_rows_excluded": invalid_rows,
        "exact_duplicate_rows_removed": exact_duplicates,
        "rows_removed_by_timestamp_resolution": int(len(frame) - len(resolved)),
        "unique_timestamps_after_resolution": int(len(resolved)),
        "duplicate_example_unix": duplicate_epoch,
        "duplicate_example_count": duplicate_count,
        "minute_bins": int(len(result)),
    }
    intervals = np.diff(selected_unix)
    del frame, resolved, powers, means, sample_counts
    return result, stats, intervals


def missing_run_summary(missing: pd.Series) -> dict[str, object]:
    mask = missing.to_numpy(dtype=bool)
    if not mask.any():
        return {"missing_bins": 0, "missing_runs": 0, "longest_run_minutes": 0}
    starts = np.flatnonzero(mask & np.r_[True, ~mask[:-1]])
    ends = np.flatnonzero(mask & np.r_[~mask[1:], True])
    lengths = ends - starts + 1
    longest = int(np.argmax(lengths))
    return {
        "missing_bins": int(mask.sum()),
        "missing_runs": int(len(starts)),
        "longest_run_minutes": int(lengths[longest]),
        "longest_run_start_utc": missing.index[int(starts[longest])].isoformat(),
        "longest_run_end_utc": missing.index[int(ends[longest])].isoformat(),
    }


def read_raw_window(paths: list[Path], start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    lower = int(start.timestamp())
    upper = int(end.timestamp())
    frames: list[pd.DataFrame] = []
    for path in paths:
        for chunk in pd.read_csv(
            path, usecols=RAW_COLUMNS, chunksize=250_000, low_memory=False
        ):
            unix = pd.to_numeric(chunk["Unix"], errors="coerce")
            selection = unix.between(lower, upper)
            if selection.any():
                part = chunk.loc[selection].copy()
                part["Unix"] = unix.loc[selection].astype(np.int64)
                for column in POWER_COLUMNS:
                    part[column] = pd.to_numeric(part[column], errors="coerce")
                part["timestamp_utc"] = pd.to_datetime(
                    part["Unix"], unit="s", utc=True
                )
                part["source_file"] = path.name
                frames.append(part)
    if not frames:
        return pd.DataFrame(columns=[*RAW_COLUMNS, "timestamp_utc", "source_file"])
    return pd.concat(frames, ignore_index=True)


def choose_representative_day(cleaned: pd.DataFrame) -> pd.Timestamp:
    daily = cleaned["samples_in_minute"].resample("1D").sum()
    complete = daily[daily >= 0.8 * 1440]
    if complete.empty:
        raise ValueError("No day has at least 80% Aggregate-minute coverage.")
    non_extreme_days = []
    for day in complete.index:
        day_data = cleaned.loc[day : day + pd.Timedelta(days=1)]
        if day_data["Aggregate"].max(skipna=True) <= HIGH_POWER_SCREEN_W:
            non_extreme_days.append(day)
    return non_extreme_days[0] if non_extreme_days else complete.index[0]


def save_before_after_plot(
    paths: list[Path], cleaned: pd.DataFrame, part2_start_minute: int
) -> str:
    day = choose_representative_day(cleaned)
    end = day + pd.Timedelta(days=1)
    raw = read_raw_window(paths, day, end)
    raw = raw.loc[
        (raw["source_file"] == RAW_FILES[1])
        | (
            (raw["source_file"] == RAW_FILES[0])
            & (raw["Unix"] < part2_start_minute)
        )
    ]
    minute = cleaned.loc[day:end]
    channels = (
        ("Aggregate", "Whole-home aggregate"),
        ("Appliance4", "Washer Dryer (Appliance4)"),
        ("Appliance5", "Washing Machine (Appliance5)"),
    )
    fig, axes = plt.subplots(3, 2, figsize=(16, 11), sharex=True)
    for row, (column, label) in enumerate(channels):
        axes[row, 0].scatter(
            raw["timestamp_utc"], raw[column], s=3, alpha=0.45, label="Raw observations"
        )
        axes[row, 0].set_title(f"Before: {label}")
        axes[row, 1].plot(
            minute.index, minute[column], linewidth=0.8, label="1-minute observed mean"
        )
        axes[row, 1].set_title(f"After: {label}")
        for axis in axes[row]:
            axis.set_ylabel("Power (W)")
            axis.grid(True, alpha=0.25)
            axis.legend(loc="upper right")
    for axis in axes[-1]:
        axis.set_xlabel("Time (UTC)")
        axis.xaxis.set_major_formatter(
            mdates.DateFormatter("%H:%M", tz=timezone.utc)
        )
    fig.suptitle(f"House 1: raw observations and 1-minute resampling ({day.date()} UTC)")
    fig.autofmt_xdate()
    fig.tight_layout()
    output = FIGURES_DIR / "house1_before_after_1min.png"
    fig.savefig(output, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return str(output.relative_to(PROJECT_ROOT))


def save_gap_plot(
    paths: list[Path],
    cleaned: pd.DataFrame,
    gap: dict[str, object],
    part2_start_minute: int,
) -> str:
    start = pd.Timestamp(gap["longest_run_start_utc"])
    end = pd.Timestamp(gap["longest_run_end_utc"])
    window_start = start - pd.Timedelta(hours=6)
    window_end = end + pd.Timedelta(hours=6)
    raw = read_raw_window(paths, window_start, window_end)
    raw = raw.loc[
        (raw["source_file"] == RAW_FILES[1])
        | (
            (raw["source_file"] == RAW_FILES[0])
            & (raw["Unix"] < part2_start_minute)
        )
    ]
    minute = cleaned.loc[window_start:window_end]
    fig, axis = plt.subplots(figsize=(15, 5))
    axis.scatter(
        raw["timestamp_utc"], raw["Aggregate"], s=4, alpha=0.5, label="Raw observations"
    )
    axis.plot(
        minute.index, minute["Aggregate"], linewidth=0.9, label="1-minute observed mean"
    )
    axis.axvspan(start, end + pd.Timedelta(minutes=1), color="red", alpha=0.12,
                 label="Longest missing run")
    axis.set_title("House 1 aggregate around the longest missing-data run")
    axis.set_ylabel("Power (W)")
    axis.set_xlabel("Time (UTC)")
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M", tz=mdates.UTC))
    axis.grid(True, alpha=0.25)
    axis.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    output = FIGURES_DIR / "house1_longest_gap.png"
    fig.savefig(output, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return str(output.relative_to(PROJECT_ROOT))


def save_diagnostics_plot(
    intervals: np.ndarray, missing_fraction: pd.Series
) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    positive = intervals[intervals > 0]
    axes[0].hist(positive, bins=np.arange(0, min(121, int(positive.max()) + 2), 1),
                 color="steelblue", alpha=0.85)
    axes[0].set_yscale("log")
    axes[0].set_xlim(0, 120)
    axes[0].set_title("Unique raw timestamp intervals (0-120 seconds)")
    axes[0].set_xlabel("Interval (seconds)")
    axes[0].set_ylabel("Count (log scale)")
    axes[0].grid(True, alpha=0.25)
    missing_fraction.sort_values().plot.barh(ax=axes[1], color="darkorange")
    axes[1].set_xlim(0, 1)
    axes[1].set_title("Missing 1-minute bins by channel")
    axes[1].set_xlabel("Fraction missing")
    axes[1].set_ylabel("")
    axes[1].grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    output = FIGURES_DIR / "house1_sampling_and_missingness.png"
    fig.savefig(output, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return str(output.relative_to(PROJECT_ROOT))


def quality_rows(report: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name, result in report["files"].items():
        rows.extend([
            {
                "dataset": name,
                "test": "Rows and file size",
                "measured_result": f"{result['rows']} rows; {result['bytes']} bytes",
                "severity": "info",
                "interpretation": "Raw CSV inventory.",
                "action": "Raw file unchanged.",
            },
            {
                "dataset": name,
                "test": "Timestamp parsing",
                "measured_result": (
                    f"Unix invalid={result['invalid_unix_timestamps']}; "
                    f"Time invalid={result['invalid_time_strings']}"
                ),
                "severity": "high" if (
                    result["invalid_unix_timestamps"] or result["invalid_time_strings"]
                ) else "info",
                "interpretation": "Unix seconds are used as the canonical timestamp.",
                "action": "Invalid Unix rows excluded from output; failures raise in the pipeline.",
            },
            {
                "dataset": name,
                "test": "Duplicate timestamp conflicts",
                "measured_result": (
                    f"{result['duplicate_timestamp_groups']} duplicate timestamp groups; "
                    f"{result['conflicting_duplicate_timestamp_groups_any_channel']} "
                    "groups differ in at least one channel"
                ),
                "severity": "medium",
                "interpretation": "Timestamp is not a unique row key in the raw files.",
                "action": (
                    "Exact rows removed; for each channel at a repeated Unix second, "
                    "the last nonmissing source value is retained."
                ),
            },
            {
                "dataset": name,
                "test": "Missing and zero power readings",
                "measured_result": json.dumps({
                    "missing": result["raw_missing_by_channel"],
                    "zero": result["raw_zero_by_channel"],
                }),
                "severity": "review",
                "interpretation": (
                    "Part 1 encodes unavailable sensors as zero; Part 2 uses NaN "
                    "for unavailable readings, as documented in raw_readme.txt."
                ),
                "action": (
                    "Zeros are preserved as measurements; Part 2 NaNs remain missing."
                ),
            },
            {
                "dataset": name,
                "test": "Row ordering and cadence",
                "measured_result": (
                    f"{result['row_order_unix_decreases']} Unix decreases; "
                    f"{result['row_order_unix_repeats']} adjacent repeats; "
                    f"unique-timestamp median interval "
                    f"{result['intervals']['interval_quantiles_seconds'].get('0.5')} s; "
                    f"{result['intervals']['intervals_over_60_seconds']} intervals >60 s"
                ),
                "severity": "medium",
                "interpretation": (
                    "The documented cadence is approximate; duplicates, polling "
                    "jitter, and outages are present."
                ),
                "action": "Sort timestamps before resampling; retain outage missingness.",
            },
            {
                "dataset": name,
                "test": "Negative active power",
                "measured_result": str(sum(result["raw_negative_by_channel"].values())),
                "severity": "medium" if sum(
                    result["raw_negative_by_channel"].values()
                ) else "info",
                "interpretation": "Negative readings are physically suspect for this active-power dataset.",
                "action": "None observed in the full scan; pipeline does not clip values.",
            },
            {
                "dataset": name,
                "test": "Power above 10 kW screen",
                "measured_result": json.dumps(result["raw_over_10000_w_by_channel"]),
                "severity": "review",
                "interpretation": "Screening threshold only; some readings may be sensor/data errors.",
                "action": "Retained unchanged and flagged for review, not deleted.",
            },
        ])
    return rows


def main() -> None:
    ensure_output_directories()
    paths = [RAW_DIR / filename for filename in RAW_FILES]
    missing_paths = [str(path) for path in paths if not path.is_file()]
    if missing_paths:
        raise FileNotFoundError(f"Required House 1 raw CSVs not found: {missing_paths}")

    LOGGER.info("Starting REFIT House 1 audit; raw files will not be modified.")
    file_reports: dict[str, dict[str, object]] = {}
    for path in paths:
        LOGGER.info("Auditing %s", path.name)
        file_reports[path.name] = audit_file(path)

    expected_columns = list(RAW_COLUMNS)
    for report in file_reports.values():
        if report["columns"] != expected_columns:
            raise ValueError(
                f"Unexpected raw header in {report['file']}: {report['columns']}"
            )
        if report["invalid_unix_timestamps"] or report["invalid_time_strings"]:
            LOGGER.warning(
                "%s has timestamp parse failures; check audit before use.",
                report["file"],
            )

    overlap, overlap_frame = overlap_audit(paths)
    LOGGER.info("Overlap timestamp comparison: %s", overlap["unique_timestamp_merge_counts"])

    part2_start = int(file_reports[paths[1].name]["unix_min"])
    part2_start_minute = (part2_start // 60) * 60
    clean1, clean1_stats, intervals1 = clean_file(
        paths[0], keep_before_unix=part2_start_minute
    )
    clean2, clean2_stats, intervals2 = clean_file(paths[1], keep_before_unix=None)
    cleaned = pd.concat([clean1, clean2]).sort_index()
    if cleaned.index.has_duplicates:
        raise AssertionError("Part-selection and duplicate resolution left duplicate minute bins.")

    cleaned.index.name = "Time_UTC"
    cleaned.insert(
        0,
        "Unix",
        cleaned.index.to_numpy(dtype="datetime64[s]").astype(np.int64),
    )
    missing_fraction = cleaned[
        [f"{column}_was_missing" for column in POWER_COLUMNS]
    ].mean()
    missing_fraction.index = [
        column.removesuffix("_was_missing") for column in missing_fraction.index
    ]
    missing_runs = {
        column: missing_run_summary(cleaned[f"{column}_was_missing"])
        for column in POWER_COLUMNS
    }
    output_csv = CLEAN_DIR / "CLEAN_House1_1min.csv"
    cleaned.to_csv(output_csv, index=True, date_format="%Y-%m-%dT%H:%M:%S%z")

    minute_stats = {
        "output_rows": int(len(cleaned)),
        "utc_start": cleaned.index.min().isoformat(),
        "utc_end": cleaned.index.max().isoformat(),
        "minute_bins_with_aggregate": int(cleaned["Aggregate"].notna().sum()),
        "full_grid_missing_aggregate_bins": int(cleaned["Aggregate"].isna().sum()),
        "per_channel_missing_bins": {
            column: int(cleaned[column].isna().sum()) for column in POWER_COLUMNS
        },
        "per_channel_imputed_bins": {
            column: int(cleaned[f"{column}_was_imputed"].sum())
            for column in POWER_COLUMNS
        },
        "per_channel_negative_bins": {
            column: int(cleaned[column].lt(0).sum()) for column in POWER_COLUMNS
        },
        "missing_runs": missing_runs,
        "max_resampled_value_w_by_channel": {
            column: None if cleaned[column].notna().sum() == 0
            else float(cleaned[column].max())
            for column in POWER_COLUMNS
        },
        "sum_appliances_comparison": {},
    }
    appliance_columns = [f"Appliance{i}" for i in range(1, 10)]
    complete = cleaned[["Aggregate", *appliance_columns]].dropna()
    residual = complete[appliance_columns].sum(axis=1) - complete["Aggregate"]
    minute_stats["sum_appliances_comparison"] = {
        "complete_channel_minutes": int(len(complete)),
        "median_appliance_sum_minus_aggregate_w": (
            None if residual.empty else float(residual.median())
        ),
        "mean_absolute_difference_w": (
            None if residual.empty else float(residual.abs().mean())
        ),
        "aggregate_and_appliance_sum_exactly_equal_minutes": int(
            residual.eq(0).sum()
        ),
    }
    selected_intervals = np.concatenate([intervals1[intervals1 > 0],
                                         intervals2[intervals2 > 0]])
    selected_intervals = selected_intervals[
        selected_intervals <= 120
    ]

    duplicate_epochs = [
        stats["duplicate_example_unix"]
        for stats in (clean1_stats, clean2_stats)
        if stats["duplicate_example_unix"] is not None
    ]
    duplicate_epoch = duplicate_epochs[0] if duplicate_epochs else part2_start
    duplicate_window_start = pd.to_datetime(
        duplicate_epoch, unit="s", utc=True
    ) - pd.Timedelta(minutes=5)
    duplicate_window_end = duplicate_window_start + pd.Timedelta(minutes=10)
    duplicate_window = read_raw_window(
        paths, duplicate_window_start, duplicate_window_end
    )
    if not duplicate_window.empty:
        fig, axis = plt.subplots(figsize=(14, 5))
        for file_name, group in duplicate_window.groupby("source_file"):
            axis.scatter(
                group["timestamp_utc"],
                group["Aggregate"],
                s=7,
                alpha=0.55,
                label=f"Raw {file_name}",
            )
        axis.plot(
            cleaned.loc[duplicate_window_start:duplicate_window_end].index,
            cleaned.loc[duplicate_window_start:duplicate_window_end]["Aggregate"],
            color="black",
            linewidth=1.2,
            label="1-minute observed mean",
        )
        axis.set_title("Aggregate around a repeated Unix timestamp")
        axis.set_ylabel("Power (W)")
        axis.set_xlabel("Time (UTC)")
        axis.grid(True, alpha=0.25)
        axis.legend()
        fig.autofmt_xdate()
        fig.tight_layout()
        duplicate_plot = FIGURES_DIR / "house1_duplicate_timestamp_window.png"
        fig.savefig(duplicate_plot, dpi=160, bbox_inches="tight")
        plt.close(fig)
    else:
        duplicate_plot = None

    longest_aggregate_gap = missing_runs["Aggregate"]
    gap_plot = None
    if longest_aggregate_gap.get("longest_run_minutes", 0):
        gap_plot = save_gap_plot(
            paths, cleaned, longest_aggregate_gap, part2_start_minute
        )

    representative_plot = save_before_after_plot(
        paths, cleaned, part2_start_minute
    )
    diagnostics_plot = save_diagnostics_plot(selected_intervals, missing_fraction)

    report: dict[str, object] = {
        "report_generated_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "project_root": str(PROJECT_ROOT),
        "dataset": "REFIT House 1 active power",
        "units": "W",
        "timestamp_basis": (
            "Unix epoch seconds interpreted as UTC; Time strings parsed as "
            "naive UTC only for consistency checks."
        ),
        "documented_cadence_seconds": 8,
        "file_selection_policy": (
            "Part 1 rows strictly before the UTC minute containing Part 2's "
            "first Unix timestamp, then "
            "all Part 2 rows. Part 2 takes precedence throughout its temporal "
            "coverage because README identifies it as the later database iteration."
        ),
        "duplicate_policy": (
            "Remove exact full-row duplicates; stable-sort by Unix then original "
            "row order; for each channel at a duplicate Unix timestamp, keep the "
            "last nonmissing value. This preserves channel values when Part 2 has "
            "separate sparse rows at the same second."
        ),
        "resampling_policy": (
            "Mean of observed, timestamp-deduplicated readings within each UTC "
            "minute; empty minutes remain missing. This is observation-weighted, "
            "not a time-weighted reconstruction."
        ),
        "imputation_policy": IMPUTATION_POLICY,
        "high_power_screen_w": HIGH_POWER_SCREEN_W,
        "house1_channel_mapping_documented": HOUSE1_CHANNELS,
        "files": file_reports,
        "overlap": overlap,
        "cleaning": {
            "part1": clean1_stats,
            "part2": clean2_stats,
            "output_csv": str(output_csv.relative_to(PROJECT_ROOT)),
            "raw_rows_considered": int(
                clean1_stats["rows_considered_for_cleaning"]
                + clean2_stats["rows_considered_for_cleaning"]
            ),
            "cleaned_minutes": minute_stats,
        },
        "figures": {
            "before_after": representative_plot,
            "longest_gap": gap_plot,
            "duplicate_window": (
                None if duplicate_plot is None
                else str(duplicate_plot.relative_to(PROJECT_ROOT))
            ),
            "sampling_missingness": diagnostics_plot,
        },
        "official_cleaned_reference": {
            "path": "data/cleaned/CLEAN_House1.csv",
            "not_modified": True,
            "observed_header": [
                "Time", "Unix", *POWER_COLUMNS, "Issues"
            ],
        },
        "environment": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
    }
    report_path = METRICS_DIR / "house1_audit.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    pd.DataFrame(quality_rows(report)).to_csv(
        METRICS_DIR / "house1_quality_audit.csv", index=False
    )
    config = {
        "input_files": [str(path.relative_to(PROJECT_ROOT)) for path in paths],
        "output_file": str(output_csv.relative_to(PROJECT_ROOT)),
        "resample_rule": RESAMPLE_RULE,
        "resample_aggregation": "mean of observed values per UTC minute",
        "imputation": IMPUTATION_POLICY,
        "high_power_screen_w": HIGH_POWER_SCREEN_W,
        "part1_exclusive_end_unix": part2_start_minute,
        "duplicate_rule": report["duplicate_policy"],
    }
    (METRICS_DIR / "house1_cleaning_config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )
    LOGGER.info(
        "Finished: %s rows in %s; report at %s",
        minute_stats["output_rows"],
        output_csv.relative_to(PROJECT_ROOT),
        report_path.relative_to(PROJECT_ROOT),
    )
    LOGGER.info(
        "Generated figures: %s",
        json.dumps(report["figures"]),
    )


if __name__ == "__main__":
    main()
