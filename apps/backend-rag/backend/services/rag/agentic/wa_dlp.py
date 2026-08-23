"""DLP (Data Loss Prevention) policy for the WA codex-route context package
(BOT-V4 G-P3, research/operations/2026-08-19-bot-chatgpt-provider-broker-spec.md
section G-P3).

The codex-route package (`wa_package_builder.build_context_package`, D1) is
built from real customer conversation history, our own curated-KB chunks,
and the pricing lookup's own echoed search query — all three free-text
surfaces can carry Indonesian PII (NIK/KTP, NPWP, passport, phone, email,
bank account, credential shapes). This module redacts every occurrence to a
stable placeholder BEFORE the package is sealed (`package_hash` is computed
over the REDACTED content, never the original), and reverses the
substitution on the codex-generated answer so the client still sees the
real value.

Pure, regex-only, dependency-free by design (no Presidio in the hot path —
apps/backend-rag/backend/middleware/pii_scanner.py already carries that
dependency for a different, offline surface). No I/O, no logging of any
matched ORIGINAL string anywhere in this module — every log line here
carries category + count only, never content (project CLAUDE.md §14 PII
boundary).

Precedence is enforced BY CONSTRUCTION, not by a separate disambiguation
step: `_CATEGORY_PATTERNS` runs in a fixed priority order, and each
category's matches are substituted with placeholders before the NEXT
category's patterns scan the (now partially placeholder-bearing) text — a
span already claimed by a higher-priority category can never be re-matched
by a lower-priority one, because the original characters underneath it are
gone. This is how a 16-digit NPWP (`\\b0\\d{15}\\b`) is guaranteed to be
labelled NPWP and never NIK, even though a bare-digit NIK pattern would
otherwise also match it: NPWP runs first.

DECLARED LIMITS (not bugs — read before "fixing" one of these):
  - Dedup keys on the literal SURFACE FORM of a match, not on a normalized
    value: the SAME NIK quoted once bare ("1234567890123456") and once
    separated ("1234 5678 9012 3456") is two different original strings and
    gets TWO different placeholders. Every occurrence is still redacted;
    only the "same placeholder" guarantee is scoped to identical surface
    form.
  - NIK_KTP's category runs BEFORE BANK_ACCOUNT, so a labelled 15/16-digit
    bank account number ("rekening 1234567890123456") is claimed by the
    bare/separated NIK pattern first and comes out as `[PII-NIK_KTP-N]`
    with the label left literal — a MISLABEL, never a leak (the digits are
    redacted either way). Same story for a bare/separated NPWP-old-15
    written without its official dotted format: it falls through NPWP's
    dotted-only patterns and is caught by NIK_KTP's new separated pattern
    instead.
  - `restore_text`'s placeholder regex is intentionally strict
    (`\\[PII-[A-Z_]+-\\d+\\]`, uppercase, closed brackets). A near-miss shape
    a model might emit — lowercase `[pii-email-1]`, an unclosed
    `[PII-EMAIL-1`, extra whitespace — matches neither the known-placeholder
    branch NOR the unknown-placeholder strip path: it passes through
    untouched. This is a declared gap, not silently accepted: it can never
    be a raw ORIGINAL value (those never had a chance to be typed by the
    model, since the model only ever sees placeholders), so the exposure is
    "a malformed-looking token survives", not "PII survives".
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Fail-closed overflow guard (spec G-P3 rule 7): a package needing more than
# this many DISTINCT redacted values in one turn is a suspicious payload,
# not an unlucky one — the caller converts this into PackageUnbuildable.
# Counts EVERY distinct value the redactor issued a placeholder for,
# including one-way categories (CREDENTIAL, spalla S1) that never enter
# `reversal_map` — the overflow guard tracks placeholder ISSUANCE, not the
# reversal map's size, so a flood of credential-shaped tokens still trips it.
MAX_PLACEHOLDERS = 64

_PLACEHOLDER_RE = re.compile(r"\[PII-([A-Z_]+)-(\d+)\]")


@dataclass(frozen=True)
class DlpHit:
    category: str
    placeholder: str


@dataclass(frozen=True)
class DlpResult:
    """Explicit result of `redact_package_fields` — a named dataclass
    instead of a positional tuple (spalla review: a 4/5-element positional
    tuple is a silent-reshuffle trap the moment a field is added or
    reordered; every call site here unpacks by ATTRIBUTE name instead)."""

    history: list[dict[str, Any]]
    chunks: list[dict[str, Any]]
    search_query: str | None
    reversal_map: dict[str, str]
    hits: list[DlpHit]


class DlpOverflow(Exception):
    """More than MAX_PLACEHOLDERS distinct values would be redacted in one
    package — the caller treats the whole package as unbuildable rather
    than emitting a partially-redacted one."""


# --------------------------------------------------------------------------
# Category patterns, in FIXED priority order (see module docstring for why
# order is load-bearing). EMAIL runs first so a digit-bearing local-part or
# domain is captured whole before any digit-shaped category can eat part of
# it. CREDENTIAL shapes are structurally distinct from every digit pattern
# below and run next purely to keep them out of the digit-precedence
# discussion entirely. NPWP runs before NIK_KTP — the ONE precedence
# requirement the design spec calls out by name. BANK_ACCOUNT (label-
# anchored only, per spec — a bare digit run is NEVER a bank account, that
# is scar family #3 over-match territory: Bali addresses, prices, KBLI
# codes are all bare digit runs) runs before PHONE so a labelled account
# number sitting in a phone-shaped run is not consumed as a phone first.
# --------------------------------------------------------------------------

# Kimi-5 (MINOR): the previous final segment `[\w.-]+` is greedy and
# includes `.`, so "foo@example.com." (a customer's sentence-final email)
# swallowed the trailing sentence period into the match. `\.\w{2,}` anchors
# the TLD to word-characters only — a literal trailing `.` is never part of
# a TLD, so it is left behind as ordinary punctuation.
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w{2,}")

# CREDENTIAL — JWT (three dot-separated base64url segments), PEM header,
# common vendor key prefixes, and a bare bearer token. Deliberately the
# literal shapes from the design spec — no attempt to unify or extend them.
# ONE-WAY CATEGORY (spalla S1): see `_ONE_WAY_CATEGORIES` below.
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b")
_PEM_RE = re.compile(r"-----BEGIN [A-Z ]*KEY-----")
# F5: the vendor prefixes now REQUIRE their separator. Without it, `sk`
# followed by 16+ word characters swallows ordinary vocabulary
# ("skincareproducts2026", "skillsheet1234567890") — and CREDENTIAL is a
# ONE-WAY category with no reversal map, so such a false positive is an
# IRRECOVERABLE hole in the customer's own reply. AKIA is a separate
# alternative: its format carries no separator by construction.
_KEY_PREFIX_RE = re.compile(
    r"\b(?:"
    r"sk[-_][A-Za-z0-9_-]{16,}"
    r"|ghp_[A-Za-z0-9_-]{16,}"
    r"|gho_[A-Za-z0-9_-]{16,}"
    r"|xoxb-[A-Za-z0-9_-]{16,}"
    r"|xoxp-[A-Za-z0-9_-]{16,}"
    r"|AKIA[A-Z0-9]{16}"
    r")\b"
)
_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}")

# F5b (Kimi round-3 BLOCKER): requiring the separator was not enough. The
# tail class still contains `-` and `_`, so `sk-` followed by hyphen-separated
# WORDS satisfies the 16-char minimum — and `SK` is Surat Keputusan, the
# single most-cited document type this business writes about
# (`sk-kemenkumham-ahu-0012345`, the article slug `sk-immigration-update-2026`).
# CREDENTIAL is ONE-WAY: that span would be deleted from the customer's own
# answer with no way back.
#
# The distinguisher is STRUCTURAL, not a word list: a real key carries its
# entropy in one UNBROKEN alphanumeric run (`sk-proj-A1b2...` — 32 chars with
# no separator), while human text is short words joined by hyphens. So the
# `sk` alternative additionally requires one unbroken run of >=16 alphanumeric
# characters somewhere after the prefix. The other prefixes are left alone:
# `ghp_`/`gho_`/`xoxb-`/`xoxp-`/`AKIA` are not words in any language this
# business writes, so they have no innocent collision to protect against —
# narrow at the false positive, never at the canonical form.
_KEY_ENTROPY_RUN_RE = re.compile(r"[A-Za-z0-9]{16,}")


def _validate_key_prefix(_source: str, match: re.Match[str]) -> bool:
    # `_source` is unused: unlike the amount/passport validators, this one
    # decides entirely on the matched span's own shape — surrounding prose
    # cannot make a hyphenated slug more or less of a credential. The
    # parameter stays to satisfy the `Validator` signature.
    surface = match.group(0)
    if not surface.startswith(("sk-", "sk_")):
        return True
    return _KEY_ENTROPY_RUN_RE.search(surface[3:]) is not None

# NPWP — reused verbatim from backend/middleware/pii_scanner.py's Presidio
# patterns (already hardened, already the codebase's chosen shapes):
# old 15-digit dotted, new 16-digit bare (leading zero), new 16-digit
# dotted. Order among the three does not matter (their shapes are mutually
# exclusive by word-boundary construction — a dotted string never satisfies
# a bare 16-digit boundary), but NPWP as a CATEGORY must precede NIK_KTP.
_NPWP_OLD_RE = re.compile(r"\b\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3}\b")
_NPWP_NEW16_RE = re.compile(r"\b0\d{15}\b")
_NPWP_NEW_DOTTED_RE = re.compile(r"\b0\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3}\b")

# NIK/KTP — label-anchored variant (catches separator-broken forms a bare
# 16-digit boundary regex would miss, e.g. "NIK: 1234 5678 9012 3456") plus
# the bare 16-digit run, plus (Kimi M2) an UNLABELLED separator-broken form
# ("1234 5678 9012 3456" / "1234.5678.9012.3456" with no "NIK"/"KTP" word
# nearby — the bare 16-digit boundary regex never sees these because the
# separators break `\b\d{16}\b`'s contiguity). The separated pattern is
# validated (digit-count in {15,16} AND not amount-adjacent) so it does not
# degrade into a bare-digit-run over-matcher (scar family #3) — an
# unlabelled 15/16-digit-with-separators run is a much rarer coincidence in
# ordinary prose than a labelled one, but "IDR 1.234.567.890.123" (a huge
# but plausible amount) is exactly the shape this guard exists to decline.
#
# GROUP 1 (not the whole match) on the label variant: the label text
# ("NIK: ") is kept as literal, unredacted output and only the digit run is
# turned into a placeholder. This matters for dedup (spec rule 1, "the SAME
# original string gets the SAME placeholder"): without it, the SAME NIK
# value quoted once with a label and once bare ("NIK 1234...; ulangi:
# 1234...") would be captured as two DIFFERENT original strings ("NIK
# 1234..." vs "1234...") and get two different placeholders.
_NIK_LABEL_RE = re.compile(r"(?i)\b(?:nik|ktp|no\.?\s*ktp)\b[\s:=#-]*(\d[\d\s.-]{14,25}\d)")
_NIK_BARE_RE = re.compile(r"\b\d{16}\b")
_NIK_SEPARATED_RE = re.compile(r"\b\d(?:[\s.-]?\d){14,15}\b")

# F1b — a list of three 5-digit KBLI codes ("55130 70100 64210") is exactly
# 15 separator-joined digits, so the NIK matcher claimed the whole span and
# redacted this business's DAILY vocabulary out of the package.
#
# The guard declines the KBLI SHAPE, not everything unlike a NIK. An earlier
# attempt required a 4-4-4-4 grouping instead and broke TWO real cases the
# corpus already pinned: a NIK written `32 04 15 12 88 00 0001` (2-digit
# groups — a legitimate way to type one) and a bare 15-digit old-format NPWP.
# Narrow at the false positive, never at the canonical form.
_KBLI_LIST_RE = re.compile(r"\d{5}(?:[\s.-]\d{5}){2}")

# F1 — date shapes, BOTH directions, with the separator pinned by a
# backreference so "20-08.2026" is not a date. The year is anchored to FOUR
# digits on purpose: digits 7-12 of a real NIK encode the date of birth as
# ddmmyy (day +40 for women), so a 2-digit-year rule would decline the
# canonical NIK shape and blind the detector. The decline applies only to
# separator-bearing forms — NEVER to bare digits.
_DATE_SHAPE_RE = re.compile(
    r"(?<!\d)(?:"
    r"(?:0[1-9]|[12]\d|3[01])(?P<dmy_sep>[-./])"
    r"(?:0[1-9]|1[0-2])(?P=dmy_sep)(?:19|20)\d{2}"
    r"|"
    r"(?:19|20)\d{2}(?P<ymd_sep>[-./])"
    r"(?:0[1-9]|1[0-2])(?P=ymd_sep)(?:0[1-9]|[12]\d|3[01])"
    r")(?!\d)"
)

# PASSPORT — reused verbatim from pii_scanner.py, now (Kimi M2) case-
# INSENSITIVE: a lowercase-first-letter passport ("b1234567") is a real
# shape that the original `[A-Z]` char class silently missed. Widening to
# `(?i)` alone would over-match common alphanumeric codes that are NOT
# passports — purchase orders, reference numbers, invoice numbers — so a
# validator declines the letter-prefixes that are near-universally one of
# those instead (Kimi MINOR-4, "PO123456" false-positive). The codebase has
# 5 divergent passport shapes across sentry_config/pii_scanner; per the
# design spec this is the ONE chosen for this module, not an attempt to
# unify the other 4.
_PASSPORT_RE = re.compile(r"(?i)\b[A-Za-z]{1,2}\d{6,7}\b")
# F4: `inv`, `ref` and `sku` are REMOVED and must not come back — they were
# dead entries. `_PASSPORT_RE` captures at most TWO leading letters, so a
# three-letter prefix can never be produced and never be compared here.
_PASSPORT_DECLINE_PREFIXES = frozenset({"po", "no", "id", "pt", "cv", "rp", "os", "wa"})

# F4: the deny-list is context-blind — it refuses a REAL passport that happens
# to start with PO/NO. When the customer says "passport"/"paspor" just before
# the value, that word overrides the deny-list. Bounded window, looking
# BACKWARD only: a mention after the match must not license a redaction.
_PASSPORT_CONTEXT_RE = re.compile(r"(?i)\b(?:passport|paspor)\b")

# BANK_ACCOUNT — label-anchored ONLY (bare digit runs are Bali addresses,
# prices, KBLI codes — scar family #3). Both label-then-digits and
# digits-then-label orderings, "within ~40 chars" per the design spec, plus
# the IBAN shape. GROUP 1 for the same reason as NIK_LABEL above: only the
# account-number digits become the placeholder, the label stays literal.
# Kimi M2: the gap class narrowed from `[^\d\n]` to `[^\d]` — a label and
# its digits split across a newline ("rekening BCA\n1234567890", a common
# WhatsApp line-break) previously never matched because `\n` was excluded
# from the gap; the 0-40 char CAP still bounds how far the gap can reach,
# so this does not turn into an unbounded label...digits-anywhere matcher.
_BANK_LABEL_THEN_DIGITS_RE = re.compile(
    r"(?i)\b(?:no\.?\s*rek(?:ening)?|rekening|acc(?:oun)?t\s*(?:no|number))\b"
    r"[^\d]{0,40}?(\d{8,16})\b"
)
_BANK_DIGITS_THEN_LABEL_RE = re.compile(
    r"(?i)\b(\d{8,16})\b[^\d]{0,40}?"
    r"(?:no\.?\s*rek(?:ening)?|rekening|acc(?:oun)?t\s*(?:no|number))\b"
)
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")

# PHONE — reused verbatim from backend/app/setup/sentry_config.py's four
# hardened sub-patterns (intl-with-separators, intl-contiguous-run,
# Indonesian local 08-form, WhatsApp-JID 62-form), PLUS (Kimi M2) a
# separated 62-form ("62 812 3456 7890", spaces and no leading "+" — the
# bare `\b62\d{9,12}\b` never sees this because the spaces break
# contiguity). Both the contiguous and the separated 62-form now carry a
# validator (Kimi M3): `\b62\d{9,12}\b` alone redacted IDR amounts like
# "total investasi 62500000000 rupiah" as a PHONE — an 11-14-digit run
# starting with "62" is EXACTLY as plausible a rupiah amount as a phone
# number in Indonesian business prose. The validator declines when the run
# reads as an amount (adjacent Rp/IDR/rupiah/juta/miliar/ribu) OR ends in
# "00000" (round amounts are not phone numbers — a WA number never ends in
# five zeros).
_PHONE_INTL_FMT_RE = re.compile(r"\+\d{1,3}[\s()-]{1,3}\d[\d\s()-]{5,16}\d")
_PHONE_INTL_RUN_RE = re.compile(r"\+\d{11,15}\b")
_PHONE_LOCAL_RE = re.compile(r"\b08\d{1,2}[\s.-]?\d{3,4}[\s.-]?\d{3,5}\b")
_PHONE_ID_RE = re.compile(r"\b62\d{9,12}\b")
_PHONE_62_SEPARATED_RE = re.compile(r"\b62[\s.-]?\d(?:[\s.-]?\d){8,12}\b")


def _digits_only(s: str) -> str:
    return "".join(c for c in s if c.isdigit())


# "Not-an-amount" guard shared by the NIK-separated and PHONE-62 validators
# (Kimi M2/M3): a bare/separated digit run adjacent to a Rupiah cue is a
# PRICE, not an identifier. The window is intentionally SHORT (6 chars
# before, 8 after) so it only catches genuine adjacency ("Rp 62.500.000",
# "62500000000 rupiah"), never a same-sentence coincidence several clauses
# away.
_AMOUNT_PREFIX_RE = re.compile(r"(?i)\b(?:rp|idr)\.?\s*$")
# F3: `,-` is the local way to close a Rupiah figure and `IDR` its trailing
# code. `,-` cannot carry a `\b` (both `-` and what follows are non-word
# positions), so it is a separate alternative OUTSIDE the word-boundary group.
_AMOUNT_SUFFIX_RE = re.compile(r"(?i)^\s*(?:(?:rupiah|juta|milyar|miliar|ribu|idr)\b|,-)")


def _looks_like_amount(source: str, match: re.Match[str]) -> bool:
    before = source[max(0, match.start() - 6) : match.start()]
    after = source[match.end() : match.end() + 8]
    return bool(_AMOUNT_PREFIX_RE.search(before)) or bool(_AMOUNT_SUFFIX_RE.match(after))


def _validate_nik_separated(source: str, match: re.Match[str]) -> bool:
    surface = match.group(0)
    digits = _digits_only(surface)
    if len(digits) not in (15, 16):
        return False
    # F1: a separator-bearing date anywhere in the span means the run is a
    # date plus a bystander number, not an identifier. Anchored to a FOUR-digit
    # year, so a real NIK's own ddmmyy block (digits 7-12) cannot trip it.
    if _DATE_SHAPE_RE.search(surface):
        return False
    # F1b: three separator-joined 5-digit codes is a KBLI list, not an
    # identifier. This declines the KBLI SHAPE specifically — the 15/16 digit
    # class above stays, because a bare 15-digit old-format NPWP lives in it.
    if _KBLI_LIST_RE.fullmatch(surface) is not None:
        return False
    return not _looks_like_amount(source, match)


def _validate_phone_digit_count(source: str, match: re.Match[str]) -> bool:
    digits = _digits_only(match.group(0))
    if not (11 <= len(digits) <= 14):
        return False
    if digits.endswith("00000"):
        return False
    return not _looks_like_amount(source, match)


def _validate_passport_prefix(source: str, match: re.Match[str]) -> bool:
    context_before = source[max(0, match.start() - 24) : match.start()]
    if _PASSPORT_CONTEXT_RE.search(context_before):
        return True
    letters = "".join(c for c in match.group(0) if c.isalpha()).lower()
    return letters not in _PASSPORT_DECLINE_PREFIXES


# A validator receives (the text the CURRENT pattern is scanning, the
# match) and returns True to accept (redact it) or False to decline (leave
# the matched text untouched — the same span may still be claimed by a
# LATER pattern/category).
Validator = Callable[[str, "re.Match[str]"], bool]


@dataclass(frozen=True)
class _PatternSpec:
    pattern: re.Pattern[str]
    group: int = 0
    validator: Validator | None = None


# Category names in this set never get a `reversal_map` entry (spalla S1):
# a placeholder is still ISSUED (counted for dedup + the overflow guard,
# recorded in `hits`), but `restore_text` can never look it up — so a
# CREDENTIAL placeholder the model echoes back is stripped by the EXISTING
# unknown-placeholder path, not restored to the customer's own credential.
# Rationale: no legitimate reply ever needs to echo the customer's own
# credential back over WhatsApp, and `wa_finalize.py`'s secret-egress veto
# (jwt/sk-/PEM/bearer patterns mirroring this module's CREDENTIAL category)
# is pointed at what the EXECUTOR leaks — restoring a customer-supplied
# credential first would let the veto discard the whole answer over PII
# that was never the model's to leak in the first place.
_ONE_WAY_CATEGORIES = frozenset({"CREDENTIAL"})

_CATEGORY_PATTERNS: tuple[tuple[str, tuple[_PatternSpec, ...]], ...] = (
    ("EMAIL", (_PatternSpec(_EMAIL_RE),)),
    (
        "CREDENTIAL",
        (
            _PatternSpec(_JWT_RE),
            _PatternSpec(_PEM_RE),
            _PatternSpec(_KEY_PREFIX_RE, validator=_validate_key_prefix),
            _PatternSpec(_BEARER_RE),
        ),
    ),
    (
        "NPWP",
        (
            _PatternSpec(_NPWP_OLD_RE),
            _PatternSpec(_NPWP_NEW16_RE),
            _PatternSpec(_NPWP_NEW_DOTTED_RE),
        ),
    ),
    (
        "NIK_KTP",
        (
            _PatternSpec(_NIK_LABEL_RE, group=1),
            _PatternSpec(_NIK_BARE_RE),
            _PatternSpec(_NIK_SEPARATED_RE, validator=_validate_nik_separated),
        ),
    ),
    ("PASSPORT", (_PatternSpec(_PASSPORT_RE, validator=_validate_passport_prefix),)),
    (
        "BANK_ACCOUNT",
        (
            _PatternSpec(_BANK_LABEL_THEN_DIGITS_RE, group=1),
            _PatternSpec(_BANK_DIGITS_THEN_LABEL_RE, group=1),
            _PatternSpec(_IBAN_RE),
        ),
    ),
    (
        "PHONE",
        (
            _PatternSpec(_PHONE_INTL_FMT_RE),
            _PatternSpec(_PHONE_INTL_RUN_RE),
            _PatternSpec(_PHONE_LOCAL_RE),
            _PatternSpec(_PHONE_ID_RE, validator=_validate_phone_digit_count),
            _PatternSpec(_PHONE_62_SEPARATED_RE, validator=_validate_phone_digit_count),
        ),
    ),
)


class _RedactionState:
    """Per-package mutable state: placeholder numbering, value dedup and the
    reversal map — shared across every string redacted for one package (all
    of history, chunks AND the pricing search_query, spec M1) so "the SAME
    original string gets the SAME placeholder" (spec rule 1) holds
    everywhere, not just within one string. See the module docstring's
    DECLARED LIMITS for the dedup-on-surface-form scope of that guarantee.
    """

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}
        self._value_to_placeholder: dict[str, str] = {}
        self.reversal_map: dict[str, str] = {}
        self.hits: list[DlpHit] = []

    def placeholder_for(self, category: str, original: str) -> str:
        existing = self._value_to_placeholder.get(original)
        if existing is not None:
            return existing
        n = self._counts.get(category, 0) + 1
        self._counts[category] = n
        placeholder = f"[PII-{category}-{n}]"
        self._value_to_placeholder[original] = placeholder
        if category not in _ONE_WAY_CATEGORIES:
            self.reversal_map[placeholder] = original
        self.hits.append(DlpHit(category=category, placeholder=placeholder))
        # Counts placeholder ISSUANCE (`_value_to_placeholder`), not
        # `reversal_map`'s size — a one-way category still counts toward
        # the overflow guard even though it never reaches reversal_map.
        if len(self._value_to_placeholder) > MAX_PLACEHOLDERS:
            raise DlpOverflow(
                f"package would carry more than {MAX_PLACEHOLDERS} distinct "
                "redacted values"
            )
        return placeholder


def _splice_placeholder(
    match: re.Match[str], group: int, category: str, state: _RedactionState
) -> str:
    """Redact `match.group(group)`, leaving any label/context text the
    pattern also matched (group 0 minus that span) untouched in the
    output. `group == 0` is the common case: the whole match IS the
    value, so this degenerates to a plain whole-match replacement."""
    original = match.group(group)
    placeholder = state.placeholder_for(category, original)
    if group == 0:
        return placeholder
    full = match.group(0)
    match_start = match.start(0)
    prefix = full[: match.start(group) - match_start]
    suffix = full[match.end(group) - match_start :]
    return f"{prefix}{placeholder}{suffix}"


def _redact_or_decline(
    match: re.Match[str], spec: _PatternSpec, category: str, state: _RedactionState, source: str
) -> str:
    """The `.sub()` callback: consult the spec's validator (if any) against
    `source` — the string this PARTICULAR `.sub()` call is scanning, so
    `match.start()/end()` line up with it — and leave the text unchanged
    when the validator declines (a later pattern/category may still claim
    the same span)."""
    if spec.validator is not None and not spec.validator(source, match):
        return match.group(0)
    return _splice_placeholder(match, spec.group, category, state)


def _redact_one(text: str, state: _RedactionState) -> str:
    for category, specs in _CATEGORY_PATTERNS:
        for spec in specs:
            source = text
            text = spec.pattern.sub(
                lambda m, _category=category, _spec=spec, _source=source: _redact_or_decline(
                    m, _spec, _category, state, _source
                ),
                source,
            )
    return text


def redact_package_fields(
    history: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    search_query: str | None = None,
) -> DlpResult:
    """Redact every free-text field the package builder ships: each
    `history[i]["content"]`, each `chunks[i]["text"]`, and (spec M1) the
    pricing lookup's own echoed `search_query` — `pricing_block` otherwise
    ships the customer's RAW query into the wire+hash unredacted even
    though it is, verbatim, the same text already redacted in `history`.
    Nothing else — the package's other fields are structured non-free-text
    by the builder's own allowlist (spec rule 3).

    Pure function: no I/O, no logging of any ORIGINAL matched string (only
    a category+count summary). Raises `DlpOverflow` if a single package
    would need more than `MAX_PLACEHOLDERS` distinct redacted values — the
    caller (`wa_package_builder.build_context_package`) converts ANY
    exception from this call into `PackageUnbuildable("dlp_error")`
    (fail-closed, spec rule 7).

    Returns a `DlpResult` (history/chunks/search_query redacted,
    reversal_map, hits). `reversal_map` maps placeholder -> original and
    must never travel beyond the caller that keeps it local to one build
    (see wa_dlp module docstring and wa_codex_leg._attempt). CREDENTIAL
    placeholders never appear in `reversal_map` at all (one-way category,
    spalla S1) even though they DO count toward the overflow guard and DO
    appear in `hits`.
    """
    state = _RedactionState()

    redacted_history = [
        {**entry, "content": _redact_one(str(entry.get("content", "")), state)}
        for entry in history
    ]
    redacted_chunks = [
        {**chunk, "text": _redact_one(str(chunk.get("text", "")), state)} for chunk in chunks
    ]
    redacted_search_query = (
        _redact_one(search_query, state) if search_query else search_query
    )

    if state.hits:
        counts_by_category: dict[str, int] = {}
        for hit in state.hits:
            counts_by_category[hit.category] = counts_by_category.get(hit.category, 0) + 1
        # Category + count ONLY — never the matched value (project CLAUDE.md
        # §14 PII boundary; this module's own docstring repeats the rule).
        logger.info("wa_dlp: redacted %s", counts_by_category)

    return DlpResult(
        history=redacted_history,
        chunks=redacted_chunks,
        search_query=redacted_search_query,
        reversal_map=state.reversal_map,
        hits=state.hits,
    )


def restore_text(text: str, reversal_map: dict[str, str]) -> str:
    """Substitute placeholders back to their original values.

    An unknown/hallucinated placeholder shape — the generator emitted a
    `[PII-CATEGORY-N]` token that was never issued for THIS package (wrong
    category, wrong n, a shape it invented outright, OR a legitimately
    one-way CREDENTIAL placeholder that was never in `reversal_map` to
    begin with — spalla S1) — is STRIPPED (never shown to the client),
    never restored to garbage or left as a raw placeholder in a
    client-facing reply. Fail-visible via a WARNING log naming only the
    COUNT, never the text.

    A near-miss placeholder shape (lowercase, unclosed brackets, extra
    whitespace) matches neither this function's regex NOR the unknown-
    placeholder branch — it passes through unchanged. Declared limit, see
    the module docstring's DECLARED LIMITS.

    R26-adjacent (spec discipline): this function never scans the codex
    ANSWER for new PII — restore only, per the reversal map built at
    redact time.
    """
    unknown = 0

    def _sub(match: re.Match[str]) -> str:
        nonlocal unknown
        placeholder = match.group(0)
        original = reversal_map.get(placeholder)
        if original is None:
            unknown += 1
            return ""
        return original

    restored = _PLACEHOLDER_RE.sub(_sub, text)
    if unknown:
        logger.warning("wa_dlp: restore_text stripped %d unknown placeholder(s)", unknown)
    return restored
