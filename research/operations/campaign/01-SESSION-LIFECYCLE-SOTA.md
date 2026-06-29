# Il ciclo di vita di una sessione SOTA (giugno 2026) — mappa precisa + auto-critica

> **Scopo:** descrivere ESATTAMENTE cosa fa ogni runner della Connectome Campaign, dal worktree-create al
> cleanup, ogni step nel mezzo. Con dialogo di auto-critica inline (🔴 = io attacco il mio design, 🟢 = io rispondo).
> **Ancoraggio:** disco (interfacce reali verificate) + best-practice web 2026 + reuse-first (cosa esiste già).
>
> **Reuse-first verdict:** 6 dei 7 mattoni del lifecycle ESISTONO GIÀ su disco (broker, lease, gate-hook,
> dispatch, loop-skill, task-tracking). Solo l'**effect-receipt** (heartbeat-di-effetto, antidoto #11) è nuovo —
> ed è un singolo JSON per ciclo. Il workflow è ORCHESTRAZIONE di pezzi esistenti, non costruzione.
>
> **Fondamento web 2026** (convergente col disco): worktree-isolation load-bearing da Q1 2026; i 6 pattern
> anti-conflitto (spec-decomp · worktree-isolation · coordinator/specialist/verifier · per-task model routing ·
> quality-gates · sequential-merges); self-verification abbassa i fallimenti dall'80% al 23%; "git worktree NON
> avvisa se due worktree toccano lo stesso file" → serve il lease. context-rot su sessioni lunghe → task bounded.
> Fonti in §Riferimenti.

---

## Vista d'insieme: le 9 fasi di una sessione

```
FASE 0  GROUND      stadio-zero: memoria + hot-files verificati su disco + criteri falsificabili
FASE 1  SCOPE       il lane-lead riceve il mandato, decompone per-anatomia (task indipendenti)
FASE 2  CREATE      agent_start.py → worktree isolato + branch dedicato + TTL
FASE 3  LEASE       agent_lease acquire su ogni hot-zone che toccherà (FAIL-CLOSED per chiusure)
FASE 4  FAN-OUT     spawn worker (1/organo) + dispatch multi-AI (Gemini width / Codex code / Ollama PII)
FASE 5  ACT         il worker fa il lavoro nel worktree (read → edit → test)
FASE 6  GATE        i 5 cancelli prima di QUALSIASI chiusura (grounding→refuter→effetto→confine→audit)
FASE 7  RECEIPT     effect-receipt JSON (heartbeat-di-EFFETTO, non di esistenza) → path noto
FASE 8  HARVEST     commit + PR (mai merge) · findings/ · aggiorna campaign-state · mem save
FASE 9  CLEANUP     lease release · worktree --release (se merged) o TTL-reap · receipt finale
```

---

## FASE 0 — GROUND (entry gate)
**Cosa:** la sessione carica `stadio-zero` (o `opus-mythos` se deep/wide). Verifica: memory-hits pertinenti,
hot-files VERIFICATI su disco (non citati a memoria), PII-scope, criteri di accettazione falsificabili.
**Reuse:** skill `stadio-zero` esiste. Hook `stadio_zero_nudge.py` lo ricorda.
**Perché:** previene la "file:line hallucination" — costruire un piano su un path che non esiste (superscar #6).

> 🔴 *"FASE 0 è teatro se il runner la salta — è una skill, non un hook bloccante."*
> 🟢 Vero, `stadio_zero_nudge.py` è nudge non block. MA il GATE di FASE 6 (cancello-0 grounding) RI-richiede
>    prova-in-questo-turn prima di committare: se hai saltato FASE 0, FASE 6 ti ferma comunque. Doppia rete.
> 🔴 *"E se il mandato è già nel file-prompt? FASE 0 non ridonda?"*
> 🟢 No: il file-prompt dà lo SCOPO, FASE 0 verifica il TERRENO oggi (i file potrebbero essere cambiati da
>    quando ho scritto il prompt, 1h fa). Lo scopo è statico, il terreno è vivo.

## FASE 1 — SCOPE (decomposizione)
**Cosa:** il lane-lead (L2) legge `00-CAMPAIGN-STATE.md` + il suo mandato, decompone la lane in task ATOMICI
e INDIPENDENTI (best-practice: parallelismo solo su task indipendenti, altrimenti degenera in seriale costoso).
**Reuse:** `TaskCreate`/`TaskList` (harness) per tracciare. La decomposizione per-anatomia è in opus-mythos.
**Output:** una lista di task, ognuno → un worker in FASE 4.

> 🔴 *"Decomporre per-anatomia garantisce davvero indipendenza? Un fix di security in un file backend che
>     l'audit-lane sta leggendo NON è indipendente."*
> 🟢 Corretto — ed è il limite noto del web 2026 ("git worktree non avvisa su file condivisi"). La rete è il
>    LEASE (FASE 3): se due lane puntano lo stesso file, la seconda fallisce `agent_lease check`. L'indipendenza
>    by-anatomy è il 90%; il lease copre il 10% di overlap residuo. Non mi fido della sola decomposizione.

## FASE 2 — CREATE (worktree)
**Cosa:** `python scripts/agent_start.py --lane <X> --task-id <Y> --ttl-min <N>` → crea
`.worktrees/<lane>-<task>/` con branch dedicato forkato da main, TTL per il reap.
**Reuse:** `agent_start.py` ESISTE (verificato: `--lane --task-id --ttl-min --base-branch --list --cleanup --release --force`).
**Perché:** isolamento — "worktree load-bearing da Q1 2026"; il main checkout resta read-only (hook lo impone).

> 🔴 *"Su Pro/Mini il main è 0-behind; su M5 è 37-behind. I worktree forkano da `main` LOCALE → un worker M5
>     lavora su codice vecchio di 37 commit."*
> 🟢 Catch reale. Mitigazione: `--base-branch origin/main` invece di `main` locale, OPPURE il lane-lead M5 fa
>    `git fetch` (read-only, permesso) e forka da origin/main aggiornato. Lo metto come step esplicito di FASE 2
>    per M5. Su Pro/Mini non serve (già allineati).
> 🔴 *"TTL default 60min. Un audit profondo dura di più → il reap potrebbe uccidere un worktree vivo (W80!)."*
> 🟢 Per questo `agent_start --cleanup` ha la `--skip-recent-min` guard (default 10min di FS-activity) + il
>    reap-guard a 2-AND (no-live-process AND merged-in-origin). W80 è già fixato. Ma per sicurezza i runner
>    della campagna usano `--ttl-min 240` (4h) per i task lunghi. Heartbeat di FS-activity tiene vivo il resto.

## FASE 3 — LEASE (coordinamento cross-machine)
**Cosa:** prima di toccare una hot-zone (LaunchAgent, migration, auth/billing, .github/workflows, ~/.claude),
`python scripts/agent_lease.py acquire <resource> --task-id <Y>`. Heartbeat periodico. FAIL-CLOSED per chiusure.
**Reuse:** `agent_lease.py` ESISTE (`acquire/release/heartbeat/list/check`), backbone Redis su Mini (PONG verificato).
**Perché:** è la rete per l'overlap che la decomposizione non copre (limite noto web 2026).

> 🔴 *"Redis è su Mini. Se Mini cade, il lease graceful-degrada a pass-through (WARN) → race silenziose
>     proprio durante alta concorrenza. E Mini è ANCHE un runner → si auto-DOS?"*
> 🟢 Due risposte. (1) Override di campagna (in costituzione §3.3): per le CHIUSURE, Redis-down = FAIL-CLOSED,
>    non pass-through. Leggere sì, committare no. (2) Mini come backbone+runner: la costituzione cappa Mini a 2
>    worker proprio perché regge Redis + Ollama + claude. Se va in pressione, scende a 1. Il Super-Osservatore
>    (io) monitora `redis-cli ping` a ogni giro.
> 🔴 *"Un lease su `~/.claude` cross-machine non ha senso — ogni macchina ha il SUO ~/.claude, non è condiviso."*
> 🟢 Giusto, correzione: il lease cross-machine vale solo per risorse REALMENTE condivise (git origin, Fly DB,
>    Redis stesso, organs_registry). `~/.claude` è per-host → lease LOCALE per-host, non cross. Lo annoto.

## FASE 4 — FAN-OUT (worker + dispatch AI)
**Cosa:** il lane-lead spawna worker (subagent Sonnet, 1 per organo/task) ognuno nel suo worktree. Dispatch
multi-AI per ruolo: Gemini (width/corpus), Codex (code/migration-test), DeepSeek (refuter non-PII), Ollama
(PII-local), NLM (ground-truth dominio).
**Reuse:** `ai-dispatch.sh` ESISTE (explore/search/sandbox/redteam/oracolo). Agent tool per i subagent.
**Perché:** coordinator/specialist/verifier split (best-practice 2026). +90% vs single-agent (Anthropic).

> 🔴 *"Reliability compounding: 95% × N worker = degrado. Quanti worker prima che la catena collassi?"*
> 🟢 Web+costituzione concordano: oltre ~4-5 worker in catena la qualità crolla SE non c'è verifica per-ramo.
>    Per questo ogni finding ha un refuter (FASE 6 cancello-1). Cap: M5≤1, Pro≤4, Mini≤2 worker. Il refuter
>    RECUPERA affidabilità — ma solo se il Super-Osservatore ha banda di ri-verificare ognuno (vedi FASE 7).
> 🔴 *"Il refuter è un altro agente → alluc­ina anche lui (#6). Chi verifica il verificatore?"*
> 🟢 Esatto, è il GOTCHA appena scoperto nella TAC. Risposta a 2 livelli: (a) il refuter è su AI DIVERSA dal
>    producer (DeepSeek refuta Claude, non Claude-refuta-Claude) → errori non correlati. (b) il gate FINALE è
>    sempre Opus che rifà il grep su disco (W65: "l'ultimo grep del padre non si delega"). Il Super-Osservatore
>    è il verificatore-del-verificatore, e LUI ri-esegue i comandi-prova, non si fida dei receipt.

## FASE 5 — ACT (il lavoro vero)
**Cosa:** il worker, nel suo worktree, fa il ciclo: read (grep/glob) → ipotesi → edit → test. Per i fix
applica `karpathy-discipline` (no silent assumptions, no hypertrophy, no collateral changes).
**Reuse:** skill `karpathy-discipline`, `sota-architecture-loop` per le decisioni strutturali.
**Confine:** SOLO L2-safe in autonomia (edit lane-owned, test). Le azioni di chiusura aspettano FASE 6.

> 🔴 *"'no collateral changes' vs un audit che TROVA bug in 5 file diversi — il worker deve fixarli tutti o no?"*
> 🟢 Un worker = un task atomico = un organo. Se trova bug fuori scope, NON li fixa: li registra in findings/ e
>    il lane-lead crea un nuovo task (nuovo worktree). Mai espandere lo scope a runtime (context-rot, web 2026).

## FASE 6 — GATE (i 5 cancelli, in sequenza, prima di OGNI chiusura)
**Cosa:** nessun commit/PR/azione passa senza i 5 cancelli IN ORDINE (se uno fallisce, STOP):
- **Cancello 0 — Grounding:** prova-in-questo-turn (file:line letti, comando+exit, test verde). No "ho visto prima".
- **Cancello 1 — Refuter indipendente:** un AI DIVERSO prova a DEMOLIRE il finding (asimmetrico, non consenso). Mai self-review.
- **Cancello 2 — Test di EFFETTO:** non "i test passano" ma "l'effetto è dimostrato" (il cron prima non produceva / ora sì; test rosso→verde attribuibile).
- **Cancello 3 — Confine L2/L3 (hard, hook):** `host_boundary.py` + `orchestrate_gate.py` bloccano se l'azione è L3-firebreak.
- **Cancello 4 — Audit-pre:** scrive l'intent nell'audit trail PRIMA di agire.
**Reuse:** hooks ESISTONO (host_boundary, orchestrate_gate, seam_verify, stop_verify). Skill `verify`.
**Perché:** self-verification 80%→23% fallimenti (web 2026). È il cuore della sicurezza.

> 🔴 *"5 cancelli per OGNI commit = lentissimo. Un fix di un typo passa 5 cancelli?"*
> 🟢 No, proporzionalità: un fix reversibile triviale in lane-owned passa solo cancello-0 (grounding) +
>    cancello-3 (il confine, che è automatico via hook). I 5 pieni sono per azioni a impatto: armare-qualcosa,
>    toccare hot-zone, chiudere un loop. Il GATE scala con il blast-radius dell'azione, non è fisso.
> 🔴 *"Cancello-3 è hook → ma gli hook sono in ~/.claude di OGNI macchina. Sono identici su Pro/Mini/M5?"*
> 🟢 DOMANDA APERTA load-bearing. Su M5 verificato (52 hook armati). Su Pro/Mini NON ri-verificato in questo
>    turno. → è un task per la lane-AUDIT/META: confermare che host_boundary+worktree_isolation siano armati
>    e IDENTICI (md5) sulle 3 macchine. Se un host ha hook diversi, il confine L2/L3 non è uniforme = pericolo.
>    Lo aggiungo al backlog §7 del campaign-state.

## FASE 7 — RECEIPT (heartbeat-di-EFFETTO) ← l'unico pezzo NUOVO
**Cosa:** ad ogni ciclo, il worker emette un JSON in `research/operations/campaign/receipts/<host>-<lane>-<task>.json`:
```json
{"host","lane","task_id","account","git_sha_before","git_sha_after","files_touched":[],
 "artifact_proof","cause_command","cause_exitcode","refuter_id","refuter_verdict","lease_held":[],"ts"}
```
**Reuse:** NON esiste → [SCRIVI-NUOVO], ma minimo (un dict + write). È l'antidoto #11 (heartbeat-di-consumo).
**Perché:** distingue lavoro reale da teatro. exit-0 NON è prova; `git_sha_before != git_sha_after` + artifact lo è.

> 🔴 *"Il receipt stesso può essere allucinato — un worker scrive sha falsi."*
> 🟢 Per questo il Super-Osservatore NON si fida del receipt: ri-legge `git_sha_after` dal git reale, ri-esegue
>    `cause_command` e controlla l'exit. Il receipt è un CLAIM, non una prova. La prova è la mia ri-verifica.
>    (Esattamente il pattern "Verifier Agent monitora i tool-call output", web 2026.)
> 🔴 *"Perché un file JSON e non un DB? Sembra fragile."*
> 🟢 Reuse-first + sovranità: file su path-noto = zero infra nuova, git-tracciabile, leggibile via ssh,
>    nessun servizio da armare (che sarebbe esso stesso #11: un servizio-receipt armato-a-vuoto). Il file È
>    lo shared-context-layer (causa #1 di fallimento risolta col mezzo più semplice). KISS.

## FASE 8 — HARVEST (raccolta del valore)
**Cosa:** se i 5 cancelli passano: `git commit` (atomico, convenzionale, co-author) → `gh pr create` (MAI
merge — il merge è L3) → scrive `findings/<host>-<lane>-<slug>.md` → aggiorna `00-CAMPAIGN-STATE.md` §6/§7/§8
→ `mem save` delle discovery durevoli.
**Reuse:** git/gh, skill `scar` per cicatrici nuove, CLI `mem`. Merge-train: `gh pr merge --auto` lo arma
SOLO il Super-Osservatore/Zero, mai il runner.
**Perché:** sequential-merges (best-practice 2026: mai merge paralleli che collidono).

> 🔴 *"PR mai-merge → si accumulano PR aperte all'infinito. Chi le merga?"*
> 🟢 Il merge è firebreak L3 = Zero (o io con conferma esplicita). È DELIBERATO: l'autonomia alta si ferma
>    PRIMA del merge su main. Le PR sono il deliverable; Zero fa il merge-train a fine campagna o a comando.
>    Questo è il confine "chiude tutto tranne firebreak fisico" che Zero ha confermato.

## FASE 9 — CLEANUP (chiusura del ciclo)
**Cosa:** `agent_lease release --task-id <Y>` (rilascia tutti i lease) → `agent_start.py --release <Y>` (se il
branch è merged) OPPURE lascia che il TTL-reap lo recuperi (se WIP-safe) → scrive il receipt finale di lane.
**Reuse:** `agent_start --release` (richiede branch merged) + `--cleanup` (TTL+WIP-safe) + `worktree_gc_universal.py`.
**Perché:** "session lifecycle = create, navigate, delete, stage" (web 2026). Niente worktree zombie (superscar #5/W62).

> 🔴 *"--release richiede branch MERGED, ma il merge è L3 (Zero). Quindi il runner non può MAI fare cleanup?"*
> 🟢 Catch importante. Risoluzione: il runner a fine task fa SOLO `lease release` + lascia il worktree con la PR
>    aperta (NON lo distrugge — contiene lavoro non ancora merged). Il cleanup del worktree avviene DOPO che
>    Zero merga la PR: a quel punto `--release` funziona (branch merged) o il TTL-reap lo prende (W80-guard:
>    no-live-process AND merged-in-origin). Il runner NON distrugge worktree con lavoro non-merged. Coerente
>    con "leave-dirty intenzionale verso il lavoro sibling".
> 🔴 *"E i worktree orfani se un runner crasha a metà?"*
> 🟢 Il TTL (240min) + il cron `agent_worktree_cleanup_cron.sh` li reclamano, MA con la 2-AND guard (mai
>    distruggere worktree con processo vivo O commit non-merged). NB: quel cron è uno dei 2 morti-da-TCC su M5
>    (TAC §4.1) → su M5 il reap va fatto a mano dal Super-Osservatore finché Zero non concede il Full-Disk-Access.

---

## Sintesi del dialogo: cosa il self-critique ha aggiunto al design
1. FASE 2 su M5: forka da `origin/main` (fetch read-only), non da main-locale-37-behind.
2. FASE 2: TTL 240min per task lunghi, non 60 default.
3. FASE 3: lease cross-machine SOLO per risorse condivise (git/Fly/Redis/registry); `~/.claude` = lease locale.
4. FASE 3: Redis-down = FAIL-CLOSED per chiusure (override del graceful-degrade).
5. FASE 6 cancello-3: VERIFICARE che gli hook siano armati e IDENTICI (md5) sulle 3 macchine → task aggiunto al backlog.
6. FASE 6: il GATE scala col blast-radius (typo = 2 cancelli; armare-qualcosa = 5).
7. FASE 9: il runner NON distrugge worktree con PR non-merged; cleanup post-merge-di-Zero; su M5 reap a mano (TCC).

## Riferimenti (best-practice 2026)
- Anthropic, multi-agent research system (orchestrator-worker, +90%, token 15×).
- MindStudio / Augment / Google Cloud (Weinmeister): git worktrees per agenti paralleli, 6 pattern anti-conflitto, "git worktree non avvisa su file condivisi" → serve lease.
- InfoWorld via dev.to: self-verification 80%→23% fallimenti; Verifier Agent indipendente sul Chain-of-Thought.
- Penligent: "worktree need runtime isolation" (porte/DB/cache/secret/test-state oltre ai file).
- decodethefuture / Lyzr: context-inconsistency = causa #1 di fallimento; reliability compounding.
