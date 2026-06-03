#!/usr/bin/env python3
"""S18 RAG truth-eval harness for Zantara prod.

Measures two things against a *verified* golden set (golden_set.json):

  1. RETRIEVAL — recall@k: of the source documents a correct answer should
     surface (``expected_sources`` basenames), how many appear in the top-k
     ``sources`` the RAG returns.

  2. GENERATION — faithfulness + correctness: does the RAG ``answer`` assert
     the ground-truth ``must_contain`` facts, and is it grounded in the
     retrieved contexts? Scored two ways:
       - cheap lexical ``must_contain`` coverage (always runs, no LLM), and
       - an optional LLM judge over the Claude Max-plan OAuth CLI
         (``--judge``) that returns a 0-1 faithfulness score per item.

Design constraints (S18):
  * Embedding model is FROZEN to ``text-embedding-3-small`` / 1536 dim. This
    harness never embeds anything itself — it only consumes the prod RAG's
    own retrieval, so the frozen embedding is honoured by construction.
  * NO paid Anthropic endpoint. The LLM judge shells out to the ``claude`` CLI
    (Max-plan OAuth, ``CLAUDE_CODE_OAUTH_TOKEN``) and strips ANTHROPIC_API_KEY
    from the subprocess env. If the CLI is absent the judge degrades to the
    lexical scorer; it never falls back to a paid SDK call.
  * Prod is RBAC-walled (S2 scar): ``/api/oracle/query`` requires a JWT bound
    to a ``team_members`` row. Pass it with ``--jwt`` (or env
    ``RAG_EVAL_JWT``). With no JWT the harness runs in ``--offline`` mode: it
    validates the golden set, prints the eval plan, and exits 0 so the harness
    is provably runnable even while the prod arm is blocked. The role grant is
    documented as NEEDS-ANTONELLO in the FROZEN artifact.

Usage:
    python rag_eval.py --offline                 # golden-set self-check, no prod
    python rag_eval.py --jwt <token> --k 5       # full eval vs prod
    python rag_eval.py --jwt <token> --local     # vs http://localhost:8000
    python rag_eval.py --jwt <token> --judge     # add LLM faithfulness judge
    python rag_eval.py --report out.json         # write machine-readable report
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
_GOLDEN_FILE = _THIS_DIR / "golden_set.json"

PRODUCTION_API = "https://nuzantara-rag.fly.dev"
LOCAL_API = "http://localhost:8000"
ORACLE_QUERY_PATH = "/api/oracle/query"

# Frozen — must never change (S18 constraint). Asserted against the golden set.
FROZEN_EMBEDDING_MODEL = "text-embedding-3-small"
FROZEN_EMBEDDING_DIM = 1536

# Quality gates (advisory; reported, not enforced as exit code in offline mode).
MIN_RECALL_AT_K = 0.60
MIN_MUSTCONTAIN_COVERAGE = 0.70
MIN_JUDGE_FAITHFULNESS = 0.70


# --------------------------------------------------------------------------- #
# Golden set loading + validation                                             #
# --------------------------------------------------------------------------- #
@dataclass
class GoldenPair:
    id: str
    domain: str
    question: str
    ground_truth: str
    must_contain: list[str] = field(default_factory=list)
    expected_sources: list[str] = field(default_factory=list)
    verdict_anchor: str | None = None
    must_not_assert_current: list[str] = field(default_factory=list)


def load_golden(path: Path = _GOLDEN_FILE) -> tuple[dict[str, Any], list[GoldenPair]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("embedding_model") != FROZEN_EMBEDDING_MODEL:
        raise ValueError(
            f"golden_set embedding_model={data.get('embedding_model')!r} != "
            f"frozen {FROZEN_EMBEDDING_MODEL!r}"
        )
    if data.get("embedding_dim") != FROZEN_EMBEDDING_DIM:
        raise ValueError(
            f"golden_set embedding_dim={data.get('embedding_dim')!r} != "
            f"frozen {FROZEN_EMBEDDING_DIM}"
        )
    pairs: list[GoldenPair] = []
    seen: set[str] = set()
    for raw in data["pairs"]:
        if raw["id"] in seen:
            raise ValueError(f"duplicate golden id {raw['id']!r}")
        seen.add(raw["id"])
        pairs.append(
            GoldenPair(
                id=raw["id"],
                domain=raw["domain"],
                question=raw["question"],
                ground_truth=raw["ground_truth"],
                must_contain=raw.get("must_contain", []),
                expected_sources=raw.get("expected_sources", []),
                verdict_anchor=raw.get("verdict_anchor"),
                must_not_assert_current=raw.get("must_not_assert_current", []),
            )
        )
    if not pairs:
        raise ValueError("golden_set has zero pairs")
    return data, pairs


# --------------------------------------------------------------------------- #
# Prod RAG query (RBAC-aware)                                                  #
# --------------------------------------------------------------------------- #
def query_rag(question: str, api_url: str, jwt: str, limit: int) -> dict[str, Any]:
    """Query the prod RAG. Returns {answer, sources:[...], error?}.

    ``sources`` is the list of retrieved context dicts from the oracle
    response (used for recall@k). On HTTP/RBAC failure returns
    {"error": "...", "status": <code>}.
    """
    import httpx  # local import so --offline needs no deps

    headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}
    try:
        resp = httpx.post(
            f"{api_url}{ORACLE_QUERY_PATH}",
            json={
                "query": question,
                "limit": limit,
                "use_ai": True,
                "include_sources": True,
            },
            headers=headers,
            timeout=90.0,
        )
    except Exception as exc:  # network
        return {"error": f"network: {exc}", "status": None}

    if resp.status_code == 401:
        return {"error": "rbac_401", "status": 401}
    if resp.status_code != 200:
        return {"error": f"http_{resp.status_code}", "status": resp.status_code}

    data = resp.json()
    return {
        "answer": data.get("answer") or "",
        "sources": data.get("sources") or [],
        "error": None,
        "status": 200,
    }


def _source_label(src: dict[str, Any]) -> str:
    """Best-effort basename/title extracted from a source dict for recall match."""
    for key in ("source", "file", "filename", "path", "document", "title", "id"):
        val = src.get(key)
        if isinstance(val, str) and val:
            return val
    return json.dumps(src, ensure_ascii=False)[:120]


# --------------------------------------------------------------------------- #
# Metrics                                                                      #
# --------------------------------------------------------------------------- #
def recall_at_k(expected_sources: list[str], retrieved: list[dict[str, Any]]) -> float:
    """Fraction of expected source basenames found in the retrieved sources.

    Match is substring-insensitive: an expected basename (e.g.
    ``kbli_2025_catalogo_completo.txt``) counts as retrieved if it appears
    inside any retrieved source label.
    """
    if not expected_sources:
        return float("nan")
    labels = " | ".join(_source_label(s).lower() for s in retrieved)
    # Also match on the stem (drop extension) to tolerate path/title variants.
    hits = 0
    for exp in expected_sources:
        stem = exp.lower().rsplit(".", 1)[0]
        if exp.lower() in labels or stem in labels:
            hits += 1
    return hits / len(expected_sources)


def mustcontain_coverage(answer: str, must_contain: list[str]) -> float:
    if not must_contain:
        return float("nan")
    low = answer.lower()
    hits = sum(1 for m in must_contain if m.lower() in low)
    return hits / len(must_contain)


def asserts_stale_as_current(answer: str, forbidden: list[str]) -> list[str]:
    low = answer.lower()
    return [f for f in forbidden if f.lower() in low]


# --------------------------------------------------------------------------- #
# LLM judge (Claude Max OAuth CLI — NO paid endpoint)                          #
# --------------------------------------------------------------------------- #
_CLAUDE_CANDIDATES = (
    "/opt/homebrew/bin/claude",
    str(Path.home() / ".local/bin/claude"),
    str(Path.home() / ".npm-global/bin/claude"),
    "/usr/local/bin/claude",
)

_JUDGE_PROMPT = """You are a strict RAG faithfulness judge. You are given a QUESTION, a verified \
GROUND_TRUTH, and a RAG_ANSWER. Score the RAG_ANSWER from 0.0 to 1.0 on whether it is (a) factually \
consistent with GROUND_TRUTH and (b) not contradicting it. 1.0 = fully correct and grounded; \
0.0 = contradicts ground truth or hallucinates. Respond with ONLY a JSON object: \
{{"score": <float>, "reason": "<one sentence>"}}.

QUESTION:
{question}

GROUND_TRUTH:
{ground_truth}

RAG_ANSWER:
{answer}
"""


def _find_claude() -> str | None:
    for c in _CLAUDE_CANDIDATES:
        if Path(c).exists():
            return c
    return None


def llm_judge(question: str, ground_truth: str, answer: str) -> dict[str, Any]:
    """Score faithfulness via the Claude Max-plan OAuth CLI.

    Strips ANTHROPIC_API_KEY from the subprocess env (Golden Rule: never let
    the paid endpoint be used). Returns {"score": float|None, "reason": str}.
    If the CLI is unavailable, returns score=None so the caller falls back to
    the lexical scorer — it never reaches for a paid SDK.
    """
    cli = _find_claude()
    if not cli:
        return {"score": None, "reason": "claude CLI not found — lexical fallback"}
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    prompt = _JUDGE_PROMPT.format(
        question=question, ground_truth=ground_truth, answer=answer or "(empty)"
    )
    try:
        proc = subprocess.run(
            [cli, "-p", "--model", "claude-sonnet-4-6"],
            input=prompt,
            text=True,
            capture_output=True,
            env=env,
            timeout=120,
        )
    except Exception as exc:
        return {"score": None, "reason": f"judge error: {exc}"}
    if proc.returncode != 0:
        return {"score": None, "reason": f"judge rc={proc.returncode}: {proc.stderr[:120]}"}
    out = proc.stdout.strip()
    m = re.search(r"\{.*\}", out, re.DOTALL)
    if not m:
        return {"score": None, "reason": f"judge non-json: {out[:120]}"}
    try:
        parsed = json.loads(m.group(0))
        return {"score": float(parsed["score"]), "reason": str(parsed.get("reason", ""))}
    except Exception as exc:
        return {"score": None, "reason": f"judge parse: {exc}"}


# --------------------------------------------------------------------------- #
# Eval loop                                                                    #
# --------------------------------------------------------------------------- #
def run_eval(
    pairs: list[GoldenPair],
    api_url: str,
    jwt: str,
    k: int,
    use_judge: bool,
) -> dict[str, Any]:
    results = []
    rbac_blocked = 0
    for p in pairs:
        rag = query_rag(p.question, api_url, jwt, limit=k)
        item: dict[str, Any] = {"id": p.id, "domain": p.domain}
        if rag.get("error"):
            item["error"] = rag["error"]
            if rag["error"] == "rbac_401":
                rbac_blocked += 1
            results.append(item)
            continue
        answer = rag["answer"]
        sources = rag["sources"]
        item["recall_at_k"] = recall_at_k(p.expected_sources, sources)
        item["mustcontain_coverage"] = mustcontain_coverage(answer, p.must_contain)
        stale = asserts_stale_as_current(answer, p.must_not_assert_current)
        item["asserts_stale_as_current"] = stale
        item["answer_preview"] = answer[:240]
        if use_judge:
            item["judge"] = llm_judge(p.question, p.ground_truth, answer)
        results.append(item)

    return {
        "api_url": api_url,
        "k": k,
        "n_pairs": len(pairs),
        "rbac_blocked": rbac_blocked,
        "results": results,
        "aggregate": _aggregate(results),
    }


def _aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    def _mean(key: str) -> float | None:
        vals = [
            r[key]
            for r in results
            if key in r and isinstance(r[key], (int, float)) and r[key] == r[key]
        ]
        return round(sum(vals) / len(vals), 4) if vals else None

    judge_vals = [
        r["judge"]["score"]
        for r in results
        if r.get("judge") and isinstance(r["judge"].get("score"), (int, float))
    ]
    return {
        "mean_recall_at_k": _mean("recall_at_k"),
        "mean_mustcontain_coverage": _mean("mustcontain_coverage"),
        "mean_judge_faithfulness": (
            round(sum(judge_vals) / len(judge_vals), 4) if judge_vals else None
        ),
        "n_scored": sum(1 for r in results if "recall_at_k" in r),
        "n_errors": sum(1 for r in results if "error" in r),
    }


# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="S18 Zantara RAG truth-eval harness")
    ap.add_argument("--jwt", default=os.environ.get("RAG_EVAL_JWT", ""),
                    help="JWT bearer for the RBAC-walled oracle endpoint")
    ap.add_argument("--local", action="store_true", help="query localhost:8000")
    ap.add_argument("--k", type=int, default=5, help="top-k for recall@k")
    ap.add_argument("--judge", action="store_true",
                    help="add LLM faithfulness judge (Claude Max OAuth CLI)")
    ap.add_argument("--offline", action="store_true",
                    help="golden-set self-check + plan; no prod call")
    ap.add_argument("--report", default="", help="write JSON report to this path")
    args = ap.parse_args(argv)

    data, pairs = load_golden()
    print(f"[S18-eval] golden set v{data['version']} — {len(pairs)} pairs "
          f"(embedding {FROZEN_EMBEDDING_MODEL}/{FROZEN_EMBEDDING_DIM} FROZEN)")

    if args.offline or not args.jwt:
        domains: dict[str, int] = {}
        for p in pairs:
            domains[p.domain] = domains.get(p.domain, 0) + 1
        plan = {
            "mode": "offline",
            "reason": ("--offline requested" if args.offline
                       else "no JWT supplied — prod arm is RBAC-walled (S2)"),
            "golden_pairs": len(pairs),
            "by_domain": domains,
            "embedding_frozen": f"{FROZEN_EMBEDDING_MODEL}/{FROZEN_EMBEDDING_DIM}",
            "needs_antonello": (
                "Provision a JWT for a team_members row (e.g. role "
                "visa_specialist/tax_consultant/company_setup) so "
                "/api/oracle/query returns 200 instead of 401, then re-run "
                "with --jwt <token>."
            ),
            "verdict_villa_kbli": "55203 (see golden id kbli-villa-current)",
        }
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        if args.report:
            Path(args.report).write_text(
                json.dumps({"plan": plan, "golden_meta": data}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"[S18-eval] wrote {args.report}")
        print("[S18-eval] OFFLINE self-check PASSED — harness is runnable; "
              "prod eval pending JWT grant.")
        return 0

    api_url = LOCAL_API if args.local else PRODUCTION_API
    print(f"[S18-eval] querying {api_url} (k={args.k}, judge={args.judge})")
    report = run_eval(pairs, api_url, args.jwt, args.k, args.judge)
    print(json.dumps(report["aggregate"], indent=2))
    if report["rbac_blocked"]:
        print(f"[S18-eval] WARNING: {report['rbac_blocked']}/{len(pairs)} "
              "queries RBAC-blocked (401) — JWT lacks a valid team_members binding.")
    if args.report:
        Path(args.report).write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"[S18-eval] wrote {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
