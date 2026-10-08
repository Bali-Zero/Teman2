"""derive_seq26_e31_options.py — seq-26: the E31 family offers a 1- or 2-year ITAS.

# bites-observable — every path has a repo-relative default; no argument names a
# program to run or a database to reach. The output path is the only write.

One concern: each E31 product whose saved portal page says "1 tahun atau 2 tahun"
gains ``duration_options`` (365 days on its existing 1-year catalogue key, 730 days on
the same variant's "2 Years" sibling) and a FIXED_DAYS stay policy that reaches 730.
No rule, no source record and no stamp moves, so the freshness boundary of seq-25
(2026-11-08T13:32:18Z) carries over unchanged. Identity fields move as in every fold.

The derivation is deterministic: it reads the seq-25 source, the saved portal texts and
the official price catalogue, and refuses on the first inconsistency. A product whose
page does not say 2 years gets no option; a 2-year sibling missing from the catalogue
aborts, because a key or a price is never invented here.

Owner ruling (Zero, 2026-10-08): the 2-year ITAS is a duration option of the same product,
priced all-inclusive per option from the official catalogue; never a PNBP figure in
client-facing text, never "quote on request".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

from backend.services.visa_engine.bundle import canonicalize_json
from backend.services.visa_engine.models import RulePackPayload

_REPO_ROOT = Path(__file__).resolve().parents[5]
_BACKEND = _REPO_ROOT / "apps/backend-rag/backend"
_PACKS = _BACKEND / "services/visa_engine/contracts/packs"

SEQ25_PAYLOAD_SHA256 = (
    "603f777e5fdd8ffbd5824282593b6584893f39b0b6b192f59c4563ae6d9c9d11"  # pragma: allowlist secret
)
FOLD_VERSION = "2026.10.8"
FOLD_CREATED_AT = "2026-10-08T08:31:00Z"
FOLD_CREATED_BY = "agent.air-m5.backend-rag.visa-e31-two-year.fold-2026-10-08"
LEDGER_DIR = _REPO_ROOT / "research/visa/2026-10-07-freshness-restamp-seq25"
CATALOGUE_PATH = _BACKEND / "data/bali_zero_official_prices_2026.json"
SEQ25_SOURCE_PATH = _PACKS / "rulepack-prod-025.source.json"
SEQ26_SOURCE_PATH = _PACKS / "rulepack-prod-026.source.json"

#: The sentence the Ditjen Imigrasi E31 pages carry, verified verbatim in the saved text.
TWO_YEAR_SENTENCE = "selama 1 tahun atau 2 tahun dihitung sejak tanggal kedatangan"
FAMILY_PREFIX = "E31"
ONE_YEAR_MARK = "1 Year"
TWO_YEAR_MARK = "2 Years"
OPTION_DAYS = (365, 730)

_RULE_PACK_ID_URL_PREFIX = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/"
)


def _fail(message: str) -> NoReturn:
    sys.exit(f"derive_seq26_e31_options: REFUSED — {message}")


def rule_pack_id(sequence: int) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"{_RULE_PACK_ID_URL_PREFIX}{sequence}")


def portal_text_for(product: dict[str, Any], ledger_dir: Path) -> tuple[str, Path] | None:
    """(source_record_id, saved text file) of the product's page that says 1 or 2 years, if any."""

    for source_id in product["source_refs"]:
        path = ledger_dir / "text" / f"{source_id[:8]}.txt"
        if path.exists() and TWO_YEAR_SENTENCE in " ".join(
            path.read_text(encoding="utf-8").split()
        ):
            return source_id, path
    return None


def derive(seq25: dict[str, Any], catalogue: dict[str, Any], ledger_dir: Path) -> dict[str, Any]:
    digest = hashlib.sha256(canonicalize_json(seq25)).hexdigest()
    if digest != SEQ25_PAYLOAD_SHA256:
        _fail(
            f"the seq-25 source is not the signed artifact: JCS digest {digest} != {SEQ25_PAYLOAD_SHA256}"
        )
    if seq25.get("sequence") != 25 or seq25.get("rule_pack_id") != str(rule_pack_id(25)):
        _fail("the anchor is not seq-25 with the uuid5 identity")
    rows = catalogue["services"]["kitas_permits"]

    out = json.loads(json.dumps(seq25))
    optioned: list[str] = []
    for product in out["products"]:
        code = product["product_code"]
        if not code.startswith(FAMILY_PREFIX):
            continue
        if portal_text_for(product, ledger_dir) is None:
            continue
        key = product["pricing_key"]
        if key["category"] != "kitas_permits" or ONE_YEAR_MARK not in key["item_key"]:
            _fail(f"{code}: base pricing_key {key!r} is not a 1-year kitas_permits row")
        sibling = key["item_key"].replace(ONE_YEAR_MARK, TWO_YEAR_MARK)
        if key["item_key"] not in rows or sibling not in rows:
            _fail(
                f"{code}: catalogue row {key['item_key']!r} or its sibling {sibling!r} is missing — STOP"
            )
        stay = product["stay_policy"]
        if stay["kind"] != "FIXED_DAYS" or stay["minimum_days"] != OPTION_DAYS[0]:
            _fail(f"{code}: stay_policy {stay!r} is not FIXED_DAYS from 365")
        stay["maximum_days"] = OPTION_DAYS[1]
        product["duration_options"] = [
            {"days": OPTION_DAYS[0], "pricing_key": dict(key)},
            {
                "days": OPTION_DAYS[1],
                "pricing_key": {"category": key["category"], "item_key": sibling},
            },
        ]
        optioned.append(code)
    if not optioned:
        _fail("no E31 product's saved page says 1 or 2 years — nothing to derive")

    out["sequence"] = 26
    out["rule_pack_id"] = str(rule_pack_id(26))
    out["version"] = FOLD_VERSION
    out["created_at"] = FOLD_CREATED_AT
    out["created_by"] = FOLD_CREATED_BY
    out["previous_payload_sha256"] = SEQ25_PAYLOAD_SHA256
    out["rollback_of_payload_sha256"] = None
    created = datetime.strptime(FOLD_CREATED_AT, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    if created > datetime.now(timezone.utc):
        _fail(f"created_at {FOLD_CREATED_AT} is in the future — fix FOLD_CREATED_AT")
    RulePackPayload.model_validate(out)
    return out


#: The nine products the ruling names and the base key each one carries (Offshore variant).
E31_BASE_KEYS = {
    "E31A": "Spouse 1 Year (Offshore)",
    **dict.fromkeys(
        ("E31B", "E31C", "E31D", "E31E", "E31F", "E31G", "E31H", "E31J"),
        "Dependent 1 Year (Offshore)",
    ),
}
EXPECTED_AMOUNTS_IDR = (11_000_000, 15_000_000)


class _CatalogueView:
    loaded = True

    def __init__(self, catalogue: dict[str, Any]) -> None:
        self._catalogue = catalogue
        self._rows = catalogue["services"]["kitas_permits"]

    def get_service_by_key(self, key: str) -> dict[str, Any] | None:
        row = self._rows.get(key)
        return None if row is None else {**row, "category": "kitas_permits"}

    def get_all_prices(self) -> dict[str, Any]:
        return {
            "version": self._catalogue["version"],
            "metadata": self._catalogue["metadata"],
            "services": self._rows,
        }


def check_e31_options(pack: dict[str, Any], catalogue: dict[str, Any]) -> list[str]:
    """Everything the ruling says about all nine E31 products, independent of the derivation.

    Used by the CI observer and the tests: a pack that lost one product's options, pointed a
    730-day option at the 1-year row, or let the top-level key drift from the first option is
    named here even when a re-derivation drifts the same way. Returns the problems found.
    """

    from datetime import datetime, timezone

    from pydantic import ValidationError

    from backend.services.visa_engine.models import VisaProductVersion
    from backend.services.visa_engine.pricing_adapter import resolve_candidate_pricing

    problems: list[str] = []
    products = {p["product_code"]: p for p in pack["products"]}
    view = _CatalogueView(catalogue)
    for code, base in E31_BASE_KEYS.items():
        product = products.get(code)
        if product is None:
            problems.append(f"{code}: product missing")
            continue
        options = product.get("duration_options") or []
        if [o.get("days") for o in options] != list(OPTION_DAYS):
            problems.append(f"{code}: options are not exactly 365 and 730 days")
            continue
        sibling = base.replace(ONE_YEAR_MARK, TWO_YEAR_MARK)
        wanted = [
            {"category": "kitas_permits", "item_key": base},
            {"category": "kitas_permits", "item_key": sibling},
        ]
        if [o["pricing_key"] for o in options] != wanted:
            problems.append(f"{code}: option keys are not {base!r} then {sibling!r}")
        if product["pricing_key"] != options[0]["pricing_key"]:
            problems.append(f"{code}: top-level pricing_key is not the first option's")
        stay = product["stay_policy"]
        if (stay["kind"], stay["minimum_days"], stay["maximum_days"]) != (
            "FIXED_DAYS",
            *OPTION_DAYS,
        ):
            problems.append(f"{code}: stay_policy is not FIXED_DAYS 365..730")
        try:
            model = VisaProductVersion.model_validate(product)
        except ValidationError:
            problems.append(f"{code}: the product no longer validates against the model")
            continue
        for days, amount in zip(OPTION_DAYS, EXPECTED_AMOUNTS_IDR, strict=True):
            got = resolve_candidate_pricing(
                model,
                pricing_catalog=view,
                evaluated_at=datetime(2026, 10, 8, tzinfo=timezone.utc),
                stay_days=days,
            ).amount
            if got != amount:
                problems.append(f"{code}: {days} days resolves {got}, expected {amount}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Derive RulePack seq-26 (E31 duration options) from seq-25."
    )
    parser.add_argument("--seq25-source", type=Path, default=SEQ25_SOURCE_PATH)
    parser.add_argument("--catalogue", type=Path, default=CATALOGUE_PATH)
    parser.add_argument("--ledger-dir", type=Path, default=LEDGER_DIR)
    parser.add_argument("--output", type=Path, default=SEQ26_SOURCE_PATH)
    args = parser.parse_args(argv)
    if args.output == args.seq25_source:
        _fail("--output collides with the anchor")
    seq25 = json.loads(args.seq25_source.read_text(encoding="utf-8"))
    catalogue = json.loads(args.catalogue.read_text(encoding="utf-8"))
    seq26 = derive(seq25, catalogue, args.ledger_dir)
    args.output.write_text(json.dumps(seq26, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    digest = hashlib.sha256(canonicalize_json(seq26)).hexdigest()
    with_options = [p["product_code"] for p in seq26["products"] if p.get("duration_options")]
    sys.stdout.write(
        f"derive_seq26_e31_options: wrote {args.output}\n"
        f"derive_seq26_e31_options: seq-26 payload_sha256 = {digest}\n"
        f"derive_seq26_e31_options: duration options on {','.join(with_options)}\n"
        "derive_seq26_e31_options: NOT SIGNED, NOT ACTIVATED\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
