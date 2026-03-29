# Brainstorm Strategico: HR Module — Bali Zero

> **Data:** 2026-03-30
> **Autore:** Claude Code (Opus 4.6), sessione HR Strategy
> **Target:** kita.balizero.com/hr — modulo interno per ~10 team members, sede Bali
> **Riferimenti legali:** UU 13/2003 Ketenagakerjaan, UU HPP 7/2021, PP 58/2023 (TER),
> Perpres 64/2020 (BPJS Kes), PP 44/2015 + PP 46/2015 (BPJS TK), Permenaker 6/2016 (THR),
> SK Gub Bali 1021/03-M/HK/2025 (UMK Badung 2026)

---

## 1. Analisi Stato Attuale

### 1.1 Backend — COMPLETO e solido

| Componente       | Stato        | Dettagli                                                                        |
| ---------------- | ------------ | ------------------------------------------------------------------------------- |
| `hr.py` (router) | **COMPLETO** | 20 endpoint, RBAC admin/team, Pydantic models                                   |
| `hr_service.py`  | **COMPLETO** | Logica business per employees, bonuses, payroll, leave, dashboard               |
| `hr_utils.py`    | **COMPLETO** | PPh21 (progressive + TER simplified), BPJS (Kes+JHT+JKK+JKM+JP), THR, UMK, RBAC |
| Migration 068    | **COMPLETO** | 9 tabelle, 11 indici, 5 trigger (lock, validate, updated_at), seed data         |
| Test utils       | **COMPLETO** | 22 test (RBAC, PPh21, BPJS, THR, UMK) — tutti passing                           |
| Test router      | **PRESENTE** | Cache `.pyc` presente, file sorgente non trovato                                |

**Schema DB (9 tabelle):**

```
hr_employees ──→ team_members (FK)
hr_bonus_rates
hr_bonus_ledger ──→ hr_employees, practices, hr_payroll_periods, hr_bonus_rates
hr_payroll_periods
hr_payslips ──→ hr_payroll_periods, hr_employees
hr_deductions ──→ hr_payslips
hr_leave_types (seeded: 7 tipi UU 13/2003)
hr_leave_balances ──→ hr_employees, hr_leave_types
hr_leave_requests ──→ hr_employees, hr_leave_types
```

**Trigger di protezione (eccellenti):**

- `hr_validate_completed_practice`: bonus solo per pratiche completate
- `hr_enforce_period_lock`: payroll approvato → immutabile
- `hr_prevent_locked_payslip_mutation`: payslip in periodo locked → read-only

### 1.2 Frontend — FUNZIONANTE ma basico

| Pagina              | Stato           | Dettagli                                                                                                                          |
| ------------------- | --------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `/hr` (Dashboard)   | **FUNZIONANTE** | Admin: 4 stat cards (employees, pending bonuses, leave requests, current period). Team: 3 cards (bonuses, payslip, leave balance) |
| `/hr/bonuses`       | **FUNZIONANTE** | Lista bonus con status badge, approve button per admin                                                                            |
| `/hr/payroll`       | **FUNZIONANTE** | Admin: lista periodi + calculate + approve + mark-paid. Team: lista payslip                                                       |
| `/hr/leave`         | **FUNZIONANTE** | Lista richieste + bilancio ferie + approve/reject per admin                                                                       |
| `/hr/leave/request` | **FUNZIONANTE** | Form creazione richiesta (tipo, date, motivo, auto-calcolo giorni)                                                                |
| `/hr/settings`      | **FUNZIONANTE** | CRUD bonus rates (solo admin) — tabella practice_type ↔ importo                                                                   |
| Layout + Sidebar    | **FUNZIONANTE** | 5 voci nav, BZ accent tokens, active state                                                                                        |
| API lib (`hr.ts`)   | **FUNZIONANTE** | 15 funzioni API, tutte tipizzate come `any`                                                                                       |

### 1.3 Mappa Completamento

```
BACKEND ████████████████████ 100% — Completo, testato, production-ready
FRONTEND █████████████░░░░░░░  65% — Funzionante ma grezzo (no types, no empty states ricchi, no detail views)
COMPLIANCE ████████████████░░░░  80% — BPJS e PPh21 base corretti, manca TER reale e THR in payroll
ANALYTICS ░░░░░░░░░░░░░░░░░░░░   0% — Nessun grafico, trend, o KPI
INTEGRATIONS ░░░░░░░░░░░░░░░░░░░░   0% — Zero sinergia con CRM/Portal
```

---

## 2. Pain Points & Gap

### 2.1 Gap Normativi (Indonesia-specifici)

| Gap                                   | Severita | Dettaglio                                                                                                                                                                         |
| ------------------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **PPh21 TER reale mancante**          | ALTA     | `hr_utils.py` usa annualizzazione/12 semplificata. PP 58/2023 richiede lookup table TER con 44 bracket × 3 categorie PTKP. La differenza di calcolo puo arrivare a ±200K IDR/mese |
| **THR non integrato in payroll**      | ALTA     | `calculate_thr()` esiste in utils ma non viene chiamato da `calculate_payroll()`. THR dovrebbe essere aggiunto automaticamente nel mese di Lebaran/Natale                         |
| **BPJS JP cap non aggiornato**        | MEDIA    | Cap attuale `10_042_300` e del 2025. BPJS TK aggiorna annualmente — serve meccanismo di update                                                                                    |
| **Rapporto Bulanan BPJS (e-billing)** | MEDIA    | Non c'e export per il reporting mensile BPJS da inviare tramite SIPP/eBilling                                                                                                     |
| **PPh21 Dec reconciliation**          | MEDIA    | Nessun endpoint per la riconciliazione annuale (diff tra TER mensile e progressivo annuale). Obbligatorio a dicembre.                                                             |
| **Lembur (straordinario)**            | BASSA    | Nessun tracciamento overtime. UU 13/2003 Pasal 78: max 4h/giorno, 18h/settimana. Rate: 1.5x prima ora, 2x successive                                                              |
| **UMK validation mancante**           | BASSA    | `validate_minimum_wage()` esiste ma non viene chiamata in `upsert_employee()` — un admin puo inserire salario sotto UMK                                                           |

### 2.2 Gap Funzionali

| Gap                             | Severita | Dettaglio                                                                                                                                                    |
| ------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Zero employee management UI** | ALTA     | Nessuna pagina per visualizzare/aggiungere/modificare dipendenti. L'unico modo e via API diretta                                                             |
| **Payslip detail assente**      | ALTA     | Team member vede solo riga sintetica. Nessuna vista con breakdown BPJS, PPh21, bonus, deduzioni. Backend endpoint `GET /payslips/{id}` esiste ma non e usato |
| **Nessun export/download**      | MEDIA    | Nessun PDF payslip, nessun CSV export per contabilita                                                                                                        |
| **Leave calendar mancante**     | MEDIA    | Nessuna vista calendario delle ferie team — solo lista. Il manager non vede overlap                                                                          |
| **Notifiche assenti**           | MEDIA    | Nessuna notifica Telegram/email per: leave approved/rejected, payroll calculated, bonus awarded                                                              |
| **Audit trail leggero**         | BASSA    | Solo `approved_by` + `approved_at`. Nessuno storico delle modifiche                                                                                          |
| **TypeScript types mancanti**   | BASSA    | Tutta la API lib usa `any` — 0 type safety                                                                                                                   |

### 2.3 Gap UX

| Gap                          | Impatto | Dettaglio                                                                                            |
| ---------------------------- | ------- | ---------------------------------------------------------------------------------------------------- |
| **`alert()` per errori**     | ALTO    | Bonuses, payroll, leave usano `alert()` nativo del browser per errori. Deve diventare toast (sonner) |
| **`prompt()` per rejection** | ALTO    | Leave rejection usa `prompt()` nativo. Serve un dialog modale                                        |
| **Nessun mobile nav**        | MEDIO   | Sidebar HR e `hidden md:block` — su mobile non c'e navigazione                                       |
| **Loading state piatto**     | BASSO   | Skeleton loader presenti ma generici (rettangoli grigi). Non rappresentano il layout reale           |

---

## 3. Miglioramenti Proposti

### P0: Completare Scaffold (1-2 settimane)

> Obiettivo: ogni pagina HR funziona correttamente, nessun `alert()`, TypeScript tipizzato.

**P0.1 — Employees Page (`/hr/employees`)**
Nuova pagina admin con:

- Tabella dipendenti (nome, email, ruolo, salario, BPJS status, hire date)
- Form aggiunta/modifica dipendente (dialog o sheet)
- Badge: attivo/inattivo, UMK compliance (verde/rosso se sotto minimo)
- Quick action: attiva/disattiva dipendente

**P0.2 — Payslip Detail (`/hr/payroll/[slipId]`)**
Nuova pagina (o sheet) con:

- Header: nome dipendente, mese/anno, status periodo
- Breakdown:
  - Gaji Pokok (base salary)
  - Bonus (lista dettagliata per pratica)
  - Deduzioni dipendente: BPJS Kes (1%), JHT (2%), JP (1%), PPh21
  - Contributi datore: BPJS Kes (4%), JHT (3.7%), JKK (0.24%), JKM (0.30%), JP (2%)
  - Net salary
- Download PDF (futuro P1)

**P0.3 — TypeScript Types**
Creare `apps/mouth/src/types/hr.ts` con:

```typescript
interface HREmployee { id: number; team_member_id: string; full_name: string; email: string; ... }
interface Bonus { id: number; practice_type_code: string; amount_idr: number; status: BonusStatus; ... }
interface PayrollPeriod { id: number; payroll_month: number; payroll_year: number; status: PayrollStatus; ... }
interface Payslip { id: number; base_salary_idr: number; bonus_total_idr: number; ... }
interface LeaveRequest { id: number; leave_type_name: string; start_date: string; ... }
interface LeaveBalance { id: number; leave_type_name: string; allocated_days: number; ... }
```

Eliminare tutti i `any` dalla API lib e dai componenti.

**P0.4 — UX Fix**

- Sostituire `alert()` con `toast` (sonner, gia installato in mouth)
- Sostituire `prompt()` (leave rejection) con `AlertDialog` Radix
- Aggiungere mobile nav (hamburger menu o bottom tabs per HR)
- Empty state con illustrazione e CTA per ogni sezione

**P0.5 — Sidebar: aggiungere "Employees" e "Calendar"**

```typescript
const navItems = [
  { href: "/hr", label: "Dashboard", icon: LayoutDashboard },
  { href: "/hr/employees", label: "Employees", icon: Users }, // NUOVO
  { href: "/hr/bonuses", label: "Bonuses", icon: Gift },
  { href: "/hr/payroll", label: "Payroll", icon: Banknote },
  { href: "/hr/leave", label: "Leave", icon: Calendar },
  { href: "/hr/leave/calendar", label: "Calendar", icon: CalendarDays }, // NUOVO
  { href: "/hr/settings", label: "Settings", icon: Settings },
];
```

### P1: Compliance Indonesia (2-4 settimane)

> Obiettivo: payroll legalmente corretto per diritto del lavoro indonesiano.

**P1.1 — PPh21 TER Reale (PP 58/2023)**
Implementare la tabella TER effettiva con:

- 3 categorie PTKP (A: TK/0-TK/1, B: TK/2-TK/3-K/0-K/1, C: K/2-K/3)
- 44 bracket di reddito mensile lordo per categoria
- Lookup diretto (non annualizzazione/12)
- Reconciliation dicembre: confronto TER cumulato vs progressivo annuale
- Nuovo endpoint: `GET /api/hr/pph21/reconciliation?year=2026`

**P1.2 — THR in Payroll**
Modificare `calculate_payroll()`:

- Parametro opzionale `include_thr: bool`
- Se attivo: calcola THR per ogni dipendente e aggiunge a `thr_idr` in payslip
- Nuova riga deduction type `'thr'` (non e una deduzione, ma un'aggiunta — campo separato gia nel schema)
- UI: checkbox "Include THR" nel calcolo payroll di marzo/aprile (Lebaran) e dicembre (Natale)
- Calcolo: `calculate_thr(salary, hire_date)` gia implementato

**P1.3 — BPJS Reporting**
Nuovo endpoint: `GET /api/hr/reports/bpjs?month=&year=`
Output:

```json
{
  "period": "03/2026",
  "total_employees": 10,
  "kesehatan": { "employer_total": 4_800_000, "employee_total": 1_200_000, "grand_total": 6_000_000 },
  "jht": { ... },
  "jkk": { ... },
  "jkm": { ... },
  "jp": { ... },
  "employees": [{ "name": "...", "npwp": "...", "bpjs_kes_no": "...", "contributions": { ... } }]
}
```

Export CSV/Excel per upload su SIPP BPJS.

**P1.4 — Lembur (Overtime)**
Nuove tabelle e endpoint:

```sql
hr_overtime_entries (
    id, employee_id, work_date, start_time, end_time,
    total_hours NUMERIC(4,2), rate_multiplier NUMERIC(3,2),
    amount_idr BIGINT, status, approved_by
)
```

Calcolo: UU 13/2003 Pasal 78 — 1.5x prima ora, 2x successive.
Integrazione payroll: overtime incluso in `allowance_total_idr` (campo gia presente nello schema).

**P1.5 — UMK Validation**
Aggiungere check in `upsert_employee()`:

```python
if not validate_minimum_wage(data["base_salary_idr"]):
    raise ValueError(f"Salary below UMK Badung 2026: Rp {UMK_BADUNG_2026:,}")
```

Con override admin esplicito (flag `force_below_umk: bool` per casi speciali come part-time).

### P2: Feature Avanzate (1-2 mesi)

**P2.1 — Leave Calendar**
Vista calendario mensile che mostra:

- Chi e in ferie (barre colorate per tipo leave)
- Overlap visualizzato (2+ persone assenti = warning)
- Click su giorno → lista assenti con dettaglio
- Integrazione con calendar.balizero.com (Google Calendar SA)

**P2.2 — Payslip PDF**
Generazione PDF lato server con:

- Template professionale Bali Zero branded
- Header: logo, periodo, nome azienda
- Breakdown completo (come P0.2 ma in PDF)
- Firma digitale admin (opzionale)
- Download individuale + batch (tutti i payslip del mese in ZIP)
- Libreria suggerita: `weasyprint` o `reportlab` (Python)

**P2.3 — Dashboard Analytics**
Widget dashboard admin:

- **Trend payroll**: grafico linea 12 mesi (totale netto, contributi BPJS, PPh21)
- **Distribuzione salari**: istogramma per fasce (UMK → 2x UMK → 3x → ...)
- **Leave consumption**: % utilizzo ferie annuali per dipendente (barra)
- **Bonus leaderboard**: top earner bonus del mese (per motivazione team)
- **Cost projection**: stima costo aziendale totale prossimi 3 mesi (salary + BPJS employer + THR proiezione)

**P2.4 — Org Chart**
Visualizzazione gerarchica del team:

- Tree view: Owner → Manager → Agent
- Click su nodo → card con: ruolo, pratiche attive, ferie residue, ultimo payslip
- Usa dati da CRM `clients.assigned_to` per mostrare carico

**P2.5 — Notifiche Automatiche**
Integrazione con canali esistenti:

- **Telegram** (via `TelegramBotService`): notifica su leave approve/reject, payroll calculated
- **Email** (via `send_email`): payslip mensile con PDF allegato
- **Portal** (my.balizero.com): status team member "In ferie fino al [data]"

**P2.6 — Time Tracking (Presenze)**
Se necessario in futuro:

```sql
hr_attendance (
    id, employee_id, date, clock_in TIMESTAMPTZ, clock_out TIMESTAMPTZ,
    status VARCHAR(20), -- present, absent, half_day, remote
    location_lat NUMERIC, location_lng NUMERIC, -- geo-fence Bali Zero office
    notes TEXT
)
```

MCP tool `clock_in` / `clock_out` gia esistenti nel nuzantara-mcp — collegarli.

---

## 4. Visione UX/UI

### Principi Guida

Questo e un **tool interno usato quotidianamente** da ~10 persone. Non deve essere bello da vetrina —
deve essere **efficiente, veloce, zero-friction**:

- **1-click actions**: approve/reject con un click, no modal di conferma per azioni reversibili
- **Keyboard shortcuts**: `A` approve, `R` reject sulla riga selezionata (power user)
- **Inline editing**: bonus rates editabili inline (gia implementato, buon pattern)
- **Batch actions**: seleziona multipli bonus → approve all
- **Zero page reload**: mutazioni optimistiche (update state prima della risposta API)

### Design Tokens (Warm Depth)

```css
/* Gia definiti in bz-tokens.css */
--bz-base: #0c0c0e; /* Background principale */
--bz-accent: #d4845a; /* Accent terracotta */

/* Palette HR specifica (da definire) */
--hr-salary: #22c55e; /* Verde — importi positivi */
--hr-deduction: #ef4444; /* Rosso — deduzioni */
--hr-pending: #f59e0b; /* Ambra — in attesa */
--hr-approved: #3b82f6; /* Blu — approvato */
--hr-paid: #22c55e; /* Verde — pagato */
```

### Layout Pagine Chiave

**Dashboard Admin:**

```
┌─────────────────────────────────────────────────────────┐
│ HR Dashboard                            March 2026      │
├─────────┬─────────┬──────────┬─────────────────────────┤
│ 10      │ 3       │ 2        │ Calculated              │
│ Employees│ Pending │ Leave    │ March 2026              │
│         │ Bonuses │ Requests │ Rp 85.000.000           │
├─────────┴─────────┴──────────┴─────────────────────────┤
│ Pending Actions                              [View All] │
│ ┌─ Leave: Damar requests 3 days Annual (Apr 5-7) [A][R]│
│ ├─ Bonus: Asya — PT PMA — Rp 1.500.000        [Approve]│
│ └─ Payroll: March 2026 ready for approval    [Approve] │
├─────────────────────────────────────────────────────────┤
│ Payroll Trend (12 months)                    [linechart]│
│ ████████████████████████████████████████████            │
└─────────────────────────────────────────────────────────┘
```

**Payslip Detail:**

```
┌─────────────────────────────────────────────────────────┐
│ ← Payroll    Payslip — Damar Wijaya — March 2026       │
├─────────────────────────────────────────────────────────┤
│ PENDAPATAN                                              │
│   Gaji Pokok ................................ Rp 10.000.000│
│   Bonus (2x practices) .................... Rp  1.350.000│
│   Lembur ................................... Rp    450.000│
│                                         ─────────────── │
│   Total Bruto .............................. Rp 11.800.000│
├─────────────────────────────────────────────────────────┤
│ POTONGAN KARYAWAN                                       │
│   BPJS Kesehatan (1%) ..................... Rp    118.000│
│   BPJS JHT (2%) ........................... Rp    236.000│
│   BPJS JP (1%) ............................ Rp    100.423│
│   PPh 21 (TER) ............................ Rp    295.000│
│                                         ─────────────── │
│   Total Potongan ........................... Rp    749.423│
├─────────────────────────────────────────────────────────┤
│ KONTRIBUSI PERUSAHAAN (info)                            │
│   BPJS Kes (4%) ........... Rp 472.000                  │
│   BPJS JHT (3.7%) ........ Rp 436.600                  │
│   BPJS JKK (0.24%) ....... Rp  28.320                  │
│   BPJS JKM (0.30%) ....... Rp  35.400                  │
│   BPJS JP (2%) ........... Rp 200.846                  │
├─────────────────────────────────────────────────────────┤
│ GAJI BERSIH               Rp 11.050.577                │
│                                      [Download PDF]     │
└─────────────────────────────────────────────────────────┘
```

---

## 5. Modifiche Backend Necessarie

### 5.1 Nuovi Endpoint

| Endpoint                           | Metodo    | Descrizione                               | Priorita |
| ---------------------------------- | --------- | ----------------------------------------- | -------- |
| `GET /api/hr/employees`            | Esistente | gia funzionante                           | —        |
| `GET /api/hr/employees/{id}`       | Esistente | gia funzionante                           | —        |
| `POST /api/hr/employees`           | Esistente | aggiungere UMK validation                 | P1       |
| `GET /api/hr/payslips/{id}`        | Esistente | gia funzionante, connettere a frontend    | P0       |
| `GET /api/hr/pph21/reconciliation` | **NUOVO** | Reconciliation annuale TER vs progressivo | P1       |
| `GET /api/hr/reports/bpjs`         | **NUOVO** | Report BPJS mensile con dettaglio         | P1       |
| `GET /api/hr/reports/bpjs/export`  | **NUOVO** | CSV/Excel export per SIPP                 | P1       |
| `POST /api/hr/payroll/calculate`   | Esistente | aggiungere `include_thr` flag             | P1       |
| `GET /api/hr/leave/calendar`       | **NUOVO** | Vista calendario ferie team               | P2       |
| `GET /api/hr/payslips/{id}/pdf`    | **NUOVO** | PDF download payslip                      | P2       |
| `GET /api/hr/analytics/trends`     | **NUOVO** | Payroll trend 12 mesi                     | P2       |
| `POST /api/hr/overtime`            | **NUOVO** | Registra overtime                         | P2       |
| `GET /api/hr/overtime`             | **NUOVO** | Lista overtime entries                    | P2       |

### 5.2 Schema Changes

**Migration 069 — TER lookup table:**

```sql
CREATE TABLE IF NOT EXISTS hr_pph21_ter (
    id SERIAL PRIMARY KEY,
    category CHAR(1) NOT NULL CHECK (category IN ('A','B','C')),
    bracket_min BIGINT NOT NULL,
    bracket_max BIGINT NOT NULL,
    rate NUMERIC(6,4) NOT NULL,
    effective_year SMALLINT NOT NULL DEFAULT 2024,
    CONSTRAINT uq_ter_bracket UNIQUE (category, bracket_min, effective_year)
);
-- Seed con 44 bracket × 3 categorie = 132 righe (da PP 58/2023 Lampiran)
```

**Migration 070 — Overtime:**

```sql
CREATE TABLE IF NOT EXISTS hr_overtime_entries (
    id BIGSERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES hr_employees(id),
    work_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    total_hours NUMERIC(4,2) NOT NULL CHECK (total_hours > 0 AND total_hours <= 4),
    rate_multiplier NUMERIC(3,2) NOT NULL DEFAULT 1.5,
    amount_idr BIGINT NOT NULL CHECK (amount_idr >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    approved_by VARCHAR(36) REFERENCES team_members(id),
    approved_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_overtime_emp_date UNIQUE (employee_id, work_date),
    CONSTRAINT ck_overtime_status CHECK (status IN ('pending','approved','rejected','paid'))
);
```

### 5.3 Modifiche Servizio Esistente

**`hr_service.py` — `calculate_payroll()` modifiche:**

1. Aggiungere parametro `include_thr: bool = False`
2. Se `include_thr`: calcolare THR per ogni employee e popolare `thr_idr` nel payslip
3. Includere overtime approvato in `allowance_total_idr`
4. Usare TER reale (lookup da `hr_pph21_ter`) invece di annualizzazione/12

**`hr_utils.py` — Nuova funzione:**

```python
async def calculate_pph21_ter(
    monthly_gross: int,
    ptkp_status: str,
    db_pool: asyncpg.Pool,
) -> int:
    """PPh21 with actual TER table lookup (PP 58/2023)."""
    category = ptkp_to_ter_category(ptkp_status)
    # Query hr_pph21_ter for matching bracket
    ...
```

---

## 6. Punti di Sinergia

### 6.1 HR ↔ CRM

**Dati CRM utili per HR:**

| Dato CRM                             | Uso HR                          | Implementazione                                                                               |
| ------------------------------------ | ------------------------------- | --------------------------------------------------------------------------------------------- |
| `clients.assigned_to` (email)        | Carico di lavoro per dipendente | Query: `SELECT assigned_to, COUNT(*) FROM clients WHERE status='active' GROUP BY assigned_to` |
| `practices` attive per `assigned_to` | Bonus auto-calculation trigger  | Trigger DB: pratica completata → `INSERT INTO hr_bonus_ledger`                                |
| Tempo risposta medio per team member | Performance review data         | Log da `conversation_sessions.created_at` → risposta                                          |
| Numero clienti serviti / completati  | KPI per review annuale          | Aggregato da practices completate                                                             |

**Flusso Bonus Automatico (gia previsto ma non wired):**

```
Practice status → 'completed'
  → DB trigger hr_validate_completed_practice (esiste!)
  → INSERT INTO hr_bonus_ledger con amount da hr_bonus_rates
  → Frontend mostra in /hr/bonuses con status 'pending'
  → Admin approva → incluso in prossimo payroll
```

Questo flusso e gia architetturalmente pronto (trigger + schema). Manca solo il **trigger INSERT**
che crea la riga bonus quando una pratica viene completata. Va aggiunto in `practices` table
o nel service CRM che aggiorna lo status.

**Dashboard HR con metriche CRM:**

```
┌─────────────────────────────────────────┐
│ Team Performance (from CRM)             │
│ ┌───────────────┬────────┬────────────┐ │
│ │ Team Member   │ Active │ Completed  │ │
│ │               │ Clients│ This Month │ │
│ ├───────────────┼────────┼────────────┤ │
│ │ Damar         │ 45     │ 8          │ │
│ │ Asya          │ 38     │ 12         │ │
│ │ Vino          │ 52     │ 6          │ │
│ └───────────────┴────────┴────────────┘ │
└─────────────────────────────────────────┘
```

### 6.2 HR ↔ Portal (my.balizero.com)

**Impatto diretto sul cliente:**

| Scenario              | Stato attuale       | Stato target                                                                                  |
| --------------------- | ------------------- | --------------------------------------------------------------------------------------------- |
| Team member in ferie  | Cliente non sa      | Portal mostra "Your contact [nome] is on leave until [data]. [nome alternativo] is covering." |
| Team member assegnato | `assigned_to` email | Portal mostra card con foto, nome, ruolo, status (online/leave/busy)                          |
| Tempo di risposta     | Non tracciato       | Portal mostra "Average response time: 2h"                                                     |

**Implementazione:**

```
GET /api/portal/team-member-status?email=damar@balizero.com
→ {
    "name": "Damar Wijaya",
    "status": "on_leave",           // from hr_leave_requests active today
    "leave_until": "2026-04-07",    // end_date from approved leave
    "cover_by": "Asya Putri",       // backup assignment
    "avg_response_hours": 2.3       // from conversation metrics
  }
```

Il portal `my.balizero.com` gia mostra `assigned_to` nella sezione practices.
Aggiungere badge colorato:

- Verde: disponibile
- Giallo: in ferie ma coperto
- Grigio: weekend/fuori orario

### 6.3 Componenti Condivisi

| Componente        | Usato in                                                                         | Pattern                                         |
| ----------------- | -------------------------------------------------------------------------------- | ----------------------------------------------- |
| `StatusBadge`     | HR (bonus/payroll/leave status), CRM (practice status), Portal (document status) | `<StatusBadge status="pending" variant="hr" />` |
| `EmployeeCard`    | HR (employee list), CRM (assigned_to preview), Portal (contact card)             | `<EmployeeCard email="..." showLeaveStatus />`  |
| `ApprovalActions` | HR (bonus/leave/payroll approve), CRM (practice approval futuro)                 | `<ApprovalActions onApprove onReject />`        |
| `IDRAmount`       | HR (salari, bonus), CRM (pricing), Portal (fatture)                              | `<IDRAmount value={10000000} size="lg" />`      |
| `DateRangePicker` | HR (leave request), CRM (practice dates), Calendar                               | Gia in shadcn/ui                                |
| `MonthYearPicker` | HR (payroll period), Analytics (filtro mese)                                     | Custom component                                |

---

## 7. Roadmap Implementazione

### Fase 1: P0 — Completare Scaffold (Settimana 1-2)

```
Settimana 1:
├── Giorno 1-2: TypeScript types (hr.ts) + refactor API lib (remove `any`)
├── Giorno 3: /hr/employees page (lista + form aggiunta)
├── Giorno 4: Payslip detail view (breakdown BPJS/PPh21)
└── Giorno 5: UX fixes (toast, dialog, mobile nav, empty states)

Settimana 2:
├── Giorno 1: Leave calendar view (griglia mensile)
├── Giorno 2: Dashboard migliorato (pending actions con 1-click approve)
├── Giorno 3: Batch actions (approve multipli bonus)
├── Giorno 4: Frontend tests (componenti chiave)
└── Giorno 5: QA + deploy
```

### Fase 2: P1 — Compliance Indonesia (Settimana 3-6)

```
Settimana 3:
├── PPh21 TER table implementation (migration + utils + tests)
└── THR integration in payroll calculate

Settimana 4:
├── BPJS monthly report endpoint + CSV export
├── UMK validation in employee upsert
└── PPh21 December reconciliation endpoint

Settimana 5:
├── Overtime schema + endpoints + frontend
└── Auto-bonus trigger (practice completed → bonus ledger)

Settimana 6:
├── Integration tests (full payroll cycle)
├── Red team review (Gemini) — compliance verification
└── Deploy + production validation
```

### Fase 3: P2 — Feature Avanzate (Settimana 7-12)

```
Settimana 7-8:
├── Payslip PDF generation (backend)
├── Download individual + batch ZIP
└── Email payslip automatico (via Brevo)

Settimana 9-10:
├── Dashboard analytics (payroll trend, salary distribution, leave consumption)
├── Org chart component
└── CRM performance data integration

Settimana 11-12:
├── Portal integration (team member status, leave visibility)
├── Telegram notifications (leave approve, payroll ready)
├── Time tracking scaffold (if needed)
└── Final QA + documentation
```

### Dipendenze Critiche

```
P0 → Nessuna dipendenza esterna. Solo frontend.
P1 → PP 58/2023 TER table (132 righe di dati da regolamento ufficiale)
P1 → BPJS JP cap 2026 (da verificare sul sito BPJS TK)
P2 → weasyprint/reportlab (nuova dipendenza Python per PDF)
P2 → Google Calendar SA (per leave calendar sync)
P2 → Portal refactor (aggiungere team member status)
```

---

## Appendice: Checklist Compliance Indonesia

| Requisito                                     | Status   | Note                                 |
| --------------------------------------------- | -------- | ------------------------------------ |
| PPh21 calcolo mensile (TER PP 58/2023)        | PARZIALE | Simplified, non TER reale            |
| PPh21 reconciliation annuale                  | MANCANTE | Obbligatorio a dicembre              |
| BPJS Kesehatan 5% (4% employer + 1% employee) | OK       | Cap 12M implementato                 |
| BPJS JHT 5.7% (3.7% + 2%)                     | OK       | Nessun cap                           |
| BPJS JKK 0.24% (employer)                     | OK       | Risk class I                         |
| BPJS JKM 0.30% (employer)                     | OK       |                                      |
| BPJS JP 3% (2% + 1%)                          | OK       | Cap 10.042.300 (2025)                |
| THR (Permenaker 6/2016)                       | PARZIALE | Calcolo OK, non integrato in payroll |
| Cuti tahunan 12 hari (UU 13/2003 Pasal 79)    | OK       | Seeded in leave_types                |
| Cuti sakit (UU 13/2003)                       | OK       | 0 default, document required         |
| Cuti melahirkan 90 hari                       | OK       | Seeded                               |
| Cuti nikah 3 hari                             | OK       | Seeded                               |
| Cuti duka 2 hari                              | OK       | Seeded                               |
| UMK Badung 2026: Rp 3.791.003                 | PRESENTE | Non validato in upsert               |
| Lembur max 4h/hari (UU 13/2003 Pasal 78)      | MANCANTE | No overtime tracking                 |
| E-billing BPJS (SIPP)                         | MANCANTE | No export                            |
| Slip gaji (wajib)                             | MANCANTE | No PDF generation                    |
