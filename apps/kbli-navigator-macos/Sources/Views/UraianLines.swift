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
        (markdown ? Text(LabelBook.emphasis(s, size: size)) : Text(s)).font(Theme.scalable(size)).lineSpacing(5)
            .foregroundStyle(color).fixedSize(horizontal: false, vertical: true)
    }
}

extension LabelBook {
    /// `ledgerInline` as drawn at `size`, for the curated meaning (UraianLines) and a Bali reason (LeadBody). Manrope
    /// ships neither a bold nor an italic cut and the app never synthesises weight or slant (`Theme.face`), so every
    /// emphasised run, `**…**` and `*…*` alike, takes the SemiBold cut by name. A code span is not emphasis: it draws
    /// as written, backticks included, in the line's face (55203's footer verdict, "(`dialokasikan` column"). A line
    /// with no `*` is not parsed: it draws exactly as written.
    static func emphasis(_ line: String, size: CGFloat) -> AttributedString {
        guard line.contains("*") else { return AttributedString(line) }
        let a = ledgerInline(line)
        return a.runs.reduce(into: AttributedString()) { out, r in
            var piece = AttributedString(a[r.range])
            if r.inlinePresentationIntent?.contains(.code) == true {
                piece = AttributedString("`" + String(piece.characters) + "`")
            } else if r.inlinePresentationIntent?.isDisjoint(with: [.stronglyEmphasized, .emphasized]) == false {
                piece.font = Theme.scalable(size, weight: .semibold)
            }
            out += piece
        }
    }
}
