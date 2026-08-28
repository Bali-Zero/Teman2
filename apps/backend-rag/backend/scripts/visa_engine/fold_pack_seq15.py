"""fold_pack_seq15.py — assemble ``rulepack-prod-015.source.json`` from the
SIGNED seq-13 payload: repair the E31B/E31D fail-open predicates and carry
forward seq-14's two retirements.

E31 fail-open repair lane (2026-08-29, Zero's GO on the BLOCK-DEFECT rows of
``research/visa/2026-08-15-gold-divergence-disposition.md``; behavior
re-measured and probe-confirmed in ``research/visa/
2026-08-28-visa-oracle-gold-coverage-and-divergence-adjudication.md`` §5).

**Why this fold chains from seq-13, not from the seq-14 draft.** Activation
(``bundle.py`` anti-rollback chain) requires the candidate's
``previous_payload_sha256`` to equal the CURRENT production bundle's
``payload_sha256``. seq-13 is the highest SIGNED pack; seq-14 exists only as
an unsigned source candidate (#4797) — a pack chained from 14 could never be
activated while 13 is current. So this fold re-derives from the signed
seq-13 payload and INCLUDES seq-14's two removals verbatim (same rule_ids,
same rationale — see ``fold_pack_seq14.py``'s docstring), making seq-15 a
strict successor of both. seq-14's source file stays on disk as history;
it is superseded, not edited.

**The repair, exactly (2 edits + 2 removals of its own):**

1. ``el.e31b-spouse-itas-support`` — the terminal predicate
   ``{"fact": "family.sponsor_status_code", "op": "known"}`` accepted ANY
   answered value, ``"NONE"`` (sponsor holds no status at all) included.
   It becomes ``{"op": "in", "values": [<the pack's own stay-permit
   codes>]}`` — the closed set is DERIVED at fold time from the seq-13
   catalog itself (every product code with the ``E`` stay-permit prefix;
   A/B/C/D codes are visit/entry visas), not hand-authored. This is the
   rule's own name (``itas``) made mechanical: the sponsor must hold one
   of the stay permits this catalog defines, so ``"NONE"`` AND a visit
   visa (``C1``, ``B1`` — the round-1 grader's counterexamples) both fail;
   an UNKNOWN status keeps Kleene-UNKNOWN → ``on_unknown: NEEDS_INPUT``.
   A first revision used ``neq "NONE"`` and the cross-family grader
   (gpt-5.6-sol, REJECT) proved it still fail-open for tourist-visa
   sponsors. Deliberately NOT decided here: KITAP representation —
   ``family.sponsor_status_code`` is ``product_code``-typed and this
   catalog carries no KITAP product, so a KITAP sponsor is inexpressible
   today; that is part of Zero's already-pending KITAP-widening ruling
   (refuter decision package Q1), not this fold's call.

2. ``el.e31b-sponsor-itas-itap`` — same terminal clause, same swap.

3. ``el.e31d-stepchild-support`` — the predicate was FAMILY intent alone,
   which converted a missing-evidence case (gold persona 8) into SUPPORT.
   It becomes the full conjunction the rule's own name claims: FAMILY
   purpose ∧ ``relation_to_sponsor == STEPCHILD`` ∧ both stepchild evidence
   facts confirmed (``stepchild_birth_certificate_confirmed``,
   ``stepchild_marriage_certificate_confirmed`` — registered FactPaths that
   no rule referenced before this fold) ∧ ``sponsor_confirmed == true``
   (added on the round-1 grader's second blocker: without it the rule never
   asked anything about the SPONSOR at all, and a stepchild with documents
   but a wholly unconfirmed sponsor was still supported). WHICH person may
   sponsor (the WNI parent vs the WNA step-parent) is decision-package Q2 —
   an owner call this fold does not make; ``sponsor_confirmed`` is the
   catalog's existing sponsor-identity gate, not a new semantic.
   ``required_facts`` widens to match, so any UNKNOWN evidence yields
   NEEDS_INPUT, never support.

4. ``el.e31d-step-parent-relation`` and ``el.e31d-sponsor-mixed-marriage``
   are REMOVED. Both were byte-duplicates of the intent-only predicate
   (a redundant self-conjunction of ``intersects(purposes, [FAMILY])``);
   as SUPPORT rules they are disjunctive, so each one alone re-opened the
   hole the repaired rule closes. This applies the E33A/E33C doctrine from
   ``fold_pack_seq14.py``: a SUPPORT predicate true for everyone with the
   purpose manufactures offers; a partial-aspect SUPPORT rule is that bug
   by construction. If a distinct population (e.g. the sponsoring
   step-parent as APPLICANT) needs its own E31D path, that is new rule
   authoring with its own claims and sources — an owner/doctrine act, not
   this repair.

Everything else — every other rule, all products, all source_records —
must be byte-identical to seq-13, and the invariance sweep below enforces
that. Deterministic: fixed timestamps, no ``datetime.now()``; re-running is
byte-identical.

Usage::

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
_SEQ13_SIGNED = _PACKS_DIR / "rulepack-prod-013.signed.json"
_SEQ15_OUT = _PACKS_DIR / "rulepack-prod-015.source.json"

_PRETTIER_BIN = _REPO_ROOT / "node_modules" / ".bin" / "prettier"

# ---------------------------------------------------------------------------
# seq-15 identity
# ---------------------------------------------------------------------------

_SEQ15_SEQUENCE = 15
_SEQ15_VERSION = "2026.8.29"
_SEQ15_RULE_PACK_ID_URL = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/15"
)
_SEQ15_CREATED_AT = "2026-08-29T05:00:00Z"
_SEQ15_CREATED_BY = "agent.air-m5.backend-rag.e31-failopen-repair.fold-2026-08-29"

# fmt: off
# The wrap below is LOAD-BEARING, not style — same CONTENT_KEYED_RULE shape as
# fold_pack_seq14.py's anchor (value alone on its own line, or the Detect
# Secrets auto-triage pattern stops matching and the gate goes red).
_EXPECTED_SEQ13_PAYLOAD_SHA256 = (
    "b9edb809930ab486e49a4af7804fbae7f072caa3b6459b78a94ecb7f6bfe14f8"
)
# fmt: on

_IDENTITY_KEYS = frozenset(
    {"sequence", "version", "rule_pack_id", "previous_payload_sha256", "created_at", "created_by"}
)

#: seq-14's two retirements, carried forward verbatim (rationale in
#: fold_pack_seq14.py), plus the two intent-only E31D duplicates this fold
#: retires itself (docstring point 4).
_EXPECTED_REMOVED_RULE_IDS = (
    "review.e23u.requested-product",
    "review.e23v.requested-product",
    "el.e31d-step-parent-relation",
    "el.e31d-sponsor-mixed-marriage",
)

#: Rules whose predicates this fold EDITS (docstring points 1-3). Any other
#: rule drifting a byte fails the invariance sweep.
_EXPECTED_EDITED_RULE_IDS = (
    "el.e31b-spouse-itas-support",
    "el.e31b-sponsor-itas-itap",
    "el.e31d-stepchild-support",
)

_SPONSOR_STATUS_FACT = "family.sponsor_status_code"

#: Stay-permit prefix in this catalog's product-code vocabulary: every ``E``
#: code is a KITAS-class stay permit; A/B/C/D codes are visit/entry visas.
#: The E31B closed set is derived from the pack's OWN product list at fold
#: time (see docstring point 1) — never hand-authored, so a catalog change
#: flows through on refold instead of drifting.
_STAY_PERMIT_PREFIX = "E"

_E31D_REPAIRED_WHEN: dict[str, Any] = {
    "op": "all",
    "args": [
        {"fact": "intent.purposes", "op": "intersects", "values": ["FAMILY"]},
        {"fact": "family.relation_to_sponsor", "op": "eq", "value": "STEPCHILD"},
        {"fact": "family.sponsor_confirmed", "op": "eq", "value": True},
        {"fact": "family.stepchild_birth_certificate_confirmed", "op": "eq", "value": True},
        {"fact": "family.stepchild_marriage_certificate_confirmed", "op": "eq", "value": True},
    ],
}

_E31D_REPAIRED_REQUIRED_FACTS = [
    "intent.purposes",
    "family.relation_to_sponsor",
    "family.sponsor_confirmed",
    "family.stepchild_birth_certificate_confirmed",
    "family.stepchild_marriage_certificate_confirmed",
]


class FoldPackError(RuntimeError):
    """A fail-loud gate inside the fold tripped — never silently degrade."""


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _verify_rule_pack_id() -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, _SEQ15_RULE_PACK_ID_URL)


def _verify_chain(seq13_source: dict[str, Any]) -> str:
    signed = _load_json(_SEQ13_SIGNED)
    declared = signed.get("payload_sha256")
    if declared != _EXPECTED_SEQ13_PAYLOAD_SHA256:
        raise FoldPackError(
            f"{_SEQ13_SIGNED} declares payload_sha256={declared!r}, expected "
            f"{_EXPECTED_SEQ13_PAYLOAD_SHA256!r} — the signed seq-13 on disk is "
            "not the one this fold was authored against"
        )
    recomputed = hashlib.sha256(canonicalize_json(seq13_source)).hexdigest()
    if recomputed != declared:
        raise FoldPackError(
            f"seq-13 SOURCE bytes re-hash to {recomputed}, but the signed file "
            f"declares {declared} — source/signed mismatch, refusing to chain"
        )
    return declared


# ---------------------------------------------------------------------------
# Removals and edits
# ---------------------------------------------------------------------------


def _stay_permit_codes(payload: dict[str, Any]) -> list[str]:
    """The catalog's own stay-permit product codes (``E`` prefix), sorted.

    This is the E31B closed sponsor-status set: derived from the pack being
    folded, never hand-authored. A/B/C/D codes are visit/entry visas and are
    exactly what the round-1 grader proved the ``neq "NONE"`` revision still
    admitted (C1, B1).
    """
    codes = sorted(
        p["product_code"]
        for p in payload["products"]
        if p["product_code"].startswith(_STAY_PERMIT_PREFIX)
    )
    if not codes:
        raise FoldPackError("no stay-permit (E-prefix) product codes found in the pack")
    return codes


def _swap_sponsor_known_for_closed_set(node: Any, *, stay_permit_codes: list[str]) -> int:
    """Recursively replace the fail-open terminal
    ``{"fact": family.sponsor_status_code, "op": "known"}`` with
    ``{"op": "in", "values": <the catalog's stay-permit codes>}`` on the
    same fact. Returns how many terminals were swapped; the caller asserts
    the expected count so a pack whose shape drifted cannot be silently
    half-repaired.
    """
    swapped = 0
    if isinstance(node, dict):
        if node.get("op") == "known" and node.get("fact") == _SPONSOR_STATUS_FACT:
            node.clear()
            node.update(
                {"fact": _SPONSOR_STATUS_FACT, "op": "in", "values": list(stay_permit_codes)}
            )
            return 1
        for value in node.values():
            swapped += _swap_sponsor_known_for_closed_set(
                value, stay_permit_codes=stay_permit_codes
            )
    elif isinstance(node, list):
        for item in node:
            swapped += _swap_sponsor_known_for_closed_set(item, stay_permit_codes=stay_permit_codes)
    return swapped


def _apply_removals(payload: dict[str, Any]) -> None:
    rules_by_id = {r["rule_id"]: r for r in payload["rules"]}
    for rule_id in _EXPECTED_REMOVED_RULE_IDS:
        if rule_id not in rules_by_id:
            raise FoldPackError(f"rule {rule_id!r} not found in seq-13 — cannot remove")
    payload["rules"] = [
        r for r in payload["rules"] if r["rule_id"] not in _EXPECTED_REMOVED_RULE_IDS
    ]


def _apply_edits(payload: dict[str, Any]) -> None:
    rules_by_id = {r["rule_id"]: r for r in payload["rules"]}
    for rule_id in _EXPECTED_EDITED_RULE_IDS:
        if rule_id not in rules_by_id:
            raise FoldPackError(f"rule {rule_id!r} not found — cannot edit")

    stay_permit_codes = _stay_permit_codes(payload)
    for rule_id in ("el.e31b-spouse-itas-support", "el.e31b-sponsor-itas-itap"):
        rule = rules_by_id[rule_id]
        swapped = _swap_sponsor_known_for_closed_set(
            rule["when"], stay_permit_codes=stay_permit_codes
        )
        if swapped < 1:
            raise FoldPackError(
                f"{rule_id}: expected >=1 fail-open `op:known` terminal on "
                f"{_SPONSOR_STATUS_FACT} to swap, found none — the pack shape "
                "drifted from what this fold was authored against"
            )

    e31d = rules_by_id["el.e31d-stepchild-support"]
    e31d["when"] = copy.deepcopy(_E31D_REPAIRED_WHEN)
    e31d["required_facts"] = list(_E31D_REPAIRED_REQUIRED_FACTS)


# ---------------------------------------------------------------------------
# Byte-invariance sweep — everything except the declared removals/edits and
# the six identity keys must be byte-identical to seq-13.
# ---------------------------------------------------------------------------


def _assert_untouched(payload: dict[str, Any], seq13: dict[str, Any]) -> None:
    for key in set(seq13) | set(payload):
        if key in _IDENTITY_KEYS or key == "rules":
            continue
        if _canon(payload.get(key)) != _canon(seq13.get(key)):
            raise FoldPackError(
                f"top-level payload key {key!r} drifted from seq-13 — this fold "
                "declares no edit there (products/source_records are untouched)"
            )

    seq13_rules = {r["rule_id"]: r for r in seq13["rules"]}
    new_rules = {r["rule_id"]: r for r in payload["rules"]}

    for rid, rule in new_rules.items():
        if rid not in seq13_rules:
            raise FoldPackError(f"rule {rid!r} added — this fold declares no insertion")
        if rid in _EXPECTED_EDITED_RULE_IDS:
            if _canon(rule) == _canon(seq13_rules[rid]):
                raise FoldPackError(
                    f"rule {rid!r} is byte-identical to seq-13 — the declared edit did not land"
                )
            continue
        if _canon(rule) != _canon(seq13_rules[rid]):
            raise FoldPackError(
                f"rule {rid!r} drifted from seq-13 — it is not in the declared edit set"
            )
    missing = set(seq13_rules) - set(new_rules)
    if missing != set(_EXPECTED_REMOVED_RULE_IDS):
        raise FoldPackError(
            f"removed-rule set mismatch: {sorted(missing)} != {sorted(_EXPECTED_REMOVED_RULE_IDS)}"
        )


# ---------------------------------------------------------------------------
# Write (atomic + prettier)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def assemble_payload() -> dict[str, Any]:
    seq13_original = _load_json(_SEQ13_SOURCE)
    previous_sha = _verify_chain(seq13_original)
    payload = copy.deepcopy(seq13_original)

    _apply_removals(payload)
    _apply_edits(payload)

    payload["sequence"] = _SEQ15_SEQUENCE
    payload["version"] = _SEQ15_VERSION
    payload["rule_pack_id"] = str(_verify_rule_pack_id())
    payload["previous_payload_sha256"] = previous_sha
    payload["created_at"] = _SEQ15_CREATED_AT
    payload["created_by"] = _SEQ15_CREATED_BY

    _assert_untouched(payload, seq13_original)

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
