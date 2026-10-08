import SwiftUI

// KBLIRegistryTable.swift — direction "a — registry" (K2, 2026-09-13).
//
// WHY A TABLE AND NOT A PRETTIER CARD. The lie this app shipped lived in the LIST, not in the
// card: everything that was not *provably* closed printed an open verdict, and 217 records with
// no `kategori_risiko` at any scale were handed a literal `?? "Menengah Rendah"`. A client
// scanning the registry read a regulatory fact the corpus never carried, before opening
// anything. So the three states are rendered where the scan happens — one row, four columns
// (code · activity · Bali · OSS risk) — and every cell that has no fact says so in words.
//
// The single reader of the classification fields here is `KBLIVerdict` (Sources/KBLIVerdict.swift):
// this file never touches `l4_bali.blocked`, `pma_status` or `per_skala` to DECIDE anything. It
// quotes them, which is a different act — see `AxisSource` below.

// MARK: - The badge that can say "I do not know"

/// One verdict cell. Four renderings, and the fourth is the point: `.undetermined` is a DASHED
/// outline with no tint at all — neither the sage of an open code nor the coral of a closed one,
/// because a colour would be a claim. Colour is never the only carrier: each state also has its
/// own word and its own VoiceOver sentence.
struct VerdictBadge: View {
    /// `.undetermined` (the Bali axis) and `.undeterminedNational` (the ownership axis) render
    /// identically — a dashed cell — but they are NOT the same fact, and VoiceOver must not say
    /// "Bali: not determined" on a record whose Bali axis is perfectly determined and whose
    /// NATIONAL position is the unknown one (council round 1, codex-gpt-5.6-sol).
    enum State: Equatable { case open, blocked, closedNational, undetermined, undeterminedNational }
    let state: State
    var isID: Bool = false
    var compact: Bool = false

    var text: String {
        switch state {
        case .open:            return isID ? "TERBUKA" : "OPEN"
        case .blocked:         return isID ? "DIBLOKIR" : "BLOCKED"
        case .closedNational:  return isID ? "TERTUTUP · NAS" : "CLOSED · NAT"
        case .undetermined, .undeterminedNational:
            return isID ? "TIDAK DITENTUKAN" : "NOT DETERMINED"
        }
    }

    /// The sentence VoiceOver reads. The badge text alone ("NOT DETERMINED") is a fragment; the
    /// axis it belongs to and what it means about the records have to travel with it.
    var voiceOverLabel: String {
        switch state {
        case .open:           return isID ? "Bali: terbuka untuk PT PMA" : "Bali: open to a PT PMA"
        case .blocked:        return isID ? "Bali: diblokir untuk PT PMA" : "Bali: blocked for a PT PMA"
        case .closedNational: return isID ? "Tertutup untuk modal asing secara nasional" : "Closed to foreign capital nationally"
        case .undetermined:   return isID ? "Bali: tidak dapat ditentukan dari data yang ada"
                                          : "Bali: not determined by the records"
        case .undeterminedNational:
            return isID ? "Posisi nasional: tidak dapat ditentukan dari data yang ada"
                        : "National position: not determined by the records"
        }
    }

    private var isUndetermined: Bool { state == .undetermined || state == .undeterminedNational }

    private var color: Color {
        switch state {
        case .open: return Theme.pmaOpen
        case .blocked, .closedNational: return Theme.pmaClosed
        case .undetermined, .undeterminedNational: return Theme.faint
        }
    }

    var body: some View {
        Text(text)
            .font(Theme.scalable(compact ? 9 : 10, weight: .heavy, design: .monospaced))
            .tracking(0.6)
            .foregroundStyle(isUndetermined ? Theme.muted : color)
            .lineLimit(2).multilineTextAlignment(.center)
            .padding(.horizontal, 8).padding(.vertical, 4)
            .frame(maxWidth: .infinity)
            .background {
                if isUndetermined {
                    // No fill: an undetermined axis gets no colour to argue with.
                    RoundedRectangle(cornerRadius: Theme.radiusSm, style: .continuous)
                        .strokeBorder(style: StrokeStyle(lineWidth: 1, dash: [3, 2]))
                        .foregroundStyle(Theme.hairlineHi)
                } else {
                    RoundedRectangle(cornerRadius: Theme.radiusSm, style: .continuous)
                        .fill(color.opacity(0.13))
                        .overlay(RoundedRectangle(cornerRadius: Theme.radiusSm, style: .continuous)
                            .strokeBorder(color.opacity(0.35), lineWidth: 1))
                }
            }
            .accessibilityElement()
            .accessibilityLabel(voiceOverLabel)
    }

    /// The list's Bali column, derived from the ONE rule. `.nationallyClosed` outranks the Bali
    /// axis here exactly as it does in `KBLIVerdict.headline` — a code closed nationwide is not
    /// "open in Bali" and not "undetermined in Bali" either.
    static func state(for v: KBLIVerdict) -> State {
        switch v.headline {
        case .nationallyClosed:  return .closedNational
        case .baliBlocked:       return .blocked
        case .nationalUndetermined: return .undeterminedNational
        case .baliUndetermined:    return .undetermined
        case .openInBali:        return .open
        }
    }
}

/// The OSS-risk column. `.absent` is not "—" here but a sentence in the row's own language:
/// "no class on record". 217 of the 1,559 records land on it (the census line under the table
/// counts them live, from this same rule).
struct RiskCell: View {
    let risk: KBLIRiskVerdict
    var isID: Bool = false
    var compact: Bool = false

    static func absentText(isID: Bool) -> String { isID ? "tidak ada kelas tercatat" : "no class on record" }

    var body: some View {
        switch risk {
        case .known(let label):
            Text(Theme.riskShortLabel(label, isID: isID))
                .font(Theme.scalable(compact ? 9 : 10, weight: .semibold, design: .monospaced))
                .foregroundStyle(Theme.riskColor(label))
                .lineLimit(1)
                .padding(.horizontal, 8).padding(.vertical, 4)
                .frame(maxWidth: .infinity)
                .background(RoundedRectangle(cornerRadius: Theme.radiusSm, style: .continuous)
                    .fill(Theme.riskColor(label).opacity(0.12))
                    .overlay(RoundedRectangle(cornerRadius: Theme.radiusSm, style: .continuous)
                        .strokeBorder(Theme.riskColor(label).opacity(0.30), lineWidth: 1)))
                .accessibilityElement()
                .accessibilityLabel((isID ? "Risiko OSS: " : "OSS risk: ") + label)
        case .absent:
            Text(Self.absentText(isID: isID))
                .font(Theme.scalable(compact ? 9 : 10).italic())
                .foregroundStyle(Theme.faint)
                .lineLimit(2)
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityElement()
                .accessibilityLabel(isID ? "Risiko OSS: tidak ada kelas pada catatan"
                                         : "OSS risk: no class on record")
        }
    }
}

// MARK: - One row of the register

/// The dense row. Keeps D2's three distinct states (hover wash ≠ selection tint+rail ≠ focus ring)
/// and D3b's single combined VoiceOver stop; adds the two verdict columns that make the scan
/// honest. `isSelected`/`isListFocused` stay explicit parameters for the same reason the old row
/// had them: `Snapshot.swift` renders bare rows off-screen with no EnvironmentObject installed.
struct KBLIRegistryRow: View {
    let kbli: KBLI
    var isSelected: Bool = false
    var isListFocused: Bool = false
    var isID: Bool = false
    var density: RowDensity = .comfortable
    @State private var hovering = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var verdict: KBLIVerdict { KBLIVerdict.of(record: kbli) }
    private var compact: Bool { density == .compact }

    var body: some View {
        let v = verdict
        let badgeState = VerdictBadge.state(for: v)
        HStack(spacing: 12) {
            Text(kbli.kode)
                .font(Theme.scalable(compact ? 11 : 12, weight: .semibold, design: .monospaced))
                .foregroundStyle(Theme.accent)
                .frame(width: compact ? 52 : 58, alignment: .leading)
            Text(kbli.judul)
                .font(Theme.scalable(compact ? 11 : 12.5))
                .foregroundStyle(Theme.white)
                .lineLimit(1).truncationMode(.tail)
                .frame(maxWidth: .infinity, alignment: .leading)
                .help(kbli.judul)
            VerdictBadge(state: badgeState, isID: isID, compact: compact)
                .frame(width: compact ? 116 : 132)
            RiskCell(risk: v.risk, isID: isID, compact: compact)
                .frame(width: compact ? 116 : 132)
        }
        .padding(.horizontal, 10)
        .frame(minHeight: density.rowHeight)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(rowFill, in: RoundedRectangle(cornerRadius: Theme.radiusSm, style: .continuous))
        .overlay(alignment: .leading) {
            if isSelected {
                RoundedRectangle(cornerRadius: 1.5).fill(Theme.accent).frame(width: 2.5).padding(.vertical, 3)
            }
        }
        .overlay(RoundedRectangle(cornerRadius: Theme.radiusSm, style: .continuous)
            .strokeBorder(isSelected && isListFocused ? Theme.accent : .clear, lineWidth: 2))
        .contentShape(Rectangle())
        .onHover { hovering = $0 }
        .animation(reduceMotion ? nil : .easeInOut(duration: 0.12), value: hovering)
        .animation(reduceMotion ? nil : .easeInOut(duration: 0.12), value: isSelected)
        .accessibilityElement(children: .combine)
        // The old `List(selection:)` gave the selected row this trait for free; a LazyVStack does
        // not (council round 1, codex-gpt-5.6-sol).
        .accessibilityAddTraits(isSelected ? [.isSelected] : [])
    }

    private var rowFill: Color {
        if isSelected { return Theme.accent.opacity(0.13) }
        if hovering { return Theme.scrim }
        return .clear
    }
}

// MARK: - The verdict, flattened for the card's secondary surfaces

/// Five booleans over ONE `KBLIVerdict`, for the ledger rows, the roadmap label and the related-code
/// mini-cards of the embedded dossier. They exist so those surfaces stop re-deriving closure from
/// `pma_status`/`l4_bali.blocked` locally — which is how each of them ended in a bare "open" for
/// the records the dataset cannot classify. Pure projection: no record field is read here.
struct VerdictAxes: Equatable {
    let nationallyClosed: Bool
    let nationalUndetermined: Bool
    let baliBlocked: Bool
    let baliUndetermined: Bool
    let openInBali: Bool
    var anyUndetermined: Bool { nationalUndetermined || baliUndetermined }

    init(_ v: KBLIVerdict) {
        if case .closed = v.national { nationallyClosed = true } else { nationallyClosed = false }
        if case .undetermined = v.national { nationalUndetermined = true } else { nationalUndetermined = false }
        if case .blocked = v.bali { baliBlocked = true } else { baliBlocked = false }
        if case .undetermined = v.bali { baliUndetermined = true } else { baliUndetermined = false }
        openInBali = v.isOpenToPMAInBali
    }
}

// MARK: - The census under the table

/// What the whole catalogue looks like on the two axes the old code used to fabricate. Counted
/// from `KBLIVerdict` over every record, never from a constant: if the corpus changes, the line
/// under the table changes with it, and a wrong number is a visible bug instead of stale prose.
@MainActor
enum RegistryCensus {
    struct Census: Equatable { let total: Int; let notDetermined: Int; let noRiskClass: Int }

    /// Computed on every call, deliberately. Two cache keys were tried (`count`, then
    /// `count|first|last kode`) and council round 2 (codex-gpt-5.6-sol) was right both times: a
    /// re-ingested corpus can hold the same codes and different classifications, so any key short
    /// of the corpus itself eventually describes the dataset that is no longer loaded. A stale
    /// census is precisely the failure this line exists to prevent, and one pass over 1,559
    /// records of pure value work is cheaper than being wrong.
    /// The footer's entry point. Council K2 round 1 (agy-gemini-3.1-pro) named the cost: one pass of
    /// `KBLIVerdict` over every record on EVERY render, arrow-key repeats included. The key is the
    /// store OBJECT, compared with `===` and held strongly so its address cannot be reused: both
    /// `KBLIStore.all` and `AppState.store` are `let`, so a different corpus is necessarily a
    /// different store — which is exactly what the two rejected count-based keys could not promise.
    private static var cache: (store: KBLIStore, census: Census)?
    static func cached(for store: KBLIStore) -> Census {
        if let c = cache, c.store === store { return c.census }
        let fresh = of(store.all)
        cache = (store, fresh)
        return fresh
    }

    /// The verdict of one record of `store`, from a per-store index built once. The verdict
    /// filters run over every row of the table on every render; at 7.3 ms per full pass of
    /// `KBLIVerdict` (measured, -O, M5, 1,559 records) two passes per render ate a frame. Same key
    /// discipline as `cached(for:)`; kode is unique in both measured corpora (1,559 of 1,559), and
    /// a code the index does not hold is derived on the spot, never guessed.
    private static var index: (store: KBLIStore, byCode: [String: KBLIVerdict])?
    static func verdict(_ k: KBLI, in store: KBLIStore) -> KBLIVerdict {
        if index == nil || index!.store !== store {
            var m = [String: KBLIVerdict](minimumCapacity: store.all.count)
            for r in store.all { m[r.kode] = KBLIVerdict.of(record: r) }
            index = (store, m)
        }
        return index!.byCode[k.kode] ?? KBLIVerdict.of(record: k)
    }

    static func of(_ all: [KBLI]) -> Census {
        var undetermined = 0, noRisk = 0
        for k in all {
            let v = KBLIVerdict.of(record: k)
            switch v.headline {
            case .nationalUndetermined, .baliUndetermined: undetermined += 1
            default: break
            }
            if v.risk == .absent { noRisk += 1 }
        }
        return Census(total: all.count, notDetermined: undetermined, noRiskClass: noRisk)
    }
}

/// Locale-correct digit grouping (1,559 in English · 1.559 in Indonesian) — a registry that
/// prints "1559" in an Indonesian window is sloppy, and a hand-rolled separator would be wrong
/// in one of the two languages.
enum RegistryFormat {
    static func number(_ n: Int, isID: Bool) -> String {
        let f = NumberFormatter()
        f.numberStyle = .decimal
        f.locale = Locale(identifier: isID ? "id_ID" : "en_US")
        return f.string(from: NSNumber(value: n)) ?? "\(n)"
    }
}

// MARK: - The per-axis source lines (the graft)

/// Direction "b — dossier" carried one idea this direction did not: every axis states its OWN
/// source inline, so claim and provenance never separate by a scroll. Grafted here onto the
/// sheet's three axis cards — it costs no extra file and closes the one gap the panel named
/// against "a" (sources bundled into a single quote block instead of exploded per axis).
///
/// These strings are FIELD LOCATORS, not prose: they name the record key the verdict was read
/// from and the value it held, so a reader can check the dataset instead of trusting the card.
enum AxisSource {
    /// Council round 1 (codex-gpt-5.6-sol) named a real defect here: the first version mixed
    /// fields `KBLIVerdictInput` consumes with fields it does not (`pma_source`, `confidence`,
    /// the moratorium block) and omitted two it does (`pma_kondisi`, `pma_route_to`). A source
    /// line that names a field the rule never read is not provenance, it is decoration. So each
    /// line now has two halves: what the RULE READ, then what the RECORD CITES beside it.
    ///
    /// The field keys and values are locators and stay verbatim in both languages; the connecting
    /// words are the reader's language (council K2 round 1, both seats: they were English on the
    /// Indonesian sheet).
    private static func compose(read: [String], cites: [String], isID: Bool) -> String {
        let a = read.joined(separator: " · ")
        guard cites.isEmpty == false else { return a }
        return a + (isID ? "  ·  dikutip catatan: " : "  ·  cited by the record: ") + cites.joined(separator: " · ")
    }

    static func national(_ k: KBLI, isID: Bool = false) -> String {
        var read: [String] = ["pma_status=\(k.pmaStatus ?? "∅")",
                              "pma_max_asing=\(k.pmaMaxAsing.map(String.init) ?? "∅")"]
        if k.pmaCapSpecial == true { read.append("pma_cap_special=true") }
        // `pma_kondisi` is consumed by the rule on exactly two branches (a special cap, a 0% cap).
        if k.pmaCapSpecial == true || k.pmaMaxAsing == 0 {
            let kondisi = (k.pmaKondisi?.isEmpty == false) ? k.pmaKondisi! : "∅"
            read.append("pma_kondisi=\(kondisi)")   // read on this branch even when it is empty
        }
        if (k.pmaStatus ?? "").uppercased() == "TERTUTUP" {
            let route = (k.pmaRouteTo?.isEmpty == false) ? k.pmaRouteTo! : "∅"
            read.append("pma_route_to=\(route)")
        }
        var cites: [String] = []
        if let src = k.pmaSource, src.isEmpty == false { cites.append(src) }
        if k.pmaCapVerified == false { cites.append("pma_cap_verified=false") }
        return compose(read: read, cites: cites, isID: isID)
    }

    static func bali(_ k: KBLI, isID: Bool = false) -> String {
        guard let l4 = k.l4Bali else {
            return isID ? "l4_bali=∅ (catatan ini tidak memiliki blok Bali)" : "l4_bali=∅ (no Bali block on this record)"
        }
        var read: [String] = ["l4_bali.status=\(l4.status)", "blocked=\(l4.blocked)"]
        // Present/absent, NOT "the sentence above": when a national closure dominates, the
        // sentence above is the national reason and this one is not on screen at all (council
        // round 2, codex-gpt-5.6-sol).
        read.append("reason=" + ((l4.reason?.isEmpty == false) ? "✓" : "∅"))   // symbols: language-free
        var cites: [String] = []
        if let c = l4.confidence, c.isEmpty == false { cites.append("confidence=\(c)") }
        if let m = l4.moratorium {
            if let eff = m.effective { cites.append("moratorium.effective=\(eff)") }
            if let s = m.source, s.isEmpty == false { cites.append(s) }
        }
        return compose(read: read, cites: cites, isID: isID)
    }

    /// Takes the VERDICT, not just the record: the label printed here is the one the rule chose
    /// (`riskLabelRaw`), so the locator can never name a different row than the axis above it.
    /// The ledger ("n of m rows carry a class") is the honest per-scale count either way.
    static func risk(_ k: KBLI, verdict v: KBLIVerdict, isID: Bool = false) -> String {
        let rows = k.perSkala.count
        let withCat = k.perSkala.filter { ($0.kategoriRisiko ?? "").isEmpty == false }.count
        if rows == 0 { return isID ? "per_skala=[] (0 baris)" : "per_skala=[] (0 rows)" }
        let ledger = isID ? "(\(withCat) dari \(rows) baris memiliki kelas)" : "(\(withCat) of \(rows) rows carry a class)"
        guard let chosen = v.riskLabelRaw else { return "per_skala.kategori_risiko=∅ \(ledger)" }
        let fromBesar = k.perSkala.contains { row in
            row.skalaUsaha.contains { $0.lowercased().contains("besar") } && row.kategoriRisiko == chosen
        }
        let where_ = fromBesar ? "per_skala[Besar]"
            : (isID ? "per_skala[tertinggi lintas skala — tidak ada baris Besar yang memilikinya]"
                    : "per_skala[highest across scales — no Besar row carries one]")
        return "\(where_).kategori_risiko=\(chosen) \(ledger)"
    }
}

/// Short, bilingual OSS-risk labels for the narrow column. Kept here rather than in `Theme`
/// (outside this window's perimeter) and deliberately never invents a tier: it only shortens a
/// label the record actually carries — the absent case is `RiskCell.absentText`, not a default.
extension Theme {
    static func riskShortLabel(_ raw: String, isID: Bool) -> String {
        let r = raw.uppercased()
        if r.contains("MENENGAH TINGGI") || r.contains("MENENGAH_TINGGI") || r.contains("MEDIUM_HIGH") || r == "MT" {
            return isID ? "Menengah Tinggi" : "Medium-High"
        }
        if r.contains("MENENGAH RENDAH") || r.contains("MENENGAH_RENDAH") || r.contains("MEDIUM_LOW") || r == "MR" {
            return isID ? "Menengah Rendah" : "Medium-Low"
        }
        if r.contains("TINGGI") || r.contains("HIGH") || r == "H" { return isID ? "Tinggi" : "High" }
        if r.contains("RENDAH") || r.contains("LOW") || r == "R" || r == "L" { return isID ? "Rendah" : "Low" }
        return raw   // an unrecognised label is DATA: shown verbatim, never normalised away
    }
}
