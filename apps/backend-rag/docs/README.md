# Backend Docs Index

This directory is the canonical documentation hub for the Nuzantara RAG backend.
Use the links below for API reference, architecture diagrams, and documentation
standards that keep the OpenAPI schema complete and accurate.

## Quick Links

- OpenAPI / Swagger: `OPENAPI.md`
- Architecture (Mermaid): `ARCHITECTURE.md`
- Docstring standards: `DOCSTRINGS.md`
- AI deep study index: `ai/BACKEND_STUDY_INDEX.md`

## OpenAPI / Swagger

The full, generated OpenAPI schema is the canonical source of truth for every
endpoint. It is exposed by the running service and a snapshot is committed in
`apps/backend-rag/openapi.json`.

- Swagger UI (local): `http://localhost:8080/docs`
- OpenAPI JSON: `http://localhost:8080/api/v1/openapi.json`

Details and regeneration steps are in `OPENAPI.md`.

## Architecture

See `ARCHITECTURE.md` for high-level system context, request flows, and
ingestion/knowledge-graph diagrams (Mermaid).

## Documentation Standards

Docstrings are required for all FastAPI endpoints, services, and public methods
to ensure the OpenAPI schema is descriptive and accurate. See `DOCSTRINGS.md`.

## Additional References

- `API_SEARCH_SERVICES.md` - Search and retrieval service details
- `PORTAL_SYNC_ARCHITECTURE.md` - Portal integration architecture
- `DISTRIBUTED_TRACING.md` - Observability, tracing, and monitoring
