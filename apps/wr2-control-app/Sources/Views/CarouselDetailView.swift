import SwiftUI
import Combine

/// Task 5 — full carousel detail: big cover + engagement results panel + mark-as-published.
///
/// Layout: two-column HStack:
///   Left  (flex) — big cover image + slide thumbnail strip + close button
///   Right (360 pt fixed) — title, fact rule, metrics block, critic verdict, publish controls
///
/// Brand rules enforced:
///   - Yellow `#F4C430` ONLY for data numbers + fact rule
///   - Red `#C8102E` ONLY for FAIL verdict
///   - Shares are the KING metric: shown FIRST, at larger size in yellow
///   - Honest empty states: if published but no metrics → "awaiting"; if not published → "not published" + mark button
///   - Mark-published is REVERSIBLE: published items show "Open IG" + "Undo" control
struct CarouselDetailView: View {
    let carousel: Carousel
    var onClose: () -> Void

    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager

    @State private var showPublishForm = false
    @State private var igLink = ""
    @State private var showReviseForm = false
    @State private var reviseFeedback = ""
    // Publish-to-IG confirm popover (Legge 5: explicit operator gate before posting).
    @State private var showPublishIGConfirm = false
    @State private var publishCaption = ""
    @State private var captionIsLoading = false
    @State private var captionLoadError: String?
    // Live console: tail of <carousel>/.run.log, refreshed while a run is in flight.
    @State private var logTail: [String] = []
    @State private var showConsole = false
    private let logTimer = Timer.publish(every: 2.0, on: .main, in: .common).autoconnect()

    /// Which slide is shown in the big preview. nil ⇒ the cover. Driven by the thumbnail
    /// strip + ◀ ▶ arrows, so the operator can flip through all 8 slides, not just the cover.
    @State private var selectedSlide: URL? = nil

    /// All slide images in order. Falls back to the cover when the scan found none.
    private var slides: [URL] {
        carousel.slidePNGs.isEmpty ? [carousel.coverURL].compactMap { $0 } : carousel.slidePNGs
    }
    /// The image currently in the big preview: the chosen slide, else cover, else first slide.
    private var shownSlide: URL? { selectedSlide ?? carousel.coverURL ?? slides.first }
    private var shownIndex: Int? { slides.firstIndex(where: { $0 == shownSlide }) }

    private func step(_ delta: Int) {
        guard slides.isEmpty == false else { return }
        let cur = shownIndex ?? 0
        let next = (cur + delta + slides.count) % slides.count
        selectedSlide = slides[next]
    }

    /// The in-flight (or just-finished) run for THIS carousel, from AppState's disk+ps scan.
    private var run: RunMarker? { state.liveRuns[carousel.slug] }

    var body: some View {
        HStack(spacing: 0) {
            coverColumn
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            Divider()
                .overlay(Theme.hairline)
            resultsPanel
                .frame(minWidth: 360, maxWidth: 360, maxHeight: .infinity)
        }
        .background(Theme.ink)
        .onAppear { refreshTail() }
        .onReceive(logTimer) { _ in
            // keep the live console fresh while a run is in flight
            if run?.isLive == true && showConsole { refreshTail() }
        }
    }

    // MARK: - Left: cover + thumbnails

    private var coverColumn: some View {
        VStack(alignment: .leading, spacing: 14) {
            // close button
            Button(action: onClose) {
                Label(lang.t("detail.close"), systemImage: "chevron.left")
                    .font(.system(size: 12, weight: .semibold))
            }
            .buttonStyle(.plain)
            .foregroundStyle(Theme.muted)

            // big preview — the SELECTED slide (default cover), flippable via ◀ ▶ + thumbs
            ZStack {
                SlideImage(url: shownSlide)
                    .aspectRatio(1080.0 / 1350.0, contentMode: .fit)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .strokeBorder(Theme.hairline, lineWidth: 1)
                    )

                // download THIS slide — top-right over the preview
                VStack {
                    HStack {
                        Spacer()
                        Button {
                            if let src = shownSlide {
                                state.exportSlide(slug: carousel.slug,
                                                  index: shownIndex ?? 0, src: src, lang: lang)
                            }
                        } label: {
                            Image(systemName: "square.and.arrow.down")
                                .font(.system(size: 13, weight: .bold))
                                .foregroundStyle(.white)
                                .frame(width: 30, height: 30)
                                .background(Circle().fill(.black.opacity(0.45)))
                                .overlay(Circle().strokeBorder(.white.opacity(0.25), lineWidth: 0.5))
                        }
                        .buttonStyle(.plain)
                        .help(lang.t("io.downloadSlide"))
                    }
                    Spacer()
                }
                .padding(10)

                // prev / next arrows + position counter (only when there's more than one slide)
                if slides.count > 1 {
                    HStack {
                        arrowButton(system: "chevron.left") { step(-1) }
                        Spacer()
                        arrowButton(system: "chevron.right") { step(1) }
                    }
                    .padding(.horizontal, 10)

                    if let i = shownIndex {
                        VStack {
                            Spacer()
                            Text("\(i + 1) / \(slides.count)")
                                .font(.system(size: 11, weight: .semibold, design: .rounded))
                                .foregroundStyle(.white)
                                .padding(.horizontal, 9).padding(.vertical, 4)
                                .background(Capsule().fill(.black.opacity(0.55)))
                                .padding(.bottom, 10)
                        }
                    }
                }
            }

            // slide thumbnail strip — click to jump to that slide
            thumbnailStrip
        }
        .padding(20)
    }

    private func arrowButton(system: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: system)
                .font(.system(size: 15, weight: .bold))
                .foregroundStyle(.white)
                .frame(width: 34, height: 34)
                .background(Circle().fill(.black.opacity(0.45)))
                .overlay(Circle().strokeBorder(.white.opacity(0.25), lineWidth: 0.5))
        }
        .buttonStyle(.plain)
    }

    private var thumbnailStrip: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(Array(slides.enumerated()), id: \.element) { idx, url in
                    let isSel = url == shownSlide
                    Button { selectedSlide = url } label: {
                        SlideImage(url: url)
                            .aspectRatio(1080.0 / 1350.0, contentMode: .fill)
                            .frame(width: 44, height: 55)
                            .clipShape(RoundedRectangle(cornerRadius: 5))
                            .overlay(
                                RoundedRectangle(cornerRadius: 5)
                                    .strokeBorder(isSel ? Theme.yellow : Theme.hairline,
                                                  lineWidth: isSel ? 2 : 1)
                            )
                            .opacity(isSel ? 1.0 : 0.7)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .frame(height: 60)
    }

    // MARK: - Right: results panel

    private var resultsPanel: some View {
        VStack(alignment: .leading, spacing: 0) {
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 18) {
                    topicHeader
                    if run != nil { runSection }
                    metricsSection
                    Divider().overlay(Theme.hairline)
                    criticSection
                }
                .padding(20)
            }

            Divider().overlay(Theme.hairline)
            exportBar
                .padding(.horizontal, 20).padding(.top, 14)
            publishControlsSection
                .padding(20)
        }
        .background(Theme.antracite.opacity(0.45))
    }

    // Persistent export toolbar: download the whole carousel as PNGs. Plus a transient
    // IO notice (saved / uploaded / error) so the action is never silent.
    @ViewBuilder private var exportBar: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let n = state.ioNotice {
                Text(n).font(.system(size: 11, weight: .semibold)).foregroundStyle(Theme.green)
            }
            Button {
                state.exportCarousel(carousel, lang: lang)
            } label: {
                Label(lang.t("io.downloadAll"), systemImage: "square.and.arrow.down.on.square")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(Theme.white)
                    .padding(.horizontal, 12).padding(.vertical, 7)
                    .background(Capsule().fill(Theme.muted.opacity(0.28)))
            }
            .buttonStyle(.plain)
            .disabled(carousel.slidePNGs.isEmpty)
        }
    }

    // Topic title + fact rule
    private var topicHeader: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(carousel.topic ?? humanizeSlug(carousel.slug))
                .font(Theme.headingFont)
                .foregroundStyle(Theme.white)
                .fixedSize(horizontal: false, vertical: true)
            FactRule(width: 40)
        }
    }

    // MARK: - Live run (scar #2 cure: the app shows work in flight + a live console)

    @ViewBuilder private var runSection: some View {
        if let run {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    RunPill(run: run, lang: lang)
                    Spacer()
                    Button { showConsole.toggle(); refreshTail() } label: {
                        Label(lang.t("run.console"),
                              systemImage: showConsole ? "chevron.up" : "chevron.down")
                            .font(.system(size: 10, weight: .semibold))
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(Theme.muted)
                }
                if showConsole { consoleView }
            }
        }
    }

    private var consoleView: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: 1) {
                    if logTail.isEmpty {
                        Text(lang.t("run.noLog"))
                            .font(.system(size: 10)).foregroundStyle(Theme.muted)
                    } else {
                        ForEach(Array(logTail.enumerated()), id: \.offset) { idx, line in
                            Text(prettyLogLine(line))
                                .font(.system(size: 9.5, design: .monospaced))
                                .foregroundStyle(Theme.muted)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .id(idx)
                        }
                    }
                }
            }
            .frame(height: 160)
            .padding(8)
            .background(RoundedRectangle(cornerRadius: 8).fill(Theme.ink))
            .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(Theme.hairline, lineWidth: 1))
            .onChange(of: logTail.count) {
                if let last = logTail.indices.last { proxy.scrollTo(last, anchor: .bottom) }
            }
        }
    }

    private func refreshTail() {
        logTail = AppState.runLogTail(slug: carousel.slug)
    }

    /// Condense a stream-json line to a human-readable token: pull the event `type` /
    /// tool name out of the JSON so the console reads like a progress log, not raw JSON.
    private func prettyLogLine(_ line: String) -> String {
        let s = line.trimmingCharacters(in: .whitespaces)
        guard s.hasPrefix("{"),
              let data = s.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return String(s.prefix(160)) }
        let type = (obj["type"] as? String) ?? "?"
        if let name = obj["subtype"] as? String { return "• \(type)/\(name)" }
        // surface tool calls if present
        if let msg = obj["message"] as? [String: Any],
           let content = msg["content"] as? [[String: Any]] {
            for block in content {
                if let t = block["type"] as? String, t == "tool_use",
                   let n = block["name"] as? String { return "→ tool: \(n)" }
            }
        }
        return "• \(type)"
    }

    // MARK: - Metrics

    @ViewBuilder private var metricsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(lang.t("detail.results"))
                .font(.system(size: 11, weight: .bold))
                .foregroundStyle(Theme.muted)
                .textCase(.uppercase)

            if let m = carousel.metrics, !m.isEmpty {
                // Real data — shares FIRST (king metric)
                VStack(alignment: .leading, spacing: 10) {
                    metricRow(icon: "arrow.2.squarepath", value: m.shares,
                              key: "detail.shares", emphasize: true)
                    metricRow(icon: "heart.fill",          value: m.likes,
                              key: "detail.likes")
                    metricRow(icon: "bubble.left.fill",    value: m.comments,
                              key: "detail.comments")
                    metricRow(icon: "bookmark.fill",       value: m.saves,
                              key: "detail.saves")
                    metricRow(icon: "eye.fill",            value: m.reach,
                              key: "detail.reach")
                }
            } else if carousel.isPublished {
                // Published but no metrics yet
                HStack(spacing: 8) {
                    Image(systemName: "clock.arrow.circlepath")
                        .font(.system(size: 13))
                        .foregroundStyle(Theme.muted)
                    Text(lang.t("detail.awaiting"))
                        .font(Theme.bodyFont)
                        .foregroundStyle(Theme.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }
            } else {
                // Not published
                HStack(spacing: 8) {
                    Image(systemName: "chart.bar.xaxis")
                        .font(.system(size: 13))
                        .foregroundStyle(Theme.muted.opacity(0.5))
                    Text(lang.t("detail.notPublished"))
                        .font(Theme.bodyFont)
                        .foregroundStyle(Theme.muted)
                }
            }
        }
    }

    private func metricRow(icon: String, value: Int?, key: String,
                           emphasize: Bool = false) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .font(.system(size: emphasize ? 15 : 12))
                .foregroundStyle(emphasize ? Theme.yellow : Theme.muted)
                .frame(width: 18, alignment: .center)

            // value
            Text(value.map { formatNumber($0) } ?? "—")
                .font(.system(size: emphasize ? 24 : 17,
                              weight: emphasize ? .bold : .semibold,
                              design: .rounded))
                .foregroundStyle(emphasize ? Theme.yellow : Theme.white)

            Text(lang.t(key))
                .font(.system(size: 11))
                .foregroundStyle(Theme.muted)

            Spacer()
        }
    }

    // MARK: - Critic verdict

    private var criticSection: some View {
        HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 4) {
                Text(lang.t("detail.critic"))
                    .font(.system(size: 11, weight: .bold))
                    .foregroundStyle(Theme.muted)
                    .textCase(.uppercase)
                Text(carousel.humanVerdict(lang))
                    .font(.system(size: 14, weight: .bold))
                    .foregroundStyle(verdictColor)
            }
            Spacer()
            // verdict icon badge
            Image(systemName: verdictIcon)
                .font(.system(size: 22))
                .foregroundStyle(verdictColor)
        }
    }

    private var verdictColor: Color {
        let v = (carousel.criticVerdict ?? "").lowercased()
        if v.contains("pass") { return Theme.green }
        if v.contains("fail") { return Theme.red }
        return Theme.muted
    }

    private var verdictIcon: String {
        let v = (carousel.criticVerdict ?? "").lowercased()
        if v.contains("pass") { return "checkmark.seal.fill" }
        if v.contains("fail") { return "xmark.seal.fill" }
        return "seal"
    }

    // MARK: - Publish controls

    @ViewBuilder private var publishControlsSection: some View {
        if carousel.isPublished {
            publishedControls
        } else if showPublishForm {
            publishForm
        } else {
            markPublishedButton
        }
    }

    // Already published: "Open on IG" + "Undo" control
    private var publishedControls: some View {
        VStack(alignment: .leading, spacing: 10) {
            // Published date chip
            if let date = carousel.publishedAt {
                HStack(spacing: 6) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 12))
                        .foregroundStyle(Theme.green)
                    Text(date.prefix(10))
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(Theme.green)
                }
            }
            HStack(spacing: 12) {
                // Open on Instagram
                if let urlString = carousel.instagramURL, let url = URL(string: urlString) {
                    Link(destination: url) {
                        Label(lang.t("detail.openIG"), systemImage: "arrow.up.right.square")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundStyle(.black)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 7)
                            .background(Capsule().fill(Theme.yellow))
                    }
                }
                Spacer()
                // Undo publish (reversible)
                Button(lang.t("detail.undo")) {
                    state.undoPublished(slug: carousel.slug)
                }
                .buttonStyle(.plain)
                .font(.system(size: 11))
                .foregroundStyle(Theme.muted)
            }
        }
    }

    // Inline publish form: text field + confirm button
    private var publishForm: some View {
        VStack(alignment: .leading, spacing: 10) {
            TextField(lang.t("detail.igLink"), text: $igLink)
                .textFieldStyle(.plain)
                .font(.system(size: 12))
                .foregroundStyle(Theme.white)
                .padding(10)
                .background(RoundedRectangle(cornerRadius: 8).fill(Theme.inkLift))
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .strokeBorder(Theme.hairline, lineWidth: 1)
                )

            HStack(spacing: 10) {
                Button(lang.t("detail.confirm")) {
                    let today = String(Self.isoDateFormatter.string(from: Date()).prefix(10))
                    state.markPublished(slug: carousel.slug, igURL: igLink, publishedAt: today)
                    showPublishForm = false
                    igLink = ""
                }
                .buttonStyle(.plain)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.black)
                .padding(.horizontal, 14)
                .padding(.vertical, 8)
                .background(Capsule().fill(igLink.trimmingCharacters(in: .whitespaces).isEmpty
                                           ? Theme.yellow.opacity(0.4) : Theme.yellow))
                .disabled(igLink.trimmingCharacters(in: .whitespaces).isEmpty)

                Button(lang.t("studio.cancel")) {
                    showPublishForm = false
                    igLink = ""
                }
                .buttonStyle(.plain)
                .font(.system(size: 12))
                .foregroundStyle(Theme.muted)
            }
        }
    }

    // Initial CTA: "Mark as published" button
    private var markPublishedButton: some View {
        // Waitlist actions: work on it in Zero Design, then publish.
        HStack(spacing: 10) {
            // Zero Design Studio — the in-house magic layer on the Mini. Per-slug deep-link
            // if the queue item carries one (future); otherwise opens the studio (single
            // current-project editor — no per-slug route, verified 2026-06-23).
            if let url = zeroDesignURL {
                Link(destination: url) {
                    Label(lang.t("detail.openDesign"), systemImage: "paintbrush.pointed.fill")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 9)
                        .background(Capsule().fill(Theme.blue))
                }
            }
            // Corrective re-run — revise this carousel in place with feedback, then re-render.
            Button {
                showReviseForm = true
            } label: {
                Label(lang.t("detail.revise"), systemImage: "arrow.triangle.2.circlepath")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 9)
                    .background(Capsule().fill(Theme.muted.opacity(0.35)))
            }
            .buttonStyle(.plain)
            .disabled(state.isRunning)
            .popover(isPresented: $showReviseForm, arrowEdge: .bottom) { reviseForm }

            // Fast local re-render — replay the production renderer from slides.json
            // (~2-3s, deterministic, no agent). For when the copy is already in shape
            // and you just want fresh PNGs without clicking Migliora and waiting.
            Button {
                state.reRenderCarousel(slug: carousel.slug, lang: lang)
            } label: {
                HStack(spacing: 6) {
                    if state.reRenderingSlug == carousel.slug {
                        ProgressView().controlSize(.small)
                    } else {
                        Image(systemName: "wand.and.stars")
                    }
                    Text(lang.t("detail.rerender"))
                }
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.white)
                .padding(.horizontal, 14)
                .padding(.vertical, 9)
                .background(Capsule().fill(Theme.muted.opacity(0.35)))
            }
            .buttonStyle(.plain)
            .disabled(state.isRunning || state.reRenderingSlug != nil)

            // Publish to Instagram — the carousel + caption go LIVE on @balizero0,
            // server-side via the Fly backend. LEGGE 5: a confirm popover gates it
            // (Verifica dry-run first, then an explicit "Pubblica ora"). Nothing
            // posts on the first click.
            Button {
                showPublishIGConfirm = true
                publishCaption = ""
                captionLoadError = nil
                captionIsLoading = true
                state.loadInstagramCaption(slug: carousel.slug) { result in
                    captionIsLoading = false
                    switch result {
                    case .success(let caption):
                        publishCaption = caption
                    case .failure(let error):
                        captionLoadError = error.localizedDescription
                    }
                }
            } label: {
                HStack(spacing: 6) {
                    if state.isPublishingSlug == carousel.slug {
                        ProgressView().controlSize(.small)
                    } else {
                        Image(systemName: "paperplane.fill")
                    }
                    Text(lang.t("detail.publishIG"))
                }
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.white)
                .padding(.horizontal, 14)
                .padding(.vertical, 9)
                .background(Capsule().fill(Theme.blue))
            }
            .buttonStyle(.plain)
            .disabled(state.isRunning || state.isPublishingSlug != nil)
            .popover(isPresented: $showPublishIGConfirm, arrowEdge: .bottom) { publishIGConfirm }

            Button {
                showPublishForm = true
            } label: {
                Label(lang.t("detail.markPublished"), systemImage: "checkmark.seal.fill")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(.black)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 9)
                    .background(Capsule().fill(Theme.green))
            }
            .buttonStyle(.plain)
        }
    }

    // Publish-to-IG confirm popover: dry-run check (safe) + explicit publish (Legge 5).
    private var publishIGConfirm: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(lang.t("detail.publishIGTitle"))
                .font(.system(size: 14, weight: .semibold))
            Text(lang.t("detail.publishIGInfo"))
                .font(.system(size: 12))
                .foregroundStyle(Theme.muted)
                .fixedSize(horizontal: false, vertical: true)

            Text(lang.t("detail.captionLabel"))
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(Theme.white)

            if captionIsLoading {
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text(lang.t("detail.captionLoading"))
                        .font(.system(size: 12))
                        .foregroundStyle(Theme.muted)
                }
                .frame(maxWidth: .infinity, minHeight: 180, alignment: .center)
            } else if let captionLoadError {
                Text(captionLoadError)
                    .font(.system(size: 12))
                    .foregroundStyle(Theme.red)
                    .frame(maxWidth: .infinity, minHeight: 100, alignment: .topLeading)
                    .padding(10)
                    .background(RoundedRectangle(cornerRadius: 8).fill(Theme.ink))
            } else {
                TextEditor(text: $publishCaption)
                    .font(.system(size: 12))
                    .foregroundStyle(Theme.white)
                    .scrollContentBackground(.hidden)
                    .padding(8)
                    .frame(height: 220)
                    .background(RoundedRectangle(cornerRadius: 8).fill(Theme.ink))
                    .overlay(
                        RoundedRectangle(cornerRadius: 8)
                            .strokeBorder(Theme.hairline, lineWidth: 1)
                    )

                HStack(spacing: 8) {
                    if publishCaption.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        Text(lang.t("detail.captionRequired"))
                            .foregroundStyle(Theme.red)
                    } else if InstagramCaption.characterCount(publishCaption) > InstagramCaption.maxLength {
                        Text(lang.t("detail.captionTooLong"))
                            .foregroundStyle(Theme.red)
                    }
                    Spacer()
                    Text("\(InstagramCaption.characterCount(publishCaption)) / \(InstagramCaption.maxLength)")
                        .foregroundStyle(
                            InstagramCaption.characterCount(publishCaption) > InstagramCaption.maxLength
                                ? Theme.red : Theme.muted
                        )
                }
                .font(.system(size: 11, weight: .semibold))
            }

            HStack(spacing: 10) {
                // Dry-run: exercises upload + backend validation, posts NOTHING.
                Button {
                    state.publishToInstagram(
                        slug: carousel.slug, caption: publishCaption, lang: lang, confirm: false
                    )
                } label: {
                    Text(lang.t("detail.publishIGCheck"))
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 14).padding(.vertical, 8)
                        .background(Capsule().fill(Theme.muted.opacity(0.35)))
                }
                .buttonStyle(.plain)
                .disabled(
                    captionIsLoading || captionLoadError != nil
                        || InstagramCaption.isPublishable(publishCaption) == false
                        || state.isPublishingSlug != nil
                )

                // The explicit operator publish click (confirm=true).
                Button {
                    showPublishIGConfirm = false
                    state.publishToInstagram(
                        slug: carousel.slug, caption: publishCaption, lang: lang, confirm: true
                    )
                } label: {
                    Text(lang.t("detail.publishIGConfirm"))
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 14).padding(.vertical, 8)
                        .background(Capsule().fill(Theme.blue))
                }
                .buttonStyle(.plain)
                .disabled(
                    captionIsLoading || captionLoadError != nil
                        || InstagramCaption.isPublishable(publishCaption) == false
                        || state.isPublishingSlug != nil
                )

                Button(lang.t("detail.publishIGCancel")) { showPublishIGConfirm = false }
                    .buttonStyle(.plain)
                    .font(.system(size: 12))
                    .foregroundStyle(Theme.muted)
            }
        }
        .padding(16)
        .frame(width: 520)
    }

    // Corrective re-run popover: a short feedback note, then launch the revise run.
    private var reviseForm: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(lang.t("detail.reviseTitle"))
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.white)
            TextField(lang.t("detail.revisePlaceholder"), text: $reviseFeedback, axis: .vertical)
                .lineLimit(2...5)
                .textFieldStyle(.roundedBorder)
                .frame(width: 320)
            HStack {
                Spacer()
                Button(lang.t("detail.reviseLaunch")) {
                    state.reviseCarousel(slug: carousel.slug, feedback: reviseFeedback)
                    reviseFeedback = ""
                    showReviseForm = false
                }
                .disabled(state.isRunning)
            }
        }
        .padding(14)
        .frame(width: 348)
    }

    /// Destination for "Apri in Zero Design": the item's own deep-link when present,
    /// else the Zero Design Studio root on the Mini (Theme.zeroDesignStudioURL).
    private var zeroDesignURL: URL? {
        if let canva = carousel.canvaURL, let url = URL(string: canva) { return url }
        return URL(string: Theme.zeroDesignStudioURL)
    }

    // MARK: - Helpers

    /// Human-friendly number: 1247 → "1 247", 18200 → "18 200"
    private func formatNumber(_ n: Int) -> String {
        return Self.numberFormatter.string(from: NSNumber(value: n)) ?? "\(n)"
    }

    private static let numberFormatter: NumberFormatter = {
        let f = NumberFormatter()
        f.numberStyle = .decimal
        f.groupingSeparator = " "
        f.usesGroupingSeparator = true
        return f
    }()

    private static let isoDateFormatter = ISO8601DateFormatter()
}
