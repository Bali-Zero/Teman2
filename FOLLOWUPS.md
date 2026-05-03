# Follow-ups — Open Tracking

Living list of non-trivial tech-debt items. Each section is owned by the PR
that introduced it and should link to its tracking artifacts (issues,
commits, docs).

## Open Tracking Issues (TODO remediation)

Living list of TODOs converted from inline comments. Every entry here has a
GitHub issue; every in-code `TODO(#N)` should point to one of these. If you
close an item on GitHub, also delete it here.

| Issue | File (line)                                                                | Summary                                                      |
| ----- | -------------------------------------------------------------------------- | ------------------------------------------------------------ |
| [#76](https://github.com/Balizero1987/Teman2/issues/76) | `apps/backend-rag/backend/core/chunker.py:232`                             | Implement page-aware chunking (respect page_markers)         |
| [#77](https://github.com/Balizero1987/Teman2/issues/77) | `apps/backend-rag/backend/app/routers/dream.py:64`                         | Replace Dream Room `MOCK_DB` with Postgres JSONB persistence |
| [#78](https://github.com/Balizero1987/Teman2/issues/78) | `apps/backend-rag/backend/app/routers/dream.py:84`                         | Swap the mock scraper for Firecrawl / BeautifulSoup          |
| [#79](https://github.com/Balizero1987/Teman2/issues/79) | `apps/backend-rag/backend/app/routers/debug.py:131`                        | Wire `/admin/debug/logs` to Loki or `fly logs --json`        |
| [#80](https://github.com/Balizero1987/Teman2/issues/80) | `apps/backend-rag/backend/app/routers/newsletter.py:210`                   | Send double-opt-in confirmation email (Brevo)                |
| [#81](https://github.com/Balizero1987/Teman2/issues/81) | `apps/backend-rag/backend/services/rag/kg_auto_expansion.py:233`           | Share `ENTITY_PATTERNS` between entity_extractor and kg_auto_expansion |
| [#82](https://github.com/Balizero1987/Teman2/issues/82) | `apps/backend-rag/backend/services/integrations/google_drive_service.py:741` | Use native Drive `pageToken` pagination                      |

All open items carry the `tech-debt` label on GitHub.

### Conventions (TODO)

- Inline TODOs MUST reference an issue: `# TODO(#123): short description`.
- A TODO without an issue number is a review-blocker. Either open an issue and link it, or delete the comment.
- Closing an issue without updating this file is fine — CI can regenerate it later.

## Mypy strict-module expansion

Introduced with `ci(mypy): enforce strict typing on core and models modules`.
The CI gate (`.github/workflows/tests.yml`) runs mypy only on the strict
allowlist in `apps/backend-rag/pyproject.toml → [[tool.mypy.overrides]]`.
The modules below had >5 pre-existing errors and are intentionally
**outside** the allowlist. Each needs a dedicated cleanup pass before it can
be promoted. Error counts are from the 2026-04-17 baseline.

| File                                                                  | Errors | Notes                                                          |
| --------------------------------------------------------------------- | ------ | -------------------------------------------------------------- |
| `apps/backend-rag/backend/core/plugins/executor.py`                   | 37     | untyped generics, missing return types, dynamic dispatch       |
| `apps/backend-rag/backend/core/qdrant_db.py`                          | 18     | `dict`/`list` generic params, `Any` returns from qdrant client |
| `apps/backend-rag/backend/core/legal/hierarchical_indexer.py`         | 12     | generics + missing annotations                                 |
| `apps/backend-rag/backend/core/cache.py`                              | 12     | async contextmanager typing                                    |
| `apps/backend-rag/backend/core/embeddings.py`                         | 10     | OpenAI response shape untyped                                  |
| `apps/backend-rag/backend/core/chunker.py`                            | 10     | legacy function annotations                                    |
| `apps/backend-rag/backend/core/plugins/registry.py`                   | 9      | dynamic plugin loading                                         |
| `apps/backend-rag/backend/core/redis_manager.py`                      | 6      | redis-py stubs                                                 |
| `apps/backend-rag/backend/core/parsers.py`                            | 6      | `ebooklib`/`fitz` missing stubs + unreachable branches         |
| `apps/backend-rag/backend/core/legal/structure_parser.py`             | 5      | regex match typing                                             |
| `apps/backend-rag/backend/core/reranker.py`                           | 3      | conditional function re-definition                             |

Promote modules by (a) fixing their errors, (b) appending them to the
`module = [...]` allowlist in `pyproject.toml`, (c) re-running
`cd apps/backend-rag && mypy backend/core backend/app/models`. No CI change
is required for promotion.
