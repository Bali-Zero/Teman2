#!/usr/bin/env python3
"""check_watcher_coverage.py — self-conformance for main-push-failure-watch.yml
(task #23, cicatrix-superscar.md #2 "Esiste != Armato" cure).

THE RULE THIS EXECUTES: the meta-watcher (.github/workflows/main-push-failure-
watch.yml) only protects a workflow's failure if that workflow's `name:` is
present in the watcher's `on.workflow_run.workflows:` list. Add a workflow,
forget to add it to the watcher, and it silently falls back into exactly the
disease task #23 diagnosed (32 push-to-main workflows, 1 watched) — the
watcher itself would then need its own external audit to notice the gap,
which is the theater this file exists to prevent.

Design deliberately mirrors infra/guard-conformance/'s self-protecting-check
pattern (census parity, fail loud on drift, run by its own CI workflow) but
is intentionally NOT folded into that registry: guard-conformance's shape is
guilt+innocence proofs for reply/command guards; this is plain set-equality
between "every workflow's registered name" and "the watcher's declared
list" — a different, simpler contract that doesn't fit that schema.

WHAT IT CHECKS:
  1. Every workflow file's `name:` (the same field GitHub itself uses to
     match `workflow_run.workflows:` — verified empirically 2026-07-26
     against this repo's live `gh api .../actions/workflows` response, not
     assumed from docs) is present in the watcher's list, OR is the
     watcher's own name (self-exclusion is correct, not a gap — see the
     watcher file's header comment on chain-depth/self-trigger).
  2. No stale entries: every name in the watcher's list still matches a
     real workflow (renamed/deleted workflows leave phantom entries
     otherwise, which just accumulate forever without being wrong).
  3. The watcher does not list its OWN name (self-trigger risk).

KNOWN LIMIT (not a gap this file closes): the contract above is pure
name-set membership against the watcher's declared list — it proves a
workflow is LISTED, not that a failure of that workflow actually reaches
anyone. A `pull_request`-only workflow (actionlint, hot-zone-enforcement,
Prettier, Harness floor, and now zantara-core-edit-gate) can never fire
the `push`/`schedule`-on-main `workflow_run` event the watcher's own
`alert` job's `if:` requires (see main-push-failure-watch.yml's SCOPE
comment) — it is listed, this script reports green, and the alert path is
still structurally unreachable for it. That is by design (the list is
deliberately over-inclusive so adding a workflow never requires a
push-vs-pull_request judgment call) but it means green here is narrower
than it looks: verify alert-path reachability separately for any workflow
whose failure actually needs a human paged, do not read this script's
exit 0 as "someone gets told."

Design note carried from the watcher's own build: two live workflow `name:`
fields are unquoted YAML plain scalars containing " #" (`Golden Rule #10 —
httpx pattern lint`, `Guard conformance (superscar #3 enforcement)`) — YAML
treats an unquoted "#" preceded by whitespace as a comment start, so BOTH
this script's parser and GitHub's own registration silently truncate them
("Golden Rule", "Guard conformance (superscar"). Confirmed against the live
GH API, not assumed. This script intentionally uses the SAME parse GitHub
uses (PyYAML's default), so it stays correct against whatever GitHub
actually matches on — do not "fix" the truncation here; fixing the two
source `name:` lines (quote them) is a separate, unrelated 2-line hygiene
PR, out of scope for this file.

Exit 0 = conformant. Exit 1 = drift found (each item printed). Exit 2 =
could not parse (fail loud, never fail silent-clean — cicatrix #2).

    python3 scripts/check_watcher_coverage.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
WATCHER_FILE = WORKFLOWS_DIR / "main-push-failure-watch.yml"


def live_workflow_names() -> dict[str, Path]:
    """Every workflow's registered `name:`, keyed to its file. Fails loud
    (exit 2) on any unparseable file or any workflow missing a `name:` —
    a nameless workflow is invisible to `workflow_run.workflows:` by
    construction, so silently skipping it here would just relocate the gap."""
    names: dict[str, Path] = {}
    if not WORKFLOWS_DIR.exists():
        print(f"::error::workflows dir missing: {WORKFLOWS_DIR}")
        sys.exit(2)
    for f in sorted(WORKFLOWS_DIR.glob("*.yml")):
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            print(f"::error::cannot parse {f}: {e}")
            sys.exit(2)
        if not isinstance(doc, dict):
            print(f"::error::{f} did not parse to a mapping")
            sys.exit(2)
        name = doc.get("name")
        if not name:
            print(f"::error::{f} has no top-level `name:` — invisible to workflow_run matching")
            sys.exit(2)
        names[str(name)] = f
    return names


def watcher_name_and_list() -> tuple[str | None, set[str]]:
    if not WATCHER_FILE.exists():
        print(f"::error::{WATCHER_FILE} does not exist")
        sys.exit(2)
    try:
        doc = yaml.safe_load(WATCHER_FILE.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        print(f"::error::cannot parse {WATCHER_FILE}: {e}")
        sys.exit(2)
    self_name = doc.get("name") if isinstance(doc, dict) else None
    # PyYAML parses `on:` as boolean key True (YAML 1.1 quirk); handle both.
    on = doc.get(True, doc.get("on", {})) if isinstance(doc, dict) else {}
    wr = on.get("workflow_run", {}) if isinstance(on, dict) else {}
    workflows = wr.get("workflows", []) if isinstance(wr, dict) else []
    return self_name, set(str(w) for w in (workflows or []))


def main() -> int:
    live = live_workflow_names()
    self_name, watched = watcher_name_and_list()

    violations: list[str] = []

    if self_name and self_name in watched:
        violations.append(
            f"watcher lists its own name `{self_name}` in workflows: — "
            f"self-trigger risk (workflow_run chains up to 3 levels deep), remove it"
        )

    missing = sorted(n for n in live if n not in watched and n != self_name)
    for n in missing:
        violations.append(f"`{n}` ({live[n].name}) is not covered by {WATCHER_FILE.name}")

    stale = sorted(n for n in watched if n not in live and n != self_name)
    for n in stale:
        print(f"::warning::stale entry in watcher's workflows: list, no matching workflow: `{n}`")

    if violations:
        print(f"watcher-coverage: {len(violations)} violation(s)")
        for v in violations:
            print(f"  ✗ {v}")
        return 1

    print(f"✓ watcher-coverage: all {len(live)} live workflow(s) covered by {WATCHER_FILE.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
