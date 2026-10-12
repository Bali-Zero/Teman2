import PDFKit
import SwiftUI

/// What the user picked in the media content column.
enum MediaSelection: Hashable {
    case article(MediaItem)
    case chapter(MediaItem)
    case book(PDFItem)
}

/// Media content column: sections for articles, book chapters, and the PDF book.
struct MediaView: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    private let lib = MediaLibrary()

    var body: some View {
        List {
            mediaSection(lang.t("media.book")) {
                ForEach(lib.books) { b in
                    rowLabel(b.label, "book.closed", selected: state.mediaSelection == .book(b))
                        .onTapGesture { state.mediaSelection = .book(b) }
                }
            }
            // BKPM ships the book only — Resources/articles/ is excluded from that bundle at
            // build time, so `lib.articles` is empty and this section would otherwise render as
            // a bare header with no rows. Gate on the data, not on AppVariant directly: INTERNAL
            // stays correct even if someone bundles a partial articles/ folder by hand.
            if !lib.articles.isEmpty {
                mediaSection(lang.t("media.articles")) {
                    ForEach(lib.articles) { a in
                        rowLabel(a.title, "doc.text", selected: state.mediaSelection == .article(a))
                            .onTapGesture { state.mediaSelection = .article(a) }
                    }
                }
            }
            mediaSection(lang.t("media.chapters")) {
                ForEach(lib.chapters) { c in
                    rowLabel(c.title, "book.pages", selected: state.mediaSelection == .chapter(c))
                        .onTapGesture { state.mediaSelection = .chapter(c) }
                }
            }
        }
        .listStyle(.plain)
        .scrollContentBackground(.hidden)
        .background(Theme.antracite)
    }

    @ViewBuilder private func mediaSection<C: View>(_ title: String, @ViewBuilder _ rows: () -> C) -> some View {
        Section {
            rows()
        } header: {
            Text(title.uppercased())
                .font(Theme.scalable(10, weight: .bold)).tracking(1.2).foregroundStyle(Theme.faint)
                .padding(.top, 6)
        }
        .listRowBackground(Color.clear)
        .listRowSeparator(.hidden)
    }

    private func rowLabel(_ title: String, _ icon: String, selected: Bool) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .foregroundStyle(selected ? Theme.accent : Theme.faint)
                .font(Theme.scalable(12)).frame(width: 18)
            Text(title).font(Theme.scalable(12, weight: selected ? .semibold : .regular))
                .foregroundStyle(selected ? Theme.white : Theme.muted).lineLimit(2)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 10).padding(.vertical, 8)
        .background(
            RoundedRectangle(cornerRadius: Theme.radiusMd, style: .continuous)
                .fill(selected ? Theme.accent.opacity(0.12) : Color.clear)
        )
        .contentShape(Rectangle())
    }
}

/// Media detail column — renders the selected article/chapter (markdown) or PDF book.
struct MediaDetailHost: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager

    var body: some View {
        switch state.mediaSelection {
        case .article(let m), .chapter(let m):
            ScrollView {
                MarkdownView(markdown: (try? String(contentsOf: m.url, encoding: .utf8)) ?? "")
                    .padding(24).frame(maxWidth: 760, alignment: .leading)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .background(Theme.antracite)
        case .book(let b):
            PDFViewer(url: b.url)
        case nil:
            EmptyDetail(text: lang.t("search.pick"), kind: .mediaEmpty)
        }
    }
}

/// PDFKit wrapper. Loads the document on a background thread (49MB PDFs would freeze the main
/// thread — spec §9 trap) and releases it on disappear so two books never sit in RAM together.
struct PDFViewer: NSViewRepresentable {
    let url: URL

    func makeNSView(context: Context) -> PDFView {
        let v = PDFView()
        v.autoScales = true
        v.displayMode = .singlePageContinuous
        loadAsync(into: v)
        return v
    }

    func updateNSView(_ v: PDFView, context: Context) {
        if v.document?.documentURL != url { loadAsync(into: v) }
    }

    static func dismantleNSView(_ v: PDFView, coordinator: ()) {
        v.document = nil   // free the ~49MB document when the view goes away
    }

    private func loadAsync(into v: PDFView) {
        let u = url
        DispatchQueue.global(qos: .userInitiated).async {
            let doc = PDFDocument(url: u)
            DispatchQueue.main.async { v.document = doc }
        }
    }
}
