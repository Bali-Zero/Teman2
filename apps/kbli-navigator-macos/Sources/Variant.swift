import Foundation

/// The two build variants shipped from this one codebase (`build.sh --variant internal|bkpm`).
/// build.sh bakes the choice into the bundle as the `BZVariant` Info.plist key; this is the one
/// place at runtime that asks "which variant is this build" — everything else asks THIS, never
/// the bundle identifier or a compile-time flag, so there is exactly one source of truth.
///
/// BKPM's bundle-content difference (Resources/articles/ excluded) is enforced by build.sh at
/// package time, not here — MediaLibrary already degrades to an empty array when the directory
/// is absent, so the UI only needs to hide an empty section (see MediaView), never branch on
/// AppVariant directly for that part.
enum AppVariant: String {
    case internalFull = "internal"
    case bkpm = "bkpm"

    static var current: AppVariant {
        let raw = Bundle.main.object(forInfoDictionaryKey: "BZVariant") as? String
        return raw.flatMap(AppVariant.init(rawValue:)) ?? .internalFull
    }

    /// BKPM removes every link/connection to balizero.com (Zero's ruling, 2026-08-09 app split).
    var showsExternalLinks: Bool { self == .internalFull }
}
