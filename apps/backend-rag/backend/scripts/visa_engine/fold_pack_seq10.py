"""fold_pack_seq10.py — assemble RulePack seq-10 from seq-9 + the inc4 edits.

E5 increment 4 (spec: research/visa/doctrine-factory/e5/
2026-08-19-e5-increment4-spec.md). Two concerns, nothing else changes:

1. **Source re-stamp** (Phase A): 17 stale OFFICIAL_PORTAL records get
   ``verified_at``/``verified_by`` bumped, each backed by a live QW-5-method
   re-verification (inc4-pack-edits/freshness-restamp-2026-08-19.md); the
   18th (``ee8fe5b8``, CHANGED on two independent rechecks) loses its 3
   remaining PRODUCT-level co-refs (D1/D2/D12) and is dropped at zero refs
   (0497cb52 precedent).
2. **Cure of the two CP3 lint residuals** (Phase B):
   ``el.c2.corporate-sponsor-type`` RETIRED (its deduped condition is
   canonical-JSON-identical to ``el.c2.business``'s entire ``when``; the
   corporate-sponsor grounding attempt was refuted by the live C2 page —
   CF-17); ``el.e31c-mixed-marriage-parents`` tightened in place and
   ``hf.e31c-marriage-not-registered`` inserted, both compiled through
   ``compile_claims`` against the inc4 ledger (CL-E31C-02/03, VERIFIED).

Every input is read from disk at run time. The chain hash is read LIVE from
``rulepack-prod-009.signed.json`` and asserted against the expected anchor;
the seq-9 source bytes are additionally re-hashed (RFC 8785 JCS) and must
equal that same value — a source/signed mismatch aborts the fold. All edits
carry ledger-drift guards ({current_value, new_value} pairs asserted against
the seq-9 bytes before mutating). Deterministic: fixed timestamps, no
``datetime.now()`` — re-running is byte-identical (idempotence is proven by
hashing the output twice in the ship notes, not assumed).

Usage::

    PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq10
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
_SEQ9_SOURCE = _PACKS_DIR / "rulepack-prod-009.source.json"
_SEQ9_SIGNED = _PACKS_DIR / "rulepack-prod-009.signed.json"
_SEQ10_SOURCE = _PACKS_DIR / "rulepack-prod-010.source.json"

_E5_DIR = _REPO_ROOT / "research" / "visa" / "doctrine-factory" / "e5"
_INC4_EDITS_DIR = _E5_DIR / "inc4-pack-edits"
_RESTAMP_EDITS = _INC4_EDITS_DIR / "source-restamp-edits.json"
_CURE_FILE = _INC4_EDITS_DIR / "cure-c2-e31c.json"
_INC4_MANIFEST = _INC4_EDITS_DIR / "inc4-rule-manifest.json"

_CLAIMS_DIR = _REPO_ROOT / "research" / "visa" / "doctrine-factory" / "claims"
_LEDGER_FILES = [
    _CLAIMS_DIR / "e2a-claim-ledger.md",
    _CLAIMS_DIR / "e2b-batch1-claim-ledger.md",
    _CLAIMS_DIR / "e2b-batch2-claim-ledger.md",
    _CLAIMS_DIR / "e3a-cf1-resolution.md",
    _CLAIMS_DIR / "e2b-batch3-claim-ledger.md",
    _CLAIMS_DIR / "e2c-blocked5-claim-ledger.md",
    _CLAIMS_DIR / "inc4-c2-e31c-claim-ledger.md",
]

_PRETTIER_BIN = _REPO_ROOT / "node_modules" / ".bin" / "prettier"

# ---------------------------------------------------------------------------
# seq-10 identity (spec §1 — the uuid5 anchor is verified, never assumed)
# ---------------------------------------------------------------------------

_SEQ10_SEQUENCE = 10
_SEQ10_VERSION = "2026.8.19"  # same-day precedent: seq-2/seq-3 shared 2026.8.8
_SEQ10_RULE_PACK_ID_URL = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/10"
)
_EXPECTED_SEQ10_RULE_PACK_ID = uuid.UUID("d390c8eb-926d-5c37-9bbb-83e4a8601195")

# The signed seq-9 payload hash this pack must chain to. Read LIVE from the
# signed file at run time AND asserted equal to this anchor AND equal to the
# recomputed canonical hash of the seq-9 SOURCE bytes — three independent
# derivations of one value, any mismatch aborts.
_EXPECTED_SEQ9_PAYLOAD_SHA256 = (
    "47feff8246c608c7c6085ffdac776fdc020bb56688d5f35a0a3e685eb40f271e"
)

# Fixed (not datetime.now()) so re-running this script is byte-identical.
_SEQ10_CREATED_AT = "2026-08-19T05:00:00Z"
_SEQ10_CREATED_BY = "agent.air-m5.backend-rag.visa-e5-seq10-orchestrator.fold-2026-08-19"
_SEQ10_NEW_RULE_VALID_FROM = "2026-08-19T00:00:00Z"

# Phase B constants.
_RETIRED_RULE_ID = "el.c2.corporate-sponsor-type"
_EDITED_RULE_ID = "el.e31c-mixed-marriage-parents"
_INSERTED_RULE_ID = "hf.e31c-marriage-not-registered"
_C2_HEALTHY_SIBLING = "el.c2.business"

# Phase A constants.
_EE8FE5B8_ID = "ee8fe5b8-b0b4-544a-bf9a-fe53c3e316f2"
_EE8FE5B8_PRODUCTS = ("D1", "D2", "D12")

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


# ---------------------------------------------------------------------------
# Identity + chain
# ---------------------------------------------------------------------------


def _verify_rule_pack_id() -> uuid.UUID:
    computed = uuid.uuid5(uuid.NAMESPACE_URL, _SEQ10_RULE_PACK_ID_URL)
    if computed != _EXPECTED_SEQ10_RULE_PACK_ID:
        raise FoldPackError(
            f"seq-10 rule_pack_id convention drifted: uuid5(NAMESPACE_URL, "
            f"{_SEQ10_RULE_PACK_ID_URL!r}) = {computed}, expected "
            f"{_EXPECTED_SEQ10_RULE_PACK_ID} — do not hand-adjust either side"
        )
    return computed


def _chain_hash(seq9_source: dict[str, Any]) -> str:
    signed = _load_json(_SEQ9_SIGNED)
    declared = signed.get("payload_sha256")
    if declared != _EXPECTED_SEQ9_PAYLOAD_SHA256:
        raise FoldPackError(
            f"{_SEQ9_SIGNED} declares payload_sha256={declared!r}, expected "
            f"{_EXPECTED_SEQ9_PAYLOAD_SHA256!r} — the signed seq-9 on disk is "
            "not the one this fold was authored against"
        )
    recomputed = hashlib.sha256(canonicalize_json(seq9_source)).hexdigest()
    if recomputed != declared:
        raise FoldPackError(
            f"seq-9 SOURCE bytes re-hash to {recomputed}, but the signed file "
            f"declares {declared} — source/signed mismatch, refusing to chain"
        )
    return declared


def _apply_identity(payload: dict[str, Any], seq9_source: dict[str, Any]) -> None:
    payload["sequence"] = _SEQ10_SEQUENCE
    payload["version"] = _SEQ10_VERSION
    payload["rule_pack_id"] = str(_verify_rule_pack_id())
    payload["previous_payload_sha256"] = _chain_hash(seq9_source)
    payload["created_at"] = _SEQ10_CREATED_AT
    payload["created_by"] = _SEQ10_CREATED_BY
    # rollback_of_payload_sha256 stays null; valid_period untouched.


# ---------------------------------------------------------------------------
# Phase A — source re-stamp + ee8fe5b8 drop
# ---------------------------------------------------------------------------


def _apply_restamps(payload: dict[str, Any]) -> int:
    edits = _load_json(_RESTAMP_EDITS)
    records_by_id = {r["source_record_id"]: r for r in payload["source_records"]}

    restamps = edits["restamps"]
    if len(restamps) != 17:
        raise FoldPackError(f"expected exactly 17 restamps, edit file carries {len(restamps)}")

    for edit in restamps:
        sid = edit["source_record_id"]
        record = records_by_id.get(sid)
        if record is None:
            raise FoldPackError(f"restamp names unknown source_record_id {sid!r}")
        if record.get("verified_at") != edit["current_verified_at"] or record.get(
            "verified_by"
        ) != edit["current_verified_by"]:
            raise FoldPackError(
                f"source_record {sid!r} verified_at/verified_by do not match the "
                "edit file's declared current values — ledger drift, not applying blind"
            )
        record["verified_at"] = edit["new_verified_at"]
        record["verified_by"] = edit["new_verified_by"]

    return len(restamps)


def _apply_ee8fe5b8_drop(payload: dict[str, Any]) -> None:
    drop = _load_json(_RESTAMP_EDITS)["drop_ee8fe5b8"]
    if drop["source_record_id"] != _EE8FE5B8_ID:
        raise FoldPackError("drop_ee8fe5b8 names an unexpected source_record_id")
    # The edit file's declarative removal list is CONSUMED, not decorative
    # (Codex refuter finding 5: a drift in `product_ref_removals` must fail
    # loud, never be papered over by a hardcoded constant) — and it must
    # name exactly the products that actually cite the record.
    declared = tuple(drop["product_ref_removals"])
    if declared != _EE8FE5B8_PRODUCTS:
        raise FoldPackError(
            f"drop_ee8fe5b8.product_ref_removals = {declared!r}, this fold was "
            f"authored for {_EE8FE5B8_PRODUCTS!r} — ledger drift, not applying blind"
        )
    citing = tuple(
        p["product_code"]
        for p in payload["products"]
        if _EE8FE5B8_ID in p.get("source_refs", [])
    )
    if set(citing) != set(declared):
        raise FoldPackError(
            f"products citing ee8fe5b8 = {sorted(citing)}, edit file declares "
            f"{sorted(declared)} — the seq-9 bytes drifted"
        )

    products_by_code = {p["product_code"]: p for p in payload["products"]}
    for code in _EE8FE5B8_PRODUCTS:
        product = products_by_code.get(code)
        if product is None:
            raise FoldPackError(f"product {code!r} not found for ee8fe5b8 co-ref removal")
        refs = product.get("source_refs", [])
        if _EE8FE5B8_ID not in refs:
            raise FoldPackError(
                f"product {code!r} does not cite ee8fe5b8 — the seq-9 bytes drifted "
                "from what this fold was authored against"
            )
        remaining = [r for r in refs if r != _EE8FE5B8_ID]
        if not remaining:
            raise FoldPackError(f"removing ee8fe5b8 would leave product {code!r} at zero refs")
        product["source_refs"] = remaining

    # Assert-then-drop (0497cb52 precedent): zero refs anywhere.
    rule_refs = sum(1 for r in payload["rules"] if _EE8FE5B8_ID in r.get("source_refs", []))
    product_refs = sum(
        1 for p in payload["products"] if _EE8FE5B8_ID in p.get("source_refs", [])
    )
    if rule_refs or product_refs:
        raise FoldPackError(
            f"ee8fe5b8 still has {rule_refs} rule ref(s) and {product_refs} product "
            "ref(s) after the declared removals — refusing to drop"
        )
    before = len(payload["source_records"])
    payload["source_records"] = [
        r for r in payload["source_records"] if r["source_record_id"] != _EE8FE5B8_ID
    ]
    if before - len(payload["source_records"]) != 1:
        raise FoldPackError("expected to drop exactly 1 source_record (ee8fe5b8)")


# ---------------------------------------------------------------------------
# Phase B — retirement + compiled cure rules
# ---------------------------------------------------------------------------


def _apply_retirement(payload: dict[str, Any]) -> None:
    # Consume the cure file's declarative retirement list (Codex refuter
    # finding 5): exactly one entry, naming exactly the constant.
    cure_retirements = _load_json(_CURE_FILE)["retirements"]
    if [e["rule_id"] for e in cure_retirements] != [_RETIRED_RULE_ID]:
        raise FoldPackError(
            f"cure-c2-e31c.json retirements = "
            f"{[e['rule_id'] for e in cure_retirements]!r}, this fold was "
            f"authored for [{_RETIRED_RULE_ID!r}] — ledger drift, not applying blind"
        )
    rules_by_id = {r["rule_id"]: r for r in payload["rules"]}
    retired = rules_by_id.get(_RETIRED_RULE_ID)
    if retired is None:
        raise FoldPackError(f"rule {_RETIRED_RULE_ID!r} not found — nothing to retire")
    sibling = rules_by_id.get(_C2_HEALTHY_SIBLING)
    if sibling is None:
        raise FoldPackError(
            f"healthy sibling {_C2_HEALTHY_SIBLING!r} not found — retirement would "
            "change C2 behavior, refusing"
        )

    # The retirement is behavior-preserving ONLY if the retired rule's deduped
    # condition equals the sibling's entire `when` and both effects SUPPORT the
    # same purposes. Assert it — never assume it survived since authoring.
    when = retired.get("when", {})
    args = when.get("args") if isinstance(when, dict) else None
    if not (
        isinstance(args, list)
        and len(args) == 2
        and _canon(args[0]) == _canon(args[1])
        and _canon(args[0]) == _canon(sibling["when"])
    ):
        raise FoldPackError(
            f"{_RETIRED_RULE_ID!r} is no longer the all(X,X) duplicate of "
            f"{_C2_HEALTHY_SIBLING!r}'s when — the retirement rationale does not "
            "hold, refusing"
        )
    if retired["effect"].get("type") != "SUPPORT" or sibling["effect"].get("type") != "SUPPORT":
        raise FoldPackError("retirement rationale requires both rules to be SUPPORT effects")
    if retired["effect"].get("covered_purposes") != sibling["effect"].get("covered_purposes"):
        raise FoldPackError(
            "retired rule and sibling cover different purposes — retirement would "
            "change coverage, refusing"
        )
    # Kimi refuter finding 5: when-duplication + effect alone do not prove
    # behavior preservation — priority, on_unknown, validity window, scope
    # and product binding all feed the evaluator too. Assert every one.
    for key in ("stage", "scope", "priority", "on_unknown", "valid_period", "product_version_ids"):
        if _canon(retired.get(key)) != _canon(sibling.get(key)):
            raise FoldPackError(
                f"retired rule and sibling differ on {key!r} — retirement is not "
                "provably behavior-preserving, refusing"
            )

    payload["rules"] = [r for r in payload["rules"] if r["rule_id"] != _RETIRED_RULE_ID]


def _compile_inc4_rules() -> dict[str, dict[str, Any]]:
    try:
        ledger = load_claim_ledgers(_LEDGER_FILES)
    except (OSError, ClaimLedgerError) as exc:
        raise FoldPackError(f"failed to load claim ledgers: {exc}") from exc

    manifest = load_manifest(_INC4_MANIFEST)
    report = compile_manifest(manifest, ledger)
    if not report.ok:
        raise FoldPackError("inc4-rule-manifest.json failed to compile clean:\n" + report.render())

    compiled: dict[str, dict[str, Any]] = {}
    for entry in report.compiled:
        rule_dict = _to_pack_rule_dict(entry.rule.model_dump(mode="json", by_alias=True))
        compiled[rule_dict["rule_id"]] = rule_dict
    expected = {_EDITED_RULE_ID, _INSERTED_RULE_ID}
    if set(compiled) != expected:
        raise FoldPackError(
            f"manifest compiled {sorted(compiled)}, expected exactly {sorted(expected)}"
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


def _apply_e31c_cure(payload: dict[str, Any], compiled: dict[str, dict[str, Any]]) -> None:
    cure = _load_json(_CURE_FILE)
    rules_by_id = {r["rule_id"]: r for r in payload["rules"]}

    # --- In-place edit, double-entry: the cure file's ledger-drift pairs are
    # asserted against the seq-9 bytes; the RESULT must equal the compiled
    # rule from the manifest (two independent statements of the new body).
    edited = rules_by_id.get(_EDITED_RULE_ID)
    if edited is None:
        raise FoldPackError(f"rule {_EDITED_RULE_ID!r} not found for the E31C edit")
    for edit in cure["rule_edits"]:
        if edit["rule_id"] != _EDITED_RULE_ID:
            raise FoldPackError(f"unexpected rule_edit target {edit['rule_id']!r}")
        if edited.get(edit["field"]) != edit["current_value"]:
            raise FoldPackError(
                f"rule {_EDITED_RULE_ID!r} field {edit['field']!r} does not match "
                "cure-c2-e31c.json's declared current_value — ledger drift, not "
                "applying blind"
            )
        edited[edit["field"]] = edit["new_value"]

    compiled_edit = compiled[_EDITED_RULE_ID]
    if _canon(edited) != _canon(compiled_edit):
        raise FoldPackError(
            f"the edited {_EDITED_RULE_ID!r} does not equal the manifest-compiled "
            "body — cure file and manifest have drifted apart"
        )
    diff_keys = {
        k
        for k in _RULE_KEY_ORDER
        if _canon(compiled_edit.get(k)) != _canon(cure_seq9_baseline(cure, k))
    }
    # (helper below returns the seq-9 value for `when`/`required_facts` from the
    # cure file's own current_value pairs, everything else from the edited rule
    # — so this asserts ONLY when/required_facts changed.)
    if diff_keys != {"when", "required_facts"}:
        raise FoldPackError(
            f"E31C edit touched unexpected fields: {sorted(diff_keys)} — only "
            "when/required_facts may change"
        )

    # --- Insertion. Cross-check the cure file's declarative insertion
    # against the manifest-compiled body (Codex refuter finding 5: both
    # statements of the new rule must agree, or one has drifted) — compared
    # on every pack key except valid_period, which the fold normalizes.
    cure_insertions = cure["insertions"]
    if [e["rule_id"] for e in cure_insertions] != [_INSERTED_RULE_ID]:
        raise FoldPackError(
            f"cure-c2-e31c.json insertions = "
            f"{[e['rule_id'] for e in cure_insertions]!r}, expected "
            f"[{_INSERTED_RULE_ID!r}] — ledger drift"
        )
    inserted = copy.deepcopy(compiled[_INSERTED_RULE_ID])
    cure_ins = {k: v for k, v in cure_insertions[0].items() if not k.startswith("_")}
    for key in _RULE_KEY_ORDER:
        if key == "valid_period":
            continue
        if _canon(cure_ins.get(key)) != _canon(inserted.get(key)):
            raise FoldPackError(
                f"cure-c2-e31c.json insertion field {key!r} does not match the "
                "manifest-compiled rule — cure file and manifest drifted apart"
            )
    inserted["valid_period"]["from"] = _SEQ10_NEW_RULE_VALID_FROM
    if inserted["rule_id"] in rules_by_id:
        raise FoldPackError(f"rule {inserted['rule_id']!r} already exists — cannot insert")
    payload["rules"] = [*payload["rules"], inserted]


def cure_seq9_baseline(cure: dict[str, Any], key: str) -> Any:
    """The seq-9 value for ``key`` on the edited rule: for the two edited
    fields it is the cure file's own ``current_value`` (already
    drift-asserted against the real bytes); for every other key the edit
    never touches it, so the post-edit value IS the seq-9 value."""

    for edit in cure["rule_edits"]:
        if edit["field"] == key:
            return edit["current_value"]
    compiled_like = _load_json(_SEQ9_SOURCE)
    rule = next(r for r in compiled_like["rules"] if r["rule_id"] == _EDITED_RULE_ID)
    return rule.get(key)


# ---------------------------------------------------------------------------
# Byte-invariance sweep — everything not declared touched must match seq-9
# ---------------------------------------------------------------------------


#: Top-level payload keys this fold is ALLOWED to differ from seq-9 on.
#: Everything else must be byte-identical (Kimi refuter finding 5: the
#: original sweep covered only rules/products/source_records — hit_policy,
#: jurisdiction, engine_min/max_version etc. were unswept, so the
#: byte-identity claim held by accident, not by proof).
_IDENTITY_KEYS = frozenset(
    {"sequence", "version", "rule_pack_id", "previous_payload_sha256", "created_at", "created_by"}
)
_SWEPT_COLLECTIONS = frozenset({"rules", "products", "source_records"})


def _assert_untouched(payload: dict[str, Any], seq9: dict[str, Any]) -> None:
    for key in set(seq9) | set(payload):
        if key in _IDENTITY_KEYS or key in _SWEPT_COLLECTIONS:
            continue
        if _canon(payload.get(key)) != _canon(seq9.get(key)):
            raise FoldPackError(
                f"top-level payload key {key!r} drifted from seq-9 — this fold "
                "declares no edit there"
            )

    seq9_rules = {r["rule_id"]: r for r in seq9["rules"]}
    new_rules = {r["rule_id"]: r for r in payload["rules"]}
    touched_rules = {_RETIRED_RULE_ID, _EDITED_RULE_ID, _INSERTED_RULE_ID}

    for rid, rule in new_rules.items():
        if rid in touched_rules:
            continue
        if rid not in seq9_rules or _canon(rule) != _canon(seq9_rules[rid]):
            raise FoldPackError(f"rule {rid!r} drifted from seq-9 outside the declared edit set")
    missing = set(seq9_rules) - set(new_rules) - {_RETIRED_RULE_ID}
    if missing:
        raise FoldPackError(f"rule(s) vanished beyond the declared retirement: {sorted(missing)}")

    edits = _load_json(_RESTAMP_EDITS)
    restamped_ids = {e["source_record_id"] for e in edits["restamps"]}
    seq9_records = {r["source_record_id"]: r for r in seq9["source_records"]}
    new_records = {r["source_record_id"]: r for r in payload["source_records"]}
    for sid, record in new_records.items():
        if sid in restamped_ids:
            baseline = dict(seq9_records[sid])
            baseline.pop("verified_at"), baseline.pop("verified_by")
            candidate = dict(record)
            candidate.pop("verified_at"), candidate.pop("verified_by")
            if _canon(baseline) != _canon(candidate):
                raise FoldPackError(
                    f"source_record {sid!r} changed beyond verified_at/verified_by"
                )
        elif _canon(record) != _canon(seq9_records.get(sid)):
            raise FoldPackError(f"source_record {sid!r} drifted from seq-9 outside the re-stamp set")
    gone = set(seq9_records) - set(new_records)
    if gone != {_EE8FE5B8_ID}:
        raise FoldPackError(f"unexpected source_record removals: {sorted(gone)}")

    seq9_products = {p["product_code"]: p for p in seq9["products"]}
    for product in payload["products"]:
        code = product["product_code"]
        baseline = seq9_products[code]
        if code in _EE8FE5B8_PRODUCTS:
            b, c = dict(baseline), dict(product)
            b.pop("source_refs"), c.pop("source_refs")
            if _canon(b) != _canon(c):
                raise FoldPackError(f"product {code!r} changed beyond source_refs")
        elif _canon(product) != _canon(baseline):
            raise FoldPackError(f"product {code!r} drifted from seq-9")


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
    seq9_original = _load_json(_SEQ9_SOURCE)
    payload = copy.deepcopy(seq9_original)

    _apply_identity(payload, seq9_original)
    restamped = _apply_restamps(payload)
    _apply_ee8fe5b8_drop(payload)
    _apply_retirement(payload)
    compiled = _compile_inc4_rules()
    _apply_e31c_cure(payload, compiled)
    _assert_untouched(payload, seq9_original)

    try:
        RulePackPayload.model_validate(payload)
    except Exception as exc:  # re-raised loud with context
        raise FoldPackError(
            f"assembled seq-10 payload failed RulePackPayload validation: {exc}"
        ) from exc

    print(f"re-stamped {restamped} source_record(s)")
    return payload


def main(argv: list[str] | None = None) -> int:
    del argv  # no CLI flags — deterministic single-purpose script
    try:
        payload = assemble_payload()
    except FoldPackError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    _write_pack(payload, _SEQ10_SOURCE)
    print(
        f"wrote {_SEQ10_SOURCE} — {len(payload['rules'])} rule(s), "
        f"{len(payload['products'])} product(s), {len(payload['source_records'])} source_record(s)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
