"""Every evidence pack must declare the CANONICAL staging brief_ref.

The contract is documented in `scripts/ci/evidence_paths.py`'s module
docstring: a per-PR pack at `evidence/<YYYY-MM>/<slug>/pack.yml` must still
declare the literal `brief_ref: evidence/brief.yml`, because
`harness-floor.yml` Step 7b stages pack and brief into a synthetic
`/tmp/evidence-check/evidence/{pack,brief}.yml` tree and lints it with
`--repo-root` pointed at THAT tree. The "obviously correct" per-PR value
resolves against the real repo, not the staging tree, and fails with a
message that never mentions staging.

`evidence_pack_lint.py` already refuses such a pack -- but only for a PR the
harness-floor gate actually runs on. Six packs reached main carrying the wrong
value anyway, because the gate executes the copy of itself recorded at the
PR's base sha: a PR whose base predates the gate never runs it. A repo-wide
sweep is what closes that hole, so this test walks the whole tree instead of
trusting the per-PR gate to have fired.

Guilt AND innocence, per superscar #3. The innocence case is not decorative:
the first sweep written for this fix matched `brief_ref:` with a regex and
"corrected" a pack whose value was already canonical but carried an inline
YAML comment -- the comment was captured as part of the value. The predicate
must PARSE the YAML, and the test pins that.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
EVIDENCE = REPO / "evidence"

CANONICAL_BRIEF_REF = "evidence/brief.yml"


def _declared_brief_ref(pack_text: str) -> str | None:
    """The pack's brief_ref as YAML sees it -- comments and quoting removed by
    the parser, never by hand."""
    doc = yaml.safe_load(pack_text) or {}
    if not isinstance(doc, dict):
        return None
    value = doc.get("brief_ref")
    return value if isinstance(value, str) else None


def test_every_pack_in_the_tree_declares_the_canonical_brief_ref() -> None:
    offenders = []
    checked = 0
    for pack in sorted(EVIDENCE.rglob("pack.yml")):
        declared = _declared_brief_ref(pack.read_text(encoding="utf-8"))
        if declared is None:
            continue
        checked += 1
        if declared != CANONICAL_BRIEF_REF:
            offenders.append(f"{pack.relative_to(REPO)} -> {declared!r}")
    assert checked, "no pack.yml declared a brief_ref -- the sweep found nothing to check"
    assert not offenders, (
        "these packs name their real per-PR brief path instead of the canonical "
        f"staging literal {CANONICAL_BRIEF_REF!r} (see scripts/ci/evidence_paths.py):\n  "
        + "\n  ".join(offenders)
    )


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
