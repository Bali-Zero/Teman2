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
    /// pattern (`per_skala` is `field`'s own name for it). Each of the record's own closed-set values — a
    /// `kewenangan` office, the `perizinan` licence, a non-numeric `jangka_waktu` term — and its own `judul` (lead,
    /// 2026-10-11) reads in English with its original in parentheses after it ("Regent / Mayor (Bupati/Walikota)",
    /// "<English title> (<official title>)"), wherever it stands alone. It does not when it is the whole of a (…) —
    /// the curator's own original —, a title anywhere inside one, inside quotes, or a word of a longer name
    /// ("Instruksi Gubernur Bali"); inside a longer parenthesis an office is prose like any other (#8232 F2:
    /// "(outside Jakarta: Bupati/Walikota)"). The same rule en_purity reads (HARNESS-REQUESTS R19).
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
                let alone = pre.range(of: "\\(\\s*$", options: .regularExpression) != nil
                    && post.range(of: "^\\s*\\)", options: .regularExpression) != nil
                if n("(") > n(")") && (gap.isTitle || alone) || n("\"") % 2 == 1 || n("“") > n("”")
                    || pre.range(of: "[A-Z][a-z]+ $", options: .regularExpression) != nil
                    || post.range(of: "^ [A-Z][a-z]", options: .regularExpression) != nil { continue }
                out.replaceSubrange(Range(m.range, in: out)!, with: "\(gap.en) (\(gap.original))")
            }
            return out
        }.joined(separator: "\n")
    }

    /// The record's `kewenangan` offices, `perizinan` licence, non-numeric `jangka_waktu` terms and `judul` that have
    /// an English here, longest first, so "Bupati/Walikota" is read before a shorter value inside it.
    private static func closedValues(_ k: KBLI) -> [(raw: String, en: String, original: String, isTitle: Bool)] {
        var out: [String: (String, String, Bool)] = [:]
        for p in k.perSkala {
            for v in p.kewenanganLevels.map({ $0.trimmingCharacters(in: .whitespaces) }) where authorityRank(v) > 0 {
                out[v] = (authority(v, isID: false), v, false)
            }
            for v in p.perizinanList where v == "NIB dan Sertifikat Standar" { out[v] = ("NIB + Standard Certificate", v, false) }
            if let v = p.jangkaWaktu?.trimmingCharacters(in: .whitespaces), v.contains(where: \.isLetter), term(v, isID: false) != v {
                out[v] = (term(v, isID: false), v, false)
            }
        }
        let j = k.judul.trimmingCharacters(in: .whitespaces)
        if !j.isEmpty, title(k, isID: false) != j { out[j] = (title(k, isID: false), officialTitle(k), true) }
        return out.sorted { $0.key.count > $1.key.count }.map { ($0.key, $0.value.0, $0.value.1, $0.value.2) }
    }

    /// The roadmap's incorporation step, which the View writes for every code (scaleAwareStep): a PT PMA route only
    /// where a Besar row exists and the code is not nationally closed. English: "sole proprietorship" stands for
    /// "Perorangan" (listed for Zero).
    static func incorporationStep(foreignRoute: Bool, isID: Bool) -> String {
        foreignRoute
            ? (isID ? "PT PMDN (lokal) atau PT PMA (asing) — akta notaris, AHU" : "PT PMDN (local) or PT PMA (foreign) — notary deed, AHU")
            : (isID ? "PT PMDN / CV / Perorangan (lokal, WNI) — akta notaris, AHU"
                    : "PT PMDN / CV / sole proprietorship (local, WNI) — notary deed, AHU")
    }

    /// A dataset string the ledger draws (a scope title, an obligation, a requirement) in the reader's language: the
    /// one `OverlayStore.dataString` table, curated English or the string as written (then under `OriginalLabel`).
    static func data(_ raw: String, isID: Bool) -> String { OverlayStore.shared.dataString(raw, isID: isID) }

    /// A row's scales, "Micro/Small": `scale` per name, in the row's order.
    static func scales(_ raw: [String], isID: Bool) -> String { raw.map { scale($0, isID: isID) }.joined(separator: "/") }

    /// A risk row's tier on the ledger's chips: its full name ("Medium-Low Risk") and the matrix's letters ("MR").
    static func riskTier(_ raw: String, isID: Bool) -> String { Theme.RiskTier.label(raw, isID: isID) }
    static func riskAbbr(_ raw: String?, isID: Bool) -> String { Theme.RiskTier.abbr(raw, isID: isID) }

    /// The roadmap's step duration, a closed set (Q17, exact match): its one Indonesian value, "Otomatis", is a
    /// `jangka_waktu` word and reads as `term` draws it; "1–2w", "post-license" and the rest stay as written.
    static func roadmapDuration(_ raw: String, isID: Bool) -> String {
        !isID && raw == "Otomatis" ? term(raw, isID: false) : raw
    }

    /// An overlay permit name (`authority.pbUmku`, a closed set the instrument maps by exact match): English first,
    /// as the other values ("TDUP — Tourism Business Registration") read. The one curated value that opens with the
    /// Indonesian name keeps its acronym; the name itself stays on the same sheet, in the post-license obligation
    /// "Have a Health Worthiness Certificate (Sertifikat Laik Sehat)" (55203). Every other value stays as written.
    static func permitName(_ raw: String, isID: Bool) -> String {
        guard !isID else { return raw }
        return ["Sertifikat Laik Sehat (SLHS) — Health-Worthiness Certificate": "Health-Worthiness Certificate (SLHS)"][raw] ?? raw
    }

    /// One line of the curated meaning, which is markdown like the `baliContext` MarkdownView draws on the same sheet:
    /// its inline emphasis (the 21 `**…**` pairs of 17 codes, 55204's `*not*`) draws as emphasis, never as asterisks.
    /// The characters are the source's minus the markers; a line the native parser refuses stays as written. A Bali
    /// reason's paired emphasis reads the same way (Q24 over Z-3 for pairs, 2026-10-11); a lone `*` stays (Z-3).
    static func ledgerInline(_ line: String) -> AttributedString {
        (try? AttributedString(markdown: line, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace)))
            ?? AttributedString(line)
    }

    /// A record string with no English source, met by an English reader (Q12 ruling 4): the source came back
    /// unchanged from the translation table and does not read as English.
    static func isOriginal(_ source: String, drawn: String, isID: Bool) -> Bool {
        !isID && drawn == source && !isEnglish(source)
    }
}
