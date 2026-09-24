"""B2.2 — the no-send retrieval harness (evidence/2026-09/agent-nuzantara-
backend-rag-b2-2-harness-5936113c/brief.yml, key `harness_contract`
HC1-HC10 — binding, supersedes the earlier QueryRouter design after Codex
r2 BLOCKed it: finding 1, importing `SearchService` at module scope
constructs global Settings before the plan-file gate; finding 2, the F6
subprocess guarded sockets only, not providers; finding 3, `--collection`
and a bare `QueryRouter` diverge from the ONE real consumer of these
thresholds; finding 4, `RetrievalError` interpolated `str(exc)`).

The ONE real consumer mirrored here is the WA codex-route package builder
(`backend/services/rag/agentic/wa_package_builder.py`,
`build_context_package`, B2 §1): deterministic, LLM-free retrieval via
`QueryPlanner().plan(query).collections` (pure heuristics, no I/O), one
search per PLANNED collection (never a router's choice, never an LLM tool
call), the builder's own sort/cap/DLP, then `build_abstain_policy` +
`calculate_evidence_score` with `support=None` exactly as the builder
calls them. The orchestrator label site (`orchestrator_response.py:93`) is
NOT reproducible — its collection comes from an LLM tool call or a
federation over `AVAILABLE_COLLECTIONS` (`tools.py:159-209`) that bypasses
`QueryPlanner` entirely — `_ORCHESTRATOR_EXCLUSION_REASON` says so.

NO network call, NO embedding call, NO generation call, NO send, NO cache
write, NO paid reranking BY CONSTRUCTION: nothing here ever imports or
constructs an embedder, an LLM client, a channel sender, a cache service,
a reranker or a `QueryExpander`. `run_query`/`run_all` take a
PRE-COMPUTED vector plus a caller-supplied `resolve_client` callable —
there is no branch through which a provider could be reached.
`test_b2_2_retrieval_harness.py` proves this via socket guards, a
fresh-subprocess import-time check, and a fresh subprocess that installs
monkeypatch guards on the real production entrypoints BEFORE importing
this module at all, then runs a safe AND several guilty fake-client
scenarios in that SAME process (HC7).

Import boundary (HC5) — and a discovered limit on it
--------------------------------------------------------
Module scope imports the standard library plus `score_provenance`,
`bm25_vectorizer`, `collection_registry` and `build_query_vectors` — each
independently verified to import nothing beyond the standard library,
transitively. `QueryPlanner` and `get_keyword_translator` are the ONLY two
production names `build_plan()` needs (it runs unconditionally: plan mode
AND the `--execute` recompute-and-compare step), and both are bound at
module scope too — but via `_import_pure_leaf`, not a plain `from X import
Y`.

DISCOVERED DURING THIS BUILD, not assumed: `query_planner.py` and
`keyword_translator.py` are themselves clean, but Python runs a package's
`__init__.py` on ANY import reaching into it, and their two ancestor
packages eagerly import Settings-constructing classes as a pure side
effect of package init, independent of which name is actually requested —
`backend/services/rag/agentic/__init__.py` imports the full
`AgenticRAGOrchestrator`/`tools.py` stack; `backend/services/search/
__init__.py` imports `SearchService` directly (the exact class Codex r2
finding 1 named). A plain import of either would load
`backend.app.core.config` before `build_plan()` ever runs. Verified file
by file in fresh subprocesses (see this PR's report). Reimplementing
`QueryPlanner`'s ~300 lines of routing locally to dodge this would violate
HC1's own requirement to call the REAL production planner and would
create the drift-prone duplicate this codebase's SSOT culture forbids —
so `_import_pure_leaf` reaches the real files instead, giving each
not-yet-imported ancestor package a bare stub for the duration of the one
import it takes to reach the leaf module, then removing every trace of
the stub (see its own docstring; `TestHC5StubBypassLeavesNoTrace` proves
no residue survives for a later, unrelated, real import in the same
process).

Everything else this module needs (`build_search_filter`,
`format_search_results`, `redact_package_fields`, `calculate_evidence_score`,
`build_abstain_policy`, `CollectionManager`) is imported lazily, inside a
function, via a PLAIN import — accepting whatever their own package
cascades load, because by the time any of them runs, the query's
collections are already known non-empty (the first five) or `--execute`'s
plan-file gate has already passed (`CollectionManager` — the one class
that can construct a REAL network-capable Qdrant client). `NAMED_VECTOR_
COLLECTIONS`/`_uses_named_vectors`/`_requires_current_law_guard`/
`_cap_chunks` are reproduced locally as pure, I/O-free constants instead
of imported at all (each cites the production lines it mirrors — no
package-cascade concern applies to a constant that is never imported).
`evidence_sufficiency.harness` is avoided the same way `_abstain_policy`
is: `_hash_file_bytes` reproduces its `source_sha256` algorithm locally.

Per-query retrieval (HC1-HC4)
-------------------------------
`_plan_for_query(query)` — the ONE function both `build_plan()` (sync,
pure) and `run_query()` (async) call — returns
`QueryPlanner().plan(query).collections`, deduped in priority order
exactly as `build_context_package` dedups them, plus whether
`get_keyword_translator().translate(query)` changes the query (HC3). An
empty collection list is `unbuildable:no_collections` — not scored, not a
failure. A changed-translation query is `embedding_divergent`: still
retrieved in full on the artifact's RAW-query vector (no translated vector
is ever generated — that would be a new paid attempt), reported in its
own column, EXCLUDED from threshold inference.

Per planned collection: `resolve_client(collection)` (caller-injected,
duck-typed like `CollectionManager.get_collection`); its `await
.get_stats()` (the same read-only info call `QdrantClient.get_stats()`
exposes) must show non-zero `total_documents`; the filter is built via
the exact `_prepare_search_context` recipe for `tier_filter=None`,
`apply_filters=None` (`search_service.py:534-552`) through the SAME
`build_search_filter`, never reimplemented; the sparse vector is
`BM25Vectorizer(settings.bm25_vocab_size, settings.bm25_k1,
settings.bm25_b).generate_query_sparse_vector(query)` — lazily
constructed, the one legitimate need for Settings, reached only after a
query's collections are known non-empty; `if query_sparse and
hasattr(vector_db, "hybrid_search")` mirrors `search_service.py:1152-1197`
exactly, entering `hybrid_search` even for a pathological empty-indices
sparse dict — that fallback lives inside `QdrantClient.hybrid_search`
itself, not here. `score_kind` is declared by `"search_type" in
raw_results`, never inferred from magnitude. Results are formatted by the
unchanged `format_search_results(...)`, reshaped into the WA builder's
`{collection, text, score, id}` chunk shape (`id` is an addition, kept
only for `_opaque_source_ref`, never exported as text), sorted by
`(-score, collection, text)`, capped by a local `_cap_chunks` mirroring
`wa_package_builder.py:404-429` (unsafe to import — see HC5), then
redacted by the unchanged, dependency-free `redact_package_fields([],
chunks, None)`.

Fail-closed retrieval (HC6, HC8)
-----------------------------------
An absent collection, a collection whose `get_stats()` shows zero points,
or ANY exception from `get_stats`/`hybrid_search`/`search` is a HARD STOP
for the WHOLE batch — never scored, never partially written. A single
collection returning zero hits among several planned ones is recorded and
the case continues; only zero hits across EVERY planned collection of a
case is itself a hard stop. Every `RetrievalError` carries a FIXED message
plus `_safe_exception_summary` (class name, and an int `status_code` ONLY
when the original carries one in `100..599`) — NEVER `str(exc)` — raised
`from None` so Python's own traceback formatter cannot print the original
(possibly secret-bearing) message even if this propagates uncaught.

Export boundary (HC9) and the plan-file pin (HC6/F1/F3)
----------------------------------------------------------
`QueryOutcome` never carries chunk text; `_opaque_source_ref` uses a
chunk's `id` or a hash of its `score_kind`/`score`, never
`chunk["text"]`. `support=None` is the UPPER BOUND under the engine's
fail-closed-only rule: **a false acceptance seen is real; a pass does not
prove support.** `build_report` embeds that sentence verbatim, the canary
line (UNVERIFIABLE, never `0`), the orchestrator-exclusion reason, and
every case in the tax `[0.10, 0.15)` / visa `[0.12, 0.15)` relief band —
the number this PR exists to find. `load_artifact` hashes the artifact
FILE's bytes against the fixed `EXPECTED_ARTIFACT_SHA256` before parsing
it — no CLI override for path or hash. `--execute` requires
`--plan-file`/`--plan-sha256` naming a file whose bytes hash to the given
sha256 AND whose parsed plan equals `build_plan()` recomputed now —
refused, before importing `CollectionManager`, on any mismatch.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib
import json
import os
import sys
import types
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from backend.core import score_provenance
from backend.core.bm25_vectorizer import BM25Vectorizer
from backend.core.collection_registry import canonicalize_collection_name
from backend.tests.benchmarks.evidence_sufficiency.build_query_vectors import mapping_key

_HERE = Path(__file__).resolve().parent
DEFAULT_ARTIFACT = _HERE / "query_vectors_b1_5.json"


def _import_pure_leaf(dotted_module: str) -> Any:
    """Import `dotted_module` by its real dotted path WITHOUT executing any
    not-yet-imported ancestor package's `__init__.py`.

    DISCOVERED DURING THIS BUILD, not assumed: `query_planner.py` and
    `keyword_translator.py` are themselves clean (stdlib-only module-scope
    imports), but Python runs a package's `__init__.py` on ANY import
    reaching into it — and `backend/services/rag/agentic/__init__.py`
    imports the full `AgenticRAGOrchestrator`/`tools.py` stack (needed for
    `QueryPlanner`), while `backend/services/search/__init__.py` imports
    `SearchService` directly (needed for `get_keyword_translator` — the
    exact class Codex r2 finding 1 named). Either import, done normally,
    loads `backend.app.core.config` before `build_plan()` ever runs, which
    HC5 forbids. Reimplementing `QueryPlanner`'s ~300 lines of routing
    locally to dodge this would violate HC1's own requirement to call the
    REAL production planner and would create the drift-prone duplicate
    this codebase's SSOT culture forbids.

    This helper gives each not-yet-imported ancestor package a bare
    `types.ModuleType` stub — with a correct `__path__`, so the finder
    still locates real files inside it — for the DURATION of this one
    import, then removes every stub AND everything cached under it again,
    so a LATER, unrelated real import of the same package (elsewhere in
    the same process) is unaffected and gets a fresh, fully-initialized
    module. If an ancestor is ALREADY genuinely imported (e.g. an earlier
    test in the same pytest process already loaded it), it is left alone
    and used as-is — no stub, no cleanup for it.
    `TestHC5StubBypassLeavesNoTrace` proves the no-residue claim.
    """
    if dotted_module in sys.modules:
        return sys.modules[dotted_module]

    pkg_root = _HERE.parents[3]  # .../apps/backend-rag (contains "backend/")
    parts = dotted_module.split(".")
    stubbed: list[str] = []
    try:
        for i in range(1, len(parts)):
            ancestor = ".".join(parts[:i])
            if ancestor in sys.modules:
                continue
            stub = types.ModuleType(ancestor)
            stub.__path__ = [str(pkg_root.joinpath(*ancestor.split(".")))]
            stub.__package__ = ancestor
            sys.modules[ancestor] = stub
            stubbed.append(ancestor)
        return importlib.import_module(dotted_module)
    finally:
        for name in list(sys.modules):
            if any(name == a or name.startswith(a + ".") for a in stubbed):
                del sys.modules[name]


#: QueryPlanner/get_keyword_translator — the ONLY two production names
#: `build_plan()` needs, and `build_plan()` runs unconditionally (plan mode
#: AND the --execute recompute-and-compare step) — bypassed via
#: `_import_pure_leaf` so neither one loads Settings before the plan-file
#: gate. See that function's docstring for the discovery and the reasoning.
QueryPlanner = _import_pure_leaf("backend.services.rag.agentic.query_planner").QueryPlanner
get_keyword_translator = _import_pure_leaf(
    "backend.services.search.keyword_translator",
).get_keyword_translator

#: The B1.5 artifact's pinned sha256 (research/operations/2026-09-11-
#: bot-staff-room/B2-engine.md §4) — the FILE's raw bytes, not a
#: re-serialization of its parsed JSON.
EXPECTED_ARTIFACT_SHA256 = "0021c3275b7bd9f812f0ce52fc06da1330e89a9d1c40a4c105ca932720083012"

#: wa_package_builder.py:91 — fixed, documented access level for this
#: deterministic, unauthenticated path. Verified equal to the real constant
#: by a test (import is safe only inside a test file, never here — see
#: module docstring HC5).
_SEARCH_USER_LEVEL = 1

#: wa_package_builder.py:64 — per-collection chunk cap passed to
#: `hybrid_search`/`search`.
_CHUNKS_PER_COLLECTION_LIMIT = 3

#: wa_package_builder.py:60-61 — package hygiene caps `_cap_chunks` (below)
#: enforces, reproduced because importing wa_package_builder.py is unsafe
#: (it imports `_abstain_policy` at module scope, which imports Settings).
_MAX_CHUNKS = 8
_MAX_CHUNK_CHARS = 4000

#: search_service.py:64-75 NAMED_VECTOR_COLLECTIONS, reproduced (importing
#: search_service.py at module scope constructs Settings at its own :25 —
#: Codex r2 finding 1). Pure set membership, no I/O, no config dependency.
_NAMED_VECTOR_COLLECTIONS: frozenset[str] = frozenset(
    {
        "legal_unified",
        "legal_unified_2026",
        "tax_genius",
        "tax_genius_hybrid",
        "training_conversations_hybrid",
        "legal_unified_hybrid",
        "legal_unified_hybrid_hybrid",
        "kbli_2025_final",
        "kbli_2025_final_hybrid",
        "visa_oracle",
    },
)


def _uses_named_vectors(collection_name: str) -> bool:
    """search_service.py:79-81, reproduced verbatim (see module constant
    above for why it is not imported)."""
    return collection_name in _NAMED_VECTOR_COLLECTIONS or collection_name.endswith("_hybrid")


#: search_service.py:248-253 `_requires_current_law_guard`'s two names.
_CURRENT_LAW_GUARD_COLLECTIONS: frozenset[str] = frozenset({"legal_unified", "tax_genius"})


def _requires_current_law_guard(collection: str) -> bool:
    """search_service.py:248-253's staticmethod, reproduced: canonicalize
    then membership-test. `canonicalize_collection_name` IS imported
    (`collection_registry.py` is proven pure — see module docstring)."""
    return canonicalize_collection_name(collection) in _CURRENT_LAW_GUARD_COLLECTIONS


#: config.py:383-393's BM25 env var names — presence only, per HC2's "never
#: a value" rule (a value could reveal a deployment-specific tuning).
_BM25_ENV_VARS: tuple[str, ...] = ("ENABLE_BM25", "BM25_VOCAB_SIZE", "BM25_K1", "BM25_B")


def bm25_env_presence() -> dict[str, bool]:
    """Presence (never value) of each BM25_* env var — `os.environ` is
    stdlib, local, and carries no config-construction risk."""
    return {name: name in os.environ for name in _BM25_ENV_VARS}


#: HC4 — operations disabled BY CONSTRUCTION, embedded in every plan.
_DISABLED_BY_CONSTRUCTION: tuple[dict[str, str], ...] = (
    {
        "operation": "embedding",
        "reason": (
            "run_query has no embedder parameter; the vector is resolved from the "
            "frozen B1.5 artifact before run_query is ever called"
        ),
    },
    {
        "operation": "query_expansion",
        "reason": "no QueryExpander is ever constructed or called anywhere in this module",
    },
    {
        "operation": "reranking",
        "reason": "no reranker (Ze-Rank or cross-encoder) is ever constructed or called",
    },
    {
        "operation": "cache_read_or_write",
        "reason": (
            "no SearchService, CacheService or SemanticCache is ever constructed; the "
            "collection client's get_stats/hybrid_search/search are called directly"
        ),
    },
    {
        "operation": "health_monitor_write",
        "reason": "no HealthMonitor.record_query call — this module never constructs one",
    },
    {
        "operation": "surface_router",
        "reason": "SurfaceRouter is absent from the WA path this harness mirrors; never imported",
    },
    {
        "operation": "network_fallback",
        "reason": (
            "a sha256 mismatch, a missing vector, an absent/empty collection, or any "
            "client exception raises ArtifactError/RetrievalError; there is no fallback "
            "path to a different provider anywhere in this module"
        ),
    },
    {
        "operation": "generation",
        "reason": "no LLM generation client (Gemini/Codex/Claude) is ever constructed or called",
    },
    {
        "operation": "send",
        "reason": "no channel adapter / sender is ever constructed or called",
    },
)

#: F4 — measurement-scope limitations, embedded verbatim in every plan and
#: quoted in the module docstring above.
_LIMITATIONS: tuple[str, ...] = (
    "curated_qa_block is always None here — curated-QA evidence is a source-quality "
    "concern (pre-gated by OrchestratorCore.curated_qa_grounding_block), out of scope "
    "for a retrieval-fidelity sample.",
    "support=None scores EXACTLY as SUPPORTED under the engine's fail-closed-only rule "
    '(reasoning_utils.py: \'None means "not consulted" and changes nothing; anything but '
    "SUPPORTED zeroes relevance') — every score this harness reports is the UPPER BOUND "
    "the support gate allows: a false acceptance seen is real; a pass does not prove support.",
    "the orchestrator label site (orchestrator_response.py:93) is out of this sample by "
    "construction: its collection comes from an LLM tool call or a federation over "
    "AVAILABLE_COLLECTIONS (tools.py:159-209) that bypasses QueryPlanner entirely.",
    "canary overlap is UNVERIFIABLE on this host (no baseline present) — never reported as 0.",
)

_SUPPORT_NONE_SENTENCE = _LIMITATIONS[1]
_ORCHESTRATOR_EXCLUSION_REASON = _LIMITATIONS[2]
_CANARY_LINE = "canary overlap: UNVERIFIABLE (baseline absent on this host)"

__all__ = [
    "DEFAULT_ARTIFACT",
    "EXPECTED_ARTIFACT_SHA256",
    "ArtifactError",
    "QueryOutcome",
    "QueryVectorArtifact",
    "RetrievalError",
    "bm25_env_presence",
    "build_plan",
    "build_report",
    "load_artifact",
    "main",
    "outcome_to_dict",
    "resolve_vectors",
    "run_all",
    "run_and_write",
    "run_query",
]


class ArtifactError(Exception):
    """Raised on a sha256 mismatch or a missing pre-computed vector.

    Raising this IS the harness's abort mechanism: it always fires before
    the injected vector-store client is touched for the run in question.
    """


class RetrievalError(Exception):
    """Raised on ANY retrieval failure — a HARD STOP, never an abstain.

    Carries a FIXED message plus `_safe_exception_summary` — the causing
    exception's class name, and an int `status_code` ONLY when the
    original carries one in `100..599` — NEVER `str(exc)`. Always raised
    with `from None`: the exception chain is deliberately severed so
    Python's own traceback formatter cannot print the original exception's
    (possibly secret-bearing) message even if this propagates uncaught.

    Six cases, all in `run_query()` (A55_1/A55_2 amended HC6/HC8):

    1. A planned collection's canonicalized name resolves to nothing AND the
       production substitution target `"legal_unified"` ALSO resolves to
       nothing (`resolve_client(...)` returns `None` both times) —
       search_service.py:526-532's own fallback has nothing left to fall
       back to (production raises `ValueError` here). An unresolvable name
       that DOES substitute successfully is NOT a hard stop any more — see
       `collection_resolutions`.
    2. The RESOLVED collection's `get_stats()` shows zero `total_documents`.
    3. `get_stats`/`hybrid_search`/`search` raises ANY exception.
    4. `hybrid_search`/`search` RETURNS a dict carrying an `"error"` key
       (qdrant_db.py:1363-1375 does this instead of raising on some HTTP
       failures) — never treated as zero evidence.
    5. Zero hits across EVERY RESOLVED collection of this case (a single
       collection among several returning zero hits is recorded, not fatal).
    6. (Not a `RetrievalError`.) A resolved collection's `hybrid_search()`
       fell back to dense internally (no `"search_type"` key) — recorded as
       `score_kind_divergent=True` and excluded from inference, never a hard
       stop.

    Raising this aborts the WHOLE `run_all()` batch — never scored as a
    zero-evidence abstain, never a partial report on disk.
    """


def _safe_exception_summary(exc: BaseException) -> dict[str, Any]:
    """The exception's class name, and an int `status_code` ONLY when the
    exception carries one in `100..599` — NEVER `str(exc)` (HC8): a
    transport exception's own message can carry credentials, headers, URLs
    or retrieved content."""
    summary: dict[str, Any] = {"exception_type": type(exc).__name__}
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599:
        summary["status_code"] = status
    return summary


@dataclasses.dataclass(frozen=True)
class QueryVectorArtifact:
    """The loaded, sha256-verified B1.5 vector artifact."""

    path: Path
    sha256: str
    data: Mapping[str, Any]

    @property
    def model(self) -> str:
        return self.data["model"]

    @property
    def dimension(self) -> int:
        return self.data["dimension"]

    @property
    def query_list(self) -> list[dict[str, str]]:
        return list(self.data["query_list"])


@dataclasses.dataclass(frozen=True)
class QueryOutcome:
    """One query's retrieval + scoring result. NEVER carries chunk text —
    `source_refs` is opaque (ids/hashes only)."""

    query_key: str
    query: str
    query_lang: str
    case: str  # "scored" | "unbuildable:no_collections"
    query_domain: str | None  # the THRESHOLD domain (AbstainPolicy.query_domain)
    translation_changes_query: bool
    embedding_divergent: bool
    planned_collections: tuple[str, ...]
    collection_hit_counts: tuple[tuple[str, int], ...]
    score: float | None
    score_kinds: tuple[str, ...]
    generation_decision: str | None  # "pass" | "abstain"
    label_decision: str | None  # "pass" | "abstain"
    generation_threshold: float | None
    label_threshold: float | None
    source_count: int
    source_refs: tuple[str, ...]
    #: A55_1 — per planned collection: (collection_planned, collection_resolved,
    #: substituted, duplicate_after_resolution). `collection_resolved` is the
    #: name search_service.py:526-532 would actually query (after
    #: canonicalize_collection_name and, if that resolves to nothing, the
    #: silent substitution to "legal_unified"); `substituted` is True whenever
    #: that substitution branch fired (even if the canonical name already WAS
    #: "legal_unified"); `duplicate_after_resolution` is True when an EARLIER
    #: entry in this same tuple already carries the same `collection_resolved`
    #: (production searches it again — never deduped post-resolution).
    collection_resolutions: tuple[tuple[str, str, bool, bool], ...] = ()
    #: A55_2 — True when ANY resolved collection's hybrid_search() fell back
    #: to a dense-shaped result internally (raw_results lacked "search_type").
    #: The case is still fully scored and reported, but EXCLUDED from
    #: threshold inference (same treatment as `embedding_divergent`).
    score_kind_divergent: bool = False


def outcome_to_dict(outcome: QueryOutcome) -> dict[str, Any]:
    """JSON-safe projection of a `QueryOutcome` (tuples -> lists/dicts)."""
    payload = dataclasses.asdict(outcome)
    payload["planned_collections"] = list(payload["planned_collections"])
    payload["collection_hit_counts"] = dict(payload["collection_hit_counts"])
    payload["score_kinds"] = list(payload["score_kinds"])
    payload["source_refs"] = list(payload["source_refs"])
    payload["collection_resolutions"] = [
        {
            "collection_planned": planned,
            "collection_resolved": resolved,
            "substituted": substituted,
            "duplicate_after_resolution": duplicate,
        }
        for (planned, resolved, substituted, duplicate) in payload["collection_resolutions"]
    ]
    return payload


def _hash_file_bytes(path: str | Path) -> str:
    """sha256 of the FILE's raw bytes — the same algorithm
    `backend.tests.benchmarks.evidence_sufficiency.harness.source_sha256`
    implements, reproduced locally: that module imports `_abstain_policy`
    (-> Settings) at module scope, which HC5 forbids importing here."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_artifact(
    path: str | Path = DEFAULT_ARTIFACT,
    *,
    expected_sha256: str = EXPECTED_ARTIFACT_SHA256,
) -> QueryVectorArtifact:
    """Load the B1.5 artifact, verifying its FILE BYTES' sha256 first.

    Raises `ArtifactError` on a mismatch, before the file is parsed as
    JSON — a mismatch aborts before anything else in a run happens.
    """
    path = Path(path)
    actual = _hash_file_bytes(path)
    if actual != expected_sha256:
        raise ArtifactError(
            f"{path}: sha256 mismatch — expected {expected_sha256}, got {actual}. "
            "Aborting before the artifact is even parsed.",
        )
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return QueryVectorArtifact(path=path, sha256=actual, data=data)


def resolve_vectors(
    artifact: QueryVectorArtifact,
    query_entries: Sequence[Mapping[str, str]],
) -> dict[str, list[float]]:
    """Resolve every (query_lang, query) pair in `query_entries` to its
    pre-computed vector from `artifact`.

    Fail-closed, all-or-nothing: if even ONE requested pair has no vector,
    raises `ArtifactError` naming every missing key, before any client
    call for ANY query in the batch.
    """
    vectors = artifact.data.get("vectors", {})
    resolved: dict[str, list[float]] = {}
    missing: list[str] = []
    for entry in query_entries:
        key = mapping_key(entry)
        if key not in vectors:
            missing.append(key)
            continue
        resolved[key] = vectors[key]
    if missing:
        raise ArtifactError(
            f"missing pre-computed vector(s), aborting before any client call: {sorted(missing)}",
        )
    return resolved


def _plan_for_query(query: str) -> tuple[str, list[str], bool]:
    """The ONE function `build_plan()` and `run_query()` both call —
    `QueryPlanner().plan(query).collections`, deduped in priority order
    exactly as `wa_package_builder.build_context_package` dedups them
    (:527-536), plus whether `get_keyword_translator().translate(query)`
    changes the query (HC3). Fully synchronous and pure (`QueryPlanner`
    does no I/O — see its own module docstring), so plan and execution can
    never disagree the way a sync/async router-mirror pair could.

    Returns `(planned_domain, collections, translation_changes_query)`;
    `planned_domain` is `QueryPlanner`'s ROUTING domain (`QueryDomain.value`)
    — NOT `AbstainPolicy.query_domain` (the THRESHOLD domain `QueryOutcome`
    carries), a different, unrelated taxonomy computed later in `run_query`.
    """
    plan = QueryPlanner().plan(query)
    seen: set[str] = set()
    collections: list[str] = []
    for collection in plan.collections:
        if collection not in seen:
            seen.add(collection)
            collections.append(collection)
    translated = get_keyword_translator().translate(query)
    translation_changes_query = translated != query
    return plan.domain.value, collections, translation_changes_query


def _build_search_filter_for(collection: str) -> dict[str, Any] | None:
    """`_prepare_search_context`'s filter recipe (search_service.py:534-552)
    for `tier_filter=None`, `apply_filters=None` — calls the SAME
    `build_search_filter` production calls, never reimplementing it.
    `tier_filter_dict` there is only ever non-None for
    `collection_name == "zantara_books"`, which `QueryPlanner`'s
    `_DOMAIN_COLLECTIONS` never produces (query_planner.py) — so that
    branch is faithfully absent here rather than built for a case that can
    never occur on a planner-selected collection.

    Lazy import: `search_filters.py` is itself clean, but its package
    (`backend/services/search/__init__.py`) imports `SearchService`
    directly — reached here only per-collection, during ACTUAL retrieval
    (never before the plan-file gate; see `_import_pure_leaf`'s docstring
    for why `build_plan()`'s own two dependencies ARE bypassed instead).
    """
    from backend.services.search.search_filters import build_search_filter

    return build_search_filter(
        tier_filter=None,
        exclude_repealed=True,
        exclude_historical=_requires_current_law_guard(collection),
    )


def _cap_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """wa_package_builder.py:404-429's hygiene cap, reproduced (see module
    docstring for why that module is not imported): truncate any chunk
    over `_MAX_CHUNK_CHARS`, then keep only the first `_MAX_CHUNKS`."""
    capped: list[dict[str, Any]] = []
    for chunk in chunks:
        text = chunk["text"]
        if len(text) > _MAX_CHUNK_CHARS:
            text = text[:_MAX_CHUNK_CHARS]
        capped.append({**chunk, "text": text})
    return capped[:_MAX_CHUNKS]


def _opaque_source_ref(source: Mapping[str, Any], *, collection: str) -> str:
    """An opaque, collection-scoped reference for one retrieved chunk.

    Uses the chunk's own `id` when present (`"<collection>:id:<id>"`).
    Otherwise hashes its `score_kind`/`score` fields — NEVER
    `source["text"]`, and never anything else text-derived.
    """
    raw_id = source.get("id") if isinstance(source, Mapping) else None
    if raw_id is not None:
        return f"{collection}:id:{raw_id}"
    fingerprint = json.dumps(
        {
            "score_kind": source.get("score_kind") if isinstance(source, Mapping) else None,
            "score": source.get("score") if isinstance(source, Mapping) else None,
        },
        sort_keys=True,
        default=str,
    )
    return f"{collection}:hash:{hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()[:16]}"


def _empty_outcome(
    *,
    query_key: str,
    query: str,
    query_lang: str,
    case: str,
    translation_changes_query: bool,
) -> QueryOutcome:
    return QueryOutcome(
        query_key=query_key,
        query=query,
        query_lang=query_lang,
        case=case,
        query_domain=None,
        translation_changes_query=translation_changes_query,
        embedding_divergent=False,
        planned_collections=(),
        collection_hit_counts=(),
        score=None,
        score_kinds=(),
        generation_decision=None,
        label_decision=None,
        generation_threshold=None,
        label_threshold=None,
        source_count=0,
        source_refs=(),
    )


async def run_query(
    *,
    query_entry: Mapping[str, str],
    vector: Sequence[float],
    resolve_client: Callable[[str], Any],
    bm25: Any | None = None,
) -> QueryOutcome:
    """Run ONE query through the WA package builder's retrieval + scoring
    path, with `vector` injected in place of an embedding call.

    `resolve_client` is the injected vector-store dependency: a
    `Callable[[str], Any]` that, given a collection name, returns an object
    exposing async `.get_stats()`, `.search(query_embedding, filter, limit,
    vector_name)` and optionally `.hybrid_search(query_embedding,
    query_sparse, filter, limit, prefetch_limit)` — `QdrantClient`'s exact
    shape (`core/qdrant_db.py`). This function never constructs a client.

    `bm25`, when `None`, is lazily constructed from
    `backend.app.core.config.settings` — the ONE point in this module
    reached only AFTER a query's collections are known non-empty.

    Raises `RetrievalError` — see its docstring — on any hard-stop
    condition. Never falls back to computing a fresh embedding.
    """
    query = query_entry["query"]
    query_lang = query_entry["query_lang"]
    query_key = mapping_key(query_entry)

    _planned_domain, collections, translation_changes_query = _plan_for_query(query)

    if not collections:
        return _empty_outcome(
            query_key=query_key,
            query=query,
            query_lang=query_lang,
            case="unbuildable:no_collections",
            translation_changes_query=translation_changes_query,
        )

    if bm25 is None:
        from backend.app.core.config import settings as _settings

        bm25 = BM25Vectorizer(
            vocab_size=_settings.bm25_vocab_size,
            k1=_settings.bm25_k1,
            b=_settings.bm25_b,
        )

    # Lazy: `result_formatter.py` is itself clean, but its package
    # (`backend/services/misc/__init__.py`) eagerly imports a dozen heavy
    # services; `wa_dlp.py` is clean too, but its package
    # (`backend/services/rag/agentic/__init__.py`) is the SAME one
    # `_import_pure_leaf` bypasses for `QueryPlanner`. Both are reached
    # only once this query's collections are confirmed non-empty — never
    # before the plan-file gate.
    from backend.services.misc.result_formatter import format_search_results
    from backend.services.rag.agentic.wa_dlp import redact_package_fields

    chunks: list[dict[str, Any]] = []
    hit_counts: dict[str, int] = {}
    collection_resolutions: list[tuple[str, str, bool, bool]] = []
    seen_resolved: set[str] = set()
    case_score_kind_divergent = False

    for collection in collections:
        # A55_1 — search_service.py:526-532's REAL resolution path, called
        # (`canonicalize_collection_name`) or replicated verbatim (the
        # substitution: see `TestA55CollectionResolution.
        # test_search_service_substitution_shape_parity` for the pin).
        canonical = canonicalize_collection_name(collection)
        resolved = canonical
        substituted = False
        vector_db = resolve_client(resolved)
        if vector_db is None:
            substituted = True
            resolved = "legal_unified"
            vector_db = resolve_client(resolved)
            if vector_db is None:
                raise RetrievalError(
                    f"collection resolution failed for query_key={query_key!r}: "
                    f"planned={collection!r} canonical={canonical!r}, and the "
                    "production substitution target 'legal_unified' is ALSO "
                    "absent. Hard stop — search_service.py:526-532's own "
                    "fallback has nothing left to fall back to (production "
                    "raises ValueError here).",
                ) from None
        duplicate_after_resolution = resolved in seen_resolved
        seen_resolved.add(resolved)
        collection_resolutions.append(
            (collection, resolved, substituted, duplicate_after_resolution)
        )

        try:
            stats = await vector_db.get_stats()
        except Exception as exc:
            raise RetrievalError(
                f"get_stats raised for query_key={query_key!r} collection_resolved={resolved!r}: "
                f"{_safe_exception_summary(exc)}. Hard stop, never an abstain.",
            ) from None

        total_documents = stats.get("total_documents") if isinstance(stats, Mapping) else None
        if not total_documents:
            raise RetrievalError(
                f"collection_resolved={resolved!r} has zero points_count for "
                f"query_key={query_key!r}. Hard stop — an absent index is never "
                "a zero-evidence data point.",
            ) from None

        search_filter = _build_search_filter_for(resolved)
        query_sparse = bm25.generate_query_sparse_vector(query)

        try:
            if query_sparse and hasattr(vector_db, "hybrid_search"):
                raw_results = await vector_db.hybrid_search(
                    query_embedding=list(vector),
                    query_sparse=query_sparse,
                    filter=search_filter,
                    limit=_CHUNKS_PER_COLLECTION_LIMIT,
                    prefetch_limit=_CHUNKS_PER_COLLECTION_LIMIT * 3,
                )
                went_hybrid = True
            else:
                use_vector_name = "dense" if _uses_named_vectors(resolved) else None
                raw_results = await vector_db.search(
                    query_embedding=list(vector),
                    filter=search_filter,
                    limit=_CHUNKS_PER_COLLECTION_LIMIT,
                    vector_name=use_vector_name,
                )
                went_hybrid = False
        except Exception as exc:
            raise RetrievalError(
                f"client search raised for query_key={query_key!r} collection_resolved={resolved!r}: "
                f"{_safe_exception_summary(exc)}. Hard stop, never an abstain.",
            ) from None

        # A55_2 — qdrant_db.py hybrid_search does NOT always raise: some HTTP
        # failures RETURN a dict carrying an "error" key with empty lists
        # (qdrant_db.py:1363-1375). That is a HARD STOP too, never treated as
        # zero evidence — and never interpolated into the message (HC8).
        if isinstance(raw_results, Mapping) and "error" in raw_results:
            raise RetrievalError(
                f"qdrant returned an 'error' key for query_key={query_key!r} "
                f"collection_resolved={resolved!r}: hard stop, never zero evidence.",
            ) from None

        if went_hybrid:
            has_search_type = isinstance(raw_results, Mapping) and "search_type" in raw_results
            declared_kind = (
                score_provenance.HYBRID_RRF_FORMATTED
                if has_search_type
                else score_provenance.DENSE_FORMATTED
            )
            if not has_search_type:
                # hybrid_search() fell back to dense INTERNALLY (production's
                # own qdrant_db.py:1358-1362) — not this harness's dense
                # branch. A score-kind divergence, excluded from inference.
                case_score_kind_divergent = True
        else:
            declared_kind = score_provenance.DENSE_FORMATTED

        formatted = format_search_results(
            raw_results,
            resolved,
            primary_collection=None,
            query=query,
            score_kind=declared_kind,
        )
        hit_counts[collection] = len(formatted)

        # wa_package_builder.py:280-290: a non-dict or empty-text hit is
        # skipped, and the chunk keeps the PLANNED collection name (the
        # value passed as collection_override), never the resolved one —
        # it is the sort tie-breaker below.
        for hit in formatted:
            if not isinstance(hit, Mapping):
                continue
            hit_map = hit
            if not hit_map.get("text"):
                continue
            chunk = {
                "collection": collection,
                "text": hit_map["text"],
                "score": hit_map.get("score", 0.0),
                "id": hit_map.get("id"),
            }
            score_provenance.stamp(
                chunk,
                score_provenance.kind_of(hit_map),
                score_provenance.raw_of(hit_map),
            )
            chunks.append(chunk)

    if not any(hit_counts.values()):
        raise RetrievalError(
            f"zero hits across ALL resolved collections for query_key={query_key!r}: "
            f"resolved={sorted(seen_resolved)}. Hard stop, never a zero-evidence data point.",
        ) from None

    chunks.sort(key=lambda c: (-float(c["score"]), c["collection"], c["text"]))
    chunks = _cap_chunks(chunks)

    dlp_result = redact_package_fields([], chunks, None)
    chunks = dlp_result.chunks

    # Lazy: both transitively import Settings (via reasoning_utils.py:24).
    # Reached only after this query's retrieval has fully succeeded.
    from backend.services.rag.agentic._abstain_policy import build_abstain_policy
    from backend.services.rag.agentic.reasoning_utils import calculate_evidence_score

    evidence_score = calculate_evidence_score(
        sources=[
            {
                "score": chunk["score"],
                "score_kind": score_provenance.kind_of(chunk),
                "score_raw": score_provenance.raw_of(chunk),
            }
            for chunk in chunks
        ],
        context_gathered=[chunk["text"] for chunk in chunks],
        query=query,
        support=None,
    )
    policy = build_abstain_policy(query)

    return QueryOutcome(
        query_key=query_key,
        query=query,
        query_lang=query_lang,
        case="scored",
        query_domain=policy.query_domain,
        translation_changes_query=translation_changes_query,
        embedding_divergent=translation_changes_query,
        planned_collections=tuple(collections),
        collection_hit_counts=tuple(sorted(hit_counts.items())),
        score=evidence_score,
        score_kinds=tuple(score_provenance.kind_of(c) for c in chunks),
        generation_decision="abstain" if policy.generation_abstains(evidence_score) else "pass",
        label_decision="abstain" if policy.label_abstains(evidence_score) else "pass",
        generation_threshold=policy.generation_threshold,
        label_threshold=policy.label_threshold,
        source_count=len(chunks),
        source_refs=tuple(_opaque_source_ref(c, collection=c["collection"]) for c in chunks),
        collection_resolutions=tuple(collection_resolutions),
        score_kind_divergent=case_score_kind_divergent,
    )


async def run_all(
    *,
    artifact: QueryVectorArtifact,
    query_entries: Sequence[Mapping[str, str]],
    resolve_client: Callable[[str], Any],
    bm25: Any | None = None,
) -> list[QueryOutcome]:
    """Resolve every query's vector (all-or-nothing) then run each through
    `run_query`, in order. Never calls `resolve_client` if `resolve_vectors`
    raises. Lets `RetrievalError` propagate — the WHOLE batch aborts, never
    scored, never partially written. `unbuildable:no_collections` cases do
    NOT abort the batch — they are recorded and the loop continues.
    """
    resolved = resolve_vectors(artifact, query_entries)
    outcomes: list[QueryOutcome] = []
    for entry in query_entries:
        key = mapping_key(entry)
        outcome = await run_query(
            query_entry=entry,
            vector=resolved[key],
            resolve_client=resolve_client,
            bm25=bm25,
        )
        outcomes.append(outcome)
    return outcomes


def build_plan(query_entries: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    """The call graph `run_all()` WOULD execute for `query_entries` — pure,
    no I/O, no client, no config import (see module docstring HC5): every
    per-query decision comes from `_plan_for_query`, the SAME function
    `run_query()` calls.
    """
    cases: list[dict[str, Any]] = []
    for entry in query_entries:
        query = entry.get("query", "")
        planned_domain, collections, translation_changes_query = _plan_for_query(query)
        cases.append(
            {
                "query_key": mapping_key(entry)
                if "query" in entry and "query_lang" in entry
                else None,
                "query": query,
                "query_lang": entry.get("query_lang"),
                "planned_domain": planned_domain,
                "planned_collections": collections,
                "case": "scored" if collections else "unbuildable:no_collections",
                "translation_changes_query": translation_changes_query,
            },
        )
    return {
        "query_count": len(query_entries),
        "cases": cases,
        "fixed_constants": {
            "search_user_level": _SEARCH_USER_LEVEL,
            "chunks_per_collection_limit": _CHUNKS_PER_COLLECTION_LIMIT,
            "max_chunks": _MAX_CHUNKS,
            "max_chunk_chars": _MAX_CHUNK_CHARS,
        },
        "disabled_by_construction": [dict(d) for d in _DISABLED_BY_CONSTRUCTION],
        "limitations": list(_LIMITATIONS),
    }


def _canonical_plan_bytes(plan: Mapping[str, Any]) -> bytes:
    """`plan`'s canonical JSON bytes (`sort_keys=True`,
    `separators=(",", ":")`, `ensure_ascii=False`) — the EXACT bytes
    `main()` writes to `--out` in plan mode, so a `--plan-file`'s bytes at
    `--execute` time hash to precisely `_plan_sha256(plan)` and parse back
    to an object equal to `plan` (F3).
    """
    return json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8",
    )


def _plan_sha256(plan: Mapping[str, Any]) -> str:
    """sha256 of `_canonical_plan_bytes(plan)` — the "the call graph was
    actually inspected" fingerprint. `build_plan()` never adds a
    `plan_sha256` key to its own return value.
    """
    return hashlib.sha256(_canonical_plan_bytes(plan)).hexdigest()


def _manifest_index(
    manifest_cases: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    """Index the frozen mandatory manifest's cases by the SAME
    `f"{query_lang}::{query}"` key `mapping_key` uses — read-only join, no
    relabel."""
    index: dict[str, Mapping[str, Any]] = {}
    for case in manifest_cases:
        key = f"{case.get('query_lang', '')}::{case.get('query', '')}"
        index[key] = case
    return index


def build_report(
    outcomes: Sequence[QueryOutcome],
    *,
    manifest_cases: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """HC9/HC10's report shape: no chunk text (outcomes already carry
    none), the support=None sentence verbatim, the canary line, the
    orchestrator-exclusion reason, `relief_band_cases` (tax `[0.10,0.15)` /
    visa `[0.12,0.15)`), and — when `manifest_cases` is given — the frozen
    mandatory manifest's expected label beside each matching case, with NO
    verdict and NO relabel; where the manifest's score_kind differs from
    what was actually retrieved, both are shown, still no verdict.

    `inferable_count` (unchanged historical key) and the new
    `inferable_case_count` share ONE definition (A55_2/HC3): `case == "scored"`
    and neither `embedding_divergent` nor `score_kind_divergent` — a
    `score_kind_divergent` case is fully scored and reported (its own row)
    but, like an embedding-divergent one, never counted toward threshold
    inference or named in the relief band.

    `substitutions` (A55_1) is the run-level finding: every
    (query_key, collection_planned, collection_resolved) triple where
    production's search_service.py:526-532 silently re-routed a planned
    collection this run actually observed — the pack's named production
    debt for B2.3/B3, not fixed here.
    """
    manifest_index = _manifest_index(manifest_cases) if manifest_cases else {}
    divergent = [o for o in outcomes if o.embedding_divergent]
    inferable = [
        o
        for o in outcomes
        if o.case == "scored" and not o.embedding_divergent and not o.score_kind_divergent
    ]

    substitutions: list[dict[str, Any]] = []
    for outcome in outcomes:
        for planned, resolved, substituted, _duplicate in outcome.collection_resolutions:
            if substituted:
                substitutions.append(
                    {
                        "query_key": outcome.query_key,
                        "collection_planned": planned,
                        "collection_resolved": resolved,
                    },
                )

    relief_band_cases: list[str] = []
    rows: list[dict[str, Any]] = []
    for outcome in outcomes:
        row: dict[str, Any] = {
            "query_key": outcome.query_key,
            "case": outcome.case,
            "query_domain": outcome.query_domain,
            "translation_changes_query": outcome.translation_changes_query,
            "embedding_divergent": outcome.embedding_divergent,
            "score_kind_divergent": outcome.score_kind_divergent,
            "score": outcome.score,
            "generation_decision": outcome.generation_decision,
            "label_decision": outcome.label_decision,
            "collection_resolutions": [
                {
                    "collection_planned": planned,
                    "collection_resolved": resolved,
                    "substituted": substituted,
                    "duplicate_after_resolution": duplicate,
                }
                for (planned, resolved, substituted, duplicate) in outcome.collection_resolutions
            ],
        }

        manifest_case = manifest_index.get(outcome.query_key)
        if manifest_case is not None:
            row["manifest_expected_generation_gate"] = manifest_case.get("expected_generation_gate")
            row["manifest_expected_label_gate"] = manifest_case.get("expected_label_gate")
            sources = (manifest_case.get("provenance_fixture") or {}).get("sources") or []
            manifest_score_kind = sources[0].get("score_kind") if sources else None
            harness_kinds = set(outcome.score_kinds)
            if (
                manifest_score_kind is not None
                and harness_kinds
                and manifest_score_kind not in harness_kinds
            ):
                row["score_kind_disagreement"] = {
                    "manifest": manifest_score_kind,
                    "harness": sorted(harness_kinds),
                    "verdict": None,
                }

        rows.append(row)

        if (
            outcome.case == "scored"
            and not outcome.embedding_divergent
            and not outcome.score_kind_divergent
            and outcome.score is not None
        ):
            if outcome.query_domain == "tax" and 0.10 <= outcome.score < 0.15:
                relief_band_cases.append(outcome.query_key)
            elif outcome.query_domain == "visa" and 0.12 <= outcome.score < 0.15:
                relief_band_cases.append(outcome.query_key)

    return {
        "support_none_sentence": _SUPPORT_NONE_SENTENCE,
        "canary": _CANARY_LINE,
        "orchestrator_exclusion_reason": _ORCHESTRATOR_EXCLUSION_REASON,
        "divergent_count": len(divergent),
        "inferable_count": len(inferable),
        "inferable_case_count": len(inferable),
        "substitutions": substitutions,
        "relief_band_cases": relief_band_cases,
        "rows": rows,
    }


def _require_numeric(value: Any, *, name: str) -> int | float:
    """Guard the report-write boundary: refuse to embed anything that is not
    a real `int`/`float` under `name`.

    DISCOVERED DURING THIS BUILD (item E): running this suite's OWN test file
    alone is green, but `backend/tests/unit/services/rag/agentic/conftest.py`
    (lines 39-55) replaces `sys.modules["backend.app.core.config"]` with a
    fake module at IMPORT time — no fixture, no teardown — whose `settings`
    is a bare `MagicMock()` that never sets `bm25_vocab_size`/`bm25_k1`/
    `bm25_b`. Once pytest collects that conftest anywhere in the SAME
    process (e.g. a full `backend/tests/unit/services/rag` run, which
    recurses into its `agentic/` subdirectory), every LATER
    `from backend.app.core.config import settings` in the process — this
    module's included — resolves those three attributes to auto-generated
    child `MagicMock`s, which `json.dump` cannot serialize. This function
    turns that into a clear, attributable error at the point this module
    actually WRITES a report, instead of a cryptic `TypeError` three stdlib
    frames deep inside `json.encoder`; `run_and_write`'s own tests also pin
    an explicit `bm25=` so they never depend on that global at all.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(
            f"{name}={value!r} ({type(value).__name__}) is not a real int/float — "
            "refusing to write it. This is a polluted global (e.g. an unrelated "
            "test's unreverted mock on backend.app.core.config.settings), not a "
            "value this harness computed.",
        )
    return value


async def run_and_write(
    *,
    artifact_path: str | Path = DEFAULT_ARTIFACT,
    expected_sha256: str = EXPECTED_ARTIFACT_SHA256,
    query_entries: Sequence[Mapping[str, str]] | None = None,
    resolve_client: Callable[[str], Any],
    bm25: Any | None = None,
    out_path: str | Path | None = None,
    manifest_cases: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Load+verify the artifact, run every query in `query_entries` (default:
    the artifact's own full `query_list`) through `run_all`, and return
    `{"run": {...}, "cases": [...]}` — writing it to `out_path` too, when
    given.

    `resolve_client` is always caller-supplied: this function never
    constructs a vector-store client itself, live or fake. If `run_all`
    raises (`ArtifactError`/`RetrievalError`), it propagates here too and
    NO file is ever written to `out_path`.

    `manifest_cases`, when given, adds a `"report"` key built through
    `build_report(outcomes, manifest_cases=manifest_cases)` — the SAME
    HC9/HC10 report shape the offline `build_sample_report.py` rebuild
    script used to construct out-of-band from a written `--execute`
    payload. Omitting it (the default) keeps the payload exactly as before
    this parameter existed: no report key, no behavior change for any
    caller that does not pass it.
    """
    artifact = load_artifact(artifact_path, expected_sha256=expected_sha256)
    entries = list(query_entries) if query_entries is not None else artifact.query_list

    outcomes = await run_all(
        artifact=artifact,
        query_entries=entries,
        resolve_client=resolve_client,
        bm25=bm25,
    )

    bm25_meta = bm25
    if bm25_meta is None:
        # No case reached retrieval (e.g. every one unbuildable) — bm25 was
        # never constructed inside run_query either. Construct it here too,
        # from the SAME settings, so the run record is honest either way.
        from backend.app.core.config import settings as _settings

        bm25_meta = BM25Vectorizer(
            vocab_size=_settings.bm25_vocab_size,
            k1=_settings.bm25_k1,
            b=_settings.bm25_b,
        )

    payload: dict[str, Any] = {
        "run": {
            "search_user_level": _SEARCH_USER_LEVEL,
            "chunks_per_collection_limit": _CHUNKS_PER_COLLECTION_LIMIT,
            # A55_4: on the QUERY side only vocab_size determines the sparse
            # vector (bm25_vectorizer.py:288-319 — _hash_token + log(1+count);
            # k1/b are document-side). vocab_size is the ONE sparse
            # determinant reported as such.
            "bm25_sparse_determinant": {
                "vocab_size": _require_numeric(bm25_meta.vocab_size, name="bm25_vocab_size"),
            },
            # k1/b ARE still passed to the constructor, exactly as production
            # does (BM25Vectorizer's document-side scoring params) — recorded
            # here for completeness, but NEVER as sparse determinants.
            "bm25_document_side_constructor_params": {
                "k1": _require_numeric(bm25_meta.k1, name="bm25_k1"),
                "b": _require_numeric(bm25_meta.b, name="bm25_b"),
            },
            "bm25_env_presence": bm25_env_presence(),
        },
        "cases": [outcome_to_dict(o) for o in outcomes],
    }
    if manifest_cases is not None:
        payload["report"] = build_report(outcomes, manifest_cases=manifest_cases)

    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True, ensure_ascii=False)
            fh.write("\n")

    return payload


def main(argv: list[str] | None = None) -> int:
    """CLI. Default mode (no `--execute`) is the plan/dry-run: load+verify
    the FIXED artifact (no flag can swap the path or the pin, and there is
    no `--collection`/`--limit`/`--unsafe` of any kind — HC6/F1) and print
    the call graph `run_all()` would execute, together with its
    `plan_sha256`; when `--out` is given, the EXACT canonical plan bytes
    are written there too — REQUIRED when the caller intends to `--execute`
    later.

    `--execute` is the ONLY branch that constructs a real client. It
    REQUIRES both `--plan-file <path>` and `--plan-sha256 <hex>`, and
    refuses (returns `1`, before importing or constructing
    `CollectionManager`) unless (a) the named file's bytes hash to the
    given sha256 AND (b) the file's parsed plan equals the plan freshly
    recomputed NOW. `--execute` is never invoked by this PR, its tests, or
    the agent that wrote it — it exists for the LATER, separately-
    authorized live sample.
    """
    parser = argparse.ArgumentParser(
        description="B2.2 no-send retrieval harness — plan mode by default.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help=(
            "write the canonical plan bytes here too. REQUIRED if you intend to "
            "--execute later — --execute reads the plan back from --plan-file."
        ),
    )
    parser.add_argument(
        "--plan-sha256",
        default=None,
        help=(
            "the plan_sha256 printed by a prior plan-mode run. REQUIRED for "
            "--execute; refused on mismatch or absence, before any client is "
            "constructed."
        ),
    )
    parser.add_argument(
        "--plan-file",
        default=None,
        help=(
            "path to the plan file written by a prior plan-mode run's --out. "
            "REQUIRED for --execute: its bytes must hash to --plan-sha256 AND its "
            "parsed plan must equal the plan recomputed now."
        ),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "actually run retrieval against a REAL read-only vector-store client. "
            "Requires --plan-file + --plan-sha256 to match the recomputed plan. "
            "Requires separate authorization; never used by this harness's own tests."
        ),
    )
    args = parser.parse_args(argv)

    artifact = load_artifact(DEFAULT_ARTIFACT, expected_sha256=EXPECTED_ARTIFACT_SHA256)
    entries = artifact.query_list

    plan = build_plan(entries)
    plan_sha256 = _plan_sha256(plan)

    if not args.execute:
        pretty = json.dumps(
            {**plan, "plan_sha256": plan_sha256}, indent=2, sort_keys=True, ensure_ascii=False
        )
        print(pretty)
        if args.out:
            Path(args.out).write_bytes(_canonical_plan_bytes(plan))
        return 0

    def _refuse(reason: str) -> int:
        print(f"refusing --execute: {reason}", file=sys.stderr)
        return 1

    if not args.plan_file or not args.plan_sha256:
        return _refuse(
            "both --plan-file and --plan-sha256 are required, naming a plan "
            "written by a prior plan-mode run's --out and the plan_sha256 it "
            "printed.",
        )

    plan_path = Path(args.plan_file)
    try:
        file_bytes = plan_path.read_bytes()
    except OSError as exc:
        return _refuse(f"could not read --plan-file {args.plan_file!r}: {type(exc).__name__}")

    actual_file_sha256 = hashlib.sha256(file_bytes).hexdigest()
    if actual_file_sha256 != args.plan_sha256:
        return _refuse(
            f"--plan-file {args.plan_file!r} hashes to {actual_file_sha256}, "
            f"not the given --plan-sha256 {args.plan_sha256!r}.",
        )

    try:
        file_plan = json.loads(file_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return _refuse(f"--plan-file {args.plan_file!r} is not valid JSON: {type(exc).__name__}")

    if file_plan != plan:
        return _refuse(
            f"--plan-file {args.plan_file!r}'s plan does not match the plan "
            "recomputed now. Run plan mode again (no --execute) and re-supply a "
            "matching --plan-file/--plan-sha256.",
        )

    # --execute: constructs a REAL client. Deliberately isolated past the
    # plan-file gate above, imported lazily, so plan mode (the default)
    # never imports or touches anything that could reach a provider, and a
    # mismatched/missing --plan-file/--plan-sha256 never even imports
    # CollectionManager.
    import asyncio

    from backend.app.core.config import settings
    from backend.services.ingestion.collection_manager import CollectionManager
    from backend.tests.benchmarks.evidence_sufficiency import harness as _harness

    # D3 (gate-6429, folded into the B2 ledger close): --execute used to
    # write only the raw {"run", "cases"} payload, never the HC9/HC10
    # report `build_report` produces — every report in every B2.x evidence
    # pack was rebuilt OFFLINE by a standalone script instead. Loading the
    # frozen mandatory manifest here (read-only, never mutated, never sent
    # anywhere) lets run_and_write build that report directly, in-process.
    manifest_cases = _harness.load(_harness.DEFAULT_MANIFEST).get("cases")

    async def _live() -> dict[str, Any]:
        collection_manager = CollectionManager(qdrant_url=settings.qdrant_url)
        bm25 = BM25Vectorizer(
            vocab_size=settings.bm25_vocab_size,
            k1=settings.bm25_k1,
            b=settings.bm25_b,
        )

        def resolve_client(collection: str) -> Any:
            return collection_manager.get_collection(collection)

        return await run_and_write(
            artifact_path=DEFAULT_ARTIFACT,
            expected_sha256=EXPECTED_ARTIFACT_SHA256,
            query_entries=entries,
            resolve_client=resolve_client,
            bm25=bm25,
            out_path=args.out,
            manifest_cases=manifest_cases,
        )

    report = asyncio.run(_live())
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
