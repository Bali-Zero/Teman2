import Foundation

// LabelBook.swift — Q12 (Z-DECISIONI, 2026-10-10): "in English it's English".
//
// The ONE projection from what the dataset carries to the words a reader sees. Three kinds of key
// reach a View: the canonical status words (`pma_status`: TERBUKA / TERBATAS / TERTUTUP), the
// Italian pipeline enums (`l4_bali.status`) and the `field=value` locators the provenance strip
// used to print. Enums and locators are pipeline keys, not content: they are never drawn, in either
// language (ruling 1). Status, risk, scale and authority words are drawn verbatim in Indonesian
// and translated in English (ruling 5), from the app's existing tables first — `Theme.kbliStatusLabel`,
// `Theme.riskShortLabel`, `PP28ScalePanel.scaleLabel`, `ownershipLine`'s words. The strings this
// file had to add are listed in the EN-1 PR body.
//
// Titles and descriptions come from `OverlayStore` (`kbli-data-i18n-en.json`: judul and uraian
// 1559/1559). Legal text with no English source (`pma_kondisi`, 0/122 translated) is never
// machine-translated: an English View shows it verbatim, labelled by `original(_:isID:)` (ruling 4).
enum LabelBook {

    // MARK: titles and descriptions (rulings 2 and 3)

    static func title(_ k: KBLI, isID: Bool) -> String { OverlayStore.shared.primaryTitle(k, isID: isID) }
    /// The official Indonesian title an English View may keep under the English one — always with
    /// `officialTitleLabel` above it, never bare.
    static func officialTitle(_ k: KBLI) -> String { OverlayStore.shared.primaryTitle(k, isID: true) }
    static let officialTitleLabel = "Official title (Bahasa Indonesia)"
    static func uraian(_ k: KBLI, isID: Bool) -> String { OverlayStore.shared.dataString(k.uraian, isID: isID) }

    /// Legal text as the record states it. An English View quotes it whole under the label when it is
    /// Indonesian: it has no English source and is never machine-translated (ruling 4). Five of the 21
    /// distinct `pma_kondisi` values are English already ("national capital owner must retain single
    /// majority", 51101) and stay as written — the label must not call English Indonesian.
    static func original(_ text: String, isID: Bool) -> String {
        isID || isEnglish(text) ? text : "Original (Bahasa Indonesia): “\(text)”"
    }

    /// The opening clause decides, up to the first " — ", "(" or ";": a record's Indonesian legal phrase
    /// leads and an English gloss may follow it ("Modal dalam negeri 100% — open to domestic capital
    /// only"), never the reverse. English when that clause holds more English than Indonesian function words.
    static func isEnglish(_ text: String) -> Bool {
        let head = text.components(separatedBy: " — ")[0].split(whereSeparator: { "(;".contains($0) }).first ?? ""
        let words = head.lowercased().split(whereSeparator: { !$0.isLetter }).map(String.init)
        let en: Set = ["the", "of", "and", "to", "in", "for", "with", "on", "by", "or", "from", "as", "at", "is",
                       "are", "not", "only", "must", "may", "any", "no"]
        let id: Set = ["yang", "dan", "di", "ke", "dari", "untuk", "dengan", "pada", "dalam", "atau", "oleh",
                       "tidak", "bukan", "bagi", "serta", "hanya"]
        return words.filter(en.contains).count > words.filter(id.contains).count
    }

    // MARK: verdict, risk, scale, authority words (ruling 5)

    /// `pma_status`, the canonical word: verbatim in Indonesian, `ownershipLine`'s word in English.
    static func pmaStatus(_ raw: String?, isID: Bool) -> String {
        guard let raw, raw.isEmpty == false else { return "—" }
        if isID { return raw }
        switch raw.uppercased() {
        case "TERBUKA": return "Open"
        case "TERBATAS": return "Restricted"
        case "TERTUTUP": return "Closed"
        default: return raw   // an unknown word stays visible, so the census can name it
        }
    }

    /// `l4_bali.status`, in both languages. `Theme.kbliStatusLabel` first; it names neither status
    /// added by the 2026-09-17 re-anchor, and its one English label kept an Indonesian word.
    static func baliStatus(_ raw: String, isID: Bool) -> String {
        switch raw.uppercased() {
        case "ATTENZIONE_FASCIA_BALI": return isID ? "Periksa di OSS (kelas risiko Bali)" : "Verify on OSS (Bali risk tier)"
        case "NON_CLASSIFICABILE": return isID ? "Tidak dapat diklasifikasikan" : "Not classifiable"
        case "CHIUSO_PMA_NO_BESAR" where !isID: return "Closed to PMA (Large scale)"
        default: return Theme.kbliStatusLabel(raw, isID: isID)
        }
    }

    static func risk(_ raw: String, isID: Bool) -> String { Theme.riskShortLabel(raw, isID: isID) }
    static func scale(_ raw: String, isID: Bool) -> String { PP28ScalePanel.scaleLabel(raw, isID: isID) }

    static func authorityRank(_ raw: String) -> Int {
        let u = raw.lowercased()
        if u.contains("menteri") || u.contains("kepala badan") { return 3 }  // Minister / Agency Head
        if u.contains("gubernur") { return 2 }                                // Governor
        if u.contains("bupati") || u.contains("walikota") || u.contains("wali kota") { return 1 } // Regent / Mayor
        return 0
    }

    static func authority(_ raw: String, isID: Bool) -> String {
        switch authorityRank(raw) {
        case 3: return isID ? "Menteri/Kepala Badan" : "Minister / Agency Head"
        case 2: return isID ? "Gubernur" : "Governor"
        case 1: return isID ? "Bupati/Walikota" : "Regent / Mayor"
        default: return raw   // unrecognized tier → show the dataset value verbatim rather than guess
        }
    }

    // MARK: provenance — the record keys, named

    /// The human name of a record key the provenance strip cites, so the strip says what the rule
    /// read without printing the key itself.
    static func field(_ key: String, isID: Bool) -> String {
        let names: [String: (en: String, id: String)] = [
            "pma_status": ("PMA status", "Status PMA"),
            "pma_max_asing": ("foreign cap", "batas modal asing"),
            "pma_cap_special": ("special-condition cap", "batas dengan syarat khusus"),
            "pma_kondisi": ("condition", "syarat"),
            "pma_route_to": ("private-sector route", "rute swasta"),
            "pma_cap_verified=false": ("cap not verified", "batas belum diverifikasi"),
            "l4_bali=∅": ("no Bali block on this record", "catatan ini tidak memiliki blok Bali"),
            "l4_bali.status": ("Bali status", "Status Bali"),
            "l4_bali.blocked": ("blocked", "diblokir"),
            "l4_bali.reason": ("reason", "alasan"),
            "l4_bali.confidence": ("confidence", "keyakinan"),
            "moratorium.effective": ("moratorium effective", "moratorium berlaku"),
            "per_skala": ("licensing rows", "baris perizinan"),
            "kategori_risiko": ("risk class", "kelas risiko"),
        ]
        guard let n = names[key] else { return key }
        return isID ? n.id : n.en
    }

    static func yesNo(_ b: Bool, isID: Bool) -> String { b ? (isID ? "ya" : "yes") : (isID ? "tidak" : "no") }

    static func confidence(_ raw: String, isID: Bool) -> String {
        switch raw.uppercased() {
        case "HIGH": return isID ? "tinggi" : "high"
        case "MEDIUM": return isID ? "sedang" : "medium"
        case "LOW": return isID ? "rendah" : "low"
        default: return raw
        }
    }

    // MARK: sentences composed upstream

    private static let enumToken = try! NSRegularExpression(pattern: "\\b[A-Za-z]+(?:_[A-Za-z]+)+\\b")

    /// A sentence composed upstream (a `KBLIVerdict` reason, an `l4_bali.reason`), made drawable. In
    /// both languages a Bali-status enum inside it becomes its label. In English the record's own
    /// `pma_kondisi` becomes the labelled original, and the status word that opens one of the rule's
    /// own national reasons (`KBLIVerdict.nationalVerdict`) becomes its English word. Nothing else is
    /// touched: a curated reason is content, even when it opens with a status word.
    static func humanise(_ s: String, record k: KBLI, isID: Bool) -> String {
        var out = s
        for m in enumToken.matches(in: s, range: NSRange(s.startIndex..., in: s)).reversed() {
            guard let r = Range(m.range, in: out), KBLIVerdict.knownBaliStatuses.contains(out[r].uppercased())
            else { continue }
            out.replaceSubrange(r, with: baliStatus(String(out[r]), isID: isID))
        }
        guard !isID else { return out }
        if let kondisi = k.pmaKondisi, kondisi.isEmpty == false, out.contains(kondisi) {
            out = out.replacingOccurrences(of: kondisi, with: original(kondisi, isID: false))
        }
        for (word, rest) in [("TERTUTUP", " — closed to foreign capital nationally"),
                             ("TERBATAS", " with no foreign-ownership cap recorded")] where out.hasPrefix(word + rest) {
            out = pmaStatus(word, isID: false) + out.dropFirst(word.count)
        }
        return out
    }
}
