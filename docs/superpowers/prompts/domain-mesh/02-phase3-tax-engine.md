# Phase 3 — Tax Engine (B2)

> **Prerequisiti**: Phase 1+2 mergiate. Setup Team domain operativo.
>
> **Stima**: 10-14 giorni solo-dev (B2 è il dominio più complesso — Coretax instability + PJAP partner contract).
>
> **Pre-azione richiesta a te (Antonello)**: contratto Pajakku PJAP (~€85/mese) o PajakExpress. Senza, il dominio funziona solo in dry-run mode.

---

## PROMPT (drop-in)

Continuiamo il Domain Mesh. Phase 3: implementa il dominio **Tax Engine (B2)**.

Prima di tutto, leggi:

1. `docs/superpowers/specs/2026-05-08-domain-mesh-autonomic-design.md` §3 B2 (genesi Tax Engine completa)
2. `docs/superpowers/specs/2026-05-08-domain-mesh-research/r3-djp-coretax-tax-tech-2026-05-08.md` (R3 SOTA, 8 sezioni dettagliate su DJP/Coretax/PJAP)
3. `docs/superpowers/plans/2026-05-08-domain-mesh-phase1-setup-team.md` (pattern Phase 1)
4. `apps/mata-garuda/mata_garuda/domains/setup_team/` (template completo da imitare)

Verifica anche se Antonello ha già firmato il contratto Pajakku (PJAP). Cerca:

```bash
grep -ri "PAJAKKU_API_TOKEN\|PJAP" ~/.nuzantara-secrets.env ~/.nuzantara-backend-secrets.env 2>/dev/null
```

Se token presente → modalità live. Se assente → modalità dry-run (mock submit, log ma non chiama Coretax).

Poi `superpowers:brainstorming` (verifica se le decisioni B2.a + B2.b del design sono ancora valide), `superpowers:writing-plans`, `superpowers:subagent-driven-development`.

### Scope

**Domains/tax/**init**.py** (PEP 562 lazy) + sotto-moduli:

1. **Feeders (NB-INTEL ingestion, simile pattern Setup Team)**:
   - `feeders/nb_intel_tax.py`: pajak.go.id/siaran-pers + jdih.kemenkeu.go.id + setkab Kemenkeu filter + Ortax + DDTC
   - `feeders/nb_intel_coretax.py` **DEDICATO** (R3 conferma instability strutturale): DJP Coretax incident bulletin + Twitter community + Reddit r/PersonalFinanceIndonesia + KIP DJP press

2. **PJAP adapter**:
   - `pjap_client.py`: abstraction layer su Pajakku (primary) + PajakExpress (fallback). Interface `PJAPClient` con metodi `submit_faktur`, `submit_e_bupot`, `submit_efiling`, `submit_spt`. Retry policy exponential backoff max 5, escalation Telegram Veronika su >5 fail.
   - `coretax_incident_taxonomy.py`: enum dei 12 incident types da R3 (login_fail_face_verif, save_invalid_faktur, error_404_mass, error_500_api_queue, period_spt_default_off, upload_attachment_fail, nik_validation_dukcapil_timeout, digital_cert_refresh_expired, pph_21_23_ebupot_xml_broken, faktur_xml_import_bug, approval_workflow_stuck, browser_specific_ui_break)
   - `workaround_library.py`: SQLite `~/Desktop/nuzantara/apps/mata-garuda/data/coretax_workarounds.sqlite` con tabella `incident_workarounds` (incident_type, workaround_text, last_verified, screenshots_dir)

3. **Tax engine layers** (R3 workflow automation map, 6 layer):
   - `engine/L1_ingestion.py`: OCR fatture (foundations qwen2.5vl:7b via Ollama subprocess, NOT Anthropic SDK), parse e-bupot XML, parse fattura PDF
   - `engine/L2_classification.py`: tax code classifier (rule-based + LLM via `claude --print` for edge cases). KBLI → tax obligations mapping (federation con NB-3 setup_team)
   - `engine/L3_compute.py`: PPh 21/23/26/25 deterministic, PPN output-input
   - `engine/L4_equalization.py`: PPN ↔ SPT Tahunan reconciliation, variance flag if > 5% → Veronika alert
   - `engine/L5_submission.py`: chiama PJAPClient con retry + incident taxonomy detection
   - `engine/L6_human_gate.py`: Veronika sign-off final (HARD), no auto-submit per audit response

4. **Promotion gate** (riusa pattern setup-team, ma PIÙ STRINGENTE per tax):
   - Solo tier ≤ 1 (gov direct: pajak.go.id, kemenkeu.go.id, setkab.go.id) può triggherare promotion
   - **NO auto-approve dopo SLA** (Veronika click obbligatorio anche se tier 1 — accuracy fiscale > convenience)

5. **Quote engine grounding** (R3 Sink 3):
   - `quote_engine.py`: input cliente profile + KBLI + complexity factors, output draft XLSX/PDF
   - Grounding: NB-4 (procedure), NB-3 (KBLI), NB-WORKBENCH casi simili (Marta storia)
   - Sign-off Veronika via signed-by field

6. **Cron LaunchAgent**:
   - `infra/scripts/tax-engine-cron.sh`
   - `infra/launchagents/com.balizero.tax-engine.daily.plist`
   - Schedule: 07:00 WITA (dopo Setup Team 06:00)
   - Kill switch: `TAX_ENGINE_CRON_ENABLED=false`
   - Dry-run mode: `TAX_ENGINE_DRY_RUN=true` (default per testing senza PJAP token)

### Sink (output)

1. Telegram `#tax-alerts` — KEP/PMK/Coretax incidents
2. CRM tax workflow trigger
3. Quote engine grounding draft
4. Mouth content tax-vertical (NB-INTEL-Tax → article generator)
5. Coretax workaround library Veronika quick-access
6. **NEW**: IndoTax-LLM positioning (R3 discovery: gap competitivo, no public Indonesian tax LLM esiste)

### Cose specifiche da R3

- **Zero Coretax public API**: NON tentare di chiamare Coretax direttamente. Solo via PJAP.
- **Coretax instability strutturale**: 18/21 issues ancora pending da MUC May 2025. NB-INTEL-Coretax dedicato è giustificato.
- **Indonesian tax-LLM gap**: posizionamento "Bali Zero machine-augmented" vs joki phenomenon. Aggiungilo al sink dispatcher per articoli editorial.
- **PajakExpress unico con pricing pubblico** (~Rp 1.5jt/mese stima); Pajakku più maturo ma richiede sales contract.

### Regole forti

- **Anthropic SDK BANNED**. Solo `claude --print` subprocess. (mata-garuda CLAUDE.md)
- Lazy imports PEP 562.
- TDD per task: 80+ test attesi (engine layers + feeders + PJAP adapter + workaround lib).
- Cron PATH include `/Users/nuzantara/.local/bin`.
- Atomic mv snapshot.
- Branch hijack scar: `git push` post commit.
- Cicatrice etica: PJAP credenziali in `~/.nuzantara-secrets.env`, MAI nel repo.

### External review wave (mandatory per dominio Tax — alta accuracy)

Dopo l'implementazione, lancia 3-LLM wave (Codex + DeepSeek + NotebookLM NB-1) **prima** del merge. Il pattern Phase 1 ha trovato 9 bug in 3 wave; per Tax (compliance fiscale) il rischio è più alto. Prompt review focus su:

- PJAP adapter retry semantics
- Coretax workaround library semantic accuracy (cita PMK/PER source per ogni workaround)
- Promotion gate stringency (no auto-approve)
- L4 equalization variance threshold (5% troppo basso? troppo alto?)

### Pre-condizioni per merge

- 80+ test green
- Live PJAP smoke test (con token o dry-run)
- Veronika consultata su workflow L1-L6 (non implementare quello che lei rifiuta)
- `~/logs/tax-engine/tax-engine-daily-YYYYMMDD.log` mostra summary pulito

### Pre-azione richiesta a Antonello

**PRIMA di partire questa fase**:

1. Decidi PJAP partner (Pajakku vs PajakExpress) e firma contratto. Senza, dry-run only.
2. Conferma con Veronika che il workflow L1-L6 + Veronika sign-off finale è compatibile col modo in cui lei lavora oggi (Marta Reyes case ha mostrato 4 cicatrici evitate, non aggiungerne nuove).
3. Decidi B2.a (NB-INTEL-Coretax dedicato vs sub-tag) — R3 conferma fortemente "dedicato".
4. Decidi B2.b (Quote consistency detector attivo/silent/off) — default suggerito: silent (logga ma non alert real-time).

Procedi quando hai conferma su questi 4 punti.
