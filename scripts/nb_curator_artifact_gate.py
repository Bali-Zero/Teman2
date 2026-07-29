#!/usr/bin/env python3
"""nb_curator_artifact_gate.py — prove the nb-curator actually WROTE its report,
and that the artifact carries an R1 declaration the repo's own gate accepts.

WHY THIS EXISTS (measured 2026-07-28, not reasoned)
---------------------------------------------------
`nb-curator-daily.sh` mandates the R1 frontmatter *inside the prompt*, verbatim,
with the reason spelled out to the model ("every prior report missing this failed
R1 on the PR that harvested it"). That contract is enforced by an LLM's
compliance and nothing else. Compliance is not total — measured on the reports
actually on `main`, in the era where the mandate existed:

  2026-07-10 / 07-11 / 07-12 ... mandated block present in the add-commit  (3 ok)
  2026-07-27 .................... NO frontmatter at all                    (1 miss)

The 07-27 miss is not theoretical: the PR that harvested it (#3254) merged with
the REQUIRED check "R1 gate — adversarial review present" RED, and the next PR to
re-harvest the same file (#3416) was blocked by that same gate.

Worse than the missing line: **nothing downstream looks at the artifact at all.**
The wrapper greps its `SUMMARY:` line out of the brain's STDOUT, never out of the
report file, and ends on an unconditional `exit 0`. A run whose brain prints a
perfect SUMMARY and writes no file whatsoever reports "OK — no action/anomaly"
and leaves a green cron receipt (superscar #2: the receipt is green, the organ
produced nothing).

WHAT THIS DOES (deterministic; policy, never judgment)
------------------------------------------------------
  * report absent / empty / undecodable      -> exit 3, loudly, no write
  * report present, no frontmatter           -> --fix prepends the exemption block
  * report present, frontmatter w/o the key  -> --fix inserts the key IN that block
  * report present, declaration already ok   -> exit 0, file untouched (idempotent)
  * report present, declaration NOT accepted -> exit 4, file untouched

The last row is the one that matters for honesty: a report carrying
`adversarial_review: glm` is an ATTESTATION that a seat reviewed it (2026-07-25
and 07-26 carry exactly that, with a real `## Adversarial review` section written
by a session). This gate will never overwrite one with a machine exemption —
downgrading a claimed review to "exempt" would launder a broken attestation into
a green one. It refuses and says so.

Validity is NOT re-implemented here. It is delegated to
`scripts/check_adversarial_review.py::evaluate_file` — the very code the required
CI gate runs. A second, independent notion of "valid R1 frontmatter" would drift
from the first one and the drift would be invisible (superscar #9).

Exit codes: 0 ok · 2 usage · 3 artifact missing/empty/undecodable ·
4 present but carries a declaration this gate refuses to touch · 5 needs a fix
and --fix was not given.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_adversarial_review as r1  # noqa: E402  (path set above, on purpose)

# Kept textually equal to what nb-curator-daily.sh asks the brain for, so a
# hand-read diff of two reports (one written by the brain, one repaired here)
# shows nothing. They are NOT coupled for correctness: both are valid because
# `evaluate_file` says so, and that is the only judge either of them answers to.
EXEMPT_VALUE = (
    "exempt-machine-report # nb-curator daily health snapshot "
    "(generated artifact, not a research deliverable)"
)
EXEMPT_LINE = f"adversarial_review: {EXEMPT_VALUE}"
DELIM = "---"

# The exemption above is not a formality — it is a CLAIM about the document:
# "generated artifact, not a research deliverable". Stamping it on a document
# that is a deliverable makes this gate write something false, and the R1 gate
# then passes it on that false basis.
#
# Not hypothetical. research/nb-health/ is the curator's OUTPUT directory, and
# it also holds 2026-05-28-nb3-kbli-corrections.md — a human-facing correction
# report on KBLI 2025, verified against a 623-page primary source, carrying an
# explicit "decision → operator" line. It has frontmatter without the R1 key,
# which is precisely the shape --fix rewrites. A backfill over the directory
# would have stamped "generated artifact" on it, and been green.
#
# So: judge the DOCUMENT, never its location (superscar #3 — location is a form,
# deliverable-ness is the entity). The research-capture convention (CLAUDE.md
# §15) makes these keys mandatory for a real deliverable and absent from a
# machine snapshot, so their presence is the discriminator.
#
# LIMIT, declared: this can only see a document that HAS frontmatter. A
# deliverable with no frontmatter at all is indistinguishable from a health
# snapshot here and would still be stamped. The live path is unaffected (the
# wrapper passes the one report it just wrote); the exposure is bulk/backfill
# runs, where the operator reads the refusals.
DELIVERABLE_KEY_RE = re.compile(
    r"^\s*(sources|client_case|discovered_by)\s*:", re.IGNORECASE
)

OK = 0
USAGE = 2
MISSING = 3
REFUSED = 4
NEEDS_FIX = 5


def _split_frontmatter(text: str) -> Tuple[Optional[List[str]], Optional[int]]:
    """Return (frontmatter_lines, index_of_closing_delimiter).

    (None, None)  -> the file has no frontmatter block at all (line 1 != '---')
    (lines, None) -> line 1 IS '---' but no closing '---' was found: MALFORMED,
                     the caller must refuse rather than guess where the header
                     ends.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != DELIM:
        return None, None
    for i in range(1, len(lines)):
        if lines[i].strip() == DELIM:
            return lines[1:i], i
    return lines[1:], None


def _has_key(fm_lines: List[str]) -> bool:
    return any(r1.FRONTMATTER_KEY_RE.match(ln.strip()) for ln in fm_lines)


def _prepend_block(text: str) -> str:
    body = text.lstrip("\n")
    return f"{DELIM}\n{EXEMPT_LINE}\n{DELIM}\n\n{body}"


def _insert_key(text: str, close_idx: int) -> str:
    lines = text.split("\n")
    lines.insert(close_idx, EXEMPT_LINE)
    return "\n".join(lines)


def evaluate(report: Path) -> Tuple[int, str, Optional[str]]:
    """Return (exit_code, human_message, repaired_text_or_None).

    Pure: never writes. `repaired_text` is non-None exactly when a --fix run
    would rewrite the file.
    """
    if not report.exists():
        return (
            MISSING,
            f"ARTIFACT MISSING: the brain reported success but wrote no report at {report}",
            None,
        )
    try:
        raw = report.read_bytes()
    except OSError as exc:  # unreadable is as bad as absent, and just as silent
        return MISSING, f"ARTIFACT UNREADABLE: {report}: {exc}", None
    if not raw.strip():
        return MISSING, f"ARTIFACT EMPTY: {report} exists but has no content", None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return REFUSED, f"ARTIFACT NOT UTF-8: {report}: {exc}", None

    fm_lines, close_idx = _split_frontmatter(text)

    if fm_lines is not None and close_idx is None:
        return (
            REFUSED,
            f"MALFORMED FRONTMATTER: {report} opens with '---' and never closes it — "
            "refusing to guess where the header ends",
            None,
        )

    if fm_lines is not None and not _has_key(fm_lines):
        claimed = [ln.split(":", 1)[0].strip() for ln in fm_lines if DELIVERABLE_KEY_RE.match(ln)]
        if claimed:
            return (
                REFUSED,
                f"REFUSING TO EXEMPT {report.name}: its frontmatter declares "
                f"{', '.join(sorted(set(claimed)))} — that is a research deliverable, and the "
                "machine exemption asserts the opposite ('generated artifact, not a research "
                "deliverable'). Stamping it would make this gate write a false statement and the "
                "R1 gate pass on it. It needs a real adversarial review, by a seat, by hand.",
                None,
            )

    if fm_lines is not None and _has_key(fm_lines):
        verdict = r1.evaluate_file(report)
        if verdict.ok:
            return OK, f"OK: {report.name} already declares — {verdict.reason}", None
        return (
            REFUSED,
            f"DECLARATION PRESENT BUT REJECTED by the R1 gate: {verdict.reason}. "
            "Refusing to overwrite it: an existing adversarial_review value is an "
            "attestation that a seat reviewed this file, and replacing it with a "
            "machine exemption would launder a broken attestation into a green one. "
            "Fix the declaration (or the missing '## Adversarial review' section) by hand.",
            None,
        )

    if fm_lines is None:
        repaired = _prepend_block(text)
        what = "no frontmatter block — prepending the machine-report exemption"
    else:
        repaired = _insert_key(text, close_idx)
        what = "frontmatter without adversarial_review — inserting the exemption key"

    return NEEDS_FIX, f"{report.name}: {what}", repaired


def _verify_after_write(report: Path) -> Tuple[bool, str]:
    verdict = r1.evaluate_file(report)
    return verdict.ok, verdict.reason


def run(report: Path, fix: bool) -> int:
    code, msg, repaired = evaluate(report)

    if code == OK:
        print(msg)
        return OK
    if code in (MISSING, REFUSED):
        print(msg, file=sys.stderr)
        return code

    # code == NEEDS_FIX
    if not fix:
        print(f"NEEDS FIX (run with --fix): {msg}", file=sys.stderr)
        return NEEDS_FIX

    assert repaired is not None
    report.write_text(repaired, encoding="utf-8")
    ok, reason = _verify_after_write(report)
    if not ok:
        # The repair must satisfy the same judge the CI gate uses. If it does
        # not, saying "fixed" would be the lie this whole file exists to stop.
        print(
            f"REPAIR DID NOT SATISFY THE R1 GATE: {report} — {reason}",
            file=sys.stderr,
        )
        return REFUSED
    print(f"REPAIRED: {msg} — now passes R1 ({reason})")
    return OK


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--report", required=True, help="path to the report the brain was told to write")
    p.add_argument(
        "--fix",
        action="store_true",
        help="repair a missing declaration in place (never overwrites an existing one)",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    return run(Path(args.report).expanduser(), fix=args.fix)


if __name__ == "__main__":
    raise SystemExit(main())
