# Master Architect Action Plan - Verification & Patches

**Created:** 2026-01-10  
**Purpose:** Structured prompts for verifying issues before fixing them

> **Principle:** Always verify a problem exists before refactoring. This prevents unnecessary work and ensures we fix real issues, not perceived ones.

---

## 🔍 VERIFICATION WORKFLOW

For each action:
1. **VERIFY** - Run verification prompt to confirm the problem exists
2. **MEASURE** - Quantify the impact (if applicable)
3. **PATCH** - Apply fix only if verification confirms the issue

---

## 1. SECURITY: Public Endpoints Audit

### 🔍 VERIFICATION PROMPT

```
@docs/ai/AI_HANDOVER_PROTOCOL.md @docs/operations/OBSERVABILITY_GUIDE.md

ANALISI SECURITY AUDIT:

Verifica se ci sono endpoint pubblici che NON dovrebbero essere pubblici:

1. Controlla `backend/middleware/hybrid_auth.py` - lista `public_endpoints`
2. Cerca endpoint marcati come "TEMPORARY", "DEBUG", "FIX" nel codice
3. Verifica se endpoint pubblici hanno:
   - Rate limiting appropriato
   - Logging/audit trail
   - Validazione input rigorosa
   - Protezione contro abuse (IP whitelist, secret token, signature verification)

4. Controlla se endpoint pubblici espongono:
   - Informazioni sensibili (user data, internal config)
   - Operazioni state-changing senza autenticazione
   - Debug information in produzione

RESTITUISCI:
- Lista endpoint pubblici con classificazione: CRITICAL (deve essere pubblico), RISKY (dovrebbe essere protetto), TEMPORARY (va rimosso)
- Per ogni endpoint RISKY/TEMPORARY: spiegazione perché è rischioso
- Quantificazione: quanti endpoint pubblici ci sono? Quanti sono TEMPORARY?
```

### ✅ PATCH PROMPT (solo se verificato)

```
@backend/middleware/hybrid_auth.py

PROBLEMA VERIFICATO: [Inserisci risultati verifica]

RIMUOVI endpoint temporanei/debug dalla lista public_endpoints:

1. Rimuovi tutti gli endpoint marcati come TEMPORARY/FIX/DEBUG
2. Se un endpoint è necessario ma non deve essere pubblico:
   - Spostalo in un router separato con autenticazione API key
   - Oppure proteggilo con secret token/whitelist IP
3. Aggiungi commento per ogni endpoint pubblico che spiega PERCHÉ deve essere pubblico

REQUISITI:
- Mantieni solo endpoint veramente pubblici (health, docs, webhook con verifica)
- Aggiungi logging strutturato per ogni accesso a endpoint pubblici
- Documenta in un commento la ragione business per ogni endpoint pubblico rimasto
```

---

## 2. CHAT: Duplicate Streaming Implementations

### 🔍 VERIFICATION PROMPT

```
@apps/mouth/src/lib/api/chat/chat.api.ts @apps/mouth/src/app/chat/actions.ts @apps/mouth/src/app/chat/page.tsx

ANALISI DUPLICAZIONE STREAMING:

Verifica se ci sono implementazioni duplicate di SSE streaming:

1. Confronta `chat.api.ts` (client-side) vs `actions.ts` (server-side):
   - Stessa logica di parsing SSE?
   - Stessa gestione errori?
   - Stessa pulizia response (cleanImageResponse)?
   - Stessi timeout/abort logic?

2. Verifica quale implementazione è usata:
   - Cerca tutti i `import` di `sendMessageStreaming` da `chat.api.ts`
   - Cerca tutti i `import` di `sendMessageStream` da `actions.ts`
   - Controlla `chat/page.tsx` - quale usa?

3. Verifica differenze funzionali:
   - Una gestisce meglio gli errori?
   - Una ha feature che l'altra non ha?
   - Una è più performante?

RESTITUISCI:
- Lista file che usano client-side streaming
- Lista file che usano server-side streaming
- Differenze funzionali tra le due implementazioni
- Quale è la "source of truth" attuale?
- Quante righe di codice duplicate?
```

### ✅ PATCH PROMPT (solo se verificato)

```
@apps/mouth/src/lib/api/chat/chat.api.ts @apps/mouth/src/app/chat/actions.ts

PROBLEMA VERIFICATO: [Inserisci risultati verifica]

DECISIONE: Usare SOLO client-side streaming (chat.api.ts) come source of truth.

AZIONI:
1. Rimuovi `sendMessageStream` da `actions.ts` (o marca come DEPRECATED con redirect)
2. Assicurati che `chat.api.ts` abbia tutte le feature necessarie:
   - Gestione errori robusta
   - Timeout configurabili
   - Abort signal support
   - Image cleaning
   - Correlation ID support
3. Aggiorna `chat/page.tsx` per usare SOLO `chat.api.ts`
4. Rimuovi import non utilizzati

REQUISITI:
- Mantieni backward compatibility se ci sono altri file che usano server action
- Aggiungi deprecation warning se server action è ancora referenziata
- Testa che tutto funzioni dopo la rimozione
```

---

## 3. CHAT: Monolithic page.tsx

### 🔍 VERIFICATION PROMPT

```
@apps/mouth/src/app/chat/page.tsx

ANALISI COMPLESSITÀ CHAT PAGE:

Verifica se `chat/page.tsx` è troppo complesso:

1. Conta:
   - Numero di useState hooks
   - Numero di useEffect hooks
   - Numero di funzioni definite nel componente
   - Numero di linee totali
   - Numero di responsabilità (SSE, TTS, upload, modals, sidebar, team status, etc.)

2. Verifica accoppiamento:
   - Quanti stati sono interdipendenti?
   - Quanti useEffect hanno dipendenze complesse?
   - Ci sono "god hooks" che gestiscono troppe cose?

3. Verifica manutenibilità:
   - Quanto è difficile aggiungere una nuova feature?
   - Quanto è difficile testare una singola feature?
   - Quanti bug sono stati introdotti modificando questo file?

RESTITUISCI:
- Metriche quantitative (righe, hooks, funzioni)
- Lista responsabilità del componente
- Stima difficoltà di testing (1-10)
- Stima difficoltà di aggiungere feature (1-10)
```

### ✅ PATCH PROMPT (solo se verificato)

```
@apps/mouth/src/app/chat/page.tsx

PROBLEMA VERIFICATO: [Inserisci risultati verifica - es: 1938 righe, 20+ useState, 15+ useEffect]

REFACTOR CHAT PAGE in componenti modulari:

1. Estrai custom hooks:
   - `useChatStreaming` - gestisce SSE connection, events, abort
   - `useChatMessages` - gestisce messages state, optimistic updates
   - `useChatInput` - gestisce input, attachments, image upload
   - `useChatTTS` - gestisce text-to-speech
   - `useChatSidebar` - gestisce sidebar state, conversations

2. Estrai componenti:
   - `ChatMessages` - rendering messaggi con virtualizzazione
   - `ChatInput` - input field con attachments
   - `ChatSidebar` - sidebar con conversations list
   - `ChatHeader` - header con user info, settings
   - `ImageGenModal` - modal per generazione immagini
   - `SearchDocsModal` - modal per ricerca documenti

3. Mantieni `page.tsx` come orchestratore leggero:
   - Solo layout e composizione componenti
   - Max 200-300 righe

REQUISITI:
- Ogni hook/componente deve essere testabile in isolamento
- Mantieni tutte le feature esistenti (non rimuovere funzionalità)
- Usa TypeScript strict mode
- Aggiungi JSDoc per ogni hook/componente pubblico
```

---

## 4. BACKEND: God Object - Orchestrator

### 🔍 VERIFICATION PROMPT

```
@apps/backend-rag/backend/services/rag/agentic/orchestrator.py

ANALISI COMPLESSITÀ ORCHESTRATOR:

Verifica se `orchestrator.py` è un "god object":

1. Analizza responsabilità:
   - Quante responsabilità ha? (routing, memory, KG, cache, prompt, streaming, etc.)
   - Quante dipendenze ha? (quanti servizi inizializza?)
   - Quante linee di codice?

2. Verifica accoppiamento:
   - Quanti altri file dipendono da questo file?
   - Quanto è difficile mockare questo componente nei test?
   - Quanto è difficile testare una singola responsabilità?

3. Verifica manutenibilità:
   - Quanto tempo serve per capire il flusso completo?
   - Quanto è difficile aggiungere una nuova feature?
   - Quanti bug sono stati introdotti modificando questo file?

RESTITUISCI:
- Numero righe
- Numero responsabilità distinte
- Numero dipendenze inizializzate
- Numero file che importano questo modulo
- Stima complessità ciclomatica (se possibile)
```

### ✅ PATCH PROMPT (solo se verificato)

```
@apps/backend-rag/backend/services/rag/agentic/orchestrator.py

PROBLEMA VERIFICATO: [Inserisci risultati verifica - es: 1560 righe, 8+ responsabilità]

REFACTOR ORCHESTRATOR in moduli focalizzati:

1. Crea `orchestrator_core.py`:
   - Solo coordinamento flusso principale
   - Delega a moduli specializzati
   - Max 300-400 righe

2. Estrai moduli:
   - `orchestrator_context.py` - gestione context loading (user, memory, history)
   - `orchestrator_routing.py` - intent classification, tier selection
   - `orchestrator_streaming.py` - SSE event generation, streaming logic
   - `orchestrator_response.py` - response formatting, post-processing
   - `orchestrator_metrics.py` - metrics collection, timing

3. Mantieni `orchestrator.py` come thin wrapper:
   - Inizializza moduli
   - Coordina flusso
   - Gestisce errori top-level

REQUISITI:
- Ogni modulo deve avere una singola responsabilità chiara
- Mantieni backward compatibility (stessa interfaccia pubblica)
- Ogni modulo deve essere testabile in isolamento
- Aggiungi type hints completi
- Documenta ogni modulo con docstring
```

---

## 5. CODE DUPLICATION: cleanImageResponse

### 🔍 VERIFICATION PROMPT

```
@apps/backend-rag/backend/app/routers/agentic_rag.py @apps/mouth/src/lib/api/chat/chat.api.ts @apps/mouth/src/app/chat/actions.ts

ANALISI DUPLICAZIONE cleanImageResponse:

Verifica se `cleanImageResponse` è duplicato:

1. Cerca tutte le occorrenze di `cleanImageResponse` o `cleanImage` nel codebase
2. Confronta le implementazioni:
   - Stessa logica?
   - Stessi pattern regex?
   - Stessi edge cases gestiti?
   - Stesso fallback message?

3. Verifica se le implementazioni sono sincronizzate:
   - Quando una viene modificata, le altre vengono aggiornate?
   - Ci sono bug fix applicati solo a una versione?

RESTITUISCI:
- Lista file con implementazione di cleanImageResponse
- Differenze tra implementazioni (se esistono)
- Stima rischio di drift (quanto è probabile che vadano out-of-sync?)
```

### ✅ PATCH PROMPT (solo se verificato)

```
@apps/backend-rag/backend/app/routers/agentic_rag.py @apps/mouth/src/lib/api/chat/chat.api.ts @apps/mouth/src/app/chat/actions.ts

PROBLEMA VERIFICATO: [Inserisci risultati verifica - es: 3 implementazioni, alcune differenze minori]

CENTRALIZZA cleanImageResponse:

OPZIONE A (Preferita): Backend come source of truth
1. Mantieni SOLO implementazione in `backend/app/routers/agentic_rag.py`
2. Rimuovi implementazioni frontend
3. Il backend pulisce sempre le risposte prima di inviarle
4. Frontend riceve già pulito

OPZIONE B: Shared utility (se frontend ha bisogno di pulire anche altre sorgenti)
1. Crea `apps/mouth/src/lib/utils/imageResponseCleaner.ts`
2. Usa questa utility sia in `chat.api.ts` che in `actions.ts`
3. Rimuovi duplicazioni

REQUISITI:
- Una sola implementazione (source of truth)
- Se backend pulisce, frontend non deve pulire di nuovo
- Test unitari per la funzione di pulizia
- Documenta i pattern che vengono rimossi
```

---

## 6. TYPE SAFETY: Frontend `any` Types

### 🔍 VERIFICATION PROMPT

```
@apps/mouth/src

ANALISI TYPE SAFETY:

Verifica uso di `any` nel frontend:

1. Cerca tutte le occorrenze di `any`:
   ```bash
   grep -r ":\s*any" apps/mouth/src --include="*.ts" --include="*.tsx" | wc -l
   grep -r "@ts-ignore" apps/mouth/src --include="*.ts" --include="*.tsx" | wc -l
   grep -r "eslint-disable" apps/mouth/src --include="*.ts" --include="*.tsx" | wc -l
   ```

2. Analizza pattern:
   - `any` usati per API responses?
   - `any` usati per event handlers?
   - `any` usati per component props?
   - `any` usati per state management?

3. Verifica impatto:
   - Quanti `any` sono in file critici (API clients, state management)?
   - Quanti sono in file non critici (utilities, helpers)?
   - Ci sono type errors nascosti da `any`?

RESTITUISCI:
- Numero totale occorrenze `any`
- Numero totale `@ts-ignore`
- Lista file con più `any` (top 10)
- Stima rischio: quanti `any` sono in codice critico?
```

### ✅ PATCH PROMPT (solo se verificato)

```
@apps/mouth/src/lib/api @apps/mouth/src/lib/realtime.tsx @apps/mouth/src/hooks

PROBLEMA VERIFICATO: [Inserisci risultati verifica - es: 972 occorrenze any, 100+ in API clients]

MIGRAZIONE GRADUALE TYPE SAFETY:

FASE 1: API Clients (priorità alta)
1. Crea tipi TypeScript per tutte le API responses:
   - `src/lib/api/types/chat.types.ts` - Chat API types
   - `src/lib/api/types/crm.types.ts` - CRM API types (già esiste?)
   - `src/lib/api/types/auth.types.ts` - Auth API types

2. Sostituisci `any` in API clients con tipi specifici
3. Usa `unknown` invece di `any` dove il tipo non è noto, con type guards

FASE 2: Realtime Service
1. Definisci tipi per WebSocket messages
2. Rimuovi `any` da `realtime.tsx`

FASE 3: Hooks
1. Tipizza tutti i custom hooks
2. Rimuovi `any` da return types

REQUISITI:
- Non rompere funzionalità esistente
- Usa `unknown` + type guards invece di `any` dove necessario
- Aggiungi `// @ts-expect-error` con commento esplicativo se `any` è temporaneo
- Abilita `noImplicitAny` in `tsconfig.json` gradualmente (file per file)
```

---

## 7. TEST DEBT: 300 Failing Tests

### 🔍 VERIFICATION PROMPT

```
@apps/backend-rag/300_failing_tests.txt @apps/backend-rag/tests

ANALISI TEST DEBT:

Verifica lo stato reale dei test:

1. Esegui test suite:
   ```bash
   cd apps/backend-rag
   PYTHONPATH=. pytest --co -q | wc -l  # Totale test
   PYTHONPATH=. pytest -x --tb=short 2>&1 | grep -E "FAILED|ERROR" | wc -l  # Test falliti
   ```

2. Analizza `300_failing_tests.txt`:
   - Quando è stato generato?
   - I test sono ancora rilevanti?
   - Sono test obsoleti o test che testano codice rimosso?

3. Categorizza test falliti:
   - Test che testano codice rimosso/deprecato
   - Test con bug (test stesso è sbagliato)
   - Test che rivelano bug reali nel codice
   - Test che necessitano aggiornamento per nuove API

RESTITUISCI:
- Numero totale test
- Numero test falliti (reale, non dal file)
- Categorizzazione test falliti
- Stima tempo per fixare (ore)
- Priorità: quali test sono critici?
```

### ✅ PATCH PROMPT (solo se verificato)

```
@apps/backend-rag/tests @apps/backend-rag/300_failing_tests.txt

PROBLEMA VERIFICATO: [Inserisci risultati verifica - es: 150 test falliti su 9278, 50% obsoleti]

PIANO DI RECUPERO TEST:

FASE 1: Pulizia (1-2 giorni)
1. Rimuovi test obsoleti (testano codice rimosso)
2. Aggiorna test con API cambiate
3. Fixa test con bug evidenti

FASE 2: Fix Critici (3-5 giorni)
1. Identifica test critici (testano funzionalità core)
2. Fixa test che rivelano bug reali
3. Aggiorna test per nuove signature API

FASE 3: Automazione (1 giorno)
1. Aggiungi test failure tracking in CI
2. Blocca merge se test critici falliscono
3. Genera report automatico test falliti

REQUISITI:
- Non rimuovere test senza verificare che codice sia davvero rimosso
- Aggiungi `@pytest.mark.skip(reason="...")` invece di rimuovere test temporaneamente
- Documenta ogni test fixato con issue/ticket number
- Obiettivo: < 5% test falliti
```

---

## 8. BACKEND: Intel Router Monolith

### 🔍 VERIFICATION PROMPT

```
@apps/backend-rag/backend/app/routers/intel.py

ANALISI COMPLESSITÀ INTEL ROUTER:

Verifica se `intel.py` è troppo grande:

1. Metriche:
   - Numero righe
   - Numero endpoint definiti
   - Numero funzioni helper
   - Numero responsabilità (routing, business logic, data transformation)

2. Verifica separazione concerns:
   - Logica business è nel router o in services?
   - Ci sono query SQL direttamente nel router?
   - Ci sono trasformazioni dati complesse nel router?

3. Verifica testabilità:
   - Quanto è difficile testare un singolo endpoint?
   - Quanto è difficile mockare le dipendenze?

RESTITUISCI:
- Numero righe
- Numero endpoint
- Numero responsabilità
- Stima complessità (1-10)
```

### ✅ PATCH PROMPT (solo se verificato)

```
@apps/backend-rag/backend/app/routers/intel.py

PROBLEMA VERIFICATO: [Inserisci risultati verifica - es: 1474 righe, 20+ endpoint, logica business mista]

REFACTOR INTEL ROUTER:

1. Estrai servizi:
   - `backend/services/intel/intel_classification_service.py` - classificazione articoli
   - `backend/services/intel/intel_approval_service.py` - gestione approval workflow
   - `backend/services/intel/intel_staging_service.py` - gestione staging items
   - `backend/services/intel/intel_analytics_service.py` - analytics e metrics

2. Mantieni router come thin layer:
   - Solo routing HTTP → service calls
   - Validazione input (Pydantic models)
   - Formattazione output
   - Max 300-400 righe

3. Aggiorna router per usare servizi:
   - Router chiama servizi, non contiene logica business
   - Servizi sono testabili in isolamento

REQUISITI:
- Mantieni stessa API pubblica (non breaking changes)
- Ogni servizio ha una responsabilità chiara
- Aggiungi type hints completi
- Documenta ogni servizio con docstring
```

---

## 📋 TEMPLATE PER NUOVE VERIFICAZIONI

Quando identifichi un nuovo potenziale problema, usa questo template:

```markdown
## N. [TITOLO PROBLEMA]

### 🔍 VERIFICATION PROMPT

```
[Comandi/query per verificare se il problema esiste]
[File da analizzare]
[Metrica da misurare]
[Output atteso]
```

### ✅ PATCH PROMPT (solo se verificato)

```
[Azioni concrete da fare]
[File da modificare]
[Requisiti da rispettare]
[Test da eseguire]
```
```

---

## 🎯 PRIORITÀ CONSIGLIATA

1. **Security Audit** (P0) - Verifica immediata, patch critica
2. **Chat Streaming Duplication** (P0) - Verifica rapida, patch semplice
3. **Test Debt** (P1) - Verifica completa, patch graduale
4. **Chat Monolith** (P1) - Verifica completa, patch strutturata
5. **Orchestrator Refactor** (P2) - Verifica approfondita, patch complessa
6. **Type Safety** (P2) - Verifica completa, patch graduale
7. **Intel Router** (P2) - Verifica completa, patch strutturata
8. **Code Duplication** (P3) - Verifica rapida, patch semplice

---

**Last Updated:** 2026-01-10  
**Next Review:** After each verification completes
