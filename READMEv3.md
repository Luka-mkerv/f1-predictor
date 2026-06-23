## Version 3 — Predicting Overtake Counts (Poisson Regression)

### Goal

Predict the number of on-track overtakes a driver makes in a race, using only 
pre-race information. A new target entirely — not classification (v1) or ranking 
(v2), but count prediction using XGBoost's Poisson objective.

### Overtake Definition

True on-track passes only, defined as:
- Lap-to-lap position improvement (Position < prev_position)
- No pit stop on that lap (PitInTime is NaT)
- No pit-out on that lap (PitOutTime is NaT)
- Green flag laps only (TrackStatus == '1')

This excludes pit-stop shuffling and safety car position changes. Imperfect — 
undercut recoveries still count — but the closest approximation to genuine 
on-track overtaking achievable from lap-by-lap position data alone.

### Data

Lap-by-lap position data extracted from FastF1 for all 92 races (2022-2025), 
computed on the fly from cache rather than stored in the database. Overtake counts 
aggregated per driver per race, then joined with race_results for grid position 
and qualifying data. 1,780 driver-race rows total, 1,749 after dropping first-race 
NaNs (no historical average available yet).

Train: 2022-2024 (1,291 rows). Test: 2025 (458 rows).

### Why Poisson, not standard regression

Overtake counts are non-negative integers with a right-skewed distribution 
(most drivers make 0-3, a few make 12+). Standard regression assumes symmetric, 
continuous, unbounded targets — a poor fit that can produce negative predictions 
and penalizes over/under-prediction symmetrically. Poisson regression is built 
for count data: non-negative by construction, variance scales with mean, and the 
log-likelihood loss respects the integer structure of the target.

### Features tested

Same ablation discipline as v2 — minimal first, add complexity only if it earns 
its place.

| Feature set | Exact match | Within 2 |
|---|---|---|
| Baseline (predict training mean always) | 7.2% (33/458) | — |
| Minimal: grid_position + driver_avg_overtakes | **12.7% (58/458)** | 51.1% |
| + constructor_career_avg | 10.9% (50/458) | 51.7% |
| + made_q3 | 11.6% (53/458) | 51.7% |

`driver_avg_overtakes` is a leakage-safe historical average — expanding mean of 
past races only, shifted so the current race never contributes to its own feature 
value. Same shift/expanding discipline as all rolling features in v1 and v2.

### Key finding

Minimal 2-feature model (grid_position + driver_avg_overtakes) wins on exact 
match — the third consecutive version of this project where a small, clean feature 
set outperforms richer combinations on the metric that matters most. Added features 
(constructor form, qualifying progression) hurt exact precision while marginally 
improving the within-2 tolerance metric — the same front/back tradeoff pattern 
seen in v2's ranking ablation.

MAE of 2.90 overtakes vs baseline MAE of 3.15 — model beats naive mean prediction 
by ~8%, a real but modest margin, consistent with the fundamental information limit: 
overtake counts are driven substantially by in-race events (incidents, safety cars, 
strategy variance) that no pre-race feature can capture.

### Honest limitations

- Undercut recoveries counted as overtakes — position gained after pit stop 
  re-entry isn't purely on-track skill, but can't be cleanly separated from 
  genuine passes without car-to-car proximity data FastF1 doesn't provide at 
  lap granularity.
- Low variance in predictions (predicted std 1.34 vs actual std 3.85) — model 
  correctly identifies average tendency but can't predict the full range of 
  outcomes. Some races a driver makes 0 overtakes, others 15 — that variance is 
  real randomness, not a modeling failure.
- 24 test races is a small sample for stable percentage estimates — results should 
  be re-checked against future seasons before treating numbers as definitive.

### Open questions

- Whether being-overtaken count (positions lost on track) adds signal as a 
  separate target or feature — discussed but not yet built.
- Whether circuit type (street circuit vs high-speed) would add genuine signal 
  for overtake tendency, since overtaking at Monaco is structurally different 
  from Spa — not tested here due to sparse circuit-level data.
- Whether lap-by-lap overtake tendency mid-race could improve the v2 ranking 
  model as a pre-race historical feature — the original motivation for v3, 
  not yet wired back into v2.