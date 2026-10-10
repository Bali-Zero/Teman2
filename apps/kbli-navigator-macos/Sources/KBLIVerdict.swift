import Foundation

// KBLIVerdict.swift — the ONE verdict rule.
//
// Before this file the rule was `let blocked = l4.blocked || nationallyClosed`, a local
// constant inside `KBLIRegistryView.verdictBanner`. Two consequences, one root:
//
//   1. It was BINARY. Everything not *provably* closed fell into the `else` branch and printed
//      "In Bali: open to a PT PMA" — including the 8 codes whose Bali applicability the dataset
//      explicitly says it cannot classify (`l4_bali.status == "NON_CLASSIFICABILE"`,
//      `blocked == false`). Superscar #3 in UNDER-match: a guard that judges a substring of the
//      truth. The same shape was patched once already on 2026-06-27 for national closures; the
//      *unknown* case was never added.
//   2. The chat did not use it AT ALL. The chat's path to the model is the context package,
//      which serialized the raw classification fields and let the model draw its own conclusion.
//      One product, two rules, no mechanism keeping them equal.
//
// So the semantics live here, once, as a pure value with no view, no store and no I/O, and every
// consumer goes through the typed API. Raw-field access for classification purposes is the thing
// this file exists to replace: a `grep` proves nothing (a rename or a helper walks around it),
// which is why the guarantees below are carried by tests over the WHOLE dataset instead.
//
// THREE AXES, never one boolean (spec §3): the uncertainty attaches to the axis that is
// uncertain. An established national closure DOMINATES a Bali position that cannot be
// determined — it does not become uncertain by contagion. Symmetrically, a Bali position that
// cannot be determined never erases an established closure: of the 24 `NON_CLASSIFICABILE`
// records on the current anchor, ALL 24 are unblocked and become `.undetermined` — the 17 that
// used to be `blocked` (measured 2026-09-13) were reclassified onto their own explicit statuses
// by the 2026-09-17 re-anchor (b30b1759…) and no longer share this bucket.
//
// 2026-09-17 re-anchor (b30b1759…): `ATTENZIONE_FASCIA_BALI` appeared (383 records, all
// `blocked == false`) where `BLOCCATO_CLASSE_RISCHIO` (373 records, all `blocked == true`) used
// to be — a genuinely SOFTER classification ("verify on OSS"), not a pin error. A status this
// file has never classified must never default to open (packagetest's schema-snapshot
// discipline, extended here to the status enum itself): `baliVerdict` below keeps an EXHAUSTIVE
// registry of every `l4_bali.status` the dataset carries, partitioned into "reads as open when
// unblocked" and "reads as undetermined even when unblocked"; anything outside both — the
// `ZZZ_UNKNOWN` guarantee — falls to `.undetermined`, never `.open`.

/// The ownership axis — what the national regime says about foreign capital in this activity.
/// `cap` is optional because the dataset genuinely does not carry a percentage for every record
/// (measured: 1 `TERBUKA` record with no cap, and 1 `TERBATAS` record whose cap is the literal
/// string `"special"`). A missing number is rendered as "—", NEVER as a default.
enum KBLINationalVerdict: Equatable {
    case open(cap: Int?)
    case restricted(cap: Int?)
    case closed(reason: String)
    case undetermined(reason: String)
}

/// The Bali axis — what the provincial moratorium regime says. `.undetermined` is the state the
/// old boolean could not express.
enum KBLIBaliVerdict: Equatable {
    case open
    case blocked(reason: String)
    case undetermined(reason: String)
}

/// The risk axis. `.absent` is a real answer: 217 of the 1,559 records (measured 2026-09-13)
/// carry no `kategori_risiko` on any scale row, and the previous code handed those a literal
/// `?? "Menengah Rendah"` — a fabricated regulatory fact on 14% of the catalogue.
enum KBLIRiskVerdict: Equatable {
    case known(String)
    case absent
}

/// The precedence-resolved single statement. Consumers that need ONE sentence (the card banner,
/// the chat package) read this; consumers that show the axes separately read the axes. Both
/// derive from the same value, so they cannot disagree.
enum KBLIVerdictHeadline: Equatable {
    /// An established national closure. Dominates everything else on the Bali axis.
    case nationallyClosed(reason: String)
    /// Established Bali block (moratorium / risk class / provincial closure).
    case baliBlocked(reason: String)
    /// The national position itself cannot be stated from the fields carried.
    case nationalUndetermined(reason: String)
    /// The national position is known and not closed, but the Bali applicability is not
    /// classifiable. This is the third state the binary rule could not express.
    case baliUndetermined(reason: String)
    /// Open in Bali. Carries the national verdict so the caller can qualify it ("open, foreign
    /// ownership capped at 49%") instead of re-deriving the cap from raw fields.
    case openInBali(national: KBLINationalVerdict)
}

/// Everything the rule needs, and nothing else. Two adapters build it (`KBLI` for the views,
/// the raw dictionary for the context package) so that the typed model and the raw JSON index
/// cannot drift into two rules.
struct KBLIVerdictInput: Equatable {
    let code: String
    let pmaStatus: String?
    /// nil when the record has no numeric cap (absent, or a non-numeric marker like `"special"`).
    let pmaMaxAsing: Int?
    let pmaKondisi: String?
    let pmaCapSpecial: Bool
    let pmaRouteTo: String?
    /// false when the record carries no `l4_bali` block at all.
    let baliRecordPresent: Bool
    let baliStatus: String?
    let baliBlocked: Bool
    let baliReason: String?
    /// `kategori_risiko` per scale row, paired with that row's `skala_usaha` entries, in record
    /// order. Empty strings are treated as absent by the rule.
    let riskRows: [(scales: [String], category: String?)]

    static func == (a: KBLIVerdictInput, b: KBLIVerdictInput) -> Bool {
        a.code == b.code && a.pmaStatus == b.pmaStatus && a.pmaMaxAsing == b.pmaMaxAsing
            && a.pmaKondisi == b.pmaKondisi && a.pmaCapSpecial == b.pmaCapSpecial
            && a.pmaRouteTo == b.pmaRouteTo && a.baliRecordPresent == b.baliRecordPresent
            && a.baliStatus == b.baliStatus && a.baliBlocked == b.baliBlocked
            && a.baliReason == b.baliReason
            && a.riskRows.map({ [$0.scales.joined(separator: "|"), $0.category ?? ""] })
                == b.riskRows.map({ [$0.scales.joined(separator: "|"), $0.category ?? ""] })
    }
}

struct KBLIVerdict: Equatable {
    let code: String
    let national: KBLINationalVerdict
    let bali: KBLIBaliVerdict
    let risk: KBLIRiskVerdict
    /// The non-percentage condition attached to the ownership axis when there is one (the
    /// `"special"` distribution-network class). Carried beside the axis rather than inside it so
    /// the four-case shape frozen in the sibling contract stays exactly four cases.
    let nationalCondition: String?

    // MARK: - The rule

    static func derive(_ input: KBLIVerdictInput) -> KBLIVerdict {
        KBLIVerdict(code: input.code,
                    national: nationalVerdict(input),
                    bali: baliVerdict(input),
                    risk: riskVerdict(input),
                    nationalCondition: input.pmaCapSpecial ? input.pmaKondisi : nil)
    }

    private static func nationalVerdict(_ i: KBLIVerdictInput) -> KBLINationalVerdict {
        let status = (i.pmaStatus ?? "").uppercased()
        // A government-reserved / nationally closed activity. `pma_route_to` names the private
        // sibling a PMA client registers instead, when the 2026-06-27 audit found one.
        if status == "TERTUTUP" {
            if let route = i.pmaRouteTo, route.isEmpty == false {
                return .closed(reason: "TERTUTUP — closed to foreign capital nationally; private-sector equivalent: \(route)")
            }
            return .closed(reason: "TERTUTUP — closed to foreign capital nationally")
        }
        // The special-distribution class (47221): numerically capless, but NOT closed — the
        // restriction is a distribution-network/location condition, carried in
        // `nationalCondition`. Rendering its cap as "0%" is the exact lie this file exists to
        // stop, and so is calling it closed.
        if i.pmaCapSpecial {
            return .restricted(cap: nil)
        }
        // A 0% cap IS a closure on the ownership axis, whatever the status word says — INCLUDING
        // when the status word is missing or unrecognised. The benchmark's Umrah/Hajj class
        // (79122) is the reference case: "not blocked by the moratorium" must never be read as
        // open to foreign capital. This test sits ABOVE the status dispatch because of council
        // round 3 (codex-gpt-5.6-sol, VERDICT DEFECT): with `pma_status` absent and a 0% cap the
        // record fell through to the final `.undetermined`, so an ESTABLISHED closure was lost to
        // an unknown — the precedence this file exists to enforce, inverted.
        if i.pmaMaxAsing == 0 {
            if let k = i.pmaKondisi, k.isEmpty == false {
                return .closed(reason: "a 0% foreign-ownership cap — \(k)")
            }
            return .closed(reason: "a 0% foreign-ownership cap")
        }
        if status == "TERBATAS" {
            guard let cap = i.pmaMaxAsing else {
                return .undetermined(reason: "TERBATAS with no foreign-ownership cap recorded")
            }
            return .restricted(cap: cap)
        }
        if status == "TERBUKA" {
            // cap may be nil: open, percentage not recorded. Open is a determined fact; only the
            // number is missing, and a missing number renders "—".
            return .open(cap: i.pmaMaxAsing)
        }
        return .undetermined(reason: "no recognised pma_status on this record")
    }

    /// Statuses whose non-blocked reading is an ESTABLISHED open position. `CHIUSO_BALI_PROPOSTO`
    /// belongs here (not in the undetermined set): a *proposed* closure that has not flipped
    /// `blocked` to true is, by the dataset's own naming, not yet a closure — the test-suite
    /// precedent this file has carried since the binary rule was replaced.
    static let knownOpenBaliStatuses: Set<String> = [
        "OK_OR_HIGHER_RISK", "APERTO_BALI_RISCHIO_ALTO", "BLOCCATO_DIPENDE_SCOPE", "TERBATAS",
        "CHIUSO_BALI_PROPOSTO",
    ]

    /// Statuses that state their OWN uncertainty even when `blocked` is false — the third state
    /// the binary rule could not express. `ATTENZIONE_FASCIA_BALI` (2026-09-17 re-anchor,
    /// b30b1759…) replaced `BLOCCATO_CLASSE_RISCHIO` (always `blocked == true`) with a softer
    /// "verify on OSS" reading that must not collapse into "open" just because it isn't blocked.
    static let knownUndeterminedBaliStatuses: Set<String> = [
        "NON_CLASSIFICABILE", "ATTENZIONE_FASCIA_BALI",
    ]

    /// Statuses this file has seen carry an established Bali closure — i.e. every record bearing
    /// one is expected to also read `blocked == true` and take the `i.baliBlocked` branch below.
    /// Listed ONLY so `knownBaliStatuses` is the exhaustive registry the packagetest-style guilt
    /// test (verdicttest) checks against the dataset's real status set — this set plays no role
    /// in `baliVerdict`'s own dispatch, which trusts `blocked` directly and never the status word.
    static let knownBlockedBaliStatuses: Set<String> = [
        "TERTUTUP", "CHIUSO_BALI", "CHIUSO_MORATORIA_BALI", "CHIUSO_PMA_NO_BESAR",
        "CHIUSO_REGOLATORE_SETTORIALE",
    ]

    /// EXHAUSTIVE union of every `l4_bali.status` this file has explicitly considered. A status
    /// the dataset carries but this set does not name is a guilt condition for verdicttest — the
    /// day a new one appears silently it must be looked at and classified, never inferred.
    static let knownBaliStatuses: Set<String> =
        knownOpenBaliStatuses.union(knownUndeterminedBaliStatuses).union(knownBlockedBaliStatuses)

    private static func baliVerdict(_ i: KBLIVerdictInput) -> KBLIBaliVerdict {
        guard i.baliRecordPresent else {
            return .undetermined(reason: "no Bali classification block on this record")
        }
        // Established block first: `blocked` is the single source of truth, independent of the
        // status word (a `CHIUSO_*` status can in principle arrive with `blocked == false` — the
        // "proposed" class already does — and the reverse never happens today, but the ORDER
        // here is what makes that safe either way). Uncertainty never erases a closure.
        if i.baliBlocked {
            let reason = (i.baliReason?.isEmpty == false) ? i.baliReason! : (i.baliStatus ?? "blocked in Bali")
            return .blocked(reason: reason)
        }
        let status = (i.baliStatus ?? "").uppercased()
        if knownUndeterminedBaliStatuses.contains(status) {
            let reason = (i.baliReason?.isEmpty == false) ? i.baliReason!
                : "Bali moratorium applicability is not classifiable from the fields carried"
            return .undetermined(reason: reason)
        }
        if knownOpenBaliStatuses.contains(status) {
            return .open
        }
        // A status this file has never classified (including the always-blocked family above,
        // arriving here unblocked, and any future value) must never default to open — the
        // `ZZZ_UNKNOWN` guarantee. Fail closed to undetermined, not to a claim of permission.
        let reason = (i.baliReason?.isEmpty == false) ? i.baliReason!
            : "unrecognised Bali status \"\(i.baliStatus ?? "")\" — cannot confirm it is open"
        return .undetermined(reason: reason)
    }

    private static func riskVerdict(_ i: KBLIVerdictInput) -> KBLIRiskVerdict {
        // The PMA-relevant scale is Besar: a PT PMA is a large enterprise by law, and reading
        // `per_skala.first` (Mikro) understates the class — the "Medium-Low restaurant" trap.
        // The HIGHEST Besar row, not the first: a code can carry one scale block per OSS scope,
        // and 01140 has Besar/Menengah Tinggi on scope 0 and Besar/Tinggi on scope 1 (council
        // round 4, codex-gpt-5.6-sol). The verdict is per CODE, so taking the first row would
        // understate the risk for every scope after it. The axis never understates; a
        // scope-aware risk would be a different contract and belongs to a different window.
        let besar = i.riskRows
            .filter { $0.scales.contains(where: { $0.lowercased().contains("besar") }) }
            .compactMap { $0.category }
            .filter { $0.isEmpty == false }
        if let highestBesar = besar.max(by: { riskRank($0) < riskRank($1) }) {
            return .known(highestBesar)
        }
        let all = i.riskRows.compactMap { $0.category }.filter { $0.isEmpty == false }
        guard let highest = all.max(by: { riskRank($0) < riskRank($1) }) else { return .absent }
        return .known(highest)
    }

    /// Severity rank for an OSS risk category (higher = riskier); 0 for an unrecognised label,
    /// which still counts as *present* — an unknown label is data, an absent one is not.
    static func riskRank(_ r: String) -> Int {
        let u = r.lowercased()
        if u.contains("menengah rendah") || u.contains("medium_low") { return 2 }
        if u.contains("menengah tinggi") || u.contains("medium_high") { return 3 }
        if u.contains("tinggi") || u.contains("high") { return 4 }
        if u.contains("rendah") || u.contains("low") { return 1 }
        return 0
    }

    // MARK: - Precedence

    /// Order: established national closure → established Bali block → national uncertainty →
    /// Bali uncertainty → open. The two closures come first because an established fact beats an
    /// unknown; national uncertainty comes before Bali uncertainty because the national axis is
    /// the broader scope (a code whose national position is unstatable cannot be reported as
    /// "open in Bali" on the strength of a provincial field).
    var headline: KBLIVerdictHeadline {
        if case .closed(let reason) = national { return .nationallyClosed(reason: reason) }
        if case .blocked(let reason) = bali { return .baliBlocked(reason: reason) }
        if case .undetermined(let reason) = national { return .nationalUndetermined(reason: reason) }
        if case .undetermined(let reason) = bali { return .baliUndetermined(reason: reason) }
        return .openInBali(national: national)
    }

    /// True only when every axis needed to say "a PT PMA may register this code in Bali" is
    /// established and permissive. The negation is NOT "closed" — that is the binary the old
    /// rule collapsed into; ask `headline` for what is actually the case.
    var isOpenToPMAInBali: Bool {
        if case .openInBali = headline { return true }
        return false
    }

    // MARK: - Machine-readable projection (the chat package, the manifest, the tests)

    /// Stable, vendor-free, language-free tags. The card renders them in the user's language;
    /// the chat package serializes them verbatim so the model is told the verdict instead of
    /// being handed the flags and left to infer one.
    var headlineTag: String {
        switch headline {
        case .nationallyClosed: return "NATIONALLY_CLOSED"
        case .baliBlocked: return "BALI_BLOCKED"
        case .nationalUndetermined: return "NATIONAL_UNDETERMINED"
        case .baliUndetermined: return "BALI_UNDETERMINED"
        case .openInBali: return "OPEN_IN_BALI"
        }
    }

    var headlineReason: String? {
        switch headline {
        case .nationallyClosed(let r), .baliBlocked(let r),
             .nationalUndetermined(let r), .baliUndetermined(let r):
            return r
        case .openInBali:
            return nil
        }
    }

    var nationalTag: String {
        switch national {
        case .open: return "OPEN"
        case .restricted: return "RESTRICTED"
        case .closed: return "CLOSED"
        case .undetermined: return "UNDETERMINED"
        }
    }

    var baliTag: String {
        switch bali {
        case .open: return "OPEN"
        case .blocked: return "BLOCKED"
        case .undetermined: return "UNDETERMINED"
        }
    }

    /// The foreign-ownership percentage when one is recorded. `nil` renders "—", never a default.
    var nationalCap: Int? {
        switch national {
        case .open(let c), .restricted(let c): return c
        case .closed, .undetermined: return nil
        }
    }

    /// The risk label when the record carries one; `nil` renders "—".
    var riskLabelRaw: String? {
        if case .known(let k) = risk { return k }
        return nil
    }

    /// The block the context package serializes. Flat, small, and named so a model cannot mistake
    /// it for the raw moratorium flags sitting next to it.
    func packageDictionary() -> [String: Any] {
        var out: [String: Any] = [
            "headline": headlineTag,
            "national": nationalTag,
            "bali": baliTag,
        ]
        out["reason"] = headlineReason ?? NSNull()
        out["national_cap_percent"] = nationalCap ?? NSNull()
        out["national_condition"] = nationalCondition ?? NSNull()
        out["risk_category"] = riskLabelRaw ?? NSNull()
        // OPEN-1 (2026-09-17): the model is TOLD the same short ownership line every visual
        // surface renders, instead of being left to phrase "Restricted · 49%" from the raw
        // `national_cap_percent`/`national` tags itself — the exact drift this cure exists to
        // close, one surface earlier than the render layer.
        out["ownership_line"] = ownershipLine(isID: false)
        return out
    }

    // MARK: - The ownership line (OPEN-1, 2026-09-17)

    /// The ONE foreign-ownership line every surface renders — chat context, table row, detail
    /// card, dossier and the registry sheet/ledger. Before this, five surfaces each phrased the
    /// national axis in their own words and drifted: the same 49%-capped TERBATAS record read
    /// "Restricted · 49%" on the sheet and "49% Open" on the ledger row — a foreign-ownership
    /// fact contradicting itself between two panes of the SAME window. Now every surface calls
    /// this, and a wrong wording is a compile error away from being fixed everywhere at once
    /// instead of a `grep` away from being found in the fourth of five places.
    ///
    /// Scoped to the NATIONAL axis only, on purpose: the Bali axis, the cap-verification flag and
    /// `pma_route_to` are separate facts a surface may still show alongside this line (a badge, a
    /// footnote, a second sentence) — but they must never be blended back into the string this
    /// function returns, or two surfaces could again spell the same fact two different ways.
    ///
    /// `.restricted(cap: nil)` only ever arises from the `pma_cap_special` condition (the 47221
    /// class) — a TERBATAS record with no cap recorded is `.undetermined` (see `nationalVerdict`
    /// above), never `.restricted(nil)` — so this switch never needs to ask which. And a 0% cap
    /// is already folded into `.closed` before this switch ever runs (the scar of 2026-06-27:
    /// "0% Open" must never render) — there is no separate "cap == 0" branch to write here,
    /// because the invariant is enforced once, upstream, in `nationalVerdict`.
    ///
    /// No default branch: a fifth `KBLINationalVerdict` case must be handled here explicitly or
    /// the file fails to compile — the guarantee that keeps every surface honest.
    func ownershipLine(isID: Bool) -> String {
        switch national {
        case .open(let cap):
            guard let cap else { return isID ? "Terbuka · —" : "Open · —" }
            return isID ? "Terbuka · \(cap)%" : "Open · \(cap)%"
        case .restricted(let cap):
            guard let cap else { return isID ? "Terbatas · syarat khusus" : "Restricted · special conditions" }
            return isID ? "Terbatas · \(cap)%" : "Restricted · \(cap)%"
        case .closed:
            return isID ? "Tertutup" : "Closed"
        case .undetermined:
            return "—"
        }
    }

    /// Heads-up class (spec §2): 1 Bali-blocked · 2 nationally closed · 3 national undetermined ·
    /// 4 Bali undetermined · 5 TERBATAS cap>0, Bali open · 6 TERBATAS special cap · 7 TERBUKA, Bali open.
    /// First match wins, on the derived axes (never raw strings). After the first four tests the Bali
    /// axis is open and the national axis is open or restricted, so the last switch is exhaustive.
    var headsUpClass: Int {
        if case .blocked = bali { return 1 }
        switch national {
        case .closed: return 2
        case .undetermined: return 3
        case .open, .restricted: break
        }
        if case .undetermined = bali { return 4 }
        switch national {
        case .restricted(let cap): return cap != nil ? 5 : 6
        case .open: return 7
        case .closed: return 2
        case .undetermined: return 3
        }
    }

    /// The ONE heads-up label + sentence + tone every surface renders (Q6 extended by Q10): canonical
    /// words only, never a derived "open" — the open pair survives only in class 7. Q12: the canonical
    /// word is verbatim in Indonesian and its `LabelBook` word in English, and `pma_kondisi`, which has
    /// no English source, is the labelled original in English.
    @MainActor
    static func headsUp(record k: KBLI, isID: Bool) -> (label: String, sentence: String?, tone: Theme.Tone) {
        let v = KBLIVerdict.of(record: k)
        func t(_ key: String) -> String {
            let table = LanguageManager.strings[isID ? .id : .en] ?? LanguageManager.strings[.en]!
            return table[key] ?? LanguageManager.strings[.en]?[key] ?? key
        }
        func nonEmpty(_ s: String?) -> String? { (s?.isEmpty == false) ? s : nil }
        let kondisi = nonEmpty(k.pmaKondisi).map { LabelBook.original($0, isID: isID) }
        switch v.headsUpClass {
        case 1:
            return (t("rich.verdict.blocked"), t("dossier.holding.blocked"), .closed)
        case 2:
            if (k.pmaStatus ?? "").uppercased() == "TERTUTUP" {
                let sentence: String
                if let route = k.pmaRouteTo, !route.isEmpty {
                    sentence = isID
                        ? "Untuk PMA, daftarkan \(route) (versi swasta) sebagai gantinya."
                        : "For a PMA, register \(route) (the private-sector version) instead."
                } else {
                    sentence = isID
                        ? "Hanya badan usaha milik Indonesia 100% yang diizinkan."
                        : "Only a 100% Indonesian-owned entity is permitted."
                }
                return (LabelBook.pmaStatus("TERTUTUP", isID: isID), sentence, .closed)
            }
            let cap = k.pmaMaxAsing.map(String.init) ?? "—"
            return ("\(LabelBook.pmaStatus(k.pmaStatus, isID: isID)) · \(cap)%", kondisi, .closed)
        case 3:
            return (VerdictBadge(state: .undeterminedNational, isID: isID).text,
                    v.headlineReason.map { LabelBook.humanise($0, record: k, isID: isID) }, .neutral)
        case 4:
            let reason = nonEmpty(k.l4Bali?.reason).map {
                LabelBook.humanise(OverlayStore.shared.displayReason($0, isID: isID), record: k, isID: isID)
            }
            return (VerdictBadge(state: .undetermined, isID: isID).text, reason, .neutral)
        case 5:
            let cap = v.nationalCap.map(String.init) ?? "—"
            return ("\(LabelBook.pmaStatus(k.pmaStatus ?? "TERBATAS", isID: isID)) · \(cap)%", kondisi, .restricted)
        case 6:
            return (LabelBook.pmaStatus(k.pmaStatus ?? "TERBATAS", isID: isID), kondisi, .restricted)
        case 7:
            return (t("rich.verdict.open"), t("dossier.holding.open"), .open)
        default:
            // Unreachable (headsUpClass is 1…7); fail closed — never a derived "open".
            return (VerdictBadge(state: .undetermined, isID: isID).text, nil, .neutral)
        }
    }
}

// MARK: - Adapters

extension KBLIVerdictInput {
    /// From the typed model (the card surfaces).
    init(record k: KBLI) {
        self.init(code: k.kode,
                  pmaStatus: k.pmaStatus,
                  pmaMaxAsing: k.pmaMaxAsing,
                  pmaKondisi: k.pmaKondisi,
                  pmaCapSpecial: k.pmaCapSpecial == true,
                  pmaRouteTo: k.pmaRouteTo,
                  baliRecordPresent: k.l4Bali != nil,
                  baliStatus: k.l4Bali?.status,
                  baliBlocked: k.l4Bali?.blocked ?? false,
                  baliReason: k.l4Bali?.reason,
                  riskRows: k.perSkala.map { (scales: $0.skalaUsaha, category: $0.kategoriRisiko) })
    }

    /// From the raw JSON record (the context package's schema index). Mirrors the typed
    /// decoder's tolerances exactly — `pma_max_asing` may be an Int, a numeric String, or a
    /// non-numeric marker; anything not parseable as an Int is *no cap*, not zero.
    init(rawRecord raw: [String: Any], code: String) {
        var cap: Int? = nil
        if let n = raw["pma_max_asing"] as? Int { cap = n }
        else if let s = raw["pma_max_asing"] as? String { cap = Int(s) }
        let l4 = raw["l4_bali"] as? [String: Any]
        let rows = (raw["per_skala"] as? [[String: Any]] ?? []).map { row -> (scales: [String], category: String?) in
            // `[String]` ONLY — deliberately no scalar fallback. Council round 3
            // (codex-gpt-5.6-sol, VERDICT DEFECT): the typed decoder in Models.swift is
            // `(try? decode([String].self)) ?? []`, so a scalar `skala_usaha` decodes to an
            // EMPTY scale list there. Accepting it here would make the raw adapter see a "Besar"
            // row the typed one cannot — two rules again, on an input no record carries today
            // and nothing stops a future one from carrying.
            let scales = (row["skala_usaha"] as? [String]) ?? []
            return (scales: scales, category: row["kategori_risiko"] as? String)
        }
        self.init(code: code,
                  pmaStatus: raw["pma_status"] as? String,
                  pmaMaxAsing: cap,
                  pmaKondisi: raw["pma_kondisi"] as? String,
                  pmaCapSpecial: (raw["pma_cap_special"] as? Bool) == true,
                  pmaRouteTo: raw["pma_route_to"] as? String,
                  baliRecordPresent: l4 != nil,
                  baliStatus: l4?["status"] as? String,
                  baliBlocked: (l4?["blocked"] as? Bool) == true,
                  baliReason: l4?["reason"] as? String,
                  riskRows: rows)
    }
}

extension KBLIVerdict {
    static func of(record k: KBLI) -> KBLIVerdict { derive(KBLIVerdictInput(record: k)) }
    static func of(rawRecord raw: [String: Any], code: String) -> KBLIVerdict {
        derive(KBLIVerdictInput(rawRecord: raw, code: code))
    }
}

// MARK: - The chat's consumption of the verdict

/// The seed question the chat sends when the user taps "Ask Zantara" from a code page. It is
/// built HERE, from the verdict, rather than in the view: the chat must not open a turn by
/// asserting a Bali status the card would contradict, and on an undetermined code the useful
/// question is what is missing, not "is it open".
///
/// Pure, so the chat's use of `KBLIVerdict` is provable by a test instead of by reading the view.
/// No localized strings are added anywhere by this window; these two inline literals live where
/// the view's existing inline seed literals already lived.
enum KBLIChatSeed {
    static func question(code: String, title: String, verdict: KBLIVerdict, isEnglish: Bool) -> String {
        switch verdict.headline {
        case .baliUndetermined, .nationalUndetermined:
            return isEnglish
                ? "Tell me about KBLI \(code) (\(title)). Its status is recorded as not determinable — say what is missing and do not state a verdict the records do not support."
                : "Parlami del codice KBLI \(code) (\(title)). Il suo stato risulta non determinabile: di' che cosa manca e non affermare un verdetto che i dati non sostengono."
        case .nationallyClosed, .baliBlocked, .openInBali:
            return isEnglish
                ? "Tell me about KBLI \(code) (\(title)) and its Bali status."
                : "Parlami del codice KBLI \(code) (\(title)) e del suo stato a Bali."
        }
    }
}
