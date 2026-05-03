# Plan: Split clients/[id]/page.tsx (6394 lines → ~15 files)

## Current Structure (line map)

| Line      | Component                                                                                                        | Lines | Dependencies                                                      |
| --------- | ---------------------------------------------------------------------------------------------------------------- | ----- | ----------------------------------------------------------------- |
| 60-192    | Constants (STATUS_COLORS, ALERT_COLORS, etc.)                                                                    | 132   | None                                                              |
| 194       | `getCountryFlag` import (already extracted)                                                                      | 1     | `nationality-flags.ts`                                            |
| 197-370   | Utility functions (formatCurrency, formatPhoneNumber, getPassportAlertStatus, getVisaAlertStatus, COUNTRY_CODES) | 173   | None                                                              |
| 391-847   | **ClientDetailPage** (main orchestrator)                                                                         | 456   | All tabs, all modals, api.crm                                     |
| 849-1092  | **OverviewTab**                                                                                                  | 243   | client, stats, documents, practices, formatDate, formatCurrency   |
| 1093-1538 | **PassportCard**                                                                                                 | 445   | client, documents, formatDate, api.crm                            |
| 1540-1977 | **VisaCard**                                                                                                     | 437   | client, documents, practices, formatDate, formatCurrency, api.crm |
| 1978-2094 | **FamilyMemberUploadButton**                                                                                     | 116   | api.crm, toast                                                    |
| 2095-2230 | **DocumentsTab**                                                                                                 | 135   | clientId, documents, documentsByCategory, formatDate              |
| 2231-2631 | **FamilyTab**                                                                                                    | 400   | clientId, familyMembers, documents, formatDate                    |
| 2632-2876 | **ImmigrationTab**                                                                                               | 244   | clientId, documents, formatDate                                   |
| 2877-2994 | **ProcessTab**                                                                                                   | 117   | clientId, practices, formatDate, formatCurrency, router           |
| 2995-3089 | **TimelineTab**                                                                                                  | 94    | clientId                                                          |
| 3090-3188 | **Modal** (generic wrapper)                                                                                      | 98    | children only                                                     |
| 3189-3477 | **EditClientModal**                                                                                              | 288   | client, api.crm, onSave                                           |
| 3478-3585 | **AddFamilyMemberModal**                                                                                         | 107   | clientId, api.crm, onSave                                         |
| 3586-3762 | **EditFamilyMemberModal**                                                                                        | 176   | member, clientId, api.crm, onSave                                 |
| 3763-3918 | **AddDocumentModal**                                                                                             | 155   | clientId, api.crm, onSave                                         |
| 3919-4059 | **EditDocumentModal**                                                                                            | 140   | document, clientId, api.crm, onSave                               |
| 4060-4254 | **CompanyDocUpload**                                                                                             | 194   | companyId, api.crm, toast                                         |
| 4255-4706 | **CompanyTab**                                                                                                   | 451   | clientId, api.crm                                                 |
| 4707-5076 | **EditCompanyModal**                                                                                             | 369   | company, api.crm, onSave                                          |
| 5077-5573 | **TaxTab**                                                                                                       | 496   | clientId, formatDate                                              |
| 5574-5882 | **useCompanyForm** (hook)                                                                                        | 308   | clientId, api.crm                                                 |
| 5883-6394 | **AddCompanyModal**                                                                                              | 511   | clientId, useCompanyForm                                          |

## Target Structure

```
clients/[id]/
├── page.tsx                          (~500 lines — thin orchestrator)
├── components/
│   ├── constants.ts                  (~130 lines — STATUS_COLORS, ALERT_COLORS, etc.)
│   ├── utils.ts                      (~170 lines — formatCurrency, formatPhoneNumber, COUNTRY_CODES, alert fns)
│   ├── Modal.tsx                     (~100 lines — generic modal wrapper)
│   ├── OverviewTab.tsx               (~250 lines)
│   ├── PassportCard.tsx              (~450 lines)
│   ├── VisaCard.tsx                  (~440 lines)
│   ├── DocumentsTab.tsx              (~140 lines)
│   ├── FamilyTab.tsx                 (~520 lines — includes FamilyMemberUploadButton)
│   ├── ImmigrationTab.tsx            (~250 lines)
│   ├── ProcessTab.tsx                (~120 lines)
│   ├── TimelineTab.tsx               (~100 lines)
│   ├── CompanyTab.tsx                (~650 lines — includes CompanyDocUpload)
│   ├── TaxTab.tsx                    (~500 lines)
│   ├── modals/
│   │   ├── EditClientModal.tsx       (~290 lines)
│   │   ├── AddFamilyMemberModal.tsx  (~110 lines)
│   │   ├── EditFamilyMemberModal.tsx (~180 lines)
│   │   ├── AddDocumentModal.tsx      (~160 lines)
│   │   ├── EditDocumentModal.tsx     (~140 lines)
│   │   ├── EditCompanyModal.tsx      (~370 lines)
│   │   └── AddCompanyModal.tsx       (~520 lines — includes useCompanyForm)
│   └── types.ts                      (~50 lines — shared prop types)
```

## Shared Types to Extract (types.ts)

```typescript
export type TabType =
  | "overview"
  | "documents"
  | "process"
  | "family"
  | "immigration"
  | "visas"
  | "company"
  | "tax";

export type ModalType =
  | "edit_client"
  | "add_family"
  | "edit_family"
  | "add_document"
  | "edit_document"
  | "edit_company"
  | "add_company"
  | null;

export interface TabProps {
  clientId: number;
  formatDate: (d: string | undefined) => string;
  formatCurrency: (n: number) => string;
}

export interface ModalProps {
  onClose: () => void;
  onSave: () => void;
}
```

## Extraction Order (safest first)

### Phase 1: Zero-risk extractions (no behavior change)

1. `constants.ts` — pure data, no imports from other components
2. `utils.ts` — pure functions, already partially extracted (formatDate, getCountryFlag)
3. `types.ts` — type definitions only
4. `Modal.tsx` — generic wrapper, zero coupling

### Phase 2: Leaf tabs (no cross-tab dependencies)

5. `TimelineTab.tsx` — smallest tab, only needs clientId
6. `ProcessTab.tsx` — small, only needs practices list
7. `DocumentsTab.tsx` — simple props, no internal state
8. `ImmigrationTab.tsx` — filter of documents, no API calls

### Phase 3: Complex tabs (internal state + API calls)

9. `TaxTab.tsx` — self-contained, fetches own data
10. `CompanyTab.tsx` + `CompanyDocUpload` — self-contained, fetches own data
11. `FamilyTab.tsx` + `FamilyMemberUploadButton` — API calls for upload
12. `PassportCard.tsx` — OCR extraction, API calls
13. `VisaCard.tsx` — OCR extraction, API calls
14. `OverviewTab.tsx` — composes PassportCard + VisaCard

### Phase 4: Modals

15. All 7 modals into `modals/` directory — each is self-contained

### Phase 5: Final cleanup

16. `page.tsx` becomes thin orchestrator (~500 lines)

## Risk Assessment

| Risk                                                   | Mitigation                                 |
| ------------------------------------------------------ | ------------------------------------------ |
| Closure-captured `refreshProfile` callback             | Pass as prop to all tabs/modals            |
| `activeModal` state shared across tabs                 | Keep in page.tsx, pass setter as prop      |
| `client` / `profile` data shared across all tabs       | Keep in page.tsx, pass as props            |
| CompanyTab/TaxTab fetch own data independently         | Already isolated — safe to extract         |
| OverviewTab composes PassportCard + VisaCard           | Extract Passport/Visa first, then Overview |
| `formatDate` already in utils but some tabs use inline | Replace inline usages during split         |
| TypeScript `any` types in some callbacks               | Fix during split                           |

## Execution Strategy

- Use git worktree for isolation
- Extract one component at a time
- Run `tsc --noEmit` after each extraction
- Run `npm run build` after Phase 2 complete
- Visual QA with browser after Phase 3
- Total estimated: ~90 minutes mechanical, ~30 minutes verification
