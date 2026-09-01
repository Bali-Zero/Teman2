"""Tests for scripts/evidence_pack_lint.py (PR-3, fleet-order harness).

The script carries its own hermetic --selftest fixture (guilt+innocence over
every rule); this file makes pytest/CI run it AND pins each `check_*` guard's
verdict function directly, by name, for the guard-conformance registry
(superscar #3: "nessuna guardia mergiata senza un test di innocenza E di
colpevolezza" — each guard needs BOTH proofs registered).
"""

from __future__ import annotations

import contextlib
import datetime
import io
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"

sys.path.insert(0, str(SCRIPTS))
from evidence_pack_lint import (  # noqa: E402
    EVIDENCE_ROOT_BRIEF_DEPRECATION_DATE,
    EVIDENCE_ROOT_DEPRECATION_DATE,
    FLOOR_SOURCE_BOTH,
    FLOOR_SOURCE_NONE,
    FLOOR_SOURCE_PATH,
    FLOOR_SOURCE_SIZE,
    LANES_NON_ANTHROPIC_ENFORCEMENT_DATE,
    R9_R11_ENFORCEMENT_DATE,
    SEAT_RULES_ENFORCEMENT_DATE,
    SIZE_GEAR2_THRESHOLD,
    SIZE_GEAR3_THRESHOLD,
    _is_anthropic_seat,
    _seat_rule_verdict,
    _size_term_net_lines,
    check_acceptance_probe_pairing,
    check_appetite_acknowledgment,
    check_assumptions_register,
    check_brief_ref_exists,
    check_cheap_seat_floor,
    check_council_run_gear3,
    check_countable_claims,
    check_dissent_nonempty_on_gear3,
    check_brief_not_at_deprecated_root,
    check_gear_floor,
    check_ground_truth_lane,
    check_lanes_build_seat_diversity,
    check_pack_not_at_deprecated_root,
    check_pii_local_seat,
    check_pii_scan_clean,
    check_receipts_have_provenance,
    check_size_budget,
    compute_ceiling,
    compute_floor,
    compute_floor_source,
    compute_seat_floor,
    effort_for_gear,
    format_measured_claims,
    lint,
    measured_commit_count,
    parse_numstat_totals,
    sum_numstat,
    workflow_paths_exempt_from_path_term,
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


def test_gear_floor_guilt_size_term_below_floor_rejected():
    """GUILT (S1): brief declares gear 1 on a diff that touches no hot-zone
    path but whose numstat clears SIZE_GEAR3_THRESHOLD — the size term
    alone must reject it, same as a hot-zone hit would."""
    changed = ["apps/some/plain/module.py"]
    numstat = f"{SIZE_GEAR3_THRESHOLD}\t0\tapps/some/plain/module.py\n"
    violations = check_gear_floor({"gear": 1}, changed, numstat)
    assert violations
    assert "floor" in violations[0]


def test_gear_floor_innocence_size_term_below_threshold_passes():
    """INNOCENCE (S1): the same non-hot-zone diff with a numstat below
    SIZE_GEAR2_THRESHOLD passes at gear 1 — the size term does not fire
    below its own threshold."""
    changed = ["apps/some/plain/module.py"]
    numstat = f"{SIZE_GEAR2_THRESHOLD - 1}\t0\tapps/some/plain/module.py\n"
    assert check_gear_floor({"gear": 1}, changed, numstat) == []


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


# --------------------------------------------------------- compute_floor size term (S1)


def test_compute_floor_guilt_large_plain_diff_floors_three():
    """GUILT: a diff net >= SIZE_GEAR3_THRESHOLD on ordinary (non-hot-zone)
    paths floors at Gear 3 on size alone."""
    numstat = f"{SIZE_GEAR3_THRESHOLD}\t0\tapps/some/plain/module.py\n"
    assert compute_floor(["apps/some/plain/module.py"], numstat) == 3


def test_compute_floor_guilt_medium_plain_diff_floors_two():
    """GUILT: a diff net >= SIZE_GEAR2_THRESHOLD but below the Gear-3
    threshold raises the floor to (at least) Gear 2 — the one path by which
    compute_floor can return 2 at all (the path term alone never does)."""
    numstat = f"{SIZE_GEAR2_THRESHOLD}\t0\tapps/some/plain/module.py\n"
    assert compute_floor(["apps/some/plain/module.py"], numstat) == 2


def test_compute_floor_innocence_small_diff_stays_one():
    """INNOCENCE: a diff net below SIZE_GEAR2_THRESHOLD on ordinary paths
    stays at the path-only floor (1) — the size term does not fire."""
    numstat = f"{SIZE_GEAR2_THRESHOLD - 1}\t0\tdocs/notes.md\n"
    assert compute_floor(["docs/notes.md"], numstat) == 1


def test_compute_floor_innocence_large_fixtures_only_diff_unchanged():
    """INNOCENCE: a large diff confined to excluded paths (fixtures/) does
    NOT inflate the size term — floor stays at whatever the path term alone
    gives, even though the raw numstat would clear SIZE_GEAR3_THRESHOLD by
    a wide margin."""
    numstat = f"{SIZE_GEAR3_THRESHOLD * 2}\t0\ttests/fixtures/huge.json\n"
    assert compute_floor(["tests/fixtures/huge.json"], numstat) == 1


def test_compute_floor_fallback_numstat_none_is_path_only():
    """FALLBACK: omitting numstat entirely (the default) reproduces the
    exact pre-S1 path-only behavior, even for a changed-file set that WOULD
    floor at 3 on size if a numstat were supplied — compute_floor has no
    way to know the diff is large without one, and must not guess."""
    assert compute_floor(["apps/some/plain/module.py"]) == 1
    assert compute_floor(["apps/some/plain/module.py"], numstat=None) == 1


def test_compute_floor_hotzone_hit_wins_over_small_size():
    """Path term and size term are independent — a hot-zone hit still
    floors at 3 even when the accompanying numstat is tiny."""
    numstat = "3\t1\tfly.toml\n"
    assert compute_floor(["fly.toml"], numstat) == 3


# --------------------------------------------------------- compute_floor_source (S2)
# S2, 2026-08-27 (Gear-3 gate review round 2, PR #5049): compute_floor_source()
# exposes WHY the floor is what it is, so harness-floor.yml's Step 5b can grant
# the SIZE_GEAR2_ENFORCEMENT_DATE grace period ONLY to a floor==2 diff that got
# there via the size term. See _compute_floor_with_source()'s docstring for the
# full contract and the "both means both INDEPENDENTLY sufficient, not merely
# both present" tie-break rule the two subtle cases below exercise.


def test_compute_floor_source_innocence_hotzone_only_is_path():
    """INNOCENCE: a hot-zone hit with no numstat at all -> source == 'path'."""
    assert compute_floor_source(["fly.toml"], None) == FLOOR_SOURCE_PATH
    assert compute_floor(["fly.toml"], None) == 3


def test_compute_floor_source_innocence_size_gear3_only_is_size():
    """INNOCENCE: no hot-zone hit, size term alone clears SIZE_GEAR3_THRESHOLD
    -> source == 'size', floor == 3 (source distinguishes THIS from a hot-zone
    floor==3, both read floor==3 but only one is 'path')."""
    numstat = f"{SIZE_GEAR3_THRESHOLD}\t0\tapps/some/plain/module.py\n"
    assert compute_floor_source(["apps/some/plain/module.py"], numstat) == FLOOR_SOURCE_SIZE
    assert compute_floor(["apps/some/plain/module.py"], numstat) == 3


def test_compute_floor_source_innocence_size_gear2_only_is_size():
    """INNOCENCE: no hot-zone hit, size term clears SIZE_GEAR2_THRESHOLD but
    NOT SIZE_GEAR3_THRESHOLD -> source == 'size', floor == 2. This is the
    ONLY way floor==2 is reachable — see the invariant test below."""
    numstat = f"{SIZE_GEAR2_THRESHOLD}\t0\tapps/some/plain/module.py\n"
    assert compute_floor_source(["apps/some/plain/module.py"], numstat) == FLOOR_SOURCE_SIZE
    assert compute_floor(["apps/some/plain/module.py"], numstat) == 2


def test_compute_floor_source_innocence_neither_term_is_none():
    """INNOCENCE: no hot-zone hit, numstat=None entirely -> source == 'none',
    floor == 1 (mirrors compute_floor()'s own fallback behavior)."""
    assert compute_floor_source(["docs/notes.md"], None) == FLOOR_SOURCE_NONE
    assert compute_floor(["docs/notes.md"], None) == 1


def test_compute_floor_source_innocence_neither_term_below_thresholds_is_none():
    """INNOCENCE: no hot-zone hit, numstat present but below even
    SIZE_GEAR2_THRESHOLD -> source == 'none', not 'size' (the size term never
    fired at all, it isn't that it fired weakly)."""
    numstat = f"{SIZE_GEAR2_THRESHOLD - 1}\t0\tdocs/notes.md\n"
    assert compute_floor_source(["docs/notes.md"], numstat) == FLOOR_SOURCE_NONE
    assert compute_floor(["docs/notes.md"], numstat) == 1


def test_compute_floor_source_guilt_both_terms_independently_sufficient_is_both():
    """GUILT-shaped (the subtle case): a hot-zone hit AND churn that
    INDEPENDENTLY clears SIZE_GEAR3_THRESHOLD -> source == 'both'. Removing
    either term alone would still leave the diff at floor 3 on the other."""
    numstat = f"{SIZE_GEAR3_THRESHOLD}\t0\tfly.toml\n"
    assert compute_floor_source(["fly.toml"], numstat) == FLOOR_SOURCE_BOTH
    assert compute_floor(["fly.toml"], numstat) == 3


def test_compute_floor_source_guilt_hotzone_plus_gear2_only_size_is_path_not_both():
    """GUILT-shaped (the tie-break rule, the one non-obvious part of the
    'both' semantics): a hot-zone hit alongside churn that clears
    SIZE_GEAR2_THRESHOLD but NOT SIZE_GEAR3_THRESHOLD is source == 'path',
    NOT 'both' — the path term is doing all the real work here (floor stays
    3 with or without the size signal, which never independently cleared the
    Gear-3 bar on its own). 'both' means both terms are independently
    SUFFICIENT for floor==3, not merely both present."""
    numstat = f"{SIZE_GEAR2_THRESHOLD}\t0\tfly.toml\n"
    assert compute_floor_source(["fly.toml"], numstat) == FLOOR_SOURCE_PATH
    assert compute_floor(["fly.toml"], numstat) == 3


def test_compute_floor_source_invariant_floor_two_implies_source_size():
    """PROVABLE INVARIANT (see _compute_floor_with_source()'s docstring):
    floor==2 is reachable ONLY via source=='size' — swept across a small
    grid of hot-zone/no-hot-zone x below/at/above-each-threshold cases,
    every single one that lands on floor==2 must report source=='size', and
    none of the hot-zone cases ever lands on floor==2 at all (they jump
    straight to 3, per compute_floor()'s own docstring)."""
    hotzone_files = ["fly.toml"]
    plain_files = ["apps/some/plain/module.py"]
    churns = [0, SIZE_GEAR2_THRESHOLD - 1, SIZE_GEAR2_THRESHOLD, SIZE_GEAR3_THRESHOLD - 1, SIZE_GEAR3_THRESHOLD]
    for files in (hotzone_files, plain_files):
        for churn in churns:
            numstat = f"{churn}\t0\t{files[0]}\n"
            floor = compute_floor(files, numstat)
            source = compute_floor_source(files, numstat)
            if floor == 2:
                assert source == FLOOR_SOURCE_SIZE, (files, churn, floor, source)
            if files is hotzone_files:
                assert floor != 2, (files, churn, floor, source)  # hot-zone never lands on exactly 2


def test_size_term_net_lines_sums_churn_not_global_net():
    """The size term's Σ(added+deleted) CHURN does NOT cancel across files
    the way sum_numstat()'s plain global net would — two files that
    individually net +10000/-10000 sum to 20000 here, not 0."""
    numstat = "10000\t0\ta/big_add.py\n0\t10000\tb/big_del.py\n"
    assert _size_term_net_lines(numstat) == 20000
    assert sum_numstat(numstat) == 0  # the pre-existing global-net function, for contrast


def test_size_term_net_lines_balanced_same_file_rewrite_does_not_cancel():
    """REGRESSION (adversarial review, codex-sol, PR #5049, finding 2 HIGH):
    an earlier cut of _size_term_net_lines() summed the PER-FILE ABSOLUTE
    net (`abs(added-deleted)`), which a balanced in-place rewrite of a
    SINGLE file could cancel to (near) zero — 2000 added + 2000 deleted in
    the same file netted to 0, hiding a full-file rewrite from the floor
    entirely. CHURN (added+deleted) cannot cancel this way: it must report
    4000, not 0."""
    numstat = "2000\t2000\tapps/x/rewritten_module.py\n"
    assert _size_term_net_lines(numstat) == 4000


def test_size_term_net_lines_excludes_generated_lockfile_minified_and_binary():
    numstat = (
        "9999\t0\tpackage-lock.json\n"
        "9999\t0\tapps/x/generated/schema.py\n"
        "9999\t0\tassets/hero.png\n"
        "9999\t0\tbundle.min.js\n"
        "-\t-\tapps/x/binary.bin\n"
        "50\t10\tapps/x/real_code.py\n"
    )
    assert _size_term_net_lines(numstat) == 60  # only real_code.py counts (churn: 50+10)


def test_size_term_net_lines_excludes_vendored_directories():
    """A real vendored tree exists in this repo (vendor/evoskill) — a
    routine vendor bump must not false-floor at Gear 2/3 on churn volume
    alone (adversarial review, codex-sol, PR #5049, finding 4 MEDIUM)."""
    numstat = (
        "9999\t9999\tvendor/evoskill/lib.js\n"
        "9999\t9999\tnode_modules/left-pad/index.js\n"
        "9999\t9999\tapps/web/dist/bundle.js\n"
        "50\t10\tapps/x/real_code.py\n"
    )
    assert _size_term_net_lines(numstat) == 60  # only real_code.py counts (churn: 50+10)


def test_size_term_net_lines_named_lockfile_excluded_but_other_dot_lock_counts():
    """The lockfile exclusion is a NAMED list of well-known package-manager
    lockfiles, deliberately NOT a blanket `*.lock` suffix match (adversarial
    review, codex-sol, PR #5049, finding 4 MEDIUM): this repo's own
    coordination primitives use `.lock`-suffixed names for real hand-written
    state (CLAUDE.md's `agent_lock:<resource>` pattern) — a blanket suffix
    match would exempt a diff touching real lock-coordination code."""
    numstat = "9999\t0\tpackage-lock.json\n50\t10\tinfra/coordination/custom.lock\n"
    assert _size_term_net_lines(numstat) == 60  # custom.lock counts (churn: 50+10), package-lock.json excluded


def test_size_term_net_lines_innocence_not_fixtures_directory_not_excluded():
    """INNOCENCE (guard-over-match, superscar #3): a directory whose name
    merely CONTAINS "fixtures" as a substring (not an exact path segment)
    is NOT excluded — only a genuine `fixtures/` component is."""
    numstat = "100\t0\tapps/x/not_fixtures/real.py\n"
    assert _size_term_net_lines(numstat) == 100


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


def test_print_floor_cli_honors_numstat_file_size_term(tmp_path):
    """--print-floor also accepts --numstat-file (S1) and must agree with
    compute_floor() called directly with the same numstat text — the size
    term is reachable through the CLI, not just the Python API."""
    changed = tmp_path / "changed.txt"
    changed.write_text("apps/some/plain/module.py\n", encoding="utf-8")
    numstat_text = f"{SIZE_GEAR3_THRESHOLD}\t0\tapps/some/plain/module.py\n"
    numstat_file = tmp_path / "numstat.txt"
    numstat_file.write_text(numstat_text, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "evidence_pack_lint.py"),
         "--print-floor", "--changed-files-file", str(changed),
         "--numstat-file", str(numstat_file)],
        capture_output=True, text=True, timeout=30, cwd=str(REPO),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert int(proc.stdout.strip()) == compute_floor(
        ["apps/some/plain/module.py"], numstat_text
    ) == 3


def test_print_floor_source_cli_matches_compute_floor_source(tmp_path):
    """--print-floor-source (S2) and the pure compute_floor_source() function
    must agree — harness-floor.yml's Step 5b consumes this exact CLI mode to
    decide whether the SIZE_GEAR2_ENFORCEMENT_DATE grace period applies."""
    changed = tmp_path / "changed.txt"
    changed.write_text("apps/some/plain/module.py\n", encoding="utf-8")
    numstat_text = f"{SIZE_GEAR2_THRESHOLD}\t0\tapps/some/plain/module.py\n"
    numstat_file = tmp_path / "numstat.txt"
    numstat_file.write_text(numstat_text, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "evidence_pack_lint.py"),
         "--print-floor-source", "--changed-files-file", str(changed),
         "--numstat-file", str(numstat_file)],
        capture_output=True, text=True, timeout=30, cwd=str(REPO),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.strip() == compute_floor_source(
        ["apps/some/plain/module.py"], numstat_text
    ) == FLOOR_SOURCE_SIZE


def test_print_floor_source_cli_requires_changed_files_file(tmp_path):
    """GUILT: --print-floor-source without --changed-files-file is a usage
    error (exit 3), mirroring --print-floor's own guard — never silently
    prints a source computed from an empty/undefined changed-files set."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "evidence_pack_lint.py"), "--print-floor-source"],
        capture_output=True, text=True, timeout=30, cwd=str(REPO),
    )
    assert proc.returncode == 3, proc.stdout + proc.stderr


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
        "apps/mouth/data/KBLI-2025-master.json",
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


def test_ground_truth_guilt_kbli_filiera_dataset_rejected_post_flip():
    """GUILT (regression, refuter round 1 2026-08-26): a real, on-disk KBLI
    regulatory dataset outside data/source_documents/ — data/kbli-filiera/
    perpres-foreign-caps.json — was an under-match: no pattern covered it."""
    viol, notice = check_ground_truth_lane(
        {"lanes": []},
        ["data/kbli-filiera/perpres-foreign-caps.json"],
        today=_POST_FLIP,
    )
    assert viol and "ground_truth" in viol[0]
    assert notice is None


def test_ground_truth_innocence_page_own_test_file_skipped():
    """INNOCENCE (regression, refuter round 1 2026-08-26): fnmatch's `*`
    crosses `/`, so `apps/mouth/src/app/kbli-explorer/*` also matched the
    page's own test scaffolding — an innocuous UI test making no
    regulatory claim of its own. `_is_test_path` excludes it; the page
    file itself (test_ground_truth_guilt_hit_no_lane_rejected_post_flip)
    is still covered directly."""
    viol, notice = check_ground_truth_lane(
        {"lanes": []},
        ["apps/mouth/src/app/kbli-explorer/hooks/__tests__/useTypewriter.test.ts"],
        today=_POST_FLIP,
    )
    assert viol == [] and notice is None


@pytest.mark.parametrize(
    "path",
    [
        "apps/mouth/src/app/kbli-explorer/loading.tsx",
        "apps/mouth/src/app/kbli-explorer/error.tsx",
    ],
)
def test_ground_truth_innocence_nextjs_framework_files_skipped(path):
    """INNOCENCE (regression, refuter round 2 2026-08-26): loading.tsx and
    error.tsx are Next.js App-Router-reserved special filenames — always
    framework scaffolding (loading skeleton / error boundary), never page
    content, by the framework's own naming contract. `_is_test_path`
    excludes them via _NEXTJS_FRAMEWORK_BASENAMES."""
    viol, notice = check_ground_truth_lane({"lanes": []}, [path], today=_POST_FLIP)
    assert viol == [] and notice is None


def test_ground_truth_guilt_claim_page_components_not_excluded_by_nextjs_fix():
    """GUILT (proving the Next.js fix didn't over-reach): layout.tsx and a
    real claim-rendering component under the same claim-page directory
    are NOT excluded — only the 4 exact reserved framework basenames are.
    RiskGauge.tsx renders the actual regulatory risk category; excluding
    it would trade the loading.tsx/error.tsx over-match for a worse
    under-match."""
    for path in (
        "apps/mouth/src/app/kbli-explorer/layout.tsx",
        "apps/mouth/src/app/kbli-explorer/components/RiskGauge.tsx",
    ):
        viol, notice = check_ground_truth_lane({"lanes": []}, [path], today=_POST_FLIP)
        assert viol and "ground_truth" in viol[0], path
        assert notice is None


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


@pytest.mark.parametrize(
    "path",
    [
        "apps/backend-rag/backend/app/routers/crm_clients.py",
        "apps/backend-rag/backend/app/routers/whatsapp_conversations.py",
        "apps/backend-rag/backend/app/routers/admin_crm_kg.py",
        "apps/backend-rag/backend/app/routers/admin_pii.py",
        "apps/backend-rag/backend/app/routers/crm_guardian_drive.py",
        "apps/backend-rag/backend/app/routers/intake_gate.py",
    ],
)
def test_pii_local_guilt_router_layer_rejected_post_flip(path):
    """GUILT (regression, refuter round 1 2026-08-26): the services/* PII
    patterns missed the app/routers/* layer that actually exposes CRM/
    WhatsApp/intake client data over HTTP — e.g. app/routers/crm_clients.py
    and app/routers/whatsapp_conversations.py both read/serve phone
    numbers and names, and matched neither pattern before this fix."""
    pack = {"lanes": [{"lane": "D1", "role": "build", "seat": "sonnet-5"}]}
    viol, notice = check_pii_local_seat(pack, [path], today=_POST_FLIP)
    assert viol and "pii_local" in viol[0]
    assert notice is None


def test_pii_local_innocence_core_guardian_router_not_crm_guardian():
    """INNOCENCE (regression, refuter round 2 2026-08-26): a bare
    `app/routers/guardian.py` is Core Guardian (decision audit trail +
    risk scores — an unrelated system-health/monitoring API, per its own
    module docstring), NOT the CRM-Guardian feature. It was briefly a
    false-positive PII_PATH_PATTERNS entry; removed. The real CRM-Guardian
    router, crm_guardian_drive.py, stays covered via the crm_*.py glob
    (see test_pii_local_guilt_router_layer_rejected_post_flip)."""
    pack = {"lanes": [{"lane": "D1", "role": "build", "seat": "sonnet-5"}]}
    viol, notice = check_pii_local_seat(
        pack, ["apps/backend-rag/backend/app/routers/guardian.py"], today=_POST_FLIP
    )
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


@pytest.mark.parametrize("pack", [{}, {"lanes": []}, {"lanes": None}])
def test_pii_local_guilt_lanes_absent_or_empty_rejected_post_flip(pack):
    """GUILT (refuter finding #7, 2026-08-27): a PII-path hit with NO
    `lanes` declared at all — or an empty list — used to return ([], None)
    silently: `offending` is only ever populated by iterating `lanes`, so
    nothing to iterate meant nothing to flag, not even a NOTICE. Since
    D3/rule-8 already lets a Gear-1 pack omit `lanes` entirely, this was a
    silent bypass: a Gear-1 PII-touching diff got zero R10 signal. A pack
    that cannot show ANY seat touched the PII path is now itself the
    violation."""
    viol, notice = check_pii_local_seat(
        pack, ["apps/backend-rag/backend/services/crm/service.py"], today=_POST_FLIP
    )
    assert viol and "pii_local" in viol[0]
    assert notice is None


def test_pii_local_innocence_lanes_absent_but_cloud_ok_clean_still_passes():
    """INNOCENCE: the cloud_ok+pii_scan escape does not require `lanes` at
    all — a pack can assert "reviewed clean, DPA on file" with zero lanes
    declared, and that still clears the rule."""
    pack = {"pii_scan": "clean", "cloud_ok": "DPA-2026-08-consent-ref-17"}
    viol, notice = check_pii_local_seat(
        pack, ["apps/backend-rag/backend/services/crm/service.py"], today=_POST_FLIP
    )
    assert viol == [] and notice is None


def test_pii_local_innocence_lanes_absent_pre_flip_notice_not_fail():
    """INNOCENCE: the lanes-absent guilty shape only NOTICEs before the
    flip, same phasing as every other seat-rule violation."""
    viol, notice = check_pii_local_seat(
        {}, ["apps/backend-rag/backend/services/crm/service.py"], today=_PRE_FLIP
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


def test_seat_rules_end_to_end_notice_prints_to_stderr(tmp_repo, capsys):
    """End-to-end (refuter finding #5, 2026-08-27): every other seat-rule
    end-to-end test only asserts on lint()'s RETURN value — a NOTICE print
    statement silently deleted from the source would not be caught by any
    of them. This one captures real stderr via capsys and proves the
    ground_truth NOTICE text actually reaches the operator, pre-flip."""
    tmp_path, write_brief, write_pack = tmp_repo
    write_brief(gear=3)
    write_pack(
        lanes=[{"lane": "D1", "role": "build", "seat": "codex"}],
        dissent=[{"seat": "codex-sol", "objection": "x", "status": "PLAUSIBLE"}],
    )
    lint(
        tmp_path / "evidence" / "pack.yml", tmp_path,
        ["apps/backend-rag/backend/kb/legal/foo.md"],
    )
    captured = capsys.readouterr()
    if datetime.datetime.now(datetime.timezone.utc).date() < SEAT_RULES_ENFORCEMENT_DATE:
        assert "ground_truth" in captured.err
        assert "NOTICE" in captured.err
# ============================================================================
# PR-B: R11 cheap-seat floor for mechanical diffs + R9 Gear-3 council_run
# (2026-08-26-PIANO-SPEC-receptor-live.md §8). Self-contained on this branch
# (created before #5054/R8-R10 merged) — R9_R11_ENFORCEMENT_DATE is its own
# constant, not SEAT_RULES_ENFORCEMENT_DATE, precisely so this module never
# ends up with two same-named top-level definitions regardless of merge
# order between the two PRs.
# ============================================================================

_R9_R11_PRE_FLIP = R9_R11_ENFORCEMENT_DATE - datetime.timedelta(days=1)
_R9_R11_POST_FLIP = R9_R11_ENFORCEMENT_DATE


# ---- R11: compute_seat_floor (pure predicate) ------------------------------


@pytest.mark.parametrize(
    "path",
    [
        ".claude/skills/modus/PENDING-ARMS.md",
        "apps/mouth/src/i18n/locales/en.json",
        "apps/admin-dashboard/src/i18n/locales/it.json",
        "scripts/tests/fixtures/merge_gate_integrity/guilt_3227.json",
        "packages/research-os-core/fixtures/object_successor_edge/valid_with_actor.json",
        "apps/mouth/public/catalog/consultant-services-update-data-coretax-activation.jpg",
    ],
)
def test_compute_seat_floor_guilt_single_mechanical_file_is_true(path):
    """GUILT (for the predicate): each of these six is a REAL, on-disk file
    (verified 2026-08-27 by refuter round 1, which found 3 of the original
    6 example paths here were invented/illustrative rather than real —
    corrected to actual `find`-verified paths) covering every
    MECHANICAL_PATH_PATTERNS class; each, alone, makes the whole (1-file)
    diff count as 100% mechanical."""
    assert compute_seat_floor([path]) is True


def test_compute_seat_floor_innocence_one_non_mechanical_file_flips_to_false():
    """INNOCENCE: a diff that is mostly mechanical but touches even ONE
    real code file is NOT 100% mechanical — the rule is all-or-nothing."""
    assert compute_seat_floor([
        "apps/mouth/src/i18n/locales/en.json",
        "apps/backend-rag/backend/app/main.py",
    ]) is False


def test_compute_seat_floor_innocence_empty_or_none_is_false():
    """INNOCENCE: no changed files is not evidence of "100% mechanical" —
    same convention as compute_floor's own empty-diff handling."""
    assert compute_seat_floor([]) is False
    assert compute_seat_floor(None) is False


# ---- R11: check_cheap_seat_floor -------------------------------------------


_MECHANICAL_DIFF = ["apps/mouth/src/i18n/locales/en.json", ".claude/skills/modus/PENDING-ARMS.md"]


def test_cheap_seat_floor_guilt_no_cheap_lane_rejected_post_flip():
    """GUILT: a 100%-mechanical diff with only a frontier-tier build seat
    and no override is a violation on/after the flip."""
    pack = {"lanes": [{"lane": "D1", "role": "build", "seat": "claude-opus-5"}]}
    viol, notice = check_cheap_seat_floor(pack, _MECHANICAL_DIFF, today=_R9_R11_POST_FLIP)
    assert viol and "seat_floor" in viol[0]
    assert notice is None


def test_cheap_seat_floor_innocence_not_100pct_mechanical_skipped():
    """INNOCENCE: a diff that is not 100% mechanical is not this rule's
    problem, regardless of seats."""
    pack = {"lanes": [{"lane": "D1", "role": "build", "seat": "claude-opus-5"}]}
    viol, notice = check_cheap_seat_floor(
        pack, ["apps/backend-rag/backend/app/main.py"], today=_R9_R11_POST_FLIP
    )
    assert viol == [] and notice is None
    viol, notice = check_cheap_seat_floor(pack, None, today=_R9_R11_POST_FLIP)
    assert viol == [] and notice is None


@pytest.mark.parametrize(
    "seat",
    [
        "claude-haiku-4-5",
        "claude-haiku-4-5-20251001",
        "codex-gpt-5.6-luna",
        "kimi-code/kimi-for-coding-highspeed",
        "tp1-qwen3.6-flash",
        "tp1-deepseek-v4-flash-0731",
    ],
)
def test_cheap_seat_floor_innocence_cheap_build_lane_passes(seat):
    """INNOCENCE: any CHEAP_SEATS-prefixed build-lane seat clears the rule,
    even with a trailing version suffix (prefix match, not exact)."""
    pack = {"lanes": [{"lane": "D1", "role": "build", "seat": seat}]}
    viol, notice = check_cheap_seat_floor(pack, _MECHANICAL_DIFF, today=_R9_R11_POST_FLIP)
    assert viol == [] and notice is None


def test_cheap_seat_floor_guilt_non_build_lane_does_not_count():
    """GUILT (for the role filter): a cheap seat on a REVIEW lane does not
    satisfy R11 — the requirement is specifically a build lane."""
    pack = {"lanes": [{"lane": "D1", "role": "review", "seat": "claude-haiku-4-5"},
                       {"lane": "D2", "role": "build", "seat": "claude-opus-5"}]}
    viol, notice = check_cheap_seat_floor(pack, _MECHANICAL_DIFF, today=_R9_R11_POST_FLIP)
    assert viol and "seat_floor" in viol[0]


def test_cheap_seat_floor_innocence_seat_override_reports_not_fails():
    """INNOCENCE: `seat_override` clears the violation and is reported."""
    pack = {
        "lanes": [{"lane": "D1", "role": "build", "seat": "claude-opus-5"}],
        "seat_override": "mechanical-looking diff also touched generated code, verified by hand",
    }
    viol, notice = check_cheap_seat_floor(pack, _MECHANICAL_DIFF, today=_R9_R11_POST_FLIP)
    assert viol == []
    assert notice is not None and "(overridden)" in notice


def test_cheap_seat_floor_innocence_pre_flip_notice_not_fail():
    """INNOCENCE: the same guilty shape only NOTICEs before the flip."""
    pack = {"lanes": [{"lane": "D1", "role": "build", "seat": "claude-opus-5"}]}
    viol, notice = check_cheap_seat_floor(pack, _MECHANICAL_DIFF, today=_R9_R11_PRE_FLIP)
    assert viol == []
    assert notice is not None and "seat_floor" in notice


# ---- R9: check_council_run_gear3 -------------------------------------------


def _write_journal(tmp_path: Path, name: str, lines: list[dict]) -> Path:
    import json as _json

    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(_json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    return p


def test_council_run_innocence_gear_not_3_skipped(tmp_path):
    """INNOCENCE: this rule is Gear-3-only — Gear 1/2 (or unknown gear)
    is not its problem, regardless of council_run."""
    for gear in (None, 1, 2):
        viol, notice = check_council_run_gear3({}, tmp_path, gear, today=_R9_R11_POST_FLIP)
        assert viol == [] and notice is None


def test_council_run_guilt_no_council_run_field_rejected_post_flip(tmp_path):
    """GUILT: a Gear-3 pack with no `council_run` field at all is a
    violation on/after the flip."""
    viol, notice = check_council_run_gear3({}, tmp_path, gear=3, today=_R9_R11_POST_FLIP)
    assert viol and "council_run" in viol[0]
    assert notice is None


def test_council_run_guilt_dangling_or_escaping_path_rejected(tmp_path):
    """GUILT: council_run pointing nowhere, or escaping pack_dir via `..`,
    or an absolute path, all count as zero qualifying seats — none of them
    raise."""
    for bad in ("journal.jsonl", "../../etc/passwd", "/etc/passwd"):
        pack = {"council_run": bad}
        viol, notice = check_council_run_gear3(pack, tmp_path, gear=3, today=_R9_R11_POST_FLIP)
        assert viol and "council_run" in viol[0]


def test_council_run_guilt_single_seat_below_quorum_rejected(tmp_path):
    """GUILT: exactly one distinct qualifying review seat is below the
    >=2 quorum."""
    _write_journal(tmp_path, "journal.jsonl", [
        {"seat": "codex-gpt-5.6-sol", "role": "review", "ok": True, "ts": "2026-08-26T00:00:00Z"},
    ])
    pack = {"council_run": "journal.jsonl"}
    viol, notice = check_council_run_gear3(pack, tmp_path, gear=3, today=_R9_R11_POST_FLIP)
    assert viol and "council_run" in viol[0]
    assert notice is None


def test_council_run_guilt_ok_false_or_wrong_role_does_not_count(tmp_path):
    """GUILT (for the line filter): a line with ok:false, or role != review,
    does not count toward quorum even from a real COUNCIL_REVIEW_SEATS
    member — 2 such lines still leaves zero qualifying seats."""
    _write_journal(tmp_path, "journal.jsonl", [
        {"seat": "codex-gpt-5.6-sol", "role": "review", "ok": False, "ts": "x"},
        {"seat": "kimi-code/k3", "role": "build", "ok": True, "ts": "x"},
    ])
    pack = {"council_run": "journal.jsonl"}
    viol, notice = check_council_run_gear3(pack, tmp_path, gear=3, today=_R9_R11_POST_FLIP)
    assert viol and "council_run" in viol[0]


def test_council_run_guilt_missing_ts_does_not_count(tmp_path):
    """GUILT (regression, refuter round 1 2026-08-27): the declared minimal
    schema is {"seat", "role": "review", "ok": true, "ts"} — a line missing
    `ts` (or with it empty/non-string) was silently accepted before this
    fix; now it does not count toward quorum, same as a missing seat."""
    _write_journal(tmp_path, "journal.jsonl", [
        {"seat": "codex-gpt-5.6-sol", "role": "review", "ok": True},
        {"seat": "kimi-code/k3", "role": "review", "ok": True, "ts": ""},
    ])
    pack = {"council_run": "journal.jsonl"}
    viol, notice = check_council_run_gear3(pack, tmp_path, gear=3, today=_R9_R11_POST_FLIP)
    assert viol and "council_run" in viol[0]


def test_council_run_guilt_duplicate_only_postings_below_quorum_rejected(tmp_path):
    """GUILT (regression, refuter round 1 2026-08-27): the SAME seat
    posting many times must not be mistaken for multiple distinct seats —
    5 lines, all from one seat, is still only 1 distinct seat, still below
    the >=2 quorum."""
    _write_journal(tmp_path, "journal.jsonl", [
        {"seat": "codex-gpt-5.6-sol", "role": "review", "ok": True, "ts": f"t{i}"}
        for i in range(5)
    ])
    pack = {"council_run": "journal.jsonl"}
    viol, notice = check_council_run_gear3(pack, tmp_path, gear=3, today=_R9_R11_POST_FLIP)
    assert viol and "council_run" in viol[0]


def test_council_run_innocence_two_distinct_qualifying_seats_passes(tmp_path):
    """INNOCENCE: >=2 distinct COUNCIL_REVIEW_SEATS members, each ok:true
    role:review, clears the rule — a duplicate posting from the same seat
    does not inflate the distinct count (mirrors the guilt case above)."""
    _write_journal(tmp_path, "council/journal.jsonl", [
        {"seat": "codex-gpt-5.6-sol", "role": "review", "ok": True, "ts": "a"},
        {"seat": "codex-gpt-5.6-sol", "role": "review", "ok": True, "ts": "b"},
        {"seat": "kimi-code/k3", "role": "review", "ok": True, "ts": "c"},
        {"seat": "not-a-council-seat", "role": "review", "ok": True, "ts": "d"},
    ])
    pack = {"council_run": "council/journal.jsonl"}
    viol, notice = check_council_run_gear3(pack, tmp_path, gear=3, today=_R9_R11_POST_FLIP)
    assert viol == [] and notice is None


def test_council_run_innocence_seat_override_reports_not_fails(tmp_path):
    """INNOCENCE: `seat_override` clears the violation and is reported."""
    pack = {"seat_override": "solo emergency hotfix, verified live under active incident"}
    viol, notice = check_council_run_gear3(pack, tmp_path, gear=3, today=_R9_R11_POST_FLIP)
    assert viol == []
    assert notice is not None and "(overridden)" in notice


def test_council_run_innocence_pre_flip_notice_not_fail(tmp_path):
    """INNOCENCE: the same guilty shape only NOTICEs before the flip —
    and this is the day-0 measure the PR body declares: every EXISTING
    Gear-3 pack predates council_run entirely."""
    viol, notice = check_council_run_gear3({}, tmp_path, gear=3, today=_R9_R11_PRE_FLIP)
    assert viol == []
    assert notice is not None and "council_run" in notice


# ---- end-to-end: lint() wires both R11 and R9 through one call site -------


def test_seat_floor_end_to_end_through_lint(tmp_repo):
    """End-to-end: lint() surfaces an R11 seat_floor violation for a real
    pack+brief tree via the public entry point."""
    tmp_path, write_brief, write_pack = tmp_repo
    write_brief(gear=1)
    write_pack(lanes=[{"lane": "D1", "role": "build", "seat": "claude-opus-5"}])
    rc, viol = lint(tmp_path / "evidence" / "pack.yml", tmp_path, _MECHANICAL_DIFF)
    if datetime.datetime.now(datetime.timezone.utc).date() < R9_R11_ENFORCEMENT_DATE:
        assert rc == 0
    else:
        assert rc == 1
        assert any("seat_floor" in v for v in viol)


def test_seat_floor_end_to_end_notice_when_no_changed_files(tmp_repo, capsys):
    """End-to-end regression (refuter round 1 2026-08-27): with no
    --changed-files-file, R11 is silently unable to fire (compute_seat_floor
    is False-by-construction on None) — lint() must SAY so on stderr, the
    same transparency convention rule 6's own skip-notice already has,
    rather than silently doing nothing."""
    tmp_path, write_brief, write_pack = tmp_repo
    write_brief(gear=1)
    write_pack(lanes=[{"lane": "D1", "role": "build", "seat": "claude-opus-5"}])
    rc, viol = lint(tmp_path / "evidence" / "pack.yml", tmp_path, None)
    assert rc == 0 and viol == []
    err = capsys.readouterr().err
    assert "seat_floor check (rule 11) skipped" in err


def test_council_run_end_to_end_through_lint(tmp_repo):
    """End-to-end: lint() surfaces an R9 council_run violation for a real
    Gear-3 pack+brief tree via the public entry point (pack_dir resolution
    comes from pack_path.parent inside lint(), not a parameter the caller
    threads through)."""
    tmp_path, write_brief, write_pack = tmp_repo
    write_brief(gear=3)
    write_pack(dissent=[{"seat": "codex-sol", "objection": "x", "status": "PLAUSIBLE"}])
    rc, viol = lint(tmp_path / "evidence" / "pack.yml", tmp_path, None)
    if datetime.datetime.now(datetime.timezone.utc).date() < R9_R11_ENFORCEMENT_DATE:
        assert rc == 0
    else:
        assert rc == 1
        assert any("council_run" in v for v in viol)


# ---- rule 9: check_pack_not_at_deprecated_root -----------------------------

_ROOT_PRE_FLIP = EVIDENCE_ROOT_DEPRECATION_DATE - datetime.timedelta(days=1)
_ROOT_POST_FLIP = EVIDENCE_ROOT_DEPRECATION_DATE


def test_evidence_root_guilt_root_path_post_flip_rejected(tmp_path):
    viol, notice = check_pack_not_at_deprecated_root(
        "evidence/pack.yml", tmp_path, today=_ROOT_POST_FLIP
    )
    assert notice is None
    assert any("evidence_root_deprecated" in v for v in viol)
    assert any("evidence/pack.yml is deprecated" in v for v in viol)


def test_evidence_root_guilt_absolute_root_path_post_flip_rejected(tmp_path):
    """An absolute path resolving to repo_root/evidence/pack.yml is judged
    the same as its repo-relative form — the resolution helper, not just a
    literal-string match, must catch it."""
    absolute = tmp_path / "evidence" / "pack.yml"
    viol, notice = check_pack_not_at_deprecated_root(
        str(absolute), tmp_path, today=_ROOT_POST_FLIP
    )
    assert notice is None
    assert any("evidence_root_deprecated" in v for v in viol)


def test_evidence_root_innocence_pre_flip_notice_not_fail(tmp_path):
    viol, notice = check_pack_not_at_deprecated_root(
        "evidence/pack.yml", tmp_path, today=_ROOT_PRE_FLIP
    )
    assert viol == []
    assert notice is not None
    assert "evidence_root_deprecated" in notice


def test_evidence_root_innocence_per_task_dir_clean_both_sides():
    """A per-task directory pack is clean on EITHER side of the flip date —
    this rule only ever judges the literal root path, never the per-task
    shape (that belongs to scripts/ci/evidence_paths.py)."""
    for today in (_ROOT_PRE_FLIP, _ROOT_POST_FLIP):
        viol, notice = check_pack_not_at_deprecated_root(
            "evidence/2026-08/ops-evidence-pertask-a0adff64/pack.yml",
            Path("/repo"),
            today=today,
        )
        assert viol == [] and notice is None


def test_evidence_root_innocence_no_source_path_skipped(tmp_path):
    """source_path=None (no --source-path supplied) skips the rule outright
    — same 'skip, don't guess' shape as rules 6/7 without
    --changed-files-file, never presumed guilt or innocence."""
    viol, notice = check_pack_not_at_deprecated_root(None, tmp_path, today=_ROOT_POST_FLIP)
    assert viol == [] and notice is None


def test_evidence_root_innocence_empty_source_path_skipped(tmp_path):
    """source_path="" is treated the same as None — an empty string is
    'no info', not a path that resolves to '.' and slips past the literal
    comparison as clean-by-accident (regression: agy cross-family review,
    2026-08-27, on this PR's own diff)."""
    viol, notice = check_pack_not_at_deprecated_root("", tmp_path, today=_ROOT_POST_FLIP)
    assert viol == [] and notice is None


def test_evidence_root_guilt_dot_segments_normalize_to_root_post_flip(tmp_path):
    """A relative source_path with dot-segments that textually collapses to
    the literal root path IS caught — not left to slip through unnormalized
    (regression: agy cross-family review, 2026-08-27, on this PR's own
    diff: 'evidence/x/../pack.yml' never equalled 'evidence/pack.yml' by
    bare string comparison even though it names the exact same file)."""
    viol, notice = check_pack_not_at_deprecated_root(
        "evidence/x/../pack.yml", tmp_path, today=_ROOT_POST_FLIP
    )
    assert notice is None
    assert any("evidence_root_deprecated" in v for v in viol)


def test_evidence_root_innocence_dot_segments_normalize_to_per_task_clean():
    """The same normalization must not FALSE-POSITIVE a per-task path whose
    dot-segments happen to collapse to itself — only a collapse to the
    literal root path is guilty."""
    viol, notice = check_pack_not_at_deprecated_root(
        "evidence/./2026-08/some-task-a0adff64/pack.yml",
        Path("/repo"),
        today=_ROOT_POST_FLIP,
    )
    assert viol == [] and notice is None


# ---- end-to-end: lint() wires rule 9 through --source-path -----------------


def test_evidence_root_end_to_end_notice_pre_flip_does_not_fail(tmp_repo):
    """End-to-end: lint() wires rule 9 through the public entry point's
    `source_path` parameter, using the REAL current date (2026-08-27, before
    EVIDENCE_ROOT_DEPRECATION_DATE) — lint() never threads a `today`
    override through any phased check, matching rules 8/9/11's existing
    convention, so this exercises the notice branch without pinning it."""
    tmp_path, write_brief, write_pack = tmp_repo
    write_brief(gear=1)
    write_pack()
    rc, viol = lint(
        tmp_path / "evidence" / "pack.yml",
        tmp_path,
        None,
        source_path="evidence/pack.yml",
    )
    if datetime.datetime.now(datetime.timezone.utc).date() < EVIDENCE_ROOT_DEPRECATION_DATE:
        assert rc == 0
        assert not any("evidence_root_deprecated" in v for v in viol)
    else:
        assert rc == 1
        assert any("evidence_root_deprecated" in v for v in viol)


def test_evidence_root_end_to_end_per_task_source_path_clean(tmp_repo):
    """End-to-end innocence: a per-task --source-path never trips rule 9,
    regardless of where lint() actually READ the staged pack from — this is
    the CI staging shape (harness-floor.yml's Gear-3 step lints a copy
    staged at the canonical evidence/pack.yml name, but passes the real
    per-task PACK_PATH as --source-path)."""
    tmp_path, write_brief, write_pack = tmp_repo
    write_brief(gear=1)
    write_pack()
    rc, viol = lint(
        tmp_path / "evidence" / "pack.yml",
        tmp_path,
        None,
        source_path="evidence/2026-08/some-task-a0adff64/pack.yml",
    )
    assert rc == 0
    assert not any("evidence_root_deprecated" in v for v in viol)


def test_evidence_root_end_to_end_no_source_path_default_clean(tmp_repo):
    """lint() called with no source_path at all (the pre-existing call
    shape every other test in this file uses) never trips rule 9 — this is
    the backward-compatibility guarantee: adding rule 9 must not change the
    verdict of any caller that doesn't opt in via --source-path."""
    tmp_path, write_brief, write_pack = tmp_repo
    write_brief(gear=1)
    write_pack()
    rc, viol = lint(tmp_path / "evidence" / "pack.yml", tmp_path, None)
    assert rc == 0
    assert not any("evidence_root_deprecated" in v for v in viol)


def test_evidence_root_cli_source_path_defaults_to_pack_path_argument(tmp_repo):
    """CLI contract: with no --source-path flag, main() defaults source_path
    to the PACK_PATH positional argument itself — the correct default for a
    direct/local invocation, where the path you point the linter at IS the
    real path. Exercised via subprocess so this pins the actual CLI wiring,
    not just the Python-level default."""
    tmp_path, write_brief, write_pack = tmp_repo
    write_brief(gear=1)
    write_pack()
    result = subprocess.run(
        [
            sys.executable, str(SCRIPTS / "evidence_pack_lint.py"),
            "evidence/pack.yml", "--repo-root", str(tmp_path), "--json",
        ],
        capture_output=True, text=True, timeout=30,
    )
    import json as _json

    payload = _json.loads(result.stdout)
    if datetime.datetime.now(datetime.timezone.utc).date() < EVIDENCE_ROOT_DEPRECATION_DATE:
        assert payload["exit"] == 0
    else:
        assert payload["exit"] == 1
        assert any("evidence_root_deprecated" in v for v in payload["violations"])


def test_evidence_root_cli_explicit_source_path_overrides_default(tmp_repo):
    """CLI contract: an explicit --source-path PER-TASK value overrides the
    positional-argument default even though the positional PACK_PATH itself
    is the root literal — this is exactly the CI staging shape (the staged
    file always lives at the canonical evidence/pack.yml name, but
    --source-path names the real per-task path)."""
    tmp_path, write_brief, write_pack = tmp_repo
    write_brief(gear=1)
    write_pack()
    result = subprocess.run(
        [
            sys.executable, str(SCRIPTS / "evidence_pack_lint.py"),
            "evidence/pack.yml", "--repo-root", str(tmp_path),
            "--source-path", "evidence/2026-08/some-task-a0adff64/pack.yml",
            "--json",
        ],
        capture_output=True, text=True, timeout=30,
    )
    import json as _json

    payload = _json.loads(result.stdout)
    assert payload["exit"] == 0
    assert not any("evidence_root_deprecated" in v for v in payload["violations"])


# ---- rule 12: check_brief_not_at_deprecated_root ---------------------------
#
# Rule 9 above judges the PACK's path and is structurally blind to the BRIEF.
# Measured on origin/main 2026-08-31: six open PRs wrote the root brief, and
# #5158 had the shape rule 9 cannot see — pack already migrated to a per-task
# directory, brief still at the root, rule 9 green while the collision was
# live. These tests pin BOTH the new rule's guilt and the one innocence case
# that would break the whole fleet if it regressed: the mandatory
# `brief_ref: evidence/brief.yml` STRING must never be mistaken for a root
# brief FILE write.

_BRIEF_ROOT_PRE_FLIP = EVIDENCE_ROOT_BRIEF_DEPRECATION_DATE - datetime.timedelta(days=1)
_BRIEF_ROOT_POST_FLIP = EVIDENCE_ROOT_BRIEF_DEPRECATION_DATE


def test_brief_root_guilt_root_path_post_flip_rejected(tmp_path):
    viol, notice = check_brief_not_at_deprecated_root(
        "evidence/brief.yml", tmp_path, today=_BRIEF_ROOT_POST_FLIP
    )
    assert notice is None
    assert any("evidence_root_brief_deprecated" in v for v in viol)
    assert any("evidence/brief.yml is deprecated as a WRITE target" in v for v in viol)


def test_brief_root_guilt_absolute_root_path_post_flip_rejected(tmp_path):
    """An absolute path resolving to repo_root/evidence/brief.yml is judged the
    same as its repo-relative form — a literal-string match alone would miss
    it, so the shared resolution helper must be doing the work."""
    absolute = tmp_path / "evidence" / "brief.yml"
    viol, notice = check_brief_not_at_deprecated_root(
        str(absolute), tmp_path, today=_BRIEF_ROOT_POST_FLIP
    )
    assert notice is None
    assert any("evidence_root_brief_deprecated" in v for v in viol)


def test_brief_root_guilt_dot_segments_normalize_to_root_post_flip(tmp_path):
    """`evidence/x/../brief.yml` names the root brief; a textual comparison
    would pass it as per-task. Same gap a cross-family review caught in rule 9
    (see _pack_source_relpath's docstring) — it must not reopen here."""
    viol, notice = check_brief_not_at_deprecated_root(
        "evidence/x/../brief.yml", tmp_path, today=_BRIEF_ROOT_POST_FLIP
    )
    assert notice is None
    assert any("evidence_root_brief_deprecated" in v for v in viol)


def test_brief_root_innocence_pre_flip_notice_not_fail(tmp_path):
    viol, notice = check_brief_not_at_deprecated_root(
        "evidence/brief.yml", tmp_path, today=_BRIEF_ROOT_PRE_FLIP
    )
    assert viol == []
    assert notice is not None
    assert "evidence_root_brief_deprecated" in notice


def test_brief_root_innocence_per_task_dir_clean_both_sides():
    """A per-task brief is clean on EITHER side of the flip — this rule only
    judges the literal root path, never the per-task shape."""
    for today in (_BRIEF_ROOT_PRE_FLIP, _BRIEF_ROOT_POST_FLIP):
        viol, notice = check_brief_not_at_deprecated_root(
            "evidence/2026-08/ops-evidence-pertask-a0adff64/brief.yml",
            Path("/repo"),
            today=today,
        )
        assert viol == [] and notice is None


def test_brief_root_innocence_no_brief_source_path_skipped(tmp_path):
    """None/empty means the caller has no diff context — skip, don't guess.
    This is also the LOCAL-invocation path: `evidence_pack_lint.py
    evidence/pack.yml` knows the pack but not the brief, and there is
    deliberately no positional fallback to invent one."""
    for value in (None, ""):
        viol, notice = check_brief_not_at_deprecated_root(
            value, tmp_path, today=_BRIEF_ROOT_POST_FLIP
        )
        assert viol == [] and notice is None


def test_brief_root_does_not_ride_the_pack_rules_flip_date():
    """The two dates are deliberately separate (see the constant's comment):
    adding the brief to the pack's 2026-09-05 would silently re-price the
    readiness measurement taken the day this rule was written. On the pack's
    flip date the brief must still only NOTICE."""
    assert EVIDENCE_ROOT_BRIEF_DEPRECATION_DATE > EVIDENCE_ROOT_DEPRECATION_DATE
    viol, notice = check_brief_not_at_deprecated_root(
        "evidence/brief.yml", Path("/repo"), today=EVIDENCE_ROOT_DEPRECATION_DATE
    )
    assert viol == []
    assert notice is not None


def test_brief_root_innocence_mandatory_brief_ref_string_is_not_a_root_write(tmp_repo):
    """THE load-bearing innocence case. Every conformant pack in this repo is
    REQUIRED to declare the literal `brief_ref: evidence/brief.yml` — the
    staging contract (scripts/ci/evidence_paths.py's module docstring). A rule
    that judged that STRING instead of the PR's written PATH would fail every
    correct pack in the fleet.

    The pack below carries that mandatory string (asserted, not assumed) while
    the PR's resolved brief path is per-task. The rule therefore RUNS — it is
    given a real path, so it does not short-circuit — and must still find the
    pack clean, which is only possible if it never reads `brief_ref` at all.

    IT ASSERTS ON STDERR, NOT ONLY ON THE VIOLATION LIST, and that is the
    whole point — two drafts of this test were insensitive before this one:

      1. The first omitted `brief_source_path` entirely. VACUOUS: with no path
         the function returns at its first line, so the assertion held whether
         the rule existed or not. It pinned the skip-when-blind branch (already
         covered by test_brief_root_innocence_no_brief_source_path_skipped)
         while claiming to pin the string-vs-path distinction.
      2. The second supplied the path but still asserted only `rc == 0` and an
         empty violation list. Also insensitive: today is BEFORE the flip date,
         so a rule that over-matched every path would emit a NOTICE and still
         exit 0 — proven by mutation, `if False:` in place of the path
         comparison left this test green.

    A notice goes to stderr, so stderr is where an over-matching rule becomes
    visible before its flip date. Verified by mutation both ways: neutering the
    comparison kills the guilt tests, over-matching it kills this one."""
    tmp_path, write_brief, write_pack = tmp_repo
    write_brief(gear=1)
    pack_file = write_pack()
    assert "brief_ref: evidence/brief.yml" in pack_file.read_text(encoding="utf-8")
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        rc, viol = lint(
            tmp_path / "evidence" / "pack.yml",
            tmp_path,
            None,
            brief_source_path="evidence/2026-08/some-task-a0adff64/brief.yml",
        )
    assert rc == 0
    assert not any("evidence_root_brief_deprecated" in v for v in viol)
    assert "evidence_root_brief_deprecated" not in err.getvalue()


def test_brief_root_end_to_end_notice_pre_flip_does_not_fail(tmp_repo):
    """End-to-end through lint() with a ROOT brief path: today is before the
    flip date, so this NOTICEs and exits 0.

    It asserts the notice IS EMITTED, not merely that nothing failed. Asserting
    only `rc == 0` would leave this test green against a DELETED rule — the
    guilt tests would still catch that, but a test that cannot tell "correctly
    silent" from "not wired up at all" is not evidence of wiring, and wiring is
    exactly what this end-to-end case exists to prove."""
    tmp_path, write_brief, write_pack = tmp_repo
    write_brief(gear=1)
    write_pack()
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        rc, viol = lint(
            tmp_path / "evidence" / "pack.yml",
            tmp_path,
            None,
            brief_source_path="evidence/brief.yml",
        )
    assert rc == 0
    assert not any("evidence_root_brief_deprecated" in v for v in viol)
    assert "evidence_root_brief_deprecated" in err.getvalue()


def test_brief_root_resolver_seam_produces_diff_relative_paths_not_the_staged_name():
    """THE SEAM TEST, and it exists because a cross-family reviewer refused to
    take it on faith (tp1-glm-5.2, 2026-08-31, on this PR's own diff).

    Its objection: the rule's safety rests entirely on `--brief-source-path`
    carrying a DIFF-RELATIVE path. CI lints a synthetic tree where the brief is
    always staged under the canonical name `evidence/brief.yml`; if the value
    handed to this rule came from that tree, then on the flip date EVERY
    conformant PR in the fleet would be judged as writing the root brief and
    the whole queue would go red. The reviewer's verdict was DO-NOT-SHIP on the
    grounds that the diff asserted the link in a docstring and pinned it
    nowhere — the assertion spans two modules, so neither module's own tests
    covered it.

    The conclusion was wrong and the demand was right. `resolve_evidence_path`
    is a pure function over the changed-files LIST — it never touches the
    filesystem, so it cannot see the staged tree, and harness-floor.yml calls
    it at Step 2b, before staging exists at all. This test pins that end to
    end rather than restating it: the resolver's real output, for each of the
    three diff shapes, fed to the real rule."""
    # scripts/ci is not on sys.path for this module (only scripts/ is), and it
    # is added HERE rather than at import time on purpose: a module-level
    # sys.path mutation would change resolution for every other test in this
    # file, which is a side effect nobody reading them would expect.
    sys.path.insert(0, str(SCRIPTS / "ci"))
    from evidence_paths import resolve_evidence_path  # noqa: PLC0415

    per_task = "evidence/2026-08/agent-x-infra-thing-a0adff64/brief.yml"

    # (1) a PR that wrote a per-task brief -> per-task path -> clean, even
    #     past the flip date. This is the case the reviewer feared would
    #     collapse to the staged canonical name. It does not.
    resolved = resolve_evidence_path("brief", ["scripts/x.py", per_task])
    assert resolved == per_task
    viol, notice = check_brief_not_at_deprecated_root(
        resolved, Path("/repo"), today=_BRIEF_ROOT_POST_FLIP
    )
    assert viol == [] and notice is None

    # (2) a PR that wrote the ROOT brief -> root path -> flagged. The rule
    #     must still bite, or it protects nothing.
    resolved = resolve_evidence_path("brief", ["scripts/x.py", "evidence/brief.yml"])
    assert resolved == "evidence/brief.yml"
    viol, _ = check_brief_not_at_deprecated_root(
        resolved, Path("/repo"), today=_BRIEF_ROOT_POST_FLIP
    )
    assert any("evidence_root_brief_deprecated" in v for v in viol)

    # (3) a PR that wrote NO brief also resolves to the root path (documented
    #     pre-migration fallback). That shape never reaches this rule, because
    #     harness-floor.yml gates the lint step on the brief being present in
    #     THIS PR's diff — recorded here so a future reader who finds the
    #     fallback alarming can see it was considered, not missed.
    assert resolve_evidence_path("brief", ["scripts/x.py"]) == "evidence/brief.yml"


def test_brief_root_cli_accepts_and_threads_brief_source_path(tmp_repo):
    """CLI contract: --brief-source-path is accepted and reaches the rule. Run
    with a per-task value so the assertion is about THREADING, not about the
    date — a value the rule must find clean, on stderr as well as in the
    violation list (pre-flip, an over-matching rule shows up ONLY on stderr)."""
    tmp_path, write_brief, write_pack = tmp_repo
    write_brief(gear=1)
    write_pack()
    result = subprocess.run(
        [
            sys.executable, str(SCRIPTS / "evidence_pack_lint.py"),
            "evidence/pack.yml", "--repo-root", str(tmp_path),
            "--brief-source-path", "evidence/2026-08/some-task-a0adff64/brief.yml",
            "--json",
        ],
        capture_output=True, text=True, timeout=30,
    )
    import json as _json

    payload = _json.loads(result.stdout)
    assert payload["exit"] == 0
    assert not any("evidence_root_brief_deprecated" in v for v in payload["violations"])
    assert "evidence_root_brief_deprecated" not in result.stderr


def test_brief_root_cli_absent_flag_leaves_rule_inert(tmp_repo):
    """CLI contract, and the DIVERGENCE from --source-path worth pinning:
    --source-path defaults to the positional pack argument, --brief-source-path
    has NO fallback. Omitted, rule 12 is inert — a local run must not invent a
    brief location it cannot know."""
    tmp_path, write_brief, write_pack = tmp_repo
    write_brief(gear=1)
    write_pack()
    result = subprocess.run(
        [
            sys.executable, str(SCRIPTS / "evidence_pack_lint.py"),
            "evidence/pack.yml", "--repo-root", str(tmp_path), "--json",
        ],
        capture_output=True, text=True, timeout=30,
    )
    import json as _json

    payload = _json.loads(result.stdout)
    assert payload["exit"] == 0
    assert not any("evidence_root_brief_deprecated" in v for v in payload["violations"])
    assert "evidence_root_brief_deprecated" not in result.stderr


# --------------------------------------------------------- check_countable_claims

#: A numstat blob standing in for `git diff --numstat <merge-base>..HEAD`:
#: 2 changed files, +1860/-83. The numbers are the REAL measurement PR #5157's
#: pack contradicted (its prose said "11 files, +1195/-119 across two commits"
#: where the cited command returned 14 files, +1860/-83 and 6 commits).
CC_NUMSTAT = "1800\t60\ta.py\n60\t23\tb.py\n"
CC_RECEIPTS = [{
    "claim": "the narrow suite passes", "cmd": "pytest -q",
    "result": "64 passed", "exit": 0,
    "ts": "2026-08-29T00:00:00Z", "seat": "sonnet-5",
}]


def test_countable_guilt_wrong_diff_stats_rejected():
    """GUILT: narrated file count and +ins/-del that contradict the measured
    numstat are convicted, and the message carries computed, narrated AND the
    command that produced the computed value."""
    violations, _notices = check_countable_claims(
        {"diff": {"net_lines": "11 files, +1195/-119"}, "receipts": CC_RECEIPTS},
        CC_NUMSTAT, commits=6,
    )
    assert len(violations) == 2
    joined = " ".join(violations)
    assert '"11 files"' in joined and "changes 2" in joined
    assert '"+1195/-119"' in joined and "+1860/-83" in joined
    assert "git diff --numstat" in joined


def test_countable_guilt_wrong_commit_count_rejected_digit_and_word():
    """GUILT: "two commits" and "both commits" are both count claims, and both
    are convicted against a 6-commit branch — #5157 made the second form."""
    violations, _ = check_countable_claims(
        {"diff": {"net_lines": "across two commits"},
         "lanes": [{"lane": "D1", "role": "build", "seat": "codex",
                    "note": "both commits reviewed"}],
         "receipts": CC_RECEIPTS},
        CC_NUMSTAT, commits=6,
    )
    assert len(violations) == 2
    assert all("git rev-list --count" in v for v in violations)


def test_countable_guilt_unsubstantiated_test_count_rejected():
    """GUILT: "the 44 tests" with no receipt reporting 44 is prose asserting a
    measurement nobody took."""
    violations, _ = check_countable_claims(
        {"lanes": [{"lane": "D1", "role": "build", "seat": "codex",
                    "note": "both lanes, the 44 tests"}],
         "receipts": CC_RECEIPTS},
        CC_NUMSTAT, commits=2,
    )
    assert any('"44 tests"' in v for v in violations)


def test_countable_innocence_accurate_numbers_pass():
    """INNOCENCE: the same fields with the COMPUTED values are clean — the rule
    convicts inaccuracy, not the act of stating a number."""
    assert check_countable_claims(
        {"diff": {"net_lines": "2 files, +1860/-83 across 6 commits"},
         "lanes": [{"lane": "D1", "role": "build", "seat": "codex",
                    "note": "64 tests pass"}],
         "receipts": CC_RECEIPTS},
        CC_NUMSTAT, commits=6,
    ) == ([], [])


def test_countable_innocence_unmeasured_notices_never_convicts():
    """INNOCENCE: with no numstat and no commit count, the same wrong pack
    NOTICEs and does not fail — "could not measure" is never "guilty" (same
    discipline as the floor's size term)."""
    violations, notices = check_countable_claims(
        {"diff": {"net_lines": "11 files, +1195/-119 across two commits"},
         "receipts": CC_RECEIPTS},
        None, commits=None,
    )
    assert violations == []
    assert len(notices) == 2


def test_countable_innocence_dissent_and_receipts_out_of_scope():
    """INNOCENCE (superscar #3, guard-over-match): judgment prose keeps its
    numbers. Identical wrong figures inside `dissent` — and inside the receipts
    themselves — are not this rule's business."""
    assert check_countable_claims(
        {"dissent": [{"seat": "kimi", "objection": "11 files, +1195/-119, two commits, 44 tests",
                      "status": "CONFIRMED", "resolution": "x"}],
         "receipts": CC_RECEIPTS},
        CC_NUMSTAT, commits=6,
    ) == ([], [])


def test_countable_innocence_binary_file_downgrades_line_counts_to_notice():
    """INNOCENCE: numstat cannot report line counts for a binary file, so the
    computed +ins/-del is a lower bound — a mismatch NOTICEs instead of
    convicting, while the file COUNT (which binary rows do not corrupt) stays
    enforced."""
    numstat = "10\t2\ta.py\n-\t-\tlogo.png\n"
    violations, notices = check_countable_claims(
        {"diff": {"net_lines": "2 files, +999/-999"}, "receipts": CC_RECEIPTS},
        numstat, commits=1,
    )
    assert violations == []
    assert any("+10/-2" in n for n in notices)


def test_parse_numstat_totals_guilt_and_innocence():
    """The pure measurement function: real rows sum, binary rows count as files
    but not as lines, and an unusable blob returns None (never a false zero)."""
    assert parse_numstat_totals(CC_NUMSTAT) == (2, 1860, 83, False)
    assert parse_numstat_totals("10\t2\ta.py\n-\t-\tlogo.png\n") == (2, 10, 2, True)
    assert parse_numstat_totals(None) is None
    assert parse_numstat_totals("") is None
    assert parse_numstat_totals("garbage\n") is None


def test_measured_commit_count_reads_pull_request_event_payload(tmp_path):
    """In CI the commit count comes from the event payload with NO workflow
    change; an explicit flag wins, and a merge_group-shaped payload (no
    pull_request key) degrades to None rather than guessing."""
    import json as _json

    pr_event = tmp_path / "pr.json"
    pr_event.write_text(_json.dumps({"pull_request": {"commits": 6}}), encoding="utf-8")
    assert measured_commit_count(None, str(pr_event)) == 6
    assert measured_commit_count(3, str(pr_event)) == 3

    mg_event = tmp_path / "mg.json"
    mg_event.write_text(_json.dumps({"merge_group": {"head_sha": "abc"}}), encoding="utf-8")
    assert measured_commit_count(None, str(mg_event)) is None
    assert measured_commit_count(None, str(tmp_path / "missing.json")) is None


def test_countable_end_to_end_red_pack_fails_and_green_pack_passes(tmp_repo):
    """RED-FIRST PROOF, end to end through lint(): the SAME pack fails with the
    narrated numbers PR #5157 carried and passes once they are corrected to the
    computed ones. Nothing else about the pack changes between the two runs."""
    tmp_path, write_brief, write_pack = tmp_repo
    write_brief(gear=2)

    wrong = write_pack(
        diff={"net_lines": "11 files, +1195/-119 across two commits"},
        lanes=[{"lane": "D1", "role": "build", "seat": "codex", "note": "the 44 tests"}],
        receipts=CC_RECEIPTS,
    )
    exit_code, violations = lint(
        wrong, tmp_path, None, numstat_text=CC_NUMSTAT, measured_commits=6
    )
    assert exit_code == 1
    assert len([v for v in violations if "countable claim" in v]) == 4

    right = write_pack(
        diff={"net_lines": "2 files, +1860/-83 across 6 commits"},
        lanes=[{"lane": "D1", "role": "build", "seat": "codex", "note": "64 tests pass"}],
        receipts=CC_RECEIPTS,
    )
    exit_code, violations = lint(
        right, tmp_path, None, numstat_text=CC_NUMSTAT, measured_commits=6
    )
    assert exit_code == 0
    assert violations == []


def test_print_measured_emits_pasteable_sentence(tmp_path):
    """The GENERATE half: `--print-measured` hands the author the canonical
    sentence so the value never has to be counted by hand."""
    import os as _os

    numstat = tmp_path / "numstat.txt"
    numstat.write_text(CC_NUMSTAT, encoding="utf-8")
    env = {**_os.environ}
    env.pop("GITHUB_EVENT_PATH", None)
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "evidence_pack_lint.py"),
         "--print-measured", "--numstat-file", str(numstat), "--commit-count", "6"],
        capture_output=True, text=True, timeout=30, env=env,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "2 files, +1860/-83, 6 commits"
    assert format_measured_claims(CC_NUMSTAT, 6) == "2 files, +1860/-83, 6 commits"


# --------------------------------------------------------- check_acceptance_probe_pairing

CAP_RECEIPT_FOO = {"claim": "foo test", "cmd": "pytest -k foo", "exit": 0,
                    "ts": "2026-08-10T00:00:00Z", "seat": "sonnet-5"}
CAP_RECEIPT_DRAIN = {"claim": "drain test", "cmd": "pytest -k drain", "exit": 0,
                      "ts": "2026-08-10T00:00:00Z", "seat": "sonnet-5"}
CAP_RECEIPT_BAR = {"claim": "bar test", "cmd": "pytest -k bar", "exit": 0,
                    "ts": "2026-08-10T00:00:00Z", "seat": "sonnet-5"}
CAP_RECEIPT_BAZ = {"claim": "baz test", "cmd": "pytest -k baz", "exit": 0,
                    "ts": "2026-08-10T00:00:00Z", "seat": "sonnet-5"}
CAP_RECEIPT_SHA = {"claim": "sha256 verified against source manifest",
                    "cmd": "python3 verify.py", "exit": 0,
                    "ts": "2026-08-10T00:00:00Z", "seat": "sonnet-5"}


def test_acceptance_probe_guilt_legacy_bullets_notice():
    """GUILT: a Gear-2 brief with two legacy (bare-string) acceptance
    bullets — a legacy bullet can never carry a `probe:` — pins exactly
    one N1 (probe-coverage) notice naming both as uncovered. Both bullets
    carry SHALL so N3 (EARS shape) stays silent, isolating the assertion
    to N1 alone."""
    brief = {
        "acceptance": [
            "WHEN a client submits the form THE system SHALL confirm receipt.",
            "WHILE the queue is draining THE worker SHALL not double-process an item.",
        ],
    }
    notices = check_acceptance_probe_pairing(brief, {}, 2)
    assert len(notices) == 1
    assert notices[0].startswith("acceptance-probe: 2 of 2")


def test_acceptance_probe_guilt_unbound_probe_notice():
    """GUILT: a declared probe ("pytest -k foo") that appears in no
    receipt's claim/cmd — GOOD_RECEIPT's cmd is "pytest -q", which
    contains neither substring in either direction — fires N2 (receipt
    binding), naming the outcome unrecorded."""
    brief = {
        "acceptance": [
            {"text": "WHEN the suite runs THE gate SHALL report the exit code.",
             "probe": "pytest -k foo"},
        ],
    }
    notices = check_acceptance_probe_pairing(brief, {"receipts": [GOOD_RECEIPT]}, 2)
    assert any("unrecorded" in n for n in notices)


def test_acceptance_probe_guilt_non_ears_text_notice():
    """GUILT: a bullet's text carries no EARS keyword at all, even though
    its probe is declared and bound to a receipt (isolating the
    assertion to N3 — N1/N2 stay silent)."""
    brief = {
        "acceptance": [
            {"text": "the deploy finishes and the health check returns green",
             "probe": "pytest -k bar"},
        ],
    }
    notices = check_acceptance_probe_pairing(brief, {"receipts": [CAP_RECEIPT_BAR]}, 2)
    assert any("not EARS-shaped" in n for n in notices)


def test_acceptance_probe_guilt_lowercase_ears_words_do_not_count():
    """GUILT (case-sensitivity, the real point of this fixture): a bullet
    reading "the check is green if the migration applies when run" has
    lowercase "if"/"when" — ordinary prose, not an EARS clause — so N3
    fires exactly as if no keyword were present at all. Probe is
    declared and bound, isolating the assertion to N3."""
    brief = {
        "acceptance": [
            {"text": "the check is green if the migration applies when run",
             "probe": "pytest -k baz"},
        ],
    }
    notices = check_acceptance_probe_pairing(brief, {"receipts": [CAP_RECEIPT_BAZ]}, 2)
    assert any("not EARS-shaped" in n for n in notices)


def test_acceptance_probe_innocence_fully_probed_pack_silent():
    """INNOCENCE: every bullet declares a probe, every probe's stripped
    text is a verbatim substring of a receipt's cmd, and every text
    carries SHALL — all three notice classes stay silent."""
    brief = {
        "acceptance": [
            {"text": "WHEN the suite runs THE gate SHALL report the exit code.",
             "probe": "pytest -k foo"},
            {"text": "WHILE the queue is draining THE worker SHALL not double-process.",
             "probe": "pytest -k drain"},
        ],
    }
    pack = {"receipts": [CAP_RECEIPT_FOO, CAP_RECEIPT_DRAIN]}
    assert check_acceptance_probe_pairing(brief, pack, 2) == []


def test_acceptance_probe_innocence_gear1_out_of_scope():
    """INNOCENCE: the exact guilty shape from
    test_acceptance_probe_guilt_legacy_bullets_notice (two uncovered
    legacy bullets, which fires N1 at gear>=2) is silent at gear=1 — the
    same `type(gear) is int and gear >= 2` scope guard check_gear_floor
    itself uses."""
    brief = {
        "acceptance": [
            "WHEN a client submits the form THE system SHALL confirm receipt.",
            "WHILE the queue is draining THE worker SHALL not double-process an item.",
        ],
    }
    assert check_acceptance_probe_pairing(brief, {}, 1) == []


def test_acceptance_probe_innocence_absent_block_silent():
    """INNOCENCE: a brief with no `acceptance:` key at all (an empty
    mapping) is not this rule's problem at any gear >= 2."""
    assert check_acceptance_probe_pairing({}, {}, 2) == []


def test_acceptance_probe_innocence_probe_bound_via_claim():
    """INNOCENCE: a probe bound via a receipt's `claim` field, not its
    `cmd` — CAP_RECEIPT_SHA's claim contains the probe's exact text while
    its cmd ("python3 verify.py") does not — still counts as bound (N2
    scans BOTH fields, per rule 12's docstring)."""
    brief = {
        "acceptance": [
            {"text": "WHEN the case closes THE report SHALL cite the sha.",
             "probe": "sha256 verified against source"},
        ],
    }
    assert check_acceptance_probe_pairing(brief, {"receipts": [CAP_RECEIPT_SHA]}, 2) == []


def test_acceptance_probe_guilt_probe_not_bound_inside_longer_word():
    """GUILT: a probe must bind as a whole token, not as a bare substring.
    Before the 2026-08-29 adversarial fix, probe `ls` was considered BOUND by
    a receipt reading "run the tools suite" — the under-match direction of
    superscar #3: the notice that should have said "this probe has no
    receipt" said nothing at all."""
    brief = {"gear": 2, "acceptance": [{"text": "SHALL run", "probe": "ls"}]}
    notices = check_acceptance_probe_pairing(
        brief, {"receipts": [{"cmd": "run the tools suite"}]}, 2
    )
    assert any("unrecorded" in n for n in notices)


def test_acceptance_probe_innocence_probe_binds_as_whole_token():
    """INNOCENCE (the other half of the same fix): the boundary must not make
    a genuine probe unbindable. `ls` IS bound by `ls -la`, and a probe whose
    receipt carries extra flags still binds."""
    brief = {"gear": 2, "acceptance": [{"text": "SHALL run", "probe": "ls"}]}
    assert not any(
        "unrecorded" in n
        for n in check_acceptance_probe_pairing(brief, {"receipts": [{"cmd": "ls -la"}]}, 2)
    )
    flagged = {"gear": 2, "acceptance": [{"text": "SHALL t", "probe": "pytest -k foo"}]}
    assert not any(
        "unrecorded" in n
        for n in check_acceptance_probe_pairing(
            flagged, {"receipts": [{"cmd": "pytest -k foo --verbose"}]}, 2
        )
    )


def test_acceptance_probe_innocence_duplicate_probes_counted_once():
    """INNOCENCE: two bullets naming the SAME probe are one probe to bind.
    Counting per-bullet made the notice overstate the gap ("2 declared
    probe(s)" for a single string)."""
    brief = {"gear": 2, "acceptance": [
        {"text": "SHALL a", "probe": "same-probe"},
        {"text": "SHALL b", "probe": "same-probe"},
    ]}
    notices = check_acceptance_probe_pairing(brief, {"receipts": []}, 2)
    assert any("1 declared probe(s)" in n for n in notices)


def test_acceptance_probe_innocence_examples_sanitize_quotes_and_newlines():
    """INNOCENCE: acceptance text arrives from YAML block scalars and
    legitimately carries newlines and quotes. Un-sanitised, ONE notice spanned
    several stderr lines and its `"..."` delimiters never closed — a
    grep-hostile message (reproduced before the fix)."""
    notices = check_acceptance_probe_pairing(
        {"gear": 2, "acceptance": ['he said "go"\nsecond line']}, {}, 2
    )
    assert notices
    for n in notices:
        assert "\n" not in n
        assert '"go"' not in n
    assert any("'go'" in n for n in notices)


def test_acceptance_probe_innocence_non_mapping_pack_does_not_crash():
    """INNOCENCE: a NOTICE-only rule must never be able to fail a run. Called
    directly with `pack=None` it raised AttributeError before the fix; it now
    treats the absent pack as carrying no receipts."""
    brief = {"gear": 2, "acceptance": [{"text": "SHALL x", "probe": "p"}]}
    assert any("unrecorded" in n for n in check_acceptance_probe_pairing(brief, None, 2))


def test_acceptance_probe_end_to_end_notice_reaches_stderr(tmp_repo, capsys):
    """End-to-end (same 'wiring, not just return value' pattern as
    test_seat_rules_end_to_end_notice_prints_to_stderr): rule 12 is
    NOTICE-only UNCONDITIONALLY (no phased flip date, unlike rules 8-10)
    — lint() must return rc == 0 on a Gear-2 pack with uncovered legacy
    acceptance bullets, and the operator must still see the
    "acceptance-probe" text on stderr."""
    tmp_path, write_brief, write_pack = tmp_repo
    write_brief(gear=2, acceptance=[
        "WHEN a client submits the form THE system SHALL confirm receipt.",
    ])
    write_pack()
    rc, viol = lint(tmp_path / "evidence" / "pack.yml", tmp_path, None)
    assert rc == 0
    assert viol == []
    captured = capsys.readouterr()
    assert "acceptance-probe" in captured.err
    assert "NOTICE" in captured.err


# --------------------------------------------------------- check_assumptions_register

AA_RECEIPT_B211A = {"claim": "b211a probe", "cmd": "pytest -k test_b211a_probe", "exit": 0,
                     "ts": "2026-08-29T00:00:00Z", "seat": "sonnet-5"}


def test_assumptions_guilt_unverified_entry_notice():
    """GUILT: a single mapping entry with `status: unverified` pins exactly
    one N1 (unverified) notice naming the total out of one."""
    brief = {
        "assumptions": [
            {"text": "the client already holds a valid B211A", "status": "unverified",
             "probe": "pytest -k test_b211a_probe"},
        ],
    }
    notices = check_assumptions_register(brief)
    assert len(notices) == 1
    assert notices[0].startswith("assumptions: 1 of 1")
    assert "still 'unverified'" in notices[0]


def test_assumptions_guilt_status_pending_fires_n2_not_n1():
    """GUILT: `status: pending` is neither `verified` nor `unverified` — it
    fires N2 (unadjudicated) and must NOT fire N1, or the whole point of
    N2 (a status other than the literal string can't hide) is untested."""
    brief = {"assumptions": [{"text": "the queue drains nightly", "status": "pending"}]}
    notices = check_assumptions_register(brief)
    assert any("no recognised status" in n for n in notices)
    assert not any("still 'unverified'" in n for n in notices)


def test_assumptions_guilt_status_typo_fires_n2_not_n1():
    """GUILT: the typo `unverfied` (one keystroke short of `unverified`) is
    the load-bearing case for N2 — matching only the literal `unverified`
    string in N1 would let this escape in total silence."""
    brief = {"assumptions": [{"text": "the mirror is idempotent", "status": "unverfied"}]}
    notices = check_assumptions_register(brief)
    assert any("no recognised status" in n for n in notices)
    assert not any("still 'unverified'" in n for n in notices)


def test_assumptions_guilt_bare_string_entry_fires_n2():
    """GUILT: an entry that is not a mapping at all (a bare string, the
    same legacy shape rule 12 accepts for `acceptance:`) has no status to
    read and fires N2."""
    brief = {"assumptions": ["the API key never expires"]}
    notices = check_assumptions_register(brief)
    assert any("no recognised status" in n for n in notices)


def test_assumptions_guilt_missing_status_key_fires_n2():
    """GUILT: a mapping entry with no `status:` key at all fires N2, same
    as an unrecognised value — missing is not a special case."""
    brief = {"assumptions": [{"text": "the cron runs hourly"}]}
    notices = check_assumptions_register(brief)
    assert any("no recognised status" in n for n in notices)


def test_assumptions_guilt_unverified_without_probe_fires_n1_and_n3():
    """GUILT: an `unverified` entry with no usable `probe:` fires BOTH N1
    (it is unverified) and N3 (nothing names the check that would settle
    it) — the two are independent facts about the same entry."""
    brief = {"assumptions": [{"text": "the ledger is append-only", "status": "unverified"}]}
    notices = check_assumptions_register(brief)
    assert any("still 'unverified'" in n for n in notices)
    assert any("declare no 'probe:'" in n for n in notices)


def test_assumptions_innocence_all_verified_silent():
    """INNOCENCE: every entry declaring `status: verified` is silent."""
    brief = {
        "assumptions": [
            {"text": "the schema migration already ran", "status": "verified"},
            {"text": "the receipt format is stable", "status": "verified"},
        ],
    }
    assert check_assumptions_register(brief) == []


def test_assumptions_innocence_absent_block_silent():
    """INNOCENCE: no `assumptions:` key at all — the block is opt-in, and
    absence must never be read as a gap."""
    assert check_assumptions_register({}) == []


def test_assumptions_innocence_empty_list_silent():
    """INNOCENCE: `assumptions: []` (declared, deliberately empty) is
    silent, same as absent."""
    assert check_assumptions_register({"assumptions": []}) == []


def test_assumptions_innocence_brief_none_does_not_crash():
    """INNOCENCE: `brief=None` (rule 6's check_brief_ref_exists already
    flagged that elsewhere) must not raise — a NOTICE-only rule crashing
    is the one thing it can never do."""
    assert check_assumptions_register(None) == []


def test_assumptions_innocence_non_list_assumptions_do_not_crash():
    """INNOCENCE: `assumptions:` present but shaped as a mapping or a bare
    string (not a list) must not crash — it is simply out of scope,
    identical to rule 12's `acceptance` non-list guard."""
    assert check_assumptions_register({"assumptions": {"text": "not a list"}}) == []
    assert check_assumptions_register({"assumptions": "not a list"}) == []


def test_assumptions_innocence_status_tolerates_whitespace_and_case():
    """INNOCENCE: `status` is compared stripped and lower-cased — leading/
    trailing whitespace and any case of `VERIFIED` still reads as
    verified."""
    brief = {"assumptions": [{"text": "the token rotates weekly", "status": "  VERIFIED  "}]}
    assert check_assumptions_register(brief) == []


def test_assumptions_innocence_unverified_with_probe_fires_n1_not_n3():
    """INNOCENCE: an `unverified` entry that DOES declare a usable `probe:`
    still fires N1 (it is unverified) but N3 (unsettleable) stays silent
    — the probe names the check that would settle it."""
    brief = {
        "assumptions": [
            {"text": "the outbox drains within 5 minutes", "status": "unverified",
             "probe": "pytest -k test_outbox_drain_latency"},
        ],
    }
    notices = check_assumptions_register(brief)
    assert any("still 'unverified'" in n for n in notices)
    assert not any("declare no 'probe:'" in n for n in notices)


def test_assumptions_innocence_examples_sanitize_quotes_and_newlines():
    """INNOCENCE: an assumption's `text` arrives from prose that may
    legitimately carry a newline and a double quote (the same YAML
    block-scalar reality rule 12 already guards against) — reusing
    `_acceptance_examples()` must keep every notice on one stderr line."""
    notices = check_assumptions_register(
        {"assumptions": [{"text": 'he said "go"\nsecond line', "status": "unverified"}]}
    )
    assert notices
    for n in notices:
        assert "\n" not in n


def test_assumptions_innocence_control_bytes_never_reach_a_notice():
    """Blind adversarial review 2026-08-29 (Kimi K3, finding 1), verified
    on disk before it was accepted: `_acceptance_examples` collapsed
    whitespace and swapped double quotes, but ESC/BEL/NUL are not
    whitespace (`"\x1b".isspace()` is False), so a control byte in an
    assumption's text travelled verbatim into a stderr-bound notice while
    the helper's own docstring said "Every item is SANITIZED first". The
    over-claim was the defect; the code now matches the claim. This guard
    covers rule 12 as well, since both rules share the helper."""
    notices = check_assumptions_register(
        {"assumptions": [
            {"text": "settle \x1b[31mRED\x1b[0m later \x07\x00",
             "status": "unverified"},
        ]}
    )
    assert notices
    for n in notices:
        assert "\x1b" not in n and "\x07" not in n and "\x00" not in n


def test_assumptions_guilt_whitespace_only_probe_is_not_a_probe():
    """Found by MUTATION, not by reading: making `probe_ok` accept any
    string (dropping the `.strip()` truthiness test) left every test
    green, so `probe: "   "` counted as a settlement path. That is
    precisely the boilerplate degeneration N3 exists to surface — a
    declared field carrying nothing."""
    notices = check_assumptions_register(
        {"assumptions": [
            {"text": "the lease renews", "status": "unverified", "probe": "   "},
        ]}
    )
    assert any("declare no 'probe:'" in n for n in notices)


def test_assumptions_guilt_bare_string_entry_names_itself():
    """Also found by MUTATION: collapsing a non-mapping entry's text to
    "" survived the first corpus, and would have rendered a bare-string
    assumption as "<non-text bullet>" in N2 — the one notice whose whole
    job is naming the offending entry. For a bare string, the string IS
    the text."""
    notices = check_assumptions_register(
        {"assumptions": ["the queue is drained by the nightly cron"]}
    )
    assert any("the queue is drained by the nightly cron" in n for n in notices)


def test_assumptions_end_to_end_notice_reaches_stderr(tmp_repo, capsys):
    """End-to-end (same 'wiring, not just return value' pattern as
    test_acceptance_probe_end_to_end_notice_reaches_stderr): rule 13 is
    NOTICE-only and NOT gear-gated — lint() must return rc == 0 on a pack
    whose brief carries one unverified assumption, and the operator must
    still see the "assumptions" text on stderr."""
    tmp_path, write_brief, write_pack = tmp_repo
    write_brief(gear=1, assumptions=[
        {"text": "the mirror is idempotent", "status": "unverified"},
    ])
    write_pack()
    rc, viol = lint(tmp_path / "evidence" / "pack.yml", tmp_path, None)
    assert rc == 0
    assert viol == []
    captured = capsys.readouterr()
    assert "assumptions:" in captured.err
    assert "NOTICE" in captured.err


# --------------------------------------------------------- check_appetite_acknowledgment


def test_appetite_guilt_over_wall_clock_hours_no_ack_violation():
    """GUILT: a single declared ceiling (wall_clock_hours), observed spend
    strictly over it, and no `appetite_exceeded:` — the ONLY rule in this
    lane that fails."""
    brief = {"appetite": {"wall_clock_hours": 4}}
    pack = {"spend": {"wall_clock_hours": 11}}
    violations, notices = check_appetite_acknowledgment(brief, pack)
    assert violations
    assert notices == []
    assert "appetite_exceeded" in violations[0]


def test_appetite_guilt_over_adversarial_rounds_names_both_numbers():
    """GUILT: the violation message names BOTH the declared ceiling and the
    observed value for the breached dimension, so the reader can act."""
    brief = {"appetite": {"adversarial_rounds": 2}}
    pack = {"spend": {"adversarial_rounds": 5}}
    violations, _notices = check_appetite_acknowledgment(brief, pack)
    assert violations
    assert "adversarial_rounds" in violations[0]
    assert "declared 2" in violations[0]
    assert "observed 5" in violations[0]


def test_appetite_guilt_over_two_dimensions_names_both():
    """GUILT: two breached dimensions in one pack — the message names
    both, not just the first one found."""
    brief = {"appetite": {"wall_clock_hours": 4, "adversarial_rounds": 2}}
    pack = {"spend": {"wall_clock_hours": 11, "adversarial_rounds": 5}}
    violations, _notices = check_appetite_acknowledgment(brief, pack)
    assert len(violations) == 1
    assert "wall_clock_hours" in violations[0]
    assert "adversarial_rounds" in violations[0]


def test_appetite_guilt_whitespace_only_ack_is_not_an_acknowledgment():
    """GUILT: `appetite_exceeded: "   "` is whitespace-only — mirrors
    `gear_override`'s `.strip()` truthiness discipline exactly; a blank
    string must not launder a real overrun into silence."""
    brief = {"appetite": {"wall_clock_hours": 4}}
    pack = {"spend": {"wall_clock_hours": 11}, "appetite_exceeded": "   "}
    violations, _notices = check_appetite_acknowledgment(brief, pack)
    assert violations


def test_appetite_guilt_non_str_ack_is_not_an_acknowledgment():
    """GUILT: `appetite_exceeded: 42` (non-str) is not an acknowledgment —
    only a genuine `str` can carry a reason."""
    brief = {"appetite": {"wall_clock_hours": 4}}
    pack = {"spend": {"wall_clock_hours": 11}, "appetite_exceeded": 42}
    violations, _notices = check_appetite_acknowledgment(brief, pack)
    assert violations


def test_appetite_innocence_acknowledged_overrun_reports_not_fails():
    """INNOCENCE: the SAME overrun as the first guilt test, but WITH a
    real, non-empty `appetite_exceeded:` — 0 violations, 1 notice, mirrors
    `gear_override`'s "reported, not failed" posture."""
    brief = {"appetite": {"wall_clock_hours": 4}}
    pack = {
        "spend": {"wall_clock_hours": 11},
        "appetite_exceeded": "hotfix under active incident, verified live",
    }
    violations, notices = check_appetite_acknowledgment(brief, pack)
    assert violations == []
    assert len(notices) == 1
    assert "acknowledged" in notices[0]
    assert "hotfix under active incident, verified live" in notices[0]


def test_appetite_innocence_absent_block_silent():
    """INNOCENCE: no `appetite:` key at all in the brief — SILENT,
    `([], [])`."""
    assert check_appetite_acknowledgment({"gear": 1}, {}) == ([], [])


def test_appetite_innocence_real_corpus_string_shape_silent():
    """INNOCENCE, the CRITICAL case: on disk right now (measured
    2026-08-29) `appetite:` appears in 1 of 53 briefs and its value is
    this exact free-text STRING, not a mapping —
    evidence/2026-08/agent-nuzantara-docs-craft-wave-specs-8455f4c0/
    brief.yml. A string declares no machine-readable ceiling and has
    nothing to exceed, so it must ALSO stay silent, or this rule would
    crash or falsely convict on the only real instance in the corpus."""
    brief = {"appetite": 'one session; two adversarial rounds (Kimi, then Codex on the fixes); no third round — leftover objections become spec caveats, not rewrites.'}
    assert check_appetite_acknowledgment(brief, {}) == ([], [])


def test_appetite_innocence_spend_absent_unmeasured_notice():
    """INNOCENCE: a ceiling IS declared but the pack records no `spend:`
    at all — 0 violations, 1 "not verified this run" notice. An
    unmeasured ceiling is not a breached one."""
    brief = {"appetite": {"wall_clock_hours": 4}}
    violations, notices = check_appetite_acknowledgment(brief, {})
    assert violations == []
    assert len(notices) == 1
    assert "not verified this run" in notices[0]


def test_appetite_innocence_spend_equal_to_ceiling_not_a_breach():
    """INNOCENCE: comparison is `observed > declared` — spend EQUAL to the
    ceiling is not a breach, SILENT."""
    brief = {"appetite": {"wall_clock_hours": 4}}
    pack = {"spend": {"wall_clock_hours": 4}}
    assert check_appetite_acknowledgment(brief, pack) == ([], [])


def test_appetite_innocence_spend_under_ceiling_silent():
    """INNOCENCE: spend strictly under the declared ceiling is SILENT."""
    brief = {"appetite": {"wall_clock_hours": 4}}
    pack = {"spend": {"wall_clock_hours": 1}}
    assert check_appetite_acknowledgment(brief, pack) == ([], [])


def test_appetite_innocence_empty_mapping_silent():
    """INNOCENCE: `appetite: {}` declares no recognised numeric ceiling at
    all — SILENT, same as absence."""
    assert check_appetite_acknowledgment({"appetite": {}}, {}) == ([], [])


def test_appetite_innocence_bool_ceiling_not_numeric():
    """INNOCENCE: `appetite: {wall_clock_hours: true}` — a bool is not a
    numeric ceiling (`type(True) is int` is False, `type(True) is bool`).
    `type(v) is int or type(v) is float` rejects it without needing a
    separate `isinstance(v, bool)` guard."""
    brief = {"appetite": {"wall_clock_hours": True}}
    pack = {"spend": {"wall_clock_hours": 99}}
    assert check_appetite_acknowledgment(brief, pack) == ([], [])


def test_appetite_innocence_brief_none_pack_none_does_not_crash():
    """INNOCENCE: `brief=None` and `pack=None` simultaneously must not
    raise — this rule can FAIL a pack, but it must never crash a run."""
    assert check_appetite_acknowledgment(None, None) == ([], [])


def test_appetite_innocence_non_mapping_spend_does_not_crash():
    """INNOCENCE: `spend:` shaped as a str, a list, or an int must not
    crash — each is treated exactly like `spend:` absent, so it produces
    the same "not verified this run" notice, never a violation."""
    brief = {"appetite": {"wall_clock_hours": 4}}
    for bad_spend in ("eleven hours", [1, 2, 3], 11):
        violations, notices = check_appetite_acknowledgment(
            brief, {"spend": bad_spend}
        )
        assert violations == []
        assert len(notices) == 1
        assert "not verified this run" in notices[0]


def test_appetite_end_to_end_violation_reaches_lint_and_rc1(tmp_repo):
    """End-to-end (same 'wiring, not just return value' pattern as
    test_assumptions_end_to_end_notice_reaches_stderr): this is the ONE
    rule in the lane that can fail, so the end-to-end proof is that a
    genuine breach with no acknowledgment reaches lint()'s RETURNED
    violations list and flips the exit code to 1 — not just a stderr
    notice."""
    tmp_path, write_brief, write_pack = tmp_repo
    write_brief(gear=1, appetite={"wall_clock_hours": 4})
    write_pack(spend={"wall_clock_hours": 11})
    rc, violations = lint(tmp_path / "evidence" / "pack.yml", tmp_path, None)
    assert rc == 1
    assert any("appetite" in v and "appetite_exceeded" in v for v in violations)



# ---------------------------------------------------------------------------
# Rule 14 — defects found by the ORCHESTRATOR's on-disk gate (not by the
# implementer, not by the refuter). Each test carries the measurement that
# found it, so the next reader knows why the case exists rather than
# guessing it was written for symmetry.
# ---------------------------------------------------------------------------


def test_appetite_guilt_acknowledgment_reason_is_sanitized_before_stderr():
    """MEASURED on this branch before the fix: an `appetite_exceeded:` reason
    containing a newline produced a notice that SPLIT ACROSS TWO stderr lines,
    and an ESC/BEL travelled to the terminal verbatim.

    That is the identical defect blind adversarial review found in rule 13 one
    PR earlier (Kimi K3, finding 1) — the sanitiser existed, and rule 14 simply
    did not call it. The cure was to extract it into a shared, named
    `_sanitize_notice_text`: a sanitiser that lives inside one rule's formatter
    is a sanitiser the next rule forgets."""
    violations, notices = check_appetite_acknowledgment(
        {"appetite": {"wall_clock_hours": 4}},
        {
            "spend": {"wall_clock_hours": 11},
            "appetite_exceeded": "line1\nline2\x1b[31mRED\x07 tail",
        },
    )
    assert violations == []
    assert len(notices) == 1
    assert "\n" not in notices[0]
    assert all(ch.isprintable() or ch == " " for ch in notices[0])


def test_appetite_guilt_control_bytes_only_reason_is_not_an_acknowledgment():
    """Emptiness is judged AFTER sanitising. Judged before, three invisible
    bytes would acknowledge any overrun and buy a silent pass — the exact
    shape of a bypass, on the lane's only failing rule."""
    violations, notices = check_appetite_acknowledgment(
        {"appetite": {"wall_clock_hours": 4}},
        {"spend": {"wall_clock_hours": 11}, "appetite_exceeded": "\x1b\x07"},
    )
    assert len(violations) == 1
    assert notices == []


def test_appetite_innocence_non_ascii_reason_survives_sanitizing():
    """The sanitiser drops NON-PRINTABLES, not merely-non-ASCII text. Without
    this the over-match twin would be silent data loss: a reason written in
    Italian or Indonesian arriving at the reader mangled."""
    violations, notices = check_appetite_acknowledgment(
        {"appetite": {"tokens": 10}},
        {"spend": {"tokens": 99}, "appetite_exceeded": "café naïve — sforato"},
    )
    assert violations == []
    assert "café naïve — sforato" in notices[0]


def test_appetite_innocence_over_long_reason_is_capped():
    """A reason is prose, so it is capped generously (200) rather than at the
    60 an acceptance bullet gets — but it IS capped: an unbounded field must
    not be able to emit an unbounded stderr line."""
    violations, notices = check_appetite_acknowledgment(
        {"appetite": {"tokens": 10}},
        {"spend": {"tokens": 99}, "appetite_exceeded": "x" * 400},
    )
    assert violations == []
    # The reason is rendered QUOTED, so the ellipsis sits inside the quotes.
    assert '..."' in notices[0]
    assert len(notices[0]) < 400


def test_appetite_partial_coverage_breach_and_unmeasured_coexist():
    """Flagged by the implementer as pinned by NO specified case, and correct:
    with three independent dimensions a pack can breach one while leaving
    another unmeasured in the same call. The spec's prose decides it — a
    declared ceiling with no matching spend contributes to the unmeasured
    notice, "never to a violation" — so the two facts are independent and BOTH
    must be reported. Untested, a later refactor could silently fold one into
    the other and no case would notice."""
    violations, notices = check_appetite_acknowledgment(
        {"appetite": {"wall_clock_hours": 4, "tokens": 100}},
        {"spend": {"wall_clock_hours": 11}},
    )
    assert len(violations) == 1
    assert "wall_clock_hours" in violations[0]
    assert "tokens" not in violations[0]
    assert len(notices) == 1
    assert "tokens" in notices[0]
    assert "not verified this run" in notices[0]


def test_appetite_nan_and_inf_spend_are_UNMEASURED_not_silent():
    """THIS TEST WAS WRONG WHEN FIRST WRITTEN, AND THAT IS WHY IT IS HERE.

    The orchestrator's gate found NaN, checked that it "never convicts", and
    pinned `([], [])` — total silence — as correct, reasoning that fail-open on
    the lane's only convicting rule is the safe direction. Half right. Fail-open
    on the VIOLATION is safe; fail-open on the NOTICE is a BYPASS: `type(nan) is
    float` admitted NaN as a MEASUREMENT, so it never entered `unmeasured`, and
    a pack could report any overrun as `spend: {tokens: .nan}` and the rule
    would say nothing at all. It also contradicted the rule's own docstring,
    which promises a notice for a dimension with "no comparable numeric value".

    Caught pre-merge by blind cross-family review (Kimi K3, finding F4), which
    is the whole argument for generator != grader: the author had already
    examined this exact input and pinned the wrong half of it.

    NaN is not a measurement, it is the ABSENCE of one — so it must produce the
    unmeasured NOTICE, and still never convict."""
    for bad in (float("nan"), float("inf"), float("-inf"), -5):
        violations, notices = check_appetite_acknowledgment(
            {"appetite": {"tokens": 1000}}, {"spend": {"tokens": bad}}
        )
        assert violations == [], f"{bad!r} must never convict"
        assert len(notices) == 1, f"{bad!r} must be reported as unmeasured, not silent"
        assert "not verified this run" in notices[0]


def test_appetite_innocence_nonsense_ceiling_is_not_a_ceiling():
    """A negative or non-finite CEILING is a typo, not a declaration. Before
    the fix, `appetite: {adversarial_rounds: -1}` was admitted as genuine and
    an honest `spend: 0` convicted (`0 > -1`) — a false positive on the one
    rule whose false positive costs an unrelated squad its merge (Kimi K3,
    finding F3). Now it declares nothing, so there is nothing to exceed."""
    for bad in (-1, float("nan"), float("inf")):
        assert check_appetite_acknowledgment(
            {"appetite": {"adversarial_rounds": bad}},
            {"spend": {"adversarial_rounds": 0}},
        ) == ([], []), f"{bad!r} must not be a ceiling"


def test_appetite_innocence_zero_is_a_real_value_on_both_sides():
    """The over-correction twin of the two tests above (W94: curing an
    over-match births the under-match). The bound is `>= 0`, NOT `> 0` —
    `wall_clock_hours: 0` is a real, harsh declaration and a real observation,
    and a fix that excluded zero would silently disarm both."""
    assert check_appetite_acknowledgment(
        {"appetite": {"wall_clock_hours": 0}}, {"spend": {"wall_clock_hours": 0}}
    ) == ([], [])
    violations, _ = check_appetite_acknowledgment(
        {"appetite": {"wall_clock_hours": 0}}, {"spend": {"wall_clock_hours": 1}}
    )
    assert len(violations) == 1


def test_appetite_guilt_non_str_acknowledgment_message_does_not_lie():
    """`appetite_exceeded: yes` parses as the BOOL True under YAML 1.1. The
    conviction is CORRECT and unchanged — this field mirrors `gear_override`,
    where the reason IS the artifact, and accepting a bare `yes` would turn the
    lane's only failing rule into a one-token bypass. What was defective was
    the MESSAGE: it told the author there was "no `appetite_exceeded:`
    acknowledgment" when they had plainly written one, sending them to grep for
    a field sitting right there (Kimi K3, finding F1, ranked HIGH). The message
    now names the type."""
    import yaml

    pack = yaml.safe_load("spend: {tokens: 1500}\nappetite_exceeded: yes")
    assert pack["appetite_exceeded"] is True  # premise: YAML really does this
    violations, notices = check_appetite_acknowledgment(
        {"appetite": {"tokens": 1000}}, pack
    )
    assert len(violations) == 1
    assert "bool" in violations[0]
    assert "not a reason" in violations[0]
    assert "no `appetite_exceeded:` acknowledgment" not in violations[0]

    int_violations, _ = check_appetite_acknowledgment(
        {"appetite": {"tokens": 1000}}, {"spend": {"tokens": 1500}, "appetite_exceeded": 42}
    )
    assert len(int_violations) == 1
    assert "int" in int_violations[0]


def test_appetite_innocence_missing_acknowledgment_message_is_unchanged():
    """Innocence twin of the test above: the ORIGINAL message must still be
    what a genuinely-absent acknowledgment gets. A fix that routed every
    conviction through the new branch would make the common case read as if
    the author had written something."""
    violations, _ = check_appetite_acknowledgment(
        {"appetite": {"tokens": 1000}}, {"spend": {"tokens": 1500}}
    )
    assert len(violations) == 1
    assert "no `appetite_exceeded:` acknowledgment" in violations[0]
    assert "not a reason" not in violations[0]


# ------------------------- path-term exemption: first-party action pins (2026-09-01)
# Owner ruling "Cambio la regola adesso": a mechanical `uses:` version bump under
# .github/workflows/ floored at Gear 3 and demanded a full evidence pack. Measured
# that day, PRs #5442 / #5444 / #5445 were each a one-to-two-line pin whose ONLY red
# check was "Harness floor recompute".
#
# These tests carry BOTH directions on purpose. An exemption is a hole in a gate, so
# the guilt half is the load-bearing half: if every case here went green the suite
# would be indistinguishable from one that exempts unconditionally. The parametrized
# guilt corpus below is therefore the primary artifact, and the innocence cases exist
# to prove it is not simply refusing everything.

_WF = ".github/workflows/ci.yml"


def _patch(body: str, path: str = _WF) -> str:
    """A minimal but REAL unified-diff envelope — headers included, because the
    `--- a/<path>` line is exactly the trap a naive `line.startswith("-")` parser
    falls into, and a fixture that omitted it would not exercise it."""
    return (
        f"diff --git a/{path} b/{path}\n"
        f"index 1111111..2222222 100644\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"{body}"
    )


_PIN_ONLY = _patch(
    "@@ -1 +1 @@\n"
    "-      - uses: actions/checkout@v4\n"
    "+      - uses: actions/checkout@v5\n"
)


@pytest.mark.parametrize(
    "why,patch,changed",
    [
        (
            "a permissions: change rides along in the same file",
            _patch(
                "@@ -1,2 +1,2 @@\n"
                "-      - uses: actions/checkout@v4\n"
                "+      - uses: actions/checkout@v5\n"
                "@@ -9 +9 @@\n"
                "-    permissions: read-all\n"
                "+    permissions: write-all\n"
            ),
            [_WF],
        ),
        (
            "the action is THIRD-party — the live supply-chain surface",
            _patch(
                "@@ -1 +1 @@\n"
                "-      - uses: snyk/actions/python@0.4.0\n"
                "+      - uses: snyk/actions/python@0.5.0\n"
            ),
            [_WF],
        ),
        (
            "the identity is SWAPPED, not the ref (typosquat)",
            _patch(
                "@@ -1 +1 @@\n"
                "-      - uses: actions/checkout@v4\n"
                "+      - uses: actions/chekcout@v4\n"
            ),
            [_WF],
        ),
        (
            "a new first-party step is ADDED",
            _patch(
                "@@ -1 +1,2 @@\n"
                "       - uses: actions/checkout@v4\n"
                "+      - uses: actions/setup-node@v4\n"
            ),
            [_WF],
        ),
        (
            "a step is REMOVED",
            _patch(
                "@@ -1,2 +1 @@\n"
                "       - uses: actions/checkout@v4\n"
                "-      - uses: actions/setup-node@v4\n"
            ),
            [_WF],
        ),
        (
            "the pin is clean but another hot-zone file rides in the same PR",
            _PIN_ONLY,
            [_WF, "fly.toml"],
        ),
        (
            "no content hunk at all (mode change) — not PROVEN safe",
            f"diff --git a/{_WF} b/{_WF}\nold mode 100644\nnew mode 100755\n",
            [_WF],
        ),
        (
            "a second workflow in the same PR disarms a gate",
            _PIN_ONLY
            + _patch(
                "@@ -3 +3 @@\n-  if: always()\n+  if: false\n",
                ".github/workflows/gate.yml",
            ),
            [_WF, ".github/workflows/gate.yml"],
        ),
        (
            "uses-only lines but the path is fly.toml — exemption must not leak",
            _patch(
                "@@ -1 +1 @@\n"
                "-      - uses: actions/checkout@v4\n"
                "+      - uses: actions/checkout@v5\n",
                "fly.toml",
            ),
            ["fly.toml"],
        ),
        (
            "uses-like lines under .github/CODEOWNERS — exemption must not leak",
            _patch(
                "@@ -1 +1 @@\n"
                "-      - uses: actions/checkout@v4\n"
                "+      - uses: actions/checkout@v5\n",
                ".github/CODEOWNERS",
            ),
            [".github/CODEOWNERS"],
        ),
    ],
)
def test_path_term_exemption_guilt_these_all_keep_gear_three(why, patch, changed):
    assert compute_floor(changed, None, patch) == 3, why
    assert compute_floor_source(changed, None, patch) == FLOOR_SOURCE_PATH, why


def test_path_term_exemption_innocence_pure_pin_drops_to_one():
    assert compute_floor([_WF], None, _PIN_ONLY) == 1
    assert compute_floor_source([_WF], None, _PIN_ONLY) == FLOOR_SOURCE_NONE


def test_path_term_exemption_innocence_sha_pin_with_trailing_version_comment():
    """PR #5444's exact shape: the ref is a SHA and the version lives in a
    trailing comment. A parser that stopped at the `#` would read the two sides
    as different identities and never exempt it."""
    patch = _patch(
        "@@ -1 +1 @@\n"
        "-        uses: github/codeql-action/autobuild@ff2f1c62 # v4.37.7\n"
        "+        uses: github/codeql-action/autobuild@cdf488f5 # v4.37.9\n"
    )
    assert compute_floor([_WF], None, patch) == 1


def test_path_term_exemption_innocence_two_pins_in_one_file():
    patch = _patch(
        "@@ -1 +1 @@\n"
        "-        uses: github/codeql-action/init@aaaaaaa # v4.37.7\n"
        "+        uses: github/codeql-action/init@bbbbbbb # v4.37.9\n"
        "@@ -8 +8 @@\n"
        "-        uses: actions/cache@v3\n"
        "+        uses: actions/cache@v4\n"
    )
    assert compute_floor([_WF], None, patch) == 1


def test_path_term_exemption_defaults_to_no_exemption_at_all():
    """FAIL-CLOSED: the exemption must be PROVEN by a patch. Every caller that
    omits one — and every run where the patch file was missing or unreadable —
    gets exactly the floor this function returned before the exemption existed."""
    assert compute_floor([_WF]) == 3
    assert compute_floor([_WF], None, None) == 3
    assert compute_floor([_WF], None, "") == 3


def test_path_term_exemption_never_returns_a_non_workflow_path():
    """The exemption set is structurally confined to .github/workflows/, so it
    can only ever narrow the path term for the one directory it was written for
    — no future edit to the parser can widen it without failing here."""
    patch = (
        _PIN_ONLY
        + _patch(
            "@@ -1 +1 @@\n"
            "-      - uses: actions/checkout@v4\n"
            "+      - uses: actions/checkout@v5\n",
            "fly.toml",
        )
        + _patch(
            "@@ -1 +1 @@\n"
            "-      - uses: actions/checkout@v4\n"
            "+      - uses: actions/checkout@v5\n",
            "scripts/dlq_autopilot.py",
        )
    )
    exempt = workflow_paths_exempt_from_path_term(patch)
    assert exempt == {_WF}
    assert all(p.startswith(".github/workflows/") for p in exempt)


def test_path_term_exemption_a_path_only_the_patch_claims_exempts_nothing():
    """STRUCTURAL defence, stated as a test because it is the one that holds
    when every other condition is satisfied: the exemption set is INTERSECTED
    against the real changed-file list. A patch can therefore claim whatever
    path it likes — the floor is still computed over the files git says
    changed, and a name that appears only in the patch matches nothing."""
    lying_patch = _patch(
        "@@ -1 +1 @@\n"
        "-      - uses: actions/checkout@v4\n"
        "+      - uses: actions/checkout@v5\n",
        ".github/workflows/not-actually-in-this-pr.yml",
    )
    assert compute_floor(["fly.toml"], None, lying_patch) == 3
    assert compute_floor(["apps/backend-rag/backend/app/auth/jwt.py"], None, lying_patch) == 3


def test_path_term_exemption_rejects_a_traversal_path():
    """`.github/workflows/../../fly.toml` passes a naive startswith() and names
    another hot zone. Refused at the parser, not only by the intersection."""
    patch = _patch(
        "@@ -1 +1 @@\n"
        "-      - uses: actions/checkout@v4\n"
        "+      - uses: actions/checkout@v5\n",
        ".github/workflows/../../fly.toml",
    )
    assert workflow_paths_exempt_from_path_term(patch) == set()


def test_path_term_exemption_rejects_a_non_ascii_homoglyph_owner():
    """A Cyrillic 'а' in `аctions/checkout` is a different owner to GitHub and
    to this parser. It must not be read as first-party."""
    patch = _patch(
        "@@ -1 +1 @@\n"
        "-      - uses: аctions/checkout@v4\n"
        "+      - uses: аctions/checkout@v5\n"
    )
    assert compute_floor([_WF], None, patch) == 3


def test_path_term_exemption_rejects_a_combined_diff():
    """A merge-commit `diff --cc` puts TWO status columns on each line, so the
    body of a `++`/`--` line still carries a leading +/-. CI never produces one
    (the producer runs a two-endpoint `git diff`), but a future caller might."""
    patch = (
        ".github/workflows/ci.yml\n"
        "diff --cc .github/workflows/ci.yml\n"
        "index 111,222..333\n"
        "--- a/.github/workflows/ci.yml\n"
        "+++ b/.github/workflows/ci.yml\n"
        "@@@ -1,1 -1,1 +1,1 @@@\n"
        "- -      - uses: actions/checkout@v4\n"
        "++      - uses: actions/checkout@v5\n"
    )
    assert compute_floor([_WF], None, patch) == 3


def test_path_term_exemption_guilt_reordering_two_bare_steps_keeps_gear_three():
    """Found by a cross-family refuter (deepseek-v4-flash-0731) whose answer was
    truncated at 214 bytes and still contained it. Two bare one-line steps whose
    `uses:` lines swap places have an IDENTICAL multiset of action identities, so
    the first cut of condition 3 — `sorted(minus) != sorted(plus)` — exempted a
    reorder. Reordering steps is a semantic change: it can put a scan before the
    step that produces what it scans, which passes vacuously. Condition 3 now
    compares the SEQUENCES, both of which are in file order."""
    reorder = _patch(
        "@@ -1,2 +1,2 @@\n"
        "-      - uses: actions/checkout@v4\n"
        "-      - uses: actions/setup-node@v4\n"
        "+      - uses: actions/setup-node@v4\n"
        "+      - uses: actions/checkout@v4\n"
    )
    assert compute_floor([_WF], None, reorder) == 3
    assert workflow_paths_exempt_from_path_term(reorder) == set()


def test_path_term_exemption_innocence_two_pins_keep_their_order():
    """The control for the test above: the same two actions, both bumped, order
    unchanged. If sequence-equality were over-tight this would go red too, and a
    guilt test whose innocence twin also fails proves nothing."""
    both_bumped = _patch(
        "@@ -1,2 +1,2 @@\n"
        "-      - uses: actions/checkout@v4\n"
        "-      - uses: actions/setup-node@v4\n"
        "+      - uses: actions/checkout@v5\n"
        "+      - uses: actions/setup-node@v5\n"
    )
    assert compute_floor([_WF], None, both_bumped) == 1


def test_path_term_exemption_guilt_two_full_steps_swap_when_their_with_blocks_align():
    """The shape a peer session named as adjacent to the reorder hole, and the
    reason this fixture is a REAL git-produced diff rather than a hand-written
    one: when two steps carry IDENTICAL `with:` blocks, git aligns those blocks
    as context and the minimal diff it emits changes ONLY the two `uses:` lines.
    So "the surrounding block moved too, therefore a non-uses line changed" is
    NOT a defence — git can hide the move entirely. Verified by initialising a
    scratch repo, swapping the two steps and capturing `git diff -U0` (2026-09-01);
    the bytes below are that command's actual output.

    Sequence equality is what refuses it — the identities appear in opposite
    order on the two sides. Under the superseded sorted() comparison this would
    have been EXEMPTED."""
    real_git_diff = (
        "diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml\n"
        "index 731c10d..8cd8c2c 100644\n"
        "--- a/.github/workflows/ci.yml\n"
        "+++ b/.github/workflows/ci.yml\n"
        "@@ -4 +4 @@ jobs:\n"
        "-      - uses: actions/upload-artifact@v4\n"
        "+      - uses: actions/download-artifact@v4\n"
        "@@ -7 +7 @@ jobs:\n"
        "-      - uses: actions/download-artifact@v4\n"
        "+      - uses: actions/upload-artifact@v4\n"
    )
    assert workflow_paths_exempt_from_path_term(real_git_diff) == set()
    assert compute_floor([_WF], None, real_git_diff) == 3
