# agent-fico

[![CI](https://github.com/eliem08/agent-fico/actions/workflows/ci.yml/badge.svg)](https://github.com/eliem08/agent-fico/actions/workflows/ci.yml)

> **FICO for agents** — a trust score before an agent can spend money.

Merchants, payment rails and APIs are about to receive purchase requests from
millions of autonomous agents. They need one number that says *should I let
this agent spend?* `agent-fico` computes a 300–850 score from an agent's
transaction history, with reason codes and a recommended spending limit.

## What the MVP does

Five FICO-style factors, each 0–1:

| factor | weight | what it measures |
|---|---|---|
| payment history | 35% | completed vs disputed / charged-back / failed transactions (recent weighs more) |
| utilization | 30% | spend vs. the agent's authorised budget |
| history length | 15% | days since first transaction |
| velocity | 10% | spikes in transactions per day vs. its own baseline |
| counterparty mix | 10% | number of distinct merchants transacted with |

- Score = `300 + 550 × Σ weight × factor`
- Bands: Exceptional / Very good / Good / Fair / Poor
- **Reason codes** for the two weakest factors (adverse-action style)
- **Recommended limit** per transaction and per day by band

## Quickstart

```bash
pip install -e .
agent-fico score examples/history.json --budget 2000
agent-fico score examples/history.json --budget 2000 --json
```

History format: a list of `{"ts": "2026-10-01T12:00:00", "amount": 42.5, "merchant": "acme", "outcome": "completed|disputed|chargeback|refunded|failed"}`.

## Roadmap

- Network-wide bureau: merchants report outcomes, agents carry a portable score
- Owner (human/org) score blended in for new agents ("thin file")
- Signed score attestations verifiable by merchants (pairs with agent-okta)

## Development

Zero runtime dependencies; Python 3.10+.

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m unittest discover -s tests -t .           # unit + CLI smoke tests
ruff check . && ruff format --check .               # lint + format
```

```
agent_fico/core.py       domain logic (pure, importable, fully tested)
agent_fico/__main__.py   CLI (`agent-fico ...` / `python -m agent_fico ...`)
tests/                unit tests + generated CLI smoke tests
examples/             sample inputs used by the docs and smoke tests
```

CI runs lint and tests on Ubuntu and Windows across Python 3.10, 3.12 and 3.13.
Design, data model, trade-offs and production path: **[ARCHITECTURE.md](ARCHITECTURE.md)**.

Part of the [agent-economy](https://github.com/eliem08/agent-economy) portfolio (idea #6).
