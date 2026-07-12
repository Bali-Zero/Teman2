# HR Module P1/P2 Implementation Plan

> **Data:** 2026-03-31
> **Versione:** 2.0 (FINAL — post review round 2: DeepSeek R1 + Gemini Search + Claude CLI)
> **Target:** kita.balizero.com/hr — ~10 team members, Bali
> **Vincoli:** Fly.io 2GB RAM, auto_stop, PostgreSQL, asyncpg

---

## Review Round 2 — Correzioni Applicate

| Finding                                                                 | Fonte                                    | Azione                                                                                          |
| ----------------------------------------------------------------------- | ---------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Race condition: 2 admin calcolano payroll simultaneamente               | DeepSeek R1                              | **AGGIUNTO** `FOR UPDATE` lock su employee row in calculate_payroll()                           |
| THR incluso nel grosso mensile per TER (NON tassazione separata)        | Gemini Search (PP 58/2023 > PMK-16/2016) | **CORRETTO** — THR si somma a salary nel mese di pagamento, TER si applica sul totale           |
| Overtime base = salary + tunjangan tetap (non solo salary)              | Gemini Search (PP 35/2021)               | **CORRETTO** — 1/173 × (base_salary + fixed_allowances)                                         |
| SIPP CSV ha ~6 campi standard (non 20)                                  | Gemini Search                            | **SEMPLIFICATO** — NPP, periodo, KPJ, nome, upah, status                                        |
| Mid-year employee: TER normale dal mese di ingresso, true-up a dicembre | Gemini Search (PMK-168/2023)             | **CONFERMATO** — nessuna logica speciale per primo mese parziale                                |
| Cumulative PPh21 table dedicata                                         | DeepSeek R1                              | **RIFIUTATO** — per 10 dipendenti la query derivata da payslips e sufficiente (NB-1 confermato) |

---

## Agenti Consultati

| Agente            | Ruolo                    | Contributo                                                                               |
| ----------------- | ------------------------ | ---------------------------------------------------------------------------------------- |
| DeepSeek R1 671b  | Reasoning architetturale | Sequenza fasi, migration strategy, feature flag, risk mitigation                         |
| Gemini 2.5 Pro    | Ricerca normativa        | TER table PMK-168/2023, BPJS JP cap 2026, overtime 1/173 formula, THR penalita           |
| NB-1 (NotebookLM) | Validazione architettura | **BOCCIATO TER in DB** — deve essere in-memory constants. Confermato lock check overtime |

---

## Correzioni Post-Validazione

| Proposta Originale                   | Verdetto NB-1 | Correzione                                                                            |
| ------------------------------------ | ------------- | ------------------------------------------------------------------------------------- |
| TER rates in DB table `hr_pph21_ter` | ❌ BOCCIATA   | Hardcode in `hr_utils.py` come costanti Python (pattern identico a `PPH21_BRACKETS`)  |
| BPJS JP cap `10_042_300`             | ⚠️ OBSOLETO   | Aggiornare a `10_547_400` (cap Mar 2025 - Feb 2026)                                   |
| Overtime insert senza check          | ⚠️ RISCHIO    | Validare `payroll_period.status != 'approved'` prima di inserire overtime retroattivo |

---

## Fase 1A: Low-Risk Foundations (Settimana 1)

### 1A.1 — BPJS JP Cap Update

**File:** `apps/backend-rag/backend/app/utils/hr_utils.py`

```python
# PRIMA
BPJS_JP_SALARY_CAP = 10_042_300  # 2025 cap

# DOPO
BPJS_JP_SALARY_CAP = 10_547_400  # Mar 2025 - Feb 2026 (BPJS TK update)
```

**Test:** Aggiornare `test_hr_utils.py::TestBPJS::test_jp_cap` con nuovo valore.

### 1A.2 — UMK Validation in Employee Upsert

**File:** `apps/backend-rag/backend/app/services/hr/hr_service.py` → `upsert_employee()`

```python
async def upsert_employee(self, data: dict[str, Any]) -> dict[str, Any]:
    if not validate_minimum_wage(data["base_salary_idr"]):
        msg = f"Salary Rp {data['base_salary_idr']:,} is below UMK Badung 2026 (Rp {UMK_BADUNG_2026:,})"
        raise ValueError(msg)
    # ... existing upsert logic
```

**Override:** Aggiungere `force_below_umk: bool = False` al Pydantic model per casi part-time.

### 1A.3 — THR Integration in Payroll

**File:** `apps/backend-rag/backend/app/services/hr/hr_service.py` → `calculate_payroll()`
**File:** `apps/backend-rag/backend/app/routers/hr.py` → `PayrollCalculateRequest`

Aggiungere a `PayrollCalculateRequest`:

```python
class PayrollCalculateRequest(BaseModel):
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2100)
    include_thr: bool = False
```

In `calculate_payroll()`, dopo il calcolo bonus:

```python
thr_amount = 0
if include_thr:
    thr_amount = calculate_thr(salary, emp["hire_date"], period_end)

# THR is INCLUDED in monthly gross for TER calculation (PP 58/2023)
# The month where THR is paid uses TER on (salary + bonus + thr)
taxable_gross = salary + bonus_total + thr_amount + overtime_total

# Payslip insert: thr_idr = thr_amount (campo gia presente nello schema)
```

**Nota:** Campo `thr_idr` gia esiste in `hr_payslips` (migration 068). Nessuna migration necessaria.
**IMPORTANTE (Gemini Search):** THR NON ha tassazione separata. Si somma al grosso mensile e il TER si applica sul totale. PP 58/2023 supercede PMK-16/2016.

### 1A.4 — BPJS Monthly Report Endpoint

**File:** `apps/backend-rag/backend/app/routers/hr.py` — nuovo endpoint

```python
@router.get("/reports/bpjs")
async def export_bpjs_report(
    month: int = Query(ge=1, le=12),
    year: int = Query(ge=2000),
    format: str = Query("json", regex="^(json|csv)$"),
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    _require_hr_admin(current_user)
    service = _get_hr_service(db_pool)
    report = await service.generate_bpjs_report(month, year)
    if format == "csv":
        return StreamingResponse(...)  # CSV per SIPP upload
    return report
```

**Service:** Nuovo metodo `generate_bpjs_report()` che aggrega contributi per dipendente.

---

## Fase 1B: PPh21 TER (Settimana 2-3)

### 1B.1 — TER Constants in hr_utils.py

**File:** `apps/backend-rag/backend/app/utils/hr_utils.py`

Aggiungere dopo `PPH21_BRACKETS`:

```python
# ─── PPh21 TER (PP 58/2023, PMK-168/2023) ────────────────────────────
# Effective Jan 2024. Used for monthly withholding (Jan-Nov).
# December uses annual progressive (calculate_pph21_annual).
#
# Category A: TK/0, TK/1, K/0
# Category B: TK/2, TK/3, K/1, K/2
# Category C: K/3
#
# Format: list of (upper_bound_idr, rate)
# Rate is a decimal (e.g., 0.0025 = 0.25%)

PTKP_TO_TER_CATEGORY: dict[str, str] = {
    "TK/0": "A", "TK/1": "A", "K/0": "A",
    "TK/2": "B", "TK/3": "B", "K/1": "B", "K/2": "B",
    "K/3": "C",
}

TER_RATES: dict[str, list[tuple[int, float]]] = {
    "A": [
        (5_400_000, 0.0),
        (5_650_000, 0.0025),
        (5_950_000, 0.0050),
        (6_200_000, 0.0075),
        # ... all 44 brackets from PMK-168/2023 Lampiran
        (1_400_000_000, 0.34),
    ],
    "B": [
        (5_400_000, 0.0),
        # ... 44 brackets
        (1_400_000_000, 0.34),
    ],
    "C": [
        (5_400_000, 0.0),
        # ... 44 brackets
        (1_400_000_000, 0.34),
    ],
}


def calculate_pph21_ter(monthly_gross: int, ptkp_status: str = "TK/0") -> int:
    """Calculate monthly PPh21 using TER lookup (PP 58/2023).
    Used for Jan-Nov. December uses calculate_pph21_annual for reconciliation.
    """
    category = PTKP_TO_TER_CATEGORY.get(ptkp_status, "A")
    brackets = TER_RATES[category]
    for upper_bound, rate in brackets:
        if monthly_gross <= upper_bound:
            return int(monthly_gross * rate)
    # Above max bracket
    return int(monthly_gross * brackets[-1][1])
```

**Rationale (NB-1):** Calcolo tasse = CPU-bound. Query DB per 132 righe nel loop payroll = I/O non necessario. Costanti in-memory = O(1) lookup, zero latenza DB.

### 1B.2 — December Reconciliation

**File:** `apps/backend-rag/backend/app/utils/hr_utils.py`

```python
def calculate_pph21_december(
    cumulative_gross: int,
    cumulative_ter_paid: int,
    december_gross: int,
    ptkp_status: str = "TK/0",
) -> int:
    """December reconciliation: annual progressive - cumulative TER.
    PP 58/2023: TER used Jan-Nov, December settles with Article 17 progressive.
    """
    annual_gross = cumulative_gross + december_gross
    annual_tax = calculate_pph21_annual(annual_gross, ptkp_status)
    december_tax = max(0, annual_tax - cumulative_ter_paid)
    return december_tax
```

### 1B.3 — Wire TER in Payroll Service

**File:** `apps/backend-rag/backend/app/services/hr/hr_service.py` → `calculate_payroll()`

**Race condition fix (DeepSeek R1):** Aggiungere `FOR UPDATE` lock all'inizio del loop dipendenti:

```python
async with conn.transaction(isolation='serializable'):
    employees = await conn.fetch("""
        SELECT e.*, tm.full_name, tm.email
        FROM hr_employees e
        JOIN team_members tm ON tm.id = e.team_member_id
        WHERE e.is_active = TRUE
        FOR UPDATE OF e
    """)
```

Sostituire:

```python
pph21 = calculate_pph21_monthly(salary + bonus_total, ptkp)
```

Con:

```python
if data_month == 12:
    # December: use annual progressive reconciliation
    cumulative = await self._get_cumulative_pph21(conn, emp_id, data_year)
    pph21 = calculate_pph21_december(
        cumulative["gross"], cumulative["tax_paid"],
        salary + bonus_total, ptkp,
    )
else:
    # Jan-Nov: use TER
    pph21 = calculate_pph21_ter(salary + bonus_total, ptkp)
```

### 1B.4 — Cumulative Tracking

**Migration 069:** Aggiungere colonne a `hr_payslips` (non a `hr_employees` — il cumulo e derivabile):

```sql
-- No schema change needed: cumulative is computed from existing payslips
-- Query: SUM(base_salary_idr + bonus_total_idr + allowance_total_idr + thr_idr) for year
-- Query: SUM(pph21 deductions) for year
```

**Metodo helper:**

```python
async def _get_cumulative_pph21(self, conn, employee_id: int, year: int) -> dict:
    row = await conn.fetchrow("""
        SELECT
            COALESCE(SUM(ps.base_salary_idr + ps.bonus_total_idr + ps.allowance_total_idr + ps.thr_idr), 0) as gross,
            COALESCE(SUM(d.amount_idr), 0) as tax_paid
        FROM hr_payslips ps
        JOIN hr_payroll_periods pp ON pp.id = ps.payroll_period_id
        LEFT JOIN hr_deductions d ON d.payslip_id = ps.id AND d.deduction_type = 'pph21'
        WHERE ps.employee_id = $1 AND pp.payroll_year = $2 AND pp.payroll_month < 12
    """, employee_id, year)
    return {"gross": row["gross"], "tax_paid": row["tax_paid"]}
```

**Vantaggio:** Zero schema change, cumulo derivato da dati esistenti.

---

## Fase 1C: Overtime (Settimana 4)

### Migration 069

```sql
CREATE TABLE IF NOT EXISTS hr_overtime_entries (
    id BIGSERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES hr_employees(id) ON DELETE CASCADE,
    work_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    total_hours NUMERIC(4,2) NOT NULL CHECK (total_hours > 0 AND total_hours <= 4),
    work_type VARCHAR(20) NOT NULL DEFAULT 'weekday',
    amount_idr BIGINT NOT NULL CHECK (amount_idr >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    approved_by VARCHAR(36) REFERENCES team_members(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_overtime_emp_date UNIQUE (employee_id, work_date),
    CONSTRAINT ck_overtime_status CHECK (status IN ('pending','approved','rejected','paid')),
    CONSTRAINT ck_overtime_work_type CHECK (work_type IN ('weekday','weekend_5day','weekend_6day','holiday'))
);

CREATE INDEX IF NOT EXISTS idx_overtime_emp_date ON hr_overtime_entries(employee_id, work_date);
CREATE INDEX IF NOT EXISTS idx_overtime_status ON hr_overtime_entries(status);
```

### Overtime Rate Calculator

**File:** `apps/backend-rag/backend/app/utils/hr_utils.py`

```python
# ─── Overtime (UU Cipta Kerja + PP 35/2021) ───────────────────────────
# Hourly rate = 1/173 × (base_salary + fixed_allowances)
# NOT just base salary (Gemini Search confirmed, PP 35/2021 Art. 7-10)

def calculate_overtime(
    base_salary: int,
    fixed_allowances: int,
    hours: float,
    work_type: str = "weekday",
) -> int:
    """Calculate overtime pay per PP 35/2021.

    wage_base = base_salary + fixed_allowances
    hourly = wage_base / 173

    work_type:
    - weekday: 1.5x first hour, 2x subsequent (max 4h/day)
    - weekend_5day: 2x first 8h, 3x 9th, 4x 10th-12th
    - weekend_6day: 2x first 7h, 3x 8th, 4x 9th-11th
    - holiday: same as weekend_5day
    """
    wage_base = base_salary + fixed_allowances
    hourly = wage_base / 173

    if work_type == "weekday":
        if hours <= 1:
            return int(hours * hourly * 1.5)
        return int(hourly * 1.5 + (hours - 1) * hourly * 2)

    elif work_type in ("weekend_5day", "holiday"):
        total = 0.0
        if hours <= 8:
            total = hours * hourly * 2
        elif hours <= 9:
            total = 8 * hourly * 2 + (hours - 8) * hourly * 3
        else:
            total = 8 * hourly * 2 + hourly * 3 + (hours - 9) * hourly * 4
        return int(total)

    elif work_type == "weekend_6day":
        total = 0.0
        if hours <= 7:
            total = hours * hourly * 2
        elif hours <= 8:
            total = 7 * hourly * 2 + (hours - 7) * hourly * 3
        else:
            total = 7 * hourly * 2 + hourly * 3 + (hours - 8) * hourly * 4
        return int(total)

    return 0
```

### Lock Check (da validazione NB-1)

In endpoint POST `/api/hr/overtime`:

```python
# BEFORE inserting overtime, check payroll period is not locked
period = await conn.fetchrow("""
    SELECT status FROM hr_payroll_periods
    WHERE payroll_month = $1 AND payroll_year = $2
""", work_date.month, work_date.year)
if period and period["status"] in ("approved", "paid"):
    raise HTTPException(400, "Cannot add overtime: payroll period is already locked")
```

### Payroll Integration

In `calculate_payroll()`, dopo bonus:

```python
# Sum approved overtime for the period
overtime_row = await conn.fetchrow("""
    SELECT COALESCE(SUM(amount_idr), 0) as total
    FROM hr_overtime_entries
    WHERE employee_id = $1 AND status = 'approved'
      AND work_date BETWEEN $2 AND $3
""", emp_id, period_start, period_end)
overtime_total = overtime_row["total"]

# Include in payslip: allowance_total_idr = overtime_total
```

---

## Fase 2: PDF, Analytics, Notifiche (Settimana 5-8)

### 2.1 — Payslip PDF (reportlab)

**Dipendenza:** `reportlab` (aggiungere a requirements.txt)
**Endpoint:** `GET /api/hr/payslips/{id}/pdf`
**Pattern:** Genera in-memory, return StreamingResponse con `application/pdf`
**Nota:** reportlab usa ~50MB RAM vs ~150MB di weasyprint (critico su Fly.io 2GB)

### 2.2 — Dashboard Analytics

**Endpoint:** `GET /api/hr/analytics/trends?months=12`
**Dati:** Aggregazione da `hr_payslips` + `hr_payroll_periods` ultimi N mesi
**Frontend:** Grafico linea (nivo/recharts gia disponibile in mouth)

### 2.3 — Telegram Notifications

**Integrazione:** Usare `TelegramBotService` esistente
**Eventi:**

- Leave approvata/rifiutata → notifica al dipendente
- Payroll calcolato → notifica admin
- Bonus assegnato → notifica al dipendente

### 2.4 — Portal Leave Status

**Endpoint:** `GET /api/portal/team-status?email=...`
**Logica:** Query `hr_leave_requests` per ferie attive oggi → restituire status
**Frontend Portal:** Badge colorato su team member card

---

## File Impattati (Riepilogo)

| File                                              | Modifiche                                                                                        | Fase       |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ---------- |
| `backend/app/utils/hr_utils.py`                   | BPJS cap, TER constants, calculate_pph21_ter, calculate_pph21_december, calculate_overtime       | 1A, 1B, 1C |
| `backend/app/services/hr/hr_service.py`           | UMK validation, THR in payroll, TER wiring, overtime aggregation, BPJS report, cumulative helper | 1A, 1B, 1C |
| `backend/app/routers/hr.py`                       | include_thr flag, BPJS report endpoint, overtime CRUD endpoints                                  | 1A, 1C     |
| `backend/tests/unit/utils/test_hr_utils.py`       | BPJS cap test, TER tests (44 bracket), overtime tests, December reconciliation                   | 1A, 1B, 1C |
| `backend/migrations/migration_069_hr_overtime.py` | hr_overtime_entries table                                                                        | 1C         |
| `mouth/src/app/(workspace)/hr/`                   | Overtime page, BPJS report page, analytics dashboard                                             | 1C, 2      |
| `mouth/src/lib/api/hr/hr.ts`                      | Nuove API functions per overtime, reports                                                        | 1C         |
| `mouth/src/types/hr.ts`                           | OvertimeEntry, BPJSReport types                                                                  | 1C         |

---

## Rischi e Mitigazioni

| Rischio                                     | Probabilita | Impatto | Mitigazione                                                                                      |
| ------------------------------------------- | ----------- | ------- | ------------------------------------------------------------------------------------------------ |
| PPh21 TER calcolo errato                    | MEDIO       | ALTO    | Suite test con 100+ casi da simulatore DJP. Calcolo parallelo old/new per 3 mesi                 |
| Race condition payroll (2 admin simultanei) | MEDIO       | CRITICO | `FOR UPDATE` lock su employee rows + `SERIALIZABLE` isolation (DeepSeek R1)                      |
| Overtime retroattivo su periodo lockato     | ALTO        | MEDIO   | Lock check pre-insert (validazione NB-1)                                                         |
| December reconciliation: tax negativo       | BASSO       | MEDIO   | `max(0, annual_tax - cumulative)` — mai rimborsare via payroll                                   |
| THR tassazione errata                       | MEDIO       | ALTO    | THR incluso nel grosso mensile per TER (PP 58/2023), NON tassazione separata (Gemini confermato) |
| Overtime base errata                        | MEDIO       | MEDIO   | Base = salary + fixed_allowances (PP 35/2021), non solo salary                                   |
| Fly.io OOM con PDF generation               | BASSO       | ALTO    | reportlab (non weasyprint). Streaming response, no buffer in memoria                             |
| BPJS JP cap cambia annualmente              | CERTO       | BASSO   | Costante in hr_utils.py con commento data validita. Aggiornare ogni marzo                        |

---

## Success Metrics

- PPh21 TER match simulatore DJP ± Rp 100
- Payroll runtime < 5s per 10 dipendenti
- Zero breaking change su API esistenti
- BPJS report CSV importabile in SIPP senza errori
- Memory usage < 1.5GB su Fly.io (incluso PDF generation)

---

## Riferimenti Normativi

- **PPh21 TER:** PP 58/2023 + PMK-168/2023 (44 bracket × 3 categorie)
- **PPh21 Progressive:** UU HPP 7/2021 Pasal 17
- **BPJS Kesehatan:** Perpres 64/2020 (cap 12M, 4%+1%)
- **BPJS Ketenagakerjaan:** PP 44/2015, PP 46/2015
- **BPJS JP Cap:** 10.547.400 (Mar 2025 - Feb 2026)
- **THR:** Permenaker 6/2016 (penalita 5% ritardo)
- **Overtime:** UU Cipta Kerja + PP 35/2021 (1/173, rate fino a 4x)
- **UMK Badung 2026:** SK Gub Bali 1021/03-M/HK/2025 (Rp 3.791.003)
- **Cuti:** UU 13/2003 Pasal 79, 82, 93
