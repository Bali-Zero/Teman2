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

    private var content: some View {
        // Wider macro-block spacing (26→32) so the stack of plates groups into "chapters" (C5).
        VStack(alignment: .leading, spacing: 32) {
            // VERDICT-FIRST order (D2, 2026-08-11 — Zero's D2 plan approval, mock showed
            // verdict-on-top): this SUPERSEDES the 2026-06-30 "verdict moved down after related
            // codes" ruling recorded on the two lines below. The binding answer now leads, followed
            // immediately by a 4-up facts inspector (Bali verdict / risk class / national cap /
            // renumber), THEN the supporting exception pills — heroPlate still opens the card.
            if showsIdentityAndVerdict {
                heroPlate
                verdictBanner.padding(.horizontal, PAD)
                factsRow.padding(.horizontal, PAD)
            }
            pillStrip.padding(.horizontal, PAD)       // carries the No-PMA tags (the exception flags)
            description.padding(.horizontal, PAD)
            licensing.padding(.horizontal, PAD)
            // Gold-Tier "Bali context — reality check" intentionally NOT rendered in the app
            // (Zero 2026-06-30): too Bali-centric for the national/KBLI-first surface. The prose
            // stays in kbli-overlay.json `baliContext` for the WEBSITE. baliIntelTeaser / baliIntel
            // view-builders are kept defined but no longer mounted here.
            pp28.padding(.horizontal, PAD)
            roadmap.padding(.horizontal, PAD)
            referenceDrawer.padding(.horizontal, PAD)
            relatedGrid.padding(.horizontal, PAD)
            authorityPlate.padding(.horizontal, PAD)  // Legal Basis → bottom (Zero 2026-06-30, unchanged)
            // BKPM variant strips every link/connection to balizero.com (Zero's ruling) — this
            // plate is the sole one in the app that opens one (readGuide's onTapGesture below).
            if AppVariant.current.showsExternalLinks {
                readGuide.padding(.horizontal, PAD)
            }
            footer            // its own full-width warmer inset, no horizontal pad
        }
        .frame(maxWidth: WIDTH, alignment: .leading)
        .frame(maxWidth: .infinity, alignment: .center)
    }

    private let WIDTH: CGFloat = 760
    private let PAD: CGFloat = 28

    // MARK: 1 · HERO PLATE — big code + title (photo band removed — D1, 2026-08-11, Zero)
    private var heroPlate: some View {
        // D4c (2026-08-11): a near-watermark guilloché wash behind the big numeral — "carta
        // filigranata, mai un pattern" (Zero). Scoped to the hero block only (`.clipped()`, no
        // fixed height beyond a generous estimate of the text stack below it) — never the whole
        // card. Uses `GuillocheBand` (D4Decor.swift) at `decorHeroWashAlpha`, deliberately BELOW
        // the D4 ambient tier per spec.
        ZStack(alignment: .topLeading) {
            GuillocheField(height: 150, alpha: Theme.decorFieldAlpha, rows: 16)
            // D4d.2 (2026-08-11): evolved from the small corner `WatermarkSeal` to the FULL
            // archipelago (Sumatra→Papua, `ArchipelagoConstellation` — D4Decor.swift), per
            // Zero's follow-up on the picked B direction. `showArc: false` — a judgment call,
            // not spec'd either way: the hero is already carrying the big code numeral + two
            // title lines, and the golden-arc's dome (it dips a further ~28% of its own height
            // below frame) felt like one flourish too many stacked behind that much text; flip
            // to `true` in one edit if the reviewer wants it. `Theme.decorFocalAlpha` and
            // `Theme.decor` are already what `ArchipelagoConstellation` uses internally (it
            // exposes no `alpha`/`tint` params to override — see Task 1 report), so no extra
            // opacity/tint modifier is added here. Sized to WIDTH*0.45 (WIDTH=760 → 342pt,
            // inside the requested 40-50% band) via a fixed frame rather than wrapping heroPlate
            // in a GeometryReader — WIDTH is already the known, constant width this ZStack is
            // always laid out at (content's `.frame(maxWidth: WIDTH...)`, heroPlate itself carries
            // no horizontal .padding), so a GeometryReader would only reintroduce indirection for
            // a value already in scope. Kept BEFORE the title VStack below in ZStack's child
            // list (same slot the old WatermarkSeal held) — SwiftUI draws ZStack children
            // back-to-front in declaration order, so it is unconditionally behind the title text
            // no matter how long the title runs; no "hide if title is long" branch needed.
            // D4d ship (2026-08-11, Zero's B2 sign-off): unconditional — no more A/B/C switch.
            ArchipelagoConstellation(showArc: false, height: 150)
                .frame(width: WIDTH * 0.45)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .trailing)
            VStack(alignment: .leading, spacing: 0) {
                // title block on paper (NOT overlaid on photo — the key "elegante e sobrio" decision)
                VStack(alignment: .leading, spacing: 5) {
                    // BIG code lockup — the dominant registry identifier (Zero: "KBLI 55203 lo voglio grande").
                    HStack(alignment: .firstTextBaseline, spacing: 10) {
                        Text("KBLI")
                            .font(Theme.scalable(17, weight: .semibold, design: .monospaced))
                            .tracking(1.0)
                            .foregroundStyle(Theme.muted)
                        Text(kbli.kode)
                            .font(Theme.scalable(46, weight: .bold, design: .monospaced))
                            .foregroundStyle(Theme.accent)
                    }
                    Text(primaryTitle)
                        .font(Theme.scalable(34, weight: .semibold, design: .serif))
                        .foregroundStyle(Theme.white)
                        .accessibilityAddTraits(.isHeader)   // D3b — the card's own top-level title
                    // Secondary line = the OTHER language's title (EN shows the Bahasa name and
                    // vice-versa), so the bilingual pairing is always visible without duplicating.
                    Text(secondaryTitle)
                        .font(Theme.scalable(17, weight: .regular, design: .serif)).italic()
                        .foregroundStyle(Theme.muted)
                    Text(sectorLine)
                        .font(Theme.scalable(11, weight: .medium, design: .monospaced))
                        .tracking(0.6)
                        .foregroundStyle(Theme.faint)
                        .padding(.top, 3)
                }
                .padding(.horizontal, PAD).padding(.top, 16)
            }
        }
        .clipped()
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

    /// The secondary (italic) title = the OTHER language's name. In EN we show the Indonesian
    /// `judul`; in ID we show the English overlay title, else the army-translated `judul`.
    private var secondaryTitle: String {
        if isID {
            return overlays.overlay(kbli.kode, lang: "en")?.title ?? overlays.dataString(kbli.judul, isID: false)
        } else {
            return kbli.judul   // the Indonesian name (always present in the dataset)
        }
    }

    // MARK: 2 · VERDICT PILL STRIP — the 2-second scan
    private var pillStrip: some View {
        FlowPills(pills: verdictPills)
    }

    private var verdictPills: [PillSpec] {
        // The full Bali verdict now lives in `verdictBanner` (moved UP, ahead of the facts row and
        // related codes — D2, 2026-08-11, superseding the 2026-06-30 "moved down" ruling). The
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

    // MARK: 1b · VERDICT BANNER (C1) — the binding answer, full-width, before the supporting pills.
    //
    // K2 2026-09-13: this banner now CONSUMES `KBLIVerdict` instead of re-deriving a verdict from
    // the raw fields. It used to compute `let blocked = l4.blocked || nationallyClosed` locally,
    // which is binary: everything not provably closed fell into the else branch and printed "In
    // Bali: open to a PT PMA" — including the records whose Bali applicability the dataset says
    // it cannot classify, and including records with no `l4_bali` block at all, for which the
    // banner simply rendered NOTHING. The rule lives in one file; this view states it.
    @ViewBuilder private var verdictBanner: some View {
        let v = KBLIVerdict.of(record: kbli)
        let undetermined: Bool = {
            switch v.headline {
            case .nationalUndetermined, .baliUndetermined: return true
            default: return false
            }
        }()
        let closed: Bool = {
            switch v.headline {
            case .nationallyClosed, .baliBlocked: return true
            default: return false
            }
        }()
        let color: Color = undetermined ? Theme.faint : (closed ? Theme.pmaClosed : Theme.pmaOpen)
        let icon = undetermined ? "questionmark.diamond"
                                : (closed ? "xmark.octagon.fill" : "checkmark.seal.fill")
        HStack(alignment: .top, spacing: 12) {
            // D3b: decorative — redundant with the headline text right next to it (the state is
            // stated in words, not implied by the glyph), so it is hidden from VoiceOver rather
            // than announced by its raw SF Symbol name.
            Image(systemName: icon).font(Theme.scalable(20, weight: .semibold)).foregroundStyle(color)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 3) {
                Text(isID ? "PUTUSAN BALI" : "BALI VERDICT")
                    .font(Theme.scalable(10, weight: .heavy, design: .monospaced)).tracking(0.8)
                    .foregroundStyle(color)
                Text(verdictHeadlineText(v))
                    .font(Theme.scalable(19, weight: .semibold, design: .serif))
                    .foregroundStyle(Theme.white).fixedSize(horizontal: false, vertical: true)
                if let subtitle = verdictSubtitle(v) {
                    Text(subtitle)
                        .font(Theme.scalable(12)).foregroundStyle(Theme.muted).lineSpacing(2)
                        .fixedSize(horizontal: false, vertical: true)
                }
                if undetermined {
                    Text(isID
                         ? "Tidak ada verdikt yang dapat dinyatakan dari catatan ini — jangan diperlakukan sebagai terbuka maupun tertutup."
                         : "No verdict can be stated from these records — do not read this as open or as closed.")
                        .font(Theme.scalable(12)).foregroundStyle(Theme.muted).lineSpacing(2)
                        .fixedSize(horizontal: false, vertical: true)
                }
                // confidence demoted to metadata UNDER the answer, not inside it.
                if let c = confidenceLabel(kbli.l4Bali?.confidence) {
                    Text("· \(c)").font(Theme.scalable(11, weight: .medium, design: .monospaced))
                        .foregroundStyle(Theme.faint)
                }
            }
            Spacer(minLength: 0)
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(color.opacity(undetermined ? 0.05 : 0.08), in: RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous))
        .overlay(alignment: .leading) { RoundedRectangle(cornerRadius: 2).fill(color).frame(width: 4).padding(.vertical, 12) }
        .overlay(RoundedRectangle(cornerRadius: Theme.radiusMd).strokeBorder(color.opacity(0.25), lineWidth: 1))
        // D3b: one VoiceOver stop for the whole banner instead of 3-4 separate swipes.
        .accessibilityElement(children: .combine)
    }

    /// `KBLIVerdict` is language-free by design: its reasons are English strings meant for a
    /// machine-readable package. Concatenating one into an Indonesian sentence produced
    /// half-translated prose on a regulator-facing card (council round 3, codex-gpt-5.6-sol), so
    /// in Indonesian the rule's sentence is QUOTED and labelled as such instead of being blended in.
    /// The record's own `l4_bali.reason`, translated where `kbli-reason-i18n` has it and QUOTED
    /// with a label where it does not — never blended untranslated into an Indonesian card.
    private func recordReason(_ r: String) -> String {
        let shown = overlays.reasonString(r, isID: isID)
        return (isID && shown == r) ? "Kutipan catatan (EN): \(r)" : shown
    }

    private func quotedRuleReason(_ r: String?) -> String? {
        guard let r, r.isEmpty == false else { return nil }
        return isID ? "Kutipan aturan (EN): \(r)" : r
    }

    private func verdictHeadlineText(_ v: KBLIVerdict) -> String {
        switch v.headline {
        case .nationallyClosed:
            // The route clause is stated ONLY when the record carries one. The rule emits this
            // same headline for a bare TERTUTUP and for any 0% cap, neither of which necessarily
            // has a private sibling to route to (council round 2, codex-gpt-5.6-sol).
            if let route = kbli.pmaRouteTo, route.isEmpty == false {
                return isID ? "Tertutup untuk PMA (nasional) — alihkan ke kode \(route)"
                            : "Closed to PMA (national) — route to code \(route)"
            }
            return isID ? "Tertutup untuk PMA (nasional)" : "Closed to PMA (national)"
        case .baliBlocked:
            return isID ? "Di Bali: PT PMA tidak dapat mendaftarkan kode ini"
                        : "In Bali: a PT PMA cannot register this code"
        case .nationalUndetermined:
            return isID ? "Posisi nasional tidak dapat ditentukan dari data yang ada"
                        : "The national position is not determined by the available records"
        case .baliUndetermined:
            return isID ? "Penerapan di Bali tidak dapat ditentukan dari data yang ada"
                        : "Bali applicability is not determined by the available records"
        case .openInBali:
            return isID ? "Di Bali: terbuka untuk PT PMA" : "In Bali: open to a PT PMA"
        }
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
                    : "Open to a PT PMA, but scope-dependent: some scopes carry a higher OSS risk class at Besar scale — register by declaring the higher-risk scope."
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

    /// Extract the SHORT punchy bullets from baliContext markdown for the teaser. Returns them
    /// ALL — the teaser shows 3 and `ExpandableList` owns the cap, so the count on the button is
    /// the real one (68 codes carry more than 3; 68112 carries 31).
    private var baliTeaserBullets: [String]? {
        let bc = ovStrict?.baliContext ?? kbli.intel?.baliContext.map { overlays.baliContextString($0, isID: isID) }
        guard let bc else { return nil }
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
    private func riskLabel(_ r: String) -> String { Theme.RiskTier.label(r, isID: isID) }

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
        VStack(alignment: .leading, spacing: 10) {
            SectionLabel(rail: Theme.muted, text: isID ? "Deskripsi" : "Description")
            Text(ovStrict?.meaning ?? overlays.dataString(kbli.uraian, isID: isID))
                .font(Theme.scalable(15, weight: .regular))
                .foregroundStyle(Theme.white)
                .lineSpacing(5)
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
            return u.isEmpty ? "idx:\(s.scopeIndex ?? 0)" : "u:\(u.lowercased())"
        }).count
        let scaleN = Set(kbli.perSkala.flatMap { $0.skalaUsaha }).count
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
            PP28ScalePanel(scales: kbli.perSkala, isID: isID, riskLabel: riskLabel,
                           tr: { overlays.dataString($0, isID: isID) })
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
        let detail = (hasBesar && closedToForeignCapital == false)
            ? (isID ? "PT PMDN (lokal) atau PT PMA (asing) — akta notaris, AHU"
                    : "PT PMDN (local) or PT PMA (foreign) — notary deed, AHU")
            : (isID ? "PT PMDN / CV / Perorangan (lokal, WNI) — akta notaris, AHU"
                    : "PT PMDN / CV / Perorangan (local, WNI) — notary deed, AHU")
        return CodeOverlay.Step(title: title, detail: detail, duration: step.duration)
    }

    @ViewBuilder private var roadmap: some View {
        if let steps = ov?.roadmap, !steps.isEmpty {
            // K2 2026-09-13: "reference only" unless the ONE rule says open in Bali. It read
            // `l4_bali.blocked` alone, so an undetermined record — and a nationally closed one whose
            // Bali flag is false — was handed a "Registration Roadmap" as if the path were open.
            let axes = VerdictAxes(KBLIVerdict.of(record: kbli))
            let blocked = axes.openInBali == false
            let shownSteps = steps.map { scaleAwareStep($0) }
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
        if let pb = ov?.authority?.pbUmku, !pb.isEmpty { return pb }
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
        if let bc = ovStrict?.baliContext ?? kbli.intel?.baliContext.map({ overlays.baliContextString($0, isID: isID) }), !bc.isEmpty {
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
    private var footer: some View {
        VStack(alignment: .leading, spacing: 18) {
            // D4c.1 (2026-08-11, Zero: "non le vedo"): alpha raised from `decorAmbientAlpha * 0.6`
            // (~.06 night / .096 day — invisible in a pixel-verified snapshot) to `decorFocalAlpha`
            // directly, plus a touch more amplitude — a 15pt-tall strip needs MORE presence than a
            // large wash to read at all, not less. Chrome, not probative content (verdicts/tables/
            // citations stay nude per the D4/D4c guardrail).
            // D4d (2026-08-11): swapped for the dense `GuillocheField` — density over amplitude.
            GuillocheField(height: 15, alpha: Theme.decorFieldAlpha, rows: 5)
            SectionLabel(rail: Theme.zantara, text: isID ? "Tanya Zantara" : "Ask Zantara")
            chatFooter
        }
        .padding(.horizontal, PAD).padding(.vertical, 22)
        .frame(maxWidth: WIDTH, alignment: .leading)
        .frame(maxWidth: .infinity, alignment: .center)
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
    /// prose. Bounded, shape-anchored replacements only — never free-text translation.
    private func cleanOpener(_ s: String) -> String {
        var t = s.replacingOccurrences(of: "**", with: "")
        if !isID {
            t = t.replacingOccurrences(of: "Timeline: Otomatis", with: "Timeline: Automatic")
            t = t.replacingOccurrences(of: #"Timeline: (\d+) Hari Kerja"#, with: "Timeline: $1 working days", options: .regularExpression)
            t = t.replacingOccurrences(of: #"Timeline: (\d+) Hari"#, with: "Timeline: $1 days", options: .regularExpression)
            t = t.replacingOccurrences(of: "NIB dan Sertifikat Standar", with: "NIB + Standard Certificate")
            t = t.replacingOccurrences(of: "Authority: Bupati/Walikota", with: "Authority: Regent/Mayor")
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
            return "Tertarik dengan \(kbli.judul) (\(kbli.kode))? Mari saya bantu menelusurinya."
        }
        return "Looking into \(overlays.dataString(kbli.judul, isID: false)) (\(kbli.kode))? Let me walk you through it."
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
                .lineLimit(2)
                .fixedSize(horizontal: false, vertical: true)
            if let caption {
                Text(caption)
                    .font(Theme.scalable(9, weight: .medium))
                    .foregroundStyle(Theme.faint)
                    .lineLimit(2)
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
                            Text(p).font(Theme.scalable(11)).foregroundStyle(Theme.faint).lineLimit(1)
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
    let riskLabel: (String) -> String
    /// Translate a dataset (Indonesian) string to the current language (EN → English, ID → unchanged).
    /// Bound to OverlayStore.dataString so scope names / obligations / requirements aren't macaronic.
    var tr: (String) -> String = { $0 }
    @State private var sel: Int = 0          // selected row index into `scales` (single-scope tab path)
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
        return u.isEmpty ? "idx:\(s.scopeIndex ?? 0)" : "u:\(u.lowercased())"
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
    /// Scale columns actually present, in canonical order, plus any unknown scales appended.
    private var columns: [String] {
        let present = Set(scales.flatMap { $0.skalaUsaha })
        let canon = Self.scaleOrder.filter { present.contains($0) }
        let extra = present.subtracting(Self.scaleOrder).sorted()
        return canon + extra
    }
    /// Short, human label for a collapsed scope key. The raw OSS `uraian` is frequently a noisy
    /// dump — "Kode subklasifikasi: IG002 Kelompok ini mencakup…" (a paragraph), or near-identical
    /// PMSE regulatory boilerplate. `cleanScopeLabel` distils a readable head; then we resolve any
    /// COLLISION against sibling scopes in the same code (49 codes have two scopes whose distilled
    /// heads clip identically — e.g. "Pemanfaatan jasa lingkungan energi/air/panas…" or
    /// "Perpanjangan/Peningkatan IUP Tahap Operasi…"). A regulator must be able to tell them apart.
    private func scopeName(_ key: String) -> String {
        let p = scopeNameParts(key)
        return p.disc.map { "\(p.base) · \($0)" } ?? p.base
    }
    /// The distilled scope label split into (base, discriminator?). The discriminator is the
    /// distinguishing token added when the base collides with a sibling. Returning it SEPARATELY lets
    /// the narrow matrix column render it on its own guaranteed-visible line — appending it to the
    /// tail let a 132pt clip eat it, so long-base rows (e.g. "Pengecer Minuman Beralkohol") collided
    /// visually even though scopeName() was unique (round-3 audit finding).
    private func scopeNameParts(_ key: String) -> (base: String, disc: String?) {
        let ord = (scopeKeys.firstIndex(of: key) ?? 0) + 1
        // Translate the source uraian to the display language BEFORE distilling, so EN shows English
        // scope names (collapse key stays on the raw ID so grouping is language-stable).
        let u = tr(rows(forKey: key).first?.row.scopeUraian ?? "")
        let base = Self.cleanScopeLabel(u, ordinal: ord, isID: isID)
        let siblings = scopeKeys.filter { $0 != key }.map { k -> String in
            let o = (scopeKeys.firstIndex(of: k) ?? 0) + 1
            let su = tr(rows(forKey: k).first?.row.scopeUraian ?? "")
            return Self.cleanScopeLabel(su, ordinal: o, isID: isID)
        }
        guard siblings.contains(base) else { return (base, nil) }
        // Collision → disambiguate ONLY against the scopes that distil to the SAME base.
        let colliders = scopeKeys.filter { $0 != key }.compactMap { k -> String? in
            let o = (scopeKeys.firstIndex(of: k) ?? 0) + 1
            let su = tr(rows(forKey: k).first?.row.scopeUraian ?? "")
            return Self.cleanScopeLabel(su, ordinal: o, isID: isID) == base ? su : nil
        }
        if let disc = Self.distinguishingToken(of: u, against: colliders), !disc.isEmpty {
            return (base, disc)
        }
        return (base, "\(isID ? "Lingkup" : "Scope") \(ord)")
    }
    /// The first word/short-phrase in `target` that does NOT appear in the shared prefix common to
    /// `others` — i.e. the token that makes this scope distinct. Returns up to ~3 words, title-trimmed.
    static func distinguishingToken(of target: String, against others: [String]) -> String? {
        let t = stripHTML(target)
        let tw = t.split(separator: " ").map(String.init)
        guard !tw.isEmpty else { return nil }
        let othersW = others.map { stripHTML($0).split(separator: " ").map(String.init) }
        // walk word positions; the distinguishing token is the first where target diverges from ALL others
        for i in tw.indices {
            let word = tw[i]
            let sharedHere = othersW.contains { ow in i < ow.count && ow[i].lowercased() == word.lowercased() }
            if !sharedHere {
                // take this word + up to 2 following for a meaningful fragment
                let frag = tw[i..<min(i + 3, tw.count)].joined(separator: " ")
                return clip(frag, max: 22)
            }
        }
        return nil
    }
    /// The PerSkala row for (collapsed scope key, scale), if present.
    private func rowFor(scope key: String, scale: String) -> (idx: Int, row: PerSkala)? {
        for (i, s) in scales.enumerated() where scopeKey(s) == key && s.skalaUsaha.contains(scale) {
            return (i, s)
        }
        return nil
    }
    private func riskAbbr(_ r: String?) -> String { Theme.RiskTier.abbr(r, isID: isID) }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if scales.isEmpty {
                Text(isID ? "Tidak ada data skala untuk kode ini." : "No per-scale data for this code.")
                    .font(Theme.scalable(12)).foregroundStyle(Theme.faint)
            } else if scopeIndices.count > Self.matrixMaxScopes {
                scopeListView                    // many scopes (≥6) → compact searchable scope list
            } else if scopeIndices.count > 1 {
                matrixView                       // 2–5 scopes → risk matrix (scope × scale)
            } else {
                singleScopeTabs                  // single scope → clean scale tabs
            }
        }
    }

    /// Above this scope count, a row-per-scope matrix becomes an unreadable wall (71109 has 29).
    /// Switch to a compact, searchable, expandable scope list instead.
    static let matrixMaxScopes = 5

    // MARK: many-scope → compact searchable list (one expandable row per scope)

    @State private var scopeQuery: String = ""
    @State private var expandedScope: String? = nil

    private var scopeListView: some View {
        let scopes = scopeIndices
        let q = scopeQuery.lowercased()
        let filtered = q.isEmpty ? scopes : scopes.filter { key in
            (rows(forKey: key).first?.row.scopeUraian ?? "").lowercased().contains(q)
            || scopeName(key).lowercased().contains(q)
        }
        return VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text((isID ? "\(scopes.count) RUANG LINGKUP" : "\(scopes.count) ACTIVITY SCOPES"))
                    .font(Theme.scalable(10, weight: .heavy, design: .monospaced)).tracking(0.5).foregroundStyle(Theme.faint)
                Spacer()
            }
            // scale-abbreviation legend — the per-row chips read "Mi/Ke/Me/Be"; spell them out once.
            Text(isID ? "Skala: Mi=Mikro · Ke=Kecil · Me=Menengah · Be=Besar"
                      : "Scale: Mi=Micro · Ke=Small · Me=Medium · Be=Large")
                .font(Theme.scalable(9, design: .monospaced)).foregroundStyle(Theme.faint.opacity(0.85))
            // search field — essential when a code carries 12–29 scopes
            HStack(spacing: 6) {
                Image(systemName: "magnifyingglass").font(Theme.scalable(11)).foregroundStyle(Theme.faint)
                TextField(isID ? "Cari lingkup…" : "Filter scopes…", text: $scopeQuery)
                    .textFieldStyle(.plain).font(Theme.scalable(12)).foregroundStyle(Theme.white)
            }
            .padding(.horizontal, 10).padding(.vertical, 7)
            .background(Theme.inkLift, in: RoundedRectangle(cornerRadius: 8))
            .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(Theme.hairline, lineWidth: 1))

            ForEach(filtered, id: \.self) { sc in
                scopeRow(sc)
            }
            if filtered.isEmpty {
                Text(isID ? "Tidak ada lingkup cocok." : "No matching scope.").font(Theme.scalable(12)).foregroundStyle(Theme.faint)
            }
        }
    }

    private func scopeRow(_ sc: String) -> some View {
        let rows = self.rows(forKey: sc).map { (offset: $0.idx, element: $0.row) }
        let expanded = expandedScope == sc
        return VStack(alignment: .leading, spacing: 6) {
            Button { expandedScope = expanded ? nil : sc } label: {
                HStack(spacing: 8) {
                    Image(systemName: expanded ? "chevron.down" : "chevron.right")
                        .font(Theme.scalable(10, weight: .bold)).foregroundStyle(Theme.statutory)
                    Text(scopeName(sc)).font(Theme.scalable(12, weight: .semibold)).foregroundStyle(Theme.white)
                        .lineLimit(expanded ? nil : 1).multilineTextAlignment(.leading)
                    Spacer(minLength: 6)
                    // mini risk chips: a FIXED 4-slot grid in canonical Mikro→Besar order. Each present
                    // scale shows its initial on that scale's `Theme.riskChip` (tiers differ by fill weight;
                    // census rows in measure_contrast.py cite this line). An ABSENT scale shows a dim "·"
                    // placeholder so columns stay aligned and "not applicable" is explicit, never a
                    // silent blank that reads as "no data" (regulator-confusing).
                    HStack(spacing: 3) {
                        ForEach(Self.scaleOrder, id: \.self) { scale in
                            if let row = rows.first(where: { $0.element.skalaUsaha.contains(scale) })?.element {
                                let chip = Theme.riskChip(row.kategoriRisiko)
                                Text(String(scale.prefix(2)))
                                    .font(Theme.scalable(9, weight: .heavy, design: .monospaced))
                                    .foregroundStyle(chip.fg)
                                    .frame(minWidth: 16)
                                    .padding(.horizontal, 5).padding(.vertical, 2)
                                    .background(chip.bg, in: Capsule())
                                    .overlay(Capsule().strokeBorder(chip.border ?? .clear, lineWidth: 1))
                            } else {
                                Text("·")
                                    .font(Theme.scalable(9, weight: .heavy, design: .monospaced))
                                    .foregroundStyle(Theme.faint.opacity(0.4))
                                    .frame(minWidth: 16)
                                    .padding(.horizontal, 5).padding(.vertical, 2)
                                    .background(Theme.faint.opacity(0.06), in: Capsule())
                            }
                        }
                    }
                }
                .contentShape(Rectangle())
            }.buttonStyle(.plain)
            if expanded {
                if let full = rows.first?.element.scopeUraian, !full.isEmpty {
                    Text(tr(full)).font(Theme.scalable(11)).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
                }
                ForEach(rows, id: \.offset) { _, row in cellDetail(row) }
            }
        }
        .padding(10)
        .background(Theme.ink.opacity(0.5), in: RoundedRectangle(cornerRadius: 8))
        .overlay(alignment: .leading) { RoundedRectangle(cornerRadius: 2).fill(Theme.statutory.opacity(0.6)).frame(width: 2).padding(.vertical, 8) }
    }

    // MARK: multi-scope → matrix (scope rows × scale columns), tap a cell for its real detail

    private var matrixView: some View {
        let cols = columns
        let scopes = scopeIndices
        return VStack(alignment: .leading, spacing: 10) {
            Text((isID ? "RISIKO — \(scopes.count) RUANG LINGKUP × \(cols.count) SKALA" : "RISK — \(scopes.count) SCOPES × \(cols.count) SCALES"))
                .font(Theme.scalable(10, weight: .heavy, design: .monospaced)).tracking(0.5).foregroundStyle(Theme.faint)

            // column header: scale names
            HStack(spacing: 6) {
                Text("").frame(width: 150, alignment: .leading)
                ForEach(cols, id: \.self) { c in
                    Text(Self.scaleLabel(c, isID: isID)).font(Theme.scalable(10, weight: .semibold, design: .monospaced))
                        .foregroundStyle(Theme.muted).frame(maxWidth: .infinity)
                }
            }
            // one row per scope
            ForEach(Array(scopes.enumerated()), id: \.offset) { _, sc in
                let parts = scopeNameParts(sc)
                HStack(spacing: 6) {
                    // Round-3 fix: two distinct truncation hazards. (1) When the base distils to a
                    // genuine collision, show the discriminator on its own mono line (clip-proof).
                    // (2) When two bases merely share a long leading prefix (e.g. "Pengecer Minuman
                    // Beralkohol pada Toko Bebas Bea" vs "…Golongan A"), the distinguishing part is at
                    // the TAIL — use .middle truncation so the tail survives the narrow column.
                    VStack(alignment: .leading, spacing: 1) {
                        if let disc = parts.disc {
                            Text(disc)
                                .font(Theme.scalable(9, weight: .heavy, design: .monospaced))
                                .foregroundStyle(Theme.statutory).lineLimit(1).truncationMode(.tail)
                        }
                        Text(parts.base)
                            .font(Theme.scalable(11, weight: .semibold)).foregroundStyle(Theme.white)
                            .lineLimit(parts.disc == nil ? 2 : 1)
                            .truncationMode(.middle)
                    }
                    .frame(width: 150, alignment: .leading)
                    ForEach(cols, id: \.self) { col in
                        cell(scope: sc, scale: col)
                    }
                }
            }
            // legend + tapped-cell detail (full scope description shows in the tapped cell's detail)
            HStack(spacing: 10) {
                legendChip("Rendah", isID ? "R" : "L"); legendChip("Menengah Rendah", "MR")
                legendChip("Menengah Tinggi", "MT"); legendChip("Tinggi", isID ? "T" : "H")
                Text(isID ? "— ketuk sel untuk detail" : "— tap a cell for detail")
                    .font(Theme.scalable(10)).foregroundStyle(Theme.faint)
            }.padding(.top, 2)

            // Default to the PMA-relevant cell (Besar of the first scope, else first existing) so the
            // detail is populated on open — for a regulator the "what does a PT PMA face" row matters.
            let shown = matrixSel ?? defaultCell
            if let mi = shown, mi < scales.count {
                cellDetail(scales[mi])
            }
        }
    }

    /// Index of the cell to show by default: Besar of the first scope, else the highest-risk cell.
    private var defaultCell: Int? {
        if let first = scopeIndices.first,
           let hit = rowFor(scope: first, scale: "Besar") { return hit.idx }
        // else the first existing row
        return scales.indices.first
    }

    private func cell(scope: String, scale: String) -> some View {
        Group {
            if let hit = rowFor(scope: scope, scale: scale) {
                // The tier is the chip's fill weight (spec §1.3 ramp), as in the registry's RiskCell;
                // the selected cell adds a 2 pt copper ring, the selection colour of every table.
                let selected = (matrixSel ?? defaultCell) == hit.idx
                let chip = Theme.riskChip(hit.row.kategoriRisiko)
                Button { matrixSel = (matrixSel == hit.idx ? nil : hit.idx) } label: {
                    Text(riskAbbr(hit.row.kategoriRisiko))
                        .foregroundStyle(chip.fg)
                        .font(Theme.scalable(11, weight: .bold, design: .monospaced))
                        .frame(maxWidth: .infinity, minHeight: 30)
                        .background(chip.bg, in: RoundedRectangle(cornerRadius: 7, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 7).strokeBorder(selected ? Theme.accent : (chip.border ?? .clear),
                                                                                lineWidth: selected ? 2 : 1))
                }.buttonStyle(.plain)
            } else {
                // combination does not exist (real fact: e.g. no "Warung" at Besar scale)
                Text("—").font(Theme.scalable(12)).foregroundStyle(Theme.faint.opacity(0.5))
                    .frame(maxWidth: .infinity, minHeight: 30)
            }
        }
    }

    /// One tier of the matrix legend, drawn as the cells draw it: the riskChip fill, ink and border.
    private func legendChip(_ tier: String, _ t: String) -> some View {
        let chip = Theme.riskChip(tier)
        return Text(t).font(Theme.scalable(9, weight: .semibold, design: .monospaced)).foregroundStyle(chip.fg)
            .padding(.horizontal, 5).padding(.vertical, 1)
            .background(chip.bg, in: RoundedRectangle(cornerRadius: 2))
            .overlay(RoundedRectangle(cornerRadius: 2).strokeBorder(chip.border ?? .clear, lineWidth: 1))
    }

    /// Detail for one tapped (scope, scale) cell: scope label + scale + risk + duties + requirements.
    /// The licensing authorities for ONE scale cell — the FULL list, not just the highest tier.
    /// Verified against the official PP 28/2025 lampiran (2026-06-30): `Kewenangan` is a per-row
    /// (scope × scale × perizinan-step) column. A cell legitimately carries SEVERAL tiers because a
    /// code's licensing has several steps, each signed off at a different level (the automatic/base
    /// step at Bupati/Walikota, the verified/higher step at Gubernur or Menteri). Showing only the
    /// max hid that the base step is a municipal sign-off. It is NOT derivable from the risk/step
    /// (≈8% exceptions — sector-driven), so we show the real data, sorted low→high, deduplicated.
    /// Returns nil when the dataset names none for this scale (line hidden, no placeholder).
    private func scaleAuthority(_ s: PerSkala) -> String? {
        func rank(_ raw: String) -> Int {
            let u = raw.lowercased()
            if u.contains("menteri") || u.contains("kepala badan") || u.contains("lembaga") { return 3 }
            if u.contains("gubernur") { return 2 }
            if u.contains("bupati") || u.contains("walikota") || u.contains("wali kota") { return 1 }
            return 0
        }
        func localized(_ raw: String) -> String {
            let u = raw.lowercased()
            if u.contains("menteri") || u.contains("kepala badan") { return isID ? "Menteri / Kepala Badan" : "Minister / Agency Head" }
            if u.contains("gubernur") { return isID ? "Gubernur" : "Governor" }
            if u.contains("bupati") || u.contains("walikota") || u.contains("wali kota") { return isID ? "Bupati / Walikota" : "Regent / Mayor" }
            return raw
        }
        let levels = s.kewenanganLevels.map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
        guard !levels.isEmpty else { return nil }
        // dedupe by localized label, sort low→high tier (Bupati → Gubernur → Menteri)
        var seen = Set<String>(); var out: [String] = []
        for l in levels.sorted(by: { rank($0) < rank($1) }) {
            let label = localized(l)
            if seen.insert(label).inserted { out.append(label) }
        }
        return out.joined(separator: " · ")
    }

    private func cellDetail(_ s: PerSkala) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Text(s.skalaUsaha.map { Self.scaleLabel($0, isID: isID) }.joined(separator: "/")).font(Theme.scalable(12, weight: .heavy, design: .monospaced)).foregroundStyle(Theme.white)
                if let risk = s.kategoriRisiko {
                    Text(riskLabel(risk)).font(Theme.scalable(11, weight: .semibold)).foregroundStyle(Theme.riskChip(risk).fg)
                        .padding(.horizontal, 8).padding(.vertical, 3)
                        .background(Theme.riskChip(risk).bg, in: Capsule())
                        .overlay(Capsule().strokeBorder(Theme.riskChip(risk).border ?? .clear, lineWidth: 1))
                }
                if let jw = s.jangkaWaktu, !jw.isEmpty {
                    Text(Self.formatJangkaWaktu(jw, isID: isID)).font(Theme.scalable(11, design: .monospaced)).foregroundStyle(Theme.muted)
                }
            }
            // Licensing AUTHORITY for THIS scale (Zero 2026-06-30): moved here from the Authority table,
            // which only showed the single highest tier — misleading, since a Micro/Small operator
            // answers to the Bupati/Walikota while only the large scale reaches the Menteri. Per-scale
            // it is honest. Derived from per_skala.kewenangan; hidden when the dataset is silent.
            if let auth = scaleAuthority(s) {
                HStack(spacing: 5) {
                    Text(isID ? "Kewenangan:" : "Authority:")
                        .font(Theme.scalable(10, weight: .semibold, design: .monospaced)).foregroundStyle(Theme.faint)
                    Text(auth).font(Theme.scalable(11, weight: .medium)).foregroundStyle(Theme.muted)
                }
            }
            if let su = s.scopeUraian, !su.isEmpty {
                Text(tr(su)).font(Theme.scalable(11)).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
            }
            // De-duplicate then translate to the display language (EN→English, ID→unchanged).
            // (e.g. the OJK reporting line repeated twice — a regulator reads it as sloppy.)
            let duties = Self.dedupKeepingOrder(s.kewajiban.map(Self.stripHTML).filter { !$0.isEmpty }).map(tr)
            if !duties.isEmpty {
                scaleList(title: isID ? "KEWAJIBAN PASCA-IZIN" : "POST-LICENSE OBLIGATIONS", items: duties, tint: Theme.yellow)
            }
            let reqs = Self.dedupKeepingOrder(s.persyaratan.map(Self.stripHTML).filter { !$0.isEmpty }).map(tr)
            if !reqs.isEmpty {
                scaleList(title: isID ? "PERSYARATAN" : "REQUIREMENTS", items: reqs, tint: Theme.statutory)
            }
        }
        .padding(.top, 4)
    }

    // MARK: single-scope → clean scale tabs (unchanged behavior)

    /// One representative row per DISTINCT scale, in canonical order, PAIRED with the canonical
    /// scale it represents. When a single scope is backed by several raw blocks (e.g. 23961's 3
    /// collapsed "Seluruh" indices each carrying Mikro→Besar), iterating raw rows produced a 12-tab
    /// "Mi Ke Me Be Mi Ke Me Be…" overrun. This dedups to ≤4 tabs.
    /// We carry the (scale, row) pair so the tab label is the scale THIS tab stands for — NOT the
    /// row's first scale. A row like ["Menengah","Besar"] must label its Besar tab "Large", not
    /// "Medium" (columns.first would hit Menengah first and HIDE that a Besar scale exists — which
    /// for a PT PMA, Besar by law, is the load-bearing fact). (scar #3: a surface mislabels the fact.)
    private var distinctScaleRows: [(scale: String, row: PerSkala)] {
        var out: [(String, PerSkala)] = []
        for scale in columns {   // canonical order, present scales only
            if let row = scales.first(where: { $0.skalaUsaha.contains(scale) }) { out.append((scale, row)) }
        }
        return out.isEmpty ? scales.map { (scale: $0.skalaUsaha.first ?? "", row: $0) } : out
    }

    private var singleScopeTabs: some View {
        let rows = distinctScaleRows
        return VStack(alignment: .leading, spacing: 12) {
            Picker("", selection: $sel) {
                ForEach(Array(rows.enumerated()), id: \.offset) { i, pair in
                    // label by the canonical scale THIS tab represents (not the row's first scale)
                    Text(Self.scaleLabel(pair.scale, isID: isID)).tag(i)
                }
            }
            .pickerStyle(.segmented).labelsHidden().tint(Theme.accent)
            let s = rows[min(sel, rows.count - 1)].row
            HStack(spacing: 8) {
                if let risk = s.kategoriRisiko {
                    Text(riskLabel(risk)).font(Theme.scalable(12, weight: .semibold)).foregroundStyle(Theme.riskColor(risk))
                        .padding(.horizontal, 9).padding(.vertical, 4).background(Theme.riskColor(risk).opacity(0.12), in: Capsule())
                }
                if let jw = s.jangkaWaktu, !jw.isEmpty {
                    Text((isID ? "Proses: " : "Processing: ") + Self.formatJangkaWaktu(jw, isID: isID))
                        .font(Theme.scalable(12, weight: .medium, design: .monospaced)).foregroundStyle(Theme.muted)
                } else {
                    // 133 of the 9095 scale rows carry no `jangka_waktu`. That silence used to
                    // print "Automatic", which is a statement about how the licence is issued —
                    // not something the empty field says.
                    Text(Theme.absent).font(Theme.scalable(12, weight: .medium, design: .monospaced)).foregroundStyle(Theme.faint)
                }
            }
            let duties = Self.dedupKeepingOrder(s.kewajiban.map(Self.stripHTML).filter { !$0.isEmpty }).map(tr)
            if !duties.isEmpty {
                scaleList(title: isID ? "KEWAJIBAN PASCA-IZIN" : "POST-LICENSE OBLIGATIONS", items: duties, tint: Theme.yellow)
            }
            let reqs = Self.dedupKeepingOrder(s.persyaratan.map(Self.stripHTML).filter { !$0.isEmpty }).map(tr)
            if !reqs.isEmpty {
                scaleList(title: isID ? "PERSYARATAN" : "REQUIREMENTS", items: reqs, tint: Theme.statutory)
            }
            if duties.isEmpty && reqs.isEmpty {
                Text(isID ? "Tidak ada kewajiban/persyaratan terdaftar untuk skala ini."
                          : "No obligations/requirements listed for this scale.")
                    .font(Theme.scalable(12)).foregroundStyle(Theme.faint)
            }
        }
    }

    /// A titled bullet list of real per-scale items (obligations or requirements).
    private func scaleList(title: String, items: [String], tint: Color) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(Theme.scalable(10, weight: .heavy, design: .monospaced)).tracking(0.5).foregroundStyle(tint)
            // 1090 scale rows carry more than 8 obligations (05101 carries 34). The old
            // "+26 more" caption named them and gave no way to read them — these are the
            // post-licence duties a registrant is bound by, so the count is now a button.
            ExpandableList(items: items, limit: 8, isID: isID, tint: tint, spacing: 8) { shown in
                ForEach(Array(shown.enumerated()), id: \.offset) { _, t in
                    HStack(alignment: .top, spacing: 8) {
                        Text("›").font(Theme.scalable(13, weight: .bold, design: .monospaced)).foregroundStyle(tint)
                        Text(t).font(Theme.scalable(13)).foregroundStyle(Theme.white).fixedSize(horizontal: false, vertical: true)
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

    /// Distil a readable, distinguishable label from a raw OSS `scope_uraian`. The dataset has
    /// four recurring noise patterns this untangles (verified across 418 multi-scope codes):
    ///   1. SUBKLASIFIKASI — "Kode subklasifikasi: IG002 Kelompok ini mencakup …" / "Kode
    ///      Subklasifikasi Jasa Rekayasa … : RK001" → surface the activity name + its short code.
    ///   2. PMSE boilerplate — long "…Perdagangan Melalui Sistem Elektronik (PPMSE)…" variants →
    ///      canonical short labels (Via marketplace / Direct / All-except-marketplace).
    ///   3. LONG paragraphs — clip to a clause/word boundary, never mid-word, add "…".
    ///   4. "Seluruh" / empty → ordinal fallback ("Scope N") so two of them never read identically.
    static func cleanScopeLabel(_ raw: String, ordinal: Int, isID: Bool) -> String {
        let scopeWord = isID ? "Lingkup" : "Scope"
        let u = stripHTML(raw).trimmingCharacters(in: .whitespacesAndNewlines)
        if u.isEmpty { return "\(scopeWord) \(ordinal)" }
        let low = u.lowercased()

        // 2. PMSE boilerplate → canonical short label. Classify on the LEADING INTENT (word-anchored
        //    prefix), NEVER a bare substring: the operator scope "…yang tidak diKECUALIkan…" contains
        //    "kecuali" as a substring and would over-match the "all-except" branch (cicatrice #3,
        //    guard-over-match). Three distinct legal scopes must stay distinguishable.
        if low.contains("perdagangan melalui sistem elektronik") || low.contains("ppmse") || low.contains("pmse") {
            // "Seluruh, kecuali …PPMSE…" → everything EXCEPT marketplace operators.
            if low.hasPrefix("seluruh, kecuali") || low.hasPrefix("seluruh kecuali") {
                return isID ? "Seluruh kecuali PPMSE" : "All except marketplace"
            }
            // "Selain …PPMSE…" → other-than-marketplace (direct sellers).
            if low.hasPrefix("selain") {
                return isID ? "Selain PPMSE (langsung)" : "Direct (non-marketplace)"
            }
            // Otherwise it describes the PPMSE/PSP operators themselves (often prefixed "1. Penyelenggara…").
            return isID ? "Via PPMSE (marketplace)" : "Marketplace operators (PPMSE)"
        }

        // 1. SUBKLASIFIKASI — pull out the trailing code and the activity head.
        //    Pattern A: "Kode Subklasifikasi <Activity> : RK001"
        //    Pattern B: "Kode subklasifikasi: IG002 Kelompok ini mencakup <paragraph>"
        if low.hasPrefix("kode subklasifikasi") || low.hasPrefix("kode sub") {
            // trailing short code like ": RK001" / "IG002"
            var code = ""
            if let m = u.range(of: "[A-Z]{2}\\d{3}", options: .regularExpression) { code = String(u[m]) }
            // strip the "Kode subklasifikasi[:]" prefix and any "Kelompok ini mencakup…" tail
            var body = u.replacingOccurrences(of: "(?i)^kode\\s+subklasifikasi\\s*:?\\s*", with: "", options: .regularExpression)
            // drop a leading bare code token (e.g. "IG002 ")
            body = body.replacingOccurrences(of: "^[A-Z]{2}\\d{3}\\s*", with: "", options: .regularExpression)
            // cut the boilerplate descriptor tail
            if let r = body.range(of: "Kelompok ini mencakup", options: .caseInsensitive) { body = String(body[..<r.lowerBound]) }
            if let r = body.range(of: "Usaha dalam kelompok ini", options: .caseInsensitive) { body = String(body[..<r.lowerBound]) }
            // also drop a trailing ": CODE" we already captured
            body = body.replacingOccurrences(of: "\\s*:\\s*[A-Z]{2}\\d{3}\\s*$", with: "", options: .regularExpression)
            body = body.trimmingCharacters(in: CharacterSet(charactersIn: " :—–-"))
            // If nothing meaningful survives (the whole label WAS the boilerplate paragraph),
            // fall back to the code itself rather than re-showing the noise.
            if body.isEmpty {
                if !code.isEmpty { return isID ? "Subkl. \(code)" : "Subclass \(code)" }
                return clip(u, max: 30)
            }
            let head = clip(body, max: 30)
            return code.isEmpty ? head : "\(head) · \(code)"
        }

        // 3 & 4. Plain label. "Seluruh" alone is ambiguous → ordinal-qualify.
        if low == "seluruh" { return isID ? "Seluruh (\(scopeWord) \(ordinal))" : "All (\(scopeWord) \(ordinal))" }
        return clip(u, max: 38)
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

    /// Word-boundary clip (never mid-word) with ellipsis.
    static func clip(_ s: String, max: Int) -> String {
        let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.count <= max { return t }
        // prefer a clause boundary (comma / paren) before `max`
        let prefix = String(t.prefix(max))
        if let comma = prefix.range(of: ",", options: .backwards), prefix.distance(from: prefix.startIndex, to: comma.lowerBound) > max / 2 {
            return String(prefix[..<comma.lowerBound]) + "…"
        }
        // else last whole word
        if let sp = prefix.range(of: " ", options: .backwards) {
            return String(prefix[..<sp.lowerBound]) + "…"
        }
        return prefix + "…"
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
                Text(note).font(Theme.scalable(13)).foregroundStyle(Theme.muted).lineLimit(2)
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
                    .lineLimit(2).fixedSize(horizontal: false, vertical: true)
                if !noteText.isEmpty {
                    Text(noteText).font(Theme.scalable(11)).foregroundStyle(Theme.muted).lineLimit(2).fixedSize(horizontal: false, vertical: true)
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
