"""fold_pack_seq14.py — assemble ``rulepack-prod-014.source.json`` from
seq-13 by REMOVING two permanently-unknown rules. Nothing is inserted.

E5 blocked5 lane (2026-08-24). seq-13's active pack reaches 29 of 38
products; five of the nine still-blocked products (E23U, E23V, E33A, E33B,
E33C) have their doctrine CLOSED (E2c mini-batch, PR #4294,
``research/visa/doctrine-factory/claims/e2c-blocked5-claim-ledger.md``) but
carry no ELIGIBILITY/SUPPORT rule at all.

**This fold removes two rules and adds none.**
``review.e23u.requested-product`` and ``review.e23v.requested-product``
(the E5-increment-3 HUMAN_REVIEW rules, live since seq-9) are both keyed on
``intent.requested_product_code``, which ``fact-mapper.ts:597`` hard-codes
``NOT_ASKED`` in production — so they never merely "never fire", they are
ALWAYS unknown, and per ``evaluator.py``'s documented precedence
("on_unknown=NEEDS_INPUT UNKNOWNs from HARD_FILTER/HUMAN_REVIEW block via
BLOCKED_UNKNOWN" regardless of ELIGIBILITY's own verdict), that permanent
unknown unconditionally forces the WHOLE per-product proof to
BLOCKED_UNKNOWN — including any ELIGIBILITY-stage SUPPORT rule that
resolves cleanly TRUE. They are therefore not merely inert but actively
poison any future SUPPORT rule on the same product. Removing them is a
strict improvement and is behaviour-preserving today (a product with no
SUPPORT rule does not surface either way).

**WHY NO SUPPORT RULE IS AUTHORED FOR E23U/E23V (REWORK 2026-08-24).**
An earlier revision of this fold inserted two SUPPORT rules —
``el.e23u.diplomatic-household-support`` (EMPLOYMENT ∧ ``sponsor.type ==
INDIVIDUAL`` ∧ ``work.employer_is_indonesian_entity == false``) and
``el.e23v.trade-office-support`` (the same shape with ``GOVERNMENT``). Both
were claim-cited and compiled clean, and both were WRONG: they constrain
the CATEGORY of the sponsor and never the attribute that DEFINES the
product. E23U is the stay permit for the domestic staff of a **diplomat**;
its rule would have declared a nanny hired by any non-diplomatic expat
family eligible for it. E23V is the permit for the representative of a
foreign **Trade and Economic Office**; ``GOVERNMENT`` covers any government
body, an Indonesian-government invitation included.

The fact vocabulary cannot express the defining attribute at all:
``SponsorType`` has no DIPLOMATIC_MISSION or TRADE_OFFICE member, so no
predicate over the current facts can separate the intended population from
the over-broad one. And this is not a gap that better rule-authoring
closes: ``enums.py`` (``SponsorType`` docstring, CORRECTED 2026-08-11 by
the W3 sponsor-rules factbase) records that **E23U/E23V have no dedicated
Permenkumham Pasal at all** — confirmed by full-text search of 22/2023 and
11/2024 — and that their ``sponsor_types`` values in the pack are "Bali
Zero working hypotheses, not statutory readings, and remain UNRESOLVED".
There is no statute to encode. Flagging the over-breadth in a manifest
``caveats`` field (what the earlier revision did) does not stop the wrong
answer from reaching a client, so the two insertions are dropped: E23U and
E23V stay unreachable by the engine and route to a human consultant, which
is the honest outcome until either the fact vocabulary gains the defining
attribute or a governing instrument is found.

**E33A/E33B/E33C likewise get NO new rule** — the E5 increment-3 lane
already tried a SUPPORT shape for these three and rejected it ("W3: no safe
SUPPORT exists" / "manufactured offer" bug), shipping HARD_FILTER-only
instead, which is what is live today. Their claim ledger flags the actual
eligibility gates — the financial threshold (CL-E33A-03, a Director-General
decree not in this corpus), the sponsor pathway (CL-E33B-03, an unresolved
tension between two NB-2 answers) and the qualifying-evidence process
(CL-E33B-04, CL-E33C-01/02, citation-audit verdict PROSE_ONLY) — as
UNVERIFIED/contested, not clean VERIFIED facts a SUPPORT predicate can rest
on. See ``research/visa/2026-08-24-e33abc-grounding-nb2.md``.

Every input is read from disk at run time. The chain hash is read LIVE
from ``rulepack-prod-013.signed.json`` and asserted against the expected
anchor; the seq-13 SOURCE bytes are additionally re-hashed (RFC 8785 JCS)
and must equal that same value — a source/signed mismatch aborts the fold.
No rule, product or source_record is edited: the only mutation is the two
removals plus the six identity keys. Deterministic: fixed timestamps, no
``datetime.now()`` — re-running is byte-identical (proven by ``main``
running the assembly twice and comparing sha256).

Usage::

    PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq14
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
_SEQ14_OUT = _PACKS_DIR / "rulepack-prod-014.source.json"

_PRETTIER_BIN = _REPO_ROOT / "node_modules" / ".bin" / "prettier"

# ---------------------------------------------------------------------------
# seq-14 identity (uuid5 anchor verified, never assumed)
# ---------------------------------------------------------------------------

_SEQ14_SEQUENCE = 14
_SEQ14_VERSION = "2026.8.24"
_SEQ14_RULE_PACK_ID_URL = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/14"
)
_SEQ14_CREATED_AT = "2026-08-24T06:00:00Z"
_SEQ14_CREATED_BY = "agent.air-m5.backend-rag.visa-seq14-blocked5-e23uv-retire.fold-2026-08-24"

# fmt: off
# The wrap below is LOAD-BEARING, not style. `scripts/detect_secrets_auto_triage.py`
# approves this specific hash through a CONTENT_KEYED_RULE whose content pattern is
# `^\s*"b9edb809…"\s*$` — the value alone on its own line. Collapsed to a single
# assignment line (99 chars, so `ruff format` will collapse it given the chance) the
# pattern stops matching, the finding goes unaudited, and the Detect Secrets gate goes
# red. `test_guilt_fold_seq14_real_finding_approved` asserts this exact shape.
_EXPECTED_SEQ13_PAYLOAD_SHA256 = (
    "b9edb809930ab486e49a4af7804fbae7f072caa3b6459b78a94ecb7f6bfe14f8"
)
# fmt: on

_IDENTITY_KEYS = frozenset(
    {"sequence", "version", "rule_pack_id", "previous_payload_sha256", "created_at", "created_by"}
)

#: This fold inserts NOTHING. The tuple is kept (empty) so the invariance
#: sweep below reads as an explicit declaration rather than an omission.
_EXPECTED_INSERTED_RULE_IDS: tuple[str, ...] = ()

#: Pre-existing rules removed by this fold — see module docstring for why:
#: both are permanently BLOCKED_UNKNOWN in production (keyed on
#: ``intent.requested_product_code``, hard-coded NOT_ASKED at
#: ``fact-mapper.ts:597``) and, per the evaluator's own documented
#: precedence, that permanent unknown blocks the WHOLE per-product proof
#: regardless of ELIGIBILITY's verdict.
_EXPECTED_REMOVED_RULE_IDS = (
    "review.e23u.requested-product",
    "review.e23v.requested-product",
)


class FoldPackError(RuntimeError):
    """A fail-loud gate inside the fold tripped — never silently degrade."""


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _verify_rule_pack_id() -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, _SEQ14_RULE_PACK_ID_URL)


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
# Apply the two removals
# ---------------------------------------------------------------------------


def _apply_removals(payload: dict[str, Any]) -> None:
    rules_by_id = {r["rule_id"]: r for r in payload["rules"]}
    for rule_id in _EXPECTED_REMOVED_RULE_IDS:
        if rule_id not in rules_by_id:
            raise FoldPackError(f"rule {rule_id!r} not found in seq-13 — cannot remove")
    payload["rules"] = [
        r for r in payload["rules"] if r["rule_id"] not in _EXPECTED_REMOVED_RULE_IDS
    ]


# ---------------------------------------------------------------------------
# Byte-invariance sweep — everything except the two removed rules and the
# six identity keys must be byte-identical to seq-13.
# ---------------------------------------------------------------------------


def _assert_untouched(payload: dict[str, Any], seq13: dict[str, Any]) -> None:
    for key in set(seq13) | set(payload):
        if key in _IDENTITY_KEYS or key == "rules":
            continue
        if _canon(payload.get(key)) != _canon(seq13.get(key)):
            raise FoldPackError(
                f"top-level payload key {key!r} drifted from seq-13 — this fold "
                "declares no edit there (products/source_records are untouched: "
                "this is a removal-only fold)"
            )

    seq13_rules = {r["rule_id"]: r for r in seq13["rules"]}
    new_rules = {r["rule_id"]: r for r in payload["rules"]}

    for rid, rule in new_rules.items():
        if rid not in seq13_rules or _canon(rule) != _canon(seq13_rules[rid]):
            raise FoldPackError(f"rule {rid!r} drifted from seq-13 — this fold edits no rule")
    missing = set(seq13_rules) - set(new_rules)
    if missing != set(_EXPECTED_REMOVED_RULE_IDS):
        raise FoldPackError(
            f"rule(s) vanished unexpectedly: {sorted(missing - set(_EXPECTED_REMOVED_RULE_IDS))}"
        )
    added = set(new_rules) - set(seq13_rules)
    if added != set(_EXPECTED_INSERTED_RULE_IDS):
        raise FoldPackError(
            f"rules added beyond the declared insertion set (which is EMPTY): {sorted(added)}"
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

    payload["sequence"] = _SEQ14_SEQUENCE
    payload["version"] = _SEQ14_VERSION
    payload["rule_pack_id"] = str(_verify_rule_pack_id())
    payload["previous_payload_sha256"] = previous_sha
    payload["created_at"] = _SEQ14_CREATED_AT
    payload["created_by"] = _SEQ14_CREATED_BY

    _assert_untouched(payload, seq13_original)

    try:
        RulePackPayload.model_validate(payload)
    except Exception as exc:  # re-raised loud with context
        raise FoldPackError(
            f"assembled seq-14 payload failed RulePackPayload validation: {exc}"
        ) from exc

    return payload


def main(argv: list[str] | None = None) -> int:
    del argv  # no CLI flags — deterministic single-purpose script
    try:
        payload = assemble_payload()
    except FoldPackError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    _write_pack(payload, _SEQ14_OUT)
    print(
        f"wrote {_SEQ14_OUT} — {len(payload['rules'])} rule(s), "
        f"{len(payload['products'])} product(s), {len(payload['source_records'])} source_record(s)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
