import SwiftUI

/// Keyboard-focus targets shared by the search field and the code list (D2, 2026-08-11) — a single
/// `@FocusState` owned here (the nearest common ancestor of both) and threaded into `SearchListView`
/// so ⌘K / `/` / Down-arrow can move focus between them and the list's own selection highlight can
/// tell "selected" apart from "selected AND this is where arrow keys currently land".
enum RootFocus: Hashable { case search, list }

/// TWO-pane NavigationSplitView (K2 2026-09-13, direction "a — registry"; was a 3-column split
/// from D3a, 2026-08-11): the native source-list sidebar (Codes / Library / Assistant) stays, and
/// the second pane is the section itself — the register table with its verdict sheet, the Library
/// list+detail pair, or the chat. The search field is pinned above the register
/// (`SearchFieldBar` — CUSTOM since D3a.1, see its doc-comment: D3a's native `.searchable` hoisted
/// into the trailing window toolbar instead).
/// Brand header (logo + wordmark + tagline) tops the sidebar. Language (EN/ID) and
/// theme (☀/☾) live in the trailing window toolbar — D3a.1 briefly moved language to the bottom
/// of the sidebar, D3a.2 (2026-08-11, Zero's direct call) moved it back next to the new theme
/// toggle; see `langToggle`/`themeToggle` doc-comments.
struct RootView: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    @EnvironmentObject var theme: ThemeManager
    /// D3a.2 (2026-08-11, Zero's direct call — supersedes D3a's "system-only, no toggle"
    /// decision): "system" (default, the app follows OS appearance) or "light"/"dark" (the user
    /// clicked `themeToggle` at least once — persists across relaunches). Read by the
    /// `systemColorScheme` onChange below to decide whether a system appearance change should
    /// actually move the needle, and by `themeToggle` itself to know which way to flip.
    @AppStorage("themeOverride") private var themeOverride: String = "system"
    /// D3a: the app follows SYSTEM appearance UNLESS `themeOverride` says otherwise (D3a.2) — this
    /// observes @Environment so `theme.mode` can be kept in sync (ThemeManager itself has no way
    /// to see the system setting on its own; RootView is the seam that watches and pushes it in).
    @Environment(\.colorScheme) private var systemColorScheme
    /// D3b: same seam as `systemColorScheme` above, for Increase Contrast.
    @Environment(\.colorSchemeContrast) private var systemContrast
    /// Read-only enumeration of the bundled media (mirrors MediaView's own `let lib = MediaLibrary()`
    /// — cheap, a handful of directory listings) so the sidebar can gate the Articles row on data
    /// (BKPM ships no articles) and preselect a first item when a Library row is tapped.
    private let lib = MediaLibrary()
    /// Controls which columns are visible. When the user opens a code's detail card we collapse
    /// the result-list column (`.detailOnly`) so the card breathes full-width; a hamburger in the
    /// toolbar brings the list back (`.all`).
    // Start with the list collapsed (.doubleColumn) because AppState preselects a code on launch,
    // so the user lands directly on a full-width detail card; the hamburger / clearing brings it back.
    @State private var columns: NavigationSplitViewVisibility = .all
    /// D2 keyboard model: which of {search field, code list} currently holds keyboard focus. D3a
    /// briefly targeted the native `.searchable` field via `.searchFocused`; D3a.1 reverted to a
    /// custom TextField's plain `.focused` (see `SearchFieldBar`) — same enum, same downstream
    /// wiring (⌘K, `/`) either way.
    @FocusState private var focusedField: RootFocus?
    @AppStorage("rowDensity") private var rowDensity: RowDensity = .comfortable
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    // Split out of `body` (D3b): adding the Increase-Contrast onChange alongside the existing
    // colorScheme/focusSearchTrigger ones pushed the modifier chain past what the type-checker
    // will infer in one expression ("unable to type-check ... in reasonable time") — breaking the
    // split view + its own modifiers into a separate `some View` property, with the environment
    // `.onChange` syncs applied to the outer `body`, is the standard fix (no behavior change).
    var body: some View {
        splitView
            // D3a: system appearance drives the theme, UNLESS the user has overridden it (D3a.2).
            // `initial: true` (macOS 14+) fires this once immediately on first render too, so a
            // fresh launch (no override yet) never shows a wrong-mode frame before the system
            // value is read, AND a launch with a stored override applies it right away instead of
            // flashing system first (`themeOverride != "system"` branch below).
            .onChange(of: systemColorScheme, initial: true) { _, newValue in
                theme.mode = themeOverride == "system" ? (newValue == .dark ? .dark : .light)
                    : (themeOverride == "dark" ? .dark : .light)
            }
            // D3b: Increase Contrast, same initial:true pattern — see Theme.pickAA /
            // ThemeManager.contrastIncreased.
            .onChange(of: systemContrast, initial: true) { _, newValue in
                theme.contrastIncreased = (newValue == .increased)
            }
            // ⌘K fired from the menu-bar Commands group (App scene scope, no view-local
            // FocusState of its own) — jump into Search and focus the field. A counter (not a
            // Bool) so repeat presses re-fire even if the field is already focused.
            .onChange(of: state.focusSearchTrigger) { _, _ in
                state.section = .search
                focusedField = .search
            }
    }

    private var splitView: some View {
        // K2 2026-09-13, direction "a — registry": TWO panes, not three. The register is a wide
        // dense table (code · activity · Bali · OSS risk) that needs the whole main pane to show
        // its verdict columns, and the code the reader picks answers in a sheet over that table
        // instead of in a third column. Media keeps its own list+detail pair, nested here as an
        // HSplitView so nothing about the Library browse is lost in the move.
        NavigationSplitView(columnVisibility: $columns) {
            sidebarColumn
                .safeAreaInset(edge: .top) { brandHeader }
                .safeAreaInset(edge: .bottom) { sidebarFooterBand }
                .navigationSplitViewColumnWidth(min: 200, ideal: 232, max: 300)
        } detail: {
            mainColumn
        }
        // D3a.2: language + theme back in the trailing window toolbar (Zero's direct call,
        // reverting D3a.1's sidebar-footer placement for language and D3a's system-only theme).
        .toolbar {
            langToggle
            themeToggle
        }
        .tint(Theme.accent)
        .background(Theme.antracite)
    }

    private var brandHeader: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 11) {
                BZLogo(size: 32)
                VStack(alignment: .leading, spacing: 1) {
                    Text(lang.t("app.title")).font(Theme.scalable(15, weight: .bold)).foregroundStyle(Theme.white)
                    Text("Bali Zero · KBLI 2025").font(Theme.scalable(10)).foregroundStyle(Theme.faint)
                }
                Spacer(minLength: 0)
            }
            FactRule(width: 36)
        }
        .padding(.horizontal, 16).padding(.top, 14).padding(.bottom, 8)
        .background(Theme.ink)
    }

    /// D4 "Anima Indonesiana" (2026-08-11): a subtle band at the bottom of the sidebar — a small
    /// micro-guilloché rosette (~28pt) + a "1945 ·──────· 2045" mono hairline row. Deliberately NO
    /// opaque background (unlike `brandHeader` above, which is declared-opaque per Zero's D3a
    /// framing "meglio header opaco dichiarato che glass illeggibile" — that ruling was about
    /// TEXT legibility on a header that must always read clearly): this band is meant to sit
    /// UNDER the sidebar's own `.listStyle(.sidebar)` vibrancy material, "quasi invisibile ma
    /// percepibile" — a transparent overlay only, so the system material still shows through.
    private var sidebarFooterBand: some View {
        // Draft's `'band'` canvas role is `guilloche()` — a wavy multi-row band, NOT `rosette()`
        // (an earlier v1 pass used a small rosette here; wrong motif family, see D4Decor.swift
        // header). The "1945 ·──────· 2045" row is a separate text overlay in the draft too (plain
        // HTML there, a SwiftUI Text here) — never drawn by the canvas itself.
        // D4c (2026-08-11): alpha raised from `decorAmbientAlpha + 0.04` to the dedicated
        // `decorSidebarBandAlpha` token (day .20→.24, night .14→.17) — Zero found the launch value
        // "quasi invisibile"; same geometry otherwise.
        VStack(spacing: 3) {
            GuillocheField(height: 64, alpha: Theme.decorFieldAlpha, rows: 10)
            Text("1945 ·──────· 2045")
                .font(Theme.scalable(9, design: .monospaced))
                .foregroundStyle(Theme.faint.opacity(Theme.decorAmbientAlpha))
        }
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity)
    }

    // MARK: sidebar (D3a, 2026-08-11) — native source-list, replaces the pill-segmented tabs.

    /// One selectable row in the sidebar. Library has 3 destinations (Book / Articles / Chapters)
    /// because MediaView itself already distinguishes those 3 as separate List sections — the
    /// sidebar mirrors that distinction rather than collapsing it to one generic "Media" entry.
    private enum SidebarItem: Hashable {
        case codes, libraryBook, libraryArticles, libraryChapters, assistant
    }

    /// Derived, not stored: the sidebar's selection is always a PROJECTION of `state.section` /
    /// `state.mediaSelection`, never a second source of truth that could drift from it. Tapping a
    /// Library row switches to the Media section and, if the current selection isn't already in
    /// that category, preselects its first item — so the row lands on real content instead of an
    /// empty detail pane — without touching MediaView's own list/sections at all.
    private var sidebarSelection: Binding<SidebarItem?> {
        Binding(
            get: {
                switch state.section {
                case .search: return .codes
                case .chat:   return .assistant
                case .media:
                    switch state.mediaSelection {
                    case .article: return .libraryArticles
                    case .chapter: return .libraryChapters
                    default:       return .libraryBook
                    }
                }
            },
            set: { newValue in
                guard let newValue else { return }
                switch newValue {
                case .codes:     state.section = .search
                case .assistant: state.section = .chat
                case .libraryBook:
                    state.section = .media
                    if case .book = state.mediaSelection {} else {
                        state.mediaSelection = lib.books.first.map { .book($0) }
                    }
                case .libraryArticles:
                    state.section = .media
                    if case .article = state.mediaSelection {} else {
                        state.mediaSelection = lib.articles.first.map { .article($0) }
                    }
                case .libraryChapters:
                    state.section = .media
                    if case .chapter = state.mediaSelection {} else {
                        state.mediaSelection = lib.chapters.first.map { .chapter($0) }
                    }
                }
            }
        )
    }

    /// Native source-list sidebar: Codes (Search) / Library (Book, Articles, Chapters) / Assistant
    /// (Zantara). Deliberately NO custom `.background` here — `.listStyle(.sidebar)` renders the
    /// system vibrancy/material on its own, and painting a flat fill behind it would defeat that
    /// (D3a materials pass). `brandHeader` stays opaque `Theme.ink` on top via `.safeAreaInset` —
    /// the logo + wordmark + tagline need reliable contrast, and vibrancy behind small brand text
    /// reads as illegible glass more often than it reads as depth; a declared-opaque header beats
    /// that (Zero's own framing for this pass: "meglio header opaco dichiarato che glass illeggibile").
    private var sidebarColumn: some View {
        List(selection: sidebarSelection) {
            Section(lang.t("nav.section.codes")) {
                Label(lang.t("nav.search"), systemImage: "magnifyingglass").tag(SidebarItem.codes)
            }
            Section(lang.t("nav.section.library")) {
                // Gate on the DATA, not on AppVariant (mirrors MediaView's own established
                // convention) — BKPM excludes Resources/articles/ at build time, so lib.articles is
                // empty there; showing the row anyway would land on a Media list with no Articles
                // section to show for it (MediaView already hides that section when empty).
                if !lib.articles.isEmpty {
                    Label(lang.t("media.articles"), systemImage: "doc.text").tag(SidebarItem.libraryArticles)
                }
                Label(lang.t("media.book"), systemImage: "book.closed").tag(SidebarItem.libraryBook)
                Label(lang.t("media.chapters"), systemImage: "book.pages").tag(SidebarItem.libraryChapters)
            }
            Section(lang.t("nav.section.assistant")) {
                Label(lang.t("nav.chat"), systemImage: "bubble.left.and.bubble.right").tag(SidebarItem.assistant)
            }
        }
        .listStyle(.sidebar)
    }

    // MARK: content column (browser / media list / chat) — search (`SearchFieldBar`) lives on a
    // `.safeAreaInset(edge: .top)` scoped to the `.search` case only (not the outer Group), so the
    // field simply isn't part of the view tree while Media/Chat are showing — no dead search bar
    // that types into nothing.

    private var mainColumn: some View {
        Group {
            switch state.section {
            case .search:
                // D3a keyboard model: ⌘K (Commands menu) and `/` (SearchListView's list) both still
                // land here via the same RootFocus.search case. Return still hands off to the list.
                SearchListView(focusedField: $focusedField)
                    .safeAreaInset(edge: .top) {
                        SearchFieldBar(focusedField: $focusedField) { handOffToList() }
                    }
            case .media:
                // The Library keeps its two panes — the list that was the content column and the
                // detail that was the detail column — inside the single main pane.
                HSplitView {
                    MediaView().frame(minWidth: 260, idealWidth: 320, maxWidth: 420)
                    MediaDetailHost().frame(maxWidth: .infinity)
                }
            case .chat:
                ChatView()
            }
        }
        .background(Theme.antracite)
    }

    /// Move keyboard focus from the search field into the code list. The initial highlight is the
    /// TABLE's call (`SearchListView.selectVisibleOnFocus`): `AppState.visibleRows` knows neither
    /// verdict filter and holds no rows for the whole register, so choosing here picked rows the
    /// table was hiding (council K2 round 1).
    private func handOffToList() {
        focusedField = .list
    }

    // The former third column is gone (K2 2026-09-13): a picked code is answered by
    // `RegistryVerdictSheet` over the table, which carries the verdict once and embeds the
    // registry dossier card under it on demand. The A/B/C card-variant compare switch went with
    // it — `AppState.cardVariant` has had one shipped value (D, the registry dossier) since
    // 2026-08-11 and the two prototype cards are still reachable off-screen through
    // `Snapshot.swift` (`--snapshot rich:<code>` / `dossier:claude|gemini:<code>`).

    /// D3a.1 moved this to the bottom of the sidebar; D3a.2 (2026-08-11, Zero's direct call) moved
    /// it back HERE, the trailing window toolbar — his literal ask was "rimetti i bottoni... in
    /// alto a destra". D3a.1's own reasoning (language must stay reachable outside the Search
    /// section) still holds with this placement: the window toolbar is visible in every section,
    /// same as the sidebar was.
    private var langToggle: some ToolbarContent {
        ToolbarItem(placement: .primaryAction) {
            Picker("", selection: $lang.lang) {
                ForEach(LanguageManager.Lang.allCases, id: \.self) { l in
                    Text(l.rawValue.uppercased()).tag(l)
                }
            }
            .pickerStyle(.segmented)
            .frame(width: 130)
        }
    }

    /// D3a.2 (2026-08-11, Zero's direct call — supersedes D3a's system-only decision): a
    /// user-facing ☀/☾ toggle is back, next to `langToggle`. Each tap sets `themeOverride` to the
    /// OPPOSITE of the current mode and applies it immediately; the override then persists across
    /// relaunches (via @AppStorage) and system appearance changes are ignored until the user taps
    /// again (see the `systemColorScheme` onChange in `body`). There is no separate "back to
    /// system" control — matching Zero's literal ask (bring the toggle back), not a 3-state
    /// Auto/Light/Dark redesign.
    private var themeToggle: some ToolbarContent {
        ToolbarItem(placement: .primaryAction) {
            Button {
                let next: Theme.Mode = theme.mode == .dark ? .light : .dark
                themeOverride = next == .dark ? "dark" : "light"
                theme.mode = next
            } label: {
                Image(systemName: theme.mode == .dark ? "moon.fill" : "sun.max.fill")
            }
            .help(theme.mode == .dark ? "Switch to Light" : "Switch to Dark")
        }
    }
}

/// Shown wherever nothing is selected / nothing matched — a calm dark empty state. D4 "Anima
/// Indonesiana" (2026-08-11) made this parametric by `Kind`: `text` (existing per-caller message)
/// is unconditional, each kind additionally layers its own procedural decoration (D4Decor.swift)
/// plus, for the two search-related kinds, a hint row. Under Increase Contrast every decoration's
/// own `Theme.decorationsVisible` check removes it from the view tree entirely (not just fades it)
/// — the VStack simply collapses to text-only, no reserved dead space.
struct EmptyDetail: View {
    enum Kind {
        /// The flagship "tela principale" — the detail column with nothing selected. Full
        /// archipelago constellation + the 1945→2045 gold arc + a search-example hint.
        case noSelection
        /// SearchListView when a query matches zero rows. Compact broken cartographic line + a
        /// spelling/code hint.
        case noResults
        /// MediaDetailHost with nothing selected. Reduced constellation (no arc).
        case mediaEmpty
        /// ChatPlaceholderColumn (content column while the Chat section is active). Small
        /// zantara-tinted guilloché rosette.
        case chatColumn
    }
    let text: String
    var kind: Kind = .noSelection
    @EnvironmentObject var lang: LanguageManager

    var body: some View {
        VStack(spacing: 14) {
            decoration
            Text(text).font(Theme.bodyFont).foregroundStyle(Theme.muted).multilineTextAlignment(.center)
            if let hint {
                Text(hint).font(Theme.scalable(11)).foregroundStyle(Theme.faint).multilineTextAlignment(.center)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Theme.antracite)
    }

    private var hint: String? {
        switch kind {
        case .noSelection: lang.t("empty.hint.trySearch")
        case .noResults:   lang.t("empty.hint.spelling")
        case .mediaEmpty, .chatColumn: nil
        }
    }

    @ViewBuilder private var decoration: some View {
        switch kind {
        case .noSelection:
            ArchipelagoConstellation(showArc: true)
        case .noResults:
            CartographicSquiggle()
        case .mediaEmpty:
            ArchipelagoConstellation(showArc: false, height: 90)
        case .chatColumn:
            GuillocheRosette(tint: Theme.zantara, size: 84)
        }
    }
}

/// In the chat section the content column is intentionally minimal — the chat lives in detail.
struct ChatPlaceholderColumn: View {
    @EnvironmentObject var lang: LanguageManager
    var body: some View {
        EmptyDetail(text: lang.t("chat.lead"), kind: .chatColumn)
    }
}
