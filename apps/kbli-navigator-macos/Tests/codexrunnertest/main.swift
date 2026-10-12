import Foundation
import Darwin

func ck(_ c: Bool, _ m: String) { if c { print("  ✅ \(m)") } else { print("  ❌ FAIL: \(m)"); exit(1) } }

func isAlive(_ pid: pid_t) -> Bool { kill(pid, 0) == 0 }
func waitUntil(_ timeout: Double, _ cond: () -> Bool) -> Bool {
    let deadline = Date().addingTimeInterval(timeout)
    while Date() < deadline { if cond() { return true }; usleep(50_000) }
    return cond()
}

@discardableResult
func spawnSleeper(cwd: URL, seconds: Int = 30) -> pid_t {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/bin/sleep")
    p.arguments = ["\(seconds)"]
    p.currentDirectoryURL = cwd
    try! p.run()
    let pid = p.processIdentifier
    setpgid(pid, pid)
    return pid
}

func mkTempDir(_ name: String) -> URL {
    let dir = FileManager.default.temporaryDirectory.appendingPathComponent("kblitest-\(name)-\(UUID().uuidString)", isDirectory: true)
    try! FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
    return dir
}

// ─────────────────────────────────────────────────────────────────────────────────────────
print("argv shape (design §2 fixed prefix):")
let argv = KBLICodexRunner.buildArgv()
ck(argv == ["exec", "--sandbox", "read-only", "--skip-git-repo-check", "--ephemeral",
            "--ignore-user-config", "--ignore-rules", "-m", "gpt-5.6-terra", "-"],
   "argv is exactly the pinned prefix + model + stdin marker (got \(argv))")
ck(argv.last == "-", "argv ends with '-' (stdin marker)")
ck(argv.contains(where: { $0.count > 200 }) == false, "no argv element looks like an embedded prompt (ps-readable check)")

// ─────────────────────────────────────────────────────────────────────────────────────────
print("env minimality (design §2):")
let env = KBLICodexRunner.buildEnv(codexHome: nil)
ck(Set(env.keys) == ["PATH", "HOME"], "env carries ONLY PATH + HOME when CODEX_HOME is unset (got \(env.keys.sorted()))")
ck(env["PATH"]?.contains("/opt/homebrew/bin") == true, "PATH includes /opt/homebrew/bin (design §2 baseline)")
ck(env["PATH"]?.contains(".local/share/mise/shims") == true, "PATH includes the mise-shims addition (M5 landmine fix)")
let envWithHome = KBLICodexRunner.buildEnv(codexHome: "/tmp/fake-codex-home")
ck(envWithHome["CODEX_HOME"] == "/tmp/fake-codex-home", "CODEX_HOME passed through when present")
ck(Set(envWithHome.keys) == ["PATH", "HOME", "CODEX_HOME"], "env carries exactly PATH+HOME+CODEX_HOME when set, nothing else")

// ─────────────────────────────────────────────────────────────────────────────────────────
print("error taxonomy — classify() ordering and the echoed-prompt/stdout stripping guard:")
ck(KBLICodexRunner.classify(stdoutStr: "", stderrStr: "Error: not logged in. Please run codex login") == .authDeath,
   "'not logged in' -> authDeath")
ck(KBLICodexRunner.classify(stdoutStr: "", stderrStr: "token has been revoked, refresh_token_reused") == .authDeath,
   "'token...revoked' -> authDeath")
ck(KBLICodexRunner.classify(stdoutStr: "", stderrStr: "rate limit exceeded, try again later") == .quotaThrottle,
   "'rate limit' -> quotaThrottle")
ck(KBLICodexRunner.classify(stdoutStr: "", stderrStr: "429 Too Many Requests") == .quotaThrottle,
   "'429' -> quotaThrottle")
ck(KBLICodexRunner.classify(stdoutStr: "", stderrStr: "unknown flag --frobnicate") == .processError("exit status non-zero"),
   "unrecognized stderr -> processError, NEVER guessed as transient")
ck(KBLICodexRunner.classify(stdoutStr: "", stderrStr: "") == .processError("exit status non-zero"),
   "empty stderr on non-zero exit -> processError (never crashes on empty input)")

// the stripping guard: a partial ANSWER that merely echoes/quotes "not logged in" (because it
// was also printed to stdout, e.g. an echoed banner) must NOT be misread as a real auth death —
// only stderr content that is NOT ALSO present verbatim in stdout counts.
let echoedLine = "the user is not logged in to their bank account (a fictional example)"
ck(KBLICodexRunner.classify(stdoutStr: echoedLine, stderrStr: echoedLine) != .authDeath,
   "stderr line that ALSO appears verbatim in stdout is stripped before auth-death matching (echoed-prompt/stdout guard)")
ck(KBLICodexRunner.classify(stdoutStr: "some other output", stderrStr: "not logged in") == .authDeath,
   "a genuine auth-death line NOT echoed in stdout still classifies correctly")

// ─────────────────────────────────────────────────────────────────────────────────────────
print("availability probe — symlink-chain resolution + identity + re-stat drift (design §2):")
let fixtureDir = mkTempDir("identity")
let realFile = fixtureDir.appendingPathComponent("real_codex")
try! "original content A".write(to: realFile, atomically: true, encoding: .utf8)
try! FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: realFile.path)
let symlink = fixtureDir.appendingPathComponent("codex_link")
try! FileManager.default.createSymbolicLink(at: symlink, withDestinationURL: realFile)

let idA = KBLICodexAvailability.resolveIdentity(path: symlink.path)
ck(idA != nil, "resolveIdentity follows the symlink to the real file")
ck(idA?.realPath == realFile.path, "resolved realPath is the SYMLINK TARGET, not the symlink itself")
let idA2 = KBLICodexAvailability.resolveIdentity(path: symlink.path)
ck(idA == idA2, "re-resolving the SAME unmodified file yields an identical identity (stable re-stat)")

// mutate the real file (simulates a Homebrew upgrade landing between probe and spawn) — identity
// must change so a caller doing "re-stat immediately before spawn" can detect the drift.
usleep(1_100_000)  // mtime has 1s resolution on some filesystems; ensure a detectable change
try! "different content BBBBBB".write(to: realFile, atomically: true, encoding: .utf8)
let idB = KBLICodexAvailability.resolveIdentity(path: symlink.path)
ck(idA != idB, "identity changes after the real file's content/size/mtime changes (TOCTOU guard, R6-3)")

// symlink RETARGET (R7-2): point the same symlink PATH at a DIFFERENT real file — the resolved
// identity must reflect the NEW target, proving resolution always re-derives the real path fresh
// rather than caching path A's identity across a retarget.
let realFile2 = fixtureDir.appendingPathComponent("real_codex_2")
try! "a completely different binary".write(to: realFile2, atomically: true, encoding: .utf8)
try! FileManager.default.removeItem(at: symlink)
try! FileManager.default.createSymbolicLink(at: symlink, withDestinationURL: realFile2)
let idC = KBLICodexAvailability.resolveIdentity(path: symlink.path)
ck(idC?.realPath == realFile2.path, "after a symlink RETARGET, resolution follows the NEW target (never the stale cached path)")
ck(idC != idB, "retargeted identity differs from the pre-retarget identity")

ck(KBLICodexAvailability.minimalPATH.hasPrefix("/opt/homebrew/bin"), "minimalPATH starts with /opt/homebrew/bin")
// PIN TRIPWIRE. The previous form of this line compared one literal to another literal, which
// is why a pin naming a version no binary on the fleet carried survived for three weeks: every
// spawn was refused before it started and nothing said so. A pin is only worth something if a
// binary on THIS machine actually answers it, so measure the runtime the runner will spawn.
ck(KBLICodexAvailability.pinnedVersion == "codex-cli 0.147.0",
   "pinnedVersion is the 2026-09-13 pin, measured on M5 at the absolute path the runner resolves")
ck(KBLICodexAvailability.configuredPath == KBLICodexAvailability.dedicatedRuntimePath
       || ProcessInfo.processInfo.environment["KBLI_CODEX_BIN"] != nil,
   "configuredPath defaults to the app-owned runtime, not a package manager's symlink")
if let liveIdentity = KBLICodexAvailability.resolveIdentity() {
    ck(KBLICodexAvailability.versionMatches(liveIdentity),
       "the runtime at configuredPath answers EXACTLY the pinned version (live --version spawn)")
} else {
    ck(false, "configuredPath resolves to an installed runtime on this host (\(KBLICodexAvailability.configuredPath))")
}

// ─────────────────────────────────────────────────────────────────────────────────────────
print("version allow-list — exact entries, one test per allowed version, fail-closed otherwise:")
/// A stand-in runtime: a shell script that answers `--version` with `line` on stdout (or on
/// stderr only), exiting `status`. `versionMatches` spawns it exactly as it spawns the real one.
func fakeRuntime(_ name: String, line: String, status: Int32 = 0, toStderr: Bool = false) -> URL {
    let dir = mkTempDir("runtime-\(name)")
    let file = dir.appendingPathComponent("codex.js")
    let redirect = toStderr ? " 1>&2" : ""
    let script = "#!/bin/sh\nprintf '%s\\n' '\(line)'\(redirect)\nexit \(status)\n"
    try! script.write(to: file, atomically: true, encoding: .utf8)
    try! FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: file.path)
    return file
}
func runtimeAnswers(_ url: URL) -> Bool {
    guard let id = KBLICodexAvailability.resolveIdentity(path: url.path) else { return false }
    return KBLICodexAvailability.versionMatches(id)
}

// The literal IS the tripwire: adding a version without writing its test below fails here first.
ck(KBLICodexAvailability.allowedVersions == ["codex-cli 0.147.0"],
   "allowedVersions is exactly the set measured on M5 on 2026-09-14 (got \(KBLICodexAvailability.allowedVersions))")
let exactShape = try! NSRegularExpression(pattern: "^codex-cli [0-9]+\\.[0-9]+\\.[0-9]+$")
for v in KBLICodexAvailability.allowedVersions {
    let ns = v as NSString
    ck(exactShape.firstMatch(in: v, range: NSRange(location: 0, length: ns.length)) != nil,
       "allow-list entry '\(v)' is one exact version — no floor, range, wildcard or suffix")
}
ck(Set(KBLICodexAvailability.allowedVersions).count == KBLICodexAvailability.allowedVersions.count,
   "allow-list carries no duplicate entry")
ck(KBLICodexAvailability.allowedVersions.contains(KBLICodexAvailability.pinnedVersion),
   "the default runtime's version is itself on the allow-list")
ck(KBLICodexAvailability.dedicatedRuntimePath.contains("/codex-cli-0.147.0/"),
   "the default runtime path names the version it carries")

// One test per allowed version (GUILT side below). 0.147.0: the app-owned runtime and Homebrew.
ck(runtimeAnswers(fakeRuntime("allowed-0147", line: "codex-cli 0.147.0")),
   "ALLOWED codex-cli 0.147.0 — a runtime answering it is accepted")
ck(runtimeAnswers(fakeRuntime("allowed-0147-ws", line: "  codex-cli 0.147.0  ")),
   "INNOCENCE: surrounding whitespace around an allowed version is not a different version")

// GUILT: everything that is not an exact allowed entry is refused before any spawn.
ck(runtimeAnswers(fakeRuntime("stale-0148", line: "codex-cli 0.148.0")) == false,
   "REFUSED codex-cli 0.148.0 — the 2026-08-20 pin; no binary on M5 answers it, so it is not allowed")
ck(runtimeAnswers(fakeRuntime("mise-0154", line: "codex-cli 0.154.0")) == false,
   "REFUSED codex-cli 0.154.0 — the shadowing mise install, never benchmarked")
ck(runtimeAnswers(fakeRuntime("patch-01471", line: "codex-cli 0.147.1")) == false,
   "REFUSED codex-cli 0.147.1 — a neighbour of an allowed version is not allowed (no range)")
// BELOW the allowed version too (council round 1, codex-gpt-5.6-sol): with only higher versions
// refused, a ceiling mutant that accepts anything <= 0.147.0 kept the suite green.
ck(runtimeAnswers(fakeRuntime("below-0146", line: "codex-cli 0.146.0")) == false,
   "REFUSED codex-cli 0.146.0 — an older version is not allowed either (no ceiling)")
ck(runtimeAnswers(fakeRuntime("below-01469", line: "codex-cli 0.146.9")) == false,
   "REFUSED codex-cli 0.146.9 — the closest older patch is not allowed")
ck(KBLICodexAvailability.isAllowedVersion("codex-cli 0.0.0") == false,
   "isAllowedVersion refuses the lowest possible version when called directly")
ck(runtimeAnswers(fakeRuntime("suffix", line: "codex-cli 0.147.0-alpha.1")) == false,
   "REFUSED codex-cli 0.147.0-alpha.1 — a suffix is not the version")
ck(runtimeAnswers(fakeRuntime("short", line: "codex-cli 0.147")) == false,
   "REFUSED codex-cli 0.147 — a prefix of the version is not the version")
ck(runtimeAnswers(fakeRuntime("floor", line: ">= codex-cli 0.147.0")) == false,
   "REFUSED a floor-shaped line")
ck(runtimeAnswers(fakeRuntime("nonzero", line: "codex-cli 0.147.0", status: 1)) == false,
   "REFUSED an allowed line from a runtime that exits non-zero")
ck(runtimeAnswers(fakeRuntime("stderr", line: "codex-cli 0.147.0", toStderr: true)) == false,
   "REFUSED an allowed line printed on stderr only (stdout is the version channel)")
ck(KBLICodexAvailability.isAllowedVersion("") == false, "REFUSED an empty --version output")
// DIRECT, not through versionMatches (council round 1, agy-gemini-3.1-pro): versionMatches trims
// the spawned output before calling isAllowedVersion, so the runtime-level whitespace case above
// cannot see whether isAllowedVersion trims on its own. Both halves of its contract, called bare.
ck(KBLICodexAvailability.isAllowedVersion("  codex-cli 0.147.0\n"),
   "isAllowedVersion itself trims surrounding whitespace (called directly, untrimmed input)")
ck(KBLICodexAvailability.isAllowedVersion("codex-cli 0.147.0") ,
   "isAllowedVersion accepts the allowed entry verbatim")
ck(KBLICodexAvailability.isAllowedVersion("codex-cli 0.148.0\n") == false,
   "isAllowedVersion refuses 0.148.0 when called directly")
ck(KBLICodexAvailability.isAllowedVersion("codex-cli  0.147.0") == false,
   "isAllowedVersion trims only the ends: an inner double space is a different line")

// KBLI_CODEX_BIN resolves the binary the runner spawns, and the allow-list still binds through it.
let envAllowed = fakeRuntime("env-allowed", line: "codex-cli 0.147.0")
let envStale = fakeRuntime("env-stale", line: "codex-cli 0.148.0")
let priorOverride = ProcessInfo.processInfo.environment["KBLI_CODEX_BIN"]
setenv("KBLI_CODEX_BIN", envAllowed.path, 1)
ck(KBLICodexAvailability.configuredPath == envAllowed.path, "KBLI_CODEX_BIN is the path the runner resolves")
ck(KBLICodexAvailability.resolveIdentity()?.realPath
       == envAllowed.resolvingSymlinksInPath().path,
   "resolveIdentity() with no argument resolves the KBLI_CODEX_BIN binary")
ck(KBLICodexAvailability.resolveIdentity().map(KBLICodexAvailability.versionMatches) == true,
   "an allowed runtime behind KBLI_CODEX_BIN is accepted")
setenv("KBLI_CODEX_BIN", envStale.path, 1)
ck(KBLICodexAvailability.resolveIdentity().map(KBLICodexAvailability.versionMatches) == false,
   "a 0.148.0 runtime behind KBLI_CODEX_BIN is refused — the override never widens the allow-list")
ck(KBLIBrain.availability(variant: .internalFull, markerValid: false) == .offline(reason: "codex-version-mismatch"),
   "the CONSUMER: the chat brain goes offline on a runtime off the allow-list (fail-closed)")
setenv("KBLI_CODEX_BIN", "/nonexistent/kbli-codex/codex.js", 1)
ck(KBLIBrain.availability(variant: .internalFull, markerValid: false) == .offline(reason: "codex-not-found"),
   "a KBLI_CODEX_BIN naming no file reads codex-not-found, never a fallback to another install")
if let prior = priorOverride { setenv("KBLI_CODEX_BIN", prior, 1) } else { unsetenv("KBLI_CODEX_BIN") }

// ─────────────────────────────────────────────────────────────────────────────────────────
print("output collector — 256 KiB cap, no truncated-and-served (real Pipe, no subprocess needed):")
let pipe = Pipe()
let errPipe = Pipe()
let collector = KBLIOutputCollector(capBytes: 256 * 1024)
var oversizedFired = false
collector.onOversized = { oversizedFired = true }
collector.attach(stdout: pipe, stderr: errPipe)
let bigChunk = Data(repeating: 0x41, count: 300 * 1024)   // 300 KiB > 256 KiB cap
pipe.fileHandleForWriting.write(bigChunk)
pipe.fileHandleForWriting.closeFile()
errPipe.fileHandleForWriting.closeFile()
ck(waitUntil(2.0, { oversizedFired }), "collector fires onOversized once stdout exceeds the 256 KiB cap")
ck(collector.oversized, "collector.oversized is true")
collector.finish()

let pipe2 = Pipe()
let errPipe2 = Pipe()
let collector2 = KBLIOutputCollector(capBytes: 256 * 1024)
collector2.attach(stdout: pipe2, stderr: errPipe2)
let smallChunk = "hello codex".data(using: .utf8)!
pipe2.fileHandleForWriting.write(smallChunk)
pipe2.fileHandleForWriting.closeFile()
errPipe2.fileHandleForWriting.closeFile()
_ = waitUntil(1.0, { collector2.stdoutData.count > 0 })
ck(collector2.oversized == false, "collector under the cap never fires oversized")
ck(collector2.stdoutData == smallChunk, "under-cap output is captured intact, byte-for-byte")
collector2.finish()

// ─────────────────────────────────────────────────────────────────────────────────────────
print("launch guard — process-group kill by durable cwd identity (design §2, R6-2), real subprocesses:")
let cwdA = mkTempDir("cwdA")
let pidA = spawnSleeper(cwd: cwdA)
ck(isAlive(pidA), "sleeper A spawned and alive")
KBLIRunnerLaunchGuard.killGroupIfCwdMatches(pgid: pidA, tempDir: cwdA.path)
ck(waitUntil(2.0, { isAlive(pidA) == false }), "group killed: pid \(pidA) (pgid match + cwd match) is dead")

print("launch guard — spares a matching pgid whose cwd does NOT match (recycled-pgid case):")
let cwdB = mkTempDir("cwdB")
let pidB = spawnSleeper(cwd: cwdB)
ck(isAlive(pidB), "sleeper B spawned and alive")
KBLIRunnerLaunchGuard.killGroupIfCwdMatches(pgid: pidB, tempDir: "/nonexistent/unrelated/tempdir")
usleep(500_000)
ck(isAlive(pidB), "pid \(pidB) is SPARED (pgid matched but cwd did not) — the recycled-pgid guard")
kill(pidB, SIGKILL)   // manual cleanup

print("launch guard — incomplete-intent recovery: hunt by tempDir alone (no pgid yet, R7-1 case):")
let cwdC = mkTempDir("cwdC")
let pidC = spawnSleeper(cwd: cwdC)
ck(isAlive(pidC), "sleeper C spawned and alive")
KBLIRunnerLaunchGuard.killByTempDirScan(tempDir: cwdC.path)
ck(waitUntil(2.0, { isAlive(pidC) == false }), "tempDir-only scan (crash-in-spawn-window recovery path) kills pid \(pidC)")

print("launch guard — begin/complete/remove sidecar lifecycle + sweep():")
let cwdD = mkTempDir("cwdD")
let pidD = spawnSleeper(cwd: cwdD)
let intentPath = KBLIRunnerLaunchGuard.begin(tempDir: cwdD)
ck(FileManager.default.fileExists(atPath: intentPath.path), "intent sidecar written BEFORE completion")
KBLIRunnerLaunchGuard.complete(intentPath, pgid: pidD, leaderPid: pidD, leaderStartTime: Date().timeIntervalSince1970)
// Simulate "app crashed before reap": do NOT call remove() — call sweep() as the NEXT launch would.
KBLIRunnerLaunchGuard.sweep()
ck(waitUntil(2.0, { isAlive(pidD) == false }), "sweep() (simulating the next app launch) reaps the orphan left by a completed-but-unreaped intent")
ck(FileManager.default.fileExists(atPath: intentPath.path) == false, "sweep() removes the sidecar file after handling it")

// ─────────────────────────────────────────────────────────────────────────────────────────
// NOT covered here — documented honestly rather than faked (design §2's full transition-matrix
// asks for more than a headless sh+sleep harness can cheaply prove):
//   TODO(P2b or later): grandchild-survives-timeout/cancellation/app-exit, spawned via an actual
//     multi-generation process tree (sleeper spawns its own sleeper) rather than the single-level
//     sleeper used above — the cwd-match kill logic is proven above, but not against a true
//     multi-hop descendant tree.
//   TODO(P2b or later): the LEADERLESS-group case (leader exits, a backgrounded grandchild
//     survives in the same pgid) — plausible to construct via `/bin/sh -c "/bin/sleep 30 &"` but
//     not attempted here for time; the durable-tempDir-cwd design (proven above for the simple
//     case) is the same mechanism that would need to cover it.
//   TODO(P2b or later): full crash-injection matrix at each of the four record transitions
//     (pre-intent, intent-no-spawn, spawn-no-completion, completion-no-reap) — only the
//     "completion-no-reap" transition is exercised above (the sweep() test); the other three are
//     unexercised here.
print("ALL CODEX-RUNNER TESTS PASSED (see TODO block above for what P2a deliberately leaves for P2b)")
