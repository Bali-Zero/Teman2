---
date: 2026-08-27
domain: design
client_case: none
sources:
  - live DOM measurement (Playwright/Chrome, 2026-08-27 01:08 WITA) of balizero.com, /visa, /visa/match, /visa-oracle, /kbli, kita/my/prime/zantara subdomains — script `capture_live.mjs` (session scratchpad), output `measure.json`
  - packages/core/tokens/{primitives,semantic,index}.css + themes/editorial.css (repo, origin/main fa6fbcc53)
  - apps/mouth/src/app/(visa-oracle)/visa-oracle/oracle.css (1620 lines)
  - apps/mouth/src/lib/theme/rumahVars.ts · apps/mouth/src/app/v2/_components/{HeroBlueprint,PersonaDoors}.tsx · apps/mouth/src/app/(marketing)/FunnelCTAs.tsx
  - apps/mouth/src/app/visa/layout.tsx · apps/mouth/src/app/visa/voa/page.tsx · packages/core/components/apps/{AppFrame,AppWizard,AppTrustStrip}.tsx
  - skills/bali-zero-brand/{tokens.json,SKILL.md,surfaces/email-template.md} · docs/design/2026-07-19-garuda-os-unified-surfaces/PLAN.md · docs/X_BRAND_VOICE.md
  - artifact «Funnel GARUDA & Visa Oracle» (2026-08-26, 20 screenshots recovered from its data-URIs — source JPEGs no longer on disk)
adversarial_review: kimi
mandate: DESIGN STUDY LOOP — R0 (Zero, 2026-08-27)
---

# R0 — Censimento delle superfici pubbliche e design system *di fatto*

> **Round 0 del Design Study Loop.** Inventario + misura. **Nessun giudizio estetico in questo documento**: ogni riga è un fatto misurato dal DOM vivo, dal CSS su disco o da una schermata. Le opinioni iniziano in R1.

## UNKNOWNS (dichiarati in testa, non in coda)

1. **Schermate non raggiunte** al momento della stesura: checkout / upload / tracking di GARUDA e il Verdetto finale di Visa Oracle. Una lane di cattura locale è in corso (build da `origin/main`, flag accesi solo in locale, dati sintetici); il documento sarà aggiornato con l'esito o con la dichiarazione di irraggiungibilità e la causa esatta.
2. **Email Brevo**: su disco esiste solo la *spec* (`skills/bali-zero-brand/surfaces/email-template.md`, «pending first production email»). Nessun template HTML effettivamente inviato è stato trovato nel repo (`find … -iname '*.html' -path '*email*'` = 0). Cosa riceve oggi un cliente per email **non è misurato**.
3. **Carousel IG WR2 recenti**: `apps/war-room/output/carousel` è vuoto sul Pro; l'unico corpus su disco sono i 64 carousel importati il 2026-05-08 (`skills/bali-zero-brand/past/`). L'identità IG è quindi misurata dai token del brand-skill + 3 copertine di maggio, non dalle uscite delle ultime settimane.
4. **Taglio esatto del serif**: il token dichiara `"Cormorant Garamond"` (primitives.css:62) ma `next/font` carica una famiglia risolta come `cormorant` (DOM). Quale cut sia effettivamente servito (Cormorant vs Cormorant Garamond) non è stato verificato sul file font.
5. **Stato del secondo SSOT di token** citato dal piano GARUDA OS (`packages/design-system/tokens/bz-tokens.css`): la directory `tokens/` non esiste più in `packages/design-system` (oggi: `brand-api/`, `README.md`). Se sia stata fusa in `packages/core` o semplicemente rimossa non è stato tracciato qui.
6. Le catture sono **headless, senza login**: kita/knowledge/zantara sono misurate sulla sola pagina di login; my.balizero.com sulla pagina `login-upgraded` (redirect osservato).

## 1. Metodo

- **Live**: 9 URL × 2 viewport (1280×900, 390×844), `networkidle`, screenshot full-page, poi `getComputedStyle` su ≤2500 elementi visibili: famiglia font dei nodi-foglia con testo, colori di testo/sfondo, raggi, peso, `h1`, prima CTA piena, `data-theme`, `meta robots`, valore risolto di 7 custom property.
- **Disco**: token e temi di `@balizero/core`, `oracle.css`, `rumahVars.ts`, componenti dei funnel, brand-skill IG/email, piano GARUDA OS.
- **Galleria 26-27/8** (20 schermate dei due funnel in build locale con flag accesi): i JPEG originali erano spariti dal disco; sono stati **recuperati dai data-URI dell'artifact** (`757f82b9…`), quindi sono byte-identici a quelli visti da Zero.
- Nessun dato cliente in nessuna cattura (pagine pubbliche, form vuoti, dati sintetici).

## 2. Inventario delle superfici (misurato 2026-08-27)

| Superficie | URL finale | HTTP | robots | `data-theme` | Sfondo (body misurato → superficie di pagina) | Font corpo (nodi-foglia) | `h1` | CTA primaria |
|---|---|---|---|---|---|---|---|---|
| **Home** | `balizero.com/` | 200 | index,follow | `editorial` | body `#1d273b`; sezioni carta `#f7f6f2` (Rumah Putih) su hero navy `#1e3863` | Inter ×146, Cormorant ×12 | Cormorant 53.8px w600, bianco, tracking −0.54px | prima CTA piena misurata = pillola nav «Get Started via WhatsApp» **verde `#25d366`**, radius 12 (nel hero c'è anche «Chat with us» rosso, non prima nell'ordine DOM) |
| **Visa v1** (funnel vecchio, PUBBLICO) | `balizero.com/visa` | 200 | **index,follow** | `editorial` | navy `#1e3863` (gradiente) + foto risaie in trasparenza | **Montserrat ×21** (da `visa/layout.tsx`), Cormorant ×1 | Cormorant 41.6px w400 «24 visa types. One fits you.» | card ghost bianco 5.5%, radius 4; rosso `#ff3344` presente ×1, blu `#3a6dff` ×1, rame `#d4845a` ×1 |
| **Visa Match** (v1, 4 domande) | `balizero.com/visa/match` | 200 | index,follow | `editorial` | navy | Montserrat ×16 | Cormorant 41.6px «Visa Match» | rosso `#ff3344` ×2 |
| **Visa Oracle v2** (flagship, SHADOW) | `balizero.com/visa-oracle` | 200 | **noindex,nofollow** | `editorial` (ma **scoped**: `.oracle-root` ignora il tema globale) | body `#1d273b` → `.oracle-root` crema `#f7f5ef`, elevato `#fff` | Inter ×18, Cormorant ×1 | Cormorant 44px w500 «A map, not an application», inchiostro verde `#16231c` | «Start» = pillola **bianca** con inchiostro `#16231c`, radius 20 (il canopy `#1f4d3d` compare come sfondo di un elemento separato) |
| **GARUDA VOA** (dark, flag OFF in prod → 404) | `/visa/voa` (galleria locale) | — | noindex (layout) | `editorial` + `data-funnel="visa"` | navy `#1e3863` con card sfondo 5.5% | Montserrat (ereditato da `visa/layout.tsx`); etichette `var(--font-serif)` | Cormorant «Visa on Arrival» | «Next» / «See result» **rosso `#ff3344`**, radius 4; hairline progresso rosso |
| **KBLI** | `balizero.com/kbli` | 200 | index,follow | `editorial` | navy | **Montserrat ×111** | Cormorant 72px «KBLI 2025» | ghost bianco 6%, testo **rame `#d4845a` ×23** |
| **kita** (workspace) | `kita.balizero.com/login` | 200 | index,follow | `operative-light` | avorio `#f8f6f2`; card login **nera `#131315`** | Inter ×5, IBM Plex Mono ×2 | — | «Authenticate» 12px bold, radius **0** |
| **my** (portale clienti) | `my.balizero.com/portal/login-upgraded` | 200 | noindex | `operative-light` | carta `#f4f1ea`, illustrazione tempio + luna | Cormorant ×4, Inter ×2 | Cormorant **42px w300 MAIUSCOLO** tracking +2.5px, **rame `#9d5230`** | «Pass the Portal →» rame `#9d5230`, radius 12 |
| **prime** (mappa 3D) | `prime.balizero.com/?layers=zoneColors` | 200 | noindex | `operative-dark` | body `#1d273b` → app `#121016` | Inter ×21 | — | rame `#d4845a` come accento |
| **zantara** (chat) | `zantara.balizero.com/login` | 200 | index,follow | `operative-light` | carta `#f4f1ea`, card nera | Inter, IBM Plex Mono | — | identica a kita |
| **knowledge** (da `curl`) | → `kita.balizero.com/login?redirect=…` | 307 | — | — | (= kita) | | | |
| **IG carousel WR2** | brand-skill + 64 `past/` | — | — | — | antracite `#373D42` / nero, foto full-bleed | **Montserrat 700/800 MAIUSCOLO** | 84px cover | giallo `#F4C430` per dati, rosso `#C8102E` logo/status |
| **Email Brevo** | spec only | — | — | — | (eredita palette IG) | Montserrat, Title Case, 600px | H1 28px | — |

Note di misura (da `curl`, non da `measure.json`): `visa.balizero.com` → 302 → `balizero.com/visa` (la home in `FunnelCTAs.tsx` punta ancora al sottodominio); `tax.balizero.com` → 200 (non catturato, fuori perimetro del mandato).

## 3. I sei sistemi di design che coesistono (misurati, non dedotti)

| # | Sistema | Dove vive | Palette (esatta) | Tipografia | Owner/data |
|---|---|---|---|---|---|
| S1 | **Core «editorial»** (default balizero.com) | `packages/core/tokens/themes/editorial.css` | navy gradiente `#24406e→#1e3863→#1a3258`, accento **blu McKinsey `#3a6dff`**; override `[data-funnel=visa]` → rosso `#ff3344` (il testo-accento è `#ff7a88`, 4.66:1 su navy — editorial.css:54-58) | Inter / Cormorant Garamond / IBM Plex Mono (`primitives.css:61-64`) | 2026-04-17 → 06-11 |
| S2 | **Rumah Putih** (home + blog) | `rumahVars.ts` + `.rumah-putih` in `globals.css` | carta `#f7f6f2`, inchiostro `#16213a`, inchiostro-soft `#475372`, navy `#1e3863`, hairline `#e3e1da`, CTA rosso **scurito `#D01033`** (AA su bianco) | Cormorant titoli / Inter utility; «no red anywhere in this section» (PersonaDoors) | MYTHOS 2026-06-11 → 08-11 |
| S3 | **Oracle** (Visa Oracle v2, scoped) | `oracle.css` (1620 righe, 67 occorrenze hex / 29 uniche, tier `--oracle-*`) | crema `#f7f5ef`, inchiostro `#16231c`, **canopy verde `#1f4d3d`**, ramo `#6b7a5e`, oro `#a8791f`; 4 stati: eligible `#16683f` / likely `#2a6f97` / conditional `#7a5209` / likely-not `#a83a44`; dark: `#0a100d` + `#8fe0b8` | Inter + Cormorant (h1) | 2026-07-17 → 08-23 |
| S4 | **Operative** (kita/my/prime/zantara) + piano **GARUDA OS** «copper/anthracite» | `operative.css`, `themes/operative-{light,dark}.css`, `docs/design/…/PLAN.md` (PR #2850) | avorio `#f8f6f2` (kita) / carta `#f4f1ea` (my) / `#121016` (prime); **rame `#9d5230` / `#d4845a`**; card login nere `#131315` | Inter; my: Cormorant maiuscolo w300; kita: IBM Plex Mono | Kimi 2026-07-19 (esclude esplicitamente `/visa-oracle` e marketing) |
| S5 | **Brand IG/editoriale** (WR2) | `skills/bali-zero-brand/tokens.json` + constitution | antracite `#373D42`, nero, bianco, **giallo `#F4C430`**, **rosso `#C8102E`**; «NEVER green, blue, purple, pastel, beige» | **Montserrat 700/800, titoli MAIUSCOLI**, tracking 0.02em | 2026-05-08, 64 carousel |
| S6 | **Funnel `/visa/*`** (v1 + GARUDA) | `apps/mouth/src/app/visa/layout.tsx:27-29` + `AppFrame data-funnel="visa"` | S1 navy + rosso `#ff3344`; inline `#0a0a0a` ×7, `#25D366` ×3 (WhatsApp) | **Montserrat** corpo (forzato dal layout) + Cormorant etichette | 2026-04-20 → 08-25 |

Primitivi condivisi da tutti i sistemi web (S1–S4, S6): `--color-red-500 #ff2d4c`, `--color-gold-500 #f59e0b`, `--color-cyan-500 #06b6d4`, `--color-green-500 #22c55e`, `--color-purple-500 #8b5cf6` (Zantara), nero `#040406`; accenti per funnel `[data-funnel]`: visa rosso, kbli `#eab308`, tax cyan, property verde. In `globals.css` compaiono inoltre `"Arial Black", "Impact"` (riga 45) e `JetBrains Mono` (95, 108).

## 4. Componenti dei due funnel

**GARUDA VOA** (`/visa/voa`, 4 passi): `AppFrame` (max 1120px, griglia header/trust/main/footer) · `AppTrustStrip` («4 quick questions · 1 all-inclusive price · 0 extra to pay the government after») · `AppWizard` (stacked-context: riga sommario del passo precedente in corsivo sopra, hairline di progresso 2px, slide+fade, haptic) · `AppStampReveal` (risultato) · `AppShareBar` · `AppWhatsAppCTA`. Card-bottone radius 4, bordo 1px 6% bianco, selezionato 2px `--accent-funnel`. Passo 4 = date + checkbox consenso + «See result» rosso. Stato d'errore senza backend: rimando a WhatsApp (galleria 05). Lingua: **solo EN, nessun toggle** (vincolo 5a nel sorgente). Logo «BALI ZERO» nella nav, badge «WhatsApp» blu-elettrico in alto a destra.

**Visa Oracle v2** (`/visa-oracle`): `OracleShell` · `LivingTree` (sidebar sinistra, 10-14 nodi con linea verticale e pallini; su mobile accordion «Your path so far») · `PathsCounter` («1 interview branches») · `QuestionScreen` (h1 Cormorant, sottotitolo, «Why we ask», 2-3 risposte come card bianche radius 12 con freccia, «Not sure?») · `VerdictReveal` (morph View-Transitions albero→card) · `OutcomeSheet` (5 stati) · `ConfirmationCard` · `ConsentHandoff` · `LanguageToggle` EN/ID · `ThemeToggle` luna. Footer disclaimer fisso («private decision support… Ditjen Imigrasi decides»). **Nessun logo Bali Zero, nessuna nav verso la home** nelle schermate catturate: l'unico marchio è il FAB «N» in basso a sinistra.

## 5. Mappa delle incoerenze (fatti, senza giudizio)

1. **Quattro famiglie sans sulle superfici pubbliche**: Inter (home, VO, kita, my, prime), **Montserrat** (`/visa`, `/visa/match`, `/visa/voa`, `/kbli`, IG, email-spec), IBM Plex Mono (kita/zantara), JetBrains Mono + Arial Black/Impact dichiarati in `globals.css`. Il serif è uno (Cormorant) ma usato in 4 pesi (300/400/500/600) e 2 casi (maiuscolo solo su my).
2. **Cinque rossi**: `#ff2d4c` (core), `#ff3344` (visa su editorial), `#C8102E` (brand IG/logo), `#D01033` (home AA-fix), `#c40020` (red-700). Nessuno dei due funnel usa il rosso del logo.
3. **Quattro «carte»** entro 4 punti esadecimali: home `#f7f6f2`, VO `#f7f5ef`, my `#f4f1ea`, kita `#f8f6f2`; più il navy `#1e3863` della home, `#051C2C` ×4 e `#1f2a44` ×4 in `globals.css`.
4. **Verdi**: canopy VO `#1f4d3d` e i 4 stati-verdetto non esistono in nessun file token condiviso; «eligible» ha tre verdi diversi nel repo (`#16683f` VO, `#10b981` state-success, `#22c55e` green-500). Il WhatsApp `#25d366` è l'unico colore identico ovunque.
5. **Accento del funnel visa contraddetto tre volte**: token `[data-funnel=visa]` = rosso; home `FunnelCTAs.tsx` assegna a «Visa Oracle» **blu `#2E6FD4`** e a KBLI **rame `#d4845a`** (mentre il token kbli è oro `#eab308`); la pagina `/kbli` viva usa il rame ×23, non l'oro.
6. **Home = due terreni**: banda navy (hero, nav, footer: S1) e corpo di carta (S2). VO ripete la carta ma con **verde** al posto del navy; GARUDA ripete il navy ma con **rosso** al posto del blu. Nessuno dei due funnel eredita la coppia navy+carta della home.
7. **Raggi CTA**: home 12px + pillole 9999 (×47), GARUDA 4px, VO 20px, my 12px, kita **0px**, KBLI 9999 (×81).
8. **Marchio**: logo roundel «BALI ZERO» presente su home, `/visa`, GARUDA, my; **assente su VO** (il flagship) e ridotto al FAB «N».
9. **Posture di indicizzazione** (già rilevate 24/8, ri-misurate oggi): `/visa` v1 **index,follow** e promette «24 visa types · We know which · show the cost»; `/visa-oracle` (pack firmato seq-12: 38 prodotti / 110 regole, astensione a contratto) **noindex**. Bug di copy visibile in cattura: `/visa` mostra «24+ visa categories supported» nel trust strip sotto un titolo che dice «24».
10. **Lingua**: GARUDA solo EN (per vincolo); VO EN/ID; home EN; my/kita EN; IG EN con lessico ID. Nessuna superficie in IT.
11. **Densità mobile**: su 390px l'accordion «Your path so far» di VO occupa **~1.100 px** prima della domanda (galleria vo-04-mobile); GARUDA su mobile mantiene il trust strip a 3 numeri sopra il primo passo.
12. **Piano di design già ratificato ma scoped altrove**: GARUDA OS (PR #2850) adotta rame/antracite per kita+my ed **esclude** `/visa-oracle` e marketing; il brand-skill IG **vieta** verde/blu/beige — VO è verde su beige, la home è blu su beige. Le due dottrine scritte non coprono le superfici transazionali pubbliche.

## 6. Schermate non raggiunte (dichiarate)

- GARUDA `checkout/[resultId]`, `upload/[resultId]`, `orders/[orderId]`, `orders/[orderId]/return` — richiedono id emessi dal backend (lane locale in corso; senza backend è atteso lo stato d'errore).
- Visa Oracle **Verdetto** e `OutcomeSheet` — il validatore di coerenza respinge risposte sintetiche generiche; serve un percorso coerente scritto a mano (lane locale in corso).
- Email Brevo reale, carousel IG post-maggio, `evoa.imigrasi.go.id` e i portali di confronto → R2.

## 7. Domande per il ruling di R0 (chiuse, max 3, con raccomandazione)

1. **Perimetro dell'identità unica.** (a) solo i funnel pubblici (visa/VO/GARUDA/kbli/tax/property) derivati dalla home; **(b) anche `my.balizero.com`**, perché il tracking ordine GARUDA e il portale cliente sono lo stesso viaggio dopo il pagamento; kita/prime/zantara restano operativi (S4). — **Raccomandazione: (b).**
2. **Ancora della derivazione «dalla home».** (a) il **navy** del tema editorial (banda hero/nav/footer, `#1e3863` + blu `#3a6dff`); **(b) la coppia Rumah Putih** (carta `#f7f6f2` + inchiostro `#16213a` + navy come accento, Cormorant/Inter) che è ciò che Zero ha riconosciuto in VO («più leggero, dialoga con la home»). — **Raccomandazione: (b), con il navy come colore di struttura, non di sfondo.**
3. **Il funnel v1 `/visa` (pubblico, indicizzato).** (a) entra nel loop come superficie da ridisegnare; **(b) è fuori dal loop: il loop disegna Visa Oracle come unico ingresso e `/visa` viene assorbito/ritirato** (decisione già aperta come TWO-DOORS 24/8, Legge 5). — **Raccomandazione: (b); parcheggiata finché Zero non decide TWO-DOORS, il loop avanza su VO+GARUDA.**

## Adversarial review

**Seat**: Kimi K3 (`kimi-code/k3`, contesto fresco, cross-family), 2026-08-27 01:35 WITA, sessione `session_12f26f00…`. Mandato: falsificare §2-§5 contro disco e `measure.json`.

**Esito**: 8/8 claim mandatori CONFERMATI con file:line (`visa/layout.tsx:2,27-29` · `editorial.css:44,56-57` · `oracle.css:54,65-72` · `rumahVars.ts:32-58` · `FunnelCTAs.tsx:18-22,43-46` + `semantic.css:205-206` · `tokens.json:14-45` + `SKILL.md:69` · `PLAN.md:33` · `voa/layout.tsx:36-50`). Tutti i conteggi DOM (font ×N, raggi ×N, rame ×23, `#ff3344` ×1/×2) confermati contro il JSON.

**Obiezioni sopravvissute e disposizioni** (ognuna ri-verificata dal conduttore su disco prima della correzione):
1. CTA home «Chat with us» → REFUTATA: la prima CTA piena nell'ordine DOM è la pillola nav «Get Started via WhatsApp». **Corretto** in §2 (entrambe esistono; la misura prende la prima).
2. CTA VO «bianco su verde-canopy» → REFUTATA: la pillola è bianca con inchiostro `#16231c`. **Corretto**.
3. «25 hex» in `oracle.css` → REFUTATA: 67 occorrenze / 29 uniche (`grep -oE | sort -u`). **Corretto**.
4. 4.66:1 attribuito a `#ff3344` → REFUTATA: il commento CSS lo attribuisce a `#ff7a88` (accent-text). **Corretto**.
5. «38 prodotti» come esatto → il conduttore cita ora la fonte esatta: pack firmato seq-12, 38 prodotti / 110 regole (corner visaoracle, PR #3090/#4413). **Precisato**.
6. Righe `knowledge` e `visa.balizero.com` non nel JSON → vere ma da `curl`; **fonte esplicitata**.
7. Colonna «sfondo» mescolava body misurato e superficie → **rinominata e valori doppi** (body → superficie) dove differiscono.
8. «3ALI ZERO» → resa visiva della B stilizzata nel roundel; **scritto «BALI ZERO»**.
9. «invertita» in §5.9 è un giudizio → **titolo neutralizzato**; i fatti robots restano.

Nessuna obiezione ha toccato l'inventario dei sei sistemi (§3) né la mappa (§5) nel merito: le incoerenze sono fatti.
