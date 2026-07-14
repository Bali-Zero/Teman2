import Foundation

@main
struct WarRoomTest {
    static func main() {
        // cover = the lowest-numbered slide png; nil if none
        let tmp = FileManager.default.temporaryDirectory.appendingPathComponent("wr2cov-\(UUID().uuidString)/slides")
        try! FileManager.default.createDirectory(at: tmp, withIntermediateDirectories: true)
        for n in ["3","1","2"] { FileManager.default.createFile(atPath: tmp.appendingPathComponent("\(n).png").path, contents: Data([0])) }
        FileManager.default.createFile(atPath: tmp.appendingPathComponent("logo.png").path, contents: Data([0]))
        let pngs = WarRoom.slidePNGs(in: tmp)
        let cover = WarRoom.coverURL(slidesDir: tmp, slidePNGs: pngs)
        var fails = 0
        func expect(_ c: Bool, _ m: String) { if c { print("  ✅ \(m)") } else { print("  ❌ \(m)"); fails += 1 } }
        expect(cover?.lastPathComponent == "1.png", "cover is lowest-numbered slide, not logo")
        let empty = WarRoom.coverURL(slidesDir: tmp.appendingPathComponent("none"), slidePNGs: [])
        expect(empty == nil, "no slides → nil cover")
        print("RESULT: \(fails == 0 ? "GREEN" : "RED")")
        exit(fails == 0 ? 0 : 1)
    }
}
