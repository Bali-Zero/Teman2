import Foundation

/// A per-code, per-LANGUAGE enrichment + translation overlay that sits ON TOP of the shared
/// KBLI dataset. The dataset is bilingually split (judul/uraian/kewajiban are ID-only; intel_2026
/// is EN-only) and is curated/shared with the web — we do NOT mutate it. Instead this overlay
/// supplies the MISSING translations and the OSS-rigor authority fields (Dasar Hukum / Kewenangan /
/// PB UMKU / Regulasi) so the detail card can render fully in EN *or* fully in ID, with citations.
///
/// File: Resources/kbli-overlay.json — shape: { "<code>": { "en": {…}, "id": {…} } }.
/// Only curated codes need an entry; codes without one fall back to the raw dataset fields.
struct CodeOverlay: Codable, Hashable {
    let title: String?          // localized judul
    let meaning: String?        // localized "what it means"
    let verdict: String?        // localized verdict (whatYouNeed)
    let baliContext: String?    // localized reality-check (markdown)
    let whoFor: String?
    let changed: String?
    let related: [Related]?     // localized related-code descriptions
    let authority: Authority?   // OSS-rigor block (citations) — same in both langs, labels localized
    let roadmap: [Step]?        // the registration roadmap (numbered steps) — overlay-only content
    let pricing: Pricing?       // Bali Zero service pricing (PT PMA setup / virtual office)

    struct Related: Codable, Hashable {
        let code: String
        let note: String
        let title: String?      // localized short title for the mini-card (e.g. "Homestay")
        let status: String?     // short status label for the card pill ("Open 100%" / "Closed to PMA")
        let open: Bool?         // drives the status-dot color (sage when true, coral when false)
    }

    /// One numbered registration-roadmap step.
    struct Step: Codable, Hashable {
        let title: String       // "PT PMA incorporation"
        let detail: String?     // "notary deed, AHU, TDP"
        let duration: String?   // "1–2w" / "1–3d" / "Otomatis" / "post-license"
    }

    /// Bali Zero service pricing for this activity (rendered as the quiet footer ledger).
    struct Pricing: Codable, Hashable {
        let setupLabel: String? // "PT PMA Setup"
        let setup: String?      // "IDR 20.000.000"
        let voLabel: String?    // "Virtual Office"
        let vo: String?         // "IDR 5.000.000"
        let note: String?       // "5.000+ companies registered since 2020"
        let stat: String?       // "5k+ · ★ 4.9 · ~15 min"
    }

    /// The authority / legal-basis ledger — the trust spine. Values are real (from the dataset
    /// pma_source / pp28_sources / per_skala.kewenangan); labels are localized by the UI.
    struct Authority: Codable, Hashable {
        let dasarHukum: [String]?     // legal basis documents (Perpres/PP/Permen…)
        let kewenangan: [String]?     // licensing authority levels
        let pbUmku: [String]?         // ancillary business licenses (PB UMKU)
        let regulasi: [String]?       // governing regulations
        let predecessor: String?      // KBLI 2020 predecessor code
        let verified: String?         // "last verified" date stamp (authority signal)
    }
}

/// Loads + serves the overlay bundle. Pure data, offline, no PII.
final class OverlayStore {
    /// One shared instance: `init()` reads its JSON files, so surfaces that only need
    /// `displayReason` share this rather than each parsing the bundle again.
    static let shared = OverlayStore()

    private let byCode: [String: [String: CodeOverlay]]   // code → lang → overlay
    /// Dataset-string translation map: the dataset's scope names / obligations / requirements are
    /// Indonesian-only, so the EN card showed Indonesian ("macaronic"). This maps each Indonesian
    /// source string → its English translation (army-translated + bilingual-QA'd). Lookup is by the
    /// HTML-stripped source so it matches what the card renders.
    private let dataEN: [String: String]
    /// The dataset's `l4_bali.reason` strings leaked in mixed English+Italian (e.g.
    /// "real estate: proposto per chiusura PMA Bali"). This maps each raw source string →
    /// {en, id} clean regulatory translations so the verdict banner reads cleanly in either
    /// language. Keyed by the raw reason string exactly as it appears in the dataset.
    private let reasonI18n: [String: [String: String]]
    /// The dataset's `intel_2026.baliContext` notes are English-only, so the ID card showed English
    /// ("macaronic"). This maps each English baliContext source → its Indonesian translation
    /// (army-translated + QA'd). Keyed by the HTML-stripped English source.
    private let baliContextID: [String: String]
    /// The curated `related[]` mini-cards carry an English `note` and an Indonesian `title` (the
    /// official KBLI name). So the EN card showed Indonesian related-titles and the ID card showed
    /// English related-notes — both macaronic. The title is resolved EN via `dataString` (the judul
    /// translation map already covers 303/309); the note is resolved ID via this map (army-translated).
    /// Keyed by the English note source exactly as stored in the overlay.
    private let relatedNoteID: [String: String]

    init() {
        func loadOverlay(_ url: URL?) -> [String: [String: CodeOverlay]] {
            guard let url, let raw = try? Data(contentsOf: url),
                  let obj = try? JSONDecoder().decode([String: [String: CodeOverlay]].self, from: raw)
            else { return [:] }
            return obj
        }
        func loadDict(_ name: String) -> [String: String] {
            let url = Bundle.main.url(forResource: name, withExtension: "json")
                ?? URL(fileURLWithPath: Bundle.main.bundleURL
                    .appendingPathComponent("Contents/Resources/\(name).json").path)
            guard let raw = try? Data(contentsOf: url),
                  let obj = try? JSONDecoder().decode([String: String].self, from: raw) else { return [:] }
            return obj
        }
        let url = Bundle.main.url(forResource: "kbli-overlay", withExtension: "json")
            ?? URL(fileURLWithPath: Bundle.main.bundleURL
                .appendingPathComponent("Contents/Resources/kbli-overlay.json").path)
        func loadNested(_ name: String) -> [String: [String: String]] {
            let url = Bundle.main.url(forResource: name, withExtension: "json")
                ?? URL(fileURLWithPath: Bundle.main.bundleURL
                    .appendingPathComponent("Contents/Resources/\(name).json").path)
            guard let raw = try? Data(contentsOf: url),
                  let obj = try? JSONDecoder().decode([String: [String: String]].self, from: raw) else { return [:] }
            return obj
        }
        byCode = loadOverlay(url)
        dataEN = loadDict("kbli-data-i18n-en")
        reasonI18n = loadNested("kbli-reason-i18n")
        baliContextID = loadDict("kbli-balicontext-i18n-id")
        relatedNoteID = loadDict("kbli-related-note-i18n-id")
    }

    /// Overlay for a code in a language, falling back to the other language if one is missing.
    func overlay(_ code: String, lang: String) -> CodeOverlay? {
        guard let langs = byCode[code] else { return nil }
        return langs[lang] ?? langs["en"] ?? langs.values.first
    }

    /// STRICT-language overlay: no cross-language fallback. For TEXT fields (title / meaning /
    /// verdict / baliContext) the cross-language fallback is the macaronic bug, not a feature:
    /// 321/322 curated codes are EN-only, so the ID card was showing English prose ON TOP of a
    /// dataset whose judul/uraian are already native Indonesian. Callers use this for prose and
    /// keep `overlay()` for structural fields (roadmap, authority citations) where content is
    /// language-neutral.
    func overlayStrict(_ code: String, lang: String) -> CodeOverlay? {
        byCode[code]?[lang]
    }

    /// English rendering of a dataset (Indonesian) string. Returns the translation when present,
    /// else the original (so untranslated codes degrade gracefully, never crash). Caller passes the
    /// HTML-stripped string. `isID == true` → return the Indonesian source unchanged.
    func dataString(_ idSource: String, isID: Bool) -> String {
        if isID { return idSource }
        return dataEN[idSource] ?? idSource
    }

    /// Clean bilingual rendering of a dataset `l4_bali.reason` string (raw strings are mixed
    /// English+Italian). Returns the EN translation when `!isID`, the ID translation when `isID`.
    /// Falls back to the raw string if unmapped (graceful — never crashes, never blanks).
    func reasonString(_ rawReason: String, isID: Bool) -> String {
        guard let pair = reasonI18n[rawReason] else { return rawReason }
        return (isID ? pair["id"] : pair["en"]) ?? rawReason
    }

    /// The ONE display path for an `l4_bali.reason`: the en translation table, and in Indonesian
    /// the registry sheet's labelled-quote fallback (`RegistryVerdictSheet.swift:42-44`) when the
    /// reason has no id translation, so half-translated prose never blends into an id surface.
    func displayReason(_ raw: String, isID: Bool) -> String {
        guard isID else { return reasonString(raw, isID: false) }
        let t = reasonString(raw, isID: true)
        return t != raw ? t : "Kutipan catatan (EN): \(raw)"
    }

    /// The PRIMARY title every surface shows, lifted verbatim from the ledger's `primaryTitle`
    /// (`KBLIRegistryView.swift:173-184`). ID → the strict Indonesian overlay title, else the raw
    /// `judul`. EN → the curated overlay title when it is not just the Indonesian `judul` again, else
    /// the army-translated `judul` — never Indonesian in an English card. The content pack's frozen
    /// titles ("Villa Rental" for 55203) are this function's output, not `KBLIStore.judulEN`'s.
    func primaryTitle(_ k: KBLI, isID: Bool) -> String {
        if isID { return overlayStrict(k.kode, lang: "id")?.title ?? k.judul }
        if let t = overlay(k.kode, lang: "en")?.title,
           t.trimmingCharacters(in: .whitespaces) != k.judul.trimmingCharacters(in: .whitespaces) {
            return t
        }
        return dataString(k.judul, isID: false)
    }

    /// FALLBACK Bali-verdict subtitle template — consumed ONLY when the per-code, cured
    /// `l4_bali.reason` is absent or empty (D2.1, 2026-08-11: the caller now prefers `l4_bali.reason`
    /// whenever present, because it carries a citation/locator for THIS code — e.g. "Lampiran II
    /// p.15, entry 48" — that a generic template can never provide; this function is the last resort
    /// for codes without curated prose). GENERATED from the structured `l4_bali.status` (a 🔵
    /// transitive field), never read from free-prose, so a code that DOES fall back here can never
    /// carry a stale hand-authored citation. The status itself is derived upstream from the frozen
    /// 🟢 fields (pma_status, pma_max_asing, per_skala scales).
    ///
    /// CHIUSO_PMA_NO_BESAR was itself corrected 2026-08-03 (RETRACTED): the earlier wording inferred
    /// closure from "OSS has no Usaha Besar scale row for this code" — an inference from PP 28/2025
    /// OSS-RBA scale-gating (Pasal 127). That inference is withdrawn. The actual, on-instrument basis
    /// is the allocation to Koperasi/UMKM in Perpres 10/2021 as amended by 49/2021, Lampiran II
    /// (column "dialokasikan") — not a scale-gating inference at all.
    ///
    /// Returns nil to fall back to no subtitle for statuses without a canonical generated form.
    static func generatedReason(status: String?, isID: Bool) -> String? {
        switch status {
        case "CHIUSO_PMA_NO_BESAR":
            return isID
                ? "Dialokasikan untuk Koperasi & UMKM dalam Perpres 10/2021 jo. 49/2021 Lampiran II — PT PMA tidak dapat mengambil bidang usaha ini."
                : "Allocated to Koperasi & UMKM by Perpres 10/2021 as amended by 49/2021, Annex II (dialokasikan) — a PT PMA cannot take this bidang usaha."
        case "TERTUTUP":
            return isID
                ? "Tertutup untuk kepemilikan asing (TERTUTUP · 0%). Hanya badan usaha milik Indonesia / publik; PT PMA tidak dapat mendaftarkannya."
                : "Closed to foreign ownership (TERTUTUP · 0%). Reserved for Indonesian / public entities; a PT PMA cannot register it."
        case "BLOCCATO_CLASSE_RISCHIO", "BLOCCATO_DIPENDE_SCOPE":
            return isID
                ? "Diblokir di Bali oleh moratorium provinsi 13 Mei 2026: kelas risiko OSS rendah/menengah-rendah pada skala Besar tidak dapat didaftarkan PMA baru di Bali."
                : "Blocked in Bali by the 13 May 2026 provincial moratorium: the OSS low / medium-low risk class at Besar scale is not registrable by a new PMA in Bali."
        default:
            return nil
        }
    }

    /// ID rendering of a dataset `intel_2026.baliContext` note (the source is English). `isID == false`
    /// returns the English source unchanged; `isID == true` returns the Indonesian translation, else
    /// the English source if unmapped (graceful — non-curated codes degrade, never blank).
    func baliContextString(_ enSource: String, isID: Bool) -> String {
        if !isID { return enSource }
        return baliContextID[enSource] ?? enSource
    }

    /// ID rendering of a curated `related[].note` (the source is English). `isID == false` returns the
    /// English source unchanged; `isID == true` returns the Indonesian translation, else the English
    /// source if unmapped (graceful — never blanks).
    func relatedNoteString(_ enSource: String, isID: Bool) -> String {
        if !isID { return enSource }
        return relatedNoteID[enSource] ?? enSource
    }
}
