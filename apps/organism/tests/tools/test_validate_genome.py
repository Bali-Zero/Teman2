"""Tests for `organism.tools.validate_genome`.

The validator parses a Genoma YAML file, enforces schema/enum/dep/checksum
invariants, and returns a list of validation errors. Tests cover the 8
classes of failure documented in 07_innervation_protocol.md §2.3 plus a
happy-path baseline.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from organism.tools import validate_genome as vg


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


# ---------- live genome.yaml integration ------------------------------------


_LIVE_GENOME = (
    Path(__file__).resolve().parents[2] / "organism" / "genome.yaml"
)


def test_live_genome_is_valid():
    """The repo's genome.yaml must always validate clean — guards against
    accidental schema drift in PRs that touch the live registry."""
    assert _LIVE_GENOME.exists(), f"missing {_LIVE_GENOME}"
    errors = vg.validate_file(_LIVE_GENOME)
    assert errors == [], f"live genome failed validation: {errors}"


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
