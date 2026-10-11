import SwiftUI

/// IMM-BRIEF shared pieces (2026-10-11): elevation tokens (M5), the motion clock and its one Reduce Motion gate (M2),
/// the sticky verdict ribbon (M5) and the hover lift (M7). Presentation only: no string is born here — every word a
/// piece draws comes from the record or the LabelBook, handed in by the caller.

// MARK: - Elevation tokens (M5): three named planes

enum Elevation {
    /// The window's paper. No shadow.
    case ground
    /// A plate laid on the paper: verdict box, Bali map, basis plate.
    case raised
    /// The one thing the reader is operating: the focused scale column.
    case floating

    var radius: CGFloat { switch self { case .ground: return 0; case .raised: return 12; case .floating: return 30 } }
    var dy: CGFloat { switch self { case .ground: return 0; case .raised: return 4; case .floating: return 14 } }
    var alpha: Double {
        let day = Theme.mode == .light
        switch self { case .ground: return 0; case .raised: return day ? 0.13 : 0.48; case .floating: return day ? 0.26 : 0.68 }
    }
}

private struct PlaneModifier: ViewModifier {
    let plane: Elevation
    func body(content: Content) -> some View {
        switch plane {
        case .ground:
            content
        case .raised:
            content.background(Theme.inkLift)
                .overlay(Rectangle().strokeBorder(Theme.lineSoft, lineWidth: 1))
                .shadow(color: .black.opacity(plane.alpha), radius: plane.radius, y: plane.dy)
        case .floating:
            content.background(Theme.inkLift)
                .overlay(Rectangle().strokeBorder(Theme.lineStrong, lineWidth: 1))
                .shadow(color: .black.opacity(plane.alpha), radius: plane.radius, y: plane.dy)
                .shadow(color: .black.opacity(plane.alpha * 0.5), radius: 2, y: 1)
        }
    }
}

extension View {
    /// Paints the view as one of the three elevation planes.
    func plane(_ e: Elevation) -> some View { modifier(PlaneModifier(plane: e)) }
}

// MARK: - Motion clock and the Reduce Motion gate (M2)

enum Motion {
    /// The one choreography per screen, start to final frame.
    static let total: Double = 0.6
    /// Snapshot clock: when set (ms), the card is drawn frozen at that instant instead of animating.
    static var frozenMs: Double?
    /// Snapshot twin of the system Reduce Motion switch (`accessibilityReduceMotion` is read-only).
    static var forceReduce = false

    /// 0…1 progress of one beat inside the choreography, eased out.
    static func phase(_ p: Double, _ from: Double, _ to: Double) -> Double {
        guard to > from else { return p >= to ? 1 : 0 }
        let k = min(1, max(0, (p - from) / (to - from)))
        return 1 - pow(1 - k, 3)
    }
}

private struct ArrivalKey: EnvironmentKey { static let defaultValue: Double = 1 }
extension EnvironmentValues {
    /// Choreography progress 0…1; 1 (the final frame) whenever Reduce Motion is on or no host drives it.
    var arrival: Double {
        get { self[ArrivalKey.self] }
        set { self[ArrivalKey.self] = newValue }
    }
}

/// The single gate: Reduce Motion (system or snapshot flag) returns the final frame, never a shortened animation.
struct ArrivalHost<Content: View>: View {
    @Environment(\.accessibilityReduceMotion) private var systemReduce
    @State private var live: Double = 0
    @ViewBuilder let content: Content

    var body: some View {
        // A snapshot owns its own switch (--reduce-motion); the host's system setting must not leak into a render.
        let reduce = Motion.frozenMs != nil ? Motion.forceReduce : (systemReduce || Motion.forceReduce)
        let p = reduce ? 1 : (Motion.frozenMs.map { min(1, max(0, $0 / (Motion.total * 1000))) } ?? live)
        content
            .environment(\.arrival, p)
            .onAppear {
                guard !reduce, Motion.frozenMs == nil else { return }
                withAnimation(.linear(duration: Motion.total)) { live = 1 }
            }
    }
}

/// One beat of the choreography: fade and rise between `from` and `to` of the shared progress.
struct Beat: ViewModifier, Animatable {
    var p: Double
    var from: Double
    var to: Double
    var dx: CGFloat = 0
    var dy: CGFloat = 0
    var fade = true
    var animatableData: Double { get { p } set { p = newValue } }
    func body(content: Content) -> some View {
        let k = Motion.phase(p, from, to)
        content.opacity(fade ? k : 1).offset(x: dx * (1 - k), y: dy * (1 - k))
    }
}

/// A rule that draws itself left to right.
struct DrawnRule: ViewModifier, Animatable {
    var p: Double
    var from: Double
    var to: Double
    var animatableData: Double { get { p } set { p = newValue } }
    func body(content: Content) -> some View {
        content.scaleEffect(x: max(0.0001, Motion.phase(p, from, to)), y: 1, anchor: .leading)
    }
}

/// The foreign-ownership cap counts up to its value. Final frame text == "\(value)%", the flat card's string.
struct CountUpPercent: View, Animatable {
    var p: Double
    var value: Int
    var animatableData: Double { get { p } set { p = newValue } }
    var body: some View { Text("\(Int((Double(value) * Motion.phase(p, 0.25, 1.0)).rounded()))%") }
}

// MARK: - Related codes (M7, cheap part): a hover lift

struct HoverLift: ViewModifier {
    @State private var over = false
    func body(content: Content) -> some View {
        content
            .shadow(color: .black.opacity(over ? Elevation.floating.alpha * 0.7 : 0), radius: 14, y: 8)
            .offset(y: over ? -3 : 0)
            .animation(.easeOut(duration: 0.14), value: over)
            .onHover { over = $0 }
    }
}

extension Theme {
    /// The semantic hue Bali is lit in: the verdict tone's own palette entry, no new colour.
    static func baliHue(_ tone: Tone) -> Color {
        switch tone {
        case .open: return pmaOpen
        case .restricted: return pmaRestricted
        case .closed: return pmaClosed
        case .neutral: return structure
        }
    }
}


/// The sticky verdict ribbon: pinned once the masthead has scrolled away. Same strings as the masthead and the verdict box.
struct VerdictRibbon: View {
    let kbli: KBLI
    let isID: Bool
    let bali: (word: String, tone: Theme.Tone, voiceOver: String)
    var body: some View {
        let tone = Theme.tone(kbli.pmaStatus ?? "")
        let c = Theme.chip(tone), b = Theme.chip(bali.tone)
        HStack(spacing: 16) {
            Text(kbli.kode).font(Theme.scalable(13, weight: .semibold)).monospacedDigit().foregroundStyle(Theme.muted)
            Text(LabelBook.title(kbli, isID: isID)).font(Theme.serif(20)).foregroundStyle(Theme.structure).lineLimit(1)
            Spacer(minLength: 8)
            Text(LabelBook.pmaStatus(kbli.pmaStatus, isID: isID)).font(Theme.scalable(11, weight: .semibold)).foregroundStyle(c.fg)
                .padding(.vertical, 4).padding(.horizontal, 8).background(c.bg, in: RoundedRectangle(cornerRadius: 2))
            Text(kbli.pmaMaxAsing.map { "\($0)%" } ?? Theme.absent).font(Theme.title(24)).monospacedDigit().foregroundStyle(Theme.structure)
            Text(bali.word).font(Theme.scalable(11, weight: .semibold)).foregroundStyle(b.fg)
                .padding(.vertical, 4).padding(.horizontal, 8).background(b.bg, in: RoundedRectangle(cornerRadius: 2))
        }
        .padding(.horizontal, 48).padding(.vertical, 12)
        .frame(maxWidth: .infinity)
        .plane(.floating)
    }
}

/// Where the masthead's bottom edge sits in the card's scroll space; below 0 the masthead has left the viewport.
struct StageBottomKey: PreferenceKey {
    static var defaultValue: CGFloat = 1
    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) { value = nextValue() }
}

extension Motion {
    /// Snapshot hook: draw the sticky ribbon as if the masthead had scrolled away.
    static var forceRibbon = false
}

extension Motion {
    /// Snapshot hooks, parsed once per render: `--at-ms N` freezes the clock (default: the final frame), `--reduce-motion` is the
    /// Reduce Motion gate, `--ribbon` draws the sticky ribbon, `--scale-focus Mikro|Kecil|Menengah|Besar` picks the focused scale.
    /// Returns whether the render is the immersive twin of its band (`--imm`).
    static func configure(_ args: [String]) -> Bool {
        func flag(_ name: String) -> String? {
            guard let i = args.firstIndex(of: name), args.count > i + 1 else { return nil }
            return args[i + 1]
        }
        frozenMs = flag("--at-ms").flatMap(Double.init) ?? total * 1000
        forceReduce = args.contains("--reduce-motion")
        forceRibbon = args.contains("--ribbon")
        ScalePath.snapshotFocus = flag("--scale-focus")
        ScalePath.snapshotScope = flag("--scope").flatMap(Int.init)
        ScalePath.snapshotUnbounded = args.contains("--scope-list-full")
        ScaleMatrix.snapshotOpenScope = flag("--flat-open").flatMap(Int.init)
        return args.contains("--imm")
    }
}

private struct ImmersiveKey: EnvironmentKey { static let defaultValue = false }
extension EnvironmentValues {
    /// True under `ImmersiveHost`: Views that have an immersive presentation read it instead of taking a flag.
    var immersive: Bool {
        get { self[ImmersiveKey.self] }
        set { self[ImmersiveKey.self] = newValue }
    }
}

/// Puts a View in its immersive presentation: the choreography clock above it, the `immersive` switch in its environment.
struct ImmersiveHost<Content: View>: View {
    @ViewBuilder let content: Content
    var body: some View { ArrivalHost { content.environment(\.immersive, true) } }
}
