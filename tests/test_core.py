import unittest
from datetime import datetime, timedelta

from agent_fico import score

NOW = datetime(2026, 10, 24)


def hist(n, outcome="completed", merchants=10, days=400, amount=10):
    return [{"ts": (NOW - timedelta(days=days - i * days // n)).isoformat(), "amount": amount,
             "merchant": f"m{i % merchants}", "outcome": outcome} for i in range(n)]


class Tests(unittest.TestCase):
    def test_clean_long_history_scores_high(self):
        r = score(hist(60), budget=5000, now=NOW)
        self.assertGreaterEqual(r.score, 800)
        self.assertEqual(r.band, "Exceptional")
        self.assertEqual(r.reasons, [])

    def test_disputes_hurt(self):
        good = score(hist(30), budget=5000, now=NOW).score
        h = hist(30)
        for t in h[-5:]:
            t["outcome"] = "chargeback"
        bad = score(h, budget=5000, now=NOW)
        self.assertLess(bad.score, good - 100)
        self.assertTrue(any("Disputes" in r for r in bad.reasons))

    def test_thin_file_and_high_utilization(self):
        r = score(hist(2, merchants=1, days=5, amount=900), budget=1000, now=NOW)
        self.assertLess(r.score, 670)
        self.assertLessEqual(r.limit_per_txn, 50)

    def test_bounds(self):
        self.assertGreaterEqual(score([], now=NOW).score, 300)


if __name__ == "__main__":
    unittest.main()
