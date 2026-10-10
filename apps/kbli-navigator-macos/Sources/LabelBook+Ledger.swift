import Foundation

/// The ledger's own words (lead ruling 2026-10-10, Q18): a per-View extension of LabelBook, born with its consumer.
/// Closed sets only; every English string here that the dataset does not already carry is listed in the PR body for
/// Zero. Open statute text is never translated here: it is drawn verbatim under `OriginalLabel`.
extension LabelBook {
    /// The Bali chip of the verdict stack (D3, D14): the axis word in the national chip's casing — capitals in
    /// Indonesian, as `pmaStatus` draws the record's word; sentence case in English, as `pmaStatus` draws "Open".
    /// The word, its tone and its VoiceOver sentence come from VerdictBadge, so the three never part.
    static func baliChip(_ v: KBLIVerdict, isID: Bool) -> (word: String, tone: Theme.Tone, voiceOver: String) {
        let state: VerdictBadge.State
        let tone: Theme.Tone
        switch v.bali {
        case .open: state = .open; tone = .open
        case .blocked: state = .blocked; tone = .closed
        case .undetermined: state = .undetermined; tone = .neutral
        }
        let badge = VerdictBadge(state: state, isID: isID)
        let w = badge.text
        return (isID ? w : w.prefix(1) + w.dropFirst().lowercased(), tone, badge.voiceOverLabel)
    }

    /// `per_skala[].jangka_waktu`: numbers and "Otomatis" as PP28ScalePanel has always drawn them; the four other
    /// values of the closed set (921 codes carry a non-numeric term) in curated English. An unknown value stays
    /// verbatim, so the census can name it.
    static func term(_ raw: String, isID: Bool) -> String {
        if !isID, let en = ledgerTerms[raw.trimmingCharacters(in: .whitespaces)] { return en }
        return PP28ScalePanel.formatJangkaWaktu(raw, isID: isID)
    }

    private static let ledgerTerms: [String: String] = [
        "Sesuai ketentuan OJK/BI": "As set by OJK/BI rules",
        "Izin Kemendikbud (di luar OSS)": "Ministry of Education license (outside OSS)",
        "Izin Dinas Sosial/PAUD (di luar OSS)": "Social Affairs Office / early-childhood (PAUD) license (outside OSS)",
        "Sesuai tahapan IUP (ESDM)": "Follows the IUP mining-license stages (ESDM)",
    ]

    /// Q17: a pipeline token quoted inside curated English prose becomes its label by exact match, never by
    /// pattern (`per_skala` is `field`'s own name for it); and each of the record's own closed-set values the
    /// prose quotes where it stands alone reads in English: an office or a licence keeps its original in
    /// parentheses (none when the curator's own gloss follows: "Regent / Mayor (district/city head)"), a term
    /// does not. One inside (…), quotes or a longer name ("Instruksi Gubernur Bali") is the curator's original.
    static func ledgerProse(_ s: String, record k: KBLI, isID: Bool) -> String {
        guard !isID else { return s }
        let t = [("BPS_ONLY", "BPS-only"), ("per_skala", field("per_skala", isID: false))]
            .reduce(s) { $0.replacingOccurrences(of: $1.0, with: $1.1) }
        let gaps = closedValues(k)
        guard !gaps.isEmpty, let rx = try? NSRegularExpression(pattern: gaps.map {
            "(?<!\\w)" + NSRegularExpression.escapedPattern(for: $0.raw) + "(?!\\w)" }.joined(separator: "|")) else { return t }
        return t.components(separatedBy: "\n").map { line in
            var out = line
            for m in rx.matches(in: line, range: NSRange(line.startIndex..., in: line)).reversed() {
                guard let r = Range(m.range, in: line), let gap = gaps.first(where: { $0.raw == String(line[r]) }) else { continue }
                let pre = line[..<r.lowerBound], post = line[r.upperBound...]
                let n = { (c: Character) in pre.filter { $0 == c }.count }
                if n("(") > n(")") || n("\"") % 2 == 1 || n("“") > n("”")
                    || pre.range(of: "[A-Z][a-z]+ $", options: .regularExpression) != nil
                    || post.range(of: "^ [A-Z][a-z]", options: .regularExpression) != nil { continue }
                let glossed = post.hasPrefix(" (") || post.hasPrefix("(")
                out.replaceSubrange(Range(m.range, in: out)!, with: gap.keepsOriginal && !glossed ? "\(gap.en) (\(gap.raw))" : gap.en)
            }
            return out
        }.joined(separator: "\n")
    }

    /// The record's `kewenangan` offices, `perizinan` licences and non-numeric `jangka_waktu` terms that have an
    /// English here, longest first, so "Bupati/Walikota" is read before a shorter value inside it.
    private static func closedValues(_ k: KBLI) -> [(raw: String, en: String, keepsOriginal: Bool)] {
        var out: [String: (String, Bool)] = [:]
        for p in k.perSkala {
            for v in p.kewenanganLevels where authorityRank(v) > 0 { out[v.trimmingCharacters(in: .whitespaces)] = (authority(v, isID: false), true) }
            for v in p.perizinanList where v == "NIB dan Sertifikat Standar" { out[v] = ("NIB + Standard Certificate", true) }
            if let v = p.jangkaWaktu?.trimmingCharacters(in: .whitespaces), v.contains(where: \.isLetter), term(v, isID: false) != v {
                out[v] = (term(v, isID: false), false)
            }
        }
        return out.sorted { $0.key.count > $1.key.count }.map { ($0.key, $0.value.0, $0.value.1) }
    }

    /// The roadmap's step duration, a closed set (Q17, exact match): its one Indonesian value, "Otomatis", is a
    /// `jangka_waktu` word and reads as `term` draws it; "1–2w", "post-license" and the rest stay as written.
    static func roadmapDuration(_ raw: String, isID: Bool) -> String {
        !isID && raw == "Otomatis" ? term(raw, isID: false) : raw
    }

    /// An overlay permit name (`authority.pbUmku`, a closed set, Q17): English first, the original in
    /// parentheses. One curated value opens with the Indonesian name; every other value stays as written.
    static func permitName(_ raw: String, isID: Bool) -> String {
        guard !isID else { return raw }
        return ["Sertifikat Laik Sehat (SLHS) — Health-Worthiness Certificate":
                    "Health-Worthiness Certificate (Sertifikat Laik Sehat, SLHS)"][raw] ?? raw
    }

    /// A record string with no English source, met by an English reader (Q12 ruling 4): the source came back
    /// unchanged from the translation table and does not read as English.
    static func isOriginal(_ source: String, drawn: String, isID: Bool) -> Bool {
        !isID && drawn == source && !isEnglish(source)
    }
}
