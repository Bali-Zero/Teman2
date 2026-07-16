import Foundation

/// Mutates the WR2 review queue JSON to record/undo a manual Instagram publish.
/// Operates on the raw JSON object graph so UNKNOWN fields are preserved verbatim
/// (scar #9 schema-drift) and only publish-state keys are touched (scar #5).
/// Writes atomically (tmp + rename) so a concurrent reader never sees a partial file.
enum QueueWriter {

    /// Pull the IG media shortcode out of a post URL, or pass a bare id through.
    static func extractMediaID(from igURL: String) -> String? {
        let s = igURL.trimmingCharacters(in: .whitespacesAndNewlines)
        if s.isEmpty { return nil }
        // .../p/<id>/ or .../reel/<id>/
        if let r = s.range(of: #"/(p|reel)/([^/?#]+)"#, options: .regularExpression) {
            let seg = String(s[r])
            return seg.components(separatedBy: "/").filter { !$0.isEmpty }.last
        }
        // bare id (no slashes, no scheme)
        if !s.contains("/") && !s.contains(":") { return s }
        return nil
    }

    /// The folder-derived identity from `carousel_path` — the SAME value the app
    /// uses as `Carousel.slug` (`WarRoom.swift`: `dir.lastPathComponent`). Some
    /// queue entries carry a shorter/stale `topic_slug` (missing the date prefix
    /// or the draft-id suffix — 21/67 entries observed 2026-07-11), so this is
    /// the primary match key; `topic_slug` is only a fallback for entries with
    /// no `carousel_path` at all.
    private static func pathSlugOf(_ item: [String: Any]) -> String? {
        guard let p = item["carousel_path"] as? String else { return nil }
        let t = p.hasSuffix("/") ? String(p.dropLast()) : p
        return t.components(separatedBy: "/").last
    }

    private static func slugOf(_ item: [String: Any]) -> String? {
        pathSlugOf(item) ?? (item["topic_slug"] as? String)
    }

    private static func matches(_ item: [String: Any], slug: String) -> Bool {
        if let p = pathSlugOf(item), p == slug { return true }
        if pathSlugOf(item) == nil, let t = item["topic_slug"] as? String, t == slug { return true }
        return false
    }

    private static func mutate(queueFile: URL, slug: String,
                              _ change: (inout [String: Any]) -> Void) throws {
        let data = try Data(contentsOf: queueFile)
        guard var arr = try JSONSerialization.jsonObject(with: data) as? [[String: Any]] else {
            throw NSError(domain: "QueueWriter", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "queue is not a JSON array"])
        }
        var touched = false
        for i in arr.indices where matches(arr[i], slug: slug) {
            change(&arr[i]); touched = true
        }
        guard touched else {
            throw NSError(domain: "QueueWriter", code: 2,
                          userInfo: [NSLocalizedDescriptionKey: "no queue item for slug \(slug)"])
        }
        let out = try JSONSerialization.data(withJSONObject: arr, options: [.prettyPrinted, .sortedKeys])
        let tmp = queueFile.deletingLastPathComponent()
            .appendingPathComponent(".\(queueFile.lastPathComponent).tmp-\(UUID().uuidString)")
        do {
            try out.write(to: tmp)
            // atomic replace
            _ = try FileManager.default.replaceItemAt(queueFile, withItemAt: tmp)
        } catch {
            try? FileManager.default.removeItem(at: tmp)
            throw error
        }
    }

    static func markPublished(queueFile: URL, slug: String, igURL: String, publishedAt: String) throws {
        let mediaID = extractMediaID(from: igURL)
        try mutate(queueFile: queueFile, slug: slug) { item in
            if item["state_before_publish"] == nil {
                item["state_before_publish"] = item["state"] ?? "drafted"
            }
            item["state"] = "published"
            item["instagram_post_url"] = igURL
            if let m = mediaID { item["ig_media_id"] = m }
            item["instagram_published_at"] = publishedAt
        }
    }

    static func undoPublished(queueFile: URL, slug: String) throws {
        try mutate(queueFile: queueFile, slug: slug) { item in
            let prior = (item["state_before_publish"] as? String) ?? "drafted"
            item["state"] = prior
            item.removeValue(forKey: "ig_media_id")
            item.removeValue(forKey: "instagram_post_url")
            item.removeValue(forKey: "instagram_published_at")
            item.removeValue(forKey: "state_before_publish")
        }
    }

    /// Append a fresh `drafted` review entry for a just-rendered carousel, so it surfaces
    /// in Revisione. Closes the Step-7 enqueue gap: the orchestrator renders to
    /// output/carousel/<slug>/ but does not always write the queue row itself.
    /// Idempotent — no-op if an entry for `slug` already exists (avoids double-enqueue
    /// on re-run / racing terminal events). Atomic write (scar #5), unknown fields N/A
    /// on a new entry. Returns true if a new row was appended.
    @discardableResult
    static func enqueueDrafted(queueFile: URL, slug: String, slideCount: Int,
                               isoTimestamp: String) throws -> Bool {
        let data = (try? Data(contentsOf: queueFile)) ?? Data("[]".utf8)
        var arr = (try? JSONSerialization.jsonObject(with: data)) as? [[String: Any]] ?? []
        // idempotent: already queued (any state) → do nothing
        if arr.contains(where: { matches($0, slug: slug) }) { return false }
        let entry: [String: Any] = [
            "id": "carousel_\(isoTimestamp)_\(slug)",
            "topic_slug": slug,
            "state": "drafted",
            "media_type": "CAROUSEL_ALBUM",
            "carousel_path": "~/nuzantara/apps/war-room/output/carousel/\(slug)/",
            "slide_count": slideCount,
            // Honest vocabulary (audit §6/§5a, A3 edit spec D2, 2026-07-14): the app
            // enqueues drafted carousels WITHOUT ever running a critic — including raw
            // PNG imports the critic never saw. "pass" fabricated a verdict that never
            // happened; "not_run" says the true thing. Matches the Python cron path's
            // parallel fix (wr2_html_render_apply.py: legibility_only_pass/soft_fail)
            // and the existing "external" precedent (wr2_carousel_import.py).
            "critic_overall_verdict": "not_run",
            "instagram_post_url": NSNull(),
            "instagram_published_at": NSNull(),
            "engagement_metrics": NSNull(),
            "caption": NSNull(),
            "state_history": [["state": "drafted", "at": isoTimestamp, "by": "wr2-control-app"]],
            "_provenance": "auto-enqueue by WR2 Control on run success (Step-7 handoff gap)",
            "attr_source": "app",
        ]
        arr.append(entry)
        let out = try JSONSerialization.data(withJSONObject: arr, options: [.prettyPrinted, .sortedKeys])
        let tmp = queueFile.deletingLastPathComponent()
            .appendingPathComponent(".\(queueFile.lastPathComponent).tmp-\(UUID().uuidString)")
        do {
            try out.write(to: tmp)
            _ = try FileManager.default.replaceItemAt(queueFile, withItemAt: tmp)
        } catch {
            try? FileManager.default.removeItem(at: tmp)
            throw error
        }
        return true
    }
}
