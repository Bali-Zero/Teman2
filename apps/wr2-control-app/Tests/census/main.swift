import Foundation

// A2 GATE — REAL-DATA CENSUS (mandatory innocence proof, 2026-07-16 Codex red-team round)
//
// Runs the FIXED, production WarRoom.scanCarousels() read-only against the REAL local
// war-room output (no root/queue override — same defaults AppState uses) and independently
// recomputes, for every physical directory the gate did NOT list, WHY it was excluded — by
// calling the same public WarRoom resolvers (declaredSlideCount/slidePNGs), never by parsing
// stderr log lines. This never mutates anything: FileManager reads only, no writes.
//
// Categories reported, each with the hidden dirs BY NAME:
//   listed              — carousels the gallery would actually show
//   hidden-incomplete    — real PNGs exist but declared != disk (or slides/ empty/unreadable)
//   hidden-undeclarable  — no declaration source at all (or ambiguous same-tier queue rows)
//   published-exempt     — listed carousels kept ONLY because they're genuinely published
//                          (both on-disk exempted dirs and queue-only virtual entries)

let fm = FileManager.default
let queue = WarRoom.readQueue()
let croot = WarRoom.carouselRoot()

let listed = WarRoom.scanCarousels(queue: queue)
let listedSlugs = Set(listed.map { $0.slug })

// Every physical (non-archived) directory on disk — the SAME filter scanCarousels applies
// (skip dot-hidden entries and any `_`-prefixed archive dir).
let physical: [String] = (try? fm.contentsOfDirectory(
    at: croot, includingPropertiesForKeys: [.isDirectoryKey], options: [.skipsHiddenFiles]))?
    .filter { (try? $0.resourceValues(forKeys: [.isDirectoryKey]))?.isDirectory ?? false }
    .map { $0.lastPathComponent }
    .filter { $0.hasPrefix("_") == false } ?? []

print("═══════════════════════════════════════════════════════════════")
print("A2 GATE — REAL-DATA CENSUS")
print("carousel root: \(croot.path)")
print("queue file:    \(WarRoom.queueFile().path)")
print("run at:        \(Date())")
print("═══════════════════════════════════════════════════════════════")
print("physical directories (non-archived): \(physical.count)")
print("queue items:                          \(queue.count)")
print("")

var hiddenIncomplete: [(slug: String, reason: String)] = []
var hiddenUndeclarable: [(slug: String, reason: String)] = []
var publishedExemptPhysical: [String] = []

for slug in physical {
    let dir = croot.appendingPathComponent(slug, isDirectory: true)
    let slidesDir = dir.appendingPathComponent("slides", isDirectory: true)
    let pngs = WarRoom.slidePNGs(in: slidesDir)

    if listedSlugs.contains(slug) {
        if let c = listed.first(where: { $0.slug == slug }), c.isPublished {
            publishedExemptPhysical.append(slug)
        }
        continue
    }

    // Not listed — independently recompute WHY, via the exact same public resolvers
    // the gate itself calls (never trusting a remembered/logged reason).
    if pngs.isEmpty {
        hiddenIncomplete.append((slug, "empty or unreadable slides/ dir"))
        continue
    }
    let declared = WarRoom.declaredSlideCount(in: dir, slug: slug, queue: queue)
    if let d = declared {
        hiddenIncomplete.append((slug, "disk=\(pngs.count) declared=\(d)"))
    } else {
        hiddenUndeclarable.append((slug, "no slides.json/manifest.json/queue slide_count (or ambiguous same-tier queue rows)"))
    }
}

// Queue-only "virtual" published carousels the second pass materializes (no physical dir
// at all) — verified by an independent, direct disk-existence check on the Carousel's own
// `directory` field, not by any internal bookkeeping flag (scar #9 discipline: verify by
// content/reality, never by a proxy that could itself be wrong).
let virtualPublished = listed.filter { fm.fileExists(atPath: $0.directory.path) == false }

let listedPhysicalCount = listed.count - virtualPublished.count

print("LISTED (total the gallery shows): \(listed.count)")
print("  of which physical on-disk:       \(listedPhysicalCount)")
print("  of which queue-only virtual:      \(virtualPublished.count)")
print("")

print("HIDDEN — incomplete (\(hiddenIncomplete.count)):")
for (s, r) in hiddenIncomplete.sorted(by: { $0.slug < $1.slug }) { print("   - \(s)   [\(r)]") }
print("")

print("HIDDEN — undeclarable (\(hiddenUndeclarable.count)):")
for (s, r) in hiddenUndeclarable.sorted(by: { $0.slug < $1.slug }) { print("   - \(s)   [\(r)]") }
print("")

print("PUBLISHED-EXEMPT — physical dir kept despite incompleteness (\(publishedExemptPhysical.count)):")
for s in publishedExemptPhysical.sorted() { print("   - \(s)") }
print("")

print("PUBLISHED-EXEMPT — virtual, queue-only, no physical dir at all (\(virtualPublished.count)):")
for c in virtualPublished.sorted(by: { $0.slug < $1.slug }) { print("   - \(c.slug)") }
print("")

// Sanity identity: every physical dir is in EXACTLY one bucket — listed (physical) XOR
// hidden-incomplete XOR hidden-undeclarable. If this doesn't add up, the census itself
// has a bug (double-counted or dropped a dir) and its other numbers can't be trusted.
let accounted = listedPhysicalCount + hiddenIncomplete.count + hiddenUndeclarable.count
print("═══════════════════════════════════════════════════════════════")
print("SANITY: physical(\(physical.count)) == listed-physical + hidden-incomplete + hidden-undeclarable (\(accounted))? \(accounted == physical.count ? "OK" : "MISMATCH — census bug, do not trust the above")")
print("═══════════════════════════════════════════════════════════════")

exit(accounted == physical.count ? 0 : 1)
