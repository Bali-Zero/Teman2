import SwiftUI

/// SPEC-detail-polish D1: risk × scale is a matrix, everywhere. Four columns in the canonical order
/// (Mikro · Kecil · Menengah · Besar), the scale header said once over a 2 pt structure rule, what the
/// cell lines are said once too — `.ledger`: an 80 pt label column (`detail.risk` / `detail.term` /
/// `detail.authority`); `.compact` (detail card, dossier): an 11-muted caption "Risk · Term". A cell
/// is centred: `riskChip` with the full tier word, the term at 13 tabular, and on the ledger the
/// §3.5 authority stack (every `kewenanganLevels` element in array order, exact repeats once).
/// More than one scope: a wrapped title row per scope. Six or more: the filter field, the scale header
/// pinned under it, one collapsible row per scope (wrapped title + the four tier abbreviations, the
/// legend kept). An absent scale is the faint "·"; a scope that lists a scale twice stacks both
/// entries in that cell. No row merged or dropped; text wraps, never clamps.
extension View {
    /// The shown risk cell's selection mark (flat matrix and scale path alike): a 2 pt accent ring outside the chip with a
    /// 1.5 pt gap, so the ring touches only the surface, never the chip's fill (accent on the surface is >= 3:1 day and night).
    func selectionRing(_ on: Bool) -> some View {
        overlay { if on { RoundedRectangle(cornerRadius: 4).strokeBorder(Theme.accent, lineWidth: 2).padding(-3.5) } }
    }
}

struct ScaleMatrix: View {
    enum Mode { case ledger, compact }

    let scales: [PerSkala]
    let isID: Bool
    var mode: Mode = .compact
    /// When set, a chip is a button selecting its `scales` index (the PP28 block's cell detail).
    var selection: Binding<Int?>? = nil
    /// What an expanded row of the six-or-more list shows for each of its entries.
    var expanded: ((PerSkala) -> AnyView)? = nil

    @EnvironmentObject var lang: LanguageManager
    @State private var query = ""
    @State private var open: Set<String> = []

    static let order = PP28ScalePanel.scaleOrder
    /// Between stacked cells of one scale: the shown cell's ring (1.5 pt gap + 2 pt line, outside its chip) must clear the chip beside it by >= 1.5 pt.
    static let cellGap: CGFloat = 8
    static let listFrom = PP28ScalePanel.matrixMaxScopes + 1
    /// Snapshot hook (the content proof of the immersive scope selector): draw this scope's row of the list expanded.
    static var snapshotOpenScope: Int?

    struct Scope: Identifiable { let id: String; let uraian: String?; let rows: [(idx: Int, row: PerSkala)] }

    /// Scopes in record order, keyed as PP28ScalePanel always has: the description (case-folded), else the index.
    static func scopes(_ scales: [PerSkala]) -> [Scope] {
        var order: [String] = [], rows: [String: [(Int, PerSkala)]] = [:]
        for (i, s) in scales.enumerated() {
            let u = (s.scopeUraian ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            let key = u.isEmpty ? "idx:\(s.scopeIndex ?? 0)" : "u:" + u.lowercased()   // an identity, never drawn
            if rows[key] == nil { order.append(key) }
            rows[key, default: []].append((i, s))
        }
        return order.map { k in
            Scope(id: k, uraian: rows[k]?.first?.1.scopeUraian, rows: (rows[k] ?? []).map { (idx: $0.0, row: $0.1) })
        }
    }

    static func entries(_ sc: Scope, _ scale: String) -> [(idx: Int, row: PerSkala)] {
        sc.rows.filter { $0.row.skalaUsaha.contains(scale) }
    }

    /// §3.5: the authority stack — verbatim in Indonesian, the LabelBook word in English.
    static func authorities(_ s: PerSkala, isID: Bool) -> [String] {
        var seen = Set<String>()
        return s.kewenanganLevels.filter { seen.insert($0).inserted }.map { isID ? $0 : LabelBook.authority($0, isID: false) }
    }

    static func term(_ s: PerSkala, isID: Bool) -> String? {
        guard let j = s.jangkaWaktu, !j.isEmpty else { return nil }
        return LabelBook.term(j, isID: isID)
    }

    /// Every string a cell draws, one entry per (scope, scale, row) — the function `contenttest` prints.
    static func cells(for scales: [PerSkala], isID: Bool, ledger: Bool) -> [[String: String]] {
        scopes(scales).flatMap { sc in order.flatMap { scale in entries(sc, scale).map { e -> [String: String] in
            var c = ["scope": sc.uraian ?? "", "scale": scale,
                     "risk": e.row.kategoriRisiko.map { LabelBook.risk($0, isID: isID) } ?? Theme.absent,
                     "term": term(e.row, isID: isID) ?? ""]
            if ledger { c["authority"] = authorities(e.row, isID: isID).joined(separator: "\n") }
            return c
        } } }
    }

    var body: some View {
        let scs = Self.scopes(scales)
        if scs.count >= Self.listFrom { list(scs) } else { matrix(scs) }
    }

    // MARK: one to five scopes — the matrix

    private var ncols: Int { Self.order.count + (mode == .ledger ? 1 : 0) }

    private func matrix(_ scs: [Scope]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            if mode == .compact {
                Text("\(lang.t("detail.risk")) · \(lang.t("detail.term"))")
                    .font(Theme.scalable(11)).foregroundStyle(Theme.muted)
            }
            Grid(alignment: .top, horizontalSpacing: 8, verticalSpacing: 0) {
                GridRow {
                    if mode == .ledger { Color.clear.frame(width: 80, height: 1) }
                    ForEach(Self.order, id: \.self) { s in
                        header(s).anchorPreference(key: ColumnEdges.self, value: .bounds) { [$0] }
                    }
                }
                GridRow {
                    Rectangle().fill(Theme.structure).frame(height: 2).padding(.top, 8).gridCellColumns(ncols)
                }
                ForEach(scs) { sc in
                    if scs.count > 1 {
                        GridRow {
                            VStack(alignment: .leading, spacing: 2) {
                                if isOriginal(sc) { OriginalLabel() }
                                Text(LabelBook.data(sc.uraian ?? "", isID: isID))
                                    .font(Theme.scalable(13, weight: .semibold)).foregroundStyle(Theme.white)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.top, 16).padding(.bottom, 8)
                            .gridCellColumns(ncols)
                        }
                    }
                    line(lang.t("detail.risk"), sc, top: 12) { chip($0) }
                    line(lang.t("detail.term"), sc, top: 4, bottom: mode == .compact ? 12 : 0) { e in
                        Text(Self.term(e.row, isID: isID) ?? Theme.absent)
                            .font(Theme.scalable(13)).monospacedDigit().foregroundStyle(Theme.white)
                            .multilineTextAlignment(.center).fixedSize(horizontal: false, vertical: true)
                    }
                    if mode == .ledger {
                        line(lang.t("detail.authority"), sc, top: 4, bottom: 12) { e in
                            // Two authorities are two entries: a short rule between them, each text as written.
                            VStack(spacing: 6) {
                                ForEach(Array(Self.authorities(e.row, isID: isID).enumerated()), id: \.offset) { i, a in
                                    if i > 0 { Rectangle().fill(Theme.lineStrong).frame(width: 24, height: 1) }
                                    Text(a).font(Theme.scalable(13)).foregroundStyle(Theme.muted)
                                        .multilineTextAlignment(.center).fixedSize(horizontal: false, vertical: true)
                                }
                            }
                        }
                    }
                    GridRow { Rectangle().fill(Theme.lineSoft).frame(height: 1).gridCellColumns(ncols) }
                }
            }
            .backgroundPreferenceValue(ColumnEdges.self) { edges in
                GeometryReader { g in
                    let r = edges.map { g[$0] }
                    Path { p in
                        for i in r.indices.dropFirst() {
                            let x = ((r[i - 1].maxX + r[i].minX) / 2).rounded() + 0.5
                            p.move(to: CGPoint(x: x, y: (r.first?.maxY ?? 0) + 10))
                            p.addLine(to: CGPoint(x: x, y: g.size.height))
                        }
                    }
                    .stroke(Theme.lineSoft, lineWidth: 1)
                }
            }
            if selection != nil, Set(scs.flatMap { $0.rows.map(\.idx) }).count > 1 {
                Text(LabelBook.cellHint(isID: isID)).font(Theme.scalable(10)).foregroundStyle(Theme.faint)
            }
        }
    }

    private func header(_ scale: String) -> some View {
        Text(LabelBook.scale(scale, isID: isID))
            .font(Theme.scalable(11, weight: .semibold)).tracking(0.88).foregroundStyle(Theme.muted)
            .frame(minWidth: 80, maxWidth: .infinity)
    }

    /// One labelled line of a scope block: the label column (ledger) and the four cells.
    private func line<C: View>(_ label: String, _ sc: Scope, top: CGFloat, bottom: CGFloat = 0,
                               @ViewBuilder _ cell: @escaping ((idx: Int, row: PerSkala)) -> C) -> some View {
        GridRow(alignment: .firstTextBaseline) {
            if mode == .ledger {
                Text(label).font(Theme.scalable(11, weight: .semibold)).foregroundStyle(Theme.muted)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(width: 80, alignment: .leading)
                    .padding(.top, top).padding(.bottom, bottom)
            }
            ForEach(Self.order, id: \.self) { scale in
                let es = Self.entries(sc, scale)
                VStack(spacing: ScaleMatrix.cellGap) {
                    if es.isEmpty {
                        if top == 12 { Text("·").font(Theme.scalable(13)).foregroundStyle(Theme.faint) }
                    } else {
                        ForEach(es, id: \.idx) { cell($0) }
                    }
                }
                .frame(minWidth: 80, maxWidth: .infinity)
                .padding(.top, top).padding(.bottom, bottom)
            }
        }
    }

    private func chip(_ e: (idx: Int, row: PerSkala)) -> some View {
        let c = Theme.riskChip(e.row.kategoriRisiko)
        let selected = selection?.wrappedValue == e.idx
        let face = (e.row.kategoriRisiko.map { Text(LabelBook.risk($0, isID: isID)) } ?? Text(Theme.absent))
            .font(Theme.scalable(11, weight: .semibold)).foregroundStyle(c.fg)
            .multilineTextAlignment(.center).fixedSize(horizontal: false, vertical: true)
            .padding(.vertical, 4).padding(.horizontal, 8)
            .background(c.bg, in: RoundedRectangle(cornerRadius: 2))
            .overlay(RoundedRectangle(cornerRadius: 2).strokeBorder(c.border ?? .clear, lineWidth: 1))
            .selectionRing(selected)
        return Group {
            if let selection {
                Button { selection.wrappedValue = selected ? nil : e.idx } label: { face }.buttonStyle(.plain)
                    .accessibilityAddTraits(selected ? .isSelected : [])
            } else { face }
        }
    }

    /// An English reader meeting a scope title with no English source sees it under its label (Q12 ruling 4).
    private func isOriginal(_ sc: Scope) -> Bool {
        let u = sc.uraian ?? ""
        return !u.isEmpty && LabelBook.isOriginal(u, drawn: LabelBook.data(u, isID: isID), isID: isID)
    }

    // MARK: six or more scopes — the filterable list

    private static let col: CGFloat = 56

    private func list(_ scs: [Scope]) -> some View {
        let q = query.lowercased()
        let shown = q.isEmpty ? scs : scs.filter { LabelBook.data($0.uraian ?? "", isID: isID).lowercased().contains(q) || ($0.uraian ?? "").lowercased().contains(q) }
        return VStack(alignment: .leading, spacing: 8) {
            Text(isID ? "\(scs.count) RUANG LINGKUP" : "\(scs.count) ACTIVITY SCOPES")
                .font(Theme.scalable(11, weight: .semibold)).tracking(0.88).foregroundStyle(Theme.muted)
            HStack(spacing: 8) {
                ForEach(["Rendah", "Menengah Rendah", "Menengah Tinggi", "Tinggi"], id: \.self) { t in
                    abbrChip(t)
                    Text(LabelBook.risk(t, isID: isID)).font(Theme.scalable(11)).foregroundStyle(Theme.muted)
                }
            }
            HStack(spacing: 8) {
                Image(systemName: "magnifyingglass").font(Theme.scalable(11)).foregroundStyle(Theme.muted)
                TextField(isID ? "Cari lingkup…" : "Filter scopes…", text: $query)
                    .textFieldStyle(.plain).font(Theme.scalable(13)).foregroundStyle(Theme.white)
            }
            .padding(.horizontal, 12).padding(.vertical, 8)
            .background(Theme.inkLift, in: RoundedRectangle(cornerRadius: 2))
            .overlay(RoundedRectangle(cornerRadius: 2).strokeBorder(Theme.lineStrong, lineWidth: 1))
            LazyVStack(alignment: .leading, spacing: 0, pinnedViews: [.sectionHeaders]) {
                Section {
                    ForEach(shown) { sc in listRow(sc) }
                    if shown.isEmpty {
                        Text(isID ? "Tidak ada lingkup cocok." : "No matching scope.")
                            .font(Theme.scalable(13)).foregroundStyle(Theme.muted).padding(.top, 12)
                    }
                } header: {
                    VStack(spacing: 8) {
                        HStack(spacing: 8) {
                            Spacer(minLength: 0)
                            ForEach(Self.order, id: \.self) { s in
                                Text(LabelBook.scale(s, isID: isID)).font(Theme.scalable(11, weight: .semibold))
                                    .tracking(0.88).foregroundStyle(Theme.muted)
                                    .fixedSize().frame(width: Self.col)
                            }
                        }
                        Rectangle().fill(Theme.structure).frame(height: 2)
                    }
                    .padding(.top, 8).background(Theme.antracite)
                }
            }
        }
    }

    private func listRow(_ sc: Scope) -> some View {
        let isOpen = open.contains(sc.id) || Self.snapshotOpenScope.map { Self.scopes(scales).indices.contains($0) && Self.scopes(scales)[$0].id == sc.id } == true
        return VStack(alignment: .leading, spacing: 8) {
            if isOriginal(sc) { OriginalLabel().padding(.leading, 20) }
            Button {
                if isOpen { open.remove(sc.id) } else { open.insert(sc.id) }
            } label: {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Image(systemName: isOpen ? "chevron.down" : "chevron.right")
                        .font(Theme.scalable(11, weight: .semibold)).foregroundStyle(Theme.structure)
                    Text(LabelBook.data(sc.uraian ?? "", isID: isID)).font(Theme.scalable(13, weight: .semibold)).foregroundStyle(Theme.white)
                        .multilineTextAlignment(.leading).fixedSize(horizontal: false, vertical: true)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    ForEach(Self.order, id: \.self) { scale in
                        VStack(spacing: 4) {
                            let es = Self.entries(sc, scale)
                            if es.isEmpty {
                                Text("·").font(Theme.scalable(13)).foregroundStyle(Theme.faint)
                            } else {
                                ForEach(es, id: \.idx) { abbrChip($0.row.kategoriRisiko) }
                            }
                        }
                        .frame(width: Self.col)
                    }
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            if isOpen {
                ForEach(sc.rows, id: \.idx) { e in
                    expanded.map { $0(e.row) } ?? AnyView(entryLine(e.row))
                }
                .padding(.leading, 20)
            }
        }
        .padding(.vertical, 12)
        .overlay(alignment: .bottom) { Rectangle().fill(Theme.lineSoft).frame(height: 1) }
    }

    private func abbrChip(_ raw: String?) -> some View {
        let c = Theme.riskChip(raw)
        return Text(LabelBook.riskAbbr(raw, isID: isID))
            .font(Theme.scalable(11, weight: .semibold)).foregroundStyle(c.fg)
            .padding(.vertical, 2).padding(.horizontal, 6)
            .background(c.bg, in: RoundedRectangle(cornerRadius: 2))
            .overlay(RoundedRectangle(cornerRadius: 2).strokeBorder(c.border ?? .clear, lineWidth: 1))
    }

    /// An expanded entry by default: its scales, tier word, term and (ledger) authorities.
    private func entryLine(_ s: PerSkala) -> some View {
        let parts = [LabelBook.scales(s.skalaUsaha, isID: isID), LabelBook.risk(s.kategoriRisiko ?? "", isID: isID),
                     Self.term(s, isID: isID) ?? ""]
            + (mode == .ledger ? Self.authorities(s, isID: isID) : [])
        return Text(parts.filter { !$0.isEmpty }.joined(separator: " · "))
            .font(Theme.scalable(13)).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
    }
}

/// The header cells' frames, so the column verticals sit in the gutters (never over text).
private struct ColumnEdges: PreferenceKey {
    static var defaultValue: [Anchor<CGRect>] = []
    static func reduce(value: inout [Anchor<CGRect>], nextValue: () -> [Anchor<CGRect>]) { value += nextValue() }
}
