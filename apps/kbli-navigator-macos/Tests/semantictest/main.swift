import Foundation

// Tests/semantictest — OPEN-1 (2026-09-17): `KBLIVerdict.ownershipLine` is the ONLY source of
// the foreign-ownership line on every surface (chat context, table row, detail card, dossier,
// registry sheet/ledger). For all 1,559 records this loads the dataset once, computes the
// verdict, and asserts that each surface's OWN pure function — `ownershipLine(_:isID:)` on
// `KBLIRegistryView`/`KBLIDetailRichView`/`KBLIDossierView`/`RegistryVerdictSheet`, and the chat
// context package's serialized `ownership_line` field — returns the EXACT string the projection
// returns. A static source probe follows, checking that no surface outside `KBLIVerdict.swift`
// still reconstructs the line as its own literal.

var failures = 0
func ck(_ c: Bool, _ m: String) {
    if c { print("  ✅ \(m)") } else { print("  ❌ FAIL: \(m)"); failures += 1 }
}
func done() -> Never {
    if failures == 0 { print("ALL SEMANTIC TESTS PASSED"); exit(0) }
    print("\(failures) FAILURE(S)"); exit(1)
}

guard let jsonPath = ProcessInfo.processInfo.environment["KBLI_JSON"],
      let store = KBLIStore(jsonPath: jsonPath),
      let schema = KBLIRawSchemaIndex(jsonPath: jsonPath) else {
    print("set KBLI_JSON to the bundled dataset path"); exit(2)
}

let records = store.all
print("census:")
ck(records.count == 1559, "1,559 records loaded (got \(records.count))")

// ─────────────────────────────────────────────────────────────────────────────────────────
print("\nsurface agreement — every surface's own pure function equals the projection, all records × both languages:")

var surfaceMismatches: [String] = []
for k in records {
    let v = KBLIVerdict.of(record: k)
    for isID in [false, true] {
        let projected = v.ownershipLine(isID: isID)
        let surfaces: [(String, String)] = [
            ("table", KBLIRegistryView.ownershipLine(k, isID: isID)),
            ("card", KBLIDetailRichView.ownershipLine(k, isID: isID)),
            ("dossier", KBLIDossierView.ownershipLine(k, isID: isID)),
            ("sheet", RegistryVerdictSheet.ownershipLine(k, isID: isID)),
        ]
        for (name, line) in surfaces where line != projected {
            surfaceMismatches.append("\(k.kode):\(name):isID=\(isID) got \"\(line)\" want \"\(projected)\"")
        }
    }
}
ck(surfaceMismatches.isEmpty,
   "table/card/dossier/sheet equal the projection on all \(records.count) records × 2 languages (mismatches: \(surfaceMismatches.prefix(5)))")

// The chat context — English only; `packageDictionary()` serializes tags and this line for a
// model to read, never a localized string (`KBLIContextPackage.swift`'s own design).
var chatMismatches: [String] = []
for k in records {
    guard let raw = schema.raw(k.kode) else { chatMismatches.append("\(k.kode):no-raw-record"); continue }
    let result = KBLIRecordReduction.reduce(code: k.kode, raw: raw, questionTerms: [], perSkalaByteBudget: 8192)
    guard let pkg = result.dict["pma_bali_verdict"] as? [String: Any],
          let line = pkg["ownership_line"] as? String else {
        chatMismatches.append("\(k.kode):no-ownership_line-field"); continue
    }
    let projected = KBLIVerdict.of(record: k).ownershipLine(isID: false)
    if line != projected { chatMismatches.append("\(k.kode):chat got \"\(line)\" want \"\(projected)\"") }
}
ck(chatMismatches.isEmpty,
   "chat context's ownership_line equals the projection on all \(records.count) records (mismatches: \(chatMismatches.prefix(5)))")

// ─────────────────────────────────────────────────────────────────────────────────────────
print("\nthe 55 verified TERBATAS records — three disjoint classes (measured on this dataset), each its own line:")

let terbatasVerified = records.filter { $0.pmaStatus == "TERBATAS" && $0.pmaCapVerified == true }
ck(terbatasVerified.count == 55, "55 TERBATAS records with pma_cap_verified (got \(terbatasVerified.count))")

let positive = terbatasVerified.filter { ($0.pmaMaxAsing ?? 0) > 0 && $0.pmaCapSpecial != true }
let special = terbatasVerified.filter { $0.pmaCapSpecial == true }
let zeroCap = terbatasVerified.filter { $0.pmaMaxAsing == 0 && $0.pmaCapSpecial != true }
ck(positive.count == 32, "32 positive-% TERBATAS records (got \(positive.count))")
ck(special.count == 1, "1 special-condition TERBATAS record (got \(special.count))")
ck(zeroCap.count == 22, "22 zero-cap TERBATAS records (got \(zeroCap.count))")
ck(positive.count + special.count + zeroCap.count == terbatasVerified.count,
   "the three classes partition the 55 with no remainder")

var positiveLeaks: [String] = []
for k in positive {
    let line = KBLIVerdict.of(record: k).ownershipLine(isID: false)
    let cap = k.pmaMaxAsing ?? -1
    if line != "Restricted · \(cap)%" || line.contains("Open") { positiveLeaks.append("\(k.kode):\"\(line)\"") }
}
ck(positiveLeaks.isEmpty,
   "every positive-% TERBATAS record reads \"Restricted · N%\" and never contains \"Open\" (leaks: \(positiveLeaks.prefix(5)))")

for k in special {
    let line = KBLIVerdict.of(record: k).ownershipLine(isID: false)
    ck(line == "Restricted · special conditions",
       "\(k.kode) (the one special-condition record) reads the special line (got \"\(line)\")")
}

var zeroCapLeaks: [String] = []
for k in zeroCap {
    let line = KBLIVerdict.of(record: k).ownershipLine(isID: false)
    if line != "Closed" || line.contains("0% Open") || line.contains("Fully open") {
        zeroCapLeaks.append("\(k.kode):\"\(line)\"")
    }
}
ck(zeroCapLeaks.isEmpty,
   "every zero-cap TERBATAS record reads the zero-cap line and never \"0% Open\" nor \"Fully open\" (leaks: \(zeroCapLeaks.prefix(5)))")

// ─────────────────────────────────────────────────────────────────────────────────────────
print("\nundetermined — the third state renders \"—\", never a percentage:")

var undeterminedLeaks: [String] = []
var undeterminedCount = 0
for k in records {
    guard case .undetermined = KBLIVerdict.of(record: k).national else { continue }
    undeterminedCount += 1
    let line = KBLIVerdict.of(record: k).ownershipLine(isID: false)
    if line != "—" || line.contains("0%") || line.contains("100%") { undeterminedLeaks.append("\(k.kode):\"\(line)\"") }
}
// Measured on this dataset: every one of the 1,559 records carries a recognised `pma_status`
// (TERBUKA 1,444 / TERTUTUP 60 / TERBATAS 55) and no TERBATAS record lacks a cap — so the
// national axis is never `.undetermined` here. That is a fact about THIS dataset, not a rule this
// file may assume: the invariant below is checked over however many such records exist, zero
// included, rather than asserting a count the data does not carry.
print("  ℹ️  \(undeterminedCount) record(s) carry an undetermined national verdict on this dataset")

// The real dataset never reaches `.undetermined` (measured above) — a synthetic input exercises
// the branch directly, so a mutant that breaks it is caught even though no real record can catch
// it. `KBLIVerdictInput` is a plain struct with a synthesized memberwise init; a `pma_status` this
// file has never seen (here: absent) is exactly `nationalVerdict`'s own fall-through case.
let syntheticUndetermined = KBLIVerdict.derive(KBLIVerdictInput(
    code: "TEST-UNDETERMINED", pmaStatus: nil, pmaMaxAsing: nil, pmaKondisi: nil,
    pmaCapSpecial: false, pmaRouteTo: nil, baliRecordPresent: false, baliStatus: nil,
    baliBlocked: false, baliReason: nil, riskRows: []))
let syntheticIsUndetermined: Bool = { if case .undetermined = syntheticUndetermined.national { return true } else { return false } }()
ck(syntheticIsUndetermined, "sanity check: the synthetic no-status input derives .undetermined on the national axis")
ck(syntheticUndetermined.ownershipLine(isID: false) == "—", "synthetic undetermined record's ownershipLine is \"—\" in English")
ck(syntheticUndetermined.ownershipLine(isID: true) == "—", "synthetic undetermined record's ownershipLine is \"—\" in Indonesian too")
ck(undeterminedLeaks.isEmpty,
   "every undetermined record renders \"—\" and never \"0%\" nor \"100%\" (leaks: \(undeterminedLeaks.prefix(5)))")

// ─────────────────────────────────────────────────────────────────────────────────────────
print("\nstatic probe — no surface outside KBLIVerdict.swift reconstructs the line as a literal:")

// `KBLI_JSON` is `<ROOT>/Resources/KBLI_2025_FINAL_CLEAN.json` per the suite recipe — walk back
// up to `<ROOT>` and into `Sources/`, rather than assuming a relative path from the binary.
let sourcesRoot = URL(fileURLWithPath: jsonPath)
    .deletingLastPathComponent()   // KBLI_2025_FINAL_CLEAN.json
    .deletingLastPathComponent()   // Resources
    .appendingPathComponent("Sources")

func allSwiftFiles(under root: URL) -> [URL] {
    var results: [URL] = []
    guard let e = FileManager.default.enumerator(at: root, includingPropertiesForKeys: nil) else { return results }
    for case let url as URL in e where url.pathExtension == "swift" { results.append(url) }
    return results
}

guard FileManager.default.fileExists(atPath: sourcesRoot.path) else {
    print("could not locate Sources/ from KBLI_JSON=\(jsonPath) — expected \(sourcesRoot.path)")
    exit(2)
}
let swiftFiles = allSwiftFiles(under: sourcesRoot)
// A probe that silently scans zero files would pass vacuously — the exact "believable zero"
// shape this codebase's own lessons warn against. Assert a real tree was walked.
ck(swiftFiles.count > 20, "scanned a real Sources tree (\(swiftFiles.count) .swift files found)")

let forbidden = ["Fully open", "% Open", "Restricted ·"]
var staticProbeViolations: [String] = []
for file in swiftFiles where file.lastPathComponent != "KBLIVerdict.swift" {
    guard let text = try? String(contentsOf: file, encoding: .utf8) else { continue }
    for pattern in forbidden where text.contains(pattern) {
        staticProbeViolations.append("\(file.lastPathComponent): contains \"\(pattern)\"")
    }
}
ck(staticProbeViolations.isEmpty,
   "none of \(forbidden) appears outside KBLIVerdict.swift (violations: \(staticProbeViolations.prefix(10)))")

// Positive control: the probe must be able to SEE the pattern, or its silence proves nothing —
// KBLIVerdict.swift itself legitimately carries "Restricted ·" in `ownershipLine`.
let verdictFile = sourcesRoot.appendingPathComponent("KBLIVerdict.swift")
if let text = try? String(contentsOf: verdictFile, encoding: .utf8) {
    ck(text.contains("Restricted ·"), "positive control: KBLIVerdict.swift contains \"Restricted ·\" (the probe can detect the pattern)")
} else {
    ck(false, "could not read KBLIVerdict.swift for the positive control at \(verdictFile.path)")
}

done()
