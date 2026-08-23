"""fold_pack_seq13_rules.py — assemble RulePack seq-13's RULES-ONLY half from
seq-12 + the inc6 cure.

E5 increment 6. This fold covers ONLY the rule-graph half of seq-13 — a
separate lane owns re-verifying the 18 portal `source_records` for freshness
(the seq-12 pattern this repo already uses for that concern, `fold_pack_
seq12.py`); a third step folds both halves together into the actual
`rulepack-prod-013.source.json`. This module therefore does **not** write
that file — it writes an intermediate `rulepack-prod-013.rules-only.json`
carrying the full RulePackPayload shape with `source_records` and
`sequence`/`version`/`rule_pack_id`/`previous_payload_sha256`/`created_at`/
`created_by` left at seq-12's own values (the combining step owns identity
and chaining; this fold's job is provably correct RULE bytes, nothing else).

**A rule tightening is a DATA entry, never bespoke code.** Every fix this
fold applies — one rule or nine — is one or more entries in `inc6-pack-edits/
inc6-rule-manifest.json` (the claim-backed body, compiled through `compile_
claims`) plus the matching declarative entries in `inc6-pack-edits/cure-
seq13-rule-tightenings.json` (`rule_edits`/`insertions`, with ledger-drift
{current_value, new_value} pairs). The set of edited/inserted rule_ids is
**derived from the cure file at run time** (`_edited_rule_ids`/`_inserted_
rule_ids` below) — there is no hardcoded tuple anywhere in this module to
fall out of sync. Adding a fix means adding manifest + cure entries; it
never means touching this file's logic. The "delta is exactly what was
declared" sweep (`_assert_untouched`) enumerates its touched-rule set from
that same cure data, so an accidental Nth change (one nobody added an entry
for) fails the sweep by construction rather than silently widening the diff.

Fixes carried by the current manifest/cure data, closing the gap
`.agents/skills/visaoracle/SKILL.md`'s 2026-08-23 LIVE STATE entry names as
"audit the class, not patch one rule" — `hit_policy.eligibility =
COVER_ALL_DECLARED_PURPOSES` makes rule coverage OR-like, so ONE untouched
broad SUPPORT rule silently carries a product past every tightened sibling:

1. **E31C nationality leg** (Fix 1). `el.e31c-child-mixed-marriage-support`
   is edited in place to add the `family.sponsor_nationalities intersects
   [ID]` conjunct its sibling `el.e31c-mixed-marriage-parents` already
   carries (seq-10) — proven live against the real evaluator to reach
   SUPPORTED for a child of two foreign parents on its own. A paired
   HARD_FILTER `hf.e31c-sponsor-not-indonesian` is inserted, mirroring
   `hf.e31c-marriage-not-registered`'s exact shape (seq-10), so a FUTURE
   untouched sibling cannot silently re-open the same gap — HARD_FILTER
   stage runs before any SUPPORT rule is even consulted.
2. **D12 missing sibling conjunct** (Fix 3). `el.d12-multi-entry-support` is
   the only one of D12's 6 ELIGIBILITY rules missing `investment.
   pt_pma_committed != true`, restructured in place into the identical
   nested-all shape its 5 siblings already use. Mutation-proven red->green:
   adding the conjunct makes all 7 D12 rules resolve FALSE for a
   `pt_pma_committed=True` applicant.
3. **Sponsor-status value check** (Fix 4). Nine rules across four products
   (E31B/E31E/E31H/E31J) test `family.sponsor_status_code` with `op:known`
   — presence only, never value, so any non-empty string (a visit-visa code,
   an expired permit) passes a rule literally named `*-sponsor-itas-itap`.
   Each of the nine is edited in place to `op:in, values:[ITAS_ACTIVE,
   ITAP_ACTIVE, VITAS_APPROVED]` — grounded by four independently-worded
   articles, one per product (Permenkumham 22/2023 Pasal 44(2)(b)/47(2)(c)/
   50(2)(b), 11/2024 Pasal 50A(2)(c) for E31J), each with its own VITAS
   fallback clause (44(3)/47(3)/50(3)/50A(3)) — see `inc6-sponsor-status-
   claim-ledger.md`.

**E31D is deliberately NOT touched by this fold.** The team-lead's mandate
named a third fix there; `research/visa/2026-08-15-gold-family-refuter.md`
explicitly blocks a direct pack edit for it — the fact vocabulary has no
STEPCHILD `relation_to_sponsor` value and no dedicated WNA-WNI
mixed-marriage-basis fact (re-verified live 2026-08-23: `RelationType` enum
and all three `el.e31d-*` rules are byte-unchanged since that audit), and
overloading the existing CHILD/PARENT facts with new semantics is the exact
"legally misleading boundary" the refuter warns against. That fix needs a
Zero/legal decision plus a fact-vocabulary extension (backend reader +
frontend writer) — outside a RULES-ONLY fold's authority.

Every input is read from disk at run time. The chain hash is read LIVE from
`rulepack-prod-012.signed.json` and asserted against the expected anchor; the
seq-12 source bytes are additionally re-hashed (RFC 8785 JCS) and must equal
that same value — a source/signed mismatch aborts the fold. Every rule edit
carries ledger-drift guards ({current_value, new_value} pairs asserted against
the seq-12 bytes before mutating), and the compiled body from `compile_
claims` is cross-checked byte-for-byte against the cure file's own
declarative edit — two independent statements of the new rule body, any
mismatch aborts. Deterministic: fixed timestamps, no `datetime.now()` —
re-running is byte-identical.

Usage::

    PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq13_rules
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
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
_SEQ12_SOURCE = _PACKS_DIR / "rulepack-prod-012.source.json"
_SEQ12_SIGNED = _PACKS_DIR / "rulepack-prod-012.signed.json"
_SEQ13_RULES_ONLY_OUT = _PACKS_DIR / "rulepack-prod-013.rules-only.json"

_E5_DIR = _REPO_ROOT / "research" / "visa" / "doctrine-factory" / "e5"
_INC6_EDITS_DIR = _E5_DIR / "inc6-pack-edits"
_CURE_FILE = _INC6_EDITS_DIR / "cure-seq13-rule-tightenings.json"
_INC6_MANIFEST = _INC6_EDITS_DIR / "inc6-rule-manifest.json"

_CLAIMS_DIR = _REPO_ROOT / "research" / "visa" / "doctrine-factory" / "claims"
_LEDGER_FILES = [
    _CLAIMS_DIR / "e2a-claim-ledger.md",
    _CLAIMS_DIR / "inc4-c2-e31c-claim-ledger.md",
    _CLAIMS_DIR / "inc6-sponsor-status-claim-ledger.md",
]

_PRETTIER_BIN = _REPO_ROOT / "node_modules" / ".bin" / "prettier"

# ---------------------------------------------------------------------------
# Chain verification against the SIGNED seq-12 pack (identity itself is left
# to the combining fold — see module docstring).
# ---------------------------------------------------------------------------

_EXPECTED_SEQ12_PAYLOAD_SHA256 = (
    "ff43d55e79e833a91820c4b68dd9ffdd086e7969b3b3a44dbd80747aa451406d"
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


class FoldPackError(RuntimeError):
    """A fail-loud gate inside the fold tripped — never silently degrade."""


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _verify_chain(seq12_source: dict[str, Any]) -> str:
    signed = _load_json(_SEQ12_SIGNED)
    declared = signed.get("payload_sha256")
    if declared != _EXPECTED_SEQ12_PAYLOAD_SHA256:
        raise FoldPackError(
            f"{_SEQ12_SIGNED} declares payload_sha256={declared!r}, expected "
            f"{_EXPECTED_SEQ12_PAYLOAD_SHA256!r} — the signed seq-12 on disk is "
            "not the one this fold was authored against"
        )
    recomputed = hashlib.sha256(canonicalize_json(seq12_source)).hexdigest()
    if recomputed != declared:
        raise FoldPackError(
            f"seq-12 SOURCE bytes re-hash to {recomputed}, but the signed file "
            f"declares {declared} — source/signed mismatch, refusing to chain"
        )
    return declared


# ---------------------------------------------------------------------------
# Data-driven touched-rule sets — derived from the cure file, never hardcoded.
# Adding a fix means adding cure/manifest entries, never editing these.
# ---------------------------------------------------------------------------


def _edited_rule_ids(cure: dict[str, Any]) -> tuple[str, ...]:
    """Every rule_id named by ``cure["rule_edits"]``, in first-seen order,
    deduplicated (one rule commonly carries 2+ field edits, e.g. `when` +
    `required_facts`)."""

    seen: list[str] = []
    for edit in cure["rule_edits"]:
        rid = edit["rule_id"]
        if rid not in seen:
            seen.append(rid)
    return tuple(seen)


def _inserted_rule_ids(cure: dict[str, Any]) -> tuple[str, ...]:
    return tuple(e["rule_id"] for e in cure["insertions"])


# ---------------------------------------------------------------------------
# Compile the inc6 manifest against the claim ledgers
# ---------------------------------------------------------------------------


def _compile_inc6_rules(cure: dict[str, Any]) -> dict[str, dict[str, Any]]:
    try:
        ledger = load_claim_ledgers(_LEDGER_FILES)
    except (OSError, ClaimLedgerError) as exc:
        raise FoldPackError(f"failed to load claim ledgers: {exc}") from exc

    manifest = load_manifest(_INC6_MANIFEST)
    report = compile_manifest(manifest, ledger)
    if not report.ok:
        raise FoldPackError("inc6-rule-manifest.json failed to compile clean:\n" + report.render())

    compiled: dict[str, dict[str, Any]] = {}
    for entry in report.compiled:
        rule_dict = _to_pack_rule_dict(entry.rule.model_dump(mode="json", by_alias=True))
        compiled[rule_dict["rule_id"]] = rule_dict

    # Two independent declarations of "what this fold touches" — the
    # manifest's compiled output and the cure file's edits/insertions — must
    # name exactly the same rule_ids, or one of the two data files drifted
    # from the other without anyone updating its twin.
    expected = set(_edited_rule_ids(cure)) | set(_inserted_rule_ids(cure))
    if set(compiled) != expected:
        raise FoldPackError(
            f"manifest compiled {sorted(compiled)}, cure file declares "
            f"{sorted(expected)} — manifest and cure file have drifted apart"
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
# Apply the two in-place edits + one insertion, all cross-checked against
# the compiled bodies above.
# ---------------------------------------------------------------------------


def _rule_edits_for(cure: dict[str, Any], rule_id: str) -> list[dict[str, Any]]:
    edits = [e for e in cure["rule_edits"] if e["rule_id"] == rule_id]
    if not edits:
        raise FoldPackError(f"cure file declares no rule_edits for {rule_id!r}")
    return edits


def _seq12_baseline_value(seq12_source: dict[str, Any], rule_id: str, key: str) -> Any:
    """The seq-12 value for ``key`` on ``rule_id``: for a field this cure
    edits, the correct baseline is the cure file's own declared
    ``current_value`` (already drift-asserted against the real bytes); for
    every other key the edit never touches it, so the post-edit value IS
    the seq-12 value — read straight off the source pack."""

    rule = next(r for r in seq12_source["rules"] if r["rule_id"] == rule_id)
    return rule.get(key)


def _apply_rule_edits(
    payload: dict[str, Any], seq12_source: dict[str, Any], cure: dict[str, Any],
    compiled: dict[str, dict[str, Any]],
) -> None:
    rules_by_id = {r["rule_id"]: r for r in payload["rules"]}

    for rule_id in _edited_rule_ids(cure):
        edited = rules_by_id.get(rule_id)
        if edited is None:
            raise FoldPackError(f"rule {rule_id!r} not found for the seq-13 edit")

        touched_fields: set[str] = set()
        for edit in _rule_edits_for(cure, rule_id):
            field = edit["field"]
            touched_fields.add(field)
            if edited.get(field) != edit["current_value"]:
                raise FoldPackError(
                    f"rule {rule_id!r} field {field!r} does not match "
                    "cure-seq13-rule-tightenings.json's declared current_value — "
                    "ledger drift, not applying blind"
                )
            edited[field] = edit["new_value"]

        compiled_edit = compiled[rule_id]
        if _canon(edited) != _canon(compiled_edit):
            raise FoldPackError(
                f"the edited {rule_id!r} does not equal the manifest-compiled "
                "body — cure file and manifest have drifted apart"
            )

        diff_keys = {
            k
            for k in _RULE_KEY_ORDER
            if _canon(compiled_edit.get(k)) != _canon(_seq12_baseline_value(seq12_source, rule_id, k))
        }
        if diff_keys != touched_fields:
            raise FoldPackError(
                f"{rule_id!r} edit touched {sorted(diff_keys)}, cure file "
                f"declares exactly {sorted(touched_fields)} — only the "
                "declared fields may change"
            )


def _apply_insertions(payload: dict[str, Any], cure: dict[str, Any], compiled: dict[str, dict[str, Any]]) -> None:
    cure_insertions = cure["insertions"]
    declared_ids = [e["rule_id"] for e in cure_insertions]
    if len(declared_ids) != len(set(declared_ids)):
        raise FoldPackError(
            f"cure-seq13-rule-tightenings.json insertions names a duplicate "
            f"rule_id: {declared_ids!r}"
        )

    rules_by_id = {r["rule_id"]: r for r in payload["rules"]}
    for cure_ins_raw in cure_insertions:
        rule_id = cure_ins_raw["rule_id"]
        inserted = copy.deepcopy(compiled[rule_id])
        cure_ins = {k: v for k, v in cure_ins_raw.items() if not k.startswith("_")}
        for key in _RULE_KEY_ORDER:
            if _canon(cure_ins.get(key)) != _canon(inserted.get(key)):
                raise FoldPackError(
                    f"cure-seq13-rule-tightenings.json insertion field {key!r} for "
                    f"{rule_id!r} does not match the manifest-compiled rule — cure "
                    "file and manifest drifted apart"
                )
        if rule_id in rules_by_id:
            raise FoldPackError(f"rule {rule_id!r} already exists — cannot insert")
        payload["rules"] = [*payload["rules"], inserted]
        rules_by_id[rule_id] = inserted


# ---------------------------------------------------------------------------
# Byte-invariance sweep — everything not declared touched must match seq-12
# ---------------------------------------------------------------------------

_IDENTITY_KEYS = frozenset(
    {"sequence", "version", "rule_pack_id", "previous_payload_sha256", "created_at", "created_by"}
)


def _assert_untouched(payload: dict[str, Any], seq12: dict[str, Any], cure: dict[str, Any]) -> None:
    """Enumerate the touched-rule set from the cure file's OWN data (never a
    hardcoded tuple) — this is the guard that stops a fold from silently
    carrying an Nth change nobody added a manifest/cure entry for: any rule
    not named by `cure["rule_edits"]`/`cure["insertions"]` must be
    byte-identical to seq-12, full stop."""

    for key in set(seq12) | set(payload):
        if key in _IDENTITY_KEYS or key == "rules":
            continue
        if _canon(payload.get(key)) != _canon(seq12.get(key)):
            raise FoldPackError(
                f"top-level payload key {key!r} drifted from seq-12 — this fold "
                "declares no edit there (products/source_records are untouched: "
                "the rules-only lane owns neither)"
            )

    seq12_rules = {r["rule_id"]: r for r in seq12["rules"]}
    new_rules = {r["rule_id"]: r for r in payload["rules"]}
    touched_rules = set(_edited_rule_ids(cure)) | set(_inserted_rule_ids(cure))

    for rid, rule in new_rules.items():
        if rid in touched_rules:
            continue
        if rid not in seq12_rules or _canon(rule) != _canon(seq12_rules[rid]):
            raise FoldPackError(f"rule {rid!r} drifted from seq-12 outside the declared edit set")
    missing = set(seq12_rules) - set(new_rules)
    if missing:
        raise FoldPackError(f"rule(s) vanished unexpectedly: {sorted(missing)}")


# ---------------------------------------------------------------------------
# Write (atomic + prettier — fold_pack.py's Codex-finding-7 shape)
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
    seq12_original = _load_json(_SEQ12_SOURCE)
    _verify_chain(seq12_original)
    payload = copy.deepcopy(seq12_original)

    cure = _load_json(_CURE_FILE)
    compiled = _compile_inc6_rules(cure)
    _apply_rule_edits(payload, seq12_original, cure, compiled)
    _apply_insertions(payload, cure, compiled)
    _assert_untouched(payload, seq12_original, cure)

    try:
        RulePackPayload.model_validate(payload)
    except Exception as exc:  # re-raised loud with context
        raise FoldPackError(
            f"assembled seq-13 rules-only payload failed RulePackPayload validation: {exc}"
        ) from exc

    return payload


def main(argv: list[str] | None = None) -> int:
    del argv  # no CLI flags — deterministic single-purpose script
    try:
        payload = assemble_payload()
    except FoldPackError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    _write_pack(payload, _SEQ13_RULES_ONLY_OUT)
    print(
        f"wrote {_SEQ13_RULES_ONLY_OUT} — {len(payload['rules'])} rule(s), "
        f"{len(payload['products'])} product(s), {len(payload['source_records'])} source_record(s)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
