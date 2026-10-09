import Foundation

// Tests/contenttest — prints, for each frozen code and language, the strings the views produce
// (same functions, no literal copies), as ONE JSON object for Tools/design/content_check.py.
// Diagnostics go to stderr; stdout carries nothing but the JSON.

func err(_ s: String) { FileHandle.standardError.write(Data((s + "\n").utf8)) }

guard let jsonPath = ProcessInfo.processInfo.environment["KBLI_JSON"],
      let store = KBLIStore(jsonPath: jsonPath) else {
    err("set KBLI_JSON to the bundled dataset path"); exit(2)
}
let appRoot = ProcessInfo.processInfo.environment["KBLI_APP_ROOT"] ?? FileManager.default.currentDirectoryPath
let frozenCodes = ["55203", "51101", "56101"]
let viewFiles = ["SearchListView", "KBLIRegistryTable", "KBLIDetailRichView",
                 "KBLIDossierView", "KBLIRegistryView", "ChatView"]

let out: [String: Any] = MainActor.assumeIsolated {
    var codes: [String: Any] = [:]
    var rejoin: [String: Bool] = [:]
    var frozenStrings: [String] = []   // the output strings the probe looks for in the views

    for code in frozenCodes {
        guard let k = store.all.first(where: { $0.kode == code }) else { err("missing \(code)"); exit(2) }
        var entry: [String: Any] = [
            "verdict": k.pmaStatus.map { $0 as Any } ?? NSNull(),
            "cap": k.pmaMaxAsing.map { String($0) as Any } ?? NSNull(),
            "basis": k.pmaOfficialBasis.map { $0 as Any } ?? NSNull(),
            "bali_status": k.l4Bali.map { $0.status as Any } ?? NSNull(),
        ]
        if let b = k.pmaOfficialBasis {
            rejoin[code] = BalancedColumns.split(b, into: 4).joined(separator: " ") == b
            frozenStrings.append(b)
        }
        for isID in [false, true] {
            let title = OverlayStore.shared.primaryTitle(k, isID: isID)
            let reason = OverlayStore.shared.displayReason(k.l4Bali?.reason ?? "", isID: isID)
            let hu = KBLIVerdict.headsUp(record: k, isID: isID)
            let rows: [[String: Any]] = k.perSkala.map { r in
                ["authority": r.kewenanganLevels,
                 "permits": r.perizinanList,
                 "risk": r.kategoriRisiko.map { $0 as Any } ?? NSNull(),
                 "scale": r.skalaUsaha,
                 "term": r.jangkaWaktu.map { $0 as Any } ?? NSNull()]
            }
            entry[isID ? "id" : "en"] = [
                "title": title,
                "bali_reason": reason,
                "heads_up": [hu.label, hu.sentence.map { $0 as Any } ?? NSNull()],
                "rows": rows,
            ] as [String: Any]
            frozenStrings.append(title)
            frozenStrings.append(reason)
            if let s = hu.sentence { frozenStrings.append(s) }
        }
        codes[code] = entry
    }

    var violations: [String] = []
    let needles = Set(frozenStrings.filter { $0.count >= 16 })
    for name in viewFiles {
        let path = "\(appRoot)/Sources/Views/\(name).swift"
        guard let src = try? String(contentsOfFile: path, encoding: .utf8) else {
            err("probe: cannot read \(path)"); continue
        }
        for n in needles.sorted() where src.contains(n) {
            violations.append("\(name).swift contains a literal copy: \(n.prefix(60))")
        }
    }
    // Each redesigned view must still ask the canonical functions (append one line per view).
    let mustCall: [String: [String]] = [
        "Sources/Views/SearchListView.swift": ["KBLIVerdict.headsUp(", "primaryTitle("],
    ]
    for (file, calls) in mustCall.sorted(by: { $0.key < $1.key }) {
        guard let src = try? String(contentsOfFile: "\(appRoot)/\(file)", encoding: .utf8) else {
            err("probe: cannot read \(file)"); continue
        }
        for call in calls where !src.contains(call) {
            violations.append("\(file) lacks the required call \(call)")
        }
    }
    return ["codes": codes, "balanced_rejoin": rejoin, "probe_violations": violations]
}

guard let data = try? JSONSerialization.data(withJSONObject: out,
                                             options: [.sortedKeys, .withoutEscapingSlashes]),
      let text = String(data: data, encoding: .utf8) else { err("serialization failed"); exit(2) }
print(text)
