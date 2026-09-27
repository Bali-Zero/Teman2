#!/usr/bin/env python3
"""Guilt+innocence for `import_lkpm_q1_2026.py`'s two secret-handling surfaces
(R3/R4 cures of gate-7477.md / gate-7484.md on PR #7477 / #7484):

1. `_load_oss_credentials()` — the loader itself. Neither PR's guard suite
   ever called it (both gates flagged the mismatched probe). GUILT here means
   "fails closed when the file is absent"; INNOCENCE means "loads correctly
   when a synthetic credentials file is present".

2. `_process_rows()`'s per-row log line. Both gates found the pre-cure code
   logging `oss_user[:20]` whole (49/57 real usernames are <=20 chars, so
   they printed in full; the gate's own empirical run showed 59/59 synthetic
   usernames landing intact in the log). GUILT here means "no credential
   VALUE reaches any log record"; INNOCENCE means "the presence-only marker
   (`OSS=set`) still appears once per row that has credentials" — proving the
   fix silenced the value without silencing the signal.

All credential material in this file is SYNTHETIC, generated inline, and
never any of the 105 real removed username/password values (never printed
by this repo, this pack, or any test — see brief.yml constraints).

    python3 -m pytest scripts/tests/test_import_lkpm_q1_2026_secrets.py -q
"""

import asyncio
import importlib.util
import json
import logging
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "apps" / "backend-rag" / "scripts" / "import_lkpm_q1_2026.py"


def _ensure_asyncpg_importable() -> None:
    """The real `asyncpg` package is a `backend-rag` venv dependency, not a
    dependency of the lightweight guard CI job this test runs in. Nothing in
    this test ever calls a real connection method — `FakeConn` below stands
    in for `asyncpg.Connection` — so a minimal stub is enough when the real
    package isn't installed. If it IS installed (e.g. local dev shell), use
    the real one; either way `import asyncpg` inside the module under test
    succeeds.
    """
    if "asyncpg" in sys.modules:
        return
    try:
        import asyncpg  # noqa: F401
        return
    except ImportError:
        pass
    stub = types.ModuleType("asyncpg")

    class _Connection:  # placeholder — only used as a type-hint target
        pass

    async def _connect(*_args, **_kwargs):  # pragma: no cover - never called
        raise RuntimeError("asyncpg.connect() must not be called by this test")

    stub.Connection = _Connection
    stub.connect = _connect
    sys.modules["asyncpg"] = stub


def _load_module():
    _ensure_asyncpg_importable()
    spec = importlib.util.spec_from_file_location(
        "import_lkpm_q1_2026_under_test", SCRIPT,
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class _RecordCollector(logging.Handler):
    """Collects LogRecords directly off the module's own logger, bypassing
    the root logger entirely (`propagate=False` while attached — see
    `_run_process_rows`) so nothing prints to the console. Nothing collected
    here is a real credential (see module docstring): this exists to avoid
    the near-miss noted in gate-7484.md ("a redaction-preview regex ... let
    company names print in cleartext") recurring for synthetic fixture data.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class FakeConn:
    """Stands in for `asyncpg.Connection` through the full `_process_rows`
    loop: every company lookup succeeds, every upsert takes the INSERT path.
    No real DB, no real credential — mirrors the gate's own empirical method
    (asyncpg stub + fake conn + synthetic map) from gate-7484.md.
    """

    def __init__(self) -> None:
        self._next_id = 10_000

    async def fetchval(self, query, *_args):
        q = " ".join(query.split())
        if q.startswith("SELECT company_name FROM companies"):
            return "Fake Co"
        self._next_id += 1
        return self._next_id

    async def fetchrow(self, _query, *_args):
        return None  # "not existing" -> both upserts take the INSERT branch

    async def execute(self, _query, *_args):
        return None


def _synthetic_credentials(mod) -> dict:
    """One synthetic (never-real) username/password pair per LORI_59 row —
    same shape as the gate's own 59/59 empirical fixture.
    """
    return {
        row[0]: (f"synth-user-{row[0]:02d}", f"synth-pass-{row[0]:02d}")
        for row in mod.LORI_59
    }


def _run_process_rows(mod):
    stats: dict[str, int] = {
        "companies_minimal_created": 0,
        "lkpm_config_inserted": 0,
        "lkpm_config_updated": 0,
        "lkpm_reports_inserted": 0,
        "lkpm_reports_exists": 0,
        "errors": 0,
    }
    creds = _synthetic_credentials(mod)
    collector = _RecordCollector()
    original_propagate = mod.logger.propagate
    original_level = mod.logger.level
    # `logging.basicConfig(level=INFO)` at module-import time is a no-op if
    # the root logger already has a handler — which it does under pytest
    # (its own logging plugin attaches one before collection, at the
    # pytest-default WARNING level). Set this logger's own level explicitly
    # so the test doesn't depend on which order module-import vs. pytest's
    # plugin happened to win.
    mod.logger.setLevel(logging.INFO)
    mod.logger.propagate = False
    mod.logger.addHandler(collector)
    try:
        asyncio.run(mod._process_rows(FakeConn(), stats, creds))
    finally:
        mod.logger.removeHandler(collector)
        mod.logger.propagate = original_propagate
        mod.logger.setLevel(original_level)
    assert stats["errors"] == 0, f"fixture must process every row cleanly, got {stats}"
    return creds, collector.records


def test_process_rows_never_logs_a_credential_value():
    """GUILT: no synthetic username or password may appear in any log
    record's rendered message.
    """
    mod = _load_module()
    creds, records = _run_process_rows(mod)
    assert records, "fixture produced no log records — test would pass vacuously"
    messages = "\n".join(r.getMessage() for r in records)
    leaked = [
        value
        for user, pw in creds.values()
        for value in (user, pw)
        if value in messages
    ]
    assert not leaked, f"credential value(s) reached a log line: {len(leaked)} leaked"


def test_process_rows_logs_presence_marker_once_per_row():
    """INNOCENCE: the fix must not silence the SIGNAL along with the value —
    the `OSS=set` presence marker must still appear exactly once per row that
    has credentials (every row, in this fixture).
    """
    mod = _load_module()
    creds, records = _run_process_rows(mod)
    marker_count = sum(r.getMessage().count("OSS=set") for r in records)
    assert marker_count == len(creds), (
        f"expected one OSS=set marker per row ({len(creds)}), got {marker_count}"
    )


def test_load_oss_credentials_missing_file_fails_closed(tmp_path, monkeypatch):
    """GUILT/INNOCENCE pair, half 1: env unset (file absent) -> SystemExit,
    with the corrected message (R3 cure: pending, not already-rotated).
    """
    mod = _load_module()
    missing = tmp_path / "does-not-exist.json"
    monkeypatch.setattr(mod, "OSS_CREDENTIALS_FILE", missing)
    try:
        mod._load_oss_credentials()
        raise AssertionError("expected SystemExit when the credentials file is absent")
    except SystemExit as exc:
        message = str(exc)
        assert "must be rotated by the owner (pending)" in message
        assert "2026-04-07" in message
        assert "has been rotated by the owner" not in message


def test_load_oss_credentials_loads_from_synthetic_path(tmp_path, monkeypatch):
    """GUILT/INNOCENCE pair, half 2: path set to a synthetic file -> loads
    the mapping correctly. Values here are invented for this test only.
    """
    mod = _load_module()
    creds_file = tmp_path / "synthetic-credentials.json"
    creds_file.write_text(json.dumps({"1": ["synth-user-01", "synth-pass-01"]}))
    monkeypatch.setattr(mod, "OSS_CREDENTIALS_FILE", creds_file)
    loaded = mod._load_oss_credentials()
    assert loaded == {1: ("synth-user-01", "synth-pass-01")}
