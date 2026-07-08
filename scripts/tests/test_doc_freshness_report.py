"""Tests for scripts/doc_freshness_report.py (report-only signaler)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "doc_freshness_report.py"

_spec = importlib.util.spec_from_file_location("doc_freshness_report", SCRIPT)
dfr = importlib.util.module_from_spec(_spec)
sys.modules["doc_freshness_report"] = dfr
_spec.loader.exec_module(dfr)


# ---------------------------------------------------------------------------
# Reference extraction / normalization (the #3-family unit: innocence AND guilt)
# ---------------------------------------------------------------------------

def test_normalize_strips_line_numbers_and_punct():
    assert dfr._normalize("scripts/docs_sync.py:255") == "scripts/docs_sync.py"
    assert dfr._normalize("apps/foo/bar.py:12-30") == "apps/foo/bar.py"
    assert dfr._normalize("docs/x.md).") == "docs/x.md"
    assert dfr._normalize("docs/x.md#anchor") == "docs/x.md"


def test_checkable_path_guilt():
    # Path-shaped, known prefix → must be checked
    assert dfr._is_checkable_path("apps/federation/")
    assert dfr._is_checkable_path("scripts/docs_sync.py")


def test_checkable_path_innocence():
    # URLs, globs, placeholders, bare filenames, env-expansions → never checked
    assert not dfr._is_checkable_path("https://example.com/apps/x")
    assert not dfr._is_checkable_path("apps/*/README.md")
    assert not dfr._is_checkable_path("apps/<nome>/README.md")
    assert not dfr._is_checkable_path("PRICING_REFERENCE.md")  # bare, aspirational
    assert not dfr._is_checkable_path("$HOME/scripts/x.sh")
    assert not dfr._is_checkable_path("~/logs/x.log")
    assert not dfr._is_checkable_path("apps/evaluator/nlm_deep_research/*_state.json")
    assert not dfr._is_checkable_path("")
    # NNN naming templates (real false positives caught by the 2026-07-02
    # innocence probe — parent dirs exist, the basename is a convention)
    assert not dfr._is_checkable_path(
        "apps/backend-rag/backend/db/migrations_v2/NNN_name.sql"
    )
    assert not dfr._is_checkable_path(
        "apps/backend-rag/backend/migrations/apply_migration_NNN.py"
    )
    # backend-relative shorthand must not be root-resolved
    assert not dfr._is_checkable_path("migrations_v2/")


def test_scan_atlas_flags_known_dead_ref(tmp_path, monkeypatch):
    # Synthetic atlas: one live ref, one dead code ref, one dead link.
    root = tmp_path
    (root / "docs").mkdir()
    (root / "scripts").mkdir()
    (root / "scripts" / "real.py").write_text("# real\n")
    (root / "INDEX.md").write_text(
        "See `scripts/real.py` and `scripts/ghost.py`.\n"
        "[dead link](docs/GONE.md)\n"
        "[url](https://x.com) `apps/*/glob` `BARE.md`\n"
    )
    for rel in dfr.ATLAS_FILES[1:]:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("clean\n")
    monkeypatch.setattr(dfr, "REPO_ROOT", root)
    dead = dfr.scan_atlas_dead_paths()
    refs = {(d["doc"], d["ref"]) for d in dead}
    assert ("INDEX.md", "scripts/ghost.py") in refs
    assert ("INDEX.md", "docs/GONE.md") in refs
    # Innocence: live file, URL, glob, bare filename NOT flagged
    assert all(r[1] not in ("scripts/real.py", "apps/*/glob", "BARE.md") for r in refs)


# ---------------------------------------------------------------------------
# Smoke on the real repo (the report must run green end-to-end)
# ---------------------------------------------------------------------------

def test_smoke_real_repo_exit_zero_and_sections():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr[-500:]
    for header in (
        "## 1. Atlas dead paths",
        "## 2. Organ arming",
        "## 3. Coverage",
        "## 4. Doc↔code pairing",
    ):
        assert header in proc.stdout


def test_json_mode_parses():
    import json

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert set(data) == {"dead_paths", "organ_arming", "coverage", "doc_code_pairing"}
    assert data["coverage"]["plists_total"] > 0
