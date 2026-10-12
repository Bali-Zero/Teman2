import Foundation

// Standalone test for Models + KBLIStore. Compiled with the Sources it tests:
//   swiftc Sources/Models.swift Sources/KBLIStore.swift Tests/storetest/main.swift -o /tmp/storetest && /tmp/storetest
// Loads the JSON from the repo Resources/ via an env var (build-independent).

func assert(_ cond: Bool, _ msg: String) {
    if cond { print("  ✅ \(msg)") }
    else { print("  ❌ FAIL: \(msg)"); exit(1) }
}

let resourcePath = ProcessInfo.processInfo.environment["KBLI_JSON"]
    ?? (FileManager.default.currentDirectoryPath + "/Resources/KBLI_2025_FINAL_CLEAN.json")

guard let store = KBLIStore(jsonPath: resourcePath) else {
    print("  ❌ FAIL: store could not load \(resourcePath)"); exit(1)
}

print("KBLIStore tests:")
assert(store.all.count == 1559, "loads 1559 records (got \(store.all.count))")

let villa = store.code("55203")
assert(villa != nil, "code(55203) found")
assert(villa?.judul.lowercased().contains("vila") == true, "55203 judul mentions vila (got \(villa?.judul ?? "nil"))")
assert(villa?.l4Bali?.status == "CHIUSO_PMA_NO_BESAR", "55203 l4_bali.status == CHIUSO_PMA_NO_BESAR (got \(villa?.l4Bali?.status ?? "nil"))")
assert(villa?.l4Bali?.blocked == true, "55203 l4_bali.blocked == true")
// "third week of May 2026", not "2026-05-13": nuzantara commit eaa5a69cf8577581106f77738cbe4e80
// bcf2ec16 ("fix(kbli): Bali 'blocked' now means the closure Bali actually applied — 17 open
// codes closed, ~387 tier-only blocks lifted to 'verify on OSS' (W-J B1, PR-D) (#6597)") rewrote
// every record's `l4_bali.moratorium.effective` from the precise ISO date to this vaguer phrase
// as part of the same applied-closure pass that produced ATTENZIONE_FASCIA_BALI (see
// KBLIVerdict.swift) — corroborated: this session's `git log -S"2026-05-13"` on the canonical
// dataset names the SAME commit as the one removing that string's occurrences.
assert(villa?.l4Bali?.moratorium?.effective == "third week of May 2026",
       "55203 moratorium effective 'third week of May 2026' (got \(villa?.l4Bali?.moratorium?.effective ?? "nil"))")
assert(villa?.perSkala.isEmpty == false, "55203 has per_skala entries")

print("Search ranking tests:")
let exact = store.search("55203")
assert(exact.rows.first?.kode == "55203", "search '55203' ranks exact code first (got \(exact.rows.first?.kode ?? "nil"))")

let byName = store.search("villa")
assert(byName.rows.contains { $0.kode == "55203" }, "search 'villa' includes 55203 (fuzzy vila)")

// prefix-code beats substring: searching "552" should surface 552xx codes near the top
let prefix = store.search("552")
assert(prefix.rows.first?.kode.hasPrefix("552") == true, "search '552' ranks a 552xx code first (got \(prefix.rows.first?.kode ?? "nil"))")

// truncation honesty: a broad query reports total > rows and truncated == true
let broad = store.search("a")
assert(broad.total == 1559, "search 'a' reports true total 1559 (got \(broad.total))")
assert(broad.truncated == true, "search 'a' flags truncated")
assert(broad.rows.count <= KBLIStore.displayCap, "search 'a' caps rows at \(KBLIStore.displayCap) (got \(broad.rows.count))")
// narrow query: not truncated
let narrow = store.search("55203")
assert(narrow.truncated == false, "search '55203' not truncated")

assert(KBLIStore.normalize("villa") == KBLIStore.normalize("vila"), "normalize villa==vila")
assert(store.search("vila").rows.contains { $0.kode == "55203" }, "search vila finds 55203")
assert(store.search("villa").rows.contains { $0.kode == "55203" }, "search villa finds 55203 fuzzy")

print("ALL STORE TESTS PASSED (\(store.all.count) records)")
