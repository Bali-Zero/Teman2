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
                              _ change: (inout [String: Any]) throws -> Void) throws {
        let data = try Data(contentsOf: queueFile)
        guard var arr = try JSONSerialization.jsonObject(with: data) as? [[String: Any]] else {
            throw NSError(domain: "QueueWriter", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "queue is not a JSON array"])
        }
        var touched = false
        for i in arr.indices where matches(arr[i], slug: slug) {
            try change(&arr[i]); touched = true
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

    /// Publish-eligibility error domain code — thrown BEFORE any field is touched
    /// (guard-first inside the `mutate` closure), so a refused publish never leaves a
    /// partial mutation on disk: `mutate` only writes after its closure returns
    /// without throwing.
    static let ineligibleStateErrorCode = 3

    /// Marks a queue entry published. FAIL-CLOSED on the entry's CURRENT state
    /// (cross-finding with the Python A3 daily-reconciler, 2026-07-16): this writer
    /// mutates the queue JSON directly and never goes through
    /// `scripts/wr2_queue_writer.py`'s `mark_published`, so without this check an
    /// entry the reconciler just flagged `render_incomplete` (declared/disk mismatch
    /// it could not explain as stale metadata) — or any other not-ready state — could
    /// still be published from this app even though every OTHER consumer already
    /// refuses it by construction (that script's own `PUBLISHABLE_STATES` allow-list).
    /// Uses `isQueuePublishEligible` (Models.swift) — the SAME `CarouselPhase`
    /// classification the gallery band and `Carousel.isPublishEligible` use — so this
    /// is not a second, independently-maintained rule (scar #3).
    static func markPublished(queueFile: URL, slug: String, igURL: String, publishedAt: String) throws {
        try mutate(queueFile: queueFile, slug: slug) { item in
            let state = item["state"] as? String
            let verdict = item["critic_overall_verdict"] as? String
            guard isQueuePublishEligible(state: state, criticVerdict: verdict) else {
                throw NSError(domain: "QueueWriter", code: ineligibleStateErrorCode, userInfo: [
                    NSLocalizedDescriptionKey:
                        "refusing to mark published — state \(state.map { "\"\($0)\"" } ?? "(none)") is not publish-eligible (the carousel needs to reach a finished/ready state first, e.g. a render_incomplete or in-review entry cannot be published)"
                ])
            }
            if item["state_before_publish"] == nil {
                item["state_before_publish"] = item["state"] ?? "drafted"
            }
            item["state"] = "published"
            item["instagram_post_url"] = igURL
            // NEVER write ig_media_id here (Codex red-team, 2026-07-17, finding B):
            // extractMediaID(from:) returns the URL SHORTCODE, not the real numeric
            // Graph media id — the scraper's media_id_of() (wr2_ig_metrics_scraper.py)
            // now treats a present ig_media_id as AUTHORITATIVE and feeds it straight
            // to the Graph API, so writing the shortcode here would poison metrics for
            // every app-published post (Graph 400 / wrong media). The real numeric id
            // is only ever known by wr2_ig_discovery.py's Graph fetch and is backfilled
            // later via backfill_media_id — this writer must leave the field untouched.
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

    /// Duplicate error code for `addExternalPost` — mirrors `ineligibleStateErrorCode`.
    static let duplicateExternalPostErrorCode = 4

    /// Append a manually-registered external Instagram post (§A external-post feature,
    /// 2026-07-17) — a post Zero/Damar published OUTSIDE the WR2 pipeline, so there is
    /// no drafted carousel for it to advance. Unlike `enqueueDrafted` (state="drafted",
    /// awaiting review) this writes directly in the ALREADY-published shape so it shows
    /// up in the gallery immediately via `isQueueItemPublished`'s exemption from the A2
    /// completeness gate — mirroring the existing ig-* virtual-entry convention
    /// (WarRoom.swift:361-397) this feature is modeled on.
    ///
    /// Refuses a duplicate — same `instagram_post_url` (trimmed) OR same `item_id`
    /// already present in the LOCAL queue — BEFORE any write (mirrors `markPublished`'s
    /// guard-first discipline), so a double-tap of Save (or a retried M5→Pro replay)
    /// never double-enqueues (acceptance criteria §A #2). This is the LOCAL/M5 half of
    /// the duplicate check; `scripts/wr2_queue_writer.py add_external` re-checks
    /// independently on the Pro side once the entry propagates (§B).
    @discardableResult
    static func addExternalPost(queueFile: URL, entry: [String: Any]) throws -> Bool {
        let newID = entry["item_id"] as? String
        let newURL = (entry["instagram_post_url"] as? String)?
            .trimmingCharacters(in: .whitespacesAndNewlines)
        // Only a genuine "no queue file yet" starts from an empty array (Codex
        // red-team, 2026-07-17, finding A). The previous `(try? ...) ?? []` on
        // BOTH the read and the parse meant ANY transient read error (a sandbox
        // hiccup, a concurrent writer mid-replace) OR a decode failure (corrupt/
        // truncated JSON) silently degraded to [], and the append below would
        // then WRITE OVER THE WHOLE QUEUE with just this one entry. A real file
        // that exists but fails to read or parse must THROW — visible in the UI,
        // zero write — never be treated as "empty".
        var arr: [[String: Any]]
        if FileManager.default.fileExists(atPath: queueFile.path) {
            let data = try Data(contentsOf: queueFile)
            guard let parsed = try JSONSerialization.jsonObject(with: data) as? [[String: Any]] else {
                throw NSError(domain: "QueueWriter", code: 1, userInfo: [
                    NSLocalizedDescriptionKey: "queue is not a JSON array — refusing to overwrite it"
                ])
            }
            arr = parsed
        } else {
            arr = []
        }

        // Shortcode-first (Codex red-team, 2026-07-17, finding D, mirrored from the
        // Python-side add_external fix): an existing entry's URL may carry a
        // different query string/scheme/www variant (e.g. a stray ?utm_...) of
        // the SAME post — comparing by shortcode first (WarRoom.igShortcode)
        // catches that; exact-string is only the fallback when either URL
        // doesn't parse a shortcode at all.
        let newShortcode = newURL.flatMap { WarRoom.igShortcode(from: $0) }
        let isDuplicate = arr.contains { existing in
            if let nid = newID, (existing["item_id"] as? String) == nid { return true }
            if let nurl = newURL, nurl.isEmpty == false {
                let existingURL = (existing["instagram_post_url"] as? String)?
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                if let newCode = newShortcode, let existingURL,
                   let existingCode = WarRoom.igShortcode(from: existingURL) {
                    if existingCode == newCode { return true }
                } else if existingURL == nurl {
                    return true
                }
            }
            return false
        }
        guard isDuplicate == false else {
            throw NSError(domain: "QueueWriter", code: duplicateExternalPostErrorCode, userInfo: [
                NSLocalizedDescriptionKey:
                    "un post con questo URL o id è già registrato"
            ])
        }

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
