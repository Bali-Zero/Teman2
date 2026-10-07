import SwiftUI

/// The register itself — direction "a — registry" (K2, 2026-09-13, replacing the 2026-06-24
/// sector-grid browser). One dense table across the whole main column: code · activity · Bali ·
/// OSS risk, with the verdict rendered ON THE ROW. The sector grid became a filter menu (the
/// browse is preserved, the extra navigation level is not), and the code the reader picks answers
/// in a bottom sheet over the table instead of a third column.
///
/// The design brief for this direction was chosen because the defect it cures lives HERE: the
/// scan is where a client decides which codes are worth opening, and until today the scan said
/// "open" for every code the corpus could not classify and invented a risk class for 217 records
/// that carry none. The row now has a third state and a "no class on record" cell, and the line
/// under the table counts both over the whole catalogue.
struct SearchListView: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    /// D2 keyboard model: shared with RootView's search field so `/` (this list → search) and
    /// Down-arrow (search → this list) can move focus, and so a row can tell "selected" apart from
    /// "selected AND the list currently owns keyboard focus" (the focus-ring case). Defaulted to a
    /// throwaway unwired binding so `SearchListView()` (Snapshot.swift's off-screen QA renders,
    /// which have no live window/focus anyway) keeps compiling without threading focus through.
    /// `var` (not `let`) is load-bearing here: a `let` with an inline default is EXCLUDED entirely
    /// from Swift's synthesized memberwise init (compiler-verified), which would drop the
    /// parameter RootView passes.
    var focusedField: FocusState<RootFocus?>.Binding = FocusState<RootFocus?>().projectedValue
    @AppStorage("rowDensity") private var rowDensity: RowDensity = .comfortable

    /// QA hooks (same convention as `KBLI_OPEN_ALL` / `KBLI_SHEET_EXPANDED`): the third state and
    /// the classless records are a handful of rows in 1,559, so an off-screen snapshot has to be
    /// able to open on them — `KBLI_FILTER_BALI=undetermined`, `KBLI_FILTER_RISK=absent`. Unset in
    /// every normal launch; the same two filters are reachable by hand from the pickers above.
    @State private var baliFilter: BaliFilter =
        BaliFilter(rawValue: ProcessInfo.processInfo.environment["KBLI_FILTER_BALI"] ?? "") ?? .all
    @State private var riskFilter: RiskFilter =
        RiskFilter(rawValue: ProcessInfo.processInfo.environment["KBLI_FILTER_RISK"] ?? "") ?? .all
    /// QA hook, same convention as `KBLIRegistryView`'s `KBLI_OPEN_ALL`: an off-screen snapshot
    /// has no way to click the grabber, so `KBLI_SHEET_EXPANDED=1` opens the dossier under the
    /// verdict for the render. Unset in every normal launch.
    @State private var sheetExpanded = ProcessInfo.processInfo.environment["KBLI_SHEET_EXPANDED"] == "1"

    private var isID: Bool { lang.lang == .id }
    private var listHasFocus: Bool { focusedField.wrappedValue == .list }
    private var searching: Bool { !state.query.trimmingCharacters(in: .whitespaces).isEmpty }

    // MARK: filters — the third state is reachable, not just visible

    enum BaliFilter: String, CaseIterable, Identifiable {
        case all, open, blocked, closedNational, undetermined
        var id: String { rawValue }
        func title(_ isID: Bool) -> String {
            switch self {
            case .all: return isID ? "Semua" : "All"
            case .open: return isID ? "Terbuka" : "Open"
            case .blocked: return isID ? "Diblokir" : "Blocked"
            case .closedNational: return isID ? "Tertutup (nasional)" : "Closed (national)"
            case .undetermined: return isID ? "Tidak ditentukan" : "Not determined"
            }
        }
    }

    enum RiskFilter: String, CaseIterable, Identifiable {
        case all, low, mediumLow, mediumHigh, high, absent
        var id: String { rawValue }
        func title(_ isID: Bool) -> String {
            switch self {
            case .all: return isID ? "Semua" : "All"
            case .low: return isID ? "Rendah" : "Low"
            case .mediumLow: return isID ? "Menengah Rendah" : "Medium-Low"
            case .mediumHigh: return isID ? "Menengah Tinggi" : "Medium-High"
            case .high: return isID ? "Tinggi" : "High"
            case .absent: return RiskCell.absentText(isID: isID)
            }
        }
        /// `KBLIVerdict.riskRank`: 1 low · 2 medium-low · 3 medium-high · 4 high · 0 unrecognised.
        var rank: Int? {
            switch self {
            case .low: return 1
            case .mediumLow: return 2
            case .mediumHigh: return 3
            case .high: return 4
            case .all, .absent: return nil
            }
        }
    }

    // MARK: rows

    /// The row set before the preview cap: search hits, or the browsed sector, or the whole
    /// register — then the two verdict filters.
    private var matchedRows: [KBLI] {
        var rows: [KBLI]
        if searching { rows = state.results.rows }
        else if let sec = state.browsedSector { rows = state.store.codes(in: sec) }
        else { rows = state.store.all }
        if baliFilter != .all || riskFilter != .all {
            let store = state.store
            rows = rows.filter { passes(RegistryCensus.verdict($0, in: store)) }
        }
        return rows
    }

    private func passes(_ v: KBLIVerdict) -> Bool {
        if baliFilter != .all && baliState(baliFilter).contains(VerdictBadge.state(for: v)) == false { return false }
        switch riskFilter {
        case .all: break
        case .absent: if v.risk != .absent { return false }
        default:
            guard case .known(let label) = v.risk, KBLIVerdict.riskRank(label) == riskFilter.rank else { return false }
        }
        return true
    }

    /// "Not determined" is ONE filter over TWO states — the Bali axis and the national one, which
    /// render the same dashed cell but are different facts (council round 1, codex-gpt-5.6-sol).
    /// A reader filtering for what the records cannot say wants both.
    private func baliState(_ f: BaliFilter) -> [VerdictBadge.State] {
        switch f {
        case .all: return []
        case .open: return [.open]
        case .blocked: return [.blocked]
        case .closedNational: return [.closedNational]
        case .undetermined: return [.undetermined, .undeterminedNational]
        }
    }

    /// Every matched row, always. The first version opened the whole register on a 25-row page
    /// with a "Show all" button; council K2 round 2 (codex-gpt-5.6-sol) showed the page broke the
    /// sheet's contract — a selected code beyond row 25 (the launch code, 55203, is one) answered
    /// over a table that did not hold it. A LazyVStack materialises only what is on screen, so the
    /// page bought nothing and hid records: the register now has no truncation of its own. The
    /// store's 300-hit search cap is the one cap left, and the footer states it.
    private var visibleRows: [KBLI] { matchedRows }

    // MARK: body

    var body: some View {
        VStack(spacing: 0) {
            filterBar
            columnHeader
            // Expanded, the sheet takes the pane and the table keeps a three-row peek: a dossier
            // squeezed under a full-height table was a strip nobody could read (render of
            // 68112 at 1440x1400, K2 2026-09-14). Collapse gives the table its height back.
            tableBody
                .frame(maxHeight: (sheetExpanded && state.selected != nil) ? 132 : .infinity)
            footerBar          // the census stays visible ABOVE the sheet, never under it
            sheetLayer
        }
        .background(Theme.antracite)
        // A filter, a sector or a query that hides the selected code closes its sheet: a verdict
        // sheet over a table that no longer holds the code was an open-code answer sitting over an
        // all-blocked list (council K2 round 1, both seats).
        .onChange(of: baliFilter) { _, _ in dropHiddenSelection() }
        .onChange(of: riskFilter) { _, _ in dropHiddenSelection() }
        .onChange(of: state.browsedSector) { _, _ in dropHiddenSelection() }
        .onChange(of: state.query) { _, _ in dropHiddenSelection() }
        // RootView's hand-off picks from `AppState.visibleRows`, which knows nothing of the two
        // verdict filters and holds no rows for the whole register; the table corrects it here.
        .onChange(of: listHasFocus) { _, focused in if focused { selectVisibleOnFocus() } }
        // The other direction: a selection made OUTSIDE the table (a related-code card in the
        // dossier, a deep link) that the current filters hide reveals itself — filters, sector and
        // query clear — instead of answering over a table that does not hold it (council K2
        // round 2, codex-gpt-5.6-sol).
        .onChange(of: state.selected?.id) { _, _ in revealSelectionIfHidden() }
    }

    private var selectionIsHidden: Bool {
        guard let s = state.selected else { return false }
        return matchedRows.contains { $0.id == s.id } == false
    }

    private func dropHiddenSelection() {
        guard state.section == .search, selectionIsHidden else { return }
        state.selected = nil
        sheetExpanded = false
    }

    /// Clears the LEAST that hides the code: the two verdict filters first, and the sector and the
    /// query only when the code is outside them too — a reader's search is not wiped to reveal a
    /// code the search already holds.
    private func revealSelectionIfHidden() {
        guard state.section == .search, let s = state.selected, selectionIsHidden else { return }
        baliFilter = .all
        riskFilter = .all
        let base: [KBLI] = searching ? state.results.rows
            : (state.browsedSector.map { state.store.codes(in: $0) } ?? state.store.all)
        if base.contains(where: { $0.id == s.id }) { return }
        state.browsedSector = nil
        state.query = ""
    }

    private func selectVisibleOnFocus() {
        guard state.section == .search else { return }
        if state.selected == nil || selectionIsHidden { state.selected = visibleRows.first }
    }

    /// A `ScrollView`+`LazyVStack`, not a `List`: the selection/arrow-key behaviour a `List` gives
    /// for free is reimplemented below in ~20 lines, and in exchange the register renders in the
    /// off-screen snapshot path (`Snapshot.swift` → `NSHostingView.cacheDisplay`), where a real
    /// `List` never materialises its lazy rows — the app's only headless QA camera. A table whose
    /// honesty cannot be photographed is a table nobody can check.
    @ViewBuilder private var tableBody: some View {
        if state.store.all.isEmpty {
            banner(lang.t("data.missing"))
        } else if visibleRows.isEmpty {
            EmptyDetail(text: lang.t("search.empty"), kind: .noResults)
        } else {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 1) {
                        ForEach(visibleRows) { k in
                            row(k, isSelected: state.selected?.id == k.id, isListFocused: listHasFocus, isID: isID)
                                .id(k.id)
                                .contentShape(Rectangle())
                                .onTapGesture {
                                    state.selected = k
                                    focusedField.wrappedValue = .list
                                }
                        }
                    }
                    .padding(.horizontal, 6).padding(.vertical, 4)
                }
                // A `List` scrolled its selection into view for free; a LazyVStack does not, so
                // arrow-key navigation used to continue invisibly past the viewport (council
                // round 1, codex-gpt-5.6-sol).
                .onChange(of: state.selected?.id) { _, id in
                    guard let id else { return }
                    withAnimation(.easeInOut(duration: 0.12)) { proxy.scrollTo(id, anchor: .center) }
                }
            }
            .background(Theme.antracite)
            .focusable()
            .focused(focusedField, equals: .list)
            .onKeyPress(.upArrow) { moveSelection(-1) }
            .onKeyPress(.downArrow) { moveSelection(+1) }
            .onKeyPress("/") { focusedField.wrappedValue = .search; return .handled }
            // Return on a selected row opens the whole dossier under the verdict — the keyboard
            // reaches the same depth the grabber and the footer button do.
            .onKeyPress(.return) {
                guard state.selected != nil else { return .ignored }
                sheetExpanded = true
                return .handled
            }
        }
    }

    /// Arrow-key navigation over the rows currently on screen. Clamps at both ends (no wrap: a
    /// register that jumps from the last row back to the first reads as a glitch, not a feature).
    private func moveSelection(_ delta: Int) -> KeyPress.Result {
        let rows = visibleRows
        guard rows.isEmpty == false else { return .ignored }
        guard let current = state.selected, let i = rows.firstIndex(where: { $0.id == current.id }) else {
            state.selected = rows.first
            return .handled
        }
        let next = min(max(i + delta, 0), rows.count - 1)
        state.selected = rows[next]
        return .handled
    }

    // MARK: a single code row (shared with Snapshot.swift's off-screen QA renders)

    func row(_ k: KBLI, isSelected: Bool = false, isListFocused: Bool = false, isID: Bool = false) -> some View {
        KBLIRegistryRow(kbli: k, isSelected: isSelected, isListFocused: isListFocused,
                        isID: isID, density: rowDensity)
    }

    // MARK: chrome

    /// Native popup buttons, not custom `Menu` labels: a `.menuStyle(.borderlessButton)` label
    /// renders only its first text element off-screen (measured on the first render of this
    /// window), so the selected value — the whole point of a filter control — was invisible in
    /// the snapshot. A `Picker` also states its selection to VoiceOver without extra wiring.
    private var filterBar: some View {
        HStack(spacing: 10) {
            filterTitle(isID ? "SEKTOR" : "SECTOR", active: state.browsedSector != nil)
            Picker(selection: Binding(get: { state.browsedSector },
                                      set: { state.browsedSector = $0 })) {
                Text(isID ? "Semua sektor" : "All sectors").tag(String?.none)
                ForEach(state.store.sectors) { sec in
                    Text("\(sec.letter) — \(isID ? sec.id_ : sec.en) (\(sec.count))").tag(String?.some(sec.letter))
                }
            } label: { EmptyView() }
            .pickerStyle(.menu).controlSize(.small).frame(maxWidth: 260)
            .accessibilityLabel(isID ? "Saring menurut sektor" : "Filter by sector")

            Spacer(minLength: 0)

            filterTitle("BALI", active: baliFilter != .all)
            Picker(selection: $baliFilter) {
                ForEach(BaliFilter.allCases) { f in Text(f.title(isID)).tag(f) }
            } label: { EmptyView() }
            .pickerStyle(.menu).controlSize(.small).frame(maxWidth: 190)
            .accessibilityLabel(isID ? "Saring menurut putusan Bali" : "Filter by Bali verdict")

            filterTitle(isID ? "RISIKO OSS" : "OSS RISK", active: riskFilter != .all)
            Picker(selection: $riskFilter) {
                ForEach(RiskFilter.allCases) { f in Text(f.title(isID)).tag(f) }
            } label: { EmptyView() }
            .pickerStyle(.menu).controlSize(.small).frame(maxWidth: 190)
            .accessibilityLabel(isID ? "Saring menurut kelas risiko OSS" : "Filter by OSS risk class")
        }
        .tint(Theme.accent)
        .frame(maxWidth: .infinity)
        .padding(.horizontal, 14).padding(.vertical, 7)
        .background(Theme.ink.opacity(0.9))
        .overlay(alignment: .bottom) { Rectangle().fill(Theme.hairline).frame(height: 1) }
    }

    private func filterTitle(_ text: String, active: Bool) -> some View {
        Text(text)
            .font(Theme.scalable(9.5, weight: .heavy, design: .monospaced)).tracking(0.8)
            .foregroundStyle(active ? Theme.accent : Theme.faint)
            .lineLimit(1).fixedSize()    // "OSS RISK" must not wrap to "OSS / RISK" at 1040pt
            .accessibilityHidden(true)   // the picker beside it carries the accessible name
    }

    private var columnHeader: some View {
        HStack(spacing: 12) {
            Text("KBLI").frame(width: rowDensity == .compact ? 52 : 58, alignment: .leading)
            Text(isID ? "AKTIVITAS" : "ACTIVITY").frame(maxWidth: .infinity, alignment: .leading)
            Text("BALI").frame(width: rowDensity == .compact ? 116 : 132, alignment: .center)
            Text(isID ? "RISIKO OSS" : "OSS RISK").frame(width: rowDensity == .compact ? 116 : 132, alignment: .center)
        }
        .font(Theme.scalable(9.5, weight: .heavy, design: .monospaced)).tracking(0.9)
        .foregroundStyle(Theme.faint)
        .padding(.horizontal, 16).padding(.vertical, 7)
        .overlay(alignment: .bottom) { Rectangle().fill(Theme.hairline).frame(height: 1) }
        .accessibilityHidden(true)   // the rows carry their own combined labels
    }

    /// The census: what is on screen, and what the WHOLE catalogue says about the two axes this
    /// app used to fabricate. Both counts come from `RegistryCensus` (every record, one rule) —
    /// not from a constant that could outlive the corpus it described.
    private var footerBar: some View {
        let census = RegistryCensus.cached(for: state.store)
        let matched = matchedRows     // one pass per render, not three
        // The total is what this table actually holds — NOT `results.total`, which counts matches
        // the search never returned (the store caps a query at 300 rows) and which, next to a
        // filtered row set, was simply a different number about a different thing (council round 1,
        // codex-gpt-5.6-sol). The cap itself is stated in the line instead of hidden by it.
        let total = matched.count
        return HStack(spacing: 12) {
            Text(censusLine(total: total, census: census))
                .font(Theme.scalable(11)).foregroundStyle(Theme.muted)
                .lineLimit(2).fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 16).padding(.vertical, 9)
        .background(Theme.ink.opacity(0.9))
        .overlay(alignment: .top) { Rectangle().fill(Theme.hairline).frame(height: 1) }
        .accessibilityElement(children: .combine)
    }

    /// Two populations, and the line names both: what the table holds now, then the CATALOGUE —
    /// a one-hit search used to read "1 of 1 shown · 8 codes not determined", as if the 8 were
    /// among the 1 (council K2 round 2, codex-gpt-5.6-sol).
    private func censusLine(total: Int, census: RegistryCensus.Census) -> String {
        let n = { (v: Int) in RegistryFormat.number(v, isID: isID) }
        var line: String
        if isID {
            line = "\(n(total)) kode ditampilkan · katalog \(n(census.total)): \(n(census.notDetermined)) tidak ditentukan, \(n(census.noRiskClass)) tanpa kelas risiko"
        } else {
            line = "\(n(total)) codes shown · catalogue of \(n(census.total)): \(n(census.notDetermined)) not determined, \(n(census.noRiskClass)) without a risk class"
        }
        if searching, state.results.truncated {
            let r = state.results
            line += isID
                ? " · pencarian dibatasi pada \(n(r.rows.count)) dari \(n(r.total)) kecocokan"
                : " · search capped at \(n(r.rows.count)) of \(n(r.total)) matches"
        }
        return line
    }

    // MARK: the sheet over the table

    @ViewBuilder private var sheetLayer: some View {
        if let k = state.selected, state.section == .search {
            RegistryVerdictSheet(kbli: k, expanded: $sheetExpanded) {
                state.selected = nil
                sheetExpanded = false
            }
            .frame(maxHeight: sheetExpanded ? .infinity : 470)
            .padding(.horizontal, 12).padding(.bottom, 10).padding(.top, 6)
        }
    }

    private func banner(_ msg: String) -> some View {
        VStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(Theme.yellow).font(Theme.scalable(30))
            Text(msg).font(Theme.bodyFont).foregroundStyle(Theme.muted).multilineTextAlignment(.center)
        }
        .padding(24).frame(maxWidth: .infinity, maxHeight: .infinity).background(Theme.antracite)
    }
}
