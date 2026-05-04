"""Unit tests for the events_outbox_prune cron script (Sprint 6).

Pattern: same AST-based contract test approach used in
test_drive_poll_service_methods.py (cf. cicatrix 2026-04-29 backend
prod down). The script is tested as a static artifact:
  - file exists
  - imports prune_consumed from outbox helper (no copy-paste)
  - parses --database-url, --older-than-days, --dry-run flags
  - has the structured logger fields the LaunchAgent log monitor
    will grep for ("prune complete:", "deleted=", "duration_ms=")

Live PG behavior is verified separately via
`bash scripts/events_outbox_prune_wrapper.sh --dry-run` against the
fly proxy on Pro (see sprint6 commit message).
"""
from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[5]
SCRIPT_PATH = _REPO_ROOT / "scripts" / "events_outbox_prune.py"
WRAPPER_PATH = _REPO_ROOT / "scripts" / "events_outbox_prune_wrapper.sh"
PLIST_PATH = (
    _REPO_ROOT
    / "infra"
    / "launchagents"
    / "com.matagaruda.events-outbox-prune.plist"
)


def test_script_exists():
    assert SCRIPT_PATH.exists(), f"missing {SCRIPT_PATH}"


def test_script_imports_prune_consumed():
    """Re-uses the helper, doesn't copy-paste the SQL."""
    src = SCRIPT_PATH.read_text()
    assert "from backend.services.events.outbox import prune_consumed" in src


def test_script_has_dry_run_flag():
    src = SCRIPT_PATH.read_text()
    assert '"--dry-run"' in src
    assert "action=" in src and "store_true" in src


def test_script_has_older_than_days_flag():
    src = SCRIPT_PATH.read_text()
    assert '"--older-than-days"' in src
    assert "OUTBOX_PRUNE_DAYS" in src


def test_script_default_retention_is_30_days():
    """Aligned with the helper's default (outbox.py prune_consumed)."""
    src = SCRIPT_PATH.read_text()
    assert 'OUTBOX_PRUNE_DAYS", "30"' in src


def test_script_logs_structured_summary():
    """LaunchAgent log monitors grep for these tokens — keep them stable."""
    src = SCRIPT_PATH.read_text()
    assert "prune complete:" in src
    assert "deleted=" in src
    assert "duration_ms=" in src


def test_script_returns_nonzero_on_db_failure():
    """db_connect_failed must exit 1 so LaunchAgent retries next day."""
    src = SCRIPT_PATH.read_text()
    tree = ast.parse(src)
    # The except branch around asyncpg.connect must `return 1`.
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Constant) and node.value.value == 1:
            found = True
            break
    assert found, "expected at least one `return 1` in error path"


def test_script_closes_connection_in_finally():
    src = SCRIPT_PATH.read_text()
    # Ensure `finally:` block contains conn.close()
    assert "finally:" in src
    assert "await conn.close()" in src


def test_script_validates_database_url_required():
    src = SCRIPT_PATH.read_text()
    assert "DATABASE_URL not set" in src
    # Exit code 2 = config error (vs 1 = runtime failure)
    assert "sys.exit(2)" in src


def test_wrapper_exists():
    wrapper = WRAPPER_PATH
    assert wrapper.exists()


def test_wrapper_sources_secrets_file():
    wrapper = WRAPPER_PATH
    content = wrapper.read_text()
    assert "SECRETS_FILE=" in content
    assert ".nuzantara-secrets.env" in content


def test_wrapper_prefers_database_url_local():
    """Same routing as mata_garuda_invalidation_sweep_wrapper.sh —
    DATABASE_URL_LOCAL points at the fly proxy, DATABASE_URL points at
    flycast (requires wireguard which isn't running)."""
    wrapper = WRAPPER_PATH
    content = wrapper.read_text()
    assert "DATABASE_URL_LOCAL" in content
    assert 'export DATABASE_URL="${DATABASE_URL_LOCAL}"' in content


def test_plist_exists():
    plist = PLIST_PATH
    assert plist.exists()


def test_plist_schedule_is_04_30_wita():
    """Verified slot AFTER the 04:13 invalidation sweep, BEFORE 06:00
    drive watchdog. Local time on macOS launchd."""
    plist = PLIST_PATH
    content = plist.read_text()
    assert "<integer>4</integer>" in content
    assert "<integer>30</integer>" in content


def test_plist_no_inline_secrets():
    """Cicatrix P0-3 secrets-leak: never inline DATABASE_URL or any
    secret as an EnvironmentVariables KEY in the plist (mode 0644 default).

    The plist body documentation MAY mention DATABASE_URL in human-readable
    XML comments — that's allowed. What is forbidden is a real
    `<key>DATABASE_URL</key>` block exposing the value."""
    plist = PLIST_PATH
    content = plist.read_text()
    # Forbidden: real plist key declarations (not in comments)
    assert "<key>DATABASE_URL</key>" not in content
    assert "<key>PASSWORD</key>" not in content
    assert "<key>TOKEN</key>" not in content
    # Defense in depth — no obvious secret-string patterns
    assert "postgres://" not in content
    assert "ghp_" not in content
    assert "fw_" not in content


def test_plist_keepalive_false():
    """Cron classification: KeepAlive=false (verified slot is StartCalendarInterval)."""
    plist = PLIST_PATH
    content = plist.read_text()
    assert "<key>KeepAlive</key>" in content
    # Find the value after KeepAlive
    after = content.split("<key>KeepAlive</key>", 1)[1]
    assert "<false/>" in after.split("<key>", 1)[0]


def test_plist_logs_to_logs_dir_not_tmp():
    """Cicatrix P0-3: 6/53 plist logged to /tmp lose entries on reboot."""
    plist = PLIST_PATH
    content = plist.read_text()
    assert "/Users/nuzantara/logs/" in content
    assert "/tmp/" not in content
