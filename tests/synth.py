"""Deterministic synthetic outcomes for tests and the example file. Not real agents.

Bad agents dispute and charge back more often and run closer to their budget; everything else is shared
noise, so the calibration has a real but imperfect signal to find.
"""

import random
from datetime import datetime, timedelta


def make_outcomes(n: int = 80, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    end = datetime(2026, 11, 1)
    rows = []
    for i in range(n):
        bad = rng.random() < 0.35
        budget = rng.choice([200, 500, 1000, 2000])
        days = rng.randint(30, 400)
        txns = []
        for _ in range(rng.randint(8, 40)):
            ts = end - timedelta(days=rng.randint(0, days), hours=rng.randint(0, 23))
            r = rng.random()
            if bad:
                outcome = (
                    "chargeback" if r < 0.12 else "disputed" if r < 0.25 else "failed" if r < 0.32 else "completed"
                )
            else:
                outcome = "disputed" if r < 0.03 else "failed" if r < 0.07 else "completed"
            share = rng.uniform(0.02, 0.12) if bad else rng.uniform(0.005, 0.05)
            txns.append(
                {
                    "ts": ts.isoformat(),
                    "amount": round(budget * share, 2),
                    "merchant": f"m{rng.randint(1, 12)}",
                    "outcome": outcome,
                }
            )
        rows.append({"agent": f"agent-{i:03d}", "budget": budget, "bad": bad, "history": txns})
    return rows
