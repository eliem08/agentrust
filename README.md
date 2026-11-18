<!-- sell-kit:start -->
# Agentrust

[![CI](https://github.com/eliem08/agentrust/actions/workflows/ci.yml/badge.svg)](https://github.com/eliem08/agentrust/actions/workflows/ci.yml)

> **A 300-850 trust score for AI agents before you let them spend money.**

**Who it's for:** Merchants, marketplaces and payment teams accepting agent-initiated purchases.

**The problem:** Agents are starting to pay for things, and merchants have no way to tell a reliable agent from a risky one.

**What you get:** Score an agent's transaction history into a 300-850 band with reason codes and recommended per-transaction and daily limits; weights calibrate to your own good and bad outcomes, with an out-of-sample check.

## Quickstart

Customers receive a release archive with the wheel and the examples. Python 3.10+ and no other dependencies.

```bash
pip install agentrust-0.1.0-py3-none-any.whl
agentrust score examples/history.json --budget 2000
agentrust score examples/history.json --json
agentrust calibrate examples/outcomes.jsonl
```

## Web app and API

Every command is also a JSON API endpoint and a browser form, served by the built-in web app.

```bash
agentrust-web --port 8000          # then open http://127.0.0.1:8000
agentrust-web keys create --label "first customer"   # prints an API key (stored hashed)
docker build -t agentrust . && docker run -p 8000:8000 -e API_KEYS=sk_... -v agentrust-data:/data agentrust
```

Every API call needs `Authorization: Bearer <key>` once any key exists; a server on a public address refuses to start without one. Calls are rate-limited per key (60/min, `--rate`) and metered: `agentrust-web usage` prints calls per key for billing.

Endpoints: `POST /api/score`, `POST /api/calibrate`, plus `GET /healthz` and `GET /api/spec` (machine-readable field list).
Files are sent as `{"name": ..., "content": ...}`, folders as `{"files": [...]}` or a base64 zip.

## Deploy and sell

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/eliem08/agentrust)

`render.yaml` (one click, above) and `fly.toml` (`fly launch --copy-config`) both run the Dockerfile with a persistent `/data` volume and a `/healthz` check.
To sell self-serve, set four variables and point a Stripe webhook at `https://<your-host>/billing/webhook` (events `checkout.session.completed` and `customer.subscription.deleted`):

| Variable | Example |
|---|---|
| `STRIPE_SECRET_KEY` | `sk_live_...` |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` |
| `STRIPE_PRICES` | `team=price_123,business=price_456` |
| `PUBLIC_URL` | `https://agentrust.example.com` |
| `PLAN_QUOTAS` (optional) | `team=10000,business=250000` successful calls per key per month |

Buyers pick a plan on `/pricing`, pay on Stripe Checkout and see their API key once on the success page. Cancelling the subscription revokes the key. A selling server always requires a key.

## Pricing

Monthly plans start with a 14-day free trial. Prices in USD, billed monthly unless noted.

| Plan | Price | Includes |
|---|---|---|
| **Developer** | $49 per month | 10,000 scores a month; Reason codes; Spend-limit bands |
| **Growth** | $499 per month | 250,000 scores a month; Weights calibrated to your outcomes; Hosted API; JSON output |
| **Enterprise** | $2,500 per month | Unlimited scoring; Self-hosted deployment; SLA |

To start a trial or buy a plan, [request access](https://github.com/eliem08/agentrust/issues/new?title=Agentrust%20trial&labels=sales).

Plan note: every plan runs the same software, and every API key unlocks all of it. Monthly call volumes are
enforced when `PLAN_QUOTAS` is set (see Deploy and sell); seat and agent limits are licence terms the code does
not enforce. Support, SLA and done-for-you items are services.

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

## Calibrate to your own outcomes

The weights above are starting values. Once you know how some agents turned out, fit the weights to that:

```bash
agentrust calibrate outcomes.jsonl --out calibration.json
agentrust score history.json --budget 2000 --weights calibration.json
```

`outcomes.jsonl` has one agent per line: `{"agent": "a1", "history": [...], "budget": 500, "bad": true}`, where
`bad` is whatever outcome you want to predict (defaulted, fraud, cut off). You need at least 20 agents, with at
least 5 good and 5 bad.

How the fit works and how you can check it:
- The five factors are computed exactly as `score` computes them. An L2-regularised logistic regression (Newton's
  method, deterministic) then predicts `bad` from them.
- Each factor's weight is how strongly a higher value predicts a good outcome. A factor that points the wrong way
  in your data gets 0 and is named.
- The command prints the ranking quality (AUC) of the built-in weights and of the fitted weights. The fitted
  weights' AUC uses 5-fold cross-validation, so every agent is scored by a model that never saw it. It
  recommends the fitted weights only if they rank better out of sample.
- It shows the bad rate in each band under the fitted weights.

`examples/outcomes.jsonl` is synthetic data for trying the command, not real agents.

## Quickstart

```bash
pip install -e .
agentrust score examples/history.json --budget 2000
agentrust score examples/history.json --budget 2000 --json
agentrust calibrate examples/outcomes.jsonl --out calibration.json
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
