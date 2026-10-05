"""Drift and disclosure gates for static Universal Conductor host seat maps."""

from __future__ import annotations

import copy
import json
import re
import subprocess
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
CODEX_ROSTERS = {
    "Pro": ["O1", "O2"],
    "Mini": ["O1", "O2"],
    "Air-M5": ["O1", "O2", "O3"],
}
CODEX_SEAT_LIB = REPO / "scripts" / "lib" / "codex_seat.sh"


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
    assert list(fleet["accounts"]["openai"]["slots"]) == ["O1", "O2", "O3"]
    assert "unrostered_seats" not in fleet["accounts"]["openai"]

    for machine, path in MAPS.items():
        manifest = _read(path)
        assert manifest["providers"]["anthropic"]["canonical_roster"] == CLAUDE_ROSTER
        assert (
            manifest["providers"]["openai"]["canonical_roster"]
            == CODEX_ROSTERS[machine]
        )


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
                status = {k: v for k, v in status.items() if k != "quota_independence"}
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


def test_codex_roster_and_alias_policy_are_pinned_per_host() -> None:
    for machine in ("Pro", "Mini"):
        openai = _read(MAPS[machine])["providers"]["openai"]
        assert [seat["seat_id"] for seat in openai["seats"]] == ["O1", "O2"]
        assert (
            openai["o2_alias_policy"] == "canonical-plus-compatibility-name-is-one-seat"
        )
    air = _read(MAPS["Air-M5"])["providers"]["openai"]
    assert [seat["seat_id"] for seat in air["seats"]] == ["O1", "O2", "O3"]
    assert air["o2_alias_policy"] == "acct2-is-a-distinct-account-O3"
    assert air["seats"][2]["quota_independence"] == "unverified"


def _openai_errors(machine: str, mutate) -> list[str]:
    manifest = copy.deepcopy(_read(MAPS[machine]))
    mutate(manifest["providers"]["openai"])
    validator = Draft202012Validator(_read(SCHEMA), format_checker=FormatChecker())
    return [error.message for error in validator.iter_errors(manifest)]


def _make_three_seat(openai: dict[str, Any]) -> None:
    openai["canonical_roster"] = ["O1", "O2", "O3"]
    openai["o2_alias_policy"] = "acct2-is-a-distinct-account-O3"
    openai["auto_rotation_order"] = ["O1", "O2", "O3"]
    openai["seats"].append(
        {**openai["seats"][0], "seat_id": "O3", "quota_independence": "unverified"}
    )


def test_schema_rejects_o3_in_the_pro_shape() -> None:
    assert _openai_errors("Pro", lambda openai: None) == []
    assert _openai_errors("Air-M5", lambda openai: None) == []
    for machine in ("Pro", "Mini"):
        assert _openai_errors(machine, _make_three_seat)


def test_schema_rejects_the_three_seat_shape_without_the_marker() -> None:
    assert _openai_errors("Air-M5", lambda openai: None) == []  # control: valid as is

    # the marker is the ONLY difference from the control, so only it can be the cause
    assert _openai_errors(
        "Air-M5", lambda openai: openai["seats"][2].pop("quota_independence")
    )


def test_schema_rejects_a_verified_quota_independence_claim() -> None:
    def claim(openai: dict[str, Any]) -> None:
        openai["seats"][2]["quota_independence"] = "verified"

    assert _openai_errors("Air-M5", lambda openai: None) == []  # control
    assert _openai_errors("Air-M5", claim)


def test_the_third_seat_with_the_two_seat_alias_policy_is_rejected() -> None:
    def mix(openai: dict[str, Any]) -> None:
        openai["o2_alias_policy"] = "canonical-plus-compatibility-name-is-one-seat"

    assert _openai_errors("Air-M5", mix)


def _bound_homes(machine: str, home: Path) -> dict[str, str]:
    slots = _read(FLEET)["accounts"]["openai"]["slots"]
    return {
        str(home / slot["codex_home_by_machine"][machine][2:]): seat
        for seat, slot in slots.items()
        if machine in slot["codex_home_by_machine"]
    }


def test_registry_seat_map_and_conductor_agree_on_the_air_m5_codex_bindings() -> None:
    seat_map = _read(REPO / "scripts" / "usage" / "seat_map.json")
    registry = {home: seat for home, seat in _bound_homes("Air-M5", Path("/h")).items()}
    by_machine = {
        str(Path("/h") / home[2:]): seat
        for home, seat in seat_map["by_machine"]["Air-M5"]["codex_homes"].items()
    }
    assert by_machine == registry
    air = _read(MAPS["Air-M5"])["providers"]["openai"]
    assert list(registry.values()) == air["canonical_roster"]
    assert "O3" not in seat_map["codex_homes"].values()  # the Pro/Mini fallback
    assert [
        m
        for m, b in seat_map["by_machine"].items()
        if "O3" in b["codex_homes"].values()
    ] == ["Air-M5"]
    for machine in ("Pro", "Mini"):
        assert (
            "O3" not in _read(MAPS[machine])["providers"]["openai"]["canonical_roster"]
        )
        assert "O3" not in {
            seat
            for seat, slot in _read(FLEET)["accounts"]["openai"]["slots"].items()
            if machine in slot["codex_home_by_machine"]
        }


def _enumerated_seats(
    tmp_path: Path, dirs: list[str], seat_by_dir: dict[str, str]
) -> list[str]:
    for name in dirs:
        (tmp_path / name).mkdir()
        (tmp_path / name / "auth.json").write_text("{}", encoding="utf-8")
    out = subprocess.run(
        ["sh", "-c", f'. "{CODEX_SEAT_LIB}"; codex_seat_dirs'],
        capture_output=True,
        text=True,
        env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
        timeout=60,
        check=True,
    ).stdout.split()
    return [seat_by_dir[Path(line).name] for line in out]


def test_declared_auto_rotation_order_matches_codex_seat_enumeration(
    tmp_path: Path,
) -> None:
    air_dirs = {
        Path(home).name: seat
        for home, seat in _bound_homes("Air-M5", Path("/h")).items()
    }
    air = _read(MAPS["Air-M5"])["providers"]["openai"]
    (tmp_path / "m5").mkdir()
    got = _enumerated_seats(tmp_path / "m5", list(air_dirs), air_dirs)
    assert got == air["auto_rotation_order"] == ["O1", "O2", "O3"]

    pro_dirs = {".codex": "O1", ".codex-acct2": "O2"}
    (tmp_path / "pro").mkdir()
    got = _enumerated_seats(tmp_path / "pro", list(pro_dirs), pro_dirs)
    assert got == _read(MAPS["Pro"])["providers"]["openai"]["auto_rotation_order"]
    assert _read(MAPS["Mini"])["providers"]["openai"]["auto_rotation_order"] == [
        "O1",
        "O2",
    ]


def test_claude_profiles_and_headless_oauth_slots_stay_unmapped() -> None:
    for path in MAPS.values():
        surface = _read(path)["providers"]["anthropic"]["headless_oauth_surface"]
        assert surface == {
            "relationship_to_profiles": "separate-surface",
            "logical_seat_mapping": "unverified",
        }
