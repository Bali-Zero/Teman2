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

func makeCarousel(in root: URL, slug: String, slides: [String], brief: [String: Any]? = nil) -> URL {
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
    let foreign = "/Users/nuzantara/Desktop/nuzantara/apps/war-room/output/carousel/e33g-visa-2026/"
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
       "carousel_path":"/Users/nuzantara/Desktop/nuzantara/apps/war-room/output/carousel/2026-07-08-lkpm-panic-myth-79d3c3a9","state":"drafted"},
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
    test_carouselPhaseMapping,
    test_instagramCaptionValidation,
    test_instagramCaptionProcessContract,
    test_externalImportClassification,
    test_externalImportArguments,
    test_externalImportOutcomeParsing,
]
for s in suites { s() }
exit(T.report())
