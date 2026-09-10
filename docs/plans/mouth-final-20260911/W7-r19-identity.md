# W7 — R19 Direction A: identità e chrome marketing/blog

## 1. Mandate

`SHWEB-20260911 / W7-R19-IDENTITY` · BLUE default · Gear 2 minimo (floor prevale).
Mini; nuovo worktree `mouth-shweb-w7-r19-20260911`, task-id `shweb-w7-r19-20260911`.
Prerequisiti: W2 integrata; **scelta D-A di Zero registrata**, con override R4 limitato
a marketing/blog. Successo: identità Direction A dentro mouth, funnel conservati.
Con D-B questa window non parte; nessuna decisione dedotta dal silenzio.

## 2. Owned perimeter

- `apps/mouth/src/lib/theme/r19Vars.ts` nuovo; CSS module dedicati in marketing/blog.
- `src/app/(marketing)/page.tsx` solo integrazione chrome/font/theme; `(blog)/layout.tsx`,
  `(blog)/_components/BlogNav.tsx`; wrapper di presentazione in `(blog)/team/page.tsx`,
  `NewsPageClient.tsx`, `[category]/[slug]/ArticleClient.tsx`, `services/page.tsx`,
  `services/[slug]/page.tsx`, `contact/page.tsx` **solo se necessario a sostituire
  override di palette/font che bloccano l'eredità**. Nessun loader/handler/data change.
- `src/app/v2/_components/{Footer,MobileNav,HeroBlueprint,PersonaDoors}.tsx` per
  varianti opt-in; CSS module/test adiacenti. `packages/core/components/NavShell.tsx`
  e test solo variante paper, default conservato. L'alternativa di un header locale
  va fissata nel brief prima di BUILD; non costruire entrambe le implementazioni.
- `packages/core/fonts/{fraunces,manrope}.ts`, due woff2 latin in `fonts/files`,
  `packages/core/package.json` **solo export font**; nessuna dipendenza/lockfile.
- E2E `persona-doors`, `blog-news-light`, `service-pages-light`, nuova coverage R19
  e test dei token/contrasto in mouth, nella suite già obbligatoria. Nessuna nuova
  required context necessaria in questa window e nessuna guardia esistente rimossa.

Vietati root layout/font preload, globals.css R19 o mouth, core tokens/ThemeProvider,
proxy/routing, API/engine/dati, MDX/i18n di contenuto, trust figures, nuovi recapiti,
Oracle/Studio, KBLI e contrast guard Merah Putih. Verifica scope manuale, anche per
hunk/funzione nei file misti. W7 possiede questi file esclusivamente prima di W4/W5.

## 3. Sibling contract

Fonte immutabile R19 6603d2913e; token carta #F7F4EE, ink #1D2C3B, slate #233D52,
copper #A44B36, surface #FFFCF7, wash #EAE3D8, line #DAD8D1; footer #EEE9E1.
Fraunces display, Manrope UI, fallback misurati anche per lingue/glyph non latin.
Non rimuovere i font root in questa window: misurare il costo cumulativo.

Tema scoped con alias ridichiarati nel wrapper; in blog nav/footer sono fratelli
del main, quindi il wrapper del layout governa il chrome. La pagina `(blog)/property`
condivide quel layout: **preservarne esplicitamente il trattamento attuale con
opt-out per route e relativo test**, oppure tornare a Zero per estendere D-A; il
tool `/property/eligibility` non è la stessa superficie. Nessun repaint accidentale.
NavShell attuale è fixed 56px/glass: la variante R19 sticky/carta e ritmo 88px
richiedono offset del contenuto/menu coerenti, non soltanto due variabili colore.
Default v2 e altri consumer invariati; nuovi token non filtrano verso i funnel.

Una primaria riconoscibile sulla home sostituisce il test di hue rosso solo dopo
D-A; destinazione e tracking WhatsApp restano gli stessi. Non applicare il colore
primario a stati semantici e non cancellare CTA utili per ottenere il conteggio.

## 4. Acceptance

- Snapshot base/candidato 360/390/768/1280/1440: home, team, news, un reader con
  MDX interattivo, services/list+detail, contact. Confronto Direction A renderizzato;
  nessun gap fra header e contenuto, menu tastiera/Escape, focus, immagini, no overflow.
- Negativi: data-theme salvato, navigazione client da/verso Oracle/Studio, fonte
  lenta/non caricata, testo lungo EN/ID e lingua non latin, no news, scroll con FAB.
- Test dark-nav e one-red-CTA ripinnati **solo sui consumer convertiti** nella stessa
  PR; assert di link, tracking, contenuto, accessibilità e prezzi preservati. Reader
  e services/contact conservano struttura/comportamenti e fonti: sola identità.
- Token e contrasti computati nel contesto, incluse CTA, link, bordi interattivi,
  focus e stati disabilitati. Test negativo con colore illegibile deve fallire.
  Font budget e Lighthouse secondo README, suite/TSC/lint/build; default NavShell,
  `/v2`, `/property`, Oracle/Studio, accessi portal/kita/my come controlli pertinenti.
- Dopo release autorizzata: SHA servito e browser su ogni tipo di pagina convertita,
  più i funnel protetti; nessuna prova per semplice HTTP 200 o screenshot isolato.

## 5. Team

Dux, eventuale implementer, reviewer cross-family, gate fresco e release owner da
army-map §1bis; nominati al lancio, con modelli/effort/thread effettivi. Zero firma
la scelta D-A; non è sostituita dal verdetto tecnico del reviewer.

## 6. Appetite and stop-loss

Proposta 6h; deadline UTC e rinnovo Zero/staff room, cap comuni README. Un lotto
identità, non un refactor generale. Se diff/asset superano una tranche reviewable,
checkpoint e dividere in nuovi mandati/worktree con stesso contratto, mai continuare
una branch armata. Nessun terzo slot e nessuna nuova spesa API implicita.

## 7. Evidence and release

`Bites:` visitatore marketing/blog che vede Direction A e completa gli stessi
percorsi. Allegare ruling, baseline/after, test/exit, font/licenze/hash e costo per
route, contrasti, consumer inventory, negativi e receipt gate sul HEAD corrente.
W2 → W7 → W4/W5; W1/W3/W0 paralleli solo con paths disgiunti. Release secondo il
percorso verificato al lancio; rollback per leakage, regressione contrasto/font/CLS,
CTA persa, consumer fuori D-A ridipinto o perdita metadata. Merah Putih guard resta.
