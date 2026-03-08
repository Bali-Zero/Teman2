# Session Changelog — 2026-02-27

## Summary

Merge conflict resolution, KBLI Navigator routing fix, documentation updates.

---

## 1. Merge Conflicts (origin/main)

**Resolved files:**

- `.mcp.json` — kept remote version
- `apps/backend-rag/backend/app/metrics.py`
- `apps/backend-rag/backend/app/utils/error_sanitizer.py`
- `apps/backend-rag/backend/tests/unit/llm/providers/test_ollama.py`
- `apps/backend-rag/backend/tests/unit/llm/providers/test_openrouter_comprehensive.py`
- `apps/backend-rag/backend/tests/unit/services/rag/agentic/test_reasoning.py`
- `apps/backend-rag/backend/tests/unit/services/rag/agentic/test_reasoning_comprehensive.py`
- `apps/backend-rag/backend/tests/unit/services/routing/test_golden_router_service.py`
- `apps/backend-rag/backend/tests/unit/services/routing/test_priority_override.py`
- `apps/backend-rag/backend/tests/unit/utils/test_path_validator.py`

**Commit:** `2ff3507f8` — merge: resolve conflicts with origin/main

---

## 2. KBLI Navigator — Redirect & Links

**Problem:** `/kbli-navigator` returned 404 (static `index.html` removed in dfdd380de, rewrite never configured).

**Solution:**

- Added permanent redirects in `next.config.ts`: `/kbli-navigator` → `/kbli`, `/kbli-navigator/:path*` → `/kbli/:path*`
- Updated KBLISearch, NewsPageClient, KBLINavigatorSection to use `/kbli`
- Adapted e2e test for new Next.js `/kbli` page

**Commit:** `e9b8037a2` — fix(frontend): redirect /kbli-navigator to /kbli, update links and e2e

**Files changed:**

- `apps/mouth/next.config.ts`
- `apps/mouth/src/components/kbli/KBLISearch.tsx`
- `apps/mouth/src/app/(blog)/NewsPageClient.tsx`
- `apps/mouth/src/app/(blog)/components/KBLINavigatorSection.tsx`
- `apps/mouth/e2e/zantara-expert-deep-test.spec.ts`

---

## 3. Documentation Updates

- **CLAUDE.md:** Added KBLI Navigator routes table, updated Last Updated
- **apps/mouth/public/kbli-navigator/SUMMARY.md:** Updated status for Next.js `/kbli` app and redirect
- **docs/CHANGELOG_SESSION_2026-02-27.md:** This file

---

## 4. Deployment Status

| Component         | Status                                                     |
| ----------------- | ---------------------------------------------------------- |
| Backend (Fly.io)  | Deployed                                                   |
| Frontend (Vercel) | Push completed; redirect propagation may need verification |
| Merge             | Completed                                                  |

---

## 5. Next Steps (for future sessions)

- [ ] Verify redirect live on balizero.com / kita.balizero.com (Vercel project config)
- [ ] Rewrite e2e skipped tests for new ZantaraChat UI (if needed)
