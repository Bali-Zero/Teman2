import Foundation

func ck(_ c: Bool, _ m: String) { if c { print("  ✅ \(m)") } else { print("  ❌ FAIL: \(m)"); exit(1) } }

let resDir = ProcessInfo.processInfo.environment["KBLI_RES"]
    ?? (FileManager.default.currentDirectoryPath + "/Resources")

print("MediaLibrary tests:")
let lib = MediaLibrary(resourcesPath: resDir)
ck(lib.articles.count == 20, "20 articles (got \(lib.articles.count))")
ck(lib.chapters.count == 13, "13 chapters (got \(lib.chapters.count))")
ck(lib.books.count == 2, "2 PDF books (got \(lib.books.count))")
ck(lib.books.contains { $0.lang == .en } && lib.books.contains { $0.lang == .id }, "books include EN and ID")
ck(lib.articles.first(where: { $0.title.isEmpty == false }) != nil, "articles have titles")

print("Markdown block parser tests:")
let blocks = MarkdownParser.blocks(of: """
# Title
## Section Two

A paragraph here.

- first bullet
- second bullet

> a quote
""")
let headings = blocks.filter { if case .heading = $0 { return true }; return false }
let bullets  = blocks.filter { if case .bullet = $0 { return true }; return false }
let quotes   = blocks.filter { if case .quote = $0 { return true }; return false }
let paras    = blocks.filter { if case .paragraph = $0 { return true }; return false }
ck(headings.count == 2, "2 headings (got \(headings.count))")
ck(bullets.count == 2, "2 bullets (got \(bullets.count))")
ck(quotes.count == 1, "1 quote (got \(quotes.count))")
ck(paras.count == 1, "1 paragraph (got \(paras.count))")

// frontmatter is stripped (articles start with --- ... ---)
let fm = MarkdownParser.stripFrontmatter("---\ndate: 2026\n---\n# Real Title\nbody")
ck(fm.hasPrefix("# Real Title"), "frontmatter stripped (got prefix '\(fm.prefix(15))')")

let tbl = MarkdownParser.blocks(of: "| a | b |\n| 1 | 2 |\n| 3 | 4 |")
let cb = tbl.filter { if case .code = $0 { return true }; return false }
ck(cb.count == 1, "3 table rows -> 1 code block")

print("ALL MEDIA TESTS PASSED")
