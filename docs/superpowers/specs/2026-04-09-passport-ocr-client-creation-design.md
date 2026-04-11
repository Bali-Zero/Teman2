# Passport OCR Upload — Client Creation Flow

**Date:** 2026-04-09
**Status:** Approved
**Author:** Zero + Claude Opus 4.6
**Validated by:** Gemini 3.1 Pro, DeepSeek V3 (consensus: Option A)
**Reviewed from:** 5 perspectives (Security, End User, Backend, Frontend, Product)

---

## 1. Problem

Creating a new client in `/clients/new` requires manually typing passport data (name, nationality, DOB, passport number, expiry). This is error-prone — transcription mistakes on passport numbers and dates cause downstream issues in visa processing.

## 2. Solution

Add a **Passport Scan** option to the Personal Details tab. Upload passport photo → OCR extracts 6 fields → user reviews per-field → confirms → form pre-fills. On submit, passport image saves to Google Drive `00_Profile/`.

**Two paths coexist:**
- **Scan Passport** — upload → OCR → review → pre-fill 6 fields
- **Fill Manually** — current flow, unchanged

## 3. Architecture

### 3.1 Endpoint: Refactor `extract-passport-enhanced`

**No new endpoint.** Refactor existing `POST /api/crm/clients/extract-passport-enhanced` to accept `client_id: int | None = None`.

- `client_id = None` → **preview mode**: OCR only, no DB write, no Drive save. Returns extracted fields.
- `client_id = int` → **persist mode**: existing behavior (OCR + DB update + Drive).

```python
class PassportPreviewRequest(BaseModel):
    image_base64: str = Field(..., max_length=14_000_000)  # ~10MB after base64
    mime_type: str = "image/jpeg"
    client_id: int | None = None  # None = preview mode

class PassportPreviewResponse(BaseModel):
    success: bool
    confidence: float  # 0.0-1.0
    fields: PassportFields
    warnings: list[str] = []

class PassportFields(BaseModel):
    full_name: str | None = None       # Title Case normalized
    nationality: str | None = None     # Full name (not ISO3)
    date_of_birth: str | None = None   # YYYY-MM-DD
    gender: str | None = None          # "M" or "F"
    passport_number: str | None = None
    passport_expiry: str | None = None # YYYY-MM-DD
    issuing_country: str | None = None
```

**Location:** `crm_clients_documents.py` — refactor `extract_passport_enhanced` (function starts at line 276, endpoint body spans ~276-506). The current `PassportEnhancedRequest` takes `client_id: int` + `file_id: str`. The refactor replaces `file_id` with `image_base64` and makes `client_id` optional. This is a **breaking change** to the request shape — the existing test at `tests/unit/app/routers/test_crm_clients.py:436` sends `{"client_id": 99, "file_id": "..."}` and must be updated.

**Normalization utilities to create:**
- `_title_case(name: str) -> str` — Python `str.title()` with fix for apostrophes/hyphens (O'BRIAN → O'Brian, not O'brian)
- `ISO3_TO_NATIONALITY: dict[str, str]` — inline mapping dict (copy from `scripts/normalize_nationalities.py:NATIONALITY_MAP`, ~100 entries). Must match `COMMON_NATIONALITIES` in frontend `crm.types.ts`.

### 3.2 Security Hardening

| Measure | Implementation |
|---------|---------------|
| **Body size limit** | `max_length=14_000_000` on `image_base64` field |
| **Rate limit** | 10 calls/minute per authenticated user (add `slowapi` or custom middleware) |
| **PII log scrubbing** | Log ONLY `success`, `confidence`, `fields_count`. NEVER extracted values |
| **Consent gate** | Frontend shows toast "Passport data will be processed by AI to extract information" with Accept before sending |
| **Auth** | `Depends(get_current_user)` — team members only |

### 3.3 Data Normalization (in backend response)

| Raw MRZ | Normalized | How |
|---------|-----------|-----|
| `KIRMASOV<<MAKSIM` | `Kirmasov Maksim` | `toTitleCase()` |
| `RUS` | `Russian` | ISO 3166-1 alpha-3 → nationality name lookup |
| `900512` (YYMMDD) | `1990-05-12` | Parse with century logic (>50 = 19xx, ≤50 = 20xx) |
| `M` | `M` | Pass through |
| `3011177` (YYMMDD) | `2030-11-17` | Same century logic |

### 3.4 Vision Model

- **Primary:** Gemini 2.0 Flash Lite (existing, already configured)
- **Fallback on Fly.io:** None. If Gemini down → return `{ success: false, warnings: ["OCR service unavailable"] }`
- **qwen2.5vl:7b** is local-only (Pro/Air) — NOT available on Fly.io. Design does NOT rely on it.

### 3.5 Drive Upload — Race Condition Fix

**Problem:** `createClient` creates Drive folder as `BackgroundTask` (async). `uploadDocumentBase64` runs immediately after and folder may not exist.

**Fix: Frontend retry with exponential backoff** (NOT synchronous creation).

Making `create_client_folder` synchronous is too slow — it creates 15+ subfolders via sequential Google Drive API calls, taking 10-30s on Fly.io shared CPU. This would cause frontend timeouts.

**Instead:** Keep `BackgroundTask` as-is. Frontend upload retries with exponential backoff:
```
attempt 1: wait 2s  → try upload
attempt 2: wait 4s  → try upload  
attempt 3: wait 8s  → try upload
all fail  → toast "Client created. Upload passport later from profile." + link
```

**Implementation:** Add `uploadWithRetry()` helper in `PassportScanSection.tsx` that wraps `uploadDocumentBase64` with 3 retry attempts.

## 4. Frontend Design

### 4.1 UI — Personal Details Tab

**New section at top, before existing fields:**

```
┌──────────────────────────────────────────────────────┐
│  📄 Passport Scan (optional)                          │
│                                                        │
│  ┌─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐  │
│  │  📷 Drop passport photo here or click to browse  │  │
│  │  JPG, PNG — max 10MB                             │  │
│  │  (on mobile: opens camera)                        │  │
│  └─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘  │
│                                                        │
│  Or skip and fill fields manually below                │
└──────────────────────────────────────────────────────┘
```

**After OCR success (per-field confirmation):**

```
┌──────────────────────────────────────────────────────┐
│  📄 Passport Scan  ✅ Extracted                       │
│                                                        │
│  ┌────────┐  ☑ Full Name:     Kirmasov Maksim         │
│  │ thumb  │  ☑ Nationality:   Russian                  │
│  │        │  ☑ Date of Birth: 1990-05-12               │
│  └────────┘  ☑ Gender:        Male                     │
│              ☑ Passport No:   758120246                 │
│              ☑ Expiry:        2030-11-17                │
│                                                        │
│  ⚠️ Passport expired (if applicable)                  │
│                                                        │
│  Uncheck fields you want to fill manually              │
│  [✓ Apply selected]  [✗ Discard all]                  │
└──────────────────────────────────────────────────────┘
```

**Low confidence (< 0.7):**

```
┌──────────────────────────────────────────────────────┐
│  📄 Passport Scan  ⚠️ Low quality                     │
│                                                        │
│  Photo quality is too low for reliable extraction.     │
│  Please try a clearer photo or fill manually below.    │
│                                                        │
│  [🔄 Try another photo]  [Fill manually]              │
└──────────────────────────────────────────────────────┘
```

### 4.2 State Management

```typescript
type PassportOcrState =
  | { status: 'idle' }
  | { status: 'consent' }           // Showing AI consent toast
  | { status: 'uploading' }         // File being read as base64
  | { status: 'processing' }        // API call in progress
  | { status: 'preview'; result: PassportOcrResult }  // Showing extracted fields
  | { status: 'confirmed'; file: string }             // User confirmed, file in state
  | { status: 'discarded' }         // User discarded, back to manual
  | { status: 'error'; message: string };             // OCR failed

// useReducer, not useState booleans
const [ocrState, dispatch] = useReducer(passportOcrReducer, { status: 'idle' });
```

### 4.3 Cross-Tab Pre-Fill

When user clicks "Apply selected":
1. Checked fields update `formData` via `setFormData()`
2. Clear `fieldErrors` for each updated field
3. Add badge on Basic Info tab: "✨ Updated from passport"
4. `full_name` (Basic Info tab) updated silently — badge makes it visible

### 4.4 Mobile Support

```tsx
<input
  type="file"
  accept="image/jpeg,image/png"
  capture="environment"  // Opens rear camera on mobile
  onChange={handlePassportUpload}
/>
```

### 4.5 Submit Flow (revised)

```
1. Zod validate form
2. const newClient = await api.crm.createClient(cleanData, user.email)
   // MUST capture response — currently discarded at line 124
3. IF passportFile in ocrState:
   await uploadWithRetry(newClient.id, {
     file: passportFile,
     file_name: `passport_${formData.full_name.replace(/\s/g, '_')}.jpg`,
     document_type: "passport",
     document_category: "personal",  // → routes to 00_Profile
     expiry_date: formData.passport_expiry
   })
   // uploadWithRetry: 3 attempts with 2s/4s/8s backoff
   // On final failure → toast "Client created. Upload passport later from profile." + link
4. router.push(`/clients/${newClient.id}`)  // Go to new client profile
```

**Note:** `formData` must include `gender` in initial state (currently missing from `page.tsx` lines 52-71). Add `gender: undefined` to initial state so OCR can pre-fill it. Gender is NOT shown as a visible form field — it's submitted silently in the payload via `CreateClientParams.gender`.

## 5. Files to Modify

### Backend (1 file)
| File | Change |
|------|--------|
| `apps/backend-rag/backend/app/routers/crm_clients_documents.py` | Refactor `extract-passport-enhanced` (line 276+) to accept `client_id: None` for preview mode + `image_base64` instead of `file_id`. Add `max_length=14_000_000` on base64 field. Scrub PII from log lines 186/400/698/852. Fix `httpx.AsyncClient()` inline creation at line 142 (Golden Rule #10 violation) — use persistent client. Add `ISO3_TO_NATIONALITY` dict + `_title_case()` utility for normalization. |

**Note:** `crm_clients.py` unchanged — Drive folder stays as BackgroundTask. Frontend handles timing via retry.

### Frontend (4 files)
| File | Change |
|------|--------|
| `apps/mouth/src/app/(workspace)/clients/new/page.tsx` | Add PassportScanSection component, useReducer for OCR state, add `gender` to formData initial state, modify handleSubmit to capture createClient response + retry upload, change redirect to `/clients/${id}` |
| `apps/mouth/src/lib/api/crm/crm.api.ts` | Add `extractPassportPreview(base64, mimeType)` method |
| `apps/mouth/src/lib/api/crm/crm.types.ts` | Add `PassportOcrResult`, `PassportOcrField` types |
| `apps/mouth/src/lib/api/crm/crm.schemas.ts` | No change needed — `optionalDate` validator already validates `YYYY-MM-DD` regex. OCR output in this format passes validation. |

### New Files (1)
| File | Purpose |
|------|---------|
| `apps/mouth/src/app/(workspace)/clients/new/components/PassportScanSection.tsx` | Self-contained passport upload + OCR preview + per-field confirmation component. Uses raw `<input capture="environment">` (NOT FileUploadField — it lacks `capture` prop). |

### Test to Update (1)
| File | Change |
|------|--------|
| `apps/backend-rag/backend/tests/unit/app/routers/test_crm_clients.py` | Line 436: update test payload from `{"client_id": 99, "file_id": "..."}` to `{"image_base64": "...", "client_id": 99}` |

## 6. Out of Scope (future)

- KTP / KITAS card OCR (different prompt, same architecture)
- "Quick Add from Passport" standalone flow on `/clients` list page
- Document-agnostic "Smart Scan" routing
- Usage analytics tracking (`passport_ocr_used` in custom_fields)
- Per-user rate limiting middleware (slowapi)

## 7. Testing

- **Unit:** Passport field normalization (title case, ISO3 → nationality, date parsing)
- **Integration:** Preview mode returns fields without DB side effects
- **E2E:** Upload passport → confirm → create client → verify passport in Drive + PassportCard visible
- **Edge cases:** Blurry photo, expired passport, non-Latin alphabet, rotated image, oversized file

## 8. Acceptance Criteria

1. User can upload passport in Personal Details → 6 fields extracted and shown
2. Per-field checkboxes let user select which values to use
3. Unchecked fields remain empty for manual input
4. On submit: client created + passport saved in `00_Profile/` in Google Drive
5. Client profile shows passport in PassportCard
6. If OCR fails: clear message, form stays usable for manual entry
7. If upload fails: client still created, toast with link to profile
8. No PII in server logs
9. Mobile: camera opens directly via `capture="environment"`
