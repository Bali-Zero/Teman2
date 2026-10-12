import Foundation

/// Talks to the single Zantara-KBLI brain (OpenClaw, GPT-5.5) on the Mini.
/// Dual-mode: runs `openclaw` locally when ON the Mini, via `ssh mini` from M5/Pro.
/// NOT a clone of `codex exec` (which is agentic and unusable as chat — spec §9 F1):
/// OpenClaw's `agent --json` returns clean assistant text.
final class OpenClawRunner {

    enum RunnerError: Error, LocalizedError {
        case launchFailed(String), unreachable, emptyReply
        var errorDescription: String? {
            switch self {
            case .launchFailed(let m): return "Impossibile avviare OpenClaw: \(m)"
            case .unreachable: return "OpenClaw sul Mini non raggiungibile."
            case .emptyReply: return "Nessuna risposta da Zantara."
            }
        }
    }

    static let openclawPath = "~/.openclaw/bin/openclaw"   // NOT in PATH on Mini → absolute
    static let agentName = "zantara-kbli"

    /// Build the zsh command argv. On the Mini we invoke openclaw directly; elsewhere via ssh.
    /// The agent's JSON is emitted on stderr after banners, so we redirect 2>&1 and parse the
    /// first JSON object out of the combined stream (verified live 2026-06-23).
    /// Hard wall-clock cap so a stuck model-fallback cascade (e.g. GPT-5.5 auth expired) can never
    /// hang the chat forever — enforced in Swift (DispatchWorkItem + p.terminate), NOT via gtimeout
    /// (absent on macOS by default — DeepSeek review minor #5).
    static let timeoutSeconds = 120.0

    /// Build the executable + argv directly — NO shell, so a chat message can never break out of
    /// quoting and inject commands (DeepSeek review FATAL: shell injection). Each argument is a
    /// separate array element; the OS passes them verbatim, no interpretation.
    static func commandArgs(host: String, message: String, agent: String = agentName) -> [String] {
        if host.lowercased().contains("mini") {
            // LOCAL (on the Mini): exec openclaw directly → expand ~ against THIS machine's HOME.
            let openclaw = (openclawPath as NSString).expandingTildeInPath
            return [openclaw, "agent", "--agent", agent, "--local", "--json", "--message", message]
        }
        // REMOTE (ssh mini from M5/Pro): the binary lives under the MINI user's HOME (nuzantara),
        // NOT this machine's (e.g. /Users/balizero/ on M5). Do NOT locally-expand ~ — leave the
        // literal `~/.openclaw/bin/openclaw` so the REMOTE shell expands it. Local tilde-expansion
        // here leaks the wrong absolute path onto the wire → ssh runs a non-existent path → exit 127
        // → "OpenClaw unreachable" even though the brain is healthy (HOME-fork drift, cicatrix #1).
        let inner = [openclawPath, "agent", "--agent", agent, "--local", "--json", "--message", message]
        return ["ssh", "-o", "ConnectTimeout=8", "mini"] + inner
    }

    /// Current host short name (e.g. "Air-M5", "Mini-Pro2").
    static func currentHost() -> String {
        ProcessInfo.processInfo.hostName
            .replacingOccurrences(of: ".local", with: "")
    }

    /// Extract the assistant reply from OpenClaw's mixed (banner + JSON) output.
    /// Handles THREE shapes (OpenClaw's schema drifted 2026-06; verified live on Mini):
    ///   1. CURRENT: `{ payloads: [{ text }], meta: {…} }`  ← gpt-5.5 / openai-codex agent shape
    ///   2. legacy embedded: `result.output[].text`
    ///   3. legacy gateway:  `result.finalAssistantVisibleText`
    /// Returns "" on any parse failure (never throws). The banner lines before the JSON are skipped
    /// by seeking the first `{`.
    static func parseReply(_ raw: String) -> String {
        guard let jsonStart = raw.firstIndex(of: "{") else { return "" }
        let slice = String(raw[jsonStart...])
        guard let data = slice.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return "" }

        // 1) CURRENT shape: payloads[].text (last non-empty).
        if let payloads = obj["payloads"] as? [[String: Any]] {
            let texts = payloads.compactMap { p -> String? in
                let t = (p["text"] as? String) ?? (p["content"] as? String)
                return (t?.isEmpty == false) ? t : nil
            }
            if let last = texts.last { return last }
        }

        // 2) / 3) legacy `result.*` shapes.
        if let result = obj["result"] as? [String: Any] {
            if let v = result["finalAssistantVisibleText"] as? String, v.isEmpty == false { return v }
            if let v = result["finalAssistantRawText"] as? String, v.isEmpty == false { return v }
            if let output = result["output"] as? [[String: Any]] {
                let texts = output.compactMap { entry -> String? in
                    guard let t = entry["text"] as? String, t.isEmpty == false else { return nil }
                    let type = (entry["type"] as? String) ?? "message"
                    return type == "reasoning" ? nil : t
                }
                if let last = texts.last { return last }
            }
        }
        return ""
    }

    /// Single-quote a string for a POSIX remote shell (ssh reassembles argv into one command line
    /// on the remote, so the inner args must be safely quoted for THAT shell). `'` → `'\''`.
    /// A LEADING `~/` is emitted UNQUOTED so the REMOTE shell tilde-expands it to the remote user's
    /// HOME (single-quoting `~` would make it a literal char → path-not-found). Only the leading
    /// `~/` is special-cased; the remainder is fully quoted, so injection safety is preserved.
    private static func shQuote(_ s: String) -> String {
        let q = { (x: String) -> String in "'" + x.replacingOccurrences(of: "'", with: "'\\''") + "'" }
        if s.hasPrefix("~/") {
            return "~/" + q(String(s.dropFirst(2)))
        }
        return q(s)
    }

    /// Test-only forwarder so the standalone runnertest can assert shQuote behavior
    /// without making the private method public. NOT used by the app.
    static func shQuoteForTest(_ s: String) -> String { shQuote(s) }

    /// Run one turn. NO shell on the local side (argv passed verbatim → no injection). For the
    /// remote ssh path, the openclaw args are POSIX-quoted into one remote command. A Swift
    /// wall-clock timeout terminates a stuck process. Callbacks fire on the main queue.
    func ask(message: String, completion: @escaping (Result<String, Error>) -> Void) {
        let host = Self.currentHost()
        let args = Self.commandArgs(host: host, message: message)
        DispatchQueue.global(qos: .userInitiated).async {
            let p = Process()
            if host.lowercased().contains("mini") {
                // local: exec openclaw directly, argv verbatim (no shell)
                p.executableURL = URL(fileURLWithPath: args[0])
                p.arguments = Array(args.dropFirst())
            } else {
                // remote: ssh <opts> mini '<quoted openclaw cmd>' — quote inner args for remote shell
                let sshIdx = 4   // ["ssh","-o","ConnectTimeout=8","mini", <inner…>]
                let sshOpts = Array(args[0..<sshIdx])      // ssh -o ConnectTimeout=8 mini
                let inner = Array(args[sshIdx...])
                let remoteCmd = inner.map(Self.shQuote).joined(separator: " ")
                p.executableURL = URL(fileURLWithPath: "/usr/bin/ssh")
                p.arguments = Array(sshOpts.dropFirst()) + [remoteCmd]
            }
            var env = ProcessInfo.processInfo.environment
            env.removeValue(forKey: "ANTHROPIC_API_KEY")   // defense-in-depth
            p.environment = env
            let pipe = Pipe()
            p.standardOutput = pipe
            p.standardError = pipe   // JSON is on stderr; merge

            // Swift wall-clock timeout (no gtimeout dependency).
            var timedOut = false
            let killer = DispatchWorkItem { if p.isRunning { timedOut = true; p.terminate() } }
            DispatchQueue.global().asyncAfter(deadline: .now() + Self.timeoutSeconds, execute: killer)

            do { try p.run() }
            catch {
                killer.cancel()
                DispatchQueue.main.async { completion(.failure(RunnerError.launchFailed(error.localizedDescription))) }
                return
            }
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            p.waitUntilExit()
            killer.cancel()
            let reply = Self.parseReply(String(data: data, encoding: .utf8) ?? "")
            DispatchQueue.main.async {
                if reply.isEmpty {
                    completion(.failure(timedOut || p.terminationStatus != 0 ? RunnerError.unreachable : RunnerError.emptyReply))
                } else {
                    completion(.success(reply))
                }
            }
        }
    }
}
