import SwiftUI

/// A named element a `png_census.py` C-check measures (PR 3-h-2). A View marks it with `.censusFrame("cap")`, and the
/// band snapshot's `--layout-json` writes every mark's frame in the band's points. Frames only: encensus stays the one
/// text instrument. The mark draws nothing (a clear background), so a render is byte-identical with or without it.
/// It replaces the accessibility walk, which an off-screen `NSHostingView` never builds (1 node, no text, measured
/// 2026-10-11: bare, run loop pumped, in a borderless window, ordered front, after `finishLaunching`).
struct CensusFrame: Equatable {
    static let space = "census-band"
    /// Set by the band snapshot when it writes `--layout-json`; the live app never collects.
    static var collecting = false
    let name: String
    let value: String
    let rect: CGRect
}

struct CensusFramesKey: PreferenceKey {
    static let defaultValue: [CensusFrame] = []
    static func reduce(value: inout [CensusFrame], nextValue: () -> [CensusFrame]) { value += nextValue() }
}

extension View {
    /// `value` is a descriptor, never drawn text (lead ruling 2026-10-11): a step ("0"…"3" in `scaleOrder`), an ordinal,
    /// a fraction ("0.49"), or a chip's tone as the record's own state dispatches it (`Theme.tone(<record field>)`),
    /// never the View's own tone variable. Off unless a band snapshot collects (`--layout-json`).
    func censusFrame(_ name: String, _ value: String = "") -> some View {
        modifier(CensusMark(name: name, value: value))
    }
}

/// The mark itself: a clear background that reports its frame while a band snapshot collects, and nothing otherwise,
/// so render_set's identity run (CENSUS_IDENTITY=1) proves a render byte-identical with and without the collector.
struct CensusMark: ViewModifier {
    let name: String
    let value: String
    func body(content: Content) -> some View {
        if CensusFrame.collecting {
            content.background(GeometryReader { g in
                Color.clear.preference(key: CensusFramesKey.self, value: [
                    CensusFrame(name: name, value: value, rect: g.frame(in: .named(CensusFrame.space)))])
            })
        } else {
            content
        }
    }
}
