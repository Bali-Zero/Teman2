# Mouth: spec consolidata motori + riuso R19

2026-09-11 · v2 · preparazione delle finestre, nessuna implementazione o release.
Pacchetto autorevole per questa consegna: questo README → spec W0–W7 → fonti
storiche. Riusa le sei window Second Home/Website; aggiunge soltanto **W0 Oracle**
e **W7 identità/chrome**. [Prompt pronti](LAUNCH.md) · [confronto e provenienza](evidence/discussion.md).

## Decisioni e perimetro finale

| Punto | Disposizione |
|---|---|
| Sito | `apps/mouth` unico live. `apps/website` archiviato; solo `git show` dei singoli file. Mai checkout, cherry-pick o applicazione della patch R19. |
| Fonte visuale | R19 integrato **6603d2913ee9b85201c19ef8a0d124bd45f9324e**, Direction A del 09-09: carta #F7F4EE, slate #233D52, copper #A44B36, Fraunces/Manrope. Il precedente strato forest/Georgia resta provenienza, non target indistinto. |
| Roster | Già deciso da Zero: home solo Zainal/Heru; Faysha/Faisha e Sahira escluse dal pubblico. Kadek, Rina e la voce Zero restano come oggi, salvo nuova istruzione. Nessuna cancellazione di record interni o bio/ruolo inventato. |
| Funnel | Oracle conserva canopy/gold, light/dark e quattro stati distinti; Second Home conserva Merah Putih e IDR Cormorant + tabular-nums. Nessun re-skin dei funnel nel pacchetto; atlas Oracle e fork del motore Studio R19 non si importano. |
| Motori, scelta M | Chiesto a Zero se includere entrambi, solo Oracle o solo Studio. La raccomandazione è **entrambi**, ma la risposta non è registrata. W0 è pronta, non implicitamente assegnata. W1/W3 completano il perimetro Studio già richiesto. |
| Identità, scelta D | **D-A consigliata:** R19 Direction A sulle superfici marketing/blog, primario R19 al posto del vincolo di hue rosso, font locali per route. **D-B:** sola composizione con colori/font attuali. Nessuna risposta registrata: W7 resta READY_FOR_RULING; W2/W4/W5 possono procedere nel solo perimetro D-B. |

La scelta D-A sostituisce R4 **soltanto** su home e gruppo blog; lascia invariati
funnel, portal, kita, prime, tax/property tools e KBLI. Il nome della home attuale è
**Rumah Putih + navy + CTA rossa**, non Merah Putih. Questo documento non si
autorizza a prevalere su una ruling owner: il valore D e il messaggio di Zero
devono essere registrati prima di avviare W7. Q1/Q2/Q4 diventano un unico pacchetto
grafico reviewable; Q3 non rimette in discussione le due esclusioni già ordinate.

## Cosa cambia, cosa significa finito

| Superficie | Window | Cambiamento e criterio di chiusura |
|---|---|---|
| Team e fascia founder | W2 | Directory/ritmo R19, esclusioni pubbliche, due founder, link Ari/Surya reali; recensioni e altri profili conservati. |
| Home | W5; W7 se D-A | Gerarchia e spaziature R19 dentro le porte attuali. W7 aggiunge carta/chrome/font/primario Direction A. Ancore, tool, login, CTA e analytics equivalenti. |
| News/Journal | W4; W7 se D-A | Masthead, lead/secondari, ricerca corretta anche con 1–5 hit; Journal punta a `/news`. Articoli ricevuti dal loader attuale, zero nuova pipeline Magazine. |
| Reader, services, contact | Solo W7 se D-A | Chrome, tipografia e accenti della presentazione esistente, con compatibilità delle pagine intere. **Nessuna ricostruzione dei body/MDX o della struttura reader**. Se D-B, restano graficamente invariati: è una scelta di perimetro, non lavoro concluso su di essi. |
| KBLI | W6, go esplicito | Sola introduzione/ritmo locale, sistema dark/Montserrat e semantica invariati. Nessun light re-skin; baseline prestazioni prima del go. |
| Visa Oracle | W0, se M lo include | Motivazioni conosciute EN/ID specifiche, inventario completo, fallback tecnico distinto e smoke del contratto. Non certifica la correttezza legale di tutto il pack né autorizza cambi di stato/mode. |
| Second Home Studio | W1 → W3 | Hygiene tecnica e export verificati; audit/correzione editoriale E33 per il manifest completo. Motore, prezzi, bande, save/share/print conservati. |

**D-A conclusa** richiede W2 + W7 + W4 + W5 sul commit effettivamente servito e
controlli positivi anche su reader/services/contact. **D-B conclusa** significa
solo il riuso compositivo nominato; non “R19 completo”. KBLI è una chiusura separata.
W1 da sola non chiude F7: occorre W3. Day-90, risposte alle lettere, StayGuard,
property module e marketing restano dipendenze esterne secondo il report F7;
nessun dato aggregato, cron 200 o fine budget li chiude. Nessuna promessa di nuove
credenziali, prezzi, recensioni o fatti visa senza fonte verificata.

## Sequenza: due slot, non otto sessioni simultanee

| Slot motori | Slot Website |
|---|---|
| W1 Studio tecnico → W3 Studio editoriale | W2 Team → W7 identità/chrome se D-A → W4 News → W5 Home |
| M=entrambi: W0 prima di W1 o dopo W3; M=solo Oracle: soltanto W0; M=solo Studio: soltanto W1/W3 | W6 KBLI solo dopo W5 e go esplicito; con D-B si salta W7 |

Due nuove window iniziali consigliate: **W1 + W2**, nel perimetro Studio già
richiesto. Se Zero priorizza Oracle e M lo include: **W0 + W2**; W1/W3 seguono
soltanto con M=entrambi. Con M=solo Oracle W1/W3 sono escluse da questo lancio.
Una sorella senza dipendenza
non aspetta l'altra. Ogni cella è una window, un mandato, un organo, un worktree
nuovo da `origin/main` corrente. Dopo arming la branch è read-only; il lotto
successivo non continua a committare lì. Massimo due window operative complessive.

W7 arriva prima dei successivi body work W4/W5: evita due owner contemporanei di
NewsHero, home, CSS e font. Se D-A viene scelta dopo W4/W5, W7 nasce comunque da
base aggiornata e ripete tutti i controlli sui loro consumer. Non usare le vecchie
wave A–D della mappa Fable come un secondo scheduler concorrente.

## Contratti e ownership

`studio-web-contract-v1`, [manifest](evidence/source-manifest.json). Snapshot delle
spec precedenti e patch Studio conservati per hash; il manifest distingue hash di
importazione da hash finale. Mappa Fable e audit Oracle sono copiati in `evidence/`;
sono prove storiche, non test ripetuti in questa consegna. La patch R19 resta
esterna e non si applica. Ogni Dux
congela `contract-lock.json` con le revisioni/fonti/fixture attuali prima di BUILD.

- Studio produce piano/storage `bz_shs_plan_v1` e URL `#p=`; Website consuma solo
  l'ingresso. Resolver prezzi e importi invariati, prezzo assente non diventa zero.
- Oracle produce `Decision` con stato, review reasons, fonti e integrità. W0 è
  proprietaria di copy/inventario/test; emitter/evaluator/schema/pack sono read-only.
  `HUMAN_REVIEW_REQUIRED` vieta `missing_facts` nel modello: non aggiungerli per
  recuperare a forza una domanda. Una modifica di stato/precedenza è un nuovo lotto.
- W1 possiede patch F7, due prezzi Studio, generator/export test e sola riga build
  mouth; W3 eredita generatore e possiede manifest MDX E33 ed export. Nessun lockfile.
- W2 possiede Team/SocialProof; W4 NewsHero/LatestNews/NewsPageClient; W5 li eredita
  dopo integrazione. W7 possiede le sole varianti di identità e i nuovi font; core
  package manifest solo export font. Nessun owner simultaneo di un file condiviso.
- Topic 4 ha ancora una patch locale su `scripts/ci/npm_audit_gate*` nella fonte
  Studio: **W1 adotta quella patch una sola volta**, dopo confronto con il suo owner
  e main; non crea una seconda remediation. Topic 3 possiede Oracle: prima di W0
  confrontare il suo handoff corrente e prendere il mandato o proseguire quello
  già assegnato, mai due window Oracle sugli stessi file.

## Gate comuni

1. Baseline prima del lotto: commit servito `/api/health`, identità delle route,
   font effettivamente caricati, screenshot 360/390/768/1280/1440, navigazione client
   e reload. HTTP 200 con pagina not-found è FAIL. Sitemaps confrontate come insieme
   di URL alla stessa base, non contro conteggi giornalieri hardcoded.
2. Test mirati ai consumer, negativi e integrazione; typecheck/lint/build completi
   dove applicabili. Nuovi codici/route/input non coperti falliscono il controllo.
   Nessuna soppressione di una guardia o fixture di comodo per far passare il tema.
3. Contrasto misurato, focus, Escape/menu, tastiera, reduced motion, target e
   assenza di collisioni/overflow. Nuovi font: budget totale per route **incremento
   ≤120 KB e ciascun subset ≤60 KB**, costo root Inter/Cormorant compreso nel
   baseline; W7 non cambia i preload root. Stessi profili Lighthouse, mediana di
   tre run: nessun aumento CLS e LCP non oltre +5% (tolleranza proposta di test,
   non previsione business); rumore non risolto richiede altra misura, non PASS.
4. Default dei componenti condivisi preservati e provati su `/v2`, reader,
   services/contact, Oracle e Studio; consent, handoff, metadata/noindex, fonti,
   prezzi e analytics preservati. Nessun invio reale di lead per fare una prova.
5. Diff dei path controllata a mano contro la spec; `scope_globs`/change_map non
   sono un write fence. Review indipendente, gate fresco fuori contribution chain,
   ricevuta sul HEAD effettivo della PR. Il confronto Astra è contributo alla spec,
   non il suo gate. `Bites:` identifica il consumer e una prova osservata.
6. Prove su preview e poi sul commit distribuito da un release owner autorizzato.
   Questa consegna è **prepare-only**, non nomina Astra Dux e non autorizza deploy.
   Release/promotion/autopromote si misurano al lancio, non si assume come vigente
   il meccanismo descritto da una vecchia nota. Rollback del singolo lotto secondo
   il percorso di release verificato; mai dati o regole alterati come rollback UI.

## Regole di lancio

Applicare AGENTS, onboarding, skill dell'organ e modus/battle-window-spec. Missione
`SHWEB-20260911`, BLUE default della dottrina, nessun nuovo mandato ORANGE. Ruoli,
modelli e porte dalla tabella `docs/architecture/dual-consul/army-map.md §1bis`.
Registrare nomina, thread/model/effort, SHA, deadline UTC e cap prima di delegare.
Gear 2 minimo (W3 Gear 3; il floor reale può alzarlo), brief presente con percorsi
calcolati da `scripts/ci/evidence_paths.py`, Python di progetto. Nessun budget token
richiesto o nuovo endpoint a pagamento. Tetti delle singole spec sono proposte
operative, non autorizzazione di spesa. Child: un implementer massimo, profondità
1, un hop, 50 tool call/45 minuti attivi, N=0. Due rework per blocco poi checkpoint;
tre rossi della stessa causa sospendono la PR. Mai chiusura per budget esaurito.

Se `scripts/mandate_budget.py` manca nella base corrente, non inventare flag o
enforcement: ledger+supervisore disponibile, limiti e limite tecnico dichiarati.
Checkpoint alla mailbox con hash; consegna file non equivale ad ack (15 minuti
quando destinatario live, un retry). La spec è pronta per il lancio dei lotti già
autorizzati; le sole scelte pendenti M/D restano visibili nei prompt.

## Stato della consegna

PR [#6124](https://github.com/Bali-Zero/Teman2/pull/6124), head `d23454ce…`, verificata
OPEN e auto-merge armato; Harness rosso perché manca brief per churn ≥400. Nessun
rerun o edit del branch armato in questa sessione. Il materiale è utilizzabile come
fonte pinning sul commit, ma non va descritto come già su main.

**Nessun codice applicativo modificato e nessun rilascio eseguito dalla presente
consegna. La futura non regressione si attesta solo dopo i gate per il lotto:
spec, test precedenti e HTTP 200 da soli non sono una conferma di funzionalità.**
