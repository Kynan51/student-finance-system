"""
Unusual-spending detection and category trend comparison.
"""
from datetime import date, timedelta

import numpy as np
import pandas as pd


def detect_anomalies(expenses: pd.DataFrame, today: date, recent_days=14, z_threshold=3.5, min_samples=6):
    """
    Robust z-score per category using the median and the median absolute
    deviation (MAD), which are not distorted by the very outliers we look for.
    Only expenses in the last `recent_days` are reported.
    Expected columns: id, date, amount, category, description.
    """
    if expenses is None or expenses.empty:
        return []
    frame = expenses.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame["amount"] = frame["amount"].astype(float)
    cutoff = today - timedelta(days=recent_days)
    flagged = []
    for category, group in frame.groupby("category"):
        if len(group) < min_samples:
            continue
        median = float(group["amount"].median())
        mad = float(np.median(np.abs(group["amount"] - median)))
        if mad == 0:
            mad = float(group["amount"].std(ddof=0)) or 1.0
            scale = mad
        else:
            scale = 1.4826 * mad  # makes MAD comparable to a standard deviation
        for row in group[group["date"] >= cutoff].itertuples():
            z = (row.amount - median) / scale
            if z >= z_threshold and row.amount >= 2 * median:
                flagged.append(
                    {
                        "id": int(row.id),
                        "date": row.date.isoformat(),
                        "category": category,
                        "amount": round(row.amount, 2),
                        "typical": round(median, 2),
                        "robust_z": round(float(z), 1),
                        "sample_size": int(len(group)),
                        "description": row.description,
                    }
                )
    flagged.sort(key=lambda r: r["robust_z"], reverse=True)
    return flagged


def category_trends(expenses: pd.DataFrame, today: date, window=14, min_change_pct=40.0, min_change_abs=300.0, min_records=3):
    """
    Compare spending per category: last `window` days vs the window before.
    Categories with fewer than `min_records` transactions across both windows
    (e.g. a once-a-month rent payment) are skipped: a single payment landing
    in one window is timing, not a trend.
    """
    if expenses is None or expenses.empty:
        return []
    frame = expenses.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame["amount"] = frame["amount"].astype(float)
    cur_start = today - timedelta(days=window - 1)
    prev_start = cur_start - timedelta(days=window)
    both = frame[(frame["date"] >= prev_start) & (frame["date"] <= today)]
    counts = both.groupby("category")["amount"].count()
    current = frame[(frame["date"] >= cur_start) & (frame["date"] <= today)].groupby("category")["amount"].sum()
    previous = frame[(frame["date"] >= prev_start) & (frame["date"] < cur_start)].groupby("category")["amount"].sum()
    changes = []
    for category in sorted(set(current.index) | set(previous.index)):
        if int(counts.get(category, 0)) < min_records:
            continue
        cur, prev = float(current.get(category, 0.0)), float(previous.get(category, 0.0))
        diff = cur - prev
        if prev > 0:
            pct = diff / prev * 100
        else:
            pct = None
        if abs(diff) >= min_change_abs and (pct is None or abs(pct) >= min_change_pct):
            changes.append(
                {
                    "category": category,
                    "current": round(cur, 2),
                    "previous": round(prev, 2),
                    "change": round(diff, 2),
                    "change_pct": None if pct is None else round(pct, 0),
                    "window_days": window,
                }
            )
    changes.sort(key=lambda r: abs(r["change"]), reverse=True)
    return changes
