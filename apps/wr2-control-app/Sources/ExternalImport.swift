import Foundation

/// "Importa carosello esterno" — bring in a carousel Zero built OUTSIDE the app (a single
/// PDF where each page is a slide, a folder of images, or several loose image files) via
/// the `wr2_carousel_import.py` normalizer pipeline (PDF/image → 1080×1350 PNG, carousel
/// dir + queue row). This file is the pure-Foundation core: input classification and CLI
/// argument shaping, both unit-testable without SwiftUI (same split as InstagramCaption.swift
/// and WarRoom.swift). Process launching + progress streaming lives in AppState, matching
/// the reRenderCarousel/publishToInstagram idiom.
enum ExternalImport {

    /// Script path relative to the monorepo root — the frozen contract:
    /// `wr2_carousel_import.py <input>... [--slug SLUG] [--topic "TEXT"] [--fit MODE] [--dry-run]`.
    static let scriptRelativePath = "scripts/wr2_carousel_import.py"

    static let supportedImageExtensions: Set<String> = ["png", "jpg", "jpeg", "webp", "heic"]

    // MARK: - Fit mode

    enum FitMode: String, CaseIterable, Identifiable {
        case contain, cover, native
        var id: String { rawValue }
    }

    // MARK: - Input classification

    /// One entry the operator picked, with whether it's a directory (resolved by the
    /// caller via FileManager — kept out of this pure function so it stays testable
    /// with synthetic entries, no disk access required).
    struct InputEntry: Equatable {
        let url: URL
        let isDirectory: Bool
    }

    enum InputKind: Equatable {
        case pdf(URL)
        case folder(URL)
        case images([URL])
    }

    enum ClassifyError: Error, Equatable {
        case empty
        case multiplePDFs
        case multipleFolders
        case mixedKinds
        case unsupportedExtension(String)
    }

    /// Classify a set of picked entries into exactly one of: a single PDF, a single
    /// folder, or a run of image files — never a mix (scar #3 discipline: reject on
    /// the actual composition, not a substring/count heuristic).
    static func classify(_ entries: [InputEntry]) -> Result<InputKind, ClassifyError> {
        guard entries.isEmpty == false else { return .failure(.empty) }

        let dirs = entries.filter { $0.isDirectory }
        let files = entries.filter { $0.isDirectory == false }

        if dirs.isEmpty == false {
            if entries.count > 1 {
                return .failure(dirs.count > 1 ? .multipleFolders : .mixedKinds)
            }
            return .success(.folder(dirs[0].url))
        }

        let pdfs = files.filter { $0.url.pathExtension.lowercased() == "pdf" }
        if pdfs.isEmpty == false {
            if files.count > 1 {
                return .failure(pdfs.count > 1 ? .multiplePDFs : .mixedKinds)
            }
            return .success(.pdf(pdfs[0].url))
        }

        for f in files {
            let ext = f.url.pathExtension.lowercased()
            guard supportedImageExtensions.contains(ext) else {
                return .failure(.unsupportedExtension(ext))
            }
        }
        return .success(.images(files.map { $0.url }))
    }

    /// The absolute input paths to hand the script, in a stable order, for a resolved kind.
    static func inputPaths(for kind: InputKind) -> [URL] {
        switch kind {
        case .pdf(let u):     return [u]
        case .folder(let u):  return [u]
        case .images(let us): return us
        }
    }

    // MARK: - CLI argument shaping

    /// Build the script's argument list — everything AFTER the script path itself.
    /// The caller (AppState) resolves the script path (repo-relative vs. fallback
    /// invocation differ in how they name the python executable, so the path isn't
    /// baked in here, unlike InstagramCaption's `previewArguments`/`publishArguments`).
    /// `topic` is trimmed and omitted when blank (optional field).
    static func scriptArguments(inputs: [URL], topic: String, fit: FitMode) -> [String] {
        var args = inputs.map { $0.path }
        let trimmedTopic = topic.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmedTopic.isEmpty == false {
            args.append(contentsOf: ["--topic", trimmedTopic])
        }
        args.append(contentsOf: ["--fit", fit.rawValue])
        return args
    }

    // MARK: - Result parsing

    struct ImportSuccess: Decodable, Equatable {
        let ok: Bool
        let slug: String
        let carousel_dir: String
        let slide_count: Int
        let queue_id: String
    }

    private struct ImportFailure: Decodable {
        let ok: Bool
        let error: String
    }

    enum ParsedOutcome: Equatable {
        case success(ImportSuccess)
        case failure(String)
    }

    /// Parse the script's stdout for its one JSON result line (contract: `{"ok":true,...}`
    /// on exit 0, `{"ok":false,"error":"..."}` on exit 2). Scans from the LAST line
    /// backwards so stray non-JSON noise on stdout (there shouldn't be any per contract,
    /// but stderr/stdout mixing has bitten this app before) doesn't hide the real result.
    /// Falls back to a bare "exit N" message if nothing decodes — never silently succeeds.
    static func parseOutcome(stdout: String, exitCode: Int32) -> ParsedOutcome {
        let lines = stdout.split(separator: "\n", omittingEmptySubsequences: true).map(String.init)
        for line in lines.reversed() {
            guard let data = line.data(using: .utf8) else { continue }
            if let ok = try? JSONDecoder().decode(ImportSuccess.self, from: data), ok.ok {
                return .success(ok)
            }
            if let fail = try? JSONDecoder().decode(ImportFailure.self, from: data), fail.ok == false {
                return .failure(fail.error)
            }
        }
        return .failure("exit \(exitCode)")
    }
}
