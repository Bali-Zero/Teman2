import CoreGraphics
import Foundation

// usage: clickwin <pid> <dxFromRight> <dyFromTop>   (points)
let pid = Int32(CommandLine.arguments[1])!
let dxr = Double(CommandLine.arguments[2])!
let dy = Double(CommandLine.arguments[3])!
let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as? [[String: Any]] ?? []
var best: CGRect? = nil
for w in list {
    guard let p = w[kCGWindowOwnerPID as String] as? Int32, p == pid,
          let layer = w[kCGWindowLayer as String] as? Int, layer == 0,
          let b = w[kCGWindowBounds as String] as? [String: Double] else { continue }
    let r = CGRect(x: b["X"]!, y: b["Y"]!, width: b["Width"]!, height: b["Height"]!)
    if best == nil || r.width * r.height > best!.width * best!.height { best = r }
}
guard let r = best else { print("no window"); exit(1) }
let fromLeft = CommandLine.arguments.count > 4 && CommandLine.arguments[4] == "L"
let pt = CGPoint(x: fromLeft ? r.minX + dxr : r.maxX - dxr, y: r.minY + dy)
let src = CGEventSource(stateID: .hidSystemState)
CGEvent(mouseEventSource: src, mouseType: .mouseMoved, mouseCursorPosition: pt, mouseButton: .left)?.post(tap: .cghidEventTap)
usleep(150_000)
CGEvent(mouseEventSource: src, mouseType: .leftMouseDown, mouseCursorPosition: pt, mouseButton: .left)?.post(tap: .cghidEventTap)
usleep(80_000)
CGEvent(mouseEventSource: src, mouseType: .leftMouseUp, mouseCursorPosition: pt, mouseButton: .left)?.post(tap: .cghidEventTap)
print("clicked \(pt)")
