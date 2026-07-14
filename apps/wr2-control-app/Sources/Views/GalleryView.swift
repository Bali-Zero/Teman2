import SwiftUI
import AppKit

// MARK: - Sort mode

enum GallerySort: String, CaseIterable {
    case recent, viral, awaiting
    @MainActor func label(_ lang: LanguageManager) -> String {
        switch self {
        case .recent:   return lang.t("gallery.sort.recent")
        case .viral:    return lang.t("gallery.sort.viral")
        case .awaiting: return lang.t("gallery.sort.awaiting")
        }
    }
}

// MARK: - GalleryView

struct GalleryView: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    /// When provided by RootView (Task 5), tapping a card navigates to CarouselDetailView
    /// in the main content area instead of opening the legacy sheet.
    var onSelect: ((Carousel) -> Void)? = nil
    @State private var selected: Carousel?   // used only when onSelect is nil (legacy sheet)
    @State private var sort: GallerySort = .recent

    private let columns = [GridItem(.adaptive(minimum: 200, maximum: 240), spacing: 18)]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(lang.t("gallery.title")).font(Theme.titleFont).foregroundStyle(Theme.white)
                        HStack(spacing: 8) {
                            FactRule(width: 28)
                            Text("\(visible(state.carousels).count) \(lang.t("gallery.count"))")
                                .font(Theme.bodyFont).foregroundStyle(Theme.muted)
                        }
                    }
                    Spacer()
                    // Sort picker
                    Picker("", selection: $sort) {
                        ForEach(GallerySort.allCases, id: \.self) { s in
                            Text(s.label(lang)).tag(s)
                        }
                    }
                    .pickerStyle(.segmented)
                    .frame(width: 260)

                    Button { state.refreshFromDisk() } label: {
                        Label(lang.t("gallery.refresh"), systemImage: "arrow.clockwise").font(.system(size: 12))
                    }.buttonStyle(.bordered).tint(Theme.muted)
                }

                if visible(state.carousels).isEmpty {
                    emptyState
                } else {
                    LazyVGrid(columns: columns, spacing: 18) {
                        ForEach(sorted(visible(state.carousels))) { c in
                            CarouselCard(carousel: c, lang: lang) {
                                if let onSelect { onSelect(c) } else { selected = c }
                            }
                        }
                    }
                }
            }
            .padding(28)
        }
        // legacy sheet — only shown when onSelect is nil (e.g. GalleryView used standalone)
        .sheet(item: $selected) { c in CarouselDetail(carousel: c, lang: lang) }
    }

    private var emptyState: some View {
        VStack(spacing: 8) {
            Image(systemName: "rectangle.stack.badge.plus").font(.system(size: 32)).foregroundStyle(Theme.muted.opacity(0.5))
            Text(lang.t("gallery.empty")).font(Theme.bodyFont).foregroundStyle(Theme.muted)
            Text(lang.t("gallery.empty.sub")).font(.system(size: 11)).foregroundStyle(Theme.muted.opacity(0.7))
        }.frame(maxWidth: .infinity).padding(.top, 60)
    }

    // MARK: - Visibility filter

    /// Hide drafts that were never published AND carry no engagement metrics
    /// (per Zero 2026-06-23: "togli i caroselli che non hanno metriche e non abbiamo pubblicato").
    /// A published carousel is ALWAYS kept (even while awaiting metrics).
    private func visible(_ carousels: [Carousel]) -> [Carousel] {
        carousels.filter { c in
            if c.isPublished { return true }
            if let m = c.metrics, m.isEmpty == false { return true }
            return false
        }
    }

    // MARK: - Sort logic

    private func sorted(_ carousels: [Carousel]) -> [Carousel] {
        switch sort {
        case .recent:
            return carousels.sorted { $0.modified > $1.modified }
        case .viral:
            let viral = AppState.viralCovers(carousels, now: Date(), windowDays: 240)
            let viralIDs = Set(viral.map { $0.id })
            let rest = carousels.filter { !viralIDs.contains($0.id) }.sorted { $0.modified > $1.modified }
            return viral + rest
        case .awaiting:
            // published but no metrics first, then the rest
            let awaiting = carousels.filter { $0.isPublished && ($0.metrics?.isEmpty != false) }
                .sorted { $0.modified > $1.modified }
            let awaitingIDs = Set(awaiting.map { $0.id })
            let rest = carousels.filter { !awaitingIDs.contains($0.id) }.sorted { $0.modified > $1.modified }
            return awaiting + rest
        }
    }
}

struct CarouselCard: View {
    let carousel: Carousel
    let lang: LanguageManager
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            VStack(alignment: .leading, spacing: 0) {
                ZStack(alignment: .top) {
                    SlideImage(url: carousel.coverURL)
                        .aspectRatio(1080.0/1350.0, contentMode: .fill)
                        .frame(height: 230).clipped()
                    // top row: fallback badge (left) + critic verdict (right)
                    HStack {
                        if carousel.imagegenFallback { fallbackBadge }
                        Spacer()
                        verdictBadge
                    }.padding(8)
                    // bottom row: result / state badge
                    VStack {
                        Spacer()
                        HStack {
                            Spacer()
                            resultBadge
                        }.padding(8)
                    }
                }
                VStack(alignment: .leading, spacing: 5) {
                    Text(carousel.topic ?? humanizeSlug(carousel.slug))
                        .font(.system(size: 12, weight: .semibold)).foregroundStyle(Theme.white).lineLimit(2)
                    HStack(spacing: 8) {
                        if let d = carousel.domain {
                            Text(d.uppercased()).font(.system(size: 9, weight: .bold)).foregroundStyle(Theme.yellow)
                        }
                        Text("\(carousel.slideCount) \(lang.t("gallery.slides"))").font(.system(size: 9)).foregroundStyle(Theme.muted)
                        Spacer()
                        Text(carousel.modified, format: .dateTime.day().month()).font(.system(size: 9)).foregroundStyle(Theme.muted)
                    }
                }.padding(10)
            }
            .background(RoundedRectangle(cornerRadius: 14).fill(Theme.inkLift))
            .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Theme.hairline))
            .clipShape(RoundedRectangle(cornerRadius: 14))
        }.buttonStyle(.plain)
        .help(carousel.imagegenFallback ? lang.t("gallery.fallback.tip") : "")
    }

    /// Lifecycle band badge. Published = green (with 🔁 shares when known),
    /// waitlist = blue ("in waitlist"), review = yellow, rejected = muted.
    @ViewBuilder
    private var resultBadge: some View {
        switch carousel.phase {
        case .published:
            if let shares = carousel.metrics?.shares {
                HStack(spacing: 3) {
                    Text("🔁").font(.system(size: 9))
                    Text("\(shares)").font(.system(size: 9, weight: .bold)).foregroundStyle(.white)
                }
                .padding(.horizontal, 7).padding(.vertical, 3)
                .background(Capsule().fill(Theme.green))
            } else {
                bandLabel(lang.t("phase.published"), Theme.green)
            }
        case .waitlist:
            bandLabel(lang.t("phase.waitlist"), Theme.blue)
        case .review:
            bandLabel(lang.t("phase.review"), Theme.yellow)
        case .rejected:
            bandLabel(lang.t("phase.rejected"), Theme.muted)
        }
    }

    private func bandLabel(_ text: String, _ color: Color) -> some View {
        Text(text)
            .font(.system(size: 9, weight: .bold)).foregroundStyle(.white)
            .padding(.horizontal, 7).padding(.vertical, 3)
            .background(Capsule().fill(color))
    }

    private var verdictBadge: some View {
        Group {
            if carousel.criticVerdict != nil {
                Text(carousel.humanVerdict(lang)).font(.system(size: 9, weight: .bold)).foregroundStyle(.black)
                    .padding(.horizontal, 7).padding(.vertical, 3).background(Capsule().fill(badgeColor))
            }
        }
    }
    private var fallbackBadge: some View {
        HStack(spacing: 3) {
            Image(systemName: "exclamationmark.triangle.fill").font(.system(size: 8))
            Text(lang.t("gallery.fallback")).font(.system(size: 8, weight: .bold))
        }
        .foregroundStyle(.black).padding(.horizontal, 6).padding(.vertical, 3)
        .background(Capsule().fill(Theme.yellow))
    }
    private var badgeColor: Color {
        switch carousel.criticVerdict {
        case "pass": return Theme.green
        case "soft_fail": return Theme.yellow
        default: return Theme.muted
        }
    }
}

struct CarouselDetail: View {
    let carousel: Carousel
    let lang: LanguageManager
    @Environment(\.dismiss) private var dismiss
    @State private var brief: WarRoom.Brief?

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                BZLogo(size: 26)
                VStack(alignment: .leading, spacing: 2) {
                    Text(carousel.topic ?? humanizeSlug(carousel.slug))
                        .font(.system(size: 16, weight: .bold)).foregroundStyle(Theme.white)
                    Text("\(carousel.slideCount) \(lang.t("gallery.slides")) · \(carousel.humanVerdict(lang))")
                        .font(.system(size: 11)).foregroundStyle(Theme.muted)
                }
                Spacer()
                if carousel.imagegenFallback {
                    Label(lang.t("gallery.fallback"), systemImage: "exclamationmark.triangle.fill")
                        .font(.system(size: 10, weight: .semibold)).foregroundStyle(Theme.yellow)
                }
                Button { NSWorkspace.shared.open(carousel.directory) } label: {
                    Label(lang.t("gallery.openfolder"), systemImage: "folder").font(.system(size: 11))
                }.buttonStyle(.bordered).tint(Theme.muted)
                Button { dismiss() } label: { Image(systemName: "xmark") }.buttonStyle(.plain).foregroundStyle(Theme.muted)
            }.padding(18)
            Divider().overlay(Theme.hairline)

            ScrollView {
                if let b = brief, (b.key_facts?.isEmpty == false || b.key_numbers?.isEmpty == false) {
                    briefFacts(b).padding(18)
                }
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 180, maximum: 220), spacing: 14)], spacing: 14) {
                    ForEach(carousel.slidePNGs, id: \.self) { url in
                        SlideImage(url: url).aspectRatio(1080.0/1350.0, contentMode: .fit)
                            .background(Theme.ink).clipShape(RoundedRectangle(cornerRadius: 8))
                            .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(Theme.hairline))
                    }
                }.padding(18)
            }
        }
        .frame(width: 860, height: 680).background(Theme.ink)
        .onAppear { brief = WarRoom.readBrief(in: carousel.directory) }
    }

    private func briefFacts(_ b: WarRoom.Brief) -> some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 8) { FactRule(width: 22)
                    Text(lang.t("gallery.brief")).font(Theme.headingFont).foregroundStyle(Theme.white) }
                if let facts = b.key_facts, facts.isEmpty == false {
                    ForEach(facts.prefix(5), id: \.self) { f in
                        HStack(alignment: .top, spacing: 6) {
                            Circle().fill(Theme.yellow).frame(width: 5, height: 5).padding(.top, 6)
                            Text(f).font(.system(size: 12)).foregroundStyle(Theme.muted)
                        }
                    }
                }
                if let nums = b.key_numbers, nums.isEmpty == false {
                    Text(nums.prefix(6).joined(separator: "  ·  ")).font(Theme.numberFont).foregroundStyle(Theme.yellow)
                }
            }
        }
    }
}

struct SlideImage: View {
    let url: URL?
    @State private var image: NSImage?
    var body: some View {
        Group {
            if let img = image {
                Image(nsImage: img).resizable()
            } else {
                ZStack { Rectangle().fill(Theme.antracite)
                    Image(systemName: "photo").foregroundStyle(Theme.muted.opacity(0.4)) }
            }
        }
        .task(id: url) { await load() }
    }
    private func load() async {
        guard let url else { image = nil; return }
        let loaded = await Task.detached(priority: .utility) { NSImage(contentsOf: url) }.value
        await MainActor.run { self.image = loaded }
    }
}

func humanizeSlug(_ slug: String) -> String {
    slug.replacingOccurrences(of: "-", with: " ").replacingOccurrences(of: "_", with: " ").capitalized
}
