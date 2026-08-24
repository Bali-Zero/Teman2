"""Regression coverage for the UTC-timestamp hash-parity defect.

CONTRACTS.md sec 3's ``UtcDateTime`` accepts two wire spellings of the same
instant (trailing ``Z`` or ``+00:00``, ``_UTC_OFFSET_PATTERN`` in
``primitives.py``) and places no constraint on fractional-second digit count.
``research_os.hashing.object_hash`` has two entry paths:

- a ``BaseModel`` is re-rendered through ``model_dump(mode="json", ...)``,
  which pydantic *always* normalizes to a single spelling (``Z``, fractional
  seconds omitted when exactly zero else zero-padded to 6 digits);
- a plain ``Mapping`` is hashed byte-for-byte as received.

A wire-valid document carrying the ``+00:00`` spelling (or non-canonical
fractional-second padding) therefore hashes differently depending on which
path computes it -- breaking CONTRACTS.md sec 2's "the hash procedure must be
identical in every implementation" promise. This is a hash-computation defect
inside ``object_hash``/``canonicalize``, not a schema-acceptance question:
both spellings remain wire-valid; they must simply hash identically.

No fixture named ``fixtures/intel_event/`` exists in this package -- only the
foundation slice's two implemented contract kinds (``object_successor_edge``,
``revocation_receipt``) ship fixtures today -- so the reproduction below uses
those two real, checked-in fixtures instead.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import research_os.hashing as hashing
from pydantic import BaseModel, ValidationError
from research_os.cli import FIXTURES_ROOT, PACKAGE_ROOT
from research_os.models.revocation_receipt import RevocationReceipt
from research_os.models.successor_edge import ObjectSuccessorEdge

CONTRACT_MODELS: dict[str, type[BaseModel]] = {
    "object_successor_edge": ObjectSuccessorEdge,
    "revocation_receipt": RevocationReceipt,
}
UTC_FIELD_BY_CONTRACT = {
    "object_successor_edge": "recorded_at",
    "revocation_receipt": "issued_at",
}


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "research_os.cli", *args],
        check=False,
        capture_output=True,
        cwd=PACKAGE_ROOT,
        text=True,
    )


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# --- 1. object_hash() itself must be invariant to spelling -----------------


def test_object_hash_invariant_to_utc_offset_spelling() -> None:
    z_spelled = {"contract_version": "research-os/v1.0.0", "issued_at": "2026-02-01T00:01:00Z"}
    offset_spelled = {
        "contract_version": "research-os/v1.0.0",
        "issued_at": "2026-02-01T00:01:00+00:00",
    }

    assert hashing.object_hash(z_spelled) == hashing.object_hash(offset_spelled)


def test_object_hash_invariant_to_fractional_second_padding() -> None:
    unpadded = {"contract_version": "research-os/v1.0.0", "issued_at": "2026-02-01T00:01:00.5Z"}
    padded = {
        "contract_version": "research-os/v1.0.0",
        "issued_at": "2026-02-01T00:01:00.500000Z",
    }
    zero_fraction = {
        "contract_version": "research-os/v1.0.0",
        "issued_at": "2026-02-01T00:01:00.000000Z",
    }
    no_fraction = {"contract_version": "research-os/v1.0.0", "issued_at": "2026-02-01T00:01:00Z"}

    assert hashing.object_hash(unpadded) == hashing.object_hash(padded)
    assert hashing.object_hash(zero_fraction) == hashing.object_hash(no_fraction)
    # a genuinely different instant must still hash differently -- the fix
    # must not collapse everything that merely *contains* a timestamp.
    assert hashing.object_hash(unpadded) != hashing.object_hash(no_fraction)


def test_object_hash_still_distinguishes_non_timestamp_content() -> None:
    base = {"contract_version": "research-os/v1.0.0", "issued_at": "2026-02-01T00:01:00Z"}
    changed = {**base, "issued_at": "2026-02-01T00:01:01Z"}

    assert hashing.object_hash(base) != hashing.object_hash(changed)


# --- 2. end-to-end reproduction on the two real, implemented fixtures ------


def test_offset_rewritten_wire_document_validates_against_both_foundation_contracts() -> None:
    for contract_kind, model in CONTRACT_MODELS.items():
        field = UTC_FIELD_BY_CONTRACT[contract_kind]
        fixture_path = FIXTURES_ROOT / contract_kind / "valid_minimal.json"
        doc = _load(fixture_path)
        assert doc[field].endswith("Z"), f"fixture assumption violated: {doc[field]!r}"

        rewritten = copy.deepcopy(doc)
        rewritten[field] = rewritten[field][:-1] + "+00:00"
        # A real cross-language producer would hash the wire-valid document
        # it is about to send using the raw-dict path (it has no reason to
        # instantiate a Python pydantic model first).
        rewritten["object_hash"] = hashing.object_hash(rewritten)

        try:
            model.model_validate(rewritten)
        except ValidationError as exc:  # pragma: no cover -- failure path asserted below
            codes = {str(error["type"]) for error in exc.errors()}
            raise AssertionError(
                f"{contract_kind}: a +00:00-spelled, self-consistently-hashed wire "
                f"document was rejected by model validation: {codes}"
            ) from exc


# --- 3. the two CLI verbs must agree ----------------------------------------


def test_cli_hash_and_validate_agree_on_offset_rewritten_fixture(tmp_path: Path) -> None:
    contract_kind = "revocation_receipt"
    field = UTC_FIELD_BY_CONTRACT[contract_kind]
    doc = _load(FIXTURES_ROOT / contract_kind / "valid_minimal.json")
    doc[field] = doc[field][:-1] + "+00:00"
    doc["object_hash"] = hashing.object_hash(doc)

    rewritten_path = tmp_path / "offset_variant.json"
    rewritten_path.write_text(json.dumps(doc), encoding="utf-8")

    hash_result = _run_cli("hash", "--file", str(rewritten_path))
    validate_result = _run_cli(
        "validate", "--contract", contract_kind, "--file", str(rewritten_path)
    )

    assert hash_result.returncode == 0, hash_result.stdout
    assert validate_result.returncode == 0, validate_result.stdout
    assert json.loads(hash_result.stdout)["object_hash"] == doc["object_hash"]
    assert json.loads(validate_result.stdout)["valid"] is True


def test_cli_hash_matches_stored_object_hash_for_every_checked_in_fixture() -> None:
    """The user-visible symptom: `hash` and `validate` must never disagree.

    For every checked-in ``valid_*.json`` fixture (already self-consistent by
    construction), `cli hash` must reproduce the document's own stored
    ``object_hash`` and `cli validate` must accept it. If the two verbs ever
    computed the hash differently, at least one of these would fail for a
    fixture that is -- by its own filename convention -- supposed to be
    valid.
    """

    checked = 0
    for contract_kind in CONTRACT_MODELS:
        contract_dir = FIXTURES_ROOT / contract_kind
        for fixture_path in sorted(contract_dir.glob("valid_*.json")):
            checked += 1
            doc = _load(fixture_path)

            hash_result = _run_cli("hash", "--file", str(fixture_path))
            validate_result = _run_cli(
                "validate", "--contract", contract_kind, "--file", str(fixture_path)
            )

            assert hash_result.returncode == 0, (fixture_path, hash_result.stdout)
            assert validate_result.returncode == 0, (fixture_path, validate_result.stdout)
            assert json.loads(hash_result.stdout)["object_hash"] == doc["object_hash"], fixture_path
            assert json.loads(validate_result.stdout)["valid"] is True, fixture_path

    assert checked >= 2, "expected both foundation-slice contract kinds to ship a valid fixture"
