import SwiftUI

/// Design tokens — "Warm Paper" LIGHT theme (2026-06-24, Zero's choice): a calm, restful
/// ivory/sand base with soft, full pastel accents. Token NAMES are kept stable
/// (antracite/ink/inkLift, white, yellow, red, accent, zantara…) so the 100+ call-sites don't
/// need renaming — only their hex values flip from the dark "Claude Night" theme to this light one.
/// All accents are tuned a touch deeper/saturated so they READ on a light background (pastel but
/// full, not washed out); all text is warm ink with WCAG-AA contrast on the ivory surfaces.
enum Theme {
    /// Two palettes share the SAME token names so the 100+ call-sites (`Theme.antracite`, `.accent`,
    /// `.white`…) never change — only which palette they resolve to. `.light` = "Warm Paper";
    /// `.dark` = "Night" (anthracite grey, white text, ORANGE protagonist) — added 2026-06-24 (Zero).
    enum Mode { case light, dark }
    /// Live theme mode. Driven by `ThemeManager`, synced from SYSTEM appearance by default (D3a,
    /// 2026-08-11) OR from a persisted user override (D3a.2, 2026-08-11 — `RootView.themeToggle` /
    /// `@AppStorage("themeOverride")`); the `.dark` seed here is just the placeholder value before
    /// RootView's first-render sync runs. The tokens below are computed `var`s, so they re-resolve
    /// on every read once `mode` changes.
    static var mode: Mode = .dark
    /// D3b (2026-08-11): Increase Contrast — driven ONE-WAY from system `@Environment(\.colorSchemeContrast)`
    /// via `ThemeManager.contrastIncreased`, same seam/pattern as `mode` (RootView observes, pushes
    /// in; `ThemeManager`'s `@Published` change is what actually triggers the re-render that makes
    /// these tokens re-resolve — this flag alone changing wouldn't redraw anything on its own).
    static var contrastIncreased: Bool = false

    /// D4d QA override (2026-08-11): `SNAPSHOT_FORCE_THEME=day|light` or `night|dark` forces the
    /// theme for the off-screen `--snapshot` renderer regardless of `mode`, so the same code path
    /// can render both day and night comparison PNGs without touching `Theme.mode` twice. Falls
    /// through to the existing `mode`-driven logic when unset — `Snapshot.swift` already sets
    /// `Theme.mode` from `KBLI_THEME=light|dark` before constructing its view, so this is an
    /// additional override layered on top of that existing mechanism, not a replacement for it.
    private static var isDark: Bool {
        if let forced = ProcessInfo.processInfo.environment["SNAPSHOT_FORCE_THEME"] {
            let v = forced.lowercased()
            if v == "day" || v == "light" { return false }
            if v == "night" || v == "dark" { return true }
        }
        return mode == .dark
    }
    private static func pick(_ light: UInt32, _ dark: UInt32) -> Color { Color(hex: isDark ? dark : light) }
    /// Increase-Contrast variant of `pick`: when the user has Increase Contrast on, resolve to a
    /// SEPARATE, independently WCAG-verified hex pair instead of the normal one — not a runtime
    /// blend, an actual measured swap. `lightHC`/`darkHC` ratios against this app's two backgrounds
    /// (antracite 0xF5F1E8 light / 0x2F3034 dark) were computed with a throwaway WCAG script
    /// (`/tmp/d3b_contrast_check.py`, D3b contrast pass) by blending each existing color toward its
    /// mode's extreme (white in dark mode, black in light mode) until the ratio reached AAA (7:1) —
    /// every one of the 4 semantic-color families below cleared 7:1 well inside a 0.05–0.20 blend.
    private static func pickAA(_ light: UInt32, _ dark: UInt32, lightHC: UInt32, darkHC: UInt32) -> Color {
        guard contrastIncreased else { return pick(light, dark) }
        return Color(hex: isDark ? darkHC : lightHC)
    }

    // MARK: Backgrounds — light: warm ivory/sand · dark: ANTHRACITE GREY.
    // "Proposta" palette (Zero, 2026-08-11) — panel-approved, AA-verified as foreground colors on
    // this surface ramp via a throwaway WCAG script (/tmp/kbli_contrast_check.py, D1 contrast audit).
    static var antracite: Color { pick(0xF5F1E8, 0x2F3034) } // window bg
    static var ink: Color       { pick(0xF8F4EC, 0x34353A) } // elevated panel / sidebar
    static var inkLift: Color   { pick(0xFFFCF7, 0x3E3F45) } // raised card / row
    static var surfaceHi: Color { pick(0xEAE2D5, 0x47484E) } // surface hover / footer inset

    // MARK: Accent — terracotta (light) → warm orange (dark, the star color)
    static var accent: Color    { pick(0x995026, 0xF5AA72) } // terracotta → warm orange
    static var accentHi: Color  { pick(0x7F3E1C, 0xFFBA86) } // orange hover/pressed

    // `red` = danger/closed semantic. Same hex family as pmaClosed/riskHigh — boosts together.
    static var red: Color       { pickAA(0x9F3C3B, 0xFF9F98, lightHC: 0x873332, darkHC: 0xFFA9A2) }

    // MARK: Secondary — periwinkle = ZANTARA ONLY (reserved). Do NOT use for data/rails (C2).
    static var zantara: Color   { pick(0x4E5DB7, 0xB9B5FF) } // periwinkle
    // `statutory` = the renumber / national-reference / non-Zantara blue. Distinct from periwinkle so
    // periwinkle stays uniquely Zantara (C2, 2026-06-24).
    static var statutory: Color { pickAA(0x29639E, 0x91C2F7, lightHC: 0x214F7E, darkHC: 0x96C5F7) } // statutory/reference blue
    static var blue: Color      { pickAA(0x29639E, 0x91C2F7, lightHC: 0x214F7E, darkHC: 0x96C5F7) } // risk-medium-low (kept as alias)

    // MARK: Highlight — amber/gold. Same hex family as pmaRestricted/riskMediumHigh — boosts together.
    static var yellow: Color    { pickAA(0x765A00, 0xEBD077, lightHC: 0x644C00, darkHC: 0xECD27E) } // amber (facts, numbers, gold-tier)

    // MARK: Text — warm ink on ivory · cool near-white / neutral greys on anthracite.
    static var white: Color     { pick(0x302D29, 0xF5F3EE) } // PRIMARY TEXT
    // D3b Increase Contrast: "muted → text" — under increased contrast the secondary-text tier
    // stops being a dimmer shade and just IS the primary text color (per instruction, `faint` is
    // deliberately untouched — narrower than "every secondary tone gets boosted").
    static var muted: Color     { contrastIncreased ? white : pick(0x625D55, 0xD0CCC4) } // secondary text
    static var faint: Color     { pick(0x686159, 0xBCB8B1) } // de-emphasised labels

    // MARK: Semantic status (open / restricted / closed). D3b: each family gets an independently
    // WCAG-verified Increase-Contrast hex pair (see `pickAA` doc-comment) — all 4 families reach
    // AAA (>=7:1) against this app's antracite backgrounds when Increase Contrast is on.
    static var pmaOpen: Color       { pickAA(0x176F4B, 0x6FD2B0, lightHC: 0x12593C, darkHC: 0x76D4B4) } // sage → brighter sage on dark
    static var pmaRestricted: Color { pickAA(0x765A00, 0xEBD077, lightHC: 0x644C00, darkHC: 0xECD27E) }
    static var pmaClosed: Color     { pickAA(0x9F3C3B, 0xFF9F98, lightHC: 0x873332, darkHC: 0xFFA9A2) }
    static var green: Color         { pickAA(0x176F4B, 0x6FD2B0, lightHC: 0x12593C, darkHC: 0x76D4B4) }

    static var riskLow: Color        { pickAA(0x176F4B, 0x6FD2B0, lightHC: 0x12593C, darkHC: 0x76D4B4) }
    static var riskMediumLow: Color  { pickAA(0x29639E, 0x91C2F7, lightHC: 0x214F7E, darkHC: 0x96C5F7) }
    static var riskMediumHigh: Color { pickAA(0x765A00, 0xEBD077, lightHC: 0x644C00, darkHC: 0xECD27E) }
    static var riskHigh: Color       { pickAA(0x9F3C3B, 0xFF9F98, lightHC: 0x873332, darkHC: 0xFFA9A2) }

    // MARK: Borders / fills — light: soft BLACK at low alpha · dark: soft WHITE at low alpha.
    // D3b Increase Contrast: hairline alpha ×2 (per instruction — literal doubling, not re-measured).
    static var hairline: Color   { isDark ? Color.white.opacity(contrastIncreased ? 0.28 : 0.14) : Color.black.opacity(contrastIncreased ? 0.20 : 0.10) }
    static var hairlineHi: Color { isDark ? Color.white.opacity(contrastIncreased ? 0.44 : 0.22) : Color.black.opacity(contrastIncreased ? 0.32 : 0.16) }
    static var scrim: Color      { isDark ? Color.white.opacity(0.05) : Color.black.opacity(0.04) }
    static var overlay: Color    { Color.black.opacity(0.45) } // badge backdrop over hero images (both)

    // MARK: Icon-on-fill ink — BZLogo's fallback glyph and ChatView's send-button glyph paint a
    // FIXED glyph directly on a solid Theme.accent / Theme.zantara circle (not the usual
    // color-as-text-on-opacity-tint pattern used everywhere else). Night accent/zantara are light
    // enough for a dark glyph (AAA, 7.3-7.5:1); day accent/zantara are dark terracotta/indigo, so a
    // dark glyph FAILS WCAG (2.38:1 / 2.41:1, measured) — flip to a light glyph in day mode instead
    // (5.9:1 / 5.9:1, measured). D1 contrast audit, 2026-08-11.
    static var iconOnAccentFill: Color  { pick(0xFFFFFF, 0x2B2B2B) }
    static var iconOnZantaraFill: Color { pick(0xFFFFFF, 0x2B2B2B) }

    // MARK: D4 "Anima Indonesiana" decorative tokens (2026-08-11, Zero-approved — values ported
    // VERBATIM from the reference draft's own `P` palette object, `kbli-d4-draft.html` §script,
    // now available locally; this replaces an earlier v1 pass built before the draft was reachable,
    // which mis-read the draft's `lw` field as a third alpha tier — it is a STROKE WIDTH in points,
    // not an opacity, and `decorLineAlpha` never existed in the source). Two colors: `decor` is the
    // general line-art color (archipelago dots, cartographic dashed lines, sidebar guilloché band,
    // chat medallion rosette); `decorGold` is reserved for the 1945→2045 arc only. Four named alpha/
    // metric tiers, each mapped 1:1 to a `P[mode]` field: `decorAmbientAlpha`=`amb` (background wash,
    // lowest), `decorFocalAlpha`=`focal` (coastline dots/rings, medium), `decorArcAlpha`=`arc` (the
    // golden arc's own stroke — a dedicated tier, distinct from focal), `decorLineWidth`=`lw` (the
    // guilloché/rosette stroke WIDTH in points — 0.55 night / 0.85 day, NOT an opacity),
    // `decorDotRadius`=`dotR` (coastline dot radius in points). The draft's `dot` field (.30 night /
    // .5 day) is intentionally NOT ported as a token: it feeds a JS ternary (`p.dot ? .5 : .3`) that
    // is always-truthy on a non-zero number, so the value Zero actually saw rendered is a flat `.5`
    // in both modes — call sites hardcode `0.5` with a comment rather than adding a token that would
    // misleadingly imply mode-awareness that was never live. Apply via `Theme.decor.opacity(Theme.decorFocalAlpha)`.
    private static func pickD(_ light: Double, _ dark: Double) -> Double { isDark ? dark : light }
    static var decor: Color              { pick(0x6E3F2C, 0xE9B878) }
    static var decorGold: Color          { pick(0x8A6524, 0xC99A4A) }
    static var decorAmbientAlpha: Double { pickD(0.16, 0.10) }   // P[mode].amb
    static var decorFocalAlpha: Double   { pickD(0.24, 0.16) }   // P[mode].focal
    static var decorArcAlpha: Double     { pickD(0.72, 0.55) }   // P[mode].arc
    static var decorLineWidth: CGFloat   { pickD(0.85, 0.55) }   // P[mode].lw — a WIDTH, not an alpha
    static var decorDotRadius: CGFloat   { pickD(1.15, 0.9) }    // P[mode].dotR
    /// D4c (2026-08-11, Zero's follow-up GO — "anima anche la navigazione normale, sempre
    /// elegante"): the hero-plate watermark wash, DELIBERATELY below `decorAmbientAlpha` (a
    /// background wash BEHIND the big code numeral must read as watermarked paper, never as a
    /// pattern competing with the numeral) — exact values from Zero's spec, not derived from the
    /// existing amb/focal tiers. Raised 2026-08-11 (D4c.1, Zero: "non le vedo") from an initial pickD(0.09,
    /// 0.05) that rendered too faint to perceive even in a pixel-verified snapshot — this value is
    /// close to `decorFocalAlpha`, a tier already proven visible (the archipelago coastline dots).
    static var decorHeroWashAlpha: Double { pickD(0.26, 0.18) }
    /// D4c: the sidebar footer band was "quasi invisibile" at the D4 launch value
    /// (`decorAmbientAlpha + 0.04` = .20 day / .14 night) — Zero asked for more presence without
    /// losing restraint. Exact target values from spec (day .20→.24, night .14→.17), not a formula
    /// offset (the day/night deltas aren't equal, so a flat "+0.0x" can't hit both).
    static var decorSidebarBandAlpha: Double { pickD(0.24, 0.17) }
    /// D4d (2026-08-11): per-row alpha for the dense `GuillocheField` texture (`D4Decor.swift`) —
    /// the prior pass hardcoded `alpha: 0.06` at all 3 call sites, tuned only against the dark/
    /// night anthracite background and never checked against the light/ivory one. night=0.06 is
    /// the already-proven-right value (kept exact); day=0.09 follows the same ~1.5x day/night
    /// ratio every other decor tier here uses (e.g. `decorFocalAlpha` 0.24/0.16, `decorAmbientAlpha`
    /// 0.16/0.10) rather than a flat offset.
    static var decorFieldAlpha: Double { pickD(0.09, 0.06) }
    /// D4 guardrail: decorations must never compete with legibility. Every decorative view/Canvas
    /// checks this (and additionally sets `.allowsHitTesting(false)` + `.accessibilityHidden(true)`,
    /// unconditionally) rather than just dialing alpha down, so Increase Contrast removes them
    /// entirely instead of leaving a fainter-but-still-present distraction.
    static var decorationsVisible: Bool { !contrastIncreased }

    // MARK: KBLI Bali-status semantic colors (l4_bali.status → color + symbol)
    // 3-state to match the web: open (green) / restricted (amber) / closed (red).
    // `blocked` is the SINGLE source of truth (the l4_bali.blocked bool the verdict banner uses).
    // The status STRING is only a presentation hint — `BLOCCATO_DIPENDE_SCOPE` carries the "BLOCCATO"
    // prefix yet has blocked=false (scope-registrable), so a prefix-match would paint the list dot red
    // while the banner is green. When `blocked` is known it overrides the prefix; pass nil to fall back
    // to the string (legacy callers without the record).
    static func kbliStatusColor(_ status: String, blocked: Bool? = nil) -> Color {
        if let b = blocked { return b ? pmaClosed : pmaOpen }
        if status.hasPrefix("OK_") || status.hasPrefix("APERTO") || status == "TERBUKA" { return pmaOpen }
        if status == "TERBATAS" { return pmaRestricted }
        if status.hasPrefix("BLOCCATO") || status.hasPrefix("CHIUSO") || status == "TERTUTUP" { return pmaClosed }
        return faint   // NEEDS_REVIEW_* and unknown
    }

    static func kbliStatusSymbol(_ status: String, blocked: Bool? = nil) -> String {
        if let b = blocked { return b ? "xmark.octagon.fill" : "checkmark.circle.fill" }
        if status.hasPrefix("OK_") || status.hasPrefix("APERTO") || status == "TERBUKA" { return "checkmark.circle.fill" }
        if status == "TERBATAS" { return "exclamationmark.triangle.fill" }
        if status.hasPrefix("BLOCCATO") || status.hasPrefix("CHIUSO") || status == "TERTUTUP" { return "xmark.octagon.fill" }
        return "questionmark.circle"
    }

    /// A short human label for a Bali status (used inside status badges).
    static func kbliStatusLabel(_ status: String) -> String { kbliStatusLabel(status, isID: false) }

    /// Bilingual, enum-precise human label. The dataset carries internal tokens (some Italian:
    /// BLOCCATO/CHIUSO) that must NEVER reach a regulator-facing card verbatim — this maps every
    /// known token to a clean phrase. Unknown tokens degrade to a title-cased, de-underscored form
    /// rather than the raw SCREAMING_SNAKE enum.
    static func kbliStatusLabel(_ status: String, isID: Bool) -> String {
        let s = status.trimmingCharacters(in: .whitespaces)
        let su = s.uppercased()
        switch su {
        case "OK_OR_HIGHER_RISK":        return isID ? "Terbuka (cek risiko)" : "Open (verify risk)"
        case "TERBUKA", "TERBUKA · 100%", "OPEN · 100%": return isID ? "Terbuka 100%" : "Open 100%"
        case "TERBATAS":                 return isID ? "Terbatas" : "Restricted"
        case "BLOCCATO_CLASSE_RISCHIO":  return isID ? "Tertutup (kelas risiko)" : "Closed (risk class)"
        case "BLOCCATO_DIPENDE_SCOPE":   return isID ? "Tergantung lingkup" : "Depends on scope"
        case "CHIUSO_PMA_NO_BESAR":      return isID ? "Tertutup PMA (skala Besar)" : "Closed to PMA (Besar)"
        case "CHIUSO_BALI":              return isID ? "Tertutup di Bali" : "Closed in Bali"
        case "CHIUSO_BALI_PROPOSTO":     return isID ? "Diusulkan tertutup (Bali)" : "Proposed closed (Bali)"
        // l4 verdicts from the NB-3 moratorium-by-risk-tier resolution (2026-06-28):
        case "APERTO_BALI_RISCHIO_ALTO": return isID ? "Terbuka di Bali (risiko tinggi)" : "Open in Bali (high-risk tier)"
        case "CHIUSO_MORATORIA_BALI":    return isID ? "Tertutup (moratorium Bali)" : "Closed (Bali moratorium)"
        case "CHIUSO_REGOLATORE_SETTORIALE": return isID ? "Tertutup (regulator sektoral)" : "Closed (sector regulator)"
        case "TERTUTUP":                 return isID ? "Tertutup" : "Closed to PMA"
        case "NEEDS_REVIEW_NO_OSS_SCOPE": return isID ? "Perlu telaah" : "Needs review"
        default: break
        }
        // generic prefix coverage for any future variant
        if su.hasPrefix("OK_") || su.hasPrefix("APERTO") { return isID ? "Terbuka" : "Open" }
        if su.hasPrefix("BLOCCATO") || su.hasPrefix("CHIUSO") { return isID ? "Tertutup" : "Closed" }
        if su.hasPrefix("NEEDS_REVIEW") { return isID ? "Perlu telaah" : "Needs review" }
        // last resort: never show raw SCREAMING_SNAKE — title-case it
        if su.contains("_") {
            // `String($0.prefix(1))` and not `$0.prefix(1)`: same first CHARACTER, spelled the way
            // the truncation scan in Tests/uitest recognises as a character operation rather than a
            // silently capped list. One spelling for one meaning beats an exception in the scanner.
            return s.split(separator: "_").map { String($0.prefix(1)).uppercased() + $0.dropFirst().lowercased() }.joined(separator: " ")
        }
        return s
    }

    // MARK: Risk-category color (kategori_risiko → color)
    // ORDER IS LOAD-BEARING: the dataset uses space-separated compound labels ("Menengah Tinggi",
    // "Menengah Rendah"). The compound forms MUST be tested before the bare "Tinggi"/"Rendah",
    // otherwise "Menengah Tinggi" matches contains("TINGGI") and mis-renders as High (2455 rows),
    // and "Menengah Rendah" matches contains("RENDAH") and mis-renders as Low (1574 rows).
    static func riskColor(_ risk: String) -> Color {
        let r = risk.uppercased()
        if r.contains("MENENGAH TINGGI") || r.contains("MENENGAH_TINGGI") || r.contains("MEDIUM_HIGH") || r == "MT" { return riskMediumHigh }
        if r.contains("MENENGAH RENDAH") || r.contains("MENENGAH_RENDAH") || r.contains("MEDIUM_LOW") || r == "MR" { return riskMediumLow }
        if r.contains("TINGGI") || r.contains("HIGH") || r == "H" { return riskHigh }
        if r.contains("RENDAH") || r.contains("LOW") || r == "R" || r == "L" { return riskLow }
        return faint
    }

    // MARK: Absent data (2026-09-13) — one silence, one rendering, never a default
    /// What a surface prints where the corpus carries nothing.
    ///
    /// 217 of the 1559 records carry no `per_skala` at all, so no `kategori_risiko` at any scale.
    /// The card used to print "Medium-Low Risk" on every one of them — a literal fallback that
    /// turned a government risk tier the data never states into an asserted one, and then every
    /// statement DERIVED from the risk tier (licence type, processing mode) inherited the
    /// assertion. Absence is a fact about the corpus and is rendered as one.
    static let absent = "—"

    /// The OSS risk tier of a record, and everything the decree derives from it — each answering
    /// `nil`/`Theme.absent` when the corpus carries no tier, so no caller can fabricate one.
    ///
    /// This is the single place that reads `kategori_risiko`: the besar-or-highest rule used to
    /// live in three near-copies across the cards, which is how one of them could keep a default
    /// the others had already dropped.
    enum RiskTier {
        /// Severity rank (higher = riskier). 0 = present but unrecognised, which is NOT absence.
        /// ORDER IS LOAD-BEARING, same reason as `riskColor`: compound labels before bare ones.
        static func rank(_ r: String) -> Int {
            let u = r.lowercased()
            if u.contains("menengah rendah") || u.contains("medium_low") { return 2 }
            if u.contains("menengah tinggi") || u.contains("medium_high") { return 3 }
            if u.contains("tinggi") || u.contains("high") { return 4 }
            if u.contains("rendah") || u.contains("low") { return 1 }
            return 0
        }

        /// Every tier the record actually states, in corpus order. Empty ⇒ the corpus is silent.
        static func stated(_ perSkala: [PerSkala]) -> [String] {
            perSkala.compactMap { $0.kategoriRisiko }.filter { !$0.isEmpty }
        }

        /// The PMA-relevant tier: the Besar (large) scale — a PT PMA is Usaha Besar by law —
        /// else the highest tier stated. NEVER `.first` (Mikro understates: the "Medium-Low
        /// restaurant" trap). `nil` when the corpus states none.
        static func category(_ perSkala: [PerSkala]) -> String? {
            for s in perSkala where s.skalaUsaha.contains(where: { $0.lowercased().contains("besar") }) {
                if let k = s.kategoriRisiko, !k.isEmpty { return k }
            }
            return stated(perSkala).max(by: { rank($0) < rank($1) })
        }

        /// Bilingual tier label. Unrecognised-but-present values are shown verbatim rather than
        /// guessed at.
        static func label(_ r: String, isID: Bool) -> String {
            let u = r.lowercased()
            if u.contains("menengah rendah") || u.contains("medium_low") { return isID ? "Risiko Menengah-Rendah" : "Medium-Low Risk" }
            if u.contains("menengah tinggi") || u.contains("medium_high") { return isID ? "Risiko Menengah-Tinggi" : "Medium-High Risk" }
            if u.contains("tinggi") || u.contains("high") { return isID ? "Risiko Tinggi" : "High Risk" }
            if u.contains("rendah") || u.contains("low") { return isID ? "Risiko Rendah" : "Low Risk" }
            return r
        }

        /// One-or-two-letter matrix abbreviation. Absent ⇒ `Theme.absent`, matching the "this
        /// scope×scale row does not exist" cell right next to it; "?" stays reserved for a value
        /// that IS stated and is not recognised.
        static func abbr(_ r: String?, isID: Bool) -> String {
            guard let r, !r.isEmpty else { return Theme.absent }
            let u = r.lowercased()
            if u.contains("menengah rendah") { return "MR" }
            if u.contains("menengah tinggi") { return "MT" }
            if u.contains("tinggi") { return isID ? "T" : "H" }
            if u.contains("rendah") { return isID ? "R" : "L" }
            return "?"
        }

        /// An honest summary across scales: one label when uniform, "lowest → highest" when the
        /// tier varies, `Theme.absent` when the corpus states none.
        static func summary(_ perSkala: [PerSkala], isID: Bool) -> String {
            let cats = stated(perSkala)
            guard let lo = cats.min(by: { rank($0) < rank($1) }),
                  let hi = cats.max(by: { rank($0) < rank($1) }) else { return Theme.absent }
            return rank(lo) == rank(hi) ? label(hi, isID: isID) : "\(label(lo, isID: isID)) → \(label(hi, isID: isID))"
        }

        /// PP 28/2025 licence type derived from the (Besar-tier) risk class — the decree's
        /// deterministic mapping (Pasal 130/131/132/133, confirmed NB-3). `Theme.absent` when
        /// there is no tier to derive from: a bare "NIB" there was a requirement stated on the
        /// app's own authority.
        static func licence(_ perSkala: [PerSkala], isID: Bool) -> String {
            guard let risk = category(perSkala) else { return Theme.absent }
            return licence(tier: risk, isID: isID)
        }

        /// The same mapping applied to a tier the caller already holds (a single `per_skala` row).
        static func licence(tier risk: String, isID: Bool) -> String {
            let u = risk.lowercased()
            if u.contains("tinggi") && !u.contains("menengah") { return isID ? "NIB + Izin" : "NIB + Permit" }   // Tinggi (Pasal 133)
            if u.contains("menengah tinggi") { return isID ? "NIB + Sertifikat Standar" : "NIB + Standard Cert" } // Men-Tinggi (Pasal 132)
            if u.contains("menengah") { return isID ? "NIB + Sertifikat Standar" : "NIB + Standard Cert" }        // Men-Rendah (Pasal 131)
            if u.contains("rendah") || u.contains("low") { return "NIB" }                                        // Rendah (Pasal 130)
            return Theme.absent   // stated but unrecognised: the decree's mapping does not reach it
        }

        /// How the licence is ISSUED, per PP 28/2025 Pasal 130-133 — automatic / self-declared /
        /// verified, as a min→max range when the tier varies across scales. `Theme.absent` when
        /// the corpus states no tier: "Automatic" was the friendliest of the three and the one
        /// the data supports least.
        static func processing(_ perSkala: [PerSkala], isID: Bool) -> String {
            // 0 = automatic · 1 = auto + self-declared · 2 = requires verification.
            // ORDER MATTERS: test "menengah" BEFORE bare "rendah" so "Menengah Rendah" → 1, not 0.
            func level(_ risk: String) -> Int {
                let u = risk.lowercased()
                if u.contains("tinggi") { return 2 }
                if u.contains("menengah") { return 1 }
                if u.contains("rendah") || u.contains("low") { return 0 }
                return 1
            }
            let labels = isID
                ? ["Otomatis", "Otomatis + pernyataan mandiri", "Perlu verifikasi"]
                : ["Automatic", "Auto + self-declared", "Requires verification"]
            let levels = stated(perSkala).map(level)
            guard let lo = levels.min(), let hi = levels.max() else { return Theme.absent }
            return lo == hi ? labels[lo] : "\(labels[lo]) → \(labels[hi])"
        }
    }

    // MARK: Typography (D3b, 2026-08-11 — Dynamic Type)
    // All 6 named roles now resolve to a system TEXT STYLE (Font.TextStyle) instead of a frozen
    // point size — SwiftUI reads the user's Dynamic Type setting from the environment at RENDER
    // time for style-based fonts, automatically, with no @ScaledMetric wiring needed anywhere else
    // in the app. The point-size comment on each line is the role's OLD fixed size, kept as the
    // "scale-1.0 baseline" reference the task asked for — the mapping targets the CLOSEST matching
    // role, not pixel-identical output (title's old 26pt vs .title's own ~28pt default, etc.); the
    // goal is preserving RELATIVE hierarchy, which `scalable(_:)` below formalizes for every other
    // call site in the app using the same size→style ladder.
    static let titleFont   = Font.system(.title, design: .default, weight: .bold)         // was 26
    static let headingFont = Font.system(.headline, design: .default, weight: .semibold)  // was 17
    static let bodyFont    = Font.system(.body, design: .default, weight: .regular)       // was 13
    static let monoFont    = Font.system(.body, design: .monospaced, weight: .medium)     // was 12
    /// Small ALL-CAPS labels (facts-row captions, section eyebrows) — the "micro-label" role.
    static let microFont   = Font.system(.caption2, design: .default, weight: .medium)     // was 10
    static let numberFont  = Font.system(.title3, design: .rounded, weight: .semibold)    // was 15
    /// Big "premium amount" face for the detail hero (SF Pro Rounded, like a fintech figure).
    static let bigNumberFont = Font.system(.largeTitle, design: .rounded, weight: .bold)  // was 30

    /// Dynamic-Type-aware replacement for the ~190 call sites that used to write
    /// `.font(.system(size: N, weight: W, design: D))` directly with a frozen point size. Maps N
    /// onto the CLOSEST matching `Font.TextStyle` via the ladder below (built from the app's
    /// observed size inventory, D3b class-audit) so every one of those call sites gains Dynamic
    /// Type support with a single mechanical swap (`.system(size:` → `Theme.scalable(`), no per-
    /// call-site judgment needed — the size argument still documents the ORIGINAL scale-1.0 intent,
    /// it just no longer freezes the actual rendered size against the user's text-size setting.
    /// Anchors that must hold (given, not derived): 10→.caption2, 13→.body, 17→.headline,
    /// 26→.title (titleFont) — the remaining boundaries interpolate between them, monotonically.
    ///
    /// DECLARED EXCEPTION (not swept by the D3b bulk pass): fonts inside fixed-pixel-height List
    /// rows (`KBLICodeRow`'s status-dot glyph, `SearchListView.swift`) were left on a literal,
    /// non-scaling size — those rows have a hard `.frame(height: density.rowHeight)` (28/36pt, D2)
    /// with no wrapping fallback, so a scaling icon glyph risks clipping rather than the "wrap or
    /// 2-up, never truncate" degradation this pass otherwise aims for. The row's TEXT (code +
    /// title, via `Theme.monoFont` / a swept literal) still scales per the anchors above, since
    /// freezing it would mean two supposedly-matching Theme tokens drifting apart depending on
    /// context — the residual risk (a taller code/title line inside an unchanged-height row at
    /// large accessibility sizes) is real and NOT resolved by this pass; flagged for a live GUI
    /// check, not silently accepted.
    static func scalable(_ size: CGFloat, weight: Font.Weight = .regular, design: Font.Design? = nil) -> Font {
        let style: Font.TextStyle
        switch size {
        case ..<10.5: style = .caption2
        case ..<11.5: style = .caption
        case ..<12.5: style = .footnote
        case ..<13.5: style = .body
        case ..<15.5: style = .subheadline
        case ..<16.5: style = .callout
        case ..<17.5: style = .headline
        case ..<20.5: style = .title3
        case ..<24:   style = .title2
        case ..<29:   style = .title
        default:      style = .largeTitle
        }
        return .system(style, design: design, weight: weight)
    }

    // MARK: Radii (--kbli-radius-*)
    static let radiusSm: CGFloat = 6
    static let radiusMd: CGFloat = 10
    static let radiusLg: CGFloat = 14
    static let radiusXl: CGFloat = 20
}

/// Holds the live light/dark mode. Setting `mode` mutates the static `Theme.mode` (so the
/// computed color tokens re-resolve) AND publishes, so every SwiftUI view that observes it
/// redraws. D3a (2026-08-11): `mode` is driven from system appearance (RootView observes
/// @Environment(\.colorScheme) and assigns here) — no more `.preferredColorScheme` forcing the
/// window away from the system setting. D3a.2 (2026-08-11): a user-facing ☀/☾ toggle is back
/// (`RootView.themeToggle`); it sets a persisted override that RootView's sync then respects
/// instead of overwriting — `mode` itself doesn't know or care whether its last write came from
/// the system or from the user, it's just the live value either way.
@MainActor
final class ThemeManager: ObservableObject {
    @Published var mode: Theme.Mode {
        didSet { Theme.mode = mode }
    }
    /// D3b: Increase Contrast, synced one-way from RootView's @Environment(\.colorSchemeContrast) —
    /// same seam as `mode`. The @Published change here is what actually triggers SwiftUI to
    /// re-render every view holding this object (and re-resolve `Theme.*` tokens along the way);
    /// `Theme.contrastIncreased` alone flipping would not redraw anything by itself.
    @Published var contrastIncreased: Bool = false {
        didSet { Theme.contrastIncreased = contrastIncreased }
    }
    init(_ initial: Theme.Mode = .dark) {
        self.mode = initial
        Theme.mode = initial
    }
}

extension Color {
    init(hex: UInt32) {
        let r = Double((hex >> 16) & 0xFF) / 255.0
        let g = Double((hex >> 8) & 0xFF) / 255.0
        let b = Double(hex & 0xFF) / 255.0
        self.init(.sRGB, red: r, green: g, blue: b, opacity: 1.0)
    }
}

// MARK: - Bali Zero logo

/// The real Bali Zero circular logo, loaded from the app bundle Resources (bz-logo.png),
/// with a graceful monogram fallback so the UI never shows a broken image.
struct BZLogo: View {
    var size: CGFloat = 34
    private static let cached: NSImage? = {
        if let url = Bundle.main.url(forResource: "bz-logo", withExtension: "png"),
           let img = NSImage(contentsOf: url) { return img }
        let exe = Bundle.main.bundleURL.appendingPathComponent("Contents/Resources/bz-logo.png")
        return NSImage(contentsOf: exe)
    }()
    var body: some View {
        Group {
            if let img = BZLogo.cached {
                Image(nsImage: img).resizable().scaledToFit()
            } else {
                ZStack {
                    Circle().fill(Theme.accent)
                    // D3b DECLARED EXCEPTION: proportional to `size` (the badge's own diameter
                    // parameter, not a text role) — a decorative monogram glyph inside a fixed
                    // circular badge, not body text; Dynamic Type scaling doesn't apply here the
                    // way it does to a text role, and scaling it independently of `size` would
                    // make the monogram overflow its own circle.
                    Text("BZ").font(.system(size: size * 0.38, weight: .heavy)).foregroundStyle(Theme.iconOnAccentFill)
                }
            }
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
    }
}

/// A thin terracotta "fact" accent rule — the Bali Zero signature for verifiable data.
struct FactRule: View {
    var width: CGFloat = 40
    var body: some View {
        RoundedRectangle(cornerRadius: 2).fill(Theme.accent).frame(width: width, height: 3)
    }
}

// MARK: - Depth card (the real --kbli-shadow-card: multi-layer + ring + hover glow)

/// A reusable depth card matching the web's `--kbli-shadow-card` / `-hover`:
/// surface fill + 1px ring + tight black shadow + diffuse black shadow, and on hover a
/// soft terracotta glow (`--kbli-shadow-glow`). The glow is conditional (only the hovered
/// card composites the radius-30 layer) — perf note from the SwiftUI research.
struct GlassCard<Content: View>: View {
    var padding: CGFloat = 16
    var radius: CGFloat = Theme.radiusLg
    var hoverable: Bool = true
    @ViewBuilder var content: Content
    @State private var hovered = false

    var body: some View {
        content
            .padding(padding)
            .background(
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .fill(Theme.inkLift.opacity(hovered ? 0.95 : 0.85))
            )
            .overlay(
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .strokeBorder(hovered ? Theme.hairlineHi : Theme.hairline, lineWidth: 1)
            )
            .shadow(color: .black.opacity(0.20), radius: 2, x: 0, y: 1)
            .shadow(color: .black.opacity(hovered ? 0.15 : 0.12), radius: hovered ? 24 : 16, x: 0, y: hovered ? 12 : 4)
            .shadow(color: hovered ? Theme.accent.opacity(0.12) : .clear, radius: 30)
            .animation(.easeInOut(duration: 0.18), value: hovered)
            .onHover { if hoverable { hovered = $0 } }
    }
}

// MARK: - Soft-tinted status badge (the real PMABadge pattern)

/// A soft-tinted status badge: icon + label on a `color.opacity(0.10)` fill with a
/// `color.opacity(0.20)` capsule border and full-color text. NOT a solid grey pill —
/// this is the exact pattern from the web `PMABadge.tsx` / `RiskBadge.tsx`.
struct StatusBadge: View {
    let icon: String
    let label: String
    let color: Color
    var compact: Bool = false

    var body: some View {
        HStack(spacing: 5) {
            // D3b: scales — these badges live in scrollable detail cards, not a fixed-height row
            // (unlike KBLICodeRow's status dot), so there's no clipping risk to guard against.
            Image(systemName: icon).font(Theme.scalable(compact ? 10 : 11, weight: .semibold))
            Text(label).font(Theme.scalable(compact ? 11 : 12, weight: .semibold))
        }
        .foregroundStyle(color)
        .padding(.horizontal, compact ? 8 : 11)
        .padding(.vertical, compact ? 4 : 6)
        .background(color.opacity(0.10))
        .clipShape(Capsule())
        .overlay(Capsule().strokeBorder(color.opacity(0.20), lineWidth: 1))
    }
}

// MARK: - Big "premium amount" figure (detail hero numbers)

/// A label + large SF-Pro-Rounded figure (fintech-style), for headline numbers on the
/// detail card (e.g. modal minimum, processing time).
struct PremiumStat: View {
    let label: String
    let value: String
    var color: Color = Theme.white
    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(label.uppercased())
                .font(Theme.scalable(10, weight: .semibold))
                .tracking(1.1)
                .foregroundStyle(Theme.faint)
            Text(value)
                .font(Theme.bigNumberFont)
                .foregroundStyle(color)
                .lineLimit(1)
                .minimumScaleFactor(0.6)
        }
    }
}

// MARK: - Overflow that is reachable (2026-09-13)

/// A list that shows the first `limit` items and, when the record has more, a REAL button that
/// reveals the rest.
///
/// Every list cap in the cards goes through this. The two shapes it replaces both told the reader
/// something untrue: a list that simply stops asserts a completeness the record does not have
/// (a code with 34 post-licence obligations showed 8 and said nothing), and a `Text("+26 more")`
/// names the missing rows while giving no way to reach them — a caption is not an action. Collapsed,
/// this renders exactly what the card rendered before, so the D1→D4d hierarchy is unchanged: it adds
/// a state and an action, it does not redesign.
///
/// QA: `KBLI_OPEN_ALL=1` starts it expanded, so the off-screen snapshot runner can capture the full
/// list — the same hook `RegistryDisclosure` already uses.
struct ExpandableList<Item, Rows: View>: View {
    let items: [Item]
    let limit: Int
    let isID: Bool
    var tint: Color = Theme.faint
    var spacing: CGFloat = 8
    /// Renders the visible slice. Takes the slice (not one item) so a caller whose overflow is
    /// laid out in columns or grouped rows keeps control of its own container.
    let rows: ([Item]) -> Rows
    @State private var expanded: Bool

    init(items: [Item], limit: Int, isID: Bool, tint: Color = Theme.faint, spacing: CGFloat = 8,
         @ViewBuilder rows: @escaping ([Item]) -> Rows) {
        self.items = items; self.limit = limit; self.isID = isID
        self.tint = tint; self.spacing = spacing; self.rows = rows
        _expanded = State(initialValue: ProcessInfo.processInfo.environment["KBLI_OPEN_ALL"] == "1")
    }

    /// The slice on screen. A range, not `.prefix` — the only cap in the app lives here, next to
    /// the control that opens it.
    private var visible: [Item] {
        (expanded || items.count <= limit) ? items : Array(items[0..<limit])
    }

    var body: some View {
        VStack(alignment: .leading, spacing: spacing) {
            rows(visible)
            if items.count > limit {
                Button {
                    withAnimation(.easeInOut(duration: 0.18)) { expanded.toggle() }
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "chevron.down")
                            .font(Theme.scalable(9, weight: .bold))
                            .rotationEffect(.degrees(expanded ? 180 : 0))
                        Text(expanded
                             ? (isID ? "Tampilkan lebih sedikit" : "Show fewer")
                             : (isID ? "Tampilkan semua \(items.count)" : "Show all \(items.count)"))
                            .font(Theme.scalable(11, weight: .semibold))
                    }
                    .foregroundStyle(tint)
                    .padding(.horizontal, 9).padding(.vertical, 5)
                    .background(tint.opacity(0.10), in: Capsule())
                    .contentShape(Capsule())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(expanded
                                    ? (isID ? "Tampilkan lebih sedikit" : "Show fewer")
                                    : (isID ? "Tampilkan semua \(items.count) item" : "Show all \(items.count) items"))
            }
        }
    }
}
