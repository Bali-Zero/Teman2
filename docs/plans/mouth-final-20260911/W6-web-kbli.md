# W6 — Website: rifiniture locali KBLI

## 1. Mandate

`SHWEB-20260911 / W6-WEB-KBLI` · BLUE default · organ introduzione KBLI · Gear 2 minimo. Mini; nuovo worktree `~/nuzantara/.worktrees/mouth-shweb-w6-kbli-20260911`, task id `shweb-w6-kbli-20260911`. Base `origin/main` dopo W5, SHA registrato. Lancio solo con go esplicito Zero e baseline Lighthouse su `/kbli` e un dettaglio; criteri performance del README. Successo: introduzione e ritmo editoriale coerenti, ricerca e classificazioni invariate. Non è conversione light R19.

## 2. Owned perimeter

Dentro mouth: `src/app/kbli/page.tsx` sola presentazione introduttiva e blocchi editoriali; nuovo `kbli-editorial.module.css` colocato, `kbli-editorial.test.tsx`, `e2e/shweb-kbli.spec.ts`. Non toccare logica di ricerca nello stesso file: il diff viene controllato anche per funzione, non solo per path.

Vietati: KBLI engine/API/cataloghi/JSON/risultati/colore rischio o PMA, `--kbli-*` globali, font Montserrat, Footer/NavShell/layout/theme/globals, pipeline articoli, package/lock, Oracle/Studio. Nessun file shared writable.

## 3. Sibling contract

`studio-web-contract-v1`; congelare fixture di query e risultato presenti nei test correnti prima di BUILD. Ricerca, filtri, codice/titolo/rischio/stato e link dettaglio rimangono identici; composizione ospita gli stessi consumer. Query vuota, senza risultati ed errore di rete mantengono stati espliciti. L'aspetto dark/copper KBLI resta distinto; R19 fornisce soltanto gerarchia e spaziatura.

## 4. Acceptance

- Introduzione più leggibile senza inventare dati o ridisegnare risultati. Nessun badge o stato cambia colore/semantica.
- Negativi: query vuota, no match, codice lungo/titolo lungo, rete in errore. Fixture prima/dopo danno gli stessi risultati e messaggi.
- Integrazione query reale → dettaglio → back/reload con stato atteso; test search/filter esistenti, confronto payload o risultati verificati. Nessuna scrittura in DB/Qdrant.
- 360/390/768/1440, keyboard/focus/contrasto/overflow ≤1px, TSC/lint/test/build. Dopo release ripetere query e dettaglio sulla revisione servita; controllo comparativo home/Oracle/Studio per assenza di leakage.

## 5. Team

Ruoli e porte da `army-map.md §1bis`; Dux, implementer opzionale, reviewer cross-family, gate fresco fuori catena e release owner. Modello/effort/thread id registrati all'apertura.

## 6. Appetite and stop-loss

3h; deadline UTC al lancio, rinnovo Zero/staff room. Nessun token budget richiesto, subscription. Un implementer, profondità 1, un hop, due rework; child 50 tool call/45 minuti attivi, N=0. Ledger/mailbox come README. Difetto motore scoperto: evidenza e scope separato, nessun refactor opportunistico.

## 7. Evidence and release

Evidence paths reali, fixture/hash e confronto risultati, screenshot, Lighthouse e prove sul commit distribuito. **Bites:** utente che trova il codice e interpreta uno stato senza alterazioni. Dopo W5 e go; nuova PR/worktree. Gate receipt HEAD corrente e release owner autorizzato. Rollback se query, risultato, badge o detail link cambia comportamento. Questa chiusura riguarda soltanto la rifinitura KBLI; le definizioni D-A/D-B sono nel README. Nessun restyle Studio/Oracle è promesso.
