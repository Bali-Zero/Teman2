import Foundation

/// A single decoded line from `claude --output-format stream-json --verbose`.
/// The format (verified on disk 2026-06-21) is one JSON object per line:
///   {"type":"system","subtype":"init", "model":..., "agents":[...]}
///   {"type":"assistant","message":{"content":[{"type":"text","text":...}|{"type":"tool_use","name":...}]}}
///   {"type":"user","message":{"content":[{"type":"tool_result", ...}]}}
///   {"type":"result","subtype":"success","result":..., "total_cost_usd":..., "is_error":...}
///   {"type":"rate_limit_event", ...}
enum StreamEvent {
    case systemInit(model: String?)
    case assistantText(String)
    case toolUse(name: String, input: String?)
    case toolResult(isError: Bool)
    case result(text: String?, isError: Bool, costUSD: Double?, errorStatus: String?)
    case rateLimit(status: String?)
    case other(type: String)
    case unparsable(String)

    /// Parse one line of stream-json. Never throws — a malformed line becomes `.unparsable`
    /// (scar #6: surface the truth, don't crash the monitor on garbage).
    static func parse(line: String) -> StreamEvent? {
        let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmed.isEmpty == false else { return nil }
        guard trimmed.first == "{" else { return .unparsable(trimmed) }
        guard let data = trimmed.data(using: .utf8),
              let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
        else { return .unparsable(trimmed) }

        let type = (obj["type"] as? String) ?? "?"
        switch type {
        case "system":
            if (obj["subtype"] as? String) == "init" {
                return .systemInit(model: obj["model"] as? String)
            }
            return .other(type: "system")

        case "assistant":
            guard let msg = obj["message"] as? [String: Any],
                  let content = msg["content"] as? [[String: Any]] else {
                return .other(type: "assistant")
            }
            // a message can carry multiple blocks; prefer tool_use, else text
            for block in content {
                if (block["type"] as? String) == "tool_use" {
                    let name = (block["name"] as? String) ?? "?"
                    let input = inputSummary(block["input"])
                    return .toolUse(name: name, input: input)
                }
            }
            for block in content {
                if (block["type"] as? String) == "text",
                   let t = block["text"] as? String, t.isEmpty == false {
                    return .assistantText(t)
                }
            }
            return .other(type: "assistant")

        case "user":
            if let msg = obj["message"] as? [String: Any],
               let content = msg["content"] as? [[String: Any]] {
                for block in content where (block["type"] as? String) == "tool_result" {
                    let isErr = (block["is_error"] as? Bool) ?? false
                    return .toolResult(isError: isErr)
                }
            }
            return .other(type: "user")

        case "result":
            let isErr = (obj["is_error"] as? Bool) ?? false
            let text = obj["result"] as? String
            let cost = obj["total_cost_usd"] as? Double
            let errStatus = obj["api_error_status"] as? String
            return .result(text: text, isError: isErr, costUSD: cost, errorStatus: errStatus)

        case "rate_limit_event":
            let info = obj["rate_limit_info"] as? [String: Any]
            return .rateLimit(status: info?["status"] as? String)

        default:
            return .other(type: type)
        }
    }

    private static func inputSummary(_ input: Any?) -> String? {
        guard let dict = input as? [String: Any] else { return nil }
        // Agent tool: surface subagent_type + a short slice of the prompt
        if let sub = dict["subagent_type"] as? String {
            return sub
        }
        if let desc = dict["description"] as? String {
            return desc
        }
        return nil
    }
}

/// Applies a stream of events to a Run, advancing the pipeline steps.
/// Pure function-style mutation so it can be unit-tested without a process.
struct RunReducer {

    /// Apply one event to a run, returning the mutated run.
    static func apply(_ event: StreamEvent, to run: inout Run) {
        switch event {
        case .systemInit:
            run.status = .running
            setStep("init", .done, in: &run)

        case .toolUse(let name, let input):
            // An Agent dispatch to a specialist subagent advances a pipeline step.
            let subagent = input ?? name
            if let stepID = RunStep.stepID(forSubagent: subagent) {
                // mark prior pending steps before this one as done (best-effort ordering)
                activate(stepID, in: &run)
            } else if name.lowercased() == "bash" && (input ?? "").lowercased().contains("render") {
                activate("render", in: &run)
            }

        case .assistantText(let text):
            // keep the latest assistant note on the active step (human-readable)
            if let idx = run.steps.firstIndex(where: { $0.state == .active }) {
                run.steps[idx].detail = text.prefix(120).trimmingCharacters(in: .whitespacesAndNewlines)
            }

        case .result(let text, let isError, let cost, let errStatus):
            run.costUSD = cost
            run.resultText = text
            run.finishedAt = Date()
            if isError {
                run.status = .failed
                run.errorMessage = humanError(errStatus, fallback: text)
                failActiveStep(in: &run)
            } else {
                run.status = .succeeded
                markRemainingDone(in: &run)
            }

        case .rateLimit(let status):
            if status == "rejected" || status == "blocked" {
                // H1 fix: a hard rate-limit rejection ends the run — mark it failed now so the
                // UI never shows a contradictory running+error state.
                run.errorMessage = "Limite di utilizzo Claude raggiunto — riprova più tardi."
                run.status = .failed
                run.finishedAt = Date()
                failActiveStep(in: &run)
            }

        case .toolResult(let isError):
            if isError, let idx = run.steps.firstIndex(where: { $0.state == .active }) {
                run.steps[idx].detail = "Un passaggio ha segnalato un problema"
            }

        case .other, .unparsable:
            break
        }
    }

    // MARK: helpers

    private static func setStep(_ id: String, _ state: RunStep.StepState, in run: inout Run) {
        if let i = run.steps.firstIndex(where: { $0.id == id }) {
            run.steps[i].state = state
        }
    }

    /// Activate a step: mark all earlier-pending steps done, this one active.
    private static func activate(_ id: String, in run: inout Run) {
        guard let target = run.steps.firstIndex(where: { $0.id == id }) else { return }
        for i in 0..<run.steps.count {
            if i < target {
                if run.steps[i].state == .pending || run.steps[i].state == .active {
                    run.steps[i].state = .done
                }
            } else if i == target {
                if run.steps[i].state != .done { run.steps[i].state = .active }
            }
        }
    }

    private static func failActiveStep(in run: inout Run) {
        if let i = run.steps.firstIndex(where: { $0.state == .active }) {
            run.steps[i].state = .failed
        }
    }

    private static func markRemainingDone(in run: inout Run) {
        for i in 0..<run.steps.count where run.steps[i].state != .failed {
            run.steps[i].state = .done
        }
    }

    private static func humanError(_ status: String?, fallback: String?) -> String {
        if let s = status, s.isEmpty == false {
            return "La pipeline si è interrotta (\(s)). Controlla i log."
        }
        if let f = fallback, f.isEmpty == false {
            return String(f.prefix(200))
        }
        return "La pipeline si è interrotta per un errore non specificato."
    }
}
