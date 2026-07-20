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
        // Codex red-team finding B, 2026-07-17: markPublished must NEVER write
        // ig_media_id — extractMediaID's output is a URL SHORTCODE, not the real
        // numeric Graph media id, and the scraper now trusts a present ig_media_id
        // as authoritative (would poison metrics for every app-published post).
        expect(after[0]["ig_media_id"] == nil, "markPublished writes no ig_media_id (finding B)")
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

        // --- addExternalPost — external-post feature (§A, 2026-07-17) ----------------
        func makeExternalEntry(itemID: String, url: String) -> [String: Any] {
            [
                "item_id": itemID,
                "state": "published",
                "instagram_post_url": url,
                "source": "external_manual",
                "published_at": "2026-07-17T09:00:00+00:00",
                "instagram_published_at": "2026-07-17T09:00:00+00:00",
                "topic": "A manual post",
                "topic_slug": "a-manual-post",
                "slide_count": 0,
            ]
        }

        let dir3 = FileManager.default.temporaryDirectory.appendingPathComponent("wr2q-\(UUID().uuidString)")
        try! FileManager.default.createDirectory(at: dir3, withIntermediateDirectories: true)
        let qf3 = dir3.appendingPathComponent("q.json")
        try! Data("[]".utf8).write(to: qf3)

        let entry1 = makeExternalEntry(itemID: "external_2026-07-17T090000_a-manual-post",
                                        url: "https://www.instagram.com/p/ManualOne/")
        let added1 = try! QueueWriter.addExternalPost(queueFile: qf3, entry: entry1)
        expect(added1, "addExternalPost returns true on a fresh append")
        let afterAdd = try! JSONSerialization.jsonObject(with: Data(contentsOf: qf3)) as! [[String: Any]]
        expect(afterAdd.count == 1, "queue now has exactly 1 entry")
        expect((afterAdd[0]["state"] as? String) == "published", "external entry written with state=published")
        expect((afterAdd[0]["source"] as? String) == "external_manual", "external entry written with source=external_manual")

        // duplicate by SAME item_id (different URL) must be refused, no write.
        let dupSameID = makeExternalEntry(itemID: "external_2026-07-17T090000_a-manual-post",
                                           url: "https://www.instagram.com/p/DifferentURL/")
        var threwDupID = false
        do { try QueueWriter.addExternalPost(queueFile: qf3, entry: dupSameID) }
        catch { threwDupID = true }
        expect(threwDupID, "addExternalPost throws on duplicate item_id")
        let afterDupID = try! JSONSerialization.jsonObject(with: Data(contentsOf: qf3)) as! [[String: Any]]
        expect(afterDupID.count == 1, "duplicate item_id attempt does not append (queue still has 1 entry)")

        // duplicate by SAME url (different item_id) must ALSO be refused, no write.
        let dupSameURL = makeExternalEntry(itemID: "external_2026-07-17T091500_retry-post",
                                            url: "https://www.instagram.com/p/ManualOne/")
        var threwDupURL = false
        do { try QueueWriter.addExternalPost(queueFile: qf3, entry: dupSameURL) }
        catch { threwDupURL = true }
        expect(threwDupURL, "addExternalPost throws on duplicate instagram_post_url (different item_id)")
        let afterDupURL = try! JSONSerialization.jsonObject(with: Data(contentsOf: qf3)) as! [[String: Any]]
        expect(afterDupURL.count == 1, "duplicate URL attempt does not append (queue still has 1 entry)")

        // a genuinely different post (different id AND url) must append fine, alongside
        // — and must NEVER disturb the existing entry (scar #9 discipline).
        let entry2 = makeExternalEntry(itemID: "external_2026-07-17T093000_second-post",
                                        url: "https://www.instagram.com/p/ManualTwo/")
        let added2 = try! QueueWriter.addExternalPost(queueFile: qf3, entry: entry2)
        expect(added2, "addExternalPost returns true for a genuinely new entry")
        let afterSecond = try! JSONSerialization.jsonObject(with: Data(contentsOf: qf3)) as! [[String: Any]]
        expect(afterSecond.count == 2, "queue now has 2 entries")
        let firstStillThere = afterSecond.contains { ($0["item_id"] as? String) == "external_2026-07-17T090000_a-manual-post" }
        expect(firstStillThere, "the first entry is untouched by the second append")

        // --- Codex red-team finding D (Swift mirror), 2026-07-17: shortcode-first ----
        // dedup compare. A "?utm_..." query-string variant of the SAME post
        // (ManualOne, already in qf3) must still be caught as a duplicate — exact
        // string compare alone would have missed it and double-enqueued.
        let dupSameShortcodeDifferentQuery = makeExternalEntry(
            itemID: "external_2026-07-17T094000_utm-retry",
            url: "https://www.instagram.com/p/ManualOne/?utm_source=ig")
        var threwDupShortcode = false
        do { try QueueWriter.addExternalPost(queueFile: qf3, entry: dupSameShortcodeDifferentQuery) }
        catch { threwDupShortcode = true }
        expect(threwDupShortcode, "addExternalPost throws on a same-shortcode-different-query duplicate (finding D)")
        let afterShortcodeDup = try! JSONSerialization.jsonObject(with: Data(contentsOf: qf3)) as! [[String: Any]]
        expect(afterShortcodeDup.count == 2, "same-shortcode duplicate attempt does not append (queue still has 2 entries)")

        // INNOCENCE: a genuinely different shortcode must still append fine even
        // though it shares the same URL prefix/domain as an existing entry.
        let entry3 = makeExternalEntry(itemID: "external_2026-07-17T094500_third-post",
                                        url: "https://www.instagram.com/p/ManualThree/")
        let added3 = try! QueueWriter.addExternalPost(queueFile: qf3, entry: entry3)
        expect(added3, "addExternalPost still appends a genuinely different shortcode (innocence, finding D)")

        // --- Codex red-team finding A, 2026-07-17: corrupt/unparseable queue file ----
        // must THROW, never silently degrade to []. `(try? ...) ?? []` on both the
        // read AND the parse meant a transient read error or corrupt/truncated JSON
        // was indistinguishable from "no queue file yet" — the subsequent append
        // would then WRITE OVER THE WHOLE QUEUE with just the new entry. Only a
        // genuine missing file may start from an empty array.
        let dirCorrupt = FileManager.default.temporaryDirectory.appendingPathComponent("wr2q-\(UUID().uuidString)")
        try! FileManager.default.createDirectory(at: dirCorrupt, withIntermediateDirectories: true)
        let qfCorrupt = dirCorrupt.appendingPathComponent("q.json")
        let corruptBytes = "{not valid json at all".data(using: .utf8)!
        try! corruptBytes.write(to: qfCorrupt)
        let entryForCorrupt = makeExternalEntry(itemID: "external_2026-07-17T094500_corrupt-test",
                                                 url: "https://www.instagram.com/p/CorruptTest/")
        var threwOnCorrupt = false
        do { try QueueWriter.addExternalPost(queueFile: qfCorrupt, entry: entryForCorrupt) }
        catch { threwOnCorrupt = true }
        expect(threwOnCorrupt, "addExternalPost throws on a corrupt/unparseable queue file (finding A)")
        let corruptAfter = try! Data(contentsOf: qfCorrupt)
        expect(corruptAfter == corruptBytes, "corrupt queue file is left byte-for-byte untouched, not overwritten")

        // INNOCENCE: a genuinely missing queue file still starts from [] and appends fine.
        let dirMissing = FileManager.default.temporaryDirectory.appendingPathComponent("wr2q-\(UUID().uuidString)")
        try! FileManager.default.createDirectory(at: dirMissing, withIntermediateDirectories: true)
        let qfMissing = dirMissing.appendingPathComponent("q.json")  // never created
        let entryForMissing = makeExternalEntry(itemID: "external_2026-07-17T095000_missing-file-test",
                                                 url: "https://www.instagram.com/p/MissingFileTest/")
        let addedToMissing = try! QueueWriter.addExternalPost(queueFile: qfMissing, entry: entryForMissing)
        expect(addedToMissing, "addExternalPost still succeeds against a genuinely missing queue file (innocence)")

        print("RESULT: \(fails == 0 ? "GREEN" : "RED")")
        exit(fails == 0 ? 0 : 1)
    }
}
