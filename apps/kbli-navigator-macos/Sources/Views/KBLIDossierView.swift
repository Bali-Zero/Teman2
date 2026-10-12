import SwiftUI

/// "The Dossier" — the legal-document variant of the detail card, synthesised from the
/// independent Gemini 3.1 Pro and Claude Opus design panels (they converged): New York serif for
/// the title + verdict (a court "holding"), SF Mono for codes/regulations (registry precision),
/// hairlines instead of shadows (printed document, not app), an authority/Dasar-Hukum citation
/// apparatus, and a 3-column per-scale ledger. Fully bilingual via the CodeOverlay; OSS-rigor
/// authority fields surfaced for trust.
///
/// Two variants to compare on screen:
///   .gemini — austere, NO photo, pure typography + hairlines (Gemini's "printed statute")
///   .claude — keeps a calmed sector-photo "plate" band under a letterhead masthead (Claude's "Dossier")
struct KBLIDossierView: View {
    enum Variant { case gemini, claude }
    let kbli: KBLI
    var variant: Variant = .claude
    var scrolls: Bool = true
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    private let overlays = OverlayStore()

    private var ov: CodeOverlay? { overlays.overlay(kbli.kode, lang: lang.lang.rawValue) }

    var body: some View {
        if scrolls { ScrollView { content }.background(Theme.antracite) }
        else { content.background(Theme.antracite) }
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: 0) {
            // letterhead top rule (both variants) — the "legal document" signal
            Rectangle().fill(Theme.accent).frame(height: 2)
            VStack(alignment: .leading, spacing: 22) {
                masthead
                verdict
                if variant == .claude { photoPlate }   // Claude keeps the calmed photo band
                atAGlance
                section(lang.t("rich.meaning")) { serifProse(ov?.meaning ?? kbli.uraian) }
                authorityBlock
                licensingLedger
                // Gold-Tier "Bali context — reality check" NOT rendered in the app (Zero 2026-06-30):
                // too Bali-centric for the national/KBLI-first surface; prose kept in the overlay for the website.
                if let r = ov?.related, !r.isEmpty { relatedSection(r) }
                section(lang.t("rich.changed")) { serifProse(ov?.changed ?? "") }
                askZantara
                footerProvenance
                Spacer(minLength: 24)
            }
            .padding(.horizontal, 36).padding(.top, 24)
            .frame(maxWidth: 660, alignment: .leading)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    // MARK: masthead — KBLI label + mono code + serif title + authority sub-line

    private var masthead: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("KBLI 2025").font(Theme.scalable(11, weight: .semibold, design: .monospaced))
                .tracking(1.5).foregroundStyle(Theme.muted)
            HStack(alignment: .firstTextBaseline, spacing: 16) {
                Text(kbli.kode)
                    .font(Theme.scalable(44, weight: .medium, design: .monospaced))
                    .foregroundStyle(Theme.white)
                Spacer()
                badgeRow
            }
            Text(ov?.title ?? kbli.judul)
                .font(Theme.scalable(28, weight: .semibold, design: .serif))
                .foregroundStyle(Theme.white).fixedSize(horizontal: false, vertical: true)
            Text("\(lang.t("rich.fact.sector")) \(kbli.sektorId ?? "—")  ·  \(ov?.authority?.predecessor ?? "")")
                .font(Theme.scalable(12)).foregroundStyle(Theme.faint)
        }
    }

    private var badgeRow: some View {
        let status = kbli.l4Bali?.status ?? ""
        return HStack(spacing: 8) {
            StatusBadge(icon: "sparkle", label: lang.t("rich.gold"), tone: .neutral, compact: true)
            StatusBadge(icon: Theme.kbliStatusSymbol(status), label: Theme.kbliStatusLabel(status),
                        tone: Theme.tone(status), compact: true)
        }
    }

    // MARK: verdict — serif "holding" with a terracotta left margin-rule (no flood)

    private var verdict: some View {
        let blocked = kbli.l4Bali?.blocked == true
        let color = blocked ? Theme.pmaClosed : Theme.pmaOpen
        let headline = blocked ? lang.t("dossier.holding.blocked") : lang.t("dossier.holding.open")
        return HStack(alignment: .top, spacing: 0) {
            Rectangle().fill(color).frame(width: 4)
            VStack(alignment: .leading, spacing: 9) {
                Text((blocked ? lang.t("rich.verdict.blocked") : lang.t("rich.verdict.open")))
                    .font(Theme.scalable(11, weight: .bold)).tracking(1.2).foregroundStyle(color)
                Text(headline)
                    .font(Theme.scalable(22, weight: .semibold, design: .serif))
                    .foregroundStyle(Theme.white).fixedSize(horizontal: false, vertical: true)
                Text(ov?.verdict ?? kbli.l4Bali?.reason ?? "")
                    .font(Theme.scalable(15)).foregroundStyle(Theme.muted).lineSpacing(4)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(.vertical, 16).padding(.leading, 18).padding(.trailing, 16)
            Spacer(minLength: 0)
        }
        .background(RoundedRectangle(cornerRadius: variant == .gemini ? 2 : Theme.radiusMd).fill(color.opacity(0.07)))
    }

    // MARK: calmed photo plate (Claude variant only)

    private var photoPlate: some View {
        Group {
            if let n = SectorImage.name(for: kbli), let img = SectorImage.load(n) {
                Image(nsImage: img).resizable().aspectRatio(contentMode: .fill)
                    .frame(maxWidth: .infinity).frame(height: 140).clipped()
                    .saturation(0.85)
                    .overlay(alignment: .bottom) {
                        LinearGradient(colors: [.clear, Theme.antracite.opacity(0.35)], startPoint: .top, endPoint: .bottom)
                    }
                    .clipShape(RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: Theme.radiusMd).strokeBorder(Theme.hairline, lineWidth: 1))
            }
        }
    }

    // MARK: at-a-glance — mono ledger row (no colored mini-cards)

    /// Pure, headless-callable (`Tests/semantictest`) — the dossier's ownership cell. Before
    /// OPEN-1 (2026-09-17) this read the raw `pma_max_asing`/`pma_status` fields directly and
    /// could show a bare `"TERTUTUP"` beside a card whose registry ledger, reading the SAME
    /// record through `KBLIVerdict`, read `"Closed"` — two spellings of the same axis.
    static func ownershipLine(_ kbli: KBLI, isID: Bool) -> String {
        KBLIVerdict.of(record: kbli).ownershipLine(isID: isID)
    }

    private var atAGlance: some View {
        // PMA-relevant risk = the Besar (large) scale, since a PT PMA is Besar by law; else the
        // highest across scales. NOT `.first` (Mikro understates — the "Medium-Low restaurant"
        // trap). Read from the one reader (`Theme.RiskTier`): this was a second copy of that rule,
        // and copies are how the third one kept a default the others had already dropped.
        let risk = Theme.RiskTier.category(kbli.perSkala) ?? Theme.absent
        return HStack(alignment: .top, spacing: 0) {
            cell(lang.t("rich.fact.pma"), Self.ownershipLine(kbli, isID: lang.lang == .id))
            vrule
            cell(lang.t("rich.fact.risk"), risk, accent: Theme.riskColor(risk))
            vrule
            cell(lang.t("rich.fact.scales"), "\(kbli.perSkala.count)")
            vrule
            cell(lang.t("rich.fact.sector"), kbli.sektorId ?? Theme.absent)
        }
        .padding(.vertical, 14)
        .overlay(alignment: .top) { hrule }
        .overlay(alignment: .bottom) { hrule }
    }

    private func cell(_ label: String, _ value: String, accent: Color? = nil) -> some View {
        VStack(spacing: 5) {
            Text(value).font(Theme.scalable(20, weight: .semibold, design: .monospaced))
                .foregroundStyle(Theme.white).lineLimit(1).minimumScaleFactor(0.5)
                .overlay(alignment: .bottom) { if let a = accent { Rectangle().fill(a).frame(height: 2).offset(y: 5) } }
            Text(label.uppercased()).font(Theme.scalable(9, weight: .semibold)).tracking(0.8).foregroundStyle(Theme.faint)
        }.frame(maxWidth: .infinity)
    }

    // MARK: authority / Dasar Hukum — the trust apparatus (hairline-ruled citation rows)

    private var authorityBlock: some View {
        section(lang.t("dossier.authority")) {
            VStack(alignment: .leading, spacing: 14) {
                if let docs = ov?.authority?.dasarHukum, !docs.isEmpty {
                    citationGroup(lang.t("dossier.dasarhukum"), docs, binding: true)
                }
                if let auth = ov?.authority?.kewenangan, !auth.isEmpty {
                    citationGroup(lang.t("dossier.kewenangan"), auth, binding: false)
                }
                if let pb = ov?.authority?.pbUmku, !pb.isEmpty {
                    VStack(alignment: .leading, spacing: 6) {
                        groupLabel(lang.t("dossier.pbumku"))
                        FlowChips(items: pb, color: Theme.green)
                    }
                }
                if let reg = ov?.authority?.regulasi, !reg.isEmpty {
                    citationGroup(lang.t("dossier.regulasi"), reg, binding: false)
                }
                if let v = ov?.authority?.verified {
                    Text("\(lang.t("dossier.verified")) \(v)  ·  Bali Zero")
                        .font(Theme.scalable(11, design: .monospaced)).foregroundStyle(Theme.faint)
                }
            }
        }
    }

    private func citationGroup(_ label: String, _ items: [String], binding: Bool) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            groupLabel(label)
            ForEach(Array(items.enumerated()), id: \.offset) { _, item in
                HStack(alignment: .top, spacing: 8) {
                    if binding { Image(systemName: "checkmark.seal.fill").font(Theme.scalable(11)).foregroundStyle(Theme.green).padding(.top, 2) }
                    Text(item).font(Theme.scalable(13, design: .monospaced)).foregroundStyle(Theme.muted)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 0)
                }
            }
        }
    }

    private func groupLabel(_ s: String) -> some View {
        Text(s.uppercased()).font(Theme.scalable(10, weight: .bold)).tracking(1.2).foregroundStyle(Theme.zantara)
    }

    // MARK: per-scale licensing — 3 parallel columns (ledger)

    private var licensingLedger: some View {
        section(lang.t("rich.licensing")) {
            // Four columns is the ledger's width, not the record's: 407 codes declare more than
            // four scales and 71109 declares 112. Expanded, the extra scales wrap into further
            // rows of four — same column design, nothing hidden.
            ExpandableList(items: kbli.perSkala, limit: 4, isID: lang.lang == .id,
                           tint: Theme.zantara, spacing: 0) { shown in
                ForEach(Array(stride(from: 0, to: shown.count, by: 4)), id: \.self) { start in
                    HStack(alignment: .top, spacing: 0) {
                        ForEach(start..<min(start + 4, shown.count), id: \.self) { i in
                            if i > start { vrule }
                            scaleColumn(shown[i])
                        }
                        // keep the last row's columns the same width as a full row's
                        if shown.count - start < 4 {
                            ForEach(0..<(4 - (shown.count - start)), id: \.self) { _ in
                                Color.clear.frame(maxWidth: .infinity)
                            }
                        }
                    }
                    .padding(.vertical, 14)
                    .overlay(alignment: .top) { hrule }
                    .overlay(alignment: .bottom) { hrule }
                }
            }
        }
    }

    private func scaleColumn(_ ps: PerSkala) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(ps.skalaUsaha.joined(separator: " · "))
                .font(Theme.scalable(13, weight: .semibold)).foregroundStyle(Theme.white)
            if let r = ps.kategoriRisiko, !r.isEmpty {
                Text(r).font(Theme.scalable(11, weight: .semibold, design: .monospaced))
                    .foregroundStyle(Theme.riskColor(r))
                    .padding(.horizontal, 7).padding(.vertical, 3)
                    .background(Capsule().fill(Theme.riskColor(r).opacity(0.14)))
            }
            if let p = ps.perizinan, !p.isEmpty {
                Text(p).font(Theme.scalable(11)).foregroundStyle(Theme.faint).lineLimit(3)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 10)
    }

    // MARK: related codes

    private func relatedSection(_ items: [CodeOverlay.Related]) -> some View {
        section(lang.t("rich.related")) {
            VStack(spacing: 8) {
                ForEach(Array(items.enumerated()), id: \.offset) { _, it in
                    HStack(spacing: 12) {
                        Text(it.code).font(Theme.scalable(13, weight: .medium, design: .monospaced))
                            .foregroundStyle(Theme.zantara)
                            .padding(.horizontal, 8).padding(.vertical, 4)
                            .overlay(RoundedRectangle(cornerRadius: 4).strokeBorder(Theme.zantara.opacity(0.3), lineWidth: 1))
                        Text(it.note).font(Theme.scalable(13)).foregroundStyle(Theme.muted).lineLimit(2)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .padding(.vertical, 7)
                    .overlay(alignment: .bottom) { hrule.opacity(0.6) }
                }
            }
        }
    }

    private var askZantara: some View {
        Button { state.askZantara(about: kbli) } label: {
            HStack(spacing: 12) {
                Image(systemName: "sparkles").foregroundStyle(Theme.zantara).font(Theme.scalable(15, weight: .semibold))
                Text(lang.t("rich.cta.title")).font(Theme.scalable(14, weight: .semibold)).foregroundStyle(Theme.white)
                Spacer()
                Image(systemName: "arrow.right").font(Theme.scalable(12, weight: .bold)).foregroundStyle(Theme.zantara)
            }
            .padding(15)
            .overlay(RoundedRectangle(cornerRadius: Theme.radiusMd).strokeBorder(Theme.zantara.opacity(0.25), lineWidth: 1))
        }.buttonStyle(.plain)
    }

    private var footerProvenance: some View {
        Text("Bali Zero · KBLI 2025 · \(ov?.authority?.verified ?? "")")
            .font(Theme.scalable(10, design: .monospaced)).foregroundStyle(Theme.faint)
            .padding(.top, 4)
    }

    // MARK: building blocks — the marginal-rule grammar (hairline under every section title)

    @ViewBuilder private func section<C: View>(_ title: String, @ViewBuilder _ inner: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 7) {
                Text(title.uppercased()).font(Theme.scalable(12, weight: .semibold)).tracking(1.0).foregroundStyle(Theme.muted)
                hrule
            }
            inner()
        }
    }

    private func serifProse(_ s: String) -> some View {
        Text(s).font(Theme.scalable(15, design: .serif)).foregroundStyle(Theme.muted).lineSpacing(5)
            .fixedSize(horizontal: false, vertical: true)
    }

    private var hrule: some View { Rectangle().fill(Theme.hairline).frame(height: 1) }
    private var vrule: some View { Rectangle().fill(Theme.hairline).frame(width: 1).frame(maxHeight: 44) }
}

/// A simple wrapping chip row (PB UMKU licenses), sage-outlined.
struct FlowChips: View {
    let items: [String]
    var color: Color
    var body: some View {
        // single-column stack of chips (robust off-screen; real wrapping not needed for ≤5 items)
        VStack(alignment: .leading, spacing: 6) {
            ForEach(Array(items.enumerated()), id: \.offset) { _, it in
                Text(it).font(Theme.scalable(12)).foregroundStyle(color)
                    .padding(.horizontal, 9).padding(.vertical, 4)
                    .overlay(Capsule().strokeBorder(color.opacity(0.35), lineWidth: 1))
            }
        }
    }
}
