# Utility Strategic Recommendation & Section 4 Evaluation
## Non-Intrusive Load Monitoring (NILM) for Residential Demand-Side Flexibility

**Target Audience:** Distribution Network Operator (DNO) & Retail Energy Supplier Executive Committee  
**Prepared by:** Senior Energy Analytics Consultant & Utility Product Lead  
**Evidence Base:** Empirical Analysis of the Official Cleaned REFIT Dataset (Houses 1, 2, 3, 5, 20) & Gradient-Boosted Machine Learning Disaggregation Benchmark  
**Date:** November 2026  
**Status:** Strategic Advisory, Pilot Specification & Section 4 Assessment  

---

## Part 1: Executive Summary & Strategic Decision Gate

### 1. Executive Recommendation: CONDITIONAL GO FOR A 500-CUSTOMER PILOT
We recommend that the utility innovation and flexibility team authorize a **targeted, voluntary 500-customer residential pilot** utilizing 1-minute smart-meter NILM disaggregation for washing machines. 

We advise **against** deploying automated disaggregation as a standalone billing mechanism or hard automated direct-load-control service today. While our Gradient-Boosted Decision Tree (GBDT) model achieves an operational active recall of **85.50%** and an energy estimation error of just **12.55%** on House 1 (and **2.53%** on unseen homes), its 1-minute instantaneous precision is **28.03%** due to false positives from concurrent high-power resistive loads (electric kettles, hobs, ovens). Consequently, NILM must be positioned as an **informational nudging and voluntary peak-shifting service** paired with Time-of-Use (ToU) tariffs.

### 2. Strategic Go/No-Go Decision Gate

| Decision Milestone | Required Gate Metric | Action if Passed | Action if Failed |
|---|---|---|---|
| **Phase 1: Edge Validation** | Sub-metered IAM verification on 30 homes achieves $\ge 75\%$ Recall, $\le 20\%$ Energy Error | Proceed to 500-home customer pilot | Re-train model with 15-minute aggregated features |
| **Phase 2: Customer Pilot** | $\ge 20\%$ peak cycle shift, customer opt-out $< 10\%$ | Commercial roll-out to flexible tariff customers | Restrict NILM to aggregate energy disaggregation reports |

---

## Part 2: Section 4 Comprehensive Evaluation

### A. Practical Energy-Saving / Customer-Insight Opportunity: Voluntary Peak-to-Solar Laundry Shifting

#### 1. Observed Evidence Supporting the Opportunity
Across 3,004 days of monitoring and 2,509 verified washing machine cycles in REFIT Houses 1, 2, 3, 5, and 20:
- **Diurnal Usage Profile:** **62.4% of cycles are naturally initiated between 08:00 and 13:00 UTC**. Only **4.2%** occur during the system evening peak (16:30–19:30 UTC), and night-time operation (00:00–05:00 UTC) is negligible.
- **Physical Invariants:** Water-heating immersion elements universally draw **1,900 W – 2,400 W** across all homes, creating substantial transient localized network demand.
- **Flexibility Potential:** Domestic laundry routines exhibit high discretionary flexibility; occupants do not require immediate laundry completion during peak hours.

#### 2. Intended Customer or Utility User
- **Utility Users:** Distribution System Operator (DSO) constraint managers seeking localized substation peak reduction, and retail energy supplier trading desks seeking to minimize wholesale peak imbalance charges.
- **End Customers:** Residential smart-meter bill-payers subscribed to dynamic Time-of-Use (ToU) tariffs (e.g., Octopus Agile/Go) or households with rooftop solar PV looking to maximize self-consumption.

#### 3. Proposed Pilot & Customer Communication Approach
- **Cohort:** 500 consented dual-fuel residential smart-meter customers in a distribution constraint zone.
- **Communication:** Gentle, non-punitive mobile app notifications and weekly email summaries:
  - *"Sun's out! Midday solar window (10:00–14:00) offers low-cost laundry today."*
  - *"Did you run a laundry cycle around 11 AM? Shifting it away from 17:00–19:00 saved ~25p on your flexible tariff."*
- Nudges are framed probabilistically to maintain high trust despite the model's 28% instantaneous precision.

#### 4. Control or Comparison Group (RCT Setup)
- **Randomized Controlled Trial (RCT):** 
  - **Treatment Cohort ($N = 250$):** Receives personalized appliance-level disaggregation feedback, solar-alignment nudges, and peak-avoidance savings notifications.
  - **Control Cohort ($N = 250$):** Receives standard whole-home smart-meter displays and ToU price signals without appliance-level disaggregation insights.

#### 5. Primary and Secondary Success Metrics
- **Primary Metric:** Relative reduction in the proportion of washing-machine cycles initiated during peak tariff hours (16:30–19:30 UTC) in the treatment cohort compared to control ($\ge 20\%$ target).
- **Secondary Metrics:**
  - Participant opt-out rate ($< 10\%$).
  - Net monthly bill savings per participant (£4.00–£8.00/month).
  - Peak-hour feeder transformer load relief (kW).
  - Disaggregation model energy tracking accuracy within $\pm 15\%$ against physical validation plugs.

#### 6. Baseline and Evaluation Time Horizons
- **Pre-Pilot Baseline Period:** 90 days of continuous smart-meter monitoring prior to notification rollout to establish household-specific habitual schedules.
- **Post-Pilot Evaluation Period:** 6 months of active intervention covering both summer (solar alignment) and winter (peak constraint) grid conditions.

#### 7. Measuring Energy Reduction Separately from Load Shifting
- **Load Shifting:** Measured by calculating the shift in cycle start timestamp distribution across tariff bins without expecting thermodynamic kWh reduction:
  $$\Delta \text{Peak Share} = \frac{\text{Cycles}_{\text{Peak}}^{\text{Post}}}{\text{Cycles}_{\text{Total}}^{\text{Post}}} - \frac{\text{Cycles}_{\text{Peak}}^{\text{Pre}}}{\text{Cycles}_{\text{Total}}^{\text{Pre}}}$$
- **Energy Reduction:** Measured by tracking total cycle energy consumption (Wh/cycle). A 40°C wash uses ~0.4 kWh regardless of timing; true energy conservation is achieved only when customers switch to eco/30°C cycles (reducing Wh/cycle by 30–50%). Total appliance kWh is tracked independently of hour-of-day.

#### 8. Confounders, Risks, Privacy & Stop Conditions
- **Confounders:** Weather extremes, seasonal holiday periods, school vacations, and macroeconomic inflation. Controlled via Difference-in-Differences (DiD) regression against the control cohort.
- **Rebound Peak Risk:** Automated timer synchronization could cause thousands of machines to fire simultaneously at 23:00 when off-peak rates start, creating an artificial secondary substation spike. Mitigated by staggered customer notification windows.
- **Privacy Safeguards:** High-frequency data processed on-device (edge); telemetry transmissions limited to daily kWh summaries under explicit GDPR/DPDP informed consent.
- **Stop Conditions:** The pilot will be terminated immediately if:
  1. Participant opt-out exceeds 15%.
  2. False-alarm complaint rate exceeds 5%.
  3. Local distribution transformer experiences unmanaged secondary rebound peaks.

#### 9. Results Justifying Full-Scale Programme Rollout
- A statistically significant $\ge 20\%$ reduction in peak-hour laundry starts.
- Treatment group customer satisfaction $\ge 75\%$.
- Positive net economic benefit per customer after software licensing and cloud infrastructure costs.

---

### B. Limitations and Generalisation Matrix

| # | Limitation Domain | Likely Effect | How Tested | Realistic Mitigation |
|---|---|---|---|---|
| **1** | **Overlapping Signatures & Non-Identifiability** | Kettles, hobs, and ovens (2–3 kW) mimic the 2 kW water-heating plateau, causing false positives. | Evaluate false-positive rate during known cooking hours (17:00–19:00). | Add 15-min lead window context and rolling std features to verify motor agitation. |
| **2** | **Unmonitored Loads & Baseline Drift** | Unmonitored baseline loads (fridge, computers) reduce SNR, masking low-power motor pulses (80–150 W). | Compare residual distribution variance against baseline aggregate power levels. | Apply non-negative post-projection $\hat{y} = \max(0, \hat{y})$ and hierarchical 2-stage gating. |
| **3** | **Missing Intervals & Outages** | Extended telemetry dropouts truncate active cycles and corrupt rolling feature state buffers. | Stress-test pipeline with synthetic missing blocks of 5, 15, and 60 minutes. | Forward-fill short gaps ($\le 5$ min); mask extended outages and reset buffer windows. |
| **4** | **Cross-Household Load Diversity** | Differing wash habits (House 1 runs 33-min washes vs. House 2 running 95-min washes) degrade zero-shot transfer. | Benchmark model trained on Houses 2 & 3 on 100% unseen House 1. | Normalise input load by dwelling baseload; employ transfer fine-tuning with user prompts. |
| **5** | **Event-Detection Threshold Sensitivity** | Standby electronics (3 W in House 5) cause false continuous activation if threshold is $< 20\text{ W}$. | Run sensitivity grid varying $P_{\text{thresh}}$ from 5 W to 50 W across 5 homes. | Adopt physics-grounded 20 W threshold combined with 3-minute gap merging ($G=3$). |
| **6** | **Validation Design & Leakage Risk** | Random train/test splits cause severe lookahead leakage due to autocorrelation across cycle minutes. | Compare random split performance (overfitted) against strict chronological holdout. | Enforce strict chronological holdout and cross-household leave-one-out validation. |
| **7** | **False Positives & Energy Error** | Instantaneous precision caps at ~28%, yielding over-allocation during high-load aggregate cooking events. | Compute precision, recall, F1, and relative total energy error (%) on test data. | Evaluate energy on multi-day horizons (where error drops to 12.55% on H1, 2.53% on unseen). |
| **8** | **Small UK Dataset Sample Size** | 20 UK homes do not represent full socio-demographic diversity or commercial laundry appliances. | Evaluate performance variance across detached, semi-detached, and terraced houses. | Re-calibrate model against larger smart-meter populations (e.g., Low Carbon London). |
| **9** | **UK-to-India Transferability** | Indian washers are cold-fill top-loaders (200–400 W motor only); 2 kW heating signature is completely absent. | Run UK model on Indian smart-meter traces (expected failure to detect heating spikes). | Re-target Indian NILM algorithms toward air conditioners, geysers, and water pumps. |
| **10**| **Privacy & Routine Fingerprinting** | Appliance traces reveal sleep/wake routines, occupancy, and lifestyle patterns. | Audit inferred occupancy against ground-truth diary logs. | Execute inference locally on edge gateways; transmit only anonymized daily energy metrics. |

---

### C. Technical Analysis: 15-Minute and 30-Minute Smart-Meter Data

Standard utility smart meters (such as UK SMETS2 or Indian RDSS AMI) record aggregate active energy averaged over 15-minute or 30-minute integration periods rather than streaming 1-minute power traces. A 15-minute to 25-minute washing-machine water-heating surge of 2,300 W represents approximately 0.58 to 0.77 kWh of energy. When averaged across a 30-minute smart-meter integration interval, this high-power surge is mathematically diluted into an apparent continuous load of only 760 W to 1,150 W (or ~380 W if shared across an interval boundary). 

This temporal dilution produces three major effects on disaggregation:
1. **Peak Dilution:** Sharp physical peaks are smoothed into low-amplitude trapezoids, severely degrading the model's ability to distinguish a washing-machine heating element from lower-power appliances running concurrently (such as a 1 kW toaster, desktop computer, or small space heater).
2. **Loss of High-Frequency Micro-Signatures:** The characteristic 80 W to 300 W motor drum reversals occurring every 30 to 60 seconds are completely averaged out, eliminating the distinct variance and rolling-standard-deviation cues that allow 1-minute models to reject 3-minute kettle boils.
3. **Cycle Boundary Blurring:** Identifying exact cycle start and stop times becomes uncertain within $\pm 30$ minutes. 

While event-level operational state detection degrades under 30-minute averaging, macro-level energy disaggregation across multi-hour or daily integration windows remains statistically viable using regularized linear regression or sequence-to-sequence neural architectures, particularly for high-energy thermal loads (electric vehicles and heat pumps).
