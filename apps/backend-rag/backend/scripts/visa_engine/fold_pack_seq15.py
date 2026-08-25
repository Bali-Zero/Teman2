"""fold_pack_seq15.py — assemble ``rulepack-prod-015.source.json`` from
seq-14 by RESTORING the two rules seq-14 removed. Nothing else changes.

V1/E23UV lane (2026-08-25), owner ruling (A) — see
``docs/plans/2026-08-24-visa-oracle-live/DEADEND-PURPOSE-COVERAGE.md``.

**This fold inserts two rules and removes none: 109 -> 111.**

WHY seq-14 WAS RIGHT AND IS BEING UNDONE ANYWAY. PR #4797 folded
``review.e23u.requested-product`` and ``review.e23v.requested-product`` out of
seq-13 on a premise that was TRUE when it was written: both are keyed on
``intent.requested_product_code``, which the interview hard-coded
``unknownFact(NOT_ASKED)``, so they were not merely inert but permanently
UNKNOWN — and per ``evaluator.py``'s documented precedence an
``on_unknown=NEEDS_INPUT`` UNKNOWN at HUMAN_REVIEW forces the whole
per-product proof to ``BLOCKED_UNKNOWN``, poisoning any future SUPPORT rule
on the same product. Removing dead rules that also poison their own product
is correct maintenance, and this fold does not dispute one word of it.

The premise stopped being true in the SAME change that produced this fold:
``employment_special_employer`` (tree.ts / flow.ts, this PR) asks the
applicant who their employer is and can now emit ``E23U``/``E23V`` into that
fact. The two rules go from permanently-unknown to genuinely reachable, so
the maintenance that removed them no longer applies.

WHY THE OPPOSITE CURE, AND WHY IT DOES NOT REOPEN #4797's OBJECTION. #4797
also, in an earlier revision, tried to author SUPPORT rules for these two
products and rightly dropped them: no predicate over the current fact
vocabulary separates "a diplomat's household" from "any individual
employer" (``SponsorType`` has no ``DIPLOMATIC_MISSION`` member), so an
auto-approval would have told a nanny hired by an ordinary expat family that
she qualifies. That objection is FATAL to a SUPPORT rule and does NOT bind a
REVIEW rule. A REQUIRE_REVIEW effect hands the case to a human: over-capture
costs a consultant reading an ordinary case, under-capture leaves the
applicant a confidently WRONG answer. This fold therefore restores ONLY the
two HUMAN_REVIEW rules and authors NO SUPPORT rule for E23U/E23V — the
unresolved sponsor semantics recorded in ``enums.py`` and in
``research/visa/2026-08-11-w3-sponsor-rules-factbase.md`` stay unresolved.

WHAT THE DEFECT ACTUALLY IS, measured. #4797's closing line says E23U/E23V
"stay unreachable and route to a human consultant". The first half is
measured (``reachability_report.py``: 29/38 either way); the second half is
not, and is false. An unreachable product does not route anywhere — it is
silent. A foreign diplomat's household worker answers ``work`` ->
``intent.purposes = ["EMPLOYMENT"]`` -> E23 resolves SUPPORTED and WINS, so
the Oracle answers "E23" with confidence while the applicant's real case is
E23U. That is the mandate's own prohibition ("Never an invented answer")
reached without hallucinating anything: not by inventing a product, but by
staying silent about the right one.

CONTENT NOTE, deliberately not hidden: because seq-14's only change was
these two removals, restoring them makes seq-15's ``rules`` array
byte-identical to seq-13's. That is asserted below, not hoped for
(``_assert_rules_equal_seq13``). seq-15 is a true revert with a fresh
identity and an auditable reason, which is why seq-14 is superseded rather
than deleted: the history "13 present -> 14 removed on premise P -> 15
restored because P became false" is the trail a regulatory engine wants, and
deleting the candidate would erase the reasoning.

CHAIN NOTE: seq-14 has no ``.signed.json`` — it is a candidate that was
never signed or activated (the live pack is still seq-13). This fold
therefore chains to seq-14's SOURCE bytes, which is the same thing
``fold_pack_seq10.py`` and ``fold_pack_seq12.py`` already do, and no
consumer validates ``previous_payload_sha256`` at activation time. If seq-14
is ever signed with different bytes, this chain link goes stale and the
gates below will say so loudly.

    PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq15
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from backend.services.visa_engine.bundle import canonicalize_json
from backend.services.visa_engine.models import RulePackPayload

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_THIS_FILE = Path(__file__).resolve()
_BACKEND_ROOT = _THIS_FILE.parents[2]  # apps/backend-rag/backend
_REPO_ROOT = _THIS_FILE.parents[5]

_PACKS_DIR = _BACKEND_ROOT / "services" / "visa_engine" / "contracts" / "packs"
_SEQ13_SOURCE = _PACKS_DIR / "rulepack-prod-013.source.json"
_SEQ14_SOURCE = _PACKS_DIR / "rulepack-prod-014.source.json"
_SEQ15_OUT = _PACKS_DIR / "rulepack-prod-015.source.json"

_PRETTIER_BIN = _REPO_ROOT / "node_modules" / ".bin" / "prettier"

# ---------------------------------------------------------------------------
# seq-15 identity
# ---------------------------------------------------------------------------

_SEQ15_SEQUENCE = 15
_SEQ15_VERSION = "2026.8.25"
_SEQ15_RULE_PACK_ID_URL = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/15"
)
_SEQ15_CREATED_AT = "2026-08-25T06:00:00Z"
_SEQ15_CREATED_BY = "agent.pro.visa-oracle.e23uv-review-restore.fold-2026-08-25"

_IDENTITY_KEYS = frozenset(
    {"sequence", "version", "rule_pack_id", "previous_payload_sha256", "created_at", "created_by"}
)

#: Restored VERBATIM from seq-13 — this fold copies the rule objects, it does
#: not re-author them, so "restore" is provable rather than asserted.
_EXPECTED_INSERTED_RULE_IDS = (
    "review.e23u.requested-product",
    "review.e23v.requested-product",
)

#: This fold removes NOTHING. Kept (empty) so the invariance sweep reads as an
#: explicit declaration rather than an omission.
_EXPECTED_REMOVED_RULE_IDS: tuple[str, ...] = ()

#: seq-14 declares seq-13 as its predecessor; re-checked here so a
#: seq-13/seq-14 mismatch cannot slip through this fold silently.
_EXPECTED_SEQ13_PAYLOAD_SHA256 = (
    "b9edb809930ab486e49a4af7804fbae7f072caa3b6459b78a94ecb7f6bfe14f8"
)


class FoldPackError(RuntimeError):
    """A fail-loud gate inside the fold tripped — never silently degrade."""


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _verify_rule_pack_id() -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, _SEQ15_RULE_PACK_ID_URL)


def _chain_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonicalize_json(payload)).hexdigest()


def _verify_predecessors(seq13: dict[str, Any], seq14: dict[str, Any]) -> str:
    """seq-14 must be the candidate this fold was authored against, and it
    must itself declare the seq-13 we are restoring rules FROM."""
    if seq14.get("sequence") != 14:
        raise FoldPackError(f"{_SEQ14_SOURCE} declares sequence={seq14.get('sequence')!r}, expected 14")
    if seq13.get("sequence") != 13:
        raise FoldPackError(f"{_SEQ13_SOURCE} declares sequence={seq13.get('sequence')!r}, expected 13")

    seq13_hash = _chain_hash(seq13)
    if seq13_hash != _EXPECTED_SEQ13_PAYLOAD_SHA256:
        raise FoldPackError(
            f"seq-13 SOURCE re-hashes to {seq13_hash}, expected "
            f"{_EXPECTED_SEQ13_PAYLOAD_SHA256} — the seq-13 on disk is not the one "
            "these rules are being restored from"
        )
    declared = seq14.get("previous_payload_sha256")
    if declared != _EXPECTED_SEQ13_PAYLOAD_SHA256:
        raise FoldPackError(
            f"seq-14 declares previous_payload_sha256={declared!r}, but seq-13 hashes to "
            f"{_EXPECTED_SEQ13_PAYLOAD_SHA256} — refusing to chain across a broken link"
        )
    return _chain_hash(seq14)


def _restore_rules(payload: dict[str, Any], seq13: dict[str, Any]) -> None:
    """Re-insert the two rules, copied verbatim from seq-13, at the index
    they occupied there — so rule ORDER is restored too, not just membership
    (``_canon`` on the whole list below would catch order drift anyway; this
    makes the restoration exact rather than merely equivalent)."""
    seq13_rules = seq13["rules"]
    by_id = {r["rule_id"]: r for r in payload["rules"]}
    for rule_id in _EXPECTED_INSERTED_RULE_IDS:
        if rule_id in by_id:
            raise FoldPackError(f"rule {rule_id!r} already present in seq-14 — nothing to restore")
        source = next((r for r in seq13_rules if r["rule_id"] == rule_id), None)
        if source is None:
            raise FoldPackError(f"rule {rule_id!r} not found in seq-13 — cannot restore verbatim")

    restored: list[dict[str, Any]] = []
    seq14_by_id = {r["rule_id"]: r for r in payload["rules"]}
    for rule in seq13_rules:
        rid = rule["rule_id"]
        if rid in _EXPECTED_INSERTED_RULE_IDS:
            restored.append(copy.deepcopy(rule))
        elif rid in seq14_by_id:
            restored.append(seq14_by_id[rid])
    # Any rule seq-14 holds that seq-13 never had would be dropped by the loop
    # above; that must be impossible, and is asserted rather than assumed.
    dropped = set(seq14_by_id) - {r["rule_id"] for r in restored}
    if dropped:
        raise FoldPackError(f"seq-14 rules not present in seq-13 would be lost: {sorted(dropped)}")
    payload["rules"] = restored


def _assert_untouched(payload: dict[str, Any], seq14: dict[str, Any]) -> None:
    for key in set(seq14) | set(payload):
        if key in _IDENTITY_KEYS or key == "rules":
            continue
        if _canon(payload.get(key)) != _canon(seq14.get(key)):
            raise FoldPackError(
                f"top-level payload key {key!r} drifted from seq-14 — this fold "
                "declares no edit there (products/source_records untouched)"
            )

    seq14_rules = {r["rule_id"]: r for r in seq14["rules"]}
    new_rules = {r["rule_id"]: r for r in payload["rules"]}
    for rid, rule in new_rules.items():
        if rid in _EXPECTED_INSERTED_RULE_IDS:
            continue
        if rid not in seq14_rules or _canon(rule) != _canon(seq14_rules[rid]):
            raise FoldPackError(f"rule {rid!r} drifted from seq-14 — this fold edits no existing rule")
    added = set(new_rules) - set(seq14_rules)
    if added != set(_EXPECTED_INSERTED_RULE_IDS):
        raise FoldPackError(f"insertions beyond the declared set: {sorted(added - set(_EXPECTED_INSERTED_RULE_IDS))}")
    missing = set(seq14_rules) - set(new_rules)
    if missing != set(_EXPECTED_REMOVED_RULE_IDS):
        raise FoldPackError(f"rule(s) vanished unexpectedly: {sorted(missing)}")


def _assert_rules_equal_seq13(payload: dict[str, Any], seq13: dict[str, Any]) -> None:
    """The load-bearing claim of this fold: seq-15 is a TRUE REVERT of
    seq-14's rule change. If this ever fails, the fold has quietly become a
    re-authoring and the module docstring is lying."""
    if _canon(payload["rules"]) != _canon(seq13["rules"]):
        raise FoldPackError(
            "seq-15 rules are NOT byte-identical to seq-13 — this fold claims to be "
            "a pure restoration of the two rules seq-14 removed, so any other "
            "difference means the claim is false"
        )


def _write_pack(payload: dict[str, Any], out_path: Path) -> None:
    if not _PRETTIER_BIN.exists():
        raise FoldPackError(
            f"prettier binary not found at {_PRETTIER_BIN} — run `npm install` at repo root"
        )
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f"{out_path.stem}.tmp.", suffix=out_path.suffix, dir=str(out_path.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with open(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        result = subprocess.run(
            [str(_PRETTIER_BIN), "--write", str(tmp_path)],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise FoldPackError(
                f"prettier --write {tmp_path} failed (rc={result.returncode}):\n"
                f"{result.stdout}\n{result.stderr}"
            )
        tmp_path.replace(out_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def assemble_payload() -> dict[str, Any]:
    seq13 = _load_json(_SEQ13_SOURCE)
    seq14 = _load_json(_SEQ14_SOURCE)
    previous_sha = _verify_predecessors(seq13, seq14)

    payload = copy.deepcopy(seq14)
    _restore_rules(payload, seq13)

    payload["sequence"] = _SEQ15_SEQUENCE
    payload["version"] = _SEQ15_VERSION
    payload["rule_pack_id"] = str(_verify_rule_pack_id())
    payload["previous_payload_sha256"] = previous_sha
    payload["created_at"] = _SEQ15_CREATED_AT
    payload["created_by"] = _SEQ15_CREATED_BY

    _assert_untouched(payload, seq14)
    _assert_rules_equal_seq13(payload, seq13)

    try:
        RulePackPayload.model_validate(payload)
    except Exception as exc:  # re-raised loud with context
        raise FoldPackError(
            f"assembled seq-15 payload failed RulePackPayload validation: {exc}"
        ) from exc
    return payload


def main(argv: list[str] | None = None) -> int:
    del argv  # no CLI flags — deterministic single-purpose script
    try:
        payload = assemble_payload()
    except FoldPackError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    _write_pack(payload, _SEQ15_OUT)
    print(
        f"wrote {_SEQ15_OUT} — {len(payload['rules'])} rule(s), "
        f"{len(payload['products'])} product(s), {len(payload['source_records'])} source_record(s)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
