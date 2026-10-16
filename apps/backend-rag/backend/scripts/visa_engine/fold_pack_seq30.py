"""Fold seq-30: content fold chained on verified signed seq-29 (PENDING-ARMS.md row E).

Chained on the signed seq-29 anchor (payload
``3f3b45ed1aaeadc72ec9dd2a5e33519ded3a0ec1da8408fade150a0ae39b9295``).
Because seq-29 re-stamped all 18 official Imigrasi portal ``source_records`` at
``2026-10-13T00:07:47Z`` (freshness boundary ``2026-11-14T00:07:47Z``), seq-30
is a mid-week content fold (same pattern as seq-26): all 28 ``source_records``
stay byte-identical to signed seq-29 and six source-backed items land:

1. ``SEQ29-A2`` — ``el.e28a.investment``:
   Drop ``{"op": "in", "fact": "investment.proposed_role", "values": ["SHAREHOLDER_DIRECTOR",
   "SHAREHOLDER_COMMISSIONER"]}`` from ``when.args`` and ``"investment.proposed_role"`` from
   ``required_facts``. Saved page ``df3ba889-e28a.txt`` states only the IDR 10,000,000,000
   shareholding and PT PMA capital floor for E28A; passive shareholders
   (``NO_OPERATIONAL_ROLE`` / ``EMPLOYEE``) meeting the IDR 2.5bn paid-up and IDR 10bn
   investment floor are admitted.
2. ``SEQ29-D1`` — ``el.e28d.branch-or-subsidiary`` and ``el.e28f.ikn-subsidiary``:
   Add ``{"op": "in", "fact": "investment.proposed_role", "values": ["SHAREHOLDER_DIRECTOR",
   "SHAREHOLDER_COMMISSIONER"]}`` to ``when.args`` and ``"investment.proposed_role"`` to
   ``required_facts`` (``on_unknown: "NEEDS_INPUT"``), backed by saved official pages
   ``dd5e2a06-e28d.txt`` and ``74e25e50-e28f.txt`` ("akan menjabat sebagai anggota direksi
   atau anggota dewan komisaris").
3. ``S02`` — ``hf.a1.onshore-conversion-excluded``:
   Insert a ``HARD_FILTER`` ``EXCLUDE`` rule on ``A1``
   (``aee1a12d-3285-526e-8a6f-3d8467fe5d72``) when
   ``process.wants_onshore_conversion == True`` with reason code ``A1_NOT_CONVERTIBLE`` and
   ``on_unknown: "NO_EFFECT"``, backed by ``808d691c-374e-5581-8186-9eb54d0ca7ab`` (PP 48/2021)
   and ``dcf08e19-fbc3-5f96-93fa-0325b1ffe91d`` (Imigrasi Alih Status portal).
4. ``SEQ29-E30-02`` — ``E30A`` and ``E30B`` ``duration_options``:
   Populate ``E30A`` ``duration_options`` (365d -> 9.000.000 IDR, 730d -> 11.500.000 IDR) and
   ``E30B`` ``duration_options`` (365d -> 9.000.000 IDR, 730d -> 11.500.000 IDR, 1460d ->
   15.000.000 IDR) from ``bali_zero_official_prices_2026.json``.
5. ``SEQ29-S1`` — ``E28B``, ``E28D``, and ``E28F`` ``sponsor_types``:
   Flip ``sponsor_types`` from ``["INVESTMENT"]`` to ``["NONE"]``, backed by saved official
   pages ``4ba3c1a3-e28b.txt``, ``dd5e2a06-e28d.txt``, and ``74e25e50-e28f.txt`` ("Anda tidak
   membutuhkan penjamin/sponsor untuk mengajukan visa ini.").
6. ``SEQ29-N1`` — ``E28C``, ``E28D``, and ``E28F`` ``names``:
   Align product names to the saved official Imigrasi headings:
   * ``E28C.names.id`` -> ``"Visa Investor Pasar Modal (E28C)"``
   * ``E28D.names.id`` -> ``"Visa Investor Pendirian Cabang atau Anak Perusahaan (E28D)"``
   * ``E28F.names.id`` -> ``"Visa Investor Pendirian Cabang atau Anak Perusahaan di Ibu Kota Nusantara (E28F)"``
   * ``E28F.names.en`` -> ``"Investor Golden Visa — Branch or Subsidiary in the New Capital (IKN) (E28F)"``
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

from backend.scripts.visa_engine import fold_pack_seq28 as seq28
from backend.scripts.visa_engine import fold_pack_seq29 as seq29
from backend.scripts.visa_engine.compile_pack import compile_pack_source
from backend.scripts.visa_engine.fold_pack_seq24 import (
    assert_no_hard_filter_reads_a_synthesised_twin_basis_fact,
)
from backend.scripts.visa_engine.portal_read_receipt import fingerprint
from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    canonicalize_json,
    verify_rule_pack,
)
from backend.services.visa_engine.errors import RulePackVerificationError
from backend.services.visa_engine.models import RulePackPayload, VisaProductVersion

SEQ29_SEQUENCE = 29
SEQ29_PAYLOAD_SHA256 = (
    "3f3b45ed1aaeadc72ec9dd2a5e33519ded3a0ec1da8408fade150a0ae39b9295"  # pragma: allowlist secret
)
SEQ30_SEQUENCE = 30
FOLD_VERSION = "2026.10.16"
FOLD_CREATED_AT = "2026-10-16T12:00:00Z"
FOLD_CREATED_BY = "agent.air-m5.backend-rag.vo-seq30-e28-1016"
NEW_RULE_VALID_FROM = "2026-10-16T00:00:00Z"

A1_PRODUCT_VERSION_ID = "aee1a12d-3285-526e-8a6f-3d8467fe5d72"
E28A_PRODUCT_VERSION_ID = "c8277316-c29d-5fde-bf9f-2611099a0029"
E28B_PRODUCT_VERSION_ID = "ca8c1177-ad94-5261-82a6-68bc912d31bb"
E28C_PRODUCT_VERSION_ID = "b074270f-fa7c-598b-a728-81ca89432364"
E28D_PRODUCT_VERSION_ID = "ee4fef98-3497-507c-8486-225932364e26"
E28E_PRODUCT_VERSION_ID = "46cd2ff9-7cd0-5b8d-8e56-f1b90ab9f760"
E28F_PRODUCT_VERSION_ID = "2df6f723-7fc3-585a-b26f-0e8c060a2d8d"
E30A_PRODUCT_VERSION_ID = "5028908f-25be-5ef1-91b9-0d6bccfc0e1f"
E30B_PRODUCT_VERSION_ID = "904d99ec-d198-5eb8-9dc4-0b2047e49137"

SRC_BVK_REGULATION = "808d691c-374e-5581-8186-9eb54d0ca7ab"
SRC_ALIH_STATUS_PORTAL = "dcf08e19-fbc3-5f96-93fa-0325b1ffe91d"

A1_RULE_ID = "hf.a1.onshore-conversion-excluded"
A1_NOT_CONVERTIBLE_REASON_CODE = "A1_NOT_CONVERTIBLE"
E28A_RULE_ID = "el.e28a.investment"
E28D_RULE_ID = "el.e28d.branch-or-subsidiary"
E28F_RULE_ID = "el.e28f.ikn-subsidiary"

DIRECTOR_OR_COMMISSIONER_ROLES = ["SHAREHOLDER_DIRECTOR", "SHAREHOLDER_COMMISSIONER"]
PROPOSED_ROLE_PREDICATE: dict[str, Any] = {
    "op": "in",
    "fact": "investment.proposed_role",
    "values": DIRECTOR_OR_COMMISSIONER_ROLES,
}

MODIFIED_RULE_IDS = frozenset({E28A_RULE_ID, E28D_RULE_ID, E28F_RULE_ID})
INSERTED_RULE_IDS_IN_ORDER = (A1_RULE_ID,)
INSERTED_RULE_IDS = frozenset(INSERTED_RULE_IDS_IN_ORDER)
RETIRED_RULE_IDS: frozenset[str] = frozenset()

# product_version_id -> ((days, catalogue item_key, price, validity), ...)
E30_OPTIONS: dict[str, tuple[tuple[int, str, str, str], ...]] = {
    E30A_PRODUCT_VERSION_ID: (
        (365, "E30A Education Visa (1 Year)", "9.000.000 IDR", "1 year"),
        (730, "E30A Education Visa (2 Years)", "11.500.000 IDR", "2 years"),
    ),
    E30B_PRODUCT_VERSION_ID: (
        (365, "E30B Higher Education (1 Year)", "9.000.000 IDR", "1 year"),
        (730, "E30B Higher Education (2 Years)", "11.500.000 IDR", "2 years"),
        (1460, "E30B Higher Education (4 Years)", "15.000.000 IDR", "4 years"),
    ),
}

# SEQ29-S1: E28B, E28D, E28F sponsor_types ["INVESTMENT"] -> ["NONE"].
E28_NO_SPONSOR_PRODUCT_IDS = frozenset(
    {
        E28B_PRODUCT_VERSION_ID,
        E28D_PRODUCT_VERSION_ID,
        E28F_PRODUCT_VERSION_ID,
    }
)

# SEQ29-N1: E28C, E28D, E28F official headings in names.
E28_NAME_UPDATES: dict[str, dict[str, dict[str, str]]] = {
    E28C_PRODUCT_VERSION_ID: {
        "before": {
            "en": "Investor Golden Visa \u2014 Capital Market (E28C)",
            "id": "Visa Investor Tanpa Mendirikan Perusahaan (E28C)",
        },
        "after": {
            "en": "Investor Golden Visa \u2014 Capital Market (E28C)",
            "id": "Visa Investor Pasar Modal (E28C)",
        },
    },
    E28D_PRODUCT_VERSION_ID: {
        "before": {
            "en": "Investor Golden Visa \u2014 Branch or Subsidiary (E28D)",
            "id": "Visa Investor Pendirian Kantor Cabang atau Anak Perusahaan (E28D)",
        },
        "after": {
            "en": "Investor Golden Visa \u2014 Branch or Subsidiary (E28D)",
            "id": "Visa Investor Pendirian Cabang atau Anak Perusahaan (E28D)",
        },
    },
    E28F_PRODUCT_VERSION_ID: {
        "before": {
            "en": "Investor Golden Visa \u2014 New Capital (IKN) Subsidiary (E28F)",
            "id": "Visa Investor Anak Perusahaan Ibukota Nusantara (E28F)",
        },
        "after": {
            "en": "Investor Golden Visa \u2014 Branch or Subsidiary in the New Capital (IKN) (E28F)",
            "id": "Visa Investor Pendirian Cabang atau Anak Perusahaan di Ibu Kota Nusantara (E28F)",
        },
    },
}

MODIFIED_PRODUCT_IDS = (
    frozenset(E30_OPTIONS) | E28_NO_SPONSOR_PRODUCT_IDS | frozenset(E28_NAME_UPDATES)
)

_IDENTITY_KEYS = seq28._IDENTITY_KEYS
_REPO_ROOT = seq28._REPO_ROOT
_PACKS = seq28._PACKS
_RESEARCH = seq28._RESEARCH
_CATALOGUE = seq28._CATALOGUE
E28_PAGES_DIR = _RESEARCH / "2026-10-15-e28-pages"
_canon = seq28._canon
_rules_by_id = seq28._rules_by_id
_products_by_id = seq28._products_by_id
_fact_paths = seq28._fact_paths
_without_identity = seq28._without_identity

SAVED_E28_PAGE_SPECS: dict[str, dict[str, str]] = {
    "E28A": {
        "canonical_url": "https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E28A",
        "file": "text/df3ba889-20261015T142247Z.txt",
        "visible_text_sha256": "a596fc358d5f38ff4a630107bca6a561d113843364e2b2676a2b494f9cd52a55",  # pragma: allowlist secret
        "heading_line": "E28A Visa Investor",
        "sponsor_line": "Anda membutuhkan penjamin/sponsor untuk mengajukan visa ini.",
        "role_line": (
            "Bukti kepemilikan saham paling sedikit Rp10.000.000.000,00 (sepuluh miliar rupiah) "
            "atau setara pada perusahaan penjamin yang terdaftar di Kementerian Investasi/"
            "Badan Koordinasi Penanaman Modal."
        ),
    },
    "E28B": {
        "canonical_url": "https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E28B",
        "file": "text/4ba3c1a3-20261015T142247Z.txt",
        "visible_text_sha256": "3e749492599c6967a8ecd62d1375c6aaea3d2bc89d92ea48f19363772eca3d30",  # pragma: allowlist secret
        "heading_line": "E28B Visa Investor Pendirian Perusahaan",
        "sponsor_line": "Anda tidak membutuhkan penjamin/sponsor untuk mengajukan visa ini",
    },
    "E28C": {
        "canonical_url": "https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E28C",
        "file": "text/2cdb5b81-20261015T142248Z.txt",
        "visible_text_sha256": "0910b79e00cf5f1c063e6e82582b50a14bf765744d4068050b300b62d5e5f847",  # pragma: allowlist secret
        "heading_line": "E28C Visa Investor Pasar Modal",
        "sponsor_line": "Anda tidak membutuhkan penjamin/sponsor untuk mengajukan visa ini",
    },
    "E28D": {
        "canonical_url": "https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E28D",
        "file": "text/dd5e2a06-20261015T142249Z.txt",
        "visible_text_sha256": "e29d040a6f7edcf43635606066080ee23d96595b9c22da1557331bcfdd6f0f8c",  # pragma: allowlist secret
        "heading_line": "E28D Visa Investor Pendirian Cabang atau Anak Perusahaan",
        "sponsor_line": "Anda tidak membutuhkan penjamin/sponsor untuk mengajukan visa ini",
        "role_line": (
            "Visa ini diperuntukkan bagi orang asing yang akan menjabat sebagai anggota direksi "
            "atau anggota dewan komisaris pada perusahaan yang akan didirikan di Indonesia, "
            "yang merupakan cabang atau anak perusahaan dari perusahaan di luar wilayah Indonesia"
        ),
    },
    "E28E": {
        "canonical_url": "https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E28E",
        "file": "text/5b9dd676-20261015T142249Z.txt",
        "visible_text_sha256": "e85ad3928a1c08c364e3acec629eb955c198f62af6f5f5eda44b3e4a3d71fccd",  # pragma: allowlist secret
        "heading_line": "E28E Visa Investor Kawasan Ekonomi Khusus",
        "sponsor_line": "Data Belum Tersedia",
    },
    "E28F": {
        "canonical_url": "https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E28F",
        "file": "text/74e25e50-20261015T142250Z.txt",
        "visible_text_sha256": "989cd366dabba0893d70bab648367fb0ccd1a2f4fb015f80bc7dda3eaa1a00f5",  # pragma: allowlist secret
        "heading_line": (
            "E28F Visa Investor Pendirian Cabang atau Anak Perusahaan di Ibu Kota Nusantara"
        ),
        "sponsor_line": "Anda tidak membutuhkan penjamin/sponsor untuk mengajukan visa ini",
        "role_line": (
            "Visa ini diperuntukkan bagi orang asing yang akan menjabat sebagai anggota direksi "
            "atau anggota dewan komisaris pada perusahaan yang akan didirikan di Ibu Kota Nusantara, "
            "yang merupakan cabang atau anak perusahaan dari perusahaan di luar wilayah Indonesia"
        ),
    },
}


def _fail(message: str) -> NoReturn:
    raise SystemExit(f"fold_pack_seq30: {message}")


def verify_saved_e28_pages(pages_dir: Path = E28_PAGES_DIR) -> None:
    """Verify the six saved official Imigrasi E28 page snapshots and receipts on disk."""

    receipts_path = pages_dir / "e28-pages.receipts.jsonl"
    if not receipts_path.exists():
        _fail(f"missing E28 receipts file: {receipts_path}")

    receipts_by_url: dict[str, dict[str, Any]] = {}
    for raw_line in receipts_path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        row = json.loads(raw_line)
        receipts_by_url[row["canonical_url"]] = row

    for code, spec in SAVED_E28_PAGE_SPECS.items():
        receipt = receipts_by_url.get(spec["canonical_url"])
        if receipt is None:
            _fail(f"missing receipt for {code} ({spec['canonical_url']})")
        if receipt.get("http_status") != 200 or receipt.get("key_phrase_found") is not True:
            _fail(f"receipt for {code} is not a verified 200 read: {receipt}")
        if receipt.get("visible_text_sha256") != spec["visible_text_sha256"]:
            _fail(
                f"receipt sha256 mismatch for {code}: "
                f"{receipt.get('visible_text_sha256')} != {spec['visible_text_sha256']}"
            )
        text_path = pages_dir / spec["file"]
        if not text_path.exists():
            _fail(f"missing saved page text for {code}: {text_path}")
        page_text = text_path.read_text(encoding="utf-8")
        computed_sha = fingerprint(page_text.rstrip("\n"))
        if computed_sha != spec["visible_text_sha256"]:
            _fail(
                f"saved text sha256 mismatch for {code}: "
                f"{computed_sha} != {spec['visible_text_sha256']}"
            )
        for required_key in ("heading_line", "sponsor_line", "role_line"):
            expected_phrase = spec.get(required_key)
            if expected_phrase and expected_phrase not in page_text:
                _fail(
                    f"saved page {code} ({text_path.name}) does not contain expected "
                    f"{required_key}: {expected_phrase!r}"
                )


def assert_catalogue_preconditions(catalogue: dict[str, Any]) -> None:
    """Every E30 option must already be a priced catalogue row; nothing is invented."""

    rows = seq28._catalogue_rows(catalogue)
    for options in E30_OPTIONS.values():
        for _days, item_key, price, validity in options:
            row = rows.get(item_key)
            if not isinstance(row, dict):
                _fail(f"pricing row {item_key!r} does not exist")
            if row.get("price") != price or row.get("validity") != validity:
                _fail(
                    f"pricing row {item_key!r} is not {price} / {validity}: "
                    f"{row.get('price')!r} / {row.get('validity')!r}"
                )


def build_e30_product(product: dict[str, Any]) -> dict[str, Any]:
    """SEQ29-E30-02: populate E30A (1y/2y) and E30B (1y/2y/4y) duration_options."""

    product_id = str(product.get("product_version_id"))
    options = E30_OPTIONS.get(product_id)
    if options is None:
        _fail(f"{product_id!r} is not E30A or E30B")
    if product.get("duration_options"):
        _fail(f"{product.get('product_code')} already carries duration_options")
    first_key = {"category": "kitas_permits", "item_key": options[0][1]}
    if product.get("pricing_key") != first_key:
        _fail(f"{product.get('product_code')} pricing_key is not its one-year row")
    stay = product.get("stay_policy") or {}
    if stay.get("kind") != "FIXED_DAYS" or stay.get("maximum_days") != options[-1][0]:
        _fail(f"{product.get('product_code')} stay_policy does not end at {options[-1][0]} days")
    out = copy.deepcopy(product)
    out["duration_options"] = [
        {"days": days, "pricing_key": {"category": "kitas_permits", "item_key": item_key}}
        for days, item_key, _price, _validity in options
    ]
    VisaProductVersion.model_validate(out)
    return out


def build_e28_product(product: dict[str, Any]) -> dict[str, Any]:
    """SEQ29-S1 and SEQ29-N1: update E28B/E28C/E28D/E28F sponsor_types and names."""

    product_id = str(product.get("product_version_id"))
    if product_id not in (E28_NO_SPONSOR_PRODUCT_IDS | frozenset(E28_NAME_UPDATES)):
        _fail(f"{product_id!r} is not one of E28B, E28C, E28D, E28F")

    out = copy.deepcopy(product)
    if product_id in E28_NO_SPONSOR_PRODUCT_IDS:
        if out.get("sponsor_types") != ["INVESTMENT"]:
            _fail(
                f"{out.get('product_code')} sponsor_types is {out.get('sponsor_types')!r}, "
                "expected ['INVESTMENT']"
            )
        out["sponsor_types"] = ["NONE"]

    if product_id in E28_NAME_UPDATES:
        spec = E28_NAME_UPDATES[product_id]
        if out.get("names") != spec["before"]:
            _fail(
                f"{out.get('product_code')} names is {out.get('names')!r}, "
                f"expected {spec['before']!r}"
            )
        out["names"] = copy.deepcopy(spec["after"])

    VisaProductVersion.model_validate(out)
    return out


def build_e28a_rule(rule: dict[str, Any]) -> dict[str, Any]:
    """SEQ29-A2: drop investment.proposed_role from el.e28a.investment."""

    if rule.get("rule_id") != E28A_RULE_ID:
        _fail(f"expected {E28A_RULE_ID!r}, got {rule.get('rule_id')!r}")
    expected_when = {
        "op": "all",
        "args": [
            {"op": "intersects", "fact": "intent.purposes", "values": ["INVESTMENT"]},
            {"op": "eq", "fact": "investment.pt_pma_committed", "value": True},
            PROPOSED_ROLE_PREDICATE,
            {"op": "gte", "fact": "investment.paid_up_capital_idr", "value": 2500000000},
            {"op": "gte", "fact": "investment.investment_capital_idr", "value": 10000000000},
        ],
    }
    if rule.get("when") != expected_when:
        _fail(f"{E28A_RULE_ID!r} no longer has the seq-29 five-argument shape")
    if rule.get("on_unknown") != "NEEDS_INPUT":
        _fail(f"{E28A_RULE_ID!r} on_unknown is not NEEDS_INPUT")

    out = copy.deepcopy(rule)
    out["when"] = {
        "op": "all",
        "args": [
            {"op": "intersects", "fact": "intent.purposes", "values": ["INVESTMENT"]},
            {"op": "eq", "fact": "investment.pt_pma_committed", "value": True},
            {"op": "gte", "fact": "investment.paid_up_capital_idr", "value": 2500000000},
            {"op": "gte", "fact": "investment.investment_capital_idr", "value": 10000000000},
        ],
    }
    out["required_facts"] = _fact_paths(out["when"])
    return out


def build_e28d_rule(rule: dict[str, Any]) -> dict[str, Any]:
    """SEQ29-D1: add investment.proposed_role director/commissioner gate to E28D."""

    if rule.get("rule_id") != E28D_RULE_ID:
        _fail(f"expected {E28D_RULE_ID!r}, got {rule.get('rule_id')!r}")
    expected_when = {
        "op": "all",
        "args": [
            {"op": "intersects", "fact": "intent.purposes", "values": ["INVESTMENT"]},
            {"op": "eq", "fact": "investment.foreign_branch_or_subsidiary", "value": True},
            {"op": "eq", "fact": "investment.meets_published_threshold", "value": True},
        ],
    }
    if rule.get("when") != expected_when:
        _fail(f"{E28D_RULE_ID!r} no longer has the seq-29 three-argument shape")
    if rule.get("on_unknown") != "NEEDS_INPUT":
        _fail(f"{E28D_RULE_ID!r} on_unknown is not NEEDS_INPUT")

    out = copy.deepcopy(rule)
    out["when"]["args"].append(copy.deepcopy(PROPOSED_ROLE_PREDICATE))
    out["required_facts"] = _fact_paths(out["when"])
    return out


def build_e28f_rule(rule: dict[str, Any]) -> dict[str, Any]:
    """SEQ29-D1: add investment.proposed_role director/commissioner gate to E28F."""

    if rule.get("rule_id") != E28F_RULE_ID:
        _fail(f"expected {E28F_RULE_ID!r}, got {rule.get('rule_id')!r}")
    expected_when = {
        "op": "all",
        "args": [
            {"op": "intersects", "fact": "intent.purposes", "values": ["INVESTMENT"]},
            {"op": "eq", "fact": "investment.ikn_subsidiary", "value": True},
            {"op": "eq", "fact": "investment.meets_published_threshold", "value": True},
            {"op": "eq", "fact": "investment.foreign_branch_or_subsidiary", "value": True},
        ],
    }
    if rule.get("when") != expected_when:
        _fail(f"{E28F_RULE_ID!r} no longer has the seq-29 four-argument shape")
    if rule.get("on_unknown") != "NEEDS_INPUT":
        _fail(f"{E28F_RULE_ID!r} on_unknown is not NEEDS_INPUT")

    out = copy.deepcopy(rule)
    out["when"]["args"].append(copy.deepcopy(PROPOSED_ROLE_PREDICATE))
    out["required_facts"] = _fact_paths(out["when"])
    return out


def build_a1_rule() -> dict[str, Any]:
    """S02: A1 Visa-Free Tourism Visit cannot be converted onshore into another permit."""

    when = {"op": "eq", "fact": "process.wants_onshore_conversion", "value": True}
    return {
        "rule_id": A1_RULE_ID,
        "stage": "HARD_FILTER",
        "scope": "PRODUCTS",
        "product_version_ids": [A1_PRODUCT_VERSION_ID],
        "when": when,
        "effect": {"type": "EXCLUDE", "reason_code": A1_NOT_CONVERTIBLE_REASON_CODE},
        "on_unknown": "NO_EFFECT",
        "priority": 100,
        "required_facts": _fact_paths(when),
        "source_refs": [SRC_BVK_REGULATION, SRC_ALIH_STATUS_PORTAL],
        "valid_period": {"from": NEW_RULE_VALID_FROM, "to": None},
        "explanation_key": f"explain.{A1_RULE_ID}",
        "safety_critical": True,
    }


_MODIFIED_RULE_BUILDERS = {
    E28A_RULE_ID: build_e28a_rule,
    E28D_RULE_ID: build_e28d_rule,
    E28F_RULE_ID: build_e28f_rule,
}

_INSERTED_RULE_BUILDERS = {
    A1_RULE_ID: build_a1_rule,
}

_MODIFIED_PRODUCT_BUILDERS = {
    E30A_PRODUCT_VERSION_ID: build_e30_product,
    E30B_PRODUCT_VERSION_ID: build_e30_product,
    E28B_PRODUCT_VERSION_ID: build_e28_product,
    E28C_PRODUCT_VERSION_ID: build_e28_product,
    E28D_PRODUCT_VERSION_ID: build_e28_product,
    E28F_PRODUCT_VERSION_ID: build_e28_product,
}


def _assert_required_facts(rule: dict[str, Any]) -> None:
    expected = _fact_paths(rule["when"])
    if rule.get("required_facts") != expected:
        _fail(
            f"{rule['rule_id']}: required_facts {rule.get('required_facts')!r} "
            f"!= condition facts {expected!r}"
        )


def assert_only_expected_changes(restamped: dict[str, Any], out: dict[str, Any]) -> None:
    """The seq-29 base may differ from seq-30 in exactly the 6 scheduled products and 4 rules."""

    if set(restamped) != set(out):
        _fail("top-level key set changed")
    for key in set(restamped) - _IDENTITY_KEYS - {"products", "rules"}:
        if _canon(restamped[key]) != _canon(out[key]):
            _fail(f"{key} changed; source_records and all other content must be byte-identical")

    before_products = _products_by_id(restamped)
    after_products = _products_by_id(out)
    if [p["product_version_id"] for p in restamped["products"]] != [
        p["product_version_id"] for p in out["products"]
    ]:
        _fail("product order or membership changed")

    for pid, before in before_products.items():
        after = after_products[pid]
        if pid in MODIFIED_PRODUCT_IDS:
            expected_after = _MODIFIED_PRODUCT_BUILDERS[pid](before)
            if _canon(after) != _canon(expected_after):
                _fail(f"product {pid} ({before.get('product_code')}) does not match builder output")
        elif _canon(before) != _canon(after):
            _fail(f"unscheduled product {pid} ({before.get('product_code')}) changed")

    # Guard: E28A extension_policy must remain VERIFIED / allowed=True / 365 / 100 (PR A #8574).
    e28a = after_products[E28A_PRODUCT_VERSION_ID]
    if e28a.get("extension_policy") != {
        "status": "VERIFIED",
        "allowed": True,
        "reason_code": None,
        "days_per_extension": 365,
        "maximum_extensions": 100,
    }:
        _fail(f"E28A extension_policy drifted: {e28a.get('extension_policy')!r}")

    before_rules = _rules_by_id(restamped)
    after_rules = _rules_by_id(out)
    expected_rule_order = [
        *(r["rule_id"] for r in restamped["rules"] if r["rule_id"] not in RETIRED_RULE_IDS),
        *INSERTED_RULE_IDS_IN_ORDER,
    ]
    if [r["rule_id"] for r in out["rules"]] != expected_rule_order:
        _fail("rule order or membership changed outside the scheduled insertions")

    for rule_id, before in before_rules.items():
        if rule_id in RETIRED_RULE_IDS:
            continue
        after = after_rules[rule_id]
        if rule_id in MODIFIED_RULE_IDS:
            expected_after = _MODIFIED_RULE_BUILDERS[rule_id](before)
            if _canon(after) != _canon(expected_after):
                _fail(f"modified rule {rule_id!r} does not equal its builder output")
        elif _canon(before) != _canon(after):
            _fail(f"unscheduled rule {rule_id!r} changed")

    for rule_id in INSERTED_RULE_IDS_IN_ORDER:
        if _canon(after_rules[rule_id]) != _canon(_INSERTED_RULE_BUILDERS[rule_id]()):
            _fail(f"inserted rule {rule_id!r} does not equal its builder output")


def assert_anchor_relative_changes(anchor: dict[str, Any], out: dict[str, Any]) -> None:
    """Compare the seq-30 output directly with the seq-29 anchor."""

    if set(anchor) != set(out):
        _fail("anchor-relative top-level key set changed")
    for key in set(anchor) - _IDENTITY_KEYS - {"products", "rules"}:
        if _canon(anchor[key]) != _canon(out[key]):
            _fail(f"anchor-relative unexpected top-level change in {key}")
    restamped_shape = _with_identity(
        anchor,
        str(out["created_at"]),
        str(out["created_by"]),
    )
    assert_only_expected_changes(restamped_shape, out)


def _with_identity(payload: dict[str, Any], created_at: str, created_by: str) -> dict[str, Any]:
    out = copy.deepcopy(payload)
    out.update(
        {
            "sequence": SEQ30_SEQUENCE,
            "rule_pack_id": str(seq28._rule_pack_id(SEQ30_SEQUENCE)),
            "version": FOLD_VERSION,
            "created_at": created_at,
            "created_by": created_by,
            "previous_payload_sha256": SEQ29_PAYLOAD_SHA256,
            "rollback_of_payload_sha256": None,
        }
    )
    return out


def _assert_compile_gate(out: dict[str, Any], created_at: str) -> None:
    with tempfile.TemporaryDirectory(prefix="seq30-compile-") as temp_dir:
        path = Path(temp_dir) / "rulepack-prod-030.source.json"
        path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        _, report = compile_pack_source(
            path, observed_at=datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        )
    if not report.ok:
        detail = "; ".join(f"{error.code}:{error.message}" for error in report.errors)
        _fail(f"compile_pack gate failed: {detail}")


def _assert_candidate_review_inventory(out: dict[str, Any]) -> None:
    import os

    os.environ.setdefault("JWT_SECRET_KEY", "0" * 32)
    os.environ.setdefault("API_KEYS", "fold-pack-seq30-offline-check")
    seq29._assert_candidate_review_inventory(out)


def apply_content_edits(
    restamped: dict[str, Any],
    catalogue: dict[str, Any],
    *,
    created_at: str = FOLD_CREATED_AT,
    pages_dir: Path = E28_PAGES_DIR,
) -> dict[str, Any]:
    if restamped.get("sequence") != SEQ30_SEQUENCE:
        _fail(
            f"restamped base carries sequence {restamped.get('sequence')!r}, "
            f"expected {SEQ30_SEQUENCE}"
        )
    verify_saved_e28_pages(pages_dir)
    assert_catalogue_preconditions(catalogue)

    out = copy.deepcopy(restamped)
    products = _products_by_id(out)
    for pid in MODIFIED_PRODUCT_IDS:
        if pid not in products:
            _fail(f"product {pid!r} is absent")
    out["products"] = [
        _MODIFIED_PRODUCT_BUILDERS[p["product_version_id"]](p)
        if p["product_version_id"] in MODIFIED_PRODUCT_IDS
        else p
        for p in out["products"]
    ]

    rules = _rules_by_id(out)
    for rule_id in MODIFIED_RULE_IDS | RETIRED_RULE_IDS:
        if rule_id not in rules:
            _fail(f"rule {rule_id!r} is absent")
    for rule_id in INSERTED_RULE_IDS:
        if rule_id in rules:
            _fail(f"rule {rule_id!r} already exists")
    out["rules"] = [
        _MODIFIED_RULE_BUILDERS[rule["rule_id"]](rule)
        if rule["rule_id"] in MODIFIED_RULE_IDS
        else rule
        for rule in out["rules"]
        if rule["rule_id"] not in RETIRED_RULE_IDS
    ]
    out["rules"].extend(_INSERTED_RULE_BUILDERS[rule_id]() for rule_id in INSERTED_RULE_IDS_IN_ORDER)

    assert_only_expected_changes(restamped, out)
    for rule_id in (*sorted(MODIFIED_RULE_IDS), *INSERTED_RULE_IDS_IN_ORDER):
        _assert_required_facts(_rules_by_id(out)[rule_id])
    _assert_candidate_review_inventory(out)
    assert_no_hard_filter_reads_a_synthesised_twin_basis_fact(out)
    RulePackPayload.model_validate(out)
    _assert_compile_gate(out, created_at)
    return out


def fold_from_signed_seq29(
    anchor_source: dict[str, Any],
    anchor_signed: dict[str, Any],
    catalogue: dict[str, Any],
    *,
    trust_store: StaticTrustStore,
    observed_at: datetime | None = None,
    created_at: str = FOLD_CREATED_AT,
    created_by: str = FOLD_CREATED_BY,
    pages_dir: Path = E28_PAGES_DIR,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Verify signed seq-29, check its payload equals rulepack-prod-029.source.json, and fold."""

    if anchor_source.get("sequence") != SEQ29_SEQUENCE:
        _fail(f"anchor carries sequence {anchor_source.get('sequence')!r}, expected 29")
    if hashlib.sha256(_canon(anchor_source)).hexdigest() != SEQ29_PAYLOAD_SHA256:
        _fail("anchor source is not the pinned signed seq-29 payload")

    signed_at_raw = anchor_signed.get("protected", {}).get("signed_at")
    if not isinstance(signed_at_raw, str):
        _fail("anchor signed bundle is missing protected.signed_at")
    verify_at = observed_at or datetime.fromisoformat(signed_at_raw.replace("Z", "+00:00"))
    try:
        verified = verify_rule_pack(
            anchor_signed,
            trust_store=trust_store,
            observed_at=verify_at,
        )
    except RulePackVerificationError as exc:
        _fail(f"signed seq-29 anchor failed verification: {exc}")

    if verified.unsigned_dev is not False or verified.pack.payload.sequence != SEQ29_SEQUENCE:
        _fail("signed seq-29 anchor did not verify as production sequence 29")
    if verified.payload_sha256.hex() != SEQ29_PAYLOAD_SHA256:
        _fail(
            f"signed seq-29 payload_sha256 {verified.payload_sha256.hex()} != {SEQ29_PAYLOAD_SHA256}"
        )
    if _canon(anchor_signed.get("payload")) != _canon(anchor_source):
        _fail("signed seq-29 payload does not equal rulepack-prod-029.source.json")

    restamped = _with_identity(anchor_source, created_at, created_by)
    out = apply_content_edits(
        restamped,
        catalogue,
        created_at=created_at,
        pages_dir=pages_dir,
    )
    assert_anchor_relative_changes(anchor_source, out)
    return restamped, out


def main(argv: list[str] | None = None, *, observed_at: datetime | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--anchor-source",
        type=Path,
        default=_PACKS / "rulepack-prod-029.source.json",
    )
    parser.add_argument(
        "--anchor-signed",
        type=Path,
        default=_PACKS / "rulepack-prod-029.signed.json",
    )
    parser.add_argument("--catalogue", type=Path, default=_CATALOGUE)
    parser.add_argument("--e28-pages-dir", type=Path, default=E28_PAGES_DIR)
    parser.add_argument("--created-at", default=FOLD_CREATED_AT)
    parser.add_argument("--created-by", default=FOLD_CREATED_BY)
    parser.add_argument(
        "--output",
        type=Path,
        default=_PACKS / "rulepack-prod-030.source.json",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify that the existing --output file matches the fold output.",
    )
    args = parser.parse_args(argv)

    try:
        trust_store = StaticTrustStore.from_env()
    except RulePackVerificationError as exc:
        _fail(f"cannot load production trust store: {exc}")

    anchor_source = seq28._read_json(args.anchor_source)
    anchor_signed = seq28._read_json(args.anchor_signed)
    catalogue = seq28._read_json(args.catalogue)

    _, out = fold_from_signed_seq29(
        anchor_source,
        anchor_signed,
        catalogue,
        trust_store=trust_store,
        observed_at=observed_at,
        created_at=args.created_at,
        created_by=args.created_by,
        pages_dir=args.e28_pages_dir,
    )
    digest = hashlib.sha256(canonicalize_json(out)).hexdigest()

    if args.check:
        if not args.output.exists():
            _fail(f"{args.output} does not exist")
        on_disk = seq28._read_json(args.output)
        if _canon(on_disk) != _canon(out):
            _fail(f"{args.output} differs from fold_pack_seq30 output")
        print(f"fold_pack_seq30: OK ({args.output.name}, payload_sha256={digest})")
        return 0

    seq28._assert_output_path(
        args.output,
        [args.anchor_source, args.anchor_signed, args.catalogue, args.e28_pages_dir],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"fold_pack_seq30: wrote {args.output}")
    print(f"fold_pack_seq30: seq-30 payload_sha256 = {digest}")
    print(f"fold_pack_seq30: modified products = {sorted(MODIFIED_PRODUCT_IDS)}")
    print(f"fold_pack_seq30: modified rules = {sorted(MODIFIED_RULE_IDS)}")
    print(f"fold_pack_seq30: inserted rules = {list(INSERTED_RULE_IDS_IN_ORDER)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
