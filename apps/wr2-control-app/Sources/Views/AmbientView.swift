import SwiftUI
import Combine

/// The TV face of WR2 Control: a full-screen "editorial wall" for the office screen.
/// Slowly cycles the most-viral carousel covers (readable from 3–4 meters), with a bottom
/// ribbon that ALWAYS shows what's running now + production counters. When a run is active,
/// the wall foregrounds a large "a carousel is being born" panel with the pipeline steps.
///
/// Reads the SAME `AppState` as work mode — no duplicated data. A timer rotates the cover index.
struct AmbientView: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    @State private var index = 0

    // Rotate the featured cover every 9 seconds (slow, cinematic).
    private let tick = Timer.publish(every: 9, on: .main, in: .common).autoconnect()

    // MARK: cover selection
    /// Most-viral covers of the last 240 days; honest fallback to recent PASS covers.
    private var covers: [Carousel] {
        let viral = AppState.viralCovers(state.carousels, now: Date(), windowDays: 240)
        if viral.isEmpty == false { return viral }
        return state.carousels.filter { ($0.criticVerdict ?? "").uppercased().contains("PASS") }
    }
    private var featured: Carousel? {
        let list = covers
        guard list.isEmpty == false else { return nil }
        return list[index % list.count]
    }
    private var usingViral: Bool {
        AppState.viralCovers(state.carousels, now: Date(), windowDays: 240).isEmpty == false
    }

    var body: some View {
        ZStack {
            Theme.ink.ignoresSafeArea()
            VStack(spacing: 0) {
                stage.frame(maxHeight: .infinity)
                ribbon
            }
        }
        .onReceive(tick) { _ in
            let n = covers.count
            guard n > 0 else { return }
            withAnimation(.easeInOut(duration: 1.0)) { index = (index + 1) % n }
        }
    }

    // MARK: stage (cover + results, OR the live-run "being born" panel)
    @ViewBuilder private var stage: some View {
        if state.isRunning, let run = state.activeRun {
            beingBorn(run)
        } else if let c = featured {
            featuredCover(c)
        } else {
            emptyStage
        }
    }

    private func featuredCover(_ c: Carousel) -> some View {
        HStack(spacing: 0) {
            // big cover, full height
            ZStack {
                if let cover = c.coverURL, let img = NSImage(contentsOf: cover) {
                    Image(nsImage: img).resizable().scaledToFit()
                } else {
                    RoundedRectangle(cornerRadius: 14).fill(Theme.inkLift)
                        .overlay(Image(systemName: "photo").font(.system(size: 60)).foregroundStyle(Theme.muted.opacity(0.4)))
                }
            }
            .id(c.slug)                                   // re-trigger the cross-fade per cover
            .transition(.opacity)
            .padding(48)
            .frame(maxWidth: .infinity)

            // results column (big type for distance)
            VStack(alignment: .leading, spacing: 26) {
                Spacer()
                if let domain = c.domain {
                    Text(domain.uppercased())
                        .font(.system(size: 18, weight: .bold)).tracking(2)
                        .foregroundStyle(Theme.muted)
                }
                Text(c.topic ?? c.slug)
                    .font(.system(size: 40, weight: .heavy)).foregroundStyle(Theme.white)
                    .lineLimit(4).fixedSize(horizontal: false, vertical: true)
                FactRule(width: 64)
                resultsBlock(c)
                Spacer()
            }
            .frame(width: 520, alignment: .leading)
            .padding(.trailing, 56)
        }
    }

    @ViewBuilder private func resultsBlock(_ c: Carousel) -> some View {
        if let m = c.metrics, m.isEmpty == false {
            VStack(alignment: .leading, spacing: 18) {
                // shares — the king metric, huge and yellow
                HStack(alignment: .firstTextBaseline, spacing: 12) {
                    Text("🔁").font(.system(size: 40))
                    Text(m.shares.map { "\($0)" } ?? "—")
                        .font(.system(size: 72, weight: .heavy, design: .rounded))
                        .foregroundStyle(Theme.yellow)
                    Text(lang.t("detail.shares")).font(.system(size: 20)).foregroundStyle(Theme.muted)
                }
                HStack(spacing: 28) {
                    miniMetric("❤", m.likes)
                    miniMetric("💾", m.saves)
                    miniMetric("👁", m.reach)
                }
                Text(usingViral ? lang.t("ambient.mostShared") : lang.t("ambient.justPublished"))
                    .font(.system(size: 16, weight: .semibold)).foregroundStyle(Theme.muted)
            }
        } else {
            Text(lang.t("ambient.awaiting"))
                .font(.system(size: 22, weight: .semibold)).foregroundStyle(Theme.muted)
        }
    }

    private func miniMetric(_ icon: String, _ value: Int?) -> some View {
        HStack(spacing: 7) {
            Text(icon).font(.system(size: 22))
            Text(value.map { "\($0)" } ?? "—")
                .font(.system(size: 26, weight: .semibold)).foregroundStyle(Theme.white)
        }
    }

    // MARK: live run — "a carousel is being born"
    private func beingBorn(_ run: Run) -> some View {
        VStack(spacing: 30) {
            Spacer()
            HStack(spacing: 16) {
                Circle().fill(Theme.yellow).frame(width: 16, height: 16)
                Text(lang.t("ambient.born"))
                    .font(.system(size: 44, weight: .heavy)).foregroundStyle(Theme.white)
            }
            Text(run.humanRequest)
                .font(.system(size: 24, weight: .semibold)).foregroundStyle(Theme.yellow)
                .lineLimit(2).multilineTextAlignment(.center)
            FactRule(width: 80)
            VStack(alignment: .leading, spacing: 14) {
                ForEach(run.steps) { step in
                    HStack(spacing: 16) {
                        Image(systemName: glyph(step.state))
                            .font(.system(size: 22)).foregroundStyle(Theme.stepColor(step.state))
                            .frame(width: 28)
                        Text(step.humanTitle)
                            .font(.system(size: 22, weight: step.state == .active ? .bold : .regular))
                            .foregroundStyle(step.state == .pending ? Theme.muted : Theme.white)
                    }
                }
            }
            .padding(28)
            .background(RoundedRectangle(cornerRadius: 18).fill(Theme.inkLift.opacity(0.7)))
            Spacer()
        }
        .frame(maxWidth: .infinity)
    }

    private func glyph(_ s: RunStep.StepState) -> String {
        switch s {
        case .done: return "checkmark.circle.fill"
        case .active: return "circle.dotted"
        case .failed: return "xmark.circle.fill"
        case .pending: return "circle"
        }
    }

    private var emptyStage: some View {
        VStack(spacing: 16) {
            BZLogo(size: 80)
            Text(lang.t("ambient.empty")).font(.system(size: 22)).foregroundStyle(Theme.muted)
        }.frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: bottom ribbon (always present)
    private var ribbon: some View {
        HStack(spacing: 28) {
            // brand mark
            BZLogo(size: 34)

            // now-running indicator
            if state.isRunning, let run = state.activeRun {
                HStack(spacing: 12) {
                    Circle().fill(Theme.yellow).frame(width: 10, height: 10)
                    Text(lang.t("ambient.nowRunning")).font(.system(size: 16, weight: .bold)).foregroundStyle(Theme.white)
                    Text(run.humanRequest).font(.system(size: 15)).foregroundStyle(Theme.muted).lineLimit(1)
                    progressBar(run)
                }
            }
            Spacer()
            // production counters
            counter(publishedCount, lang.t("ambient.published"))
            counter(awaitingCount, lang.t("ambient.awaitingCount"))
            counter(avgSharesWeek, lang.t("ambient.avgShares"))
        }
        .padding(.horizontal, 40).padding(.vertical, 18)
        .background(Theme.antracite.opacity(0.6))
        .overlay(Rectangle().fill(Theme.hairline).frame(height: 1), alignment: .top)
    }

    private func progressBar(_ run: Run) -> some View {
        let total = max(run.steps.count, 1)
        let done = run.steps.filter { $0.state == .done }.count
        return ProgressView(value: Double(done), total: Double(total))
            .progressViewStyle(.linear).tint(Theme.yellow).frame(width: 180)
    }

    private func counter(_ value: String, _ label: String) -> some View {
        VStack(spacing: 2) {
            Text(value).font(.system(size: 26, weight: .heavy, design: .rounded)).foregroundStyle(Theme.yellow)
            Text(label).font(.system(size: 12)).foregroundStyle(Theme.muted)
        }
    }

    // MARK: counters
    private var publishedCount: String { "\(state.carousels.filter { $0.isPublished }.count)" }
    private var awaitingCount: String {
        "\(state.carousels.filter { $0.isPublished && ($0.metrics?.isEmpty != false) }.count)"
    }
    private var avgSharesWeek: String {
        let shares = state.carousels.compactMap { $0.metrics?.shares }
        guard shares.isEmpty == false else { return "—" }
        return "\(shares.reduce(0, +) / shares.count)"
    }
}
