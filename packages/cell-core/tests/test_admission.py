"""Tests for the 7 Leggi admission test framework — Sprint 0 Track C1.

Sprint 1 W1 added:
- ``load_cell_definition`` (YAML / JSON loader)
- intel-scraper-cell admission test against the on-disk cell.yaml
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cell_core.admission_test import (
    AdmissionTest,
    CellDefinitionLoadError,
    Legge,
    load_cell_definition,
)


# Repo root (cell.yaml lives at <repo>/apps/bali-intel-scraper/cell.yaml)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_INTEL_SCRAPER_CELL_YAML = (
    _REPO_ROOT / "apps" / "bali-intel-scraper" / "cell.yaml"
)


def _passing_cell() -> dict:
    """Minimal cell definition that passes all 7 Leggi."""
    return {
        "name": "system-doctor-cell",
        "level": "L1",
        "exposes_gui": False,
        "llm_invocation": "ollama",
        "external_sources": ["fly-api"],
        "client_data_access": False,
        "publishes_via": "pg_notify",
        "fallback_modes": ["redis_down", "llm_provider_down"],
        "kill_switch": True,
        "auto_publishes": False,
        "depends_on_other_cell_decisions": False,
        "metrics": ["ttr", "error_rate", "throughput"],
    }


def test_passing_cell_passes_all_seven_laws() -> None:
    cell = _passing_cell()
    result = AdmissionTest().run_all(cell)
    assert result.passed is True, result.summary()
    assert result.cell_name == "system-doctor-cell"
    blockers = [v for v in result.violations if v.severity == "blocker"]
    assert blockers == [], f"expected no blockers, got: {blockers}"


def test_cli_only_blocks_gui_exposure() -> None:
    """A cell that exposes a GUI fails Law 1 (CLI-only)."""
    cell = _passing_cell()
    cell["exposes_gui"] = True
    result = AdmissionTest().run_all(cell)
    assert result.passed is False
    blockers = [v for v in result.violations if v.severity == "blocker"]
    assert any(v.legge == Legge.CLI_ONLY for v in blockers), result.summary()


def test_osint_blindato_blocks_external_plus_client() -> None:
    """A cell that mixes OSINT external sources with client PII access fails Law 2."""
    cell = _passing_cell()
    cell["external_sources"] = ["intel-scraper"]
    cell["client_data_access"] = True
    result = AdmissionTest().run_all(cell)
    assert result.passed is False
    osint_violations = [
        v for v in result.violations
        if v.legge == Legge.OSINT_BLINDATO and v.severity == "blocker"
    ]
    assert osint_violations, result.summary()


def test_event_driven_blocks_filesystem_publish() -> None:
    """A cell that publishes via filesystem fails Law 3 (Event-driven)."""
    cell = _passing_cell()
    cell["publishes_via"] = "filesystem"
    result = AdmissionTest().run_all(cell)
    assert result.passed is False
    event_violations = [
        v for v in result.violations
        if v.legge == Legge.EVENT_DRIVEN and v.severity == "blocker"
    ]
    assert event_violations, result.summary()


def test_local_sovereignty_blocks_dependency_on_other_cell_decisions() -> None:
    """A cell whose decisions depend on another cell's reasoning fails Law 6.

    Example: a hypothetical 'oracle L4 cell' that bypassed war-room — DeepSeek
    round-2 risk callout. The right classification for such a unit is
    'organelle inside the parent cell', not a free-standing cell.
    """
    cell = _passing_cell()
    cell["name"] = "oracle-bypass-attempt"
    cell["depends_on_other_cell_decisions"] = True
    result = AdmissionTest().run_all(cell)
    assert result.passed is False
    local_violations = [
        v for v in result.violations
        if v.legge == Legge.LOCAL_SOVEREIGNTY and v.severity == "blocker"
    ]
    assert local_violations, result.summary()


def test_numbers_first_blocks_under_three_metrics() -> None:
    """A cell that declares fewer than 3 metrics fails Law 7."""
    cell = _passing_cell()
    cell["metrics"] = ["ttr"]
    result = AdmissionTest().run_all(cell)
    assert result.passed is False
    numbers_violations = [
        v for v in result.violations
        if v.legge == Legge.NUMBERS_FIRST and v.severity == "blocker"
    ]
    assert numbers_violations, result.summary()


def test_summary_format_passing() -> None:
    cell = _passing_cell()
    result = AdmissionTest().run_all(cell)
    summary = result.summary()
    assert "PASS" in summary
    assert "system-doctor-cell" in summary
    assert "BLOCKER" not in summary


def test_summary_format_failing() -> None:
    cell = _passing_cell()
    cell["kill_switch"] = False
    result = AdmissionTest().run_all(cell)
    summary = result.summary()
    assert "FAIL" in summary
    assert "BLOCKER" in summary
    assert Legge.ZERO_FINAL_INSTANCE.value in summary


def test_graceful_degradation_blocks_no_fallbacks() -> None:
    """A cell with empty fallback_modes fails Law 4."""
    cell = _passing_cell()
    cell["fallback_modes"] = []
    result = AdmissionTest().run_all(cell)
    assert result.passed is False
    grace_violations = [
        v for v in result.violations
        if v.legge == Legge.GRACEFUL_DEGRADATION and v.severity == "blocker"
    ]
    assert grace_violations, result.summary()


# ── round-2 review fixes (4-LLM cross-review of PR #426) ──────────────


def test_registry_has_all_seven_leggi_populated() -> None:
    """Round-2 review (Claude): protect the 7 Leggi registry from a future
    refactor accidentally dropping a check. Without this assert, a missing
    check silently surfaces as a warning ("no check registered") and the
    cell still PASSES — defeating the point of the gate.
    """
    assert len(AdmissionTest.CHECKS) == 7
    assert set(AdmissionTest.CHECKS.keys()) == set(Legge)


def test_publishes_via_none_blocks_when_cell_class_is_cell() -> None:
    """Round-2 review (Claude/GPT-5.5): publishes_via='none' is reserved for
    substrate-only organelles. A cell setting it bypasses Law 3 entirely.
    Now blocks unless cell_class='organelle' is also declared.
    """
    cell = _passing_cell()
    cell["publishes_via"] = "none"   # cell_class defaults to 'cell'
    result = AdmissionTest().run_all(cell)
    assert result.passed is False
    event_violations = [
        v for v in result.violations
        if v.legge == Legge.EVENT_DRIVEN and v.severity == "blocker"
    ]
    assert event_violations, result.summary()


def test_publishes_via_none_passes_for_organelle() -> None:
    """A substrate-only organelle (e.g. pg-proxy) explicitly opts out of
    publishing — declaring cell_class='organelle' makes publishes_via='none'
    valid.
    """
    cell = _passing_cell()
    cell["name"] = "pg-proxy-organelle"
    cell["publishes_via"] = "none"
    cell["cell_class"] = "organelle"
    result = AdmissionTest().run_all(cell)
    assert result.passed is True, result.summary()


def test_publishes_via_unknown_value_blocks() -> None:
    """Round-2 review (Claude/GPT-5.5): unknown publishes_via values were
    only WARNING — silent admission. Now they BLOCK.
    """
    cell = _passing_cell()
    cell["publishes_via"] = "rabbitmq"   # not in allowlist
    result = AdmissionTest().run_all(cell)
    assert result.passed is False
    event_violations = [
        v for v in result.violations
        if v.legge == Legge.EVENT_DRIVEN and v.severity == "blocker"
    ]
    assert event_violations, result.summary()


def test_llm_invocation_anthropic_api_blocks() -> None:
    """Round-2 review (Gemini): Law 1 specifically bans the Anthropic paid
    API. Verify a cell declaring llm_invocation='anthropic_api' fails.
    """
    cell = _passing_cell()
    cell["llm_invocation"] = "anthropic_api"
    result = AdmissionTest().run_all(cell)
    assert result.passed is False
    cli_violations = [
        v for v in result.violations
        if v.legge == Legge.CLI_ONLY and v.severity == "blocker"
    ]
    assert cli_violations, result.summary()


def test_auto_publishes_true_blocks() -> None:
    """Round-2 review (Gemini/GPT-5.5): Law 5 forbids auto-publishing to
    externally-visible channels. Verify auto_publishes=True triggers a
    blocker even with kill_switch=True.
    """
    cell = _passing_cell()
    cell["auto_publishes"] = True   # kill_switch already True
    result = AdmissionTest().run_all(cell)
    assert result.passed is False
    zero_violations = [
        v for v in result.violations
        if v.legge == Legge.ZERO_FINAL_INSTANCE and v.severity == "blocker"
    ]
    assert zero_violations, result.summary()


# ── Sprint 1 W1: load_cell_definition + intel-scraper-cell admission ──


def test_load_cell_definition_json_round_trip(tmp_path: Path) -> None:
    """JSON round-trip — must produce the same dict that run_all() consumes."""
    cd = {
        "name": "json-cell",
        "level": "L1",
        "exposes_gui": False,
        "external_sources": ["fly-api"],
        "client_data_access": False,
        "publishes_via": "pg_notify",
        "fallback_modes": ["redis_down"],
        "kill_switch": True,
        "auto_publishes": False,
        "depends_on_other_cell_decisions": False,
        "metrics": ["a", "b", "c"],
    }
    p = tmp_path / "json-cell.json"
    p.write_text(json.dumps(cd))
    loaded = load_cell_definition(p)
    assert loaded == cd
    # And the loaded dict passes admission.
    assert AdmissionTest().run_all(loaded).passed is True


def test_load_cell_definition_missing_file_raises(tmp_path: Path) -> None:
    """FileNotFoundError surfaces — caller can decide whether to skip."""
    with pytest.raises(FileNotFoundError):
        load_cell_definition(tmp_path / "nope.yaml")


def test_load_cell_definition_root_not_mapping_raises(tmp_path: Path) -> None:
    """A list at the root of a JSON file fails loud."""
    p = tmp_path / "list.json"
    p.write_text(json.dumps(["not", "a", "dict"]))
    with pytest.raises(CellDefinitionLoadError):
        load_cell_definition(p)


def test_intel_scraper_cell_yaml_exists() -> None:
    """The Sprint 1 W1 cell.yaml MUST be on disk at the canonical path."""
    assert _INTEL_SCRAPER_CELL_YAML.exists(), (
        f"missing {_INTEL_SCRAPER_CELL_YAML} — Sprint 1 W1 declarative "
        f"contract not in place"
    )


def test_intel_scraper_cell_passes_admission() -> None:
    """The intel-scraper-cell definition PASSES all 7 Leggi (zero blockers).

    This is the canonical Sprint 1 W1 acceptance test. If it ever fails,
    either the cell definition drifted (fix cell.yaml) or the admission
    rubric changed (fix admission_test.py). Both deserve a code review.
    """
    pytest.importorskip("yaml", reason="cell.yaml requires PyYAML to load")
    cd = load_cell_definition(_INTEL_SCRAPER_CELL_YAML)
    result = AdmissionTest().run_all(cd)
    blockers = [v for v in result.violations if v.severity == "blocker"]
    assert blockers == [], (
        "intel-scraper-cell admission FAILED:\n" + result.summary()
    )
    assert result.passed is True, result.summary()
    assert result.cell_name == "intel-scraper-cell"


def test_intel_scraper_cell_metadata_contracts() -> None:
    """Cell-yaml-only contract checks (not part of the 7 Leggi).

    These are Sprint 1 W1 specific invariants that don't belong in the
    generic admission_test runtime check but DO belong in the cell's
    own test surface.
    """
    pytest.importorskip("yaml", reason="cell.yaml requires PyYAML to load")
    cd = load_cell_definition(_INTEL_SCRAPER_CELL_YAML)

    # Identity
    assert cd["name"] == "intel-scraper-cell"
    assert cd["level"] == "L1"
    assert cd["runtime"] == "cron-agent-python"

    # OSINT-blindato pre-declaration
    assert cd["client_data_access"] is False
    assert isinstance(cd["external_sources"], list)
    assert len(cd["external_sources"]) >= 3

    # Event contracts must include intel.scraper.run with the 8 declared fields
    contracts = cd.get("event_contracts", [])
    run_contracts = [c for c in contracts if c.get("name") == "intel.scraper.run"]
    assert len(run_contracts) == 1, (
        "exactly one intel.scraper.run contract expected"
    )
    fields = set(run_contracts[0].get("fields", {}).keys())
    required_fields = {
        "trace_id",
        "status",
        "sources_attempted",
        "articles_found",
        "scars_added",
        "duration_ms",
        "started_at",
        "finished_at",
    }
    missing = required_fields - fields
    assert not missing, f"intel.scraper.run contract missing fields: {missing}"

    # HGT publish policy: structural patterns only (UU PDP scope)
    assert cd.get("hgt_publish_only_structural_patterns") is True


def test_intel_scraper_cell_drift_blocks_when_fields_missing(tmp_path: Path) -> None:
    """Defensive: simulate cell.yaml drift (e.g. someone removes
    ``kill_switch``) and confirm admission FAILS with a clear blocker."""
    pytest.importorskip("yaml", reason="cell.yaml requires PyYAML to load")
    cd = load_cell_definition(_INTEL_SCRAPER_CELL_YAML)
    # Corrupted copy
    drifted = dict(cd)
    drifted["kill_switch"] = False   # operator removed the kill switch
    result = AdmissionTest().run_all(drifted)
    assert result.passed is False
    assert any(
        v.legge == Legge.ZERO_FINAL_INSTANCE and v.severity == "blocker"
        for v in result.violations
    ), result.summary()


# ── Sprint 1 W2 — hgt-coordinator-cell admission entry ────────────────────


def _hgt_coordinator_cell() -> dict:
    """Cell definition for the HGT coordinator quarantine layer.

    The coordinator is CLI-only (OpenClaw Kimi K2.6 invokes
    ``python -m cell_core.hgt_coordinator.cli observe`` — no GUI), reads
    Redis Stream cell:skills (substrate-only, OSINT blindato N/A — the
    stream is internal cell traffic, not external scraping), publishes
    NOTHING (it's a propose-only observer; consumer of cell:skills, NOT
    a producer of new pg_notify channels), degrades to [] when Redis is
    down, leaves Zero as final instance via the SQLite audit log
    (humans + Kimi review pending rows; no auto-merge), runs locally
    with SQLite per-machine (Local Sovereignty doctrine — JSONL
    canonical / SQLite per-machine outside git tree per ADR
    federation-bus.md), and declares ≥3 quantitative metrics.
    """
    return {
        "name": "hgt-coordinator-cell",
        "level": "L2",
        "exposes_gui": False,
        "llm_invocation": "none",  # python coordinator has no LLM call;
                                    # Kimi K2.6 OpenClaw agent runs
                                    # *outside* this cell and uses
                                    # OpenClaw OAuth/OpenRouter, not the
                                    # python module.
        "external_sources": [],     # cell:skills is internal substrate
        "client_data_access": False,
        "publishes_via": "consumer_only",  # observes cell:skills, writes
                                            # only to local SQLite — not
                                            # a pg_notify producer
        "fallback_modes": [
            "redis_down",            # → return [] + warning
            "sqlite_down",           # → propose_transfers raises;
                                     # CLI returns exit 2 transient
        ],
        "kill_switch": True,         # disable agent in openclaw.json
                                     # (sandbox.mode='off-disabled') OR
                                     # remove agent entry entirely
        "auto_publishes": False,     # propose-only — humans review via
                                     # `cli resolve --status …`
        "depends_on_other_cell_decisions": False,  # reads raw substrate
                                                    # (cell:skills); does
                                                    # NOT depend on any
                                                    # other cell's
                                                    # reasoning
        "metrics": [
            "proposals_emitted_per_run",
            "proposals_resolved_within_72h",
            "redis_read_latency_ms",
            "audit_log_row_count",
        ],
    }


def test_hgt_coordinator_cell_passes_admission() -> None:
    """Sprint 1 W2 — quarantine layer must pass all 7 Leggi.

    Reference: ``docs/cell-core/hgt-coordinator-quarantine.md`` §
    Quarantine Guarantees, ``packages/cell-core/cell_core/hgt_coordinator/__init__.py``
    docstring §, brainstorm round 2 § Q3.
    """
    cell = _hgt_coordinator_cell()
    result = AdmissionTest().run_all(cell)
    assert result.passed is True, result.summary()
    blockers = [v for v in result.violations if v.severity == "blocker"]
    assert blockers == [], (
        f"hgt-coordinator-cell must clear admission with zero blockers; got: "
        f"{[(v.legge.value, v.message) for v in blockers]}"
    )


# ── Sprint 3 W2 — crm-cell + mata-garuda-cell admission entries ───────────

_CRM_CELL_YAML = _REPO_ROOT / "apps" / "crm-cell" / "cell.yaml"
_MATA_GARUDA_CELL_YAML = _REPO_ROOT / "apps" / "mata-garuda" / "cell.yaml"


def test_crm_cell_yaml_exists() -> None:
    """The Sprint 3 W2 crm-cell.yaml MUST be on disk at the canonical path."""
    assert _CRM_CELL_YAML.exists(), (
        f"missing {_CRM_CELL_YAML} — Sprint 3 W2 declarative contract not in place"
    )


def test_crm_cell_passes_admission() -> None:
    """The crm-cell definition PASSES all 7 Leggi (zero blockers).

    Sprint 3 W2 acceptance test. If it ever fails, either the cell
    definition drifted (fix cell.yaml) or the admission rubric changed
    (fix admission_test.py). Both deserve a code review.

    Note: ``client_data_access=true`` IS valid for crm-cell — the cell IS
    the CRM client data domain (UU PDP scope). What Law 2 (OSINT blindato)
    forbids is the *combination* of OSINT external_sources AND client PII
    — CRM has neither OSINT scrapers nor any external_source on
    domains like ``intel-scraper`` (it has Drive/Brevo/WhatsApp/Telegram,
    which are non-OSINT integrations).
    """
    pytest.importorskip("yaml", reason="cell.yaml requires PyYAML to load")
    cd = load_cell_definition(_CRM_CELL_YAML)
    result = AdmissionTest().run_all(cd)
    blockers = [v for v in result.violations if v.severity == "blocker"]
    assert blockers == [], (
        "crm-cell admission FAILED:\n" + result.summary()
    )
    assert result.passed is True, result.summary()
    assert result.cell_name == "crm-cell"


def test_crm_cell_metadata_contracts() -> None:
    """Cell-yaml-only contract checks (Sprint 3 W2 invariants).

    v2.5 review V2-B2 fix: AdmissionTest Law 2 rubric is now
    default-deny via `_DELIVERY_CLASS_ALLOWLIST`. crm-cell legitimately
    mixes external_sources (Drive/Brevo/WhatsApp/Telegram — all in the
    allowlist) with client_data_access=true. Any future external_source
    name not in the allowlist will FAIL admission until added there
    via a dedicated code review.
    """
    pytest.importorskip("yaml", reason="cell.yaml requires PyYAML to load")
    cd = load_cell_definition(_CRM_CELL_YAML)

    # Identity
    assert cd["name"] == "crm-cell"
    assert cd["level"] == "L1"
    assert "fastapi-inproc" in cd["runtime"]

    # CRM IS the client data domain — UU PDP scope (Q4 W1.2 decision)
    assert cd["client_data_access"] is True
    # external_sources must be truthfully declared
    declared_sources = set(cd.get("external_sources", []))
    assert declared_sources, (
        "crm-cell must declare its actual external integrations, not []"
    )
    # …and ALL declared sources must be in the delivery allowlist
    # (default-deny posture; anything else = OSINT-class blocker).
    from cell_core.admission_test import _DELIVERY_CLASS_ALLOWLIST
    untrusted = declared_sources - _DELIVERY_CLASS_ALLOWLIST
    assert not untrusted, (
        f"crm-cell external_sources contains providers not in the "
        f"delivery allowlist: {sorted(untrusted)}. Either add them to "
        f"_DELIVERY_CLASS_ALLOWLIST or remove them from the cell."
    )
    # Expect the 4 declared delivery integrations
    expected_delivery = {
        "google_drive_api",
        "brevo_api",
        "whatsapp_business_api",
        "telegram_bot_api",
    }
    assert expected_delivery.issubset(declared_sources), (
        f"crm-cell must declare all 4 delivery integrations, got: "
        f"{declared_sources}"
    )

    # Outbound contract — crm_welcome_completed (mig 153) must be declared
    outbound = set(cd.get("events", {}).get("outbound", []))
    assert "crm_welcome_completed" in outbound, (
        "crm-cell must declare crm_welcome_completed in events.outbound "
        "(emitted by mig 153 trigger)"
    )

    # Pro-only sub-organelles per W1.2 Q3 (Drive page_token persistence)
    suborganelles = {s["name"] for s in cd.get("sub_organelles", [])}
    assert "drive_poll" in suborganelles
    assert "nightly_engine" in suborganelles


def test_unknown_external_source_blocks_with_client_data() -> None:
    """v2.5 review V2-B2: default-deny posture. A cell that declares
    an external_source NOT in `_DELIVERY_CLASS_ALLOWLIST` AND has
    client_data_access=true MUST fail admission. Catches the security
    regression where the v2 blocklist would have silently allowed
    unknown providers.
    """
    cell = _passing_cell()
    cell["external_sources"] = ["unknown_new_scraper.example.com"]
    cell["client_data_access"] = True
    result = AdmissionTest().run_all(cell)
    assert result.passed is False
    osint_violations = [
        v for v in result.violations
        if v.legge == Legge.OSINT_BLINDATO and v.severity == "blocker"
    ]
    assert osint_violations, (
        "default-deny posture: an unknown external_source combined with "
        "client_data_access=true MUST block admission, even if the "
        "name doesn't match any known OSINT provider"
    )
    # The error message must point the author at the allowlist constant
    msg = osint_violations[0].message
    assert "_DELIVERY_CLASS_ALLOWLIST" in msg, (
        f"violation message must mention _DELIVERY_CLASS_ALLOWLIST so "
        f"the cell author knows where to add new delivery providers; "
        f"got: {msg!r}"
    )


def test_delivery_allowlist_with_client_data_passes() -> None:
    """v2.5 review V2-B2: a cell with ONLY delivery-allowlisted
    external_sources AND client_data_access=true MUST pass admission.
    This is the legitimate crm-cell case.
    """
    cell = _passing_cell()
    cell["external_sources"] = [
        "google_drive_api", "brevo_api", "whatsapp_business_api",
    ]
    cell["client_data_access"] = True
    result = AdmissionTest().run_all(cell)
    osint_violations = [
        v for v in result.violations
        if v.legge == Legge.OSINT_BLINDATO and v.severity == "blocker"
    ]
    assert not osint_violations, (
        f"delivery-only external_sources + client_data should pass; "
        f"got Law 2 violations: {[v.message for v in osint_violations]}"
    )


def test_mata_garuda_cell_yaml_exists() -> None:
    """The Sprint 3 W2 mata-garuda-cell.yaml MUST be on disk."""
    assert _MATA_GARUDA_CELL_YAML.exists(), (
        f"missing {_MATA_GARUDA_CELL_YAML} — Sprint 3 W2 declarative "
        f"contract not in place"
    )


def test_mata_garuda_cell_passes_admission() -> None:
    """The mata-garuda-cell definition PASSES all 7 Leggi (zero blockers).

    Sprint 3 W2 acceptance test. Mata-Garuda is L4.5 (meta-awareness)
    rather than L1; the admission rubric does not gate on level value
    — it gates on the 7 Leggi declarations themselves. OSINT blindato
    is satisfied because external_sources=[] (no inbound cloud) and
    client_data_access=False.
    """
    pytest.importorskip("yaml", reason="cell.yaml requires PyYAML to load")
    cd = load_cell_definition(_MATA_GARUDA_CELL_YAML)
    result = AdmissionTest().run_all(cd)
    blockers = [v for v in result.violations if v.severity == "blocker"]
    assert blockers == [], (
        "mata-garuda-cell admission FAILED:\n" + result.summary()
    )
    assert result.passed is True, result.summary()
    assert result.cell_name == "mata-garuda-cell"


def test_mata_garuda_cell_metadata_contracts() -> None:
    """Cell-yaml-only contract checks (Sprint 3 W2 invariants)."""
    pytest.importorskip("yaml", reason="cell.yaml requires PyYAML to load")
    cd = load_cell_definition(_MATA_GARUDA_CELL_YAML)

    # Identity — L4.5 meta-awareness
    assert cd["name"] == "mata-garuda-cell"
    assert cd["level"] == "L4.5"

    # OSINT blindato: zero external_sources, zero client_data_access
    assert cd["external_sources"] == [], (
        "mata-garuda-cell must have empty external_sources (OSINT blindato — "
        "Pro-local, no inbound cloud)"
    )
    assert cd["client_data_access"] is False, (
        "mata-garuda-cell must NOT touch CRM client data (separate from "
        "crm-cell domain)"
    )

    # Outbound contracts — both new channels declared
    outbound = set(cd.get("events", {}).get("outbound", []))
    assert "asset_provenance" in outbound, (
        "mata-garuda-cell must declare asset_provenance in events.outbound "
        "(emitted by mig 155 trigger)"
    )
    assert "asset_invalidated" in outbound, (
        "mata-garuda-cell must declare asset_invalidated in events.outbound "
        "(emitted by daily invalidation_sweeper sub-organelle)"
    )

    # Meta-awareness layer — cells observed must NOT include self
    meta = cd.get("meta_awareness", {})
    assert "self" in meta.get("does_not_observe", []), (
        "mata-garuda-cell.meta_awareness.does_not_observe must include 'self' "
        "to prevent feedback loop (cell adapter enforces this at runtime)"
    )

    # Sub-organelle: invalidation_sweeper at 04:13 WITA
    suborganelles = {s["name"]: s for s in cd.get("sub_organelles", [])}
    sweeper = suborganelles.get("invalidation_sweeper")
    assert sweeper is not None
    assert sweeper["schedule"] == "13 4 * * *", (
        f"invalidation_sweeper schedule must be '13 4 * * *' (daily 04:13 WITA, "
        f"off-minute off-hour), got {sweeper.get('schedule')!r}"
    )

    # Event contracts must include asset_provenance with all M2 + X5 fields
    contracts = cd.get("event_contracts", [])
    prov_contracts = [
        c for c in contracts if c.get("name") == "mata_garuda.asset_provenance"
    ]
    assert len(prov_contracts) == 1
    fields = set(prov_contracts[0].get("fields", {}).keys())
    required_m2_x5 = {
        "reliability",            # M2 admiralty
        "credibility",            # M2 admiralty
        "tlp",                    # M2 distribution control
        "valid_until",            # X5 invalidation column
        "invalidation_event_topic",  # X5 invalidation column
        "invalidation_mode",      # X5 invalidation enum
        "_outbox_id",             # mig 146 contract
    }
    missing = required_m2_x5 - fields
    assert not missing, (
        f"asset_provenance contract missing M2/X5 fields: {missing}"
    )
