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
    static func matchCarousel(for item: ReviewItem, in carousels: [Carousel]) -> Carousel? {
        if let p = item.carousel_path {
            let trimmed = p.hasSuffix("/") ? String(p.dropLast()) : p
            let slug = (trimmed as NSString).lastPathComponent
            if slug.isEmpty == false,
               let c = carousels.first(where: { $0.slug == slug }) { return c }
        }
        guard let ts = item.topic_slug, ts.isEmpty == false else { return nil }
        if let c = carousels.first(where: { $0.slug == ts }) { return c }
        let escaped = NSRegularExpression.escapedPattern(for: ts)
        let pattern = "^\\d{4}-\\d{2}-\\d{2}-\(escaped)-[0-9a-f]{6,}$"
        guard let re = try? NSRegularExpression(pattern: pattern) else { return nil }
        return carousels.first(where: { c in
            let r = NSRange(c.slug.startIndex..., in: c.slug)
            return re.firstMatch(in: c.slug, range: r) != nil
        })
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
                slideCount: pngs.count,
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
