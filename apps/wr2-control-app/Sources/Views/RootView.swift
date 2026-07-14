import SwiftUI

enum Section: String, CaseIterable, Identifiable {
    case home, studio, chat, gallery, insights, review, history
    var id: String { rawValue }
    var icon: String {
        switch self {
        case .home: return "star.circle"
        case .studio: return "wand.and.stars"
        case .chat: return "bubble.left.and.bubble.right"
        case .gallery: return "rectangle.stack"
        case .insights: return "lightbulb"
        case .review: return "checkmark.seal"
        case .history: return "clock.arrow.circlepath"
        }
    }
    var titleKey: String { "nav.\(rawValue)" }
    var subKey: String { "nav.\(rawValue).sub" }
}

struct RootView: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    @State private var selection: Section = .home
    /// When non-nil the main content area shows CarouselDetailView instead of the gallery.
    @State private var selectedCarousel: Carousel?
    /// Idle → ambient. Reset on any user interaction; fires after 180s.
    @State private var idleTimer: Timer?
    @State private var eventMonitor: Any?
    private let idleSeconds: TimeInterval = 180
    /// Kiosk (Mini/TV) launch: a stray mouse move must NOT drop the wall — only a deliberate
    /// gesture (key press / explicit click) leaves ambient. (Review M1.)
    private let kioskMode = CommandLine.arguments.contains("--ambient")

    var body: some View {
        Group {
            if state.mode == .ambient {
                AmbientView()
            } else {
                workShell
            }
        }
        .background(Theme.ink.ignoresSafeArea())
        .onAppear { installIdleMonitor(); armIdleTimer() }
        .onDisappear { removeIdleMonitor() }
    }

    private var workShell: some View {
        HStack(spacing: 0) {
            sidebar.frame(width: 238)
            Divider().overlay(Theme.hairline)
            content.frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .overlay(alignment: .topTrailing) { modeToggle.padding(14) }
    }

    // MARK: - mode toggle + idle → ambient

    private var modeToggle: some View {
        Button { state.mode = .ambient } label: {
            Label(lang.t("mode.ambient"), systemImage: "tv")
                .font(.system(size: 11, weight: .semibold)).foregroundStyle(Theme.muted)
                .padding(.horizontal, 10).padding(.vertical, 5)
                .background(Capsule().fill(Theme.hairline))
        }.buttonStyle(.plain)
    }

    private func armIdleTimer() {
        idleTimer?.invalidate()
        idleTimer = Timer.scheduledTimer(withTimeInterval: idleSeconds, repeats: false) { _ in
            Task { @MainActor in
                if state.isRunning == false { state.mode = .ambient }
                else { armIdleTimer() }   // don't blank the wall mid-run reset; re-arm
            }
        }
    }

    private func installIdleMonitor() {
        guard eventMonitor == nil else { return }
        // In kiosk (TV) mode only a deliberate gesture leaves ambient; a passing mouse move
        // or scroll must NOT (review M1). In normal mode any interaction returns to work.
        let exitGestures: NSEvent.EventTypeMask = kioskMode
            ? [.keyDown, .leftMouseDown]
            : [.keyDown, .mouseMoved, .leftMouseDown, .scrollWheel]
        eventMonitor = NSEvent.addLocalMonitorForEvents(matching: exitGestures) { event in
            Task { @MainActor in
                if state.mode == .ambient { state.mode = .work }
                armIdleTimer()
            }
            return event
        }
    }

    private func removeIdleMonitor() {
        if let m = eventMonitor { NSEvent.removeMonitor(m); eventMonitor = nil }
        idleTimer?.invalidate(); idleTimer = nil
    }

    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 0) {
            // brand header — real Bali Zero logo + a yellow fact-rule signature
            HStack(spacing: 11) {
                BZLogo(size: 38)
                VStack(alignment: .leading, spacing: 2) {
                    Text(lang.t("app.title")).font(.system(size: 15, weight: .bold)).foregroundStyle(Theme.white)
                    HStack(spacing: 6) {
                        FactRule(width: 16)
                        Text(lang.t("app.subtitle")).font(.system(size: 10)).foregroundStyle(Theme.muted)
                    }
                }
            }
            .padding(.horizontal, 18).padding(.top, 22).padding(.bottom, 18)

            ForEach(Section.allCases) { sec in
                Button { selection = sec } label: { navRow(sec) }
                    .buttonStyle(.plain).padding(.horizontal, 10)
            }

            Spacer()
            languageSwitch
            diagnostics
        }
        .background(
            ZStack {
                Theme.antracite.opacity(0.45)
                // subtle Hammurabi-stone brand motif at the very bottom (the "law" texture)
                VStack { Spacer()
                    LinearGradient(colors: [.clear, Theme.red.opacity(0.05)],
                                   startPoint: .top, endPoint: .bottom).frame(height: 120)
                }
            }
        )
    }

    private func navRow(_ sec: Section) -> some View {
        let on = selection == sec
        return HStack(spacing: 12) {
            Image(systemName: sec.icon).frame(width: 22)
                .foregroundStyle(on ? Theme.yellow : Theme.muted)
            VStack(alignment: .leading, spacing: 1) {
                Text(lang.t(sec.titleKey)).font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(on ? Theme.white : Theme.muted)
                Text(lang.t(sec.subKey)).font(.system(size: 10)).foregroundStyle(Theme.muted.opacity(0.8))
            }
            Spacer()
            if sec == .review && state.queue.isEmpty == false {
                Text("\(state.queue.count)").font(.system(size: 10, weight: .bold)).foregroundStyle(.black)
                    .padding(.horizontal, 7).padding(.vertical, 2).background(Capsule().fill(Theme.yellow))
            }
        }
        .padding(.horizontal, 14).padding(.vertical, 10)
        .background(RoundedRectangle(cornerRadius: 10)
            .fill(on ? Theme.hairline : .clear))
        .overlay(alignment: .leading) {
            if on { RoundedRectangle(cornerRadius: 2).fill(Theme.yellow)
                .frame(width: 3, height: 22).padding(.leading, 2) }
        }
    }

    private var languageSwitch: some View {
        HStack(spacing: 8) {
            ForEach(Lang.allCases, id: \.self) { l in
                Button { lang.lang = l } label: {
                    HStack(spacing: 5) {
                        Text(l.flag).font(.system(size: 13))
                        Text(l.rawValue.uppercased()).font(.system(size: 10, weight: .semibold))
                    }
                    .foregroundStyle(lang.lang == l ? .black : Theme.muted)
                    .padding(.horizontal, 9).padding(.vertical, 5)
                    .background(Capsule().fill(lang.lang == l ? Theme.yellow : Theme.hairline))
                }.buttonStyle(.plain)
            }
            Spacer()
        }
        .padding(.horizontal, 16).padding(.bottom, 10)
    }

    private var diagnostics: some View {
        VStack(alignment: .leading, spacing: 6) {
            Divider().overlay(Theme.hairline)
            dot(state.claudePath != nil, ok: "diag.assistant.ok", no: "diag.assistant.no")
            dot(state.warRoomOK, ok: "diag.archive.ok", no: "diag.archive.no")
        }
        .padding(.horizontal, 18).padding(.bottom, 16)
    }

    private func dot(_ ok: Bool, ok okKey: String, no noKey: String) -> some View {
        HStack(spacing: 6) {
            Circle().fill(ok ? Theme.green : Theme.red).frame(width: 7, height: 7)
            Text(lang.t(ok ? okKey : noKey)).font(.system(size: 10)).foregroundStyle(Theme.muted)
        }
    }

    @ViewBuilder private var content: some View {
        // If a carousel is selected, show the full detail view (Task 5).
        // The user can return to the gallery via the "Chiudi / Tutup" button.
        if let sel = selectedCarousel {
            CarouselDetailView(carousel: sel) { selectedCarousel = nil }
        } else {
            switch selection {
            case .home: HomeView(lang: lang, onOpen: { selectedCarousel = $0; selection = .home })
            case .studio: StudioView(onGoToStudio: nil)
            case .chat: ChatView(goToStudio: { selection = .studio })
            case .gallery: GalleryView(onSelect: { selectedCarousel = $0; selection = .gallery })
            case .insights: InsightsView(lang: lang)
            case .review: ReviewView()
            case .history: HistoryView(onSelectCarousel: { selectedCarousel = $0; selection = .history })
            }
        }
    }
}
