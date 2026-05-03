# OpenAPI / Swagger Documentation

The backend uses FastAPI's automatic OpenAPI generation. Every endpoint exposed
by the service is represented in the OpenAPI schema and rendered in Swagger UI.

## Live Docs

- Swagger UI: `http://localhost:8080/docs`
- OpenAPI JSON: `http://localhost:8080/api/v1/openapi.json`
- Redoc (if enabled): `http://localhost:8080/redoc`

## Source of Truth

The canonical schema is generated at runtime by FastAPI. A committed snapshot is
available at `apps/backend-rag/openapi.json` for versioned reviews and diffs.

## Regenerating the Snapshot

Use the running app to export an up-to-date OpenAPI snapshot:

```bash
curl http://localhost:8080/api/v1/openapi.json -o openapi.json
```

From the repo root, replace `apps/backend-rag/openapi.json` with the new file.

## Ensuring Full Coverage

To keep the schema complete for all endpoints:

- Every router must set `prefix` and `tags` on `APIRouter`.
- Every endpoint must include a docstring (used as the OpenAPI description).
- All request/response models should be Pydantic models or explicit schemas.
- Use explicit `response_model` where possible.

See `DOCSTRINGS.md` for the required docstring format and examples.
