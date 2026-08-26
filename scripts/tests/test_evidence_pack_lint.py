"""Tests for scripts/evidence_pack_lint.py (PR-3, fleet-order harness).

The script carries its own hermetic --selftest fixture (guilt+innocence over
every rule); this file makes pytest/CI run it AND pins each `check_*` guard's
verdict function directly, by name, for the guard-conformance registry
(superscar #3: "nessuna guardia mergiata senza un test di innocenza E di
colpevolezza" — each guard needs BOTH proofs registered).
"""

from __future__ import annotations

import datetime
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"

sys.path.insert(0, str(SCRIPTS))
from evidence_pack_lint import (  # noqa: E402
    LANES_NON_ANTHROPIC_ENFORCEMENT_DATE,
    SEAT_RULES_ENFORCEMENT_DATE,
    _is_anthropic_seat,
    _seat_rule_verdict,
    check_brief_ref_exists,
    check_dissent_nonempty_on_gear3,
    check_gear_floor,
    check_ground_truth_lane,
    check_lanes_build_seat_diversity,
    check_pii_local_seat,
    check_pii_scan_clean,
    check_receipts_have_provenance,
    check_size_budget,
    compute_ceiling,
    compute_floor,
    effort_for_gear,
    lint,
    sum_numstat,
)

GOOD_RECEIPT = {
    "claim": "tests pass", "cmd": "pytest -q", "exit": 0,
    "ts": "2026-08-10T00:00:00Z", "seat": "sonnet-5",
}


@pytest.fixture()
def tmp_repo(tmp_path):
    """A tempdir standing in for repo_root, with evidence/brief.yml + pack.yml
    writable helpers."""

    def write_brief(**overrides):
        brief = {"task_id": "ops-test", "gear": 1, "grader": "codex-sol"}
        brief.update(overrides)
        p = tmp_path / "evidence" / "brief.yml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump(brief, sort_keys=False), encoding="utf-8")
        return p

    def write_pack(**overrides):
        pack = {
            "brief_ref": "evidence/brief.yml",
            "receipts": [GOOD_RECEIPT],
            "dissent": [],
            "pii_scan": "clean",
            # Rule 8 (D3 lane-declaration) went live at 2026-08-24 UTC midnight.
            # Before that date a Gear>=2 pack with no `lanes` got a NOTICE; after
            # it, a hard violation. These fixtures exist to exercise OTHER rules,
            # so they carry a conformant block rather than riding a grace period
            # that has now expired — otherwise every Gear>=2 test here fails for
            # a reason it was never written to test. Rule 8's own guilt and
            # innocence live in the `check_lanes_build_seat_diversity` tests,
            # which pin `today` on both sides of the flip and call the function
            # directly, so they are unaffected by this default. A test that needs
            # `lanes` absent or malformed overrides it explicitly.
            "lanes": [{"lane": "D1", "role": "build", "seat": "codex"}],
        }
        pack.update(overrides)
        p = tmp_path / "evidence" / "pack.yml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump(pack, sort_keys=False), encoding="utf-8")
        return p

    return tmp_path, write_brief, write_pack


# --------------------------------------------------------- check_receipts_have_provenance


def test_receipts_guilt_missing_field_rejected():
    """GUILT: a receipt entry missing `cmd` is not a receipt."""
    violations = check_receipts_have_provenance(
        {"receipts": [{"claim": "no cmd here", "exit": 0, "ts": "x", "seat": "y"}]}
    )
    assert violations
    assert "cmd" in violations[0]


def test_receipts_innocence_complete_receipt_passes():
    """INNOCENCE: a fully-shaped receipt is not flagged; a pack with no
    receipts key at all is also not this rule's problem."""
    assert check_receipts_have_provenance({"receipts": [GOOD_RECEIPT]}) == []
    assert check_receipts_have_provenance({}) == []


def test_receipts_guilt_empty_on_gear3_rejected():
    """GUILT (adversarial-review 2026-08-10): a Gear-3 pack with zero/missing
    receipts carries no evidence — symmetric with the dissent rule."""
    assert check_receipts_have_provenance({}, gear=3) != []
    assert check_receipts_have_provenance({"receipts": []}, gear=3) != []


def test_receipts_innocence_empty_on_gear1_passes():
    """INNOCENCE: the same empty/missing receipts shape is NOT this rule's
    problem below Gear-3 — an empty evidence pack may legitimately have no
    claims yet on Gear 1/2."""
    assert check_receipts_have_provenance({}, gear=1) == []
    assert check_receipts_have_provenance({"receipts": []}, gear=2) == []


# --------------------------------------------------------- check_dissent_nonempty_on_gear3


def test_dissent_guilt_zero_dissent_on_gear3_rejected():
    """GUILT: dissent=[] on a Gear-3 pack is 'consenso sospetto'."""
    violations = check_dissent_nonempty_on_gear3({"dissent": []}, gear=3)
    assert violations
    assert "consenso sospetto" in violations[0]


def test_dissent_guilt_missing_field_rejected():
    """GUILT: the dissent key must always exist — it is mandatory, not just
    non-empty-conditionally."""
    assert check_dissent_nonempty_on_gear3({}, gear=1) != []


def test_dissent_innocence_empty_on_gear2_passes():
    """INNOCENCE: an empty dissent list is fine below Gear-3."""
    assert check_dissent_nonempty_on_gear3({"dissent": []}, gear=2) == []
    assert check_dissent_nonempty_on_gear3({"dissent": []}, gear=1) == []


def test_dissent_innocence_nonempty_on_gear3_passes():
    """INNOCENCE: a Gear-3 pack with at least one dissent entry passes."""
    entry = [{"seat": "codex-sol", "objection": "x", "status": "PLAUSIBLE"}]
    assert check_dissent_nonempty_on_gear3({"dissent": entry}, gear=3) == []


def test_dissent_guilt_entry_missing_fields_rejected():
    """GUILT (adversarial-review 2026-08-10): `dissent: [{}]` used to pass
    purely on list length — each entry now needs seat/objection/status."""
    violations = check_dissent_nonempty_on_gear3({"dissent": [{}]}, gear=1)
    assert violations
    assert "missing/empty field(s)" in violations[0]


def test_dissent_guilt_invalid_status_rejected():
    """GUILT: a dissent entry's status must be one of the closed set
    {CONFIRMED, PLAUSIBLE, RETRACTED} — a plausible-looking impostor like
    'APPROVED' is rejected, not accepted by shape alone."""
    entry = [{"seat": "codex-sol", "objection": "x", "status": "APPROVED"}]
    violations = check_dissent_nonempty_on_gear3({"dissent": entry}, gear=1)
    assert violations
    assert "status" in violations[0]


def test_dissent_innocence_structured_entry_passes():
    """INNOCENCE: a fully-shaped dissent entry with a valid status is not
    flagged, on Gear-1 (any status) and Gear-3 (needs >=1 too, already
    covered above)."""
    entry = [{"seat": "codex-sol", "objection": "x", "status": "RETRACTED"}]
    assert check_dissent_nonempty_on_gear3({"dissent": entry}, gear=1) == []


# --------------------------------------------------------- check_pii_scan_clean


def test_pii_scan_guilt_dirty_value_rejected():
    """GUILT: any pii_scan value other than the literal 'clean' is rejected."""
    assert check_pii_scan_clean({"pii_scan": "dirty"}) != []
    assert check_pii_scan_clean({}) != []


def test_pii_scan_innocence_clean_value_passes():
    """INNOCENCE: pii_scan == 'clean' passes."""
    assert check_pii_scan_clean({"pii_scan": "clean"}) == []


# --------------------------------------------------------- check_size_budget


def test_size_guilt_oversize_rejected():
    """GUILT: one byte over the 30k-token cap (4 bytes/token approx) fails."""
    from evidence_pack_lint import SIZE_TOKEN_CAP

    assert check_size_budget(b"x" * (SIZE_TOKEN_CAP * 4 + 4)) != []


def test_size_innocence_at_cap_passes():
    """INNOCENCE: a pack exactly at the cap boundary passes."""
    from evidence_pack_lint import SIZE_TOKEN_CAP

    assert check_size_budget(b"x" * (SIZE_TOKEN_CAP * 4)) == []


# --------------------------------------------------------- check_brief_ref_exists


def test_brief_ref_guilt_missing_key_rejected(tmp_repo):
    """GUILT: no brief_ref key at all."""
    root, _write_brief, _write_pack = tmp_repo
    violations, brief = check_brief_ref_exists({}, root)
    assert violations and brief is None


def test_brief_ref_guilt_dangling_path_rejected(tmp_repo):
    """GUILT: brief_ref names a file that does not exist on disk."""
    root, _write_brief, _write_pack = tmp_repo
    violations, brief = check_brief_ref_exists({"brief_ref": "evidence/nope.yml"}, root)
    assert violations and brief is None


def test_brief_ref_innocence_resolves_and_loads(tmp_repo):
    """INNOCENCE: a brief_ref pointing at a real, valid YAML mapping loads
    cleanly with zero violations."""
    root, write_brief, _write_pack = tmp_repo
    write_brief(gear=2)
    violations, brief = check_brief_ref_exists({"brief_ref": "evidence/brief.yml"}, root)
    assert violations == []
    assert brief == {"task_id": "ops-test", "gear": 2, "grader": "codex-sol"}


def test_brief_ref_guilt_absolute_path_rejected(tmp_repo):
    """GUILT (adversarial-review 2026-08-10): pathlib's `/` operator silently
    DISCARDS repo_root when brief_ref is absolute — `(repo_root / "/etc/x")`
    resolves to `/etc/x`. An absolute brief_ref must be rejected outright,
    never resolved."""
    root, write_brief, _write_pack = tmp_repo
    brief_path = write_brief(gear=1)
    violations, brief = check_brief_ref_exists({"brief_ref": str(brief_path)}, root)
    assert violations and brief is None
    assert "absolute" in violations[0]


def test_brief_ref_guilt_path_traversal_rejected(tmp_repo):
    """GUILT: a `../`-relative brief_ref that resolves OUTSIDE repo_root is a
    path-confinement escape — this repo has its own py/path-injection scar
    class for exactly this shape."""
    root, _write_brief, _write_pack = tmp_repo
    outside = root.parent / "outside-secret.yml"
    outside.write_text(yaml.safe_dump({"task_id": "x", "gear": 1, "grader": "y"}), encoding="utf-8")
    try:
        violations, brief = check_brief_ref_exists(
            {"brief_ref": f"../{outside.name}"}, root
        )
        assert violations and brief is None
        assert "escapes repo_root" in violations[0]
    finally:
        outside.unlink()


def test_brief_ref_guilt_directory_rejected(tmp_repo):
    """GUILT: brief_ref naming a directory (e.g. "evidence") used to raise an
    uncaught IsADirectoryError — now rejected cleanly, no crash."""
    root, write_brief, _write_pack = tmp_repo
    write_brief(gear=1)
    violations, brief = check_brief_ref_exists({"brief_ref": "evidence"}, root)
    assert violations and brief is None


# --------------------------------------------------------- check_gear_floor


def test_gear_floor_guilt_declared_below_floor_rejected():
    """GUILT: brief declares gear 1 while the diff touches a hot-zone path
    (floor 3)."""
    brief = {"gear": 1}
    changed = ["apps/backend-rag/backend/app/auth/session.py"]
    violations = check_gear_floor(brief, changed)
    assert violations
    assert "floor" in violations[0]


def test_gear_floor_innocence_declared_at_or_above_floor_passes():
    """INNOCENCE: gear 3 on the same hot-zone diff passes; gear 1 on a
    non-hot-zone diff passes too (the floor is a lower bound, not an exact
    classifier)."""
    hotzone_changed = ["apps/backend-rag/backend/app/auth/session.py"]
    assert check_gear_floor({"gear": 3}, hotzone_changed) == []
    assert check_gear_floor({"gear": 1}, ["docs/readme.md"]) == []


def test_gear_floor_innocence_skipped_without_changed_files():
    """INNOCENCE: with no changed-files context, the check adds no
    violation (the caller is responsible for surfacing the NOTICE that the
    rule was skipped, not for treating silence as a pass)."""
    assert check_gear_floor({"gear": 1}, None) == []


def test_gear_floor_guilt_bool_type_rejected():
    """GUILT (adversarial-review 2026-08-10): Python's bare `in` on a tuple
    of ints treats bool as an int (`True in (1, 2, 3)` is True), so
    `gear: true` used to silently pass as gear==1. Must be a genuine int."""
    violations = check_gear_floor({"gear": True}, None)
    assert violations
    assert "int" in violations[0]


def test_gear_floor_guilt_float_type_rejected():
    """GUILT: same coercion hole via float (`1.0 in (1, 2, 3)` is True) —
    `gear: 1.0` must be rejected too."""
    violations = check_gear_floor({"gear": 1.0}, None)
    assert violations
    assert "int" in violations[0]


# --------------------------------------------------------- compute_ceiling (pure fn)


def test_ceiling_guilt_gear3_council_on_docs_diff_rejected():
    """GUILT: a Gear-3 pack that also convened a `council` over a 1-file
    markdown diff is over-provisioned — rejected unless `gear_override`
    explains why."""
    ceiling, reasons = compute_ceiling(["docs/notes.md"], 3, {"council": True})
    assert ceiling == 1
    assert reasons
    assert reasons[0].startswith("ceiling: Gear 1 shape")
    assert "gear_override" in reasons[0]


def test_ceiling_guilt_gear3_many_grader_dispatches_on_json_diff_rejected():
    """GUILT: the same over-provisioning signal via >=3 grader dispatches
    instead of a council — ledger/json-only diff."""
    ceiling, reasons = compute_ceiling(
        ["evidence/ledger.json"], 3, {"grader_dispatches": 3}
    )
    assert ceiling == 1
    assert reasons
    assert "3 grader dispatches" in reasons[0]


def test_ceiling_innocence_gear_override_reports_not_fails():
    """INNOCENCE: the exact guilty shape above, but with a non-empty
    `gear_override` — the ceiling REPORTS (a distinguishable
    "ceiling (overridden)" line), it does not produce a violation. The
    caller (lint()) is responsible for keeping such a line out of
    `violations` — this test pins the string contract that decision relies
    on."""
    ceiling, reasons = compute_ceiling(
        ["docs/notes.md"], 3, {"council": True, "gear_override": "verified live, one-off"}
    )
    assert ceiling == 1
    assert reasons
    assert reasons[0].startswith("ceiling (overridden)")
    assert "verified live" in reasons[0]


def test_ceiling_innocence_empty_override_is_not_an_override():
    """GUILT (edge of the innocence test above): an empty/whitespace-only
    `gear_override` string does not count as "present and non-empty" — it
    must still fail like the no-override case."""
    ceiling, reasons = compute_ceiling(["docs/notes.md"], 3, {"council": True, "gear_override": "   "})
    assert ceiling == 1
    assert reasons
    assert not reasons[0].startswith("ceiling (overridden)")


def test_ceiling_innocence_hotzone_diff_floor_stands_silent():
    """INNOCENCE: the floor always wins — a hot-zone (`apps/.../auth/*`)
    docs-shaped diff floors AND ceilings at 3, silently, even with a
    council declared. Never a conflicting verdict."""
    hotzone = ["apps/backend-rag/backend/app/auth/session.py"]
    ceiling, reasons = compute_ceiling(hotzone, 3, {"council": True})
    assert ceiling == 3
    assert reasons == []


def test_ceiling_innocence_real_backend_diff_gear3_passes():
    """INNOCENCE: an 8-file, non-docs backend diff is not Gear-1-shaped by
    either predicate (not docs/json-only, more than 2 files) — a Gear-3
    declaration with a council on it is not flagged at all."""
    big_diff = [f"apps/backend-rag/backend/services/f{i}.py" for i in range(8)]
    ceiling, reasons = compute_ceiling(big_diff, 3, {"council": True})
    assert ceiling == 3
    assert reasons == []


def test_ceiling_innocence_gear3_without_council_or_graders_not_heavy():
    """INNOCENCE: a Gear-3 pack on a Gear-1-shaped diff with NO council and
    no (or <3) grader dispatches is not flagged — the ceiling only fires on
    the heavyweight signals, never on gear==3 alone."""
    assert compute_ceiling(["docs/notes.md"], 3, {}) == (1, [])
    assert compute_ceiling(["docs/notes.md"], 3, {"grader_dispatches": 2}) == (1, [])


def test_ceiling_innocence_gear1_declared_never_flagged():
    """INNOCENCE: the ceiling only concerns itself with a Gear-3
    declaration — a Gear-1-shaped diff correctly declaring gear 1 (even
    with a council key present, e.g. leftover from a template) is not
    this rule's problem."""
    assert compute_ceiling(["docs/notes.md"], 1, {"council": True}) == (1, [])


def test_ceiling_innocence_small_diff_below_net_lines_cap_flagged_too():
    """GUILT: shape predicate (b) — <=2 files, pack-declared net_lines
    <=60, outside hot zones — triggers the same over-provisioning check as
    the docs/json predicate (a)."""
    small_diff = ["apps/backend-rag/backend/services/tiny.py"]
    ceiling, reasons = compute_ceiling(small_diff, 3, {"council": True, "net_lines": 12})
    assert ceiling == 1
    assert reasons


def test_ceiling_innocence_unknown_net_lines_does_not_assert_small_shape():
    """INNOCENCE: predicate (b) requires the pack to actually DECLARE
    net_lines — a diff with no net_lines key is not assumed small just
    because it is short on files."""
    small_diff = ["apps/backend-rag/backend/services/tiny.py"]
    assert compute_ceiling(small_diff, 3, {"council": True}) == (3, [])


def test_ceiling_innocence_no_diff_context_returns_no_assertion():
    """INNOCENCE: an empty changed-paths list (no diff context) asserts
    nothing — mirrors compute_floor's None-context skip in lint()."""
    assert compute_ceiling([], 3, {"council": True}) == (3, [])


def test_ceiling_guilt_measured_overrides_pack_lie_no_false_ceiling():
    """GUILT (adversarial-review 2026-08-21, team-lead hardening): the pack
    self-declares net_lines=10 but the MEASURED value is 400 — shape (b)
    must NOT be asserted (measured wins), so a Gear-3 + council pack over
    this 2-file non-hot-zone diff is NOT flagged. Without this precedence,
    an author could dodge the ceiling entirely by under-reporting net_lines
    in the pack."""
    diff = ["apps/backend-rag/backend/services/a.py", "apps/backend-rag/backend/services/b.py"]
    ceiling, reasons = compute_ceiling(
        diff, 3, {"net_lines": 10, "council": True}, measured_net_lines=400
    )
    assert ceiling == 3
    assert reasons == []


def test_ceiling_guilt_measured_used_when_pack_omits_net_lines():
    """GUILT, the reverse case: the pack OMITS net_lines entirely, but a
    measured value of 20 is supplied — shape (b) IS asserted from the
    measured value alone, and the gear-3+council over-provisioning is
    flagged."""
    diff = ["apps/backend-rag/backend/services/a.py", "apps/backend-rag/backend/services/b.py"]
    ceiling, reasons = compute_ceiling(diff, 3, {"council": True}, measured_net_lines=20)
    assert ceiling == 1
    assert reasons
    assert reasons[0].startswith("ceiling: Gear 1 shape")
    # measured source -> no self-declared notice anywhere in reasons
    assert not any("self-declared" in r for r in reasons)


def test_ceiling_innocence_self_declared_net_lines_emits_notice():
    """INNOCENCE (still passes/fails on its own merits) + NOTICE: when NO
    measured value is supplied and the pack alone carries net_lines, the
    self-declared value is still used for shape (b), but a distinguishable
    "ceiling (notice)" line names the lower-trust source — never a
    violation on its own."""
    diff = ["apps/backend-rag/backend/services/a.py", "apps/backend-rag/backend/services/b.py"]
    ceiling, reasons = compute_ceiling(diff, 3, {"council": True, "net_lines": 20})
    assert ceiling == 1
    assert any(r.startswith("ceiling (notice): net_lines self-declared") for r in reasons)
    # AND the primary guilt reason (no override) is still present, first
    assert reasons[0].startswith("ceiling: Gear 1 shape")


def test_ceiling_innocence_self_declared_notice_does_not_fire_when_measured_present():
    """INNOCENCE: supplying a measured value suppresses the self-declared
    notice entirely, even if the pack ALSO carries its own net_lines."""
    diff = ["apps/backend-rag/backend/services/a.py", "apps/backend-rag/backend/services/b.py"]
    ceiling, reasons = compute_ceiling(
        diff, 3, {"council": True, "net_lines": 999}, measured_net_lines=20
    )
    assert ceiling == 1
    assert not any("self-declared" in r for r in reasons)


def test_lint_end_to_end_measured_net_lines_overrides_pack_lie(tmp_repo):
    """GUILT/INNOCENCE wired through lint(): the pack lies (net_lines=10)
    but the caller supplies the real measured value (400) via lint()'s
    measured_net_lines parameter — no false ceiling."""
    root, write_brief, write_pack = tmp_repo
    write_brief(gear=3)
    pack_path = write_pack(
        dissent=[{"seat": "codex-sol", "objection": "x", "status": "PLAUSIBLE"}],
        council=True,
        net_lines=10,
    )
    diff = ["apps/backend-rag/backend/services/a.py", "apps/backend-rag/backend/services/b.py"]
    rc, violations = lint(pack_path, root, diff, measured_net_lines=400)
    assert rc == 0
    assert violations == []


# --------------------------------------------------------- sum_numstat (pure fn)


def test_sum_numstat_basic_sum():
    text = "10\t2\tfoo.py\n5\t0\tbar.py\n"
    assert sum_numstat(text) == (10 - 2) + (5 - 0)


def test_sum_numstat_skips_binary_files():
    """Binary files report "-\t-\tpath" per git's numstat format — their
    line count is unknowable, not zero, so they must be excluded rather
    than counted as 0/0."""
    text = "10\t2\tfoo.py\n-\t-\timage.png\n"
    assert sum_numstat(text) == 8


def test_sum_numstat_empty_and_malformed_lines_ignored():
    assert sum_numstat("") == 0
    assert sum_numstat("\n\n") == 0
    assert sum_numstat("not-a-numstat-line\n10\t2\tfoo.py\n") == 8


# --------------------------------------------------------- effort_for_gear (pure fn)


def test_effort_for_gear_mapping():
    """Gear 1 -> medium (the cost/latency lever for routine turns); Gear 2
    and Gear 3 -> xhigh. `max` is never returned — it is an explicit,
    opt-in escalation a session makes by hand, never this function's
    default for any gear."""
    assert effort_for_gear(1) == "medium"
    assert effort_for_gear(2) == "xhigh"
    assert effort_for_gear(3) == "xhigh"


def test_effort_for_gear_guilt_invalid_gear_raises():
    """GUILT: a gear outside {1,2,3} raises rather than guessing."""
    with pytest.raises(ValueError):
        effort_for_gear(4)
    with pytest.raises(ValueError):
        effort_for_gear(0)


def test_effort_for_gear_guilt_bool_type_rejected():
    """GUILT: same bool-is-an-int coercion trap check_gear_floor already
    guards against (`True in (1,2,3)` is True in bare Python) — gear must
    be a genuine int."""
    with pytest.raises(ValueError):
        effort_for_gear(True)


# --------------------------------------------------------- compute_floor (pure fn)


def test_compute_floor_guilt_hotzone_hit_returns_three():
    assert compute_floor(["fly.toml"]) == 3
    assert compute_floor([".github/workflows/anything.yml"]) == 3


def test_compute_floor_innocence_ordinary_files_return_one():
    assert compute_floor(["docs/x.md", "research/operations/y.md"]) == 1
    assert compute_floor([]) == 1


# --------------------------------------------------------- end-to-end lint()


def test_lint_end_to_end_innocent_pack_passes(tmp_repo):
    root, write_brief, write_pack = tmp_repo
    write_brief(gear=1)
    pack_path = write_pack()
    rc, violations = lint(pack_path, root, None)
    assert rc == 0 and violations == []


def test_lint_end_to_end_guilt_ceiling_gear3_council_docs_diff(tmp_repo):
    """GUILT, wired through lint(): a Gear-3 pack with a council over a
    docs-only diff fails, naming gear_override in the violation."""
    root, write_brief, write_pack = tmp_repo
    write_brief(gear=3)
    pack_path = write_pack(
        dissent=[{"seat": "codex-sol", "objection": "x", "status": "PLAUSIBLE"}],
        council=True,
    )
    rc, violations = lint(pack_path, root, ["docs/notes.md"])
    assert rc == 1
    assert any("gear_override" in v for v in violations)


def test_lint_end_to_end_innocence_ceiling_override_reports_not_fails(tmp_repo):
    """INNOCENCE, wired through lint(): the exact same guilty shape, but
    with gear_override set — lint() must NOT add the "(overridden)" reason
    to violations, so the pack passes clean."""
    root, write_brief, write_pack = tmp_repo
    write_brief(gear=3)
    pack_path = write_pack(
        dissent=[{"seat": "codex-sol", "objection": "x", "status": "PLAUSIBLE"}],
        council=True,
        gear_override="verified live, one-off",
    )
    rc, violations = lint(pack_path, root, ["docs/notes.md"])
    assert rc == 0
    assert violations == []


def test_lint_end_to_end_blind_on_missing_pack(tmp_repo):
    root, _write_brief, _write_pack = tmp_repo
    rc, violations = lint(root / "evidence" / "absent.yml", root, None)
    assert rc == 2


def test_selftest_corpus_passes():
    """The script's own embedded guilt+innocence corpus must pass on this
    tree (subprocess, so it exercises the real CLI entry point too)."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "evidence_pack_lint.py"), "--selftest"],
        capture_output=True, text=True, timeout=60, cwd=str(REPO),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_print_floor_cli_matches_compute_floor(tmp_path):
    """The --print-floor CLI mode and the pure compute_floor() function must
    agree — it is the single source of truth harness-floor.yml consumes."""
    changed = tmp_path / "changed.txt"
    changed.write_text("fly.toml\ndocs/readme.md\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "evidence_pack_lint.py"),
         "--print-floor", "--changed-files-file", str(changed)],
        capture_output=True, text=True, timeout=30, cwd=str(REPO),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert int(proc.stdout.strip()) == compute_floor(["fly.toml", "docs/readme.md"]) == 3


def test_effort_for_cli_matches_effort_for_gear():
    """The --effort-for CLI mode agrees with the pure function, and exits
    with a usage error (3) on an invalid gear rather than printing garbage."""
    for gear in (1, 2, 3):
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "evidence_pack_lint.py"), "--effort-for", str(gear)],
            capture_output=True, text=True, timeout=30, cwd=str(REPO),
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert proc.stdout.strip() == effort_for_gear(gear)

    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "evidence_pack_lint.py"), "--effort-for", "9"],
        capture_output=True, text=True, timeout=30, cwd=str(REPO),
    )
    assert proc.returncode == 3


def _write_full_tree(tmp_path, *, gear, pack_overrides):
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "brief.yml").write_text(
        yaml.safe_dump({"task_id": "ops-test", "gear": gear, "grader": "codex-sol"}),
        encoding="utf-8",
    )
    pack = {
        "brief_ref": "evidence/brief.yml",
        "receipts": [GOOD_RECEIPT],
        "dissent": [{"seat": "codex-sol", "objection": "x", "status": "PLAUSIBLE"}],
        "pii_scan": "clean",
        # See the identical note on `write_pack` above: rule 8 became enforcing
        # at 2026-08-24 UTC midnight, and these fixtures test the ceiling and
        # net-lines rules, not lane declaration.
        "lanes": [{"lane": "D1", "role": "build", "seat": "codex"}],
    }
    pack.update(pack_overrides)
    (tmp_path / "evidence" / "pack.yml").write_text(
        yaml.safe_dump(pack, sort_keys=False), encoding="utf-8"
    )
    return tmp_path / "evidence" / "pack.yml"


def test_net_lines_cli_flag_overrides_pack_lie_end_to_end(tmp_path):
    """--net-lines, given a diff shaped like predicate (b), wins over the
    pack's own (lying) net_lines field — reaching compute_ceiling() through
    the full CLI entry point, not just lint() called in-process."""
    pack_path = _write_full_tree(
        tmp_path, gear=3, pack_overrides={"council": True, "net_lines": 10}
    )
    changed = tmp_path / "changed.txt"
    changed.write_text(
        "apps/backend-rag/backend/services/a.py\n"
        "apps/backend-rag/backend/services/b.py\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable, str(SCRIPTS / "evidence_pack_lint.py"),
            str(pack_path), "--repo-root", str(tmp_path),
            "--changed-files-file", str(changed), "--net-lines", "400",
        ],
        capture_output=True, text=True, timeout=30, cwd=str(REPO),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr  # measured wins -> no false ceiling


def test_numstat_file_cli_flag_wired_end_to_end(tmp_path):
    """--numstat-file sums via sum_numstat() and reaches compute_ceiling()
    through the CLI, flagging the same gear-3+council over-provisioning
    --net-lines would (pack omits net_lines entirely here)."""
    pack_path = _write_full_tree(tmp_path, gear=3, pack_overrides={"council": True})
    changed = tmp_path / "changed.txt"
    changed.write_text(
        "apps/backend-rag/backend/services/a.py\n"
        "apps/backend-rag/backend/services/b.py\n",
        encoding="utf-8",
    )
    numstat = tmp_path / "numstat.txt"
    numstat.write_text("15\t5\tapps/backend-rag/backend/services/a.py\n", encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable, str(SCRIPTS / "evidence_pack_lint.py"),
            str(pack_path), "--repo-root", str(tmp_path),
            "--changed-files-file", str(changed), "--numstat-file", str(numstat),
        ],
        capture_output=True, text=True, timeout=30, cwd=str(REPO),
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "gear_override" in (proc.stdout + proc.stderr)


# --------------------------------------------------------- check_lanes_build_seat_diversity


def _lane_pack(*lanes):
    return {"lanes": list(lanes)}


LANE_BUILD_ANTHRO = {"lane": "D1", "role": "build", "seat": "sonnet"}
LANE_BUILD_CODEX = {"lane": "D2", "role": "build", "seat": "codex"}
LANE_REVIEW_ANTHRO = {"lane": "D3", "role": "review", "seat": "opus"}


def test_lanes_guilt_gear2_two_anthropic_builders_post_flip():
    """GUILT: Gear 2, two build lanes, both Anthropic -> violation on/after
    the enforcement date."""
    pack = _lane_pack(LANE_BUILD_ANTHRO, {"lane": "D2", "role": "build", "seat": "opus"})
    violations, notice = check_lanes_build_seat_diversity(
        pack, gear=2, today=LANES_NON_ANTHROPIC_ENFORCEMENT_DATE
    )
    assert violations
    assert notice is None
    assert "D3" in violations[0]


def test_lanes_notice_gear2_two_anthropic_builders_pre_flip():
    """NOTICE (not guilt): same shape as above, but before the flip date —
    the rule reports via the notice return, not via violations."""
    pack = _lane_pack(LANE_BUILD_ANTHRO, {"lane": "D2", "role": "build", "seat": "opus"})
    before = LANES_NON_ANTHROPIC_ENFORCEMENT_DATE - datetime.timedelta(days=1)
    violations, notice = check_lanes_build_seat_diversity(pack, gear=2, today=before)
    assert violations == []
    assert notice is not None
    assert "D3" in notice


def test_lanes_guilt_gear3_three_anthropic_builders_post_flip():
    """GUILT: Gear 3, three Anthropic build lanes (mixed name styles) ->
    violation on/after the enforcement date."""
    pack = _lane_pack(
        LANE_BUILD_ANTHRO,
        {"lane": "D2", "role": "build", "seat": "opus"},
        {"lane": "D3", "role": "build", "seat": "claude-sonnet-5"},
    )
    violations, notice = check_lanes_build_seat_diversity(
        pack, gear=3, today=LANES_NON_ANTHROPIC_ENFORCEMENT_DATE
    )
    assert violations
    assert notice is None


def test_lanes_guilt_not_a_list():
    """GUILT: `lanes` present but not a list is always a violation."""
    violations, notice = check_lanes_build_seat_diversity({"lanes": "nope"}, gear=2)
    assert violations
    assert "list" in violations[0]
    assert notice is None


def test_lanes_guilt_entry_not_mapping():
    """GUILT: a lane entry that is not a mapping is always a violation."""
    pack = _lane_pack("not-a-mapping")
    violations, notice = check_lanes_build_seat_diversity(pack, gear=2)
    assert violations
    assert "mapping" in violations[0]
    assert notice is None


def test_lanes_guilt_missing_seat():
    """GUILT: a lane entry missing `seat` is always a violation."""
    pack = {"lanes": [{"lane": "D1", "role": "build"}]}
    violations, notice = check_lanes_build_seat_diversity(pack, gear=2)
    assert violations
    assert "seat" in violations[0]
    assert notice is None


def test_lanes_guilt_invalid_role():
    """GUILT: `role: deploy` is not in {build, review, read}."""
    pack = {"lanes": [{"lane": "D1", "role": "deploy", "seat": "codex"}]}
    violations, notice = check_lanes_build_seat_diversity(pack, gear=2)
    assert violations
    assert "deploy" in violations[0]
    assert notice is None


def test_lanes_innocence_mixed_builders_clean_both_sides():
    """INNOCENCE: Gear 2, two build lanes, one non-Anthropic (codex) ->
    clean on both sides of the flip date."""
    pack = _lane_pack(LANE_BUILD_ANTHRO, LANE_BUILD_CODEX)
    before = LANES_NON_ANTHROPIC_ENFORCEMENT_DATE - datetime.timedelta(days=1)
    for today in (before, LANES_NON_ANTHROPIC_ENFORCEMENT_DATE):
        violations, notice = check_lanes_build_seat_diversity(pack, gear=2, today=today)
        assert violations == []
        assert notice is None


def test_lanes_innocence_one_build_plus_reviews():
    """INNOCENCE: Gear 2, only ONE build lane + two review lanes (all
    Anthropic) -> exempt by the <2-build-lanes carve-out."""
    pack = _lane_pack(LANE_BUILD_ANTHRO, LANE_REVIEW_ANTHRO, LANE_REVIEW_ANTHRO)
    violations, notice = check_lanes_build_seat_diversity(
        pack, gear=2, today=LANES_NON_ANTHROPIC_ENFORCEMENT_DATE
    )
    assert violations == []
    assert notice is None


def test_lanes_innocence_gear1_exempt():
    """INNOCENCE: Gear 1 with two Anthropic build lanes is exempt."""
    pack = _lane_pack(LANE_BUILD_ANTHRO, {"lane": "D2", "role": "build", "seat": "opus"})
    violations, notice = check_lanes_build_seat_diversity(
        pack, gear=1, today=LANES_NON_ANTHROPIC_ENFORCEMENT_DATE
    )
    assert violations == []
    assert notice is None


def test_lanes_missing_gear2_notices_today_and_fails_post_flip():
    """Gear 2 must declare `lanes`: omission NOTICEs during the grace
    period and becomes a violation on the existing enforcement date."""
    today = datetime.date(2026, 8, 23)
    assert today < LANES_NON_ANTHROPIC_ENFORCEMENT_DATE

    violations, notice = check_lanes_build_seat_diversity({}, gear=2, today=today)
    assert violations == []
    assert notice is not None
    assert "mandatory" in notice

    violations, notice = check_lanes_build_seat_diversity(
        {}, gear=2, today=LANES_NON_ANTHROPIC_ENFORCEMENT_DATE
    )
    assert violations
    assert "mandatory" in violations[0]
    assert notice is None


def test_lanes_missing_gear1_stays_clean_both_sides():
    """INNOCENCE: Gear 1 remains exempt from the `lanes` declaration on
    both sides of the enforcement date."""
    before = LANES_NON_ANTHROPIC_ENFORCEMENT_DATE - datetime.timedelta(days=1)
    after = LANES_NON_ANTHROPIC_ENFORCEMENT_DATE + datetime.timedelta(days=1)
    for today in (before, after):
        violations, notice = check_lanes_build_seat_diversity({}, gear=1, today=today)
        assert violations == []
        assert notice is None


def test_lanes_existing_valid_pack_keeps_passing():
    """INNOCENCE: a valid declared lane set remains clean after the flip."""
    pack = _lane_pack(LANE_BUILD_ANTHRO, LANE_BUILD_CODEX)
    violations, notice = check_lanes_build_seat_diversity(
        pack, gear=2, today=LANES_NON_ANTHROPIC_ENFORCEMENT_DATE
    )
    assert violations == []
    assert notice is None


def test_lanes_empty_list_gear2_notices_today_and_fails_post_flip():
    """GUILT: `lanes: []` (present but empty) defeats the shape check
    trivially and produces zero build lanes -> without the empty-list guard
    it would silently exempt itself from D3. It must take the same phased
    path as a missing `lanes:` key: NOTICE before the flip date, violation
    on/after it."""
    today = datetime.date(2026, 8, 23)
    assert today < LANES_NON_ANTHROPIC_ENFORCEMENT_DATE

    violations, notice = check_lanes_build_seat_diversity(
        {"lanes": []}, gear=2, today=today
    )
    assert violations == []
    assert notice is not None
    assert "empty" in notice

    violations, notice = check_lanes_build_seat_diversity(
        {"lanes": []}, gear=2, today=LANES_NON_ANTHROPIC_ENFORCEMENT_DATE
    )
    assert violations
    assert "empty" in violations[0]
    assert notice is None


def test_lanes_empty_list_gear1_stays_clean_both_sides():
    """INNOCENCE: `lanes: []` at Gear 1 remains exempt on both sides of the
    enforcement date."""
    before = LANES_NON_ANTHROPIC_ENFORCEMENT_DATE - datetime.timedelta(days=1)
    after = LANES_NON_ANTHROPIC_ENFORCEMENT_DATE + datetime.timedelta(days=1)
    for today in (before, after):
        violations, notice = check_lanes_build_seat_diversity(
            {"lanes": []}, gear=1, today=today
        )
        assert violations == []
        assert notice is None


def test_lanes_innocence_single_build_lane_anthropic_seat_post_flip():
    """INNOCENCE: exactly ONE build lane using an Anthropic seat stays clean
    post-flip — fewer than 2 build lanes exempts only the diversity floor,
    not the `lanes:` declaration itself, and this must keep working
    alongside the new empty-list guard."""
    pack = _lane_pack(LANE_BUILD_ANTHRO)
    violations, notice = check_lanes_build_seat_diversity(
        pack, gear=2, today=LANES_NON_ANTHROPIC_ENFORCEMENT_DATE
    )
    assert violations == []
    assert notice is None


def test_lanes_innocence_overmatch_guard_opusculum_claude_ish():
    """INNOCENCE: seats literally named `opusculum` or `claude_ish` are
    treated as non-Anthropic (word/prefix-aware match, not bare substring)."""
    pack = _lane_pack(
        {"lane": "D1", "role": "build", "seat": "opusculum"},
        {"lane": "D2", "role": "build", "seat": "claude_ish"},
    )
    violations, notice = check_lanes_build_seat_diversity(
        pack, gear=2, today=LANES_NON_ANTHROPIC_ENFORCEMENT_DATE
    )
    assert violations == []
    assert notice is None


def test_lanes_end_to_end_notice_pre_flip_does_not_fail(tmp_repo):
    """Wired through lint(): a Gear-2 pack with two Anthropic build lanes
    NOTICEs (exit 0) before LANES_NON_ANTHROPIC_ENFORCEMENT_DATE and fails
    (exit 1) on/after it. lint() has no `today` override, so this exercises
    the real wall clock — assert conditionally on the actual date rather
    than assuming which side of the flip "today" falls on (the flip date
    turns this test red by the calendar otherwise, which is exactly the
    failure mode this conditional exists to avoid)."""
    root, write_brief, write_pack = tmp_repo
    write_brief(gear=2)
    pack_path = write_pack(lanes=[
        {"lane": "D1", "role": "build", "seat": "sonnet"},
        {"lane": "D2", "role": "build", "seat": "opus"},
    ])
    rc, violations = lint(pack_path, root, None)
    if datetime.date.today() < LANES_NON_ANTHROPIC_ENFORCEMENT_DATE:
        assert rc == 0
        assert violations == []
    else:
        assert rc == 1
        assert violations and "D3" in violations[0]


@pytest.mark.parametrize(
    "seat,expected",
    [
        ("opus-5", True),
        ("sonnet-5", True),
        ("haiku-4-5", True),
        ("claude-opus-5", True),
        ("claude-sonnet-5", True),
        ("sonnet", True),
        ("opus", True),
        ("haiku", True),
        ("Claude-Sonnet-5", True),
        ("  sonnet  ", True),
    ],
)
def test_is_anthropic_seat_guilt_anthropic_token_matches(seat, expected):
    """GUILT (for the matcher): roster-style Anthropic names are recognised
    regardless of trailing version tokens, case, or surrounding whitespace."""
    assert _is_anthropic_seat(seat) is expected


@pytest.mark.parametrize(
    "seat,expected",
    [
        ("opusculum", False),
        ("claude_ish", False),
        ("codex", False),
        ("kimi", False),
        ("glm", False),
        ("qwen", False),
        ("codex-sol", False),
    ],
)
def test_is_anthropic_seat_innocence_non_anthropic_token_matches(seat, expected):
    """INNOCENCE (for the matcher): non-Anthropic names are not swept up by
    substring or prefix matching, and ``_`` is not treated as a separator."""
    assert _is_anthropic_seat(seat) is expected


def test_lanes_gear3_opus5_sonnet5_flip_behavior():
    """End-to-end under-match regression: roster-style Anthropic build seats
    must be a VIOLATION post-flip and a NOTICE pre-flip."""
    pack = _lane_pack(
        {"lane": "D1", "role": "build", "seat": "opus-5"},
        {"lane": "D2", "role": "build", "seat": "sonnet-5"},
    )
    before = LANES_NON_ANTHROPIC_ENFORCEMENT_DATE - datetime.timedelta(days=1)
    violations, notice = check_lanes_build_seat_diversity(pack, gear=3, today=before)
    assert violations == []
    assert notice is not None

    violations, notice = check_lanes_build_seat_diversity(
        pack, gear=3, today=LANES_NON_ANTHROPIC_ENFORCEMENT_DATE
    )
    assert violations
    assert notice is None


# --------------------------------------------------------- seat rules by path class (E3/R8-R11)
#
# Shared today= pins for the four rules' own flip date (distinct from D3's
# LANES_NON_ANTHROPIC_ENFORCEMENT_DATE — this program never fired before,
# so it gets its own clock).
_PRE_FLIP = SEAT_RULES_ENFORCEMENT_DATE - datetime.timedelta(days=1)
_POST_FLIP = SEAT_RULES_ENFORCEMENT_DATE


def test_seat_rules_shared_phasing_helper_flip_behavior():
    """Date-freeze test for the shared _seat_rule_verdict plumbing all four
    seat rules build on: not-a-violation is always clean regardless of
    date; a violation NOTICEs pre-flip and FAILS post-flip; an explicit
    `seat_override` wins outright on EITHER side of the flip (a human call
    is not a rollout clock) and is still reported, never silent."""
    assert _seat_rule_verdict("r", False, "msg", {}, _POST_FLIP) == ([], None)

    viol, notice = _seat_rule_verdict("r", True, "msg", {}, _PRE_FLIP)
    assert viol == [] and notice == "r: msg"

    viol, notice = _seat_rule_verdict("r", True, "msg", {}, _POST_FLIP)
    assert viol == ["r: msg"] and notice is None

    viol, notice = _seat_rule_verdict(
        "r", True, "msg", {"seat_override": "verified by hand"}, _POST_FLIP
    )
    assert viol == []
    assert notice == "r (overridden): msg — verified by hand"

    # a blank/whitespace-only override is not an override (same "complete
    # or it doesn't count" shape as rule 7's gear_override) — falls through
    # to ordinary phasing instead of silently swallowing the violation.
    viol, notice = _seat_rule_verdict(
        "r", True, "msg", {"seat_override": "   "}, _POST_FLIP
    )
    assert viol == ["r: msg"] and notice is None


# ---- R11 (compute_seat_floor / check_seat_floor_cheap_seat) and R9
# (check_council_run_gear3) land in a follow-up PR — split per the
# mandate's PR-size contract; this PR ships R8 + R10 only, reusing the
# shared _seat_rule_verdict plumbing tested above.


# ---- R8: check_ground_truth_lane -------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "apps/backend-rag/backend/kb/legal/uu_6_2011.md",
        "apps/backend-rag/backend/services/visa_engine/flow.py",
        "apps/backend-rag/backend/scripts/visa_engine/tools.py",
        "data/source_documents/KBLI_2025_FINAL_CLEAN.json",
        "apps/mouth/data/kbli-gold-all.json",
        "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json",
        "apps/mouth/data/bali-zero-prices.json",
        "research/regulatory/2026-08-26-delta.json",
        "apps/mouth/src/app/visa/voa/page.tsx",
        "apps/mouth/src/app/(visa-oracle)/visa-oracle/page.tsx",
        "apps/mouth/src/app/kbli/page.tsx",
        "apps/mouth/src/app/kbli-explorer/page.tsx",
        "apps/mouth/src/app/taxes/page.tsx",
        "apps/mouth/src/app/(tax-calendar)/page.tsx",
        "apps/mouth/src/app/zoning/page.tsx",
        "apps/mouth/src/app/property/page.tsx",
    ],
)
def test_ground_truth_guilt_hit_no_lane_rejected_post_flip(path):
    """GUILT: every real ground-truth path class, with no ground_truth
    lane declared, is a violation on/after the flip."""
    viol, notice = check_ground_truth_lane({"lanes": []}, [path], today=_POST_FLIP)
    assert viol and "ground_truth" in viol[0]
    assert notice is None


def test_ground_truth_innocence_no_hit_skipped():
    """INNOCENCE: a diff touching none of the ground-truth path classes is
    not this rule's problem."""
    viol, notice = check_ground_truth_lane(
        {"lanes": []}, ["apps/backend-rag/backend/app/main.py"], today=_POST_FLIP
    )
    assert viol == [] and notice is None
    viol, notice = check_ground_truth_lane({"lanes": []}, None, today=_POST_FLIP)
    assert viol == [] and notice is None


def test_ground_truth_innocence_well_formed_lane_passes():
    """INNOCENCE: a {role: ground_truth, seat, nb, query_hash} lane with
    all three fields non-empty clears the rule."""
    pack = {
        "lanes": [
            {"lane": "GT", "role": "ground_truth", "seat": "nlm",
             "nb": "NB-1", "query_hash": "a1b2c3"},
        ],
    }
    viol, notice = check_ground_truth_lane(
        pack, ["apps/backend-rag/backend/kb/legal/foo.md"], today=_POST_FLIP
    )
    assert viol == [] and notice is None


@pytest.mark.parametrize(
    "entry",
    [
        {"lane": "GT", "role": "ground_truth", "seat": "nlm", "nb": "", "query_hash": "a1b2c3"},
        {"lane": "GT", "role": "ground_truth", "seat": "nlm", "query_hash": "a1b2c3"},
        {"lane": "GT", "role": "ground_truth", "seat": "", "nb": "NB-1", "query_hash": "a1b2c3"},
    ],
)
def test_ground_truth_guilt_incomplete_lane_rejected(entry):
    """GUILT: a ground_truth lane missing/emptying any of seat/nb/
    query_hash is not well-formed — same "complete or it isn't evidence"
    shape as rule 1's receipts."""
    viol, notice = check_ground_truth_lane(
        {"lanes": [entry]}, ["apps/backend-rag/backend/kb/legal/foo.md"], today=_POST_FLIP
    )
    assert viol
    assert notice is None


def test_ground_truth_innocence_seat_override_reports_not_fails():
    """INNOCENCE: `seat_override` clears the violation and is reported."""
    pack = {"lanes": [], "seat_override": "regulatory text unchanged, formatting only"}
    viol, notice = check_ground_truth_lane(
        pack, ["apps/backend-rag/backend/kb/legal/foo.md"], today=_POST_FLIP
    )
    assert viol == []
    assert notice is not None and "(overridden)" in notice


def test_ground_truth_innocence_pre_flip_notice_not_fail():
    """INNOCENCE: the same guilty shape only NOTICEs before the flip."""
    viol, notice = check_ground_truth_lane(
        {"lanes": []}, ["apps/backend-rag/backend/kb/legal/foo.md"], today=_PRE_FLIP
    )
    assert viol == []
    assert notice is not None and "ground_truth" in notice


# ---- R10: check_pii_local_seat ----------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "apps/backend-rag/backend/services/intake/classifier.py",
        "apps/backend-rag/backend/services/crm/service.py",
        "apps/backend-rag/backend/services/crm_guardian/gate.py",
        "apps/backend-rag/backend/channels/whatsapp/handler.py",
        "scripts/yield_optimizer_pitch_gate.py",
    ],
)
def test_pii_local_guilt_cloud_seat_on_pii_path_rejected_post_flip(path):
    """GUILT: every real PII path class, with a non-`ollama-` build seat
    and no cloud_ok+clean pair, is a violation on/after the flip."""
    pack = {"lanes": [{"lane": "D1", "role": "build", "seat": "sonnet-5"}]}
    viol, notice = check_pii_local_seat(pack, [path], today=_POST_FLIP)
    assert viol and "pii_local" in viol[0]
    assert notice is None


def test_pii_local_innocence_no_hit_skipped():
    """INNOCENCE: a diff touching none of the PII path classes is not this
    rule's problem, regardless of seats."""
    pack = {"lanes": [{"lane": "D1", "role": "build", "seat": "sonnet-5"}]}
    viol, notice = check_pii_local_seat(
        pack, ["apps/backend-rag/backend/app/main.py"], today=_POST_FLIP
    )
    assert viol == [] and notice is None
    viol, notice = check_pii_local_seat(pack, None, today=_POST_FLIP)
    assert viol == [] and notice is None


def test_pii_local_innocence_all_ollama_seats_passes():
    """INNOCENCE: every lane on an `ollama-*` seat clears the rule."""
    pack = {
        "lanes": [
            {"lane": "D1", "role": "build", "seat": "ollama-qwen3.5:9b"},
            {"lane": "D2", "role": "review", "seat": "ollama-qwen2.5vl:7b"},
        ],
    }
    viol, notice = check_pii_local_seat(
        pack, ["apps/backend-rag/backend/services/crm/service.py"], today=_POST_FLIP
    )
    assert viol == [] and notice is None


def test_pii_local_innocence_cloud_ok_and_clean_passes():
    """INNOCENCE: a non-local seat is fine when the pack ALSO carries a
    non-empty `cloud_ok` AND `pii_scan: clean` — BOTH are required, this
    rule reads rule 3's field rather than re-deriving PII status."""
    pack = {
        "lanes": [{"lane": "D1", "role": "build", "seat": "sonnet-5"}],
        "pii_scan": "clean",
        "cloud_ok": "DPA-2026-08-consent-ref-17",
    }
    viol, notice = check_pii_local_seat(
        pack, ["apps/backend-rag/backend/services/crm/service.py"], today=_POST_FLIP
    )
    assert viol == [] and notice is None


def test_pii_local_guilt_cloud_ok_without_clean_still_rejected():
    """GUILT: `cloud_ok` alone, without `pii_scan: clean`, is NOT the
    escape — both fields are required."""
    pack = {
        "lanes": [{"lane": "D1", "role": "build", "seat": "sonnet-5"}],
        "cloud_ok": "DPA-2026-08-consent-ref-17",
        "pii_scan": "dirty",
    }
    viol, notice = check_pii_local_seat(
        pack, ["apps/backend-rag/backend/services/crm/service.py"], today=_POST_FLIP
    )
    assert viol
    assert notice is None


def test_pii_local_innocence_pre_flip_notice_not_fail():
    """INNOCENCE: the same guilty shape only NOTICEs before the flip."""
    pack = {"lanes": [{"lane": "D1", "role": "build", "seat": "sonnet-5"}]}
    viol, notice = check_pii_local_seat(
        pack, ["apps/backend-rag/backend/services/crm/service.py"], today=_PRE_FLIP
    )
    assert viol == []
    assert notice is not None and "pii_local" in notice


# ---- R9 (check_council_run_gear3) lands in a follow-up PR alongside R11,
# same reasoning as the R11 note above.


# ---- end-to-end: lint() wires the seat rules through one call site --------


def test_seat_rules_end_to_end_through_lint(tmp_repo):
    """End-to-end: lint() surfaces a seat-rule violation (R8, ground_truth)
    for a real pack+brief tree via the public entry point, not just the
    unit-level check_* functions."""
    tmp_path, write_brief, write_pack = tmp_repo
    write_brief(gear=3)
    write_pack(
        lanes=[{"lane": "D1", "role": "build", "seat": "codex"}],
        dissent=[{"seat": "codex-sol", "objection": "x", "status": "PLAUSIBLE"}],
    )
    rc, viol = lint(
        tmp_path / "evidence" / "pack.yml", tmp_path,
        ["apps/backend-rag/backend/kb/legal/foo.md"],
    )
    # NOTE: `today` is not injectable through the public lint() entry point
    # (it always reads the real wall-clock date), so this end-to-end check
    # only proves WIRING (the violation reaches lint()'s return value) —
    # whether it is a NOTICE or a FAIL depends on whichever side of
    # SEAT_RULES_ENFORCEMENT_DATE the suite actually runs on.
    if datetime.datetime.now(datetime.timezone.utc).date() < SEAT_RULES_ENFORCEMENT_DATE:
        assert rc == 0
    else:
        assert rc == 1
        assert any("ground_truth" in v for v in viol)
