import SwiftUI

/// SPEC-detail-polish D2: the ONE way a View paints `KBLIVerdict.headsUp(record:isID:)` — the label
/// small, the sentence carrying the weight. chip(tone) fill, a 4 pt leading bar in the tone's fg,
/// label 11 semibold tracked .08em, sentence `serif(20)` on a 27 pt line, both in the tone's fg.
/// `.stacked` (search, dossier, ledger, chat rail): label over sentence, 8 apart. `.band` (detail
/// card, full width): a 200 pt label column beside the sentence on one first baseline. With no
/// sentence the label takes the sentence slot at `serif(20)`. The pair is drawn byte for byte; the
/// text wraps, never clamps.
struct HeadsUpBlock: View {
    enum Layout { case stacked, band }

    let label: String
    let sentence: String?
    let tone: Theme.Tone
    var layout: Layout = .stacked

    init(_ hu: (label: String, sentence: String?, tone: Theme.Tone), layout: Layout = .stacked) {
        label = hu.label; sentence = hu.sentence; tone = hu.tone; self.layout = layout
    }

    var body: some View {
        let c = Theme.chip(tone)
        HStack(spacing: 0) {
            Rectangle().fill(c.fg).frame(width: 4)
            Group {
                if let sentence {
                    switch layout {
                    case .stacked:
                        VStack(alignment: .leading, spacing: 8) { labelText(c.fg); sentenceText(sentence, c.fg) }
                    case .band:
                        HStack(alignment: .firstTextBaseline, spacing: 24) {
                            labelText(c.fg).frame(width: 200, alignment: .leading)
                            sentenceText(sentence, c.fg)
                        }
                    }
                } else {
                    sentenceText(label, c.fg)
                }
            }
            .padding(.vertical, 24).padding(.horizontal, 16)
            Spacer(minLength: 0)
        }
        .background(c.bg)
        .accessibilityElement(children: .combine)
    }

    private func labelText(_ fg: Color) -> some View {
        Text(label).font(Theme.scalable(11, weight: .semibold)).tracking(0.88).foregroundStyle(fg)
            .fixedSize(horizontal: false, vertical: true)
    }

    private func sentenceText(_ s: String, _ fg: Color) -> some View {
        Text(s).font(Theme.serif(20)).lineSpacing(Theme.leading(20, 27, serif: true)).foregroundStyle(fg)
            .fixedSize(horizontal: false, vertical: true)
    }
}
