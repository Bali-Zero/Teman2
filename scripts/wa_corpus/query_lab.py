"""Query lab — iterate on prompt formulations against an already-indexed source.

Reuses sources already loaded in an NB (no re-render/re-add cost) so we can run
MANY prompt variants quickly and score the answers. Used to perfect the
prompt-master (Antonello: "fai tanti test per arrivare alla perfezione").

Scoring (per answer, all source-grounded):
  - n_citations: how many verbatim cited_text references NLM returned
  - foreign_citations: citations from a DIFFERENT source_id (contamination)
  - hits: how many ground-truth facts the answer mentions (recall proxy)
  - misses: ground-truth facts NOT mentioned
  - hallucination_flags: ground-truth NEGATIVES wrongly asserted as present

Usage:
  PYTHONPATH=. apps/backend-rag/.venv/bin/python -m scripts.wa_corpus.query_lab \\
      --nb <NB_ID> --source <SOURCE_ID> --variant v2
"""
from __future__ import annotations

import argparse
import json

from scripts.wa_corpus.query_runner import _nlm

# Ground-truth per real chat — what the recap MUST surface and must NOT invent.
# Keyed by source_id so the lab can score whichever chat is queried.
#
# The REAL ground truth (real client names/phones/companies, tied to real NLM
# source_ids) lives in the untracked, gitignored
# scripts/wa_corpus/_ground_truth_local.py (same GROUND_TRUTH dict shape) —
# these were tracked in THIS file on origin/main until this removal (Builder
# Contract §4, gate G1 on #7468). Recreate that file locally to run this lab
# against real indexed chats. Absent it, GROUND_TRUTH falls back to the
# synthetic fixtures below, which keep the module importable/runnable but
# will not score against a real source_id.
try:
    from scripts.wa_corpus._ground_truth_local import GROUND_TRUTH  # type: ignore
except ImportError:
    GROUND_TRUTH = {
        # Client Alpha +6281234567890 / PT Contoh Alpha — synthetic fixture.
        "fixture-source-alpha": {
            "label": "Client Alpha / PT Contoh Alpha",
            "must_mention": ["PT Contoh Alpha", "LKPM", "27 march", "email", "meet"],
            "must_flag_risk": ["support"],
            "must_not_invent": ["invoice paid", "payment received", "visa approved", "kitas issued"],
        },
        # Client Beta +6281234567891 / PT Contoh Beta — synthetic fixture.
        "fixture-source-beta": {
            "label": "Client Beta / PT Contoh Beta",
            "must_mention": ["kitas", "pt contoh beta", "passport", "document"],
            "must_flag_risk": [],
            "must_not_invent": ["17 million", "payment received", "tax filing"],
        },
        # Client Gamma +6281234567892 / PT Contoh Gamma — synthetic fixture.
        "fixture-source-gamma": {
            "label": "Client Gamma / PT Contoh Gamma",
            "must_mention": ["kitas", "17", "july", "ticket"],
            "must_flag_risk": [],
            "must_not_invent": ["lkpm", "pt contoh beta", "unrelated person"],
        },
    }


def run(nb_id: str, source_id: str, prompt: str) -> dict:
    out = _nlm(
        ["notebook", "query", nb_id, prompt,
         "--source-ids", source_id, "--json", "-t", "150"]
    )
    data = json.loads(out)
    value = data.get("value", data)
    answer = value.get("answer", "")
    refs = value.get("references", []) or []
    citations = [r.get("cited_text", "") for r in refs if r.get("cited_text")]
    foreign = [r for r in refs if r.get("source_id") and r["source_id"] != source_id]
    return {"answer": answer, "citations": citations, "foreign": len(foreign)}


def score(answer: str, gt: dict) -> dict:
    low = answer.lower()
    hits = [m for m in gt["must_mention"] if m.lower() in low]
    misses = [m for m in gt["must_mention"] if m.lower() not in low]
    risk_hits = [m for m in gt["must_flag_risk"] if m.lower() in low]
    halluc = [m for m in gt["must_not_invent"] if m.lower() in low]
    return {
        "hits": hits,
        "misses": misses,
        "risk_hits": risk_hits,
        "hallucinations": halluc,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nb", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--variant", required=True, help="prompt variant name from PROMPTS")
    args = ap.parse_args()

    from scripts.wa_corpus.prompt_variants import PROMPTS

    prompt = PROMPTS[args.variant]
    gt = GROUND_TRUTH[args.source]
    r = run(args.nb, args.source, prompt)
    s = score(r["answer"], gt)

    print("=" * 70)
    print(r["answer"])
    print("=" * 70)
    print(f"variant={args.variant}  chat={gt['label']}")
    print(f"citations={len(r['citations'])} foreign={r['foreign']}")
    print(f"hits={len(s['hits'])}/{len(gt['must_mention'])} {s['hits']}")
    print(f"misses={s['misses']}")
    print(f"risk_hits={s['risk_hits']}")
    print(f"HALLUCINATIONS={s['hallucinations']}")
    print(f"chars={len(r['answer'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
