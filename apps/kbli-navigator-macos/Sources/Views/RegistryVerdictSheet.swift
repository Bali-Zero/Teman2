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

    /// Pure, headless-callable (`Tests/semantictest`) — the sheet's national-axis card delegates
    /// entirely to `KBLIVerdict.ownershipLine` (OPEN-1, 2026-09-17). `nationalValue` below calls
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
            if scrolls { ScrollView { content } } else { content }
        }
        .background(Theme.ink)
        .overlay(alignment: .top) { Rectangle().fill(Theme.hairlineHi).frame(height: 1) }
        .clipShape(RoundedRectangle(cornerRadius: Theme.radiusLg, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Theme.radiusLg, style: .continuous)
            .strokeBorder(Theme.hairline, lineWidth: 1))
        .shadow(color: .black.opacity(0.28), radius: 18, y: -6)
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: 14) {
            head
            actions
            if expanded {
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
        return VStack(alignment: .leading, spacing: 18) {
            WideOrStacked(side: 330, wideFrom: 780, spacing: 32) {
                identity
                nationalPlate(v)
            }
            verdictBand(v)
            baliBlock(v)
            riskRow(v)
        }
    }

    private var identity: some View {
        HStack(alignment: .top, spacing: 16) {
            VStack(alignment: .leading, spacing: 8) {
                Text("KBLI \(kbli.kode) · 2025")
                    .font(Theme.scalable(11, weight: .semibold, design: .monospaced)).tracking(1.0)
                    .foregroundStyle(Theme.faint)
                Text(LabelBook.title(kbli, isID: isID))
                    .font(Theme.display(44))
                    .foregroundStyle(Theme.white)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityAddTraits(.isHeader)
                    .censusFrame("title")
                if !isID {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(LabelBook.officialTitleLabel).font(Theme.scalable(11)).foregroundStyle(Theme.muted)
                        Text(LabelBook.officialTitle(kbli)).font(Theme.scalable(15)).foregroundStyle(Theme.muted)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            // IMM: the division glyph sits beside the title, never under its text (Q28).
            if immersive && Theme.decorationsVisible {
                GlyphStroke(division: Int(kbli.kode.prefix(2)) ?? 0, size: 64, alpha: Theme.mode == .light ? 0.55 : 0.5, width: 1.6)
                    .modifier(Beat(p: arrival, from: 0, to: 0.6, dx: 16, fade: false))
                    .censusFrame("glyph")
                    .accessibilityHidden(true)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .modifier(Beat(p: immersive ? arrival : 1, from: 0, to: 0.35, dy: 6))
    }

    /// The national answer, from `KBLIVerdict.ownershipLine` and nothing else (IMM-L binding (a)): the word is its first half, the
    /// figure its cap. The cap counts up to its value (M2); the axis's own source line stays behind "Source".
    private func nationalPlate(_ v: KBLIVerdict) -> some View {
        let parts = v.ownershipLine(isID: isID).components(separatedBy: " · ")
        let tone: Theme.Tone = { switch v.national { case .open: return .open; case .restricted: return .restricted
                                                    case .closed: return .closed; case .undetermined: return .neutral } }()
        let c = Theme.chip(tone)
        return VStack(alignment: .leading, spacing: 10) {
            Text(isID ? "NASIONAL" : "NATIONAL")
                .font(Theme.scalable(9.5, weight: .heavy, design: .monospaced)).tracking(0.9).foregroundStyle(Theme.faint)
            Text(parts[0]).font(Theme.scalable(11, weight: .semibold)).foregroundStyle(c.fg)
                .padding(.vertical, 4).padding(.horizontal, 8)
                .background(c.bg, in: RoundedRectangle(cornerRadius: 2))
                .censusFrame("chip.national", CensusTone.national(verdict: v))
            if let cap = v.nationalCap {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Group {
                        if immersive { CountUpPercent(p: arrival, value: cap) } else { Text("\(cap)%") }
                    }
                    .font(Theme.display(64)).monospacedDigit().foregroundStyle(Theme.white)
                    .censusFrame("cap")
                    Text(lang.t("rich.fact.pma")).font(Theme.scalable(11)).foregroundStyle(Theme.muted)
                }
            } else if parts.count > 1 {
                Text(parts[1]).font(Theme.scalable(15, weight: .semibold)).foregroundStyle(Theme.muted)
            }
            SourceDisclosure(text: AxisSource.national(kbli, isID: isID), isID: isID)
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.inkLift, in: RoundedRectangle(cornerRadius: 2))
        .overlay(RoundedRectangle(cornerRadius: 2).strokeBorder(Theme.lineSoft, lineWidth: 1))
        .shadow(color: .black.opacity(immersive ? Elevation.raised.alpha : 0), radius: Elevation.raised.radius, y: Elevation.raised.dy)
        .modifier(Beat(p: immersive ? arrival : 1, from: 0.1, to: 0.45, dy: 6))
        .censusFrame("plate")
    }

    /// Bali: the axis's own claim, its source behind "Source". (The map beside it is the next PR.)
    private func baliBlock(_ v: KBLIVerdict) -> some View {
        let color = baliColor(v), tone = Theme.chip(LabelBook.baliChip(v, isID: isID).tone)
        return VStack(alignment: .leading, spacing: 8) {
            Text("BALI").font(Theme.scalable(9.5, weight: .heavy, design: .monospaced)).tracking(0.9).foregroundStyle(Theme.faint)
            Text(LabelBook.baliChip(v, isID: isID).word).font(Theme.scalable(11, weight: .semibold)).foregroundStyle(tone.fg)
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

    // OPEN-1 (2026-09-17): this used to re-phrase the national axis in the sheet's own words
    // ("Open · cap not recorded", "Closed to foreign capital" — a wording no other surface used).
    // `KBLIVerdict.ownershipLine` is now the ONLY source of this line; a pure delegate so the
    // semantic probe can assert this surface never drifts from the other four again.
    private func nationalValue(_ v: KBLIVerdict) -> String { Self.ownershipLine(kbli, isID: isID) }

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

    private func nationalColor(_ v: KBLIVerdict) -> Color {
        switch v.national {
        case .open: return Theme.pmaOpen
        case .restricted: return Theme.pmaRestricted
        case .closed: return Theme.pmaClosed
        case .undetermined: return Theme.faint
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
                Rectangle().fill(color).frame(height: 3).modifier(DrawnRule(p: arrival, from: 0.1, to: 0.5))
            }
        }
        .modifier(Beat(p: immersive ? arrival : 1, from: 0.15, to: 0.5, dy: 6))
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

/// One axis: the name, the state, and the record fields the state was read from. The source line
/// is selectable — a reader checking the dataset copies the locator instead of retyping it.
struct AxisCard: View {
    let title: String
    let value: String
    let color: Color
    let undetermined: Bool
    let source: String

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(Theme.scalable(9.5, weight: .heavy, design: .monospaced)).tracking(0.9)
                .foregroundStyle(Theme.faint)
            HStack(spacing: 7) {
                if undetermined {
                    Image(systemName: "diamond").font(Theme.scalable(10, weight: .bold)).foregroundStyle(Theme.muted)
                        .accessibilityHidden(true)
                }
                Text(value)
                    .font(Theme.scalable(13, weight: .semibold))
                    .foregroundStyle(undetermined ? Theme.muted : color)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Text(source)
                .font(Theme.scalable(9.5, design: .monospaced))
                .foregroundStyle(Theme.faint)
                .fixedSize(horizontal: false, vertical: true)
                .textSelection(.enabled)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.inkLift.opacity(undetermined ? 0.5 : 1),
                    in: RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous))
        .overlay {
            if undetermined {
                RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous)
                    .strokeBorder(style: StrokeStyle(lineWidth: 1, dash: [3, 2]))
                    .foregroundStyle(Theme.hairlineHi)
            } else {
                RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous)
                    .strokeBorder(Theme.hairline, lineWidth: 1)
            }
        }
        .accessibilityElement(children: .combine)
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
