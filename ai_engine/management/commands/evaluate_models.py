"""
Evaluate every forecaster on SYNTHETIC students and write a Markdown report.

    python manage.py evaluate_models --students 30 --days 120

Outputs docs/MODEL_EVALUATION.md with MAE / RMSE per model, how often each
model would be selected, and how often it beat the 14-day-average baseline.
"""
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from ai_engine.engine.baseline import daily_series
from ai_engine.engine.forecasting import ALL_MODELS, BASELINE_NAME, backtest, select_model
from ai_engine.engine.synthetic import generate_student


class Command(BaseCommand):
    help = "Backtest the forecasting models on synthetic student data."

    def add_arguments(self, parser):
        parser.add_argument("--students", type=int, default=30)
        parser.add_argument("--days", type=int, default=120)
        parser.add_argument("--horizon", type=int, default=7)
        parser.add_argument("--output", default=str(Path(settings.BASE_DIR) / "docs" / "MODEL_EVALUATION.md"))

    def handle(self, *args, **opts):
        n, days, horizon = opts["students"], opts["days"], opts["horizon"]
        start = date(2026, 1, 5)
        maes = {m.name: [] for m in ALL_MODELS}
        rmses = {m.name: [] for m in ALL_MODELS}
        rel = {m.name: [] for m in ALL_MODELS}
        wins = {m.name: 0 for m in ALL_MODELS}
        selected = {m.name: 0 for m in ALL_MODELS}
        selected["historical_mean"] = 0

        for seed in range(n):
            _, expenses = generate_student(seed=seed, start=start, days=days)
            daily = daily_series(expenses, start, start + timedelta(days=days - 1))
            scores, mean_actual = backtest(daily, horizon=horizon)
            base = scores[BASELINE_NAME]
            for name, s in scores.items():
                if s.mae is None:
                    continue
                maes[name].append(s.mae)
                rmses[name].append(s.rmse)
                rel[name].append(s.mae / mean_actual if mean_actual else np.nan)
                if name != BASELINE_NAME and base.mae is not None and s.mae < base.mae:
                    wins[name] += 1
            choice, _ = select_model(scores)
            selected[choice] = selected.get(choice, 0) + 1

        lines = [
            "# Model evaluation (synthetic data)",
            "",
            f"_Generated {timezone.now():%Y-%m-%d %H:%M} by `python manage.py evaluate_models`._",
            "",
            "> **All figures below come from SYNTHETIC student data** produced by "
            "`ai_engine/engine/synthetic.py`. They show that the evaluation pipeline works and how the "
            "models compare on plausible patterns. They are **not** evidence of accuracy on real students; "
            "repeat this evaluation on consented pilot data (proposal section 3.5).",
            "",
            f"* Students simulated: **{n}**, history length: **{days} days**",
            f"* Task: predict total spending over the next **{horizon} days**",
            "* Method: rolling-origin backtest (fit on days before the origin only, step 1 day, first origin at day 28)",
            "* Metrics: MAE and RMSE in KSh; relative MAE = MAE / mean actual 7-day spend",
            "",
            "| Model | Mean MAE (KSh) | Mean RMSE (KSh) | Relative MAE | Beat 14-day baseline | Selected |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for m in ALL_MODELS:
            if not maes[m.name]:
                lines.append(f"| {m.label} | n/a | n/a | n/a | n/a | {selected.get(m.name, 0)} |")
                continue
            beat = "baseline" if m.name == BASELINE_NAME else f"{wins[m.name]}/{n}"
            lines.append(
                f"| {m.label} | {np.mean(maes[m.name]):,.0f} | {np.mean(rmses[m.name]):,.0f} | "
                f"{np.nanmean(rel[m.name]):.1%} | {beat} | {selected.get(m.name, 0)} |"
            )
        lines += [
            "",
            "## How to read this",
            "",
            "* The app selects a learned model for a student only when it beats the 14-day average by at least 5% "
            "on that student's own backtest; otherwise the simpler baseline is used.",
            "* Student spending is spiky (a monthly rent payment can land inside or outside a 7-day window, plus "
            "weekend outings and late HELB), so even the best model's 7-day error is a large share of weekly "
            "spending (see the Relative MAE column). This is why the app labels every forecast with a reliability "
            "level, shows the error figures, and never presents a forecast as a guarantee.",
            "* 'Beat 14-day baseline' compares overall MAE per student; 'Selected' uses the paired comparison on "
            "shared test days with the 5% rule, exactly as the live app does.",
            "* With fewer than 14 days of history no forecast is shown as reliable.",
        ]
        out = Path(opts["output"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.stdout.write("\n".join(lines))
        self.stdout.write(self.style.SUCCESS(f"\nReport written to {out}"))
