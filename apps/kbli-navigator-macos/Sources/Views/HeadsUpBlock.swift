import SwiftUI

/// SPEC-detail-polish D2: the ONE way a View paints `KBLIVerdict.headsUp(record:isID:)` — the label
/// small, the sentence carrying the weight. chip(tone) fill, a 4 pt leading bar in the tone's fg,
/// label 11 semibold tracked .08em, sentence `serif(20)` on a 27 pt line, both in the tone's fg.
/// `.stacked` (search, dossier, ledger, chat rail): label over sentence, 8 apart. `.band` (detail
/// card, full width): a 200 pt label column beside the sentence on one first baseline. With no
/// sentence the label takes the sentence slot at `serif(20)`. The pair is drawn byte for byte, save a Bali
/// reason's paired emphasis (`LabelBook.emphasis`, Q24); the text wraps, never clamps.
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
                        VStack(alignment: .leading, spacing: 8) {
                            labelText(c.fg).censusFrame("headsup.label")
                            sentenceText(sentence, c.fg).censusFrame("headsup.sentence")
                        }
                    case .band:
                        HStack(alignment: .firstTextBaseline, spacing: 24) {
                            labelText(c.fg).frame(width: 200, alignment: .leading).censusFrame("headsup.label")
                            sentenceText(sentence, c.fg).censusFrame("headsup.sentence")
                        }
                    }
                } else {
                    sentenceText(label, c.fg).censusFrame("headsup.label")
                }
            }
            .padding(.vertical, 24).padding(.horizontal, 16)
            Spacer(minLength: 0)
        }
        .background(c.bg)
        .censusFrame("headsup", "\(tone)")
        .accessibilityElement(children: .combine)
    }

    private func labelText(_ fg: Color) -> some View {
        Text(label).font(Theme.scalable(11, weight: .semibold)).tracking(0.88).foregroundStyle(fg)
            .fixedSize(horizontal: false, vertical: true)
    }

    private func sentenceText(_ s: String, _ fg: Color) -> some View {
        Text(LabelBook.emphasis(s, size: 20)).font(Theme.serif(20)).lineSpacing(Theme.leading(20, 27, serif: true)).foregroundStyle(fg)
            .fixedSize(horizontal: false, vertical: true)
    }
}
