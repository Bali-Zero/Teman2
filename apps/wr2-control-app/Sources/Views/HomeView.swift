import SwiftUI

/// Home — the landing wall. An auto-advancing carousel of Bali Zero's most successful published
/// carousels (ranked by shares, then reach). Split layout: cover image on one side, engagement
/// metrics on the other. This is the first thing the operator sees on launch.
struct HomeView: View {
    @EnvironmentObject var state: AppState
    let lang: LanguageManager
    var onOpen: (Carousel) -> Void = { _ in }

    @State private var index = 0
    @State private var timer: Timer?
    @State private var paused = false
    private let advanceSeconds: TimeInterval = 5

    /// Top performers: prefer the share-ranked viral set; widen the window generously so the full
    /// IG backfill (10 months) qualifies. Cap to a sensible rotation length.
    private var top: [Carousel] {
        let viral = AppState.viralCovers(state.carousels, now: Date(), windowDays: 400)
        return Array(viral.prefix(12))
    }

    var body: some View {
        GeometryReader { geo in
            VStack(alignment: .leading, spacing: 0) {
                header
                if top.isEmpty {
                    emptyState
                } else {
                    stage(geo: geo)
                    dots
                }
            }
            .padding(28)
        }
        .onAppear { arm() }
        .onDisappear { timer?.invalidate(); timer = nil }
    }

    // MARK: - header

    private var header: some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 6) {
                Text(lang.t("nav.home")).font(Theme.titleFont).foregroundStyle(Theme.white)
                HStack(spacing: 8) {
                    FactRule(width: 28)
                    Text(lang.t("home.sub")).font(.system(size: 11)).foregroundStyle(Theme.muted)
                }
            }
            Spacer()
            if !top.isEmpty {
                Text("\(index + 1) / \(top.count)")
                    .font(Theme.numberFont).foregroundStyle(Theme.muted)
            }
        }
        .padding(.bottom, 18)
    }

    private var emptyState: some View {
        VStack(spacing: 8) {
            Image(systemName: "star").font(.system(size: 32)).foregroundStyle(Theme.muted.opacity(0.5))
            Text(lang.t("home.empty")).font(Theme.bodyFont).foregroundStyle(Theme.muted)
        }.frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - stage (cover | metrics)

    private func stage(geo: GeometryProxy) -> some View {
        let c = top[min(index, top.count - 1)]
        return HStack(spacing: 0) {
            // LEFT — cover image
            ZStack {
                Rectangle().fill(Theme.ink)
                CoverImage(url: c.coverURL)
            }
            .frame(width: max(280, geo.size.width * 0.42))
            .frame(maxHeight: .infinity)
            .clipShape(RoundedRectangle(cornerRadius: 16))

            // RIGHT — metrics + topic
            metricsPanel(c)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
                .padding(.leading, 28)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(RoundedRectangle(cornerRadius: 18).fill(Theme.inkLift))
        .overlay(RoundedRectangle(cornerRadius: 18).strokeBorder(Theme.hairline))
        .contentShape(Rectangle())
        .onTapGesture { onOpen(c) }
        .onHover { h in paused = h; if h { timer?.invalidate() } else { arm() } }
        .animation(.easeInOut(duration: 0.4), value: index)
        .padding(.vertical, 4)
    }

    private func metricsPanel(_ c: Carousel) -> some View {
        VStack(alignment: .leading, spacing: 18) {
            VStack(alignment: .leading, spacing: 8) {
                if let d = c.domain {
                    Text(d.uppercased()).font(.system(size: 11, weight: .bold)).foregroundStyle(Theme.yellow)
                }
                Text(c.topic ?? humanizeSlug(c.slug))
                    .font(.system(size: 24, weight: .bold)).foregroundStyle(Theme.white)
                    .lineLimit(4).fixedSize(horizontal: false, vertical: true)
                if let when = c.publishedAt {
                    Text(when.prefix(10)).font(.system(size: 11)).foregroundStyle(Theme.muted)
                }
            }

            // metric grid
            let m = c.metrics
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 14) {
                metricCell("🔁", lang.t("metric.shares"), m?.shares, accent: true)
                metricCell("❤️", lang.t("metric.likes"), m?.likes)
                metricCell("🔖", lang.t("metric.saves"), m?.saves)
                metricCell("👁", lang.t("metric.reach"), m?.reach)
            }
            .frame(maxWidth: 360, alignment: .leading)

            Spacer()
            HStack(spacing: 6) {
                Image(systemName: "hand.tap").font(.system(size: 11))
                Text(lang.t("home.tap.open")).font(.system(size: 11))
            }.foregroundStyle(Theme.muted.opacity(0.7))
        }
        .padding(.vertical, 8)
    }

    private func metricCell(_ glyph: String, _ label: String, _ value: Int?, accent: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(glyph).font(.system(size: 16))
            Text(value.map(format) ?? "—")
                .font(.system(size: 28, weight: .heavy, design: .rounded))
                .foregroundStyle(accent ? Theme.yellow : Theme.white)
            Text(label).font(.system(size: 10, weight: .semibold)).foregroundStyle(Theme.muted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 12).fill(Theme.ink))
    }

    private func format(_ n: Int) -> String {
        if n >= 1000 { return String(format: "%.1fk", Double(n) / 1000).replacingOccurrences(of: ".0k", with: "k") }
        return "\(n)"
    }

    // MARK: - dots + timer

    private var dots: some View {
        HStack(spacing: 6) {
            ForEach(0..<top.count, id: \.self) { k in
                Capsule()
                    .fill(k == index ? Theme.yellow : Theme.hairline)
                    .frame(width: k == index ? 18 : 6, height: 6)
                    .onTapGesture { withAnimation { index = k }; arm() }
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 16)
    }

    private func arm() {
        timer?.invalidate()
        guard top.count > 1, !paused else { return }
        timer = Timer.scheduledTimer(withTimeInterval: advanceSeconds, repeats: true) { _ in
            Task { @MainActor in advance() }
        }
    }

    private func advance() {
        guard !top.isEmpty else { return }
        withAnimation(.easeInOut(duration: 0.4)) {
            index = (index + 1) % top.count
        }
    }
}

/// Async cover loader (mirrors SlideImage but fills the frame editorially).
struct CoverImage: View {
    let url: URL?
    @State private var image: NSImage?
    var body: some View {
        Group {
            if let img = image {
                Image(nsImage: img).resizable().aspectRatio(contentMode: .fill)
            } else {
                ZStack {
                    Rectangle().fill(Theme.antracite)
                    Image(systemName: "photo").font(.system(size: 28)).foregroundStyle(Theme.muted.opacity(0.4))
                }
            }
        }
        .task(id: url) {
            guard let url else { image = nil; return }
            let loaded = await Task.detached(priority: .utility) { NSImage(contentsOf: url) }.value
            await MainActor.run { self.image = loaded }
        }
    }
}
