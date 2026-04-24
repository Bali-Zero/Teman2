# Layer 2: OpenAPI Type Safety Pipeline — Codex Brief

## Obiettivo

Riconnettere la pipeline OpenAPI → TypeScript che era stata abbandonata. Quando completa, ogni mismatch di tipo tra backend Python e frontend TypeScript diventa un errore compile-time.

## Contesto

- `docs/TYPE_SAFETY_GUIDE.md` documenta la pipeline (implementata 2026-02-06)
- `apps/mouth/src/lib/api/schema.d.ts` esisteva, generato da `openapi-typescript`, ma è stato disconnesso
- Il commento in `client.ts` dice: "Generated OpenAPI client removed - was importing from non-existent file"
- Il backend FastAPI ha `response_model` rigorosi su quasi tutti gli endpoint (88 router)

## Piano di lavoro (sezione per sezione)

### Fase 1: Generare openapi.json

1. Creare `apps/backend-rag/scripts/generate_openapi.py` che:
   - Importa `create_app()` da `backend.app.setup.app_factory`
   - Chiama `app.openapi()` per ottenere lo schema
   - Scrive in `apps/backend-rag/openapi.json`
   - NOTA: potrebbe servire `ENVIRONMENT=test` o mock dei pool DB per evitare connessioni reali al boot
2. Eseguire: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. python scripts/generate_openapi.py`
3. Verificare che `openapi.json` è generato senza errori

### Fase 2: Rigenerare schema.d.ts

1. Da `apps/mouth/`: `npx openapi-typescript ../../apps/backend-rag/openapi.json -o src/lib/api/schema.d.ts`
2. Aggiungere script in `apps/mouth/package.json`: `"gen:api-types": "npx openapi-typescript ../../apps/backend-rag/openapi.json -o src/lib/api/schema.d.ts"`
3. Verificare che `schema.d.ts` è generato

### Fase 3: Misurare il danno

1. Eseguire `cd apps/mouth && npx tsc --noEmit 2>&1 | wc -l` per contare gli errori
2. Salvare l'output completo in `/tmp/tsc_errors_baseline.txt`
3. Categorizzare: quanti errori per file/sezione?

### Fase 4: Fix errori TypeScript (sezione per sezione)

Ordine prioritario:

1. **CRM** (`src/lib/api/crm/`, `src/app/(workspace)/clients/`, `src/app/(workspace)/process/`)
2. **HR** (`src/lib/api/hr/`, `src/app/(workspace)/hr/`)
3. **Resto** (portal, blog, intelligence, etc.)

Per ogni sezione:

- Fixare i type error allineando i tipi frontend ai `response_model` Pydantic del backend
- NON cambiare i backend models — il frontend si adatta al backend
- Sostituire `as any` con i tipi corretti da `schema.d.ts` dove possibile
- Verificare con `npx tsc --noEmit` dopo ogni batch

### Fase 5: Riconnettere in client.ts

- Trovare il commento "Generated OpenAPI client removed" in `src/lib/api/client.ts`
- Riconnettere l'import di `schema.d.ts`
- Verificare che `tsc --noEmit` passa pulito

## Regole IMPORTANTI

### NON committare su main

- Lavora su branch `feature/layer2-openapi-pipeline`
- `git checkout -b feature/layer2-openapi-pipeline` prima di iniziare
- Quando hai completato una fase, FERMATI e chiedi validazione a Claude Code (nella finestra principale) e a NB-1
- Solo dopo validazione si fa merge su main

### Regole di codice

- NON modificare backend Python (routers, services, models) — solo frontend si adatta
- NON rimuovere funzionalità — solo allineare tipi
- NON usare `@ts-ignore` per risolvere errori — risolvili davvero
- Se un `any` non è risolvibile senza refactoring, documentalo con `// TODO(layer2): needs refactoring`
- Usa `PYTHONPATH=.` quando esegui script Python dal backend
- Venv: `.venv` (NON `venv`)

### Validazione inter-agente

Dopo ogni fase completata:

1. Salva lo stato: `git add -A && git stash` (o commit su branch)
2. Scrivi un report: cosa hai fatto, quanti errori risolti, quanti rimangono
3. Il report va in `/tmp/codex_layer2_phase_N_report.md`
4. Aspetta che Claude Code e NB-1 validino prima di proseguire alla fase successiva

### Verifica finale

- `npx tsc --noEmit` deve dare 0 errori
- `npx vitest run` deve passare tutti i 924 test
- `openapi.json` deve essere generabile senza errori
- `schema.d.ts` deve essere rigenerabile da `openapi.json`

## File chiave da leggere prima di iniziare

- `docs/TYPE_SAFETY_GUIDE.md` — la documentazione originale della pipeline
- `apps/mouth/src/lib/api/client.ts` — dove schema.d.ts era importato
- `apps/mouth/src/lib/api/crm/crm.api.ts` — il client API CRM (più grande)
- `apps/mouth/src/lib/api/crm/crm.types.ts` — i tipi CRM attuali
- `apps/backend-rag/backend/app/setup/app_factory.py` — come si crea l'app FastAPI
