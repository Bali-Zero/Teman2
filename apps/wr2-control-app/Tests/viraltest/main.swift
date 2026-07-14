import Foundation

// Compile: swiftc -parse-as-library Sources/Models.swift Sources/ViralSelector.swift
//          Tests/viraltest/main.swift -o build/viraltest
// (NO AppState.swift — ViralSelector is Foundation-pure, no SwiftUI link needed)

@main
struct ViralTest {
    static func main() {
        func car(_ slug: String, shares: Int?, published: Bool, mod: Date) -> Carousel {
            var c = Carousel(slug: slug, directory: URL(fileURLWithPath: "/tmp/\(slug)"),
                             slidesDir: URL(fileURLWithPath: "/tmp/\(slug)/slides"),
                             slidePNGs: [URL(fileURLWithPath: "/tmp/\(slug)/slides/1.png")],
                             modified: mod, topic: slug, domain: "kbli",
                             criticVerdict: "PASS", slideCount: 1, imagegenFallback: false)
            c.coverURL = c.slidePNGs.first
            c.metrics = EngagementMetrics(shares: shares, likes: nil, comments: nil, saves: nil, reach: nil, impressions: nil)
            c.instagramURL = published ? "https://instagram.com/p/\(slug)" : nil
            return c
        }

        let now = Date(timeIntervalSince1970: 1_780_000_000)
        let day: TimeInterval = 86400
        let list = [
            car("viral-big",          shares: 500, published: true,  mod: now.addingTimeInterval(-10*day)),
            car("viral-small",        shares: 100, published: true,  mod: now.addingTimeInterval(-5*day)),
            car("old-published",      shares: 999, published: true,  mod: now.addingTimeInterval(-300*day)),
            car("unpublished-recent", shares: nil, published: false, mod: now.addingTimeInterval(-1*day)),
        ]

        let viral = ViralSelector.viralCovers(list, now: now, windowDays: 240)

        var fails = 0
        func expect(_ c: Bool, _ m: String) { if c { print("  ✅ \(m)") } else { print("  ❌ \(m)"); fails += 1 } }

        expect(viral.first?.slug == "viral-big",                           "most shares within window first")
        expect(viral.contains { $0.slug == "old-published" } == false,     "outside 240d window excluded")
        expect(viral.contains { $0.slug == "unpublished-recent" } == false, "unpublished excluded from viral")

        // fallback when nothing published-with-metrics
        let none = ViralSelector.viralCovers([car("u", shares: nil, published: false, mod: now)],
                                             now: now, windowDays: 240)
        expect(none.isEmpty, "no viral candidates → empty (caller does recent-PASS fallback)")

        print("RESULT: \(fails == 0 ? "GREEN" : "RED")")
        exit(fails == 0 ? 0 : 1)
    }
}
