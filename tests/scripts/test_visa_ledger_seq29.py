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
                 "production pack seq-29", "updated 2026-10-15"):
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
    assert dated[0].startswith("- 2026-10-15 (M5, visaoracle E28 lane, ledger E28 close-out part 1")
    assert dated[1].startswith("- 2026-10-15 (M5, Qdrant pricing backfill lane)")
    assert "ledger addendum after the E33 closure" in dated[2]
    assert "ledger wave 5 — the E33 family closes" in dated[3]
    assert "ledger after E33 wave 4" in dated[4]
    assert "ledger after E33 wave 3" in dated[5]
    waves12 = [ln for ln in dated if "ledger after the E33 audit waves 1-2" in ln]
    assert len(waves12) == 1 and dated.index(waves12[0]) == 6
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


def _pairs_ok(body: str) -> bool:
    """Each `#PR ...` segment (up to the next `; #` or the end of clause (1)) carries ITS OWN merge sha."""
    import re

    for pr, sha in E33_WAVE3:
        seg = re.search(rf"#{pr} .*?(?=; #\d{{4}} |\n|$)", body)
        if not seg or f"merge `{sha}`" not in seg.group(0):
            return False
        if any(f"merge `{o}`" in seg.group(0) for _, o in E33_WAVE3 if o != sha):
            return False
    return True


def test_wave3_entry_carries_each_pr_and_merge_sha_exactly_once():
    body = _wave3_entry()
    for pr, sha in E33_WAVE3:
        assert body.count(f"#{pr} ") == 1, pr
        assert body.count(f"merge `{sha}`") == 1, sha
    assert _pairs_ok(body)


def test_wave3_pr_to_sha_pairing_fails_when_two_shas_are_swapped():
    body = _wave3_entry()
    a, b = E33_WAVE3[0][1], E33_WAVE3[1][1]
    swapped = body.replace(a, "@@").replace(b, a).replace("@@", b)
    assert swapped != body and not _pairs_ok(swapped)


def test_wave3_entry_does_not_call_the_wave_live_without_the_proof_level():
    body = _wave3_entry()
    assert "live proof partial" in body and "merged and live" not in body
    assert body.count("proof level:") >= 5
    assert "ID NOT proven" in body and "retirement persona shows the block under E33E and E33F, remote-worker innocence persona shows no block" in body


def test_wave3_entry_states_the_documentation_catalogue_as_the_code_holds_it():
    import json

    snap = REPO / "apps/backend-rag/backend/data/bali_zero_documentation_catalog_2026.json"
    codes = set(json.loads(snap.read_text(encoding="utf-8"))["products"])
    assert codes == {"E33", "E33A", "E33B", "E33C", "E33E", "E33F", "E33G"}
    body = _wave3_entry()
    assert "all seven catalogued E33 codes (E33, E33A, E33B, E33C, E33E, E33F, E33G)" in body
    assert "E33F seen in the browser walk (EN/ID penjamin line); E33E and E33B seen AVAILABLE in the synthetic-driver probe; E33, E33A, E33C and E33G not seen live" in body and "out-of-catalogue code UNKNOWN" in body
    assert "six wave-3 PRs merged, live proof partial" in body and "seven Zero decisions" in body
    for token in ("dpl_4V8f1nWHfYgEWYcbJ6e4QNjfMJaB", "dpl_7kib2aoAPDm1vZrN94dzTbHLxAGv",
                  "issuecomment-6166176350", "issuecomment-6166321868", "Rp 14.000.000", "45.000.000"):
        assert body.count(token) >= 1, token


def test_wave3_entry_records_8459_8460_and_the_corrected_proof_levels():
    body = _wave3_entry()
    for token in ("bd45ad8e33", "098b7f8025", "issuecomment-6158197835", "issuecomment-6158440541",
                  "dpl_hKpvZA2NAD3DrVr8nvEqurj7HuDq", "eff946e0d4"):
        assert body.count(token) == 1, token
    assert "`/health` matched only" not in body and "a test, not a live observation" not in body


def test_wave3_entry_names_the_three_c4_items_and_the_in_flight_lanes():
    body = _wave3_entry()
    for token in ("business_meetings", "terkecuali diperlukan dalam pekerjaannya", "paid_employment",
                  "catalogue-decisions", "zantara-e33f", "brochure-prices", "stay-invariants",
                  "pr10", "vo-copy", "tree-invest", "ID NOT proven"):
        assert body.count(token) >= 1, token


def test_skill_live_state_leads_with_wave3_and_stays_an_index():
    text = SKILL.read_text(encoding="utf-8")
    block = text[text.index("## LIVE STATE"):text.index("SUPERSEDED by seq-29")]
    assert block.index("2026-10-14 (wave 3): E33 wave 3 merged, live proof partial") < block.index("2026-10-13 position")
    for pr, sha in E33_WAVE3:
        assert block.count(f"#{pr} ") == 1, pr
        assert block.count(f"`{sha}`") == 1, sha
    assert "ID not proven" in block


WAVE3_ROWS = (
    ("re-read before 2027-10-13", "owner: me (passivo — verifica 2027-10-13, next Visa Oracle session)"),
    ("No runtime staleness check", "owner: me (sessione M5, next Visa Oracle session)"),
    ("#8468 Indonesian surfaces not proven live", "owner: me (next session, nuzantara-57)"),
    ("Three PR-20 C4 items", "owner: me (next session, visa-night conductor and signer)"),
    ("Council seats degraded", "owner: operator[secret]"),
    ("iQOO has not been attached to Pro since 2026-09-26", "owner: operator[physical]"),
)
WAVE3_CLASSES = ("NATURAL-WAIT", "TECH-DEBT", "TECH-DEBT", "TECH-DEBT", "OPERATOR-GATED", "OPERATOR-GATED")


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


def test_wave3_rows_parse_with_the_ledger_grammar_and_classify_as_intended():
    import json
    import subprocess
    import sys

    out = subprocess.run([sys.executable, str(REPO / "scripts/pending_arms_report.py"), "--json"],
                         capture_output=True, text=True, check=True, cwd=REPO).stdout
    found: list[dict] = []

    def walk(o):
        if isinstance(o, dict):
            if "owner" in o and "class" in o and "VISA-ORACLE E33 wave 3" in json.dumps(o)[:4000]:
                found.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(json.loads(out))
    assert [(f["owner"], f["class"]) for f in found] == [
        (o.removeprefix("owner: "), c) for (_, o), c in zip(WAVE3_ROWS, WAVE3_CLASSES)
    ]
    annual = _rows("re-read before 2027-10-13")[0]
    for token in ("seven successful live probes", "observed URLs", "fingerprint"):
        assert token in annual, token


E33_WAVE4 = (("8501", "f91af7a8f7"), ("8505", "4776e2c04e"), ("8506", "7d0fb6393e"))
WAVE4_COMMENTS = ("issuecomment-6169157235", "issuecomment-6170065306", "issuecomment-6170187076", "issuecomment-6171198490")


def _wave4_entry() -> str:
    text = LOG.read_text(encoding="utf-8")
    heads = [ln for ln in text.splitlines() if ln.startswith("- 2026-10-14 (M5") and "ledger after E33 wave 4" in ln]
    assert len(heads) == 1
    start = text.index(heads[0])
    end = text.index("\n- 20", start + 1)
    return " ".join(text[start:end].split())


def test_wave4_entry_carries_each_pr_and_merge_sha_once_and_the_comment_urls():
    import re

    body = _wave4_entry()
    for pr, sha in E33_WAVE4:
        assert body.count(f"merge `{sha}`") == 1, sha
        seg = re.search(rf"#{pr} .*?(?=\(\d\) |$)", body)
        assert seg and f"merge `{sha}`" in seg.group(0), pr
    for token in WAVE4_COMMENTS + ("run 38580739053", "dpl_3DB1orjU1pPXsoHxaMQuc5wUiHr4", "88896ff89797595c", "d460923bf1"):
        assert body.count(token) == 1, token


def test_wave4_entry_states_the_gaps_and_does_not_overclaim():
    body = _wave4_entry()
    assert "'pensiun' live query was NOT run" in body
    assert "the Qdrant pricing collection still serves the three internal points" in body
    assert "`line-clamp-5`" in body and "Altus/Onshore row (16.000.000) is not printed" in body
    assert "RED on main since #8496" in body and "No CI workflow runs this observer" in body
    assert "closed" not in body.split("(1)")[0].lower()


def test_wave4_entry_names_the_in_flight_lanes_by_name():
    body = _wave4_entry()
    for lane in ("pr10", "vo-copy", "tree-invest", "stay-invariants", "zantara-e33f-followup", "book-sponsor", "replay-fixture"):
        assert body.count(lane) >= 1, lane


def test_skill_live_state_leads_with_wave4_and_stays_an_index():
    text = SKILL.read_text(encoding="utf-8")
    block = text[text.index("## LIVE STATE"):text.index("SUPERSEDED by seq-29")]
    assert block.index("2026-10-14 (wave 4): E33 wave 4 merged and live") < block.index("2026-10-14 (wave 3)")
    for pr, sha in E33_WAVE4:
        assert block.count(f"#{pr} ") == 1, pr
        assert block.count(f"`{sha}`") == 1, sha
    assert "In flight at the time, all merged since (wave 5, above)" in block and "purge not run" in block and "'pensiun' live query NOT run" in block
    assert len([ln for ln in block.splitlines() if ln.startswith("- **2026-10-14")]) == 2


WAVE4_OPEN_ROW = ("observe_visa_oracle_replay_pins.py` was red on main", "owner: me (nuzantara-57)")


def test_wave4_pending_rows_only_the_replay_pins_row_stays_open_narrowed():
    opened = _rows("opened 2026-10-14 (M5, VISA-ORACLE E33 wave 4)")
    assert len(opened) == 1
    needle, owner = WAVE4_OPEN_ROW
    fields = opened[0].split(" | ")
    assert needle in opened[0] and len(fields) == 5
    assert fields[2].startswith("missing arming step: wire the observer into a workflow or a receptor")
    assert fields[3] == owner and fields[4].startswith("proof-of-armed:")
    for token in ("#8513", "`ba0105c684`", "Tests 305 passed (305)", "no CI workflow or receptor runs the observer", "Updated 2026-10-15 (wave 5)"):
        assert token in fields[1], token
    assert "AND one green observation of that job or receptor" in fields[4]
    for gone in ("Qdrant pricing collection still serves", "does not print the E33F Altus/Onshore row",
                 "'pensiun' live query of #8505 was not run", "the parity failure message lacks the cure"):
        assert _rows(gone) == [], gone


def test_wave4_council_row_is_updated_in_place_and_c6_is_closed_once():
    council = _rows("Council seats degraded")
    assert len(council) == 1 and council[0].count("seat_override promised a second roster review seat") == 1
    assert council[0].split(" | ")[3] == "owner: operator[secret]"
    closed = _rows("closed 2026-10-14 (M5, VISA-ORACLE E33 wave 4)")
    assert len(closed) == 1 and "C6" in closed[0] and "#8506" in closed[0]


def _report_rows(tag: str) -> list[dict]:
    import json
    import subprocess
    import sys

    out = subprocess.run([sys.executable, str(REPO / "scripts/pending_arms_report.py"), "--json"],
                         capture_output=True, text=True, check=True, cwd=REPO).stdout
    found: list[dict] = []

    def walk(o):
        if isinstance(o, dict):
            if "owner" in o and "class" in o and tag in json.dumps(o)[:4000]:
                found.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(json.loads(out))
    return found


def test_wave4_row_parses_with_the_ledger_grammar_as_tech_debt():
    found = _report_rows("VISA-ORACLE E33 wave 4")
    assert [(f["owner"], f["class"]) for f in found] == [("me (nuzantara-57)", "TECH-DEBT")]


E33_WAVE5 = (
    ("8511", "500da5c3d0"), ("8512", "f411374c98"), ("8513", "ba0105c684"), ("8515", "da14603a95"),
    ("8517", "6437b00137"), ("8518", "44b72bc860"), ("8519", "010e71031f"), ("8520", "03690ec350"),
    ("8521", "d0b352ae30"), ("8527", "e21e466c1d"), ("8528", "704b07b3fe"), ("8533", "4ab255207c"),
)
WAVE5_COMMENTS = (
    "8511#issuecomment-6174864680", "8511#issuecomment-6175811919", "8512#issuecomment-6175473942",
    "8513#issuecomment-6177880264", "8513#issuecomment-6177939507", "8515#issuecomment-6176725352",
    "8517#issuecomment-6179341400", "8518#issuecomment-6179626729", "8519#issuecomment-6178802051",
    "8520#issuecomment-6179553313", "8521#issuecomment-6180588279", "8527#issuecomment-6182682234",
    "8528#issuecomment-6183759368", "8533#issuecomment-6185444197", "8468#issuecomment-6177081375",
)


def _wave5_entry() -> str:
    text = LOG.read_text(encoding="utf-8")
    heads = [ln for ln in text.splitlines() if ln.startswith("- 2026-10-15 (M5") and "ledger wave 5" in ln]
    assert len(heads) == 1
    start = text.index(heads[0])
    end = text.index("\n- 20", start + 1)
    return " ".join(text[start:end].split())


def _wave5_pairs_ok(body: str) -> bool:
    """Each PR's segment (from its first `#PR ` to the next PR's first `#PR `) carries ITS merge sha and no other."""
    sec = body[body.index("(1) Merges and live proofs"):body.index("(2) Addenda")]
    starts = [sec.index(f"#{pr} ") for pr, _ in E33_WAVE5]
    if starts != sorted(starts):
        return False
    for i, (pr, sha) in enumerate(E33_WAVE5):
        seg = sec[starts[i]:starts[i + 1] if i + 1 < len(starts) else len(sec)]
        if f"merge `{sha}`" not in seg:
            return False
        if any(f"merge `{o}`" in seg for _, o in E33_WAVE5 if o != sha):
            return False
    return True


def test_wave5_entry_carries_each_pr_merge_sha_once_with_its_comment_urls():
    body = _wave5_entry()
    for pr, sha in E33_WAVE5:
        assert body.count(f"merge `{sha}`") == 1, sha
    assert _wave5_pairs_ok(body)
    for c in WAVE5_COMMENTS:
        assert body.count(f"pull/{c}") == 1, c
    for token in ("dpl_5kYWa3cR4iqYwt3gLoW2KiUEeKuj", "dpl_3aqxe9ud3FeHNgHWXZ4TWRkXiZTE", "dpl_5j9XhDxPUt8BchFDNu4wyMe5UozP",
                  "dpl_725yNekB5z76uTRU8K73GZ1qcbQ1", "26185b41341de17f", "run 38621650781", "run 38666679095", "run 38674301009",
                  "'Tests 392 passed (392)'", "'Tests 305 passed (305)'", "eleven PRs merged besides the wave-4 ledger itself (#8519)"):
        assert body.count(token) == 1, token


def test_wave5_pr_to_sha_pairing_fails_when_two_shas_are_swapped():
    body = _wave5_entry()
    a, b = E33_WAVE5[0][1], E33_WAVE5[1][1]
    swapped = body.replace(a, "@@").replace(b, a).replace("@@", b)
    assert swapped != body and not _wave5_pairs_ok(swapped)


def test_wave5_entry_never_upgrades_a_partial_or_missing_proof():
    body = _wave5_entry()
    assert body.count("proof level: PARTIAL") == 2
    assert "golden route investor_kitas_retirement has no public URL, so it is PARTIAL" in body
    assert "merged without the harness/fable-gate status" in body and "the status was never published" in body
    assert body.count("iQOO NOT run") >= 4 and "adb is installed on Pro" in body and "adb not installed" not in body
    assert "E33C is not walkable in the browser (unit pins only)" in body
    assert "The Vercel deployment was not matched to the sha (the served bytes were checked instead)" in body
    assert "16 of 38 products with a permit-length line and 22 rendering none" in body
    assert "Gate conditions 3-5 remain follow-ups" in body
    assert "(6) NOT done:" in body and "outside the E33 closure" in body


def test_wave5_entry_records_the_qdrant_purge_with_the_lost_backup():
    body = _wave5_entry()
    for token in ("2026-10-14T23:23Z", "`ed39c54869`", "bali_zero_pricing_hybrid", "updates=0 deletes=3 refused=0",
                  "985842427274579734", "2740830935052460964", "8903719483458810235", "DELETED 3, APPLIED 0",
                  "Re-plan after: deletes=0", "returns 0 points", "**The pre-delete backup was LOST**",
                  "re-ingest from the catalog rows", "65 catalog rows have no Qdrant point, including all E33F rows",
                  "17 points have no catalog row", "never printed"):
        assert body.count(token) == 1, token


def test_wave5_entry_records_zeros_decisions_and_the_addenda():
    body = _wave5_entry()
    for token in ("'entrambi si'", "'go'", "the Qdrant production purge is authorised",
                  "the brochure prints the E33F Altus/Onshore row at 16.000.000", "BAILOUT_TO_CLIENT_SIDE_RENDERING",
                  "`83debabf15`", "#8523", "#8493 re-sign C7 cured", "`gh pr edit`", "e33f-sponsor-types-1014"):
        assert body.count(token) >= 1, token


def test_skill_live_state_leads_with_wave5_and_stays_an_index():
    import re

    text = SKILL.read_text(encoding="utf-8")
    block = text[text.index("## LIVE STATE"):text.index("SUPERSEDED by seq-29")]
    assert block.index("2026-10-15 (wave 5): E33 family CLOSED 2026-10-15 (wave 5)") < block.index("2026-10-14 (wave 4)")
    lead = block[block.index("- **2026-10-15 (wave 5)"):block.index("- **2026-10-14 (wave 4)")]
    for pr, sha in E33_WAVE5:
        assert len(re.findall(rf"#{pr}\b", lead)) == 1, pr
        if pr not in ("8513", "8518", "8519", "8520"):
            assert lead.count(f"`{sha}`") == 1, sha
    for token in ("PARTIAL", "**Not done:**", "pre-delete backup was lost", "Backlog rows:", "no iQOO walk"):
        assert token in lead, token
    assert len(lead) < 3300 and "adb not installed" not in lead and "adb is installed on Pro" in lead
    assert len([ln for ln in block.splitlines() if ln.startswith("- **2026-10-15")]) == 4
    assert len([ln for ln in block.splitlines() if ln.startswith("- **2026-10-14")]) == 2
    assert "(updated 2026-10-15;" in text


WAVE5_CLOSED = (
    ("The Qdrant pricing collection no longer serves", "closed 2026-10-14T23:23Z", ("re-plan after the apply shows deletes=0", "returns 0 points")),
    ("The Qdrant pricing collection now has a point for every public catalog row", "closed 2026-10-15T15:58Z", ("catalog_rows_without_point=0", "#8568", "'pensiun' (14.000.000, 10.000.000) and 'retirement' (14.000.000, 16.000.000)")),
    ("The iQOO walk of the E33 public surfaces", "closed 2026-10-15", ("W1-W6 PASS comments", "pull/8511#issuecomment-6188925096", "pull/8533#issuecomment-6188925677", "pull/8512#issuecomment-6188926239", "20261015-e33-mobile")),
    ("The brochure now prints the E33F Altus/Onshore row", "closed 2026-10-15", ("26185b41341de17f", "Onshore, 1 year Rp 16.000.000", "#8528")),
    ("The gate's 'pensiun' live query of #8505 was run and passes", "closed 2026-10-15", ("2026-10-14T16:45Z", "3 E33F rows", "no generic Retirement row")),
    ("#8506 brochure guard LOW follow-ups: test_guilt_f now fails", "closed 2026-10-15", ("#8518", "17 passed", "printed the cure")),
)
WAVE5_OPENED = (
    ("the book-pricing.spec.ts ID test added by #8543", "owner: me (nuzantara-57)", "TECH-DEBT"),
    ("seq-30 candidate, the E33F `sponsor_types` is INDIVIDUAL", "owner: me (next session, visa-night conductor and signer)", "TECH-DEBT"),
    ("the E28A Indonesian article does not render in Indonesian", "owner: me (nuzantara-57)", "TECH-DEBT"),
    ("still carries stale data after the backfill", "owner: operator[business] (Zero)", "OPERATOR-GATED"),
    ("remaining LOWs of the E33 family (one row, no per-nit rows)", "owner: me (nuzantara-57)", "TECH-DEBT"),
)


def test_wave5_closed_rows_each_appear_once_with_owner_na_and_proof():
    closed = [r for r in ARMS_LINES if r.startswith("- closed 2026-10-1") and "VISA-ORACLE E33 wave 5" in r]
    assert len(closed) == len(WAVE5_CLOSED) == 6
    for needle, prefix, proofs in WAVE5_CLOSED:
        rows = [r for r in closed if needle in r]
        assert len(rows) == 1, needle
        assert rows[0].startswith(f"- {prefix} (M5, VISA-ORACLE E33 wave 5)"), needle
        fields = rows[0].split(" | ")
        assert len(fields) == 4 and fields[2] == "owner: n/a (closed)" and fields[3].startswith("proof-of-armed:"), needle
        for proof in proofs:
            assert proof in fields[3] or proof in fields[1], (needle, proof)


def test_wave5_backlog_rows_each_open_once_with_owner_proof_and_class():
    opened = [r for r in ARMS_LINES if r.startswith("- opened 2026-10-15 (M5, VISA-ORACLE E33 wave 5)")]
    assert len(opened) == len(WAVE5_OPENED) == 5
    for needle, owner, _ in WAVE5_OPENED:
        rows = [r for r in opened if needle in r]
        assert len(rows) == 1, needle
        fields = rows[0].split(" | ")
        assert len(fields) == 5 and fields[1].startswith("**BACKLOG"), needle
        assert fields[2].startswith("missing arming step:") and fields[3] == owner and fields[4].startswith("proof-of-armed:"), needle
    found = _report_rows("VISA-ORACLE E33 wave 5")
    assert sorted((f["owner"], f["class"]) for f in found) == sorted((o.removeprefix("owner: "), c) for _, o, c in WAVE5_OPENED)


def test_wave5_low_row_merges_the_nits_into_one_row_and_the_qdrant_gap_row_names_the_proof():
    low = _rows("remaining LOWs of the E33 family")
    assert len(low) == 1
    for token in ("BROCHURE_CURE == PDF_PARITY_CURE", "gate C5", "match='PRICE_E33E'", "'Claude Sonnet 5.5'", "claude-sonnet-5-5",
                  "'Dolar' casing", "harness/fable-gate status", "stay.kind", "36500", "39-case count", "says 1 where the floor is 2",
                  "StayPolicy at models.py:301 has no cross-field validator", "(10) the Firefox project of the book-pricing e2e is not runnable on Pro"):
        assert low[0].count(token) == 1, token
    assert len(_rows("match='PRICE_E33E'")) == 1 and len(_rows("StayPolicy at models.py:301")) == 1
    qdrant = _rows("still carries stale data after the backfill")[0]
    assert "points_without_catalog_row=0" in qdrant.split(" | ")[4] and "patch_pricing_contact_block.py" in qdrant
    sponsor = _rows("seq-30 candidate, the E33F `sponsor_types`")[0]
    assert "e33f-sponsor-types-1014" in sponsor and "Pasal citation" in sponsor and "inert today" in sponsor


def test_wave5_leaves_the_council_and_the_wave3_rows_untouched():
    assert len(_rows("Council seats degraded")) == 1 and len(_rows("opened 2026-10-14 (M5, VISA-ORACLE E33 wave 3)")) == 6
    assert len(_rows("iQOO has not been attached to Pro since 2026-09-26")) == 1
    assert len(_rows("#8468 Indonesian surfaces not proven live")) == 1


E33_ADDENDUM = (("8541", "66c7c706dd"), ("8543", "3d94f56a4c"))
ADDENDUM_COMMENTS = (
    "8511#issuecomment-6188925096", "8533#issuecomment-6188925677", "8512#issuecomment-6188926239",
    "8543#issuecomment-6190499447",
)


def _addendum_entry() -> str:
    text = LOG.read_text(encoding="utf-8")
    heads = [ln for ln in text.splitlines() if ln.startswith("- 2026-10-15 (M5") and "ledger addendum after the E33 closure" in ln]
    assert len(heads) == 1
    start = text.index(heads[0])
    return " ".join(text[start:text.index("\n- 20", start + 1)].split())


def test_addendum_entry_carries_the_walks_the_two_prs_and_the_comment_urls_once():
    body = _addendum_entry()
    for pr, sha in E33_ADDENDUM:
        assert body.count(f"merge `{sha}`") == 1 and body.count(f"#{pr} ") >= 1, sha
    for c in ADDENDUM_COMMENTS:
        assert body.count(f"pull/{c}") == 1, c
    for token in ("W1-W6 of 2026-10-15, all PASS", "20261015-e33-mobile/receipt.md", "dpl_GqCCrtn9NeZ47hT5CwLcCndhrF69",
                  "`vercel promote`", "chromium and webkit pass all 4 tests", "the Firefox project is not runnable on Pro",
                  "`card.innerText()` is empty under reducedMotion", "a spec fragility, not a product defect",
                  "`ssh pro '~/.local/bin/iqoo-unlock'`", "always-on VPN setting did NOT take", "phone is cabled to Pro by USB",
                  "Not proved: unlock without the owner after a reboot, and wireless ADB returning after a reboot",
                  "adb is installed on Pro; the blocker of the unrun iQOO walks was the missing device", "(6) NOT done:"):
        assert body.count(token) == 1, token


def test_addendum_never_writes_the_pin_or_overclaims_the_unlock():
    body = _addendum_entry()
    assert "one attempt per call, never looped, never read or printed" in body
    assert "PIN lives only on Pro in a 0600 file" in body
    assert "the Mobile Chrome spec is not cured" in body


def test_skill_live_state_leads_with_the_addendum_and_stays_an_index():
    text = SKILL.read_text(encoding="utf-8")
    block = text[text.index("## LIVE STATE"):text.index("SUPERSEDED by seq-29")]
    lead = block[block.index("- **2026-10-15 (addendum)"):block.index("- **2026-10-15 (wave 5)")]
    for token in ("#8511, #8512, #8533", "`3d94f56a4c`", "`66c7c706dd`", "Firefox is not installed on Pro", "~/.local/bin/iqoo-unlock"):
        assert token in lead, token
    assert len(lead) < 1800 and block.count("newest)") == 1


def test_addendum_pending_rows_close_the_iqoo_walk_and_open_the_spec_fragility_once():
    assert len(_rows("no iQOO walk of the E33 public surfaces was run")) == 0
    spec = _rows("the book-pricing.spec.ts ID test added by #8543")
    assert len(spec) == 1
    fields = spec[0].split(" | ")
    assert len(fields) == 5 and "textContent" in fields[2] and fields[3] == "owner: me (nuzantara-57)"
    assert "Mobile Chrome against balizero.com" in fields[4]
    assert "adb is installed" in _rows("The iQOO walk of the E33 public surfaces")[0]
    assert "adb is not installed on Pro" not in ARMS.read_text(encoding="utf-8").split("opened 2026-10-15 (M5, VISA-ORACLE E33 wave 5)", 1)[1]


def test_qdrant_backfill_row_is_closed_once_and_the_old_open_needle_is_gone():
    closed = _rows("the backfill CLOSED it, by #8568")
    assert len(closed) == 1
    row = closed[0]
    assert row.startswith("- closed 2026-10-15T15:58Z (M5, VISA-ORACLE E33 wave 5)")
    assert "#8568" in row and "`b93adf342d`" in row and "catalog_rows_without_point=0" in row
    assert not [r for r in ARMS_LINES if r.startswith("- opened") and "has no point for 65 catalog rows" in r]
    assert len(_rows("has no point for 65 catalog rows")) == 0


def test_qdrant_backfill_log_entry_is_second_and_carries_the_apply_facts():
    text = LOG.read_text(encoding="utf-8")
    dated = [ln for ln in text.splitlines() if ln.startswith("- 20")]
    assert dated[1].startswith("- 2026-10-15 (M5, Qdrant pricing backfill lane): **the pricing collection has a point for every public catalog row")
    start = text.index(dated[1])
    body = " ".join(text[start:text.index("\n- 20", start + 1)].split())
    for token in ("`b93adf342d`", "CREATED 66", "in_sync=116", "`6321afd152`"):
        assert body.count(token) >= 1, token


def test_skill_live_state_second_bullet_is_the_qdrant_backfill_and_only_one_says_newest():
    text = SKILL.read_text(encoding="utf-8")
    block = text[text.index("## LIVE STATE"):text.index("SUPERSEDED by seq-29")]
    bullets = [ln for ln in block.splitlines() if ln.startswith("- **")]
    assert bullets[0].startswith("- **2026-10-15 (E28 close-out part 1, newest)**")
    assert bullets[1].startswith("- **2026-10-15 (Qdrant pricing backfill)**")
    assert len([ln for ln in bullets if "newest" in ln]) == 1


E28_PRS = (("8572", "a5de6b1b3ac79975c5d38fbbb1c4a8280de3743e"), ("8573", "322ae68e3388a98a75097fd40682adc5ec450379"),
           ("8574", "147cdf0adfae8f79262167f67b4dbcae1a92c1db"))
E28_HEADS = "- 2026-10-15 (M5, visaoracle E28 lane, ledger E28 close-out part 1"
E28_AUDIT = REPO / "research/visa/2026-10-15-e28-family-audit.md"
E28_PAGES = REPO / "research/visa/2026-10-15-e28-pages"


def _e28_entry() -> str:
    text = LOG.read_text(encoding="utf-8")
    heads = [ln for ln in text.splitlines() if ln.startswith(E28_HEADS)]
    assert len(heads) == 1
    start = text.index(heads[0])
    return " ".join(text[start:text.index("\n- 20", start + 1)].split())


def test_e28_entry_carries_the_three_prs_with_full_merge_shas_once():
    body = _e28_entry()
    for pr, sha in E28_PRS:
        assert body.count(f"#{pr},") == 1 and body.count(f"merge `{sha}`") == 1, pr
    for token in ("run 38773190405", "2026-10-15T17:29:34Z", "dpl_AqVLBbqnCtsEgTzWyS9Py9oxrt97", "dpl_6CjUnBMaW3GVGT7RhAYDSAfj1pB5",
                  "scripts/ci/observe_zantara_e28_1015.py", "scripts/ci/observe_visa_oracle_stay_permit_length.py",
                  "Stay of 730 days (2 years), extendable online by the sponsor.", "All-inclusive price: government fees and Bali Zero service included.",
                  "user-agent `bz-synthetic-prove-live-20261016`", "the renewal line is present, which is true per page df3ba889:69,72",
                  "the lease was taken and released, the phone left locked", "session gate receipts, not repo paths",
                  "except PR B, which had none", "(7) NOT done:"):
        assert body.count(token) == 1, token


def test_e28_entry_closes_no_row_and_ships_the_audit_matrix_with_the_pages_on_main():
    body = _e28_entry()
    assert "No row is closed." in body
    assert "already on main via #8572" in body
    assert E28_AUDIT.is_file() and E28_AUDIT.read_text(encoding="utf-8").startswith("---")
    assert len(list(E28_PAGES.rglob("*.txt"))) == 6 and (E28_PAGES / "e28-pages.receipts.jsonl").is_file()


def test_skill_live_state_leads_with_the_e28_closeout_and_stays_an_index():
    text = SKILL.read_text(encoding="utf-8")
    block = text[text.index("## LIVE STATE"):text.index("SUPERSEDED by seq-29")]
    lead = block[block.index("- **2026-10-15 (E28 close-out part 1, newest)"):block.index("- **2026-10-15 (Qdrant pricing backfill)")]
    for pr, sha in E28_PRS:
        assert lead.count(f"#{pr} (`{sha[:10]}`") == 1, pr
    for token in ("**Open:**", "C2", "SEQ29-A2", "SEQ29-D1", "READY-TO-SIGN", "research/visa/2026-10-15-e28-family-audit.md"):
        assert token in lead, token
    assert len(lead) < 2600


E28_OPENED = (
    ("C2: the KB data PR #8578 is MERGED", "migration 128", "owner: me (next session; the PROD data op is operator-run)"),
    ("D: the article PR", "/visa/kitas", "owner: me (next session)"),
    ("E: seq-30 is owned by the Pro conductor", "SEQ29-D1", "owner: me (next session, visa-night conductor and signer)"),
    ("BACKLOG of the E28 close-out", "F73", "owner: me (nuzantara-57)"),
)


def test_e28_opened_rows_each_appear_once_in_the_ledger_format():
    opened = [r for r in ARMS_LINES if r.startswith("- opened 2026-10-15 (M5, VISA-ORACLE E28 close-out)")]
    assert len(opened) == len(E28_OPENED) == 4
    for needle, token, owner in E28_OPENED:
        rows = [r for r in opened if needle in r]
        assert len(rows) == 1, needle
        fields = rows[0].split(" | ")
        assert len(fields) == 5 and token in fields[1] and fields[3] == owner, needle
        assert fields[2].startswith("missing arming step:") and fields[4].startswith("proof-of-armed:"), needle
    assert not [r for r in ARMS_LINES if r.startswith("- closed") and "VISA-ORACLE E28 close-out" in r]


def test_e28_backlog_row_carries_every_item_once():
    row = _rows("BACKLOG of the E28 close-out")[0]
    for token in ("F5, the E28 documents catalogue", "F54, the Golden codes in the legacy enum", "F73, `services_data.ts:125` passport 18 months",
                  "`golden-visa-2026-updates.mdx:49,65`", "`indonesia-golden-visa-2025-no-sponsor-no-merp-usd-25m-minimum.mdx:38`",
                  "about 20 other investor/golden articles", "a Qdrant re-embed", "`visa_check.py:166` 25 days", "IMTA mentions left in KG routes",
                  "`services_data.ts:165` KITAP", "`FunnelFeature.tsx:80`", "Last updated: April 2026", "government-fee inclusion for non-visa services",
                  "Investor KITAS notes are empty", "extensions_possible 1 for E28A", "\"Covers 730 days\" but the pack has 180+180", "assumes a foreign branch",
                  "(16) E28B-F metadata.bali_zero_service is false", "(17) the retired E28G row still has foreign_eligible true"):
        assert row.count(token) == 1, token


def test_e28_c2_production_addendum_is_stated_as_given_and_the_row_stays_open():
    body = _e28_entry()
    for token in ("PR C2 #8578, merge `5fe495bb02`", 'printed "COMMITTED: 6 row(s) updated"', 'a second run printed "NO-OP: every row already matches every target field"',
                  "2026-10-15T18:42:46Z", "PROD B (Qdrant visa_oracle payload fixer): NOT RUN", "Nothing was written to Qdrant",
                  "stated as given by the Dux, not re-measured", "vo-e28-qdrant-id-1016", "C2 stays OPEN after PROD A",
                  "PROD A committed, PROD B not run; open = the Qdrant run (fix PR #8584, armed), the article PR (D) and seq-30 (E)",
                  "PR #8584 (head `29778d03ed`, gate PASS, armed", 'E28A cost_visa "IDR'):
        assert body.count(token) == 1, token
    assert "KB data PR not merged" not in body and "still open.**" not in body
    row = _rows("C2: the KB data PR #8578 is MERGED")[0]
    assert 'E28A cost_visa "IDR' in row and "PR #8584 (head `29778d03ed`" in row
    assert row.startswith("- opened 2026-10-15") and "so the row stays OPEN" in row
    for token in ('"COMMITTED: 6 row(s) updated"', '"NO-OP: every row already matches every target field"', "PROD B (Qdrant visa_oracle payload fixer): the dry-run refused with exit 3",
                  "plans 7 changes", "0 pending", "no E28G point is left"):
        assert row.count(token) == 1, token
    assert not [r for r in ARMS_LINES if r.startswith("- closed") and "VISA-ORACLE E28 close-out" in r]


def test_observer_floor_is_the_true_count_of_this_file():
    import re

    own = len(re.findall(r"^def test_", Path(__file__).read_text(encoding="utf-8"), flags=re.M))
    observer = (REPO / "scripts/ci/observe_visa_ledger_seq29.py").read_text(encoding="utf-8")
    assert int(re.search(r"^MIN_TESTS = (\d+)$", observer, flags=re.M).group(1)) == own
