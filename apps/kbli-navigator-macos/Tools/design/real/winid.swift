import CoreGraphics
import Foundation

let pid = Int32(CommandLine.arguments[1])!
let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as? [[String: Any]] ?? []
var best: (Int, Double)? = nil
for w in list {
    guard let p = w[kCGWindowOwnerPID as String] as? Int32, p == pid,
          let layer = w[kCGWindowLayer as String] as? Int, layer == 0,
          let b = w[kCGWindowBounds as String] as? [String: Double],
          let id = w[kCGWindowNumber as String] as? Int else { continue }
    let area = (b["Width"] ?? 0) * (b["Height"] ?? 0)
    if best == nil || area > best!.1 { best = (id, area) }
}
if let b = best { print(b.0) } else { exit(1) }
