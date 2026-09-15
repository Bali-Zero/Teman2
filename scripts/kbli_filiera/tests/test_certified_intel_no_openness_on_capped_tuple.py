"""Guard: a `located` + capped (`pma_max_asing < 100`) record's CERTIFIED
text must never still assert national openness — the class of defect W-H
PR-3b found by hand on 5 of its own 8 codes (the mechanical detector in
`cure_prose_national_openness.py`/`cure_gold_pma_line.py` is blind to the
template "Nationally this carries PMA status: Open." and to zantaraOpener/
baliContext prose; see those two compilers' own docstrings). This guard does
NOT extend either detector (out of this lane's code budget) — it is a
read-only regex sweep of the text `data/kbli-filiera/pma-editorial-
certifications.json` actually certifies, run as a pytest guard so a future
allocation that reintroduces the pattern fails CI instead of shipping quietly.

WHAT COUNTS AS "CERTIFIED TEXT": the registry's `canonicalIntel`/`mouthGold`/
`standaloneGold` sections store a hash of the WHOLE object each section
certifies (`stable_editorial_sha256`, mirrored from
`kbli_editorial_certification.py` / `recert.py`) — canonical's own
`intel_2026`, the mouth gold entry, or the standalone-navigator gold entry.
This guard reads those same objects live (never the hash) and regex-sweeps
every string value in them.

Population: only codes the registry actually certifies, restricted to
`pma_verification_status == "located"` AND `pma_max_asing < 100` on the
CURRENT canonical record — a genuinely open (TERBUKA/100) or still-
`declared_gap` code is out of scope by design (innocence fixture below).

RATCHET, not a plain red/green gate (Dux decision, SAETTA-20260915 W-H
PR-3b): `BASELINE` names every pre-existing `(section, code, field)` debt
tuple this guard tolerates; the live test asserts STRICT equality against
it both ways — no offender outside `BASELINE` (no new debt) and no
`BASELINE` entry that has stopped offending (no un-shrunk baseline; a cure
must delete the tuple here, not just fix the text). `REVIEWED_TRUE_TEXT`
is a separate allowlist for text that is TRUE and was reviewed, not debt —
keyed on `(section, code, field, exact_substring, reason)` so a future
wording change on that same field still fires (containment of the exact
string, not identity of the field).

`BASELINE` targets the state AFTER PR-3c (curing 29 certified fields and
de-certifying the 47111 gold entries) lands on `main`, which merges BEFORE
this PR — so `BASELINE` is empty here by design. This guard will NOT run
green on this branch's own un-merged base (PR-3c hasn't cured those fields
here yet); that is expected and accepted per the Dux, who reconciles it
when she merges `main` post-PR-3c.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
REGISTRY = REPO_ROOT / "data" / "kbli-filiera" / "pma-editorial-certifications.json"
GOLD = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-gold-all.json"

sys.path.insert(0, str(REPO_ROOT / "apps" / "backend-rag"))
sys.path.insert(0, str(REPO_ROOT / "apps" / "backend-rag" / "backend" / "scripts"))

# The exact pattern named by the Dux (SAETTA-20260915 W-H PR-3b), case-insensitive.
OPENNESS_RE = re.compile(
    r"PMA status: (Open|Terbuka)|open to (foreign|PMA)|100 ?% (foreign|PMA|open)|fully open|"
    r"PMA[- ]friendly|your PT PMA|Typical structure: PT PMA|PT PMA setup|"
    r"foreign[- ]owned (shop|store|retail)",
    re.IGNORECASE,
)


def _walk_strings(node: Any, path: str = "") -> list[tuple[str, str]]:
    """Every (dotted-path, text) leaf string under `node`."""
    out: list[tuple[str, str]] = []
    if isinstance(node, str):
        out.append((path, node))
    elif isinstance(node, dict):
        for k, v in node.items():
            out.extend(_walk_strings(v, f"{path}.{k}" if path else str(k)))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out.extend(_walk_strings(v, f"{path}[{i}]"))
    return out


def offending_strings(obj: Any) -> list[tuple[str, str, str]]:
    """(path, matched-text, full-string) for every leaf string of `obj` that
    the openness regex hits. Pure — no I/O, exercised directly by the
    fixture-based guilt/innocence tests below."""
    return [
        (path, m.group(0), text)
        for path, text in _walk_strings(obj)
        for m in [OPENNESS_RE.search(text)]
        if m
    ]


def qualifies(record: dict[str, Any]) -> bool:
    """A record enters the guarded population only when its CURRENT tuple is
    `located` and genuinely capped below 100 — a TERBUKA/100 or still-
    `declared_gap` record is not this guard's business (innocence fixture)."""
    cap = record.get("pma_max_asing")
    return (
        record.get("pma_verification_status") == "located"
        and isinstance(cap, int)
        and cap < 100
    )


# ---------------------------------------------------------------------------
# Ratchet baseline + reviewed-true allowlist (Dux decision, SAETTA-20260915
# W-H PR-3b). See module docstring for the two-way equality this enforces.
# ---------------------------------------------------------------------------

# (section, code, field) — pre-existing debt this guard tolerates. Empty:
# targets the state AFTER PR-3c cures the corpus; see module docstring.
BASELINE: frozenset[tuple[str, str, str]] = frozenset()

# (section, code, field, exact_substring, reason) — TRUE text, reviewed by
# PR-3c, never debt. Matched on (section, code, field) AND containment of
# the exact substring, so different wording on the same field still fires.
REVIEWED_TRUE_TEXT: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "canonicalIntel",
        "50126",
        "editorial.body",
        "capped at 49%, rather than being fully open",
        "negation: the sentence states the national cap IS 49%, not full openness — "
        "the regex's 'fully open' hit is inside a clause denying it.",
    ),
    (
        "canonicalIntel",
        "51101",
        "editorial.headline",
        "Open to PMA in Bali",
        "Bali-axis: 51101 is nationally TERBATAS/49%, but Bali carries no moratorium "
        "block for it (Besar-scale risk is medium-high/high) — the headline's claim "
        "is scoped to Bali, not the national cap, and is true as written.",
    ),
)


def _reviewed_reason(section: str, code: str, path: str, text: str) -> str | None:
    """The allowlist reason if this exact offender is reviewed-true text,
    else None. Containment of `exact_substring`, not just field identity —
    so a wording change on the same field is NOT silently excused."""
    for r_section, r_code, r_field, exact_substring, reason in REVIEWED_TRUE_TEXT:
        if (
            section == r_section
            and code == r_code
            and path == r_field
            and exact_substring in text
        ):
            return reason
    return None


# ---------------------------------------------------------------------------
# Fixture-based guilt + innocence (no I/O) — the guard's own TDD anchor.
# ---------------------------------------------------------------------------


def test_guilt_flags_the_pma_status_open_template():
    """The exact template W-H PR-3b found on 4 of its own 8 codes' canonical
    zantaraOpener, cap 0 / located — the guard's core detection duty."""
    certified_intel = {
        "zantaraOpener": "Nationally this carries PMA status: Open. Let me walk you through it.",
        "whatYouNeed": "The national foreign-ownership ceiling for this activity is 0%.",
    }
    hits = offending_strings(certified_intel)
    assert hits, "guilt fixture must be flagged: a capped/located record's certified text still asserts national openness"
    assert any("PMA status: Open" in h[2] for h in hits)


def test_guilt_flags_gold_fully_open_sentence():
    """The gold whatYouNeed line the reference lane's cure_gold_pma_line.py
    could not mechanically patch on 47712/47722 (a condition beyond the bare
    percentage) — flagged here as raw text regardless of who fixes it."""
    mouth_gold_entry = {
        "whatYouNeed": "**PMA:** Fully open (TERBUKA), 100% foreign ownership allowed.",
    }
    hits = offending_strings(mouth_gold_entry)
    assert hits
    assert any("fully open" in h[1].lower() or "100" in h[1] for h in hits)


def test_innocence_ignores_crosswalk_percentage_match_wording():
    """'100% match' is a crosswalk/identity claim, not an ownership claim —
    the regex requires 'foreign'/'PMA'/'open' immediately after the percent
    sign, so this must NOT be flagged."""
    certified_intel = {
        "editorial": {"body": "The 2020 and 2025 codes are a 100% match on scope and description."},
    }
    assert offending_strings(certified_intel) == []


def test_innocence_genuinely_open_record_is_out_of_population():
    """A TERBUKA/100 record saying 'open to foreign ownership' is telling the
    truth — it must never enter the guarded population in the first place,
    regardless of what its text says. `qualifies()` is the gate; the regex is
    never even consulted for it in the live-data test below."""
    record = {"pma_verification_status": "located", "pma_max_asing": 100}
    assert not qualifies(record)
    declared_gap_record = {"pma_verification_status": "declared_gap", "pma_max_asing": 0}
    assert not qualifies(declared_gap_record)
    capped_record = {"pma_verification_status": "located", "pma_max_asing": 0}
    assert qualifies(capped_record)


def test_innocence_reviewed_true_text_is_excused_on_exact_substring():
    """The 2 PR-3c-reviewed TRUE offenders are excused ONLY when the exact
    reviewed substring is present — proving the allowlist is substring-
    keyed, not field-keyed."""
    assert _reviewed_reason(
        "canonicalIntel",
        "50126",
        "editorial.body",
        "Nationally, the activity is TERBATAS: foreign ownership is "
        "capped at 49%, rather than being fully open. In Bali...",
    )
    assert _reviewed_reason(
        "canonicalIntel",
        "51101",
        "editorial.headline",
        "Scheduled Commercial Air Transport Is Open to PMA in Bali",
    )


def test_innocence_reviewed_true_text_does_not_excuse_other_wording():
    """A DIFFERENT sentence on the same (section, code, field) must still
    fire — the allowlist is keyed on the exact reviewed substring, not on
    field identity, so a future regression on 50126/51101 is not silently
    swallowed by their own past review."""
    assert _reviewed_reason(
        "canonicalIntel", "50126", "editorial.body", "This activity is fully open to PMA."
    ) is None
    assert _reviewed_reason(
        "canonicalIntel", "51101", "editorial.headline", "Fully open to foreign investment."
    ) is None
    # Same exact substring, wrong field or wrong code: also not excused.
    assert _reviewed_reason(
        "canonicalIntel", "51101", "zantaraOpener", "Open to PMA in Bali"
    ) is None
    assert _reviewed_reason(
        "canonicalIntel", "50135", "editorial.headline", "Open to PMA in Bali"
    ) is None


# ---------------------------------------------------------------------------
# Live-data guard: every code the registry currently certifies.
# ---------------------------------------------------------------------------


def _load_canonical_by_code() -> dict[str, dict]:
    payload = json.loads(CANONICAL.read_text(encoding="utf-8"))
    records = payload["data"] if isinstance(payload, dict) else payload
    return {str(r["kode_kbli_2025"]): r for r in records}


def _load_gold() -> dict[str, dict]:
    if not GOLD.exists():
        return {}
    return json.loads(GOLD.read_text(encoding="utf-8"))


def _load_standalone_gold() -> dict[str, dict]:
    try:
        from index_kbli_gold_content import GOLD_CONTENT_FILE, parse_gold_content_ts
    except Exception:
        return {}
    if not GOLD_CONTENT_FILE.exists():
        return {}
    try:
        return parse_gold_content_ts(GOLD_CONTENT_FILE)
    except Exception:
        return {}


def test_no_current_certified_entry_asserts_openness_on_a_capped_tuple():
    """Walks every code the registry actually certifies today. Skips a code
    the registry names but the live source no longer carries (a stale
    registry entry is `recert.py`'s job to catch, not this guard's). Ratchet
    (see module docstring): every hit is either (a) `REVIEWED_TRUE_TEXT`
    (excused, true), (b) in `BASELINE` (pre-existing, tolerated, must still
    offend), or (c) new — and (c) fails the build. This guard NEVER edits
    certified text; it only names offenders."""
    if not REGISTRY.exists():
        pytest.skip("no editorial certification registry on this checkout")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    by_code = _load_canonical_by_code()
    gold = _load_gold()
    standalone = _load_standalone_gold()

    sources = {
        "canonicalIntel": lambda code: (by_code.get(code) or {}).get("intel_2026"),
        "mouthGold": lambda code: gold.get(code),
        "standaloneGold": lambda code: standalone.get(code),
    }

    found: dict[tuple[str, str, str], str] = {}
    for section, getter in sources.items():
        for code in registry.get(section) or {}:
            record = by_code.get(code)
            if record is None or not qualifies(record):
                continue
            content = getter(code)
            if content is None:
                continue
            for path, match, text in offending_strings(content):
                if _reviewed_reason(section, code, path, text) is not None:
                    continue  # TRUE text, reviewed — not debt.
                found[(section, code, path)] = f"{match!r} in {text[:120]!r}"

    found_keys = frozenset(found)
    new_debt = found_keys - BASELINE
    shrunk = BASELINE - found_keys  # a baseline entry that stopped offending

    assert not new_debt, (
        "certified text asserts national openness on a capped/located record and "
        "is NOT in BASELINE or REVIEWED_TRUE_TEXT — do NOT edit certified text to "
        "silence this; report the offenders:\n  "
        + "\n  ".join(f"{s}.{c}.{p}: {found[(s, c, p)]}" for s, c, p in sorted(new_debt))
    )
    assert not shrunk, (
        "BASELINE names a (section, code, field) that no longer offends — delete "
        "it from BASELINE instead of leaving a stale entry:\n  "
        + "\n  ".join(f"{s}.{c}.{p}" for s, c, p in sorted(shrunk))
    )
