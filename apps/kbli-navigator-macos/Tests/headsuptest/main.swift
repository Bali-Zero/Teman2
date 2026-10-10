import Foundation

// Tests/headsuptest — the heads-up projection (spec §2) over the WHOLE dataset, guilt AND
// innocence: the census, the open pair's iff, the named first codes, the frozen codes, the
// class-5 membership, the synthetic TERTUTUP (OQ-14), and "no raw Bali token in any label".

var failures = 0
func ck(_ c: Bool, _ m: String) {
    if c { print("  ✅ \(m)") } else { print("  ❌ FAIL: \(m)"); failures += 1 }
}
func done() -> Never {
    if failures == 0 { print("ALL HEADS-UP TESTS PASSED"); exit(0) }
    print("\(failures) FAILURE(S)"); exit(1)
}

guard let jsonPath = ProcessInfo.processInfo.environment["KBLI_JSON"],
      let store = KBLIStore(jsonPath: jsonPath) else {
    print("set KBLI_JSON to the bundled dataset path"); exit(2)
}

MainActor.assumeIsolated {
    let records = store.all
    let byCode = Dictionary(records.map { ($0.kode, $0) }, uniquingKeysWith: { a, _ in a })
    @MainActor func hu(_ k: KBLI, _ isID: Bool = false) -> (label: String, sentence: String?, tone: Theme.Tone) {
        KBLIVerdict.headsUp(record: k, isID: isID)
    }
    func cls(_ k: KBLI) -> Int { KBLIVerdict.of(record: k).headsUpClass }
    @MainActor func tbl(_ isID: Bool) -> [String: String] { LanguageManager.strings[isID ? .id : .en]! }

    print("class census:")
    var census: [Int: Int] = [:]
    var first: [Int: KBLI] = [:]
    for k in records {
        let c = cls(k)
        census[c, default: 0] += 1
        if first[c] == nil { first[c] = k }
    }
    let want: [Int: Int] = [1: 135, 2: 21, 3: 0, 4: 395, 5: 31, 6: 1, 7: 976]
    for c in 1...7 { ck((census[c] ?? 0) == want[c]!, "class \(c): \(census[c] ?? 0) == \(want[c]!)") }
    ck(census.values.reduce(0, +) == 1559 && records.count == 1559, "total 1559")

    // N5: a moved code is NAMED, against the committed membership (Tests/headsuptest/classes.txt,
    // one line per class, for the anchored dataset). Regenerate with HEADSUP_WRITE_CLASSES=<path>.
    let env = ProcessInfo.processInfo.environment
    if let out = env["HEADSUP_WRITE_CLASSES"] {
        let lines = (1...7).map { c in ([String(c)] + records.filter { cls($0) == c }.map(\.kode)).joined(separator: " ") }
        try? (lines.joined(separator: "\n") + "\n").write(toFile: out, atomically: true, encoding: .utf8)
        print("wrote \(out)"); exit(0)
    }
    let root = env["KBLI_APP_ROOT"] ?? FileManager.default.currentDirectoryPath
    var frozen: [String: Int] = [:]
    for line in ((try? String(contentsOfFile: root + "/Tests/headsuptest/classes.txt", encoding: .utf8)) ?? "").split(separator: "\n") {
        let f = line.split(separator: " ").map(String.init)
        if let c = f.first.flatMap(Int.init) { for code in f.dropFirst() { frozen[code] = c } }
    }
    let moved = records.compactMap { k in frozen[k.kode] == cls(k) ? nil : "\(k.kode): class \(frozen[k.kode].map(String.init) ?? "none") → \(cls(k))" }
    let gone = Set(frozen.keys).subtracting(records.map(\.kode)).sorted()
    ck(frozen.count == 1559 && moved.isEmpty && gone.isEmpty, "every code in its committed class (moved: \(moved.prefix(10)), gone: \(gone.prefix(10)))")

    print("\nthe open pair appears iff TERBUKA and Bali open (both directions, both languages):")
    var openBad: [String] = []
    for k in records {
        let v = KBLIVerdict.of(record: k)
        let expected = k.pmaStatus == "TERBUKA" && v.bali == .open
        for isID in [false, true] {
            let r = hu(k, isID)
            let t = tbl(isID)
            let shown = r.label == t["rich.verdict.open"]! || r.sentence == t["dossier.holding.open"]!
            if shown != expected { openBad.append("\(k.kode):\(isID)") }
        }
    }
    ck(openBad.isEmpty, "open pair iff TERBUKA && bali open on all records (violations: \(openBad.prefix(5)))")

    print("\nfirst code per class, in dataset order:")
    for c in [1, 2, 4, 5, 6, 7] {
        guard let k = first[c] else { ck(false, "class \(c) has a first code"); continue }
        let r = hu(k)
        print("  class \(c): first \(k.kode) label=\"\(r.label)\" tone=\(r.tone)")
    }
    ck(first[1].map { hu($0).label == tbl(false)["rich.verdict.blocked"]! && hu($0).tone == .closed } ?? false,
       "class 1 first code carries the blocked label, tone closed")
    // Q12 (2026-10-10): the canonical word is verbatim in id and English in en; an Indonesian pma_kondisi has
    // no English source, so en shows it whole under the "Original (Bahasa Indonesia)" label.
    func original(_ s: String?) -> String? { s.map { "Original (Bahasa Indonesia): “\($0)”" } }
    ck(first[2]?.kode == "10307" && first[2].map {
           hu($0, true).label == "TERBATAS · 0%" && hu($0, true).sentence == $0.pmaKondisi
           && hu($0).label == "Restricted · 0%" && hu($0).sentence == original($0.pmaKondisi) && hu($0).tone == .closed } == true,
       "class 2 first = 10307, label TERBATAS · 0% (en Restricted · 0%), sentence pma_kondisi verbatim (en labelled original), tone closed")
    ck(first[4]?.kode == "01192" && first[4].map { hu($0).label == "NOT DETERMINED" && hu($0).tone == .neutral } == true,
       "class 4 first = 01192, label NOT DETERMINED, tone neutral")
    ck(first[5].map { hu($0).tone == .restricted && hu($0, true).label.hasPrefix("TERBATAS · ") && hu($0).label.hasPrefix("Restricted · ") } == true,
       "class 5 first carries TERBATAS · cap (en Restricted · cap), tone restricted")
    ck(first[6]?.kode == "47221" && first[6].map {
           hu($0, true).label == "TERBATAS" && hu($0).label == "Restricted" && hu($0).tone == .restricted } == true,
       "class 6 first = 47221, label TERBATAS (en Restricted, no cap), tone restricted")
    ck(first[7].map { hu($0).label == tbl(false)["rich.verdict.open"]! && hu($0).tone == .open } == true,
       "class 7 first carries the open label, tone open")

    print("\nfrozen codes:")
    if let k = byCode["55203"] {
        ck(cls(k) == 1 && hu(k).label == "HEADS UP — the verdict" && hu(k).tone == .closed,
           "55203: class 1, label \"HEADS UP — the verdict\", tone closed")
    } else { ck(false, "55203 present") }
    if let k = byCode["56101"] { ck(cls(k) == 7, "56101: class 7") } else { ck(false, "56101 present") }
    if let k = byCode["79110"] { ck(cls(k) == 1, "79110: class 1") } else { ck(false, "79110 present") }
    if let k = byCode["51101"] {
        let en = hu(k, false), id = hu(k, true)
        ck(cls(k) == 5 && id.label == "TERBATAS · 49%" && en.label == "Restricted · 49%",
           "51101: class 5, label \"TERBATAS · 49%\", en \"Restricted · 49%\" (got \"\(id.label)\" / \"\(en.label)\")")
        ck(id.sentence == k.pmaKondisi && k.pmaKondisi != nil, "51101: id sentence == pma_kondisi verbatim (no Kutipan prefix)")
        ck(en.sentence == k.pmaKondisi, "51101: en sentence == pma_kondisi verbatim — English already, so not labelled")
    } else { ck(false, "51101 present") }

    // B3 (0b1 ruling): 448 codes change against the pre-Q10 predicates, frozen here as on main 27ca6fb108:
    // detail card `cannotProceed = baliBlocked || nationallyClosed` (KBLIDetailRichView.swift:189-193) → the
    // rich.verdict.blocked/open label; dossier `l4Bali.blocked == true` (KBLIDossierView.swift:88) → that
    // label + dossier.holding.blocked/open. The changed set must be exactly classes 2–6, in en and id.
    print("\nchanged against the frozen pre-Q10 predicates:")
    let cls26 = Set(records.filter { (2...6).contains(cls($0)) }.map(\.kode))
    for isID in [false, true] {
        let t = tbl(isID)
        var detail = Set<String>(), dossier = Set<String>()
        for kbli in records {
            // KBLIDetailRichView.swift:189-193 at 27ca6fb108, byte for byte after the indentation:
            let v = KBLIVerdict.of(record: kbli)
            let baliBlocked: Bool = { if case .blocked = v.bali { return true } else { return false } }()
            let nationallyClosed: Bool = { if case .closed = v.national { return true } else { return false } }()
            // Any of these means a foreign-owned PMA cannot freely register this code as-is.
            let cannotProceed = baliBlocked || nationallyClosed
            // KBLIDossierView.swift:88 at 27ca6fb108, byte for byte after the indentation:
            let blocked = kbli.l4Bali?.blocked == true
            let r = hu(kbli, isID)
            if r.label != t[cannotProceed ? "rich.verdict.blocked" : "rich.verdict.open"]! { detail.insert(kbli.kode) }
            if r.label != t[blocked ? "rich.verdict.blocked" : "rich.verdict.open"]!
                || r.sentence != t[blocked ? "dossier.holding.blocked" : "dossier.holding.open"]! { dossier.insert(kbli.kode) }
        }
        for (name, got) in [("detail card", detail), ("dossier", dossier)] {
            ck(got.count == 448 && got == cls26, "[\(isID ? "id" : "en")] \(name): \(got.count) changed == 448 == classes 2–6 "
               + "(extra: \(got.subtracting(cls26).sorted().prefix(5)), missing: \(cls26.subtracting(got).sorted().prefix(5)))")
        }
    }

    print("\nclass-5 membership:")
    let wantFive = Set("25200 30400 50111 50112 50113 50121 50122 50123 50124 50125 50126 50131 50132 50133 50134 50135 50211 50212 50213 50221 50222 50223 51101 51102 53200 65111 65112 65121 65122 65201 65202".split(separator: " ").map(String.init))
    let gotFive = Set(records.filter { cls($0) == 5 }.map { $0.kode })
    ck(gotFive == wantFive, "class 5 == the 31 named codes (extra: \(gotFive.subtracting(wantFive).sorted()), missing: \(wantFive.subtracting(gotFive).sorted()))")

    print("\nsynthetic TERTUTUP (OQ-14):")
    func synth(_ route: String?) -> KBLI? {
        let r = route.map { ",\"pma_route_to\":\"\($0)\"" } ?? ""
        let j = "{\"kode_kbli_2025\":\"99999\",\"judul\":\"X\",\"pma_status\":\"TERTUTUP\",\"pma_max_asing\":0\(r),"
            + "\"l4_bali\":{\"status\":\"OK_or_HIGHER_RISK\",\"blocked\":false,\"reason\":\"\"},\"per_skala\":[]}"
        return try? JSONDecoder().decode(KBLI.self, from: Data(j.utf8))
    }
    if let a = synth("12345"), let b = synth(nil) {
        let ra = hu(a), rb = hu(b)
        ck(cls(a) == 2 && ra.label == "Closed" && hu(a, true).label == "TERTUTUP" && ra.tone == .closed
           && ra.sentence == "For a PMA, register 12345 (the private-sector version) instead.",
           "TERTUTUP with route: class 2, label, route sentence (got \(ra.label) / \(ra.sentence ?? "nil"))")
        ck(cls(b) == 2 && rb.label == "Closed" && rb.sentence == "Only a 100% Indonesian-owned entity is permitted.",
           "TERTUTUP without route: class 2, label, 100% sentence (got \(rb.sentence ?? "nil"))")
        ck(hu(a, true).sentence == "Untuk PMA, daftarkan 12345 (versi swasta) sebagai gantinya.", "TERTUTUP with route (id)")
    } else { ck(false, "synthetic TERTUTUP record decodes") }

    print("\nno raw Bali status token in any label (all records, both languages):")
    var leaks: [String] = []
    for k in records {
        for isID in [false, true] {
            let l = hu(k, isID).label
            if l.contains("ATTENZIONE") || l.contains("NON_CLASSIFICABILE") || l.contains("_") { leaks.append("\(k.kode):\(l)") }
        }
    }
    ck(leaks.isEmpty, "no label carries a raw token (leaks: \(leaks.prefix(5)))")
}
done()
