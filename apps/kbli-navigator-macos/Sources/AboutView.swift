import SwiftUI

/// D4 "Anima Indonesiana" (2026-08-11): custom About window content, opened via
/// `CommandGroup(replacing: .appInfo)` in KBLINavigatorApp — replaces the generic system panel.
/// Variant-aware per Zero's 2026-08-09 app-split ruling: identical content on BKPM, minus the
/// external balizero.com link (`AppVariant.current.showsExternalLinks`).
struct AboutView: View {
    @EnvironmentObject var lang: LanguageManager

    private var appVersion: String {
        (Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String) ?? "1.0"
    }

    /// The bundled dataset's own file modification date — a REAL, self-updating value (never a
    /// hand-maintained date that can silently go stale) rather than any single field inside the
    /// dataset's own metadata, which carries several different sub-pass dates
    /// (l4_bali_injected / prose_pass1_fix / …) and no single canonical "as of" field.
    private var datasetVerifiedDate: String {
        guard let url = Bundle.main.url(forResource: "KBLI_2025_FINAL_CLEAN", withExtension: "json"),
              let attrs = try? FileManager.default.attributesOfItem(atPath: url.path),
              let modified = attrs[.modificationDate] as? Date else { return "—" }
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: modified)
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                BZLogo(size: 56)
                Text(lang.t("app.title"))
                    .font(Theme.scalable(22, weight: .semibold, design: .serif))
                    .foregroundStyle(Theme.white)
                Text("\(lang.t("about.tagline")) · v\(appVersion)")
                    .font(Theme.scalable(10, design: .monospaced))
                    .foregroundStyle(Theme.faint)

                // Draft's `'about'` canvas role draws goldenArc + sprigs + a background guilloché
                // wash into ONE shared canvas (`goldenArc(x,w,h*.92,...); sprigs(x,w*.5,h*.62,60,...);
                // guilloche(x,w,h,...,3,4,[h*.94,10])`) — an earlier v1 pass stacked the arc and
                // sprigs as two independently-framed views (proportions didn't match the source) and
                // omitted the wash entirely. `.topLeading` keeps all three anchored to the same
                // origin the draft's single canvas shares, instead of each view's own frame
                // re-centering it.
                ZStack(alignment: .topLeading) {
                    GoldenArc(width: 340, height: 170 * 0.92, alpha: Theme.decorArcAlpha * 0.8)
                    PadiKapasSprigs(width: 340, height: 170, scale: 60, centerYFraction: 0.62)
                    GuillocheBand(width: 340, height: 170, alpha: Theme.decorAmbientAlpha * 0.5, rows: 3, amplitude: 4, band: (0.94, 10))
                }
                .frame(width: 340, height: 170)

                VStack(spacing: 6) {
                    Text(String(format: lang.t("about.provenance"), datasetVerifiedDate))
                        .font(Theme.scalable(11))
                        .foregroundStyle(Theme.muted)
                        .multilineTextAlignment(.center)
                    Text(lang.t("about.closing"))
                        .font(Theme.scalable(12, weight: .medium, design: .serif))
                        .foregroundStyle(Theme.decorGold)
                        .italic()
                }
                .padding(.horizontal, 24)

                if AppVariant.current.showsExternalLinks {
                    Link("balizero.com", destination: URL(string: "https://balizero.com")!)
                        .font(Theme.scalable(11))
                        .foregroundStyle(Theme.accent)
                }
            }
            .padding(28)
            .frame(maxWidth: .infinity)
        }
        .background(Theme.antracite)
        .frame(width: 420, height: 480)
    }
}
