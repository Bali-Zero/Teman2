# Owner Weekly Cashout — Design

**Date:** 2026-04-07
**Owner:** Zero
**Status:** Draft → Awaiting review
**Visibility:** OWNER ONLY (zero@balizero.com, antonellosiano@balizero.com)

---

## Goal

Importare nel `kita.balizero.com/hr` (sezione personale dell'owner) i dati del Google Sheet "WEEKLY CASHOUT" (`1OZzgvDLgf3yd9eUh5CyADjHCHLoXmE5nIRoJlut_jBE`) per avere una vista aggregata + drill-down delle pratiche settimanali Bali Zero / Bali Services con relativi margini.

I dati sono **strettamente confidenziali**: solo l'owner deve vederli, nemmeno gli altri admin (Adit, Asya).

## Non-goals

- Sostituire il foglio (resta source of truth, l'owner continua a editarlo)
- Editing dei dati dalla UI (sola lettura)
- Sync bidirezionale
- Multi-currency / conversione FX
- Notifiche automatiche su nuove settimane (si scopre dal cron settimanale)
- Integrazione con i payslip aziendali esistenti (`hr_employees`, `payroll_periods`) — sistemi disgiunti

---

## Sheet structure (verified 2026-04-07)

**Spreadsheet:** `WEEKLY CASHOUT` — 46 tab totali.
Verificato 2026-04-07: **22 tab BZ + 21 tab BS** (BS 30 JAN ancora da creare) **+ 3 da skippare** (`Sheet18`, `Copy of BZ 31 OCT`, `BS 19 DEC 25 - 09 JAN 26` = riassunto 3-week duplicato).

**Settimane mappate:** 22 settimane logiche dal **22 AUG 2025** al **30 JAN 2026**, di cui 2 sono "combo weeks" (`BZ 26 DES & 2 JAN`, `BZ 16-23 JAN 26`) che coprono 2 settimane in una sola tab.

**Pattern tab:** `BZ DD MMM[ YY]` e `BS DD MMM[ YY]`, di norma una coppia per settimana.
Junk da ignorare: `Sheet18`, `Copy of BZ 31 OCT`, `BS 19 DEC 25 - 09 JAN 26`.

**Schema tab BZ** (es. `BZ 22 AUG`):
```
Riga 1: NEW CASHOUT 22 AUGUST 2025          (titolo, ignorare)
Riga 2: NAME | PROCESS | PNBP | URGENT | RPTKA/IMTA | TOTAL INCOME | MARGIN BS | MARGIN BZ | NOTE
Riga 3+: dati clienti (righe vuote come separatori visivi tra gruppi)
```

**Schema tab BS** (es. `BS 22 AUG`):
```
Riga 1: NEW CASHOUT 22 AUG                  (titolo, ignorare)
Riga 2: NAME | PROCESS | PNBP | URGENT | RPTKA/IMTA | MARGIN BS | FINAL PRICE
Riga 3+: dati clienti
```

**Edge cases osservati:**
- Importi formato `Rp1,000,000` (stringa con prefisso e virgole)
- Celle vuote `""` per campi non applicabili
- Righe completamente vuote come separatori
- Nome cliente troncato a volte (es. `LUIZA BIEKIETOVA (RUSLANA`)
- Note libere occasionali in colonna I (BZ): `DISCOUNT 200K`
- Visa types eterogenei: `C1`, `C10`, `C22B`, `D12 1 YEAR`, `D12 1 YEAR - URGENT`, `D12 2 YEARS`, `BRIDGING VISA`...

---

## Architecture

```
Google Sheet (WEEKLY CASHOUT)
        |
        | Sheets API v4 (read-only)
        | SA: nuzantara-google-drive-sa@nuzantara.iam.gserviceaccount.com
        v
Air (cron Monday 09:00 WITA)
sync_owner_cashout.py
        |
        | upsert via asyncpg
        v
PostgreSQL (Fly: nuzantara-postgres)
  - owner_weekly_cashout_weeks
  - owner_weekly_cashout_rows
  - owner_cashout_sync_log
        |
        | SELECT (owner-only auth)
        v
FastAPI (nuzantara-rag) /api/hr/owner/cashout/*
        |
        v
Next.js (kita.balizero.com)
/hr/owner-cashout (page + sidebar entry)
```

---

## Auth & privacy

### Service Account (Sheet read)
- File: `/Users/nuzantara/Desktop/codexyz/nuzantara-google-drive-sa-key-20260312.json`
- Email: `nuzantara-google-drive-sa@nuzantara.iam.gserviceaccount.com`
- Scope: `https://www.googleapis.com/auth/spreadsheets.readonly`
- Sheet già condiviso con la SA come Viewer (verificato funzionante 2026-04-07)
- **Deploy**: la chiave JSON va caricata come secret su Air (env `OWNER_CASHOUT_SA_JSON`), NON committata

### Owner gate (FastAPI)
Nuovo dependency `backend/app/dependencies/owner.py`:

```python
OWNER_EMAILS = frozenset({
    "zero@balizero.com",
    "antonellosiano@balizero.com",
})

async def require_owner(
    user: dict = Depends(get_current_user),
) -> dict:
    if user.get("email") not in OWNER_EMAILS:
        raise HTTPException(status_code=403, detail="Owner access required")
    return user
```

Tutti gli endpoint `/api/hr/owner/cashout/*` proteggi con `Depends(require_owner)`. Gli altri admin (zainal@, asya@, etc.) ricevono 403.

### Owner gate (Next.js sidebar)
- Voce sidebar "Owner Cashout" renderizzata solo se `session.user.email in OWNER_EMAILS`
- Pagina `/hr/owner-cashout` chiama l'API. Server-side già blocca, ma evitiamo il flash mostrando 404-style se non owner

### NO logging del payload
- Sync log salva `weeks_processed` count, MAI nomi clienti o importi
- API logger filtra response body per `/api/hr/owner/cashout/*` (no body in access log)

---

## Data model (PostgreSQL)

Migration `070_owner_weekly_cashout.sql`:

```sql
-- Settimana = una riga (anche se ha 2 tab BZ+BS nel foglio)
CREATE TABLE owner_weekly_cashout_weeks (
    id SERIAL PRIMARY KEY,
    week_start DATE NOT NULL UNIQUE,        -- es. 2025-08-22
    tab_name_bz TEXT,                       -- 'BZ 22 AUG'
    tab_name_bs TEXT,                       -- 'BS 22 AUG'
    total_practices INT NOT NULL DEFAULT 0,
    total_income_idr BIGINT NOT NULL DEFAULT 0,    -- somma da tab BZ
    total_margin_bz_idr BIGINT NOT NULL DEFAULT 0, -- somma da tab BZ
    total_margin_bs_idr BIGINT NOT NULL DEFAULT 0, -- somma da tab BS
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Riga = una pratica per cliente, una entry per entity (BZ o BS)
CREATE TABLE owner_weekly_cashout_rows (
    id SERIAL PRIMARY KEY,
    week_id INT NOT NULL REFERENCES owner_weekly_cashout_weeks(id) ON DELETE CASCADE,
    entity TEXT NOT NULL CHECK (entity IN ('BZ', 'BS')),
    row_index INT NOT NULL,                 -- riga originale nello sheet (debug)
    client_name TEXT NOT NULL,
    process TEXT,                           -- 'C1', 'D12 1 YEAR', etc.
    pnbp_idr BIGINT DEFAULT 0,
    urgent_idr BIGINT DEFAULT 0,
    rptka_imta_idr BIGINT DEFAULT 0,
    total_income_idr BIGINT DEFAULT 0,      -- popolato solo per BZ
    margin_bs_idr BIGINT DEFAULT 0,
    margin_bz_idr BIGINT DEFAULT 0,         -- popolato solo per BZ
    final_price_idr BIGINT DEFAULT 0,       -- popolato solo per BS
    note TEXT,
    UNIQUE (week_id, entity, row_index)
);

CREATE INDEX idx_cashout_rows_week ON owner_weekly_cashout_rows(week_id);
CREATE INDEX idx_cashout_rows_process ON owner_weekly_cashout_rows(process);
CREATE INDEX idx_cashout_weeks_start ON owner_weekly_cashout_weeks(week_start DESC);

-- Sync history
CREATE TABLE owner_cashout_sync_log (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL,                   -- 'success' | 'partial' | 'failed'
    weeks_processed INT DEFAULT 0,
    weeks_skipped INT DEFAULT 0,
    rows_upserted INT DEFAULT 0,
    error TEXT,
    triggered_by TEXT NOT NULL              -- 'cron' | 'manual:zero@balizero.com'
);

CREATE INDEX idx_sync_log_started ON owner_cashout_sync_log(started_at DESC);
```

**Backup:** coperto da `~/scripts/fly-pg-backup.sh` esistente (Tigris daily).
**RLS:** non necessario, l'unico ingresso è l'API gated da `require_owner()`.

---

## Sync job

**File:** `apps/backend-rag/scripts/sync_owner_cashout.py` (eseguibile su Air via cron + via FastAPI endpoint).

### Tab → week_start lookup table

Hardcoded nel codice (zero parser fuzzy):

```python
# Verified against sheet 2026-04-07 — 22 weeks Aug 2025 → Jan 2026
TAB_TO_WEEK: dict[str, date] = {
    "BZ 22 AUG":          date(2025, 8, 22),
    "BS 22 AUG":          date(2025, 8, 22),
    "BZ 29 AUG":          date(2025, 8, 29),
    "BS 29 AUG":          date(2025, 8, 29),
    "BZ 05 SEPT":         date(2025, 9, 5),
    "BS 05 SEPT":         date(2025, 9, 5),
    "BZ 12 SEPT":         date(2025, 9, 12),
    "BS 12 SEPT":         date(2025, 9, 12),
    "BZ 19 SEPT":         date(2025, 9, 19),
    "BS 19 SEPT":         date(2025, 9, 19),
    "BZ 26 SEPT":         date(2025, 9, 26),
    "BS 26 SEPT":         date(2025, 9, 26),
    "BZ 03 OCT":          date(2025, 10, 3),
    "BS 03 OCT":          date(2025, 10, 3),
    "BZ 10 OCT":          date(2025, 10, 10),
    "BS 10 OCT":          date(2025, 10, 10),
    "BZ 17 OCT":          date(2025, 10, 17),
    "BS 17 OCT":          date(2025, 10, 17),
    "BZ 24 OCT":          date(2025, 10, 24),
    "BS 24 OCT":          date(2025, 10, 24),
    "BZ 31 OCT":          date(2025, 10, 31),
    "BS 31 OCT":          date(2025, 10, 31),
    "BZ 07 NOV":          date(2025, 11, 7),
    "BS 07 NOV":          date(2025, 11, 7),
    "BZ 14 NOV":          date(2025, 11, 14),
    "BS 14 NOV":          date(2025, 11, 14),
    "BZ 21 NOV":          date(2025, 11, 21),
    "BS 21 NOV":          date(2025, 11, 21),
    "BZ 28 NOV":          date(2025, 11, 28),
    "BS 28 NOV":          date(2025, 11, 28),
    "BZ 05 DEC":          date(2025, 12, 5),
    "BS 05 DEC":          date(2025, 12, 5),
    "BZ 12 DEC":          date(2025, 12, 12),
    "BS 12 DEC":          date(2025, 12, 12),
    "BZ 19 DEC":          date(2025, 12, 19),
    "BS 19 DEC":          date(2025, 12, 19),
    "BZ 26 DES & 2 JAN":  date(2025, 12, 26),  # combina 2 settimane in 1 tab
    "BS 26 DES & 2 JAN":  date(2025, 12, 26),
    "BZ 09 JAN 26":       date(2026, 1, 9),
    "BS 09 JAN 26":       date(2026, 1, 9),
    "BZ 16-23 JAN 26":    date(2026, 1, 16),   # combina 2 settimane in 1 tab
    "BS 16-23 JAN 26":    date(2026, 1, 16),
    "BZ 30 JAN":          date(2026, 1, 30),
    # NOTE: BS 30 JAN attualmente assente nel foglio (verificato 2026-04-07)
    # Quando l'owner la creerà sarà tab unknown → alert TG → aggiungi qui
}

# Tab da skippare esplicitamente (junk o duplicati)
JUNK_TABS: frozenset[str] = frozenset({
    "Sheet18",
    "Copy of BZ 31 OCT",                # backup vecchio
    "BS 19 DEC 25 - 09 JAN 26",         # riassunto 3-settimane, dati già in BS 19/26 DEC + 09 JAN
})
```

**Note:**
- 2 tab combinano 2 settimane in una (`BZ 26 DES & 2 JAN`, `BZ 16-23 JAN 26`). Le mappiamo alla data della prima settimana — in UI verranno mostrate come "Week of Dec 26 (2 weeks)" con nota.
- `BS 30 JAN` manca attualmente nel foglio. Non è un errore: verrà creata dall'owner quando chiuderà la settimana, e il sync la flagga come unknown la prima volta.

**Quando arriva una tab nuova non in lookup:** sync continua sulle altre, log warning, **alert Telegram a chat 1125336968**:
> ⚠️ Owner Cashout sync: tab sconosciuta `BZ FEB 06`. Aggiungila a `TAB_TO_WEEK` in `sync_owner_cashout.py` e rifai sync.

L'owner aggiunge l'entry, commit, restart sync.

### Parser

```python
def parse_idr(s: str) -> int:
    """'Rp1,000,000' -> 1000000, '' -> 0, None -> 0"""
    if not s:
        return 0
    cleaned = str(s).replace("Rp", "").replace(",", "").replace(".", "").strip()
    if not cleaned or cleaned in ("-", "—"):
        return 0
    try:
        return int(cleaned)
    except ValueError:
        logger.warning(f"[CASHOUT] Failed to parse IDR: {s!r}")
        return 0


def parse_bz_tab(rows: list[list[str]]) -> list[CashoutRow]:
    """Schema BZ: NAME|PROCESS|PNBP|URGENT|RPTKA/IMTA|TOTAL_INCOME|MARGIN_BS|MARGIN_BZ|NOTE"""
    out = []
    # Riga 1 = titolo, Riga 2 = header, dati da riga 3
    for i, row in enumerate(rows[2:], start=3):
        # Pad row to 9 columns
        row = (row + [""] * 9)[:9]
        name = row[0].strip()
        if not name:  # riga vuota separatore
            continue
        out.append(CashoutRow(
            entity="BZ",
            row_index=i,
            client_name=name,
            process=row[1].strip() or None,
            pnbp_idr=parse_idr(row[2]),
            urgent_idr=parse_idr(row[3]),
            rptka_imta_idr=parse_idr(row[4]),
            total_income_idr=parse_idr(row[5]),
            margin_bs_idr=parse_idr(row[6]),
            margin_bz_idr=parse_idr(row[7]),
            final_price_idr=0,
            note=row[8].strip() or None,
        ))
    return out


def parse_bs_tab(rows: list[list[str]]) -> list[CashoutRow]:
    """Schema BS: NAME|PROCESS|PNBP|URGENT|RPTKA/IMTA|MARGIN_BS|FINAL_PRICE"""
    out = []
    for i, row in enumerate(rows[2:], start=3):
        row = (row + [""] * 7)[:7]
        name = row[0].strip()
        if not name:
            continue
        out.append(CashoutRow(
            entity="BS",
            row_index=i,
            client_name=name,
            process=row[1].strip() or None,
            pnbp_idr=parse_idr(row[2]),
            urgent_idr=parse_idr(row[3]),
            rptka_imta_idr=parse_idr(row[4]),
            total_income_idr=0,
            margin_bs_idr=parse_idr(row[5]),
            margin_bz_idr=0,
            final_price_idr=parse_idr(row[6]),
            note=None,
        ))
    return out
```

### Idempotenza (per settimana, atomico)

```python
async def upsert_week(conn, week_start, tab_bz, tab_bs, rows_bz, rows_bs):
    async with conn.transaction():
        # Upsert settimana
        week_id = await conn.fetchval("""
            INSERT INTO owner_weekly_cashout_weeks
                (week_start, tab_name_bz, tab_name_bs, last_synced_at)
            VALUES ($1, $2, $3, now())
            ON CONFLICT (week_start) DO UPDATE SET
                tab_name_bz = EXCLUDED.tab_name_bz,
                tab_name_bs = EXCLUDED.tab_name_bs,
                last_synced_at = now()
            RETURNING id
        """, week_start, tab_bz, tab_bs)

        # Replace atomico delle righe
        await conn.execute(
            "DELETE FROM owner_weekly_cashout_rows WHERE week_id = $1", week_id
        )
        for r in rows_bz + rows_bs:
            await conn.execute("""
                INSERT INTO owner_weekly_cashout_rows
                    (week_id, entity, row_index, client_name, process,
                     pnbp_idr, urgent_idr, rptka_imta_idr, total_income_idr,
                     margin_bs_idr, margin_bz_idr, final_price_idr, note)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """, week_id, r.entity, r.row_index, r.client_name, r.process,
                r.pnbp_idr, r.urgent_idr, r.rptka_imta_idr, r.total_income_idr,
                r.margin_bs_idr, r.margin_bz_idr, r.final_price_idr, r.note)

        # Recompute totali
        await conn.execute("""
            UPDATE owner_weekly_cashout_weeks SET
                total_practices = (
                    SELECT COUNT(DISTINCT client_name)
                    FROM owner_weekly_cashout_rows
                    WHERE week_id = $1 AND entity = 'BZ'
                ),
                total_income_idr = (
                    SELECT COALESCE(SUM(total_income_idr), 0)
                    FROM owner_weekly_cashout_rows
                    WHERE week_id = $1 AND entity = 'BZ'
                ),
                total_margin_bz_idr = (
                    SELECT COALESCE(SUM(margin_bz_idr), 0)
                    FROM owner_weekly_cashout_rows
                    WHERE week_id = $1 AND entity = 'BZ'
                ),
                total_margin_bs_idr = (
                    SELECT COALESCE(SUM(margin_bs_idr), 0)
                    FROM owner_weekly_cashout_rows
                    WHERE week_id = $1 AND entity = 'BS'
                )
            WHERE id = $1
        """, week_id)
```

### Sync flow

```python
async def run_sync(triggered_by: str) -> SyncResult:
    log_id = await create_sync_log(triggered_by)
    weeks_processed = 0
    weeks_skipped = 0
    rows_upserted = 0
    unknown_tabs = []

    try:
        sheet_meta = await read_sheet_metadata(SHEET_ID)
        all_tabs = [s["properties"]["title"] for s in sheet_meta["sheets"]]

        # Group by week_start
        weeks: dict[date, dict] = {}
        for tab in all_tabs:
            if tab in JUNK_TABS:
                continue
            if tab not in TAB_TO_WEEK:
                unknown_tabs.append(tab)
                weeks_skipped += 1
                continue
            week_start = TAB_TO_WEEK[tab]
            entry = weeks.setdefault(week_start, {})
            if tab.startswith("BZ"):
                entry["bz"] = tab
            elif tab.startswith("BS"):
                entry["bs"] = tab

        for week_start, entry in sorted(weeks.items()):
            tab_bz = entry.get("bz")
            tab_bs = entry.get("bs")
            rows_bz = []
            rows_bs = []
            if tab_bz:
                raw = await read_range(SHEET_ID, f"{tab_bz}!A1:I200")
                rows_bz = parse_bz_tab(raw)
            if tab_bs:
                raw = await read_range(SHEET_ID, f"{tab_bs}!A1:G200")
                rows_bs = parse_bs_tab(raw)

            await upsert_week(conn, week_start, tab_bz, tab_bs, rows_bz, rows_bs)
            weeks_processed += 1
            rows_upserted += len(rows_bz) + len(rows_bs)

        if unknown_tabs:
            await alert_telegram(unknown_tabs)
            status = "partial"
        else:
            status = "success"

        await finalize_sync_log(log_id, status, weeks_processed,
                                weeks_skipped, rows_upserted, None)
        return SyncResult(status, weeks_processed, weeks_skipped, rows_upserted)

    except Exception as e:
        logger.exception("[CASHOUT] sync failed")
        await finalize_sync_log(log_id, "failed", weeks_processed,
                                weeks_skipped, rows_upserted, str(e))
        await alert_telegram_error(e)
        raise
```

### Cron schedule

**Air crontab:**
```
# Owner Cashout sync (Mondays 09:00 WITA)
0 9 * * 1 cd ~/Desktop/projects/nuzantara/apps/backend-rag && /usr/bin/env -S bash -c 'source venv/bin/activate && PYTHONPATH=. python scripts/sync_owner_cashout.py --triggered-by cron >> ~/logs/owner_cashout_sync.log 2>&1'
```

(Air gira con `venv` non `.venv` — vedi CLAUDE.md §14)

---

## API endpoints

Router file: `apps/backend-rag/backend/app/routers/hr_owner_cashout.py`
Mount path: `/api/hr/owner/cashout`
All routes guarded by `Depends(require_owner)`.

### `GET /api/hr/owner/cashout/overview`
Response:
```json
{
  "total_weeks": 22,
  "first_week": "2025-08-22",
  "last_week": "2026-01-30",
  "kpi": {
    "margin_bz_total_idr": 425000000,
    "margin_bz_last_week_idr": 18500000,
    "margin_bs_total_idr": 132000000,
    "practices_total": 487,
    "practices_last_week": 21
  },
  "trend": [
    {"week_start": "2025-08-22", "margin_bz": 18000000, "margin_bs": 6000000, "practices": 19},
    {"week_start": "2025-08-29", "margin_bz": 21000000, "margin_bs": 7200000, "practices": 23}
  ]
}
```

### `GET /api/hr/owner/cashout/weeks`
Lista settimane per la tabella overview.
```json
{
  "weeks": [
    {
      "id": 22,
      "week_start": "2026-01-30",
      "total_practices": 21,
      "total_income_idr": 87000000,
      "total_margin_bz_idr": 18500000,
      "total_margin_bs_idr": 5800000,
      "last_synced_at": "2026-04-07T02:00:00Z"
    }
  ]
}
```

### `GET /api/hr/owner/cashout/weeks/{id}`
Drill-down: dettaglio righe di una settimana.
```json
{
  "week": { "id": 22, "week_start": "2026-01-30", ... },
  "rows_bz": [
    {
      "client_name": "ANDREA ALEXANDRA G",
      "process": "BRIDGING VISA",
      "pnbp_idr": 1000000,
      "urgent_idr": 0,
      "rptka_imta_idr": 0,
      "total_income_idr": 4500000,
      "margin_bs_idr": 3000000,
      "margin_bz_idr": 500000,
      "note": null
    }
  ],
  "rows_bs": [...],
  "subtotals_by_process": [
    {"process": "C1", "count": 8, "margin_bz_idr": 5600000},
    {"process": "D12 1 YEAR", "count": 5, "margin_bz_idr": 8500000}
  ]
}
```

### `GET /api/hr/owner/cashout/visa-types`
Top visa types per margine BZ totale (per bar chart).
```json
{
  "top": [
    {"process": "D12 1 YEAR", "count": 87, "margin_bz_total_idr": 145000000},
    {"process": "C1", "count": 156, "margin_bz_total_idr": 98000000}
  ]
}
```

### `POST /api/hr/owner/cashout/sync`
Trigger manuale (bottone "Refresh now"). Response immediato 202 + sync in background task FastAPI.
```json
{ "status": "started", "log_id": 47 }
```

### `GET /api/hr/owner/cashout/sync-status`
Ultimo sync log.
```json
{
  "last_sync": {
    "id": 47,
    "started_at": "2026-04-07T02:00:00Z",
    "finished_at": "2026-04-07T02:00:08Z",
    "status": "success",
    "weeks_processed": 22,
    "weeks_skipped": 0,
    "rows_upserted": 487,
    "triggered_by": "cron"
  }
}
```

---

## Frontend (Next.js)

### File da creare
- `apps/mouth/src/app/(workspace)/hr/owner-cashout/page.tsx` (overview + tabella settimane)
- `apps/mouth/src/app/(workspace)/hr/owner-cashout/[weekId]/page.tsx` (drill-down)
- `apps/mouth/src/lib/api/hr/owner-cashout.ts` (typed fetch wrappers)
- `apps/mouth/src/types/owner-cashout.ts` (TS types)

### File da modificare
- `apps/mouth/src/app/(workspace)/hr/layout.tsx` — aggiungere voce sidebar "Owner Cashout" gated:
  ```tsx
  {OWNER_EMAILS.has(session?.user?.email ?? "") && (
    <SidebarLink href="/hr/owner-cashout" icon={<Lock />}>Owner Cashout</SidebarLink>
  )}
  ```

### Overview page layout
```
┌─────────────────────────────────────────────────────────────┐
│ Owner Cashout                            [🔄 Refresh] [⚙]   │
│ Last sync: 2026-04-07 02:00 (cron) — success                │
├─────────────────────────────────────────────────────────────┤
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐                │
│ │ MBZ    │ │ MBZ    │ │ MBS    │ │ Total  │                │
│ │ Total  │ │ Last W │ │ Total  │ │ Pratich│                │
│ │ 425M   │ │ 18.5M  │ │ 132M   │ │ 487    │                │
│ └────────┘ └────────┘ └────────┘ └────────┘                │
├─────────────────────────────────────────────────────────────┤
│ Margin trend (last 26 weeks)                                │
│ [Line chart: MBZ blue, MBS amber]                           │
├─────────────────────────────────────────────────────────────┤
│ Top visa types                                              │
│ [Horizontal bar chart, top 10]                              │
├─────────────────────────────────────────────────────────────┤
│ Weekly breakdown                          ↓ newest first    │
│ ┌───────────────────────────────────────────────────────┐  │
│ │ Week        │ Pratiche │ Income  │ MBZ    │ MBS   │ →│  │
│ │ 30 Jan 2026 │   21     │ 87M     │ 18.5M  │ 5.8M  │ →│  │
│ │ 23 Jan 2026 │   18     │ 75M     │ 16.2M  │ 5.1M  │ →│  │
│ └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Drill-down page layout
```
┌─────────────────────────────────────────────────────────────┐
│ ← Back   Week of 30 Jan 2026                                │
│          [Open in Google Sheets ↗]                          │
├─────────────────────────────────────────────────────────────┤
│ Subtotals by visa type                                      │
│ C1: 8 (5.6M)  D12 1Y: 5 (8.5M)  BRIDGING: 1 (0.5M)         │
├─────────────────────────────────────────────────────────────┤
│ Bali Zero (entity BZ)                                       │
│ ┌──────────────────────────────────────────────────────┐   │
│ │ Client            │ Visa     │ Income │ MBZ    │ ... │   │
│ │ ANDREA ALEXANDRA  │ BRIDGING │ 4.5M   │ 0.5M   │     │   │
│ │ PIERGIORGIO A.    │ C1       │ 2.3M   │ 0.7M   │     │   │
│ └──────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│ Bali Services (entity BS)                                   │
│ [stessa tabella, schema BS]                                 │
└─────────────────────────────────────────────────────────────┘
```

### Tech UI
- Recharts (già usato in progetto) per line/bar
- Tabelle Tailwind raw (no DataTable lib)
- Loading skeleton stile `payroll/page.tsx`
- IDR formatter già esistente in `hr/page.tsx`
- Colori: zinc bg + emerald per MBZ, amber per MBS

---

## Failure modes & rollback

| Failure | Behavior | Recovery |
|---|---|---|
| Sync cron fails | Telegram alert chat 1125336968, sync_log status=failed | UI mostra ultimo sync ok + bottone Retry |
| Tab nuova non in lookup | Sync continua sulle altre, status=partial, alert TG | Owner aggiunge entry a `TAB_TO_WEEK`, commit, manual sync |
| Parser eccezione su una riga | Riga loggata, week segnata partial, alert TG | Owner ispeziona log, fix sheet o parser |
| SA key revoked/expired | Sync fallisce, status=failed, alert TG | Rigenera SA key, aggiorna secret Air |
| Sheet ID cambiato | 404, fail loud | Owner aggiorna constant nel codice |
| DB rollback completo | `DELETE FROM owner_weekly_cashout_weeks` cascade | Re-run sync da zero, atomico |
| API 500 (DB up) | UI mostra error state, retry button disponibile | Retry, dati nel DB intatti |
| Postgres down | UI mostra error state | Restart Fly app, dati salvi in volume |

**Tabelle isolate:** zero foreign key verso `hr_employees`, `team_members`, `payroll_periods`. Drop sicuro.

---

## Monitoring

- **Telegram alerts** a chat `1125336968` (verificato live 2026-04-07):
  - Sync `failed` → ❌ con error
  - Sync `partial` con `unknown_tabs` → ⚠️ con lista
  - Sync `partial` con parser errors → ⚠️ con count
- **Health endpoint** `/api/hr/owner/cashout/sync-status` consultabile da `system_doctor.py` su Air
- **Log file Air** `~/logs/owner_cashout_sync.log` (rotation manuale, low volume)

---

## Implementation order

1. **Migration** `070_owner_weekly_cashout.sql` → upgrade + downgrade testati
2. **Owner dependency** `backend/app/dependencies/owner.py` + test
3. **Sync script** `scripts/sync_owner_cashout.py` con SA auth
4. **Test sync script** sulle 22 tab esistenti (dry-run mode con `--dry-run` flag, no DB writes, solo print)
5. **Run sync per davvero** in locale contro Postgres dev → verifica dati popolati correttamente
6. **API router** `hr_owner_cashout.py` + 6 endpoints + tests
7. **Mount router** in `router_registration.py`
8. **Frontend types** + API client
9. **Overview page**
10. **Drill-down page**
11. **Sidebar gating**
12. **Deploy backend** → smoke test endpoint con session owner
13. **Deploy frontend** + QA screenshot (CLAUDE.md §10)
14. **Carica SA key su Air** come secret env var
15. **Installa cron Air** + test manuale prima sync produzione
16. **Telegram alert test** (forza failure)

---

## Open questions

Nessuna. Tutte le decisioni sono state prese:
- Auth: SA esistente (verificato funzionante)
- Cadenza: cron settimanale lunedì + manual refresh
- Tab mapping: lookup hardcoded, alert TG su tab unknown
- Privacy: hardcoded `OWNER_EMAILS` set
- Schema: 3 tabelle isolate
- UI: overview + drill-down con metriche definite
