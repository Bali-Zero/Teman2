import AppKit
import PDFKit
import SwiftUI

// Tests/encensus — the text census of the en-purity gate (Q12, Tools/design/en_purity.py).
// `encensus <out.jsonl> [--lang en|id] [--mode fast|full] [--codes a,b] [--views v1,v2]` renders each View a
// code reaches through ImageRenderer into a PDF context and writes the text PDFKit reads back: what is DRAWN,
// accessibility-hidden labels included. ImageRenderer leaves out what AppKit draws (a text field's placeholder,
// a pop-up's title), so the chromes and the search field also host the View once and read those controls.
// One JSON line per (code, view): {"code","view","text","anchors"}. The anchors (Q19) are what the View must draw —
// its code, and the last thing it draws — so a dump that holds them is the whole View: a View whose text sits in a
// ScrollView ImageRenderer leaves unexpanded reads INCOMPLETE, never 0. Two probes prove it on every run: the same
// text in a ScrollView (INCOMPLETE) and plain (complete). `fast` is the three frozen codes plus a stratified sample
// (every heads-up class, sector, Bali status and LabelBook branch, and every 26th record); `full` is all 1,559;
// `--codes none` dumps the chromes only. The dataset comes from the bundle path, as in the app.

func err(_ s: String) { FileHandle.standardError.write(Data((s + "\n").utf8)) }

let args = CommandLine.arguments
guard args.count > 1 else { err("usage: encensus <out.jsonl> [--lang en|id] [--mode fast|full] [--codes …] [--views …]"); exit(2) }
func flag(_ name: String) -> String? {
    guard let j = args.firstIndex(of: name), args.count > j + 1 else { return nil }
    return args[j + 1]
}
let views = flag("--views").map { Set($0.split(separator: ",").map(String.init)) }
_ = NSApplication.shared

@MainActor func pdfText(_ v: AnyView, height: CGFloat?) -> String {
    let framed = height.map { AnyView(v.frame(width: 1280, height: $0, alignment: .top)) }
        ?? AnyView(v.frame(width: 1280, alignment: .top).fixedSize(horizontal: false, vertical: true))
    // A hair of tracking keeps PDFKit from splitting words at ligatures ("permied" for "permitted").
    let r = ImageRenderer(content: framed.tracking(0.01).background(Theme.antracite))
    let data = NSMutableData()
    r.render { size, draw in
        var box = CGRect(origin: .zero, size: size)
        guard let consumer = CGDataConsumer(data: data as CFMutableData),
              let ctx = CGContext(consumer: consumer, mediaBox: &box, nil) else { return }
        ctx.beginPDFPage(nil); draw(ctx); ctx.endPDFPage(); ctx.closePDF()
    }
    return PDFDocument(data: data as Data)?.string ?? ""
}

/// SearchFieldBar with the focus binding RootView gives it, as Snapshot's SearchResultsBand does.
struct FieldBand: View {
    @FocusState private var focus: RootFocus?
    var body: some View { SearchFieldBar(focusedField: $focus) {} }
}

/// The strings AppKit draws inside a hosted SwiftUI View: a text field's value, or its placeholder when empty;
/// a button's title; a pop-up's selected item. The controls exist once the host has drawn, as in Snapshot.
@MainActor func appKitText(_ v: AnyView, height: CGFloat) -> [String] {
    let host = NSHostingView(rootView: v.frame(width: 1280, height: height, alignment: .top))
    host.frame = NSRect(x: 0, y: 0, width: 1280, height: height)
    if let rep = host.bitmapImageRepForCachingDisplay(in: host.bounds) { host.cacheDisplay(in: host.bounds, to: rep) }
    var out: [String] = []
    func walk(_ view: NSView) {
        if let p = view as? NSPopUpButton { out.append(p.titleOfSelectedItem ?? "") }
        else if let b = view as? NSButton { out.append(b.title) }
        else if let f = view as? NSTextField { out.append(f.stringValue.isEmpty ? f.placeholderString ?? "" : f.stringValue) }
        view.subviews.forEach(walk)
    }
    walk(host)
    return out.filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }
}

let rc: Int32 = MainActor.assumeIsolated {
    let state = AppState()
    guard state.store.all.count == 1559 else { err("dataset not found next to the binary"); return 2 }
    let lang = LanguageManager()
    lang.lang = (flag("--lang") ?? "en") == "id" ? .id : .en
    let isID = lang.lang == .id
    Theme.mode = .light
    let all = state.store.all
    var pick: Set<String>
    if let only = flag("--codes") {
        pick = Set(only.split(separator: ",").map(String.init))
    } else if (flag("--mode") ?? "fast") == "full" {
        pick = Set(all.map(\.kode))
    } else {
        pick = ["55203", "51101", "56101"]
        var perClass: [Int: Int] = [:], sectors = Set<String>(), bali = Set<String>(), taken = Set<String>()
        for (i, k) in all.enumerated() {
            let c = KBLIVerdict.of(record: k).headsUpClass
            if perClass[c, default: 0] < 3 { perClass[c, default: 0] += 1; pick.insert(k.kode) }
            if let s = KBLIStore.sectorLetter(for: k.kode), sectors.insert(s).inserted { pick.insert(k.kode) }
            if let b = k.l4Bali?.status, bali.insert(b).inserted { pick.insert(k.kode) }
            // one code per branch a LabelBook map takes on this record (#8227 gate (v): 02101/03120's cap not verified;
            // the EN-1c gate (d): 02102, whose Bali reason holds a record key humanise draws as its field label)
            let branches = ["pma:\(k.pmaStatus ?? "∅")", "cap:\(k.pmaMaxAsing.map { $0 == 0 || $0 == 100 ? "\($0)" : "x" } ?? "∅")",
                            "verified:\(k.pmaCapVerified.map(String.init) ?? "∅")", "special:\(k.pmaCapSpecial ?? false)",
                            "route:\(k.pmaRouteTo != nil)", "bali:\(k.l4Bali != nil)", "conf:\(k.l4Bali?.confidence ?? "∅")",
                            "blocked:\(k.l4Bali?.blocked ?? false)", "moratorium:\(k.l4Bali?.moratorium != nil)",
                            "reason-key:\(LabelBook.fieldNames.keys.contains { k.l4Bali?.reason?.contains($0) == true })"]
                + k.perSkala.flatMap { r in ["risk:\(r.kategoriRisiko ?? "∅")", "auth:\(r.kewenangan ?? "∅")"]
                    + r.skalaUsaha.map { "scale:\($0)" } }
            if branches.contains(where: { taken.insert($0).inserted }) { pick.insert(k.kode) }
            if i % 26 == 0 { pick.insert(k.kode) }
        }
    }
    FileManager.default.createFile(atPath: args[1], contents: nil)
    guard let fh = FileHandle(forWritingAtPath: args[1]) else { err("cannot write \(args[1])"); return 2 }
    @MainActor func emit(_ code: String, _ view: String, _ v: some View, height: CGFloat? = nil, anchors: [String] = []) {
        if let views, !views.contains(view), !view.hasPrefix("probe-") { return }
        let hosted = AnyView(v.environmentObject(state).environmentObject(lang))
        var text = pdfText(hosted, height: height)
        if code == "-" { text += "\n" + appKitText(hosted, height: height ?? 800).joined(separator: "\n") }
        if let d = try? JSONSerialization.data(withJSONObject: ["code": code, "view": view, "text": text, "anchors": anchors],
                                               options: [.sortedKeys]) {
            fh.write(d); fh.write(Data("\n".utf8))
        }
    }
    let probe = "Census anchor probe, drawn whole"
    emit("-", "probe-scrollview", ScrollView { Text(probe) }, height: 200, anchors: [probe])
    emit("-", "probe-plain", Text(probe), height: 200, anchors: [probe])
    // The chrome, once: the registry browsing a sector, and the search pane with a query, no code open. Its rows sit
    // in a ScrollView, so they are censused per code below as registry-row, search-row and search-peak (#8227 (vi)).
    state.selected = nil
    state.browsedSector = "I"
    let sector = isID ? "SEKTOR" : "SECTOR"
    emit("-", "registry-chrome", SearchListView(), height: 800, anchors: [sector])
    state.browsedSector = nil
    state.query = "55203"
    emit("-", "search-chrome", SearchListView(), height: 800, anchors: [sector])
    state.query = ""
    emit("-", "search-field", FieldBand(), height: 120, anchors: [lang.t("search.placeholder")])   // empty: the placeholder
    let codes = all.filter { pick.contains($0.kode) }
    for (n, k) in codes.enumerated() {
        let c = [k.kode]   // the code; then the last thing each View draws, from the View's own source
        emit(k.kode, "registry-row", KBLIRegistryRow(kbli: k, isID: isID), anchors: c)
        emit(k.kode, "registry-sheet", RegistryVerdictSheet(kbli: k, expanded: .constant(false), onClose: {}, scrolls: false),
             anchors: c + [isID ? "Buka dosir lengkap" : "Open the full dossier"])
        emit(k.kode, "search-peak", QueryResultRow(kbli: k, isFirst: true, isSelected: false, isID: isID), anchors: c)
        emit(k.kode, "search-row", QueryResultRow(kbli: k, isFirst: false, isSelected: false, isID: isID), anchors: c)
        emit(k.kode, "detail-card", KBLIDetailRichView(kbli: k, scrolls: false), anchors: c + [lang.t("rich.cta.title")])
        emit(k.kode, "dossier", KBLIDossierView(kbli: k, variant: .claude, scrolls: false), anchors: c + ["Bali Zero · KBLI 2025"])
        emit(k.kode, "sheet-ledger", KBLIRegistryView(kbli: k, scrolls: false),
             anchors: c + [isID ? "Tanya tentang \(k.kode)…" : "Ask about \(k.kode)…"])
        state.chatContextCode = k
        emit(k.kode, "chat", ChatView(), height: 800, anchors: c)   // the code it is asked about
        state.chatContextCode = nil
        if n % 200 == 0 { err("encensus \(n)/\(codes.count)") }
    }
    try? fh.close()
    err("encensus: \(codes.count) codes, lang \(isID ? "id" : "en")")
    return 0
}
exit(rc)
