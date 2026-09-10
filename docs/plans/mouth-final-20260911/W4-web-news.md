# W4 — Website: News / composizione Journal

## 1. Mandate

`SHWEB-20260911 / W4-WEB-NEWS` · BLUE default · organ discovery articoli · Gear 2 minimo. Mini; nuovo worktree `~/nuzantara/.worktrees/mouth-shweb-w4-news-20260911`, task id `shweb-w4-news-20260911`, base `origin/main` con W2 integrata e SHA registrato. Se D-A già scelta, attendere anche W7; consumarne i token senza riscriverli. Con D-B preservare identità corrente. Successo: pagina editoriale leggibile e ricerca che mostra gli articoli attesi.

## 2. Owned perimeter

Dentro mouth: `src/app/(blog)/NewsPageClient.tsx`, `src/app/v2/_components/NewsHero.tsx`, `LatestNews.tsx`; nuovi `NewsPageClient.module.css`/`.test.tsx` colocati e moduli/test omonimi dei due componenti; `e2e/shweb-news.spec.ts`. Varianti opt-in mantengono il default dei consumer non assegnati.

Vietati: MDX/export, ArticleClient, loader/tipi/categorie/sitemap, Footer/layout/globals/NavShell, font/theme/i18n/proxy, package/lock, Team, KBLI, Oracle/Studio. W3 possiede contenuti; W5 eredita LatestNews/NewsHero dopo W4. Scope check manuale.

## 3. Sibling contract

`studio-web-contract-v1`, hash di ArticleListItem/categorie e fixture 0/1/5/N articoli congelati prima di BUILD. `q`, categoria, lingua e slug esistenti conservati. Destinazione canonica `/news`; “Journal” può essere un'etichetta, non un link a `/journal` inesistente. Metadata e reader consumati senza riscriverli. Stato vuoto esplicito; cover fallback esistente; niente slug o dati editoriali costruiti a mano.

## 4. Acceptance

- Masthead, gerarchia e filetti R19 con token ospitanti. Ogni risultato atteso visibile esattamente nel flusso previsto, senza buchi tra hero e grid.
- Negativi: zero risultati, **1–5 hit**, N hit/paginazione, cover mancante, titolo lungo. Riprodurre prima il difetto `filtered.slice(5,17)` + hero non filtrato; test con prima hit e quinta hit impedisce la regressione.
- Integrazione `/news?q=…&category=…` → articolo vero → lingua disponibile → back/reload con ricerca conservata. Home/LatestNews e `/v2` mantengono il loro comportamento. Nessun cambio di API o ingest.
- Screenshot 360/390/768/1440, immagini decodificate, tastiera/focus, overflow ≤1px, contrasto; TSC/lint/test/build. Dopo release verificare la revisione servita e ripetere ricerca piccola e articolo reale: HTTP 200 non basta.

## 5. Team

Dux/implementer/reviewer cross-family/gate fresco/release owner da `army-map.md §1bis`; registrare modello, effort e thread id reali. Review di proposta e candidato, gate fuori catena.

## 6. Appetite and stop-loss

5h; deadline UTC al lancio, rinnovo Zero/staff room. Nessun token budget richiesto, subscription. Un implementer, profondità 1, un hop, due rework; child 50 tool call/45 minuti attivi, N=0. Max due window totali, mailbox/ledger/ack come README. Se serve riscrivere la pipeline articoli, checkpoint con scope delta.

## 7. Evidence and release

Evidence paths reali, fixture congelate, prova difetto prima/dopo, browser e revisione live. **Bites:** lettore che cerca e apre una notizia. W2 → W4 → W5, W3 parallela a contratto invariato. Gate receipt HEAD corrente e release owner autorizzato. Rollback se ricerca omette hit, locale/link errato, vuoto opaco o regressione Home/v2.
