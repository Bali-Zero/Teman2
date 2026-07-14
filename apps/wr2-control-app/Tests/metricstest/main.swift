import Foundation

@main
struct MetricsTest {
    static func main() {
        let json = """
[{"id":"x","topic_slug":"kbli-cafe","carousel_path":"/Users/nuzantara/.../carousel/kbli-cafe",
  "instagram_post_url":"https://instagram.com/p/ABC","instagram_published_at":"2026-06-10",
  "engagement_metrics":{"likes":1247,"comments":38,"saves":340,"reach":18200,"shares":312},
  "state":"published"},
 {"item_id":"y","topic":"spt","engagement_metrics":{"likes":null,"comments":null,"saves":null,"reach":null}}]
""".data(using: .utf8)!
        let items = try! JSONDecoder().decode([ReviewItem].self, from: json)
        var fails = 0
        func expect(_ c: Bool, _ m: String) { if c { print("  ✅ \(m)") } else { print("  ❌ \(m)"); fails += 1 } }
        expect(items.count == 2, "both schemas decode")
        let m = items[0].engagement_metrics
        expect(m?.shares == 312, "shares parsed (the king metric)")
        expect(m?.likes == 1247, "likes parsed")
        expect(items[0].instagram_post_url == "https://instagram.com/p/ABC", "ig url parsed")
        expect(items[1].engagement_metrics?.isEmpty == true, "all-null metrics → isEmpty true")
        expect(items[0].engagement_metrics?.isEmpty == false, "real metrics → isEmpty false")
        print("RESULT: \(fails == 0 ? "GREEN" : "RED")")
        exit(fails == 0 ? 0 : 1)
    }
}
