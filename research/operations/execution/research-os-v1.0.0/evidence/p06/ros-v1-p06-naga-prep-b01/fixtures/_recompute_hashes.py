"""Recompute every `object_hash` in the P06 bundle's fixtures -- never hand-type one again.

WHY THIS EXISTS. R1-build-spec.md §5b: "a `ClaimRef`'s `object_hash` is the real
`research_os.hashing.object_hash` of the object it names, computed, not typed." Before this PR
`bitemporal/03` and `supersession/01` carried "4444...", "7777...", "8888...", "9999..." --
placeholder references presented as provenance, and `supersession/01` bound the SAME predecessor
claim to two DIFFERENT placeholder hashes across `supersedes_claim_ref` and
`object_successor_edge.predecessor_ref`. This script is the fix made permanent: run it after
editing any canonical object in these fixtures and it puts every hash back in agreement with the
object it actually names.

WHAT COUNTS AS "canonical" HERE. Any JSON object (dict) that carries BOTH `contract_version` and
`object_hash` is a canonical Research OS object (`Claim`, `Evidence`, `ObjectSuccessorEdge`, ...);
its own `object_hash` is recomputed from its own content via `research_os.hashing.object_hash`,
which already excludes the `object_hash` field itself (`HASH_OMISSION_FIELDS`). Any OTHER dict
that carries `object_hash` alongside `claim_id`, `evidence_id`, or an `{object_kind, object_id}`
pair naming a `claim`/`evidence` is a REFERENCE to one of those canonical objects
(`ClaimRef`/`EvidenceRef`/`ClaimEvidenceRef`/`ExactObjectRef`); its `object_hash` is set to match
the CURRENT hash of the object it names, wherever that object lives in the SAME file. A reference
to an object that is not present in the file at all (e.g. `Claim.statement.subject_ref` naming an
external "regulation" document, or `Evidence.source_event_ref` naming a placeholder `IntelEvent`
this bundle never instantiates) is left untouched -- there is nothing in this file to recompute it
from, and inventing one here would be exactly the "presented as provenance" defect this script
exists to remove.

CONVERGENCE. A `Claim`'s own hash depends on its `evidence_refs`/`supersedes_claim_ref` being
already-correct; an edge's hash depends on its `predecessor_ref`/`successor_ref` already being
correct. Rather than hardcode that dependency order per fixture shape, this recomputes in ROUNDS
(recompute every canonical object's own hash, then propagate into every reference, repeat) until a
round makes no change -- which converges in at most a few rounds for the shallow reference graphs
this bundle actually has, and is safe (idempotent) to run any number of extra times.

USAGE. `PYTHONPATH=<worktree>/packages/research-os-core <worktree>/apps/backend-rag/.venv/bin/python
fixtures/_recompute_hashes.py` from this directory, or via an absolute path -- it locates its own
target files relative to itself, not the caller's cwd. Synthetic-only: touches nothing outside
this bundle's `fixtures/` tree.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from research_os.hashing import object_hash

_BUNDLE_FIXTURES = Path(__file__).resolve().parent

#: The fixture files known to carry full canonical objects (`contract_version` + `object_hash`
#: dicts). Listed explicitly rather than globbed over the whole tree: most fixtures in this
#: bundle are deliberately ILLUSTRATIVE (no canonical objects at all, e.g. `invalidation/01`,
#: `abstention/*`) and must never silently start being touched just because a future edit
#: happens to add an `object_hash`-shaped dict to one of them by accident -- that would be this
#: script quietly promoting a fixture to "canonical" nobody decided to promote. Add a path here
#: deliberately, in the same PR that makes the fixture canonical.
_TARGET_FILES: tuple[Path, ...] = (
    _BUNDLE_FIXTURES / "bitemporal" / "03_time_travel_query_example.json",
    _BUNDLE_FIXTURES / "supersession" / "01_amendment_supersedes_original.json",
    *sorted((_BUNDLE_FIXTURES / "seed_public_regulatory").glob("*.json")),
)

_MAX_ROUNDS = 10


def _walk(node: Any) -> Any:
    """Yield every dict in the tree, pre-order, including nested ones."""

    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def _identity(node: dict[str, Any]) -> str:
    for field in ("claim_id", "evidence_id", "object_successor_edge_id"):
        if field in node:
            return f"{field}={node[field]}"
    return "?"


def _recompute_file(path: Path) -> list[str]:
    original_text = path.read_text(encoding="utf-8")
    doc = json.loads(original_text)
    changes: list[str] = []

    for round_index in range(_MAX_ROUNDS):
        changed_this_round = False
        id_map: dict[str, dict[str, str]] = {"claim": {}, "evidence": {}}

        # Pass 1: every canonical object recomputes its OWN hash from its current content.
        for node in _walk(doc):
            if not isinstance(node, dict):
                continue
            if "contract_version" not in node or "object_hash" not in node:
                continue
            new_hash = object_hash(node)
            if node["object_hash"] != new_hash:
                changes.append(
                    f"{path.name}: {_identity(node)} object_hash "
                    f"{node['object_hash'][:12]}... -> {new_hash[:12]}..."
                )
                node["object_hash"] = new_hash
                changed_this_round = True
            if "claim_id" in node:
                id_map["claim"][node["claim_id"]] = node["object_hash"]
            if "evidence_id" in node:
                id_map["evidence"][node["evidence_id"]] = node["object_hash"]

        # Pass 2: every REFERENCE to a canonical object present in this file is set to match.
        for node in _walk(doc):
            if not isinstance(node, dict) or "object_hash" not in node:
                continue
            if "contract_version" in node:
                continue  # a canonical object itself, already handled in pass 1.

            target_hash: str | None = None
            if "claim_id" in node and node["claim_id"] in id_map["claim"]:
                target_hash = id_map["claim"][node["claim_id"]]
            elif "evidence_id" in node and node["evidence_id"] in id_map["evidence"]:
                target_hash = id_map["evidence"][node["evidence_id"]]
            else:
                kind = node.get("object_kind")
                object_id = node.get("object_id")
                if kind in id_map and object_id in id_map[kind]:
                    target_hash = id_map[kind][object_id]

            if target_hash is not None and node["object_hash"] != target_hash:
                changes.append(
                    f"{path.name}: reference {_identity(node)} object_hash "
                    f"{node['object_hash'][:12]}... -> {target_hash[:12]}..."
                )
                node["object_hash"] = target_hash
                changed_this_round = True

        if not changed_this_round:
            break
    else:
        raise RuntimeError(
            f"{path}: hash propagation did not converge in {_MAX_ROUNDS} rounds -- "
            "there may be a reference cycle between canonical objects"
        )

    new_text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if new_text != original_text:
        path.write_text(new_text, encoding="utf-8")
    return changes


def main() -> int:
    all_changes: list[str] = []
    for path in _TARGET_FILES:
        if not path.is_file():
            print(f"skip (not found): {path}", file=sys.stderr)
            continue
        all_changes.extend(_recompute_file(path))

    if all_changes:
        print(f"recomputed {len(all_changes)} hash(es):")
        for line in all_changes:
            print(f"  {line}")
    else:
        print("no changes: every object_hash already matches its recomputed value")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
