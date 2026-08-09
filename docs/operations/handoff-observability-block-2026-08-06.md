# HANDOFF — il blocco osservabilità/HOME-fork rimasto aperto (scritto 2026-08-06, M5)

> ## ✅ ESAURITO 2026-08-08 — NON ri-eseguire il PROMPT
>
> Sette reperti su otto sono chiusi; l'unico aperto è **§3**, ed è una decisione di business
> (Legge 5), non lavoro tecnico. **Il PROMPT qui sotto è archeologia**: chi lo incolla in una
> sessione nuova rifà lavoro già fatto. La tabella per-sezione, con la misura ri-eseguita e
> chi ha chiuso cosa, è in fondo → [§ CHIUSURA](#chiusura--2026-08-08).

> **Come usarlo:** incolla la sezione «PROMPT» qui sotto in una sessione nuova. Tutto il resto è
> il dossier che quel prompt presuppone. **Ogni numero in questo file è una MISURA del 2026-08-06
> e scade**: la prima cosa che il workflow fa è ri-misurarli, non fidarsi.

---

## PROMPT (da incollare)

Leggi `docs/operations/handoff-observability-block-2026-08-06.md`. Contiene sette reperti misurati il
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

**Fase 1 — GROUND (fan-out, letture indipendenti, nessuna scrittura).** Un agent per reperto, sette
in parallelo. Ognuno ha UN compito: ri-misurare il proprio reperto sul mondo di oggi e tornare uno
schema `{finding_id, still_real: bool, numbers: {...}, blast_radius, by_design: bool, evidence:
[comando → output]}`. Nessuno propone cure in questa fase. La `by_design` è la domanda più
importante: due dei sette probabilmente NON vanno curati (§6).

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
indipendente di `source_sha256` sulle stesse due lingue dava **426 timbrate / 1167 no** —
**RETRACTED 2026-08-07** (sbagliato di quasi un fattore 2; non cancellato, resta annotato
perché chi legge dopo lo trovi già smentito invece di ri-derivarlo da capo — W113).

**Ri-misurato oggi, lettura FULL-FILE con le stesse `split_frontmatter`/`read_stamp` di
`scripts/translate-articles.py` (non reinventate): 847 timbrate / 746 non-timbrate sui 1593
file `id`+`it` su disco.** Coincide con l'847 «already fresh» del log dell'organo qui sopra —
il log riporta 0 stale, quindi ogni file timbrato è ANCHE fresco, e le due misure indipendenti
(mia, oggi; dell'organo, ieri 19:30) collimano esattamente. `746 = 745 + 1`: il file in più è
un **orfano invisibile al loop** — `immigration/driving-license-bali-foreigners-2026.id.mdx`
esiste sul disco ma la sua sorgente inglese (`driving-license-bali-foreigners-2026.mdx`) è
sparita, quindi `discover_articles()` non lo scopre mai e non entra né negli 847 né nei 745
(PR #3736, aperta in parallelo sullo stesso reperto, lo rende visibile a livello di codice).

Le due ipotesi lasciate aperte:

- **«already fresh ≠ timbrato» — REFUTATA dal codice.** `freshness_verdict()`
  (`scripts/translate-articles.py:165-180`) ritorna `"fresh"` _solo_ quando `stamp == digest`,
  e uno stamp esiste solo se il campo è già scritto: «already fresh» IMPLICA timbrato, il
  contrario non regge.
- **byte-cap sulla mia sonda — CONFERMATA, ed è la causa.** Leggevo solo i primi ~2000
  caratteri di ogni file. `stamp_frontmatter()` (riga 146) aggiunge `source_sha256` **per
  ultimo** nel blocco frontmatter, e la SEO frontmatter di questo corpus supera regolarmente i
  2KB — la sonda mancava sistematicamente proprio i file con frontmatter lunga, non a caso.
  Ri-eseguita oggi con lo STESSO taglio (`_STAMP_RE.search(text[:2000])`, la regex dell'organo,
  non una reinventata): degli 847 file davvero timbrati, **425 hanno il timbro oltre il
  carattere 2000** (persi dal taglio) e **422 sono catturati entro il taglio** —
  `422 + 425 = 847`. Una ri-esecuzione byte-capped riproduce **422**, stesso ordine di
  grandezza del vecchio 426 sbagliato: il meccanismo è dimostrato riproducibile, non solo
  affermato.

**Riconciliato: il lavoro parte da 847/746, non dal numero vecchio.**

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

### §8 — `refs_in` conta per SUBSTRING del basename, e quel numero decide chi è orfano `[famiglia #3]`

Trovato spedendo questo file, non cercandolo: `inventory-check` mi ha bocciato, ho rigenerato
`docs/DOCS_INVENTORY.md` come chiede, e il diff toccava **19 righe** — la mia più AI_ONBOARDING
(che cito davvero) più **17 README che non cito affatto**.

Controllo positivo, stesso meccanismo: tolto il mio file e rilanciato lo STESSO regen, le righe
README che si muovono sono **0**. Quindi le causo io. Ma il documento contiene il token `README.md`
**una volta sola**, dentro un blocco di output verbatim di `docs_sync.py` (§5) — non è un link.

La regola la nominano le eccezioni: dei 20 README dell'inventario se ne muovono 17, e i **3 fermi**
sono esattamente quelli il cui basename non è letteralmente `README.md` — due sotto
`docs/audits/2026-04-29-zero-crash-audit/prompts/` con un prefisso numerico davanti al nome, e uno
in `docs/` con un prefisso maiuscolo. **Non li scrivo per esteso, e il motivo È la prova**:
nominarli qui li accrediterebbe, e per il terzo la prima stesura di questa sezione lo aveva già
fatto — il regen lo portava da `ARCHIVED` a `LIVE`, `refs_in` 0→1, e gli **cancellava**
`orphan_flipped_on: 2026-07-26`, cioè la data in cui era stato dichiarato orfano. La frase che lo
citava come esempio di file senza riferimenti entranti è ciò che lo rendeva riferito. Per
riprodurlo: scrivi il suo nome in un qualunque `.md` sotto `docs/` e rilancia il regen.

Il meccanismo è dichiarato nel sorgente: `scripts/docs_audit.py:340` documenta «count other .md
files that contain target's basename» e `:365` lo esegue come `if basename in c.read_text(...)` —
**substring, non path risolto né word-boundary**. Conseguenza: qualunque doc che nomini `README.md`
in prosa accredita in un colpo tutti i README dell'albero. E la stessa forma morde in generale — un
doc chiamato `sync.md` incassa un riferimento da ogni testo che scriva `docs_sync.md`.

**Perché non è cosmesi:** `refs_in` non è decorativo, è il predicato dell'orfanità.
`docs_audit.py:895` fa `structurally_eligible = row.refs_in == 0 and rel not in whitelist`, e `:1094`
titola «Orphans (past orphan_eligible_on AND refs_in==0)». Un `refs_in` gonfiato **sopprime la flag
di orfano**: 17 README risultano referenziati da un token che non li nomina.

**Cosa NON fare:** riscrivere la mia riga per non emettere il token. È output verbatim di un tool —
alterarlo sarebbe fabbricare l'output di un tool, che è la sola cosa che qui non si fa mai. Il
difetto è nel contatore, non nella prosa che lo inciampa.

**Cura vera** (PR propria, non da infilare qui): contare per **link risolto** — o almeno per
basename ancorato ai delimitatori di un path/markdown-link — con corpus di colpevolezza (un link
vero conta) **e** di innocenza (una menzione in prosa, e un basename che è sotto-stringa di un
altro, NON contano). Finché non è curato, `refs_in` è un proxy e va letto come tale (W88).

---

## Ordine consigliato

**Prima** la riconciliazione di §3 (blocca tutto il resto di §3) e §1 (job quotidiano su codice
forkato). **Poi** §2 e §4 in parallelo, indipendenti. **Poi** §5, meccanico. **Infine** §6 e §7,
che sono decisioni da mettere a verbale, non diff.

**§8 sta fuori da quest'ordine**: è una guardia difettosa, non un organo derivato, e vuole la sua PR
con corpus di colpevolezza e innocenza propri. Non infilarlo in una cura d'altro — è precisamente
così che una #3 si cura sul solo payload che ti ha morso.

Uno solo di questi è client-facing: §3, perché `fr`/`ru` sono ancora **servite**. Lì il gate
adversariale va alzato, e la decisione «cosa facciamo delle 967» è Legge 5 — si porta a Zero
misurata, non si sceglie in autonomia.

---

## CHIUSURA — 2026-08-08

Ogni riga qui sotto è stata **ri-misurata oggi**, su un `origin/main` fresco (`git fetch` prima),
non ricordata dal dossier. Dove un numero qui contraddice il corpo sopra, il corpo è la lettura
vecchia e vince questa tabella: il corpo resta intatto di proposito, così chi legge dopo trova la
cifra precedente già smentita invece di ri-derivarla (W113).

| §   | Reperto                                                 | Stato                             | Chiuso da                                                           | Prova ri-eseguita oggi                                                                                                                                    |
| --- | ------------------------------------------------------- | --------------------------------- | ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| §1  | `auth-sentinel.daily` esegue una copia HOME divergente  | **CHIUSO**                        | non mio — stato già riconciliato                                    | `sha256` di live, `origin/main` e questo checkout tutti `fc7ed0b2b44af2b1`; reconciler: `HOME-fork target (0)`, la coppia ora classificata `Canon-paired` |
| §2  | `nuzantara-repo-sync` non ha canon per niente           | **CHIUSO** (Opzione A, ritiro)    | questa sessione — #3800                                             | plist su disco come `…plist.retired-20260808` (età 0.2d); record di decisione con header `Status: CLOSED`                                                 |
| §3  | 967 pagine `fr`/`ru` fuori dal loop orario              | **APERTO — `operator[business]`** | nessuno: è una chiamata Legge 5, non un difetto                     | riga 774 del ledger aperta; il log dell'organo stanotte nomina ancora l'orfano                                                                            |
| §4  | il battito di `pro.translate_hourly` mente              | **CHIUSO**                        | non mio — #3725 (`scan_sidecars` giudica per giurisdizione)         | sidecar **su Pro**: `ts 2026-08-08T05:30:24Z status ok`; `launchctl` caricato, exit 0                                                                     |
| §5a | `docs_sync` stantio su due file, la sonda ne nomina uno | **CHIUSO**                        | non mio — #3727 (il parser exit-code di `run_wrap` sotto-riportava) | `docs_sync.py --check` **RC=0**, eseguito su un albero fatto a `origin/main`                                                                              |
| §5b | plist `worktree-gc-universal` Repo-divergent            | **CHIUSO**                        | questa sessione — #3799                                             | reconciler con lo script mergiato: `Repo-divergent (0)`                                                                                                   |
| §6  | due sonde prescrivono cure superate                     | **CHIUSO**                        | non mio — #3723                                                     | eseguita contro il checkout vero: ora stampa «do NOT pull it» — vedi il reperto nuovo qui sotto                                                           |
| §7  | code aperte ereditate dal ledger                        | **CHIUSO come contesto**          | —                                                                   | ciascuno dei cinque item ha ≥1 riga viva a ledger; `phantom_operator=0`, `malformed=0`                                                                    |
| §8  | `refs_in` conta per substring del basename              | **CHIUSO**                        | non mio — #3777                                                     | un regen dell'inventario in questa sessione ha mosso **2 righe** (il timbro e la mia riga), non le 19 di prima                                            |

### Un reperto nuovo, ed è la stessa malattia un piano sotto

§6 chiedeva di curare la **prescrizione**, e la prescrizione è curata. Eseguendo la sonda curata
contro il checkout M5 vero, però, emerge la sua metà azionabile:

```
!! [P1] git_alignment: main checkout: 200 behind origin/main, 16 dirty entries
   fix: … do NOT pull it … The actionable half is the ledger: refresh just that file from
   origin/main (e.g. `git checkout origin/main -- .claude/skills/modus/PENDING-ARMS.md`
   in the main checkout, not a full pull) so TRIAGE stops reading stale state.
```

Il reperto è reale — il ledger nel main checkout è **99 inserzioni / 10 cancellazioni** indietro
rispetto a `origin/main`, è `tracked-clean` (nessun lavoro non committato di nessuno è a rischio),
e TRIAGE legge quella copia. Ma **nessuna sessione può eseguire la prescrizione**:
`worktree_isolation.py` blocca ogni git mutante nel main checkout, e l'unica via d'uscita che il
messaggio documenta è `AGENT_WORKTREE_ENFORCEMENT=false`, che disarma la guardia in blocco. I git
_read-only_ lì passano — misurato più volte in questa sessione — quindi il blocco è selettivo per
verbo, non un malfunzionamento.

Con «non c'è nessun operatore» in vigore, una prescrizione che solo un umano potrebbe eseguire
nomina una corsia che non esiste. È esattamente ciò di cui parlava §6: una sonda che consiglia
una cosa vietata addestra chi legge a ignorarla, e la volta dopo ignorerà quella giusta. Lasciato
come riga a ledger invece che forzato — la cura sta nel testo del rimedio o in un'uscita stretta
sanzionata, non in una sessione che disarma la guardia per passare.

### Due letture mie che erano sbagliate, e come sono state prese

- **Una sonda eseguita dall'albero sbagliato.** Il reconciler dava `Repo-divergent (1)` per §5b,
  cioè ancora rotto. Era lo **script pre-cura**: quel worktree è 10 commit indietro e non porta
  #3799 (`_rebase_homes`: 0 occorrenze lì, 4 su `origin/main`). Ri-eseguito con la copia mergiata
  — e col canon plist provato byte-identico fra le due revisioni prima di fidarsi — dà 0. Lo
  stesso strumento risponde 1 o 0 secondo il checkout che lo esegue.
- **Assenza letta come salute.** La proprioception di M5 non elenca più `pro.translate_hourly`, e
  stavo per chiudere §4 su quello. M5 porta **5** sidecar, Pro ne porta **152**. La sparizione non
  prova niente: solo chiedendo a Pro è arrivata la ricevuta vera. (Il divario 5-vs-152 **non** è un
  punto cieco: il detector legge i sidecar locali per disegno, il sync cross-host è una allowlist
  esplicita di UN organo, e il codice dice che i guardiani residenti su Pro «legittimamente non
  esistono» su M5. Su questo mi ero sbagliato per una misura.)

### Non toccato, di proposito

- **Le 967 pagine di §3** — sono ancora **servite**; se continuino a invecchiare senza manutenzione
  è una decisione di business (Legge 5), non un difetto da auto-chiudere.
- **Il main checkout M5** — 200 indietro per progetto; non tirato, e la sonda curata ora lo dice da sé.
- **I commenti di `com.nuzantara.worktree-gc-universal.daily.plist`** — una lane sibling
  (`agent/air-m5/infra/worktree-gc-plist-docsync`, creata alle 13:45 di oggi) li sta allineando alla
  copia viva M5. Complementare, non duplicato: sono commenti XML, che `plistlib` scarta, quindi il
  reconciler non li ha mai visti e #3799 non poteva vederli. Tocca a loro atterrare.

---

### §9 — il guardiano non sapeva quale versione di sé stesso, né dei payload che esegue, stesse girando `[famiglia #2 + #9]`

Trovato **chiudendo** questo dossier, non cercandolo. §6 chiedeva di curare una prescrizione
superata, e la cura è entrata. Ma la domanda che §6 pone — _«questa prescrizione è più vecchia della
decisione che la contraddice?»_ — vale anche un piano sotto, e lì nessuno l'aveva posta: **quale
copia del codice ha scritto la riga che sto leggendo?**

Su M5 il main checkout è indietro per progetto (223 commit alla chiusura) e `proprioception.py` gira
**da lì**. Due insiemi distinti, due PR:

1. **La sonda stessa** era 4 commit indietro: ogni reperto e ogni rimedio del report erano il testo
   VECCHIO di quella copia, sotto un timestamp di minuti prima. **#3835** — il report ora porta
   `runner_blob`, e se la copia che l'ha scritto non è quella di `origin/main` lo dice in prima riga
   e sopprime il rimedio del registro (che parlerebbe di _schedule_ quando il problema è il _codice_).
2. **Gli script che la sonda ESEGUE** non erano coperti da quella cura. Curare il runner e
   dichiarare chiusa la malattia è W107. La PR gemella di questa tornata (branch
   `agent/air-m5/ops/executed-code-currency`, aperta subito dopo #3835 e da essa dipendente —
   citata per branch e non per numero, perché il numero non esiste finché la PR non è aperta e
   indovinarlo produce un riferimento che RISOLVE su una PR altrui): censiti leggendo il
   registro caricato,
   **3 dei 6 in giurisdizione M5** erano indietro.

**Uno mentiva, e l'A/B è controllato** — stessa macchina, stessa `~/Library/LaunchAgents`, stesso
minuto: il `launchagent_reconcile.py` del checkout risponde `repo_divergent:
[com.nuzantara.worktree-gc-universal.daily]`, quello di `origin/main` risponde `[]`; `_rebase_homes`,
la funzione aggiunta da #3799, compare **0** volte nella copia eseguita e **4** su `origin/main`.
Cioè: **il P2 in cima al banner di sessione era il verdetto pre-cura di §5b, che questa stessa
sessione aveva chiuso**, e nulla nel report permetteva di distinguerlo da un P2 vero.

**Il conto giusto è 3 su 6, non 4 su 7 — e la differenza è una lezione, non un arrotondamento.**
`arsenal_probe.py` è anch'esso indietro qui, ma il suo wrap è `machines: ["mini","pro"]`: M5 non lo
esegue mai, e le macchine che lo eseguono sono state misurate lo stesso giorno a **0/7 divergenti**.
Contarlo produceva un P1 su cui nessuno su questo host può agire. La prima stesura lo contava.

**Perché è una malattia di M5 e non del codice**: Pro e Mini sono auto-pulled e misurati oggi a 0/7
payload divergenti ciascuno — la sonda tace lì per costruzione, e l'innocenza è verificata sulle
macchine vere. È anche il motivo per cui giudica il **blob del singolo file** e non la distanza in
commit: entrambe sono «1 indietro», e nessuno dei sette file è cambiato in quel commit.

**Non curabile tirando il checkout** (W106b: corre contro ~45 worktree vivi). La cura è che l'organo
lo DICHIARI e indichi la sola via percorribile qui — eseguire la copia di `origin/main` fuori albero,
senza toccare il checkout:

```
git -C <root> show origin/main:scripts/proprioception.py > /tmp/prop_main.py \
  && NUZ_REPO_ROOT=<root> python3 /tmp/prop_main.py
```

**Resta aperto a ledger**: su M5 ogni payload di hook risolto via `${CLAUDE_PROJECT_DIR}` è congelato
all'HEAD del main checkout, quindi «merged» non raggiunge quelle superfici. Misurato oggi: **5
payload, 0 divergenti** — l'esposizione è latente, non attiva, e la riga a ledger lo dice
esplicitamente invece di lasciar credere il contrario.
