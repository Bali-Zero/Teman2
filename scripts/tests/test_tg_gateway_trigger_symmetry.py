#!/usr/bin/env python3
"""Every suffix the direct-sender lint SCANS must also be a path that TRIGGERS
the job that runs it (cicatrix-superscar.md #2 "Esiste ≠ Armato").

THE DEFECT THIS EXISTS TO CATCH (measured live 2026-07-28):

`lint_tg_direct_senders.py` is the anti-regrowth guard for the Telegram
gateway — "the family of direct Telegram senders can only shrink". It has two
lists that must agree and lived in two different files:

  1. SCAN_SUFFIXES in the lint          — which files it looks inside;
  2. the `paths:` filter in tg-gateway.yml — which diffs start the job at all.

Both were short, in different ways, and each hid the other:

  - `SCAN_SUFFIXES` had no `.yml`/`.yaml`, so the census that founded the
    register never scanned GitHub Actions — the surface where the alarms
    actually live. Uncounted at the time of the fix: **18 workflows holding 28
    direct sendMessage call sites**, none of them in the register, none of them
    ever reported. The lint said "clean" about a place it had never looked
    (superscar #3, UNDER-match: a scope that structurally skips a surface).
  - the `paths:` filter named 6 suffixes against the lint's 15. So even after
    widening the scan, a regrown sender in `.yml`, `.rb`, `.pl`, `.zsh`,
    `.bash`, `.cjs`, `.tsx` or `.jsx` would land in a PR that never started the
    job. A guard that cannot be triggered by the only diff that could violate
    it is decorative.

Fixing one and not the other leaves a guard that is exactly as green and
exactly as blind, which is why this is a machine check and not a comment.

DIRECTION (deliberately one-way): scan ⊆ trigger is required, the converse is
not. The trigger legitimately lists paths that are not suffix globs at all —
the gateway's own sources, `infra/tg-gateway/**` — and may watch a suffix the
lint does not read. Asserting equality would fail on the first legitimate
extra path.

Run:  python3 scripts/tests/test_tg_gateway_trigger_symmetry.py
      pytest scripts/tests/test_tg_gateway_trigger_symmetry.py -q
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tg-gateway.yml"
LINT = REPO_ROOT / "scripts" / "lint_tg_direct_senders.py"

# A trigger entry of the form:  - "**/*.yml"
_GLOB_RE = re.compile(r'^\s+-\s+"\*\*/\*(\.[A-Za-z0-9]+)"\s*$', re.MULTILINE)


def _load_lint():
    spec = importlib.util.spec_from_file_location("lint_tg_direct_senders", LINT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _paths_block(text: str) -> str:
    """The `paths:` list of the pull_request trigger, and only that.

    Anchored rather than scanned whole-file: a suffix glob appearing anywhere
    else in the workflow (a comment, another trigger) must not be mistaken for
    a live trigger entry — the same 'form is not the entity' rule the guard it
    protects is about.
    """
    start = text.index("\n    paths:\n")
    rest = text[start + len("\n    paths:\n"):]
    end = rest.index("\n  workflow_dispatch")
    return rest[:end]


def trigger_suffixes(text: str) -> set[str]:
    return set(_GLOB_RE.findall(_paths_block(text)))


def test_every_scanned_suffix_triggers_the_job() -> None:
    lint = _load_lint()
    text = WORKFLOW.read_text()
    triggers = trigger_suffixes(text)

    # The parser must be able to find a POSITIVE, or an empty set would read as
    # "nothing missing" and this test would pass by being broken (W84).
    assert triggers, (
        "parsed ZERO suffix globs out of tg-gateway.yml's paths: — the parser is "
        "wrong, not the workflow; a blind scan is not a clean scan"
    )

    missing = set(lint.SCAN_SUFFIXES) - triggers
    assert not missing, (
        f"lint_tg_direct_senders.SCAN_SUFFIXES scans {sorted(missing)} but "
        f"tg-gateway.yml does not trigger on {sorted(missing)}. A PR that regrows a "
        f"direct Telegram sender in one of those files would not start the guard "
        f"at all. Add '**/*<suffix>' to the paths: list."
    )


def test_legacy_suffix_set_is_a_subset_of_the_current_one() -> None:
    """LEGACY_SCAN_SUFFIXES records what the 2026-07-06 register COULD see.

    check_monotone grants a one-time enrollment to suffixes outside it, so if
    someone ever "tidied" it by removing an entry, files whose suffix was always
    visible would silently become enrollable — turning the exemption into the
    bypass the monotone rule exists to close.
    """
    lint = _load_lint()
    assert set(lint.LEGACY_SCAN_SUFFIXES) <= set(lint.SCAN_SUFFIXES), (
        "LEGACY_SCAN_SUFFIXES must stay a subset of SCAN_SUFFIXES: it is a "
        "historical fact about what the founding census covered, not a setting"
    )
    assert ".yml" not in lint.LEGACY_SCAN_SUFFIXES and ".yaml" not in lint.LEGACY_SCAN_SUFFIXES, (
        "the 2026-07-06 census did NOT scan .yml/.yaml — recording that it did "
        "would retroactively make 19 grandfathered workflow entries look like "
        "illegal growth, and the next real growth would be waved through"
    )


def test_register_declares_the_scope_it_froze() -> None:
    """A register that does not say what it scanned cannot be read honestly."""
    import json

    doc = json.loads((REPO_ROOT / "infra" / "tg-gateway" / "grandfathered.json").read_text())
    declared = set(doc.get("scan_suffixes", []))
    assert declared, "grandfathered.json must declare scan_suffixes"
    lint = _load_lint()
    assert declared == set(lint.SCAN_SUFFIXES), (
        f"grandfathered.json declares {sorted(declared)} but the lint scans "
        f"{sorted(set(lint.SCAN_SUFFIXES))}. Re-freeze (or hand-merge) so the register "
        f"states the scope it actually covers — otherwise 'no senders in X' and "
        f"'nobody looked at X' stay indistinguishable."
    )


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok   {name}")
            except AssertionError as exc:
                failures += 1
                print(f"  FAIL {name}\n       {exc}")
    print("PASS" if not failures else f"FAIL ({failures})")
    sys.exit(1 if failures else 0)
