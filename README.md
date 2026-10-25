<!-- sell-kit:start -->
# Agentrust

[![CI](https://github.com/eliem08/agentrust/actions/workflows/ci.yml/badge.svg)](https://github.com/eliem08/agentrust/actions/workflows/ci.yml)

> **A 300-850 trust score for AI agents before you let them spend money.**

**Who it's for:** Merchants, marketplaces and payment teams accepting agent-initiated purchases.

**The problem:** Agents are starting to pay for things, and merchants have no way to tell a reliable agent from a risky one.

**What you get:** Score an agent's transaction history into a 300-850 band with reason codes and recommended per-transaction and daily limits.

## Quickstart

Customers receive a release archive with the wheel and the examples. Python 3.10+ and no other dependencies.

```bash
pip install agentrust-0.1.0-py3-none-any.whl
agentrust score examples/history.json --budget 2000
agentrust score examples/history.json --json
```

## Web app and API

Every command is also a JSON API endpoint and a browser form, served by the built-in web app.

```bash
agentrust-web --port 8000          # then open http://127.0.0.1:8000
agentrust-web keys create --label "first customer"   # prints an API key (stored hashed)
docker build -t agentrust . && docker run -p 8000:8000 -e API_KEYS=sk_... -v agentrust-data:/data agentrust
```

Every API call needs `Authorization: Bearer <key>` once any key exists; a server on a public address refuses to start without one. Calls are rate-limited per key (60/min, `--rate`) and metered: `agentrust-web usage` prints calls per key for billing.

Endpoints: `POST /api/score`, plus `GET /healthz` and `GET /api/spec` (machine-readable field list).
Files are sent as `{"name": ..., "content": ...}`, folders as `{"files": [...]}` or a base64 zip.

## Pricing

Every plan starts with a 14-day free trial. Prices in USD, billed monthly unless noted.

| Plan | Price | Includes |
|---|---|---|
| **Developer** | $49 per month | 10,000 scores a month; Reason codes; Spend-limit bands |
| **Growth** | $499 per month | 250,000 scores a month; Custom band thresholds; Batch scoring |
| **Enterprise** | $2,500 per month | Unlimited scoring; Model customisation; SLA |

To start a trial or buy a plan, email **sales@YOUR-DOMAIN.com**.

## Licence

Proprietary. Copyright (c) 2026 eliem08. All rights reserved. Use requires a paid plan or an active trial; see [LICENSE](LICENSE).
<!-- sell-kit:end -->

## What it does

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
agentrust score examples/history.json --budget 2000
agentrust score examples/history.json --budget 2000 --json
```

History format: a list of `{"ts": "2026-10-01T12:00:00", "amount": 42.5, "merchant": "acme", "outcome": "completed|disputed|chargeback|refunded|failed"}`.

## Roadmap

- Network-wide bureau: merchants report outcomes, agents carry a portable score
- Owner (human/org) score blended in for new agents ("thin file")
- Signed score attestations verifiable by merchants (pairs with agentwarden)

## Development

Zero runtime dependencies; Python 3.10+.

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m unittest discover -s tests -t .           # unit + CLI smoke tests
ruff check . && ruff format --check .               # lint + format
```

```
agentrust/core.py       domain logic (pure, importable, fully tested)
agentrust/__main__.py   CLI (`agentrust ...` / `python -m agentrust ...`)
tests/                unit tests + generated CLI smoke tests
examples/             sample inputs used by the docs and smoke tests
```

CI runs lint and tests on Ubuntu and Windows across Python 3.10, 3.12 and 3.13.
Design, data model, trade-offs and production path: **[ARCHITECTURE.md](ARCHITECTURE.md)**.

Part of the [agent-economy](https://github.com/eliem08/agent-economy) portfolio (idea #6).
