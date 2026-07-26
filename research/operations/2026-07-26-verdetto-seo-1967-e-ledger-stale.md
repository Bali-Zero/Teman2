---
date: 2026-07-26
domain: operations
client_case: none
adversarial_review: glm
sources:
  - apps/mouth/src/lib/kbli-data.ts:376-380 (commento flip META_EN, su main)
  - .claude/skills/modus/PENDING-ARMS.md:79 (#1967) e :169 (META_EN)
  - git 969f1f82bc (unico commit del branch agent/air-m5/mouth/seo-batch3-title-meta-v3)
  - scripts/pending_arms_report.py (run 2026-07-26, counts)
  - .claude/rules/cicatrix-scars.md (W88, W90, W100)
---

# Verdetto: PR #1967 (KBLI batch3 title/meta v3) + flip META_EN — e due voci di ledger stantie

Sessione: digest mattutino 2026-07-26, delega esplicita di Zero ("giudica e procedi tu").
Ambiente: Cowork/M5, sandbox Linux con mount del repo — **nessun `gh`, nessun `fly`, nessun
accesso a Pro/Mini/Vercel/GSC**. Quindi: giudizio + verifica su disco eseguiti; merge, env-flip
e rotazioni NON eseguibili da qui (lista di armamento in §4).

## 1. Il flip META_EN è GIÀ FATTO — la voce di ledger è stantia

`apps/mouth/src/lib/kbli-data.ts:377-379` su main dice verbatim:

> FLIPPED 2026-07-13 (Zero GO, post-#2359 editorial launch): NEXT_PUBLIC_KBLI_META_EN=1
> is set in Vercel Production — metadata now consumes the full-coverage titles.

La voce di ledger `PENDING-ARMS.md:169` (aperta 2026-07-07, `operator[business]`, età 18d) chiede
esattamente quella decisione: **è chiusa da 13 giorni**. Contribuisce a gonfiare
`operator_gated_overdue=63` con un item su cui Zero ha già deciso e che è già armato.
Famiglia #2 (Esiste ≠ Armato) al contrario: *armato ma il ledger lo dà come pendente*, cioè il
rischio #1 di W78 (no unlearning) — un dato marcio che si propaga a ogni digest.

Restava non verificato solo il criterio di prova della riga ("view-source di /kbli/28180 mostra
un `<title>` inglese"): non eseguibile da questa sandbox.

## 2. PR #1967: NON è su main (verifica per CONTENUTO, regola W88)

- Branch vivo su origin: `agent/air-m5/mouth/seo-batch3-title-meta-v3` → tip `969f1f82bc`
  (2026-07-05, "PAUSED, operator gate"), **un solo commit**, 4 file, +144/-3.
- File autorati: `apps/mouth/src/app/kbli/[code]/page.tsx`, `apps/mouth/src/lib/kbli-derive.ts`,
  `kbli-derive.test.ts`, `research/seo/2026-07-05-batch3-title-meta-queue.md`.
- Content-check: il simbolo introdotto `riskLabelEn` ha **0 occorrenze** in `apps/mouth/src` su
  main, e il queue doc non esiste su main (`research/seo/` contiene solo
  `2026-07-05-kbli-seo-offensive.md`). → sostanza **non landed**, nessun rework l'ha anticipata.

## 3. Verdetto: NO-GO al merge oggi. Due motivi, il secondo è nuovo

**(a) Il firebreak era il congelamento dei metadata, e è già stato speso il 13/07.**
#1967 riscrive `<title>` e `description` di ~1.559 pagine. La stessa superficie è già stata
riscritta 13 giorni fa dal flip META_EN (curated-legacy → mappa EN completa), per GO di Zero.
Mergiare adesso impila una seconda riscrittura sopra una riscrittura di 13 giorni, nella
finestra in cui il criterio di prova della riga 169 (impression GSC stabili **2 settimane** dopo
il flip) non è ancora valutabile: la data utile è **≥ 2026-07-27**, non il 26. La scadenza
"~26/07" che ho segnalato nel digest era la finestra di crawl-recovery, non una deadline di merge.

**(b) Rischio nuovo, che il PR del 05/07 non poteva conoscere: mette claim regolatori nel `<title>`.**
Il suffisso v3 costruisce titoli come `Max {maxForeign}% Foreign Ownership`,
`Blocked for PT PMA in Bali (2026)`, `{risk} Risk`, e la description aggiunge
`license: {licenseType || "NIB"}`. Le sorgenti sono `pma.maxForeign/capVerified`,
`baliL4.blocked`, `licensing[0].riskCategory/licenseType` — cioè proprio i campi rimessi a terra
DOPO il 05/07: risoluzione PMA contro il lampiran Perpres 10/2021 (27/06) e i lot Batch A chiusi
fino al 21/07, dove W100 ha trovato **13/13 quarantine nel Lot 1** su payload licensing
(`payload_cross_contamination` / `unresolvable_source_pointer`).
Il suffisso *è* prudente su `capVerified` (senza flag degrada a "Foreign Ownership Restricted"),
ma **`baliL4.blocked`, `riskCategory` e `licenseType` non sono gated** — e finirebbero indicizzati
in title/meta su 1.559 pagine. Regola di onestà regolatoria + W90/W100: un claim su cap/rischio/
licenza non va in un `<title>` se non è verificato alla sorgente.

**Condizione di GO (verificabile, non "a sentimento"):**
1. dal 2026-07-27, GSC: long-tail `/kbli/*` last-crawl <14d e impression stabili post-flip 13/07;
2. gate sui campi non verificati: il suffisso emette la variante rischio/Bali-blocked **solo** se
   il record porta il flag di verifica (stessa disciplina già applicata a `capVerified`),
   altrimenti degrada a un suffisso neutro;
3. spot-check post-merge su un codice del Lot-1 quarantinato, non solo su `/kbli/56101`.

Il punto 2 è una modifica di ~10 righe su `page.tsx`: senza quella, il merge pubblica dati sotto
cura in superficie indicizzata.

## 4. Lista di armamento (Mac-side — non eseguibile da questa sandbox)

| # | Azione | Owner | Note |
|---|---|---|---|
| 1 | Chiudere `PENDING-ARMS.md:169` (META_EN) come CLOSED 2026-07-13, con la citazione di `kbli-data.ts:377` | sessione (worktree + PR) | rimuove 1 falso overdue operator-gated |
| 2 | Riscrivere la riga 79 (#1967): premessa cambiata, GO condizionato ai 3 punti §3 | sessione | non è più "attesa indefinita" |
| 3 | Pass di riconciliazione sui 63 `operator_gated_overdue` con la regola W88 (contenuto, non SHA) | sessione | il numero 63 non è affidabile: 1 stantio trovato al primo controllo |
| 4 | Patch gate su `baliL4.blocked`/`riskCategory`/`licenseType` nel branch #1967, poi merge | sessione | prerequisito tecnico del GO |
| 5 | P0 `apps/cell/.env`: rotazione password `backend_rag_v2` + demozione NOSUPERUSER (W38), atomica su Fly secret + `.env` locali Pro/Mini/M5 | operator[secret] | perms su M5 già `0600` (verificato); la copia Pro non verificabile da qui |
| 6 | Seat `claude-opus` del bot tri-LLM `down (no_json)` | operator[secret] o sessione | il bot **non è** `ai-pr-review.yml` (single-seat, degrada a skip su token assente); posizione del tri-LLM non localizzata in questo checkout → non verificato |

## 5. Non verificato (dichiarato, non indovinato)

- Stato GitHub di #1967 (open/closed/draft): nessun `gh` nella sandbox.
- Dati GSC (crawl freshness, impression post-flip).
- Perms e valore del `.env` su Pro (mai aperto alcun file `.env` in questa sessione).
- Se le 5 crawl-fix (#1963/#1965/#1966/#1974/#1977) sono live da 2-3 settimane.

---

# ADDENDUM 2026-07-26 (sessione M5, con `gh`) — la premessa è cambiata

La sessione Cowork aveva `gh` assente e dichiarò lo stato GitHub di #1967 come UNKNOWN (§5).
Verificato oggi, quell'unknown era la premessa portante: **il verdetto §3 giudicava un merge che
non esiste.**

## A1. #1967 è CLOSED — e non per una decisione

`gh pr view 1967` → `state: CLOSED`, `closedAt 2026-07-13T00:57:29Z`, `mergedAt: null` (chiusa
NON mergiata, non "mergiata poi chiusa"). La timeline porta, **allo stesso secondo**, l'evento
`base_ref_force_pushed`. Meccanismo esatto non accertato (correzione da adversarial review, vedi
in fondo): il comportamento standard di GitHub su un force-push del base è marcare la PR
"out of date", non chiuderla — la chiusura è più probabilmente l'effetto dell'orfanizzazione
dell'head-commit per il rewrite `filter-repo`, con `base_ref_force_pushed` co-occorrente ma non
necessariamente la causa diretta. La conclusione (il PII-purge come causa radice) regge in
entrambi i casi; il meccanismo preciso no.

Non è un caso isolato: `gh pr list --state closed --search "closed:>=2026-07-13 closed:<=2026-07-13 is:unmerged"`
restituisce 22 PR, di cui **21 chiuse nell'intervallo `00:57:28–29Z`** (17 alle :28Z, 4 alle :29Z,
corretto da adversarial review — vedi in fondo) — un solo secondo. L'unico outlier (#2402, 14:24:32Z)
è un cleanup manuale successivo del ledger, non parte del cluster. È la finestra di force-push del
PII history-purge (`ops_pii_history_purge_executed_proven_2026_07_13`, memoria di sessione — non un
file di questo repo: `origin/main 2ae5e6fb → 33120add`, `enforce_admins=false`, filter-repo su 7837
commit). Ventuno PR non si chiudono per ventuno decisioni indipendenti nello stesso secondo.

Esito del ripristino, 13 giorni dopo:

| | n | nota |
|---|---|---|
| branch DELETED (rifatte e atterrate) | 18 | es. #2357 → #2393, #2366 → #2394 |
| branch vivo, nessun successore | 3 | #2326, #2301, **#1967** |

Ricerca per titolo, per nome-branch e per `"title/meta"`: **nessuna PR erede di #1967**. Il lavoro
è orfano dal 13/07 senza che nessuno l'abbia deciso — e il ledger lo dava ancora come "in attesa
della decisione di Zero", cioè W78 (no unlearning) al secondo grado: non solo il dato è marcio, ma
descrive come *pendente-per-scelta* qualcosa che è *morto-per-incidente*.

## A2. Il merge-base è morto — e con lui il check W88 del graveyard

`git merge-base origin/main <branch>` è **VUOTO** per tutti e tre i branch pre-purge: la riscrittura
ha reso le storie non correlate. E `scripts/branch_graveyard_cleanup.sh::content_on_main()` apre con
`mb=$(git merge-base …) || return 1` → dal 13/07 **restituisce "contenuto non su main" per ogni
branch tagliato prima del purge, senza confrontare un solo blob**. Il "0 content-on-main deletable su
83 branch" registrato quel giorno è quindi un artefatto del merge-base morto, non un fatto sul
contenuto. Terzo grado della trappola W88: là il proxy era il three-dot, qui è il merge-base stesso.

**Metodo corretto post-rewrite** (usato qui, e da usare in ogni riconciliazione): il file-set si
prende dai **commit che il branch ha autorato** (`tip^..tip` per un branch mono-commit), poi
blob-compare per file contro `origin/main`. Per #1967: 4/4 file DIFF → contenuto non su main,
corroborato indipendentemente da `riskLabelEn` = 0 hit su `apps/mouth/src`.

## A3. La riga 169 (META_EN) ha la sua prova sulla superficie, non nel codice

Il criterio di prova della riga era "view-source di /kbli/28180 mostra un `<title>` inglese":

```
GET https://balizero.com/kbli/28180 → 200
<title>KBLI 28180: Power-Driven Hand Tool Manufacturing — Indonesia Business Guide 2025 | Bali Zero</title>
```

Titolo inglese full-coverage, live. La riga si chiude su questo, non sul commento a `kbli-data.ts:377`
(che è il codice, cioè di nuovo un proxy).

## A4. Il gate del punto 2 §3, misurato invece che stimato

Il repo ha già l'anticorpo: `isLicensingVerificationPending()` (`kbli-provenance.ts`), il cui
commento dice *"Every surface that states risk/license/processing as fact for such a code must
qualify the claim — FAQ, JSON-LD, key-fact grids all key on this single helper so they can't drift
apart"*. Il body di `/kbli/[code]` ci si aggancia già (`page.tsx:345` sul `RiskBadge`) e qualifica il
claim Bali passando `confidence` + `needsReview` a `BaliStatusBadge` (`page.tsx:353-354`).

`generateMetadata` sarebbe stata una **nuova superficie che afferma gli stessi fatti senza
agganciarsi a nessuno dei due**. Misura sul dataset reale (1.559 record):

| fatto nel `<title>` di #1967 | pagine coinvolte | di cui verificate | **claim non verificati indicizzati** |
|---|---|---|---|
| `{risk} Risk` + `license: {licenseType}` | 1.342 con risk servito | 1.336 oss-native | **6** |
| `Blocked for PT PMA in Bali (2026)` | 455 (PMA-open ∧ `baliL4.blocked`) | 33 (`confidence=HIGH` ∧ `!needsReview`) | **422** |

Il gate non è cosmetico: toglie **422 titoli** che affermerebbero un blocco regolatorio a
confidence MEDIUM/LOW — il 27% del catalogo — da una superficie indicizzata da Google.

## A5. Verdetto aggiornato

Il NO-GO §3 resta, per i motivi (a) e (b) originali, **più** un terzo che li precede: non c'è nulla
da mergiare. Il lavoro va **risuscitato in draft** (decisione di Zero, 2026-07-26) su un branch
tagliato dal main corrente, col gate §3.2 agganciato agli helper esistenti. Il merge resta
subordinato alle 3 condizioni §3, invariate.

## Adversarial review

**Seat:** GLM (`claude-glm`, Zhipu GLM-5.2 su Claude Code CLI, Keychain OAuth token) — seat
cross-family rispetto a Claude, unico mandato: falsificare o confermare l'affermazione centrale di
§A1-A2 ("PR #1967 died to a force-push, not a decision"). Dispatch con path del file (non diff
incollato), sandbox con `gh`/`git` reali, istruito a RI-ESEGUIRE le query invece di fidarsi della
prosa.

**Verdict: CONFIRMED**, con due correzioni fattuali reali (non un timbro):

1. **Conteggio sbagliato**: il report diceva "20 PR su 22 chiuse nella finestra di un secondo" —
   il conteggio corretto è **21** (17 alle `:28Z` + 4 alle `:29Z`; il 22° è #2402, cleanup manuale
   alle 14:24:32Z, eventi confermano nessun `base_ref_force_pushed` associato). Il clustering è
   ANCORA PIÙ stretto di quanto dichiarato, non più debole — ma il numero citato era sbagliato ed
   è stato corretto in §A1 sopra.
2. **Meccanismo non accertato**: GLM ha verificato che il comportamento standard di GitHub su un
   force-push del base è marcare la PR "out of date" (DIRTY), non chiuderla automaticamente. La
   causa più probabile della chiusura è l'orfanizzazione dell'head-commit dal rewrite
   `filter-repo`, con l'evento `base_ref_force_pushed` co-occorrente ma non necessariamente il
   trigger diretto. Corretto in §A1 sopra — la conclusione causale (PII-purge = causa radice) non
   ne risulta indebolita, solo il "come" preciso.
3. **Imprecisione di provenienza**: il report citava
   `ops_pii_history_purge_executed_proven_2026_07_13` come "referenced elsewhere in this repo" —
   è uno slug di memoria di sessione (`~/.claude/projects/.../memory/`), non un file di questo
   repo Teman2. Corretto in §A1 sopra.

**Prove indipendenti aggiunte da GLM, non presenti nel report originale:** `gh pr view 1967
--json baseRefOid` restituisce `33120add2ac3b6f65c25191856af2c0ee81a77f9` — corrispondenza
verbatim (40 hex char) con l'SHA post-purge citato dal report, confermata lato server GitHub
indipendentemente dalla profondità del clone locale (che è shallow e non può verificare
l'ancestry SHA in profondità — limite d'ambiente dichiarato da GLM, non un buco nella tesi).
GLM ha anche campionato 4 PR aggiuntive nel cluster (#2368, #2363, #2322, #2295): tutte mostrano
lo stesso pattern `closed` + `base_ref_force_pushed` co-occorrenti, stesso attore, stesso secondo.

**Cosa NON è stato rivisto** (fuori mandato, dichiarato esplicitamente nel brief): §1-§4 e
A3-A5 (il gate sui campi non verificati, il verdetto NO-GO, la lista di armamento) — solo la
claim del force-push in §A1-A2 era in scope per questo seat.
