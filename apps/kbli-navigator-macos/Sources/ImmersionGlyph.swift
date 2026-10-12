import SwiftUI

/// IMM piece the live verdict panel draws (Q28): the division glyph beside the title. Presentation only: the glyph comes from the
/// code's division. No string is drawn here.

/// Division glyph lookup (glyph-forge's set, 24 pt grid, monoline), baked by Tools/design/gen_division_glyphs.py into
/// `DivisionGlyphData`. A division without a glyph returns nil and the callers fall back to the guilloche rosette.
enum DivisionGlyph {
    static let table: [Int: Path] = DivisionGlyphData.ops.mapValues(build)

    static func path(division: Int) -> Path? { table[division] }

    private static func build(_ ops: [Double]) -> Path {
        var p = Path(), i = 0
        func pt(_ k: Int) -> CGPoint { CGPoint(x: ops[i + k], y: ops[i + k + 1]) }
        while i < ops.count {
            switch Int(ops[i]) {
            case 0: i += 1; p.move(to: pt(0)); i += 2
            case 1: i += 1; p.addLine(to: pt(0)); i += 2
            case 2: i += 1; p.addCurve(to: pt(4), control1: pt(0), control2: pt(2)); i += 6
            default: p.closeSubpath(); i += 1
            }
        }
        return p
    }
}

/// A division glyph stroked at `size` pt. Without a glyph for the division it draws the guilloche rosette.
struct GlyphStroke: View {
    let division: Int
    var size: CGFloat
    var alpha: Double
    var width: CGFloat = 2
    var body: some View {
        if let glyph = DivisionGlyph.path(division: division) {
            Canvas { ctx, sz in
                let s = min(sz.width, sz.height) / 24
                ctx.stroke(glyph.applying(CGAffineTransform(scaleX: s, y: s)), with: .color(Theme.structure.opacity(alpha)),
                           style: StrokeStyle(lineWidth: width, lineCap: .round, lineJoin: .round))
            }
            .frame(width: size, height: size)
            .accessibilityHidden(true)
        } else {
            GuillocheRosette(tint: Theme.structure, size: size, alpha: alpha * 0.8)
        }
    }
}
