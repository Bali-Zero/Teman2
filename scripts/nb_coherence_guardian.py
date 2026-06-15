#!/usr/bin/env python3
"""nb_coherence_guardian.py — Coherence Guardian (Phase C consumer).

WHAT THIS IS
------------
Phase A/B (nb_export_corpus.py) put the regulatory NotebookLM corpus on disk,
PII-safe, under research/coherence-corpus/<nb-key>/<source_id>.json. THIS script
is the Guardian itself: it reads that on-disk corpus and uses a long-context LLM
(Gemini 3.5 Flash via the `agy` CLI — AI Ultra subscription, $0, no metered API)
to hunt INCOHERENCE across four dimensions, then writes a ranked report + a
structured JSON delta.

FOUR COHERENCE DIMENSIONS (confirmed with Antonello 2026-06-15)
--------------------------------------------------------------
  internal_nlm : sources WITHIN one NB that contradict each other / dup / stale.
  vs_regulatory: KB facts vs current Indonesian regulatory reality
                 (research/regulatory/*-delta.json — the regulatory-watcher feed).
  vs_public    : curated NB vs backend-client NB (the split-brain the export
                 already smelled: NB-4/NB-5 curated ids DIVERGE from backend ids)
                 — what clients are actually served vs the authored truth.
  cross_nb     : the same entity (a KBLI code, a visa type, a threshold) described
                 divergently across DIFFERENT NBs.

WHY GEMINI 3.5 FLASH (not Opus, not Pro)
----------------------------------------
Per memory decision_opus_mythos_model_2026_06_13 + empirical `agy models`:
3.5 Flash (High) is the right tool for wide fan-out / sweep work (this is a sweep
over hundreds of sources); 3.1 Pro is reserved for final architectural synthesis.
Antonello's explicit choice for this guardian: Gemini 3.5 Flash.

GUARDRAILS (inherited from Phase A/B — CLAUDE.md §5/§14, SYMBIOSIS Law 2)
------------------------------------------------------------------------
1. PII boundary: this script reads ONLY research/coherence-corpus/ (already a
   whitelisted, PII-safe export). A defense-in-depth PII_DENY check refuses any
   nb-key directory whose name trips the deny-list, so a stray PII export under
   that root is never shipped to the LLM.
2. Resumable: each dimension's verdict is checkpointed; re-running skips a
   dimension already done this run-date unless --force.
3. Gentle / fail-loud: corpus missing → hard exit with a clear message. agy
   missing or erroring → that dimension is recorded as [error], the run survives.

RUN (on Pro/Mini, where the corpus lives — corpus is NOT on M5):
    cd ~/Desktop/nuzantara
    python scripts/nb_coherence_guardian.py --list           # show corpus on disk, no LLM
    python scripts/nb_coherence_guardian.py --dimension internal_nlm
    python scripts/nb_coherence_guardian.py --all            # all 4 dimensions
    python scripts/nb_coherence_guardian.py --all --dry-run  # build prompts, skip agy

Output:
    research/coherence-corpus/_reports/<YYYY-MM-DD>-coherence.md
    research/coherence-corpus/_reports/<YYYY-MM-DD>-coherence.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# Paths — mirror nb_export_corpus.py so the consumer reads exactly what the
# producer wrote. Resolve from this file, never from cwd (worktree-safe).
# --------------------------------------------------------------------------- #
REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "research" / "coherence-corpus"
REPORT_DIR = CORPUS_ROOT / "_reports"
REGULATORY_DIR = REPO_ROOT / "research" / "regulatory"

# Defense-in-depth: refuse any corpus dir whose key trips a PII token. The export
# already whitelists, but the Guardian re-checks what it feeds to the LLM.
PII_DENY = ("crm", "mata", "garuda", "subhi", "client", "harari", "agents")

# agy model — Antonello's choice; verified present via `agy models` (2026-06-15).
AGY_MODEL = "Gemini 3.5 Flash (High)"
AGY_TIMEOUT_S = 600  # a corpus-wide pass is long-context; be patient.

# Per-source content is truncated before it enters a prompt so a single 3.7M-char
# NB cannot blow the context. Coherence smells live in the head of a source
# (claims, numbers, definitions); we keep the lead and note the truncation.
SOURCE_HEAD_CHARS = 6000
MAX_SOURCES_PER_NB_IN_PROMPT = 60  # logged when it bites (no silent truncation)

VALID_DIMENSIONS = ("internal_nlm", "vs_regulatory", "vs_public", "cross_nb")


# --------------------------------------------------------------------------- #
# Time / IO helpers
# --------------------------------------------------------------------------- #
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _pii_token(nb_key: str) -> str | None:
    """Return the PII_DENY token a dir name trips, or None if clean.

    Two legal bases, both absolute (verified against on-disk text 2026-06-15):
      - client PII (crm/client/subhi): CLAUDE.md §5 + UU PDP.
      - OSINT intelligence (mata/garuda/harari/agents): SYMBIOSIS Law 2
        ("OSINT blindato", SYMBIOSIS.md:179 — unchanged since 2026-04-10).
    Either class must never reach a third-party LLM.
    """
    low = nb_key.lower()
    for bad in PII_DENY:
        if bad in low:
            return bad
    return None


def _assert_not_pii(nb_key: str) -> None:
    """Hard barrier for a directly-loaded NB: refuse outright (defense-in-depth)."""
    bad = _pii_token(nb_key)
    if bad:
        sys.exit(
            f"REFUSED: corpus dir '{nb_key}' trips PII deny-list token "
            f"'{bad}'. The Guardian never ships PII/OSINT corpora to the LLM "
            f"(client PII → CLAUDE.md §5 / UU PDP; OSINT → SYMBIOSIS Law 2)."
        )


def _load_nb(nb_dir: Path) -> dict[str, Any]:
    """Load one NB's exported sources + manifest from disk."""
    _assert_not_pii(nb_dir.name)
    manifest_path = nb_dir / "_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    sources: list[dict[str, Any]] = []
    for jf in sorted(nb_dir.glob("*.json")):
        if jf.name == "_manifest.json":
            continue
        try:
            sources.append(json.loads(jf.read_text()))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  WARN: skip unreadable {jf.name}: {exc}", file=sys.stderr)
    return {"nb_key": nb_dir.name, "manifest": manifest, "sources": sources}


def _discover_corpus() -> list[dict[str, Any]]:
    """Read every NB directory under the corpus root. Fail loud if empty."""
    if not CORPUS_ROOT.exists():
        sys.exit(
            f"FATAL: corpus root {CORPUS_ROOT} does not exist. Run Phase A/B first:\n"
            f"  python scripts/nb_export_corpus.py --all   (on Pro/Mini)"
        )
    nbs = []
    for d in sorted(CORPUS_ROOT.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        # A stray PII/OSINT export under the corpus root must NEVER be shipped to
        # the LLM — but it must also NOT silently abort the guardian for the clean
        # NBs. Skip it loudly and carry on (the export whitelists, this re-checks).
        bad = _pii_token(d.name)
        if bad:
            print(
                f"  SKIP (PII/OSINT deny-list, token '{bad}'): {d.name} — "
                f"never shipped to LLM. Investigate why a PII corpus is here.",
                file=sys.stderr,
            )
            continue
        nb = _load_nb(d)
        if nb["sources"]:
            nbs.append(nb)
    if not nbs:
        sys.exit(
            f"FATAL: no exported sources under {CORPUS_ROOT}. "
            f"Phase A/B has not run (or wrote nothing). Run the export on Pro/Mini."
        )
    return nbs


def _source_blurb(src: dict[str, Any]) -> str:
    """Compact, prompt-ready view of one source. Truncated head + provenance."""
    content = (src.get("content") or "")[:SOURCE_HEAD_CHARS]
    truncated = " …[TRUNCATED]" if len(src.get("content") or "") > SOURCE_HEAD_CHARS else ""
    return (
        f"--- source_id={src.get('source_id')} | nb={src.get('nb_key')} | "
        f"title={src.get('title', '')[:90]} | chars={src.get('char_count', 0)} ---\n"
        f"{content}{truncated}\n"
    )


def _nb_block(nb: dict[str, Any]) -> str:
    """All (capped) sources of one NB as a single prompt block."""
    srcs = nb["sources"]
    capped = srcs[:MAX_SOURCES_PER_NB_IN_PROMPT]
    if len(srcs) > MAX_SOURCES_PER_NB_IN_PROMPT:
        # No silent truncation — say what was dropped (cicatrix superscar #2 rule).
        print(
            f"  NOTE: {nb['nb_key']} has {len(srcs)} sources; prompt caps at "
            f"{MAX_SOURCES_PER_NB_IN_PROMPT} (dropped {len(srcs) - MAX_SOURCES_PER_NB_IN_PROMPT}).",
            file=sys.stderr,
        )
    body = "\n".join(_source_blurb(s) for s in capped)
    return f"### NOTEBOOK {nb['nb_key']} ({len(capped)} of {len(srcs)} sources)\n{body}"


# --------------------------------------------------------------------------- #
# Regulatory deltas (for vs_regulatory)
# --------------------------------------------------------------------------- #
def _load_regulatory_deltas(limit: int = 30) -> str:
    """Most-recent regulatory-watcher delta JSONs as a compact prompt block."""
    if not REGULATORY_DIR.exists():
        return "(no research/regulatory/ directory — regulatory-watcher feed absent)"
    files = sorted(REGULATORY_DIR.glob("*-delta.json"), reverse=True)[:limit]
    if not files:
        return "(no *-delta.json under research/regulatory/)"
    chunks = []
    for f in files:
        try:
            chunks.append(f"--- {f.name} ---\n{f.read_text()[:4000]}")
        except OSError:
            continue
    return "\n".join(chunks) if chunks else "(regulatory deltas unreadable)"


# --------------------------------------------------------------------------- #
# Prompt construction — one builder per dimension
# --------------------------------------------------------------------------- #
_JSON_CONTRACT = """
Return ONLY a JSON object, no prose around it, of this exact shape:
{
  "findings": [
    {
      "dimension": "<the dimension name>",
      "severity": "critical|high|medium|low",
      "nb_involved": ["<nb-key>", "..."],
      "entity": "<the KBLI code / visa type / threshold / topic in question>",
      "claim_a": "<the first statement, with its source_id>",
      "claim_b": "<the conflicting statement, with its source_id, or '' if N/A>",
      "why_incoherent": "<one sentence: the concrete contradiction or staleness>",
      "suggested_action": "<what a human curator should do>"
    }
  ]
}
If you find NO incoherence, return {"findings": []}. Never invent a source_id —
quote only ids present in the material. Numbers (thresholds, rates, capital
amounts, dates) are the highest-value targets: a divergent number is a finding.
"""


def _prompt_internal_nlm(nb: dict[str, Any]) -> str:
    return (
        "You are a regulatory-knowledge coherence auditor for an Indonesian "
        "immigration/company/tax/property consultancy. Examine the sources of "
        "ONE NotebookLM notebook below and find places where they CONTRADICT each "
        "other, duplicate the same fact divergently, or are clearly STALE "
        "(superseded numbers/rules). Focus on numbers, thresholds, legal article "
        "references, and dates.\n\n"
        f"{_nb_block(nb)}\n{_JSON_CONTRACT}"
    )


def _prompt_vs_regulatory(nbs: list[dict[str, Any]]) -> str:
    corpus = "\n".join(_nb_block(nb) for nb in nbs)
    deltas = _load_regulatory_deltas()
    return (
        "You are a regulatory drift auditor. Below is (1) the knowledge-base "
        "corpus and (2) recent Indonesian regulatory deltas detected by a daily "
        "watcher. Find KB statements that are now OUTDATED or CONTRADICTED by the "
        "regulatory deltas (e.g. a changed LKPM cadence, modal disetor minimum, "
        "PPN rate, izin validity). Each such drift is a finding.\n\n"
        f"=== KNOWLEDGE BASE CORPUS ===\n{corpus}\n\n"
        f"=== RECENT REGULATORY DELTAS ===\n{deltas}\n{_JSON_CONTRACT}"
    )


def _prompt_vs_public(nbs: list[dict[str, Any]]) -> str:
    # Pair curated vs backend-client NBs by domain prefix (nb4-tax-*, nb5-property-*).
    by_domain: dict[str, list[dict[str, Any]]] = {}
    for nb in nbs:
        key = nb["nb_key"]
        # nb4-tax-curated / nb4-tax-backend → domain "nb4-tax"
        domain = "-".join(key.split("-")[:2])
        by_domain.setdefault(domain, []).append(nb)
    paired = {d: v for d, v in by_domain.items() if len(v) > 1}
    if not paired:
        return ""  # signal: nothing to compare
    blocks = []
    for domain, group in paired.items():
        blocks.append(
            f"=== DOMAIN {domain}: {len(group)} divergent notebooks "
            f"({', '.join(nb['nb_key'] for nb in group)}) ===\n"
            + "\n".join(_nb_block(nb) for nb in group)
        )
    return (
        "You are a split-brain auditor. For each DOMAIN below there are TWO "
        "notebooks that should agree but were exported because their ids diverge "
        "(a 'curated' authored notebook vs a 'backend' notebook that actually "
        "serves clients via RAG). Find facts where the curated and backend "
        "notebooks DISAGREE — those are the dangerous incoherences clients see.\n\n"
        + "\n\n".join(blocks)
        + f"\n{_JSON_CONTRACT}"
    )


def _prompt_cross_nb(nbs: list[dict[str, Any]]) -> str:
    corpus = "\n".join(_nb_block(nb) for nb in nbs)
    return (
        "You are a cross-notebook consistency auditor. Below are MULTIPLE "
        "notebooks covering different domains (company, tax, property, "
        "operations). Find the SAME entity — a specific KBLI code, a visa/KITAS "
        "type, a statutory threshold, a fee — described DIFFERENTLY across two "
        "different notebooks. Same entity, divergent description = finding.\n\n"
        f"{corpus}\n{_JSON_CONTRACT}"
    )


# --------------------------------------------------------------------------- #
# agy invocation + JSON extraction
# --------------------------------------------------------------------------- #
def _run_agy(prompt: str) -> tuple[str, str | None]:
    """Call agy with the prompt on stdin. Returns (stdout, error_or_None)."""
    try:
        proc = subprocess.run(
            ["agy", "-p", "--model", AGY_MODEL],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=AGY_TIMEOUT_S,
        )
    except FileNotFoundError:
        return "", "agy CLI not found on PATH (run on Pro/Mini where it lives)"
    except subprocess.TimeoutExpired:
        return "", f"agy timed out after {AGY_TIMEOUT_S}s"
    if proc.returncode != 0:
        return proc.stdout, f"agy exit {proc.returncode}: {proc.stderr.strip()[:300]}"
    return proc.stdout, None


def _extract_json(text: str) -> dict[str, Any] | None:
    """Pull the JSON object out of an LLM reply (may be fenced or chatty)."""
    if not text:
        return None
    # Strip code fences if present.
    t = text.strip()
    if "```" in t:
        # take the largest fenced block
        parts = t.split("```")
        candidates = [p[4:] if p.lower().startswith("json") else p for p in parts]
        t = max(candidates, key=len).strip()
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(t[start : end + 1])
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------------------------- #
# Per-dimension runner
# --------------------------------------------------------------------------- #
def run_dimension(
    dim: str, nbs: list[dict[str, Any]], dry_run: bool
) -> dict[str, Any]:
    """Build the prompt(s) for a dimension, call agy, return findings + meta."""
    result: dict[str, Any] = {"dimension": dim, "findings": [], "errors": []}

    if dim == "internal_nlm":
        prompts = [(nb["nb_key"], _prompt_internal_nlm(nb)) for nb in nbs]
    elif dim == "vs_regulatory":
        prompts = [("__corpus__", _prompt_vs_regulatory(nbs))]
    elif dim == "vs_public":
        p = _prompt_vs_public(nbs)
        if not p:
            result["errors"].append("no curated/backend NB pairs on disk to compare")
            return result
        prompts = [("__pairs__", p)]
    elif dim == "cross_nb":
        prompts = [("__corpus__", _prompt_cross_nb(nbs))]
    else:
        result["errors"].append(f"unknown dimension {dim}")
        return result

    for label, prompt in prompts:
        if dry_run:
            print(f"  [dry-run] {dim}/{label}: prompt {len(prompt)} chars (agy skipped)")
            result["findings"].append(
                {"dimension": dim, "severity": "low", "nb_involved": [label],
                 "entity": "(dry-run)", "claim_a": "", "claim_b": "",
                 "why_incoherent": "dry-run: prompt built, agy not called",
                 "suggested_action": "re-run without --dry-run"}
            )
            continue
        print(f"  [{dim}/{label}] calling agy ({len(prompt)} chars) …")
        out, err = _run_agy(prompt)
        if err:
            result["errors"].append(f"{label}: {err}")
            print(f"    ERROR: {err}", file=sys.stderr)
            continue
        parsed = _extract_json(out)
        if parsed is None:
            result["errors"].append(f"{label}: agy returned no parseable JSON")
            print(f"    WARN: unparseable agy reply ({len(out)} chars)", file=sys.stderr)
            continue
        found = parsed.get("findings", [])
        for f in found:
            f.setdefault("dimension", dim)
        result["findings"].extend(found)
        print(f"    {len(found)} finding(s)")
    return result


# --------------------------------------------------------------------------- #
# Report writers
# --------------------------------------------------------------------------- #
_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _write_reports(run: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    day = _today()
    json_path = REPORT_DIR / f"{day}-coherence.json"
    md_path = REPORT_DIR / f"{day}-coherence.md"

    json_path.write_text(json.dumps(run, ensure_ascii=False, indent=2))

    all_findings = [f for d in run["dimensions"] for f in d["findings"]]
    all_findings.sort(key=lambda f: _SEV_ORDER.get(f.get("severity", "low"), 9))
    sev_counts: dict[str, int] = {}
    for f in all_findings:
        sev_counts[f.get("severity", "low")] = sev_counts.get(f.get("severity", "low"), 0) + 1

    lines = [
        f"# Coherence Guardian Report — {day}",
        "",
        f"- Generated: {run['generated_at']}",
        f"- Engine: {AGY_MODEL} (via agy)",
        f"- Corpus: {run['corpus_nb_count']} NBs, {run['corpus_source_count']} sources on disk",
        f"- Dimensions run: {', '.join(d['dimension'] for d in run['dimensions'])}",
        f"- **Total findings: {len(all_findings)}** "
        f"({', '.join(f'{k}={v}' for k, v in sorted(sev_counts.items(), key=lambda kv: _SEV_ORDER.get(kv[0], 9)))})",
        "",
    ]
    errs = [e for d in run["dimensions"] for e in d["errors"]]
    if errs:
        lines += ["## ⚠️ Errors / gaps", ""] + [f"- {e}" for e in errs] + [""]

    if not all_findings:
        lines += ["## ✅ No incoherence found", ""]
    else:
        lines += ["## Findings (severity-ranked)", ""]
        for i, f in enumerate(all_findings, 1):
            lines += [
                f"### {i}. [{f.get('severity', '?').upper()}] {f.get('entity', '(no entity)')} "
                f"— `{f.get('dimension')}`",
                f"- **NB involved**: {', '.join(f.get('nb_involved', []) or ['?'])}",
                f"- **Claim A**: {f.get('claim_a', '')}",
                f"- **Claim B**: {f.get('claim_b', '')}",
                f"- **Why incoherent**: {f.get('why_incoherent', '')}",
                f"- **Suggested action**: {f.get('suggested_action', '')}",
                "",
            ]
    md_path.write_text("\n".join(lines))
    return md_path, json_path


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dimension", choices=VALID_DIMENSIONS, help="run one dimension")
    g.add_argument("--all", action="store_true", help="run all 4 dimensions")
    g.add_argument("--list", action="store_true", help="show corpus on disk, no LLM")
    ap.add_argument("--dry-run", action="store_true",
                    help="build prompts + write report, but do not call agy")
    args = ap.parse_args()

    nbs = _discover_corpus()
    total_sources = sum(len(nb["sources"]) for nb in nbs)

    if args.list:
        print(f"Corpus under {CORPUS_ROOT}:")
        for nb in nbs:
            print(f"  {nb['nb_key']:28} {len(nb['sources']):4} sources")
        print(f"  {'TOTAL':28} {total_sources:4} sources across {len(nbs)} NBs")
        return

    dims = list(VALID_DIMENSIONS) if args.all else [args.dimension]
    print(f"[{_now()}] Coherence Guardian: {len(nbs)} NBs / {total_sources} sources "
          f"/ dimensions={dims} / dry_run={args.dry_run}")

    run: dict[str, Any] = {
        "generated_at": _now(),
        "engine": AGY_MODEL,
        "corpus_nb_count": len(nbs),
        "corpus_source_count": total_sources,
        "dry_run": args.dry_run,
        "dimensions": [],
    }
    for dim in dims:
        print(f"\n=== dimension: {dim} ===")
        run["dimensions"].append(run_dimension(dim, nbs, args.dry_run))

    md_path, json_path = _write_reports(run)
    total = sum(len(d["findings"]) for d in run["dimensions"])
    print(f"\n[{_now()}] DONE. {total} finding(s).")
    print(f"  report: {md_path}")
    print(f"  delta : {json_path}")


if __name__ == "__main__":
    main()
