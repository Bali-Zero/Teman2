# W3 — Second Home: archivio e AI export

## 1. Mandate

`SHWEB-20260911 / W3-SH-EDITORIAL` · BLUE default · organ pubblicazione E33 · Gear 3 per contenuto normativo pubblico. Mini; nuovo worktree `~/nuzantara/.worktrees/mouth-shweb-w3-editorial-20260911`, task id `shweb-w3-editorial-20260911`; branch e SHA corrente registrati **dopo W1 integrata**. Successo: fonti, pagine e corpus AI del perimetro concordano sui fatti verificati, con incertezze conservate.

## 2. Owned perimeter

`apps/mouth/src/content/articles/**/*.mdx` limitatamente alle famiglie del manifest E33 da congelare; `public/llms.txt`, `llms-full.txt`, `llms-id.txt`; generatore/test export ereditati da W1 solo per difetti scoperti; `research/secondhome/` ledger editoriale e `.agents/skills/secondhome/SKILL.md`. Scrivere prima `editorial-disposition.json` con path, famiglia, lingua, claim/fact-id, stato/source/date e azione; quello è l'elenco effettivo delle fonti writable.

Vietati: mutazioni fact registry/letter tracker senza nuova fonte ammessa, prezzi, backend/DB, lock/manifest, componenti WEB, ArticleClient, tipi/loader/categorie/sitemap globali. Nessun bulk delete di articoli. Nuovo difetto infrastrutturale → scope delta, non allargamento tacito. W4 modifica la presentazione, non i testi.

## 3. Sibling contract

`studio-web-contract-v1`; hash registry, categorie, tipi e corpus congelati prima di BUILD. Ricalcolare il censimento: baseline 125 famiglie/532 file, 19 noIndex/7 famiglie. Revisionare anche gli indicizzabili e le traduzioni sorelle, ampliare il manifest se emergono altri claim E33 correlati. `ArticleListItem`, URL canonica e `?lang=` restano compatibili con WEB. Draft/noIndex esclusi dagli export; contenuto mancante resta stato esplicito. Nessuna promozione di pending/unknown/disputed a confirmed per eliminare un disclaimer.

## 4. Acceptance

- Ogni famiglia ha una disposizione motivata; ogni affermazione sospetta ha esito con fonte e data. Riscrivere le affermazioni obsolete confermate, inclusi metadata/snippet/FAQ e traduzioni; non limitarsi al flag noIndex. Verifica normativa su fonti primarie attuali quando necessaria; PricingTool per i prezzi, mai importi inventati o copia di vecchi listini.
- Distinguere appartenenza E33G alla famiglia Second Home dalla falsa equivalenza col prodotto HNW. Non dichiarare errate righe short LLMS che distinguono già remote/retirement: correggere l'aggregazione ambigua e dettagli effettivamente superati. NoIndex rimosso soltanto a contenuto revisionato e con disposizione SEO esplicita nel ledger, mai in massa per gonfiare la chiusura.
- Negativi: claim obsoleto in una traduzione indicizzabile intercettato; `/blog/<slug>` 200 not-found non supera la prova; pending resta pending. Ratchet esistente utile ma non equivale a audit legale.
- Integrazione: build reale, EN/ID rigenerati, freshness canonica senza duplicati, KBLI invariato; campioni e diff semantico provano che il claim eliminato non riappare nel corpus. URL canoniche e tutte le lingue modificate: articolo identificabile, robots, canonical, sitemap e link da `/news` coerenti.
- Dopo release controllare sorgente di release → pagina → entrambi gli export serviti. Contenuti ancora bloccati da lettere sono elencati e mantengono F7 aperta se necessari alla chiusura; nessun verdetto «tutto corretto» basato sul solo conteggio noIndex.

## 5. Team

Incarichi da `army-map.md §1bis`; reviewer qualificato su contenuto normativo e di famiglia diversa dal builder, gate fresco indipendente, release owner nominato. Gear 3: Evidence Pack e altri gate vigenti. Registrare modelli/effort/thread effettivi; nessuna nuova risposta ufficiale può essere inventata dal team.

## 6. Appetite and stop-loss

8h; deadline assoluta al lancio, rinnovo Zero/staff room. Token non richiesti, subscription; un implementer massimo, profondità 1 e un hop. Due rework per blocco; child 50 tool call/45 minuti attivi, N=0. Ledger/mailbox come README. Se il censimento eccede il tetto, checkpoint con famiglie completate/restanti e fonti mancanti; niente chiusura F7 per esaurimento budget.

## 7. Evidence and release

Evidence paths calcolati, manifest completo, claim matrix, fonti primarie, diff, corpus generati e prove canoniche/locali/live. **Bites:** lettore di archivio e AI crawler che citano E33. W1 → W3; W4 parallela solo con contratto fermo. Gate sul HEAD corrente, poi release owner autorizzato. Rollback per nuova affermazione falsa, traduzione divergente o export desincronizzato; riaprire la riga editoriale invece di cancellarne la prova.
