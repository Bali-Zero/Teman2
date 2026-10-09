import SwiftUI

/// PROTOTYPE — the enriched KBLI detail card (reader-need order, not schema order).
/// Built on the real `intel_2026` editorial layer the JSON already carries, plus a sector hero
/// image. Goal: verdict → at-a-glance → meaning → Bali reality → related → what-changed, so the
/// card reads like a designed brief, not a JSON dump. Register: elegant & restrained (Zero's pick).
///
/// Mapping of a KBLI code → a bundled sector hero image. Falls back to nil (no hero) if unknown.
/// Kept tiny + explicit for the prototype (one code); the real version will key off sektor_id.
enum SectorImage {
    /// KBLI category letter (A-U) from the 2-digit division of the code (standard KBLI 2025 / ISIC
    /// category boundaries). Each category gets a culturally-grounded Indonesian batik background.
    static func category(for code: String) -> Character? {
        guard code.count >= 2, let d = Int(code.prefix(2)) else { return nil }
        switch d {
        case 1...3:   return "A"
        case 5...9:   return "B"
        case 10...33: return "C"
        case 35:      return "D"
        case 36...39: return "E"
        case 41...43: return "F"
        case 45...47: return "G"
        case 49...53: return "H"
        case 55...56: return "I"
        case 58...63: return "J"
        case 64...66: return "K"
        case 68:      return "L"
        case 69...75: return "M"
        case 77...82: return "N"
        case 84:      return "O"
        case 85:      return "P"
        case 86...88: return "Q"
        case 90...93: return "R"
        case 94...96: return "S"
        case 97...98: return "T"
        case 99:      return "U"
        default:      return nil
        }
    }

    private static let slugByCategory: [Character: String] = [
        "A": "sektor-a-agriculture", "B": "sektor-b-mining",    "C": "sektor-c-manufacturing",
        "D": "sektor-d-energy",      "E": "sektor-e-water",      "F": "sektor-f-construction",
        "G": "sektor-g-trade",       "H": "sektor-h-transport",  "I": "sektor-i-hospitality",
        "J": "sektor-j-ict",         "K": "sektor-k-finance",    "L": "sektor-l-realestate",
        "M": "sektor-m-professional","N": "sektor-n-admin",      "O": "sektor-o-public",
        "P": "sektor-p-education",   "Q": "sektor-q-health",     "R": "sektor-r-arts",
        "S": "sektor-s-services",    "T": "sektor-t-household",  "U": "sektor-u-extraterritorial",
    ]

    static func name(for kbli: KBLI) -> String? {
        guard let cat = category(for: kbli.kode) else { return nil }
        return slugByCategory[cat]
    }

    /// Localized human name of a category letter (for the dynamic section line).
    static func categoryName(_ cat: Character, isID: Bool) -> String {
        let en: [Character: String] = [
            "A":"Agriculture, Forestry & Fishing","B":"Mining & Quarrying","C":"Manufacturing",
            "D":"Electricity & Gas","E":"Water Supply & Waste","F":"Construction",
            "G":"Wholesale & Retail Trade","H":"Transportation & Storage","I":"Accommodation & Food Service",
            "J":"Information & Communication","K":"Financial & Insurance","L":"Real Estate",
            "M":"Professional, Scientific & Technical","N":"Administrative & Support","O":"Public Administration & Defence",
            "P":"Education","Q":"Human Health & Social Work","R":"Arts, Entertainment & Recreation",
            "S":"Other Service Activities","T":"Household Activities","U":"Extraterritorial Organizations"]
        let id: [Character: String] = [
            "A":"Pertanian, Kehutanan & Perikanan","B":"Pertambangan & Penggalian","C":"Industri Pengolahan",
            "D":"Listrik & Gas","E":"Pengelolaan Air & Limbah","F":"Konstruksi",
            "G":"Perdagangan Besar & Eceran","H":"Transportasi & Pergudangan","I":"Akomodasi & Makan-Minum",
            "J":"Informasi & Komunikasi","K":"Keuangan & Asuransi","L":"Real Estat",
            "M":"Profesional, Ilmiah & Teknis","N":"Jasa Administrasi & Penunjang","O":"Administrasi Pemerintahan & Pertahanan",
            "P":"Pendidikan","Q":"Kesehatan & Kegiatan Sosial","R":"Kesenian, Hiburan & Rekreasi",
            "S":"Aktivitas Jasa Lainnya","T":"Aktivitas Rumah Tangga","U":"Badan Internasional & Ekstrateritorial"]
        return (isID ? id : en)[cat] ?? (isID ? "Lainnya" : "Other")
    }

    static func load(_ named: String) -> NSImage? {
        for ext in ["png", "jpg"] {
            if let url = Bundle.main.url(forResource: named, withExtension: ext, subdirectory: "sectors")
                ?? Bundle.main.url(forResource: named, withExtension: ext) {
                if let img = NSImage(contentsOf: url) { return img }
            }
            let exe = Bundle.main.bundleURL.appendingPathComponent("Contents/Resources/sectors/\(named).\(ext)")
            if let img = NSImage(contentsOf: exe) { return img }
        }
        return nil
    }
}

struct KBLIDetailRichView: View {
    let kbli: KBLI
    /// In the app the card scrolls; the off-screen snapshot renders it un-scrolled (a ScrollView
    /// inside a fixed NSHostingView doesn't reliably start at the top) so QA captures the full card.
    var scrolls: Bool = true
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager

    var body: some View {
        if scrolls {
            ScrollView { stack }.background(Theme.antracite)
        } else {
            stack.background(Theme.antracite)
        }
    }

    private var stack: some View {
        VStack(alignment: .leading, spacing: 0) {
            hero
            VStack(alignment: .leading, spacing: 22) {
                verdictCard
                ledgerStrip
                if let s = kbli.intel?.whatItMeans, !s.isEmpty { section(lang.t("rich.meaning"), "text.alignleft") { prose(s) } }
                // Gold-Tier "Bali context — reality check" NOT rendered in the app (Zero 2026-06-30):
                // too Bali-centric for the national/KBLI-first surface; prose stays in the overlay
                // for the website. baliContextSection(_:) kept defined but no longer mounted.
                if let s = kbli.intel?.whoThisIsFor, !s.isEmpty { section(lang.t("rich.whofor"), "person.crop.circle") { prose(s) } }
                if let s = kbli.intel?.youllAlsoNeed, !s.isEmpty { relatedSection(s) }
                if let s = kbli.intel?.whatChanged, !s.isEmpty { section(lang.t("rich.changed"), "arrow.triangle.2.circlepath") { prose(s) } }
                askZantaraCTA
                Spacer(minLength: 24)
            }
            .padding(.horizontal, 32)
            .padding(.top, 20)
            .frame(maxWidth: 760, alignment: .leading)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    // MARK: hero — restrained photo BAND + typographic code lockup on the paper
    // (4-LLM panel: photo de-emphasised, code becomes a mono "numbers-as-authority" figure on the
    //  ivory, not a lifestyle-blog overlay. The photo is an accent band, no longer the dominant layer.)

    private var hero: some View {
        let bg: NSImage? = SectorImage.name(for: kbli).flatMap { SectorImage.load($0) }
        return VStack(alignment: .leading, spacing: 0) {
            // thin sector photo band (accent, not hero) — only when an image exists.
            if let img = bg {
                Image(nsImage: img).resizable().aspectRatio(contentMode: .fill)
                    .frame(maxWidth: .infinity).frame(height: 150).clipped()
                    .overlay(alignment: .bottom) {
                        LinearGradient(colors: [.clear, Color.black.opacity(0.10)], startPoint: .top, endPoint: .bottom)
                            .frame(height: 40)
                    }
            }
            codeLockup
                .padding(.horizontal, 32).padding(.top, bg == nil ? 28 : 20).padding(.bottom, 18)
        }
    }

    /// The typographic code lockup: badges row, the code as a large MONO figure (authority, not
    /// dashboard candy), title beneath in a recessed weight. Lives on the ivory paper.
    private var codeLockup: some View {
        let status = kbli.l4Bali?.status ?? ""
        return VStack(alignment: .leading, spacing: 9) {
            HStack(spacing: 8) {
                StatusBadge(icon: "sparkle", label: lang.t("rich.gold"), tone: .neutral, compact: true)
                StatusBadge(icon: Theme.kbliStatusSymbol(status), label: Theme.kbliStatusLabel(status),
                            tone: Theme.tone(status), compact: true)
            }
            Text(kbli.kode)
                .font(Theme.scalable(52, weight: .semibold, design: .monospaced))
                .foregroundStyle(Theme.white).tracking(1)
            Text(kbli.judul)
                .font(Theme.scalable(19, weight: .regular)).foregroundStyle(Theme.muted)
                .fixedSize(horizontal: false, vertical: true)
            FactRule(width: 48).padding(.top, 2)
        }
    }

    // MARK: verdict card — the single most important fact, FIRST (from whatYouNeed)

    /// Pure, headless-callable (`Tests/semantictest`) — the detail card's ownership fragment
    /// delegates entirely to `KBLIVerdict.ownershipLine`. Before OPEN-1 (2026-09-17) this view
    /// re-derived "nationallyClosed" from the raw fields on its own and could label a
    /// TERBATAS/cap-0 record "(TERTUTUP · 0%)" — a status word the record itself never carried —
    /// while the Registry ledger, reading the same record through `KBLIVerdict`, correctly said
    /// "Closed". One rule, once, closes that class for good.
    static func ownershipLine(_ kbli: KBLI, isID: Bool) -> String {
        KBLIVerdict.of(record: kbli).ownershipLine(isID: isID)
    }

    private var verdictCard: some View {
        // The verdict is DERIVED from `KBLIVerdict` (OPEN-1, 2026-09-17), never re-built from the
        // raw PMA fields in this view — that used to let the card contradict the free-prose
        // intel.whatYouNeed (LLM-written before the 2026-06-27 PMA audit) on one side and the
        // Registry ledger's own derivation on the other. Schema-drift scar #9: derive the
        // most-important fact from the ONE rule every surface reads.
        let isID = lang.lang == .id
        let v = KBLIVerdict.of(record: kbli)
        let baliBlocked: Bool = { if case .blocked = v.bali { return true } else { return false } }()
        let nationallyClosed: Bool = { if case .closed = v.national { return true } else { return false } }()
        // Any of these means a foreign-owned PMA cannot freely register this code as-is.
        let cannotProceed = baliBlocked || nationallyClosed

        let color = cannotProceed ? Theme.pmaClosed : Theme.pmaOpen
        let icon = cannotProceed ? "exclamationmark.shield.fill" : "checkmark.shield.fill"
        let title = cannotProceed ? lang.t("rich.verdict.blocked") : lang.t("rich.verdict.open")

        // Build the verdict line from structured data. Priority: national closure first (the hard
        // legal wall), then the Bali moratorium, else the ownership line itself — the SAME
        // projection the Registry ledger and the registry sheet render (`Self.ownershipLine`).
        let verdict: String
        if nationallyClosed {
            let base = Self.ownershipLine(kbli, isID: isID) + "."
            if let route = kbli.pmaRouteTo, !route.isEmpty {
                verdict = base + (isID
                    ? " Untuk PMA, daftarkan \(route) (versi swasta) sebagai gantinya."
                    : " For a PMA, register \(route) (the private-sector version) instead.")
            } else {
                verdict = base + (isID
                    ? " Hanya badan usaha milik Indonesia 100% yang diizinkan."
                    : " Only a 100% Indonesian-owned entity is permitted.")
            }
        } else if baliBlocked {
            // Bali moratorium wins; the reason text is curated, structured-ish data.
            verdict = (kbli.l4Bali?.reason ?? "")
                .replacingOccurrences(of: "**", with: "")
        } else {
            verdict = Self.ownershipLine(kbli, isID: isID)
        }

        // Left-accent border + very light tint (NOT a flooded card) — colour signals state, the
        // ivory paper + a 3pt accent rail carry it. (Panel: "colour signals state, not decoration".)
        return HStack(alignment: .top, spacing: 14) {
            Image(systemName: icon)
                .font(Theme.scalable(20)).foregroundStyle(color)
            VStack(alignment: .leading, spacing: 7) {
                Text(title)
                    .font(Theme.scalable(12, weight: .bold)).tracking(0.8).foregroundStyle(color)
                Text(verdict)
                    .font(Theme.scalable(15)).foregroundStyle(Theme.white).lineSpacing(4)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
        }
        .padding(.vertical, 16).padding(.horizontal, 18)
        .background(
            RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous).fill(color.opacity(0.06))
        )
        .overlay(alignment: .leading) {
            RoundedRectangle(cornerRadius: 2).fill(color).frame(width: 3).padding(.vertical, 6)
        }
        .overlay(RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous).strokeBorder(Theme.hairline, lineWidth: 1))
    }

    // MARK: regulatory ledger — "numbers as authority" in tabular mono, hairline dividers
    // (Panel: ledger aesthetic — tabular mono numbers, hairlines, no four colored mini-cards.)

    /// The risk a PMA client actually faces: the Besar (large) scale — a PT PMA is Besar by law —
    /// else the highest tier across scales, else "—". Never `.first`, which understates on the 541
    /// codes whose risk varies by scale. Shared logic with DossierView.atAGlance.
    static func pmaRisk(_ perSkala: [PerSkala]) -> String {
        func rank(_ r: String) -> Int {
            let u = r.lowercased()
            if u.contains("tinggi") && !u.contains("menengah") { return 4 }
            if u.contains("menengah tinggi") || u.contains("medium_high") { return 3 }
            if u.contains("menengah") || u.contains("medium_low") { return 2 }
            if u.contains("rendah") || u.contains("low") { return 1 }
            return 0
        }
        let besar = perSkala.first(where: { $0.skalaUsaha.contains { $0.lowercased().contains("besar") } })?.kategoriRisiko
        let cats = perSkala.compactMap { $0.kategoriRisiko }.filter { !$0.isEmpty }
        let highest = cats.max(by: { rank($0) < rank($1) })
        return besar ?? highest ?? "—"
    }

    private var ledgerStrip: some View {
        // PMA-relevant risk = the Besar (large) scale — a PT PMA is Besar by law — else the highest
        // across scales. NOT `.first` (Mikro), which understates: 541 codes have risk that varies by
        // scale, so `.first` (often Rendah) would headline a Tinggi code as low. Mirrors DossierView.
        let risk = Self.pmaRisk(kbli.perSkala)
        return HStack(alignment: .top, spacing: 0) {
            fact(lang.t("rich.fact.pma"), kbli.pmaMaxAsing.map { "\($0)%" } ?? (kbli.pmaStatus ?? "—"))
            divider
            fact(lang.t("rich.fact.risk"), risk, accent: Theme.riskColor(risk))
            divider
            fact(lang.t("rich.fact.scales"), "\(kbli.perSkala.count)")
            divider
            fact(lang.t("rich.fact.sector"), kbli.sektorId ?? "—")
        }
        .padding(.vertical, 15).padding(.horizontal, 6)
        .background(RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous).fill(Theme.scrim))
        .overlay(RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous).strokeBorder(Theme.hairline, lineWidth: 1))
    }

    /// One ledger cell: large tabular-mono value (ink), small uppercase label. A thin accent
    /// underline only where a value carries a status (e.g. risk) — otherwise pure ink, no colour.
    private func fact(_ label: String, _ value: String, accent: Color? = nil) -> some View {
        VStack(spacing: 5) {
            Text(value)
                .font(Theme.scalable(21, weight: .semibold, design: .monospaced))
                .foregroundStyle(Theme.white).lineLimit(1).minimumScaleFactor(0.5)
                .overlay(alignment: .bottom) {
                    if let a = accent { Rectangle().fill(a).frame(height: 2).offset(y: 5) }
                }
            Text(label.uppercased()).font(Theme.scalable(9, weight: .semibold)).tracking(0.8)
                .foregroundStyle(Theme.faint)
        }
        .frame(maxWidth: .infinity)
    }

    private var divider: some View { Rectangle().fill(Theme.hairline).frame(width: 1, height: 34) }

    // MARK: Bali context — the "reality check" (markdown with emoji headers)

    private func baliContextSection(_ s: String) -> some View {
        section(lang.t("rich.bali"), "mappin.and.ellipse") {
            MarkdownView(markdown: s)
        }
    }

    // MARK: related codes — lateral exploration (parse the youllAlsoNeed bullets)

    private func relatedSection(_ s: String) -> some View {
        // lines look like "- **56101** — If you provide food service…"
        let items = s.components(separatedBy: "\n").compactMap { line -> (String, String)? in
            let t = line.trimmingCharacters(in: CharacterSet(charactersIn: "- *").union(.whitespaces))
            guard t.isEmpty == false else { return nil }
            // split the leading code from the description on the em-dash / hyphen
            let parts = t.components(separatedBy: "—")
            guard parts.count >= 2 else { return nil }
            let code = parts[0].trimmingCharacters(in: CharacterSet(charactersIn: "* ").union(.whitespaces))
            let desc = parts.dropFirst().joined(separator: "—").trimmingCharacters(in: .whitespaces)
            return code.isEmpty ? nil : (code, desc)
        }
        return section(lang.t("rich.related"), "square.grid.2x2") {
            VStack(spacing: 8) {
                ForEach(Array(items.enumerated()), id: \.offset) { _, item in
                    relatedRow(code: item.0, desc: item.1)
                }
            }
        }
    }

    private func relatedRow(code: String, desc: String) -> some View {
        let target = state.store.code(code)
        let color = target.map { Theme.kbliStatusColor($0.l4Bali?.status ?? "") } ?? Theme.faint
        return HStack(spacing: 12) {
            Text(code).font(Theme.monoFont).foregroundStyle(Theme.white)
                .padding(.horizontal, 9).padding(.vertical, 5)
                .background(RoundedRectangle(cornerRadius: Theme.radiusSm).fill(color.opacity(0.12)))
                .overlay(RoundedRectangle(cornerRadius: Theme.radiusSm).strokeBorder(color.opacity(0.2), lineWidth: 1))
            Text(desc).font(Theme.scalable(13)).foregroundStyle(Theme.muted).lineLimit(2)
                .frame(maxWidth: .infinity, alignment: .leading)
            Image(systemName: "chevron.right").font(Theme.scalable(11, weight: .semibold)).foregroundStyle(Theme.faint)
        }
        .padding(.horizontal, 14).padding(.vertical, 11)
        .background(RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous).fill(Theme.inkLift))
    }

    // MARK: Ask-Zantara CTA — turns the closed lookup into an open conversation

    private var askZantaraCTA: some View {
        Button { state.askZantara(about: kbli) } label: {
            HStack(spacing: 12) {
                ZStack {
                    Circle().fill(Theme.zantara.opacity(0.16)).frame(width: 38, height: 38)
                    Image(systemName: "sparkles").foregroundStyle(Theme.zantara).font(Theme.scalable(16, weight: .semibold))
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text(lang.t("rich.cta.title")).font(Theme.scalable(14, weight: .semibold)).foregroundStyle(Theme.white)
                    Text(kbli.intel?.zantaraOpener ?? lang.t("chat.lead"))
                        .font(Theme.scalable(12)).foregroundStyle(Theme.muted).lineLimit(2)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                Image(systemName: "arrow.right").font(Theme.scalable(13, weight: .bold)).foregroundStyle(Theme.zantara)
            }
            .padding(16)
            .background(RoundedRectangle(cornerRadius: Theme.radiusLg, style: .continuous).fill(Theme.zantara.opacity(0.07)))
            .overlay(RoundedRectangle(cornerRadius: Theme.radiusLg, style: .continuous).strokeBorder(Theme.zantara.opacity(0.18), lineWidth: 1))
        }.buttonStyle(.plain)
    }

    // MARK: building blocks

    @ViewBuilder private func section<C: View>(_ title: String, _ icon: String, @ViewBuilder _ content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 7) {
                Image(systemName: icon).font(Theme.scalable(11, weight: .semibold)).foregroundStyle(Theme.accent)
                Text(title.uppercased()).font(Theme.scalable(11, weight: .bold)).tracking(1.4).foregroundStyle(Theme.faint)
            }
            content()
        }
    }

    private func prose(_ s: String) -> some View {
        MarkdownView(markdown: s)
    }

    /// A badge for the photo hero: colored icon+label on a dark translucent pill, so it reads on
    /// any background image (the soft-tint StatusBadge is for light surfaces, not over photos).
    private func heroBadge(_ icon: String, _ label: String, _ color: Color) -> some View {
        HStack(spacing: 5) {
            Image(systemName: icon).font(Theme.scalable(10, weight: .semibold))
            Text(label).font(Theme.scalable(11, weight: .semibold))
        }
        .foregroundStyle(color)
        .padding(.horizontal, 9).padding(.vertical, 5)
        .background(Capsule().fill(Color.black.opacity(0.45)))
        .overlay(Capsule().strokeBorder(color.opacity(0.45), lineWidth: 1))
    }
}
