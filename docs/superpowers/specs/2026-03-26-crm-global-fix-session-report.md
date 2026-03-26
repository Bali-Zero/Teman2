# CRM Global Fix — Session Report

_Date: 2026-03-26_
_Plan: `docs/superpowers/plans/2026-03-26-crm-global-fix.md`_
_Design: `docs/superpowers/specs/2026-03-26-crm-global-fix-design.md`_

## Status: ✅ COMPLETE

- **Backend tests:** 22/22 passing
- **Frontend TypeScript:** 0 errors
- **Backend deploy:** Live (nuzantara-rag.fly.dev, rolling strategy)
- **Frontend deploy:** Vercel auto-deploy triggered on push to main

---

## Round 1 — Security (5 vulnerabilities fixed)

### Planned fixes (3)

| Endpoint                          | Vulnerability                                                              | Fix                                                                                 |
| --------------------------------- | -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `POST /extract-passport-enhanced` | `_current_user` ignored — any admin could read/write any client's passport | `verify_client_access` + `except HTTPException: raise`                              |
| `POST /extract-npwp`              | No `client_id`, no access control, extracted NPWP discarded                | Added `client_id`, RBAC, `base64.b64decode(validate=True)`, saves to `clients.npwp` |
| `POST /extract-nib`               | Identical to NPWP                                                          | Same fix, saves to `clients.nib`                                                    |

### Red team discoveries (2 additional HIGH)

| Endpoint                          | Vulnerability                                          | Fix                                                 |
| --------------------------------- | ------------------------------------------------------ | --------------------------------------------------- |
| `POST /extract-passport` (base)   | Same `_current_user` pattern as enhanced version       | RBAC added                                          |
| `DELETE /documents/{document_id}` | Any authenticated user could delete any document by ID | `verify_client_access(doc["client_id"], ...)` added |

**Key pattern established:** All OCR/mutation endpoints now follow:

```python
async with db_pool.acquire() as conn:
    await verify_client_access(request.client_id, current_user, conn, allow_assigned=True)
    # ... rest of logic
except HTTPException:
    raise  # always before outer except Exception
except Exception as e:
    ...
```

**Commits:** `a6a347139`, `7936bf0e6`, `0285bea04` + red team fixes inside the same deploy

---

## Round 2 — UX/Bug (frontend + backend)

### Frontend fixes

| File                   | Issue                                                                                   | Fix                                                                                                   |
| ---------------------- | --------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `clients/new/page.tsx` | Avatar upload silently disabled — `avatar_url` missing from Zod schema                  | Added to `createClientSchema` + `CreateClientParams`, uncommented UI                                  |
| `AddCompanyModal.tsx`  | `extractNpwp`/`extractNib` not awaited; `Promise.all` silently dropped partial failures | `void extractNpwp()`, `Promise.allSettled` + toast on partial failure; added `client_id` to OCR calls |
| `VisaCard.tsx`         | Empty OCR catch — failures invisible                                                    | Auto-extract: `logger.error`; manual: `toast.error`                                                   |
| `PassportCard.tsx`     | One-shot OCR, no retry on failure                                                       | `ocrError` state, reset `hasTriggeredOcr` on catch, inline error + retry                              |
| `CompanyTab.tsx`       | 3 empty catch blocks                                                                    | `toast.error` + unmount guard                                                                         |
| `FamilyTab.tsx`        | `onRefresh()` not awaited in `handleDelete`                                             | Added `await`                                                                                         |
| `clients/page.tsx`     | Unsafe `as string[]` cast on assignees                                                  | Proper TypeScript type predicate                                                                      |
| `useCrmClients.ts`     | `refetch()` unhandled promise                                                           | `void refetch()`                                                                                      |
| `crm.api.ts`           | No timeout on GET operations; `response.timeline \|\| []` unsafe                        | `AbortController` 10s on 4 read methods; `Array.isArray()` guard                                      |

### Backend fixes

| File                            | Issue                      | Fix                                    |
| ------------------------------- | -------------------------- | -------------------------------------- |
| `crm_clients.py` stats endpoint | `by_practice_type` missing | Added single `GROUP BY` query (no N+1) |

### Already correct (no fix needed)

- `ImmigrationTab.tsx` — no optimistic update to roll back
- `TaxTab.tsx` — loading state already implemented
- `EditClientModal.tsx` — `date_of_birth` null guard already present
- `required-docs` endpoint — already used JOIN
- `page.tsx` `getUserProfile` — synchronous, no await needed

---

## Test coverage added

| Test class                        | Tests | What's covered             |
| --------------------------------- | ----- | -------------------------- |
| `TestExtractPassportEnhancedRBAC` | 1     | 403 on unauthorized access |
| `TestExtractNpwpRBAC`             | 2     | 403 + DB write verified    |
| `TestExtractNibRBAC`              | 2     | 403 + DB write verified    |

Previous baseline: 17 tests. Final: 22 tests.

---

## Commits (this session)

```
a6a347139  fix(security): add RBAC check on /extract-passport-enhanced
7936bf0e6  fix(security): add RBAC + NPWP storage on /extract-npwp
0285bea04  fix(security): add RBAC + NIB storage on /extract-nib
           fix(security): /extract-passport base + /documents DELETE (inside red team deploy)
9080ac862  fix(crm): restore avatar upload on client creation form
bae3af1f9  fix(crm): fix async gaps and silent failures in AddCompanyModal
55eca8a21  fix(crm): surface OCR errors in VisaCard and PassportCard
e56cc9fc6  fix(crm): surface errors in CompanyTab and FamilyTab
5dd1e4c18  perf(crm): eliminate N+1 in stats endpoint with GROUP BY
2e5a97b68  fix(crm): null-safe assignees + proper type predicate in clients page
97f41cea0  fix(crm): timeout on read ops and await refetch in CRM data layer
c8303bc2b  fix(sentinel): crm api test fixes (timeout assertions)
```
