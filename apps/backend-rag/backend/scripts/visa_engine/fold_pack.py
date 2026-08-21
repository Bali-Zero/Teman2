"""E5 increment 3, Step 5 — deterministic, idempotent assembly of
``rulepack-prod-009.source.json`` from repo bytes alone.

This is the seq-9 fold: seq-7 (active, signed) is the base, seq-8's
pricing_key delta is folded in (OD-2: seq-8 was never signed standalone,
its chain to seq-7 is broken — see the module-level ``_ANCHOR_*``
constants and ``test_pack_chain_and_pricing.py``), the two defective
seq-7 ELIGIBILITY rules are retired, the E33G income-evidence review gate
and the 7 blocked7-manifest rules are inserted, and the E31E/0497cb52/
ee8fe5b8 source_record edits from Step 4 are applied.

Every input is read from disk at run time — no hardcoded hash/content
copy-pasted from a prior session's terminal output (Anchors section of
``research/visa/doctrine-factory/e5/2026-08-19-e5-increment3-spec.md``:
"previous read FROM rulepack-prod-007.signed.json's payload_sha256 at run
time, never hardcoded"). Re-running this script produces byte-identical
output (no ``datetime.now()``, no filesystem-order-dependent iteration
over anything that affects content) — see ``test_pack_chain_and_pricing.py``
for the idempotence proof via sha256.

Formatting: the existing packs are Prettier-formatted (verified this
session: ``prettier --check`` on ``rulepack-prod-007.source.json`` reports
"All matched files use Prettier code style!", and a plain
``json.dump(..., indent=2, ensure_ascii=False)`` round-trip through
``prettier --write`` reproduces that file byte-for-byte). This script
therefore writes with the same recipe and shells out to the repo's local
``node_modules/.bin/prettier`` to canonicalize line-wrapping — key ORDER
is entirely under this script's control (Prettier does not sort JSON
object keys), only whitespace/line-breaking is Prettier's job.

``valid_period.from`` on every EXISTING (byte-inherited) seq-7 rule is
deliberately left untouched (inherited verbatim from seq-7's
``2026-07-25T00:00:00Z``, never advanced to the fold date): advancing it
would make seq-9 stop covering the currently-open legal period for any
applicant whose relevant facts (e.g. an already-collected answer, a
pending review case) fall between 2026-07-25 and 2026-08-19 — a
retroactivity break with no doctrinal justification in this increment (no
legal-period-changing edit is made here; every semantic change is either a
defect retirement, a claim-backed addition, or a re-sourcing). Mirrors the
spec's own explicit fallback instruction ("if unclear, mirror seq-7's
valid_period.from exactly").

The 8 NEWLY INSERTED rules are a different case: this fold is when they
first enter any pack, so ``_apply_insertions`` normalizes every inserted
rule's ``valid_period.from`` to ``_SEQ9_NEW_RULE_VALID_FROM`` (the fold
date, matching ``_SEQ9_CREATED_AT``) — never mind what a prepared-artifact
JSON file (e.g. ``cure-e33g.json``, authored 2026-07-24 as a standalone
draft before seq-9 existed) happened to carry. Left un-normalized, a
reviewer diffing "when did each seq-9 rule become effective" would see 7
rules dated 2026-08-19 and 1 (``review.e33g.income-evidence``) dated
2026-07-24 for no doctrinal reason — an authoring-artifact date leaking
into the pack, not a real legal-period distinction (Kimi refuter finding
5, 2026-08-19).

Usage::

    PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack

Exit code 0 only when the fold completes and every internal fail-loud
gate (blocked7-manifest compilation, e31e-source-edits assertions,
0497cb52 zero-ref assertion, final ``RulePackPayload`` schema validation)
passes; non-zero otherwise. This script never signs anything — the output
is a bare, unsigned payload source file, exactly like
``rulepack-prod-007.source.json`` before it was signed into
``rulepack-prod-007.signed.json``.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from backend.scripts.visa_engine.compile_claims import compile_manifest, load_manifest
from backend.services.visa_engine.ast import collect_fact_paths, parse_condition
from backend.services.visa_engine.claim_ledger import ClaimLedgerError, load_claim_ledgers
from backend.services.visa_engine.models import Rule, RulePackPayload

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_THIS_FILE = Path(__file__).resolve()
_BACKEND_ROOT = _THIS_FILE.parents[2]  # apps/backend-rag/backend
_REPO_ROOT = _THIS_FILE.parents[5]

_PACKS_DIR = _BACKEND_ROOT / "services" / "visa_engine" / "contracts" / "packs"
_SEQ7_SOURCE = _PACKS_DIR / "rulepack-prod-007.source.json"
_SEQ7_SIGNED = _PACKS_DIR / "rulepack-prod-007.signed.json"
_SEQ8_SOURCE = _PACKS_DIR / "rulepack-prod-008.source.json"
_SEQ9_SOURCE = _PACKS_DIR / "rulepack-prod-009.source.json"

_E5_DIR = _REPO_ROOT / "research" / "visa" / "doctrine-factory" / "e5"
_INC3_EDITS_DIR = _E5_DIR / "inc3-pack-edits"
_BLOCKED7_MANIFEST = _E5_DIR / "blocked7-rule-manifest.json"
_CURE_E33G = _INC3_EDITS_DIR / "cure-e33g.json"
_E31E_EDITS = _INC3_EDITS_DIR / "e31e-source-edits.json"
_COREF_TABLE_OUT = _INC3_EDITS_DIR / "ee8fe5b8-coref-table.md"

_CLAIMS_DIR = _REPO_ROOT / "research" / "visa" / "doctrine-factory" / "claims"
_LEDGER_FILES = [
    _CLAIMS_DIR / "e2a-claim-ledger.md",
    _CLAIMS_DIR / "e2b-batch1-claim-ledger.md",
    _CLAIMS_DIR / "e2b-batch2-claim-ledger.md",
    _CLAIMS_DIR / "e3a-cf1-resolution.md",
    _CLAIMS_DIR / "e2b-batch3-claim-ledger.md",
    _CLAIMS_DIR / "e2c-blocked5-claim-ledger.md",
]

_PRETTIER_BIN = _REPO_ROOT / "node_modules" / ".bin" / "prettier"

# ---------------------------------------------------------------------------
# seq-9 identity (Anchors section of the E5 inc-3 spec, verified this
# session — see ``_verify_rule_pack_id`` below, never hand-adjusted).
# ---------------------------------------------------------------------------

_SEQ9_SEQUENCE = 9
_SEQ9_VERSION = "2026.8.19"
_SEQ9_RULE_PACK_ID_URL = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/9"
)
_EXPECTED_SEQ9_RULE_PACK_ID = uuid.UUID("66eb0b4c-58ee-56c3-812c-2acc26fff8ce")

# Fixed (not datetime.now()) so re-running this script is byte-identical.
_SEQ9_CREATED_AT = "2026-08-19T00:00:00Z"
_SEQ9_CREATED_BY = "agent.air-m5.backend-rag.visa-e5-seq9-implementer-c.fold-2026-08-19"

# The fold date every NEWLY INSERTED rule's valid_period.from is normalized
# to (module docstring) — deliberately the SAME value as _SEQ9_CREATED_AT,
# but kept as its own named constant since the two fields mean different
# things (pack metadata vs. per-rule legal-effective-date) and could
# legitimately diverge in a future increment.
_SEQ9_NEW_RULE_VALID_FROM = "2026-08-19T00:00:00Z"

# The 11 products whose pricing_key seq-9 folds in from seq-8 (Anchors
# section; verified this session against both packs — exactly these 11
# flip null->non-null between seq-7 and seq-8, the other 27 are unchanged).
_PRICING_FOLD_PRODUCTS = frozenset(
    {"E28A", "E33", "E33E", "E33F", "E33G", "A1", "B1", "C1", "C6", "C2", "BRIDGING"}
)

# The 2 defective seq-7 rules retired with no replacement (Assembly
# decisions #1/#2 — el.e33e.deposit-income-basis is UNSAT and can never
# fire; el.e33g.income-60k-manual is VACUOUS-duplicate and byte-identical
# in intent to the healthy sibling el.e33g.remote-work).
_RETIRED_RULE_IDS = frozenset({"el.e33e.deposit-income-basis", "el.e33g.income-60k-manual"})

# Source record dropped for zero active refs (Assembly decision #4,
# spec Step 4 — assert-then-drop, never presumed).
_DROP_SOURCE_RECORD_ID = "0497cb52-9c10-5ad5-a0ea-596e7678bd9b"

# Co-cited source whose per-rule coverage this fold computes fresh
# (Assembly decision #5) — RULES only, per that decision's own wording
# ("for every rule citing it"); the 3 D1/D2/D12 PRODUCT-level co-refs are
# deliberately untouched (out of this decision's scope) and noted in the
# coref table.
_EE8FE5B8_ID = "ee8fe5b8-b0b4-544a-bf9a-fe53c3e316f2"

# ecd22722 verified_at bump (Step 4 / freshness-2026-08-19.md's own
# recommendation, §1) — the record itself was re-fetched live this
# session's sibling implementer pass and still supports
# el.e31e-child-itas-support / el.e31e-sponsor-itas-itap; it is being
# REPLACED (not re-verified) as the source for the two HARD_FILTER rules,
# so only the record's own verified_at/verified_by move, not any rule's
# source_refs pointing at it for those two facts.
_ECD22722_ID = "ecd22722-3e42-5808-be18-45fbb7d8e9c5"
_ECD22722_VERIFIED_AT = "2026-08-18T21:41:23Z"
_ECD22722_VERIFIED_BY = (
    "agent.air-m5.backend-rag.visa-e5-seq9-implementer-b.qw5-recheck-2026-08-19"
)

# Canonical key order for a rule dict as authored in this pack (verified
# this session against every existing rule in rulepack-prod-007.source.json
# — dict_keys is identical for rule #0 and for review.e33a.*, hand-checked).
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


class FoldPackError(RuntimeError):
    """A fail-loud gate inside the fold tripped — never silently degrade."""


# ---------------------------------------------------------------------------
# Small IO helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _required_facts_for(when: dict[str, Any]) -> list[str]:
    """Independently derive ``required_facts`` from a raw ``when`` dict —
    never trust a manifest/cure-file's own ``required_facts`` field (same
    invariant ``compile_claims.py`` enforces at authoring time; re-derived
    here rather than round-tripped through a Pydantic dump, see module
    docstring).
    """

    parsed = parse_condition(when)
    return sorted(collect_fact_paths(parsed))


def _to_pack_rule_dict(rule_src: dict[str, Any]) -> dict[str, Any]:
    """Build a pack-convention-ordered rule dict from a manifest/cure-file
    rule object, deriving ``required_facts`` fresh from ``when`` (never
    trusting a manifest entry that omits it, or a cure-file entry that
    states it) and dropping any authoring-only ``_``-prefixed comment keys.
    """

    clean = {k: v for k, v in rule_src.items() if not k.startswith("_")}
    required_facts = _required_facts_for(clean["when"])
    out: dict[str, Any] = {}
    for key in _RULE_KEY_ORDER:
        if key == "required_facts":
            out[key] = required_facts
        elif key in clean:
            out[key] = clean[key]
        else:
            raise FoldPackError(f"rule {clean.get('rule_id')!r} is missing required key {key!r}")
    extra = set(clean) - set(_RULE_KEY_ORDER)
    if extra:
        raise FoldPackError(f"rule {clean.get('rule_id')!r} has unexpected key(s): {sorted(extra)}")
    # Fail loud on any schema defect before this rule ever reaches the pack.
    Rule.model_validate(out)
    return out


def _verify_rule_pack_id() -> uuid.UUID:
    computed = uuid.uuid5(uuid.NAMESPACE_URL, _SEQ9_RULE_PACK_ID_URL)
    if computed != _EXPECTED_SEQ9_RULE_PACK_ID:
        raise FoldPackError(
            f"seq-9 rule_pack_id convention drifted: uuid5(NAMESPACE_URL, "
            f"{_SEQ9_RULE_PACK_ID_URL!r}) = {computed}, expected "
            f"{_EXPECTED_SEQ9_RULE_PACK_ID} — do not hand-adjust either side, "
            "investigate why the convention changed"
        )
    return computed


# ---------------------------------------------------------------------------
# Step (b) — identity + chain
# ---------------------------------------------------------------------------


def _apply_identity(payload: dict[str, Any]) -> None:
    rule_pack_id = _verify_rule_pack_id()
    signed = _load_json(_SEQ7_SIGNED)
    previous_payload_sha256 = signed["payload_sha256"]
    if not isinstance(previous_payload_sha256, str) or len(previous_payload_sha256) != 64:
        raise FoldPackError(
            f"{_SEQ7_SIGNED} did not yield a well-formed payload_sha256: "
            f"{previous_payload_sha256!r}"
        )

    payload["sequence"] = _SEQ9_SEQUENCE
    payload["version"] = _SEQ9_VERSION
    payload["rule_pack_id"] = str(rule_pack_id)
    payload["previous_payload_sha256"] = previous_payload_sha256
    payload["created_at"] = _SEQ9_CREATED_AT
    payload["created_by"] = _SEQ9_CREATED_BY
    # rollback_of_payload_sha256 stays null (inherited from seq-7's deep
    # copy) — this is a forward fold, not a rollback.
    # valid_period is deliberately left untouched — see module docstring.


# ---------------------------------------------------------------------------
# Step (c) — pricing_key fold
# ---------------------------------------------------------------------------


def _apply_pricing_fold(payload: dict[str, Any], seq7_original: dict[str, Any]) -> None:
    seq8 = _load_json(_SEQ8_SOURCE)
    seq8_by_code = {p["product_code"]: p for p in seq8["products"]}
    seq7_by_code = {p["product_code"]: p for p in seq7_original["products"]}

    missing = _PRICING_FOLD_PRODUCTS - set(seq8_by_code)
    if missing:
        raise FoldPackError(f"seq-8 source is missing product(s): {sorted(missing)}")

    touched: set[str] = set()
    for product in payload["products"]:
        code = product["product_code"]
        if code in _PRICING_FOLD_PRODUCTS:
            seq8_key = seq8_by_code[code].get("pricing_key")
            if seq8_key is None:
                raise FoldPackError(
                    f"product {code!r} is in the pricing-fold set but seq-8's "
                    "pricing_key is null — refusing to fold a null over the "
                    "intended non-null value"
                )
            product["pricing_key"] = copy.deepcopy(seq8_key)
            touched.add(code)
        else:
            # Byte-identical assertion against seq-7 (T2.c requirement) —
            # `payload` is a deep copy of seq7_original at this point so
            # this is currently a no-op mutation-wise, but the assertion
            # itself is the point: fail loud if that ever stops holding.
            if product.get("pricing_key") != seq7_by_code[code].get("pricing_key"):
                raise FoldPackError(
                    f"product {code!r} pricing_key drifted from seq-7 outside "
                    "the declared 11-product fold set"
                )

    if touched != _PRICING_FOLD_PRODUCTS:
        raise FoldPackError(
            f"pricing fold touched {sorted(touched)}, expected exactly "
            f"{sorted(_PRICING_FOLD_PRODUCTS)}"
        )


# ---------------------------------------------------------------------------
# Step (d) — retire the 2 defective rules
# ---------------------------------------------------------------------------


def _apply_retirements(payload: dict[str, Any]) -> None:
    before = len(payload["rules"])
    payload["rules"] = [r for r in payload["rules"] if r["rule_id"] not in _RETIRED_RULE_IDS]
    removed = before - len(payload["rules"])
    if removed != len(_RETIRED_RULE_IDS):
        raise FoldPackError(
            f"expected to retire exactly {len(_RETIRED_RULE_IDS)} rule(s) "
            f"({sorted(_RETIRED_RULE_IDS)}), actually removed {removed}"
        )


# ---------------------------------------------------------------------------
# Step (e) — insert review.e33g.income-evidence + the 7 blocked7 rules
# ---------------------------------------------------------------------------


def _compile_blocked7() -> list[dict[str, Any]]:
    try:
        ledger = load_claim_ledgers(_LEDGER_FILES)
    except (OSError, ClaimLedgerError) as exc:
        raise FoldPackError(f"failed to load claim ledgers: {exc}") from exc

    manifest = load_manifest(_BLOCKED7_MANIFEST)
    report = compile_manifest(manifest, ledger)
    if not report.ok:
        raise FoldPackError(
            "blocked7-rule-manifest.json failed to compile clean:\n" + report.render()
        )

    return [
        _to_pack_rule_dict(entry.rule.model_dump(mode="json", by_alias=True))
        for entry in report.compiled
    ]


def _load_cure_e33g_review_rule() -> dict[str, Any]:
    cure = _load_json(_CURE_E33G)
    rules_by_id = {r["rule_id"]: r for r in cure["rules"]}
    if "review.e33g.income-evidence" not in rules_by_id:
        raise FoldPackError(f"{_CURE_E33G} does not carry review.e33g.income-evidence")
    # Deliberately NOT pulling in el.e33g.remote-work-configuration — see
    # Assembly decision #2 (module docstring): it would be byte-identical
    # to the pre-existing healthy el.e33g.remote-work sibling.
    return _to_pack_rule_dict(rules_by_id["review.e33g.income-evidence"])


def _normalize_new_rule_valid_from(new_rules: list[dict[str, Any]]) -> None:
    """Every newly-inserted rule's ``valid_period.from`` is normalized to
    the seq-9 fold date (module docstring) — regardless of what a
    prepared-artifact source file (e.g. ``cure-e33g.json``, authored
    2026-07-24 as a standalone draft) happened to carry. Mutates in place.
    """

    for rule in new_rules:
        rule["valid_period"]["from"] = _SEQ9_NEW_RULE_VALID_FROM


def _apply_insertions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    new_rules = [_load_cure_e33g_review_rule(), *_compile_blocked7()]
    _normalize_new_rule_valid_from(new_rules)

    existing_ids = {r["rule_id"] for r in payload["rules"]}
    new_ids = [r["rule_id"] for r in new_rules]
    dupes = existing_ids & set(new_ids)
    if dupes:
        raise FoldPackError(f"new rule id(s) collide with an existing seq-7 rule id: {dupes}")
    if len(set(new_ids)) != len(new_ids):
        raise FoldPackError(f"new rule ids are not unique: {new_ids}")

    payload["rules"] = [*payload["rules"], *new_rules]
    return new_rules


# ---------------------------------------------------------------------------
# Step (f) — E31E source_record edits
# ---------------------------------------------------------------------------


def _apply_e31e_edits(payload: dict[str, Any]) -> None:
    edits = _load_json(_E31E_EDITS)

    records_by_id = {r["source_record_id"]: r for r in payload["source_records"]}
    for edit in edits["source_record_edits"]:
        sid = edit["source_record_id"]
        record = records_by_id.get(sid)
        if record is None:
            raise FoldPackError(f"e31e-source-edits.json names unknown source_record_id {sid!r}")
        if record.get(edit["field"]) != edit["current_value"]:
            raise FoldPackError(
                f"source_record {sid!r} field {edit['field']!r} does not match "
                f"e31e-source-edits.json's declared current_value — ledger drift, "
                "not applying blind"
            )
        record[edit["field"]] = edit["new_value"]

    rules_by_id = {r["rule_id"]: r for r in payload["rules"]}
    for edit in edits["rule_edits"]:
        rid = edit["rule_id"]
        rule = rules_by_id.get(rid)
        if rule is None:
            raise FoldPackError(f"e31e-source-edits.json names unknown rule_id {rid!r}")
        if rule.get(edit["field"]) != edit["current_value"]:
            raise FoldPackError(
                f"rule {rid!r} field {edit['field']!r} does not match "
                "e31e-source-edits.json's declared current_value — ledger drift, "
                "not applying blind"
            )
        rule[edit["field"]] = edit["new_value"]

    for entry in edits["unchanged_by_design"]:
        rid = entry["rule_id"]
        rule = rules_by_id.get(rid)
        if rule is None:
            raise FoldPackError(f"e31e-source-edits.json names unknown rule_id {rid!r}")
        if rule.get("source_refs") != entry["source_refs"]:
            raise FoldPackError(
                f"rule {rid!r} source_refs diverged from e31e-source-edits.json's "
                "'unchanged_by_design' declaration — this rule was supposed to be "
                "untouched"
            )

    # verified_at bump on ecd22722 (Step 4 / freshness-2026-08-19.md §1) —
    # the SAME record still backs el.e31e-child-itas-support /
    # el.e31e-sponsor-itas-itap (confirmed live this session's sibling
    # pass, unchanged by the two rule_edits above).
    ecd22722 = records_by_id.get(_ECD22722_ID)
    if ecd22722 is None:
        raise FoldPackError(f"source_record {_ECD22722_ID!r} not found for verified_at bump")
    ecd22722["verified_at"] = _ECD22722_VERIFIED_AT
    ecd22722["verified_by"] = _ECD22722_VERIFIED_BY


# ---------------------------------------------------------------------------
# Step (g) — drop 0497cb52
# ---------------------------------------------------------------------------


def _apply_drop_0497cb52(payload: dict[str, Any]) -> None:
    rule_refs = sum(1 for r in payload["rules"] if _DROP_SOURCE_RECORD_ID in r["source_refs"])
    product_refs = sum(
        1 for p in payload["products"] if _DROP_SOURCE_RECORD_ID in p.get("source_refs", [])
    )
    if rule_refs or product_refs:
        raise FoldPackError(
            f"{_DROP_SOURCE_RECORD_ID!r} has {rule_refs} rule ref(s) and "
            f"{product_refs} product ref(s) — refusing to drop a still-referenced "
            "source_record"
        )

    before = len(payload["source_records"])
    payload["source_records"] = [
        r for r in payload["source_records"] if r["source_record_id"] != _DROP_SOURCE_RECORD_ID
    ]
    if before - len(payload["source_records"]) != 1:
        raise FoldPackError(f"expected to drop exactly 1 source_record ({_DROP_SOURCE_RECORD_ID})")


# ---------------------------------------------------------------------------
# Step (h) — ee8fe5b8 per-rule co-source coverage
# ---------------------------------------------------------------------------


def _apply_ee8fe5b8_coref(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Assembly decision #5: for every RULE citing ee8fe5b8, drop the
    co-ref if the rule retains >=1 other source; keep it (declared
    residual) if dropping it would leave zero. Product-level refs
    (D1/D2/D12) are out of this decision's scope and are left untouched —
    see the table's own "Scope note" row.
    """

    table_rows: list[dict[str, Any]] = []
    for rule in payload["rules"]:
        refs = rule.get("source_refs", [])
        if _EE8FE5B8_ID not in refs:
            continue
        other_refs = [r for r in refs if r != _EE8FE5B8_ID]
        if other_refs:
            rule["source_refs"] = other_refs
            action = "DROPPED (co-ref removed)"
        else:
            action = "KEPT (would end at zero refs — declared residual)"
        table_rows.append(
            {
                "rule_id": rule["rule_id"],
                "other_refs_remaining": len(other_refs),
                "action": action,
            }
        )
    return table_rows


def _render_and_write_coref_table(rows: list[dict[str, Any]]) -> str:
    residuals = [r for r in rows if r["action"].startswith("KEPT")]
    lines = [
        "---",
        "adversarial_review: exempt-generated-artifact"
        " # regenerable snapshot emitted by fold_pack.py, not a research deliverable",
        "---",
        "",
        "# ee8fe5b8 per-rule co-source coverage — E5 increment 3 seq-9 fold",
        "",
        "Assembly decision #5 (2026-08-19-e5-increment3-spec.md): for every RULE",
        "citing `ee8fe5b8-b0b4-544a-bf9a-fe53c3e316f2` (general \"Izin Tinggal",
        "Keimigrasian\" landing page, freshness-2026-08-19.md verdict CHANGED —",
        "the page's \"Persyaratan Dokumen\" section does not corroborate the 5",
        "facts these rules co-cite it for), drop the co-ref if the rule retains",
        "at least 1 other in-force source; keep it (and declare a residual) if",
        "dropping it would leave the rule with zero sources.",
        "",
        f"18 rules cited ee8fe5b8 in seq-7. {len(rows)} were processed here.",
        f"Residuals (rules that would end at zero refs): {len(residuals)}.",
        "",
        "| rule_id | other refs remaining | action |",
        "|---|---|---|",
    ]
    for row in rows:
        lines.append(f"| `{row['rule_id']}` | {row['other_refs_remaining']} | {row['action']} |")
    lines.extend(
        [
            "",
            "## Scope note — products NOT touched",
            "",
            "Assembly decision #5 reads \"for every rule citing it\" — the 3",
            "PRODUCT-level co-refs (D1, D2, D12), which also cite ee8fe5b8",
            "alongside 2 other sources each, are deliberately left untouched by",
            "this fold. This keeps ee8fe5b8 itself referenced in seq-9 (by those",
            "3 products) even though its rule-level ref count drops to 0 — so it",
            "stays in `source_records`, not dropped like 0497cb52. Re-pointing",
            "the D1/D2/D12 product source_refs is a decision the spec's own",
            "Step 4 write-up (freshness-2026-08-19.md) flags as future CP3",
            "scope, not attempted here.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Step (i) — write with the pack's own formatting convention
# ---------------------------------------------------------------------------


def _write_pack(payload: dict[str, Any], out_path: Path) -> None:
    """Write ``payload`` to ``out_path`` atomically: stage the content (raw
    dump, then Prettier canonicalization) in a temp file in the SAME
    directory, and only replace the real target once both steps succeeded.

    Codex refuter finding 7 (2026-08-19): the previous version wrote
    directly to ``out_path`` and ran Prettier on it AFTER — a Prettier
    failure (binary missing, malformed input, non-zero rc for any reason)
    left the tracked pack file already overwritten with non-canonical
    content, not a fail-before-write. A temp file in the same directory
    (not ``/tmp``) keeps ``Path.replace`` a same-filesystem, atomic rename
    rather than a cross-device copy. The temp filename preserves the
    ``.json`` suffix (``mkstemp``'s ``suffix`` argument) so Prettier's
    extension-based parser inference still resolves to JSON.
    """

    if not _PRETTIER_BIN.exists():
        raise FoldPackError(
            f"prettier binary not found at {_PRETTIER_BIN} — cannot canonicalize "
            "formatting to match the existing packs. Run `npm install` at repo "
            "root first."
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

        # Only now does the tracked file change — a Prettier failure above
        # raised before this line ever runs, leaving out_path untouched.
        tmp_path.replace(out_path)
    finally:
        # tmp_path no longer exists at this name once replace() succeeds;
        # on any earlier failure, clean up the leftover temp file so a
        # failed fold never leaves a stray non-canonical sibling on disk.
        if tmp_path.exists():
            tmp_path.unlink()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def assemble_payload() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Build the seq-9 payload dict in memory (no I/O to the output file).

    Returns ``(payload, new_rules, ee8fe5b8_table_rows)``.
    """

    seq7_original = _load_json(_SEQ7_SOURCE)
    payload = copy.deepcopy(seq7_original)

    _apply_identity(payload)
    _apply_pricing_fold(payload, seq7_original)
    _apply_retirements(payload)
    new_rules = _apply_insertions(payload)
    _apply_e31e_edits(payload)
    _apply_drop_0497cb52(payload)
    ee8fe5b8_rows = _apply_ee8fe5b8_coref(payload)

    # Final structural gate — fail loud before ever writing to disk.
    try:
        RulePackPayload.model_validate(payload)
    except Exception as exc:
        raise FoldPackError(f"assembled seq-9 payload failed RulePackPayload validation: {exc}") from exc

    return payload, new_rules, ee8fe5b8_rows


def main(argv: list[str] | None = None) -> int:
    del argv  # no CLI flags — deterministic single-purpose script
    try:
        payload, new_rules, ee8fe5b8_rows = assemble_payload()
    except FoldPackError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    _write_pack(payload, _SEQ9_SOURCE)

    table_md = _render_and_write_coref_table(ee8fe5b8_rows)
    _COREF_TABLE_OUT.write_text(table_md, encoding="utf-8")

    print(f"wrote {_SEQ9_SOURCE} — {len(payload['rules'])} rule(s), "
          f"{len(payload['products'])} product(s), {len(payload['source_records'])} source_record(s)")
    print(f"inserted {len(new_rules)} new rule(s): {[r['rule_id'] for r in new_rules]}")
    print()
    print(table_md)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
