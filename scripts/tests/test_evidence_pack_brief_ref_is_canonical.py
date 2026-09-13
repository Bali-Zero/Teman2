"""Every NEW evidence pack must declare the canonical staging brief_ref.

THE CONTRACT (`scripts/ci/evidence_paths.py`, module docstring): a per-PR pack
at `evidence/<YYYY-MM>/<slug>/pack.yml` must still declare the literal
`brief_ref: evidence/brief.yml`. `harness-floor.yml` Step 7b never lints a pack
in place -- it stages pack and brief into a synthetic
`/tmp/evidence-check/evidence/{pack,brief}.yml` tree and lints THAT with
`--repo-root` pointed at it, so `brief_ref` resolves against the staging layout.
A pack naming its own real path fails with `does not resolve to a file on disk`,
a message that never mentions staging. evidence_paths.py calls this "exactly the
shape of trap this module exists to remove".

WHY A SWEEP, WHEN evidence_pack_lint.py ALREADY REFUSES SUCH A PACK. It refuses
it only on a PR the harness-floor gate actually runs, and the gate executes the
copy of itself recorded at the PR's BASE sha -- so a PR whose base predates the
gate never runs it. Five packs reached main that way. A per-PR gate cannot close
a hole it was not present for.

WHY THIS IS A RATCHET AND NOT A CLEAN SWEEP. Those five cannot currently be
fixed. `resolve_evidence_path` identifies "this PR's evidence" by asking which
`evidence/**/pack.yml` the diff touches, and refuses to guess when the diff
touches more than one. A PR whose SUBJECT is other lanes' packs therefore
always fails closed, and `harness-floor.yml` exposes no override
(`workflow_dispatch: {}` -- no inputs). Measured 2026-09-01: no commit since
2026-08-01 touches two or more `pack.yml` files, and `Harness floor recompute`
is a required check -- so this has never been done and cannot be, until the
resolver can tell a pack a PR OWNS from one it merely edits. The five are
named below with that reason rather than silently tolerated: the ratchet stops
the sixth, and the list is the debt, visible and countable.

Guilt AND innocence, per superscar #3. The innocence case is not decorative:
the first sweep written for this matched `brief_ref:` with a regex and
"corrected" a pack whose value was already canonical but carried an inline YAML
comment -- the comment was captured as part of the value. The predicate must
PARSE the YAML, and the test pins that.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
EVIDENCE = REPO / "evidence"

CANONICAL_BRIEF_REF = "evidence/brief.yml"

_LEGACY_REASON = (
    "landed before the harness-floor gate armed on its base sha; not fixable "
    "in place while resolve_evidence_path refuses a diff touching >1 pack.yml"
)

# Frozen 2026-09-01. This list may only ever SHRINK. Adding to it means a new
# pack drifted, which is the thing this test exists to prevent.
KNOWN_LEGACY_NON_CANONICAL: dict[str, str] = {
    "evidence/2026-08/agent-nuzantara-craft-d-codec-jsonb-default-str-c9e5b351/pack.yml": _LEGACY_REASON,
    "evidence/2026-08/agent-nuzantara-craft-d-jsonb-real-column-arming-48fc41e8/pack.yml": _LEGACY_REASON,
    "evidence/2026-08/agent-nuzantara-craft-e-acceptance-probe-lint-4ec4ffc0/pack.yml": _LEGACY_REASON,
    "evidence/2026-08/agent-nuzantara-craft-e-appetite-ceiling-ed1409e7/pack.yml": _LEGACY_REASON,
    "evidence/2026-08/agent-nuzantara-craft-e-assumptions-register-ece48074/pack.yml": _LEGACY_REASON,
}


def _declared_brief_ref(pack_text: str) -> str | None:
    """The pack's brief_ref as YAML sees it -- comments and quoting removed by
    the parser, never by hand."""
    doc = yaml.safe_load(pack_text) or {}
    if not isinstance(doc, dict):
        return None
    value = doc.get("brief_ref")
    return value if isinstance(value, str) else None


def _non_canonical_packs() -> list[str]:
    out = []
    for pack in sorted(EVIDENCE.rglob("pack.yml")):
        declared = _declared_brief_ref(pack.read_text(encoding="utf-8"))
        if declared is not None and declared != CANONICAL_BRIEF_REF:
            out.append(pack.relative_to(REPO).as_posix())
    return out


def test_no_pack_outside_the_frozen_legacy_list_drifts() -> None:
    """The ratchet. A NEW pack naming its own brief path reddens this."""
    offenders = [p for p in _non_canonical_packs() if p not in KNOWN_LEGACY_NON_CANONICAL]
    assert not offenders, (
        "these packs name their real per-PR brief path instead of the canonical "
        f"staging literal {CANONICAL_BRIEF_REF!r} (see scripts/ci/evidence_paths.py). "
        "Write the literal value; do NOT add them to KNOWN_LEGACY_NON_CANONICAL:\n  "
        + "\n  ".join(offenders)
    )


def test_the_legacy_list_never_grows_and_every_entry_is_still_real() -> None:
    """The list may only shrink. An entry that no longer drifts must be deleted,
    or the list slowly becomes a place to hide a live defect."""
    actual = set(_non_canonical_packs())
    stale = sorted(set(KNOWN_LEGACY_NON_CANONICAL) - actual)
    assert not stale, (
        "these are listed as legacy but are now canonical — remove them from "
        "KNOWN_LEGACY_NON_CANONICAL:\n  " + "\n  ".join(stale)
    )
    assert all(KNOWN_LEGACY_NON_CANONICAL.values()), "every legacy entry must carry a reason"


def test_a_per_pr_brief_ref_is_recognised_as_wrong() -> None:
    """GUILT: the shape that actually reached main must be detected."""
    declared = _declared_brief_ref(
        "brief_ref: evidence/2026-08/agent-nuzantara-craft-e-appetite-ceiling-ed1409e7/brief.yml\n"
    )
    assert declared != CANONICAL_BRIEF_REF


def test_the_canonical_value_passes_even_with_an_inline_comment_or_quotes() -> None:
    """INNOCENCE: both real spellings on main are correct and must not be 'fixed'."""
    with_comment = _declared_brief_ref(
        "brief_ref: evidence/brief.yml # STAGING layout, never the real per-PR path\n"
    )
    quoted = _declared_brief_ref('brief_ref: "evidence/brief.yml"\n')
    assert with_comment == CANONICAL_BRIEF_REF
    assert quoted == CANONICAL_BRIEF_REF
