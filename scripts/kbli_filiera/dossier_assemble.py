#!/usr/bin/env python3
"""dossier_assemble.py — GARUDA-FILIERA per-code D3 dossier writer (deterministic).

The ONLY sanctioned writer of `data/kbli-filiera/dossiers/<code>.jsonl`
(guard-enforced: infra/claude-hooks/data-plane-registry.json, id
"kbli-filiera" — an interactive hand-edit of that path is blocked by
data_plane_guard.py; running THIS script is the registered route around
that guard, per the registry's own `compilers` pointer).

Takes the evidence pulled by dossier_pull.py (`--evidence <dir>`, must
contain evidence-index.json) and a set of stage PROPOSALS from the
Workflow's LLM seats (`--proposals <json>` — a JSON list of
`{stage, payload, evidence_refs[]}`), and appends one append-only event
per stage to the dossier: `{seq, stage, op_id, at, payload, evidence_refs,
prev_sha256}`.

Garuda law (research/operations/2026-07-16-kbli-garuda-filiera-workflow.md
§1): an LLM never manufactures a deterministic fact. `op_id` is therefore
computed HERE, deterministically, from `sha256(code|stage|canonical_json
(payload))` — never trusted from the caller's proposal — so idempotent
resume (op_id/2026-07-16 §3) cannot be spoofed by a re-run that "claims"
to be the same op with different content.

Append-only integrity: a stage that already has a recorded payload
DIFFERENT from the new one is a REFUSED rewrite (raises
DivergentRewriteError) — dossiers are a hash-chained event log
(`prev_sha256`), never silently mutated. Same op_id (== same payload) is
an idempotent no-op: no new line, success.

Every `evidence_ref` in a proposal must name a `rel_path` that actually
exists in the pulled evidence-index for this code — an unresolvable
reference is a compiler exception (schema violation, §6 failure rules:
"code to quarantine, batch continues, fail-visible") and this script
exits non-zero for that entry without touching the dossier file.

Usage:
    python scripts/kbli_filiera/dossier_assemble.py \\
        --evidence /tmp/pilot-a1-evidence/68112 \\
        --proposals /tmp/pilot-a1-evidence/68112/proposals.json \\
        [--code 68112] [--dossier-root data/kbli-filiera/dossiers]
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from kbli_filiera import vault_common as common
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from kbli_filiera import vault_common as common

LOG = common.setup_logger("dossier_assemble")

DEFAULT_DOSSIER_ROOT = Path("data/kbli-filiera/dossiers")


class DivergentRewriteError(ValueError):
    """A stage already has a DIFFERENT recorded payload — append-only
    integrity refuses the rewrite (workflow doc §3: dossiers are a
    hash-chained event log, never silently mutated)."""


@dataclass
class AssembleOutcome:
    stage: str
    op_id: str
    accepted: bool  # True only if a NEW line was appended
    reason: str  # "appended" | "idempotent-noop"


# ---------------------------------------------------------------------------
# op_id (deterministic, compiler-owned — never trusted from the caller)
# ---------------------------------------------------------------------------

def canonical_json(obj) -> str:
    """Stable serialization (sorted keys, no whitespace) so the SAME
    logical payload always hashes to the SAME op_id regardless of key
    order in the caller's JSON."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_op_id(code: str, stage: str, payload) -> str:
    return common.sha256_bytes(f"{code}|{stage}|{canonical_json(payload)}".encode("utf-8"))


# ---------------------------------------------------------------------------
# Dossier path + raw-line helpers (raw, not vault_common.read_jsonl, so the
# hash chain covers the EXACT bytes on disk, including a torn/corrupt last
# line — the chain must reflect reality, not a best-effort parse of it)
# ---------------------------------------------------------------------------

def dossier_path_for(dossier_root: Path, code: str) -> Path:
    return dossier_root / f"{code}.jsonl"


def _raw_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _next_seq(path: Path) -> int:
    return len(_raw_lines(path)) + 1


def _last_line_sha256(path: Path) -> str:
    lines = _raw_lines(path)
    if not lines:
        return "GENESIS"
    return common.sha256_bytes(lines[-1].encode("utf-8"))


def load_existing_stage_index(dossier_path: Path) -> dict[str, dict]:
    """stage -> its recorded event. At most one canonical record per stage
    is ever accepted through `append_stage` — `setdefault` (first
    occurrence wins) is belt-and-suspenders replay-safety, not the
    integrity guarantee itself (that lives in `append_stage`)."""
    by_stage: dict[str, dict] = {}
    for rec in common.read_jsonl(dossier_path):
        stage = rec.get("stage")
        if stage:
            by_stage.setdefault(stage, rec)
    return by_stage


# ---------------------------------------------------------------------------
# Append (the append-only integrity contract)
# ---------------------------------------------------------------------------

def append_stage(dossier_path: Path, code: str, stage: str, payload, evidence_refs: list[str],
                  *, at: str | None = None) -> AssembleOutcome:
    op_id = compute_op_id(code, stage, payload)
    existing = load_existing_stage_index(dossier_path).get(stage)
    if existing is not None:
        if existing.get("op_id") == op_id:
            return AssembleOutcome(stage=stage, op_id=op_id, accepted=False, reason="idempotent-noop")
        raise DivergentRewriteError(
            f"stage {stage!r} for code {code!r} already has a recorded payload "
            f"(op_id={existing.get('op_id')}) that differs from the new one "
            f"(op_id={op_id}) — append-only integrity refuses the rewrite"
        )

    dossier_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "seq": _next_seq(dossier_path),
        "stage": stage,
        "op_id": op_id,
        "at": at or common.now_iso(),
        "payload": payload,
        "evidence_refs": list(evidence_refs),
        "prev_sha256": _last_line_sha256(dossier_path),
    }
    common.append_jsonl(dossier_path, record)
    return AssembleOutcome(stage=stage, op_id=op_id, accepted=True, reason="appended")


# ---------------------------------------------------------------------------
# Evidence-index cross-check
# ---------------------------------------------------------------------------

def load_evidence_rel_paths(evidence_dir: Path) -> set[str]:
    index_path = evidence_dir / "evidence-index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"evidence-index.json not found under {evidence_dir} (run dossier_pull.py first)")
    items = json.loads(index_path.read_text(encoding="utf-8"))
    return {item.get("rel_path") for item in items if item.get("rel_path")}


def validate_evidence_refs(evidence_refs: list[str], known_rel_paths: set[str], *, code: str, stage: str) -> None:
    unknown = [r for r in evidence_refs if r not in known_rel_paths]
    if unknown:
        raise ValueError(
            f"unresolvable evidence_refs for code={code!r} stage={stage!r}: {unknown} "
            "(not present in this code's evidence-index.json)"
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def run(evidence_dir: Path, proposals: list[dict], code: str, dossier_root: Path) -> int:
    known_rel_paths = load_evidence_rel_paths(evidence_dir)
    dossier_path = dossier_path_for(dossier_root, code)

    failures = 0
    for entry in proposals:
        stage = entry.get("stage")
        payload = entry.get("payload")
        evidence_refs = entry.get("evidence_refs") or []
        if not stage or payload is None:
            LOG.error("malformed proposal entry (missing stage/payload), skipped: %r", entry)
            failures += 1
            continue
        try:
            validate_evidence_refs(evidence_refs, known_rel_paths, code=code, stage=stage)
            outcome = append_stage(dossier_path, code, stage, payload, evidence_refs)
            LOG.info("code=%s stage=%s %s (op_id=%s)", code, stage, outcome.reason, outcome.op_id[:12])
        except (DivergentRewriteError, ValueError) as exc:
            LOG.error(str(exc))
            failures += 1

    if failures:
        LOG.error("ASSEMBLE COMPLETE with %s of %s stage(s) failed for code=%s", failures, len(proposals), code)
        return 1
    LOG.info("ASSEMBLE COMPLETE %s stage(s) ok for code=%s -> %s", len(proposals), code, dossier_path)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--evidence", type=Path, required=True, help="per-code evidence dir from dossier_pull.py")
    ap.add_argument("--proposals", type=Path, required=True, help="JSON list of {stage, payload, evidence_refs[]}")
    ap.add_argument("--code", type=str, default=None, help="defaults to the --evidence directory's basename")
    ap.add_argument("--dossier-root", type=Path, default=DEFAULT_DOSSIER_ROOT)
    args = ap.parse_args(argv)

    code = args.code or args.evidence.name
    if not code:
        LOG.error("could not determine --code (pass it explicitly or use a non-empty --evidence dir name)")
        return 2

    try:
        proposals = json.loads(args.proposals.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOG.error("could not read --proposals %s: %s", args.proposals, exc)
        return 2
    if not isinstance(proposals, list):
        LOG.error("--proposals must be a JSON list of stage records, got %s", type(proposals).__name__)
        return 2

    try:
        return run(args.evidence, proposals, code, args.dossier_root)
    except FileNotFoundError as exc:
        LOG.error(str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
