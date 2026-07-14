import Foundation

enum InstagramCaption {
    static let maxLength = 2_200
    private static let publisherScript = "scripts/wr2_ig_publish_remote.py"

    static func characterCount(_ text: String) -> Int {
        text.count
    }

    static func isPublishable(_ text: String) -> Bool {
        text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty == false
            && characterCount(text) <= maxLength
    }

    static func previewArguments(slug: String) -> [String] {
        [publisherScript, slug, "--print-caption"]
    }

    static func publishArguments(
        slug: String, captionFile: URL, confirm: Bool
    ) -> [String] {
        var arguments = [publisherScript, slug, "--caption-file", captionFile.path]
        if confirm { arguments.append("--confirm") }
        return arguments
    }

    static func writeTemporaryFile(
        _ text: String,
        directory: URL = FileManager.default.temporaryDirectory
    ) throws -> URL {
        let url = directory.appendingPathComponent(
            "wr2-instagram-caption-\(UUID().uuidString).txt"
        )
        try Data(text.utf8).write(to: url, options: .atomic)
        return url
    }
}
