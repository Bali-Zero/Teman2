"""Tripwire tests for the two data-invariants that have NO other guard.

These are the "silent corruption" class (CLAUDE.md §9): a plausible change
passes every other test and CI-green while breaking something expensive.
Because the repo runs on `required-checks + auto-merge, no human review`, the
gate for this class must be a test, not a reviewer.

Born 2026-07-16 from two real gaps found the same day:
  1. The homepage_hero LeadSource drift 422'd the primary CTA for 10 days
     (#2495) — nothing linked the frontend `source=` to the backend enum.
  2. The FROZEN embedding model had no test pinning it, though a change
     silently invalidates 93,283 vectors.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

from backend.core import embeddings
from backend.services.lead_capture.source import LeadSource


def _repo_root() -> Path:
    """Walk up from this file until the dir that contains apps/."""
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "apps").is_dir():
            return p
        p = p.parent
    raise AssertionError("repo root (dir containing apps/) not found from test file")


# ---------------------------------------------------------------------------
# Invariant 1 — frontend lead sources ⊆ backend LeadSource enum
# ---------------------------------------------------------------------------

_SOURCE = re.compile(r'source="([a-z_]+)"')


def _frontend_lead_sources() -> dict[str, str]:
    """Every literal `source="..."` in mouth's non-test .tsx → the file it's in.

    NOT anchored to one component name. There are several lead-capture CTAs
    (WhatsAppLeadButton, AppWhatsAppCTA, ServicePricing, KBLIConsultationCTA,
    ...); anchoring to any single one would be an under-match (scar W82) that
    silently misses a value sent from a component the anchor forgot. Verified
    2026-07-16: EVERY `source="..."` literal in mouth (tests excluded) is a
    lead source — there is no unrelated `source=` prop — so a full scan is both
    complete and false-positive-free today. If a future non-lead `source=`
    prop appears, this test fails LOUDLY (clear message, add-to-enum or exclude)
    rather than a component-anchored scan failing SILENTLY — loud-wrong beats
    silent-blind for a tripwire.

    Test files are excluded: they carry deliberately-invalid sources.
    Only literals are covered — `source={variable}` is out of reach and is a
    separate, harder contract (documented limitation, not a silent hole).
    """
    mouth_src = _repo_root() / "apps" / "mouth" / "src"
    assert mouth_src.is_dir(), f"mouth src missing at {mouth_src}"
    found: dict[str, str] = {}
    for tsx in mouth_src.rglob("*.tsx"):
        if tsx.name.endswith(".test.tsx"):
            continue
        text = tsx.read_text(encoding="utf-8")
        for m in _SOURCE.finditer(text):
            found.setdefault(m.group(1), str(tsx.relative_to(_repo_root())))
    return found


def test_frontend_lead_sources_are_all_valid_enum_values() -> None:
    """A frontend source the backend enum lacks = 422 on every click, silent.

    This is the exact gap that hid the homepage_hero bug for 10 days (#2495).
    """
    found = _frontend_lead_sources()

    # Blindness guard (scars W82/W97): a scan that finds ~nothing must FAIL, not
    # pass green. There are 7 lead sources across the site today; a drop below 3
    # means the `source=` pattern stopped matching (prop renamed / files moved)
    # and the test went blind, not that the site lost its CTAs.
    assert len(found) >= 3, (
        f"Only {len(found)} frontend lead source(s) found ({sorted(found)}) — "
        "expected the site's several lead-capture CTAs. The scan looks blind: "
        "did the `source` prop get renamed or the CTAs move? Fix this test "
        "before trusting a green."
    )

    valid = {s.value for s in LeadSource}
    unknown = {v: f for v, f in found.items() if v not in valid}
    assert not unknown, (
        "Frontend sends lead source(s) the backend LeadSource enum does not "
        f"define → POST /api/lead/capture returns 422 and the lead is never "
        f"written: {unknown}. Add the value to "
        "apps/backend-rag/backend/services/lead_capture/source.py (with its two "
        "@property entries) or fix the frontend."
    )


# ---------------------------------------------------------------------------
# Invariant 2 — OpenAI embedding model is FROZEN (text-embedding-3-small / 1536)
# ---------------------------------------------------------------------------


def test_openai_embedding_model_is_frozen() -> None:
    """text-embedding-3-small @ 1536 dims is FROZEN — a change invalidates the
    93,283 existing vectors with no other test failure (CLAUDE.md §9).

    This is a canary on the OpenAI init path specifically (the Sentence
    Transformers fallback deliberately uses a different model/dims). If you are
    running a real re-index, update this test in the SAME PR — that conscious
    edit is the whole point of the guard.
    """
    src = inspect.getsource(embeddings.EmbeddingsGenerator._init_openai)
    assert '"text-embedding-3-small"' in src, (
        "The OpenAI embedding default model changed away from the FROZEN "
        "text-embedding-3-small. This invalidates 93,283 existing vectors. If "
        "intentional, it needs a re-index plan and this test updated together."
    )
    assert "1536" in src, (
        "The OpenAI embedding dimensions changed away from the FROZEN 1536. "
        "Mismatched dims corrupt every similarity search against the existing "
        "index."
    )
