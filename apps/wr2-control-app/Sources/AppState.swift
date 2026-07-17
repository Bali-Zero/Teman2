import Foundation
import SwiftUI
import Combine
import AppKit
import UniformTypeIdentifiers

/// Central observable state for the app. Owns the active run, the gallery, and the queue.
@MainActor
final class AppState: ObservableObject {

    // Run
    @Published var activeRun: Run?
    @Published var rawLog: [String] = []          // bounded raw stream lines
    @Published var pastRuns: [Run] = []

    // Gallery + queue
    @Published var carousels: [Carousel] = []
    @Published var queue: [ReviewItem] = []
    @Published var lastRefresh: Date?
    /// Dirs the A2 complete-or-nothing gate excluded on the last refresh (drafted/
    /// unpublished carousels whose disk PNG count didn't match their declared count).
    /// Surfaced in GalleryView so the exclusion stays observable, not silent (scar #2).
    @Published var excludedIncompleteCount: Int = 0

    /// slug → live/just-finished run, rebuilt every refresh from TWO signals:
    /// the on-disk `.run.json` marker AND a `ps` scan (catches orphan/legacy runs
    /// launched before markers existed or by a since-closed app instance). This is
    /// what un-mutes the app about a rebuild in flight (scar #2).
    @Published var liveRuns: [String: RunMarker] = [:]

    // UI mode
    @Published var mode: AppMode = .work

    // Diagnostics
    @Published var claudePath: String?
    @Published var warRoomOK: Bool = false

    // Brainstorm chat
    @Published var chat: [ChatMessage] = []
    @Published var chatModel: ChatModel = .claude
    @Published var chatBusy: Bool = false
    @Published var pendingTopicFromChat: String?   // last "TOPIC:" the assistant proposed
    @Published var prefillRequest: String = ""     // hand-off from chat → Studio launch field

    private var runner: ClaudeRunner?
    private var chatter: Conversationalist?
    private var pollTimer: Timer?
    private let maxRawLines = 800
    private var activeRunID: UUID?      // H2: which run terminal events belong to

    init() {
        self.claudePath = ClaudeRunner.resolveClaudePath()
        refreshFromDisk()
        startPolling()
    }

    // MARK: - Launch / monitor

    var isRunning: Bool { activeRun?.status == .running || activeRun?.status == .starting }

    /// Turn a human request into a topic prompt for the orchestrator and launch.
    func launch(humanRequest: String) {
        let request = humanRequest.trimmingCharacters(in: .whitespacesAndNewlines)
        guard request.isEmpty == false, isRunning == false else { return }
        launchPrompt(humanRequest: request, topic: Self.toTopicPrompt(request))
    }

    /// Corrective re-run: revise an existing carousel in place with operator feedback,
    /// reusing the same orchestrator + run plumbing as a fresh launch.
    func reviseCarousel(slug: String, feedback: String) {
        guard slug.isEmpty == false, isRunning == false else { return }
        let human = feedback.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            ? "Migliora «\(slug)»" : "Correggi «\(slug)»: \(feedback)"
        launchPrompt(humanRequest: human,
                     topic: PromptBuilder.revisePrompt(slug: slug, feedback: feedback),
                     slug: slug, kind: .revise)
    }

    /// Shared launch plumbing for both fresh and corrective runs.
    /// When `slug` is non-nil the run leaves an on-disk breadcrumb next to the carousel
    /// (`.run.json` + teed `.run.log`) so ANY app instance — post-restart, cross-machine —
    /// can see it's in flight and tail it (scar #2 cure: live run visible on disk).
    private func launchPrompt(humanRequest request: String, topic: String,
                              slug: String? = nil, kind: RunMarker.Kind = .fresh) {
        var run = Run(humanRequest: request, topic: topic)
        self.activeRun = run
        self.activeRunID = run.id      // H2: tag terminal events to THIS run
        self.rawLog = []

        // Where the run's on-disk breadcrumb + live log will live (revise runs only — a
        // fresh run has no slug/dir yet). Captured here so onPID/onTerminate can write it.
        let carouselDir: URL? = slug.map {
            WarRoom.carouselRoot().appendingPathComponent($0, isDirectory: true)
        }
        let logSink = carouselDir.map { RunMarkerStore.logURL(in: $0) }

        let runner = ClaudeRunner()
        self.runner = runner
        let myRunID = run.id
        do {
            try runner.start(
                prompt: topic,
                logSink: logSink,
                onPID: { [weak self] pid in
                    // Drop the on-disk run-marker as soon as we have a real PID, so a
                    // restarted / second app instance can discover this run (scar #2).
                    if let dir = carouselDir, let s = slug {
                        RunMarkerStore.writeStarted(carouselDir: dir, slug: s, pid: pid,
                                                    kind: kind, startedAt: Date())
                    }
                    Task { @MainActor in
                        guard self?.activeRunID == myRunID else { return }
                        self?.activeRun?.pid = pid
                    }
                },
                onEvent: { [weak self] event in
                    Task { @MainActor in
                        guard self?.activeRunID == myRunID else { return }
                        self?.handle(event)
                    }
                },
                onRawLine: { [weak self] line in
                    Task { @MainActor in
                        guard self?.activeRunID == myRunID else { return }
                        self?.appendRaw(line)
                    }
                },
                onTerminate: { [weak self] code in
                    // Flip the breadcrumb to finished (kept on disk for last-outcome display).
                    if let dir = carouselDir {
                        RunMarkerStore.writeFinished(carouselDir: dir, exitCode: code, finishedAt: Date())
                    }
                    Task { @MainActor in self?.handleTerminate(code, runID: myRunID) }
                })
        } catch {
            run.status = .failed
            run.errorMessage = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
            self.activeRun = run
        }
    }

    func cancelRun() {
        runner?.cancel()
        if var r = activeRun {
            r.status = .cancelled
            r.finishedAt = Date()
            activeRun = r
        }
    }

    // MARK: - Brainstorm chat

    func sendChat(_ text: String) {
        let msg = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard msg.isEmpty == false, chatBusy == false else { return }
        let history = chat
        chat.append(ChatMessage(role: .user, text: msg))
        var reply = ChatMessage(role: .assistant, text: "", pending: true)
        chat.append(reply)
        let replyID = reply.id
        chatBusy = true

        let c = Conversationalist()
        self.chatter = c
        c.send(model: chatModel, history: history, user: msg,
               onDelta: { [weak self] delta in
                   guard let self else { return }
                   if let i = self.chat.firstIndex(where: { $0.id == replyID }) {
                       // stream-json assistant events are cumulative snapshots → replace, not append
                       if self.chatModel == .claude { self.chat[i].text = delta }
                       else { self.chat[i].text += (self.chat[i].text.isEmpty ? "" : "\n") + delta }
                   }
               },
               onDone: { [weak self] ok in
                   guard let self else { return }
                   if let i = self.chat.firstIndex(where: { $0.id == replyID }) {
                       self.chat[i].pending = false
                       if self.chat[i].text.isEmpty {
                           self.chat[i].text = ok ? "…" : "⚠︎ Nessuna risposta (riprova)."
                       }
                       self.pendingTopicFromChat = Self.extractTopic(self.chat[i].text)
                   }
                   self.chatBusy = false
               })
        _ = reply  // silence unused warning
    }

    func resetChat() { chat = []; pendingTopicFromChat = nil; chatter?.cancel() }

    /// Pull a "TOPIC: ..." line out of the assistant's reply, if present.
    nonisolated static func extractTopic(_ text: String) -> String? {
        for raw in text.split(separator: "\n") {
            let line = raw.trimmingCharacters(in: .whitespaces)
            for marker in ["TOPIC:", "Topic:", "topic:", "ARGOMENTO:", "TOPIK:"] {
                if line.uppercased().hasPrefix(marker.uppercased()) {
                    let t = line.dropFirst(marker.count).trimmingCharacters(in: .whitespaces)
                    if t.isEmpty == false { return t }
                }
            }
        }
        return nil
    }

    private func handle(_ event: StreamEvent) {
        guard var run = activeRun else { return }
        RunReducer.apply(event, to: &run)
        activeRun = run
    }

    private func appendRaw(_ line: String) {
        rawLog.append(line)
        if rawLog.count > maxRawLines {
            rawLog.removeFirst(rawLog.count - maxRawLines)
        }
    }

    private func handleTerminate(_ code: Int32, runID: UUID) {
        // H2: ignore terminal events from a superseded run (a second launch happened).
        guard var run = activeRun, run.id == runID else { return }
        if run.status == .running || run.status == .starting {
            // process exited without a clean result event
            if code == 0 {
                run.status = .succeeded
            } else {
                run.status = .failed
                if run.errorMessage == nil {
                    run.errorMessage = "La pipeline si è chiusa con codice \(code) senza un risultato."
                }
            }
            run.finishedAt = Date()
        }
        activeRun = run
        // M1: never insert the same run twice (double-cancel / racing terminal events).
        if pastRuns.contains(where: { $0.id == run.id }) == false {
            pastRuns.insert(run, at: 0)
        }
        refreshFromDisk()   // a finished run likely produced a new carousel
        if run.status == .succeeded { enqueueNewestCarousel() }
    }

    /// Close the Step-7 enqueue gap: after a successful run, the orchestrator has rendered a
    /// carousel to output/carousel/<slug>/ but may not have written its review-queue row, so it
    /// never appears in Revisione. Find the newest on-disk carousel that is NOT yet in the queue
    /// and append a `drafted` entry for it. Idempotent + atomic in QueueWriter.
    private func enqueueNewestCarousel() {
        let queued = Set(queue.compactMap { $0.topic_slug })
        guard let fresh = carousels
            .filter({ queued.contains($0.slug) == false })
            .max(by: { $0.modified < $1.modified })
        else { return }
        let iso = ISO8601DateFormatter().string(from: fresh.modified)
        do {
            let appended = try QueueWriter.enqueueDrafted(
                queueFile: WarRoom.queueFile(), slug: fresh.slug,
                slideCount: fresh.slideCount, isoTimestamp: iso)
            if appended { refreshFromDisk() }   // surface the new drafted row in Revisione
        } catch {
            // non-fatal: carousel is on disk regardless; enqueue can be retried manually
        }
    }

    /// Convert a colloquial request into the orchestrator prompt.
    static func toTopicPrompt(_ request: String) -> String {
        PromptBuilder.toTopicPrompt(request)
    }

    // MARK: - PNG import / export (download slides, upload a carousel)

    /// Lightweight banner for IO outcomes, shown briefly in the detail view.
    @Published var ioNotice: String?

    /// The slug of a carousel that just arrived via "Importa carosello esterno", so
    /// Revisione can highlight the new row instead of it silently appearing in the
    /// list (scar #2 discipline — same spirit as RunPill: don't be mute about state
    /// changes). Cleared automatically a few seconds after it's set.
    @Published var highlightedSlug: String?

    private func notice(_ s: String) {
        ioNotice = s
        // auto-clear after a few seconds
        let mine = s
        Task { @MainActor in
            try? await Task.sleep(nanoseconds: 4_000_000_000)
            if self.ioNotice == mine { self.ioNotice = nil }
        }
    }

    // MARK: - Local re-render (no agent, no wait)

    /// The slug currently being re-rendered, if any — drives the button's spinner +
    /// disabled state. Distinct from `isRunning` (an orchestrator run): a local
    /// re-render is a 2-3s python call, not a 15-min agent.
    @Published var reRenderingSlug: String?

    /// The slug currently being published (or dry-run validated) to Instagram, if
    /// any — drives the publish button's spinner + disabled state. Like
    /// `reRenderingSlug`, it is a short-lived shell call, not an orchestrator run.
    @Published var isPublishingSlug: String?

    /// Re-render a carousel's PNGs straight from its on-disk slides.json, reusing the
    /// PRODUCTION renderer (`scripts/wr2_rerender_local.py`, fast/no-vision default).
    ///
    /// WHY this exists next to "Migliora": "Migliora" drives the full wr2-design-architect
    /// agent — it re-reasons about feedback (~15 min). When the slides.json is ALREADY in
    /// the desired shape (operator/agent edited the copy directly), there's nothing to
    /// reason about — only re-render. This is that fast path: ~2-3s, deterministic, no DB
    /// write, no Drive upload. So the operator doesn't have to click Migliora and wait.
    func reRenderCarousel(slug: String, lang: LanguageManager) {
        let s = slug.trimmingCharacters(in: .whitespaces)
        guard s.isEmpty == false, reRenderingSlug == nil else { return }
        reRenderingSlug = s
        notice(lang.t("io.rerendering"))

        // Run the renderer exactly as the CLI does: PYTHONPATH=scripts + venv python,
        // from the monorepo root (where war-room relative paths resolve). zsh -lc so
        // mise shims resolve, matching ClaudeRunner.workingDirectory().
        let repo = ClaudeRunner.workingDirectory()
        let venvPy = repo.appendingPathComponent("apps/backend-rag/.venv/bin/python").path
        // Escape the slug for the shell (defense-in-depth — slugs are dir names, but
        // never trust a value going into a command line).
        let safeSlug = s.replacingOccurrences(of: "'", with: "'\\''")
        let cmd = "PYTHONPATH=scripts exec '\(venvPy)' -m wr2_rerender_local '\(safeSlug)'"

        // SAFETY (cicatrice 2026-06-25): the renderer CLEARS the slide PNGs before
        // regenerating. If the render step crashes (e.g. Playwright browser missing), the
        // carousel is left mutilated with no slides. Back them up first; restore on failure
        // so a failed re-render is a no-op, never a destroyed carousel.
        let slidesDir = WarRoom.carouselRoot()
            .appendingPathComponent(s, isDirectory: true)
            .appendingPathComponent("slides", isDirectory: true)
        let backupDir = Self.backupSlidePNGs(in: slidesDir)

        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/zsh")
        p.arguments = ["-lc", cmd]
        p.currentDirectoryURL = repo
        var env = ProcessInfo.processInfo.environment
        env.removeValue(forKey: "ANTHROPIC_API_KEY")   // defense-in-depth (no paid path)
        env["CI"] = "1"
        p.environment = env

        // Capture the tail so a failure shows WHY (the renderer prints its gate verdict).
        let outPipe = Pipe()
        p.standardOutput = outPipe
        p.standardError = outPipe

        p.terminationHandler = { [weak self] proc in
            let data = outPipe.fileHandleForReading.readDataToEndOfFile()
            let out = String(data: data, encoding: .utf8) ?? ""
            let code = proc.terminationStatus
            if code != 0 {
                // Failed → put the slides back exactly as they were (no mutilation).
                Self.restoreSlidePNGs(from: backupDir, to: slidesDir)
            }
            Self.cleanupBackup(backupDir)
            Task { @MainActor in
                guard let self else { return }
                self.reRenderingSlug = nil
                if code == 0 {
                    self.notice(lang.t("io.rerendered"))
                    self.refreshFromDisk()   // pick up the fresh PNGs
                } else {
                    // Surface the last meaningful line of the renderer's output.
                    let lastLine = out.split(separator: "\n")
                        .last(where: { $0.contains("ERROR") || $0.contains("gate") || $0.contains("failed") })
                        .map(String.init) ?? "exit \(code)"
                    self.notice("⚠︎ " + lastLine + " · slide ripristinate")
                }
            }
        }

        do {
            try p.run()
        } catch {
            // process never started → restore immediately (carousel untouched)
            Self.restoreSlidePNGs(from: backupDir, to: slidesDir)
            Self.cleanupBackup(backupDir)
            reRenderingSlug = nil
            notice("⚠︎ \(error.localizedDescription)")
        }
    }

    /// Load the deterministic WR2 caption without credentials, upload, or network calls.
    func loadInstagramCaption(
        slug: String,
        completion: @escaping (Result<String, Error>) -> Void
    ) {
        let s = slug.trimmingCharacters(in: .whitespacesAndNewlines)
        guard s.isEmpty == false else {
            completion(.failure(NSError(
                domain: "WR2Caption", code: 1,
                userInfo: [NSLocalizedDescriptionKey: "Slug del carosello mancante."]
            )))
            return
        }

        let repo = ClaudeRunner.workingDirectory()
        let python = repo.appendingPathComponent("apps/backend-rag/.venv/bin/python")
        let process = Process()
        process.executableURL = python
        process.arguments = InstagramCaption.previewArguments(slug: s)
        process.currentDirectoryURL = repo
        var environment = ProcessInfo.processInfo.environment
        environment.removeValue(forKey: "ANTHROPIC_API_KEY")
        environment["CI"] = "1"
        process.environment = environment

        let stdout = Pipe()
        let stderr = Pipe()
        process.standardOutput = stdout
        process.standardError = stderr
        process.terminationHandler = { proc in
            let output = String(
                data: stdout.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8
            ) ?? ""
            let errorOutput = String(
                data: stderr.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8
            ) ?? ""
            Task { @MainActor in
                if proc.terminationStatus == 0, InstagramCaption.isPublishable(output) {
                    completion(.success(output))
                } else {
                    let message = errorOutput.split(separator: "\n").last.map(String.init)
                        ?? "Impossibile generare la caption."
                    completion(.failure(NSError(
                        domain: "WR2Caption", code: Int(proc.terminationStatus),
                        userInfo: [NSLocalizedDescriptionKey: message]
                    )))
                }
            }
        }

        do {
            try process.run()
        } catch {
            completion(.failure(error))
        }
    }

    /// Publish (or dry-run validate) a carousel to Instagram via the Fly backend.
    ///
    /// LEGGE 5 — nothing posts without an explicit operator click. The 2-step flow
    /// the view drives: first call with `confirm: false` (a dry run — the backend
    /// uploads the slides to Tigris and assembles the Graph CAROUSEL container but
    /// NEVER calls /media_publish), then, only on the operator's explicit confirm,
    /// call again with `confirm: true` to actually post.
    ///
    /// Unlike Re-render (a LOCAL renderer script), publish MUST go through the
    /// backend: only Fly has the Tigris creds + the ledger DB + the IG token. So
    /// this runs `scripts/wr2_ig_publish_remote.py`, a pure HTTP client that logs
    /// in, uploads the slides, and POSTs the operator-approved caption.
    /// The completion is surfaced via the same `ioNotice` banner as Re-render.
    func publishToInstagram(
        slug: String, caption: String, lang: LanguageManager, confirm: Bool
    ) {
        let s = slug.trimmingCharacters(in: .whitespaces)
        guard s.isEmpty == false,
              InstagramCaption.isPublishable(caption),
              isPublishingSlug == nil else { return }

        let captionFile: URL
        do {
            captionFile = try InstagramCaption.writeTemporaryFile(caption)
        } catch {
            notice("⚠︎ \(error.localizedDescription)")
            return
        }

        isPublishingSlug = s
        notice(lang.t(confirm ? "io.publishing" : "io.publishChecking"))

        let repo = ClaudeRunner.workingDirectory()
        let python = repo.appendingPathComponent("apps/backend-rag/.venv/bin/python")

        let p = Process()
        p.executableURL = python
        p.arguments = InstagramCaption.publishArguments(
            slug: s, captionFile: captionFile, confirm: confirm
        )
        p.currentDirectoryURL = repo
        var env = ProcessInfo.processInfo.environment
        env.removeValue(forKey: "ANTHROPIC_API_KEY")   // defense-in-depth (no paid path)
        env["CI"] = "1"
        p.environment = env

        let outPipe = Pipe()
        p.standardOutput = outPipe
        p.standardError = outPipe

        p.terminationHandler = { [weak self] proc in
            let data = outPipe.fileHandleForReading.readDataToEndOfFile()
            let out = String(data: data, encoding: .utf8) ?? ""
            let code = proc.terminationStatus
            try? FileManager.default.removeItem(at: captionFile)
            Task { @MainActor in
                guard let self else { return }
                self.isPublishingSlug = nil
                if code == 0 {
                    if confirm {
                        // Surface the permalink line if the CLI printed one.
                        let permalink = out.split(separator: "\n")
                            .last(where: { $0.contains("instagram.com/p/") })
                            .map(String.init)
                        self.notice("✓ " + lang.t("io.published") + (permalink.map { " · \($0.suffix(40))" } ?? ""))
                        self.refreshFromDisk()
                    } else {
                        self.notice("✓ " + lang.t("io.publishChecked"))
                    }
                } else {
                    let lastLine = out.split(separator: "\n")
                        .last(where: { $0.contains("ABORTED") || $0.contains("ERROR") || $0.contains("failed") })
                        .map(String.init) ?? "exit \(code)"
                    self.notice("⚠︎ " + lastLine)
                }
            }
        }

        do {
            try p.run()
        } catch {
            try? FileManager.default.removeItem(at: captionFile)
            isPublishingSlug = nil
            notice("⚠︎ \(error.localizedDescription)")
        }
    }

    // MARK: - Re-render slide backup/restore (cicatrice 2026-06-25: failed re-render
    // must never leave a carousel without slides)

    /// Copy the slide PNGs to a temp dir; returns the backup dir (nil if nothing to back up).
    nonisolated static func backupSlidePNGs(in slidesDir: URL) -> URL? {
        let fm = FileManager.default
        guard let entries = try? fm.contentsOfDirectory(at: slidesDir,
                  includingPropertiesForKeys: nil, options: [.skipsHiddenFiles]) else { return nil }
        let pngs = entries.filter { $0.pathExtension.lowercased() == "png" }
        guard pngs.isEmpty == false else { return nil }
        let bak = fm.temporaryDirectory.appendingPathComponent("wr2-rerender-bak-\(UUID().uuidString)")
        guard (try? fm.createDirectory(at: bak, withIntermediateDirectories: true)) != nil else { return nil }
        for p in pngs {
            try? fm.copyItem(at: p, to: bak.appendingPathComponent(p.lastPathComponent))
        }
        return bak
    }

    /// Restore backed-up PNGs into slidesDir (overwriting), so a failed render is a no-op.
    nonisolated static func restoreSlidePNGs(from backupDir: URL?, to slidesDir: URL) {
        guard let bak = backupDir else { return }
        let fm = FileManager.default
        guard let entries = try? fm.contentsOfDirectory(at: bak, includingPropertiesForKeys: nil) else { return }
        for p in entries where p.pathExtension.lowercased() == "png" {
            let dest = slidesDir.appendingPathComponent(p.lastPathComponent)
            try? fm.removeItem(at: dest)
            try? fm.copyItem(at: p, to: dest)
        }
    }

    nonisolated static func cleanupBackup(_ backupDir: URL?) {
        if let b = backupDir { try? FileManager.default.removeItem(at: b) }
    }

    /// Save ONE slide PNG via an NSSavePanel (suggested name `<slug>-NN.png`).
    func exportSlide(slug: String, index: Int, src: URL, lang: LanguageManager) {
        let panel = NSSavePanel()
        panel.allowedContentTypes = [.png]
        panel.nameFieldStringValue = "\(CarouselIO.safeSlug(slug))-\(String(format: "%02d", index + 1)).png"
        panel.canCreateDirectories = true
        guard panel.runModal() == .OK, let dest = panel.url else { return }
        do {
            try CarouselIO.exportSlide(src, to: dest)
            notice(lang.t("io.savedOne"))
        } catch { notice("⚠︎ \(error.localizedDescription)") }
    }

    /// Save the WHOLE carousel into a user-chosen folder, as `<slug>/01.png…NN.png`.
    func exportCarousel(_ carousel: Carousel, lang: LanguageManager) {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.canCreateDirectories = true
        panel.prompt = lang.t("io.chooseFolder")
        guard panel.runModal() == .OK, let folder = panel.url else { return }
        do {
            let (outDir, n) = try CarouselIO.exportCarousel(
                slug: carousel.slug, slides: carousel.slidePNGs, into: folder)
            notice(String(format: lang.t("io.savedAll"), n))
            NSWorkspace.shared.activateFileViewerSelecting([outDir])
        } catch { notice("⚠︎ \(error.localizedDescription)") }
    }

    /// Import a carousel from PNGs the user picks, name it, write it to the war-room,
    /// and enqueue it as `drafted` so it surfaces in Revisione.
    func importCarousel(lang: LanguageManager) {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = true
        panel.allowedContentTypes = [.png]
        panel.prompt = lang.t("io.pickPNGs")
        guard panel.runModal() == .OK, panel.urls.isEmpty == false else { return }
        let pngs = panel.urls

        // ask for a name (default derived from the first file's parent folder)
        let suggested = pngs.first?.deletingLastPathComponent().lastPathComponent ?? "upload"
        let alert = NSAlert()
        alert.messageText = lang.t("io.nameTitle")
        alert.informativeText = lang.t("io.nameInfo")
        let field = NSTextField(frame: NSRect(x: 0, y: 0, width: 260, height: 24))
        field.stringValue = CarouselIO.safeSlug(suggested)
        alert.accessoryView = field
        alert.addButton(withTitle: lang.t("io.create"))
        alert.addButton(withTitle: lang.t("studio.cancel"))
        guard alert.runModal() == .alertFirstButtonReturn else { return }
        let slug = CarouselIO.safeSlug(field.stringValue)

        do {
            let (dir, n) = try CarouselIO.importCarousel(
                slug: slug, pngs: pngs, carouselRoot: WarRoom.carouselRoot())
            // enqueue as drafted so it shows in Revisione (idempotent + atomic)
            let iso = ISO8601DateFormatter().string(from: Date())
            _ = try? QueueWriter.enqueueDrafted(
                queueFile: WarRoom.queueFile(), slug: dir.lastPathComponent,
                slideCount: n, isoTimestamp: iso)
            refreshFromDisk()
            notice(String(format: lang.t("io.uploaded"), n))
            NSWorkspace.shared.activateFileViewerSelecting([dir])
        } catch { notice("⚠︎ \(error.localizedDescription)") }
    }

    // MARK: - External carousel import (PDF / folder / images → normalizer pipeline)

    /// True while `wr2_carousel_import.py` is running — drives the sheet's spinner +
    /// disabled state, like `reRenderingSlug`/`isPublishingSlug` do for their actions.
    @Published var externalImportBusy: Bool = false

    /// Import an externally-produced carousel (a single PDF, a folder of images, or
    /// several loose image files) via `scripts/wr2_carousel_import.py`. The script does
    /// the heavy lifting (normalize to 1080×1350 PNG, create the carousel dir, append a
    /// `drafted` queue row) — this just launches it, streams its stderr progress lines
    /// live via `onProgress`, and on success refreshes the gallery/queue so the import
    /// surfaces in Revisione automatically (same Step-7 handoff contract as
    /// `enqueueNewestCarousel`, just written by the script instead of by us).
    ///
    /// stdout carries exactly one JSON result line (contract); stderr carries progress —
    /// so, unlike the streaming ClaudeRunner, only stderr needs a live readabilityHandler.
    /// stdout is captured in full at termination, matching reRenderCarousel/publishToInstagram.
    func importExternalCarousel(
        inputs: [URL], topic: String, fit: ExternalImport.FitMode,
        onProgress: @escaping (String) -> Void,
        completion: @escaping (ExternalImport.ParsedOutcome) -> Void
    ) {
        guard externalImportBusy == false, inputs.isEmpty == false else { return }
        externalImportBusy = true

        let repo = ClaudeRunner.workingDirectory()
        let scriptPath = repo.appendingPathComponent(ExternalImport.scriptRelativePath).path
        let venvPython = repo.appendingPathComponent("apps/backend-rag/.venv/bin/python")
        let scriptArgs = ExternalImport.scriptArguments(inputs: inputs, topic: topic, fit: fit)

        let p = Process()
        if FileManager.default.isExecutableFile(atPath: venvPython.path) {
            p.executableURL = venvPython
            p.arguments = [scriptPath] + scriptArgs
        } else {
            // Fallback to the frozen contract's literal invocation if the repo venv isn't
            // present — `/usr/bin/env` resolves `python3` off PATH.
            p.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            p.arguments = ["python3", scriptPath] + scriptArgs
        }
        p.currentDirectoryURL = repo
        var env = ProcessInfo.processInfo.environment
        env.removeValue(forKey: "ANTHROPIC_API_KEY")   // defense-in-depth (no paid path)
        env["CI"] = "1"
        p.environment = env

        let outPipe = Pipe()
        let errPipe = Pipe()
        p.standardOutput = outPipe
        p.standardError = errPipe

        errPipe.fileHandleForReading.readabilityHandler = { handle in
            let chunk = handle.availableData
            guard chunk.isEmpty == false, let s = String(data: chunk, encoding: .utf8) else { return }
            for line in s.split(separator: "\n", omittingEmptySubsequences: true) {
                let text = String(line)
                DispatchQueue.main.async { onProgress(text) }
            }
        }

        p.terminationHandler = { [weak self] proc in
            errPipe.fileHandleForReading.readabilityHandler = nil
            let outData = outPipe.fileHandleForReading.readDataToEndOfFile()
            let out = String(data: outData, encoding: .utf8) ?? ""
            let outcome = ExternalImport.parseOutcome(stdout: out, exitCode: proc.terminationStatus)
            Task { @MainActor in
                guard let self else { return }
                self.externalImportBusy = false
                if case .success(let s) = outcome {
                    self.refreshFromDisk()
                    self.highlightedSlug = s.slug
                    self.notice("✓ " + s.slug)
                    Task { @MainActor in
                        try? await Task.sleep(nanoseconds: 6_000_000_000)
                        if self.highlightedSlug == s.slug { self.highlightedSlug = nil }
                    }
                }
                completion(outcome)
            }
        }

        do {
            try p.run()
        } catch {
            externalImportBusy = false
            completion(.failure(error.localizedDescription))
        }
    }

    // MARK: - External post registration (§A, 2026-07-17 — "aggiungi upload e URL di
    // un post che abbiamo fatto e non obbligatoriamente passato per la app")

    /// Register a manually-published Instagram post that bypassed the WR2 pipeline
    /// entirely — no drafted carousel ever existed for it. Validates the URL/topic
    /// (ExternalPostRegistration, pure), optionally copies+converts picked images to
    /// PNG under `<root>/carousel/external-<date>-<slug>/slides/` (numeric naming so
    /// WarRoom's existing cover/scan logic just works — that logic only recognizes
    /// `.png`, so a JPG pick is re-encoded, not just renamed), then appends the queue
    /// entry via `QueueWriter.addExternalPost` (throws on validation failure or
    /// duplicate URL/id — refused, not silently ignored) and refreshes the gallery so
    /// the new card appears immediately, matching `importCarousel`'s idiom.
    func addExternalPost(igURLRaw: String, topicRaw: String, publishDate: Date,
                         images: [URL], lang: LanguageManager) throws {
        let url = try ExternalPostRegistration.canonicalizeInstagramURL(igURLRaw)
        let topic = try ExternalPostRegistration.validateTopic(topicRaw)
        let slug = CarouselIO.safeSlug(topic)
        guard slug.isEmpty == false else { throw ExternalPostRegistration.ValidationError.emptyTopic }

        var carouselPath: String?
        var slideCount = 0
        if images.isEmpty == false {
            let dirName = ExternalPostRegistration.carouselDirName(publishDate: publishDate, slug: slug)
            let dir = WarRoom.carouselRoot().appendingPathComponent(dirName, isDirectory: true)
            let slidesDir = dir.appendingPathComponent("slides", isDirectory: true)
            try FileManager.default.createDirectory(at: slidesDir, withIntermediateDirectories: true)
            for (i, src) in images.enumerated() {
                let dest = slidesDir.appendingPathComponent(String(format: "%02d.png", i + 1))
                try Self.writeImageAsPNG(from: src, to: dest)
            }
            slideCount = images.count
            carouselPath = "~/nuzantara/apps/war-room/output/carousel/\(dirName)/"
        }

        let entry = ExternalPostRegistration.buildQueueEntry(
            instagramURL: url, topic: topic, slug: slug, publishDate: publishDate,
            slideCount: slideCount, carouselPath: carouselPath)
        try QueueWriter.addExternalPost(queueFile: WarRoom.queueFile(), entry: entry)
        refreshFromDisk()
        notice("✓ " + lang.t("externalPost.saved"))
    }

    /// Copy `src` to `dest` as PNG. A `.png` source is a plain file copy; any other
    /// image type (JPG etc., per §A's "PNG/JPG" acceptance) is decoded and re-encoded
    /// via NSImage/NSBitmapImageRep — `WarRoom.slidePNGs` filters strictly on `.png`
    /// extension, so a bytes-only rename would silently vanish from the slide count.
    private static func writeImageAsPNG(from src: URL, to dest: URL) throws {
        if FileManager.default.fileExists(atPath: dest.path) {
            try FileManager.default.removeItem(at: dest)
        }
        if src.pathExtension.lowercased() == "png" {
            try FileManager.default.copyItem(at: src, to: dest)
            return
        }
        guard let image = NSImage(contentsOf: src),
              let tiff = image.tiffRepresentation,
              let rep = NSBitmapImageRep(data: tiff),
              let png = rep.representation(using: .png, properties: [:]) else {
            throw NSError(domain: "AppState", code: 1, userInfo: [
                NSLocalizedDescriptionKey: "Non riesco a leggere l'immagine: \(src.lastPathComponent)"
            ])
        }
        try png.write(to: dest)
    }

    // MARK: - Disk refresh (gallery + queue)

    func refreshFromDisk() {
        let root = WarRoom.defaultOutputRoot()
        warRoomOK = FileManager.default.fileExists(atPath: root.path)
        let q = WarRoom.readQueue()
        let c = WarRoom.scanCarousels(queue: q)
        self.queue = q
        self.carousels = c
        self.excludedIncompleteCount = WarRoom.excludedIncompleteCount
        self.liveRuns = Self.detectLiveRuns(carousels: c)
        self.lastRefresh = Date()
    }

    /// Build the slug → run map from disk markers + a process-table scan.
    /// Signal 1 (marker): authoritative kind/started-at; if its PID is dead and it never
    ///   wrote a `finished` record, we still show it as finished (outcome-unknown) rather
    ///   than "running forever".
    /// Signal 2 (ps): a live `claude -p ... <slug>` with no marker (orphan/legacy run) is
    ///   synthesised into a live `.revise` marker so the UI still shows "in corso".
    nonisolated static func detectLiveRuns(carousels: [Carousel]) -> [String: RunMarker] {
        var out: [String: RunMarker] = [:]
        // disk markers
        for c in carousels {
            if var m = RunMarkerStore.read(in: c.directory) {
                if RunMarkerStore.isStaleLive(m) {
                    // PID gone, no finished record — present as finished, code unknown.
                    m = RunMarker(slug: m.slug, pid: m.pid, kind: m.kind,
                                  startedAt: m.startedAt, finishedAt: Date(), exitCode: nil)
                }
                out[c.slug] = m
            }
        }
        // ps fallback for runs with no marker yet
        let slugs = carousels.map { $0.slug }
        let psHits = ProcessProbe.liveOrchestratorRuns(knownSlugs: slugs)
        for (slug, pid) in psHits where out[slug] == nil {
            out[slug] = RunMarker(slug: slug, pid: pid, kind: .revise,
                                  startedAt: ProcessProbe.startTime(of: pid) ?? Date(),
                                  finishedAt: nil, exitCode: nil)
        }
        return out
    }

    /// Tail of the on-disk run log for a carousel (last `maxLines` lines), for the
    /// detail view's live console. Empty when there is no log.
    nonisolated static func runLogTail(slug: String, maxLines: Int = 200) -> [String] {
        let dir = WarRoom.carouselRoot().appendingPathComponent(slug, isDirectory: true)
        let url = RunMarkerStore.logURL(in: dir)
        guard let text = try? String(contentsOf: url, encoding: .utf8) else { return [] }
        let lines = text.split(separator: "\n", omittingEmptySubsequences: false).map(String.init)
        return Array(lines.suffix(maxLines))
    }

    private func startPolling() {
        // light poll so gallery/queue reflect on-disk changes during a run
        pollTimer = Timer.scheduledTimer(withTimeInterval: 4.0, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.refreshFromDisk() }
        }
    }

    // MARK: - Publish actions

    /// Mark a carousel as published. Calls QueueWriter atomically, then refreshes the
    /// gallery. On error, appends a ⚠︎-prefixed line to `rawLog` — never crashes.
    func markPublished(slug: String, igURL: String, publishedAt: String) {
        do {
            try QueueWriter.markPublished(queueFile: WarRoom.queueFile(),
                                          slug: slug, igURL: igURL, publishedAt: publishedAt)
            refreshFromDisk()
        } catch {
            rawLog.append("⚠︎ mark-published (\(slug)): \(error.localizedDescription)")
        }
    }

    /// Reverse a mark-published action. Restores prior state in the queue, then
    /// refreshes the gallery. On error, appends a ⚠︎-prefixed line to `rawLog`.
    func undoPublished(slug: String) {
        do {
            try QueueWriter.undoPublished(queueFile: WarRoom.queueFile(), slug: slug)
            refreshFromDisk()
        } catch {
            rawLog.append("⚠︎ undo-published (\(slug)): \(error.localizedDescription)")
        }
    }

    // MARK: - Viral cover selection

    /// Published carousels with a non-nil shares metric within `windowDays` of `now`,
    /// sorted by shares DESC then reach DESC. Thin wrapper over ViralSelector so any
    /// caller gets the same semantics; the pure logic lives in ViralSelector.swift
    /// (Foundation-only, CLI-testable without SwiftUI).
    nonisolated static func viralCovers(_ carousels: [Carousel], now: Date, windowDays: Int) -> [Carousel] {
        ViralSelector.viralCovers(carousels, now: now, windowDays: windowDays)
    }
}
