import SwiftUI
import AppKit

/// Off-screen snapshot mode: render the real views to PNGs on disk using ImageRenderer.
/// This needs NO Screen Recording TCC grant (the app writes files, it does not capture the
/// display) — so it works from a terminal-launched session where `screencapture` is blocked.
///
/// Invoked via:  WR2Control --snapshot <output-dir>
///
/// NOTE: ImageRenderer does NOT materialize lazy/scroll content off-screen (LazyVGrid in a
/// ScrollView renders empty). The snapshot views below therefore use NON-lazy VStack/HStack
/// with explicit sizing so the renderer captures the full content. They reuse the SAME row/card
/// components and the SAME live data the real views show — this is a faithful render, not a mock.
enum Snapshot {

    @MainActor
    static func runIfRequested() -> Bool {
        let args = CommandLine.arguments
        guard let i = args.firstIndex(of: "--snapshot"), i + 1 < args.count else { return false }
        let outDir = URL(fileURLWithPath: args[i + 1], isDirectory: true)
        try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)

        let state = AppState()  // synchronous disk scan already ran in init
        // demo brainstorm thread for the chat snapshot
        state.chat = [
            ChatMessage(role: .user, text: "Voglio un carosello sul nuovo visto E33G per nomadi digitali."),
            ChatMessage(role: .assistant, text: "Angolo investigativo: l'E33G promette zero tasse sul reddito estero, ma oltre i 183 giorni scatti tax-resident — e il requisito di ~$60.000/anno + datore estero esclude la maggior parte.\n\nTOPIC: E33G remote worker KITAS — la promessa 'tax-free' vs la trappola dei 183 giorni"),
        ]
        state.pendingTopicFromChat = "E33G remote worker KITAS — la promessa 'tax-free' vs la trappola dei 183 giorni"

        // Render every view in BOTH languages (proves the IT/ID switch). Files: studio.it.png,
        // gallery.id.png, etc. — plus plain studio.png/gallery.png/review.png in Italian.
        let size = CGSize(width: 1180, height: 820)
        for code in ["it", "id"] {
            let lm = LanguageManager(); lm.lang = Lang(rawValue: code) ?? .it
            let suffix = code
            capture(HomeSnapshot().environmentObject(state).environmentObject(lm),
                    to: outDir.appendingPathComponent("home.\(suffix).png"), size: size)
            capture(InsightsSnapshot(lang: lm).environmentObject(state).environmentObject(lm),
                    to: outDir.appendingPathComponent("insights.\(suffix).png"), size: size)
            capture(StudioSnapshot().environmentObject(state).environmentObject(lm),
                    to: outDir.appendingPathComponent("studio.\(suffix).png"), size: size)
            capture(ChatSnapshot().environmentObject(state).environmentObject(lm),
                    to: outDir.appendingPathComponent("chat.\(suffix).png"), size: size)
            capture(GallerySnapshot().environmentObject(state).environmentObject(lm),
                    to: outDir.appendingPathComponent("gallery.\(suffix).png"), size: size)
            capture(ReviewSnapshot().environmentObject(state).environmentObject(lm),
                    to: outDir.appendingPathComponent("review.\(suffix).png"), size: size)
            capture(DetailSnapshot(carousel: demoPublishedCarousel(from: state), lang: lm),
                    to: outDir.appendingPathComponent("detail.\(suffix).png"), size: size)
            capture(DetailSnapshot(carousel: demoPublishedCarousel(from: state), lang: lm),
                    to: outDir.appendingPathComponent("detail.published.\(suffix).png"), size: size)
            capture(DetailSnapshot(carousel: demoUnpublishedCarousel(from: state), lang: lm),
                    to: outDir.appendingPathComponent("detail.unpublished.\(suffix).png"), size: size)
            capture(AmbientSnapshot(carousel: demoPublishedCarousel(from: state), lang: lm)
                        .environmentObject(state).environmentObject(lm),
                    to: outDir.appendingPathComponent("ambient.\(suffix).png"), size: size)
            capture(HistorySnapshot(lang: lm).environmentObject(state).environmentObject(lm),
                    to: outDir.appendingPathComponent("history.\(suffix).png"), size: size)
        }
        // canonical IT copies (back-compat names)
        let lmIT = LanguageManager(); lmIT.lang = .it
        capture(StudioSnapshot().environmentObject(state).environmentObject(lmIT),
                to: outDir.appendingPathComponent("studio.png"), size: size)
        capture(GallerySnapshot().environmentObject(state).environmentObject(lmIT),
                to: outDir.appendingPathComponent("gallery.png"), size: size)
        capture(ReviewSnapshot().environmentObject(state).environmentObject(lmIT),
                to: outDir.appendingPathComponent("review.png"), size: size)

        FileHandle.standardOutput.write(
            "SNAPSHOT written (IT+ID): \(state.carousels.count) carousels, \(state.queue.count) queue items → \(outDir.path)\n"
                .data(using: .utf8)!)
        return true
    }

    @MainActor
    private static func capture<V: View>(_ view: V, to url: URL, size: CGSize) {
        let renderer = ImageRenderer(content:
            view.frame(width: size.width, height: size.height)
                .preferredColorScheme(.light)
                .background(Theme.ink)
        )
        renderer.scale = 2.0
        guard let nsImage = renderer.nsImage,
              let tiff = nsImage.tiffRepresentation,
              let rep = NSBitmapImageRep(data: tiff),
              let png = rep.representation(using: .png, properties: [:]) else {
            FileHandle.standardError.write("failed to render \(url.lastPathComponent)\n".data(using: .utf8)!)
            return
        }
        try? png.write(to: url)
    }
}

// MARK: - shared chrome

private struct SnapSidebar: View {
    let active: Section
    let queueCount: Int
    let lang: LanguageManager
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 11) {
                BZLogo(size: 38)
                VStack(alignment: .leading, spacing: 2) {
                    Text(lang.t("app.title")).font(.system(size: 15, weight: .bold)).foregroundStyle(Theme.white)
                    HStack(spacing: 6) { FactRule(width: 16)
                        Text(lang.t("app.subtitle")).font(.system(size: 10)).foregroundStyle(Theme.muted) }
                }
            }.padding(.horizontal, 18).padding(.top, 22).padding(.bottom, 18)
            ForEach(Section.allCases) { sec in
                let on = sec == active
                HStack(spacing: 12) {
                    Image(systemName: sec.icon).frame(width: 22).foregroundStyle(on ? Theme.yellow : Theme.muted)
                    VStack(alignment: .leading, spacing: 1) {
                        Text(lang.t(sec.titleKey)).font(.system(size: 14, weight: .semibold))
                            .foregroundStyle(on ? Theme.white : Theme.muted)
                        Text(lang.t(sec.subKey)).font(.system(size: 10)).foregroundStyle(Theme.muted.opacity(0.8))
                    }
                    Spacer()
                    if sec == .review && queueCount > 0 {
                        Text("\(queueCount)").font(.system(size: 10, weight: .bold)).foregroundStyle(.black)
                            .padding(.horizontal, 7).padding(.vertical, 2).background(Capsule().fill(Theme.yellow))
                    }
                }
                .padding(.horizontal, 14).padding(.vertical, 10)
                .background(RoundedRectangle(cornerRadius: 10).fill(on ? Theme.hairline : .clear))
                .overlay(alignment: .leading) {
                    if on { RoundedRectangle(cornerRadius: 2).fill(Theme.yellow).frame(width: 3, height: 22).padding(.leading, 2) } }
                .padding(.horizontal, 10)
            }
            Spacer()
            HStack(spacing: 8) {
                ForEach(Lang.allCases, id: \.self) { l in
                    HStack(spacing: 5) { Text(l.flag).font(.system(size: 13))
                        Text(l.rawValue.uppercased()).font(.system(size: 10, weight: .semibold)) }
                        .foregroundStyle(lang.lang == l ? .black : Theme.muted)
                        .padding(.horizontal, 9).padding(.vertical, 5)
                        .background(Capsule().fill(lang.lang == l ? Theme.yellow : Theme.hairline))
                }
                Spacer()
            }.padding(.horizontal, 16).padding(.bottom, 10)
            VStack(alignment: .leading, spacing: 6) {
                Divider().overlay(Theme.hairline)
                HStack(spacing: 6) { Circle().fill(Theme.green).frame(width: 7, height: 7)
                    Text(lang.t("diag.assistant.ok")).font(.system(size: 10)).foregroundStyle(Theme.muted) }
                HStack(spacing: 6) { Circle().fill(Theme.green).frame(width: 7, height: 7)
                    Text(lang.t("diag.archive.ok")).font(.system(size: 10)).foregroundStyle(Theme.muted) }
            }.padding(.horizontal, 18).padding(.bottom, 16)
        }
        .frame(width: 238)
        .background(Theme.antracite.opacity(0.45))
    }
}

private struct SnapFrame<Content: View>: View {
    let active: Section
    let queueCount: Int
    let lang: LanguageManager
    @ViewBuilder var content: Content
    var body: some View {
        HStack(spacing: 0) {
            SnapSidebar(active: active, queueCount: queueCount, lang: lang)
            Divider().overlay(Theme.hairline)
            content.frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        }
        .background(Theme.ink)
    }
}

// MARK: - Studio snapshot (with a representative in-progress run)

private struct StudioSnapshot: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    var body: some View {
        SnapFrame(active: .studio, queueCount: state.queue.count, lang: lang) {
            VStack(alignment: .leading, spacing: 18) {
                Text(lang.t("studio.title")).font(Theme.titleFont).foregroundStyle(Theme.white)
                FactRule(width: 44)
                Text(lang.t("studio.lead")).font(Theme.bodyFont).foregroundStyle(Theme.muted)
                GlassCard {
                    VStack(alignment: .leading, spacing: 12) {
                        Label(lang.t("studio.ask"), systemImage: "text.bubble").font(Theme.headingFont).foregroundStyle(Theme.white)
                        Text(lang.t("studio.placeholder"))
                            .font(.system(size: 14)).foregroundStyle(Theme.muted.opacity(0.7))
                            .padding(12).frame(maxWidth: .infinity, alignment: .leading)
                            .background(RoundedRectangle(cornerRadius: 10).fill(Theme.ink))
                        HStack {
                            Label(lang.t("studio.create"), systemImage: "wand.and.stars")
                                .font(.system(size: 14, weight: .semibold)).foregroundStyle(.black)
                                .padding(.horizontal, 14).padding(.vertical, 8).background(Capsule().fill(Theme.yellow))
                        }
                    }
                }
                GlassCard {
                    VStack(alignment: .leading, spacing: 14) {
                        HStack { Circle().fill(Theme.yellow).frame(width: 9, height: 9)
                            Text(lang.t("status.running")).font(Theme.headingFont).foregroundStyle(Theme.white)
                            Spacer()
                            Text("\(lang.t("studio.process")) #50002").font(Theme.monoFont).foregroundStyle(Theme.muted) }
                        Text("« KBLI 2025 requirements to open a small café in Bali »")
                            .font(.system(size: 13, design: .serif)).italic().foregroundStyle(Theme.yellow)
                        let demo: [(String, RunStep.StepState)] = [
                            ("init", .done), ("brief", .done), ("storyboard", .done), ("images", .done),
                            ("layout", .done), ("render", .done), ("critic", .active), ("queue", .pending)]
                        ForEach(Array(demo.enumerated()), id: \.offset) { idx, s in
                            StepRow(step: RunStep(id: s.0, humanTitle: s.0, state: s.1, detail: nil),
                                    isLast: idx == demo.count - 1, lang: lang)
                        }
                    }
                }
            }
            .padding(28).frame(maxWidth: 820, alignment: .leading)
        }
    }
}

private struct HomeSnapshot: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    var body: some View {
        // Top performer (share-ranked). Load its cover SYNCHRONOUSLY (ImageRenderer can't await).
        let top = AppState.viralCovers(state.carousels, now: Date(), windowDays: 400)
        let c = top.first
        let cover = c?.coverURL.flatMap { NSImage(contentsOf: $0) }
        return SnapFrame(active: .home, queueCount: state.queue.count, lang: lang) {
            VStack(alignment: .leading, spacing: 16) {
                Text(lang.t("nav.home")).font(Theme.titleFont).foregroundStyle(Theme.white)
                Text(lang.t("home.sub")).font(.system(size: 11)).foregroundStyle(Theme.muted)
                if let c {
                    HStack(spacing: 24) {
                        ZStack {
                            Rectangle().fill(Theme.ink)
                            if let cover { Image(nsImage: cover).resizable().aspectRatio(contentMode: .fill) }
                        }
                        .frame(width: 300, height: 360).clipShape(RoundedRectangle(cornerRadius: 16))
                        VStack(alignment: .leading, spacing: 16) {
                            if let d = c.domain { Text(d.uppercased()).font(.system(size: 11, weight: .bold)).foregroundStyle(Theme.yellow) }
                            Text(c.topic ?? humanizeSlug(c.slug)).font(.system(size: 23, weight: .bold)).foregroundStyle(Theme.white).lineLimit(3)
                            HStack(spacing: 14) {
                                snapMetric("🔁", c.metrics?.shares, accent: true)
                                snapMetric("❤️", c.metrics?.likes)
                                snapMetric("🔖", c.metrics?.saves)
                                snapMetric("👁", c.metrics?.reach)
                            }
                            Spacer()
                        }
                    }
                    .padding(18)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(RoundedRectangle(cornerRadius: 18).fill(Theme.inkLift))
                }
            }
            .padding(28)
        }
    }
    private func snapMetric(_ g: String, _ v: Int?, accent: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(g).font(.system(size: 14))
            Text(v.map { $0 >= 1000 ? String(format: "%.1fk", Double($0)/1000) : "\($0)" } ?? "—")
                .font(.system(size: 24, weight: .heavy, design: .rounded))
                .foregroundStyle(accent ? Theme.yellow : Theme.white)
        }.frame(minWidth: 64, alignment: .leading).padding(10)
            .background(RoundedRectangle(cornerRadius: 10).fill(Theme.ink))
    }
}

private struct InsightsSnapshot: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    init(lang: LanguageManager) {}
    var body: some View {
        let blocks = InsightsSource.latestFile()
            .flatMap { try? String(contentsOf: $0, encoding: .utf8) }
            .map { MDParser.parse($0) } ?? []
        return SnapFrame(active: .insights, queueCount: state.queue.count, lang: lang) {
            VStack(alignment: .leading, spacing: 14) {
                Text(lang.t("nav.insights")).font(Theme.titleFont).foregroundStyle(Theme.white)
                ForEach(Array(blocks.prefix(7).enumerated()), id: \.offset) { _, b in
                    b.view(lang: lang)
                }
            }
            .padding(28)
        }
    }
}

private struct GallerySnapshot: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    var body: some View {
        SnapFrame(active: .gallery, queueCount: state.queue.count, lang: lang) {
            VStack(alignment: .leading, spacing: 16) {
                Text(lang.t("gallery.title")).font(Theme.titleFont).foregroundStyle(Theme.white)
                Text("\(state.carousels.count) \(lang.t("gallery.count"))").font(Theme.bodyFont).foregroundStyle(Theme.muted)
                let cols = Array(repeating: GridItem(.fixed(210), spacing: 16), count: 4)
                LazyVGrid(columns: cols, spacing: 16) {
                    ForEach(Array(state.carousels.prefix(8))) { c in
                        CarouselCard(carousel: c, lang: lang) {}
                    }
                }
            }
            .padding(28)
        }
    }
}

private struct ChatSnapshot: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    var body: some View {
        SnapFrame(active: .chat, queueCount: state.queue.count, lang: lang) {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(lang.t("chat.title")).font(Theme.titleFont).foregroundStyle(Theme.white)
                        FactRule(width: 44)
                        Text(lang.t("chat.lead")).font(Theme.bodyFont).foregroundStyle(Theme.muted)
                    }
                    Spacer()
                    HStack(spacing: 6) {
                        Text(lang.t("chat.with")).font(.system(size: 10)).foregroundStyle(Theme.muted)
                        ForEach(ChatModel.allCases, id: \.self) { m in
                            Label(m.label, systemImage: m.icon).font(.system(size: 11, weight: .semibold))
                                .foregroundStyle(state.chatModel == m ? .black : Theme.muted)
                                .padding(.horizontal, 9).padding(.vertical, 4)
                                .background(Capsule().fill(state.chatModel == m ? Theme.yellow : Theme.hairline))
                        }
                    }
                }
                VStack(alignment: .leading, spacing: 12) {
                    ForEach(state.chat) { m in chatBubble(m) }
                }
                if let topic = state.pendingTopicFromChat {
                    HStack(spacing: 10) {
                        Image(systemName: "lightbulb.fill").foregroundStyle(Theme.yellow)
                        Text(topic).font(.system(size: 12, weight: .semibold)).foregroundStyle(Theme.white).lineLimit(1)
                        Spacer()
                        Label(lang.t("chat.useidea"), systemImage: "arrow.right.circle.fill")
                            .font(.system(size: 12, weight: .semibold)).foregroundStyle(.black)
                            .padding(.horizontal, 12).padding(.vertical, 7).background(Capsule().fill(Theme.yellow))
                    }
                    .padding(.horizontal, 14).padding(.vertical, 10).background(Theme.yellow.opacity(0.08))
                }
            }
            .padding(24).frame(maxWidth: 820, alignment: .leading)
        }
    }
    private func chatBubble(_ m: ChatMessage) -> some View {
        HStack(alignment: .top, spacing: 10) {
            if m.role == .assistant {
                ZStack { Circle().fill(Theme.yellow.opacity(0.18)).frame(width: 26, height: 26)
                    Image(systemName: state.chatModel.icon).font(.system(size: 11)).foregroundStyle(Theme.yellow) }
            } else { Spacer(minLength: 80) }
            Text(m.text).font(.system(size: 13)).foregroundStyle(m.role == .user ? .black : Theme.white)
                .padding(.horizontal, 12).padding(.vertical, 9)
                .background(RoundedRectangle(cornerRadius: 12).fill(m.role == .user ? Theme.yellow : Theme.inkLift))
            if m.role == .user {
                ZStack { Circle().fill(Theme.hairline).frame(width: 26, height: 26)
                    Image(systemName: "person.fill").font(.system(size: 11)).foregroundStyle(Theme.muted) }
            } else { Spacer(minLength: 80) }
        }
        .frame(maxWidth: .infinity, alignment: m.role == .user ? .trailing : .leading)
    }
}

private struct ReviewSnapshot: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    var body: some View {
        SnapFrame(active: .review, queueCount: state.queue.count, lang: lang) {
            VStack(alignment: .leading, spacing: 12) {
                Text(lang.t("review.title")).font(Theme.titleFont).foregroundStyle(Theme.white)
                Text("\(state.queue.count) \(lang.t("review.count"))").font(Theme.bodyFont).foregroundStyle(Theme.muted)
                VStack(spacing: 10) {
                    ForEach(Array(state.queue.prefix(6))) { item in
                        ReviewRow(item: item, lang: lang)
                    }
                }
            }
            .padding(28).frame(maxWidth: 880, alignment: .leading)
        }
    }
}

// MARK: - new surfaces (Task 9)

/// A real carousel with DEMO metrics injected so the snapshot shows the populated results
/// panel (the live loop is still starved → real metrics are all nil). Clearly a render demo,
/// not fabricated production data: it exists only inside --snapshot.
@MainActor private func demoPublishedCarousel(from state: AppState) -> Carousel? {
    guard var c = state.carousels.first else { return nil }
    c.metrics = EngagementMetrics(shares: 312, likes: 1247, comments: 38, saves: 340, reach: 18200, impressions: 24100)
    c.instagramURL = "https://instagram.com/p/DEMO"
    c.publishedAt = "2026-06-12"
    return c
}

@MainActor private func demoUnpublishedCarousel(from state: AppState) -> Carousel? {
    guard var c = state.carousels.dropFirst().first ?? state.carousels.first else { return nil }
    c.metrics = nil
    c.instagramURL = nil
    c.publishedAt = nil
    return c
}

/// Detail snapshot — loads the cover SYNCHRONOUSLY (the real CarouselDetailView uses the async
/// SlideImage loader, which ImageRenderer cannot materialize off-screen). Faithful to layout.
private struct DetailSnapshot: View {
    let carousel: Carousel?
    let lang: LanguageManager
    var body: some View {
        HStack(spacing: 0) {
            ZStack {
                if let c = carousel, let u = c.coverURL, let img = NSImage(contentsOf: u) {
                    Image(nsImage: img).resizable().scaledToFit().padding(24)
                } else {
                    RoundedRectangle(cornerRadius: 10).fill(Theme.inkLift)
                }
            }.frame(maxWidth: .infinity)
            VStack(alignment: .leading, spacing: 16) {
                Text(carousel?.topic ?? carousel?.slug ?? "—").font(Theme.titleFont).foregroundStyle(Theme.white).lineLimit(3)
                FactRule(width: 44)
                Text(lang.t("detail.results")).font(.system(size: 12, weight: .bold)).foregroundStyle(Theme.muted)
                if let m = carousel?.metrics, m.isEmpty == false {
                    HStack(spacing: 8) {
                        Text("🔁"); Text("\(m.shares ?? 0)").font(.system(size: 24, weight: .bold)).foregroundStyle(Theme.yellow)
                        Text(lang.t("detail.shares")).font(.system(size: 11)).foregroundStyle(Theme.muted)
                    }
                    HStack(spacing: 8) { Text("❤"); Text("\(m.likes ?? 0)").foregroundStyle(Theme.white) }
                    HStack(spacing: 8) { Text("💾"); Text("\(m.saves ?? 0)").foregroundStyle(Theme.white) }
                    HStack(spacing: 8) { Text("👁"); Text("\(m.reach ?? 0)").foregroundStyle(Theme.white) }
                } else if carousel?.isPublished == true {
                    Label(lang.t("detail.awaiting"), systemImage: "clock.arrow.circlepath")
                        .font(Theme.bodyFont)
                        .foregroundStyle(Theme.muted)
                } else {
                    Label(lang.t("detail.notPublished"), systemImage: "chart.bar.xaxis")
                        .font(Theme.bodyFont)
                        .foregroundStyle(Theme.muted)
                }
                Spacer()
            }.frame(width: 360).padding(20).background(Theme.antracite.opacity(0.5))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Theme.ink)
    }
}

/// Ambient snapshot — a static frame of the editorial wall (no Timer, no rotation off-screen).
private struct AmbientSnapshot: View {
    let carousel: Carousel?
    let lang: LanguageManager
    @EnvironmentObject var state: AppState
    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 0) {
                ZStack {
                    if let c = carousel, let u = c.coverURL, let img = NSImage(contentsOf: u) {
                        Image(nsImage: img).resizable().scaledToFit().padding(40)
                    } else { RoundedRectangle(cornerRadius: 14).fill(Theme.inkLift) }
                }.frame(maxWidth: .infinity)
                VStack(alignment: .leading, spacing: 22) {
                    Spacer()
                    Text(carousel?.topic ?? carousel?.slug ?? "—")
                        .font(.system(size: 36, weight: .heavy)).foregroundStyle(Theme.white).lineLimit(4)
                    FactRule(width: 64)
                    HStack(alignment: .firstTextBaseline, spacing: 12) {
                        Text("🔁").font(.system(size: 36))
                        Text("\(carousel?.metrics?.shares ?? 0)")
                            .font(.system(size: 64, weight: .heavy, design: .rounded)).foregroundStyle(Theme.yellow)
                        Text(lang.t("detail.shares")).font(.system(size: 18)).foregroundStyle(Theme.muted)
                    }
                    Text(lang.t("ambient.mostShared")).font(.system(size: 15, weight: .semibold)).foregroundStyle(Theme.muted)
                    Spacer()
                }.frame(width: 460).padding(.trailing, 48)
            }.frame(maxHeight: .infinity)
            HStack(spacing: 24) {
                BZLogo(size: 30)
                Spacer()
                VStack(spacing: 2) { Text("\(state.carousels.filter { $0.isPublished }.count)").font(.system(size: 22, weight: .heavy)).foregroundStyle(Theme.yellow)
                    Text(lang.t("ambient.published")).font(.system(size: 11)).foregroundStyle(Theme.muted) }
            }.padding(.horizontal, 36).padding(.vertical, 16).background(Theme.antracite.opacity(0.6))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Theme.ink)
    }
}

/// History snapshot — three headline numbers + a few run rows (uses live pastRuns if any).
private struct HistorySnapshot: View {
    let lang: LanguageManager
    @EnvironmentObject var state: AppState
    var body: some View {
        SnapFrame(active: .history, queueCount: state.queue.count, lang: lang) {
            VStack(alignment: .leading, spacing: 22) {
                Text(lang.t("history.title")).font(Theme.titleFont).foregroundStyle(Theme.white)
                FactRule(width: 28)
                HStack(spacing: 14) {
                    statCard("\(state.pastRuns.count)", lang.t("history.runsThisMonth"))
                    statCard("—", lang.t("history.passRate"))
                    statCard("—", lang.t("history.avgDuration"))
                }
                if state.pastRuns.isEmpty {
                    Text(lang.t("history.empty")).font(Theme.bodyFont).foregroundStyle(Theme.muted).padding(.top, 30)
                }
            }
            .padding(28).frame(maxWidth: 880, alignment: .leading)
        }
    }
    private func statCard(_ v: String, _ l: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(v).font(.system(size: 38, weight: .heavy, design: .rounded)).foregroundStyle(Theme.yellow)
            Text(l).font(.system(size: 12)).foregroundStyle(Theme.muted)
        }
        .frame(maxWidth: .infinity, alignment: .leading).padding(18)
        .background(RoundedRectangle(cornerRadius: 14).fill(Theme.inkLift.opacity(0.85)))
    }
}
