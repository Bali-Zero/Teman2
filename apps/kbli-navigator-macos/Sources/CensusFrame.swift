import SwiftUI

/// A named element a `png_census.py` C-check measures (PR 3-h-2). A View marks it with `.censusFrame("cap")`, and the
/// band snapshot's `--layout-json` writes every mark's frame in the band's points. Frames only: encensus stays the one
/// text instrument. The mark draws nothing (a clear background), so a render is byte-identical with or without it.
/// It replaces the accessibility walk, which an off-screen `NSHostingView` never builds (1 node, no text, measured
/// 2026-10-11: bare, run loop pumped, in a borderless window, ordered front, after `finishLaunching`).
struct CensusFrame: Equatable {
    static let space = "census-band"
    let name: String
    let value: String
    let rect: CGRect
}

struct CensusFramesKey: PreferenceKey {
    static let defaultValue: [CensusFrame] = []
    static func reduce(value: inout [CensusFrame], nextValue: () -> [CensusFrame]) { value += nextValue() }
}

extension View {
    /// `value` is what the check compares against: a scale key, a code, a cap figure, or a chip's tone as the
    /// record's own state dispatches it (`Theme.tone(<record field>)`), never the View's own tone variable.
    func censusFrame(_ name: String, _ value: String = "") -> some View {
        background(GeometryReader { g in
            Color.clear.preference(key: CensusFramesKey.self, value: [
                CensusFrame(name: name, value: value, rect: g.frame(in: .named(CensusFrame.space)))])
        })
    }
}
