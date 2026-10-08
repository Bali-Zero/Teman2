import Foundation
import Darwin

// KBLICodexRunner.swift — talks to ChatGPT Pro via headless `codex exec` (design §2). Replaces
// OpenClawRunner in the chat flow. Every invariant in the design's §2 table is implemented here;
// where this machine's real filesystem diverges from the design's Pro-only measurements, the
// divergence is called out inline (and in the implementation report) rather than silently papered
// over — see `KBLICodexAvailability.minimalPATH` and `.configuredPath`.

enum KBLICodexRunnerError: Error, LocalizedError, Equatable {
    case unavailable(String)
    case timeout
    case oversized
    case authDeath
    case quotaThrottle
    case processError(String)
    case cancelled

    var errorDescription: String? {
        switch self {
        case .unavailable(let m): return "Chat seat unavailable: \(m)"
        case .timeout: return "The assistant did not respond in time."
        case .oversized: return "The assistant's response was too large to verify."
        case .authDeath: return "The assistant seat needs re-authentication on this Mac."
        case .quotaThrottle: return "The assistant seat is temporarily rate-limited — try again shortly."
        case .processError(let m): return "The assistant could not answer (\(m))."
        case .cancelled: return "Cancelled."
        }
    }
}

// MARK: - Availability / identity (design §2 "availability probe" row)

struct KBLICodexBinaryIdentity: Equatable {
    let realPath: String
    let dev: Int32
    let ino: UInt64
    let mtime: Int64
    let size: Int64
}

enum KBLICodexAvailability {
    /// Pinned manifest version — the ONLY version this runner will spawn (fail-closed on drift,
    /// never a `≥` floor, never a range — ruled 2026-09-11). Measured live 2026-09-13 on M5 at the
    /// ABSOLUTE path this runner resolves: `codex-cli 0.147.0`. The previous pin (0.148.0, taken
    /// 2026-08-20 from a Pro host that had auto-updated) matched NO binary on the fleet, so every
    /// spawn was refused before it started and the whole §8 suite would have scored 0 answers on
    /// transport alone. The fleet is M5 alone (gate 0.1) and the pin now tracks a runtime the app
    /// OWNS. Update only together with `dedicatedRuntimePath` and a re-run §8 manifest.
    /// It is the version the DEFAULT runtime carries; what the runner accepts is `allowedVersions`.
    static let pinnedVersion = "codex-cli 0.147.0"

    /// The EXPLICIT allow-list: every `--version` line this runner will spawn, each one exact.
    /// Never a `>=` floor and never a min-max range (ruled 2026-09-11: testing the two ends of a
    /// range does not prove the middle keeps the invariants). An entry is admitted only when a
    /// binary answering it was MEASURED on the fleet with `"$KBLI_CODEX_BIN" --version` at an
    /// absolute path — never `codex --version` by name, which on M5 reads a shadowing install —
    /// and every entry has its own test in `Tests/codexrunnertest`, which also pins this literal.
    /// Measured 2026-09-14 on M5 (the fleet, gate 0.1): the app-owned runtime and the Homebrew
    /// copy both answer `codex-cli 0.147.0`. No binary answering `codex-cli 0.148.0` exists on
    /// disk, so the old 0.148.0 pin is NOT re-admitted: an entry no binary answers is the exact
    /// defect that refused 87 of 87 spawns on 2026-08-20. Adding a version is a code change here,
    /// a new test for it, and a re-run §8 manifest — never an edit of the runtime behind a path.
    static let allowedVersions: [String] = ["codex-cli 0.147.0"]

    /// Exact membership of one `--version` line. Only surrounding whitespace is trimmed: a suffix
    /// (`-alpha.1`), a shorter form (`0.147`) or any other version is refused (fail-closed).
    static func isAllowedVersion(_ versionLine: String) -> Bool {
        allowedVersions.contains(versionLine.trimmingCharacters(in: .whitespacesAndNewlines))
    }

    /// The app-owned, version-pinned runtime — a frozen copy of the codex CLI installed outside
    /// any package manager's reach. `/opt/homebrew/bin/codex` is a Homebrew-managed symlink: a
    /// `brew upgrade` run by anything else on this machine moves it under the app and turns the
    /// chat off the day after a green benchmark (the exact drift that produced the 0.148.0 pin).
    /// The version is IN the directory name, so bumping the runtime is necessarily a code change
    /// next to `pinnedVersion` — never a silent swap behind a stable alias.
    static let dedicatedRuntimePath =
        NSHomeDirectory() + "/.local/share/kbli-navigator/runtime/codex-cli-0.147.0/bin/codex.js"

    /// The binary path this runner resolves and spawns. Deliberately NOT a bare PATH lookup of
    /// "codex" (design §2: "never a PATH lookup") — measured landmine on M5, 2026-08-19: `which
    /// codex` resolves to `~/.local/bin/codex`, an INTERACTIVE MENU wrapper script (a real file,
    /// not a symlink — `resolvingSymlinksInPath()` cannot see through it) that only forwards to
    /// the real binary once it detects non-tty stdin/stdout or a non-empty argv. A PATH-based
    /// spawn would verify the identity of one file and then execute a different one the moment
    /// mise/homebrew rearranges what shadows what — measured again 2026-09-13: `which -a codex`
    /// on M5 lists five entries, and the first is a shell function.
    /// Since 2026-09-13 the default is `dedicatedRuntimePath`, not the Homebrew symlink: the
    /// runner spawns the copy the app owns, at a path whose name carries the pinned version.
    /// Override for local dev/test via `KBLI_CODEX_BIN`.
    static var configuredPath: String {
        ProcessInfo.processInfo.environment["KBLI_CODEX_BIN"] ?? dedicatedRuntimePath
    }

    /// Minimal child PATH — always includes `/opt/homebrew/bin` per the design (codex is a Node
    /// shebang script). ADDITIONALLY includes the mise shims directory: measured landmine on M5,
    /// 2026-08-19 — `node` is NOT at `/opt/homebrew/bin/node` there (mise-managed,
    /// `~/.local/share/mise/shims/node`); with PATH limited to the design's literal prescription
    /// alone, `/opt/homebrew/bin/codex --version` fails `env: node: No such file or directory`
    /// even though the codex file itself resolves and stats cleanly. On Pro `node` IS at
    /// `/opt/homebrew/bin/node` (verified live), so this second directory is a harmless no-op
    /// there. Still an explicit, controlled, minimal list — never the ambient inherited PATH.
    static var minimalPATH: String {
        "/opt/homebrew/bin:\(NSHomeDirectory())/.local/share/mise/shims"
    }

    /// `path` overrides `configuredPath` — used by tests to exercise symlink-chain resolution
    /// and identity capture against a disposable fixture without depending on env-var visibility
    /// timing or a real codex install.
    static func resolveIdentity(path: String? = nil) -> KBLICodexBinaryIdentity? {
        let configured = path ?? configuredPath
        guard FileManager.default.fileExists(atPath: configured) else { return nil }
        let real = URL(fileURLWithPath: configured).resolvingSymlinksInPath().path
        guard let st = statPath(real) else { return nil }
        return KBLICodexBinaryIdentity(realPath: real, dev: st.dev, ino: st.ino, mtime: st.mtime, size: st.size)
    }

    private static func statPath(_ path: String) -> (dev: Int32, ino: UInt64, mtime: Int64, size: Int64)? {
        var s = stat()
        guard lstat(path, &s) == 0 else { return nil }
        return (dev: s.st_dev, ino: UInt64(s.st_ino), mtime: Int64(s.st_mtimespec.tv_sec), size: Int64(s.st_size))
    }

    static func authFilePresent(codexHome: String? = nil) -> Bool {
        let home = codexHome ?? ProcessInfo.processInfo.environment["CODEX_HOME"] ?? (NSHomeDirectory() + "/.codex")
        let path = home + "/auth.json"
        guard let attrs = try? FileManager.default.attributesOfItem(atPath: path),
              let size = attrs[.size] as? Int else { return false }
        return size > 0
    }

    /// Cheap PRE-FILTER only (design §2): runs `<realPath> --version` and checks it against the
    /// exact allow-list (`allowedVersions`).
    /// The AUTHORITATIVE signal is always the first real call's typed failure.
    static func versionMatches(_ identity: KBLICodexBinaryIdentity) -> Bool {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: identity.realPath)
        p.arguments = ["--version"]
        p.environment = ["PATH": minimalPATH, "HOME": NSHomeDirectory()]
        let out = Pipe()
        p.standardOutput = out
        p.standardError = FileHandle.nullDevice
        do { try p.run() } catch { return false }
        let data = out.fileHandleForReading.readDataToEndOfFile()
        p.waitUntilExit()
        try? out.fileHandleForReading.close()
        try? out.fileHandleForWriting.close()
        guard p.terminationStatus == 0 else { return false }
        let text = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return isAllowedVersion(text)
    }
}

// MARK: - Durable intent sidecar + launch sweep (design §2, R5-2/R6-2/R7-1)

enum KBLIRunnerLaunchGuard {
    static let intentDir: URL = {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("kbli-codex-intents", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }()

    struct Intent: Codable {
        let id: String
        let tempDir: String
        var pgid: Int32?
        var leaderPid: Int32?
        var leaderStartTime: Double?
    }

    /// Written BEFORE `posix_spawn`/`Process.run()`. If the app crashes between here and
    /// `complete`, the next launch's sweep still knows "a spawn may have happened" and can hunt
    /// by tempDir alone (design §2, R7-1 — the crash-injection matrix this exists for).
    static func begin(tempDir: URL) -> URL {
        let id = UUID().uuidString
        let intent = Intent(id: id, tempDir: tempDir.path, pgid: nil, leaderPid: nil, leaderStartTime: nil)
        let path = intentDir.appendingPathComponent(id + ".json")
        write(intent, to: path)
        return path
    }

    static func complete(_ path: URL, pgid: Int32, leaderPid: Int32, leaderStartTime: Double) {
        guard var intent = read(path) else { return }
        intent.pgid = pgid
        intent.leaderPid = leaderPid
        intent.leaderStartTime = leaderStartTime
        write(intent, to: path)
    }

    static func remove(_ path: URL) { try? FileManager.default.removeItem(at: path) }

    /// Run once per app launch. A leftover intent is either an INCOMPLETE spawn (no pgid yet —
    /// hunt by tempDir across every live process) or a COMPLETED one (hunt the recorded pgid,
    /// but kill only if at least one member's cwd is inside the recorded tempDir — the durable-
    /// identity check design §2/R6-2 requires: a bare pgid kill would spare a LEADERLESS orphan
    /// group and could murder an unrelated codex process that reused the same pgid).
    static func sweep() {
        guard let files = try? FileManager.default.contentsOfDirectory(at: intentDir, includingPropertiesForKeys: nil) else { return }
        for f in files where f.pathExtension == "json" {
            guard let intent = read(f) else { try? FileManager.default.removeItem(at: f); continue }
            if let pgid = intent.pgid {
                killGroupIfCwdMatches(pgid: pgid, tempDir: intent.tempDir)
            } else {
                killByTempDirScan(tempDir: intent.tempDir)
            }
            try? FileManager.default.removeItem(at: f)
        }
    }

    private static func write(_ intent: Intent, to path: URL) {
        guard let data = try? JSONEncoder().encode(intent) else { return }
        try? data.write(to: path, options: .atomic)
    }
    private static func read(_ path: URL) -> Intent? {
        guard let data = try? Data(contentsOf: path) else { return nil }
        return try? JSONDecoder().decode(Intent.self, from: data)
    }

    static func killGroupIfCwdMatches(pgid: Int32, tempDir: String) {
        guard let pids = psPidsForGroup(pgid), pids.contains(where: { pidHasCwd($0, under: tempDir) }) else { return }
        killpg(pgid, SIGKILL)
    }

    /// No pgid recorded (crash landed in the spawn→complete window): the tempDir is the only
    /// durable clue. Bounded cost — this scan runs once per app launch, not per call.
    static func killByTempDirScan(tempDir: String) {
        guard let pids = allPids() else { return }
        for pid in pids where pidHasCwd(pid, under: tempDir) { kill(pid, SIGKILL) }
    }

    static func psPidsForGroup(_ pgid: Int32) -> [Int32]? {
        guard let out = runCapture("/bin/ps", ["-Ao", "pid,pgid"]) else { return nil }
        var pids: [Int32] = []
        for line in out.split(separator: "\n").dropFirst() {
            let parts = line.split(separator: " ", omittingEmptySubsequences: true)
            guard parts.count >= 2, let p = Int32(parts[0]), let g = Int32(parts[1]), g == pgid else { continue }
            pids.append(p)
        }
        return pids
    }

    private static func allPids() -> [Int32]? {
        guard let out = runCapture("/bin/ps", ["-Ao", "pid"]) else { return nil }
        return out.split(separator: "\n").dropFirst().compactMap { Int32($0.trimmingCharacters(in: .whitespaces)) }
    }

    /// Canonicalizes a path via `realpath(3)` — resolves macOS firmlinks (`/var` ->
    /// `/private/var`, `/tmp` -> `/private/tmp`) the same way the kernel does. `lsof`'s reported
    /// cwd is ALWAYS the kernel-canonical form; a raw `FileManager.temporaryDirectory`-derived
    /// path keeps the `/var/...` firmlink form, so comparing the two directly silently NEVER
    /// matches (measured bug: the pgid matched but the cwd check always failed because
    /// `/var/folders/...` != `/private/var/folders/...`). Falls back to the raw path if
    /// `realpath` fails (e.g. the directory was already cleaned up) rather than crashing.
    private static func canonicalPath(_ path: String) -> String {
        var buf = [Int8](repeating: 0, count: Int(PATH_MAX))
        guard let r = realpath(path, &buf) else { return path }
        return String(cString: r)
    }

    /// cwd of a target pid, via `lsof -a -p <pid> -d cwd -Fn` (widely available on macOS by
    /// default — avoids needing a libproc/bridging-header C shim this build's plain-swiftc
    /// pipeline has no infrastructure for). `-Fn` emits a `pNNN` line then an `n<path>` line.
    static func pidHasCwd(_ pid: Int32, under tempDir: String) -> Bool {
        guard let out = runCapture("/usr/sbin/lsof", ["-a", "-p", "\(pid)", "-d", "cwd", "-Fn"]) else { return false }
        let canonicalTempDir = canonicalPath(tempDir)
        for line in out.split(separator: "\n") where line.hasPrefix("n") {
            let path = String(line.dropFirst())
            if path == canonicalTempDir || path.hasPrefix(canonicalTempDir + "/") { return true }
        }
        return false
    }

    private static func runCapture(_ launchPath: String, _ args: [String]) -> String? {
        guard FileManager.default.isExecutableFile(atPath: launchPath) else { return nil }
        let p = Process()
        p.executableURL = URL(fileURLWithPath: launchPath)
        p.arguments = args
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = FileHandle.nullDevice
        do { try p.run() } catch { return nil }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        p.waitUntilExit()
        try? pipe.fileHandleForReading.close()
        try? pipe.fileHandleForWriting.close()
        guard p.terminationStatus == 0 || p.terminationStatus == 1 else { return nil }  // lsof exits 1 on "no match", still valid empty output
        return String(data: data, encoding: .utf8)
    }
}

// MARK: - Output draining (design §2: concurrent, capped, never truncated-and-served)

final class KBLIOutputCollector {
    let capBytes: Int
    private(set) var stdoutData = Data()
    private(set) var stderrData = Data()
    private(set) var oversized = false
    var onOversized: (() -> Void)?
    private let lock = NSLock()
    private var stdoutHandle: FileHandle?
    private var stderrHandle: FileHandle?

    init(capBytes: Int) { self.capBytes = capBytes }

    func attach(stdout: Pipe, stderr: Pipe) {
        stdoutHandle = stdout.fileHandleForReading
        stderrHandle = stderr.fileHandleForReading
        stdoutHandle?.readabilityHandler = { [weak self] h in self?.drainStdout(h) }
        stderrHandle?.readabilityHandler = { [weak self] h in self?.drainStderr(h) }
    }

    private func drainStdout(_ handle: FileHandle) {
        let chunk = handle.availableData
        guard chunk.isEmpty == false else { return }
        lock.lock()
        stdoutData.append(chunk)
        let over = stdoutData.count > capBytes
        lock.unlock()
        if over { markOversized() }
    }

    private func drainStderr(_ handle: FileHandle) {
        let chunk = handle.availableData
        guard chunk.isEmpty == false else { return }
        lock.lock()
        stderrData.append(chunk)
        let over = stderrData.count > capBytes
        lock.unlock()
        if over { markOversized() }
    }

    private func markOversized() {
        lock.lock()
        let already = oversized
        oversized = true
        lock.unlock()
        if already == false { onOversized?() }
    }

    func finish() {
        stdoutHandle?.readabilityHandler = nil
        stderrHandle?.readabilityHandler = nil
    }
}

// MARK: - The runner

final class KBLICodexRunner {
    static let model = "gpt-5.6-terra"
    static let timeoutSeconds: TimeInterval = 60
    static let outputCapBytes = 256 * 1024

    // single-flight (design §2 "broker daemon rule", ported to a single-process desktop app)
    private static let flightLock = NSLock()
    private static var inFlight = false
    private static var activePgid: Int32?

    private static func acquireSlot() -> Bool {
        flightLock.lock(); defer { flightLock.unlock() }
        if inFlight { return false }
        inFlight = true
        return true
    }
    private static func releaseSlot() {
        flightLock.lock(); inFlight = false; flightLock.unlock()
    }
    private static func setActivePgid(_ pgid: Int32?) {
        flightLock.lock(); activePgid = pgid; flightLock.unlock()
    }

    /// Called from the app-exit handler (design §2: group-kill "on ... applicationWillTerminate").
    /// Best-effort, synchronous, safe to call even with nothing in flight.
    static func terminateActiveCallForAppExit() {
        flightLock.lock(); let pgid = activePgid; flightLock.unlock()
        if let pgid { killpg(pgid, SIGKILL) }
    }

    /// Fixed argv (design §2): `codex exec --sandbox read-only --skip-git-repo-check --ephemeral
    /// --ignore-user-config --ignore-rules -m <model> -`. Pure and side-effect-free so P2a can
    /// assert the exact shape without spawning anything — the prompt is deliberately NOT a
    /// parameter here: it is written to stdin, never argv (ps-readable).
    static func buildArgv() -> [String] {
        ["exec", "--sandbox", "read-only", "--skip-git-repo-check", "--ephemeral",
         "--ignore-user-config", "--ignore-rules", "-m", model, "-"]
    }

    /// Minimal child env (design §2): explicit `PATH` (+ the M5 mise-shims addition, see
    /// `KBLICodexAvailability.minimalPATH`), `HOME`, optional `CODEX_HOME` — nothing else
    /// inherited from the app's own environment.
    static func buildEnv(codexHome: String? = ProcessInfo.processInfo.environment["CODEX_HOME"]) -> [String: String] {
        var env: [String: String] = [
            "PATH": KBLICodexAvailability.minimalPATH,
            "HOME": NSHomeDirectory(),
        ]
        if let codexHome { env["CODEX_HOME"] = codexHome }
        return env
    }

    private static let throttlePatterns: [String] = [
        "rate limit", "rate_limit", "quota exceeded", "usage limit", "429", "too many requests",
    ]
    private static let authDeathPatterns: [String] = [
        "not logged in", "not authenticated", "please run.*login", "auth.*expired", "401",
        "token.*revoked", "no credentials found",
    ]

    /// Run one turn. `async` so cancellation composes with Swift structured concurrency: a
    /// `Task` cancelled while this call is in flight (view disappears, user starts a new chat)
    /// tears down the WHOLE process group via `onCancel`, not just the direct child.
    func run(prompt: String) async throws -> String {
        guard KBLICodexRunner.acquireSlot() else {
            throw KBLICodexRunnerError.processError("a chat call is already in flight")
        }
        var spawnedPgid: Int32?
        defer {
            KBLICodexRunner.releaseSlot()
            if let p = spawnedPgid { KBLICodexRunner.setActivePgid(nil); _ = p }
        }

        guard let identity = KBLICodexAvailability.resolveIdentity() else {
            throw KBLICodexRunnerError.unavailable("codex CLI not found at the configured path")
        }
        guard KBLICodexAvailability.versionMatches(identity) else {
            throw KBLICodexRunnerError.unavailable(
                "codex CLI version is not on the benchmarked allow-list (\(KBLICodexAvailability.allowedVersions.joined(separator: ", "))) — restore an allowed version or re-run the new-brain benchmark suite")
        }
        guard KBLICodexAvailability.authFilePresent() else {
            throw KBLICodexRunnerError.unavailable("no codex seat is logged in on this Mac")
        }

        let tempDir = FileManager.default.temporaryDirectory
            .appendingPathComponent("kbli-codex-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        let intentPath = KBLIRunnerLaunchGuard.begin(tempDir: tempDir)
        defer {
            KBLIRunnerLaunchGuard.remove(intentPath)
            try? FileManager.default.removeItem(at: tempDir)
        }

        // Re-stat the SAME real path immediately before spawn — shrinks the probe→spawn TOCTOU
        // window to microseconds (design §2, R5-3/R6-3/R7-2).
        guard let reStat = KBLICodexAvailability.resolveIdentity(), reStat == identity else {
            throw KBLICodexRunnerError.unavailable("codex binary changed identity between check and spawn — refusing to execute an unverified file")
        }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: identity.realPath)
        process.arguments = KBLICodexRunner.buildArgv()
        process.currentDirectoryURL = tempDir
        process.environment = KBLICodexRunner.buildEnv()

        let stdinPipe = Pipe()
        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()
        process.standardInput = stdinPipe
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe

        let collector = KBLIOutputCollector(capBytes: KBLICodexRunner.outputCapBytes)
        collector.attach(stdout: stdoutPipe, stderr: stderrPipe)

        do {
            try process.run()
        } catch {
            throw KBLICodexRunnerError.processError("failed to launch: \(error.localizedDescription)")
        }
        let pid = process.processIdentifier
        // Own process group: best-effort setpgid immediately after spawn (the same race every
        // POSIX shell accepts for job control — the window is microseconds). Declared residual:
        // if the child forks a grandchild before this lands, that grandchild inherits whichever
        // pgid was current at ITS fork time; the durable-tempDir-cwd check in the launch sweep is
        // the backstop for exactly this case (design §2, R6-2 residual).
        setpgid(pid, pid)
        let pgid = pid
        spawnedPgid = pgid
        KBLICodexRunner.setActivePgid(pgid)
        KBLIRunnerLaunchGuard.complete(intentPath, pgid: pgid, leaderPid: pid, leaderStartTime: Date().timeIntervalSince1970)

        // stdin-only prompt — NEVER in argv (ps-readable).
        if let data = prompt.data(using: .utf8) {
            stdinPipe.fileHandleForWriting.write(data)
        }
        stdinPipe.fileHandleForWriting.closeFile()

        return try await withTaskCancellationHandler(operation: {
            try await KBLICodexRunner.awaitResult(process: process, collector: collector, pgid: pgid)
        }, onCancel: {
            killpg(pgid, SIGKILL)
        })
    }

    private static func awaitResult(process: Process, collector: KBLIOutputCollector, pgid: Int32) async throws -> String {
        try await withCheckedThrowingContinuation { (cont: CheckedContinuation<String, Error>) in
            let settleLock = NSLock()
            var settled = false
            func settle(_ result: Result<String, Error>) {
                settleLock.lock()
                let already = settled
                settled = true
                settleLock.unlock()
                guard already == false else { return }
                switch result {
                case .success(let s): cont.resume(returning: s)
                case .failure(let e): cont.resume(throwing: e)
                }
            }

            let timeoutWork = DispatchWorkItem {
                killpg(pgid, SIGKILL)
                settle(.failure(KBLICodexRunnerError.timeout))
            }
            DispatchQueue.global().asyncAfter(deadline: .now() + timeoutSeconds, execute: timeoutWork)

            collector.onOversized = {
                timeoutWork.cancel()
                killpg(pgid, SIGKILL)
                settle(.failure(KBLICodexRunnerError.oversized))
            }

            process.terminationHandler = { p in
                timeoutWork.cancel()
                collector.finish()
                if collector.oversized {
                    settle(.failure(KBLICodexRunnerError.oversized))
                    return
                }
                let stdoutStr = String(data: collector.stdoutData, encoding: .utf8) ?? ""
                let stderrStr = String(data: collector.stderrData, encoding: .utf8) ?? ""
                if p.terminationStatus != 0 {
                    settle(.failure(classify(stdoutStr: stdoutStr, stderrStr: stderrStr)))
                    return
                }
                settle(.success(stdoutStr))
            }
        }
    }

    /// Error taxonomy, checked IN ORDER (design §2): auth_death (stderr regex AFTER stripping
    /// any line that also appears verbatim in stdout — the echoed-prompt/echoed-answer guard, so
    /// a partial answer merely quoting "not logged in" can't fake an auth death) → quota_throttle
    /// (pinned recognized set only) → process_error (everything else, including flag/entitlement
    /// rejection — unknown is NEVER guessed as transient). Raw stderr is never shown or logged.
    static func classify(stdoutStr: String, stderrStr: String) -> KBLICodexRunnerError {
        let stdoutLines = Set(stdoutStr.split(separator: "\n").map(String.init))
        let strippedLines = stderrStr.split(separator: "\n").map(String.init)
            .filter { stdoutLines.contains($0) == false }
        let stripped = strippedLines.joined(separator: "\n")

        for pattern in authDeathPatterns {
            if stripped.range(of: pattern, options: [.regularExpression, .caseInsensitive]) != nil {
                return .authDeath
            }
        }
        for pattern in throttlePatterns {
            if stripped.range(of: pattern, options: [.regularExpression, .caseInsensitive]) != nil {
                return .quotaThrottle
            }
        }
        return .processError("exit status non-zero")
    }
}
