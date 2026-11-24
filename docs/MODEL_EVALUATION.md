# Model evaluation (synthetic data)

_Generated 2026-11-24 08:58 by `python manage.py evaluate_models`._

> **All figures below come from SYNTHETIC student data** produced by `ai_engine/engine/synthetic.py`. They show that the evaluation pipeline works and how the models compare on plausible patterns. They are **not** evidence of accuracy on real students; repeat this evaluation on consented pilot data (proposal section 3.5).

* Students simulated: **30**, history length: **120 days**
* Task: predict total spending over the next **7 days**
* Method: rolling-origin backtest (fit on days before the origin only, step 1 day, first origin at day 28)
* Metrics: MAE and RMSE in KSh; relative MAE = MAE / mean actual 7-day spend

| Model | Mean MAE (KSh) | Mean RMSE (KSh) | Relative MAE | Beat 14-day baseline | Selected |
|---|---:|---:|---:|---:|---:|
| Historical average | 2,312 | 2,688 | 56.2% | 27/30 | 6 |
| Recent 14-day average | 2,717 | 3,326 | 65.5% | baseline | 1 |
| Weekday profile (8 weeks) | 2,278 | 2,694 | 55.2% | 28/30 | 4 |
| Linear trend (28 days) | 3,746 | 4,587 | 90.4% | 0/30 | 0 |
| Ridge regression on rolling windows | 2,042 | 2,523 | 49.0% | 28/30 | 19 |

## How to read this

* The app selects a learned model for a student only when it beats the 14-day average by at least 5% on that student's own backtest; otherwise the simpler baseline is used.
* Student spending is spiky (a monthly rent payment can land inside or outside a 7-day window, plus weekend outings and late HELB), so even the best model's 7-day error is a large share of weekly spending (see the Relative MAE column). This is why the app labels every forecast with a reliability level, shows the error figures, and never presents a forecast as a guarantee.
* 'Beat 14-day baseline' compares overall MAE per student; 'Selected' uses the paired comparison on shared test days with the 5% rule, exactly as the live app does.
* With fewer than 14 days of history no forecast is shown as reliable.
