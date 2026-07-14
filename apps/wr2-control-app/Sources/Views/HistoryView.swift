import SwiftUI

/// Production control panel: past pipeline runs + three headline numbers.
/// Distinct from the market RESULTS (Section 2) — this is about how the FACTORY ran,
/// not how the carousels performed on Instagram. Sober by design: a tool to consult.
/// No charts in v1 (data is still bootstrapping; charts would plot near-empty series).
struct HistoryView: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    /// Tap a run → open its linked carousel (matched by slug/topic) in detail.
    var onSelectCarousel: ((Carousel) -> Void)? = nil

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                header
                statsRow
                if state.pastRuns.isEmpty {
                    empty
                } else {
                    VStack(spacing: 10) {
                        ForEach(state.pastRuns) { run in runRow(run) }
                    }
                }
            }
            .padding(28)
            .frame(maxWidth: 880, alignment: .leading)
            .frame(maxWidth: .infinity, alignment: .center)
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(lang.t("history.title")).font(Theme.titleFont).foregroundStyle(Theme.white)
            FactRule(width: 28)
        }
    }

    // MARK: three headline numbers
    private var statsRow: some View {
        HStack(spacing: 14) {
            statCard("\(runsThisMonth)", lang.t("history.runsThisMonth"))
            statCard(passRateLabel, lang.t("history.passRate"))
            statCard(avgDurationLabel, lang.t("history.avgDuration"))
        }
    }

    private func statCard(_ value: String, _ label: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(value).font(.system(size: 38, weight: .heavy, design: .rounded)).foregroundStyle(Theme.yellow)
            Text(label).font(.system(size: 12)).foregroundStyle(Theme.muted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background(RoundedRectangle(cornerRadius: 14).fill(Theme.inkLift.opacity(0.85)))
        .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Theme.hairline))
    }

    // MARK: run row
    private func runRow(_ run: Run) -> some View {
        Button { if let c = linkedCarousel(run) { onSelectCarousel?(c) } } label: {
            HStack(spacing: 14) {
                statusPill(run.status)
                VStack(alignment: .leading, spacing: 3) {
                    Text(run.humanRequest.isEmpty ? run.topic : run.humanRequest)
                        .font(.system(size: 14, weight: .semibold)).foregroundStyle(Theme.white).lineLimit(1)
                    HStack(spacing: 10) {
                        Text(Self.dateFmt.string(from: run.startedAt))
                        if let c = linkedCarousel(run) { Text("\(c.slideCount) \(lang.t("history.slides"))") }
                        Text(durationLabel(run))
                    }.font(.system(size: 11)).foregroundStyle(Theme.muted)
                }
                Spacer()
                if linkedCarousel(run) != nil {
                    Image(systemName: "chevron.right").font(.system(size: 11)).foregroundStyle(Theme.muted)
                }
            }
            .padding(.horizontal, 14).padding(.vertical, 11)
            .background(RoundedRectangle(cornerRadius: 10).fill(Theme.inkLift.opacity(0.6)))
            .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(Theme.hairline))
        }
        .buttonStyle(.plain)
    }

    private func statusPill(_ s: RunStatus) -> some View {
        Text(s.localized(lang))
            .font(.system(size: 10, weight: .bold))
            .foregroundStyle(.black)
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(Capsule().fill(Theme.statusColor(s)))
    }

    private var empty: some View {
        VStack(spacing: 8) {
            Image(systemName: "clock.arrow.circlepath").font(.system(size: 30)).foregroundStyle(Theme.muted.opacity(0.5))
            Text(lang.t("history.empty")).font(Theme.bodyFont).foregroundStyle(Theme.muted)
        }.frame(maxWidth: .infinity).padding(.top, 50)
    }

    // MARK: stats computation
    private var runsThisMonth: Int {
        let cal = Calendar.current
        let now = Date()
        return state.pastRuns.filter {
            cal.isDate($0.startedAt, equalTo: now, toGranularity: .month)
        }.count
    }

    /// First-try PASS proxy: runs that succeeded without a failed step.
    private var passRateLabel: String {
        let finished = state.pastRuns.filter { $0.status == .succeeded || $0.status == .failed }
        guard finished.isEmpty == false else { return "—" }
        let firstTryPass = finished.filter {
            $0.status == .succeeded && $0.steps.contains(where: { $0.state == .failed }) == false
        }.count
        return "\(Int((Double(firstTryPass) / Double(finished.count)) * 100))%"
    }

    private var avgDurationLabel: String {
        let durations = state.pastRuns.compactMap { run -> TimeInterval? in
            guard let end = run.finishedAt else { return nil }
            return end.timeIntervalSince(run.startedAt)
        }
        guard durations.isEmpty == false else { return "—" }
        return Self.formatDuration(durations.reduce(0, +) / Double(durations.count))
    }

    private func durationLabel(_ run: Run) -> String {
        guard let end = run.finishedAt else { return "—" }
        return Self.formatDuration(end.timeIntervalSince(run.startedAt))
    }

    private static func formatDuration(_ s: TimeInterval) -> String {
        let m = Int(s) / 60, sec = Int(s) % 60
        return m > 0 ? "\(m)m \(sec)s" : "\(sec)s"
    }

    /// Match a run to a carousel by slug derived from its topic (best-effort).
    private func linkedCarousel(_ run: Run) -> Carousel? {
        let t = run.topic.lowercased()
        return state.carousels.first {
            t.contains($0.slug) || ($0.topic?.lowercased() == run.topic.lowercased())
        }
    }

    private static let dateFmt: DateFormatter = {
        let f = DateFormatter(); f.dateFormat = "d MMM HH:mm"; return f
    }()
}
