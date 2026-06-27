---
date: 2026-06-23
domain: operations
client_case: none
sources:
  - https://kapeli.com/dash
  - https://developer.apple.com/documentation/swiftui/building-a-great-mac-app-with-swiftui
  - https://github.com/conorluddy/LiquidGlassReference
  - https://github.com/gonzalezreal/swift-markdown-ui
  - https://blog.eidinger.info/3-surprises-when-using-markdown-in-swiftui
  - https://pfandrade.me/blog/mac-assed-swiftui-app/
  - https://github.com/open-saas-directory/awesome-native-macosx-apps
---

# SOTA design — app Mac nativa reference/knowledge-browser (2026)

Deep research (fork Opus, 8 tool-use, 167k tok) per il design dell'app **KBLI Navigator** nativa
SwiftUI: reference browser search-driven (1559 codici → scheda editoriale) + media markdown/PDF + chat AI in focus.
Bias spietato verso **framework Apple nativi** (zero-dependency, zero-licenza, compatibili con build `swiftc`/`build.sh`,
NO Swift Package Manager).

## TOP 5 app di riferimento — cosa rubare di preciso

1. **Dash (Kapeli)** — modello 3 zone "sidebar tipi → lista risultati ranked → detail scrollabile",
   ricerca istantanea offline, match-by-prefix che porta in cima gli esatti. È il flusso codice→scheda.
2. **Bear** — tipografia editoriale + search per frammenti (substring tollerante), palette calma a tutta-area senza chrome.
3. **Reflect** — "AI in focus sull'entità corrente": la card aperta diventa il contesto dell'AI → bottone "Chiedi a Zantara su questo codice".
4. **Apple Dictionary.app** — reference-card densa fatta bene: lemma grande in testa, badge inline, blocchi gerarchici separati da spazio bianco NON da linee.
5. **Proxyman** — Swift/SwiftUI nativo: `List` con selezione nativa + detail-pane reattivo + toolbar consolidata, "Mac-assed" senza Electron.

## Decisione per mattone (reuse-first)

| Mattone | Decisione | Etichetta | Licenza |
|---|---|---|---|
| M1 scheletro (Theme/Chat/Runner/RootView/build.sh) | da `wr2-control-app` | [COPIA-DIRETTO] | nostra (repo interno, no LICENSE) |
| M2 search/filter 1559 record | `.searchable` nativo + ranking manuale ~30 righe (no Fuse/SwiftData) | [SCRIVI-NUOVO minimale] | nostra |
| M3 markdown articoli/.md | mini block-renderer vendorato ~120 righe (NON AttributedString da solo) | [STUDIA-PATTERN-RISCRIVI] | nostra |
| M4 PDF libro EN/ID | `PDFKit.PDFView` in `NSViewRepresentable`, lazy load | [INSTALLA-LIB Apple] | sistema |

**Ranking search** (exact code > prefix code > judul prefix > substring judul/uraian):
```swift
func rank(_ r: KBLI, _ q: String) -> Int? {
    let c = r.kode, j = r.judul.lowercased(), ql = q.lowercased()
    if c == ql { return 0 }
    if c.hasPrefix(ql) { return 1 }
    if j.hasPrefix(ql) { return 2 }
    if j.contains(ql) || r.uraian.lowercased().contains(ql) { return 3 }
    return nil
}
```

**PDF viewer nativo**:
```swift
struct PDFViewer: NSViewRepresentable {
    let url: URL
    func makeNSView(context: Context) -> PDFView {
        let v = PDFView(); v.autoScales = true; v.displayMode = .singlePageContinuous
        v.document = PDFDocument(url: url); return v
    }
    func updateNSView(_ v: PDFView, context: Context) {
        if v.document?.documentURL != url { v.document = PDFDocument(url: url) } // switch EN/ID
    }
}
```

## Design moves concreti (traducibili in SwiftUI)

1. **`NavigationSplitView` 3-col** (sidebar / lista risultati / scheda) invece dell'`HStack` manuale di WR2 → Liquid Glass + ambient reflection gratis su Tahoe; il pattern WR2 (HStack 2-col) li perde.
2. **`.searchable(text:)` + `.searchToolbarBehavior(.minimized)`** sulla colonna lista → barra ricerca adattiva nativa, non TextField custom.
3. **Status-badge Bali a sinistra del kode**, SF Symbol + colore semantico Theme: `circle.fill` verde (`OK_or_HIGHER_RISK`), `xmark.octagon.fill` rosso (`BLOCCATO_*`/`CHIUSO_*`), `questionmark.circle` grigio (`NEEDS_REVIEW`). Stesso badge piccolo in lista, grande in scheda.
4. **Scheda in `ScrollView` con sezioni `GroupBox`** (header / Status-Bali / Licensing per-skala / Moratorium) su material — separa per spazio bianco e material, MAI righe divisorie (lezione Dictionary/Bear). Tahoe: `.glassEffect(.regular, in: .rect(cornerRadius:))`.
5. **`List` nativo per i risultati** (non LazyVStack custom): selezione, emphasis finestra attiva, frecce ↑↓ gratis.
6. **`@Environment(\.appearsActive)`** per smorzare accenti quando finestra inattiva (Mini = kiosk H24).
7. **Moratorium come callout amber** (icona `exclamationmark.triangle` + regola + data 13/5/26 + fonte Gubernur), visibile solo se `l4_bali.blocked` → trasforma il dato nella "notizia 2026".
8. **Bottone "Chiedi a Zantara" come `.toolbar` primaryAction** della scheda → apre Chat passando `kode` + estratto `l4_bali`/`uraian` come system-context (pattern Reflect AI-in-focus).

## Trappole note

1. **Markdown headings**: `AttributedString(markdown:)` nativo perde `##`/liste/immagini → long-form = muro di testo. Inline nativo (bold/italic/link) per-riga OK; per i blocchi serve il mini-renderer vendorato.
2. **PDF 49MB ×2**: `PDFDocument(url:)` lazy per pagina OK, ma NON istanziare entrambi insieme né bundlare nel binario — tienili in `Resources/`, carica on-tab, `document=nil` all'uscita (Mini 24GB condiviso con Ollama).
3. **SPM vs swiftc**: qualunque lib SPM (swift-markdown-ui, Fuse) rompe `build.sh`. Regola app: SOLO framework Apple + codice vendorato single-file.
