"""Regression coverage for the sixth Claude OAuth subscription slot.

Renamed 2026-08-23 (Zero ruling) from ``test_claude_oauth_slot5_coverage.py``.
Slot 6 is the Claude Team seat (``zero@balizero.com``) — it enters the
cascade ONLY as a last resort: the five MAX seats (1-5) are tried first,
and slot 6 is reached only if all five fail. That property is obtained
from LIST POSITION, not from any special-cased logic, so slot 6 must
always be appended after slot 5 in every consumer — never inserted
in the middle, never reordered ahead of a MAX seat.
"""

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

SLOT6_CONSUMERS = (
    ("infra/launchagents/wrappers/cron-agent.sh", "for i in 1 2 3 4 5 6; do"),
    (
        "infra/launchagents/wrappers/wr2-ig-metrics-analyst-run.sh",
        "CLAUDE_CODE_OAUTH_TOKEN_6",
    ),
    ("scripts/ai-dispatch.sh", '"CLAUDE_CODE_OAUTH_TOKEN_6"'),
    (
        "infra/launchagents/wrappers/claude-cascade.sh",
        "CLAUDE_CODE_OAUTH_TOKEN_6",
    ),
    ("scripts/wr3_dispatch_v2.py", "range(1, 7)"),
    ("scripts/dlq_autopilot.py", "for i in (1, 2, 3, 4, 5, 6):"),
    ("scripts/wr2_html_renderer/claude_vision.py", "for index in (1, 2, 3, 4, 5, 6):"),
    ("scripts/zantara-gateway/claude_client.py", "for i in (1, 2, 3, 4, 5, 6):"),
    ("apps/backend-rag/scripts/auto_verifier.py", "for i in (1, 2, 3, 4, 5, 6):"),
    ("apps/backend-rag/scripts/verified_generator.py", "for i in (1, 2, 3, 4, 5, 6):"),
    ("apps/bali-intel-scraper/scripts/bz_image_style.py", "for i in (1, 2, 3, 4, 5, 6):"),
    (
        "apps/evaluator/nlm_deep_research/t4_monitor.py",
        "for index in (1, 2, 3, 4, 5, 6):",
    ),
    (
        "apps/mata-garuda/mata_garuda/agents/daily_briefing_agent.py",
        "claude_token_chain",
    ),
    (
        "apps/mata-garuda/mata_garuda/agents/weekly_digest_agent.py",
        "claude_token_chain",
    ),
    (
        "apps/mata-garuda/mata_garuda/runtime/cli_runtime.py",
        '"CLAUDE_CODE_OAUTH_TOKEN_6"',
    ),
    ("apps/mata-garuda/scripts/run_ai_digest.py", "claude_token_chain"),
)


@pytest.mark.parametrize(("relative_path", "slot6_sentinel"), SLOT6_CONSUMERS)
def test_every_automation_consumer_reaches_slot6(
    relative_path: str,
    slot6_sentinel: str,
) -> None:
    source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")

    assert slot6_sentinel in source, (
        f"{relative_path} no longer reaches CLAUDE_CODE_OAUTH_TOKEN_6"
    )


def test_mata_runtime_documents_all_six_slot_identities() -> None:
    """The CLAUDE_TOKEN_VARS comment map was verified stale on 2026-08-23
    (Zero ruling): every slot but 1 carried a wrong identity comment,
    including a "RETIRED, slot libero" note for slot 3 that was re-armed
    the same day it was written. This pins the corrected, verified map so
    a future edit cannot silently reintroduce stale identities."""
    source = (
        REPO_ROOT / "apps/mata-garuda/mata_garuda/runtime/cli_runtime.py"
    ).read_text(encoding="utf-8")

    assert '"CLAUDE_CODE_OAUTH_TOKEN_1",  # antonellosiano@gmail.com (MAX 20x)' in source
    assert '"CLAUDE_CODE_OAUTH_TOKEN_2",  # sianoantonello@gmail.com (MAX 20x)' in source
    assert (
        '"CLAUDE_CODE_OAUTH_TOKEN_3",  # applevisionpro1987@gmail.com (MAX 20x)'
        in source
    )
    assert '"CLAUDE_CODE_OAUTH_TOKEN_4",  # antozero1987@gmail.com (MAX 20x)' in source
    assert (
        '"CLAUDE_CODE_OAUTH_TOKEN_5",  # kaiser198719871987@gmail.com (MAX 20x)'
        in source
    )
    assert (
        '"CLAUDE_CODE_OAUTH_TOKEN_6",  '
        "# zero@balizero.com (Team premium seat — weekly-capped, LAST RESORT)"
    ) in source


# ── Ordering proof: slot 6 must sit AFTER slot 5 ────────────────────────────
#
# "Last resort" is a property of POSITION, not of any special-cased logic —
# so the mechanical guarantee has to be that slot 6's marker never appears
# before slot 5's marker in source. Three shapes exist across the 16
# consumers:
#
#   (a) two independent, order-comparable markers (numbered-var / array /
#       list / shell-case consumers) — compared directly via str.index();
#   (b) a single shared tuple literal `(1, 2, 3, 4, 5, 6)` (the 7 Python
#       files that loop `for <var> in (1, 2, 3, 4, 5, 6):`) — there slot 6
#       can only ever be textually after slot 5 (it is one literal), so the
#       meaningful proof is that 6 was APPENDED at the tuple's tail rather
#       than inserted before 5 (e.g. never `(1, 2, 3, 4, 6, 5)` or
#       `(6, 1, 2, 3, 4, 5)`).
#   (c) a `range(1, 7)` call (scripts/wr3_dispatch_v2.py) — order is
#       guaranteed by construction (a range is monotonic), so there is no
#       marker pair to compare; the meaningful proof is the endpoint (7,
#       exclusive) and the slot-6 label, covered by its own test below.
#
# The 3 mata-garuda callers (daily_briefing_agent.py / weekly_digest_agent.py
# / run_ai_digest.py) only import `claude_token_chain` — they carry no order
# of their own to prove; the ordering guarantee lives entirely in
# cli_runtime.py, already covered below.

ORDER_MARKER_CONSUMERS = (
    (
        "infra/launchagents/wrappers/cron-agent.sh",
        "CLAUDE_CODE_OAUTH_TOKEN_{1,2,3,4,5}",
        "CLAUDE_CODE_OAUTH_TOKEN_6",
    ),
    (
        "infra/launchagents/wrappers/wr2-ig-metrics-analyst-run.sh",
        "CLAUDE_CODE_OAUTH_TOKEN_5",
        "CLAUDE_CODE_OAUTH_TOKEN_6",
    ),
    (
        "scripts/ai-dispatch.sh",
        '"CLAUDE_CODE_OAUTH_TOKEN_5"',
        '"CLAUDE_CODE_OAUTH_TOKEN_6"',
    ),
    (
        "apps/mata-garuda/mata_garuda/runtime/cli_runtime.py",
        '"CLAUDE_CODE_OAUTH_TOKEN_5"',
        '"CLAUDE_CODE_OAUTH_TOKEN_6"',
    ),
    (
        "infra/launchagents/wrappers/claude-cascade.sh",
        "${CLAUDE_CODE_OAUTH_TOKEN_5:-}",
        "${CLAUDE_CODE_OAUTH_TOKEN_6:-}",
    ),
)


@pytest.mark.parametrize(
    ("relative_path", "slot5_marker", "slot6_marker"), ORDER_MARKER_CONSUMERS
)
def test_slot6_marker_follows_slot5_marker(
    relative_path: str,
    slot5_marker: str,
    slot6_marker: str,
) -> None:
    source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")

    assert slot5_marker in source, f"{relative_path}: slot-5 marker missing"
    assert slot6_marker in source, f"{relative_path}: slot-6 marker missing"
    assert source.index(slot6_marker) > source.index(slot5_marker), (
        f"{relative_path}: slot 6 appears BEFORE slot 5 in source — the "
        "Team seat must be last-resort by position, never reordered ahead "
        "of a MAX seat"
    )


TUPLE_LOOP_CONSUMERS = (
    "scripts/dlq_autopilot.py",
    "scripts/wr2_html_renderer/claude_vision.py",
    "scripts/zantara-gateway/claude_client.py",
    "apps/backend-rag/scripts/auto_verifier.py",
    "apps/backend-rag/scripts/verified_generator.py",
    "apps/bali-intel-scraper/scripts/bz_image_style.py",
    "apps/evaluator/nlm_deep_research/t4_monitor.py",
)


@pytest.mark.parametrize("relative_path", TUPLE_LOOP_CONSUMERS)
def test_tuple_loop_appends_slot6_after_slot5(relative_path: str) -> None:
    """These 7 consumers share one seat-loop shape:
    ``for <var> in (1, 2, 3, 4, 5, 6):``. It is one literal, so "6 after 5"
    cannot be proven by comparing two independent marker positions (that is
    what test_slot6_marker_follows_slot5_marker does for the other shape) —
    instead this proves slot 6 was APPENDED at the tuple's tail, not
    inserted before slot 5."""
    source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")

    assert "4, 5, 6)" in source, (
        f"{relative_path}: slot 6 is not the last element of the seat "
        "tuple — the Team seat must be appended after slot 5, never "
        "inserted mid-tuple"
    )


def test_wr3_dispatch_v2_range_covers_slot6_with_correct_label() -> None:
    """``scripts/wr3_dispatch_v2.py::_collect_claude_seats`` used
    ``range(1, 6)`` (slots 1-5 only, exclusive upper bound) with a
    ``"slot5-team"`` label wired to slot 5 — both stale as of the
    2026-08-23 remap that moved the Team seat to slot 6. A ``range()`` call
    is monotonic by construction (unlike a hand-written tuple/list it
    cannot be reordered to put 6 ahead of 5), so the meaningful proof here
    is the endpoint and the label, not an index() comparison."""
    source = (REPO_ROOT / "scripts/wr3_dispatch_v2.py").read_text(encoding="utf-8")

    assert "range(1, 7)" in source, (
        "the seat loop must run through slot 6 (range(1, 7), exclusive upper "
        "bound) — range(1, 6) stops at slot 5 and never reaches the Team seat"
    )
    assert "range(1, 6)" not in source, (
        "a stale range(1, 6) alongside range(1, 7) would mean a second, "
        "unconverted seat loop exists"
    )
    assert 'label = "slot6-team" if slot == 6 else f"slot{slot}"' in source, (
        "the Team label must be wired to slot == 6, not slot == 5"
    )
    assert "slot5-team" not in source, (
        "the stale 'slot5-team' label must not survive the slot-6 remap — "
        "slot 5 is a plain MAX seat now"
    )


def test_claude_cascade_team_config_dir_only_on_slot6() -> None:
    """The 2026-08-23 slot remap broke silently once already: slot 5 kept
    pointing at ``$HOME/.claude-zero-team`` (the Team profile) and slot 5's
    label still said "team", even after the Team seat itself moved to
    slot 6. This proves the slot<->profile coupling mechanically by parsing
    each numbered case branch out of the picker and asserting the Team
    config dir and any "team"-naming label appear in the slot-6 branch and
    nowhere else."""
    source = (REPO_ROOT / "infra/launchagents/wrappers/claude-cascade.sh").read_text(
        encoding="utf-8"
    )

    branches = dict(re.findall(r"\n {8}(\d)\)\n(.*?)\n {12};;", source, flags=re.DOTALL))
    assert set(branches) == {"1", "2", "3", "4", "5", "6"}, (
        f"expected exactly 6 numbered case branches in the OAuth seat "
        f"picker, found {sorted(branches)}"
    )

    for slot, body in branches.items():
        has_team_config_dir = ".claude-zero-team" in body
        has_team_label = "team" in body.lower()
        if slot == "6":
            assert has_team_config_dir, "slot 6 must select the Team config dir"
            assert has_team_label, "slot 6's label should name it as the Team seat"
        else:
            assert not has_team_config_dir, (
                f"slot {slot} points at the Team config dir "
                "($HOME/.claude-zero-team) — that is exactly how the "
                "2026-08-23 remap broke (slot 5 kept the old Team profile "
                "after the Team seat moved to slot 6)"
            )
            assert not has_team_label, (
                f"slot {slot}'s label must not mention 'team' — only slot 6 "
                "is the Team seat"
            )
