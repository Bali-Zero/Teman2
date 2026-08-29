#!/usr/bin/env python3
"""council_yield_report.py — per-family/per-role yield report over evidence
pack dissent blocks (L03-PR-3 of the beyond-SOTA craft wave, squad E).

WHAT THIS IS: a report over the `dissent:` blocks 53 of 54 evidence packs
already carry (267 findings, 2026-08-29 measurement). It answers: which
*families* of seat actually change designs (CONFIRMED — the objection stuck
and the design moved), which sit in the RETRACTED bin (raised and refuted),
which land in PLAUSIBLE limbo (neither), and — critically — which *role*
each seat played (an actual cross-family review, a self-check on the same
session's own work, or a deterministic CI/harness re-derivation). Pooling
those three roles into one "council yield" number is precisely the report
this PR exists to prevent: see the HONEST LIMIT note below and printed by
this script every run.

WHY `council_yield:` AND NOT `council:` AS THE PACK KEY (AMENDMENT 0 of the
implementer brief, `SQUAD-LEDGER.md` line ~335): `scripts/evidence_pack_lint.py`
already reads a truthy `pack.get("council")` as the R11-CEILING rule's
override signal. A structured, possibly-empty `council: {}` block for THIS
report would either read as R11's trigger (hard violation on a Gear-1-shaped
pack that legitimately ran a council) or, if empty, read as clean while a
POPULATED one convicts — two readers disagreeing about one key, superscar
#9 ("un nome, due ruoli"). `council_yield:` is a new, disjoint key: this
script never touches `evidence_pack_lint.py`, and no new `check_*` rule is
required for it.

READING ORDER (per the implementer brief):
  1. PRIMARY — every `evidence/**/pack.yml` under the repo root (default,
     auto-discovered), read for its `dissent:` list (already-structured
     YAML — this is where all 267 measured findings live) and its optional
     `council_yield:` override block (see OVERRIDE SCHEMA below).
  2. FALLBACK — markdown `## Adversarial review` sections, ONLY when a
     `.md` file is explicitly named via `--paths` (never auto-discovered:
     "## Adversarial review" appears in ~3,173 files repo-wide, and sweeping
     them would be exactly the over-reach `--paths` exists to prevent). Only
     a fallback doc whose "## Adversarial review" section contains an actual
     markdown table with `Seat` and `Disposition` columns is parseable by
     this tool; a doc that states its tally in prose only (two of the three
     2026-08-28 dossiers this brief points at) is honestly reported as
     `unparseable`, never guessed at — this tool does not synthesize
     structured data out of narrative prose.

OVERRIDE SCHEMA (`council_yield:`, optional, additive, absent in all 54
packs measured 2026-08-29 — every code path below that reads it is
exercised only by this file's own test fixtures):

    council_yield:
      seats:                     # optional — a dissent-shaped mini-list;
        - seat: kimi-k3           # when present, findings/applied/rejected/
          status: CONFIRMED       # plausible below are DERIVED from it and
        - seat: codex-gpt-5.6-sol  # each seat is family/role-normalised
          status: RETRACTED        # exactly like a `dissent:` item, so the
      findings: 2                 # per-family matrix stays meaningful even
      applied: 1                  # for an overridden pack. Absent `seats:`
      rejected: 1                 # falls back to the four scalar counts
      plausible: 0                # below (pack-level totals only; that
      est_tokens: 4000            # pack's contribution to the family x role
                                   # matrix is then `unattributed`, because
                                   # there is no seat string to normalise).

Presence of `council_yield:` on a pack OVERRIDES that pack's dissent-derived
counts for TOTALS purposes (per the brief: "absence means derive from
dissent"). `est_tokens`, if present, is purely informational and surfaces
only in `--json` output.

CLI: `council_yield_report.py [--json] [--paths PATH ...]`. Exit 0 always —
this is a REPORT, never a gate. A pack (or fallback doc) this tool cannot
parse is named in the output as `unparseable`, never silently skipped.
`--paths` is ADDITIVE to the default `evidence/**/pack.yml` auto-discovery
(a directory is recursed for `pack.yml`; a `.md` file is fallback-parsed;
anything else ending `pack.yml`/`.yml`/`.yaml` is read as a single pack) —
naming one fallback doc does not silently drop the primary corpus.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover — exercised only in a yaml-less env
    yaml = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# DECISION 1 — family normalisation, word/token-boundary matched, DECLARED
# PRECEDENCE ORDER (first match in this list wins; a synthetic two-family
# string is pinned by test_precedence_order_is_deterministic). Every alias
# is matched with `\b...\b` against the raw seat string — never a bare
# substring — so "opus" cannot bind inside an unrelated word and, per the
# over-match twin the brief names explicitly, there is deliberately NO bare
# "gpt" alias (only version-qualified "gpt-5.6"/"gpt5.6"): prose that merely
# *mentions* GPT without a version number never binds to this family.
# "codex-gpt-5.6-sol" is ONE seat (decision 1, verbatim) — both its aliases
# resolve to the SAME family entry, so which alias fires is irrelevant.
# ---------------------------------------------------------------------------
UNATTRIBUTED = "unattributed"

FAMILY_PRECEDENCE: list[tuple[str, tuple[str, ...]]] = [
    ("kimi", ("kimi",)),
    ("codex-gpt-5.6", ("codex", "gpt-5.6", "gpt5.6")),
    ("gemini", ("gemini", "agy")),
    ("opus", ("opus",)),
    ("sonnet", ("sonnet",)),
]


def _binds(text: str, token: str) -> bool:
    """True iff `token` appears in `text` on a word boundary (case-insensitive).

    `\\b` anchors on a transition between a word char (`[A-Za-z0-9_]`) and a
    non-word char (or start/end of string) — it does not care what sits
    *between* the anchors, so a token containing internal punctuation
    (`gpt-5.6`) still anchors correctly at its own first/last letter-or-digit.
    """
    pattern = r"\b" + re.escape(token) + r"\b"
    return re.search(pattern, text, re.IGNORECASE) is not None


def normalize_family(raw_seat: str) -> str:
    """Resolve a raw `seat:` string to a family, or `unattributed` if no
    declared family token binds. First match in FAMILY_PRECEDENCE wins."""
    for family, aliases in FAMILY_PRECEDENCE:
        if any(_binds(raw_seat, alias) for alias in aliases):
            return family
    return UNATTRIBUTED


# ---------------------------------------------------------------------------
# DECISION 2 (as narrowed by AMENDMENT 2) — role is ORTHOGONAL to family.
# Three buckets, checked in this order (self before gate: a string can in
# principle carry both a self marker and the bare word "gate" — e.g. the
# real corpus seat "session (gate, on its own diff)" — and self must win
# there, because "gate" alone is NOT one of the amendment's gate triggers).
#
# self  : "self", "own diff", "its own", "this session", "against its own",
#         OR the seat string's leading token is bare "session". The leading-
#         token form (not "session anywhere") is what keeps this from
#         over-matching "the session's own refuter" — there "session" is
#         the possessive's SUBJECT further into the sentence, not the seat
#         announcing itself; that string correctly falls through to review.
# gate  : "harness", "github actions", "ci", "floor recompute" — CI/harness
#         determinism, never an LLM's own adjudication (the real corpus has
#         seats literally named "... on-disk gate ..." that must NOT land
#         here — "gate" alone is deliberately not a trigger for this bucket).
# review: everything else — a real cross-family seat AND an unattributed one
#         both land here by default; DECISION 3 keeps family and role
#         orthogonal, so "review, but we don't know whose family" is exactly
#         the honest thing to report, not a contradiction.
# ---------------------------------------------------------------------------
ROLE_SELF = "self"
ROLE_GATE = "gate"
ROLE_REVIEW = "review"

_SELF_LEADING_TOKEN = re.compile(r"^\s*session\b", re.IGNORECASE)
# The self-signal must describe the SEAT, not the work the seat reviewed.
# Blind review found the over-match: "kimi-k3 on opus's own diff" is a KIMI
# seat reviewing an opus diff — the cross-family case this report exists to
# measure — and it was being filed as `self`; likewise "sonnet reviewing
# codex, this session was clean". Both phrases described the SUBJECT.
# `\bagainst its own\b` was also dead, fully subsumed by `\bits own\b`.
# The under-match twin is guarded by test: a leading `session ...` and a
# plain `self-refutation` must still classify as `self`.
#: STRONG self-signals: they name the seat's relationship to the diff
#: outright, so they decide regardless of which family the seat belongs to
#: ("sonnet-5 (self, bite-proof)" is self even though its family is sonnet).
_SELF_PATTERNS = [
    r"\bself\b",
    r"\bits own\b",
    r"\bown diff\b",
]
#: WEAK self-signal, and the distinction is measured rather than guessed.
#: "this session" is TEMPORAL, not an identity, and the live corpus uses it
#: both ways: `kimi-code/k3 (cross-family adversarial review, this session)`
#: is a KIMI seat that merely says WHEN — filing it as `self` deleted four
#: genuine cross-family findings from council yield — while `this session,
#: independent gate re-run ...` names no family at all and IS the session
#: speaking. So it decides only when nothing else identifies the seat.
#: (`\bagainst its own\b` was dropped as dead: fully subsumed by
#: `\bits own\b`. Dropping `\bthis session\b` outright, which the first cut of
#: this cure did by accident, reclassified both genuine self-refutations as
#: `review` — the under-match twin, caught by the live-corpus diff.)
_WEAK_SELF_PATTERNS = [
    r"\bthis session\b",
]
#: Phrases that name the reviewed WORK rather than the reviewing seat. When one
#: of these is present the `own diff` / `this session` signal is not evidence
#: about the seat, so it is not allowed to convict.
#
# The REFLEXIVE pronouns are excluded deliberately, and finding out why cost a
# failing innocence test on a real corpus string: "the build lane, against its
# OWN correction" is a genuine self-refutation — `its own` points back at the
# seat — while "kimi-k3 on OPUS'S own diff" names a third party. The first cut
# of this pattern matched both and silently reclassified every real
# self-refutation as `review`, i.e. it inflated council yield with
# self-review: the exact number this report exists to keep honest. Curing an
# over-match births the under-match twin (W94), and only the innocence half of
# the corpus catches it.
_SUBJECT_NOT_SEAT_RE = re.compile(
    r"\b(?:on|against|of|over)\s+"
    r"(?!its\b|their\b|his\b|her\b|my\b|our\b|own\b)"
    r"\S+(?:'s)?\s+(?:own\b|diff\b)"
    r"|\breviewing\b",
    re.IGNORECASE,
)
_GATE_PATTERNS = [
    r"\bharness\b",
    r"\bgithub actions\b",
    r"\bfloor recompute\b",
    r"\bci\b",
]


def classify_role(raw_seat: str) -> str:
    subject_not_seat = bool(_SUBJECT_NOT_SEAT_RE.search(raw_seat))
    if _SELF_LEADING_TOKEN.match(raw_seat) or (
        not subject_not_seat
        and any(re.search(p, raw_seat, re.IGNORECASE) for p in _SELF_PATTERNS)
    ):
        return ROLE_SELF
    if (
        not subject_not_seat
        and normalize_family(raw_seat) == UNATTRIBUTED
        and any(re.search(p, raw_seat, re.IGNORECASE) for p in _WEAK_SELF_PATTERNS)
    ):
        return ROLE_SELF
    if any(re.search(p, raw_seat, re.IGNORECASE) for p in _GATE_PATTERNS):
        return ROLE_GATE
    return ROLE_REVIEW


# ---------------------------------------------------------------------------
# DECISION 4 — disposition. CONFIRMED -> applied (design changed).
# RETRACTED -> rejected (objection refused, with a reason). PLAUSIBLE is a
# THIRD, distinct bucket — neither applied nor rejected. Anything else
# (missing status, or a value none of the three) is `unrecognized`: named,
# never silently folded into any of the three real dispositions.
# ---------------------------------------------------------------------------
DISP_CONFIRMED = "confirmed"
DISP_RETRACTED = "retracted"
DISP_PLAUSIBLE = "plausible"
DISP_UNRECOGNIZED = "unrecognized"

_STATUS_MAP = {
    "CONFIRMED": DISP_CONFIRMED,
    "RETRACTED": DISP_RETRACTED,
    "PLAUSIBLE": DISP_PLAUSIBLE,
}


def _usable_count(value: Any) -> int | None:
    """A usable council count: exactly `int`, never `bool`, never negative.

    `isinstance(True, int)` is True in Python, so a YAML `applied: yes` became
    the integer 1 and a `rejected: -3` flowed straight into the report — a
    review count that is a boolean, or negative, is not a measurement of
    anything. This is the same cure rule 14 in `evidence_pack_lint.py` had to
    make days ago for `appetite:`/`spend:` (`_appetite_numeric`): validate the
    NUMBER, not merely the type. Returns None for anything unusable, so the
    caller can say so instead of silently counting nonsense."""
    if type(value) is not int:
        return None
    if value < 0:
        return None
    return value


def normalize_disposition(raw_status: Any) -> str:
    if isinstance(raw_status, str):
        return _STATUS_MAP.get(raw_status.strip().upper(), DISP_UNRECOGNIZED)
    return DISP_UNRECOGNIZED


#: Distinguishes "key absent" from "key present with value None" — a
#: declared `applied: null` is an author saying something, and must not be
#: read as the author saying nothing.
_MISSING = object()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    raw_seat: str
    family: str
    role: str
    disposition: str
    source_path: str
    source_kind: str  # "dissent" | "council_yield" | "fallback_md"


@dataclass
class PackResult:
    path: str
    ok: bool = True
    error: str | None = None
    findings: list[Finding] = field(default_factory=list)
    used_override: bool = False
    override_totals: dict[str, int] | None = None  # only when seats: absent
    est_tokens: int | None = None
    kind: str = "pack"  # "pack" (evidence/**/pack.yml) | "fallback_md"
    #: Things that were wrong with an otherwise-readable pack. A pack is not
    #: `unparseable` just because one item inside it was malformed, but the
    #: reader must still be told — `_seat_findings_from_items` already counted
    #: malformed items and its docstring promised they were "never silently
    #: vanished from the pack's diagnostics", while BOTH call sites bound the
    #: count to `_malformed` and dropped it (blind review, verified). A
    #: docstring describing behaviour the code does not have is worse than
    #: silence: it tells the next reader not to look.
    warnings: list[str] = field(default_factory=list)


def _seat_findings_from_items(
    items: Any, source_path: str, source_kind: str
) -> tuple[list[Finding], int]:
    """Turns a dissent-shaped list (`[{seat, status}, ...]`) into Findings.
    Returns (findings, malformed_item_count) — a non-dict item, or one
    missing/mistyped `seat`, is skipped from the findings list but counted,
    never silently vanished from the pack's diagnostics."""
    findings: list[Finding] = []
    malformed = 0
    if not isinstance(items, list):
        return findings, malformed
    for item in items:
        if not isinstance(item, dict):
            malformed += 1
            continue
        raw_seat = item.get("seat")
        if not isinstance(raw_seat, str) or not raw_seat.strip():
            malformed += 1
            continue
        raw_seat = raw_seat.strip()
        findings.append(
            Finding(
                raw_seat=raw_seat,
                family=normalize_family(raw_seat),
                role=classify_role(raw_seat),
                disposition=normalize_disposition(item.get("status")),
                source_path=source_path,
                source_kind=source_kind,
            )
        )
    return findings, malformed


def load_pack(path: Path) -> PackResult:
    rel = _rel(path)
    if yaml is None:
        return PackResult(path=rel, ok=False, error="pyyaml not importable")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return PackResult(path=rel, ok=False, error=f"read error: {exc}")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return PackResult(path=rel, ok=False, error=f"yaml parse error: {exc}")
    if not isinstance(data, dict):
        return PackResult(path=rel, ok=False, error="top-level YAML is not a mapping")

    result = PackResult(path=rel)

    override = data.get("council_yield")
    if override is not None and not isinstance(override, dict):
        # Asymmetric validation was the defect: a mistyped `dissent:` raised a
        # hard error while a mistyped `council_yield:` vanished without a word.
        result.warnings.append(
            "council_yield: is present but not a mapping — ignored, "
            "counts derived from dissent: instead"
        )
        override = None
    if isinstance(override, dict) and override:
        est_tokens = _usable_count(override.get("est_tokens"))
        if est_tokens is not None:
            result.est_tokens = est_tokens
        seats = override.get("seats")
        raw_seats = override.get("seats", _MISSING)
        totals: dict[str, int] = {}
        unusable: list[str] = []
        for key in ("findings", "applied", "rejected", "plausible"):
            raw = override.get(key, _MISSING)
            if raw is _MISSING:
                continue
            usable = _usable_count(raw)
            if usable is None:
                unusable.append(f"{key}={raw!r}")
            else:
                totals[key] = usable

        if isinstance(seats, list) and seats:
            findings, malformed = _seat_findings_from_items(seats, rel, "council_yield")
            result.findings = findings
            result.used_override = True
            if malformed:
                result.warnings.append(
                    f"council_yield.seats: {malformed} malformed item(s) skipped"
                )
        elif totals:
            for key in ("findings", "applied", "rejected", "plausible"):
                totals.setdefault(key, 0)
            result.override_totals = totals
            result.used_override = True
        else:
            # THE DEFECT THIS BRANCH EXISTS FOR (blind review F1/F2, verified
            # on disk): ANY non-empty mapping used to take the override path
            # and zero the pack out. `council_yield: {est_tokens: 5000}` —
            # an author adding only the informational field — silently
            # DELETED that pack's entire `dissent:` list, and because the
            # derived counts then read 0 findings, it also silenced the
            # AMENDMENTS antidote on precisely the pack that needed it. An
            # override that overrides with nothing is not an override.
            result.warnings.append(
                "council_yield: carries no usable seats: or counts — "
                "not treated as an override; counts derived from dissent:"
            )
            override = None
        if unusable:
            result.warnings.append(
                "council_yield: unusable count(s) ignored (must be a "
                "non-negative int, never a bool): " + ", ".join(sorted(unusable))
            )
        if raw_seats is not _MISSING and not (isinstance(seats, list) and seats):
            result.warnings.append(
                f"council_yield.seats: present but not a non-empty list ({type(seats).__name__})"
            )
        if result.used_override:
            return result

    dissent = data.get("dissent")
    if dissent is None:
        return result  # no dissent block — a valid, empty-of-findings pack
    if not isinstance(dissent, list):
        return PackResult(path=rel, ok=False, error="dissent: is present but not a list")
    findings, malformed = _seat_findings_from_items(dissent, rel, "dissent")
    result.findings = findings
    if malformed:
        result.warnings.append(f"dissent: {malformed} malformed item(s) skipped")
    return result


# ---------------------------------------------------------------------------
# FALLBACK — markdown `## Adversarial review` table parser. Only reached for
# a `.md` path explicitly passed via `--paths`. A doc whose section has no
# `Seat`/`Disposition` table (prose-only tally, the shape of two of the
# three 2026-08-28 dossiers this brief names) is honestly `unparseable`,
# never guessed at from narrative numbers.
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^##\s+Adversarial review\s*$", re.IGNORECASE)
# ANY heading level ends the section. `^##\s+\S` matched h2 only, so an `#`
# chapter or an `###` subheading below the review section did not terminate
# it and every table further down the document was ingested as findings
# (blind review, verified: an `# Appendix` table produced phantom seats
# `foo`, `---`, `a`). A report that manufactures findings out of unrelated
# tables is worse than one that reports none.
_NEXT_HEADING_RE = re.compile(r"^#{1,6}\s+\S")
_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
_TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
_SEPARATOR_CELL_RE = re.compile(r"^\s*:?-{2,}:?\s*$")


def _extract_adversarial_section(text: str) -> list[str] | None:
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if _HEADING_RE.match(line):
            start = i + 1
            break
    if start is None:
        return None
    end = len(lines)
    for i in range(start, len(lines)):
        if _NEXT_HEADING_RE.match(lines[i]):
            end = i
            break
    return lines[start:end]


def _parse_markdown_table(section: list[str]) -> list[dict[str, str]] | None:
    rows: list[list[str]] = []
    in_fence = False
    for line in section:
        # A fenced block is an ILLUSTRATION, not data. Without this a dossier
        # that shows the reader what the table looks like was convicted by its
        # own example (blind review, verified).
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _TABLE_ROW_RE.match(line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        rows.append(cells)
    if len(rows) < 2:
        return None
    header = [c.lower() for c in rows[0]]
    if "seat" not in header or "disposition" not in header:
        return None
    seat_idx = header.index("seat")
    disp_idx = header.index("disposition")
    parsed: list[dict[str, str]] = []
    for cells in rows[1:]:
        # Only the FIRST data row used to be separator-checked, so a second
        # table in the same section contributed its header row and its `---`
        # separator as findings named `Seat` and `---` (blind review,
        # verified). Every row is now checked, and a repeated header row is
        # skipped rather than counted as a seat.
        if cells and all(_SEPARATOR_CELL_RE.match(c) for c in cells if c):
            continue
        lowered = [c.lower() for c in cells]
        if "seat" in lowered and "disposition" in lowered:
            continue
        if len(cells) <= max(seat_idx, disp_idx):
            continue
        seat = cells[seat_idx]
        if not seat.strip():
            # An empty seat cell is not a finding. The YAML path already
            # refuses a blank seat; the markdown path accepted one and
            # reported a finding named "''".
            continue
        parsed.append({"seat": seat, "disposition": cells[disp_idx]})
    return parsed


def _normalize_fallback_disposition(raw: str) -> str:
    """The markdown tally vocabulary, PLUS the pack schema's own words.

    Blind review found the asymmetry: a hand-written table saying
    `Disposition: Confirmed` — the exact word the `dissent:` schema uses —
    fell through to `unrecognized`, because this mapper only knew
    applied/rejected/partial. The two formats describe the same three
    outcomes and must not disagree about their names."""
    upper = raw.strip().upper()
    mapped = _STATUS_MAP.get(upper)
    if mapped is not None:
        return mapped
    if upper.startswith("APPLIED"):
        return DISP_CONFIRMED
    if upper.startswith("REJECTED"):
        return DISP_RETRACTED
    if upper.startswith("PARTIAL"):
        return DISP_PLAUSIBLE
    return DISP_UNRECOGNIZED


def load_fallback_markdown(path: Path) -> PackResult:
    rel = _rel(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return PackResult(path=rel, ok=False, error=f"read error: {exc}", kind="fallback_md")
    section = _extract_adversarial_section(text)
    if section is None:
        return PackResult(
            path=rel, ok=False, error="no '## Adversarial review' section", kind="fallback_md"
        )
    rows = _parse_markdown_table(section)
    if rows is None:
        return PackResult(
            path=rel,
            ok=False,
            error=(
                "'## Adversarial review' section has no Seat/Disposition table "
                "(prose-only tally — not fabricated into structured data)"
            ),
            kind="fallback_md",
        )
    findings = [
        Finding(
            raw_seat=r["seat"],
            family=normalize_family(r["seat"]),
            role=classify_role(r["seat"]),
            disposition=_normalize_fallback_disposition(r["disposition"]),
            source_path=rel,
            source_kind="fallback_md",
        )
        for r in rows
    ]
    return PackResult(path=rel, findings=findings, kind="fallback_md")


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover_default_packs(repo_root: Path) -> list[Path]:
    return sorted((repo_root / "evidence").glob("**/pack.yml"))


def resolve_extra_paths(raw_paths: list[str], repo_root: Path) -> tuple[list[Path], list[Path]]:
    """Splits caller-supplied `--paths` into (pack_paths, markdown_paths).
    A directory is recursed for `pack.yml` only (never `.md` — markdown
    fallback is explicit-file-only, per the brief's "do not sweep the
    repo"). Order is not significant here; callers sort before use."""
    pack_paths: list[Path] = []
    md_paths: list[Path] = []
    for raw in raw_paths:
        p = (repo_root / raw) if not Path(raw).is_absolute() else Path(raw)
        if p.is_dir():
            pack_paths.extend(p.glob("**/pack.yml"))
        elif p.suffix.lower() == ".md":
            md_paths.append(p)
        elif p.name == "pack.yml" or p.suffix.lower() in (".yml", ".yaml"):
            pack_paths.append(p)
        else:
            # Unknown shape — still surfaced, as an unparseable pack path,
            # rather than dropped silently.
            pack_paths.append(p)
    return pack_paths, md_paths


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

DISPOSITIONS = (DISP_CONFIRMED, DISP_RETRACTED, DISP_PLAUSIBLE, DISP_UNRECOGNIZED)


def _empty_cell() -> dict[str, int]:
    return {d: 0 for d in DISPOSITIONS}


def aggregate(pack_results: list[PackResult]) -> dict[str, Any]:
    matrix: dict[tuple[str, str], dict[str, int]] = {}
    totals = _empty_cell()
    unparseable: list[dict[str, str]] = []
    packs_with_dissent = 0
    packs_with_override = 0

    warnings: list[dict[str, str]] = []
    for pr in sorted(pack_results, key=lambda r: r.path):
        for w in pr.warnings:
            warnings.append({"path": pr.path, "warning": w})
        if not pr.ok:
            unparseable.append({"path": pr.path, "error": pr.error or "unknown error"})
            continue
        if pr.used_override:
            packs_with_override += 1
        if pr.findings and any(f.source_kind == "dissent" for f in pr.findings):
            packs_with_dissent += 1

        if pr.override_totals is not None:
            # Scalar-only override: contributes to totals AND to the matrix
            # at (unattributed, review) — there is no seat string to
            # normalise, so `unattributed` is where it honestly belongs.
            # This comment used to say "not to the family x role matrix",
            # contradicting both the code three lines below it and the module
            # docstring (which says the contribution IS unattributed). Blind
            # review caught the pair disagreeing; the code and the module
            # docstring agreed with each other, so the inline comment was the
            # one that was wrong. A comment that misdescribes the code beside
            # it sends the next auditor looking for a bug that is not there.
            t = pr.override_totals
            found = t.get("findings", 0)
            applied = t.get("applied", 0)
            rejected = t.get("rejected", 0)
            plausible = t.get("plausible", 0)
            unrecognized = max(found - applied - rejected - plausible, 0)
            totals[DISP_CONFIRMED] += applied
            totals[DISP_RETRACTED] += rejected
            totals[DISP_PLAUSIBLE] += plausible
            totals[DISP_UNRECOGNIZED] += unrecognized
            key = (UNATTRIBUTED, ROLE_REVIEW)
            cell = matrix.setdefault(key, _empty_cell())
            cell[DISP_CONFIRMED] += applied
            cell[DISP_RETRACTED] += rejected
            cell[DISP_PLAUSIBLE] += plausible
            cell[DISP_UNRECOGNIZED] += unrecognized
            continue

        for finding in pr.findings:
            totals[finding.disposition] += 1
            key = (finding.family, finding.role)
            cell = matrix.setdefault(key, _empty_cell())
            cell[finding.disposition] += 1

    rows = []
    for (fam, role), cell in sorted(matrix.items()):
        n = sum(cell.values())
        applied = cell[DISP_CONFIRMED]
        rows.append(
            {
                "family": fam,
                "role": role,
                "findings": n,
                "confirmed": cell[DISP_CONFIRMED],
                "retracted": cell[DISP_RETRACTED],
                "plausible": cell[DISP_PLAUSIBLE],
                "unrecognized": cell[DISP_UNRECOGNIZED],
                "yield_rate": round(applied / n, 4) if n else None,
            }
        )

    return {
        "totals": {
            "findings": sum(totals.values()),
            "confirmed": totals[DISP_CONFIRMED],
            "retracted": totals[DISP_RETRACTED],
            "plausible": totals[DISP_PLAUSIBLE],
            "unrecognized": totals[DISP_UNRECOGNIZED],
        },
        "family_role_matrix": rows,
        "unparseable": sorted(unparseable, key=lambda u: u["path"]),
        "packs_scanned": sum(1 for r in pack_results if r.kind == "pack"),

        "packs_with_dissent": packs_with_dissent,
        "packs_with_council_yield_override": packs_with_override,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# DECISION 5 — the AMENDMENTS antidote, false positive closed: a
# `council_yield:` override recording 0 applied emits a candidate line only
# when it declared findings > 0. Zero findings means nothing was raised —
# there is nothing to have been silent about, and convicting that pack would
# be the misfire-log defect in reverse (case D of AMENDMENT 0's own probe).
# ---------------------------------------------------------------------------


def amendments_candidates(pack_results: list[PackResult]) -> list[dict[str, Any]]:
    """A pack whose council raised findings and applied NONE of them is an
    AMENDMENTS candidate — the antidote to "the misfire log was silent while
    misfiring".

    BOTH sources are examined, and each candidate NAMES the one it came from:

      source="declared" — the pack carries a `council_yield:` block and that
                          block's own counts show findings>0, applied==0.
      source="derived"  — the pack carries no block, so the counts come from
                          its `dissent:` list (findings>0, zero CONFIRMED).

    Scoping this to `declared` alone was the shape this function shipped in
    first, and it was WRONG in the one way that matters: `council_yield:`
    appears in 0 of the 54 packs on disk today, so the antidote could only
    ever fire on a synthetic fixture while FOUR real packs sat in the corpus
    exhibiting exactly the shape it exists to detect. An antidote that is
    green because nobody has adopted its schema yet is armed-to-nothing
    (superscar #2, Esiste != Armato) — and building the misfire-log antidote
    so that it is itself silent while the corpus misfires reproduces the very
    defect inside its own cure.

    The `source` field is not decoration. Pooling a declared count and a
    derived one under one label would be the same "one name, two meanings"
    drift this PR already had to cure once, in the pack key itself: a
    declared block is the author's own accounting, a derived count is this
    script's reading of `dissent:`, and they are not interchangeable
    evidence.

    The false-positive guard stands on both paths: findings > 0 is required,
    so a council that raised nothing is never convicted of applying nothing
    (that would be the misfire-log defect in reverse). Cost of a false
    positive here is near zero by construction — this is a REPORT, exit 0
    always, and the line is advisory, never a gate on anyone's merge."""
    out: list[dict[str, Any]] = []
    for pr in sorted(pack_results, key=lambda r: r.path):
        if not pr.ok:
            continue
        if pr.used_override:
            source = "declared"
            if pr.override_totals is not None:
                findings = pr.override_totals.get("findings", 0)
                applied = pr.override_totals.get("applied", 0)
            else:
                findings = len(pr.findings)
                applied = sum(1 for f in pr.findings if f.disposition == DISP_CONFIRMED)
        else:
            # A fallback markdown doc has no `dissent:` list to derive FROM,
            # so labelling it "derived" would make the `source` field say
            # something untrue about where the number came from — the exact
            # failure the field exists to prevent (blind review, verified).
            source = "fallback_md" if pr.kind == "fallback_md" else "derived"
            findings = len(pr.findings)
            applied = sum(1 for f in pr.findings if f.disposition == DISP_CONFIRMED)
        if findings > 0 and applied == 0:
            out.append(
                {
                    "pack": pr.path,
                    "findings": findings,
                    "applied": applied,
                    "source": source,
                }
            )
    return out


# ---------------------------------------------------------------------------
# AMENDMENT 2 — the honest limit, printed every run, never papered over.
# ---------------------------------------------------------------------------
HONEST_LIMIT = (
    "HONEST LIMIT: this report cannot know a seat's FAMILY from the pack alone "
    "beyond word-matching its raw description. A seat such as 'opus-5 Gear-3 "
    "on-disk gate (fresh context, did not write the diff)' is an independent "
    "CONTEXT but the SAME FAMILY as most authors in this corpus — under "
    "family-exclusion doctrine that is not cross-family review, and this report "
    "does not claim otherwise. It reports family x role as measured, and "
    "deliberately emits no single 'council yield' scalar that would quietly "
    "assume the author's family and flatter the process it measures."
)


def render_human(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("COUNCIL YIELD REPORT — per-seat/family/role yield over dissent blocks")
    lines.append("=" * 78)
    lines.append("")
    lines.append(HONEST_LIMIT)
    lines.append("")
    src = report["sources"]
    lines.append(
        f"packs scanned: {src['packs_scanned']}  |  with dissent: {src['packs_with_dissent']}"
        f"  |  with council_yield override: {src['packs_with_council_yield_override']}"
        f"  |  fallback docs: {src['fallback_docs_scanned']}"
    )
    if src.get("warnings"):
        lines.append(f"warnings: {len(src['warnings'])}")
        for w in src["warnings"]:
            lines.append(f"  ! {w['path']}: {w['warning']}")
    if src["unparseable"]:
        lines.append(f"UNPARSEABLE ({len(src['unparseable'])}), named, not skipped:")
        for u in src["unparseable"]:
            lines.append(f"  - {u['path']}: {u['error']}")
    else:
        lines.append("unparseable: 0")
    lines.append("")

    tot = report["totals"]
    lines.append(
        f"TOTALS  findings={tot['findings']}  confirmed(applied)={tot['confirmed']}"
        f"  retracted(rejected)={tot['retracted']}  plausible={tot['plausible']}"
        f"  unrecognized={tot['unrecognized']}"
    )
    lines.append("")

    lines.append("FAMILY x ROLE  (findings | confirmed | retracted | plausible | yield_rate)")
    lines.append("-" * 78)
    header = f"{'family':<16}{'role':<10}{'find':>6}{'conf':>6}{'retr':>6}{'plaus':>7}{'yield':>8}"
    lines.append(header)
    for row in report["family_role_matrix"]:
        yr = "n/a" if row["yield_rate"] is None else f"{row['yield_rate']:.0%}"
        lines.append(
            f"{row['family']:<16}{row['role']:<10}{row['findings']:>6}"
            f"{row['confirmed']:>6}{row['retracted']:>6}{row['plausible']:>7}{yr:>8}"
        )
    lines.append("")

    unattributed_rows = [r for r in report["family_role_matrix"] if r["family"] == UNATTRIBUTED]
    unattributed_total = sum(r["findings"] for r in unattributed_rows)
    lines.append(
        f"UNATTRIBUTED: {unattributed_total} finding(s) name no family — see DECISION 3: "
        "reported as its own bucket, never pooled into a catch-all with a per-seat yield."
    )
    lines.append("")

    cands = report["amendments_candidates"]
    if cands:
        lines.append(
            f"AMENDMENTS candidates ({len(cands)}) — council raised findings, applied none:"
        )
        for c in cands:
            lines.append(
                f"  - [{c['source']}] {c['pack']}: {c['findings']} findings, 0 applied"
            )
    else:
        lines.append("AMENDMENTS candidates: none")
    lines.append("")
    lines.append("=" * 78)
    return "\n".join(lines) + "\n"


def build_report(pack_results: list[PackResult], fallback_count: int) -> dict[str, Any]:
    agg = aggregate(pack_results)
    sources = {
        "packs_scanned": agg.pop("packs_scanned"),
        "packs_with_dissent": agg.pop("packs_with_dissent"),
        "packs_with_council_yield_override": agg.pop("packs_with_council_yield_override"),
        "warnings": agg.pop("warnings"),
        "fallback_docs_scanned": fallback_count,
        "unparseable": agg.pop("unparseable"),
    }
    return {
        "sources": sources,
        "totals": agg["totals"],
        "family_role_matrix": agg["family_role_matrix"],
        "amendments_candidates": amendments_candidates(pack_results),
        "honest_limit": HONEST_LIMIT,
    }


def run(paths: list[str] | None, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    default_packs = discover_default_packs(repo_root)
    extra_packs, md_paths = resolve_extra_paths(paths or [], repo_root)

    seen: set[str] = set()
    all_pack_paths: list[Path] = []
    for p in sorted(default_packs) + sorted(extra_packs, key=lambda x: str(x)):
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        all_pack_paths.append(p)

    pack_results = [load_pack(p) for p in all_pack_paths]
    for md in sorted(md_paths, key=lambda x: str(x)):
        pack_results.append(load_fallback_markdown(md))

    return build_report(pack_results, fallback_count=len(md_paths))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    parser.add_argument(
        "--paths",
        nargs="*",
        default=[],
        help="additive paths (dir -> recurse pack.yml; .md -> fallback parse; else -> single pack)",
    )
    args = parser.parse_args(argv)

    report = run(args.paths)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        sys.stdout.write(render_human(report))

    return 0  # a report never gates — see module docstring


if __name__ == "__main__":
    raise SystemExit(main())
