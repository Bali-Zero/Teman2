# CLEANUP 5 STEPS PLAN

**Data:** 2026-01-13  
**Obiettivo:** Pulizia sistematica di legacy, duplicati, bug e ridondanze

---

## 📋 ANALISI INIZIALE

### Problemi Identificati:

1. **Console Logging** (92 file)
   - `console.log/warn/error/debug` invece di logger strutturato
   - Perdita di tracciabilità e contesto

2. **TODO Comments** (10+ trovati)
   - TODO non risolti che indicano codice incompleto
   - Alcuni critici, altri non necessari

3. **Type Safety** (13 occorrenze `any`)
   - Uso di `any` che nasconde errori
   - `unknown` non gestito correttamente

4. **Error Handling Duplicato**
   - Pattern di gestione errori ripetuti
   - Nessuna standardizzazione

5. **Dead Code**
   - Codice commentato
   - Funzioni non utilizzate

---

## 🎯 5 PASSAGGI DI PULIZIA

### PASSO 1: Sostituire Console Logging con Logger Strutturato ✅

**File Prioritari:**
- ✅ `apps/mouth/src/lib/api/chat/chat.api.ts` - COMPLETATO
- ⏳ `apps/mouth/src/app/(workspace)/clients/[id]/page.tsx` - 3 console.error
- ⏳ `apps/mouth/src/app/(workspace)/process/new/page.tsx` - 2 console.error
- ⏳ `apps/mouth/src/app/(workspace)/process/[id]/page.tsx` - 1 console.error
- ⏳ `apps/mouth/src/components/dashboard/AutoCRMWidget.tsx` - 2 console.error

**Pattern da Applicare:**
```typescript
// PRIMA
console.error('Failed to load client data:', err);

// DOPO
import { logger } from '@/lib/logger';
logger.error('Failed to load client data', {
  component: 'ClientDetailPage',
  action: 'loadClientData',
}, err instanceof Error ? err : new Error(String(err)));
```

**Benefici:**
- Tracciabilità strutturata
- Context automatico (component, action)
- Filtrabile per livello
- Integrazione con monitoring

---

### PASSO 2: Risolvere TODO Critici

**TODO Trovati:**
1. `apps/mouth/src/app/(workspace)/process/[id]/page.tsx:86` - Replace with dedicated API endpoint
2. `apps/mouth/src/app/(workspace)/process/[id]/page.tsx:473` - Add notes field to Practice type
3. `apps/mouth/src/app/(workspace)/documents/page.tsx:324` - Get storageUsed from API
4. `apps/mouth/src/components/blog/ArticleEngagement.tsx:387` - Send to backend
5. `apps/mouth/src/lib/web-vitals.ts:9` - Re-enable when dependency resolved

**Azioni:**
- Risolvere TODO critici (API endpoints, type definitions)
- Rimuovere TODO non necessari
- Creare issue per TODO futuri

---

### PASSO 3: Migliorare Type Safety

**Problemi:**
- `any` type in test files (accettabile)
- `unknown` non gestito correttamente
- Type assertions non sicure

**Azioni:**
- Sostituire `any` con tipi specifici dove possibile
- Aggiungere type guards per `unknown`
- Migliorare type assertions

**Pattern:**
```typescript
// PRIMA
const data: unknown = JSON.parse(jsonStr);
const value = data as any;

// DOPO
const data: unknown = JSON.parse(jsonStr);
if (isRecord(data) && typeof data.field === 'string') {
  const value = data.field; // Type-safe
}
```

---

### PASSO 4: Unificare Error Handling

**Pattern Duplicati:**
- Try-catch con console.error
- Error handling senza context
- Nessuna standardizzazione

**Soluzione:**
- Creare utility `handleError()` standardizzata
- Usare logger strutturato ovunque
- Aggiungere error boundaries dove necessario

**Pattern:**
```typescript
// Utility centralizzata
export function handleError(
  error: unknown,
  context: { component: string; action: string }
): void {
  logger.error('Operation failed', context, 
    error instanceof Error ? error : new Error(String(error))
  );
}
```

---

### PASSO 5: Rimuovere Dead Code

**Da Cercare:**
- Codice commentato non necessario
- Funzioni non utilizzate
- Import non utilizzati
- Variabili non utilizzate

**Strumenti:**
- ESLint `no-unused-vars`
- TypeScript `noUnusedLocals`
- Manual review

---

## 📊 METRICHE DI SUCCESSO

### Prima:
- ❌ 92 file con console.log/warn/error
- ❌ 10+ TODO non risolti
- ❌ 13 occorrenze `any` non necessarie
- ❌ Pattern error handling duplicati
- ❌ Dead code presente

### Dopo:
- ✅ 0 console.log/warn/error (sostituiti con logger)
- ✅ TODO critici risolti, altri documentati
- ✅ Type safety migliorata
- ✅ Error handling standardizzato
- ✅ Dead code rimosso

---

## 🚀 PRIORITÀ

1. **ALTA:** Console logging in file critici (API, pages principali)
2. **MEDIA:** TODO critici (API endpoints, type definitions)
3. **MEDIA:** Type safety improvements
4. **BASSA:** Error handling unification
5. **BASSA:** Dead code removal

---

## 📝 NOTE

- Mantenere backward compatibility
- Testare dopo ogni passo
- Documentare cambiamenti significativi
- Non rompere funzionalità esistenti

---

**Last Updated:** 2026-01-13
