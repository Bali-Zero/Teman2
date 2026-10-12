import SwiftUI

/// A markdown block. Inline emphasis (bold/italic/link) is rendered per-line via the
/// NATIVE `AttributedString(markdown:)` (which handles inline but NOT blocks — spec §9 F3).
/// This vendored block parser handles the structure: headings, bullets, quotes, code, paragraphs.
enum MDBlock: Hashable {
    case heading(level: Int, text: String)
    case paragraph(String)
    case bullet(String)
    case quote(String)
    case code(String)
}

/// Vendored markdown block parser (no SPM dependency — spec constraint). Targets the article
/// corpus shape (H1-H3, bullets, blockquotes, fenced code, paragraphs). Tables fall back to
/// monospaced raw lines (logged via a `code` block) — articles use them sparsely.
enum MarkdownParser {

    /// Strip a leading YAML frontmatter block (`---\n…\n---`).
    static func stripFrontmatter(_ raw: String) -> String {
        guard raw.hasPrefix("---") else { return raw }
        let lines = raw.components(separatedBy: "\n")
        // find the closing --- after line 0
        for i in 1..<lines.count where lines[i].trimmingCharacters(in: .whitespaces) == "---" {
            return lines[(i + 1)...].joined(separator: "\n")
                .trimmingCharacters(in: .whitespacesAndNewlines)
        }
        return raw
    }

    static func blocks(of markdown: String) -> [MDBlock] {
        let body = stripFrontmatter(markdown)
        var blocks: [MDBlock] = []
        var paragraph: [String] = []
        var inFence = false
        var fence: [String] = []
        var tableRows: [String] = []   // consecutive `|…` rows coalesce into ONE code block

        func flushParagraph() {
            let joined = paragraph.joined(separator: " ").trimmingCharacters(in: .whitespaces)
            if joined.isEmpty == false { blocks.append(.paragraph(joined)) }
            paragraph.removeAll()
        }
        func flushTable() {
            if tableRows.isEmpty == false { blocks.append(.code(tableRows.joined(separator: "\n"))); tableRows.removeAll() }
        }

        for rawLine in body.components(separatedBy: "\n") {
            let line = rawLine
            let trimmed = line.trimmingCharacters(in: .whitespaces)

            if trimmed.hasPrefix("```") {
                if inFence { blocks.append(.code(fence.joined(separator: "\n"))); fence.removeAll(); inFence = false }
                else { flushParagraph(); flushTable(); inFence = true }
                continue
            }
            if inFence { fence.append(line); continue }

            // table rows accumulate; any non-`|` line flushes them first
            if trimmed.hasPrefix("|") { flushParagraph(); tableRows.append(trimmed); continue }
            if tableRows.isEmpty == false { flushTable() }

            if trimmed.isEmpty { flushParagraph(); continue }

            if trimmed.hasPrefix("### ") { flushParagraph(); blocks.append(.heading(level: 3, text: String(trimmed.dropFirst(4)))); continue }
            if trimmed.hasPrefix("## ")  { flushParagraph(); blocks.append(.heading(level: 2, text: String(trimmed.dropFirst(3)))); continue }
            if trimmed.hasPrefix("# ")   { flushParagraph(); blocks.append(.heading(level: 1, text: String(trimmed.dropFirst(2)))); continue }
            if trimmed.hasPrefix("- ") || trimmed.hasPrefix("* ") { flushParagraph(); blocks.append(.bullet(String(trimmed.dropFirst(2)))); continue }
            if trimmed.hasPrefix("> ")   { flushParagraph(); blocks.append(.quote(String(trimmed.dropFirst(2)))); continue }

            paragraph.append(trimmed)
        }
        if inFence, fence.isEmpty == false { blocks.append(.code(fence.joined(separator: "\n"))) }
        flushTable()
        flushParagraph()
        return blocks
    }
}

/// Renders parsed markdown blocks with the Bali Zero editorial Theme.
struct MarkdownView: View {
    let markdown: String
    /// When true, bullets render as PLAIN list rows (no card wrapper) — avoids the false-affordance
    /// of card-shaped bullets that look tappable (C8, 2026-06-24). Default keeps the legacy card style.
    var flatBullets: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(Array(MarkdownParser.blocks(of: markdown).enumerated()), id: \.offset) { _, block in
                render(block)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// Inline emphasis via the native parser; falls back to plain text if it can't parse.
    private func inline(_ s: String) -> AttributedString {
        (try? AttributedString(markdown: s, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace)))
            ?? AttributedString(s)
    }

    @ViewBuilder private func render(_ block: MDBlock) -> some View {
        switch block {
        case .heading(let level, let text):
            Text(text)
                // D3b: Dynamic Type — same level→size ternary, routed through Theme.scalable so it
                // resolves to a system text style instead of a frozen point size.
                .font(Theme.scalable(level == 1 ? 26 : level == 2 ? 19 : 15,
                                      weight: level <= 2 ? .bold : .semibold))
                .foregroundStyle(Theme.white)
                .padding(.top, level <= 2 ? 10 : 2)
        case .paragraph(let text):
            Text(inline(text)).font(Theme.scalable(14)).foregroundStyle(Theme.muted).lineSpacing(5)
        case .bullet(let text):
            // discrete surface card-row, .kbli-prose li: bullet at left:12, text at ~28 (Review #4)
            HStack(alignment: .top, spacing: 11) {
                RoundedRectangle(cornerRadius: 2).fill(Theme.accent.opacity(0.6))
                    .frame(width: 5, height: 5).padding(.top, 8)
                Text(inline(text)).font(Theme.scalable(14)).foregroundStyle(Theme.muted).lineSpacing(4)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(.leading, flatBullets ? 2 : 12).padding(.trailing, flatBullets ? 0 : 16)
            .padding(.vertical, flatBullets ? 4 : 10)
            // flat = no card wrapper (C8 false-affordance fix); legacy = discrete surface card-row.
            .background(flatBullets ? nil : RoundedRectangle(cornerRadius: Theme.radiusMd).fill(Theme.inkLift))
        case .quote(let text):
            Text(inline(text)).font(Theme.scalable(14)).italic().foregroundStyle(Theme.faint)
                .padding(.leading, 14).padding(.vertical, 4)
                .overlay(alignment: .leading) { RoundedRectangle(cornerRadius: 2).fill(Theme.accent).frame(width: 3) }
        case .code(let text):
            Text(text).font(Theme.monoFont).foregroundStyle(Theme.muted)
                .padding(12).frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: Theme.radiusMd).fill(Theme.ink))
                .overlay(RoundedRectangle(cornerRadius: Theme.radiusMd).strokeBorder(Theme.hairline, lineWidth: 1))
        }
    }
}
