"""
Disaggregation Model: Washing Machine Active Power from Aggregate Power.
REFIT Dataset (1-minute cleaned data).

This module implements:
1. Data loading and feature engineering (lags, leads, rolling statistics, calendar harmonics).
2. Leakage-resistant validation:
   - Chronological intra-household holdout (House 1: 75% train, 25% test).
   - Cross-household unseen domain test (Train: Houses 2 & 3, Test: House 1).
3. Baseline models:
   - Always-Off Baseline (predicts 0 W).
   - Heuristic Threshold Baseline (rule-based aggregate power detector).
4. Machine Learning model:
   - HistGradientBoostingRegressor with non-negative post-projection.
5. Standard NILM evaluation metrics:
   - MAE, RMSE, Normalized MAE (NMAE).
   - On/Off state classification metrics at 20 W threshold (Precision, Recall, F1).
   - Total energy tracking (Actual kWh, Predicted kWh, Relative Energy Error %).
6. Visualizations and diagnostic export.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, precision_recall_fscore_support

# Configure plotting style
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial"]
plt.rcParams["axes.edgecolor"] = "#cccccc"
plt.rcParams["axes.linewidth"] = 0.8

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("disaggregation_model")

# Constants
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "cleaned"
RESULTS_DIR = PROJECT_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
TABLES_DIR = RESULTS_DIR / "tables"

# Active threshold definition (agreed with Requirement 2 EDA)
ACTIVE_THRESHOLD_WATTS = 20.0


def load_house_data(house_id: int) -> pd.DataFrame:
    """Load cleaned 1-minute REFIT data for a specific household."""
    file_path = DATA_DIR / f"CLEAN_House{house_id}.csv"
    if not file_path.exists():
        raise FileNotFoundError(f"Missing cleaned data file: {file_path}")

    logger.info("Loading House %d from %s...", house_id, file_path.name)
    df = pd.read_csv(file_path)
    df["Time"] = pd.to_datetime(df["Time"], utc=True)
    df = df.sort_values("Time").reset_index(drop=True)

    # Validate appliance column mapping
    # House 1: Appliance5 is Washing Machine
    # House 2: Appliance2 is Washing Machine
    # House 3: Appliance6 is Washing Machine
    # House 5: Appliance3 is Washing Machine
    # House 20: Appliance4 is Washing Machine
    mapping = {1: "Appliance5", 2: "Appliance2", 3: "Appliance6", 5: "Appliance3", 20: "Appliance4"}
    wm_col = mapping.get(house_id)
    if wm_col not in df.columns:
        raise ValueError(f"Washing machine column {wm_col} not found in House {house_id}")

    sub = df[["Time", "Aggregate", wm_col]].copy()
    sub.rename(columns={wm_col: "WashingMachine"}, inplace=True)

    # Ensure regular 1-minute grid
    sub = sub.set_index("Time").resample("1min").mean()
    # Forward-fill short missing gaps <= 5 min, then drop remaining NaNs
    sub = sub.ffill(limit=5).dropna().reset_index()

    # Enforce non-negative physical values
    sub["Aggregate"] = sub["Aggregate"].clip(lower=0.0)
    sub["WashingMachine"] = sub["WashingMachine"].clip(lower=0.0)

    logger.info("House %d loaded: %d rows from %s to %s",
                house_id, len(sub), sub["Time"].min().date(), sub["Time"].max().date())
    return sub


def extract_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Extract causal and near-real-time window features from aggregate power trace.
    Features:
    - Pointwise: Aggregate power at t
    - Window context: Lags (t-15 to t-1) and Leads (t+1 to t+15)
    - Rolling window statistics: Mean, Std, Max (5 min, 15 min, 30 min)
    - Diurnal / Calendar features: Sine/Cosine hour-of-day, Sine/Cosine day-of-week
    """
    feat = pd.DataFrame(index=df.index)
    agg = df["Aggregate"]

    # Pointwise
    feat["agg_t"] = agg

    # Lags (past context)
    for lag in [1, 2, 3, 5, 10, 15]:
        feat[f"agg_lag_{lag}"] = agg.shift(lag)

    # Leads (future context - valid for batch disaggregation with 15-min latency buffer)
    for lead in [1, 2, 3, 5, 10, 15]:
        feat[f"agg_lead_{lead}"] = agg.shift(-lead)

    # Differences / derivatives (transient spikes)
    feat["agg_diff_1"] = agg.diff(1)
    feat["agg_diff_5"] = agg.diff(5)

    # Rolling statistics (using forward & backward centered or rolling past)
    # Using past rolling windows to preserve causal integrity where possible
    feat["agg_roll_mean_5"] = agg.rolling(window=5, min_periods=1).mean()
    feat["agg_roll_mean_15"] = agg.rolling(window=15, min_periods=1).mean()
    feat["agg_roll_mean_30"] = agg.rolling(window=30, min_periods=1).mean()

    feat["agg_roll_std_15"] = agg.rolling(window=15, min_periods=1).std().fillna(0.0)
    feat["agg_roll_std_30"] = agg.rolling(window=30, min_periods=1).std().fillna(0.0)

    feat["agg_roll_max_15"] = agg.rolling(window=15, min_periods=1).max()
    feat["agg_roll_max_30"] = agg.rolling(window=30, min_periods=1).max()

    # Time harmonics
    hours = df["Time"].dt.hour + df["Time"].dt.minute / 60.0
    feat["sin_hour"] = np.sin(2 * np.pi * hours / 24.0)
    feat["cos_hour"] = np.cos(2 * np.pi * hours / 24.0)

    dow = df["Time"].dt.dayofweek
    feat["sin_dow"] = np.sin(2 * np.pi * dow / 7.0)
    feat["cos_dow"] = np.cos(2 * np.pi * dow / 7.0)

    # Handle boundary NaNs created by shifts
    feat = feat.bfill().ffill()

    target = df["WashingMachine"].copy()
    return feat, target


class HeuristicThresholdBaseline:
    """
    Domain-heuristic baseline:
    Predicts median active power when aggregate power crosses typical WM heating threshold.
    Fitted strictly on training data statistics.
    """
    def __init__(self, threshold_power: float = 1800.0):
        self.threshold_power = threshold_power
        self.active_median_ = 0.0

    def fit(self, X: pd.DataFrame, y: pd.Series):
        active_vals = y[y >= ACTIVE_THRESHOLD_WATTS]
        if len(active_vals) > 0:
            self.active_median_ = float(active_vals.median())
        else:
            self.active_median_ = 200.0
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        agg = X["agg_t"].to_numpy()
        preds = np.where(agg >= self.threshold_power, self.active_median_, 0.0)
        return preds


def compute_nilm_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Compute comprehensive NILM regression, classification, and energy metrics."""
    # Ensure non-negative predictions
    y_pred = np.clip(y_pred, 0.0, None)

    # 1. Regression metrics (Power in Watts)
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    sum_true = float(np.sum(y_true))
    nmae = float(np.sum(np.abs(y_true - y_pred)) / sum_true) if sum_true > 0 else 0.0

    # 2. State classification metrics (Active >= 20 W)
    y_true_binary = (y_true >= ACTIVE_THRESHOLD_WATTS).astype(int)
    y_pred_binary = (y_pred >= ACTIVE_THRESHOLD_WATTS).astype(int)

    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true_binary, y_pred_binary, average="binary", zero_division=0
    )

    # 3. Energy metrics (1-minute resolution -> 1 W-min = 1/60 Wh = 1/60000 kWh)
    energy_true_kwh = float(np.sum(y_true) / 60000.0)
    energy_pred_kwh = float(np.sum(y_pred) / 60000.0)
    relative_energy_error_pct = (
        float(np.abs(energy_pred_kwh - energy_true_kwh) / energy_true_kwh * 100.0)
        if energy_true_kwh > 0 else 0.0
    )

    return {
        "MAE_Watts": round(mae, 2),
        "RMSE_Watts": round(rmse, 2),
        "NMAE": round(nmae, 4),
        "Precision": round(float(precision), 4),
        "Recall": round(float(recall), 4),
        "F1_Score": round(float(f1), 4),
        "Energy_True_kWh": round(energy_true_kwh, 2),
        "Energy_Pred_kWh": round(energy_pred_kwh, 2),
        "Energy_Error_Pct": round(relative_energy_error_pct, 2),
    }


def run_pipeline() -> Dict[str, Any]:
    """Execute complete disaggregation training, evaluation, and plotting pipeline."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # PART 1: Intra-Household Chronological Holdout (House 1)
    # =========================================================================
    logger.info("=== EVALUATION 1: Intra-Household Chronological Split (House 1) ===")
    df_h1 = load_house_data(1)
    X_h1, y_h1 = extract_features(df_h1)

    # 75% train, 25% test chronological split
    n_samples = len(df_h1)
    split_idx = int(0.75 * n_samples)
    cutoff_time = df_h1["Time"].iloc[split_idx]

    logger.info("Chronological Split: %d Train rows (to %s), %d Test rows (from %s)",
                split_idx, cutoff_time, n_samples - split_idx, cutoff_time)

    X_train_h1, X_test_h1 = X_h1.iloc[:split_idx], X_h1.iloc[split_idx:]
    y_train_h1, y_test_h1 = y_h1.iloc[:split_idx], y_h1.iloc[split_idx:]
    t_test_h1 = df_h1["Time"].iloc[split_idx:]

    # Baselines
    # Always-off
    y_pred_off = np.zeros(len(y_test_h1), dtype=float)
    metrics_off = compute_nilm_metrics(y_test_h1.to_numpy(), y_pred_off)

    # Heuristic Threshold
    heuristic = HeuristicThresholdBaseline(threshold_power=1800.0)
    heuristic.fit(X_train_h1, y_train_h1)
    y_pred_heur = heuristic.predict(X_test_h1)
    metrics_heur = compute_nilm_metrics(y_test_h1.to_numpy(), y_pred_heur)

    # HistGradientBoostingRegressor
    logger.info("Training HistGradientBoostingRegressor on House 1 (75%)...")
    gbdt_h1 = HistGradientBoostingRegressor(
        max_iter=150,
        max_depth=6,
        min_samples_leaf=50,
        learning_rate=0.08,
        random_state=42
    )
    gbdt_h1.fit(X_train_h1, y_train_h1)
    y_pred_gbdt = np.clip(gbdt_h1.predict(X_test_h1), 0.0, None)
    metrics_gbdt = compute_nilm_metrics(y_test_h1.to_numpy(), y_pred_gbdt)

    logger.info("House 1 Test Results:")
    logger.info("  Always-Off: MAE=%.2f W, RMSE=%.2f W, F1=%.3f, Energy Err=%.1f%%",
                metrics_off["MAE_Watts"], metrics_off["RMSE_Watts"], metrics_off["F1_Score"], metrics_off["Energy_Error_Pct"])
    logger.info("  Heuristic : MAE=%.2f W, RMSE=%.2f W, F1=%.3f, Energy Err=%.1f%%",
                metrics_heur["MAE_Watts"], metrics_heur["RMSE_Watts"], metrics_heur["F1_Score"], metrics_heur["Energy_Error_Pct"])
    logger.info("  GBDT Model: MAE=%.2f W, RMSE=%.2f W, F1=%.3f, Energy Err=%.1f%%",
                metrics_gbdt["MAE_Watts"], metrics_gbdt["RMSE_Watts"], metrics_gbdt["F1_Score"], metrics_gbdt["Energy_Error_Pct"])

    # =========================================================================
    # PART 2: Cross-Household Generalization (Train House 2+3 -> Test House 1)
    # =========================================================================
    logger.info("=== EVALUATION 2: Cross-Household Domain Transfer ===")
    df_h2 = load_house_data(2)
    df_h3 = load_house_data(3)

    X_h2, y_h2 = extract_features(df_h2)
    X_h3, y_h3 = extract_features(df_h3)

    X_cross_train = pd.concat([X_h2, X_h3], axis=0, ignore_index=True)
    y_cross_train = pd.concat([y_h2, y_h3], axis=0, ignore_index=True)

    logger.info("Cross-House Train Set: %d rows (H2 + H3). Testing on 100%% Unseen House 1 (%d rows)...",
                len(X_cross_train), len(X_h1))

    gbdt_cross = HistGradientBoostingRegressor(
        max_iter=150,
        max_depth=6,
        min_samples_leaf=100,
        learning_rate=0.08,
        random_state=42
    )
    gbdt_cross.fit(X_cross_train, y_cross_train)
    y_pred_cross = np.clip(gbdt_cross.predict(X_h1), 0.0, None)
    metrics_cross = compute_nilm_metrics(y_h1.to_numpy(), y_pred_cross)
    metrics_cross_off = compute_nilm_metrics(y_h1.to_numpy(), np.zeros(len(y_h1)))

    logger.info("Unseen House 1 Generalization:")
    logger.info("  Cross Always-Off: MAE=%.2f W, RMSE=%.2f W, F1=%.3f",
                metrics_cross_off["MAE_Watts"], metrics_cross_off["RMSE_Watts"], metrics_cross_off["F1_Score"])
    logger.info("  Cross GBDT Model: MAE=%.2f W, RMSE=%.2f W, F1=%.3f, Energy Err=%.1f%%",
                metrics_cross["MAE_Watts"], metrics_cross["RMSE_Watts"], metrics_cross["F1_Score"], metrics_cross["Energy_Error_Pct"])

    # =========================================================================
    # PART 3: Save Prediction Samples & Metrics Tables
    # =========================================================================
    # Metrics Table
    summary_df = pd.DataFrame([
        {"Experiment": "Intra-House (House 1)", "Model": "Always-Off Baseline", **metrics_off},
        {"Experiment": "Intra-House (House 1)", "Model": "Heuristic Threshold (1.8kW)", **metrics_heur},
        {"Experiment": "Intra-House (House 1)", "Model": "HistGradientBoosting", **metrics_gbdt},
        {"Experiment": "Cross-House (H2+3 -> H1)", "Model": "Always-Off Baseline", **metrics_cross_off},
        {"Experiment": "Cross-House (H2+3 -> H1)", "Model": "HistGradientBoosting", **metrics_cross},
    ])
    summary_df.to_csv(TABLES_DIR / "disaggregation_metrics.csv", index=False)
    summary_df.to_csv(RESULTS_DIR / "disaggregation_metrics.csv", index=False)

    with open(RESULTS_DIR / "disaggregation_metrics.json", "w") as f:
        json.dump(summary_df.to_dict(orient="records"), f, indent=2)

    # Save test predictions trace for House 1
    test_preds_df = pd.DataFrame({
        "Time": t_test_h1.values,
        "Aggregate_W": X_test_h1["agg_t"].values,
        "WashingMachine_Actual_W": y_test_h1.values,
        "Predicted_AlwaysOff_W": y_pred_off,
        "Predicted_Heuristic_W": y_pred_heur,
        "Predicted_GBDT_W": np.round(y_pred_gbdt, 1),
    })
    test_preds_df.to_csv(RESULTS_DIR / "disaggregation_test_predictions.csv", index=False)
    logger.info("Saved predictions and metrics to %s", RESULTS_DIR)

    # =========================================================================
    # PART 4: Generate All Deliverable Figures
    # =========================================================================
    logger.info("Generating deliverable diagnostic figures...")

    # 1. Actual vs Predicted Trace (Representative 3-day active window in test period)
    # Find window with multiple prominent cycles
    active_mask = (test_preds_df["WashingMachine_Actual_W"] > 500.0)
    if active_mask.any():
        idx_mid = active_mask.idxmax()
        start_idx = max(0, idx_mid - 720) # 12 hours before
        end_idx = min(len(test_preds_df), start_idx + 2880) # 48 hours total
        sub_trace = test_preds_df.iloc[start_idx:end_idx]
    else:
        sub_trace = test_preds_df.iloc[:2880]

    fig, axes = plt.subplots(3, 1, figsize=(14, 9), sharex=True)

    axes[0].plot(sub_trace["Time"], sub_trace["Aggregate_W"], color="#4a5568", lw=1.2, label="Aggregate Household Power")
    axes[0].set_ylabel("Power (W)", fontweight="bold")
    axes[0].set_title("House 1 Disaggregation Test Period: Aggregate Power vs Ground Truth & Model Predictions",
                      fontweight="bold", fontsize=12)
    axes[0].legend(loc="upper right", frameon=True)
    axes[0].grid(True, linestyle="--", alpha=0.5)

    axes[1].plot(sub_trace["Time"], sub_trace["WashingMachine_Actual_W"], color="#2b6cb0", lw=1.5, label="Actual Washing Machine (Ground Truth)")
    axes[1].plot(sub_trace["Time"], sub_trace["Predicted_GBDT_W"], color="#dd6b20", lw=1.3, alpha=0.9, label="Predicted (HistGradientBoosting)")
    axes[1].set_ylabel("Power (W)", fontweight="bold")
    axes[1].set_title("Ground Truth vs GBDT Disaggregation Model", fontweight="bold", fontsize=11)
    axes[1].legend(loc="upper right", frameon=True)
    axes[1].grid(True, linestyle="--", alpha=0.5)

    axes[2].plot(sub_trace["Time"], sub_trace["WashingMachine_Actual_W"], color="#2b6cb0", lw=1.2, label="Actual Washing Machine")
    axes[2].plot(sub_trace["Time"], sub_trace["Predicted_Heuristic_W"], color="#805ad5", lw=1.2, ls="--", label="Heuristic Baseline (>=1.8 kW)")
    axes[2].set_ylabel("Power (W)", fontweight="bold")
    axes[2].set_title("Ground Truth vs Heuristic Threshold Baseline", fontweight="bold", fontsize=11)
    axes[2].legend(loc="upper right", frameon=True)
    axes[2].grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "disaggregation_actual_vs_predicted.png", dpi=180)
    plt.close(fig)

    # 2. Residual Distribution and Error Analysis
    residuals = y_test_h1.to_numpy() - y_pred_gbdt
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Error distribution
    ax1.hist(residuals, bins=100, range=(-200, 200), color="#3182ce", edgecolor="white", alpha=0.85)
    ax1.axvline(0, color="red", linestyle="--", lw=1.5, label=f"Mean Error: {np.mean(residuals):.2f} W")
    ax1.set_xlabel("Residual Error (Actual - Predicted, W)", fontweight="bold")
    ax1.set_ylabel("Minute Count", fontweight="bold")
    ax1.set_title("Residual Error Distribution (Zoomed [-200W, +200W])", fontweight="bold")
    ax1.legend(frameon=True)
    ax1.grid(True, linestyle="--", alpha=0.5)

    # Residual vs Aggregate Power
    # Sample 10,000 points to keep plot crisp and light
    sample_mask = np.random.RandomState(42).choice(len(residuals), size=min(10000, len(residuals)), replace=False)
    ax2.scatter(X_test_h1["agg_t"].iloc[sample_mask], residuals[sample_mask],
                alpha=0.25, s=12, color="#dd6b20", edgecolors="none")
    ax2.axhline(0, color="black", linestyle="-", lw=1)
    ax2.set_xlabel("Aggregate Power (W)", fontweight="bold")
    ax2.set_ylabel("Residual (Actual - Predicted, W)", fontweight="bold")
    ax2.set_title("Disaggregation Residuals vs Household Aggregate Load", fontweight="bold")
    ax2.set_xlim(0, 5000)
    ax2.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "disaggregation_residuals.png", dpi=180)
    plt.close(fig)

    # 3. Model & Baseline Comparison Bar Chart
    fig, ((bx1, bx2), (bx3, bx4)) = plt.subplots(2, 2, figsize=(12, 8))
    models = ["Always-Off", "Heuristic (1.8kW)", "GBDT Model"]
    mae_vals = [metrics_off["MAE_Watts"], metrics_heur["MAE_Watts"], metrics_gbdt["MAE_Watts"]]
    rmse_vals = [metrics_off["RMSE_Watts"], metrics_heur["RMSE_Watts"], metrics_gbdt["RMSE_Watts"]]
    f1_vals = [metrics_off["F1_Score"], metrics_heur["F1_Score"], metrics_gbdt["F1_Score"]]
    nmae_vals = [metrics_off["NMAE"], metrics_heur["NMAE"], metrics_gbdt["NMAE"]]

    colors = ["#718096", "#9f7aea", "#38a169"]

    bx1.bar(models, mae_vals, color=colors, edgecolor="black", alpha=0.85)
    bx1.set_title("Mean Absolute Error (Lower is Better)", fontweight="bold")
    bx1.set_ylabel("MAE (Watts)")
    for i, v in enumerate(mae_vals):
        bx1.text(i, v + 0.5, f"{v:.1f}W", ha="center", fontweight="bold")

    bx2.bar(models, rmse_vals, color=colors, edgecolor="black", alpha=0.85)
    bx2.set_title("Root Mean Squared Error (Lower is Better)", fontweight="bold")
    bx2.set_ylabel("RMSE (Watts)")
    for i, v in enumerate(rmse_vals):
        bx2.text(i, v + 2.0, f"{v:.1f}W", ha="center", fontweight="bold")

    bx3.bar(models, f1_vals, color=colors, edgecolor="black", alpha=0.85)
    bx3.set_title("Active State F1-Score (Higher is Better, Threshold >= 20W)", fontweight="bold")
    bx3.set_ylabel("F1 Score")
    bx3.set_ylim(0, 0.6)
    for i, v in enumerate(f1_vals):
        bx3.text(i, v + 0.015, f"{v:.3f}", ha="center", fontweight="bold")

    bx4.bar(models, nmae_vals, color=colors, edgecolor="black", alpha=0.85)
    bx4.set_title("Normalized MAE (NMAE) (Lower is Better)", fontweight="bold")
    bx4.set_ylabel("NMAE (Ratio)")
    for i, v in enumerate(nmae_vals):
        bx4.text(i, v + 0.05, f"{v:.2f}", ha="center", fontweight="bold")

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "disaggregation_baseline_comparison.png", dpi=180)
    plt.close(fig)

    # 4. Failure Modes & Diagnostic Case Studies
    # Find distinct failure scenarios in test set:
    # (a) False Positive: WM is OFF (0W), Aggregate is HIGH (>2000W), GBDT predicts >200W
    # (b) False Negative / Low Prediction: WM is ON (>500W), GBDT predicts <100W
    # (c) Accurate Detection: WM is ON (>1000W) and GBDT predicts >800W
    fp_mask = (test_preds_df["WashingMachine_Actual_W"] < 5.0) & (test_preds_df["Aggregate_W"] > 2200.0) & (test_preds_df["Predicted_GBDT_W"] > 150.0)
    fn_mask = (test_preds_df["WashingMachine_Actual_W"] > 800.0) & (test_preds_df["Predicted_GBDT_W"] < 300.0)
    tp_mask = (test_preds_df["WashingMachine_Actual_W"] > 1500.0) & (test_preds_df["Predicted_GBDT_W"] > 1200.0)

    fig, axes = plt.subplots(3, 1, figsize=(13, 10))

    # Panel A: False Positive (Kettle/Cooker interference)
    if fp_mask.any():
        loc = int(fp_mask.idxmax())
        win = test_preds_df.iloc[max(0, loc - 40): min(len(test_preds_df), loc + 50)]
        axes[0].plot(win["Time"], win["Aggregate_W"], label="Aggregate Power", color="#4a5568", lw=1.2)
        axes[0].plot(win["Time"], win["WashingMachine_Actual_W"], label="Actual WM (0W)", color="#2b6cb0", lw=2.0)
        axes[0].plot(win["Time"], win["Predicted_GBDT_W"], label="Predicted WM (False Positive)", color="#e53e3e", lw=1.8, ls="--")
        axes[0].set_title("Failure Case A: False Positive from Concurrent High-Power Appliance (Kettle / Oven)", fontweight="bold")
        axes[0].set_ylabel("Power (W)")
        axes[0].legend(loc="upper right")
        axes[0].grid(True, linestyle="--", alpha=0.5)

    # Panel B: False Negative / Underestimation
    if fn_mask.any():
        loc = int(fn_mask.idxmax())
        win = test_preds_df.iloc[max(0, loc - 30): min(len(test_preds_df), loc + 60)]
        axes[1].plot(win["Time"], win["Aggregate_W"], label="Aggregate Power", color="#4a5568", lw=1.2)
        axes[1].plot(win["Time"], win["WashingMachine_Actual_W"], label="Actual WM", color="#2b6cb0", lw=2.0)
        axes[1].plot(win["Time"], win["Predicted_GBDT_W"], label="Predicted WM (Underestimation)", color="#dd6b20", lw=1.8, ls="--")
        axes[1].set_title("Failure Case B: Heating Peak Attenuation / Missed Cycle Start", fontweight="bold")
        axes[1].set_ylabel("Power (W)")
        axes[1].legend(loc="upper right")
        axes[1].grid(True, linestyle="--", alpha=0.5)

    # Panel C: Success Case (True Positive Cycle)
    if tp_mask.any():
        loc = int(tp_mask.idxmax())
        win = test_preds_df.iloc[max(0, loc - 30): min(len(test_preds_df), loc + 90)]
        axes[2].plot(win["Time"], win["Aggregate_W"], label="Aggregate Power", color="#4a5568", lw=1.2)
        axes[2].plot(win["Time"], win["WashingMachine_Actual_W"], label="Actual WM", color="#2b6cb0", lw=2.0)
        axes[2].plot(win["Time"], win["Predicted_GBDT_W"], label="Predicted WM (Accurate Trace)", color="#38a169", lw=1.8)
        axes[2].set_title("Success Case C: Clean Cycle Disaggregation (Heating Spike & Wash Phase Correctly Captured)", fontweight="bold")
        axes[2].set_ylabel("Power (W)")
        axes[2].legend(loc="upper right")
        axes[2].grid(True, linestyle="--", alpha=0.5)
    if tp_mask.any():
        tp_idx = tp_mask.idxmax()
        loc = test_preds_df.index.get_loc(tp_idx)
        win = test_preds_df.iloc[max(0, loc - 30): min(len(test_preds_df), loc + 90)]
        axes[2].plot(win["Time"], win["Aggregate_W"], label="Aggregate Power", color="#4a5568", lw=1.2)
        axes[2].plot(win["Time"], win["WashingMachine_Actual_W"], label="Actual WM", color="#2b6cb0", lw=2.0)
        axes[2].plot(win["Time"], win["Predicted_GBDT_W"], label="Predicted WM (Accurate Trace)", color="#38a169", lw=1.8)
        axes[2].set_title("Success Case C: Clean Cycle Disaggregation (Heating Spike & Wash Phase Correctly Captured)", fontweight="bold")
        axes[2].set_ylabel("Power (W)")
        axes[2].legend(loc="upper right")
        axes[2].grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "disaggregation_failure_cases.png", dpi=180)
    plt.close(fig)

    logger.info("Pipeline execution complete! Deliverables saved in results/.")
    return {
        "intra_house": {
            "always_off": metrics_off,
            "heuristic": metrics_heur,
            "gbdt": metrics_gbdt,
        },
        "cross_house": {
            "always_off": metrics_cross_off,
            "gbdt": metrics_cross,
        }
    }


if __name__ == "__main__":
    run_pipeline()
