import SwiftUI

/// IMM-BRIEF M4: risk × scale as a stepped path, Mikro → Kecil → Menengah → Besar. The same strings as the flat
/// compact `ScaleMatrix` (header, tier chip, term, the faint "·" gap, the scope titles) — the header row becomes
/// the path, and the picked scale's column lifts onto the floating plane. Pick by click or arrow keys; VoiceOver
/// reads each node as its LabelBook scale name, the picked one with the selected trait. A scale without a
/// published row is a hollow node on a dashed tread — the honest gap, still reachable. Six or more scopes keep
/// `ScaleMatrix`'s filterable list (the caller decides).
struct ScalePath: View {
    let scales: [PerSkala]
    let isID: Bool
    /// `.ledger` adds the 80 pt label column and the authority line, as `ScaleMatrix(.ledger)` draws them.
    var mode: ScaleMatrix.Mode = .compact
    /// Snapshot hook: the scale shown focused in a render (nil = the default below).
    static var snapshotFocus: String?

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
        if let s = Self.snapshotFocus, order.contains(s) { return s }
        return order.reversed().first { published($0, scs) } ?? order[0]
    }

    var body: some View {
        let scs = ScaleMatrix.scopes(scales)
        let sel = picked ?? initial(scs)
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
                        node(s, index: i, selected: i == selIdx, reached: i <= selIdx, hasRow: published(s, scs))
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
            .onKeyPress(.leftArrow) { move(-1, from: selIdx); return .handled }
            .onKeyPress(.rightArrow) { move(1, from: selIdx); return .handled }
        }
    }

    private func move(_ d: Int, from i: Int) {
        let n = min(order.count - 1, max(0, i + d))
        withAnimation(Theme.motion(systemReduce || Motion.forceReduce)) { picked = order[n] }
    }

    /// One stair: the tread (lit up to the picked scale), the node, the scale name under it.
    private func node(_ scale: String, index i: Int, selected: Bool, reached: Bool, hasRow: Bool) -> some View {
        Button {
            withAnimation(Theme.motion(systemReduce || Motion.forceReduce)) { picked = scale }
        } label: {
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
                VStack(spacing: 4) {
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
        return (e.row.kategoriRisiko.map { Text(LabelBook.risk($0, isID: isID)) } ?? Text(Theme.absent))
            .font(Theme.scalable(11, weight: .semibold)).foregroundStyle(c.fg)
            .multilineTextAlignment(.center).fixedSize(horizontal: false, vertical: true)
            .padding(.vertical, 4).padding(.horizontal, 8)
            .background(c.bg, in: RoundedRectangle(cornerRadius: 2))
            .overlay(RoundedRectangle(cornerRadius: 2).strokeBorder(c.border ?? .clear, lineWidth: 1))
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
