---
date: 2026-09-11
domain: visa
client_case: none (technical hygiene of the E33 Second Home Studio and its llms exports)
adversarial_review: codex
sources:
  - https://github.com/advisories/GHSA-frvp-7c67-39w9
  - https://github.com/advisories/GHSA-9mqv-5hh9-4cgg
  - https://github.com/advisories/GHSA-c96f-x56v-gq3h
  - https://github.com/advisories/GHSA-5p4m-2wfm-xmqj
  - https://github.com/Bali-Zero/Teman2/actions/runs/34423820190
  - https://balizero.com/llms-full.txt
  - https://balizero.com/llms-id.txt
---

# Second Home Studio — F7 e prerequisiti, 11 settembre 2026

Passata tecnica preparata su Mini, base `be45266252`, branch
`agent/mini-pro2/mouth/secondhome-f7-20260911`. Pro/Mini raggiungibili e
sincronizzati al controllo iniziale. Prodotto esistente, nome ufficiale invariato.
Le modifiche di questa passata sono locali: nessuna chiusura SHIPPED è implicita.

## Traguardo proposto a Zero

Chiudere l'hygiene tecnica F7 con verifica dei consumer e conservare un elenco
editoriale verificabile. F7 complessiva resta aperta finché la riscrittura
editoriale non è completata. La domanda distinta/R19 è stata posta esplicitamente
a Zero e resta senza risposta in questa passata; nessun allineamento R19 eseguito.
Il vincolo Cormorant + tabular-nums per gli importi IDR è applicato ai due prezzi
dello Studio, principale e anteprima, conservando il font serif esistente.

| Fase | Stato verificato / preparato | Criterio di chiusura |
| --- | --- | --- |
| F4b Day-90 | SUSPENDED. Prod: 2 casi, uno `fit_memo`, uno `status_change`; 0 negli stadi dello scanner. Switch assente. | Caso reale in uno stadio letto dallo scanner, attivazione autorizzata e prova di una vera riga alert; conteggio totale o cron verde non bastano. |
| F5 letter-reply | SUSPENDED. Il tracker contiene ancora 16 righe pending; nessuna risposta registrata nel percorso repo. Non è stata verificata una casella di posta né l'archivio fisico. | Risposta scritta acquisita, fatti promossi con fonte/data e propagazione verificata sulle superfici indicate. |
| F6 commerciale | Dependent e senior pricing chiusi dalle ruling già registrate. StayGuard dipende da F4b; property module dipende da `property_validation_standard`. | StayGuard dopo prova Day-90; property module dopo standard ricevuto. Nessun nuovo prezzo o lancio deciso. |
| F7 gitignore | CLOSED, già presente su main dal 25 luglio. | `git check-ignore -v .husky/_` identifica `.gitignore:942`. Nessuna duplicazione della regola. |
| F7 waiver npm | PREPARED: ritirate tutte e quattro le eccezioni obsolete. | Gate senza standing waiver; una loro reintroduzione viene segnalata. Le nuove advisory rimangono visibili. |
| F7 llms | PREPARED: il build rigenera EN, ID e freshness di `llms.txt`; il corpus KBLI resta fuori da questo comando. | Dopo release, entrambi gli export serviti devono coincidere con le fonti della release, esclusa la data di generazione. |
| F7 editoriale | OPEN. Censimento attuale sotto; nessuna riscrittura o rimozione eseguita. | Revisionare ogni famiglia e tutte le traduzioni contro la fact registry; eliminare le affermazioni obsolete, verificare pagine ed export. Il solo noIndex non chiude il lavoro. |
| F8 marketing | `operator[business]`. | Decisione esplicita di Zero sui materiali/canali; nessun invio o pubblicazione in questa passata. |

## Prove F4b e F5

Read-only via Pro, `scripts/pg.sh`, database `nuzantara_rag`, ruolo
`nuzantara_readonly`. Nessun dato cliente identificativo letto nell'output.

```sql
SELECT count(*) FROM e33_cases;
-- 2
SELECT stage, count(*) FROM e33_cases GROUP BY stage ORDER BY stage;
-- fit_memo | 1
-- status_change | 1
SELECT count(*) FROM e33_cases
WHERE stage IN ('itas_active', 'guarantee_proof_due', 'annual_maintenance');
-- 0
SELECT key, value FROM system_settings
WHERE key = 'e33_guarantee_scan_enabled';
-- 0 rows
```

Gli stadi sono quelli della query reale in
`apps/backend-rag/backend/services/crm/e33_case_repository.py`, `list_open_guarantee_cases`.
Non è stato inferito che i due casi siano reali o sintetici: non soddisfano il
prerequisito di stadio in nessuno dei due casi.

Ultimo run disponibile al controllo:
[cron 34423820190, 10 settembre 01:02:19 UTC](https://github.com/Bali-Zero/Teman2/actions/runs/34423820190),
conclusion success, HTTP 200; il body letto tramite `gh run view --log` è:

```json
{"service":"e33_guarantee_scan","status":"blocked","switch_state":"unprovisioned","reason":"switch_not_provisioned"}
```

La registry ha **34 fatti: 7 confirmed, 18 pending, 8 unknown, 1 disputed**.
Il vecchio totale 33 nel corner è superato; le 16 righe pending del tracker
lettere sono un conteggio diverso, non il totale dei fatti pending.

## Waiver: patch già nel lockfile

Confrontati `package-lock.json`, npm audit attuale e gli advisory upstream:

| Eccezione ritirata | Versione nel lock | Prima versione corretta del ramo |
| --- | --- | --- |
| [Hono path traversal](https://github.com/advisories/GHSA-frvp-7c67-39w9) | `@hono/node-server` 2.0.11 | 2.0.5 |
| [Hono WebSocket](https://github.com/advisories/GHSA-9mqv-5hh9-4cgg) | `@hono/node-server` 2.0.11 | 2.0.10 |
| [find-my-way HTTP2](https://github.com/advisories/GHSA-c96f-x56v-gq3h) | 9.7.0 | 9.7.0 |
| [js-yaml omap](https://github.com/advisories/GHSA-5p4m-2wfm-xmqj) | 3.15.1 sotto gray-matter; 4.3.1 al root | 3.15.1 / 4.3.1 |

Nessun aggiornamento di dipendenze o override 3.x → 4.x introdotto.
`npm audit --audit-level=high --omit=dev --json` sull'intero workspace rileva
ancora **3 package high, 1 moderate, 0 critical**. Non sono le vecchie waiver:
`js-yaml` GHSA-2883-xcg3-v3hh, `mysql2` GHSA-3f6p-5ww8-9rcr e
GHSA-rgwj-5xj2-c3m3, `sharp` GHSA-rgj7-g3m4-5g8c; `prisma` è il carrier
moderate. Questa passata non certifica il workspace come privo di advisory né
attribuisce queste dipendenze al runtime dello Studio. Serve una passata dedicata
al lockfile e alla raggiungibilità, senza estendere le vecchie autorizzazioni.
Il gate reale è stato eseguito sul JSON dell'audit: **exit 1**, con questi tre
package high ancora segnalati. I flag coincidono con `.github/workflows/tests.yml`
(`npm audit --audit-level=high --omit=dev --json`); il workflow tratta l'exit 1
come advisory non bloccante. I 19 unit test verdi non sono un audit pulito.

## Export: misura e correzione

Scaricati da `https://balizero.com/llms.txt`, `/llms-full.txt`, `/llms-id.txt`,
tutti HTTP 200. Eseguito il generatore reale in una directory temporanea con
le sorgenti del worktree, senza scrivere nel checkout principale.

| Export | Live | Rigenerato dalla base verificata |
| --- | --- | --- |
| `llms-full.txt` | 2.552 record, 25.522.700 byte | Uguale ignorando la sola riga data |
| `llms-id.txt` | 785 record, 6.327.315 byte | 799 record, 6.476.339 byte; differente |

Il vecchio build usava `LLMS_GENERATE_FULL_ONLY=1`, il cui return precede ID e
freshness. Ora usa `LLMS_GENERATE_ARTICLES_ONLY=1`, che esegue entrambi gli
export e la freshness ma salta KBLI. Il vecchio flag conserva il comportamento
per eventuali chiamanti esterni. Gli artefatti tracciati non vengono riscritti
in questa patch: la generazione avviene nel build, come già per EN.

Il test esegue lo script vero contro una fixture di articoli EN/ID, bozze,
noIndex e output vecchi. Usa il flag estratto dal comando build reale e un
input KBLI volutamente invalido per verificare che non sia elaborato.
Ripristinare il vecchio flag fa fallire il test su `stale ID export`.

Eseguito anche il primo comando esatto di `npm run build` nel worktree reale:
exit 0; `git status` mostra modificati solo i tre export editoriali tra i file
pubblici controllati, KBLI invariato. Poi ripristinati i tre file dai byte salvati
prima della prova. Non è stato eseguito `next build`.

La prova sul corpus reale ha trovato quattro copie dello stesso URL nella
freshness, prodotte dalle traduzioni. Corretto selezionando i soli file canonici
con `publicSlug()`; i contenuti multilingua restano negli export. Il test include
una traduzione FR: presente nel corpus, assente dalla freshness, URL canonico
presente una volta. La rigenerazione finale produce questi cinque slug distinti,
tutti con data sorgente 2026-09-04, sotto `https://balizero.com/business/`:

```text
balis-r600k-dream-homes-what-the-leasehold-fine-print-really-means
balis-sub-50k-villa-boom-accessible-luxury-or-due-diligence-trap
indonesia-mandates-full-digital-filing-for-pt-and-foundation-announcements
indonesias-2026-oss-portal-makes-nib-registration-fully-digital
indonesias-kbli-2025-shake-up-the-transition-rules-every-business-must-know
```

## Importi IDR

Nel codice Studio i due importi dinamici sono `{price}` in `StudioApp.tsx` e
`{previewPrice}` in `ScenarioToggle.tsx`. Entrambi mantengono `--font-serif` e
ora dichiarano `fontVariantNumeric: "tabular-nums"`. Il binding viene da
`apps/mouth/src/app/layout.tsx:193`, tramite il font locale
`packages/core/fonts/cormorant.ts`.

Prova browser anonima in produzione, su un elemento temporaneo nello scope
Studio con le proprietà della patch: dopo `document.fonts.load`, la faccia
`cormorant` è `loaded`, il valore numerico è `tabular-nums` e tutte le dieci
sequenze `0000000000` … `9999999999` misurano **157,125 px** a 32 px.
Questo verifica il font e il supporto alle cifre tabulari; non pretende che le
due nuove proprietà siano già distribuite sui prezzi reali.

## Censimento editoriale attuale

Metodo: selezione delle famiglie con `E33[A-Z]?` o `second[\s-]+home` nelle
fonti, inclusione delle traduzioni sorelle, parsing del frontmatter. Trovati
125 famiglie / 532 file; **19 file noIndex in 7 famiglie**, EN 7, ID 4, IT 4,
FR 2, RU 2. Questo perimetro lessicale non è una certificazione legale degli
altri file e non dimostra perché il vecchio elenco 31/13 si sia ridotto.

| Slug | File noIndex attuali |
| --- | --- |
| `freelancing-legally-indonesia` | en |
| `indonesia-second-home-visa-2026-what-wealthy-expats-need-to-know-now` | en, id, it, fr, ru |
| `indonesias-second-home-visa-kitas-e33-the-complete-2025-framework` | en, id, it |
| `indonesias-second-home-visa-the-5-year-and-10-year-kitas-fully-decoded` | en, id, it |
| `live-long-term-in-indonesia-second-home-golden-visa-pnb-immigration-law-firm` | en, id, it, fr, ru |
| `education-expat-children` | en |
| `living-in-bali-honest-guide` | en |

**Correzione dopo confronto Astra, 11 settembre 02:10 WITA:** il precedente
controllo su `/blog/<slug>` era invalido come prova degli articoli. `blog` non è
una categoria pubblica valida: la route restituisce "Page not found" con HTTP
200 e robots noindex. Il controllo negativo lo riproduce; non va contato come
contenuto verificato. Le categorie canoniche derivano da
`src/lib/blog/categories.ts` (`immigration` → `visas`, `digital-nomad` e
`lifestyle` → `living`).

Ripetuta la verifica sulle **19 URL canoniche/localizzate** dei file noIndex,
usando `?lang=` per le traduzioni: tutte HTTP 200, titolo/H1 dell'articolo,
canonical alla URL di base, robots `noindex, nofollow`, nessuna pagina not-found.
I sette slug sono assenti dalla sitemap pubblica letta in questa prova. Le
traduzioni delle tre famiglie con solo EN noIndex non portano lo stesso flag:
vanno incluse nella revisione editoriale, non cancellate automaticamente. Questa
prova non certifica gli altri 513 file né l'assenza di affermazioni obsolete
indicizzabili. Il JSON e il probe riproducibile sono nel pacchetto finale
`docs/plans/studio-engine-design-20260911/evidence/`.

La famiglia `indonesias-second-home-visa-the-5-year-and-10-year-kitas-fully-decoded`
contiene ancora la classificazione deposito/property come E33B/E33A nelle tre
lingue: esempio concreto del lavoro aperto, da confrontare con la registry.
La ratchet esistente passa con 268 match in 106 file: sono match lessicali
baselinati, non 268 errori legali confermati né una garanzia di correttezza.

## Verifica locale

- Suite Second Home: **29 file, 534 test passati**, cwd del worktree verificato.
- Gate npm: **19 test passati**; il test delle quattro vecchie eccezioni ora
  richiede il rifiuto se gli advisory ricompaiono.
- Export articoli: **1 test passato**, mutazione del vecchio flag respinta.
- Corpus KBLI: **17 test passati**.
- Dopo le due proprietà tabular-nums: StudioApp + ScenarioToggle,
  **45 test passati** (sottoinsieme dei 534, non conteggio aggiuntivo).
- Ripetuta poi l'intera selezione Second Home + export + KBLI:
  **31 file / 552 test passati**. Dopo la correzione freshness, ripetuti i due
  file interessati export/KBLI: **18 test passati**.
- ESLint dei due componenti: 0 errori. Il nuovo test è escluso dalla configurazione
  ESLint del progetto; eseguito con Vitest e formattato con Prettier.
- TypeScript dell'app: `tsc --noEmit --incremental false`, exit 0, nessuna
  diagnostica. `git diff --check` pulito; checkout principale ancora pulito.
- Review indipendente Claude Opus 5 sul pacchetto di sorgenti: primo passaggio
  senza blocker certi, condizionato alle prove sul corpus reale e sul gate npm;
  prove aggiunte sopra. Il delta finale freshness ha ricevuto **LGTM** in una
  seconda review indipendente. È review del codice fornito, non un gate di
  rilascio né una verifica di produzione compiuta dal reviewer.

Build Next completo, deploy e prova post-release dei nuovi export non eseguiti.
Il contratto external-agent in `AGENTS.md` consente la preparazione, non merge,
arming o deploy da questa sessione. Le prove live sopra fotografano la produzione
prima di questa patch.

## Adversarial review

Aggiunta all'adozione in W1-SH-TECH (SHWEB-20260911, 2026-09-11); il corpo sopra è
invariato rispetto alla patch congelata (sha256 `e3004f3d…`). Nessuno dei due seat ha
scritto la patch (autrice Astra) né il brief del Dux.

- **Codex Sol** (`gpt-5.6-sol` xhigh, `codex exec --sandbox read-only`, sessione
  `01a0902a-8855-7ed0-a01b-940ce3a9bcf2`): GO-WITH-CONDITIONS. Ha confermato nel
  `package-lock.json` le versioni dietro le quattro waiver ritirate (`@hono/node-server`
  2.0.11, `find-my-way` 9.7.0, `js-yaml` 3.15.1 annidato e 4.3.1 al root) contro i range
  corretti degli advisory. Obiezione principale accettata: i due advisory Hono sono
  Moderate a monte e il gate ignora Moderate per costruzione, quindi il test storico prova
  che la waiver non esiste più, non che una reintroduzione Moderate reale blocchi; il test
  è stato rinominato di conseguenza. Non ha potuto eseguire `npm audit` (registry non
  raggiungibile dalla sandbox).
- **Kimi K3** (`kimi-code/k3`, sessione `session_a41ccd47-d2cc-4d4b-86a5-f327daedfd05`):
  HOLDS-WITH-CONDITIONS. Ha eseguito mutazioni sul gate: ripristinare una qualsiasi delle
  quattro waiver fa diventare rosso il test storico; 19/19 verdi con `WAIVE` vuoto.
  Obiezione accettata: il test sul percorso non verificato ora blocca come "not waived" e
  non più attraverso il ramo di path-scoping, che resta coperto dai test con waiver di
  fixture; rinominato. Obiezione respinta per W1: un vincolo che impedisca per test ogni
  futura waiver è una scelta di policy fuori mandato.

Le tre advisory high più recenti (`js-yaml`, `sharp`, `mysql2` via `prisma`) restano
segnalate e non coperte da waiver: questa revisione non certifica il workspace privo di
advisory.
