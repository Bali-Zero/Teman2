import SwiftUI

/// The search field bar pinned above the results (extracted verbatim from `RootView.searchHeader`,
/// restyled for the spec §3.1 search-results view): a 52 pt elevated field in a column of at most
/// 760 pt, so it lines up with the results spine below. Same field, focus wiring, hand-off, clear
/// button and row-density button as before.
struct SearchFieldBar: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    @AppStorage("rowDensity") private var rowDensity: RowDensity = .comfortable
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    var focusedField: FocusState<RootFocus?>.Binding
    /// Return / Down-arrow in the field: move keyboard focus into the list.
    var onHandOff: () -> Void

    var body: some View {
        // Equal flexible sides keep the field exactly on the 760 pt results spine; the density
        // button sits just outside it, in the right-hand side.
        HStack(spacing: 0) {
            Spacer(minLength: 0).frame(maxWidth: .infinity)
            HStack(spacing: 7) {
                Image(systemName: "magnifyingglass").font(Theme.scalable(16)).foregroundStyle(Theme.faint)
                TextField(lang.t("search.placeholder"), text: $state.query)
                    .textFieldStyle(.plain).font(Theme.scalable(20)).foregroundStyle(Theme.white)
                    .focused(focusedField, equals: .search)
                    .onSubmit { onHandOff() }
                    .onKeyPress(.downArrow) { onHandOff(); return .handled }
                if !state.query.isEmpty {
                    Button { state.query = "" } label: {
                        Image(systemName: "xmark.circle.fill").font(Theme.scalable(14)).foregroundStyle(Theme.faint)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 12)
            .frame(height: 52)
            .background(Theme.inkLift, in: RoundedRectangle(cornerRadius: 2))
            .overlay(RoundedRectangle(cornerRadius: 2).strokeBorder(Theme.lineStrong, lineWidth: 1))
            .frame(maxWidth: 760)
            .layoutPriority(1)   // the field takes its 760 first; the two sides share the rest

            HStack(spacing: 0) {
            // Small toolbar icon twin of ⌘⇧D, right next to the field it applies to.
            Button {
                withAnimation(Theme.motion(reduceMotion)) { rowDensity.toggle() }
            } label: {
                Image(systemName: rowDensity == .compact ? "rectangle.expand.vertical" : "rectangle.compress.vertical")
                    .font(Theme.scalable(12))
            }
            .buttonStyle(.plain)
            .help(rowDensity == .compact ? "Comfortable density" : "Compact density")
            .padding(.leading, 12)
            Spacer(minLength: 0)
            }
            .frame(maxWidth: .infinity)
        }
        .padding(.horizontal, 12).padding(.top, 10).padding(.bottom, 8)
        .background(Theme.antracite)
    }
}
