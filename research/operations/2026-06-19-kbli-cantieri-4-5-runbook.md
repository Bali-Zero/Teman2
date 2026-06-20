---
date: 2026-06-19
domain: compliance
client_case: none
status: RUNBOOK — Cantiere 4 (Qdrant) + 5 (NB-3). PRONTO, NON ESEGUITO (confine produzione, GO Zero).
sources:
  - data/kbli_schema_v2/KBLI_2025_SCHEMA_V2.json
  - apps/backend-rag/backend/app/routers/kbli_notebook.py (collection resolver)
---

# Cantiere 4 + 5 — Runbook (NON eseguito in autonomia — toccano produzione)

> Safety: questi due cantieri mutano stato condiviso (Qdrant prod su Pro / NotebookLM curato).
> In autonomia li ho PREPARATI, non applicati. Servono il GO di Zero + esecuzione su Pro.

## CANTIERE 4 — Re-ingest Qdrant `kbli_2025_final`

**Collection**: `kbli_2025_final` (risolta via `resolve_collection_name()`), consumata da
kbli_notebook.py / dashboard_summary.py / knowledge/service.py.
**VINCOLO FERREO (golden rule #9)**: embedding `text-embedding-3-small` **1536-dim FROZEN**.
NON cambiare modello (93k vettori globali). Re-ingest = stesso modello, payload nuovo.

**Decisione delta-vs-recreate**:
- Il payload schema-v2 AGGIUNGE campi (l4_bali, l3 grounded, title_en separato) → è un cambio payload
  → richiede re-embed dei testi cambiati. Ma il TESTO embeddato (judul+uraian) è in gran parte
  invariato vs l'attuale (OSS = stessso uraian). → **strategia: recreate pulito** è più sicuro di
  delta parziale (evita payload misto vecchio/nuovo). Costo: ~1559 embed (text-embedding-3-small,
  economico). Da fare SU PRO (dove gira Qdrant + ci sono le API key embedding).

**Payload flat per il vettore** (rispetta KBLI flat payload, golden rule #9):
  kode_kbli, judul, content(=uraian), sektor_id, pma_status, skala_usaha, kategori_risiko,
  + NUOVI: bali_status, bali_blocked(bool), title_en. (NO nested — flat.)

**Procedura (su Pro)**:
```bash
ssh pro
cd ~/Desktop/nuzantara && git fetch && git checkout agent/air-m5/intel/kbli-schema-v2
# rigenera lo schema (artifact gitignored): 
cd .worktrees/... || cd apps/backend-rag && source .venv/bin/activate
python <worktree>/scripts/kbli_schema_v2_populate.py   # produce KBLI_2025_SCHEMA_V2.json
# poi uno script ingest (DA SCRIVERE su Pro con le sue API key embedding) che:
#   1. legge KBLI_2025_SCHEMA_V2.json
#   2. per ogni 5-digit: text = judul + " " + uraian; embed con text-embedding-3-small (1536)
#   3. payload flat come sopra (incl. bali_status)
#   4. recreate_collection kbli_2025_final (vectors=1536, distance=Cosine) → upsert
#   5. verify: count == 1559, smoke query "villa bali" → 55203 con bali_status=BLOCCATO
```
**Verifica post**: `curl .../collections/kbli_2025_final` count + 1 query nota. NON marcare done
finché lo smoke-test passa LIVE.

## CANTIERE 5 — Update NB-3 (Company, UUID 933509f9)

NB-3 = sole consumer NotebookLM company/KBLI (Contract 2). Mutazione di ground-truth curato →
**diff preparato, NON applicato**.

**Cosa aggiungere a NB-3**:
1. **Strato L4 (moratoria Bali)** — NB-3 oggi porta solo status nazionale. Aggiungere come text source
   un sunto verificato: moratoria 13/5/26 whole-class low/medium-low + virtual-office ban + i codici
   TERTUTUP/TERBATAS/CHIUSO-BALI (dallo schema L4, NON da memoria).
   ⚠ fonti afe820b0+81630d48 GIÀ aggiunte (2026-06-09) — VERIFICARE prima, non duplicare.
2. **Correzione 2 errori noti NB-3**:
   - "74149 = codice nuovo KBLI 2025" → FALSO (74149 non esiste 2025, è 2020). Veri creator 2025:
     59112/60103/60203/60390/90113/90200.
   - conflation 2020/2025 su codici creator.

**Procedura (con GO Zero)**:
```
mcp__notebooklm-mcp__source_add(notebook=933509f9..., source_type=text, text="<L4 summary verificato>")
# + nota di correzione 74149
mcp__notebooklm-mcp__notebook_query per verificare ground-truth post-update
```
**NON applicato in autonomia**: scrivere su NB curato è prerogativa che lascio a Zero.

## Stato schema per entrambi
`KBLI_2025_SCHEMA_V2.json` (rigenerabile) ha già: L4 su tutti i 2422 + L3 grounded su 780 5-digit.
Gli 11 `needs_human_review` (codici-divieto rinumerati) restano da confermare prima dell'ingest finale.
