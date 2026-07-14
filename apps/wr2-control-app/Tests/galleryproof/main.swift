import Foundation

// Gallery proof: run the EXACT production WarRoom layer the GalleryView uses, against the
// live war-room dir, and dump what the app would show. Proves the app sees the real,
// just-produced carousel.

let queue = WarRoom.readQueue()
let carousels = WarRoom.scanCarousels(queue: queue)

print("APP GALLERY VIEW (production WarRoom layer, live disk):")
print("  carousels visible: \(carousels.count)")
print("  queue items: \(queue.count)")
print("")

// find the café carousel produced by the live run
if let cafe = carousels.first(where: { $0.slug == "kbli-2025-small-cafe-bali" }) {
    print("✅ NEW CAROUSEL VISIBLE IN GALLERY:")
    print("   slug:    \(cafe.slug)")
    print("   topic:   \(cafe.topic ?? "?")")
    print("   domain:  \(cafe.domain ?? "?")")
    print("   slides:  \(cafe.slideCount) PNG")
    print("   cover:   \(cafe.coverImage?.lastPathComponent ?? "none")")
    print("   verdict: \(cafe.humanVerdict)")
    // verify each slide path actually exists + is non-empty
    var ok = 0
    for p in cafe.slidePNGs {
        let attrs = try? FileManager.default.attributesOfItem(atPath: p.path)
        let size = (attrs?[.size] as? Int) ?? 0
        if size > 0 { ok += 1 }
    }
    print("   slide files present & non-empty: \(ok)/\(cafe.slidePNGs.count)")
    exit(ok == cafe.slideCount && cafe.slideCount > 0 ? 0 : 1)
} else {
    print("❌ café carousel NOT visible in gallery")
    print("   (top 3 by recency: \(carousels.prefix(3).map { $0.slug }))")
    exit(1)
}
