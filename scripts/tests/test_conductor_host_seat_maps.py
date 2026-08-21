"""Drift and disclosure gates for static Universal Conductor host seat maps."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

REPO = Path(__file__).resolve().parents[2]
FLEET = REPO / "FLEET_TOPOLOGY.json"
SCHEMA = REPO / "infra" / "conductor" / "host_seat_map.schema.json"
MAP_DIR = REPO / "infra" / "conductor" / "seat_maps"
MAPS = {
    "Pro": MAP_DIR / "pro.v1.json",
    "Mini": MAP_DIR / "mini.v1.json",
    "Air-M5": MAP_DIR / "air-m5.v1.json",
}
CLAUDE_ROSTER = ["A1", "A2", "A3", "A4", "A5", "AZ"]
CODEX_ROSTER = ["O1", "O2"]


def _read(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def _seat_statuses(
    manifest: dict[str, Any], provider: str
) -> dict[str, dict[str, str]]:
    return {seat["seat_id"]: seat for seat in manifest["providers"][provider]["seats"]}


def test_every_host_map_validates_against_the_committed_schema() -> None:
    schema = _read(SCHEMA)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    for machine, path in MAPS.items():
        manifest = _read(path)
        errors = sorted(
            validator.iter_errors(manifest), key=lambda item: list(item.path)
        )
        assert not errors, (machine, [error.message for error in errors])
        assert manifest["machine"] == machine


def test_fleet_and_all_host_maps_share_one_exact_opaque_roster() -> None:
    fleet = _read(FLEET)
    assert list(fleet["accounts"]["anthropic"]["slots"]) == CLAUDE_ROSTER
    assert list(fleet["accounts"]["openai"]["slots"]) == CODEX_ROSTER

    for path in MAPS.values():
        manifest = _read(path)
        assert manifest["providers"]["anthropic"]["canonical_roster"] == CLAUDE_ROSTER
        assert manifest["providers"]["openai"]["canonical_roster"] == CODEX_ROSTER


def test_pro_records_only_verified_static_selector_state() -> None:
    pro = _read(MAPS["Pro"])
    claude = _seat_statuses(pro, "anthropic")

    assert {
        seat
        for seat, status in claude.items()
        if status["selector_state"] == "available"
    } == {"A1", "A2", "A3", "AZ"}
    assert {
        seat for seat, status in claude.items() if status["local_binding"] == "unbound"
    } == {"A4", "A5"}
    assert all(status["runtime_auth"] == "unverified" for status in claude.values())
    assert all(
        status["selector_state"] == "unverified"
        for status in _seat_statuses(pro, "openai").values()
    )


def test_mini_and_air_never_inherit_or_infer_pro_bindings() -> None:
    for machine in ("Mini", "Air-M5"):
        manifest = _read(MAPS[machine])
        for provider in ("anthropic", "openai"):
            for status in _seat_statuses(manifest, provider).values():
                assert status == {
                    "seat_id": status["seat_id"],
                    "local_binding": "unverified",
                    "selector_state": "unverified",
                    "runtime_auth": "unverified",
                    "evidence": "no-host-evidence",
                }


def test_static_maps_cannot_claim_runtime_auth_or_embed_sensitive_locator_data() -> (
    None
):
    forbidden_keys = {
        "email",
        "account_identity",
        "token_value",
        "secret",
        "path",
        "profile_dir",
        "codex_home",
    }
    credential_shape = re.compile(
        r"(?:sk-|bearer\s+|oauth[_-]?token|refresh[_-]?token)", re.IGNORECASE
    )
    local_path_shape = re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\\\|~/)")

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            assert forbidden_keys.isdisjoint(value)
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)
        elif isinstance(value, str):
            assert "@" not in value
            assert not credential_shape.search(value)
            assert not local_path_shape.search(value)

    for path in MAPS.values():
        manifest = _read(path)
        walk(manifest)
        serialized = json.dumps(manifest, sort_keys=True)
        assert "endpoint_id" not in serialized
        assert "model_id" not in serialized
        assert all(
            status["runtime_auth"] == "unverified"
            for provider in ("anthropic", "openai")
            for status in _seat_statuses(manifest, provider).values()
        )


def test_o2_alias_policy_never_creates_a_third_codex_seat() -> None:
    for path in MAPS.values():
        openai = _read(path)["providers"]["openai"]
        assert openai["canonical_roster"] == ["O1", "O2"]
        assert [seat["seat_id"] for seat in openai["seats"]] == ["O1", "O2"]
        assert (
            openai["o2_alias_policy"] == "canonical-plus-compatibility-name-is-one-seat"
        )


def test_claude_profiles_and_headless_oauth_slots_stay_unmapped() -> None:
    for path in MAPS.values():
        surface = _read(path)["providers"]["anthropic"]["headless_oauth_surface"]
        assert surface == {
            "relationship_to_profiles": "separate-surface",
            "logical_seat_mapping": "unverified",
        }
