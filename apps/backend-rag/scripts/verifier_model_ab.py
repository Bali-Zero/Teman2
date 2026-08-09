"""Verifier model A/B harness (self-correction latency, increment-1 evidence).

Compares candidate verifier models against the current default
(`gemini-3.5-flash`) on the SAME cases: mean latency, verdict-agreement at the
0.7 pass/fail gate (`VerificationResult.is_valid`, see verification_service.py),
and — since 2026-08-09 — the two error types measured against KNOWN ground
truth. This is the evidence increment-2 needs to decide whether to flip
`VERIFIER_MODEL` (env) to a faster judge — see `self-correction-speed-design.md`
for the full plan. Reasoning.py's self-correction LOGIC is untouched by this
script; it only calls the verifier in isolation.

Each curated triple yields a faithful case AND corrupted twins (see
`build_labelled_cases`). Agreement with the incumbent measures similarity, not
correctness — two models can agree while both being wrong — so the number that
decides a model swap is **FALSE-ACCEPT**: a corrupted draft the candidate waved
through. Positives alone can never show it.

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
logged, skipped) rather than crashing the run — expect `verdicts=0/N` for a
rejected model name, not a traceback.

Read `verdicts=`, not `returned=`. `verify_response()` swallows its own API
errors and hands back a degraded placeholder, so a run where every call failed
still "returns" N times; only `verdicts=` counts judgments that actually
happened, and agreement is computed from those alone.
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import json
import logging
import re
import statistics
import time
from pathlib import Path

from backend.services.rag.verification_service import VerificationService

logger = logging.getLogger("verifier_model_ab")

# (query, draft_answer, context_chunks, should_accept, kind)
Case = tuple[str, str, list[str], bool, str]

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


# ── negative cases: the only way to see a FALSE ACCEPT ──────────────────────
#
# Every curated triple is a POSITIVE: a vetted answer checked against itself,
# which a healthy verifier accepts. Run on positives alone, this harness can
# only ever observe false REJECTS and agreement — so "switch models only if
# the candidate never accepts something the incumbent rejects" was a rule no
# amount of running it could test (adversarial review, Codex, 2026-08-09).
#
# A negative keeps the ORIGINAL vetted answer as context and hands the verifier
# a corrupted draft. The draft now contradicts its own grounding, so accepting
# it IS the failure the verifier exists to prevent. Mutations are deterministic
# — a rerun must be comparable to the run before it, and a seeded RNG would
# make "the candidate looked worse" indistinguishable from "it drew a harder
# sample".

# A number is only worth corrupting if changing it changes a FACT. The first
# draft mutated any digit at all, and on real curated answers that first digit
# is often a list enumerator: turning "(1) LKPM" into "(7) LKPM" produced a
# "corrupted" draft the verifier was RIGHT to accept, and the harness scored
# that correct behaviour as a false accept. Measured on the first run: of 33
# corruptions, the ones that fired on enumerators inflated the incumbent's
# false-accept count. The probe had the disease it was measuring.
#
# So the number must carry semantic weight: a currency, a magnitude word, a
# unit, a month, or a percent sign next to it. Fewer negatives, but every
# negative is a real contradiction of its own context.
_UNIT_BEFORE = r"(?:IDR|Rp\.?|USD|\$|EUR|€|article|artikel|pasal|no\.?)\s*"
# `\b` closes only the WORD alternatives: after "%" there is no word boundary
# (both "%" and the following space are non-word characters), so a trailing
# \b on the whole group silently dropped every percentage.
_UNIT_AFTER = (
    r"\s*(?:%|(?:billion|million|miliar|juta|ribu|thousand|"
    r"year|years|tahun|month|months|bulan|day|days|hari|week|weeks|"
    r"January|February|March|April|May|June|July|August|September|October|"
    r"November|December|"
    r"Januari|Februari|Maret|Mei|Juni|Juli|Agustus|Oktober|Desember)\b)"
)
_NUMBER_RE = re.compile(
    rf"(?:{_UNIT_BEFORE})(\d[\d.,]*\d|\d)|(\d[\d.,]*\d|\d)(?={_UNIT_AFTER})",
    re.IGNORECASE,
)

_INVENTED_CLAIM = (
    " In addition, Ministerial Regulation 41/2023 Article 7 requires a "
    "supplementary deposit of IDR 750 million before the application is "
    "accepted."
)


def corrupt_number(answer: str) -> str | None:
    """Change the first SEMANTICALLY WEIGHTED number to a clearly different one.

    The realistic hallucination shape for this business: right structure, wrong
    figure — a capital threshold, a validity period, a filing date, a fee.

    Returns None when the answer carries no such number, so the caller skips it
    rather than emitting a "negative" that is really faithful. Skipping is the
    safe direction: a missing negative under-counts a model's failures, while a
    bogus negative invents failures that are not there — and the second is the
    one that would get a working model rejected.
    """
    m = _NUMBER_RE.search(answer)
    if not m:
        return None
    # Whichever alternative matched (unit-before or unit-after).
    group = 1 if m.group(1) is not None else 2
    original = m.group(group)
    digits = original.replace(",", "").replace(".", "")
    if not digits or set(digits) == {"0"}:
        return None
    mutated = original.replace(digits[0], "7", 1) if digits[0] != "7" else original + "0"
    if mutated == original:
        return None
    return answer[: m.start(group)] + mutated + answer[m.end(group) :]


def corrupt_with_invented_requirement(answer: str) -> str:
    """Append a fabricated regulation + obligation absent from the context."""
    return answer.rstrip() + _INVENTED_CLAIM


def build_labelled_cases(n: int) -> list[Case]:
    """Positives from curated_qa, plus one corrupted twin per positive.

    Returns ``(query, draft, context, should_accept, kind)``. Context is always
    the vetted answer: what changes between a positive and its twin is only
    the draft under test, so a verdict difference isolates the corruption.
    """
    cases: list[Case] = []
    for query, answer, context in build_triples(n):
        cases.append((query, answer, context, True, "faithful"))
        swapped = corrupt_number(answer)
        if swapped:
            cases.append((query, swapped, context, False, "wrong-number"))
        cases.append(
            (query, corrupt_with_invented_requirement(answer), context, False, "invented-rule"),
        )
    return cases


async def run_model(
    service: VerificationService,
    model: str,
    cases: list[Case],
) -> dict:
    service.model_name = model
    latencies: list[float] = []
    verdicts: list[bool | None] = []
    for query, answer, context, _should_accept, _kind in cases:
        t0 = time.perf_counter()
        try:
            result = await service.verify_response(query, answer, context)
        except Exception as e:  # offline diagnostic: keep going, don't crash the run
            logger.warning("model=%s rejected/failed on a case: %s", model, e)
            verdicts.append(None)
            continue
        latencies.append(time.perf_counter() - t0)
        # A placeholder verdict (verdict_available=False) is not a real
        # pass/fail — exclude it from agreement math, same as reasoning.py
        # never lets it gate self-correction.
        verdicts.append(result.is_valid if result.verdict_available else None)
    mean_latency = statistics.mean(latencies) if latencies else float("nan")
    # Two DIFFERENT counts, deliberately not collapsed into one.
    # verify_response() catches its own API errors and returns a degraded
    # result, so "the call did not raise" says nothing about whether a verdict
    # was produced: counting returns alone reported ok=25/25 on a run where
    # every single verdict was unavailable (a transient 403 on the API key,
    # 2026-08-09). A counter that measures survival cannot fail.
    return {
        "model": model,
        "mean_latency_s": mean_latency,
        "verdicts": verdicts,
        "n_returned": len(latencies),
        "n_verdict": sum(1 for v in verdicts if v is not None),
    }


def score_against_truth(cases: list[Case], verdicts: list[bool | None]) -> dict:
    """Split the verdicts into the two errors that are NOT interchangeable.

    A false REJECT costs a rewrite. A false ACCEPT ships an unfaithful answer
    to a client, which is the whole reason the verifier exists — so they are
    reported separately and never averaged into one "accuracy".
    """
    false_accept: list[str] = []
    false_reject = 0
    graded = 0
    for (_q, _a, _c, should_accept, kind), verdict in zip(cases, verdicts, strict=False):
        if verdict is None:
            continue
        graded += 1
        if verdict and not should_accept:
            false_accept.append(kind)
        elif not verdict and should_accept:
            false_reject += 1
    return {"graded": graded, "false_accept": false_accept, "false_reject": false_reject}


async def main(n: int) -> None:
    cases = build_labelled_cases(n)
    n_pos = sum(1 for c in cases if c[3])
    logger.info(
        "Running verifier A/B on %d cases (%d faithful, %d corrupted) — NO client PII",
        len(cases),
        n_pos,
        len(cases) - n_pos,
    )

    service = VerificationService()
    results: dict[str, dict] = {}
    for model in CANDIDATE_MODELS:
        print(f"\n=== {model} ===")
        res = await run_model(service, model, cases)
        results[model] = res
        print(
            f"  verdicts={res['n_verdict']}/{len(cases)}  "
            f"(returned={res['n_returned']})  mean_latency={res['mean_latency_s']:.2f}s",
        )
        if res["n_verdict"] < res["n_returned"]:
            print(
                f"  ⚠️  {res['n_returned'] - res['n_verdict']} call(s) came back WITHOUT a "
                "verdict — the verifier degraded (check its log for the error type).",
            )
        truth = score_against_truth(cases, res["verdicts"])
        res["truth"] = truth
        fa = truth["false_accept"]
        detail = ""
        if fa:
            kinds = ", ".join(f"{k}×{fa.count(k)}" for k in sorted(set(fa)))
            detail = f" [{kinds}]"
        print(
            f"  FALSE-ACCEPT={len(fa)}{detail}  false-reject={truth['false_reject']}  "
            f"(graded={truth['graded']})",
        )

    baseline = results.get("gemini-3.5-flash")
    if not baseline or baseline["n_verdict"] == 0:
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
    parser.add_argument(
        "--n",
        type=int,
        default=10,
        help="number of SOURCE triples to sample; each yields up to 3 cases "
        "(1 faithful + 2 corrupted), so --n 25 runs up to 75 calls per model",
    )
    args = parser.parse_args()
    asyncio.run(main(args.n))
