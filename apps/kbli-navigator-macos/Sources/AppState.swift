import Combine
import SwiftUI

/// The three primary areas of the app. `.icon`/`.titleKey` (used by the old pill-segmented
/// Search/Media/Zantara tabs) were retired in D3a (2026-08-11) when those tabs were replaced by
/// the native sidebar — RootView's sidebar rows carry their own per-destination SF Symbols and
/// localization keys directly (Library alone now maps to 3 distinct icons, not AppSection's one).
enum AppSection: String, CaseIterable, Identifiable {
    case search, media, chat
    var id: String { rawValue }
}

/// One chat message in the Zantara conversation.
struct ChatMessage: Identifiable, Hashable {
    enum Role: String { case user, zantara, system }
    let id = UUID()
    let role: Role
    var text: String
}

/// Row height mode for the code/sector lists — persisted via `@AppStorage("rowDensity")` (D2,
/// 2026-08-11). String rawValue so it round-trips through UserDefaults directly, no Codable needed.
enum RowDensity: String, CaseIterable {
    case compact, comfortable
    var rowHeight: CGFloat { self == .compact ? 28 : 36 }
    mutating func toggle() { self = self == .compact ? .comfortable : .compact }
}

/// Slim app-wide state — KBLI-specific only. Deliberately does NOT carry any WR2 concepts
/// (WarRoom / QueueWriter / run pipeline / ambient kiosk). Surgical fork per spec §9 S2.
@MainActor
final class AppState: ObservableObject {
    let store: KBLIStore
    /// Raw-JSON index of the SAME bundled dataset `store` decodes, used ONLY by the Phase-2 chat
    /// package builder (KBLIContextPackage.swift) for its schema-snapshot fail-closed check and
    /// per-record reduction — see that file's header comment. `nil` when the bundled JSON is
    /// missing (mirrors `store`'s own missing-JSON fallback); `KBLIBrain.availability()` still
    /// gates the chat path independently, but a `nil` here degrades chat to the internal-error
    /// message rather than crashing.
    let rawSchema: KBLIRawSchemaIndex?

    // search + selection
    @Published var section: AppSection = .search
    @Published var query: String = ""
    @Published var selected: KBLI?
    /// The browsed sector (A–U). nil = showing the 21-sector grid; non-nil = showing that sector's
    /// codes. A live search (`query` non-empty) overrides this and searches across ALL sectors.
    @Published var browsedSector: String?
    /// Bumped by the `Commands` menu's "Search Codes ⌘K" action (App-scene scope has no view-local
    /// @FocusState to target directly) — RootView observes this and moves keyboard focus into the
    /// search field. A counter, not a Bool, so a repeat ⌘K while already focused still re-fires.
    @Published var focusSearchTrigger: Int = 0

    /// The codes currently on screen in the Search section — search results if a query is active,
    /// else the browsed sector's codes, else empty (the 21-sector grid has no code rows). Used to
    /// pick a fallback selection when a Down-arrow from the search field hands focus to the list.
    var visibleRows: [KBLI] {
        let q = query.trimmingCharacters(in: .whitespaces)
        if !q.isEmpty { return results.rows }
        if let sec = browsedSector { return store.codes(in: sec) }
        return []
    }

    /// TEMPORARY design-comparison switch. D = "Registry Dossier" — the synthesised authoritative
    /// card (both LLM panels converged on it 2026-06-24); the default. A/B/C kept for live A/B compare.
    enum CardVariant: String, CaseIterable { case current = "A", gemini = "B", claude = "C", registry = "D" }
    @Published var cardVariant: CardVariant = .registry

    // media (content column selects, detail column renders)
    @Published var mediaSelection: MediaSelection?

    // chat
    @Published var messages: [ChatMessage] = []
    @Published var chatBusy: Bool = false
    /// When the user taps "Ask Zantara" from a code, this primes the chat with that code's context.
    @Published var pendingCodeContext: KBLI?
    /// The code the conversation is about, for the chat's citation rail (spec §3.6): set with the
    /// pending context, kept after it is consumed, cleared by a new chat.
    @Published var chatContextCode: KBLI?

    init() {
        // Load the bundled dataset. If it's missing the app still runs (search shows a banner).
        self.store = KBLIStore() ?? KBLIStore.empty()
        self.rawSchema = KBLIRawSchemaIndex()
        // Open on a designed card rather than an empty pane: preselect the flagship gold-tier
        // code (55203 villa) so the first thing the user sees is the enriched detail.
        // Override with KBLI_OPEN=<code> to deep-link straight to any code (demos / QA).
        let openCode = ProcessInfo.processInfo.environment["KBLI_OPEN"]
        self.selected = (openCode.flatMap { store.code($0) }) ?? store.code("55203")
    }

    var results: KBLIStore.Results { store.search(query) }

    /// Jump to the chat with a specific code in focus (called from the detail view toolbar).
    func askZantara(about code: KBLI) {
        pendingCodeContext = code
        chatContextCode = code
        section = .chat
    }

    func resetChat() {
        messages.removeAll()
        pendingCodeContext = nil
        chatContextCode = nil
    }
}
