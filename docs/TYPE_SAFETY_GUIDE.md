# Type Safety Across Boundaries (Python <-> TypeScript)

**Implemented:** 2026-02-06
**Tooling:** `openapi-typescript` + `FastAPI OpenAPI`

## Overview

We have bridged the gap between the Python Backend (`apps/backend-rag`) and the Next.js Frontend (`apps/mouth`). You can now auto-generate TypeScript interfaces that strictly match your Pydantic models.

## 🚀 Quick Start

To sync types after changing Backend code:

```bash
# From project root
./scripts/sync-types.sh
```

This command will:

1. Extract OpenAPI JSON from FastAPI (`apps/backend-rag/openapi.json`)
2. Generate TypeScript definitions (`apps/mouth/src/lib/api/schema.d.ts`)

## 💻 Frontend Usage

Import the generated types in your Frontend code:

```typescript
import { components } from "@/lib/api/schema";

// Use generated types for strict safety
type UserProfile = components["schemas"]["UserProfile"];
type LoginResponse = components["schemas"]["LoginResponse"];

// Example API call
async function getUser(): Promise<UserProfile> {
  const res = await fetch("/api/auth/profile");
  return await res.json();
}
```

## 🏗️ Architecture

- **Source of Truth:** Python Code (`FastAPI` Models & Pydantic Schemas)
- **Intermediate:** `apps/backend-rag/openapi.json` (Auto-generated)
- **Destination:** `apps/mouth/src/lib/api/schema.d.ts` (Auto-generated)

## ⚠️ Notes

- **Do NOT** manually edit `schema.d.ts`. It will be overwritten.
- **Do NOT** manually edit `openapi.json`.
- The manual file `apps/mouth/src/lib/api/openapi.yaml` still exists for documentation/SwaggerUI purposes but is **decoupled** from this type generation pipeline to ensure code-level accuracy.
