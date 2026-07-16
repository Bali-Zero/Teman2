import SwiftUI
import AppKit

/// The human-review queue: what's waiting for approval. Read-only, interactive. Bilingual.
struct ReviewView: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    @State private var selectedCarousel: Carousel? = nil
    @State private var showExternalImport = false

    // Codex red-team finding J, 2026-07-17: `state.queue` is the RAW, unfiltered
    // parse of human-review-queue.json — every state, including already-published
    // entries (WR2-native AND the §A external-post feature's own state="published"
    // rows). This surface is titled "Review" / "items in queue" — a published entry
    // isn't waiting for anything, so it must not pollute the pending-review list.
    // Reuses the SAME canonical predicate the gallery/completeness-gate use
    // (`isQueueItemPublished`, Models.swift) rather than a second ad-hoc rule.
    private var pendingReviewQueue: [ReviewItem] {
        state.queue.filter { !isQueueItemPublished($0) }
    }

    var body: some View {
        let pending = pendingReviewQueue
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(lang.t("review.title")).font(Theme.titleFont).foregroundStyle(Theme.white)
                        HStack(spacing: 8) {
                            FactRule(width: 28)
                            Text("\(pending.count) \(lang.t("review.count"))")
                                .font(Theme.bodyFont).foregroundStyle(Theme.muted)
                        }
                    }
                    Spacer()
                    Button { showExternalImport = true } label: {
                        Label(lang.t("import.button"), systemImage: "photo.on.rectangle.angled").font(.system(size: 12))
                    }.buttonStyle(.bordered).tint(Theme.yellow)
                    Button { state.importCarousel(lang: lang) } label: {
                        Label(lang.t("io.upload"), systemImage: "square.and.arrow.up").font(.system(size: 12))
                    }.buttonStyle(.bordered).tint(Theme.muted)
                    Button { state.refreshFromDisk() } label: {
                        Label(lang.t("gallery.refresh"), systemImage: "arrow.clockwise").font(.system(size: 12))
                    }.buttonStyle(.bordered).tint(Theme.muted)
                }
                if let n = state.ioNotice {
                    Text(n).font(.system(size: 11, weight: .semibold)).foregroundStyle(Theme.green)
                }

                if pending.isEmpty {
                    empty
                } else {
                    VStack(spacing: 10) {
                        ForEach(pending) { item in
                            // Open the carousel detail (Migliora / Zero Design / mark-published)
                            // by joining the queue item to its on-disk carousel.
                            // WarRoom.matchCarousel handles both slug vocabularies (legacy
                            // topic_slug == dir; FSM dir = date-<topic_slug>-<id8>).
                            let liveRun = item.topic_slug.flatMap { state.liveRuns[$0] }
                            if let carousel = WarRoom.matchCarousel(for: item, in: state.carousels) {
                                Button { selectedCarousel = carousel } label: {
                                    ReviewRow(item: item, lang: lang, run: liveRun,
                                              isNew: carousel.slug == state.highlightedSlug)
                                }.buttonStyle(.plain)
                            } else {
                                // No matching carousel on disk yet — non-interactive row.
                                ReviewRow(item: item, lang: lang, run: liveRun)
                            }
                        }
                    }
                }
            }
            .padding(28)
            .frame(maxWidth: 880, alignment: .leading)
            .frame(maxWidth: .infinity, alignment: .center)
        }
        .sheet(item: $selectedCarousel) { c in
            CarouselDetailView(carousel: c) { selectedCarousel = nil }
                .environmentObject(state)
                .environmentObject(lang)
                .frame(minWidth: 900, minHeight: 620)
        }
        .sheet(isPresented: $showExternalImport) {
            ExternalImportSheet(onDismiss: { showExternalImport = false })
                .environmentObject(state)
                .environmentObject(lang)
        }
    }

    private var empty: some View {
        VStack(spacing: 8) {
            Image(systemName: "tray").font(.system(size: 32)).foregroundStyle(Theme.muted.opacity(0.5))
            Text(lang.t("review.empty")).font(Theme.bodyFont).foregroundStyle(Theme.muted)
        }.frame(maxWidth: .infinity).padding(.top, 60)
    }
}

struct ReviewRow: View {
    let item: ReviewItem
    let lang: LanguageManager
    var run: RunMarker? = nil
    /// True right after this row arrived via "Importa carosello esterno" — a brief
    /// visual callout so the operator doesn't have to hunt for the new entry in the
    /// list (scar #2 discipline: don't be mute about a state change).
    var isNew: Bool = false
    var body: some View {
        GlassCard(padding: 14) {
            HStack(spacing: 14) {
                stateBadge
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 8) {
                        Text(item.displayTopic).font(.system(size: 13, weight: .semibold)).foregroundStyle(Theme.white).lineLimit(2)
                        if isNew {
                            Text(lang.t("import.new")).font(.system(size: 9, weight: .bold)).foregroundStyle(.black)
                                .padding(.horizontal, 6).padding(.vertical, 2)
                                .background(Capsule().fill(Theme.yellow))
                        }
                    }
                    HStack(spacing: 10) {
                        if item.displayDate.isEmpty == false {
                            Label(item.displayDate, systemImage: "calendar").font(.system(size: 10)).foregroundStyle(Theme.muted)
                        }
                        if let n = item.slide_count {
                            Text("\(n) \(lang.t("gallery.slides"))").font(.system(size: 10)).foregroundStyle(Theme.muted)
                        }
                        if item.hasCanva {
                            Label("Canva", systemImage: "paintbrush.pointed").font(.system(size: 10)).foregroundStyle(Theme.yellow)
                        }
                    }
                    if let run { RunPill(run: run, lang: lang) }
                    if let summary = item.critic_summary, summary.isEmpty == false {
                        Text(summary).font(.system(size: 11)).foregroundStyle(Theme.muted).lineLimit(2).padding(.top, 2)
                    }
                }
                Spacer()
                if let urlStr = item.canvaLink, let url = URL(string: urlStr) {
                    Button { NSWorkspace.shared.open(url) } label: {
                        Image(systemName: "arrow.up.right.square").font(.system(size: 14))
                    }.buttonStyle(.plain).foregroundStyle(Theme.muted)
                }
            }
        }
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .strokeBorder(isNew ? Theme.yellow.opacity(0.7) : .clear, lineWidth: 2)
        )
    }

    private var stateBadge: some View {
        VStack(spacing: 4) {
            Image(systemName: icon).font(.system(size: 16)).foregroundStyle(color)
            Text(localizedState).font(.system(size: 9, weight: .semibold)).foregroundStyle(color).multilineTextAlignment(.center)
        }.frame(width: 84)
    }

    private var rawState: String { item.state ?? item.critic_overall_verdict ?? "" }
    private var localizedState: String {
        switch rawState {
        case "pass": return lang.t("verdict.pass")
        case "soft_fail": return lang.t("verdict.soft_fail")
        case "applied_ready_for_damar": return lang.t("verdict.applied_ready")
        default: return item.displayState
        }
    }
    private var color: Color {
        if rawState == "pass" || rawState.hasPrefix("applied") { return Theme.green }
        if rawState == "soft_fail" { return Theme.yellow }
        return Theme.muted
    }
    private var icon: String {
        if rawState == "pass" { return "checkmark.seal.fill" }
        if rawState.hasPrefix("applied") { return "paperplane.fill" }
        if rawState == "soft_fail" { return "exclamationmark.triangle.fill" }
        return "clock"
    }
}

/// Small status pill: shows that a carousel has an in-flight (or just-finished) rebuild.
/// This is the visible end of the scar #2 cure — the app is no longer mute about work.
struct RunPill: View {
    let run: RunMarker
    let lang: LanguageManager
    @State private var pulse = false

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .font(.system(size: 10, weight: .bold))
                .foregroundStyle(tint)
                .opacity(run.isLive && pulse ? 0.35 : 1.0)
            Text(label).font(.system(size: 10, weight: .semibold)).foregroundStyle(tint)
        }
        .padding(.horizontal, 8).padding(.vertical, 3)
        .background(Capsule().fill(tint.opacity(0.14)))
        .overlay(Capsule().stroke(tint.opacity(0.35), lineWidth: 0.5))
        .padding(.top, 3)
        .onAppear {
            guard run.isLive else { return }
            withAnimation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true)) { pulse = true }
        }
    }

    private var icon: String {
        if run.isLive { return "gearshape.2.fill" }
        if run.exitCode == 0 { return "checkmark.circle.fill" }
        if run.exitCode == nil { return "questionmark.circle.fill" }
        return "exclamationmark.octagon.fill"
    }
    private var tint: Color {
        if run.isLive { return Theme.yellow }
        if run.exitCode == 0 { return Theme.green }
        return Theme.muted
    }
    private var label: String {
        let mins = run.elapsedMinutes(now: Date())
        if run.isLive {
            let verb = run.kind == .revise ? lang.t("run.rebuilding") : lang.t("run.building")
            return "\(verb) · PID \(run.pid) · \(mins)\(lang.t("run.minShort"))"
        }
        if run.exitCode == 0 { return lang.t("run.finishedOK") }
        if run.exitCode == nil { return lang.t("run.finishedUnknown") }
        return "\(lang.t("run.finishedFail")) (exit \(run.exitCode!))"
    }
}
