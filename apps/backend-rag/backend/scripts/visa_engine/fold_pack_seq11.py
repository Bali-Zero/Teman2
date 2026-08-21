"""fold_pack_seq11.py — assemble RulePack seq-11 from seq-10 + a single,
minimal payload change: give products E30A and E30B a ``pricing_key``.

One concern, nothing else changes:

1. **Pricing-key assignment.** E30A ("Primary/Secondary Education Visa")
   and E30B ("Higher Education Visa") ship on seq-10 with
   ``pricing_key: null`` — the E30 family was authored (2026-07-24, W2)
   before the education-visa price list existed. This fold assigns the
   base 1-year variant to each, matching the house convention set by
   E28A → the base "Investor KITAS 2 Years (Offshore)" single key
   (no altus/onshore/extend tier split at the RulePack layer — that
   lives in the pricing catalog, not the product's ``pricing_key``):

   - E30A → ``{"category": "kitas_permits", "item_key": "E30A Education
     Visa (1 Year)"}``
   - E30B → ``{"category": "kitas_permits", "item_key": "E30B Higher
     Education (1 Year)"}``

   E30, E30E, E30F are deliberately left ``null`` — no per-product price
   has been authored for the SEZ / student-exchange / generic-E30
   variants yet (the "Data Belum Tersedia" honesty pin).

**PRICING-RESOLUTION GATE (deliberate blocker).** Both new item_keys are
asserted to resolve against a non-empty ``price`` row in
``backend/data/bali_zero_official_prices_2026.json`` BEFORE the payload is
mutated. As of this fold's authoring, PR #4383 (which adds the E30A/E30B
price-list entries) has not merged to main — running this module today
aborts loud on that gate. This is intentional: the fold becomes runnable
the moment #4383 lands, with no further code change.

Every input is read from disk at run time. The chain hash is read LIVE from
``rulepack-prod-010.signed.json`` and asserted against the expected anchor;
the seq-10 source bytes are additionally re-hashed (RFC 8785 JCS) and must
equal that same value — a source/signed mismatch aborts the fold.
Ledger-drift guards assert each touched product's CURRENT ``pricing_key`` is
``null`` before overwriting it. Deterministic: fixed timestamps, no
``datetime.now()`` — re-running is byte-identical.

Usage::

    PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq11
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
_SEQ10_SOURCE = _PACKS_DIR / "rulepack-prod-010.source.json"
_SEQ10_SIGNED = _PACKS_DIR / "rulepack-prod-010.signed.json"
_SEQ11_SOURCE = _PACKS_DIR / "rulepack-prod-011.source.json"

_PRICES_FILE = _BACKEND_ROOT / "data" / "bali_zero_official_prices_2026.json"

_PRETTIER_BIN = _REPO_ROOT / "node_modules" / ".bin" / "prettier"

# ---------------------------------------------------------------------------
# seq-11 identity (the uuid5 anchor is verified, never assumed)
# ---------------------------------------------------------------------------

_SEQ11_SEQUENCE = 11
_SEQ11_VERSION = "2026.8.20"
_SEQ11_RULE_PACK_ID_URL = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/11"
)
_EXPECTED_SEQ11_RULE_PACK_ID = uuid.UUID("5c3974ab-bb15-5a73-b74f-f9f0af88a4a7")

# The signed seq-10 payload hash this pack must chain to. Read LIVE from the
# signed file at run time AND asserted equal to this anchor AND equal to the
# recomputed canonical hash of the seq-10 SOURCE bytes — three independent
# derivations of one value, any mismatch aborts.
_EXPECTED_SEQ10_PAYLOAD_SHA256 = (
    "188442baee0af899e464a696b883d2158e6e362c29d75b61eec5769ba24b9aac"
)

# Fixed (not datetime.now()) so re-running this script is byte-identical.
_SEQ11_CREATED_AT = "2026-08-20T01:00:00Z"
_SEQ11_CREATED_BY = "agent.air-m5.backend-rag.visa-seq11-pricing.fold-2026-08-20"

# ---------------------------------------------------------------------------
# Phase constants — the two touched products and their new pricing_key.
# ---------------------------------------------------------------------------

_E30A_PRICING_KEY: dict[str, str] = {
    "category": "kitas_permits",
    "item_key": "E30A Education Visa (1 Year)",
}
_E30B_PRICING_KEY: dict[str, str] = {
    "category": "kitas_permits",
    "item_key": "E30B Higher Education (1 Year)",
}
_NEW_PRICING_KEYS: dict[str, dict[str, str]] = {
    "E30A": _E30A_PRICING_KEY,
    "E30B": _E30B_PRICING_KEY,
}
_TOUCHED_PRODUCT_CODES = ("E30A", "E30B")

# Cross-check on the fold's own assumption about seq-10's baseline split —
# if this drifts, the seq-10 bytes (or the touched-product set) changed
# under this fold without the fold being updated to match.
_EXPECTED_NON_NULL_PRICING_KEYS_AFTER = 26
_EXPECTED_NULL_PRICING_KEYS_AFTER = 12


class FoldPackError(RuntimeError):
    """A fail-loud gate inside the fold tripped — never silently degrade."""


class PricingResolutionError(FoldPackError):
    """A newly-assigned pricing_key does not resolve to a priced catalog
    row. DELIBERATE until the price-list PR (#4383) lands on main — this
    is the gate that makes the fold unrunnable until then."""


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Identity + chain
# ---------------------------------------------------------------------------


def _verify_rule_pack_id() -> uuid.UUID:
    computed = uuid.uuid5(uuid.NAMESPACE_URL, _SEQ11_RULE_PACK_ID_URL)
    if computed != _EXPECTED_SEQ11_RULE_PACK_ID:
        raise FoldPackError(
            f"seq-11 rule_pack_id convention drifted: uuid5(NAMESPACE_URL, "
            f"{_SEQ11_RULE_PACK_ID_URL!r}) = {computed}, expected "
            f"{_EXPECTED_SEQ11_RULE_PACK_ID} — do not hand-adjust either side"
        )
    return computed


def _chain_hash(seq10_source: dict[str, Any]) -> str:
    signed = _load_json(_SEQ10_SIGNED)
    declared = signed.get("payload_sha256")
    if declared != _EXPECTED_SEQ10_PAYLOAD_SHA256:
        raise FoldPackError(
            f"{_SEQ10_SIGNED} declares payload_sha256={declared!r}, expected "
            f"{_EXPECTED_SEQ10_PAYLOAD_SHA256!r} — the signed seq-10 on disk is "
            "not the one this fold was authored against"
        )
    recomputed = hashlib.sha256(canonicalize_json(seq10_source)).hexdigest()
    if recomputed != declared:
        raise FoldPackError(
            f"seq-10 SOURCE bytes re-hash to {recomputed}, but the signed file "
            f"declares {declared} — source/signed mismatch, refusing to chain"
        )
    return declared


def _apply_identity(payload: dict[str, Any], seq10_source: dict[str, Any]) -> None:
    payload["sequence"] = _SEQ11_SEQUENCE
    payload["version"] = _SEQ11_VERSION
    payload["rule_pack_id"] = str(_verify_rule_pack_id())
    payload["previous_payload_sha256"] = _chain_hash(seq10_source)
    payload["created_at"] = _SEQ11_CREATED_AT
    payload["created_by"] = _SEQ11_CREATED_BY
    # rollback_of_payload_sha256 stays null; top-level valid_period untouched
    # (seq-10's fold precedent: it is not in _IDENTITY_KEYS, so the
    # byte-invariance sweep below asserts it equals seq-10's).


# ---------------------------------------------------------------------------
# Pricing-resolution gate — deliberate blocker until PR #4383 lands
# ---------------------------------------------------------------------------


def _assert_price_resolves(
    prices_payload: Any, pricing_key: dict[str, str], *, product_code: str
) -> None:
    services = prices_payload.get("services") if isinstance(prices_payload, dict) else None
    if not isinstance(services, dict):
        raise PricingResolutionError(
            f"{_PRICES_FILE} has no top-level 'services' object — cannot resolve "
            f"{product_code}'s pricing_key {pricing_key!r}"
        )
    category = services.get(pricing_key["category"])
    if not isinstance(category, dict):
        raise PricingResolutionError(
            f"{product_code}: pricing category {pricing_key['category']!r} does not "
            f"exist in {_PRICES_FILE.name} — PR #4383 (E30A/E30B price-list entries) "
            "has not landed on main yet"
        )
    entry = category.get(pricing_key["item_key"])
    if not isinstance(entry, dict):
        raise PricingResolutionError(
            f"{product_code}: pricing item_key {pricing_key['item_key']!r} not found "
            f"under category {pricing_key['category']!r} in {_PRICES_FILE.name} — "
            "PR #4383 (E30A/E30B price-list entries) has not landed on main yet"
        )
    price = entry.get("price")
    if not isinstance(price, str) or not price.strip():
        raise PricingResolutionError(
            f"{product_code}: pricing row {pricing_key['item_key']!r} exists under "
            f"{pricing_key['category']!r} but has no non-empty 'price' — PR #4383 has "
            "not fully landed"
        )


def _pricing_resolution_gate() -> None:
    if not _PRICES_FILE.exists():
        raise PricingResolutionError(f"pricing catalog not found at {_PRICES_FILE}")
    prices_payload = _load_json(_PRICES_FILE)
    for code, key in _NEW_PRICING_KEYS.items():
        _assert_price_resolves(prices_payload, key, product_code=code)


# ---------------------------------------------------------------------------
# Payload edit — E30A/E30B pricing_key: null -> {category, item_key}
# ---------------------------------------------------------------------------


def _apply_pricing_keys(payload: dict[str, Any]) -> None:
    products_by_code = {p["product_code"]: p for p in payload["products"]}
    for code in _TOUCHED_PRODUCT_CODES:
        product = products_by_code.get(code)
        if product is None:
            raise FoldPackError(f"product {code!r} not found — cannot set pricing_key")
        current = product.get("pricing_key")
        if current is not None:
            raise FoldPackError(
                f"product {code!r} pricing_key is {current!r} on seq-10, expected "
                "null — ledger drift, refusing to overwrite blind"
            )
        product["pricing_key"] = copy.deepcopy(_NEW_PRICING_KEYS[code])

    non_null = sum(1 for p in payload["products"] if p.get("pricing_key") is not None)
    null = len(payload["products"]) - non_null
    if (
        non_null != _EXPECTED_NON_NULL_PRICING_KEYS_AFTER
        or null != _EXPECTED_NULL_PRICING_KEYS_AFTER
    ):
        raise FoldPackError(
            f"post-fold pricing_key split is {non_null} non-null / {null} null, "
            f"expected {_EXPECTED_NON_NULL_PRICING_KEYS_AFTER} non-null / "
            f"{_EXPECTED_NULL_PRICING_KEYS_AFTER} null — the seq-10 bytes or the "
            "touched-product set drifted from what this fold was authored against"
        )


# ---------------------------------------------------------------------------
# Byte-invariance sweep — everything not declared touched must match seq-10
# ---------------------------------------------------------------------------

#: Top-level payload keys this fold is ALLOWED to differ from seq-10 on.
_IDENTITY_KEYS = frozenset(
    {"sequence", "version", "rule_pack_id", "previous_payload_sha256", "created_at", "created_by"}
)


def _assert_untouched(payload: dict[str, Any], seq10: dict[str, Any]) -> None:
    for key in set(seq10) | set(payload):
        if key in _IDENTITY_KEYS or key == "products":
            continue
        if _canon(payload.get(key)) != _canon(seq10.get(key)):
            raise FoldPackError(
                f"top-level payload key {key!r} drifted from seq-10 — this fold "
                "declares no edit there"
            )

    # rules and source_records: this fold declares ZERO edits anywhere in
    # either collection — whole-collection canonical equality, not a
    # per-item sweep with a carve-out (there is no carve-out to make).
    if _canon(payload["rules"]) != _canon(seq10["rules"]):
        raise FoldPackError("rules drifted from seq-10 — this fold declares no rule edits")
    if _canon(payload["source_records"]) != _canon(seq10["source_records"]):
        raise FoldPackError(
            "source_records drifted from seq-10 — this fold declares no source_record edits"
        )

    seq10_products = {p["product_code"]: p for p in seq10["products"]}
    new_products = {p["product_code"]: p for p in payload["products"]}
    if set(new_products) != set(seq10_products):
        raise FoldPackError(
            "product set (by product_code) drifted from seq-10 — this fold declares "
            "no product add/remove"
        )
    for code, product in new_products.items():
        baseline = seq10_products[code]
        if code in _TOUCHED_PRODUCT_CODES:
            b, c = dict(baseline), dict(product)
            b.pop("pricing_key"), c.pop("pricing_key")
            if _canon(b) != _canon(c):
                raise FoldPackError(f"product {code!r} changed beyond pricing_key")
        elif _canon(product) != _canon(baseline):
            raise FoldPackError(
                f"product {code!r} drifted from seq-10 outside the declared "
                "pricing_key edit set"
            )


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
    seq10_original = _load_json(_SEQ10_SOURCE)
    payload = copy.deepcopy(seq10_original)

    _apply_identity(payload, seq10_original)
    # The pricing gate is a pure read against the catalog file — it does not
    # depend on payload state, so it runs before any mutation: fail fastest,
    # fail loudest, and never leave the payload half-edited on a gate abort.
    _pricing_resolution_gate()
    _apply_pricing_keys(payload)
    _assert_untouched(payload, seq10_original)

    try:
        RulePackPayload.model_validate(payload)
    except Exception as exc:  # re-raised loud with context
        raise FoldPackError(
            f"assembled seq-11 payload failed RulePackPayload validation: {exc}"
        ) from exc

    return payload


def main(argv: list[str] | None = None) -> int:
    del argv  # no CLI flags — deterministic single-purpose script
    try:
        payload = assemble_payload()
    except FoldPackError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    _write_pack(payload, _SEQ11_SOURCE)
    print(
        f"wrote {_SEQ11_SOURCE} — {len(payload['rules'])} rule(s), "
        f"{len(payload['products'])} product(s), {len(payload['source_records'])} source_record(s)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
