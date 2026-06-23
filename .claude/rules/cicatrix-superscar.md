# cicatrix-superscar.md — le 10 famiglie (PONTE)

> **Questo file è un PONTE, non l'enciclopedia.** Le ~86 cicatrici singole dell'organismo
> si raggruppano in **10 superscar** (famiglie/generi) + alcune orfane. Qui c'è, per ogni
> famiglia: la **malattia** (il difetto strutturale che genera tutte le istanze), il
> **segnale-precoce** (cosa vedi PRIMA che morda di nuovo), l'**antidoto strutturale**
> (la regola che ucciderebbe l'intera famiglia), e i **membri**.
>
> **Per il dettaglio di una scar specifica → segui il ponte:** il corpo completo
> (TRAUMA/ANTIBODY/GOTCHA verbatim) vive in `cicatrix-scars.md` (recenti) + `cicatrix-scars-archive.md`
> (storiche). Cercalo con la CLI **`scar query "<tema>"`** (ricerca lessicale zero-dependency su
> entrambi i file-corpo — `scar query --list` per l'indice, `scar query --family N` per saltare a un
> cluster qui), oppure grep per W-number.
>
> **Perché esiste:** il blob piatto delle cicatrici pesava ~28k token a ogni sessione (W77:
> "l'organismo cataloga il trauma ma non lo promuove a struttura"). Questo file È la promozione
> a struttura — ~2k token che coprono di più. Genesi: clustering Gemini 3.5 Flash High su 86 scar +
> gate W65 (W-number tutti verificati su disco) + review one-by-one Antonello, 2026-06-14.
>
> **Dominanza (dato):** 4 famiglie — #1 HOME-fork, #2 Esiste≠Armato, #5 Sibling-race, #4 Secret-clear —
> coprono il **65-75%** delle 86 cicatrici. L'organismo non ha 86 malattie: ne ha ~10, e 4 dominano.

---

## #1 — HOME-fork drift (deploy-path desync)

**MALATTIA:** il runtime esegue una **copia in `$HOME`** (o un path hardcodato di un utente/macchina)
che diverge silenziosamente dal repo "source of truth". Il fix entra nel repo ma la copia viva non lo
vede — o, peggio, lavoro vivo nella copia HOME non torna mai nel repo.

**SEGNALE-PRECOCE:** plist/cron/script che invoca file da `~/scripts/`, `~/.openclaw/bin/`, `~/bin/`
invece che dal repo; path assoluti con username specifico (`/Users/nuzantara/`, Air decommissionato);
"due copie byte-identical" di un file.

**ANTIDOTO:** lint CI che fallisce se un file eseguito-live diverge (`cmp -s`) dalla versione tracciata
su git, o se una config live punta a un path-HOME invece che al repo. Divieto di cold-copy di ambienti
tra macchine.

**MEMBRI:** W50/W51/W52 (madre — wrapper/plist/script fork) · W68/W72/W73 (bridge `~/.openclaw/bin/`) ·
W70 (path-drift `Projects/nuzantara` Air) · W76 (repomap cron su checkout stale) · M5-dev-env (venv+marketplace
copiati con path `/Users/nuzantara/`) · TAC wa-mirror 2026-06-14 (HOME-fork 510+ righe non promosse) ·
W81 (deploy worktree `~/Desktop/nuzantara-deploy` sparito → ~20 cron critici armati a vuoto su host morto, 2026-06-15).
**→ dettaglio:** archive (W50/51/52) + cicatrix-scars.md (W68/W70/W76/M5-dev-env) · `scar query "home-fork"`
> _Nota cross-famiglia:_ **W84** (TCC-dead launchd cron, vedi #2) è imparentata: il wrapper vive sotto `~/Desktop` (path-HOME TCC-protetto) ed è quella collocazione a renderlo decertificabile. Antidoto HOME-fork applicabile: rilocare i wrapper fuori da `~/Desktop` (come fanno i 2 cron sani).

---

## #2 — Esiste ≠ Armato (cron theater / blind autopilot)

**MALATTIA:** demoni/cron/processi risultano "verdi" (exit 0, `KeepAlive` attivo) ma mascherano worker
morti, loop infiniti, eccezioni ingoiate, output vuoti — falsa illusione di protezione.

**SEGNALE-PRECOCE:** log intasati di noise stderr che annega i veri avvisi; `except` troppo permissivi;
`/health` che controlla il web ma non i worker sottostanti; un cron "green every Sunday" con la dir di
output vuota; `log_tail="exit 1 after 3 attempts"` (false friend, zero diagnostica).

**ANTIDOTO:** monitora l'**esito reale / heartbeat end-to-end nel DB**, non il PID/exit-code. RUN il
guardiano e leggi il suo verdetto prima di fidarti del verde. Falla visibile + allarme proattivo se non
ci sono prove-di-vita. _(Regola madre: «green ≠ working — leggi l'OUTPUT, non l'exit code».)_
**W81 estende:** leggi anche lo **STATO DI ATTIVAZIONE** — costruito≠attivato. Un artefatto/cron/PR/fix che
esiste ma non è merged/installed/propagated/armed/committed è **sospeso, non vivo**. Antidoto della famiglia
"Armamento Sospeso": un _reconciliation-report_ (segnalatore, non auto-attuatore) che allarma su
"costruito-ma-non-attivato >48h", distinguendo il firebreak legittimo (publish/Legge-5/business) dal debito tecnico.

**MEMBRI:** W74 (reflexion cron-theater F21 + evoskill 0-pressure F18) · W69 (decadimento entropico
inosservabile / required-checks disarmati) · W64/W34 (asyncpg silent-death, manca `InterfaceError`) ·
W71 (verify_mcp_integrity glyph-bug: gira e mente) · W32 (pg-bridge morto silenzioso) · 503-RAG
(health=200 ma RAG worker stoppato) · W70 (sentinel log_tail cieco) · W81 (Armamento Sospeso: ~20 cron
"green storico" che `launchctl` dà a exit 127/78 — il verde memorizzato mente, costruito≠attivato) · W81b (DLQ blind heal-loop, 2026-06-15: 28 entry DLQ, 14 "corpses" con state=ok mai puliti — il TERMINAL-guard di process_entry li skippa per sempre e il W70-resurrect copre solo job in job_registry.json, che ne contiene 3; antidoto: **corpse-sweep incondizionato** in dlq_autopilot.py che ad ogni tick drena ogni entry il cui state-file dice ok) · W84 (green-but-TCC-dead launchd cron, 2026-06-16: 2 LaunchAgent M5 sotto `~/Desktop` — incl. `verify-connectome` il guardiano-dei-guardiani — con `LastExitStatus=0` VERDE mentre il log dice `Operation not permitted`; il contesto **launchd ha perso il grant TCC/Full-Disk-Access** verso `~/Desktop` SENZA cambiare codice/plist/permessi — **vettore nuovo: lo stato-di-attivazione TCC è un principal separato da iTerm**; prova che il verde mente: STESSO plist su Pro dà exit 1 onesto. Antidoto: `launchd_liveness_detector.py` PR #1518 incrocia exit-code col CONTENUTO del log; cura=solo-operatore. La W81-estensione si estende ancora: leggi anche lo stato-di-attivazione **TCC**, non solo merge/install).
**→ dettaglio:** cicatrix-scars.md (W64/W69/W70/W71/W74/503/W84) + archive (W34/W32) · `scar query "esiste non armato"`

---

## #3 — Guard-over-match (substring trapping) — **E il gemello UNDER-match (W82)**

**MALATTIA:** una guardia decide su **substring testuale**, non su entità/intento. Due segni opposti, stessa
radice: **OVER-match** = layer anti-allucinazione (`_guard_*`) con trigger a sotto-stringa che clobberano
risposte CORRETTE (match troppo ampio / escape-clause irraggiungibile). **UNDER-match (W82)** = guardia che
sorveglia una frase-letterale e lascia passare il FATTO marcio se riformulato, in tabella, o in altra lingua →
resta VERDE mentre il sito mente. Falso-positivo (over) e falso-negativo (under) sono lo stesso bug a segno
invertito: il match è sulla forma, non sul fatto.

**SEGNALE-PRECOCE:** guardia definita con `if "keyword" in testo:` o `.includes(needle)` (substring, non
word-boundary né entità); escape-clause che tiene/scusa solo su UNA frase esatta (gating irraggiungibile o
lista-di-frasi fragile); trigger corti (`lease`/`ota`/`rent`/`tax`) che matchano dentro parole più lunghe;
**[under]** un guardiano di freschezza/integrità che cerca `stale_pattern` literal e si dichiara verde mentre
lo stesso codice/norma è marcio altrove; scope che salta strutturalmente una superficie ("translations audited
separately" = audited mai).

**ANTIDOTO:** nessuna guardia mergiata senza un test di **innocenza** (NON scatta su un caso legittimo
limitrofo) **E** di colpevolezza. Match su **entità/intento**, mai bare-substring: word-boundary
(`_contains_any_word`) o intento compositivo [over]; **fact-key strutturato** (codice KBLI / sigla visto /
numero-norma, language-invariant) con anchor tolleranti a contesto-tabella [under]. Escape negative-gating
(default passthrough). Nessuna superficie esclusa "per dopo" senza un secondo guardiano che la copra.

**MEMBRI:** W68 (villa-leasehold zoning) · W72 (B211/KITAS deflesso) · W73 (5 over-match in un colpo +
asse linguistico) · W77 (wa-mirror, stessa classe) · W68b (`_guard_property_zoning` "lease") ·
**W82 (UNDER-match — content-freshness-sentinel: substring + cieco alle traduzioni → fatto stale resta verde)** ·
**W83 (OVER-match su guard di COMANDO — worktree-isolation hook: `ssh host git pull` / `cd <wt> && git` / git-verb-in-quote falsi-block; fix = `_strip_noise` pre-scan + dispatcher segment-anchored)** ·
**W84 (OVER-match — lo `_strip_noise` di W83 usava `[^q]*` che matcha i newline → quota orfana cross-line (apostrofo IT / `ssh '...'`) fonde i comandi → phantom write-target; fix = char-class senza `\n` + classifier scarta `\`/`|`. Un fix che partorisce il bug gemello)** ·
**W85 (OVER-match — `BLOCKED_SUBCMD_RE` ha `stash` nudo → `git stash list`/`show` read-only bloccati come `stash push`/`pop`; fix = enumerare i mutanti `stash (push|pop|apply|drop|...)` o allow-list `stash (list|show)`. TERZO over-match consecutivo della STESSA guardia in 2 giorni — la #3 sul worktree-isolation non si chiude con un fix puntuale)**.
**→ dettaglio:** cicatrix-scars.md (W68/W72/W73/**W82**/**W83**/**W84**/**W85**) · `scar query "guard over-match"`

---

## #4 — Secret in the clear (world-readable credentials)

**MALATTIA:** segreti di produzione (DB password, API key) esposti sul filesystem con permessi larghi,
bypassando il secret-manager della piattaforma (Fly secrets). Anche i `.bak` ereditano l'esposizione.

**SEGNALE-PRECOCE:** `cat`/`echo` di file con chiavi su ssh (finisce nel transcript); backup `.bak`
creati senza chmod restrittivo; `.env`/`.plist` con umask di default (0644/0444); un secret sullo
stesso stdin che `bash -s` consuma come script (W75).

**ANTIDOTO:** enforcing `chmod 0600` su tutta la famiglia di dotfiles (live + `.bak*`); MAI `cat` di un
file-secret in diagnosi (leggi via codice/log/DB); minimizza la persistenza del secret sul FS locale;
rotazione se un valore è stato world-readable storicamente.

**MEMBRI:** P0 2026-06-03 (`apps/cell/.env` readable by `cat`) · W65 (skills-bridge `.bak` 64-hex key) ·
W75 (nuz_db_refresh fly-ssh secret leak su pipe) · P0 2026-05-21 (postgres pw in 32 file) ·
2026-04-29 (plist world-readable).
**→ dettaglio:** cicatrix-scars.md (P0-cell.env/W65/W75) + archive (2026-05-21/04-29) · `scar query "secret cleartext"`

---

## #5 — Sibling-race / shared-worktree chaos

**MALATTIA:** agenti/cron paralleli usano lo stesso checkout (`~/Desktop/nuzantara`) o worktree
contemporaneamente → collisioni su stash, drift del branch attivo, distruzione silente di modifiche
altrui in volo, o reap di un worktree mentre ci si lavora.

**SEGNALE-PRECOCE:** più processi che fanno `git checkout` o lavorano nella cartella globale invece di
preallocarsi un ambiente isolato; un worktree pulito-ma-scaduto (reap-eligibile mentre vivo); file
untracked che non sono tuoi (drift di sessione parallela).

**ANTIDOTO:** ogni agent run in un `git worktree` dedicato (`scripts/agent_start.py`), distrutto a fine
run; reap solo a 2-AND (nessun processo vivo nel worktree AND branch già in origin/main); **leave-dirty
intenzionale** verso il lavoro sibling (non committare/stashare/scartare roba altrui).

**MEMBRI:** W62 (6 ops worktree abbandonati, TTL violato) · W63 (nested worktree) · W80 (reap di worktree
pulito con commit non-mergiati) · agent-library-evolver (REPO_ROOT condiviso con wr2-deploy-puller) ·
W59 (sibling-race madre) · 2026-04-29 (untracked persi mid-session).
**→ dettaglio:** cicatrix-scars.md (W62/W80) + archive (W59/W63/evolver) · `scar query "sibling worktree"`

---

## #6 — Anti-hallucination blindness (phantom citations)

**MALATTIA:** in catene multi-agente un LLM "immagina" file/righe/conclusioni plausibili; l'agente o tool
successivo le prende per vere senza verifica, e costruisce contro un fantasma.

**SEGNALE-PRECOCE:** piano dettagliato basato solo su un `report.md` o uno "state schema" prodotto da un
altro LLM, senza un audit fisico preliminare; un `file:line` citato da un report mai ri-eseguito in
questo turno; un refuter/verifier che "boccia" senza che tu abbia ri-grepato.

**ANTIDOTO:** la Regola d'Oro — mai costruire su un file/path citato da un log o report senza aver fatto
`find`/`ls`/`cat` per validarlo fisicamente **in questo turno**. Anche il refuter allucina (W65): l'ultimo
grep del padre non si delega mai.

**MEMBRI:** ℹ️ META 2026-06-05 (13-agent WR2 autopsy, 3 file:line fantasma) · W74 (phantom
`vendor/evoskill/cli/scorer.py`) · W65 (refuter falso-refuta una security finding) · W78 (cicatrice-sbagliata-propagata).
**→ dettaglio:** cicatrix-scars.md (META-autopsy/W65/W74/W78) · `scar query "phantom citation"` · `lessons_hallucinating_tool_output_is_diabolical`

---

## #7 — Daemon-vs-cron KeepAlive misconfig

**MALATTIA:** launchd configurato `KeepAlive=true` su uno script di natura one-shot/transiente → ogni
exit è letto come "morto" → restart storm; i figli `nohup` nel process-group vengono SIGTERM-killati ad
ogni ciclo.

**SEGNALE-PRECOCE:** `KeepAlive=true` + payload `exec <one-shot>` o `nohup … &` dentro un LaunchAgent;
contatore `runs` che CRESCE su una finestra; un figlio sano killato da SIGTERM-dall'esterno (non crash).

**ANTIDOTO:** sostituire lo pseudo-demone con un **loop bloccante reale** nel wrapper (`while true; do …;
sleep N; done`) così launchd non cicla mai; oppure, se è davvero un cron, `StartInterval` + niente
KeepAlive. Grep `exec ` in tutto ciò che gira `KeepAlive=true`.

**MEMBRI:** W67/W67b (wa-mirror reconnect storm ~22s + retry-stop/keepalive) · W60 (Fly api machine
flapping) · 2026-04-29 (53 LaunchAgents, solo 13% KeepAlive corretti).
**→ dettaglio:** cicatrix-scars.md (W67/W67b) + archive (W60/04-29) · `scar query "keepalive daemon cron"`

---

## #8 — Network flap / proxy fragility

**MALATTIA:** componenti long-running o connessioni ad-hoc crashano a cascata e perdono transazioni
quando l'infra di rete esterna (proxy, WireGuard, Postgres-proxy) vive i normali brevi flap.

**SEGNALE-PRECOCE:** chiamata diretta singola a un network service (DB/API) non protetta da retry/reload;
log pieni di `TimeoutError`/`gaierror`; un alerter single-attempt che droppa sul primo fail.

**ANTIDOTO:** socket persistenti con keep-alive (`SELECT 1`); azioni puntuali avvolte in retry-loop con
backoff; cattura completa delle eccezioni di connessione (`asyncpg.InterfaceError` oltre a `PostgresError`).

**MEMBRI:** W49 (`wr2_canva_lease_watchdog` 98 TimeoutError lifetime) · W55 (Telegram alerter single-attempt
drop) · W32 (interface error ignorato silenzioso) · W47.
**→ dettaglio:** archive (W47/W49/W55/W32) · `scar query "network flap proxy retry"`

---

## #9 — State-schema mutation drift

**MALATTIA:** uno step isolato cambia una proprietà o il formato di un payload JSON / file-di-stato; i
lettori non allineati a valle si rompono.

**SEGNALE-PRECOCE:** modifica "veloce" ai dati intermedi passati su code-path disaccoppiati (DLQ, redis
stream, event bus, `*.last.json`) senza scope end-to-end di chi li legge.

**ANTIDOTO:** i cambi di schema sui contratti inter-servizio (incluso file di stato) richiedono deploy
unificato + scansione completa dei partecipanti; mai cambiare un formato condiviso da un solo lato.

**MEMBRI:** W54 (timestamp ISO-8601 schianta il check di staleness) · W53 (DLQ TERMINAL suppression gate
mancante al ricevente) · W61 (autopilot_attempts droppati da `add_to_dlq`) · **W86 (DOCSYNC stale —
auto-merge-a-verde mergia il commit-feature PRIMA che il commit docs_sync bump atterri → il
contratto-derivato `AI_ONBOARDING.md` test/router/service count resta stale su main → il gate
`check-docs-sync` boccia la PR backend successiva, innocente. Antidoto: il `docs_sync.py` regen va
nello STESSO commit della feature, MAI separato — con `--auto` non esiste "poi", merge al primo
verde. 2026-06-23, PR #1670→#1672)**.
**→ dettaglio:** cicatrix-scars.md (W86) + archive (W53/W54/W61) · `scar query "schema drift json contract"`

---

## #10 — Active-active split-brain

**MALATTIA:** un componente architettato come **singleton** finisce eseguito in parallelo su host diversi
(Pro + Mini), ognuno credendosi unico → carico duplicato, dati corrotti, alert spettrali.

**SEGNALE-PRECOCE:** `localhost` come hostname in un servizio fleet-wide; nessuna master-election;
notifiche/alert che arrivano da una macchina che "non dovrebbe" inviarli; un `runs`/`attempt` che sale su
un nodo che credevi spento.

**ANTIDOTO:** Single-Source-of-Truth nel DB o un campo dichiarativo (`expected_status`/`assigned_node`)
che il servizio legge su QUALSIASI macchina e fa graceful-exit se `node≠hostname`; bootout+disable
persistente dell'istanza legacy.

**MEMBRI:** W67c (wa-mirror Telegram spam dal Mini, non dal Pro) · 2026-05-07 (12+1 mata_garuda
LaunchAgents active-active) · NLM feeder split-brain (redis locale vs host parametrizzato).
**→ dettaglio:** cicatrix-scars.md (W67c) + archive (mata_garuda/NLM-feeder) · `scar query "active-active split-brain"`

---

## Orfane (NON forzate in un cluster — uniche per natura)

Queste non sono famiglie ricorrenti; restano scar singole consultabili nel file dettaglio:

- **W38** — `backend_rag_v2` NOSUPERUSER (hardening strutturale, non un bug)
- **P3 FLAKY** — `test_duplicate_alert_id_skipped` (clock-race puro in un test)
- **W33** — kill-switch operatore su auto-remediation
- **W40 / SQL v2 migrations** — collisione da numerazione manuale migrazioni
- **W39** — Dependabot bump (manutenzione di routine)
- **Atlas migrate-lint paywall** — costo terze-parti, non bug
- **Deploy crash / Dockerfile cell-core missing** — ordering di promozione nel monorepo CI

**→ dettaglio:** grep il W-number in `cicatrix-scars.md` / `cicatrix-scars-archive.md`.

---

> **Manutenzione:** quando nasce una scar nuova, aggiungila al suo cluster qui (1 riga in MEMBRI +
> aggiorna l'antidoto se la scar lo rafforza); il corpo completo va in `cicatrix-scars.md` come oggi.
> Se una scar non rientra in nessuna delle 10 → è una candidata-orfana, OPPURE il segnale che serve una
> **11ª superscar** (rivedi il clustering). Genesi e metodo: `research/operations/` + skill `opus-mythos`.
