import Foundation

/// Wraps the `claude` CLI as a child process and streams its stream-json output.
///
/// Auth: relies ENTIRELY on the system OAuth (`CLAUDE_CODE_OAUTH_TOKEN` in the inherited
/// environment). It never reads or sets `ANTHROPIC_API_KEY` — in fact it STRIPS it from the
/// child environment as defense-in-depth (mirrors apps/backend-rag/.../claude_oauth_client.py),
/// so a stray paid key can never be used. No Anthropic SDK anywhere.
final class ClaudeRunner {

    enum RunnerError: Error, LocalizedError {
        case claudeNotFound
        case launchFailed(String)
        var errorDescription: String? {
            switch self {
            case .claudeNotFound:
                return "Non trovo il comando 'claude' sul sistema. Assicurati che sia installato e nel PATH."
            case .launchFailed(let m):
                return "Impossibile avviare la pipeline: \(m)"
            }
        }
    }

    private var process: Process?
    private var stdoutBuffer = Data()
    private let lineQueue = DispatchQueue(label: "wr2.runner.lines")
    /// Optional disk sink: every raw line is teed here so any app instance (post-restart,
    /// cross-machine) can tail an in-flight run. nil ⇒ no disk log (e.g. fresh launch with
    /// no slug yet). Opened in start(), closed in the termination handler.
    private var logHandle: FileHandle?

    /// Locate the `claude` executable. The interactive shell aliases `claude`, but a child
    /// Process has no alias — resolve the real binary path via the user's login shell.
    static func resolveClaudePath() -> String? {
        // 1) common explicit locations first (fast, no shell spawn)
        let candidates = [
            "\(NSHomeDirectory())/.local/share/mise/installs/node/22/bin/claude",
            "\(NSHomeDirectory())/.local/bin/claude",
            "/opt/homebrew/bin/claude",
            "/usr/local/bin/claude",
        ]
        for c in candidates where FileManager.default.isExecutableFile(atPath: c) { return c }

        // 2) ask the login shell to resolve it (handles mise shims / aliases → real path)
        let probe = Process()
        probe.executableURL = URL(fileURLWithPath: "/bin/zsh")
        probe.arguments = ["-lc", "command -v claude || which claude"]
        let pipe = Pipe()
        probe.standardOutput = pipe
        probe.standardError = Pipe()
        do {
            try probe.run()
            probe.waitUntilExit()
            let out = String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
            let path = out.trimmingCharacters(in: .whitespacesAndNewlines)
                .components(separatedBy: "\n").first ?? ""
            if path.isEmpty == false, FileManager.default.isExecutableFile(atPath: path) {
                return path
            }
            // mise sometimes prints a shim path that is a .exe wrapper; accept it if runnable
            if path.isEmpty == false { return path }
        } catch { /* fall through */ }
        return nil
    }

    /// Build the working directory the agent should run in (the monorepo root, where
    /// war-room relative paths resolve). Falls back to home if not present.
    static func workingDirectory() -> URL {
        let repo = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("nuzantara", isDirectory: true)
        var isDir: ObjCBool = false
        if FileManager.default.fileExists(atPath: repo.path, isDirectory: &isDir), isDir.boolValue {
            return repo
        }
        return FileManager.default.homeDirectoryForCurrentUser
    }

    /// Model for AGENT-LESS claude legs (chat, caption, import). Explicit pin per
    /// routing rule 2026-07-14 ("every leg carries an explicit model — never
    /// inherit the session default"): the interactive default may be Fable 5,
    /// whose window is the final-gate budget, not the app's. Override via
    /// WR2_APP_CLAUDE_MODEL when launching from a shell; single-quote-stripped
    /// so it can never break out of the shell quoting in the command line.
    static func headlessModel() -> String {
        let raw = ProcessInfo.processInfo.environment["WR2_APP_CLAUDE_MODEL"] ?? "claude-sonnet-5"
        return raw.replacingOccurrences(of: "'", with: "")
    }

    /// Start a run. Callbacks fire on the main queue.
    /// - onEvent: each decoded stream-json event
    /// - onRawLine: each raw line (for the raw-log pane)
    /// - onTerminate: process exit (code)
    func start(prompt: String,
               agent: String = "wr2-design-architect",
               logSink: URL? = nil,
               onPID: @escaping (Int32) -> Void,
               onEvent: @escaping (StreamEvent) -> Void,
               onRawLine: @escaping (String) -> Void,
               onTerminate: @escaping (Int32) -> Void) throws {

        guard let claude = Self.resolveClaudePath() else { throw RunnerError.claudeNotFound }

        // Open the disk log sink (truncating) so a fresh run starts a fresh tail. Best-effort:
        // a failure here is non-fatal — the run still streams to the in-RAM rawLog.
        if let sink = logSink {
            FileManager.default.createFile(atPath: sink.path, contents: nil)
            self.logHandle = try? FileHandle(forWritingTo: sink)
        }

        let p = Process()
        // Use zsh -lc so mise shims / PATH resolve exactly as in an interactive session,
        // while still being non-interactive (-c) and login (-l for full env).
        p.executableURL = URL(fileURLWithPath: "/bin/zsh")

        // Quote the prompt safely for the shell.
        let safePrompt = prompt.replacingOccurrences(of: "'", with: "'\\''")
        // Only pass --agent when a non-empty agent name is given. An empty value would make
        // the shell hand `--agent` the NEXT flag (`--output-format`) as its value (bug fixed
        // 2026-06-21: empty agent silently broke stream-json output).
        let agentNameRaw = agent.trimmingCharacters(in: .whitespaces)
        // L1: escape single-quotes in the agent name too (defense-in-depth — no shell injection
        // even if a future caller passes a dynamic agent name).
        let agentName = agentNameRaw.replacingOccurrences(of: "'", with: "'\\''")
        let agentFlag = agentName.isEmpty ? "" : "--agent '\(agentName)' "
        // Model pin (2026-07-14): agent-less runs must NEVER inherit the session
        // default model — when that default is Fable 5 (interactive final-gate tier)
        // every app action dies the moment the Fable window is exhausted, and burns
        // final-gate quota even when it isn't (routing rule: headless app legs =
        // Sonnet). Agent runs keep the model pinned in their agent frontmatter.
        let modelFlag = agentName.isEmpty ? "--model '\(Self.headlessModel())' " : ""
        let cmd = "exec '\(claude)' -p '\(safePrompt)' \(agentFlag)\(modelFlag)"
            + "--output-format stream-json --verbose --permission-mode bypassPermissions"
        p.arguments = ["-lc", cmd]
        p.currentDirectoryURL = Self.workingDirectory()

        // Environment: inherit, but STRIP any paid Anthropic key (defense-in-depth).
        var env = ProcessInfo.processInfo.environment
        env.removeValue(forKey: "ANTHROPIC_API_KEY")
        // ensure non-interactive
        env["CI"] = "1"
        p.environment = env

        let outPipe = Pipe()
        let errPipe = Pipe()
        p.standardOutput = outPipe
        p.standardError = errPipe

        outPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let chunk = handle.availableData
            guard chunk.isEmpty == false else { return }
            self?.lineQueue.async {
                self?.stdoutBuffer.append(chunk)
                self?.drainLines { line in
                    self?.teeToLog(line)
                    DispatchQueue.main.async {
                        onRawLine(line)
                        if let ev = StreamEvent.parse(line: line) { onEvent(ev) }
                    }
                }
            }
        }

        // stderr: surface as raw lines too (human can see real errors)
        errPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let chunk = handle.availableData
            guard chunk.isEmpty == false,
                  let s = String(data: chunk, encoding: .utf8) else { return }
            for line in s.split(separator: "\n", omittingEmptySubsequences: true) {
                self?.teeToLog("⚠︎ " + String(line))
                DispatchQueue.main.async { onRawLine("⚠︎ " + String(line)) }
            }
        }

        p.terminationHandler = { [weak self] proc in
            outPipe.fileHandleForReading.readabilityHandler = nil
            errPipe.fileHandleForReading.readabilityHandler = nil
            // Drain any stdout that arrived after the last readability callback (the final
            // `result` event is often in this tail). Process it on the same serial lineQueue
            // so ordering is preserved, THEN signal termination.
            let tail = outPipe.fileHandleForReading.readDataToEndOfFile()
            let finish = {
                self?.lineQueue.async {
                    if tail.isEmpty == false { self?.stdoutBuffer.append(tail) }
                    self?.drainLines { line in
                        self?.teeToLog(line)
                        DispatchQueue.main.async {
                            onRawLine(line)
                            if let ev = StreamEvent.parse(line: line) { onEvent(ev) }
                        }
                    }
                    // flush any partial trailing line that has no newline
                    if let self, self.stdoutBuffer.isEmpty == false,
                       let line = String(data: self.stdoutBuffer, encoding: .utf8) {
                        self.stdoutBuffer.removeAll()
                        self.teeToLog(line)
                        DispatchQueue.main.async {
                            onRawLine(line)
                            if let ev = StreamEvent.parse(line: line) { onEvent(ev) }
                        }
                    }
                    // close the disk log sink once all output is flushed
                    self?.closeLog()
                    // onTerminate must run AFTER the tail events are dispatched to main
                    DispatchQueue.main.async { onTerminate(proc.terminationStatus) }
                }
            }
            if self == nil {
                DispatchQueue.main.async { onTerminate(proc.terminationStatus) }
            } else {
                finish()
            }
        }

        do {
            try p.run()
        } catch {
            throw RunnerError.launchFailed(error.localizedDescription)
        }
        self.process = p
        onPID(p.processIdentifier)
    }

    /// Append one line to the disk log sink (newline-terminated). Always called on the
    /// serial `lineQueue`, so writes are ordered and race-free. Best-effort.
    private func teeToLog(_ line: String) {
        guard let h = logHandle, let data = (line + "\n").data(using: .utf8) else { return }
        try? h.write(contentsOf: data)
    }

    private func closeLog() {
        try? logHandle?.close()
        logHandle = nil
    }

    /// Split buffered stdout into complete lines, leaving any partial tail buffered.
    private func drainLines(_ emit: (String) -> Void) {
        let newline = UInt8(ascii: "\n")
        while let idx = stdoutBuffer.firstIndex(of: newline) {
            let lineData = stdoutBuffer.subdata(in: stdoutBuffer.startIndex..<idx)
            stdoutBuffer.removeSubrange(stdoutBuffer.startIndex...idx)
            if let line = String(data: lineData, encoding: .utf8) {
                emit(line)
            }
        }
    }

    func cancel() {
        process?.terminate()
    }

    var isRunning: Bool { process?.isRunning ?? false }
}
