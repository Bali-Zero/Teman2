"""The seq-28 ledger in the corner skill and PENDING-ARMS (read by scripts/ci/observe_visa_ledger_seq28.py)."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / ".agents/skills/visaoracle/SKILL.md"
LOG = REPO / ".agents/skills/visaoracle/references/live-state-log.md"
ARMS = REPO / ".claude/skills/modus/PENDING-ARMS.md"
ACTIVATION = "b7c808bd-c0f4-48fe-9fdb-3f7f47f7e86a"
RULE_PACK = "b383effb-eea4-5890-9a6a-0f13d816e855"
ARMS_LINES = ARMS.read_text(encoding="utf-8").splitlines()


def test_skill_names_the_seq28_activation():
    text = SKILL.read_text(encoding="utf-8")
    assert ACTIVATION in text and RULE_PACK in text
    assert "production pack seq-28" in text


def test_older_skill_bullets_are_marked_superseded():
    assert SKILL.read_text(encoding="utf-8").count("SUPERSEDED by seq-28") >= 2


def test_live_state_log_records_the_activation_and_proof():
    text = LOG.read_text(encoding="utf-8")
    assert ACTIVATION in text
    assert "issuecomment-6117354289" in text


def test_both_seq28_rows_are_closed_with_proof():
    closed = [ln for ln in ARMS_LINES if ln.startswith("- closed 2026-10-12 (CLOSED BY #8300")]
    assert len(closed) == 2
    assert all(ACTIVATION in ln and "issuecomment-6117354289" in ln for ln in closed)
    opened = [ln for ln in ARMS_LINES if ln.startswith("- opened")]
    assert not [ln for ln in opened if "seq-28 must be signed" in ln]
    assert not [ln for ln in opened if "seq-28 chain: A" in ln]


def test_seq29_freshness_row_appears_exactly_once():
    rows = [ln for ln in ARMS_LINES if "VISA-ORACLE freshness, after seq-28)" in ln]
    assert len(rows) == 1
    assert "2026-11-12T18:00:16Z" in rows[0] and "OK pack_sequence 29" in rows[0]


def test_no_pending_arms_row_is_duplicated():
    rows = [ln for ln in ARMS_LINES if ln.startswith(("- opened 2026-10-1", "- closed 2026-10-1"))]
    assert [ln[:80] for ln, n in Counter(rows).items() if n > 1] == []
    prefixes = Counter(ln[:120] for ln in rows)
    assert [k for k, n in prefixes.items() if n > 1 and "seq-28" in k] == []
