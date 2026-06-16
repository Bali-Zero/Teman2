# cicatrix-scars.md

Living document of "scars" — past bugs/issues auto-extracted from development history.
Each entry has TRAUMA (what went wrong), ANTIBODY (how it's now protected), and GOTCHA (edge cases).

---

### 🐛 W83 (P2 STRUCTURAL): il worktree-isolation hook decide su substring testuale → 3 falsi BLOCK in una sessione (git pull remoto ssh, `cd <worktree> && git`, git-verb dentro una stringa quotata) (2026-06-16)

_Discovered: 2026-06-16 vissuta IN DIRETTA 3 volte nella sessione che rianimava curiosity_loop — il hook bloccò `ssh pro git pull`, `cd .worktrees/... && git checkout`, e un comando diagnostico multi-riga che conteneva git-verb non-quotati · Severity: **P2 STRUCTURAL** (over-match anti-allucinazione che NUOCE: clobbera ops legittime; il danno è frizione operatore + workaround rischiosi tipo `false && cd /pro && git pull`) · Status: **FIXED** — `_strip_noise` pre-scan + `_is_remote_dispatch` segment-anchored, 21/21 test, live+repo sync (PR #1517)_

**Famiglia: superscar #3 (Guard-over-match), gemello-locale di W82.** Stessa malattia: una guardia (qui `worktree_isolation.py`, non un `_guard_*` di WhatsApp ma identica classe) decide sulla **forma testuale** del comando, non sul suo **target reale**. W68/W72/W73/W77 = guard di RISPOSTA; W82 = under-match; W83 = over-match su un guard di COMANDO. Il layer è lo stesso, il bersaglio diverso.

**TRAUMA:** Il hook `infra/claude-hooks/worktree_isolation.py` (+ copia live `~/.claude/hooks/`) blocca i git mutanti nel main checkout per evitare sibling-race (superscar #5). Tre over-match, tutti provati live nella stessa sessione: (1) **`ssh pro git pull`** — l'op gira su UN ALTRO host, non tocca QUESTO checkout, ma il `git pull` nudo nel payload ssh scattava il block; l'operatore aggirava con `false && cd /pro/path && git pull` per far risolvere il target al path Pro. (2) **`cd <worktree> && git checkout -b x`** — legittimo (il `cd` ri-targetizza al worktree) ma Bash **resetta la cwd al main checkout** prima di eseguire, quindi il target effettivo cadeva su main → falso block. (3) **un git-verb dentro una stringa quotata / heredoc** (`echo "git reset is dangerous"`, o un comando diagnostico di test multi-riga) veniva scansionato come se fosse un comando reale.

**ANTIBODY:** (a) **`_strip_noise`** (rimozione heredoc + stringhe-quotate, la ricetta W79) ora gira **PRIMA** dello scan blocked-subcmd E della risoluzione del target — un git-verb che vive solo dentro un literal quotato non è più visto come comando. (b) **`_is_remote_dispatch`**: ssh/scp/rsync short-circuit ad ALLOW — ma **ancorato a un confine di SEGMENTO** (inizio riga o subito dopo `&&`/`||`/`;`/`|`), NON bare-substring: `ssh pro git reset` è esentato (off-box) mentre `echo via ssh && git reset --hard` NON lo è (op locale distruttiva che solo MENZIONA ssh → deve bloccare). (c) la risoluzione del target effettivo gestiva già `cd <wt> && git` e `git -C <wt>`; ora gira anche sul form strippato (chiude #2). Test `test_w83_remote_dispatch.py` 21 casi (incl. il caso pericoloso `echo ssh && git reset` no-exempt) → 21/21; W79 (20/20) e innocence-vaccine #1485 (29/29) restano verdi (nessun nuovo over-match). Live smoke 4/4.

**GOTCHA:** (a) **L'over-match `_is_remote_dispatch` v1 era esso stesso superscar #3**: il primo regex `(?:^|[\s|;&(])(?:ssh|scp|rsync)\b` matchava `ssh` come parola dentro `echo ssh ...` → un `echo ssh && git reset` in main sarebbe stato erroneamente esentato. Il TEST l'ha trovato (2/17 fail iniziale) — uno dei 2 fail era questo over-match reale nel codice, l'ALTRO era una mia ASPETTATIVA di test sbagliata (`git commit -m "..."` senza `-a` NON è un blocked subcmd → atteso False, non True). Lezione gemella W82/W73: il test d'innocenza deve includere il caso "menzione-innocua-vicino-a-op-distruttiva", e il refuter (il test) può sbagliare in ENTRAMBI i versi. (b) **Il hook ispeziona OGNI Bash, compresi i propri smoke-test**: un comando diagnostico multi-riga con git-verb non-quotati si auto-blocca → scrivi i test in un FILE ed eseguilo, mai inline. (c) **host_boundary asimmetria**: la scrittura sul control-plane `~/.claude/hooks/` è bloccata per i SUBAGENT ma passa dal main-loop (operatore) — propaga i fix-hook tu, non delegarli a un subagent. (d) **HOME-fork (superscar #1)**: il hook è vendored in `infra/claude-hooks/` con installer `install_worktree_hooks.sh`; patchare solo la copia live `~/.claude/` lascia il repo source-of-truth indietro → il prossimo install/reset perde il fix. Patcha ENTRAMBI (questa scar lo fa).

**Reference:** PR #1517, branch `fix/w83-vendor-worktree-isolation-hook`. Edited: `worktree_isolation.py` (`REMOTE_DISPATCH_RE` segment-anchored, `_is_remote_dispatch` nuovo, `_strip_noise` pre-scan in `main()`). Test: `infra/claude-hooks/test_w83_remote_dispatch.py` (21 casi, nuovo). Live `~/.claude/hooks/worktree_isolation.py` patchato+smoke 4/4 + backup `.bak.w83-hardened` chmod 600. Famiglia: superscar #3 (W68/W72/W73/W77 reply-guards, W82 under-match), eredita `_strip_noise` da W79, protegge superscar #5 (sibling-race).

---

### ⚠️ W82 (P1 STRUCTURAL): il sentinel di freschezza-conoscenza sorveglia la STRINGA, non il FATTO → under-match: lo stesso fatto stale in tabella / altra formulazione / altra lingua sfugge, e il guardiano resta VERDE (2026-06-16)

_Discovered: 2026-06-16 dalla lane L-KNOWLEDGE della Connectome Campaign (Mini, ciclo 1→2), confermata su disco dal Super-Osservatore leggendo `content-freshness-sentinel.test.ts` riga per riga · Severity: **P1 STRUCTURAL** (il guardiano anti-knowledge-decay ha un buco strutturale: verde mentre il sito è marcio) · Status: **REPORTED + scar promossa per decisione operatore (Antonello, 2026-06-16) — fix = guardiano fact-based, spec+PR mai armata senza OK**_

**Famiglia: superscar #3 (Guard-over-match) — variante UNDER-match.** #3 nasce con guardie che *sopra*-matchano (clobberano risposte corrette). W82 è il gemello speculare: una guardia che *sotto*-matcha (lascia passare fatti marci). Stessa malattia di fondo — **il match è sulla forma testuale, non sull'intento/entità** — segno opposto.

**TRAUMA:** `apps/mouth/src/content/content-freshness-sentinel.test.ts` (nato 2026-06-14, Mythos M3) è il "dead-man's switch" tra contenuto pubblicato e ground-truth regolatorio: legge `_regulatory-claim-ledger.json` (15 `stale_pattern` literal) e FALLISCE se un pattern stale ricompare in MDX pubblicato. **Ma il match è puro substring-letterale** (`staleHits`, riga 125: `lines[i].toLowerCase().includes(needle)`). Tre buchi strutturali, tutti verificati nel codice:

1. **Substring, non fatto** (riga 119-132): cerca la *frase esatta* `"hotels (55110)"`. Lo **stesso codice KBLI 55110** dentro una cella-tabella, o riformulato (`"perhotelan 55110"`, `"55110 (hotel)"`), o citato senza la parola "hotels", **NON matcha** → test verde. Prova viva: C312 (retirement) e 55110 (hotels) sono stale **anche nel canonico EN**, e il sentinel è **verde** su entrambi.
2. **Scope strutturalmente cieco alle traduzioni** (riga 21-22, 35-36, `TRANSLATION_SUFFIX`): *"English canonical .mdx only — translations audited separately"*. Il sentinel **non guarda mai** `.it/.id/.ru/.fr/.de/.es/.nl`. Questa è **letteralmente la causa-radice del bug KN-3** che il ciclo 2 ha dovuto fixare a mano (LKPM 10th→15th era stale in it/ru/fr mentre il sentinel era verde) — by-design non poteva vederlo. "Audited separately" = audited **mai**, finché un umano/agente non passa.
3. **Anche l'escape-clause è literal** (`MIGRATION_CONTEXT`, riga 58-97): la lista di frasi che "scusano" un pattern stale (`"superseded"`, `"old kbli 2020"`, `"moved to the 15th"`...) è essa stessa una lista di stringhe → fragile e da manutenere a mano; una correzione fraseggiata diversamente o non-EN non viene riconosciuta come legittima.

**ANTIBODY (PROGETTATO, NON armato — firebreak operatore):** guardiano **fact-based**, non string-based. La spec (vedi Reference) propone:
1. **Match per ENTITÀ normativa, non per frase**: ogni claim del ledger porta un `fact_key` strutturato (codice KBLI / sigla visto / numero-norma / soglia) + `fact_anchor` regex tolleranti a contesto-tabella e punteggiatura, NON una singola `stale_pattern` letterale. Il test fallisce se l'*entità* ricompare con il valore-stale, ovunque appaia.
2. **Scope multilingua**: rimuovere `TRANSLATION_SUFFIX` dallo skip per i `fact_key` numerici/codici (un codice KBLI è language-invariant: `55110` è `55110` in ogni lingua). Le traduzioni rientrano nel guardiano per i fatti-codice; restano fuori solo per il fact-in-prosa che richiede NLM.
3. **Test di INNOCENZA obbligatorio** (regola madre #3): ogni nuovo `fact_anchor` deve dimostrare di NON scattare su un caso legittimo limitrofo (es. `55110` dentro una nota "old KBLI 2020"), oltre al test di colpevolezza. Mai mergiare una guardia senza prova d'innocenza.
4. **Stale-anche-in-EN → escalation NLM, non auto-fix**: i claim marci nel canonico (C312, 55110) NON si indovinano — si verificano contro NotebookLM ground-truth (no-guess rule). Solo i `traduzione-lag-puliti` (EN corretto come riferimento) sono auto-fixabili.

**GOTCHA:**

- Il test **già si auto-accusa**: il suo stesso commento (riga 8-12) cita *"the malattia-delle-malattie: the SAME stale code reappears across many files and silently rots"* — ma poi lo combatte con substring-match, che è proprio il vettore del "silently rots". L'intento era giusto, l'implementazione resta alla forma.
- "Verde non prova che il sito sia perfetto, prova solo che i known-stale non sono regrediti" (riga 16-18) — vero, ma **understated**: verde non prova nemmeno *quello*, perché un known-stale riformulato/in-tabella/in-traduzione regredisce SENZA far diventare rosso il test. È #2 (Esiste≠Armato) applicato a un guardiano: gira e si dichiara verde mentre il fatto che dovrebbe presidiare è marcio.
- Confine #3-vs-W82: stessa famiglia, NON unire. #3 = guardia che NUOCE (clobbera il corretto, falso-positivo). W82 = guardia che NON PROTEGGE (lascia passare il marcio, falso-negativo). L'antidoto comune è identico: **match su entità/intento, non su substring** + test di innocenza E di colpevolezza.
- Scope reale della classe: 15 entry nel ledger oggi, ognuna una superficie di evasione × N lingue × (tabella|prosa|FAQ-embed). Il numero di "fatti potenzialmente marci ma verdi" è 15 × molteplicità, non 15.

**Reference**: scoperta in `research/operations/campaign/findings/mini-knowledge-SUMMARY.md` (lane L-KNOWLEDGE, ciclo 1-2). Code-fix del sintomo KN-3 in PR #1500 (LKPM it/ru/fr). Artefatti in PR #1501. Spec del guardiano fact-based: `research/operations/campaign/findings/W82-fact-based-sentinel-spec.md` (da redigere, lane KNOWLEDGE o META). Bridge superscar: aggiunto a `#3 — Guard-over-match` come membro under-match. NO valore-secret in questa scar (non applicabile).

---

### 🚨 P0 SECURITY: `apps/cell/.env` holds prod superuser password in cleartext, readable by plain `cat` (2026-06-03)

_Discovered: 2026-06-03 ~20:30 WITA during the organism TAC (read-only diagnosis), when `ssh pro 'cat ~/Desktop/nuzantara/apps/cell/.env'` printed the secret into the session transcript · Severity: **P0 SECURITY** · Status: **REPORTED — rotation + chmod deferred to deliberate operator decision (Antonello)**_

**TRAUMA:** While hunting for Cell's health-check URL, a `cat` of `apps/cell/.env` returned `CELL_DATABASE_URL` and `EVENTBUS_DATABASE_URL` with the **`backend_rag_v2` Postgres password in cleartext**. `backend_rag_v2` is the **superuser** role (per W38 scar, `rolsuper=t`) — so that single string is full production-DB compromise (DROP DATABASE, ALTER SYSTEM, COPY FROM PROGRAM = RCE on DB host). The secret is now in this session's transcript. Two problems compound:

1. The `.env` is readable by a plain `cat` over ssh with no friction → permissions too open (not `0600`).
2. The DB password lives in cleartext in a dotfile on disk (same class as the 2026-04-29 plist-secret-leak and the 2026-05-21 "postgres password in 32 files" P0).

**ANTIBODY (NOT executed — operator decision):**

1. **Rotate** the `backend_rag_v2` password (it's already slated for NOSUPERUSER demotion in W38 spec — rotate + demote together). Update the Fly secret `DATABASE_URL` + every local `.env` (`apps/cell/.env`, `apps/backend-rag/.env`, EventBus consumers) atomically, else half the organism loses DB.
2. **`chmod 600 apps/cell/.env`** on Pro (and audit all `apps/*/.env` for mode > 600) — reduces read surface to owner only.
3. **Stop printing env with secrets into transcripts**: diagnosis must read config via code (`core/config.py` defaults) + logs + DB, NEVER `cat .env`. A single `cat` of a secret-bearing dotfile leaks it irreversibly into the conversation log.

**GOTCHA:**

- Rotation is NOT a solo `ALTER ROLE ... PASSWORD` — it cascades to Fly secret + N local `.env` files + any cron wrapper that sources them. Coordinate as one atomic change in a low-traffic window (same window as W38 demotion).
- The secret is in THIS transcript regardless of rotation — if the transcript is synced anywhere (Drive mirror, logs), it carries the live credential until rotated. Rotation is the only true remediation; `chmod` only stops _future_ reads.
- Orthogonal to W38 (which minimizes blast radius _if_ the secret leaks). This scar is "the secret leaks trivially". Both layer: rotate (this) + demote NOSUPERUSER (W38) = leaked-secret becomes both fresh-invalid AND low-privilege.
- Family: 2026-04-29 plist world-readable secrets, 2026-05-21 P0 postgres password in 32 files. Recurring class: **prod credentials in cleartext on the Pro filesystem**, reachable by any process/agent with read access.

**Reference**: discovered during `research/operations/2026-06-03-organism-tac.md` (organism TAC). Related: W38 (`backend_rag_v2` rolsuper demotion spec), archived 2026-05-21 P0 postgres-password-leak. NO secret value recorded in this scar by design.

---

### ⚠️ W78 (P2 STRUCTURAL/META): il sistema plasma l'agente all'~80% → due rischi sistemici non-presidiati — cicatrice-sbagliata-propagata (no unlearning) + l'-umano-disimpara (escalation drift) (2026-06-13)

_Discovered: 2026-06-13 da un panel asimmetrico 4-LLM (Gemini 3.1 Pro + 3.5 Flash + Codex GPT-5.5 + DeepSeek V4 Pro) sul flusso grezzo di 14 sessioni-madre Fable M5+Pro, analisi 1°/2°/3° grado · Severity: P2 STRUCTURAL/META (non runtime — rischio di governance dell'organismo) · Status: **REPORTED** — research capture `research/operations/2026-06-13-system-shapes-the-agent-4llm.md`, fix di processo operator-decided_

**TRAUMA:** Studiando "quanto del comportamento di Fable è il modello vs il nostro sistema", i 4 LLM convergono: **~75-80% è il SISTEMA** (i 5 layer coercitivi: hook-che-bloccano, memoria persistente, cicatrici, SessionStart injection, Autonomous Ops L2), **20-25% è il modello**. Il sistema impone il COME, il modello porta il PERCHÉ. Corollario verificato: **qualunque modello (GPT-5.5, Gemini) per ~40 sessioni qui dentro diventa "agente Nuzantara"** — il comportamento operativo è sovrascritto dall'esoscheletro, sopravvive solo la qualità del giudizio. Questo è una FORZA (replicabilità, scala, disciplina) ma il 3° grado dell'analisi ha smascherato **due rischi sistemici che nessun layer attuale presidia**:

1. **Cicatrice-sbagliata-propagata (no unlearning):** l'organismo impara solo dagli errori _diventati cicatrice_, le carica a freddo ogni sessione, e **non ha alcun meccanismo di unlearning**. Se una cicatrice è SBAGLIATA (o invecchia, o si contraddice con un'altra in scenari edge), **TUTTI gli agenti ereditano lo stesso errore per sempre**. Precedente reale già accaduto: la ℹ️ META cicatrice "il 13-agent autopsy HALLUCINATED 3 file:line" — un report sbagliato citato come ground-truth. Il rischio scala col numero di cicatrici (548 righe e in crescita).

2. **L'-umano-disimpara (escalation drift):** SYMBIOSIS Legge 5 ("gli allarmi sono input per l'organismo, non per te") + memoria + auto-merge spingono l'agente a disturbare sempre meno l'operatore. Conseguenza di 2° ordine: Antonello passa da programmatore a "Gatekeeper biologico / Oracolo di approvazione", e **se l'agente si ferma (API down, quota, sistema corrotto) l'operatore potrebbe non saper più intervenire a mano**. DeepSeek lo nota già nei transcript: "Antonello chiede 'Finito?' → indica che non ha più il polso diretto." A questo si lega il rischio-dipendenza (nessun fallback umano agile se il sistema cade).

**ANTIBODY (proposto, NON ancora shippato — fix di processo, operator-decided):**

- **Per #1 (no unlearning):** (a) ogni cicatrice dovrebbe avere un campo `verified_on` / `expires_after` o una review periodica; (b) un meccanismo esplicito di RETRACT (marcare una cicatrice come superata/sbagliata, non solo archiviarla); (c) un lint che segnala cicatrici contraddittorie. Modello già esistente da estendere: la ℹ️ META autopsy-phantom-citation è già la prova-di-concetto di "cicatrice che inocula contro un'altra cicatrice sbagliata".
- **Per #2 (umano disimpara):** (a) un digest periodico "cosa ho deciso in autonomia che forse vorresti sapere" (contro l'escalation drift); (b) runbook di intervento-manuale-quando-l'agente-è-giù; (c) accettare il drift come trade-off consapevole, MA documentato — non scoperto il giorno che il sistema cade.

**GOTCHA:**

- **Questa NON è una cicatrice di bug — è una cicatrice di GOVERNANCE.** Non c'è un `exit 1` da aggiungere; è un rischio di 2° ordine dell'intero design SYMBIOSIS. Va probabilmente promossa a blocco in SYMBIOSIS.md, non solo qui.
- **Il rischio #1 è auto-referenziale:** questa stessa cicatrice W78 potrebbe un giorno essere sbagliata e propagarsi. È il paradosso del sistema che documenta il proprio difetto-di-documentazione. L'unico presidio è la regola anti-allucinazione (ri-verifica su disco prima di costruire su una cicatrice) — che però è un nudge, non un blocco.
- **Famiglia:** ℹ️ META 13-agent-autopsy phantom-citation (cicatrice sbagliata già accaduta), W64/W71 (esiste≠armato — qui: "armato ma su premessa sbagliata"), W55 (segnale emesso ma non visto — qui: segnale MAI emesso per escalation drift).
- **Verificato sul disco (gate scettico W65):** i blocchi-prova del 20%-modello che i 4 LLM citano (`[82]` 3-porte-UX, `[91-92]` Subhi-non-cliente) esistono e sono verbatim-corretti — il panel non ha proiettato.

**Reference:** research `research/operations/2026-06-13-system-shapes-the-agent-4llm.md` (+ appendice RAW-PANEL coi 4 output grezzi). Corpus: `~/Desktop/FABLE-FLUSSO-COMPLETO-M5-Pro.txt` (14 sessioni-madre), `decision_opus_mythos_model_2026_06_13.md`. Metodo: panel asimmetrico 4-LLM via skill `opus-mythos`. Sibling: cicatrice gemella sul difetto Opus-interattivo (i layer sono nudge non exit 1 → Opus si ferma/chiede-permesso dove Fable obbedisce).

---

### ⚠️ W80 (P2 STRUCTURAL): il WIP-guard del worktree-cleanup protegge SOLO i worktree sporchi → committare-tutto (per soddisfare stop_verify) rende il proprio worktree reap-eligibile mentre ci lavori ancora (2026-06-13)

_Discovered: 2026-06-13 da Opus durante la sessione W79, quando `git -C .../.worktrees/docs-system-shapes-agent-4llm` ha dato `No such file` a metà lavoro · Severity: P2 STRUCTURAL · Status: **FIXED** — antibody a 2-AND shippato + testato (PR #1401), 35/35 test verdi_

**TRAUMA:** Il worktree attivo `docs-system-shapes-agent-4llm` è scomparso sotto i piedi a metà sessione. La diagnosi iniziale ("colpa del cron cleanup") era SBAGLIATA: il log `~/logs/agent-worktree-cleanup.log` prova che il cron `com.nuzantara.agent-worktree-cleanup.daily` (gira 00:15, ma quel giorno alle 22:08 locale) ha CORRETTAMENTE SALTATO il worktree (`WARN: skip system-shapes-agent-4llm — uncommitted WIP present`). Il WIP-guard (W62 antibody #1) ha funzionato. La causa REALE è un'interazione perversa tra due guardrail: `stop_verify.py` blocca lo Stop su git dirty → spinge a **committare tutto in continuazione**; ma `scripts/agent_start.py --cleanup` reap-a i worktree scaduti che sono **puliti** (`cmd_cleanup` ~L671: controlla solo `is_expired` TTL + `_worktree_has_wip` + `_worktree_recently_active` su FILE). Quindi: **nel momento esatto in cui committi tutto per soddisfare lo stop-hook, il tuo worktree diventa reap-eligibile** — e se un cleanup parte in quella finestra (o lo scateni tu/un subagent durante operazioni di cleanup), te lo porta via mentre ci stai ancora lavorando. Più sei disciplinato coi commit, più il worktree è vulnerabile. (In questo caso il danno è stato ZERO — branch + commit erano su origin + PR — ma è stato fortuna, non design.)

**ANTIBODY (SHIPPATO + testato, PR #1401):** Reap automatico SOLO se **ENTRAMBE** vere (regola a 2-AND):

1. **Nessuna sessione viva nel worktree** — un PROCESSO con cwd o file aperti dentro il worktree (`lsof +D <wt>` / `ps` con cwd-match), NON l'mtime dei file. Il guard di liveness attuale `_worktree_recently_active` (`agent_start.py` ~L481) misura solo mtime di dir/`.git`/`HEAD` → una sessione interattiva Claude Code che RAGIONA/RISPONDE a lungo senza scrivere file né committare risulta "inattiva" pur essendo viva (è ESATTAMENTE come il bug è scattato). Il fix vero è qui: liveness = processo, non mtime.
2. **Lavoro consolidato in `origin/main`** — `git -C <wt> merge-base --is-ancestor HEAD origin/main` (branch GIÀ mergiato). Confronto con `origin/main`, NON con `@{upstream}` del branch.

Implementato in `cmd_cleanup` come guard #3 (dopo WIP + recent-activity): reap automatico SOLO se `_worktree_has_live_process(wt)` è False (nessun processo OS ancorato — `lsof +D` rileva cwd/fd-aperti, coglie la sessione-che-committa-e-ragiona che il guard mtime manca) AND `_branch_in_origin_main(wt)` è True (`git merge-base --is-ancestor HEAD origin/main`). Se uno dei due dice "proteggi" → WARN + skip (non un fallimento, come il recent-activity guard). Scelto `origin/main` e NON `@{upstream}..HEAD` (rev-list count) né main locale: il refuter DeepSeek ha ucciso entrambi — main locale può essere indietro rispetto a origin; rev-list-count protegge gli zombie-mergiati per sempre E scatta sul caso-bug. Il test dell'ancestor contro il ref d'integrazione è il discriminante non-ambiguo. 35/35 test (4 casi cmd_cleanup + 2 real-resolver no-mock: `_branch_in_origin_main` su git vero, `_worktree_has_live_process` su lsof vero).

Se il branch NON è mergiato in `origin/main` → **mai rimuovere, solo WARN**. Se il guard-processo non è implementabile → disabilitare del tutto il reap automatico (solo `--list` + warn + rimozione manuale). Il 24h CI cap (`find_stale_worktrees`) resta il tetto duro.

> ⚠️ **NOTA AUTO-CORRETTIVA (esempio vivo di W78):** l'antibody v1 era SBAGLIATO — `rev-list @{upstream}..HEAD > 0` NON scatta se i commit sono già pushati ma non in main (= il caso reale → reap di nuovo) e protegge per sempre un branch-mergiato-non-cancellato (zombie). Colto dal refuter DeepSeek PRIMA del merge = rischio #1 di W78 (cicatrice-sbagliata-propagata) in atto. Presidio = il panel, non un hook.

**GOTCHA:** (a) La diagnosi "è il cron" è il falso-amico qui — RUN il log del cron e leggi `skip ... WIP` prima di accusarlo (come per W70 `log_tail` false friend). (b) Il `recently_active` guard misura mtime dei FILE del worktree, non la vita della sessione — un agente che passa minuti su risposte/panel senza scrivere file supera la soglia pur essendo vivo. (c) Il danno è mascherato dal fatto che il branch sopravvive su origin: perdi solo il checkout fisico, non il lavoro — il che rende il bug subdolo (non rompe nulla di visibile, solo `No such file` improvviso). (d) Famiglia: W62 (worktree broker TTL — questo è il rovescio: lì i worktree NON venivano puliti, qui vengono puliti TROPPO presto), W70 (false-friend diagnostico), e l'interazione-tra-guardrail (come phase-aware §9: due hook che si ostacolano). (e) **Trappola empirica scoperta in implementazione (W64/W75 — RUN it, don't trust `bash -n`):** `lsof +D` su un linked worktree ritorna **rc=1 ANCHE QUANDO trova** la riga `cwd DIR` viva (emette un warning mentre discende il `.git` _file_ pointer). Keyare la liveness sull'exit code legge una sessione viva come morta. Fix: parsare lo STDOUT per qualunque data-line oltre l'header `COMMAND`, ignorare rc. `bash -n` + AST-parse + una probe su dir-piatta in /tmp passavano tutti — solo il run sul vero linked-worktree ha esposto il bug.

**Reference:** `~/logs/agent-worktree-cleanup.log` (prova dello skip-WIP corretto), `scripts/agent_start.py` `cmd_cleanup` (~L638-700: i 3 guard is_expired/WIP/recent-active, NESSUN guard unmerged-commits), LaunchAgent `com.nuzantara.agent-worktree-cleanup.daily`. Fix shippato PR #1401 (branch `agent/air-m5/infra/w80-reap-guard`, `scripts/agent_start.py` `cmd_cleanup` + `_worktree_has_live_process` + `_branch_in_origin_main`, test `scripts/tests/test_agent_start.py`). Diagnosi: sessione W79 (PR #1399). Famiglia: W62, W70, phase-aware-guardrails §9 (interazione tra guardrail).

---

### ✅ W81 (FIXED): i 3 loop di apprendimento WR3 erano "verdi ma vuoti" — malattia-madre "Omeostasi Tautologica" (telemetria-verde ≠ delta-di-stato); F20+F21 curati come codice+test, F18 escalato (2026-06-14)

_Discovered/Fixed: 2026-06-14 sessione OPUS MYTHOS P4 (Pro), dispatch multi-AI asimmetrico (Gemini synth + Codex refuter; DeepSeek refuter DOWN 402) · Severity: P2 STRUCTURAL · Status: **F20+F21 FIXED (live-proven, 114/114 test WR3), STEP-0 B1 igiene shippata, F18 ESCALATO operatore**_

**TRAUMA:** WR3 (video-room) aveva 3 loop di auto-miglioramento tutti "armed but inactive / green but empty": **F20** validator manifest dead-code (il manifest reale 17 chiavi → hard-fail 4 gate, cablato in nulla); **F21** reflexion stub 816B `sys.exit(0)` (cron nemmeno loaded) vs WR2 reale 314 righe; **F18** evoskill che propone 0 by construction (curriculum risolto 100%). A monte: supervisor **sano+idle** (exit 74 wrapper, NON "FAILED exit=78" come scriveva il DEBT-INDEX) con siccità producer (2 righe outbox, newest 2026-05-22). La malattia-delle-malattie (2° ordine, Gemini): **"Omeostasi Tautologica"** — confondere la _telemetria di processo_ (cron esce 0) con l'_impatto di stato_ (il sistema evolve). Fratello **attivo-ingannevole** di "Esistere≠Armato" (statico, W64/W71) e "catalogare-non-curare" (passivo): qui la macchina corre sul tapis roulant **producendo attivamente verde**. I learning-loop sono l'istanza più insidiosa: la **convergenza** (propongo 0 perché ho imparato tutto) è fenomenologicamente identica all'**inerzia** (propongo 0 perché il curriculum è rotto / il giudice è 402).

**ANTIBODY (FIXED + live-proven):** **F21** — port reale WR2→file-based `scripts/wr3_reflexion_synthesis.py` con il **DELTA GATE** (`_reflexion-state.json` registra `{episodes_found,lessons_written,status∈{SYNTHESIZED,THIN_SIGNAL,NO_INPUT,LLM_FAILED}}` — un run vuoto NON è più `sys.exit(0)` silenzioso) + plist versionato `infra/launchagents/` + install. Live: 5 episodi → claude Sonnet → 5 lessons.md genuine. **F20** — `normalize_assembler_manifest()` + `finalize_episode_manifest()` + enum `PASS-WITH-NOTES` in `wr3_episode_manifest.py`: il manifest REALE su disco normalizzato VALIDA (18 campi, 27 claim_ids, cosine 0.79); il validator non è più dead-code. **STEP-0 B1** — `_heartbeat` timeout 2.0→8.0s env-gated (`scripts/wr3_supervisor.py`): il churn da 2s su tunnel idle aveva prodotto lo stale exit-74 = la causa-radice della mis-diagnosi "FAILED". 114/114 test WR3 verdi. Report `research/operations/2026-06-14-mythos-p4-wr3-debt.md`.

**Contromisura strutturale (Gemini "Mutation & Delta Gate", raccomandata per tutti i loop):** nessun loop è "Healthy" senza (1) **failure-injection** (inietta input rotto → verifica che ALLARMI) + (2) **state-delta** (delta=0 per N cicli → degrada a "Futility Run", non resta verde). F21 implementa il fattore-2 (delta gate); F20 il fattore-1 (test fail-loud); F18 ha entrambi nel readiness-gate `scar_replay` già esistente.

**GOTCHA:** (a) **F18 NON eseguito (escalato):** cron plist fuori perimetro WR3 + `vendor/evoskill` vendored + curriculum=ground-truth-del-giudice (panel review). Scoperta load-bearing: il refuter DeepSeek è tornato **402 Insufficient Balance** → l'evolver (harness+scorer=deepseek-v4-pro) crasherebbe comunque → doppiamente morto. (b) **Zero credito Veo speso:** l'episodio reale end-to-end (STEP-0 A1) resta operatore (spende Veo + muta prod outbox + cascata agenti); la **logica di dispatch è provata FREE** da 24 test esistenti (consume→route→ack con fake-PG). (c) **Enum widening `PASS-WITH-NOTES` deliberato** (il critic LIVE lo emette — escluderlo era il bug); se non deve contare come pass per i downstream, mapparlo a `DEGRADED`. (d) **W74 in atto:** le spec sembravano phantom ma erano solo su `origin/main` (checkout locale stale `e2b355f45`); ri-verificate tutte su disco prima di costruire. (e) **Refuter esterni entrambi fragili** (DeepSeek 402, Codex stdin-confusion al 1° tentativo) → gate finale = Opus, ogni claim ri-eseguito su disco/PG/pytest questo turno.

**Reference:** report `research/operations/2026-06-14-mythos-p4-wr3-debt.md`. Spec `research/operations/specs/WR3-{DEBT-INDEX,supervisor-revival,F18,F20,F21}.md`. File: `scripts/wr3_reflexion_synthesis.py` (nuovo), `scripts/wr3_episode_manifest.py` (normalizer+enum), `scripts/wr3_supervisor.py` (B1 heartbeat), `infra/launchagents/com.balizero.wr3.reflexion.weekly.plist`+`install_wr3_reflexion.sh`, test `scripts/tests/test_wr3_{reflexion_synthesis,manifest_normalize}.py`. Famiglia: W64/W71 (Esistere≠Armato), W74 (green cron≠working + phantom-citation), connectome TAC (catalogare-non-curare). Modello readiness-gate: `agent-library/scar_replay/scar_replay.py`.

---

## Archived

Resolved scars moved to [`cicatrix-scars-archive.md`](./cicatrix-scars-archive.md) (not auto-loaded per session). Currently archived:

**Archived 2026-06-13 sweep+W68 (16 scars, RESOLVED/stable — oversize remediation to land the W78 commit <40k char, rebased on main+W77):**

- W62, agent-library-evolver, W38, live-503+CORRECTION, W64, W65, W67, W68 (subsumed by live W73/W77), P3-flaky-clock-race, W69, W71, W72 (subsumed by live W73), M5-dev-env-path-drift, W74, W76. Full TRAUMA/ANTIBODY/GOTCHA in archive — grep by W-number.

**Archived 2026-06-13 (W75 — RESOLVED/stable, swept to keep cicatrix <40k while landing the W80→FIXED update; the W64/W75 cross-ref in the W80 GOTCHA stays valid — grep `W75` in the archive):**

- ✅ **W75** (P2 SECURITY): `nuz_db_refresh.sh` DUMP_MODE=fly-ssh leaked the readonly DB password (secret as line 1 of a `bash -s` script). FIXED PR #1372 (`_shq()` helper, secret on stdin not argv). Full TRAUMA/ANTIBODY/GOTCHA in archive.

**Archived 2026-05-27 sweep (~36 scars, RESOLVED/INFO/STRUCTURAL ≤2026-05-23 — W31–W57 series, T0.2/T3.2/Wave 1/3/4 spec runs, mata-garuda consumer-group + NER worker repairs, CRM-Guardian Phase 1.5 OCR layer, P0 SECURITY postgres password rotation, Cell `.env` quoting trap, KG-linker dead-upstream, claude mcp list stale-status, canva-renderer flycast DNS wrapper):**

- See archive file for full TRAUMA/ANTIBODY/GOTCHA — grep by W-number, date, or keyword. Notable entries: W31 fly_machines_restart actuator, W34 asyncpg.PostgresError lint guard, W37 incident ledger, W48 cell_skills.source migration 196, W50/W51/W52 HOME-fork family, W55 alerter retry, W57 wa-mirror enrichment self-healing.

**Archived 2026-05-25 sweep (8 scars, RESOLVED/INFO < 2026-05-18):**

- ⚠️ STRUCTURAL: GDRIVE_COMPANIES_FOLDER_ID phantom + wa-mirror bypasses POST /api/clients (2026-05-21) — fix shipped commit `1a3824b39`
- ⚠️ STRUCTURAL: Intel Lake routing prefix-blind for subdomains (2026-05-20) — patched PR-B1a
- ✅ RESOLVED: outbox-drain stderr noise (2026-05-20) — PR-B2
- ⚠️ STRUCTURAL: WR2 master template requires verified richtext slot count (2026-05-10 → bypassed 2026-05-13)
- ⚠️ STRUCTURAL: WR2 canva-apply path coupling (2026-05-10) — workaround shipped
- ✅ RESOLVED: LegalIngestionService bypasses OpenAI 300k token batch limit (2026-05-10)
- ⚠️ STRUCTURAL: NLM feeder split-brain — base_worker redis-cli no host arg (2026-05-06) — patched same day
- ✅ RESOLVED: Backend `/health` masks `app.state.startup_failed` (2026-04-29) — PR #337

**Historical archives (pre-2026-05-25 cleanup):**

- ✅ RESOLVED: OpenClaw MCP child apparent mortality = test artifact (2026-05-02)
- ✅ RESOLVED: Backend prod down — drive_poll_service called missing method on ServiceAccountDriveService (2026-04-29)
- ✅ RESOLVED: Atlas migrate-lint paywalled in v0.38 — pivoted to Squawk (2026-04-26)
- ✅ RESOLVED: SQL v2 migrations apply on OLD image, not the freshly-built one (2026-04-26 → 2026-04-29)
- ✅ RESOLVED: Deploy crash before health check went unalerted (Air A3, 2026-04-18)
- ✅ RESOLVED: Dockerfile cell-core missing (PR #56 → PR #62 → monorepo workspace promotion)

---

### ⚠️ W70 (P2, renumber of m5-branch W67): sentinel + meta-watchdog OK but 39 jobs DLQ-terminal (21 in 24h), healing=0 — common cause = Air-decommissioned path-drift in backup scripts + sentinel captures no real stderr (blind autopilot) (2026-06-09)

_Discovered: 2026-06-09 ~04:45 WITA during FASE-0 instrumentation re-arm (read-only audit from M5 via ssh pro) · Severity: P2 · Status: **DIAGNOSED — fix deferred to a dedicated Pro session**. Renumbered from the m5-branch's "W67" because W67 was independently taken on main by the wa-mirror reconnect-storm scar (2026-06-07); two different scars, same number → this DLQ one becomes W70._

**TRAUMA**: FASE-0 re-arm went hunting for "disarmed guardians" (per the 9-spec armies verdict). The verdict said `sentinel_meta_watchdog` was "esiste ma non gira" — FALSE: `launchctl list` on Pro shows `com.nuzantara.sentinel-meta-watchdog` LOADED, `LastExitStatus=0`, state file fresh. The watchdog WORKS. But verifying it surfaced the real wound: `sentinel_status.json` reports `jobs_circuit_terminal=38 dlq_terminal=38 healing_actions_24h=0`. The true source `~/.agent/decisions/dlq.json` → **39 entries, all status=TERMINAL**, age **21 ≤1d / 12 2-7d / 6 8-30d**. NOT stale legacy noise — CORE infra jobs dying NOW: `fly_pg_backup`, `qdrant_snapshot`, `fly_qdrant_backup`, `rag_canary`, `garuda_indexer`, `knowledge_graph_builder`, `nlm_nb1_daily_refresh`, `post_publish_poller`, etc. The fleet sheds jobs into terminal-DLQ and **nobody resuscitates them** (`healing_actions_24h=0`).

Two compounding root causes (found by EXECUTING the real scripts, which the sentinel does not):

1. **Air-decommissioned path-drift (W50/W51/W52 family)**: `qdrant_snapshot` + `fly_qdrant_backup` fail with `/Users/nuzantara/Projects/nuzantara/.../.env not found` — the **Air checkout path decommissioned 2026-05-05**. Live path is `~/Desktop/nuzantara`. Hardcoded dead-machine path.
2. **`fly_pg_backup` runs but produces a 0-byte dump**: `pg_dump` inside the Fly primary returns empty, silent.

**META-problem (load-bearing)**: the sentinel's `log_tail` captures only the retry-wrapper summary ("exit 1 after 3 attempts"), NOT the job's real stderr. So every terminal entry has `classification={type:UNKNOWN, confidence:0.0}` → the autopilot retries blind 10× → gives up → TERMINAL. Observability exists (we KNOW 39 died) but is BLIND on WHY — the exact "instrumentation disarmed" thesis made concrete.

**ANTIBODY (DIAGNOSED, NOT executed — highest-leverage = #3):**

1. grep `~/scripts/*backup*.sh` + `*snapshot*.sh` for `Projects/nuzantara` → repoint to `~/Desktop/nuzantara` (resuscitates the qdrant pair + several of the 21).
2. Fix `fly_pg_backup` 0-byte dump (Fly-side pg_dump empty; cf. W38 role demotion in flight).
3. Make the sentinel capture REAL stderr in `log_tail` (not the retry-summary) — re-arms the WHOLE auto-heal loop.
4. Resolve `com.nuzantara.sentinel` one-shot-vs-daemon mismatch (RunAtLoad, no StartInterval → one-shot the watchdog tamps every ~1h, W55-masked slow crash-loop).

**GOTCHA**: monitor-alive ≠ fleet-healthy — read `dlq.json` / `jobs_circuit_terminal` + `healing_actions_24h`, not just "is the sentinel running". `log_tail="exit 1 after 3 attempts"` is a false friend (zero diagnostic signal). The Air decommission (2026-05-05) keeps spawning path-drift scars 35 days later — no sweep ever grepped all scripts for `Projects/nuzantara`. Family: W50/W51/W52 (Air-path drift), W55 (cooldown masks slow failure).

**Reference**: `~/.agent/decisions/dlq.json` (39 terminal), `sentinel_status.json`, `~/scripts/nuzantara-sentinel.py` (log_tail handling). Origin: m5 branch `agent/air-m5/fase0-instrumentation-rearm` commit d6ae97e33. Pending: triage 39 DLQ + 3 fixes on a dedicated Pro session.

---

### 🐛 W73: WhatsApp `_guard_*` family — 5 MORE over-match defects found by an 8-agent parallel quality-loop; root class = bare-substring triggers + unreachable positive-gating escapes (2026-06-09)

_Discovered: 2026-06-09 by an 8-agent parallel quality-loop (5 service domains + 3 transversal axes: guard-hunter, multilingua, adversarial-caution) sweeping 80 questions against the live OpenClaw/GPT-5.5 bridge · Severity: P1 (2 live-proven wrong-topic answers) + P2 (3 over-caution) · Status: **FIXED** — all 5 + word-boundary helper + 4 persona reply_rules, 11 regression tests (38/38 green), both copies byte-identical + bridge restarted + 7/7 live-verified end-to-end_

**TRAUMA:** After W68 (villa) and W72 (b211), a structured 8-agent fan-out confirmed the model itself is SOLID (zero price/KBLI/regulatory hallucinations across 80 Qs, all verified to the rupiah vs `migration_066`/`157`) — but **five more `_guard_*` functions clobber CORRECT answers**, all the same class:

1. **`_guard_villa_kbli_reply` / `_VILLA_TERMS` (P1, live-proven):** the term tuple held `"ota"` and `"rent"` as bare substrings — `"ota"` matches "qu**ota**"/"bi**ota**", `"rent"` matches "diffe**rent**"/"cu**rrent**". A live probe _"Which KBLI code covers the import quota for frozen food distribution?"_ returned the **verbatim villa Airbnb 55203 canonical** — a food-import client got a villa answer.
2. **`_guard_lkpm_reply` (P1, live-proven):** the escape clause `"1 to 15 april" not in reply` was near-unsatisfiable — ANY correct LKPM answer lacking that exact English literal (a definition, an ID/IT answer, "April 1-15") was clobbered into the deadline-heavy canonical. A "what is LKPM" definition got the "do not use old 1-10 deadlines" lecture.
3. **`_guard_tax_compliance_reply` (P2):** the OSS/BKPM verify-suffix was appended on bare `"tax"/"spt"/"ppn"/"pph"` — so 5/10 STABLE-fact answers (Coretax definition, SPT deadline, VAT rate) got an irrelevant compliance tail. Worst case: "What is Coretax?" (a dictionary definition) got a risk-verify suffix.
4. **`_guard_cafe_pma_reply` (P2, intermittent live):** fired on `"pt pma" in message` + cafe/coffee NEL **reply** (never checking the message) — so a definitional "difference between PT PMA and PT lokal" answer that named a cafe as an example was randomly clobbered into the cafe-Canggu canonical.
5. **`_guard_nominee_reply` (P2, two compounding bugs):** (a) the trigger was the literal word `"nominee"` only, so the most common real request — "can my Indonesian friend hold the title for me?" — never fired; (b) even when it fired, the canonical said only "risky / red flag", **never illegal/void** under agrarian law, so a client could read "risky but doable".

**ANTIBODY:** Root-class fix + 5 targeted gates, all live-verified:

- **`_contains_any_word()`** new helper: word-boundary (`\b`) containment so short triggers (`tax`/`spt`/`lease`/`ota`) can't match inside longer words. Applied to the tax trigger; the recurring substring-trap root.
- **(1)** dropped `"ota"`/`"rent"` from `_VILLA_TERMS` (kept `"rental"`). Food-import query no longer mis-classified.
- **(2)** LKPM escape rewritten to **negative-gating**: clobber only on a stale-deadline marker OR a wrong deadline-window assertion (`deadline`/`due date`/`no later than` terms — NOT generic verbs like "submit"); a reply with no deadline at all (pure definition) passes.
- **(3)** tax suffix gated on **RISK/PENALTY/EXPOSURE intent** (`risk`/`penalty`/`denda`/`fine`/`late`/`audit`/`compliance`/`owe`/…), not bare tax keywords. Stable rate/definition answers stay clean.
- **(4)** cafe guard now requires cafe intent in the **MESSAGE** (`cafe`/`coffee`/`kafe`/`kedai`/`56303`/…), not merely in the reply.
- **(5)** nominee: a **compositional intent detector** `_is_nominee_intent()` (verb `hold/keep/register/put-in` + asset `title/land/property/shares` + proxy `for me/friend/wife/atas nama`) catches lexical variants a fixed phrase list missed ("hold the land **title** for me"); the canonical now states the arrangement is **ILLEGAL and void under Indonesian agrarian law** (land can fall to the State, no enforceable claim) in all 3 languages; a short risky-only answer to a real request is substituted regardless of length, while a correct definitional answer that already frames the illegality passes.
- **4 persona `reply_rules`** (the over-caution levers, not guards): never convert a published threshold into a personal eligibility verdict; working in Indonesia plainly requires a work permit and a tourist/VOA does not grant work rights (say it, don't hedge to "I wouldn't rely on that"); office is in the Kerobokan area of Bali by appointment; VAT is 11% effective / 12% headline (PPnBM luxury full 12%) stated consistently across languages.

11 new regression tests, **38/38 green** — each asserts the guard does NOT clobber a CORRECT answer AND still catches the bad one (the W68/W72 discipline). Both copies patched byte-identical (repo `scripts/openclaw_whatsapp_bridge.py` + HOME `~/.openclaw/bin/openclaw_whatsapp_bridge.py`), bridge restarted, **7/7 live-verified** (food-import→no-villa, LKPM-def→clean, Coretax→no-suffix, PT-PMA-vs-lokal→no-cafe, nominee×2→ILLEGAL, + W68 villa-leasehold and PT-PMA-HGB regressions hold).

**GOTCHA:** This is the FOURTH+ guard-over-match sweep (W68, W72, now 5 at once). The recurring root is now named: (a) **bare-substring triggers** — `_contains_any` does `term in value`, so every short term is a landmine; use `_contains_any_word()` for triggers. (b) **positive-gating escapes** — a guard that keeps the reply only if it contains one exact phrase (`"1 to 15 april"`, `oss`+`bkpm`) is unreachable for a correct answer phrased any other way; flip to **negative-gating** (clobber only on a detectable WRONG signal, default passthrough). (c) **fixed phrase lists are brittle** — "hold the title for me" missed "hold the land title for me"; prefer a compositional verb+noun+signal detector. (d) HOME-fork double-file (W50/W51/W52) — the live bridge runs the HOME copy; a `scripts/`-only fix is invisible until HOME is patched + bridge restarted. The cherry-pick base for this PR pulled #1197 (persona + b211) forward so this is a super-set; #1197 can close as subsumed. **Meta-recommendation (not yet shipped): a shared test-matrix harness — for each `_guard_*`, one "correct-answer-passes" + one "wrong-answer-clobbers" assertion — would have caught all five at once and gates the next one.**

**Reference:** branch `agent/air-m5/wa-guard-family-fix`, fix commit (this PR). Edited: `_VILLA_TERMS`, `_contains_any_word` (new), `_guard_lkpm_reply`, `_guard_tax_compliance_reply`, `_guard_cafe_pma_reply`, `_canonical_nominee_answer`, `_is_nominee_intent` (new) + `_guard_nominee_reply`, `_build_prompt` `reply_rules`. Tests: `apps/backend-rag/backend/tests/unit/scripts/test_openclaw_whatsapp_bridge_script.py` (11 new). Discovered via the 8-agent quality-loop (memory `decision_zantara_wa_live_test_protocol_2026_06_07`). Family: `_guard_*` over-match (W68 villa, W72 b211), HOME-fork double-file (W50/W51/W52), bare-substring-trigger root class.

---

### 🐛 W77: WhatsApp `_guard_*` family — QUARTA sweep trova l'ASSE LINGUISTICO: 10 wrong-answer-passes ID/IT + 1 falso positivo nominee; il layer era calibrato in inglese su un canale EN/ID/IT (2026-06-13)

_Discovered: 2026-06-13 dalla sessione Fable 5 "Zantara Golden Corpus" — probe empirico di 13 casi ID/IT sui guard live, 10 GAP confermati PRIMA del fix · Severity: P1 (risposte sbagliate a clienti in 2 delle 3 lingue del canale) · Status: **FIXED** — 11 fix + matrice trilingue 80 casi + META gate lingue, 165/165 test verdi (PR branch `agent/nuzantara/zantara-golden-corpus`)_

**TRAUMA:** Dopo W68 (villa), W72 (b211/persona), W73 (5 guard in un colpo), la quarta sweep trova l'asse che le precedenti non vedevano: **la lingua**. La GUARD_MATRIX (shippata con l'hardening F06) era English-only, e i gate dei guard pure: (1) `document_status` aveva marker unsafe SOLO inglesi → `"KITAS kamu sudah disetujui dan siap diambil"` (status inventato, la classe più pericolosa) arrivava al cliente non clobberato, idem l'italiano `"già approvata"`; (2) `lkpm` stale-markers senza mesi ID/IT → `"la scadenza LKPM è il 10 luglio"` (deadline ABROGATA da PerBKPM 5/2025) passava in IT e ID; (3) `property_zoning` non si ARMAVA affatto su messaggi IT/ID (secondo braccio trigger solo `zoning/residential/zone/lease`) → wrong "non serve permesso per l'Airbnb" passava; (4) `hak_milik`: `_normalize_text` converte gli apostrofi curvi ma NON strippa gli accenti, quindi il marker `"puo' detenere"` non matchava mai il naturale `"può detenere"` → una risposta SBAGLIATA "può detenere Hak Milik tramite PMA" passava se <125 parole; (5) `cafe_pma`: "caffè" (doppia f) non contiene "cafe" come substring → guard mai armato su domande italiane; (6) `tax_compliance`: "IVA"/"tasse" assenti dai trigger → risk-suffix mai applicato a domande fiscali italiane; (7) over-match inverso: una risposta IT CORRETTA che inquadrava il B211 come "una vecchia dicitura" veniva CLOBBERATA (gli escape marker erano `old`/`lama`, mai `vecchia`); (8) il nuovo probe no_trigger ha trovato un falso positivo EN: "can you book the hotel room under my wife's name?" riceveva la lezione sull'illegalità del nominee (solo il gerundio "booking" era nei false-positive admin, non "book the" né "hotel").

**ANTIBODY:** (a) 9 fix chirurgici ai gate (marker affermativi ID/IT per document*status; "vecchia/vecchio"+"non più"+"tidak lagi"+route corrente/attuale/saat ini per b211; varianti accentate in \_NEGATIONS/\_CAN_OWN per hak_milik; mesi ID/IT + "tanggal 10" negli stale-markers lkpm; zona/residenziale/residensial nel trigger zoning; iva/tasse nel trigger tax; caffè/caffe/caffetteria + reply-check ristorante per cafe_pma; book the/book a/book me/hotel nei false-positive nominee). (b) **Refactor `_apply_reply_guards()` + `_REPLY_GUARD_CHAIN`**: la catena di produzione esce dall'endpoint inline e diventa l'unica fonte di verità condivisa da endpoint e test — l'ordering non può più driftare, e 6 test full-chain coprono ordering/no-double-mutation/format-net. (c) **GUARD_MATRIX 20→80 casi**: pass+clobber × en/id/it × 10 guard + un probe no_trigger per guard. (d) **META gate lingue** (`test_guard_matrix_covers_languages_and_no_trigger`): ogni `\_guard*\*`futuro FALLISCE la suite finché non porta pass+clobber in TUTTE e tre le lingue + no_trigger — dimostrato iniettando un guard fantasma (3/3 gate scattano). (e) Golden corpus`apps/evaluator/zantara_persona_eval/golden_corpus.json`(50 scenari × 3 lingue, ogni fatto con fonte,`valid_until`sui deperibili) +`validate_corpus.py` + CI binding.

**GOTCHA:** (1) **`_normalize_text` NON strippa gli accenti** — ogni marker italiano deve esistere in ENTRAMBE le grafie ("puo'" E "può"); è la versione linguistica del substring-trap. (2) Le tre lingue del canale NON sono simmetriche nei gate: l'indonesiano era parzialmente coperto (i canonical sono trilingui dal D1), l'italiano quasi zero — quando si aggiunge un marker, aggiungerlo per TUTTE le lingue del canale, il META gate ora lo forza. (3) Il probe no_trigger è quello che ha trovato il falso positivo nominee: testare solo pass+clobber non basta, la terza polarità (messaggio off-domain → reply intatta) è dove vivono i substring-trap. (4) **HOME-fork (W50/51/52)**: il bridge live gira da `~/.openclaw/bin/openclaw_whatsapp_bridge.py` — i fix proteggono i clienti SOLO dopo sync della copia HOME + `launchctl kickstart -k gui/501/com.nuzantara.openclaw-whatsapp-bridge` post-merge. (5) La famiglia è ricorsiva: W68 trovò 1 bug, W72 2 layer, W73 5 bug + raccomandò l'harness, l'harness nacque EN-only, W77 trova l'asse lingua. La domanda per la quinta sweep è già scritta: **quale asse manca ancora? (history/context multi-turn? code-switching ID-EN nello stesso messaggio?)**

**Reference:** branch `agent/nuzantara/zantara-golden-corpus`. Report completo: `research/operations/2026-06-13-zantara-golden-corpus-fable5.md`. Probe empirico pre-fix: 13 casi, 10 GAP (in sessione). Famiglia: W68 (#1195), W72 (#1197), W73, F05-F39 hardening, HOME-fork (W50/51/52). Ground truth fonti: `research/operations/2026-06-13-knowledge-decay-audit-fable5.md` (41 claim verificate).
