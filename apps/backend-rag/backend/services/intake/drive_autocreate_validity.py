"""Creation-validity rules for drive contact auto-create (wave 1).

Validation is NOT normalization — two named layers, kept separate on purpose
(spec: research/operations/2026-07-19-drive-contact-autocreate-design.md, v3
point 6):

- **Matching normalization** belongs to ``routing.py`` (``_normalize_passport``
  strip+upper, ``_ascii_digits``): it decides EQUALITY against the client book
  and this module mirrors those projections exactly so a value validated here
  matches with the matcher's own semantics.
- **Creation validity** (this module) decides whether an extracted value is
  strong enough to MINT a new identity from. Deliberately STRICTER: a value
  good enough to match against is not automatically good enough to create a
  person card. Verified 2026-07-19: no pre-existing validator applies length
  bounds (``ClientValidator.validate_passport`` is ``[A-Z0-9]+`` only), so the
  bounds live HERE, named and unit-tested.

Bounds:

- passport: 6-9 alphanumerics with >=1 digit (ICAO 9303 caps machine-readable
  passport numbers at 9 characters; <6 is OCR-fragment territory).
- kitas: >=6 alphanumerics with >=1 digit (observed corpus format; no reliable
  upper bound documented, so none imposed).
- npwp: exactly 15 or 16 ASCII digits (mirror of the m248 matcher rule).
- name: >=5 chars after whitespace-collapse, >=2 letters, not a placeholder
  token (mirror of the census v1 rule, single Python home).

Every function returns the CANONICAL value on success and ``None`` on
rejection — callers never re-normalize.
"""

from __future__ import annotations

import re

# EXACT mirrors of the matcher's projections (gate round-3 R3-4: an earlier
# draft stripped EVERY non-alphanumeric, so `AB#123456` canonicalized
# differently here than in routing._normalize_id — divergent book comparison).
# routing strips ONLY whitespace/dot/dash/slash; digits are ASCII-class.
_SEPARATOR_STRIP_RE = re.compile(r"[\s.\-/]")
_DIGIT_STRIP_RE = re.compile(r"[^0-9]")

PASSPORT_RE = re.compile(r"^(?=.*[0-9])[A-Z0-9]{6,9}$")
KITAS_RE = re.compile(r"^(?=.*[0-9])[A-Z0-9]{6,}$")

_NAME_PLACEHOLDER_RE = re.compile(
    r"^(UNKNOWN|N/?A|NAME|NONE|NULL|TRUE|FALSE|UNDEFINED)$"
)
_NAME_MIN_LEN = 5


def canonical_alnum(value: object) -> str | None:
    """Strip separators + upper-case — routing._normalize_id verbatim.

    Only ``[\\s.\\-/]`` is stripped (NOT every symbol): a value like
    ``AB#123456`` keeps its ``#`` and must canonicalize identically here and
    in the matcher. The creation regexes below then reject any residual
    symbol — such a value is creation-INVALID, never silently cleaned.
    """
    if value is None:
        return None
    s = _SEPARATOR_STRIP_RE.sub("", str(value)).upper()
    return s or None


def canonical_digits(value: object) -> str | None:
    """ASCII-digits-only projection — routing's npwp comparison side."""
    if value is None:
        return None
    d = _DIGIT_STRIP_RE.sub("", str(value))
    return d or None


def valid_passport(value: object) -> str | None:
    """Canonical passport number iff it meets the creation bound, else None."""
    canon = canonical_alnum(value)
    if canon is None or not PASSPORT_RE.match(canon):
        return None
    return canon


def valid_kitas(value: object) -> str | None:
    """Canonical KITAS number iff it meets the creation bound, else None."""
    canon = canonical_alnum(value)
    if canon is None or not KITAS_RE.match(canon):
        return None
    return canon


def valid_npwp(value: object) -> str | None:
    """Canonical NPWP iff exactly 15/16 ASCII digits, else None."""
    canon = canonical_digits(value)
    if canon is None or len(canon) not in (15, 16):
        return None
    return canon


_NAME_STRUCTURAL_RE = re.compile(r'[{}\[\]"\\:=<>|]')


def valid_name(value: object) -> str | None:
    """Whitespace-collapsed upper-cased subject name, or None if too weak.

    Rejects fragments (<5 chars), digit/symbol soup (<2 letters),
    placeholder tokens the OCR emits for unreadable name fields, and any
    string carrying JSON/markup STRUCTURAL characters (R12-1: a field
    whose 'value' member is a STRING containing serialized JSON —
    '{"label":"JOHN SMITH"}' — is scalar-typed and sails through the SQL
    projection; no legitimate person name contains {}[]"\\:=<>|, so the
    validator is the right guard, shared by census and probes alike).

    R13-1: the placeholder set also covers bare JSON LITERAL tokens
    (null/true/false/undefined) — structural-char-free serialized JSON
    like the string 'false' has 5 letters and no structural characters, so
    it would otherwise survive both gates above.
    """
    if value is None:
        return None
    collapsed = re.sub(r"\s+", " ", str(value).strip()).upper()
    if len(collapsed) < _NAME_MIN_LEN:
        return None
    if not re.search(r"[A-Z]{2}", collapsed):
        return None
    if _NAME_PLACEHOLDER_RE.match(collapsed):
        return None
    if _NAME_STRUCTURAL_RE.search(collapsed):
        return None
    return collapsed


# kind -> validator, the single dispatch table census/apply share.
VALIDATORS = {
    "passport": valid_passport,
    "kitas": valid_kitas,
    "npwp": valid_npwp,
}
