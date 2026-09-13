"""Dux measurement run — B2.1. The REAL seat measurement behind the replay record CI uses.

Runs the CHOSEN support signal (ruling I26 candidate (iii): the Codex seat through the
UNCHANGED CodexExecClient.generate adapter, majority of three, split = NOT_SUPPORTED) over
the frozen mandatory manifest AND the B2 supplement, and writes the replay record keyed by
sha256(query || 0x00 || "\n".join(context)) — never by case_id, so no label can travel
through the key.

Nothing here is production code and nothing here writes to the repo's production tree.
"""
from __future__ import annotations

import argparse, asyncio, hashlib, json, sys, time
from pathlib import Path

sys.path.insert(0, "/Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-engine/apps/backend-rag")

from backend.services.rag.agentic._support_signal import (  # noqa: E402
    CodexSupportJudge,
    OllamaSupportJudge,
    evaluate_support,
)

_JUDGE = {"codex": CodexSupportJudge, "ollama": OllamaSupportJudge, "auto": None}

BENCH = Path("/Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-engine/apps/backend-rag/backend/tests/benchmarks/evidence_sufficiency")


def key(query: str, context: list[str]) -> str:
    """Kept BYTE-IDENTICAL with harness.support_record_key(). This copy is the
    script AS RUN for the measurement: the run itself used the concatenated
    form, which the adversarial seat then showed to be non-injective; the
    record was re-keyed with the canonical form below WITHOUT re-measuring a
    verdict (the 114 cases produced 114 distinct keys under both, so the
    collision was latent, never active). A re-run of this script today
    reproduces the record's current keys."""
    payload = json.dumps([query, context], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def one(case: dict, sem: asyncio.Semaphore, judge=None) -> dict:
    async with sem:
        t0 = time.time()
        d = await evaluate_support(case["query"], "\n".join(case["context"]), judge=judge)
        return {
            "key": key(case["query"], case["context"]),
            "case_id": case.get("case_id"),
            "set": case.get("set", "mandatory"),
            "pair_id": case.get("pair_id"),
            "stratum": case.get("stratum"),
            "verdict": str(d.verdict),
            "votes": [str(v) for v in d.votes],
            "judge": d.judge,
            "fallback_used": d.fallback_used,
            "latency_s": round(time.time() - t0, 2),
            "detail": d.detail,
        }


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(BENCH / "manifest_mandatory.json"))
    ap.add_argument("--supplement", default=str(BENCH / "manifest_supplement_b2.json"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--judge", choices=["auto", "codex", "ollama"], default="auto")
    a = ap.parse_args()

    cases: list[dict] = []
    for p, tag in ((a.manifest, "mandatory"), (a.supplement, "supplement")):
        if not Path(p).exists():
            print(f"skip (absent): {p}")
            continue
        for c in json.load(open(p))["cases"]:
            c.setdefault("set", tag)
            cases.append(c)
    if a.limit:
        cases = cases[: a.limit]
    print(f"cases: {len(cases)}")

    sem = asyncio.Semaphore(a.concurrency)
    t0 = time.time()
    cls = _JUDGE[a.judge]
    judge = cls() if cls is not None else None
    records = await asyncio.gather(*(one(c, sem, judge) for c in cases))
    elapsed = round(time.time() - t0, 1)

    record = {
        "schema_version": 1,
        "key_derivation": 'sha256(query + "\\x00" + "\\n".join(context)) — never case_id',
        "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": "Nuzantara (Pro)",
        "method": "ruling I26 candidate (iii): Codex via the UNCHANGED CodexExecClient.generate adapter, majority of 3, split = NOT_SUPPORTED; fallback (ii) local Ollama qwen3.8:27b-mlx, the switch recorded per case",
        "elapsed_s": elapsed,
        "verdicts": {r["key"]: r["verdict"] for r in records},
        "records": records,
    }
    Path(a.out).write_text(json.dumps(record, indent=2, ensure_ascii=False))
    print(f"wrote {a.out} in {elapsed}s")

    import collections
    print("verdicts:", collections.Counter(r["verdict"] for r in records))
    print("judges:", collections.Counter(r["judge"] for r in records))
    print("fallback_used:", sum(1 for r in records if r["fallback_used"]))
    unstable = [r["case_id"] for r in records if len(set(r["votes"])) > 1]
    print("cases with a non-unanimous vote:", len(unstable), unstable[:12])
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
