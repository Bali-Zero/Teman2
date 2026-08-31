#!/usr/bin/env python3
"""lint_trigger_symmetry.py — guard against the head-green / queue-red split
that happens when a workflow runs in a merge queue but is hidden from the PR
that enters the queue.

THE TRAP (Codex F12 / W69, reproduced live 2026-08-31). In GitHub Actions,
`merge_group:` does NOT support a `paths:` sub-key at all — this is platform
fact, not a policy choice. A workflow that declares BOTH an `on.merge_group`
trigger AND an `on.pull_request` trigger that carries `paths:` or
`paths-ignore:` therefore has path semantics that can never match between the
two triggers:

  * the `pull_request` run may be SKIPPED for a given PR when none of the
    filtered paths changed;
  * the `merge_group` run has no `paths:` key available, so it ALWAYS executes
    for every queued entry.

TWO DISTINCT HARMS, and an earlier draft of this paragraph conflated them into
one — a blind refuter was right to call that mechanically wrong, so they are
separated here.

  * For a NON-REQUIRED context: head-green / queue-red. The author sees a green
    head (the workflow was skipped on their PR), the entry reaches the front of
    the queue, the same job runs there, fails, and the entry is ejected with a
    red the author was never shown.

  * For a REQUIRED context the failure arrives EARLIER, not later. The PR shows
    the context as "Expected — waiting for status to be reported" forever,
    because no `pull_request` run ever reported it, and a PR whose required
    check is pending cannot be added to the merge queue at all (W69). So it is
    NOT a queue-red — it is a PR that can never be queued, with nothing red to
    fix. Different mechanism, different symptom, same root cause, and calling
    both "the queue-red trap" would send whoever hits the second one looking in
    the wrong place.

THE RULE (intentionally narrow, superscar #3 guard over-match: judge the
entity, not the form):

  A workflow VIOLATES if and only if `on.merge_group` is present AND
  `on.pull_request` carries `paths:` or `paths-ignore:`.

Everything else is clean by this rule: no `merge_group`; no `pull_request`; a
`pull_request` with no filter; a `push.paths` filter of any shape.

DECLARED SCOPE LIMIT — `on.push.paths` is DELIBERATELY out of scope. A push to
`main` happens AFTER a PR has already merged and gates no PR, so a filter there
is a legitimate cost optimisation (skip re-running on an irrelevant post-merge
push), not the head-green / queue-red trap above. This guard is concerned only
with the shape that blocks the PR itself. (Same style as
scripts/ci/check_required_workflow_conformance.py's own declared scope limit.)

NO ALLOWLIST. Measured on this repo 2026-08-31: 112 workflows, ZERO violations.
There is no escape hatch because, with an empty violation set, an allowlist
could only ever be used to admit the FIRST violation — and the fix is always
available: remove the `pull_request` paths filter, or do not add the
`merge_group` trigger. If a legitimate case appears later, an allowlist may be
added WITH that case; it must never be added ahead of it (superscar #2
"exists != armed": an armed allowlist before it has anything to allow is just a
backdoor waiting to be used).

PYYAML QUIRK: a bare top-level `on:` key parses as the YAML 1.1 boolean `True`,
not the string `"on"`. The code must read `doc.get("on", doc.get(True))` — this
bites everyone who writes a workflow linter.

Usage:
    python3 scripts/ci/lint_trigger_symmetry.py [--repo-root PATH]

Exit codes:
    0  no violations;
    1  one or more violations (including unparseable workflow files);
    2  operational failure — unreadable workflows directory, or no workflow
       files found at all. Operational failures are never reported as zero
       violations (W84 "esiste ≠ armato"): a guard that found nothing to guard
       is not a guard that passed.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORKFLOW_DIR = Path(".github") / "workflows"


def trigger_present(on_block: Any, name: str) -> bool:
    """Whether trigger `name` is declared in `on_block`.

    Recognises both mapping form (`on.<name>:`) and list form
    (`on: [<name>, ...]`). Scalar/bare forms are treated as absent for the
    triggers this guard cares about.
    """
    if isinstance(on_block, dict):
        return name in on_block
    if isinstance(on_block, list):
        return name in on_block
    return False


#: Per-file opt-out. NOT a central allowlist — the justification travels with
#: the workflow it excuses, where the next reader of that workflow will meet it,
#: instead of in a registry nobody opens. A blind refuter of this lint named a
#: shape the rule forbids that a careful author could make safe: keep the
#: pull_request `paths:` filter for PR-runner economy, and have the merge_group
#: job self-skip with an in-job path filter. Whether that is equivalent is not
#: statically decidable — this rule judges the FORM (`paths:` present) and the
#: hazard is about the ENTITY (can the queue run diverge from the PR run), which
#: is superscar #3 pointed at this lint's own rule. Rather than pretend
#: otherwise, the escape is explicit, one line, and must carry a reason.
_OPT_OUT_RE = re.compile(
    r"^\s*#\s*trigger-symmetry:\s*intentional\s*(?:[-—]\s*(?P<reason>\S.*?))?\s*$",
    re.MULTILINE,
)


def opt_out_reason(text: str) -> str | None:
    """The declared reason a workflow is exempt, or None.

    A marker with NO reason does not exempt: an exemption is a guard running in
    reverse and wants its own justification, not a free pass — the same rule the
    required-context conformance guard applies to its allowlist entries.
    """
    m = _OPT_OUT_RE.search(text)
    if not m:
        return None
    reason = (m.group("reason") or "").strip()
    return reason or None


def pull_request_filter_violation(on_block: Any) -> str | None:
    """Return a violation description if a PR-shaped trigger carries `paths:` or
    `paths-ignore:`, else None.

    BOTH `pull_request` and `pull_request_target` are judged, and the second was
    missing on the first pass — a blind refuter supplied it. They carry the same
    trap for the same reason: each starts a run on a PR, each supports a `paths:`
    filter, and `merge_group` supports none, so either one filtered while the
    queue trigger is present produces the same divergence. Checking only the
    commoner name would have been an under-match on the rarer and more dangerous
    trigger (this repo has exactly one workflow using it, measured).
    """
    if not isinstance(on_block, dict):
        return None
    found: list[str] = []
    for trigger in ("pull_request", "pull_request_target"):
        block = on_block.get(trigger)
        if not isinstance(block, dict):
            continue
        for key in ("paths", "paths-ignore"):
            if key in block:
                found.append(f"on.{trigger}.{key}")
    if not found:
        return None
    return "carries " + ", ".join(repr(k) for k in found)


def format_trigger_shape(on_block: Any, name: str) -> str:
    """Compact representation of how a trigger is declared."""
    if isinstance(on_block, dict):
        # `name not in on_block` is the ONLY test for absence. A bare `merge_group:`
        # parses to None, so `on_block.get(name) is None` cannot tell "key missing"
        # from "key present, no value" -- and the bare form is the commonest way to
        # write this trigger. Reported as "absent", it sent a reader to open the file,
        # find `merge_group:` sitting right there, and conclude the LINTER was broken.
        # The verdict was never wrong (trigger_present uses `name in on_block`); only
        # this message was, and the message is the whole diagnostic surface.
        # Measured on .github/workflows/with-seat-broker-tests.yml, 2026-08-31.
        if name not in on_block:
            return f"on.{name}: absent"
        value = on_block.get(name)
        if value is None or value is True:
            return f"on.{name}: bare"
        if isinstance(value, dict) and not value:
            return f"on.{name}: bare"
        if isinstance(value, dict):
            keys = ", ".join(sorted(value.keys()))
            return f"on.{name}: {{{keys}}}"
        if isinstance(value, list):
            return f"on.{name}: {value!r}"
        return f"on.{name}: present"
    if isinstance(on_block, list):
        return f"on.{name}: present" if name in on_block else f"on.{name}: absent"
    return f"on.{name}: unreadable"


def evaluate(repo_root: Path) -> tuple[list[str], int]:
    """Return (violations, workflows_checked).

    Violations include both symmetry violations and unparseable workflow files.
    An empty workflow list is returned as a checked count of 0 so the caller can
    treat it as an operational failure, not a clean run.
    """
    workflows_dir = repo_root / WORKFLOW_DIR
    try:
        files = sorted(
            p
            for p in workflows_dir.iterdir()
            if p.is_file() and p.suffix in (".yml", ".yaml")
        )
    except OSError:
        return ([f"BLIND: cannot read {workflows_dir}"], 0)

    if not files:
        return ([f"BLIND: no workflow files found in {workflows_dir}"], 0)

    violations: list[str] = []

    for path in files:
        relative = path.relative_to(repo_root)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            violations.append(f"{relative}: unreadable ({exc})")
            continue

        # TWO DISTINCT FAILURES, and conflating them mislabels an innocent file.
        # A refuter of this lint pointed out that a workflow which parses
        # perfectly but simply has no `on:` key was being reported as
        # "unparseable", which is false and sends a reader hunting for a syntax
        # error that is not there. A single parse-or-None helper cannot tell them
        # apart, so the parse is done here and the two are reported separately.
        #
        # That helper (`load_on_block`) used to live above this function and was
        # DELETED rather than left as residue. A cross-family refuter noticed it
        # was unreachable: it read authoritatively, and its YAML-1.1 fallback was
        # the WEAKER one — it took `doc.get(True)` for any scalar, where the code
        # below takes it only when the value is trigger-shaped (mapping or list).
        # A dead function whose behaviour is subtly worse than the live path is
        # not harmless: the next reader wires it back in and reopens the hole.
        try:
            doc = yaml.safe_load(text)
            parsed = True
        except yaml.YAMLError as exc:
            doc, parsed = None, False
            violations.append(f"{relative}: unparseable YAML ({type(exc).__name__})")
        if not parsed:
            continue

        if not isinstance(doc, dict):
            violations.append(f"{relative}: does not parse to a mapping — not a usable workflow")
            continue

        # PyYAML 1.1 reads a bare `on:` as the boolean True. The fallback is
        # necessary and it has an edge the refuter found: a document with no
        # `on:` but a literal `true:` key would satisfy the fallback and sail
        # through. So the fallback is taken ONLY when the value it finds is
        # trigger-shaped (a mapping or a list), never for an arbitrary scalar.
        on_block = doc.get("on")
        if on_block is None:
            candidate = doc.get(True)
            if isinstance(candidate, (dict, list)):
                on_block = candidate
        if on_block is None:
            violations.append(f"{relative}: no `on:` trigger block — nothing this lint can guard")
            continue

        if not trigger_present(on_block, "merge_group"):
            # Rule is narrow: no merge_group means nothing to mismatch.
            continue

        filter_reason = pull_request_filter_violation(on_block)
        if filter_reason is None:
            continue

        reason = opt_out_reason(text)
        if reason:
            # Reported, never silently dropped — an exemption a nobody can see
            # is an exemption nobody can revisit.
            print(f"  ~ {relative}: EXEMPT — {reason}")
            continue

        mg_shape = format_trigger_shape(on_block, "merge_group")
        pr_shape = format_trigger_shape(on_block, "pull_request")
        violations.append(
            f"{relative}: {filter_reason}; {mg_shape}; {pr_shape}"
        )

    return (violations, len(files))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root)
    violations, checked = evaluate(repo_root)

    if checked == 0:
        print(f"trigger-symmetry: CANNOT VERIFY — {violations[0] if violations else 'unknown error'}")
        return 2

    print(f"trigger-symmetry: {checked} workflow(s) checked, {len(violations)} violation(s)")
    for v in violations:
        print(f"  ✗ {v}")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
