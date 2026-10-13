"""The seq-28 ledger in the corner skill and PENDING-ARMS (read by scripts/ci/observe_visa_ledger_seq28.py)."""
from __future__ import annotations

import re
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


LOG_FACTS = (
    "2026-10-11T22:53:04Z",
    "2026-10-12T03:05:56Z",
    "7bb50d079e",
    "#8300",
    "b383effb-eea4-5890-9a6a-0f13d816e855",
    "a23a5bf55a77a658aef4ff06637cdb6fea476c5569d3d47a56896af2b8557046",
    "2026-11-12T18:00:16Z",
    "2026-11-05",
    "2630e98c70",
    "2026-10-11T15:40:19Z",
    "issuecomment-6111023863",
    "fdce3f78dd",
    "merged 16:50:19Z",
    "issuecomment-6111522657",
    "OK pack_sequence 28",
    "03:09:58Z",
    "03:10:54Z",
    "EN 03:35:50Z / ID 03:43:20Z",
    "live gold 18/20",
)
PROOF_13 = (
    "PR #8300 merged 2026-10-12T03:05:56Z as `7bb50d079e`",
    "ceremony on Pro 03:08Z",
    ACTIVATION,
    "rule_pack_id `b383effb-eea4",
    "payload `a23a5bf5",
    "seq-27 activation `471bddfa` closed",
    "sentinel `OK pack_sequence 28` at 03:09:58Z",
    "`/evaluate` sequence 28 at 03:10:54Z",
    "exactly one open PRODUCTION activation",
    "https://github.com/Bali-Zero/Teman2/pull/8300#issuecomment-6117354289",
)
CHAIN_PROOF = (
    "headless walks EN 03:35:50Z / ID 03:43:20Z show the USD 60,000 sentence",
    "business age 36 no AGE_BELOW_55",
    "retirement 54 AGE_BELOW_55",
    "remote 85000 [E33G]",
    "59999 E33G_INCOME_BELOW_THRESHOLD",
    "unknown NEEDS_INPUT",
    "E33E quote 45000000",
    "live gold 18/20 (only 9 and 10, known)",
)


def _closed():
    return [ln for ln in ARMS_LINES if ln.startswith("- closed 2026-10-12 (CLOSED BY #8300")]


def test_live_state_log_carries_every_pinned_fact():
    text = LOG.read_text(encoding="utf-8")
    assert [f for f in LOG_FACTS if f not in text] == []
    assert "03:06:42" not in text


def test_both_closed_rows_carry_the_pinned_proof():
    for row in _closed():
        assert [f for f in PROOF_13 if f not in row] == []
        assert "03:06:42" not in row
    assert [f for f in CHAIN_PROOF if f not in _closed()[1]] == []


def test_skill_pins_boundary_t7_and_the_merge():
    text = SKILL.read_text(encoding="utf-8")
    for fact in ("2026-11-12T18:00:16Z", "2026-11-05", "7bb50d079e", "2026-10-11T22:53:04Z",
                 "2630e98c70", "fdce3f78dd", "issuecomment-6117354289", "TRACK C stays claimed"):
        assert fact in text, fact


def test_f1_f3_row_is_closed_by_8385_with_its_proof():
    rows = [ln for ln in ARMS_LINES if "F1 unknown-category" in ln]
    assert len(rows) == 1
    row = rows[0]
    for k in ("owner: me", "proof-of-armed:", "NAMES_THE_THRESHOLD", "every category"):
        assert k in row, k
    assert row.startswith("- closed 2026-10-12")
    assert "CLOSED BY #8385" in row and "bc35468022" in row
    assert "issuecomment-6127011575" in row
    assert "pending-on-merge" not in row
    assert "MIN_TESTS 9" in row and "MIN_TESTS 8" not in row


def test_8390_post_organ_row_appears_once_open_with_owner_and_proof():
    rows = [ln for ln in ARMS_LINES if "#8390 post-organ observation" in ln]
    assert len(rows) == 1
    row = rows[0]
    assert row.startswith("- opened 2026-10-12")
    assert "owner: me" in row and "proof-of-armed:" in row
    assert "2026-10-18T18:00Z" in row
    assert "d00c73dd48" in row and "issuecomment-6127248185" in row
    assert "only main after the organ's ledger has merged counts" in row
    assert "not the organ's PR" in row
    assert "on the organ's PR or" not in row
    assert "research/visa/2026-10-11-organ-reattest-seq28" in row


def test_seq29_row_pins_owner_deadline_and_proof():
    row = [ln for ln in ARMS_LINES if "VISA-ORACLE freshness, after seq-28)" in ln][0]
    assert "owner: me (sessione M5, nuzantara-57) before 2026-11-05" in row
    assert "T-7 fires 2026-11-05" in row
    assert "`/evaluate` sequence 29" in row
