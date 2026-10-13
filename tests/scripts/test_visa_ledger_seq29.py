"""The seq-29 ledger in the corner skill and PENDING-ARMS (read by scripts/ci/observe_visa_ledger_seq29.py)."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / ".agents/skills/visaoracle/SKILL.md"
LOG = REPO / ".agents/skills/visaoracle/references/live-state-log.md"
ARMS = REPO / ".claude/skills/modus/PENDING-ARMS.md"
RUNBOOK = REPO / "docs/runbooks/visa-engine-key-ceremony.md"
ACTIVATION = "84e8a5c5-55eb-4649-8dc4-f620c9f9b00b"
RULE_PACK = "ed666554-c476-5e67-9c25-921388e64537"
PAYLOAD = "3f3b45ed1aaeadc72ec9dd2a5e33519ded3a0ec1da8408fade150a0ae39b9295"
BOUNDARY = "2026-11-14T00:07:47Z"
PROOF = "issuecomment-6144652983"
ARMS_LINES = ARMS.read_text(encoding="utf-8").splitlines()


def _rows(needle: str) -> list[str]:
    return [ln for ln in ARMS_LINES if needle in ln]


def test_skill_names_the_seq29_activation_and_boundary():
    text = SKILL.read_text(encoding="utf-8")
    for fact in (ACTIVATION, RULE_PACK, PAYLOAD, BOUNDARY, "2026-11-07", "2bf9ed3c93", PROOF,
                 "production pack seq-29", "updated 2026-10-14"):
        assert fact in text, fact


def test_runbook_records_the_seq29_activation_done():
    text = RUNBOOK.read_text(encoding="utf-8")
    note = text[text.index("## Signing + activation note (2026-10-13, seq-29)") :]
    note = note.split("\n## Rotation", 1)[0]
    for fact in (ACTIVATION, "2026-10-13T11:19:00Z", "**Activation: done 2026-10-13T11:19:00Z.**",
                 "b7c808bd-c0f4-48fe-9fdb-3f7f47f7e86a", "closed at 11:18:58Z", PROOF.replace("issuecomment-", "#issuecomment-")):
        assert fact in note, fact
    assert "activation: pending" not in note.lower()


def test_seq28_skill_bullets_are_marked_superseded_by_seq29():
    assert SKILL.read_text(encoding="utf-8").count("SUPERSEDED by seq-29") >= 3


def test_live_state_log_entry_carries_activation_merge_and_proof():
    text = LOG.read_text(encoding="utf-8")
    for fact in (ACTIVATION, "2bf9ed3c93c345db1ebd7675fed60111b4bf15e3", PROOF, "2026-10-13T11:19:00Z",
                 BOUNDARY, "dpl_8V8qTy4xedXAe7GD7r3AESbcw1Qq", "#8410", "vo-seq30-a1-e30-material"):
        assert fact in text, fact


def test_live_state_log_entry_is_the_newest():
    text = LOG.read_text(encoding="utf-8")
    dated = [ln for ln in text.splitlines() if ln.startswith("- 20")]
    assert dated[0].startswith("- 2026-10-14 (M5")
    assert "E33 audit waves 1-2" in dated[0]
    seq29 = [ln for ln in dated if ln.startswith("- 2026-10-13 (M5")]
    assert seq29 and "seq-29 active" in seq29[0]


def test_freshness_row_is_closed_with_its_proof():
    rows = _rows("seq-29 must be signed and activated before the seq-28 boundary 2026-11-12T18:00:16Z")
    assert len(rows) == 1
    row = rows[0]
    assert row.startswith("- closed 2026-10-13 (CLOSED BY #8433, merge `2bf9ed3c93`")
    assert "activation 84e8a5c5 at 2026-10-13T11:19:00Z" in row and PROOF in row


def test_8390_row_is_closed_with_the_suite_as_proof():
    rows = _rows("#8390 post-organ observation")
    assert len(rows) == 1
    row = rows[0]
    assert row.startswith("- closed 2026-10-13 (CLOSED BY #8433")
    assert "actions/runs/38382522528/job/115250277579" in row
    assert "actions/runs/38384044570/job/115255605209" in row  # merge_group run on 2bf9ed3c93
    assert "research/visa/2026-10-13-organ-reattest-seq29" in row
    assert "observe_visa_seq28_signed.py" in row and "retired by #8433" in row


def test_next_freshness_row_appears_exactly_once_open():
    rows = _rows("VISA-ORACLE freshness, after seq-29)")
    assert len(rows) == 1
    row = rows[0]
    assert row.startswith("- opened 2026-10-13 (M5")
    assert "owner: me (sessione M5, nuzantara-57)" in row
    assert BOUNDARY in row and "T-7 fires 2026-11-07" in row
    assert "missing arming step:" in row and "proof-of-armed:" in row


def test_no_pending_arms_line_is_duplicated():
    counts = Counter(ln for ln in ARMS_LINES if ln.startswith(("- opened 2026-10-1", "- closed 2026-10-1")))
    assert [ln[:80] for ln, n in counts.items() if n > 1] == []
    visa = [ln for ln in counts.elements() if "VISA-ORACLE" in ln[:200] or "visaoracle" in ln[:200]]
    prefixes = Counter(ln[:140] for ln in visa)
    assert [k[:80] for k, n in prefixes.items() if n > 1] == []
