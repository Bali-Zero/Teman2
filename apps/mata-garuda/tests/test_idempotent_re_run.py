"""Tests for idempotent APOPTOSIS re-run + crash-safety."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _import_apo():
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import execute_apoptosis  # type: ignore[import-not-found]
    return execute_apoptosis


@pytest.fixture
def tmp_registry(tmp_path, monkeypatch):
    """Redirect _registry_data.py target + AUDIT_LOG to tmp files.

    W18 (2026-05-22): without env-var redirect, run_apoptosis() appended
    one row per UUID to the real research/nb-archive/audit_log.md on every
    test invocation (~17/run x 5 tests), drifting the file. AUDIT_LOG is
    now `Path(os.environ["APOPTOSIS_AUDIT_LOG"])` if the var is set; tests
    set it to tmp_path. Also patches in-memory `apo.AUDIT_LOG` for runs
    that import the module before the env var is read.
    """
    apo = _import_apo()
    fake_target = tmp_path / "_registry_data.py"
    fake_audit = tmp_path / "audit_log.md"
    monkeypatch.setenv("APOPTOSIS_AUDIT_LOG", str(fake_audit))
    monkeypatch.setattr(apo, "REGISTRY_TARGET", fake_target)
    monkeypatch.setattr(apo, "AUDIT_LOG", fake_audit)
    return fake_target


def test_run_1_partial_failure_persists_done_state(tmp_registry, monkeypatch):
    apo = _import_apo()
    pending = [f"uuid-{i:02d}" for i in range(17)]

    def fake_rename(uuid, new_name):
        return uuid in {p for i, p in enumerate(pending) if i < 10}  # first 10 succeed

    monkeypatch.setattr(apo, "nlm_rename", fake_rename)
    persisted = []
    monkeypatch.setattr(apo, "persist_transition", lambda u, s: persisted.append((u, s)))
    apo.run_apoptosis(pending=pending, dry_run=False)
    done = [u for u, s in persisted if s == "APOPTOSIS_DONE"]
    failed = [u for u, s in persisted if s != "APOPTOSIS_DONE"]
    assert len(done) == 10
    assert len(failed) == 7


def test_run_2_resumes_from_pending(tmp_registry, monkeypatch):
    apo = _import_apo()
    pending = [f"uuid-{i:02d}" for i in range(17)]
    # Simulate run-2 where caller passes only the 7 still-pending.
    still_pending = pending[10:]
    persisted = []
    monkeypatch.setattr(apo, "nlm_rename", lambda u, n: True)
    monkeypatch.setattr(apo, "persist_transition", lambda u, s: persisted.append((u, s)))
    apo.run_apoptosis(pending=still_pending, dry_run=False)
    assert len(persisted) == 7
    assert all(s == "APOPTOSIS_DONE" for _, s in persisted)


def test_run_3_no_op_when_all_done(tmp_registry, monkeypatch):
    apo = _import_apo()
    rename_calls = []
    monkeypatch.setattr(apo, "nlm_rename", lambda u, n: rename_calls.append(u) or True)
    apo.run_apoptosis(pending=[], dry_run=False)
    assert rename_calls == []


def test_apoptosis_idempotent_skips_already_renamed_nb(tmp_registry, monkeypatch):
    apo = _import_apo()
    monkeypatch.setattr(apo, "nlm_get_title", lambda u: "[ARCHIVED-2026-05-07] Foo")
    rename_calls = []
    monkeypatch.setattr(apo, "nlm_rename", lambda u, n: rename_calls.append(u) or True)
    monkeypatch.setattr(apo, "persist_transition", lambda u, s: None)
    apo.run_apoptosis(pending=["uuid-AA"], dry_run=False)
    assert rename_calls == [], "must NOT re-rename already-archived NB"


def test_persistence_after_simulated_sigkill(tmp_registry, monkeypatch):
    apo = _import_apo()
    pending = [f"uuid-{i:02d}" for i in range(5)]

    def fake_rename(uuid, new_name):
        if uuid == "uuid-02":
            raise SystemExit("simulated SIGKILL mid-loop")
        return True

    monkeypatch.setattr(apo, "nlm_rename", fake_rename)
    persisted: list[tuple[str, str]] = []
    monkeypatch.setattr(apo, "persist_transition", lambda u, s: persisted.append((u, s)))
    with pytest.raises(SystemExit):
        apo.run_apoptosis(pending=pending, dry_run=False)
    # uuid-00, uuid-01 must have been persisted before uuid-02 crashed.
    assert ("uuid-00", "APOPTOSIS_DONE") in persisted
    assert ("uuid-01", "APOPTOSIS_DONE") in persisted
