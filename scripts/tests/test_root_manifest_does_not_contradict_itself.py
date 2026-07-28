#!/usr/bin/env python3
"""The root package.json must not silently contradict itself, or the apps.

TWO REAL DEFECTS, both measured on origin/main 2026-07-28, both of the same
shape: the manifest says one thing in two places and the reader can only see
one of them.

(1) THE REACT SPLIT. The root `overrides`/`resolutions` pinned react and
    react-dom to an exact `19.2.6`, while `apps/mouth/package.json` declared
    `19.2.8` — landed the same morning by the Dependabot minor-and-patch group
    (fc3141d0e5, #3388), which bumps app manifests and never looks at the root
    override block. main's lock happened to hoist 19.2.6 for everyone, so
    production ran a react its own manifest did not ask for, and nothing was
    red. The trap is what happens on the NEXT lock regeneration: a bare
    `npm uninstall <unrelated-dead-dep> --package-lock-only` re-resolved the
    workspace and moved `apps/mouth` (balizero.com and every subdomain) to a
    NESTED react 19.2.8 — measured: 0 nested react entries before, 8 after.
    So an ordinary dependency cleanup silently changes the production frontend's
    react, and the diff that does it is 981 lines of lock nobody reads.

    The exact pin is not the bug: react and react-dom are the only exact pins
    in a block of 24 `>=` security floors, and for a production frontend an
    exact version is the right shape (an override of `>=X` forces the newest
    satisfying version on every transitive consumer — for a framework that is
    worse, not better). The bug is that TWO places must move together and only
    one of them is on Dependabot's path.

(2) THE DUPLICATE KEY. `sharp` appeared TWICE in both `resolutions` and
    `overrides`: `^0.35.3` and `>=0.35.3`. JSON is last-wins, so `^0.35.3` was
    dead text and the effective constraint was `>=0.35.3` — verified by parsing
    main's own file both ways. Harmless by luck, not by design: the same
    duplication with the STRICTER value written second would silently discard
    a security floor, and `npm` rewrites the pair to a single key the first
    time any command touches the manifest, so the diff appears in an unrelated
    PR. A repo-wide sweep of all 18 package.json files found exactly one file
    with duplicate keys, so this is bounded, not endemic.

WHY A TEST AND NOT A NOTE: both defects are invisible to every existing gate.
A duplicate key parses fine; a pin that disagrees with an app manifest installs
fine as long as nobody regenerates the lock. Documentation cannot fail a build.

Run: python3 scripts/tests/test_root_manifest_does_not_contradict_itself.py
     (also collected by pytest)
"""

from __future__ import annotations

import collections
import json
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ROOT_MANIFEST = REPO_ROOT / "package.json"

# Packages the root block pins EXACTLY and that apps also declare directly.
# Only these are cross-checked: a `>=` floor is deliberately allowed to sit
# below an app's own newer version, which is the whole point of a floor.
CROSS_CHECKED = ("react", "react-dom")

PIN_SECTIONS = ("resolutions", "overrides")


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _duplicate_keys(path: pathlib.Path) -> dict[str, list]:
    """Return {json_pointer_ish_key: [values...]} for every repeated key."""
    dupes: dict[str, list] = {}

    def hook(pairs):
        counts = collections.Counter(k for k, _ in pairs)
        for key, n in counts.items():
            if n > 1:
                dupes[key] = [v for k, v in pairs if k == key]
        return dict(pairs)

    json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=hook)
    return dupes


def _app_manifests() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for base in ("apps", "packages"):
        root = REPO_ROOT / base
        if not root.is_dir():
            continue
        for p in root.glob("*/package.json"):
            if "node_modules" not in p.parts:
                out.append(p)
    return sorted(out)


def test_root_manifest_has_no_duplicate_keys() -> None:
    """DEFECT (2). A repeated key is a value silently discarded by last-wins."""
    dupes = _duplicate_keys(ROOT_MANIFEST)
    assert not dupes, (
        f"{ROOT_MANIFEST.name} repeats these keys, so the earlier value is dead "
        f"text that JSON silently drops: {dupes}. Keep one entry per key — and "
        "check WHICH value survives before deleting either: last-wins means the "
        "one written second is the one in force today."
    )


def test_the_scan_can_see_app_manifests_at_all() -> None:
    """Non-vacuity. Every assertion below is over a set; an empty set would pass
    all of them while proving nothing (a broken glob reads exactly like a clean
    repo). Anchor it: this monorepo has many app manifests and mouth is one."""
    manifests = _app_manifests()
    assert len(manifests) >= 5, (
        f"only {len(manifests)} app/package manifests found under apps/ and "
        "packages/ — the glob is broken, so the cross-check below is vacuous"
    )
    names = {p.parent.name for p in manifests}
    assert "mouth" in names, (
        "apps/mouth not among the discovered manifests — it is the production "
        f"frontend and the reason this guard exists. Found: {sorted(names)}"
    )


def test_the_two_pin_sections_agree_with_each_other() -> None:
    """resolutions and overrides are read by different tools (yarn vs npm). A
    repo that ships both must keep them identical for the packages it pins, or
    the installed version depends on which package manager ran."""
    root = _load(ROOT_MANIFEST)
    for pkg in CROSS_CHECKED:
        values = {sec: root.get(sec, {}).get(pkg) for sec in PIN_SECTIONS}
        present = {s: v for s, v in values.items() if v is not None}
        if len(present) < 2:
            continue  # pinned in one section only, or not at all — not a conflict
        assert len(set(present.values())) == 1, (
            f"{pkg} is pinned differently per section: {present}. npm reads "
            "`overrides`, yarn reads `resolutions` — divergent values mean the "
            "installed version depends on which tool ran."
        )


def test_exact_root_pins_agree_with_every_app_that_declares_them() -> None:
    """DEFECT (1). An exact root pin and an app's own exact declaration must be
    the same string, because Dependabot's group bumps touch the app manifest and
    never the root block. When they disagree, the lock decides — and the lock
    changes on any unrelated regeneration."""
    root = _load(ROOT_MANIFEST)
    problems: list[str] = []
    checked = 0

    for pkg in CROSS_CHECKED:
        pins = {
            sec: root.get(sec, {}).get(pkg)
            for sec in PIN_SECTIONS
            if root.get(sec, {}).get(pkg)
        }
        if not pins:
            continue
        # Only EXACT pins are cross-checked; a floor may legitimately sit below.
        exact = {v for v in pins.values() if v and v[0].isdigit()}
        if not exact:
            continue
        pinned = exact.pop() if len(exact) == 1 else None
        if pinned is None:
            continue  # the sibling test above already reports the disagreement

        for manifest in _app_manifests():
            data = _load(manifest)
            for field in ("dependencies", "devDependencies", "peerDependencies"):
                declared = data.get(field, {}).get(pkg)
                if not declared:
                    continue
                checked += 1
                # A range (^, ~, >=) is fine: it is not a competing exact claim.
                if not declared[0].isdigit():
                    continue
                if declared != pinned:
                    rel = manifest.relative_to(REPO_ROOT)
                    problems.append(
                        f"{rel} {field}.{pkg} = {declared!r} but the root "
                        f"{'/'.join(PIN_SECTIONS)} pin is {pinned!r}"
                    )

    assert checked > 0, (
        f"no app declares any of {CROSS_CHECKED} directly — either the packages "
        "moved or this guard is now vacuous. Re-anchor CROSS_CHECKED."
    )
    assert not problems, (
        "the root exact pin disagrees with an app's own exact declaration:\n  "
        + "\n  ".join(problems)
        + "\n\nBoth must move together. Dependabot bumps the app manifest and "
        "never the root block, so today's lock silently decides which one wins "
        "and the next lock regeneration can flip it — measured on 2026-07-28: "
        "an unrelated `npm uninstall --package-lock-only` moved apps/mouth from "
        "the hoisted 19.2.6 to a nested react 19.2.8 (0 nested entries before, "
        "8 after) with no test going red."
    )


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
