"""Fit the score's factor weights to your own outcomes instead of the built-in guesses.

Input: past agents with what happened to them. A JSON list or JSON-lines file of
  {"agent": "a1", "history": [...transactions...], "budget": 500, "bad": true}
where `bad` means the agent later defaulted, committed fraud, or was cut off; use the outcome you care about.

Method: the five factors are computed for every agent exactly as `score` does, then a logistic regression
(L2-regularised, deterministic) predicts `bad` from them. A factor's weight is how strongly a higher value
predicts a good outcome; a factor that points the wrong way gets weight 0 and is reported.

Honesty checks, printed with the result:
- AUC of the built-in weights and of the fitted weights, the fitted ones measured with 5-fold cross-validation
  (each agent scored by a model that never saw it). 0.5 is a coin flip, 1.0 is perfect ranking.
- The fitted weights are recommended only if their cross-validated AUC beats the built-in weights.
- The bad rate in each score band under the fitted weights.
"""

from __future__ import annotations

import json
import math

from .core import BANDS, WEIGHTS, score

FACTORS = tuple(WEIGHTS)
MIN_AGENTS, MIN_EACH = 20, 5


def load_outcomes(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig") as fh:
        text = fh.read()
    stripped = text.lstrip()
    if stripped.startswith("["):
        rows = json.loads(text)
    else:
        rows = []
        for n, line in enumerate(text.splitlines(), 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError as e:
                    raise ValueError(f"{path} line {n}: not JSON ({e})") from None
    out = []
    for i, r in enumerate(rows, 1):
        if not isinstance(r, dict) or not isinstance(r.get("history"), list) or "bad" not in r:
            raise ValueError(f"{path} record {i}: needs 'history' (a list) and 'bad' (true/false)")
        if not isinstance(r["bad"], bool):
            raise ValueError(f"{path} record {i}: 'bad' must be true or false, got {r['bad']!r}")
        out.append(r)
    return out


def _features(rows: list[dict]) -> list[list[float]]:
    feats = []
    for i, r in enumerate(rows, 1):
        try:
            rep = score(r["history"], r.get("budget"))
        except ValueError as e:
            raise ValueError(f"record {i} ({r.get('agent', '?')}): {e}") from None
        feats.append([rep.factors[f] for f in FACTORS])
    return feats


def _sigmoid(z: float) -> float:
    return 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))


def _solve(a: list[list[float]], v: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting (the system is small: one row per factor plus one)."""
    m = [[*row, vi] for row, vi in zip(a, v)]
    k = len(m)
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        if abs(m[c][c]) < 1e-12:
            raise ValueError("the outcome data is degenerate (a factor never varies)")
        for r in range(k):
            if r != c:
                f = m[r][c] / m[c][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [m[i][k] / m[i][i] for i in range(k)]


def fit_logistic(x: list[list[float]], y: list[int], l2: float = 0.01, steps: int = 50):
    """L2-regularised logistic regression by Newton's method; returns (intercept, coefficients). Deterministic.

    l2 is per agent (scaled by n), the intercept is not penalised. Stops when the update is negligible.
    """
    n, k = len(x), len(x[0])
    rows = [[1.0, *xi] for xi in x]
    beta = [0.0] * (k + 1)
    for _ in range(steps):
        grad = [0.0] * (k + 1)
        hess = [[0.0] * (k + 1) for _ in range(k + 1)]
        for xi, yi in zip(rows, y):
            p = _sigmoid(sum(b * v for b, v in zip(beta, xi)))
            s = p * (1 - p)
            for i in range(k + 1):
                grad[i] += (p - yi) * xi[i]
                for j in range(k + 1):
                    hess[i][j] += s * xi[i] * xi[j]
        for i in range(1, k + 1):
            grad[i] += l2 * n * beta[i]
            hess[i][i] += l2 * n
        step = _solve(hess, grad)
        beta = [b - d for b, d in zip(beta, step)]
        if max(abs(d) for d in step) < 1e-8:
            break
    return beta[0], beta[1:]


def auc(scores: list[float], bad: list[int]) -> float:
    """Probability a random good agent outscores a random bad one (ties count half)."""
    good_s = [s for s, b in zip(scores, bad) if not b]
    bad_s = [s for s, b in zip(scores, bad) if b]
    if not good_s or not bad_s:
        return float("nan")
    wins = sum((g > s) + 0.5 * (g == s) for g in good_s for s in bad_s)
    return wins / (len(good_s) * len(bad_s))


def _weights_from(coefs: list[float]) -> tuple[dict, list[str]]:
    # a positive coefficient means a higher factor predicts *bad*: that factor gets no credit
    raw = {f: max(0.0, -c) for f, c in zip(FACTORS, coefs)}
    backwards = [f for f, c in zip(FACTORS, coefs) if c > 0]
    total = sum(raw.values())
    if total <= 0:
        raise ValueError("no factor separates good from bad agents in this data; keep the built-in weights")
    return {f: round(v / total, 4) for f, v in raw.items()}, backwards


def _weighted(feats: list[list[float]], weights: dict) -> list[float]:
    return [300 + 550 * sum(weights[f] * v for f, v in zip(FACTORS, row)) for row in feats]


def calibrate(rows: list[dict], folds: int = 5) -> dict:
    bad = [int(r["bad"]) for r in rows]
    if len(rows) < MIN_AGENTS or min(sum(bad), len(bad) - sum(bad)) < MIN_EACH:
        raise ValueError(
            f"need at least {MIN_AGENTS} agents with {MIN_EACH}+ good and {MIN_EACH}+ bad outcomes; "
            f"got {len(rows)} ({sum(bad)} bad)"
        )
    feats = _features(rows)
    _, coefs = fit_logistic(feats, bad)
    weights, backwards = _weights_from(coefs)
    # cross-validated: every agent scored by weights fitted without it
    cv_scores = [0.0] * len(rows)
    for f in range(folds):
        test = [i for i in range(len(rows)) if i % folds == f]
        train = [i for i in range(len(rows)) if i % folds != f]
        if not test:
            continue
        _, c = fit_logistic([feats[i] for i in train], [bad[i] for i in train])
        try:
            w, _ = _weights_from(c)
        except ValueError:
            w = dict(WEIGHTS)
        for i, s in zip(test, _weighted([feats[i] for i in test], w)):
            cv_scores[i] = s
    auc_default = auc(_weighted(feats, WEIGHTS), bad)
    auc_cv = auc(cv_scores, bad)
    fitted = _weighted(feats, weights)
    bands = []
    for floor, name, _, _ in BANDS:
        upper = next((f for f, *_ in reversed(BANDS) if f > floor), 10_000)
        members = [b for s, b in zip(fitted, bad) if floor <= round(s) < upper]
        bands.append(
            {
                "band": name,
                "agents": len(members),
                "bad_rate": round(sum(members) / len(members), 3) if members else None,
            }
        )
    return {
        "weights": weights,
        "recommended": auc_cv > auc_default,
        "auc_default": round(auc_default, 4),
        "auc_calibrated_cv": round(auc_cv, 4),
        "agents": len(rows),
        "bad": sum(bad),
        "backwards_factors": backwards,
        "bands": bands,
    }


def load_weights(path: str) -> dict:
    """Weights from a calibration file (or a plain {factor: weight} object), checked and normalised."""
    with open(path, encoding="utf-8-sig") as fh:
        doc = json.load(fh)
    w = doc.get("weights", doc) if isinstance(doc, dict) else None
    if not isinstance(w, dict) or set(w) != set(FACTORS):
        raise ValueError(f"{path}: weights must name exactly {list(FACTORS)}")
    vals = {}
    for k, v in w.items():
        if not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise ValueError(f"{path}: weight {k} must be a number >= 0")
        vals[k] = float(v)
    total = sum(vals.values())
    if total <= 0:
        raise ValueError(f"{path}: weights sum to zero")
    return {k: v / total for k, v in vals.items()}
