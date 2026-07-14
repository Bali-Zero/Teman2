import Foundation

/// Pure, Foundation-only viral cover selection logic.
/// Kept in its own file so the CLI test harness can compile it WITHOUT AppState.swift
/// (which imports SwiftUI and cannot be linked in a plain swiftc CLI build).
/// AppState.viralCovers delegates here; any future caller should do the same.
enum ViralSelector {

    /// Returns published carousels that have a non-nil shares metric and whose
    /// `modified` date falls within `windowDays` of `now`, sorted by shares DESC
    /// then reach DESC. Returns empty when no qualifying candidates exist
    /// (the caller is responsible for any "recent-PASS" fallback in the UI layer).
    static func viralCovers(_ carousels: [Carousel], now: Date, windowDays: Int) -> [Carousel] {
        let cutoff = now.addingTimeInterval(-Double(windowDays) * 86400)
        return carousels
            .filter { $0.isPublished && ($0.metrics?.shares != nil) && $0.modified >= cutoff }
            .sorted {
                let s0 = $0.metrics?.shares ?? -1, s1 = $1.metrics?.shares ?? -1
                if s0 != s1 { return s0 > s1 }
                return ($0.metrics?.reach ?? -1) > ($1.metrics?.reach ?? -1)
            }
    }
}
