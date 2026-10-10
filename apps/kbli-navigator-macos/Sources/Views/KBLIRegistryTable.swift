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

    /// Opaque chip (spec §1.3): the tone's own fill and ink, radius 2, no stroke, no opacity tint.
    private var tone: Theme.Tone {
        switch state {
        case .open: return .open
        case .blocked, .closedNational: return .closed
        case .undetermined, .undeterminedNational: return .neutral
        }
    }

    var body: some View {
        let c = Theme.chip(tone)
        Text(text)
            .font(Theme.scalable(compact ? 9 : 10, weight: .heavy, design: .monospaced))
            .tracking(0.6)
            .foregroundStyle(c.fg)
            .multilineTextAlignment(.center)
            .padding(.horizontal, 8).padding(.vertical, 4)
            .frame(maxWidth: .infinity)
            .background(c.bg, in: RoundedRectangle(cornerRadius: 2))
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
            let c = Theme.riskChip(label)
            Text(Theme.riskShortLabel(label, isID: isID))
                .font(Theme.scalable(compact ? 9 : 10, weight: .semibold, design: .monospaced))
                .foregroundStyle(c.fg)
                .padding(.horizontal, 8).padding(.vertical, 4)
                .frame(maxWidth: .infinity)
                .background(c.bg, in: RoundedRectangle(cornerRadius: 2))
                .overlay {
                    if let b = c.border { RoundedRectangle(cornerRadius: 2).strokeBorder(b, lineWidth: 1) }
                }
                .accessibilityElement()
                .accessibilityLabel((isID ? "Risiko OSS: " : "OSS risk: ") + LabelBook.risk(label, isID: isID))
        case .absent:
            Text(Self.absentText(isID: isID))
                .font(Theme.scalable(compact ? 9 : 10).italic())
                .foregroundStyle(Theme.faint)
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
        let title = LabelBook.title(kbli, isID: isID)
        HStack(spacing: 12) {
            Text(kbli.kode)
                .font(Theme.scalable(13, weight: .regular, design: .monospaced))
                .foregroundStyle(Theme.muted)
                .frame(width: compact ? 52 : 58, alignment: .leading)
            Text(title)
                .font(Theme.scalable(13))
                .lineSpacing(Theme.leading(13, 20))
                .foregroundStyle(Theme.white)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, alignment: .leading)
                .help(title)
            VerdictBadge(state: badgeState, isID: isID, compact: compact)
                .frame(width: compact ? 116 : 132)
            RiskCell(risk: v.risk, isID: isID, compact: compact)
                .frame(width: compact ? 116 : 132)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, compact ? 4 : 8)
        .frame(minHeight: density.rowHeight)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(rowFill)
        .overlay(alignment: .bottom) { Rectangle().fill(Theme.lineSoft).frame(height: 1) }
        .overlay(alignment: .leading) {
            if isSelected { Rectangle().fill(Theme.accent).frame(width: 3) }
        }
        .overlay(Rectangle().strokeBorder(isSelected && isListFocused ? Theme.accent : .clear, lineWidth: 2))
        .contentShape(Rectangle())
        .onHover { hovering = $0 }
        .animation(Theme.motion(reduceMotion), value: hovering)
        .animation(Theme.motion(reduceMotion), value: isSelected)
        .accessibilityElement(children: .combine)
        // The old `List(selection:)` gave the selected row this trait for free; a LazyVStack does
        // not (council round 1, codex-gpt-5.6-sol).
        .accessibilityAddTraits(isSelected ? [.isSelected] : [])
    }

    private var rowFill: Color {
        isSelected || hovering ? Theme.wash : .clear
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
/// Each line names the record fields the verdict was read from and the value each held, so a reader
/// can check the dataset instead of trusting the card. Q12 (2026-10-10): it names them in the
/// reader's language — the keys and the Italian enums are pipeline keys, never drawn; every word
/// comes from `LabelBook`.
enum AxisSource {
    /// Council round 1 (codex-gpt-5.6-sol) named a real defect here: the first version mixed
    /// fields `KBLIVerdictInput` consumes with fields it does not (`pma_source`, `confidence`,
    /// the moratorium block) and omitted two it does (`pma_kondisi`, `pma_route_to`). A source
    /// line that names a field the rule never read is not provenance, it is decoration. So each
    /// line now has two halves: what the RULE READ, then what the RECORD CITES beside it.
    private static func compose(read: [String], cites: [String], isID: Bool) -> String {
        let a = read.joined(separator: " · ")
        guard cites.isEmpty == false else { return a }
        return a + (isID ? "  ·  dikutip catatan: " : "  ·  cited by the record: ") + cites.joined(separator: " · ")
    }

    private static func pair(_ key: String, _ value: String, isID: Bool) -> String {
        "\(LabelBook.field(key, isID: isID)): \(value)"
    }

    static func national(_ k: KBLI, isID: Bool = false) -> String {
        var read: [String] = [pair("pma_status", LabelBook.pmaStatus(k.pmaStatus ?? "∅", isID: isID), isID: isID),
                              pair("pma_max_asing", k.pmaMaxAsing.map { "\($0)%" } ?? "∅", isID: isID)]
        if k.pmaCapSpecial == true { read.append(LabelBook.field("pma_cap_special", isID: isID)) }
        // `pma_kondisi` is consumed by the rule on exactly two branches (a special cap, a 0% cap).
        if k.pmaCapSpecial == true || k.pmaMaxAsing == 0 {
            let kondisi = (k.pmaKondisi?.isEmpty == false) ? LabelBook.original(k.pmaKondisi!, isID: isID) : "∅"
            read.append(pair("pma_kondisi", kondisi, isID: isID))   // read on this branch even when it is empty
        }
        if (k.pmaStatus ?? "").uppercased() == "TERTUTUP" {
            let route = (k.pmaRouteTo?.isEmpty == false) ? k.pmaRouteTo! : "∅"
            read.append(pair("pma_route_to", route, isID: isID))
        }
        var cites: [String] = []
        if let src = k.pmaSource, src.isEmpty == false { cites.append(src) }
        if k.pmaCapVerified == false { cites.append(LabelBook.field("pma_cap_verified=false", isID: isID)) }
        return compose(read: read, cites: cites, isID: isID)
    }

    static func bali(_ k: KBLI, isID: Bool = false) -> String {
        guard let l4 = k.l4Bali else { return LabelBook.field("l4_bali=∅", isID: isID) }
        var read: [String] = [pair("l4_bali.status", LabelBook.baliStatus(l4.status, isID: isID), isID: isID),
                              pair("l4_bali.blocked", LabelBook.yesNo(l4.blocked, isID: isID), isID: isID)]
        // Present/absent, NOT "the sentence above": when a national closure dominates, the
        // sentence above is the national reason and this one is not on screen at all (council
        // round 2, codex-gpt-5.6-sol).
        read.append(pair("l4_bali.reason", (l4.reason?.isEmpty == false) ? "✓" : "∅", isID: isID))   // symbols: language-free
        var cites: [String] = []
        if let c = l4.confidence, c.isEmpty == false {
            cites.append(pair("l4_bali.confidence", LabelBook.confidence(c, isID: isID), isID: isID))
        }
        if let m = l4.moratorium {
            if let eff = m.effective { cites.append(pair("moratorium.effective", eff, isID: isID)) }
            if let s = m.source, s.isEmpty == false { cites.append(s) }
        }
        return compose(read: read, cites: cites, isID: isID)
    }

    /// Takes the VERDICT, not just the record: the label printed here is the one the rule chose
    /// (`riskLabelRaw`), so the line can never name a different row than the axis above it.
    /// The ledger ("n of m rows carry a class") is the honest per-scale count either way.
    static func risk(_ k: KBLI, verdict v: KBLIVerdict, isID: Bool = false) -> String {
        let rows = k.perSkala.count
        let withCat = k.perSkala.filter { ($0.kategoriRisiko ?? "").isEmpty == false }.count
        if rows == 0 { return pair("per_skala", "0", isID: isID) }
        let ledger = isID ? "(\(withCat) dari \(rows) baris memiliki kelas)" : "(\(withCat) of \(rows) rows carry a class)"
        let risk = LabelBook.field("kategori_risiko", isID: isID)
        guard let chosen = v.riskLabelRaw else { return "\(risk): ∅ \(ledger)" }
        let fromBesar = k.perSkala.contains { row in
            row.skalaUsaha.contains { $0.lowercased().contains("besar") } && row.kategoriRisiko == chosen
        }
        let large = LabelBook.scale("Besar", isID: isID)
        let where_ = fromBesar ? (isID ? "\(risk) pada skala \(large)" : "\(risk) at \(large) scale")
            : (isID ? "\(risk) tertinggi lintas skala (tidak ada baris \(large) yang memilikinya)"
                    : "\(risk), highest across scales (no \(large)-scale row carries one)")
        return "\(where_): \(LabelBook.risk(chosen, isID: isID)) \(ledger)"
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
