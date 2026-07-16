import Foundation

@main struct QueueWriterTest {
    static func main() {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("wr2q-\(UUID().uuidString)")
        try! FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let qf = dir.appendingPathComponent("q.json")
        let original = """
[{"id":"a","topic_slug":"kbli-cafe","state":"drafted","UNKNOWN_FUTURE":"keepme","engagement_metrics":{"likes":null}}]
""".data(using: .utf8)!
        try! original.write(to: qf)

        var fails = 0
        func expect(_ c: Bool, _ m: String) { if c { print("  ✅ \(m)") } else { print("  ❌ \(m)"); fails += 1 } }

        // media id extraction
        expect(QueueWriter.extractMediaID(from: "https://www.instagram.com/p/ABC123/") == "ABC123", "media id from /p/ url")
        expect(QueueWriter.extractMediaID(from: "ABC123") == "ABC123", "bare id passes through")

        // mark published
        try! QueueWriter.markPublished(queueFile: qf, slug: "kbli-cafe", igURL: "https://instagram.com/p/ABC123/", publishedAt: "2026-06-22")
        let after = try! JSONSerialization.jsonObject(with: Data(contentsOf: qf)) as! [[String: Any]]
        expect((after[0]["state"] as? String) == "published", "state advanced to published")
        expect((after[0]["instagram_post_url"] as? String) == "https://instagram.com/p/ABC123/", "ig url written")
        expect((after[0]["ig_media_id"] as? String) == "ABC123", "media id written")
        expect((after[0]["instagram_published_at"] as? String) == "2026-06-22", "published_at written")
        expect((after[0]["UNKNOWN_FUTURE"] as? String) == "keepme", "unknown field preserved (scar #9)")

        // undo
        try! QueueWriter.undoPublished(queueFile: qf, slug: "kbli-cafe")
        let undone = try! JSONSerialization.jsonObject(with: Data(contentsOf: qf)) as! [[String: Any]]
        expect((undone[0]["state"] as? String) == "drafted", "undo restores prior state")
        expect(undone[0]["ig_media_id"] == nil, "undo clears media id (sampler stops measuring)")
        expect((undone[0]["UNKNOWN_FUTURE"] as? String) == "keepme", "unknown field still preserved after undo")

        // undo must clear its own bookkeeping field (else it leaks into production data)
        expect(undone[0]["state_before_publish"] == nil, "undo clears state_before_publish bookkeeping")
        // slug not found must throw, not silently succeed
        var threw = false
        do { try QueueWriter.markPublished(queueFile: qf, slug: "does-not-exist", igURL: "x", publishedAt: "2026-06-22") }
        catch { threw = true }
        expect(threw, "markPublished throws on unknown slug")

        // --- D2 innocence test (audit §6/§5a, A3 edit spec) -------------------------
        // enqueueDrafted must NEVER fabricate a critic verdict — no critic runs on
        // this path, including raw PNG imports. Guards against a future edit
        // reintroducing the literal "pass" (guilt-detection via substring scan on the
        // serialized entry, not just dict equality — scar-family #3 discipline).
        let dir2 = FileManager.default.temporaryDirectory.appendingPathComponent("wr2q-\(UUID().uuidString)")
        try! FileManager.default.createDirectory(at: dir2, withIntermediateDirectories: true)
        let qf2 = dir2.appendingPathComponent("q.json")
        try! Data("[]".utf8).write(to: qf2)
        _ = try! QueueWriter.enqueueDrafted(queueFile: qf2, slug: "honest-verdict-test", slideCount: 9,
                                            isoTimestamp: "2026-07-14T00:00:00Z")
        let enqueuedRaw = try! String(contentsOf: qf2, encoding: .utf8)
        // whitespace-insensitive: JSONSerialization pretty-print spacing is an
        // implementation detail, not part of the contract under test.
        let enqueued = enqueuedRaw.filter { !$0.isWhitespace }
        expect(enqueued.contains("\"critic_overall_verdict\":\"pass\"") == false,
               "enqueueDrafted never fabricates a \"pass\" critic verdict")
        expect(enqueued.contains("\"critic_overall_verdict\":\"not_run\""),
               "enqueueDrafted honestly records \"not_run\" (no critic ever ran on this path)")

        // --- Publish-eligibility fail-closed gate (2026-07-16 cross-finding with the -
        // Python A3 daily-reconciler): markPublished must refuse a not-ready state, and
        // must leave the queue entry byte-for-byte unchanged when it does (no partial
        // mutation snuck in before the guard fires).
        func makeQueue(state: String, extra: String = "") -> URL {
            let d = FileManager.default.temporaryDirectory.appendingPathComponent("wr2q-\(UUID().uuidString)")
            try! FileManager.default.createDirectory(at: d, withIntermediateDirectories: true)
            let f = d.appendingPathComponent("q.json")
            try! Data("""
            [{"id":"a","topic_slug":"gate-test","state":"\(state)"\(extra)}]
            """.utf8).write(to: f)
            return f
        }

        // COLPEVOLEZZA — render_incomplete (the A3 reconciler's queue-level state for a
        // declared/disk mismatch it could not explain as stale metadata) must refuse.
        let qfIncomplete = makeQueue(state: "render_incomplete")
        var threwIncomplete = false
        do { try QueueWriter.markPublished(queueFile: qfIncomplete, slug: "gate-test", igURL: "https://instagram.com/p/X/", publishedAt: "2026-07-16") }
        catch { threwIncomplete = true }
        expect(threwIncomplete, "markPublished refuses a render_incomplete entry")
        let afterIncomplete = try! JSONSerialization.jsonObject(with: Data(contentsOf: qfIncomplete)) as! [[String: Any]]
        expect((afterIncomplete[0]["state"] as? String) == "render_incomplete",
               "refused publish leaves state untouched (no partial mutation)")
        expect(afterIncomplete[0]["instagram_post_url"] == nil,
               "refused publish never writes instagram_post_url")

        // COLPEVOLEZZA (generalization — not a hardcoded string check on just one
        // literal) — any other not-ready state (in-flight render, quality bounce,
        // rejection) must ALSO refuse, since the gate classifies via CarouselPhase, not
        // a narrow allow-list of one string.
        for badState in ["rendering", "soft_fail", "render_failed", "rejected", "missed"] {
            let qf3 = makeQueue(state: badState)
            var threw3 = false
            do { try QueueWriter.markPublished(queueFile: qf3, slug: "gate-test", igURL: "https://instagram.com/p/X/", publishedAt: "2026-07-16") }
            catch { threw3 = true }
            expect(threw3, "markPublished refuses state \"\(badState)\"")
        }

        // INNOCENZA — genuinely ready states must still publish. "drafted" is already
        // exercised as the baseline case at the top of this file; here we additionally
        // prove the fix doesn't over-restrict the OTHER waitlist-band states.
        for goodState in ["drafted", "rendered", "approved", "applied_ready_for_damar"] {
            let qf4 = makeQueue(state: goodState)
            do {
                try QueueWriter.markPublished(queueFile: qf4, slug: "gate-test", igURL: "https://instagram.com/p/X/", publishedAt: "2026-07-16")
                let after4 = try! JSONSerialization.jsonObject(with: Data(contentsOf: qf4)) as! [[String: Any]]
                expect((after4[0]["state"] as? String) == "published",
                       "markPublished still succeeds from state \"\(goodState)\" (innocence)")
            } catch {
                expect(false, "markPublished should NOT refuse state \"\(goodState)\": \(error)")
            }
        }

        // INNOCENZA — a legacy-schema row with NO `state` field at all, only a
        // critic_overall_verdict of "pass" (CarouselPhase.of treats bare "pass" as
        // waitlist-equivalent), must still be publishable — the state-first fallback
        // to criticVerdict must not regress legacy rows that never had a state field.
        let dirLegacy = FileManager.default.temporaryDirectory.appendingPathComponent("wr2q-\(UUID().uuidString)")
        try! FileManager.default.createDirectory(at: dirLegacy, withIntermediateDirectories: true)
        let qfLegacy = dirLegacy.appendingPathComponent("q.json")
        try! Data("""
        [{"id":"a","topic_slug":"gate-test","critic_overall_verdict":"pass"}]
        """.utf8).write(to: qfLegacy)
        do {
            try QueueWriter.markPublished(queueFile: qfLegacy, slug: "gate-test", igURL: "https://instagram.com/p/X/", publishedAt: "2026-07-16")
            let afterLegacy = try! JSONSerialization.jsonObject(with: Data(contentsOf: qfLegacy)) as! [[String: Any]]
            expect((afterLegacy[0]["state"] as? String) == "published",
                   "legacy row with no state field, verdict \"pass\", still publishes (innocence)")
        } catch {
            expect(false, "legacy verdict-only \"pass\" row should NOT be refused: \(error)")
        }

        print("RESULT: \(fails == 0 ? "GREEN" : "RED")")
        exit(fails == 0 ? 0 : 1)
    }
}
