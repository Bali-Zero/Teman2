#!/usr/bin/env python3
"""lint_decision_registry.py — executable antidote for W40/W128 applied to decision ids.

THE DEFECT (W40 migration-number collision, and its sibling W128 scar-number
collision): a `D-NNN` decision id is only CLAIMED when a writer edits
`docs/decisions/registry.yaml` and only RESOLVED when the edit merges. The next
writer who needs a number looks at the file, picks what appears to be free, and
if nobody re-reads the current draft, two concurrent lanes can pick the same
`D-NNN`. A reservation living only in a document that nobody re-reads decays
monotonically with the number of concurrent writers.

This script lints the registry for duplicates, malformed ids, shape errors,
missing evidence, and dangling cross-references. It is pure at the core; the
only I/O is reading the registry and, for evidence paths, asking git whether the
path exists on `origin/main`.

Exit codes: 0 = clean · 1 = violations · 2 = usage error · 3 = registry file
missing or unreadable.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = Path("docs/decisions/registry.yaml")

_ID_RE = re.compile(r"^D-(\d{3})$")
_ALLOWED_STATUSES = {"proposed", "accepted", "superseded-by", "postponed"}
_ALLOWED_DOORS = {"one-way", "two-way"}
_EVIDENCE_FRAGMENT_RE = re.compile(r"#[Ll]\d+$")

Entry = dict[str, Any]


class CannotVerify(Exception):
    """The lint could not look, which is neither clean nor dirty.

    A distinct type because the CLI must render it as a VERDICT with an exit
    code, not as a traceback. The previous version raised a bare RuntimeError
    that `main` did not catch — so the docstring promised a CANNOT-VERIFY verdict
    and the code delivered a stack trace, which is a claim the code made about
    itself and did not keep.
    """


class ParseError(Exception):
    """A line of the registry could not be parsed by the small YAML subset parser."""

    def __init__(self, line: int, message: str) -> None:
        self.line = line
        self.message = message
        super().__init__(f"line {line}: {message}")


def _strip_comment(line: str) -> str:
    """Remove a trailing YAML comment while preserving `#` inside values like `CLAUDE.md#L130`.

    A `#` starts a comment only when it is outside quotes and is preceded by
    whitespace (or is the first character). This keeps path fragments such as
    `#L130` intact.
    """
    in_single = False
    in_double = False
    chars: list[str] = []
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double and (i == 0 or line[i - 1].isspace()):
            break
        chars.append(ch)
    return "".join(chars).rstrip()


def _parse_scalar(value: str, line_no: int) -> str | list[str]:
    """Parse one YAML value: inline list, quoted string, or unquoted scalar."""
    value = value.strip()
    if not value:
        return ""

    # Inline list: [] or [D-002, D-003]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        items = [item.strip() for item in inner.split(",")]
        return [item for item in items if item]

    # Quoted string
    if len(value) >= 2:
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            return value[1:-1]

    # Unquoted scalar
    return value


def parse_registry(text: str) -> list[Entry]:
    """Parse the small YAML subset used by `docs/decisions/registry.yaml`.

    Raises `ParseError` on the first line that cannot be parsed; unparsable
    content is never silently skipped.
    """
    entries: list[Entry] = []
    current: Entry | None = None
    started = False

    for line_no, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if not started:
            if stripped.startswith("decisions:"):
                started = True
                continue
            raise ParseError(line_no, f"expected top-level 'decisions:', got {raw!r}")

        item_match = re.match(r"^  - ([\w-]+):\s?(.*)$", raw)
        if item_match:
            if current is not None:
                entries.append(current)
            key, raw_value = item_match.group(1), item_match.group(2)
            value = _parse_scalar(_strip_comment(raw_value), line_no)
            current = {
                "_line": line_no,
                "_field_lines": {key: line_no},
                key: value,
            }
            continue

        # `[\w-]`, not `\w`: the STATUS value is literally spelled `superseded-by`,
        # so a writer naturally reaches for `superseded-by:` as the key too. Under
        # `\w+` that was a hard ParseError on the single most confusable field in
        # the schema. It is accepted, normalised to the underscore spelling, and
        # the writer is not punished for the schema's own inconsistency.
        # `:\s?` — a bare `key:` with no value is valid YAML (null) and a natural
        # way to leave a field blank. Rejecting it as UNPARSEABLE moved a schema
        # question into the parser, where the answer is "I do not understand this
        # file" instead of the true "this field is empty and should not be". Let
        # it through; R3/R5 judge whether an empty value is allowed there.
        cont_match = re.match(r"^    ([\w-]+):\s?(.*)$", raw)
        if cont_match:
            if current is None:
                raise ParseError(line_no, f"continuation key outside entry: {raw!r}")
            key, raw_value = cont_match.group(1), cont_match.group(2)
            key_norm = key.replace("-", "_")
            if key_norm in current and not key_norm.startswith("_"):
                # A repeated key inside one entry used to overwrite silently, and
                # that hollowed out R1 — the whole point of this lint. Paste a
                # record, add a new `id:` at the top, leave the old one below: the
                # first id vanishes, so TWO entries can claim one number and the
                # hard-fail never sees it. The most likely hand-edit accident was
                # the one case the collision rule could not catch.
                raise ParseError(
                    line_no,
                    f"duplicate key {key_norm!r} in the entry starting at line "
                    f"{current['_line']} (first seen at line {current['_field_lines'][key_norm]})",
                )
            key = key.replace("-", "_")
            current[key] = _parse_scalar(_strip_comment(raw_value), line_no)
            current["_field_lines"][key] = line_no
            continue

        raise ParseError(line_no, f"cannot parse line: {raw!r}")

    if current is not None:
        entries.append(current)

    if not started:
        raise ParseError(1, "expected top-level 'decisions:'")

    return entries


def check_unique_ids(entries: list[Entry]) -> list[str]:
    """R1: a reused `D-NNN` is a hard fail. Report all line numbers for each duplicate."""
    id_lines: dict[str, list[int]] = {}
    for entry in entries:
        did = entry.get("id")
        if isinstance(did, str) and _ID_RE.match(did):
            id_lines.setdefault(did, []).append(entry["_line"])

    violations: list[str] = []
    for did, lines in id_lines.items():
        if len(lines) > 1:
            violations.append(
                f"R1 duplicate id {did} at lines {', '.join(str(n) for n in sorted(lines))}"
            )
    return violations


def check_id_format(entries: list[Entry]) -> list[str]:
    r"""R2: every id must match `^D-\d{3}$`."""
    violations: list[str] = []
    for entry in entries:
        did = entry.get("id")
        line = entry["_line"]
        if not isinstance(did, str) or not _ID_RE.match(did):
            violations.append(f"R2 malformed id {did!r} at line {line} (expected D-NNN)")
    return violations


def check_status_shape(entries: list[Entry]) -> list[str]:
    """R3: status value and conditional fields (`superseded_by`, `revisit_by`) are correct."""
    all_ids = {entry.get("id") for entry in entries if isinstance(entry.get("id"), str)}
    violations: list[str] = []

    for entry in entries:
        status = entry.get("status")
        status_line = entry.get("_field_lines", {}).get("status", entry["_line"])
        superseded_by = entry.get("superseded_by")
        revisit_by = entry.get("revisit_by")
        own_id = entry.get("id")

        if status not in _ALLOWED_STATUSES:
            violations.append(f"R3 invalid status {status!r} at line {status_line}")

        if status == "superseded-by":
            if not isinstance(superseded_by, str) or not superseded_by:
                violations.append(
                    f"R3 status superseded-by at line {status_line} missing superseded_by"
                )
            elif superseded_by == own_id:
                violations.append(
                    f"R3 {own_id!r} at line {status_line} superseded by itself"
                )
            elif superseded_by not in all_ids:
                sb_line = entry.get("_field_lines", {}).get("superseded_by", entry["_line"])
                violations.append(
                    f"R3 superseded_by {superseded_by!r} at line {sb_line} does not exist"
                )
        elif superseded_by is not None:
            # No `!= ""` carve-out. An empty `superseded_by:` on a record that is
            # not superseded used to pass silently — a field present, meaningless,
            # and read by a human as "somebody looked into this". A vacuous field
            # is worse than an absent one, because absence is honest.
            sb_line = entry.get("_field_lines", {}).get("superseded_by", entry["_line"])
            violations.append(
                f"R3 superseded_by present at line {sb_line} but status is {status!r}"
            )

        if status == "postponed":
            if not isinstance(revisit_by, str) or not revisit_by:
                violations.append(
                    f"R3 status postponed at line {status_line} missing revisit_by"
                )
        elif revisit_by is not None and revisit_by != "":
            rb_line = entry.get("_field_lines", {}).get("revisit_by", entry["_line"])
            violations.append(
                f"R3 revisit_by present at line {rb_line} but status is {status!r}"
            )

    return violations


def check_door(entries: list[Entry]) -> list[str]:
    """R4: `door` is required and must be `one-way` or `two-way`."""
    violations: list[str] = []
    for entry in entries:
        door = entry.get("door")
        line = entry.get("_field_lines", {}).get("door", entry["_line"])
        if door not in _ALLOWED_DOORS:
            violations.append(f"R4 invalid or missing door {door!r} at line {line}")
    return violations


def check_evidence_resolves(
    entries: list[Entry], resolver: Callable[[str], bool]
) -> list[str]:
    """R5: every `evidence` path resolves; strip `#Lnnn` fragments before resolving."""
    violations: list[str] = []
    for entry in entries:
        evidence = entry.get("evidence")
        line = entry.get("_field_lines", {}).get("evidence", entry["_line"])
        if evidence is None:
            violations.append(f"R5 missing evidence at line {line}")
            continue
        if not isinstance(evidence, str) or not evidence:
            violations.append(f"R5 empty or malformed evidence at line {line}")
            continue
        path = _EVIDENCE_FRAGMENT_RE.sub("", evidence)
        if not resolver(path):
            violations.append(f"R5 evidence unresolved at line {line}: {path!r}")
    return violations


def check_contradicts_resolve(entries: list[Entry]) -> list[str]:
    """R6: every id referenced by `contradicts` must exist in the registry."""
    all_ids = {entry.get("id") for entry in entries if isinstance(entry.get("id"), str)}
    violations: list[str] = []
    for entry in entries:
        contradicts = entry.get("contradicts", [])
        line = entry["_line"]
        if not isinstance(contradicts, list):
            violations.append(
                f"R6 contradicts must be a list at line {entry['_field_lines'].get('contradicts', entry['_line'])}: "
                f"got {contradicts!r} — a scalar here was silently SKIPPED, so a "
                f"malformed field read as 'no contradictions'"
            )
            continue
        for target in contradicts:
            if isinstance(target, str) and target not in all_ids:
                violations.append(
                    f"R6 contradicts target {target!r} at line {line} does not exist"
                )
    return violations


def compute_id_map(entries: list[Entry]) -> dict[str, list[int]]:
    """Map well-formed decision id -> list of line numbers where it appears."""
    id_map: dict[str, list[int]] = {}
    for entry in entries:
        did = entry.get("id")
        if isinstance(did, str) and _ID_RE.match(did):
            id_map.setdefault(did, []).append(entry["_line"])
    return id_map


def find_collisions(id_map: dict[str, list[int]]) -> dict[str, list[int]]:
    """Return ids that appear on more than one line."""
    return {did: lines for did, lines in id_map.items() if len(lines) > 1}


def next_free_id(entries: list[Entry]) -> str:
    """Monotonic id convention: smallest number strictly above every well-formed id seen."""
    nums = []
    for entry in entries:
        did = entry.get("id")
        if isinstance(did, str):
            m = _ID_RE.match(did)
            if m:
                nums.append(int(m.group(1)))
    if not nums:
        return "D-001"
    return f"D-{max(nums) + 1:03d}"


def format_report(violations: list[str], next_id: str | None = None) -> str:
    """Human-readable lint report."""
    lines: list[str] = []
    if next_id is not None:
        lines.append(f"Next free decision id: {next_id}")
    if violations:
        lines.append("")
        lines.append(f"VIOLATIONS — {len(violations)} found:")
        for violation in violations:
            lines.append(f"  {violation}")
    else:
        lines.append("No violations.")
    return "\n".join(lines)


def run_lint(
    entries: list[Entry], resolver: Callable[[str], bool]
) -> tuple[int, list[str]]:
    """Pure orchestration: registry entries -> (exit_code, violations). No I/O."""
    violations: list[str] = []
    violations.extend(check_unique_ids(entries))
    violations.extend(check_id_format(entries))
    violations.extend(check_status_shape(entries))
    violations.extend(check_door(entries))
    violations.extend(check_evidence_resolves(entries, resolver))
    violations.extend(check_contradicts_resolve(entries))
    return (1 if violations else 0), violations


def gather_live_registry_data(
    registry_path: Path,
) -> tuple[list[Entry], Callable[[str], bool]]:
    """Read the local registry and return a resolver over origin/main, HEAD, then the tree.

    The order carries the meaning:

      - `origin/main` is the question that matters — did this evidence actually
        land, or is the record pointing at something that only ever existed in a
        branch someone abandoned?
      - `HEAD` and the working tree are the bootstrap. A change that adds a
        decision AND the artefact it cites together is the normal case (this
        registry's own D-012 is exactly that, and at pre-commit time the file is
        staged rather than committed). Rejecting it would mean landing the
        evidence first and the record later, which is how records stop getting
        written at all.

    A typo resolves in NONE of the three and is still a violation, which is the
    property worth keeping. What is given up, deliberately: an evidence path
    added in this change is trusted one commit before it is on main.
    """
    text = registry_path.read_text(encoding="utf-8")
    entries = parse_registry(text)

    # ONE up-front probe for "can I ask git at all", then plain exit codes.
    # Deliberately NOT stderr string-matching: git says "exists on disk, but not
    # in 'origin/main'" in one case and "does not exist in" in another (both
    # measured), and a rule keyed to that prose breaks the day git rewords it.
    # This fleet already cured that anti-pattern once, in lint_immune_contracts.py.
    # Probe for ANY usable ref, not for origin/main specifically. Getting this
    # wrong was a CI landmine I nearly shipped: the immune workflow's ONLY
    # `git fetch origin main` sits ~750 lines AFTER the unit-test battery that
    # runs this lint, and the workflow's own comment says checkout's
    # fetch-depth:0 does not reliably leave refs/remotes/origin/main on a
    # pull_request event. So `origin/main` is routinely ABSENT when this runs —
    # and gating on it alone would have raised on every innocent PR and turned a
    # required job red for a ref that was never fetched.
    #
    # HEAD plus the working tree is a weaker check than origin/main, not a blind
    # one: a typo still resolves nowhere. CANNOT-VERIFY is reserved for the case
    # where NOTHING is answerable, which is the only state that deserves it.
    def _ref_ok(ref: str) -> bool:
        return (
            subprocess.run(
                ["git", "rev-parse", "--verify", "--quiet", ref],
                cwd=REPO_ROOT,
                capture_output=True,
            ).returncode
            == 0
        )

    usable_refs = [r for r in ("origin/main", "HEAD") if _ref_ok(r)]

    def _in_ref(ref: str, path: str) -> bool:
        # `-t` and not `-e`: `-e` says "an object exists here", which is TRUE for
        # a directory (`evidence: docs` resolved), for a submodule gitlink, and
        # for anything else git happens to have at that name. Evidence must be a
        # readable DOCUMENT, so the object has to be a blob.
        proc = subprocess.run(
            ["git", "cat-file", "-t", f"{ref}:{path}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        return proc.returncode == 0 and proc.stdout.strip() == "blob"

    def resolver(path: str) -> bool:
        if not path:
            return False
        # Confined to the repo, checked LEXICALLY before any filesystem call.
        # `evidence: /etc/passwd` resolved through `Path.exists()` and left the
        # repository entirely; `../secrets` would too. A registry records
        # decisions about THIS repo, so evidence outside it is a category error
        # even when the file is really there.
        if path.startswith("/") or path.startswith("~") or ".." in Path(path).parts:
            return False
        if not usable_refs and not REPO_ROOT.exists():
            # W84: a probe that could not look has not looked. Reserved for the
            # state where nothing at all is answerable.
            raise CannotVerify(
                "no git ref and no working tree are readable, so no evidence path "
                "can be checked. That is not a clean registry and not a dirty one "
                "— it is an unanswered question."
            )
        return any(_in_ref(r, path) for r in usable_refs) or (REPO_ROOT / path).is_file()

    return entries, resolver


def gather_fixture_registry_data(
    fixture_path: Path,
) -> tuple[list[Entry], Callable[[str], bool]]:
    """Offline/test path: parse the fixture and accept every evidence path."""
    text = fixture_path.read_text(encoding="utf-8")
    entries = parse_registry(text)
    return entries, lambda _path: True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
        help=f"registry file to lint (default: {DEFAULT_REGISTRY})",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=None,
        help="registry fixture to parse instead of the live file (resolver accepts all paths)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit JSON report instead of plain text",
    )
    parser.add_argument(
        "--print-next-id",
        action="store_true",
        help="print only the next free decision id; violations go to stderr",
    )
    args = parser.parse_args(argv)

    try:
        if args.fixture:
            entries, resolver = gather_fixture_registry_data(args.fixture)
        else:
            entries, resolver = gather_live_registry_data(args.registry)
    except ParseError as exc:
        sys.stderr.write(f"PARSE ERROR at line {exc.line}: {exc.message}\n")
        return 1
    except OSError as exc:
        target = args.fixture if args.fixture else args.registry
        sys.stderr.write(f"ERROR: cannot read {target}: {exc}\n")
        return 3

    try:
        exit_code, violations = run_lint(entries, resolver)
    except CannotVerify as exc:
        # A VERDICT, not a traceback. Exit 4 so a caller can tell "I could not
        # check" apart from "I checked and it is dirty" (1) and from "I could not
        # find the file" (3) — three different states that must not share a code.
        sys.stderr.write(f"CANNOT-VERIFY: {exc}\n")
        return 4
    next_id = next_free_id(entries)

    if args.print_next_id:
        print(next_id)
        if exit_code:
            for violation in violations:
                sys.stderr.write(f"{violation}\n")
    elif args.json:
        print(
            json.dumps(
                {"exit_code": exit_code, "next_free_id": next_id, "violations": violations},
                indent=2,
            )
        )
    else:
        print(format_report(violations, next_id))

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
