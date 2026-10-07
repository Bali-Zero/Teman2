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

    /// Pure, headless-callable (`Tests/semantictest`) — the sheet's national-axis card delegates
    /// entirely to `KBLIVerdict.ownershipLine` (OPEN-1, 2026-09-17). `nationalValue` below calls
    /// this SAME function with the view's own `isID`; kept `static` and free of `@EnvironmentObject`
    /// state so a test can assert it against the projection without instantiating a live view.
    static func ownershipLine(_ kbli: KBLI, isID: Bool) -> String {
        KBLIVerdict.of(record: kbli).ownershipLine(isID: isID)
    }

    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager

    private var isID: Bool { lang.lang == .id }
    /// Loaded once, not per render: `OverlayStore()` reads its JSON files in `init`.
    private static let reasons = OverlayStore()

    /// The sentence under the headline, in the reader's language where the record has one. The
    /// rule's reasons and most `l4_bali.reason` strings exist in English only; blended into an
    /// Indonesian sheet they read as half-translated prose, so in Indonesian an untranslated reason
    /// is shown as a LABELLED quote of the record instead (the card's `quotedRuleReason` twin).
    private func displayedReason(_ r: String) -> String {
        guard isID else { return r }
        let translated = Self.reasons.reasonString(r, isID: true)
        return translated != r ? translated : "Kutipan catatan (EN): \(r)"
    }
    private var verdict: KBLIVerdict { KBLIVerdict.of(record: kbli) }

    var body: some View {
        VStack(spacing: 0) {
            grabber
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    identity
                    // VERDICT-FIRST, per the D2 ruling the dossier card already follows
                    // (2026-08-11): the binding answer leads, the three axes and their sources
                    // support it underneath. At the app's minimum window height this is also the
                    // difference between a reader seeing the verdict and having to scroll for it.
                    verdictBlock
                    axisCards
                    actions
                    if expanded {
                        Divider().overlay(Theme.hairline)
                        KBLIRegistryView(kbli: kbli, scrolls: false, showsIdentityAndVerdict: false)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .padding(.horizontal, 24).padding(.top, 4).padding(.bottom, 16)
            }
        }
        .background(Theme.ink)
        .overlay(alignment: .top) { Rectangle().fill(Theme.hairlineHi).frame(height: 1) }
        .clipShape(RoundedRectangle(cornerRadius: Theme.radiusLg, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Theme.radiusLg, style: .continuous)
            .strokeBorder(Theme.hairline, lineWidth: 1))
        .shadow(color: .black.opacity(0.28), radius: 18, y: -6)
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

    private var identity: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("KBLI \(kbli.kode) · 2025")
                .font(Theme.scalable(11, weight: .semibold, design: .monospaced)).tracking(1.0)
                .foregroundStyle(Theme.faint)
            Text(kbli.judul)
                .font(Theme.scalable(26, weight: .bold, design: .serif))
                .foregroundStyle(Theme.white)
                .fixedSize(horizontal: false, vertical: true)
        }
        .accessibilityElement(children: .combine)
    }

    // MARK: the three axes, each with its own source line (the graft)

    /// Three siblings in one row, each taking an equal share and WRAPPING its source line rather
    /// than truncating it (a truncated locator is not a source). Deliberately not `ViewThatFits`:
    /// that measures the ideal, unwrapped width of the source text, which never fits, so it always
    /// collapsed to a single column even in a 1,440pt window.
    private var axisCards: some View {
        HStack(alignment: .top, spacing: 12) { cards(verdict) }
    }

    @ViewBuilder private func cards(_ v: KBLIVerdict) -> some View {
        AxisCard(title: isID ? "NASIONAL" : "NATIONAL",
                 value: nationalValue(v), color: nationalColor(v),
                 undetermined: v.nationalTag == "UNDETERMINED",
                 source: AxisSource.national(kbli, isID: isID))
        AxisCard(title: "BALI",
                 value: baliValue(v), color: baliColor(v),
                 undetermined: v.baliTag == "UNDETERMINED",
                 source: AxisSource.bali(kbli, isID: isID))
        AxisCard(title: isID ? "RISIKO OSS" : "OSS RISK",
                 value: riskValue(v), color: riskColor(v),
                 undetermined: v.risk == .absent,
                 source: AxisSource.risk(kbli, verdict: v, isID: isID))
    }

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

    private var verdictBlock: some View {
        let v = verdict
        let closed: Bool = {
            switch v.headline {
            case .nationallyClosed, .baliBlocked: return true
            default: return false
            }
        }()
        let undetermined: Bool = {
            switch v.headline {
            case .nationalUndetermined, .baliUndetermined: return true
            default: return false
            }
        }()
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
                    Text(displayedReason(reason))
                        .font(Theme.scalable(12)).foregroundStyle(Theme.muted).lineSpacing(2)
                        .fixedSize(horizontal: false, vertical: true)
                        .textSelection(.enabled)
                }
                if undetermined {
                    // What is missing, not just that something is. The sentence names the field
                    // the rule looked at and found unusable — the same locator the Bali axis card
                    // above quotes verbatim.
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
