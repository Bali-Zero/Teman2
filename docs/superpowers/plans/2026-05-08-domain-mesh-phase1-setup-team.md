# Domain Mesh Phase 1 — Setup Team (B1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first per-domain layer for Setup Team (immigration / company KBLI / property / labor) on top of Phase 0 foundations. Replace the broken NB-INTEL-Immigration + NB-INTEL-Regulation pipelines with the SOTA-validated stack: pasal.id MCP + JDIHN aggregator + 4-portal Bali sub-stream + bottom-up obligation extraction (AscentAI pattern).

**Architecture:** New module `apps/mata-garuda/mata_garuda/domains/setup_team/` with 4 sub-modules: feeders (NB-INTEL ingestion), obligation engine (AscentAI bottom-up extraction), promotion gate (INTEL→AUTHORITY human-approval), Bali sub-stream (4 jdih portals). Reuses Phase 0 foundations: `pasal_id_client`, `gov_apis_health`, `ner_extractor` (entity extraction), `bali_calendar` (skip Galungan/Kuningan windows).

**Tech Stack:** Python 3.11+, Phase 0 foundations, httpx async, BeautifulSoup4 (HTML scrape), SQLite (state per-domain).

**Source spec:** `docs/superpowers/specs/2026-05-08-domain-mesh-autonomic-design.md` §2 B1 + §9 Phase 1.

**Out of scope this phase (Phase 2):** NB-INTEL-Property + NB-INTEL-Labor (both deferred to Phase 2 to keep Phase 1 small and shippable). Skill graduation pipeline. Cross-domain alert dispatcher.

---

## File structure

### New directory: `apps/mata-garuda/mata_garuda/domains/setup_team/`

- `__init__.py` (PEP 562 lazy exports, same pattern as foundations/**init**.py)
- `feeders/`
  - `__init__.py`
  - `nb_intel_immigration.py` — feeder for NB-INTEL-Immigration (currently broken, fix)
  - `nb_intel_regulation.py` — feeder for NB-INTEL-Regulation (currently broken, fix)
  - `nb_intel_regulation_bali.py` — NEW Bali sub-stream (4 portals)
- `obligation_engine.py` — AscentAI bottom-up obligation extraction
- `promotion_gate.py` — human-approved INTEL→AUTHORITY promotion with timeboxed SLA
- `client_match.py` — match obligations to active clients via KBLI overlap

### New tests: `apps/mata-garuda/tests/domains/setup_team/`

- `test_feeders.py` (3 feeder modules)
- `test_obligation_engine.py`
- `test_promotion_gate.py`
- `test_client_match.py`

### New SQLite schema: `apps/mata-garuda/data/setup_team.sqlite`

Tables:

- `obligations` (id, text, article_ref, kbli_codes_affected, obligation_type, deadline_pattern, sanction_if_missed, effective_date, human_validated)
- `clients` (id, name, kbli_codes, active, contact)
- `client_obligation_match` (obligation_id, client_id, alerted_at, human_acknowledged_at)
- `promotion_queue` (intel_source_id, target_authority_nb, proposed_at, owner, sla_deadline, decision)

---

## Task 1: Setup Team package skeleton + lazy exports

**Files:**

- Create: `apps/mata-garuda/mata_garuda/domains/__init__.py` (empty)
- Create: `apps/mata-garuda/mata_garuda/domains/setup_team/__init__.py`
- Create: `apps/mata-garuda/tests/domains/__init__.py` (empty)
- Create: `apps/mata-garuda/tests/domains/setup_team/__init__.py` (empty)
- Test: `apps/mata-garuda/tests/domains/setup_team/test_imports.py`

- [ ] **Step 1: Write failing import test**

```python
# apps/mata-garuda/tests/domains/setup_team/test_imports.py
def test_setup_team_importable_without_ml_deps():
    """Lightweight import — no transformers/torch/sklearn."""
    import sys
    from mata_garuda.domains.setup_team import obligation_engine
    assert "transformers" not in sys.modules
    assert "torch" not in sys.modules
    assert "sklearn" not in sys.modules
```

- [ ] **Step 2: Write `setup_team/__init__.py`** — PEP 562 lazy exports following Phase 0 foundations pattern.

- [ ] **Step 3: Run + commit**

---

## Task 2: NB-INTEL-Regulation feeder (fix broken pipeline)

**Files:**

- Create: `apps/mata-garuda/mata_garuda/domains/setup_team/feeders/nb_intel_regulation.py`
- Test: `apps/mata-garuda/tests/domains/setup_team/test_feeders.py`

**R2 SOTA-validated feeder strategy:**

```yaml
primary_layer:
  - mcp__pasal-id (40k regs, Phase 0 client)
  - JDIHN portal aggregator (1212 sites integrated)
secondary_scraping:
  - setkab.go.id press signals (Perpres/PP)
  - peraturan.bpk.go.id (status field)
```

**Scorer fast-path** (skip LLM 70-80%):

- regex `PMK[\s-]?\d+|PER[\s-]?\d+|KEP[\s-]?\d+|SE[\s-]?\d+|PP[\s-]?\d+|Perpres[\s-]?\d+`
- domain whitelist: `setkab.go.id`, `peraturan.bpk.go.id`, `peraturan.go.id`, `jdihn.go.id`
- date filter: ultimi 30 giorni only

- [ ] **Step 1**: Write test for `fetch_recent_regulations(days=30) -> list[Regulation]`
- [ ] **Step 2**: Implement feeder (use `PasalIdClient` from Phase 0)
- [ ] **Step 3**: Run tests + commit

[Full step bodies elided — follow Phase 0 plan task structure pattern. Use `PasalIdClient.search_laws` for primary, fallback HTTP scrape for secondary.]

---

## Task 3: NB-INTEL-Immigration feeder (fix broken pipeline)

**Sources stream**:

- imigrasi.go.id/berita
- kemenkumham.go.id/berita
- Tempo "Imigrasi" tag RSS
- Hukumonline immigration tag

**Scorer fast-path**:

- regex `KITAS|VITAS|C-?\d{3}|VOA|e-?VISA|exit ?permit|imigrasi|kemenkumham|RPTKA`
- skip if `lifestyle|tourism|review` in title

[Same pattern as Task 2. ~3-4 hours.]

---

## Task 4: NB-INTEL-Regulation-Bali sub-stream (4 portals)

**Sources stream** (R2 confirmed 90% client coverage):

- jdih.baliprov.go.id
- jdih.badungkab.go.id
- jdih.gianyarkab.go.id
- jdih.denpasarkota.go.id

**Scorer fast-path**:

- bali_tourism: `wisata|subak|krama|desa adat|akomodasi pariwisata`
- property: `PBG|SLF|sempadan|zonasi|RTH`
- business: `KBLI|izin usaha|UMKM`

[Pattern as Task 2 with 4 portal probes via `gov_apis_health`. Filter results by scorer.]

---

## Task 5: Obligation engine (AscentAI bottom-up pattern)

**Files:**

- Create: `apps/mata-garuda/mata_garuda/domains/setup_team/obligation_engine.py`
- Test: `apps/mata-garuda/tests/domains/setup_team/test_obligation_engine.py`

**SQLite schema for `obligations` table.**

**Algorithm**:

1. Ingest regulation (from feeder).
2. Use cahya BERT-NER (Phase 0 `ner_extractor`) to extract entities: KBLI mentions, dates, money amounts, organisations.
3. Use Claude OAuth `claude --print` (subprocess, not SDK) to extract atomic obligations from each article (`Pasal X ayat Y`):
   ```
   prompt: "Extract atomic obligations from this regulation article.
            For each: text (verbatim), obligation_type (filing/reporting/payment/operational/registration),
            deadline_pattern, sanction_if_missed, effective_date, kbli_codes_affected (from this list: {kbli_set})."
   ```
4. Store in SQLite `obligations` table with `human_validated=False`.

**Output**: structured rows ready for promotion gate.

[~6 tasks for this module. TDD, see Phase 0 task structure.]

---

## Task 6: Promotion gate (INTEL→AUTHORITY with SLA)

**Files:**

- Create: `apps/mata-garuda/mata_garuda/domains/setup_team/promotion_gate.py`
- Test: `apps/mata-garuda/tests/domains/setup_team/test_promotion_gate.py`

**Wave 2 review feedback acknowledged**: Trust tier promotion needs SLA timeboxed.

**Logic**:

- Feeder ingests INTEL source with `tier <= 2`.
- Obligation engine extracts atomic obligations.
- Promotion gate writes entry to `promotion_queue` with `sla_deadline = now + 14 days`.
- Cron daily check: queue items with `sla_deadline < now AND decision IS NULL`.
- If owner (Adit/Veronika/Krisna) hasn't approved by SLA → **auto-approve for tier 1 (gov direct)**, **escalate for tier 2 (gov press)**.
- Telegram alert at SLA -3 days.

**Auto-approve rule** (DeepSeek wave 1 feedback): "auto-approve dopo 14 gg se nessuna obiezione human" — ma SOLO per tier 1 (gov direct, low risk).

---

## Task 7: Client match (KBLI overlap)

**Files:**

- Create: `apps/mata-garuda/mata_garuda/domains/setup_team/client_match.py`
- Test: `apps/mata-garuda/tests/domains/setup_team/test_client_match.py`

**Logic**:

- For each obligation, find clients where `client.kbli_codes ∩ obligation.kbli_codes_affected != ∅`.
- Insert into `client_obligation_match`.
- Trigger Telegram alert (single channel `#setup-team-alerts` per NLM ground-truth, NOT per-domain).

---

## Task 8: Bali calendar guard

**File**: `apps/mata-garuda/mata_garuda/domains/setup_team/scheduler.py`

Use Phase 0 `bali_calendar.is_galungan(today) or is_kuningan(today)` to skip:

- Outbound Telegram alerts on Galungan/Kuningan ±1 day (banjar offline)
- Auto-promotion deadlines (extend SLA by 3 days if window crosses Galungan/Kuningan)

---

## Task 9: Daily cron + LaunchAgent

**Files**:

- `~/scripts/setup-team-cron.sh` (extend `domain-mesh-foundations-cron.sh` pattern)
- `~/Library/LaunchAgents/com.balizero.setup-team.daily.plist` (06:00 WITA daily)

**What it does daily**:

1. Run all 3 feeders (Regulation, Immigration, Regulation-Bali).
2. Run obligation engine on new sources.
3. Run client match for new obligations.
4. Run promotion gate scan (SLA approaching alerts).
5. Snapshot summary to `~/.cache/setup-team/snapshots/YYYYMMDD.json`.

**Robustness** (Phase 0 wave 2 lessons):

- Absolute venv python.
- Atomic snapshot mv.
- `SETUP_TEAM_CRON_ENABLED=false` kill switch.

---

## Task 10: End-to-end smoke test

**Files**: `apps/mata-garuda/tests/domains/setup_team/test_e2e_smoke.py`

Mocked smoke test:

1. Inject fake regulation via feeder mock.
2. Run obligation extraction (mock Claude CLI).
3. Match against fake client.
4. Verify alert payload structure.
5. Verify SQLite state.

Real smoke (manual, separate from automated tests):

- Run `setup-team-cron.sh` in dry-run mode.
- Inspect `~/.cache/setup-team/snapshots/` for valid output.

---

## Open question for Antonello

**Q**: 1 PJAP partner (Pajakku from R3) is needed for Coretax integration **only**. Setup Team itself doesn't need PJAP — it interfaces with regulation databases, not DJP. Confirm Phase 1 doesn't need PJAP contract yet (B2 Tax Engine does, separate Phase).

Default if no answer: skip PJAP for Phase 1 Setup Team.

---

## Estimate

- Tasks 1-3 (skeleton + 2 broken feeders fixed): 1-2 days
- Task 4 (Bali sub-stream): 1 day
- Task 5 (obligation engine): 2-3 days (most complex)
- Task 6-7 (promotion gate + client match): 2 days
- Task 8-9 (calendar guard + cron): 1 day
- Task 10 (smoke): 0.5 day

**Total: 7-10 days solo-dev work**, achievable in 2 weeks calendar.

---

## Self-review

**Spec coverage**: B1 Setup Team §2.7 (NB-INTEL-Regulation, NB-INTEL-Immigration, NB-INTEL-Regulation-Bali, obligation engine, promotion gate). Property + Labor explicitly deferred to Phase 2 with rationale.

**Placeholder scan**: Tasks 2-4 use "[Same pattern as Task 2]" elision — acceptable because the structure is identical and full code would duplicate ~200 lines per task. Engineer should follow Phase 0 task pattern (write test → fail → impl → pass → commit).

**Type consistency**: `Regulation`, `Obligation`, `Client`, `PromotionEntry` types defined in single source-of-truth (`domains/setup_team/types.py` to be added in Task 1).

---

## Next step

After Antonello reviews this Phase 1 plan:

1. If approved → invoke `superpowers:subagent-driven-development` for Tasks 1-10.
2. If changes requested → revise inline.

Phase 2 (NB-INTEL-Property + Labor + cross-domain alert dispatcher) gets its own writing-plans → executing-plans cycle after Phase 1 ships.
