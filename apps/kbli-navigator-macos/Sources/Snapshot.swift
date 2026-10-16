import AppKit
import PDFKit
import SwiftUI

/// Off-screen renderer for QA screenshots without a GUI session.
/// Usage: `KBLINavigator --snapshot <code> <out.png>` renders the detail card for <code>.
/// Returns true if it handled the snapshot request (caller should then exit).
enum Snapshot {
    @MainActor
    static func runIfRequested() -> Bool {
        let args = CommandLine.arguments
        guard let idx = args.firstIndex(of: "--snapshot") else { return false }
        let code = args.count > idx + 1 ? args[idx + 1] : "55203"
        let out  = args.count > idx + 2 ? args[idx + 2] : "/tmp/kbli-snapshot.png"

        let state = AppState()
        let lang = LanguageManager()
        // Default EN; honor KBLI_LANG=id so QA can capture the Bahasa render off-screen.
        lang.lang = (ProcessInfo.processInfo.environment["KBLI_LANG"]?.lowercased() == "id") ? .id : .en
        // Theme: honor KBLI_THEME=light|dark (default dark — Night is the current pick).
        Theme.mode = (ProcessInfo.processInfo.environment["KBLI_THEME"]?.lowercased() == "light") ? .light : .dark

        // Snapshot canvas size — wider for full-window modes so the 3 columns show.
        var w: CGFloat = 760
        var h: CGFloat = 900

        let view: AnyView
        if code.hasPrefix("dossier:") {
            // PROTOTYPE: the legal-dossier variants. Usage: --snapshot dossier:gemini:55203 out.png [h]
            // or dossier:claude:55203 . Optional language via env not needed (EN default).
            let rest = String(code.dropFirst("dossier:".count))
            let parts = rest.split(separator: ":", maxSplits: 1).map(String.init)
            let variant: KBLIDossierView.Variant = (parts.first == "gemini") ? .gemini : .claude
            let target = parts.count > 1 ? parts[1] : "55203"
            let argH = args.count > idx + 3 ? Double(args[idx + 3]) : nil
            w = 760; h = CGFloat(argH ?? 2400)
            if let k = state.store.code(target) {
                view = AnyView(KBLIDossierView(kbli: k, variant: variant, scrolls: false)
                    .environmentObject(state).environmentObject(lang)
                    .frame(width: 760, alignment: .top).frame(height: h, alignment: .top).clipped().background(Theme.antracite))
            } else {
                view = AnyView(EmptyDetail(text: "code \(target) not found"))
            }
        } else if code.hasPrefix("registry:footer:") {
            // D4c.1 QA: isolate just the footer's Y-region (guilloché band + "Ask Zantara") without
            // a huge full-card image to eyeball — renders the full card top-aligned inside a wide
            // frame, then a large negative offset + small clipped viewport acts as a crop window.
            // Usage: --snapshot registry:footer:55203 out.png [yOffset]  (yOffset default -2900,
            // tuned empirically for a typical card; pass a 4th CLI arg to nudge it if a given code's
            // card is longer/shorter than average). MUST sit before the broader `registry:` prefix
            // check below — Swift's if/else-if is evaluated top-to-bottom and "registry:footer:X"
            // also starts with "registry:", so the generic case would always intercept it first
            // (found live: it did, on the first attempt — the generic case stripped only "registry:",
            // leaving target="footer:55203", which doesn't resolve to a real code and fell through
            // to an EmptyDetail built WITHOUT .environmentObject(lang) → crash).
            let target = String(code.dropFirst("registry:footer:".count))
            let yOffset = args.count > idx + 3 ? (Double(args[idx + 3]) ?? -2900) : -2900
            if let k = state.store.code(target) {
                w = 760; h = 500
                view = AnyView(
                    KBLIRegistryView(kbli: k, scrolls: false).environmentObject(state).environmentObject(lang)
                        .frame(width: 760, alignment: .top)
                        .offset(y: yOffset)
                        .frame(width: w, height: h, alignment: .top)
                        .clipped()
                        .background(Theme.antracite)
                )
            } else {
                view = AnyView(EmptyDetail(text: "code \(target) not found"))
            }
        } else if code.hasPrefix("registry:") {
            // PROTOTYPE: the synthesised "Registry Dossier" (variant D). Tall canvas so the full
            // scroll is captured off-screen. Usage: --snapshot registry:55203 out.png [height]
            let target = String(code.dropFirst("registry:".count))
            let argH = args.count > idx + 3 ? Double(args[idx + 3]) : nil
            w = 760; h = CGFloat(argH ?? 3200)
            if let k = state.store.code(target) {
                view = AnyView(KBLIRegistryView(kbli: k, scrolls: false).environmentObject(state).environmentObject(lang)
                    .frame(width: 760, alignment: .top).frame(height: h, alignment: .top).clipped().background(Theme.antracite))
            } else {
                view = AnyView(EmptyDetail(text: "code \(target) not found"))
            }
        } else if code.hasPrefix("rich:") {
            // PROTOTYPE: the enriched detail card for one code. Tall canvas so the full scroll
            // is captured off-screen (no live window to scroll). Usage: --snapshot rich:55203 out.png
            // optional 3rd arg = canvas height in pt (default 2200 for the full card; pass a
            // smaller value e.g. 1150 to capture just the top hero+verdict+keyfacts region).
            let target = String(code.dropFirst("rich:".count))
            let argH = args.count > idx + 3 ? Double(args[idx + 3]) : nil
            w = 820; h = CGFloat(argH ?? 2200)
            if let k = state.store.code(target) {
                view = AnyView(KBLIDetailRichView(kbli: k, scrolls: false).environmentObject(state).environmentObject(lang)
                    .frame(width: 820, alignment: .top).frame(height: h, alignment: .top).clipped().background(Theme.antracite))
            } else {
                view = AnyView(EmptyDetail(text: "code \(target) not found"))
            }
        } else if code == "sectors" {
            // QA: the 21-sector grid (LazyVStack materializes off-screen fine).
            view = AnyView(SearchListView().environmentObject(state).environmentObject(lang)
                .frame(width: 360, height: 900).background(Theme.antracite))
            w = 360; h = 900
        } else if code.hasPrefix("sector:") {
            // QA: that sector's codes rendered EAGERLY (a real List won't materialize lazy rows
            // off-screen — same technique as the `search` mode). Shows the exact row design.
            let letter = String(code.dropFirst("sector:".count))
            let sv = SearchListView()
            let rows = state.store.codes(in: letter).prefix(18)
            view = AnyView(
                ScrollView {
                    VStack(spacing: 2) {
                        ForEach(Array(rows), id: \.kode) { k in sv.row(k).padding(.horizontal, 8) }
                    }.padding(.vertical, 10)
                }
                .environmentObject(state).environmentObject(lang)
                .frame(width: 360, height: 900).background(Theme.antracite)
            )
            w = 360; h = 900
        } else if code == "article" {
            // render the first article's markdown (QA: heading+bullets, not flat text)
            let lib = MediaLibrary()
            if let a = lib.articles.first,
               let md = try? String(contentsOf: a.url, encoding: .utf8) {
                view = AnyView(ScrollView { MarkdownView(markdown: md).padding(24) }
                    .frame(width: 760, height: 900).background(Theme.antracite))
            } else {
                view = AnyView(EmptyDetail(text: "no articles found"))
            }
        } else if code == "search" || code.hasPrefix("search:") {
            // QA-only: render the result ROWS eagerly in a VStack (a real `List` doesn't
            // materialize its lazy rows inside an off-screen NSHostingView). This shows the
            // exact row design the live `List` uses — `SearchListView.row(_:)` verbatim.
            // D3a.1: optional query after the colon (`search:football`), default stays "kopi"
            // for backward compat with existing QA scripts/muscle memory.
            let query = code.hasPrefix("search:") ? String(code.dropFirst("search:".count)) : "kopi"
            let sv = SearchListView()
            let rows = state.store.search(query).rows.prefix(14)
            view = AnyView(
                ScrollView {
                    VStack(spacing: 2) {
                        ForEach(Array(rows), id: \.kode) { k in
                            sv.row(k).padding(.horizontal, 8)
                        }
                    }.padding(.vertical, 10)
                }
                .environmentObject(state).environmentObject(lang)
                .frame(width: 380, height: 900).background(Theme.antracite)
            )
            w = 380
        } else if code == "chat" {
            // NOTE (D4c.1, 2026-08-11): this mode's OLD comment claimed to show "the empty-state
            // suggested chips" but seeds 2 messages below, so `state.messages.isEmpty` is false and
            // `ChatView.emptyState` (the medallion rosette + chips) never actually renders here — it
            // has been rendering the BUBBLE path this whole time. Use `chat:empty` (added below) for
            // the real empty-state pixel check; this mode is kept as-is for bubble QA.
            state.messages = [
                ChatMessage(role: .user, text: "Posso aprire una PT PMA per il codice 56101 (ristorante) a Bali?"),
                ChatMessage(role: .zantara, text: "Sì. Il KBLI 56101 (Restoran) è aperto agli investitori esteri (PMA) e NON è toccato dalla moratoria Bali del 13 maggio 2026, che colpisce solo le attività a rischio basso/medio-basso. Capitale minimo PT PMA: IDR 10 miliardi di investimento, IDR 2,5 miliardi versati per ogni KBLI a 2 cifre.")
            ]
            view = AnyView(ChatView().environmentObject(state).environmentObject(lang)
                .frame(width: 820, height: 900).background(Theme.antracite))
            w = 820
        } else if code == "chat:empty" {
            // D4c.1 QA: the ACTUAL empty-conversation state — guilloché medallion rosette behind
            // the suggested-question chips (D4 spec item 2). `state.messages` starts empty, so
            // `ChatView.emptyState` is what renders (unlike plain `chat` above).
            state.messages = []
            view = AnyView(ChatView().environmentObject(state).environmentObject(lang)
                .frame(width: 820, height: 900).background(Theme.antracite))
            w = 820
        } else if code.hasPrefix("empty:") {
            // D4c.1 QA: pixel-verify each parametric `EmptyDetail.Kind` surface directly, off-screen
            // — no CLI path existed for these before this pass (D4's kind param was never snapshot-
            // tested per-case). Usage: --snapshot empty:noSelection|noResults|mediaEmpty|chat out.png [h]
            let kindName = String(code.dropFirst("empty:".count))
            let kind: EmptyDetail.Kind
            let text: String
            switch kindName {
            case "noResults":  kind = .noResults;  text = lang.t("search.empty")
            case "mediaEmpty": kind = .mediaEmpty; text = lang.t("search.pick")
            case "chat":       kind = .chatColumn; text = lang.t("chat.lead")
            default:           kind = .noSelection; text = lang.t("search.pick")
            }
            let argH = args.count > idx + 3 ? Double(args[idx + 3]) : nil
            w = 480; h = CGFloat(argH ?? 520)
            view = AnyView(EmptyDetail(text: text, kind: kind).environmentObject(lang)
                .frame(width: w, height: h).background(Theme.antracite))
        } else if code == "about" {
            // D4c.1 QA: the custom About window content off-screen — normally only reachable via
            // the CommandGroup(replacing: .appInfo) menu button, no CLI path existed before this pass.
            w = 420; h = 480
            view = AnyView(AboutView().environmentObject(lang))
        } else if code == "root" || code == "sidebar" {
            // D4c.1 QA: the full 3-column shell, to pixel-verify the sidebar footer band under its
            // REAL `.listStyle(.sidebar)` vibrancy material — the one D4/D4c surface that can't be
            // isolated as a standalone subview and still mean anything (the band is meant to read
            // "quasi invisibile ma percepibile" against that specific material, not a plain fill).
            // K2 2026-09-13: optional `[width] [height]` after the out path — the register is a
            // width-sensitive surface (four columns + a sheet) and its minimum-width behaviour is
            // only provable by rendering it AT the app's minimum (1040, KBLINavigatorApp.swift).
            // Defaults unchanged, so every existing QA call site still captures 1180x800.
            w = args.count > idx + 3 ? CGFloat(Double(args[idx + 3]) ?? 1180) : 1180
            h = args.count > idx + 4 ? CGFloat(Double(args[idx + 4]) ?? 800) : 800
            UserDefaults.pinThemeOverride(Theme.mode)   // RootView re-syncs its theme from the stored override: pin the one KBLI_THEME names
            view = AnyView(RootView()
                .environmentObject(state).environmentObject(lang).environmentObject(ThemeManager(Theme.mode))
                .frame(width: w, height: h))
        } else if let k = state.store.code(code) {
            view = AnyView(KBLIDetailView(kbli: k).environmentObject(state).environmentObject(lang))
        } else {
            view = AnyView(EmptyDetail(text: "code \(code) not found (store: \(state.store.all.count))"))
        }

        let host = NSHostingView(rootView: view.frame(width: w, height: h))
        host.frame = NSRect(x: 0, y: 0, width: w, height: h)
        guard let rep = host.bitmapImageRepForCachingDisplay(in: host.bounds) else { return true }
        host.cacheDisplay(in: host.bounds, to: rep)
        if let data = rep.representation(using: .png, properties: [:]) {
            try? data.write(to: URL(fileURLWithPath: out))
            FileHandle.standardError.write("snapshot written: \(out)\n".data(using: .utf8)!)
        }
        return true
    }
}

// MARK: - Design-baseline renderer (2026-09-17)

extension Snapshot {
    /// Six named UI surfaces ("bands"), explicit --theme/--lang/--code/--text-size flags (no env-
    /// var toggles), and a FIXED 1280×800 canvas for every band — so a baseline set is directly
    /// window-to-window comparable across bands/themes/langs regardless of each band's own natural
    /// content height. Legacy `--snapshot` (above) is untouched; this is a parallel entry point.
    /// Usage: `--snapshot-band <band> --theme day|night --lang en|id --code <code>
    ///         [--width <pt>] [--height <pt>] [--text-size default|xxxLarge] [--layout-json <out.json>] <out.png>`
    /// Design loop 2026-10-09 (spec §3, §7): every band is a PAGE — the live view at the full canvas
    /// width (`--width`, default 1280; 948 = the live main pane), top-anchored, clipped at `--height`
    /// (default 800, the set's canvas; a taller value shows a page band below the fold for review).
    /// Bands: registry-table, detail-card, dossier, sheet-ledger, chat, search-results, search-results-multi.
    /// `--layout-json` writes the band's census frames (`CensusFrame`) for png_census's C-checks.
    @MainActor
    static func runBandIfRequested() -> Bool {
        let args = CommandLine.arguments
        guard let idx = args.firstIndex(of: "--snapshot-band") else { return false }
        guard args.count > idx + 1 else {
            FileHandle.standardError.write("--snapshot-band requires a value\n".data(using: .utf8)!)
            return true
        }
        let band = args[idx + 1]

        func flag(_ name: String) -> String? {
            guard let i = args.firstIndex(of: name), args.count > i + 1 else { return nil }
            return args[i + 1]
        }

        let themeArg = (flag("--theme") ?? "night").lowercased()
        let langArg = (flag("--lang") ?? "en").lowercased()
        let code = flag("--code") ?? "55101"
        let textSizeArg = (flag("--text-size") ?? "default").lowercased()
        let layoutJSONPath = flag("--layout-json")
        CensusFrame.collecting = layoutJSONPath != nil

        // The output path is the trailing CLI argument, mirroring the legacy `--snapshot` parser's
        // "last positional wins" contract — every named flag above already consumed its own value.
        guard let out = args.last, out.hasSuffix(".png") else {
            FileHandle.standardError.write("--snapshot-band requires a trailing <out.png> path\n".data(using: .utf8)!)
            return true
        }

        let state = AppState()
        let lang = LanguageManager()
        lang.lang = (langArg == "id") ? .id : .en
        Theme.mode = (themeArg == "day") ? .light : .dark
        let dynamicSize: DynamicTypeSize = (textSizeArg == "xxxlarge") ? .xxxLarge : .large

        let w = CGFloat(flag("--width").flatMap(Double.init) ?? 1280)
        let h = CGFloat(flag("--height").flatMap(Double.init) ?? 800)
        let notFound = AnyView(EmptyDetail(text: "code \(code) not found (store: \(state.store.all.count))")
            .environmentObject(lang))

        let imm = Motion.configure(args)   // --imm: the immersive twin of the band; hooks: --at-ms --reduce-motion --ribbon --scale-focus
        let content: AnyView
        var textView: AnyView?
        switch band {
        case "registry-table":
            // The live scan surface: `SearchListView` browsing the sector --code belongs to, no
            // selection (so no preview sheet) — the same view, filters and census the user sees.
            state.browsedSector = KBLIStore.sectorLetter(for: code) ?? "A"
            state.selected = nil
            content = AnyView(SearchListView()
                .environmentObject(state).environmentObject(lang)
                .frame(width: w, height: h, alignment: .top))
        case "detail-card":
            if let k = state.store.code(code) {
                content = Self.page(KBLIDetailRichView(kbli: k, scrolls: false)
                    .environmentObject(state).environmentObject(lang), width: w, height: h)
            } else { content = notFound }
        case "dossier":
            if let k = state.store.code(code) {
                content = Self.page(KBLIDossierView(kbli: k, variant: .claude, scrolls: false)
                    .environmentObject(state).environmentObject(lang), width: w, height: h)
            } else { content = notFound }
        case "registry-sheet":
            // The sheet the user opens over the table (`SearchListView.sheetLayer`): flat by default, the live layout with --imm.
            // --sheet-open expands it, which is where its ledger shows: the only live caller of `KBLIRegistryView`.
            if let k = state.store.code(code) {
                let open = args.contains("--sheet-open")
                let sheet = RegistryVerdictSheet(kbli: k, expanded: .constant(open), onClose: {}, scrolls: false)
                if imm {
                    content = Self.page(sheet.immersiveHost().environmentObject(state).environmentObject(lang), width: w, height: h)
                    textView = AnyView(RegistryVerdictSheet(kbli: k, expanded: .constant(open), onClose: {}, scrolls: false)
                        .immersiveHost().environmentObject(state).environmentObject(lang))
                } else {
                    content = Self.page(sheet.environmentObject(state).environmentObject(lang), width: w, height: h)
                    textView = AnyView(RegistryVerdictSheet(kbli: k, expanded: .constant(open), onClose: {}, scrolls: false)
                        .environmentObject(state).environmentObject(lang))
                }
            } else { content = notFound }
        case "live-sheet":
            // The sheet as the app MOUNTS it: `SearchListView` with a code selected, `sheetLayer` and its host and all (no `--imm`:
            // the mount decides flat or immersive, never the harness). `--sheet-open` expands it (the env the live view reads).
            // png_census C25 compares it with the flat and the immersive twins of `registry-sheet`.
            if let k = state.store.code(code) {
                if args.contains("--sheet-open") { setenv("KBLI_SHEET_EXPANDED", "1", 1) }
                state.browsedSector = KBLIStore.sectorLetter(for: code) ?? "A"
                state.selected = k
                content = AnyView(SearchListView().environmentObject(state).environmentObject(lang)
                    .frame(width: w, height: h, alignment: .top))
            } else { content = notFound }
        case "root-sheet":
            // The sheet in the REAL window (#8492 gate): RootView with its sidebar (default width) and toolbar at the window's size, a code
            // selected. The app's minimum window is 1040 pt wide, which leaves the main pane about 807 pt, not the 1040 of `live-sheet`.
            // `--width` / `--height` are the WINDOW's. png_census C27 reads it against the window's bottom edge.
            if let k = state.store.code(code) {
                if args.contains("--sheet-open") { setenv("KBLI_SHEET_EXPANDED", "1", 1) }
                state.browsedSector = KBLIStore.sectorLetter(for: code) ?? "A"
                state.selected = k
                UserDefaults.pinThemeOverride(Theme.mode)
                content = AnyView(RootView().environmentObject(state).environmentObject(lang).environmentObject(ThemeManager(Theme.mode))
                    .frame(width: w, height: h, alignment: .top))
            } else { content = notFound }
        case "sheet-ledger":
            // The registry sheet/ledger (KBLIVerdict.swift's own name for this surface) — the mono
            // UPPERCASE label↔value LedgerPlate table, `KBLIRegistryView`.
            if let k = state.store.code(code) {
                if imm {
                    content = Self.page(KBLIImmersiveLedger(kbli: k, scrolls: false)
                        .environmentObject(state).environmentObject(lang), width: w, height: h)
                    textView = AnyView(KBLIImmersiveLedger(kbli: k, scrolls: false).environmentObject(state).environmentObject(lang))
                } else {
                    content = Self.page(KBLIRegistryView(kbli: k, scrolls: false)
                        .environmentObject(state).environmentObject(lang), width: w, height: h)
                    textView = AnyView(KBLIRegistryView(kbli: k, scrolls: false).environmentObject(state).environmentObject(lang))
                }
            } else { content = notFound }
        case "chat":
            state.messages = [
                ChatMessage(role: .user, text: "Posso aprire una PT PMA per il codice \(code) a Bali?"),
                ChatMessage(role: .zantara, text: "Sì. Verifica il KBLI \(code) rispetto alla moratoria e al capitale minimo PT PMA.")
            ]
            state.chatContextCode = state.store.code(code)
            content = AnyView(ChatView().environmentObject(state).environmentObject(lang)
                .frame(width: w, height: h, alignment: .top))
        case "search-results", "search-results-multi":
            // The live result list for --code typed as a query, no selection (no preview sheet).
            state.query = code
            state.selected = nil
            // search-results-multi (spec D6): a query that lists three results or more, else no render.
            if band == "search-results-multi", state.results.rows.count < 3 {
                FileHandle.standardError.write("\(band): '\(code)' lists \(state.results.rows.count) results, need >= 3\n".data(using: .utf8)!)
                exit(5)
            }
            content = AnyView(SearchResultsBand()
                .environmentObject(state).environmentObject(lang)
                .frame(width: w, height: h, alignment: .top))
        default:
            content = AnyView(EmptyDetail(text: "unknown band \(band)").environmentObject(lang))
        }

        final class Marks { var frames: [CensusFrame] = [] }
        let marks = Marks()
        let base = content
            .environment(\.dynamicTypeSize, dynamicSize)
            .frame(width: w, height: h, alignment: .top)
            .background(Theme.antracite)
            .clipped()
        let framedView = CensusFrame.collecting
            ? AnyView(base.coordinateSpace(name: CensusFrame.space).onPreferenceChange(CensusFramesKey.self) { marks.frames = $0 })
            : AnyView(base)

        let host = NSHostingView(rootView: framedView)
        host.frame = NSRect(x: 0, y: 0, width: w, height: h)
        guard let rep = host.bitmapImageRepForCachingDisplay(in: host.bounds) else { return true }
        // The live sheet sizes itself from what it measures (`SheetFit`, `PaneKey`): a preference read into @State lays the window out
        // once more, which a single draw never reaches. The window the user has settles; these two bands render it settled.
        if ["live-sheet", "root-sheet"].contains(band) {
            for _ in 0..<12 {
                RunLoop.current.run(until: Date().addingTimeInterval(0.03))
                host.layoutSubtreeIfNeeded()
                host.cacheDisplay(in: host.bounds, to: rep)
            }
        }
        host.cacheDisplay(in: host.bounds, to: rep)
        // Written in sRGB, so a pixel reads the token's own hex: the cache comes back tagged
        // Generic RGB (paper F7F4EE read F5F1EA, lineSoft DAD8D1 read D1CFC7), which a colour-managed
        // viewer shows right but a pixel census (png_census.py) cannot match.
        let srgb = rep.converting(to: .sRGB, renderingIntent: .default) ?? rep
        if let data = srgb.representation(using: .png, properties: [:]) {
            try? data.write(to: URL(fileURLWithPath: out))
            FileHandle.standardError.write("band snapshot written: \(out)\n".data(using: .utf8)!)
        }

        if let pdfPath = flag("--pdf"), let tv = textView {
            // Content byte-diff, the encensus way: the un-scrolled View through ImageRenderer into a PDF, read back by PDFKit.
            let r = ImageRenderer(content: AnyView(tv.frame(width: w, alignment: .top).fixedSize(horizontal: false, vertical: true)
                .tracking(0.01).background(Theme.antracite)))
            let data = NSMutableData()
            r.render { size, draw in
                var box = CGRect(origin: .zero, size: size)
                guard let consumer = CGDataConsumer(data: data as CFMutableData),
                      let ctx = CGContext(consumer: consumer, mediaBox: &box, nil) else { return }
                ctx.beginPDFPage(nil); draw(ctx); ctx.endPDFPage(); ctx.closePDF()
            }
            try? (PDFDocument(data: data as Data)?.string ?? "").write(toFile: pdfPath, atomically: true, encoding: .utf8)
        }

        if let jsonPath = layoutJSONPath {
            let frames = marks.frames.map { f -> [String: Any] in
                ["name": f.name, "value": f.value, "frame": [f.rect.minX, f.rect.minY, f.rect.width, f.rect.height]] }
            var doc: [String: Any] = ["width": w, "frames": frames]
            // The record's own state as the harness reads it, beside the frames (PR 3-h-2b): a mark's value comes from
            // the record, never from the function that paints the element, and png_census FAILs one that disagrees.
            if ["detail-card", "dossier", "sheet-ledger", "chat", "registry-sheet"].contains(band), let k = state.store.code(code) {
                let bali: String
                switch KBLIVerdict.of(record: k).bali {
                case .open: bali = "open"
                case .blocked: bali = "closed"
                case .undetermined: bali = "neutral"
                }
                // `cells`: the rows the page offers to pick between (under the six-scope selector, the picked scope's).
                // One cell: nothing to choose, so no hint is drawn.
                let scs = ScaleMatrix.scopes(k.perSkala)
                let picked = ScalePath.snapshotScope ?? 0
                let pickable: [(idx: Int, row: PerSkala)] = imm && scs.count >= ScaleMatrix.listFrom
                    ? (scs.indices.contains(picked) ? scs[picked].rows : []) : k.perSkala.enumerated().map { (idx: $0.offset, row: $0.element) }
                let cells = pickable.count
                // One chip per (row, scale), named as the mark names it ("scale:row"): the SET the sheet must mark, not a count.
                let chipSet = pickable.flatMap { p in Set(p.row.skalaUsaha).intersection(ScaleMatrix.order).compactMap { sc in
                    ScaleMatrix.order.firstIndex(of: sc).map { "\($0):\(p.idx)" } } }.sorted()
                // The sheet draws no raw `pma_status` chip, only the plate, which reads the verdict; every other band draws the card's.
                let verdict = KBLIVerdict.of(record: k)
                let national: String = band == "registry-sheet" ? { switch verdict.national { case .open: return "open"; case .restricted: return "restricted"
                                                                                           case .closed: return "closed"; case .undetermined: return "neutral" } }()
                                                                 : "\(Theme.tone(k.pmaStatus ?? ""))"
                var record: [String: Any] = ["code": code, "national": national, "bali": bali,
                                             "headsup": "\(KBLIVerdict.headsUp(record: k, isID: lang.lang == .id).tone)",
                                             "cells": cells, "chipSet": chipSet]
                if let cap = verdict.nationalCap { record["cap"] = cap }
                doc["record"] = record
            }
            if ["registry-sheet", "live-sheet", "root-sheet"].contains(band) {
                // What a sheet band rendered, said by the snapshot and not by a mark (#8492 gate binding 5): png_census keys the compact head's
                // exemption and C27's "collapsed" on it, so a head.compact mark on an expanded render buys nothing.
                doc["sheet"] = ["expanded": args.contains("--sheet-open"), "immersive": imm || band != "registry-sheet"]
            }
            if let data = try? JSONSerialization.data(withJSONObject: doc, options: [.prettyPrinted, .sortedKeys]) {
                try? data.write(to: URL(fileURLWithPath: jsonPath))
                FileHandle.standardError.write("census frames written: \(jsonPath) (\(frames.count))\n".data(using: .utf8)!)
            }
        }

        return true
    }

    /// A page band: the view at full canvas width inside a ScrollView, so a page taller than the
    /// canvas shows its TOP (as the live app opens it) instead of being centred and clipped at both
    /// ends — the 2026-09-17 sheet-ledger renders lost their masthead that way.
    @MainActor
    private static func page<V: View>(_ v: V, width: CGFloat, height: CGFloat) -> AnyView {
        AnyView(ScrollView(.vertical) { v.frame(width: width, alignment: .top) }
            .scrollIndicators(.never)
            .frame(width: width, height: height, alignment: .top))
    }
}

/// Off-screen twin of the live search pane: the field bar over the results, with the focus binding
/// the live window gets from RootView.
private struct SearchResultsBand: View {
    @FocusState private var focus: RootFocus?
    var body: some View {
        VStack(spacing: 0) {
            SearchFieldBar(focusedField: $focus) { }
            SearchListView(focusedField: $focus)
        }
    }
}

extension UserDefaults {
    /// What a user's tap on the theme toggle sets, for THIS process only: `themeOverride` in the argument domain (the `-themeOverride dark` of a command line),
    /// which wins over what the app's own domain holds and over the system appearance. RootView syncs its theme from them on its first render, so a render that
    /// only sets `Theme.mode` is drawn in whatever this machine's override or appearance says (Pro's was `light`: `--theme night` drew a day window).
    static func pinThemeOverride(_ mode: Theme.Mode) {
        var d = UserDefaults.standard.volatileDomain(forName: UserDefaults.argumentDomain)
        d["themeOverride"] = mode == .dark ? "dark" : "light"
        UserDefaults.standard.setVolatileDomain(d, forName: UserDefaults.argumentDomain)
    }
}
