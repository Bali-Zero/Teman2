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
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

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
            if searching {
                queryLayout
                    .frame(maxHeight: (sheetExpanded && state.selected != nil) ? 132 : .infinity)
            } else {
                // Expanded, the sheet takes the pane and the table keeps a peek: a dossier
                // squeezed under a full-height table was a strip nobody could read (render of
                // 68112 at 1440x1400, K2 2026-09-14). Collapse gives the table its height back.
                // Browse mode keeps 300 pt (the header block alone is ~150 pt of it).
                browseLayout
                    .frame(maxHeight: (sheetExpanded && state.selected != nil) ? 300 : .infinity)
            }
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
                    let firstID = visibleRows.first?.id
                    let groupStarts = searching ? [] : groupStartIDs
                    LazyVStack(spacing: 0) {
                        ForEach(visibleRows) { k in
                            // Group headers are not rows: no id of their own, outside the tap
                            // target, so selection ids, arrow order and `scrollTo` never see them.
                            VStack(spacing: 0) {
                                if groupStarts.contains(k.id) { groupHeader(k) }
                                tableRow(k, firstID: firstID)
                                    .contentShape(Rectangle())
                                    .onTapGesture {
                                        state.selected = k
                                        focusedField.wrappedValue = .list
                                    }
                            }
                            .id(k.id)
                        }
                    }
                    .padding(.vertical, 4)
                }
                // A `List` scrolled its selection into view for free; a LazyVStack does not, so
                // arrow-key navigation used to continue invisibly past the viewport (council
                // round 1, codex-gpt-5.6-sol).
                .onChange(of: state.selected?.id) { _, id in
                    guard let id else { return }
                    withAnimation(Theme.motion(reduceMotion)) { proxy.scrollTo(id, anchor: .center) }
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

    @ViewBuilder private func tableRow(_ k: KBLI, firstID: String?) -> some View {
        let selected = state.selected?.id == k.id
        if searching {
            QueryResultRow(kbli: k, isFirst: k.id == firstID, isSelected: selected, isID: isID)
        } else {
            row(k, isSelected: selected, isListFocused: listHasFocus, isID: isID)
        }
    }

    // MARK: query mode (spec §3.1) — facets · peak card + spine · census

    private static let wideBreakpoint: CGFloat = 1160

    private var queryLayout: some View {
        GeometryReader { geo in
            if geo.size.width >= Self.wideBreakpoint {
                HStack(alignment: .top, spacing: 0) {
                    VStack(alignment: .trailing, spacing: 12) {
                        facet(isID ? "SEKTOR" : "SECTOR") { sectorPicker }
                        facet("BALI") { baliPicker }
                        facet(isID ? "RISIKO OSS" : "OSS RISK") { riskPicker }
                    }
                    .tint(Theme.accent)
                    .padding(.top, 48).padding(.trailing, 32)
                    .frame(minWidth: 200, maxWidth: .infinity, alignment: .topTrailing)

                    VStack(alignment: .leading, spacing: 16) {
                        PadiLine(width: 760)
                        tableBody
                    }
                    .padding(.top, 8)
                    .frame(width: 760)

                    censusText
                        .padding(.top, 48).padding(.horizontal, 32)
                        .frame(minWidth: 200, maxWidth: .infinity, alignment: .topLeading)
                }
            } else {
                VStack(spacing: 0) {
                    filterBar
                    // §4: below the collapse width the editorial moment survives as the PadiLine.
                    PadiLine(width: 760)
                        .padding(.vertical, 16)
                        .frame(maxWidth: .infinity)
                    tableBody
                        .frame(maxWidth: 760)
                        .frame(maxWidth: .infinity)
                    censusText
                        .frame(maxWidth: 760, alignment: .leading)
                        .frame(maxWidth: .infinity)
                        .padding(.horizontal, 16).padding(.vertical, 8)
                }
            }
        }
    }

    // MARK: browse mode (spec §3.2, §4) — rail · display header · grouped table

    private static let browseBreakpoint: CGFloat = 880

    private var browseLayout: some View {
        GeometryReader { geo in
            if geo.size.width >= Self.browseBreakpoint {
                HStack(spacing: 0) {
                    VStack(alignment: .leading, spacing: 0) {
                        VStack(alignment: .leading, spacing: 24) {
                            facet(isID ? "SEKTOR" : "SECTOR", align: .leading) { sectorPicker }
                            facet("BALI", align: .leading) { baliPicker }
                            facet(isID ? "RISIKO OSS" : "OSS RISK", align: .leading) { riskPicker }
                        }
                        .tint(Theme.accent)
                        Spacer(minLength: 24)
                        PadiLine(width: 200)
                        PadiLine(width: 120).padding(.top, 12).padding(.bottom, 32)
                    }
                    .padding(.horizontal, 24).padding(.top, 24)
                    .frame(width: 248).frame(maxHeight: .infinity)
                    .background(Theme.wash)

                    VStack(alignment: .leading, spacing: 0) {
                        browseHeader.frame(height: 92)
                        browseRule
                        columnHeader
                        tableBody
                    }
                    .padding(.top, 24).padding(.trailing, 32).padding(.leading, 40)
                }
            } else {
                VStack(spacing: 0) {
                    filterBar
                    VStack(alignment: .leading, spacing: 0) {
                        browseHeader.frame(minHeight: 92)
                        browseRule
                        PadiLine(width: 200).padding(.top, 12)
                        PadiLine(width: 120).padding(.top, 12)
                        columnHeader
                        tableBody
                    }
                    .padding(.top, 16).padding(.horizontal, 16)
                }
            }
        }
    }

    private var browseHeader: some View {
        HStack(alignment: .lastTextBaseline) {
            Text(lang.t("nav.section.codes"))
                .font(Theme.display(64)).foregroundStyle(Theme.white)
                .fixedSize()
            Spacer(minLength: 16)
            censusText
                .multilineTextAlignment(.trailing)
                .frame(maxWidth: 360, alignment: .trailing)
        }
    }

    private var browseRule: some View {
        Rectangle().fill(Theme.structure).frame(height: 2)
    }

    /// First row of every two-digit code group (the first row of the table included).
    private var groupStartIDs: Set<String> {
        var out = Set<String>()
        var prev: Substring?
        for k in visibleRows {
            let g = k.kode.prefix(2)
            if g != prev { out.insert(k.id) }
            prev = g
        }
        return out
    }

    private func groupHeader(_ k: KBLI) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(String(k.kode.prefix(2)))
                .font(Theme.scalable(12, weight: .semibold)).foregroundStyle(Theme.muted)
                .padding(.leading, 10)
            Rectangle().fill(Theme.lineStrong).frame(height: 1)
        }
        .padding(.top, 16)
        .accessibilityHidden(true)
    }

    private func facet<P: View>(_ title: String, align: HorizontalAlignment = .trailing,
                                @ViewBuilder _ picker: () -> P) -> some View {
        VStack(alignment: align, spacing: 4) {
            Text(title)
                .font(Theme.scalable(11, weight: .semibold)).tracking(0.9)
                .foregroundStyle(Theme.muted)
                .accessibilityHidden(true)
            picker().frame(width: 200, alignment: align == .leading ? .leading : .trailing)
        }
    }

    private var censusText: some View {
        let census = RegistryCensus.cached(for: state.store)
        return Text(censusLine(total: matchedRows.count, census: census))
            .font(Theme.scalable(12)).foregroundStyle(Theme.muted)
            .fixedSize(horizontal: false, vertical: true)
            .accessibilityElement(children: .combine)
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
            sectorPicker

            Spacer(minLength: 0)

            filterTitle("BALI", active: baliFilter != .all)
            baliPicker

            filterTitle(isID ? "RISIKO OSS" : "OSS RISK", active: riskFilter != .all)
            riskPicker
        }
        .tint(Theme.accent)
        .frame(maxWidth: .infinity)
        .padding(.horizontal, 14).padding(.vertical, 7)
        .background(Theme.ink.opacity(0.9))
        .overlay(alignment: .bottom) { Rectangle().fill(Theme.hairline).frame(height: 1) }
    }

    private var sectorPicker: some View {
        Picker(selection: Binding(get: { state.browsedSector },
                                  set: { state.browsedSector = $0 })) {
            Text(isID ? "Semua sektor" : "All sectors").tag(String?.none)
            ForEach(state.store.sectors) { sec in
                Text("\(sec.letter) — \(isID ? sec.id_ : sec.en) (\(sec.count))").tag(String?.some(sec.letter))
            }
        } label: { EmptyView() }
        .pickerStyle(.menu).controlSize(.small).frame(maxWidth: 260)
        .accessibilityLabel(isID ? "Saring menurut sektor" : "Filter by sector")
    }

    private var baliPicker: some View {
        Picker(selection: $baliFilter) {
            ForEach(BaliFilter.allCases) { f in Text(f.title(isID)).tag(f) }
        } label: { EmptyView() }
        .pickerStyle(.menu).controlSize(.small).frame(maxWidth: 190)
        .accessibilityLabel(isID ? "Saring menurut putusan Bali" : "Filter by Bali verdict")
    }

    private var riskPicker: some View {
        Picker(selection: $riskFilter) {
            ForEach(RiskFilter.allCases) { f in Text(f.title(isID)).tag(f) }
        } label: { EmptyView() }
        .pickerStyle(.menu).controlSize(.small).frame(maxWidth: 190)
        .accessibilityLabel(isID ? "Saring menurut kelas risiko OSS" : "Filter by OSS risk class")
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
        .font(Theme.scalable(11, weight: .semibold)).tracking(0.9)
        .foregroundStyle(Theme.muted)
        .padding(.horizontal, 10).padding(.top, 8).padding(.bottom, 4)
        .accessibilityHidden(true)   // the rows carry their own combined labels
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

// MARK: - one result in query mode (spec §3.1)

/// The first hit is the peak card, every other hit a ruled row. Text wraps (no line limits); the
/// selection / tap handling stays with `SearchListView.tableBody`.
private struct QueryResultRow: View {
    @EnvironmentObject var lang: LanguageManager
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    let kbli: KBLI
    let isFirst: Bool
    let isSelected: Bool
    let isID: Bool
    @State private var hovered = false

    var body: some View {
        let hu = KBLIVerdict.headsUp(record: kbli, isID: isID)
        let title = OverlayStore.shared.primaryTitle(kbli, isID: isID)
        Group {
            if isFirst { peak(hu: hu, title: title) } else { ruled(hu: hu, title: title) }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(isSelected || hovered ? Theme.wash : Color.clear)
        .overlay(alignment: .leading) {
            if isSelected { Rectangle().fill(Theme.accent).frame(width: 3) }
        }
        .onHover { hovered = $0 }
        .animation(Theme.motion(reduceMotion), value: hovered)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(kbli.kode) \(title) \(hu.label)")
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }

    private func statusChip() -> some View {
        Text(kbli.pmaStatus ?? "—")
            .font(Theme.scalable(11, weight: .semibold))
            .foregroundStyle(Theme.chip(Theme.tone(kbli.pmaStatus ?? "")).fg)
            .padding(.vertical, 4).padding(.horizontal, 8)
            .background(Theme.chip(Theme.tone(kbli.pmaStatus ?? "")).bg, in: RoundedRectangle(cornerRadius: 2))
    }

    private func peak(hu: (label: String, sentence: String?, tone: Theme.Tone), title: String) -> some View {
        let c = Theme.chip(hu.tone)
        // The canonical `pma_max_asing`, not `nationalCap`: a closed axis carries no cap, and 55203's
        // frozen cap is "0", which must read 0% — "—" only when the record states no number.
        let cap = kbli.pmaMaxAsing
        let other = OverlayStore.shared.primaryTitle(kbli, isID: !isID)
        return VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .firstTextBaseline, spacing: 16) {
                Text(kbli.kode).font(Theme.title(27)).foregroundStyle(Theme.structure)
                statusChip()
                VStack(alignment: .leading, spacing: 4) {
                    Text(cap.map { "\($0)%" } ?? "—").font(Theme.title(36)).foregroundStyle(Theme.white)
                    Text(lang.t("rich.fact.pma")).font(Theme.scalable(12)).foregroundStyle(Theme.muted)
                }
            }
            VStack(alignment: .leading, spacing: 12) {
                Text(title).font(Theme.title(36)).foregroundStyle(Theme.white)
                    .fixedSize(horizontal: false, vertical: true)
                Text(other).font(Theme.scalable(15)).foregroundStyle(Theme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            HStack(spacing: 0) {
                Rectangle().fill(c.fg).frame(width: 4)
                VStack(alignment: .leading, spacing: 8) {
                    Text(hu.label).font(Theme.scalable(12, weight: .semibold)).foregroundStyle(c.fg)
                    if let sentence = hu.sentence {
                        Text(sentence).font(Theme.serif(20)).foregroundStyle(c.fg)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .padding(16)
                Spacer(minLength: 0)
            }
            .background(c.bg)
        }
        .padding(24)
        .background(Theme.inkLift, in: RoundedRectangle(cornerRadius: 2))
        .overlay(RoundedRectangle(cornerRadius: 2).strokeBorder(Theme.lineSoft, lineWidth: 1))
    }

    private func ruled(hu: (label: String, sentence: String?, tone: Theme.Tone), title: String) -> some View {
        let c = Theme.chip(hu.tone)
        let line: Text = {
            let label = Text(hu.label).font(Theme.scalable(13, weight: .semibold)).foregroundColor(c.fg)
            guard let sentence = hu.sentence else { return label }
            return label + Text("  ") + Text(sentence).font(Theme.scalable(13)).foregroundColor(Theme.muted)
        }()
        return VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline, spacing: 12) {
                Text(kbli.kode).font(Theme.serif(20)).foregroundStyle(Theme.muted)
                Text(title).font(Theme.serif(20)).foregroundStyle(Theme.white)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
                statusChip()
                Text(KBLIVerdict.of(record: kbli).ownershipLine(isID: isID))
                    .font(Theme.scalable(12)).foregroundStyle(Theme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            line.fixedSize(horizontal: false, vertical: true)
        }
        .padding(.top, 16)
        .overlay(alignment: .top) { Rectangle().fill(Theme.lineStrong).frame(height: 1) }
        .padding(.bottom, 8)
    }
}
