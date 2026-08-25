"""Every ingest entrypoint must name a collection the registry actually maps.

WORK ITEM ZERO, measured 2026-08-25 against production Qdrant:

  * `legal_unified_2026` holds 15,410 points / 18 documents. Those counts are
    byte-identical to the ones recorded on 2026-05-16 in
    `research/nb-lifecycle/2026-05-16-r5-phase2-indexing-parity.md:202`
    (`Permen_18_2021` 10,266x, `Permen_35_2012` 1,240x), so nothing has been
    written to it in over three months. It is a frozen artifact, not a live drawer.
  * THREE entrypoints named it — the regulatory runner plus two sibling ingest
    scripts — and every one of them was a dead path twice over: the registry maps
    no alias to it, so no retrieval reads it, AND `LegalIngestionService`'s
    preflight raises `LegalIngestIntegrityError` for any target outside
    `ALLOWED_CANONICAL_COLLECTIONS`, so they could not have written to it either.
  * `apps/backend-rag/scripts/ingest_2026_laws.py` had already been cured this
    exact way, and left its reasoning in a comment. A comment does not fail. This
    file is the version that does.

The mandate asks for "a test that fails if the runner's collection name ever
again names something the registry does not map". That is `test_declared_*`
below; the rest is what stops it from passing vacuously.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_lint():
    """Load scripts/ci/ingest_target_lint.py by path.

    Located from THIS file, never from cwd: the CI shards run pytest from
    `apps/backend-rag`, so a cwd-relative lookup would report the module absent
    on precisely the machine that matters.
    """
    here = Path(__file__).resolve()
    for candidate in here.parents:
        module_path = candidate / "scripts" / "ci" / "ingest_target_lint.py"
        if module_path.is_file():
            spec = importlib.util.spec_from_file_location(
                "ingest_target_lint", module_path
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules["ingest_target_lint"] = module
            spec.loader.exec_module(module)
            return module
    raise AssertionError(
        f"scripts/ci/ingest_target_lint.py not found above {here} — the gate this "
        "module exists to run has been moved or deleted"
    )


LINT = _load_lint()
ROOT = LINT.repo_root()

RETIRED_TARGET = "legal_unified_2026"


def test_declared_ingest_entrypoints_name_registry_mapped_collections():
    """The gate itself. Red means: something writes where nothing reads."""
    violations = LINT.check(ROOT)
    assert violations == [], (
        "An ingest entrypoint names a collection `collection_registry.py` does "
        "not map. Content written there is unreachable by every retrieval path, "
        "and `LegalIngestionService`'s preflight will refuse the write outright.\n"
        "Cure: point it at the registry-mapped name (legal corpus -> "
        "'legal_unified'), or add the collection to the registry if it is "
        "genuinely a new logical target.\n  " + "\n  ".join(violations)
    )


def test_the_regulatory_runner_does_not_name_the_retired_2026_target():
    """The mandate's literal ask, pinned to the file that carried the defect."""
    runner = ROOT / "infra/eventbus/regulatory_ingest_runner.py"
    assert runner.is_file(), "the regulatory ingest runner has moved — repoint this test"
    source = runner.read_text(encoding="utf-8")
    offending = [
        f"{n}: {line.strip()}"
        for n, line in enumerate(source.splitlines(), 1)
        if RETIRED_TARGET in line and not line.lstrip().startswith("#")
    ]
    assert offending == [], (
        f"{RETIRED_TARGET!r} is retired as an ingest target (frozen since 2026-05-16, read by "
        "nothing, refused by the ingestion preflight). Non-comment occurrences:\n  " + "\n  ".join(offending)
    )


def test_no_undeclared_ingest_entrypoint_exists():
    """A new ingest script cannot dodge the gate by not being on the list."""
    undeclared = LINT.discover(ROOT)
    assert undeclared == [], (
        "These modules write to a Qdrant collection but are not in "
        "DECLARED_ENTRYPOINTS, so the gate above never inspects them. Add each to "
        "scripts/ci/ingest_target_lint.py::DECLARED_ENTRYPOINTS, or to "
        "DISCOVERY_ALLOWLIST with a reason:\n  " + "\n  ".join(undeclared)
    )


def test_the_target_scanner_is_not_silently_finding_nothing():
    """Anti-vacuity: a broken scanner must go red, not quietly pass everything.

    `test_declared_*` is an assertion over a list. If the AST rules stopped
    matching, that list would be empty and the gate would be green while
    inspecting nothing — the exact failure mode this repo calls a probe that
    agrees with itself.
    """
    per_file = {
        rel: LINT.collection_targets((ROOT / rel).read_text(encoding="utf-8"))
        for rel in LINT.DECLARED_ENTRYPOINTS
    }
    empty = sorted(rel for rel, targets in per_file.items() if not targets)
    assert empty == [], (
        "declared as ingest entrypoints but no collection target was found — the "
        "AST rules in ingest_target_lint.py have drifted away from how these call "
        "sites are written:\n  " + "\n  ".join(empty)
    )
    total = sum(len(t) for t in per_file.values())
    assert total >= len(LINT.DECLARED_ENTRYPOINTS), (
        f"found {total} targets across {len(LINT.DECLARED_ENTRYPOINTS)} declared "
        "entrypoints — fewer than one each is not a corpus, it is a broken scanner"
    )


def test_the_checker_actually_catches_an_unmapped_collection(tmp_path):
    """GUILT. Runs the real checker over a synthetic tree that violates.

    Without this, every green above is compatible with a checker that can only
    ever return an empty list.
    """
    bad = tmp_path / "fake_ingest.py"
    bad.write_text(
        f'service = LegalIngestionService(collection_name="{RETIRED_TARGET}")\n',
        encoding="utf-8",
    )
    violations = LINT.check(ROOT, entrypoints=("fake_ingest.py",), source_root=tmp_path)
    assert len(violations) == 1, violations
    assert RETIRED_TARGET in violations[0]
    assert "NOT in collection_registry" in violations[0]


def test_the_checker_passes_a_registry_mapped_collection(tmp_path):
    """INNOCENCE. The cure must actually be accepted by the same code path."""
    good = tmp_path / "fake_ingest.py"
    good.write_text(
        'service = LegalIngestionService(collection_name="legal_unified")\n',
        encoding="utf-8",
    )
    assert LINT.check(ROOT, entrypoints=("fake_ingest.py",), source_root=tmp_path) == []


def test_a_declared_entrypoint_that_vanishes_is_a_violation_not_a_skip(tmp_path):
    """A missing file must go red. Skipping on absence is how gates die quietly."""
    violations = LINT.check(ROOT, entrypoints=("does_not_exist.py",), source_root=tmp_path)
    assert len(violations) == 1
    assert "does not exist" in violations[0]


@pytest.mark.parametrize(
    "source,expected",
    [
        # shapes real call sites in this repo use
        ('LegalIngestionService(collection_name="legal_unified")', ["legal_unified"]),
        ('COLLECTION_NAME = "tax_genius"\nx = QdrantClient(collection_name=COLLECTION_NAME)',
         ["tax_genius", "tax_genius"]),
        ('upsert(collection_name="legal_unified", points=p)', ["legal_unified"]),
        ('subprocess.run(["--collection", "legal_unified", "--limit"])', ["legal_unified"]),
        # the six forms a cross-family refuter used to walk straight past the
        # regex version on 2026-08-25 — two of them GREEN over a live defect
        ('LegalIngestionService(collection_name="legal_unified" + "_2026")',
         ["legal_unified_2026"]),
        ('LegalIngestionService(collection_name="legal_unified" "_2026")',
         ["legal_unified_2026"]),
        ('LegalIngestionService("legal_unified_2026")', ["legal_unified_2026"]),
        ('cfg = {"collection": "legal_unified_2026"}', ["legal_unified_2026"]),
        ('DEAD = "legal_unified_2026"\nLegalIngestionService(collection_name=DEAD)',
         ["legal_unified_2026"]),
        # not resolvable -> reported as such, never guessed and never dropped
        ('LegalIngestionService(collection_name=f"legal_unified_{y}")', [LINT.UNRESOLVED]),
        ('LegalIngestionService(collection_name=argv[1])', [LINT.UNRESOLVED]),
    ],
)
def test_target_extraction_shapes(source, expected):
    assert [value for value, _, _ in LINT.collection_targets(source)] == expected


def test_a_runtime_assembled_target_is_a_violation_not_a_silence(tmp_path):
    """The refuter's strongest finding, pinned.

    `collection_name="legal_unified" + "_2026"` extracted a MAPPED name under the
    regex scanner and passed clean while writing to the dead collection. Green over
    a live defect is worse than no gate; both halves are asserted here.
    """
    concat = tmp_path / "concat.py"
    concat.write_text(
        'LegalIngestionService(collection_name="legal_unified" + "_2026")\n',
        encoding="utf-8",
    )
    violations = LINT.check(ROOT, entrypoints=("concat.py",), source_root=tmp_path)
    assert len(violations) == 1 and "legal_unified_2026" in violations[0], violations

    dynamic = tmp_path / "dynamic.py"
    dynamic.write_text(
        'LegalIngestionService(collection_name=os.environ["C"])\n', encoding="utf-8"
    )
    violations = LINT.check(ROOT, entrypoints=("dynamic.py",), source_root=tmp_path)
    assert len(violations) == 1 and "assembled at runtime" in violations[0], violations


def test_qdrant_client_first_positional_is_a_url_not_a_collection():
    """A rule that INVENTS a target is as bad as one that misses it: reading
    QdrantClient's first positional as a collection produced a phantom `:memory:`
    on this checker's first run over the tree."""
    assert LINT.collection_targets('QdrantClient(":memory:")') == []


def test_every_discovery_allowlist_entry_carries_a_reason():
    empty = sorted(k for k, v in LINT.DISCOVERY_ALLOWLIST.items() if not (v or "").strip())
    assert empty == [], (
        "an allowlist entry with no reason is how this list becomes the whole "
        f"tree: {empty}"
    )


def test_an_allowlisted_open_finding_has_a_row_in_the_inventory():
    """Cross-source. An entry parked here as an OPEN FINDING must be recorded as
    one where the campaign can see it — otherwise the allowlist is a graveyard."""
    import re

    import yaml

    inventory = yaml.safe_load(
        (ROOT / "kb/inventory/legal_unified_2026.yaml").read_text(encoding="utf-8")
    )
    recorded = {f["id"] for f in inventory.get("open_findings", [])}
    cited = set()
    for reason in LINT.DISCOVERY_ALLOWLIST.values():
        cited.update(re.findall(r"\bWIZ-\d+\b", reason or ""))
    missing = sorted(cited - recorded)
    assert missing == [], (
        "allowlisted as OPEN FINDINGs but absent from "
        f"kb/inventory/legal_unified_2026.yaml -> open_findings: {missing}"
    )
