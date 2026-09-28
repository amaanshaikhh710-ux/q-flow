# Q-FLOW — Prediction Engine

## Purpose
Estimate when a specific patient is likely to be consulted, express uncertainty honestly, adapt to live queue conditions, and support travel-aware arrival optimization. No Q-FLOW accuracy claim is valid until measured.

## Four conceptual layers
### Model A — Service Duration
Predict consultation/service duration using available context. Features: doctor, department, day/time, priority class, queue length, current session speed, historical doctor speed.
Progression (FINAL FOR MVP):
- Phase 1: Robust statistical baseline using rolling/historical median service duration.
- Phase 2: Basic tabular service-duration model using scikit-learn.
Architecture allows later replacement with XGBoost/CatBoost without rewriting the queue engine.

**Critical Architectural Rule:** The queue engine MUST NOT depend on ML availability. If ML is unavailable or training data is insufficient, fallback to the robust statistical baseline is automatic.

### Model B — Queue State / Downstream ETA
Determine which eligible patients are ahead and accumulate service-time estimates while accounting for queue state and doctor availability.

### Model C — Disruption / Volatility
Incorporate emergency insertion, doctor delay/break, sudden slowdown, no-show and other recorded operational events. Do not claim to know that a future emergency will happen.

### Model D — Arrival Optimizer
Combine consultation window, travel-time estimate, buffer and lateness risk to recommend departure/arrival.

## Current position
Authoritative queue position comes from server-side queue state/event history, not token arithmetic in the browser.

Algorithmic sequence:
1. Identify eligible entries ahead.
2. Apply priority ordering (EMERGENCY > PRIORITY > NORMAL).
3. Exclude completed/no-show entries.
4. Exclude TEMPORARILY_LEFT entries (awaiting staff requeue).
5. Check doctor availability and queue pause.
6. Estimate service duration for relevant patients (scikit-learn or median baseline).
7. Accumulate expected downstream time.
8. Apply live correction/disruption logic.
9. Produce uncertainty bounds.

## Baseline
Before sufficient historical data, use robust statistics: rolling median and historical median doctor/department service duration.

## Cold start & fallback
```text
No/low data / ML down → robust median baseline → scikit-learn tabular model → live correction
```
Fallback to baseline is automatic and seamless.

## Live correction
Compare recent completed consultation durations with historical/session expectations. Faster current sessions should move forecasts accordingly; slower sessions should do the same.

## Emergency insertion
When staff records an emergency/priority case: append event → change queue ordering → recompute affected patients → produce reason code (`PRIORITY_INSERTED`) → broadcast → evaluate notification.

## Outliers
### Data error
Impossible timestamps/invalid records: reject or exclude from model training, while retaining audit/error information as appropriate.

### Operational anomaly
Example: doctor interruption causes unusually long service. Classify separately; do not treat as normal service baseline.

### Genuine complex consultation
Example: 40-minute clinical consultation. Retain; optionally classify.

### Emergency priority
A different queue class/event, not simply a statistical outlier.

**Critical rule:** outlier handling for forecasting is not pretending the event did not happen. The active queue uses actual elapsed/remaining time.

## Doctor delay/break
Recorded event changes availability and downstream ETA.

## No-show
Remove from eligible active path, retain event, recalculate downstream ETA.

## Temporary leave/return: STAFF-MANAGED RE-QUEUEING (FINAL)
When patient leaves, marked `TEMPORARILY_LEFT` (excluded from active service path). Upon return, marked `RETURNED`. Staff decides and executes `STAFF_REQUEUES` into `WAITING`. No automatic position preservation or end-of-queue placement.

## Multiple doctors
Each queue has independent state and service history. Hospital analytics may aggregate; mutable state must not leak across queues. Dynamic reassignment between doctors is POST-MVP.

## Queue shock detector: POST-MVP
Candidate behavior: monitor service-duration/queue-growth changes, detect sudden slowdown, widen uncertainty. Not a blocker for MVP; architecture allows adding post-MVP.

## ETA stability & notification threshold (FINAL FOR MVP)
Avoid notification noise from tiny fluctuations. Meaningful-change threshold is set to >= 10 minutes (configurable in backend settings). Outgoing notifications trigger only if window shifts >= 10 minutes or a critical event occurs.

## Explainable changes
Use reason codes such as PRIORITY_INSERTED, DOCTOR_DELAY, DOCTOR_BREAK, SERVICE_SPEED_CHANGE, NO_SHOW, QUEUE_PAUSED/RESUMED. Patient-facing text must reflect actual recorded/derived causes.

## Implementation Architecture (Phase 4 Verified)

### 1. Robust Median Baseline & 5-Tier Fallback Hierarchy
The prediction engine implements `RobustMedianPredictor` and `PredictionFeatureBuilder` with a 5-tier fallback hierarchy for predicting consultation duration:
1. **Tier 1 (Doctor + Department Recent):** Last 10 completed consultations for the assigned doctor in this department.
2. **Tier 2 (Doctor Historical):** All completed consultations for the doctor (requires >= 3 samples).
3. **Tier 3 (Department Historical):** All completed consultations across doctors in this department (requires >= 3 samples).
4. **Tier 4 (Global Clinic Historical):** All clinic consultations across all departments (requires >= 3 samples).
5. **Tier 5 (Safe Default):** 15.0 minutes (900.0 seconds).

### 2. Downstream ETA & Cumulative Waiting Time
For an entry at position $K$ in queue:
- **Active Consultation in Progress:** Remaining duration = `max(60, predicted_duration - elapsed_seconds)`.
- **Called Patient (if any):** Predicted duration.
- **Waiting Patients Ahead:** Sum of predicted durations for all active waiting patients ordered by `(priority_rank DESC, position ASC)`.
- **Doctor Breaks & Delays:** Active breaks and cumulative delays are added to downstream start times.
- **Predicted Window:** `predicted_start_at = now + accumulated_wait_seconds`, `predicted_end_at = predicted_start_at + predicted_duration + uncertainty_margin`.

### 3. Dynamic Reforecasting & Explanation
Triggered automatically by queue disruption events:
- `EMERGENCY_INSERTED`: Explains emergency patient insertion ahead.
- `PATIENT_NO_SHOW`: Explains token skipped due to no-show.
- `DOCTOR_DELAY`: Explains doctor delay of $N$ minutes.
- `DOCTOR_BREAK_STARTED` / `DOCTOR_BREAK_ENDED`: Explains doctor operational pause/resume.
- `PRIORITY_CHANGED`, `PATIENT_TEMPORARILY_LEFT`, `PATIENT_RETURNED`, `STAFF_REQUEUES`, `CONSULTATION_STARTED`, `CONSULTATION_COMPLETED`.

**Meaningful Change Threshold:**
If `abs(new_predicted_start - old_predicted_start) >= 600s` (10 minutes), `is_meaningful_change = True`.

**Idempotency:**
If `reforecast_after_event` is called multiple times with the same `trigger_event_id`, existing snapshots are returned and duplicate records are prevented.

**Advisory Rule:**
The prediction engine is strictly advisory. Failure or error in prediction never blocks queue operations or mutations.

### 4. Prediction Window Semantics (Phase 4.1 Hardened)


Q-FLOW explicitly produces an **Estimated Consultation Window**, not a fixed appointment slot:
`Estimated Consultation Window: [predicted_start_at — predicted_end_at]`

#### Field Semantics
- **`predicted_start_at`**: The earliest/central expected consultation start time according to the server-authoritative deterministic queue calculation (accumulating active consultation remaining time, called patients, waiting patients ahead, and active doctor delays/breaks).
  - *Critical Patient Invariant:* A patient must **never** interpret `predicted_start_at` as a guaranteed appointment time. It represents the estimated moment consultations ahead will conclude and the patient will be called. Patients are instructed to arrive with adequate buffer.
- **`predicted_end_at`**: The expected completion/end boundary of the consultation window, calculated as:
  `predicted_end_at = predicted_start_at + predicted_duration_seconds + uncertainty_margin_seconds`
  Because `predicted_duration_seconds >= 60` and `uncertainty_margin_seconds >= 180`, `predicted_end_at > predicted_start_at` is guaranteed to be strictly chronologically valid at all times.
- **`uncertainty_margin_seconds`**: Non-negative uncertainty buffer in seconds (`>= 180s`, default `300s`), derived from historical Median Absolute Deviation (MAD). Reflects operational variability without misleading percentage claims.
- **`predicted_duration_seconds`**: Non-negative estimated service duration in seconds (`>= 60s`, default `900s`).
- **`patients_ahead_count`**: Non-negative integer count (`>= 0`) of active unserviced patients ahead in authoritative queue order.
- **`explanation`**: Patient-facing context explanation explaining initial estimate or why the window shifted.
- **`model_version`**: Model identifier (e.g. `baseline-v1`).

#### Integrity Guarantees
- Zero fake confidence percentages exposed across models, APIs, and logs.
- Negative durations, negative uncertainty margins, and negative counts ahead are strictly rejected at the service and Pydantic schema validation layers (`ge=0`).
- Chronological validity is preserved through all reforecasts and operational disruptions.


## Arrival Optimization (Phase 5 Implemented)
Model D bridges the consultation window with patient transit times:
- `ArrivalOptimizationService` combines `[predicted_start_at, predicted_end_at]`, travel duration ($D$), travel uncertainty ($U$), and arrival buffer ($B = 10\text{ min}$) to compute recommended arrival window ($[T_{\text{start}} - 15\text{m}, T_{\text{start}} - 5\text{m}]$) and departure window ($[T_{\text{arr\_start}} - (D+U), T_{\text{arr\_end}} - (D+U)]$).
- See [`09_ARRIVAL_OPTIMIZATION.md`](file:///c:/Users/Admin/Downloads/documentation/documentation/09_ARRIVAL_OPTIMIZATION.md) for complete mathematical proofs, provider abstraction, caching, and privacy invariants.


## Evaluation
Use MAE, median absolute error, P90 absolute error, underestimation rate and prediction interval coverage. Never invent values.

## Benchmark
Model 0 simple average; Model 1 rolling median; Model 2 ML; Model 3 ML + live correction; Model 4 ML + live correction + disruption handling. Values must come from actual tests/simulation.

## Drift
Support monitoring/recalibration because service behavior can change. Retraining cadence TBD.
