import Foundation

// Tests/verdicttest — the ONE verdict rule, exercised over the WHOLE dataset.
//
// Every condition below carries BOTH a guilt case and an innocence case, because this product
// has already paid twice for a guard that only ever checked one side: on 2026-06-27 a national
// closure was made to dominate (guilt), and the *unknown* case was never added (innocence of the
// "everything else is open" branch was never tested, and 8 codes have been shown as open to a PT
// PMA ever since). Counts are not asserted from the spec — they are re-derived from the dataset
// in the same run and cross-checked against the values measured on 2026-09-13 for sha
// 3dafab17f6c48477c34ae562d74d5015faeba74a44fee125ee9267c6c45da2e8.

var failures = 0
func ck(_ c: Bool, _ m: String) {
    if c { print("  ✅ \(m)") } else { print("  ❌ FAIL: \(m)"); failures += 1 }
}
func done() -> Never {
    if failures == 0 { print("ALL VERDICT TESTS PASSED"); exit(0) }
    print("\(failures) FAILURE(S)"); exit(1)
}

guard let jsonPath = ProcessInfo.processInfo.environment["KBLI_JSON"],
      let store = KBLIStore(jsonPath: jsonPath),
      let schema = KBLIRawSchemaIndex(jsonPath: jsonPath) else {
    print("set KBLI_JSON to the bundled dataset path"); exit(2)
}

let records = store.all
let verdicts = Dictionary(uniqueKeysWithValues: records.map { ($0.kode, KBLIVerdict.of(record: $0)) })

print("census — the corpus the rule is judged on:")
ck(records.count == 1559, "1,559 records loaded (got \(records.count))")

// ─────────────────────────────────────────────────────────────────────────────────────────
print("\none rule, two doors — the typed model and the raw JSON index cannot drift:")
var adapterMismatch: [String] = []
for k in records {
    guard let raw = schema.raw(k.kode) else { adapterMismatch.append("\(k.kode):no-raw"); continue }
    if KBLIVerdict.of(record: k) != KBLIVerdict.of(rawRecord: raw, code: k.kode) {
        adapterMismatch.append(k.kode)
    }
}
ck(adapterMismatch.isEmpty, "all \(records.count) records derive the SAME verdict from both adapters (mismatches: \(adapterMismatch.prefix(5)))")

// ─────────────────────────────────────────────────────────────────────────────────────────
print("\nGUILT — an established closure is never softened by uncertainty:")

let l4Tertutup = records.filter { ($0.l4Bali?.status ?? "") == "TERTUTUP" }
// 72, not 68: 2026-09-17 re-anchor to canonical b30b1759…. Measured against the OLD anchor
// (c69a260d…, /tmp/kbli-2026-09-17/KBLI-c69a260d.json): OLD_COUNT 68 (no pin error — this pin
// already matched the prior anchor exactly). ENTRIES (4, new TERTUTUP): 10214 16221 95220 95299.
// EXITS: none. 68 + 4 − 0 = 72.
ck(l4Tertutup.count == 72, "72 records carry l4_bali.status == TERTUTUP (got \(l4Tertutup.count))")
let tertutupNotClosed = l4Tertutup.filter { k in
    switch verdicts[k.kode]!.headline {
    case .nationallyClosed, .baliBlocked: return false
    default: return true
    }
}
ck(tertutupNotClosed.isEmpty, "every one of the 72 reads as closed — none open, none undetermined (leaks: \(tertutupNotClosed.prefix(5).map { $0.kode }))")

let blockedTrue = records.filter { $0.l4Bali?.blocked == true }
// 135, not 519: 2026-09-17 re-anchor to canonical b30b1759…. Measured against the OLD anchor
// (c69a260d…): OLD_COUNT 519 (no pin error — this pin already matched the prior anchor exactly,
// per the "519, not 518" note it replaces). ENTRIES (17): 55101 55102 55103 55104 55105 55106
// 55400 56400 68111 68112 68123 68125 68126 68127 68129 77100 77510. EXITS (401): the bulk is the
// old BLOCCATO_CLASSE_RISCHIO population reclassifying to the unblocked ATTENZIONE_FASCIA_BALI
// third state (349 of the 373 old BLOCCATO_CLASSE_RISCHIO codes; the other 24 kept blocked=true
// under a new status), plus 52 further codes individually reclassified elsewhere — the full
// 401-code EXITS set is enumerated (codes only) in
// docs/gates/2026-09-17-candidato/pin-reconciliation-8f0367a.json and in the commit body of the
// receipt commit that adds it; population arithmetic: 519 + 17 − 401 = 135.
ck(blockedTrue.count == 135, "135 records carry l4_bali.blocked == true (got \(blockedTrue.count))")
let blockedLeaks = blockedTrue.filter { k in
    switch verdicts[k.kode]!.headline {
    case .openInBali, .baliUndetermined: return true
    default: return false
    }
}
ck(blockedLeaks.isEmpty, "no blocked record is reported open or Bali-undetermined (leaks: \(blockedLeaks.prefix(5).map { $0.kode }))")

let nonClass = records.filter { ($0.l4Bali?.status ?? "") == "NON_CLASSIFICABILE" }
// 24, not 25: 2026-09-17 re-anchor. OLD_COUNT 25 (no pin error). ENTRIES: none. EXITS (1):
// 68112, which left NON_CLASSIFICABILE for CHIUSO_BALI/blocked=true. 25 + 0 − 1 = 24.
ck(nonClass.count == 24, "24 records are NON_CLASSIFICABILE (got \(nonClass.count))")
let nonClassBlocked = nonClass.filter { $0.l4Bali?.blocked == true }
// 0, not 17: the 17 codes that used to be NON_CLASSIFICABILE+blocked stayed NON_CLASSIFICABILE
// but their `blocked` flag itself flipped to false in the same re-anchor (measured: 47771 52211
// 70100 91424 93115 93121 93122 93123 93125 93126 93128 93129 93192 93194 93195 93197 93199 —
// 17 codes, all now blocked=false). Not a pin error: this is a real reclassification, not a
// count nobody re-measured.
ck(nonClassBlocked.count == 0, "0 of them are already blocked (got \(nonClassBlocked.count))")
let seventeenStillClosed = nonClassBlocked.allSatisfy { k in
    if case .blocked = verdicts[k.kode]!.bali { return true }
    return false
}
ck(seventeenStillClosed, "every still-blocked NON_CLASSIFICABILE record (0 today) keeps a BLOCKED Bali axis — uncertainty never erases a closure")

// ─────────────────────────────────────────────────────────────────────────────────────────
print("\nINNOCENCE — the third state fires on exactly the right set, and nowhere else:")

// 407, not 8: 2026-09-17 re-anchor added ATTENZIONE_FASCIA_BALI (383 codes, the softer "verify
// on OSS" third state — see KBLIVerdict.swift) to the population that already read undetermined
// via NON_CLASSIFICABILE (24 unblocked today). Computed independently of `verdicts` — straight
// off the raw field, mirroring what the SUT's own status-membership dispatch does but without
// calling it — and cross-checked (this run) against `pma_status`: all 407 are TERBUKA nationally,
// so precedence never routes any of them to nationallyClosed/nationalUndetermined ahead of the
// Bali axis; the per-code loop below still re-verifies that per code. ENTRIES (400): 383
// ATTENZIONE_FASCIA_BALI codes + the same 17 NON_CLASSIFICABILE codes whose `blocked` flag
// flipped to false above. EXITS (1): 68112 (see nonClass EXITS above — it left
// NON_CLASSIFICABILE for CHIUSO_BALI/blocked=true, so it also leaves this undetermined set).
// Full 400-code ENTRIES set enumerated (codes only) in
// docs/gates/2026-09-17-candidato/pin-reconciliation-8f0367a.json; 8 + 400 − 1 = 407.
let expectedUndetermined = Set(records.filter { k in
    let s = (k.l4Bali?.status ?? "").uppercased()
    return (s == "NON_CLASSIFICABILE" || s == "ATTENZIONE_FASCIA_BALI") && k.l4Bali?.blocked != true
}.map { $0.kode })
let derivedUndetermined = Set(records.filter { k in
    if case .baliUndetermined = verdicts[k.kode]!.headline { return true }
    return false
}.map { $0.kode })
ck(expectedUndetermined.count == 407, "407 non-blocked NON_CLASSIFICABILE/ATTENZIONE_FASCIA_BALI codes exist (got \(expectedUndetermined.count))")
ck(derivedUndetermined == expectedUndetermined,
   "exactly the 407 non-blocked NON_CLASSIFICABILE/ATTENZIONE_FASCIA_BALI codes read BALI_UNDETERMINED (extra: \(derivedUndetermined.subtracting(expectedUndetermined).sorted().prefix(5)), missing: \(expectedUndetermined.subtracting(derivedUndetermined).sorted().prefix(5)))")

for code in expectedUndetermined.sorted() {
    let v = verdicts[code]!
    ck(v.isOpenToPMAInBali == false, "\(code) is no longer reported open to a PT PMA in Bali")
    ck(v.headlineReason?.isEmpty == false, "\(code) states WHY it cannot be determined")
    if case .open = v.national {} else { ck(false, "\(code) keeps its determined national axis (TERBUKA), uncertainty attaches to the Bali axis only") }
}

// innocence of the whole rule: an ordinary open code stays open.
// 68111 was dropped from this list 2026-09-17: on the OLD anchor (c69a260d…) it carried
// status CHIUSO_BALI_PROPOSTO / blocked=false — a genuine "a proposed closure is not a closure"
// case. On the re-anchored canonical (b30b1759…) it is one of the 39 codes that entered
// CHIUSO_BALI with blocked=true (see the blockedTrue ENTRIES list above): the moratorium
// proposal was finalised for this code, so it is now correctly BALI_BLOCKED — not a pin error,
// a real closure. 01112 replaces it as the stable open control (OK_or_HIGHER_RISK / blocked=false
// / TERBUKA 100%, unaffected by any entries/exits set measured this session) — 79122 was tried
// first and rejected on measurement: it is CLOSED on the ownership axis (0% cap, see the
// ownership-axis block below), so its headline is NATIONALLY_CLOSED, not OPEN_IN_BALI, whatever
// its OK_or_HIGHER_RISK Bali status says.
for open in ["56101", "01112"] {
    ck(verdicts[open]!.isOpenToPMAInBali, "\(open) stays OPEN_IN_BALI")
}
// the CHIUSO_BALI_PROPOSTO innocence case itself: today's dataset carries exactly one such
// record (79110) and it is blocked=true — genuinely closed, not merely proposed — so there is no
// live (CHIUSO_BALI_PROPOSTO, blocked=false) example to assert against. The RULE that a proposed
// closure with blocked=false must read open is still armed in `knownOpenBaliStatuses`
// (KBLIVerdict.swift) and stays covered by the ZZZ_UNKNOWN/known-status tests below, which prove
// the dispatch mechanism rather than one instance of it.
let openCount = records.filter { verdicts[$0.kode]!.isOpenToPMAInBali }.count
print("  · headline census: OPEN_IN_BALI=\(openCount) " +
      "NATIONALLY_CLOSED=\(records.filter { if case .nationallyClosed = verdicts[$0.kode]!.headline { return true }; return false }.count) " +
      "BALI_BLOCKED=\(records.filter { if case .baliBlocked = verdicts[$0.kode]!.headline { return true }; return false }.count) " +
      "BALI_UNDETERMINED=\(derivedUndetermined.count) " +
      "NATIONAL_UNDETERMINED=\(records.filter { if case .nationalUndetermined = verdicts[$0.kode]!.headline { return true }; return false }.count)")
let buckets = records.reduce(into: [String: Int]()) { acc, k in acc[verdicts[k.kode]!.headlineTag, default: 0] += 1 }
ck(buckets.values.reduce(0, +) == records.count && buckets.keys.count <= 5,
   "every record lands in exactly one of the five headline buckets: \(buckets.sorted { $0.key < $1.key })")

// ─────────────────────────────────────────────────────────────────────────────────────────
print("\nthe ownership axis — a cap is a measured number or it is nothing:")
let v79122 = verdicts["79122"]!
if case .closed(let r) = v79122.national {
    ck(r.contains("0%"), "79122 (Umrah/Hajj) is CLOSED on the ownership axis with its 0% cap named")
} else { ck(false, "79122 must be closed on the ownership axis, got \(v79122.national)") }
ck(v79122.nationalCap == nil, "79122 exposes no cap percentage to render (a closure has no cap to quote)")

if case .restricted(let c) = verdicts["51101"]!.national { ck(c == 49, "51101 is RESTRICTED at 49%") }
else { ck(false, "51101 must be restricted, got \(verdicts["51101"]!.national)") }
if case .restricted(let c) = verdicts["25200"]!.national { ck(c == 49, "25200 is RESTRICTED at 49%") }
else { ck(false, "25200 must be restricted, got \(verdicts["25200"]!.national)") }

// the special-distribution class: capless but NOT closed and NOT "0%"
let v47221 = verdicts["47221"]!
if case .restricted(let c) = v47221.national {
    ck(c == nil, "47221 (special distribution network) is restricted with NO numeric cap")
} else { ck(false, "47221 must be restricted-with-condition, got \(v47221.national)") }
ck(v47221.nationalCondition?.isEmpty == false, "47221 carries its non-percentage condition instead of a fabricated 0%")

// TERBUKA with no recorded cap: open is determined, the number is not
let v01122 = verdicts["01122"]!
ck(v01122.isOpenToPMAInBali, "01122 (TERBUKA, no cap recorded) stays open — a missing number is not a missing status")
ck(v01122.nationalCap == nil, "01122 exposes no cap (renders \"—\", never a default)")

// ─────────────────────────────────────────────────────────────────────────────────────────
print("\nthe risk axis — .absent is an answer, never a default:")
let noRisk = records.filter { k in k.perSkala.allSatisfy { ($0.kategoriRisiko ?? "").isEmpty } }
ck(noRisk.count == 217, "217 records carry no kategori_risiko on any scale row (got \(noRisk.count))")
ck(noRisk.allSatisfy { verdicts[$0.kode]!.risk == .absent },
   "all 217 read .absent — none receives the old `?? \"Menengah Rendah\"` default")
ck(noRisk.allSatisfy { verdicts[$0.kode]!.riskLabelRaw == nil }, "all 217 expose nil to render (\"—\")")
// innocence: a present risk is never dropped, and is always a value the record actually carries
let withRisk = records.filter { k in k.perSkala.contains { ($0.kategoriRisiko ?? "").isEmpty == false } }
ck(withRisk.count + noRisk.count == records.count, "every record is in exactly one of the two risk populations")
let fabricated = withRisk.filter { k in
    guard let label = verdicts[k.kode]!.riskLabelRaw else { return true }
    return k.perSkala.contains { $0.kategoriRisiko == label } == false
}
ck(fabricated.isEmpty, "no record's risk label is a value absent from its own rows (fabrications: \(fabricated.prefix(5).map { $0.kode }))")
// the Besar scale wins where it exists (the "Medium-Low restaurant" trap)
if let besarRow = store.all.first(where: { $0.kode == "56101" })?.perSkala.first(where: { $0.skalaUsaha.contains { $0.lowercased().contains("besar") } }),
   let besarCat = besarRow.kategoriRisiko {
    ck(verdicts["56101"]!.riskLabelRaw == besarCat, "56101 reports the Besar-scale risk (\(besarCat)), not the Mikro row")
}

// ─────────────────────────────────────────────────────────────────────────────────────────
print("\nthe package builder consumes the verdict (proved on the built package, not by grep):")
for code in ["20111", "56303", "79122", "56101"] {
    guard let raw = schema.raw(code) else { ck(false, "raw record for \(code)"); continue }
    let outcome = KBLIContextPackageBuilder.build(question: code, currentCard: nil, history: [],
                                                  store: store, schema: schema)
    guard case .built(let prompt, let included, _, _, _) = outcome, included.contains(code) else {
        ck(false, "package builds for \(code)"); continue
    }
    let expected = KBLIVerdict.of(rawRecord: raw, code: code)
    ck(prompt.contains("\"pma_bali_verdict\""), "\(code): the served package carries a pma_bali_verdict block")
    ck(prompt.contains("\"headline\":\"\(expected.headlineTag)\""),
       "\(code): the package's headline is the verdict's own (\(expected.headlineTag)) — not a second derivation")
}
// the third state reaches the model verbatim
if case .built(let prompt, _, _, _, _) = KBLIContextPackageBuilder.build(question: "20111", currentCard: nil, history: [], store: store, schema: schema) {
    ck(prompt.contains("BALI_UNDETERMINED"), "an undetermined code reaches the model AS undetermined")
    ck(prompt.contains("do NOT report such a code as open"), "the preamble forbids resolving an undetermined code either way")
}
// innocence: an open code is not relabelled by the new block
if case .built(let prompt, _, _, _, _) = KBLIContextPackageBuilder.build(question: "56101", currentCard: nil, history: [], store: store, schema: schema) {
    ck(prompt.contains("\"headline\":\"OPEN_IN_BALI\""), "an open code still reaches the model as open")
}

// ─────────────────────────────────────────────────────────────────────────────────────────
print("\nthe chat consumes the verdict (the seed turn cannot contradict the code page):")
let undeterminedRecord = records.first { $0.kode == "20111" }!
let openRecord = records.first { $0.kode == "56101" }!
for isEN in [true, false] {
    let seedU = KBLIChatSeed.question(code: undeterminedRecord.kode, title: undeterminedRecord.judul,
                                      verdict: KBLIVerdict.of(record: undeterminedRecord), isEnglish: isEN)
    let seedO = KBLIChatSeed.question(code: openRecord.kode, title: openRecord.judul,
                                      verdict: KBLIVerdict.of(record: openRecord), isEnglish: isEN)
    ck(seedU != seedO, "\(isEN ? "EN" : "IT"): the seed turn differs between an undetermined and a determined code")
    ck(seedU.lowercased().contains(isEN ? "not determinable" : "non determinabile"),
       "\(isEN ? "EN" : "IT"): the undetermined seed names the uncertainty")
    ck(seedO.lowercased().contains(isEN ? "not determinable" : "non determinabile") == false,
       "\(isEN ? "EN" : "IT"): innocence — a determined code's seed is unchanged")
}

// ─────────────────────────────────────────────────────────────────────────────────────────
print("\nQ11 — the retrieval intent guarantee, with its innocence corpus:")
let q11 = "Klien mau buka kafe di Ubud. KBLI mana yang tepat dan izin apa saja yang wajib?"
if case .built(_, let included, _, _, _) = KBLIContextPackageBuilder.build(question: q11, currentCard: nil, history: [], store: store, schema: schema) {
    ck(included.contains("56303"), "Q11 package contains 56303 (the Bali-blocked kafe code)")
    ck(included.contains("56101"), "Q11 package contains 56101 (the one a client may actually register)")
} else { ck(false, "Q11 package builds") }

// the guarantee fires only on a term that NAMES something, and on at most one term
ck(KBLIContextPackageBuilder.intentGuaranteedCodes(question: q11, store: store)
     == Set(["10761", "56101", "56290", "56303"]),
   "the guarantee is exactly the 4 records whose text carries \"kafe\" — no more")
let q13 = "Klien asing mau pegang 51% saham PT - semua sektor boleh atau ada batasan?"
let q23 = "Sejak 13 Mei 2026, KBLI apa yang terkena moratorium PMA Bali dan apakah larangannya hanya sementara?"
ck(KBLIContextPackageBuilder.intentGuaranteedCodes(question: q13, store: store).isEmpty,
   "INNOCENCE: Q13 has no naming term that fits the budget — its package is untouched")
ck(KBLIContextPackageBuilder.intentGuaranteedCodes(question: q23, store: store).isEmpty,
   "INNOCENCE: Q23 has no naming term that fits the budget — the question that passes today is not disturbed")
// a term whose hits overflow the slot budget never guarantees
ck(KBLIContextPackageBuilder.intentGuaranteedCodes(question: "restoran", store: store).count
     <= KBLIContextPackageBuilder.maxSearchHits,
   "a guarantee can never exceed the slot budget (\(KBLIContextPackageBuilder.maxSearchHits))")

// ─────────────────────────────────────────────────────────────────────────────────────────
print("\nthe BKPM marker — the issuer is not this program:")
let tmp = FileManager.default.temporaryDirectory.appendingPathComponent("kbli-marker-\(UUID().uuidString)")
try? FileManager.default.createDirectory(at: tmp, withIntermediateDirectories: true)
let absent = tmp.appendingPathComponent("nothing-here.json").path
ck(KBLIBKPMMarker.isValid(markerPath: absent, machineID: "abc") == false, "marker ABSENT → invalid")
ck(KBLIBKPMMarker.currentMachineID()?.isEmpty == false, "this machine has a stable identifier")

let realMarker = ProcessInfo.processInfo.environment["KBLI_BKPM_MARKER_PATH"] ?? KBLIBKPMMarker.markerPath
let haveIssued = FileManager.default.fileExists(atPath: realMarker)
if haveIssued, let me = KBLIBKPMMarker.currentMachineID() {
    ck(KBLIBKPMMarker.isValid(markerPath: realMarker, machineID: me), "an ISSUED marker validates on the machine it was cut for")
    ck(KBLIBKPMMarker.isValid(markerPath: realMarker, machineID: String(repeating: "0", count: 64)) == false,
       "the SAME marker fails for a different machine identity")
    // tamper: flip the machine_id in the file, keep the signature
    if let data = FileManager.default.contents(atPath: realMarker),
       var obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] {
        obj["machine_id"] = String(repeating: "0", count: 64)
        let tampered = tmp.appendingPathComponent("tampered.json").path
        FileManager.default.createFile(atPath: tampered, contents: try? JSONSerialization.data(withJSONObject: obj, options: [.sortedKeys]))
        ck(KBLIBKPMMarker.isValid(markerPath: tampered, machineID: String(repeating: "0", count: 64)) == false,
           "re-pointing a marker at another machine breaks its signature")
        obj["machine_id"] = KBLIBKPMMarker.currentMachineID()!
        obj["scope"] = "everything"
        let widened = tmp.appendingPathComponent("widened.json").path
        FileManager.default.createFile(atPath: widened, contents: try? JSONSerialization.data(withJSONObject: obj, options: [.sortedKeys]))
        ck(KBLIBKPMMarker.isValid(markerPath: widened, machineID: KBLIBKPMMarker.currentMachineID()!) == false,
           "widening the scope inside the file breaks its signature")
    }
} else {
    print("  · no issued marker on this host — issue one with Tools/kbli-bkpm-provision to exercise the positive case")
}

print("\nthe marker is a HARD gate — a working seat never substitutes for it:")
ck(KBLIBrain.availability(variant: .bkpm, markerValid: false) == .offline(reason: "bkpm-no-marker"),
   "BKPM + no marker → offline, whatever the seat says")
let internalWithoutMarker = KBLIBrain.availability(variant: .internalFull, markerValid: false)
ck(internalWithoutMarker != .offline(reason: "bkpm-no-marker"),
   "INNOCENCE: the internal variant is not gated by the marker (got \(internalWithoutMarker))")
ck(KBLIBrain.availability(variant: .bkpm, markerValid: true) == internalWithoutMarker,
   "with a valid marker the BKPM verdict is exactly the seat's own verdict — the marker adds a gate, never a bypass")
// the pages do not depend on the brain
ck(store.all.count == 1559 && store.search("kafe").total > 0,
   "with the chat gated off, the catalogue still loads and searches (the pages keep working)")

// ─────────────────────────────────────────────────────────────────────────────────────────
print("\nthe legacy path is UNREACHABLE, not absent:")
ck(useLegacyOpenClawBrain == false, "the legacy flag is off")
let sourcesDir = ProcessInfo.processInfo.environment["KBLI_SOURCES_DIR"] ?? "Sources"
var legacyRefs: [String] = []
var chatViewBody = ""
if let e = FileManager.default.enumerator(atPath: sourcesDir) {
    for case let f as String in e where f.hasSuffix(".swift") {
        guard let text = try? String(contentsOfFile: sourcesDir + "/" + f, encoding: .utf8) else { continue }
        if f.hasSuffix("ChatView.swift") { chatViewBody = text }
        if f.hasSuffix("OpenClawRunner.swift") { continue }
        for (n, line) in text.components(separatedBy: "\n").enumerated() where line.contains("OpenClawRunner") {
            if line.trimmingCharacters(in: .whitespaces).hasPrefix("//") { continue }
            legacyRefs.append("\(f):\(n + 1)")
        }
    }
}
ck(legacyRefs.allSatisfy { $0.hasPrefix("Views/ChatView.swift:") },
   "every non-comment reference to OpenClawRunner outside its own file is in ChatView (found \(legacyRefs))")
ck(chatViewBody.isEmpty == false, "ChatView source was read (\(sourcesDir))")
let legacyCallSites = chatViewBody.components(separatedBy: "\n").enumerated().filter {
    $0.element.contains("runLegacyTurn(") && $0.element.trimmingCharacters(in: .whitespaces).hasPrefix("//") == false
}
ck(legacyCallSites.count == 2, "runLegacyTurn appears exactly twice: one guarded call, one definition (got \(legacyCallSites.count))")
if let call = legacyCallSites.first {
    let lines = chatViewBody.components(separatedBy: "\n")
    let window = lines[max(0, call.offset - 3)..<call.offset].joined(separator: " ")
    ck(window.contains("if useLegacyOpenClawBrain"),
       "the only call to the legacy brain sits directly under `if useLegacyOpenClawBrain`")
}
// …and every one of those references is either the stored property or inside the guarded
// function: nothing else in the view can reach the legacy brain.
let chatLines = chatViewBody.components(separatedBy: "\n")
let declLine = chatLines.firstIndex { $0.contains("private let legacyRunner") }
let legacyFuncLine = chatLines.firstIndex { $0.contains("private func runLegacyTurn") }
ck(declLine != nil && legacyFuncLine != nil, "ChatView has one stored legacy runner and one guarded legacy function")
let strayRefs = chatLines.enumerated().filter { (i, line) in
    guard line.contains("OpenClawRunner"), line.trimmingCharacters(in: .whitespaces).hasPrefix("//") == false else { return false }
    return i != declLine && i < (legacyFuncLine ?? 0)
}.map { $0.offset + 1 }
ck(strayRefs.isEmpty, "no reference to the legacy runner outside the declaration and the guarded function (stray: \(strayRefs))")
ck(chatViewBody.contains("legacyRunner.ask"), "the legacy runner is still COMPILED and callable — unreachable, not deleted")


// ─────────────────────────────────────────────────────────────────────────────────────────
print("\ncouncil round 3 — an established closure is never lost to a missing status field:")
// codex-gpt-5.6-sol, VERDICT DEFECT: `pma_status` absent with a 0% cap fell through to
// NATIONAL_UNDETERMINED. A 0% cap is a closure whatever the status word says, or does not say.
let noStatusZeroCap = KBLIVerdictInput(
    code: "T0001", pmaStatus: nil, pmaMaxAsing: 0, pmaKondisi: nil, pmaCapSpecial: false,
    pmaRouteTo: nil, baliRecordPresent: true, baliStatus: "OK_or_HIGHER_RISK", baliBlocked: false,
    baliReason: nil, riskRows: [(scales: ["Besar"], category: "Rendah")])
if case .closed = KBLIVerdict.derive(noStatusZeroCap).national {
    ck(true, "pma_status missing + 0% cap reads CLOSED, not undetermined")
} else {
    ck(false, "pma_status missing + 0% cap must read closed, got \(KBLIVerdict.derive(noStatusZeroCap).national)")
}
let unknownStatusZeroCap = KBLIVerdictInput(
    code: "T0002", pmaStatus: "SOMETHING_NEW", pmaMaxAsing: 0, pmaKondisi: nil, pmaCapSpecial: false,
    pmaRouteTo: nil, baliRecordPresent: true, baliStatus: "OK_or_HIGHER_RISK", baliBlocked: false,
    baliReason: nil, riskRows: [])
ck(KBLIVerdict.derive(unknownStatusZeroCap).headlineTag == "NATIONALLY_CLOSED",
   "an unrecognised status word + 0% cap still reads NATIONALLY_CLOSED")
// INNOCENCE: a missing status with a NON-zero cap is genuinely undetermined, not closed
let noStatusRealCap = KBLIVerdictInput(
    code: "T0003", pmaStatus: nil, pmaMaxAsing: 49, pmaKondisi: nil, pmaCapSpecial: false,
    pmaRouteTo: nil, baliRecordPresent: true, baliStatus: "OK_or_HIGHER_RISK", baliBlocked: false,
    baliReason: nil, riskRows: [])
ck(KBLIVerdict.derive(noStatusRealCap).headlineTag == "NATIONAL_UNDETERMINED",
   "INNOCENCE: a missing status with a real cap stays undetermined — a 0% cap is the fact, not the gap")
// INNOCENCE: the special-distribution class is still NOT closed, although its cap is not a number
ck(verdicts["47221"]!.headlineTag != "NATIONALLY_CLOSED",
   "INNOCENCE: 47221 is still not reported closed after the 0%-cap rule moved above the status dispatch")

print("\ncouncil round 3 — the two adapters accept exactly the same shapes:")
// codex-gpt-5.6-sol, VERDICT DEFECT: the raw adapter accepted a SCALAR skala_usaha, which the
// typed decoder drops. It would have seen a "Besar" row the typed side cannot see.
let scalarScaleRaw: [String: Any] = [
    "kode_kbli_2025": "T0004", "pma_status": "TERBUKA", "pma_max_asing": 100,
    "l4_bali": ["status": "OK_or_HIGHER_RISK", "blocked": false],
    "per_skala": [
        ["skala_usaha": "Besar", "kategori_risiko": "Rendah"],
        ["skala_usaha": ["Mikro"], "kategori_risiko": "Tinggi"],
    ],
]
let rawScalar = KBLIVerdict.of(rawRecord: scalarScaleRaw, code: "T0004")
ck(rawScalar.riskLabelRaw == "Tinggi",
   "a SCALAR skala_usaha is ignored by both adapters — the highest remaining tier wins (got \(rawScalar.riskLabelRaw ?? "nil"))")
// INNOCENCE: a proper array Besar row is still honoured
let arrayScaleRaw: [String: Any] = [
    "kode_kbli_2025": "T0005", "pma_status": "TERBUKA", "pma_max_asing": 100,
    "l4_bali": ["status": "OK_or_HIGHER_RISK", "blocked": false],
    "per_skala": [
        ["skala_usaha": ["Besar"], "kategori_risiko": "Rendah"],
        ["skala_usaha": ["Mikro"], "kategori_risiko": "Tinggi"],
    ],
]
ck(KBLIVerdict.of(rawRecord: arrayScaleRaw, code: "T0005").riskLabelRaw == "Rendah",
   "INNOCENCE: an array-shaped Besar row still wins over a riskier Mikro row")


print("\ncouncil round 4 — the risk axis never understates across OSS scopes:")
// codex-gpt-5.6-sol, VERDICT DEFECT: a code can carry one scale block per OSS scope, and 01140
// has Besar/Menengah Tinggi on scope 0 and Besar/Tinggi on scope 1. Taking the FIRST Besar row
// understated the class for every later scope.
let twoBesarScopes: [String: Any] = [
    "kode_kbli_2025": "T0006", "pma_status": "TERBUKA", "pma_max_asing": 100,
    "l4_bali": ["status": "OK_or_HIGHER_RISK", "blocked": false],
    "per_skala": [
        ["skala_usaha": ["Besar"], "kategori_risiko": "Menengah Tinggi", "scope_index": 0],
        ["skala_usaha": ["Besar"], "kategori_risiko": "Tinggi", "scope_index": 1],
    ],
]
ck(KBLIVerdict.of(rawRecord: twoBesarScopes, code: "T0006").riskLabelRaw == "Tinggi",
   "the HIGHEST Besar row wins across scopes, never the first")
// INNOCENCE: a Besar row still beats a riskier non-Besar row — the rule did not become "highest
// of everything", which would reintroduce the Mikro overstatement from the other side
let besarLowerThanMikro: [String: Any] = [
    "kode_kbli_2025": "T0007", "pma_status": "TERBUKA", "pma_max_asing": 100,
    "l4_bali": ["status": "OK_or_HIGHER_RISK", "blocked": false],
    "per_skala": [
        ["skala_usaha": ["Mikro"], "kategori_risiko": "Tinggi"],
        ["skala_usaha": ["Besar"], "kategori_risiko": "Rendah"],
    ],
]
ck(KBLIVerdict.of(rawRecord: besarLowerThanMikro, code: "T0007").riskLabelRaw == "Rendah",
   "INNOCENCE: Besar still governs — the rule is 'highest BESAR', not 'highest row'")
if let r01140 = schema.raw("01140") {
    let v = KBLIVerdict.of(rawRecord: r01140, code: "01140")
    print("  · 01140 on this dataset reads risk \(v.riskLabelRaw ?? "—")")
}

// ─────────────────────────────────────────────────────────────────────────────────────────
print("\ncouncil round 5 — every l4_bali.status the dataset carries is EXPLICITLY mapped, and a")
print("status this file has never seen defaults to undetermined, never to open:")
// (a) guilt: the dataset's real status set must be a SUBSET of KBLIVerdict's exhaustive
// registry. Built independently of `baliVerdict`'s own dispatch — straight off the raw records —
// so this cannot pass merely because the SUT and the check share one Set literal.
let datasetBaliStatuses = Set(records.compactMap { $0.l4Bali?.status.uppercased() })
let unmapped = datasetBaliStatuses.subtracting(KBLIVerdict.knownBaliStatuses)
ck(unmapped.isEmpty,
   "every l4_bali.status present in the dataset is in KBLIVerdict.knownBaliStatuses (unmapped: \(unmapped.sorted()))")
// INNOCENCE: the registry is not vacuously wide — it doesn't, for instance, claim a status the
// dataset does not carry as its only member (that would pass (a) by never being exercised).
ck(datasetBaliStatuses.isEmpty == false && KBLIVerdict.knownBaliStatuses.isSuperset(of: datasetBaliStatuses),
   "INNOCENCE: the registry actually covers a non-empty, real dataset status set")

// (b) an injected unknown status must never render open, and must never render blocked either —
// only `blocked` does that, never the status word. A status this file has genuinely never
// classified is undetermined by construction (the ZZZ_UNKNOWN guarantee).
let zzzUnknownInput = KBLIVerdictInput(
    code: "T0008", pmaStatus: "TERBUKA", pmaMaxAsing: 100, pmaKondisi: nil, pmaCapSpecial: false,
    pmaRouteTo: nil, baliRecordPresent: true, baliStatus: "ZZZ_UNKNOWN", baliBlocked: false,
    baliReason: nil, riskRows: [])
let zzzVerdict = KBLIVerdict.derive(zzzUnknownInput)
ck(zzzVerdict.headlineTag == "BALI_UNDETERMINED",
   "an injected 'ZZZ_UNKNOWN' status maps to BALI_UNDETERMINED (got \(zzzVerdict.headlineTag))")
ck(zzzVerdict.headlineReason?.isEmpty == false, "ZZZ_UNKNOWN states a reason, never a silent undetermined")
ck(zzzVerdict.isOpenToPMAInBali == false, "ZZZ_UNKNOWN is never reported open")
if case .blocked = zzzVerdict.bali { ck(false, "ZZZ_UNKNOWN with blocked=false must never read BLOCKED") }
else { ck(true, "ZZZ_UNKNOWN with blocked=false never reads BLOCKED") }
// INNOCENCE: the SAME unknown status WITH blocked=true still reads blocked — `blocked` outranks
// the status word in both directions, unknown or known.
let zzzUnknownBlocked = KBLIVerdictInput(
    code: "T0009", pmaStatus: "TERBUKA", pmaMaxAsing: 100, pmaKondisi: nil, pmaCapSpecial: false,
    pmaRouteTo: nil, baliRecordPresent: true, baliStatus: "ZZZ_UNKNOWN", baliBlocked: true,
    baliReason: "test fixture", riskRows: [])
ck(KBLIVerdict.derive(zzzUnknownBlocked).headlineTag == "BALI_BLOCKED",
   "INNOCENCE: the same unknown status WITH blocked=true still reads BALI_BLOCKED")

done()
