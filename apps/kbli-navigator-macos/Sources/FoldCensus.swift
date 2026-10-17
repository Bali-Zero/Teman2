import SwiftUI
import AppKit

/// The verdict-fold census (#8492 gate, bindings 1-2): every code, in each language, on the real `RootView` with its sidebar and a
/// code selected, collapsed, at each window size; one JSON line per render with the census frames the band's fold is read against.
/// `<app> --fold-census <out.jsonl> [--lang en|id] [--sidebar 200..300] [--open] [--sizes 1040x700,1180x800] [--codes all|a,b] [--theme day|night]`.
/// One process and one hosting view per (language, size): a code's state change relays the whole window out, as a click does.
/// Frames only, as `CensusFrame` says: the numbers a reader of `png_census.py` C27 would take from a PNG, for all 1,559 codes.
enum FoldCensus {
    @MainActor
    static func run() {
        let args = CommandLine.arguments
        func flag(_ name: String) -> String? {
            guard let i = args.firstIndex(of: name), args.count > i + 1 else { return nil }
            return args[i + 1]
        }
        guard let i = args.firstIndex(of: "--fold-census"), args.count > i + 1 else {
            FileHandle.standardError.write("--fold-census requires an <out.jsonl>\n".data(using: .utf8)!); return
        }
        let out = args[i + 1]
        let langs = (flag("--lang") ?? "en,id").split(separator: ",").map(String.init)
        let sizes: [CGSize] = (flag("--sizes") ?? "1040x700,1180x800").split(separator: ",").compactMap {
            let p = $0.split(separator: "x").compactMap { Double($0) }
            return p.count == 2 ? CGSize(width: p[0], height: p[1]) : nil
        }
        let theme = (flag("--theme") ?? "day").lowercased()
        let sidebar = Double(flag("--sidebar") ?? "") ?? 232
        if sidebar != 232 { setenv("KBLI_CENSUS_SIDEBAR", String(Int(sidebar)), 1) }   // RootView.sidebarIdeal, a collecting run only
        let open = args.contains("--open")   // the sheet expanded (E6: it is never shorter than the collapsed one); each row says `open`
        Theme.mode = theme == "day" ? .light : .dark
        UserDefaults.pinThemeOverride(Theme.mode)   // RootView syncs its theme from the override and the system: pin the one the census names
        CensusFrame.collecting = true
        Motion.frozenMs = Motion.total * 1000   // every motion at its end: the frames are the final ones

        let state = AppState()
        let all = state.store.all
        let codes: [KBLI] = {
            guard let only = flag("--codes"), only != "all" else { return all }
            let want = Set(only.split(separator: ",").map(String.init))
            return all.filter { want.contains($0.kode) }
        }()
        FileManager.default.createFile(atPath: out, contents: nil)
        guard let sink = FileHandle(forWritingAtPath: out) else { return }

        final class Marks { var frames: [CensusFrame] = [] }
        for l in langs {
            for size in sizes {
                let lang = LanguageManager()
                lang.lang = l == "id" ? .id : .en
                let marks = Marks()
                state.selected = nil
                let root = RootView().environmentObject(state).environmentObject(lang).environmentObject(ThemeManager(Theme.mode))
                    .environment(\.dynamicTypeSize, .large)
                    .frame(width: size.width, height: size.height, alignment: .top)
                    .background(Theme.antracite)
                    .clipped()
                    .coordinateSpace(name: CensusFrame.space)
                    .onPreferenceChange(CensusFramesKey.self) { marks.frames = $0 }
                let host = NSHostingView(rootView: AnyView(root))
                host.frame = NSRect(origin: .zero, size: size)
                CensusWindow.attach(host, size: size)
                guard let rep = host.bitmapImageRepForCachingDisplay(in: host.bounds) else { continue }
                func settle() -> [String: [Double]] {
                    // A preference read into @State lays the window out once more, a turn of the run loop later: settled is the same frames
                    // eight turns running (the list's scroll passes run in 15 ms steps), never two (a loaded machine skips a turn).
                    var last = "", same = 0
                    for _ in 0..<40 {
                        RunLoop.current.run(until: Date().addingTimeInterval(0.02))
                        host.layoutSubtreeIfNeeded()
                        host.cacheDisplay(in: host.bounds, to: rep)
                        let now = marks.frames.map { "\($0.name):\($0.rect)" }.sorted().joined(separator: "|")
                        same = now == last ? same + 1 : 0
                        if same >= 8 { break }
                        last = now
                    }
                    var f: [String: [Double]] = [:]
                    for m in marks.frames where f[m.name] == nil {
                        f[m.name] = [m.rect.minX, m.rect.minY, m.rect.width, m.rect.height].map { Double($0) }
                    }
                    return f
                }
                _ = settle()
                // The first selection of a fresh window takes more turns of the run loop than any later one (the table, the fonts): two warm-up
                // rounds, so the first code of the run is measured as settled as the last. fold_census.py FAILs a row that is not (`unsettled`).
                for _ in 0..<2 {
                    if let k = codes.first { state.browsedSector = KBLIStore.sectorLetter(for: k.kode) ?? "A"; state.selected = k; _ = settle(); state.selected = nil; _ = settle() }
                }
                for k in codes {
                    state.browsedSector = KBLIStore.sectorLetter(for: k.kode) ?? "A"
                    state.selected = k
                    var f = settle()
                    if open { state.censusExpand = true; f = settle() }
                    var row: [String: Any] = ["code": k.kode, "lang": l, "w": Double(size.width), "h": Double(size.height), "frames": f, "open": open, "sidebar": sidebar]
                    if f["sheet"] == nil || (!open && f["band"] == nil) { row["miss"] = true }
                    if let d = try? JSONSerialization.data(withJSONObject: row, options: [.sortedKeys]) {
                        sink.write(d); sink.write("\n".data(using: .utf8)!)
                    }
                    state.censusExpand = false
                    state.selected = nil
                    _ = settle()
                }
                CensusWindow.closeAll()
                FileHandle.standardError.write("fold-census \(l) \(Int(size.width))x\(Int(size.height)): \(codes.count) codes\n".data(using: .utf8)!)
            }
        }
        try? sink.close()
    }
}
