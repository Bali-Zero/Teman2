# Subdomain Migration Benchmark

## Date: 2026-03-08

## PRE-REMOVAL (monolith still has all features)

### zantara.balizero.com (monolith — apps/mouth/)

| Route              | Status | TTFB   | Size    |
| ------------------ | ------ | ------ | ------- |
| `/`                | 307    | 0.171s | 15b     |
| `/email`           | 200    | 0.699s | 37,457b |
| `/calendar`        | 200    | 0.670s | 37,107b |
| `/documents`       | 200    | 0.822s | 49,128b |
| `/knowledge`       | 200    | 0.443s | 48,118b |
| `/knowledge/kitas` | 200    | 0.905s | 48,588b |

### Standalone subdomains

| URL                            | Status | TTFB   | Size    |
| ------------------------------ | ------ | ------ | ------- |
| `knowledge.balizero.com/`      | 200    | 0.480s | 15,268b |
| `knowledge.balizero.com/kitas` | 200    | 0.739s | 15,703b |
| `mail.balizero.com/`           | 307    | 0.404s | 4,204b  |
| `calendar.balizero.com/`       | 307    | 0.685s | 4,160b  |
| `drive.balizero.com/`          | 307    | 0.680s | 4,423b  |

### Initial observations

- Knowledge standalone serves ~3x smaller pages (15KB vs 48KB) — no monolith shell/nav overhead
- TTFB comparable for auth-gated apps (307 redirect)
- Monolith `/documents` is heaviest at 49KB, 0.822s TTFB

---

## POST-REMOVAL (after features removed from monolith)

### Cleanup completed (local)

**Files removed from `apps/mouth/`:**

- `src/lib/api/email/` — Email API module (2 files)
- `src/lib/api/knowledge-activity.api.ts` — KB activity tracking
- `src/app/api/calendar/` — Calendar API routes (2 files)
- `src/app/api/documents/` — Document proxy routes (2 files)
- `src/lib/google-calendar.ts` — Calendar utility
- `src/components/dashboard/EmailPreview.tsx` — Dashboard widget
- `src/hooks/useDriveOptimized.ts` — Drive hooks
- `src/hooks/useFileSelection.ts` — File selection hook

**Files modified:**

- `src/lib/api/api-client.ts` — Removed EmailApi, KnowledgeActivityApi imports/getters
- `src/components/dashboard/index.ts` — Removed EmailPreview export
- `src/hooks/index.ts` — Removed drive/fileSelection hook exports

**Preserved (still used by remaining features):**

- `src/lib/api/knowledge/` — Used by search (SearchDocsModal, useSearchDocs)
- `src/lib/api/drive/` — Used by settings/integrations page (connect/disconnect)
- `src/components/documents/FileUploadField.tsx` — Used by process pages

**Verification:** 901 tests passing, 0 TypeScript errors.

### Benchmark (pending Vercel deploy)

_Monolith not yet redeployed — old routes still serve. Post-deploy benchmark needed._
