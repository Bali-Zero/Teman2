# cicatrix-superscar.md — le 10 famiglie (PONTE)

> **PONTE, non enciclopedia.** ~99 cicatrici in 10 famiglie + orfane. Per famiglia: **malattia**,
> **segnale-precoce**, **antidoto**, **membri** (3-8 parole — il corpo vive in
> `cicatrix-scars.md`/`-archive.md`, mai qui; unica eccezione le righe **PR-1 landing**, senza
> W-number, col corpo in `PENDING-ARMS.md`, che il gate di completezza non sa risolvere). Dettaglio →
> grep il W-number, o `scar query "<tema>"`/`--list`/`--family N`. ⚠️ **Anche questo file può esserti
> arrivato STALE**: dove il main checkout è tenuto indietro di proposito (M5) la copia iniettata E
> quella letta da `scar` sono entrambe vecchie — il riferimento è `git show origin/main:<path>`.
>
> **Budget ≤14KB**, armato da `scripts/tests/test_superscar_budget.py` (byte + completezza: ogni W-number qui deve avere un
> corpo reale). Iniettato
> a OGNI sessione e OGNI subagent: ciò che aggiungi lo paga tutta la flotta, per sempre. Tre nomi
> disambiguano collisioni: `W81-armamento-sospeso`, `W81b-dlq-blind-heal-loop`, `W84-tcc-dead`.
> Storia: `research/operations/2026-08-21-token-ceremony-ci-system-audit.md`.
>
> **Dominanza:** #1 HOME-fork, #2 Esiste≠Armato, #5 Sibling-race, #4 Secret-clear coprono 65-75%.

---

## #1 — HOME-fork drift (deploy-path desync)

**MALATTIA:** il runtime esegue una copia in `$HOME` (path hardcodato) che diverge dal repo. Il fix
entra nel repo, la copia viva non lo vede.

**SEGNALE-PRECOCE:** plist/cron che invoca `~/scripts/` o `~/.openclaw/bin/` invece del repo; path
con username; "due copie byte-identical".

**ANTIDOTO:** lint CI `cmp -s` live vs git, contro `origin/main` mai contro il checkout locale — un
checkout indietro accusa la copia viva (W106b, #9).
**→ ESEGUIBILE:** `scripts/lint_home_fork.py` — sha256 sulle coppie dichiarate, `--discover`, exit 1|2|4.

**MEMBRI:** W50/W51/W52 (madre: wrapper/plist/script) · W68/W72/W73 (bridge openclaw) · W70 (path-drift Air) · W76 (repomap su checkout stale) · M5-dev-env (venv+marketplace) · TAC wa-mirror (fork non promossa) · W81-armamento-sospeso (deploy worktree sparito).
**→ dettaglio:** archive (W50/W51/W52/W68/W76/M5-dev-env) + cicatrix-scars.md (W70/W81-armamento-sospeso)

> _Cross-famiglia:_ **W84-tcc-dead** (#2) — wrapper sotto `~/Desktop` TCC-protetto.

---

## #2 — Esiste ≠ Armato (cron theater / blind autopilot)

**MALATTIA:** demoni/cron "verdi" (exit 0, KeepAlive attivo) mascherano worker morti, eccezioni
ingoiate, output vuoti.

**SEGNALE-PRECOCE:** `/health` che guarda il web non i worker; cron verde a output vuoto;
`except` permissivi; log-tail senza diagnostica.

**ANTIDOTO:** monitora l'esito/heartbeat, non PID né exit-code («green ≠ working, leggi l'OUTPUT»).
W81: anche lo STATO DI ATTIVAZIONE — costruito≠attivato è sospeso, non vivo. W120: la sonda deve
leggere la STESSA chiave che il reporter emette, o l'allarme si azzera muto.
**→ ESEGUIBILE:** `scripts/pending_arms_report.py` — allarma righe `PENDING-ARMS.md` aperte >48h.

**MEMBRI:** W74 (reflexion cron-theater) · W69 (required-checks disarmati) · W64/W34 (asyncpg silent-death) · W71 (mcp_integrity gira e mente) · W32 (pg-bridge muto) · 503-RAG (health=200, worker giù) · W70 (log_tail cieco) · W81-armamento-sospeso (~20 cron exit 127/78) · W81b-dlq-blind-heal-loop (14 DLQ mai puliti) · W84-tcc-dead (launchd perde TCC) · W84-tccutil-recidiva (`reset All` creduto read-only) · W87 (dev identity su proxy PROD) · W97 (display-cap letto come completo) · W98 (dependabot bypassa `!=`) · W101 (fail-closed decapitato da `sh -e`) · W101-recidiva-fly-backup (Fase 2 non parte) · W104 (`redis-cli` esce 0 con NOAUTH) · W107 (1 wrapper su 5) · W108 (19/20 cron muti) · W110 (heartbeat sull'organo errato) · W116 (allarme su esito giusto, cura morta) · W118 (11h fermo, nessun rosso) · W120 (sentinella di famiglia disarmata) · W121 (mutation su bytecode avvelenato) · W122 (rosso mente: lavoro fatto, SIGINT→130) · W123 (`success` ≠ armato) · W124 (PR DIRTY: `completed` su un sottoinsieme) · W126 (draft non espelle dalla coda).
**→ dettaglio:** cicatrix-scars.md (resto) + archive (W34/W32/W64/W69/W71/W74/503)

---

## #3 — Guard-over-match (substring trapping) — gemello UNDER-match (W82)

**MALATTIA:** la guardia decide su substring, non entità/intento. OVER-match = clobbera risposte
corrette. UNDER-match = sorveglia una frase letterale, il fatto marcio riformulato sfugge e resta
verde.

**SEGNALE-PRECOCE:** `if "keyword" in testo`; escape-clause su UNA frase; trigger corti
(`lease`/`429`) dentro token più lunghi; scope che salta una superficie.

**ANTIDOTO:** nessuna guardia senza test di innocenza E colpevolezza, su entità/intento mai su
substring. **→ ESEGUIBILE:** `infra/guard-conformance/` — censita senza guilt+innocence = FAIL CI.

**MEMBRI:** W68 (villa-leasehold zoning) · W72 (B211/KITAS deflesso) · W73 (5 over-match insieme) · W77 (asse linguistico) · W68b (variante) · W82 (cieco alle traduzioni) · W83 (3 falsi BLOCK) · W84 (char-class matcha newline, fonde comandi) · W85 (`stash` blocca `list`) · W91 (flag in un commento apre l'eccezione) · W92 (path relativo vs cwd) · W94 (esenzione whole-command) · W95 (blocca una fixture, cieco ad `async def`) · W99 (self-closing salta font-inject) · W105 (troncatura primo segmento) · W109 (esenzione per collocazione) · W112 (Prettier riscrive le cicatrici) · W115
(veto post-selezione) · W117 (payload svuotato pre-esenzione) · W119 (`\s` attraversa il newline) · W127 (`levelname` reso, non `levelno`).
**→ dettaglio:** cicatrix-scars.md (resto) + archive (W68/W72)
**PR-1 landing** (corpo in `PENDING-ARMS.md`): `git branch -D` da worktree è repo-wide, la guardia giudica il cwd.

---

## #4 — Secret in the clear (world-readable credentials)

**MALATTIA:** segreti prod esposti sul filesystem con permessi larghi, bypassando Fly secrets. Il
`.bak` eredita l'esposizione.

**SEGNALE-PRECOCE:** `cat`/`echo` di file-chiave su ssh; `.bak` senza chmod; secret sullo stdin che
`bash -s` consuma.

**ANTIDOTO:** `chmod 0600` su dotfiles (live + `.bak*`); mai `cat` di un secret in diagnosi; ruota
se è stato world-readable.
**→ ESEGUIBILE:** `scripts/secrets_permissions_audit.py` — `--fix` chmod 0600, blind-scan guard exit 2.

**MEMBRI:** P0 2026-06-03 (`apps/cell/.env` readable) · W65 (`.bak` 64-hex key) · W75 (fly-ssh leak
su pipe) · P0 2026-05-21 (pw in 32 file) · 2026-04-29 (plist world-readable).
**→ dettaglio:** cicatrix-scars.md (P0-cell.env) + archive (2026-05-21/04-29/W65/W75)

---

## #5 — Sibling-race / shared-worktree chaos

**MALATTIA:** agenti/cron paralleli sullo stesso checkout → collisioni stash, distruzione silente di
modifiche altrui, reap mentre ci si lavora.

**SEGNALE-PRECOCE:** `git checkout` nella cartella globale; worktree pulito-ma-scaduto reapabile
mentre è vivo; untracked non tuoi.

**ANTIDOTO:** ogni agent in un worktree dedicato (`agent_start.py`); reap solo a 2-AND (nessun
processo vivo AND già su origin/main); leave-dirty sul lavoro sibling.

**MEMBRI:** W62 (6 worktree, TTL violato) · W63 (nested worktree) · W80 (reap con commit non-mergiati)
· agent-library-evolver (REPO_ROOT condiviso) · W59 (madre) · 2026-04-29 (untracked persi).

**→ dettaglio:** cicatrix-scars.md (W80/W59) + archive (W62/W63/evolver)

---

## #6 — Anti-hallucination blindness (phantom citations)

**MALATTIA:** un LLM immagina file/righe/conclusioni plausibili; chi sta a valle le prende per vere.

**SEGNALE-PRECOCE:** piano su un report LLM senza audit fisico; `file:line` mai ri-eseguito;
refuter che boccia senza ri-grepare.

**ANTIDOTO:** mai costruire su un path citato senza `find`/`ls`/`cat` in QUESTO turno. Anche il
refuter allucina (W65).

**MEMBRI:** META 2026-06-05 (3 file:line falsi) · W74 (phantom scorer.py) · W65 (refuter
falso-refuta) · W78 (cicatrice-sbagliata-propagata) · W100 (blind agreement, 7/8 false-clean) · W90 (ground-truth stantio) · W113 (la correzione mente). Linea: W65→W90→W100→W113.
**→ dettaglio:** cicatrix-scars.md (W78/resto) + archive (META-autopsy/W65/W74)

---

## #7 — Daemon-vs-cron KeepAlive misconfig

**MALATTIA:** `KeepAlive=true` su uno script one-shot → ogni exit letto come morte → restart storm;
figli `nohup` SIGTERM-killati ogni ciclo.

**SEGNALE-PRECOCE:** `KeepAlive=true` + `exec <one-shot>` o `nohup … &`; contatore `runs` che cresce.

**ANTIDOTO:** loop bloccante reale (`while true; do …; sleep N; done`) o `StartInterval` senza
KeepAlive. **→ ESEGUIBILE:** `scripts/lint_plist_keepalive.py` — `nohup &`=FAIL.

**MEMBRI:** W67/W67b (wa-mirror reconnect storm) · W60 (Fly api flapping) · 2026-04-29 (53 plist, 13%
corretti).
**→ dettaglio:** archive (W60/04-29/W67/W67b)

---

## #8 — Network flap / proxy fragility

**MALATTIA:** componenti long-running crashano sui flap di rete (proxy/WG/pg-proxy).

**SEGNALE-PRECOCE:** chiamata singola senza retry; log pieni di `TimeoutError`; alerter
single-attempt.

**ANTIDOTO:** socket persistenti keep-alive; retry con backoff; cattura `InterfaceError` oltre
`PostgresError`.

**MEMBRI:** W49 (98 timeout) · W55 (Telegram one-shot) · W32 (InterfaceError ignorato) · W47 (solo numero, nessun dettaglio).
**→ dettaglio:** archive (W49/W55/W32) + cicatrix-scars.md (W47)

---

## #9 — State-schema mutation drift

**MALATTIA:** uno step cambia il formato di un payload/file-stato; i lettori a valle si rompono.

**SEGNALE-PRECOCE:** modifica ai dati intermedi (DLQ, redis, `*.last.json`) senza scope end-to-end;
uno stato letto da un proxy (SHA/timestamp) e non dal CONTENUTO.

**ANTIDOTO:** deploy unificato sui contratti condivisi. W88: "già su main" si verifica per CONTENUTO
(diff vuoto/subset), mai per patch-equivalenza, SHA-ancestor o timestamp.
**→ ESEGUIBILE:** `scripts/branch_graveyard_cleanup.sh::content_on_main()`.

**MEMBRI:** W54 (timestamp rompe staleness) · W53 (DLQ TERMINAL mancante) · W61 (attempts droppati) · W86 (DOCSYNC stale boccia innocenti) · W88 (cherry mente post-squash) · W102 (two-dot accusa la PR dei file di main) · W106 (proxy congelato sceglie credenziale morta) · W106b (checkout come proxy) · W109b (2 PR si bloccano) · W111 (`gh run rerun` su merge-ref stantio) · W114 (fake e codice
condividono l'immaginazione) · W118 (3 proxy merge-queue mentono) · W125 (fusione pulita, la resa a mano la tiene) · W131 (un nome, due ruoli).
**→ dettaglio:** cicatrix-scars.md (resto) + archive (W53/W54/W61)
**PR-1 landing** (corpo in `PENDING-ARMS.md`): mergeability GitHub non onora `merge=union`;
`autoMergeRequest` NULL non prova armata/disarmata — leggi `mergeQueueEntry`; dopo conflitto/espulsione RIARMA (idempotente).

---

## #10 — Active-active split-brain

**MALATTIA:** un singleton gira su host diversi, ognuno credendosi unico → carico duplicato, alert
spettrali.

**SEGNALE-PRECOCE:** `localhost` come hostname fleet-wide; nessuna master-election; alert da una
macchina "che non dovrebbe".

**ANTIDOTO:** SSOT nel DB (`expected_status`/`assigned_node`); graceful-exit se `node≠hostname`;
bootout+disable dell'istanza legacy.

**MEMBRI:** W67c (spam dal Mini) · 2026-05-07 (12+1 mata_garuda) · NLM feeder split-brain.
**→ dettaglio:** archive (mata_garuda/NLM-feeder/W67c)

---

## Orfane (uniche per natura, non forzate in un cluster)

- **W38** — `backend_rag_v2` NOSUPERUSER (hardening, non bug)
- **P3 FLAKY** (CURATA) + **W129** — test e produttore non condividono «adesso»: là un tick non
  congelato, qui un orologio congelato che il codice sotto test non legge.
- **W33** — kill-switch su auto-remediation · **W39** — Dependabot bump (routine)
- **W40** — collisione numerazione migrazioni · **W128** — collisione numero cicatrice (sibling W40,
  antidoto `lint_scar_number_collision.py`)
- **Atlas migrate-lint paywall** — costo terze-parti · **Deploy crash / Dockerfile cell-core** —
  ordering promozione monorepo CI
- **W96** — test non isolati scrivono STATO DI PRODUZIONE (`Path.home()` di default)

**→ dettaglio:** grep il W-number in `cicatrix-scars.md` / `cicatrix-scars-archive.md`.

---

> **Manutenzione:** scar nuova → 1 riga in MEMBRI (3-8 parole + numero), corpo in `cicatrix-scars.md`.
> Più di 1-2 frasi qui È un corpo: sta nel file sbagliato. Non rientra in nessuna delle 10 →
> orfana, o serve un'11ª famiglia. Metodo: skill `modus` Gear 3.
