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
    check_brief_ref_exists,
    check_cheap_seat_floor,
    check_council_run_gear3,
    check_countable_claims,
    check_dissent_nonempty_on_gear3,
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
