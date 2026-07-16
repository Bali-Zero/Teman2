import Foundation

/// Reads the WR2 pipeline's on-disk state: the carousel gallery and the review queue.
///
/// Defensive against scar #1 (HOME-fork / path-drift): the queue JSON stores absolute
/// paths under `/Users/nuzantara/...`, which are dead on M5 (user `balizero`). We NEVER
/// trust an absolute path read from the JSON — we re-root it against the live war-room
/// directory by basename.
enum WarRoom {

    /// Resolve the war-room output root.
    /// Honors the `WR2_WARROOM_ROOT` env override. The Mini/TV postazione uses this after
    /// `deploy/install-mini.sh` creates a local Pro-synced copy, because the Mini has no
    /// war-room output at the monorepo path. Falls back to:
    /// ~/nuzantara/apps/war-room/output.
    static func defaultOutputRoot() -> URL {
        if let override = ProcessInfo.processInfo.environment["WR2_WARROOM_ROOT"],
           override.isEmpty == false {
            return URL(fileURLWithPath: override, isDirectory: true)
        }
        let home = FileManager.default.homeDirectoryForCurrentUser
        return home
            .appendingPathComponent("nuzantara/apps/war-room/output", isDirectory: true)
    }

    static func carouselRoot(outputRoot: URL? = nil) -> URL {
        (outputRoot ?? defaultOutputRoot()).appendingPathComponent("carousel", isDirectory: true)
    }

    static func queueFile(outputRoot: URL? = nil) -> URL {
        (outputRoot ?? defaultOutputRoot())
            .appendingPathComponent("queue/human-review-queue.json", isDirectory: false)
    }

    // MARK: - Path-drift resolver (scar #1)

    /// Given a (possibly foreign-host) absolute carousel path from the queue JSON,
    /// re-root it under the LIVE carousel root by its slug (last path component),
    /// so a `/Users/nuzantara/...` path still resolves on `balizero`'s machine.
    /// Returns nil if no matching live directory exists.
    static func resolveCarouselDir(foreignPath: String, carouselRoot root: URL) -> URL? {
        let trimmed = foreignPath.hasSuffix("/")
            ? String(foreignPath.dropLast()) : foreignPath
        let slug = (trimmed as NSString).lastPathComponent
        guard slug.isEmpty == false else { return nil }
        let candidate = root.appendingPathComponent(slug, isDirectory: true)
        return FileManager.default.fileExists(atPath: candidate.path) ? candidate : nil
    }

    // MARK: - Queue item → on-disk carousel join

    /// Join a review-queue item to its on-disk carousel.
    ///
    /// The queue has two slug vocabularies (scar #9, schema drift):
    ///  - legacy items: `topic_slug` IS the directory name;
    ///  - FSM items (topic-selector 2026-07+): the directory is
    ///    `YYYY-MM-DD-<topic_slug>-<draftid8>` while `topic_slug` stays truncated,
    ///    so an exact `topic_slug == dir` match never fires and the review row
    ///    silently loses its click target ("non riesco ad aprire i drafted").
    ///
    /// Resolution order — every step is an exact/anchored match, never bare
    /// substring (scar #3, guard-over-match):
    ///  1. basename of `carousel_path` (authoritative — same join scanCarousels uses)
    ///  2. `topic_slug` exact (legacy schema)
    ///  3. anchored FSM pattern `^\d{4}-\d{2}-\d{2}-<topic_slug>-[0-9a-f]{6,}$`
    ///
    /// Steps extracted into `queueItemMatchesByPath`/`queueItemMatchesByTopicSlug` so the
    /// A2 completeness gate below (which only has a candidate SLUG, not a built Carousel
    /// array, while it's still deciding whether the dir belongs in the gallery at all) can
    /// reuse the exact same resolution rule instead of growing a second, driftable copy
    /// (scar #3: a guard and its untested twin are how over/under-match pairs are born).
    static func matchCarousel(for item: ReviewItem, in carousels: [Carousel]) -> Carousel? {
        if let c = carousels.first(where: { queueItemMatchesByPath(item, candidateSlug: $0.slug) }) {
            return c
        }
        guard item.topic_slug?.isEmpty == false else { return nil }
        return carousels.first(where: { queueItemMatchesByTopicSlug(item, candidateSlug: $0.slug) })
    }

    /// Step 1: does `item.carousel_path`'s basename equal `slug`?
    static func queueItemMatchesByPath(_ item: ReviewItem, candidateSlug slug: String) -> Bool {
        guard let p = item.carousel_path else { return false }
        let trimmed = p.hasSuffix("/") ? String(p.dropLast()) : p
        let pathSlug = (trimmed as NSString).lastPathComponent
        return pathSlug.isEmpty == false && pathSlug == slug
    }

    /// Steps 2+3: does `item.topic_slug` match `slug` exactly (legacy schema) or via the
    /// anchored FSM `date-topic_slug-id8` pattern?
    static func queueItemMatchesByTopicSlug(_ item: ReviewItem, candidateSlug slug: String) -> Bool {
        guard let ts = item.topic_slug, ts.isEmpty == false else { return false }
        if ts == slug { return true }
        let escaped = NSRegularExpression.escapedPattern(for: ts)
        let pattern = "^\\d{4}-\\d{2}-\\d{2}-\(escaped)-[0-9a-f]{6,}$"
        guard let re = try? NSRegularExpression(pattern: pattern) else { return false }
        let r = NSRange(slug.startIndex..., in: slug)
        return re.firstMatch(in: slug, range: r) != nil
    }

    // MARK: - A2 complete-or-nothing gate (2026-07-16, Zero mandate: "the app must NEVER
    // receive drafted carousels with a single/partial slide — complete or nothing")

    /// Count of on-disk dirs the gate excluded on the MOST RECENT `scanCarousels` call
    /// (reset at the top of each scan). Exclusion must be observable, not silent (scar
    /// #2, esiste≠armato) — this is the cheapest surface that doesn't require threading a
    /// new return type through every call site (AppState, galleryproof, and the test
    /// harness all call `scanCarousels() -> [Carousel]` today). AppState republishes it so
    /// GalleryView can show "N nascosti" next to the existing carousel count.
    private(set) static var excludedIncompleteCount: Int = 0

    private static func logGateExclusion(slug: String, reason: String) {
        FileHandle.standardError.write("wr2-gate: excluded '\(slug)' — \(reason)\n".data(using: .utf8)!)
        excludedIncompleteCount += 1
    }

    /// Resolve the DECLARED slide count for an on-disk carousel directory — the number the
    /// gate compares against the REAL PNG count. Three sources, first hit wins:
    ///  (a) `slides.json` in the dir — count of entries in the `slides` array (or the bare
    ///      top-level array in older files). NEVER the top-level `slide_count` int field:
    ///      that metadata can go stale after an in-place revise (scar #9 — ground fact
    ///      2026-07-16: 13 live queue entries found off-by-one after post-draft edits that
    ///      never re-derived it; trusting the array length itself is what the render
    ///      pipeline's own A1 gate does, so the app agrees with the producer).
    ///  (b) `manifest.json` `total_slides` — the external-import path
    ///      (`wr2_carousel_import.py`, MIN_SLIDES=1) writes this shape with no slides.json.
    ///  (c) the review queue's `slide_count`, joined via the SAME path/topic_slug
    ///      resolution `matchCarousel` uses.
    /// `nil` = undeclarable — no source exists, so the dir is not eligible for the gallery
    /// at all (see scanCarousels): silently trusting raw disk PNGs is the disease, not the cure.
    static func declaredSlideCount(in dir: URL, slug: String, queue: [ReviewItem]) -> Int? {
        if let n = slideCountFromSlidesJSON(in: dir) { return n }
        if let n = slideCountFromManifest(in: dir) { return n }
        return queueDeclaredSlideCount(forSlug: slug, in: queue)
    }

    private static func slideCountFromSlidesJSON(in dir: URL) -> Int? {
        let url = dir.appendingPathComponent("slides.json")
        guard let data = try? Data(contentsOf: url),
              let obj = try? JSONSerialization.jsonObject(with: data) else { return nil }
        if let arr = obj as? [[String: Any]] { return arr.count }
        if let d = obj as? [String: Any], let arr = d["slides"] as? [[String: Any]] { return arr.count }
        return nil
    }

    private static func slideCountFromManifest(in dir: URL) -> Int? {
        let url = dir.appendingPathComponent("manifest.json")
        guard let data = try? Data(contentsOf: url),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return nil }
        return obj["total_slides"] as? Int
    }

    private static func queueDeclaredSlideCount(forSlug slug: String, in queue: [ReviewItem]) -> Int? {
        if let item = queue.first(where: { queueItemMatchesByPath($0, candidateSlug: slug) }) {
            return item.slide_count
        }
        if let item = queue.first(where: { queueItemMatchesByTopicSlug($0, candidateSlug: slug) }) {
            return item.slide_count
        }
        return nil
    }

    // MARK: - Carousel gallery scan

    static func scanCarousels(carouselRoot root: URL? = nil,
                              queue: [ReviewItem] = []) -> [Carousel] {
        let fm = FileManager.default
        let croot = root ?? carouselRoot()
        guard let entries = try? fm.contentsOfDirectory(
            at: croot,
            includingPropertiesForKeys: [.contentModificationDateKey, .isDirectoryKey],
            options: [.skipsHiddenFiles]) else { return [] }

        excludedIncompleteCount = 0

        // build slug -> verdict/metrics/url/published maps from the queue (defensive across schemas)
        var verdictBySlug: [String: String] = [:]
        var metricsBySlug: [String: EngagementMetrics] = [:]
        var igUrlBySlug: [String: String] = [:]
        var pubAtBySlug: [String: String] = [:]
        var canvaBySlug: [String: String] = [:]
        for item in queue {
            let slug: String?
            if let p = item.carousel_path {
                let trimmed = p.hasSuffix("/") ? String(p.dropLast()) : p
                slug = trimmed.components(separatedBy: "/").last
            } else {
                slug = item.topic_slug
            }
            guard let s = slug else { continue }
            if let v = item.critic_overall_verdict ?? item.state {
                verdictBySlug[s] = v
            }
            if let m = item.engagement_metrics {
                metricsBySlug[s] = m
            }
            if let u = item.instagram_post_url {
                igUrlBySlug[s] = u
            }
            if let a = item.instagram_published_at {
                pubAtBySlug[s] = a
            }
            if let c = item.canvaLink {
                canvaBySlug[s] = c
            }
        }

        var carousels: [Carousel] = []
        for dir in entries {
            let isDir = (try? dir.resourceValues(forKeys: [.isDirectoryKey]))?.isDirectory ?? false
            guard isDir else { continue }
            let slug = dir.lastPathComponent
            if slug.hasPrefix("_") { continue }   // skip _archived-*, etc.

            let slidesDir = dir.appendingPathComponent("slides", isDirectory: true)
            let pngs = slidePNGs(in: slidesDir)
            guard pngs.isEmpty == false else { continue }   // only real carousels

            // A2 complete-or-nothing gate (mandate 2026-07-16): a drafted/unpublished
            // carousel is listed ONLY when the real PNG count matches its DECLARED count.
            // Published/history entries are exempt — immutable, REPOINT-guarded, and
            // already passed the render pipeline's own completeness gate before going
            // live, so a later local drift here must never hide them retroactively.
            let published = pubAtBySlug[slug] != nil || igUrlBySlug[slug] != nil
            let declared = declaredSlideCount(in: dir, slug: slug, queue: queue)
            if published == false {
                guard let d = declared else {
                    logGateExclusion(slug: slug,
                                      reason: "undeclarable — no slides.json/manifest.json/queue slide_count")
                    continue
                }
                guard pngs.count == d else {
                    logGateExclusion(slug: slug, reason: "incomplete — disk=\(pngs.count) declared=\(d)")
                    continue
                }
            }

            let mod = (try? dir.resourceValues(forKeys: [.contentModificationDateKey]))?
                .contentModificationDate ?? Date.distantPast
            let brief = readBrief(in: dir)

            carousels.append(Carousel(
                slug: slug,
                directory: dir,
                slidesDir: slidesDir,
                slidePNGs: pngs,
                modified: mod,
                topic: brief?.topic,
                domain: brief?.domain,
                criticVerdict: verdictBySlug[slug],
                slideCount: declared ?? pngs.count,   // displayed count = declared, never raw disk
                imagegenFallback: detectImagegenFallback(in: dir),
                coverURL: coverURL(slidesDir: slidesDir, slidePNGs: pngs),
                metrics: metricsBySlug[slug],
                instagramURL: igUrlBySlug[slug],
                publishedAt: pubAtBySlug[slug],
                canvaURL: canvaBySlug[slug]))
        }

        // Second pass — published carousels that live ONLY in the queue (no on-disk render).
        // The Graph-API backfill (2026-06-23) injected ~45 already-published IG carousels with
        // engagement metrics but no slides/ folder. The folder scan above can never surface them,
        // so the gallery would show 0 of them ("apro la app e non è aggiornata"). We add them here
        // as IG-only carousels: no local PNG (cover placeholder), metrics/URL/topic/date from queue.
        let physicalSlugs = Set(carousels.map { $0.slug })
        for item in queue {
            guard let igURL = item.instagram_post_url, igURL.isEmpty == false else { continue }
            let slug = item.topic_slug
                ?? item.carousel_path.map { ($0 as NSString).lastPathComponent }
                ?? item.id
            guard physicalSlugs.contains(slug) == false else { continue }

            let mod = item.instagram_published_at.flatMap(parsePublishedAt) ?? Date.distantPast
            carousels.append(Carousel(
                slug: slug,
                directory: croot.appendingPathComponent(slug, isDirectory: true), // notional; not on disk
                slidesDir: croot.appendingPathComponent(slug, isDirectory: true)
                    .appendingPathComponent("slides", isDirectory: true),
                slidePNGs: [],
                modified: mod,
                topic: item.topic ?? humanizeSlugBasic(slug),
                domain: item.domain,
                criticVerdict: item.critic_overall_verdict ?? item.state,
                slideCount: item.slide_count ?? 0,
                imagegenFallback: false,
                coverURL: nil,
                metrics: item.engagement_metrics,
                instagramURL: igURL,
                publishedAt: item.instagram_published_at,
                canvaURL: item.canvaLink))
        }

        return carousels.sorted { $0.modified > $1.modified }
    }

    /// Parse the IG `instagram_published_at` (e.g. "2025-09-05T09:45:00+0000").
    /// Tries ISO-8601 with internet date-time + fractional/zone variants.
    static func parsePublishedAt(_ s: String) -> Date? {
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime]
        if let d = iso.date(from: s) { return d }
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = iso.date(from: s) { return d }
        // fallback: "+0000" without colon, plain formatter
        let df = DateFormatter()
        df.locale = Locale(identifier: "en_US_POSIX")
        df.dateFormat = "yyyy-MM-dd'T'HH:mm:ssZ"
        return df.date(from: s)
    }

    /// Foundation-pure slug humanizer (the SwiftUI side has its own `humanizeSlug`).
    private static func humanizeSlugBasic(_ slug: String) -> String {
        slug.replacingOccurrences(of: "-", with: " ")
            .replacingOccurrences(of: "_", with: " ")
            .capitalized
    }

    /// Sorted slide PNGs, excluding chrome (logo, hero source jpgs, placeholders,
    /// hammurabi-stele). Slides are named NN.png (zero-padded in recent runs,
    /// single-digit in older ones) — sort numerically.
    static func slidePNGs(in slidesDir: URL) -> [URL] {
        let fm = FileManager.default
        guard let files = try? fm.contentsOfDirectory(
            at: slidesDir, includingPropertiesForKeys: nil,
            options: [.skipsHiddenFiles]) else { return [] }
        let chrome: Set<String> = ["logo.png"]
        let slides = files.filter { url in
            guard url.pathExtension.lowercased() == "png" else { return false }
            let name = url.lastPathComponent.lowercased()
            if chrome.contains(name) { return false }
            if name.hasPrefix("placeholder") { return false }
            // slide files are <digits>.png ; reject anything non-numeric stem
            let stem = url.deletingPathExtension().lastPathComponent
            return stem.allSatisfy { $0.isNumber } && stem.isEmpty == false
        }
        return slides.sorted { a, b in
            let na = Int(a.deletingPathExtension().lastPathComponent) ?? 0
            let nb = Int(b.deletingPathExtension().lastPathComponent) ?? 0
            return na < nb
        }
    }

    /// The cover image of a carousel = the lowest-numbered slide PNG. nil if none.
    static func coverURL(slidesDir: URL, slidePNGs: [URL]) -> URL? {
        return slidePNGs.first   // slidePNGs is already numerically sorted ascending
    }

    // MARK: - imagegen fallback detection

    /// True if the carousel fell back to the Hammurabi texture / placeholder because fresh
    /// hero images could NOT be generated (Codex/FlowKit quota exhausted). Read from
    /// slides.json `image_source` markers. This is what lets the gallery flag "fresh vs fallback".
    static func detectImagegenFallback(in carouselDir: URL) -> Bool {
        let url = carouselDir.appendingPathComponent("slides.json")
        guard let data = try? Data(contentsOf: url),
              let obj = try? JSONSerialization.jsonObject(with: data) else { return false }
        let slides: [[String: Any]]
        if let arr = obj as? [[String: Any]] { slides = arr }
        else if let dict = obj as? [String: Any], let arr = dict["slides"] as? [[String: Any]] { slides = arr }
        else { return false }

        let markers = ["imagegen_unavailable", "quota_exhausted", "quota exhausted",
                       "not_provisioned", "codex_quota", "flowkit_not"]
        for s in slides {
            let src = (s["image_source"] as? String ?? "").lowercased()
            if markers.contains(where: { src.contains($0) }) { return true }
        }
        return false
    }

    // MARK: - brief.json

    struct Brief: Decodable {
        let topic: String?
        let domain: String?
        let key_facts: [String]?
        let key_numbers: [String]?
        let archetype: String?
    }

    static func readBrief(in carouselDir: URL) -> Brief? {
        let url = carouselDir.appendingPathComponent("brief.json")
        guard let data = try? Data(contentsOf: url) else { return nil }
        // key_numbers may be heterogeneous in older briefs; decode leniently
        return try? lenientBriefDecode(data)
    }

    private static func lenientBriefDecode(_ data: Data) throws -> Brief {
        guard let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw NSError(domain: "WarRoom", code: 1)
        }
        func strArray(_ v: Any?) -> [String]? {
            if let a = v as? [String] { return a }
            if let a = v as? [Any] { return a.map { String(describing: $0) } }
            return nil
        }
        return Brief(
            topic: obj["topic"] as? String,
            domain: obj["domain"] as? String,
            key_facts: strArray(obj["key_facts"]),
            key_numbers: strArray(obj["key_numbers"]),
            archetype: obj["archetype"] as? String)
    }

    // MARK: - Review queue

    // M3 fix: cache the last good decode. If the pipeline is mid-write and the JSON is
    // momentarily truncated, keep the previous result instead of flashing an empty queue
    // (which would wipe every gallery verdict badge for one poll cycle).
    private static var lastGoodQueue: [ReviewItem] = []

    static func readQueue(queueFile url: URL? = nil) -> [ReviewItem] {
        let file = url ?? queueFile()
        guard let data = try? Data(contentsOf: file) else { return lastGoodQueue }
        let dec = JSONDecoder()
        if let items = try? dec.decode([ReviewItem].self, from: data) {
            lastGoodQueue = items
            return items
        }
        return lastGoodQueue   // decode failed (partial write) → keep last known good
    }
}
