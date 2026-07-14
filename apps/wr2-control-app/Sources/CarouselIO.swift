import Foundation

/// Import/export of carousels as plain PNG files.
///
/// WHY: the operator needs to (a) pull the finished slides out to publish them on
/// Instagram by hand, and (b) bring an externally-edited carousel (e.g. retouched in
/// Zero Design / Canva, exported as PNG) back INTO the war-room so it surfaces in
/// Revisione and can be marked published. Both are pure file moves — no pipeline.
///
/// All writes are best-effort-atomic per file; a partial failure is reported, never
/// silently swallowed (scar #2 — no green-but-empty). Foundation-only so it is testable
/// without SwiftUI.
enum CarouselIO {

    enum IOError: LocalizedError {
        case noSlides
        case notReadable(String)
        case writeFailed(String)
        case badName
        var errorDescription: String? {
            switch self {
            case .noSlides:           return "Questo carosello non ha slide PNG su disco."
            case .notReadable(let f): return "Non riesco a leggere: \(f)"
            case .writeFailed(let f): return "Scrittura fallita: \(f)"
            case .badName:            return "Nome non valido per il carosello."
            }
        }
    }

    // MARK: - Export (download)

    /// Copy ONE slide PNG to a destination chosen by the user. Returns the written URL.
    @discardableResult
    static func exportSlide(_ src: URL, to dest: URL) throws -> URL {
        guard FileManager.default.isReadableFile(atPath: src.path) else {
            throw IOError.notReadable(src.lastPathComponent)
        }
        do {
            if FileManager.default.fileExists(atPath: dest.path) {
                try FileManager.default.removeItem(at: dest)
            }
            try FileManager.default.copyItem(at: src, to: dest)
            return dest
        } catch { throw IOError.writeFailed(dest.lastPathComponent) }
    }

    /// Copy the WHOLE carousel into `destFolder/<slug>/`, slides renamed `01.png…NN.png`
    /// (Instagram-upload order). Creates the folder. Returns the folder + count written.
    @discardableResult
    static func exportCarousel(slug: String, slides: [URL], into destFolder: URL) throws -> (URL, Int) {
        guard slides.isEmpty == false else { throw IOError.noSlides }
        let outDir = destFolder.appendingPathComponent(safeSlug(slug), isDirectory: true)
        try FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)
        var written = 0
        for (i, src) in slides.enumerated() {
            guard FileManager.default.isReadableFile(atPath: src.path) else {
                throw IOError.notReadable(src.lastPathComponent)
            }
            let name = String(format: "%02d.png", i + 1)
            let dest = outDir.appendingPathComponent(name)
            do {
                if FileManager.default.fileExists(atPath: dest.path) {
                    try FileManager.default.removeItem(at: dest)
                }
                try FileManager.default.copyItem(at: src, to: dest)
                written += 1
            } catch { throw IOError.writeFailed(name) }
        }
        return (outDir, written)
    }

    // MARK: - Import (upload)

    /// Create a NEW carousel on disk from a set of PNG files the user picked, sorted by
    /// filename so a "1.png … 8.png" or "01 … 08" export keeps its order. Writes them to
    /// `<carouselRoot>/<slug>/slides/NN.png`. Returns the carousel directory + slide count.
    /// Does NOT enqueue — the caller does that (so it can refresh UI + stay idempotent).
    @discardableResult
    static func importCarousel(slug rawSlug: String, pngs rawPNGs: [URL],
                               carouselRoot: URL) throws -> (URL, Int) {
        let slug = safeSlug(rawSlug)
        guard slug.isEmpty == false else { throw IOError.badName }
        let pngs = rawPNGs
            .filter { $0.pathExtension.lowercased() == "png" }
            .sorted { naturalLess($0.lastPathComponent, $1.lastPathComponent) }
        guard pngs.isEmpty == false else { throw IOError.noSlides }

        let dir = carouselRoot.appendingPathComponent(slug, isDirectory: true)
        let slidesDir = dir.appendingPathComponent("slides", isDirectory: true)
        try FileManager.default.createDirectory(at: slidesDir, withIntermediateDirectories: true)

        var written = 0
        for (i, src) in pngs.enumerated() {
            guard FileManager.default.isReadableFile(atPath: src.path) else {
                throw IOError.notReadable(src.lastPathComponent)
            }
            // canonical on-disk name is "N.png" (scanCarousels sorts these → cover = 1.png)
            let dest = slidesDir.appendingPathComponent("\(i + 1).png")
            do {
                if FileManager.default.fileExists(atPath: dest.path) {
                    try FileManager.default.removeItem(at: dest)
                }
                try FileManager.default.copyItem(at: src, to: dest)
                written += 1
            } catch { throw IOError.writeFailed(dest.lastPathComponent) }
        }
        // a tiny provenance marker so it's clear this came in via upload, not the pipeline
        let marker = dir.appendingPathComponent("uploaded.json")
        let meta: [String: Any] = ["source": "wr2-control-app upload", "slide_count": written]
        if let data = try? JSONSerialization.data(withJSONObject: meta, options: [.prettyPrinted]) {
            try? data.write(to: marker)
        }
        return (dir, written)
    }

    // MARK: - Helpers

    /// Slugify: lowercase, spaces/underscores → hyphens, keep [a-z0-9-], collapse repeats.
    static func safeSlug(_ s: String) -> String {
        let lowered = s.lowercased()
        var out = ""
        var lastHyphen = false
        for ch in lowered {
            if ch.isLetter || ch.isNumber {
                out.append(ch); lastHyphen = false
            } else if ch == " " || ch == "_" || ch == "-" {
                if !lastHyphen && !out.isEmpty { out.append("-"); lastHyphen = true }
            }
        }
        while out.hasSuffix("-") { out.removeLast() }
        return out
    }

    /// Natural-order compare so "2.png" < "10.png" (not lexical "10" < "2").
    static func naturalLess(_ a: String, _ b: String) -> Bool {
        func num(_ s: String) -> Int? {
            let digits = s.prefix { $0.isNumber }
            return digits.isEmpty ? nil : Int(digits)
        }
        if let na = num(a), let nb = num(b), na != nb { return na < nb }
        return a.localizedStandardCompare(b) == .orderedAscending
    }
}
