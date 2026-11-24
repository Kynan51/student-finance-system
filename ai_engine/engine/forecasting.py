"""
Spending forecasters and an honest rolling-origin evaluation (Phase 9, step 2).

Every model answers the same question: "how much will this student spend in
the next H days?" Models are compared against the simple baselines using a
rolling-origin backtest (walk forward one day at a time, fit only on the past,
predict the next H days, compare with what actually happened).

A learned model is only selected if it beats the recent-average baseline by a
clear margin; otherwise the simpler, more explainable baseline is used.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, Ridge


class InsufficientData(Exception):
    pass


class Forecaster:
    name = "base"
    label = "Base"
    min_history = 7

    def predict(self, history: pd.Series, horizon: int) -> float:
        raise NotImplementedError

    def _check(self, history, needed=None):
        needed = needed or self.min_history
        if len(history) < needed:
            raise InsufficientData(f"{self.name} needs {needed} days, got {len(history)}")


class HistoricalMean(Forecaster):
    name, label, min_history = "historical_mean", "Historical average", 7

    def predict(self, history, horizon):
        self._check(history)
        return float(history.mean()) * horizon


class RecentMean(Forecaster):
    name, label = "recent_mean", "Recent 14-day average"
    window = 14
    min_history = 14

    def predict(self, history, horizon):
        self._check(history)
        return float(history.tail(self.window).mean()) * horizon


class WeekdayProfile(Forecaster):
    """Average spend per weekday over the last 8 weeks (captures weekend spikes)."""

    name, label, min_history = "weekday_profile", "Weekday profile (8 weeks)", 21

    def predict(self, history, horizon):
        self._check(history)
        recent = history.tail(56)
        profile = recent.groupby(recent.index.dayofweek).mean()
        overall = float(recent.mean())
        last = history.index[-1]
        future = pd.date_range(last + pd.Timedelta(days=1), periods=horizon, freq="D")
        return float(sum(profile.get(d.dayofweek, overall) for d in future))


class LinearTrend(Forecaster):
    """Ordinary least squares on the last 28 days (scikit-learn LinearRegression)."""

    name, label, min_history = "linear_trend", "Linear trend (28 days)", 28

    def predict(self, history, horizon):
        self._check(history)
        y = history.tail(28).to_numpy(dtype=float)
        x = np.arange(len(y)).reshape(-1, 1)
        model = LinearRegression().fit(x, y)
        future_x = np.arange(len(y), len(y) + horizon).reshape(-1, 1)
        preds = np.clip(model.predict(future_x), 0, None)
        return float(preds.sum())


class RidgeWindows(Forecaster):
    """
    Supervised regression (scikit-learn Ridge). Each training row is a past
    day t with features [spend in last 7, 14, 28 days, day of month] and
    target = spend over the following H days. Needs a long history.
    """

    name, label = "ridge_windows", "Ridge regression on rolling windows"
    min_history = 28

    def _features(self, cumsum, t, dom):
        last7 = cumsum[t] - cumsum[t - 7]
        last14 = cumsum[t] - cumsum[t - 14]
        last28 = cumsum[t] - cumsum[t - 28]
        return [last7, last14, last28, dom]

    def predict(self, history, horizon):
        values = history.to_numpy(dtype=float)
        n = len(values)
        min_rows = 20
        if n < 28 + horizon + min_rows:
            raise InsufficientData("ridge_windows needs more history")
        cumsum = np.concatenate([[0.0], np.cumsum(values)])
        days_of_month = history.index.day.to_numpy()
        X, y = [], []
        for t in range(28, n - horizon + 1):
            X.append(self._features(cumsum, t, days_of_month[t - 1]))
            y.append(cumsum[t + horizon] - cumsum[t])
        model = Ridge(alpha=1.0).fit(np.array(X), np.array(y))
        x_now = np.array([self._features(cumsum, n, days_of_month[-1])])
        return float(max(model.predict(x_now)[0], 0.0))


ALL_MODELS = [HistoricalMean(), RecentMean(), WeekdayProfile(), LinearTrend(), RidgeWindows()]
BASELINE_NAME = "recent_mean"


@dataclass
class ModelScore:
    name: str
    label: str
    mae: float | None
    rmse: float | None
    n_origins: int
    errors: list = field(default_factory=list, repr=False)

    def as_dict(self):
        return {
            "name": self.name,
            "label": self.label,
            "mae": None if self.mae is None else round(self.mae, 2),
            "rmse": None if self.rmse is None else round(self.rmse, 2),
            "n_origins": self.n_origins,
        }


def backtest(daily: pd.Series, models=None, horizon=7, min_train=28, max_origins=120):
    """Rolling-origin evaluation. Returns {model_name: ModelScore} and mean actual."""
    models = models or ALL_MODELS
    n = len(daily)
    origins = list(range(min_train, n - horizon + 1))
    if len(origins) > max_origins:
        origins = origins[-max_origins:]
    scores = {m.name: [] for m in models}
    actuals = []
    for t in origins:
        hist = daily.iloc[:t]
        actual = float(daily.iloc[t : t + horizon].sum())
        actuals.append(actual)
        for m in models:
            try:
                pred = m.predict(hist, horizon)
                scores[m.name].append((t, pred - actual))
            except InsufficientData:
                continue
    result = {}
    for m in models:
        pairs = scores[m.name]
        errs = np.array([e for _, e in pairs], dtype=float)
        if len(errs):
            result[m.name] = ModelScore(m.name, m.label, float(np.mean(np.abs(errs))), float(np.sqrt(np.mean(errs**2))), len(errs), pairs)
        else:
            result[m.name] = ModelScore(m.name, m.label, None, None, 0)
    mean_actual = float(np.mean(actuals)) if actuals else 0.0
    return result, mean_actual


def paired_mae(candidate, base):
    """MAE of both models on the origins where BOTH produced a forecast (a fair comparison)."""
    base_err = dict(base.errors)
    shared = [(abs(e), abs(base_err[t])) for t, e in candidate.errors if t in base_err]
    if not shared:
        return None, None, 0
    arr = np.array(shared, dtype=float)
    return float(arr[:, 0].mean()), float(arr[:, 1].mean()), len(shared)


def select_model(scores, min_improvement=0.05, min_shared=10):
    """
    Choose the model with the largest error reduction versus the recent-mean
    baseline, measured on the origins both models were tested on. A model is
    only chosen if it beats the baseline by at least `min_improvement` (5%)
    over at least `min_shared` test origins; otherwise keep the baseline.
    Returns (model_name, reason).
    """
    base = scores.get(BASELINE_NAME)
    if not base or base.mae is None:
        return "historical_mean", "Not enough history to evaluate models; using the overall average."
    if base.mae == 0:
        return BASELINE_NAME, "The 14-day average already predicts your spending exactly."
    best_name, best_gain, best_label = BASELINE_NAME, 0.0, None
    for s in scores.values():
        if s.name == BASELINE_NAME or s.mae is None:
            continue
        cand_mae, base_mae, n = paired_mae(s, base)
        if n < min_shared or not base_mae:
            continue
        gain = 1 - cand_mae / base_mae
        if gain >= min_improvement and gain > best_gain:
            best_name, best_gain, best_label = s.name, gain, s.label
    if best_name != BASELINE_NAME:
        return best_name, f"{best_label} reduced error by {best_gain * 100:.0f}% versus the 14-day average on the same test days."
    return BASELINE_NAME, "No model beat the simple 14-day average by 5% or more, so the simpler method is used."


def get_model(name):
    for m in ALL_MODELS:
        if m.name == name:
            return m
    return RecentMean()
