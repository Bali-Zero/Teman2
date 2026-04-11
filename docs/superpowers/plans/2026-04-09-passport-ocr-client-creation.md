# Passport OCR Client Creation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add passport photo upload + OCR extraction to the client creation form, pre-filling 6 fields and saving the passport to Google Drive.

**Architecture:** Refactor existing `extract-passport-enhanced` endpoint to accept optional `client_id` (None = stateless preview mode, returns extracted fields without DB writes). Frontend adds `PassportScanSection` component with `useReducer` state machine, per-field confirmation checkboxes, and post-creation upload with retry.

**Tech Stack:** Python/FastAPI (backend OCR), Next.js/React (frontend), Gemini 2.0 Flash Lite (vision), Google Drive API (file storage)

**Spec:** `docs/superpowers/specs/2026-04-09-passport-ocr-client-creation-design.md`

---

## File Structure

### Backend — Modify
| File | Responsibility |
|------|---------------|
| `apps/backend-rag/backend/app/routers/crm_clients_documents.py` | OCR endpoint refactor: preview mode, base64 input, normalization, PII scrub |

### Backend — New
| File | Responsibility |
|------|---------------|
| `apps/backend-rag/backend/utils/passport_normalize.py` | Title case, ISO3→nationality mapping, date normalization |

### Backend — Test Update
| File | Responsibility |
|------|---------------|
| `apps/backend-rag/backend/tests/unit/app/routers/test_crm_clients.py` | Update test payload for refactored endpoint |

### Backend — New Test
| File | Responsibility |
|------|---------------|
| `apps/backend-rag/backend/tests/unit/utils/test_passport_normalize.py` | Unit tests for normalization utilities |

### Frontend — Modify
| File | Responsibility |
|------|---------------|
| `apps/mouth/src/lib/api/crm/crm.types.ts` | Add `PassportOcrResult` type |
| `apps/mouth/src/lib/api/crm/crm.api.ts` | Add `extractPassportPreview()` method |
| `apps/mouth/src/app/(workspace)/clients/new/page.tsx` | Integrate PassportScanSection, capture createClient response, upload retry, redirect |

### Frontend — New
| File | Responsibility |
|------|---------------|
| `apps/mouth/src/app/(workspace)/clients/new/components/PassportScanSection.tsx` | Self-contained passport upload + OCR + per-field preview component |

---

## Task 1: Backend — Passport Normalization Utilities

**Files:**
- Create: `apps/backend-rag/backend/utils/passport_normalize.py`
- Create: `apps/backend-rag/backend/tests/unit/utils/test_passport_normalize.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/unit/utils/test_passport_normalize.py
"""Tests for passport field normalization utilities."""
import pytest
from backend.utils.passport_normalize import title_case_name, normalize_nationality, normalize_date


class TestTitleCaseName:
    def test_basic_uppercase(self):
        assert title_case_name("KIRMASOV MAKSIM") == "Kirmasov Maksim"

    def test_already_title_case(self):
        assert title_case_name("John Smith") == "John Smith"

    def test_apostrophe(self):
        assert title_case_name("O'BRIAN") == "O'Brian"

    def test_hyphen(self):
        assert title_case_name("JEAN-PIERRE") == "Jean-Pierre"

    def test_mrz_format(self):
        assert title_case_name("KIRMASOV<<MAKSIM") == "Kirmasov Maksim"

    def test_none(self):
        assert title_case_name(None) is None

    def test_empty(self):
        assert title_case_name("") is None


class TestNormalizeNationality:
    def test_iso3_code(self):
        assert normalize_nationality("RUS") == "Russian"

    def test_full_name(self):
        assert normalize_nationality("Russian Federation") == "Russian"

    def test_already_normalized(self):
        assert normalize_nationality("Russian") == "Russian"

    def test_uppercase(self):
        assert normalize_nationality("AUSTRALIA") == "Australian"

    def test_unknown(self):
        assert normalize_nationality("XYZLAND") == "Xyzland"

    def test_none(self):
        assert normalize_nationality(None) is None

    def test_indonesian_term(self):
        assert normalize_nationality("JERMAN") == "German"


class TestNormalizeDate:
    def test_iso_format(self):
        assert normalize_date("1990-05-12") == "1990-05-12"

    def test_yymmdd_past(self):
        assert normalize_date("900512") == "1990-05-12"

    def test_yymmdd_future(self):
        assert normalize_date("301117") == "2030-11-17"

    def test_invalid(self):
        assert normalize_date("not-a-date") is None

    def test_none(self):
        assert normalize_date(None) is None

    def test_dd_mon_yyyy(self):
        assert normalize_date("15 AUG 2029") == "2029-08-15"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/utils/test_passport_normalize.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.utils.passport_normalize'`

- [ ] **Step 3: Implement normalization utilities**

```python
# backend/utils/passport_normalize.py
"""Passport field normalization — MRZ to human-readable."""
import re
from datetime import datetime

# Source: scripts/normalize_nationalities.py (production DB audit, 227 variants)
# Subset covering ISO3 codes + common variations matching COMMON_NATIONALITIES frontend dropdown
NATIONALITY_MAP: dict[str, str] = {
    # ISO3 codes
    "AUS": "Australian", "AUSTRALIA": "Australian", "Australian": "Australian",
    "USA": "American", "US": "American", "UNITED STATES": "American",
    "UNITED STATES OF AMERICA": "American", "American": "American",
    "GBR": "British", "UNITED KINGDOM": "British", "BRITISH CITIZEN": "British", "British": "British",
    "CAN": "Canadian", "CANADA": "Canadian", "Canadian": "Canadian",
    "CHN": "Chinese", "CHINA": "Chinese", "Chinese": "Chinese",
    "NLD": "Dutch", "NETHERLANDS": "Dutch", "Dutch": "Dutch",
    "FRA": "French", "FRANCE": "French", "FRANCAISE": "French", "French": "French",
    "DEU": "German", "GERMANY": "German", "DEUTSCH": "German", "JERMAN": "German", "German": "German",
    "IND": "Indian", "INDIA": "Indian", "Indian": "Indian",
    "IDN": "Indonesian", "INDONESIA": "Indonesian", "WNI": "Indonesian", "Indonesian": "Indonesian",
    "ITA": "Italian", "ITALY": "Italian", "ITALIANA": "Italian", "Italian": "Italian",
    "JPN": "Japanese", "JAPAN": "Japanese", "Japanese": "Japanese",
    "KOR": "Korean", "KOREA": "Korean", "Korean": "Korean",
    "MYS": "Malaysian", "MALAYSIA": "Malaysian", "Malaysian": "Malaysian",
    "RUS": "Russian", "RUSSIA": "Russian", "RUSSIAN FEDERATION": "Russian",
    "RUSIA": "Russian", "Russian": "Russian",
    "SGP": "Singaporean", "SINGAPORE": "Singaporean", "Singaporean": "Singaporean",
    "ESP": "Spanish", "SPAIN": "Spanish", "SPANYOL": "Spanish", "Spanish": "Spanish",
    "SWE": "Swedish", "SWEDEN": "Swedish", "Swedish": "Swedish",
    "CHE": "Swiss", "SWITZERLAND": "Swiss", "Swiss": "Swiss",
    "UKR": "Ukrainian", "UKRAINE": "Ukrainian", "Ukrainian": "Ukrainian",
}


def title_case_name(name: str | None) -> str | None:
    """Convert MRZ uppercase name to Title Case.

    Handles: apostrophes (O'BRIAN → O'Brian), hyphens (JEAN-PIERRE → Jean-Pierre),
    MRZ separators (KIRMASOV<<MAKSIM → Kirmasov Maksim).
    """
    if not name:
        return None

    # Replace MRZ separators
    name = name.replace("<<", " ").replace("<", " ")
    name = " ".join(name.split())  # normalize whitespace

    if not name:
        return None

    def _capitalize_part(part: str) -> str:
        # Handle apostrophes: O'BRIAN → O'Brian
        if "'" in part:
            segments = part.split("'")
            return "'".join(s.capitalize() for s in segments)
        return part.capitalize()

    # Handle hyphens: JEAN-PIERRE → Jean-Pierre
    words = []
    for word in name.split():
        if "-" in word:
            words.append("-".join(_capitalize_part(p) for p in word.split("-")))
        else:
            words.append(_capitalize_part(word))

    return " ".join(words)


def normalize_nationality(nationality: str | None) -> str | None:
    """Convert ISO3 code, full country name, or variant to standard adjective form.

    Returns the normalized form matching COMMON_NATIONALITIES frontend dropdown.
    Falls back to Title Case if not in the lookup table.
    """
    if not nationality:
        return None

    cleaned = nationality.strip()

    # Direct lookup (case-sensitive first)
    if cleaned in NATIONALITY_MAP:
        return NATIONALITY_MAP[cleaned]

    # Case-insensitive lookup
    upper = cleaned.upper()
    for key, value in NATIONALITY_MAP.items():
        if key.upper() == upper:
            return value

    # Fallback: title case the input
    return cleaned.title()


def normalize_date(date_str: str | None) -> str | None:
    """Normalize date to YYYY-MM-DD format.

    Handles: ISO format, MRZ YYMMDD, "DD MON YYYY" (e.g. "15 AUG 2029").
    Returns None for unparseable dates.
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # Already ISO format
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str

    # MRZ YYMMDD (6 digits)
    if re.match(r"^\d{6}$", date_str):
        yy, mm, dd = int(date_str[:2]), int(date_str[2:4]), int(date_str[4:6])
        year = 1900 + yy if yy > 50 else 2000 + yy
        try:
            return datetime(year, mm, dd).strftime("%Y-%m-%d")
        except ValueError:
            return None

    # "DD MON YYYY" format
    try:
        dt = datetime.strptime(date_str, "%d %b %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # "DD MONTH YYYY" full month name
    try:
        dt = datetime.strptime(date_str, "%d %B %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/utils/test_passport_normalize.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/utils/passport_normalize.py backend/tests/unit/utils/test_passport_normalize.py
git commit -m "feat: add passport field normalization utilities (title case, ISO3 nationality, date)"
```

---

## Task 2: Backend — Refactor extract-passport-enhanced for Preview Mode

**Files:**
- Modify: `apps/backend-rag/backend/app/routers/crm_clients_documents.py:250-506`
- Modify: `apps/backend-rag/backend/tests/unit/app/routers/test_crm_clients.py:435-436`

- [ ] **Step 1: Write the failing test for preview mode**

Add to `backend/tests/unit/app/routers/test_crm_clients.py` after the existing test class:

```python
class TestExtractPassportPreviewMode:
    """Tests for preview mode (client_id=None) on extract-passport-enhanced"""

    def test_preview_mode_accepts_base64_without_client_id(self):
        """Preview mode should accept image_base64 and return fields without DB access."""
        from backend.app.routers.crm_clients_documents import PassportPreviewRequest

        # Should not raise
        req = PassportPreviewRequest(
            image_base64="data:image/jpeg;base64,/9j/4AAQ...",
            mime_type="image/jpeg",
            client_id=None,
        )
        assert req.client_id is None
        assert req.image_base64.startswith("data:")

    def test_preview_request_rejects_oversized_base64(self):
        """Base64 field must reject payloads over 14MB."""
        from pydantic import ValidationError

        from backend.app.routers.crm_clients_documents import PassportPreviewRequest

        with pytest.raises(ValidationError):
            PassportPreviewRequest(
                image_base64="x" * 15_000_000,
                mime_type="image/jpeg",
            )

    def test_persist_mode_requires_client_id(self):
        """Persist mode should still accept client_id as int."""
        from backend.app.routers.crm_clients_documents import PassportPreviewRequest

        req = PassportPreviewRequest(
            image_base64="data:image/jpeg;base64,/9j/test",
            client_id=99,
        )
        assert req.client_id == 99
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/app/routers/test_crm_clients.py::TestExtractPassportPreviewMode -v`
Expected: FAIL — `ImportError: cannot import name 'PassportPreviewRequest'`

- [ ] **Step 3: Refactor the endpoint**

Replace `PassportEnhancedRequest` (lines 250-254) and refactor `extract_passport_enhanced` (lines 275-506):

```python
# Replace lines 250-254 with:
class PassportPreviewRequest(BaseModel):
    """Request model for passport OCR — preview or persist mode.

    Preview mode (client_id=None): stateless OCR, no DB write, no Drive.
    Persist mode (client_id=int): OCR + DB update (existing behavior).
    """

    image_base64: str = Field(..., max_length=14_000_000)  # ~10MB after base64 overhead
    mime_type: str = "image/jpeg"
    client_id: int | None = None  # None = preview mode
```

Replace `PassportEnhancedResponse` (lines 257-272) with:

```python
class PassportPreviewResponse(BaseModel):
    """Response model for passport OCR — works for both preview and persist modes."""

    success: bool
    confidence: float = 0.0
    full_name: str | None = None
    nationality: str | None = None
    date_of_birth: str | None = None
    gender: str | None = None
    passport_number: str | None = None
    passport_expiry: str | None = None
    issuing_country: str | None = None
    birthplace: str | None = None
    mrz_line1: str | None = None
    mrz_line2: str | None = None
    name_match: bool | None = None  # Only set in persist mode
    warnings: list[str] = []
    message: str | None = None
```

Refactor the endpoint function body. Key changes:
1. Accept `image_base64` instead of `file_id` — decode base64 directly, remove the httpx Drive download block (lines 325-362)
2. If `client_id is None` (preview mode): skip DB lookup (lines 311-323), skip DB update (lines 430-481), skip name match (lines 408-419)
3. If `client_id is not None` (persist mode): keep existing DB lookup + update logic
4. Apply normalization: `title_case_name()`, `normalize_nationality()`, `normalize_date()` on extracted fields
5. **Scrub PII from logs:** Replace `logger.info(f"Enhanced OCR response: {response_text[:300]}...")` (line 400) with `logger.info(f"Passport OCR: success={bool(extracted)}, fields={len(extracted) if extracted else 0}")`
6. Also scrub line 405: Replace `logger.error(f"OCR JSON parsing failed. Raw response: {response_text[:500]}")` with `logger.error("Passport OCR: JSON parsing failed")`

Add imports at top of file:
```python
from backend.utils.passport_normalize import title_case_name, normalize_nationality, normalize_date
```

After extracting JSON from Gemini response, add normalization block:

```python
        # Normalize extracted fields
        if extracted:
            extracted["full_name"] = title_case_name(extracted.get("full_name"))
            extracted["nationality"] = normalize_nationality(extracted.get("nationality"))
            extracted["date_of_birth"] = normalize_date(extracted.get("date_of_birth"))
            extracted["expiry_date"] = normalize_date(extracted.get("expiry_date"))
            if extracted.get("gender"):
                extracted["gender"] = extracted["gender"][0].upper()  # M or F

            # Add warnings
            warnings = []
            confidence = extracted.get("confidence", 0.0)
            if confidence < 0.7:
                warnings.append("Low image quality — verify extracted fields")
            expiry = extracted.get("expiry_date")
            if expiry:
                try:
                    from datetime import date
                    if datetime.strptime(expiry, "%Y-%m-%d").date() < date.today():
                        warnings.append("Passport is expired")
                except ValueError:
                    pass
```

For preview mode (client_id is None), return immediately after normalization:

```python
        # Preview mode — return extracted fields without persisting
        if request.client_id is None:
            return PassportPreviewResponse(
                success=bool(extracted),
                confidence=extracted.get("confidence", 0.0) if extracted else 0.0,
                full_name=extracted.get("full_name") if extracted else None,
                nationality=extracted.get("nationality") if extracted else None,
                date_of_birth=extracted.get("date_of_birth") if extracted else None,
                gender=extracted.get("gender") if extracted else None,
                passport_number=extracted.get("passport_number") if extracted else None,
                passport_expiry=extracted.get("expiry_date") if extracted else None,
                issuing_country=extracted.get("nationality") if extracted else None,
                birthplace=extracted.get("birthplace") if extracted else None,
                mrz_line1=extracted.get("mrz_line1") if extracted else None,
                mrz_line2=extracted.get("mrz_line2") if extracted else None,
                warnings=warnings if extracted else ["OCR extraction failed"],
                message="Preview — fields extracted but not saved" if extracted else "Could not extract passport data",
            )
```

Base64 decoding (replaces the httpx Drive download):

```python
        # Decode base64 image
        raw_b64 = request.image_base64
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]  # Strip data URI prefix
        try:
            image_data = base64.b64decode(raw_b64, validate=True)
        except Exception:
            return PassportPreviewResponse(success=False, message="Invalid base64 image data")

        mime_type = request.mime_type
```

- [ ] **Step 4: Update the existing test**

In `test_crm_clients.py`, update line 436:
```python
# Old:
json={"client_id": 99, "file_id": "some-drive-file-id"},
# New:
json={"client_id": 99, "image_base64": "data:image/jpeg;base64,/9j/test"},
```

- [ ] **Step 5: Run all tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/app/routers/test_crm_clients.py -v -k "passport"`
Expected: ALL PASS

- [ ] **Step 6: Verify import chain**

Run: `cd apps/backend-rag && PYTHONPATH=. python -c "from backend.app.dependencies import get_current_user; print('OK')"`
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/crm_clients_documents.py backend/tests/unit/app/routers/test_crm_clients.py
git commit -m "feat: refactor extract-passport-enhanced for preview mode (stateless OCR without client_id)"
```

---

## Task 3: Backend — Deploy to Fly.io

**Files:** None (deploy only)

- [ ] **Step 1: Run core tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/services/rag/test_confidence.py -q --tb=no`
Expected: 24 passed

- [ ] **Step 2: Deploy**

Run: `cd apps/backend-rag && fly deploy --strategy rolling`
Expected: All machines healthy, DNS verified

- [ ] **Step 3: Smoke test preview endpoint**

```bash
# Test with a tiny base64 (will fail OCR but should return 200 with success=false)
curl -s -X POST "https://nuzantara-rag.fly.dev/api/crm/clients/extract-passport-enhanced" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: admin-key-2024" \
  -d '{"image_base64": "/9j/4AAQ", "mime_type": "image/jpeg"}' | python3 -m json.tool
```
Expected: `{"success": false, "message": "...", "warnings": [...]}` — NOT a 422 or 500

- [ ] **Step 4: Commit (if any hotfix needed)**

---

## Task 4: Frontend — Add Types and API Method

**Files:**
- Modify: `apps/mouth/src/lib/api/crm/crm.types.ts`
- Modify: `apps/mouth/src/lib/api/crm/crm.api.ts`

- [ ] **Step 1: Add PassportOcrResult type**

Add to `crm.types.ts` after `CreateClientParams`:

```typescript
/** Result from passport OCR preview endpoint */
export interface PassportOcrResult {
  success: boolean;
  confidence: number;
  full_name: string | null;
  nationality: string | null;
  date_of_birth: string | null;
  gender: "M" | "F" | null;
  passport_number: string | null;
  passport_expiry: string | null;
  issuing_country: string | null;
  birthplace: string | null;
  warnings: string[];
  message: string | null;
}

/** Per-field state for OCR confirmation checkboxes */
export interface PassportOcrField {
  key: keyof PassportOcrResult;
  label: string;
  value: string | null;
  checked: boolean;
  formField: keyof CreateClientParams;
}
```

- [ ] **Step 2: Add API method**

Add to `crm.api.ts` inside the `CrmApi` class:

```typescript
  /**
   * Extract passport data from image via OCR (preview mode — no DB write).
   * @param imageBase64 Base64-encoded passport image (with or without data URI prefix)
   * @param mimeType Image MIME type (default: image/jpeg)
   */
  async extractPassportPreview(
    imageBase64: string,
    mimeType: string = "image/jpeg",
  ): Promise<PassportOcrResult> {
    return this.client.request<PassportOcrResult>(
      "/api/crm/clients/extract-passport-enhanced",
      {
        method: "POST",
        body: JSON.stringify({
          image_base64: imageBase64,
          mime_type: mimeType,
        }),
      },
      30000, // 30 second timeout for OCR
    );
  }
```

Add import at top of `crm.api.ts`:
```typescript
import type { PassportOcrResult } from "./crm.types";
```

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/lib/api/crm/crm.types.ts apps/mouth/src/lib/api/crm/crm.api.ts
git commit -m "feat: add PassportOcrResult type and extractPassportPreview API method"
```

---

## Task 5: Frontend — Create PassportScanSection Component

**Files:**
- Create: `apps/mouth/src/app/(workspace)/clients/new/components/PassportScanSection.tsx`

- [ ] **Step 1: Create the component**

```tsx
'use client';

import React, { useReducer, useRef, useCallback } from 'react';
import { Camera, Check, X, Loader2, AlertTriangle, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import type { PassportOcrResult } from '@/lib/api/crm/crm.types';
import type { CreateClientInput } from '@/lib/api/crm/crm.schemas';
import { logger } from '@/lib/logger';
import { COMMON_NATIONALITIES } from '@/lib/api/crm/crm.types';

// ─── State Machine ───────────────────────────────────────────────────────────

type OcrState =
  | { status: 'idle' }
  | { status: 'consent' }
  | { status: 'uploading' }
  | { status: 'processing' }
  | { status: 'preview'; result: PassportOcrResult; file: string; checked: Record<string, boolean> }
  | { status: 'confirmed'; file: string }
  | { status: 'discarded' }
  | { status: 'error'; message: string };

type OcrAction =
  | { type: 'FILE_SELECTED' }
  | { type: 'CONSENT_ACCEPTED' }
  | { type: 'CONSENT_REJECTED' }
  | { type: 'UPLOAD_START' }
  | { type: 'PROCESSING' }
  | { type: 'OCR_SUCCESS'; result: PassportOcrResult; file: string }
  | { type: 'OCR_FAIL'; message: string }
  | { type: 'TOGGLE_FIELD'; field: string }
  | { type: 'CONFIRM' }
  | { type: 'DISCARD' }
  | { type: 'RESET' };

function ocrReducer(state: OcrState, action: OcrAction): OcrState {
  switch (action.type) {
    case 'FILE_SELECTED':
      return { status: 'consent' };
    case 'CONSENT_ACCEPTED':
      return { status: 'uploading' };
    case 'CONSENT_REJECTED':
      return { status: 'idle' };
    case 'UPLOAD_START':
      return { status: 'uploading' };
    case 'PROCESSING':
      return { status: 'processing' };
    case 'OCR_SUCCESS': {
      const checked: Record<string, boolean> = {};
      const fields = ['full_name', 'nationality', 'date_of_birth', 'gender', 'passport_number', 'passport_expiry'];
      for (const f of fields) {
        const val = action.result[f as keyof PassportOcrResult];
        checked[f] = val != null && val !== '';
      }
      return { status: 'preview', result: action.result, file: action.file, checked };
    }
    case 'OCR_FAIL':
      return { status: 'error', message: action.message };
    case 'TOGGLE_FIELD':
      if (state.status !== 'preview') return state;
      return {
        ...state,
        checked: { ...state.checked, [action.field]: !state.checked[action.field] },
      };
    case 'CONFIRM':
      if (state.status !== 'preview') return state;
      return { status: 'confirmed', file: state.file };
    case 'DISCARD':
      return { status: 'discarded' };
    case 'RESET':
      return { status: 'idle' };
    default:
      return state;
  }
}

// ─── Field mapping ───────────────────────────────────────────────────────────

const OCR_FIELDS = [
  { key: 'full_name', label: 'Full Name', formKey: 'full_name' },
  { key: 'nationality', label: 'Nationality', formKey: 'nationality' },
  { key: 'date_of_birth', label: 'Date of Birth', formKey: 'date_of_birth' },
  { key: 'gender', label: 'Gender', formKey: 'gender' },
  { key: 'passport_number', label: 'Passport Number', formKey: 'passport_number' },
  { key: 'passport_expiry', label: 'Expiry Date', formKey: 'passport_expiry' },
] as const;

// ─── Props ───────────────────────────────────────────────────────────────────

interface PassportScanSectionProps {
  onFieldsConfirmed: (fields: Partial<CreateClientInput>, file: string) => void;
  onDiscarded: () => void;
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function PassportScanSection({ onFieldsConfirmed, onDiscarded }: PassportScanSectionProps) {
  const [state, dispatch] = useReducer(ocrReducer, { status: 'idle' });
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pendingFile = useRef<string>('');

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate
    if (!file.type.startsWith('image/')) {
      dispatch({ type: 'OCR_FAIL', message: 'Please select an image file (JPG or PNG).' });
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      dispatch({ type: 'OCR_FAIL', message: 'File too large. Maximum size is 10MB.' });
      return;
    }

    // Read as base64
    const reader = new FileReader();
    reader.onload = () => {
      pendingFile.current = reader.result as string;
      dispatch({ type: 'FILE_SELECTED' });
    };
    reader.readAsDataURL(file);
  }, []);

  const handleConsentAccepted = useCallback(async () => {
    dispatch({ type: 'CONSENT_ACCEPTED' });
    dispatch({ type: 'PROCESSING' });

    try {
      const result = await api.crm.extractPassportPreview(
        pendingFile.current,
        'image/jpeg',
      );

      if (result.success && result.confidence >= 0.7) {
        dispatch({ type: 'OCR_SUCCESS', result, file: pendingFile.current });
      } else if (result.success && result.confidence < 0.7) {
        dispatch({
          type: 'OCR_FAIL',
          message: 'Photo quality is too low for reliable extraction. Try a clearer photo or fill manually.',
        });
      } else {
        dispatch({
          type: 'OCR_FAIL',
          message: result.message || 'Could not extract passport data. Fill manually.',
        });
      }
    } catch (err) {
      logger.error('Passport OCR failed', { component: 'PassportScanSection' }, err instanceof Error ? err : new Error(String(err)));
      dispatch({
        type: 'OCR_FAIL',
        message: 'OCR service unavailable. Please fill fields manually.',
      });
    }
  }, []);

  const handleConfirm = useCallback(() => {
    if (state.status !== 'preview') return;

    const fields: Partial<CreateClientInput> = {};
    for (const f of OCR_FIELDS) {
      if (state.checked[f.key]) {
        const val = state.result[f.key as keyof PassportOcrResult] as string | null;
        if (val) {
          // Validate nationality against dropdown
          if (f.formKey === 'nationality' && !COMMON_NATIONALITIES.includes(val as typeof COMMON_NATIONALITIES[number])) {
            // If OCR returned a nationality not in dropdown, skip it
            continue;
          }
          (fields as Record<string, string>)[f.formKey] = val;
        }
      }
    }

    dispatch({ type: 'CONFIRM' });
    onFieldsConfirmed(fields, state.file);
  }, [state, onFieldsConfirmed]);

  const handleDiscard = useCallback(() => {
    dispatch({ type: 'DISCARD' });
    onDiscarded();
  }, [onDiscarded]);

  const cardClass = 'rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-5 mb-5';

  // ─── Consent Dialog ──────────────────────────────────────────────────────
  if (state.status === 'consent') {
    return (
      <div className={cardClass}>
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-400 mt-0.5 shrink-0" />
          <div className="flex-1">
            <p className="text-sm text-[var(--foreground)]">
              Passport data will be processed by AI to extract information.
              No data is stored until you create the client.
            </p>
            <div className="flex gap-2 mt-3">
              <Button size="sm" onClick={handleConsentAccepted}>Continue</Button>
              <Button size="sm" variant="outline" onClick={() => dispatch({ type: 'CONSENT_REJECTED' })}>Cancel</Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ─── Processing ──────────────────────────────────────────────────────────
  if (state.status === 'uploading' || state.status === 'processing') {
    return (
      <div className={cardClass}>
        <div className="flex items-center gap-3 justify-center py-6">
          <Loader2 className="w-5 h-5 animate-spin text-[var(--accent)]" />
          <span className="text-sm text-[var(--foreground-muted)]">
            Analyzing passport... this may take a few seconds
          </span>
        </div>
      </div>
    );
  }

  // ─── Preview with Per-Field Checkboxes ───────────────────────────────────
  if (state.status === 'preview') {
    return (
      <div className={cardClass}>
        <div className="flex items-center gap-2 mb-4">
          <Check className="w-5 h-5 text-green-400" />
          <h4 className="text-sm font-semibold text-[var(--foreground)]">Passport Data Extracted</h4>
        </div>

        <div className="space-y-2 mb-4">
          {OCR_FIELDS.map(({ key, label }) => {
            const val = state.result[key as keyof PassportOcrResult] as string | null;
            if (!val) return null;
            const displayVal = key === 'gender' ? (val === 'M' ? 'Male' : 'Female') : val;
            return (
              <label key={key} className="flex items-center gap-3 text-sm cursor-pointer group">
                <input
                  type="checkbox"
                  checked={state.checked[key] ?? false}
                  onChange={() => dispatch({ type: 'TOGGLE_FIELD', field: key })}
                  className="w-4 h-4 rounded border-[var(--border)] text-[var(--accent)] focus:ring-[var(--accent)]"
                />
                <span className="text-[var(--foreground-muted)] w-28">{label}:</span>
                <span className="text-[var(--foreground)] font-medium">{displayVal}</span>
              </label>
            );
          })}
        </div>

        {/* Warnings */}
        {state.result.warnings.length > 0 && (
          <div className="mb-4">
            {state.result.warnings.map((w, i) => (
              <p key={i} className="text-xs text-amber-400 flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" />
                {w}
              </p>
            ))}
          </div>
        )}

        <p className="text-xs text-[var(--foreground-muted)] mb-3">
          Uncheck fields you want to fill manually.
        </p>

        <div className="flex gap-2">
          <Button size="sm" onClick={handleConfirm} className="gap-1">
            <Check className="w-3.5 h-3.5" />
            Apply selected
          </Button>
          <Button size="sm" variant="outline" onClick={handleDiscard} className="gap-1">
            <X className="w-3.5 h-3.5" />
            Discard all
          </Button>
        </div>
      </div>
    );
  }

  // ─── Error ───────────────────────────────────────────────────────────────
  if (state.status === 'error') {
    return (
      <div className={cardClass}>
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-red-400 mt-0.5 shrink-0" />
          <div className="flex-1">
            <p className="text-sm text-red-400">{state.message}</p>
            <div className="flex gap-2 mt-3">
              <Button size="sm" variant="outline" onClick={() => { dispatch({ type: 'RESET' }); fileInputRef.current?.click(); }} className="gap-1">
                <RotateCcw className="w-3.5 h-3.5" />
                Try another photo
              </Button>
              <Button size="sm" variant="ghost" onClick={() => dispatch({ type: 'DISCARD' })}>
                Fill manually
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ─── Confirmed ───────────────────────────────────────────────────────────
  if (state.status === 'confirmed') {
    return (
      <div className={cardClass}>
        <div className="flex items-center gap-2">
          <Check className="w-5 h-5 text-green-400" />
          <span className="text-sm text-green-400 font-medium">Passport data applied to form</span>
          <span className="text-xs text-[var(--foreground-muted)]">— passport will be saved on submit</span>
        </div>
      </div>
    );
  }

  // ─── Idle / Discarded — Upload Zone ──────────────────────────────────────
  return (
    <div className={cardClass}>
      <h4 className="text-sm font-semibold text-[var(--foreground)] flex items-center gap-2 mb-3">
        <Camera className="w-4 h-4 text-[var(--accent)]" />
        Passport Scan
        <span className="text-xs font-normal text-[var(--foreground-muted)]">(optional)</span>
      </h4>

      <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-[var(--border)] rounded-lg cursor-pointer hover:border-[var(--accent)] hover:bg-[var(--background-elevated)]/50 transition-all">
        <Camera className="w-8 h-8 text-[var(--foreground-muted)] mb-2" />
        <span className="text-sm text-[var(--foreground-muted)]">
          Drop passport photo or click to browse
        </span>
        <span className="text-xs text-[var(--foreground-muted)] mt-1">
          JPG, PNG — max 10MB
        </span>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png"
          capture="environment"
          onChange={handleFileSelect}
          className="hidden"
        />
      </label>

      <p className="text-xs text-[var(--foreground-muted)] mt-2">
        Or skip and fill fields manually below
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/mouth/src/app/\(workspace\)/clients/new/components/PassportScanSection.tsx
git commit -m "feat: add PassportScanSection component with OCR state machine and per-field confirmation"
```

---

## Task 6: Frontend — Integrate into Client Creation Form

**Files:**
- Modify: `apps/mouth/src/app/(workspace)/clients/new/page.tsx`

- [ ] **Step 1: Add imports and state**

At top of file, add import:
```typescript
import PassportScanSection from './components/PassportScanSection';
import type { CreateClientInput } from '@/lib/api/crm/crm.schemas';
```

Inside `NewClientPage`, add state for passport file and OCR badge:
```typescript
const [passportFile, setPassportFile] = useState<string | null>(null);
const [ocrApplied, setOcrApplied] = useState(false);
```

Add `gender: undefined` to the initial `formData` state (after line 70, before `}`):
```typescript
    gender: undefined,
```

- [ ] **Step 2: Add callback handlers**

After the existing `handleAvatarUpload` function, add:
```typescript
  const handleOcrFieldsConfirmed = (fields: Partial<CreateClientInput>, file: string) => {
    setFormData((prev) => ({ ...prev, ...fields }));
    setPassportFile(file);
    setOcrApplied(true);
    // Clear field errors for OCR-filled fields
    setFieldErrors((prev) => {
      const next = { ...prev };
      for (const key of Object.keys(fields)) {
        delete next[key];
      }
      return next;
    });
  };

  const handleOcrDiscarded = () => {
    setPassportFile(null);
    setOcrApplied(false);
  };
```

- [ ] **Step 3: Add upload retry helper**

```typescript
  const uploadPassportWithRetry = async (clientId: number): Promise<boolean> => {
    if (!passportFile) return true;

    const delays = [2000, 4000, 8000]; // exponential backoff
    for (let i = 0; i < delays.length; i++) {
      await new Promise((r) => setTimeout(r, delays[i]));
      try {
        await api.crm.uploadDocumentBase64(clientId, {
          file: passportFile,
          file_name: `passport_${formData.full_name?.replace(/\s/g, '_') || 'scan'}.jpg`,
          document_type: 'passport',
          document_category: 'personal',
          expiry_date: formData.passport_expiry || undefined,
        });
        return true;
      } catch (err) {
        logger.warn('Passport upload attempt failed', {
          component: 'NewClientPage',
          attempt: i + 1,
        });
        if (i === delays.length - 1) return false;
      }
    }
    return false;
  };
```

- [ ] **Step 4: Modify handleSubmit**

Replace lines 110-155 (the existing `handleSubmit`) — key changes:
1. Capture `createClient` response
2. Call `uploadPassportWithRetry` after creation
3. Redirect to `/clients/${id}` instead of `/clients`

```typescript
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFieldErrors({});

    const result = createClientSchema.safeParse(formData);
    if (!result.success) {
      const errors = flattenErrors(result.error);
      setFieldErrors(errors);
      const firstField = result.error.issues[0]?.path[0] as string;
      const personalFields = ['nationality', 'date_of_birth', 'passport_number', 'passport_expiry', 'notes'];
      const crmFields = ['status', 'lead_source', 'assigned_to', 'service_interest'];
      if (personalFields.includes(firstField)) setActiveSection('personal');
      else if (crmFields.includes(firstField)) setActiveSection('crm');
      else setActiveSection('basic');
      return;
    }

    setIsLoading(true);
    try {
      const user = await api.getProfile();
      if (!user?.email) throw new Error('User email not available');

      const cleanData: CreateClientParams = {
        ...result.data,
        tags: result.data.tags?.length ? result.data.tags : undefined,
        service_interest: result.data.service_interest?.length ? result.data.service_interest : undefined,
      };

      const newClient = await api.crm.createClient(cleanData, user.email);

      // Upload passport if present (with retry for Drive folder race condition)
      if (passportFile && newClient?.id) {
        const uploaded = await uploadPassportWithRetry(newClient.id);
        if (!uploaded) {
          // Non-blocking — client is created, passport can be uploaded later
          logger.warn('Passport upload failed after retries', { clientId: newClient.id });
          toastError(
            'Passport upload failed',
            'Client created successfully. You can upload the passport from the client profile.',
          );
        }
      }

      router.push(`/clients/${newClient.id}`);
    } catch (error) {
      logger.error('Failed to create client', { component: 'NewClientPage', action: 'createClient' }, error instanceof Error ? error : new Error(String(error)));
      let errorMessage = 'Failed to create client';
      if (error instanceof Error) {
        errorMessage = error.message;
        if (error.message.includes('{"')) {
          try {
            const parsed = JSON.parse(error.message);
            errorMessage = parsed.detail || parsed.message || error.message;
          } catch { /* Not JSON */ }
        }
      }
      setFieldErrors({ _form: errorMessage });
    } finally {
      setIsLoading(false);
    }
  };
```

Add missing import for `CreateClientParams`:
```typescript
import type { CreateClientParams } from '@/lib/api/crm/crm.types';
```

- [ ] **Step 5: Insert PassportScanSection in Personal Details tab**

In the JSX, inside `{activeSection === 'personal' && (` block, add right after the opening `<div className="rounded-xl...">`:

```tsx
            <PassportScanSection
              onFieldsConfirmed={handleOcrFieldsConfirmed}
              onDiscarded={handleOcrDiscarded}
            />
```

- [ ] **Step 6: Add OCR badge to Basic Info tab button**

In the tab bar (around line 254), modify the Basic Info button to show a badge when OCR updated full_name:

```tsx
{key === 'basic' && ocrApplied && (
  <span className="ml-1 text-xs text-green-400">*</span>
)}
```

- [ ] **Step 7: Commit**

```bash
git add apps/mouth/src/app/\(workspace\)/clients/new/page.tsx
git commit -m "feat: integrate PassportScanSection into client creation form with retry upload"
```

---

## Task 7: Frontend — Deploy and E2E Test

**Files:** None (deploy + test)

- [ ] **Step 1: Push to trigger Vercel deploy**

```bash
git push origin main
```

- [ ] **Step 2: Wait for deploy**

Check Vercel build status or:
```bash
curl -s -o /dev/null -w "%{http_code}" https://kita.balizero.com
```
Expected: 200 or 307

- [ ] **Step 3: E2E test — manual verification**

Open `https://kita.balizero.com/clients/new`:

1. Go to Personal Details tab
2. See "Passport Scan (optional)" section at top
3. Upload a passport photo
4. See consent dialog → click Continue
5. See "Analyzing passport..." spinner
6. See extracted fields with checkboxes
7. Uncheck a field → click "Apply selected"
8. Go to Basic Info tab → verify `full_name` is pre-filled
9. Fill remaining fields (email, phone)
10. Go to CRM Settings → set status, assigned_to
11. Click "Create Client"
12. Verify redirect to `/clients/{id}`
13. Verify PassportCard shows passport in overview
14. Verify Google Drive `00_Profile/` has the passport file

- [ ] **Step 4: QA screenshots**

Take screenshots of each state using `mcp__claude-in-chrome__*`:
- Idle state (upload zone)
- Processing state (spinner)
- Preview state (checkboxes)
- Confirmed state (green badge)
- Error state (retry button)
- Final client profile with PassportCard

- [ ] **Step 5: Commit any hotfixes**

---

## Summary

| Task | What | Files | Est. |
|------|------|-------|------|
| 1 | Normalization utilities + tests | 2 new | 10min |
| 2 | Backend endpoint refactor | 2 modify | 20min |
| 3 | Deploy backend | - | 5min |
| 4 | Frontend types + API method | 2 modify | 5min |
| 5 | PassportScanSection component | 1 new | 15min |
| 6 | Form integration | 1 modify | 15min |
| 7 | Deploy + E2E test | - | 15min |
| **Total** | | **5 new/modify + 3 test** | **~85min** |
