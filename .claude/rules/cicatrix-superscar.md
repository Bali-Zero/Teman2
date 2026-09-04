# cicatrix-superscar.md — le 10 famiglie (PONTE)

> **PONTE, non enciclopedia.** ~99 cicatrici in 10 famiglie + orfane. Per famiglia: **malattia**,
> **segnale-precoce**, **antidoto**, **membri** (1-3 parole — corpo in `cicatrix-scars.md`/
> `-archive.md`, mai qui). Dettaglio → grep il W-number, o `scar query "<tema>"`/`--list`/
> `--family N`. ⚠️ **Può arrivarti STALE** (M5, checkout indietro apposta) — riferimento: `git show
> origin/main:<path>`.
>
> **Budget ≤8KB**, armato da `scripts/tests/test_superscar_budget.py` (byte + completezza: ogni
> W-number qui ha un corpo reale). Iniettato a OGNI sessione e subagent. Tre nomi disambiguano
> collisioni: `W81-armamento-sospeso`, `W81b-dlq-blind-heal-loop`, `W84-tcc-dead`. Storia:
> `research/operations/2026-08-21-token-ceremony-ci-system-audit.md`.
>
> **Dominanza:** #1 HOME-fork, #2 Esiste≠Armato, #5 Sibling-race, #4 Secret-clear = 65-75%.

---

## #1 — HOME-fork drift (deploy-path desync)

**MALATTIA:** il runtime esegue una copia in `$HOME` divergente dal repo; il fix nel repo non la
raggiunge.

**SEGNALE-PRECOCE:** plist/cron che invoca `~/scripts/`; path con username; "due copie
byte-identical".

**ANTIDOTO:** lint CI `cmp -s` live vs git, contro `origin/main` mai il checkout locale.
**→ ESEGUIBILE:** `scripts/lint_home_fork.py` — sha256 sulle coppie, `--discover`.

**MEMBRI:** W50/W51/W52 (wrapper/plist) · W68/W72/W73 (bridge openclaw) · W70 (path-drift) · W76
(repomap stale) · M5-dev-env (venv) · TAC wa-mirror (fork orfana) · W81-armamento-sospeso
(worktree sparito).

---

## #2 — Esiste ≠ Armato (cron theater / blind autopilot)

**MALATTIA:** demoni/cron "verdi" mascherano worker morti, eccezioni ingoiate, output vuoti.

**SEGNALE-PRECOCE:** `/health` guarda il web non i worker; cron verde a output vuoto.

**ANTIDOTO:** monitora l'esito/heartbeat, non PID né exit-code (green≠working). W81: lo STATO DI
ATTIVAZIONE conta.
**→ ESEGUIBILE:** `scripts/pending_arms_report.py` — allarma `PENDING-ARMS.md` aperte >48h.

**MEMBRI:** W74 (cron-theater) · W69 (checks disarmati) · W64/W34 (asyncpg death) · W71
(mcp_integrity mente) · W32 (pg-bridge muto) · 503-RAG (worker giù) · W70 (log_tail cieco) ·
W81-armamento-sospeso (cron exit 127/78) · W81b-dlq-blind-heal-loop (DLQ mai puliti) ·
W84-tcc-dead (launchd perde TCC) · W84-tccutil-recidiva (`reset All`) · W87 (identity su PROD) ·
W97 (display-cap) · W101 (fail-closed decapitato) · W101-recidiva-fly-backup (Fase 2) · W104
(`redis-cli` NOAUTH) · W108 (19/20 cron muti) · W110 (heartbeat errato) · W116 (cura morta) · W118
(11h fermo) · W120 (sentinella disarmata) · W122 (SIGINT→130) · W123 (`success`≠armato) · W126
(draft in coda).

---

## #3 — Guard-over-match (substring trapping) — gemello UNDER-match (W82)

**MALATTIA:** la guardia decide su substring, non entità/intento. OVER clobbera; UNDER lascia
passare il fatto riformulato.

**SEGNALE-PRECOCE:** `if "keyword" in testo`; escape-clause su UNA frase.

**ANTIDOTO:** nessuna guardia senza test di innocenza E colpevolezza, su entità mai su substring.
**→ ESEGUIBILE:** `infra/guard-conformance/` — senza guilt+innocence = FAIL CI.

**MEMBRI:** W68 (villa zoning) · W72 (B211/KITAS) · W73 (5 insieme) · W77 (asse linguistico) ·
W68b (variante) · W82 (traduzioni) · W83 (3 falsi BLOCK) · W84 (char-class) · W85 (`stash`/`list`)
· W92 (path vs cwd) · W94 (whole-command) · W95 (`async def`) · W99 (self-closing) · W109
(collocazione) · W112 (Prettier) · W115 (post-selezione) · W119 (`\s` newline) · W127
(`levelname`/`levelno`).

---

## #4 — Secret in the clear (world-readable credentials)

**MALATTIA:** segreti prod esposti sul filesystem, bypassando Fly secrets. `.bak` eredita
l'esposizione.

**SEGNALE-PRECOCE:** `cat`/`echo` di file-chiave su ssh; `.bak` senza chmod.

**ANTIDOTO:** `chmod 0600` (live + `.bak*`); mai `cat` di un secret; ruota se world-readable.
**→ ESEGUIBILE:** `scripts/secrets_permissions_audit.py` — `--fix` chmod 0600.

**MEMBRI:** P0 2026-06-03 (`.env` readable) · W65 (`.bak` key) · W75 (fly-ssh leak) · P0 2026-05-21
(pw in 32 file) · 2026-04-29 (plist world-readable).

---

## #5 — Sibling-race / shared-worktree chaos

**MALATTIA:** agenti/cron paralleli sullo stesso checkout → collisioni stash, distruzione
silente.

**SEGNALE-PRECOCE:** `git checkout` nella cartella globale; worktree scaduto reapabile mentre è
vivo.

**ANTIDOTO:** ogni agent in worktree dedicato (`agent_start.py`); reap solo a 2-AND.

**MEMBRI:** W62 (TTL violato) · W63 (nested worktree) · W80 (reap non-mergiati) ·
agent-library-evolver (REPO_ROOT) · W59 (madre) · 2026-04-29 (untracked persi).

---

## #6 — Anti-hallucination blindness (phantom citations)

**MALATTIA:** un LLM immagina file/righe/conclusioni plausibili; chi sta a valle le prende per
vere.

**SEGNALE-PRECOCE:** piano su report LLM senza audit fisico; `file:line` mai ri-eseguito.

**ANTIDOTO:** mai costruire su un path citato senza `find`/`ls`/`cat` in QUESTO turno. Anche il
refuter allucina (W65).

**MEMBRI:** META 2026-06-05 (3 falsi) · W74 (phantom scorer.py) · W65 (refuter falso-refuta) · W78
(cicatrice sbagliata) · W100 (7/8 false-clean) · W90 (ground-truth stantio) · W113 (correzione
mente). Linea: W65→W90→W100→W113.

---

## #7 — Daemon-vs-cron KeepAlive misconfig

**MALATTIA:** `KeepAlive=true` su script one-shot → ogni exit letto come morte → restart storm.

**SEGNALE-PRECOCE:** `KeepAlive=true` + `nohup … &`; contatore `runs` cresce.

**ANTIDOTO:** loop bloccante reale o `StartInterval` senza KeepAlive.
**→ ESEGUIBILE:** `scripts/lint_plist_keepalive.py` — `nohup &`=FAIL.

**MEMBRI:** W67/W67b (wa-mirror storm) · W60 (Fly api flapping) · 2026-04-29 (53 plist, 13%
corretti).

---

## #8 — Network flap / proxy fragility

**MALATTIA:** componenti long-running crashano sui flap di rete (proxy/WG/pg-proxy).

**SEGNALE-PRECOCE:** chiamata singola senza retry; log pieni di `TimeoutError`.

**ANTIDOTO:** socket persistenti keep-alive; retry con backoff; cattura `InterfaceError`.

**MEMBRI:** W49 (98 timeout) · W55 (Telegram one-shot) · W32 (InterfaceError) · W47 (solo
numero).

---

## #9 — State-schema mutation drift

**MALATTIA:** uno step cambia il formato di un payload/file-stato; i lettori a valle si rompono.

**SEGNALE-PRECOCE:** modifica ai dati intermedi (DLQ, redis) senza scope end-to-end.

**ANTIDOTO:** deploy unificato sui contratti condivisi. W88: "già su main" per CONTENUTO, mai per
SHA-ancestor o timestamp.
**→ ESEGUIBILE:** `scripts/branch_graveyard_cleanup.sh::content_on_main()`.

**MEMBRI:** W54 (timestamp) · W53 (DLQ TERMINAL) · W61 (attempts) · W86 (DOCSYNC stale) · W88
(cherry post-squash) · W102 (two-dot) · W106 (proxy congelato) · W106b (checkout proxy) ·
W109b (2 PR bloccate) · W111 (`rerun` stantio) · W114 (fake e codice) · W118 (3 proxy
mentono) · W125 (resa a mano) · W131 (un nome, due ruoli).

---

## #10 — Active-active split-brain

**MALATTIA:** un singleton gira su host diversi, ognuno credendosi unico → carico duplicato.

**SEGNALE-PRECOCE:** `localhost` come hostname fleet-wide; nessuna master-election.

**ANTIDOTO:** SSOT nel DB (`expected_status`/`assigned_node`); graceful-exit se `node≠hostname`.

**MEMBRI:** W67c (spam dal Mini) · 2026-05-07 (mata_garuda) · NLM feeder split-brain.

---

## Orfane (uniche per natura, non forzate in un cluster)

- **W38** NOSUPERUSER (hardening) · **P3 FLAKY**+**W129** «adesso» non condiviso
- **W33** kill-switch auto-remediation · **W39** Dependabot bump (routine)
- **W40**/**W128** collisione numerazione/numero cicatrice (`lint_scar_number_collision.py`)
- Atlas migrate-lint paywall · Deploy crash cell-core (ordering CI)
- **W96** test scrivono STATO PRODUZIONE (`Path.home()`)

**→ dettaglio:** grep il W-number in `cicatrix-scars.md`/`-archive.md`.

---

> **Manutenzione:** scar nuova → 1 riga in MEMBRI, corpo in `cicatrix-scars.md`. Più di 1-2 frasi
> qui È un corpo: sta nel file sbagliato. Non rientra in nessuna delle 10 → orfana, o serve
> un'11ª famiglia. Metodo: skill `modus` Gear 3.
