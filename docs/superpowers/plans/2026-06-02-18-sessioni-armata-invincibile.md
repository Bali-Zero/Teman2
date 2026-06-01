# 🎖️ 18 SESSIONI MASSIVE — Armata Invincibile

> Ordini di battaglia. Ogni blocco = 1 prompt pronto da copia-incollare in una sessione
> Claude Code NUOVA. Quella sessione diventa un ORCHESTRATORE che spawna le sue armate.
> Tu (Antonello) lanci le sessioni. Il Generale (sessione-comando separata) converge alla fine.
>
> Topologia validata SOTA: `research/operations/2026-06-02-sota-army-topology.md`
> (Anthropic eng 90.2%, arXiv MAST, Cognition, towardsdatascience 17.2×→4.4×).

---

## 📐 ARCHITETTURA DI COMANDO

```
IL GENERALE (sessione-comando) — non combatte. Riceve i 18 FROZEN. Converge.
   └─ 18 SESSIONI = 18 ORCHESTRATORI (1 lead Claude ciascuno)
        └─ ogni sessione, per FASE, fa fan-out 3-5 worker (oltre → plateau)
           ASSALITORI → ANALISTI → SPAZZINI → MECCANICO (pipeline, no barriera)
```

**Le 3 leggi anti-auto-distruzione (in OGNI prompt):**
1. Mai peer-to-peer tra worker — coord solo via file nel proprio worktree.
2. Worker ricevono il brief COMPLETO della sessione (anti-Cognition).
3. Git single-threaded — 1 solo meccanico serializza commit/push; assalitori/analisti
   parallelizzano breadth, git no.

**Stop point (TUTTE):** commit → push branch feature → PR draft → **STOP pre-merge**.
Mai merge su main. Mai `--force`. Mai `git reset --hard` fuori dal proprio worktree.
Mai toccare `~/Desktop/nuzantara` (main) né `~/Desktop/nuzantara-deploy`.

**Secret:** autonomo su tutto il reversibile-locale (chmod 0400, secret→Keychain,
checklist rotazione). Rotazione token esterni (gh/Fireworks/Fly) = NEEDS-ANTONELLO
(hard-to-reverse, outward-facing).

---

## 🖥️ DOVE LANCIARE + QUALE MODELLO

| Macchina | Slot LLM | Sessioni assegnate | Modello orchestratore |
|---|---|---|---|
| **Pro 48GB** | Claude slot1 `antonellosiano@` | Prod-touch + OSINT: S5, S7, S10, S14 | `opus` xhigh |
| **Mini 24GB** | Claude slot2 `~/.claude-acct2/` | Long-running/batch: S6, S8, S13, S16 | `opus` (acct2) |
| **M5 Air 24GB** | thin-client | Leggere/coord: S2, S11, S15 | `sonnet` + fan-out Codex |
| **GPT-5.5 Pro x20** | Codex illimitato | Worker di TUTTE + code-heavy lead: S1, S3, S4, S9, S12, S18 | `codex exec --sandbox workspace-write` |
| **agy AI Ultra** | Gemini 3.1 Pro 1M | Ingestion: S6/S13/S14/S16 | `agy -p` |

**Comandi slot:**
```bash
# Slot 1 (Pro)        cd ~/Desktop/nuzantara && claude
# Slot 2 (Mini/2a fin) claude-acct2     # CLAUDE_CONFIG_DIR=$HOME/.claude-acct2 claude
# M5                   sessione locale M5 o ssh
```
Primo comando dentro ogni sessione: `/model opus` o `/model sonnet`.

**Lane valide** (broker allow-list): `wr2 wr3 infra docs db cicatrix-fix mouth intel cell
organism backend-rag frontend ops mata-garuda`. Usa queste + task-id univoco.

---

## 🌊 ONDE (dipendenze)

- **ONDA 1** (6 parallele, zero dipendenze): S1, S4, S5, S6, S15, S16
- **ONDA 2** (6, usano output Onda 1): S2, S3, S7, S10, S13, S14
- **ONDA 3** (6): S8, S9, S11, S12, S17, S18

Max simultanee consigliato: **5-6** (pacing — lessons_wave_pacing). Le Codex-heavy
(S1,S3,S9,S18) pesano poco su Claude → puoi sovrapporle.

---

# ═══════════════ PROMPT PRONTI ═══════════════

Ogni prompt include già: lane+worktree, le 3 leggi, lo stop point, il dominio.
**Aggiungi tu come prima riga:** `/model opus` (o sonnet) secondo la tabella.

---

## 🌊 ONDA 1

### ▶ S1 — events-outbox: i 6 canali morti  `[Codex-heavy lead / opus]`

```
Sei l'ORCHESTRATORE della sessione S1 "events-outbox-resurrection". Procedi in piena
autonomia in loop senza chiedere conferma ad Antonello, fino allo stop point.

PASSO 0 worktree isolato (OBBLIGATORIO prima di toccare qualsiasi cosa):
  python scripts/agent_start.py --lane backend-rag --task-id s1-events-outbox
  cd .worktrees/backend-rag-s1-events-outbox
  export BRANCH_EXPECTED=$(git branch --show-current)

LE 3 LEGGI ANTI-AUTODISTRUZIONE: (1) i tuoi worker non parlano tra loro, coordinano solo
via file in questo worktree; (2) ogni worker riceve il brief COMPLETO qui sotto, non
frammenti; (3) git single-threaded: UN solo meccanico committa, serializzato.

MISSIONE: events_outbox ha ~492 eventi stale >24h su canali in gate-off da metà maggio:
client_changed (215h, consumer morto), practice_changed (38h parziale),
cell_pulse_sustained_red (64h), intel_lake_event (378h), war_room_event (378h).
whatsapp_message_received gate-off è ATTESO (wa-mirror local-only cutover) — benigno, NON
toccare. Fonte verità: research/operations/2026-05-31-system-audit-FROZEN.json
§prod_data_postgres.

TOPOLOGIA (orchestrator-worker, pipeline):
- ASSALITORI (Workflow tool, fan-out 1 per canale = 5 paralleli, schema {channel,
  expected_consumer, death_cause, last_alive_ts, resurrection_plan, replay_risk}): ogni
  assalitore (a) trova il daemon/handler che DOVREBBE consumare quel canale (grep
  apps/backend-rag/backend/ + infra/launchagents/), (b) verifica perché è morto
  (launchctl print, log mtime, git log file handler), (c) propone resurrection.
- ANALISTI (adversarial, dopo ogni assalitore): 1 devils-advocate (puoi usare
  `codex exec --sandbox read-only` come spalla) che cerca il RISCHIO DI REPLAY — eventi
  16-giorni-vecchi replayati possono causare doppi side-effect (doppia email? doppio
  edge KG? doppia notifica)? Verdetto SAFE/UNSAFE per canale.
- SPAZZINI: 1 agente che ripulisce il worktree (rimuove file temp/scratch, verifica
  niente PII nei file di output).
- MECCANICO (1 solo, serial): research/operations/S1-outbox-resurrection-FROZEN.json
  (tabella 5-canali × verdetto) + report .md. git add -A . (scope worktree) →
  git commit → git push origin $BRANCH_EXPECTED → gh pr create --draft → STOP.

VINCOLI: query Postgres SOLO read-only via postgres-nuzantara MCP. Mai mutation. Il fix
vero (riavviare consumer / prune cron) è NEEDS-ANTONELLO — produci lo spec eseguibile +
il rischio, NON eseguire. events_outbox è unbounded fino a phase-3 prune.

OUTPUT FINALE: il FROZEN.json + PR draft. Poi: python ../../scripts/agent_start.py
--release s1-events-outbox (solo se branch pushato).
```

### ▶ S4 — Worktree storm + broker enforcement (W62)  `[M5 / sonnet, fan-out Codex]`

```
ORCHESTRATORE sessione S4 "worktree-broker-enforcement". Autonomia piena in loop, no
conferme, fino allo stop point.

PASSO 0:
  python scripts/agent_start.py --lane infra --task-id s4-broker
  cd .worktrees/infra-s4-broker
  export BRANCH_EXPECTED=$(git branch --show-current)

LE 3 LEGGI: no peer-to-peer worker; brief completo a ognuno; git single-threaded.

MISSIONE: cicatrix W62 — broker agent_start.py ha TTL=60min ma --cleanup è OPT-IN,
nessun cron lo lancia, i subagent non chiamano --release → worktree storm con WIP reale
non committato (danger zone "untracked-files-lost", scar W-family).

⚠️ PASSO 1 CRITICO PRIMA DI TUTTO — SALVA IL WIP ALTRUI: ispeziona ogni worktree stale in
.worktrees/ (git -C <wt> status). Se trovi WIP non committato reale (.py/.ts modificati o
NEW untracked), committalo su un branch dedicato di salvataggio PRIMA di qualsiasi cleanup
— altrimenti è perdita. NON fare git stash senza -u (cancella untracked). Documenta cosa
hai salvato.

TOPOLOGIA con TDD (test prima del codice):
- ASSALITORI (Workflow, fan-out): 1 agente-audit per le 4 ANTIBODY W62.
- ANALISTI: verifica ogni fix con test reale (pytest). Codex spalla adversarial.
- IMPLEMENTAZIONE (TDD, serial): (1) LaunchAgent cleanup daily WIP-safe (skip worktree
  dirty o mtime<10min), (2) hook orphan-detection in agent_start.py --list (WARN su
  worktree >2× TTL), (3) tests/integration/test_no_stale_worktrees.py (fail CI se
  mtime>24h), (4) broker-aware spawn convention documentata.
- SPAZZINI: pulisci worktree scratch.
- MECCANICO (1, serial): commit → push → PR draft → STOP.

VINCOLI: NON cancellare worktree con WIP non salvato. --cleanup è già WIP-safe — non
romperlo. OUTPUT: research/operations/S4-broker-FROZEN.json + PR con 4 fix + nota WIP
salvato. Poi --release.
```

### ▶ S5 — Secret in chiaro nei plist (P0 SECURITY)  `[Pro OBBLIGATORIO / opus, Ollama]`

```
ORCHESTRATORE sessione S5 "plist-secret-hardening" — DEVE girare sul Pro (OSINT/secret,
Symbiosis Law 2). Autonomia piena in loop sul reversibile, no conferme.

PASSO 0:
  python scripts/agent_start.py --lane infra --task-id s5-plist-secrets
  cd .worktrees/infra-s5-plist-secrets
  export BRANCH_EXPECTED=$(git branch --show-current)

LE 3 LEGGI. + LEGGE SECRET: nessun worker tocca il cloud. Reasoning solo locale (Ollama
qwen3.5:9b se serve). MAI loggare il VALORE di un secret — solo nome-chiave + path.

MISSIONE: residuo scar 2026-04-29 + audit S4: plist world-readable con secret in chiaro
(wa-dashboard-m1 DB url 0644, skills-bridge-consumer API key, + ghp_/FIREWORKS/SCRAPER
tokens citati in session_2026_05_31). I 644 sono leggibili da qualsiasi processo.

TOPOLOGIA:
- ASSALITORI (locali, fan-out): scansiona ~/Library/LaunchAgents/com.{nuzantara,balizero,
  cell}.*.plist per EnvironmentVariables con pattern secret (token|key|password|
  url-con-credenziali). Lista nome-chiave × plist × permessi attuali (SENZA valori).
- ANALISTI: per ognuno classifica blast-radius (se ruoti sbagliato cosa si rompe?).
  GH_TOKEN/DATABASE_URL = alto (spegne CI/deploy). Altri = basso.
- AZIONE AUTONOMA (reversibile): chmod 0400 sui plist con secret. Dove possibile, sposta
  il secret a Keychain o env-file fuori-plist e referenzia. Questo è autonomo.
- SPAZZINI: verifica nessun file di output contenga un valore-secret. Pulisci scratch.
- MECCANICO (1, serial): research/operations/S5-plist-secrets-FROZEN.json (lista
  secret×plist×azione, SENZA VALORI) + rotation checklist (NEEDS-ANTONELLO per i token
  esterni). git add SOLO file safe (mai un file con secret). commit → push → PR draft →
  STOP.

VINCOLI: chmod è autonomo. Rotazione token esterni (gh secret set / fly secrets set) =
NEEDS-ANTONELLO. NON committare MAI un valore-secret. OUTPUT: FROZEN + chmod applicati +
checklist. Poi --release.
```

### ▶ S6 — Ricerca regolatoria deep: domini affamati  `[Mini acct2 / opus, agy+NB]`

```
ORCHESTRATORE sessione S6 "regulatory-deep-fill". Autonomia piena in loop, no conferme.

PASSO 0:
  python scripts/agent_start.py --lane docs --task-id s6-regulatory
  cd .worktrees/docs-s6-regulatory
  export BRANCH_EXPECTED=$(git branch --show-current)

LE 3 LEGGI.

MISSIONE: research/legal/ ha 1 file, property/ 2, tax/ 6 — sotto-documentati per
un'agenzia immigration/company/tax/property. Riempi i gap con ricerca ground-truth.

TOPOLOGIA MULTI-LLM (pattern deep-researcher, NON Claude-only):
- ASSALITORI INGESTION (agy Gemini 3.1 Pro 1M context): ingerisci i PDF/fonti regolatori
  long-context. Fan-out per dominio.
- GROUND-TRUTH (NotebookLM bipolar verifier): NB-2 visa / NB-3 company/KBLI / NB-4 tax /
  NB-5 property. Verifica ogni claim contro NB. MAI 4-LLM council su NB (sono autorità).
- ANALISTI (DeepSeek V4 Pro ESPLICITO, mai -reasoner alias): math/legal-numeric (tax
  projection, deadline). + devils-advocate su contraddizioni.
- SINTESI (Claude opus): per OGNI dominio gap, 1 ricerca ≥400 parole + ≥3 fonti.
  Temi: legal (PT PMA, nominee ban, BKPM), property (Hak Pakai vs HGB vs leasehold,
  foreigner ownership 2025), tax (estendi PMK 131/2024 PPN già in mem → PPh, withholding,
  BUT). VERIFICA con NB cosa manca davvero prima di scrivere.
- MECCANICO (1, serial): file in research/<domain>/2026-06-02-<slug>.md con frontmatter
  (date/domain/sources). property → push NB-5 via MCP (convenzione §15). Altri domini:
  NON toccare NB curati. commit → push → PR draft → STOP.

OUTPUT: 4-6 file research + research/operations/S6-regulatory-FROZEN.json (indice). --release.
```

### ▶ S15 — Symbiosis & cicatrici: organismo profondo  `[M5 / sonnet, fan-out Codex]`

```
ORCHESTRATORE sessione S15 "symbiosis-deep-audit". Autonomia piena in loop, no conferme.

PASSO 0:
  python scripts/agent_start.py --lane organism --task-id s15-symbiosis
  cd .worktrees/organism-s15-symbiosis
  export BRANCH_EXPECTED=$(git branch --show-current)

LE 3 LEGGI. + sii FORENSE, anti-celebrativo (lessons_close_out_numbers_unverified): ogni
numero derivato da tool IN QUESTO TURN, mai ricordato.

MISSIONE: audit profondo dell'organismo. Le 8 Leggi Symbiosis rispettate nel codice reale?
Le cicatrici "archiviate" DAVVERO risolte o nascoste? I 167 LaunchAgent — quanti zombie/
flapping/no-KeepAlive (W61 storm)? Questo è il "ricordare cose vecchie dimenticate".

TOPOLOGIA (Workflow fan-out):
- ASSALITORI (3-5 paralleli): (a) Symbiosis-compliance — lint_symbiosis_promises.py +
  verifica ogni Legge nel codice; (b) cicatrix-resurrection — rileggi
  cicatrix-scars-archive.md, verifica sul disco/prod che ogni RESOLVED sia ANCORA risolto
  (re-test empirico, non fede); (c) launchagent-health — 167 plist (KeepAlive,
  binary_missing, flapping via launchctl print active_count).
- ANALISTI: Codex devils-advocate sui falsi-positivi (un daemon "morto" per log-mtime può
  essere vivo — usa launchctl print authoritative, non ps/log).
- SPAZZINI: pulisci scratch.
- MECCANICO (1, serial): research/operations/S15-symbiosis-FROZEN.json + lista cicatrici
  RIAPERTE (se ce ne sono — usa la skill `scar` per appendere, APPEND-ONLY no auto-commit).
  commit → push → PR draft → STOP.

VINCOLI: read-only diagnosi su prod. Riaprire una cicatrix = entry strutturata, non fix.
OUTPUT: FROZEN + organism-truth aggiornato. --release.
```

### ▶ S16 — SOTA multi-agent architecture 2026  `[Mini acct2 / opus, agy+WebSearch]`

```
ORCHESTRATORE sessione S16 "sota-multiagent-2026". Autonomia piena in loop, no conferme.

PASSO 0:
  python scripts/agent_start.py --lane docs --task-id s16-sota
  cd .worktrees/docs-s16-sota
  export BRANCH_EXPECTED=$(git branch --show-current)

LE 3 LEGGI. + numeri prima (Legge 7): ogni tecnica proposta con benchmark/evidenza, non
"sembra meglio".

MISSIONE: esiste research/operations/2026-05-24-sota-multi-agent-repo-architecture-
synthesis.md + il fresco 2026-06-02-sota-army-topology.md. Aggiorna allo stato-dell'arte
2026: cosa c'è di nuovo in orchestration multi-agente oltre il nostro broker+worktree+
orchestrator-worker? Cosa adottare DI CONCRETO?

TOPOLOGIA:
- ASSALITORI (deep-research skill + agy long-context per ingerire paper/repo SOTA +
  WebSearch/WebFetch, fan-out multi-modale): cerca per angolo (topology, failure-mode,
  coordination-primitive, benchmark agent-count).
- ANALISTI (adversarial, 2/3 vote): verifica ogni claim — no hype, fonti primarie. Killa
  le claim non verificabili. NOTA: il workflow deep-research ha un bug nel verify-stage
  (vota 0-0 abstain) — giudica le claim sul merito-fonte, non sul verdetto automatico.
- SINTESI (Claude opus): cosa applicare al NOSTRO sistema (federation_orchestrator,
  agent_start, Workflow patterns). Spec di adozione, non rassegna accademica.
- MECCANICO (1, serial): research/operations/2026-06-02-sota-multiagent-FROZEN.json +
  report con top-N tecniche adottabili. commit → push → PR draft → STOP.

OUTPUT: FROZEN + report azionabile. --release.
```

---

## 🌊 ONDA 2

### ▶ S2 — Spec graveyard: le 11 DRAFT pendenti  `[M5 / sonnet, fan-out Codex]`

```
ORCHESTRATORE sessione S2 "spec-graveyard-triage". Autonomia piena in loop, no conferme.

PASSO 0:
  python scripts/agent_start.py --lane docs --task-id s2-spec-graveyard
  cd .worktrees/docs-s2-spec-graveyard
  export BRANCH_EXPECTED=$(git branch --show-current)

LE 3 LEGGI.

MISSIONE: ~30 spec in research/operations/specs/, ~11 in status DRAFT/NOT-EXECUTED/pending
(W38 rolsuper, W39 dependabot-cve, T3.5 session-start-consolidation, T3.6 tool-search-auto,
L5.1/L5.2 worktree-enforcement, T2.x). Per OGNUNA: ancora valida? superata da lavoro
shippato? eseguibile in autonomia o NEEDS-ANTONELLO?

TOPOLOGIA (Workflow fan-out 1 per spec):
- ASSALITORI (5 paralleli): per ogni spec, grep stato shippato vs spec, verifica se il
  problema esiste ANCORA sul disco/prod. Classifica: EXECUTE-NOW (autonomo, basso rischio)
  / NEEDS-ANTONELLO / DEAD (già risolto, archivia) / RE-SPEC (obsoleta).
- ANALISTI: Codex adversarial sul rischio degli EXECUTE-NOW (è davvero basso rischio?).
  W38 rolsuper: NON eseguire (DO-NOT-EXECUTE confermato), ma verifica via postgres MCP che
  backend_rag_v2 rolsuper=t sia ANCORA vero + aggiorna lo spec con la data.
- ESECUZIONE (solo EXECUTE-NOW basso-rischio, ognuno nel SUO sub-worktree se tocca codice):
  TDD, test, PR draft separata.
- MECCANICO (1, serial): research/operations/S2-spec-graveyard-FROZEN.json (matrice 11
  spec × verdict) + N PR draft. commit → push → PR draft → STOP.

VINCOLI: W38 mai eseguire. EXECUTE-NOW solo se l'analista conferma basso rischio +
reversibile. OUTPUT: matrice + PR. --release.
```

### ▶ S3 — escalations_pro.jsonl 1.17MB + DLQ hygiene  `[Codex-heavy / opus]`

```
ORCHESTRATORE sessione S3 "escalation-debt-cleanup". Autonomia piena in loop, no conferme.

PASSO 0:
  python scripts/agent_start.py --lane infra --task-id s3-escalation-debt
  cd .worktrees/infra-s3-escalation-debt
  export BRANCH_EXPECTED=$(git branch --show-current)

LE 3 LEGGI.

MISSIONE: shared/escalations_pro.jsonl = 1.17MB / 4519 entry tutte "pending", git-tracked,
storm STORICA CONTENUTA (ultimo ts reale 2026-05-24, loop morto). Debito dal gap "weekly
digest/pruning" di W61. RISCHIO: pruning NON è additivo-sicuro (sentinel tooling può
parsare il file).

TOPOLOGIA (Workflow):
- ASSALITORI: (a) agente-forense — grep scripts/ + apps/ per OGNI consumer del file (chi
  legge escalations_pro.jsonl) → mappa chi si rompe se prune; (b) agente-DLQ — verifica
  stato DLQ (W61 add_to_dlq fix funziona? tutti TERMINAL?).
- ANALISTI: Codex devils-advocate sul rischio rotation. La rotation è safe SOLO se
  l'agente-forense prova 0 consumer rompibili O consumer tollera file vuoto.
- ESECUZIONE: implementa rotation (archive→.jsonl.gz + truncate + sentinel-aware) SOLO se
  provata safe. Testa su COPIA in /tmp, MAI sul file vero senza prova. + costruisci il
  "weekly digest suppressed-alerts" mancante (W55 gap).
- MECCANICO (1, serial): research/operations/S3-escalation-debt-FROZEN.json + rotation
  script (testato su copia) + PR. Se NON provato safe → spec + NEEDS-ANTONELLO.
  commit → push → PR draft → STOP.

VINCOLI: MAI truncare il file vero senza prova-forense di sicurezza. OUTPUT: FROZEN +
script + digest. --release.
```

### ▶ S7 — CRM yield: 11.699 clienti → revenue signals  `[Pro OBBLIGATORIO / opus, Ollama]`

```
ORCHESTRATORE sessione S7 "crm-yield-mining" — DEVE girare sul Pro (PII, Law 2 + UU PDP).
Autonomia piena in loop, no conferme.

PASSO 0:
  python scripts/agent_start.py --lane backend-rag --task-id s7-crm-yield
  cd .worktrees/backend-rag-s7-crm-yield
  export BRANCH_EXPECTED=$(git branch --show-current)

LE 3 LEGGI. + LEGGE PII: ZERO dato cliente verso cloud LLM. Reasoning/drafting su PII SOLO
con Ollama LOCALE (qwen3.5:9b Pro/Mini).

MISSIONE: 11.699 clienti, 440 pratiche. L'agent yield-optimizer esiste
(~/.claude/agents/yield-optimizer.md, gira Sunday 04:00). Estendi: segnali di revenue
(KITAS in scadenza, business pivot, no-contact-recente, alto engagement) → pipeline pitch.

TOPOLOGIA:
- ASSALITORI (query CRM via postgres-nuzantara MCP read-only o nuzantara-mcp
  list_clients/get_expiry_alerts/get_compliance_alerts, fan-out): (a) segmentazione — chi
  scade nei prossimi 60-90gg; (b) engagement-score; (c) business-pivot signal.
- ANALISTI (Ollama locale): valida i segmenti, niente falsi positivi.
- DRAFTING (Ollama locale, WhatsApp template via bali-zero-brand): pitch per segmento.
- MECCANICO (1, serial): research/crm/S7-yield-FROZEN.json (segmenti + COUNT aggregati,
  SENZA nomi/PII nel file) + draft pitch in staging locale. commit → push → PR draft → STOP.

VINCOLI: NON inviare nulla (Legge 5, draft only). PII mai nei file committati, mai cloud.
OUTPUT: segmenti aggregati + draft. --release.
```

### ▶ S10 — CRM data quality: i 11.699 clienti  `[Pro OBBLIGATORIO / opus, Ollama]`

```
ORCHESTRATORE sessione S10 "crm-data-quality" — DEVE girare sul Pro (PII). Autonomia piena
in loop, no conferme.

PASSO 0:
  python scripts/agent_start.py --lane backend-rag --task-id s10-crm-quality
  cd .worktrees/backend-rag-s10-crm-quality
  export BRANCH_EXPECTED=$(git branch --show-current)

LE 3 LEGGI. + LEGGE PII: aggregati SÌ, PII nei file NO. Conta "847 duplicati", non
"Mario==Mario". Reasoning su PII → Ollama locale.

MISSIONE: 11.699 clienti — quanti duplicati, incompleti, orfani (no pratica/contatto),
Drive-link rotti? CRM-Guardian esiste (crm_guardian_* MCP tools). Mappa-salute completa.

TOPOLOGIA (Workflow + CRM-Guardian MCP):
- ASSALITORI (4 paralleli): (a) duplicati (stesso nome/email/phone); (b) completezza
  (campi critici mancanti); (c) orfani (no pratica né timeline); (d) drive
  (crm_guardian_find_stale_drive_links + find_unlinked_drive_items +
  find_external_owner_risks).
- ANALISTI (Ollama locale): valida i cluster duplicati (omonimi ≠ duplicati).
- SPAZZINI: verifica zero PII nei file output.
- MECCANICO (1, serial): research/crm-guardian/S10-crm-quality-FROZEN.json (metriche
  AGGREGATE) + spec remediation prioritizzato. commit → push → PR draft → STOP.

VINCOLI: fix DB mai via MCP (read-only). Remediation = spec, NEEDS-ANTONELLO. Cache
invalidation discipline se proponi mutation (§9). OUTPUT: metriche + spec. --release.
```

### ▶ S13 — Agent library evolution (Voyager + Reflexion)  `[Mini acct2 / opus, agy]`

```
ORCHESTRATORE sessione S13 "agent-library-evolution". Autonomia piena in loop, no conferme.

PASSO 0:
  python scripts/agent_start.py --lane organism --task-id s13-agent-evolve
  cd .worktrees/organism-s13-agent-evolve
  export BRANCH_EXPECTED=$(git branch --show-current)

LE 3 LEGGI. + rispetta NB Contract 2 (solo brief-interpreter consuma NB direttamente).

MISSIONE: 37 agenti custom esistono. Voyager skill-library + Reflexion weekly (wr3-
reflexion-synth, agent-library-evolver) girano. Ciclo di evoluzione: quali agenti hanno
lesson accumulate non sintetizzate? quali skill mancano? quali si sovrappongono?

TOPOLOGIA:
- ASSALITORI INGESTION (agy Gemini 1M context): ingerisci TUTTO il corpus agenti +
  lessons.md + 64 carousel + episodi WR3 in un pass.
- ANALISTI (Claude opus): ≤10 lesson verbali per agente; mappa overlap/gap; proposte skill
  draft. Codex adversarial su proposte ridondanti.
- MECCANICO (1, serial): research/agent-library/S13-evolution-FROZEN.json + N skill draft
  in _proposed/ + overlap matrix. commit → push → PR draft → STOP.

VINCOLI: NON modificare agenti in produzione. Proposte in _proposed/, Antonello approva
append a lessons.md. OUTPUT: FROZEN + draft + matrix. --release.
```

### ▶ S14 — NB curation: 64 NB / 3618 source  `[Pro OBBLIGATORIO / opus]`

```
ORCHESTRATORE sessione S14 "nb-curation-sweep" — Pro (NB-INTEL = OSINT, Law 2). Autonomia
piena in loop, no conferme.

PASSO 0:
  python scripts/agent_start.py --lane intel --task-id s14-nb-curation
  cd .worktrees/intel-s14-nb-curation
  export BRANCH_EXPECTED=$(git branch --show-current)

LE 3 LEGGI. + LEGGE OSINT: NB-INTEL Pro-only, mai cloud, mai team.

MISSIONE: 64 NB attivi, ~3618 source. nb-curator esiste (Mode C dedup/summarize/stale-
cleanup). NB-INTEL family degradata post UUID-switch 2026-05-18. Health-sweep completo +
proposta curation.

TOPOLOGIA (nb-curator agent Mode C + agy ingestion):
- ASSALITORI: per ogni NB — source count, staleness (>90d), dedup cluster, broken source.
  NB-INTEL: verifica UUID vivi (nb-intel-live-uuids-verified-2026-05-29 in mem) — FIDATI di
  `nlm query` NON di nb-migration-mapping.json (direzione invertita, trap nota).
- ANALISTI (bipolar verifier): valida i cluster dedup contro NB ground-truth.
- MECCANICO (1, serial): research/nb-health/S14-curation-FROZEN.json (64 NB × salute) +
  proposte curation prioritizzate. commit → push → PR draft → STOP.

VINCOLI: NB curati (NB-0..14) — proposte dedup/summarize, Antonello approva delete. Mai
delete autonomo di source. OUTPUT: FROZEN + proposte. --release.
```

---

## 🌊 ONDA 3

### ▶ S8 — WR2 carousel batch: contenuti IG  `[Mini acct2 / opus, FlowKit]`

```
ORCHESTRATORE sessione S8 "wr2-content-batch". Autonomia piena in loop, no conferme, FINO
al Telegram review gate (NON auto-publish, Legge 5).

PASSO 0:
  python scripts/agent_start.py --lane wr2 --task-id s8-content-batch
  cd .worktrees/wr2-s8-content-batch
  export BRANCH_EXPECTED=$(git branch --show-current)

LE 3 LEGGI.

MISSIONE: 4-6 carousel IG Bali Zero su temi regolatori freschi. La pipeline WR2 esiste
COMPLETA (skill wr2-carousel-pipeline + 27 subagent wr2-*/wr3-*). NON ricostruire —
ORCHESTRA invocando la skill.

TOPOLOGIA (skill wr2-carousel-pipeline guida tutto):
- Per ogni topic: wr2-design-architect orchestra (brief-interpreter NB ground-truth →
  storyboarder → image-prompt-author → layout-composer → critic gate). Questo È già
  orchestrator-worker.
- Immagini via FlowKit (skill nuzantara-flowkit-flow-generation, AI Ultra, NON Gemini API
  pagata — ricorda il fix TIER1P5).
- Topic: pesca da S6 (ricerca regolatoria fresca, se completata) + regulatory-watcher
  delta recenti + bali-zero-brand voice.
- Critic gate OBBLIGATORIO (Article 6.2 bilingual, 6.3 bullet-promise, 5.10
  no-silent-reuse). Retry se FAIL.
- MECCANICO: draft + Telegram review gate. research/operations/S8-wr2-FROZEN.json (topic ×
  critic-verdict). commit → push → PR draft → STOP.

VINCOLI: MAI auto-publish IG (Legge 5). OUTPUT: 4-6 carousel in queue + FROZEN. --release.
```

### ▶ S9 — Client case dossier: i casi aperti  `[Codex-heavy / opus]`

```
ORCHESTRATORE sessione S9 "client-case-dossier". Autonomia piena in loop, no conferme.

PASSO 0:
  python scripts/agent_start.py --lane docs --task-id s9-client-cases
  cd .worktrees/docs-s9-client-cases
  export BRANCH_EXPECTED=$(git branch --show-current)

LE 3 LEGGI.

MISSIONE: casi cliente reali in research/visa/clients/ + caso Marc Buckner C5a/E33G barter
(research/visa/2026-05-31). Dossier completi + quote per i casi attivi.

⚠️ ATTENZIONE scar S3-redteam: client-case-quote-generator ha 6 difetti strutturali
(STRUCT-1 no PricingTool, STRUCT-2 deepseek-reasoner deprecato→flash silente). QUINDI:

TOPOLOGIA:
- ASSALITORI: visa-eligibility per caso (NB-2 ground-truth bipolar verifier) + cost
  (SOLO via PricingTool/calculate_pricing MCP, MAI user-input/DeepSeek) + timeline + risk
  + deliverable.
- ANALISTI: math su deepseek-v4-pro ESPLICITO (mai -reasoner alias → flash silente).
  devils-advocate gate pre-output OBBLIGATORIO.
- MECCANICO (1, serial): N dossier PDF (bali-zero-brand internal-print-a4) +
  research/visa/clients/S9-cases-FROZEN.json. commit → push → PR draft → STOP.

VINCOLI: quote NON send-ready senza PricingTool verde + devils-advocate PASS. Se
PricingTool RBAC-blocca (role unknown) → NEEDS-ANTONELLO. OUTPUT: dossier + FROZEN. --release.
```

### ▶ S11 — Portal cliente: audit UX + gap  `[M5 / sonnet, browser]`

```
ORCHESTRATORE sessione S11 "portal-audit". Autonomia piena in loop, no conferme.

PASSO 0:
  python scripts/agent_start.py --lane frontend --task-id s11-portal-audit
  cd .worktrees/frontend-s11-portal-audit
  export BRANCH_EXPECTED=$(git branch --show-current)

LE 3 LEGGI.

MISSIONE: il portal cliente esiste (get_portal_dashboard/timeline/visa_status,
list_portal_documents/messages, send_portal_message MCP). Audit completo: cosa vede il
cliente, cosa manca, dove si rompe.

TOPOLOGIA:
- ASSALITORI: (a) frontend-browser subagent (skill browser, nuzantara-browser MCP stealth)
  per QA live subdomini balizero.com (kita/my/prime) — UX-walk login→dashboard→timeline→
  docs→messaggi; (b) backend-verifier per le route portal.
- ANALISTI: gap-analysis (cosa un cliente immigration vorrebbe e non c'è) + broken-element
  scan. Codex adversarial.
- MECCANICO (1, serial): research/operations/S11-portal-FROZEN.json + backlog UX
  prioritizzato + screenshot evidenze. commit → push → PR draft → STOP.

VINCOLI: post-deploy QA discipline (§11) — curl 200/307 PRIMA di screenshot. NON modificare
prod, solo audit + spec. OUTPUT: FROZEN + backlog + screenshot. --release.
```

### ▶ S12 — CRM automation: i daemon morti  `[Codex-heavy / opus]`

```
ORCHESTRATORE sessione S12 "crm-automation-revive". Autonomia piena in loop, no conferme.

PASSO 0:
  python scripts/agent_start.py --lane backend-rag --task-id s12-crm-automation
  cd .worktrees/backend-rag-s12-crm-automation
  export BRANCH_EXPECTED=$(git branch --show-current)

LE 3 LEGGI.

MISSIONE: collega a S1 — client_changed gate-off da 215h (consumer CRM morto). Quali
automazioni CRM (assignment, birthday_notifier, birthplace_enrichment, automation.py) sono
vive vs morte? Cosa NON gira che dovrebbe?

TOPOLOGIA (Workflow fan-out 1 per servizio):
- ASSALITORI: 1 agente per servizio in apps/backend-rag/backend/services/crm/ — handler
  registrato? daemon attivo? ultimo run? events_outbox drenato? + cross-ref con i 167
  LaunchAgent.
- ANALISTI: Codex adversarial sui falsi-positivi (servizio "morto" può essere on-demand,
  non daemon).
- MECCANICO (1, serial): research/crm/S12-automation-FROZEN.json (servizio × stato ×
  revive-plan). commit → push → PR draft → STOP.

VINCOLI: read-only diagnosi. Revive = spec + NEEDS-ANTONELLO (toccare consumer prod).
OUTPUT: FROZEN. --release.
```

### ▶ S17 — Crea agenti SOTA nuovi (libertà creativa)  `[M5 / sonnet, 4-LLM panel]`

```
ORCHESTRATORE sessione S17 "new-sota-agents". Libertà creativa (richiesta Antonello).
Autonomia piena in loop, no conferme.

PASSO 0:
  python scripts/agent_start.py --lane organism --task-id s17-new-agents
  cd .worktrees/organism-s17-new-agents
  export BRANCH_EXPECTED=$(git branch --show-current)

LE 3 LEGGI.

MISSIONE: progetta e crea 3-5 NUOVI agenti SOTA che mancano nell'arsenale. Identifica i
buchi: cosa Bali Zero fa a mano che un agente potrebbe fare? (es: lead-qualifier da
WhatsApp inbound, document-ocr-classifier per akta, compliance-deadline-sentinel,
competitor-pricing-tracker, onboarding-orchestrator).

TOPOLOGIA (skill writing-skills + sota-architecture-loop 8-step per ognuno):
- ASSALITORI: identifica i gap (cosa è manuale e automatizzabile). Usa NB-AGENTS (86
  source agent-craft, 6d449787-...) come ground-truth di design.
- ANALISTI (4-LLM panel review su OGNI spec agente — Gemini agy + Codex GPT-5.5 + DeepSeek
  V4 Pro + NB-AGENTS): verdict per agente. Pattern bipolar verifier.
- COSTRUZIONE: ogni nuovo agente = file in ~/.claude/agents/ + skill se serve + test.
- MECCANICO (1, serial): 3-5 agent definition + research/agent-craft/S17-new-agents-
  FROZEN.json + 4-LLM panel verdict per ognuno. commit → push → PR draft → STOP.

VINCOLI: rispetta i ban (no ANTHROPIC_API_KEY, CLI-only). NON registrare in cron senza
Antonello. Proposte, non auto-deploy. OUTPUT: agent defs + FROZEN + panel. --release.
```

### ▶ S18 — RAG eval: Zantara accuracy ground-truth  `[Codex-heavy / opus]`

```
ORCHESTRATORE sessione S18 "rag-eval-truth". Autonomia piena in loop, no conferme.

PASSO 0:
  python scripts/agent_start.py --lane backend-rag --task-id s18-rag-eval
  cd .worktrees/backend-rag-s18-rag-eval
  export BRANCH_EXPECTED=$(git branch --show-current)

LE 3 LEGGI.

MISSIONE: collega a scar S2 (RAG accuracy NON misurabile via MCP — RBAC wall, role
'unknown' blocca ask_legal/chat_kbli; villa KBLI 55193 vs 55203 dubbio). Costruisci un
harness di eval RAG vero per Zantara prod.

TOPOLOGIA (skill evaluate-rag + error-analysis + write-judge-prompt + validate-evaluator):
- ASSALITORI: genera golden set (QA pairs visa/tax/KBLI da NB ground-truth). Per il dubbio
  KBLI villa: risolvilo definitivamente (oracle 55193 vs codebase 55203 — quale è giusto
  per PP28/KBLI 2025? verifica via NB-3 + inspect_kbli).
- ANALISTI: misura retrieval (recall@k) + generation (faithfulness). Judge prompt validato.
- COSTRUZIONE: harness in apps/evaluator/, pronto-a-girare.
- MECCANICO (1, serial): harness + golden set + research/operations/S18-rag-eval-FROZEN.json
  + verdict villa-KBLI. commit → push → PR draft → STOP.

VINCOLI: se RBAC blocca accesso prod (role unknown) → documenta come NEEDS-ANTONELLO (serve
role grant) MA costruisci comunque l'harness. Embedding FROZEN (text-embedding-3-small/1536)
— mai cambiare (§9). OUTPUT: harness + golden set + FROZEN + verdict. --release.
```

---

## 🏁 LA CONVERGENZA (il Generale)

Ogni sessione lascia `research/operations/S{N}-*-FROZEN.json` (o nel suo dominio). Quando
le 3 onde sono finite, in una sessione-comando dici: **"converge"**. Il Generale:

1. Legge TUTTI i 18 FROZEN (tool reali, no memoria).
2. Costruisce la matrice unificata: EXECUTE-NOW-già-fatto / NEEDS-ANTONELLO / DEAD / RE-SPEC.
3. Dà UN solo report di comando: le decisioni che spettano ad Antonello (merge dei PR draft,
   rotazioni secret, demotion rolsuper, consumer-revive) + il piano del residuo.

Le 18 PR draft restano in attesa del tuo merge. Tu mergi al risveglio, dopo aver letto il
report di convergenza.

---

## ✅ CHECKLIST PRE-LANCIO (Antonello)

- [ ] Redis su (lease-check): `redis-cli ping` → PONG
- [ ] Slot 2 Claude OAuth'd: `bash -lc 'unset ANTHROPIC_API_KEY; CLAUDE_CONFIG_DIR=$HOME/.claude-acct2 claude auth status'`
- [ ] Codex vivo: `codex exec --sandbox read-only "ping"` → 0
- [ ] agy vivo: `agy -p "ping"` → risposta
- [ ] Ollama (per S5/S7/S10): `ollama list | grep qwen3.5`
- [ ] Disco: `df -h /` → <85% (scar 2026-05-14 disk-full)
- [ ] Max 5-6 sessioni simultanee (pacing)
