import SwiftUI

/// IMM-BRIEF M4 (one to five scopes): risk × scale as a stepped path, Mikro → Kecil → Menengah → Besar. The same strings as the flat
/// compact `ScaleMatrix` (header, tier chip, term, the faint "·" gap, the scope titles) — the header row becomes
/// the path, and the picked scale's column lifts onto the floating plane. Pick by click or arrow keys; VoiceOver
/// reads each node as its LabelBook scale name, the picked one with the selected trait. A scale without a
/// published row is a hollow node on a dashed tread — the honest gap, still reachable. Six or more scopes keep
/// `ScaleMatrix`'s filterable list (the caller decides).
struct ScalePathGrid: View {
    let scales: [PerSkala]
    let isID: Bool
    /// `.ledger` adds the 80 pt label column and the authority line, as `ScaleMatrix(.ledger)` draws them.
    var mode: ScaleMatrix.Mode = .compact
    /// The live panel's shown cell (an index into `scales`): a chip selects it, the path's picked scale follows it.
    var selection: Binding<Int?>? = nil
    /// Draw only this scope's rows (the six-or-more selector's pick); the indices stay those of `scales`.
    var onlyScope: String? = nil
    @EnvironmentObject var lang: LanguageManager
    @Environment(\.accessibilityReduceMotion) private var systemReduce
    @State private var picked: String?
    @FocusState private var pathFocused: Bool

    private var order: [String] { ScaleMatrix.order }
    private var ncols: Int { order.count + (mode == .ledger ? 1 : 0) }

    private func published(_ scale: String, _ scs: [ScaleMatrix.Scope]) -> Bool {
        scs.contains { !ScaleMatrix.entries($0, scale).isEmpty }
    }

    /// A PT PMA is Besar by law: focus starts there when Besar has a row, else the last scale that does.
    private func initial(_ scs: [ScaleMatrix.Scope]) -> String {
        if let s = ScalePath.snapshotFocus, order.contains(s) { return s }
        return order.reversed().first { published($0, scs) } ?? order[0]
    }

    var body: some View {
        let scs = ScaleMatrix.scopes(scales).filter { onlyScope == nil || $0.id == onlyScope }
        let shownScale = selection?.wrappedValue.flatMap { i in
            scales.indices.contains(i) ? order.reversed().first { scales[i].skalaUsaha.contains($0) && published($0, scs) } : nil
        }
        let snapScale = ScalePath.snapshotFocus.flatMap { order.contains($0) ? $0 : nil }
        let sel = picked ?? snapScale ?? shownScale ?? initial(scs)
        let selIdx = order.firstIndex(of: sel) ?? 0
        VStack(alignment: .leading, spacing: 8) {
            if mode == .compact {
                Text("\(lang.t("detail.risk")) · \(lang.t("detail.term"))")
                    .font(Theme.scalable(11)).foregroundStyle(Theme.muted)
            }
            Grid(alignment: .top, horizontalSpacing: 8, verticalSpacing: 0) {
                GridRow {
                    if mode == .ledger { Color.clear.frame(width: 80, height: 1) }
                    ForEach(Array(order.enumerated()), id: \.element) { i, s in
                        node(s, index: i, selected: i == selIdx, reached: i <= selIdx, hasRow: published(s, scs), pick: { pick(s, scs) })
                            .anchorPreference(key: PathEdges.self, value: .bounds) { [$0] }
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
                    line(lang.t("detail.risk"), sc, top: 12, bottom: 0, selIdx: selIdx) { chip($0) }
                    line(lang.t("detail.term"), sc, top: 4, bottom: mode == .compact ? 12 : 0, selIdx: selIdx) { e in
                        Text(ScaleMatrix.term(e.row, isID: isID) ?? Theme.absent)
                            .font(Theme.scalable(13)).monospacedDigit().foregroundStyle(Theme.white)
                            .multilineTextAlignment(.center).fixedSize(horizontal: false, vertical: true)
                    }
                    if mode == .ledger {
                        line(lang.t("detail.authority"), sc, top: 4, bottom: 12, selIdx: selIdx) { e in
                            // Two authorities are two entries: a short rule between them, each text as written.
                            VStack(spacing: 6) {
                                ForEach(Array(ScaleMatrix.authorities(e.row, isID: isID).enumerated()), id: \.offset) { i, a in
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
            .backgroundPreferenceValue(PathEdges.self) { edges in
                GeometryReader { g in
                    let r = edges.map { g[$0] }
                    ZStack(alignment: .topLeading) {
                        if r.indices.contains(selIdx) {
                            let c = r[selIdx]
                            Color.clear
                                .frame(width: c.width + 8, height: max(0, g.size.height - c.minY + 6))
                                .plane(.floating)
                                .offset(x: c.minX - 4, y: c.minY - 6)
                        }
                        Path { p in
                            for i in r.indices.dropFirst() where i != selIdx && i - 1 != selIdx {
                                let x = ((r[i - 1].maxX + r[i].minX) / 2).rounded() + 0.5
                                p.move(to: CGPoint(x: x, y: (r.first?.maxY ?? 0) + 10))
                                p.addLine(to: CGPoint(x: x, y: g.size.height))
                            }
                        }
                        .stroke(Theme.lineSoft, lineWidth: 1)
                    }
                }
            }
            .focusable()
            .focused($pathFocused)
            .onKeyPress(.leftArrow) { move(-1, from: selIdx, scs); return .handled }
            .onKeyPress(.rightArrow) { move(1, from: selIdx, scs); return .handled }
            if selection != nil, Set(scs.flatMap { $0.rows.map(\.idx) }).count > 1 {
                Text(LabelBook.cellHint(isID: isID)).font(Theme.scalable(10)).foregroundStyle(Theme.faint)
            }
        }
    }

    private func move(_ d: Int, from i: Int, _ scs: [ScaleMatrix.Scope]) {
        pick(order[min(order.count - 1, max(0, i + d))], scs)
    }

    /// Light a scale. With a shown cell, the cell moves to that scale in the same scope (else the first scope that has one);
    /// a scale with no published row is only focused, the honest gap.
    private func pick(_ scale: String, _ scs: [ScaleMatrix.Scope]) {
        withAnimation(Theme.motion(systemReduce || Motion.forceReduce)) {
            guard let selection else { picked = scale; return }
            let all = scs.flatMap { ScaleMatrix.entries($0, scale) }
            guard let first = all.first else { picked = scale; return }
            let here = selection.wrappedValue.flatMap { i in scs.first { $0.rows.contains { $0.idx == i } } }
            selection.wrappedValue = here.flatMap { ScaleMatrix.entries($0, scale).first }?.idx ?? first.idx
            picked = nil
        }
    }

    /// One stair: the tread (lit up to the picked scale), the node, the scale name under it.
    private func node(_ scale: String, index i: Int, selected: Bool, reached: Bool, hasRow: Bool, pick: @escaping () -> Void) -> some View {
        Button(action: pick) {
            VStack(spacing: 6) {
                Canvas { ctx, size in
                    let y = 22 - 5 * CGFloat(i)
                    let lit = reached && hasRow ? Theme.structure : Theme.lineStrong
                    let dash: [CGFloat] = hasRow ? [] : [3, 3]
                    var tread = Path()
                    tread.move(to: CGPoint(x: 0, y: y)); tread.addLine(to: CGPoint(x: size.width, y: y))
                    ctx.stroke(tread, with: .color(reached ? Theme.structure : Theme.lineStrong),
                               style: StrokeStyle(lineWidth: 2, dash: dash))
                    if i > 0 {
                        var riser = Path()
                        riser.move(to: CGPoint(x: 0, y: y + 5)); riser.addLine(to: CGPoint(x: 0, y: y))
                        ctx.stroke(riser, with: .color(reached ? Theme.structure : Theme.lineStrong), lineWidth: 2)
                    }
                    let c = CGPoint(x: size.width / 2, y: y)
                    let r: CGFloat = selected ? 5.5 : 3.5
                    let dot = Path(ellipseIn: CGRect(x: c.x - r, y: c.y - r, width: 2 * r, height: 2 * r))
                    if hasRow {
                        ctx.fill(dot, with: .color(lit))
                    } else {
                        ctx.fill(dot, with: .color(Theme.inkLift))
                        ctx.stroke(dot, with: .color(Theme.faint), style: StrokeStyle(lineWidth: 1.2, dash: [2, 2]))
                    }
                    if selected {
                        let ring = Path(ellipseIn: CGRect(x: c.x - 9, y: c.y - 9, width: 18, height: 18))
                        ctx.stroke(ring, with: .color(Theme.accent), lineWidth: 1.5)
                    }
                }
                .frame(height: 30)
                Text(LabelBook.scale(scale, isID: isID))
                    .font(Theme.scalable(11, weight: .semibold)).tracking(0.88)
                    .foregroundStyle(selected ? Theme.white : Theme.muted)
            }
            .frame(minWidth: 80, maxWidth: .infinity)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(LabelBook.scale(scale, isID: isID))
        .accessibilityAddTraits(selected ? [.isSelected, .isButton] : .isButton)
    }

    private func line<C: View>(_ label: String, _ sc: ScaleMatrix.Scope, top: CGFloat, bottom: CGFloat, selIdx: Int,
                               @ViewBuilder _ cell: @escaping ((idx: Int, row: PerSkala)) -> C) -> some View {
        GridRow(alignment: .firstTextBaseline) {
            if mode == .ledger {
                Text(label).font(Theme.scalable(11, weight: .semibold)).foregroundStyle(Theme.muted)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(width: 80, alignment: .leading)
                    .padding(.top, top).padding(.bottom, bottom)
            }
            ForEach(Array(order.enumerated()), id: \.element) { i, scale in
                let es = ScaleMatrix.entries(sc, scale)
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
                Button { selection.wrappedValue = selected ? nil : e.idx; picked = nil } label: { face }.buttonStyle(.plain)
                    .accessibilityAddTraits(selected ? .isSelected : [])
            } else { face }
        }
    }

    private func isOriginal(_ sc: ScaleMatrix.Scope) -> Bool {
        let u = sc.uraian ?? ""
        return !u.isEmpty && LabelBook.isOriginal(u, drawn: LabelBook.data(u, isID: isID), isID: isID)
    }
}

private struct PathEdges: PreferenceKey {
    static var defaultValue: [Anchor<CGRect>] = []
    static func reduce(value: inout [Anchor<CGRect>], nextValue: () -> [Anchor<CGRect>]) { value += nextValue() }
}


/// IMM-BRIEF M4: the scale path. One to five scopes draw the path directly; six or more first ask for the scope
/// (the filterable list of `ScaleMatrix`, as a selector), then draw THAT scope's four scales as the path. Same strings
/// as the flat matrix and its expanded row — the selector rows are the flat list's rows, the path the expanded entry.
struct ScalePath: View {
    let scales: [PerSkala]
    let isID: Bool
    var mode: ScaleMatrix.Mode = .compact
    var selection: Binding<Int?>? = nil
    /// Snapshot hooks: the focused scale, the picked scope (index into the scopes), the selector list drawn unbounded
    /// (a ScrollView's content is not drawn by the PDF read-back that proves the text).
    static var snapshotFocus: String?
    static var snapshotScope: Int?
    static var snapshotUnbounded = false

    var body: some View {
        if ScaleMatrix.scopes(scales).count >= ScaleMatrix.listFrom {
            ScopedScalePath(scales: scales, isID: isID, mode: mode, selection: selection)
        } else {
            ScalePathGrid(scales: scales, isID: isID, mode: mode, selection: selection)
        }
    }
}

struct ScopedScalePath: View {
    let scales: [PerSkala]
    let isID: Bool
    let mode: ScaleMatrix.Mode
    var selection: Binding<Int?>? = nil

    @EnvironmentObject var lang: LanguageManager
    @Environment(\.accessibilityReduceMotion) private var systemReduce
    @State private var query = ""
    @State private var chosen: String?
    private let col: CGFloat = 56

    var body: some View {
        let scs = ScaleMatrix.scopes(scales)
        let q = query.lowercased()
        let shown = q.isEmpty ? scs : scs.filter {
            LabelBook.data($0.uraian ?? "", isID: isID).lowercased().contains(q) || ($0.uraian ?? "").lowercased().contains(q)
        }
        let current = shown.first { $0.id == chosen }
            ?? ScalePath.snapshotScope.flatMap { shown.indices.contains($0) ? shown[$0] : nil }
            ?? shown.first
        VStack(alignment: .leading, spacing: 12) {
            Text(isID ? "\(scs.count) RUANG LINGKUP" : "\(scs.count) ACTIVITY SCOPES")
                .font(Theme.scalable(11, weight: .semibold)).tracking(0.88).foregroundStyle(Theme.muted)
            HStack(spacing: 8) {
                ForEach(["Rendah", "Menengah Rendah", "Menengah Tinggi", "Tinggi"], id: \.self) { t in
                    abbr(t)
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
            selector(shown, current: current)
            if let current {
                ScalePathGrid(scales: scales, isID: isID, mode: mode, selection: selection, onlyScope: current.id).id(current.id)
            } else {
                Text(isID ? "Tidak ada lingkup cocok." : "No matching scope.")
                    .font(Theme.scalable(13)).foregroundStyle(Theme.muted).padding(.top, 4)
            }
        }
        // The shown cell follows the picked scope: its Large row, else the last scale that has one.
        .onChange(of: current?.id) { _, _ in
            guard let selection, let current else { return }
            let cell = ScaleMatrix.order.reversed().lazy.compactMap { ScaleMatrix.entries(current, $0).first }.first
            if let cell { selection.wrappedValue = cell.idx }
        }
    }

    /// The flat list's rows (wrapped title + the four tier abbreviations), each a button that picks the scope.
    private func selector(_ shown: [ScaleMatrix.Scope], current: ScaleMatrix.Scope?) -> some View {
        let rows = VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 8) {
                Spacer(minLength: 0)
                ForEach(ScaleMatrix.order, id: \.self) { s in
                    Text(LabelBook.scale(s, isID: isID)).font(Theme.scalable(11, weight: .semibold))
                        .tracking(0.88).foregroundStyle(Theme.muted).fixedSize().frame(width: col)
                }
            }
            .padding(.top, 8).padding(.bottom, 8)
            Rectangle().fill(Theme.structure).frame(height: 2)
            ForEach(shown) { sc in row(sc, picked: sc.id == current?.id) }
        }
        return Group {
            if ScalePath.snapshotUnbounded {
                rows
            } else if Motion.frozenMs != nil {
                // A snapshot cannot draw a nested ScrollView's content: show the viewport at its top instead.
                rows.frame(height: 232, alignment: .top).clipped()
            } else {
                ScrollView { rows }.scrollIndicators(.automatic).frame(maxHeight: 232)
            }
        }
        .focusable()
        .onKeyPress(.upArrow) { step(-1, shown, current); return .handled }
        .onKeyPress(.downArrow) { step(1, shown, current); return .handled }
    }

    private func step(_ d: Int, _ shown: [ScaleMatrix.Scope], _ current: ScaleMatrix.Scope?) {
        guard let i = shown.firstIndex(where: { $0.id == current?.id }) else { return }
        let n = min(shown.count - 1, max(0, i + d))
        withAnimation(Theme.motion(systemReduce || Motion.forceReduce)) { chosen = shown[n].id }
    }

    private func row(_ sc: ScaleMatrix.Scope, picked: Bool) -> some View {
        Button {
            withAnimation(Theme.motion(systemReduce || Motion.forceReduce)) { chosen = sc.id }
        } label: {
            VStack(alignment: .leading, spacing: 4) {
                if isOriginal(sc) { OriginalLabel() }
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(LabelBook.data(sc.uraian ?? "", isID: isID))
                        .font(Theme.scalable(13, weight: picked ? .semibold : .regular)).foregroundStyle(Theme.white)
                        .multilineTextAlignment(.leading).fixedSize(horizontal: false, vertical: true)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    ForEach(ScaleMatrix.order, id: \.self) { scale in
                        VStack(spacing: 4) {
                            let es = ScaleMatrix.entries(sc, scale)
                            if es.isEmpty { Text("·").font(Theme.scalable(13)).foregroundStyle(Theme.faint) }
                            else { ForEach(es, id: \.idx) { abbr($0.row.kategoriRisiko) } }
                        }
                        .frame(width: col)
                    }
                }
            }
            .padding(.vertical, 10).padding(.horizontal, 8)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(picked ? Theme.inkLift : .clear)
            .overlay(alignment: .leading) { if picked { Rectangle().fill(Theme.structure).frame(width: 3) } }
            .overlay(alignment: .bottom) { Rectangle().fill(Theme.lineSoft).frame(height: 1) }
            .shadow(color: .black.opacity(picked ? Elevation.raised.alpha : 0), radius: 6, y: 2)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(picked ? [.isSelected, .isButton] : .isButton)
    }

    private func abbr(_ raw: String?) -> some View {
        let c = Theme.riskChip(raw)
        return Text(LabelBook.riskAbbr(raw, isID: isID))
            .font(Theme.scalable(11, weight: .semibold)).foregroundStyle(c.fg)
            .padding(.vertical, 2).padding(.horizontal, 6)
            .background(c.bg, in: RoundedRectangle(cornerRadius: 2))
            .overlay(RoundedRectangle(cornerRadius: 2).strokeBorder(c.border ?? .clear, lineWidth: 1))
    }

    private func isOriginal(_ sc: ScaleMatrix.Scope) -> Bool {
        let u = sc.uraian ?? ""
        return !u.isEmpty && LabelBook.isOriginal(u, drawn: LabelBook.data(u, isID: isID), isID: isID)
    }
}
