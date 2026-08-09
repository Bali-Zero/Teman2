#!/usr/bin/env python3
"""lint_retracted_claims.py — a retracted claim must not reappear un-annotated.

WHY THIS EXISTS. On 2026-08-02 this repo finished retracting a claim it had
asserted for two months: "Google's 17.2x error-amplification finding" as the
REASON for the rule that subagents never talk peer-to-peer. It took three PRs,
and the reason it took three is the point of this file: correcting a surface
does not stop the next session from reading a DATED RECORD and re-deriving the
claim into a live one. That is exactly how it reached the live WR2 orchestrator.

So the durable cure is not "fix every file". It is: make the reappearance FAIL
LOUDLY, and let dated records keep saying what they said, annotated.

WHAT COUNTS AS CLEAN. Quoting a retracted claim in order to correct it is the
CURE, not the disease. A hit is clean when a retraction DIRECTIVE sits within
`window_lines` of it. This lint never asks anyone to delete history.

DIRECTIVES ARE CASE-SENSITIVE ALL-CAPS TOKENS, and that is the load-bearing
lesson of this file's own first draft. That draft accepted ordinary words as
markers — including `Independent`, which is the very word inside the endorsement
it was built to catch (`| Independent (no coordination) | 17.2x | MAI |`). It
reported a live endorsement as CLEAN. Superscar #3 in its purest form, written
during a session about superscar #3. It also accepted `CORRECTED`, a substring
of `uncorrected`. Ordinary words, adjectives and bare numbers are BANNED as
directives, and `load_registry` refuses a registry that tries to use one.

FAIL-CLOSED. A file that cannot be read is exit 2, never an empty hit list: a
scan that could not look is not a scan that found nothing (W84). Likewise a
`--all` run that walks zero files refuses to report clean.

SELFTEST runs against the PRODUCTION registry as well as fixtures — a corpus
that only exercises a toy pattern proves the harness, not the guard. Every real
claim gets a generated guilt case (its own pattern, naked) and an innocence case
(the same text with a directive).

EXIT CODES:
    0   no un-annotated occurrence (including "no files in scope")
    1   >=1 un-annotated occurrence
    2   registry unreadable/malformed, unreadable source file, bad CLI args, or
        a scan that could not run
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Sequence

DEFAULT_REGISTRY = Path("infra/retracted-claims/registry.json")

# Only prose carries claims. A JSON payload containing "17.2" is Postgres 17.2
# nine times out of ten — measured: the naive digit grep over research/ returns
# 11 files, of which 5 are versions, a timestamp and a tax percentage.
SCOPED_SUFFIXES = {".md"}

# A directive must be unmistakably an act of retraction, never an ordinary word.
# Enforced on the registry itself so a future edit cannot re-open the hole that
# made this lint's first draft absolve the endorsement it was built to catch.
# Two classes, and the distinction is load-bearing:
#   `directives`        ALL-CAPS single tokens, matched CASE-SENSITIVELY. Case is
#                       what stops an ordinary word from absolving a hit.
#   `phrase_directives` multi-word imperatives, matched case-INSENSITIVELY. A
#                       three-word imperative cannot occur by accident, so case
#                       carries no signal there — and requiring an exact case
#                       silently misses "Do not restore" at the start of a
#                       sentence, which is how every real correction writes it.
DIRECTIVE_RE = re.compile(r"^[A-Z][A-Z \-\[\]]{4,}$")
PHRASE_MIN_WORDS = 3
BANNED_DIRECTIVES = {"CORRECTED", "CORRECTION", "CORRETTA", "CORREZIONE", "INDEPENDENT"}

# `NOT RETRACTED` means the opposite of `RETRACTED` and contains it. Checked on
# the 24 characters before every directive match.
_NEGATION_RE = re.compile(r"\b(not|non|mai|never|n[e\u00e8]|nor|isn'?t|wasn'?t)\b[\s,:;\-]*$", re.IGNORECASE)

# An absolution token must be something that appears ONLY in a correction, never
# in the endorsement being corrected. The first version of this file accepted
# `no coordination` for the 17.2x claim -- a phrase that sits inside the very
# endorsement ("Independent (no coordination) amplifies errors 17.2x, therefore
# no peers"), so a retraction of a DIFFERENT claim nearby absolved the live one.
# Same shape as the `Independent`-as-directive hole, one layer down. Statistics
# and exact table values are strong; descriptive prose is not.
_WEAK_ABSOLUTION_TOKENS = {
    "no coordination", "nessun coordinamento", "synthesis_only", "independent",
    "decentralized", "centralized", "peer-to-peer", "amplif", "retracted",
}


class Hit(NamedTuple):
    path: Path
    line_no: int
    line: str
    claim_id: str


class Claim(NamedTuple):
    id: str
    pattern: re.Pattern
    context: Optional[re.Pattern]
    context_window: int
    # A directive alone says "something here was retracted"; it does not say
    # WHICH claim. Two claims annotated inside one window would cross-absolve.
    # `absolution` binds the annotation to THIS claim: the window must also
    # carry a token from this claim's own correction (e.g. its true numbers).
    # Optional, and its absence is a DECLARED limit, not an oversight — a
    # claim without one is absolved by any directive nearby, as before.
    absolution: Optional[re.Pattern]
    # When true, ONLY `RETRACTED[<id>]` absolves. Cross-family review round 4
    # (2026-08-02) showed why the unstructured fallback cannot be made sound:
    # directive and correction token are matched anywhere in the same window,
    # so BOTH can come from inside the endorsement itself — `RETRACTED …` on one
    # line and `Centralized > Independent confirms the rule; Table 5 reports
    # Decentralized 0.477` on the next absolves the second line with its own
    # words. No token list fixes that; only a marker that NAMES the claim does.
    require_marker: bool
    why: str
    still_stands: str
    correction_lives_in: List[str]


class RegistryError(Exception):
    """Malformed registry — always surfaced as exit 2, never as 'nothing found'."""


def load_registry(path: Path) -> tuple[List[Claim], int, List[str]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RegistryError(f"registry unreadable at {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RegistryError(f"registry is not valid JSON ({path}): {exc}") from exc

    window = raw.get("window_lines")
    if not isinstance(window, int) or window < 0:
        raise RegistryError("`window_lines` must be a non-negative integer")

    directives = raw.get("directives")
    if not isinstance(directives, list) or not directives:
        raise RegistryError("`directives` must be a non-empty list")
    for d in directives:
        if not isinstance(d, str) or not d.strip():
            raise RegistryError("`directives` entries must be non-empty strings")
        if d.upper() in BANNED_DIRECTIVES:
            raise RegistryError(
                f"directive {d!r} is banned: it is an ordinary word or a substring of one "
                "(e.g. CORRECTED inside 'uncorrected'), which is how the first draft of this "
                "lint absolved the endorsement it existed to catch"
            )
        if not DIRECTIVE_RE.match(d.strip()):
            raise RegistryError(
                f"directive {d!r} is not an unambiguous ALL-CAPS retraction token — put "
                "multi-word imperatives in `phrase_directives` instead"
            )

    phrases = raw.get("phrase_directives") or []
    if not isinstance(phrases, list):
        raise RegistryError("`phrase_directives` must be a list")
    for ph in phrases:
        if not isinstance(ph, str) or len(ph.split()) < PHRASE_MIN_WORDS:
            raise RegistryError(
                f"phrase directive {ph!r} must be at least {PHRASE_MIN_WORDS} words — a shorter "
                "one can occur by accident, and these are matched case-insensitively"
            )

    entries = raw.get("claims")
    if not isinstance(entries, list) or not entries:
        raise RegistryError("`claims` must be a non-empty list")

    claims: List[Claim] = []
    for i, e in enumerate(entries):
        cid, pat = e.get("id"), e.get("pattern")
        if not isinstance(cid, str) or not cid:
            raise RegistryError(f"claims[{i}] has no `id`")
        if not isinstance(pat, str) or not pat:
            raise RegistryError(f"claim `{cid}` has no `pattern`")
        try:
            compiled = re.compile(pat, re.IGNORECASE)
        except re.error as exc:
            raise RegistryError(f"claim `{cid}` has an invalid regex: {exc}") from exc
        ctx_raw = e.get("context_pattern")
        try:
            ctx = re.compile(ctx_raw, re.IGNORECASE) if ctx_raw else None
        except re.error as exc:
            raise RegistryError(f"claim `{cid}` has an invalid context regex: {exc}") from exc
        abs_raw = e.get("absolution_pattern")
        try:
            absol = re.compile(abs_raw, re.IGNORECASE) if abs_raw else None
        except re.error as exc:
            raise RegistryError(f"claim `{cid}` has an invalid absolution regex: {exc}") from exc
        if abs_raw:
            for alt in abs_raw.split("|"):
                bare = alt.strip().strip("()").replace("\\", "").lower()
                if bare and any(w in bare for w in _WEAK_ABSOLUTION_TOKENS):
                    raise RegistryError(
                        f"claim `{cid}` absolution alternative {alt!r} is WEAK: it can occur inside "
                        "the endorsement this claim exists to catch, so it would absolve the very "
                        "text it is meant to bind. Use a value that appears only in a correction "
                        "(an exact statistic or table figure)."
                    )
        claims.append(
            Claim(
                id=cid,
                pattern=compiled,
                context=ctx,
                context_window=int(e.get("context_window", 3)),
                absolution=absol,
                require_marker=bool(e.get("require_bound_marker", False)),
                why="; ".join(e.get("why_retracted") or []) or "(no reason recorded)",
                still_stands=e.get("what_still_stands") or "",
                correction_lives_in=list(e.get("correction_lives_in") or []),
            )
        )
    return claims, window, [d.strip() for d in directives] + [f"~ci~{p.strip()}" for p in phrases]


def is_in_scope(path: Path) -> bool:
    return path.suffix.lower() in SCOPED_SUFFIXES


def _window(lines: Sequence[str], idx: int, radius: int) -> str:
    lo, hi = max(0, idx - radius), min(len(lines), idx + radius + 1)
    return "\n".join(lines[lo:hi])


def _block_bounds(lines: Sequence[str], idx: int) -> tuple[int, int]:
    """The contiguous markdown block containing line idx.

    A block is a maximal run of lines of the same kind: blockquote (`>`), table
    row (`|`), or ordinary prose. Blank lines end it.

    Why blocks and not only a line window: a real correction is a blockquote,
    and a thorough one runs 15-25 lines. Under a pure +/-20 window the FIRST
    line of a long correction is "annotated" and its last line is not, which
    makes the verdict depend on how verbose the correction is — nonsense. The
    line window stays as the rule for footnotes NEAR a claim; the block rule
    covers a claim quoted INSIDE its own correction, however long.
    """
    def kind(l: str) -> str:
        t = l.lstrip()
        if not t:
            return ""
        if t.startswith(">"):
            return "quote"
        if t.startswith("|"):
            return "table"
        return "prose"

    k = kind(lines[idx])
    if not k:
        return idx, idx
    lo = idx
    while lo > 0 and kind(lines[lo - 1]) == k:
        lo -= 1
    hi = idx
    while hi + 1 < len(lines) and kind(lines[hi + 1]) == k:
        hi += 1
    return lo, hi


def _has_directive(
    lines: Sequence[str],
    idx: int,
    directives: Sequence[str],
    window: int,
    absolution: Optional[re.Pattern] = None,
    claim_id: str = "",
    require_marker: bool = False,
) -> bool:
    """A retraction directive in the hit's own markdown BLOCK, or within
    `window` lines either side of it.

    Both directions on the window deliberately: an annotation can precede the
    quoted claim (a correction block introducing it) or follow it (a footnote
    under a table row). ALL-CAPS tokens are matched case-SENSITIVELY — that is
    what stops an ordinary word from absolving a hit; multi-word phrases are
    matched case-insensitively, since a three-word imperative cannot occur by
    accident and every real correction writes "Do not restore", capitalised.
    """
    lo, hi = _block_bounds(lines, idx)
    haystack = "\n".join(lines[lo:hi + 1]) + "\n" + _window(lines, idx, window)

    # THE ONLY SOUND FORM: an explicit claim-bound marker `RETRACTED[<claim-id>]`
    # names what it retracts, so it cannot be borrowed by a neighbouring claim
    # nor supplied by the endorsement's own words.
    if claim_id and f"RETRACTED[{claim_id}]" in haystack:
        return True
    if require_marker:
        # Registered claims opt into marker-ONLY absolution. Everything below is
        # the unstructured fallback, kept for claims that have not opted in.
        return False

    # Claim-bound absolution: a directive proves an act of retraction happened
    # here; this proves it is about THIS claim. Both, or the hit stands.
    # The registry validates that these tokens are STRONG — see `load_registry`.
    if absolution is not None and not absolution.search(haystack):
        return False

    # NEGATION GUARD. `NOT RETRACTED` / `NON RITIRATA` / `MAI RITIRATA` contain
    # a directive token and mean its exact opposite; a substring test reads them
    # as absolution and lets the endorsement stand. Superscar #3 (the guard
    # decides on form, not meaning) applied to the guard's own escape hatch.
    def _negated(text: str, at: int) -> bool:
        prefix = text[max(0, at - 24):at]
        return bool(_NEGATION_RE.search(prefix))

    lowered = haystack.lower()
    for d in directives:
        if d.startswith("~ci~"):
            needle = d[4:].lower()
            for mt in re.finditer(re.escape(needle), lowered):
                if not _negated(lowered, mt.start()):
                    return True
        else:
            for mt in re.finditer(re.escape(d), haystack):
                if not _negated(haystack.lower(), mt.start()):
                    return True
    return False


def scan_text(text: str, claims: Sequence[Claim], directives: Sequence[str], window: int) -> List[tuple[int, str, str]]:
    """Return (line_no, line, claim_id) for every un-annotated occurrence."""
    lines = text.splitlines()
    out: List[tuple[int, str, str]] = []
    for claim in claims:
        for i, line in enumerate(lines):
            if not claim.pattern.search(line):
                continue
            # A number alone is not the claim (Postgres 17.2, "17.2 x 9 cm").
            # Require the claim's own subject matter nearby — entity, not form.
            if claim.context and not claim.context.search(_window(lines, i, claim.context_window)):
                continue
            if _has_directive(lines, i, directives, window, claim.absolution, claim.id, claim.require_marker):
                continue
            out.append((i + 1, line.strip(), claim.id))
    return out


def scan_file(path: Path, claims: Sequence[Claim], directives: Sequence[str], window: int) -> List[Hit]:
    """Read and scan one file. Raises OSError/UnicodeDecodeError — callers must
    NOT swallow it: a file that could not be read is not a file with no hits."""
    text = path.read_text(encoding="utf-8")
    return [Hit(path, n, l, cid) for n, l, cid in scan_text(text, claims, directives, window)]


def git_tracked_files(repo_root: Path) -> Optional[List[str]]:
    """Every tracked file, or None if git cannot answer (never [] on failure).

    Deliberately unfiltered by pathspec: suffix filtering happens in Python so
    `.MD` is caught too — a git glob would silently miss it while is_in_scope()
    accepts it, and a scope that disagrees with itself is how things hide.
    """
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=str(repo_root), capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    return [p for p in out.stdout.split("\0") if p.strip()]


def report(hits: Sequence[Hit], claims: Sequence[Claim], scanned: int) -> int:
    by_id: Dict[str, Claim] = {c.id: c for c in claims}
    if not hits:
        print(f"OK — {scanned} file(s) scanned, no un-annotated retracted claim")
        return 0

    print(f"FAIL — {len(hits)} un-annotated occurrence(s) of a RETRACTED claim:")
    for h in hits:
        snippet = h.line if len(h.line) <= 140 else h.line[:137] + "..."
        print(f"  {h.path}:{h.line_no}: {snippet}")
    print()
    for cid in sorted({h.claim_id for h in hits}):
        c = by_id[cid]
        print(f"claim `{cid}` was retracted because: {c.why}")
        if c.still_stands:
            print(f"  what STILL stands: {c.still_stands}")
        if c.correction_lives_in:
            print(f"  the correction lives in: {', '.join(c.correction_lives_in)}")
    print()
    print(
        "fix: do NOT delete the sentence — a dated record should keep saying what it said.\n"
        "     Add a retraction DIRECTIVE within the window (RETRACTED / RITIRATA / 'do not\n"
        "     restore'), stating what was wrong and what still stands."
    )
    return 1


# --------------------------------------------------------------------------- #
# --selftest: guilt + innocence, on fixtures AND on the production registry
# --------------------------------------------------------------------------- #

FIXTURE_REGISTRY = {
    "window_lines": 3,
    "directives": ["RETRACTED", "RITIRATA"],
    "claims": [
        {
            "id": "t",
            "pattern": r"\b17[.,]2\s*[x×]",
            "context_pattern": "error|peer|amplif|Independent|Decentralized",
            "context_window": 2,
            "why_retracted": ["it names the wrong topology"],
            "what_still_stands": "the rule",
        }
    ],
}


def run_selftest(registry_path: Optional[Path] = None) -> int:
    checks = 0
    failures: List[str] = []

    def expect(label: str, cond: bool) -> None:
        nonlocal checks
        checks += 1
        if not cond:
            failures.append(label)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rp = tmp / "registry.json"
        rp.write_text(json.dumps(FIXTURE_REGISTRY), encoding="utf-8")
        claims, window, directives = load_registry(rp)
        expect("fixture registry parses", len(claims) == 1 and window == 3)

        def scan(body: str) -> List[tuple[int, str, str]]:
            return scan_text(body, claims, directives, window)

        # ---- GUILT ----
        expect("GUILT naked assertion", len(scan("we forbid peer-to-peer (the 17.2x error finding)\n")) == 1)
        expect(
            "GUILT directive outside the window",
            len(scan("17.2x error is why\n" + "\n" * 12 + "RETRACTED elsewhere\n")) == 1,
        )
        expect(
            "GUILT a second naked occurrence is not excused by the first one's note",
            len(scan("17.2x error\nRETRACTED\n" + "\n" * 10 + "again 17.2x error, naked\n")) == 1,
        )
        # The exact shape that defeated this lint's first draft: the endorsement
        # contains the word that was being used as a marker.
        expect(
            "GUILT the endorsement table row that the first draft absolved",
            len(scan("| **Independent (no coordination)** | **17.2×** | **MAI** |\n")) == 1,
        )
        expect(
            "GUILT lowercase directive does not absolve",
            len(scan("17.2x error here\nretracted (lowercase)\n")) == 1,
        )
        expect(
            "GUILT 'uncorrected' does not absolve",
            len(scan("17.2x error here\nthis is uncorrected\n")) == 1,
        )

        # ---- INNOCENCE ----
        expect("INNOCENCE directive after", scan("| row | 17.2x error |\n\n> RETRACTED 2026-08-02.\n") == [])
        expect("INNOCENCE directive before", scan("> RETRACTED: below is wrong.\n\nit said 17.2x error\n") == [])
        expect("INNOCENCE italian directive", scan("cita 17.2x peer\n\n> CITAZIONE RITIRATA.\n".replace("CITAZIONE ", "")) == [])
        # Real-world false positives the naive digit grep produced:
        expect("INNOCENCE postgres 17.2", scan("postgres-flex 17.2, repmgr HA\n") == [])
        expect("INNOCENCE 17.2 x 9 cm", scan("the card is 17.2 x 9 cm\n") == [])
        expect("INNOCENCE 17.21% tax", scan("PPh Final UMKM 17.21% of registered\n") == [])
        expect("INNOCENCE timestamp", scan("modified 2026-01-19T06:42:17.292Z\n") == [])
        expect("INNOCENCE version with arch", scan("Postgres 17.2 x86_64 build\n") == [])
        expect("INNOCENCE .json out of scope", is_in_scope(Path("a/b.json")) is False)
        expect("INNOCENCE .MD in scope (case)", is_in_scope(Path("a/b.MD")) is True)

        # ---- registry validation: every malformed shape is a loud error ----
        for label, payload in (
            ("no claims", {"window_lines": 3, "directives": ["RETRACTED"], "claims": []}),
            ("no directives", {"window_lines": 3, "directives": [], "claims": [{"id": "a", "pattern": "x"}]}),
            ("bad window", {"window_lines": -1, "directives": ["RETRACTED"], "claims": [{"id": "a", "pattern": "x"}]}),
            ("no pattern", {"window_lines": 3, "directives": ["RETRACTED"], "claims": [{"id": "a"}]}),
            ("bad regex", {"window_lines": 3, "directives": ["RETRACTED"], "claims": [{"id": "a", "pattern": "("}]}),
            ("banned directive", {"window_lines": 3, "directives": ["CORRECTED"], "claims": [{"id": "a", "pattern": "x"}]}),
            ("ordinary-word directive", {"window_lines": 3, "directives": ["Independent"], "claims": [{"id": "a", "pattern": "x"}]}),
            ("empty directive", {"window_lines": 3, "directives": [""], "claims": [{"id": "a", "pattern": "x"}]}),
        ):
            bad = tmp / f"bad-{label.replace(' ', '-')}.json"
            bad.write_text(json.dumps(payload), encoding="utf-8")
            try:
                load_registry(bad)
                expect(f"GUILT malformed registry ({label}) -> raises", False)
            except RegistryError:
                expect(f"GUILT malformed registry ({label}) -> raises", True)

        # ---- CLAIM-BOUND ABSOLUTION. The gap this file pinned on day one (a
        #      directive says something was retracted, never WHICH claim) is
        #      closed for claims that declare `absolution_pattern`: the window
        #      must also carry a token from THIS claim's own correction.
        bound_reg = {
            "window_lines": 3,
            "directives": ["RETRACTED"],
            "claims": [{
                "id": "b",
                "pattern": r"\b17[.,]2\s*[x×]",
                "context_pattern": "error|peer",
                "context_window": 2,
                "absolution_pattern": r"0\.658|Table\s*4",
                "why_retracted": ["wrong topology"],
            }],
        }
        brp = tmp / "bound.json"
        brp.write_text(json.dumps(bound_reg), encoding="utf-8")
        bclaims, bwin, bdirs = load_registry(brp)
        expect("bound registry parses with absolution", bclaims[0].absolution is not None)
        expect(
            "GUILT a directive about ANOTHER claim no longer absolves",
            len(scan_text("17.2x error\nRETRACTED — this note is about a DIFFERENT claim\n", bclaims, bdirs, bwin)) == 1,
        )
        expect(
            "GUILT the claim's own truth WITHOUT a directive does not absolve either",
            len(scan_text("17.2x error\nnote: p=0.658 in Table 4 (no directive)\n", bclaims, bdirs, bwin)) == 1,
        )
        expect(
            "INNOCENCE directive AND this claim's own correction -> clean",
            scan_text("17.2x error\nRETRACTED — Table 4 gives p=0.658\n", bclaims, bdirs, bwin) == [],
        )
        # DECLARED LIMIT, pinned: a claim with no absolution_pattern is still
        # absolved by any nearby directive. That is the documented fallback.
        expect(
            "known gap: a claim WITHOUT absolution_pattern is not claim-bound",
            scan("17.2x error\nRETRACTED — but this note is about a DIFFERENT claim\n") == [],
        )

        # ---- CROSS-CLAIM OUTCOME, on TWO registered claims. The previous
        #      version of this corpus used ONE claim and a fixture whose
        #      absolution token did not appear in the guilt text, so it asserted
        #      a PREREQUISITE and never the outcome. Cross-family review
        #      (2026-08-02) showed the shipped registry cross-absolved anyway:
        #      `no coordination` was claim 1's absolution token AND a phrase
        #      inside the endorsement it exists to catch, so a retraction of
        #      claim 2 standing next to a live claim-1 endorsement absolved it.
        two_reg = {
            "window_lines": 4,
            "directives": ["RETRACTED"],
            "claims": [
                {"id": "c-num", "pattern": r"\b17[.,]2\s*[x×]", "context_pattern": "peer|error|coordinat",
                 "context_window": 3, "absolution_pattern": r"0[.,]658|Table\s*4", "require_bound_marker": True, "why_retracted": ["wrong topology"]},
                {"id": "c-rank", "pattern": r"\bCentralized\b\s*>\s*\bIndependent\b|\bCentralized\b[^.\n]{0,40}\bbest\b",
                 "context_pattern": "peer|rank|Independent", "context_window": 3,
                 "absolution_pattern": r"0[.,]477|no single architecture dominates", "require_bound_marker": True, "why_retracted": ["wrong ranking"]},
            ],
        }
        trp = tmp / "two.json"
        trp.write_text(json.dumps(two_reg), encoding="utf-8")
        tclaims, twin, tdirs = load_registry(trp)
        c_num = [c for c in tclaims if c.id == "c-num"][0]
        c_rank = [c for c in tclaims if c.id == "c-rank"][0]

        # BOTH claims asserted nakedly, ONE of them retracted by an unbound
        # directive. The previous version of this test used a text containing
        # no claim-2 pattern at all, so "clean for claim 2" was vacuously true —
        # it asserted a PREREQUISITE, not the outcome (round 4 caught it, and
        # this file's own README says a test that reads conditions instead of
        # outcomes is how a guard passes while broken).
        cross = ("Independent (no coordination) has 17.2x error amplification, therefore no peer-to-peer.\n"
                 "Centralized > Independent confirms the no-peer rule.\n"
                 "> RETRACTED — Table 4 gives p=0.658; Table 5 gives Decentralized 0.477.\n")
        expect("cross fixture really contains claim 1", bool(c_num.pattern.search(cross)))
        expect("cross fixture really contains claim 2", bool(c_rank.pattern.search(cross)))
        expect(
            "GUILT cross-claim: an unbound directive absolves NEITHER claim",
            len(scan_text(cross, [c_num], tdirs, twin)) == 1
            and len(scan_text(cross, [c_rank], tdirs, twin)) == 1,
        )
        expect(
            "GUILT the endorsement's OWN words cannot supply the correction token",
            # `0.477` and `RETRACTED` are both present, and both come from text
            # that is not a retraction OF CLAIM 2. Marker-only mode is the fix.
            len(scan_text("> RETRACTED — the 17.2x citation is withdrawn.\n"
                          "Centralized > Independent confirms the rule; Table 5 reports Decentralized 0.477.\n",
                          [c_rank], tdirs, twin)) == 1,
        )
        expect(
            "INNOCENCE adding the claim-2 marker, and ONLY that, clears claim 2",
            scan_text(cross + "> RETRACTED[c-rank]\n", [c_rank], tdirs, twin) == []
            and len(scan_text(cross + "> RETRACTED[c-rank]\n", [c_num], tdirs, twin)) == 1,
        )
        expect(
            "GUILT a NEGATED directive does not absolve",
            len(scan_text("17.2x error, our peer rule\n> NOT RETRACTED — Table 4 p=0.658 notwithstanding\n",
                          [c_num], tdirs, twin)) == 1,
        )
        expect(
            "INNOCENCE the structured claim-bound marker absolves with no other token",
            scan_text("17.2x error peer\n> RETRACTED[c-num] see the registry\n", [c_num], tdirs, twin) == [],
        )
        expect(
            "GUILT the structured marker for ANOTHER claim does not absolve",
            len(scan_text("17.2x error peer\n> RETRACTED[c-rank] see the registry\n", [c_num], tdirs, twin)) == 1,
        )
        # The fourth-generation forms the first claim-2 regex missed entirely:
        # a comparison or a superlative used as SUPPORT, with no "best" adjacent
        # to "Centralized". Asserted on the PRODUCTION pattern further below.
        expect(
            "GUILT claim-2 catches the comparison-as-support form",
            len(scan_text("Centralized > Independent confirms the no-peer rule\n", [c_rank], tdirs, twin)) == 1,
        )
        # DECLARED FRICTION, pinned so it is a choice and not a surprise: an
        # accurate, neutral, non-causal mention still wants a directive. A
        # scanner cannot tell description from appeal, and this claim's history
        # is exactly a neutral quotation being re-derived into a reason.
        expect(
            "known friction: an accurate neutral mention is still flagged (by design)",
            len(scan_text("Kim reports a descriptive 17.2x ratio for Independent; peer-to-peer is separate.\n",
                          [c_num], tdirs, twin)) == 1,
        )
        # The registry must REFUSE a weak absolution token outright.
        weak = tmp / "weak.json"
        weak.write_text(json.dumps({"window_lines": 3, "directives": ["RETRACTED"], "claims": [
            {"id": "w", "pattern": "x", "absolution_pattern": r"no coordination|0\.658"}]}), encoding="utf-8")
        try:
            load_registry(weak)
            expect("GUILT registry refuses a WEAK absolution token", False)
        except RegistryError:
            expect("GUILT registry refuses a WEAK absolution token", True)

        expect("end-to-end guilt exits 1", report([Hit(Path("a.md"), 1, "x", "t")], claims, 1) == 1)
        expect("end-to-end innocence exits 0", report([], claims, 1) == 0)

        # ---- THE PRODUCTION REGISTRY, not just the toy one. A corpus that only
        #      exercises a fixture proves the harness, never the guard actually
        #      shipped. Every real claim gets a generated guilt + innocence pair.
        # Every formulation cross-family review found evading the production
        # patterns, pinned so a future "tidy-up" of the regex re-opens them
        # loudly. These run against the SHIPPED registry, not a fixture.
        _EVASIONS = [
            ("kim-2025-17x-error-amplification-as-cause",
             "Google's 17.2x finding is why agents must never talk to each other"),
            ("kim-2025-ranking-supports-the-no-peer-rule",
             "Centralized is better than Independent, so the no-peer rule follows"),
            ("kim-2025-ranking-supports-the-no-peer-rule",
             "Centralized outperforms Independent; hence our no-peer policy"),
            ("kim-2025-ranking-supports-the-no-peer-rule",
             "Centralized > Independent confirms the no-peer rule (Kim et al.)"),
            ("kim-2025-ranking-supports-the-no-peer-rule",
             "Independent is lowest, therefore use centralized state (2512.08296)"),
        ]
        # The mirror of _EVASIONS: real repo prose that CARRIES the relic number
        # and is NOT the claim. `4.4x` is a homograph — a wall-clock ratio is the
        # commonest way a number-followed-by-x appears in an ops ledger — so the
        # context_pattern is the only thing standing between the guard and a false
        # accusation. It failed on 2026-08-09 (PR #3837, blocked for a ReDoS timing
        # measurement) because the pattern carried `agents?` and `never`: tokens
        # present in 556 and 834 tracked .md files respectively, i.e. satisfied by
        # ambient prose in a repo about agents. Verbatim, so a future widening of
        # the context re-opens this loudly instead of on someone else's PR.
        _HOMOGRAPHS = [
            ("kim-2025-17x-error-amplification-as-cause",
             "promote the plist into `infra/launchagents/`, and check whether the other wr2 agents' plists\n"
             "are in the same state | proof-of-armed: the tracked copy is byte-identical to the loaded one\n"
             "the suite then failed at 96% on `test_redos_anchor_patterns.py`: `0.0049s -> 0.0216s "
             "(4.4x for 2x input, max 3.0x)`, and again at 3.8x when re-run alone at load average 9-11\n"
             "**Deliberately NOT fixed by widening the allowlist**: unblocking my own push by relaxing\n"
             "the gate that blocked it is the generator grading its own diff, and it must never be done"),
        ]
        prod_path = registry_path or DEFAULT_REGISTRY
        if prod_path.is_file():
            pclaims, pwindow, pdirs = load_registry(prod_path)
            expect("production registry parses", len(pclaims) >= 1)
            for c in pclaims:
                probe, truth = {
                    "kim-2025-17x-error-amplification-as-cause": (
                        "the 17.2× error-amplification finding forbids peer-to-peer",
                        "it measures Independent (no coordination); Table 4 gives p=0.658, so it is not the mechanism",
                    ),
                    "kim-2025-ranking-supports-the-no-peer-rule": (
                        "no peer-to-peer: Centralized > Independent confirms the rule (Kim et al.)",
                        "Table 5: Decentralized 0.477 > Centralized 0.463; no single architecture dominates",
                    ),
                    # The probe states ONE of the pattern's two phrases, not both:
                    # scan_text reports per match, so a probe carrying `separate
                    # checkout` AND `different inode` would flag twice and fail an
                    # assertion that is about the guard biting, not about arithmetic.
                    "desktop-nuzantara-is-a-separate-checkout": (
                        # Context comes from `repo-sync`, not from the pre-2026-07-16
                        # home location the claim is about: spelling that path here
                        # would hardcode it into a payload and trip the
                        # tcc-desktop-paths lint (superscar #1) — which is exactly what
                        # the first draft of this probe did. Another disjunct of
                        # context_pattern exercises the guard just as well.
                        "the repo-sync target is a separate checkout, so the cron writes a side copy",
                        "it is a symlink: stat -L gives 758478 for both, and both git-dirs are ~/nuzantara/.git",
                    ),
                }.get(c.id, (None, None))
                if probe is None:
                    expect(f"production claim `{c.id}` has no generated probe — add one", False)
                    continue
                naked = scan_text(probe + "\n", [c], pdirs, pwindow)
                expect(f"PROD GUILT `{c.id}` naked -> flagged", len(naked) == 1)
                if not c.require_marker:
                    annotated = scan_text(f"{probe}\n> RETRACTED — {truth}\n", [c], pdirs, pwindow)
                    expect(f"PROD INNOCENCE `{c.id}` annotated with its own truth -> clean", annotated == [])
                for eid, text in _EVASIONS:
                    if eid != c.id:
                        continue
                    expect(
                        f"PROD GUILT `{c.id}` catches the evasive form: {text[:46]}...",
                        len(scan_text(text + "\n", [c], pdirs, pwindow)) == 1,
                    )
                for hid, text in _HOMOGRAPHS:
                    if hid != c.id:
                        continue
                    expect(
                        f"PROD INNOCENCE `{c.id}` a homograph of the relic number is not the claim",
                        scan_text(text + "\n", [c], pdirs, pwindow) == [],
                    )
                if c.require_marker:
                    expect(
                        f"PROD GUILT `{c.id}` is marker-ONLY: a bare directive + correction token does not absolve",
                        len(scan_text(f"{probe}\n> RETRACTED — {truth}\n", [c], pdirs, pwindow)) == 1,
                    )
                    expect(
                        f"PROD INNOCENCE `{c.id}` the bound marker absolves",
                        scan_text(f"{probe}\n> RETRACTED[{c.id}]\n", [c], pdirs, pwindow) == [],
                    )
                if c.absolution is not None and not c.require_marker:
                    # A bare directive, with no statement of what is true, must
                    # NOT absolve a claim that declares an absolution pattern.
                    bare = scan_text(probe + "\n> RETRACTED — see registry.\n", [c], pdirs, pwindow)
                    expect(f"PROD GUILT `{c.id}` bare directive (no correction stated) -> still flagged", len(bare) == 1)
        else:
            print(
                f"SELFTEST NOTE - production registry not found at {prod_path}: SKIPPING the "
                "production-claim probes; this run proves the fixtures only.",
                file=sys.stderr,
            )
            expect("production registry probes skipped loudly", True)

    if failures:
        print(f"SELFTEST FAILED — {len(failures)}/{checks} checks failed:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"SELFTEST OK — {checks} checks")
    return 0


# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lint_retracted_claims.py",
        description="Fail when a RETRACTED claim reappears without a retraction directive near it.",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--all", action="store_true", help="Scan every git-tracked markdown file")
    mode.add_argument("--files", nargs="+", metavar="FILE", help="Scan these files")
    mode.add_argument("--selftest", action="store_true", help="Run guilt+innocence fixtures and exit")
    p.add_argument("--registry", default=str(DEFAULT_REGISTRY), help="Path to registry.json")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.selftest:
        return run_selftest(Path(args.registry))

    try:
        claims, window, directives = load_registry(Path(args.registry))
    except RegistryError as exc:
        print(f"lint_retracted_claims: {exc}", file=sys.stderr)
        return 2

    repo_root = Path.cwd()
    if args.all:
        tracked = git_tracked_files(repo_root)
        if tracked is None:
            print("lint_retracted_claims: git could not list tracked files", file=sys.stderr)
            return 2
        rels = [p for p in tracked if is_in_scope(Path(p))]
        if not rels:
            print(
                "lint_retracted_claims: git listed ZERO tracked markdown files — refusing to "
                "report clean on a scan that saw nothing",
                file=sys.stderr,
            )
            return 2
    elif args.files:
        rels = [str(Path(f)) for f in args.files]
    else:
        print("lint_retracted_claims: no mode — use --all, --files, or --selftest", file=sys.stderr)
        return 2

    hits: List[Hit] = []
    scanned = 0
    for rel in rels:
        path = repo_root / rel
        if not is_in_scope(path) or not path.is_file():
            continue
        try:
            hits.extend(scan_file(path, claims, directives, window))
        except (OSError, UnicodeDecodeError) as exc:
            # Fail CLOSED: a file we could not read is not a file with no hits.
            print(f"lint_retracted_claims: could not read {rel}: {exc}", file=sys.stderr)
            return 2
        scanned += 1

    return report(hits, claims, scanned)


if __name__ == "__main__":
    sys.exit(main())
