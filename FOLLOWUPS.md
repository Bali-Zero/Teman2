# Follow-ups — Open Tracking

Living list of non-trivial tech-debt items. Each section is owned by the PR
that introduced it and should link to its tracking artifacts (issues,
commits, docs).

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
