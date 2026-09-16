SHIP

### Findings

#### MINOR: Ineffective curated-QA prefetch spends an unnecessary search for planner-greeting disagreement queries

- **File:Line**: [`apps/backend-rag/backend/app/routers/wa_package.py:143-147`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-greeting-authority/apps/backend-rag/backend/app/routers/wa_package.py#L143-L147)
- **Evidence**:
  ```python
  curated_qa_block = ""
  if match_greeting(request.query) is None:
      curated_qa_block = await orchestrator.core.curated_qa_grounding_block(
          request.query,
          {"domain": plan.domain.value},
      )
  ```
- **Concrete failing input**: `"Halo, apa kabar semuanya di kantor hari ini?"` (or any query where `QueryPlanner` assigns `QueryDomain.GREETING` but `match_greeting` returns `None`).
- **Details**: When `plan.domain` is `QueryDomain.GREETING` and `match_greeting` is `None`, `wa_package.py` passes `{"domain": "greeting"}` to `curated_qa_grounding_block`. In [`OrchestratorCore._inject_curated_qa_grounding`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-greeting-authority/apps/backend-rag/backend/services/rag/agentic/orchestrator_core.py#L595-L647), `"greeting"` passes the initial `DOMAIN_GENERAL` check, which triggers an embedding calculation and a Qdrant search against the `curated_qa` collection. However, because curated QA points only hold substantive domain tags (`"visa"`, `"company"`, `"tax"`, etc.), the per-hit check `hit_domain != domain` discards 100% of the returned hits and returns `""`. If the domain were passed as `"general"`, `_inject_curated_qa_grounding` would short-circuit immediately at line 599 with zero I/O.
- **Proposed Fix**: Align the domain passed to `curated_qa_grounding_block` with the builder's effective domain (e.g., pass `{"domain": QueryDomain.GENERAL.value}` when `plan.domain == QueryDomain.GREETING`, or skip prefetch when `plan.domain in (QueryDomain.GREETING, QueryDomain.GENERAL)`).

#### MINOR: Private symbol import across service boundaries

- **File:Line**: [`apps/backend-rag/backend/services/rag/agentic/wa_package_builder.py:63`](file:///Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-greeting-authority/apps/backend-rag/backend/services/rag/agentic/wa_package_builder.py#L63)
- **Evidence**:
  ```python
  from backend.services.rag.agentic.query_planner import _DOMAIN_COLLECTIONS, QueryPlanner
  ```
- **Concrete failing input**: N/A (architectural hygiene / encapsulation).
- **Details**: `wa_package_builder.py` directly imports the private module-level dict `_DOMAIN_COLLECTIONS` from `query_planner.py` to populate `plan.collections` when falling back to `QueryDomain.GENERAL`. While necessary here to respect the invariant that `query_planner.py` remain untouched, importing underscore-prefixed internals bypasses module encapsulation.
- **Proposed Fix**: In a future unconstrained cleanup of `query_planner.py`, expose a public helper (such as `QueryPlanner.collections_for_domain(domain: QueryDomain) -> list[str]`) or make `DOMAIN_COLLECTIONS` public.
