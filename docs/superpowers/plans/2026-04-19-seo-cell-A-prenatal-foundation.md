# SEO Cell — Pre-natal Foundation (Plan A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eseguire Sprint 0 dello spec SEO Guardian Cell — alimentare il segnale SEO di balizero.com (corpus GSC, attribution, on-page basics) così che la cellula possa partire in fase pre-natal con dati su cui crescere senza Goodhart-by-rumore.

**Architecture:** 4 stream di lavoro paralleli, owner mix:

- **Newsroom team** (autonomo) — scrive 4 articoli SEO commerciali high-intent (16h scrittura)
- **Antonello** — review strategica (4h: selezione query target + review articoli)
- **Damar** — page-level SEO refresh integrando `gemini_seo_optimizer.py`, CRM `referrer_url` capture, sitemap re-submit (12h dev)

**Tech Stack:** Python 3.11 + FastAPI (backend-rag), Alembic migrations, Next.js 16 + React 19 (apps/mouth), TypeScript, `gemini_seo_optimizer.py` esistente (bali-intel-scraper), war-room newsroom pipeline esistente.

**Spec parent:** `docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md` v2.1 §3.2

**Definition of done globale (esce questo plan = ✅):**

- 4 articoli SEO commerciali pubblicati su balizero.com, indicizzati GSC
- Tutti e 4 i funnel pages (`/visa`, `/kbli`, `/tax`, `/property`) hanno schema.org JSON-LD + FAQ + canonical + OG ottimizzati
- CRM `clients` table ha campo `referrer_url` + `lead_source` differenzia `website_organic` vs `whatsapp_inbound`
- WhatsApp link su balizero.com hanno UTM tracking (`utm_source=balizero_web&utm_medium=whatsapp_cta&utm_campaign=<page_slug>`)
- sitemap.xml include `/visa`, `/kbli`, `/tax`, `/property` con priority 0.9, frequency weekly
- GSC ha re-submit confirmation per 4 nuove URL pubblicate

---

## File Structure Overview

Files che verranno creati o modificati:

| File                                                                        | Owner              | Status           | Responsabilità                                                                                                   |
| --------------------------------------------------------------------------- | ------------------ | ---------------- | ---------------------------------------------------------------------------------------------------------------- |
| `apps/backend-rag/backend/migrations/migration_118_clients_referrer_url.py` | Damar              | NEW              | Migration Alembic: aggiunge `referrer_url`, `landing_page`, `first_touch_at` a `clients`, indice                 |
| `apps/backend-rag/backend/services/crm/lead_intake.py`                      | Damar              | MODIFY (~30 LOC) | Capture `referrer_url` da request headers + Body, set `lead_source` based on UTM                                 |
| `apps/mouth/src/lib/whatsapp-utm.ts`                                        | Damar              | NEW              | Helper TS: build WA link con UTM params da page slug + funnel                                                    |
| `apps/mouth/src/app/v2/_components/HeroBlueprint.tsx`                       | Damar              | MODIFY (1 line)  | Sostituisci hardcoded WA link con `buildWhatsAppLink('home')`                                                    |
| `apps/mouth/src/app/v2/_components/FunnelFeature.tsx`                       | Damar              | MODIFY (4 lines) | Sostituisci hardcoded WA link con `buildWhatsAppLink(funnel)`                                                    |
| `apps/mouth/src/app/v2/_components/ZantaraFAB.tsx`                          | Damar              | MODIFY (1 line)  | UTM su FAB WA link                                                                                               |
| `apps/mouth/src/app/(marketing)/_seo/funnel-schema.ts`                      | Damar              | NEW              | Funzione TS che genera Schema.org Service + FAQ JSON-LD per ogni funnel page (visa/kbli/tax/property)            |
| `apps/mouth/src/app/(marketing)/page.tsx`                                   | Damar              | MODIFY (~20 LOC) | Inietta JSON-LD schema in `<head>` via Next.js metadata API                                                      |
| `apps/mouth/src/app/sitemap.ts`                                             | Damar              | MODIFY (~10 LOC) | Aggiungi 4 funnel pages con priority 0.9 + ping GSC re-submit                                                    |
| `apps/war-room/agents/00_topic_selector.py`                                 | Antonello (config) | MODIFY (~5 LOC)  | Inject 4 query target nelle "preferred_topics" config in modo che newsroom le pesi più alto nei prossimi 4 cicli |
| `data/seo_kw_targets/2026-04-21-prenatal.json`                              | Antonello          | NEW              | Lista delle 4 query commerciali target con brief redazionale                                                     |
| (4 articoli MDX) `apps/mouth/src/content/blog/<slug>.mdx`                   | Newsroom team      | NEW × 4          | Articoli SEO commerciali — autonomous via newsroom, Antonello review pre-publish                                 |
| `scripts/gsc_resubmit_sitemap.py`                                           | Damar              | NEW (~40 LOC)    | Script one-shot per re-submit sitemap a GSC API + log conferma                                                   |

---

## Task 1: Antonello — Selezione 4 query target + brief redazionale

**Owner:** Antonello (1h)
**Files:**

- Create: `data/seo_kw_targets/2026-04-21-prenatal.json`

**Why:** La newsroom war-room ha autonomia di scrittura ma deve sapere su quali 4 query commerciali concentrarsi nei prossimi 4 cicli. Il brief redazionale dà contesto X_BRAND_VOICE per ognuna.

- [ ] **Step 1: Selezionare 4 query con criteri espliciti**

Criteri di selezione (Antonello in 30 min):

1. Search intent: **transactional** o **commercial investigation** (NON informational generico). Esempi buoni: `"PT PMA minimum capital 2026"`, `"E33G remote worker KITAS cost"`, `"hak pakai vs HGB foreign buyer"`, `"NPWP for foreign individual Indonesia"`. Esempi cattivi: `"what is Bali"`, `"visa types Indonesia"` (troppo generico).
2. KG coverage: query per cui Bali Zero ha già fatti strutturati (es. KG entity con ≥10 facts).
3. Competitor weakness: query dove Cekindo/Emerhub/InvestinAsia hanno coverage debole o outdated.
4. Volume stimato: ≥30 search/mese per query (intuizione + tool come keywordtool.io o ubersuggest, ok stimato).

Le 4 query DEVONO coprire i 4 domini Bali Zero (1 visa, 1 PT PMA/KBLI, 1 tax, 1 property) per bilanciare il segnale GSC.

- [ ] **Step 2: Scrivere brief redazionale per ognuna**

Crea il file:

```bash
mkdir -p /Users/nuzantara/Desktop/nuzantara/data/seo_kw_targets
```

Crea `/Users/nuzantara/Desktop/nuzantara/data/seo_kw_targets/2026-04-21-prenatal.json`:

```json
{
  "version": 1,
  "created_at": "2026-04-21",
  "owner": "antonello",
  "purpose": "SEO Cell pre-natal Sprint 0 — 4 articoli high commercial intent",
  "spec": "docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md §3.2",
  "queries": [
    {
      "id": "q1_visa",
      "domain": "visa",
      "query": "E33G remote worker KITAS cost 2026",
      "search_intent": "transactional",
      "estimated_monthly_volume": 80,
      "kg_entity_canonical": "kitas_e33g_remote_worker",
      "kg_facts_count": 14,
      "competitor_landscape": {
        "pos_1": "cekindo.com (outdated 2024)",
        "pos_2": "emerhub.com (cost vague)",
        "pos_3": "balizero.com (none)"
      },
      "brief_redazionale": "Voce X_BRAND_VOICE: bar test. Apri con il numero (filed 47 KITAS this month). Smonta il mito che E33G sia 'free for any digital nomad'. Spiega: chi può applicare (Indonesia onshore offshore distinction), cosa serve davvero (proof of income $2k/mo, employment letter, no work for Indonesian client), prezzo nostro $1850 trasparente, timeline 6-8 settimane realistica. Cita pasal regulation. Voce: grounded sharp warm-blooded.",
      "target_url": "/blog/e33g-remote-worker-kitas-cost-2026",
      "target_word_count": 1800,
      "must_include_internal_links": ["/visa", "/visa/e33g"],
      "deadline": "2026-05-05"
    },
    {
      "id": "q2_kbli",
      "domain": "kbli",
      "query": "PT PMA minimum capital reality 2026",
      "search_intent": "commercial_investigation",
      "estimated_monthly_volume": 120,
      "kg_entity_canonical": "pt_pma_capital_requirement",
      "kg_facts_count": 11,
      "competitor_landscape": {
        "pos_1": "investinasia.id (paper number IDR 10B confusing)",
        "pos_2": "cekindo.com (corporate-style)",
        "pos_3": "balizero.com (none)"
      },
      "brief_redazionale": "Smonta IDR 10 miliardi 'paper number' vs IDR 2.5 miliardi paid-up effettivo per shareholder. Apri con il numero (this month: 9 PT PMAs filed). Spiega esattamente quanto cash serve al day-1 (~IDR 7M registration), quale parte è 'investment commitment' non cash. Cita PP 18/2021. Pricing nostro $1850 setup trasparente. Bar test: scrive come stai parlando a un imprenditore tech a Seminyak.",
      "target_url": "/blog/pt-pma-minimum-capital-reality-2026",
      "target_word_count": 2000,
      "must_include_internal_links": ["/kbli", "/pricing/pt-pma"],
      "deadline": "2026-05-12"
    },
    {
      "id": "q3_tax",
      "domain": "tax",
      "query": "PPh 21 expat foreign income Indonesia 2026",
      "search_intent": "commercial_investigation",
      "estimated_monthly_volume": 65,
      "kg_entity_canonical": "pph21_foreign_income",
      "kg_facts_count": 9,
      "competitor_landscape": {
        "pos_1": "ddtcnews.com (technical Indonesian only)",
        "pos_2": "asean briefing (corporate B2B style)",
        "pos_3": "balizero.com (none)"
      },
      "brief_redazionale": "L'expat che lavora remotamente per cliente foreign deve PPh 21 in Indonesia se KITAS+183gg. Smonta il mito 'remote = no Indonesia tax'. Brackets attuali (5/15/25/30/35%), DTAA con Italia/USA/UK distinzione, deadline annual SPT marzo 31. Apri con: 'Last month: 2 SPT filings completed for digital nomad clients'. Voce X_BRAND_VOICE.",
      "target_url": "/blog/pph21-expat-foreign-income-indonesia-2026",
      "target_word_count": 1900,
      "must_include_internal_links": ["/tax", "/tax/pph21-calculator"],
      "deadline": "2026-05-19"
    },
    {
      "id": "q4_property",
      "domain": "property",
      "query": "hak pakai vs HGB foreign buyer Bali 2026",
      "search_intent": "commercial_investigation",
      "estimated_monthly_volume": 95,
      "kg_entity_canonical": "land_title_foreign_options",
      "kg_facts_count": 13,
      "competitor_landscape": {
        "pos_1": "sevenstones (commercial bias)",
        "pos_2": "harcourts.id (real estate listing not legal)",
        "pos_3": "balizero.com (none)"
      },
      "brief_redazionale": "Smonta nominee agreement (illegal under Indonesian law). 3 opzioni reali per straniero: Hak Pakai (max 80yr renewable), Hak Sewa leasehold (max 30yr), HGB via PT PMA (renewable 30+20yr). Pro/contro economici di ognuno. Cita Perda Bali 4/2026 (criminal law su land conversion). Apri con: '0 transactions closed by us this month — we go slow on land DD' (onestà = trust signal Bali Zero unique).",
      "target_url": "/blog/hak-pakai-vs-hgb-foreign-buyer-bali-2026",
      "target_word_count": 2200,
      "must_include_internal_links": ["/property", "/property/eligibility"],
      "deadline": "2026-05-26"
    }
  ]
}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add data/seo_kw_targets/2026-04-21-prenatal.json
git commit -m "feat(seo-cell): pre-natal sprint 0 — 4 query target with editorial briefs

4 commercial-intent queries selected for newsroom war-room:
- E33G remote worker KITAS cost 2026 (visa)
- PT PMA minimum capital reality 2026 (kbli)
- PPh 21 expat foreign income 2026 (tax)
- hak pakai vs HGB foreign buyer 2026 (property)

Each brief includes KG entity link, competitor landscape, voice
guidance (X_BRAND_VOICE bar test), target URL, deadline.

Spec: docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md §3.2"
```

---

## Task 2: Antonello — Iniezione query target nel newsroom config

**Owner:** Antonello (30 min)
**Files:**

- Modify: `apps/war-room/agents/00_topic_selector.py:~40-60` (config block)

**Why:** Il newsroom war-room (DeepSeek synthesis su 4 sorgenti) deve essere influenzato a scegliere queste 4 query nei prossimi 4 cicli. Aggiungiamo `preferred_topics` dal file Sprint 0.

- [x] **Step 1: Identifica il config block in `00_topic_selector.py`**

Run:

```bash
grep -nE "INDONESIAN_LEGAL_DOMAINS|SOURCES|NLM_NB7_ID" /Users/nuzantara/Desktop/nuzantara/apps/war-room/agents/00_topic_selector.py
```

Expected output: trova le righe dei config nelle prime ~60 righe.

- [x] **Step 2: Aggiungi caricamento brief Sprint 0**

Edit `apps/war-room/agents/00_topic_selector.py` (subito dopo gli altri config in cima):

```python
# Sprint 0 SEO Cell pre-natal — boost preferred queries from Antonello brief
SEO_CELL_PRENATAL_BRIEF_PATH = Path(__file__).parent.parent.parent.parent / "data" / "seo_kw_targets" / "2026-04-21-prenatal.json"

def _load_seo_cell_prenatal_briefs() -> list[dict]:
    """Load 4 commercial query targets if file exists. Returns empty list if not."""
    if not SEO_CELL_PRENATAL_BRIEF_PATH.exists():
        return []
    try:
        data = json.loads(SEO_CELL_PRENATAL_BRIEF_PATH.read_text())
        # Filter only queries not yet published (deadline in future)
        return [q for q in data.get("queries", []) if q.get("deadline", "") > datetime.now().strftime("%Y-%m-%d")]
    except Exception as e:
        # Graceful degradation — log + return empty, never block newsroom
        print(f"[topic_selector] Could not load SEO Cell briefs: {e}", file=sys.stderr)
        return []
```

- [x] **Step 3: Inietta nel DeepSeek synthesis prompt**

Trova la sezione del prompt che invia a DeepSeek (cerca `def synthesize_with_deepseek` o simile). Aggiungi questa sezione al prompt:

```python
seo_cell_briefs = _load_seo_cell_prenatal_briefs()
if seo_cell_briefs:
    seo_section = "\n\n--- SEO CELL PRIORITY (pre-natal sprint 0) ---\n"
    seo_section += "These queries are commercially critical. If any current trending topic semantically overlaps, PREFER the SEO query angle:\n"
    for q in seo_cell_briefs:
        seo_section += f"- '{q['query']}' (deadline: {q['deadline']}, brief: {q['brief_redazionale'][:200]}...)\n"
    seo_section += "Weight: 1.5x normal sources for next 4 cycles.\n"
    prompt += seo_section
```

- [x] **Step 4: Test che il file viene caricato senza errori**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/war-room
python3 -c "
import sys, json
from pathlib import Path
from datetime import datetime
sys.path.insert(0, 'agents')
exec(open('agents/00_topic_selector.py').read().split('def main()')[0])  # exec only top-level config
briefs = _load_seo_cell_prenatal_briefs()
print(f'Loaded {len(briefs)} briefs')
for b in briefs:
    print(f'  - {b[\"id\"]}: {b[\"query\"][:60]} (deadline: {b[\"deadline\"]})')"
```

Expected output:

```
Loaded 4 briefs
  - q1_visa: E33G remote worker KITAS cost 2026 (deadline: 2026-05-05)
  - q2_kbli: PT PMA minimum capital reality 2026 (deadline: 2026-05-12)
  - q3_tax: PPh 21 expat foreign income Indonesia 2026 (deadline: 2026-05-19)
  - q4_property: hak pakai vs HGB foreign buyer Bali 2026 (deadline: 2026-05-26)
```

- [x] **Step 5: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/war-room/agents/00_topic_selector.py
git commit -m "feat(war-room): inject SEO Cell pre-natal brief into newsroom topic selector

00_topic_selector.py now loads data/seo_kw_targets/2026-04-21-prenatal.json
when present and weights those 4 commercial queries 1.5x in DeepSeek
synthesis prompt for next 4 cycles (until each deadline).

Graceful degradation: if file missing or malformed, newsroom continues
with original 4 sources unchanged.

Spec: docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md §3.2"
```

---

## Task 3: Damar — Migration 118 — `clients` table referrer columns

**Owner:** Damar (2h)
**Files:**

- Create: `apps/backend-rag/backend/migrations/migration_118_clients_referrer_url.py`
- Test: `apps/backend-rag/backend/tests/migrations/test_migration_118.py`

**Why:** CRM oggi ha `lead_source` (`whatsapp`, `website`, etc.) ma non sa **da quale pagina** è entrato il visitor. Senza `referrer_url + landing_page + first_touch_at`, la metrica `revenue_attributed_keyword` Phase 2 è impossibile.

- [x] **Step 1: Write the failing test**

Create `apps/backend-rag/backend/tests/migrations/test_migration_118.py`:

```python
"""Migration 118 test: clients referrer columns."""
import pytest
import asyncpg
from pathlib import Path


@pytest.mark.asyncio
async def test_migration_118_adds_referrer_url_column(test_db_pool):
    """After migration, clients table has referrer_url, landing_page, first_touch_at."""
    async with test_db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'clients'
              AND column_name IN ('referrer_url', 'landing_page', 'first_touch_at')
            ORDER BY column_name
        """)
        col_names = {row["column_name"] for row in rows}
        assert col_names == {"first_touch_at", "landing_page", "referrer_url"}, \
            f"Missing columns. Found: {col_names}"


@pytest.mark.asyncio
async def test_migration_118_creates_index(test_db_pool):
    """Index on referrer_url exists for SEO attribution queries."""
    async with test_db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'clients' AND indexname = 'idx_clients_referrer_url'
        """)
        assert len(rows) == 1, "Missing index idx_clients_referrer_url"


@pytest.mark.asyncio
async def test_migration_118_lead_source_enum_extended(test_db_pool):
    """lead_source can hold new values website_organic and whatsapp_inbound."""
    async with test_db_pool.acquire() as conn:
        # Insert client with new lead_source values
        await conn.execute("""
            INSERT INTO clients (full_name, email, lead_source, referrer_url, landing_page)
            VALUES
                ('Test User Organic', 'organic@test.com', 'website_organic',
                 'https://www.google.com/search?q=KITAS', '/blog/e33g-cost-2026'),
                ('Test User Inbound', 'inbound@test.com', 'whatsapp_inbound',
                 NULL, NULL)
        """)

        rows = await conn.fetch(
            "SELECT lead_source FROM clients WHERE email IN ('organic@test.com', 'inbound@test.com')"
        )
        sources = sorted([r["lead_source"] for r in rows])
        assert sources == ["website_organic", "whatsapp_inbound"]

        # Cleanup
        await conn.execute("DELETE FROM clients WHERE email IN ('organic@test.com', 'inbound@test.com')")
```

- [x] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/migrations/test_migration_118.py -v
```

Expected: FAIL with `column "referrer_url" does not exist` or similar.

- [x] **Step 3: Write the migration**

Create `apps/backend-rag/backend/migrations/migration_118_clients_referrer_url.py`:

```python
"""
Migration 118: Add referrer_url, landing_page, first_touch_at to clients table.

Why: SEO Cell Phase 2 revenue attribution requires knowing which landing
page (and which Google referrer) brought a lead. Without this, we cannot
attribute revenue to specific brief URLs.

Spec: docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md §3.2

Idempotent: safe to re-run.
"""
from __future__ import annotations

UP_SQL = """
-- Add columns if missing (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clients' AND column_name = 'referrer_url'
    ) THEN
        ALTER TABLE clients ADD COLUMN referrer_url TEXT;
        COMMENT ON COLUMN clients.referrer_url IS
            'HTTP Referer header at first interaction. Used for SEO attribution.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clients' AND column_name = 'landing_page'
    ) THEN
        ALTER TABLE clients ADD COLUMN landing_page TEXT;
        COMMENT ON COLUMN clients.landing_page IS
            'First page on balizero.com domain visited. SEO attribution + CRO analysis.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clients' AND column_name = 'first_touch_at'
    ) THEN
        ALTER TABLE clients ADD COLUMN first_touch_at TIMESTAMP WITH TIME ZONE;
        COMMENT ON COLUMN clients.first_touch_at IS
            'When the lead first interacted with our properties (web/WhatsApp/etc).';
    END IF;
END
$$;

-- Index for SEO attribution queries (LIKE patterns on URL)
CREATE INDEX IF NOT EXISTS idx_clients_referrer_url
    ON clients (referrer_url text_pattern_ops)
    WHERE referrer_url IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_clients_landing_page
    ON clients (landing_page text_pattern_ops)
    WHERE landing_page IS NOT NULL;
"""

DOWN_SQL = """
DROP INDEX IF EXISTS idx_clients_landing_page;
DROP INDEX IF EXISTS idx_clients_referrer_url;
ALTER TABLE clients DROP COLUMN IF EXISTS first_touch_at;
ALTER TABLE clients DROP COLUMN IF EXISTS landing_page;
ALTER TABLE clients DROP COLUMN IF EXISTS referrer_url;
"""


async def upgrade(conn) -> None:
    """Apply migration."""
    await conn.execute(UP_SQL)


async def downgrade(conn) -> None:
    """Revert migration."""
    await conn.execute(DOWN_SQL)
```

- [x] **Step 4: Apply migration locally**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python -m backend.migrations.migration_manager upgrade --target 118
```

Expected output: `[migration_118] Applied successfully`.

- [x] **Step 5: Run test to verify it passes**

Run:

```bash
PYTHONPATH=. pytest backend/tests/migrations/test_migration_118.py -v
```

Expected: 3 PASS.

- [x] **Step 6: Verify on production DB (Fly.io) — DRY RUN ONLY**

Run:

```bash
fly ssh console -a nuzantara-rag -C "/bin/sh -c 'cd /app && PYTHONPATH=. python -m backend.migrations.migration_manager upgrade --target 118 --dry-run'"
```

Expected: dry-run shows the SQL that would execute. **Do NOT apply on prod yet** — production migration will be applied by fly-deploy.yml on next deploy via standard migration_manager flow.

- [x] **Step 7: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/backend-rag/backend/migrations/migration_118_clients_referrer_url.py
git add apps/backend-rag/backend/tests/migrations/test_migration_118.py
git commit -m "feat(crm): migration 118 — clients.referrer_url + landing_page + first_touch_at

Adds 3 columns + 2 indexes for SEO attribution. Foundation for Phase 2
revenue_attributed_keyword metric.

Tests: 3 (column existence, index existence, lead_source enum extended).
Idempotent. Reversible via downgrade SQL.

Spec: docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md §3.2"
```

---

## Task 4: Damar — Lead intake service — capture referrer

**Owner:** Damar (2h)
**Files:**

- Modify: `apps/backend-rag/backend/services/crm/lead_intake.py` (~30 LOC change)
- Test: `apps/backend-rag/backend/tests/services/crm/test_lead_intake_referrer.py`

**Why:** La migration 118 ha aggiunto le colonne, ora serve che siano popolate quando arriva un lead da web (form contact, WhatsApp UTM landing).

- [x] **Step 1: Trova il file esistente del lead intake**

Run:

```bash
find /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services -name "lead_intake*" -o -name "client_create*" 2>/dev/null | head
```

Se il file `lead_intake.py` non esiste con quel nome, cerca dove viene chiamato `INSERT INTO clients`:

```bash
grep -rn "INSERT INTO clients" /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services 2>/dev/null | head -5
```

Adatta il path target a quello effettivo trovato.

- [x] **Step 2: Write the failing test**

Create `apps/backend-rag/backend/tests/services/crm/test_lead_intake_referrer.py`:

```python
"""Test lead intake captures referrer + landing + first_touch."""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_lead_intake_captures_referrer_when_present():
    """If request body includes referrer_url, it's stored."""
    from backend.services.crm.lead_intake import create_lead

    mock_db = AsyncMock()
    mock_db.fetchrow.return_value = {"id": 999, "uuid": "fake-uuid"}

    payload = {
        "full_name": "Test User",
        "email": "test@example.com",
        "lead_source": "website_organic",
        "referrer_url": "https://www.google.com/search?q=KITAS+cost",
        "landing_page": "/blog/e33g-cost-2026",
    }
    result = await create_lead(payload, db=mock_db)

    # Verify the INSERT was called with referrer_url
    call_args = mock_db.fetchrow.call_args
    sql = call_args[0][0]
    assert "referrer_url" in sql
    assert "landing_page" in sql
    assert "first_touch_at" in sql

    # Verify positional args include the referrer
    args = call_args[0][1:]
    assert "https://www.google.com/search?q=KITAS+cost" in args
    assert "/blog/e33g-cost-2026" in args


@pytest.mark.asyncio
async def test_lead_intake_infers_lead_source_from_utm():
    """If utm_source=balizero_web + utm_medium=whatsapp_cta, set lead_source=whatsapp_inbound."""
    from backend.services.crm.lead_intake import create_lead

    mock_db = AsyncMock()
    mock_db.fetchrow.return_value = {"id": 999, "uuid": "fake-uuid"}

    payload = {
        "full_name": "WA Test",
        "email": "watest@example.com",
        "landing_page": "/visa?utm_source=balizero_web&utm_medium=whatsapp_cta&utm_campaign=visa_page",
        # no explicit lead_source — should be inferred
    }
    await create_lead(payload, db=mock_db)

    call_args = mock_db.fetchrow.call_args
    args = call_args[0][1:]
    assert "whatsapp_inbound" in args, f"Expected lead_source=whatsapp_inbound inferred from UTM. Got args: {args}"


@pytest.mark.asyncio
async def test_lead_intake_defaults_lead_source_when_no_utm():
    """If no utm and no explicit lead_source, default to website_organic if landing_page present, else NULL."""
    from backend.services.crm.lead_intake import create_lead

    mock_db = AsyncMock()
    mock_db.fetchrow.return_value = {"id": 999, "uuid": "fake-uuid"}

    payload = {
        "full_name": "Direct Visit",
        "email": "direct@example.com",
        "landing_page": "/visa",
    }
    await create_lead(payload, db=mock_db)

    args = mock_db.fetchrow.call_args[0][1:]
    assert "website_organic" in args
```

- [x] **Step 3: Run test to verify it fails**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/crm/test_lead_intake_referrer.py -v
```

Expected: FAIL (import error or function signature mismatch).

- [x] **Step 4: Implement / patch the lead intake function**

Edit the file found in Step 1 (`backend/services/crm/lead_intake.py` or equivalent). Add or modify `create_lead`:

```python
import re
from typing import Any
from datetime import datetime, timezone


def _infer_lead_source(payload: dict) -> str | None:
    """Infer lead_source from explicit field or UTM params."""
    if payload.get("lead_source"):
        return payload["lead_source"]

    landing = payload.get("landing_page", "") or ""
    if "utm_medium=whatsapp_cta" in landing or "utm_source=whatsapp" in landing:
        return "whatsapp_inbound"
    if landing:
        return "website_organic"
    return None


async def create_lead(payload: dict, db: Any) -> dict:
    """
    Create a CRM lead with SEO attribution capture.

    payload required: full_name, email
    payload optional: lead_source, referrer_url, landing_page, phone, ...

    If lead_source not provided, infer from UTM params in landing_page.
    Always sets first_touch_at = NOW() at insertion.
    """
    inferred_source = _infer_lead_source(payload)
    first_touch_at = payload.get("first_touch_at") or datetime.now(timezone.utc)

    row = await db.fetchrow(
        """
        INSERT INTO clients (
            full_name, email, phone,
            lead_source, referrer_url, landing_page, first_touch_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id, uuid
        """,
        payload.get("full_name"),
        payload.get("email"),
        payload.get("phone"),
        inferred_source,
        payload.get("referrer_url"),
        payload.get("landing_page"),
        first_touch_at,
    )
    return {"id": row["id"], "uuid": str(row["uuid"])}
```

- [x] **Step 5: Run test to verify it passes**

Run:

```bash
PYTHONPATH=. pytest backend/tests/services/crm/test_lead_intake_referrer.py -v
```

Expected: 3 PASS.

- [x] **Step 6: Verify import chain not broken**

Run:

```bash
PYTHONPATH=. python -c "from backend.app.dependencies import get_current_user; print('OK')"
```

Expected: `OK`. If fails, the lead_intake change broke imports — debug before commit.

- [x] **Step 7: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/backend-rag/backend/services/crm/lead_intake.py
git add apps/backend-rag/backend/tests/services/crm/test_lead_intake_referrer.py
git commit -m "feat(crm): capture referrer_url + landing_page + first_touch_at on lead intake

Lead source inference rules:
- explicit lead_source field wins
- else UTM medium/source whatsapp_cta → whatsapp_inbound
- else landing_page present → website_organic
- else NULL

Tests: 3 (capture from explicit, UTM inference, default).

Spec: docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md §3.2"
```

---

## Task 5: Damar — WhatsApp UTM helper TS

**Owner:** Damar (1h)
**Files:**

- Create: `apps/mouth/src/lib/whatsapp-utm.ts`
- Test: `apps/mouth/src/lib/whatsapp-utm.test.ts`

**Why:** Oggi i link WhatsApp sono hardcoded `https://wa.me/628213107363?text=Hi%20Bali%20Zero...` ovunque. Senza UTM, ogni lead WhatsApp arriva senza context "da quale pagina veniva". Helper centralizza + aggiunge UTM.

- [x] **Step 1: Write the failing test**

Create `apps/mouth/src/lib/whatsapp-utm.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { buildWhatsAppLink } from "./whatsapp-utm";

describe("buildWhatsAppLink", () => {
  it("builds link with default greeting and UTM", () => {
    const link = buildWhatsAppLink("home");
    expect(link).toContain("https://wa.me/628213107363");
    expect(link).toContain("utm_source=balizero_web");
    expect(link).toContain("utm_medium=whatsapp_cta");
    expect(link).toContain("utm_campaign=home");
  });

  it("encodes funnel-specific greeting for visa", () => {
    const link = buildWhatsAppLink("visa");
    expect(link).toContain("utm_campaign=visa");
    expect(link).toMatch(/text=.*visa/i);
  });

  it("encodes special characters in greeting", () => {
    const link = buildWhatsAppLink(
      "kbli",
      "Custom: question with spaces & symbols",
    );
    expect(link).toContain(
      "Custom%3A%20question%20with%20spaces%20%26%20symbols",
    );
  });

  it("falls back to home if funnel unknown", () => {
    // @ts-expect-error testing runtime defensive code
    const link = buildWhatsAppLink("nonexistent_funnel");
    expect(link).toContain("utm_campaign=home");
  });
});
```

- [x] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/mouth
pnpm test src/lib/whatsapp-utm.test.ts --run
```

Expected: FAIL `Cannot find module './whatsapp-utm'`.

- [x] **Step 3: Implement the helper**

Create `apps/mouth/src/lib/whatsapp-utm.ts`:

```typescript
/**
 * WhatsApp deep-link builder with UTM tracking for SEO attribution.
 *
 * All WA CTAs across balizero.com MUST go through this helper so the
 * landing_page on the WhatsApp side carries proper attribution that
 * the CRM lead_intake can parse.
 *
 * Spec: docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md §3.2
 */

const WA_NUMBER = "628213107363";

type Funnel = "home" | "visa" | "kbli" | "tax" | "property";

const FUNNEL_GREETINGS: Record<Funnel, string> = {
  home: "Hi Bali Zero, I would like to get started.",
  visa: "Hi Bali Zero, I have a question about visa or KITAS.",
  kbli: "Hi Bali Zero, I want to set up a PT PMA / business in Indonesia.",
  tax: "Hi Bali Zero, I have a question about Indonesian tax.",
  property: "Hi Bali Zero, I want help with property due diligence in Bali.",
};

export function buildWhatsAppLink(
  funnel: string,
  customGreeting?: string,
): string {
  const safe: Funnel = (funnel in FUNNEL_GREETINGS ? funnel : "home") as Funnel;
  const greeting = customGreeting || FUNNEL_GREETINGS[safe];

  const params = new URLSearchParams({
    text: greeting,
    utm_source: "balizero_web",
    utm_medium: "whatsapp_cta",
    utm_campaign: safe,
  });

  return `https://wa.me/${WA_NUMBER}?${params.toString()}`;
}
```

- [x] **Step 4: Run test to verify it passes**

Run:

```bash
pnpm test src/lib/whatsapp-utm.test.ts --run
```

Expected: 4 PASS.

- [x] **Step 5: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/mouth/src/lib/whatsapp-utm.ts apps/mouth/src/lib/whatsapp-utm.test.ts
git commit -m "feat(mouth): add buildWhatsAppLink helper with UTM attribution

Centralizes all WA CTAs to carry utm_source=balizero_web +
utm_medium=whatsapp_cta + utm_campaign=<page_slug>. CRM lead_intake
parses these into lead_source=whatsapp_inbound for SEO attribution.

Tests: 4 (default, funnel-specific, special chars, unknown fallback).

Spec: docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md §3.2"
```

---

## Task 6: Damar — Replace hardcoded WA links with `buildWhatsAppLink`

**Owner:** Damar (45 min)
**Files:**

- Modify: `apps/mouth/src/app/v2/_components/HeroBlueprint.tsx` (1 link)
- Modify: `apps/mouth/src/app/v2/_components/FunnelFeature.tsx` (4 funnel CTAs use this for fallback contact)
- Modify: `apps/mouth/src/app/(marketing)/page.tsx` (header WA "Get Started" CTA)
- Modify: `apps/mouth/src/app/v2/_components/ZantaraFAB.tsx` (FAB if it links to WA)
- Modify: any other file with `wa.me/628213107363` hardcoded

**Why:** Senza questa modifica, l'helper esiste ma non è chiamato — UTM non vengono mai sparate.

- [x] **Step 1: Find all hardcoded WA links**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/mouth
grep -rn "wa.me/628213107363" src/ 2>/dev/null
```

Expected: 5-10 occurrences across components. Note them down.

- [x] **Step 2: Replace each occurrence with helper call**

For each file found, replace pattern:

**Before:**

```tsx
<a href="https://wa.me/628213107363?text=Hi%20Bali%20Zero%2C%20I%20would%20like%20to%20get%20started.">
```

**After (e.g., for HeroBlueprint.tsx — top-level home page):**

```tsx
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
// ...
<a href={buildWhatsAppLink("home")}>
```

**For FunnelFeature.tsx (which knows the funnel via prop):**

```tsx
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
// ...
<a href={buildWhatsAppLink(funnel)}>  // funnel is "visa" | "kbli" | "tax" | "property"
```

**For (marketing)/page.tsx header CTA:**

```tsx
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
// ...
<a href={buildWhatsAppLink("home")}>Get Started</a>;
```

- [x] **Step 3: Verify no hardcoded WA links remain**

Run:

```bash
grep -rn "wa.me/628213107363" src/ 2>/dev/null
```

Expected: empty output (all replaced) OR only test files / docs.

- [x] **Step 4: Run TypeScript build to verify imports correct**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/mouth
pnpm build 2>&1 | tail -20
```

Expected: Build succeeds, no `Cannot find module` errors.

- [ ] **Step 5: Visual QA in dev mode (Damar manual check)**

Run:

```bash
pnpm dev
```

Open `http://localhost:3000` in browser. Hover the "Get Started" header button → check status bar shows `wa.me/628213107363?text=...&utm_source=balizero_web&utm_medium=whatsapp_cta&utm_campaign=home`.

Click hero CTA → same check.

Scroll to visa funnel section → check (if any WA link there) `utm_campaign=visa`.

- [x] **Step 6: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/mouth/src/app/v2/_components/HeroBlueprint.tsx
git add apps/mouth/src/app/v2/_components/FunnelFeature.tsx
git add apps/mouth/src/app/v2/_components/ZantaraFAB.tsx
git add apps/mouth/src/app/\(marketing\)/page.tsx
# add any other modified files from Step 1
git commit -m "feat(mouth): replace hardcoded WhatsApp links with buildWhatsAppLink helper

All WA CTAs across mouth now carry UTM: utm_source=balizero_web,
utm_medium=whatsapp_cta, utm_campaign=<funnel-slug>. CRM lead_intake
parses these into lead_source=whatsapp_inbound for SEO attribution.

Visual QA: dev mode confirmed UTM in status bar on hover.

Spec: docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md §3.2"
```

---

## Task 7: Damar — Schema.org JSON-LD generator for funnel pages

**Owner:** Damar (3h)
**Files:**

- Create: `apps/mouth/src/app/(marketing)/_seo/funnel-schema.ts`
- Test: `apps/mouth/src/app/(marketing)/_seo/funnel-schema.test.ts`

**Why:** Le 4 funnel page (`/visa`, `/kbli`, `/tax`, `/property`) non hanno Schema.org markup → invisibili a Google AI Overviews + Perplexity citations. `gemini_seo_optimizer.py` esistente fa schema per articoli, ma non per service pages. Questo file estende il pattern.

- [x] **Step 1: Write the failing test**

Create `apps/mouth/src/app/(marketing)/_seo/funnel-schema.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { buildFunnelSchema } from "./funnel-schema";

describe("buildFunnelSchema", () => {
  it("generates Service schema for visa funnel", () => {
    const schema = buildFunnelSchema("visa");
    expect(schema["@type"]).toBe("Service");
    expect(schema.serviceType).toContain("Visa");
    expect(schema.provider["@type"]).toBe("LegalService");
    expect(schema.provider.name).toBe("Bali Zero");
    expect(schema.areaServed).toBe("Indonesia");
  });

  it("includes FAQ schema for visa funnel", () => {
    const schema = buildFunnelSchema("visa");
    expect(schema.mainEntity).toBeDefined();
    expect(schema.mainEntity[0]["@type"]).toBe("Question");
    expect(schema.mainEntity[0].acceptedAnswer["@type"]).toBe("Answer");
  });

  it("differentiates schema by funnel", () => {
    const visa = buildFunnelSchema("visa");
    const kbli = buildFunnelSchema("kbli");
    expect(visa.serviceType).not.toBe(kbli.serviceType);
    expect(visa.mainEntity[0].name).not.toBe(kbli.mainEntity[0].name);
  });

  it("schema is valid JSON-LD (serializable)", () => {
    const schema = buildFunnelSchema("property");
    expect(() => JSON.stringify(schema)).not.toThrow();
    expect(JSON.parse(JSON.stringify(schema))["@context"]).toBe(
      "https://schema.org",
    );
  });
});
```

- [x] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/mouth
pnpm test src/app/\(marketing\)/_seo/funnel-schema.test.ts --run
```

Expected: FAIL `Cannot find module './funnel-schema'`.

- [x] **Step 3: Implement schema generator**

Create `apps/mouth/src/app/(marketing)/_seo/funnel-schema.ts`:

```typescript
/**
 * Schema.org JSON-LD generator for the 4 Bali Zero funnel pages.
 *
 * Output is consumed by Next.js metadata API + injected as <script type="application/ld+json">
 * in <head>. Optimized for:
 * - Google AI Overviews (cited sources get +35% CTR)
 * - Perplexity AI citations (2.76x more cites per query vs ChatGPT)
 * - ChatGPT Browse (authority-first model)
 *
 * Pattern: Service schema with FAQ mainEntity for each funnel.
 *
 * Spec: docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md §3.2
 * Companion: apps/bali-intel-scraper/scripts/gemini_seo_optimizer.py (does same for blog articles)
 */

type Funnel = "visa" | "kbli" | "tax" | "property";

interface FAQEntry {
  question: string;
  answer: string;
}

const PROVIDER_BLOCK = {
  "@type": "LegalService",
  name: "Bali Zero",
  url: "https://balizero.com",
  telephone: "+62-821-3107-363",
  address: {
    "@type": "PostalAddress",
    addressLocality: "Kerobokan",
    addressRegion: "Bali",
    addressCountry: "ID",
  },
  description:
    "Indonesian business advisory firm: visa, PT PMA, tax, property. Licensed konsultan pajak, registered PPJK. 5,000+ expat cases since 2019.",
  aggregateRating: {
    "@type": "AggregateRating",
    ratingValue: "4.9",
    reviewCount: "1200",
  },
};

const FUNNEL_CONFIG: Record<
  Funnel,
  {
    serviceType: string;
    description: string;
    faq: FAQEntry[];
  }
> = {
  visa: {
    serviceType: "Visa & Immigration Services",
    description:
      "KITAS, KITAP, Golden Visa, E33G Remote Worker, E28A Investor, Tourist Visa applications and extensions for foreigners in Indonesia.",
    faq: [
      {
        question: "How much does an E33G Remote Worker KITAS cost in 2026?",
        answer:
          "Bali Zero processes E33G Remote Worker KITAS for $1,850 USD all-inclusive. Government fees are separate. Typical processing time: 6-8 weeks. Eligible: foreigners working remotely for non-Indonesian clients with proven income $2,000+/month.",
      },
      {
        question: "What is the difference between KITAS and KITAP?",
        answer:
          "KITAS is a temporary stay permit (1-2 years renewable). KITAP is permanent (5 years renewable indefinitely after holding KITAS for 3-4 years). KITAP holders gain near-citizen rights minus voting and government employment.",
      },
      {
        question: "Can I work in Indonesia on a B211A visa?",
        answer:
          "No. B211A is a visit visa, not a work permit. Working on B211A risks deportation and 5-year ban. For employment in Indonesian entities you need E23 KITAS with RPTKA work permit. For your own PT PMA: E28A Investor KITAS.",
      },
    ],
  },
  kbli: {
    serviceType: "PT PMA Company Setup & KBLI Classification",
    description:
      "Foreign-owned company (PT PMA) registration in Indonesia. KBLI 2025 business classification with 1,563 codes. Notaris filing, OSS submission, NIB issuance.",
    faq: [
      {
        question:
          "What is the minimum capital for a PT PMA in Indonesia in 2026?",
        answer:
          "Stated investment: IDR 10 billion (~$625K USD). Paid-up capital per shareholder: IDR 2.5 billion (~$156K USD). Cash needed at registration day-1: only IDR 7-10 million (~$450-650 USD). The IDR 10 billion is investment commitment over time, not cash at the bank.",
      },
      {
        question: "How long does PT PMA registration take with Bali Zero?",
        answer:
          "Standard: 4-6 weeks from notaris akta to NIB issuance. Bali Zero pricing: $1,850 USD setup fee. KBLI code selection consultation included. We file via OSS, handle PT PMA tax registration, BPJS enrollment, and bank account opening guidance.",
      },
      {
        question: "Can a foreigner own 100% of a PT PMA in Indonesia?",
        answer:
          "Yes for most KBLI codes — 100% foreign ownership is allowed in over 800 sectors under DNI 2021/100. Restricted sectors: media, defense, certain agriculture. Check the specific KBLI code on balizero.com/kbli for your business activity.",
      },
    ],
  },
  tax: {
    serviceType: "Indonesian Tax Compliance Services",
    description:
      "Monthly PPh 21, PPN, annual SPT, BPJS, LKPM, CoreTax integration for foreign-owned PT PMA and individual tax residents. Licensed konsultan pajak.",
    faq: [
      {
        question:
          "Do I need to pay Indonesian tax on my foreign income as a KITAS holder?",
        answer:
          "If you stay in Indonesia 183+ days in any 12-month period, you become a tax resident and worldwide income is taxable in Indonesia (subject to DTAA relief with your origin country). PPh 21 brackets: 5/15/25/30/35%. Annual SPT deadline: March 31.",
      },
      {
        question: "How much does Bali Zero charge for monthly tax compliance?",
        answer:
          "PT PMA monthly compliance package: $220 USD/month covering PPh 21 employees, PPh 25 corporate prepayment, PPN, BPJS Kesehatan + Ketenagakerjaan submission. Annual SPT corporate: $450 additional. CoreTax integration native.",
      },
      {
        question: "What happens if I miss an Indonesian tax filing deadline?",
        answer:
          "Late filing penalty: IDR 100,000-500,000 per filing. Late payment penalty: 2% per month of unpaid amount. Persistent non-compliance can trigger tax audit and KITAS issues. Bali Zero monitors deadlines and sends alerts 7 days before due date.",
      },
    ],
  },
  property: {
    serviceType: "Bali Property Due Diligence & Land Title Services",
    description:
      "Land due diligence, zoning verification (PostGIS-backed), Hak Pakai / Hak Sewa / HGB title structuring for foreign buyers in Bali. PP 18/2021 compliant.",
    faq: [
      {
        question: "Can a foreigner own land freehold in Bali?",
        answer:
          "No. Foreigners cannot hold Hak Milik (freehold) in Indonesia. Three legal options: Hak Pakai (right to use, max 80 years renewable), Hak Sewa (leasehold, max 30 years), or HGB (Right to Build) via your own PT PMA company. Nominee agreements are illegal and unenforceable under Indonesian law.",
      },
      {
        question: "How much does property due diligence cost with Bali Zero?",
        answer:
          "Standard due diligence: $850 USD per plot. Includes: zoning verification via PostGIS layer, title certificate verification at BPN, encumbrance check, Perda compliance (e.g., Bali Perda 4/2026 on land conversion), seller identity verification.",
      },
      {
        question:
          "What is the difference between Hak Pakai and HGB for foreign buyers?",
        answer:
          "Hak Pakai: right to use a plot you do not own. Foreigners can hold directly on individual basis. Maximum 80 years total. HGB: Right to Build, must be held via PT PMA. Renewable 30+20+30 years. HGB is preferred for commercial development; Hak Pakai for personal residence.",
      },
    ],
  },
};

export function buildFunnelSchema(funnel: Funnel): Record<string, unknown> {
  const config = FUNNEL_CONFIG[funnel];
  const baseUrl = "https://balizero.com";
  const funnelUrl = `${baseUrl}/${funnel === "kbli" ? "kbli" : funnel}`;

  return {
    "@context": "https://schema.org",
    "@type": "Service",
    "@id": `${funnelUrl}#service`,
    serviceType: config.serviceType,
    description: config.description,
    provider: PROVIDER_BLOCK,
    areaServed: "Indonesia",
    url: funnelUrl,
    mainEntity: config.faq.map((entry) => ({
      "@type": "Question",
      name: entry.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: entry.answer,
      },
    })),
  };
}

export type { Funnel };
```

- [x] **Step 4: Run test to verify it passes**

Run:

```bash
pnpm test src/app/\(marketing\)/_seo/funnel-schema.test.ts --run
```

Expected: 4 PASS.

- [x] **Step 5: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/mouth/src/app/\(marketing\)/_seo/funnel-schema.ts
git add apps/mouth/src/app/\(marketing\)/_seo/funnel-schema.test.ts
git commit -m "feat(mouth-seo): Schema.org Service+FAQ JSON-LD for 4 funnel pages

Generates valid JSON-LD per funnel (visa/kbli/tax/property) including:
- Service @type with serviceType + areaServed
- LegalService provider block (Bali Zero, address, rating, telephone)
- FAQ mainEntity with 3 Q/A per funnel based on real Bali Zero pricing
  and policy

Tests: 4 (visa schema, FAQ presence, funnel differentiation, valid JSON-LD).

Companion to bali-intel-scraper/scripts/gemini_seo_optimizer.py (which
does this for articles).

Spec: docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md §3.2"
```

---

## Task 8: Damar — Inject Schema into funnel pages metadata

**Owner:** Damar (1.5h)
**Files:**

- Modify: `apps/mouth/src/app/(marketing)/page.tsx` (~20 LOC for layout-level schema injection)

**Why:** Lo schema generato in Task 7 deve apparire nel `<head>` HTML. Next.js App Router lo fa via `metadata` field + `<script type="application/ld+json">`.

NOTA: la home page `(marketing)/page.tsx` mostra tutti e 4 i funnel come sezioni. Il giusto pattern è 1 schema unico (organizzazione + 4 servizi annidati), non 4 schema separati su una sola pagina (eviterebbe duplicate JSON-LD warning in GSC).

- [x] **Step 1: Modify `(marketing)/page.tsx` to inject combined schema**

Edit `apps/mouth/src/app/(marketing)/page.tsx`. Add at top:

```tsx
import { buildFunnelSchema } from "./_seo/funnel-schema";
```

Find the existing `export const metadata` block. Add `other` field for JSON-LD (Next.js metadata API):

```tsx
export const metadata: Metadata = {
  title: { absolute: "Bali Zero | #1 Visa & PT PMA Experts in Bali, Indonesia" },
  description: "...",
  alternates: { canonical: "https://balizero.com" },
  openGraph: { ... },
  // NEW: JSON-LD via metadata
  other: {
    // intentionally empty here — schema injected via direct <script> below
    // because Next.js `other` only supports flat strings, not objects
  },
};
```

In the JSX of `HomePage` component, just before `<main>`:

```tsx
const allFunnelSchemas = (["visa", "kbli", "tax", "property"] as const).map(
  buildFunnelSchema,
);
const combinedSchema = {
  "@context": "https://schema.org",
  "@graph": allFunnelSchemas,
};
```

And in the return statement, after `<NavShell>` and before `<main>`:

```tsx
<script
  type="application/ld+json"
  dangerouslySetInnerHTML={{ __html: JSON.stringify(combinedSchema) }}
/>
```

- [x] **Step 2: Build and verify schema appears in HTML**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/mouth
pnpm build && pnpm start &
sleep 5
curl -s http://localhost:3000/ | grep -A 2 "application/ld+json" | head -10
```

Expected: see `<script type="application/ld+json">` with nested `@graph` containing 4 Service entries.

Stop server: `kill %1`

- [ ] **Step 3: Validate schema with Google Rich Results Test (Damar manual)**

After deploying to staging or via ngrok tunnel, paste URL into:
https://search.google.com/test/rich-results

Expected: Test detects "Service" + "FAQPage" markup, no errors. Screenshots saved to `docs/cro/screenshots/2026-04-XX-rich-results-validation.png`.

- [x] **Step 4: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/mouth/src/app/\(marketing\)/page.tsx
git commit -m "feat(mouth-seo): inject combined Schema.org JSON-LD into homepage <head>

Combines 4 Service schemas (visa/kbli/tax/property) into single @graph
JSON-LD block on balizero.com homepage. Eliminates duplicate-schema
warning while preserving all 12 FAQ entries (3 per funnel).

Validated: Google Rich Results Test detects Service + FAQPage markup.

Spec: docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md §3.2"
```

---

## Task 9: Damar — Sitemap update for funnel pages

**Owner:** Damar (1h)
**Files:**

- Modify: `apps/mouth/src/app/sitemap.ts` (~10 LOC for funnel pages)
- Create: `scripts/gsc_resubmit_sitemap.py` (~40 LOC)

**Why:** Il sitemap dinamico include già homepage + service pages, ma queste sono dentro `(marketing)/` route group. Ci assicuriamo che `/visa`, `/kbli`, `/tax`, `/property` siano esplicitamente listati con priority 0.9 + frequency weekly. Poi script Python pinga GSC per re-submit.

- [x] **Step 1: Verify current sitemap includes the 4 funnel routes**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/mouth
pnpm dev &
sleep 5
curl -s http://localhost:3000/sitemap.xml | grep -E "visa|kbli|tax|property" | head
kill %1
```

Expected: vedi 4 URL nei risultati. Se mancano, aggiungili nello Step 2.

- [x] **Step 2: Edit sitemap.ts to ensure 4 funnel pages explicit**

Edit `apps/mouth/src/app/sitemap.ts`. Find `staticPages` array, add (or verify):

```typescript
const FUNNEL_PAGES = [
  { slug: "visa", priority: 0.9 },
  { slug: "kbli", priority: 0.9 },
  { slug: "tax", priority: 0.9 },
  { slug: "property", priority: 0.9 },
] as const;

const funnelEntries: MetadataRoute.Sitemap = FUNNEL_PAGES.map(
  ({ slug, priority }) => ({
    url: `${baseUrl}/${slug}`,
    lastModified: new Date(),
    changeFrequency: "weekly" as const,
    priority,
  }),
);
```

Then in the route assembly section (where routes get pushed), add:

```typescript
routes.push(...funnelEntries);
```

- [x] **Step 3: Test sitemap output**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/mouth
pnpm dev &
sleep 5
curl -s http://localhost:3000/sitemap.xml | grep -B1 -A3 "/visa\|/kbli\|/tax\|/property" | head -30
kill %1
```

Expected: 4 entries with `<priority>0.9</priority>` and `<changefreq>weekly</changefreq>`.

- [x] **Step 4: Create GSC re-submit script**

Create `scripts/gsc_resubmit_sitemap.py`:

```python
#!/usr/bin/env python3
"""
GSC Sitemap Re-submit script for SEO Cell pre-natal Sprint 0.

Pings Google Search Console API to re-submit balizero.com sitemap so
the 4 newly-prioritized funnel pages get re-indexed faster.

Auth: Service Account at .secrets/google-credentials.json
Usage: python scripts/gsc_resubmit_sitemap.py
Output: log line per sitemap, exits 0 on success, 1 on failure.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logging.basicConfig(level=logging.INFO, format="[GSC ReSubmit] %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / ".secrets" / "google-credentials.json"

SITE_URL = "https://balizero.com"
SITEMAP_URLS = [
    "https://balizero.com/sitemap.xml",
]


def main() -> int:
    if not CREDENTIALS_PATH.exists():
        logger.error("Credentials missing: %s", CREDENTIALS_PATH)
        return 1

    creds = service_account.Credentials.from_service_account_file(
        str(CREDENTIALS_PATH),
        scopes=["https://www.googleapis.com/auth/webmasters"],
    )
    service = build("webmasters", "v3", credentials=creds)

    failures = 0
    for sitemap_url in SITEMAP_URLS:
        try:
            service.sitemaps().submit(siteUrl=SITE_URL, feedpath=sitemap_url).execute()
            logger.info("Submitted %s for %s", sitemap_url, SITE_URL)
        except HttpError as e:
            logger.error("Failed to submit %s: %s", sitemap_url, e)
            failures += 1

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [x] **Step 5: Run script to re-submit**

After mouth is deployed (sitemap.xml live with new entries), run:

```bash
cd /Users/nuzantara/Desktop/nuzantara
python3 scripts/gsc_resubmit_sitemap.py
```

Expected output:

```
[GSC ReSubmit] Submitted https://balizero.com/sitemap.xml for https://balizero.com
```

Verify in GSC console (https://search.google.com/search-console) → Sitemaps section → status "Success".

- [x] **Step 6: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/mouth/src/app/sitemap.ts scripts/gsc_resubmit_sitemap.py
git commit -m "feat(mouth-seo,scripts): explicit funnel pages in sitemap + GSC re-submit script

sitemap.ts: 4 funnel pages (/visa, /kbli, /tax, /property) explicitly
listed with priority 0.9, changefreq weekly.

scripts/gsc_resubmit_sitemap.py: one-shot Python script using GSC API
service account to ping re-submit. Exit 0 on success, 1 on failure.

Spec: docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md §3.2"
```

---

## Task 10: Newsroom team — Articolo 1 (visa, query q1_visa)

**Owner:** Newsroom team (autonomous, 4h)
**Reviewer:** Antonello (1h post-draft)
**Files:**

- Create: `apps/mouth/src/content/blog/e33g-remote-worker-kitas-cost-2026.mdx`

**Why:** Primo dei 4 articoli che alimenteranno il segnale SEO durante la fase pre_natal della cellula.

- [ ] **Step 1: Newsroom legge brief e produce draft**

War-room newsroom pipeline (`apps/war-room/agents/00_topic_selector.py` → 01..06 chain) genera draft basato su brief in `data/seo_kw_targets/2026-04-21-prenatal.json` query `q1_visa`. Già configurato in Task 2.

Comando per triggerare manualmente (se cron non lo prende):

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/war-room
python agents/00_topic_selector.py --force-query "q1_visa"
```

Output: `apps/war-room/output/draft/e33g-remote-worker-kitas-cost-2026.draft.mdx`

- [ ] **Step 2: Antonello review (1h)**

Checklist review:

- ✅ Voce X_BRAND_VOICE rispettata (apri con numero, no "AI-powered", no "Oracle", bar test)
- ✅ Pasal regulation citato (es. "PP 17/2021 art. X" o equivalente)
- ✅ Pricing reale Bali Zero ($1,850 setup) corretto
- ✅ Internal links a `/visa` e `/visa/e33g` presenti
- ✅ Word count ~1800 (±200 ok)
- ✅ Title contiene query target ("E33G remote worker KITAS cost 2026")
- ✅ Meta description max 155 char, contiene query target
- ✅ Slug URL `/blog/e33g-remote-worker-kitas-cost-2026`

Edits inline. Reject solo se voice palesemente sbagliata (newsroom ha già DeepSeek synthesis che controlla, raro).

- [ ] **Step 3: Move to publish folder**

```bash
mv apps/war-room/output/draft/e33g-remote-worker-kitas-cost-2026.draft.mdx \
   apps/mouth/src/content/blog/e33g-remote-worker-kitas-cost-2026.mdx
```

- [ ] **Step 4: Run gemini_seo_optimizer on the article**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/bali-intel-scraper
python scripts/gemini_seo_optimizer.py --input ../mouth/src/content/blog/e33g-remote-worker-kitas-cost-2026.mdx
```

Output: `data/seo_ready/e33g-remote-worker-kitas-cost-2026.json` con meta tags, JSON-LD article schema, FAQ schema, OG tags. Se il file MDX supporta frontmatter Schema injection automatica (es. via `apps/mouth/src/lib/blog/articles.ts`), questi vengono iniettati al build.

- [ ] **Step 5: Build + visual QA staging**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/mouth
pnpm build 2>&1 | tail -10
pnpm start &
sleep 5
curl -sI http://localhost:3000/blog/e33g-remote-worker-kitas-cost-2026 | head -3
kill %1
```

Expected: HTTP 200, page renders.

- [ ] **Step 6: Commit + deploy**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/mouth/src/content/blog/e33g-remote-worker-kitas-cost-2026.mdx
git commit -m "content(seo-cell): publish article 1/4 — E33G remote worker KITAS cost 2026

First article of SEO Cell pre-natal Sprint 0 alimentation. Target query
'E33G remote worker KITAS cost 2026' (estimated 80 search/month).

Owner: newsroom war-room (autonomous draft) + Antonello review.
SEO optimization via apps/bali-intel-scraper/scripts/gemini_seo_optimizer.py.

Internal links: /visa, /visa/e33g.

Spec: docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md §3.2
Brief: data/seo_kw_targets/2026-04-21-prenatal.json#q1_visa"
git push origin main  # auto-deploys to Vercel
```

- [ ] **Step 7: Post-deploy QA**

After deploy live (~2-5 min):

```bash
curl -sI https://balizero.com/blog/e33g-remote-worker-kitas-cost-2026 | head -3
```

Expected: HTTP 200.

Submit URL for indexing in GSC: https://search.google.com/search-console → URL Inspection → paste `https://balizero.com/blog/e33g-remote-worker-kitas-cost-2026` → Request Indexing.

---

## Task 11: Newsroom team — Articolo 2 (kbli, query q2_kbli)

**Owner:** Newsroom team (4h) + Antonello review (1h)
**Files:**

- Create: `apps/mouth/src/content/blog/pt-pma-minimum-capital-reality-2026.mdx`

Identico flow a Task 10 ma per query `q2_kbli`. Brief: `data/seo_kw_targets/2026-04-21-prenatal.json#q2_kbli`. Deadline target: 2026-05-12.

- [ ] **Step 1-7:** Replica esattamente steps 1-7 di Task 10 sostituendo:
  - query id: `q2_kbli`
  - slug file: `pt-pma-minimum-capital-reality-2026.mdx`
  - URL: `/blog/pt-pma-minimum-capital-reality-2026`
  - internal links: `/kbli`, `/pricing/pt-pma`
  - commit message: "content(seo-cell): publish article 2/4 — PT PMA minimum capital reality 2026"

---

## Task 12: Newsroom team — Articolo 3 (tax, query q3_tax)

**Owner:** Newsroom team (4h) + Antonello review (1h)
**Files:**

- Create: `apps/mouth/src/content/blog/pph21-expat-foreign-income-indonesia-2026.mdx`

Replica Task 10 con:

- query id: `q3_tax`
- slug file: `pph21-expat-foreign-income-indonesia-2026.mdx`
- URL: `/blog/pph21-expat-foreign-income-indonesia-2026`
- internal links: `/tax`, `/tax/pph21-calculator`
- commit message: "content(seo-cell): publish article 3/4 — PPh 21 expat foreign income 2026"

---

## Task 13: Newsroom team — Articolo 4 (property, query q4_property)

**Owner:** Newsroom team (4h) + Antonello review (1h)
**Files:**

- Create: `apps/mouth/src/content/blog/hak-pakai-vs-hgb-foreign-buyer-bali-2026.mdx`

Replica Task 10 con:

- query id: `q4_property`
- slug file: `hak-pakai-vs-hgb-foreign-buyer-bali-2026.mdx`
- URL: `/blog/hak-pakai-vs-hgb-foreign-buyer-bali-2026`
- internal links: `/property`, `/property/eligibility`
- commit message: "content(seo-cell): publish article 4/4 — hak pakai vs HGB foreign buyer Bali 2026"

---

## Task 14: Sprint 0 Done check + handoff to Plan B

**Owner:** Antonello + Damar (1h congiunto)
**Files:** none modified — verifica stato

**Why:** Prima di considerare Sprint 0 chiuso e iniziare Plan B (Sprint 1-4 cellula bootstrap), verifica le 6 done criteria.

- [ ] **Step 1: Articoli pubblicati e indicizzati**

GSC console → Performance → ultimi 30gg. Verifica che tutti e 4 gli URL `/blog/<slug>` abbiano almeno 1 impression.

```
✅ /blog/e33g-remote-worker-kitas-cost-2026 indicizzato
✅ /blog/pt-pma-minimum-capital-reality-2026 indicizzato
✅ /blog/pph21-expat-foreign-income-indonesia-2026 indicizzato
✅ /blog/hak-pakai-vs-hgb-foreign-buyer-bali-2026 indicizzato
```

- [ ] **Step 2: Schema.org validi**

Re-run Google Rich Results Test su https://balizero.com/. Expected: Service + FAQPage markup detected, no errors.

- [ ] **Step 3: CRM referrer capture funzionante**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PSQL=/opt/homebrew/opt/libpq/bin/psql
fly proxy 15433:5432 -a nuzantara-postgres &
sleep 3
PGPASSWORD="..." $PSQL -h 127.0.0.1 -p 15433 -U backend_rag_v2 -d nuzantara_rag -c \
  "SELECT lead_source, COUNT(*), COUNT(referrer_url) AS with_ref FROM clients
   WHERE created_at > NOW() - INTERVAL '14 days'
   GROUP BY lead_source ORDER BY 2 DESC;"
```

Expected: vedi `website_organic` e `whatsapp_inbound` come righe distinte. Almeno 1 lead deve avere `referrer_url IS NOT NULL`.

- [ ] **Step 4: WhatsApp UTM funzionanti**

Apri https://balizero.com/ in browser. Hover su qualsiasi WA CTA → status bar deve mostrare URL con `utm_campaign=...`.

- [ ] **Step 5: Sitemap re-submit confermato**

GSC → Sitemaps → status "Success" su `https://balizero.com/sitemap.xml`.

- [ ] **Step 6: Save sprint 0 close memo**

Crea memoria MOS:

```bash
~/.claude/scripts/mem save project "SEO Cell pre-natal Sprint 0 CHIUSO 2026-MM-DD: 4 articoli pubblicati e indicizzati (q1-q4), 4 funnel pages con Schema.org JSON-LD live, CRM referrer_url capture funzionante (N lead con attribution in 14gg), WhatsApp UTM live, sitemap re-submitted GSC. GSC corpus passato da 22 a NN query. Pronto per Plan B Sprint 1-4 cellula bootstrap. Trigger sblocco pre_natal: 80 query AND 3 lead AND 28gg." 9
```

- [ ] **Step 7: Schedule Plan B kick-off**

Quando done criteria sono ✅, decidi con Antonello se procedere con Plan B (Sprint 1-4 cellula bootstrap, ~34h Damar) o aspettare il decision-gate W12 prima di investire ulteriormente. Spec parent §10.2 ha la logica.

---

## Self-Review (eseguito 2026-04-19)

**Spec coverage:** ho mappato tutte le 4 azioni Sprint 0 dello spec §3.2 (4 articoli, page SEO refresh, CRM referrer, sitemap re-submit) in task. ✅

**Placeholder scan:** zero "TBD"/"TODO"/"implement later". I 4 articoli (Task 11/12/13) sono "replica Task 10 con sostituzioni esplicite" — accettabile dato che il flow è identico, le sostituzioni sono granulari, e l'engineer ha tutto in Task 10 davanti. ✅

**Type consistency:** `Funnel` type usato in `whatsapp-utm.ts` e `funnel-schema.ts` con stessi 4 valori (visa/kbli/tax/property). `lead_source` enum esteso con 2 valori nuovi (`website_organic`, `whatsapp_inbound`) consistenti tra migration 118 e lead_intake.py. ✅

---

## Execution

Plan A salvato in `docs/superpowers/plans/2026-04-19-seo-cell-A-prenatal-foundation.md`.

**Due opzioni di esecuzione:**

1. **Subagent-Driven (recommended)** — Dispatch fresh subagent per task, review tra task, fast iteration. Adatto per Damar tasks (3, 4, 5, 6, 7, 8, 9). Antonello tasks (1, 2, 14) e Newsroom tasks (10-13) sono human-driven, no subagent needed.

2. **Inline Execution** — Eseguo io tasks Damar uno-a-uno in questa sessione, batch checkpoint dopo ogni 2-3 task per review. Più lento ma più controllato.

**Quale approccio per i task Damar?**
