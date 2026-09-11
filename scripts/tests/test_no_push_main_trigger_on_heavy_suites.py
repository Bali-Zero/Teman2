#!/usr/bin/env python3
"""Regression guard for Merge-OS v3 build order step 2 (research/operations/
2026-08-14-merge-os-v3-research-council.md §6): `tests.yml` and `security.yml`
must never re-grow a `push: main` trigger, because the merge queue's
`merge_group` run already re-tests the exact commit a merge would produce —
running the same heavy suite again on the resulting push to `main` is the
"third payment" the council's build order names and orders removed.

THE DEFECT THIS EXISTS TO CATCH (it already happened once, in prose):

The removal itself shipped over two PRs, 2026-08-15/16 (#4210 dropped
`tests.yml`'s entire `push:` block; #4218 narrowed `security.yml`'s
`on.push.branches` from `[main, develop]` to `[develop]`), gated on each
workflow's own schedule producing a first green run first, so there was
never a window with no confirmed backstop. But the comments narrating that
plan (in both files' `on:` blocks) were never updated afterward: they kept
describing the removal as a *future* "prerequisite for a later PR", and
`.claude/skills/modus/PENDING-ARMS.md` carried a matching stale row making
the same claim. Nothing was structurally wrong — the trigger really was
gone — but a comment that outlives the state it describes reads as a
standing TODO to the next reader (cicatrix-superscar.md #9 / W106: "a cure
anchored to a frozen measurement of the world"), which is exactly what
produced a second Zero GO order asking a session to redo a step that had
already landed 11-12 days earlier. This test cannot catch a stale COMMENT
(prose isn't machine-checkable), but it makes the one fact the comment used
to get wrong durably self-verifying: the trigger set itself.

Every assertion below checks the SPECIFIC content the removal was gated on
(the exact cron string, not merely "a schedule exists"), and treats
`branches:` as the possibly-scalar-or-missing YAML value it can legally be
(never a bare substring check on a string — cicatrix-superscar.md #3,
"guard-over-match": `"main" in "maintenance"` is `True`, and this test must
not repeat that class of bug while guarding against a different one).

YAML 1.1 gotcha: a bare `on:` key parses as the boolean `True` under
PyYAML's `safe_load`, not the string "on" — handled defensively below for
both spellings, since a formatter or a future author quoting `"on":` would
otherwise make this test's OWN lookup the thing that breaks, silently
passing (a raised `KeyError` would fail loudly, but only in `main()`'s
try/except, not for a bare module-level access).

Run:  python3 scripts/tests/test_no_push_main_trigger_on_heavy_suites.py
      pytest scripts/tests/test_no_push_main_trigger_on_heavy_suites.py -q
"""

from __future__ import annotations

import pathlib
import sys

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
TESTS_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tests.yml"
SECURITY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "security.yml"

# The two crons the push:main removals were gated on producing a first green
# run for, verbatim from each file today. Asserting the STRING, not merely
# "a schedule key exists", so a future edit that empties/narrows the
# schedule to something that no longer covers the backstop is caught.
TESTS_SCHEDULE_CRON = "17 */2 * * *"
SECURITY_DAILY_BACKSTOP_CRON = "17 19 * * *"


def _load_triggers(path: pathlib.Path) -> dict:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    # `on:` is parsed as the boolean key `True` by PyYAML's YAML-1.1 loader
    # when written bare (both files today) — but a quoted `"on":` parses as
    # the string "on" instead, so check both rather than assume one.
    if True in doc:
        triggers = doc[True]
    elif "on" in doc:
        triggers = doc["on"]
    else:
        raise AssertionError(
            f"{path.name}: found neither a bare `on:` key (parses as "
            f"boolean True) nor a quoted \"on\": key in the parsed YAML — "
            f"top-level keys were {list(doc.keys())!r}"
        )
    assert isinstance(triggers, dict), (
        f"{path.name}: expected the `on:` trigger block to parse as a "
        f"mapping of trigger name -> config, got {type(triggers)!r}"
    )
    return triggers


def _cron_strings(schedule_value) -> list[str]:
    """`schedule:` is a list of `{cron: "..."}` mappings — extract the cron
    strings, tolerating None/empty/malformed entries rather than crashing,
    so a broken schedule fails the assertion with a clear message instead
    of a raw TypeError."""
    if not isinstance(schedule_value, list):
        return []
    out = []
    for entry in schedule_value:
        if isinstance(entry, dict) and isinstance(entry.get("cron"), str):
            out.append(entry["cron"])
    return out


def _push_branches(triggers: dict) -> list[str]:
    """Normalize `on.push.branches` to a list of branch-name strings,
    regardless of which legal-but-different YAML shape produced it:
    `push:` bare (None), `push: {}` (no `branches:` key), or
    `branches: single-name` (YAML permits a bare scalar, not only a list).
    Never returns a raw string for the caller to run `in` against — that
    is exactly the "main" in "maintenance" substring trap this module's
    docstring names."""
    push = triggers.get("push")
    if not isinstance(push, dict):
        return []
    branches = push.get("branches", [])
    if isinstance(branches, str):
        return [branches]
    if isinstance(branches, list):
        return [b for b in branches if isinstance(b, str)]
    return []


def test_tests_yml_has_no_push_trigger_at_all():
    """tests.yml has carried NO `push:` trigger since #4210 (2026-08-15) —
    only `pull_request`, `merge_group`, `workflow_dispatch`, `schedule`. The
    2-hourly schedule + the required `merge_group` run are the backstop; a
    `push` trigger here would re-run the full heavy suite on every commit
    that lands on `main`, exactly the queue-then-re-test double payment the
    council's build order exists to remove.
    """
    triggers = _load_triggers(TESTS_WORKFLOW)
    assert "push" not in triggers, (
        "tests.yml has re-grown a `push:` trigger — this re-introduces the "
        "'third payment' (re-testing on main a commit the merge queue just "
        "tested) that Merge-OS v3 build order step 2 removed. If this is "
        "deliberate, it needs a fresh precondition check (ruleset audit + "
        "green scheduled runs) and an update to this test's expectations, "
        "not a silent revert."
    )
    for required in ("pull_request", "merge_group"):
        assert required in triggers, (
            f"tests.yml lost its `{required}` trigger — that (plus the "
            "schedule below) is what keeps main from landing on an "
            "untested commit now that push:main is gone."
        )
    crons = _cron_strings(triggers.get("schedule"))
    assert TESTS_SCHEDULE_CRON in crons, (
        f"tests.yml's schedule no longer carries the 2-hourly cron "
        f"({TESTS_SCHEDULE_CRON!r}, got {crons!r}) — that schedule is the "
        "post-merge proof-of-health backstop push:main used to provide; "
        "narrowing or removing it re-opens the exact window Merge-OS v3 "
        "build order step 2 closed."
    )


def test_security_yml_push_trigger_excludes_main():
    """security.yml keeps a `push:` trigger for `develop` (pre-merge-queue
    branch, no merge_group coverage there) but must never list `main` again
    — that half was removed in #4218 (2026-08-16), gated on the daily
    schedule (03:17 WITA) having produced a first green run.
    """
    triggers = _load_triggers(SECURITY_WORKFLOW)
    assert "push" in triggers, (
        "security.yml lost its `push` trigger entirely — `develop` pushes "
        "still need a security scan (no merge_group there)."
    )
    branches = _push_branches(triggers)
    assert "main" not in branches, (
        "security.yml's `push` trigger has re-grown `main` in its "
        f"`branches:` list ({branches!r}) — this re-introduces the 'third "
        "payment' that Merge-OS v3 build order step 2 removed. The daily "
        "schedule (03:17 WITA) is the confirmed backstop; re-adding this "
        "needs a fresh precondition check, not a silent revert."
    )
    assert "develop" in branches, (
        f"security.yml's `push` trigger lost `develop` ({branches!r}) — "
        "that branch has no merge_group coverage and needs its own push "
        "trigger."
    )
    crons = _cron_strings(triggers.get("schedule"))
    assert SECURITY_DAILY_BACKSTOP_CRON in crons, (
        f"security.yml's schedule no longer carries the daily backstop "
        f"cron ({SECURITY_DAILY_BACKSTOP_CRON!r}, got {crons!r}) — that is "
        "the confirmed backstop the push:main removal was gated on; "
        "losing it without also removing the push:main dedupe re-opens a "
        "window with no backstop."
    )


def main() -> int:
    failures = []
    for fn in (test_tests_yml_has_no_push_trigger_at_all, test_security_yml_push_trigger_excludes_main):
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001 - report any failure mode, not just AssertionError
            failures.append(fn.__name__)
            print(f"FAIL {fn.__name__}: {exc!r}")
    if failures:
        print(f"\n{len(failures)} failure(s): {', '.join(failures)}")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
