import unittest
from datetime import datetime, timedelta

from agent_fico import score

NOW = datetime(2026, 10, 24)


def hist(n, outcome="completed", merchants=10, days=400, amount=10):
    return [
        {
            "ts": (NOW - timedelta(days=days - i * days // n)).isoformat(),
            "amount": amount,
            "merchant": f"m{i % merchants}",
            "outcome": outcome,
        }
        for i in range(n)
    ]


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

    def test_outcome_case_cannot_launder_disputes(self):
        clean = score(hist(30), budget=5000, now=NOW).score
        for outcome in ("Chargeback", "DISPUTED", " failed "):
            with self.subTest(outcome=outcome):
                h = hist(30)
                for t in h[-6:]:
                    t["outcome"] = outcome
                self.assertLess(score(h, budget=5000, now=NOW).score, clean)

    def test_made_up_outcomes_earn_no_payment_credit(self):
        honest = hist(30)
        honest[-1]["outcome"] = "disputed"
        padded = honest + [dict(t, outcome=o) for t, o in zip(hist(10), ["totally-fine-trust-me", "pending"] * 5)]
        self.assertEqual(
            score(padded, budget=5000, now=NOW).factors["payment_history"],
            score(honest, budget=5000, now=NOW).factors["payment_history"],
        )

    def test_negative_or_nan_amounts_and_bad_budgets_are_rejected(self):
        for amount in (-5000, float("nan"), float("inf")):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                score(hist(5, amount=amount), budget=1000, now=NOW)
        for budget in (0, -100, float("nan")):
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                score(hist(5), budget=budget, now=NOW)

    def test_future_dated_records_do_not_pad_history(self):
        real = score(hist(5, days=20), budget=5000, now=NOW)
        padded = hist(5, days=20) + [
            {"ts": (NOW + timedelta(days=d)).isoformat(), "amount": 1, "merchant": f"x{d}"} for d in range(1, 40)
        ]
        self.assertEqual(score(padded, budget=5000, now=NOW).score, real.score)

    def test_mixed_timezones_do_not_crash(self):
        h = hist(10)
        h[0]["ts"] = "2025-11-01T10:00:00Z"
        h[1]["ts"] = "2025-11-02T10:00:00+05:30"
        self.assertGreaterEqual(score(h, budget=5000).score, 300)

    def test_non_list_history_is_a_clean_error(self):
        for bad in (None, {"ts": "x"}, [1, 2]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                score(bad, now=NOW)


if __name__ == "__main__":
    unittest.main()
