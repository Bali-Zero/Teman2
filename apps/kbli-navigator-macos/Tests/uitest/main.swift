import SwiftUI

func check(_ cond: Bool, _ msg: String) {
    if cond { print("  ✅ \(msg)") } else { print("  ❌ FAIL: \(msg)"); exit(1) }
}

// 3-state status semantics, matching the live web (PMABadge): open(green) / restricted(amber) /
// closed(coral). NEEDS_REVIEW → faint grey. Redesign 2026-06-24 to the real Claude-Night theme.
print("Status helper tests:")
check(Theme.kbliStatusColor("OK_or_HIGHER_RISK") == Theme.pmaOpen, "OK_ → open/green")
check(Theme.kbliStatusColor("TERBUKA") == Theme.pmaOpen, "TERBUKA → open/green")
check(Theme.kbliStatusColor("TERBATAS") == Theme.pmaRestricted, "TERBATAS → restricted/amber")
check(Theme.kbliStatusColor("BLOCCATO_CLASSE_RISCHIO") == Theme.pmaClosed, "BLOCCATO → closed/coral")
check(Theme.kbliStatusColor("CHIUSO_PMA_NO_BESAR") == Theme.pmaClosed, "CHIUSO → closed/coral")
check(Theme.kbliStatusColor("TERTUTUP") == Theme.pmaClosed, "TERTUTUP → closed/coral")
check(Theme.kbliStatusColor("NEEDS_REVIEW_NO_OSS_SCOPE") == Theme.faint, "NEEDS_REVIEW → faint")
check(Theme.kbliStatusSymbol("OK_or_HIGHER_RISK") == "checkmark.circle.fill", "OK_ symbol checkmark.circle.fill")
check(Theme.kbliStatusSymbol("TERBATAS") == "exclamationmark.triangle.fill", "TERBATAS symbol triangle")
check(Theme.kbliStatusSymbol("BLOCCATO_CLASSE_RISCHIO") == "xmark.octagon.fill", "BLOCCATO symbol xmark.octagon.fill")
check(Theme.kbliStatusSymbol("NEEDS_REVIEW_NO_OSS_SCOPE") == "questionmark.circle", "NEEDS_REVIEW symbol questionmark.circle")
// status labels (used inside the soft-tint badge)
// INHERITED RED, not this window's (proved: this file at 830683a fails on `open label` too).
// The labels were made enum-precise and bilingual at some point — "Open to PMA" became
// "Open 100%" and "Closed at Bali" became "Closed to PMA (Besar)" — and these three assertions
// were never moved with them, so the whole runner exited on the first one and everything below
// it stopped being checked. The assertions are corrected to what the app actually renders; the
// LABELS are not touched (they are customer-visible copy and belong to whoever changed them).
check(Theme.kbliStatusLabel("TERBUKA") == "Open 100%", "open label")
check(Theme.kbliStatusLabel("TERBATAS") == "Restricted", "restricted label")
check(Theme.kbliStatusLabel("CHIUSO_PMA_NO_BESAR") == "Closed to PMA (Besar)", "closed label")
// risk-category color mapping (per-scale RiskBadge)
check(Theme.riskColor("RENDAH") == Theme.riskLow, "RENDAH → riskLow")
check(Theme.riskColor("TINGGI") == Theme.riskHigh, "TINGGI → riskHigh")
print("ALL UI HELPER TESTS PASSED")

print("Detail logic tests:")
// Build a couple of L4Bali fixtures by decoding tiny JSON (mirrors real shape)
func l4(_ json: String) -> L4Bali? {
    try? JSONDecoder().decode(L4Bali.self, from: Data(json.utf8))
}
let blocked = l4(#"{"status":"CHIUSO_PMA_NO_BESAR","blocked":true,"moratorium":{"effective":"2026-05-13","source":"Gubernur B.27.000/642/PM/DPMPTSP","rule":"Bali blocks low/med-low risk PMA"}}"#)
let openOk  = l4(#"{"status":"OK_or_HIGHER_RISK","blocked":false}"#)
check(KBLIDetail.shouldShowMoratorium(blocked) == true, "blocked l4 → show moratorium")
check(KBLIDetail.shouldShowMoratorium(openOk) == false, "open l4 → hide moratorium")
check(KBLIDetail.shouldShowMoratorium(nil) == false, "nil l4 → hide moratorium")
check(KBLIDetail.moratoriumText(blocked).contains("2026-05-13"), "moratorium text has effective date")
print("ALL DETAIL TESTS PASSED")

// ─────────────────────────────────────────────────────────────────────────────────────────────
// Window B, 2026-09-13 — absence is a fact about the corpus, and it is rendered as one.
//
// The defect these tests pin: `riskSummary()` ended in `?? "Menengah Rendah"`, so the Risk Level
// row asserted a government risk tier on the 217 records that carry no `per_skala` at all — while
// the Risk Class cell on the SAME card honestly printed "—". Everything derived from the tier
// (licence type, processing mode) inherited the assertion. The cure is the class, not the line:
// one reader (`Theme.RiskTier`) answers for the tier and for everything the decree derives from
// it, and it answers `nil`/`Theme.absent` when the corpus is silent.
// ─────────────────────────────────────────────────────────────────────────────────────────────

func skala(_ scales: [String], _ risk: String?) -> PerSkala {
    let json = """
    {"skala_usaha": \(String(data: try! JSONSerialization.data(withJSONObject: scales), encoding: .utf8)!),
     "kategori_risiko": \(risk.map { "\"\($0)\"" } ?? "null")}
    """
    return try! JSONDecoder().decode(PerSkala.self, from: Data(json.utf8))
}

print("RiskTier — guilt (the tier is stated, so it must be READ):")
check(Theme.RiskTier.category([skala(["Mikro"], "Rendah"), skala(["Besar"], "Menengah Tinggi")]) == "Menengah Tinggi",
      "Besar wins over Mikro (the Medium-Low restaurant trap)")
check(Theme.RiskTier.category([skala(["Mikro"], "Rendah"), skala(["Kecil"], "Tinggi")]) == "Tinggi",
      "no Besar row → the highest tier stated")
check(Theme.RiskTier.summary([skala(["Mikro"], "Rendah"), skala(["Besar"], "Tinggi")], isID: false) == "Low Risk → High Risk",
      "a varying tier is summarised as a range, not collapsed")
check(Theme.RiskTier.summary([skala(["Besar"], "Menengah Rendah")], isID: false) == "Medium-Low Risk", "uniform tier → one label")
check(Theme.RiskTier.summary([skala(["Besar"], "Menengah Rendah")], isID: true) == "Risiko Menengah-Rendah", "…and in Bahasa")
check(Theme.RiskTier.licence([skala(["Besar"], "Tinggi")], isID: false) == "NIB + Permit", "Tinggi → NIB + Permit (Pasal 133)")
check(Theme.RiskTier.licence([skala(["Besar"], "Menengah Rendah")], isID: false) == "NIB + Standard Cert", "Men-Rendah → NIB + SS (Pasal 131)")
check(Theme.RiskTier.licence([skala(["Besar"], "Rendah")], isID: false) == "NIB", "Rendah → bare NIB (Pasal 130)")
check(Theme.RiskTier.processing([skala(["Besar"], "Rendah")], isID: false) == "Automatic", "Rendah → automatic issuance")
check(Theme.RiskTier.abbr("Menengah Tinggi", isID: false) == "MT", "compound abbreviation before the bare one")

print("RiskTier — innocence (the corpus is silent, so NOTHING may be asserted):")
check(Theme.RiskTier.category([]) == nil, "no scales → no tier")
check(Theme.RiskTier.category([skala(["Besar"], nil)]) == nil, "a scale with a null tier states no tier")
check(Theme.RiskTier.category([skala(["Besar"], "")]) == nil, "an empty-string tier states no tier")
check(Theme.RiskTier.summary([], isID: false) == Theme.absent, "silent corpus → the Risk Level row reads —")
check(Theme.RiskTier.summary([], isID: true) == Theme.absent, "…in Bahasa too")
check(Theme.RiskTier.licence([], isID: false) == Theme.absent, "silent corpus → no licence type is derived")
check(Theme.RiskTier.processing([], isID: false) == Theme.absent, "silent corpus → no processing mode is derived")
check(Theme.RiskTier.abbr(nil, isID: false) == Theme.absent, "matrix cell with no tier reads —, not blank")
check(Theme.RiskTier.summary([], isID: false).lowercased().contains("menengah") == false
      && Theme.RiskTier.summary([], isID: false).lowercased().contains("medium") == false,
      "the literal 'Menengah Rendah' default is gone")

// ── the whole dataset, not the single row ────────────────────────────────────────────────────
let uiJSON = ProcessInfo.processInfo.environment["KBLI_JSON"]
    ?? (FileManager.default.currentDirectoryPath + "/Resources/KBLI_2025_FINAL_CLEAN.json")
guard let uiStore = KBLIStore(jsonPath: uiJSON) else {
    print("  ❌ FAIL: store could not load \(uiJSON)"); exit(1)
}
print("Whole-dataset honesty (\(uiStore.all.count) records, \(uiJSON)):")
var silent = 0, stated = 0
var fabricated: [String] = []
var erased: [String] = []
for k in uiStore.all {
    let tier = Theme.RiskTier.category(k.perSkala)
    for isID in [false, true] {
        let summary = Theme.RiskTier.summary(k.perSkala, isID: isID)
        let licence = Theme.RiskTier.licence(k.perSkala, isID: isID)
        let processing = Theme.RiskTier.processing(k.perSkala, isID: isID)
        if tier == nil {
            // GUILT: nothing derived from an absent tier may carry a value.
            if summary != Theme.absent || licence != Theme.absent || processing != Theme.absent {
                fabricated.append("\(k.kode) isID=\(isID): risk=\(summary) licence=\(licence) processing=\(processing)")
            }
        } else {
            // INNOCENCE: a tier that IS stated must still be read, not swallowed by the cure.
            if summary == Theme.absent || licence == Theme.absent || processing == Theme.absent {
                erased.append("\(k.kode) isID=\(isID): tier=\(tier!) risk=\(summary) licence=\(licence) processing=\(processing)")
            }
        }
    }
    if tier == nil { silent += 1 } else { stated += 1 }
}
check(fabricated.isEmpty, "no record with an absent risk tier renders a risk, a licence or a processing mode"
      + (fabricated.isEmpty ? "" : " — first offender: \(fabricated[0]) (+\(fabricated.count - 1) more)"))
check(erased.isEmpty, "every record that STATES a tier still renders risk, licence and processing"
      + (erased.isEmpty ? "" : " — first: \(erased[0]) (+\(erased.count - 1) more)"))
check(silent == 217, "exactly 217 records carry no risk tier (measured on this corpus: \(silent))")
check(stated == uiStore.all.count - 217, "the other \(uiStore.all.count - 217) do (got \(stated))")

// Uncertainty attaches to the axis that is uncertain: a record with no risk tier can still be a
// settled closure, and the risk cure must not touch that. (The BANNER's third state is window A's
// verdict type and is NOT tested here — see docs/gates/2026-09-13-window-b/README.md.)
let closedWithNoTier = uiStore.all.filter { Theme.RiskTier.category($0.perSkala) == nil && $0.l4Bali?.blocked == true }
check(closedWithNoTier.isEmpty == false, "some codes are Bali-blocked AND carry no risk tier (\(closedWithNoTier.count))")
check(closedWithNoTier.allSatisfy { $0.l4Bali?.blocked == true },
      "…and every one of them is still blocked after the risk cure — an absent tier erases no closure")

// ── every list cap is an ACTION, and there are no others ─────────────────────────────────────
// A `.prefix(N)` on a collection silently drops rows; on a String it takes characters, which is a
// different operation (a 2-digit section code, a 2-letter scale badge, an ellipsised label). The
// scan is written as an ENTITY rule, not a substring ban, and it is exercised on fixtures in both
// directions below so an over-matching or under-matching scanner fails here rather than in review.
func truncationOffenders(in source: String) -> [Int] {
    var out: [Int] = []
    for (i, raw) in source.split(separator: "\n", omittingEmptySubsequences: false).enumerated() {
        let line = String(raw)
        // Drop the trailing comment. `split(separator: "/")` was wrong here and the fixture below
        // caught it: it omits empty subsequences, so a line that STARTS with "//" kept its comment.
        let code = line.components(separatedBy: "//").first ?? line
        guard code.contains(".prefix(") else { continue }
        if code.contains(".prefix(while:") { continue }                        // a predicate, not a cap
        if code.contains("String(") || code.contains("Int(") { continue }      // characters, not rows
        out.append(i + 1)
    }
    return out
}
print("Truncation scan — the scanner itself, both directions:")
check(truncationOffenders(in: "ForEach(Array(items.prefix(8).enumerated()))") == [1], "guilt: a capped list is caught")
check(truncationOffenders(in: "let n = Int(code.prefix(2))").isEmpty, "innocence: Int(code.prefix(2)) is a 2-digit section")
check(truncationOffenders(in: "Text(String(scale.prefix(2)))").isEmpty, "innocence: String(scale.prefix(2)) is a badge")
check(truncationOffenders(in: "let num = String(t.prefix(while: { $0.isNumber }))").isEmpty, "innocence: prefix(while:) is a predicate")
check(truncationOffenders(in: "// ForEach(Array(x.prefix(3)))").isEmpty, "innocence: a commented-out cap is not code")
check(truncationOffenders(in: "a\nb\nrows.prefix(4)\nc") == [3], "guilt: the offending LINE is reported")

let sourcesDir = ProcessInfo.processInfo.environment["KBLI_SOURCES"]
    ?? (FileManager.default.currentDirectoryPath + "/Sources")
let viewsDir = sourcesDir + "/Views"
var scanned = 0
var caps: [String] = []
for file in ((try? FileManager.default.contentsOfDirectory(atPath: viewsDir)) ?? []).sorted() where file.hasSuffix(".swift") {
    guard let text = try? String(contentsOfFile: viewsDir + "/" + file, encoding: .utf8) else { continue }
    scanned += 1
    for line in truncationOffenders(in: text) { caps.append("\(file):\(line)") }
}
// Theme.swift too: `ExpandableList` is the ONE place a cap is allowed to live, and it uses a
// range, not `.prefix` — so the rule is absolute here as well and needs no named exception.
if let themeText = try? String(contentsOfFile: sourcesDir + "/Theme.swift", encoding: .utf8) {
    scanned += 1
    for line in truncationOffenders(in: themeText) { caps.append("Theme.swift:\(line)") }
}
check(scanned >= 9, "scanned the view layer (\(scanned) files under \(sourcesDir))")
check(caps.isEmpty, "no silent list cap remains in the view layer" + (caps.isEmpty ? "" : " — found: \(caps.joined(separator: ", "))"))
print("ALL WINDOW-B HONESTY TESTS PASSED (\(uiStore.all.count) records · \(silent) silent · \(scanned) files scanned)")
