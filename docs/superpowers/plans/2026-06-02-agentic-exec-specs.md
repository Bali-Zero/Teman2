# Spec Eseguibili — G4 + R1 + WR3-fix + Fusione WR2/WR3

> Da copia-incollare in sessioni-armata NUOVE. Topic VERI, verificati sul codice nel
> censimento (research/agent-craft/2026-06-02-DOSSIER-agentic-strategy.md, commit f153e1c46).
> Decisioni Antonello 2026-06-02: WR3 ripara+fondi, R1 sì, G4 subito.
>
> REGOLE COMUNI (in ogni sessione): worktree isolato via agent_start.py PRIMA di toccare
> codice · BRANCH_EXPECTED settato · le 3 leggi anti-autodistruzione (no peer-to-peer, brief
> completo, git single-threaded) · stop point: commit→push branch→PR draft→STOP pre-merge ·
> anti-hallucination: ogni numero da tool in-turn · NEEDS-ANTONELLO per prod/secret.

---

## ORDINE DI ESECUZIONE (dipendenze)

```
SPEC-1 (G4 Observatory) → SUBITO, fondazionale, sblocca il resto
SPEC-2 (R1 loop + WR3 venv fix) → DOPO G4 (così misuri che il fix attecchisce)
SPEC-3 (WR2/WR3 fusione primitive) → DOPO R1 (WR3 deve girare prima di fonderlo)
```

Lanciale in quest'ordine. G4 prima perché è l'occhio: ripari alla cieca senza.

---

## ▶ SPEC-1 — G4 Agent Observatory  `[Pro / opus, fondazionale]`

```
ORCHESTRATORE sessione "g4-observatory". Autonomia piena in loop, no conferme, fino allo
stop point.

PASSO 0:
  python scripts/agent_start.py --lane organism --task-id g4-observatory
  cd .worktrees/organism-g4-observatory
  export BRANCH_EXPECTED=$(git branch --show-current)

LE 3 LEGGI ANTI-AUTODISTRUZIONE (worker no peer-to-peer, brief completo, git single-thread).

MISSIONE: costruire la spina dorsale di osservabilità per TUTTE le ~241 entità agentiche
(34 claude-agent + 169 launchagent + 8 chain + servizi). FONDAZIONALE: senza trace+health
ogni intervento futuro è alla cieca. Riferimento: dossier §9 G4, Codex FASE2 area-12.

PROBLEMA REALE che deve catturare (dal censimento, verificato sul codice):
- organism.supervisor consuma 92k eventi Redis ma attua ZERO (shadow) → "alive-but-idle"
  è lo stato più insidioso: un daemon che gira ma non produce è DEGRADATO, non healthy.
- agent-library-evolver generation=0 (mai evoluto), wr3.reflexion morto codesigning.
- 8 chain MCP code-complete ma 0 auto-invocate.

COSTRUISCI (TDD, test prima):
1. **Trace schema** (locale-first, JSONL/SQLite per Law 2 — no PII in cloud):
   trace_id, agent_id, runtime (launchd|cli|backend|frontend|mcp-chain), task_type,
   pii_class, tool_calls, approval_checkpoints, output_digest, cost, latency, success,
   failure_reason, artifact_paths, human_feedback.
2. **Health probes** per ogni entità:
   - launchagent: launchctl active/loaded + log-mtime + import smoke
   - python venv/interprete esiste (CRITICO: vedi WR3 codesigning)
   - env richiesto presente SENZA esporre valori-secret
   - **"alive-but-idle" detection**: daemon che consuma eventi ma produce 0 azioni/draft/
     alert = DEGRADATO (questo cattura organism.supervisor 92k/0).
3. **Daily report**: agenti rotti, duplicati, costo-per-outcome-accettato, eval-failures,
   stale/idle quarantinabili.
4. **CI gate** (opzionale): scripts/agent_eval_gate.py --changed.

VINCOLI: locale-first (JSONL/SQLite), OpenTelemetry-GenAI-compatible fields per export
futuro ma NON esportare PII. Embedding FROZEN se tocchi RAG. Non modificare le 241 entità —
solo OSSERVARLE. OUTPUT: apps/<observatory>/ + test + research/operations/G4-observatory-
report.md. commit→push→PR draft→STOP. Poi --release.

GROUND-TRUTH del censimento: git show f153e1c46:research/agent-craft/census-raw/
phase1-synthesis.md (i macro-gruppi + 15 rotti + duplicati da monitorare).
```

---

## ▶ SPEC-2 — R1 Self-Improvement Loop + WR3 venv fix  `[Pro / opus, ROI 250%]`

```
ORCHESTRATORE sessione "r1-selfimprovement-loop". Autonomia piena in loop, no conferme.

PASSO 0:
  python scripts/agent_start.py --lane organism --task-id r1-loop
  cd .worktrees/organism-r1-loop
  export BRANCH_EXPECTED=$(git branch --show-current)

LE 3 LEGGI. PREREQUISITO: idealmente dopo G4 (così misuri che ogni fix attecchisce).

MISSIONE: l'architettura di auto-miglioramento è sofisticata (Voyager evolver + Reflexion
anti-self-justification + outcome-bucketing) MA il LOOP NON SI CHIUDE — è aperto a OGNI
giunto. ROI 250% ($60k riparazione → $70k/anno, DeepSeek FASE2). Riferimento: dossier §7 R1.

I 4 GIUNTI ROTTI (verificati sul codice in-turn, NON da memoria — RI-VERIFICA ognuno):

GIUNTO 1 — federation_orchestrator NO checkpointer:
  scripts/federation_orchestrator.py:509 = `return graph.compile()` senza checkpointer.
  → aggiungi PostgresSaver (durabile) o MemorySaver. Verifica il pattern già usato in
    kg_langgraph_orchestrator + workflow/checkpointer (esistono nel repo). Il
    human_checkpoint_node usa input() bloccante → valuta interrupt LangGraph durabile.

GIUNTO 2 — WR3 reflexion morto CODESIGNING (questo è il WR3-fix di Antonello):
  com.balizero.wr3.reflexion.weekly → OS_REASON_CODESIGNING su apps/war-room/.venv/bin/
  python3 (è un SYMLINK a ~/.pyenv/versions/3.11.11/bin/python3, xattr com.apple.provenance).
  → DIAGNOSI ESATTA prima del fix: `codesign -v $(readlink -f apps/war-room/.venv/bin/
    python3)` per vedere cosa fallisce. Fix robusto = RICOSTRUIRE la venv war-room sul Pro
    (python3 -m venv, reinstalla requirements) invece di patchare il symlink. Poi
    `launchctl kickstart -k gui/$(id -u)/com.balizero.wr3.reflexion.weekly` + verifica che
    ~/Library/Logs/wr3-reflexion-weekly.log venga finalmente prodotto.

GIUNTO 3 — agent-library-evolver DEEPSEEK_KEY mancante (generation=0):
  com.balizero.agent-library-evolver.weekly → 2026-05-31 FATAL: DEEPSEEK_API_KEY not set.
  Il plist ha EnvironmentVariables ma NON la key (commento dice "NOT here" per il bypass,
  ma EvoSkill ne ha bisogno). → la key è in ~/.openclaw/workspace/.env.master. Il WRAPPER
  (agent-library-evolver-run.sh) deve sourcearla, NON il plist (Law: secret non nei plist
  world-readable — vedi scar 2026-04-29). Verifica il wrapper, aggiungi source della key lì.
  Poi kickstart + verifica generation passa da 0 a >0.

GIUNTO 4 — wr2.reflexion AFFAMATO (carousel_runs=0):
  wr2.reflexion gira (exit 0) ma il suo input (carousel_runs) è VUOTO → la pipeline WR2
  upstream non lo alimenta. → trova dove WR2 dovrebbe scrivere i run consumati da reflexion
  e collega. (Potenziamento P1 del dossier.)

VINCOLI: ogni fix ha test/verifica empirica (kickstart + log prodotto + generation>0). Il
checkpointer DB tocca schema → se serve migration, Codex sandbox la testa. NON ruotare
secret esterni (NEEDS-ANTONELLO). Secret MAI nei plist (sempre nel wrapper via source).
OUTPUT: 4 giunti riparati + research/operations/R1-loop-report.md (before/after: generation
0→N, reflexion log prodotto sì/no, checkpointer attivo). commit→push→PR draft→STOP. --release.
```

---

## ▶ SPEC-3 — Fusione WR2/WR3: primitive condivise  `[Pro / opus]`

```
ORCHESTRATORE sessione "wr2-wr3-fusione". Autonomia piena in loop, no conferme.

PASSO 0:
  python scripts/agent_start.py --lane wr2 --task-id wr2-wr3-fusione
  cd .worktrees/wr2-wr2-wr3-fusione
  export BRANCH_EXPECTED=$(git branch --show-current)

LE 3 LEGGI. PREREQUISITO: DOPO R1 (WR3 deve girare prima di fonderlo — non fondere un
sistema rotto).

MISSIONE: WR2 (8 agenti carousel) e WR3 (13 agenti video) condividono il PATTERN ma
duplicano 2-3 agenti quasi-gemelli. Decisione Antonello: ripara WR3 (fatto in R1) E POI
fondi. NON merge totale (WR3 ha 8 agenti video-specifici: clip-renderer, audio-asset-
producer, shot-director, pre-render-gatekeeper, post-assembler, b-roll-curator — non hanno
gemello WR2). Fusione = ESTRARRE PRIMITIVE CONDIVISE. Riferimento: dossier §6 M2/duplicati
D1-D2, Codex FASE2 area-7.

I DUPLICATI VERI (dal censimento, RI-VERIFICA leggendo i .md):
- D1: wr2-brief-interpreter ≈ wr3-brief-interpreter (stesso ruolo NB-grounding, stesso
  nlm-CLI, stesso claim/citation-verbatim contract; differisce solo NB routing NB-1/4/5 vs
  NB-2..7) → estrai `BriefGrounder` parametrico (param: nb_routing, downstream_consumer).
- D2: wr2-external-bench ≈ wr3-editorial-bench (stesso design "monthly SOTA bench, 12 brand
  + 3 competitor, agy+Claude+DeepSeek cascade") → estrai `ExternalBench` (param: domain
  carousel|video). NOTA: wr3-editorial-bench è anche ROTTO → R1 deve averlo sistemato.
- (valuta) wr2-critic ≈ wr3-critic (entrambi quality-gate 4-rubric) → primitiva `CriticGate`?

COME FONDERE (senza rompere produzione WR2 che è VIVA — 33 output, supervisor pid 17298):
1. Estrai la primitiva condivisa come modulo/skill base parametrico.
2. wr2-X e wr3-X diventano THIN WRAPPER che chiamano la primitiva con i loro parametri.
3. Test: WR2 carousel deve ancora produrre identico (regression — è in produzione!).
4. WR3 episode deve girare con la primitiva fusa.
5. Aggiorna i riferimenti "MUST BE USED by wr2/wr3-design-architect".

VINCOLI: WR2 è PRODUZIONE VIVA — zero regressione (test prima/dopo che il carousel esce
identico). Non toccare gli 8 agenti video-specifici WR3 (no gemello). Le primitive vanno
in ~/.claude/agents/ o skill condivisa. OUTPUT: BriefGrounder + ExternalBench (+CriticGate?)
estratti + wr2/wr3 agenti come wrapper + research/operations/wr2-wr3-fusione-report.md
(before: 2 agenti duplicati; after: 1 primitiva + 2 wrapper; test regression WR2 PASS).
commit→push→PR draft→STOP. --release.
```

---

## NOTE STRATEGICHE

- **G4 prima è non-negoziabile**: è l'occhio. Con G4 attivo, R1 e fusione li MISURI
  (generation 0→N, carousel-identico-sì/no, reflexion-log-prodotto) invece di sperare.
- **WR3 fix è dentro R1** (GIUNTO 2) perché il codesigning è anche un giunto del loop
  (reflexion morto = loop aperto). Due piccioni.
- **Fusione DOPO riparazione**: non si fonde un sistema rotto. R1 sistema WR3, poi fondi.
- **ROI cumulato** (DeepSeek): R1 +$70k/anno, consolidamento (fusione+macro) -$70k/anno
  costi. G4 è fondazionale (abilita di misurare tutto il resto).
- **Prossimo round** (dopo questi 3): i game-changer al fatturato G1 WA-Copilot + G2
  Akta-OCR ($200k/anno) + G3 Predictive-Sentinel ($250k/anno) — spec separate quando questi
  3 sono mergiati.
```
