#!/usr/bin/env python3
"""pending_arms_report.py — superscar #2 "Esiste != Armato / Armamento Sospeso" (W81) reconciliation report.

The W81 ledger (`.claude/skills/modus/PENDING-ARMS.md`) records every artifact that was
BUILT but not yet {merged, installed, propagated, armed, committed}. This script is a
PURE SIGNALER over that ledger: it parses the open section, ages each entry, and alarms
on anything TECH-DEBT-classified that has sat unarmed for >48h — while distinguishing
that from legitimate, pre-declared firebreaks (operator gate / Legge 5 / business
decision) which are informational only, never an alarm, and from NATURAL-WAIT lines
(owner declares a passive wait on a dated calendar trigger, e.g. `me (passivo —
verifica 07-12)`): armed work whose proof needs the calendar is not overdue debt,
and alarming on it starves the healer's idle branch (genome convergence, 2026-07-06).

It NEVER writes, edits, or otherwise mutates anything — ledger, filesystem, or process
state. It only reads the ledger and prints a report (markdown by default, --json on
request). The only way this script affects control flow is its own exit code, and only
under --strict.

Ledger format (documented in the ledger's own header):

    - opened YYYY-MM-DD | artifact | missing arming step | owner (me|operator[<category>]) | proof-of-armed

The parser also accepts "- open YYYY-MM-DD" (dropped "-ed") — a verb-tense drift found
live in the real ledger that a bare "- opened " prefix check silently discarded as an
unrelated list item instead of parsing it as debt.

Entries are recognized ANYWHERE in the file by their own "- opened "/"- open " + date
prefix — never gated by position relative to a `## closed` heading. `- closed ` lines
(proof-of-armed history) are excluded by that same prefix check regardless of where
they live, so no positional cutoff is needed to keep them out. This matters in
practice: a strict "stop scanning at the first `## closed` heading" cutoff was found
2026-07-11 to silently swallow 14 real open-debt lines that had been appended BELOW
that heading over several sessions (mixed in with genuine closed history) — a
positional guard is itself a family #3 under-match the moment reality stops matching
the assumed document shape.

PHANTOM-OPERATOR rule (Zero, 2026-07-06: "io sono te — non c'è nessun operatore"):
sessions ARE the operator for all repo/infra work. An owner may say `operator` ONLY
for the true-operator categories — actions a session structurally cannot take — and
must DECLARE the category inline as `operator[<category>]` (see
TRUE_OPERATOR_CATEGORIES). An `operator` owner with no declared category, or an
unrecognized one, is classified PHANTOM-OPERATOR: work parked behind a human lane
that does not exist. It is the loudest bucket in the report, and both --strict and
--strict-phantom fail on it REGARDLESS OF AGE — a phantom is wrong the moment it is
written, not after 48h.

MALFORMED rule (found live 2026-07-26: a stray/orphaned diff3 conflict marker,
`||||||| ebfbd71019`, baked as main's own committed ledger line silently blanked
the owner of the entry above it — `owner=?`, `cls=TECH-DEBT` — never tripping the
pipe-count malformed check and never matching the phantom-operator substring, so a
corrupted line sailed straight through both gates). An entry whose owner cannot be
parsed at all is, if anything, MORE untrustworthy than a phantom one — the ledger
cannot even say who is supposed to own it — so it is classified MALFORMED and both
--strict and --strict-phantom fail on it too, same as PHANTOM-OPERATOR. A stray
conflict-marker-shaped line is also refused as a continuation (CONFLICT_MARKER_RE)
rather than silently absorbed into whatever entry is being built, and is surfaced as
its own MALFORMED entry instead of vanishing without a trace.

PR-ALREADY-MERGED rule (added 2026-08-03, megatopics-1-5 action plan #1): an entry
whose artifact/missing_step/proof cites a `PR #NNN` reference that `gh pr
view` now reports as MERGED is a CANDIDATE for "its owner is still waiting on
something that already landed" — but measured against the real 312-entry
ledger the SAME day this shipped, this is a noisy, low-confidence signal, not
a verdict, and the report/JSON label it as such. Two false-positive classes
found live: (1) a bare `#NNN` token is not always a PR — `(#6860, #2837,
#2836)` in one real entry are CodeQL ALERT numbers sitting next to an
unrelated file:line list, so the regex requires a literal `PR` immediately
before the hash (cuts the naive match count roughly 3x on this ledger); (2)
even with that anchor, this ledger's own authoring convention is to cite a
merged PR as historical/precedent context ("cured via PR #3524", "mirroring
PR #2921's design") far more often than as a live blocker — of every
PR-anchored hit manually reviewed against this ledger, none were a genuine
"still waiting, and now it merged" case; every one was the author already
knowing and stating the PR's status while the entry stays open for an
UNRELATED reason. A reliable version of "is this specific entry's remaining
work blocked on this specific PR" needs semantic judgment (Tier-2, explicitly
out of scope for this Tier-1 signaler) or a git-blame correlation this file
does not attempt. Treat this section as a skim list for a human's own
judgment, never as an actionable alert — it is why `--strict`'s exit code
never reads `merged_pr_refs`/CLASS_PR_ALREADY_MERGED, only entry.cls.

This check is OPT-IN via --check-pr-refs (default off)
because it needs network + `gh` auth, which the existing test suite and any
offline/shallow-checkout run cannot assume; when the flag is not passed,
every entry's merged_pr_refs stays empty and this rule never fires, so
behavior is byte-for-byte unchanged from before this feature existed. A PR
reference `gh` could not verify (missing binary, auth failure, timeout,
non-zero exit, unparseable JSON) is NEVER treated as merged — same "judge the
reply, never assume success" discipline as _ledger_freshness (W104): an
unverifiable ref just doesn't count toward merged_pr_refs, it does not crash
the report and it is not silently promoted to "merged" either.

READING MAIN FROM A CHECKOUT THAT IS BEHIND (--ref, added 2026-08-08): this ledger is
read out of a working tree, and on m5 the main checkout is deliberately left behind
origin/main (pulling it races live worktrees), so the rows can be genuinely stale.
The freshness line has always SAID so — but until now it prescribed "pull", which is
exactly what m5 must not do and what `worktree_isolation.py` refuses for any agent
session in the main checkout. A prescription only a nonexistent lane can carry out
trains its reader to ignore the probe, and the next one that matters gets ignored too.
`--ref origin/main` reads the ledger with `git show`: no pull, no fetch, no write, so
it works from the main checkout as well. It is deliberately FATAL when the ref cannot
be read — silently answering with the working tree would let a caller believe it is
looking at main while it looks at its own stale copy, which is the lie the flag exists
to end. Default (no --ref) still reads the working tree, so a session that has just
written its own line still sees it.

Usage:
    python3 scripts/pending_arms_report.py [--ledger PATH] [--ref GITREF] [--now YYYY-MM-DD]
                                           [--json] [--strict] [--strict-phantom]

Exit codes:
    0   always, by default (pure signaler — a report is not a failure)
    1   with --strict, if >=1 overdue TECH-DEBT entry OR >=1 PHANTOM-OPERATOR entry
        OR >=1 MALFORMED entry exists; with --strict-phantom, if >=1 PHANTOM-OPERATOR
        entry OR >=1 MALFORMED entry exists (the narrow CI ledger gate — pre-existing
        overdue debt never blocks innocent PRs)
    2   ledger file not found, or a CLI argument error (argparse's own exit code)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

# 48h at day-precision: the ledger records opened-dates, not timestamps, so "overdue"
# is age_days >= 2 (i.e. the entry has survived at least one full day beyond the day
# it was opened, which is the closest day-precision proxy for >48h — declared here and
# in every report header so nobody mistakes it for hour-precision).
OVERDUE_AGE_DAYS = 2

# Tolerates the 'opened'/'open' verb-tense drift seen in the real ledger (14 lines
# written "- open YYYY-MM-DD" instead of "- opened YYYY-MM-DD") — a bare-prefix
# entry-start check silently dropped every one of them (family #3 under-match: the
# guard watched one literal spelling and let the real debt through unclassified).
OPENED_RE = re.compile(r"-\s*open(?:ed)?\s+(\d{4}-\d{2}-\d{2})")
ENTRY_START_RE = re.compile(r"^-\s*open(?:ed)?\s+\d{4}-\d{2}-\d{2}")

CLASS_MALFORMED = "MALFORMED"
CLASS_FIREBREAK = "FIREBREAK"
CLASS_NATURAL_WAIT = "NATURAL-WAIT"
CLASS_OPERATOR_GATED = "OPERATOR-GATED"
CLASS_TECH_DEBT = "TECH-DEBT"
CLASS_PHANTOM_OPERATOR = "PHANTOM-OPERATOR"
# Not a parse_entry() classification like the others above — this bucket is
# derived AFTER parsing, only when --check-pr-refs ran annotate_pr_refs() and
# found a cited #NNN PR reference that `gh pr view` reports MERGED. See
# PR-ALREADY-MERGED rule in the module docstring.
CLASS_PR_ALREADY_MERGED = "PR-ALREADY-MERGED"

# The ONLY categories for which owner=operator is legitimate — actions a session
# structurally cannot take (feedback_no_operator_lane_io_sono_te_2026_07_06). Anything
# else labeled `operator` is a phantom: repo/infra work a session can and must do.
TRUE_OPERATOR_CATEGORIES = frozenset(
    {
        "physical",  # physical device actions (IG app toggle, hardware, on-site)
        "gui",  # GUI-only surfaces: interactive logins, GitHub settings, external-UI paste
        "tcc",  # macOS TCC grants (System Settings, per-principal)
        "consent",  # consents only the human can give
        "secret",  # credentials/keychain material only the human holds
        "control-plane",  # ~/.claude/hooks one-liners (host_boundary stays hard by design)
        "business",  # Legge 5 / strategy decisions (incl. arming historically-broken crons)
    }
)

# Tag form: `operator[<category>]` — declared in the owner field. Word-anchored so the
# tag itself is structural, while phantom DETECTION below stays substring-based on the
# owner ("operatore" in Italian prose must not slip through as TECH-DEBT — W82 under-match).
OPERATOR_TAG_RE = re.compile(r"\boperator\s*\[\s*([a-z0-9-]+)\s*\]", re.IGNORECASE)

# Explicit disclaimer of an operator-lane claim ("not operator-gated", "not
# operator[<cat>]") — found live 2026-08-30 (healer tick, PR #5269 blocked by
# --strict-phantom): the owner field "next BUILD session (repo-side; not
# operator-gated — this is a real code fix, just not a healer-tick-safe one)"
# was classified PHANTOM-OPERATOR because plain substring matching on "operator"
# cannot see the "not " sitting in front of it.
#
# WIDENED 2026-08-30 (round 2, PR #5233's own ledger row tripped it): "NOT this
# implementer session, NOT a bare operator" was still flagged, because the
# original regex required "not" immediately adjacent to "operator" — zero
# words of slack — and "a bare" sits in between. The gap is bounded to a
# small, CLOSED vocabulary of hedge/determiner words (article + a short
# adjective/adverb list), not an open `\w+`: an open wildcard would let an
# unrelated "not" anywhere upstream of a genuine bare "operator" (e.g. "not
# yet resolved — assign to operator") rescue a real phantom claim, which is
# the over-correction this classifier exists to avoid (team-lead's explicit
# warning on this fix). "\boperator\b" stays word-bounded — this must never
# become a bare substring match, or it re-opens W82 (the Italian "operatore"
# under-match OPERATOR_TAG_RE's own comment guards against).
NEGATED_OPERATOR_RE = re.compile(
    r"\bnot\s+(?:(?:a|an|the|bare|just|merely|purely|simply|really|genuinely"
    r"|truly|literally|plain|mere)\s+){0,3}operator\b",
    re.IGNORECASE,
)

# Word-bounded "operator" mentions, used ONLY to enumerate candidate spans for
# the completeness check below — never as a substitute for the deliberately
# substring-based outer gate (`"operator" in owner.lower()`, W82 guard).
OPERATOR_WORD_RE = re.compile(r"\boperator\b", re.IGNORECASE)


def _all_operator_mentions_negated(owner: str) -> bool:
    """True iff EVERY word-bounded "operator" mention in `owner` falls inside
    a NEGATED_OPERATOR_RE match — not merely that at least one negated phrase
    exists somewhere in the field. Closes a second latent gap alongside the
    regex widening above: the original call site was `NEGATED_OPERATOR_RE
    .search(owner)`, a bare existence check, so an owner naming TWO operator
    mentions where only one is negated ("not operator, but flag for operator
    eventually") would have been waved through on the strength of the first.
    Callers invoke this only when `not tags` (checked at the call site) — no
    `operator[<cat>]` bracket exists anywhere in `owner`, so every mention
    OPERATOR_WORD_RE finds here is genuinely naked, never a tag fragment.
    Returns False (not phantom-safe) when there is no mention at all —
    defensive only; every real caller has already confirmed "operator" is
    present via the outer substring gate."""
    mentions = [m.span() for m in OPERATOR_WORD_RE.finditer(owner)]
    if not mentions:
        return False
    negated_spans = [m.span() for m in NEGATED_OPERATOR_RE.finditer(owner)]
    return all(
        any(neg_start <= start and end <= neg_end for neg_start, neg_end in negated_spans)
        for start, end in mentions
    )

# NATURAL-WAIT: the owner declares a PASSIVE wait on a dated natural trigger
# (`me (passivo — verifica 07-12)`) — the arming is done, only the proof needs the
# calendar. NOT overdue debt: strict must not fail on it, and the healer's ledger
# receptor must not fire on it every tick (it starved the genome-convergence idle
# branch for a week the day it went live). Word-anchored (#3: "impassivo" in prose
# must not match; a bare `me` owner must stay TECH-DEBT).
NATURAL_WAIT_RE = re.compile(r"\b(?:passiv[oa]|passive)\b", re.IGNORECASE)

# A stray/orphaned diff3 conflict marker left in the ledger by a botched merge
# resolution (found live 2026-07-26: `||||||| ebfbd71019` baked as main's own
# committed line 519, no matching <<<<<<</=======/>>>>>>> anywhere in the file)
# must never be silently absorbed as a continuation line — a `|||||||` marker
# alone injects SEVEN pipe characters into whatever entry is being built,
# which pipe-splits into a run of empty fields and shifts the back-anchored
# owner extraction onto an empty string without ever tripping the pipe-count
# malformed check (there are far more than 3 fields once the marker is
# absorbed, just mostly empty ones).
#
# Deliberately excludes a bare `=======` run: `<<<<<<<`/`|||||||`/`>>>>>>>`
# essentially never occur in legitimate prose, but 7 (or more) `=` characters
# is also valid Markdown Setext-heading-underline / plain-text-divider syntax
# — both live orphaned markers found in this ledger were `|||||||` shaped,
# never `=======` alone, so excluding it trades a theoretical detection gap
# (an orphaned `=======` with no `<<<<<<</>>>>>>>` siblings) for not punishing
# a much more plausible legitimate line. Cross-family review (2026-07-26)
# also found that this regex ALONE does not protect a marker-shaped example
# deliberately quoted inside a fenced code block (```` ``` ````) — see the
# fence-tracking in extract_open_entries, which is the actual defense for
# that case; a bare line-anchor here cannot distinguish "fenced" from "not".
CONFLICT_MARKER_RE = re.compile(r"^(?:<{7,}|\|{7,}|>{7,})")


@dataclass
class Entry:
    """One parsed open-ledger entry (after continuation-line concatenation)."""

    raw: str
    opened_date: Optional[date]
    artifact: str
    owner: str
    missing_step: str
    proof: str
    malformed: bool
    malformed_reasons: List[str] = field(default_factory=list)
    age_days: Optional[int] = None
    overdue: bool = False
    cls: str = CLASS_TECH_DEBT
    # Populated ONLY by annotate_pr_refs() (--check-pr-refs). Empty on every
    # entry otherwise, so the bucket property below never fires this branch
    # unless that opt-in check actually ran — the default path is unaffected.
    pr_refs: List[str] = field(default_factory=list)
    merged_pr_refs: List[str] = field(default_factory=list)

    @property
    def bucket(self) -> str:
        """Report/JSON grouping key: MALFORMED > PHANTOM-OPERATOR > PR-ALREADY-MERGED
        > FIREBREAK > NATURAL-WAIT > {cls}-OVERDUE > FRESH."""
        if self.cls == CLASS_MALFORMED:
            return CLASS_MALFORMED
        if self.cls == CLASS_PHANTOM_OPERATOR:
            # never FRESH: a phantom is wrong the moment it is written, not after 48h.
            return CLASS_PHANTOM_OPERATOR
        if self.merged_pr_refs:
            # Provably wrong RIGHT NOW (gh says the cited PR is already merged) —
            # ranked with MALFORMED/PHANTOM-OPERATOR rather than merely aged
            # debt, but below both: an unparseable/phantom ledger line is a
            # worse defect than a stale-but-well-formed one. Only ever
            # non-empty when --check-pr-refs ran annotate_pr_refs(); otherwise
            # dead code and behavior is unchanged (empty list by default).
            return CLASS_PR_ALREADY_MERGED
        if self.cls == CLASS_FIREBREAK:
            return CLASS_FIREBREAK
        if self.cls == CLASS_NATURAL_WAIT:
            # never -OVERDUE: the wait is on a declared calendar trigger, not on work
            return CLASS_NATURAL_WAIT
        if self.overdue:
            return f"{self.cls}-OVERDUE"
        return "FRESH"


def _safe_get(parts: Sequence[str], idx: int) -> str:
    try:
        return parts[idx].strip()
    except IndexError:
        return ""


def _split_pipe_fields(raw: str) -> List[str]:
    """Split a raw ledger line on top-level '|' separators, ignoring '|' inside
    backtick-quoted spans (shell commands, regex alternations).

    A naive raw.split("|") breaks the moment the free-text body quotes a shell pipe
    or a regex alternation in backticks — e.g. `launchctl list \\| grep -E
    "canva-(oauth|renderer|apply)"` — because every '|' inside that quoted span
    counts as a real field separator too. Falls back to a naive split when backticks
    are unbalanced (odd count): an unbalanced backtick means the source markdown
    itself is malformed in a way this heuristic cannot reason about, and treating the
    rest of the line as one giant quoted span would be a worse guess than the
    pre-existing naive behavior.
    """
    if raw.count("`") % 2 != 0:
        return raw.split("|")
    fields: List[str] = []
    current: List[str] = []
    in_backtick = False
    for ch in raw:
        if ch == "`":
            in_backtick = not in_backtick
            current.append(ch)
        elif ch == "|" and not in_backtick:
            fields.append("".join(current))
            current = []
        else:
            current.append(ch)
    fields.append("".join(current))
    return fields


def _strip_trailing_empty_fields(parts: Sequence[str]) -> List[str]:
    """Drop EMPTY trailing fields produced by a stray trailing '|' on the line.

    A ledger line ending in '... proof text |' splits into 6 fields whose last
    is '' — back-anchoring then reads proof='' and owner=<the real proof>,
    silently re-bucketing the entry (found live 2026-07-13: the 'secrets audit
    Pro enrichment' entry, whose owner operator[secret] landed in TECH-DEBT
    because the anchor shifted one slot left). Guarded by len > 5 so a
    well-formed 5-field entry whose PROOF is genuinely empty ('... | owner |')
    is never eaten — only surplus trailing residue is.
    """
    core = list(parts)
    while len(core) > 5 and not core[-1].strip():
        core.pop()
    return core


def _extract_missing_step(parts: Sequence[str]) -> str:
    """Best-effort recovery of the 'missing arming step' field.

    Well-formed entries have exactly 5 pipe-fields (date-prefix, artifact, missing
    step, owner, proof). If the free-text itself contains extra '|' characters the
    split grows past 5 — field[1] (artifact) and the last two fields (owner, proof)
    stay anchored from the outside in, so everything left in the middle belongs to
    the missing-arming-step description; rejoin it with '|' to restore it verbatim.
    """
    middle = parts[2:-2]
    if middle:
        return "|".join(p.strip() for p in middle).strip()
    return _safe_get(parts, 2)


# A session appends a progress note to a live entry by writing another
# '| **UPDATE ...**' segment after the proof field — a legitimate growth pattern
# found live in the real ledger (2026-07-11 audit). Back-anchoring owner/proof
# (parts[-2]/parts[-1]) gets this wrong the moment it fires: the anchor shifts onto
# the appended note instead of the real owner/proof. Detecting and stripping ONLY
# this specific, narrowly-recognizable trailing shape (rather than guessing that
# any >5-field entry grew at the tail) avoids mis-anchoring entries that instead
# grew a genuine EXTRA field in the MIDDLE (date/artifact/missing-step/[note]/owner/
# proof — found live too, 'codex-redteam MCP server' entry) where back-anchoring
# from the outside-in was already correct.
_TRAILING_UPDATE_NOTE_RE = re.compile(r"^\*\*\s*UPDATE", re.IGNORECASE)


def _split_trailing_update_notes(parts: Sequence[str]) -> tuple[List[str], List[str]]:
    """Peel off trailing '**UPDATE ...**' fields, returning (core, notes).

    Only pops from the end, and only while there are still enough fields left for
    the peeled result to remain a plausible >=4-field entry (date/artifact/owner/
    proof at minimum) — never eats into the fields a normal entry needs.
    """
    core = list(parts)
    notes: List[str] = []
    while len(core) > 4 and _TRAILING_UPDATE_NOTE_RE.match(core[-1].strip()):
        notes.insert(0, core.pop())
    return core, notes


# Owner/proof extraction by LABEL, not position — the fix for a live blind spot
# proven 2026-08-23 (v2-d12): `parts[-2]`/`parts[-1]` assumes owner and proof are
# the LAST two fields, true only for the canonical 5-field shape. A hand-added
# trailing field (most commonly `| source: <path>`, a provenance note appended
# after proof) shifts that anchor one slot — `owner` reads what is actually the
# PROOF text, `proof` reads the trailing extra field, and the real, explicitly
# `owner:`-labeled field sits unexamined, absorbed into `missing_step` by
# `_extract_missing_step`'s own `parts[2:-2]` recovery. Measured against the live
# ledger the day this was found: 34 of 396 open entries carry an `owner:` label
# that `parts[-2]` misses this way. Proven exploitable, not just untidy: a
# synthetic row shaped `... | owner: operator | proof: ... | source: ...` (a
# textbook bare-phantom, no category tag) parsed to `class: TECH-DEBT` and made
# `--strict-phantom` exit 0 on a scratch copy of the real ledger — the classifier
# never saw the word "operator" in the field it thought was `owner`, because that
# field was actually the proof text. A label match is unambiguous wherever it
# fires (a field starting with `owner:` unambiguously IS the owner, regardless of
# position), so it is tried FIRST; position is the fallback only when no label is
# present anywhere — which is still most of the ledger's canonical unlabeled
# 5-field entries (`me`, `operator[secret]`, no label at all) and must keep
# resolving exactly as before.
_LABEL_PATTERNS = {
    "owner": re.compile(r"^\s*[`\"'*_]*\s*owner\s*:\s*", re.IGNORECASE),
    "proof-of-armed": re.compile(r"^\s*[`\"'*_]*\s*proof-of-armed\s*:\s*", re.IGNORECASE),
    "proof": re.compile(r"^\s*[`\"'*_]*\s*proof\s*:\s*", re.IGNORECASE),
}


def _find_labeled_fields(parts: Sequence[str], label: str) -> List[tuple[int, str]]:
    """Return every (index, stripped-value-after-label) pair among `parts` whose
    text starts with `<label>:` (case-insensitive, tolerant of surrounding
    markdown emphasis/backtick markup), in file order. Returns ALL matches, not
    just the first: a live ledger pattern (confirmed against 2 real entries,
    #128/"77 phantom KBLI codes" and #263/"queue_rearm.sh scheduling") is a
    session appending a restated `owner: ... | proof: ...` pair AFTER a `**UPDATE
    ...**`-style progress note, when the update narrows or reassigns scope rather
    than just adding commentary — a second full pair, not just the trailing-note
    shape `_split_trailing_update_notes` already handles. The caller takes the
    LAST hit as current (same "latest restatement wins" reading a human gives the
    line, and the same philosophy trailing UPDATE notes already use) — never the
    first, and never flags multiple hits as an error: every multi-hit case found
    in the real corpus was this legitimate growth pattern, not corruption.
    """
    pattern = _LABEL_PATTERNS[label]
    hits: List[tuple[int, str]] = []
    for idx, p in enumerate(parts):
        stripped = p.strip()
        m = pattern.match(stripped)
        if m:
            hits.append((idx, stripped[m.end() :].strip()))
    return hits


def _truncate(text: str, limit: int = 120) -> str:
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip() + "…"


def extract_open_entries(ledger_text: str) -> List[str]:
    """Return the raw (continuation-concatenated) text of every open-ledger entry.

    The WHOLE file is scanned — no positional cutoff at a '## closed' heading. An
    entry starts at a line matching ENTRY_START_RE ('- opened ' or '- open '
    immediately followed by a YYYY-MM-DD date; both verb forms are accepted, and the
    date anchor keeps unrelated '- open ...' prose from being mistaken for a ledger
    entry). '- closed ' lines (proof-of-armed history) never match that prefix, so
    they're excluded wherever they live — no section boundary needed to keep them
    out. Any line following an entry-start that is non-blank, doesn't start a new
    '- ' list item, isn't a heading/blockquote, and isn't a stray diff3 conflict
    marker (CONFLICT_MARKER_RE) is treated as a wrapped continuation and appended
    (space-joined) to the current entry. A blank line, a new '- ' item, a
    heading/blockquote line, or a conflict-marker line ends the current entry.
    A conflict-marker-shaped line between a ``` fence pair is exempt from ONLY
    the marker check (still absorbed as literal continuation content) so a
    marker deliberately quoted as an EXAMPLE inside a fenced code block is
    never mistaken for the real thing.

    A positional cutoff was tried and dropped 2026-07-11: it silently discarded 14
    real open-debt lines that sessions had appended below the '## closed' heading
    (mixed in with genuine closed history) — verified as the same under-match
    disease (family #3) as the 'opened' vs 'open' spelling drift this same fix
    addresses, just expressed structurally instead of lexically.
    """
    lines = ledger_text.splitlines()

    entries: List[str] = []
    current: Optional[str] = None

    def finalize() -> None:
        nonlocal current
        if current is not None:
            entries.append(current)
        current = None

    in_fence = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            # Fall through (no `continue`): a fence delimiter line itself is
            # inert under every OTHER check (not an entry-start, not a real
            # list item, not blank, not a heading/blockquote, not a conflict
            # marker), so the normal chain below absorbs it correctly either
            # way — only the marker check needs the in_fence exemption.
        if in_fence and CONFLICT_MARKER_RE.match(stripped):
            # Exempt ONLY the marker check while fenced (found live by
            # cross-family review, 2026-07-26: a `|||||||` example
            # deliberately quoted inside a ``` fence to ILLUSTRATE a marker
            # was itself mistaken for a real one, truncating the entry).
            # Deliberately narrower than exempting ALL structure while
            # in_fence (an earlier draft did that and was itself flagged,
            # same review round, second pass): an unclosed/mismatched fence
            # — e.g. a stray lone ``` line, or an odd total count anywhere
            # below it in the file — would then silently swallow every
            # subsequent line, including every future real entry, until EOF,
            # with zero MALFORMED signal (--strict-phantom stays green while
            # the rest of the ledger vanishes from the parse — the exact
            # "stored green nobody re-derived" disease this whole gate exists
            # to catch). This narrower exemption degrades safely instead: if
            # a fence never closes, entry/list/blank/heading detection keeps
            # working for the rest of the file regardless, and the only
            # residual risk is a genuine orphaned marker after the accidental
            # open going uncaught until EOF — the same class of accepted,
            # documented trade-off as the dropped bare `=======` shape and
            # the known 4-field-missing-owner gap above. Residual, NOT fixed
            # here (all narrow, all degrade safely, none reproducible in the
            # real corpus today — zero fences of ANY kind currently exist in
            # this ledger): `~~~`-style fences are not recognized; a fence
            # opened with N backticks is "closed" by ANY run of >=3 backticks
            # regardless of exact length (a shorter nested example inside a
            # longer outer fence would prematurely re-expose content); and a
            # 4-space-indented code block (no backticks) is not recognized at
            # all, since `strip()` removes the indentation before this check
            # ever sees it.
            if current is not None:
                current = f"{current} {stripped}"
            continue
        if ENTRY_START_RE.match(stripped):
            finalize()
            current = stripped
        elif stripped.startswith("- "):
            # some other list item (not a ledger entry) — ends any entry in progress,
            # is not itself collected.
            finalize()
        elif stripped == "":
            finalize()
        elif CONFLICT_MARKER_RE.match(stripped):
            # Checked BEFORE the blockquote branch below: a `>>>>>>>` marker
            # also starts with '>' and would otherwise be silently dropped
            # by that check first (found live by this fix's own test corpus
            # — the other two marker shapes don't start with '>' or '#'
            # so they never hit that branch, which is exactly the kind of
            # asymmetric coverage a guard-conformance corpus exists to catch).
            # See CONFLICT_MARKER_RE docstring-comment: never absorb a stray
            # diff3 marker into the entry in progress — finalize() first, so
            # whatever entry was being built is protected from corruption.
            # The marker line itself is then collected as its OWN raw entry
            # (rather than silently dropped): it has no 'opened YYYY-MM-DD'
            # date, so parse_entry's existing malformed-reasons path surfaces
            # it in the MALFORMED section instead of it vanishing without a
            # trace. A stray marker in a committed ledger is a hygiene defect
            # worth seeing even on a tick it doesn't happen to corrupt an
            # owner field.
            finalize()
            entries.append(stripped)
        elif stripped.startswith("#") or stripped.startswith(">"):
            finalize()
        else:
            if current is not None:
                current = f"{current} {stripped}"

    finalize()
    return entries


def parse_entry(raw: str, now: date) -> Entry:
    """Parse one raw entry string into a structured, never-crashing Entry."""
    reasons: List[str] = []

    date_match = OPENED_RE.search(raw)
    opened_dt: Optional[date] = None
    if date_match:
        opened_dt = datetime.strptime(date_match.group(1), "%Y-%m-%d").date()
    else:
        reasons.append("no 'opened YYYY-MM-DD' date found")

    all_parts = _strip_trailing_empty_fields(_split_pipe_fields(raw))
    if len(all_parts) < 3:
        reasons.append(f"only {len(all_parts)} pipe-segment(s) (need >= 3)")
    # NOTE (considered and REJECTED, 2026-07-26): cross-family review flagged
    # that a 4-field entry omitting the owner segment entirely (`| artifact |
    # missing step | proof`, no separate owner field) back-anchors the
    # missing_step TEXT into owner instead of being caught. Raising this
    # floor to `< 5` (canonical field count) WOULD catch that shape — but
    # measured against the real ledger, 45 of 225 open entries (20%) are a
    # DIFFERENT, legitimate 4-field shape (artifact + owner + proof, no
    # separate missing_step — mostly FIREBREAK-style entries where the
    # artifact description already explains why nothing is "missing"), and
    # every one of those has a correctly-extracted, real owner. A `< 5` floor
    # would have flagged all 45 as MALFORMED, which is a far worse regression
    # for a gate whose entire purpose is "pre-existing legitimate debt never
    # blocks an innocent PR" than the narrower gap it would have closed. The
    # remaining gap (an entry that omits ONLY the owner field while keeping
    # a real missing_step) is real but unobserved in the actual corpus so
    # far, and is left to the owner-emptiness backstop below, which does not
    # share this false-positive problem because it only fires on a truly
    # EMPTY owner string, never a wrongly-populated-but-nonempty one.

    parts, trailing_notes = _split_trailing_update_notes(all_parts)

    artifact = _safe_get(parts, 1)

    # Label-anchored extraction FIRST (see _find_labeled_fields docstring for why):
    # a field starting with `owner:`/`proof:`/`proof-of-armed:` unambiguously IS
    # that field, wherever it sits. Position is the fallback only when no label
    # exists anywhere in the entry — the canonical unlabeled 5-field shape.
    owner_hits = _find_labeled_fields(parts, "owner")
    proof_hits = _find_labeled_fields(parts, "proof-of-armed") or _find_labeled_fields(parts, "proof")

    owner_idx: Optional[int] = None
    if owner_hits:
        owner_idx, owner = owner_hits[-1]
    else:
        owner = _safe_get(parts, -2)

    proof_idx: Optional[int] = None
    if proof_hits:
        proof_idx, proof_core = proof_hits[-1]
    else:
        proof_core = _safe_get(parts, -1)

    if owner_idx is not None or proof_idx is not None:
        # At least one field was label-anchored — missing_step is everything
        # between artifact and the FIRST anchored field, not the fixed
        # `parts[2:-2]` outside-in guess (which assumes owner/proof are the
        # last two fields, false once a label anchors one of them elsewhere).
        anchor = min(x for x in (owner_idx, proof_idx) if x is not None)
        middle = parts[2:anchor]
        missing_step = "|".join(p.strip() for p in middle).strip() if middle else _safe_get(parts, 2)
    else:
        missing_step = _extract_missing_step(parts)

    proof = "|".join([proof_core, *trailing_notes]).strip() if trailing_notes else proof_core

    if date_match and len(all_parts) >= 3 and not owner:
        # An unparseable/blank owner is NOT a lesser problem than a phantom
        # operator — it means the ledger cannot say who owns this debt at
        # all, e.g. corruption from an absorbed stray line (a `|||||||`
        # conflict marker injects 7 pipes, which back-anchoring reads as an
        # empty owner without ever tripping the pipe-count check above,
        # since the field COUNT is still >= 3, just mostly empty ones).
        # Surface it as MALFORMED — "owner=?" must never quietly resolve to
        # ordinary TECH-DEBT. Guarded on the two prior reasons already being
        # absent so this doesn't relabel an already-malformed line's reason.
        # Safe against false positives (unlike a blanket field-count floor,
        # considered and rejected above): this only fires on a genuinely
        # EMPTY owner string, never on a wrongly-populated-but-nonempty one,
        # so it does not collide with the real ledger's legitimate 4-field
        # shape (verified: 45/225 real entries, all with real, nonempty,
        # correctly-extracted owners).
        reasons.append("owner field is empty after parsing (unparseable/corrupted owner)")

    # Strong-signal owner-corruption backstop for the entries a LABEL cannot
    # rescue (no `owner:` label exists anywhere to correct the position-based
    # fallback) — 2 of 36 audited live cases had none. Deliberately narrow:
    # only two unambiguous tells, never a loose "doesn't start with
    # me/operator/session" shape check. That looser check has real false
    # positives in this corpus — a legitimately-phrased owner like "next
    # war-room-lane session" starts with neither token and is not corrupt; a
    # shape check flags it anyway. These two tells fire only on content that
    # cannot legitimately BE an owner under any phrasing: text explicitly
    # re-labeled as proof (an anchor collision, not a phrasing choice), or an
    # exact bare status word lifted from elsewhere in the entry.
    #
    # Exempted for FIREBREAK-classified entries (`"firebreak" in raw.lower()`,
    # checked the same way `cls` itself is decided below): a FIREBREAK is
    # informational-only by design (never alarmed, never blocks a merge) — the
    # entire point of this backstop is to stop an owner-shape defect from
    # silently hiding a live CI risk, and a firebreak entry carries no such
    # risk regardless of how its owner field reads. Found live 2026-08-23: the
    # unguarded version of this check newly flagged a real, pre-existing,
    # harmless FIREBREAK row (`INTERACTIVE-DEFAULT RULING`, owner text reduced
    # to the stray word "closed" by its own closure prose) as MALFORMED —
    # which fails `--strict-phantom` unconditionally, so shipping this fix
    # without the exemption would have gone CI-red on the real, UNCHANGED
    # ledger. The fix is for the READER, not a mandate to also correct every
    # row's prose in the same PR (see this fix's own PR description).
    if date_match and len(all_parts) >= 3 and owner and "firebreak" not in raw.lower():
        if _LABEL_PATTERNS["proof-of-armed"].match(owner) or _LABEL_PATTERNS["proof"].match(owner):
            reasons.append("owner field holds text labeled proof:/proof-of-armed: — anchor collision")
        elif owner.strip().rstrip(".").lower() in {"closed", "tech-debt"}:
            reasons.append(f"owner field is a bare status word ({owner.strip()!r}), not an owner")

    age_days: Optional[int] = None
    overdue = False
    if opened_dt is not None:
        age_days = (now - opened_dt).days
        overdue = age_days >= OVERDUE_AGE_DAYS

    malformed = bool(reasons)
    if malformed:
        cls = CLASS_MALFORMED
    elif "firebreak" in raw.lower():
        cls = CLASS_FIREBREAK
    elif NATURAL_WAIT_RE.search(owner):
        # owner-field only: "passivo" in the free-text body (e.g. quoting a log)
        # must not reclassify a line whose owner is active.
        cls = CLASS_NATURAL_WAIT
    elif "operator" in owner.lower():
        # Owner claims an operator lane. Legitimate ONLY if every declared tag names a
        # true-operator category; untagged (or unknown-category) = PHANTOM-OPERATOR.
        tags = [m.group(1).lower() for m in OPERATOR_TAG_RE.finditer(owner)]
        if tags and all(t in TRUE_OPERATOR_CATEGORIES for t in tags):
            cls = CLASS_OPERATOR_GATED
        elif not tags and _all_operator_mentions_negated(owner):
            # No bracket tag at all AND EVERY naked "operator" mention is
            # inside a "not [hedge-words] operator" disclaimer — this is
            # prose DENYING an operator-lane claim, not making one. Full
            # coverage, not mere existence: see _all_operator_mentions_negated's
            # own docstring for why a bare .search() here was itself a gap.
            cls = CLASS_TECH_DEBT
        else:
            cls = CLASS_PHANTOM_OPERATOR
    else:
        cls = CLASS_TECH_DEBT

    return Entry(
        raw=raw,
        opened_date=opened_dt,
        artifact=artifact,
        owner=owner,
        missing_step=missing_step,
        proof=proof,
        malformed=malformed,
        malformed_reasons=reasons,
        age_days=age_days,
        overdue=overdue,
        cls=cls,
    )


def _git(argv: List[str], *, cwd: Path, timeout: int = 15) -> tuple[int, str, str]:
    """Run a read-only git command. Returns (rc, stdout, stderr), never raises.

    A spawn failure is reported as a non-zero rc with the reason in stderr, so
    every caller decides on the same three values and none of them has to
    remember that "no output" might mean "git is missing".
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), *argv], capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError:
        return 127, "", "git not on PATH"
    except (subprocess.SubprocessError, OSError) as exc:
        return 1, "", f"git invocation failed: {type(exc).__name__}"
    return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()


class LedgerRefUnreadable(RuntimeError):
    """`--ref` was given and could not be honoured.

    Deliberately fatal rather than a fallback. Silently reading the working
    tree after being asked for a ref is the worst possible outcome: the caller
    believes it is looking at main and is looking at its own stale checkout —
    the same class of lie the ref option exists to end.
    """


def _ledger_text_at_ref(ledger_path: Path, ref: str) -> str:
    """Read the ledger as of `ref`, without touching the working tree.

    Read-only by construction: `git show` writes nothing, changes no branch and
    fetches nothing. `origin/main` is therefore only as fresh as the last fetch
    — stated in the freshness line rather than papered over with a fetch, so
    this stays a pure signaler (offline is a natural state, Law 6).
    """
    repo = ledger_path.parent
    rc, top, err = _git(["rev-parse", "--show-toplevel"], cwd=repo)
    if rc != 0:
        raise LedgerRefUnreadable(f"not a git repository at {repo}: {err or f'git exited {rc}'}")
    try:
        rel = ledger_path.resolve().relative_to(Path(top).resolve())
    except ValueError as exc:  # ledger outside the repo — nothing to resolve against
        raise LedgerRefUnreadable(f"{ledger_path} is not inside {top}") from exc
    rc, out, err = _git(["show", f"{ref}:{rel.as_posix()}"], cwd=repo)
    if rc != 0:
        raise LedgerRefUnreadable(f"cannot read {rel.as_posix()} at {ref!r}: {err or f'git exited {rc}'}")
    if not out.strip():
        # Empty is not a ledger. Zero entries is a claim, and a claim this tool
        # must not make on the strength of an empty read.
        raise LedgerRefUnreadable(f"{rel.as_posix()} at {ref!r} is empty")
    return out


def load_entries(ledger_path: Path, now: date, ref: Optional[str] = None) -> List[Entry]:
    text = _ledger_text_at_ref(ledger_path, ref) if ref else ledger_path.read_text(encoding="utf-8")
    return [parse_entry(raw, now) for raw in extract_open_entries(text)]


# -----------------------------------------------------------------------------
# PR-ALREADY-MERGED (megatopics-1-5 action plan #1, added 2026-08-03) — OPT-IN,
# only ever exercised behind --check-pr-refs. See the module docstring's
# "PR-ALREADY-MERGED rule" for the full rationale.
# -----------------------------------------------------------------------------

# Requires a literal `PR` immediately before the hash — a bare `#NNN` in this
# ledger is frequently NOT a pull request (measured live 2026-08-03: CodeQL
# alert numbers cited next to a file:line list, e.g. "telegram_webhook.py:147
# (#6860, #2837, #2836)" — none of those are PRs). `PR\s*#` anchors on the
# entity a reader would call a PR, not on the digit shape. 3-5 digits with a
# trailing word-boundary so a longer digit run fails to match rather than
# silently truncating to its first 5 digits and citing the wrong PR.
PR_REF_RE = re.compile(r"\bPR\s*#(\d{3,5})\b", re.IGNORECASE)


def extract_pr_refs(entry: Entry) -> List[str]:
    """`PR #123`-style references cited in an entry's artifact/missing_step/proof.

    Order-preserving, deduplicated across all three fields. Even with the `PR`
    anchor this is a noisy signal on this ledger — see the module docstring's
    PR-ALREADY-MERGED rule for the measured false-positive rate before trusting
    a hit here as anything more than a candidate for a human to skim.
    """
    seen: Dict[str, None] = {}
    for text in (entry.artifact, entry.missing_step, entry.proof):
        for m in PR_REF_RE.finditer(text or ""):
            seen.setdefault(m.group(1), None)
    return list(seen.keys())


def _check_pr_merged(pr_number: str) -> Dict[str, Any]:
    """Best-effort `gh pr view <n> --json state,mergedAt`. Never raises.

    Returns {"checked": bool, "merged": bool, "detail": str}. "checked" False
    means the call could not be trusted (gh missing, timeout, non-zero exit,
    unparseable JSON) — the caller must NEVER treat that as "merged" (same
    "judge the reply, never assume success" discipline as _ledger_freshness,
    W104: a bare non-crash is not proof of anything either way).
    """
    try:
        proc = subprocess.run(
            ["gh", "pr", "view", pr_number, "--json", "state,mergedAt"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except FileNotFoundError:
        return {"checked": False, "merged": False, "detail": "gh not on PATH"}
    except (subprocess.SubprocessError, OSError) as exc:
        return {
            "checked": False,
            "merged": False,
            "detail": f"gh invocation failed: {type(exc).__name__}",
        }

    if proc.returncode != 0:
        reason = (proc.stderr or "").strip().splitlines()
        return {
            "checked": False,
            "merged": False,
            "detail": reason[-1] if reason else f"gh exited {proc.returncode}",
        }

    try:
        payload = json.loads(proc.stdout or "")
    except json.JSONDecodeError:
        return {"checked": False, "merged": False, "detail": "unparseable gh output"}

    if not isinstance(payload, dict):
        return {"checked": False, "merged": False, "detail": "unexpected gh payload shape"}

    state = payload.get("state")
    return {"checked": True, "merged": state == "MERGED", "detail": state or "unknown state"}


def annotate_pr_refs(
    entries: List[Entry],
    checker: Callable[[str], Dict[str, Any]] = _check_pr_merged,
) -> None:
    """Mutate each Entry in place: set .pr_refs and .merged_pr_refs.

    Only ever called from main() behind --check-pr-refs — never on the
    default path, so the rest of the report is unaffected unless this ran.
    An unverifiable ref (checker returns checked=False) is left OUT of
    merged_pr_refs — "cannot verify" is never silently "merged" (W104).
    Never touches the ledger file; this remains a pure signaler.
    """
    for entry in entries:
        refs = extract_pr_refs(entry)
        entry.pr_refs = refs
        merged: List[str] = []
        for ref in refs:
            result = checker(ref)
            if result.get("checked") and result.get("merged"):
                merged.append(ref)
        entry.merged_pr_refs = merged


def compute_counts(entries: List[Entry], check_pr_refs: bool = False) -> Dict[str, int]:
    buckets = [e.bucket for e in entries]
    counts = {
        "total": len(entries),
        "phantom_operator": buckets.count(CLASS_PHANTOM_OPERATOR),
        "tech_debt_overdue": buckets.count(f"{CLASS_TECH_DEBT}-OVERDUE"),
        "operator_gated_overdue": buckets.count(f"{CLASS_OPERATOR_GATED}-OVERDUE"),
        "firebreak": buckets.count(CLASS_FIREBREAK),
        "natural_wait": buckets.count(CLASS_NATURAL_WAIT),
        "fresh": buckets.count("FRESH"),
        "malformed": buckets.count(CLASS_MALFORMED),
    }
    if check_pr_refs:
        # Additive: only present when --check-pr-refs ran, so every default
        # (offline) call site's dict shape stays byte-for-byte unchanged —
        # required so the pre-existing exact-equality tests never break.
        counts["pr_already_merged"] = buckets.count(CLASS_PR_ALREADY_MERGED)
    return counts


def _freshness_line(freshness: Optional[Dict[str, Any]], ref: Optional[str] = None) -> str:
    """One line, always printed. Silence about freshness is what made this necessary."""
    if not freshness:
        return "- ledger-freshness: not checked"
    state = freshness.get("state")
    detail = freshness.get("detail", "")
    if ref:
        # The rows below came from `ref`, so how far the WORKING TREE has fallen
        # behind cannot make them wrong. Still reported, because it is the number
        # a reader would otherwise have to go and measure.
        behind = freshness.get("behind")
        gap = (
            f"this checkout is {behind} commit(s) behind on this file"
            if isinstance(behind, int) and behind > 0
            else f"checkout gap {state}"
        )
        return (
            f"- ledger-freshness: read at `{ref}` — {gap}, which does NOT affect the rows "
            f"below (`{ref}` is itself only as fresh as your last fetch)"
        )
    if state == "stale":
        return f"- ⚠️ ledger-freshness: **STALE** — {detail}"
    if state == "current":
        return f"- ledger-freshness: current ({detail})"
    return f"- ledger-freshness: UNKNOWN — {detail} (could not check; this is not 'current')"


def render_report(
    ledger_path: Path,
    now: date,
    entries: List[Entry],
    freshness: Optional[Dict[str, Any]] = None,
    check_pr_refs: bool = False,
    ref: Optional[str] = None,
) -> str:
    counts = compute_counts(entries, check_pr_refs=check_pr_refs)
    lines: List[str] = []
    lines.append("# PENDING-ARMS reconciliation report")
    lines.append("")
    source = f"`{ledger_path}` @ `{ref}`" if ref else f"`{ledger_path}`"
    lines.append(f"- ledger: {source}")
    lines.append(_freshness_line(freshness, ref))
    lines.append(
        f"- now: {now.isoformat()} (day-precision dates; overdue = age_days >= "
        f"{OVERDUE_AGE_DAYS}, the closest day-precision proxy for >48h)"
    )
    summary = (
        "- counts: total={total} phantom_operator={phantom_operator} "
        "tech_debt_overdue={tech_debt_overdue} "
        "operator_gated_overdue={operator_gated_overdue} firebreak={firebreak} "
        "natural_wait={natural_wait} fresh={fresh} malformed={malformed}"
    ).format(**counts)
    if check_pr_refs:
        summary += " pr_already_merged={pr_already_merged}".format(**counts)
    lines.append(summary)
    lines.append("")

    def fmt_entry(e: Entry) -> str:
        opened = e.opened_date.isoformat() if e.opened_date else "?"
        age = e.age_days if e.age_days is not None else "?"
        return (
            f"- {e.artifact or '(no artifact parsed)'} "
            f"(opened {opened}, age {age}d, owner={e.owner or '?'}): "
            f"{_truncate(e.missing_step, 120)}"
        )

    def fmt_malformed(e: Entry) -> str:
        reasons = "; ".join(e.malformed_reasons) or "unknown parse failure"
        return f"- {_truncate(e.raw, 80)}  [reason: {reasons}]"

    def section(title: str, items: List[Entry], formatter) -> None:
        lines.append(f"## {title}")
        if not items:
            lines.append("none")
        else:
            for item in items:
                lines.append(formatter(item))
        lines.append("")

    by_bucket: Dict[str, List[Entry]] = {}
    for e in entries:
        by_bucket.setdefault(e.bucket, []).append(e)

    section(
        "PHANTOM-OPERATOR (owner claims an operator lane with no true-operator "
        "category — there is no operator: re-own to a session or tag operator[<cat>])",
        by_bucket.get(CLASS_PHANTOM_OPERATOR, []),
        fmt_entry,
    )
    if check_pr_refs:
        section(
            "PR-ALREADY-MERGED — LOW CONFIDENCE, SKIM ONLY (cites a `PR #N` that `gh` "
            "reports merged; measured live 2026-08-03 that most hits here are the entry "
            "already knowing and stating that, staying open for an unrelated reason — "
            "not proof of staleness, never gates --strict)",
            by_bucket.get(CLASS_PR_ALREADY_MERGED, []),
            fmt_entry,
        )
    section(
        "TECH-DEBT overdue (>48h)",
        by_bucket.get(f"{CLASS_TECH_DEBT}-OVERDUE", []),
        fmt_entry,
    )
    section(
        "OPERATOR-GATED overdue",
        by_bucket.get(f"{CLASS_OPERATOR_GATED}-OVERDUE", []),
        fmt_entry,
    )
    section(
        "FIREBREAK (legitimate, informational)",
        by_bucket.get(CLASS_FIREBREAK, []),
        fmt_entry,
    )
    section(
        "NATURAL-WAIT (armed; proof waits on a declared calendar trigger — never overdue)",
        by_bucket.get(CLASS_NATURAL_WAIT, []),
        fmt_entry,
    )
    section("Fresh (<48h)", by_bucket.get("FRESH", []), fmt_entry)
    section("MALFORMED", by_bucket.get(CLASS_MALFORMED, []), fmt_malformed)

    return "\n".join(lines).rstrip() + "\n"


def build_json(
    ledger_path: Path,
    now: date,
    entries: List[Entry],
    freshness: Optional[Dict[str, Any]] = None,
    check_pr_refs: bool = False,
) -> Dict[str, Any]:
    def _entry_dict(e: Entry) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "opened": e.opened_date.isoformat() if e.opened_date else None,
            "age_days": e.age_days,
            "artifact": e.artifact,
            "owner": e.owner,
            "class": e.cls,
            "overdue": e.overdue,
            "raw_head": e.raw[:80],
        }
        if check_pr_refs:
            # Additive-only: absent unless --check-pr-refs ran, so the default
            # entry schema stays byte-for-byte unchanged.
            d["pr_refs"] = e.pr_refs
            d["merged_pr_refs"] = e.merged_pr_refs
        return d

    return {
        "now": now.isoformat(),
        "ledger": str(ledger_path),
        "freshness": freshness if freshness is not None else {"state": "unknown", "behind": None, "detail": "not checked"},
        "counts": compute_counts(entries, check_pr_refs=check_pr_refs),
        "entries": [_entry_dict(e) for e in entries],
    }


def _default_ledger_path() -> Path:
    # scripts/pending_arms_report.py -> parent = scripts/, parent.parent = repo root.
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / ".claude" / "skills" / "modus" / "PENDING-ARMS.md"


# -----------------------------------------------------------------------------
# Ledger freshness — the reporter must not present a stale open-set as current
# -----------------------------------------------------------------------------
#
# WHY (2026-07-27, found by using this tool): a session ran this reporter inside
# a main checkout 64 commits behind origin/main and read out ~68 "open"
# operator-gated rows. Several had been CLOSED on main days earlier — the local
# ledger was 492 lines against main's 532. The report was internally correct and
# externally false: it answered honestly about a world that no longer existed.
# Nothing in the output hinted at this, because the reporter had no notion of
# git at all. Same shape as the seat-probe that answers for the invocation
# rather than the system, and as a GO criterion naming a tool nobody has.
#
# WHAT THIS IS *NOT*. This does not ask "has this content already landed on
# main" — that question demands a CONTENT check, never SHA reachability (W88,
# and W88 again at the second degree with three-dot diffs). The question here is
# strictly "does my checkout contain main's commits to this file", and for THAT
# question commit reachability is the exact semantics, not a proxy for it. The
# two questions look alike and have opposite correct answers; keep them apart.
#
# DIRECTION MATTERS. "Differs from origin/main" is the normal state of every PR
# branch that adds a ledger line — accusing those would be an over-match (#3)
# and would train readers to ignore the banner. Only a checkout MISSING main's
# commits is stale. A branch ahead of main reports `current`.
#
# FAIL-VISIBLE. A shallow CI clone has no `origin/main` ref, and a tarball is
# not a repo at all. Those report UNKNOWN with the reason, never `current`:
# a scan that could not look is not a clean scan (W84).


def _ledger_freshness(ledger_path: Path) -> Dict[str, Any]:
    """How many commits to THIS file does origin/main have that we do not?

    Returns {"state": current|stale|unknown, "behind": int|None, "detail": str}.
    Never raises: the reporter degrades to UNKNOWN rather than dying, because a
    freshness check that can take the report down is worse than no check.
    """
    unknown = lambda detail: {"state": "unknown", "behind": None, "detail": detail}
    try:
        proc = subprocess.run(
            [
                "git",
                "-C",
                str(ledger_path.parent),
                "rev-list",
                "--count",
                "HEAD..origin/main",
                "--",
                str(ledger_path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except FileNotFoundError:
        return unknown("git not on PATH")
    except (subprocess.SubprocessError, OSError) as exc:  # timeout, spawn failure
        return unknown(f"git invocation failed: {type(exc).__name__}")

    # Judge the REPLY, not the exit code (W104) — but here a non-zero rc carries
    # the only diagnosis we get (unknown revision, not a repository), so surface
    # it verbatim rather than collapsing it to a bare "unknown".
    if proc.returncode != 0:
        reason = (proc.stderr or "").strip().splitlines()
        return unknown(reason[-1] if reason else f"git exited {proc.returncode}")

    raw = (proc.stdout or "").strip()
    if not raw.isdigit():
        # An empty or unparseable count is NOT zero. Zero is a claim.
        return unknown(f"unparseable rev-list output {raw!r}")

    behind = int(raw)
    if behind == 0:
        return {"state": "current", "behind": 0, "detail": "origin/main has no newer commit to this file"}
    return {
        "state": "stale",
        "behind": behind,
        "detail": (
            f"origin/main has {behind} commit(s) to this ledger that this checkout lacks — "
            "rows shown as open may already be closed on main. Re-run with `--ref origin/main` "
            "to read main's ledger: read-only, no pull and no write, so it works from the main "
            "checkout too, where a session is (correctly) forbidden to mutate git. "
            "(origin/main is itself only as fresh as your last fetch.)"
        ),
    }


def _parse_now(value: Optional[str]) -> date:
    if value is None:
        return date.today()
    return datetime.strptime(value, "%Y-%m-%d").date()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pending_arms_report.py",
        description=(
            "Reconciliation report over the W81 PENDING-ARMS ledger: alarms on "
            "built-but-not-armed TECH-DEBT entries overdue >48h, separates "
            "legitimate firebreaks. Pure signaler — never writes anything."
        ),
    )
    parser.add_argument(
        "--ledger",
        type=Path,
        default=None,
        help="Path to PENDING-ARMS.md (default: <repo-root>/.claude/skills/modus/PENDING-ARMS.md)",
    )
    parser.add_argument(
        "--ref",
        type=str,
        default=None,
        metavar="GITREF",
        help=(
            "Read the ledger as of a git ref (e.g. origin/main) instead of the working "
            "tree. Read-only: no pull, no fetch, no write — the way to see main's ledger "
            "from a checkout that is behind. Fatal if the ref cannot be read; it never "
            "falls back to the working tree."
        ),
    )
    parser.add_argument(
        "--now",
        type=str,
        default=None,
        help="Override 'today' as YYYY-MM-DD, for deterministic runs/tests.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of the markdown report.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Exit 1 iff >=1 overdue TECH-DEBT entry OR >=1 PHANTOM-OPERATOR entry "
            "OR >=1 MALFORMED entry exists (otherwise always exit 0)."
        ),
    )
    parser.add_argument(
        "--strict-phantom",
        action="store_true",
        help=(
            "Exit 1 iff >=1 PHANTOM-OPERATOR entry OR >=1 MALFORMED entry exists "
            "— the narrow CI ledger gate: blocks writing new phantom-operator "
            "lines (or corrupting an existing entry's owner into something "
            "unparseable, e.g. an absorbed stray conflict-marker line — an "
            "unparseable owner is at least as untrustworthy as a phantom one) "
            "without turning pre-existing overdue tech-debt into a red check "
            "for innocent PRs."
        ),
    )
    parser.add_argument(
        "--check-pr-refs",
        action="store_true",
        help=(
            "Extract 'PR #NNN' references from every open entry's artifact/"
            "missing_step/proof and check via `gh pr view` whether each is "
            "already merged (network + gh auth required — best-effort, off by "
            "default so the suite runs offline). Flags a PR-ALREADY-MERGED "
            "bucket, LOW CONFIDENCE — measured live on this ledger's own prose, "
            "most hits cite a merged PR as historical context, not a live "
            "blocker; skim it, don't trust it, never gates --strict. Never "
            "mutates the ledger."
        ),
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    ledger_path: Path = args.ledger if args.ledger is not None else _default_ledger_path()

    if not ledger_path.exists():
        print(
            f"pending_arms_report: ledger not found: {ledger_path}",
            file=sys.stderr,
        )
        return 2

    try:
        now = _parse_now(args.now)
    except ValueError:
        print(
            f"pending_arms_report: invalid --now value {args.now!r}, expected YYYY-MM-DD",
            file=sys.stderr,
        )
        return 2

    try:
        entries = load_entries(ledger_path, now, ref=args.ref)
    except LedgerRefUnreadable as exc:
        # Fail loud. A caller who asked for a ref and silently got the working
        # tree would draw conclusions about main from its own stale checkout.
        print(f"pending_arms_report: --ref {args.ref!r} unreadable: {exc}", file=sys.stderr)
        return 2
    if args.check_pr_refs:
        annotate_pr_refs(entries)
    freshness = _ledger_freshness(ledger_path)

    if args.json:
        print(
            json.dumps(
                build_json(ledger_path, now, entries, freshness, check_pr_refs=args.check_pr_refs),
                indent=2,
            )
        )
    else:
        print(
            render_report(ledger_path, now, entries, freshness, check_pr_refs=args.check_pr_refs, ref=args.ref),
            end="",
        )

    has_phantom = any(e.cls == CLASS_PHANTOM_OPERATOR for e in entries)
    # --strict is the "I am about to rely on this verdict" mode, so a ledger that
    # is provably missing main's closures makes the verdict meaningless and must
    # fail. --strict-phantom is the CI ledger gate and is deliberately NOT wired
    # to freshness: CI checks out a shallow merge ref with no `origin/main`, so
    # every innocent PR would report UNKNOWN, and a gate that reddens on "could
    # not check" teaches everyone to ignore it.
    if args.strict and freshness.get("state") == "stale":
        return 1
    has_malformed = any(e.cls == CLASS_MALFORMED for e in entries)
    if args.strict and (
        has_phantom
        or has_malformed
        or any(e.cls == CLASS_TECH_DEBT and e.overdue for e in entries)
    ):
        return 1
    if args.strict_phantom and (has_phantom or has_malformed):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
