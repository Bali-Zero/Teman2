// Claude Seats — a floating desk widget for the six Claude seats.
//
// One button, one number per window: it runs claude_seat_quota.py --json (the only
// measured source of quota on this fleet) and draws each seat's 5h and weekly usage with
// its reset. The widget never talks to the endpoint itself and never sees a token; it
// shells out to the script exactly as a human would, so the two can never disagree.
//
// The script and FLEET_TOPOLOGY.json are bundled into the .app at build time, so the
// widget does not depend on the state of any checkout. Quota is Keychain-backed and only
// readable on the machine that holds the logged-in profiles (Pro): there the widget
// measures with --deep (a cold Keychain read returns expired tokens, i.e. zero seats) and
// publishes the report. On any other machine build.sh --remote pro makes it read that
// report over ssh, and measure only when the report is missing or stale — two widgets
// probing the same profiles is how the endpoint's rate limiter gets tripped.
//
// Build: infra/seat-widget/build.sh [--remote HOST] [--no-launch] [--no-autostart]

import AppKit
import SwiftUI

// MARK: - Palette (Claude orange card, white type)

enum Palette {
    static let clay = Color(red: 0.851, green: 0.467, blue: 0.341)     // #D97757 Claude orange
    static let clayDeep = Color(red: 0.788, green: 0.392, blue: 0.259) // #C96442 claude.ai button
    static let ink = Color(red: 0.078, green: 0.078, blue: 0.075)      // #141413 "full" bar
    static let text = Color.white
    static let muted = Color.white.opacity(0.85)
    static let track = Color.white.opacity(0.28)
    static let line = Color.white.opacity(0.35)

    static var card: LinearGradient {
        LinearGradient(colors: [clay, clayDeep], startPoint: .topLeading, endPoint: .bottomTrailing)
    }

    /// White while a window fills; ink once it is effectively gone (≥ 85 %).
    static func usage(_ v: Double?) -> Color {
        guard let v else { return track }
        return v >= 85 ? ink : text
    }
}

/// The whole card is drawn at `k` times its design size, so resizing keeps text crisp.
enum Zoom {
    static let min: CGFloat = 0.6
    static let max: CGFloat = 2.5
    static let step: CGFloat = 0.15
}

private struct ScaleKey: EnvironmentKey { static let defaultValue: CGFloat = 1 }

extension EnvironmentValues {
    var k: CGFloat {
        get { self[ScaleKey.self] }
        set { self[ScaleKey.self] = newValue }
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
    let throttled: Bool?
    /// Set when a rate-limited read kept this seat's previous numbers: when they were taken.
    var carriedSince: Date? = nil

    var id: String { (seat ?? "?") + "|" + (account ?? "?") }

    enum CodingKeys: String, CodingKey {
        case account, seat, error, stale, throttled
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

/// What a measurement is given before it counts as lost. A healthy refresh takes ~30s.
enum Budget {
    static let measure: TimeInterval = 240
    static let stuck: TimeInterval = 300
    static let retry: TimeInterval = 180
    /// A published report younger than this is served as-is by a --remote widget.
    static let reportMaxAgeMin = 40
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
        // --publish with no peers writes ~/.claude/seat-quota.json on the measuring machine,
        // which is what a --remote widget reads first. Exit 2 from --from-report means "no
        // fresh report" (and prints nothing on stdout), so only then does the peer measure.
        let measureArgs = "--json --deep --publish --peers \"\""
        if let host = Paths.remoteHost {
            source = "via \(host)"
            let remote = "export PATH=/opt/homebrew/bin:$HOME/.local/bin:$PATH; "
                + "for r in $HOME/nuzantara $HOME/Desktop/nuzantara; do "
                + "S=$r/scripts/claude_seat_quota.py; [ -f $S ] || continue; "
                + "python3 $S --json --from-report --max-age \(Budget.reportMaxAgeMin); rc=$?; "
                + "[ $rc -ne 2 ] && exit $rc; exec python3 $S \(measureArgs); "
                + "done; echo claude_seat_quota.py non trovato sul peer >&2; exit 2"
            proc.arguments = ["-lc", "exec ssh -o BatchMode=yes -o ConnectTimeout=10 '\(host)' '\(remote)'"]
        } else if let script = Paths.script {
            proc.arguments = ["-lc", "exec python3 '\(script)' \(measureArgs)"]
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
        // Two stages: a child that ignores SIGTERM must not be able to hold the widget still.
        let pid = proc.processIdentifier
        let term = DispatchWorkItem { if proc.isRunning { kill(pid, SIGTERM) } }
        let hard = DispatchWorkItem { if proc.isRunning { kill(pid, SIGKILL) } }
        DispatchQueue.global().asyncAfter(deadline: .now() + Budget.measure, execute: term)
        DispatchQueue.global().asyncAfter(deadline: .now() + Budget.measure + 15, execute: hard)

        // Both pipes on their own threads with a deadline: readDataToEndOfFile() on the
        // calling thread was the point where a measurement could never return.
        final class Box: @unchecked Sendable { var data = Data() }
        let outBox = Box(), errBox = Box()
        let readers = DispatchGroup()
        for (pipe, box) in [(out, outBox), (err, errBox)] {
            readers.enter()
            DispatchQueue.global().async {
                box.data = pipe.fileHandleForReading.readDataToEndOfFile()
                readers.leave()
            }
        }
        let readOK = readers.wait(timeout: .now() + Budget.measure + 30) == .success
        proc.waitUntilExit()
        term.cancel(); hard.cancel()
        let outData = outBox.data, errData = errBox.data
        if !readOK { return Outcome(failure: "misura scaduta dopo \(Int(Budget.measure))s", source: source) }

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
    @Published var expanded: Bool = UserDefaults.standard.object(forKey: "expanded") as? Bool ?? true {
        didSet {
            UserDefaults.standard.set(expanded, forKey: "expanded")
            onChange?()
        }
    }
    @Published var scale: CGFloat = {
        let v = UserDefaults.standard.double(forKey: "scale")
        return v > 0 ? CGFloat(v) : 1
    }() {
        didSet {
            UserDefaults.standard.set(Double(scale), forKey: "scale")
            onChange?()
        }
    }
    /// Ticks every minute so the reset countdowns move between measurements.
    @Published var clock = Date()
    /// While the grip is dragged the panel grows from its top-left corner, under the cursor.
    var resizing = false
    // Gesture anchors live on the model, not in view state: the Command Line Tools on M5
    // ship no SwiftUIMacros plugin, so the State property wrapper does not compile there.
    var gripStart: (mouse: NSPoint, size: NSSize, scale: CGFloat)?
    var pinchStart: CGFloat?
    var onChange: (() -> Void)?
    private var timer: Timer?
    private var supervisor: Timer?
    private(set) var interval: TimeInterval = 15 * 60

    func zoom(to s: CGFloat) {
        let v = (min(Zoom.max, max(Zoom.min, s)) * 100).rounded() / 100
        if v != scale { scale = v }
    }
    private var inflight: UUID?
    private var inflightSince: Date?
    private var attempt = 0

    /// True once the numbers on screen are two intervals old: they must be declared stale,
    /// not shown as if they were current.
    var isStale: Bool {
        guard let t = updatedAt else { return true }
        return Date().timeIntervalSince(t) > interval * 2
    }

    var age: String? {
        guard let t = updatedAt else { return nil }
        let m = Int(Date().timeIntervalSince(t) / 60)
        return m < 60 ? "\(m)m fa" : "\(m / 60)h\(m % 60 > 0 ? "\(m % 60)" : "") fa"
    }

    func start(every seconds: TimeInterval) {
        interval = seconds
        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: seconds, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.refresh() }
        }
        // A Timer does not make up ticks missed while the Mac sleeps, and one missed tick is
        // half an hour of frozen numbers: the per-minute supervisor picks them up and expires
        // a hung refresh.
        supervisor = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.tick() }
        }
        for t in [timer, supervisor] { t.map { RunLoop.main.add($0, forMode: .common) } }
        NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.didWakeNotification, object: nil, queue: .main
        ) { [weak self] _ in Task { @MainActor in self?.refresh(force: true) } }
    }

    private func tick() {
        clock = Date()
        if let since = inflightSince, Date().timeIntervalSince(since) > Budget.stuck {
            log("stuck \(Int(Date().timeIntervalSince(since)))s: refresh abandoned")
            inflight = nil
            inflightSince = nil
            loading = false
            note = "misura bloccata, riprovo"
        }
        let waited = updatedAt.map { Date().timeIntervalSince($0) } ?? .greatestFiniteMagnitude
        if !loading, waited >= nextDelay { refresh() } else { onChange?() }
    }

    /// After a failure it retries soon and widens, instead of waiting the full interval.
    private var nextDelay: TimeInterval {
        attempt == 0 ? interval
                     : min(interval, Budget.retry * pow(2, Double(min(attempt, 4) - 1)))
    }

    func refresh(force: Bool = false) {
        if loading {
            let expired = inflightSince.map { Date().timeIntervalSince($0) > Budget.stuck } ?? true
            guard force || expired else { return }
            inflight = nil          // a late outcome from the abandoned run must be dropped
        }
        let token = UUID()
        inflight = token
        inflightSince = Date()
        loading = true
        let started = Date()
        DispatchQueue.global(qos: .userInitiated).async {
            let outcome = Quota.measure()
            DispatchQueue.main.async { self.apply(outcome, started: started, token: token) }
        }
        onChange?()
    }

    private func apply(_ o: Quota.Outcome, started: Date, token: UUID) {
        guard token == inflight else {
            log("dropped: outcome of an already abandoned refresh")
            return
        }
        inflight = nil
        inflightSince = nil
        loading = false
        source = o.source
        defer { onChange?() }
        let secs = Int(Date().timeIntervalSince(started))
        if let f = o.failure {
            attempt += 1
            note = f
            log("err \(secs)s \(o.source): \(f) [attempt \(attempt), retry in \(Int(nextDelay / 60))m]")
            return
        }
        // No readable seat (typically a 429 on every profile): the last good measurement is
        // worth more than the void, so it is kept and declared stale.
        if o.seats.isEmpty, !seats.isEmpty {
            attempt += 1
            note = o.note ?? "nessun seat leggibile, mostro l'ultima misura buona"
            log("empty \(secs)s \(o.source) hidden=\(o.hidden) [keeping \(age ?? "?"), attempt \(attempt)]")
            return
        }
        // A 429 on one seat says nothing about its usage: keep that seat's last numbers,
        // marked with when they were taken, instead of blanking the row.
        let previous = Dictionary(seats.compactMap { s in s.account.map { ($0.lowercased(), s) } },
                                  uniquingKeysWith: { a, _ in a })
        var carried = 0
        let merged: [Seat] = o.seats.map { row in
            guard row.error != nil, row.throttled == true,
                  let acc = row.account?.lowercased(), var old = previous[acc], old.error == nil
            else { return row }
            old.carriedSince = old.carriedSince ?? updatedAt
            carried += 1
            return old
        }
        attempt = 0
        seats = merged
        hidden = o.hidden
        note = o.note
        updatedAt = Date()
        log("ok \(secs)s \(o.source) seats=\(o.seats.count) hidden=\(o.hidden) carried=\(carried)"
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

    /// The endpoint's own figure: whole when it is whole, one decimal when it is not.
    static func pct(_ v: Double?) -> String {
        guard let v else { return "–" }
        if v == v.rounded() { return "\(Int(v))%" }
        return String(format: "%.1f%%", v).replacingOccurrences(of: ".", with: ",")
    }
}

// MARK: - Views

struct QuotaBar: View {
    @Environment(\.k) private var k
    let label: String
    let pct: Double?
    let reset: String?
    let weekly: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 4 * k) {
            HStack(spacing: 5 * k) {
                Text(label).font(.system(size: 10 * k, weight: .bold)).foregroundStyle(Palette.muted)
                Text(Fmt.pct(pct))
                    .font(.system(size: 12 * k, weight: .semibold, design: .rounded))
                    .foregroundStyle(pct == nil ? Palette.muted : Palette.usage(pct))
                Spacer(minLength: 2 * k)
                Text("↻ " + Fmt.reset(reset, weekly: weekly))
                    .font(.system(size: 10 * k)).foregroundStyle(Palette.muted).lineLimit(1)
            }
            GeometryReader { g in
                ZStack(alignment: .leading) {
                    Capsule().fill(Palette.track)
                    Capsule().fill(Palette.usage(pct))
                        .frame(width: g.size.width * CGFloat(min(max(pct ?? 0, 0), 100)) / 100)
                }
            }
            .frame(height: 6 * k)
        }
        .frame(width: 190 * k)
    }
}

struct SeatRow: View {
    @Environment(\.k) private var k
    let seat: Seat

    var body: some View {
        HStack(spacing: 12 * k) {
            VStack(alignment: .leading, spacing: 1 * k) {
                Text(seat.seat ?? "?")
                    .font(.system(size: 13 * k, weight: .semibold, design: .monospaced))
                    .foregroundStyle(Palette.text)
                Text(seat.carriedSince.map { seat.shortAccount + " · misura " + Fmt.hm.string(from: $0) }
                     ?? seat.shortAccount)
                    .font(.system(size: 10 * k)).foregroundStyle(Palette.muted).lineLimit(1)
            }
            .frame(width: 118 * k, alignment: .leading)
            if let e = seat.error {
                Text(e).font(.system(size: 11 * k)).foregroundStyle(Palette.text).lineLimit(2)
                Spacer()
            } else {
                Group {
                    QuotaBar(label: "5h", pct: seat.sessionPct, reset: seat.sessionResetsAt, weekly: false)
                    QuotaBar(label: "7g", pct: seat.weeklyPct, reset: seat.weeklyResetsAt, weekly: true)
                }
                .opacity(seat.carriedSince == nil ? 1 : 0.6)
                .help(seat.carriedSince == nil ? "" : "429 dall'endpoint: ultima misura buona")
            }
        }
        .padding(.vertical, 4 * k)
    }
}

struct SeatChip: View {
    @Environment(\.k) private var k
    let seat: Seat

    var body: some View {
        VStack(alignment: .leading, spacing: 2 * k) {
            HStack(spacing: 4 * k) {
                Text((seat.seat ?? "?").split(separator: "/").first.map(String.init) ?? "?")
                    .font(.system(size: 10 * k, weight: .bold, design: .monospaced))
                    .foregroundStyle(Palette.muted)
                Spacer(minLength: 0)
                Text(seat.error == nil ? Fmt.pct(seat.sessionPct) : "!")
                    .font(.system(size: 12 * k, weight: .semibold, design: .rounded))
                    .foregroundStyle(Palette.usage(seat.sessionPct))
            }
            GeometryReader { g in
                ZStack(alignment: .leading) {
                    Capsule().fill(Palette.track)
                    Capsule().fill(Palette.usage(seat.sessionPct))
                        .frame(width: g.size.width * CGFloat(min(max(seat.sessionPct ?? 0, 0), 100)) / 100)
                }
            }
            .frame(height: 3 * k)
        }
        .frame(width: 62 * k)
        .opacity(seat.carriedSince == nil ? 1 : 0.6)
        .help("\(seat.seat ?? "?") \(seat.shortAccount) — 5h \(Fmt.pct(seat.sessionPct)) ↻ \(Fmt.reset(seat.sessionResetsAt, weekly: false)) · 7g \(Fmt.pct(seat.weeklyPct))")
    }
}

/// Drag the widget from any point of the card; buttons keep their clicks.
struct DragAnywhere: ViewModifier {
    func body(content: Content) -> some View {
        if #available(macOS 15, *) {
            content.gesture(WindowDragGesture())
        } else {
            content
        }
    }
}

/// The grip's event surface. A SwiftUI DragGesture loses to the panel's own background
/// drag (measured: the widget moved instead of growing), so the grip is a real NSView that
/// refuses to move the window and takes the mouse itself.
final class GripNSView: NSView {
    var onDrag: ((_ ended: Bool) -> Void)?
    override var mouseDownCanMoveWindow: Bool { false }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
    override func mouseDown(with event: NSEvent) { onDrag?(false) }
    override func mouseDragged(with event: NSEvent) { onDrag?(false) }
    override func mouseUp(with event: NSEvent) { onDrag?(true) }
}

struct GripHandle: NSViewRepresentable {
    let onDrag: (_ ended: Bool) -> Void
    func makeNSView(context: Context) -> GripNSView {
        let v = GripNSView()
        v.onDrag = onDrag
        return v
    }
    func updateNSView(_ v: GripNSView, context: Context) { v.onDrag = onDrag }
}

/// Bottom-right grip: dragging it zooms the whole card. The pointer is read in screen
/// coordinates because the card itself changes size under the gesture.
struct ResizeGrip: View {
    @ObservedObject var model: Model
    @Environment(\.k) private var k

    var body: some View {
        Canvas { ctx, size in
            for i in 1...3 {
                let o = CGFloat(i) * size.width / 3.2
                var p = Path()
                p.move(to: CGPoint(x: size.width - o, y: size.height))
                p.addLine(to: CGPoint(x: size.width, y: size.height - o))
                ctx.stroke(p, with: .color(Palette.muted), lineWidth: 1.3)
            }
        }
        .frame(width: 12 * k, height: 12 * k)
        .padding(4 * k)
        .overlay(GripHandle(onDrag: drag))
        .help("Trascina per ridimensionare")
    }

    private func drag(ended: Bool) {
        if ended {
            model.gripStart = nil
            model.resizing = false
            return
        }
        let m = NSEvent.mouseLocation
        guard let s = model.gripStart else {
            let size = NSApp.windows.first { $0 is WidgetPanel }?.frame.size ?? .zero
            guard size.width > 0, size.height > 0 else { return }
            model.gripStart = (m, size, model.scale)
            model.resizing = true
            return
        }
        let rx = (s.size.width + m.x - s.mouse.x) / s.size.width
        let ry = (s.size.height + s.mouse.y - m.y) / s.size.height
        model.zoom(to: s.scale * (abs(rx - 1) >= abs(ry - 1) ? rx : ry))
    }
}

struct RootView: View {
    @ObservedObject var model: Model

    private var k: CGFloat { model.scale }

    var header: some View {
        HStack(spacing: 6 * k) {
            Circle().fill(model.isStale ? Palette.ink : Palette.text).frame(width: 8 * k, height: 8 * k)
            Text(model.expanded ? "Claude seats" : "Claude")
                .font(.system(size: (model.expanded ? 15 : 13) * k, weight: .medium, design: .serif))
                .foregroundStyle(Palette.text)
                .onTapGesture { model.expanded.toggle() }
            Spacer(minLength: 4 * k)
            if model.expanded, let t = model.updatedAt {
                Text((model.isStale ? "fermo da " + (model.age ?? "?") + " · " : "agg. ")
                     + Fmt.hm.string(from: t) + (model.source == "local" ? "" : " · " + model.source))
                    .font(.system(size: 10 * k))
                    .foregroundStyle(model.isStale ? Palette.ink : Palette.muted)
            }
            if model.loading {
                ProgressView().controlSize(k >= 1.4 ? .small : .mini).tint(.white)
            } else {
                Button { model.refresh(force: true) } label: {
                    Image(systemName: "arrow.clockwise")
                        .font(.system(size: 12 * k, weight: .semibold))
                        .foregroundStyle(Palette.text)
                }
                .buttonStyle(.borderless)
                .help("Aggiorna adesso")
            }
            Button { model.expanded.toggle() } label: {
                Image(systemName: model.expanded ? "arrow.down.right.and.arrow.up.left" : "arrow.up.left.and.arrow.down.right")
                    .font(.system(size: 11 * k, weight: .bold))
                    .foregroundStyle(Palette.text)
            }
            .buttonStyle(.borderless)
            .help(model.expanded ? "Riduci" : "Espandi")
        }
        .frame(minHeight: 22 * k)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6 * k) {
            header
            if model.expanded {
                Rectangle().fill(Palette.line).frame(height: max(1, k))
                if model.seats.isEmpty {
                    Text(model.loading ? "misuro i sei seat…" : (model.note ?? "nessun dato"))
                        .font(.system(size: 12 * k)).foregroundStyle(Palette.muted)
                        .frame(maxWidth: .infinity, alignment: .center)
                        .padding(.vertical, 40 * k)
                } else {
                    Group { ForEach(model.seats) { SeatRow(seat: $0) } }.id(model.clock)
                }
                if !model.seats.isEmpty, let n = model.note {
                    Text(n).font(.system(size: 10 * k)).foregroundStyle(Palette.text).lineLimit(2)
                }
                if model.hidden > 0 {
                    Text("\(model.hidden) vecchi login ignorati")
                        .font(.system(size: 10 * k)).foregroundStyle(Palette.muted.opacity(0.8))
                }
            } else if model.seats.isEmpty {
                Text(model.loading ? "misuro…" : "nessun dato")
                    .font(.system(size: 11 * k)).foregroundStyle(Palette.muted)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 24 * k)
            } else {
                LazyVGrid(columns: [GridItem(.fixed(62 * k), spacing: 10 * k), GridItem(.fixed(62 * k), spacing: 0)],
                          alignment: .leading, spacing: 9 * k) {
                    ForEach(model.seats) { SeatChip(seat: $0) }
                }
                .id(model.clock)
                .padding(.top, 2 * k)
            }
        }
        .padding(.horizontal, 12 * k)
        .padding(.top, 9 * k)
        .padding(.bottom, (model.expanded ? 12 : 11) * k)
        .frame(width: (model.expanded ? 560 : 158) * k, alignment: .top)
        .background(Palette.card)
        .modifier(DragAnywhere())
        // After DragAnywhere, not inside it: WindowDragGesture claims every descendant's
        // mouse-down, NSView or not (measured: the grip moved the widget).
        .overlay(alignment: .bottomTrailing) { ResizeGrip(model: model) }
        .clipShape(RoundedRectangle(cornerRadius: 14 * k, style: .continuous))
        .environment(\.k, k)
        .environment(\.colorScheme, .dark)
        .simultaneousGesture(
            MagnificationGesture()
                .onChanged { v in
                    if model.pinchStart == nil { model.pinchStart = model.scale }
                    model.zoom(to: (model.pinchStart ?? model.scale) * v)
                }
                .onEnded { _ in model.pinchStart = nil }
        )
        .contextMenu {
            Button("Aggiorna adesso") { model.refresh(force: true) }
            Button(model.expanded ? "Riduci" : "Espandi") { model.expanded.toggle() }
            Divider()
            Button("Più grande") { model.zoom(to: model.scale + Zoom.step) }
            Button("Più piccolo") { model.zoom(to: model.scale - Zoom.step) }
            Button("Dimensione normale") { model.zoom(to: 1) }
            Divider()
            Button("Esci") { NSApp.terminate(nil) }
        }
    }
}

// MARK: - App

/// Borderless panels refuse key status by default; the ↻ button needs it for a first click.
final class WidgetPanel: NSPanel {
    override var canBecomeKey: Bool { true }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    let model = Model()
    var panel: WidgetPanel!
    var host: NSHostingView<RootView>!

    /// Size the panel to its content. The top edge stays put; the horizontal anchor is the
    /// screen edge the panel is nearer to, so a corner widget collapses into its corner.
    func fit() {
        let size = host.fittingSize
        guard size.width > 0, size.height > 0 else { return }
        var f = panel.frame
        if abs(f.width - size.width) < 1, abs(f.height - size.height) < 1 { return }
        let screen = panel.screen ?? NSScreen.main
        let anchorRight = !model.resizing && (screen.map { f.midX > $0.frame.midX } ?? false)
        let maxX = f.maxX, maxY = f.maxY
        f.size = size
        f.origin.y = maxY - size.height
        if anchorRight { f.origin.x = maxX - size.width }
        // Never let a size change push the card off every screen (measured: x=2012 on a
        // 1728pt display after a relaunch), where a desktop-level panel can't be recovered.
        if let v = screen?.visibleFrame {
            f.origin.x = max(v.minX, min(f.origin.x, v.maxX - f.width))
            f.origin.y = max(v.minY, min(f.origin.y, v.maxY - f.height))
        }
        panel.setFrame(f, display: true, animate: false)
    }

    func applicationDidFinishLaunching(_ note: Notification) {
        host = NSHostingView(rootView: RootView(model: model))
        host.sizingOptions = [.intrinsicContentSize]
        model.onChange = { [weak self] in
            DispatchQueue.main.async { self?.fit() }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.08) { self?.fit() }
        }
        panel = WidgetPanel(contentRect: NSRect(x: 0, y: 0, width: 560, height: 320),
                            styleMask: [.borderless, .nonactivatingPanel],
                            backing: .buffered, defer: false)
        panel.title = "Claude seats"
        panel.isMovableByWindowBackground = true
        // Nailed to the desktop: one notch above the Finder icons, under every app window.
        panel.level = NSWindow.Level(rawValue: Int(CGWindowLevelForKey(.desktopIconWindow)) + 1)
        panel.collectionBehavior = [.canJoinAllSpaces, .stationary, .ignoresCycle]
        panel.hidesOnDeactivate = false
        panel.isReleasedWhenClosed = false
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = true
        panel.delegate = self
        panel.contentView = host
        // A non-resizable panel restores only the saved ORIGIN, so fit()'s right-edge anchor
        // would start from the 560pt placeholder width: restore the saved size explicitly.
        let saved = UserDefaults.standard.string(forKey: "NSWindow Frame ClaudeSeatsPanel")
            .map { $0.split(separator: " ").prefix(4).compactMap { Double($0) } }
            .flatMap { v in v.count == 4 ? NSRect(x: v[0], y: v[1], width: v[2], height: v[3]) : nil }
        panel.setFrameAutosaveName("ClaudeSeatsPanel")
        if let r = saved, r.width > 0, r.height > 0 {
            panel.setFrame(r, display: false)
        } else if let screen = NSScreen.main {
            let v = screen.visibleFrame
            panel.setFrameOrigin(NSPoint(x: v.maxX - 560 - 24, y: v.maxY - 320 - 24))
        }
        panel.orderFrontRegardless()
        fit()
        model.start(every: 15 * 60)
    }

    func windowWillClose(_ notification: Notification) { NSApp.terminate(nil) }
}

let app = NSApplication.shared
let delegate = MainActor.assumeIsolated { AppDelegate() }
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
