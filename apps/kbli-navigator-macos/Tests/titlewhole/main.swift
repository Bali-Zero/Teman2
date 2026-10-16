import AppKit
import PDFKit
import SwiftUI

// Tests/titlewhole: a title is never cut (the #8492 gate, binding 8). `titlewhole <out.jsonl> [--lang en|id] [--codes a,b|all]` renders the
// sheet for each code, collapsed and open, at the two column widths the collapsed pane takes (the minimum window's and the default's),
// through ImageRenderer into a PDF as Tests/encensus does, and writes the text PDFKit reads back: what is DRAWN. Tools/design/title_whole.py
// judges it: the record's whole title is in the drawn text, on every line. One JSON line per (code, view, width).
// Adopted from the gate harness `gcensus` of #8492.

func err(_ s: String) { FileHandle.standardError.write(Data((s + "\n").utf8)) }
let args = CommandLine.arguments
guard args.count > 1 else { err("usage: titlewhole <out.jsonl> [--lang en|id] [--codes a,b|all]"); exit(2) }
func flag(_ name: String) -> String? {
    guard let j = args.firstIndex(of: name), args.count > j + 1 else { return nil }
    return args[j + 1]
}
_ = NSApplication.shared
Motion.frozenMs = Motion.total * 1000   // an immersive View is read at the final frame of its choreography

@MainActor func pdfText(_ v: AnyView, width: CGFloat) -> String {
    let framed = AnyView(v.frame(width: width, alignment: .top).fixedSize(horizontal: false, vertical: true))
    // A hair of tracking keeps PDFKit from splitting words at ligatures.
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

let rc: Int32 = MainActor.assumeIsolated {
    let state = AppState()
    guard state.store.all.count == 1559 else { err("dataset not found next to the binary"); return 2 }
    let lang = LanguageManager()
    lang.lang = (flag("--lang") ?? "en") == "id" ? .id : .en
    let isID = lang.lang == .id
    Theme.mode = .light
    let spec = flag("--codes") ?? "all"
    let codes: [KBLI] = spec == "all" ? state.store.all : state.store.all.filter { Set(spec.split(separator: ",").map(String.init)).contains($0.kode) }
    FileManager.default.createFile(atPath: args[1], contents: nil)
    guard let sink = FileHandle(forWritingAtPath: args[1]) else { return 2 }
    for (n, k) in codes.enumerated() {
        for (view, open) in [("collapsed", false), ("open", true)] {
            for width in [783.0, 924.0] {
                let sheet = RegistryVerdictSheet(kbli: k, expanded: .constant(open), onClose: {}, scrolls: false)
                let text = pdfText(AnyView(sheet.immersiveHost().environmentObject(state).environmentObject(lang)), width: CGFloat(width))
                let rec: [String: Any] = ["code": k.kode, "view": view, "width": width, "text": text, "title": LabelBook.title(k, isID: isID)]
                if let d = try? JSONSerialization.data(withJSONObject: rec, options: [.sortedKeys]) { sink.write(d); sink.write(Data("\n".utf8)) }
            }
        }
        if n % 300 == 0 { err("titlewhole \(n)/\(codes.count)") }
    }
    try? sink.close()
    err("titlewhole: \(codes.count) codes, lang \(isID ? "id" : "en")")
    return 0
}
exit(rc)
