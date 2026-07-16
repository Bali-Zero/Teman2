import Foundation

/// Pure Foundation prompt logic, kept out of AppState so it is unit-testable without
/// pulling in SwiftUI/Combine (and the macro plugin) into the test target.
enum PromptBuilder {
    /// Convert a colloquial request into the orchestrator prompt.
    /// The agent's documented entrypoint is "design a carousel for <topic>".
    static func toTopicPrompt(_ request: String) -> String {
        var t = request.trimmingCharacters(in: .whitespacesAndNewlines)
        let prefixes = [
            "fammi un carosello sulla", "fammi un carosello sul", "fammi un carosello su",
            "crea un carosello sulla", "crea un carosello sul", "crea un carosello su",
            "carosello sulla", "carosello sul", "carosello su",
            "design a carousel for", "make a carousel about", "carousel about", "carousel for",
        ]
        let lower = t.lowercased()
        for p in prefixes where lower.hasPrefix(p) {
            t = String(t.dropFirst(p.count)).trimmingCharacters(in: .whitespaces)
            break
        }
        if t.isEmpty { t = request.trimmingCharacters(in: .whitespacesAndNewlines) }
        return "design a carousel for \(t)"
    }

    /// Corrective re-run prompt: ask the orchestrator to REVISE an existing carousel in place,
    /// reusing its brief/slides/research and applying the operator's feedback — not to start
    /// a fresh topic. The agent reads output/carousel/<slug>/ as input.
    static func revisePrompt(slug: String, feedback: String) -> String {
        let fb = feedback.trimmingCharacters(in: .whitespacesAndNewlines)
        let path = "~/nuzantara/apps/war-room/output/carousel/\(slug)/"
        var p = "revise the existing carousel at \(path) (slug: \(slug)). "
        p += "Reuse its brief.json, slides.json and research; keep the verified facts. "
        if fb.isEmpty {
            p += "Apply the latest brand cortex (regenerate render + critic)."
        } else {
            p += "Apply this feedback: \(fb)"
        }
        return p
    }
}
