#!/usr/bin/env python3
"""lint_web_surface.py — the mechanically-decidable subset of the web-surface floor.

A sixteen-lane research corpus produced a 116-gate hard floor for Bali Zero's
public web surfaces (research/design/2026-08-31-web-design-sixteen-lane-corpus/
SYNTHESIS.md). Most of that floor is prose, and prose is read as a suggestion by
whoever comes next. This script is the part a machine can decide, so those gates
stop depending on anybody's memory. Repo doctrine, verbatim: "se una regola
critica e' violabile, scrivi un hook -- la documentazione non basta."

WHAT IS AND IS NOT IN HERE
--------------------------
A gate lives here only if BOTH a guilty and an innocent fixture can be written
for it (the guard-conformance rule: an over-matching guard is cicatrix superscar
family #3, and it has bitten this repo repeatedly). Gates that need a rendered
page, a photometer, a human, or a resolved open question are deliberately absent
-- see README-style notes on each gate and the report that shipped this file.

The brand red is #C8102E, verified in both
skills/bali-zero-brand/tokens.json and packages/core/tokens/semantic.css.
Contrast/APCA gates in Sec.3.1 remain out of scope because they need rendered
surface checks, not because the token is unknown. `#CE1126` also occurs in the
repo, at apps/backend-rag/scripts/templates/kbli_magazine.html:105 and
kbli_presentation.html:208. It is absent from the brand-TOKEN files, which is a
different and stronger statement. No gate here rests on that non-token colour.

SCOPE
-----
Default scan root: `apps/mouth` (the public web surface). Override with explicit
paths. Default extension set is SOURCE/UI files, NOT article content:

    .tsx .ts .jsx .js .mjs .cjs .css .scss .html .json

`.mdx` / `.md` are OPT-IN (`--ext .mdx`) and are not scanned by default. This is
a measured decision, not an oversight: apps/mouth carries ~3,360 editorial
articles in which `resmi` appears in 317 files, `100%` in 404 and `guaranteed`
in 33 -- as REPORTED FACT in third-party news prose ("pemerintah resmi
mengumumkan"), never as a Bali Zero affiliation claim. Gate 108 is about what
Bali Zero asserts about itself; that distinction is not mechanically decidable
inside a news body, so the default scope stops at the surfaces where the claim
would be Bali Zero's own.

Test files (`*.test.*`, `*.spec.*`, `__tests__/`, `__mocks__/`, `e2e/`,
`*.stories.*`) are excluded for the same reason and one sharper one: this repo
already ships a forbidden-claims guard whose fixtures are literally the banned
strings (apps/mouth/src/i18n/secondhome-forbidden-claims.test.ts contains "Kami
dijamin approve."). A lint that fires on another guard's guilty fixtures is
noise, and noise gets suppressed rather than fixed.

COPY vs CODE
------------
The string gates never run on raw file text. Each file is decomposed into:
  * a COMMENT-BLANKED view (content and structural gates read this, so ordinary
    comments cannot trip them and line numbers stay exact; lint suppression
    directives are deliberately parsed separately), and
  * a COPY corpus: string-literal contents + JSX text nodes only.
This is what makes `resmi` inside `terkonfirmasi`, `#1` inside `#1a2b3c`, and
`100%` inside `width: "100%"` decidable rather than hopeful.

Claim gates carve out explicit negation and warning/reporting copy. Honest text
such as "not guaranteed" and anti-scam advice such as "avoid any site that
promises 100% guaranteed approval" are not promises made by Bali Zero; positive
self-promises remain findings.

SUPPRESSION
-----------
    // lint-web-surface: ignore GATE-042-CLAMP -- hero type, QA'd at 360/1440

Same line, or the line immediately above the finding. The reason is MANDATORY:
a suppression with no reason is itself a finding (GATE-SUPPRESSION-NO-REASON),
because a reasonless suppression is how a gate dies quietly. There is no
blanket "ignore all" -- a suppression names exactly one gate ID.

EXIT CODES
----------
    0  clean
    1  at least one finding
    2  BLIND SCAN -- zero files were read. Not a clean result; a broken one.
    4  unknown --only gate id
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from bisect import bisect_right
from pathlib import Path
from typing import Callable, Iterable, Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SCAN_PATHS = ("apps/mouth",)

DEFAULT_EXTS = frozenset(
    {".tsx", ".ts", ".jsx", ".js", ".mjs", ".cjs", ".css", ".scss", ".html", ".json"}
)

MAX_FILE_BYTES = 1_048_576  # a hand-written web surface is not 1 MiB of text

SKIP_DIR_NAMES = frozenset(
    {
        ".git", "node_modules", ".next", ".turbo", ".vercel", "out", "dist",
        "build", "coverage", "storybook-static", "__snapshots__", ".venv",
    }
)

# Test/fixture surfaces: excluded by default (see module docstring).
TEST_PATH_RE = re.compile(
    r"(?:^|/)(?:__tests__|__mocks__|e2e|test|tests)/"
    r"|\.(?:test|spec|stories)\.[cm]?[jt]sx?$"
)

# ── suppression ────────────────────────────────────────────────────────────────

SUPPRESS_RE = re.compile(
    r"lint-web-surface\s*:\s*ignore\s+(?P<gate>[A-Z][A-Z0-9-]{3,})\s*"
    r"(?P<sep>--|—|–|:)?\s*(?P<reason>.*)$"
)
MIN_REASON_CHARS = 8


@dataclass(frozen=True)
class Finding:
    """One decided violation. `line` is 1-based and always points at real text."""

    path: str
    line: int
    gate_id: str
    message: str
    source: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: [{self.gate_id}] {self.message} (source: {self.source})"

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "line": self.line,
            "gate": self.gate_id,
            "message": self.message,
            "source": self.source,
        }


@dataclass(frozen=True)
class Span:
    """A piece of user-visible COPY, with the 1-based line it starts on."""

    text: str
    line: int
    kind: str  # "string" | "jsx" | "prose"


@dataclass
class FileCtx:
    """Everything a gate is allowed to look at, precomputed once per file."""

    path: Path
    rel: str
    ext: str
    raw: str
    # comments blanked to spaces (offsets and line numbers preserved), strings intact
    code: str
    code_lines: list[str] = field(default_factory=list)
    spans: list[Span] = field(default_factory=list)
    _line_starts: list[int] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        starts = [0]
        for m in re.finditer("\n", self.code):
            starts.append(m.end())
        self._line_starts = starts

    @property
    def is_css(self) -> bool:
        return self.ext in (".css", ".scss")

    def line_of(self, offset: int) -> int:
        """1-based line of a byte offset. Bisect, not `count` — `count` is O(offset)
        and turns any per-match loop on a large file into O(n^2)."""
        return bisect_right(self._line_starts, offset)

    def window(self, line: int, back: int = 4, forward: int = 2) -> str:
        """Joined neighbourhood of a 1-based line, from the comment-blanked view."""
        lo = max(0, line - 1 - back)
        hi = min(len(self.code_lines), line + forward)
        return "\n".join(self.code_lines[lo:hi])


def parse_suppressions(raw: str) -> tuple[dict[int, set[str]], list[tuple[int, str]]]:
    """Return ({line -> {gate ids suppressed}}, [(line, gate_id) reasonless]).

    A suppression on line L covers findings on L and on L+1 (the "comment above"
    convention). A suppression whose reason is missing or under MIN_REASON_CHARS
    suppresses NOTHING and is reported as its own finding.
    """
    covered: dict[int, set[str]] = {}
    reasonless: list[tuple[int, str]] = []
    for idx, text in enumerate(raw.splitlines(), start=1):
        m = SUPPRESS_RE.search(text)
        if not m:
            continue
        gate = m.group("gate")
        reason = (m.group("reason") or "").strip().rstrip("*/-").strip()
        if not m.group("sep") or len(reason) < MIN_REASON_CHARS:
            reasonless.append((idx, gate))
            continue
        covered.setdefault(idx, set()).add(gate)
        covered.setdefault(idx + 1, set()).add(gate)
    return covered, reasonless


# ── source decomposition ───────────────────────────────────────────────────────
#
# Three views of every file, all offset-preserving so a line number computed on
# any one of them is true of all of them:
#   code  -- comments blanked to spaces; string literals INTACT (structural gates)
#   bare  -- comments AND string contents blanked (JSX-text location only)
#   spans -- the copy corpus (string contents + JSX text nodes)

_JSX_TEXT_RE = re.compile(r">([^<>{}]+)<", re.S)
_JSX_CODEISH_RE = re.compile(r"(?:=>|&&|\|\||===|!==|;|\breturn\b)")
_HAS_LETTER_RE = re.compile(r"[A-Za-zÀ-ɏ]")


def _decompose_js(text: str) -> tuple[str, str, list[Span]]:
    """Character scanner for JS/TS/JSX. Returns (code, bare, spans).

    Deliberately not a parser: it tracks exactly the five states that decide
    whether a byte is code, comment or copy. Unterminated constructs degrade to
    "rest of file is that state", which never crashes and never invents copy.
    """
    code: list[str] = []
    bare: list[str] = []
    spans: list[Span] = []
    n = len(text)
    i = 0
    line = 1
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        # An escaped slash inside a regex (for example /\//g or /\/\//) is not
        # the start of a line comment. A full JS parser would be disproportionate
        # here; the preceding escape is the mechanically safe distinction needed
        # by the copy scanner.
        if ch == "/" and nxt == "/" and (i == 0 or text[i - 1] != "\\"):
            while i < n and text[i] != "\n":
                code.append(" ")
                bare.append(" ")
                i += 1
            continue
        if ch == "/" and nxt == "*":
            while i < n and not (text[i] == "*" and i + 1 < n and text[i + 1] == "/"):
                keep = "\n" if text[i] == "\n" else " "
                if text[i] == "\n":
                    line += 1
                code.append(keep)
                bare.append(keep)
                i += 1
            for _ in range(min(2, n - i)):
                code.append(" ")
                bare.append(" ")
                i += 1
            continue
        if ch in "\"'`":
            quote = ch
            start_line = line
            buf: list[str] = []
            code.append(ch)
            bare.append(ch)
            i += 1
            while i < n:
                c = text[i]
                if c == "\\" and i + 1 < n:
                    buf.append(text[i + 1])
                    code.append(c)
                    code.append(text[i + 1])
                    bare.append(" ")
                    bare.append(" ")
                    i += 2
                    continue
                if c == quote:
                    break
                if c == "\n":
                    line += 1
                    if quote != "`":
                        # unterminated single-line literal: stop, don't swallow the file
                        break
                    buf.append(c)
                    code.append(c)
                    bare.append(c)
                    i += 1
                    continue
                buf.append(c)
                code.append(c)
                bare.append(" ")
                i += 1
            if i < n and text[i] == quote:
                code.append(quote)
                bare.append(quote)
                i += 1
            value = "".join(buf)
            if value.strip():
                spans.append(Span(value, start_line, "string"))
            continue
        if ch == "\n":
            line += 1
        code.append(ch)
        bare.append(ch)
        i += 1
    code_s = "".join(code)
    bare_s = "".join(bare)
    for m in _JSX_TEXT_RE.finditer(bare_s):
        chunk = m.group(1)
        if not _HAS_LETTER_RE.search(chunk):
            continue
        if _JSX_CODEISH_RE.search(chunk):
            continue
        if not chunk.strip():
            continue
        spans.append(Span(chunk.strip(), bare_s.count("\n", 0, m.start(1)) + 1, "jsx"))
    return code_s, bare_s, spans


_CSS_STRING_RE = re.compile(r"""(['"])((?:\\.|(?!\1).)*)\1""", re.S)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def _blank_region(text: str) -> str:
    """Blank text without moving offsets or line numbers."""
    return "".join("\n" if char == "\n" else " " for char in text)


def _blank_css_comments(text: str, *, line_comments: bool) -> str:
    """Blank CSS block comments and, for SCSS, `//` comments outside strings."""
    out: list[str] = []
    i = 0
    quote = ""
    while i < len(text):
        char = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if quote:
            out.append(char)
            if char == "\\" and i + 1 < len(text):
                out.append(text[i + 1])
                i += 2
                continue
            if char == quote:
                quote = ""
            i += 1
            continue
        if char in "\"'":
            quote = char
            out.append(char)
            i += 1
            continue
        if char == "/" and nxt == "*":
            end = text.find("*/", i + 2)
            stop = len(text) if end < 0 else end + 2
            out.append(_blank_region(text[i:stop]))
            i = stop
            continue
        if line_comments and char == "/" and nxt == "/":
            end = text.find("\n", i + 2)
            stop = len(text) if end < 0 else end
            out.append(_blank_region(text[i:stop]))
            i = stop
            continue
        out.append(char)
        i += 1
    return "".join(out)


def _decompose_css(text: str, *, line_comments: bool = False) -> tuple[str, str, list[Span]]:
    code = _blank_css_comments(text, line_comments=line_comments)
    spans = [
        Span(m.group(2), code.count("\n", 0, m.start(2)) + 1, "string")
        for m in _CSS_STRING_RE.finditer(code)
        if m.group(2).strip()
    ]
    return code, code, spans


_JSON_STRING_RE = re.compile(r'"((?:\\.|[^"\\])*)"')


def _decompose_json(text: str) -> tuple[str, str, list[Span]]:
    spans = [
        Span(m.group(1), text.count("\n", 0, m.start(1)) + 1, "string")
        for m in _JSON_STRING_RE.finditer(text)
        if m.group(1).strip() and not re.match(r"\s*:", text[m.end():])
    ]
    return text, text, spans


_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _decompose_markdown(text: str) -> tuple[str, str, list[Span]]:
    spans: list[Span] = []
    in_fence = False
    in_front = False
    for idx, raw_line in enumerate(text.splitlines(), start=1):
        if idx == 1 and raw_line.strip() == "---":
            in_front = True
            continue
        if in_front:
            if raw_line.strip() in ("---", "..."):
                in_front = False
            continue
        if _FENCE_RE.match(raw_line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if raw_line.strip():
            spans.append(Span(raw_line.strip(), idx, "prose"))
    return text, text, spans


def build_ctx(path: Path, rel: str, raw: str) -> FileCtx:
    ext = path.suffix.lower()
    if ext in (".css", ".scss"):
        code, _bare, spans = _decompose_css(raw, line_comments=ext == ".scss")
    elif ext == ".json":
        code, _bare, spans = _decompose_json(raw)
    elif ext in (".md", ".mdx"):
        code, _bare, spans = _decompose_markdown(raw)
    else:
        source = _HTML_COMMENT_RE.sub(lambda m: _blank_region(m.group(0)), raw) if ext == ".html" else raw
        code, _bare, spans = _decompose_js(source)
    return FileCtx(
        path=path, rel=rel, ext=ext, raw=raw, code=code,
        code_lines=code.splitlines(), spans=spans,
    )


# ── shared predicates ──────────────────────────────────────────────────────────

_WORD_RE = re.compile(r"[A-Za-zÀ-ɏ][A-Za-zÀ-ɏ'’-]{2,}")

# Any of these makes a string a CSS/asset VALUE rather than user-visible copy.
_CSS_VALUE_MARKERS = re.compile(
    r"(?:gradient\(|rgba?\(|hsla?\(|color-mix\(|calc\(|var\(--|url\(|"
    r"translate|matrix\(|ellipse|cubic-bezier|\[[^\]]*%\]|%25|"
    r"\b\d+(?:\.\d+)?(?:px|rem|em|vh|vw|dvh|svh|fr|deg|ms|s)\b)",
    re.I,
)


def _is_prose(s: str) -> bool:
    """At least two real words -- an anchor `#1`, a token `100%` or a class name
    is not prose, and gates that need a sentence must not fire on them."""
    return len(_WORD_RE.findall(s)) >= 2


_CSS_BLOCK_RE = re.compile(r"\{[^{}]*[a-z-]+\s*:[^{}]*;", re.S)


def _is_css_value(s: str) -> bool:
    t = s.strip()
    if re.fullmatch(r"-?[\d.]+%", t):
        return True
    if _CSS_BLOCK_RE.search(t):
        return True  # a `<style>{`...`}` / PRINT_STYLES template literal, not copy
    return bool(_CSS_VALUE_MARKERS.search(t))


def _css_selector_for(ctx: FileCtx, line: int) -> str:
    """Nearest enclosing rule selector above a 1-based declaration line.

    At-rule headers (`@media ...{`) are skipped: the thing a gate needs to know
    is WHAT is being styled, not under which breakpoint.
    """
    for idx in range(min(line, len(ctx.code_lines)) - 1, -1, -1):
        text = ctx.code_lines[idx].strip()
        if not text.endswith("{"):
            continue
        head = text[:-1].strip()
        if head.startswith("@") or not head:
            continue
        return head
    return ""


def _css_block_after(ctx: FileCtx, line: int, limit: int = 25) -> str:
    """The remainder of the declaration block starting at a 1-based line."""
    out: list[str] = []
    for idx in range(line - 1, min(len(ctx.code_lines), line - 1 + limit)):
        text = ctx.code_lines[idx]
        out.append(text)
        if "}" in text:
            break
    return "\n".join(out)


def _id_tokens(s: str) -> set[str]:
    """camelCase / snake_case / kebab-case aware tokenizer.

    `\\bprice\\b` does NOT match `priceValue` (no word boundary between `e` and
    `V`), which is exactly how a naive money-detector goes blind. Splitting into
    tokens instead keeps `costume` innocent and `totalPrice` guilty.
    """
    return {t.lower() for t in re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]+|[a-z]+|\d+", s)}


PRICE_TOKENS = frozenset(
    {"price", "prices", "pricing", "harga", "biaya", "tarif", "rupiah", "idr",
     "rp", "amount", "subtotal", "deposit", "fee", "fees", "cost", "costs"}
)


def _balanced_call(code: str, open_paren: int, cap: int = 600) -> str:
    """Text of a call's argument list, from its `(` to the matching `)`."""
    depth = 0
    end = min(len(code), open_paren + cap)
    for i in range(open_paren, end):
        c = code[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return code[open_paren : i + 1]
    return code[open_paren:end]


# ── GATE-108-* — the string blocklist (SYNTHESIS Sec.3.10, gate 108) ───────────

_AFFILIATION_PATTERNS = (
    (re.compile(r"\bofficial\s+(?:partner|agent|agency|consultant|reseller|distributor|representative)\b", re.I),
     "official <affiliation noun>"),
    (re.compile(r"\b(?:approved|authorized|authorised)\s+(?:partner|agent|agency|consultant|reseller|distributor|representative)\b", re.I),
     "approved/authorised <affiliation noun>"),
    (re.compile(
        r"\b(?:agen|agent|mitra|partner|perwakilan|distributor|reseller|penyedia|biro|konsultan)"
        r"(?:\s+(?:imigrasi|visa|e-?voa|kitas|pma))?\s+resmi\b", re.I),
     "<affiliation noun> resmi"),
    (re.compile(r"\bresmi\s+(?:partner|mitra|agen|perwakilan|konsultan)\b", re.I),
     "resmi <affiliation noun>"),
)

_GUARANTEE_PATTERNS = (
    (re.compile(r"\bguaranteed\b", re.I), "guaranteed"),
    (re.compile(r"\bdijamin\b", re.I), "dijamin"),
    (re.compile(
        r"\bno\s+risk\b(?![\s-]*(?:tier|level|category|rating|score|profile|class|"
        r"classification|assessment|band|factor|kategori|tingkat))", re.I), "no risk"),
    (re.compile(r"\btanpa\s+risiko\b", re.I), "tanpa risiko"),
)

# The bare string `100%` is NOT decidable on this corpus: measured over
# apps/mouth it produced 18 hits of which 17 were regulatory statements of fact
# ("100% foreign ownership", "100% of the RMMG", "100% open"), which SYNTHESIS
# gate 110 explicitly protects — the conditioned claim is the compliant form.
# What survives is the claim sense, and it is the same narrowing this repo's own
# guard already made (src/i18n/secondhome-forbidden-claims.test.ts: /100%\s*approval/i).
_ABSOLUTE_CLAIM = (
    r"guarantee[ds]?|approval|approved|acceptance|success|safe|secure|certain|aman|legal|refund\w*|"
    r"dijamin|jaminan|pasti|risk[- ]?free|money[- ]?back|no\s+risk|tanpa\s+risiko|"
    r"lolos|berhasil"
)
_ABSOLUTE_RE = re.compile(
    rf"\b100\s?%\s*(?:[-–—:]\s*)?(?:{_ABSOLUTE_CLAIM})\b"
    rf"|\b(?:{_ABSOLUTE_CLAIM})\s+100\s?%",
    re.I,
)
# "entry #1", "Lampiran III ... entry #1", "step #1" are ORDINAL LOCATORS, not
# primacy claims — measured as a real false positive on
# apps/mouth/data/kbli-perpres-slice-disclosures.json:22.
_RANK_ENUMERATOR_RE = re.compile(
    r"(?i)\b(?:entry|item|no\.?|nomor|number|row|line|point|step|figure|fig\.?|note|ref|"
    r"rule|question|slide|phase|tier|option|section|pasal|ayat|lampiran)\s*$"
)
_RANK_HASH_RE = re.compile(r"(?<![\w#])#1(?![\w])")
_FIRST_RESELLER_RE = re.compile(r"\bfirst\s+reseller\b", re.I)
_RANK_SELF_RE = re.compile(r"(?i)\b(?:we|our|kami|kita|bali\s+zero|zantara)\b")
_RANK_MARKET_RE = re.compile(
    r"(?i)^\s*#1\s+(?:(?:ai[- ]powered|trusted|leading|best|top|independent|"
    r"full[- ]service)\s+)*(?:visa|kitas|immigration|imigrasi|agency|agent|consultant|konsultan|"
    r"company|pma|tax|property|relocation|service|provider)\b"
)

# These prefixes change a matched phrase from Bali Zero's promise into an
# explicit denial, warning or report about somebody else's promise. This is a
# deliberately bounded carve-out, not a general sentiment classifier.
_NEGATION_TAIL_RE = re.compile(
    r"(?i)\b(?:not|never|no|cannot|can't|can\s+not|tidak|bukan|tak)\b(?:\W+\w+){0,3}\W*$"
)
_REPORTING_PREFIX_RE = re.compile(
    r"(?i)\b(?:avoid|beware|warning|warns?|check|verify|report(?:s|ed|ing)?|"
    r"do\s+not|don't|must\s+not|should\s+not|cannot|can't|scam)\b"
)


def _is_negated_or_reported(text: str, start: int) -> bool:
    """Whether the match is explicitly denied or presented as warning/reporting copy."""
    prefix = text[max(0, start - 100):start]
    return bool(_NEGATION_TAIL_RE.search(prefix) or _REPORTING_PREFIX_RE.search(prefix))


def gate_affiliation(ctx: FileCtx) -> Iterator[tuple[int, str]]:
    for span in ctx.spans:
        for pattern, label in _AFFILIATION_PATTERNS:
            m = next(
                (
                    candidate
                    for candidate in pattern.finditer(span.text)
                    if not _is_negated_or_reported(span.text, candidate.start())
                ),
                None,
            )
            if m:
                yield span.line, (
                    f'unfalsifiable affiliation claim "{m.group(0)}" ({label}) in shipped copy — '
                    f"Bali Zero is nobody's official/resmi partner, and the string is a "
                    f"UU 8/1999 Pasal 9(1) exposure, not house style"
                )


def gate_guarantee(ctx: FileCtx) -> Iterator[tuple[int, str]]:
    for span in ctx.spans:
        for pattern, label in _GUARANTEE_PATTERNS:
            m = next(
                (
                    candidate
                    for candidate in pattern.finditer(span.text)
                    if not _is_negated_or_reported(span.text, candidate.start())
                ),
                None,
            )
            if m:
                yield span.line, (
                    f'promise of an outcome nobody controls: "{m.group(0)}" ({label}) — '
                    f"Immigration decides, so the claim is both false and the exact register "
                    f"the copycat sites print"
                )


def gate_absolute(ctx: FileCtx) -> Iterator[tuple[int, str]]:
    for span in ctx.spans:
        if _is_css_value(span.text):
            continue  # width: "100%", a gradient stop, a Tailwind arbitrary value
        m = next(
            (
                candidate
                for candidate in _ABSOLUTE_RE.finditer(span.text)
                if not _is_negated_or_reported(span.text, candidate.start())
            ),
            None,
        )
        if not m:
            continue
        yield span.line, (
            f'"{m.group(0).strip()}" — an absolute nobody can audit, on an outcome '
            "Immigration decides. State the claim WITH its conditions attached "
            "(SYNTHESIS gate 110); a weakened claim is not the fix, a conditioned one is"
        )


def gate_rank(ctx: FileCtx) -> Iterator[tuple[int, str]]:
    for span in ctx.spans:
        if _FIRST_RESELLER_RE.search(span.text):
            yield span.line, (
                '"first reseller" — an unverifiable primacy claim; '
                "there is no register that can settle it"
            )
        m = _RANK_HASH_RE.search(span.text)
        if (
            m
            and _is_prose(span.text)
            and not _RANK_ENUMERATOR_RE.search(span.text[: m.start()])
            and (
                _RANK_SELF_RE.search(span.text[:m.start()])
                or _RANK_MARKET_RE.search(span.text[m.start():])
            )
        ):
            yield span.line, (
                '"#1" in shipped copy — an unverifiable superlative; UU 8/1999 Pasal 9(1)(j) '
                '("kata-kata yang berlebihan"). It is not fine at any length'
            )


# ── GATE-057 — parseFloat on an id-ID price (Sec.3.6, gate 57) ─────────────────

_PARSE_CALL_RE = re.compile(r"\b(?:Number\.)?parse(?:Float|Int)\s*\(")
_DOTTED_PRICE_LITERAL_RE = re.compile(r"""["'`]\s*(?:Rp\.?\s*|IDR\s*)?\d{1,3}(?:\.\d{3})+""")
_ASSIGNMENT_RE = re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*([^;\n]+)")
_PRICE_FORMAT_TOKENS = frozenset(
    {"text", "string", "label", "display", "formatted", "format", "localized", "localised"}
)
_NON_PRICE_NUMERIC_TOKENS = frozenset({"percent", "percentage", "rate", "ratio"})


def _is_localized_price_reference(text: str) -> bool:
    tokens = _id_tokens(text)
    return bool(
        tokens & PRICE_TOKENS
        and tokens & _PRICE_FORMAT_TOKENS
        and not tokens & _NON_PRICE_NUMERIC_TOKENS
    )


def _is_price_parse_reference(text: str) -> bool:
    """A price-named parse operand, excluding percentages/rates."""
    tokens = _id_tokens(text)
    return bool(tokens & PRICE_TOKENS and not tokens & _NON_PRICE_NUMERIC_TOKENS)


def gate_parsefloat(ctx: FileCtx) -> Iterator[tuple[int, str]]:
    if ctx.ext in (".css", ".scss", ".json", ".md", ".mdx"):
        return
    price_aliases = {
        match.group(1)
        for match in _ASSIGNMENT_RE.finditer(ctx.code)
        if _is_localized_price_reference(match.group(2))
    }
    for m in _PARSE_CALL_RE.finditer(ctx.code):
        args = _balanced_call(ctx.code, m.end() - 1, cap=200)
        line = ctx.line_of(m.start())
        if _DOTTED_PRICE_LITERAL_RE.search(args):
            yield line, (
                "parseFloat/parseInt on a dot-grouped id-ID amount — "
                'parseFloat("790.000") returns 790, a two-order-of-magnitude error '
                "that throws nothing"
            )
            continue
        if '"' in args or "'" in args or "`" in args:
            continue
        identifier = args[1:-1].strip()
        if _is_price_parse_reference(args) or identifier in price_aliases:
            yield line, (
                f"parseFloat/parseInt on a price-named/formatted value ({args.strip()[:60]}) — "
                "an id-ID string silently loses its grouping semantics; "
                "parse with a locale-aware reverse of the formatter"
            )


# ── GATE-056 — Intl.NumberFormat notation:'compact' on money (gate 56) ─────────

_INTL_RE = re.compile(r"\bIntl\.NumberFormat\s*\(")
_COMPACT_RE = re.compile(r"""notation\s*:\s*["']compact["']""")
PAYABLE_PRICE_TOKENS = frozenset(
    {"price", "prices", "pricing", "harga", "biaya", "tarif", "payable", "checkout", "fee", "fees"}
)


def gate_compact(ctx: FileCtx) -> Iterator[tuple[int, str]]:
    if ctx.ext in (".css", ".scss", ".json", ".md", ".mdx"):
        return
    for m in _INTL_RE.finditer(ctx.code):
        args = _balanced_call(ctx.code, m.end() - 1)
        if not _COMPACT_RE.search(args):
            continue
        line = ctx.line_of(m.start())
        context_start = ctx._line_starts[max(0, line - 3)]
        named_payable = bool(_id_tokens(ctx.code[context_start:m.start()]) & PAYABLE_PRICE_TOKENS)
        if not named_payable:
            continue  # compact currency aggregates are metrics, not payable prices
        yield line, (
            "Intl.NumberFormat notation:'compact' on a payable price — emits "
            '"Rp 790 rb", which is a rounding presented as a price. Two formatters, '
            "keyed to page language, never compact"
        )


# ── GATE-042 — clamp() on price / verdict / body copy (Sec.3.5, gate 42) ───────

_CLAMP_FONTSIZE_RE = re.compile(r"\bfont-?size[\w-]*\s*[:=]\s*[^;,\n]{0,40}\bclamp\s*\(", re.I)
_TW_CLAMP_FONTSIZE_RE = re.compile(r"(?<![\w-])text-\[clamp\(", re.I)
# Token sets, not lookarounds: a lookaround boundary of `(?<![\w-])` cannot match
# `.oracle-price__value`, which is exactly the selector carrying the live
# violation at oracle.css:1288. Splitting the context into camel/kebab/snake
# tokens is the only form that survives real BEM naming.
# Deliberately NOT `copy` (would trap `.oracle-copy-cta`, a copy-to-clipboard
# button) and not `total`/`amount`. Display/hero type may clamp freely.
CLAMP_FORBIDDEN_TOKENS = frozenset(
    {"price", "prices", "harga", "verdict", "putusan", "body", "prose", "paragraph"}
)
CLAMP_DISPLAY_TOKENS = frozenset({"hero", "display", "headline", "heading", "title", "h1"})


def gate_clamp(ctx: FileCtx) -> Iterator[tuple[int, str]]:
    matches = list(_CLAMP_FONTSIZE_RE.finditer(ctx.code))
    if not ctx.is_css and ctx.ext not in (".json", ".md", ".mdx"):
        matches.extend(_TW_CLAMP_FONTSIZE_RE.finditer(ctx.code))
    for m in sorted(matches, key=lambda match: match.start()):
        line = ctx.line_of(m.start())
        if ctx.is_css:
            decl = ctx.code_lines[line - 1] if line - 1 < len(ctx.code_lines) else ""
            context = f"{_css_selector_for(ctx, line)}\n{decl}"
        else:
            context = _local_statement_context(ctx, line)
        context_tokens = _id_tokens(context)
        if context_tokens & CLAMP_DISPLAY_TOKENS:
            continue  # an explicit display/hero role wins over incidental body/prose tokens
        if not (context_tokens & CLAMP_FORBIDDEN_TOKENS):
            continue
        yield line, (
            "clamp() font-size on a price/verdict/body surface — it means nobody has "
            "looked at what the value renders as at 1023px. Use a discrete step table, "
            "pixel-checked at 360px and 1440px; clamp() is permitted only on display/hero"
        )


# ── GATE-088 — an asterisk touching a rendered price (Sec.3.8, gate 88) ────────

_PRICE_ASTERISK_RE = re.compile(
    r"(?<!\w)(?:Rp\.?|IDR|USD|EUR|SGD|\$|€)\s*[\d.,]+\s*\*(?!\*|\s*[\d{(A-Za-z_$])",
    re.I,
)
_INTERP_ASTERISK_RE = re.compile(r"\{([^{}\n]{1,80})\}\s*\*(?!\*|/)")


def gate_asterisk(ctx: FileCtx) -> Iterator[tuple[int, str]]:
    for span in ctx.spans:
        m = _PRICE_ASTERISK_RE.search(span.text)
        if m:
            yield span.line, (
                f'asterisk on a rendered price ("{m.group(0)}") — "IDR 790.000*" destroys '
                "in one glyph everything above it. Zero asterisks on a price, ever"
            )
    if ctx.ext in (".css", ".scss", ".json", ".md", ".mdx"):
        return
    for m in _INTERP_ASTERISK_RE.finditer(ctx.code):
        tail = ctx.code[m.end():].lstrip()
        if tail[:1] and re.match(r"[\w$({]", tail[0]):
            continue  # arithmetic: {price} * {nights}, {price} * count
        if _id_tokens(m.group(1)) & PRICE_TOKENS:
            yield ctx.line_of(m.start()), (
                f"asterisk rendered immediately after a price expression "
                f"({{{m.group(1).strip()[:40]}}}*) — a footnote marker on a price is the "
                "drip-pricing tell; put the condition in the price card instead"
            )


# ── GATE-030 — artificial delay on a success path (Sec.3.3, gate 30) ───────────

_SETTIMEOUT_RE = re.compile(r"\bsetTimeout\s*\(")
_SETINTERVAL_RE = re.compile(r"\bsetInterval\s*\(")
_SUCCESS_WORD_RE = re.compile(
    r"(?i)(success|sukses|berhasil|confirmed|confirmation|completed?\b|\bdone\b|"
    r"\bpaid\b|thank|\bverdict\b|\bresult\b)"
)
_STATE_SET_RE = re.compile(r"(?:set[A-Z]\w*|dispatch|router\.(?:push|replace))\s*\(")
_PROGRESS_SET_RE = re.compile(r"(?:setProgress|setPercent|setPercentage)\s*\(")
_DISMISS_ARG_RE = re.compile(
    r"""(?:set[A-Z]\w*|dispatch)\s*\(\s*(?:false|null|undefined|0|""|''|``)\s*\)"""
)
_AWAIT_PROMISE_RE = re.compile(r"\bawait\s+new\s+Promise(?:<[^>\n]+>)?\s*\(")
_TIMER_DELAY_ARG_RE = re.compile(
    r"\bsetTimeout\s*\([^,]{0,100},\s*(\d{1,7}|[A-Z0-9_]*DELAY[A-Z0-9_]*)\s*\)"
)
_PENDING_CTX_RE = re.compile(
    r"(?i)(success|submit|analy|verdict|checking|processing|memproses|menganalisa|calculat|confirm)"
)
ARTIFICIAL_DELAY_MS = 250


def gate_artificial_delay(ctx: FileCtx) -> Iterator[tuple[int, str]]:
    if ctx.ext in (".css", ".scss", ".json", ".md", ".mdx"):
        return
    for m in _SETTIMEOUT_RE.finditer(ctx.code):
        line = ctx.line_of(m.start())
        args = _balanced_call(ctx.code, m.end() - 1)
        if not (_STATE_SET_RE.search(args) and _SUCCESS_WORD_RE.search(args)):
            continue
        if _DISMISS_ARG_RE.search(args):
            continue  # auto-dismissing an already-shown toast is not a fake delay
        yield line, (
            "setTimeout drives a success/confirmation state transition — zero artificial "
            "delay on any success path; bind the animation to the real promise instead"
        )
    for m in _SETINTERVAL_RE.finditer(ctx.code):
        args = _balanced_call(ctx.code, m.end() - 1)
        if not _PROGRESS_SET_RE.search(args):
            continue
        line = ctx.line_of(m.start())
        yield line, (
            "setInterval manufactures progress without a real progress signal — bind the "
            "indicator to work completed, not elapsed wall-clock time"
        )
    for m in _AWAIT_PROMISE_RE.finditer(ctx.code):
        args = _balanced_call(ctx.code, m.end() - 1)
        delay = _TIMER_DELAY_ARG_RE.search(args)
        if not delay:
            continue
        delay_value = delay.group(1)
        if delay_value.isdigit() and int(delay_value) < ARTIFICIAL_DELAY_MS:
            continue
        line = ctx.line_of(m.start())
        if delay_value.isdigit() and not _PENDING_CTX_RE.search(ctx.window(line, back=5, forward=3)):
            continue
        detail = f"hardcoded {delay_value}ms" if delay_value.isdigit() else f"named delay {delay_value}"
        yield line, (
            f"{detail} awaited before a submit/verdict/success step — this is "
            'the "analysing your case..." theatre; compute and render, do not stage a wait'
        )


# ── GATE-059 — ellipsis on a price / verdict / inclusion line (gate 59) ────────

_TEXT_OVERFLOW_RE = re.compile(r"text-?[Oo]verflow\s*[:=]\s*[\"']?ellipsis", re.I)
_TW_TRUNCATE_RE = re.compile(r"(?<![\w-])(?:truncate|text-ellipsis|line-clamp-\d+)(?![\w-])")
_CLASS_ATTR_RE = re.compile(r"className\s*=\s*[\"']([^\"']*)[\"']")
_JSX_EXPR_RE = re.compile(r"\{([^{}]+)\}")
# Same token discipline as CLAMP. `total`/`amount` are deliberately absent:
# split over a whole JSX line they trap `{row.totalDocuments}` (a count), and an
# over-matching guard is worse here than an under-matching one.
MONEY_VERDICT_TOKENS = frozenset(
    {"price", "prices", "harga", "verdict", "putusan", "inclusive", "inclusion", "termasuk"}
)


def _css_target_selector(ctx: FileCtx, line: int) -> str:
    """Return only the element/class actually receiving the declaration."""
    current = ctx.code_lines[line - 1] if line - 1 < len(ctx.code_lines) else ""
    selector = current.split("{", 1)[0] if "{" in current else _css_selector_for(ctx, line)
    branches = selector.split(",")
    targets = [re.split(r"\s+|[>+~]", branch.strip())[-1] for branch in branches if branch.strip()]
    return " ".join(targets)


def _local_statement_context(ctx: FileCtx, line: int) -> str:
    """Small lexical statement around a JS declaration, stopping at boundaries."""
    collected: list[str] = []
    for index in range(line - 1, max(-1, line - 6), -1):
        text = ctx.code_lines[index]
        stripped = text.strip()
        if index != line - 1 and (not stripped or stripped.startswith("import ")):
            break
        collected.append(text)
        if re.search(r"\b(?:const|let|var)\b", stripped):
            break
    return "\n".join(reversed(collected))


def _tailwind_target_tokens(text: str) -> set[str]:
    """Tokens from the truncated element itself, not unrelated line context."""
    tokens: set[str] = set()
    class_match = _CLASS_ATTR_RE.search(text)
    if class_match:
        tokens.update(_id_tokens(class_match.group(1)))
    for expression in _JSX_EXPR_RE.findall(text):
        compact = expression.strip()
        # Identifiers ending in Id are opaque keys, not the verdict/price text.
        if re.search(r"(?:^|\.)[A-Za-z_$][\w$]*Id$", compact):
            continue
        tokens.update(_id_tokens(compact))
    return tokens


def gate_ellipsis(ctx: FileCtx) -> Iterator[tuple[int, str]]:
    for m in _TEXT_OVERFLOW_RE.finditer(ctx.code):
        line = ctx.line_of(m.start())
        context = (
            _css_target_selector(ctx, line) if ctx.is_css
            else _local_statement_context(ctx, line)
        )
        if not (_id_tokens(context) & MONEY_VERDICT_TOKENS):
            continue
        yield line, (
            "text-overflow: ellipsis on a price/verdict/inclusion element — a truncated "
            "Indonesian string reads as broken, not tidy, to an audience already primed "
            "to suspect a scam. Wrap, do not truncate"
        )
    if ctx.is_css or ctx.ext in (".json", ".md", ".mdx"):
        return
    for idx, text in enumerate(ctx.code_lines, start=1):
        if _TW_TRUNCATE_RE.search(text) and (_tailwind_target_tokens(text) & MONEY_VERDICT_TOKENS):
            yield idx, (
                "Tailwind truncation on a price/verdict/inclusion element — "
                "same defect as text-overflow: ellipsis (gate 59). Wrap, do not truncate"
            )


# ── GATE-062 — a flag as the language switcher (Sec.3.6, gate 62) ──────────────

_FLAG_EMOJI_RE = re.compile("[\U0001F1E6-\U0001F1FF]{2}")
_FLAG_ASSET_RE = re.compile(
    r"(?:flags?[/_-][a-z]{2,3}|[a-z]{2,3}[-_]flags?)\.(?:svg|png|webp|jpe?g)", re.I
)
_LANG_SWITCH_RE = re.compile(
    r"(?i)(language[-_]?switch\w*|locale[-_]?switch\w*|lang[-_]?switch\w*|"
    r"switch[-_]?(?:language|locale|lang)|hreflang|"
    r"(?<![\w-])(lang|locale|language|languages|bahasa|i18n)(?![\w-]))"
)
# A nationality/country picker legitimately uses flags — it is not the language
# switcher, and this repo really ships one (src/lib/utils/nationality-flags.ts).
_NATIONALITY_CTX_RE = re.compile(
    r"(?i)(nationalit|countr|passport|negara|kewarganegaraan|citizenship)"
)
_EXPLICIT_SWITCHER_RE = re.compile(
    r"(?i)(language[-_]?switch\w*|locale[-_]?switch\w*|lang[-_]?switch\w*|"
    r"switch[-_]?(?:language|locale|lang)|hreflang|setlocale|changelanguage)"
)


def _flag_context(ctx: FileCtx, line: int) -> str:
    return f"{ctx.path.name}\n{ctx.window(line, back=6, forward=4)}"


def gate_flag_switcher(ctx: FileCtx) -> Iterator[tuple[int, str]]:
    seen: set[int] = set()
    candidates: list[tuple[int, str]] = []
    for m in _FLAG_EMOJI_RE.finditer(ctx.code):
        candidates.append((ctx.line_of(m.start()), "flag emoji"))
    for m in _FLAG_ASSET_RE.finditer(ctx.code):
        candidates.append((ctx.line_of(m.start()), f"flag image `{m.group(0)}`"))
    for line, what in candidates:
        if line in seen:
            continue
        context = _flag_context(ctx, line)
        if not _LANG_SWITCH_RE.search(context):
            continue
        if _NATIONALITY_CTX_RE.search(context) and not _EXPLICIT_SWITCHER_RE.search(context):
            continue  # a nationality picker, not a language switcher
        seen.add(line)
        yield line, (
            f"{what} used in a language-switch surface — a flag names a country, not a "
            'language; Indonesia is the textbook case that breaks it. Use text "EN · ID"'
        )


# ── GATE-113 — third-party accessibility overlay (Sec.3.10, gate 113) ──────────
#
# Vendor HOSTS and package specifiers only, never the vendor NAME: a sentence
# saying "never install accessiBe" must stay innocent.

_OVERLAY_RE = re.compile(
    r"(?i)(acsbapp\.com|accessibe\.com|cdn\.userway\.org|api\.userway\.org|userway\.org/widget|"
    r"widget\.userway\.org|audioeye\.com/[\w./-]*\.js|ae\.audioeye\.com|equalweb\.com|"
    r"nagich\.co\.il|accessiway\.com|adally\.com|allyable\.com|reciteme\.com|"
    r"[\"'@/](?:accessibe|userway|audioeye|equalweb|accessiway)(?:[/-][\w-]+)?[\"'])"
)
_OVERLAY_DENYLIST_RE = re.compile(
    r"(?i)(?:^|[^a-z])(?:denylist|blocklist|blocked|forbidden)(?:$|[^a-z])"
)
_OVERLAY_WARNING_RE = re.compile(
    r"(?i)\b(?:be\s+suspicious|avoid|beware|do\s+not|don't|never)\b"
)


def gate_a11y_overlay(ctx: FileCtx) -> Iterator[tuple[int, str]]:
    for m in _OVERLAY_RE.finditer(ctx.code):
        line = ctx.line_of(m.start())
        local_line = ctx.code_lines[line - 1] if line - 1 < len(ctx.code_lines) else ""
        if _OVERLAY_DENYLIST_RE.search(local_line) or _OVERLAY_WARNING_RE.search(local_line):
            continue
        yield line, (
            f"third-party accessibility overlay ({m.group(0).strip(chr(34) + chr(39))}) — zero, on any "
            "surface, ever. 1,030+ signatories: full compliance cannot be achieved with an "
            "overlay, and overlays are now cited AGAINST defendants"
        )


# ── GATE-058 — fixed width on a button / chip / badge / pill (gate 58) ─────────

_CSS_FIXED_WIDTH_RE = re.compile(r"^\s*width\s*:\s*(\d+(?:\.\d+)?)(px|rem)\b", re.I)
_BUTTONISH_RE = re.compile(r"(?i)(?:^|[^a-z])(btn|button|chip|badge|pill|cta)(?:[^a-z]|$)")
_LAYOUT_CONTROL_SUFFIX_RE = re.compile(
    r"(?i)(?:^|[-_])(group|section|container|wrapper|list|row|grid|stack)(?:$|[-_])"
)
_SQUARE_EXEMPT_RE = re.compile(r"(?i)(icon|avatar|dot|swatch|spinner|square|toggle|close|arrow)")
_TW_FIXED_W_RE = re.compile(r"(?<![\w-])w-\[(\d+(?:\.\d+)?)(px|rem)\]")
_TW_FIXED_H_RE = re.compile(r"(?<![\w-])h-\[(\d+(?:\.\d+)?)(px|rem)\]")
_JSX_OPEN_TAG_RE = re.compile(r"<(?P<tag>[A-Za-z][\w.]*)\b(?P<attrs>[^<>]*?)/?>")

_FIXED_WIDTH_MSG = (
    "fixed {unit} width on a button/chip/badge/pill — reserve a working margin +35-50% "
    "for Indonesian copy; this is an engineering allowance, not a measurement. "
    "Use min-width + wrap + a min-height "
    "that tolerates two lines"
)


def _is_control_selector(selector: str) -> bool:
    targets = [re.split(r"\s+|[>+~]", part.strip())[-1] for part in selector.split(",") if part.strip()]
    return any(
        _BUTTONISH_RE.search(target) and not _LAYOUT_CONTROL_SUFFIX_RE.search(target)
        for target in targets
    )


def gate_fixed_width(ctx: FileCtx) -> Iterator[tuple[int, str]]:
    if ctx.is_css:
        for idx, text in enumerate(ctx.code_lines, start=1):
            m = _CSS_FIXED_WIDTH_RE.match(text)
            if not m:
                continue
            selector = _css_selector_for(ctx, idx)
            if not _is_control_selector(selector):
                continue
            if _SQUARE_EXEMPT_RE.search(selector):
                continue
            block = _css_block_after(ctx, idx)
            if "aspect-ratio" in block:
                continue
            if re.search(rf"height\s*:\s*{re.escape(m.group(1))}{m.group(2)}\b", block, re.I):
                continue  # a square control has no text to expand
            yield idx, _FIXED_WIDTH_MSG.format(unit=m.group(2))
        return
    if ctx.ext in (".json", ".md", ".mdx"):
        return
    for idx, text in enumerate(ctx.code_lines, start=1):
        for tag_match in _JSX_OPEN_TAG_RE.finditer(text):
            tag = tag_match.group("tag")
            attrs = tag_match.group("attrs")
            m = _TW_FIXED_W_RE.search(attrs)
            control = _BUTTONISH_RE.search(tag) or (
                tag.lower() == "a" and _BUTTONISH_RE.search(attrs)
            )
            if not m or not control:
                continue
            if _SQUARE_EXEMPT_RE.search(f"{tag} {attrs}"):
                continue
            h = _TW_FIXED_H_RE.search(attrs)
            if h and h.group(1) == m.group(1) and h.group(2) == m.group(2):
                continue
            yield idx, _FIXED_WIDTH_MSG.format(unit=m.group(2))


# ── GATE-068 — type="number" on a form field (Sec.3.7, gate 68) ────────────────

_TYPE_NUMBER_RE = re.compile(r"""type\s*=\s*(?:["']number["']|\{\s*["']number["']\s*\})""")


def gate_number_input(ctx: FileCtx) -> Iterator[tuple[int, str]]:
    if ctx.ext in (".css", ".scss", ".json", ".md", ".mdx"):
        return
    for m in _TYPE_NUMBER_RE.finditer(ctx.code):
        yield ctx.line_of(m.start()), (
            'type="number" on an input — use type="text" inputmode="numeric". The spinner '
            "arrows are a mis-tap target on a 360px phone and scroll-wheel edits the value "
            "silently"
        )


# ── registry ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Gate:
    id: str
    title: str
    source: str
    check: Callable[[FileCtx], Iterable[tuple[int, str]]]


GATES: tuple[Gate, ...] = (
    Gate("GATE-108-AFFILIATION", "official/resmi/approved partner claim",
         "SYNTHESIS §3.10, gate 108", gate_affiliation),
    Gate("GATE-108-GUARANTEE", "guaranteed / dijamin / no risk / tanpa risiko",
         "SYNTHESIS §3.10, gate 108", gate_guarantee),
    Gate("GATE-108-ABSOLUTE", "the string 100% in shipped copy",
         "SYNTHESIS §3.10, gate 108", gate_absolute),
    Gate("GATE-108-RANK", "#1 / first reseller primacy claim",
         "SYNTHESIS §3.10, gate 108", gate_rank),
    Gate("GATE-057-PARSEFLOAT", "parseFloat on an id-ID price string",
         "SYNTHESIS §3.6, gate 57", gate_parsefloat),
    Gate("GATE-056-COMPACT", "Intl.NumberFormat notation:'compact' on money",
         "SYNTHESIS §3.6, gate 56", gate_compact),
    Gate("GATE-042-CLAMP", "clamp() font-size on price/verdict/body copy",
         "SYNTHESIS §3.5, gate 42", gate_clamp),
    Gate("GATE-088-ASTERISK", "asterisk adjacent to a rendered price",
         "SYNTHESIS §3.8, gate 88", gate_asterisk),
    Gate("GATE-030-DELAY", "artificial delay on a success path",
         "SYNTHESIS §3.3, gate 30", gate_artificial_delay),
    Gate("GATE-059-ELLIPSIS", "ellipsis truncation on price/verdict/inclusion",
         "SYNTHESIS §3.6, gate 59", gate_ellipsis),
    Gate("GATE-062-FLAG", "flag emoji/image as the language switcher",
         "SYNTHESIS §3.6, gate 62", gate_flag_switcher),
    Gate("GATE-113-OVERLAY", "third-party accessibility overlay",
         "SYNTHESIS §3.10, gate 113", gate_a11y_overlay),
    Gate("GATE-058-FIXEDWIDTH", "fixed px/rem width on button/chip/badge/pill",
         "SYNTHESIS §3.6, gate 58", gate_fixed_width),
    Gate("GATE-068-NUMBERINPUT", 'type="number" on a form field',
         "SYNTHESIS §3.7, gate 68", gate_number_input),
)

SUPPRESSION_GATE_ID = "GATE-SUPPRESSION-NO-REASON"
SUPPRESSION_SOURCE = "lint_web_surface.py — suppression contract"
GATE_IDS = frozenset(g.id for g in GATES) | {SUPPRESSION_GATE_ID}


# ── scanning ───────────────────────────────────────────────────────────────────

def iter_files(
    roots: Iterable[Path],
    exts: frozenset[str],
    include_tests: bool,
    max_bytes: int = MAX_FILE_BYTES,
    oversize: list[Path] | None = None,
) -> Iterator[Path]:
    """Walk the scan roots. Files over `max_bytes` are NOT scanned but ARE
    recorded in `oversize` — a 37MB KBLI dataset is data, not a web surface, and
    a silent skip is the blind-scan failure this repo has been bitten by (W97)."""

    def _accept(path: Path) -> bool:
        if max_bytes and path.stat().st_size > max_bytes:
            if oversize is not None:
                oversize.append(path)
            return False
        return True

    for root in roots:
        if root.is_file():
            if root.suffix.lower() in exts and _accept(root):
                yield root
            continue
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_symlink() or not path.is_file():
                continue
            if path.suffix.lower() not in exts:
                continue
            parts = set(path.parts)
            if parts & SKIP_DIR_NAMES:
                continue
            if not include_tests and TEST_PATH_RE.search(path.as_posix()):
                continue
            if not _accept(path):
                continue
            yield path


def scan_file(path: Path, rel: str, only: set[str] | None = None) -> list[Finding]:
    try:
        raw = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    ctx = build_ctx(path, rel, raw)
    covered, reasonless = parse_suppressions(raw)
    findings: list[Finding] = []
    for gate in GATES:
        if only and gate.id not in only:
            continue
        for line, message in gate.check(ctx):
            if gate.id in covered.get(line, ()):  # type: ignore[arg-type]
                continue
            findings.append(Finding(rel, line, gate.id, message, gate.source))
    if not only or SUPPRESSION_GATE_ID in only:
        for line, gate_id in reasonless:
            findings.append(
                Finding(
                    rel, line, SUPPRESSION_GATE_ID,
                    f"suppression of {gate_id} carries no reason — a reasonless suppression "
                    f'suppresses nothing and is itself a finding. Write '
                    f'"lint-web-surface: ignore {gate_id} -- <why this case is innocent>"',
                    SUPPRESSION_SOURCE,
                )
            )
    return sorted(findings, key=lambda f: (f.line, f.gate_id))


def scan(roots: Iterable[Path], repo_root: Path, exts: frozenset[str],
         include_tests: bool = False, only: set[str] | None = None,
         max_bytes: int = MAX_FILE_BYTES) -> tuple[list[Finding], int, list[str]]:
    findings: list[Finding] = []
    scanned = 0
    oversize: list[Path] = []

    def _rel(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(repo_root))
        except ValueError:
            return str(path)

    for path in iter_files(roots, exts, include_tests, max_bytes, oversize):
        scanned += 1
        findings.extend(scan_file(path, _rel(path), only))
    return findings, scanned, [_rel(p) for p in oversize]


# ── CLI ────────────────────────────────────────────────────────────────────────

def _print_gates() -> None:
    print("Implemented gates (a gate ships only with BOTH a guilty and an innocent test):\n")
    width = max(len(g.id) for g in GATES)
    for gate in GATES:
        print(f"  {gate.id.ljust(width)}  {gate.title}")
        print(f"  {' ' * width}  source: {gate.source}")
    print(f"\n  {SUPPRESSION_GATE_ID.ljust(width)}  a suppression with no reason")
    print(f"  {' ' * width}  source: {SUPPRESSION_SOURCE}")
    print(
        "\nSuppress one gate on one line with a MANDATORY reason:\n"
        "  // lint-web-surface: ignore GATE-042-CLAMP -- hero type, QA'd at 360/1440\n"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("paths", nargs="*", type=Path,
                    help=f"files/dirs to scan (default: {', '.join(DEFAULT_SCAN_PATHS)})")
    ap.add_argument("--json", action="store_true", help="machine-readable output for CI")
    ap.add_argument("--list-gates", action="store_true", help="print implemented gates and exit")
    ap.add_argument("--ext", action="append", default=None, metavar=".mdx",
                    help="ADD an extension to the scan set (repeatable). .mdx/.md are "
                         "opt-in — see the module docstring for why")
    ap.add_argument("--only", action="append", default=None, metavar="GATE-ID",
                    help="run only these gate IDs (repeatable)")
    ap.add_argument("--max-bytes", type=int, default=MAX_FILE_BYTES,
                    help=f"skip (and report) files larger than this; 0 disables the cap "
                         f"(default: {MAX_FILE_BYTES})")
    ap.add_argument("--include-tests", action="store_true",
                    help="also scan test/spec/story files (they carry deliberate guilty fixtures)")
    ap.add_argument("--repo-root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    if args.list_gates:
        _print_gates()
        return 0

    repo_root = args.repo_root.resolve()
    exts = DEFAULT_EXTS | {e if e.startswith(".") else f".{e}" for e in (args.ext or [])}
    only = set(args.only) if args.only else None
    if only:
        unknown = only - GATE_IDS
        if unknown:
            print(f"[error] unknown gate id(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            return 4

    roots = [p if p.is_absolute() else repo_root / p
             for p in (args.paths or [Path(p) for p in DEFAULT_SCAN_PATHS])]
    findings, scanned, oversize = scan(
        roots, repo_root, exts, args.include_tests, only, args.max_bytes
    )

    if args.json:
        print(json.dumps({
            "schema": 1,
            "scanned_files": scanned,
            "findings": [f.as_dict() for f in findings],
            "skipped_oversize": oversize,
            "gates": [{"id": g.id, "title": g.title, "source": g.source} for g in GATES],
            "blind_scan": scanned == 0,
        }, indent=2))
    else:
        for finding in findings:
            print(finding.render())
        if oversize:
            print(
                f"[web-surface] {len(oversize)} file(s) over --max-bytes were NOT scanned: "
                f"{', '.join(oversize[:5])}{' ...' if len(oversize) > 5 else ''}"
            )
        if scanned and not findings:
            print(f"[web-surface] clean — {scanned} file(s) scanned, no findings")
        elif findings:
            print(
                f"\nWEB-SURFACE LINT FAIL — {len(findings)} finding(s) across {scanned} file(s). "
                f"Each names the gate that decided it; the floor is "
                f"research/design/2026-08-31-web-design-sixteen-lane-corpus/SYNTHESIS.md. "
                f"If a finding is genuinely innocent, suppress it WITH A REASON on its line "
                f"(see --list-gates) — never by widening the gate."
            )

    if scanned == 0:
        print(
            "BLIND SCAN: zero files were read — wrong path, wrong --ext, or an empty tree. "
            "NOT a clean result.",
            file=sys.stderr,
        )
        return 2
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
