"""
Transparent statistical baselines (Phase 9, step 1).

Inputs are plain pandas objects so this module has no Django dependency.
"""
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd


def daily_series(expenses: pd.DataFrame, start: date, end: date) -> pd.Series:
    """
    Turn an expenses frame (columns: date, amount) into a zero-filled daily
    spending series. Days with no recorded spending count as 0.
    """
    index = pd.date_range(start, end, freq="D")
    if expenses is None or expenses.empty:
        return pd.Series(0.0, index=index)
    frame = expenses.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["amount"] = frame["amount"].astype(float)
    series = frame.groupby("date")["amount"].sum()
    return series.reindex(index, fill_value=0.0)


@dataclass
class BaselineResult:
    days_of_history: int
    average_daily: float
    recent_daily: float
    burn_rate: float
    burn_rate_basis: str
    balance: float
    runway_days: float | None
    runway_date: date | None
    horizon_days: int
    projected_spending: float
    projected_balance: float
    upcoming_obligations: float

    def as_dict(self):
        return {
            "days_of_history": self.days_of_history,
            "average_daily": round(self.average_daily, 2),
            "recent_daily": round(self.recent_daily, 2),
            "burn_rate": round(self.burn_rate, 2),
            "burn_rate_basis": self.burn_rate_basis,
            "balance": round(self.balance, 2),
            "runway_days": None if self.runway_days is None else round(self.runway_days, 1),
            "runway_date": self.runway_date.isoformat() if self.runway_date else None,
            "horizon_days": self.horizon_days,
            "projected_spending": round(self.projected_spending, 2),
            "projected_balance": round(self.projected_balance, 2),
            "upcoming_obligations": round(self.upcoming_obligations, 2),
        }


def compute_baseline(
    daily: pd.Series,
    balance: float,
    today: date,
    horizon_days: int = 30,
    recent_window: int = 14,
    upcoming_obligations: float = 0.0,
) -> BaselineResult:
    """
    * average daily spending over the full history
    * recent spending rate over the last `recent_window` days
    * burn rate = recent rate when there is enough history, else the average
    * runway = available balance / burn rate
    * projected balance = balance - burn * horizon - unpaid obligations
    Income is NOT forecast: student income is lumpy and irregular, so we only
    count money that has already been recorded.
    """
    days = int(len(daily))
    avg = float(daily.mean()) if days else 0.0
    recent = float(daily.tail(recent_window).mean()) if days else 0.0
    if days >= recent_window:
        burn, basis = recent, f"last {recent_window} days"
    else:
        burn, basis = avg, f"all {days} recorded days"

    runway_days, runway_date = None, None
    if burn > 0:
        runway_days = max(balance, 0.0) / burn
        runway_date = today + timedelta(days=int(np.floor(runway_days)))

    projected_spending = burn * horizon_days
    projected_balance = balance - projected_spending - upcoming_obligations
    return BaselineResult(
        days_of_history=days,
        average_daily=avg,
        recent_daily=recent,
        burn_rate=burn,
        burn_rate_basis=basis,
        balance=float(balance),
        runway_days=runway_days,
        runway_date=runway_date,
        horizon_days=horizon_days,
        projected_spending=projected_spending,
        projected_balance=projected_balance,
        upcoming_obligations=float(upcoming_obligations),
    )
