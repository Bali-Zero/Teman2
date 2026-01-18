# ANALISI DUPLICAZIONE STREAMING SSE

**Data:** 2026-01-13  
**File Analizzati:**

- `apps/mouth/src/lib/api/chat/chat.api.ts` (client-side)
- `apps/mouth/src/app/chat/actions.ts` (server-side)
- `apps/mouth/src/app/chat/page.tsx` (consumer)

---

## 📊 EXECUTIVE SUMMARY

**Status:** ✅ **DUPLICAZIONE CONFERMATA**

- **Source of Truth:** `chat.api.ts` (client-side) - **ATTIVO**
- **Legacy/Unused:** `actions.ts` (server-side) - **NON UTILIZZATO**
- **Righe Duplicate:** ~150+ righe di logica SSE parsing
- **Funzione Duplicata:** `cleanImageResponse()` - 2 implementazioni con differenze

---

## 🔍 ANALISI DETTAGLIATA

### 1. IMPLEMENTAZIONI IDENTIFICATE

#### A. Client-Side Streaming (`chat.api.ts`)

**Funzione:** `ChatApi.sendMessageStreaming()`  
**Righe:** 94-628 (534 righe totali)  
**Endpoint:** `/api/agentic-rag/stream`  
**Pattern:** Fetch API + ReadableStream + callbacks

**Caratteristiche:**

- ✅ Gestione completa abort signals
- ✅ Idle timeout (60s) + max total time (10min)
- ✅ Supporto immagini (vision)
- ✅ Correlation IDs per tracing
- ✅ CSRF token handling
- ✅ Gestione errori avanzata (timeout vs abort vs error)
- ✅ Supporto eventi: `token`, `sources`, `metadata`, `image`, `error`, `reasoning_step`, `phase`, `keepalive`, `thinking`, `tool_call`, `observation`, `status`, `tool_start`, `tool_end`
- ✅ `cleanImageResponse()` con 20+ filtri

#### B. Server-Side Streaming (`actions.ts`)

**Funzione:** `sendMessageStream()`  
**Righe:** 108-245 (137 righe totali)  
**Endpoint:** `/api/agentic-rag/stream` (stesso endpoint)  
**Pattern:** Server Action + ReadableStream<StreamEvent>

**Caratteristiche:**

- ⚠️ Gestione abort limitata
- ⚠️ Nessun timeout configurato
- ⚠️ Supporto immagini base
- ❌ Nessun correlation ID
- ❌ Nessun CSRF token (usa solo Bearer)
- ⚠️ Gestione errori semplice
- ⚠️ Supporto eventi limitato: `token`, `status`, `phase`, `sources`, `error`, `done`
- ⚠️ `cleanImageResponse()` con 8 filtri (meno completo)

---

### 2. UTILIZZO NELL'APPLICAZIONE

#### File che usano **CLIENT-SIDE** (`sendMessageStreaming`):

| File                                           | Linea    | Utilizzo                           |
| ---------------------------------------------- | -------- | ---------------------------------- |
| `apps/mouth/src/app/chat/page.tsx`             | 593      | ✅ **ATTIVO** - Usato direttamente |
| `apps/mouth/src/hooks/useChatStreaming.ts`     | 78       | ✅ **ATTIVO** - Hook wrapper       |
| `apps/mouth/src/lib/api/api-client.ts`         | 208      | ✅ **ATTIVO** - Wrapper API        |
| `apps/mouth/src/lib/api.test.ts`               | 309+     | ✅ Test                            |
| `apps/mouth/src/lib/api/chat/chat.api.test.ts` | 130+     | ✅ Test                            |
| `apps/mouth/src/lib/api/integration/*.test.ts` | Multiple | ✅ Test                            |

**Totale utilizzi client-side:** 40+ occorrenze

#### File che usano **SERVER-SIDE** (`sendMessageStream`):

| File                                        | Linea | Utilizzo                                             |
| ------------------------------------------- | ----- | ---------------------------------------------------- |
| `apps/mouth/src/hooks/useOptimisticChat.ts` | 136   | ⚠️ **NON UTILIZZATO** - Hook non usato in `page.tsx` |
| `apps/mouth/src/app/chat/actions.ts`        | 108   | 📝 Definizione                                       |

**Totale utilizzi server-side:** 1 hook non utilizzato

---

### 3. DIFFERENZE FUNZIONALI

#### A. Parsing SSE

**Client-Side (`chat.api.ts`):**

```typescript
// Buffer management completo
let sseBuffer = '';
const lines = sseBuffer.split('\n');
sseBuffer = lines.pop() ?? '';

// Parsing robusto con try-catch per ogni JSON
try {
  data = JSON.parse(jsonStr);
} catch {
  console.warn('Failed to parse SSE message:', line);
  continue;
}
```

**Server-Side (`actions.ts`):**

```typescript
// Buffer management semplice
buffer += decoder.decode(value, { stream: true });
const lines = buffer.split('\n');
buffer = lines.pop() || '';

// Parsing con try-catch globale
try {
  const event = JSON.parse(data);
  // ...
} catch {
  // Skip malformed JSON
}
```

**Differenza:** Client-side ha logging degli errori, server-side silenzioso.

#### B. Gestione Errori

**Client-Side:**

- Distingue tra timeout, abort, e error generici
- Error codes: `TIMEOUT`, `ABORTED`
- Gestione unmount (non chiama onError se componente smontato)
- Cleanup completo di timeouts e abort listeners

**Server-Side:**

- Gestione errori semplice
- Nessun error code
- Nessuna distinzione timeout vs abort

#### C. Timeout Management

**Client-Side:**

- `timeoutMs`: 120s (default)
- `idleTimeoutMs`: 60s (reset su data arrival)
- `maxTotalTimeMs`: 600s (10min)
- Reset automatico idle timeout su ogni evento

**Server-Side:**

- ❌ Nessun timeout configurato
- ⚠️ Dipende da timeout di fetch nativo

#### D. Eventi Supportati

**Client-Side (13 tipi):**

1. `token` - Aggiornamento testo
2. `sources` - Fonti RAG
3. `metadata` - Metadati esecuzione
4. `image` - Immagini generate
5. `error` - Errori
6. `reasoning_step` - Step reasoning
7. `phase` - Fasi processing
8. `keepalive` - Heartbeat
9. `thinking` - Thinking events
10. `tool_call` - Tool invocati
11. `observation` - Risultati tool
12. `status` - Status updates
13. `tool_start` / `tool_end` - Tool lifecycle

**Server-Side (6 tipi):**

1. `token` - Aggiornamento testo
2. `status` / `phase` - Status (unificati)
3. `sources` - Fonti RAG
4. `error` - Errori
5. `done` - Completamento

**Differenza:** Client-side supporta 13 eventi, server-side solo 6.

#### E. `cleanImageResponse()` - DIFFERENZE CRITICHE

**Client-Side (`chat.api.ts`):**

```typescript
// 20+ filtri
- Skip pollinations URLs
- Skip markdown images ![...](...)
- Skip [Visualizza Immagine]
- Skip version lines (numbered, bullet)
- Skip intro lines ("ecco le opzioni", "ho elaborato")
- Skip outro lines ("spero che queste")
- Skip lines starting with (http
- Skip pure URLs
- Skip URL-encoded content (%20 sequences)
- Skip "alta risoluzione" descriptions
- Skip image.pollinations subdomains
- Skip broken markdown images
```

**Server-Side (`actions.ts`):**

```typescript
// 8 filtri (meno completo)
- Skip pollinations URLs
- Skip [Visualizza Immagine]
- Skip version lines (numbered only)
- Skip intro lines (meno pattern)
- Skip outro lines (meno pattern)
- Skip lines starting with (http
- Skip pure URLs
```

**Differenza:** Client-side ha 12+ filtri aggiuntivi per pulizia più accurata.

---

### 4. METRICHE DUPLICAZIONE

| Metrica                           | Valore                                          |
| --------------------------------- | ----------------------------------------------- |
| **Righe duplicate (SSE parsing)** | ~150 righe                                      |
| **Funzioni duplicate**            | `cleanImageResponse()` (2 versioni)             |
| **Logica SSE duplicata**          | Buffer management, line splitting, JSON parsing |
| **Event handling duplicato**      | Token, sources, error handling                  |
| **Differenze funzionali**         | 7+ differenze significative                     |

---

### 5. RACCOMANDAZIONI

#### ✅ OPZIONE 1: Rimuovere Server-Side (CONSIGLIATA)

**Azioni:**

1. ✅ Rimuovere `sendMessageStream()` da `actions.ts`
2. ✅ Rimuovere `useOptimisticChat.ts` hook (non utilizzato)
3. ✅ Mantenere solo `chat.api.ts` come source of truth
4. ✅ Aggiornare commenti in `cleanImageResponse()` per rimuovere riferimento duplicazione

**Vantaggi:**

- Elimina duplicazione
- Riduce maintenance burden
- Unica source of truth
- Client-side è più completo

**Svantaggi:**

- Nessuno (server-side non è utilizzato)

#### ⚠️ OPZIONE 2: Unificare Implementazioni

**Azioni:**

1. Estrarre `cleanImageResponse()` in utility condivisa
2. Estrarre logica SSE parsing in utility condivisa
3. Mantenere entrambe le API ma con logica condivisa

**Vantaggi:**

- Mantiene entrambe le API
- Elimina duplicazione logica

**Svantaggi:**

- Server-side non è utilizzato
- Overhead non necessario

---

### 6. RISCHI

| Rischio                                | Probabilità | Impatto | Mitigazione                      |
| -------------------------------------- | ----------- | ------- | -------------------------------- |
| Server-side viene utilizzato in futuro | Bassa       | Medio   | Verificare prima di rimuovere    |
| Differenze funzionali causano bug      | Media       | Alto    | Unificare `cleanImageResponse()` |
| Maintenance burden aumenta             | Alta        | Basso   | Rimuovere duplicazione           |

---

### 7. CONCLUSIONI

**Source of Truth Attuale:** `apps/mouth/src/lib/api/chat/chat.api.ts`

**Raccomandazione Finale:**

- ✅ **Rimuovere** `sendMessageStream()` da `actions.ts` (non utilizzato)
- ✅ **Rimuovere** `useOptimisticChat.ts` hook (non utilizzato)
- ✅ **Mantenere** solo client-side implementation
- ✅ **Estrarre** `cleanImageResponse()` in utility condivisa se necessario in futuro

**Priorità:** Media (non critico, ma duplicazione aumenta maintenance burden)

---

**Last Updated:** 2026-01-13
