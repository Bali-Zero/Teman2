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
    assert "ledger after E33 wave 3" in dated[0]
    waves12 = [ln for ln in dated if "ledger after the E33 audit waves 1-2" in ln]
    assert len(waves12) == 1 and dated.index(waves12[0]) == 1
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


E33_WAVES = (
    ("8437", "8b55c0dfac", "6155366109"),
    ("8439", "be66630c2e", "6155365619"),
    ("8440", "6a8f9a4cb6", "6155366644"),
    ("8441", "b0523a0a70", "6155762792"),
    ("8454", "762b364f8f", "6157110792"),
    ("8456", "cf31a25e6f", "6157110398"),
)


def _waves_entry() -> str:
    dated = [ln for ln in LOG.read_text(encoding="utf-8").splitlines() if ln.startswith("- 20")]
    entries = [ln for ln in dated if ln.startswith("- 2026-10-14 (M5") and "E33 audit waves 1-2" in ln]
    assert len(entries) == 1
    # the entry body is the indented block that follows its heading line
    text = LOG.read_text(encoding="utf-8")
    start = text.index(entries[0])
    end = text.index("\n- 20", start + 1)
    return " ".join(text[start:end].split())


def test_e33_waves_entry_carries_each_pr_sha_and_proof_exactly_once():
    body = _waves_entry()
    for pr, sha, proof in E33_WAVES:
        assert body.count(f"#{pr} ") == 1, pr
        assert body.count(f"merge `{sha}`") == 1, sha
        assert body.count(f"issuecomment-{proof}") == 1, proof
    assert "six audit items still open" in body
    open_items = ("PR-7 permit length", "PR-10 E33F note", "PR-20 render prohibited",
                  "PR-8 documents", "income-or-allowance wording fix", "replay freshness test")
    assert all(body.count(item) >= 1 for item in open_items)


def test_zero_runner_row_appears_exactly_once_open():
    rows = _rows("opened 2026-10-14 (M5, infra)")
    assert len(rows) == 1
    row = rows[0]
    assert "zero-runner-1" in row and "missing arming step:" in row and "proof-of-armed:" in row
    assert len(_rows("`zero-runner-1` (Mini) pip/uv cache refills")) == 1


def test_rangkap_row_carries_the_consumer_extension_once_in_the_action_field():
    rows = _rows("Copy still contradicting the E33 price card")
    assert len(rows) == 1
    fields = rows[0].split(" | ")
    assert len(fields) == 4
    action, proof = fields[2], fields[3]
    for token in ("e33_claim_guard.py", "country-comparator.ts", "faq-data.ts", "hf.e33.employment-not-covered"):
        assert rows[0].count(token) == 1, token
        assert token in action and token not in proof, token
    assert "live page text" in proof


E33_WAVE3 = (
    ("8466", "7c9184772a"),
    ("8467", "ac8a106930"),
    ("8468", "a14ee32144"),
    ("8469", "7391929b46"),
    ("8493", "55edebae5b"),
    ("8494", "3d2c743a48"),
)


def _wave3_entry() -> str:
    text = LOG.read_text(encoding="utf-8")
    heads = [ln for ln in text.splitlines() if ln.startswith("- 2026-10-14 (M5") and "ledger after E33 wave 3" in ln]
    assert len(heads) == 1
    start = text.index(heads[0])
    end = text.index("\n- 20", start + 1)
    return " ".join(text[start:end].split())


def test_wave3_entry_carries_each_pr_and_merge_sha_exactly_once():
    body = _wave3_entry()
    for pr, sha in E33_WAVE3:
        assert body.count(f"#{pr} ") == 1, pr
        assert body.count(f"merge `{sha}`") == 1, sha
    assert "six wave-3 PRs merged" in body and "seven Zero decisions" in body
    for token in ("dpl_4V8f1nWHfYgEWYcbJ6e4QNjfMJaB", "dpl_7kib2aoAPDm1vZrN94dzTbHLxAGv",
                  "issuecomment-6166176350", "issuecomment-6166321868", "Rp 14.000.000", "45.000.000"):
        assert body.count(token) >= 1, token


def test_wave3_entry_names_the_three_c4_items_and_the_in_flight_lanes():
    body = _wave3_entry()
    for token in ("business_meetings", "terkecuali diperlukan dalam pekerjaannya", "paid_employment",
                  "catalogue-decisions", "zantara-e33f", "brochure-prices", "stay-invariants",
                  "pr10", "vo-copy", "tree-invest", "ID NOT proven"):
        assert body.count(token) >= 1, token


def test_skill_live_state_leads_with_wave3_and_stays_an_index():
    text = SKILL.read_text(encoding="utf-8")
    block = text[text.index("## LIVE STATE"):text.index("SUPERSEDED by seq-29")]
    assert block.index("2026-10-14 (newest): E33 wave 3 live") < block.index("2026-10-13 position")
    for pr, sha in E33_WAVE3:
        assert block.count(f"#{pr} ") == 1, pr
        assert block.count(f"`{sha}`") == 1, sha
    assert "ID not proven" in block and "In flight, not merged" in block


WAVE3_ROWS = (
    ("re-read before 2027-10-13", "owner: the Visa Oracle session"),
    ("No runtime staleness check", "owner: the Visa Oracle session"),
    ("#8468 Indonesian surfaces not proven live", "owner: nuzantara-57"),
    ("Three PR-20 C4 items", "owner: visa-night conductor + signer"),
    ("Council seats degraded", "owner: operator[secret]"),
    ("iQOO has not been attached to Pro since 2026-09-26", "owner: operator[physical]"),
)


def test_wave3_pending_rows_each_open_exactly_once_with_owner_and_proof():
    opened = _rows("opened 2026-10-14 (M5, VISA-ORACLE E33 wave 3)")
    assert len(opened) == len(WAVE3_ROWS) == 6
    for needle, owner in WAVE3_ROWS:
        rows = [r for r in opened if needle in r]
        assert len(rows) == 1, needle
        fields = rows[0].split(" | ")
        assert len(fields) == 5, needle
        assert fields[2].startswith("missing arming step:"), needle
        assert fields[3] == owner, needle
        assert fields[4].startswith("proof-of-armed:"), needle
    assert any("2027-10-13T23:11Z" in r for r in opened)
