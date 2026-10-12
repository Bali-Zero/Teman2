import SwiftUI

/// The ledger's gutter mark (spec §3.5, D11): four padi stems of rising height on a ground line,
/// 120 × 330 pt. Stems at x = 18 + 26k, base y 326, tops 266 / 206 / 146 / 86, each carrying
/// 2 / 3 / 4 / 5 "^" grains (the 7 × 9 chevron of `PadiLine`) every 14 pt from its top; the ground
/// line runs 0 → 120 at y 326. Ordinal only: it encodes no datum. Same guardrails as D4Decor.swift —
/// gold stroke, decorative, no text, no hit testing, hidden from VoiceOver, no animation, gone under
/// Increase Contrast. Lives in its own grid cell, never over text.
struct PadiLadder: View {
    static let size = CGSize(width: 120, height: 330)
    static let groundY: CGFloat = 326

    var body: some View {
        if Theme.decorationsVisible {
            Canvas { ctx, _ in
                var ground = Path()
                ground.move(to: CGPoint(x: 0, y: Self.groundY))
                ground.addLine(to: CGPoint(x: Self.size.width, y: Self.groundY))
                ctx.stroke(ground, with: .color(Theme.gold), lineWidth: 1.25)
                var stems = Path(), grains = Path()
                for k in 0..<4 {
                    let x = 18 + 26 * CGFloat(k), top = 266 - 60 * CGFloat(k)
                    stems.move(to: CGPoint(x: x, y: Self.groundY))
                    stems.addLine(to: CGPoint(x: x, y: top))
                    for g in 0..<(k + 2) {
                        let y = top + 14 * CGFloat(g)
                        grains.move(to: CGPoint(x: x - 3.5, y: y + 9))
                        grains.addLine(to: CGPoint(x: x, y: y))
                        grains.addLine(to: CGPoint(x: x + 3.5, y: y + 9))
                    }
                }
                ctx.stroke(stems, with: .color(Theme.gold), lineWidth: 1.25)
                ctx.stroke(grains, with: .color(Theme.gold), lineWidth: 1)
            }
            .frame(width: Self.size.width, height: Self.size.height)
            .allowsHitTesting(false)
            .accessibilityHidden(true)
        }
    }
}
