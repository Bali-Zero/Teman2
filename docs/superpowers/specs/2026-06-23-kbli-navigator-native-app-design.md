# KBLI Navigator — app Mac nativa SwiftUI · DESIGN SPEC

> Date: 2026-06-23 · Machine dev/build: M5 (`balizero@Air-M5`) · Runtime target: **Mini-Pro2** (H24)
> Companion research: `research/operations/2026-06-23-sota-macos-native-reference-app-design.md`
> Base d'oro riusata 1:1: `~/Desktop/wr2-control-app` (repo interno nostro, no LICENSE → copiabile)

## 1. Scopo

App **Mac nativa** SwiftUI, minimalista/pulita/immediata, per navigare i **codici KBLI 2025** con
focus sul **moratorium Bali 2026**. Tre funzioni: (1) **Cerca** codice/testo → scheda editoriale;
(2) **Media** — libro PDF (EN/ID) + 20 articoli + 13 capitoli; (3) **Chat** con Zantara (GPT-5.5 via
`codex`) in focus sul codice. Offline-first. Il KBLI Navigator **web** è già live su balizero.com — questa
è la sua controparte desktop nativa, standalone.

## 2. Architettura

App single-window, **`NavigationSplitView` 3-colonne** (sidebar sezioni / lista risultati / detail).
SwiftUI + AppKit + PDFKit, compilata con `build.sh` (swiftc + plugin macro Xcode-beta) → bundle `.app`.

- **Dev + build su M5** (ha Xcode-beta → macro SwiftUI). **Deploy del `.app` compilato via `rsync` sul Mini** (H24). Pattern identico a `wr2-control-app/deploy/`.
- **NO Swift Package Manager**: solo framework Apple nativi + codice vendorato single-file (vincolo `build.sh` swiftc).
- **3 unità isolate**, comunicano solo via modelli `Codable`:
  - **(A) `KBLIStore`** — carica + indicizza il JSON, espone search ranked.
  - **(B) `MediaLibrary`** — enumera articoli/capitoli `.md` + 2 PDF; rende markdown e PDF.
  - **(C) `CodexRunner`** — chat: spawna `codex exec` locale sul Mini, streaming.

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
+ 2 PDF libro (`Bali-Threshold-2026.pdf` EN, `-ID.pdf`) con `PDFViewer` (NSViewRepresentable PDFKit),
toggle EN/ID. **Markdown reso da mini block-renderer vendorato** (~120 righe): heading `#/##/###`,
bullet `- `, blockquote `>`, paragrafi, inline bold/italic/link via `AttributedString(markdown:)` per-riga.

## 5. Sezione "Chat" (Zantara KBLI · GPT-5.5)

`CodexRunner` (clone di `ClaudeRunner.swift`, ma spawna `codex exec` invece di `claude`; strip env
API-key billing come defense-in-depth, conforme a OpenClaw `LLM_ROUTING_POLICY`). System-prompt:
"Zantara, esperta KBLI 2025 + moratorium Bali". Se arrivi dal bottone scheda: inietta `kode` + `l4_bali` +
`uraian` di quel codice come contesto iniziale. Streaming → `ChatView` (riuso WR2). PII: nessuna (codici pubblici).
Codex assente/offline → chat disabilitata con avviso; Cerca + Media intatte.

## 6. Tema, errori, test, trappole

- **Tema**: eredita `Theme.swift` WR2 (paper-ivory chiaro, ink, accenti amber/red, tipografia editoriale).
  `@Environment(\.appearsActive)` per smorzare accenti su finestra inattiva (Mini kiosk H24). Tahoe: `.glassEffect` sulle card.
- **Errori**: JSON mancante = banner "ricostruisci bundle"; PDF mancante = placeholder; codex assente = chat disabilitata con messaggio.
- **Test** (stile `Tests/` WR2, eseguibili `swift` standalone): `KBLIStore` (carica 1559 / trova `55203` /
  status `CHIUSO_PMA_NO_BESAR` / `blocked==true`); `Search.rank` (exact > prefix > substring ordering);
  `MediaLibrary` (20+13 md presenti, 2 pdf path validi); `CodexRunner.resolveCodexPath` (trova binario / fallback pulito).
- **Trappole** (da research):
  1. `AttributedString(markdown:)` NON rende heading/liste → usa mini block-renderer per articoli.
  2. PDF 49MB×2: NON istanziarli insieme, NON bundlare nel binario; lazy `PDFDocument` on-tab, `document=nil` all'uscita (Mini 24GB con Ollama).
  3. SPM rompe `build.sh` → solo framework Apple + vendor single-file.

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
    MarkdownView.swift          # mini block-renderer vendorato
    CodexRunner.swift           # clone ClaudeRunner → codex exec
    Views/
      RootView.swift            # NavigationSplitView 3-col (adattato)
      SearchListView.swift      # .searchable + List risultati
      KBLIDetailView.swift      # scheda GroupBox + callout moratorium
      MediaView.swift           # lista md + PDFViewer
      ChatView.swift            # COPIA-DIRETTO da WR2
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

1. `build.sh` su M5 → exit 0, produce `build/KBLI Navigator.app` (codesign ad-hoc OK).
2. App lancia, sidebar 3 sezioni visibili.
3. Cerca "55203" → 1 risultato in cima, scheda mostra badge ROSSO + callout moratorium con data 13/5/26.
4. Cerca "villa" → 55203 tra i risultati (match judul).
5. Media: libro PDF apre e fa switch EN/ID; un articolo .md mostra heading H2 renderizzati (non testo piatto).
6. Chat: con codex presente, "ciao" → risposta streaming; con codex assente → avviso, no crash.
7. `swift Tests/*` → tutti verdi.
8. `rsync` del `.app` sul Mini → lancia e funziona (Cerca+Media offline; Chat se codex sul Mini).
