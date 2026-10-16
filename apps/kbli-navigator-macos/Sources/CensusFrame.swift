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
    /// Where the mark sits (lead ruling 2026-10-12, #8297 gate finding 4; it replaces 2026-10-11's wording): a census
    /// frame reports the element's LAYOUT frame, where it is MEANT to land, and the check verifies that its ink is there.
    /// So the mark goes AFTER any animation modifier (`Beat`, a transition): the frame keeps the layout position, and a
    /// beat that leaves the element out of place FAILs on ink against frame. A mark placed before the move travels with
    /// it and can never disagree with the ink. A deliberate static nudge on a marked element is layout (`padding`,
    /// alignment), never `.offset`, so frame and ink agree. `mark_order_check.py` (content_check step 7) is a first-pass lint for both,
    /// not a guarantee: it does not read the shapes L1-L9 that its docstring and docs/specs/2026-10-12-kbli-nav-census-mark-order.md
    /// name (a trailing or labelled closure on the next line, a postfix `#if`, a mark inside a closure whose enclosing chain moves,
    /// a marked view moved by name, a MOVE helper such as `HoverLift`, an Animatable conformance in an extension, a ViewModifier that
    /// applies Beat, the built-in render effects). None is live today.
    /// Where a beat moves a CONTAINER of the marked element, the snapshot that renders mid-motion (`--at-ms`) collects
    /// the frames with the motion at its end; at the final frame both coincide. Off unless a band snapshot collects
    /// (`--layout-json`).
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
    /// The national plate's tone: the verdict's own (the sheet draws no raw `pma_status` chip).
    static func national(verdict v: KBLIVerdict) -> String {
        switch v.national {
        case .open: return "open"
        case .restricted: return "restricted"
        case .closed: return "closed"
        case .undetermined: return "neutral"
        }
    }
    static func bali(_ k: KBLI) -> String {
        switch KBLIVerdict.of(record: k).bali {
        case .open: return "open"
        case .blocked: return "closed"
        case .undetermined: return "neutral"
        }
    }
}

/// A scroll view reaches an unbuilt row of a lazy stack only inside a window (measured 2026-10-15 with a bare ScrollViewReader over a
/// LazyVStack: `scrollTo` left an off-screen NSHostingView at its top in every variant, ticks and a second pass included, and centred the
/// row to the point once the same view sat in a borderless window ordered front). The bands that mount the real list live in one, far off
/// every screen, as the app does.
enum CensusWindow {
    @MainActor private static var kept: [NSWindow] = []

    /// `KBLI_CENSUS_NOWINDOW=1` is the control: the same band in a bare hosting view, as the harness drew it before (its `scrollTo` does not
    /// reach an unbuilt row, and its text metrics are not the window's: id 56102 wraps one line less).
    @MainActor static func attach(_ view: NSView, size: CGSize) {
        if ProcessInfo.processInfo.environment["KBLI_CENSUS_NOWINDOW"] != nil { return }
        let win = NSWindow(contentRect: NSRect(x: -20000, y: -20000, width: size.width, height: size.height),
                           styleMask: [.borderless], backing: .buffered, defer: false)
        win.contentView = view
        win.orderFrontRegardless()
        NSApp.activate(ignoringOtherApps: true)
        win.makeKey()
        kept.append(win)
    }

    /// Takes the windows down (the fold census mounts one per language and size).
    @MainActor static func closeAll() {
        for w in kept { w.contentView = nil; w.orderOut(nil) }
        kept.removeAll()
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
