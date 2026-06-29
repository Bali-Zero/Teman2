# KBLI Navigator — app Mac nativa SwiftUI · DESIGN SPEC

> Date: 2026-06-23 · Machine dev/build: M5 (`balizero@Air-M5`) · Runtime target: **Mini-Pro2** (H24)
> Companion research: `research/operations/2026-06-23-sota-macos-native-reference-app-design.md`
> Base d'oro riusata (fork chirurgico, NON 1:1): `~/Desktop/wr2-control-app` (repo interno nostro, no LICENSE → copiabile)
> **REV 2** (2026-06-23) post review 4-LLM severa (Gemini agy + DeepSeek V4 Pro + Codex; verdetto FIX-FIRST).
> Findings incorporati sotto §9. Verifiche empiriche fatte in-turn (non assunte).

## 1. Scopo

App **Mac nativa** SwiftUI, minimalista/pulita/immediata, per navigare i **codici KBLI 2025** con
focus sul **moratorium Bali 2026**. Tre funzioni: (1) **Cerca** codice/testo → scheda editoriale;
(2) **Media** — libro PDF (EN/ID) + 20 articoli + 13 capitoli; (3) **Chat** con Zantara (GPT-5.5 via
`codex`) in focus sul codice. Offline-first. Il KBLI Navigator **web** è già live su balizero.com — questa
è la sua controparte desktop nativa, standalone.

## 2. Architettura

App single-window, **`NavigationSplitView` 3-colonne** (sidebar sezioni / lista risultati / detail).
SwiftUI + AppKit + PDFKit, compilata con `build.sh` (swiftc + plugin macro Xcode-beta) → bundle `.app`.

### Distribuzione 3-Mac (DECISO 2026-06-23) — icona nativa su M5 + Pro + Mini

**Lo stesso `.app` gira nativo su tutte e 3 le macchine** (icona vera, doppio-click). NON è un'app remota:
è un binario arm64 locale su ogni Mac. Due risorse, due politiche:

- **Dati (Cerca + Media)** = **bundlati nel `.app`** → 100% locali, veloci, offline su OGNI Mac. Nessuna rete.
- **Chat (Zantara-OpenClaw)** = **un solo cervello, sul Mini** (FASE 0). L'`OpenClawRunner` è **dual-mode**:
  - **sul Mini** → invoca `~/.openclaw/bin/openclaw agent ... --json` diretto (locale).
  - **su M5 / Pro** → invoca `ssh mini ~/.openclaw/bin/openclaw agent ... --json` (SSH verificato funzionante da
    entrambe 2026-06-23; `openclaw` NON è in PATH sul Mini → path assoluto obbligatorio). Rileva l'host via `Host.current()`/`hostname`.
  - Un solo Zantara condiviso → **niente split-brain** (cicatrice #10); ma se il Mini è giù, la chat si degrada
    e Cerca+Media restano vivi ovunque.
- **Build una volta** (M5 in `~/Downloads/Xcode-beta.app`, o Pro che ha Xcode.app pieno + macOS 27) →
  `rsync` del `.app` sulle altre due macchine. Pattern `wr2-control-app/deploy/install-mini.sh` esteso a 3 target.
- **NO Swift Package Manager**: solo framework Apple nativi + codice vendorato single-file (vincolo `build.sh` swiftc).
- **3 unità isolate**, comunicano solo via modelli `Codable`:
  - **(A) `KBLIStore`** — carica + indicizza il JSON, espone search ranked.
  - **(B) `MediaLibrary`** — enumera articoli/capitoli `.md` + 2 PDF; rende markdown e PDF.
  - **(C) `OpenClawRunner`** — chat: spawna `openclaw agent --agent zantara-kbli --json` sul Mini (NON `codex exec` nudo — vedi §9 F1), legge `result.finalAssistantVisibleText`.

### FASE 0 (prerequisito, sotto-progetto separato) — armare OpenClaw sul Mini

L'app è un **client** del runtime OpenClaw, esattamente come il bridge WhatsApp
(`~/.openclaw/bin/openclaw_whatsapp_bridge.py:1741` → `openclaw agent ... --json` → `finalAssistantVisibleText`).
Prima che l'app possa parlare con Zantara, sul Mini serve (verificato 2026-06-23):

- **Gateway daemon H24** (LaunchAgent) — oggi `pgrep openclaw` = vuoto, va armato.
- **`openclaw.json` ripulito** — 3 errori live: `OPENROUTER_API_KEY`/`DEEPSEEK_API_KEY` env mancanti (rimuovere o rendere opzionali), `models.providers.openai-codex.models.0.contextTokens` key non riconosciuta, `channels.telegram.streaming` valore invalido. Tenere il provider codex/GPT-5.5 (auth già presente: `~/.codex/auth.json` ✅).
- **Agent `zantara-kbli`** — nuovo agent con system-prompt "Zantara, esperta KBLI 2025 + moratorium Bali" (modello GPT-5.5 via OpenClaw). Agenti già presenti: `main`, `coder`, `telegram-codex`.
- **PATH**: `openclaw` NON è in PATH sul Mini → l'app/runner usa path assoluto `~/.openclaw/bin/openclaw`.
- Contratto d'interfaccia (ciò che l'app assume): `openclaw agent --agent zantara-kbli --message <q> --json [--session-id <s>]` → stdout JSON con `result.finalAssistantVisibleText`. L'app si sviluppa contro QUESTO contratto; la Fase 0 lo fornisce.

### Dataset (DECISO — provenienza verificata 2026-06-23)

`KBLI_2025_FINAL_CLEAN.json` **v10.0-L2-oss-risk** (1559 codici), copiato al build da
`/.worktrees/intel-kbli-rag-source-align/apps/mouth/data/`. Questa versione (≠ v8.0 del 28-mar) ha
**tutti i campi** che servono:

- `kode_kbli_2025`, `judul`, `uraian`, `ruang_lingkup` (scope OSS, 1338/1559)
- `per_skala[]` — per scala: `kategori_risiko`, `perizinan`, `kewajiban[]`, `sanksi_*`
- `pma_status`, `pma_max_asing`, `pma_kondisi`, `intel_2026`
- **`l4_bali`** (popolato su tutti i 1559) — `status`, `reason`, `confidence`, `blocked` (bool),
  `moratorium{rule, effective:"2026-05-13", source:"Gubernur B.27.000/642/PM/DPMPTSP", ...}`.
  Distribuzione status: 1014 `OK_or_HIGHER_RISK`, 373 `BLOCCATO_CLASSE_RISCHIO`, 70 `BLOCCATO_DIPENDE_SCOPE`,
  63 `NEEDS_REVIEW_NO_OSS_SCOPE`, 20 `CHIUSO_PMA_NO_BESAR`, 8 `TERTUTUP`, 5 `TERBATAS`, 5 `CHIUSO_BALI_PROPOSTO`, 1 `CHIUSO_BALI`.

Bundlati in `Resources/`: il JSON + 20 articoli `.md` + 13 `book-chapters/*.md` + **NON** i 2 PDF
(troppo grandi da incorporare — vedi §6 trappola PDF; restano in `Resources/` come file copiati, caricati lazy).
Fonte contenuti: `~/Desktop/KBLI-2025-Content/`.

## 3. Sezione "Cerca" (cuore)

`.searchable(text:)` sulla colonna-lista (Tahoe `.searchToolbarBehavior(.minimized)`). Filtro in-memory
con **ranking manuale** (no lib): exact-code(0) > prefix-code(1) > judul-prefix(2) > substring judul/uraian(3).
Debounce via `.task(id: query)`.

**Lista risultati** = `List` nativo (selezione + frecce ↑↓ gratis). Ogni riga: status-badge SF Symbol
colorato a sinistra + `kode` mono + `judul`.

**Scheda dettaglio** (`ScrollView` + sezioni `GroupBox` su material, NO righe divisorie):

- **Header**: `kode` grande + `judul` + **badge status-Bali grande** (verde `OK_or_HIGHER_RISK` `circle.fill` /
  rosso `BLOCCATO_*`/`CHIUSO_*`/`TERTUTUP` `xmark.octagon.fill` / grigio `NEEDS_REVIEW` `questionmark.circle`) + badge PMA nazionale.
- **Callout Moratorium** (solo se `l4_bali.blocked`): riquadro amber `exclamationmark.triangle` con
  `reason` + regola + data 13/5/26 + fonte Gubernur. È la "notizia 2026".
- **Uraian / ruang_lingkup**: descrizione + scope (markdown-renderer per il testo).
- **Licensing** (`per_skala[]`): una card compatta per scala → rischio · perizinan · kewajiban · sanzioni.
- **Toolbar primaryAction "Chiedi a Zantara"** → apre Chat con `kode` + estratto `l4_bali`/`uraian` come contesto.

## 4. Sezione "Media"

`MediaLibrary` enumera da `Resources/`: 20 articoli + 13 capitoli (lista → detail markdown renderizzato)

- 2 PDF libro (`Bali-Threshold-2026.pdf` EN, `-ID.pdf`) con `PDFViewer` (NSViewRepresentable PDFKit),
  toggle EN/ID. **Markdown reso da mini block-renderer vendorato** (~120 righe): heading `#/##/###`,
  bullet `- `, blockquote `>`, paragrafi, inline bold/italic/link via `AttributedString(markdown:)` per-riga.

## 5. Sezione "Chat" (Zantara KBLI · GPT-5.5 via OpenClaw)

**Identità del bot: un "NLM focalizzato sui KBLI con la scioltezza di GPT"** — cioè un assistente
_grounded_ sui contenuti reali Bali Zero (come NotebookLM: cita le fonti, non inventa codici/numeri/norme)
MA conversazionale e fluido (come GPT, non un retriever rigido che sputa snippet).

`OpenClawRunner` (NON clone di `codex exec` — vedi §9 F1) è **dual-mode** (vedi §2 distribuzione 3-Mac):

- **sul Mini**: spawna `~/.openclaw/bin/openclaw agent --agent zantara-kbli --message <q> --json --session-id <s>` (locale).
- **su M5/Pro**: spawna `ssh mini ~/.openclaw/bin/openclaw agent --agent zantara-kbli --message <q> --json --session-id <s>`.
  Legge `result.finalAssistantVisibleText` (testo pulito, no banner/hook). GPT-5.5 dietro OpenClaw, **un solo cervello sul Mini**.
  Streaming/poll → `ChatView` (fork chirurgico da WR2). PII: nessuna (codici pubblici). L'host si rileva a runtime (`hostname`).

**Grounding NLM-style (il cuore del "non inventa"):**

- **Corpus di grounding = i contenuti già su disco**: 1559 record KBLI (`l4_bali`, `per_skala`, `uraian`),
  20 articoli + 13 capitoli, libro PDF. Stessi contenuti della sezione Media → l'app è coerente con sé stessa.
- **Iniezione contesto**: quando l'utente chiede (o arriva dal bottone scheda), l'app fa una **retrieval locale**
  (riusa il `KBLIStore.search` + match su articoli) e inietta i passaggi rilevanti nel `--message` come
  blocco "FONTI" + la domanda. Il system-prompt dell'agent `zantara-kbli` impone: _rispondi SOLO su queste
  fonti, cita il codice/articolo, se non è nelle fonti dillo, mai inventare un codice o uno status Bali_.
- **Scioltezza GPT**: il system-prompt NON forza un formato rigido — Zantara spiega in linguaggio naturale,
  bilingue, con tono Bali Zero ("Pragmatic Sherpa"), ma ancorata. È il pattern **bipolar verifier** invertito:
  GPT per la forma, le fonti-on-disk per la verità.
- **Confine**: il grounding è retrieval LOCALE (no rete, no PII — codici pubblici). NotebookLM vero NON è
  coinvolto (sarebbe rete + account); "NLM-style" = il _comportamento_ grounded, replicato sul corpus locale.

Se OpenClaw/gateway assente/offline → chat disabilitata con avviso chiaro; Cerca + Media restano intatte.

## 6. Tema, errori, test, trappole

- **Tema**: eredita `Theme.swift` WR2 (paper-ivory chiaro, ink, accenti amber/red, tipografia editoriale).
  `@Environment(\.appearsActive)` per smorzare accenti su finestra inattiva (Mini kiosk H24). Tahoe: `.glassEffect` sulle card.
- **Errori**: JSON mancante = banner "ricostruisci bundle"; PDF mancante = placeholder; OpenClaw/gateway assente = chat disabilitata con messaggio (preflight: ping `openclaw agent` o gateway-health).
- **Test** (stile `Tests/` WR2, eseguibili `swift` standalone): `KBLIStore` (carica 1559 / trova `55203` /
  status `CHIUSO_PMA_NO_BESAR` / `blocked==true`); `Search.rank` (exact > prefix > substring ordering);
  `MediaLibrary` (20+13 md presenti, 2 pdf path validi); `OpenClawRunner` (risolve path `~/.openclaw/bin/openclaw` /
  parsa `result.finalAssistantVisibleText` da JSON mock / fallback pulito su gateway-down / rileva auth-fail su stderr).
- **Trappole** (da research + panel — vedi §9):
  1. `AttributedString(markdown:)` NON rende heading/liste → renderer markdown serio (vedi §9 F3), NON 120-righe naïf.
  2. PDF 49MB×2: NON istanziarli insieme, NON bundlare nel binario; caricamento su **background thread** (`Task.detached` + `ProgressView`), `document=nil` all'uscita (Mini 24GB con Ollama).
  3. SPM rompe `build.sh` → solo framework Apple + vendor single-file.
  4. **Riuso WR2 = fork chirurgico** (NON 1:1): gut `AppState`/`WarRoom`/`QueueWriter`/idle-kiosk; copia solo layout+styling+runner-shape (vedi §9 S2).

## 7. Layout file (worktree → poi repo dedicato `~/Desktop/kbli-navigator-app/` su M5)

```
kbli-navigator-app/
  build.sh                      # adattato da wr2-control-app
  Info.plist
  Sources/
    KBLINavigatorApp.swift      # @main
    Theme.swift                 # COPIA-DIRETTO da WR2
    Localization.swift          # COPIA-DIRETTO da WR2 (IT/EN/ID)
    Models.swift                # KBLI, PerSkala, L4Bali, MediaItem (Codable)
    KBLIStore.swift             # load JSON + search ranking
    MediaLibrary.swift          # enumera md/pdf
    MarkdownView.swift          # renderer markdown serio (vedi §9 F3)
    OpenClawRunner.swift        # spawna `openclaw agent --json` sul Mini (NON codex nudo)
    Grounding.swift             # retrieval locale → blocco FONTI per il prompt (NLM-style)
    Views/
      RootView.swift            # NavigationSplitView 3-col (adattato)
      SearchListView.swift      # .searchable + List risultati
      KBLIDetailView.swift      # scheda GroupBox + callout moratorium
      MediaView.swift           # lista md + PDFViewer
      ChatView.swift            # fork chirurgico da WR2
  Resources/
    KBLI_2025_FINAL_CLEAN.json  # v10.0
    articles/*.md (20)
    book-chapters/*.md (13)
    Bali-Threshold-2026.pdf / -ID.pdf
    bz-logo.png
  Tests/                        # standalone swift test runners (stile WR2)
  PROVENANCE.md                 # traccia riuso WR2 + dataset + research
```

## 8. Acceptance (falsificabili)

1. `build.sh` su M5 → exit 0, produce `build/KBLI Navigator.app`.
2. App lancia, sidebar 3 sezioni visibili.
3. Cerca "55203" → 1 risultato in cima, scheda mostra badge ROSSO + callout moratorium con data 13/5/26.
4. Cerca "villa" → 55203 tra i risultati (match judul).
5. Media: libro PDF apre e fa switch EN/ID (caricamento su background thread, no main-thread freeze); un articolo .md mostra heading H2 + liste renderizzati (non testo piatto).
6. **FASE 0**: `openclaw agent --agent zantara-kbli --message "test" --json` sul Mini → stdout JSON con `result.finalAssistantVisibleText` non vuoto.
7. Chat: con gateway su, "cos'è il 55203?" → risposta che cita lo status Bali REALE dal grounding (no codice inventato); con gateway giù → avviso, no crash, no hang.
8. `swift Tests/*` → tutti verdi.
9. **Deploy 3-Mac**: `rsync` del `.app` su M5 + Pro + Mini, `xattr -cr` + `codesign --force --sign -` su OGNI macchina destinazione → **lancia senza "damaged/cannot open"** ovunque (verifica F2).
10. **Chat dual-mode**: su M5/Pro "cos'è il 55203?" → risposta via `ssh mini openclaw` (cervello unico); sul Mini → stessa risposta via openclaw locale. Mini giù → chat degrada, Cerca+Media vivi su M5/Pro.

## 9. Findings review 4-LLM (REV 2) — incorporati sopra

Panel severo 2026-06-23: Gemini agy (REDESIGN) + DeepSeek V4 Pro (FIX-FIRST) + Codex GPT-5.5 (output solo-rumore → _prova_ di F1). Verdetto sintesi: **FIX-FIRST**. Tutti i findings verificati empiricamente in-turn, non assunti.

- **F1 [FATAL→risolto] codex nudo ≠ chat-backend.** Verificato: `codex exec` per 1 domanda → 718KB output, banner+hook, _esegue ssh/git_ (agentic). **Fix**: backend = **OpenClaw `agent --json`** (GPT-5.5 dietro gateway → testo pulito, come bridge WhatsApp `openclaw_whatsapp_bridge.py:1741`). Prereq = FASE 0 (§2).
- **F2 [FATAL] ad-hoc sig + rsync → Gatekeeper block sul Mini.** WR2 fa `codesign -s -` ma **mai deployato sul Mini** (verificato: `NO-WR2-APP-ON-MINI`) → mai provato. **Fix**: deploy-script con `xattr -cr` + re-`codesign --force --sign -` **eseguito sul Mini** post-rsync; acceptance #9.
- **F3 [FATAL] markdown 120-righe insufficiente** per articoli con tabelle/liste-annidate. **Fix**: renderer serio single-file vendorato O pre-render `.md`→HTML a build + `WKWebView` (decisione in fase plan).
- **S1 [SERIOUS→risolto] SwiftUI senza WindowServer crasha.** Verificato: Mini ha `nuzantara console` + `WindowServer up` → OK.
- **S2 [SERIOUS] riuso WR2 1:1 trascina stato** (`AppState`/`WarRoom`/`QueueWriter`/idle-kiosk). **Fix**: fork chirurgico (§6 trappola 4).
- **S3 [SERIOUS] macro-plugin forse inutile** — `NavigationSplitView`/`.searchable`/`.glassEffect` non richiedono il plugin (solo `#Preview`). **Fix**: in fase plan, testare build senza `-external-plugin-path` se niente `#Preview`.
- **Minori** (DeepSeek): debounce vero (Combine), build.sh copy-phase per md/pdf, PDF set-nil-before-assign, auth-fail detection — tutti recepiti nei test/trappole.
- **RESPINTO**: Gemini "`.glassEffect` è visionOS, non esiste su macOS" → **FALSO**, compila exit 0 su `arm64-apple-macosx26.0` (cicatrice #6: anche il refuter allucina, ri-verificato).
