# cicatrix-superscar.md — le 10 famiglie (PONTE)

> **PONTE, non enciclopedia.** ~99 cicatrici si raggruppano in 10 superscar (famiglie) + orfane.
> Per famiglia: **malattia** (difetto strutturale), **segnale-precoce**, **antidoto strutturale**,
> **membri** (3-8 parole — il corpo vive in `cicatrix-scars.md`/`-archive.md`, mai qui; unica
> eccezione le righe **PR-1 landing**, senza W-number, col corpo in `PENDING-ARMS.md`, che il gate
> di completezza non sa risolvere). Dettaglio → grep il W-number, o `scar query "<tema>"`/`--list`/
> `--family N`. ⚠️ **Anche questo file può esserti arrivato STALE**: dove il main checkout è tenuto
> indietro di proposito (M5, centinaia di commit) la copia iniettata E quella letta da `scar` sono
> entrambe vecchie — il riferimento è `git show origin/main:<path>`.
>
> **Budget ≤14KB**, armato da `scripts/tests/test_superscar_budget.py` (byte + completezza: ogni
> W-number citato qui deve avere un corpo reale). Questo file è iniettato a OGNI sessione e OGNI
> subagent: ciò che aggiungi lo paga tutta la flotta, per sempre. Tre nomi sono disambiguati da
> collisioni di numero — `W81-armamento-sospeso`, `W81b-dlq-blind-heal-loop`, `W84-tcc-dead`.
> Storia e metodo: `research/operations/2026-08-21-token-ceremony-ci-system-audit.md`.
>
> **Dominanza:** #1 HOME-fork, #2 Esiste≠Armato, #5 Sibling-race, #4 Secret-clear coprono 65-75%.

---

## #1 — HOME-fork drift (deploy-path desync)

**MALATTIA:** il runtime esegue una copia in `$HOME` (path hardcodato utente/macchina) che diverge
silenziosamente dal repo. Il fix entra nel repo, la copia viva non lo vede.

**SEGNALE-PRECOCE:** plist/cron che invoca `~/scripts/`, `~/.openclaw/bin/` invece del repo; path con
username specifico; "due copie byte-identical".

**ANTIDOTO:** lint CI `cmp -s` file-eseguito-live vs versione tracciata su git, confrontato contro
`origin/main` mai contro il checkout locale — un checkout indietro accusa la copia viva (W106b, #9).
**→ ESEGUIBILE:** `scripts/lint_home_fork.py` — sha256 su coppie dichiarate (97), `--discover` payload
non dichiarati, exit 1|2|4.

**MEMBRI:** W50/W51/W52 (madre — wrapper/plist/script fork) · W68/W72/W73 (bridge `~/.openclaw/bin/`) ·
W70 (path-drift Air) · W76 (repomap su checkout stale) · M5-dev-env (venv+marketplace path sbagliato) ·
TAC wa-mirror (HOME-fork non promossa) · W81-armamento-sospeso (deploy worktree sparito, 2026-06-15).
**→ dettaglio:** archive (W50/W51/W52/W68/W76/M5-dev-env) + cicatrix-scars.md (W70/W81-armamento-sospeso)

> _Cross-famiglia:_ **W84-tcc-dead** (#2) imparentata — wrapper sotto `~/Desktop` TCC-protetto.

---

## #2 — Esiste ≠ Armato (cron theater / blind autopilot)

**MALATTIA:** demoni/cron "verdi" (exit 0, KeepAlive attivo) mascherano worker morti, eccezioni
ingoiate, output vuoti — falsa illusione di protezione.

**SEGNALE-PRECOCE:** `/health` che controlla il web non i worker; cron "green every Sunday" con output
vuoto; `except` permissivi; log-tail senza diagnostica.

**ANTIDOTO:** monitora l'esito reale/heartbeat DB, non PID/exit-code («green ≠ working — leggi
l'OUTPUT»). W81: anche lo STATO DI ATTIVAZIONE — costruito≠attivato è sospeso, non vivo. W120: la sonda
deve leggere la STESSA chiave che il reporter emette, o l'allarme si azzera muto.
**→ ESEGUIBILE:** `scripts/pending_arms_report.py` — allarma righe `PENDING-ARMS.md` aperte >48h.

**MEMBRI:** W74 (reflexion cron-theater) · W69 (required-checks disarmati) · W64/W34 (asyncpg
silent-death) · W71 (verify_mcp_integrity gira e mente) · W32 (pg-bridge morto silenzioso) · 503-RAG
(health=200, worker stoppato) · W70 (sentinel log_tail cieco) · W81-armamento-sospeso (~20 cron green
storico exit 127/78) · W81b-dlq-blind-heal-loop (14 DLQ corpses mai puliti) · W84-tcc-dead (launchd
perde grant TCC) · W84-tccutil-recidiva (`tccutil reset All` scambiato per read-only) · W87 (Postgres
access-wall, dev identity su proxy PROD) · W97 (display-cap `[:40]` letto come completo) · W98
(dependabot bypassa `!=` anti-malware) · W101 (pre-push fail-closed decapitato da `sh -e`) ·
W101-recidiva-fly-backup (PARTIAL: Fase 2 mai parte) · W104 (`redis-cli` esce 0 con NOAUTH su stdout) ·
W107 (curato 1 wrapper su 5) · W108 (19/20 cron muti, 2 cause) · W110 (heartbeat sull'organo sbagliato)
· W116 (allarme su esito giusto, cura codice morto) · W118 (11h fermo, nessun check rosso) · W120
(sentinella della famiglia stessa disarmata) · W121 (mutation testing su bytecode avvelenato) · W122 (rosso mente: lavoro fatto, SIGINT→130) · W123 (hold disarmato si ri-arma al push)
· W126 (draft non espelle dalla coda)
· W124
(PR DIRTY: check-suite `completed` su un sottoinsieme, non su zero corse).
**→ dettaglio:** cicatrix-scars.md (resto) + archive (W34/W32/W64/W69/W71/W74/503)

---

## #3 — Guard-over-match (substring trapping) — gemello UNDER-match (W82)

**MALATTIA:** guardia decide su substring testuale, non entità/intento. OVER-match = trigger troppo
ampio clobbera risposte corrette. UNDER-match = sorveglia una frase-letterale, il fatto marcio
riformulato/tabulato/altra-lingua sfugge, resta verde.

**SEGNALE-PRECOCE:** `if "keyword" in testo` (non word-boundary); escape-clause su UNA frase esatta;
trigger corti (`lease`/`429`) che matchano dentro token più lunghi; scope che salta una superficie
"per dopo".

**ANTIDOTO:** nessuna guardia senza test di innocenza E colpevolezza, su entità/intento mai bare-substring.
**→ ESEGUIBILE:** `infra/guard-conformance/` — censita senza guilt+innocence = FAIL CI.

**MEMBRI:** W68 (villa-leasehold zoning) · W72 (B211/KITAS deflesso) · W73 (5 over-match in un colpo) ·
W77 (wa-mirror, asse linguistico) · W68b (variante di W68) · W82 (freshness-sentinel cieco alle
traduzioni) · W83 (3 falsi BLOCK ssh/cd/quote) · W84 (`[^q]*` matcha newline, fonde comandi cross-line)
· W85 (`stash` nudo blocca anche `list`/`show`) · W91 (flag in un commento apre l'eccezione) · W92
(path relativo in quote ssh vs cwd sessione) · W94 (esenzione remote-dispatch WHOLE-COMMAND) · W95
(linter reward-hacking blocca una fixture, cieco ad `async def`) · W99 (skeleton self-closing salta
font-inject) · W105 (troncatura primo segmento `.worktrees/`) · W109 (esenzione per collocazione non
contenuto) · W112 (Prettier riscrive i propri record di cicatrice) · W115 (veto post-selezione, non
filtro pre) · W117 (`_strip_noise` svuota payload prima dell'esenzione) · W119 (`\s` separatore
attraversa il newline) · W127 (guardia confronta `levelname` reso, non `levelno` stabile).
**→ dettaglio:** cicatrix-scars.md (resto) + archive (W68/W72)
**PR-1 landing** (corpo in `PENDING-ARMS.md`): `git branch -D` da worktree è repo-wide, la guardia giudica il cwd.

---

## #4 — Secret in the clear (world-readable credentials)

**MALATTIA:** segreti prod (DB password, API key) esposti sul filesystem con permessi larghi,
bypassando Fly secrets. `.bak` eredita l'esposizione.

**SEGNALE-PRECOCE:** `cat`/`echo` di file-chiave su ssh; backup `.bak` senza chmod; secret sullo stesso
stdin che `bash -s` consuma.

**ANTIDOTO:** `chmod 0600` su dotfiles (live + `.bak*`); mai `cat` di un secret in diagnosi; rotazione
se world-readable storicamente.
**→ ESEGUIBILE:** `scripts/secrets_permissions_audit.py` — `--fix` chmod 0600, blind-scan guard exit 2.

**MEMBRI:** P0 2026-06-03 (`apps/cell/.env` readable) · W65 (skills-bridge `.bak` 64-hex key) · W75
(fly-ssh secret leak su pipe) · P0 2026-05-21 (postgres pw in 32 file) · 2026-04-29 (plist
world-readable).
**→ dettaglio:** cicatrix-scars.md (P0-cell.env) + archive (2026-05-21/04-29/W65/W75)

---

## #5 — Sibling-race / shared-worktree chaos

**MALATTIA:** agenti/cron paralleli usano lo stesso checkout o worktree → collisioni stash, distruzione
silente di modifiche altrui, reap mentre ci si lavora.

**SEGNALE-PRECOCE:** processi che fanno `git checkout` nella cartella globale; worktree
pulito-ma-scaduto reap-eligibile mentre vivo; untracked non tuoi.

**ANTIDOTO:** ogni agent in un `git worktree` dedicato (`agent_start.py`); reap solo a 2-AND (nessun
processo vivo AND già su origin/main); leave-dirty verso lavoro sibling.

**MEMBRI:** W62 (6 worktree abbandonati, TTL violato) · W63 (nested worktree) · W80 (reap con commit
non-mergiati) · agent-library-evolver (REPO_ROOT condiviso) · W59 (sibling-race madre) · 2026-04-29
(untracked persi).
**→ dettaglio:** cicatrix-scars.md (W80/W59) + archive (W62/W63/evolver)

---

## #6 — Anti-hallucination blindness (phantom citations)

**MALATTIA:** un LLM "immagina" file/righe/conclusioni plausibili; l'agente a valle le prende per vere
senza verifica.

**SEGNALE-PRECOCE:** piano basato solo su un report LLM senza audit fisico; `file:line` mai
ri-eseguito; refuter che boccia senza ri-grepare.

**ANTIDOTO:** mai costruire su un path citato senza `find`/`ls`/`cat` in QUESTO turno. Anche il refuter
allucina (W65).

**MEMBRI:** META 2026-06-05 (13-agent autopsy, 3 file:line fantasma) · W74 (phantom scorer.py) · W65
(refuter falso-refuta) · W78 (cicatrice-sbagliata-propagata) · W100 (blind agreement, 7 false-clean su
8) · W90 (ground-truth verifier stantio) · W113 (la correzione stessa mente). Linea: W65→W90→W100→W113.
**→ dettaglio:** cicatrix-scars.md (W78/resto) + archive (META-autopsy/W65/W74)

---

## #7 — Daemon-vs-cron KeepAlive misconfig

**MALATTIA:** `KeepAlive=true` su script one-shot → ogni exit letto come morto → restart storm; figli
`nohup` SIGTERM-killati ogni ciclo.

**SEGNALE-PRECOCE:** `KeepAlive=true` + `exec <one-shot>` o `nohup … &`; contatore `runs` che cresce.

**ANTIDOTO:** loop bloccante reale (`while true; do …; sleep N; done`) o `StartInterval` senza
KeepAlive.
**→ ESEGUIBILE:** `scripts/lint_plist_keepalive.py` — `nohup &`=FAIL.

**MEMBRI:** W67/W67b (wa-mirror reconnect storm) · W60 (Fly api flapping) · 2026-04-29 (53
LaunchAgents, 13% corretti).
**→ dettaglio:** archive (W60/04-29/W67/W67b)

---

## #8 — Network flap / proxy fragility

**MALATTIA:** componenti long-running crashano a cascata sui normali brevi flap di rete
(proxy/WireGuard/Postgres-proxy).

**SEGNALE-PRECOCE:** chiamata singola non protetta da retry; log pieni di `TimeoutError`; alerter
single-attempt.

**ANTIDOTO:** socket persistenti keep-alive; retry-loop con backoff; cattura `InterfaceError` oltre
`PostgresError`.

**MEMBRI:** W49 (canva watchdog 98 TimeoutError) · W55 (Telegram single-attempt drop) · W32 (interface
error ignorato) · W47 (solo numero citato, nessun dettaglio).
**→ dettaglio:** archive (W49/W55/W32) + cicatrix-scars.md (W47)

---

## #9 — State-schema mutation drift

**MALATTIA:** uno step cambia formato di un payload JSON/file-stato; lettori a valle non allineati si
rompono.

**SEGNALE-PRECOCE:** modifica ai dati intermedi (DLQ, redis, `*.last.json`) senza scope end-to-end; uno
stato letto da un proxy (SHA/timestamp) invece che dal CONTENUTO.

**ANTIDOTO:** deploy unificato sui contratti condivisi. W88: "già su main/stale" si verifica per
CONTENUTO (diff vuoto/subset), mai patch-equivalenza/SHA-ancestor/timestamp.
**→ ESEGUIBILE:** `scripts/branch_graveyard_cleanup.sh::content_on_main()`.

**MEMBRI:** W54 (timestamp schianta staleness-check) · W53 (DLQ TERMINAL gate mancante) · W61
(autopilot_attempts droppati) · W86 (DOCSYNC stale, boccia PR innocente) · W88 (cherry mente sul
contenuto post-squash) · W102 (two-dot diff accusa PR dei file di main) · W106 (proxy congelato sceglie
credenziale morta) · W106b (il checkout stesso è il proxy) · W109b (2 PR che si bloccano a vicenda) ·
W111 (`gh run rerun` rigioca merge-ref stantio) · W114 (fake e codice condividono l'immaginazione) ·
W118 (3 proxy merge-queue che mentono) · W125 (fusione pulita senza marker, la resa a mano la tiene).
**→ dettaglio:** cicatrix-scars.md (resto) + archive (W53/W54/W61)
**PR-1 landing** (corpo in `PENDING-ARMS.md`): la mergeability GitHub non onora `merge=union`;
`autoMergeRequest` non sopravvive a un transito CONFLICTING — va riarmato via GraphQL.

---

## #10 — Active-active split-brain

**MALATTIA:** componente singleton eseguito in parallelo su host diversi (Pro+Mini), ognuno credendosi
unico → carico duplicato, alert spettrali.

**SEGNALE-PRECOCE:** `localhost` come hostname fleet-wide; nessuna master-election; alert da una
macchina "che non dovrebbe".

**ANTIDOTO:** Single-Source-of-Truth nel DB (`expected_status`/`assigned_node`); graceful-exit se
`node≠hostname`; bootout+disable persistente dell'istanza legacy.

**MEMBRI:** W67c (wa-mirror Telegram spam dal Mini) · 2026-05-07 (12+1 mata_garuda active-active) · NLM
feeder split-brain.
**→ dettaglio:** archive (mata_garuda/NLM-feeder/W67c)

---

## Orfane (uniche per natura, non forzate in un cluster)

- **W38** — `backend_rag_v2` NOSUPERUSER (hardening, non un bug)
- **P3 FLAKY** — clock-race in un test — **CURATA 2026-08-02**: orologio congelato, non un iteratore di
  tick; mutation ha trovato di peggio (test asseriva un CONTEGGIO, verde con la dedup cancellata).
- **W33** — kill-switch operatore su auto-remediation
- **W40** — collisione numerazione migrazioni
- **W128** — collisione numero cicatrice (sibling W40)
- **W129** — test congela orologio non letto dal codice (sib. P3)
- **W39** — Dependabot bump (routine)
- **Atlas migrate-lint paywall** — costo terze-parti, non bug
- **Deploy crash / Dockerfile cell-core** — ordering promozione monorepo CI
- **W96** — test non isolati scrivono STATO DI PRODUZIONE (`Path.home()` default nei worker)

**→ dettaglio:** grep il W-number in `cicatrix-scars.md` / `cicatrix-scars-archive.md`.

---

> **Manutenzione:** scar nuova → 1 riga in MEMBRI (3-8 parole + numero), corpo in `cicatrix-scars.md`.
> Più di 1-2 frasi qui È un corpo: sta nel file sbagliato. Non rientra in nessuna delle 10 →
> orfana, o serve un'11ª famiglia. Metodo: skill `modus` Gear 3.
