"""Washing Machine Usage Analysis & Disaggregation EDA on Official Cleaned REFIT Dataset.

Flock Energy NILM Appliance Disaggregation Project.
Analyses Houses 1, 2, 3, 5, and 20 at 1-minute resolution.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.ndimage import label

# Project root setup
PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / "outputs" / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import seaborn as sns

LOGGER = logging.getLogger("washing_machine_eda")

CLEAN_DATA_DIR = PROJECT_ROOT / "data" / "cleaned"
RESULTS_DIR = PROJECT_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
TABLES_DIR = RESULTS_DIR / "tables"

# Documented washing machine channel mapping and household demographics from REFIT README
HOUSEHOLD_REGISTRY = {
    1: {
        "channel": "Appliance5",
        "appliance_name": "Washing Machine",
        "washer_dryer_channel": "Appliance4",
        "occupancy": 2,
        "house_type": "Detached (4 bed)",
        "construction_year": "1975-1980",
    },
    2: {
        "channel": "Appliance2",
        "appliance_name": "Washing Machine",
        "washer_dryer_channel": None,
        "occupancy": 4,
        "house_type": "Semi-detached (3 bed)",
        "construction_year": "Unknown",
    },
    3: {
        "channel": "Appliance6",
        "appliance_name": "Washing Machine",
        "washer_dryer_channel": "Appliance4 (Tumble Dryer)",
        "occupancy": 2,
        "house_type": "Detached (3 bed)",
        "construction_year": "1988",
    },
    5: {
        "channel": "Appliance3",
        "appliance_name": "Washing Machine",
        "washer_dryer_channel": "Appliance2 (Tumble Dryer)",
        "occupancy": 4,
        "house_type": "Mid-terrace (4 bed)",
        "construction_year": "1878",
    },
    20: {
        "channel": "Appliance4",
        "appliance_name": "Washing Machine",
        "washer_dryer_channel": "Appliance3 (Tumble Dryer)",
        "occupancy": 2,
        "house_type": "Detached (3 bed)",
        "construction_year": "1965-1974",
    },
}


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def load_and_resample_household(
    house_id: int,
    col: str,
    clean_dir: Path = CLEAN_DATA_DIR,
) -> tuple[pd.Series, pd.Series, dict[str, Any]]:
    """Load official cleaned CSV, deduplicate same-second readings, and resample to 1 minute."""
    fpath = clean_dir / f"CLEAN_House{house_id}.csv"
    if not fpath.is_file():
        raise FileNotFoundError(f"Cleaned dataset missing for House {house_id}: {fpath}")

    LOGGER.info("Loading House %d from %s...", house_id, fpath.name)
    raw_df = pd.read_csv(fpath, usecols=["Unix", "Aggregate", col, "Issues"])
    total_raw_rows = len(raw_df)

    # Convert Unix epoch to UTC datetime
    raw_df["Time_UTC"] = pd.to_datetime(raw_df["Unix"], unit="s", utc=True)

    # Deterministic deduplication: keep last observation at duplicate timestamps
    dedup = raw_df.groupby("Time_UTC")[["Aggregate", col, "Issues"]].last()

    # Resample to 1-minute observed mean
    resampled_wm = dedup[col].resample("1min").mean()
    resampled_agg = dedup["Aggregate"].resample("1min").mean()
    resampled_issues = dedup["Issues"].resample("1min").max()

    total_1min_bins = len(resampled_wm)
    missing_bins = int(resampled_wm.isna().sum())
    valid_bins = total_1min_bins - missing_bins
    observed_zero_bins = int((resampled_wm == 0).sum())
    standby_bins = int(((resampled_wm > 0) & (resampled_wm < 20.0)).sum())
    active_bins = int((resampled_wm >= 20.0).sum())

    meta = {
        "house_id": house_id,
        "household": f"House {house_id}",
        "channel": col,
        "total_raw_rows": total_raw_rows,
        "start_time_utc": str(resampled_wm.index[0]),
        "end_time_utc": str(resampled_wm.index[-1]),
        "total_days": round(total_1min_bins / 1440.0, 1),
        "total_1min_bins": total_1min_bins,
        "valid_bins": valid_bins,
        "coverage_pct": round(100.0 * valid_bins / total_1min_bins, 2),
        "missing_bins": missing_bins,
        "missing_pct": round(100.0 * missing_bins / total_1min_bins, 2),
        "observed_zero_bins": observed_zero_bins,
        "zero_pct": round(100.0 * observed_zero_bins / total_1min_bins, 2),
        "standby_bins": standby_bins,
        "standby_pct": round(100.0 * standby_bins / total_1min_bins, 2),
        "active_bins": active_bins,
        "active_pct": round(100.0 * active_bins / total_1min_bins, 2),
        "flagged_issue_bins": int((resampled_issues > 0).sum()),
    }

    return resampled_wm, resampled_agg, meta


def detect_washing_machine_cycles(
    series_1min: pd.Series,
    p_thresh: float = 20.0,
    min_duration: int = 15,
    max_gap: int = 3,
    household_label: str = "House 1",
) -> pd.DataFrame:
    """Vectorized, robust detection of washing-machine cycles with gap merging."""
    vals = series_1min.to_numpy()
    is_na = np.isnan(vals)
    clean_vals = np.nan_to_num(vals, nan=0.0)
    is_active = clean_vals >= p_thresh

    # Morphological gap-merging: label inactive runs
    inactive_labels, num_gaps = label(~is_active)
    if num_gaps > 0:
        gap_sizes = np.bincount(inactive_labels)[1:]
        small_gaps = np.where(gap_sizes <= max_gap)[0] + 1
        # Exclude leading/trailing edge gaps
        if inactive_labels[0] in small_gaps:
            small_gaps = small_gaps[small_gaps != inactive_labels[0]]
        if inactive_labels[-1] in small_gaps:
            small_gaps = small_gaps[small_gaps != inactive_labels[-1]]

        merged_active = is_active.copy()
        if len(small_gaps) > 0:
            merged_active[np.isin(inactive_labels, small_gaps)] = True
    else:
        merged_active = is_active.copy()

    # Label contiguous active event blocks
    event_labels, num_events = label(merged_active)
    if num_events == 0:
        return pd.DataFrame()

    durations = np.bincount(event_labels)[1:]
    valid_events = np.where(durations >= min_duration)[0] + 1

    records = []
    for ev_num, ev_id in enumerate(valid_events, 1):
        locs = np.where(event_labels == ev_id)[0]
        start_i, end_i = locs[0], locs[-1]
        ev_vals = vals[start_i : end_i + 1]
        ev_na = is_na[start_i : end_i + 1]

        # Calculate metrics
        dur = len(locs)
        act_dur = int(np.sum(clean_vals[start_i : end_i + 1] >= p_thresh))
        peak_w = float(np.nanmax(ev_vals))
        mean_w = float(np.nanmean(ev_vals))
        # Energy in Wh: sum of 1-minute power divided by 60
        energy_wh = float(np.nansum(ev_vals) / 60.0)
        missing_count = int(np.sum(ev_na))

        records.append({
            "household": household_label,
            "cycle_id": f"{household_label.replace(' ', '')}_C{ev_num:04d}",
            "start_time": series_1min.index[start_i].isoformat(),
            "end_time": series_1min.index[end_i].isoformat(),
            "start_timestamp_unix": int(series_1min.index[start_i].timestamp()),
            "end_timestamp_unix": int(series_1min.index[end_i].timestamp()),
            "duration_min": dur,
            "active_duration_min": act_dur,
            "inactive_pause_min": dur - act_dur,
            "peak_power_w": round(peak_w, 1),
            "mean_power_w": round(mean_w, 1),
            "energy_wh": round(energy_wh, 2),
            "energy_kwh": round(energy_wh / 1000.0, 4),
            "missing_minutes": missing_count,
            "has_missing_readings": bool(missing_count > 0),
            "is_truncated": bool(start_i == 0 or end_i == len(vals) - 1 or missing_count > 0.2 * dur),
        })

    return pd.DataFrame(records)


def run_sensitivity_analysis(
    series_map: dict[str, pd.Series],
) -> pd.DataFrame:
    """Evaluate alternative threshold, duration, and gap settings across all households."""
    LOGGER.info("Running sensitivity analysis across detection parameter grid...")
    scenarios = [
        {"name": "Baseline (P=20W, D=15m, G=3m)", "p_thresh": 20.0, "min_dur": 15, "max_gap": 3},
        {"name": "Lower Threshold (P=10W, D=15m, G=3m)", "p_thresh": 10.0, "min_dur": 15, "max_gap": 3},
        {"name": "Higher Threshold (P=50W, D=15m, G=3m)", "p_thresh": 50.0, "min_dur": 15, "max_gap": 3},
        {"name": "Shorter Duration (P=20W, D=10m, G=3m)", "p_thresh": 20.0, "min_dur": 10, "max_gap": 3},
        {"name": "Longer Duration (P=20W, D=25m, G=3m)", "p_thresh": 20.0, "min_dur": 25, "max_gap": 3},
        {"name": "Strict No-Gap (P=20W, D=15m, G=0m)", "p_thresh": 20.0, "min_dur": 15, "max_gap": 0},
        {"name": "Wider Gap Merge (P=20W, D=15m, G=5m)", "p_thresh": 20.0, "min_dur": 15, "max_gap": 5},
    ]

    results = []
    for sc in scenarios:
        for hh_label, s_1min in series_map.items():
            df_cycles = detect_washing_machine_cycles(
                s_1min,
                p_thresh=sc["p_thresh"],
                min_duration=sc["min_dur"],
                max_gap=sc["max_gap"],
                household_label=hh_label,
            )
            count = len(df_cycles)
            results.append({
                "scenario": sc["name"],
                "household": hh_label,
                "p_thresh_w": sc["p_thresh"],
                "min_duration_min": sc["min_dur"],
                "max_gap_min": sc["max_gap"],
                "detected_cycle_count": count,
                "median_duration_min": round(df_cycles["duration_min"].median(), 1) if count > 0 else None,
                "median_peak_power_w": round(df_cycles["peak_power_w"].median(), 1) if count > 0 else None,
                "median_energy_wh": round(df_cycles["energy_wh"].median(), 1) if count > 0 else None,
                "total_energy_kwh": round(df_cycles["energy_kwh"].sum(), 2) if count > 0 else 0.0,
            })

    return pd.DataFrame(results)


def plot_representative_24h(
    s_wm: pd.Series,
    s_agg: pd.Series,
    household: str,
    output_dir: Path = FIGURES_DIR,
) -> Path:
    """Plot 1: Representative 24-hour trace showing whole-home aggregate and washing machine power."""
    # Find a day with active laundry and high coverage
    daily_wm = s_wm.resample("1D").max()
    active_days = daily_wm[daily_wm > 1500].index
    chosen_day = active_days[10] if len(active_days) > 10 else active_days[0]
    next_day = chosen_day + pd.Timedelta(days=1)

    sub_wm = s_wm.loc[chosen_day:next_day]
    sub_agg = s_agg.loc[chosen_day:next_day]

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(sub_agg.index, sub_agg, color="#1f77b4", alpha=0.6, linewidth=1.2, label="Whole-Home Aggregate Power")
    ax.plot(sub_wm.index, sub_wm, color="#d62728", linewidth=1.8, label="Washing Machine Active Power")
    ax.fill_between(sub_wm.index, 0, sub_wm, color="#d62728", alpha=0.25)

    ax.set_title(
        f"{household}: 24-Hour Active Power Trace on {chosen_day.strftime('%Y-%m-%d')} (UTC)",
        fontsize=13,
        fontweight="bold",
        pad=10,
    )
    ax.set_ylabel("Active Power (Watts)", fontsize=11)
    ax.set_xlabel("Time of Day (UTC)", fontsize=11)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right", frameon=True)
    ax.set_ylim(bottom=0)

    plt.tight_layout()
    out_path = output_dir / "representative_24h_aggregate_wm.png"
    plt.savefig(out_path, dpi=200)
    plt.close()
    LOGGER.info("Saved %s", out_path.name)
    return out_path


def plot_detected_cycle_trace(
    s_wm: pd.Series,
    cycles_df: pd.DataFrame,
    output_dir: Path = FIGURES_DIR,
) -> Path:
    """Plot 2: Detailed high-resolution zoom into detected washing-machine cycles with boundaries."""
    # Pick a typical cycle near the median duration and energy
    h1_cycles = cycles_df[cycles_df["household"] == "House 1"].copy()
    h1_cycles["start_dt"] = pd.to_datetime(h1_cycles["start_time"])
    h1_cycles["end_dt"] = pd.to_datetime(h1_cycles["end_time"])

    # Find cycle close to median duration
    med_dur = h1_cycles["duration_min"].median()
    c_idx = (h1_cycles["duration_min"] - med_dur).abs().idxmin()
    cycle = h1_cycles.loc[c_idx]

    c_start = cycle["start_dt"] - pd.Timedelta(minutes=20)
    c_end = cycle["end_dt"] + pd.Timedelta(minutes=25)
    sub = s_wm.loc[c_start:c_end]

    fig, ax = plt.subplots(figsize=(13, 6))
    ax.plot(sub.index, sub, color="#2b5c8f", marker="o", markersize=3, linewidth=1.5, label="Washing Machine Power (1-min)")
    ax.fill_between(sub.index, 0, sub, color="#2b5c8f", alpha=0.15)

    # Threshold line
    ax.axhline(20.0, color="darkorange", linestyle="--", linewidth=1.3, label="Detection Threshold (20 W)")

    # Cycle bounds
    ax.axvspan(cycle["start_dt"], cycle["end_dt"], color="#2ca02c", alpha=0.18, label="Detected Cycle Window")
    ax.axvline(cycle["start_dt"], color="#2ca02c", linestyle="-", linewidth=2.0)
    ax.axvline(cycle["end_dt"], color="#2ca02c", linestyle="-", linewidth=2.0)

    # Annotations
    ax.annotate(
        f"Cycle Start: {cycle['start_dt'].strftime('%H:%M')}",
        xy=(cycle["start_dt"], 500),
        xytext=(cycle["start_dt"] - pd.Timedelta(minutes=15), 1200),
        arrowprops=dict(arrowstyle="->", color="#2ca02c", lw=1.5),
        fontweight="bold",
        fontsize=9,
    )
    ax.annotate(
        f"Water Heating Peak: {cycle['peak_power_w']:.0f} W",
        xy=(cycle["start_dt"] + pd.Timedelta(minutes=5), cycle["peak_power_w"]),
        xytext=(cycle["start_dt"] + pd.Timedelta(minutes=10), cycle["peak_power_w"] + 150),
        arrowprops=dict(arrowstyle="->", color="crimson", lw=1.5),
        fontweight="bold",
        fontsize=9,
    )
    ax.annotate(
        f"Cycle End: {cycle['end_dt'].strftime('%H:%M')}\nDuration: {cycle['duration_min']} min\nEnergy: {cycle['energy_wh']:.1f} Wh",
        xy=(cycle["end_dt"], 100),
        xytext=(cycle["end_dt"] + pd.Timedelta(minutes=3), 700),
        arrowprops=dict(arrowstyle="->", color="#2ca02c", lw=1.5),
        fontweight="bold",
        fontsize=9,
    )

    ax.set_title(
        f"House 1: Detailed Operating Cycle Anatomy (Duration: {cycle['duration_min']} min, Energy: {cycle['energy_wh']} Wh)",
        fontsize=12,
        fontweight="bold",
        pad=10,
    )
    ax.set_ylabel("Power (Watts)", fontsize=11)
    ax.set_xlabel("Time (UTC)", fontsize=11)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right")

    plt.tight_layout()
    out_path = output_dir / "detected_cycle_trace.png"
    plt.savefig(out_path, dpi=200)
    plt.close()
    LOGGER.info("Saved %s", out_path.name)
    return out_path


def plot_cross_household_comparison(
    cycles_df: pd.DataFrame,
    output_dir: Path = FIGURES_DIR,
) -> Path:
    """Plot 3: Cross-household distribution comparison of Duration, Peak Power, and Energy."""
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    palette = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f"]

    # 1. Duration
    sns.boxplot(
        data=cycles_df,
        x="household",
        y="duration_min",
        palette=palette,
        ax=axes[0],
        showmeans=True,
        meanprops={"marker": "D", "markerfacecolor": "white", "markeredgecolor": "black"},
    )
    axes[0].set_title("Cycle Duration Distribution", fontsize=11, fontweight="bold")
    axes[0].set_ylabel("Duration (minutes)", fontsize=10)
    axes[0].set_xlabel("")
    axes[0].grid(True, linestyle="--", alpha=0.5, axis="y")

    # 2. Peak Power
    sns.boxplot(
        data=cycles_df,
        x="household",
        y="peak_power_w",
        palette=palette,
        ax=axes[1],
        showmeans=True,
        meanprops={"marker": "D", "markerfacecolor": "white", "markeredgecolor": "black"},
    )
    axes[1].set_title("Cycle Peak Power Distribution", fontsize=11, fontweight="bold")
    axes[1].set_ylabel("Peak Power (Watts)", fontsize=10)
    axes[1].set_xlabel("")
    axes[1].grid(True, linestyle="--", alpha=0.5, axis="y")

    # 3. Energy Consumption
    sns.boxplot(
        data=cycles_df,
        x="household",
        y="energy_wh",
        palette=palette,
        ax=axes[2],
        showmeans=True,
        meanprops={"marker": "D", "markerfacecolor": "white", "markeredgecolor": "black"},
    )
    axes[2].set_title("Energy Consumption per Cycle", fontsize=11, fontweight="bold")
    axes[2].set_ylabel("Energy (Watt-hours)", fontsize=10)
    axes[2].set_xlabel("")
    axes[2].grid(True, linestyle="--", alpha=0.5, axis="y")

    plt.tight_layout()
    out_path = output_dir / "cross_household_cycle_comparison.png"
    plt.savefig(out_path, dpi=200)
    plt.close()
    LOGGER.info("Saved %s", out_path.name)
    return out_path


def plot_hourly_usage_profile(
    cycles_df: pd.DataFrame,
    output_dir: Path = FIGURES_DIR,
) -> Path:
    """Plot 4: Diurnal usage profiles (Cycle Starts vs Total Active Energy by Hour of Day)."""
    df = cycles_df.copy()
    df["start_dt"] = pd.to_datetime(df["start_time"])
    df["hour"] = df["start_dt"].dt.hour

    fig, axes = plt.subplots(1, 2, figsize=(15, 5))

    # A. Cycle Start Count by Hour
    hourly_counts = df.groupby(["hour", "household"]).size().unstack(fill_value=0)
    hourly_counts.plot(kind="bar", stacked=True, ax=axes[0], colormap="viridis", width=0.85)
    axes[0].set_title("Washing Machine Starts by Hour of Day (UTC)", fontsize=11, fontweight="bold")
    axes[0].set_xlabel("Hour of Day (0–23)", fontsize=10)
    axes[0].set_ylabel("Total Cycle Starts", fontsize=10)
    axes[0].grid(True, linestyle="--", alpha=0.5, axis="y")
    axes[0].legend(title="Household", fontsize=9)

    # B. Normalized Hourly Probability Density
    norm_hourly = hourly_counts.div(hourly_counts.sum(axis=0), axis=1)
    norm_hourly.plot(ax=axes[1], marker="o", linewidth=2.0)
    axes[1].set_title("Normalized Start Probability by Hour", fontsize=11, fontweight="bold")
    axes[1].set_xlabel("Hour of Day (0–23)", fontsize=10)
    axes[1].set_ylabel("Fraction of Total Starts", fontsize=10)
    axes[1].grid(True, linestyle="--", alpha=0.5)
    axes[1].set_xticks(range(0, 24, 2))
    axes[1].legend(title="Household", fontsize=9)

    plt.tight_layout()
    out_path = output_dir / "hourly_usage_profile.png"
    plt.savefig(out_path, dpi=200)
    plt.close()
    LOGGER.info("Saved %s", out_path.name)
    return out_path


def plot_day_of_week_usage(
    cycles_df: pd.DataFrame,
    output_dir: Path = FIGURES_DIR,
) -> Path:
    """Plot 5: Weekly usage patterns across Monday through Sunday."""
    df = cycles_df.copy()
    df["start_dt"] = pd.to_datetime(df["start_time"])
    df["day_name"] = df["start_dt"].dt.day_name()
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    fig, axes = plt.subplots(1, 2, figsize=(15, 5))

    # A. Total Cycles by Day of Week
    dow_counts = df.groupby(["day_name", "household"]).size().unstack(fill_value=0).reindex(day_order)
    dow_counts.plot(kind="bar", ax=axes[0], colormap="tab10", width=0.8)
    axes[0].set_title("Weekly Usage Frequency (Cycle Counts by Day)", fontsize=11, fontweight="bold")
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Cycle Count", fontsize=10)
    axes[0].grid(True, linestyle="--", alpha=0.5, axis="y")
    axes[0].tick_params(axis="x", rotation=30)
    axes[0].legend(title="Household")

    # B. Total Energy (kWh) by Day of Week
    dow_energy = df.groupby(["day_name", "household"])["energy_kwh"].sum().unstack(fill_value=0).reindex(day_order)
    dow_energy.plot(kind="bar", ax=axes[1], colormap="tab10", width=0.8)
    axes[1].set_title("Weekly Active Energy Consumption (kWh)", fontsize=11, fontweight="bold")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("Total Energy (kWh)", fontsize=10)
    axes[1].grid(True, linestyle="--", alpha=0.5, axis="y")
    axes[1].tick_params(axis="x", rotation=30)
    axes[1].legend(title="Household")

    plt.tight_layout()
    out_path = output_dir / "day_of_week_usage.png"
    plt.savefig(out_path, dpi=200)
    plt.close()
    LOGGER.info("Saved %s", out_path.name)
    return out_path


def plot_coverage_missingness_diagnostic(
    summary_df: pd.DataFrame,
    output_dir: Path = FIGURES_DIR,
) -> Path:
    """Plot 6: Data availability, missingness, standby, and true zero distribution across households."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # A. State fractions breakdown (Zero, Standby, Active, Missing)
    plot_df = summary_df.set_index("household")[["zero_pct", "standby_pct", "active_pct", "missing_pct"]]
    plot_df.columns = ["Observed Zero / Off (<1W)", "Standby (1–20W)", "Active Cycle (>=20W)", "Missing / Outage"]

    plot_df.plot(
        kind="barh",
        stacked=True,
        ax=axes[0],
        color=["#2b83ba", "#abdda4", "#fdae61", "#d7191c"],
        width=0.7,
    )
    axes[0].set_title("1-Minute Data Availability & Operating State Breakdown", fontsize=11, fontweight="bold")
    axes[0].set_xlabel("Percentage of Total Deployment Time (%)", fontsize=10)
    axes[0].set_xlim(0, 100)
    axes[0].grid(True, linestyle="--", alpha=0.5, axis="x")
    axes[0].legend(loc="lower right", fontsize=9)

    # B. Cycles per week vs Occupancy
    axes[1].scatter(
        summary_df["occupancy"],
        summary_df["cycles_per_week"],
        s=summary_df["median_energy_wh"] / 2.0,
        c=["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f"],
        alpha=0.8,
        edgecolors="black",
        linewidth=1.5,
    )
    for _, row in summary_df.iterrows():
        axes[1].annotate(
            f"{row['household']}\n({row['cycles_per_week']} c/wk)",
            (row["occupancy"], row["cycles_per_week"]),
            textcoords="offset points",
            xytext=(10, 5),
            fontsize=9,
            fontweight="bold",
        )
    axes[1].set_title("Weekly Cycle Frequency vs. Occupancy (Bubble size = Median Energy Wh)", fontsize=11, fontweight="bold")
    axes[1].set_xlabel("Household Occupancy (Persons)", fontsize=10)
    axes[1].set_ylabel("Weekly Cycle Frequency (Cycles / Week)", fontsize=10)
    axes[1].set_xlim(1.5, 4.5)
    axes[1].grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    out_path = output_dir / "coverage_missingness_diagnostic.png"
    plt.savefig(out_path, dpi=200)
    plt.close()
    LOGGER.info("Saved %s", out_path.name)
    return out_path


def run_pipeline() -> dict[str, Any]:
    """Execute end-to-end washing machine EDA pipeline and save deliverables."""
    setup_logging()
    LOGGER.info("Starting Washing Machine Disaggregation Analysis...")

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    series_wm_map: dict[str, pd.Series] = {}
    series_agg_map: dict[str, pd.Series] = {}
    household_summaries: list[dict[str, Any]] = []
    all_cycles_list: list[pd.DataFrame] = []

    for hid, reg in HOUSEHOLD_REGISTRY.items():
        hh_label = f"House {hid}"
        s_wm, s_agg, meta = load_and_resample_household(hid, reg["channel"])
        series_wm_map[hh_label] = s_wm
        series_agg_map[hh_label] = s_agg

        # Detect cycles with baseline parameters
        cycles_df = detect_washing_machine_cycles(
            s_wm,
            p_thresh=20.0,
            min_duration=15,
            max_gap=3,
            household_label=hh_label,
        )
        all_cycles_list.append(cycles_df)

        meta.update({
            "occupancy": reg["occupancy"],
            "house_type": reg["house_type"],
            "construction_year": reg["construction_year"],
            "detected_cycles": len(cycles_df),
            "cycles_per_week": round(len(cycles_df) / (meta["total_days"] / 7.0), 2),
            "median_duration_min": round(cycles_df["duration_min"].median(), 1) if len(cycles_df) > 0 else None,
            "mean_duration_min": round(cycles_df["duration_min"].mean(), 1) if len(cycles_df) > 0 else None,
            "median_peak_power_w": round(cycles_df["peak_power_w"].median(), 1) if len(cycles_df) > 0 else None,
            "median_mean_power_w": round(cycles_df["mean_power_w"].median(), 1) if len(cycles_df) > 0 else None,
            "median_energy_wh": round(cycles_df["energy_wh"].median(), 1) if len(cycles_df) > 0 else None,
            "mean_energy_wh": round(cycles_df["energy_wh"].mean(), 1) if len(cycles_df) > 0 else None,
            "total_energy_kwh": round(cycles_df["energy_kwh"].sum(), 2) if len(cycles_df) > 0 else 0.0,
        })
        household_summaries.append(meta)

    # Combine all cycle records
    combined_cycles_df = pd.concat(all_cycles_list, ignore_index=True)
    summary_df = pd.DataFrame(household_summaries)

    # Save tables to both results/ and results/tables/
    cycle_csv_primary = RESULTS_DIR / "washing_machine_cycles.csv"
    cycle_csv_tables = TABLES_DIR / "washing_machine_cycles.csv"
    combined_cycles_df.to_csv(cycle_csv_primary, index=False)
    combined_cycles_df.to_csv(cycle_csv_tables, index=False)
    LOGGER.info("Saved %s (%d total cycles)", cycle_csv_primary.name, len(combined_cycles_df))

    summary_csv_primary = RESULTS_DIR / "household_washing_machine_summary.csv"
    summary_csv_tables = TABLES_DIR / "household_washing_machine_summary.csv"
    summary_df.to_csv(summary_csv_primary, index=False)
    summary_df.to_csv(summary_csv_tables, index=False)
    LOGGER.info("Saved %s", summary_csv_primary.name)

    # Run Sensitivity Analysis
    sensitivity_df = run_sensitivity_analysis(series_wm_map)
    sensitivity_csv_primary = RESULTS_DIR / "washing_machine_sensitivity.csv"
    sensitivity_csv_tables = TABLES_DIR / "washing_machine_sensitivity.csv"
    sensitivity_df.to_csv(sensitivity_csv_primary, index=False)
    sensitivity_df.to_csv(sensitivity_csv_tables, index=False)
    LOGGER.info("Saved %s", sensitivity_csv_primary.name)

    # Generate the 6 deliverable figures
    p1 = plot_representative_24h(series_wm_map["House 1"], series_agg_map["House 1"], "House 1")
    p2 = plot_detected_cycle_trace(series_wm_map["House 1"], combined_cycles_df)
    p3 = plot_cross_household_comparison(combined_cycles_df)
    p4 = plot_hourly_usage_profile(combined_cycles_df)
    p5 = plot_day_of_week_usage(combined_cycles_df)
    p6 = plot_coverage_missingness_diagnostic(summary_df)

    LOGGER.info("Washing Machine EDA pipeline finished successfully.")
    return {
        "status": "SUCCESS",
        "total_cycles_detected": len(combined_cycles_df),
        "households_analyzed": len(summary_df),
        "tables": [str(cycle_csv_primary), str(summary_csv_primary), str(sensitivity_csv_primary)],
        "figures": [str(p1), str(p2), str(p3), str(p4), str(p5), str(p6)],
    }


def main() -> None:
    run_pipeline()


if __name__ == "__main__":
    main()
