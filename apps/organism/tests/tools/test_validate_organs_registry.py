"""Tests for `organism.tools.validate_organs_registry`.

The validator parses an organs registry YAML file (the Innervation Genoma
— file renamed 2026-05-08 IG-3 from `genome.yaml` to `organs_registry.yaml`),
enforces schema/enum/dep/checksum invariants, and returns a list of
validation errors. Tests cover the 8 classes of failure documented in
07_innervation_protocol.md §2.3 plus a happy-path baseline.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from organism.tools import validate_organs_registry as vg


# ---------- helpers ----------------------------------------------------------


def _minimal_organ(**overrides) -> dict:
    base = {
        "id": "test.organ_one",
        "runtime": "pro_launchd",
        "type": "cron",
        "expected_hb_seconds": 60,
        "owner_module": "test/path.py",
        "dependencies": [],
        "recovery_action": "launchctl_kickstart",
        "recovery_params": {"label": "com.example"},
        "severity_on_silence": "warning",
        "cicatrix_refs": [],
    }
    base.update(overrides)
    return base


def _write_genome(path: Path, organs: list[dict], *, checksum: str | None = "") -> None:
    doc: dict = {
        "version": 1,
        "checksum_algo": "sha256",
        "checksum": checksum if checksum is not None else "",
        "organs": organs,
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


# ---------- happy path -------------------------------------------------------


def test_happy_path_4_organs_no_errors(tmp_path):
    """A well-formed file with 4 organs and a correct checksum returns []."""
    organs = [
        _minimal_organ(id="a.one"),
        _minimal_organ(id="a.two", dependencies=["a.one"]),
        _minimal_organ(id="a.three", dependencies=["a.two"]),
        _minimal_organ(id="a.four", dependencies=["a.one", "a.three"]),
    ]
    p = tmp_path / "genome.yaml"
    _write_genome(p, organs, checksum="")
    correct = vg.compute_checksum(organs)
    _write_genome(p, organs, checksum=correct)

    errors = vg.validate_file(p)
    assert errors == []


# ---------- 8 failure classes ------------------------------------------------


def test_duplicate_id_is_rejected(tmp_path):
    """Two organs sharing the same id is a hard error."""
    organs = [
        _minimal_organ(id="dup.one"),
        _minimal_organ(id="dup.one"),  # duplicate
    ]
    p = tmp_path / "genome.yaml"
    _write_genome(p, organs, checksum=vg.compute_checksum(organs))

    errors = vg.validate_file(p)
    assert any("duplicate id" in e.lower() for e in errors)
    assert any("dup.one" in e for e in errors)


def test_invalid_runtime_enum_is_rejected(tmp_path):
    """`runtime` must be one of the 8 documented runtimes."""
    organs = [_minimal_organ(runtime="not_a_runtime")]
    p = tmp_path / "genome.yaml"
    _write_genome(p, organs, checksum=vg.compute_checksum(organs))

    errors = vg.validate_file(p)
    assert any("invalid runtime" in e.lower() for e in errors)
    assert any("not_a_runtime" in e for e in errors)


def test_invalid_type_enum_is_rejected(tmp_path):
    """`type` must be one of the 6 documented organ types."""
    organs = [_minimal_organ(type="not_a_type")]
    p = tmp_path / "genome.yaml"
    _write_genome(p, organs, checksum=vg.compute_checksum(organs))

    errors = vg.validate_file(p)
    assert any("invalid type" in e.lower() for e in errors)


def test_dependency_pointing_to_nonexistent_organ_is_rejected(tmp_path):
    """Dependencies must resolve to organ ids in the same file."""
    organs = [_minimal_organ(id="x.one", dependencies=["x.does_not_exist"])]
    p = tmp_path / "genome.yaml"
    _write_genome(p, organs, checksum=vg.compute_checksum(organs))

    errors = vg.validate_file(p)
    assert any("unknown dependency" in e.lower() for e in errors)
    assert any("x.does_not_exist" in e for e in errors)


def test_cyclic_dependencies_are_rejected(tmp_path):
    """Cycle a → b → a must be flagged (DAG invariant)."""
    organs = [
        _minimal_organ(id="cyc.a", dependencies=["cyc.b"]),
        _minimal_organ(id="cyc.b", dependencies=["cyc.a"]),
    ]
    p = tmp_path / "genome.yaml"
    _write_genome(p, organs, checksum=vg.compute_checksum(organs))

    errors = vg.validate_file(p)
    assert any("cycle" in e.lower() for e in errors)


def test_bad_checksum_is_rejected(tmp_path):
    """A non-empty checksum that does NOT match canonical SHA256 is rejected."""
    organs = [_minimal_organ(id="cs.one")]
    p = tmp_path / "genome.yaml"
    _write_genome(p, organs, checksum="deadbeef" * 8)  # 64 hex chars but wrong

    errors = vg.validate_file(p)
    assert any("checksum mismatch" in e.lower() for e in errors)


def test_missing_required_field_is_rejected(tmp_path):
    """An organ missing `recovery_action` is rejected (every required field)."""
    bad = _minimal_organ()
    del bad["recovery_action"]
    organs = [bad]
    p = tmp_path / "genome.yaml"
    # checksum computed on what's actually written so checksum check doesn't
    # mask the missing-field error
    _write_genome(p, organs, checksum=vg.compute_checksum(organs))

    errors = vg.validate_file(p)
    assert any(
        "missing required field" in e.lower() and "recovery_action" in e
        for e in errors
    )


def test_bootstrap_mode_accepts_empty_checksum(tmp_path):
    """`--bootstrap` mode tolerates checksum="" for the very first commit
    of genome.yaml (otherwise we have a chicken-and-egg problem)."""
    organs = [_minimal_organ(id="boot.one")]
    p = tmp_path / "genome.yaml"
    _write_genome(p, organs, checksum="")  # explicitly empty

    # default mode: rejects
    errors_strict = vg.validate_file(p, bootstrap=False)
    assert any("checksum" in e.lower() for e in errors_strict)

    # bootstrap mode: accepts (only checksum gripe is suppressed)
    errors_boot = vg.validate_file(p, bootstrap=True)
    assert errors_boot == []


# ---------- compute_checksum is itself stable -------------------------------


def test_compute_checksum_is_canonical_and_stable(tmp_path):
    """Same logical content ⇒ same checksum, regardless of dict key order."""
    o1 = _minimal_organ(id="z.one")
    o2 = _minimal_organ(id="z.one")
    # reorder the keys: same data, different yaml-text representation
    reordered = {k: o2[k] for k in sorted(o2.keys())}
    h1 = vg.compute_checksum([o1])
    h2 = vg.compute_checksum([reordered])
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex length


# ---------- live organs_registry.yaml integration --------------------------


_LIVE_GENOME = (
    Path(__file__).resolve().parents[2] / "organism" / "organs_registry.yaml"
)


def test_live_organs_registry_is_valid():
    """The repo's organs_registry.yaml (Innervation Genoma) must always
    validate clean — guards against accidental schema drift in PRs that
    touch the live registry. Renamed from test_live_genome_is_valid 2026-05-08
    (IG-3) to match the file rename `genome.yaml` → `organs_registry.yaml`.
    """
    assert _LIVE_GENOME.exists(), f"missing {_LIVE_GENOME}"
    errors = vg.validate_file(_LIVE_GENOME)
    assert errors == [], f"live organs_registry failed validation: {errors}"


@pytest.mark.parametrize(
    "organ_id",
    ["wr2.supervisor", "wr2.oracle", "wr2.newsletter"],
)
def test_w1_4_wr2_core_organi_enrolled(organ_id):
    """W1.4 enrolls the WR2 core trio. Each entry must:
    - exist in the live genome
    - declare bridge_source.type == state_file
    - have severity_on_silence == 'warning' (sidecar emission deferred to W2 —
      until then the sensor sees a missing file → silent → don't page Zero)
    """
    doc = yaml.safe_load(_LIVE_GENOME.read_text())
    by_id = {o["id"]: o for o in doc["organs"]}
    assert organ_id in by_id, f"{organ_id} not enrolled in live genome"
    organ = by_id[organ_id]
    assert "bridge_source" in organ, f"{organ_id} missing bridge_source"
    assert organ["bridge_source"]["type"] == "state_file"
    assert organ["severity_on_silence"] == "warning", (
        f"{organ_id}: until the wrapper emits sidecars (W2), severity must be "
        f"'warning' — 'critical' here would page on every Cell pulse"
    )


def test_w1_5_organism_control_panel_enrolled():
    """W1.5 enrolls the organism control-panel HTTP daemon (already
    KeepAlive=true on Pro :1819) with an http bridge that hits its own
    /health endpoint. Severity=critical: if the control panel itself
    is down, /pause and /resume are unreachable — Zero loses the
    blackout escape hatch.
    """
    doc = yaml.safe_load(_LIVE_GENOME.read_text())
    by_id = {o["id"]: o for o in doc["organs"]}
    assert "pro.organism_control_panel" in by_id, (
        "pro.organism_control_panel not enrolled in live genome"
    )
    organ = by_id["pro.organism_control_panel"]
    assert organ["type"] == "daemon"
    assert organ["recovery_action"] == "launchctl_kickstart"
    assert organ["recovery_params"]["label"] == "com.nuzantara.organism.control-panel"
    assert organ["severity_on_silence"] == "critical"
    bridge = organ["bridge_source"]
    assert bridge["type"] == "http"
    assert bridge["path"] == "http://127.0.0.1:1819/health"
    assert bridge["timestamp_field"] == "ts"


# ---------- Symbiosis W1: mini_launchd runtime allowlist --------------------


def test_mini_launchd_is_an_allowed_runtime():
    """`mini_launchd` must be in the runtime allowlist (Modo B 2-node topology).

    Decision D1 from PR #479 (Symbiosis Turn-On Plan, 2026-05-06): organs
    running on Mini-Pro2.local need their own runtime tag so the Supervisor
    can route recovery to remote launchctl via the Tailscale alias
    `mini-remote` instead of attempting a (wrong) local kickstart.
    """
    assert "mini_launchd" in vg._RUNTIMES


def test_validate_data_accepts_mini_launchd_runtime(tmp_path):
    """An organ with runtime=mini_launchd must validate cleanly."""
    organs = [_minimal_organ(id="mini.test_organ", runtime="mini_launchd")]
    p = tmp_path / "genome.yaml"
    _write_genome(p, organs, checksum=vg.compute_checksum(organs))

    errors = vg.validate_file(p)
    assert errors == []


def test_validate_data_rejects_unknown_runtime(tmp_path):
    """A runtime outside the allowlist must still be rejected — this guards
    against accidental allowlist erosion when adding mini_launchd."""
    organs = [_minimal_organ(id="bogus.organ", runtime="plan9_rcd")]
    p = tmp_path / "genome.yaml"
    _write_genome(p, organs, checksum=vg.compute_checksum(organs))

    errors = vg.validate_file(p)
    assert any("invalid runtime" in e.lower() and "plan9_rcd" in e for e in errors)


# ---------- Symbiosis W1.5: 9 MISS CRITICI organi (issue #490) -------------


class TestW1_5MissCritici:
    """Wave 1.5 follow-up to PR #488 W1. Enrolls 9 organi flagged as MISS
    CRITICI in the W1 tri-LLM cross-check (Federation A2A bridge,
    auto-healing observatory, publishing pipeline tail, Lamarckian
    feedback distillation). Registry expanded 78 → 87.

    Issue: https://github.com/Balizero1987/Teman2/issues/490
    Design: docs/superpowers/specs/2026-05-07-symbiosis-w1.5-miss-critici-design.md
    """

    @staticmethod
    def _live_organs_by_id() -> dict:
        doc = yaml.safe_load(_LIVE_GENOME.read_text())
        return {o["id"]: o for o in doc["organs"]}

    def test_w1_5_nlm_bridge_enrolled(self):
        """`nlm.bridge` is the Federation v3 A2A Agent 8 (uvicorn :18790).
        critical severity because async multi-doc synthesis fails silently
        when the bridge is down. NO bridge_source declared — empirical
        check (Codex 2026-05-07): live endpoint is `/nlm/health` and
        `HealthResponse` does not include a `ts` field, so an http bridge
        would permanently read as `error: missing timestamp field 'ts'`.
        Heartbeat-staleness fallback covers observability until a sidecar
        emitter ships in a future PR.
        """
        by_id = self._live_organs_by_id()
        assert "nlm.bridge" in by_id, "nlm.bridge not enrolled in live genome"
        organ = by_id["nlm.bridge"]
        assert organ["runtime"] == "pro_launchd"
        assert organ["type"] == "daemon"
        assert organ["recovery_action"] == "launchctl_kickstart"
        assert organ["recovery_params"]["label"] == "com.balizero.nlm-bridge"
        assert organ["severity_on_silence"] == "critical"
        assert organ["dependencies"] == ["infra.postgres"]
        assert "bridge_source" not in organ, (
            "nlm.bridge intentionally omits bridge_source — see design D7. "
            "/nlm/health does not emit `ts`, so an http bridge would "
            "permanently read as 'missing timestamp field' error."
        )

    def test_w1_5_cell_observatory_triplet_enrolled(self):
        """The cell-observatory family: 1 daemon (`cell.observatory`) +
        2 self-maintenance crons (`*_prune` daily, `*_selfcheck` 5-min).
        The daemon mirrors the cell.organism pattern with state_file
        bridge. Empirical correction (Codex 2026-05-07): cell-observatory
        depends on PG + SQLite + classifier API — no Redis path. Removed
        from the dependency list vs initial draft.
        """
        by_id = self._live_organs_by_id()
        # Daemon
        assert "cell.observatory" in by_id, "cell.observatory not enrolled"
        daemon = by_id["cell.observatory"]
        assert daemon["type"] == "daemon"
        assert daemon["severity_on_silence"] == "critical"
        assert daemon["recovery_params"]["label"] == "com.nuzantara.cell-observatory"
        assert daemon["bridge_source"]["type"] == "state_file"
        assert "infra.postgres" in daemon["dependencies"]
        assert "infra.redis" not in daemon["dependencies"], (
            "cell.observatory uses PG LISTEN + SQLite + classifier API "
            "(no Redis path in collector). Adding infra.redis misstates "
            "the blast radius."
        )

        # Prune cron (daily 04:00)
        assert "cell.observatory_prune" in by_id, "cell.observatory_prune not enrolled"
        prune = by_id["cell.observatory_prune"]
        assert prune["type"] == "cron"
        assert prune["expected_hb_seconds"] == 90000  # daily + 1h grace
        assert prune["severity_on_silence"] == "warning"

        # Selfcheck cron (5-min)
        assert "cell.observatory_selfcheck" in by_id, "cell.observatory_selfcheck not enrolled"
        selfcheck = by_id["cell.observatory_selfcheck"]
        assert selfcheck["type"] == "cron"
        assert selfcheck["expected_hb_seconds"] == 3900  # 300s + 1h grace
        assert "cell.observatory" in selfcheck["dependencies"]

    def test_w1_5_post_publish_poller_enrolled(self):
        """`pro.post_publish_poller` is the final pipeline motor (SEO +
        Fireworks Flux.1 cover + git push). Severity=error because when
        down, mouth articles get stuck mid-flow, but upstream WR2 chain
        can be replayed once restored.
        """
        by_id = self._live_organs_by_id()
        assert "pro.post_publish_poller" in by_id, (
            "pro.post_publish_poller not enrolled in live genome"
        )
        organ = by_id["pro.post_publish_poller"]
        assert organ["runtime"] == "pro_launchd"
        assert organ["type"] == "cron"
        assert organ["severity_on_silence"] == "error"
        assert organ["recovery_action"] == "launchctl_kickstart"
        assert organ["recovery_params"]["label"] == "com.balizero.post-publish-poller"
        assert "infra.postgres" in organ["dependencies"]

    def test_w1_5_sota_m13_quartet_enrolled(self):
        """The 4 sota.m13_* organi are the Lamarckian feedback distillation
        loop (post_metrics_history). All 4 are crons under wr2.supervisor;
        each has expected_hb_seconds matching its schedule."""
        by_id = self._live_organs_by_id()

        expected = {
            # id: (expected_hb_seconds, severity)
            "sota.m13_checkpoint": (90000, "warning"),     # daily 09:00
            "sota.m13_collect":    (90000, "warning"),     # RunAtLoad — treat as daily
            "sota.m13_monthly":    (2678400, "info"),      # monthly day-1 04:30
            "sota.m13_weekly":     (691200, "warning"),    # weekly Sun 06:00
        }
        for organ_id, (hb, severity) in expected.items():
            assert organ_id in by_id, f"{organ_id} not enrolled in live genome"
            organ = by_id[organ_id]
            assert organ["type"] == "cron", f"{organ_id} type should be 'cron'"
            assert organ["expected_hb_seconds"] == hb, (
                f"{organ_id} expected_hb_seconds={hb}, got {organ['expected_hb_seconds']}"
            )
            assert organ["severity_on_silence"] == severity, (
                f"{organ_id} severity_on_silence={severity}, got {organ['severity_on_silence']}"
            )
            assert "wr2.supervisor" in organ["dependencies"], (
                f"{organ_id} should depend on wr2.supervisor (cron wrapper supervises)"
            )
            assert "infra.postgres" in organ["dependencies"], (
                f"{organ_id} should depend on infra.postgres (post_metrics_history)"
            )


# ---------- Backward-compat shim (IG-3, 2026-05-08) -------------------------


def test_legacy_validate_genome_alias_warns_but_works():
    """The deprecated `validate_genome` alias (renamed to
    `validate_organs_registry` 2026-05-08 IG-3) must still re-export the
    public surface and emit a DeprecationWarning when imported. Removal
    scheduled 2026-06-08.
    """
    import importlib
    import warnings

    # Force a fresh import to capture the warning at module load.
    if "organism.tools.validate_genome" in list(__import__("sys").modules):
        del __import__("sys").modules["organism.tools.validate_genome"]

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        legacy = importlib.import_module("organism.tools.validate_genome")

    assert any(
        issubclass(w.category, DeprecationWarning)
        and "validate_organs_registry" in str(w.message)
        for w in caught
    ), "import of legacy alias must emit DeprecationWarning pointing at the new module"

    # Public surface is re-exported
    assert hasattr(legacy, "validate_file")
    assert hasattr(legacy, "compute_checksum")
    assert hasattr(legacy, "main")
    assert hasattr(legacy, "_RUNTIMES")  # used by tests historically


def test_legacy_genome_yaml_symlink_resolves_to_organs_registry(tmp_path):
    """The filesystem symlink `apps/organism/organism/genome.yaml` must point
    at the new file `organs_registry.yaml`, so existing scripts/cron jobs
    with the old hardcoded path keep reading the live registry without code
    changes. Removal scheduled 2026-06-08.
    """
    legacy = (
        Path(__file__).resolve().parents[2] / "organism" / "genome.yaml"
    )
    assert legacy.exists(), f"missing legacy alias symlink {legacy}"
    assert legacy.is_symlink(), "legacy alias must be a symlink, not a copy"
    target = legacy.resolve()
    assert target.name == "organs_registry.yaml", (
        f"legacy symlink points at {target.name}, expected organs_registry.yaml"
    )
    # And reading via the legacy path must produce the same bytes.
    new = (
        Path(__file__).resolve().parents[2] / "organism" / "organs_registry.yaml"
    )
    assert legacy.read_bytes() == new.read_bytes()
