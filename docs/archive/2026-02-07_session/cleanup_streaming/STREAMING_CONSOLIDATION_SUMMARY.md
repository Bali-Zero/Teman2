# STREAMING CONSOLIDATION - SUMMARY

**Data:** 2026-01-13  
**Status:** ✅ **COMPLETATO**

---

## 🎯 OBIETTIVO

Consolidare tutto lo streaming SSE su client-side (`chat.api.ts`) come **SOURCE OF TRUTH**, deprecando l'implementazione server-side non utilizzata.

---

## ✅ MODIFICHE COMPLETATE

### 1. Deprecazione Server-Side (`actions.ts`)

**File:** `apps/mouth/src/app/chat/actions.ts`

- ✅ Aggiunto `@deprecated` JSDoc con migration guide
- ✅ Aggiunto deprecation warning in development mode
- ✅ Aggiunto logging per monitoraggio utilizzo deprecato
- ✅ Mantenuta backward compatibility (funzione ancora funzionante)

**Codice:**

```typescript
/**
 * @deprecated This server action is deprecated. Use client-side streaming via `api.sendMessageStreaming()` from `@/lib/api` instead.
 *
 * Migration guide:
 * - Replace `sendMessageStream()` with `api.sendMessageStreaming()`
 * - Use `useChatStreaming` hook or call `api.sendMessageStreaming()` directly
 * - See `apps/mouth/src/lib/api/chat/chat.api.ts` for the active implementation
 *
 * This function will be removed in a future version.
 */
export async function sendMessageStream(...)
```

### 2. Deprecazione Hook (`useOptimisticChat.ts`)

**File:** `apps/mouth/src/hooks/useOptimisticChat.ts`

- ✅ Aggiunto `@deprecated` JSDoc con migration guide
- ✅ Aggiunto deprecation warning in development mode
- ✅ Mantenuta backward compatibility

**Codice:**

```typescript
/**
 * @deprecated This hook is deprecated. Use client-side streaming via `api.sendMessageStreaming()` from `@/lib/api` instead.
 *
 * Migration guide:
 * - Replace `useOptimisticChat()` with direct calls to `api.sendMessageStreaming()`
 * - See `apps/mouth/src/app/chat/page.tsx` for an example of the active implementation
 * ...
 */
export function useOptimisticChat(...)
```

### 3. Miglioramenti Client-Side (`chat.api.ts`)

**File:** `apps/mouth/src/lib/api/chat/chat.api.ts`

#### A. Documentazione Completa

- ✅ Aggiunto JSDoc completo con tutte le feature
- ✅ Documentati tutti i parametri
- ✅ Aggiunto esempio di utilizzo
- ✅ Aggiornato commento `cleanImageResponse()` come SOURCE OF TRUTH

#### B. Logging e Metriche

- ✅ Aggiunto tracking metriche:
  - `totalDuration` - Durata totale stream
  - `timeToFirstChunk` - Tempo al primo chunk
  - `streamingDuration` - Durata streaming effettiva
  - `chunkCount` - Numero di chunk ricevuti
  - `totalBytesReceived` - Byte totali ricevuti
  - `eventTypes` - Conteggio eventi per tipo
  - `responseLength` - Lunghezza risposta finale
  - `sourcesCount` - Numero di fonti
  - `hasGeneratedImage` - Flag immagine generata

- ✅ Logging in development mode:
  - Success: `[ChatApi] Stream completed` con tutte le metriche
  - Error: `[ChatApi] Stream error` con dettagli errore e metriche

#### C. Feature Verificate

- ✅ Gestione errori robusta (error codes: TIMEOUT, ABORTED)
- ✅ Timeout configurabili (timeoutMs, idleTimeoutMs, maxTotalTimeMs)
- ✅ Abort signal support completo
- ✅ Image cleaning (20+ filtri)
- ✅ Correlation ID support
- ✅ CSRF token handling
- ✅ Supporto 13 event types
- ✅ Vision support (image attachments)
- ✅ Conversation history management
- ✅ Unmount detection

---

## 📊 STATO UTILIZZO

### Client-Side (`api.sendMessageStreaming`)

- ✅ **ATTIVO** - Usato in `page.tsx` (linea 593)
- ✅ **ATTIVO** - Usato in `useChatStreaming.ts` hook
- ✅ **ATTIVO** - Wrapper in `api-client.ts`
- ✅ **TESTATO** - 40+ test cases

### Server-Side (`sendMessageStream`)

- ⚠️ **DEPRECATO** - Usato solo in `useOptimisticChat.ts` (hook non utilizzato)
- ⚠️ **DEPRECATO** - Warning in development mode
- ✅ **BACKWARD COMPATIBLE** - Funziona ancora per compatibilità

---

## 🔍 VERIFICA COMPATIBILITÀ

### File che Importano `sendMessageStream`:

- `apps/mouth/src/hooks/useOptimisticChat.ts` - ⚠️ Deprecato, non utilizzato

### File che Importano `useOptimisticChat`:

- Nessuno - Hook non utilizzato

### File che Usano Client-Side:

- ✅ `apps/mouth/src/app/chat/page.tsx` - **ATTIVO**
- ✅ `apps/mouth/src/hooks/useChatStreaming.ts` - **ATTIVO**
- ✅ `apps/mouth/src/lib/api/api-client.ts` - **ATTIVO**

---

## 📝 MIGRATION GUIDE

### Per Sviluppatori che Usano `sendMessageStream`:

**Prima:**

```typescript
import { sendMessageStream } from '@/app/chat/actions';

const stream = await sendMessageStream(messages, sessionId, userId);
const reader = stream.getReader();
// ... process stream
```

**Dopo:**

```typescript
import { api } from '@/lib/api';

await api.sendMessageStreaming(
  message,
  sessionId,
  (chunk) => {
    /* onChunk */
  },
  (full, sources, metadata) => {
    /* onDone */
  },
  (error) => {
    /* onError */
  },
  (step) => {
    /* onStep */
  }
);
```

### Per Sviluppatori che Usano `useOptimisticChat`:

**Prima:**

```typescript
import { useOptimisticChat } from '@/hooks/useOptimisticChat';

const { send, messages } = useOptimisticChat({ userId, onError });
```

**Dopo:**

```typescript
import { api } from '@/lib/api';

// Usa direttamente api.sendMessageStreaming() o useChatStreaming hook
await api.sendMessageStreaming(...);
```

---

## 🧪 TEST COVERAGE

### Test Esistenti:

- ✅ `chat.api.test.ts` - 78+ test cases per `sendMessageStreaming`
- ✅ `api-client.test.ts` - Test wrapper
- ✅ `streaming.integration.test.ts` - Test integrazione
- ✅ `conversation-flow.integration.test.ts` - Test flusso conversazione

### Test da Aggiungere (Opzionale):

- [ ] Test deprecation warning
- [ ] Test metriche logging
- [ ] Test backward compatibility `sendMessageStream`

---

## 📈 METRICHE MONITORAGGIO

### Metriche Tracciate:

1. **Performance:**
   - `totalDuration` - Durata totale richiesta
   - `timeToFirstChunk` - Tempo al primo byte (TTFB)
   - `streamingDuration` - Durata streaming effettiva

2. **Volume:**
   - `chunkCount` - Numero chunk ricevuti
   - `totalBytesReceived` - Byte totali
   - `responseLength` - Lunghezza risposta

3. **Eventi:**
   - `eventTypes` - Conteggio per tipo evento
   - `sourcesCount` - Numero fonti RAG

4. **Errori:**
   - `errorType` - Tipo errore
   - `errorMessage` - Messaggio errore
   - `duration` - Durata prima dell'errore

### Log Format:

```typescript
// Success
[ChatApi] Stream completed {
  correlationId: "req-123456",
  totalDuration: "5234ms",
  timeToFirstChunk: "234ms",
  streamingDuration: "5000ms",
  chunkCount: 45,
  totalBytesReceived: 12345,
  responseLength: 1234,
  sourcesCount: 3,
  eventTypes: { token: 45, sources: 1, metadata: 1 },
  hasGeneratedImage: false
}

// Error
[ChatApi] Stream error {
  correlationId: "req-123456",
  errorType: "Timeout",
  errorMessage: "Request timeout",
  duration: "120000ms",
  timedOut: true,
  chunkCount: 12,
  totalBytesReceived: 3456,
  eventTypes: { token: 12 }
}
```

---

## ✅ CHECKLIST FINALE

- [x] Deprecare `sendMessageStream` con warning
- [x] Deprecare `useOptimisticChat` con warning
- [x] Verificare feature `chat.api.ts`
- [x] Aggiornare documentazione
- [x] Rimuovere import non utilizzati (nessuno trovato)
- [x] Aggiungere logging e metriche
- [x] Verificare backward compatibility
- [x] Verificare linter errors (nessuno)
- [ ] Test deprecation (opzionale)
- [ ] Test metriche (opzionale)

---

## 🚀 PROSSIMI STEP

1. **Monitoraggio:** Verificare che nessuno usi ancora `sendMessageStream` in produzione
2. **Rimozione:** Dopo periodo di deprecazione (es. 3 mesi), rimuovere completamente
3. **Documentazione:** Aggiornare README con migration guide se necessario

---

## 📚 RIFERIMENTI

- **Source of Truth:** `apps/mouth/src/lib/api/chat/chat.api.ts`
- **Deprecation:** `apps/mouth/src/app/chat/actions.ts` (linea 108)
- **Hook Deprecato:** `apps/mouth/src/hooks/useOptimisticChat.ts`
- **Analisi Duplicazione:** `docs/ai/DUPLICATE_STREAMING_ANALYSIS.md`

---

**Last Updated:** 2026-01-13
