# HANDOFF — il blocco osservabilità/HOME-fork rimasto aperto (scritto 2026-08-06, M5)

> **Come usarlo:** incolla la sezione «PROMPT» qui sotto in una sessione nuova. Tutto il resto è
> il dossier che quel prompt presuppone. **Ogni numero in questo file è una MISURA del 2026-08-06
> e scade**: la prima cosa che il workflow fa è ri-misurarli, non fidarsi.

---

## PROMPT (da incollare)

Leggi `docs/operations/handoff-observability-block-2026-08-06.md`. Contiene sei reperti misurati il
2026-08-06 e mai curati. Affrontali **in blocco** con un Workflow, non in sequenza a mano.

Vincoli non negoziabili, tutti pagati con sangue nella sessione che ha scritto questo file:

1. **Ri-misura ogni numero prima di usarlo.** I numeri qui sono di ieri. Un piano costruito su una
   cifra ricordata è un fantasma (famiglia #6). Vale anche per `origin/main`: fai `git fetch` e
   leggi il ref FRESCO — un ref locale indietro di un commit mi ha quasi fatto scrivere «il merge
   ha perso le mie righe».
2. **Cerca l'ENTITÀ, non la forma.** Nella sessione precedente sei sonde su sei hanno riportato
   assenza dove c'era presenza: `diff --changed-group-format` non esiste su BSD (ho contato le
   righe di _usage_ come dati), una regex a spazio singolo non vedeva una tabella incolonnata, un
   grep con apici singoli non vedeva la riga che Prettier aveva riscritto con apici doppi, una
   normalizzazione toglieva backslash ma non virgolette, un `ssh` dentro `while read` si mangiava
   lo stdin (serve `-n`), e un `grep -c` su un basename catturava anche un nome più lungo.
3. **Due misure che non concordano sono il reperto, non un dettaglio.** Vedi §3: prima di curare
   le traduzioni devi capire perché organo e conteggio indipendente danno tagli diversi.
4. **generator ≠ grader.** Chi produce un verdetto non lo valida. Usa
   `infra/workflows/verify-template.js` come modello del refuter su contesto fresco.
5. **Una prescrizione può essere più vecchia della decisione che la contraddice** (§6). Prima di
   eseguire il «fix:» stampato da una sonda, chiedi se qualcuno l'ha superata.
6. **Non dichiarare come coppia due copie che divergono di proposito.** Vedi §7: il marcatore
   `CANON` dentro il file dice che le copie HOME sono superate; dichiararle fabbricherebbe deriva
   permanente — la caccia al falso-drift contro cui il registro stesso mette in guardia.

Ship-lifecycle come sempre: la sessione fa review → merge → arm → deploy → PROVE-LIVE. Arma
`gh pr merge --auto --squash` all'apertura. PROVE-LIVE su OGNI superficie consumatrice, mai
sull'exit code.

### Forma del workflow suggerita

Tre fasi, con una barriera sola dove serve davvero.

**Fase 1 — GROUND (fan-out, letture indipendenti, nessuna scrittura).** Un agent per reperto, sei
in parallelo. Ognuno ha UN compito: ri-misurare il proprio reperto sul mondo di oggi e tornare uno
schema `{finding_id, still_real: bool, numbers: {...}, blast_radius, by_design: bool, evidence:
[comando → output]}`. Nessuno propone cure in questa fase. La `by_design` è la domanda più
importante: due dei sei probabilmente NON vanno curati (§6).

**BARRIERA qui, ed è giustificata**: §3 e §4 riguardano lo stesso organo, e §1/§2/§7 sono tutte
famiglia #1 — la mappa completa cambia quali cure sono indipendenti. Senza la barriera rischi due
PR che toccano `declared-pairs.json` dalla stessa base e si bloccano a vicenda (W109b: un registro
monotono accoppia diff disgiunti anche senza file in comune).

**Fase 2 — CURE (pipeline, un item per corsia, worktree isolati).** Solo i `still_real &&
!by_design`. Ogni corsia: worktree via `scripts/agent_start.py` → cura → corpus di colpevolezza
**e** innocenza → PR con auto-merge armato. `isolation: "worktree"` è obbligatorio qui: più corsie
scrivono file in parallelo.

**Fase 3 — VERIFY (per-item, appena la sua cura è pronta — NON aspettare le altre).** Un refuter
di famiglia diversa con l'ordine di **refutare**, puntato sulla frase che la cura ha SCRITTO, non
su quella che ha tolto (W113: la correzione mente e la si guarda meno di tutto il resto). Verdetto
a maggioranza su ≥2 lenti quando l'item tocca dati client-facing.

Poi un **critico di completezza** finale: «quale superficie non ho eseguito, quale claim non ho
verificato, quale lista ho letto troncata?».

### Cosa NON fare

- Non «allineare» il main checkout di M5 (§6). È indietro per progetto, ci sono worktree vivi.
- Non riavviare `translate.hourly` (§4). L'organo funziona; è il battito a mentire.
- Non toccare i permessi già stretti (49 file su tre macchine) senza ri-misurarli.
- Non dichiarare le sei spec `wr2-*` in `declared-pairs.json` (§7).

---

## IL DOSSIER

### §1 — `auth-sentinel.daily` esegue una copia HOME DIVERGENTE dal canon `[famiglia #1]`

`scripts/launchagent_reconcile.py` su M5, 2026-08-06:

```
## HOME-fork target (superscar #1) (2)
- com.balizero.auth-sentinel.daily → /Users/balizero/.nuzantara-cron/auth_sentinel_cron.sh
  (DIVERGED from canon scripts/auth_sentinel_cron.sh)
```

Un job **quotidiano** che sorveglia l'autenticazione gira su codice forkato. Non misurato: da che
parte sta la deriva. **Regola W106b**: attribuisci il lato interrogando `origin/main`, non il
checkout locale — che qui è indietro di 98 commit e accuserebbe la copia viva di una divergenza
causata da lui. Solo `live ≠ origin/main` è un HOME-fork; `live == origin/main` è checkout-stale,
altro proprietario.

### §2 — `nuzantara-repo-sync` non ha canon nel repo, per niente `[famiglia #1]`

```
- com.balizero.nuzantara-repo-sync → /Users/balizero/.local/bin/nuzantara-repo-sync
  (no repo canon (basename not found under scripts/, infra/, or apps/*/scripts/))
```

Peggiore di una divergenza: non c'è niente con cui confrontarlo, e governa la **sincronizzazione
del repo**. Sta su una sola macchina e non è ricostruibile dal repo. Decisione da prendere:
promuovere a canon — e allora vuole la sua prima review, come è successo il 2026-08-06 con
`api_server.py`, che alla prima occhiata di CodeQL portò 7 alert high e una password di produzione
in chiaro — oppure mettere a verbale che resta HOME-only, col contratto scritto dove la flotta può
leggerlo.

### §3 — la guardia di freschezza delle traduzioni copre 2 lingue su 4, e due misure litigano

Misurato su `origin/main`, 2026-08-06:

|                                                    |                       |
| -------------------------------------------------- | --------------------- |
| `.mdx` totali in `apps/mouth/src/content/articles` | **3356**              |
| sorgenti (senza suffisso lingua)                   | 796                   |
| `id` / `it` / `fr` / `ru`                          | 797 / 796 / 485 / 482 |
| con `source_sha256` (mia lettura)                  | **573**               |
| senza (mia lettura)                                | **2783**              |

Il plist `com.balizero.translate.hourly` esegue
`/Users/nuzantara/nuzantara/.venv/bin/python .../scripts/translate-articles.py` **senza `--lang`**.
Il default è `both`, e `translate-articles.py:457` dà `targets = ["id", "it"]`; `all` sarebbe
`["id","it","ru","fr"]` (`:459`). Quindi **`fr` e `ru` — 967 file — sono fuori dal loop orario per
costruzione**. È coerente con la decisione di ritirare fr/ru dal selettore
(`decision_fr_ru_withdrawn_from_the_picker_but_still_served_2026_07_29`): quelle pagine sono
ancora **servite**, quindi «fuori dal loop» significa che invecchiano senza che nessuno lo veda —
è questo il punto da decidere, non un bug da chiudere in automatico.

**E qui la trappola.** Il log dell'organo del 2026-08-06 19:30:

```
DONE in 1s: 0 new, 0 re-translated (stale source), 847 already fresh, 745 unstamped, 0 skipped, 0 FAILED
745 translation(s) carry no source_sha256 and are therefore invisible to freshness checking.
```

`847 + 745 = 1592`, sulle 1593 di `id`+`it`: internamente coerente. Ma il mio conteggio
indipendente di `source_sha256` sulle stesse due lingue dà **426 timbrate / 1167 no** — anche
questo somma a 1593. **Due misure della stessa proprietà, tagli diversi.** Ipotesi non verificate:
«already fresh» dell'organo non significa «timbrato»; oppure la mia sonda leggeva solo i primi
2000 byte e alcune frontmatter sono più lunghe. **Riconciliare questo è il PRIMO lavoro** —
partire dal numero sbagliato butta il lavoro E lo fa sopravvivere nel report finale.

### §4 — il battito di `pro.translate_hourly` mente, l'organo sta bene `[famiglia #2, rovesciata]`

`proprioception` lo dà P1, `heartbeat frozen 16.3d (threshold 7d)` — ed era 14,6 giorni all'inizio
della sessione precedente: **cresce**. Ma l'organo è vivo: `launchctl list` dà
`- 0 com.balizero.translate.hourly`, e `~/logs/translate-hourly.log` è stato scritto **oggi alle
19:30** con `0 FAILED`. Parte ogni ora al minuto 30 (`StartCalendarInterval {Minute: 30}`).

Non è «verde ma morto»: è **stantio e vivo**, il rovescio della #2. Il difetto è nel sidecar del
battito, non nell'organo — parente di W110, dove un organo pubblicava il battito dell'organo
sbagliato. **Non riavviare niente**: la riga di cura della sonda lo dice esplicitamente
(«restart is NOT the cure»). Da trovare: chi dovrebbe scrivere quel battito e perché ha smesso
intorno al 20 luglio.

Nota storica utile: `translate-hourly.error.log` si ferma al 2026-07-08 con un
`FileNotFoundError: /Users/nuzantara/Desktop/nuzantara/...` — path morto dal 16 luglio, quindi
quell'errore è **anteriore** al trasloco e non è la causa. Non inseguirlo.

### §5 — `docs_sync` stantio su DUE file, e la sonda ne nomina uno

```
DOCSYNC STALE — run: python scripts/docs_sync.py
  README.md: 85d7e38416c6 → 994993795a72
  docs/AI_ONBOARDING.md: 38e62b1fcd36 → 24df2f705603
```

`proprioception` riporta solo `docs/AI_ONBOARDING.md`: **la sonda sotto-riporta**, e chi legge il
suo P3 crede sia un file solo. Cura meccanica (rigenerare), ma **W86**: il regen va nello STESSO
commit della feature, mai separato — con auto-merge non esiste «poi».

Nella stessa passata: `com.nuzantara.worktree-gc-universal.daily.plist` è `Repo-divergent`.

### §6 — due sonde prescrivono cure superate `[decisione, non difetto]`

- `git_alignment` P1: «main checkout: 98 behind origin/main, 19 dirty entries», fix: _«interactive
  pull on this machine's main»_. Ma la decisione in vigore è l'opposto: su M5 il main resta
  indietro **per progetto**, perché tirarlo corre contro i worktree vivi. La prescrizione è più
  vecchia della decisione. **Il lavoro è sulla PRESCRIZIONE, non sullo stato** — una sonda che
  consiglia una cosa vietata addestra chi legge a ignorarla, e la prossima volta ignorerà quella
  giusta.
- `arsenal_seats_vcr_m5`: `claude FRESHNESS_EXPIRED` su M5, ma il primary di `arsenal_probe` è
  **Mini** — la staleness su M5 è by-design
  (`ops_vcr_pilot_shipped_and_m5_is_not_the_arsenal_probe_primary_2026_08_04`).

### §7 — code aperte dal ledger (contesto, non lavoro nuovo)

Le righe lasciate in `.claude/skills/modus/PENDING-ARMS.md` il 2026-08-06:

- **Le sei spec `wr2-*` in `~/.claude/agents/`**: la domanda NON è dichiararle. Il file del repo
  porta a riga 12 `> CANON: repo .claude/agents/ (vendored 2026-07-16, shadows ~/.claude/agents
copy — do not edit the HOME copy).` Sono resti superati di proposito: contenuto identico modulo
  Prettier e la riscrittura deliberata `~/.claude/agents/…` → `.claude/agents/…`. Dichiararle
  fabbricherebbe deriva permanente. La domanda vera è **ritirarle (attico, come ha fatto Pro) o
  metterle a verbale come inerti**.
- La riga `regulatory-watcher` dichiara `machines: ["pro","m5"]` con una nota che dice che Mini non
  deve avere il file. **Mini ce l'ha**, allineato a `origin/main`. Benigno oggi; se driftasse,
  nessun lint lo coprirebbe.
- `~/.openclaw/bin/wr2/wr2-cron-wrapper.sh` è sha-identico al gemello nel repo e non dichiarato.
  `.openclaw/bin/` è letteralmente il segnale-precoce della famiglia #1.

E la metà strutturale della credenziale: **126 file sulla flotta** portano il DSN Postgres in
chiaro (Pro 37, M5 17, Mini 72). I permessi sono stretti (49 erano leggibili da gruppo o altri,
ora zero), la **rilevazione** no: `secrets_permissions_audit.py` cerca per NOME e non apre mai i
contenuti — scelta deliberata e documentata, quindi «audit pulito» non va letto come «nessun
segreto su disco».

---

## Ordine consigliato

**Prima** la riconciliazione di §3 (blocca tutto il resto di §3) e §1 (job quotidiano su codice
forkato). **Poi** §2 e §4 in parallelo, indipendenti. **Poi** §5, meccanico. **Infine** §6 e §7,
che sono decisioni da mettere a verbale, non diff.

Uno solo di questi è client-facing: §3, perché `fr`/`ru` sono ancora **servite**. Lì il gate
adversariale va alzato, e la decisione «cosa facciamo delle 967» è Legge 5 — si porta a Zero
misurata, non si sceglie in autonomia.
