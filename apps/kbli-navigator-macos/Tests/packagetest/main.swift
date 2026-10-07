import Foundation

func ck(_ c: Bool, _ m: String) { if c { print("  ✅ \(m)") } else { print("  ❌ FAIL: \(m)"); exit(1) } }

guard let jsonPath = ProcessInfo.processInfo.environment["KBLI_JSON"] else {
    print("  ❌ FAIL: set KBLI_JSON to the bundled dataset path"); exit(1)
}
guard let store = KBLIStore(jsonPath: jsonPath) else { print("  ❌ FAIL: KBLIStore failed to load"); exit(1) }
guard let schema = KBLIRawSchemaIndex(jsonPath: jsonPath) else { print("  ❌ FAIL: KBLIRawSchemaIndex failed to load"); exit(1) }
ck(store.all.count == 1559, "store loaded 1559 records (got \(store.all.count))")
ck(schema.allCodes.count == 1559, "raw schema index loaded 1559 records (got \(schema.allCodes.count))")

func card(_ code: String) -> KBLI { store.code(code)! }

// ─────────────────────────────────────────────────────────────────────────────────────────
print("Zero-LLM builder assertion (P2a, design §3 'zero LLM calls'):")
let selfSource = (try? String(contentsOfFile: "Sources/KBLIContextPackage.swift", encoding: .utf8)) ?? ""
ck(selfSource.isEmpty == false, "read KBLIContextPackage.swift source (run tests from repo root)")
for forbidden in ["Process(", "URLSession", "NSTask", "posix_spawn", "Pipe("] {
    ck(selfSource.contains(forbidden) == false, "builder source never references '\(forbidden)'")
}

// ─────────────────────────────────────────────────────────────────────────────────────────
print("Schema-snapshot fail-closed check over ALL 1,559 bundled records:")
var schemaFailures = 0
for code in schema.allCodes {
    guard let raw = schema.raw(code) else { continue }
    do { try KBLISchemaSnapshot.validate(code: code, raw: raw) }
    catch { schemaFailures += 1; print("    unexpected schema drift on \(code): \(error)") }
}
ck(schemaFailures == 0, "0/1559 records have an unknown key outside the measured snapshot")

// ─────────────────────────────────────────────────────────────────────────────────────────
print("Determinism:")
let outcomeA = KBLIContextPackageBuilder.build(question: "What is the moratorium status of 55203?",
    currentCard: card("55203"), history: [], store: store, schema: schema)
let outcomeB = KBLIContextPackageBuilder.build(question: "What is the moratorium status of 55203?",
    currentCard: card("55203"), history: [], store: store, schema: schema)
ck(outcomeA == outcomeB, "same inputs -> byte-identical outcome")

// ─────────────────────────────────────────────────────────────────────────────────────────
print("Cross-field consistency gate (R4-1) — mutant conflict record, live 50111/50112/50121:")
func promptText(_ o: KBLIPackageOutcome) -> String {
    if case .built(let p, _, _, _, _) = o { return p }
    return ""
}
// 2026-09-17 re-anchor to canonical b30b1759…: 50111/50112 no longer trigger this gate. Receipt
// — nuzantara commit 1e0ad9d0bb34189fc99275e9cac145353fe52d97 (our own source_commit pin, "fix
// (kbli): 50111/50112 condition no longer contradicts their own 49% foreign cap (W-H PR-3e)
// (#6661)"): pma_kondisi rewritten from "Hanya PMDN (100% domestik)" to "Modal asing maksimal
// 49%" for both codes, so `isDomesticOnlyConflict` correctly reads false on the live data now —
// re-measured this session, zero records in the whole 1,559-record dataset carry the domestic-
// only pattern together with a nonzero cap. The GATE ITSELF is still tested directly against
// `KBLIRecordReduction.reduce`, on a synthetic record shaped exactly like the pre-cure 50111 —
// unit-level, so the mechanism stays covered even though its live exemplar was cured out from
// under it.
let mutantConflictRaw: [String: Any] = [
    "kode_kbli_2025": "T0010", "judul": "synthetic pre-cure 50111 shape",
    "pma_status": "TERBATAS", "pma_max_asing": 49, "pma_kondisi": "Hanya PMDN (100% domestik)",
]
let mutantConflict = KBLIRecordReduction.reduce(code: "T0010", raw: mutantConflictRaw, questionTerms: [], perSkalaByteBudget: 4096)
ck(mutantConflict.isConflict, "a domestic-only kondisi + nonzero cap is marked isConflict (mutant, R4-1)")
ck(mutantConflict.capIfKnown == nil, "a conflict record exposes no usable cap (mutant, R4-1)")
ck((mutantConflict.dict["pma_conflict"] as? Bool) == true, "the reduced dict carries pma_conflict:true (mutant, R4-1)")
ck(mutantConflict.dict["pma_max_asing"] == nil, "a conflict record's pma_max_asing is NOT serialized (mutant, R4-1)")
// INNOCENCE: the SAME cap with a partnership condition (not domestic-only) is not a conflict —
// same shape as live 50121.
let mutantPartnershipRaw: [String: Any] = [
    "kode_kbli_2025": "T0011", "judul": "synthetic partnership shape",
    "pma_status": "TERBATAS", "pma_max_asing": 49, "pma_kondisi": "Kemitraan dengan PMDN",
]
let mutantPartnership = KBLIRecordReduction.reduce(code: "T0011", raw: mutantPartnershipRaw, questionTerms: [], perSkalaByteBudget: 4096)
ck(mutantPartnership.isConflict == false, "INNOCENCE: a partnership condition (not domestic-only) is NOT marked conflict (mutant)")
ck(mutantPartnership.capIfKnown == 49, "INNOCENCE: the partnership record keeps its real cap (mutant)")

// Live re-verification that 50111/50112/50121 all now build ordinary, cap-bearing packages.
let o50111 = KBLIContextPackageBuilder.build(question: "foreign ownership for 50111", currentCard: card("50111"), history: [], store: store, schema: schema)
if case .built(_, _, let caps, let conflicts, _) = o50111 {
    ck(conflicts.contains("50111") == false, "50111 is no longer marked pma_conflict (cured upstream, receipt above)")
    ck(caps["50111"] == 49, "50111 carries its real 49% cap in capsByCode (got \(String(describing: caps["50111"])))")
} else { ck(false, "50111 build produced .built") }
let text50111 = promptText(o50111)
ck(text50111.contains("\"pma_conflict\":true") == false, "package JSON no longer carries pma_conflict:true for 50111")
ck(text50111.contains("\"pma_max_asing\":49"), "50111's pma_max_asing IS serialized now that it is not a conflict")

let o50112 = KBLIContextPackageBuilder.build(question: "foreign ownership for 50112", currentCard: card("50112"), history: [], store: store, schema: schema)
if case .built(_, _, let caps112, let conflicts, _) = o50112 {
    ck(conflicts.contains("50112") == false, "50112 is no longer marked pma_conflict (cured upstream, receipt above)")
    ck(caps112["50112"] == 49, "50112 carries its real 49% cap in capsByCode")
}

let o50121 = KBLIContextPackageBuilder.build(question: "foreign ownership for 50121", currentCard: card("50121"), history: [], store: store, schema: schema)
if case .built(_, _, let caps, let conflicts, _) = o50121 {
    ck(conflicts.contains("50121") == false, "50121 (Kemitraan dengan PMDN — a partnership, not domestic-only) is NOT marked conflict")
    ck(caps["50121"] == 49, "50121 keeps its real cap (49) in capsByCode")
} else { ck(false, "50121 build produced .built") }

// ─────────────────────────────────────────────────────────────────────────────────────────
print("Semantic-collision cure (R2-2) — l4_bali renamed to bali_moratorium_status:")
let o79122 = KBLIContextPackageBuilder.build(question: "Can a foreign company open 79122 in Bali?", currentCard: card("79122"), history: [], store: store, schema: schema)
let text79122 = promptText(o79122)
ck(text79122.contains("bali_moratorium_status"), "package renames l4_bali -> bali_moratorium_status")
ck(text79122.contains("\"l4_bali\"") == false, "raw l4_bali key is never re-serialized under its original name")
if case .built(_, _, let caps79122, _, _) = o79122 { ck(caps79122["79122"] == 0, "79122's real cap is 0% (the dataset's own zantaraOpener claims 'Open' — excluded by construction)") }

// ─────────────────────────────────────────────────────────────────────────────────────────
print("Explicit-code cap (R6-1) — >3 codes narrows, ≤3 builds:")
let fourCodes = "Compare 01111 01112 01113 01114"
let oFour = KBLIContextPackageBuilder.build(question: fourCodes, currentCard: nil, history: [], store: store, schema: schema)
if case .narrowComparison(let codes) = oFour { ck(codes.count == 4, "4-code question -> narrowComparison with all 4 named") }
else { ck(false, "4-code question did not narrow") }

let threeCodes = "Compare 01111 01112 01113"
let oThree = KBLIContextPackageBuilder.build(question: threeCodes, currentCard: nil, history: [], store: store, schema: schema)
if case .built(_, let included, _, _, _) = oThree {
    ck(["01111", "01112", "01113"].allSatisfy { included.contains($0) }, "3-code question includes all 3 explicit codes")
} else { ck(false, "3-code question should build") }

// ─────────────────────────────────────────────────────────────────────────────────────────
print("Question-too-long gate:")
let longQ = String(repeating: "a", count: 5000)
let oLong = KBLIContextPackageBuilder.build(question: longQ, currentCard: nil, history: [], store: store, schema: schema)
if case .questionTooLong(let n) = oLong { ck(n == 5000, "5000-byte question -> questionTooLong(5000)") }
else { ck(false, "long question did not trip questionTooLong") }

// ─────────────────────────────────────────────────────────────────────────────────────────
print("Size discipline — worst single record (61108, 64 per_skala rows) stays under the 90 KiB hard cap:")
let oWorst = KBLIContextPackageBuilder.build(question: "tell me about 61108", currentCard: card("61108"), history: [], store: store, schema: schema)
if case .built(_, _, _, _, let bytes) = oWorst {
    ck(bytes <= KBLIContextPackageBuilder.totalHardCapBytes, "61108-as-card total \(bytes) bytes <= 90 KiB hard cap")
    print("    measured: \(bytes) bytes (\(String(format: "%.1f", Double(bytes) / 1024))) KiB")
} else { ck(false, "61108 card build produced .built") }

// ─────────────────────────────────────────────────────────────────────────────────────────
print("Combinatorial worst case — card + 4 anchors + 3 explicit codes fits (design §3 R6-1/R4-2 exact scenario):")
let anchorHistory: [KBLIChatTurn] = [
    KBLIChatTurn(role: "user", text: "What about 26391?"),
    KBLIChatTurn(role: "assistant", text: "26391 details..."),
    KBLIChatTurn(role: "user", text: "And 26399?"),
    KBLIChatTurn(role: "assistant", text: "26399 details..."),
    KBLIChatTurn(role: "user", text: "What about 26410?"),
    KBLIChatTurn(role: "assistant", text: "26410 details..."),
    KBLIChatTurn(role: "user", text: "And 26420?"),
    KBLIChatTurn(role: "assistant", text: "26420 details..."),
]
let combo = KBLIContextPackageBuilder.build(
    question: "Compare 01111 01112 01113 against my card",
    currentCard: card("61108"), history: anchorHistory, store: store, schema: schema)
if case .built(_, let included, _, _, let bytes) = combo {
    ck(bytes <= KBLIContextPackageBuilder.totalHardCapBytes, "worst combo total \(bytes) bytes <= 90 KiB hard cap")
    ck(included.contains("01111") && included.contains("01112") && included.contains("01113"), "all 3 explicit codes survive (never dropped)")
    ck(included.contains("61108"), "the card survives (never dropped)")
    print("    measured: \(bytes) bytes, included=\(included.sorted())")
} else { ck(false, "worst-combo build produced .built (got \(combo))") }

// ─────────────────────────────────────────────────────────────────────────────────────────
print("Session-anchor saturation — 12 history codes, only the 4 newest survive:")
let twelveCodes = ["47762", "47763", "47764", "47765", "47771", "47772", "47773", "47774", "47779", "47781", "66221", "66222"]
let satHistory: [KBLIChatTurn] = twelveCodes.flatMap { c in
    [KBLIChatTurn(role: "user", text: "tell me about \(c)"), KBLIChatTurn(role: "assistant", text: "\(c) is ...")]
}
let sat = KBLIContextPackageBuilder.build(question: "generic question with no codes",
    currentCard: nil, history: satHistory, store: store, schema: schema)
if case .built(let prompt, let included, _, _, _) = sat {
    let survivingAnchors = twelveCodes.filter { included.contains($0) }
    ck(survivingAnchors.count <= 4, "at most 4 of the 12 history codes survive as anchors (got \(survivingAnchors.count): \(survivingAnchors))")
    let newest4 = Array(twelveCodes.suffix(4))
    ck(newest4.allSatisfy { included.contains($0) }, "the 4 NEWEST codes (\(newest4)) are exactly the ones that survive")
    ck(prompt.contains("were dropped from this prompt"), "the preamble declares the dropped older anchors")
} else { ck(false, "saturation build produced .built") }

// ─────────────────────────────────────────────────────────────────────────────────────────
print("Retrieval recall — the chat retriever IS the search index:")
let oUmrah = KBLIContextPackageBuilder.build(question: "What is the foreign ownership cap for umrah travel packages?",
    currentCard: nil, history: [], store: store, schema: schema)
if case .built(_, let included, _, _, _) = oUmrah {
    ck(included.contains("79122"), "'umrah' question retrieves 79122 through the package builder's search pipeline")
} else { ck(false, "umrah retrieval build produced .built") }

// ─────────────────────────────────────────────────────────────────────────────────────────
print("Per_skala byte-budgeted row selection is question-matched-first (46710, R3-2 case):")
let o46710 = KBLIContextPackageBuilder.build(question: "bahan bakar gas cair",
    currentCard: card("46710"), history: [], store: store, schema: schema)
if case .built(let prompt, _, _, _, _) = o46710 {
    ck(prompt.contains("46710"), "46710 card present")
    ck(prompt.lowercased().contains("gas cair"), "question-matched per_skala content ('gas cair') is present in the package")
} else { ck(false, "46710 card build produced .built") }

// ─────────────────────────────────────────────────────────────────────────────────────────
// P2b CURE B (benchmark §4b) — retrieval scoring: WHERE a term matched × HOW RARE it is.
print("Retrieval scoring — a literal title hit must outrank incidental prose vocabulary:")
let kafeQ = "Klien mau buka kafe di Ubud. KBLI mana yang tepat dan izin apa saja yang wajib?"
let kafeHits = KBLIContextPackageBuilder.searchHitsFor(question: kafeQ, store: store)
let kafeTop = Array(kafeHits.prefix(KBLIContextPackageBuilder.maxSearchHits))
ck(kafeTop.contains("56303"),
   "'kafe di Ubud' retrieves 56303 (judul 'Aktivitas Rumah Minum/Kafe') inside maxSearchHits — got \(kafeTop)")
ck(kafeHits.first == "56303",
   "56303 ranks FIRST: a title match beats 'tepat'/'kbli' matching unrelated uraian prose — got \(kafeHits.first ?? "nil")")

print("Retrieval scoring — the rarity weight reads the TRUE match total, not the capped page:")
// "dan" matches 1450 records, "izin" 8. Under the old `1/hits.count` (hits already .prefix(8))
// both scored 0.125 per hit; a term matching 1450 records must now be damped well below one
// matching 8.
let broad = store.search("dan").total, narrow = store.search("izin").total
ck(broad > 1000 && narrow < 20, "fixture holds: 'dan' matches \(broad) records, 'izin' \(narrow)")

// Questions quoted VERBATIM from the frozen P2b corpus (sha 487bc950…) — these four graded
// correct on 2026-08-20 and must not regress. Do not paraphrase them: a fixture that only
// resembles the corpus proves nothing about the corpus.
print("Retrieval regression — previously-correct P2b questions keep their key record:")
for (q, needed) in [
    ("Sejak 13 Mei 2026, KBLI apa yang terkena moratorium PMA Bali dan apakah larangannya hanya sementara?", "64330"),
    ("Untuk KBLI 51101 angkutan udara berjadwal, berapa batas kepemilikan asing dan syarat khusus pemegang saham nasional?", "51101"),
    ("Apakah PT PMA asing boleh menjalankan KBLI 79122 biro perjalanan Umrah dan Haji khusus? Berapa persen saham asing?", "79122"),
    ("Can a foreign-owned PT PMA fully own KBLI 79122 (Umrah and special Hajj travel bureau)? What foreign ownership percentage applies?", "79122"),
] {
    let top = Array(KBLIContextPackageBuilder.searchHitsFor(question: q, store: store)
        .prefix(KBLIContextPackageBuilder.maxSearchHits))
    ck(top.contains(needed), "'\(q.prefix(38))…' still retrieves \(needed) — got \(top)")
}

// ─────────────────────────────────────────────────────────────────────────────────────────
// Council round 4 (codex-gpt-5.6-sol), the finding the P2b pack carried CONFIRMED and unfixed:
// `package_codes` records code identity only. The scorer therefore judged every served code
// against the canonical `per_skala` rows, including a code the builder served with ZERO rows —
// so a requirement invented from a row the model never saw could read as supported. The builder
// now DECLARES what it served, from its own reduction; the scorer consumes that and never
// re-derives the byte budget in Python.
print("The builder declares what it served (per_skala extent, council round 4):")
let fmPlain = KBLIContextPackageBuilder.FieldMap()
let oPlain = KBLIContextPackageBuilder.build(question: "01140", currentCard: nil, history: [],
                                             store: store, schema: schema, fieldMap: fmPlain)
if case .built(_, let includedPlain, _, _, _) = oPlain {
    ck(Set(fmPlain.perSkalaRowsByCode.keys) == includedPlain,
       "the field map covers exactly the included codes (got \(fmPlain.perSkalaRowsByCode.count) of \(includedPlain.count))")
    let served = fmPlain.perSkalaRowsByCode["01140"] ?? -1
    let total = fmPlain.perSkalaRowsTotalByCode["01140"] ?? -1
    ck(total == (schema.raw("01140")?["per_skala"] as? [[String: Any]] ?? []).count,
       "01140 declares its FULL row count as the denominator (got \(total))")
    ck(served >= 0 && served <= total, "01140 declares a served count within its total (got \(served)/\(total))")
    // GUILT: the number has to come from the reduction, not from a constant. The rows the
    // package actually serialized for 01140 are the ones the map claims.
    let prompt = promptText(oPlain)
    if let recordsStart = prompt.range(of: "KBLI_RECORDS (JSON"),
       let jsonStart = prompt.range(of: "{", range: recordsStart.upperBound..<prompt.endIndex) {
        let jsonText = String(prompt[jsonStart.lowerBound...])
        let rowsInPrompt = jsonText.components(separatedBy: "\"skala_usaha\"").count - 1
        ck(rowsInPrompt == fmPlain.perSkalaRowsByCode.values.reduce(0, +),
           "the map counts the rows the prompt really carries (map \(fmPlain.perSkalaRowsByCode.values.reduce(0, +)), prompt \(rowsInPrompt))")
    } else {
        ck(false, "the built prompt carries a KBLI_RECORDS block")
    }
} else {
    ck(false, "the 01140 package builds")
}
// INNOCENCE: the parameter is optional and additive — a caller that passes nothing gets the
// identical outcome, so no production call site changed behaviour to make the benchmark honest.
let oNoMap = KBLIContextPackageBuilder.build(question: "01140", currentCard: nil, history: [],
                                             store: store, schema: schema)
ck(oNoMap == oPlain, "INNOCENCE: omitting the field map changes nothing about the package")

// ─────────────────────────────────────────────────────────────────────────────────────────
// ROW-IDENTITY CONTRACT (docs/gates/ROW-IDENTITY-CONTRACT.md), council round 5 finding (1):
// the builder serves question-matched rows FIRST, so a COUNT names no set. What the builder now
// declares is the ORDINAL of every row it served, in served order.
print("The builder declares WHICH rows it served, by ordinal (row-identity contract §4):")
ck(Set(fmPlain.perSkalaRowsServedByCode.keys) == Set(fmPlain.perSkalaRowsByCode.keys),
   "every code with a count has an enumeration")
for (code, count) in fmPlain.perSkalaRowsByCode {
    let served = fmPlain.perSkalaRowsServedByCode[code] ?? []
    ck(served.count == count,
       "\(code): the declared count IS the served count (\(count) vs \(served.count))")
    let canonical = (schema.raw(code)?["per_skala"] as? [[String: Any]] ?? [])
    ck(Set(served.map { $0.ordinal }).count == served.count, "\(code): no ordinal is declared twice")
    for s in served {
        ck(s.ordinal >= 0 && s.ordinal < canonical.count,
           "\(code): ordinal \(s.ordinal) is inside the canonical row range (\(canonical.count))")
        ck(kbliSkalaKey(canonical[s.ordinal]) == s.skalaKey,
           "\(code): the declared skala_key names the canonical row at ordinal \(s.ordinal)")
    }
}

// GUILT: the ordinals must be the CANONICAL indices, not the served positions. `besar` names
// 01140's ordinals 3 and 7 (one per OSS scope), so a relevance-first selection declares
// [3, 7, 0, 1, 2, 4, 5, 6]. If the builder ever reverted to physical order, or the ordinals were
// invented from the served index, this reads [0, 1, 2, …] and fails.
let fmRel = KBLIContextPackageBuilder.FieldMap()
let oRel = KBLIContextPackageBuilder.build(question: "01140 besar", currentCard: nil,
                                           history: [], store: store, schema: schema, fieldMap: fmRel)
if case .built = oRel {
    let served = fmRel.perSkalaRowsServedByCode["01140"] ?? []
    let canonical = (schema.raw("01140")?["per_skala"] as? [[String: Any]] ?? [])
    ck(served.count == canonical.count, "01140 serves all \(canonical.count) rows for this question")
    let matchedPositions = served.enumerated().filter { $0.element.skalaKey.contains("besar") }.map { $0.offset }
    ck(matchedPositions == Array(0..<matchedPositions.count),
       "every question-matched row is declared BEFORE every other (matched at \(matchedPositions))")
    ck(Set(served.prefix(matchedPositions.count).map { $0.ordinal }) == Set([3, 7]),
       "the matched rows are canonical ordinals 3 and 7 — got \(served.prefix(matchedPositions.count).map { $0.ordinal })")
    ck(served.map { $0.ordinal } != Array(0..<served.count),
       "the declaration is the CANONICAL order, not the served position (got \(served.map { $0.ordinal }))")
    // INNOCENCE: a relevance ordering is still a permutation — nothing is dropped or duplicated.
    ck(Set(served.map { $0.ordinal }) == Set(0..<canonical.count),
       "every canonical row is declared exactly once")
} else {
    ck(false, "the relevance-ordered 01140 package builds")
}

// The per-list truncation is DECLARED, not left to the marker alone (§4). 01140's last row
// carries more than the item cap in `kewajiban`.
let fmTrunc = KBLIContextPackageBuilder.FieldMap()
let oTrunc = KBLIContextPackageBuilder.build(question: "01140", currentCard: card("01140"),
                                             history: [], store: store, schema: schema,
                                             fieldMap: fmTrunc)
if case .built = oTrunc {
    let canonical = (schema.raw("01140")?["per_skala"] as? [[String: Any]] ?? [])
    var capped = 0, whole = 0
    for s in fmTrunc.perSkalaRowsServedByCode["01140"] ?? [] {
        let kew = (canonical[s.ordinal]["kewajiban"] as? [String] ?? [])
        let expected = min(kew.count, KBLIRecordReduction.perRowListItemCap)
        ck(s.kewajibanServed == expected,
           "ordinal \(s.ordinal): kewajiban_served is \(expected) of \(kew.count)")
        if kew.count > KBLIRecordReduction.perRowListItemCap { capped += 1 } else { whole += 1 }
    }
    // GUILT needs a really-capped row; INNOCENCE needs a really-whole one. Both, or the
    // assertion above proves nothing about the branch it never took.
    ck(capped > 0, "at least one served row of 01140 really is capped (\(capped))")
    ck(whole > 0, "at least one served row of 01140 is served whole (\(whole))")
} else {
    ck(false, "the 01140 card package builds")
}

print("ALL PACKAGE TESTS PASSED")
