import Foundation

// Integration test: drive the REAL ClaudeRunner against the live `claude` CLI with a
// tiny prompt (a generic public topic, no PII). Verifies the end-to-end contract:
//   1. the child process spawns (we get a PID, OS confirms alive)
//   2. real stream-json events flow back and the reducer advances the run
//   3. the run terminates with a result
//
// NOTE: ClaudeRunner delivers callbacks on the MAIN queue (correct for the SwiftUI app,
// whose runloop drains it). A CLI harness must therefore PUMP the main runloop instead of
// blocking it on a semaphore — otherwise the callbacks deadlock (discovered via A/B 2026-06-21).

let runner = ClaudeRunner()

guard let claudePath = ClaudeRunner.resolveClaudePath() else {
    print("❌ claude CLI not found — cannot run integration test")
    exit(2)
}
print("▸ claude: \(claudePath)")
print("▸ cwd:    \(ClaudeRunner.workingDirectory().path)")

final class Box {
    var sawPID = false
    var sawEvent = false
    var sawResult = false
    var terminated = false
    var termCode: Int32 = -999
    var run = Run(humanRequest: "integration ping", topic: "reply with exactly the word PONG")
}
let box = Box()

do {
    try runner.start(
        prompt: "reply with exactly the word PONG",
        agent: "",  // empty → no --agent specialization, fast/cheap wiring check
        onPID: { pid in
            box.sawPID = pid > 0
            print("  • child PID: \(pid)")
            let check = Process()
            check.executableURL = URL(fileURLWithPath: "/bin/ps")
            check.arguments = ["-p", "\(pid)"]
            let pipe = Pipe(); check.standardOutput = pipe
            try? check.run(); check.waitUntilExit()
            let out = String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
            if out.contains("\(pid)") { print("  • OS confirms process alive (proof-of-life)") }
        },
        onEvent: { event in
            box.sawEvent = true
            switch event {
            case .systemInit(let m): print("  • event: init (model \(m ?? "?"))")
            case .assistantText(let t): print("  • event: assistant text \"\(t.prefix(20))\"")
            case .result(let text, let err, let cost, _):
                box.sawResult = true
                print("  • event: result text=\(text ?? "?") error=\(err) cost=\(cost ?? 0)")
            default: break
            }
            RunReducer.apply(event, to: &box.run)
        },
        onRawLine: { _ in },
        onTerminate: { code in
            box.terminated = true
            box.termCode = code
        })
} catch {
    print("❌ launch failed: \(error)")
    exit(1)
}

// Pump the main runloop until termination or timeout (drains the .main.async callbacks).
let deadline = Date().addingTimeInterval(120)
while box.terminated == false && Date() < deadline {
    RunLoop.main.run(mode: .default, before: Date().addingTimeInterval(0.2))
}
if box.terminated == false {
    print("❌ TIMEOUT — run did not terminate in 120s")
    runner.cancel()
    exit(1)
}
// brief extra pump so the final result/terminate callbacks fully flush
let flushUntil = Date().addingTimeInterval(1.0)
while Date() < flushUntil {
    RunLoop.main.run(mode: .default, before: Date().addingTimeInterval(0.1))
}

print("\n────────── integration assertions ──────────")
var fails = 0
func expect(_ c: Bool, _ m: String) {
    if c { print("  ✅ \(m)") } else { print("  ❌ \(m)"); fails += 1 }
}
expect(box.sawPID, "child process spawned with a PID")
expect(box.sawEvent, "real stream-json events received from claude")
expect(box.sawResult, "a result event arrived")
expect(box.terminated && box.termCode == 0, "process terminated cleanly (code \(box.termCode))")
expect(box.run.status == .succeeded, "reducer advanced run to succeeded (status=\(box.run.status.rawValue))")
expect(box.run.steps.first(where: { $0.id == "init" })?.state == .done, "init step marked done by reducer")

print("\nRESULT: \(fails == 0 ? "GREEN" : "RED") — \(fails) failure(s)")
exit(fails == 0 ? 0 : 1)
