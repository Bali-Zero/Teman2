import Foundation

/// One markdown document (article or book chapter).
struct MediaItem: Identifiable, Hashable {
    let id: String          // file stem
    let title: String       // first H1/H2 or humanized stem
    let url: URL
}

/// One PDF book, with its language.
struct PDFItem: Identifiable, Hashable {
    enum Lang: String { case en, id }
    let id: String
    let lang: Lang
    let url: URL
    var label: String { lang == .en ? "English" : "Bahasa Indonesia" }
}

/// Enumerates the bundled media (20 articles, 13 chapters, 2 PDFs) from Resources/.
struct MediaLibrary {
    let articles: [MediaItem]
    let chapters: [MediaItem]
    let books: [PDFItem]

    init(resourcesPath: String) {
        let fm = FileManager.default
        let root = URL(fileURLWithPath: resourcesPath)
        articles = Self.markdownItems(in: root.appendingPathComponent("articles"), fm: fm)
        chapters = Self.markdownItems(in: root.appendingPathComponent("book-chapters"), fm: fm)

        var pdfs: [PDFItem] = []
        let en = root.appendingPathComponent("Bali-Threshold-2026.pdf")
        let id = root.appendingPathComponent("Bali-Threshold-2026-ID.pdf")
        if fm.fileExists(atPath: en.path) { pdfs.append(PDFItem(id: "book-en", lang: .en, url: en)) }
        if fm.fileExists(atPath: id.path) { pdfs.append(PDFItem(id: "book-id", lang: .id, url: id)) }
        books = pdfs
    }

    /// Convenience init from the app bundle Resources.
    init() {
        let path = Bundle.main.resourceURL?.path
            ?? Bundle.main.bundleURL.appendingPathComponent("Contents/Resources").path
        self.init(resourcesPath: path)
    }

    private static func markdownItems(in dir: URL, fm: FileManager) -> [MediaItem] {
        guard let names = try? fm.contentsOfDirectory(atPath: dir.path) else { return [] }
        return names.filter { $0.hasSuffix(".md") && $0 != "_INDEX.md" && $0.hasPrefix("_") == false }
            .sorted()
            .map { name in
                let url = dir.appendingPathComponent(name)
                let stem = (name as NSString).deletingPathExtension
                let title = Self.firstHeading(of: url) ?? Self.humanize(stem)
                return MediaItem(id: stem, title: title, url: url)
            }
    }

    private static func firstHeading(of url: URL) -> String? {
        guard let raw = try? String(contentsOf: url, encoding: .utf8) else { return nil }
        let body = MarkdownParser.stripFrontmatter(raw)
        for line in body.split(separator: "\n") {
            let t = line.trimmingCharacters(in: .whitespaces)
            if t.hasPrefix("# ") { return String(t.dropFirst(2)) }
            if t.hasPrefix("## ") { return String(t.dropFirst(3)) }
        }
        return nil
    }

    private static func humanize(_ stem: String) -> String {
        stem.replacingOccurrences(of: "-", with: " ")
            .replacingOccurrences(of: #"^\d+\s*"#, with: "", options: .regularExpression)
            .capitalized
    }
}
