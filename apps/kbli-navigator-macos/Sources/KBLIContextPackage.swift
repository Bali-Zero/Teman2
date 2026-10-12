import Foundation

// KBLIContextPackage.swift — the deterministic, zero-LLM context-package builder for the
// Phase-2 codex chat brain (design doc research/operations/2026-08-19-kbli-navigator-phase2-
// codex-chat-design.md §3). Everything in this file is PURE: no process spawn, no network, no
// LLM call — a P2a test asserts that property by construction (nothing here can reach a
// network/process API).
//
// Field names and "known key" snapshots below were measured THIS session (2026-08-19) directly
// against data/source_documents/KBLI_2025_FINAL_CLEAN.json (v10.0-L2-oss-risk, 1559/1559 records
// censused) in the nuzantara monorepo — never assumed from the design doc's prose alone
// (CLAUDE.md anti-hallucination discipline). Re-run KBLISchemaTests after any dataset refresh.

// MARK: - Raw schema index

/// Loads the SAME bundled JSON `KBLIStore` decodes, but keeps every record as a raw
/// `[String: Any]` dictionary, keyed by code. `Codable`'s synthesized decode silently drops any
/// JSON key that isn't named in a `CodingKeys` enum — exactly the silent-serialization failure
/// the design forbids ("the builder fails closed on unknown nested keys"). This index is what
/// lets the builder actually SEE the raw shape and refuse instead of quietly ignoring a new
/// field the dataset grows tomorrow.
final class KBLIRawSchemaIndex {
    private let byCode: [String: [String: Any]]
    let allCodes: [String]

    init?(jsonPath: String) {
        guard let raw = FileManager.default.contents(atPath: jsonPath),
              let root = try? JSONSerialization.jsonObject(with: raw) as? [String: Any],
              let data = root["data"] as? [[String: Any]] else { return nil }
        var m: [String: [String: Any]] = [:]
        var order: [String] = []
        m.reserveCapacity(data.count)
        for rec in data {
            guard let code = rec["kode_kbli_2025"] as? String else { continue }
            m[code] = rec
            order.append(code)
        }
        self.byCode = m
        self.allCodes = order
    }

    /// Convenience init that finds the JSON in the app bundle Resources (mirrors `KBLIStore`).
    convenience init?() {
        if let url = Bundle.main.url(forResource: "KBLI_2025_FINAL_CLEAN", withExtension: "json") {
            self.init(jsonPath: url.path)
        } else {
            let exe = Bundle.main.bundleURL
                .appendingPathComponent("Contents/Resources/KBLI_2025_FINAL_CLEAN.json")
            self.init(jsonPath: exe.path)
        }
    }

    func raw(_ code: String) -> [String: Any]? { byCode[code] }
}

// MARK: - Schema-snapshot fail-closed validator

enum KBLISchemaError: Error, CustomStringConvertible, Equatable {
    case unknownNestedKey(code: String, path: String, key: String)
    var description: String {
        switch self {
        case .unknownNestedKey(let code, let path, let key):
            return "KBLI \(code): unknown key '\(key)' at \(path) — dataset schema drift; the " +
                   "builder refuses to serialize this record silently (design §3 fail-closed rule)"
        }
    }
}

enum KBLISchemaSnapshot {
    // Measured 2026-08-19 against data/source_documents/KBLI_2025_FINAL_CLEAN.json in THIS
    // checkout, full census over all 1,559 records. This is a SNAPSHOT of every key the dataset
    // is known to carry today — including ones deliberately never serialized into the package
    // (provenance/adjudication metadata) — so the fail-closed check below fires only on a key
    // nobody has ever seen, never on one we've simply chosen to exclude.
    //
    // 2026-09-13, dataset anchor moved from the app's own copy (a5721756…) to the monorepo
    // CANONICAL c69a260d… (ROW-IDENTITY-CONTRACT.md §2 — an ordinal is meaningless across
    // datasets, so both halves of the benchmark had to agree on one): the L2 re-ingestion added
    // `absent_probes` to 13 records (02202, 03223, 03232, 35131, 35132, 56400, 58120, 58130,
    // 59111, 59121, 60102, 66303, 74300) — an array of ISO dates recording when an absence was
    // probed. Provenance metadata, never serialized into the package, exactly the class this
    // snapshot's comment already covers. Measured, not assumed: without this key those 13
    // records fail the fail-closed check and the builder refuses to serve them.
    //
    // 2026-09-17, dataset re-anchored to canonical b30b1759…: full 1,559-record census against
    // the new file found two more unknown-key classes, both provenance/citation metadata, never
    // serialized into the package. `l4_bali.closure` (a new key at the TOP LEVEL of `l4_bali`,
    // present on the 40 CHIUSO_BALI records) carries the closure's own source citation
    // (instrument/published/url/list_source/list_url/approval/ancestors_2020/scope_qualifier) —
    // added to `l4BaliKnownKeys` below, not recursively validated (this file's validator only
    // descends into `moratorium`, by design; `closure`'s own shape is not this snapshot's job).
    // `l4_bali.moratorium.{request,source_url,until}` are three new keys inside the moratorium
    // block present on ALL 1,559 records (the Governor's letter reference, its published URL, and
    // the moratorium's end condition) — added to `moratoriumKnownKeys`.
    static let topLevelKnownKeys: Set<String> = [
        "_data_note", "_l1_source", "_l2_source", "_l2_status", "_source", "_source_relabeled",
        "absent_probes",
        "aggregation_note", "bps_2020_ancestors", "intel_2026", "judul", "kbli_2020_source",
        "kode_kbli_2025", "l4_bali", "mapping_note", "per_skala", "per_skala_disputed_pp28_collision",
        "per_skala_disputed_pp28_mice", "per_skala_legacy", "pma_cap_note", "pma_cap_special",
        "pma_cap_verified", "pma_correction", "pma_kondisi", "pma_max_asing", "pma_nota",
        "pma_official_basis", "pma_prioritas", "pma_route_to", "pma_source", "pma_source_vintage",
        "pma_status", "pma_verification_status", "pp28_sources", "ruang_lingkup", "sektor_id",
        "sektors", "status_mapping", "uraian",
    ]
    static let l4BaliKnownKeys: Set<String> = [
        "bali_closure_note", "bali_closure_proposed", "blocked", "closure", "confidence",
        "from_2020", "moratorium", "needs_review", "reason", "review_basis", "rule", "status",
        "verdict", "verdict_state",
    ]
    static let moratoriumKnownKeys: Set<String> = [
        "effective", "request", "rule", "source", "source_url", "until", "virtual_office",
    ]
    static let perSkalaKnownKeys: Set<String> = [
        "dati_inferiti", "fiktif_positif", "jangka_waktu", "jangka_waktu_source", "kategori_risiko",
        "kewajiban", "kewenangan", "parameter", "pb_umku", "perizinan", "persyaratan",
        "sanksi_denda", "sanksi_pencabutan", "sanksi_penghentian", "sanksi_peringatan",
        "scope_index", "scope_uraian", "skala_usaha",
    ]
    static let bpsAncestorsKnownKeys: Set<String> = [
        "adjudicated_at", "adjudicated_by", "adjudication_status", "codes", "inheritance_verdict",
        "parser_run_digest", "sebagian", "source_locator",
    ]

    /// Validate ONE record's nested objects against the snapshot. Throws on the first unknown
    /// key found (deterministic order: top level → l4_bali → moratorium → each per_skala row →
    /// bps_2020_ancestors).
    static func validate(code: String, raw: [String: Any]) throws {
        try checkKeys(Set(raw.keys), against: topLevelKnownKeys, code: code, path: "<record>")
        if let l4 = raw["l4_bali"] as? [String: Any] {
            try checkKeys(Set(l4.keys), against: l4BaliKnownKeys, code: code, path: "l4_bali")
            if let mor = l4["moratorium"] as? [String: Any] {
                try checkKeys(Set(mor.keys), against: moratoriumKnownKeys, code: code, path: "l4_bali.moratorium")
            }
        }
        if let rows = raw["per_skala"] as? [[String: Any]] {
            for (i, row) in rows.enumerated() {
                try checkKeys(Set(row.keys), against: perSkalaKnownKeys, code: code, path: "per_skala[\(i)]")
            }
        }
        if let bps = raw["bps_2020_ancestors"] as? [String: Any] {
            try checkKeys(Set(bps.keys), against: bpsAncestorsKnownKeys, code: code, path: "bps_2020_ancestors")
        }
    }

    private static func checkKeys(_ present: Set<String>, against known: Set<String>, code: String, path: String) throws {
        let unknown = present.subtracting(known)
        if let key = unknown.sorted().first {
            throw KBLISchemaError.unknownNestedKey(code: code, path: path, key: key)
        }
    }
}

// MARK: - Shared helpers

/// Serialized byte size of a JSON-serializable dictionary. `.sortedKeys` makes output
/// deterministic (byte-for-byte reproducible in tests).
func kbliJSONByteCount(_ obj: [String: Any]) -> Int {
    guard let data = try? JSONSerialization.data(withJSONObject: obj, options: [.sortedKeys]) else { return 0 }
    return data.count
}

/// Clip a string to at most `maxBytes` UTF-8 bytes (marker included), never splitting a
/// multi-byte scalar. Declared, never silent — every caller supplies an explicit marker.
func kbliClipToBytes(_ s: String, maxBytes: Int, marker: String) -> String {
    if s.utf8.count <= maxBytes { return s }
    var clipped = s
    while clipped.isEmpty == false, clipped.utf8.count + marker.utf8.count > maxBytes {
        clipped.removeLast()
    }
    return clipped + marker
}

// MARK: - Row identity (docs/gates/ROW-IDENTITY-CONTRACT.md)

/// §3 of the contract — the normalised label of a `per_skala` row, derived from `skala_usaha`.
///
/// NOT required to be unique: the ordinal identifies the row, this corroborates that both halves
/// of the benchmark are pointing at the same row of the same record. The monorepo half
/// (`scripts/kbli_bench/row_identity.py`) implements the same four steps in the same order, and a
/// shared golden fixture makes the two agree on a literal instead of on a hope.
/// STRINGS ONLY (council round 1, codex-gpt-5.6-sol, finding 6). An earlier draft coerced a
/// non-string element with the language's own string conversion, which is not ONE rule: Swift
/// writes `true` where Python writes `True`, so two conforming implementations would have derived
/// DIFFERENT identities from the same record. A label this cannot form is `-`.
func kbliSkalaKey(_ row: [String: Any]) -> String {
    let parts: [String]
    if let arr = row["skala_usaha"] as? [String] { parts = arr }
    else if let s = row["skala_usaha"] as? String { parts = [s] }
    else { return "-" }
    let joined = parts.joined(separator: "+")
    // 1) NFKC, 2) lowercase, 3) whitespace runs collapsed, 4) ends stripped.
    let folded = joined.precomposedStringWithCompatibilityMapping.lowercased()
    let key = folded.split(whereSeparator: { $0.isWhitespace }).joined(separator: " ")
    return key.isEmpty ? "-" : key
}

/// §1 — one served row, declared by identity and not by position in the served array.
///
/// `ordinal` is the row's 0-based index in the record's `per_skala` array in CANONICAL order,
/// which §2 defines as its physical order in the anchored dataset. The whole contract exists
/// because the builder does NOT serve rows in that order: it puts question-matched rows first,
/// so the COUNT it used to declare named no set (council round 5, codex-gpt-5.6-sol, #6428 —
/// "4 rows of 46710" means canonical rows 5-8, and a `[:4]` slice on the scorer's side handed the
/// judge four rows the model never saw while hiding four it did).
struct KBLIServedRowIdentity {
    let ordinal: Int
    let skalaKey: String
    /// §4 — how many items of that list the model was shown. A REQUIRED, non-optional count,
    /// never a nullable "truncated to": Swift's synthesized `Codable` omits a nil Optional while
    /// Python writes an explicit null, so a nullable field would mean "the whole list" on one
    /// side and "the runner forgot to declare" on the other, and the permissive reading is the
    /// very defect this contract exists to abolish. Order inside these lists is physical, so
    /// here a count DOES name the set and the scorer slices to it.
    let persyaratanServed: Int
    let kewajibanServed: Int
}

// MARK: - Per-record reduction

enum KBLIRecordReduction {
    struct Result {
        let code: String
        let dict: [String: Any]
        let bytes: Int
        let mandatoryBytes: Int   // size of `dict` with `per_skala` rows empty (the never-drop floor)
        let isConflict: Bool
        let capIfKnown: Int?
        let rowsIncluded: Int
        let rowsTotal: Int
        /// The identities of the rows this reduction served, IN SERVED ORDER (§4). `rowsIncluded`
        /// is `rowsServed.count` by construction — the count IS the served count, and a test on
        /// each side of the contract asserts it.
        let rowsServed: [KBLIServedRowIdentity]
    }

    static let uraianClipBytes = 4096
    static let perRowListItemCap = 6
    static let perRowListItemCharCap = 400

    /// Domestic-only `pma_kondisi` pattern for the cross-field consistency gate (design §3,
    /// finding R4-1). Measured THIS session: matches EXACTLY 50111/50112 across all 1,559
    /// records. Deliberately narrower than a loose "PMDN|domestik" substring, which would also
    /// catch 50121's "Kemitraan dengan PMDN" (a PARTNERSHIP condition, compatible with a nonzero
    /// cap — not a conflict) — verified by census before choosing this pattern.
    static let domesticOnlyPattern = try! NSRegularExpression(
        pattern: "Hanya PMDN|100%\\s*domestik|100%\\s*domestic", options: [.caseInsensitive])

    static func isDomesticOnlyConflict(kondisi: String?, capAsing: Int?) -> Bool {
        guard let k = kondisi, let cap = capAsing, cap > 0 else { return false }
        let range = NSRange(k.startIndex..<k.endIndex, in: k)
        return domesticOnlyPattern.firstMatch(in: k, options: [], range: range) != nil
    }

    /// Reduce one raw record to its allowlisted, typed-reduced form. `perSkalaByteBudget` bounds
    /// ONLY the `per_skala.rows` portion — the rest of the record (scalars, uraian, ruang_lingkup,
    /// bps_2020_ancestors, the ownership axis, bali_moratorium_status) is always included in full,
    /// which is the "mandatory floor" every never-drop record pays regardless of budget pressure.
    static func reduce(code: String, raw: [String: Any], questionTerms: [String], perSkalaByteBudget: Int) -> Result {
        var dict: [String: Any] = [:]
        dict["kode_kbli_2025"] = code
        dict["judul"] = raw["judul"] as? String ?? ""
        dict["sektor_id"] = raw["sektor_id"] ?? NSNull()
        dict["status_mapping"] = raw["status_mapping"] ?? NSNull()

        let uraianFull = raw["uraian"] as? String ?? ""
        dict["uraian"] = kbliClipToBytes(uraianFull, maxBytes: uraianClipBytes,
                                          marker: "…[truncated — full text on the code page]")

        // ruang_lingkup — array on all 1,559 records (census R2-5), serialized WHOLE, never clipped.
        dict["ruang_lingkup"] = raw["ruang_lingkup"] as? [String] ?? []

        if let bps = raw["bps_2020_ancestors"] as? [String: Any] {
            dict["bps_2020_ancestors"] = ["codes": bps["codes"] as? [String] ?? []]
        }

        // Ownership axis — cross-field consistency gate (R4-1): a conflict-marked record
        // replaces its ownership fields with `pma_conflict: true` outright.
        let kondisi = raw["pma_kondisi"] as? String
        let capAsing = raw["pma_max_asing"] as? Int
        let isConflict = isDomesticOnlyConflict(kondisi: kondisi, capAsing: capAsing)
        if isConflict {
            dict["pma_conflict"] = true
        } else {
            dict["pma_status"] = raw["pma_status"] ?? NSNull()
            dict["pma_max_asing"] = raw["pma_max_asing"] ?? NSNull()
            dict["pma_kondisi"] = kondisi ?? NSNull()
            dict["pma_nota"] = raw["pma_nota"] ?? NSNull()
            dict["pma_verification_status"] = raw["pma_verification_status"] ?? NSNull()
        }

        // l4_bali → bali_moratorium_status: semantic-collision rename (R2-2) so a model can never
        // read "not blocked by the moratorium" as "open to foreign capital".
        if let l4 = raw["l4_bali"] as? [String: Any] {
            var bali: [String: Any] = [:]
            bali["verdict_state"] = l4["verdict_state"] ?? NSNull()
            bali["blocked"] = l4["blocked"] ?? NSNull()
            bali["status"] = l4["status"] ?? NSNull()
            bali["reason"] = l4["reason"] ?? NSNull()
            if let mor = l4["moratorium"] as? [String: Any] {
                bali["moratorium"] = [
                    "rule": mor["rule"] ?? NSNull(),
                    "effective": mor["effective"] ?? NSNull(),
                    "source": mor["source"] ?? NSNull(),
                ] as [String: Any]
            } else {
                bali["moratorium"] = NSNull()
            }
            dict["bali_moratorium_status"] = bali
        }

        // THE VERDICT (KBLIVerdict.swift) — the same value the card banner renders, derived
        // by the same rule from the same record, serialized so the model is TOLD the verdict
        // instead of being handed `blocked` / `pma_status` / `pma_max_asing` and left to infer
        // one of its own. This is the seam where chat and card stopped being two products: a
        // divergence is now a diff in one function, not an argument between two files.
        dict["pma_bali_verdict"] = KBLIVerdict.of(rawRecord: raw, code: code).packageDictionary()

        let mandatoryDict = dict   // snapshot BEFORE per_skala is added
        let mandatoryBytes = kbliJSONByteCount(mandatoryDict)

        let rawRows = raw["per_skala"] as? [[String: Any]] ?? []
        let (rows, served) = selectPerSkalaRows(rawRows, questionTerms: questionTerms,
                                                  maxBytes: max(0, perSkalaByteBudget))
        let includedCount = served.count
        dict["per_skala"] = [
            "rows_included": includedCount,
            "rows_total": rawRows.count,
            "note": "full table on the code page",
            "rows": rows,
        ] as [String: Any]

        let totalBytes = kbliJSONByteCount(dict)
        return Result(code: code, dict: dict, bytes: totalBytes, mandatoryBytes: mandatoryBytes,
                      isConflict: isConflict, capIfKnown: isConflict ? nil : capAsing,
                      rowsIncluded: includedCount, rowsTotal: rawRows.count,
                      rowsServed: served)
    }

    /// Question-matched rows first, then physical order; rows accumulate in that priority order
    /// UNTIL the byte budget is reached (design §3, R3-2 — NOT a row-count cap: the 46710 case,
    /// 4 rows matching "bahan bakar gas cair" at ~20.8 KiB each, is exactly why a count cap alone
    /// breaks the package cap).
    /// Returns the reduced rows AND their identities in served order (§4), never a bare count:
    /// the ordinals below are indices into `rawRows`, which is the record's canonical order, and
    /// the served order deliberately is not that order.
    private static func selectPerSkalaRows(_ rawRows: [[String: Any]], questionTerms: [String], maxBytes: Int) -> ([[String: Any]], [KBLIServedRowIdentity]) {
        guard maxBytes > 0, rawRows.isEmpty == false else { return ([], []) }
        let terms = questionTerms.map { $0.lowercased() }.filter { $0.isEmpty == false }
        func matches(_ row: [String: Any]) -> Bool {
            guard terms.isEmpty == false else { return false }
            let usaha = (row["skala_usaha"] as? [String] ?? []).joined(separator: " ").lowercased()
            let scope = (row["scope_uraian"] as? String ?? "").lowercased()
            let hay = usaha + " " + scope
            return terms.contains { hay.contains($0) }
        }
        // Carry the CANONICAL index through the reordering — that index is the row's identity.
        let indexed = Array(rawRows.enumerated())
        let ordered = indexed.filter { matches($0.element) } + indexed.filter { matches($0.element) == false }

        var out: [[String: Any]] = []
        var served: [KBLIServedRowIdentity] = []
        var used = 0
        for (ordinal, row) in ordered {
            let reduced = reduceRow(row)
            let sz = kbliJSONByteCount(reduced.row) + 2   // ~array-element separator overhead
            if used + sz > maxBytes { break }             // "accumulate ... UNTIL the budget is reached"
            out.append(reduced.row)
            served.append(KBLIServedRowIdentity(ordinal: ordinal, skalaKey: kbliSkalaKey(row),
                                                persyaratanServed: reduced.persyaratanServed,
                                                kewajibanServed: reduced.kewajibanServed))
            used += sz
        }
        return (out, served)
    }

    /// §4 — the reduction DECLARES the list truncation it applied instead of leaving the marker
    /// as the only trace of it. A marker is for the model; a number is for the scorer.
    private static func reduceRow(_ row: [String: Any]) -> (row: [String: Any], persyaratanServed: Int, kewajibanServed: Int) {
        var r: [String: Any] = [:]
        r["skala_usaha"] = row["skala_usaha"] as? [String] ?? []
        r["kategori_risiko"] = row["kategori_risiko"] ?? NSNull()
        r["jangka_waktu"] = row["jangka_waktu"] ?? NSNull()
        r["scope_uraian"] = row["scope_uraian"] ?? NSNull()
        r["perizinan"] = normalizedStringList(row["perizinan"])
        let persyaratan = cappedList(normalizedStringList(row["persyaratan"]))
        let kewajiban = cappedList(normalizedStringList(row["kewajiban"]))
        r["persyaratan"] = persyaratan.items
        r["kewajiban"] = kewajiban.items
        return (r, persyaratan.servedCount, kewajiban.servedCount)
    }

    private static func normalizedStringList(_ v: Any?) -> [String] {
        if let arr = v as? [String] { return arr }
        if let s = v as? String, s.isEmpty == false { return [s] }
        return []
    }

    /// Per-row caps on the large list sub-fields (persyaratan/kewajiban) with a declared
    /// truncation marker — never a silent cut (design §3).
    private static func cappedList(_ items: [String]) -> (items: [String], servedCount: Int) {
        var out: [String] = []
        for item in items.prefix(perRowListItemCap) {
            if item.utf8.count > perRowListItemCharCap {
                out.append(kbliClipToBytes(item, maxBytes: perRowListItemCharCap, marker: "…[truncated]"))
            } else {
                out.append(item)
            }
        }
        // The number of REAL items served — the marker below is not one of them, and the scorer
        // slices the canonical list to exactly this many. Always a number, never nil: see
        // KBLIServedRowIdentity for why a nullable count cannot cross the two encoders intact.
        let servedCount = min(items.count, perRowListItemCap)
        guard items.count > perRowListItemCap else { return (out, servedCount) }
        out.append("…[\(items.count - perRowListItemCap) more — full list on the code page]")
        return (out, servedCount)
    }
}

// MARK: - Package assembly

struct KBLIChatTurn {
    let role: String   // "user" | "assistant"
    let text: String
}

enum KBLIPackageOutcome: Equatable {
    case built(prompt: String, includedCodes: Set<String>, capsByCode: [String: Int],
               conflictCodes: Set<String>, totalBytes: Int)
    case narrowComparison(codes: [String])
    case questionTooLong(byteCount: Int)
    case schemaViolation(String)

    static func == (lhs: KBLIPackageOutcome, rhs: KBLIPackageOutcome) -> Bool {
        switch (lhs, rhs) {
        case (.built(_, let c1, let cap1, let cf1, let b1), .built(_, let c2, let cap2, let cf2, let b2)):
            return c1 == c2 && cap1 == cap2 && cf1 == cf2 && b1 == b2
        case (.narrowComparison(let a), .narrowComparison(let b)): return a == b
        case (.questionTooLong(let a), .questionTooLong(let b)): return a == b
        case (.schemaViolation(let a), .schemaViolation(let b)): return a == b
        default: return false
        }
    }
}

enum KBLIContextPackageBuilder {
    static let packageBudgetBytes = 64 * 1024
    static let historyBudgetBytes = 16 * 1024
    static let questionBudgetBytes = 4 * 1024
    static let anchorReservedBytes = 16 * 1024
    static let totalHardCapBytes = 90 * 1024
    static let maxExplicitCodes = 3
    static let maxAnchors = 4
    static let maxSearchHits = 5
    static let maxHistoryTurns = 12
    static let assistantTurnStorageClipBytes = 4096

    /// WHAT THE PACKAGE ACTUALLY SERVED, for a caller that has to prove it later.
    ///
    /// `includedCodes` says which records entered the package; it does NOT say how much of each
    /// one the model was shown. `per_skala.rows` is the only part whose extent varies — it is
    /// filled up to a byte budget and a record included as a session anchor can be served with
    /// ZERO rows. The P2b scorer judged answers against the canonical rows for every code in
    /// `package_codes` and so could count a requirement invented from a row the model never saw
    /// as supported by the record (council round 4, codex-gpt-5.6-sol; monorepo
    /// scripts/kbli_bench/score_p2b.py). The cure is for the BUILDER to declare what it served,
    /// once, from its own reduction — never for the scorer to re-derive this budget in Python.
    ///
    /// Optional and additive on purpose: every existing caller keeps its call site unchanged and
    /// pays nothing, and the benchmark runner passes a box to fill.
    /// SUPERSEDED IN PLACE 2026-09-13 (docs/gates/ROW-IDENTITY-CONTRACT.md): this map used to
    /// carry a COUNT per code, and council round 5 showed a count names no set here, because the
    /// rows are served relevance-first. `perSkalaRowsServedByCode` is the declaration that does
    /// name one; the two counts are kept because they are the denominators the scorer reports,
    /// and `perSkalaRowsByCode[code] == perSkalaRowsServedByCode[code]?.count` is asserted.
    final class FieldMap {
        private(set) var perSkalaRowsByCode: [String: Int] = [:]
        private(set) var perSkalaRowsTotalByCode: [String: Int] = [:]
        private(set) var perSkalaRowsServedByCode: [String: [KBLIServedRowIdentity]] = [:]
        init() {}
        fileprivate func record(code: String, included: Int, total: Int,
                                served: [KBLIServedRowIdentity]) {
            perSkalaRowsByCode[code] = included
            perSkalaRowsTotalByCode[code] = total
            perSkalaRowsServedByCode[code] = served
        }
    }

    static func build(question: String, currentCard: KBLI?, history: [KBLIChatTurn],
                       store: KBLIStore, schema: KBLIRawSchemaIndex,
                       fieldMap: FieldMap? = nil) -> KBLIPackageOutcome {
        let qBytes = question.utf8.count
        if qBytes > questionBudgetBytes { return .questionTooLong(byteCount: qBytes) }

        let explicitCodes = extractCodes(from: question, knownIn: schema)
        if explicitCodes.count > maxExplicitCodes { return .narrowComparison(codes: explicitCodes) }

        let retained = Array(history.suffix(maxHistoryTurns))
        // The top `maxAnchors` distinct history codes (newest-first) become anchor CANDIDATES;
        // anything beyond that is excluded by the cap itself, structurally — not a budget
        // decision — and still needs declaring in the preamble alongside any candidate that
        // additionally fails to fit its budget slice below (design §3.4).
        let allHistoryCodes = extractAnchors(from: retained, knownIn: schema)
        let anchorCodes = Array(allHistoryCodes.prefix(maxAnchors))
        let structurallyDroppedAnchors = Array(allHistoryCodes.dropFirst(maxAnchors))
        let searchHits = searchHitsFor(question: question, store: store)
        let questionTerms = tokenize(question)

        var included = Set<String>()
        var neverDrop: [String] = []
        func claim(_ code: String) { if included.insert(code).inserted { neverDrop.append(code) } }
        explicitCodes.forEach(claim)
        if let c = currentCard?.kode { claim(c) }

        // Schema-snapshot fail-closed check on every NEVER-DROP record (question codes + card).
        // T3/T4 records get the same check further down but degrade to a silent drop instead of
        // failing the whole build — only a record we CANNOT afford to omit fails closed here.
        for code in neverDrop {
            guard let raw = schema.raw(code) else { continue }
            do { try KBLISchemaSnapshot.validate(code: code, raw: raw) }
            catch { return .schemaViolation(String(describing: error)) }
        }

        var reductions: [String: KBLIRecordReduction.Result] = [:]
        var usedBytes = 0
        for code in neverDrop {
            guard let raw = schema.raw(code) else { continue }
            let r = KBLIRecordReduction.reduce(code: code, raw: raw, questionTerms: questionTerms,
                                                perSkalaByteBudget: packageBudgetBytes)
            reductions[code] = r
            usedBytes += r.bytes
        }

        // If question codes + card together exceed the package budget, the CARD's per_skala rows
        // shrink (byte-budgeted) — question codes are never shrunk, never dropped (design §3
        // declared victim order).
        if usedBytes > packageBudgetBytes, let cardCode = currentCard?.kode,
           let raw = schema.raw(cardCode), let cardR = reductions[cardCode] {
            let othersBytes = usedBytes - cardR.bytes
            let availableForCard = max(0, packageBudgetBytes - othersBytes)
            let perSkalaBudget = max(0, availableForCard - cardR.mandatoryBytes)
            let shrunk = KBLIRecordReduction.reduce(code: cardCode, raw: raw, questionTerms: questionTerms,
                                                     perSkalaByteBudget: perSkalaBudget)
            usedBytes = othersBytes + shrunk.bytes
            reductions[cardCode] = shrunk
        }

        // Session anchors — reserved ≤16 KiB slice, newest-first, dropped ENTIRELY (whole record)
        // once neither the slice nor the remaining package budget can hold their mandatory floor.
        // Anchors carry NO per_skala rows by construction: their job is referent identity, not a
        // full detail dump — a re-cited code re-enters as an explicit reference and gets the full
        // treatment (design §3.4).
        var anchorsIncluded: [String] = []
        var anchorBudget = min(anchorReservedBytes, max(0, packageBudgetBytes - usedBytes))
        for code in anchorCodes {
            if included.contains(code) { continue }
            guard let raw = schema.raw(code) else { continue }
            do { try KBLISchemaSnapshot.validate(code: code, raw: raw) } catch { continue }
            let r = KBLIRecordReduction.reduce(code: code, raw: raw, questionTerms: questionTerms, perSkalaByteBudget: 0)
            guard r.mandatoryBytes <= anchorBudget, usedBytes + r.mandatoryBytes <= packageBudgetBytes else { continue }
            reductions[code] = r
            anchorBudget -= r.mandatoryBytes
            usedBytes += r.mandatoryBytes
            included.insert(code)
            anchorsIncluded.append(code)
        }
        let budgetDroppedAnchors = anchorCodes.filter { included.contains($0) == false }
        let anchorsDropped = structurallyDroppedAnchors + budgetDroppedAnchors

        // Search-term matches — lowest priority, fill whatever remains of the package budget.
        var hitsIncluded: [String] = []
        for code in searchHits.prefix(maxSearchHits) {
            if included.contains(code) { continue }
            guard let raw = schema.raw(code) else { continue }
            do { try KBLISchemaSnapshot.validate(code: code, raw: raw) } catch { continue }
            let remaining = packageBudgetBytes - usedBytes
            guard remaining > 256 else { break }
            let r = KBLIRecordReduction.reduce(code: code, raw: raw, questionTerms: questionTerms,
                                                perSkalaByteBudget: max(0, remaining - 512))
            guard r.bytes <= remaining else { continue }
            reductions[code] = r
            usedBytes += r.bytes
            included.insert(code)
            hitsIncluded.append(code)
        }

        // NOTE: `explicitCodes` and `currentCard` can legitimately name the SAME code (e.g. the
        // question literally contains the card's own 5-digit code, "tell me about 61108") — both
        // already collapse to one entry in `included` via `claim()`, but `finalOrder` is built by
        // concatenation and must be deduped independently here, or the same reduced record would
        // be serialized twice (measured live: a 64-row card duplicated this way nearly doubled
        // the package to ~126 KiB, blowing the 90 KiB hard cap on a scenario that should fit).
        let finalOrder = explicitCodes + (currentCard.map { [$0.kode] } ?? []) + anchorsIncluded + hitsIncluded
        var capsByCode: [String: Int] = [:]
        var conflictCodes: Set<String> = []
        var recordDicts: [[String: Any]] = []
        var emittedCodes = Set<String>()
        for code in finalOrder {
            guard emittedCodes.insert(code).inserted else { continue }
            guard let r = reductions[code] else { continue }
            recordDicts.append(r.dict)
            fieldMap?.record(code: code, included: r.rowsIncluded, total: r.rowsTotal,
                             served: r.rowsServed)
            if r.isConflict { conflictCodes.insert(code) }
            else if let cap = r.capIfKnown { capsByCode[code] = cap }
        }

        let (historyText, _) = serializeHistory(retained)
        let preamble = buildPreamble(conflictCodes: conflictCodes.sorted(), anchorsDropped: anchorsDropped)

        func assemble(_ records: [[String: Any]]) -> String {
            let packageJSON = ["records": records] as [String: Any]
            let packageText = (try? kbliJSONString(packageJSON)) ?? "{\"records\":[]}"
            var prompt = preamble
            prompt += "\n\nKBLI_RECORDS (JSON — the ONLY facts you may cite):\n" + packageText
            if historyText.isEmpty == false { prompt += "\n\nCONVERSATION HISTORY:\n" + historyText }
            prompt += "\n\nUSER QUESTION:\n" + question
            return prompt
        }

        var prompt = assemble(recordDicts)

        // Emergency valve (declared residual, design §3 size-discipline / R2-4): a pathological
        // combo of several never-drop records each carrying an outsized `ruang_lingkup` array can
        // still push the TOTAL past the 90 KiB hard cap even though each individual record is
        // well under its own worst-case bound. Measured this session: the 8 largest
        // `ruang_lingkup`-bearing records sum to ~71 KiB on mandatory fields ALONE. Last resort
        // only, and only on the LOWEST-priority still-included records first (search hits, then
        // anchors) — never on explicit question codes or the current card.
        if prompt.utf8.count > totalHardCapBytes {
            var mutable = recordDicts
            let degradeOrder: [String] = Array(hitsIncluded.reversed()) + Array(anchorsIncluded.reversed())
            for code in degradeOrder {
                guard let idx = mutable.firstIndex(where: { ($0["kode_kbli_2025"] as? String) == code }) else { continue }
                mutable[idx]["ruang_lingkup"] = []
                prompt = assemble(mutable)
                if prompt.utf8.count <= totalHardCapBytes { break }
            }
            recordDicts = mutable
        }

        return .built(prompt: prompt, includedCodes: included, capsByCode: capsByCode,
                      conflictCodes: conflictCodes, totalBytes: prompt.utf8.count)
    }

    // MARK: extraction helpers

    private static let codeRegex = try! NSRegularExpression(pattern: "\\b\\d{5}\\b")

    static func extractCodes(from text: String, knownIn schema: KBLIRawSchemaIndex) -> [String] {
        let ns = text as NSString
        var seen = Set<String>()
        var out: [String] = []
        for m in codeRegex.matches(in: text, range: NSRange(location: 0, length: ns.length)) {
            let code = ns.substring(with: m.range)
            if schema.raw(code) != nil, seen.insert(code).inserted { out.append(code) }
        }
        return out
    }

    /// The mirror of `extractCodes`: the 5-digit tokens the QUESTION names which the catalogue
    /// does NOT contain. `extractCodes` drops these silently (they have no record to package), so
    /// before this the gate could not tell "a code the user asked about that does not exist" from
    /// "a code the model invented" — and correctly answering the first was impossible (P2b §4a α,
    /// Q05: "68200 is not in the KBLI 2025 catalogue" was killed as `unknownCode(68200)` 3/3 runs).
    ///
    /// Derived from the QUESTION only. A code the model invents in its answer is never in this
    /// set, so the α carve-out can never launder a hallucinated citation.
    static func absentQuestionCodes(from text: String, knownIn schema: KBLIRawSchemaIndex) -> Set<String> {
        let ns = text as NSString
        var out = Set<String>()
        for m in codeRegex.matches(in: text, range: NSRange(location: 0, length: ns.length)) {
            let code = ns.substring(with: m.range)
            if schema.raw(code) == nil { out.insert(code) }
        }
        return out
    }

    /// ALL distinct codes cited across `turns`, newest-first — deliberately NOT capped at
    /// `maxAnchors` here (only bounded generously so a pathological transcript can't scan
    /// forever). The caller slices `.prefix(maxAnchors)` for anchor CANDIDATES and treats
    /// everything past that as structurally excluded by the cap itself — both that structural
    /// exclusion and any further budget-driven drop among the top 4 need declaring in the
    /// preamble (design §3.4: "older anchors drop with a declared preamble note"), so this
    /// function must not silently discard the evidence of which codes existed beyond the cap.
    static func extractAnchors(from turns: [KBLIChatTurn], knownIn schema: KBLIRawSchemaIndex, scanCap: Int = 64) -> [String] {
        var seen = Set<String>()
        var out: [String] = []
        for turn in turns.reversed() {
            for code in extractCodes(from: turn.text, knownIn: schema) where seen.contains(code) == false {
                seen.insert(code)
                out.append(code)
                if out.count == scanCap { return out }
            }
        }
        return out
    }

    static func tokenize(_ s: String) -> [String] {
        s.lowercased().components(separatedBy: CharacterSet.alphanumerics.inverted).filter { $0.count >= 3 }
    }

    /// Retrieval: "the chat retriever IS the search index, not a new engine" (design §3.3) — every
    /// call below is `KBLIStore.search`, unmodified, with ITS OWN normalization and ranking. A raw
    /// natural-language question is first tried whole (covers a short direct query typed into
    /// chat, e.g. "villa" or "55203", exactly like the search UI), then EACH meaningful token is
    /// searched individually and results are aggregated — the search UI's own matcher does
    /// whole-string prefix/substring matching, so a full sentence alone rarely matches anything
    /// (measured: "What is the foreign ownership cap for umrah travel packages?" matches zero
    /// records as one string, but the "umrah" token alone finds 79122 via the existing
    /// judul-substring tier). A short EN/ID stopword list keeps generic connective words from
    /// diluting the ranking; it never EXCLUDES a code, only de-prioritizes ties.
    private static let searchStopwords: Set<String> = [
        "the", "for", "and", "are", "was", "were", "this", "that", "with", "from", "what", "how",
        "can", "does", "about", "tell", "have", "has", "any", "not",
        "yang", "dan", "atau", "untuk", "adalah", "ini", "itu", "apa", "bagaimana", "bisa", "saya",
        "dari", "pada", "dengan", "juga", "akan", "harus",
    ]

    /// How much a hit is worth by WHERE the term matched. A title match names the activity the
    /// user is asking about; a prose match is frequently incidental vocabulary in a long `uraian`.
    /// Flat scoring treats them as equal, which is what let a generic adverb outrank a literal
    /// title hit (see `searchHitsFor`).
    private static func fieldWeight(_ field: KBLIStore.MatchField) -> Double {
        switch field {
        case .code: return 8
        case .codePrefix: return 4
        case .titlePrefix: return 3
        case .title: return 2
        case .prose: return 0.5
        case .fuzzy: return 0.25
        }
    }

    /// Inverse-frequency damping. `1/log2(2+total)` rather than `1/total`: a term matching one
    /// record is more specific than one matching a thousand, but not a thousand times more —
    /// straight reciprocal rarity hands maximum weight to a term that matched once BY ACCIDENT,
    /// which is precisely the Q11 failure below.
    private static func rarityWeight(totalMatches: Int) -> Double { 1.0 / log2(2.0 + Double(totalMatches)) }

    static func searchHitsFor(question: String, store: KBLIStore) -> [String] {
        var scoreByCode: [String: Double] = [:]
        var firstSeenOrder: [String] = []
        func record(_ code: String, weight: Double) {
            if scoreByCode[code] == nil { firstSeenOrder.append(code) }
            scoreByCode[code, default: 0] += weight
        }
        // Scoring = WHERE the term matched × HOW RARE the term is. Two measured bugs in the
        // original (P2b §4b, "kafe di Ubud" never retrieved 56303 whose judul literally contains
        // "kafe" — it landed at rank 9, four past the maxSearchHits cliff):
        //
        //   1. The rarity weight was `1/hits.count` where `hits` had ALREADY been capped at
        //      `.prefix(8)` — so every term matching 8 or more records got the same weight, 0.125,
        //      whether it matched 8 records or 1,450. `store.search()` returns the true `.total`
        //      and it was being discarded. The old comment described the intent, not the code.
        //   2. Rarity alone is not specificity. With the cap fixed, "tepat" ("on time", a generic
        //      adverb in "KBLI mana yang tepat") still won outright: it matched exactly ONE
        //      record's uraian prose, so reciprocal rarity handed it the maximum score, while
        //      "kafe" matching 56303's TITLE scored a quarter of that. Field weighting is what
        //      separates a term that names the activity from a term that merely occurs near it.
        let whole = store.search(question)
        if whole.rows.isEmpty == false {
            let rarity = rarityWeight(totalMatches: whole.total)
            let q = question.lowercased()
            for row in whole.rows.prefix(10) {
                guard let field = KBLIStore.matchField(row, q) else { continue }
                record(row.kode, weight: fieldWeight(field) * rarity)
            }
        }
        for term in tokenize(question) where searchStopwords.contains(term) == false {
            let hits = store.search(term)
            guard hits.rows.isEmpty == false else { continue }
            let rarity = rarityWeight(totalMatches: hits.total)
            for row in hits.rows.prefix(8) {
                guard let field = KBLIStore.matchField(row, term) else { continue }
                record(row.kode, weight: fieldWeight(field) * rarity)
            }
        }
        let ranked = firstSeenOrder.sorted { (scoreByCode[$0] ?? 0) > (scoreByCode[$1] ?? 0) }

        // INTENT GUARANTEE (P2b Q11). Ranking alone cannot fix the miss it was meant to fix.
        // Measured 2026-09-13 on dataset 3dafab17…, question Q11 ("Klien mau buka kafe di
        // Ubud…"): "kafe" matches exactly 4 records — 10761, 56101, 56290, 56303 — and the
        // ranked list put 56303 first but 56101 nowhere in the top 10, so the package answered
        // with the blocked code and never mentioned the one a client may actually register. On
        // n=8 structured questions a single wrongful abstention is 12.5%, i.e. floor (iii) red:
        // "Q11 answered" and "the gate green" cannot coexist.
        //
        // The rule, stated as a class and not as a patch for one question: when a term NAMES an
        // activity or a code — it matches a title or a code, not incidental prose — and ALL of
        // its hits fit inside the slot budget, the question is asking for that whole set, so the
        // whole set is guaranteed a place ahead of score order. "kafe" appears in 4 of 1,559
        // records: whoever types it wants all four.
        //
        // Bounded by construction, in three ways, because an unbounded guarantee is just a
        // wider cap: (a) the threshold IS `maxSearchHits`, not a hand-picked constant — a term
        // can never guarantee more codes than there are slots; (b) only ONE term guarantees, the
        // strongest, so the blast radius is at most `maxSearchHits` codes; (c) a prose-only term
        // never qualifies, which is what keeps the guarantee from firing on questions that have
        // no activity noun. Measured innocence of (c): on Q13 and Q23 every fully-fitting term
        // ("boleh", "batasan", "sejak", "mei", "kbli") matches prose only, so neither question's
        // package changes at all — including Q23, whose current pass must not be disturbed.
        let guaranteed = intentGuaranteedCodes(question: question, store: store)
        guard guaranteed.isEmpty == false else { return ranked }
        let promoted = ranked.filter { guaranteed.contains($0) }
        let missing = guaranteed.subtracting(promoted).sorted()
        let rest = ranked.filter { guaranteed.contains($0) == false }
        return promoted + missing + rest
    }

    /// Field classes that mean "this term NAMES the thing" rather than "this term occurs near
    /// it". `.prose` and `.fuzzy` are deliberately excluded — see the guarantee comment.
    private static func namesTheActivity(_ field: KBLIStore.MatchField) -> Bool {
        switch field {
        case .code, .codePrefix, .titlePrefix, .title: return true
        case .prose, .fuzzy: return false
        }
    }

    /// The hits of the single strongest naming term whose matches all fit the slot budget.
    /// Deterministic: highest field weight wins, then the rarer term, then the longer term, then
    /// lexicographic — no tie is left to dictionary order.
    static func intentGuaranteedCodes(question: String, store: KBLIStore) -> Set<String> {
        var best: (weight: Double, total: Int, term: String, codes: [String])? = nil
        for term in tokenize(question) where searchStopwords.contains(term) == false {
            let hits = store.search(term)
            guard hits.total > 0, hits.total <= maxSearchHits else { continue }
            let rows = hits.rows.prefix(maxSearchHits)
            var weight = 0.0
            for row in rows {
                guard let field = KBLIStore.matchField(row, term), namesTheActivity(field) else { continue }
                weight = max(weight, fieldWeight(field))
            }
            guard weight > 0 else { continue }
            let codes = rows.map { $0.kode }
            let candidate = (weight: weight, total: hits.total, term: term, codes: codes)
            if let b = best {
                let better = (candidate.weight, -candidate.total, candidate.term.count, b.term)
                    > (b.weight, -b.total, b.term.count, candidate.term)
                if better { best = candidate }
            } else {
                best = candidate
            }
        }
        return Set(best?.codes ?? [])
    }

    /// Clip an assistant turn to the storage-time budget (design §3.4: "each stored assistant
    /// turn is clipped to 4 KiB at storage time"). Exposed so ChatView can apply the SAME clip
    /// when appending to `AppState.messages`, and applied again here defensively so this file's
    /// own history budget guarantee never depends on the caller having done it.
    static func clipAssistantTurn(_ text: String) -> String {
        kbliClipToBytes(text, maxBytes: assistantTurnStorageClipBytes, marker: "…[truncated]")
    }

    private static func serializeHistory(_ turns: [KBLIChatTurn]) -> (String, Int) {
        guard turns.isEmpty == false else { return ("", 0) }
        var lines: [(text: String, bytes: Int)] = []
        for t in turns {
            let role = t.role.lowercased() == "user" ? "USER" : "ASSISTANT"
            let text = role == "ASSISTANT" ? clipAssistantTurn(t.text) : t.text
            let line = "\(role): \(text)"
            lines.append((line, line.utf8.count))
        }
        var total = lines.reduce(0) { $0 + $1.bytes + 1 }
        var start = 0
        while total > historyBudgetBytes, start < lines.count {
            total -= lines[start].bytes + 1
            start += 1
        }
        let kept = lines[start...]
        let text = kept.map { $0.text }.joined(separator: "\n")
        return (text, text.utf8.count)
    }

    private static func buildPreamble(conflictCodes: [String], anchorsDropped: [String]) -> String {
        var p = """
        You are the KBLI Navigator assistant (Bali Zero). Answer ONLY from the KBLI_RECORDS JSON \
        provided in this prompt. If a fact is not present there, say plainly that the navigator \
        does not carry that fact — never invent a risk, licensing, or ownership detail, and never \
        answer from general knowledge about Indonesian regulation. Regulatory facts come only from \
        the structured fields, never from free prose. Answer in the same language as the user's \
        question (English or Indonesian). Always cite the KBLI code(s) your answer is grounded on. \
        Express any foreign-ownership figure as digits followed by "%" (e.g. "49%"), and make at \
        most ONE such ownership-cap statement per sentence — never combine two codes' caps in the \
        same sentence (write two sentences instead). `bali_moratorium_status` concerns ONLY the \
        Bali moratorium / risk-scale axis; foreign ownership comes ONLY from the pma_* fields on \
        each record — "not blocked" by the moratorium does NOT mean open to foreign capital. \
        Each record carries `pma_bali_verdict`, the product's OWN adjudication of that record and \
        the same one its code page shows: `headline` is one of NATIONALLY_CLOSED, BALI_BLOCKED, \
        NATIONAL_UNDETERMINED, BALI_UNDETERMINED, OPEN_IN_BALI, with `reason`. State the Bali \
        position from `pma_bali_verdict`, never by reasoning over the raw flags yourself. \
        BALI_UNDETERMINED and NATIONAL_UNDETERMINED mean the records do not determine the answer: \
        say so and say what is missing — do NOT report such a code as open, and do NOT report it \
        as closed. When `national_cap_percent` or `risk_category` is null the navigator carries no \
        such value: say so, never substitute a typical or default one.
        """
        if conflictCodes.isEmpty == false {
            p += "\n\nThe following code(s) carry a declared internal data conflict on the " +
                 "foreign-ownership axis and are marked `pma_conflict: true` instead of a cap: " +
                 conflictCodes.joined(separator: ", ") + ". Do NOT state or imply an ownership " +
                 "percentage for these codes — say the figure is under internal review and point " +
                 "the user to the code page and the Bali Zero team."
        }
        if anchorsDropped.isEmpty == false {
            p += "\n\nEarlier-referenced code(s) " + anchorsDropped.joined(separator: ", ") +
                 " were dropped from this prompt to stay within budget. If the user asks about " +
                 "one of them, ask them to re-state the code."
        }
        return p
    }
}

private func kbliJSONString(_ obj: [String: Any]) throws -> String {
    let data = try JSONSerialization.data(withJSONObject: obj, options: [.sortedKeys])
    return String(data: data, encoding: .utf8) ?? "{}"
}
