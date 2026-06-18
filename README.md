# F1 Points Finish Predictor

A machine learning pipeline that predicts whether an F1 driver will finish in the top 10 (score championship points) in a given race, using only information available before the race starts.

## Project Goals

This project was built as a structured learning exercise covering both data engineering and machine learning fundamentals, ahead of a larger final year project. Specific goals:

- Build a real ETL pipeline (not a static Kaggle CSV)
- Practice feature engineering, including avoiding data leakage in time-series contexts
- Train and rigorously evaluate a classification model
- Document findings honestly, including negative results

## Architecture

```
FastF1 API → Python (extract.py) → PostgreSQL (Docker) → Jupyter (feature engineering) → XGBoost
```

- **Data source**: FastF1 API (official F1 timing data), Ergast-style metadata
- **Storage**: PostgreSQL, normalized into 8 tables (drivers, constructors, circuits, races, race_results, qualifying_results, weather, tyre_stints), run via Docker Compose
- **ETL**: Python + SQLAlchemy ORM, with duplicate-checking and null-handling built in after debugging real data integrity issues
- **Feature engineering & modeling**: pandas, scikit-learn, XGBoost, in Jupyter

## Data

4 F1 seasons (2022–2025), ~1838 driver-race rows, extracted via FastF1's official timing API.

## Target Variable

`points_finish`: binary, 1 if a driver finished in the top 10 in a race (scored championship points), 0 otherwise. Chosen over predicting race winners (too imbalanced, ~5% positive class) or exact finishing position (high variance, hard to evaluate cleanly).

## Features Engineered

- **Race day**: grid position, qualifying gap to pole, made Q2/Q3 (boolean)
- **Driver form**: rolling average finish (last 5 races), career average finish (expanding window), form delta (recent vs career)
- **Constructor form**: rolling and career average finish for the team
- **Circuit-specific**: driver's historical average finish at this specific circuit vs their overall average (`track_delta`)
- **Team comparison**: driver's performance vs their constructor's average
- **Weather**: air/track temperature, rainfall, humidity

All time-based features were built using `shift(1)` combined with `.rolling()` or `.expanding()` windows, specifically to prevent data leakage — ensuring each feature only uses information that would genuinely have been available before that race occurred.

## Key Finding: Simpler Beat Complex

This is the most important and counterintuitive result of the project.

| Model | Features | Test Accuracy (2025 holdout) |
|---|---|---|
| `made_q3` alone | 1 | **0.779** |
| `grid_position` alone | 1 | 0.766 |
| Hand-picked "independent" features | 4 | 0.712 |
| Full engineered feature set | 53 | 0.739 |
| Hyperparameter-tuned (grid_position + made_q3) | 2 | 0.760 |

Across every combination tested — including after adding a full extra season of training data (2022) and hyperparameter tuning via GridSearchCV — no feature combination beat a single feature: whether a driver progressed to Q3 in qualifying.

### Why

1. **Multicollinearity**: several engineered features (e.g. driver/constructor rolling and career averages) were correlated with each other at 0.85–0.97, meaning they largely duplicated the same signal rather than adding new information.
2. **Sparse categoricals**: one-hot encoding 24 circuits with only 2–4 occurrences each in the dataset introduced noisy, low-sample features that the model partially overfit to.
3. **Sample size relative to feature count**: with roughly 1300–1800 training rows, adding dozens of features increases the model's capacity to fit noise rather than genuine signal.
4. **`made_q3` is a near-direct proxy for the target**: qualifying performance this strongly predicts race outcome in F1, which is itself a legitimate finding about the sport, not just an artifact of the model.

### Final Model

XGBoost classifier using `made_q3` as the sole feature.

- **Accuracy**: 0.779
- **Precision/Recall**: balanced at ~0.77–0.78 across both classes
- **Confusion matrix**: roughly symmetric error distribution (51 false positives, 55 false negatives out of 479 test rows) — no systematic bias toward over- or under-predicting points finishes

## What Didn't Help

- Adding a 4th season of historical data (correlations and best-feature accuracy were nearly identical before and after)
- Weather features (near-zero linear correlation with the target; likely matters via interaction effects the model didn't pick up on, given limited wet-race samples)
- Hyperparameter tuning via GridSearchCV (improved cross-validation score on training years, but did not transfer to better test-year performance, suggesting some shift in competitive order between training and test seasons)

## Bugs Found and Fixed Along the Way

- Duplicate row inserts from re-running the extraction pipeline without idempotency checks
- A foreign key violation caused by a null `DriverId` in FastF1's qualifying data for one race
- A subtle data leakage bug in an early version of a circuit-performance feature, caused by `groupby().shift()` operating on rows with identical dates (same race), which produced same-race information disguised as "historical" data

## Next Steps

- **Ranking approach**: reformulate as predicting relative finishing order across all 20 drivers per race (`rank:pairwise` / `rank:ndcg` objectives), rather than a binary threshold
- **Lap-by-lap behavioral features**: derive overtaking tendency / racecraft signals from raw lap-by-lap position data, as a genuinely new (not redundant) feature category
- **Tyre strategy features**: incorporate stint length and compound choice patterns more deeply
- **Constructor reliability**: DNF/mechanical retirement rate as a feature

## Tech Stack

Python 3.14, FastF1, SQLAlchemy, psycopg2, pandas, XGBoost, scikit-learn, matplotlib, seaborn, PostgreSQL 16, Docker Compose