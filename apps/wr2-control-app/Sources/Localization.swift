import SwiftUI
import Combine

/// Two-language UI (Italian / Indonesian) with an in-app switch, persisted across launches.
/// Default = Italian (Antonello's language); Indonesian for the Bali Zero team.
enum Lang: String, CaseIterable {
    case it, id
    var flag: String { self == .it ? "🇮🇹" : "🇮🇩" }
    var label: String { self == .it ? "Italiano" : "Indonesia" }
}

@MainActor
final class LanguageManager: ObservableObject {
    @Published var lang: Lang {
        didSet { UserDefaults.standard.set(lang.rawValue, forKey: "wr2.lang") }
    }
    init() {
        let saved = UserDefaults.standard.string(forKey: "wr2.lang")
        self.lang = Lang(rawValue: saved ?? "it") ?? .it
    }
    func toggle() { lang = (lang == .it) ? .id : .it }

    /// Look up a key. Falls back to the key itself if missing (visible during dev).
    func t(_ key: String) -> String {
        L10n.table[key]?[lang] ?? L10n.table[key]?[.it] ?? key
    }
}

/// All UI strings, IT + ID. One place to translate. Keep keys stable; values human.
enum L10n {
    static let table: [String: [Lang: String]] = [
        // app / nav
        "app.title":        [.it: "WR2 Control",            .id: "WR2 Control"],
        "app.subtitle":     [.it: "War Room editoriale",    .id: "War Room editorial"],
        "nav.home":         [.it: "Home",                   .id: "Beranda"],
        "nav.home.sub":     [.it: "I più di successo",      .id: "Yang paling sukses"],
        "nav.insights":     [.it: "Insights",               .id: "Insights"],
        "nav.insights.sub": [.it: "Cosa impara l'AI",       .id: "Apa yang dipelajari AI"],
        "nav.studio":       [.it: "Studio",                 .id: "Studio"],
        "nav.studio.sub":   [.it: "Crea e segui una pipeline", .id: "Buat & pantau pipeline"],
        "nav.gallery":      [.it: "Caroselli",              .id: "Karosel"],
        "nav.gallery.sub":  [.it: "I caroselli generati",   .id: "Karosel yang dibuat"],
        "nav.review":       [.it: "Revisione",              .id: "Tinjauan"],
        "nav.review.sub":   [.it: "Cosa aspetta approvazione", .id: "Menunggu persetujuan"],
        "nav.chat":         [.it: "Discuti l'idea",        .id: "Diskusi ide"],
        "nav.chat.sub":     [.it: "Brainstorm con l'AI",   .id: "Brainstorm dengan AI"],
        // home
        "home.sub":         [.it: "I caroselli che hanno funzionato meglio su Instagram", .id: "Karosel paling sukses di Instagram"],
        "home.empty":       [.it: "Nessun carosello pubblicato con metriche", .id: "Belum ada karosel terbit dengan metrik"],
        "home.tap.open":    [.it: "Tocca per aprire il carosello", .id: "Ketuk untuk membuka karosel"],
        "metric.shares":    [.it: "Condivisioni",          .id: "Dibagikan"],
        "metric.likes":     [.it: "Like",                  .id: "Suka"],
        "metric.saves":     [.it: "Salvati",               .id: "Disimpan"],
        "metric.reach":     [.it: "Persone raggiunte",     .id: "Jangkauan"],
        // insights
        "insights.sub":     [.it: "Le scoperte dell'analista IG, in chiaro", .id: "Temuan analis IG, terbuka"],
        "insights.empty":   [.it: "Nessuna analisi disponibile ancora",  .id: "Belum ada analisis"],
        "insights.empty.sub": [.it: "L'analista gira ogni lunedì — il reasoning appare qui.", .id: "Analis berjalan tiap Senin — penalaran muncul di sini."],
        "insights.tech.show": [.it: "Mostra i numeri",            .id: "Tampilkan angka"],
        "insights.tech.hide": [.it: "Nascondi i numeri",          .id: "Sembunyikan angka"],
        // carousel lifecycle bands
        "phase.published":  [.it: "Pubblicato",          .id: "Terbit"],
        "phase.waitlist":   [.it: "In waitlist",         .id: "Daftar tunggu"],
        "phase.review":     [.it: "Da rivedere",         .id: "Perlu ditinjau"],
        "phase.rejected":   [.it: "Scartato",            .id: "Ditolak"],
        // chat
        "chat.title":       [.it: "Discuti l'idea",        .id: "Diskusi ide"],
        "chat.lead":        [.it: "Parla con l'AI per mettere a fuoco l'idea del carosello, poi mandala allo Studio.",
                             .id: "Bicaralah dengan AI untuk mematangkan ide karosel, lalu kirim ke Studio."],
        "chat.placeholder": [.it: "Es. \"un carosello sul nuovo visto E33G, taglio investigativo\"",
                             .id: "Cth. \"karosel tentang visa E33G baru, gaya investigatif\""],
        "chat.send":        [.it: "Invia",                 .id: "Kirim"],
        "chat.reset":       [.it: "Nuova conversazione",   .id: "Percakapan baru"],
        "chat.useidea":     [.it: "Usa questa idea nello Studio", .id: "Pakai ide ini di Studio"],
        "chat.empty":       [.it: "Inizia a descrivere l'idea — l'AI ti aiuta a darle forma.",
                             .id: "Mulai jelaskan idenya — AI membantu membentuknya."],
        "chat.thinking":    [.it: "sto pensando…",         .id: "sedang berpikir…"],
        "chat.with":        [.it: "Parli con",             .id: "Bicara dengan"],
        // diagnostics
        "diag.assistant.ok":   [.it: "Assistente pronto",       .id: "Asisten siap"],
        "diag.assistant.no":   [.it: "Assistente non trovato",  .id: "Asisten tidak ditemukan"],
        "diag.archive.ok":     [.it: "Archivio collegato",      .id: "Arsip terhubung"],
        "diag.archive.no":     [.it: "Archivio non trovato",    .id: "Arsip tidak ditemukan"],
        // studio
        "studio.title":     [.it: "Studio",                 .id: "Studio"],
        "studio.lead":      [.it: "Descrivi un argomento e lascia che la War Room costruisca il carosello.",
                             .id: "Jelaskan sebuah topik dan biarkan War Room membangun karosel."],
        "studio.ask":       [.it: "Di cosa parliamo?",      .id: "Tentang apa?"],
        "studio.placeholder": [.it: "Es. \"fammi un carosello sul nuovo visto E33G\"",
                               .id: "Cth. \"buatkan karosel tentang visa E33G baru\""],
        "studio.create":    [.it: "Crea il carosello",      .id: "Buat karosel"],
        "studio.cancel":    [.it: "Annulla",                .id: "Batalkan"],
        "studio.empty":     [.it: "Nessuna lavorazione in corso", .id: "Tidak ada proses berjalan"],
        "studio.unavailable": [.it: "Assistente non disponibile", .id: "Asisten tidak tersedia"],
        "studio.details":   [.it: "Dettagli tecnici",      .id: "Detail teknis"],
        "studio.details.hide": [.it: "Nascondi dettagli",  .id: "Sembunyikan detail"],
        "studio.ready":     [.it: "Carosello pronto",      .id: "Karosel siap"],
        "studio.process":   [.it: "processo",              .id: "proses"],
        "studio.techlog":   [.it: "Log tecnico",           .id: "Log teknis"],
        // status
        "status.starting":  [.it: "Avvio…",                .id: "Memulai…"],
        "status.running":   [.it: "In lavorazione",        .id: "Sedang berjalan"],
        "status.succeeded": [.it: "Completato",            .id: "Selesai"],
        "status.failed":    [.it: "Errore",                .id: "Kesalahan"],
        "status.cancelled": [.it: "Annullato",             .id: "Dibatalkan"],
        // step states
        "step.pending":     [.it: "In attesa",             .id: "Menunggu"],
        "step.active":      [.it: "In corso",              .id: "Berjalan"],
        "step.done":        [.it: "Fatto",                 .id: "Selesai"],
        "step.failed":      [.it: "Errore",                .id: "Gagal"],
        // step titles
        "step.init":        [.it: "Preparazione",          .id: "Persiapan"],
        "step.brief":       [.it: "Capire l'argomento",    .id: "Memahami topik"],
        "step.storyboard":  [.it: "Scrivere la storia",    .id: "Menulis narasi"],
        "step.images":      [.it: "Creare le immagini",    .id: "Membuat gambar"],
        "step.layout":      [.it: "Comporre le slide",     .id: "Menyusun slide"],
        "step.render":      [.it: "Generare le anteprime", .id: "Membuat pratinjau"],
        "step.critic":      [.it: "Controllo qualità",     .id: "Kontrol kualitas"],
        "step.queue":       [.it: "Pronto per la revisione", .id: "Siap ditinjau"],
        // gallery
        "gallery.title":    [.it: "Caroselli",             .id: "Karosel"],
        "gallery.count":    [.it: "caroselli generati",    .id: "karosel dibuat"],
        "gallery.incompleteHidden": [.it: "nascosti (slide incomplete)", .id: "disembunyikan (slide belum lengkap)"],
        "gallery.refresh":  [.it: "Aggiorna",              .id: "Segarkan"],
        "gallery.empty":    [.it: "Nessun carosello ancora", .id: "Belum ada karosel"],
        "gallery.empty.sub":[.it: "Creane uno dallo Studio", .id: "Buat satu dari Studio"],
        "gallery.slides":   [.it: "slide",                 .id: "slide"],
        "gallery.openfolder":[.it: "Apri cartella",        .id: "Buka folder"],
        "gallery.brief":    [.it: "Brief",                 .id: "Brief"],
        "gallery.fallback": [.it: "Immagini non generate",  .id: "Gambar tidak dibuat"],
        "gallery.fallback.tip": [.it: "Le immagini hero non sono state generate in questa run — il carosello usa la texture di fallback. Rigeneralo per avere le immagini fresche a tutta pagina.",
                                 .id: "Gambar hero tidak dibuat dalam proses ini — karosel memakai tekstur fallback. Buat ulang untuk gambar penuh yang baru."],
        // verdicts
        "verdict.pass":     [.it: "Approvato",             .id: "Disetujui"],
        "verdict.soft_fail":[.it: "Da rivedere",           .id: "Perlu revisi"],
        "verdict.applied":  [.it: "Applicato",             .id: "Diterapkan"],
        "verdict.applied_ready": [.it: "Applicato — pronto", .id: "Diterapkan — siap"],
        // review
        "review.title":     [.it: "Revisione",             .id: "Tinjauan"],
        "review.count":     [.it: "elementi in coda",      .id: "item dalam antrean"],
        "review.empty":     [.it: "La coda è vuota",       .id: "Antrean kosong"],
        // errors (human)
        "err.ratelimit":    [.it: "Limite di utilizzo Claude raggiunto — riprova più tardi.",
                             .id: "Batas penggunaan Claude tercapai — coba lagi nanti."],
        "err.no_claude":    [.it: "Non trovo il comando 'claude' sul sistema.",
                             .id: "Perintah 'claude' tidak ditemukan di sistem."],
        "lang.switch":      [.it: "Lingua",                .id: "Bahasa"],
        // detail view (Task 5)
        "detail.results":      [.it: "Risultati",                                       .id: "Hasil"],
        "detail.shares":       [.it: "condivisioni",                                    .id: "dibagikan"],
        "detail.likes":        [.it: "like",                                            .id: "suka"],
        "detail.comments":     [.it: "commenti",                                        .id: "komentar"],
        "detail.saves":        [.it: "salvati",                                         .id: "disimpan"],
        "detail.reach":        [.it: "copertura",                                       .id: "jangkauan"],
        "detail.notPublished": [.it: "Non ancora pubblicato",                           .id: "Belum diterbitkan"],
        "detail.awaiting":     [.it: "Pubblicato — in attesa di misurazione (~24h)",    .id: "Terbit — menunggu pengukuran (~24 jam)"],
        "detail.markPublished":[.it: "Segna come pubblicato",                           .id: "Tandai sudah terbit"],
        "detail.openDesign":   [.it: "Apri in Zero Design",                             .id: "Buka di Zero Design"],
        "detail.revise":       [.it: "Migliora",                                        .id: "Perbaiki"],
        "detail.rerender":     [.it: "Ri-renderizza",                                   .id: "Render ulang"],
        "detail.publishIG":    [.it: "Pubblica su IG",                                  .id: "Terbitkan ke IG"],
        "detail.publishIGTitle":[.it: "Pubblicare su Instagram?",                        .id: "Terbitkan ke Instagram?"],
        "detail.publishIGInfo":[.it: "Il carosello + caption andranno LIVE su @balizero0. Controlla prima con «Verifica».", .id: "Karosel + caption akan TAYANG di @balizero0. Cek dulu dengan «Periksa»."],
        "detail.publishIGCheck":[.it: "Verifica (dry-run)",                              .id: "Periksa (dry-run)"],
        "detail.publishIGConfirm":[.it: "Pubblica ora",                                  .id: "Terbitkan sekarang"],
        "detail.publishIGCancel":[.it: "Annulla",                                        .id: "Batal"],
        "detail.captionLabel":  [.it: "Caption Instagram",                              .id: "Caption Instagram"],
        "detail.captionLoading":[.it: "Genero la caption…",                             .id: "Membuat caption…"],
        "detail.captionRequired":[.it: "La caption non può essere vuota",                .id: "Caption tidak boleh kosong"],
        "detail.captionTooLong":[.it: "Riduci la caption prima di pubblicare",           .id: "Persingkat caption sebelum terbit"],
        "detail.reviseTitle":  [.it: "Cosa correggere?",                                .id: "Apa yang diperbaiki?"],
        "detail.revisePlaceholder":[.it: "Es. immagini più calde, meno testo per slide",.id: "Mis. gambar lebih hangat, teks lebih sedikit"],
        "detail.reviseLaunch": [.it: "Rilancia",                                        .id: "Jalankan ulang"],
        // Live-run status (scar #2 cure: app no longer mute about a rebuild in flight)
        "run.rebuilding":      [.it: "Rebuild in corso",                                .id: "Sedang dibangun ulang"],
        "run.building":        [.it: "Generazione in corso",                           .id: "Sedang dibuat"],
        "run.minShort":        [.it: " min",                                           .id: " mnt"],
        "run.finishedOK":      [.it: "Rebuild terminato ✓",                            .id: "Rebuild selesai ✓"],
        "run.finishedFail":    [.it: "Rebuild fallito",                                .id: "Rebuild gagal"],
        "run.finishedUnknown": [.it: "Run terminato (esito ignoto)",                   .id: "Run berakhir (hasil tak diketahui)"],
        "run.console":         [.it: "Console live",                                   .id: "Konsol langsung"],
        "run.noLog":           [.it: "Nessun log su disco per questo run.",            .id: "Tidak ada log di disk untuk run ini."],
        // PNG import / export
        "io.downloadSlide":    [.it: "Scarica slide",                                 .id: "Unduh slide"],
        "io.downloadAll":      [.it: "Scarica tutto",                                 .id: "Unduh semua"],
        "io.upload":           [.it: "Carica PNG",                                    .id: "Unggah PNG"],
        "io.chooseFolder":     [.it: "Scegli cartella",                               .id: "Pilih folder"],
        "io.pickPNGs":         [.it: "Scegli i PNG",                                  .id: "Pilih PNG"],
        "io.savedOne":         [.it: "Slide salvata ✓",                               .id: "Slide tersimpan ✓"],
        "io.savedAll":         [.it: "%d slide salvate nella cartella ✓",             .id: "%d slide tersimpan di folder ✓"],
        "io.uploaded":         [.it: "Caricato: %d slide in Revisione ✓",             .id: "Terunggah: %d slide ke Revisi ✓"],
        "io.rerendering":      [.it: "Ri-renderizzo…",                                 .id: "Render ulang…"],
        "io.rerendered":       [.it: "Ri-renderizzato ✓",                             .id: "Render ulang selesai ✓"],
        "io.publishChecking":  [.it: "Verifico (dry-run)…",                          .id: "Memeriksa (dry-run)…"],
        "io.publishChecked":   [.it: "Verifica OK — pronto a pubblicare",            .id: "Periksa OK — siap terbit"],
        "io.publishing":       [.it: "Pubblico su Instagram…",                       .id: "Menerbitkan ke Instagram…"],
        "io.published":        [.it: "Pubblicato su IG",                             .id: "Terbit di IG"],
        "io.nameTitle":        [.it: "Nome del carosello",                            .id: "Nama karusel"],
        "io.nameInfo":         [.it: "Sarà lo slug su disco e in Revisione.",         .id: "Akan jadi slug di disk dan di Revisi."],
        "io.create":          [.it: "Crea",                                          .id: "Buat"],
        "detail.igLink":       [.it: "Link del post Instagram",                         .id: "Tautan postingan Instagram"],
        "detail.confirm":      [.it: "Conferma",                                        .id: "Konfirmasi"],
        "detail.undo":         [.it: "Annulla pubblicazione",                           .id: "Batalkan terbit"],
        "detail.openIG":       [.it: "Apri su Instagram",                              .id: "Buka di Instagram"],
        "detail.critic":       [.it: "Controllo qualità",                              .id: "Pemeriksaan kualitas"],
        "detail.close":        [.it: "Chiudi",                                          .id: "Tutup"],
        // gallery sort + result badges (Task 6)
        "gallery.sort.viral":        [.it: "Più condivisi",   .id: "Paling dibagikan"],
        "gallery.sort.recent":       [.it: "Più recenti",     .id: "Terbaru"],
        "gallery.sort.awaiting":     [.it: "In attesa",       .id: "Menunggu"],
        "gallery.badge.notPublished":[.it: "non pubblicato",  .id: "belum terbit"],
        "gallery.badge.awaiting":    [.it: "in attesa",       .id: "menunggu"],
        // ambient editorial wall (Task 7)
        "ambient.nowRunning":  [.it: "Ora in lavorazione",          .id: "Sedang dibuat"],
        "ambient.awaiting":    [.it: "in attesa di numeri",         .id: "menunggu angka"],
        "ambient.mostShared":  [.it: "il più condiviso",            .id: "paling dibagikan"],
        "ambient.justPublished":[.it: "appena pubblicato",          .id: "baru diterbitkan"],
        "ambient.published":   [.it: "pubblicati",                  .id: "diterbitkan"],
        "ambient.awaitingCount":[.it: "in attesa",                  .id: "menunggu"],
        "ambient.avgShares":   [.it: "condivisioni medie",          .id: "rata-rata dibagikan"],
        "ambient.born":        [.it: "Sta nascendo un carosello",   .id: "Sebuah karosel sedang lahir"],
        "ambient.empty":       [.it: "Nessun carosello da mostrare ancora", .id: "Belum ada karosel untuk ditampilkan"],
        "mode.ambient":        [.it: "Vetrina",                     .id: "Etalase"],
        "mode.work":           [.it: "Lavoro",                      .id: "Kerja"],
        // history panel (Task 8)
        "nav.history":         [.it: "Storico",                    .id: "Riwayat"],
        "nav.history.sub":     [.it: "Run e metriche",             .id: "Run & metrik"],
        "history.title":       [.it: "Storico",                    .id: "Riwayat"],
        "history.runsThisMonth":[.it: "run questo mese",           .id: "run bulan ini"],
        "history.passRate":    [.it: "PASS al primo giro",         .id: "PASS percobaan pertama"],
        "history.avgDuration": [.it: "durata media",               .id: "durasi rata-rata"],
        "history.empty":       [.it: "Nessuna run ancora — lanciane una dallo Studio.",
                                .id: "Belum ada run — mulai satu dari Studio."],
        "history.slides":      [.it: "slide",                      .id: "slide"],
        // external carousel import (PDF / folder / images → normalizer pipeline)
        "import.button":       [.it: "Importa carosello esterno",  .id: "Impor karosel eksternal"],
        "import.title":        [.it: "Importa un carosello esterno", .id: "Impor karosel eksternal"],
        "import.lead":         [.it: "Porta dentro un carosello che hai già lavorato fuori dall'app: un PDF (una pagina = una slide), una cartella di immagini, o più file immagine.",
                                 .id: "Bawa masuk karosel yang sudah dikerjakan di luar app: satu PDF (satu halaman = satu slide), satu folder gambar, atau beberapa file gambar."],
        "import.pick":         [.it: "Scegli PDF, cartella o immagini", .id: "Pilih PDF, folder, atau gambar"],
        "import.pickButton":   [.it: "Scegli i file…",              .id: "Pilih file…"],
        "import.selection.none":    [.it: "Nessun file selezionato", .id: "Belum ada file dipilih"],
        "import.selection.pdf":     [.it: "PDF selezionato: %@",     .id: "PDF dipilih: %@"],
        "import.selection.folder":  [.it: "Cartella selezionata: %@", .id: "Folder dipilih: %@"],
        "import.selection.images":  [.it: "%d immagini selezionate", .id: "%d gambar dipilih"],
        "import.topic.label":       [.it: "Argomento (opzionale)",   .id: "Topik (opsional)"],
        "import.topic.placeholder": [.it: "Es. \"KITAS investor 2026\"", .id: "Cth. \"KITAS investor 2026\""],
        "import.fit.label":         [.it: "Adattamento slide",       .id: "Penyesuaian slide"],
        "import.fit.contain":       [.it: "Contieni",                .id: "Muat semua"],
        "import.fit.contain.desc":  [.it: "L'immagine intera resta visibile; se le proporzioni non combaciano restano bordi.",
                                      .id: "Seluruh gambar tetap terlihat; jika rasio tidak cocok akan ada tepi kosong."],
        "import.fit.cover":         [.it: "Riempi",                  .id: "Penuhi"],
        "import.fit.cover.desc":    [.it: "Riempie tutta la slide, ritagliando i bordi dell'immagine se serve.",
                                      .id: "Mengisi seluruh slide, memotong tepi gambar bila perlu."],
        "import.fit.native":        [.it: "Originale",               .id: "Asli"],
        "import.fit.native.desc":   [.it: "Nessuna modifica alle proporzioni — Instagram può ritagliarle in feed.",
                                      .id: "Tidak ada perubahan rasio — Instagram dapat memotongnya di feed."],
        "import.run":                [.it: "Importa",                .id: "Impor"],
        "import.running":            [.it: "Importazione in corso…", .id: "Sedang mengimpor…"],
        "import.new":                 [.it: "NUOVO",                 .id: "BARU"],
        "import.err.empty":          [.it: "Seleziona almeno un file.", .id: "Pilih setidaknya satu file."],
        "import.err.multiplePDFs":  [.it: "Scegli un solo PDF alla volta.", .id: "Pilih hanya satu PDF."],
        "import.err.multipleFolders":[.it: "Scegli una sola cartella alla volta.", .id: "Pilih hanya satu folder."],
        "import.err.mixedKinds":    [.it: "Scegli UN PDF, UNA cartella, oppure più immagini — non un mix.",
                                      .id: "Pilih SATU PDF, SATU folder, atau beberapa gambar — jangan dicampur."],
        "import.err.unsupportedExt":[.it: "Formato non supportato: .%@", .id: "Format tidak didukung: .%@"],
    ]

    /// step id → localization key
    static func stepKey(_ id: String) -> String { "step.\(id)" }
}

// MARK: - Localized accessors for the pure-Foundation models (kept off the model layer)

extension RunStatus {
    @MainActor func localized(_ lang: LanguageManager) -> String { lang.t("status.\(rawValue)") }
}
extension RunStep.StepState {
    @MainActor func localized(_ lang: LanguageManager) -> String { lang.t("step.\(rawValue)") }
}
extension Carousel {
    /// Localized critic verdict for the badge.
    @MainActor func humanVerdict(_ lang: LanguageManager) -> String {
        guard let key = criticVerdictKey else { return "—" }
        // known keys start with "verdict." → translate; otherwise show the raw value
        return key.hasPrefix("verdict.") ? lang.t(key) : key
    }
}
extension ExternalImport.FitMode {
    /// Localized picker label + one-line explanation for the import sheet.
    @MainActor func label(_ lang: LanguageManager) -> String { lang.t("import.fit.\(rawValue)") }
    @MainActor func explanation(_ lang: LanguageManager) -> String { lang.t("import.fit.\(rawValue).desc") }
}
extension ExternalImport.ClassifyError {
    /// Bilingual message for the sheet's error banner (kept off the pure-Foundation
    /// model layer, same pattern as RunStatus/RunStep.StepState/Carousel above).
    @MainActor func localized(_ lang: LanguageManager) -> String {
        switch self {
        case .empty:                          return lang.t("import.err.empty")
        case .multiplePDFs:                   return lang.t("import.err.multiplePDFs")
        case .multipleFolders:                return lang.t("import.err.multipleFolders")
        case .mixedKinds:                     return lang.t("import.err.mixedKinds")
        case .unsupportedExtension(let ext):  return String(format: lang.t("import.err.unsupportedExt"), ext)
        }
    }
}
