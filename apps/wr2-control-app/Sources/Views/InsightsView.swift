import SwiftUI
import Foundation

/// Insights — surfaces the WR2 analyst's REAL reasoning (the weekly `ig-metrics-analyst` findings)
/// in human-readable form. Reads the newest `_proposed-amendments/*-ig-insights.md` (the file the
/// analyst writes after correlating engagement vs carousel attributes), skipping the
/// "insufficient-data" stubs. Pure brand-craft — no client PII.
struct InsightsView: View {
    let lang: LanguageManager
    @State private var blocks: [MDBlock] = []
    @State private var sourceName: String = ""
    @State private var loaded = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                header
                if blocks.isEmpty {
                    emptyState
                } else {
                    ForEach(Array(blocks.enumerated()), id: \.offset) { _, b in
                        b.view(lang: lang)
                    }
                }
            }
            .padding(28)
            .frame(maxWidth: 920, alignment: .leading)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .task { if !loaded { reload(); loaded = true } }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(lang.t("nav.insights")).font(Theme.titleFont).foregroundStyle(Theme.white)
            HStack(spacing: 8) {
                FactRule(width: 28)
                Text(sourceName.isEmpty ? lang.t("insights.sub") : sourceName)
                    .font(.system(size: 11)).foregroundStyle(Theme.muted)
                Spacer()
                Button { reload() } label: {
                    Label(lang.t("gallery.refresh"), systemImage: "arrow.clockwise").font(.system(size: 12))
                }.buttonStyle(.bordered).tint(Theme.muted)
            }
        }
    }

    private var emptyState: some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: "lightbulb").font(.system(size: 32)).foregroundStyle(Theme.muted.opacity(0.5))
            Text(lang.t("insights.empty")).font(Theme.bodyFont).foregroundStyle(Theme.muted)
            Text(lang.t("insights.empty.sub")).font(.system(size: 11)).foregroundStyle(Theme.muted.opacity(0.7))
        }.padding(.top, 40)
    }

    // MARK: - load + parse

    private func reload() {
        guard let url = InsightsSource.latestFile() else { blocks = []; sourceName = ""; return }
        sourceName = url.lastPathComponent
        let text = (try? String(contentsOf: url, encoding: .utf8)) ?? ""
        blocks = MDParser.parse(text)
    }
}

// MARK: - source resolution

enum InsightsSource {
    /// Newest `*-ig-insights.md` (excluding the insufficient-data stubs) under the brand skill dir.
    static func latestFile() -> URL? {
        let home = FileManager.default.homeDirectoryForCurrentUser
        let dir = home.appendingPathComponent(
            ".claude/skills/bali-zero-brand/_proposed-amendments", isDirectory: true)
        guard let files = try? FileManager.default.contentsOfDirectory(
            at: dir, includingPropertiesForKeys: nil) else { return nil }
        let candidates = files.filter {
            $0.lastPathComponent.hasSuffix("-ig-insights.md")
            && $0.lastPathComponent.contains("insufficient-data") == false
        }.sorted { $0.lastPathComponent < $1.lastPathComponent }
        return candidates.last
    }
}

// MARK: - markdown-lite blocks

/// A small block model — enough for the analyst's report shape (headings, paragraphs,
/// bullets, tables, blockquotes). Not a full markdown engine.
enum MDBlock {
    case h1(String), h2(String), h3(String)
    case para(String)
    case plain(String)          // the "In parole semplici:" human takeaway — highlighted
    case bullet([String])
    case quote([String])
    case table(header: [String], rows: [[String]])
    case techDetails([MDBlock]) // collapsed-by-default technical evidence
    case rule

    @ViewBuilder
    func view(lang: LanguageManager) -> some View {
        switch self {
        case .h1(let s):
            Text(inline(s)).font(.system(size: 21, weight: .bold)).foregroundStyle(Theme.white)
                .padding(.top, 6)
        case .h2(let s):
            HStack(spacing: 8) { FactRule(width: 18)
                Text(inline(s)).font(.system(size: 17, weight: .bold)).foregroundStyle(Theme.yellow) }
                .padding(.top, 10)
        case .h3(let s):
            Text(inline(s)).font(.system(size: 15, weight: .bold)).foregroundStyle(Theme.white)
                .padding(.top, 8)
        case .para(let s):
            Text(inline(s)).font(.system(size: 13)).foregroundStyle(Theme.muted)
                .fixedSize(horizontal: false, vertical: true)
        case .plain(let s):
            // the human takeaway — bigger, white, on a soft card so it reads as the headline
            Text(inline(s)).font(.system(size: 14.5)).foregroundStyle(Theme.white)
                .lineSpacing(3).fixedSize(horizontal: false, vertical: true)
                .padding(14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 12).fill(Theme.inkLift))
                .overlay(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2).fill(Theme.yellow).frame(width: 3).padding(.vertical, 8)
                }
        case .techDetails(let inner):
            TechDisclosure(blocks: inner, lang: lang)
        case .bullet(let items):
            VStack(alignment: .leading, spacing: 5) {
                ForEach(Array(items.enumerated()), id: \.offset) { _, it in
                    HStack(alignment: .top, spacing: 8) {
                        Text("•").foregroundStyle(Theme.yellow).font(.system(size: 13, weight: .bold))
                        Text(inline(it)).font(.system(size: 13)).foregroundStyle(Theme.muted)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
        case .quote(let lines):
            VStack(alignment: .leading, spacing: 4) {
                ForEach(Array(lines.enumerated()), id: \.offset) { _, l in
                    Text(inline(l)).font(.system(size: 12.5, design: .serif))
                        .foregroundStyle(Theme.white)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .padding(12)
            .background(RoundedRectangle(cornerRadius: 10).fill(Theme.inkLift))
            .overlay(alignment: .leading) {
                RoundedRectangle(cornerRadius: 2).fill(Theme.yellow).frame(width: 3).padding(.vertical, 6)
            }
        case .table(let header, let rows):
            VStack(alignment: .leading, spacing: 0) {
                tableRow(header, bold: true)
                ForEach(Array(rows.enumerated()), id: \.offset) { _, r in
                    Divider().overlay(Theme.hairline)
                    tableRow(r, bold: false)
                }
            }
            .padding(10)
            .background(RoundedRectangle(cornerRadius: 10).fill(Theme.ink))
            .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(Theme.hairline))
        case .rule:
            Divider().overlay(Theme.hairline).padding(.vertical, 2)
        }
    }

    private func tableRow(_ cells: [String], bold: Bool) -> some View {
        HStack(alignment: .top, spacing: 10) {
            ForEach(Array(cells.enumerated()), id: \.offset) { _, c in
                Text(inline(c))
                    .font(.system(size: 11.5, weight: bold ? .bold : .regular))
                    .foregroundStyle(bold ? Theme.yellow : Theme.muted)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(.vertical, 5)
    }

    /// Inline markdown (bold/italic/code) via the native AttributedString markdown parser.
    private func inline(_ s: String) -> AttributedString {
        (try? AttributedString(markdown: s,
            options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace)))
            ?? AttributedString(s)
    }
}

// MARK: - collapsible technical evidence

/// Hides the statistical detail behind a tap. Human takeaway stays visible; the numbers
/// (N=, Save/Like, baselines) are one click away for Antonello's merge decisions.
struct TechDisclosure: View {
    let blocks: [MDBlock]
    let lang: LanguageManager
    @State private var open = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Button { withAnimation(.easeInOut(duration: 0.2)) { open.toggle() } } label: {
                HStack(spacing: 6) {
                    Image(systemName: open ? "chevron.down" : "chevron.right").font(.system(size: 10, weight: .bold))
                    Text(lang.t(open ? "insights.tech.hide" : "insights.tech.show"))
                        .font(.system(size: 11, weight: .semibold))
                }
                .foregroundStyle(Theme.muted)
                .padding(.horizontal, 10).padding(.vertical, 6)
                .background(Capsule().fill(Theme.hairline))
            }.buttonStyle(.plain)

            if open {
                VStack(alignment: .leading, spacing: 10) {
                    ForEach(Array(blocks.enumerated()), id: \.offset) { _, b in
                        b.view(lang: lang)
                    }
                }
                .padding(14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 10).fill(Theme.ink))
                .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(Theme.hairline))
            }
        }
    }
}

// MARK: - parser

enum MDParser {
    static func parse(_ text: String) -> [MDBlock] {
        var blocks: [MDBlock] = []
        let lines = text.components(separatedBy: "\n")
        var i = 0
        var paraBuf: [String] = []
        var bulletBuf: [String] = []
        var quoteBuf: [String] = []

        func flushPara() {
            if !paraBuf.isEmpty { blocks.append(.para(paraBuf.joined(separator: " "))); paraBuf = [] }
        }
        func flushBullets() {
            if !bulletBuf.isEmpty { blocks.append(.bullet(bulletBuf)); bulletBuf = [] }
        }
        func flushQuote() {
            if !quoteBuf.isEmpty { blocks.append(.quote(quoteBuf)); quoteBuf = [] }
        }
        func flushAll() { flushPara(); flushBullets(); flushQuote() }

        while i < lines.count {
            let raw = lines[i]
            let line = raw.trimmingCharacters(in: .whitespaces)

            if line.isEmpty { flushAll(); i += 1; continue }

            // technical-evidence block: everything from `<details tech>` up to the next `---`
            // (or `</details>`) is collapsed behind a disclosure. Parsed recursively.
            if line.hasPrefix("<details") {
                flushAll()
                i += 1
                var inner: [String] = []
                while i < lines.count {
                    let t = lines[i].trimmingCharacters(in: .whitespaces)
                    if t == "---" || t.hasPrefix("</details") { break }
                    inner.append(lines[i]); i += 1
                }
                blocks.append(.techDetails(parse(inner.joined(separator: "\n"))))
                continue
            }

            // human takeaway: a line that starts with "**In parole semplici:**" (or English)
            if line.hasPrefix("**In parole semplici:**") || line.hasPrefix("**In plain terms:**") {
                flushAll()
                blocks.append(.plain(line)); i += 1; continue
            }

            // table: a line starting with | followed by a |---| separator
            if line.hasPrefix("|"), i + 1 < lines.count,
               lines[i + 1].trimmingCharacters(in: .whitespaces).hasPrefix("|"),
               lines[i + 1].contains("-") {
                flushAll()
                let header = cells(line)
                var rows: [[String]] = []
                i += 2  // skip header + separator
                while i < lines.count {
                    let t = lines[i].trimmingCharacters(in: .whitespaces)
                    if t.hasPrefix("|") == false { break }
                    rows.append(cells(t)); i += 1
                }
                blocks.append(.table(header: header, rows: rows))
                continue
            }

            if line.hasPrefix("### ") { flushAll(); blocks.append(.h3(String(line.dropFirst(4)))); i += 1; continue }
            if line.hasPrefix("## ")  { flushAll(); blocks.append(.h2(String(line.dropFirst(3)))); i += 1; continue }
            if line.hasPrefix("# ")   { flushAll(); blocks.append(.h1(String(line.dropFirst(2)))); i += 1; continue }
            if line == "---"          { flushAll(); blocks.append(.rule); i += 1; continue }
            if line.hasPrefix("> ")   { flushPara(); flushBullets(); quoteBuf.append(String(line.dropFirst(2))); i += 1; continue }
            if line == ">"            { flushPara(); flushBullets(); quoteBuf.append(""); i += 1; continue }
            if line.hasPrefix("- ") || line.hasPrefix("* ") {
                flushPara(); flushQuote(); bulletBuf.append(String(line.dropFirst(2))); i += 1; continue
            }

            // plain paragraph line
            flushBullets(); flushQuote()
            paraBuf.append(line)
            i += 1
        }
        flushAll()
        return blocks
    }

    private static func cells(_ row: String) -> [String] {
        var s = row
        if s.hasPrefix("|") { s.removeFirst() }
        if s.hasSuffix("|") { s.removeLast() }
        return s.components(separatedBy: "|").map { $0.trimmingCharacters(in: .whitespaces) }
    }
}
