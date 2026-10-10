import AppKit
import SwiftUI

/// Variant D — "Registry Dossier" (2026-06-24). The authoritative card synthesised from two
/// independent design panels (Gemini 3.1 Pro High via agy + Claude Opus effort-max) that converged
/// on the SAME aesthetic: a *warm-paper regulatory dossier*. The website's 14-section richness
/// survives, recast as a printed registry on ivory stock — not the website's dark marketing page,
/// not a cold statute.
///
/// THE SIGNATURE MOVE is the `LedgerPlate`: a mono UPPERCASE label ↔ value table with a 3pt colored
/// left-rail, hairline row separators, white #FFF floated on the ivory #F6F3EC body. The SAME plate
/// grammar is applied to every authoritative block (license, authority, PP28, TKA, pricing) — the
/// relentless repetition of one table motif is what reads "official register".
///
/// Type system used AS A SYSTEM (never decoration): New York serif (`.serif`) → titles + H2 +
/// card titles; SF Mono (`.monospaced`) → every code/number/price/date/ISCO/risk-value; SF default
/// → all prose + chrome. Periwinkle is reserved EXCLUSIVELY for Zantara.
struct KBLIRegistryView: View {
    let kbli: KBLI
    /// When false (snapshot), the outer `ScrollView` is dropped so an off-screen host can capture
    /// the full height in one bitmap (mirrors the dossier/rich snapshot convention).
    var scrolls: Bool = true
    /// ONE-VERDICT CONTRACT (K2 2026-09-14). When false, the card is embedded under
    /// `RegistryVerdictSheet`, which has ALREADY stated identity, verdict and the three axes, and
    /// the card renders NO verdict-bearing element of its own. The enumerated set, each gated on
    /// this flag: the hero plate, the verdict banner, the facts row (Bali verdict / risk class /
    /// national cap / renumber), the restriction tags and the risk pill of the pill strip, and the
    /// Zantara opener in the footer (curated overlay prose that can state a verdict). What stays is
    /// what the sheet does not say: description, licensing, PP 28 matrix, roadmap, references,
    /// related codes, legal basis. Two council rounds each found one more surface of the card
    /// arguing with the sheet; the cure is this closed list, not a fourth patch.
    /// Default true: the card on its own (snapshots) is unchanged.
    var showsIdentityAndVerdict: Bool = true

    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    private let overlays = OverlayStore()

    private var ov: CodeOverlay? { overlays.overlay(kbli.kode, lang: lang.lang.rawValue) }
    /// Strict-language overlay for PROSE fields — nil in ID for the 321 EN-only curated codes,
    /// so the card falls back to the native-Indonesian dataset text instead of English prose.
    private var ovStrict: CodeOverlay? { overlays.overlayStrict(kbli.kode, lang: lang.lang.rawValue) }
    private var isID: Bool { lang.lang == .id }

    var body: some View {
        Group {
            if scrolls {
                ScrollView { content.padding(.bottom, 40) }
            } else {
                content
            }
        }
        .background(Theme.antracite)
    }

    @ViewBuilder private var content: some View {
        if showsIdentityAndVerdict {
            // §4: the full ledger holds from 1040 pt (120 + 360 + 400 + two 40 gutters + 80 padding).
            // ViewThatFits reads ideal widths, and unwrapped text has none worth reading: the wide page
            // states its own (the §4 threshold) so the choice is the pane width against 1040.
            ViewThatFits(in: .horizontal) {
                page(wide: true).frame(minWidth: Self.fullFrom, idealWidth: Self.fullFrom, maxWidth: .infinity)
                page(wide: false)
            }
        } else {
            // Embedded under `RegistryVerdictSheet` (its only caller until the route lands, §3.7):
            // the sheet states identity and verdict, so the card keeps the plain column.
            VStack(alignment: .leading, spacing: 32) {
                sections.padding(.horizontal, PAD)
                footer(leading: PAD)
            }
            .frame(maxWidth: WIDTH, alignment: .leading)
            .frame(maxWidth: .infinity, alignment: .center)
        }
    }

    private static let fullFrom: CGFloat = 1040
    private let WIDTH: CGFloat = 760
    private let PAD: CGFloat = 28

    /// §3.5: the top grid, then everything that was below the hero, in the middle+right span.
    private func page(wide: Bool) -> some View {
        VStack(alignment: .leading, spacing: 32) {
            topGrid(wide: wide).padding(.top, 24).padding(.leading, 32).padding(.trailing, 48)
            VStack(alignment: .leading, spacing: 32) {
                factsRow   // Z-7: the stat cards stay, below the fold
                sections
            }
            .padding(.leading, wide ? 32 + 120 + 40 : 32).padding(.trailing, 48)
            footer(leading: wide ? 32 + 120 + 40 : 32)
        }
    }

    /// pillStrip … footer keep their content (§3.5 "below the fold"); the footer is laid out by the caller.
    private var sections: some View {
        VStack(alignment: .leading, spacing: 32) {
            pillStrip                 // carries the No-PMA tags (the exception flags)
            description
            licensing
            // Gold-Tier "Bali context — reality check" intentionally NOT rendered in the app
            // (Zero 2026-06-30): the prose stays in kbli-overlay.json `baliContext` for the website.
            pp28
            roadmap
            referenceDrawer
            relatedGrid
            authorityPlate            // Legal Basis → bottom (Zero 2026-06-30, unchanged)
            // BKPM variant strips every link to balizero.com (Zero's ruling): readGuide opens one.
            if AppVariant.current.showsExternalLinks { readGuide }
        }
    }

    // MARK: 1 · TOP GRID (§3.5, set A "ledger with gutter mark")
    //
    // Columns 120 · flexible · 400, gutter 40. Column 1 is the PadiLadder, its ground line sharing the
    // matrix's last rule (D11). Column 2: code, titles, the risk × scale matrix (D1), the heads-up
    // block (D2). Column 3: the verdict stack (D3) — national figure first, Bali a labelled second
    // layer with its reason (D4). Then the basis across all three columns (D4, 4 BalancedColumns).
    // Below 1040 pt the ladder becomes a PadiLine above the title and the stack follows the rows (§4).
    private func topGrid(wide: Bool) -> some View {
        VStack(alignment: .leading, spacing: 32) {
            if wide {
                HStack(alignment: .top, spacing: 40) {
                    VStack(alignment: .leading, spacing: 24) {
                        Grid(alignment: .topLeading, horizontalSpacing: 40, verticalSpacing: 24) {
                            GridRow { Color.clear.frame(width: 120, height: 0); identity }
                            GridRow(alignment: .bottom) {
                                // The ladder hangs from the row's bottom edge, so its ground line (y 326
                                // of 330) sits on the matrix's last 1 pt rule and it rises above a short table.
                                Color.clear.frame(width: 120, height: 1)
                                    .overlay(alignment: .bottom) { PadiLadder().offset(y: 3.5) }
                                matrix
                            }
                        }
                        headsUp.padding(.leading, 120 + 40)
                    }
                    verdictStack.frame(width: 400)
                }
            } else {
                VStack(alignment: .leading, spacing: 24) {
                    PadiLine(width: 240)
                    identity
                    matrix
                    headsUp
                    verdictStack
                }
            }
            basisRow(columns: wide ? 4 : 2)
        }
    }

    private var identity: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("KBLI \(kbli.kode)").font(Theme.scalable(11, weight: .semibold)).tracking(0.88)
                .foregroundStyle(Theme.muted)
            Text(LabelBook.title(kbli, isID: isID)).font(Theme.title(27)).foregroundStyle(Theme.white)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityAddTraits(.isHeader)   // D3b — the card's own top-level title
            VStack(alignment: .leading, spacing: 2) {
                // Q12 ruling 3: under an English title the official Indonesian one says what it is.
                if !isID {
                    Text(LabelBook.officialTitleLabel).font(Theme.scalable(11)).foregroundStyle(Theme.muted)
                }
                Text(isID ? secondaryTitle : LabelBook.officialTitle(kbli))
                    .font(Theme.scalable(15)).foregroundStyle(Theme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Text(sectorLine).font(Theme.scalable(11)).foregroundStyle(Theme.muted)
        }
    }

    private var matrix: some View {
        ScaleMatrix(scales: kbli.perSkala, isID: isID, mode: .ledger)
    }

    private var headsUp: some View { HeadsUpBlock(KBLIVerdict.headsUp(record: kbli, isID: isID)) }

    /// D3: `detail.national` → status chip → cap → rule → `detail.bali` → Bali chip → reason.
    private var verdictStack: some View {
        let v = KBLIVerdict.of(record: kbli)
        let tone = Theme.chip(Theme.tone(kbli.pmaStatus ?? ""))
        return VStack(alignment: .leading, spacing: 8) {
            Text(lang.t("detail.national")).font(Theme.scalable(11, weight: .semibold)).foregroundStyle(Theme.muted)
            chip(LabelBook.pmaStatus(kbli.pmaStatus, isID: isID), tone)
            // The canonical `pma_max_asing` (the search peak's rule): "—" only when the record has none.
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(kbli.pmaMaxAsing.map { "\($0)%" } ?? "—").font(Theme.display(64)).monospacedDigit()
                    .foregroundStyle(Theme.white)
                Text(lang.t("rich.fact.pma")).font(Theme.scalable(11)).foregroundStyle(Theme.muted)
            }
            Rectangle().fill(Theme.lineSoft).frame(height: 1).padding(.vertical, 8)
            Text(lang.t("detail.bali")).font(Theme.scalable(11, weight: .semibold)).foregroundStyle(Theme.muted)
            let bali = LabelBook.baliChip(v, isID: isID)
            chip(bali.word, Theme.chip(bali.tone)).accessibilityLabel(bali.voiceOver)
            if let reason = verdictSubtitle(v) {
                LeadBody(text: LabelBook.humanise(reason, record: kbli, isID: isID), kind: .reason).padding(.top, 4)
            }
            if case .undetermined = v.bali {
                Text(isID
                     ? "Tidak ada verdikt yang dapat dinyatakan dari catatan ini — jangan diperlakukan sebagai terbuka maupun tertutup."
                     : "No verdict can be stated from these records — do not read this as open or as closed.")
                    .font(Theme.scalable(13)).lineSpacing(Theme.leading(13, 20)).foregroundStyle(Theme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            // D12: confidence is metadata under the answer, with no separator left dangling.
            if let c = confidenceLabel(kbli.l4Bali?.confidence) {
                Text(c).font(Theme.scalable(11)).foregroundStyle(Theme.muted)
            }
        }
        .padding(24)
        .frame(minHeight: 200, alignment: .topLeading)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.inkLift, in: RoundedRectangle(cornerRadius: 2))
        .overlay(RoundedRectangle(cornerRadius: 2).strokeBorder(Theme.lineSoft, lineWidth: 1))
    }

    private func chip(_ word: String, _ c: (fg: Color, bg: Color)) -> some View {
        Text(word).font(Theme.scalable(11, weight: .semibold)).foregroundStyle(c.fg)
            .padding(.vertical, 4).padding(.horizontal, 8)
            .background(c.bg, in: RoundedRectangle(cornerRadius: 2))
    }

    /// The legal basis across the three columns (§3.5 full-width row, D4): citation lead, then the body
    /// in BalancedColumns.
    @ViewBuilder private func basisRow(columns: Int) -> some View {
        if let basis = kbli.pmaOfficialBasis, !basis.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                Rectangle().fill(Theme.structure).frame(height: 2)
                BasisBlock(basis: basis, isID: isID, columns: columns)
            }
        }
    }

    private var sectorLine: String {
        // Dynamic per KBLI category (was hardcoded to "Section I - Accommodation"). The leading
        // "Section X" letter is the KBLI category; the name is localized.
        guard let cat = SectorImage.category(for: kbli.kode) else {
            return isID ? "Klasifikasi Baku Lapangan Usaha Indonesia" : "Indonesian Standard Business Classification"
        }
        let label = isID ? "Bagian" : "Section"
        return "\(label) \(cat) \u{2014} \(SectorImage.categoryName(cat, isID: isID))"
    }

    /// The PRIMARY (big serif) title in the active language. ID → curated overlay title or the raw
    /// Indonesian `judul`. EN → curated overlay title, else the army-translated `judul` (so a
    /// non-curated code is NOT macaronic), else the raw `judul` as a last resort.
    private var primaryTitle: String {
        if isID {
            return ovStrict?.title ?? kbli.judul
        }
        // EN: prefer the curated overlay title — BUT 310/322 curated codes left `en.title` as the raw
        // Indonesian `judul`. So if the overlay title is missing OR equals the Indonesian judul, fall
        // through to the army-translated dataString (English), never showing Indonesian in the EN card.
        if let t = ov?.title, t.trimmingCharacters(in: .whitespaces) != kbli.judul.trimmingCharacters(in: .whitespaces) {
            return t
        }
        return overlays.dataString(kbli.judul, isID: false)
    }

    /// The secondary (italic) title in Indonesian = the English name: the English overlay title, else the
    /// army-translated `judul`. (In English the line is `LabelBook.officialTitle`, under its label.)
    private var secondaryTitle: String {
        OverlayStore.shared.overlay(kbli.kode, lang: "en")?.title ?? OverlayStore.shared.dataString(kbli.judul, isID: false)
    }

    // MARK: 2 · VERDICT PILL STRIP — the 2-second scan
    private var pillStrip: some View {
        FlowPills(pills: verdictPills)
    }

    private var verdictPills: [PillSpec] {
        // The full Bali verdict lives in the top grid's verdict stack (§3.5, D3). The
        // pills are SUPPORTING EVIDENCE: the PMA restriction TAGS (the exceptions) + national
        // reference / risk / renumber. A KBLI is open by default; the tags flag who is restricted.
        var out: [PillSpec] = []
        // K2 council round 1 (both seats): the tags re-derived closure from raw fields, so a 0%-cap
        // closure got no tag and an undetermined record got nothing to say so. They now read the
        // rule; the CHIUSO_PMA_NO_BESAR wording below is kept as the record's own allocation label.
        let axes = VerdictAxes(KBLIVerdict.of(record: kbli))
        let baliBlocked = axes.baliBlocked

        // --- PMA restriction TAGS (Zero 2026-06-30) — derived from PURE fields, two distinct axes ---
        // 🔴 national-structural: a PT PMA can NEVER register this code anywhere in Indonesia
        //    (TERTUTUP = closed to foreign capital, or CHIUSO_PMA_NO_BESAR = allocated to
        //    Koperasi/UMKM by Perpres 10/2021 jo. 49/2021 Lampiran II — corrected 2026-08-03).
        let l4status = kbli.l4Bali?.status ?? ""
        let capSpecial = kbli.pmaCapSpecial == true
        let nationallyClosedPMA = axes.nationallyClosed
            || (!capSpecial && l4status == "CHIUSO_PMA_NO_BESAR")
        // 🟠 Bali-provincial: nationally open, but the 13 May 2026 moratorium blocks a NEW PMA in Bali
        //    (low / medium-low risk). Affects ONLY a PMA, ONLY in Bali — locals (PMDN/CV/WNI) are free.
        let blockedInBaliOnly = baliBlocked && !nationallyClosedPMA
        if showsIdentityAndVerdict == false {
            // One-verdict contract: the sheet above states the axes; no tag argues with it.
        } else if nationallyClosedPMA {
            out.append(PillSpec(text: isID ? "PMA: tertutup (nasional)" : "PMA: closed (national)",
                                color: Theme.pmaClosed))
        } else if blockedInBaliOnly {
            out.append(PillSpec(text: isID ? "PMA: diblokir di Bali" : "PMA: blocked in Bali",
                                color: Theme.pmaRestricted))
        } else if axes.anyUndetermined {
            out.append(PillSpec(text: isID ? "PMA: tidak ditentukan" : "PMA: not determined",
                                color: Theme.faint))
        }
        // NOTE: the "National (reference): N%" pill was removed (Zero 2026-06-30) — a bare statutory
        // cap up top was ambiguous (a "100%" sitting next to a red "PMA: closed" tag reads as a
        // contradiction, and it is theory not an action). The foreign-ownership % still lives in the
        // Licensing table (FOREIGN OWNERSHIP) and the Authority plate, where it has context.

        // risk — show the PMA-relevant scale (Besar) when present, else the highest across scales.
        // NOT `.first` (Mikro), which understates risk for a PT PMA (the "Medium-Low restaurant" trap).
        if showsIdentityAndVerdict, let risk = pmaRiskCategory() {
            out.append(PillSpec(text: riskLabel(risk), color: Theme.riskColor(risk)))
        }
        // renumber
        if kbli.isRenumbered, let prev = kbli.kbli2020Source {
            out.append(PillSpec(text: isID ? "Dinomori \(prev)→\(kbli.kode)" : "Renumbered \(prev)→\(kbli.kode)", color: Theme.statutory))
        }
        return out
    }

    /// `KBLIVerdict` is language-free by design: its reasons are English strings meant for a
    /// machine-readable package. Concatenating one into an Indonesian sentence produced
    /// half-translated prose on a regulator-facing card (council round 3, codex-gpt-5.6-sol), so
    /// in Indonesian the rule's sentence is QUOTED and labelled as such instead of being blended in.
    /// The record's own `l4_bali.reason`, translated where `kbli-reason-i18n` has it and QUOTED
    /// with a label where it does not — never blended untranslated into an Indonesian card.
    private func recordReason(_ r: String) -> String { OverlayStore.shared.displayReason(r, isID: isID) }

    private func quotedRuleReason(_ r: String?) -> String? {
        guard let r, r.isEmpty == false else { return nil }
        return isID ? "Kutipan aturan (EN): \(r)" : r
    }

    /// The explaining sentence under the headline. Order matters and is unchanged from D2.1: the
    /// CURED per-code reason wins when there is one (it carries a real citation for THIS code),
    /// then the rule's own reason, then the template generated from the structured status.
    private func verdictSubtitle(_ v: KBLIVerdict) -> String? {
        let l4 = kbli.l4Bali
        switch v.headline {
        case .nationallyClosed:
            // The rule's own reason names WHICH closure this is (TERTUTUP, a 0% cap, a cap with a
            // condition). The previous sentence asserted "reserved for Indonesian nationals /
            // public bodies" on every one of them — a fact the verdict does not carry for a 0%-cap
            // record (council round 2, codex-gpt-5.6-sol). The one thing true of all of them is
            // that the Bali moratorium cannot apply to something already closed nationwide.
            let tail = isID ? "Moratorium Bali tidak relevan untuk kode yang sudah tertutup secara nasional."
                            : "The Bali moratorium does not apply to a code already closed nationwide."
            guard let quoted = quotedRuleReason(v.headlineReason) else { return tail }
            return isID ? "\(tail) \(quoted)" : "\(quoted) \(tail)"
        case .baliBlocked:
            if let reason = l4?.reason, reason.isEmpty == false {
                return recordReason(reason)
            }
            if let generated = OverlayStore.generatedReason(status: l4?.status ?? "", isID: isID) {
                return generated
            }
            return quotedRuleReason(v.headlineReason)
        case .nationalUndetermined:
            return quotedRuleReason(v.headlineReason)
        case .baliUndetermined:
            // Prefer the CURED per-code reason when the record carries one: `reasonString` has
            // an Indonesian rendering for it, which the rule's own sentence never will.
            if let reason = l4?.reason, reason.isEmpty == false {
                return recordReason(reason)
            }
            return quotedRuleReason(v.headlineReason)
        case .openInBali:
            if l4?.status == "BLOCCATO_DIPENDE_SCOPE" {
                // SCOPE-DEPENDENT and blocked=false: the code IS registrable (by declaring the
                // higher-risk scope). The "BLOCCATO_*" status name would say "blocked",
                // contradicting the open headline. Show the truthful caveat.
                return isID
                    ? "Terbuka untuk PT PMA, tetapi tergantung scope: beberapa scope berisiko lebih tinggi pada skala Besar — daftarkan dengan memilih scope berisiko lebih tinggi."
                    : "Open to a PT PMA, but scope-dependent: some scopes carry a higher OSS risk class at the Large scale — register by declaring the higher-risk scope."
            }
            if let cond = v.nationalCondition, cond.isEmpty == false {
                return isID ? "Terbuka dengan syarat khusus: \(cond)" : "Open with a special condition: \(cond)"
            }
            return nil
        }
    }


    // MARK: 1c · FACTS ROW (D2, 2026-08-11) — 4-up inspector grid, EXISTING data only, no new
    // sourcing. Sits directly under the verdict banner now that the verdict leads the card.
    private var factsRow: some View {
        LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 10), count: 4), spacing: 10) {
            FactCell(label: isID ? "Putusan Bali" : "Bali Verdict", value: baliVerdictFactValue, color: baliVerdictFactColor)
            FactCell(label: isID ? "Kelas Risiko" : "Risk Class", value: riskClassFactValue, color: riskClassFactColor)
            // Bare % is deliberately back HERE (removed from the pill strip 2026-06-30 — a bare
            // "100%" next to a red "closed" pill read as a contradiction). The qualifier caption is
            // what makes it safe in an inspector cell: it names the value as the STATUTORY national
            // reference, pointing at the Licensing table below for the registrable truth.
            FactCell(label: isID ? "Batas Nasional" : "National Cap", value: nationalCapFactValue, caption: nationalCapFactCaption)
            FactCell(label: isID ? "Dinomori Ulang" : "Renumbered", value: renumberedFactValue,
                     color: kbli.isRenumbered ? Theme.statutory : Theme.faint)
        }
    }

    // K2 2026-09-13: these two cells read the VERDICT, not the raw status string. The old
    // `Theme.kbliStatusLabel(l4.status)` path had no case for `NON_CLASSIFICABILE` and fell through
    // to its title-casing last resort, printing the internal Italian token as "Non Classificabile"
    // on a regulator-facing card — and it said nothing at all ("—") for a record with no l4 block.
    //
    // The cell is labelled "Bali Verdict", so it states the HEADLINE — with the rule's precedence —
    // and not the bare Bali axis: a nationally closed record whose provincial axis is open read
    // "Bali Verdict: Open" under a sheet saying closed (council K2 round 1, codex-gpt-5.6-sol).
    private var baliVerdictFactValue: String {
        switch VerdictBadge.state(for: KBLIVerdict.of(record: kbli)) {
        case .open:            return isID ? "Terbuka" : "Open"
        case .blocked:         return isID ? "Diblokir" : "Blocked"
        case .closedNational:  return isID ? "Tertutup (nasional)" : "Closed (national)"
        case .undetermined, .undeterminedNational: return isID ? "Tidak ditentukan" : "Not determined"
        }
    }
    private var baliVerdictFactColor: Color {
        switch VerdictBadge.state(for: KBLIVerdict.of(record: kbli)) {
        case .open: return Theme.pmaOpen
        case .blocked, .closedNational: return Theme.pmaClosed
        case .undetermined, .undeterminedNational: return Theme.faint
        }
    }

    private var riskClassFactValue: String {
        guard let risk = KBLIVerdict.of(record: kbli).riskLabelRaw else {
            return RiskCell.absentText(isID: isID)
        }
        return riskLabel(risk)
    }
    private var riskClassFactColor: Color {
        guard let risk = KBLIVerdict.of(record: kbli).riskLabelRaw else { return Theme.faint }
        return Theme.riskColor(risk)
    }

    private var nationalCapFactValue: String {
        guard let m = kbli.pmaMaxAsing else { return Theme.absent }
        return "\(m)%"
    }
    private var nationalCapFactCaption: String? {
        guard kbli.pmaMaxAsing != nil else { return nil }
        return isID ? "Statutori — lihat tabel perizinan" : "Statutory — see licensing table"
    }

    private var renumberedFactValue: String {
        guard kbli.isRenumbered, let prev = kbli.kbli2020Source else { return Theme.absent }
        return "\(prev) → \(kbli.kode)"
    }

    // MARK: 4b · BALI-INTEL TEASER (C4) — a 3-line reality-check high up; full block stays low.
    @ViewBuilder private var baliIntelTeaser: some View {
        if let bullets = baliTeaserBullets, !bullets.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                Label(isID ? "CEK REALITA BALI — RINGKAS" : "BALI REALITY CHECK — IN BRIEF", systemImage: "star.fill")
                    .font(Theme.scalable(10, weight: .heavy, design: .monospaced)).tracking(0.5).foregroundStyle(Theme.yellow)
                // 3 lines is the teaser's design; the other 28 on a code like 68112 are now one
                // click away instead of silently dropped (the full markdown block further down
                // is a different rendering, not this list).
                ExpandableList(items: bullets, limit: 3, isID: isID, tint: Theme.yellow, spacing: 8) { shown in
                    ForEach(Array(shown.enumerated()), id: \.offset) { _, b in
                        HStack(alignment: .top, spacing: 8) {
                            Text("›").font(Theme.scalable(13, weight: .bold, design: .monospaced)).foregroundStyle(Theme.yellow)
                            Text(b).font(Theme.scalable(13)).foregroundStyle(Theme.white).lineSpacing(2)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                Text(isID ? "↓ Intel Gold-Tier lengkap di bawah" : "↓ Full Gold-Tier intel below")
                    .font(Theme.scalable(11, weight: .medium)).foregroundStyle(Theme.faint).padding(.top, 2)
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.yellow.opacity(0.06), in: RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous))
            .overlay(alignment: .leading) { RoundedRectangle(cornerRadius: 2).fill(Theme.yellow).frame(width: 3).padding(.vertical, 12) }
        }
    }

    /// The Bali context both plates draw: curated, its record's own closed-set values in English (Q17), else the
    /// dataset's intel.
    private var baliContext: String? {
        ovStrict?.baliContext.map { LabelBook.ledgerProse($0, record: kbli, isID: isID) }
            ?? kbli.intel?.baliContext.map { overlays.baliContextString($0, isID: isID) }
    }

    /// Extract the SHORT punchy bullets from baliContext markdown for the teaser. Returns them
    /// ALL — the teaser shows 3 and `ExpandableList` owns the cap, so the count on the button is
    /// the real one (68 codes carry more than 3; 68112 carries 31).
    private var baliTeaserBullets: [String]? {
        guard let bc = baliContext else { return nil }
        var out: [String] = []
        for line in bc.split(separator: "\n") {
            let s = line.trimmingCharacters(in: .whitespaces)
            guard s.hasPrefix("- ") else { continue }
            // strip leading "- ", markdown bold markers, and emoji; keep the first clause.
            var t = String(s.dropFirst(2))
            t = t.replacingOccurrences(of: "**", with: "")
            let clause = t.split(separator: ":").first.map(String.init) ?? t
            let trimmed = clause.trimmingCharacters(in: .whitespaces)
            if trimmed.count > 8 { out.append(trimmed) }
        }
        return out.isEmpty ? nil : out
    }

    // The risk tier — the rank ladder, the besar-or-highest rule, the labels and the summary —
    // moved to `Theme.RiskTier` (2026-09-13). It lived here in one copy, in `KBLIDossierView` in
    // a second and in `KBLIDetailRichView` in a third, and that is how THIS copy could keep a
    // `?? "Menengah Rendah"` fallback the other two had already dropped: 217 records carry no
    // `per_skala` at all, and the Risk Level row asserted a government tier for every one of them
    // while the Risk Class cell on the same card honestly said "—". One reader, one answer.
    private func riskLabel(_ r: String) -> String { LabelBook.riskTier(r, isID: isID) }

    /// The rule's risk label (highest Besar class, else highest across scales), read through
    /// `KBLIVerdict` — the SAME source `riskClassFactValue`/`riskClassFactColor` read, so the risk
    /// pill and the sheet's OSS-risk axis can never disagree (council K2 round 1, codex-gpt-5.6-sol).
    /// `KBLIVerdict`'s besar-or-highest rule and `Theme.RiskTier.category`'s are the same algorithm
    /// (K2 2026-09-13 / 2026-09-14, independently); this reads the verdict's own copy on purpose so
    /// the two consumers of "the record's risk" are ONE recomputation, not two that happen to agree.
    private func pmaRiskCategory() -> String? {
        KBLIVerdict.of(record: kbli).riskLabelRaw
    }
    private func confidenceLabel(_ c: String?) -> String? {
        guard let c else { return nil }
        let conf = c.lowercased()
        if conf == "medium" { return isID ? "keyakinan sedang" : "medium conf." }
        if conf == "high" { return isID ? "keyakinan tinggi" : "high conf." }
        if conf == "low" { return isID ? "keyakinan rendah" : "low conf." }
        return nil
    }

    // MARK: 3 · DESCRIPTION — prose on ivory
    private var description: some View {
        let text = ovStrict?.meaning.map { LabelBook.ledgerProse($0, record: kbli, isID: isID) } ?? LabelBook.uraian(kbli, isID: isID)
        return VStack(alignment: .leading, spacing: 10) {
            SectionLabel(rail: Theme.muted, text: isID ? "Deskripsi" : "Description")
            // D9: the dataset's own "- " lists hang (the curated meaning, when there is one, is prose, and its
            // markdown emphasis draws as emphasis).
            UraianLines(text: text, markdown: ovStrict?.meaning != nil)
                .frame(maxWidth: 640, alignment: .leading)
        }
    }

    // MARK: 4 · LICENSING / WHAT YOU NEED — license ledger (KBLI-first)
    private var licensing: some View {
        VStack(alignment: .leading, spacing: 14) {
            SectionLabel(rail: Theme.accent, text: isID ? "Perizinan & Persyaratan" : "Licensing & Requirements")
            // The terracotta "reserved-for-MSME / does-not-apply-to-PT-PMA" callout was removed here
            // (Zero 2026-06-30): it was the THIRD PMA-centric repeat in one card. The PMA restriction is
            // now stated once as a compact pill-tag up top and once in full in the Bali verdict moved
            // below the related codes — the licensing block stays about the KBLI's actual requirements.
            LedgerPlate(rail: Theme.muted, rows: licenseRows)
        }
    }

    /// Pure, headless-callable (`Tests/semantictest`) — the ONE ownership line this file renders
    /// on both its ledger rows ("Foreign Ownership" here, "PMA" in `authorityRows`). OPEN-1
    /// (2026-09-17): before this cure the two rows each re-derived the national axis from the raw
    /// fields independently and could disagree in wording ("Closed (0%)" here, "Tertutup · 0%" +
    /// a route suffix there) on the SAME record, on the SAME expanded card. Both now call this.
    static func ownershipLine(_ kbli: KBLI, isID: Bool) -> String {
        KBLIVerdict.of(record: kbli).ownershipLine(isID: isID)
    }

    private var licenseRows: [LedgerRow] {
        // Risk Level = honest range across scales (Mikro→Besar), not the smallest scale alone.
        // K2 2026-09-13: closed / Bali-blocked / undetermined are read from `KBLIVerdict`, the one
        // rule, instead of re-derived from the raw fields. The local derivation was binary on the
        // Bali axis, so the 8 records the dataset cannot classify printed a green fully-open
        // reading in the expanded dossier, under a sheet saying the opposite.
        let axes = VerdictAxes(KBLIVerdict.of(record: kbli))
        let pmaClosed = axes.nationallyClosed
        // National PMA openness != Bali registrability. A nationally-open code that is
        // l4-blocked in Bali must NOT headline a green ownership line — drop the green tint
        // (consistent with the verdict + the Authority ledger row). The Bali qualification itself
        // is a SEPARATE fact from the ownership line (OPEN-1) — it colours this row's tint, it
        // does not get blended back into the string.
        let baliBlocked = axes.baliBlocked
        let pma = Self.ownershipLine(kbli, isID: isID)
        return [
            LedgerRow(label: isID ? "Tingkat Risiko" : "Risk Level", value: Theme.RiskTier.summary(kbli.perSkala, isID: isID), mono: true),
            // License Type derived from per_skala.perizinan — NOT hardcoded "NIB + Standard Cert" (scar:
            // that asserted a Standard Cert even for codes whose only license is a bare NIB).
            LedgerRow(label: isID ? "Jenis Izin" : "License Type", value: derivedLicenseType, mono: true),
            // "Processing" row removed here (Zero 2026-06-30): it duplicated License Type and the real,
            // contextual processing/timeline ("14 working days" per risk class) already lives in the
            // PP28 scope×scale matrix below, where it is per-scale and meaningful.
            LedgerRow(label: isID ? "Kepemilikan Asing" : "Foreign Ownership", value: pma, mono: true, tint: (pmaClosed || baliBlocked) ? Theme.pmaClosed : (axes.anyUndetermined ? Theme.muted : Theme.pmaOpen)),
            // Authority row removed here too (Zero 2026-06-30): it showed only the single highest tier.
            // The authority is now per-scale inside the PP28 matrix cell, where Micro→Bupati and
            // Besar→Menteri are each shown honestly instead of collapsing to one misleading value.
        ]
    }

    /// The License Type derived from the code's per_skala `perizinan`, across all scales — bilingual.
    /// The dataset stores this as a list per scale ("NIB", "NIB dan Sertifikat Standar", "NIB dan Izin");
    /// we surface the MOST PERMISSIVE / most-informative variant present (Izin > Standard Cert > NIB),
    /// since that is the binding requirement a registrant must satisfy. If every scale is silent we keep
    /// a neutral bare "NIB" rather than asserting a Standard Cert that may not exist.
    private var derivedLicenseType: String {
        // per_skala.perizinan is empty for ~1338/1559 codes. When present, use it (highest tier).
        let raw = kbli.perSkala.flatMap { $0.perizinanList }
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        if !raw.isEmpty {
            func tier(_ s: String) -> Int {
                let u = s.lowercased()
                if u.contains("izin") { return 3 }                 // NIB + Izin (sectoral permit)
                if u.contains("sertifikat") || u.contains("standar") { return 2 } // NIB + Standard Cert
                return 1                                            // bare NIB
            }
            let best = raw.max(by: { tier($0) < tier($1) }) ?? "NIB"
            return localizedLicense(best)
        }
        // No explicit license in data → DERIVE it from the risk class. PP 28/2025 Pasal 124(4):
        // "Tingkat Risiko menentukan jenis Perizinan Berusaha" — the risk class DETERMINES the
        // license type (verified vs NB-3). Falling back to a flat "NIB" understated the requirement
        // on 937 high-risk codes. A PT PMA is Usaha Besar by law, so we read the Besar-tier risk.
        // And when there is NO risk class (217 records), the decree's mapping has no input: the
        // row reads "—". It used to read "NIB", a licence requirement stated on the app's own
        // authority, which is the same fabrication as the risk row one line above it.
        return Theme.RiskTier.licence(kbli.perSkala, isID: isID)
    }

    /// Processing mode DERIVED from the OSS risk class (PP 28/2025 Pasal 130-133) — never hardcoded.
    /// The risk class determines HOW the licence is issued:
    ///   Rendah (low)           → NIB issued automatically                → "Automatic"
    ///   Menengah Rendah (med-low) → NIB + self-declared Standard Cert    → "Auto + self-declared"
    ///   Menengah Tinggi / Tinggi  → Standard Cert/Izin needing approval  → "Requires verification"
    /// A KBLI's risk varies across scopes/scales on 541/1559 codes, so this scans ALL scales (not just
    /// the Besar/PMA tier — Processing is KBLI-wide, not PMA-specific) and shows a min→max range when
    /// the risk differs. Empty risk → "—": "Automatic" was the friendliest of the three outcomes and
    /// the one the data supports least.
    private var derivedProcessing: String { Theme.RiskTier.processing(kbli.perSkala, isID: isID) }

    /// Map the raw Indonesian license string to a clean bilingual label.
    private func localizedLicense(_ raw: String) -> String {
        let u = raw.lowercased()
        if u.contains("izin") { return isID ? "NIB + Izin" : "NIB + Permit" }
        if u.contains("sertifikat") || u.contains("standar") { return isID ? "NIB + Sertifikat Standar" : "NIB + Standard Cert" }
        if u.contains("nib") { return "NIB" }
        return raw   // unrecognized → show the dataset value verbatim rather than guess
    }

    // MARK: 5 · PP28/2025 — per-scale (single scope) or risk matrix (multi-scope)
    @ViewBuilder private var pp28: some View {
        // Hide the whole PP28 block when the code has NO per-scale data (101 special/government codes
        // like carbon trading, R&D) — an empty "PP 28/2025 · 0 SCALES" header was ugly and useless
        // (Zero 2026-06-30). The codes that DO carry scale data render the full matrix below.
        if kbli.perSkala.isEmpty {
            EmptyView()
        } else {
            pp28Body
        }
    }

    private var pp28Body: some View {
        // Honest count: distinct activity-scopes × distinct business-scales (NOT the raw row count,
        // which double-counts a scale that appears under two scopes — the "6 SCALES" confusion).
        // Scopes are counted by DESCRIPTION so identical-label splits collapse to one (matching the
        // panel's own scopeKey collapse — 90 dataset codes have N scopes all named the same).
        let scopeN = Set(kbli.perSkala.map { s -> String in
            let u = (s.scopeUraian ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            return u.isEmpty ? "idx:\(s.scopeIndex ?? 0)" : "u:" + u.lowercased()   // an identity, never drawn
        }).count
        let scales = Set(kbli.perSkala.flatMap { $0.skalaUsaha })
        let scaleN = scales.count
        let label = scopeN > 1
            ? "PP 28/2025 · \(scopeN) \(isID ? "RUANG LINGKUP" : "SCOPES") × \(scaleN) \(isID ? "SKALA" : "SCALES")"
            : "PP 28/2025 · \(scaleN) \(isID ? "SKALA" : "SCALES")"
        return RegistryDisclosure(rail: Theme.statutory,
                           label: label,
                           preview: scopeN > 1
                                ? (isID ? "Matriks risiko: \(scopeN) aktivitas × skala usaha"
                                        : "Risk matrix: \(scopeN) activities × business scale")
                                : (isID ? "Risiko, proses & kewajiban PER SKALA (Mikro→Besar)"
                                        : "Risk, processing & duties PER SCALE (Micro→Large)"),
                           defaultOpen: true) {   // primary info — every scale matters, not just PMA/Besar
            PP28ScalePanel(scales: kbli.perSkala, isID: isID)
        }
    }

    // MARK: 6 · REGISTRATION ROADMAP — open numbered timeline (monochrome chips).
    // C7: when Bali blocks PT PMA, the title + caption make clear this is the NATIONAL reference
    // procedure, NOT a recommended Bali-PT-PMA path (which would contradict the verdict banner).
    /// The company-incorporation step is SCALE-aware, not PT-PMA-centric. The KBLI
    /// Navigator speaks to everyone (Zero, 2026-06-29):
    ///   Mikro/Kecil/Menengah → WNI → PT PMDN / CV / Perorangan (local)
    ///   Besar                → WNI or WNA → PT PMDN (local) or PT PMA (foreign)
    /// The overlay hardcoded "PT PMA incorporation" as step 1 for every code, which
    /// excludes the WNI reader and, on a Bali-blocked code, contradicts the
    /// "reserved UMKM / closed to a PT PMA" verdict above it. Rewrite that one step.
    private func scaleAwareStep(_ step: CodeOverlay.Step) -> CodeOverlay.Step {
        let t = (step.title + " " + (step.detail ?? "")).lowercased()
        let isIncorporation = t.contains("incorporation") || t.contains("pt pma")
            || t.contains("pt pmdn") || t.contains("pendirian")
        guard isIncorporation else { return step }
        let hasBesar = kbli.perSkala.contains { p in
            (p.skalaUsaha).contains { $0.lowercased().contains("besar") }
        }
        let title = isID ? "Pendirian perusahaan" : "Company incorporation"
        // Council K2 round 2 (codex-gpt-5.6-sol): a nationally closed code has no PT PMA route at
        // any scale, so the step never offers one there — the rule decides, not the Besar row.
        let closedToForeignCapital = VerdictAxes(KBLIVerdict.of(record: kbli)).nationallyClosed
        let detail = LabelBook.incorporationStep(foreignRoute: hasBesar && closedToForeignCapital == false, isID: isID)
        return CodeOverlay.Step(title: title, detail: detail, duration: step.duration)
    }

    @ViewBuilder private var roadmap: some View {
        if let steps = ov?.roadmap, !steps.isEmpty {
            // K2 2026-09-13: "reference only" unless the ONE rule says open in Bali. It read
            // `l4_bali.blocked` alone, so an undetermined record — and a nationally closed one whose
            // Bali flag is false — was handed a "Registration Roadmap" as if the path were open.
            let axes = VerdictAxes(KBLIVerdict.of(record: kbli))
            let blocked = axes.openInBali == false
            let shownSteps = steps.map { scaleAwareStep($0) }.map {
                CodeOverlay.Step(title: LabelBook.ledgerProse($0.title, record: kbli, isID: isID),
                                 detail: $0.detail.map { LabelBook.ledgerProse($0, record: kbli, isID: isID) },
                                 duration: $0.duration.map { LabelBook.roadmapDuration($0, isID: isID) })
            }
            VStack(alignment: .leading, spacing: 10) {
                SectionLabel(rail: Theme.accent,
                             text: blocked ? (isID ? "Prosedur Nasional (Referensi)" : "National Procedure (Reference)")
                                            : (isID ? "Alur Pendaftaran" : "Registration Roadmap"))
                if blocked {
                    Text(axes.anyUndetermined && axes.nationallyClosed == false && axes.baliBlocked == false
                         ? (isID ? "Langkah-langkah nasional untuk kode ini — belum dapat dipastikan sebagai jalur untuk PT PMA di Bali (lihat putusan di atas)."
                                 : "The national steps for this code — NOT a confirmed path for a PT PMA in Bali (see the verdict above).")
                         : (isID ? "Langkah-langkah nasional untuk kode ini — BUKAN jalur untuk PT PMA di Bali (lihat putusan di atas)."
                                 : "The national steps for this code — NOT a path for a PT PMA in Bali (see the verdict above)."))
                        .font(Theme.scalable(12)).foregroundStyle(Theme.muted).lineSpacing(2)
                        .fixedSize(horizontal: false, vertical: true)
                }
                VStack(spacing: 0) {
                    ForEach(Array(shownSteps.enumerated()), id: \.offset) { i, step in
                        RoadmapStepRow(index: i + 1, step: step, isFirst: i == 0, isLast: i == shownSteps.count - 1, dimmed: blocked)
                    }
                }
                .padding(.vertical, 6).padding(.horizontal, 14)
                .background(Theme.inkLift, in: RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: Theme.radiusMd).strokeBorder(Theme.hairline, lineWidth: 1))
                .opacity(blocked ? 0.82 : 1.0)   // visually subordinate when it's reference-only
            }
        }
    }

    // MARK: 7 · LEGAL BASIS (+ PMA / renumber metadata) — moved to the bottom of the card
    private var authorityPlate: some View {
        VStack(alignment: .leading, spacing: 14) {
            SectionLabel(rail: Theme.statutory, text: isID ? "Dasar Hukum" : "Legal Basis")
            LedgerPlate(rail: Theme.statutory, rows: authorityRows)
            // Legal basis is now DERIVED for every code (was curated on 1/322 overlay codes only).
            // These are the regulations actually in force for KBLI 2025 (verified 2026-06-30 vs
            // committed facts): the Daftar Positif Investasi (Perpres 10/2021 jo 49/2021 jo 14/2024)
            // for the foreign-ownership axis + PP 28/2025 for the risk-based licensing axis.
            CitationGroup(title: isID ? "Dasar Hukum" : "Legal Basis", items: derivedLegalBasis, mono: false)
            // PB UMKU from the real per_skala data where present, else the curated overlay; hidden
            // when neither has any (no placeholder).
            if let pb = derivedPbUmku, !pb.isEmpty {
                UmkuChips(title: "PB UMKU", items: pb)
            }
        }
    }

    /// The legal basis in force for KBLI 2025/2026, derived (identical for every code — it is the
    /// regime, not a per-code fact). VERIFIED via NB-3 (NotebookLM NB-3, 2026-06-30, 13 sources):
    /// foundation = UU 6/2023 Cipta Kerja jo UU 25/2007 Penanaman Modal; ownership axis = the
    /// Investment Positive List (Perpres 10/2021 jo 49/2021); licensing axis = PP 28/2025 (which now
    /// also integrates DPI updates). NB-3 explicitly CORRECTED an earlier error: "Perpres 14/2024"
    /// is NOT the investment-list amendment — it governs Carbon Capture & Storage — so it is DROPPED.
    private var derivedLegalBasis: [String] {
        isID
        ? ["UU 6/2023 (Cipta Kerja) jo. UU 25/2007 — Penanaman Modal",
           "Perpres 10/2021 jo. Perpres 49/2021 — Daftar Positif Investasi",
           "PP 28/2025 — perizinan berusaha berbasis risiko"]
        : ["UU 6/2023 (Job Creation) jo. UU 25/2007 — Investment Law",
           "Perpres 10/2021 jo. Perpres 49/2021 — Positive Investment List",
           "PP 28/2025 — risk-based business licensing"]
    }

    /// PB UMKU (ancillary licences) — real per_skala data first, curated overlay as fallback, nil if
    /// neither carries any (so the chip row is hidden rather than empty).
    private var derivedPbUmku: [String]? {
        func strip(_ s: String) -> String {
            s.replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
             .trimmingCharacters(in: .whitespacesAndNewlines)
        }
        var seen = Set<String>(); var out: [String] = []
        for s in kbli.perSkala {
            for raw in s.pbUmkuList {
                let v = strip(raw)
                guard !v.isEmpty, seen.insert(v).inserted else { continue }
                out.append(v)
            }
        }
        if !out.isEmpty { return out }
        if let pb = ov?.authority?.pbUmku, !pb.isEmpty { return pb.map { LabelBook.permitName($0, isID: isID) } }
        return nil
    }

    private var authorityRows: [LedgerRow] {
        // Authority row removed from this table (Zero 2026-06-30): it showed only the single HIGHEST
        // tier across scales, which misleads a Micro/Small operator (their authority is the
        // Bupati/Walikota, not the Menteri). The authority now lives PER SCALE inside the PP28 matrix
        // cell, where it is honest. "Processing" was likewise moved to the PP28 timeline.
        var rows: [LedgerRow] = []
        if kbli.pmaMaxAsing != nil {
            // OPEN-1 (2026-09-17): the ownership line is `Self.ownershipLine` (see
            // `licenseRows`) — the SAME projection this card's other PMA-bearing ledger row
            // calls. This row no longer re-derives a fully-open wording from the raw fields; the
            // Bali axis, the route-to and the cap-verification flag are separate facts that
            // colour this row's TINT only (never blended back into the string, or the two
            // ledger rows on this card could again drift into two sentences for one record —
            // the zero-cap scar of 2026-06-27, generalised: never let a closed record render as
            // open in one spot and correctly as closed in another).
            let axes = VerdictAxes(KBLIVerdict.of(record: kbli))
            let pmaVal = Self.ownershipLine(kbli, isID: isID)
            let pmaTint: Color = (axes.nationallyClosed || axes.baliBlocked) ? Theme.pmaClosed
                : (axes.anyUndetermined ? Theme.muted : Theme.pmaOpen)
            rows.append(LedgerRow(label: "PMA", value: pmaVal, mono: true, tint: pmaTint))
        }
        if kbli.isRenumbered, let prev = kbli.kbli2020Source {
            rows.append(LedgerRow(label: isID ? "Penomoran" : "Renumber", value: "2020 \(prev) → 2025 \(kbli.kode)", mono: true, tint: Theme.statutory))
        }
        if let src = kbli.pmaSource {
            rows.append(LedgerRow(label: isID ? "Sumber PMA" : "PMA Source", value: src, mono: false))
        }
        return rows
    }

    /// The licensing AUTHORITY derived from the code's per_skala `kewenangan`, across all scales.
    /// The dataset names the real authority tier per OSS step — most often "Menteri/Kepala Badan"
    /// (Minister/Agency-Head), NOT the mayor the old card hardcoded. We collect the DISTINCT tiers
    /// present and, when several appear, show the HIGHEST (Menteri/Kepala Badan > Gubernur >
    /// Bupati/Walikota) — the binding sign-off level. Bilingual. When the dataset is silent for every
    /// scale we soften to a neutral "BKPM · OSS" rather than assert the mayor (which is usually wrong).
    private var derivedAuthority: String {
        let levels = kbli.perSkala.flatMap { $0.kewenanganLevels }
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        // TODO: a handful of dataset rows still carry kewenangan as a scalar String (PerSkala.kewenangan);
        // those are already folded into kewenanganLevels by the model's decodeStringList, so no extra
        // handling needed here — kept as a note in case the data shape changes again.
        guard !levels.isEmpty else { return "BKPM · OSS" }   // neutral — do NOT assert the mayor
        // rank by tier; highest wins
        let best = levels.max(by: { authorityRank($0) < authorityRank($1) }) ?? levels[0]
        return localizedAuthority(best)
    }

    /// Severity/seniority rank of an OSS licensing authority tier (higher = more senior).
    private func authorityRank(_ raw: String) -> Int { LabelBook.authorityRank(raw) }

    /// Map a raw Indonesian authority tier to a clean bilingual label (ID kept verbatim, EN translated).
    private func localizedAuthority(_ raw: String) -> String { LabelBook.authority(raw, isID: isID) }

    // MARK: 8 · BALI INTELLIGENCE — the authority peak (tinted plate)
    @ViewBuilder private var baliIntel: some View {
        if let bc = baliContext, !bc.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                Label(isID ? "GOLD-TIER INTEL · BALI" : "GOLD-TIER INTEL · BALI", systemImage: "star.fill")
                    .font(Theme.scalable(11, weight: .heavy, design: .monospaced)).tracking(0.6)
                    .foregroundStyle(Theme.yellow)
                    .accessibilityAddTraits(.isHeader)   // D3b — section title for this plate
                MarkdownView(markdown: bc, flatBullets: true)   // plain bullets, no false-affordance (C8)
            }
            .padding(18)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.accent.opacity(0.06), in: RoundedRectangle(cornerRadius: Theme.radiusLg, style: .continuous))
            .overlay(alignment: .leading) {
                RoundedRectangle(cornerRadius: 2).fill(Theme.accent).frame(width: 3).padding(.vertical, 14)
            }
            .overlay(RoundedRectangle(cornerRadius: Theme.radiusLg).strokeBorder(Theme.accent.opacity(0.16), lineWidth: 1))
        }
    }

    // `tkaPreview` deleted (2026-09-13). It truncated the TKA positions to 2 with a "+N" caption
    // and had had NO caller since the TKA drawer was removed from the Navigator on 2026-06-30 —
    // dead code cannot be made reachable in-app, and leaving it would have forced the static
    // truncation scan below to carry a named exception for a function nobody renders.

    // MARK: 9 · REFERENCE DRAWER — TKA + complementary (folded)
    private var referenceDrawer: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionLabel(rail: Theme.faint, text: isID ? "Referensi" : "Reference")
            // TKA ELIGIBLE POSITIONS removed from the Navigator (Zero 2026-06-30). The KBLI↔TKA
            // association we had was built from ISCO groups (an ILO/UN proxy), NOT the official
            // Indonesian Kemnaker positive-list of permitted jabatan, covered only 167/1559 codes,
            // and never showed the FORBIDDEN positions (HR/personalia) — the part that actually
            // protects a client. Better absent than authoritative-looking but proxy-sourced. The
            // rigorous KBLI↔TKA dataset (Kemnaker positive-list + forbidden roles + RPTKA logic) is
            // being built as a separate multi-agent project; it will return here once ground-truthed.
            // Only show complementary codes that actually EXIST in the dataset — the prose carries
            // ~47 cross-links to non-existent KBLI codes (e.g. 86103 → 47252, a pharmacy code that
            // doesn't exist). A dead tappable row that resolves to nothing is worse than omitting it.
            let comp = (kbli.intel?.complementaryCodes ?? []).filter { state.store.code($0.code) != nil }
            if !comp.isEmpty {
                RegistryDisclosure(rail: Theme.statutory,
                                   label: (isID ? "KODE PELENGKAP " : "COMPLEMENTARY CODES ") + "· \(comp.count)",
                                   // one-line COLLAPSED preview; the drawer's body below lists every
                                   // one of `comp`, so this cap hides nothing — opening the drawer
                                   // is the action, and the header states the full count.
                                   preview: Array(comp[0..<min(4, comp.count)]).map(\.code).joined(separator: ", ") + (comp.count > 4 ? "…" : ""),
                                   defaultOpen: false) {
                    VStack(spacing: 0) {
                        ForEach(Array(comp.enumerated()), id: \.offset) { i, c in
                            ComplementaryRow(code: c.code, note: c.note,
                                             onTap: { state.selected = state.store.code(c.code) })
                            if i < comp.count - 1 { Divider().overlay(Theme.hairline) }
                        }
                    }
                }
            }
        }
    }

    // MARK: 10 · RELATED CODES — mini-card grid (the one grid break)
    @ViewBuilder private var relatedGrid: some View {
        if let rel = ov?.related, !rel.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                SectionLabel(rail: Theme.muted, text: isID ? "Kode Terkait" : "Related Codes")
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 210, maximum: 260), spacing: 12)], alignment: .leading, spacing: 12) {
                    ForEach(rel, id: \.code) { r in
                        // title: overlay stores the Indonesian KBLI name → translate to EN via dataString
                        // (303/309 are in the judul map; the rest are already English). note: stored in
                        // English → translate to ID via relatedNoteString. Each renders monolingual.
                        // status/open: DERIVED from the linked code's REAL l4_bali (Zero 2026-06-30), NOT
                        // the overlay's hand-written "Open · 100%" — which lied on blocked codes (68112,
                        // 79110, 77311 all showed "Open" while really blocked in Bali). The dot + label
                        // now match the linked code's actual Bali verdict.
                        let linked = state.store.code(r.code)
                        CodeMiniCard(related: r, isID: isID,
                                     onTap: { if let k = linked { state.selected = k } },
                                     localizedTitle: r.title.map { overlays.dataString($0, isID: isID) },
                                     localizedNote: overlays.relatedNoteString(r.note, isID: isID),
                                     realAxes: linked.map { VerdictAxes(KBLIVerdict.of(record: $0)) },
                                     realStatusLabel: linked.map { miniCardStatusLabel($0) })
                    }
                }
            }
        }
    }

    /// The Bali-verdict label for a related mini-card, derived from the linked code's REAL data
    /// (same gate as the main verdict): nationally closed > Bali-blocked > open. Never the overlay's
    /// stale "Open · 100%".
    private func miniCardStatusLabel(_ k: KBLI) -> String {
        // K2 2026-09-13: the ONE rule, with its third state. The local derivation ended in a bare
        // `return "Open"`, so a related code the dataset cannot classify was introduced as open.
        let axes = VerdictAxes(KBLIVerdict.of(record: k))
        if axes.nationallyClosed { return isID ? "Tertutup (nasional)" : "Closed (national)" }
        if axes.baliBlocked { return isID ? "Diblokir di Bali" : "Blocked in Bali" }
        if axes.anyUndetermined { return isID ? "Tidak ditentukan" : "Not determined" }
        return isID ? "Terbuka" : "Open"
    }

    // MARK: 11 · READ FULL GUIDE — slim link plate
    private var readGuide: some View {
        HStack(spacing: 14) {
            RoundedRectangle(cornerRadius: 8).fill(Theme.statutory.opacity(0.14))
                .frame(width: 44, height: 44)
                .overlay(Image(systemName: "book.closed.fill").foregroundStyle(Theme.statutory))
            VStack(alignment: .leading, spacing: 2) {
                Text(isID ? "BACA PANDUAN LENGKAP DI BALI ZERO" : "READ FULL GUIDE ON BALI ZERO")
                    .font(Theme.scalable(10, weight: .heavy, design: .monospaced)).tracking(0.5)
                    .foregroundStyle(Theme.accent)
                Text(guideTitle)
                    .font(Theme.scalable(14, weight: .semibold, design: .serif))
                    .foregroundStyle(Theme.white)
                Text("balizero.com ↗").font(Theme.scalable(11, design: .monospaced)).foregroundStyle(Theme.faint)
            }
            Spacer()
            Image(systemName: "chevron.right").foregroundStyle(Theme.faint)
        }
        .padding(14)
        .background(Theme.inkLift, in: RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Theme.radiusMd).strokeBorder(Theme.hairline, lineWidth: 1))
        .onTapGesture { if let u = URL(string: "https://balizero.com/\(kbli.kode)") { NSWorkspace.shared.open(u) } }
    }

    /// Guide title derived from the code's KBLI category (A–U) — NOT hardcoded to Hospitality.
    /// (Scar: this used to read "KBLI 2025 Hospitality & Accommodation…" for EVERY code — the same
    /// hardcoded-lie family as the old sectorLine bug. Now per-category + bilingual.)
    private var guideTitle: String {
        guard let cat = SectorImage.category(for: kbli.kode) else {
            return isID ? "Panduan KBLI 2025 di Bali" : "KBLI 2025 Guide for Bali"
        }
        let name = SectorImage.categoryName(cat, isID: isID)
        return isID ? "Panduan KBLI 2025: \(name) di Bali"
                    : "KBLI 2025 Guide: \(name) in Bali"
    }

    // MARK: 12 · ZANTARA — footer (warmer ivory inset). Pricing block removed (2026-06-24, Zero).
    private func footer(leading: CGFloat) -> some View {
        VStack(alignment: .leading, spacing: 18) {
            SectionLabel(rail: Theme.zantara, text: isID ? "Tanya Zantara" : "Ask Zantara")
            chatFooter
        }
        .padding(.leading, leading).padding(.trailing, 48).padding(.vertical, 22)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.surfaceHi)
    }

    private var chatFooter: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 7) {
                Circle().fill(Theme.zantara).frame(width: 7, height: 7)
                Text("Zantara").font(Theme.scalable(15, weight: .semibold, design: .serif)).foregroundStyle(Theme.white)
            }
            .accessibilityAddTraits(.isHeader)   // D3b — this footer's section title
            if showsIdentityAndVerdict, let opener = openerLine {
                Text(opener)
                    .font(Theme.scalable(13)).foregroundStyle(Theme.white).lineSpacing(4)
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Theme.zantara.opacity(0.08), in: RoundedRectangle(cornerRadius: Theme.radiusMd))
            }
            HStack(spacing: 8) {
                ForEach(chatChips, id: \.self) { chip in
                    Text(chip).font(Theme.scalable(11, weight: .medium)).foregroundStyle(Theme.zantara)
                        .padding(.horizontal, 11).padding(.vertical, 6)
                        .overlay(Capsule().strokeBorder(Theme.zantara.opacity(0.4), lineWidth: 1))
                }
            }
            Button { state.askZantara(about: kbli) } label: {
                HStack {
                    Text(isID ? "Tanya tentang \(kbli.kode)…" : "Ask about \(kbli.kode)…")
                        .font(Theme.scalable(13)).foregroundStyle(Theme.faint)
                    Spacer()
                    Image(systemName: "arrow.up.circle.fill").foregroundStyle(Theme.zantara)
                }
                .padding(12)
                .background(Theme.inkLift, in: RoundedRectangle(cornerRadius: Theme.radiusMd))
                .overlay(RoundedRectangle(cornerRadius: Theme.radiusMd).strokeBorder(Theme.zantara.opacity(0.25), lineWidth: 1))
            }
            .buttonStyle(.plain)
            .shadow(color: .black.opacity(0.06), radius: 1, y: 1)
        }
    }

    private var chatChips: [String] {
        isID ? ["Apa yang saya butuhkan?", "Bisakah asing memiliki ini?", "Apa yang berubah 2020→2025?"]
             : ["What do I need to start?", "Can foreigners own this?", "What changed 2020→2025?"]
    }

    /// The Zantara footer opener (one sentence). Curated codes carry a bilingual `verdict`; for
    /// non-curated codes the dataset's `zantaraOpener` is English boilerplate ("Looking into <judul>
    /// (<code>)? …"), which is macaronic in the ID card. So we render a faithful LOCALIZED template
    /// — invariant facts only (the localized title + code), no invented regulatory content. EN keeps
    /// the dataset opener's first sentence; ID gets the Indonesian template with the raw `judul`.
    /// Cosmetic cleanup for the curated verdict when used as the chat opener: the army-generated
    /// verdicts carry raw markdown bold (`**`) that SwiftUI `Text` renders literally (321/322
    /// codes), and 84 embed dataset-Indonesian timeline tokens ("Otomatis" / "7 Hari") in the EN
    /// prose. Bounded, shape-anchored replacements only — never free-text translation. An office name stays
    /// as the curated line writes it ("Authority: Bupati/Walikota", ruling 1): a pattern is not Q17's exact match.
    private func cleanOpener(_ s: String) -> String {
        var t = s.replacingOccurrences(of: "**", with: "")
        if !isID {
            t = t.replacingOccurrences(of: "Timeline: Otomatis", with: "Timeline: Automatic")
            t = t.replacingOccurrences(of: #"Timeline: (\d+) Hari Kerja"#, with: "Timeline: $1 working days", options: .regularExpression)
            t = t.replacingOccurrences(of: #"Timeline: (\d+) Hari"#, with: "Timeline: $1 days", options: .regularExpression)
            t = t.replacingOccurrences(of: "NIB dan Sertifikat Standar", with: "NIB + Standard Certificate")
            t = LabelBook.ledgerProse(t, record: kbli, isID: false)
        }
        return t
    }

    private var openerLine: String? {
        if let rawVerdict = ovStrict?.verdict {                   // curated → already localized
            let v = cleanOpener(rawVerdict)
            // Normally the opener is the verdict's first sentence (a compact hook). BUT for a
            // Bali-blocked code the curated verdict is written as "Nationally open … In Bali, however,
            // … closed to foreign-owned companies." — the SECOND sentence is the binding answer and the
            // FIRST sentence alone ("fully open to foreign ownership (100% PMA)") inverts the meaning.
            // Truncating to .first there is the #3 guard-miss: a green half-truth that contradicts the
            // BLOCKED verdict. When Bali blocks, keep the WHOLE verdict (it is already one tight opener).
            if kbli.l4Bali?.blocked == true {
                return v
            }
            return v.split(separator: ".").first.map { String($0) + "." } ?? v
        }
        // Non-curated: render a LOCALIZED template from the (translated) title. We do NOT reuse the
        // dataset's `zantaraOpener` — its English text embeds the *Indonesian* judul ("Looking into
        // <judul-ID> …"), which is macaronic in the EN card. The template uses the translated title,
        // so EN is fully English and ID fully Indonesian, with no invented regulatory content.
        if isID {
            return "Tertarik dengan \(OverlayStore.shared.dataString(kbli.judul, isID: true)) (\(kbli.kode))? Mari saya bantu menelusurinya."
        }
        return "Looking into \(OverlayStore.shared.dataString(kbli.judul, isID: false)) (\(kbli.kode))? Let me walk you through it."
    }
}

// MARK: - Reusable registry components (the dossier grammar)

/// SF-Mono uppercase section label preceded by a 3pt × 14pt vertical accent bar — the spine motif.
struct SectionLabel: View {
    let rail: Color
    let text: String
    var body: some View {
        HStack(spacing: 9) {
            RoundedRectangle(cornerRadius: 2).fill(rail).frame(width: 3, height: 14)
            Text(text.uppercased())
                .font(Theme.scalable(11, weight: .bold, design: .monospaced)).tracking(0.8)
                .foregroundStyle(Theme.muted)
        }
        // D3b: every section on the registry card (Description, Licensing, PP28, Roadmap, Legal
        // Basis, ...) routes through this ONE component — marking it .isHeader here covers all 7
        // call sites in one place, so VoiceOver users can jump section-to-section with the rotor
        // instead of swiping through the whole card linearly.
        .accessibilityAddTraits(.isHeader)
    }
}

struct LedgerRow: Identifiable {
    let id = UUID()
    let label: String
    let value: String
    var mono: Bool = false
    var tint: Color? = nil
}

/// One cell of the D2 (2026-08-11) "facts inspector" 4-up grid on the detail card — compact
/// label/value/caption. Deliberately its OWN small component rather than a reuse of `PremiumStat`
/// below: `PremiumStat`'s 30pt bold face is sized for short figures ("14 days", "$500"); a Bali
/// verdict label ("Closed (risk class)") or a risk category ("Risiko Menengah-Tinggi") can run
/// much longer, so this uses LedgerPlate-scale (13-15pt) typography with a 2-line wrap instead of
/// `minimumScaleFactor` shrink, which would otherwise squash long labels illegibly.
struct FactCell: View {
    let label: String
    let value: String
    var color: Color = Theme.white
    var caption: String? = nil
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label.uppercased())
                .font(Theme.scalable(9, weight: .semibold, design: .monospaced))
                .tracking(0.6)
                .foregroundStyle(Theme.faint)
            Text(value)
                .font(Theme.scalable(15, weight: .semibold))
                .foregroundStyle(color)
                .fixedSize(horizontal: false, vertical: true)
                .fixedSize(horizontal: false, vertical: true)
            if let caption {
                Text(caption)
                    .font(Theme.scalable(9, weight: .medium))
                    .foregroundStyle(Theme.faint)
                    .fixedSize(horizontal: false, vertical: true)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Theme.inkLift, in: RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Theme.radiusMd).strokeBorder(Theme.hairline, lineWidth: 1))
        // D3b: one VoiceOver stop ("Bali Verdict, Closed to PMA (Besar), <caption>") instead of
        // landing on the label and the value as two separate, order-dependent swipes.
        .accessibilityElement(children: .combine)
    }
}

/// THE SIGNATURE MOVE — mono label ↔ value table, 3pt colored left-rail, hairline rows, white on ivory.
struct LedgerPlate: View {
    let rail: Color
    let rows: [LedgerRow]
    var body: some View {
        VStack(spacing: 0) {
            ForEach(Array(rows.enumerated()), id: \.element.id) { i, row in
                HStack(alignment: .firstTextBaseline) {
                    Text(row.label.uppercased())
                        .font(Theme.scalable(11, weight: .semibold, design: .monospaced)).tracking(0.4)
                        .foregroundStyle(Theme.muted)
                        .frame(width: 150, alignment: .leading)
                    Text(row.value)
                        .font(Theme.scalable(14, weight: .medium, design: row.mono ? .monospaced : .default))
                        .foregroundStyle(row.tint ?? Theme.white)
                    Spacer(minLength: 0)
                }
                .padding(.vertical, 10).padding(.horizontal, 14)
                if i < rows.count - 1 { Divider().overlay(Theme.hairline) }
            }
        }
        .background(Theme.inkLift, in: RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous))
        .overlay(alignment: .leading) {
            RoundedRectangle(cornerRadius: 2).fill(rail).frame(width: 3).padding(.vertical, 8)
        }
        .overlay(RoundedRectangle(cornerRadius: Theme.radiusMd).strokeBorder(Theme.hairline, lineWidth: 1))
    }
}

/// A tinted callout plate (terracotta national-procedure notice).
struct CalloutPlate: View {
    let rail: Color
    let title: String
    let body_: String
    init(rail: Color, title: String, body: String) { self.rail = rail; self.title = title; self.body_ = body }
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(rail).font(Theme.scalable(14))
            VStack(alignment: .leading, spacing: 4) {
                Text(title).font(Theme.scalable(13, weight: .bold)).foregroundStyle(rail)
                Text(body_).font(Theme.scalable(13)).foregroundStyle(Theme.muted).lineSpacing(3)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(rail.opacity(0.07), in: RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous))
        .overlay(alignment: .leading) { RoundedRectangle(cornerRadius: 2).fill(rail).frame(width: 3).padding(.vertical, 12) }
        .overlay(RoundedRectangle(cornerRadius: Theme.radiusMd).strokeBorder(rail.opacity(0.18), lineWidth: 1))
    }
}

/// A disclosure styled as a registry plate header. C6: chevron sits NEXT TO the title (left cluster,
/// not decoupled at the far edge), rotates on open, and a `preview` line under the label tells the
/// user what's inside before they tap.
struct RegistryDisclosure<Content: View>: View {
    let rail: Color
    let label: String
    var preview: String? = nil
    var defaultOpen: Bool = false
    @ViewBuilder var content: Content
    @State private var open: Bool
    init(rail: Color, label: String, preview: String? = nil, defaultOpen: Bool = false, @ViewBuilder content: () -> Content) {
        self.rail = rail; self.label = label; self.preview = preview; self.defaultOpen = defaultOpen
        // QA hook: KBLI_OPEN_ALL=1 forces every drawer open so off-screen snapshots capture content.
        let forced = ProcessInfo.processInfo.environment["KBLI_OPEN_ALL"] == "1"
        self._open = State(initialValue: defaultOpen || forced); self.content = content()
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Button { withAnimation(.easeInOut(duration: 0.18)) { open.toggle() } } label: {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    // chevron NEXT TO the title (tight interactive cluster), not at the far right edge.
                    Image(systemName: "chevron.right").font(Theme.scalable(10, weight: .bold))
                        .foregroundStyle(rail).rotationEffect(.degrees(open ? 90 : 0))
                    VStack(alignment: .leading, spacing: 2) {
                        Text(label).font(Theme.scalable(11, weight: .bold, design: .monospaced)).tracking(0.6).foregroundStyle(Theme.muted)
                        if let p = preview, !open {
                            Text(p).font(Theme.scalable(11)).foregroundStyle(Theme.faint)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    Spacer(minLength: 0)
                }
                .contentShape(Rectangle())   // whole header row is the tap target
                .padding(.vertical, 11).padding(.horizontal, 14)
            }
            .buttonStyle(.plain)
            if open {
                Divider().overlay(Theme.hairline)
                content.padding(14)
            }
        }
        .background(Theme.inkLift, in: RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous))
        .overlay(alignment: .leading) { RoundedRectangle(cornerRadius: 2).fill(rail).frame(width: 3).padding(.vertical, 8) }
        .overlay(RoundedRectangle(cornerRadius: Theme.radiusMd).strokeBorder(Theme.hairline, lineWidth: 1))
    }
}

struct PillSpec: Hashable { let text: String; let color: Color; var meta: String? = nil }

/// The verdict pill strip — pastel-fill + tinted-ink pills that wrap.
struct FlowPills: View {
    let pills: [PillSpec]
    var body: some View {
        FlexWrap(spacing: 8, lineSpacing: 8) {
            ForEach(pills, id: \.self) { p in
                HStack(spacing: 5) {
                    Text(p.text).font(Theme.scalable(12, weight: .semibold))
                    if let m = p.meta {
                        Text(m).font(Theme.scalable(10, weight: .medium, design: .monospaced)).opacity(0.75)
                    }
                }
                .foregroundStyle(p.color)
                .padding(.horizontal, 11).padding(.vertical, 6)
                .background(p.color.opacity(0.12), in: Capsule())
                .overlay(Capsule().strokeBorder(p.color.opacity(0.22), lineWidth: 1))
            }
        }
    }
}

/// PP28 scale segmented control + post-license obligations sub-plate.
struct PP28ScalePanel: View {
    let scales: [PerSkala]
    let isID: Bool
    @State private var matrixSel: Int? = nil // selected cell = index into `scales` (matrix path)

    static let scaleOrder = ["Mikro", "Kecil", "Menengah", "Besar"]

    /// Localized name of an OSS enterprise scale. The dataset stores the Indonesian tier names
    /// (Mikro/Kecil/Menengah/Besar); the EN card must read Micro/Small/Medium/Large (matching the
    /// abbreviation legend). Unknown scales pass through unchanged.
    static func scaleLabel(_ raw: String, isID: Bool) -> String {
        if isID { return raw }
        switch raw.lowercased() {
        case "mikro": return "Micro"
        case "kecil": return "Small"
        case "menengah": return "Medium"
        case "besar": return "Large"
        default: return raw
        }
    }

    /// Render a `jangka_waktu` (OSS processing time) value for display. The dataset carries THREE
    /// shapes after the PP28 enrichment: "Otomatis" (instant), a bare day count ("7", "14"), and a
    /// pre-formatted "N Hari". A naive "\(jw) hari" suffix would produce "Otomatis hari" or "3 Hari
    /// hari" — so we only append the unit to a bare number, and translate.
    ///   "Otomatis" → "Instant" (EN) / "Otomatis" (ID)
    ///   "7"        → "7 Hari Kerja" (ID) / "7 working days" (EN)
    ///   "3 Hari"   → "3 Hari Kerja" (ID) / "3 working days" (EN)
    static func formatJangkaWaktu(_ raw: String, isID: Bool) -> String {
        let t = raw.trimmingCharacters(in: .whitespaces)
        if t.lowercased() == "otomatis" { return isID ? "Otomatis" : "Instant" }
        // pull the leading number; tolerate a trailing "Hari"/"hari" already present
        let num = String(t.prefix(while: { $0.isNumber }))
        guard !num.isEmpty else { return t }   // unknown shape → show verbatim
        return isID ? "\(num) Hari Kerja" : "\(num) working days"
    }

    /// Canonical scope key for a row. Two raw `scope_index` blocks that carry the SAME human
    /// description are the same activity scope to a reader — the split is a data artifact (90
    /// codes in the dataset have N scopes all named identically, e.g. "Seluruh"×3, where it's
    /// the SCALE that differs, not the activity). Collapsing them stops the card claiming
    /// "3 scopes" to a regulator when there is really one. Key = normalized uraian when present,
    /// else the raw index (so genuinely-unlabelled scopes stay distinct).
    private func scopeKey(_ s: PerSkala) -> String {
        let u = (s.scopeUraian ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        return u.isEmpty ? "idx:\(s.scopeIndex ?? 0)" : "u:" + u.lowercased()   // an identity, never drawn
    }
    /// First-seen ordered list of DISTINCT scope keys (post-collapse). This is the count the
    /// card shows and the rows the matrix/list render.
    private var scopeKeys: [String] {
        var seen = Set<String>(), order: [String] = []
        for s in scales { let k = scopeKey(s); if !seen.contains(k) { seen.insert(k); order.append(k) } }
        return order
    }
    /// All rows belonging to a collapsed scope key.
    private func rows(forKey key: String) -> [(idx: Int, row: PerSkala)] {
        scales.enumerated().compactMap { scopeKey($0.element) == key ? ($0.offset, $0.element) : nil }
    }
    /// Distinct OSS scopes (ruang lingkup) in first-seen order — now keyed by description so
    /// identical-label splits collapse. A code like 56101 still has TWO ("Restoran" / "Warung").
    private var scopeIndices: [String] { scopeKeys }

    private func rowFor(scope key: String, scale: String) -> (idx: Int, row: PerSkala)? {
        for (i, s) in scales.enumerated() where scopeKey(s) == key && s.skalaUsaha.contains(scale) {
            return (i, s)
        }
        return nil
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            if scales.isEmpty {
                Text(isID ? "Tidak ada data skala untuk kode ini." : "No per-scale data for this code.")
                    .font(Theme.scalable(12)).foregroundStyle(Theme.faint)
            } else {
                // D1: the top grid's risk × scale matrix; a chip selects the cell whose duties follow.
                // Six or more scopes: the matrix's filterable list, each scope's detail on expand.
                ScaleMatrix(scales: scales, isID: isID, mode: .ledger, selection: $matrixSel,
                            expanded: { AnyView(cellDetail($0)) })
                if scopeIndices.count < ScaleMatrix.listFrom, let mi = matrixSel ?? defaultCell, mi < scales.count {
                    cellDetail(scales[mi])
                }
            }
        }
    }

    static let matrixMaxScopes = 5

    private var defaultCell: Int? {
        if let first = scopeIndices.first,
           let hit = rowFor(scope: first, scale: "Besar") { return hit.idx }
        // else the first existing row
        return scales.indices.first
    }

    private func cellDetail(_ s: PerSkala) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Text(LabelBook.scales(s.skalaUsaha, isID: isID)).font(Theme.scalable(12, weight: .heavy, design: .monospaced)).foregroundStyle(Theme.white)
                if let risk = s.kategoriRisiko {
                    Text(LabelBook.riskTier(risk, isID: isID)).font(Theme.scalable(11, weight: .semibold)).foregroundStyle(Theme.riskChip(risk).fg)
                        .padding(.horizontal, 8).padding(.vertical, 3)
                        .background(Theme.riskChip(risk).bg, in: Capsule())
                        .overlay(Capsule().strokeBorder(Theme.riskChip(risk).border ?? .clear, lineWidth: 1))
                }
                if let jw = s.jangkaWaktu, !jw.isEmpty {
                    Text(LabelBook.term(jw, isID: isID)).font(Theme.scalable(11, design: .monospaced)).foregroundStyle(Theme.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            // Licensing AUTHORITY for THIS scale (Zero 2026-06-30): moved here from the Authority table,
            // which only showed the single highest tier — misleading, since a Micro/Small operator
            // answers to the Bupati/Walikota while only the large scale reaches the Menteri. Per-scale
            // it is honest. Derived from per_skala.kewenangan; hidden when the dataset is silent.
            if case let auth = ScaleMatrix.authorities(s, isID: isID).joined(separator: " · "), !auth.isEmpty {
                HStack(spacing: 5) {
                    Text(isID ? "Kewenangan:" : "Authority:")
                        .font(Theme.scalable(10, weight: .semibold, design: .monospaced)).foregroundStyle(Theme.faint)
                    Text(auth).font(Theme.scalable(11, weight: .medium)).foregroundStyle(Theme.muted)
                }
            }
            if let su = s.scopeUraian, !su.isEmpty {
                if LabelBook.isOriginal(su, drawn: LabelBook.data(su, isID: isID), isID: isID) { OriginalLabel() }
                Text(LabelBook.data(su, isID: isID)).font(Theme.scalable(11)).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
            }
            // De-duplicate then translate to the display language (EN→English, ID→unchanged).
            // (e.g. the OJK reporting line repeated twice — a regulator reads it as sloppy.)
            // An item with no English source is drawn verbatim under its label (Q12 ruling 4).
            let duties = Self.dedupKeepingOrder(s.kewajiban.map(Self.stripHTML).filter { !$0.isEmpty })
            if !duties.isEmpty {
                scaleList(title: isID ? "KEWAJIBAN PASCA-IZIN" : "POST-LICENSE OBLIGATIONS", items: duties.map { LabelBook.data($0, isID: isID) },
                          originals: Set(duties.filter { LabelBook.isOriginal($0, drawn: LabelBook.data($0, isID: isID), isID: isID) }), tint: Theme.yellow)
            }
            let reqs = Self.dedupKeepingOrder(s.persyaratan.map(Self.stripHTML).filter { !$0.isEmpty })
            if !reqs.isEmpty {
                scaleList(title: isID ? "PERSYARATAN" : "REQUIREMENTS", items: reqs.map { LabelBook.data($0, isID: isID) },
                          originals: Set(reqs.filter { LabelBook.isOriginal($0, drawn: LabelBook.data($0, isID: isID), isID: isID) }), tint: Theme.statutory)
            }
        }
        .padding(.top, 4)
    }

    private func scaleList(title: String, items: [String], originals: Set<String>, tint: Color) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(Theme.scalable(10, weight: .heavy, design: .monospaced)).tracking(0.5).foregroundStyle(tint)
            // 1090 scale rows carry more than 8 obligations (05101 carries 34). The old
            // "+26 more" caption named them and gave no way to read them — these are the
            // post-licence duties a registrant is bound by, so the count is now a button.
            ExpandableList(items: items, limit: 8, isID: isID, tint: tint, spacing: 8) { shown in
                ForEach(Array(shown.enumerated()), id: \.offset) { _, t in
                    HStack(alignment: .top, spacing: 8) {
                        Text("›").font(Theme.scalable(13, weight: .bold, design: .monospaced)).foregroundStyle(tint)
                        VStack(alignment: .leading, spacing: 2) {
                            if originals.contains(t) { OriginalLabel() }
                            Text(t).font(Theme.scalable(13)).foregroundStyle(Theme.white).fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(tint.opacity(0.07), in: RoundedRectangle(cornerRadius: Theme.radiusSm))
        .overlay(alignment: .leading) { RoundedRectangle(cornerRadius: 2).fill(tint).frame(width: 3).padding(.vertical, 10) }
    }

    /// Strip HTML tags/entities from a persyaratan string (the dataset embeds <strong>/<ol>/<li>…).
    static func stripHTML(_ s: String) -> String {
        var out = s.replacingOccurrences(of: "<[^>]+>", with: " ", options: .regularExpression)
        for (e, c) in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", "\"")] {
            out = out.replacingOccurrences(of: e, with: c)
        }
        return out.replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression).trimmingCharacters(in: .whitespacesAndNewlines)
    }


    /// Order-preserving de-duplication (case/space-insensitive key). Kills verbatim-repeated
    /// obligations/requirements the dataset sometimes carries.
    static func dedupKeepingOrder(_ items: [String]) -> [String] {
        var seen = Set<String>(), out: [String] = []
        for it in items {
            let key = it.lowercased().replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression).trimmingCharacters(in: .whitespaces)
            if !key.isEmpty, seen.insert(key).inserted { out.append(it) }
        }
        return out
    }

}

/// One roadmap step row — monochrome number-chip + connector line (vertical timeline).
struct RoadmapStepRow: View {
    let index: Int
    let step: CodeOverlay.Step
    let isFirst: Bool
    let isLast: Bool
    var dimmed: Bool = false   // C7: reference-only (Bali-blocked) → no sage "entry" ring on step 1
    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            ZStack {
                // C5/C7: thicker connector + brighter when not reference-only.
                // D3b REGRESSION FIX: this Rectangle has no explicit height, so (being in a ZStack
                // with no other height-constrained sibling to defer to) it auto-stretches to match
                // whatever height the row's TEXT block ends up needing. Text-style fonts
                // (Theme.scalable) carry noticeably more built-in leading than the old literal
                // `.system(size:)` calls even at the SAME Dynamic Type size — measured live: this
                // connector ballooned to ~220pt between steps (screenshot evidence, registry:55203)
                // versus the pre-D3b ~50-60pt. Capping it keeps the DEFAULT-scale look correct (the
                // regression that matters — it doesn't need an accessibility setting to trigger);
                // the accepted trade-off is the connector may visually undershoot the next circle at
                // extreme Dynamic Type sizes where a step wraps to several lines, which is a
                // proportional degradation under stress, not a default-state break.
                if !isLast { Rectangle().fill(Theme.hairlineHi).frame(width: 1.5).frame(maxHeight: 58).offset(y: 16) }
                Circle().fill(Theme.white)
                    .frame(width: 24, height: 24)
                    .overlay(Circle().strokeBorder((isFirst && !dimmed) ? Theme.pmaOpen : Color.clear, lineWidth: 1.5))
                // numeral = the window background punched out of the near-white chip (high contrast,
                // theme-robust): dark numeral on a light chip in BOTH Day and Night.
                Text("\(index)").font(Theme.scalable(12, weight: .bold, design: .monospaced)).foregroundStyle(Theme.antracite)
            }
            .frame(width: 24)
            VStack(alignment: .leading, spacing: 1) {
                Text(step.title).font(Theme.scalable(14, weight: .semibold)).foregroundStyle(Theme.white)
                if let d = step.detail { Text(d).font(Theme.scalable(12)).foregroundStyle(Theme.muted) }
            }
            Spacer(minLength: 8)
            if let dur = step.duration {
                Text(dur).font(Theme.scalable(11, weight: .semibold, design: .monospaced)).foregroundStyle(Theme.faint)
            }
        }
        .padding(.vertical, 9)
    }
}

/// TKA eligible-positions 2-col ledger (ISCO mono ↔ EN ↔ ID right) + KEDUA nested note.
struct TKAPanel: View {
    let tka: TKAInfo
    let isID: Bool
    /// Localizer for the English-only free-text fields (`insight`, `keduaNote`). Bound by the parent
    /// to `OverlayStore.baliContextString` so they read Indonesian in the ID card; defaults to identity.
    var tr: (String) -> String = { $0 }
    @State private var showKedua = false
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if let ins = tka.insight {
                Text(tr(ins)).font(Theme.scalable(11, weight: .medium, design: .monospaced)).foregroundStyle(Theme.faint)
            }
            VStack(spacing: 0) {
                ForEach(Array(tka.relevantPositions.enumerated()), id: \.offset) { i, pos in
                    HStack(alignment: .firstTextBaseline, spacing: 12) {
                        Text(pos.isco).font(Theme.scalable(12, weight: .semibold, design: .monospaced))
                            .foregroundStyle(Theme.accent).frame(width: 42, alignment: .leading)
                        Text(isID ? pos.titleId : pos.titleEn).font(Theme.scalable(13, weight: .medium)).foregroundStyle(Theme.white)
                        Spacer(minLength: 8)
                        Text(isID ? pos.titleEn : pos.titleId).font(Theme.scalable(12)).foregroundStyle(Theme.faint)
                            .frame(alignment: .trailing)
                    }
                    .padding(.vertical, 7)
                    if i < tka.relevantPositions.count - 1 { Divider().overlay(Theme.hairline) }
                }
            }
            if let kedua = tka.keduaNote {
                Button { withAnimation { showKedua.toggle() } } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "chevron.right").font(Theme.scalable(9, weight: .bold)).rotationEffect(.degrees(showKedua ? 90 : 0))
                        Text(isID ? "Ketentuan KEDUA — pengecualian Direksi & Komisaris" : "KEDUA Provision — Directors & Commissioners exemption")
                            .font(Theme.scalable(11, weight: .semibold)).foregroundStyle(Theme.muted)
                    }
                }.buttonStyle(.plain)
                if showKedua {
                    Text(tr(kedua)).font(Theme.scalable(12)).foregroundStyle(Theme.faint).lineSpacing(3).padding(.leading, 16)
                }
            }
        }
    }
}

/// One complementary-code row (tappable to navigate).
struct ComplementaryRow: View {
    let code: String
    let note: String
    let onTap: () -> Void
    @State private var hover = false
    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 12) {
                Text(code).font(Theme.scalable(13, weight: .semibold, design: .monospaced)).foregroundStyle(Theme.accent)
                    .frame(width: 56, alignment: .leading)
                Text(note).font(Theme.scalable(13)).foregroundStyle(Theme.muted)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 4)
                Image(systemName: "arrow.up.right").font(Theme.scalable(10, weight: .bold)).foregroundStyle(Theme.faint)
            }
            .padding(.vertical, 9).padding(.horizontal, 6)
            .background(hover ? Theme.surfaceHi : .clear)
        }
        .buttonStyle(.plain).onHover { hover = $0 }
    }
}

/// Related-code mini-card (the one grid break from the ledger rhythm).
struct CodeMiniCard: View {
    let related: CodeOverlay.Related
    let isID: Bool
    let onTap: () -> Void
    /// Localized title/note resolved by the caller (where OverlayStore is in scope): the overlay
    /// stores an Indonesian `title` (official KBLI name) and an English `note`, so the EN card was
    /// macaronic on the title and the ID card on the note. The caller passes the right-language
    /// strings; these default to the raw fields so the struct is still usable standalone.
    var localizedTitle: String? = nil
    var localizedNote: String? = nil
    /// The linked code's REAL Bali status, derived from its l4_bali (passed by the caller, where the
    /// store is in scope). When present these override the overlay's hand-written status/open — which
    /// could lie ("Open · 100%" on a blocked code). nil → fall back to the overlay fields.
    var realAxes: VerdictAxes? = nil
    var realStatusLabel: String? = nil
    @State private var hover = false
    private var noteText: String { localizedNote ?? related.note }
    /// Human title for the mini-card. The overlay sometimes lacks a localized title; falling back
    /// to `related.code` printed the bare number as if it were the name (regulator-confusing). Use
    /// the note's first clause as a stand-in, else a neutral generic.
    private var cardTitle: String {
        let t0 = (localizedTitle ?? related.title)?.trimmingCharacters(in: .whitespaces) ?? ""
        if !t0.isEmpty, t0 != related.code { return t0 }
        let lead = noteText.split(whereSeparator: { ".—–·".contains($0) }).first.map(String.init)?.trimmingCharacters(in: .whitespaces) ?? ""
        if !lead.isEmpty, lead.count >= 3 { return lead }
        return isID ? "Kode terkait \(related.code)" : "Related code \(related.code)"
    }
    var body: some View {
        Button(action: onTap) {
            VStack(alignment: .leading, spacing: 6) {
                Text(related.code).font(Theme.scalable(12, weight: .bold, design: .monospaced)).foregroundStyle(Theme.accent)
                // Title fallback must NEVER be the raw code (the "63120 as its own name" bug). When the
                // overlay carries no localized title, fall back to the note's lead clause, else a generic.
                Text(cardTitle).font(Theme.scalable(15, weight: .semibold, design: .serif)).foregroundStyle(Theme.white)
                    .fixedSize(horizontal: false, vertical: true)
                if !noteText.isEmpty {
                    Text(noteText).font(Theme.scalable(11)).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
                }
                // Status dot + label: prefer the REAL derived data (realBlocked/realStatusLabel); fall
                // back to the overlay only when the caller didn't resolve the linked code.
                if let label = realStatusLabel {
                    HStack(spacing: 5) {
                        Circle().fill(realAxes.map { a -> Color in
                            if a.nationallyClosed || a.baliBlocked { return Theme.pmaClosed }
                            return a.anyUndetermined ? Theme.faint : Theme.pmaOpen
                        } ?? Theme.faint).frame(width: 6, height: 6)
                        Text(label).font(Theme.scalable(10, weight: .medium)).foregroundStyle(Theme.faint)
                    }
                } else if let st = related.status, !st.isEmpty {
                    HStack(spacing: 5) {
                        // No default: an overlay entry that states neither open nor closed gets a
                        // neutral dot, never the sage of an open code (K2 2026-09-13).
                        Circle().fill(related.open.map { $0 ? Theme.pmaOpen : Theme.pmaClosed } ?? Theme.faint).frame(width: 6, height: 6)
                        // Humanize the status enum — never show raw BLOCCATO_/CHIUSO_/OK_ tokens on a BKPM card.
                        Text(Theme.kbliStatusLabel(st, isID: isID)).font(Theme.scalable(10, weight: .medium)).foregroundStyle(Theme.faint)
                    }
                }
            }
            .padding(12)
            .frame(maxWidth: .infinity, minHeight: 110, alignment: .topLeading)
            .background(Theme.inkLift, in: RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: Theme.radiusMd).strokeBorder(hover ? Theme.hairlineHi : Theme.hairline, lineWidth: 1))
        }
        .buttonStyle(.plain).onHover { hover = $0 }
    }
}

/// A citation group (legal-basis list) — numbered, mono.
struct CitationGroup: View {
    let title: String
    let items: [String]
    var mono: Bool = false
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title.uppercased()).font(Theme.scalable(10, weight: .heavy, design: .monospaced)).tracking(0.5).foregroundStyle(Theme.faint)
            ForEach(Array(items.enumerated()), id: \.offset) { _, it in
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: "checkmark.seal.fill").font(Theme.scalable(11)).foregroundStyle(Theme.pmaOpen.opacity(0.8))
                    Text(it).font(Theme.scalable(12, weight: .medium, design: mono ? .monospaced : .default)).foregroundStyle(Theme.white)
                }
            }
        }
        .padding(.top, 2)
    }
}

/// PB UMKU ancillary-license chips (flow-wrapped). Named `UmkuChips` to avoid colliding with the
/// dossier view's own `FlowChips(items:color:)`.
struct UmkuChips: View {
    let title: String
    let items: [String]
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title.uppercased()).font(Theme.scalable(10, weight: .heavy, design: .monospaced)).tracking(0.5).foregroundStyle(Theme.faint)
            FlexWrap(spacing: 7, lineSpacing: 7) {
                ForEach(Array(items.enumerated()), id: \.offset) { _, it in
                    Text(it).font(Theme.scalable(11, weight: .medium)).foregroundStyle(Theme.muted)
                        .padding(.horizontal, 9).padding(.vertical, 4)
                        .background(Theme.scrim, in: Capsule())
                        .overlay(Capsule().strokeBorder(Theme.hairline, lineWidth: 1))
                }
            }
        }
    }
}

/// Minimal flow/wrap layout (macOS 13+ `Layout`) so pills/chips wrap to the available width.
struct FlexWrap: Layout {
    var spacing: CGFloat = 8
    var lineSpacing: CGFloat = 8
    init(spacing: CGFloat = 8, lineSpacing: CGFloat = 8) { self.spacing = spacing; self.lineSpacing = lineSpacing }
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let maxW = proposal.width ?? 600
        var x: CGFloat = 0, y: CGFloat = 0, lineH: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x + s.width > maxW, x > 0 { x = 0; y += lineH + lineSpacing; lineH = 0 }
            x += s.width + spacing; lineH = max(lineH, s.height)
        }
        return CGSize(width: maxW, height: y + lineH)
    }
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let maxW = bounds.width
        var x: CGFloat = 0, y: CGFloat = 0, lineH: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x + s.width > maxW, x > 0 { x = 0; y += lineH + lineSpacing; lineH = 0 }
            v.place(at: CGPoint(x: bounds.minX + x, y: bounds.minY + y), proposal: ProposedViewSize(s))
            x += s.width + spacing; lineH = max(lineH, s.height)
        }
    }
}
