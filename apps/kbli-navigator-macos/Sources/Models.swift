import Foundation

/// One KBLI 2025 code, decoded from KBLI_2025_FINAL_CLEAN.json v10.0-L2-oss-risk.
/// JSON keys are Indonesian/snake_case; we map them to Swift camelCase.
struct KBLI: Codable, Identifiable, Hashable {
    let kode: String
    let judul: String
    let uraian: String
    let ruangLingkup: [String]
    let pmaStatus: String?
    let pmaMaxAsing: Int?
    let pmaSource: String?
    /// For govt-reserved codes (TERTUTUP via Pasal 2(1)b), the private/Swasta sibling a PMA client
    /// should register instead (e.g. 86101 govt hospital → 86103 private). Set by the 2026-06-27 audit.
    let pmaRouteTo: String?
    /// For TERBATAS codes: is the foreign-ownership cap % source-backed (Perpres lampiran / NB-3),
    /// or an unconfirmed single-curated-source number? nil for non-TERBATAS. Set by 2026-06-27 audit.
    let pmaCapVerified: Bool?
    /// TERBATAS with a special non-% condition (e.g. 47221 "jaringan distribusi & tempat khusus") —
    /// max_asing=0 numerically but the real meaning is "open with special distribution conditions".
    let pmaCapSpecial: Bool?
    let sektorId: String?
    let perSkala: [PerSkala]
    let l4Bali: L4Bali?
    /// KBLI-2020 predecessor code (when this code was renumbered) + the mapping verdict —
    /// powers the "Renumbered 55193 → 55203" registry note.
    let kbli2020Source: String?
    let statusMapping: String?
    /// The pre-written human enrichment layer (whatItMeans / whatYouNeed / baliContext / …) —
    /// this is what turns the card from a JSON dump into a designed, plain-language brief.
    let intel: Intel2026?

    // --- Added 2026-08-19 for the Phase-2 chat allowlist (design §3) — additive, decode-only
    // fields the card UI does not yet render. `pma_kondisi` is the free-text condition attached
    // to a TERBATAS cap (e.g. "Hanya PMDN (100% domestik)" — the exact string the cross-field
    // consistency gate pattern-matches for the 50111/50112 conflict class). `pma_nota` /
    // `pma_verification_status` are the remaining pma_* allowlist members. `bps_2020_ancestors`
    // is a dict in the raw JSON; only its `codes` array is decoded here — `source_locator`,
    // `parser_run_digest`, `adjudication_status`, `inheritance_verdict`, `adjudicated_by`,
    // `adjudicated_at` are exactly the "digest/adjudication metadata" the design excludes by
    // construction, so they are never given a Swift field at all (no silent partial decode of
    // fields we don't want to risk exposing later).
    let pmaKondisi: String?
    let pmaNota: String?
    let pmaVerificationStatus: String?
    let bpsAncestors: BpsAncestors?

    var id: String { kode }

    /// True when the dataset says this code was renumbered from a 2020 code.
    var isRenumbered: Bool { (statusMapping ?? "").uppercased().contains("RINUMERATO") || kbli2020Source != nil }

    enum CodingKeys: String, CodingKey {
        case kode = "kode_kbli_2025"
        case judul, uraian
        case ruangLingkup = "ruang_lingkup"
        case pmaStatus = "pma_status"
        case pmaMaxAsing = "pma_max_asing"
        case pmaSource = "pma_source"
        case pmaRouteTo = "pma_route_to"
        case pmaCapVerified = "pma_cap_verified"
        case pmaCapSpecial = "pma_cap_special"
        case sektorId = "sektor_id"
        case perSkala = "per_skala"
        case l4Bali = "l4_bali"
        case kbli2020Source = "kbli_2020_source"
        case statusMapping = "status_mapping"
        case intel = "intel_2026"
        case pmaKondisi = "pma_kondisi"
        case pmaNota = "pma_nota"
        case pmaVerificationStatus = "pma_verification_status"
        case bpsAncestors = "bps_2020_ancestors"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        kode = try c.decode(String.self, forKey: .kode)
        judul = (try? c.decode(String.self, forKey: .judul)) ?? ""
        uraian = (try? c.decode(String.self, forKey: .uraian)) ?? ""
        // ruang_lingkup is a list of scope strings (may be absent)
        ruangLingkup = (try? c.decode([String].self, forKey: .ruangLingkup)) ?? []
        pmaStatus = try? c.decode(String.self, forKey: .pmaStatus)
        // pma_max_asing may arrive as Int or String ("100") — accept both.
        if let n = try? c.decode(Int.self, forKey: .pmaMaxAsing) { pmaMaxAsing = n }
        else if let s = try? c.decode(String.self, forKey: .pmaMaxAsing) { pmaMaxAsing = Int(s) }
        else { pmaMaxAsing = nil }
        pmaSource = try? c.decode(String.self, forKey: .pmaSource)
        pmaRouteTo = try? c.decode(String.self, forKey: .pmaRouteTo)
        pmaCapVerified = try? c.decode(Bool.self, forKey: .pmaCapVerified)
        pmaCapSpecial = try? c.decode(Bool.self, forKey: .pmaCapSpecial)
        sektorId = try? c.decode(String.self, forKey: .sektorId)
        perSkala = (try? c.decode([PerSkala].self, forKey: .perSkala)) ?? []
        l4Bali = try? c.decode(L4Bali.self, forKey: .l4Bali)
        // kbli_2020_source / status_mapping may be absent or null
        kbli2020Source = try? c.decode(String.self, forKey: .kbli2020Source)
        statusMapping = try? c.decode(String.self, forKey: .statusMapping)
        intel = try? c.decode(Intel2026.self, forKey: .intel)
        pmaKondisi = try? c.decode(String.self, forKey: .pmaKondisi)
        pmaNota = try? c.decode(String.self, forKey: .pmaNota)
        pmaVerificationStatus = try? c.decode(String.self, forKey: .pmaVerificationStatus)
        bpsAncestors = try? c.decode(BpsAncestors.self, forKey: .bpsAncestors)
    }
}

/// `bps_2020_ancestors` — only the `codes` array is carried (see the field comment on `KBLI`
/// for why the rest of the raw dict is deliberately not modeled).
struct BpsAncestors: Codable, Hashable {
    let codes: [String]

    enum CodingKeys: String, CodingKey { case codes }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        codes = (try? c.decode([String].self, forKey: .codes)) ?? []
    }
}

/// The `intel_2026` enrichment block — human-written, plain-language editorial layer
/// present on every code. Decode is lenient: every field is optional (some codes are sparse).
struct Intel2026: Codable, Hashable {
    let whatItMeans: String?
    let whatYouNeed: String?
    let whatChanged: String?
    let zantaraOpener: String?
    let baliContext: String?
    let youllAlsoNeed: String?
    let whoThisIsFor: String?
    /// TKA (foreign-worker) eligible positions for this code's category — the Kepmen 228/2019 list.
    let tkaInfo: TKAInfo?

    enum CodingKeys: String, CodingKey {
        case whatItMeans, whatYouNeed, whatChanged, zantaraOpener, baliContext, youllAlsoNeed, whoThisIsFor, tkaInfo
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        whatItMeans   = try? c.decode(String.self, forKey: .whatItMeans)
        whatYouNeed   = try? c.decode(String.self, forKey: .whatYouNeed)
        whatChanged   = try? c.decode(String.self, forKey: .whatChanged)
        zantaraOpener = try? c.decode(String.self, forKey: .zantaraOpener)
        baliContext   = try? c.decode(String.self, forKey: .baliContext)
        youllAlsoNeed = try? c.decode(String.self, forKey: .youllAlsoNeed)
        whoThisIsFor  = try? c.decode(String.self, forKey: .whoThisIsFor)
        tkaInfo       = try? c.decode(TKAInfo.self, forKey: .tkaInfo)
    }

    /// Parse `youllAlsoNeed` markdown into structured (code, note) pairs for the Complementary-Codes
    /// registry rows. The REAL data format is PLAIN — `- 16291 — If you also work with rattan` — NOT
    /// bold `**16291**` (only 1 of 237 records ever used bold). The previous bold-only parser silently
    /// returned [] for all 236 plain records → the whole section was dead. We now read the leading
    /// 4-5 digit code on each bullet, tolerating the legacy `**bold**` form too. Existence filtering
    /// (dead cross-links to non-existent codes) happens in the view, which has the store to check.
    var complementaryCodes: [(code: String, note: String)] {
        guard let raw = youllAlsoNeed else { return [] }
        var out: [(String, String)] = []
        for line in raw.split(separator: "\n") {
            var s = line.trimmingCharacters(in: .whitespaces)
            // drop a leading bullet marker and any bold markers
            s = s.trimmingCharacters(in: CharacterSet(charactersIn: "-*• "))
            s = s.replacingOccurrences(of: "**", with: "")
            // the code is the leading run of digits (4-5)
            let code = String(s.prefix(while: { $0.isNumber }))
            guard code.count >= 4, code.count <= 5 else { continue }
            // note is whatever follows, stripped of the separator dash/em-dash
            var note = String(s.dropFirst(code.count)).trimmingCharacters(in: .whitespaces)
            note = note.trimmingCharacters(in: CharacterSet(charactersIn: "—–- "))
            out.append((code, note))
        }
        return out
    }
}

/// The TKA (Tenaga Kerja Asing — foreign worker) eligibility block, per Kepmen 228/2019.
struct TKAInfo: Codable, Hashable {
    let categoryId: Int?
    let categoryName: String?
    let totalInCategory: Int?
    let relevantPositions: [TKAPosition]
    let insight: String?
    let keduaNote: String?

    enum CodingKeys: String, CodingKey {
        case categoryId, categoryName, totalInCategory, relevantPositions, insight, keduaNote
    }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        categoryId      = try? c.decode(Int.self, forKey: .categoryId)
        categoryName    = try? c.decode(String.self, forKey: .categoryName)
        totalInCategory = try? c.decode(Int.self, forKey: .totalInCategory)
        relevantPositions = (try? c.decode([TKAPosition].self, forKey: .relevantPositions)) ?? []
        insight  = try? c.decode(String.self, forKey: .insight)
        keduaNote = try? c.decode(String.self, forKey: .keduaNote)
    }
}

struct TKAPosition: Codable, Hashable, Identifiable {
    let titleEn: String
    let titleId: String
    let isco: String
    var id: String { isco + titleEn }
    enum CodingKeys: String, CodingKey { case titleEn, titleId, isco }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        titleEn = (try? c.decode(String.self, forKey: .titleEn)) ?? ""
        titleId = (try? c.decode(String.self, forKey: .titleId)) ?? ""
        isco    = (try? c.decode(String.self, forKey: .isco)) ?? ""
    }
}

/// Licensing row per business scale (Mikro/Kecil/Menengah/Besar).
struct PerSkala: Codable, Hashable {
    let skalaUsaha: [String]
    let kategoriRisiko: String?
    let perizinan: String?
    let jangkaWaktu: String?
    let kewajiban: [String]
    let persyaratan: [String]   // real per-scale requirements (929 blocks carry these) — was unused
    let kewenangan: String?
    let scopeIndex: Int?        // OSS "ruang lingkup" index — a code can have >1 scope (e.g. 56101
    let scopeUraian: String?    // = Restoran vs Warung Makan), each with its own per-scale rows.
    /// The REAL shape of `kewenangan`/`perizinan` in KBLI_2025_FINAL_CLEAN.json: an ARRAY of authority
    /// levels / license strings (one entry per OSS step), NOT a scalar. The legacy `String?` fields above
    /// only ever populate for the ~160 scale-rows that happen to be scalar; the other 9102 are arrays and
    /// silently decode to nil. These array-backed accessors carry the truth so the UI can derive the
    /// actual authority ("Menteri/Kepala Badan") and license ("NIB dan Sertifikat Standar") per code
    /// instead of a hardcoded "Bupati/Walikota" / "NIB + Standard Cert" lie. Both shapes are tolerated.
    let kewenanganLevels: [String]   // distinct authority tiers across this row's steps
    let perizinanList: [String]      // license strings across this row's steps
    let pbUmkuList: [String]         // PB-UMKU (ancillary licences) across this row's steps

    enum CodingKeys: String, CodingKey {
        case skalaUsaha = "skala_usaha"
        case kategoriRisiko = "kategori_risiko"
        case perizinan
        case jangkaWaktu = "jangka_waktu"
        case kewajiban
        case persyaratan
        case kewenangan
        case scopeIndex = "scope_index"
        case scopeUraian = "scope_uraian"
    }

    /// Separate key set for the array-only fields that have NO scalar twin (so they must not appear
    /// in the main CodingKeys, or the synthesised Encodable conformance breaks — it would expect a
    /// stored property literally named after the key).
    private enum ArrayKeys: String, CodingKey {
        case pbUmku = "pb_umku"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        skalaUsaha = (try? c.decode([String].self, forKey: .skalaUsaha)) ?? []
        kategoriRisiko = try? c.decode(String.self, forKey: .kategoriRisiko)
        perizinan = try? c.decode(String.self, forKey: .perizinan)
        jangkaWaktu = try? c.decode(String.self, forKey: .jangkaWaktu)
        kewajiban = (try? c.decode([String].self, forKey: .kewajiban)) ?? []
        persyaratan = (try? c.decode([String].self, forKey: .persyaratan)) ?? []
        kewenangan = try? c.decode(String.self, forKey: .kewenangan)
        scopeIndex = try? c.decode(Int.self, forKey: .scopeIndex)
        scopeUraian = try? c.decode(String.self, forKey: .scopeUraian)
        // The dataset carries these as ARRAYS for 98% of rows; tolerate the rare scalar form too.
        kewenanganLevels = PerSkala.decodeStringList(c, forKey: .kewenangan)
        perizinanList = PerSkala.decodeStringList(c, forKey: .perizinan)
        // pb_umku has no scalar twin → decode from its own key container (array-or-scalar tolerant).
        let ac = try decoder.container(keyedBy: ArrayKeys.self)
        if let arr = try? ac.decode([String].self, forKey: .pbUmku) {
            pbUmkuList = arr.map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty }
        } else if let s = try? ac.decode(String.self, forKey: .pbUmku) {
            let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
            pbUmkuList = t.isEmpty ? [] : [t]
        } else {
            pbUmkuList = []
        }
    }

    /// Decode a field that is an `[String]` in the canonical data but may appear as a bare `String`
    /// (legacy/partial rows). Empty/blank entries are dropped. Returns [] when absent or null.
    private static func decodeStringList(_ c: KeyedDecodingContainer<CodingKeys>, forKey key: CodingKeys) -> [String] {
        if let arr = try? c.decode([String].self, forKey: key) {
            return arr.map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty }
        }
        if let s = try? c.decode(String.self, forKey: key) {
            let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
            return t.isEmpty ? [] : [t]
        }
        return []
    }
}

/// Bali-specific moratorium status (the "notizia 2026"). Populated for all 1559 codes.
struct L4Bali: Codable, Hashable {
    let status: String
    let reason: String?
    let confidence: String?
    let blocked: Bool
    let moratorium: Moratorium?
    let verdict: String?
    /// Added 2026-08-19 (design §3 nested allowlist for `l4_bali` → `bali_moratorium_status`):
    /// "provisional" vs a settled verdict — the field the allowlist names explicitly alongside
    /// verdict/blocked/status/reason.
    let verdictState: String?

    enum CodingKeys: String, CodingKey {
        case status, reason, confidence, blocked, moratorium, verdict
        case verdictState = "verdict_state"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        status = (try? c.decode(String.self, forKey: .status)) ?? "UNKNOWN"
        reason = try? c.decode(String.self, forKey: .reason)
        confidence = try? c.decode(String.self, forKey: .confidence)
        // `blocked` may be bool or absent
        blocked = (try? c.decode(Bool.self, forKey: .blocked)) ?? false
        moratorium = try? c.decode(Moratorium.self, forKey: .moratorium)
        verdict = try? c.decode(String.self, forKey: .verdict)
        verdictState = try? c.decode(String.self, forKey: .verdictState)
    }
}

/// The Bali moratorium facts (Gubernur letter, 13 May 2026).
struct Moratorium: Codable, Hashable {
    let rule: String?
    let effective: String?
    let source: String?
    let virtualOffice: String?

    enum CodingKeys: String, CodingKey {
        case rule, effective, source
        case virtualOffice = "virtual_office"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        rule = try? c.decode(String.self, forKey: .rule)
        effective = try? c.decode(String.self, forKey: .effective)
        source = try? c.decode(String.self, forKey: .source)
        virtualOffice = try? c.decode(String.self, forKey: .virtualOffice)
    }
}
