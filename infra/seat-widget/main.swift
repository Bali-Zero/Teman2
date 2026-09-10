// Claude Seats — a floating desk widget for the six Claude seats.
//
// One button, one number per window: it runs claude_seat_quota.py --json (the only
// measured source of quota on this fleet) and draws each seat's 5h and weekly usage with
// its reset. The widget never talks to the endpoint itself and never sees a token; it
// shells out to the script exactly as a human would, so the two can never disagree.
//
// The script and FLEET_TOPOLOGY.json are bundled into the .app at build time, so the
// widget does not depend on the state of any checkout. Quota is Keychain-backed and only
// readable on the machine that holds the logged-in profiles (Pro); on any other machine
// build.sh --remote pro writes a one-line config and the widget measures over ssh.
//
// Build: infra/seat-widget/build.sh [--remote HOST] [--no-launch]

import AppKit
import SwiftUI

// MARK: - Palette (claude.ai tones)

enum Palette {
    static let ivory = Color(red: 0.980, green: 0.976, blue: 0.961)   // #FAF9F5 card
    static let cloud = Color(red: 0.910, green: 0.902, blue: 0.863)   // #E8E6DC track/border
    static let ink = Color(red: 0.078, green: 0.078, blue: 0.075)     // #141413 text
    static let slate = Color(red: 0.420, green: 0.412, blue: 0.400)   // #6B6966 secondary
    static let kraft = Color(red: 0.831, green: 0.635, blue: 0.498)   // #D4A27F calm
    static let clay = Color(red: 0.851, green: 0.467, blue: 0.341)    // #D97757 Claude orange
    static let ember = Color(red: 0.690, green: 0.255, blue: 0.243)   // #B0413E saturated

    static func usage(_ v: Double?) -> Color {
        guard let v else { return cloud }
        return v >= 85 ? ember : v >= 50 ? clay : kraft
    }
}

// MARK: - Data

struct Seat: Decodable, Identifiable {
    let account: String?
    var seat: String?
    let sessionPct: Double?
    let weeklyPct: Double?
    let sessionResetsAt: String?
    let weeklyResetsAt: String?
    let error: String?
    let stale: Bool?

    var id: String { (seat ?? "?") + "|" + (account ?? "?") }

    enum CodingKeys: String, CodingKey {
        case account, seat, error, stale
        case sessionPct = "session_pct"
        case weeklyPct = "weekly_pct"
        case sessionResetsAt = "session_resets_at"
        case weeklyResetsAt = "weekly_resets_at"
    }

    var shortAccount: String {
        guard let account else { return "?" }
        let parts = account.split(separator: "@", maxSplits: 1).map(String.init)
        if parts.count == 2, parts[1] == "gmail.com" { return parts[0] }
        return account
    }
}

enum Paths {
    static let support = NSHomeDirectory() + "/Library/Application Support/Claude Seats"
    static let remoteConfig = support + "/remote"
    static let log = NSHomeDirectory() + "/Library/Logs/SeatWidget.log"

    static var repo: String? {
        let home = NSHomeDirectory()
        let roots = [ProcessInfo.processInfo.environment["NUZANTARA_REPO"],
                     home + "/nuzantara", home + "/Desktop/nuzantara"].compactMap { $0 }
        return roots.first { FileManager.default.fileExists(atPath: $0 + "/scripts/claude_seat_quota.py") }
    }

    /// Bundled copy first (frozen at build time), a checkout only when explicitly named.
    static var script: String? {
        if let r = ProcessInfo.processInfo.environment["NUZANTARA_REPO"] {
            return r + "/scripts/claude_seat_quota.py"
        }
        if let res = Bundle.main.resourcePath,
           FileManager.default.fileExists(atPath: res + "/scripts/claude_seat_quota.py") {
            return res + "/scripts/claude_seat_quota.py"
        }
        return repo.map { $0 + "/scripts/claude_seat_quota.py" }
    }

    static var topology: String? {
        if let res = Bundle.main.resourcePath,
           FileManager.default.fileExists(atPath: res + "/FLEET_TOPOLOGY.json") {
            return res + "/FLEET_TOPOLOGY.json"
        }
        return repo.map { $0 + "/FLEET_TOPOLOGY.json" }
    }

    static var remoteHost: String? {
        guard let s = try? String(contentsOfFile: remoteConfig, encoding: .utf8) else { return nil }
        let host = s.trimmingCharacters(in: .whitespacesAndNewlines)
        return host.isEmpty ? nil : host
    }
}

enum Labels {
    /// email -> "A2/_5" from FLEET_TOPOLOGY.json accounts.anthropic.slots (same rule as the script).
    static let byEmail: [String: String] = {
        guard let p = Paths.topology, let data = FileManager.default.contents(atPath: p),
              let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let accounts = root["accounts"] as? [String: Any],
              let anthropic = accounts["anthropic"] as? [String: Any],
              let slots = anthropic["slots"] as? [String: Any]
        else { return [:] }
        var out: [String: String] = [:]
        for (label, raw) in slots {
            guard let slot = raw as? [String: Any], let email = slot["email"] as? String else { continue }
            let tok = (slot["oauth_token_slot"] as? String ?? "").split(separator: "_").last.map(String.init) ?? ""
            out[email.lowercased()] = Int(tok) != nil ? "\(label)/_\(tok)" : label
        }
        return out
    }()
}

enum Quota {
    struct Outcome {
        var seats: [Seat] = []
        var hidden = 0
        var note: String?
        var failure: String?
        var source = "local"
    }

    static func measure() -> Outcome {
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/bin/zsh")
        var env = ProcessInfo.processInfo.environment
        let home = NSHomeDirectory()
        env["PATH"] = "/opt/homebrew/bin:\(home)/.local/bin:" + (env["PATH"] ?? "/usr/bin:/bin")
        for k in ["ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CONFIG_DIR"] {
            env.removeValue(forKey: k)
        }
        proc.environment = env
        var source = "local"
        if let host = Paths.remoteHost {
            source = "via \(host)"
            let remote = "export PATH=/opt/homebrew/bin:$HOME/.local/bin:$PATH; "
                + "for r in $HOME/nuzantara $HOME/Desktop/nuzantara; do "
                + "[ -f $r/scripts/claude_seat_quota.py ] && exec python3 $r/scripts/claude_seat_quota.py --json; "
                + "done; echo 'claude_seat_quota.py non trovato sul peer' >&2; exit 2"
            proc.arguments = ["-lc", "exec ssh -o BatchMode=yes -o ConnectTimeout=10 '\(host)' '\(remote)'"]
        } else if let script = Paths.script {
            proc.arguments = ["-lc", "exec python3 '\(script)' --json"]
        } else {
            return Outcome(failure: "claude_seat_quota.py non trovato (imposta NUZANTARA_REPO)")
        }
        let out = Pipe(), err = Pipe()
        proc.standardOutput = out
        proc.standardError = err
        proc.standardInput = FileHandle.nullDevice
        do { try proc.run() } catch {
            return Outcome(failure: "avvio fallito: \(error.localizedDescription)", source: source)
        }
        let watchdog = DispatchWorkItem { if proc.isRunning { proc.terminate() } }
        DispatchQueue.global().asyncAfter(deadline: .now() + 300, execute: watchdog)
        var errData = Data()
        let errThread = Thread { errData = err.fileHandleForReading.readDataToEndOfFile() }
        errThread.start()
        let outData = out.fileHandleForReading.readDataToEndOfFile()
        proc.waitUntilExit()
        while errThread.isExecuting { usleep(10_000) }
        watchdog.cancel()

        let stderr = String(decoding: errData, as: UTF8.self)
            .split(separator: "\n").last.map(String.init) ?? ""
        let stdout = String(decoding: outData, as: UTF8.self)
        guard let a = stdout.firstIndex(of: "["), let b = stdout.lastIndex(of: "]"),
              let rows = try? JSONDecoder().decode([Seat].self, from: Data(stdout[a...b].utf8)),
              !rows.isEmpty
        else {
            let why = stderr.isEmpty ? "exit \(proc.terminationStatus), nessun JSON" : stderr
            return Outcome(failure: why, source: source)
        }
        var o = Outcome(source: source)
        o.seats = rows.filter { $0.account != nil }.map { row in
            var r = row
            if r.seat == nil, let e = r.account { r.seat = Labels.byEmail[e.lowercased()] }
            return r
        }.sorted { ($0.seat ?? "~") < ($1.seat ?? "~") }
        o.hidden = rows.count - o.seats.count
        if proc.terminationStatus != 0, !stderr.isEmpty { o.note = stderr }
        return o
    }
}

// MARK: - Model

@MainActor
final class Model: ObservableObject {
    @Published var seats: [Seat] = []
    @Published var hidden = 0
    @Published var note: String?
    @Published var updatedAt: Date?
    @Published var loading = false
    @Published var source = ""
    var onChange: (() -> Void)?
    private var timer: Timer?

    func start(every seconds: TimeInterval) {
        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: seconds, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.refresh() }
        }
    }

    func refresh() {
        guard !loading else { return }
        loading = true
        let started = Date()
        DispatchQueue.global(qos: .userInitiated).async {
            let outcome = Quota.measure()
            DispatchQueue.main.async { self.apply(outcome, started: started) }
        }
    }

    private func apply(_ o: Quota.Outcome, started: Date) {
        loading = false
        source = o.source
        defer { onChange?() }
        let secs = Int(Date().timeIntervalSince(started))
        if let f = o.failure {
            note = f
            log("err \(secs)s \(o.source): \(f)")
            return
        }
        seats = o.seats
        hidden = o.hidden
        note = o.note
        updatedAt = Date()
        log("ok \(secs)s \(o.source) seats=\(o.seats.count) hidden=\(o.hidden)"
            + (o.note.map { " note=\($0)" } ?? ""))
    }

    private func log(_ line: String) {
        let data = Data("\(ISO8601DateFormatter().string(from: Date())) \(line)\n".utf8)
        if let h = FileHandle(forWritingAtPath: Paths.log) {
            h.seekToEndOfFile()
            h.write(data)
            h.closeFile()
        } else {
            FileManager.default.createFile(atPath: Paths.log, contents: data)
        }
    }
}

// MARK: - Formatting

enum Fmt {
    static let iso: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()
    static let isoPlain: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()
    static func clock(_ pattern: String) -> DateFormatter {
        let f = DateFormatter()
        f.locale = Locale(identifier: "it_IT")
        f.dateFormat = pattern
        return f
    }
    static let hm = clock("HH:mm")
    static let dayHm = clock("EEE d HH:mm")

    static func reset(_ s: String?, weekly: Bool, now: Date = Date()) -> String {
        guard let s, let d = iso.date(from: s) ?? isoPlain.date(from: s) else { return "–" }
        let mins = Int(d.timeIntervalSince(now) / 60)
        let rel: String
        if mins <= 0 { rel = "passato" }
        else if mins < 60 { rel = "\(mins)m" }
        else if mins < 1440 { rel = String(format: "%dh%02d", mins / 60, mins % 60) }
        else { rel = String(format: "%dg%02dh", mins / 1440, (mins / 60) % 24) }
        return "\((weekly ? dayHm : hm).string(from: d)) · \(rel)"
    }

    static func pct(_ v: Double?) -> String { v.map { "\(Int($0.rounded()))%" } ?? "–" }
}

// MARK: - Views

struct QuotaBar: View {
    let label: String
    let pct: Double?
    let reset: String?
    let weekly: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 5) {
                Text(label).font(.system(size: 10, weight: .bold)).foregroundStyle(Palette.slate)
                Text(Fmt.pct(pct))
                    .font(.system(size: 12, weight: .semibold, design: .rounded))
                    .foregroundStyle(pct == nil ? Palette.slate : Palette.usage(pct))
                Spacer(minLength: 2)
                Text("↻ " + Fmt.reset(reset, weekly: weekly))
                    .font(.system(size: 10)).foregroundStyle(Palette.slate).lineLimit(1)
            }
            GeometryReader { g in
                ZStack(alignment: .leading) {
                    Capsule().fill(Palette.cloud)
                    Capsule().fill(Palette.usage(pct))
                        .frame(width: g.size.width * CGFloat(min(max(pct ?? 0, 0), 100)) / 100)
                }
            }
            .frame(height: 6)
        }
        .frame(width: 190)
    }
}

struct SeatRow: View {
    let seat: Seat

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 1) {
                Text(seat.seat ?? "?")
                    .font(.system(size: 13, weight: .semibold, design: .monospaced))
                    .foregroundStyle(Palette.ink)
                Text(seat.shortAccount)
                    .font(.system(size: 10)).foregroundStyle(Palette.slate).lineLimit(1)
            }
            .frame(width: 118, alignment: .leading)
            if let e = seat.error {
                Text(e).font(.system(size: 11)).foregroundStyle(Palette.ember).lineLimit(2)
                Spacer()
            } else {
                QuotaBar(label: "5h", pct: seat.sessionPct, reset: seat.sessionResetsAt, weekly: false)
                QuotaBar(label: "7g", pct: seat.weeklyPct, reset: seat.weeklyResetsAt, weekly: true)
            }
        }
        .padding(.vertical, 4)
    }
}

struct RootView: View {
    @ObservedObject var model: Model

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 8) {
                Circle().fill(Palette.clay).frame(width: 10, height: 10)
                Text("Claude seats")
                    .font(.system(size: 16, weight: .medium, design: .serif))
                    .foregroundStyle(Palette.ink)
                Spacer()
                if let t = model.updatedAt {
                    Text("agg. " + Fmt.hm.string(from: t) + (model.source == "local" ? "" : " · " + model.source))
                        .font(.system(size: 10)).foregroundStyle(Palette.slate)
                }
                if model.loading {
                    ProgressView().controlSize(.small)
                } else {
                    Button { model.refresh() } label: {
                        Image(systemName: "arrow.clockwise")
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundStyle(Palette.clay)
                    }
                    .buttonStyle(.borderless)
                    .help("Aggiorna adesso")
                }
            }
            Rectangle().fill(Palette.cloud).frame(height: 1)
            if model.seats.isEmpty {
                Text(model.loading ? "misuro i sei seat…" : (model.note ?? "nessun dato"))
                    .font(.system(size: 12)).foregroundStyle(Palette.slate)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 40)
            } else {
                ForEach(model.seats) { SeatRow(seat: $0) }
            }
            if !model.seats.isEmpty, let n = model.note {
                Text(n).font(.system(size: 10)).foregroundStyle(Palette.ember).lineLimit(2)
            }
            if model.hidden > 0 {
                Text("\(model.hidden) vecchi login ignorati")
                    .font(.system(size: 10)).foregroundStyle(Palette.slate.opacity(0.7))
            }
        }
        .padding(.horizontal, 14)
        .padding(.top, 26)
        .padding(.bottom, 12)
        .frame(width: 560, alignment: .top)
        .background(Palette.ivory)
        .environment(\.colorScheme, .light)
    }
}

// MARK: - App

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    let model = Model()
    var panel: NSPanel!
    var host: NSHostingView<RootView>!

    /// Keep the panel exactly as tall as its content, anchored at the top edge.
    func fit() {
        let h = host.fittingSize.height
        guard h > 0, abs(panel.frame.height - h) > 1 else { return }
        var f = panel.frame
        f.origin.y = f.maxY - h
        f.size.height = h
        panel.setFrame(f, display: true, animate: false)
    }

    func applicationDidFinishLaunching(_ note: Notification) {
        host = NSHostingView(rootView: RootView(model: model))
        host.sizingOptions = [.intrinsicContentSize]
        model.onChange = { [weak self] in DispatchQueue.main.async { self?.fit() } }
        panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 560, height: 320),
                        styleMask: [.titled, .closable, .nonactivatingPanel, .utilityWindow, .fullSizeContentView],
                        backing: .buffered, defer: false)
        panel.title = "Claude seats"
        panel.titleVisibility = .hidden
        panel.titlebarAppearsTransparent = true
        panel.isMovableByWindowBackground = true
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.hidesOnDeactivate = false
        panel.isReleasedWhenClosed = false
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.delegate = self
        panel.contentView = host
        panel.setFrameAutosaveName("ClaudeSeatsPanel")
        if !panel.setFrameUsingName("ClaudeSeatsPanel"), let screen = NSScreen.main {
            let v = screen.visibleFrame
            panel.setFrameOrigin(NSPoint(x: v.maxX - 560 - 24, y: v.maxY - 320 - 24))
        }
        panel.makeKeyAndOrderFront(nil)
        fit()
        model.start(every: 30 * 60)
    }

    func windowWillClose(_ notification: Notification) { NSApp.terminate(nil) }
}

let app = NSApplication.shared
let delegate = MainActor.assumeIsolated { AppDelegate() }
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
