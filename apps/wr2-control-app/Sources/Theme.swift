import SwiftUI

/// Design tokens — aligned to the Bali Zero brand cortex (tokens.json, verified 2026-06-21)
/// so the control panel speaks the same visual language as the carousels it produces.
/// Editorial-dark, glass/depth, cinematic teal-amber bias.
enum Theme {
    // Palette — warm "paper" light theme (2026-06-23, Zero: "più luminoso e riposante").
    // Editorial ivory surfaces + ink text; brand accents (yellow/red) darkened so they
    // read on a light background. The token NAMES are kept (ink/inkLift/antracite, white)
    // so the 100+ call-sites don't need renaming — only their semantics flipped.
    static let antracite = Color(hex: 0xF4F0E6)   // primary background — warm ivory
    static let ink       = Color(hex: 0xEFEADD)   // deeper panel bg — sand
    static let inkLift   = Color(hex: 0xFBF8F1)   // raised card — near-white paper
    static let yellow    = Color(hex: 0xC79200)   // facts, numbers, accent — amber (darkened for light bg)
    static let red       = Color(hex: 0xB10E28)   // critical / logo — deep red
    static let white     = Color(hex: 0x2B2B2B)   // PRIMARY TEXT — ink (was Color.white; flipped for light theme)
    static let muted     = Color(hex: 0x6B7280)   // captions, secondary — mid grey
    static let green     = Color(hex: 0x2E9E5B)   // success / published — deeper green (reads on light)
    static let blue      = Color(hex: 0x2563C9)   // waitlist — carousel born, awaiting publish

    // semantic surface tokens (theme-aware) — replace hardcoded Color.white/.black opacities
    static let hairline  = Color.black.opacity(0.08)   // borders / dividers (was Color.white.opacity)
    static let scrim     = Color.black.opacity(0.04)   // subtle raised-fill (was Color.white.opacity 0.05)
    static let overlay   = Color.black.opacity(0.55)   // badge backdrop over images (kept dark — sits on photos)

    // step state colors
    static func stepColor(_ state: RunStep.StepState) -> Color {
        switch state {
        case .pending: return muted.opacity(0.5)
        case .active:  return yellow
        case .done:    return green
        case .failed:  return red
        }
    }

    static func statusColor(_ s: RunStatus) -> Color {
        switch s {
        case .starting, .running: return yellow
        case .succeeded:          return green
        case .failed:             return red
        case .cancelled:          return muted
        }
    }

    // Zero Design Studio (the in-house anti-Canva magic layer) — runs on the Mini,
    // node local-webapp-server.mjs on :4317 (--lan). Reached from M5 over Tailscale
    // (LAN is on a different subnet). Verified live 200 in 0.22s, 2026-06-23.
    static let zeroDesignStudioURL = "http://100.93.236.6:4317/"

    // typography
    static let titleFont   = Font.system(size: 26, weight: .bold, design: .default)
    static let headingFont = Font.system(size: 17, weight: .semibold)
    static let bodyFont    = Font.system(size: 13, weight: .regular)
    static let monoFont    = Font.system(size: 11, weight: .regular, design: .monospaced)
    static let numberFont  = Font.system(size: 15, weight: .semibold, design: .rounded)
}

extension Color {
    init(hex: UInt32) {
        let r = Double((hex >> 16) & 0xFF) / 255.0
        let g = Double((hex >> 8) & 0xFF) / 255.0
        let b = Double(hex & 0xFF) / 255.0
        self.init(.sRGB, red: r, green: g, blue: b, opacity: 1.0)
    }
}

// MARK: - Bali Zero logo

/// The real Bali Zero circular logo, loaded from the app bundle Resources (bz-logo.png),
/// with a graceful monogram fallback so the UI never shows a broken image.
struct BZLogo: View {
    var size: CGFloat = 34
    private static let cached: NSImage? = {
        if let url = Bundle.main.url(forResource: "bz-logo", withExtension: "png"),
           let img = NSImage(contentsOf: url) { return img }
        // dev fallback: look next to the executable / Resources
        let exe = Bundle.main.bundleURL.appendingPathComponent("Contents/Resources/bz-logo.png")
        return NSImage(contentsOf: exe)
    }()
    var body: some View {
        Group {
            if let img = BZLogo.cached {
                Image(nsImage: img).resizable().scaledToFit()
            } else {
                ZStack {
                    Circle().fill(Theme.red)
                    Text("BZ").font(.system(size: size * 0.38, weight: .heavy)).foregroundStyle(Theme.white)
                }
            }
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
    }
}

/// A thin yellow "fact" accent rule — the Bali Zero signature for verifiable data.
struct FactRule: View {
    var width: CGFloat = 40
    var body: some View {
        RoundedRectangle(cornerRadius: 2).fill(Theme.yellow).frame(width: width, height: 3)
    }
}

/// A reusable glass/depth card surface for the editorial-dark look.
struct GlassCard<Content: View>: View {
    var padding: CGFloat = 16
    @ViewBuilder var content: Content
    var body: some View {
        content
            .padding(padding)
            .background(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .fill(Theme.inkLift.opacity(0.85))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .strokeBorder(Theme.hairline, lineWidth: 1)
            )
            .shadow(color: .black.opacity(0.10), radius: 10, x: 0, y: 4)
    }
}
