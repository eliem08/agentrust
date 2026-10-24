import argparse
import json
import sys

from .core import score


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent-fico", description="Trust score for spending agents.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score")
    s.add_argument("history", help="JSON list of transactions")
    s.add_argument("--budget", type=float, help="agent's authorised monthly budget")
    s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    with open(a.history, encoding="utf-8") as fh:
        rep = score(json.load(fh), a.budget)
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


if __name__ == "__main__":
    sys.exit(main())
