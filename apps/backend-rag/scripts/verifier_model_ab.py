"""Verifier model A/B harness (self-correction latency, increment-1 evidence).

Compares candidate verifier models against the current default
(`gemini-3.5-flash`) on the SAME (query, answer, context) triples: mean
latency per model + verdict-agreement at the 0.7 pass/fail gate
(`VerificationResult.is_valid`, see verification_service.py). This is the
evidence increment-2 needs to decide whether to flip `VERIFIER_MODEL` (env)
to a faster judge — see `self-correction-speed-design.md` for the full plan.
Reasoning.py's self-correction LOGIC is untouched by this script; it only
calls the verifier in isolation.

Triples come from `data/curated_qa/*.jsonl` (pre-vetted, non-`client_specific`
rows only) when present, topped up with a small bundled synthetic sample —
curated_qa is gitignored (`data/curated_qa/*` — see that dir's README) so a
fresh worktree may have zero real rows; the synthetic fallback keeps this
script runnable without the harvested corpus.

PURELY DIAGNOSTIC: this is an offline, manually-run script — it is NOT wired
into the request path, imports nothing from the reasoning/orchestrator
pipeline, and calling it does not affect prod. Run manually, NON-PII INPUTS
ONLY (curated_qa is pre-vetted non-client-specific; never point --n at raw
CRM/WhatsApp data):

    PYTHONPATH=. python scripts/verifier_model_ab.py --n 10

A candidate model name the API doesn't recognize fails per-triple (caught,
logged, skipped) rather than crashing the run — expect `ok=0/N` for a
rejected model name, not a traceback.
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import json
import logging
import statistics
import time
from pathlib import Path

from backend.services.rag.verification_service import VerificationService

logger = logging.getLogger("verifier_model_ab")

# Baseline first — everything else is compared against it.
CANDIDATE_MODELS = [
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3.5-flash-lite",
]

# Non-PII, hand-written fallback sample (visa/tax/KBLI register, no client
# names/IDs) — used to top up when curated_qa has fewer than --n usable rows.
SYNTHETIC_TRIPLES: list[tuple[str, str, list[str]]] = [
    (
        "What is the minimum paid-up capital for a PT PMA in Indonesia?",
        "Under BKPM Regulation 5/2025, the minimum paid-up capital for a PT "
        "PMA is IDR 2.5 billion, unless the specific KBLI code and location "
        "require more than IDR 10 billion in total investment, in which "
        "case a higher threshold applies per KBLI per location.",
        [
            "BKPM Reg 5/2025 Art 12: minimum paid-up capital for PT PMA is "
            "IDR 2,500,000,000 (2.5 billion rupiah), replacing the prior "
            "4/2021 threshold.",
            "Investment exceeding IDR 10 billion per KBLI code per location "
            "triggers additional capital requirements under the same "
            "regulation.",
        ],
    ),
    (
        "Can a KITAS holder open a personal bank account in Bali?",
        "Yes, a valid KITAS (limited stay permit) is generally accepted by "
        "Indonesian banks as a form of ID for opening a personal savings "
        "account, alongside a passport and NPWP if available.",
        [
            "OJK consumer banking guidance: foreign nationals holding a "
            "valid KITAS/KITAP may open a rupiah savings account subject to "
            "bank internal KYC policy.",
        ],
    ),
    (
        "What KBLI code covers a beach club / restaurant with entertainment?",
        "A combined beach club and restaurant with live entertainment "
        "typically falls under KBLI 56101 (restaurant) with an additional "
        "KBLI 93290 (other recreational activities) if entertainment is a "
        "core, separately billed activity.",
        [
            "KBLI 2020 code 56101: restaurant activities providing food and "
            "beverage service with table service.",
            "KBLI 2020 code 93290: other amusement and recreation activities "
            "not elsewhere classified, including venues offering live "
            "entertainment.",
        ],
    ),
    (
        "Is annual SPT Tahunan mandatory for a dormant PT PMA with zero revenue?",
        "Yes. Even a dormant PT PMA with zero revenue must file the annual "
        "corporate tax return (SPT Tahunan Badan) — a NIHIL (zero) filing "
        "is still a filing, and skipping it risks administrative penalties "
        "and NPWP deactivation.",
        [
            "UU KUP Art 3-4: every taxpayer with an active NPWP must submit "
            "SPT Tahunan annually regardless of revenue; a NIHIL return "
            "satisfies the obligation but is still required.",
        ],
    ),
    (
        "How long does an E33 Second Home visa allow continuous stay?",
        "The E33 Second Home visa is a 5- or 10-year multiple-entry visa; "
        "each individual stay is not capped at a fixed number of days the "
        "way a tourist visa is, but the holder must maintain the qualifying "
        "deposit/property investment for the visa's validity period.",
        [
            "Permenkumham on Second Home Visa (E33): validity 5 or 10 "
            "years, multiple entry, contingent on maintaining the "
            "qualifying deposit or property investment threshold.",
        ],
    ),
]


def load_curated_qa_triples(limit: int) -> list[tuple[str, str, list[str]]]:
    """Best-effort load of (question, answer, [answer]) rows from curated_qa.

    curated_qa rows don't carry a separate "context" field — the vetted
    answer IS the ground truth, so it doubles as both draft-under-test and
    its own grounding context (a self-consistency probe: does the verifier
    still call a pre-vetted answer "verified" against itself?). Skips
    question-only seeds (answer is null) and `client_specific` rows.
    """
    repo_root = Path(__file__).resolve().parents[1]
    pattern = str(repo_root / "data" / "curated_qa" / "*.jsonl")
    triples: list[tuple[str, str, list[str]]] = []
    for path in sorted(glob.glob(pattern)):
        with open(path, encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                answer = row.get("answer")
                if not answer or row.get("client_specific"):
                    continue
                triples.append((row["question"], answer, [answer]))
                if len(triples) >= limit:
                    return triples
    return triples


def build_triples(n: int) -> list[tuple[str, str, list[str]]]:
    triples = load_curated_qa_triples(n)
    if len(triples) < n:
        needed = n - len(triples)
        logger.info(
            "curated_qa yielded %d/%d usable rows — topping up with %d synthetic sample(s)",
            len(triples),
            n,
            min(needed, len(SYNTHETIC_TRIPLES)),
        )
        triples = triples + SYNTHETIC_TRIPLES[:needed]
    return triples[:n]


async def run_model(
    service: VerificationService,
    model: str,
    triples: list[tuple[str, str, list[str]]],
) -> dict:
    service.model_name = model
    latencies: list[float] = []
    verdicts: list[bool | None] = []
    for query, answer, context in triples:
        t0 = time.perf_counter()
        try:
            result = await service.verify_response(query, answer, context)
        except Exception as e:  # offline diagnostic: keep going, don't crash the run
            logger.warning("model=%s rejected/failed on a triple: %s", model, e)
            verdicts.append(None)
            continue
        latencies.append(time.perf_counter() - t0)
        # A placeholder verdict (verdict_available=False) is not a real
        # pass/fail — exclude it from agreement math, same as reasoning.py
        # never lets it gate self-correction.
        verdicts.append(result.is_valid if result.verdict_available else None)
    mean_latency = statistics.mean(latencies) if latencies else float("nan")
    return {"model": model, "mean_latency_s": mean_latency, "verdicts": verdicts, "n_ok": len(latencies)}


async def main(n: int) -> None:
    triples = build_triples(n)
    logger.info("Running verifier A/B on %d (query, answer, context) triples — NO client PII", len(triples))

    service = VerificationService()
    results: dict[str, dict] = {}
    for model in CANDIDATE_MODELS:
        print(f"\n=== {model} ===")
        res = await run_model(service, model, triples)
        results[model] = res
        print(f"  ok={res['n_ok']}/{len(triples)}  mean_latency={res['mean_latency_s']:.2f}s")

    baseline = results.get("gemini-3.5-flash")
    if not baseline or baseline["n_ok"] == 0:
        print("\nBaseline gemini-3.5-flash produced zero usable verdicts — cannot compute agreement.")
        return

    print("\n=== Verdict agreement vs gemini-3.5-flash (0.7 gate) ===")
    for model, res in results.items():
        if model == "gemini-3.5-flash":
            continue
        pairs = [
            (a, b)
            for a, b in zip(baseline["verdicts"], res["verdicts"], strict=False)
            if a is not None and b is not None
        ]
        if not pairs:
            print(f"  {model}: no comparable pairs (model unavailable or all verdicts unavailable)")
            continue
        agreement = sum(1 for a, b in pairs if a == b) / len(pairs)
        print(
            f"  {model}: agreement={agreement:.0%} (n={len(pairs)})  "
            f"mean_latency={res['mean_latency_s']:.2f}s vs baseline {baseline['mean_latency_s']:.2f}s",
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=10, help="number of (query, answer, context) triples to sample")
    args = parser.parse_args()
    asyncio.run(main(args.n))
