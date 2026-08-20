"""Tests for scripts/evidence_pack_lint.py (PR-3, fleet-order harness).

The script carries its own hermetic --selftest fixture (guilt+innocence over
every rule); this file makes pytest/CI run it AND pins each `check_*` guard's
verdict function directly, by name, for the guard-conformance registry
(superscar #3: "nessuna guardia mergiata senza un test di innocenza E di
colpevolezza" — each guard needs BOTH proofs registered).
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"

sys.path.insert(0, str(SCRIPTS))
from evidence_pack_lint import (  # noqa: E402
    check_brief_ref_exists,
    check_dissent_nonempty_on_gear3,
    check_gear_floor,
    check_pii_scan_clean,
    check_receipts_have_provenance,
    check_size_budget,
    compute_ceiling,
    compute_floor,
    effort_for_gear,
    lint,
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
