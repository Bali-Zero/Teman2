# CRM Global Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Risolvere 67 issue nel CRM `/clients` — 3 critici security backend + 14 round UX/bug frontend e backend.

**Architecture:** Round 1 chiude i buchi RBAC nel backend con loop fix→test→redteam. Round 2 attacca frontend e backend sequenzialmente file per file con loop fix→tsc/pytest→commit.

**Tech Stack:** Python 3.11 FastAPI (backend), Next.js 14 TypeScript (frontend), pytest, ruff, mypy, Gemini CLI (red team)

---

## ROUND 1 — SECURITY

### Task 1: Fix RBAC su `/extract-passport-enhanced`

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/crm_clients.py`
- Test: `apps/backend-rag/backend/tests/unit/app/routers/test_crm_clients.py`

- [ ] **Step 1: Attiva venv**

```bash
cd apps/backend-rag && source .venv/bin/activate
```

- [ ] **Step 2: Scrivi il test failing**

Apri `backend/tests/unit/app/routers/test_crm_clients.py` e aggiungi in fondo:

```python
@pytest.mark.asyncio
async def test_extract_passport_enhanced_rbac_blocks_wrong_client(client, auth_headers):
    """Un admin non può estrarre dati su un client che non gli appartiene."""
    # Usa client_id=999999 che non esiste o non appartiene all'utente test
    payload = {
        "client_id": 999999,
        "image_base64": "aW52YWxpZA==",  # base64 di "invalid"
        "field_mapping": {}
    }
    response = await client.post(
        "/api/crm/clients/extract-passport-enhanced",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code in (403, 404)
```

- [ ] **Step 3: Esegui per verificare che fallisce**

```bash
PYTHONPATH=. pytest backend/tests/unit/app/routers/test_crm_clients.py::test_extract_passport_enhanced_rbac_blocks_wrong_client -v
```

Atteso: FAIL (200 o 500 invece di 403/404)

- [ ] **Step 4: Leggi l'endpoint attuale**

In `crm_clients.py` trova la funzione `extract_passport_enhanced`. Dovrebbe essere circa così (cerca `@router.post.*extract-passport-enhanced`):

```python
@router.post("/extract-passport-enhanced")
async def extract_passport_enhanced(
    request: PassportExtractEnhancedRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    # ... logica Gemini Vision ...
```

- [ ] **Step 5: Aggiungi validazione base64 + RBAC**

Sostituisci l'inizio della funzione `extract_passport_enhanced` con:

```python
@router.post("/extract-passport-enhanced")
async def extract_passport_enhanced(
    request: PassportExtractEnhancedRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    # Validazione base64
    import base64 as _b64
    try:
        _b64.b64decode(request.image_base64, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="image_base64 non è base64 valido")

    # RBAC: verifica accesso al client
    await verify_client_access(request.client_id, current_user, db)

    # ... resto della funzione invariato ...
```

- [ ] **Step 6: Esegui il test**

```bash
PYTHONPATH=. pytest backend/tests/unit/app/routers/test_crm_clients.py::test_extract_passport_enhanced_rbac_blocks_wrong_client -v
```

Atteso: PASS

- [ ] **Step 7: Esegui tutti i test CRM**

```bash
PYTHONPATH=. pytest backend/tests/ -k "crm or client" -q --tb=short
```

Atteso: 292+ passed, 0 failed

- [ ] **Step 8: Commit**

```bash
git add apps/backend-rag/backend/app/routers/crm_clients.py apps/backend-rag/backend/tests/unit/app/routers/test_crm_clients.py
git commit -m "fix(security): add RBAC + base64 validation to extract-passport-enhanced"
```

---

### Task 2: Fix RBAC + storage su `/extract-npwp`

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/crm_clients.py`
- Test: `apps/backend-rag/backend/tests/unit/app/routers/test_crm_clients.py`

- [ ] **Step 1: Scrivi il test failing**

```python
@pytest.mark.asyncio
async def test_extract_npwp_rbac_blocks_wrong_client(client, auth_headers):
    """client_id non accessibile → 403/404."""
    payload = {
        "client_id": 999999,
        "image_base64": "aW52YWxpZA==",
    }
    response = await client.post(
        "/api/crm/clients/extract-npwp",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code in (403, 404)


@pytest.mark.asyncio
async def test_extract_npwp_invalid_base64(client, auth_headers_admin):
    """base64 non valido → 400."""
    payload = {
        "client_id": 1,
        "image_base64": "NON_VALIDO!!!",
    }
    response = await client.post(
        "/api/crm/clients/extract-npwp",
        json=payload,
        headers=auth_headers_admin,
    )
    assert response.status_code == 400
```

- [ ] **Step 2: Esegui per verificare che falliscono**

```bash
PYTHONPATH=. pytest backend/tests/unit/app/routers/test_crm_clients.py::test_extract_npwp_rbac_blocks_wrong_client backend/tests/unit/app/routers/test_crm_clients.py::test_extract_npwp_invalid_base64 -v
```

Atteso: entrambi FAIL

- [ ] **Step 3: Trova la funzione `extract_npwp` in `crm_clients.py`**

Cerca `@router.post.*extract-npwp`. Aggiungi all'inizio della funzione:

```python
@router.post("/extract-npwp")
async def extract_npwp(
    request: NPWPExtractRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    # Validazione base64
    import base64 as _b64
    try:
        _b64.b64decode(request.image_base64, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="image_base64 non è base64 valido")

    # RBAC
    await verify_client_access(request.client_id, current_user, db)

    # ... resto invariato fino alla parte dove npwp è estratto con successo ...
```

- [ ] **Step 4: Dopo l'estrazione riuscita, salva l'NPWP sul cliente**

Trova il punto dove `npwp` è estratto con successo da Gemini e aggiungi prima del return:

```python
    # Salva NPWP estratto sul client
    if npwp and request.client_id:
        try:
            await db.execute(
                "UPDATE clients SET npwp = $1, updated_at = NOW() WHERE id = $2",
                npwp,
                request.client_id,
            )
        except Exception as e:
            logger.warning(f"Failed to save NPWP to client {request.client_id}: {e}")
            # Non bloccare la risposta se il salvataggio fallisce
```

- [ ] **Step 5: Esegui i test**

```bash
PYTHONPATH=. pytest backend/tests/unit/app/routers/test_crm_clients.py::test_extract_npwp_rbac_blocks_wrong_client backend/tests/unit/app/routers/test_crm_clients.py::test_extract_npwp_invalid_base64 -v
```

Atteso: entrambi PASS

- [ ] **Step 6: Esegui tutti i test CRM**

```bash
PYTHONPATH=. pytest backend/tests/ -k "crm or client" -q --tb=short
```

Atteso: 294+ passed, 0 failed

- [ ] **Step 7: Commit**

```bash
git add apps/backend-rag/backend/app/routers/crm_clients.py apps/backend-rag/backend/tests/unit/app/routers/test_crm_clients.py
git commit -m "fix(security): add RBAC + base64 validation + storage to extract-npwp"
```

---

### Task 3: Fix RBAC + storage su `/extract-nib`

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/crm_clients.py`
- Test: `apps/backend-rag/backend/tests/unit/app/routers/test_crm_clients.py`

- [ ] **Step 1: Scrivi i test failing**

```python
@pytest.mark.asyncio
async def test_extract_nib_rbac_blocks_wrong_client(client, auth_headers):
    """client_id non accessibile → 403/404."""
    payload = {
        "client_id": 999999,
        "image_base64": "aW52YWxpZA==",
    }
    response = await client.post(
        "/api/crm/clients/extract-nib",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code in (403, 404)


@pytest.mark.asyncio
async def test_extract_nib_invalid_base64(client, auth_headers_admin):
    """base64 non valido → 400."""
    payload = {
        "client_id": 1,
        "image_base64": "NON_VALIDO!!!",
    }
    response = await client.post(
        "/api/crm/clients/extract-nib",
        json=payload,
        headers=auth_headers_admin,
    )
    assert response.status_code == 400
```

- [ ] **Step 2: Esegui per verificare che falliscono**

```bash
PYTHONPATH=. pytest backend/tests/unit/app/routers/test_crm_clients.py::test_extract_nib_rbac_blocks_wrong_client backend/tests/unit/app/routers/test_crm_clients.py::test_extract_nib_invalid_base64 -v
```

Atteso: entrambi FAIL

- [ ] **Step 3: Fix `extract_nib` in `crm_clients.py`**

Stesso pattern di Task 2. Aggiungi all'inizio della funzione:

```python
@router.post("/extract-nib")
async def extract_nib(
    request: NIBExtractRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    # Validazione base64
    import base64 as _b64
    try:
        _b64.b64decode(request.image_base64, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="image_base64 non è base64 valido")

    # RBAC
    await verify_client_access(request.client_id, current_user, db)

    # ... resto invariato ...
```

- [ ] **Step 4: Dopo l'estrazione riuscita, salva NIB sul client**

```python
    # Salva NIB estratto sul client
    if nib and request.client_id:
        try:
            await db.execute(
                "UPDATE clients SET nib = $1, updated_at = NOW() WHERE id = $2",
                nib,
                request.client_id,
            )
        except Exception as e:
            logger.warning(f"Failed to save NIB to client {request.client_id}: {e}")
```

- [ ] **Step 5: Esegui i test**

```bash
PYTHONPATH=. pytest backend/tests/unit/app/routers/test_crm_clients.py::test_extract_nib_rbac_blocks_wrong_client backend/tests/unit/app/routers/test_crm_clients.py::test_extract_nib_invalid_base64 -v
```

Atteso: entrambi PASS

- [ ] **Step 6: Esegui tutti i test CRM**

```bash
PYTHONPATH=. pytest backend/tests/ -k "crm or client" -q --tb=short
```

Atteso: 296+ passed, 0 failed

- [ ] **Step 7: Commit**

```bash
git add apps/backend-rag/backend/app/routers/crm_clients.py apps/backend-rag/backend/tests/unit/app/routers/test_crm_clients.py
git commit -m "fix(security): add RBAC + base64 validation + storage to extract-nib"
```

---

### Task 4: Red Team Gemini su `crm_clients.py`

**Files:** nessun file modificato — solo verifica

- [ ] **Step 1: Lancia red team**

```bash
cd /Users/nuzantara/Desktop/nuzantara
./scripts/ai-dispatch.sh redteam "Analizza apps/backend-rag/backend/app/routers/crm_clients.py per vulnerabilità di sicurezza: RBAC mancante, SQL injection, missing input validation, auth bypass. Abbiamo appena fixato extract-passport-enhanced, extract-npwp, extract-nib. Controlla se ci sono altri endpoint con problemi simili."
```

- [ ] **Step 2: Leggi l'output in `./ai-dispatch-output/`**

```bash
ls -lt ./ai-dispatch-output/ | head -5
cat ./ai-dispatch-output/<ultimo-file>.json | python3 -m json.tool | grep -A5 "finding\|issue\|vuln"
```

- [ ] **Step 3: Se Gemini trova altri problemi critici → fixali ora**

Per ogni problema trovato: applica lo stesso pattern (RBAC + validazione input + test), poi ripeti pytest.

- [ ] **Step 4: Se tutto è ok → deploy backend**

```bash
cd apps/backend-rag && fly deploy --strategy rolling
```

Atteso: `v1xx deployed successfully`

- [ ] **Step 5: Verifica live**

```bash
curl -s -o /dev/null -w "%{http_code}" https://nuzantara-rag.fly.dev/health
```

Atteso: `200`

---

## ROUND 2 — UX/BUG (frontend + backend, sequenziale)

### Task 5: Fix avatar upload su `new/page.tsx`

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/clients/new/page.tsx`

- [ ] **Step 1: Leggi il file**

```bash
cat apps/mouth/src/app/\(workspace\)/clients/new/page.tsx | grep -n "avatar\|Avatar\|setFormData.*avatar\|Disabled\|disabled\|comment" | head -20
```

- [ ] **Step 2: Trova le righe commentate (circa 256, 272)**

Cerca il pattern:

```typescript
// setFormData((prev) => ({ ...prev, avatar_url: resizedImage })); // Disabled - type mismatch
// setFormData((prev) => ({ ...prev, avatar_url: '' })); // Disabled - type mismatch
```

- [ ] **Step 3: Analizza il type mismatch**

Controlla il tipo di `avatar_url` nel form state e nel tipo `ClientCreate`. Se `avatar_url` è `string | null` e `resizedImage` è `string`, il fix è semplicemente:

```typescript
setFormData((prev) => ({ ...prev, avatar_url: resizedImage ?? null }));
```

E per il clear:

```typescript
setFormData((prev) => ({ ...prev, avatar_url: null }));
```

- [ ] **Step 4: Sblocca le righe e rimuovi il codice commentato UI (linee ~354-375)**

Rimuovi le ~22 linee di UI commentata che non servono più.

- [ ] **Step 5: TypeScript check**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep -E "clients/new|avatar" | head -20
```

Atteso: nessun errore su quel file

- [ ] **Step 6: Commit**

```bash
git add apps/mouth/src/app/\(workspace\)/clients/new/page.tsx
git commit -m "fix(crm): re-enable avatar upload on new client form"
```

---

### Task 6: Fix `AddCompanyModal.tsx` — await + silent uploads

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/clients/[id]/components/modals/AddCompanyModal.tsx`

- [ ] **Step 1: Leggi il file, trova le funzioni `extractNpwp` e `extractNib`**

```bash
grep -n "extractNpwp\|extractNib\|handleExtract\|await\|Promise.all\|uploadPromises\|toast.success" apps/mouth/src/app/\(workspace\)/clients/\[id\]/components/modals/AddCompanyModal.tsx | head -30
```

- [ ] **Step 2: Await `extractNpwp` e `extractNib`**

Trova i click handler che chiamano queste funzioni. Cambia da:

```typescript
onClick={() => extractNpwp()}
// e
onClick={() => extractNib()}
```

A:

```typescript
onClick={async () => { await extractNpwp(); }}
// e
onClick={async () => { await extractNib(); }}
```

Oppure se sono già in un handler async, assicurati che vengano awaited:

```typescript
const result = await extractNpwp();
```

- [ ] **Step 3: Fix silent upload failure**

Trova il blocco `Promise.all(uploadPromises)` (circa linea 263-282). Sostituisci con:

```typescript
const uploadResults = await Promise.allSettled(uploadPromises);
const failedUploads = uploadResults.filter((r) => r.status === "rejected");
if (failedUploads.length > 0) {
  toast.error(`${failedUploads.length} documento/i non caricati. Riprova.`);
} else {
  toast.success("Azienda creata con successo");
}
```

- [ ] **Step 4: TypeScript check**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep -E "AddCompanyModal" | head -10
```

Atteso: nessun errore

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/app/\(workspace\)/clients/\[id\]/components/modals/AddCompanyModal.tsx
git commit -m "fix(crm): await extract handlers + report upload failures in AddCompanyModal"
```

---

### Task 7: Fix OCR silenzioso su `VisaCard.tsx`

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/clients/[id]/components/VisaCard.tsx`

- [ ] **Step 1: Trova il catch vuoto (circa linea 134)**

```bash
grep -n "catch\|silent\|Silent" apps/mouth/src/app/\(workspace\)/clients/\[id\]/components/VisaCard.tsx | head -20
```

- [ ] **Step 2: Sostituisci `catch {}` con notifica utente**

Trova:

```typescript
    } catch {
      /* Silent fail for auto-extract */
    }
```

Sostituisci con:

```typescript
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Errore OCR";
      logger.error("Visa OCR auto-extract failed", {}, e as Error);
      // Non mostrare toast per auto-extract silenzioso, ma logga
      // Se l'utente triggera manualmente, mostra errore
      if (!isAutoExtract) {
        toast.error(`OCR fallito: ${msg}`);
      }
    }
```

Se la funzione non ha un parametro `isAutoExtract`, aggiungi il parametro alla chiamata e al click handler manuale:

```typescript
// chiamata auto (useEffect):
await handleExtractVisa(true); // isAutoExtract = true

// chiamata manuale (button click):
await handleExtractVisa(false); // isAutoExtract = false
```

E la firma della funzione:

```typescript
const handleExtractVisa = useCallback(async (isAutoExtract = false) => {
```

- [ ] **Step 3: TypeScript check**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep -E "VisaCard" | head -10
```

Atteso: nessun errore

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/app/\(workspace\)/clients/\[id\]/components/VisaCard.tsx
git commit -m "fix(crm): show OCR errors on manual extract in VisaCard"
```

---

### Task 8: Fix OCR silenzioso + retry su `PassportCard.tsx`

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/clients/[id]/components/PassportCard.tsx`

- [ ] **Step 1: Trova la logica OCR auto-extract (circa linee 155-160)**

```bash
grep -n "hasTriggeredOcr\|handleExtractData\|auto\|useEffect\|catch" apps/mouth/src/app/\(workspace\)/clients/\[id\]/components/PassportCard.tsx | head -20
```

- [ ] **Step 2: Aggiungi stato errore OCR visibile**

Prima dello state esistente, aggiungi:

```typescript
const [ocrError, setOcrError] = useState<string | null>(null);
```

- [ ] **Step 3: Modifica `handleExtractData` per usare `isAutoExtract`**

Stessa logica di Task 7 — aggiungi parametro `isAutoExtract = false`:

```typescript
const handleExtractData = useCallback(
  async (isAutoExtract = false) => {
    setOcrError(null);
    try {
      // ... logica esistente ...
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Errore OCR";
      logger.error("Passport OCR failed", {}, e as Error);
      if (!isAutoExtract) {
        setOcrError(msg);
        toast.error(`OCR fallito: ${msg}`);
      }
      // Per auto-extract: imposta flag per permettere retry manuale
      hasTriggeredOcr.current = false; // Reset per permettere retry
    }
  },
  [
    /* deps esistenti */
  ],
);
```

- [ ] **Step 4: Mostra errore OCR nel JSX se presente**

Trova il bottone OCR nel JSX e aggiungi sotto:

```tsx
{
  ocrError && (
    <p className="text-xs text-red-400 mt-1">
      OCR fallito. Clicca per riprovare.
    </p>
  );
}
```

- [ ] **Step 5: TypeScript check**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep -E "PassportCard" | head -10
```

Atteso: nessun errore

- [ ] **Step 6: Commit**

```bash
git add apps/mouth/src/app/\(workspace\)/clients/\[id\]/components/PassportCard.tsx
git commit -m "fix(crm): show OCR error + enable retry on failure in PassportCard"
```

---

### Task 9: Fix null crash su `EditClientModal.tsx`

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/clients/[id]/components/modals/EditClientModal.tsx`

- [ ] **Step 1: Trova la riga problematica (circa 81-92)**

```bash
grep -n "date_of_birth\|new Date\|getTime\|DateObj" apps/mouth/src/app/\(workspace\)/clients/\[id\]/components/modals/EditClientModal.tsx | head -10
```

- [ ] **Step 2: Aggiungi null check**

Trova il codice simile a:

```typescript
const dateObj = new Date(client.date_of_birth);
```

Sostituisci con:

```typescript
const dateObj = client.date_of_birth ? new Date(client.date_of_birth) : null;
```

E ovunque `dateObj` venga usato dopo, aggiungi optional chaining:

```typescript
// prima:
const formatted = dateObj.toISOString().split("T")[0];
// dopo:
const formatted = dateObj?.toISOString().split("T")[0] ?? "";
```

- [ ] **Step 3: TypeScript check**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep -E "EditClientModal" | head -10
```

Atteso: nessun errore

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/app/\(workspace\)/clients/\[id\]/components/modals/EditClientModal.tsx
git commit -m "fix(crm): null check on date_of_birth in EditClientModal"
```

---

### Task 10: Fix catch vuoti su `CompanyTab.tsx`

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyTab.tsx`

- [ ] **Step 1: Trova tutti i `.catch(() => {})` e `as any`**

```bash
grep -n "catch.*{}\|as any" apps/mouth/src/app/\(workspace\)/clients/\[id\]/components/CompanyTab.tsx | head -20
```

- [ ] **Step 2: Sostituisci i catch vuoti (linee ~728, ~771)**

Pattern da sostituire:

```typescript
.catch(() => {})
```

Pattern sostitutivo:

```typescript
.catch((e: unknown) => {
  logger.error("Failed to load company data", {}, e as Error);
  toast.error("Errore nel caricamento dati azienda");
})
```

- [ ] **Step 3: Sostituisci i `as any` (linee ~723, ~745)**

Trova:

```typescript
const data: any = response.data;
const companies: any = response.data;
```

Sostituisci con tipi appropriati (controlla cosa contiene `response.data` leggendo le righe vicine):

```typescript
const data = response.data as CompanyResponse; // o il tipo corretto
const companies = response.data as Company[];
```

Se i tipi `CompanyResponse` e `Company` non esistono nel file, importali da dove sono definiti o definiscili inline come:

```typescript
const data = response.data as {
  company_id: number;
  name: string;
  [key: string]: unknown;
};
```

- [ ] **Step 4: TypeScript check**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep -E "CompanyTab" | head -15
```

Atteso: nessun errore

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/app/\(workspace\)/clients/\[id\]/components/CompanyTab.tsx
git commit -m "fix(crm): replace silent catches + any casts in CompanyTab"
```

---

### Task 11: Fix catch vuoti su `FamilyTab.tsx`

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/clients/[id]/components/FamilyTab.tsx`

- [ ] **Step 1: Trova i catch vuoti e le chiamate a `onRefresh`**

```bash
grep -n "catch.*{}\|onRefresh\|onRefreshRef" apps/mouth/src/app/\(workspace\)/clients/\[id\]/components/FamilyTab.tsx | head -20
```

- [ ] **Step 2: Fix catch vuoto sul fetch family members (linea ~124)**

Trova:

```typescript
.catch(() => {})
```

Sostituisci con:

```typescript
.catch((e: unknown) => {
  logger.error("Failed to load family members", {}, e as Error);
  toast.error("Errore nel caricamento familiari");
})
```

- [ ] **Step 3: Verifica che `onRefresh` venga chiamato con guard**

Cerca tutte le chiamate `onRefresh()`. Ogni chiamata dovrebbe essere protetta:

```typescript
// prima:
onRefresh();
// dopo:
onRefresh?.();
```

Se `onRefresh` è una prop required, questo non è necessario — verifica la firma del componente.

- [ ] **Step 4: TypeScript check**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep -E "FamilyTab" | head -10
```

Atteso: nessun errore

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/app/\(workspace\)/clients/\[id\]/components/FamilyTab.tsx
git commit -m "fix(crm): replace silent catches + guard onRefresh in FamilyTab"
```

---

### Task 12: Fix catch vuoti + loading state upload su `TaxTab.tsx`

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/clients/[id]/components/TaxTab.tsx`

- [ ] **Step 1: Trova catch vuoti e missing loading state**

```bash
grep -n "catch.*{}\|isUploading\|setIsUploading\|disabled" apps/mouth/src/app/\(workspace\)/clients/\[id\]/components/TaxTab.tsx | head -20
```

- [ ] **Step 2: Fix catch vuoto (linea ~171)**

```typescript
// prima:
.catch(() => {})
// dopo:
.catch((e: unknown) => {
  logger.error("Failed to load tax documents", {}, e as Error);
  toast.error("Errore nel caricamento documenti fiscali");
})
```

- [ ] **Step 3: Disabilita bottone upload durante il caricamento**

Trova il bottone di upload nel JSX. Se non ha già `disabled={isUploading}`:

```tsx
<Button
  onClick={handleUpload}
  disabled={isUploading} // aggiungi questo
>
  {isUploading ? "Caricamento..." : "Carica documento"}
</Button>
```

- [ ] **Step 4: TypeScript check**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep -E "TaxTab" | head -10
```

Atteso: nessun errore

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/app/\(workspace\)/clients/\[id\]/components/TaxTab.tsx
git commit -m "fix(crm): replace silent catches + disable upload button during loading in TaxTab"
```

---

### Task 13: Fix rollback ottimistico su `ImmigrationTab.tsx`

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/clients/[id]/components/ImmigrationTab.tsx`

- [ ] **Step 1: Trova il delete con ottimismo (circa linea 59-72)**

```bash
grep -n "delete\|optimis\|catch\|setDocs\|filter" apps/mouth/src/app/\(workspace\)/clients/\[id\]/components/ImmigrationTab.tsx | head -20
```

- [ ] **Step 2: Aggiungi rollback su failure**

Trova il pattern:

```typescript
// ottimismo: rimuove dalla UI prima della chiamata API
setDocs((prev) => prev.filter((d) => d.id !== doc.id));
try {
  await api.crm.deleteDoc(doc.id);
} catch (e) {
  toast.error("Errore nella cancellazione");
  // manca il rollback!
}
```

Sostituisci con:

```typescript
const previousDocs = docs; // salva stato prima
setDocs((prev) => prev.filter((d) => d.id !== doc.id));
try {
  await api.crm.deleteDoc(doc.id);
} catch (e) {
  setDocs(previousDocs); // rollback
  toast.error("Errore nella cancellazione. Il documento è stato ripristinato.");
  logger.error("Delete doc failed", {}, e as Error);
}
```

- [ ] **Step 3: TypeScript check**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep -E "ImmigrationTab" | head -10
```

Atteso: nessun errore

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/app/\(workspace\)/clients/\[id\]/components/ImmigrationTab.tsx
git commit -m "fix(crm): rollback optimistic delete on failure in ImmigrationTab"
```

---

### Task 14: Fix N+1 stats query in `crm_clients.py`

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/crm_clients.py`
- Test: `apps/backend-rag/backend/tests/unit/app/routers/test_crm_clients.py`

- [ ] **Step 1: Trova l'endpoint stats (circa linea 950)**

```bash
grep -n "stats_overview\|COUNT.*practice\|practice_type\|GROUP BY" apps/backend-rag/backend/app/routers/crm_clients.py | head -20
```

- [ ] **Step 2: Sostituisci loop N+1 con GROUP BY**

Trova il pattern (loop su practice types):

```python
practice_stats = {}
for practice_type in ["visa", "company", "tax"]:
    count = await db.fetchval(
        "SELECT COUNT(*) FROM practices WHERE practice_type = $1",
        practice_type
    )
    practice_stats[practice_type] = count
```

Sostituisci con:

```python
rows = await db.fetch(
    "SELECT practice_type, COUNT(*) as cnt FROM practices GROUP BY practice_type"
)
practice_stats = {row["practice_type"]: row["cnt"] for row in rows}
```

- [ ] **Step 3: Scrivi test per verificare il comportamento**

```python
@pytest.mark.asyncio
async def test_stats_overview_returns_practice_breakdown(client, auth_headers_admin):
    """Stats overview deve ritornare practice_stats con breakdown per tipo."""
    response = await client.get(
        "/api/crm/clients/stats/overview",
        headers=auth_headers_admin,
    )
    assert response.status_code == 200
    data = response.json()
    assert "practice_stats" in data
    assert isinstance(data["practice_stats"], dict)
```

- [ ] **Step 4: Esegui test**

```bash
PYTHONPATH=. pytest backend/tests/unit/app/routers/test_crm_clients.py::test_stats_overview_returns_practice_breakdown -v
```

Atteso: PASS

- [ ] **Step 5: Esegui tutti i test CRM**

```bash
PYTHONPATH=. pytest backend/tests/ -k "crm or client" -q --tb=short
```

Atteso: tutti green

- [ ] **Step 6: Commit**

```bash
git add apps/backend-rag/backend/app/routers/crm_clients.py apps/backend-rag/backend/tests/unit/app/routers/test_crm_clients.py
git commit -m "fix(crm): replace N+1 practice stats with GROUP BY query"
```

---

### Task 15: Fix N+1 required-docs con JOIN

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/crm_clients.py`

- [ ] **Step 1: Trova l'endpoint required-documents (circa linea 1632)**

```bash
grep -n "required.document\|required_document\|JOIN\|for.*practice" apps/backend-rag/backend/app/routers/crm_clients.py | tail -30
```

- [ ] **Step 2: Sostituisci loop N+1 con JOIN**

Trova il pattern (loop su practices):

```python
practices = await db.fetch("SELECT * FROM practices WHERE client_id = $1", client_id)
results = []
for practice in practices:
    docs = await db.fetch(
        "SELECT * FROM required_documents WHERE practice_id = $1",
        practice["id"]
    )
    results.extend(docs)
```

Sostituisci con una singola query JOIN:

```python
results = await db.fetch(
    """
    SELECT rd.*
    FROM required_documents rd
    JOIN practices p ON rd.practice_id = p.id
    WHERE p.client_id = $1
    ORDER BY rd.document_type
    """,
    client_id,
)
```

- [ ] **Step 3: Verifica test esistenti**

```bash
PYTHONPATH=. pytest backend/tests/ -k "crm or client" -q --tb=short
```

Atteso: tutti green

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/app/routers/crm_clients.py
git commit -m "fix(crm): replace N+1 required-docs loop with JOIN query"
```

---

### Task 16: Fix `page.tsx` — getUserProfile + null check

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/clients/page.tsx`

- [ ] **Step 1: Trova le righe problematiche**

```bash
grep -n "getUserProfile\|assigneesData\|as string\[\]" apps/mouth/src/app/\(workspace\)/clients/page.tsx | head -15
```

- [ ] **Step 2: Fix `getUserProfile` non awaited (circa linea 264)**

Se il codice è:

```typescript
const loadProfile = () => {
  const profile = api.getUserProfile();  // non awaited se è async
```

Cambia in:

```typescript
const loadProfile = async () => {
  try {
    const profile = await api.getUserProfile();
    if (profile?.email) {
      /* ... */
    }
  } catch (e) {
    logger.error("Failed to load user profile", {}, e as Error);
  }
};
```

- [ ] **Step 3: Fix null check su `assigneesData` (circa linea 357)**

Trova:

```typescript
const uniqueAssignees: string[] = assigneesData
  ? assigneesData.map((a) => a.assigned_to).filter(Boolean) as string[]
  : Array.from(new Set(...))
```

Sostituisci con:

```typescript
const uniqueAssignees: string[] = Array.isArray(assigneesData)
  ? assigneesData
      .map((a) => a.assigned_to)
      .filter((x): x is string => typeof x === "string")
  : [];
```

- [ ] **Step 4: TypeScript check**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep -E "clients/page" | head -10
```

Atteso: nessun errore

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/app/\(workspace\)/clients/page.tsx
git commit -m "fix(crm): await getUserProfile + type-safe assigneesData filter"
```

---

### Task 17: Fix `useCrmClients.ts` — refetch await + error propagation

**Files:**

- Modify: `apps/mouth/src/hooks/useCrmClients.ts`

- [ ] **Step 1: Trova `reset()` e il `refetch` non awaited**

```bash
grep -n "reset\|refetch\|isError\|error" apps/mouth/src/hooks/useCrmClients.ts | head -20
```

- [ ] **Step 2: Await `refetch()` in `reset()`**

Trova:

```typescript
const reset = useCallback(() => {
  setOffset(0);
  setAllClients([]);
  setHasMore(true);
  refetch(); // non awaited
}, [refetch]);
```

Sostituisci con:

```typescript
const reset = useCallback(async () => {
  setOffset(0);
  setAllClients([]);
  setHasMore(true);
  await refetch();
}, [refetch]);
```

- [ ] **Step 3: TypeScript check**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep -E "useCrmClients" | head -10
```

Atteso: nessun errore. Se ci sono errori per il cambio di firma (da `() => void` a `() => Promise<void>`), aggiorna i chiamanti di `reset`.

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/hooks/useCrmClients.ts
git commit -m "fix(crm): await refetch in reset() in useCrmClients"
```

---

### Task 18: Fix `crm.api.ts` — timeout + validazione response

**Files:**

- Modify: `apps/mouth/src/lib/api/crm/crm.api.ts`

- [ ] **Step 1: Trova le chiamate senza timeout**

```bash
grep -n "timeout\|getClients\|getPractices\|getClientSummary\|getClientTimeline" apps/mouth/src/lib/api/crm/crm.api.ts | head -20
```

- [ ] **Step 2: Aggiungi timeout su read operations**

Verifica come il client HTTP è configurato nel file. Se usa un wrapper con opzione `timeout`, aggiungila alle chiamate `getClients`, `getClientSummary`, `getClientTimeline`:

```typescript
// Se il client ha opzione timeout:
return this.client.request<Client[]>("/api/crm/clients/", {
  params: queryParams,
  timeout: 30000, // 30s per list operations
});
```

Se il client non supporta timeout per-request, aggiungi un wrapper con `AbortController`:

```typescript
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 30000);
try {
  return await this.client.request<Client[]>("/api/crm/clients/", {
    params: queryParams,
    signal: controller.signal,
  });
} finally {
  clearTimeout(timeoutId);
}
```

- [ ] **Step 3: Fix validazione `getClientTimeline` (circa linea 384)**

Trova:

```typescript
return response.timeline || [];
```

Sostituisci con:

```typescript
if (!response || !Array.isArray(response.timeline)) {
  logger.warn("getClientTimeline: unexpected response shape", {});
  return [];
}
return response.timeline;
```

- [ ] **Step 4: TypeScript check**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep -E "crm.api" | head -10
```

Atteso: nessun errore

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/lib/api/crm/crm.api.ts
git commit -m "fix(crm): add timeouts + validate getClientTimeline response shape"
```

---

### Task 19: Deploy finale + verifica

**Files:** nessuno modificato

- [ ] **Step 1: Deploy backend (se Task 14-15 non ancora deployati)**

```bash
cd apps/backend-rag && fly deploy --strategy rolling
```

Atteso: `v1xx deployed successfully`

- [ ] **Step 2: Push frontend**

```bash
cd /Users/nuzantara/Desktop/nuzantara && git push origin main
```

Atteso: Vercel build triggered automaticamente

- [ ] **Step 3: Verifica backend live**

```bash
# Attendi ~35s cold start se necessario
curl -s -o /dev/null -w "%{http_code}" https://nuzantara-rag.fly.dev/health
# Atteso: 200

curl -s -o /dev/null -w "%{http_code}" https://nuzantara-rag.fly.dev/api/crm/clients/?limit=1 \
  -H "Authorization: Bearer test" 2>/dev/null
# Atteso: 401 (non 503) — conferma che il router è attivo
```

- [ ] **Step 4: Verifica frontend live**

```bash
curl -s -o /dev/null -w "%{http_code}" https://kita.balizero.com/clients
```

Atteso: `200` o `307` (redirect auth)

- [ ] **Step 5: Run test suite finale completo**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/ -k "crm or client" -q --tb=short
```

Atteso: tutti green, nessun failed

- [ ] **Step 6: TypeScript check frontend finale**

```bash
cd apps/mouth && npx tsc --noEmit 2>&1 | grep -c "error" || echo "0 errors"
```

Atteso: `0 errors`

- [ ] **Step 7: Commit finale di riepilogo**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git commit --allow-empty -m "chore(crm): global fix complete — security + 14 UX/bug fixes"
```
