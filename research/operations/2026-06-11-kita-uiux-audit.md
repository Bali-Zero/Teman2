---
date: 2026-06-11
domain: ui-ux
client_case: internal-ops-console
surface: kita.balizero.com (Next.js operator console)
auditor: Claude Opus 4.8 via Cowork + Chrome MCP (sessione NON girata su Fable 5)
sections_reviewed: [dashboard, review, clients, process, hr, lkpm, partners, intelligence, intelligence/news-room, intelligence/article-composer]
note: audit lato-UI. Le stime "costo-codice" sono inferite dalla divergenza visiva tra pagine e vanno confermate sui componenti Next.js prima di aprire PR.
---

# kita.balizero.com — Audit UI/UX (2026-06-11)

## Premessa

Metrica guida: **più clienti gestiti per operatore** (team ~8–18, ~1.481 clienti).
Ogni proposta è valutata su *tempo/click/errori tolti all'operatore*, NON su estetica.
Vincolo Zero: **non complicare il codice — semplificarlo**. Qui non c'è tensione: ~80% delle
issue è "consolidare implementazioni divergenti in componenti/utility condivise" →
UI più coerente e veloce **E** meno codice (net costo-codice ≤ 0).

Verdetto sintetico: l'app è ricca e già ben pensata (search con `/` to focus, quick-filter,
kanban, viste multiple). I problemi NON sono di feature mancanti — sono di **coerenza,
densità informativa e segnale-operativo sepolto**. Tutti risolvibili rimuovendo/consolidando,
non aggiungendo.

---

## P0 — alto impatto, basso rischio, fai subito

### P0.1 — La dashboard seppellisce il segnale operativo sotto un hero "news"
**Problema.** La prima cosa nella dashboard è un hero gigante (articolo balizero.com "live",
carosello). Il segnale che conta per l'operatore — "50 documents waiting for your review",
i KPI (Revenue, Outstanding, Processi, Fatture), la Team Performance — sta **sotto la piega**.
In una console ops apri la giornata per sapere *cosa richiede azione ora*, non per leggere news.
**Proposta.** Invertire la gerarchia: in alto la coda azioni ("50 da revisionare" + KPI),
hero news ridotto a card laterale o spostato dentro Intelligence Center.
**Impatto operatore.** Azione del giorno visibile a colpo d'occhio, zero scroll.
**Costo-codice.** Riordino componenti + rimozione/riduzione del carosello hero → meno codice.

### P0.2 — Metriche morte e colonne sempre-zero (erodono la fiducia nell'intera dashboard)
**Problema.** (a) KPI "CLIENTI registrati" in dashboard è **vuoto**, mentre /clients mostra
1.481 — metrica scollegata/rotta. (b) La tabella **Team Performance** ha 11 colonne ma
6 sono **zero per tutti** (CONVOS, MESSAGES, EMAILS OUT, EMAILS IN, KB VIEWS, KB DL).
Una tabella per metà di zeri dice all'operatore "questi dati non sono affidabili" e contamina
la fiducia su tutto il resto.
**Proposta.** Collegare il KPI Clienti alla stessa fonte di /clients; **rimuovere** (o nascondere
finché non strumentate) le colonne sempre-zero.
**Impatto operatore.** Dashboard leggibile e credibile; tabella con sole colonne vive.
**Costo-codice.** Pura rimozione: meno colonne renderizzate + meno plumbing dati a zero.

### P0.3 — Formato valuta caotico: 4 notazioni diverse per lo stesso numero
**Problema.** Stesso tipo di importo, 4 formati tra le pagine:
dashboard `Rp 1.15B` / `Rp 45.2M` · clients `Rp 45,2 jt` / `Rp 1,1 M` ·
process `Rp 800 rb` / `Rp 2 jt` · HR `Rp 1.850.000`.
Separatore decimale virgola vs punto, unità `jt/rb/M/B` mischiate. Su numeri di **soldi**
(che operatore e owner leggono di continuo) questo costa secondi di rilettura e mina la fiducia.
**Proposta.** Un'unica utility `formatIDR()` + un componente `<Money>`. Una sola fonte di verità →
coerenza ovunque e si **cancellano** N formatter ad-hoc sparsi.
**Impatto operatore.** Lettura immediata e senza ambiguità degli importi.
**Costo-codice.** Negativo: centralizzi e rimuovi duplicazioni.

---

## P1 — consolidamento (meno codice, meno carico cognitivo)

### P1.1 — Quattro paradigmi di sotto-navigazione diversi
**Problema.** HR usa una **sotto-sidebar verticale** interna; Intelligence usa **sub-tab in alto**;
Clients/Process usano **filter-chip**; Partners usa **dropdown nativi**. Quattro pattern per la
stessa funzione "naviga/filtra dentro un modulo" → l'operatore re-impara ogni sezione.
**Proposta.** Un solo pattern di sub-nav (i sub-tab in alto sono i più puliti) + un solo
componente filtro.
**Costo-codice.** Negativo: un componente al posto di quattro.

### P1.2 — Ogni pagina-lista reinventa lo stesso scaffolding
**Problema.** Header + stat-chip + filter-chip + view-toggle + search ("press `/` to focus")
sono ricostruiti su ogni pagina con markup/stili leggermente diversi.
**Proposta.** Estrarre `<ListPageHeader>`, `<StatChips>`, `<FilterBar>`, `<SearchBox>` condivisi.
La search con `/` è ottima: standardizzala identica ovunque.
**Costo-codice.** Forte dedup → molto meno codice, coerenza automatica.

### P1.3 — Microcopy IT/EN mischiato nella stessa schermata
**Problema.** Riga KPI: `Revenue/Outstanding` (EN) + `Clienti/Processi/Fatture` (IT).
Article Composer: label `Article Title`/`Raw Content` (EN) + placeholder `Incolla contenuto…`
/ `Es. New KITAS Rules…` (IT). Il team è bahasa: oggi legge un mix di 2 lingue non-sue.
**Proposta.** Scegliere UNA lingua UI (EN coerente, o ID dato il team) e centralizzare le stringhe
in un dizionario (i18n). Abilita anche una futura traduzione bahasa.
**Costo-codice.** Negativo: stringhe centralizzate al posto di hardcode sparsi.

### P1.4 — Intelligence: l'hub mente sul numero di strumenti
**Problema.** La landing /intelligence pubblicizza **2** strumenti (News Room, Article Composer),
ma il sub-nav interno ne mostra **3** (compare **Visa Oracle**, assente dall'hub).
**Proposta.** O l'hub riflette la realtà (3 card), o — meglio — si elimina la pagina-splash e i
3 strumenti vanno diretti nella sidebar/sub-tab (togli un click **e** una pagina intera).
**Costo-codice.** Negativo se elimini lo splash.

### P1.5 — News Room: rumore visivo + azioni una-per-una
**Problema.** ~10 card ognuna con accento di colore diverso (arcobaleno) e **un bottone Publish
per card**. Le card hanno già checkbox di selezione multipla, ma manca un'azione bulk.
**Proposta.** Accento di colore guidato dallo **stato** (non per-card random) + barra azione
unica "Publish selected" sulla multiselezione.
**Impatto operatore.** Pubblicazione in blocco invece di N click; meno rumore.
**Costo-codice.** Negativo: togli la logica colore per-card.

---

## P2 — polish

- **P2.1** Partners: TIER mostrato come `10.0000 %` → `10%`. Formattazione percentuali in un'unica utility.
- **P2.2** Client card a bassa densità (molto spazio verticale, "No recent interactions" ripetuto):
  persistere l'ultima vista scelta dall'utente (list/table/grid/map) e default alla più densa per gli ops.
- **P2.3** Stati vuoti ("No period / Not calculated yet", "No reports found") puliti, ma aggiungere
  una CTA inline ("Calcola periodo ora") toglie un passaggio.

---

## Tesi di fondo (perché tutto questo è anche "meno codice")

8 issue su 11 sono **la stessa medicina**: consolidare implementazioni divergenti in elementi condivisi
— `formatIDR`/`<Money>`, un `<FilterBar>`, un pattern di sub-nav, un dizionario stringhe, un `<ListPageHeader>`.
Ogni consolidamento (a) rende l'UI coerente e più veloce da usare e (b) **cancella** codice duplicato.
Non si aggiunge: si rimuove e si centralizza.

## Sequenza consigliata (PR atomiche)

1. **P0.2** rimuovi colonne sempre-zero + ripara KPI Clienti — pura cancellazione, rischio ~0, fiducia +++.
2. **P0.3** `formatIDR()` + `<Money>` — centralizzazione, una PR, impatto trasversale.
3. **P0.1** riordino dashboard (azione sopra, news sotto).
4. **P1.2 + P1.1** scaffolding condiviso + sub-nav unica (la PR che toglie più codice).
5. **P1.3** dizionario stringhe + lingua unica.
6. **P1.4 / P1.5 / P2** a seguire.

## Nota di verità (anti-allucinazione)

Questo audit è **lato-UI** (osservazione delle pagine renderizzate). Le stime "costo-codice ≤ 0"
sono **inferite** dalla divergenza visiva tra pagine, che implica duplicazione nei componenti Next.js —
ma vanno **confermate sul codice** prima di aprire PR. Prossimo passo naturale (lato Claude Code, sul repo):
aprire il frontend kita, verificare dove vivono i formatter valuta / gli header lista / le stringhe, e
quantificare le righe effettivamente eliminabili.
