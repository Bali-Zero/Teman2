import SwiftUI

/// SPEC-detail-polish D4: a legal basis or a Bali reason read as citation + text. Presentation only —
/// the one space at the break becomes the line break, so `lead + " " + body == source` byte for
/// byte, and an unsplit text renders whole. Basis: break after the first ": " whose colon sits in
/// the first 160 characters (the lead keeps the colon), else after the first " — " whose dash sits
/// there (the lead keeps " —"); lead 15 semibold structure, body 13/20 muted, optionally in
/// `BalancedColumns`. Reason: break after the first ". " (the lead keeps the period); first sentence
/// 15/26 ink, the rest 13/20 muted. Raw characters stay (`*Vila*`, Z-3). Wraps, never clamps.
struct LeadBody: View {
    enum Kind { case basis, reason }

    let text: String
    let kind: Kind
    var columns: Int = 1
    var gutter: CGFloat = 32

    static func split(_ s: String, _ kind: Kind) -> (lead: String?, body: String?) {
        let c = Array(s)
        func cut(after i: Int) -> (String?, String?) { (String(c[...i]), String(c[(i + 2)...])) }
        switch kind {
        case .basis:
            for i in c.indices.prefix(160) where c[i] == ":" && i + 1 < c.count && c[i + 1] == " " {
                return cut(after: i)
            }
            for i in c.indices.prefix(160) where c[i] == "—" && i > 0 && c[i - 1] == " " && i + 1 < c.count && c[i + 1] == " " {
                return cut(after: i)
            }
            return (nil, s)
        case .reason:
            for i in c.indices where c[i] == "." && i + 1 < c.count && c[i + 1] == " " { return cut(after: i) }
            return (s, nil)
        }
    }

    var body: some View {
        let p = Self.split(text, kind)
        VStack(alignment: .leading, spacing: 8) {
            if let lead = p.lead {
                Text(lead)
                    .font(Theme.scalable(15, weight: kind == .basis ? .semibold : .regular))
                    .lineSpacing(kind == .reason ? Theme.leading(15, 26) : 0)
                    .foregroundStyle(kind == .basis ? Theme.structure : Theme.white)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if let body = p.body, !body.isEmpty {
                if columns > 1 {
                    HStack(alignment: .top, spacing: gutter) {
                        ForEach(Array(BalancedColumns.split(body, into: columns).enumerated()), id: \.offset) { _, col in
                            bodyText(col).frame(maxWidth: .infinity, alignment: .topLeading)
                        }
                    }
                } else {
                    bodyText(body)
                }
            }
        }
    }

    private func bodyText(_ s: String) -> some View {
        Text(s).font(Theme.scalable(13)).lineSpacing(Theme.leading(13, 20)).foregroundStyle(Theme.muted)
            .fixedSize(horizontal: false, vertical: true)
    }
}

/// The line an English View draws above record text that has no English source (Q12 ruling 4). One spelling, so
/// the census binds the text to it; EN-1b's LabelBook constant replaces the literal when it lands.
struct OriginalLabel: View {
    var body: some View {
        Text("Original (Bahasa Indonesia)").font(Theme.scalable(11)).foregroundStyle(Theme.muted)
    }
}

/// The legal basis under its heading (D4): "Legal Basis" / "Dasar Hukum", the original's label when an English
/// reader meets an Indonesian basis (Q12 ruling 4), then LeadBody. The ledger's full-width row; the chat rail next.
struct BasisBlock: View {
    let basis: String
    let isID: Bool
    var columns: Int = 1

    /// Judged on the whole text: 695 of the 722 bases are English analysis quoting the statute in «…», and their
    /// opening clause is a citation with no function word in it, so LabelBook's opening-clause rule is read over
    /// the text with its clause marks blanked.
    static func isOriginal(_ basis: String) -> Bool {
        !LabelBook.isEnglish(String(basis.map { "(;—".contains($0) ? " " : $0 }))
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(isID ? "Dasar Hukum" : "Legal Basis").font(Theme.scalable(11, weight: .semibold)).tracking(0.88)
                .foregroundStyle(Theme.muted)
            if !isID && Self.isOriginal(basis) { OriginalLabel() }
            LeadBody(text: basis, kind: .basis, columns: columns, gutter: 32)
        }
    }
}
