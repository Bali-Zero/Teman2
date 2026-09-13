# 08 — Addendum WEBSITE (topic 5, Fable): D4, addendum W2, prompt W7, coda

Complemento del kit di topic 3 (`00-LEGGIMI.md`). Non modifica nulla in `04-astra-package/`
(hash invariati: README `073e57ded13d`, LAUNCH `77baf4451c74`, W0 `ae3f0ae9c664`, W7 `3fd0bc92d869`).
Fonte: `docs/plans/mouth-final-20260911/FINAL.md` nel worktree Mini `docs-mouth-final-spec-20260911`
(PR in apertura; su main dopo il merge). Mappa design R19 → apps/mouth: PR #6124.

## 1. D4 — identità sito: cosa scrivere in `02-DECISIONI-ZERO.md`

Riga D4, colonna RISPOSTA, una delle due parole `D-A` o `D-B`. Significato:

- **D-A** — R19 Direction A (carta `#F7F4EE`, slate `#233D52`, copper `#A44B36`, Fraunces + Manrope
  caricati per route, mai nel root layout) SOLO su home e superfici marketing/blog nominate nel README
  Astra. Funnel invariati: Oracle resta canopy/gold con light/dark, Second Home resta Merah Putih.
  Il vincolo «una sola CTA rossa» (`apps/mouth/e2e/persona-doors.spec.ts:67`) viene ri-pinnato per
  token sulla primaria R19: cambia il colore atteso, non il contratto. Abilita W7.
- **D-B** — sola composizione (layout, griglie, ritmi R19) con colori e font attuali. W7 non parte;
  W2/W4/W5 procedono nel solo perimetro compositivo.

Raccomandazione Fable + Astra: **D-A**. Motivo: il conflitto «Merah Putih vs R19» sta solo
sull'accento dei funnel, e i funnel restano fuori perimetro; su home e blog oggi c'è la navy Rumah
Putih, che nessuna delle due ruling difende. Finché D4 non è scritta, W2 procede in D-B per costruzione.

## 2. Addendum al prompt W2 (incollare DOPO il testo di `07-PROMPT-WEBSITE-W2.txt`)

Vale per ogni lotto website (W2, W7, W4, W5, W6).

```text
Addendum topic 5 (FINAL.md §5, spec Oracle v6.2 §2/§4):
Consumer condivisi: Footer è consumato anche da apps/mouth/src/app/kbli/layout.tsx e NewsHero
da /v2; ogni variante è opt-in con default byte-identico provato su /v2, KBLI e reader.
globals.css: VIETATO (W2 §2 e W7 §2 vincono sulla riga «blocco additivo .r19-*» della spec
Oracle §2); i token R19 vivono in CSS module o stylesheet di route scoped, un bisogno globale è
un delta da riportare, non da prendere. Frozen per il website:
apps/mouth/src/app/(visa-oracle)/**, apps/mouth/src/app/visa/**, packages/core/tokens/**,
root layout.tsx, apps/mouth/src/data/team-roster.ts (l'esclusione dal pubblico si applica nei
tre consumer di rosterBySlug — team, SocialProof, about — E nel book: components/book/book-data.ts
deriva TEAM_MEMBERS da PUBLIC_ROSTER e nessun membro ha publicListed:false, quindi /book/team
mostra ancora i due esclusi; W2 possiede il filtro di presentazione del book + test di regressione,
roster invariato),
kbli/** (W6 possiede i soli file di presentazione KBLI, e solo dopo il go esplicito).
Leggi FINAL.md §4 e 02-DECISIONI-ZERO.md prima di eseguire e prima di ogni PR: le decisioni
scritte lì hanno precedenza sui prompt storici del pacchetto (README «M non registrata»,
blocco W7 «Scelgo D-A»). Ownership: NewsHero/LatestNews sono di W4 (W5 eredita), non di W7.
R19 si legge solo con git show 6603d2913e:<path>: mai la patch di quarantena, mai il branch
riaperto, mai apps/website attivo. Rollback: revert in NUOVA PR armata e, per apps/mouth,
vercel promote per ID della Production che precede la tua PR e segue ogni PR provata dell'altra
finestra, PRIMA che il revert atterri; l'autopromote del Mini può ri-promuovere main entro ~12 min,
quindi il rollback durevole è il merge del revert. File condiviso inatteso
con la finestra Oracle: vince la PR già armata, l'altra rebasa, collisione riportata a Zero.
Builder Contract 5: questa finestra Claude shippa da sola (review → merge → arm → deploy →
prove-live). Le frasi Astra «preparazione fino a candidato reviewable», «consegna PR/candidato
al release owner» e «nessun deploy implicito» sono ABROGATE per una finestra Claude: il release
owner sei tu, e SHIPPED vale solo dopo la prova sulla revisione servita. Riporta a Zero solo
decisioni di business, credenziali e consensi.
```

## 3. W7 identità — SOLO dopo D4 = D-A scritta in `02-DECISIONI-ZERO.md` e W2 integrata su main

Prompt verbatim da `04-astra-package/LAUNCH.md` («Dopo la scelta D-A»), seguito dall'addendum §2.

```text
Scelgo D-A: R19 Direction A (carta, slate/copper, Fraunces/Manrope locali) su home
e superfici marketing/blog nominate nel README. Sostituisce R4 solo lì e il
vincolo di hue rosso con una primaria R19. Oracle/Studio e altri perimetri attuali.
Mandato SHWEB-20260911 / W7-R19-IDENTITY. Pacchetto:
/Users/nuzantara/nuzantara/.worktrees/docs-mouth-final-windows-20260911/docs/plans/mouth-final-20260911
Leggi README.md e W7-r19-identity.md, registra questa ruling; verifica W2 integrata
e ownership esclusiva. NUOVO worktree broker lane mouth, task-id shweb-w7-r19-20260911;
check macchine/base e ruoli/effort/deadline secondo AGENTS/modus. Implementa solo
variante scoped di identità/chrome/font. Core manifest solo export font; nessun
root/preload/token globale/lock/API/dato. Default e consumer esclusi preservati.
Misura contrasti, font budget, Lighthouse; re-pin mirato dei soli test colore,
mai dei contratti funzionali. Prova tutte le famiglie convertite e funnel protetti.
Brief/prove/Bites, review indipendente e gate fresco; candidato reviewable,
release solo con autorità e gate correnti. Mai apps/website o nuovo publishing.
```

Perimetro W7 (da `W7-r19-identity.md` §2 + mappa topic 5): Footer/MobileNav/HeroBlueprint/PersonaDoors
solo come variante opt-in (NewsHero è di W4, W5 lo eredita; NavShell resta al suo default); token R19 in un blocco scoped; Fraunces/Manrope come export del core manifest, mai preload nel
root layout; budget font +≤120 KB per route e ≤60 KB per subset; Lighthouse mediana di 3 con LCP
≤ +5 % e CLS mai in aumento; ri-pin dei soli test colore (`blog-news-light`, `service-pages-light`,
persona-doors P2), mai dei contratti funzionali; screenshot 390+1440 di `/visa-oracle` e
`/visa/second-home/studio` identici prima/dopo.

## 4. Coda dopo i due slot (template in `04-astra-package/LAUNCH.md`, sezione «Coda»)

| Dipendenza | Mandato | Task id |
| --- | --- | --- |
| M = entrambi (oggi M = SOLO ORACLE: esclusa) | W1-SH-TECH → W3-SH-EDITORIAL | `shweb-w1-tech-20260911`, `shweb-w3-editorial-20260911` |
| D4 = D-A + W2 integrata | W7-R19-IDENTITY | `shweb-w7-r19-20260911` |
| W2 (+ W7 se D-A) | W4-WEB-NEWS → W5-WEB-HOME | `shweb-w4-news-20260911`, `shweb-w5-home-20260911` |
| W5 + baseline Lighthouse + go esplicito di Zero | W6-WEB-KBLI | `shweb-w6-kbli-20260911` |

Mai più di DUE finestre operative in totale; una branch armata non si riusa; ogni lotto parte da un
nuovo worktree su `origin/main`.

## 5. Panel sulla spec finale

Quattro seat letti su `FINAL.md` + README/LAUNCH/W0/W2/W7 + `02-DECISIONI-ZERO.md` + questo file:
Astra (`codex exec -m gpt-6-astra`, xhigh), Gemini 3.1 Pro (`agy`), Kimi K3 (`kimi -p`), Qwen 3.8 Max
(TP1, dichiarato fallito se ancora 403). Output grezzi e disposizioni: `docs/plans/mouth-final-20260911/
evidence/panel/` e `FINAL.md` §8 nella PR di questo lotto.
