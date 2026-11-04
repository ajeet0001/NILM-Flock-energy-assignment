# Cross-Project Technical Interview Preparation: NILM, Energy Data Engineering & Disaggregation

**Platform:** Flock Energy NILM Appliance Disaggregation  
**Scope:** Complete Cross-Project Technical Audit (Requirements 1, 2, 3, and 4)  
**Author:** Senior Machine Learning & Energy-Data Engineer  

This document contains 25 comprehensive technical interview questions, spoken model answers, empirical evidence from the REFIT project, and challenging technical follow-up questions.

---

### Category 1: Utility Strategy, Business Value & Commercialization

#### Q1: Why does Non-Intrusive Load Monitoring (NILM) matter to an electric utility or distribution network operator (DNO)?
- **Concise Spoken Answer:** Utilities face unprecedented peak distribution congestion and rising wholesale balancing costs driven by residential electrification. Sub-metering every home appliance with physical smart plugs is cost-prohibitive (£50+ per plug across millions of homes). NILM provides a pure software-based mechanism to extract appliance-level visibility directly from existing smart meters, unlocking targeted demand-side response (DSR), personalized customer energy-saving feedback, and precise measurement and verification (M&V) without capital expenditure.
- **Project Evidence:** In our REFIT analysis across 2,509 cycles, washing machines accounted for high transient peaks (up to 2.4 kW per home), but 62.4% of cycles naturally occurred during the morning/midday window, proving that domestic laundry is a highly flexible load that can be nudged away from the 16:30–19:30 distribution peak.
- **Challenging Follow-Up:** If a utility provides load-shifting feedback, how can you prove causality and verify that customers actually shifted their laundry rather than just observing seasonal or weather variations?
  *Answer:* By conducting a Randomized Controlled Trial (RCT) with treatment and control cohorts and using a Difference-in-Differences (DiD) econometric regression model to control for exogenous temperature and seasonal confounders.

#### Q2: Why is shifting washing-machine usage fundamentally different from reducing total energy consumption?
- **Concise Spoken Answer:** Shifting load is a temporal reallocation of demand, whereas reducing consumption is a thermodynamic reduction in total kilowatt-hours. Running a 40°C wash cycle consumes roughly 0.4 kWh regardless of whether it is run at 11:00 or 18:00; changing the time of day does not alter the thermodynamic work required to heat water and rotate the drum. Load shifting relieves local substation transformer peak stress and saves customers money on Time-of-Use tariffs, but true energy reduction requires behavioral changes like washing at 30°C or running fuller loads.
- **Project Evidence:** In our House 1 data, median cycle energy is 300.8 Wh; shifting all 4.8 cycles per week away from the evening peak shifts ~1.44 kWh of peak demand per week, but total energy remains ~1.44 kWh unless cycle temperature settings change.
- **Challenging Follow-Up:** What unintended consequence can occur if a utility aggressively incentivizes dynamic off-peak laundry shifting across an entire feeder?
  *Answer:* "Rebound peaks" (or timer synchronization peaks), where thousands of automated washing machines simultaneously start at the beginning of the off-peak tariff window (e.g., exactly at 23:00), creating a steeper artificial substation peak than the original evening peak.

#### Q3: What is the business case for a conditional go/no-go recommendation rather than immediate full-scale commercial rollout?
- **Concise Spoken Answer:** While our disaggregation model demonstrates high active recall (85.5%) and accurate energy estimation (12.55% error), its 1-minute precision is capped at 28.0% due to false positives from concurrent high-power heating loads (kettles, ovens). Prematurely rolling this out as an automated billing or direct-control service would trigger high customer dispute rates and brand damage. A conditional pilot allows the utility to deploy NILM as an engaging informational nudge while refining false-positive filters before committing to enterprise-scale deployment.
- **Project Evidence:** Our benchmark showed that unconstrained thresholding produces a 58% energy estimation error, while our ML model brings it down to 12.55%, but false positives from kettles still occur during peak cooking hours.
- **Challenging Follow-Up:** What specific quantitative threshold would trigger a "no-go" termination during the proposed 500-home pilot?
  *Answer:* An opt-out rate exceeding 10%, a customer false-alarm complaint rate exceeding 5%, or an inability to achieve a statistically significant 15% reduction in peak-period laundry activations compared to the control group.

---

### Category 2: Data Engineering, Cleaning & Missingness Semantics

#### Q4: What was the critical architectural discovery regarding Part 1 and Part 2 raw files for House 1, and why could they not be blindly merged?
- **Concise Spoken Answer:** The raw Part 1 and Part 2 files for House 1 are not consecutive temporal partitions; they overlap for over three months (from June 27, 2014 to October 1, 2014). An empirical audit revealed that 75.18% of shared Unix timestamps contain conflicting aggregate power readings. Part 1 was an initial database export where unavailable sensors were erroneously coded as zero; Part 2 is the corrected re-issue where unavailable sensors are encoded as `NaN`. Blindly concatenating or averaging them would corrupt sensor availability and inject false zero-power readings.
- **Project Evidence:** Audited in `DATA.md`: Part 1 has 4,377,877 rows; Part 2 has 4,140,886 rows. Our pipeline deterministically switches to Part 2 at Unix timestamp `1403906220` (June 27, 2014 21:57:00 UTC).
- **Challenging Follow-Up:** If two sensors transmit conflicting readings for the same physical second in Part 2, what deterministic rule did you use to resolve it?
  *Answer:* Timestamp-level sorting preserves file order and deterministically selects the last non-missing observation for each individual channel.

#### Q5: Why must missing smart-meter readings never be filled with zeros?
- **Concise Spoken Answer:** A reading of 0 W represents a physical state: the circuit is closed, voltage is present, but current draw is zero (the appliance is off). A missing reading represents an unobserved state: a gateway crash, home broadband outage, or utility communication failure. Converting missing intervals to zero manufactures false empirical evidence that an appliance was off, which corrupts operating duration calculations, artificially fragments active cycles, and distorts ML training gradients.
- **Project Evidence:** In House 1, we preserved the 41.6-day system outage (59,906 consecutive minutes in Feb 2014) as true `NaN` missingness. If converted to zero, the washing machine would be falsely reported as idle for 1,000 hours, artificially lowering baseline energy distributions.
- **Challenging Follow-Up:** Under what strict conditions is short-gap interpolation mathematically and physically justified?
  *Answer:* Only for small isolated missing gaps ($\le 2$ or 5 minutes) where the appliance electromechanical time constant is larger than the gap, and provided that interpolated values are explicitly tracked with a boolean flag (`*_was_imputed = True`).

#### Q6: How did you resample asynchronous, irregular raw readings to a uniform 1-minute grid without introducing phase distortion?
- **Concise Spoken Answer:** Raw REFIT readings were captured asynchronously on load change (~8-second intervals). We first parsed Unix epoch seconds as UTC instants, applied deterministic deduplication to conflicting timestamps, and aggregated observations into uniform 60-second left-closed bins using `resample('1min').mean()`. This represents the true time-weighted average active power over each minute.
- **Project Evidence:** Implemented in `src/clean_raw_data.py` and validated in `outputs/cleaned/CLEAN_House1_1min.csv` (exactly 920,031 contiguous bins).
- **Challenging Follow-Up:** If a 1-minute bin contains only one raw reading at second 02, does taking the mean accurately reflect the minute's energy?
  *Answer:* It introduces a sample-and-hold approximation. However, because raw readings were event-driven (transmitting whenever power changed by $>15\text{ W}$), an absence of readings implies power remained constant.

---

### Category 3: Physics-Informed Cycle Detection & EDA

#### Q7: Why is a simple threshold of $P > 0\text{ W}$ catastrophic for detecting washing machine activity?
- **Concise Spoken Answer:** Modern washing machines contain digital control boards, LED displays, and standby power supplies that continuously draw 1 W to 5 W even when idle. Setting a threshold at $P > 0\text{ W}$ causes standby consumption to be falsely classified as continuous washing activity, reporting that the appliance runs 24/7.
- **Project Evidence:** In House 5, 36.25% of all minutes across the year (338,398 minutes) exhibit continuous standby load between 1 W and 5 W (median 3.0 W). An unconstrained threshold classifies House 5 as washing for 43% of the year. A 20 W threshold isolates actual drum agitation.
- **Challenging Follow-Up:** Could a low threshold like 10 W work if you subtracted the baseline standby power?
  *Answer:* Standby power drifts with ambient temperature and mains voltage fluctuations; a fixed 20 W threshold provides a clean margin above standby noise while comfortably capturing drain pumps (30–50 W) and low-speed drum agitation (80 W).

#### Q8: Why is gap merging mathematically essential when segmenting washing machine cycles?
- **Concise Spoken Answer:** Domestic washing machine cycles are not continuous power blocks. During soak phases, detergent interaction periods, and motor drum reversals, active power drops below 20 W (often to 0–4 W) for 1 to 3 minutes. Without gap merging, an automated detector splits a single physical cycle into 5 to 10 fragmented micro-events and discards them if they fall below the minimum cycle duration.
- **Project Evidence:** Our sensitivity grid (`results/washing_machine_sensitivity.csv`) proved that setting gap merging to $G=0$ causes detected cycles in House 1 to collapse by 41.3% (from 438 to 257 cycles) and captured energy to drop from 141.6 kWh to 75.3 kWh. Setting $G=3\text{ minutes}$ successfully reconstructs complete physical cycles.
- **Challenging Follow-Up:** What is the risk of setting the gap-merging parameter too high (e.g., $G = 15\text{ minutes}$)?
  *Answer:* It risks bridging two completely separate, back-to-back laundry loads into a single unphysical 4-hour cycle.

#### Q9: How do household occupancy and dwelling architecture affect laundry frequency and cycle characteristics?
- **Concise Spoken Answer:** Laundry frequency scales strongly with household occupancy: 2-person households (Houses 1, 3, 20) averaged 3.1 to 4.8 cycles/week, whereas 4-person households (Houses 2 and 5) averaged 3.9 to 8.9 cycles/week. However, cycle characteristics are governed by occupant preferences: House 2 runs long, hot 60°C washes (median duration 95 min, median energy 604 Wh), whereas House 5 runs frequent, shorter, lower-temperature cycles (median duration 42 min, median energy 276 Wh).
- **Project Evidence:** Documented across 2,509 cycles in `results/household_washing_machine_summary.csv`.
- **Challenging Follow-Up:** Why does peak power remain constant (~2.0–2.4 kW) across all homes despite large differences in duration and energy?
  *Answer:* Peak power is dictated by the physical rating of the resistive immersion heating element (typically 2.0–2.4 kW across European 230V appliances), whereas duration and energy reflect the volume of water heated and temperature selection.

---

### Category 4: Machine Learning Disaggregation & Validation

#### Q10: Why did you formulate washing-machine disaggregation as continuous regression rather than binary state classification?
- **Concise Spoken Answer:** The primary objective of utility disaggregation is energy accounting (kWh) and demand flexibility quantification (kW). Active power in Watts is continuous, and energy is the time-integral of power ($E = \int P(t)\,dt$). Binary classification can tell you if a machine is running, but cannot tell you whether it is heating at 2,300 W or tumbling at 100 W, introducing massive errors when estimating bill impacts or transformer stress.
- **Project Evidence:** Continuous regression enabled direct energy calculation on House 1, achieving 38.26 kWh predicted vs. 43.75 kWh actual (12.55% error).
- **Challenging Follow-Up:** If regression is the primary objective, why did you also compute Precision, Recall, and F1-score?
  *Answer:* To evaluate operational event-detection quality. Evaluating regression alone (e.g., via MAE) can conceal event-detection failures due to extreme class imbalance.

#### Q11: Explain the danger of data leakage in time-series NILM and how your validation design prevented it.
- **Concise Spoken Answer:** Random k-fold cross-validation or random train/test splitting in time series causes severe lookahead leakage. Adjacent minutes in a washing cycle have high autocorrelation. If minute $t$ is in the test set while minute $t+1$ is in the training set, the model simply memorizes the local trajectory rather than learning disaggregation from aggregate load. We prevented leakage by enforcing strict chronological holdouts (first 75% train, final 25% test) and testing zero-shot generalization across completely unseen households (Houses 2 & 3 $\rightarrow$ House 1).
- **Project Evidence:** Evaluated on 201,683 chronological test minutes in House 1, with zero temporal shuffling.
- **Challenging Follow-Up:** If you use lead features ($t+1 \dots t+15$), did you introduce leakage at the train/test split boundary?
  *Answer:* A 15-minute buffer must be dropped at the exact split boundary between train and test sets to ensure no test aggregate values enter the training feature matrix.

#### Q12: Why did the Always-Off baseline achieve an MAE of 13.02 W while the Heuristic Threshold baseline achieved a worse MAE of 17.04 W?
- **Concise Spoken Answer:** The washing machine is active for only 1.64% of elapsed minutes. An Always-Off baseline predicts 0 W for 100% of samples, incurring zero error on the 98.36% of inactive minutes. The Heuristic Threshold flags any aggregate load $\ge 1,800\text{ W}$ as active; because electric kettles, ovens, and cookers frequently cross 1,800 W, the heuristic incurs massive false positives, adding 1,750 W of absolute error on every false alarm.
- **Project Evidence:** Documented in `results/tables/disaggregation_metrics.csv`.
- **Challenging Follow-Up:** If Always-Off has an MAE of 13.02 W and the ML model has an MAE of 12.52 W, does the ML model provide any real improvement?
  *Answer:* Yes, MAE is heavily diluted by the 98% off-state density. The true improvement is reflected in RMSE, which drops by 30.89% (from 154.64 W to 106.87 W), active-state Recall (85.5% vs 0%), and energy capture (38.26 kWh vs 0.0 kWh).

#### Q13: Why did you choose Histogram Gradient Boosting Trees over a Sequence-to-Point (Seq2Point) deep neural network?
- **Concise Spoken Answer:** GBDT on engineered window features provides superior training speed, extreme parameter efficiency, and native interpretability. Our GBDT model trains on 605,000 samples in under 10 seconds on a standard CPU, requires $<500\text{ KB}$ of memory, and achieves microsecond inference latency. A deep neural network (CNN/LSTM) requires GPU infrastructure, takes hours to train, and risks overfitting without offering significant accuracy gains on 1-minute tabular window features.
- **Project Evidence:** Native `HistGradientBoostingRegressor` implementation in `src/disaggregation_model.py`.
- **Challenging Follow-Up:** Under what conditions would a deep learning approach outperform GBDT in NILM?
  *Answer:* At higher sampling frequencies (e.g., 1-second or 10 Hz data) across hundreds of homes, where manual feature engineering becomes intractable and deep 1D convolutions can automatically discover multi-scale temporal filters.

---

### Category 5: Limitations, Generalization & Global Applicability

#### Q14: How does 15-minute or 30-minute smart-meter data degrade NILM disaggregation performance compared to 1-minute data?
- **Concise Spoken Answer:** Coarser intervals average instantaneous active power over time. A 20-minute, 2,300 W water-heating surge represents 0.76 kWh; in a 30-minute smart meter interval, that energy is averaged down to an apparent load of ~760 W or ~380 W. This dilutes peak signatures, completely eliminates high-frequency motor agitation pulses, increases ambiguity with general baseloads (fridge, lighting, TVs), and softens cycle boundary precision.
- **Project Evidence:** At 1-minute cadence, the 2.3 kW plateau and 100 W drum reversals are clearly distinct; at 30 minutes, they collapse into a single smoothed trapezoid.
- **Challenging Follow-Up:** Can any appliance disaggregation still work on 30-minute utility smart-meter data?
  *Answer:* Yes, but primarily for large thermal storage loads (e.g., electric vehicle charging at 7 kW for 4 hours, or heat pump space heating running continuously for 3 hours) rather than short-cycle domestic appliances.

#### Q15: Why can UK REFIT disaggregation models not be directly transferred to Indian residential grids?
- **Concise Spoken Answer:** 1) Appliance architecture: UK washing machines have internal 2 kW immersion heaters to heat cold 10°C inlet water. Typical Indian washing machines are cold-fill top-loaders drawing only 200–400 W for motor agitation (water is unheated or heated via external geysers), so the 2 kW heating signature is completely absent. 2) Grid power quality: Indian distribution networks experience voltage sags (180V–260V), planned load shedding, and unmonitored inverter-battery switchovers that distort aggregate current waveforms. 3) Metering infrastructure: Indian smart meters under RDSS report on 15-minute or daily batch intervals.
- **Project Evidence:** Documented in `Recommendation.md` and `RESULTS.md`.
- **Challenging Follow-Up:** How would you design a NILM solution tailored specifically for the Indian residential market?
  *Answer:* Focus disaggregation on large, distinct Indian residential loads: split-system air conditioners (1.5 kW compressor cycling), electric storage water geysers (2 kW resistive load), and borewell/rooftop agricultural water pumps.

#### Q16: What is the primary cause of false positives in your disaggregation model, and how can it be mitigated?
- **Concise Spoken Answer:** Concurrent high-power resistive loads—specifically electric kettles, electric cooking hobs, and electric ovens. When a kettle turns on, aggregate power jumps by 2.5–3.0 kW. If background loads fluctuate, the model can momentarily output a false washing-machine spike. We mitigate this by incorporating a 15-minute lead window (verifying that the plateau is sustained for $>12\text{ minutes}$) and rolling standard deviation features that detect motor drum reversals.
- **Project Evidence:** Detailed in `results/figures/disaggregation_failure_cases.png` (Panel A).
- **Challenging Follow-Up:** How could a two-stage hierarchical architecture further reduce false positives?
  *Answer:* Stage 1 uses a high-precision binary classifier with a 20-minute minimum duration constraint to confirm that a valid wash cycle has begun; Stage 2 activates the regression model strictly within the confirmed temporal window.

#### Q17: What privacy and security risks are introduced by high-frequency appliance disaggregation?
- **Concise Spoken Answer:** High-frequency electrical telemetry acts as a behavioral biometric. Disaggregated appliance traces reveal granular personal lifestyle information: wake/sleep routines (kettle, toaster), occupancy/absence patterns, medical equipment usage, and weekly household routines. If intercepted, this data creates physical security risks (e.g., identifying when a home is unoccupied) and commercial profiling risks.
- **Project Evidence:** In House 1, laundry cycles consistently started at 09:00–11:00 on Tuesdays and Saturdays, revealing consistent occupant presence.
- **Challenging Follow-Up:** What technical architectural choice best protects customer privacy in a commercial NILM deployment?
  *Answer:* Edge computing: executing model inference locally on the smart meter gateway (e.g., using compiled lightweight decision trees) and transmitting only aggregated weekly energy summaries or anonymized flexibility indices to the cloud.

---

### Category 6: Production Engineering & System Deployment

#### Q18: How would you deploy this GBDT disaggregation model onto a resource-constrained smart meter or edge gateway?
- **Concise Spoken Answer:** 1) Maintain a 31-minute sliding ring buffer in RAM to store aggregate readings ($t-15$ to $t+15$). 2) Implement incremental $O(1)$ updates for rolling mean and variance using Welford's algorithm or running accumulators. 3) Compile the trained decision tree ensemble into pure, dependency-free C or Rust code using `treelite` or `m2cgen`. 4) Enforce fixed-point integer arithmetic if floating-point hardware is absent.
- **Project Evidence:** The 150-tree model occupies $<500\text{ KB}$ and executes inference in microseconds, fitting within low-cost microcontrollers (e.g., ESP32 or ARM Cortex-M4).
- **Challenging Follow-Up:** What happens if the smart meter experiences a 10-minute communication outage during real-time streaming?
  *Answer:* The edge ring buffer marks missing bins with a sentinel `NaN` and pauses inference until 15 contiguous post-outage samples are buffered, preventing corrupt gradient outputs.

#### Q19: In a multi-appliance NILM system, how do you prevent the sum of disaggregated appliances from exceeding the aggregate meter reading?
- **Concise Spoken Answer:** By formulating disaggregation under a physical sum-to-aggregate constraint: $\sum_{m=1}^{M} \hat{y}_t^{(m)} \le X_t$. In production, independent appliance models are unified via a constrained optimization post-processing layer (such as quadratic programming projection or softmax normalization) that guarantees total disaggregated power does not exceed whole-home load minus a slack variable representing unmonitored baseload.
- **Project Evidence:** REFIT houses contain up to 9 monitored appliances plus unmonitored residual circuits; unconstrained models can over-allocate energy during high-load periods.
- **Challenging Follow-Up:** What physical phenomenon could cause the true sum of sub-metered appliances to legitimately exceed the aggregate current clamp reading?
  *Answer:* Measurement errors, sensor phase calibration drift, or local distributed generation (e.g., micro-inverter rooftop solar injecting power downstream of the sub-meter plugs).

#### Q20: How would you detect concept drift and performance degradation in a deployed NILM model without sub-metered ground truth?
- **Concise Spoken Answer:** 1) Monitor input data distribution: Track Population Stability Index (PSI) or Wasserstein distance on whole-home aggregate power profiles to detect macroeconomic or seasonal shifts. 2) Track energy conservation ratios: Monitor the ratio of disaggregated appliance energy to total monthly smart-meter kWh ($\hat{E}_{\text{app}} / E_{\text{total}}$). If a household's washing-machine share jumps from 3% to 25%, flag an anomaly. 3) Plausibility rule engines: Flag households reporting $>20$ cycles per week or cycles lasting $>4$ hours.
- **Project Evidence:** In REFIT, weekly washing frequency ranged stably between 3.1 and 8.9 cycles/week across all homes; sudden deviations indicate model degradation or appliance replacement.
- **Challenging Follow-Up:** If an occupant buys a new heat-pump washer-dryer that consumes 50% less peak power, how will the model fail and how should the system adapt?
  *Answer:* The model will miss cycles because heat-pump washers replace the 2 kW resistive element with a 500 W variable-speed compressor. The system must prompt the customer when unusual 500 W multi-hour plateaus appear to update their appliance profile and switch model weights.

---

### Category 7: Verification & Requirements Audit

#### Q21: What specific metrics prove that Requirement 1 (Data Cleaning) was successfully achieved?
- **Concise Spoken Answer:** Successful execution of `src/clean_raw_data.py` producing `outputs/cleaned/CLEAN_House1_1min.csv` with exactly 920,031 contiguous 1-minute bins. Bounded 2-minute short-gap interpolation imputed exactly 617 minutes (0.067%) while preserving the 59,906-minute February 2014 outage as true missingness. Zero negative values were introduced, and Part 1 vs. Part 2 conflict resolution was validated against raw timestamps.
- **Project Evidence:** Verified in `DATA.md` and `outputs/tables/cleaning_quality_report.csv`.

#### Q22: What specific metrics prove that Requirement 2 (EDA & Cycle Detection) was successfully achieved?
- **Concise Spoken Answer:** Analysis of 5 households (Houses 1, 2, 3, 5, 20) identifying exactly 2,509 verified washing-machine cycles across 3,004 days of monitoring. Discovery that House 5 has 36.25% standby time (3 W) and proof that $G=3\text{ min}$ gap merging prevents a 41.3% cycle fragmentation. Delivery of 6 publication-grade figures and 3 validated CSV tables.
- **Project Evidence:** Verified in `RESULTS.md`, `results/washing_machine_cycles.csv`, and `results/household_washing_machine_summary.csv`.

#### Q23: What specific metrics prove that Requirement 3 (Disaggregation Modeling) was successfully achieved?
- **Concise Spoken Answer:** Implementation and benchmark of `HistGradientBoostingRegressor` on House 1 chronological holdout (201,683 test rows), achieving an MAE of 12.52 W, an RMSE of 106.87 W (a 30.89% reduction vs. Always-Off baseline of 154.64 W), an active Recall of 85.50%, and an energy estimation error of 12.55% (38.26 kWh vs. 43.75 kWh). Cross-household transfer to unseen House 1 achieved an 11.03% RMSE reduction and 2.53% energy error.
- **Project Evidence:** Verified in `results/tables/disaggregation_metrics.csv` and `results/disaggregation_test_predictions.csv`.

#### Q24: What specific deliverables prove that Requirement 4 (Utility Recommendations) was successfully achieved?
- **Concise Spoken Answer:** Delivery of `Recommendation.md` (one-page executive brief with concrete RCT pilot specification, 20% peak reduction target, and go/no-go gates), a rigorous technical analysis of 15-minute and 30-minute sampling dilution, a comprehensive UK-to-India transferability audit, and repository-wide integration across `README.md`, `DATA.md`, and `RESULTS.md`.
- **Project Evidence:** Verified on disk in `Recommendation.md`, `README.md`, and `interview_prep/technical_interview_qa.md`.

#### Q25: If you were given 3 more months and a £50,000 innovation grant, what would be your immediate next technical step?
- **Concise Spoken Answer:** I would deploy our compiled GBDT model onto 30 residential smart-meter gateways in a live shadow trial with physical sub-metering plugs for ground-truth validation. This would measure real-time edge latency, calibrate false-positive rejection on live 1-minute streaming data, and evaluate how customers respond to prototype laundry-shifting app notifications before committing to the full 500-home pilot.
- **Project Evidence:** Outlined in Section 5 of `Recommendation.md` as the Phase 1 Edge Validation Gate.
