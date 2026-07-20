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
    /// substring (scar #3, guard-over-match), and each step is a GENUINELY SEPARATE
    /// pass over the full candidate set before falling to the next — never combined
    /// into one predicate. A combined pass lets ARRAY ORDER decide between two steps
    /// of different precedence whenever both would match different candidates
    /// (Codex red-team finding #1, 2026-07-16: an item with topic_slug=="golden-visa"
    /// must always resolve to the exact dir `golden-visa`, never to a same-topic dated
    /// FSM dir like `2026-07-08-golden-visa-deadbeef` just because that happened to
    /// come first in a modified-descending sort):
    ///  1. basename of `carousel_path` (authoritative — same join scanCarousels uses)
    ///  2. `topic_slug` exact (legacy schema)
    ///  3. anchored FSM pattern `^\d{4}-\d{2}-\d{2}-<topic_slug>-[0-9a-f]{6,}$`
    ///
    /// Steps extracted into `queueItemMatchesByPath`/`queueItemMatchesByExactTopicSlug`/
    /// `queueItemMatchesByFSMRegex` so the A2 completeness gate below (which only has a
    /// candidate SLUG, not a built Carousel array, while it's still deciding whether the
    /// dir belongs in the gallery at all) can reuse the exact same resolution rule instead
    /// of growing a second, driftable copy (scar #3: a guard and its untested twin are how
    /// over/under-match pairs are born).
    static func matchCarousel(for item: ReviewItem, in carousels: [Carousel]) -> Carousel? {
        if let c = carousels.first(where: { queueItemMatchesByPath(item, candidateSlug: $0.slug) }) {
            return c
        }
        guard item.topic_slug?.isEmpty == false else { return nil }
        if let c = carousels.first(where: { queueItemMatchesByExactTopicSlug(item, candidateSlug: $0.slug) }) {
            return c
        }
        return carousels.first(where: { queueItemMatchesByFSMRegex(item, candidateSlug: $0.slug) })
    }

    /// Step 1: does `item.carousel_path`'s basename equal `slug`?
    static func queueItemMatchesByPath(_ item: ReviewItem, candidateSlug slug: String) -> Bool {
        guard let p = item.carousel_path else { return false }
        let trimmed = p.hasSuffix("/") ? String(p.dropLast()) : p
        let pathSlug = (trimmed as NSString).lastPathComponent
        return pathSlug.isEmpty == false && pathSlug == slug
    }

    /// Step 2: does `item.topic_slug` match `slug` EXACTLY (legacy schema)? Kept as its
    /// own pass, never combined with step 3 — see `matchCarousel` doc above.
    static func queueItemMatchesByExactTopicSlug(_ item: ReviewItem, candidateSlug slug: String) -> Bool {
        guard let ts = item.topic_slug, ts.isEmpty == false else { return false }
        return ts == slug
    }

    /// Step 3: does `item.topic_slug` match `slug` via the anchored FSM
    /// `date-topic_slug-id8` pattern? Only tried after steps 1+2 both miss.
    static func queueItemMatchesByFSMRegex(_ item: ReviewItem, candidateSlug slug: String) -> Bool {
        guard let ts = item.topic_slug, ts.isEmpty == false else { return false }
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

    /// Delta-emission memory (2026-07-18 wound: ~29 gate-exclusion lines re-emitted to
    /// wr2control.err on EVERY `scanCarousels` refresh — ~10s cadence — grew the file
    /// ~30MB/day for a STEADY-STATE set of exclusions that never changed). `lastLoggedExclusions`
    /// persists ACROSS scans; `currentScanExclusions` accumulates the CURRENT scan only. A
    /// line is written to stderr ONLY the first time a `slug|reason` key appears — the SAME
    /// key on the NEXT scan stays silent. `excludedIncompleteCount` still increments on
    /// EVERY exclusion, every scan (the "N nascosti" GalleryView count must keep counting) —
    /// only the stderr WRITE is deduped, never the count.
    private static var lastLoggedExclusions: Set<String> = []
    private static var currentScanExclusions: Set<String> = []

    /// Injectable stderr sink (test seam, 2026-07-18). Production default writes to real
    /// stderr; tests swap this for an array-recorder so delta-emission is assertable
    /// deterministically without capturing real FileHandle.standardError.
    static var exclusionEmit: (String) -> Void = {
        FileHandle.standardError.write($0.data(using: .utf8)!)
    }

    private static func logGateExclusion(slug: String, reason: String) {
        let key = "\(slug)|\(reason)"
        currentScanExclusions.insert(key)
        excludedIncompleteCount += 1
        guard lastLoggedExclusions.contains(key) == false else { return }
        exclusionEmit("wr2-gate: excluded '\(slug)' — \(reason)\n")
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

    /// Queue-based fallback (source c): resolve `slug`'s declared count from the review
    /// queue, at the SAME path → exact-topic_slug → FSM-regex precedence `matchCarousel`
    /// uses — each tier tried in full before falling to the next, and each tier
    /// considers ONLY items that actually carry a `slide_count` (Codex red-team finding
    /// #2, 2026-07-16: the previous version returned `nil` the instant the FIRST
    /// path-matching item lacked a count, even when a later item at the SAME tier had
    /// one — and combined exact+regex into one pass, letting queue array order silently
    /// pick between two items that disagree). If MULTIPLE items at the SAME tier declare
    /// DIFFERENT counts, that's genuine ambiguity — fail closed (nil, i.e. undeclarable)
    /// rather than silently picking the first; the gate logs the specific reason via
    /// `queueAmbiguityDescription` below (kept pure/side-effect-free here so this
    /// function is safe to call from both `declaredSlideCount` and the diagnostic path
    /// without double-incrementing `excludedIncompleteCount`).
    private static func queueDeclaredSlideCount(forSlug slug: String, in queue: [ReviewItem]) -> Int? {
        for matcher in [queueItemMatchesByPath, queueItemMatchesByExactTopicSlug, queueItemMatchesByFSMRegex] {
            let counts = queue.filter { matcher($0, slug) }.compactMap(\.slide_count)
            guard counts.isEmpty == false else { continue }   // no count-bearing hit at this tier — try next
            let distinct = Set(counts)
            return distinct.count == 1 ? distinct.first : nil   // >1 distinct value → ambiguous → nil, stop here
        }
        return nil
    }

    /// Diagnostic-only companion to `queueDeclaredSlideCount`: if a dir's declared count
    /// came back nil specifically because of a same-tier queue disagreement (not a true
    /// absence of any source), describe the conflicting values for the gate's exclusion
    /// log. Pure — never mutates state — so calling it purely to build a log message
    /// never double-counts `excludedIncompleteCount` (Codex red-team finding #2).
    private static func queueAmbiguityDescription(forSlug slug: String, in queue: [ReviewItem]) -> String? {
        for matcher in [queueItemMatchesByPath, queueItemMatchesByExactTopicSlug, queueItemMatchesByFSMRegex] {
            let counts = queue.filter { matcher($0, slug) }.compactMap(\.slide_count)
            guard counts.isEmpty == false else { continue }
            let distinct = Set(counts)
            return distinct.count > 1 ? "ambiguous queue slide_count at this precedence tier: \(distinct.sorted())" : nil
        }
        return nil
    }

    /// Resolve the ONE queue item that authoritatively describes a physical directory
    /// `slug`, via the same path → exact-topic_slug → FSM-regex precedence
    /// `matchCarousel` uses. Used to build the per-slug verdict/metrics/published maps
    /// below so a physical dir never misses its own queue row just because a map was
    /// indexed by the queue's raw fields instead of resolved against the actual
    /// directory name (Codex red-team finding #4, 2026-07-16).
    private static func resolveQueueItem(forSlug slug: String, in queue: [ReviewItem]) -> ReviewItem? {
        if let item = queue.first(where: { queueItemMatchesByPath($0, candidateSlug: slug) }) { return item }
        if let item = queue.first(where: { queueItemMatchesByExactTopicSlug($0, candidateSlug: slug) }) { return item }
        return queue.first(where: { queueItemMatchesByFSMRegex($0, candidateSlug: slug) })
    }

    /// True if `item` resolves (via the canonical path/exact/regex precedence) to ANY
    /// of the given physical directory slugs. Used by the second pass to avoid
    /// spawning a duplicate "virtual" carousel for a queue row that already has a real
    /// on-disk dir — even one the completeness gate excluded (Codex red-team finding
    /// #4: previously the dedup set held only gate-SURVIVING slugs, checked via a raw
    /// topic_slug/basename guess, so a physical dir named differently from the queue's
    /// truncated topic_slug got excluded by the gate AND re-created here as a phantom
    /// virtual entry with no local cover/slides).
    private static func resolvesToPhysicalDir(_ item: ReviewItem, physicalSlugs: [String]) -> Bool {
        physicalSlugs.contains(where: { queueItemMatchesByPath(item, candidateSlug: $0) })
            || physicalSlugs.contains(where: { queueItemMatchesByExactTopicSlug(item, candidateSlug: $0) })
            || physicalSlugs.contains(where: { queueItemMatchesByFSMRegex(item, candidateSlug: $0) })
    }

    // MARK: - Gallery recency sort key (§D, 2026-07-17 — "re-rendered cards must not
    // stay buried under their original date")

    /// Newest on-disk modification date among the given slide PNGs, or `nil` if empty.
    static func newestSlideModificationDate(_ slidePNGs: [URL]) -> Date? {
        slidePNGs
            .compactMap { (try? $0.resourceValues(forKeys: [.contentModificationDateKey]))?.contentModificationDate }
            .max()
    }

    /// The gallery "recent" sort key for an on-disk carousel. A directory's own mtime
    /// bumps only on add/remove/rename of entries WITHIN it — on APFS/HFS+, overwriting
    /// an EXISTING file's bytes in place (a re-render replacing slides/1.png with fresh
    /// content, same filename) does NOT bump the directory's mtime, so a carousel
    /// re-rendered today kept sorting under its original creation date (ground
    /// 2026-07-17: a carousel re-rendered 16/7 stayed buried under its 2026-07-14 dir).
    /// Fix: take the max of the directory mtime and the newest slide PNG's OWN mtime —
    /// the slide FILE's mtime DOES bump on an in-place overwrite.
    ///
    /// Published carousels are the one exception: they sort by `publishedAt` (when
    /// parseable), never by file-touch recency — an unrelated LATER touch of a
    /// published carousel's files (e.g. a metrics backfill writing into the same dir)
    /// must never bump its position; publication date is what matters for a live post.
    static func recencySortKey(
        dirModified: Date, newestSlideModified: Date?, isPublished: Bool, publishedAt: String?
    ) -> Date {
        if isPublished, let pubAt = publishedAt, let parsed = parsePublishedAt(pubAt) {
            return parsed
        }
        return max(dirModified, newestSlideModified ?? Date.distantPast)
    }

    // MARK: - Duplicate virtual-entry detection (§E, 2026-07-17)

    /// Extract the IG shortcode (the `/p/<code>/` or `/reel/<code>/` segment) from a
    /// post/reel URL, or `nil` if the string doesn't look like one. Mirrors
    /// `QueueWriter.extractMediaID`'s shape (Swift) and Python's
    /// `extract_ig_shortcode`/`ExternalPostRegistration`'s pattern — used here so a
    /// cosmetic difference (trailing slash, query string) between two URLs referring to
    /// the SAME post doesn't defeat a real duplicate match (entity-based match, not
    /// bare substring — scar #3 discipline).
    static func igShortcode(from url: String) -> String? {
        let s = url.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let r = s.range(of: #"/(p|reel|tv)/([^/?#]+)"#, options: .regularExpression) else { return nil }
        let seg = String(s[r])
        return seg.components(separatedBy: "/").filter { !$0.isEmpty }.last
    }

    /// True if `igURL` refers to the SAME Instagram post as any URL in `knownURLs`
    /// (compared by shortcode when both parse as IG post/reel URLs, else by trimmed
    /// exact string). Used to hide a virtual `ig-*`-style queue entry when a REAL
    /// on-disk carousel already carries the same `instagram_post_url` (live case:
    /// `ig-DaxDJuYFPi6` duplicating `bali-pma-rental-crackdown`'s own queue-joined URL).
    static func matchesAnyPhysicalInstagramURL(_ igURL: String, knownURLs: [String]) -> Bool {
        let target = igURL.trimmingCharacters(in: .whitespacesAndNewlines)
        guard target.isEmpty == false else { return false }
        let targetCode = igShortcode(from: target)
        return knownURLs.contains { raw in
            let known = raw.trimmingCharacters(in: .whitespacesAndNewlines)
            guard known.isEmpty == false else { return false }
            if let tc = targetCode, let kc = igShortcode(from: known) { return tc == kc }
            return known == target
        }
    }

    // MARK: - Carousel gallery scan

    static func scanCarousels(carouselRoot root: URL? = nil,
                              queue: [ReviewItem] = []) -> [Carousel] {
        // Reset BEFORE any I/O, on every exit path including an early return below — a
        // stale nonzero count surviving a failed/empty scan would show "N nascosti" over
        // a gallery that simply failed to read, its own silent-lie (Codex red-team
        // finding #5, 2026-07-16).
        excludedIncompleteCount = 0
        // Delta-emission scan-local accumulator (2026-07-18) — NOT `lastLoggedExclusions`,
        // which persists across scans and is only committed at the function's FINAL
        // `return` below, once the scan has reached its natural end. The early
        // `guard let entries = ... else { return [] }` a few lines down is a DIFFERENT
        // exit path that never reaches that commit: a transient dir-read failure must
        // never wipe the dedup memory, or the next good scan would re-log every
        // exclusion (re-introducing the storm this fix exists to stop).
        currentScanExclusions = []

        let fm = FileManager.default
        let croot = root ?? carouselRoot()
        guard let entries = try? fm.contentsOfDirectory(
            at: croot,
            includingPropertiesForKeys: [.contentModificationDateKey, .isDirectoryKey],
            options: [.skipsHiddenFiles]) else { return [] }

        // Every physical (non-archived) directory slug on disk, gathered BEFORE gating
        // or queue-joining — two downstream steps need the FULL set, not just
        // gate-survivors: (1) the per-slug queue join below must resolve against every
        // real dir so one that ALSO gets excluded by the completeness gate still gets
        // correct published/verdict/metrics data; (2) the second pass's dedup must
        // never spawn a duplicate for a dir that exists physically but didn't survive
        // the gate (Codex red-team finding #4, 2026-07-16).
        var physicalSlugs: [String] = []
        for dir in entries {
            let isDir = (try? dir.resourceValues(forKeys: [.isDirectoryKey]))?.isDirectory ?? false
            guard isDir else { continue }
            let slug = dir.lastPathComponent
            if slug.hasPrefix("_") { continue }
            physicalSlugs.append(slug)
        }

        // Resolve each physical slug to ITS ONE queue item via the canonical
        // precedence — never by indexing the queue on its own raw fields (Codex
        // finding #4: that let a dir silently miss its own publication/verdict data
        // whenever the FSM directory name diverges from the queue's truncated
        // topic_slug). `publishedBySlug` uses the canonical `isQueueItemPublished`
        // predicate, not bare field presence (Codex finding #3: an empty-string
        // `instagram_post_url` used to count as "published" and bypass the gate).
        var verdictBySlug: [String: String] = [:]
        var stateBySlug: [String: String] = [:]
        var metricsBySlug: [String: EngagementMetrics] = [:]
        var igUrlBySlug: [String: String] = [:]
        var pubAtBySlug: [String: String] = [:]
        var canvaBySlug: [String: String] = [:]
        var publishedBySlug: [String: Bool] = [:]
        for slug in physicalSlugs {
            guard let item = resolveQueueItem(forSlug: slug, in: queue) else { continue }
            if let v = item.critic_overall_verdict ?? item.state { verdictBySlug[slug] = v }
            // Raw `state`, kept SEPARATE from verdictBySlug above (which is verdict-first
            // and feeds the critic-verdict badge only) — see Carousel.state doc comment
            // for why a stale verdict must never mask a fresh render_incomplete state.
            if let s = item.state { stateBySlug[slug] = s }
            if let m = item.engagement_metrics { metricsBySlug[slug] = m }
            if let u = item.instagram_post_url { igUrlBySlug[slug] = u }
            if let a = item.instagram_published_at { pubAtBySlug[slug] = a }
            if let c = item.canvaLink { canvaBySlug[slug] = c }
            publishedBySlug[slug] = isQueueItemPublished(item)
        }

        var carousels: [Carousel] = []
        for dir in entries {
            let isDir = (try? dir.resourceValues(forKeys: [.isDirectoryKey]))?.isDirectory ?? false
            guard isDir else { continue }
            let slug = dir.lastPathComponent
            if slug.hasPrefix("_") { continue }   // skip _archived-*, etc.

            let slidesDir = dir.appendingPathComponent("slides", isDirectory: true)
            // Distinguish a genuinely-empty/not-yet-rendered slides/ dir from one that
            // exists but is momentarily unreadable (permission/I/O flap): the lenient
            // `slidePNGs` collapses both to `[]` via `try?`, so an I/O error was
            // previously silently dropped with no log/counter — indistinguishable from
            // a real empty dir (Codex red-team finding #5, 2026-07-16).
            let slidesDirReadable = (try? fm.contentsOfDirectory(
                at: slidesDir, includingPropertiesForKeys: nil, options: [.skipsHiddenFiles])) != nil
            let pngs = slidePNGs(in: slidesDir)
            guard pngs.isEmpty == false else {
                if slidesDirReadable == false {
                    logGateExclusion(slug: slug, reason: "slides/ unreadable (I/O error) — not a genuine empty carousel")
                }
                continue
            }

            // A2 complete-or-nothing gate (mandate 2026-07-16): a drafted/unpublished
            // carousel is listed ONLY when the real PNG count matches its DECLARED
            // count. Published/history entries are exempt — immutable, REPOINT-guarded,
            // and already passed the render pipeline's own completeness gate before
            // going live, so a later local drift here must never hide them
            // retroactively.
            let published = publishedBySlug[slug] ?? false
            let declared = declaredSlideCount(in: dir, slug: slug, queue: queue)
            if published == false {
                guard let d = declared else {
                    let reason = queueAmbiguityDescription(forSlug: slug, in: queue)
                        ?? "undeclarable — no slides.json/manifest.json/queue slide_count"
                    logGateExclusion(slug: slug, reason: reason)
                    continue
                }
                guard pngs.count == d else {
                    logGateExclusion(slug: slug, reason: "incomplete — disk=\(pngs.count) declared=\(d)")
                    continue
                }
            }

            // §D recency fix (2026-07-17): dir mtime alone misses in-place re-renders
            // (same filenames, fresh bytes) — see recencySortKey's doc comment.
            let dirModified = (try? dir.resourceValues(forKeys: [.contentModificationDateKey]))?
                .contentModificationDate ?? Date.distantPast
            let mod = recencySortKey(
                dirModified: dirModified,
                newestSlideModified: newestSlideModificationDate(pngs),
                isPublished: published,
                publishedAt: pubAtBySlug[slug])
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
                canvaURL: canvaBySlug[slug],
                state: stateBySlug[slug]))
        }

        // Second pass — published carousels that live ONLY in the queue (no on-disk render).
        // The Graph-API backfill (2026-06-23) injected ~45 already-published IG carousels with
        // engagement metrics but no slides/ folder. The folder scan above can never surface them,
        // so the gallery would show 0 of them ("apro la app e non è aggiornata"). We add them here
        // as IG-only carousels: no local PNG (cover placeholder), metrics/URL/topic/date from queue.
        // Dedup checks EVERY physical dir (not just gate-survivors) via the canonical resolver
        // (not a raw topic_slug/basename guess) — otherwise a physical dir the gate excluded, or
        // one whose queue row's topic_slug is a truncated FSM form, gets a duplicate phantom
        // entry here that shadows its real cover/slides (Codex red-team finding #4, 2026-07-16).
        //
        // §E dedup (2026-07-17): the slug/topic_slug-based resolver above only catches a
        // duplicate when THIS item's OWN slug fields happen to match a physical dir. A
        // SEPARATE queue row (e.g. an independent Graph-API backfill entry, `ig-<mediaid>`)
        // whose slug fields point nowhere but whose `instagram_post_url` is the SAME post
        // a real carousel already displays is missed by that check — live case:
        // `ig-DaxDJuYFPi6` duplicating `bali-pma-rental-crackdown`'s own queue-joined URL.
        // `igUrlBySlug` already holds, for every physical dir, the URL its OWN resolved
        // queue item carries — comparing against those values (not just slugs) catches it.
        let physicalInstagramURLs = Array(igUrlBySlug.values)
        for item in queue {
            guard let igURL = item.instagram_post_url,
                  igURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty == false else { continue }
            guard resolvesToPhysicalDir(item, physicalSlugs: physicalSlugs) == false else { continue }
            guard matchesAnyPhysicalInstagramURL(igURL, knownURLs: physicalInstagramURLs) == false else { continue }
            let slug = item.topic_slug
                ?? item.carousel_path.map { ($0 as NSString).lastPathComponent }
                ?? item.id

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
                canvaURL: item.canvaLink,
                state: item.state))
        }

        // Commit the delta-emission memory ONLY here — the scan reached its end without
        // hitting the early `return []` above, so every exclusion this cycle was a real,
        // fully-resolved verdict (not a partial pass cut short by an I/O failure).
        lastLoggedExclusions = currentScanExclusions
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
        // Whole-array decode failed. One malformed entry must not blank the other N-1
        // valid ones (they'd otherwise fall all the way back to the stale M3 cache).
        // First confirm the file is a COMPLETE, well-formed JSON array at all — a
        // mid-write truncation is still not valid JSON of ANY shape, and must keep
        // hitting the M3 last-good fallback exactly as before.
        guard let jsonObject = try? JSONSerialization.jsonObject(with: data),
              let elements = jsonObject as? [Any] else {
            return lastGoodQueue   // not a complete JSON array → partial write, keep last good
        }
        // (an empty [] array is already handled by the fast-path decode above)
        var recovered: [ReviewItem] = []
        var skipped = 0
        for element in elements {
            guard let dict = element as? [String: Any],
                  let elementData = try? JSONSerialization.data(withJSONObject: dict),
                  let item = try? dec.decode(ReviewItem.self, from: elementData) else {
                skipped += 1
                continue
            }
            recovered.append(item)
        }
        guard recovered.isEmpty == false else {
            // Every entry failed — a systemic/schema break, not per-entry corruption.
            // Don't blank the gallery (M3 anti-blank spirit extends here too) — but stay
            // observable (scar #2, esiste≠armato): a totally-incompatible new schema must
            // be visible in the log, not a silent stale-cache hold forever.
            FileHandle.standardError.write(
                "wr2-queue: all \(elements.count) entries failed to decode — keeping \(lastGoodQueue.count) last-good (possible schema break)\n"
                    .data(using: .utf8)!)
            return lastGoodQueue
        }
        lastGoodQueue = recovered
        if skipped > 0 {
            FileHandle.standardError.write(
                "wr2-queue: recovered \(recovered.count)/\(elements.count) entries, skipped \(skipped) malformed\n"
                    .data(using: .utf8)!)
        }
        return recovered
    }
}
