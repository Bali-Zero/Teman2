import SwiftUI

/// SPEC-detail-polish D9: an `uraian` list hangs. The text splits at its own "\n"; a line opening with
/// "- " keeps the "- " in a fixed 16 pt column and wraps the rest beside it; a plain line that opens a
/// dash run gets 12 above. The lines rejoined with "\n" are the source, byte for byte. Wraps, never clamps.
struct UraianLines: View {
    let text: String
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
        Text(s).font(Theme.scalable(size)).lineSpacing(5).foregroundStyle(color)
            .fixedSize(horizontal: false, vertical: true)
    }
}
