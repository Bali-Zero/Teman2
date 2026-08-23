from __future__ import annotations

import itertools
import unicodedata
from inspect import signature
from typing import Literal, cast

import pytest
import research_os.hashing as hashing
from pydantic import BaseModel
from research_os.version import CONTRACT_VERSION

TYPED_CONTRACT_VERSION = cast(Literal["research-os/v1.0.0"], CONTRACT_VERSION)


def test_hash_wire_format_rejects_every_noncanonical_form() -> None:
    invalid_values = (
        f"sha256:{'a' * 64}",
        "A" * 64,
        "a" * 63,
        "a" * 65,
        "g" * 64,
    )
    for value in invalid_values:
        with pytest.raises(hashing.HashFormatError):
            hashing.validate_sha256_hex(value)


def test_canonicalize_translates_rfc8785_failure_to_typed_error() -> None:
    with pytest.raises(hashing.CanonicalizationError):
        hashing.canonicalize({"unsafe": float("nan")})


def test_rfc8785_number_serialization_reference_vector() -> None:
    value = [333333333.33333329, 1e30, 4.50, 2e-3, 1e-27]

    assert hashing.canonicalize(value) == b"[333333333.3333333,1e+30,4.5,0.002,1e-27]"


def test_rfc8785_unicode_and_escaping_reference_vector() -> None:
    value = {"string": '\u20ac$\u000f\nA\'B"\\\\"/', "literals": [None, True, False]}

    assert hashing.canonicalize(value) == (
        b'{"literals":[null,true,false],"string":"\xe2\x82\xac$\\u000f\\nA\'B\\"\\\\\\\\\\"/"}'
    )


def test_object_hash_is_stable_across_key_permutations_and_runs() -> None:
    pairs = [("contract_version", CONTRACT_VERSION), ("alpha", 1), ("beta", "é")]
    hashes = {
        hashing.object_hash(dict(permutation))
        for permutation in itertools.permutations(pairs)
        for _ in range(3)
    }
    assert len(hashes) == 1


def test_hash_changes_only_for_non_omitted_fields() -> None:
    base = {"contract_version": CONTRACT_VERSION, "object_hash": "0" * 64, "value": 1}
    changed_content = {**base, "value": 2}
    changed_omitted = {**base, "object_hash": "f" * 64}

    assert hashing.object_hash(base) != hashing.object_hash(changed_content)
    assert hashing.object_hash(base) == hashing.object_hash(changed_omitted)


def test_caller_cannot_choose_a_different_omission_set() -> None:
    assert "omit" not in signature(hashing.object_hash).parameters
    with pytest.raises(TypeError, match="unexpected keyword argument 'omit'"):
        hashing.object_hash(  # type: ignore[call-arg]
            {"contract_version": CONTRACT_VERSION, "value": 1},
            omit=frozenset({"value"}),
        )


class _OptionalWireModel(BaseModel):
    contract_version: Literal["research-os/v1.0.0"]
    optional_value: str | None = None


def test_explicit_null_remains_present_in_canonical_bytes() -> None:
    explicit_null = _OptionalWireModel(
        contract_version=TYPED_CONTRACT_VERSION,
        optional_value=None,
    )

    assert hashing.canonicalize(explicit_null) == (
        b'{"contract_version":"research-os/v1.0.0","optional_value":null}'
    )


def test_explicit_null_and_absent_optional_field_hash_differ() -> None:
    absent = _OptionalWireModel(contract_version=TYPED_CONTRACT_VERSION)
    explicit_null = _OptionalWireModel(
        contract_version=TYPED_CONTRACT_VERSION,
        optional_value=None,
    )

    assert hashing.object_hash(absent) != hashing.object_hash(explicit_null)


def test_v1_transport_metadata_omission_set_is_frozen_empty() -> None:
    transport_metadata_fields = getattr(hashing, "TRANSPORT_METADATA_FIELDS", None)
    assert transport_metadata_fields is not None
    assert transport_metadata_fields[CONTRACT_VERSION] == frozenset()


def test_unicode_forms_are_each_stable_without_silent_normalization() -> None:
    hashes = []
    for form in ("NFC", "NFD", "NFKC", "NFKD"):
        value = unicodedata.normalize(form, "é")
        first = hashing.object_hash({"contract_version": CONTRACT_VERSION, "value": value})
        assert all(
            hashing.object_hash({"value": value, "contract_version": CONTRACT_VERSION}) == first
            for _ in range(5)
        )
        hashes.append(first)
    assert hashes[0] != hashes[1]


def test_changing_each_non_omitted_field_changes_hash() -> None:
    base = {"contract_version": CONTRACT_VERSION, "alpha": 1, "beta": "two"}
    baseline = hashing.object_hash(base)
    mutations = ({**base, "alpha": 2}, {**base, "beta": "changed"})
    assert all(hashing.object_hash(mutation) != baseline for mutation in mutations)
