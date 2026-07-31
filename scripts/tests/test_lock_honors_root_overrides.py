#!/usr/bin/env python3
"""The lock must actually satisfy the root `overrides` security floors.

THE DEFECT, measured on origin/main 2026-07-31. The root package.json carries a
block of 26 `overrides` — 24 of them `>=` SECURITY FLOORS, the repo's declared
mechanism for forcing a patched version onto a transitive dependency nobody
declares directly. Two of them were being violated by the lock in force:

    overrides.postcss = ">=8.5.10"   lock had 8.4.31 at packages/core/node_modules/postcss
    overrides.sharp   = ">=0.35.3"   lock had 0.34.5 at packages/core/node_modules/sharp

Those two entries were 4 of the 5 open Dependabot alerts (postcss HIGH x2 +
MEDIUM, sharp HIGH). The floor had been written down and was simply not in
force.

WHY NOTHING CAUGHT IT — the gap is precise, and it is a gap between two guards
that each look correct:

  * `npm ci --dry-run` (what the `npm lock honors manifest` required check runs,
    .github/workflows/npm-lock-sync.yml) validates lock<->manifest DEPENDENCY
    sync. It is blind to `overrides`. Run against pristine main, with both
    violations present, it returns **rc=0**.
  * `test_root_manifest_does_not_contradict_itself.py` checks the manifest
    against ITSELF — overrides vs resolutions vs app manifests. Its own
    docstring names the limit: "a pin that disagrees ... installs fine as long
    as nobody regenerates the lock. Documentation cannot fail a build."

So one guard reads the lock without the overrides and the other reads the
overrides without the lock. This file is the missing edge: overrides vs lock.

HOW THE VIOLATION IS BORN (worth knowing, because the shape recurs): a
workspace pinned `next` to an exact `16.2.11` while the root hoisted `^16.2.12`,
so npm materialised a NESTED `next@16.2.11` subtree — and that subtree carries
its own postcss/sharp, below the floor. An override is applied at resolution
time; it does not retroactively rewrite a subtree the lock already records.
Neither `npm install --package-lock-only` nor `npm dedupe` prunes such a subtree
once nothing declares it.

Run: python3 scripts/tests/test_lock_honors_root_overrides.py
     (also collected by pytest)
"""

from __future__ import annotations

import json
import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ROOT_MANIFEST = REPO_ROOT / "package.json"
ROOT_LOCK = REPO_ROOT / "package-lock.json"

# Spec forms this comparator understands. An override written in any OTHER form
# is a HARD FAILURE, never a silent pass: a spec we cannot parse is a floor we
# cannot verify, and "unverifiable" must not read as "satisfied" (that is how a
# guard turns decorative). Adding a form here is deliberate work.
_SUPPORTED = (">=", "^", "~")

_NUM = re.compile(r"^(\d+)\.(\d+)\.(\d+)")


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _triple(version: str) -> tuple[int, int, int] | None:
    """major.minor.patch, or None if this is not a plain release version.

    DECLARED LIMIT: prereleases (`1.0.0-rc.1`) and non-numeric specifiers
    (`npm:alias@x`, git URLs, `*`, `latest`) return None and are reported as
    unverifiable rather than compared — semver prerelease ordering is not
    something to approximate inside a security gate.
    """
    m = _NUM.match(version.strip().lstrip("v"))
    if not m or "-" in version.split("+")[0]:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _satisfies(version: str, spec: str) -> bool | None:
    """True/False, or None when either side is not plainly comparable."""
    v = _triple(version)
    if v is None:
        return None
    spec = spec.strip()
    if spec.startswith(">="):
        s = _triple(spec[2:])
        return None if s is None else v >= s
    if spec.startswith("^"):
        s = _triple(spec[1:])
        if s is None:
            return None
        # ^0.x.y is caret-on-zero: minor is the compatibility boundary.
        if s[0] == 0:
            return v >= s and v[0] == 0 and v[1] == s[1]
        return v >= s and v[0] == s[0]
    if spec.startswith("~"):
        s = _triple(spec[1:])
        return None if s is None else (v >= s and v[:2] == s[:2])
    s = _triple(spec)  # bare exact pin
    return None if s is None else v == s


def _overrides() -> dict[str, str]:
    return {
        name: spec
        for name, spec in (_load(ROOT_MANIFEST).get("overrides") or {}).items()
        if isinstance(spec, str)
    }


def _lock_entries() -> dict[str, str]:
    """{lock path: version} for every resolved package entry that has one.

    Workspace links and bare directory entries carry no version and are skipped
    — they are not installs of a third-party package.
    """
    packages = _load(ROOT_LOCK).get("packages") or {}
    return {
        path: entry["version"]
        for path, entry in packages.items()
        if path and isinstance(entry.get("version"), str)
    }


def _violations(
    overrides: dict[str, str], entries: dict[str, str]
) -> tuple[list[str], list[str]]:
    """(violations, unverifiable) — both as human-readable lines."""
    bad: list[str] = []
    unknown: list[str] = []
    for name, spec in overrides.items():
        if not spec.startswith(_SUPPORTED) and _triple(spec) is None:
            unknown.append(f"overrides[{name!r}] = {spec!r} — unsupported spec form")
            continue
        suffix = "node_modules/" + name
        for path, version in entries.items():
            if not path.endswith(suffix):
                continue
            verdict = _satisfies(version, spec)
            if verdict is None:
                unknown.append(f"{name} {version!r} vs {spec!r} at {path}")
            elif not verdict:
                bad.append(f"{name} {version} at {path} — floor is {spec}")
    return bad, unknown


def test_the_scan_can_see_the_manifest_and_the_lock_at_all() -> None:
    """Non-vacuity, and it is load-bearing here: every assertion below is over a
    set, and an empty set passes all of them while proving nothing. A repo with
    a broken glob reads EXACTLY like a repo with a clean lock. Anchor both ends
    against numbers this monorepo has actually had."""
    overrides = _overrides()
    assert len(overrides) >= 10, (
        f"only {len(overrides)} root overrides parsed — this monorepo has "
        "carried ~26 for months, so the manifest read is broken and every "
        "check below is vacuous"
    )
    entries = _lock_entries()
    assert len(entries) >= 1000, (
        f"only {len(entries)} versioned lock entries parsed — the root lock has "
        "tens of thousands, so the lock read is broken and a violation would be "
        "invisible rather than absent"
    )
    assert any(p.endswith("node_modules/postcss") for p in entries), (
        "no postcss entry found in the lock at all — postcss is one of the two "
        "packages this guard was written for; its absence means the path "
        "matching is wrong, not that the tree is clean"
    )


def test_every_override_spec_is_one_this_guard_can_verify() -> None:
    """An override written in a form the comparator does not understand is a
    security floor nobody is checking. Fail loudly and add the form on purpose,
    rather than letting it pass as 'no violation found'."""
    overrides = _overrides()
    unsupported = {
        name: spec
        for name, spec in overrides.items()
        if not spec.startswith(_SUPPORTED) and _triple(spec) is None
    }
    assert not unsupported, (
        f"root overrides use spec forms this guard cannot verify: {unsupported}. "
        "Teach _satisfies() the form — do NOT relax the check, because an "
        "unparseable floor currently reads as a satisfied one."
    )


def test_the_lock_satisfies_every_root_override() -> None:
    """THE DEFECT. A `>=` floor in `overrides` is a security decision; a lock
    entry below it means the decision is documentation, not configuration."""
    bad, unknown = _violations(_overrides(), _lock_entries())
    assert not bad, (
        "the lock installs versions BELOW the root override floors:\n  "
        + "\n  ".join(sorted(bad))
        + "\n\nAn override is applied at resolution time and does NOT rewrite a "
        "subtree the lock already records, so this does not self-heal. Find "
        "what pins the offending subtree (usually an exact version in a "
        "workspace manifest that forces a nested copy), fix that, then remove "
        "the orphaned entries — `npm install --package-lock-only` and "
        "`npm dedupe` both leave them behind. Prefer a scoped prune over a full "
        "lock regeneration: measured 2026-07-31, regenerating moved 1687 "
        "packages in / 1841 out and changed 57 versions, 18 of them prod-scope, "
        "including a google-auth-library DOWNGRADE."
    )
    assert not unknown, (
        "some override/lock pairs could not be compared, so their floors are "
        "unverified:\n  " + "\n  ".join(sorted(unknown))
    )


# --- the guard proves guilt AND innocence (required check) -------------------


def test_guilt_a_below_floor_entry_is_detected() -> None:
    """A synthetic lock carrying the exact 2026-07-31 defect must be caught."""
    overrides = {"postcss": ">=8.5.10", "sharp": ">=0.35.3"}
    entries = {
        "node_modules/postcss": "8.5.23",  # compliant, hoisted
        "packages/core/node_modules/postcss": "8.4.31",  # the real violation
        "node_modules/sharp": "0.35.3",
    }
    bad, unknown = _violations(overrides, entries)
    assert not unknown, unknown
    assert len(bad) == 1, f"expected exactly one violation, got {bad}"
    assert "8.4.31" in bad[0] and "packages/core" in bad[0], bad


def test_guilt_a_caret_and_a_tilde_floor_are_enforced_too() -> None:
    """The `>=` majority must not be the only form with teeth."""
    bad, _ = _violations(
        {"a": "^2.3.4", "b": "~1.2.3"},
        {"node_modules/a": "3.0.0", "node_modules/b": "1.3.0"},
    )
    assert len(bad) == 2, f"caret/tilde ceilings not enforced: {bad}"


def test_innocence_a_compliant_lock_is_not_flagged() -> None:
    """The neighbouring legitimate cases must stay silent: a version ABOVE the
    floor, a package the overrides do not mention, and a nested copy that
    complies. A guard that fires on these would be disarmed within a week."""
    bad, unknown = _violations(
        {"postcss": ">=8.5.10", "next": ">=16.2.11"},
        {
            "node_modules/postcss": "8.5.25",
            "packages/core/node_modules/postcss": "8.5.23",
            "node_modules/next": "16.2.12",
            "node_modules/js-yaml": "4.2.0",  # not overridden — not our business
        },
    )
    assert not bad, f"flagged a compliant lock: {bad}"
    assert not unknown, unknown


def test_innocence_a_package_whose_name_is_a_suffix_is_not_confused() -> None:
    """`node_modules/postcss` must not match `node_modules/postcss-selector-parser`,
    and `.../node_modules/sharp` must not match `.../node_modules/sharp-cli`."""
    bad, _ = _violations(
        {"postcss": ">=8.5.10", "sharp": ">=0.35.3"},
        {
            "node_modules/postcss-selector-parser": "1.0.0",
            "node_modules/sharp-cli": "0.1.0",
            "node_modules/@scope/postcss": "1.0.0",
        },
    )
    assert not bad, f"suffix collision produced a false positive: {bad}"


def test_an_unparseable_version_is_reported_not_silently_passed() -> None:
    """A prerelease is not compared, and that fact must SURFACE. Silence here is
    the failure mode that makes a gate decorative."""
    bad, unknown = _violations({"a": ">=1.2.3"}, {"node_modules/a": "1.2.4-rc.1"})
    assert not bad
    assert unknown and "1.2.4-rc.1" in unknown[0], unknown


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")
    print(f"\n{'FAILED' if failures else 'OK'} — {failures} failure(s)")
    raise SystemExit(1 if failures else 0)
