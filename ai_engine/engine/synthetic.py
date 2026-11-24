"""
SYNTHETIC Kenyan university student finance data.

!!! These records are generated, not collected from real students. !!!
They exist so the analytics engine can be developed and evaluated before
consented participant data is available (roadmap Phase 9, proposal 3.8).

The generator models typical patterns described in the proposal:
  * a lump-sum HELB disbursement near the semester start (sometimes late)
  * irregular parental/guardian allowances
  * occasional side-hustle income
  * daily food from vibandaski, transport, internet bundles, printing,
    monthly rent, and weekend entertainment spikes
"""
from datetime import date, timedelta

import numpy as np
import pandas as pd

SYNTHETIC_TAG = "[SYNTHETIC]"


def generate_student(seed=0, start=None, days=120):
    rng = np.random.default_rng(seed)
    start = start or (date.today() - timedelta(days=days - 1))
    incomes, expenses = [], []

    def add_income(d, amount, cat, desc):
        incomes.append({"date": d, "amount": round(float(amount), 2), "category": cat, "description": f"{SYNTHETIC_TAG} {desc}"})

    def add_expense(d, amount, cat, desc):
        expenses.append({"date": d, "amount": round(float(amount), 2), "category": cat, "description": f"{SYNTHETIC_TAG} {desc}"})

    helb_delay = int(rng.integers(0, 25))  # late disbursement is common
    add_income(start + timedelta(days=helb_delay), rng.choice([30000, 35000, 40000, 45000]), "helb", "HELB disbursement")
    add_income(start, rng.integers(5000, 9000), "parents", "Upkeep from parents")

    food_level = rng.uniform(150, 260)
    rent = float(rng.choice([4000, 4500, 5000, 6000]))
    party_prob = rng.uniform(0.15, 0.45)
    hustle_prob = rng.uniform(0.02, 0.08)

    for i in range(days):
        d = start + timedelta(days=i)
        weekday = d.weekday()
        # tighter spending before HELB arrives, looser right after
        mood = 0.75 if i < helb_delay else (1.25 if i < helb_delay + 10 else 1.0)

        if d.day == 1 or i == 0:
            add_expense(d, rent, "accommodation", "Hostel rent")
        if rng.random() < 0.93:
            add_expense(d, max(60, rng.normal(food_level * mood, 60)), "food", "Lunch at kibanda")
        if weekday < 5 and rng.random() < 0.6:
            add_expense(d, rng.choice([50, 70, 100, 150]), "transport", "Matatu fare")
        if rng.random() < 0.18:
            add_expense(d, rng.choice([99, 250, 500]), "internet", "Data bundles")
        if weekday < 5 and rng.random() < 0.12:
            add_expense(d, rng.integers(20, 200), "education", "Printing notes")
        if weekday >= 4 and rng.random() < party_prob * mood:
            add_expense(d, rng.gamma(2.0, 400), "entertainment", "Weekend outing")
        if rng.random() < 0.05:
            add_expense(d, rng.integers(200, 1500), "personal", "Toiletries and personal items")
        if rng.random() < hustle_prob:
            add_income(d, rng.integers(500, 3000), "side-hustle", "Side hustle payment")
        if d.day == 1 and i > 0:
            add_income(d, rng.integers(5000, 9000), "parents", "Monthly upkeep from parents")
        if d.day == 15 and rng.random() < 0.4:
            add_income(d, rng.integers(1500, 5000), "parents", "Allowance top-up")
        # rare one-off big purchase -> useful for anomaly testing
        if rng.random() < 0.01:
            add_expense(d, rng.integers(2500, 6000), "entertainment", "Concert ticket")

    return pd.DataFrame(incomes), pd.DataFrame(expenses)
