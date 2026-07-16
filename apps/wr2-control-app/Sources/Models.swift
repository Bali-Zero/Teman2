import Foundation

// MARK: - App mode

/// The two faces of the WR2 Control app.
/// `.work` = hands-on operator shell (default).
/// `.ambient` = full-screen editorial wall for a TV / office screen.
/// Idle-timer wiring (NSEvent monitor → auto-switch after 180 s) lives in Task 7 (RootView).
enum AppMode: Equatable { case work, ambient }

// MARK: - Engagement metrics

/// Instagram engagement metrics for a carousel, extracted from the review queue.
struct EngagementMetrics: Codable, Equatable {
    var shares: Int?
    var likes: Int?
    var comments: Int?
    var saves: Int?
    var reach: Int?
    var impressions: Int?

    var isEmpty: Bool {
        [shares, likes, comments, saves, reach, impressions].allSatisfy { $0 == nil }
    }

    // The Graph-API backfill (graph_api_backfill_2026-06-23) writes the IG-native key
    // `saved`, not `saves`. Map it so the gallery doesn't silently show 0 Saves.
    // `total_interactions` / `source` in the JSON are intentionally ignored.
    enum CodingKeys: String, CodingKey {
        case shares, likes, comments, reach, impressions
        case saves = "saved"
    }
}

// MARK: - Pipeline run model

/// One end-to-end WR2 carousel generation, driven by the `claude` CLI.
struct Run: Identifiable, Equatable {
    let id: UUID
    let humanRequest: String          // what the operator typed, in plain language
    let topic: String                 // derived prompt sent to the agent
    var startedAt: Date
    var finishedAt: Date?
    var status: RunStatus
    var steps: [RunStep]              // pipeline stages, in order observed
    var costUSD: Double?             // from the final `result` event
    var resultText: String?          // final assistant text / result.result
    var errorMessage: String?        // human-readable error, never a raw stacktrace
    var pid: Int32?                  // child process pid, for proof-of-life

    init(humanRequest: String, topic: String, startedAt: Date = Date()) {
        self.id = UUID()
        self.humanRequest = humanRequest
        self.topic = topic
        self.startedAt = startedAt
        self.finishedAt = nil
        self.status = .starting
        self.steps = RunStep.pipelineTemplate()
        self.costUSD = nil
        self.resultText = nil
        self.errorMessage = nil
        self.pid = nil
    }

    static func == (lhs: Run, rhs: Run) -> Bool { lhs.id == rhs.id }
}

enum RunStatus: String, Equatable {
    case starting       // process spawned, waiting for init
    case running        // events flowing
    case succeeded
    case failed
    case cancelled

    /// IT label (fallback / tests). Use localized(_:) for the UI.
    var humanLabel: String {
        switch self {
        case .starting: return "Avvio…"
        case .running: return "In lavorazione"
        case .succeeded: return "Completato"
        case .failed: return "Errore"
        case .cancelled: return "Annullato"
        }
    }
}

// MARK: - Pipeline steps

/// The WR2 pipeline stages we surface to the operator, in human language.
/// These map to the fan-out the orchestrator performs (4 specialist subagents)
/// plus render + critic gate, recovered from the stream-json `tool_use` events.
struct RunStep: Identifiable, Equatable {
    let id: String                    // stable key, e.g. "brief"
    let humanTitle: String            // "Capire l'argomento"
    var state: StepState
    var detail: String?               // short live note (no jargon)

    enum StepState: String, Equatable {
        case pending, active, done, failed

        var humanLabel: String {
            switch self {
            case .pending: return "In attesa"
            case .active: return "In corso"
            case .done: return "Fatto"
            case .failed: return "Errore"
            }
        }
    }

    /// Canonical pipeline, in order. The orchestrator may not emit each step
    /// distinctly; we advance them as their signal appears in the stream.
    static func pipelineTemplate() -> [RunStep] {
        [
            RunStep(id: "init",       humanTitle: "Preparazione",            state: .active,  detail: "Avvio dell'assistente di design"),
            RunStep(id: "brief",      humanTitle: "Capire l'argomento",      state: .pending, detail: nil),
            RunStep(id: "storyboard", humanTitle: "Scrivere la storia",      state: .pending, detail: nil),
            RunStep(id: "images",     humanTitle: "Creare le immagini",      state: .pending, detail: nil),
            RunStep(id: "layout",     humanTitle: "Comporre le slide",       state: .pending, detail: nil),
            RunStep(id: "render",     humanTitle: "Generare le anteprime",   state: .pending, detail: nil),
            RunStep(id: "critic",     humanTitle: "Controllo qualità",       state: .pending, detail: nil),
            RunStep(id: "queue",      humanTitle: "Pronto per la revisione", state: .pending, detail: nil),
        ]
    }

    /// Map a subagent name (from a `tool_use` event) to the step it represents.
    static func stepID(forSubagent name: String) -> String? {
        let n = name.lowercased()
        if n.contains("brief-interpreter") { return "brief" }
        if n.contains("storyboarder") { return "storyboard" }
        if n.contains("image-prompt") { return "images" }
        if n.contains("layout-composer") { return "layout" }
        if n.contains("critic") { return "critic" }
        return nil
    }
}

// MARK: - Carousel (gallery)

/// A generated carousel on disk under output/carousel/<slug>/.
struct Carousel: Identifiable, Equatable {
    var id: String { slug }
    let slug: String
    let directory: URL
    let slidesDir: URL
    let slidePNGs: [URL]              // sorted NN.png
    let modified: Date
    let topic: String?               // from brief.json
    let domain: String?              // from brief.json
    let criticVerdict: String?       // from queue, if linked
    let slideCount: Int
    let imagegenFallback: Bool       // true if any slide fell back (quota-exhausted, Hammurabi texture instead of fresh hero)
    var coverURL: URL?               // resolved cover image URL
    var metrics: EngagementMetrics?   // Instagram engagement metrics from queue
    var instagramURL: String?         // Instagram post URL
    var publishedAt: String?          // ISO date of publication
    var canvaURL: String?             // Zero Design / Canva edit url (for waitlist work)

    /// Mirrors `isQueueItemPublished(_:)` below, applied to this struct's already-
    /// flattened fields (a Carousel doesn't retain the raw ReviewItem it was joined
    /// from). A trimmed non-empty `instagramURL` OR a trusted `criticVerdict=="published"`
    /// (fed from `item.critic_overall_verdict ?? item.state` at join time) — never bare
    /// presence of the URL key, which an empty string could satisfy (Codex red-team
    /// finding #3, 2026-07-16).
    var isPublished: Bool {
        let urlNonEmpty = instagramURL?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty == false
        let trustedPublishedState = criticVerdict?.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() == "published"
        return urlNonEmpty || trustedPublishedState
    }

    /// L10n key for the critic verdict (or the raw value if unknown). Kept Foundation-pure;
    /// the localized string lives in an extension in Localization.swift (SwiftUI side).
    var criticVerdictKey: String? {
        switch criticVerdict {
        case "pass": return "verdict.pass"
        case "soft_fail": return "verdict.soft_fail"
        case .some(let v) where v.hasPrefix("applied"): return "verdict.applied"
        case .some(let v): return v          // unknown → show raw
        case nil: return nil
        }
    }

    /// Lifecycle phase, derived from publication + the queue state/verdict.
    /// Drives the gallery band colour: published=green, waitlist=blue, review=yellow, rejected=red.
    var phase: CarouselPhase { CarouselPhase.of(state: criticVerdict, isPublished: isPublished) }
}

/// The visual lifecycle phase of a carousel, collapsing the full pipeline FSM
/// (briefed/drafts/rendering/rendered/rendered_shadow/render_failed/
///  applied_ready_for_damar/approved/missed/rejected/published) into the four
/// bands the operator cares about.
///
/// COHERENCE CONTRACT (2026-06-25): every status the supervisor can write to
/// `war_room_drafts.status` must map to a band EXPLICITLY. A status that falls
/// through to the `default` is a bug: `rendering` used to do exactly that and
/// showed as `waitlist` (blue = "born, ready") while a draft was in fact stuck
/// mid-render for hours (scar #2, esiste≠armato — surfaced into the UI). An
/// in-flight or stalled render is NOT a finished carousel, so it maps to
/// `review` (yellow = needs attention), never `waitlist`.
enum CarouselPhase: String {
    case published     // live on IG (green)
    case waitlist      // born by WR2, awaiting publish (blue)
    case review        // needs human attention — rendering / soft_fail / render_failed (yellow)
    case rejected      // discarded (red/muted)

    /// L10n key for the band label.
    var labelKey: String { "phase.\(rawValue)" }

    static func of(state: String?, isPublished: Bool) -> CarouselPhase {
        if isPublished { return .published }
        let s = (state ?? "").lowercased()
        switch s {
        case "published":                                   return .published
        case "rejected", "missed":                          return .rejected
        // in-flight / stalled render and quality bounces → operator must look:
        case "rendering", "soft_fail", "render_failed":     return .review
        // FINISHED-but-unpublished carousels → waitlist (blue):
        // briefed, drafts, drafted, rendered, rendered_shadow,
        // applied_ready_for_damar, approved, pass, queued…
        case "briefed", "drafts", "drafted", "rendered", "rendered_shadow",
             "applied_ready_for_damar", "approved", "pass", "queued":
            return .waitlist
        // Unknown status → review, NOT waitlist: surface it, don't hide it green.
        default:                                            return .review
        }
    }
}

// MARK: - Review queue item (multi-schema defensive)

/// An item in human-review-queue.json. The queue has drifted across ≥3 shapes
/// (legacy critic schema, FSM schema, hybrid). Every field is optional and we
/// normalize to a single presentation model.
struct ReviewItem: Identifiable, Equatable, Decodable {
    // legacy schema
    let id_legacy: String?
    let topic_slug: String?
    let carousel_path: String?
    let slides_dir: String?
    let slide_count: Int?
    let critic_overall_verdict: String?
    let critic_summary: String?
    let drafted_at: String?
    // fsm schema
    let item_id: String?
    let topic: String?
    let state: String?
    let canva_url: String?
    let canva_design_url: String?   // H4: legacy items use this key, not canva_url
    let created_at: String?
    // engagement & publication fields
    let engagement_metrics: EngagementMetrics?
    let instagram_post_url: String?
    let instagram_published_at: String?
    let domain: String?              // backfill: inferred domain (visa/tax/property/...)

    enum CodingKeys: String, CodingKey {
        case id_legacy = "id"
        case topic_slug, carousel_path, slides_dir, slide_count
        case critic_overall_verdict, critic_summary, drafted_at
        case item_id, topic, state, canva_url, canva_design_url, created_at
        case engagement_metrics, instagram_post_url, instagram_published_at, domain
    }

    // normalized presentation
    var id: String { item_id ?? id_legacy ?? topic_slug ?? UUID().uuidString }
    var displayTopic: String { topic ?? topic_slug ?? id }
    var displayState: String {
        let raw = state ?? critic_overall_verdict ?? "—"
        switch raw {
        case "pass": return "Approvato"
        case "soft_fail": return "Da rivedere"
        case "applied_ready_for_damar": return "Applicato — pronto"
        default: return raw.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }
    var displayDate: String { (applied_or_created_date ?? "").prefix(10).description }
    private var applied_or_created_date: String? { created_at ?? drafted_at }
    var canvaLink: String? {
        let s = canva_url ?? canva_design_url
        return (s?.isEmpty == false) ? s : nil
    }
    var hasCanva: Bool { canvaLink != nil }
}

/// Canonical "is this genuinely published" predicate — the ONE rule shared by the A2
/// completeness gate's exemption (WarRoom.scanCarousels), `Carousel.isPublished` above,
/// and the queue's second-pass virtual-carousel materialization. Two conditions, either
/// sufficient:
///  - a trimmed non-empty `instagram_post_url` — an empty string (present but blank,
///    not absent) must NEVER count, or an incomplete render could bypass the
///    completeness gate just by carrying a stray blank field (Codex red-team finding
///    #3, 2026-07-16, guilt direction);
///  - a trusted `state`/`critic_overall_verdict` of exactly `"published"` — a legacy row
///    that reached this state before its URL/timestamp were backfilled must still count,
///    or it silently vanishes from the gallery (same finding, innocence direction).
func isQueueItemPublished(_ item: ReviewItem) -> Bool {
    if let url = item.instagram_post_url,
       url.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty == false {
        return true
    }
    let state = (item.critic_overall_verdict ?? item.state ?? "")
        .trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    return state == "published"
}
