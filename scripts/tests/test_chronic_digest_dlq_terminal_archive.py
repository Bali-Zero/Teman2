"""Round-3 DLQ hygiene (2026-08-10) — chronic_failure_digest.py's cosmetic tag.

load_dlq_terminal() feeds the `dlq=TERMINAL` cross-ref tag on an already-firing
chronic-failure line (the line itself comes from audit snapshots, independent
of the DLQ). Once dlq_autopilot.py's sweep_terminal_corpses() starts archiving
TERMINAL entries out of dlq.json, a live-only read would silently drop the tag
for archived jobs. Low-stakes (cosmetic), still class-audited per
sweep_terminal_corpses()'s docstring.
"""
import importlib.util
import json
import os
import sys

import pytest

_MODULE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "infra", "launchagents", "chronic_failure_digest.py")
)


@pytest.fixture()
def digest(tmp_path, monkeypatch):
    state_dir = tmp_path / "decisions"
    state_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STATE_DIR", str(state_dir))
    spec = importlib.util.spec_from_file_location("chronic_failure_digest_archive", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, state_dir


def test_archived_only_job_still_tagged_terminal(digest):
    mod, state_dir = digest
    (state_dir / "dlq.json").write_text(json.dumps({"queue": []}))
    (state_dir / "dlq_terminal_archive.json").write_text(
        json.dumps({"archive": [{"job": "archived_job"}]})
    )
    out = mod.load_dlq_terminal()
    assert out.get("archived_job") == "TERMINAL"


def test_live_terminal_job_still_tagged_unchanged(digest):
    mod, state_dir = digest
    (state_dir / "dlq.json").write_text(
        json.dumps({"queue": [{"job": "live_job", "status": "TERMINAL"}]})
    )
    out = mod.load_dlq_terminal()
    assert out.get("live_job") == "TERMINAL"


def test_missing_archive_file_is_not_an_error(digest):
    mod, state_dir = digest
    (state_dir / "dlq.json").write_text(
        json.dumps({"queue": [{"job": "solo_live", "status": "TERMINAL"}]})
    )
    out = mod.load_dlq_terminal()
    assert out == {"solo_live": "TERMINAL"}


def test_non_terminal_job_is_not_tagged(digest):
    mod, state_dir = digest
    (state_dir / "dlq.json").write_text(
        json.dumps({"queue": [{"job": "healthy_job", "status": "ok"}]})
    )
    (state_dir / "dlq_terminal_archive.json").write_text(json.dumps({"archive": []}))
    out = mod.load_dlq_terminal()
    assert "healthy_job" not in out
