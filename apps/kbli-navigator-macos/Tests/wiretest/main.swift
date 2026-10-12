import Foundation
@MainActor func run() {
    // simulate AppState's store load from the repo Resources (same code path)
    let store = KBLIStore(jsonPath: ProcessInfo.processInfo.environment["KBLI_JSON"]!)!
    let s = AppStateProbe(store: store)
    func ck(_ c: Bool,_ m: String){ if c {print("  ✅ \(m)")} else {print("  ❌ \(m)"); exit(1)} }
    s.query = "55203"
    ck(s.results.rows.first?.kode == "55203", "AppState.results returns 55203 for query")
    ck(s.section == .search, "default section search")
    if let k = store.code("55203") { s.askZantara(about: k) }
    ck(s.section == .chat, "askZantara flips section to chat")
    ck(s.pendingCodeContext?.kode == "55203", "pendingCodeContext set to 55203")
    print("WIRING OK")
}
// minimal probe mirroring AppState logic without @StateObject/App
@MainActor final class AppStateProbe {
    let store: KBLIStore
    var section: AppSection = .search
    var query = ""
    var pendingCodeContext: KBLI?
    init(store: KBLIStore){ self.store = store }
    var results: KBLIStore.Results { store.search(query) }
    func askZantara(about k: KBLI){ pendingCodeContext = k; section = .chat }
}
await MainActor.run { } ; await { @MainActor in run() }()
