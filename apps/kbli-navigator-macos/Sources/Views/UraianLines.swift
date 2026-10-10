import SwiftUI

/// SPEC-detail-polish D9: an `uraian` list hangs. The text splits at its own "\n"; a line opening with
/// "- " keeps the "- " in a fixed 16 pt column and wraps the rest beside it; a plain line that opens a
/// dash run gets 12 above. The lines rejoined with "\n" are the source, byte for byte — save a curated meaning's
/// markdown emphasis (`markdown`), drawn as emphasis and not as its asterisks (`LabelBook.ledgerInline`). Wraps,
/// never clamps.
struct UraianLines: View {
    let text: String
    var markdown = false
    var size: CGFloat = 15
    var color: Color = Theme.white

    var body: some View {
        let ls = text.components(separatedBy: "\n")
        VStack(alignment: .leading, spacing: 4) {
            ForEach(Array(ls.enumerated()), id: \.offset) { i, l in
                Group {
                    if l.hasPrefix("- ") {
                        HStack(alignment: .firstTextBaseline, spacing: 0) {
                            line("- ").frame(width: 16, alignment: .leading)
                            line(String(l.dropFirst(2)))
                        }
                    } else {
                        line(l)
                    }
                }
                .padding(.top, i > 0 && !l.hasPrefix("- ") && i + 1 < ls.count && ls[i + 1].hasPrefix("- ") ? 12 : 0)
            }
        }
    }

    private func line(_ s: String) -> some View {
        (markdown ? Text(strong(LabelBook.ledgerInline(s))) : Text(s)).font(Theme.scalable(size)).lineSpacing(5)
            .foregroundStyle(color).fixedSize(horizontal: false, vertical: true)
    }

    /// Manrope ships no bold face for the strong intent to find, so a strong run takes the SemiBold cut by name; an
    /// italic run has no italic cut and reads in the line's own face.
    private func strong(_ a: AttributedString) -> AttributedString {
        a.runs.reduce(into: AttributedString()) { out, r in
            var piece = AttributedString(a[r.range])
            if r.inlinePresentationIntent?.contains(.stronglyEmphasized) == true { piece.font = Theme.scalable(size, weight: .semibold) }
            out += piece
        }
    }
}
