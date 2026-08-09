"""Reprice Nuzantara's MEASURED Gemini traffic against any model's list price.

Companion to `research/operations/2026-08-09-llm-model-cost-quality-comparison.md`.
It lived in a scratchpad while that document cited it as the reproducible basis
of its cost table — which made the table unreproducible from the delivered
artifact (adversarial review, Codex, 2026-08-09). It is committed here so the
numbers can be re-derived, and re-derived against a NEW snapshot.

WHAT THIS IS
    A repricing of OUR token counts at SOMEONE ELSE'S published rate.

WHAT THIS IS NOT
    A measurement of what those models would actually cost. Every non-Gemini
    row assumes the same tokenizer, the same answer length and the same amount
    of hidden reasoning as Gemini produced. None of that is guaranteed:
    tokenizers differ by double-digit percentages on the same text, and a model
    that thinks more bills more output. Treat cross-provider rows as an ORDER OF
    MAGNITUDE, and re-measure with `count_tokens` before acting on one.

    The volumes are also a FLOOR. `llm_cost_events` only sees the call sites
    that invoke the recorder, and at least four live Gemini paths do not
    (see the research document, §"the ledger under-counts").

SNAPSHOT DISCIPLINE
    The window is ROLLING: "last 30 days" re-queried hours later returns
    different totals as old rows age out. Mixing two snapshots in one argument
    is what made the first draft of that document irreconcilable with itself.
    So the numbers below are FROZEN with their query, and re-freezing them is a
    deliberate edit, not a refresh.

Usage:
    PYTHONPATH=. python scripts/gemini_cost_model.py
"""

from __future__ import annotations

# ── FROZEN SNAPSHOT ─────────────────────────────────────────────────────────
# Query, verbatim:
#   SELECT model, endpoint, count(*), sum(input_tokens), sum(output_tokens),
#          sum(cost_usd)
#   FROM llm_cost_events
#   WHERE provider = 'gemini' AND ts_utc > now() - interval '30 days'
#   GROUP BY model, endpoint;
# Run 2026-08-09 against Fly Postgres (nuzantara_readonly).
SNAPSHOT = "2026-08-09, rolling 30 days, provider='gemini'"

# endpoint -> (input_tokens, output_tokens, calls, cost_usd_as_recorded)
WORKLOAD: dict[str, tuple[int, int, int, float]] = {
    "rag.gateway.chat": (25_471_696, 295_504, 1_402, 40.87),
    "rag.verifier": (5_291_369, 126_530, 481, 9.08),
    "(nessun endpoint)": (650_475, 21_268, 276, 1.17),
    "test": (7_166, 6_291, 27, 0.07),
    "schematest": (213, 260, 3, 0.00),
}

# Same snapshot, the Gemini rows that are NOT gemini-3.5-flash. They are why
# the dashboard's all-provider figure ($51.31) exceeds the 3.5-flash total.
OTHER_GEMINI_COST = 0.13

TOTAL_IN = sum(v[0] for v in WORKLOAD.values())
TOTAL_OUT = sum(v[1] for v in WORKLOAD.values())
TOTAL_CALLS = sum(v[2] for v in WORKLOAD.values())
TOTAL_RECORDED = sum(v[3] for v in WORKLOAD.values())

GATEWAY_CALLS = WORKLOAD["rag.gateway.chat"][2]

# Stable, byte-identical prefix of every gateway prompt: ZANTARA_MASTER_TEMPLATE
# up to its first variable slot ({user_memory}, at 83.4% of the template).
# Measured 2026-08-09: 18,880 chars ≈ 5,103 tokens (3.7 chars/token heuristic —
# itself an estimate, not a count_tokens call).
STABLE_PREFIX_TOKENS = 5_103


def monthly(
    price_in_per_m: float,
    price_out_per_m: float,
    tok_in: int = TOTAL_IN,
    tok_out: int = TOTAL_OUT,
) -> float:
    """Cost of the frozen volume at a given list price (USD per 1M tokens)."""
    return tok_in / 1e6 * price_in_per_m + tok_out / 1e6 * price_out_per_m


def with_prefix_cache(
    price_in_per_m: float,
    price_out_per_m: float,
    cached_in_per_m: float,
    hit_rate: float = 1.0,
) -> float:
    """Gateway cost if a `hit_rate` share of the stable prefix came from cache.

    ``hit_rate=1.0`` is the CEILING of the saving, not a forecast: eligibility
    for implicit caching (prefix over the 4,096-token threshold) is not the
    same as hitting it, and the ledger did not record cache hits until
    2026-08-09, so the real rate is currently unknown. Storage fees are NOT
    included — implicit caching has none; explicit caching does, and must be
    added by the caller.
    """
    g_in, g_out, _calls, _cost = WORKLOAD["rag.gateway.chat"]
    cached = min(int(GATEWAY_CALLS * STABLE_PREFIX_TOKENS * hit_rate), g_in)
    fresh = g_in - cached
    gateway = (
        fresh / 1e6 * price_in_per_m
        + cached / 1e6 * cached_in_per_m
        + g_out / 1e6 * price_out_per_m
    )
    rest_in = TOTAL_IN - g_in
    rest_out = TOTAL_OUT - g_out
    return gateway + monthly(price_in_per_m, price_out_per_m, rest_in, rest_out)


def report(rows: list[tuple[str, float, float]], baseline: float) -> None:
    """rows = [(model_label, price_in_per_1M, price_out_per_1M), ...]"""
    print(f"{'modello':34} {'in/1M':>8} {'out/1M':>8} {'30gg $':>9} {'vs base':>9}")
    print("-" * 72)
    for label, pin, pout in sorted(rows, key=lambda r: monthly(r[1], r[2])):
        c = monthly(pin, pout)
        delta = f"{c / baseline:.2f}x" if baseline else "—"
        print(f"{label:34} {pin:8.3f} {pout:8.3f} {c:9.2f} {delta:>9}")


if __name__ == "__main__":
    print(f"Snapshot: {SNAPSHOT}")
    print(
        f"gemini-3.5-flash: {TOTAL_IN:,} tok in · {TOTAL_OUT:,} tok out "
        f"· {TOTAL_CALLS:,} chiamate registrate · ${TOTAL_RECORDED:.2f} a ledger",
    )
    at_list = monthly(1.50, 9.00)
    print(f"Ricalcolo a listino ($1.50/$9.00): ${at_list:.2f}  (ledger ${TOTAL_RECORDED:.2f})")
    print(f"Tutti i modelli gemini: ${TOTAL_RECORDED + OTHER_GEMINI_COST:.2f}\n")
    print(
        f"Prefisso stabile: {STABLE_PREFIX_TOKENS:,} tok/chiamata = "
        f"{STABLE_PREFIX_TOKENS * GATEWAY_CALLS / WORKLOAD['rag.gateway.chat'][0]:.0%} "
        f"dell'input del gateway\n",
    )
