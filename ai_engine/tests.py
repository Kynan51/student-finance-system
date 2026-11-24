from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.testutils import PASSWORD, add_expense, add_income, make_user
from transactions.models import Category

from .engine.baseline import compute_baseline, daily_series
from .engine.categorizer import suggest_category
from .engine.forecasting import BASELINE_NAME, RecentMean, backtest, select_model
from .engine.patterns import category_trends, detect_anomalies
from .engine.synthetic import SYNTHETIC_TAG, generate_student
from .models import FinancialInsight
from .services import build_insights, refresh_insights


class BaselineTests(SimpleTestCase):
    def test_daily_series_zero_fills(self):
        frame = pd.DataFrame({"date": [date(2026, 1, 1), date(2026, 1, 3)], "amount": [100.0, 50.0]})
        s = daily_series(frame, date(2026, 1, 1), date(2026, 1, 4))
        self.assertEqual(list(s.values), [100.0, 0.0, 50.0, 0.0])

    def test_runway_and_projection(self):
        s = pd.Series([200.0] * 20, index=pd.date_range("2026-01-01", periods=20))
        r = compute_baseline(s, balance=3000, today=date(2026, 1, 20), horizon_days=30, upcoming_obligations=500)
        self.assertAlmostEqual(r.burn_rate, 200.0)
        self.assertAlmostEqual(r.runway_days, 15.0)
        self.assertEqual(r.runway_date, date(2026, 2, 4))
        self.assertAlmostEqual(r.projected_balance, 3000 - 6000 - 500)

    def test_short_history_uses_average(self):
        s = pd.Series([100.0, 300.0], index=pd.date_range("2026-01-01", periods=2))
        r = compute_baseline(s, balance=1000, today=date(2026, 1, 2))
        self.assertIn("all 2", r.burn_rate_basis)
        self.assertAlmostEqual(r.burn_rate, 200.0)

    def test_zero_spending_has_no_runway(self):
        s = pd.Series([0.0] * 10, index=pd.date_range("2026-01-01", periods=10))
        self.assertIsNone(compute_baseline(s, 500, date(2026, 1, 10)).runway_days)


class ForecastingTests(SimpleTestCase):
    def test_backtest_perfect_on_constant_series(self):
        s = pd.Series([100.0] * 60, index=pd.date_range("2026-01-01", periods=60))
        scores, mean_actual = backtest(s, horizon=7)
        self.assertAlmostEqual(scores[BASELINE_NAME].mae, 0.0)
        self.assertAlmostEqual(mean_actual, 700.0)

    def test_backtest_uses_only_past_data(self):
        # a sudden jump in the future must not leak into earlier predictions
        values = [100.0] * 40 + [1000.0] * 10
        s = pd.Series(values, index=pd.date_range("2026-01-01", periods=50))
        first_pred = RecentMean().predict(s.iloc[:30], 7)
        self.assertAlmostEqual(first_pred, 700.0)

    def test_selection_prefers_baseline_unless_clearly_better(self):
        s = pd.Series(np.random.default_rng(1).gamma(2, 150, 90), index=pd.date_range("2026-01-01", periods=90))
        scores, _ = backtest(s, horizon=7)
        chosen, reason = select_model(scores)
        if chosen != BASELINE_NAME:
            from .engine.forecasting import paired_mae
            cand, base, _ = paired_mae(scores[chosen], scores[BASELINE_NAME])
            self.assertLessEqual(cand, base * 0.95)
        self.assertTrue(reason)

    def test_zero_error_baseline_does_not_crash(self):
        s = pd.Series([100.0] * 60, index=pd.date_range("2026-01-01", periods=60))
        scores, _ = backtest(s, horizon=7)
        self.assertEqual(select_model(scores)[0], BASELINE_NAME)

    def test_insufficient_history(self):
        s = pd.Series([50.0] * 10, index=pd.date_range("2026-01-01", periods=10))
        scores, _ = backtest(s, horizon=7)
        chosen, _ = select_model(scores)
        self.assertEqual(chosen, "historical_mean")


class PatternTests(SimpleTestCase):
    def _frame(self, rows):
        return pd.DataFrame(rows, columns=["id", "date", "amount", "category", "description"])

    def test_anomaly_detected_with_robust_z(self):
        today = date(2026, 3, 1)
        rows = [(i, today - timedelta(days=30 - i), 200 + (i % 3) * 20, "Food", "") for i in range(20)]
        rows.append((99, today - timedelta(days=1), 2500, "Food", "Party food"))
        flagged = detect_anomalies(self._frame(rows), today)
        self.assertEqual(flagged[0]["id"], 99)

    def test_no_anomaly_with_few_samples(self):
        today = date(2026, 3, 1)
        rows = [(1, today, 100, "Food", ""), (2, today, 5000, "Food", "")]
        self.assertEqual(detect_anomalies(self._frame(rows), today), [])

    def test_trend_ignores_single_rent_payment(self):
        today = date(2026, 3, 28)
        rows = [(1, date(2026, 3, 1), 5000, "Rent", "")]
        rows += [(10 + i, today - timedelta(days=i), 500 if i < 14 else 100, "Fun", "") for i in range(28)]
        trends = category_trends(self._frame(rows), today)
        cats = [t["category"] for t in trends]
        self.assertNotIn("Rent", cats)
        self.assertIn("Fun", cats)


class SyntheticAndCategorizerTests(TestCase):
    def test_synthetic_data_is_labelled_and_reproducible(self):
        inc1, exp1 = generate_student(seed=3, start=date(2026, 1, 1), days=60)
        inc2, exp2 = generate_student(seed=3, start=date(2026, 1, 1), days=60)
        self.assertTrue(exp1["description"].str.startswith(SYNTHETIC_TAG).all())
        self.assertTrue(exp1.equals(exp2) and inc1.equals(inc2))

    def test_keyword_categoriser(self):
        cats = Category.objects.filter(owner__isnull=True, kind="expense")
        self.assertEqual(suggest_category("Matatu fare to town", cats).slug, "transport")
        self.assertEqual(suggest_category("Lunch at the kibanda", cats).slug, "food")
        self.assertIsNone(suggest_category("random words", cats))


class InsightServiceTests(TestCase):
    def setUp(self):
        self.user = make_user("hassan", semester_end=date.today() + timedelta(days=40))
        add_income(self.user, 8000, on=date.today() - timedelta(days=40))
        for i in range(40):
            add_expense(self.user, 250, on=date.today() - timedelta(days=i))

    def test_empty_user_gets_data_insight(self):
        empty = make_user("empty")
        insights = build_insights(empty)
        self.assertEqual(insights[0]["kind"], FinancialInsight.Kind.DATA)

    def test_insights_include_runway_shortfall_forecast_with_metrics(self):
        kinds = {i["kind"] for i in build_insights(self.user)}
        self.assertTrue({"runway", "shortfall", "forecast"} <= kinds)
        forecast = next(i for i in build_insights(self.user) if i["kind"] == "forecast")
        self.assertIn("model_scores", forecast["metrics"])
        self.assertIn("not guarantees", forecast["assumptions"])

    def test_refresh_is_cached_until_data_changes(self):
        first = refresh_insights(self.user)
        again = refresh_insights(self.user)
        self.assertEqual({i.pk for i in first}, {i.pk for i in again})
        add_expense(self.user, 50)
        changed = refresh_insights(self.user)
        self.assertNotEqual({i.pk for i in first}, {i.pk for i in changed})

    def test_insights_are_user_scoped(self):
        other = make_user("other2")
        refresh_insights(self.user)
        self.client.login(username="other2", password=PASSWORD)
        response = self.client.get(reverse("ai_engine:insights"))
        self.assertNotContains(response, "Estimated financial runway")
        self.assertFalse(FinancialInsight.objects.filter(owner=other, kind="runway").exists())
