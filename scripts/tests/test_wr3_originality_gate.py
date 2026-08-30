"""Tests for the deterministic WR3 episode-local originality ledger."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from wr3_originality_gate import (  # noqa: E402
    CINEMATIC_AXES,
    CONCEPT_AXES,
    REQUEST_SCHEMA,
    OriginalityCollisionError,
    OriginalityLedgerError,
    OriginalitySeedMutationError,
    OriginalityValidationError,
    check_and_record,
    description_sha256,
    derive_child_seed,
    main,
    read_validated_ledger,
    signature_sha256,
    validated_ledger_prefix_sha256,
)


ROOT_SEED = "9fc9b711-be3b-45f8-9de0-fe4a7c99264e"
EPISODE_ID = "s01e13-residency-permit"
FIXED_NOW = datetime(2026, 8, 31, 1, 0, tzinfo=timezone.utc)


def _axes() -> dict[str, str]:
    return {
        "narrative_engine_id": "continuous-rights-unbundling",
        "spatial_metaphor_id": "invisible-thresholds",
        "opening_image_id": "warm-forward-passage",
        "emotional_turn_id": "confidence-to-calm-authority",
        "final_image_id": "neutral-locked-closeup",
        "camera_grammar_id": "tracking-compression-lockoff",
        "transition_motif_id": "architectural-occlusion",
        "sound_motif_id": "dry-latch-bridge",
        "color_arc_id": "warm-mixed-neutral",
        "blocking_id": "advance-constrain-voluntary-stop",
        "hero_prop_id": "none-body-architecture",
        "wardrobe_arc_id": "constant-ivory-gold",
    }


def _request(
    *,
    axes: dict[str, str] | None = None,
    seed_id: str | None = ROOT_SEED,
    parent_seed_id: str | None = None,
    description: str = (
        "A fluid architectural journey reveals separate rights through narrowing "
        "space and deliberate stillness."
    ),
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "schema_version": REQUEST_SCHEMA,
        "episode_id": EPISODE_ID,
        "parent_seed_id": parent_seed_id,
        "description": description,
        "signature_axes": axes or _axes(),
    }
    if seed_id is not None:
        request["seed_id"] = seed_id
    return request


def _changed_axes(
    *, concept: int = 0, cinematic: int = 0, surface: int = 0
) -> dict[str, str]:
    axes = _axes()
    surface_axes = ("hero_prop_id", "wardrobe_arc_id")
    for index, axis in enumerate(CONCEPT_AXES[:concept], start=1):
        axes[axis] = f"new-concept-{index}"
    for index, axis in enumerate(CINEMATIC_AXES[:cinematic], start=1):
        axes[axis] = f"new-cinematic-{index}"
    for index, axis in enumerate(surface_axes[:surface], start=1):
        axes[axis] = f"new-surface-{index}"
    return axes


def _register_root(ledger: Path) -> dict[str, Any]:
    return check_and_record(
        ledger,
        _request(),
        register_root=True,
        now=FIXED_NOW,
    )


def _ledger_records(ledger: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in ledger.read_text().splitlines()]


def _concurrent_root_registration(payload: tuple[str, dict[str, Any]]) -> str:
    ledger_path, request = payload
    receipt = check_and_record(Path(ledger_path), request, register_root=True)
    return str(receipt["status"])


def test_signature_sha_is_deterministic_after_nfkc_case_punctuation_normalization() -> (
    None
):
    first = _axes()
    second = _axes()
    first["camera_grammar_id"] = "  TRACKING—Compression, Lockoff  "
    second["camera_grammar_id"] = "tracking compression lockoff"
    first["opening_image_id"] = "ＷＡＲＭ forward\tpassage"
    second["opening_image_id"] = "warm forward passage"

    assert signature_sha256(first) == signature_sha256(second)


def test_root_pass_records_canonical_signature_and_receipt(tmp_path: Path) -> None:
    ledger = tmp_path / "originality-ledger.jsonl"

    receipt = _register_root(ledger)

    assert receipt["verdict"] == "PASS"
    assert receipt["status"] == "RECORDED"
    assert receipt["seed_id"] == ROOT_SEED
    assert receipt["sequence"] == 1
    expected_description = (
        "a fluid architectural journey reveals separate rights through narrowing "
        "space and deliberate stillness"
    )
    assert receipt["description_sha256"] == description_sha256(expected_description)
    assert receipt["novelty_policy"]["surface_axes_counted"] is False
    records = _ledger_records(ledger)
    assert len(records) == 1
    assert records[0]["description_normalized"] == expected_description
    assert records[0]["signature_sha256"] == signature_sha256(_axes())
    assert ledger.read_bytes().endswith(b"\n")


def test_exact_same_seed_and_signature_replay_is_idempotent(tmp_path: Path) -> None:
    ledger = tmp_path / "originality-ledger.jsonl"
    first = _register_root(ledger)

    replay = check_and_record(
        ledger,
        _request(
            description=(
                "  A FLUID ARCHITECTURAL JOURNEY REVEALS SEPARATE RIGHTS THROUGH "
                "NARROWING SPACE AND DELIBERATE STILLNESS!!!  "
            )
        ),
        register_root=True,
    )

    assert first["status"] == "RECORDED"
    assert replay["status"] == "IDEMPOTENT_REPLAY"
    assert replay["sequence"] == first["sequence"]
    assert len(_ledger_records(ledger)) == 1


def test_same_seed_signature_and_lineage_with_changed_description_fails(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "originality-ledger.jsonl"
    _register_root(ledger)

    with pytest.raises(
        OriginalitySeedMutationError, match="changes its normalized description"
    ):
        check_and_record(
            ledger,
            _request(
                description=(
                    "A deliberately different prose description cannot mutate the "
                    "already bound creative registration."
                )
            ),
            register_root=True,
        )

    assert len(_ledger_records(ledger)) == 1


def test_same_seed_with_different_signature_fails_as_mutation(tmp_path: Path) -> None:
    ledger = tmp_path / "originality-ledger.jsonl"
    _register_root(ledger)

    with pytest.raises(OriginalitySeedMutationError, match="already bound"):
        check_and_record(
            ledger,
            _request(axes=_changed_axes(concept=1)),
            register_root=True,
        )

    assert len(_ledger_records(ledger)) == 1


def test_child_with_exact_parent_structural_signature_fails(tmp_path: Path) -> None:
    ledger = tmp_path / "originality-ledger.jsonl"
    _register_root(ledger)

    with pytest.raises(OriginalityCollisionError, match="structural signature"):
        check_and_record(
            ledger,
            _request(
                seed_id=None,
                parent_seed_id=ROOT_SEED,
                description="Distinct language cannot conceal an exact structural replay.",
            ),
        )

    assert len(_ledger_records(ledger)) == 1


def test_surface_only_changes_never_count_as_material_novelty(tmp_path: Path) -> None:
    ledger = tmp_path / "originality-ledger.jsonl"
    _register_root(ledger)

    with pytest.raises(OriginalityCollisionError, match="not materially novel"):
        check_and_record(
            ledger,
            _request(
                axes=_changed_axes(surface=2),
                seed_id=None,
                parent_seed_id=ROOT_SEED,
                description="Lantern wardrobe decoration changes only superficial styling.",
            ),
        )


def test_material_threshold_passes_with_one_concept_and_three_cinematic_changes(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "originality-ledger.jsonl"
    _register_root(ledger)
    axes = _changed_axes(concept=1, cinematic=3)

    receipt = check_and_record(
        ledger,
        _request(
            axes=axes,
            seed_id=None,
            parent_seed_id=ROOT_SEED,
            description=(
                "An overhead chamber fragments momentum while resonant footsteps "
                "trigger an abrupt emotional reversal."
            ),
        ),
        now=FIXED_NOW,
    )

    expected_seed = derive_child_seed(ROOT_SEED, signature_sha256(axes))
    assert receipt["status"] == "RECORDED"
    assert receipt["seed_id"] == expected_seed
    assert receipt["novelty_policy"]["closest_structural_difference"] == {
        "material": 4,
        "concept": 1,
        "cinematic": 3,
        "surface_ignored": 0,
    }


@pytest.mark.parametrize(
    ("concept", "cinematic"),
    [
        (1, 2),  # only three material differences
        (3, 1),  # four material differences, but insufficient cinematic change
        (0, 4),  # four material differences, but no concept change
    ],
)
def test_material_threshold_fails_when_any_required_dimension_is_missing(
    tmp_path: Path, concept: int, cinematic: int
) -> None:
    ledger = tmp_path / f"originality-{concept}-{cinematic}.jsonl"
    _register_root(ledger)

    with pytest.raises(OriginalityCollisionError, match="not materially novel"):
        check_and_record(
            ledger,
            _request(
                axes=_changed_axes(concept=concept, cinematic=cinematic),
                seed_id=None,
                parent_seed_id=ROOT_SEED,
                description=(
                    f"Alternative chamber grammar changes vector {concept} and "
                    f"cinematic dimension {cinematic}."
                ),
            ),
        )


def test_description_jaccard_at_or_above_point_eight_fails(tmp_path: Path) -> None:
    ledger = tmp_path / "originality-ledger.jsonl"
    root_description = "Amber corridor woman crosses silent boundary toward chamber"
    check_and_record(
        ledger,
        _request(description=root_description),
        register_root=True,
    )

    with pytest.raises(OriginalityCollisionError, match="Jaccard collision"):
        check_and_record(
            ledger,
            _request(
                axes=_changed_axes(concept=2, cinematic=2),
                seed_id=None,
                parent_seed_id=ROOT_SEED,
                # Eight shared nontrivial tokens and two new ones: exactly 0.80.
                description=root_description + " slowly today",
            ),
        )

    assert len(_ledger_records(ledger)) == 1


def test_child_requires_existing_parent_and_does_not_create_ledger_record(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "originality-ledger.jsonl"
    missing_parent = str(uuid.uuid4())

    with pytest.raises(OriginalityValidationError, match="does not exist"):
        check_and_record(
            ledger,
            _request(
                axes=_changed_axes(concept=2, cinematic=2),
                seed_id=None,
                parent_seed_id=missing_parent,
                description="Fresh rotating chamber exposes a silent boundary fracture.",
            ),
        )

    assert ledger.exists()
    assert ledger.read_bytes() == b""


@pytest.mark.parametrize(
    "payload",
    [
        b'{"schema_version":"wr3.originality-ledger-record.v1"}',
        b"{not-json}\n",
        b"\n",
    ],
)
def test_malformed_or_torn_ledger_fails_closed_without_append(
    tmp_path: Path, payload: bytes
) -> None:
    ledger = tmp_path / "originality-ledger.jsonl"
    ledger.write_bytes(payload)

    with pytest.raises(OriginalityLedgerError):
        _register_root(ledger)

    assert ledger.read_bytes() == payload


def test_concurrent_exact_reservations_append_once_and_replay(tmp_path: Path) -> None:
    ledger = tmp_path / "originality-ledger.jsonl"
    payloads = [(str(ledger), _request()) for _ in range(8)]
    context = multiprocessing.get_context("fork")

    with context.Pool(processes=4) as pool:
        statuses = pool.map(_concurrent_root_registration, payloads)

    assert statuses.count("RECORDED") == 1
    assert statuses.count("IDEMPOTENT_REPLAY") == 7
    assert len(_ledger_records(ledger)) == 1


def test_read_validated_ledger_is_read_only_and_returns_canonical_records(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "originality-ledger.jsonl"
    request = _request()
    _register_root(ledger)
    before = ledger.read_bytes()

    records = read_validated_ledger(ledger)

    assert ledger.read_bytes() == before
    assert len(records) == 1
    assert records[0]["seed_id"] == ROOT_SEED
    assert records[0]["signature_sha256"] == signature_sha256(request["signature_axes"])


def test_validated_prefix_hash_stays_bound_after_valid_ledger_growth(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "originality-ledger.jsonl"
    _register_root(ledger)
    root_prefix = ledger.read_bytes()

    check_and_record(
        ledger,
        _request(
            axes=_changed_axes(concept=1, cinematic=3),
            seed_id=None,
            parent_seed_id=ROOT_SEED,
            description=(
                "An overhead chamber fragments momentum while resonant footsteps "
                "trigger an abrupt emotional reversal."
            ),
        ),
        now=FIXED_NOW,
    )

    assert len(_ledger_records(ledger)) == 2
    assert (
        validated_ledger_prefix_sha256(ledger, 1)
        == hashlib.sha256(root_prefix).hexdigest()
    )
    assert (
        validated_ledger_prefix_sha256(ledger, 2)
        == hashlib.sha256(ledger.read_bytes()).hexdigest()
    )
    assert validated_ledger_prefix_sha256(ledger, 0) == hashlib.sha256(b"").hexdigest()


@pytest.mark.parametrize("record_count", [-1, True, 2])
def test_validated_prefix_hash_rejects_invalid_record_count(
    tmp_path: Path, record_count: int
) -> None:
    ledger = tmp_path / "originality-ledger.jsonl"
    _register_root(ledger)

    with pytest.raises(OriginalityLedgerError, match="record_count"):
        validated_ledger_prefix_sha256(ledger, record_count)


def test_ledger_validation_replays_historical_description_policy(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "originality-ledger.jsonl"
    _register_root(ledger)
    check_and_record(
        ledger,
        _request(
            axes=_changed_axes(concept=1, cinematic=3),
            seed_id=None,
            parent_seed_id=ROOT_SEED,
            description=(
                "An overhead chamber fragments momentum while resonant footsteps "
                "trigger an abrupt emotional reversal."
            ),
        ),
        now=FIXED_NOW,
    )
    records = _ledger_records(ledger)
    records[1]["description_normalized"] = records[0]["description_normalized"]
    records[1]["description_tokens"] = records[0]["description_tokens"]
    ledger.write_bytes(
        b"".join(
            json.dumps(
                record,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
            for record in records
        )
    )

    with pytest.raises(OriginalityLedgerError, match="historical description"):
        read_validated_ledger(ledger)


def test_cli_check_and_record_emits_one_json_receipt(
    tmp_path: Path, capsys: Any
) -> None:
    ledger = tmp_path / "originality-ledger.jsonl"
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(_request()), encoding="utf-8")

    exit_code = main(
        [
            "check-and-record",
            "--ledger",
            str(ledger),
            "--request",
            str(request_path),
            "--register-root",
        ]
    )

    output = capsys.readouterr()
    receipt = json.loads(output.out)
    assert exit_code == 0
    assert output.err == ""
    assert receipt["verdict"] == "PASS"
    assert receipt["status"] == "RECORDED"
