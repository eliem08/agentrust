"""Agent credit scoring."""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

__all__ = ["WEIGHTS", "Txn", "Report", "score", "BANDS"]

WEIGHTS = {"payment_history": 0.35, "utilization": 0.30, "history_length": 0.15, "velocity": 0.10, "mix": 0.10}
BAD = {"disputed": 1.0, "chargeback": 1.5, "failed": 0.3, "refunded": 0.2}
# (min score, band, per-txn limit, daily limit)
BANDS = [
    (800, "Exceptional", 5000, 20000),
    (740, "Very good", 1000, 5000),
    (670, "Good", 250, 1000),
    (580, "Fair", 50, 200),
    (300, "Poor", 0, 0),
]
REASONS = {
    "payment_history": "Disputes, chargebacks or failed payments on record",
    "utilization": "Spending is high relative to authorised budget",
    "history_length": "Limited length of transaction history",
    "velocity": "Recent spike in transaction frequency",
    "mix": "Few distinct counterparties",
}


@dataclass
class Txn:
    ts: datetime
    amount: float
    merchant: str
    outcome: str = "completed"

    @classmethod
    def from_dict(cls, d):
        return cls(datetime.fromisoformat(d["ts"]), float(d["amount"]), d.get("merchant", "?"), d.get("outcome", "completed"))


@dataclass
class Report:
    score: int
    band: str
    factors: dict
    reasons: list = field(default_factory=list)
    limit_per_txn: float = 0
    limit_daily: float = 0


def _payment_history(txns, now):
    if not txns:
        return 0.5
    good = bad = 0.0
    for t in txns:
        age_days = max((now - t.ts).days, 0)
        w = math.exp(-age_days / 180)  # recent behaviour dominates
        if t.outcome in BAD:
            bad += w * BAD[t.outcome]
        else:
            good += w
    return good / (good + 3 * bad) if good + bad else 0.5


def _utilization(txns, budget, now):
    if not budget:
        return 0.5
    last30 = sum(t.amount for t in txns if (now - t.ts).days <= 30 and t.outcome == "completed")
    u = last30 / budget
    return 1.0 if u <= 0.1 else max(0.0, 1 - (u - 0.1) / 0.9)


def _history_length(txns, now):
    if not txns:
        return 0.0
    days = (now - min(t.ts for t in txns)).days
    return min(1.0, days / 365)


def _velocity(txns, now):
    if len(txns) < 3:
        return 0.7
    per_day = Counter(t.ts.date() for t in txns)
    span = max((now - min(t.ts for t in txns)).days, 1)
    baseline = len(txns) / span
    recent = sum(n for d, n in per_day.items() if (now.date() - d).days <= 7) / 7
    ratio = recent / baseline if baseline else 1
    return 1.0 if ratio <= 2 else max(0.0, 1 - (ratio - 2) / 8)


def _mix(txns):
    return min(1.0, len({t.merchant for t in txns}) / 8)


def score(history: list[dict], budget: float | None = None, now: datetime | None = None) -> Report:
    txns = [Txn.from_dict(h) for h in history]
    now = now or (max(t.ts for t in txns) if txns else datetime.now())
    factors = {
        "payment_history": _payment_history(txns, now),
        "utilization": _utilization(txns, budget, now),
        "history_length": _history_length(txns, now),
        "velocity": _velocity(txns, now),
        "mix": _mix(txns),
    }
    s = round(300 + 550 * sum(WEIGHTS[k] * v for k, v in factors.items()))
    band, per_txn, daily = next((b, p, d) for floor, b, p, d in BANDS if s >= floor)
    weakest = sorted(factors, key=lambda k: factors[k] * WEIGHTS[k] - WEIGHTS[k])[:2]
    reasons = [REASONS[k] for k in weakest if factors[k] < 0.8]
    return Report(s, band, {k: round(v, 3) for k, v in factors.items()}, reasons, per_txn, daily)
