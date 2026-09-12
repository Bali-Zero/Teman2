"""B2.1 acceptance A5 (g1) — direct-finalizer characterization.

Drives the REAL, UNCHANGED `finalize_wa_answer` with the payload shape the
codex leg builds from frozen evidence, once per MANDATORY NEGATIVE case, with
SUBSTANTIVE synthetic candidate text (never a stub). It answers one question:
left to itself, does D8 release substantive advice for a package the engine
判 negative? Every release observed is a VULNERABILITY of the existing
finalizer, never a safety pass of this PR.

No network, no DB, no WhatsApp send: `tell_a_human` is a recording closure and
`thread_id` is a string. Read-only with respect to the repo.
"""
from __future__ import annotations

import asyncio, collections, json, sys
sys.path.insert(0, "/Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-engine/apps/backend-rag")

from backend.services.integrations.wa_finalize import (  # noqa: E402
    FinalizeOutcome, FinalizeProvider, finalize_wa_answer,
)
from backend.services.rag.agentic._abstain_policy import build_abstain_policy  # noqa: E402
from backend.tests.benchmarks.evidence_sufficiency import harness as H  # noqa: E402

BENCH = "/Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-engine/apps/backend-rag/backend/tests/benchmarks/evidence_sufficiency/"

#: Substantive on purpose: a real-looking answer carrying a price and a
#: duration, i.e. exactly the content a client must never receive unsupported.
CANDIDATE = (
    "Pendirian PT PMA memerlukan akta notaris, pengesahan kementerian, NPWP dan NIB "
    "melalui OSS. Harga all-in IDR 20.000.000 dan prosesnya selesai dalam 14 hari kerja."
)


async def one(case: dict, record: dict) -> dict:
    decision = H.decide(case, record)
    policy = build_abstain_policy(case["query"])
    told: list[str] = []

    async def tell(reason: str) -> None:
        told.append(reason)

    result = await finalize_wa_answer(
        data={
            "answer": CANDIDATE,
            "abstain": policy.label_abstains(decision["score"]),
            "abstain_reason": (
                "frozen_evidence_label" if policy.label_abstains(decision["score"]) else None
            ),
            "context_length": len(case["context"]),
            "evidence_score": decision["score"],
        },
        query=case["query"],
        thread_id=f"g1-{case['case_id']}",
        tell_a_human=tell,
        provider=FinalizeProvider.CODEX,
        price_sources=["benchmark-fixture"],
        secret_scan=True,
    )
    text = getattr(result, "text", None) or ""
    return {
        "case_id": case["case_id"],
        "stratum": case["stratum"],
        "score": decision["score"],
        "gate": decision["generation"],
        "outcome": result.outcome.value,
        "defect_reason": getattr(result, "defect_reason", None),
        "released_candidate": CANDIDATE[:40] in text,
        "text_len": len(text),
        "told_a_human": told,
    }


async def main() -> int:
    man = H.load(BENCH + "manifest_mandatory.json")
    record = H.load_support_record(BENCH + "support_verdicts_b2.json")
    negatives = [c for c in man["cases"] if c["stratum"] != "sufficient"]
    rows = [await one(c, record) for c in negatives]
    releases = [r for r in rows if r["released_candidate"]]
    print(f"negatives: {len(rows)}")
    print("outcome x released:", dict(collections.Counter((r["outcome"], r["released_candidate"]) for r in rows)))
    print("defect_reasons:", dict(collections.Counter(r["defect_reason"] for r in rows)))
    print("told_a_human reasons:", dict(collections.Counter(tuple(r["told_a_human"]) for r in rows)))
    print(f"SUBSTANTIVE RELEASES (vulnerability if > 0): {len(releases)}")
    for r in releases[:10]:
        print("  RELEASE", r["case_id"], r["stratum"], r["score"], r["outcome"])
    # determinism: identical inputs, identical outcomes
    again = [await one(c, record) for c in negatives]
    same = all(a == b for a, b in zip(rows, again))
    print("identical inputs keep identical outcomes:", same)
    json.dump({"rows": rows, "deterministic": same}, open(sys.argv[1], "w"), indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
