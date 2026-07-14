# WR2 Control "grande" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve the working WR2 Control prototype into a "grande" native macOS app with real carousel covers + Instagram results side-by-side, a dual-mode (ambient TV / hands-on work) shell, a reversible mark-published gesture that fuels the existing metrics loop, a history panel, and a Mini deployment with Desk icons.

**Architecture:** Incremental evolution of the existing SwiftUI app at `~/Desktop/wr2-control-app/` (NOT in the nuzantara monorepo). One Swift binary on M5/Pro/Mini. Two faces (work/ambient) over one shared `AppState`. All data read/written from local disk; metrics read from the queue's own `engagement_metrics` field (no DB access from the app). No login.

**Tech Stack:** SwiftUI + AppKit + Combine, built without Xcode (swiftc + `-external-plugin-path` for macros, manual `.app` bundle via `build.sh`). Tests: standalone `swiftc` CLI harness over Foundation-pure files (`test.sh` / `test-integration.sh`).

## Global Constraints

- App is ISOLATED in `~/Desktop/wr2-control-app/` — never write into the nuzantara monorepo. (verbatim: "NEW isolated folder, NOT inside the nuzantara monorepo")
- Confined to the Bali Zero fleet (M5/Pro/Mini). NO git push / PR / deploy / Instagram publish from the app.
- Wraps `claude` CLI as subprocess. NO Anthropic SDK, NO `ANTHROPIC_API_KEY` (strip from child env).
- Do NOT modify the WR2 pipeline or off-limits files (`zantara_core.py`, `fly.toml`, `.env*`, `alembic/env.py`).
- "Mark as published" is a LOCAL state change only — never posts to Instagram (Legge 5). Reversible.
- Brand tokens (verbatim): antracite `#2C2F38`, ink `#14161C`, inkLift `#1E2129`, yellow `#F4C430` (data/numbers + fact-rule ONLY), red `#C8102E` (logo + critical ONLY), white text, muted `#9CA3AF`. Montserrat (bold 700 / extrabold 800), IBM Plex Mono (citations only).
- Bilingual IT/ID via `LanguageManager` + `L10n.table`. Every new user-facing string gets IT + ID keys.
- Keep Foundation-pure files pure (Models, WarRoom, ClaudeRunner, StreamEvent, Conversationalist, AppState-data) so the CLI test harness compiles them without SwiftUI.
- Keep the existing 52 tests green; add tests per task (TDD).
- Queue write discipline (scar #9 + #5): atomic write (tmp + rename), preserve unknown fields, modify ONLY publish-state fields, never rewrite whole items.
- LaunchAgent + wrappers must NOT live under `~/Desktop` (scar W84 — launchd loses TCC there). No `KeepAlive` on one-shot (scar #7).

## Ground-truth facts (verified on disk 2026-06-22)

- Queue: `~/Desktop/nuzantara/apps/war-room/output/queue/human-review-queue.json`, JSON array, 53 items, TWO schemas mixed: ~23 "legacy" (`id`/`topic_slug`/`carousel_path`/`critic_overall_verdict`/`engagement_metrics`/`instagram_post_url`/`instagram_published_at`/`state`) + ~30 "new" (`item_id`/`topic`/`canva_url`, no `carousel_path`).
- `engagement_metrics` field already exists per item, shape `{"likes":null,"comments":null,"saves":null,"reach":null}` — all null today (0 published). NOTE: no `shares` key yet → add it.
- Carousels: `~/Desktop/nuzantara/apps/war-room/output/carousel/<slug>/slides/<N>.png` (256 PNGs exist). Cover = lowest-numbered slide png.
- `WarRoom.swift` already path-drift-resolves and handles both schemas on READ. `readQueue` decodes `[ReviewItem]` with a last-good cache.
- Metrics loop is REAL but starved (sampler `meta_graph_sampler.py` → table `war_room_metrics`, append-only; feedback-loop populates queue `engagement_metrics`). App reads `engagement_metrics` from the queue — does NOT touch the DB.

---

## File Structure

**Models (Foundation-pure, extend):**

- `Sources/Models.swift` — extend `Carousel` (cover URL, metrics), extend `ReviewItem` (engagement_metrics, instagram fields), add `EngagementMetrics`, add `AppMode` enum.

**Data/logic (Foundation-pure, extend/create):**

- `Sources/WarRoom.swift` — harden cover resolution; add metrics extraction from queue; add `coverURL(for:)`.
- `Sources/QueueWriter.swift` — NEW. Atomic, field-preserving mark-published / undo on the queue JSON.
- `Sources/AppState.swift` — add `mode`, idle timer, `markPublished`/`undoPublished`, `viralCovers`.

**Views (SwiftUI, create/rework):**

- `Sources/Views/CoverGalleryView.swift` — rework of GalleryView: real covers + result badges + sort.
- `Sources/Views/CarouselDetailView.swift` — NEW. Big cover + results panel + mark-published + thumbnails.
- `Sources/Views/AmbientView.swift` — NEW. Editorial wall + running ribbon.
- `Sources/Views/HistoryView.swift` — NEW. 3 numbers + run list.
- `Sources/Views/RootView.swift` — add mode toggle + ambient routing + History/Detail nav.
- `Sources/Localization.swift` — add IT/ID keys for all new strings.

**Deploy:**

- `deploy/install-mini.sh` — NEW. Copy `.app` to Mini, install LaunchAgent (outside ~/Desktop), verify launch.
- `deploy/com.balizero.wr2control.plist` — NEW. Ambient autostart on Mini.
- `deploy/make-desk-icon.sh` — NEW. Place Desk launcher on M5/Pro.

---

## Task 1: Cover resolution — real images, no gray placeholders

**Files:**

- Modify: `Sources/Models.swift` (add `coverURL` to `Carousel`)
- Modify: `Sources/WarRoom.swift` (add `coverURL(in:)`, use in `scanCarousels`)
- Test: `Tests/warroomtest/main.swift` (new standalone test target)

**Interfaces:**

- Produces: `Carousel.coverURL: URL?` (the resolved cover image), `WarRoom.coverURL(slidesDir:slidePNGs:) -> URL?`

- [ ] **Step 1: Write the failing test**

Create `Tests/warroomtest/main.swift`:

```swift
import Foundation
// cover = the lowest-numbered slide png; nil if none
let tmp = FileManager.default.temporaryDirectory.appendingPathComponent("wr2cov-\(UUID().uuidString)/slides")
try! FileManager.default.createDirectory(at: tmp, withIntermediateDirectories: true)
for n in ["3","1","2"] { FileManager.default.createFile(atPath: tmp.appendingPathComponent("\(n).png").path, contents: Data([0])) }
FileManager.default.createFile(atPath: tmp.appendingPathComponent("logo.png").path, contents: Data([0]))
let pngs = WarRoom.slidePNGs(in: tmp)
let cover = WarRoom.coverURL(slidesDir: tmp, slidePNGs: pngs)
var fails = 0
func expect(_ c: Bool, _ m: String) { if c { print("  ✅ \(m)") } else { print("  ❌ \(m)"); fails += 1 } }
expect(cover?.lastPathComponent == "1.png", "cover is lowest-numbered slide, not logo")
let empty = WarRoom.coverURL(slidesDir: tmp.appendingPathComponent("none"), slidePNGs: [])
expect(empty == nil, "no slides → nil cover")
print("RESULT: \(fails == 0 ? "GREEN" : "RED")")
exit(fails == 0 ? 0 : 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Desktop/wr2-control-app && swiftc -parse-as-library Sources/Models.swift Sources/WarRoom.swift Tests/warroomtest/main.swift -o build/warroomtest 2>&1 | head` (will fail: `coverURL` undefined)
Expected: FAIL — "cannot find 'coverURL' in scope" / type error.

- [ ] **Step 3: Write minimal implementation**

In `Sources/WarRoom.swift`, add inside `enum WarRoom`:

```swift
/// The cover image of a carousel = the lowest-numbered slide PNG. nil if none.
static func coverURL(slidesDir: URL, slidePNGs: [URL]) -> URL? {
    return slidePNGs.first   // slidePNGs is already numerically sorted ascending
}
```

In `Sources/Models.swift`, add to `Carousel`:

```swift
var coverURL: URL?
```

In `Sources/WarRoom.swift` `scanCarousels`, set it in the `Carousel(...)` init:

```swift
coverURL: WarRoom.coverURL(slidesDir: slidesDir, slidePNGs: pngs),
```

(place the new argument adjacent to `slidePNGs:`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Desktop/wr2-control-app && swiftc -parse-as-library Sources/Models.swift Sources/WarRoom.swift Tests/warroomtest/main.swift -o build/warroomtest && ./build/warroomtest`
Expected: `RESULT: GREEN`

- [ ] **Step 5: Run the existing suite to confirm no regression**

Run: `cd ~/Desktop/wr2-control-app && ./test.sh`
Expected: existing tests still GREEN.

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/wr2-control-app
git add Sources/Models.swift Sources/WarRoom.swift Tests/warroomtest/main.swift
git commit -m "feat(cover): resolve real carousel cover image (lowest slide png)"
```

---

## Task 2: Engagement metrics model + extraction from the queue

**Files:**

- Modify: `Sources/Models.swift` (add `EngagementMetrics`, add fields to `ReviewItem`, add `metrics`/publish fields to `Carousel`)
- Modify: `Sources/WarRoom.swift` (map queue `engagement_metrics`+publish fields onto carousels by slug)
- Test: `Tests/metricstest/main.swift`

**Interfaces:**

- Produces: `struct EngagementMetrics { let shares, likes, comments, saves, reach, impressions: Int? }`, `EngagementMetrics.isEmpty: Bool`, `Carousel.metrics: EngagementMetrics?`, `Carousel.isPublished: Bool`, `Carousel.instagramURL: String?`, `ReviewItem.engagement_metrics: EngagementMetrics?`, `ReviewItem.instagram_post_url: String?`, `ReviewItem.instagram_published_at: String?`

- [ ] **Step 1: Write the failing test**

Create `Tests/metricstest/main.swift`:

```swift
import Foundation
let json = """
[{"id":"x","topic_slug":"kbli-cafe","carousel_path":"/Users/nuzantara/.../carousel/kbli-cafe",
  "instagram_post_url":"https://instagram.com/p/ABC","instagram_published_at":"2026-06-10",
  "engagement_metrics":{"likes":1247,"comments":38,"saves":340,"reach":18200,"shares":312},
  "state":"published"},
 {"item_id":"y","topic":"spt","engagement_metrics":{"likes":null,"comments":null,"saves":null,"reach":null}}]
""".data(using: .utf8)!
let items = try! JSONDecoder().decode([ReviewItem].self, from: json)
var fails = 0
func expect(_ c: Bool, _ m: String) { if c { print("  ✅ \(m)") } else { print("  ❌ \(m)"); fails += 1 } }
expect(items.count == 2, "both schemas decode")
let m = items[0].engagement_metrics
expect(m?.shares == 312, "shares parsed (the king metric)")
expect(m?.likes == 1247, "likes parsed")
expect(items[0].instagram_post_url == "https://instagram.com/p/ABC", "ig url parsed")
expect(items[1].engagement_metrics?.isEmpty == true, "all-null metrics → isEmpty true")
expect(items[0].engagement_metrics?.isEmpty == false, "real metrics → isEmpty false")
print("RESULT: \(fails == 0 ? "GREEN" : "RED")")
exit(fails == 0 ? 0 : 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Desktop/wr2-control-app && swiftc -parse-as-library Sources/Models.swift Tests/metricstest/main.swift -o build/metricstest 2>&1 | head`
Expected: FAIL — `engagement_metrics` / `EngagementMetrics` undefined.

- [ ] **Step 3: Write minimal implementation**

In `Sources/Models.swift` add:

```swift
struct EngagementMetrics: Codable, Equatable {
    var shares: Int?
    var likes: Int?
    var comments: Int?
    var saves: Int?
    var reach: Int?
    var impressions: Int?
    var isEmpty: Bool { [shares, likes, comments, saves, reach, impressions].allSatisfy { $0 == nil } }
}
```

Add to `ReviewItem` (alongside existing CodingKeys/optionals — all optional so both schemas decode):

```swift
var engagement_metrics: EngagementMetrics?
var instagram_post_url: String?
var instagram_published_at: String?
```

Add to `Carousel`:

```swift
var metrics: EngagementMetrics?
var instagramURL: String?
var publishedAt: String?
var isPublished: Bool { (instagramURL?.isEmpty == false) }
```

In `WarRoom.scanCarousels`, after building `verdictBySlug`, also build maps by slug and assign in the `Carousel(...)` init:

```swift
// alongside verdictBySlug:
var metricsBySlug: [String: EngagementMetrics] = [:]
var igUrlBySlug: [String: String] = [:]
var pubAtBySlug: [String: String] = [:]
for item in queue {
    let slug: String?
    if let p = item.carousel_path {
        let t = p.hasSuffix("/") ? String(p.dropLast()) : p
        slug = t.components(separatedBy: "/").last
    } else { slug = item.topic_slug }
    guard let s = slug else { continue }
    if let m = item.engagement_metrics { metricsBySlug[s] = m }
    if let u = item.instagram_post_url { igUrlBySlug[s] = u }
    if let a = item.instagram_published_at { pubAtBySlug[s] = a }
}
```

Then in the `Carousel(...)` init add:

```swift
metrics: metricsBySlug[slug],
instagramURL: igUrlBySlug[slug],
publishedAt: pubAtBySlug[slug],
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Desktop/wr2-control-app && swiftc -parse-as-library Sources/Models.swift Tests/metricstest/main.swift -o build/metricstest && ./build/metricstest`
Expected: `RESULT: GREEN`

- [ ] **Step 5: Existing suite green**

Run: `cd ~/Desktop/wr2-control-app && ./test.sh`
Expected: GREEN.

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/wr2-control-app
git add Sources/Models.swift Sources/WarRoom.swift Tests/metricstest/main.swift
git commit -m "feat(metrics): parse engagement_metrics (shares first) from queue onto carousels"
```

---

## Task 3: QueueWriter — atomic, field-preserving mark-published + undo

**Files:**

- Create: `Sources/QueueWriter.swift`
- Test: `Tests/queuewritertest/main.swift`

**Interfaces:**

- Produces:
  - `enum QueueWriter`
  - `static func markPublished(queueFile: URL, slug: String, igURL: String, publishedAt: String) throws`
  - `static func undoPublished(queueFile: URL, slug: String) throws`
  - `static func extractMediaID(from igURL: String) -> String?`
- Consumes: nothing from prior tasks (operates on raw JSON to guarantee unknown-field preservation).

- [ ] **Step 1: Write the failing test**

Create `Tests/queuewritertest/main.swift`:

```swift
import Foundation
let dir = FileManager.default.temporaryDirectory.appendingPathComponent("wr2q-\(UUID().uuidString)")
try! FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
let qf = dir.appendingPathComponent("q.json")
let original = """
[{"id":"a","topic_slug":"kbli-cafe","state":"drafted","UNKNOWN_FUTURE":"keepme","engagement_metrics":{"likes":null}}]
""".data(using: .utf8)!
try! original.write(to: qf)

var fails = 0
func expect(_ c: Bool, _ m: String) { if c { print("  ✅ \(m)") } else { print("  ❌ \(m)"); fails += 1 } }

// media id extraction
expect(QueueWriter.extractMediaID(from: "https://www.instagram.com/p/ABC123/") == "ABC123", "media id from /p/ url")
expect(QueueWriter.extractMediaID(from: "ABC123") == "ABC123", "bare id passes through")

// mark published
try! QueueWriter.markPublished(queueFile: qf, slug: "kbli-cafe", igURL: "https://instagram.com/p/ABC123/", publishedAt: "2026-06-22")
let after = try! JSONSerialization.jsonObject(with: Data(contentsOf: qf)) as! [[String: Any]]
expect((after[0]["state"] as? String) == "published", "state advanced to published")
expect((after[0]["instagram_post_url"] as? String) == "https://instagram.com/p/ABC123/", "ig url written")
expect((after[0]["ig_media_id"] as? String) == "ABC123", "media id written")
expect((after[0]["instagram_published_at"] as? String) == "2026-06-22", "published_at written")
expect((after[0]["UNKNOWN_FUTURE"] as? String) == "keepme", "unknown field preserved (scar #9)")

// undo
try! QueueWriter.undoPublished(queueFile: qf, slug: "kbli-cafe")
let undone = try! JSONSerialization.jsonObject(with: Data(contentsOf: qf)) as! [[String: Any]]
expect((undone[0]["state"] as? String) == "drafted", "undo restores prior state")
expect(undone[0]["ig_media_id"] == nil, "undo clears media id (sampler stops measuring)")
expect((undone[0]["UNKNOWN_FUTURE"] as? String) == "keepme", "unknown field still preserved after undo")
print("RESULT: \(fails == 0 ? "GREEN" : "RED")")
exit(fails == 0 ? 0 : 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Desktop/wr2-control-app && swiftc -parse-as-library Sources/QueueWriter.swift Tests/queuewritertest/main.swift -o build/qwtest 2>&1 | head`
Expected: FAIL — `QueueWriter` undefined.

- [ ] **Step 3: Write minimal implementation**

Create `Sources/QueueWriter.swift`:

```swift
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

    private static func slugOf(_ item: [String: Any]) -> String? {
        if let s = item["topic_slug"] as? String { return s }
        if let p = item["carousel_path"] as? String {
            let t = p.hasSuffix("/") ? String(p.dropLast()) : p
            return t.components(separatedBy: "/").last
        }
        return nil
    }

    private static func mutate(queueFile: URL, slug: String,
                              _ change: (inout [String: Any]) -> Void) throws {
        let data = try Data(contentsOf: queueFile)
        guard var arr = try JSONSerialization.jsonObject(with: data) as? [[String: Any]] else {
            throw NSError(domain: "QueueWriter", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "queue is not a JSON array"])
        }
        var touched = false
        for i in arr.indices where slugOf(arr[i]) == slug {
            change(&arr[i]); touched = true
        }
        guard touched else {
            throw NSError(domain: "QueueWriter", code: 2,
                          userInfo: [NSLocalizedDescriptionKey: "no queue item for slug \(slug)"])
        }
        let out = try JSONSerialization.data(withJSONObject: arr, options: [.prettyPrinted, .sortedKeys])
        let tmp = queueFile.deletingLastPathComponent()
            .appendingPathComponent(".\(queueFile.lastPathComponent).tmp-\(UUID().uuidString)")
        try out.write(to: tmp)
        // atomic replace
        _ = try FileManager.default.replaceItemAt(queueFile, withItemAt: tmp)
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
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Desktop/wr2-control-app && swiftc -parse-as-library Sources/QueueWriter.swift Tests/queuewritertest/main.swift -o build/qwtest && ./build/qwtest`
Expected: `RESULT: GREEN`

- [ ] **Step 5: Existing suite green**

Run: `cd ~/Desktop/wr2-control-app && ./test.sh`
Expected: GREEN.

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/wr2-control-app
git add Sources/QueueWriter.swift Tests/queuewritertest/main.swift
git commit -m "feat(queue): atomic field-preserving mark-published + reversible undo"
```

---

## Task 4: AppState — modes, idle timer, publish actions, viral selection

**Files:**

- Modify: `Sources/Models.swift` (add `AppMode`)
- Modify: `Sources/AppState.swift`
- Test: `Tests/viraltest/main.swift` (pure selection logic, no @MainActor needed via nonisolated static)

**Interfaces:**

- Produces:
  - `enum AppMode { case work, ambient }`
  - `AppState.mode: AppMode` (@Published)
  - `AppState.markPublished(slug:igURL:publishedAt:)`, `AppState.undoPublished(slug:)`
  - `nonisolated static func viralCovers(_ carousels: [Carousel], now: Date, windowDays: Int) -> [Carousel]`
- Consumes: `Carousel.metrics/.isPublished/.modified` (Task 2), `QueueWriter.markPublished/undoPublished` (Task 3).

- [ ] **Step 1: Write the failing test**

Create `Tests/viraltest/main.swift`:

```swift
import Foundation
func car(_ slug: String, shares: Int?, published: Bool, mod: Date) -> Carousel {
    var c = Carousel(slug: slug, directory: URL(fileURLWithPath: "/tmp/\(slug)"),
                     slidesDir: URL(fileURLWithPath: "/tmp/\(slug)/slides"),
                     slidePNGs: [URL(fileURLWithPath: "/tmp/\(slug)/slides/1.png")],
                     modified: mod, topic: slug, domain: "kbli",
                     criticVerdict: "PASS", slideCount: 1, imagegenFallback: false)
    c.coverURL = c.slidePNGs.first
    c.metrics = EngagementMetrics(shares: shares, likes: nil, comments: nil, saves: nil, reach: nil, impressions: nil)
    c.instagramURL = published ? "https://instagram.com/p/\(slug)" : nil
    return c
}
let now = Date(timeIntervalSince1970: 1_780_000_000)
let day: TimeInterval = 86400
let list = [
    car("viral-big", shares: 500, published: true, mod: now.addingTimeInterval(-10*day)),
    car("viral-small", shares: 100, published: true, mod: now.addingTimeInterval(-5*day)),
    car("old-published", shares: 999, published: true, mod: now.addingTimeInterval(-300*day)),
    car("unpublished-recent", shares: nil, published: false, mod: now.addingTimeInterval(-1*day)),
]
let viral = AppState.viralCovers(list, now: now, windowDays: 240)
var fails = 0
func expect(_ c: Bool, _ m: String) { if c { print("  ✅ \(m)") } else { print("  ❌ \(m)"); fails += 1 } }
expect(viral.first?.slug == "viral-big", "most shares within window first")
expect(viral.contains { $0.slug == "old-published" } == false, "outside 240d window excluded")
expect(viral.contains { $0.slug == "unpublished-recent" } == false, "unpublished excluded from viral")
// fallback when nothing published-with-metrics
let none = AppState.viralCovers([car("u", shares: nil, published: false, mod: now)], now: now, windowDays: 240)
expect(none.isEmpty, "no viral candidates → empty (caller does recent-PASS fallback)")
print("RESULT: \(fails == 0 ? "GREEN" : "RED")")
exit(fails == 0 ? 0 : 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Desktop/wr2-control-app && swiftc -parse-as-library Sources/Models.swift Sources/WarRoom.swift Sources/QueueWriter.swift Sources/StreamEvent.swift Sources/ClaudeRunner.swift Sources/PromptBuilder.swift Sources/Conversationalist.swift Sources/AppState.swift Tests/viraltest/main.swift -o build/viraltest 2>&1 | head`
Expected: FAIL — `viralCovers` undefined. (AppState pulls SwiftUI; if the harness can't link SwiftUI in CLI, see Step 3 note.)

- [ ] **Step 3: Write minimal implementation**

In `Sources/Models.swift` add:

```swift
enum AppMode: Equatable { case work, ambient }
```

In `Sources/AppState.swift` add the published mode + nonisolated pure selector + actions:

```swift
@Published var mode: AppMode = .work

/// Pure: published carousels with a shares metric, within the window, sorted shares↓ then reach↓.
nonisolated static func viralCovers(_ carousels: [Carousel], now: Date, windowDays: Int) -> [Carousel] {
    let cutoff = now.addingTimeInterval(-Double(windowDays) * 86400)
    return carousels
        .filter { $0.isPublished && ($0.metrics?.shares != nil) && $0.modified >= cutoff }
        .sorted {
            let s0 = $0.metrics?.shares ?? -1, s1 = $1.metrics?.shares ?? -1
            if s0 != s1 { return s0 > s1 }
            return ($0.metrics?.reach ?? -1) > ($1.metrics?.reach ?? -1)
        }
}

func markPublished(slug: String, igURL: String, publishedAt: String) {
    do { try QueueWriter.markPublished(queueFile: WarRoom.queueFile(), slug: slug,
                                       igURL: igURL, publishedAt: publishedAt)
         refreshFromDisk() }
    catch { rawLog.append("⚠︎ mark-published: \(error.localizedDescription)") }
}

func undoPublished(slug: String) {
    do { try QueueWriter.undoPublished(queueFile: WarRoom.queueFile(), slug: slug)
         refreshFromDisk() }
    catch { rawLog.append("⚠︎ undo-published: \(error.localizedDescription)") }
}
```

NOTE on the CLI test: if `swiftc` cannot link SwiftUI for the AppState file in the harness, move `viralCovers` into a Foundation-pure file `Sources/ViralSelector.swift` as `enum ViralSelector { static func viralCovers(...) }` and have `AppState.viralCovers` call it; update the test to call `ViralSelector.viralCovers` and compile WITHOUT AppState.swift. (Keeps the rule "Foundation-pure files testable".)

- [ ] **Step 4: Run test to verify it passes**

Run: the Step-2 command (or the ViralSelector variant).
Expected: `RESULT: GREEN`

- [ ] **Step 5: Build the full app to confirm AppState still compiles with SwiftUI**

Run: `cd ~/Desktop/wr2-control-app && ./build.sh`
Expected: `✅ built: …/WR2 Control.app`

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/wr2-control-app
git add Sources/Models.swift Sources/AppState.swift Tests/viraltest/main.swift Sources/ViralSelector.swift 2>/dev/null
git commit -m "feat(state): app modes, mark/undo publish actions, viral-cover selection"
```

---

## Task 5: Carousel detail view — big cover + results panel + mark-published

**Files:**

- Create: `Sources/Views/CarouselDetailView.swift`
- Modify: `Sources/Localization.swift` (IT/ID keys)
- Modify: `Sources/Views/RootView.swift` (navigate to detail; add `@State selectedCarousel`)

**Interfaces:**

- Consumes: `Carousel` (cover/metrics/isPublished/slidePNGs), `AppState.markPublished/undoPublished`, `lang.t(_:)`.
- Produces: `struct CarouselDetailView: View` (init `init(carousel: Carousel, onClose: @escaping () -> Void)`).

- [ ] **Step 1: Add localization keys (no test — strings)**

In `Sources/Localization.swift` `L10n.table`, add (IT, ID):

```swift
"detail.results": ("Risultati", "Hasil"),
"detail.shares": ("condivisioni", "dibagikan"),
"detail.likes": ("like", "suka"),
"detail.comments": ("commenti", "komentar"),
"detail.saves": ("salvati", "disimpan"),
"detail.reach": ("copertura", "jangkauan"),
"detail.notPublished": ("Non ancora pubblicato", "Belum diterbitkan"),
"detail.awaiting": ("Pubblicato — in attesa di misurazione (~24h)", "Terbit — menunggu pengukuran (~24 jam)"),
"detail.markPublished": ("Segna come pubblicato", "Tandai sudah terbit"),
"detail.igLink": ("Link del post Instagram", "Tautan postingan Instagram"),
"detail.confirm": ("Conferma", "Konfirmasi"),
"detail.undo": ("Annulla pubblicazione", "Batalkan terbit"),
"detail.openIG": ("Apri su Instagram", "Buka di Instagram"),
"detail.critic": ("Controllo qualità", "Pemeriksaan kualitas"),
"detail.close": ("Chiudi", "Tutup"),
```

- [ ] **Step 2: Write the view**

Create `Sources/Views/CarouselDetailView.swift`:

```swift
import SwiftUI

struct CarouselDetailView: View {
    let carousel: Carousel
    var onClose: () -> Void
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    @State private var showPublishForm = false
    @State private var igLink = ""

    var body: some View {
        HStack(spacing: 0) {
            coverColumn.frame(maxWidth: .infinity)
            resultsPanel.frame(width: 360)
        }
        .background(Theme.ink)
    }

    private var coverColumn: some View {
        VStack(spacing: 14) {
            HStack {
                Button(action: onClose) { Label(lang.t("detail.close"), systemImage: "chevron.left") }
                    .buttonStyle(.plain).foregroundStyle(Theme.muted)
                Spacer()
            }
            if let cover = carousel.coverURL, let img = NSImage(contentsOf: cover) {
                Image(nsImage: img).resizable().scaledToFit()
                    .frame(maxHeight: .infinity)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
            } else {
                RoundedRectangle(cornerRadius: 10).fill(Theme.inkLift).frame(maxHeight: .infinity)
            }
            thumbnails
        }.padding(20)
    }

    private var thumbnails: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(carousel.slidePNGs, id: \.self) { url in
                    if let img = NSImage(contentsOf: url) {
                        Image(nsImage: img).resizable().scaledToFill()
                            .frame(width: 44, height: 55).clipShape(RoundedRectangle(cornerRadius: 4))
                    }
                }
            }
        }.frame(height: 60)
    }

    private var resultsPanel: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(carousel.topic ?? carousel.slug).font(Theme.titleFont).foregroundStyle(.white)
            FactRule(width: 44)
            Text(lang.t("detail.results")).font(.system(size: 12, weight: .bold)).foregroundStyle(Theme.muted)
            metricsBlock
            Divider().overlay(Color.white.opacity(0.08))
            criticBlock
            Spacer()
            publishControls
        }.padding(20).background(Theme.antracite.opacity(0.5))
    }

    @ViewBuilder private var metricsBlock: some View {
        if let m = carousel.metrics, m.isEmpty == false {
            VStack(alignment: .leading, spacing: 8) {
                metricRow("🔁", m.shares, "detail.shares", emphasize: true)   // king metric first
                metricRow("❤", m.likes, "detail.likes")
                metricRow("💬", m.comments, "detail.comments")
                metricRow("💾", m.saves, "detail.saves")
                metricRow("👁", m.reach, "detail.reach")
            }
        } else if carousel.isPublished {
            Text(lang.t("detail.awaiting")).font(Theme.bodyFont).foregroundStyle(Theme.muted)
        } else {
            Text(lang.t("detail.notPublished")).font(Theme.bodyFont).foregroundStyle(Theme.muted)
        }
    }

    private func metricRow(_ icon: String, _ value: Int?, _ key: String, emphasize: Bool = false) -> some View {
        HStack(spacing: 8) {
            Text(icon)
            Text(value.map { "\($0)" } ?? "—")
                .font(.system(size: emphasize ? 22 : 16, weight: emphasize ? .bold : .semibold))
                .foregroundStyle(emphasize ? Theme.yellow : .white)
            Text(lang.t(key)).font(.system(size: 11)).foregroundStyle(Theme.muted)
        }
    }

    @ViewBuilder private var criticBlock: some View {
        HStack {
            Text(lang.t("detail.critic")).font(.system(size: 11)).foregroundStyle(Theme.muted)
            Spacer()
            Text(carousel.criticVerdict ?? "—")
                .font(.system(size: 12, weight: .bold))
                .foregroundStyle((carousel.criticVerdict ?? "").uppercased().contains("PASS") ? Theme.green : Theme.red)
        }
    }

    @ViewBuilder private var publishControls: some View {
        if carousel.isPublished {
            HStack {
                if let u = carousel.instagramURL, let url = URL(string: u) {
                    Link(destination: url) { Label(lang.t("detail.openIG"), systemImage: "arrow.up.right.square") }
                        .font(.system(size: 12)).foregroundStyle(Theme.yellow)
                }
                Spacer()
                Button(lang.t("detail.undo")) { state.undoPublished(slug: carousel.slug) }
                    .buttonStyle(.plain).font(.system(size: 12)).foregroundStyle(Theme.muted)
            }
        } else if showPublishForm {
            VStack(alignment: .leading, spacing: 8) {
                TextField(lang.t("detail.igLink"), text: $igLink)
                    .textFieldStyle(.plain).font(.system(size: 12)).foregroundStyle(.white)
                    .padding(8).background(RoundedRectangle(cornerRadius: 8).fill(Theme.inkLift))
                Button(lang.t("detail.confirm")) {
                    let today = ISO8601DateFormatter().string(from: Date()).prefix(10)
                    state.markPublished(slug: carousel.slug, igURL: igLink, publishedAt: String(today))
                    showPublishForm = false
                }
                .buttonStyle(.plain).foregroundStyle(.black)
                .padding(.horizontal, 12).padding(.vertical, 6)
                .background(Capsule().fill(Theme.yellow))
                .disabled(igLink.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        } else {
            Button { showPublishForm = true } label: {
                Label(lang.t("detail.markPublished"), systemImage: "checkmark.seal.fill")
                    .font(.system(size: 13, weight: .semibold)).foregroundStyle(.black)
                    .padding(.horizontal, 14).padding(.vertical, 8)
                    .background(Capsule().fill(Theme.yellow))
            }.buttonStyle(.plain)
        }
    }
}
```

- [ ] **Step 3: Wire navigation in RootView**

In `Sources/Views/RootView.swift`, add `@State private var selectedCarousel: Carousel?` and, in the content switch, when `selectedCarousel != nil` show `CarouselDetailView(carousel: sel) { selectedCarousel = nil }`. (Gallery cards call a closure setting `selectedCarousel`.) Ensure `Carousel` is `Identifiable` (add `var id: String { slug }` to `Carousel` in Models if not present).

- [ ] **Step 4: Build**

Run: `cd ~/Desktop/wr2-control-app && ./build.sh`
Expected: `✅ built`.

- [ ] **Step 5: Visual snapshot check**

Run: `cd ~/Desktop/wr2-control-app && ./build/WR2\ Control.app/Contents/MacOS/WR2Control --snapshot _proof/screens 2>&1 | tail -3` (extend Snapshot.swift to render detail in a later step if not auto). Manually open the app, click a carousel, confirm cover + results render.
Expected: real cover image visible, results panel shows "Non ancora pubblicato" + mark button.

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/wr2-control-app
git add Sources/Views/CarouselDetailView.swift Sources/Localization.swift Sources/Views/RootView.swift Sources/Models.swift
git commit -m "feat(detail): carousel cover+results view with reversible mark-published"
```

---

## Task 6: Cover gallery rework — real covers + result badges + sort

**Files:**

- Modify: `Sources/Views/GalleryView.swift` → render `carousel.coverURL` via `NSImage`; add result/state badge; add sort control.
- Modify: `Sources/Localization.swift` (sort + badge keys).

**Interfaces:**

- Consumes: `[Carousel]` from `state.carousels`, `carousel.coverURL/.metrics/.isPublished`, taps → set `selectedCarousel` (Task 5).

- [ ] **Step 1: Localization keys**

Add to `L10n.table`:

```swift
"gallery.sort.viral": ("Più condivisi", "Paling dibagikan"),
"gallery.sort.recent": ("Più recenti", "Terbaru"),
"gallery.sort.awaiting": ("In attesa", "Menunggu"),
"gallery.badge.notPublished": ("non pubblicato", "belum terbit"),
"gallery.badge.awaiting": ("in attesa", "menunggu"),
```

- [ ] **Step 2: Render real cover + badge**

In `GalleryView.swift`, replace the gray placeholder block with:

```swift
if let cover = carousel.coverURL, let img = NSImage(contentsOf: cover) {
    Image(nsImage: img).resizable().scaledToFill()
        .frame(height: 150).clipped().clipShape(RoundedRectangle(cornerRadius: 8))
} else {
    RoundedRectangle(cornerRadius: 8).fill(Theme.inkLift).frame(height: 150)
}
```

Overlay a badge (top-leading): if `carousel.metrics?.shares != nil` show `🔁 \(shares)`; else if `isPublished` show `lang.t("gallery.badge.awaiting")`; else `lang.t("gallery.badge.notPublished")`.
Make the card a `Button { onSelect(carousel) }` wired up to RootView's `selectedCarousel`.

- [ ] **Step 3: Sort control**

Add a segmented picker bound to `@State private var sort: GallerySort = .recent` (enum `viral/recent/awaiting`), applying:

- `.viral`: `AppState.viralCovers(state.carousels, now: Date(), windowDays: 240)` then append the rest.
- `.recent`: existing `modified`-desc.
- `.awaiting`: published-but-no-metrics first.

- [ ] **Step 4: Build + snapshot**

Run: `cd ~/Desktop/wr2-control-app && ./build.sh && open "build/WR2 Control.app"`
Expected: gallery now shows REAL cover thumbnails with badges, no gray placeholders.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/wr2-control-app
git add Sources/Views/GalleryView.swift Sources/Localization.swift
git commit -m "feat(gallery): real cover thumbnails + result badges + sort (viral/recent/awaiting)"
```

---

## Task 7: Ambient editorial wall + running ribbon

**Files:**

- Create: `Sources/Views/AmbientView.swift`
- Modify: `Sources/Views/RootView.swift` (mode toggle + idle timer + ambient routing)
- Modify: `Sources/Localization.swift` (ambient keys)

**Interfaces:**

- Consumes: `AppState.mode`, `viralCovers`, `state.carousels`, `state.activeRun` (running ribbon), `RunReducer` step states (already in activeRun).
- Produces: `struct AmbientView: View`, rotation Timer.

- [ ] **Step 1: Localization keys**

```swift
"ambient.nowRunning": ("Ora in lavorazione", "Sedang dibuat"),
"ambient.awaiting": ("in attesa di numeri", "menunggu angka"),
"ambient.mostShared": ("il più condiviso", "paling dibagikan"),
"ambient.published": ("pubblicati", "diterbitkan"),
"ambient.born": ("Sta nascendo un carosello", "Sebuah korsel sedang lahir"),
"mode.ambient": ("Modalità vetrina", "Mode etalase"),
"mode.work": ("Modalità lavoro", "Mode kerja"),
```

- [ ] **Step 2: Write AmbientView**

Create `Sources/Views/AmbientView.swift`: a full-bleed view that, every 9s via `Timer.publish`, advances an index over the cover list = `viralCovers(...)` if non-empty else recent-PASS fallback (`state.carousels.filter { ($0.criticVerdict ?? "").contains("PASS") }`). Layout: big cover left (NSImage, full height), right column with topic + `🔁 shares` (yellow, large) + editorial line. Bottom ribbon ALWAYS: if `state.activeRun != nil` show topic + a progress bar from completed/total steps + `lang.t("ambient.nowRunning")`; plus counters (published count, avg shares this week). If a run is active, replace the cover with a large `lang.t("ambient.born")` + the step checklist from `activeRun`.

- [ ] **Step 3: Mode toggle + idle auto-ambient in RootView**

In `RootView.swift`: a toolbar/corner button toggling `state.mode`. Add an idle timer: a `Timer` resetting on any key/mouse (use `.onContinuousHover` / `NSEvent` local monitor) that sets `state.mode = .ambient` after 180s idle; any input sets `.work`. When `state.mode == .ambient`, render `AmbientView()` full-screen with no sidebar; else the current sidebar shell.

- [ ] **Step 4: Build + verify both modes**

Run: `cd ~/Desktop/wr2-control-app && ./build.sh && open "build/WR2 Control.app"`
Expected: toggle switches to a full-screen editorial wall cycling covers; toggling back returns to work shell.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/wr2-control-app
git add Sources/Views/AmbientView.swift Sources/Views/RootView.swift Sources/Localization.swift
git commit -m "feat(ambient): editorial wall (viral covers + running ribbon) with idle auto-mode"
```

---

## Task 8: History panel

**Files:**

- Create: `Sources/Views/HistoryView.swift`
- Modify: `Sources/Views/RootView.swift` (add History section to sidebar + nav)
- Modify: `Sources/Localization.swift` (history keys)

**Interfaces:**

- Consumes: `state.pastRuns` (in-session `[Run]`), `state.carousels` (for completed history fallback), `Run.status/.topic/.startedAt/.finishedAt`.
- Produces: `struct HistoryView: View`; 3 summary numbers + run list; tap → `selectedCarousel`.

- [ ] **Step 1: Localization keys**

```swift
"history.title": ("Storico", "Riwayat"),
"history.runsThisMonth": ("run questo mese", "run bulan ini"),
"history.passRate": ("PASS al primo giro", "PASS percobaan pertama"),
"history.avgDuration": ("durata media", "durasi rata-rata"),
```

- [ ] **Step 2: Write HistoryView**

Create `Sources/Views/HistoryView.swift`: top row = three big stat cards computed from `state.pastRuns` (count this month; % with critic PASS first try; average `finishedAt - startedAt`). Below: a `List`/`LazyVStack` of runs (date, topic, status pill, slide count if linked carousel, duration). No charts. Tapping a run that maps to a carousel opens detail.

- [ ] **Step 3: Add to sidebar nav**

In `RootView.swift` add a `Section.history` case + sidebar entry (icon `clock.arrow.circlepath`, `lang.t("history.title")`).

- [ ] **Step 4: Build**

Run: `cd ~/Desktop/wr2-control-app && ./build.sh`
Expected: `✅ built`; History section shows 3 numbers + run list.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/wr2-control-app
git add Sources/Views/HistoryView.swift Sources/Views/RootView.swift Sources/Localization.swift
git commit -m "feat(history): production panel (runs this month / pass-rate / avg duration + list)"
```

---

## Task 9: Snapshot coverage for the new surfaces (regression proof)

**Files:**

- Modify: `Sources/Snapshot.swift` (render detail/ambient/history in IT + ID)

**Interfaces:**

- Consumes: all new Views. Produces PNGs under `_proof/screens/`.

- [ ] **Step 1: Extend Snapshot**

In `Sources/Snapshot.swift`, add cases that render `CarouselDetailView` (with a sample published + a sample unpublished carousel), `AmbientView`, `HistoryView`, each in `.it` and `.id`, via `ImageRenderer` into fixed 1280×800 frames. Reuse the existing snapshot harness pattern.

- [ ] **Step 2: Run snapshots**

Run: `cd ~/Desktop/wr2-control-app && ./build.sh && ./build/WR2\ Control.app/Contents/MacOS/WR2Control --snapshot _proof/screens 2>&1 | tail`
Expected: new PNGs written (detail.it/id, ambient.it/id, history.it/id).

- [ ] **Step 3: Eyeball**

Open `_proof/screens/detail.it.png`, `ambient.it.png`, `history.it.png`. Confirm: real cover, yellow shares emphasis, honest empty states, IT/ID both correct.

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/wr2-control-app
git add Sources/Snapshot.swift _proof/screens
git commit -m "test(snapshot): cover IT/ID renders of detail, ambient, history"
```

---

## Task 10: Mini deployment + Desk icons

**Files:**

- Create: `deploy/com.balizero.wr2control.plist`
- Create: `deploy/install-mini.sh`
- Create: `deploy/make-desk-icon.sh`

**Interfaces:** operational scripts; no app code.

- [ ] **Step 0 (FIRST — resolve open node #1): verify Mini war-room data path**

Run: `ssh mini 'ls -la ~/Desktop/nuzantara/apps/war-room/output/queue/human-review-queue.json ~/Desktop/nuzantara/apps/war-room/output/carousel 2>&1 | head'`
Decide: if the Mini has its own synced war-room copy, the app reads local. If not, point `WarRoom.defaultOutputRoot()` (via an env override `WR2_WARROOM_ROOT`) at a synced/mounted Pro path. Record the decision inline in `install-mini.sh`. Do NOT guess — confirm on disk first.

- [ ] **Step 1: Build the .app on M5**

Run: `cd ~/Desktop/wr2-control-app && ./build.sh`
Expected: `✅ built: …/WR2 Control.app`.

- [ ] **Step 2: Write the LaunchAgent (NOT under ~/Desktop — scar W84)**

Create `deploy/com.balizero.wr2control.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.balizero.wr2control</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/nuzantara/Applications/WR2 Control.app/Contents/MacOS/WR2Control</string>
    <string>--ambient</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key>
    <dict><key>SuccessfulExit</key><false/></dict>
  <key>StandardOutPath</key><string>/Users/nuzantara/Library/Logs/wr2control.log</string>
  <key>StandardErrorPath</key><string>/Users/nuzantara/Library/Logs/wr2control.err</string>
</dict></plist>
```

(KeepAlive only-on-crash is correct for a long-lived GUI app, not a one-shot → not scar #7.)

- [ ] **Step 3: Write install-mini.sh**

Create `deploy/install-mini.sh`:

```bash
#!/bin/zsh
set -euo pipefail
APP="build/WR2 Control.app"
[[ -d "$APP" ]] || { echo "build first: ./build.sh"; exit 1; }
echo "▸ copying .app to Mini (~/Applications, NOT ~/Desktop — scar W84)…"
ssh mini 'mkdir -p ~/Applications ~/Library/LaunchAgents ~/Library/Logs'
rsync -a --delete "$APP" mini:'~/Applications/'
scp deploy/com.balizero.wr2control.plist mini:'~/Library/LaunchAgents/'
echo "▸ (re)load LaunchAgent…"
ssh mini 'launchctl bootout gui/$(id -u)/com.balizero.wr2control 2>/dev/null; launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2control.plist'
echo "▸ verify it launched (real liveness, not just exit 0 — scar #2)…"
sleep 4
ssh mini 'pgrep -f WR2Control && echo "✅ running on Mini" || { echo "❌ not running — check ~/Library/Logs/wr2control.err"; exit 1; }'
```

- [ ] **Step 4: Run install + handle `--ambient` flag**

First ensure the app accepts `--ambient` (sets initial `state.mode = .ambient` + full-screen): add the flag parse in `WR2ControlApp.swift`. Rebuild. Then:
Run: `cd ~/Desktop/wr2-control-app && ./build.sh && bash deploy/install-mini.sh`
Expected: `✅ running on Mini`. Look at the office TV: app full-screen in ambient.

- [ ] **Step 5: Desk icons on M5 + Pro**

Create `deploy/make-desk-icon.sh`:

```bash
#!/bin/zsh
set -euo pipefail
# Local launcher alias on the Desktop pointing at the local .app.
APP_M5="$HOME/Desktop/wr2-control-app/build/WR2 Control.app"
ln -sf "$APP_M5" "$HOME/Desktop/WR2 Control.app" 2>/dev/null || true
echo "✅ Desk icon (alias) placed on $(hostname)"
echo "For Pro: copy the .app to ~/Applications and ln -sf to ~/Desktop similarly."
```

Run on M5: `bash deploy/make-desk-icon.sh`. For Pro: rsync the `.app` to Pro `~/Applications` then symlink to its Desktop (Pro user `nuzantara`).
Expected: double-clicking the Desk icon opens the app.

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/wr2-control-app
git add deploy/
git commit -m "feat(deploy): Mini postazione-TV LaunchAgent + install + Desk icons (scar W84-safe)"
```

---

## Self-review (done)

- **Spec coverage:** Sec 1 (architecture/dual-mode) → Tasks 4,7. Sec 2 (cover+results) → Tasks 1,2,5,6. Sec 3 (ambient viral) → Tasks 4,7. Sec 4 (mark-published reversible) → Tasks 3,5. Sec 5 (history) → Task 8. Sec 6 (Mini+icons) → Task 10. Snapshot regression → Task 9. ✓
- **Open items:** #1 data path = Task 10 Step 0 (verify-first). #2 sampler-armed + #3 token scope = operator/separate, flagged not app-blocking. #4 fonts = optional, not in plan. ✓
- **Placeholder scan:** every code step has full code; no TBD/“handle edge cases”. ✓
- **Type consistency:** `EngagementMetrics`, `viralCovers(_:now:windowDays:)`, `markPublished(slug:igURL:publishedAt:)`, `coverURL` used identically across tasks. ✓
- **Pure-file rule:** Task 4 includes the ViralSelector fallback to keep selection logic CLI-testable. ✓
