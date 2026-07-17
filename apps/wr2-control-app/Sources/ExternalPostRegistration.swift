import Foundation

/// "Aggiungi post esterno" — register an Instagram post Zero/Damar published OUTSIDE
/// the WR2 app (a post that never went through the pipeline, so no drafted carousel
/// ever existed for it locally). Pure-Foundation core: URL validation/canonicalization,
/// item_id/slug/dir-name derivation, and queue-entry construction — unit-testable
/// without SwiftUI, same split as ExternalImport.swift. The actual file copy (optional
/// images, needs AppKit for JPG→PNG conversion) and the QueueWriter append happen in
/// AppState, matching the reRenderCarousel/publishToInstagram/importExternalCarousel idiom.
enum ExternalPostRegistration {

    enum ValidationError: Error, Equatable, LocalizedError {
        case emptyURL
        case notAnInstagramPostURL
        case emptyTopic

        var errorDescription: String? {
            switch self {
            case .emptyURL:               return "L'URL Instagram è obbligatorio."
            case .notAnInstagramPostURL:  return "Non sembra un link a un post/reel Instagram valido."
            case .emptyTopic:             return "Il titolo/argomento è obbligatorio."
            }
        }
    }

    /// `instagram.com/(p|reel)/<shortcode>[/][?...]` — optional `www`, optional trailing
    /// slash/query string. Mirrors QueueWriter.extractMediaID's shape (Swift side) and
    /// scripts/wr2_queue_writer.py's `_IG_URL_RE` (Python side) — hand-kept in sync,
    /// there being no shared source between the two languages.
    private static let igURLPattern = #"^https?://(www\.)?instagram\.com/(p|reel)/([A-Za-z0-9_-]+)/?(\?.*)?$"#

    /// Validate + canonicalize a pasted Instagram URL to `https://www.instagram.com/(p|reel)/<code>/`.
    /// Rejects empty/garbage (acceptance criteria §A: "reject empty/garbage").
    static func canonicalizeInstagramURL(_ raw: String) throws -> String {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmed.isEmpty == false else { throw ValidationError.emptyURL }
        guard let re = try? NSRegularExpression(pattern: igURLPattern, options: [.caseInsensitive]) else {
            throw ValidationError.notAnInstagramPostURL
        }
        let range = NSRange(trimmed.startIndex..., in: trimmed)
        guard let m = re.firstMatch(in: trimmed, range: range),
              let kindRange = Range(m.range(at: 2), in: trimmed),
              let codeRange = Range(m.range(at: 3), in: trimmed) else {
            throw ValidationError.notAnInstagramPostURL
        }
        let kind = trimmed[kindRange].lowercased()
        let code = String(trimmed[codeRange])
        return "https://www.instagram.com/\(kind)/\(code)/"
    }

    /// Validate a required title/topic field: trimmed, non-empty. Returns the trimmed value.
    static func validateTopic(_ raw: String) throws -> String {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmed.isEmpty == false else { throw ValidationError.emptyTopic }
        return trimmed
    }

    private static func utcDateFormatter(_ format: String) -> DateFormatter {
        let df = DateFormatter()
        df.locale = Locale(identifier: "en_US_POSIX")
        df.timeZone = TimeZone(identifier: "UTC")
        df.dateFormat = format
        return df
    }

    /// `item_id` per spec §A: `external_<yyyy-MM-dd>T<HHmmss>_<slug>`.
    static func makeItemID(publishDate: Date, slug: String) -> String {
        "external_\(utcDateFormatter("yyyy-MM-dd'T'HHmmss").string(from: publishDate))_\(slug)"
    }

    /// The on-disk carousel dir name for an external post WITH images:
    /// `external-<yyyy-MM-dd>T<HHmmss>-<slug>`.
    ///
    /// Includes TIME, not just date (Codex red-team, 2026-07-17, finding H):
    /// `makeItemID` is unique on date+time+slug, but this dir name was date+slug
    /// only — two same-day, same-slug external registrations (e.g. the operator
    /// re-registers a correction, or two posts on the same topic in one day)
    /// would collide into ONE directory, silently clobbering the first post's
    /// images with the second's.
    static func carouselDirName(publishDate: Date, slug: String) -> String {
        "external-\(utcDateFormatter("yyyy-MM-dd'T'HHmmss").string(from: publishDate))-\(slug)"
    }

    /// Build the queue entry — every field from §A. `carousel_path` is present only
    /// when at least one image was copied in (0-image entries render as a cover-less
    /// virtual card, the SAME convention the ig-* Graph-API backfill entries use —
    /// WarRoom.swift:361-397). Both `published_at` (spec's literal field name) and
    /// `instagram_published_at` (the field every existing consumer — WarRoom's
    /// `pubAtBySlug`/`parsePublishedAt`, the Python scraper's staleness check — actually
    /// reads) carry the SAME ISO timestamp; writing only the former would make this
    /// entry invisible to the §D recency fix and the publish-date display.
    static func buildQueueEntry(
        instagramURL: String, topic: String, slug: String, publishDate: Date,
        slideCount: Int, carouselPath: String?
    ) -> [String: Any] {
        let iso = ISO8601DateFormatter().string(from: publishDate)
        var entry: [String: Any] = [
            "item_id": makeItemID(publishDate: publishDate, slug: slug),
            "state": "published",
            "instagram_post_url": instagramURL,
            "source": "external_manual",
            "published_at": iso,
            "instagram_published_at": iso,
            "topic": topic,
            "topic_slug": slug,
            "slide_count": slideCount,
            "created_at": iso,
        ]
        if let carouselPath { entry["carousel_path"] = carouselPath }
        return entry
    }
}
