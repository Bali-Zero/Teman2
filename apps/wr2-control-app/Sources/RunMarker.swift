import Foundation

/// On-disk evidence that a carousel has (or had) a live orchestrator run.
///
/// WHY THIS EXISTS (scar #2 — esiste≠armato, surfaced into the UI):
/// before this, a run lived ONLY in the RAM of the app instance that launched it
/// (`AppState.activeRun` / `rawLog` / the `ClaudeRunner`). Close+reopen the app and the
/// run became an orphan `claude -p` process the new instance knew nothing about — so the
/// Review pane showed a frozen on-disk status (`needs_rebuild_rubric6`) with ZERO sign
/// that a rebuild was actively running. The app was MUTE about work in flight.
///
/// The cure: the run leaves a breadcrumb on disk next to the carousel
/// (`<carousel>/.run.json` + a teed `<carousel>/.run.log`). Any app instance — on any
/// machine, after any restart — re-discovers in-flight runs by scanning disk, and tails
/// the log live. This is the "anche se gira su Pro, intervengo dal M5" principle made real.
struct RunMarker: Equatable {
    enum Kind: String { case fresh, revise }

    let slug: String
    let pid: Int32
    let kind: Kind
    let startedAt: Date
    /// Set once the process has terminated. nil ⇒ still believed live.
    let finishedAt: Date?
    /// Process exit code, once finished.
    let exitCode: Int32?

    var isLive: Bool { finishedAt == nil }

    /// Minutes elapsed since the run started, relative to `now`.
    func elapsedMinutes(now: Date) -> Int {
        max(0, Int(now.timeIntervalSince(startedAt) / 60.0))
    }
}

enum RunMarkerStore {
    static let markerName = ".run.json"
    static let logName = ".run.log"

    static func markerURL(in carouselDir: URL) -> URL {
        carouselDir.appendingPathComponent(markerName, isDirectory: false)
    }
    static func logURL(in carouselDir: URL) -> URL {
        carouselDir.appendingPathComponent(logName, isDirectory: false)
    }

    // MARK: - Write

    /// Record a run as STARTED. Atomic (tmp + replace) so a concurrent reader never sees
    /// a partial JSON. Best-effort: a write failure is non-fatal (the run still runs; the
    /// app just falls back to the `ps`-based detector).
    @discardableResult
    static func writeStarted(carouselDir: URL, slug: String, pid: Int32,
                             kind: RunMarker.Kind, startedAt: Date) -> Bool {
        let obj: [String: Any] = [
            "slug": slug,
            "pid": Int(pid),
            "kind": kind.rawValue,
            "started_at": iso.string(from: startedAt),
            "_provenance": "wr2-control-app run-marker (scar #2 — live run visible on disk)",
        ]
        return atomicWrite(obj, to: markerURL(in: carouselDir))
    }

    /// Record a run as FINISHED. Keeps the marker on disk (so the operator can see the
    /// last outcome) but flips it to non-live, and appends the exit code.
    @discardableResult
    static func writeFinished(carouselDir: URL, exitCode: Int32, finishedAt: Date) -> Bool {
        let url = markerURL(in: carouselDir)
        guard var obj = readRaw(url) else { return false }
        obj["finished_at"] = iso.string(from: finishedAt)
        obj["exit_code"] = Int(exitCode)
        return atomicWrite(obj, to: url)
    }

    // MARK: - Read

    static func read(in carouselDir: URL) -> RunMarker? {
        guard let obj = readRaw(markerURL(in: carouselDir)),
              let slug = obj["slug"] as? String,
              let pidN = obj["pid"] as? Int,
              let kindS = obj["kind"] as? String,
              let kind = RunMarker.Kind(rawValue: kindS),
              let startS = obj["started_at"] as? String,
              let start = iso.date(from: startS)
        else { return nil }
        let finished = (obj["finished_at"] as? String).flatMap { iso.date(from: $0) }
        let code = (obj["exit_code"] as? Int).map { Int32($0) }
        return RunMarker(slug: slug, pid: Int32(pidN), kind: kind,
                         startedAt: start, finishedAt: finished, exitCode: code)
    }

    /// True when the marker claims a live run BUT the PID is no longer alive — i.e. the
    /// process died (or the machine rebooted) without writing its `finished` record. The
    /// app treats this as "ended, outcome unknown" rather than "still running forever".
    static func isStaleLive(_ m: RunMarker) -> Bool {
        m.isLive && ProcessProbe.isAlive(pid: m.pid) == false
    }

    // MARK: - Internals

    private static let iso: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()

    private static func readRaw(_ url: URL) -> [String: Any]? {
        guard let data = try? Data(contentsOf: url),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return nil }
        return obj
    }

    private static func atomicWrite(_ obj: [String: Any], to url: URL) -> Bool {
        guard let out = try? JSONSerialization.data(
            withJSONObject: obj, options: [.prettyPrinted, .sortedKeys]) else { return false }
        let tmp = url.deletingLastPathComponent()
            .appendingPathComponent(".\(url.lastPathComponent).tmp-\(UUID().uuidString)")
        do {
            try out.write(to: tmp)
            if FileManager.default.fileExists(atPath: url.path) {
                _ = try FileManager.default.replaceItemAt(url, withItemAt: tmp)
            } else {
                try FileManager.default.moveItem(at: tmp, to: url)
            }
            return true
        } catch {
            try? FileManager.default.removeItem(at: tmp)
            return false
        }
    }
}

/// Liveness + orphan-run discovery over the process table.
///
/// The `ps`-based scan is the SECOND signal (alongside the on-disk marker) so that a run
/// launched BEFORE markers existed — or by a since-closed app instance — is still detected.
/// This is what un-mutes the app for the in-flight PID 76933 case.
enum ProcessProbe {

    /// Is `pid` a live process? `kill(pid, 0)` returns 0 when the process exists and we
    /// may signal it; ESRCH means it's gone. EPERM (exists, not ours) still ⇒ alive.
    static func isAlive(pid: Int32) -> Bool {
        guard pid > 0 else { return false }
        if kill(pid, 0) == 0 { return true }
        return errno == EPERM
    }

    /// Find live `claude -p ...` orchestrator processes, mapping each to the carousel slug
    /// named in its command line. Used as the fallback live-run detector when no on-disk
    /// marker is present (legacy / orphaned runs). Returns slug → pid.
    ///
    /// Matching is by the `output/carousel/<slug>/` substring the launch prompt always
    /// contains (both fresh and revise prompts embed it), so it is robust to quoting.
    static func liveOrchestratorRuns(knownSlugs: [String]) -> [String: Int32] {
        let listing = psListing()
        guard listing.isEmpty == false else { return [:] }
        var out: [String: Int32] = [:]
        for line in listing.split(separator: "\n") {
            // Only orchestrator launches.
            guard line.contains("claude") && line.contains("-p ")
                    && line.contains("wr2-design-architect") else { continue }
            guard let pid = firstPID(in: String(line)) else { continue }
            for slug in knownSlugs where slug.isEmpty == false {
                // Anchor on the canonical path segment to avoid a short slug matching
                // some unrelated token in the command line.
                if line.contains("output/carousel/\(slug)/")
                    || line.contains("(slug: \(slug))") {
                    out[slug] = pid
                    break
                }
            }
        }
        return out
    }

    /// Wall-clock start time of a process, via `ps -o lstart=`. Lets the UI show "da N min"
    /// for an orphan run that has no on-disk marker. nil if the process is gone / unparsable.
    static func startTime(of pid: Int32) -> Date? {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/ps")
        p.arguments = ["-o", "lstart=", "-p", String(pid)]
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = Pipe()
        guard (try? p.run()) != nil else { return nil }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        p.waitUntilExit()
        let raw = (String(data: data, encoding: .utf8) ?? "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard raw.isEmpty == false else { return nil }
        // lstart format e.g. "Wed Jun 25 14:13:07 2026"
        let fmt = DateFormatter()
        fmt.locale = Locale(identifier: "en_US_POSIX")
        fmt.dateFormat = "EEE MMM d HH:mm:ss yyyy"
        return fmt.date(from: raw)
    }

    /// Raw `ps` output (pid + full command). Best-effort; empty string on failure.
    private static func psListing() -> String {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/ps")
        p.arguments = ["-axo", "pid=,command="]
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = Pipe()
        do {
            try p.run()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            p.waitUntilExit()
            return String(data: data, encoding: .utf8) ?? ""
        } catch {
            return ""
        }
    }

    /// First integer token on a `ps` line is the PID.
    private static func firstPID(in line: String) -> Int32? {
        let trimmed = line.drop(while: { $0 == " " })
        var digits = ""
        for ch in trimmed {
            if ch.isNumber { digits.append(ch) } else { break }
        }
        return Int32(digits)
    }
}
