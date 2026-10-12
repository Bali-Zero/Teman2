import Foundation

/// Loads the bundled KBLI dataset and serves ranked search + code lookup.
/// All work is in-memory (1559 records) and offline — no network, no PII.
final class KBLIStore: ObservableObject {
    let all: [KBLI]
    private let byCode: [String: KBLI]

    /// Top-level shape of KBLI_2025_FINAL_CLEAN.json: { metadata, data: [KBLI] }.
    private struct Root: Codable { let data: [KBLI] }

    /// Designated init from an explicit path (used by tests and dev runs).
    init?(jsonPath: String) {
        guard let raw = FileManager.default.contents(atPath: jsonPath),
              let root = try? JSONDecoder().decode(Root.self, from: raw) else { return nil }
        self.all = root.data
        self.byCode = Dictionary(root.data.map { ($0.kode, $0) }, uniquingKeysWith: { a, _ in a })
    }

    /// Convenience init that finds the JSON in the app bundle Resources.
    convenience init?() {
        if let url = Bundle.main.url(forResource: "KBLI_2025_FINAL_CLEAN", withExtension: "json") {
            self.init(jsonPath: url.path)
        } else {
            // dev fallback: next to the executable
            let exe = Bundle.main.bundleURL
                .appendingPathComponent("Contents/Resources/KBLI_2025_FINAL_CLEAN.json")
            self.init(jsonPath: exe.path)
        }
    }

    /// Empty store fallback. AppState wires it as `KBLIStore() ?? KBLIStore.empty()`, so a missing
    /// JSON yields an empty (not nil) store and SearchListView shows the "data.missing" banner —
    /// never a force-unwrap crash. (Verified: AppState.swift uses the `??` fallback, never `!`.)
    private init(empty: Bool) { self.all = []; self.byCode = [:] }
    static func empty() -> KBLIStore { KBLIStore(empty: true) }

    func code(_ k: String) -> KBLI? { byCode[k] }

    // MARK: - 21 KBLI sectors (categories A–U)

    /// The 21 top-level KBLI/ISIC categories. `letter` is the A–U code; `range` is the 2-digit
    /// division span used to assign a code to its sector. Order = canonical A→U.
    static let sectorTable: [(letter: String, lo: Int, hi: Int, en: String, id: String, icon: String)] = [
        ("A",  1,  3,  "Agriculture, Forestry & Fishing", "Pertanian, Kehutanan & Perikanan", "leaf.fill"),
        ("B",  5,  9,  "Mining & Quarrying", "Pertambangan & Penggalian", "mountain.2.fill"),
        ("C", 10, 33,  "Manufacturing", "Industri Pengolahan", "gearshape.2.fill"),
        ("D", 35, 35,  "Electricity & Gas", "Pengadaan Listrik & Gas", "bolt.fill"),
        ("E", 36, 39,  "Water, Sewerage & Waste", "Air, Limbah & Daur Ulang", "drop.fill"),
        ("F", 41, 43,  "Construction", "Konstruksi", "hammer.fill"),
        ("G", 45, 47,  "Wholesale & Retail Trade", "Perdagangan Besar & Eceran", "cart.fill"),
        ("H", 49, 53,  "Transportation & Storage", "Transportasi & Pergudangan", "shippingbox.fill"),
        ("I", 55, 56,  "Accommodation & Food Service", "Akomodasi & Makan-Minum", "fork.knife"),
        ("J", 58, 63,  "Information & Communication", "Informasi & Komunikasi", "antenna.radiowaves.left.and.right"),
        ("K", 64, 66,  "Financial & Insurance", "Keuangan & Asuransi", "banknote.fill"),
        ("L", 68, 68,  "Real Estate", "Real Estat", "building.2.fill"),
        ("M", 69, 75,  "Professional, Scientific & Technical", "Profesional, Ilmiah & Teknis", "briefcase.fill"),
        ("N", 77, 82,  "Administrative & Support Service", "Jasa Administrasi & Penunjang", "tray.full.fill"),
        ("O", 84, 84,  "Public Administration & Defence", "Administrasi Pemerintahan", "building.columns.fill"),
        ("P", 85, 85,  "Education", "Pendidikan", "graduationcap.fill"),
        ("Q", 86, 88,  "Human Health & Social Work", "Kesehatan & Sosial", "cross.case.fill"),
        ("R", 90, 93,  "Arts, Entertainment & Recreation", "Kesenian, Hiburan & Rekreasi", "theatermasks.fill"),
        ("S", 94, 96,  "Other Service Activities", "Aktivitas Jasa Lainnya", "wrench.and.screwdriver.fill"),
        ("T", 97, 98,  "Households as Employers", "Rumah Tangga sebagai Pemberi Kerja", "house.fill"),
        ("U", 99, 99,  "Extraterritorial Organizations", "Organisasi Internasional", "globe"),
    ]

    /// A KBLI sector with a live count of its codes.
    struct Sector: Identifiable, Hashable {
        let letter: String          // "I"
        let en: String
        let id_: String             // localized name (ID)
        let icon: String            // SF Symbol
        let count: Int
        var id: String { letter }
    }

    /// The 21 sectors, each with its real code count (sectors with 0 codes are dropped — there are none).
    lazy var sectors: [Sector] = {
        var counts: [String: Int] = [:]
        for r in all { if let s = Self.sectorLetter(for: r.kode) { counts[s, default: 0] += 1 } }
        return Self.sectorTable.compactMap { t in
            let n = counts[t.letter] ?? 0
            return n > 0 ? Sector(letter: t.letter, en: t.en, id_: t.id, icon: t.icon, count: n) : nil
        }
    }()

    /// Map a 5-digit code to its sector letter via the 2-digit division.
    static func sectorLetter(for code: String) -> String? {
        guard let d = Int(code.prefix(2)) else { return nil }
        for t in sectorTable where d >= t.lo && d <= t.hi { return t.letter }
        return nil
    }

    /// All codes in a sector, ordered by code. (1559 records, in-memory — cheap.)
    func codes(in sector: String) -> [KBLI] {
        all.filter { Self.sectorLetter(for: $0.kode) == sector }
           .sorted { $0.kode < $1.kode }
    }

    /// Result of a search: the (capped) ranked rows plus the TRUE total match count, so the UI
    /// can show "showing 200 of 446 — refine" instead of silently hiding results (scar #2/#3).
    struct Results { let rows: [KBLI]; let total: Int; var truncated: Bool { total > rows.count } }

    /// Max rows handed to the UI list. A scrollable List renders these lazily; beyond this the
    /// honest move is to tell the user to refine, not to keep growing an unscannable list.
    static let displayCap = 300

    /// English translations of `judul` (Indonesian titles) — keyed by the exact Indonesian source
    /// string, same map `OverlayStore.dataEN` reads for card rendering (`kbli-data-i18n-en.json`).
    /// D3a.1 (2026-08-11): search matched ONLY the Indonesian `judul`/`uraian` fields, so an EN-mode
    /// query like "football" found nothing even though the UI itself shows "Football Club" for KBLI
    /// 93121 (judul "Klub Sepak Bola") — the EN title lives in this separate overlay bundle that
    /// `KBLIStore` never read. Loaded again here rather than shared with `OverlayStore` (a private,
    /// per-view instance) so `KBLIStore` stays self-contained for dataset+search — the file is small
    /// (~8.5k string keys covering judul/uraian/etc.) so a second parse is not a real cost.
    static let judulEN: [String: String] = {
        let name = "kbli-data-i18n-en"
        let url = Bundle.main.url(forResource: name, withExtension: "json")
            ?? URL(fileURLWithPath: Bundle.main.bundleURL
                .appendingPathComponent("Contents/Resources/\(name).json").path)
        guard let raw = try? Data(contentsOf: url),
              let obj = try? JSONDecoder().decode([String: String].self, from: raw) else { return [:] }
        return obj
    }()

    /// Ranked search: exact code (0) > prefix code/title, either language (1-2) > substring
    /// judul/uraian/EN-title (3) > fuzzy (4).
    func search(_ query: String) -> Results {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard q.isEmpty == false else {
            return Results(rows: Array(all.prefix(Self.displayCap)), total: all.count)
        }
        var scored: [(KBLI, Int)] = []
        for r in all {
            if let rank = Self.rank(r, q) { scored.append((r, rank)) }
        }
        scored.sort { a, b in a.1 != b.1 ? a.1 < b.1 : a.0.kode < b.0.kode }
        return Results(rows: scored.prefix(Self.displayCap).map { $0.0 }, total: scored.count)
    }

    /// WHERE a query matched a record, not just how well it ranked. `rank` collapses "the term is
    /// in the record's TITLE" and "the term appears somewhere in its prose description" into one
    /// tier (3), which is fine for ordering a search list but wrong for weighting a chat retrieval:
    /// a title match names the activity, a prose match is often incidental vocabulary. Measured
    /// 2026-09-11 on the P2b Q11 miss — "kafe" matching 56303's judul "Aktivitas Rumah Minum/Kafe"
    /// scored identically to "tepat" ("on time") matching an unrelated record's uraian.
    enum MatchField { case code, codePrefix, titlePrefix, title, prose, fuzzy }

    static func matchField(_ r: KBLI, _ q: String) -> MatchField? {
        let code = r.kode.lowercased()
        let judul = r.judul.lowercased()
        let judulEn = judulEN[r.judul]?.lowercased()
        if code == q { return .code }
        if code.hasPrefix(q) { return .codePrefix }
        if judul.hasPrefix(q) || (judulEn?.hasPrefix(q) ?? false) { return .titlePrefix }
        if judul.contains(q) || (judulEn?.contains(q) ?? false) { return .title }
        if r.uraian.lowercased().contains(q) { return .prose }
        let nq = normalize(q)
        if normalize(judul).contains(nq) || normalize(r.uraian).contains(nq) { return .fuzzy }
        if let en = judulEn, normalize(en).contains(nq) { return .fuzzy }
        return nil
    }

    /// Rank one record against a lowercased query; nil = no match.
    /// Text matching is accent/double-consonant tolerant so an Italian/English speaker
    /// searching "villa" still finds the Indonesian "vila" (and "cafè" → "cafe", etc.). D3a.1:
    /// the EN title (when translated) is checked at the SAME tiers as the Indonesian judul, so
    /// "football" (English) and "sepak bola" (Indonesian) both find 93121 regardless of which
    /// language the UI is currently showing — the app-wide language toggle is a display choice,
    /// not a search-scope restriction.
    static func rank(_ r: KBLI, _ q: String) -> Int? {
        let code = r.kode.lowercased()
        let judul = r.judul.lowercased()
        let judulEn = judulEN[r.judul]?.lowercased()
        if code == q { return 0 }
        if code.hasPrefix(q) { return 1 }
        if judul.hasPrefix(q) || (judulEn?.hasPrefix(q) ?? false) { return 2 }
        if judul.contains(q) || r.uraian.lowercased().contains(q) || (judulEn?.contains(q) ?? false) { return 3 }
        // fuzzy fallback: normalize BOTH sides unconditionally so it works in either direction —
        // "villa"→"vila" AND "vila"→"villa" (DeepSeek review: the `nq != q` guard skipped the
        // second case). normalize() is idempotent, so a no-op query just re-checks the same text.
        let nq = normalize(q)
        let nj = normalize(judul)
        if nj.contains(nq) || normalize(r.uraian).contains(nq) { return 4 }
        if let en = judulEn, normalize(en).contains(nq) { return 4 }
        return nil
    }

    /// Fold accents and collapse doubled consonants ("villa"→"vila", "caffè"→"cafe").
    static func normalize(_ s: String) -> String {
        let folded = s.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: nil)
        var out = ""; out.reserveCapacity(folded.count)
        var prev: Character = "\u{0}"
        for ch in folded {
            if ch == prev && ch.isLetter { continue }   // drop the 2nd of a doubled letter
            out.append(ch); prev = ch
        }
        return out
    }
}
