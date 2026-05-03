# 🔧 10 PASSAGGI DI PULIZIA & SOLIDIFICAMENTO

## CRM WORKSPACE + PORTAL

---

### PASSO 1: Rimozione Codice Morto 🗑️

**Target:** Commenti, funzioni non usate, variabili dead

**File da pulire:**

- `apps/mouth/src/app/(workspace)/clients/[id]/page.tsx` - Rimuovere funzioni legacy passport
- `apps/mouth/src/app/(workspace)/process/page.tsx` - Rimuovere vecchio mapping status
- `apps/mouth/src/app/portal/(authenticated)/process/page.tsx` - Pulire imports non usati

**Azione:**

```bash
# Trova codice morto
grep -n "quotation_sent\|payment_pending\|in_progress" apps/mouth/src/app/(workspace)/process/page.tsx
```

---

### PASSO 2: TypeScript Strict Compliance 📘

**Target:** `any` → `unknown`, optional chaining, null checks

**File:**

- `apps/mouth/src/lib/hooks/useRequiredDocuments.ts`
- `apps/mouth/src/app/(workspace)/process/[id]/RequiredDocumentsCard.tsx`

**Azione:**

```typescript
// PRIMA
const data: any = await api.get(...)

// DOPO
const data: RequiredDocument[] = await api.get(...)
```

---

### PASSO 3: Consolidamento Error Handling ⚠️

**Target:** Uniformare gestione errori in tutto il workspace

**Pattern da implementare:**

```typescript
const handleError = (err: unknown, context: string) => {
  const message = err instanceof Error ? err.message : "Unknown error";
  logger.error(`[${context}] ${message}`);
  toast.error(context, message);
};
```

**File:**

- Tutti i componenti workspace

---

### PASSO 4: Ottimizzazione React Performance ⚡

**Target:** useMemo, useCallback, React.memo

**File:**

- `apps/mouth/src/app/(workspace)/process/page.tsx`
  - Memoizzare `practicesByStatus`
  - Memoizzare `filteredPractices`
  - Callback per `handleStatusChange`

**Esempio:**

```typescript
const handleStatusChange = useCallback(
  async (id: number, status: string) => {
    // ... logic
  },
  [userEmail, toast],
);
```

---

### PASSO 5: Pulizia CSS & Classi Tailwind 🎨

**Target:** Rimuovere classi non usate, consolidare varianti

**File:**

- `apps/mouth/src/app/(workspace)/clients/[id]/page.tsx`
  - Consolidare colori alert in oggetto config
  - Rimuovere classi duplicate

**Pattern:**

```typescript
// PRIMA
className={`bg-${color}-500/10 text-${color}-500`}

// DOPO
const alertClasses = {
  warning: "bg-amber-500/10 text-amber-500",
  critical: "bg-red-500/10 text-red-500 animate-pulse",
};
```

---

### PASSO 6: Validazione Props con Zod 🛡️

**Target:** Runtime type safety per props complesse

**File:**

- `apps/mouth/src/lib/types/required-documents.ts`
- Nuovi componenti con props estese

**Aggiungere:**

```typescript
import { z } from "zod";

const RequiredDocumentSchema = z.object({
  id: z.number(),
  practice_id: z.number(),
  status: z.enum(["pending", "uploaded", "verified", "rejected"]),
  // ...
});

export type RequiredDocument = z.infer<typeof RequiredDocumentSchema>;
```

---

### PASSO 7: Standardizzazione Logger 📊

**Target:** Rimuovere console.\*, usare logger dedicato

**File:**

- `apps/mouth/src/app/portal/(authenticated)/process/page.tsx`
- `apps/mouth/src/app/(workspace)/process/[id]/page.tsx`

**Pattern:**

```typescript
// PRIMA
console.error("Failed to load data", err);

// DOPO
import { logger } from "@/lib/logger";
logger.error("Failed to load process data", { practiceId }, err);
```

---

### PASSO 8: Split Componenti Grandi ✂️

**Target:** Componenti >300 lines → separare in file

**File da splittare:**

- `apps/mouth/src/app/(workspace)/clients/[id]/page.tsx` (troppo grande)
  - Estrarre: `PassportCard.tsx`
  - Estrarre: `VisaCard.tsx`
  - Estrarre: `FamilyMembersSection.tsx`

- `apps/mouth/src/app/(workspace)/process/[id]/page.tsx`
  - Estrarre: `StatusEditModal.tsx`

---

### PASSO 9: Documentazione Inline 📚

**Target:** JSDoc per funzioni complesse

**Pattern:**

```typescript
/**
 * Handles document upload for required practice documents
 * @param practiceId - The practice ID
 * @param docId - The required document ID
 * @param file - Base64 encoded file
 * @returns Promise with upload result
 * @throws ApiError on upload failure
 */
async function uploadDocument(
  practiceId: number,
  docId: number,
  file: string,
): Promise<UploadResult> {
  // ...
}
```

---

### PASSO 10: Test Unitari Essenziali 🧪

**Target:** Coverage per logiche critiche

**File da testare:**

- `apps/mouth/src/lib/hooks/useRequiredDocuments.ts`
- `apps/mouth/src/lib/types/required-documents.ts`
- `apps/mouth/src/app/(workspace)/process/[id]/RequiredDocumentsCard.tsx`

**Esempio test:**

```typescript
// __tests__/useRequiredDocuments.test.ts
import { renderHook } from "@testing-library/react";
import { useRequiredDocuments } from "@/lib/hooks/useRequiredDocuments";

describe("useRequiredDocuments", () => {
  it("should calculate completion percentage correctly", () => {
    const { result } = renderHook(() =>
      useRequiredDocuments({ practiceId: 1 }),
    );
    expect(result.current.stats.completionPercentage).toBeDefined();
  });
});
```

---

## 📋 CHECKLIST ESECUZIONE

```bash
# Prima di iniziare
git status
git checkout -b cleanup/10-step-refactor

# Dopo ogni passo
npm run typecheck  # o tsc --noEmit
npm run lint
npm run build

# Test finale
npm run test:unit
```

---

## 🎯 PRIORITÀ

| Passo                      | Impatto | Sforzo |
| -------------------------- | ------- | ------ |
| 1 - Rimozione codice morto | Alto    | Basso  |
| 2 - TypeScript strict      | Alto    | Medio  |
| 3 - Error handling         | Alto    | Medio  |
| 4 - Performance React      | Medio   | Medio  |
| 5 - CSS cleanup            | Basso   | Basso  |
| 6 - Zod validation         | Medio   | Medio  |
| 7 - Logger standard        | Medio   | Basso  |
| 8 - Split componenti       | Alto    | Alto   |
| 9 - JSDoc                  | Basso   | Basso  |
| 10 - Test unitari          | Alto    | Alto   |

---

_Creato: 2026-02-19_
_Stato: Da eseguire_
