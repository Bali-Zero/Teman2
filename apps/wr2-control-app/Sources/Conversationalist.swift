import Foundation

/// Which model the operator is brainstorming with.
enum ChatModel: String, CaseIterable {
    case claude, codex
    var label: String { self == .claude ? "Claude" : "Codex" }
    var icon: String { self == .claude ? "sparkles" : "chevron.left.forwardslash.chevron.right" }
}

/// One message in the brainstorming thread.
struct ChatMessage: Identifiable, Equatable {
    let id = UUID()
    enum Role: Equatable { case user, assistant, system }
    let role: Role
    var text: String
    var pending: Bool = false   // assistant bubble still streaming
}

/// Runs a stateless chat turn against `claude` or `codex` (the same OAuth/CLI the rest of the
/// app uses — no SDK, no API key). Each turn sends the WHOLE thread as one prompt, so memory is
/// guaranteed without fragile session ids. The reply streams back; the closures fire on main.
final class Conversationalist {

    private var process: Process?
    private let q = DispatchQueue(label: "wr2.chat")
    private var buf = Data()

    static let baseSystemPrompt = """
    You are the Bali Zero WR2 carousel brainstorming partner. WR2 produces editorial-investigative \
    Instagram carousels (@balizero0) about Indonesian regulation, visa, tax, company, property — for \
    anglophone expats/founders. Voice: investigative-journalistic, authority + calculated alarm, \
    concrete numbers, bilingual technical terms never paraphrased. Help the operator SHAPE a carousel \
    idea: angle, hook, target segment, key facts to verify, slide arc, risks. Be concise and concrete. \
    When the idea is solid, end with a one-line 'TOPIC: <short topic for the pipeline>' the operator \
    can launch. Reply in the same language the operator writes in (Italian or Indonesian).
    """

    /// Immersive WR2 context: brand voice essentials (from constitution.md) + the list of past
    /// carousel topics (so the chat KNOWS what's already been made and won't repeat it).
    /// Loaded once and cached. This is what makes the chat "immersed in WR2", not generic.
    private static let immersiveContext: String = {
        var parts: [String] = []
        let home = FileManager.default.homeDirectoryForCurrentUser

        // 1) brand voice essentials — first ~6KB of the constitution (voice/rules live up top)
        let constitution = home.appendingPathComponent(".claude/skills/bali-zero-brand/constitution.md")
        if let text = try? String(contentsOf: constitution, encoding: .utf8) {
            parts.append("--- BALI ZERO BRAND CONSTITUTION (excerpt) ---\n" + String(text.prefix(6000)))
        }

        // 2) past carousel topics — so it doesn't re-propose what's done
        let carouselRoot = home.appendingPathComponent("Desktop/nuzantara/apps/war-room/output/carousel")
        var topics: [String] = []
        if let dirs = try? FileManager.default.contentsOfDirectory(at: carouselRoot,
                          includingPropertiesForKeys: nil, options: [.skipsHiddenFiles]) {
            for d in dirs {
                let brief = d.appendingPathComponent("brief.json")
                if let data = try? Data(contentsOf: brief),
                   let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let topic = obj["topic"] as? String {
                    topics.append(topic)
                }
            }
        }
        if topics.isEmpty == false {
            parts.append("--- CAROUSELS ALREADY PRODUCED (don't repeat these angles unless asked) ---\n"
                         + topics.map { "• \($0)" }.joined(separator: "\n"))
        }
        return parts.joined(separator: "\n\n")
    }()

    static var systemPrompt: String {
        let ctx = immersiveContext
        return ctx.isEmpty ? baseSystemPrompt : baseSystemPrompt + "\n\n" + ctx
    }

    var isRunning: Bool { process?.isRunning ?? false }

    func cancel() { process?.terminate() }

    /// Send a turn. `history` is the full prior thread (excluding the new user line, which is `user`).
    func send(model: ChatModel,
              history: [ChatMessage],
              user: String,
              onDelta: @escaping (String) -> Void,
              onDone: @escaping (Bool) -> Void) {

        let prompt = Self.composePrompt(history: history, user: user)
        switch model {
        case .claude: runClaude(prompt: prompt, onDelta: onDelta, onDone: onDone)
        case .codex:  runCodex(prompt: prompt, onDelta: onDelta, onDone: onDone)
        }
    }

    // Build a single self-contained prompt from the thread.
    private static func composePrompt(history: [ChatMessage], user: String) -> String {
        var lines = [systemPrompt, "", "--- conversation so far ---"]
        for m in history where m.role != .system {
            let who = m.role == .user ? "OPERATOR" : "YOU"
            lines.append("\(who): \(m.text)")
        }
        lines.append("OPERATOR: \(user)")
        lines.append("YOU:")
        return lines.joined(separator: "\n")
    }

    // MARK: - Claude (plain chat, no agent, stream-json for clean text extraction)

    private func runClaude(prompt: String,
                           onDelta: @escaping (String) -> Void,
                           onDone: @escaping (Bool) -> Void) {
        guard let claude = ClaudeRunner.resolveClaudePath() else {
            DispatchQueue.main.async { onDelta("⚠︎ " + "claude non trovato"); onDone(false) }; return
        }
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/zsh")
        let safe = prompt.replacingOccurrences(of: "'", with: "'\\''")
        p.arguments = ["-lc", "exec '\(claude)' -p '\(safe)' --model '\(ClaudeRunner.headlessModel())' --output-format stream-json --verbose --permission-mode bypassPermissions"]
        p.currentDirectoryURL = ClaudeRunner.workingDirectory()
        var env = ProcessInfo.processInfo.environment
        env.removeValue(forKey: "ANTHROPIC_API_KEY"); env["CI"] = "1"
        p.environment = env
        runStreaming(p, parseLine: { line in
            // pull assistant text + final result from stream-json
            if case .assistantText(let t)? = StreamEvent.parse(line: line) { return t }
            if case .result(let t, _, _, _)? = StreamEvent.parse(line: line) { return t }
            return nil
        }, onDelta: onDelta, onDone: onDone)
    }

    // MARK: - Codex (plain exec, last-message is the reply)

    private func runCodex(prompt: String,
                          onDelta: @escaping (String) -> Void,
                          onDone: @escaping (Bool) -> Void) {
        // resolve codex path
        let codex = ["/opt/homebrew/bin/codex", "/usr/local/bin/codex",
                     "\(NSHomeDirectory())/.local/bin/codex"]
            .first { FileManager.default.isExecutableFile(atPath: $0) } ?? "codex"
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/zsh")
        let safe = prompt.replacingOccurrences(of: "'", with: "'\\''")
        p.arguments = ["-lc", "exec '\(codex)' exec --sandbox read-only --skip-git-repo-check '\(safe)'"]
        p.currentDirectoryURL = ClaudeRunner.workingDirectory()
        var env = ProcessInfo.processInfo.environment
        env["CI"] = "1"
        p.environment = env
        // codex exec prints prose; emit raw lines (skip its banner noise)
        runStreaming(p, parseLine: { line in
            let l = line.trimmingCharacters(in: .whitespaces)
            if l.isEmpty { return nil }
            // skip codex banners / warnings
            let noise = ["OpenAI Codex", "workdir:", "model:", "provider:", "approval:",
                         "sandbox:", "reasoning", "session id:", "--------", "warning:", "user", "codex",
                         "tokens used", "Reading additional"]
            if noise.contains(where: { l.hasPrefix($0) }) { return nil }
            return line
        }, onDelta: onDelta, onDone: onDone)
    }

    // MARK: - shared streaming

    private func runStreaming(_ p: Process,
                              parseLine: @escaping (String) -> String?,
                              onDelta: @escaping (String) -> Void,
                              onDone: @escaping (Bool) -> Void) {
        let out = Pipe(); let err = Pipe()
        p.standardOutput = out; p.standardError = err
        buf = Data()
        out.fileHandleForReading.readabilityHandler = { [weak self] h in
            let chunk = h.availableData
            guard chunk.isEmpty == false else { return }
            self?.q.async {
                self?.buf.append(chunk)
                while let nl = self?.buf.firstIndex(of: 0x0A) {
                    guard let self else { return }
                    let lineData = self.buf.subdata(in: self.buf.startIndex..<nl)
                    self.buf.removeSubrange(self.buf.startIndex...nl)
                    if let line = String(data: lineData, encoding: .utf8),
                       let txt = parseLine(line) {
                        DispatchQueue.main.async { onDelta(txt) }
                    }
                }
            }
        }
        p.terminationHandler = { [weak self] proc in
            out.fileHandleForReading.readabilityHandler = nil
            // flush tail
            let tail = out.fileHandleForReading.readDataToEndOfFile()
            self?.q.async {
                if tail.isEmpty == false { self?.buf.append(tail) }
                if let self, self.buf.isEmpty == false,
                   let line = String(data: self.buf, encoding: .utf8), let txt = parseLine(line) {
                    DispatchQueue.main.async { onDelta(txt) }
                }
                DispatchQueue.main.async { onDone(proc.terminationStatus == 0) }
            }
        }
        do { try p.run(); self.process = p }
        catch { DispatchQueue.main.async { onDelta("⚠︎ \(error.localizedDescription)"); onDone(false) } }
    }
}
