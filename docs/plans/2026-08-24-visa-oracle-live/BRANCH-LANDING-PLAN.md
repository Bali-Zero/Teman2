# Piano di atterraggio di `feature/visa-oracle` — misurato 2026-08-26

> Il mandato Visa Oracle vive interamente su un branch che **non ha mai avuto una pull request**.
> Nessuno dei suoi contenuti è su `main`: né il pack firmato, né le firme dello switchboard, né
> `docs/plans/2026-08-24-visa-oracle-live/`. Questo documento non propone di aprire una PR da 88
> commit — propone come tagliarli.

## Lo stato, misurato (non ricordato)

```
avanti su origin/main : 88 commit
indietro              : 53 commit
gh pr list --head feature/visa-oracle --state all : []
```

Tutte le altre PR visa-oracle del repo (#4192, #4232, #4253, #4254, #4278, #4651, #4706, #4822)
vanno da un branch `agent/…` dritte a `main`. Questo branch è l'eccezione.

## La superficie, per area

| area                                 | file | righe (add+del) |
| ------------------------------------ | ---: | --------------: |
| rule packs (JSON sorgente + firmati) |    4 |          37.235 |
| docs + research                      |   30 |           5.303 |
| frontend (`apps/mouth`)              |   37 |           4.784 |
| test                                 |   21 |           3.759 |
| backend codice                       |   24 |           3.262 |
| altro (`.husky/pre-commit`, ledger)  |    2 |              37 |
| **totale**                           |  118 |          54.380 |

Il volume spaventa meno di quanto sembri: **il 68% sono i quattro JSON dei rule pack**, artefatti
generati e firmati, non codice da revisionare. Il codice effettivamente leggibile è ~11.800 righe.

## Il conflitto reale è DUE file

`git merge-tree --write-tree origin/main HEAD` (a secco, nessuna mutazione) dà **2** conflitti di
contenuto su 118 file:

- `apps/backend-rag/backend/tests/services/visa_engine/test_evaluate_endpoint.py`
- `apps/mouth/src/app/sitemap.test.ts`

Tutto il resto auto-fonde, `PENDING-ARMS.md` incluso. Dei 10 file che si sovrappongono a ciò che
`main` ha cambiato nel frattempo, 8 fondono da soli.

⚠️ Su `PENDING-ARMS.md` la fusione pulita **non** è una garanzia: è append-only, e la cicatrice
W125 dice che una fusione senza marker può comunque perdere righe. Va verificata per CONTENUTO
(conteggio righe prima/dopo), mai per assenza di conflitto.

## Le fette proposte, in ordine

Ogni fetta parte da un `origin/main` **fresco**, non dal branch — e ogni fetta è una PR con il suo
gate. L'ordine non è negoziabile: la 2 e la 3 importano artefatti che solo la 1 introduce.

**1 — motore e contratti.** `backend/services/visa_engine/**`, `backend/scripts/visa_engine/**`, i
4 rule pack, i test backend del motore. È la fetta che porta il pack **firmato**: deve atterrare
**byte-identica**, o la firma decade. Qui si risolve il conflitto di `test_evaluate_endpoint.py`.

**2 — funnel frontend.** `apps/mouth/**` (37 file). Dipende dai reason_code e dai product code che
la fetta 1 introduce. Qui si risolve `sitemap.test.ts`.

**3 — documenti e ricerca.** `docs/plans/2026-08-24-visa-oracle-live/**`, `research/visa/**`. Nessun
codice, nessun gate oltre i lint: è la fetta che si può mergiare per ultima senza rischio.

**Fuori fetta, da trattare a parte:** `.husky/pre-commit` è HOT ZONE. Non va infilato in nessuna
delle tre — o è una PR sua con il suo gate, o resta sul branch.

## Precondizioni prima della fetta 1

1. **Risolvere i 53 commit di ritardo.** Non con un merge dentro il branch (creerebbe un merge
   commit dentro le fette): rebase della singola fetta su `origin/main` fresco.
2. **Il bundle firmato deve atterrare byte-identico nel PAYLOAD.** Il file può essere riformattato
   da prettier (lo è già stato: la firma regge, RFC8785 canonicalizza l'oggetto payload e gli spazi
   non contano) — ma `payload_sha256` deve ricalcolarsi e `verify_rule_pack` deve passare **dopo**
   l'atterraggio, non prima. Verificato per contenuto, mai per hash del file.
3. **Nessuna fetta apre auto-merge verso un branch d'integrazione.** Solo verso `main`, che ha i
   required context; verso un branch d'integrazione «mergia sul verde» significa mergiare senza gate.

## Cosa questo piano NON dice

Non dice che le tre fette passeranno la CI: il branch non è mai stato misurato contro i gate di
`main`, e 53 commit di deriva possono aver rotto qualcosa che qui è verde. La prima fetta è anche
la prima misura reale.
