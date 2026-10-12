import SwiftUI

/// Pure, testable logic for the detail view (no SwiftUI) — kept separate so the unit test
/// can exercise the moratorium gating without rendering.
enum KBLIDetail {
    /// Show the amber moratorium callout ONLY when the code is actually blocked — every record
    /// carries the moratorium facts, but surfacing them on an OPEN code is misleading (the alert
    /// would cry wolf). Gate on `blocked`, not on the mere presence of moratorium data.
    static func shouldShowMoratorium(_ l4: L4Bali?) -> Bool {
        l4?.blocked == true
    }

    /// One-line moratorium summary: rule + effective date + source.
    static func moratoriumText(_ l4: L4Bali?) -> String {
        guard let m = l4?.moratorium else { return l4?.reason ?? "" }
        var parts: [String] = []
        if let r = m.rule { parts.append(r) }
        if let e = m.effective { parts.append("eff. \(e)") }
        if let s = m.source { parts.append(s) }
        return parts.joined(separator: " · ")
    }
}

/// The editorial KBLI code card, redesigned to match balizero.com/kbli-navigator ("Claude Night"):
/// a hero block (soft-tint status badge + big rounded code + title) on the dark base, optional
/// amber moratorium callout, scope as discrete card-rows, then per-scale licensing depth cards.
/// Sections separated by whitespace + depth, never divider rules (Dictionary/Bear lesson).
struct KBLIDetailView: View {
    let kbli: KBLI
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                hero
                if KBLIDetail.shouldShowMoratorium(kbli.l4Bali) { moratoriumCallout }
                if kbli.uraian.isEmpty == false { uraianSection }
                if kbli.ruangLingkup.isEmpty == false { scopeSection }
                if kbli.perSkala.isEmpty == false { licensingSection }
                Spacer(minLength: 16)
            }
            .padding(28)
            .frame(maxWidth: 820, alignment: .leading)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(Theme.antracite)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button { state.askZantara(about: kbli) } label: {
                    Label(lang.t("detail.ask"), systemImage: "bubble.left.and.bubble.right")
                }
                .tint(Theme.zantara)
            }
        }
    }

    // MARK: hero (status badge + big code + title + national PMA)

    private var hero: some View {
        let status = kbli.l4Bali?.status ?? ""
        return VStack(alignment: .leading, spacing: 14) {
            // status + national PMA badges, soft-tinted (the real PMABadge pattern)
            HStack(spacing: 8) {
                StatusBadge(icon: Theme.kbliStatusSymbol(status),
                            label: Theme.kbliStatusLabel(status),
                            tone: Theme.tone(status))
                if let pma = kbli.pmaStatus, pma.isEmpty == false {
                    StatusBadge(icon: "globe.asia.australia",
                                label: lang.t("detail.national") + " " + pma,
                                tone: .neutral)
                }
            }
            // big rounded code (premium figure)
            Text(kbli.kode)
                .font(Theme.scalable(46, weight: .bold, design: .rounded))
                .foregroundStyle(Theme.white)
                .tracking(0.5)
            Text(kbli.judul)
                .font(Theme.titleFont)
                .foregroundStyle(Theme.white)
                .fixedSize(horizontal: false, vertical: true)
            FactRule(width: 54)
        }
    }

    // MARK: moratorium callout (amber, soft-tint card)

    private var moratoriumCallout: some View {
        HStack(alignment: .top, spacing: 13) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(Theme.yellow).font(Theme.scalable(18))
            VStack(alignment: .leading, spacing: 6) {
                Text(lang.t("detail.moratorium")).font(Theme.headingFont).foregroundStyle(Theme.white)
                if let reason = kbli.l4Bali?.reason, reason.isEmpty == false {
                    Text(reason).font(Theme.bodyFont).foregroundStyle(Theme.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }
                let m = KBLIDetail.moratoriumText(kbli.l4Bali)
                if m.isEmpty == false {
                    Text(m).font(Theme.scalable(12)).foregroundStyle(Theme.faint)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            Spacer(minLength: 0)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: Theme.radiusLg, style: .continuous)
                .fill(Theme.yellow.opacity(0.10))
        )
        .overlay(
            RoundedRectangle(cornerRadius: Theme.radiusLg, style: .continuous)
                .strokeBorder(Theme.yellow.opacity(0.20), lineWidth: 1)
        )
    }

    // MARK: uraian (description)

    private var uraianSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            sectionLabel(lang.t("detail.description"))
            GlassCard(padding: 18, hoverable: false) {
                Text(kbli.uraian.replacingOccurrences(of: "\n", with: " "))
                    .font(Theme.bodyFont).foregroundStyle(Theme.muted)
                    .lineSpacing(4)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }

    // MARK: scope (ruang_lingkup) — discrete card-rows (the .kbli-prose li pattern)

    private var scopeSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            sectionLabel(lang.t("detail.scope"))
            // 20 is the card's comfortable height, not the scope's length: 71109 declares 29
            // activities and 26601 declares 24. The rest are one click away, not dropped.
            ExpandableList(items: kbli.ruangLingkup, limit: 20, isID: lang.lang == .id,
                           tint: Theme.accent, spacing: 6) { shown in
                ForEach(Array(shown.enumerated()), id: \.offset) { _, s in
                    cardRow(s)
                }
            }
        }
    }

    /// A single scope item as a surface card-row with a small terracotta square bullet
    /// (mirrors `.kbli-prose ul li` + `::before` from the web).
    private func cardRow(_ text: String) -> some View {
        // Replicates `.kbli-prose ul li` (padding 10/16/10/28) + `::before` (5px square accent
        // bullet at left:12, top:18). HStack spacing 11 takes the 5px bullet from leading-12 to a
        // ~28px text start; top padding 8 ≈ the 18px-from-top bullet baseline. (Review #4.)
        HStack(alignment: .top, spacing: 11) {
            RoundedRectangle(cornerRadius: 2)
                .fill(Theme.accent.opacity(0.6))
                .frame(width: 5, height: 5)
                .padding(.top, 8)
            Text(text).font(Theme.scalable(13)).foregroundStyle(Theme.muted)
                .lineSpacing(3)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.leading, 12).padding(.trailing, 16).padding(.vertical, 10)
        .background(
            RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous)
                .fill(Theme.inkLift)
        )
    }

    // MARK: per-scale licensing (depth cards with big stats + risk badge)

    private var licensingSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionLabel(lang.t("detail.licensing"))
            ForEach(Array(kbli.perSkala.enumerated()), id: \.offset) { _, ps in
                GlassCard(padding: 18) {
                    VStack(alignment: .leading, spacing: 14) {
                        HStack(alignment: .top) {
                            Text(ps.skalaUsaha.joined(separator: " · "))
                                .font(Theme.scalable(14, weight: .semibold)).foregroundStyle(Theme.white)
                            Spacer()
                            if let risk = ps.kategoriRisiko, risk.isEmpty == false {
                                StatusBadge(icon: "gauge.medium", label: risk,
                                            risk: risk, compact: true)
                            }
                        }
                        // big premium stats row (permit + processing time)
                        // Permit/authority live as ARRAYS (perizinanList / kewenanganLevels) on ~1338
                        // of 1457 records; the legacy scalar `perizinan`/`kewenangan` is empty for them.
                        // Reading only the scalar showed a BLANK permit/authority on the majority of
                        // codes. Prefer the scalar when present, else join the distinct array entries.
                        HStack(alignment: .top, spacing: 28) {
                            if let p = permitText(ps) {
                                PremiumStat(label: lang.t("detail.permit"), value: p, color: Theme.accent)
                            }
                            if let j = ps.jangkaWaktu, j.isEmpty == false {
                                PremiumStat(label: lang.t("detail.term"),
                                            value: PP28ScalePanel.formatJangkaWaktu(j, isID: lang.lang == .id))
                            }
                        }
                        if ps.kewajiban.isEmpty == false {
                            VStack(alignment: .leading, spacing: 5) {
                                Text(lang.t("detail.duties").uppercased())
                                    .font(Theme.scalable(10, weight: .semibold)).tracking(1.0)
                                    .foregroundStyle(Theme.faint)
                                // post-licence obligations: 1090 scale rows carry more than 8,
                                // 05101 carries 34. Stopping at 8 without saying so read as
                                // "these are all of them".
                                ExpandableList(items: ps.kewajiban, limit: 8, isID: lang.lang == .id,
                                               tint: Theme.accent, spacing: 5) { shown in
                                    ForEach(Array(shown.enumerated()), id: \.offset) { _, d in
                                        HStack(alignment: .top, spacing: 8) {
                                            Image(systemName: "checkmark")
                                                .font(Theme.scalable(9, weight: .bold))
                                                .foregroundStyle(Theme.accent.opacity(0.7)).padding(.top, 3)
                                            Text(d).font(Theme.scalable(12)).foregroundStyle(Theme.muted)
                                                .frame(maxWidth: .infinity, alignment: .leading)
                                        }
                                    }
                                }
                            }
                        }
                        if let auth = authorityText(ps) {
                            kv(lang.t("detail.authority"), auth)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
    }

    /// Permit/license text for a scale row. Prefer the explicit data (scalar `perizinan`, else the
    /// distinct `perizinanList[]` entries). When BOTH are empty (~1338 codes), DERIVE the license
    /// from this row's risk class — PP 28/2025 Pasal 124(4): the risk tier determines the license
    /// type (Rendah→NIB, Men→NIB+SS, Tinggi→NIB+Izin; verified NB-3). A flat "—"/blank understated
    /// the requirement on high-risk codes.
    private func permitText(_ ps: PerSkala) -> String? {
        if let p = ps.perizinan, !p.isEmpty { return p }
        let distinct = Array(NSOrderedSet(array: ps.perizinanList)).compactMap { $0 as? String }
        let joined = distinct.joined(separator: " · ")
        if !joined.isEmpty { return joined }
        if let risk = ps.kategoriRisiko, !risk.isEmpty {
            let derived = Theme.RiskTier.licence(tier: risk, isID: lang.lang == .id)
            return derived == Theme.absent ? nil : derived
        }
        return nil
    }

    /// Authority text for a scale row, same scalar-then-array fallback as permitText. The data's
    /// `kewenanganLevels[]` carries the real authority tiers (Menteri/Gubernur/BupID) the legacy
    /// scalar `kewenangan` left empty on the array-form majority.
    private func authorityText(_ ps: PerSkala) -> String? {
        if let a = ps.kewenangan, !a.isEmpty { return a }
        let distinct = Array(NSOrderedSet(array: ps.kewenanganLevels)).compactMap { $0 as? String }
        let joined = distinct.joined(separator: " · ")
        return joined.isEmpty ? nil : joined
    }

    private func kv(_ k: String, _ v: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(k.uppercased()).font(Theme.scalable(10, weight: .semibold)).tracking(1.0).foregroundStyle(Theme.faint)
            Text(v).font(Theme.scalable(12)).foregroundStyle(Theme.muted)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func sectionLabel(_ t: String) -> some View {
        Text(t.uppercased()).font(Theme.scalable(11, weight: .bold)).tracking(1.4).foregroundStyle(Theme.faint)
    }
}
