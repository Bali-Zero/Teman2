import SwiftUI

// RegistryVerdictSheet.swift — direction "a — registry" (K2, 2026-09-13): the code the user
// picked in the table, answered in place.
//
// The sheet carries the WHOLE verdict and the card below it carries none: `KBLIRegistryView` is
// embedded with `showsIdentityAndVerdict: false` when the reader expands the dossier, so there is
// exactly ONE verdict on screen and it is the one derived from `KBLIVerdict`. Two verdict blocks
// on one screen is how a surface ends up contradicting itself (the card's own banner still reads
// the raw fields; that cure belongs to the window that owns the card).
//
// The three axis cards carry their own source line — grafted from direction "b — dossier", which
// won the panel on exactly that point: claim and provenance must not separate by a scroll.

struct RegistryVerdictSheet: View {
    let kbli: KBLI
    @Binding var expanded: Bool
    let onClose: () -> Void
    /// When false (the text census), the `ScrollView` is dropped so an off-screen renderer draws the
    /// whole sheet — `KBLIRegistryView`'s convention.
    var scrolls: Bool = true
    /// The rows of the head the COLLAPSED sheet draws (H1d O1, whole rows only): the band always, the plate and the EN official title when
    /// `SearchListView` found them whole under its cap. A row it does not draw stays laid out (so it is measured, and a taller window brings
    /// it back) but is invisible, unmarked and out of reach. Standalone renders draw all three.
    var collapsedRows: SheetRows = .official

    /// Pure, headless-callable (`Tests/semantictest`) — the sheet's national-axis card delegates
    /// entirely to `KBLIVerdict.ownershipLine` (OPEN-1, 2026-09-17). The national plate calls
    /// this SAME function with the view's own `isID`; kept `static` and free of `@EnvironmentObject`
    /// state so a test can assert it against the projection without instantiating a live view.
    static func ownershipLine(_ kbli: KBLI, isID: Bool) -> String {
        KBLIVerdict.of(record: kbli).ownershipLine(isID: isID)
    }

    @EnvironmentObject var state: AppState
    @Environment(\.immersive) private var immersive
    @Environment(\.arrival) private var arrival
    @EnvironmentObject var lang: LanguageManager

    private var isID: Bool { lang.lang == .id }

    /// The sentence under the headline, in the reader's language where the record has one. The
    /// rule's reasons and most `l4_bali.reason` strings exist in English only; blended into an
    /// Indonesian sheet they read as half-translated prose, so in Indonesian an untranslated reason
    /// is shown as a LABELLED quote of the record instead (the card's `quotedRuleReason` twin). In
    /// English the reason is the translation table's, as the search rows show it — no longer the raw
    /// record string, which is Italian for some codes (Q12).
    private func displayedReason(_ r: String) -> String {
        LabelBook.humanise(OverlayStore.shared.displayReason(r, isID: isID), record: kbli, isID: isID)
    }
    private var verdict: KBLIVerdict { KBLIVerdict.of(record: kbli) }

    var body: some View {
        VStack(spacing: 0) {
            grabber
            if scrolls && expanded { ScrollView { content } }
            else if scrolls {
                // The collapsed sheet has no scroll view at all: its rows are whole or not drawn (H1d O1), and a scroll view reserves a
                // scroller's width on a Mac that shows scroll bars always, which wrapped the band one line more (id 56102 at 1040x648).
                // The content is an overlay of a flexible clear, so it takes its height and the frame's height stays the proposal: a
                // rigid child taller than the frame would be centred in it and the sheet's own frame would read taller than it draws.
                Color.clear.frame(maxHeight: .infinity).overlay(alignment: .top) { content.fixedSize(horizontal: false, vertical: true) }
            } else { content }
        }
        .background(Theme.ink)
        .overlay(alignment: .top) { Rectangle().fill(Theme.hairlineHi).frame(height: 1) }
        .clipShape(RoundedRectangle(cornerRadius: Theme.radiusLg, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Theme.radiusLg, style: .continuous)
            .strokeBorder(Theme.hairline, lineWidth: 1))
        .shadow(color: .black.opacity(0.28), radius: 18, y: -6)
        .coordinateSpace(name: SheetFit.space)
        .censusFrame("sheet")
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: 14) {
            head
            if expanded {
                actions
                Divider().overlay(Theme.hairline)
                KBLIRegistryView(kbli: kbli, scrolls: false, showsIdentityAndVerdict: false)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(.horizontal, 24).padding(.top, 4).padding(.bottom, 16)
    }

    // MARK: chrome

    private var grabber: some View {
        HStack(spacing: 10) {
            Spacer(minLength: 0)
            Button { expanded.toggle() } label: {
                RoundedRectangle(cornerRadius: 2).fill(Theme.hairlineHi)
                    .frame(width: 46, height: 4).padding(.vertical, 9)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel(expanded ? (isID ? "Tutup dosir lengkap" : "Collapse the full dossier")
                                         : (isID ? "Buka dosir lengkap" : "Expand the full dossier"))
            Spacer(minLength: 0)
        }
        .overlay(alignment: .trailing) {
            Button(action: onClose) {
                Image(systemName: "xmark").font(Theme.scalable(11, weight: .bold)).foregroundStyle(Theme.faint)
                    .padding(8).contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .keyboardShortcut(.escape, modifiers: [])
            .help(isID ? "Tutup (Esc)" : "Close (Esc)")
            .accessibilityLabel(isID ? "Tutup panel kode" : "Close the code panel")
            .padding(.trailing, 10)
        }
    }

    // MARK: the head (the redesigned card's head, owner decision 2026-10-12)

    private var head: some View {
        let v = verdict
        return VStack(alignment: .leading, spacing: expanded ? 18 : SheetFit.margin) {
            if expanded {
                WideOrStacked(side: 330, wideFrom: 780, spacing: 32) {
                    identity()
                    nationalPlate(v)
                }
                verdictBand(v)
                baliBlock(v)
                riskRow(v)
            } else {
                // The collapsed sheet is verdict-first at every width: the app's real main pane is about 807 pt at the minimum window (the
                // sidebar takes 232 of 1040), under the 780 where a plate sits beside the title, and the card is half the window tall. So
                // title, the band, and the plate as one thin row after it (D2 VERDICT-FIRST, #8492 gate).
                identity(official: false)
                    .censusFrame("head.compact")   // on the title block, which stands wherever the band does: the head's own frame runs below the fold
                verdictBand(v).background(SheetFit.reader(.band))
                compactPlate(v)
                if !isID { compactOfficial }
            }
        }
    }

    /// The collapsed head's plate and official title: measured always, drawn only when `collapsedRows` holds them (the 12 pt spacing under
    /// the last drawn row is then the sheet's own margin, never a sliver of the next row).
    private func compactPlate(_ v: KBLIVerdict) -> some View {
        let on = collapsedRows >= .plate
        return nationalPlate(v, drawn: on).censusFrame("plate.hidden", when: !on).background(SheetFit.reader(.plate))
            .opacity(on ? 1 : 0).allowsHitTesting(on).accessibilityHidden(!on)
    }

    private var compactOfficial: some View {
        let on = collapsedRows >= .official
        return officialTitle.censusFrame("official", when: on).censusFrame("official.hidden", when: !on).background(SheetFit.reader(.official))
            .opacity(on ? 1 : 0).allowsHitTesting(on).accessibilityHidden(!on)
    }

    /// The record's own title in Bahasa Indonesia, labelled (EN only): the collapsed sheet shows it after the verdict band and the plate.
    private var officialTitle: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(LabelBook.officialTitleLabel).font(Theme.scalable(11)).foregroundStyle(Theme.muted)
            Text(LabelBook.officialTitle(kbli)).font(Theme.scalable(15)).foregroundStyle(Theme.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func identity(official: Bool = true) -> some View {
        HStack(alignment: .top, spacing: 16) {
            VStack(alignment: .leading, spacing: official ? 8 : 4) {
                Text("KBLI \(kbli.kode) · 2025")
                    .font(Theme.scalable(11, weight: .semibold, design: .monospaced)).tracking(1.0)
                    .foregroundStyle(Theme.faint)
                StepDownTitle(text: LabelBook.title(kbli, isID: isID))
                    .accessibilityAddTraits(.isHeader)
                    .censusFrame("title")
                if !isID && official { officialTitle }
            }
            // IMM: the division glyph sits beside the title, never under its text (Q28), a title's width after it as on the card; a title
            // that takes the whole row leaves it the column's edge.
            // (The collapsed sheet's compact head gives its row to the title: no glyph there.)
            if immersive && Theme.decorationsVisible && expanded {
                GlyphStroke(division: Int(kbli.kode.prefix(2)) ?? 0, size: 64, alpha: Theme.mode == .light ? 0.55 : 0.5, width: 1.6)
                    .padding(.leading, 32)
                    .modifier(Beat(p: arrival, from: 0, to: 0.6, dx: 16, fade: false))
                    .censusFrame("glyph")
                    .accessibilityHidden(true)
            }
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .modifier(Beat(p: immersive ? arrival : 1, from: 0, to: 0.35, dy: 6))
    }

    /// The national answer, from `KBLIVerdict.ownershipLine` and nothing else (IMM-L binding (a)): the word is its first half, the
    /// figure its cap. The cap counts up to its value (M2); the axis's own source line stays behind "Source".
    private func nationalPlate(_ v: KBLIVerdict, drawn: Bool = true) -> some View {
        let parts = v.ownershipLine(isID: isID).components(separatedBy: " · ")
        let tone: Theme.Tone = { switch v.national { case .open: return .open; case .restricted: return .restricted
                                                    case .closed: return .closed; case .undetermined: return .neutral } }()
        let c = Theme.chip(tone)
        // The collapsed sheet (470 pt) carries a compact plate: label, chip, figure and "Max foreign" on one row, Source under it, so the
        // verdict band stays on the screen at the app's minimum window (D2 VERDICT-FIRST). The expanded sheet takes the card's whole plate.
        let compact = !expanded
        func capRow(_ cap: Int) -> some View {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Group {
                    if immersive { CountUpPercent(p: arrival, value: cap) } else { Text("\(cap)%") }
                }
                .font(Theme.display(compact ? 34 : 64)).monospacedDigit().foregroundStyle(Theme.white)
                .censusFrame("cap", "", when: drawn)
                Text(lang.t("rich.fact.pma")).font(Theme.scalable(11)).foregroundStyle(Theme.muted)
            }
        }
        let label = Text(isID ? "NASIONAL" : "NATIONAL")
            .font(Theme.scalable(9.5, weight: .heavy, design: .monospaced)).tracking(0.9).foregroundStyle(Theme.faint)
        let chip = Text(parts[0]).font(Theme.scalable(11, weight: .semibold)).foregroundStyle(c.fg).textCase(isID ? .uppercase : nil)
            .padding(.vertical, 4).padding(.horizontal, 8)
            .background(c.bg, in: RoundedRectangle(cornerRadius: 2))
            .censusFrame("chip.national", CensusTone.national(verdict: v), when: drawn)
        return VStack(alignment: .leading, spacing: compact ? 6 : 10) {
            if compact {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    label
                    chip
                    if let cap = v.nationalCap { capRow(cap) }
                    else if parts.count > 1 { Text(parts[1]).font(Theme.scalable(13, weight: .semibold)).foregroundStyle(Theme.muted) }
                    Spacer(minLength: 8)
                    SourceDisclosure(text: AxisSource.national(kbli, isID: isID), isID: isID)
                }
            } else {
                label
                chip
                if let cap = v.nationalCap { capRow(cap) }
                else if parts.count > 1 { Text(parts[1]).font(Theme.scalable(15, weight: .semibold)).foregroundStyle(Theme.muted) }
            }
            if !compact { SourceDisclosure(text: AxisSource.national(kbli, isID: isID), isID: isID) }
        }
        .padding(.horizontal, compact ? 14 : 20).padding(.vertical, compact ? 8 : 20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.inkLift, in: RoundedRectangle(cornerRadius: 2))
        .overlay(RoundedRectangle(cornerRadius: 2).strokeBorder(Theme.lineSoft, lineWidth: 1))
        .shadow(color: .black.opacity(immersive ? Elevation.raised.alpha : 0), radius: Elevation.raised.radius, y: Elevation.raised.dy)
        .modifier(Beat(p: immersive ? arrival : 1, from: 0.1, to: 0.45, dy: 6))
        .censusFrame("plate", when: drawn)
    }

    /// Bali: the axis's own claim, its source behind "Source". (The map beside it is the next PR.)
    private func baliBlock(_ v: KBLIVerdict) -> some View {
        let color = baliColor(v), tone = Theme.chip(LabelBook.baliChip(v, isID: isID).tone)
        return VStack(alignment: .leading, spacing: 8) {
            Text("BALI").font(Theme.scalable(9.5, weight: .heavy, design: .monospaced)).tracking(0.9).foregroundStyle(Theme.faint)
            Text(LabelBook.baliChip(v, isID: isID).word).font(Theme.scalable(11, weight: .semibold)).foregroundStyle(tone.fg).textCase(isID ? .uppercase : nil)
                .padding(.vertical, 4).padding(.horizontal, 8)
                .background(tone.bg, in: RoundedRectangle(cornerRadius: 2))
            Text(baliValue(v)).font(Theme.scalable(15, weight: .semibold))
                .foregroundStyle(v.baliTag == "UNDETERMINED" ? Theme.muted : color)
                .fixedSize(horizontal: false, vertical: true)
            SourceDisclosure(text: AxisSource.bali(kbli, isID: isID), isID: isID)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .modifier(Beat(p: immersive ? arrival : 1, from: 0.4, to: 0.75, dy: 6))
    }

    /// OSS risk is a row of the head (risk, then its source behind "Source"), not a card.
    private func riskRow(_ v: KBLIVerdict) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline, spacing: 16) {
                Text(isID ? "RISIKO OSS" : "OSS RISK").font(Theme.scalable(9.5, weight: .heavy, design: .monospaced)).tracking(0.9)
                    .foregroundStyle(Theme.faint)
                Text(riskValue(v)).font(Theme.scalable(15, weight: .semibold)).foregroundStyle(riskColor(v))
                Spacer(minLength: 0)
            }
            SourceDisclosure(text: AxisSource.risk(kbli, verdict: v, isID: isID), isID: isID)
        }
        .padding(.vertical, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .overlay(alignment: .top) { Rectangle().fill(Theme.lineSoft).frame(height: 1) }
        .overlay(alignment: .bottom) { Rectangle().fill(Theme.lineSoft).frame(height: 1) }
        .modifier(Beat(p: immersive ? arrival : 1, from: 0.55, to: 0.85, dy: 6))
    }

    // MARK: the three axes, each with its own source line (the graft)

    /// The Bali axis answers the PROVINCIAL question only. It used to render `.open` as "Open to a
    /// PT PMA", which on a nationally-closed record sat under a banner saying the opposite
    /// (council round 2, codex-gpt-5.6-sol): the axis cannot promise registrability, only that the
    /// moratorium does not block it. The headline above is where precedence is resolved.
    private func baliValue(_ v: KBLIVerdict) -> String {
        switch v.bali {
        case .open:         return isID ? "Tidak diblokir oleh moratorium Bali" : "Not blocked by the Bali moratorium"
        case .blocked:      return isID ? "Diblokir untuk PT PMA" : "Blocked for a PT PMA"
        case .undetermined: return isID ? "Tidak ditentukan oleh data" : "Not determined by the records"
        }
    }

    private func riskValue(_ v: KBLIVerdict) -> String {
        switch v.risk {
        case .known(let label): return Theme.riskShortLabel(label, isID: isID)
        case .absent:           return RiskCell.absentText(isID: isID)
        }
    }

    private func baliColor(_ v: KBLIVerdict) -> Color {
        switch v.bali {
        case .open: return Theme.pmaOpen
        case .blocked: return Theme.pmaClosed
        case .undetermined: return Theme.faint
        }
    }

    private func riskColor(_ v: KBLIVerdict) -> Color {
        switch v.risk {
        case .known(let label): return Theme.riskColor(label)
        case .absent: return Theme.faint
        }
    }

    // MARK: the binding answer

    private func verdictBand(_ v: KBLIVerdict) -> some View {
        let closed: Bool = { switch v.headline { case .nationallyClosed, .baliBlocked: return true; default: return false } }()
        let undetermined: Bool = { switch v.headline { case .nationalUndetermined, .baliUndetermined: return true; default: return false } }()
        let color: Color = undetermined ? Theme.faint : (closed ? Theme.pmaClosed : Theme.pmaOpen)
        let icon = undetermined ? "questionmark.diamond" : (closed ? "xmark.octagon.fill" : "checkmark.seal.fill")
        return HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon).font(Theme.scalable(19, weight: .semibold)).foregroundStyle(color)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 5) {
                Text(isID ? "PUTUSAN BALI" : "BALI VERDICT")
                    .font(Theme.scalable(10, weight: .heavy, design: .monospaced)).tracking(0.8)
                    .foregroundStyle(color)
                Text(headlineText(v))
                    .font(Theme.scalable(19, weight: .semibold, design: .serif))
                    .foregroundStyle(Theme.white).fixedSize(horizontal: false, vertical: true)
                if let reason = v.headlineReason, reason.isEmpty == false {
                    Text(LabelBook.emphasis(displayedReason(reason), size: 12))
                        .font(Theme.scalable(12)).foregroundStyle(Theme.muted).lineSpacing(2)
                        .fixedSize(horizontal: false, vertical: true)
                        .textSelection(.enabled)
                }
                if undetermined {
                    Text(isID
                         ? "Tidak ada verdikt yang dapat dinyatakan dari catatan ini. Bawa kode ini ke konsultasi — jangan diperlakukan sebagai terbuka maupun tertutup."
                         : "No verdict can be stated from these records. Bring this code to the consultation — do not read it as open or as closed.")
                        .font(Theme.scalable(12)).foregroundStyle(Theme.muted).lineSpacing(2)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            Spacer(minLength: 0)
        }
        .padding(15)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(color.opacity(undetermined ? 0.05 : 0.08),
                    in: RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous))
        .overlay(alignment: .leading) {
            RoundedRectangle(cornerRadius: 2).fill(color).frame(width: 4).padding(.vertical, 12)
        }
        .overlay(RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous)
            .strokeBorder(color.opacity(0.25), lineWidth: 1))
        .overlay(alignment: .top) {
            if immersive {
                Rectangle().fill(color).frame(height: 3).modifier(DrawnRule(p: arrival, from: 0.1, to: 0.5)).censusFrame("rule")
            }
        }
        .modifier(Beat(p: immersive ? arrival : 1, from: 0.15, to: 0.5, dy: 6))
        .censusFrame("band")
        .accessibilityElement(children: .combine)
    }


    private func headlineText(_ v: KBLIVerdict) -> String {
        switch v.headline {
        case .nationallyClosed:
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

    // MARK: actions

    private var actions: some View {
        HStack(spacing: 10) {
            Button { state.askZantara(about: kbli) } label: {
                Text(isID ? "Tanya Zantara tentang kode ini" : "Ask Zantara about this code")
                    .font(Theme.scalable(12, weight: .semibold))
                    .padding(.horizontal, 14).padding(.vertical, 8)
                    .background(Theme.accent.opacity(0.16), in: RoundedRectangle(cornerRadius: Theme.radiusMd))
                    .overlay(RoundedRectangle(cornerRadius: Theme.radiusMd).strokeBorder(Theme.accent.opacity(0.5), lineWidth: 1))
                    .foregroundStyle(Theme.accent)
            }
            .buttonStyle(.plain)

            Button { expanded.toggle() } label: {
                HStack(spacing: 6) {
                    Text(expanded ? (isID ? "Tutup dosir" : "Collapse dossier")
                                  : (isID ? "Buka dosir lengkap" : "Open the full dossier"))
                    Image(systemName: expanded ? "chevron.down" : "chevron.up")
                }
                .font(Theme.scalable(12, weight: .medium))
                .padding(.horizontal, 14).padding(.vertical, 8)
                .background(Theme.inkLift, in: RoundedRectangle(cornerRadius: Theme.radiusMd))
                .overlay(RoundedRectangle(cornerRadius: Theme.radiusMd).strokeBorder(Theme.hairline, lineWidth: 1))
                .foregroundStyle(Theme.white)
            }
            .buttonStyle(.plain)
            Spacer(minLength: 0)
        }
    }
}

/// The grey provenance line of an axis, collapsed behind "Source" / "Sumber" (owner ruling 2026-10-12): a reader who wants the locator
/// clicks for it. `KBLI_SOURCE_OPEN` opens every one (the text census and the content proof count the words with them open).
struct SourceDisclosure: View {
    let text: String
    let isID: Bool
    @State private var open = ProcessInfo.processInfo.environment["KBLI_SOURCE_OPEN"] != nil

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Button { open.toggle() } label: {
                HStack(spacing: 4) {
                    Text(isID ? "Sumber" : "Source")
                    Image(systemName: open ? "chevron.down" : "chevron.right").font(Theme.scalable(8, weight: .bold))
                }
                .font(Theme.scalable(10.5, weight: .semibold)).foregroundStyle(Theme.muted)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            if open {
                Text(text)
                    .font(Theme.scalable(9.5, design: .monospaced)).foregroundStyle(Theme.faint)
                    .fixedSize(horizontal: false, vertical: true).textSelection(.enabled)
            }
        }
        .censusFrame("source", open ? "open" : "closed")
    }
}

/// Two children side by side when the column is `wideFrom` wide or more (the second one `side` wide), stacked below it when not
/// (the narrow rule, owner 2026-10-12). A `Layout`, not `ViewThatFits`: the title wraps, so its ideal width never fits.
struct WideOrStacked: Layout {
    var side: CGFloat
    var wideFrom: CGFloat
    var spacing: CGFloat

    private func wide(_ w: CGFloat) -> Bool { w >= wideFrom }

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        guard subviews.count == 2 else { return .zero }
        let w = proposal.width ?? wideFrom
        if wide(w) {
            let a = subviews[0].sizeThatFits(ProposedViewSize(width: w - side - spacing, height: nil))
            let b = subviews[1].sizeThatFits(ProposedViewSize(width: side, height: nil))
            return CGSize(width: w, height: max(a.height, b.height))
        }
        let a = subviews[0].sizeThatFits(ProposedViewSize(width: w, height: nil))
        let b = subviews[1].sizeThatFits(ProposedViewSize(width: w, height: nil))
        return CGSize(width: w, height: a.height + spacing + b.height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        guard subviews.count == 2 else { return }
        if wide(bounds.width) {
            let aw = bounds.width - side - spacing
            subviews[0].place(at: CGPoint(x: bounds.minX, y: bounds.minY), anchor: .topLeading, proposal: ProposedViewSize(width: aw, height: nil))
            subviews[1].place(at: CGPoint(x: bounds.maxX - side, y: bounds.minY), anchor: .topLeading, proposal: ProposedViewSize(width: side, height: nil))
        } else {
            let a = subviews[0].sizeThatFits(ProposedViewSize(width: bounds.width, height: nil))
            subviews[0].place(at: CGPoint(x: bounds.minX, y: bounds.minY), anchor: .topLeading, proposal: ProposedViewSize(width: bounds.width, height: nil))
            subviews[1].place(at: CGPoint(x: bounds.minX, y: bounds.minY + a.height + spacing), anchor: .topLeading, proposal: ProposedViewSize(width: bounds.width, height: nil))
        }
    }
}

/// The title is content and is never truncated. At display 44 it takes up to two lines; a longer one steps down to 34, then to 28, just
/// enough to keep the verdict band on the screen (D2 VERDICT-FIRST, 2026-08-11: the binding answer leads; at the app's minimum window
/// height this is the difference between a reader seeing the verdict and having to scroll for it). At 28 it takes the lines it needs.
struct StepDownTitle: View {
    let text: String

    var body: some View {
        FiniteHeight {
            ViewThatFits(in: .vertical) {
                AtMostLines(lines: 2) { title(44); reference(44) }
                AtMostLines(lines: 2) { title(34); reference(34) }
                title(28)
            }
        }
    }

    private func title(_ size: CGFloat) -> some View {
        Text(text).font(Theme.display(size)).foregroundStyle(Theme.white).fixedSize(horizontal: false, vertical: true)
    }

    /// One line at the same size, never drawn: the ruler the line count is read against.
    private func reference(_ size: CGFloat) -> some View {
        Text("Ag").font(Theme.display(size)).fixedSize().hidden()
    }
}

/// What the collapsed sheet needs to show its head down to the verdict band, read by `SearchListView` to size the detent (D2 VERDICT-FIRST:
/// the verdict is on the screen at every window, for every title, and nothing is cut to get it there).
enum SheetFit {
    static let space = "sheet-fit"
    /// Below the last drawn row, so its last line is not on the sheet's edge.
    static let margin: CGFloat = 12
    static func reader(_ row: SheetRows) -> some View {
        GeometryReader { g in
            let end = g.frame(in: .named(space)).maxY + margin
            Color.clear.preference(key: SheetFitKey.self, value: SheetFitValue(
                band: row == .band ? end : 0, plate: row == .plate ? end : 0, official: row == .official ? end : 0))
        }
    }
}

/// The collapsed sheet's rows, top to bottom: each one is drawn only when it and every row above it fit whole (H1d O1).
enum SheetRows: Int, Comparable {
    case band, plate, official
    static func < (a: SheetRows, b: SheetRows) -> Bool { a.rawValue < b.rawValue }
}

/// Where each collapsed row ends in the sheet, plus the margin below it: the three cumulative fits. An unmeasured row is 0 (the EN official
/// title does not exist in Indonesian).
struct SheetFitValue: Equatable {
    var band: CGFloat = 0, plate: CGFloat = 0, official: CGFloat = 0

    /// The most rows that fit WHOLE under `cap`; the band is always in.
    func rows(cap: CGFloat) -> SheetRows {
        if official > 0, official <= cap { return .official }
        if plate > 0, plate <= cap { return .plate }
        return .band
    }

    /// The collapsed sheet's height: the last drawn row and the margin under it, nothing more (no slack for a sliver of the next row to
    /// show in), and never past the cap. 0 until the band is measured.
    func height(cap: CGFloat) -> CGFloat {
        guard band > 0 else { return 0 }
        let fit: CGFloat
        switch rows(cap: cap) { case .band: fit = band; case .plate: fit = plate; case .official: fit = official }
        return min(fit, max(cap, 0))
    }
}

struct SheetFitKey: PreferenceKey {
    static let defaultValue = SheetFitValue()
    static func reduce(value: inout SheetFitValue, nextValue: () -> SheetFitValue) {
        let n = nextValue()
        value.band = max(value.band, n.band); value.plate = max(value.plate, n.plate); value.official = max(value.official, n.official)
    }
}

/// Takes its first subview's size, or reports a height no frame can hold when that subview wraps to more than `lines` lines (its second
/// subview is one line of the same font, the ruler).
struct AtMostLines: Layout {
    var lines: Int

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        guard subviews.count == 2 else { return .zero }
        let t = subviews[0].sizeThatFits(proposal), one = subviews[1].sizeThatFits(.unspecified).height
        return t.height > one * (CGFloat(lines) + 0.5) ? CGSize(width: t.width, height: 10_000_000) : t
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        guard subviews.count == 2 else { return }
        subviews[0].place(at: bounds.origin, anchor: .topLeading, proposal: ProposedViewSize(width: bounds.width, height: nil))
        subviews[1].place(at: bounds.origin, anchor: .topLeading, proposal: .zero)
    }
}

/// Proposes its one child a height it can always be measured against (a `ViewThatFits` handed an unspecified height takes its first child).
struct FiniteHeight: Layout {
    static let height: CGFloat = 1_000_000

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        guard let child = subviews.first else { return .zero }
        return child.sizeThatFits(ProposedViewSize(width: proposal.width, height: Self.height))
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        subviews.first?.place(at: bounds.origin, anchor: .topLeading, proposal: ProposedViewSize(width: bounds.width, height: bounds.height))
    }
}
