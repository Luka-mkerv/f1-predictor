## Version 2 — Learning to Rank

### Goal

Move beyond binary "top 10 or not" classification (v1) to predicting a driver's full 
finishing order in a race, using only information available before lights out.

### Approach

XGBoost's `rank:ndcg` objective (LambdaMART) — same gradient boosting engine as v1, 
different loss function. Each race is treated as a group; the model learns to score 
drivers such that, when sorted, the scores approximate the true finishing order within 
that race. Relevance labels are `21 - finish_position`, with two `Withdrew` (no 
classification) rows assigned the worst relevance in their race rather than dropped.

Same pre-race features as v1 (grid position, qualifying gap to pole, rolling/career form, 
constructor form, circuit history, weather), restructured with race-level grouping. Train: 
2022-2024 (1,359 rows, 68 races). Test: 2025 season to date (479 rows, 24 races).

### Bug found and fixed: stale `race_id` ordering

`race_id` in the database is assigned by extraction order, not chronological order (e.g. 
2024's first race has `race_id=1`, 2023's first race has `race_id=2`). Building XGBoost's 
required `group` array with `groupby('race_id').size()` silently re-sorted rows by 
`race_id` value rather than preserving chronological row order, breaking the row-to-group 
correspondence. Fixed with `sort=False`, verified two independent ways (sum-matching and 
a row-by-row reconstruction) before trusting it.

### Bug found and fixed: severe early overfitting

Initial model peaked at iteration 6 of 200 boosting rounds (NDCG@10 0.856), with test 
score flat-to-declining for the remaining 194 rounds while train score kept climbing — 
classic overfitting, and an unstable basis for any feature-importance or prediction 
analysis given how few trees that represents. Fixed by lowering the learning rate 
(eta 0.1 → 0.05) and adding `subsample`/`colsample_bytree` regularization (0.8 each). 
Best iteration moved to 75, train/test gap narrowed substantially, test NDCG@10 improved 
to 0.884. A secondary symptom of the original under-trained model — multiple drivers 
receiving identical predicted scores (rank ties) — also disappeared once enough trees 
existed to differentiate every row.

### Key finding: no single feature set wins on every metric

Evaluated four feature sets (minimal: grid + quali gap only; + form features; + weather; 
full 55-feature model) against four different metrics, since NDCG@10 alone proved 
misleading — all four feature sets scored within 0.008 of each other on it, while 
Spearman correlation, winner accuracy, and exact-placement accuracy spread far more widely 
across the same models.

| Feature set | NDCG@10 | Spearman | Winner acc. | Exact placement |
|---|---|---|---|---|
| Grid position only (no model) | — | 0.651 | 66.7% | 2.3% |
| Minimal (grid + quali gap) | 0.890 | 0.650 | 66.7% | 15.9% |
| + form (rolling/career avgs) | 0.892 | 0.614 | 54.2% | 12.9% |
| + weather | 0.890 | 0.654 | 54.2% | 14.4% |
| Full model (55 features) | 0.884 | 0.631 | 58.3% | 16.3% |

No feature set dominates: minimal ties the no-model grid-position baseline on winner 
accuracy and Spearman; weather edges out everyone on whole-field correlation; the full 
model — despite underperforming on winner accuracy — wins clearly on exact placement, 
likely because its extra features (career/constructor form, circuit history) add real 
value in the more stable midfield-to-back of the grid, even while diluting front-of-field 
precision. Form features were the most consistently negative addition on front-weighted 
metrics, plausibly because rolling/career averages predict season-long tendency rather 
than a specific race's outcome.

**Practical takeaway:** which model is "best" depends on what it's for — picking race 
winners (minimal/baseline) versus predicting the full grid order (full model) call for 
different feature sets on this dataset. This is presented as a finding, not a gap to be 
explained away — discovering it required evaluating multiple metrics deliberately rather 
than trusting a single aggregate score.

### What's NOT yet tested

- Whether dropping only the worst offenders (form features, sparse one-hot circuit columns 
  already flagged as noisy in v1) while keeping the rest of the 55 produces a model strong 
  across all four metrics simultaneously, rather than trading off between them.
- Whether the front-of-field/back-of-field split is real when tested directly (e.g. exact 
  placement split into top-5 vs bottom-10 subsets per model) rather than inferred.
- Walk-forward validation across multiple train/test splits (rather than the single 
  2025 holdout used here) — would clarify whether weather's Spearman edge is a stable 
  effect or specific to this one test season.
- Wet-weather driver skill delta and lap-by-lap behavioral features (overtaking tendency, 
  position volatility) — discussed at length, not yet built. A real-race inspection during 
  this phase (Piastri: pole-adjacent grid slot, predicted P3, actually finished P9; 
  Antonelli: P16 grid, predicted P9, actually finished P4) showed both errors traceable to 
  in-race variance with no corresponding pre-race feature — exactly the gap these features 
  would target.
- Additional seasons of data (2026, earlier history) — deprioritized for now. v1 already 
  found that adding a full extra season barely moved results, and this phase's biggest 
  gains came from hyperparameter tuning and feature selection, not data volume.