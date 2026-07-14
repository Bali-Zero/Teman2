import SwiftUI
import AppKit

/// Generates the app icon PNG from the WR2 + Bali Zero concept, off-screen (no TCC).
/// Concept: a dark editorial "war-room" tile — antracite ground, the Bali Zero red ring,
/// a bold "WR2" wordmark, the yellow fact-dot (brand signal of a carousel), and a faint
/// Hammurabi-stele/column motif (the "law" texture that recurs in the carousels).
/// Invoked via:  WR2Control --makeicon <output-1024.png>
enum IconMaker {
    @MainActor
    static func runIfRequested() -> Bool {
        let args = CommandLine.arguments
        guard let i = args.firstIndex(of: "--makeicon"), i + 1 < args.count else { return false }
        let out = URL(fileURLWithPath: args[i + 1])
        let renderer = ImageRenderer(content: IconArt().frame(width: 1024, height: 1024))
        renderer.scale = 1.0
        guard let img = renderer.nsImage,
              let tiff = img.tiffRepresentation,
              let rep = NSBitmapImageRep(data: tiff),
              let png = rep.representation(using: .png, properties: [:]) else {
            FileHandle.standardError.write("icon render failed\n".data(using: .utf8)!); return true
        }
        try? png.write(to: out)
        FileHandle.standardOutput.write("ICON written → \(out.path)\n".data(using: .utf8)!)
        return true
    }
}

struct IconArt: View {
    var body: some View {
        ZStack {
            // editorial-dark rounded ground with depth
            RoundedRectangle(cornerRadius: 224, style: .continuous)
                .fill(LinearGradient(colors: [Theme.inkLift, Theme.ink],
                                     startPoint: .topLeading, endPoint: .bottomTrailing))

            // faint Hammurabi "law column" motif: vertical engraved bars
            HStack(spacing: 34) {
                ForEach(0..<5, id: \.self) { _ in
                    RoundedRectangle(cornerRadius: 8).fill(Theme.hairline).frame(width: 26)
                }
            }
            .frame(width: 520, height: 560)
            .rotationEffect(.degrees(0))
            .offset(y: 40)

            // Bali Zero red ring (the brand circle, hollow → editorial)
            Circle().strokeBorder(Theme.red, lineWidth: 46).frame(width: 620, height: 620)

            // WR2 wordmark + yellow fact-dot
            VStack(spacing: 10) {
                Text("WR2")
                    .font(.system(size: 250, weight: .heavy, design: .rounded))
                    .foregroundStyle(Theme.white)
                    .shadow(color: .black.opacity(0.4), radius: 8, y: 4)
                HStack(spacing: 12) {
                    FactRule(width: 70)
                    Circle().fill(Theme.yellow).frame(width: 22, height: 22)   // carousel "continuation" dot
                }
            }

            // tiny BZ monogram badge bottom-right (brand anchor)
            VStack { Spacer()
                HStack { Spacer()
                    ZStack {
                        Circle().fill(Theme.red).frame(width: 150, height: 150)
                        Text("BZ").font(.system(size: 64, weight: .heavy)).foregroundStyle(Theme.white)
                    }.offset(x: -90, y: -90)
                }
            }
        }
        .frame(width: 1024, height: 1024)
    }
}
