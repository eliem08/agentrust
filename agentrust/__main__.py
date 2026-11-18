import argparse
import csv
import json
import math
import os
import sys

from .calibrate import calibrate, load_outcomes, load_weights
from .core import score


def _finite_float(s: str) -> float:
    """argparse type: a float that is not nan/inf, so limits and prices cannot be bypassed."""
    v = float(s)
    if not math.isfinite(v):
        raise argparse.ArgumentTypeError(f"must be a finite number, got {s!r}")
    return v


def build_parser():
    ap = argparse.ArgumentParser(prog="agentrust", description="Trust score for spending agents.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score")
    s.add_argument("history", help="JSON list of transactions")
    s.add_argument("--budget", type=_finite_float, help="agent's authorised monthly budget")
    s.add_argument("--json", action="store_true")
    s.add_argument("--weights", help="calibration file from `calibrate` (default: built-in weights)")
    c = sub.add_parser("calibrate", help="fit the factor weights to agents whose outcome you know")
    c.add_argument("outcomes", help='JSON or JSON lines: {"history": [...], "budget": 500, "bad": true}')
    c.add_argument("--out", help="write the calibration here, for score --weights")
    return ap


def _run(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)

    if a.cmd == "calibrate":
        res = calibrate(load_outcomes(a.outcomes))
        print(f"{res['agents']} agents, {res['bad']} bad")
        print(
            f"  ranking quality (AUC): built-in weights {res['auc_default']:.3f}, "
            f"fitted weights {res['auc_calibrated_cv']:.3f} (cross-validated)"
        )
        for k, v in res["weights"].items():
            print(f"  {k:<16} {v:.3f}")
        if res["backwards_factors"]:
            print(f"  set to 0, pointed the wrong way in your data: {', '.join(res['backwards_factors'])}")
        for b in res["bands"]:
            rate = "-" if b["bad_rate"] is None else f"{b['bad_rate']:.0%} bad"
            print(f"  {b['band']:<12} {b['agents']:>5} agents  {rate}")
        verdict = "use them" if res["recommended"] else "they do not beat the built-in weights; keep those"
        print(f"fitted weights: {verdict}")
        if a.out:
            with open(a.out, "w", encoding="utf-8") as fh:
                json.dump(res, fh, indent=2)
            print(f"written to {a.out}; score with --weights {a.out}")
        return 0
    weights = load_weights(a.weights) if a.weights else None
    with open(a.history, encoding="utf-8-sig") as fh:
        rep = score(json.load(fh), a.budget, weights=weights)
    if a.json:
        print(json.dumps(rep.__dict__, indent=2))
        return 0
    print(f"Agent score: {rep.score}  ({rep.band})")
    for k, v in rep.factors.items():
        print(f"  {k:<16} {'#' * round(v * 20):<20} {v:.2f}")
    for r in rep.reasons:
        print(f"  reason: {r}")
    print(f"Recommended limits: ${rep.limit_per_txn:,.0f} per transaction, ${rep.limit_daily:,.0f} per day")
    return 0


def main(argv=None):
    """Run the CLI; a bad input file or argument exits 2 with a one-line error instead of a traceback.

    Set AGENT_ECONOMY_DEBUG=1 to see the full traceback.
    """
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    try:
        return _run(argv)
    except (OSError, ValueError, KeyError, csv.Error) as e:
        if os.environ.get("AGENT_ECONOMY_DEBUG"):
            raise
        msg = e.args[0] if isinstance(e, KeyError) and e.args else e
        print(f"error: {msg}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
