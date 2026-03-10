# Nuzantara

Monorepo della piattaforma AI di Bali Zero, alimentata da Zantara.

Il repository raccoglie backend RAG/API, frontend web, dashboard amministrative, server MCP, knowledge graph, servizi KBLI e strumenti operativi di supporto.

## Panoramica

Nuzantara e una piattaforma multi-app organizzata come monorepo. I componenti principali oggi attivi sono:

- `apps/backend-rag`: backend FastAPI per API, RAG, orchestrazione, knowledge graph e integrazioni dati
- `apps/mouth`: frontend Next.js principale
- `apps/admin-dashboard`: dashboard amministrativa
- `apps/webapp`: web application complementare
- `apps/nuzantara-mcp`: server MCP principale
- `packages/core` e `packages/shared-schemas`: package condivisi

Il repository contiene anche app secondarie, strumenti di scraping, evaluation, media tooling e componenti legacy o sperimentali che devono restare organizzati fuori dalla root.

## Struttura Del Progetto

```text
nuzantara/
├── apps/                      # Applicazioni del monorepo
│   ├── backend-rag/           # Backend FastAPI + RAG + KG
│   ├── mouth/                 # Frontend Next.js principale
│   ├── admin-dashboard/       # Admin UI
│   ├── webapp/                # Web app complementare
│   ├── nuzantara-mcp/         # MCP server principale
│   └── ...                    # Altre app di supporto, ricerca o legacy
├── packages/                  # Librerie e schemi condivisi
├── docs/                      # Documentazione tecnica, operativa e architetturale
├── scripts/                   # Script di setup, deploy, manutenzione e analisi
├── config/                    # Configurazioni condivise
├── data/                      # Dataset e file strutturati condivisi, incluse source documents
├── tests/                     # Test cross-project o harness condivisi
├── package.json               # Workspace root e script condivisi
└── docker-compose*.yml        # Stack locali, production e monitoring
```

## Componenti Principali

### Backend

Il backend principale vive in `apps/backend-rag` ed e basato su FastAPI. Gestisce:

- API applicative
- retrieval-augmented generation
- knowledge graph
- integrazione con PostgreSQL, Qdrant e Redis
- orchestrazione tool/agent
- canali di comunicazione e servizi verticali

### Frontend

Il frontend principale vive in `apps/mouth` ed e basato su Next.js. Gestisce l'esperienza web pubblica e le interfacce applicative collegate.

### MCP

`apps/nuzantara-mcp` ospita il server MCP principale, usato per tool, prompt, risorse e workflow automation.

## Prerequisiti

- Node.js 20+
- npm 10+
- Python 3.11+
- `venv` o `virtualenv`
- Docker e Docker Compose opzionali
- Variabili ambiente richieste dai servizi utilizzati

## Setup

### 1. Clonare il repository

```bash
git clone <repo-url>
cd nuzantara
```

### 2. Installare le dipendenze JavaScript del workspace

```bash
npm install
```

### 3. Configurare le variabili ambiente

Partire da:

```bash
cp .env.example .env
```

Compilare poi i valori necessari per i servizi che si vogliono eseguire.

## Setup Backend

Il backend Python usa una virtualenv locale dedicata.

```bash
cd apps/backend-rag
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Avvio locale:

```bash
PYTHONPATH=. python -m uvicorn backend.main:app --reload --port 8000
```

## Setup Frontend

```bash
cd apps/mouth
npm install
npm run dev
```

## Utilizzo

### Avviare il backend

```bash
cd apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. python -m uvicorn backend.main:app --reload --port 8000
```

### Avviare il frontend principale

```bash
cd apps/mouth
npm run dev
```

### Eseguire i test frontend dal root workspace

```bash
npm run test
```

### Typecheck frontend dal root workspace

```bash
npm run typecheck
```

## Convenzioni Del Repository

- La root deve contenere solo file essenziali di bootstrap e configurazione.
- La documentazione tecnica vive in `docs/`.
- Gli script operativi vivono in `scripts/`.
- I report non devono essere lasciati sparsi in root.
- Le credenziali non devono essere versionate.
- Gli artefatti locali come cache, screenshot, log, output di test e ambienti virtuali non devono essere committati.

## Documentazione

La documentazione tecnica e operativa e organizzata in `docs/`.

Aree principali:

- `docs/architecture/`
- `docs/operations/`
- `docs/reports/` quando presente
- `config/prompts/`
- `docs/security/`

Per l'onboarding tecnico e le regole operative del progetto:

- `docs/AI_ONBOARDING.md`
- `docs/LIVING_ARCHITECTURE.md`

## Deploy

### Backend

Il backend principale e pensato per Fly.io.

### Frontend

Il frontend principale e pensato per Vercel.

I dettagli operativi di deploy e runbook devono essere mantenuti sotto `docs/operations/`.

## Stato Del Repository

Il repository contiene sia componenti attivi sia materiale storico o sperimentale. Quando si aggiungono nuovi file:

- usare le cartelle canoniche gia esistenti
- evitare nuovi file sciolti in root
- classificare chiaramente cio che e `core`, `support`, `legacy` o `experimental`

## Manutenzione Consigliata

Interventi raccomandati a breve:

1. Consolidare la documentazione dispersa dentro `docs/`.
2. Spostare i report ad hoc dalla root verso cartelle tematiche in `docs/`.
3. Spostare gli script sciolti in root dentro `scripts/`.
4. Rimuovere dal repository credenziali e file sensibili.
5. Eliminare lockfile duplicati e standardizzare il package manager.
6. Spostare output di test, screenshot e asset temporanei fuori dalla root.
7. Archiviare o classificare in modo esplicito le directory legacy.

## Note Di Compatibilita

Alcune directory storicamente referenziate da script e documentazione sono state riallineate ma mantengono un path compatibile in root:

- `source_documents` punta alla home canonica `data/source_documents`
- `monitoring` punta alla home canonica `config/monitoring`
- `prompts` punta alla home canonica `config/prompts`
- `POSTGRESQL` punta alla home canonica `docs/database/postgresql`
- `reports` punta alla home canonica `docs/reports/root-legacy/reports`
- `tools` punta alla home canonica `scripts/tools`
- `storage` punta alla home canonica `data/runtime/storage`
- `backend` punta alla home canonica `archives/legacy-root/backend`

Eccezioni temporanee ancora presenti in root:

- `app_dashboard.py`, perche e ancora trattato come entrypoint standalone da documentazione e piani storici

## Licenza

Aggiungere un file `LICENSE` in root se il repository deve esporre una policy di utilizzo esplicita.
