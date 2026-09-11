"""Tests for organ_birth.py — the wrapper-template self-reference header.

Trauma (PENDING-ARMS 2026-08-23, ops-visaoracle-wrapper-header-0823): the
`Canon:`/`Live:` header f-string used `organ_id.replace(".", "-")` — dot only.
The ACTUAL wrapper filename (computed in main() as `dash`) replaces BOTH "."
and "_" with "-", because repo/live file naming is hyphens-only. Any organ_id
whose descriptive segment is underscore_case (the house style —
visa_freshness_sentinel, git_pull_main, llm_burn_alarm, tg_digest_flush) got a
header that lied about its own filename: reader-misdirection, not a real
home-fork DRIFT (lint_home_fork.py's sha256 pair-check is comment-blind and
was never wrong). 3 live wrappers carried the bug on main; a 4th
(visa_freshness_sentinel) had already been hand-cured by a prior fix.

Contract (guilt + innocence, per cicatrix-superscar #3 antidote):
  - GUILT: an organ_id with an underscore in its name segment must produce a
    Canon:/Live: header whose filename matches the ACTUAL computed wrapper
    filename (dot AND underscore -> hyphen).
  - INNOCENCE: an organ_id with no underscore is unaffected (dot-only and
    dot+underscore conversion agree when there's no underscore to convert).
  - SCOPE PIN: LOG_DIR and PIDFILE stay dot-only on purpose — they name
    runtime artifacts the generator creates itself (not a claim about a
    pre-existing file), so whatever it produces is correct-by-construction
    for them. Widening their scope would be an undocumented behavior change,
    not a fix.
"""

import glob
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from organ_birth import wrapper_template  # noqa: E402

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
WRAPPER_DIR = os.path.join(REPO_ROOT, "infra", "launchagents", "wrappers")


def _actual_dash_filename(organ_id: str) -> str:
    """Mirror main()'s `dash` computation — the true wrapper filename."""
    return organ_id.replace(".", "-").replace("_", "-")


def test_underscore_organ_id_header_matches_actual_filename():
    """GUILT case: the bug's exact trigger — a descriptive segment with '_'."""
    organ_id = "pro.tg_digest_flush"
    template = wrapper_template(organ_id, "pro", "cron", "flush the telegram digest queue")
    actual = _actual_dash_filename(organ_id)

    canon = re.search(r"^# Canon: infra/launchagents/wrappers/(\S+)\.sh$", template, re.M)
    live = re.search(r"^# Live:  ~/scripts/(\S+)\.sh ", template, re.M)
    assert canon is not None, "Canon: header line missing"
    assert live is not None, "Live: header line missing"
    assert canon.group(1) == actual, (
        f"Canon: header claims {canon.group(1)!r} but the real wrapper filename "
        f"is {actual!r} — reader-misdirection (2026-08-23 W-underscore-header)"
    )
    assert live.group(1) == actual


def test_no_underscore_organ_id_unaffected():
    """INNOCENCE case: no underscore in the descriptive segment -> unchanged."""
    organ_id = "pro.freshness"
    template = wrapper_template(organ_id, "pro", "cron", "no underscore here")
    actual = _actual_dash_filename(organ_id)
    assert actual == "pro-freshness"  # sanity: nothing to convert

    canon = re.search(r"^# Canon: infra/launchagents/wrappers/(\S+)\.sh$", template, re.M)
    assert canon.group(1) == "pro-freshness"


def test_multi_underscore_segment_all_converted():
    """The house style stacks multiple underscores (visa_freshness_sentinel)."""
    organ_id = "pro.visa_freshness_sentinel"
    template = wrapper_template(organ_id, "pro", "cron", "watches visa freshness")
    actual = _actual_dash_filename(organ_id)
    assert actual == "pro-visa-freshness-sentinel"

    canon = re.search(r"^# Canon: infra/launchagents/wrappers/(\S+)\.sh$", template, re.M)
    assert canon.group(1) == actual


def test_log_dir_and_pidfile_stay_dot_only_by_design():
    """SCOPE PIN: LOG_DIR/PIDFILE are runtime artifacts the generator creates
    itself — deliberately NOT widened to the dash conversion, per the
    2026-08-23 PENDING-ARMS decision (#4599 fixed only the sentinel header
    instance and explicitly declined to touch LOG_DIR/PIDFILE generation)."""
    organ_id = "pro.tg_digest_flush"
    template = wrapper_template(organ_id, "pro", "cron", "flush the telegram digest queue")

    log_dir = re.search(r'^LOG_DIR="\$HOME/logs/([^"]+)"$', template, re.M)
    pidfile = re.search(r'^PIDFILE="/tmp/nuzantara-([^"]+)\.pid"$', template, re.M)
    assert log_dir is not None
    assert pidfile is not None
    # Dot-only conversion — underscore survives, matching the generator's
    # documented (and unchanged) runtime-artifact behavior.
    assert log_dir.group(1) == "pro-tg_digest_flush"
    assert pidfile.group(1) == "pro-tg_digest_flush"


def test_repo_wide_wrapper_headers_match_their_own_filenames():
    """PERMANENT REGRESSION GUARD (proof-of-armed item 4, PENDING-ARMS row
    'ops-visaoracle-wrapper-header-0823'): every existing wrapper's own
    `# Canon:` self-reference must equal its actual filename. Catches a
    future 5th instance the instant it lands, instead of waiting for another
    refuter to find it. At the time this test was written, a repo-wide scan
    found EXACTLY ZERO mismatches (3 were hand-fixed, 1 was already fixed by
    a prior PR)."""
    mismatches = []
    for path in sorted(glob.glob(os.path.join(WRAPPER_DIR, "*.sh"))):
        fname = os.path.basename(path)
        text = open(path, encoding="utf-8").read()
        m = re.search(r"^# Canon: infra/launchagents/wrappers/(\S+)", text, re.M)
        if m and m.group(1) != fname:
            mismatches.append((fname, m.group(1)))
    assert mismatches == [], (
        f"wrapper header self-reference drift (2026-08-23 class): {mismatches}"
    )
