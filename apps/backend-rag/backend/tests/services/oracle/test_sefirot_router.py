"""Tests for sefirot_router — curated multi-NB cascade resolver."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.services.oracle.sefirot_router import (
    SefirotPath,
    SefirotStep,
    _parse_paths,
    load_paths,
    match_triggers,
    resolve_path,
    resolve_with_fallback,
    sefirot_routing_enabled,
    summarize_paths,
)


# ── Flag reading ─────────────────────────────────────────────────────────────


def test_flag_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SEFIROT_ROUTING", raising=False)
    assert sefirot_routing_enabled() is False


def test_flag_accepts_truthy(monkeypatch: pytest.MonkeyPatch) -> None:
    for val in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("SEFIROT_ROUTING", val)
        assert sefirot_routing_enabled() is True, f"{val!r} should enable"


def test_flag_rejects_other_strings(monkeypatch: pytest.MonkeyPatch) -> None:
    for val in ("", "0", "false", "off", "nope"):
        monkeypatch.setenv("SEFIROT_ROUTING", val)
        assert sefirot_routing_enabled() is False, f"{val!r} should disable"


# ── YAML parser ──────────────────────────────────────────────────────────────


def test_parse_paths_drops_missing_name() -> None:
    raw = {
        "paths": [
            {"triggers": ["x"], "sequence": [{"nb": "uuid", "key": "nb1", "weight": 1.0}]},
        ]
    }
    assert _parse_paths(raw) == []


def test_parse_paths_drops_missing_triggers() -> None:
    raw = {
        "paths": [
            {"name": "x", "triggers": [], "sequence": [{"nb": "uuid", "key": "nb1", "weight": 1.0}]},
        ]
    }
    assert _parse_paths(raw) == []


def test_parse_paths_drops_missing_sequence() -> None:
    raw = {
        "paths": [
            {"name": "x", "triggers": ["t"], "sequence": []},
        ]
    }
    assert _parse_paths(raw) == []


def test_parse_paths_normalizes_triggers_to_lowercase() -> None:
    raw = {
        "paths": [
            {
                "name": "x",
                "triggers": ["PT PMA", "Mixed Case"],
                "sequence": [{"nb": "uuid", "key": "nb1", "weight": 1.0}],
            }
        ]
    }
    parsed = _parse_paths(raw)
    assert parsed[0].triggers == ["pt pma", "mixed case"]


def test_parse_paths_skips_step_missing_weight() -> None:
    raw = {
        "paths": [
            {
                "name": "x",
                "triggers": ["t"],
                "sequence": [
                    {"nb": "uuid1", "key": "nb1", "weight": 1.0},
                    {"nb": "uuid2", "key": "nb2"},  # missing weight → dropped
                ],
            }
        ]
    }
    parsed = _parse_paths(raw)
    assert len(parsed) == 1
    assert len(parsed[0].sequence) == 1
    assert parsed[0].sequence[0].key == "nb1"


def test_parse_paths_captures_aggregator_default() -> None:
    raw = {
        "paths": [
            {
                "name": "x",
                "triggers": ["t"],
                "sequence": [{"nb": "uuid", "key": "nb1", "weight": 1.0}],
            }
        ]
    }
    parsed = _parse_paths(raw)
    assert parsed[0].aggregator == "synthesis_ordered"


def test_parse_paths_preserves_deprecated_flag() -> None:
    raw = {
        "paths": [
            {
                "name": "x",
                "triggers": ["t"],
                "sequence": [{"nb": "uuid", "key": "nb1", "weight": 1.0}],
                "deprecated": True,
            }
        ]
    }
    parsed = _parse_paths(raw)
    assert parsed[0].deprecated is True


# ── match_triggers ───────────────────────────────────────────────────────────


def _fixture_path(
    triggers: list[str],
    sequence: list[tuple[str, str, float]],
    name: str = "test",
    deprecated: bool = False,
) -> SefirotPath:
    return SefirotPath(
        name=name,
        description="",
        triggers=[t.lower() for t in triggers],
        sequence=[SefirotStep(nb_id=nb, key=k, weight=w) for nb, k, w in sequence],
        aggregator="synthesis_ordered",
        deprecated=deprecated,
    )


def test_match_triggers_case_insensitive() -> None:
    p = _fixture_path(["pt pma"], [("uuid", "nb3", 1.0)])
    assert match_triggers("Open a PT PMA today", p) == ["pt pma"]
    assert match_triggers("PT PMA setup", p) == ["pt pma"]


def test_match_triggers_no_match_empty() -> None:
    p = _fixture_path(["kitas e23"], [("uuid", "nb2", 1.0)])
    assert match_triggers("property question", p) == []


def test_match_triggers_multiple_triggers_all_matched() -> None:
    p = _fixture_path(["pt pma", "foreign company"], [("uuid", "nb3", 1.0)])
    matched = match_triggers("Opening a foreign company as PT PMA", p)
    assert set(matched) == {"pt pma", "foreign company"}


def test_match_triggers_empty_query() -> None:
    p = _fixture_path(["pt pma"], [("uuid", "nb3", 1.0)])
    assert match_triggers("", p) == []


# ── resolve_path ─────────────────────────────────────────────────────────────


def test_resolve_path_first_match_wins() -> None:
    first = _fixture_path(["pt pma"], [("u1", "nb3", 1.0)], name="first")
    second = _fixture_path(["pma"], [("u2", "nb6", 1.0)], name="second")
    match = resolve_path("pt pma setup", paths=[first, second])
    assert match is not None
    assert match.name == "first"


def test_resolve_path_skips_deprecated() -> None:
    dep = _fixture_path(["pt pma"], [("u1", "nb3", 1.0)], name="old", deprecated=True)
    active = _fixture_path(["pt pma"], [("u2", "nb6", 1.0)], name="new")
    match = resolve_path("pt pma setup", paths=[dep, active])
    assert match is not None
    assert match.name == "new"


def test_resolve_path_returns_none_on_no_match() -> None:
    p = _fixture_path(["kitas e23"], [("u", "nb2", 1.0)])
    assert resolve_path("what's the weather?", paths=[p]) is None


def test_resolve_path_returns_none_on_empty_query() -> None:
    p = _fixture_path(["x"], [("u", "nb1", 1.0)])
    assert resolve_path("", paths=[p]) is None


# ── notebook_ids_in_order ────────────────────────────────────────────────────


def test_notebook_ids_ordered_by_weight_desc() -> None:
    p = _fixture_path(
        ["x"],
        [("u_low", "nb4", 0.3), ("u_high", "nb3", 1.0), ("u_mid", "nb2", 0.6)],
    )
    assert p.notebook_ids_in_order() == ["u_high", "u_mid", "u_low"]
    assert p.matched_keys_in_order() == ["nb3", "nb2", "nb4"]


# ── resolve_with_fallback + shadow mode ──────────────────────────────────────


def test_resolve_with_fallback_flag_off_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SEFIROT_ROUTING", raising=False)
    p = _fixture_path(["pt pma"], [("u", "nb3", 1.0)])
    # Path matches, flag off → None (shadow mode)
    assert resolve_with_fallback("pt pma setup", paths=[p]) is None


def test_resolve_with_fallback_flag_on_returns_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEFIROT_ROUTING", "1")
    p = _fixture_path(["pt pma"], [("u", "nb3", 1.0)], name="pt_pma_flow")
    match = resolve_with_fallback("pt pma setup", paths=[p])
    assert match is not None
    assert match.name == "pt_pma_flow"


def test_resolve_with_fallback_no_match_returns_none_regardless_of_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = _fixture_path(["kitas"], [("u", "nb2", 1.0)])
    monkeypatch.delenv("SEFIROT_ROUTING", raising=False)
    assert resolve_with_fallback("unrelated query", paths=[p]) is None
    monkeypatch.setenv("SEFIROT_ROUTING", "1")
    assert resolve_with_fallback("unrelated query", paths=[p]) is None


def test_resolve_with_fallback_shadow_logs_when_off(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("SEFIROT_ROUTING", raising=False)
    p = _fixture_path(["pt pma"], [("u", "nb3", 1.0)], name="pt_pma_flow")
    with caplog.at_level("INFO", logger="backend.services.oracle.sefirot_router"):
        resolve_with_fallback("pt pma setup", paths=[p])
    # Expect one shadow log line
    assert any("sefirot shadow" in record.message for record in caplog.records)


# ── load_paths (real file) ───────────────────────────────────────────────────


def test_load_real_yaml_has_entries() -> None:
    paths = load_paths(force_reload=True)
    assert len(paths) >= 10


def test_load_real_yaml_has_expected_pma_flow() -> None:
    paths = load_paths(force_reload=True)
    names = {p.name for p in paths}
    assert "pt_pma_complete_flow" in names
    assert "property_foreigner_acquisition" in names
    assert "kitas_e23_work_permit_full" in names


def test_load_real_yaml_all_sequences_nonempty() -> None:
    paths = load_paths(force_reload=True)
    for p in paths:
        assert len(p.sequence) >= 1, f"path {p.name} has empty sequence"
        assert len(p.triggers) >= 1, f"path {p.name} has no triggers"


def test_load_real_yaml_all_weights_in_range() -> None:
    paths = load_paths(force_reload=True)
    for p in paths:
        for s in p.sequence:
            assert 0.0 <= s.weight <= 1.0, f"{p.name}/{s.key} weight {s.weight} out of range"


def test_load_missing_file_returns_empty(tmp_path: Path) -> None:
    paths = load_paths(path=tmp_path / "nonexistent.yaml", force_reload=True)
    assert paths == []


def test_load_malformed_yaml_returns_empty(tmp_path: Path) -> None:
    f = tmp_path / "bad.yaml"
    f.write_text("this is: {not valid: yaml: at all")
    paths = load_paths(path=f, force_reload=True)
    assert paths == []


# ── summary ──────────────────────────────────────────────────────────────────


def test_summarize_real_yaml_shape() -> None:
    s = summarize_paths()
    assert s["active_paths"] >= 10
    assert "nb2" in s["distinct_nbs_in_use"]
    assert s["triggers_total"] >= 30


# ── Integration: real PT PMA query resolves correctly ────────────────────────


def test_integration_pt_pma_query_returns_5_nb_cascade(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEFIROT_ROUTING", "1")
    paths = load_paths(force_reload=True)
    match = resolve_with_fallback("I want to open a PT PMA with team in Bali", paths=paths)
    assert match is not None
    assert match.name == "pt_pma_complete_flow"
    keys = match.matched_keys_in_order()
    # Primary is nb3, followed by a cascade
    assert keys[0] == "nb3"
    assert "nb2" in keys
    assert "nb10" in keys
    assert "nb4" in keys
