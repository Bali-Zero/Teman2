"""B2.1 perimeter-exclusion tripwires.

B2.1 (`research/operations/2026-09-11-bot-staff-room/B2-engine.md` §4, "Perimeter
decision") makes retrieval provenance plus a fact-support signal the primary
relevance gate for the sealed WhatsApp package. SIX code paths reach a client
without ever calling that scorer (widened 2026-09-12 from the original three —
see WIDENING NOTE below). The Dux ruled that all six stay EXCLUDED for B2.1 —
but silence about them was not acceptable, so each exclusion gets a tripwire
here that fails the day the code stops matching the reason it was excluded for.

1. The trusted-tool 0.85 bypass — `_reasoning_evidence.compute_evidence_score`
   (`backend/services/rag/agentic/_reasoning_evidence.py`, function at line 357
   / bypass branch 366-376 on this checkout, `EVIDENCE_SCORE_TRUSTED_TOOL = 0.85`
   at line 41) returns the flat constant whenever `trusted_tools_used=True`,
   WITHOUT reading `sources` at all. It serves the orchestrator/ReAct path, not
   the sealed WhatsApp package B2.1 gates — wiring it under the support signal
   would put a seat call on every orchestrator query, a latency/cost change
   outside this mandate's perimeter.
2. The FAQ fast path — `OrchestratorCore.check_faq_cache` in
   `orchestrator_core.py` (cache-hit branch returns a `CoreResult` at lines
   428-441 on this checkout) — returns straight from the Redis cache before
   any scorer is ever called. DEFENDED: `NotebookLMCacheService.set()` (the
   class backing `self.faq_cache`) raises `ValueError` if `metadata` is
   missing any of `source_ref`/`source_date`/`domain`/`confidence_class`/
   `source_priority` — verified on disk, `notebooklm_cache_service.py:262-281`.
   Only pre-vetted content can ever land in this cache.
3. The KG fast path — `OrchestratorCore._try_kg_fast_path` in the same module
   (returns a `CoreResult` built from the Neo4j KG traversal at lines
   1096-1103 on this checkout) — also returns before any scorer call.
4. The semantic-cache fast path — `OrchestratorCore.check_semantic_cache`
   (cache-hit branch, `CoreResult` returned at lines 520-528 on this
   checkout). **CORRECTED FINDING, not the reason first assumed**: this
   method reads `self.semantic_cache`, a `SemanticCache` instance from
   `backend/services/search/semantic_cache.py` — a DIFFERENT class from the
   FAQ path's `NotebookLMCacheService`. `SemanticCache.cache_result()` (its
   write method) has **no provenance validation whatsoever** — it stores
   whatever `result` dict it is handed, no required keys, no `ValueError`,
   nothing (verified on disk, `semantic_cache.py:98-142`). The #2 guardrail
   does NOT defend this path; the /bot corner's 2026-07-27 note conflated
   the two caches. The defence that actually holds today, verified by an
   AST sweep of every non-test `.py` file under `backend/`: **zero
   production call sites** exist anywhere for `SemanticCache.cache_result()`
   — the only caller in the whole tree is its own unit test. The cache is
   permanently write-empty in the shipped backend, which is why an unvetted
   entry can't reach a client through this path today. That is an accident
   of dead code, not a designed contract, and is exactly why it gets its own
   tripwire below rather than a comment.
5. The multi-agent-coordinator branch inside
   `OrchestratorCore._process_query_core_unfinalized` (the real pipeline body
   — `process_query_core` itself is a thin wrapper that calls this method
   then finalizes; verified on disk, `orchestrator_core.py:1296-1344`),
   guarded by `_MULTI_AGENT_COORDINATOR_ENABLED`, default OFF since
   2026-07-27 per `os.getenv(..., "false")`. Its own on-disk comment
   (`orchestrator_core.py:168-193`) records the reason: measured live in
   prod on 2026-07-27, this branch answered an E23 KITAS cost/timeline
   question with `sources=[] context_length=0 evidence_score=0
   abstain=false`, asserted a fabricated ~IDR 1.2 billion government fee
   beside the real `PricingTool` figure, and invented a 38-60 day phase
   breakdown — all before the abstain gate and before the only
   `_log_query_analytics` call, so the incident is invisible to
   `query_analytics` too.
6. The `SpecializedServiceRouter` fast path, same method (`if
   self._specialized_router:` branch routing to AutonomousResearch /
   CrossOracleSynthesis / ClientJourney before the ReAct loop).

Paths 3, 4, 5, 6 all `return` on their hit branch before reaching a scorer
call inside `_process_query_core_unfinalized` or a sibling method; bringing
any of them under the signal would require restructuring
`orchestrator_core`'s control flow, which is outside B2's writable perimeter
for this mandate.

WIDENING NOTE (2026-09-12): this file originally tripwired only #1/#2/#3 per
the spec. Re-grepping `orchestrator_core.py` on disk surfaced #4/#5/#6, which
were NOT named in the original perimeter decision. The Dux's own `/bot`
corner already recorded, on 2026-07-27, "THREE FAST-PATHS RETURN BEFORE THE
ABSTAIN GATE" naming exactly the Phase-6 multi-agent branch, the
SpecializedServiceRouter branch and the KG fast path — so the spec named
three, the disk had six, and the three missing were the ones this repo's own
history already expected to be named. The perimeter decision is now widened
to all six, each with its own tripwire below.

SWEEP FOR A SEVENTH PATH (2026-09-12): every `CoreResult(` construction site
in `orchestrator_core.py` was enumerated (`grep -n "CoreResult("`) — exactly
five: line 428 (#2 FAQ), line 520 (#4 semantic cache), line 1096 (#3 KG fast
path), line 1542 (#5 multi-agent coordinator, wrapped in
`FinalizationContext`), line 1572 (#6 SpecializedServiceRouter, wrapped in
`FinalizationContext`). Combined with #1's float-return bypass in
`_reasoning_evidence.py` (which builds no `CoreResult` at all — it returns a
bare score consumed elsewhere), that accounts for all SIX and only six; no
seventh `CoreResult(` construction site exists in this file today.

Every test below pins a PROPERTY of the exclusion (not today's literal
values/spelling), so a refactor that quietly closes one of these holes — or
opens a different one — fails loudly instead of the test just rotting green.
Each test's docstring states what a failure means: the exclusion recorded in
B2.1's perimeter decision no longer holds; re-open the decision, do not delete
the test.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# AST helpers — shared by the fast-path tripwires (#2-#6).
# ---------------------------------------------------------------------------

_SCORER_FUNCTION_NAMES = frozenset({"calculate_evidence_score", "compute_evidence_score"})


def _read_source_from_live_module(module: object) -> tuple[str, str]:
    """Read source from the LIVE imported module's own ``__file__``.

    Using the path the *imported* module itself reports — rather than a
    hardcoded repo-relative path — is what makes this immune to a
    ``sys.path`` shadow: if a different ``orchestrator_core.py`` earlier on
    ``sys.path`` had been imported instead, its ``__file__`` would point
    there, and the AST parsed below would be of THAT file, keeping the test
    honest about which module it actually inspected.
    """
    path = getattr(module, "__file__", None)
    assert path, f"{getattr(module, '__name__', module)!r} has no __file__ — cannot pin identity"
    with open(path, encoding="utf-8") as fh:
        return fh.read(), path


def _find_function_def(tree: ast.AST, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
            return node
    raise AssertionError(f"no function/method named {name!r} found in the parsed module AST")


def _find_if_by_test_name(func_node: ast.AST, name: str) -> ast.If:
    """Locate the unique ``If`` inside ``func_node`` whose test expression
    references a bare ``Name`` with the given id (e.g. a feature flag used
    directly, or as one operand of an ``and``/``or`` chain).
    """
    matches = [
        node
        for node in ast.walk(func_node)
        if isinstance(node, ast.If)
        and any(isinstance(n, ast.Name) and n.id == name for n in ast.walk(node.test))
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"expected exactly one `if` referencing {name!r} inside "
            f"{getattr(func_node, 'name', '?')!r}, found {len(matches)}"
        )
    return matches[0]


def _find_if_by_bare_self_attr(func_node: ast.AST, attr: str) -> ast.If:
    """Locate the unique ``If`` inside ``func_node`` whose test is exactly
    ``self.<attr>`` — a bare truthiness check, NOT a method call on it (which
    would appear as an ``ast.Call`` test instead of an ``ast.Attribute``).
    """
    matches = [
        node
        for node in ast.walk(func_node)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Attribute)
        and node.test.attr == attr
        and isinstance(node.test.value, ast.Name)
        and node.test.value.id == "self"
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"expected exactly one bare `if self.{attr}:` inside "
            f"{getattr(func_node, 'name', '?')!r}, found {len(matches)}"
        )
    return matches[0]


def _find_module_level_assignment(tree: ast.AST, name: str) -> ast.Assign:
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return node
    raise AssertionError(f"no module-level assignment to {name!r} found")


def _find_getenv_default_literal(node: ast.AST, env_var_name: str) -> str:
    """Find ``os.getenv(env_var_name, <default>)`` inside ``node`` and return
    the literal default string — pins "what the default resolves to" as a
    source-level fact rather than an env-dependent runtime read (which would
    be polluted by whatever the TEST PROCESS's own environment happens to
    set, and would require an ``importlib.reload`` this file deliberately
    avoids, since that would mutate a module shared with the rest of the
    test session).
    """
    for call in ast.walk(node):
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "getenv"
            and len(call.args) >= 1
            and isinstance(call.args[0], ast.Constant)
            and call.args[0].value == env_var_name
        ):
            if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
                return call.args[1].value
            raise AssertionError(f"os.getenv({env_var_name!r}, ...) default is not a literal")
    raise AssertionError(f"no os.getenv({env_var_name!r}, ...) call found")


def _calls_a_scorer(node: ast.AST) -> bool:
    """True if any ``Call`` inside ``node`` targets a known scorer function."""
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            called_name = None
            if isinstance(func, ast.Name):
                called_name = func.id
            elif isinstance(func, ast.Attribute):
                called_name = func.attr
            if called_name in _SCORER_FUNCTION_NAMES:
                return True
    return False


def _has_a_return(node: ast.AST) -> bool:
    return any(isinstance(child, ast.Return) for child in ast.walk(node))


def _iter_non_test_backend_python_sources(backend_root: Path):
    for path in backend_root.rglob("*.py"):
        if "tests" in path.relative_to(backend_root).parts:
            continue
        yield path


def _find_production_callers_of(backend_root: Path, method_name: str) -> list[str]:
    """Return relative paths of every non-test source file under
    ``backend_root`` whose AST contains a ``Call`` targeting an attribute or
    bare name equal to ``method_name``.
    """
    hits: list[str] = []
    for path in _iter_non_test_backend_python_sources(backend_root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = None
                if isinstance(func, ast.Attribute):
                    name = func.attr
                elif isinstance(func, ast.Name):
                    name = func.id
                if name == method_name:
                    hits.append(str(path.relative_to(backend_root)))
                    break
    return hits


# ---------------------------------------------------------------------------
# 1. Trusted-tool 0.85 bypass — `_reasoning_evidence.compute_evidence_score`
# ---------------------------------------------------------------------------


class TestTrustedToolBypassExclusion:
    """``compute_evidence_score(trusted_tools_used=True, ...)`` is a declared,
    source-blind bypass. B2.1 leaves it in place for the orchestrator/ReAct
    path.
    """

    def test_returns_flat_constant_regardless_of_sources(self) -> None:
        """A failure means the trusted-tool branch started reading `sources`
        or `context_gathered` — the declared blindness that justifies leaving
        this bypass outside B2.1's support signal no longer holds; re-open
        the perimeter decision, do not delete this test.
        """
        from backend.services.rag.agentic._reasoning_evidence import (
            EVIDENCE_SCORE_TRUSTED_TOOL,
            compute_evidence_score,
        )

        empty_sources_score = compute_evidence_score(
            trusted_tools_used=True,
            sources=[],
            context_gathered=None,
            query="what is the KITAS fee",
        )
        # Sources/context that WOULD score very differently on the
        # keyword-based (non-bypass) path — long, on-topic, numerically
        # dense — must not move the needle on the bypass branch.
        high_scoring_sources = [
            {
                "text": (
                    "The KITAS fee is exactly IDR 3,500,000 per year, "
                    "confirmed by the official 2026 Bali Zero price list."
                ),
                "score": 0.99,
            }
            for _ in range(10)
        ]
        high_score = compute_evidence_score(
            trusted_tools_used=True,
            sources=high_scoring_sources,
            context_gathered=["IDR 3,500,000 KITAS fee 2026 official price list " * 20],
            query="what is the KITAS fee",
        )

        assert empty_sources_score == EVIDENCE_SCORE_TRUSTED_TOOL
        assert high_score == EVIDENCE_SCORE_TRUSTED_TOOL
        assert empty_sources_score == high_score == pytest.approx(0.85)

    def test_takes_no_support_parameter(self) -> None:
        """A failure means someone wired a support/fact-check parameter into
        this function without telling the perimeter decision — the exclusion
        recorded in B2.1's perimeter decision no longer holds as a KNOWN,
        DECLARED hole; re-open the decision, do not delete this test.
        """
        from backend.services.rag.agentic._reasoning_evidence import compute_evidence_score

        params = inspect.signature(compute_evidence_score).parameters
        support_like = [name for name in params if "support" in name.lower()]
        assert support_like == [], (
            f"compute_evidence_score gained support-like parameter(s) {support_like} — "
            "B2.1's perimeter decision declared this function has none; re-open it."
        )


# ---------------------------------------------------------------------------
# 2-6. The five OrchestratorCore fast paths — AST structural checks.
# ---------------------------------------------------------------------------


class TestFastPathExclusions:
    """All five remaining excluded paths `return` a `CoreResult` on their hit
    branch before any scorer call is reachable, inside `OrchestratorCore` /
    `process_query_core` in `orchestrator_core.py`.
    """

    @pytest.fixture(scope="class")
    def orchestrator_core_module(self) -> object:
        module = importlib.import_module("backend.services.rag.agentic.orchestrator_core")
        assert hasattr(module, "OrchestratorCore"), (
            "orchestrator_core module has no OrchestratorCore class — module "
            "identity does not match what this tripwire expects"
        )
        return module

    @pytest.fixture(scope="class")
    def orchestrator_core_tree(self, orchestrator_core_module: object) -> ast.AST:
        source, path = _read_source_from_live_module(orchestrator_core_module)
        return ast.parse(source, filename=path)

    # -- #2 FAQ fast path ---------------------------------------------------

    def test_check_faq_cache_returns_before_any_scorer_call(
        self, orchestrator_core_module: object, orchestrator_core_tree: ast.AST
    ) -> None:
        """A failure means `check_faq_cache`'s cache-hit branch now calls (or
        no longer has a `return` on) the evidence scorer — the FAQ-fast-path
        exclusion recorded in B2.1's perimeter decision no longer holds;
        re-open the decision, do not delete this test.
        """
        assert hasattr(orchestrator_core_module.OrchestratorCore, "check_faq_cache"), (
            "OrchestratorCore.check_faq_cache not found on the live imported "
            "class — the module this test parsed does not match the one "
            "Python actually imports"
        )
        func_node = _find_function_def(orchestrator_core_tree, "check_faq_cache")
        assert _has_a_return(func_node), "check_faq_cache has no return statement at all"
        assert not _calls_a_scorer(func_node), (
            "check_faq_cache now calls an evidence scorer — the declared "
            "'FAQ fast path returns before any scorer call' exclusion no "
            "longer holds; re-open the B2.1 perimeter decision."
        )

    # -- #3 KG fast path -----------------------------------------------------

    def test_try_kg_fast_path_returns_before_any_scorer_call(
        self, orchestrator_core_module: object, orchestrator_core_tree: ast.AST
    ) -> None:
        """A failure means `_try_kg_fast_path` now calls (or no longer has a
        `return` on) the evidence scorer — the KG-fast-path exclusion
        recorded in B2.1's perimeter decision no longer holds; re-open the
        decision, do not delete this test.
        """
        assert hasattr(orchestrator_core_module.OrchestratorCore, "_try_kg_fast_path"), (
            "OrchestratorCore._try_kg_fast_path not found on the live "
            "imported class — the module this test parsed does not match "
            "the one Python actually imports"
        )
        func_node = _find_function_def(orchestrator_core_tree, "_try_kg_fast_path")
        assert _has_a_return(func_node), "_try_kg_fast_path has no return statement at all"
        assert not _calls_a_scorer(func_node), (
            "_try_kg_fast_path now calls an evidence scorer — the declared "
            "'KG fast path returns before any scorer call' exclusion no "
            "longer holds; re-open the B2.1 perimeter decision."
        )

    # -- #4 Semantic-cache fast path ------------------------------------------

    def test_check_semantic_cache_returns_before_any_scorer_call(
        self, orchestrator_core_module: object, orchestrator_core_tree: ast.AST
    ) -> None:
        """A failure means `check_semantic_cache`'s cache-hit branch now
        calls (or no longer has a `return` on) the evidence scorer — the
        semantic-cache exclusion recorded in B2.1's perimeter decision no
        longer holds; re-open the decision, do not delete this test.
        """
        assert hasattr(orchestrator_core_module.OrchestratorCore, "check_semantic_cache"), (
            "OrchestratorCore.check_semantic_cache not found on the live "
            "imported class — the module this test parsed does not match "
            "the one Python actually imports"
        )
        func_node = _find_function_def(orchestrator_core_tree, "check_semantic_cache")
        assert _has_a_return(func_node), "check_semantic_cache has no return statement at all"
        assert not _calls_a_scorer(func_node), (
            "check_semantic_cache now calls an evidence scorer — the "
            "declared 'semantic-cache fast path returns before any scorer "
            "call' exclusion no longer holds; re-open the B2.1 perimeter "
            "decision."
        )

    def test_semantic_cache_write_path_has_no_production_caller(self) -> None:
        """A failure means something now calls `SemanticCache.cache_result()`
        in production code. Unlike the FAQ cache's `NotebookLMCacheService`,
        `SemanticCache` enforces NO provenance contract on what it stores —
        so a new writer could populate this cache with never-scored content
        that `check_semantic_cache` would then serve straight to a client.
        The only thing defending this exclusion today is that the write path
        is unused; re-open the B2.1 perimeter decision before shipping a
        writer, don't just let this test rot red.
        """
        # Derived from this test file's own location (backend/tests/unit/
        # services/rag/agentic/<this file>) rather than a hardcoded absolute
        # path, so it stays correct across worktrees/checkouts.
        backend_root = Path(__file__).resolve().parents[5]
        assert backend_root.name == "backend", (
            f"expected the 5th parent of this test file to be `backend/`, got "
            f"{backend_root} — this test's own path assumption broke, fix the "
            f"parents[] index rather than the assertion"
        )
        hits = _find_production_callers_of(backend_root, "cache_result")
        assert hits == [], (
            f"SemanticCache.cache_result() now has production caller(s) {hits} — "
            "check_semantic_cache's exclusion had NO provenance guardrail "
            "defending it (that guardrail belongs to the unrelated "
            "NotebookLMCacheService/FAQ cache); its only defence was an unused "
            "write path. Re-open the B2.1 perimeter decision before this ships."
        )

    # -- #5 Multi-agent-coordinator branch ------------------------------------

    def test_multi_agent_coordinator_branch_off_by_default_and_returns_before_scorer(
        self, orchestrator_core_tree: ast.AST
    ) -> None:
        """A failure means EITHER the Phase-6 multi-agent-coordinator branch
        inside `_process_query_core_unfinalized` started calling an evidence
        scorer (or lost its `return`), OR `MULTI_AGENT_COORDINATOR_ENABLED`'s
        default
        flipped to on while the branch is still unscored — either way, the
        branch's own 2026-07-27 prod incident (fabricated ~IDR 1.2B
        government fee + invented timeline on an E23 KITAS query, answered
        with `sources=[] evidence_score=0 abstain=false`) is live again
        without the perimeter decision having re-examined it.
        """
        assign_node = _find_module_level_assignment(
            orchestrator_core_tree, "_MULTI_AGENT_COORDINATOR_ENABLED"
        )
        default_literal = _find_getenv_default_literal(
            assign_node, "MULTI_AGENT_COORDINATOR_ENABLED"
        )
        assert str(default_literal).strip().lower() not in ("1", "true", "yes"), (
            f"MULTI_AGENT_COORDINATOR_ENABLED's source default flipped to "
            f"{default_literal!r} — this branch is unscored and that default "
            "controls whether it runs in prod; re-open the B2.1 perimeter "
            "decision before shipping this default."
        )

        func_node = _find_function_def(orchestrator_core_tree, "_process_query_core_unfinalized")
        branch = _find_if_by_test_name(func_node, "_MULTI_AGENT_COORDINATOR_ENABLED")
        assert _has_a_return(branch), (
            "the _MULTI_AGENT_COORDINATOR_ENABLED-guarded branch has no "
            "return statement at all"
        )
        assert not _calls_a_scorer(branch), (
            "the multi-agent-coordinator branch now calls an evidence "
            "scorer — the declared exclusion no longer holds; re-open the "
            "B2.1 perimeter decision."
        )

    # -- #6 SpecializedServiceRouter branch ------------------------------------

    def test_specialized_service_router_branch_returns_before_any_scorer_call(
        self, orchestrator_core_tree: ast.AST
    ) -> None:
        """A failure means the `SpecializedServiceRouter` fast-path branch
        inside `_process_query_core_unfinalized` now calls (or no longer has
        a `return` on) the evidence scorer — the exclusion recorded in
        B2.1's perimeter decision no longer holds; re-open the decision, do
        not delete this test.
        """
        func_node = _find_function_def(orchestrator_core_tree, "_process_query_core_unfinalized")
        branch = _find_if_by_bare_self_attr(func_node, "_specialized_router")
        assert _has_a_return(branch), (
            "the `if self._specialized_router:` branch has no return "
            "statement at all"
        )
        assert not _calls_a_scorer(branch), (
            "the SpecializedServiceRouter branch now calls an evidence "
            "scorer — the declared exclusion no longer holds; re-open the "
            "B2.1 perimeter decision."
        )
