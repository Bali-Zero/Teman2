import Foundation

// Live-prod driver: uses the EXACT production ClaudeRunner (same code the SwiftUI app
// drives) to launch a REAL WR2 carousel run via the wr2-design-architect agent.
// Logs every step + raw line to stdout (redirected to a file). Pumps the main runloop.
//
// Topic is generic/public (KBLI café) — no PII (Law 2 safe).

let topic = CommandLine.arguments.count > 1
    ? CommandLine.arguments[1]
    : "design a carousel for KBLI 2025 requirements to open a small café in Bali"

let runner = ClaudeRunner()
print("▸ LIVE WR2 RUN")
print("▸ topic: \(topic)")
print("▸ claude: \(ClaudeRunner.resolveClaudePath() ?? "NOT FOUND")")
print("▸ cwd: \(ClaudeRunner.workingDirectory().path)")
print("▸ started: \(Date())")
fflush(stdout)

final class Box {
    var run = Run(humanRequest: "live test", topic: "x")
    var terminated = false
    var code: Int32 = -1
}
let box = Box()
box.run = Run(humanRequest: topic, topic: topic)

func dumpSteps() {
    let line = box.run.steps.map { "\($0.id):\($0.state.rawValue)" }.joined(separator: " ")
    print("  STEPS  \(line)")
    fflush(stdout)
}

do {
    try runner.start(
        prompt: topic,
        agent: "wr2-design-architect",
        onPID: { pid in print("  PID \(pid)"); fflush(stdout) },
        onEvent: { ev in
            switch ev {
            case .systemInit(let m): print("  ● init model=\(m ?? "?")")
            case .toolUse(let n, let i): print("  ● tool_use \(n) → \(i ?? "")")
            case .assistantText(let t): print("  ● text: \(t.prefix(100))")
            case .result(let t, let e, let c, _): print("  ● RESULT error=\(e) cost=\(c ?? 0) text=\(t?.prefix(120) ?? "")")
            case .rateLimit(let s): print("  ● rate_limit \(s ?? "")")
            default: break
            }
            fflush(stdout)
            RunReducer.apply(ev, to: &box.run)
            dumpSteps()
        },
        onRawLine: { _ in },
        onTerminate: { code in
            box.terminated = true; box.code = code
            print("  TERMINATED code=\(code) at \(Date())")
            fflush(stdout)
        })
} catch {
    print("LAUNCH FAILED: \(error)")
    exit(1)
}

// pump up to 40 minutes (a full carousel can take a while)
let deadline = Date().addingTimeInterval(2400)
while box.terminated == false && Date() < deadline {
    RunLoop.main.run(mode: .default, before: Date().addingTimeInterval(0.5))
}
if box.terminated == false {
    print("TIMEOUT after 40min")
    runner.cancel()
}
print("\nFINAL status=\(box.run.status.rawValue) code=\(box.code)")
dumpSteps()
exit(box.run.status == .succeeded ? 0 : 1)
