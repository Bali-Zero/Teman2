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
    /// `name` is one of png_census's NAMES, and `value` matches that name's pattern (PR 3-h-2b): a step ("0"…"3" in
    /// `scaleOrder`, `ScaleMatrix.step`) for `matrix.head/.chip/.cell`, a tone for `chip.national`, `chip.bali` and
    /// `headsup`, an ordinal for `headsup.label/.sentence`, a fraction ("0.49") for `bar`, nothing for every other name.
    /// Never drawn text. A tone comes from the RECORD, never from the function that paints the element (lead ruling
    /// 2026-10-11): `chip.national` is `Theme.tone(k.pmaStatus ?? "")`, `chip.bali` the tone of
    /// `KBLIVerdict.of(record:).bali`, `headsup` the tone `KBLIVerdict.headsUp(record:)` gives; the band snapshot writes
    /// those beside the frames and png_census FAILs a value that disagrees, so a wrong colour cannot hide behind its own
    /// tone variable.
    ///
    /// Where the mark sits (lead ruling 2026-10-11, #8250 gate binding 5): OUTSIDE any `.offset` or `Beat`, after it in
    /// the chain (`x.offset(…).censusFrame(…)`), so the frame says where the element must LAND and the check verifies
    /// that its ink is there. A mark inside a beat travels with the offset: an element left at a residual offset would
    /// carry its frame along and pass. Where a beat moves a CONTAINER of the marked element, the snapshot that renders
    /// mid-motion (`--at-ms`) collects the frames with the motion at its end, so they still say where it lands. At the
    /// final frame both coincide. A static nudge is layout (`padding`), not `.offset`. Off unless a band snapshot
    /// collects (`--layout-json`).
    func censusFrame(_ name: String, _ value: String = "") -> some View {
        modifier(CensusMark(name: name, value: value))
    }

    /// The same mark on some of a row's views only (the chip row of a matrix, not its term and authority rows).
    func censusFrame(_ name: String, _ value: String = "", when on: Bool) -> some View {
        modifier(CensusMark(name: name, value: value, on: on))
    }
}

/// The tone a mark states, read off the RECORD and not off the colour the painter picked. The band snapshot derives the
/// same three on its own for the JSON's `record`, and png_census FAILs a mark that disagrees with it.
enum CensusTone {
    static func national(_ k: KBLI) -> String { "\(Theme.tone(k.pmaStatus ?? ""))" }
    static func bali(_ k: KBLI) -> String {
        switch KBLIVerdict.of(record: k).bali {
        case .open: return "open"
        case .blocked: return "closed"
        case .undetermined: return "neutral"
        }
    }
}

/// The mark itself: a clear background that reports its frame while a band snapshot collects, and nothing otherwise,
/// so render_set's identity run (CENSUS_IDENTITY=1) proves a render byte-identical with and without the collector.
struct CensusMark: ViewModifier {
    let name: String
    let value: String
    var on = true
    func body(content: Content) -> some View {
        if CensusFrame.collecting && on {
            content.background(GeometryReader { g in
                Color.clear.preference(key: CensusFramesKey.self, value: [
                    CensusFrame(name: name, value: value, rect: g.frame(in: .named(CensusFrame.space)))])
            })
        } else {
            content
        }
    }
}
