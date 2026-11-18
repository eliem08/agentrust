import contextlib
import io
import json
import os
import random
import tempfile
import unittest

from agentrust.__main__ import main
from agentrust.calibrate import auc, calibrate, load_outcomes, load_weights
from agentrust.core import score
from tests.synth import make_outcomes


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = main(list(argv))
    return code, out.getvalue()


class CalibrateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, name):
        return os.path.join(self.tmp.name, name)

    def test_finds_the_real_signal_and_beats_defaults_out_of_sample(self):
        res = calibrate(make_outcomes())
        w = res["weights"]
        self.assertEqual(max(w, key=w.get), "payment_history")  # disputes drive the synthetic outcome
        self.assertAlmostEqual(sum(w.values()), 1.0, places=3)
        self.assertTrue(res["recommended"])
        self.assertGreater(res["auc_calibrated_cv"], res["auc_default"])
        rates = [b["bad_rate"] for b in res["bands"] if b["bad_rate"] is not None]
        self.assertEqual(rates, sorted(rates))  # worse bands, more bad agents

    def test_labels_with_no_signal_are_not_recommended(self):
        rows = make_outcomes(60, seed=3)
        rng = random.Random(11)
        for r in rows:
            r["bad"] = rng.random() < 0.4  # labels unrelated to behaviour
        try:
            res = calibrate(rows)
        except ValueError as e:  # or: nothing separates good from bad at all
            self.assertIn("built-in weights", str(e))
            return
        self.assertLess(res["auc_calibrated_cv"], 0.7)

    def test_too_little_data_or_bad_records_are_refused(self):
        with self.assertRaisesRegex(ValueError, "at least 20"):
            calibrate(make_outcomes(10))
        rows = make_outcomes(40)
        for r in rows:
            r["bad"] = False
        rows[0]["bad"] = True
        with self.assertRaisesRegex(ValueError, "bad outcomes"):
            calibrate(rows)
        p = self.path("o.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump([{"history": [], "bad": "yes"}], fh)
        with self.assertRaisesRegex(ValueError, "true or false"):
            load_outcomes(p)

    def test_weights_change_the_score_and_are_validated(self):
        history = make_outcomes(1, seed=5)[0]["history"]
        only_mix = {"payment_history": 0, "utilization": 0, "history_length": 0, "velocity": 0, "mix": 1}
        p = self.path("w.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump({"weights": only_mix}, fh)
        w = load_weights(p)
        rep = score(history, weights=w)
        self.assertEqual(rep.score, round(300 + 550 * rep.factors["mix"]))
        for bad in ({"mix": 1}, {**only_mix, "mix": -1}, dict.fromkeys(only_mix, 0)):
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(bad, fh)
            with self.assertRaises(ValueError):
                load_weights(p)

    def test_auc(self):
        self.assertEqual(auc([3, 2, 1], [0, 0, 1]), 1.0)
        self.assertEqual(auc([1, 2, 3], [0, 0, 1]), 0.0)
        self.assertEqual(auc([1, 1], [0, 1]), 0.5)

    def test_cli_round_trip(self):
        src = self.path("o.jsonl")
        with open(src, "w", encoding="utf-8") as fh:
            for r in make_outcomes():
                fh.write(json.dumps(r) + "\n")
        out_file = self.path("cal.json")
        code, out = run("calibrate", src, "--out", out_file)
        self.assertEqual(code, 0, out)
        self.assertIn("fitted weights: use them", out)
        hist = self.path("h.json")
        with open(hist, "w", encoding="utf-8") as fh:
            json.dump(make_outcomes(1)[0]["history"], fh)
        code, out = run("score", hist, "--weights", out_file)
        self.assertEqual(code, 0, out)
        self.assertIn("Agent score", out)


if __name__ == "__main__":
    unittest.main()
