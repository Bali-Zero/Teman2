import Foundation
import CryptoKit

// Tests/rowidentitytest — the APP half of docs/gates/ROW-IDENTITY-CONTRACT.md.
//
// The contract is one text in two repos, and this suite is the reason to believe that. It reads
// the SAME golden fixture the monorepo reads (byte-identical file, sha256 pinned below), computes
// the two digests §7 defines, and compares them to the SAME literals
// `scripts/tests/test_row_identity.py` compares to. Two implementations of one rule that agree on
// a literal are evidence; two implementations that were merely written on the same day are not.
//
// Run from the app root:
//   swiftc -sdk $(xcrun --sdk macosx --show-sdk-path) -target arm64-apple-macosx14.0 \
//     <plugin flags> -framework SwiftUI -framework AppKit -framework Combine -framework PDFKit \
//     -o /tmp/kbli-suite-rowidentity $(find Sources -name '*.swift' ! -name 'KBLINavigatorApp.swift') \
//     Tests/rowidentitytest/main.swift && /tmp/kbli-suite-rowidentity

func ck(_ c: Bool, _ m: String) { if c { print("  ✅ \(m)") } else { print("  ❌ FAIL: \(m)"); exit(1) } }

// §7 — the three literals. `scripts/tests/test_row_identity.py` carries the same three, and
// ROW-IDENTITY-CONTRACT.md §7 (identical text in both repos) writes them down once.
let GOLDEN_FILE_SHA256 = "12a13ec3fd14a02c5e995081b1edaee4f3cfc50402c984d0901e88538b2cb6f5"
let GOLDEN_CANONICAL_ROW_DIGEST = "a89b828db9a445b0dcb3de35ec9d6c59f174466a583d1a236a374a1aaf9d7e18"
let GOLDEN_SERVED_ROW_DIGEST = "2bda305c4535af4b35777cac64a608200d73d951b8044d69eec6a23799b6c130"

func sha256Hex(_ data: Data) -> String {
    SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
}

/// §7 — sha256 of "\n".join("code|skala_key|ordinal"), UTF-8, NO trailing newline. A string join
/// and not a JSON dump, precisely so two languages can be made to agree on it.
func identityDigest(_ ids: [(String, String, Int)]) -> String {
    let line = ids.map { "\($0.0)|\($0.1)|\($0.2)" }.joined(separator: "\n")
    return sha256Hex(Data(line.utf8))
}

let fixturePath = "Tests/fixtures/row_identity_golden.json"
guard let fixtureData = FileManager.default.contents(atPath: fixturePath) else {
    print("  ❌ FAIL: cannot read \(fixturePath) (run the suite from the app root)"); exit(1)
}

print("The shared golden fixture is the SAME file in both repos (§7):")
ck(sha256Hex(fixtureData) == GOLDEN_FILE_SHA256,
   "fixture file sha256 matches the contract literal (got \(sha256Hex(fixtureData)))")

guard let root = (try? JSONSerialization.jsonObject(with: fixtureData)) as? [String: Any],
      let records = root["records"] as? [[String: Any]],
      let packageFields = root["package_fields"] as? [String: Any],
      let expected = root["expected"] as? [String: Any] else {
    print("  ❌ FAIL: the fixture does not have the shape the contract declares"); exit(1)
}
ck(records.count == 2, "the fixture carries its two records (got \(records.count))")

// ─────────────────────────────────────────────────────────────────────────────────────────
print("§2/§3 — canonical order and skala_key, computed here and compared to the literal:")
var canonical: [(String, String, Int)] = []
for record in records {
    let code = (record["kode_kbli_2025"] as? String) ?? ""
    let rows = (record["per_skala"] as? [[String: Any]]) ?? []
    for (ordinal, row) in rows.enumerated() { canonical.append((code, kbliSkalaKey(row), ordinal)) }
}
let canonicalDigest = identityDigest(canonical)
ck(canonicalDigest == GOLDEN_CANONICAL_ROW_DIGEST,
   "canonical row digest matches the contract literal (got \(canonicalDigest))")
ck(canonicalDigest == (expected["canonical_row_digest"] as? String ?? ""),
   "canonical row digest matches the value the fixture itself declares")

// The keys one by one, so a digest that happened to collide would still not hide a wrong key.
if let expectedKeys = expected["skala_keys"] as? [String: [String]] {
    for record in records {
        let code = (record["kode_kbli_2025"] as? String) ?? ""
        let rows = (record["per_skala"] as? [[String: Any]]) ?? []
        ck(rows.map { kbliSkalaKey($0) } == (expectedKeys[code] ?? []),
           "\(code): every skala_key matches the fixture, item by item")
    }
} else { ck(false, "the fixture declares its skala_keys") }

// ─────────────────────────────────────────────────────────────────────────────────────────
print("§4 — the declaration names a SET and an ORDER, and the count IS the served count:")
var served: [(String, String, Int)] = []
for record in records {
    let code = (record["kode_kbli_2025"] as? String) ?? ""
    let rows = (record["per_skala"] as? [[String: Any]]) ?? []
    guard let spec = packageFields[code] as? [String: Any],
          let servedRows = spec["per_skala_rows_served"] as? [[String: Any]] else {
        ck(false, "\(code): the fixture declares an enumeration"); exit(1)
    }
    ck((spec["per_skala_rows_included"] as? Int) == servedRows.count,
       "\(code): per_skala_rows_included IS the number of enumerated rows")
    ck((spec["per_skala_rows_total"] as? Int) == rows.count,
       "\(code): per_skala_rows_total IS the record's row count")
    var seen = Set<Int>()
    for entry in servedRows {
        guard let ordinal = entry["ordinal"] as? Int else { ck(false, "\(code): an ordinal is an integer"); exit(1) }
        ck(ordinal >= 0 && ordinal < rows.count, "\(code): ordinal \(ordinal) is inside the record")
        ck(seen.insert(ordinal).inserted, "\(code): ordinal \(ordinal) is declared once")
        let key = kbliSkalaKey(rows[ordinal])
        ck((entry["skala_key"] as? String) == key,
           "\(code): the declared skala_key names the canonical row at ordinal \(ordinal)")
        // §4 — both served lengths are REQUIRED and are integers. Never nullable: a nil Optional
        // is omitted by Swift's encoder and written as null by Python's, and the scorer must not
        // have to guess which of "the whole list" and "the runner forgot" it is reading.
        for field in ["persyaratan", "kewajiban"] {
            guard let n = entry["\(field)_served"] as? Int else {
                ck(false, "\(code): ordinal \(ordinal) declares \(field)_served as an integer"); exit(1)
            }
            let canonicalList = (rows[ordinal][field] as? [String] ?? [])
            ck(n >= 0 && n <= canonicalList.count,
               "\(code): ordinal \(ordinal) \(field)_served \(n) is within 0...\(canonicalList.count)")
        }
        served.append((code, key, ordinal))
    }
}
let servedDigest = identityDigest(served)
ck(servedDigest == GOLDEN_SERVED_ROW_DIGEST,
   "served row digest matches the contract literal (got \(servedDigest))")
ck(servedDigest == (expected["served_row_digest"] as? String ?? ""),
   "served row digest matches the value the fixture itself declares")

// GUILT: the fixture would certify nothing if its served rows happened to be the first N — the
// whole defect is that they are not.
if let ordinals = expected["served_ordinals"] as? [String: [Int]] {
    ck(ordinals["99001"] == [4, 5, 6, 7], "the fixture's served ordinals are NOT a prefix")
    for (code, expectedOrdinals) in ordinals {
        let spec = packageFields[code] as? [String: Any] ?? [:]
        let rows = (spec["per_skala_rows_served"] as? [[String: Any]]) ?? []
        ck(rows.compactMap { $0["ordinal"] as? Int } == expectedOrdinals,
           "\(code): the enumeration is in SERVED order, as the fixture declares")
    }
} else { ck(false, "the fixture declares its served ordinals") }

// ─────────────────────────────────────────────────────────────────────────────────────────
print("§3 — the normalisation, case by case (the same table the Python half parametrises):")
ck(kbliSkalaKey(["skala_usaha": ["Usaha Besar"]]) == "usaha besar", "a single scale lowercases")
ck(kbliSkalaKey(["skala_usaha": ["Usaha  MENENGAH", "Usaha Besar"]]) == "usaha menengah+usaha besar",
   "a multi-scale row joins with '+' and collapses inner whitespace")
ck(kbliSkalaKey(["skala_usaha": ["  Usaha\tKecil \n"]]) == "usaha kecil", "the ends are stripped")
ck(kbliSkalaKey(["skala_usaha": "Usaha Mikro"]) == "usaha mikro", "a scalar is accepted, not parsed")
ck(kbliSkalaKey(["skala_usaha": [String]()]) == "-", "an empty array is the declared empty key")
ck(kbliSkalaKey(["skala_usaha": ["   "]]) == "-", "a whitespace-only scale is the empty key")
ck(kbliSkalaKey([:]) == "-", "an absent field is the empty key")
ck(kbliSkalaKey(["skala_usaha": ["Ｕｓａｈａ Besar"]]) == "usaha besar",
   "NFKC folds a compatibility spelling to the same key")
// §3, council round 1 finding 6: STRINGS ONLY. A coercion would be language-dependent — Swift
// writes `true` where Python writes `True` — so an unformable label is `-` in both.
ck(kbliSkalaKey(["skala_usaha": [1, "Besar"]]) == "-", "a non-string element yields the empty key")
ck(kbliSkalaKey(["skala_usaha": ["a": 1]]) == "-", "an object yields the empty key")
ck(kbliSkalaKey(["skala_usaha": [["Besar"]]]) == "-", "a nested array yields the empty key")

// ─────────────────────────────────────────────────────────────────────────────────────────
print("The digest is order-sensitive (served ORDER is part of what is declared):")
let a: [(String, String, Int)] = [("99001", "a", 0), ("99001", "b", 1)]
ck(identityDigest(a) != identityDigest(a.reversed()), "reversing the identities changes the digest")
ck(identityDigest([]) == sha256Hex(Data()), "the digest of nothing is the digest of the empty string")

print("ALL ROW-IDENTITY TESTS PASSED")
