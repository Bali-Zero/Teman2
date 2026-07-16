import Foundation
import Darwin

// Lightweight self-contained test harness (no XCTest dependency — CLT's `swift test`
// has a dyld issue with BuildServerProtocol on this machine, so we compile a plain
// executable that asserts and reports GREEN/RED with a real exit code).

final class T {
    static var passed = 0
    static var failed = 0
    static var currentSuite = ""

    static func suite(_ name: String) {
        currentSuite = name
        print("\n▸ \(name)")
    }

    static func check(_ cond: @autoclosure () -> Bool, _ msg: String) {
        if cond() {
            passed += 1
            print("  ✅ \(msg)")
        } else {
            failed += 1
            print("  ❌ \(msg)")
        }
    }

    static func eq<V: Equatable>(_ a: V, _ b: V, _ msg: String) {
        check(a == b, "\(msg)  [got \(a), want \(b)]")
    }

    static func report() -> Int32 {
        print("\n" + String(repeating: "─", count: 40))
        print("RESULT: \(passed) passed, \(failed) failed")
        return failed == 0 ? 0 : 1
    }
}

// MARK: - Fixtures

let fm = FileManager.default

/// Build a throwaway war-room-like dir tree for filesystem tests.
func makeFixtureRoot() -> URL {
    let base = fm.temporaryDirectory
        .appendingPathComponent("wr2ctrl-test-\(UUID().uuidString)", isDirectory: true)
    let carousel = base.appendingPathComponent("carousel", isDirectory: true)
    try? fm.createDirectory(at: carousel, withIntermediateDirectories: true)
    return base
}

/// - Parameter declareSlides: the A2 complete-or-nothing gate (WarRoom.declaredSlideCount)
///   needs a declaration source (slides.json/manifest.json/queue slide_count) or the dir is
///   undeclarable and excluded outright. `.auto` (the default) resolves to
///   `.objectSlides(slides.count)` — the OBJECT schema `{"slides":[...]}` is the dominant
///   real-world shape (a 2026-07-16 census of the live local carousel root found 100% of
///   existing slides.json files use it, none use a bare top-level array — Codex red-team
///   finding #6). `.bareArray` exercises the legacy/rare shape explicitly. `.absent` omits
///   slides.json entirely (majority real-world shape — most local dirs have none at all,
///   falling through to manifest.json/queue). `.malformed` writes invalid JSON.
///   NOTE: this case is named `.absent`, NOT `.none` — a case literally named `none` on an
///   enum used through an `Optional`-typed parameter is a documented Swift trap: `.none` at
///   the call site resolves to `Optional<DeclaredSlides>.none` (plain nil) instead of
///   `Optional.some(.none)`, silently discarding the intended declaration mode. Caught live
///   2026-07-16: with a `DeclaredSlides?` parameter and a `case none`, EVERY `.none` call
///   site below silently reverted to the `.auto` default instead of "no slides.json at all",
///   which made the "undeclarable" and "ambiguous same-tier queue count" guilt tests pass
///   for the wrong reason (source (a) short-circuited before source (c) was ever reached).
enum DeclaredSlides: Equatable {
    case objectSlides(Int)
    case bareArray(Int)
    case absent
    case malformed
    case auto
}

@discardableResult
func makeCarousel(in root: URL, slug: String, slides: [String], brief: [String: Any]? = nil,
                   declareSlides: DeclaredSlides = .auto) -> URL {
    let dir = root.appendingPathComponent("carousel/\(slug)", isDirectory: true)
    let slidesDir = dir.appendingPathComponent("slides", isDirectory: true)
    try? fm.createDirectory(at: slidesDir, withIntermediateDirectories: true)
    // 1x1 PNG bytes (minimal valid PNG)
    let pngBytes: [UInt8] = [
        0x89,0x50,0x4E,0x47,0x0D,0x0A,0x1A,0x0A,0x00,0x00,0x00,0x0D,0x49,0x48,0x44,0x52,
        0x00,0x00,0x00,0x01,0x00,0x00,0x00,0x01,0x08,0x06,0x00,0x00,0x00,0x1F,0x15,0xC4,
        0x89,0x00,0x00,0x00,0x0A,0x49,0x44,0x41,0x54,0x78,0x9C,0x63,0x00,0x01,0x00,0x00,
        0x05,0x00,0x01,0x0D,0x0A,0x2D,0xB4,0x00,0x00,0x00,0x00,0x49,0x45,0x4E,0x44,0xAE,
        0x42,0x60,0x82]
    let png = Data(pngBytes)
    for name in slides {
        try? png.write(to: slidesDir.appendingPathComponent(name))
    }
    // chrome that must be excluded
    try? png.write(to: slidesDir.appendingPathComponent("logo.png"))
    try? png.write(to: slidesDir.appendingPathComponent("placeholder-01.jpg"))
    if let brief = brief,
       let data = try? JSONSerialization.data(withJSONObject: brief) {
        try? data.write(to: dir.appendingPathComponent("brief.json"))
    }
    let mode: DeclaredSlides = (declareSlides == .auto) ? .objectSlides(slides.count) : declareSlides
    switch mode {
    case .objectSlides(let n):
        let entries = (0..<n).map { ["index": $0 + 1] }
        let obj: [String: Any] = ["slides": entries]
        if let data = try? JSONSerialization.data(withJSONObject: obj) {
            try? data.write(to: dir.appendingPathComponent("slides.json"))
        }
    case .bareArray(let n):
        let entries = (0..<n).map { ["index": $0 + 1] }
        if let data = try? JSONSerialization.data(withJSONObject: entries) {
            try? data.write(to: dir.appendingPathComponent("slides.json"))
        }
    case .absent, .auto:
        break
    case .malformed:
        try? Data("{ not valid json ,,,".utf8).write(to: dir.appendingPathComponent("slides.json"))
    }
    return dir
}

// MARK: - Tests

func test_streamEventParsing() {
    T.suite("stream-json parsing")

    // init event
    let initLine = #"{"type":"system","subtype":"init","model":"claude-opus-4-8[1m]"}"#
    if case .systemInit(let m)? = StreamEvent.parse(line: initLine) {
        T.eq(m, "claude-opus-4-8[1m]", "init carries model")
    } else { T.check(false, "init parsed as systemInit") }

    // assistant text
    let textLine = #"{"type":"assistant","message":{"content":[{"type":"text","text":"hello"}]}}"#
    if case .assistantText(let t)? = StreamEvent.parse(line: textLine) {
        T.eq(t, "hello", "assistant text extracted")
    } else { T.check(false, "assistant text parsed") }

    // tool_use Agent → subagent_type
    let toolLine = #"{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Agent","input":{"subagent_type":"wr2-storyboarder"}}]}}"#
    if case .toolUse(let name, let input)? = StreamEvent.parse(line: toolLine) {
        T.eq(name, "Agent", "tool_use name")
        T.eq(input, "wr2-storyboarder", "tool_use surfaces subagent_type")
    } else { T.check(false, "tool_use parsed") }

    // result success
    let resLine = #"{"type":"result","subtype":"success","is_error":false,"result":"done","total_cost_usd":0.42}"#
    if case .result(let text, let isErr, let cost, _)? = StreamEvent.parse(line: resLine) {
        T.eq(text, "done", "result text")
        T.eq(isErr, false, "result not error")
        T.check((cost ?? 0) > 0.41, "result cost parsed")
    } else { T.check(false, "result parsed") }

    // malformed line → unparsable, never crashes
    if case .unparsable? = StreamEvent.parse(line: "this is not json {") {
        T.check(true, "malformed line → unparsable (no crash)")
    } else { T.check(false, "malformed handled as unparsable") }

    // empty line → nil
    T.check(StreamEvent.parse(line: "   ") == nil, "blank line → nil")
}

func test_runReducer() {
    T.suite("run reducer (event → pipeline steps)")

    var run = Run(humanRequest: "test", topic: "design a carousel for test")
    RunReducer.apply(.systemInit(model: "x"), to: &run)
    T.eq(run.status, .running, "init → running")
    T.eq(run.steps.first(where: { $0.id == "init" })?.state, .done, "init step done")

    RunReducer.apply(.toolUse(name: "Agent", input: "wr2-brief-interpreter"), to: &run)
    T.eq(run.steps.first(where: { $0.id == "brief" })?.state, .active, "brief step active")

    RunReducer.apply(.toolUse(name: "Agent", input: "wr2-critic"), to: &run)
    T.eq(run.steps.first(where: { $0.id == "critic" })?.state, .active, "critic step active")
    T.eq(run.steps.first(where: { $0.id == "brief" })?.state, .done, "earlier step auto-marked done")

    RunReducer.apply(.result(text: "ok", isError: false, costUSD: 1.0, errorStatus: nil), to: &run)
    T.eq(run.status, .succeeded, "result success → succeeded")
    T.check(run.steps.allSatisfy { $0.state == .done }, "all steps done on success")

    // failure path
    var run2 = Run(humanRequest: "t", topic: "x")
    RunReducer.apply(.systemInit(model: nil), to: &run2)
    RunReducer.apply(.toolUse(name: "Agent", input: "wr2-storyboarder"), to: &run2)
    RunReducer.apply(.result(text: nil, isError: true, costUSD: nil, errorStatus: "overloaded"), to: &run2)
    T.eq(run2.status, .failed, "result error → failed")
    T.check(run2.errorMessage?.isEmpty == false, "failure surfaces human error message")
    T.check(run2.steps.contains { $0.state == .failed }, "active step marked failed")
}

func test_pathDriftResolver() {
    T.suite("path-drift resolver (scar #1 HOME-fork)")
    let root = makeFixtureRoot()
    defer { try? fm.removeItem(at: root) }
    let croot = root.appendingPathComponent("carousel", isDirectory: true)
    _ = makeCarousel(in: root, slug: "e33g-visa-2026", slides: ["01.png", "02.png"])

    // a FOREIGN absolute path (as stored in queue JSON on the Pro)
    let foreign = "/Users/nuzantara/nuzantara/apps/war-room/output/carousel/e33g-visa-2026/"
    let resolved = WarRoom.resolveCarouselDir(foreignPath: foreign, carouselRoot: croot)
    T.check(resolved != nil, "foreign /Users/nuzantara path re-rooted to live machine")
    T.eq(resolved?.lastPathComponent, "e33g-visa-2026", "resolves to correct slug dir")

    // nonexistent slug → nil (no hallucinated path)
    let missing = WarRoom.resolveCarouselDir(
        foreignPath: "/Users/nuzantara/.../carousel/does-not-exist/", carouselRoot: croot)
    T.check(missing == nil, "missing slug → nil, never fabricated")
}

func test_outputRootOverride() {
    T.suite("war-room output root override")
    let old = getenv("WR2_WARROOM_ROOT").map { String(cString: $0) }
    let override = fm.temporaryDirectory.appendingPathComponent("wr2root-\(UUID().uuidString)", isDirectory: true)
    setenv("WR2_WARROOM_ROOT", override.path, 1)
    defer {
        if let old { setenv("WR2_WARROOM_ROOT", old, 1) }
        else { unsetenv("WR2_WARROOM_ROOT") }
    }

    T.eq(WarRoom.defaultOutputRoot().path, override.path, "WR2_WARROOM_ROOT overrides default root")
}

func test_carouselScan() {
    T.suite("carousel gallery scan")
    let root = makeFixtureRoot()
    defer { try? fm.removeItem(at: root) }
    let croot = root.appendingPathComponent("carousel", isDirectory: true)

    _ = makeCarousel(in: root, slug: "tax-spt-2026", slides: ["1.png", "2.png", "3.png"],
                     brief: ["topic": "SPT deadline", "domain": "tax"])
    _ = makeCarousel(in: root, slug: "_archived-broken", slides: ["1.png"])   // must be skipped
    // empty carousel (no slides) must be skipped
    let emptyDir = croot.appendingPathComponent("empty-one/slides", isDirectory: true)
    try? fm.createDirectory(at: emptyDir, withIntermediateDirectories: true)

    let carousels = WarRoom.scanCarousels(carouselRoot: croot, queue: [])
    T.eq(carousels.count, 1, "only the real, non-archived carousel is listed")
    let c = carousels.first
    T.eq(c?.slug, "tax-spt-2026", "correct slug")
    T.eq(c?.slideCount, 3, "3 slides counted (logo + placeholder excluded)")
    T.eq(c?.topic, "SPT deadline", "topic read from brief.json")
    T.eq(c?.domain, "tax", "domain read from brief.json")
    // numeric sort: 1,2,3 not lexical
    T.eq(c?.slidePNGs.first?.lastPathComponent, "1.png", "slides sorted numerically")
}

func test_queueMultiSchema() {
    T.suite("review queue multi-schema decode (scar #9)")
    // legacy + fsm + hybrid in one array
    let json = """
    [
      {"id":"a","topic_slug":"golden-visa","carousel_path":"/x/carousel/golden-visa/",
       "slide_count":9,"critic_overall_verdict":"pass","critic_summary":"good","drafted_at":"2026-05-09T23:11:27Z"},
      {"item_id":"pg-1","topic":"Content creators visa","state":"applied_ready_for_damar",
       "canva_url":"https://canva.com/x","created_at":"2026-05-23T07:05:07Z"},
      {"item_id":"pg-2","topic":"Property rules","state":"soft_fail"}
    ]
    """
    let url = fm.temporaryDirectory.appendingPathComponent("q-\(UUID()).json")
    try? json.data(using: .utf8)!.write(to: url)
    defer { try? fm.removeItem(at: url) }

    let items = WarRoom.readQueue(queueFile: url)
    T.eq(items.count, 3, "all 3 schema variants decoded")
    T.eq(items[0].displayTopic, "golden-visa", "legacy uses topic_slug")
    T.eq(items[0].displayState, "Approvato", "legacy verdict 'pass' → human label")
    T.eq(items[1].displayTopic, "Content creators visa", "fsm uses topic")
    T.eq(items[1].displayState, "Applicato — pronto", "fsm state humanized")
    T.check(items[1].hasCanva, "fsm item has canva url")
    T.check(items[2].hasCanva == false, "item without canva url flagged correctly")
}

func test_topicPrompt() {
    T.suite("human request → orchestrator prompt")
    T.eq(PromptBuilder.toTopicPrompt("fammi un carosello sul nuovo visto E33G"),
         "design a carousel for nuovo visto E33G", "Italian lead-in stripped")
    T.eq(PromptBuilder.toTopicPrompt("KBLI 2025 digital economy"),
         "design a carousel for KBLI 2025 digital economy", "bare topic wrapped")
    T.eq(PromptBuilder.toTopicPrompt("design a carousel for tax residency"),
         "design a carousel for tax residency", "already-formed prompt deduped")
}

func test_adversarialFixes() {
    T.suite("adversarial-review regression (H1/H4/M3)")

    // H1: a hard rate-limit rejection must end the run as failed, not leave it running.
    var run = Run(humanRequest: "t", topic: "x")
    RunReducer.apply(.systemInit(model: nil), to: &run)
    RunReducer.apply(.toolUse(name: "Agent", input: "wr2-brief-interpreter"), to: &run)
    RunReducer.apply(.rateLimit(status: "rejected"), to: &run)
    T.eq(run.status, .failed, "H1: rate-limit rejected → status failed (no running+error mix)")
    T.check(run.errorMessage?.contains("Limite") == true, "H1: human rate-limit message set")
    T.check(run.finishedAt != nil, "H1: finishedAt stamped on rate-limit failure")

    // an ALLOWED rate-limit must NOT fail the run
    var run2 = Run(humanRequest: "t", topic: "x")
    RunReducer.apply(.systemInit(model: nil), to: &run2)
    RunReducer.apply(.rateLimit(status: "allowed"), to: &run2)
    T.eq(run2.status, .running, "H1: allowed rate-limit leaves run running (innocence test)")

    // H4: legacy queue items use canva_design_url, not canva_url.
    let json = """
    [
      {"item_id":"x","topic":"legacy item","state":"pass","canva_design_url":"https://canva.com/legacy"},
      {"item_id":"y","topic":"fsm item","state":"pass","canva_url":"https://canva.com/fsm"},
      {"item_id":"z","topic":"no canva","state":"pass"}
    ]
    """
    let url = fm.temporaryDirectory.appendingPathComponent("q-\(UUID()).json")
    try? json.data(using: .utf8)!.write(to: url)
    defer { try? fm.removeItem(at: url) }
    let items = WarRoom.readQueue(queueFile: url)
    T.check(items[0].hasCanva, "H4: legacy canva_design_url recognized as canva")
    T.eq(items[0].canvaLink, "https://canva.com/legacy", "H4: canvaLink resolves legacy key")
    T.eq(items[1].canvaLink, "https://canva.com/fsm", "H4: canvaLink resolves fsm key")
    T.check(items[2].hasCanva == false, "H4: item without any canva key → false")
}

// MARK: - review-queue → carousel join (2026-07-08 "non riesco ad aprire i drafted")

func test_reviewQueueJoin() {
    T.suite("review-queue → on-disk carousel join (matchCarousel)")

    let root = makeFixtureRoot()
    defer { try? fm.removeItem(at: root) }
    _ = makeCarousel(in: root, slug: "2026-07-08-lkpm-panic-myth-79d3c3a9", slides: ["01.png"])
    _ = makeCarousel(in: root, slug: "golden-visa", slides: ["01.png"])
    _ = makeCarousel(in: root, slug: "2026-07-08-other-topic-deadbeef", slides: ["01.png"])
    let carousels = WarRoom.scanCarousels(carouselRoot: root.appendingPathComponent("carousel"))
    T.eq(carousels.count, 3, "fixture scan sees all 3 dirs")

    let json = """
    [
      {"id":"fsm","topic_slug":"lkpm-panic-myth",
       "carousel_path":"/Users/nuzantara/nuzantara/apps/war-room/output/carousel/2026-07-08-lkpm-panic-myth-79d3c3a9","state":"drafted"},
      {"id":"legacy","topic_slug":"golden-visa","carousel_path":"/x/carousel/golden-visa/","state":"drafted"},
      {"id":"gone","topic_slug":"golden-visa-attracts-rp2-trillion",
       "carousel_path":"/x/carousel/missing-efd58430","state":"drafted"},
      {"id":"nopath","topic_slug":"lkpm-panic-myth","state":"drafted"},
      {"id":"partial","topic_slug":"lkpm-panic","state":"drafted"},
      {"id":"prefix","topic_slug":"other","state":"drafted"}
    ]
    """
    let url = fm.temporaryDirectory.appendingPathComponent("q-\(UUID()).json")
    try? json.data(using: .utf8)!.write(to: url)
    defer { try? fm.removeItem(at: url) }
    let items = WarRoom.readQueue(queueFile: url)
    T.eq(items.count, 6, "queue fixture decoded")

    func match(_ i: Int) -> String? { WarRoom.matchCarousel(for: items[i], in: carousels)?.slug }

    // COLPEVOLEZZA — the bug: FSM item whose dir is date-<topic_slug>-<id8> must open.
    T.eq(match(0), "2026-07-08-lkpm-panic-myth-79d3c3a9",
         "FSM item joins by carousel_path basename (foreign /Users/nuzantara path)")
    T.eq(match(3), "2026-07-08-lkpm-panic-myth-79d3c3a9",
         "FSM item without carousel_path joins via anchored date-slug-id pattern")

    // INNOCENZA — legacy exact join still works; no phantom joins (scar #3 over-match).
    T.eq(match(1), "golden-visa", "legacy topic_slug == dir still joins")
    T.check(match(2) == nil, "missing-on-disk item stays non-interactive (no phantom)")
    T.check(match(4) == nil, "topic_slug that is only a SUBSTRING of the dir slug does not join")
    T.check(match(5) == nil, "'other' does not join 2026-07-08-other-topic-deadbeef (suffix not hex id)")
}

// MARK: - A2 complete-or-nothing gate (2026-07-16 mandate)

func test_completeOrNothingGate() {
    T.suite("A2 complete-or-nothing gate (2026-07-16 mandate)")

    let root = makeFixtureRoot()
    defer { try? fm.removeItem(at: root) }
    let croot = root.appendingPathComponent("carousel", isDirectory: true)

    // INNOCENZA — N-of-N via slides.json (source a): a full render passes through unaffected.
    _ = makeCarousel(in: root, slug: "complete-5", slides: (1...5).map { "\($0).png" })

    // COLPEVOLEZZA — declared (9) != disk (8): must be excluded entirely, not just flagged.
    _ = makeCarousel(in: root, slug: "mismatch-9-vs-8", slides: (1...8).map { "\($0).png" },
                      declareSlides: .objectSlides(9))

    // COLPEVOLEZZA — no slides.json/manifest.json/queue entry at all: undeclarable, excluded
    // even though real PNGs exist on disk (never silently trust raw disk count).
    _ = makeCarousel(in: root, slug: "undeclarable", slides: ["1.png", "2.png"], declareSlides: .absent)

    // fallback (b) — manifest.json total_slides, no slides.json (external-import shape).
    let manifestDir = makeCarousel(in: root, slug: "manifest-fallback", slides: ["1.png", "2.png"],
                                    declareSlides: .absent)
    let manifestJSON: [String: Any] = ["total_slides": 2, "imported": true]
    try? JSONSerialization.data(withJSONObject: manifestJSON)
        .write(to: manifestDir.appendingPathComponent("manifest.json"))

    // fallback (c) — queue slide_count, no slides.json/manifest.json at all.
    _ = makeCarousel(in: root, slug: "queue-fallback", slides: ["1.png", "2.png", "3.png"],
                      declareSlides: .absent)

    // published exemption — undeclarable AND the only 1 disk PNG, but published: must stay
    // visible regardless (immutable, REPOINT-guarded — never hidden retroactively).
    _ = makeCarousel(in: root, slug: "published-partial", slides: ["1.png"], declareSlides: .absent)

    let queueJSON = """
    [
      {"id":"qf","topic_slug":"queue-fallback","slide_count":3,"state":"drafted"},
      {"id":"pp","topic_slug":"published-partial","state":"pass",
       "instagram_post_url":"https://instagram.com/p/xyz",
       "instagram_published_at":"2026-06-01T00:00:00Z"}
    ]
    """
    let qurl = fm.temporaryDirectory.appendingPathComponent("q-\(UUID()).json")
    try? queueJSON.data(using: .utf8)!.write(to: qurl)
    defer { try? fm.removeItem(at: qurl) }
    let queue = WarRoom.readQueue(queueFile: qurl)
    T.eq(queue.count, 2, "gate-test queue fixture decoded")

    let carousels = WarRoom.scanCarousels(carouselRoot: croot, queue: queue)
    func find(_ slug: String) -> Carousel? { carousels.first(where: { $0.slug == slug }) }

    T.check(find("complete-5") != nil, "innocence: N-of-N (slides.json) is listed")
    T.eq(find("complete-5")?.slideCount, 5, "innocence: displayed count == declared == disk")

    T.check(find("mismatch-9-vs-8") == nil, "guilt: declared=9 vs disk=8 is excluded entirely")
    T.check(find("undeclarable") == nil, "guilt: no declaration source at all is excluded")

    T.check(find("manifest-fallback") != nil, "fallback (b): manifest.json total_slides accepted")
    T.eq(find("manifest-fallback")?.slideCount, 2, "fallback (b): displayed count from manifest.json")

    T.check(find("queue-fallback") != nil, "fallback (c): queue slide_count accepted")
    T.eq(find("queue-fallback")?.slideCount, 3, "fallback (c): displayed count from queue join")

    T.check(find("published-partial") != nil,
            "published exemption: undeclarable+mismatched but published stays visible")

    T.eq(WarRoom.excludedIncompleteCount, 2,
         "excludedIncompleteCount counts exactly the 2 unpublished exclusions (mismatch + undeclarable)")
}

// MARK: - Codex red-team hardening (2026-07-16, findings #1/#2/#3/#6 on the A2 gate)

func test_matchCarouselPrecedenceOrder() {
    T.suite("matchCarousel precedence — exact wins over regex regardless of array order (Codex finding #1)")

    func fakeCarousel(_ slug: String) -> Carousel {
        Carousel(slug: slug, directory: URL(fileURLWithPath: "/tmp/\(slug)"),
                  slidesDir: URL(fileURLWithPath: "/tmp/\(slug)/slides"),
                  slidePNGs: [], modified: Date(), topic: nil, domain: nil,
                  criticVerdict: nil, slideCount: 1, imagegenFallback: false,
                  coverURL: nil, metrics: nil, instagramURL: nil, publishedAt: nil, canvaURL: nil)
    }
    let exactDir = fakeCarousel("golden-visa-order")
    let regexDir = fakeCarousel("2026-07-08-golden-visa-order-deadbeef")

    let json = #"[{"id":"x","topic_slug":"golden-visa-order","state":"drafted"}]"#
    let url = fm.temporaryDirectory.appendingPathComponent("q-\(UUID()).json")
    try? json.data(using: .utf8)!.write(to: url)
    defer { try? fm.removeItem(at: url) }
    let item = WarRoom.readQueue(queueFile: url)[0]

    // COLPEVOLEZZA (the pre-fix bug): a combined exact+regex pass lets array order pick
    // the regex dir here. Putting it FIRST is exactly the scenario that broke.
    T.eq(WarRoom.matchCarousel(for: item, in: [regexDir, exactDir])?.slug, "golden-visa-order",
         "exact match wins even when the regex-matching dir sorts FIRST in the array")
    // INNOCENZA — same result with the array in the other order (sanity, not the bug itself).
    T.eq(WarRoom.matchCarousel(for: item, in: [exactDir, regexDir])?.slug, "golden-visa-order",
         "exact match wins when it already sorts first too")
}

func test_completeOrNothingGateHardening() {
    T.suite("A2 gate hardening — Codex red-team findings #2/#3/#6 (2026-07-16)")

    let root = makeFixtureRoot()
    defer { try? fm.removeItem(at: root) }
    let croot = root.appendingPathComponent("carousel", isDirectory: true)

    // Finding #2 — two queue rows at the SAME precedence tier (both exact topic_slug,
    // neither has carousel_path) declare DIFFERENT slide_count. Must be excluded with a
    // logged ambiguity reason, never silently resolved by picking the first row.
    _ = makeCarousel(in: root, slug: "ambiguous-count", slides: (1...7).map { "\($0).png" },
                      declareSlides: .absent)

    // Finding #3 (guilt) — an empty-string instagram_post_url must NOT count as published
    // and must NOT let an incomplete render bypass the gate.
    _ = makeCarousel(in: root, slug: "empty-url-guilt", slides: (1...3).map { "\($0).png" },
                      declareSlides: .objectSlides(5))

    // Finding #3 (innocence) — a legacy row with state=="published" but no URL/timestamp
    // at all must still count as published and must NOT be hidden.
    _ = makeCarousel(in: root, slug: "state-only-published", slides: ["1.png"], declareSlides: .absent)

    // Finding #6 — a malformed slides.json must not crash and must fall through cleanly
    // to the next declaration source (queue slide_count here), same as if it were absent.
    _ = makeCarousel(in: root, slug: "malformed-json", slides: (1...4).map { "\($0).png" },
                      declareSlides: .malformed)

    // Finding #6 — multi-source conflict mirroring the real `bali-pma-rental-crackdown`
    // case: slides.json (a) says 9, manifest.json (b) says 999, queue (c) says 8 — (a)
    // must win over both, precedence a > b > c.
    let conflictDir = makeCarousel(in: root, slug: "multi-source-conflict",
                                    slides: (1...9).map { "\($0).png" }, declareSlides: .objectSlides(9))
    let manifestConflict: [String: Any] = ["total_slides": 999]
    try? JSONSerialization.data(withJSONObject: manifestConflict)
        .write(to: conflictDir.appendingPathComponent("manifest.json"))

    let queueJSON = """
    [
      {"id":"amb1","topic_slug":"ambiguous-count","slide_count":7,"state":"drafted"},
      {"id":"amb2","topic_slug":"ambiguous-count","slide_count":8,"state":"drafted"},
      {"id":"eu","topic_slug":"empty-url-guilt","instagram_post_url":"","state":"drafted"},
      {"id":"sp","topic_slug":"state-only-published","state":"published"},
      {"id":"mj","topic_slug":"malformed-json","slide_count":4,"state":"drafted"},
      {"id":"msc","topic_slug":"multi-source-conflict","slide_count":8,"state":"drafted"}
    ]
    """
    let qurl = fm.temporaryDirectory.appendingPathComponent("q-\(UUID()).json")
    try? queueJSON.data(using: .utf8)!.write(to: qurl)
    defer { try? fm.removeItem(at: qurl) }
    let queue = WarRoom.readQueue(queueFile: qurl)
    T.eq(queue.count, 6, "hardening-test queue fixture decoded")

    let carousels = WarRoom.scanCarousels(carouselRoot: croot, queue: queue)
    func find(_ slug: String) -> Carousel? { carousels.first(where: { $0.slug == slug }) }

    T.check(find("ambiguous-count") == nil,
            "finding #2 guilt: same-tier queue rows disagreeing on slide_count → excluded, not first-picked")

    T.check(find("empty-url-guilt") == nil,
            "finding #3 guilt: empty-string instagram_post_url does NOT bypass the gate")

    T.check(find("state-only-published") != nil,
            "finding #3 innocence: state==\"published\" with no URL/timestamp still exempts the gate")

    T.check(find("malformed-json") != nil,
            "finding #6: malformed slides.json falls through to queue fallback, no crash")
    T.eq(find("malformed-json")?.slideCount, 4, "finding #6: fallback count taken from queue after malformed (a)")

    T.check(find("multi-source-conflict") != nil, "finding #6: a>b>c conflict — carousel listed")
    T.eq(find("multi-source-conflict")?.slideCount, 9,
         "finding #6: slides.json (a)=9 wins over manifest (b)=999 and queue (c)=8")
}

// MARK: - Publish-eligibility gate (2026-07-16 cross-finding w/ Python A3 reconciler)

func test_publishEligibilityCrossFinding() {
    T.suite("publish-eligibility — fresh state must not be masked by a stale verdict")

    func fakeCarousel(state: String?, criticVerdict: String?, isPublished: Bool = false) -> Carousel {
        Carousel(slug: "x", directory: URL(fileURLWithPath: "/tmp/x"),
                 slidesDir: URL(fileURLWithPath: "/tmp/x/slides"), slidePNGs: [],
                 modified: Date(), topic: nil, domain: nil, criticVerdict: criticVerdict,
                 slideCount: 8, imagegenFallback: false, coverURL: nil, metrics: nil,
                 instagramURL: isPublished ? "https://instagram.com/p/x/" : nil,
                 publishedAt: nil, canvaURL: nil, state: state)
    }

    // COLPEVOLEZZA — the exact cross-finding bug: a stale GOOD verdict from an earlier
    // successful critic run must NOT mask a FRESH render_incomplete state the Python A3
    // daily-reconciler set later (a post-render disk-level drift the render-time gate
    // couldn't see). If phase/eligibility were still computed verdict-first
    // (critic_overall_verdict ?? state, the OLD precedence), this carousel would wrongly
    // read as waitlist/publishable.
    let maskedByStaleVerdict = fakeCarousel(state: "render_incomplete", criticVerdict: "pass")
    T.eq(maskedByStaleVerdict.phase, .review,
         "fresh render_incomplete state wins over a stale \"pass\" verdict -> review, not waitlist")
    T.check(maskedByStaleVerdict.isPublishEligible == false,
            "guilt: not publish-eligible despite the stale good verdict")

    // INNOCENZA — a legacy-schema row with NO `state` field at all, only the verdict,
    // must still fall back correctly (the fix must not regress rows that never carried
    // a state field in the first place).
    let legacyVerdictOnly = fakeCarousel(state: nil, criticVerdict: "pass")
    T.eq(legacyVerdictOnly.phase, .waitlist, "no state field -> falls back to criticVerdict -> waitlist")
    T.check(legacyVerdictOnly.isPublishEligible, "innocence: legacy verdict-only carousel stays eligible")

    // INNOCENZA — the ordinary, current-day case: state="drafted", no verdict yet.
    let ordinaryDraft = fakeCarousel(state: "drafted", criticVerdict: nil)
    T.eq(ordinaryDraft.phase, .waitlist, "drafted -> waitlist")
    T.check(ordinaryDraft.isPublishEligible, "innocence: an ordinary drafted carousel is eligible")

    // COLPEVOLEZZA — an already-published carousel is never "eligible for a FRESH
    // publish" (that's the separate, reversible undo-publish flow).
    let alreadyPublished = fakeCarousel(state: "published", criticVerdict: "pass", isPublished: true)
    T.check(alreadyPublished.isPublishEligible == false,
            "guilt: already-published carousel is not eligible for a fresh publish")
}

func test_isPublishedIndependentFieldCheck() {
    T.suite("isQueueItemPublished / Carousel.isPublished — state & verdict checked independently (2026-07-16 final-gate finding)")

    func item(state: String?, verdict: String?, url: String? = nil) -> ReviewItem {
        var obj: [String: Any] = ["id": "x", "topic_slug": "x"]
        if let s = state { obj["state"] = s }
        if let v = verdict { obj["critic_overall_verdict"] = v }
        if let u = url { obj["instagram_post_url"] = u }
        let data = try! JSONSerialization.data(withJSONObject: obj)
        return try! JSONDecoder().decode(ReviewItem.self, from: data)
    }

    func fakeCarousel(state: String?, criticVerdict: String?, instagramURL: String? = nil) -> Carousel {
        Carousel(slug: "x", directory: URL(fileURLWithPath: "/tmp/x"),
                 slidesDir: URL(fileURLWithPath: "/tmp/x/slides"), slidePNGs: [],
                 modified: Date(), topic: nil, domain: nil, criticVerdict: criticVerdict,
                 slideCount: 8, imagegenFallback: false, coverURL: nil, metrics: nil,
                 instagramURL: instagramURL, publishedAt: nil, canvaURL: nil, state: state)
    }

    // COLPEVOLEZZA — the exact corner caught in final-gate review: verdict="pass" is
    // non-nil, so the OLD coalesced `critic_overall_verdict ?? state` NEVER even looked
    // at `state`. An app-enqueued legacy row (pre-#2442 fabricated "pass" verdict)
    // later marked `state: "published"` with no URL backfill must still read as
    // published — each field is now checked independently, not coalesced.
    T.check(isQueueItemPublished(item(state: "published", verdict: "pass")),
            "guilt: verdict=\"pass\" no longer masks state=\"published\" (isQueueItemPublished)")
    T.check(fakeCarousel(state: "published", criticVerdict: "pass").isPublished,
            "guilt: same corner case on Carousel.isPublished")

    // INNOCENZA — every previously-working path must still work.
    T.check(isQueueItemPublished(item(state: nil, verdict: nil, url: "https://instagram.com/p/x/")),
            "innocence: URL alone still marks published")
    T.check(isQueueItemPublished(item(state: "published", verdict: nil)),
            "innocence: state alone (no verdict) still marks published")
    T.check(isQueueItemPublished(item(state: nil, verdict: "published")),
            "innocence: verdict alone (no state) still marks published")
    T.check(isQueueItemPublished(item(state: "drafted", verdict: "pass")) == false,
            "innocence: neither field says \"published\" -> not published (independent OR doesn't over-trigger)")
    T.check(fakeCarousel(state: "drafted", criticVerdict: "pass").isPublished == false,
            "innocence: same non-trigger case on Carousel.isPublished")
}

func test_stateWiredThroughScanCarousels() {
    T.suite("WarRoom.scanCarousels wires raw state through the queue join (not just verdict)")

    let root = makeFixtureRoot()
    defer { try? fm.removeItem(at: root) }
    let croot = root.appendingPathComponent("carousel", isDirectory: true)
    _ = makeCarousel(in: root, slug: "cross-finding-slug", slides: (1...8).map { "\($0).png" })

    let json = """
    [{"id":"cf","topic_slug":"cross-finding-slug","state":"render_incomplete","critic_overall_verdict":"pass","slide_count":8}]
    """
    let url = fm.temporaryDirectory.appendingPathComponent("q-\(UUID()).json")
    try? json.data(using: .utf8)!.write(to: url)
    defer { try? fm.removeItem(at: url) }
    let queue = WarRoom.readQueue(queueFile: url)

    let carousels = WarRoom.scanCarousels(carouselRoot: croot, queue: queue)
    guard let c = carousels.first(where: { $0.slug == "cross-finding-slug" }) else {
        T.check(false, "cross-finding-slug carousel should be listed (complete render, gate unaffected by publish state)")
        return
    }
    T.eq(c.state, "render_incomplete", "raw state wired through from the queue join")
    T.eq(c.criticVerdict, "pass", "criticVerdict stays verdict-first — unchanged field, different purpose (critic badge)")
    T.eq(c.phase, .review, "phase uses raw state, not verdict -> review despite the \"pass\" verdict")
    T.check(c.isPublishEligible == false, "publish gate correctly refuses despite the gallery listing it as complete")
}

// MARK: - carousel phase mapping (pipeline↔app coherence, 2026-06-25)

func test_carouselPhaseMapping() {
    T.suite("carousel phase mapping (FSM status → band)")

    func phase(_ s: String?, published: Bool = false) -> CarouselPhase {
        CarouselPhase.of(state: s, isPublished: published)
    }

    // COLPEVOLEZZA — the bug Zero hit: a render stuck/in-flight must NOT read as
    // "born, ready" (waitlist/blue). It must surface as review (yellow).
    T.eq(phase("rendering"), .review, "rendering → review (NOT waitlist) — scar #2 in UI")
    T.eq(phase("render_failed"), .review, "render_failed → review")
    T.eq(phase("soft_fail"), .review, "soft_fail → review")
    // An UNKNOWN/future status must surface, never hide as finished-green.
    T.eq(phase("some_new_state_2027"), .review, "unknown status → review (don't hide as waitlist)")

    // INNOCENZA — genuinely finished-but-unpublished carousels stay waitlist (blue).
    T.eq(phase("rendered"), .waitlist, "rendered → waitlist (innocence)")
    T.eq(phase("rendered_shadow"), .waitlist, "rendered_shadow → waitlist (real DB state, now known)")
    T.eq(phase("approved"), .waitlist, "approved → waitlist (innocence)")
    T.eq(phase("briefed"), .waitlist, "briefed → waitlist (innocence)")

    // terminal bands unchanged
    T.eq(phase("published"), .published, "published → published")
    T.eq(phase("rendered", published: true), .published, "isPublished overrides state → published")
    T.eq(phase("rejected"), .rejected, "rejected → rejected")
    T.eq(phase("missed"), .rejected, "missed → rejected")
}

// MARK: - Instagram caption validation

func test_instagramCaptionValidation() {
    T.suite("Instagram caption validation")

    T.check(InstagramCaption.isPublishable("   \n") == false,
            "blank or whitespace-only caption is blocked")
    T.check(InstagramCaption.isPublishable(String(repeating: "a", count: 2_200)),
            "caption at Instagram's 2,200-character limit is accepted")
    T.check(InstagramCaption.isPublishable(String(repeating: "a", count: 2_201)) == false,
            "caption over Instagram's limit is blocked")
    T.eq(InstagramCaption.characterCount("Bali 🌴"), 6,
         "counter follows Swift user-visible character count")
}

func test_instagramCaptionProcessContract() {
    T.suite("Instagram caption process contract")

    let captionFile = fm.temporaryDirectory.appendingPathComponent("approved caption.txt")
    T.eq(
        InstagramCaption.previewArguments(slug: "visa-update"),
        ["scripts/wr2_ig_publish_remote.py", "visa-update", "--print-caption"],
        "preview asks the existing Python generator for caption text only"
    )
    T.eq(
        InstagramCaption.publishArguments(
            slug: "visa-update", captionFile: captionFile, confirm: false),
        ["scripts/wr2_ig_publish_remote.py", "visa-update", "--caption-file",
         captionFile.path],
        "dry-run passes the approved caption through a file argument"
    )
    T.eq(
        InstagramCaption.publishArguments(
            slug: "visa-update", captionFile: captionFile, confirm: true).last,
        "--confirm",
        "real publish retains the explicit Legge 5 confirm flag"
    )

    let tempDir = fm.temporaryDirectory
        .appendingPathComponent("wr2-caption-test-\(UUID().uuidString)", isDirectory: true)
    try? fm.createDirectory(at: tempDir, withIntermediateDirectories: true)
    defer { try? fm.removeItem(at: tempDir) }
    do {
        let exact = "First line\n\nSecond line — 🌴"
        let url = try InstagramCaption.writeTemporaryFile(exact, directory: tempDir)
        T.eq(try String(contentsOf: url, encoding: .utf8), exact,
             "temporary UTF-8 file preserves the approved caption exactly")
    } catch {
        T.check(false, "temporary caption file can be written: \(error)")
    }
}

// MARK: - External carousel import (PDF / folder / images classification + contract)

func test_externalImportClassification() {
    T.suite("External import — input classification")

    func entry(_ name: String, dir: Bool = false) -> ExternalImport.InputEntry {
        ExternalImport.InputEntry(url: URL(fileURLWithPath: "/tmp/\(name)"), isDirectory: dir)
    }

    T.check(ExternalImport.classify([]) == .failure(.empty),
            "empty selection is rejected, not silently accepted")

    switch ExternalImport.classify([entry("brief.pdf")]) {
    case .success(.pdf(let u)): T.check(u.lastPathComponent == "brief.pdf", "single PDF classified as .pdf")
    default: T.check(false, "single PDF classified as .pdf")
    }

    switch ExternalImport.classify([entry("slides", dir: true)]) {
    case .success(.folder(let u)): T.check(u.lastPathComponent == "slides", "single folder classified as .folder")
    default: T.check(false, "single folder classified as .folder")
    }

    switch ExternalImport.classify([entry("1.png"), entry("2.jpg"), entry("3.webp")]) {
    case .success(.images(let urls)): T.check(urls.count == 3, "multiple images classified as .images")
    default: T.check(false, "multiple images classified as .images")
    }

    T.check(ExternalImport.classify([entry("a.pdf"), entry("b.pdf")]) == .failure(.multiplePDFs),
            "two PDFs rejected as multiplePDFs, not silently taking the first")
    T.check(ExternalImport.classify([entry("a", dir: true), entry("b", dir: true)]) == .failure(.multipleFolders),
            "two folders rejected as multipleFolders")
    T.check(ExternalImport.classify([entry("a.pdf"), entry("b.png")]) == .failure(.mixedKinds),
            "PDF mixed with an image is rejected as mixedKinds (never silently pick one)")
    T.check(ExternalImport.classify([entry("a", dir: true), entry("b.png")]) == .failure(.mixedKinds),
            "folder mixed with a file is rejected as mixedKinds")
    T.check(ExternalImport.classify([entry("a.png"), entry("b.gif")]) == .failure(.unsupportedExtension("gif")),
            "unsupported extension in an otherwise-valid image set is rejected, not skipped")
}

func test_externalImportArguments() {
    T.suite("External import — script argument contract")

    let pdf = URL(fileURLWithPath: "/Users/zero/Desktop/brief.pdf")
    T.eq(
        ExternalImport.scriptArguments(inputs: [pdf], topic: "", fit: .contain),
        [pdf.path, "--fit", "contain"],
        "blank topic is omitted, not passed as an empty string"
    )
    T.eq(
        ExternalImport.scriptArguments(inputs: [pdf], topic: "  KITAS investor 2026  ", fit: .cover),
        [pdf.path, "--topic", "KITAS investor 2026", "--fit", "cover"],
        "topic is trimmed before being passed to the script"
    )
    let imgs = [URL(fileURLWithPath: "/tmp/1.png"), URL(fileURLWithPath: "/tmp/2.png")]
    T.eq(
        ExternalImport.scriptArguments(inputs: imgs, topic: "", fit: .native),
        [imgs[0].path, imgs[1].path, "--fit", "native"],
        "multiple image inputs are passed as separate positional arguments in order"
    )
}

func test_externalImportOutcomeParsing() {
    T.suite("External import — stdout JSON result parsing")

    let successLine = """
    {"ok":true,"slug":"kitas-investor-2026","carousel_dir":"apps/war-room/output/carousel/kitas-investor-2026/","slide_count":6,"queue_id":"carousel_2026-07-14_kitas-investor-2026"}
    """
    switch ExternalImport.parseOutcome(stdout: successLine, exitCode: 0) {
    case .success(let s):
        T.check(s.slug == "kitas-investor-2026", "success line parses the slug")
        T.check(s.slide_count == 6, "success line parses the slide count")
    case .failure:
        T.check(false, "a well-formed success JSON line must parse as .success")
    }

    // Stray progress noise before the real result line must not hide it (contract says
    // stdout carries only the JSON, but the app must not silently misread if it doesn't).
    let noisyStdout = "warming up…\n" + successLine
    switch ExternalImport.parseOutcome(stdout: noisyStdout, exitCode: 0) {
    case .success(let s): T.check(s.slug == "kitas-investor-2026", "result line found even after stray stdout noise")
    case .failure: T.check(false, "result line found even after stray stdout noise")
    }

    let failureLine = #"{"ok":false,"error":"nessuna pagina trovata nel PDF"}"#
    switch ExternalImport.parseOutcome(stdout: failureLine, exitCode: 2) {
    case .failure(let msg): T.eq(msg, "nessuna pagina trovata nel PDF", "failure line surfaces the script's error string")
    case .success: T.check(false, "a well-formed failure JSON line must parse as .failure")
    }

    switch ExternalImport.parseOutcome(stdout: "", exitCode: 1) {
    case .failure(let msg): T.eq(msg, "exit 1", "unparseable stdout falls back to a bare exit-code message, never a silent success")
    case .success: T.check(false, "unparseable stdout must never report success")
    }
}

// MARK: - External post registration (§A, 2026-07-17)

func test_externalPostRegistrationURLValidation() {
    T.suite("ExternalPostRegistration — Instagram URL validation/canonicalization")

    // INNOCENZA — well-formed URLs in several shapes all canonicalize correctly.
    do {
        let canon = try ExternalPostRegistration.canonicalizeInstagramURL("https://instagram.com/p/Cabc123_-")
        T.eq(canon, "https://www.instagram.com/p/Cabc123_-/", "bare p/ URL (no www, no trailing slash) canonicalizes")
    } catch { T.check(false, "well-formed p/ URL should not throw: \(error)") }

    do {
        let canon = try ExternalPostRegistration.canonicalizeInstagramURL("  https://www.instagram.com/reel/Xyz789/?igshid=foo  ")
        T.eq(canon, "https://www.instagram.com/reel/Xyz789/", "reel URL with query string + surrounding whitespace canonicalizes, drops query")
    } catch { T.check(false, "well-formed reel URL should not throw: \(error)") }

    // COLPEVOLEZZA — reject empty/garbage (acceptance criteria §A).
    func expectThrows(_ url: String, _ expected: ExternalPostRegistration.ValidationError, _ msg: String) {
        do {
            _ = try ExternalPostRegistration.canonicalizeInstagramURL(url)
            T.check(false, "\(msg): should have thrown")
        } catch let e as ExternalPostRegistration.ValidationError {
            T.eq(e, expected, msg)
        } catch {
            T.check(false, "\(msg): wrong error type \(error)")
        }
    }
    expectThrows("", .emptyURL, "empty string rejected")
    expectThrows("   ", .emptyURL, "whitespace-only rejected")
    expectThrows("not a url", .notAnInstagramPostURL, "garbage string rejected")
    expectThrows("https://instagram.com/balizero0", .notAnInstagramPostURL, "profile URL (not a post) rejected")
    expectThrows("https://example.com/p/abc/", .notAnInstagramPostURL, "wrong host rejected")
}

func test_externalPostRegistrationTopicAndIdentity() {
    T.suite("ExternalPostRegistration — topic validation + item_id/dir-name/entry construction")

    do {
        let t = try ExternalPostRegistration.validateTopic("  My manual post  ")
        T.eq(t, "My manual post", "topic is trimmed")
    } catch { T.check(false, "well-formed topic should not throw") }

    do {
        _ = try ExternalPostRegistration.validateTopic("   ")
        T.check(false, "blank topic should throw emptyTopic")
    } catch ExternalPostRegistration.ValidationError.emptyTopic {
        T.check(true, "blank topic throws emptyTopic")
    } catch { T.check(false, "wrong error type") }

    var comps = DateComponents()
    comps.year = 2026; comps.month = 7; comps.day = 17; comps.hour = 9; comps.minute = 0; comps.second = 0
    var cal = Calendar(identifier: .gregorian)
    cal.timeZone = TimeZone(identifier: "UTC")!
    let date = cal.date(from: comps)!

    T.eq(ExternalPostRegistration.makeItemID(publishDate: date, slug: "my-manual-post"),
         "external_2026-07-17T090000_my-manual-post", "item_id format: external_<date>T<time>_<slug>")
    T.eq(ExternalPostRegistration.carouselDirName(publishDate: date, slug: "my-manual-post"),
         "external-2026-07-17-my-manual-post", "carousel dir name: external-<date>-<slug>")

    let entryNoImages = ExternalPostRegistration.buildQueueEntry(
        instagramURL: "https://www.instagram.com/p/Abc123/", topic: "My manual post",
        slug: "my-manual-post", publishDate: date, slideCount: 0, carouselPath: nil)
    T.eq(entryNoImages["item_id"] as? String, "external_2026-07-17T090000_my-manual-post", "0-image entry item_id")
    T.eq(entryNoImages["state"] as? String, "published", "0-image entry state=published")
    T.eq(entryNoImages["source"] as? String, "external_manual", "0-image entry source=external_manual")
    T.eq(entryNoImages["slide_count"] as? Int, 0, "0-image entry slide_count=0")
    T.check(entryNoImages["carousel_path"] == nil, "0-image entry has NO carousel_path (renders as virtual card)")
    T.check(entryNoImages["instagram_published_at"] != nil, "instagram_published_at set (existing consumers read this key)")
    T.check(entryNoImages["published_at"] != nil, "published_at also set (spec's literal field name)")

    let entryWithImages = ExternalPostRegistration.buildQueueEntry(
        instagramURL: "https://www.instagram.com/p/Abc123/", topic: "My manual post",
        slug: "my-manual-post", publishDate: date, slideCount: 3,
        carouselPath: "~/nuzantara/apps/war-room/output/carousel/external-2026-07-17-my-manual-post/")
    T.eq(entryWithImages["slide_count"] as? Int, 3, "image entry slide_count reflects the copied-image count")
    T.check(entryWithImages["carousel_path"] != nil, "image entry HAS carousel_path")
}

// MARK: - Gallery recency sort key (§D, 2026-07-17 — re-rendered cards must not stay buried)

func test_recencySortKeyPure() {
    T.suite("WarRoom.recencySortKey — max(dir, slide-mtime) for drafts, publishedAt for published")

    let dirOld = Date(timeIntervalSince1970: 1_752_000_000)
    let slideNew = Date(timeIntervalSince1970: 1_752_800_000)   // later than dirOld

    // COLPEVOLEZZA (the pre-fix bug: dir mtime alone) — a fresher slide mtime must win.
    let key1 = WarRoom.recencySortKey(dirModified: dirOld, newestSlideModified: slideNew,
                                        isPublished: false, publishedAt: nil)
    T.eq(key1, slideNew, "unpublished: newer slide mtime wins over older dir mtime")

    // INNOCENZA — max, not "always prefer slide": dir mtime wins when it IS the newer one.
    let key2 = WarRoom.recencySortKey(dirModified: slideNew, newestSlideModified: dirOld,
                                        isPublished: false, publishedAt: nil)
    T.eq(key2, slideNew, "unpublished: dir mtime wins when it's the newer one")

    let key3 = WarRoom.recencySortKey(dirModified: dirOld, newestSlideModified: nil,
                                        isPublished: false, publishedAt: nil)
    T.eq(key3, dirOld, "unpublished, no slide mtime available: falls back to dir mtime alone")

    // PUBLISHED — publishedAt wins even when file mtimes are much newer (an unrelated
    // later touch, e.g. a metrics backfill, must never bump a live post's position).
    let pubDate = "2026-06-01T00:00:00Z"
    let key4 = WarRoom.recencySortKey(dirModified: slideNew, newestSlideModified: slideNew,
                                        isPublished: true, publishedAt: pubDate)
    T.eq(key4, WarRoom.parsePublishedAt(pubDate), "published: publishedAt wins over much-newer file mtimes")

    // published but no/unparseable publishedAt → falls back to max(dir, slide).
    let key5 = WarRoom.recencySortKey(dirModified: dirOld, newestSlideModified: slideNew,
                                        isPublished: true, publishedAt: nil)
    T.eq(key5, slideNew, "published with no publishedAt: falls back to max(dir, slide)")
}

func test_scanCarouselsRerenderSortsToTop() {
    T.suite("WarRoom.scanCarousels — re-rendered carousel sorts to top of drafted (§D acceptance #3)")

    let root = makeFixtureRoot()
    defer { try? fm.removeItem(at: root) }
    let croot = root.appendingPathComponent("carousel", isDirectory: true)

    let oldDir = makeCarousel(in: root, slug: "old-draft", slides: ["1.png", "2.png"])
    // "re-rendered" dir: same shape — a re-render overwrites the PNG bytes in place,
    // same filenames, so its directory's OWN mtime does not bump (see doc comment).
    let rerenderedDir = makeCarousel(in: root, slug: "rerendered-draft", slides: ["1.png", "2.png"])

    let farPast = Date(timeIntervalSinceNow: -86_400 * 30)
    let justNow = Date()
    try? fm.setAttributes([.modificationDate: farPast], ofItemAtPath: oldDir.path)
    try? fm.setAttributes([.modificationDate: farPast], ofItemAtPath: rerenderedDir.path)
    let rerenderedSlide = rerenderedDir.appendingPathComponent("slides/1.png")
    try? fm.setAttributes([.modificationDate: justNow], ofItemAtPath: rerenderedSlide.path)

    let queueJSON = """
    [
      {"id":"od","topic_slug":"old-draft","slide_count":2,"state":"drafted"},
      {"id":"rd","topic_slug":"rerendered-draft","slide_count":2,"state":"drafted"}
    ]
    """
    let qurl = fm.temporaryDirectory.appendingPathComponent("q-\(UUID()).json")
    try? queueJSON.data(using: .utf8)!.write(to: qurl)
    defer { try? fm.removeItem(at: qurl) }
    let queue = WarRoom.readQueue(queueFile: qurl)

    let carousels = WarRoom.scanCarousels(carouselRoot: croot, queue: queue)
        .sorted { $0.modified > $1.modified }
    T.eq(carousels.first?.slug, "rerendered-draft",
         "the re-rendered carousel (fresh slide mtime) sorts FIRST despite both dirs sharing an old dir-mtime")
}

// MARK: - Duplicate virtual-entry detection (§E, 2026-07-17)

func test_igShortcodeExtraction() {
    T.suite("WarRoom.igShortcode — entity extraction for URL-equality dedup")
    T.eq(WarRoom.igShortcode(from: "https://www.instagram.com/p/DaxDJuYFPi6/"), "DaxDJuYFPi6", "p/ URL")
    T.eq(WarRoom.igShortcode(from: "https://instagram.com/reel/Xyz789/?igshid=x"), "Xyz789", "reel/ URL with query string")
    T.check(WarRoom.igShortcode(from: "https://instagram.com/balizero0") == nil, "profile URL has no shortcode")
}

func test_matchesAnyPhysicalInstagramURL() {
    T.suite("WarRoom.matchesAnyPhysicalInstagramURL — cosmetic-difference-tolerant URL dedup")

    let known = ["https://www.instagram.com/p/DaxDJuYFPi6/", "https://www.instagram.com/p/Other111/"]
    T.check(WarRoom.matchesAnyPhysicalInstagramURL("https://instagram.com/p/DaxDJuYFPi6/?igshid=x", knownURLs: known),
            "same shortcode, different cosmetic form (no www, query string) still matches")
    T.check(WarRoom.matchesAnyPhysicalInstagramURL("https://www.instagram.com/p/Unrelated999/", knownURLs: known) == false,
            "a genuinely different shortcode does not match")
    T.check(WarRoom.matchesAnyPhysicalInstagramURL("", knownURLs: known) == false, "empty string never matches")
    T.check(WarRoom.matchesAnyPhysicalInstagramURL("https://instagram.com/p/DaxDJuYFPi6/", knownURLs: []) == false,
            "no known URLs at all -> no match")
}

func test_scanCarouselsDedupesVirtualEntrySharingURL() {
    T.suite("WarRoom.scanCarousels — virtual ig-* entry hidden when a physical sibling shares its URL (§E)")

    // Live shape (team-lead diagnosis, 2026-07-17): the real queue had TWO
    // entries for this post — idx 61 (native, this fixture's "real-1") only
    // got its instagram_post_url once flipped to published, and idx 71
    // (ig-DaxDJuYFPi6) was discovery-ingested 07-14 while idx 61's URL was
    // still null, with its topic mislabeled "150 LICENSED." — kept verbatim
    // here for direct traceability to the incident, not a placeholder.
    let root = makeFixtureRoot()
    defer { try? fm.removeItem(at: root) }
    let croot = root.appendingPathComponent("carousel", isDirectory: true)

    // the REAL carousel, published, with its own queue-joined instagram_post_url.
    _ = makeCarousel(in: root, slug: "bali-pma-rental-crackdown", slides: ["1.png"], declareSlides: .absent)

    let queueJSON = """
    [
      {"id":"real-1","topic_slug":"bali-pma-rental-crackdown","state":"published",
       "instagram_post_url":"https://www.instagram.com/p/DaxDJuYFPi6/",
       "instagram_published_at":"2026-06-01T00:00:00Z"},
      {"item_id":"ig-DaxDJuYFPi6","topic":"150 LICENSED.","state":"published",
       "instagram_post_url":"https://www.instagram.com/p/DaxDJuYFPi6/?igshid=x",
       "instagram_published_at":"2026-06-01T00:00:00Z"},
      {"item_id":"ig-GenuinelyUnrelated1","topic":"(a real other IG-only post)","state":"published",
       "instagram_post_url":"https://www.instagram.com/p/GenuinelyUnrelated1/",
       "instagram_published_at":"2026-06-02T00:00:00Z"}
    ]
    """
    let qurl = fm.temporaryDirectory.appendingPathComponent("q-\(UUID()).json")
    try? queueJSON.data(using: .utf8)!.write(to: qurl)
    defer { try? fm.removeItem(at: qurl) }
    let queue = WarRoom.readQueue(queueFile: qurl)

    let carousels = WarRoom.scanCarousels(carouselRoot: croot, queue: queue)

    // GUILT — without the fix this would show TWO cards for the same post.
    let dupMatches = carousels.filter { $0.instagramURL?.contains("DaxDJuYFPi6") == true }
    T.eq(dupMatches.count, 1, "only ONE card total for the DaxDJuYFPi6 post (the real on-disk one, virtual hidden)")
    T.check(dupMatches.first?.slug == "bali-pma-rental-crackdown",
            "the surviving card is the REAL on-disk carousel, not the virtual phantom")

    // INNOCENCE — a genuinely unrelated IG-only post (no physical sibling) still shows.
    T.check(carousels.contains { $0.slug == "ig-GenuinelyUnrelated1" },
            "a genuinely different IG-only post with no physical sibling still renders as a virtual card")
}

// MARK: - External-manual entries: completeness gate exemption (§A guilt+innocence pair)

func test_externalManualCompletenessGateGuiltInnocence() {
    T.suite("A2 completeness gate — external_manual entries stay exempt (§A guilt+innocence regression)")

    let root = makeFixtureRoot()
    defer { try? fm.removeItem(at: root) }
    let croot = root.appendingPathComponent("carousel", isDirectory: true)

    // GUILT — an ordinary DRAFTED (unpublished) dir whose real PNG count (1) doesn't
    // match its declared count (3) must STILL be excluded — the pre-existing A2 gate,
    // unchanged by the external-post feature.
    _ = makeCarousel(in: root, slug: "mismatched-draft", slides: ["1.png"], declareSlides: .objectSlides(3))

    let queueJSON = """
    [
      {"id":"md","topic_slug":"mismatched-draft","state":"drafted"},
      {"item_id":"external_2026-07-17T090000_no-image-test","state":"published",
       "instagram_post_url":"https://www.instagram.com/p/ExternalNoImage1/",
       "instagram_published_at":"2026-07-17T09:00:00Z","source":"external_manual",
       "topic":"No-image external post","topic_slug":"no-image-test","slide_count":0}
    ]
    """
    let qurl = fm.temporaryDirectory.appendingPathComponent("q-\(UUID()).json")
    try? queueJSON.data(using: .utf8)!.write(to: qurl)
    defer { try? fm.removeItem(at: qurl) }
    let queue = WarRoom.readQueue(queueFile: qurl)

    let carousels = WarRoom.scanCarousels(carouselRoot: croot, queue: queue)

    T.check(carousels.contains { $0.slug == "mismatched-draft" } == false,
            "GUILT: mismatched-disk drafted entry is still excluded from the gallery")
    T.eq(WarRoom.excludedIncompleteCount, 1,
         "GUILT: the exclusion is observable via excludedIncompleteCount (scar #2)")

    let external = carousels.first { $0.instagramURL == "https://www.instagram.com/p/ExternalNoImage1/" }
    T.check(external != nil, "INNOCENCE: the 0-image external_manual entry IS present in the gallery")
    T.check(external?.isPublished == true, "INNOCENCE: it renders as published")
    T.eq(external?.slideCount, 0, "INNOCENCE: slideCount reflects the declared 0")
}

// MARK: - main

let suites: [() -> Void] = [
    test_streamEventParsing,
    test_runReducer,
    test_pathDriftResolver,
    test_outputRootOverride,
    test_carouselScan,
    test_queueMultiSchema,
    test_topicPrompt,
    test_adversarialFixes,
    test_reviewQueueJoin,
    test_completeOrNothingGate,
    test_matchCarouselPrecedenceOrder,
    test_completeOrNothingGateHardening,
    test_publishEligibilityCrossFinding,
    test_isPublishedIndependentFieldCheck,
    test_stateWiredThroughScanCarousels,
    test_carouselPhaseMapping,
    test_instagramCaptionValidation,
    test_instagramCaptionProcessContract,
    test_externalImportClassification,
    test_externalImportArguments,
    test_externalImportOutcomeParsing,
    test_externalPostRegistrationURLValidation,
    test_externalPostRegistrationTopicAndIdentity,
    test_recencySortKeyPure,
    test_scanCarouselsRerenderSortsToTop,
    test_igShortcodeExtraction,
    test_matchesAnyPhysicalInstagramURL,
    test_scanCarouselsDedupesVirtualEntrySharingURL,
    test_externalManualCompletenessGateGuiltInnocence,
]
for s in suites { s() }
exit(T.report())
