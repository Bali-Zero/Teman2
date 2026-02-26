# Patch: Rimozione residui AutoCRM e Omnichannel

## Contesto

Omnichannel e AutoCRM sono stati rimossi completamente dal sistema (backend + frontend UI).
Rimangono alcuni residui di codice morto nel layer API client del frontend che vanno eliminati.

**Non toccare nient'altro.** Solo i file elencati qui sotto.

---

## File 1: `apps/mouth/src/lib/api/crm/crm.types.ts`

**Rimuovere** l'intera interface `AutoCRMStats` (righe 530–563):

```typescript
// RIMUOVERE QUESTO BLOCCO INTERO (inclusa la riga vuota sopra):

export interface AutoCRMStats {
  total_extractions: number;
  successful_extractions: number;
  failed_extractions: number;
  clients_created: number;
  clients_updated: number;
  practices_created: number;
  last_24h: {
    extractions: number;
    clients: number;
    practices: number;
  };
  last_7d: {
    extractions: number;
    clients: number;
    practices: number;
  };
  extraction_confidence_avg: number | null;
  top_practice_types: Array<{
    code: string;
    name: string;
    count: number;
  }>;
  recent_extractions: Array<{
    id: number;
    client_id: number | null;
    practice_id: number | null;
    summary: string | null;
    sentiment: string | null;
    created_at: string | null;
    client_name: string | null;
    practice_type_code: string | null;
  }>;
}
```

---

## File 2: `apps/mouth/src/lib/api/crm/crm.api.ts`

**Step A** — Rimuovere `AutoCRMStats` dall'import in cima al file:

```typescript
// PRIMA (riga ~11):
import {
  CreateClientParams,
  CreatePracticeParams,
  RenewalAlert,
  AutoCRMStats,       // ← RIMUOVERE questa riga
  ClientSummary,
  ...
} from "./crm.types";

// DOPO:
import {
  CreateClientParams,
  CreatePracticeParams,
  RenewalAlert,
  ClientSummary,
  ...
} from "./crm.types";
```

**Step B** — Rimuovere il metodo `getAutoCRMStats` (righe 290–297):

```typescript
// RIMUOVERE QUESTO BLOCCO INTERO (inclusa la riga vuota sopra e il commento):

  /**
   * Get AUTO CRM extraction statistics
   */
  async getAutoCRMStats(days: number = 7): Promise<AutoCRMStats> {
    return this.client.request<AutoCRMStats>(
      `/api/crm/auto/stats?days=${days}`,
    );
  }
```

---

## File 3: `apps/mouth/src/lib/api/crm/crm.api.test.ts`

**Rimuovere** l'intero blocco `describe("getAutoCRMStats", ...)` (righe 654–679):

```typescript
// RIMUOVERE QUESTO BLOCCO INTERO (inclusa la riga vuota sopra):

describe("getAutoCRMStats", () => {
  it("should fetch AUTO CRM extraction stats", async () => {
    const mockStats = {
      total_extractions: 50,
      successful_extractions: 45,
      failed_extractions: 5,
      clients_created: 30,
      clients_updated: 10,
      practices_created: 20,
      last_24h: { extractions: 5, clients: 3, practices: 2 },
      last_7d: { extractions: 50, clients: 30, practices: 20 },
      extraction_confidence_avg: 0.85,
      top_practice_types: [],
      recent_extractions: [],
    };

    mockClient.request.mockResolvedValue(mockStats);

    const result = await crmApi.getAutoCRMStats(7);

    expect(mockClient.request).toHaveBeenCalledWith(
      "/api/crm/auto/stats?days=7",
    );
    expect(result.total_extractions).toBe(50);
  });
});
```

---

## Verifica post-modifica

Dopo aver fatto le modifiche, eseguire:

```bash
cd apps/mouth
npm run build 2>&1 | grep -E "error|Error"
npm run test -- --testPathPattern="crm.api" 2>&1 | tail -10
```

**Risultato atteso:**

- `npm run build`: nessun errore TypeScript
- `npm run test`: tutti i test CRM passano (il describe rimosso non esiste più)

---

## Commit

```
chore(frontend): remove AutoCRM dead code from API client

- Remove AutoCRMStats interface from crm.types.ts
- Remove getAutoCRMStats() method from crm.api.ts
- Remove getAutoCRMStats test from crm.api.test.ts

AutoCRM backend was removed in commit cb051e3e2.
This cleans up the remaining dead code in the API layer.
```

---

## Note importanti

- **NON rigenerare** `schema.d.ts` automaticamente — il file è gestito manualmente
- **NON modificare** altri file oltre ai 3 elencati
- **NON fare refactor** o "miglioramenti" non richiesti
- Se TypeScript dà errori su altri file che usano `AutoCRMStats`, segnalarlo senza correggere autonomamente
