#!/usr/bin/env python3
"""Tests for scripts/lint_google_oauth_credentials.py.

Guard-conformance registry entry: `google-oauth-credentials-lint`
(guilt + innocence below; the real-tree test is the live innocence proof —
the nine redacted scripts must stay clean).

Every credential-shaped fixture is assembled from fragments at runtime:
a literal `GOCSPX-…`/`1//…` body in THIS file would make the guard's own
test its first finding (same discipline as the sibling lint tests).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "lint_google_oauth_credentials.py"

sys.path.insert(0, str(REPO / "scripts"))
import lint_google_oauth_credentials as lint  # noqa: E402

SEC_BODY = "Qp" + "7Lm2Nx" + "4Rt8Vb" + "3Zc6Yh" + "9Js5"  # synthetic body
REF_BODY = "0g" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9t0U1v2W3x4Y5z6"
CID = "987654321098" + "-" + "zyxwvutsrqponmlkjihgfedcbaabcd" + ".apps.googleusercontent.com"


# ----------------------------------------------------------------- guilt


def test_google_oauth_lint_guilt_flagged():
    guilty = [
        '"client_secret": "GOCSPX-' + SEC_BODY + '",',
        'OAUTH_REFRESH_TOKEN = "1//' + REF_BODY + '"',
        'OAUTH_CLIENT_ID = "' + CID + '"',
    ]
    for text in guilty:
        hits = lint.scan_text(text, "fixture.py")
        assert hits, f"guard missed: {text[:40]}…"
        assert "fixture.py:1" in hits[0]


def test_google_oauth_lint_names_known_compromised_by_fingerprint():
    """The published 2026-08-21 triple is NAMED via its SHA-256, never printed."""
    import hashlib

    body = "Kn" + "3mQp7R" + "z2Lb4W" + "t6Hx8J" + "1Fs5"
    value = "GOCSPX-" + body
    lint.KNOWN_COMPROMISED[hashlib.sha256(value.encode()).hexdigest()[:16]] = "test-note"
    try:
        hits = lint.scan_text(f'S = "{value}"', "leak.py")
        assert hits and "test-note" in hits[0]
        assert body not in hits[0]  # the finding must never carry the value
    finally:
        del lint.KNOWN_COMPROMISED[hashlib.sha256(value.encode()).hexdigest()[:16]]


# ------------------------------------------------------------- innocence


def test_google_oauth_lint_innocence_env_reads_and_markers_pass():
    innocent = [
        'OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET_RCLONE", "")',
        "# Rotate GOCSPX-*** on Google Cloud Console if committed",
        'OAUTH_CLIENT_SECRET = "GOCSPX-' + "y" * 24 + '"',  # placeholder body
        'S = "GOCSPX-' + SEC_BODY + '"  # synthetic-google-oauth-credential',
        "# synthetic-google-oauth-credential\n" + 'S = "GOCSPX-' + SEC_BODY + '"',
        'ratio = "1//2"  # prose, not a token',
    ]
    for text in innocent:
        assert lint.scan_text(text, "ok.py") == [], f"false positive on: {text[:50]}…"


def test_google_oauth_lint_clean_on_real_tree():
    """The shipped tree must be clean after the 2026-08-21 redaction."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--all"],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(REPO),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_google_oauth_lint_selftest_exit_zero():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--selftest"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(REPO),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_google_oauth_lint_missing_path_is_rc2_not_clean():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "no/such/file.py"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(REPO),
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
