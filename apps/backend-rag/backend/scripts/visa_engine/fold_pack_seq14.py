"""fold_pack_seq14.py — assemble ``rulepack-prod-014.source.json`` from
seq-13 plus two claim-backed ELIGIBILITY insertions for E23U/E23V.

E5 blocked5 lane (2026-08-24). Task: seq-13's active pack reaches 29 of 38
products; five of the nine still-blocked products (E23U, E23V, E33A, E33B,
E33C) have their doctrine CLOSED (E2c mini-batch, PR #4294,
``research/visa/doctrine-factory/claims/e2c-blocked5-claim-ledger.md``) but
carry no ELIGIBILITY/SUPPORT rule at all — only a HUMAN_REVIEW and/or
HARD_FILTER.

This fold inserts exactly TWO new rules, both claim-cited and compiled
clean through ``compile_claims`` (0 lint findings — VERIFIED-only,
R-OVERSTAY-PLANNING, UNSATISFIABLE-CONDITION, VACUOUS-RULE all pass):

1. ``el.e23u.diplomatic-household-support`` — E23U reaches SUPPORTED for
   an EMPLOYMENT-purpose applicant with an INDIVIDUAL sponsor and a
   non-Indonesian-entity employer (CL-E23U-01/02, both VERIFIED).
2. ``el.e23v.trade-office-support`` — E23V reaches SUPPORTED for an
   EMPLOYMENT-purpose applicant with a GOVERNMENT sponsor and a
   non-Indonesian-entity employer (CL-E23V-01/02, both VERIFIED).

This fold ALSO REMOVES two pre-existing rules —
``review.e23u.requested-product`` and ``review.e23v.requested-product``
(the E5-increment-3 HUMAN_REVIEW rules, live since seq-9). Discovered live
by driving the real evaluator while authoring the two insertions above:
both are keyed on ``intent.requested_product_code``, which
``fact-mapper.ts:597`` hard-codes ``NOT_ASKED`` in production — so they
never merely "never fire", they are ALWAYS unknown, and per
``evaluator.py``'s documented precedence ("on_unknown=NEEDS_INPUT
UNKNOWNs from HARD_FILTER/HUMAN_REVIEW block via BLOCKED_UNKNOWN"
regardless of ELIGIBILITY's own verdict), that permanent unknown
unconditionally forces the WHOLE per-product proof to BLOCKED_UNKNOWN —
including any ELIGIBILITY-stage SUPPORT rule that resolves cleanly TRUE.
Verified directly: inserting the two SUPPORT rules ABOVE alone (without
this removal) still leaves E23U/E23V permanently BLOCKED_UNKNOWN in the
real evaluator, the two new rules dead on arrival. These two rules are
therefore not merely inert (the class this task's brief already
anticipated) but actively harmful to any future SUPPORT rule on the same
product — removing them is required, not optional, for this fold's own
stated purpose. No replacement HUMAN_REVIEW rule is authored for either
product: no claim in ``e2c-blocked5-claim-ledger.md`` establishes a
review-worthy fact pattern DISTINCT from the SUPPORT gate itself (using
the same predicate would let REVIEW's own documented precedence over
SUPPORT mask every applicant the new SUPPORT rule was meant to reach).

**E33A/E33B/E33C deliberately get NO new rule in this fold** — see the PR
body for the full design-question writeup. Short version: the E5
increment-3 lane (``research/visa/doctrine-factory/e5/
blocked7-rule-manifest.json``, folded into seq-9) already tried a SUPPORT
shape for these three and rejected it ("W3: no safe SUPPORT exists" /
"manufactured offer" bug, per the visaoracle skill's 2026-08-19 LIVE
STATE entry), shipping HARD_FILTER-only instead — which is what is live
today (``hf.e33a.sponsor-not-government`` etc.). This fold's own claim
re-read confirms the SAME structural problem persists and is, if
anything, worse for E33A/B/C than it was ruled to be for E23U/E23V: their
own claim ledger (``e2c-blocked5-claim-ledger.md``) flags the actual
eligibility gates — the financial threshold (CL-E33A-03: "minimum
threshold set by a Director-General decree (not itself in this corpus)"),
the sponsor pathway (CL-E33B-03: an unresolved tension between two NB-2
answers, explicitly not adjudicated), and the qualifying-evidence process
(CL-E33B-04, CL-E33C-01/02: citation-audit verdict PROSE_ONLY) — as
UNVERIFIED/contested/caveated, not clean VERIFIED facts a SUPPORT
predicate can safely rest on. Per this task's own instruction ("if a
needed claim is missing or only PROVISIONAL, do NOT invent it"), this
fold does not paper over that gap with a rule the claims do not actually
support, and does not re-litigate a design question already ruled once.
E23U/E23V's own SUPPORT rules ALSO carry a residual over-broad-discriminator
caveat (the fact vocabulary's `sponsor.type` enum cannot distinguish "a
foreign diplomatic mission" from "any other individual sponsor", nor "a
foreign trade/economic office" from "any other foreign government body,
including an Indonesian-government invitation") — flagged explicitly in
each inserted rule's ``caveats`` in the compiled manifest and in the PR
body, not silently accepted.

Every input is read from disk at run time. The chain hash is read LIVE
from ``rulepack-prod-013.signed.json`` and asserted against the expected
anchor; the seq-13 SOURCE bytes are additionally re-hashed (RFC 8785 JCS)
and must equal that same value — a source/signed mismatch aborts the
fold. The two new rules are independently compiled from
``inc9-pack-edits/inc9-rule-manifest.json`` through the real
``compile_claims`` module (not hand-copied JSON) and cross-checked
byte-for-byte against nothing else — there is no cure file to drift
against here, since this fold makes ZERO edits to any existing rule,
product, or source_record; the only mutation is two pure insertions.
Deterministic: fixed timestamps, no ``datetime.now()`` — re-running is
byte-identical (proven by ``main`` running the assembly twice and
comparing sha256).

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

from backend.scripts.visa_engine.compile_claims import compile_manifest, load_manifest
from backend.services.visa_engine.bundle import canonicalize_json
from backend.services.visa_engine.claim_ledger import ClaimLedgerError, load_claim_ledgers
from backend.services.visa_engine.models import Rule, RulePackPayload

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

_E5_DIR = _REPO_ROOT / "research" / "visa" / "doctrine-factory" / "e5"
_INC9_DIR = _E5_DIR / "inc9-pack-edits"
_INC9_MANIFEST = _INC9_DIR / "inc9-rule-manifest.json"

_CLAIMS_DIR = _REPO_ROOT / "research" / "visa" / "doctrine-factory" / "claims"
_LEDGER_FILES = [
    _CLAIMS_DIR / "e2c-blocked5-claim-ledger.md",
]

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
_SEQ14_CREATED_BY = "agent.air-m5.backend-rag.visa-seq14-blocked5-e23uv-support.fold-2026-08-24"

_EXPECTED_SEQ13_PAYLOAD_SHA256 = (
    "b9edb809930ab486e49a4af7804fbae7f072caa3b6459b78a94ecb7f6bfe14f8"
)

_RULE_KEY_ORDER = (
    "rule_id",
    "stage",
    "scope",
    "priority",
    "valid_period",
    "when",
    "effect",
    "on_unknown",
    "required_facts",
    "source_refs",
    "explanation_key",
    "safety_critical",
    "product_version_ids",
)

_IDENTITY_KEYS = frozenset(
    {"sequence", "version", "rule_pack_id", "previous_payload_sha256", "created_at", "created_by"}
)

_EXPECTED_INSERTED_RULE_IDS = (
    "el.e23u.diplomatic-household-support",
    "el.e23v.trade-office-support",
)

#: Pre-existing rules removed by this fold — see module docstring for why:
#: both are permanently BLOCKED_UNKNOWN in production (keyed on
#: ``intent.requested_product_code``, hard-coded NOT_ASKED at
#: ``fact-mapper.ts:597``) and, per the evaluator's own documented
#: precedence, that permanent unknown blocks the WHOLE per-product proof
#: regardless of ELIGIBILITY's verdict — proven live while authoring the
#: two insertions above: without this removal, the new SUPPORT rules never
#: surface as SUPPORTED.
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
# Compile the inc9 manifest against the E2c blocked5 claim ledger
# ---------------------------------------------------------------------------


def _compile_inc9_rules() -> dict[str, dict[str, Any]]:
    try:
        ledger = load_claim_ledgers(_LEDGER_FILES)
    except (OSError, ClaimLedgerError) as exc:
        raise FoldPackError(f"failed to load claim ledgers: {exc}") from exc

    manifest = load_manifest(_INC9_MANIFEST)
    report = compile_manifest(manifest, ledger)
    if not report.ok:
        raise FoldPackError("inc9-rule-manifest.json failed to compile clean:\n" + report.render())

    compiled: dict[str, dict[str, Any]] = {}
    for entry in report.compiled:
        rule_dict = _to_pack_rule_dict(entry.rule.model_dump(mode="json", by_alias=True))
        compiled[rule_dict["rule_id"]] = rule_dict

    if set(compiled) != set(_EXPECTED_INSERTED_RULE_IDS):
        raise FoldPackError(
            f"manifest compiled {sorted(compiled)}, expected exactly "
            f"{sorted(_EXPECTED_INSERTED_RULE_IDS)} — manifest drifted from this fold's design"
        )
    return compiled


def _to_pack_rule_dict(rule_src: dict[str, Any]) -> dict[str, Any]:
    clean = {k: v for k, v in rule_src.items() if not k.startswith("_")}
    out: dict[str, Any] = {}
    for key in _RULE_KEY_ORDER:
        if key in clean:
            out[key] = clean[key]
        else:
            raise FoldPackError(f"rule {clean.get('rule_id')!r} is missing required key {key!r}")
    extra = set(clean) - set(_RULE_KEY_ORDER)
    if extra:
        raise FoldPackError(f"rule {clean.get('rule_id')!r} has unexpected key(s): {sorted(extra)}")
    Rule.model_validate(out)
    return out


# ---------------------------------------------------------------------------
# Apply the two insertions
# ---------------------------------------------------------------------------


def _apply_removals(payload: dict[str, Any]) -> None:
    rules_by_id = {r["rule_id"]: r for r in payload["rules"]}
    for rule_id in _EXPECTED_REMOVED_RULE_IDS:
        if rule_id not in rules_by_id:
            raise FoldPackError(f"rule {rule_id!r} not found in seq-13 — cannot remove")
    payload["rules"] = [
        r for r in payload["rules"] if r["rule_id"] not in _EXPECTED_REMOVED_RULE_IDS
    ]


def _apply_insertions(payload: dict[str, Any], compiled: dict[str, dict[str, Any]]) -> None:
    rules_by_id = {r["rule_id"]: r for r in payload["rules"]}
    for rule_id in _EXPECTED_INSERTED_RULE_IDS:
        if rule_id in rules_by_id:
            raise FoldPackError(f"rule {rule_id!r} already exists in seq-13 — cannot insert")
        inserted = copy.deepcopy(compiled[rule_id])
        payload["rules"] = [*payload["rules"], inserted]
        rules_by_id[rule_id] = inserted


# ---------------------------------------------------------------------------
# Byte-invariance sweep — everything except the two new rules and the six
# identity keys must be byte-identical to seq-13.
# ---------------------------------------------------------------------------


def _assert_untouched(payload: dict[str, Any], seq13: dict[str, Any]) -> None:
    for key in set(seq13) | set(payload):
        if key in _IDENTITY_KEYS or key == "rules":
            continue
        if _canon(payload.get(key)) != _canon(seq13.get(key)):
            raise FoldPackError(
                f"top-level payload key {key!r} drifted from seq-13 — this fold "
                "declares no edit there (products/source_records are untouched: "
                "this is an insertion-only fold)"
            )

    seq13_rules = {r["rule_id"]: r for r in seq13["rules"]}
    new_rules = {r["rule_id"]: r for r in payload["rules"]}

    for rid, rule in new_rules.items():
        if rid in _EXPECTED_INSERTED_RULE_IDS:
            continue
        if rid not in seq13_rules or _canon(rule) != _canon(seq13_rules[rid]):
            raise FoldPackError(f"rule {rid!r} drifted from seq-13 outside the declared insertions")
    missing = set(seq13_rules) - set(new_rules)
    if missing != set(_EXPECTED_REMOVED_RULE_IDS):
        raise FoldPackError(
            f"rule(s) vanished unexpectedly: {sorted(missing - set(_EXPECTED_REMOVED_RULE_IDS))}"
        )
    added = set(new_rules) - set(seq13_rules)
    if added != set(_EXPECTED_INSERTED_RULE_IDS):
        raise FoldPackError(
            f"rules added beyond the declared insertion set: {sorted(added - set(_EXPECTED_INSERTED_RULE_IDS))}"
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

    compiled = _compile_inc9_rules()
    _apply_removals(payload)
    _apply_insertions(payload, compiled)

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
