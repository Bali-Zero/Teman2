import Foundation
import SwiftUI

struct StatusPayload: Decodable {
    struct Machine: Decodable {
        let user: String
        let hostname: String
        let role: String
    }

    struct Check: Decodable, Identifiable {
        let id: String
        let status: String
        let summary: String
    }

    struct Action: Decodable, Identifiable {
        let id: String
        let label: String
        let enabled: Bool
        let target: String
    }

    let generatedAt: String
    let overall: String
    let machine: Machine
    let repoRoot: String
    let checks: [Check]
    let actions: [Action]

    enum CodingKeys: String, CodingKey {
        case generatedAt = "generated_at"
        case overall
        case machine
        case repoRoot = "repo_root"
        case checks
        case actions
    }
}

struct FixPayload: Decodable {
    let target: String
    let ok: Bool
    let returncode: Int
    let stdout: String
    let stderr: String
}

struct CommandOutput {
    let status: Int32
    let stdout: String
    let stderr: String
}

enum StatusError: LocalizedError {
    case invalidRepoRoot(String)
    case commandFailed(String)

    var errorDescription: String? {
        switch self {
        case .invalidRepoRoot(let path):
            return "Invalid repo root: \(path)"
        case .commandFailed(let message):
            return message
        }
    }
}

func runProcess(executable: String, arguments: [String], cwd: URL) throws -> CommandOutput {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: executable)
    process.arguments = arguments
    process.currentDirectoryURL = cwd

    let stdoutPipe = Pipe()
    let stderrPipe = Pipe()
    process.standardOutput = stdoutPipe
    process.standardError = stderrPipe

    try process.run()
    process.waitUntilExit()

    let stdoutData = stdoutPipe.fileHandleForReading.readDataToEndOfFile()
    let stderrData = stderrPipe.fileHandleForReading.readDataToEndOfFile()
    return CommandOutput(
        status: process.terminationStatus,
        stdout: String(data: stdoutData, encoding: .utf8) ?? "",
        stderr: String(data: stderrData, encoding: .utf8) ?? ""
    )
}

func defaultRepoRoot() -> String {
    let fileManager = FileManager.default
    let current = URL(fileURLWithPath: fileManager.currentDirectoryPath)
    var cursor = current
    while true {
        if fileManager.fileExists(atPath: cursor.appendingPathComponent("scripts/nuz_status.py").path) {
            return cursor.path
        }
        let parent = cursor.deletingLastPathComponent()
        if parent.path == cursor.path {
            break
        }
        cursor = parent
    }

    for candidate in ["/Users/balizero/Desktop/nuzantara", "/Users/nuzantara/Desktop/nuzantara"] {
        if fileManager.fileExists(atPath: "\(candidate)/scripts/nuz_status.py") {
            return candidate
        }
    }
    return current.path
}

@MainActor
final class StatusModel: ObservableObject {
    @Published var repoRoot: String = defaultRepoRoot()
    @Published var payload: StatusPayload?
    @Published var isLoading = false
    @Published var lastError: String?
    @Published var fixOutput: String?
    @Published var includeNetworkChecks = true

    var overallText: String {
        payload?.overall.uppercased() ?? "UNKNOWN"
    }

    var enabledActions: [StatusPayload.Action] {
        payload?.actions.filter { $0.enabled } ?? []
    }

    func refresh() {
        isLoading = true
        lastError = nil
        let root = repoRoot
        let includeNetwork = includeNetworkChecks

        Task.detached {
            do {
                let payload = try Self.loadStatus(repoRoot: root, includeNetwork: includeNetwork)
                await MainActor.run {
                    self.payload = payload
                    self.repoRoot = payload.repoRoot
                    self.isLoading = false
                }
            } catch {
                await MainActor.run {
                    self.lastError = error.localizedDescription
                    self.isLoading = false
                }
            }
        }
    }

    func runFix(target: String) {
        isLoading = true
        lastError = nil
        fixOutput = nil
        let root = repoRoot

        Task.detached {
            do {
                let output = try Self.safeFix(repoRoot: root, target: target)
                await MainActor.run {
                    self.fixOutput = output
                    self.isLoading = false
                    self.refresh()
                }
            } catch {
                await MainActor.run {
                    self.lastError = error.localizedDescription
                    self.isLoading = false
                }
            }
        }
    }

    func runAllEnabledFixes() {
        let targets = enabledActions.map(\.target)
        guard !targets.isEmpty else { return }

        isLoading = true
        lastError = nil
        fixOutput = nil
        let root = repoRoot

        Task.detached {
            do {
                var outputs: [String] = []
                for target in targets {
                    outputs.append(try Self.safeFix(repoRoot: root, target: target))
                }
                let outputText = outputs.joined(separator: "\n\n")
                await MainActor.run {
                    self.fixOutput = outputText
                    self.isLoading = false
                    self.refresh()
                }
            } catch {
                await MainActor.run {
                    self.lastError = error.localizedDescription
                    self.isLoading = false
                }
            }
        }
    }

    nonisolated private static func loadStatus(repoRoot: String, includeNetwork: Bool) throws -> StatusPayload {
        let root = URL(fileURLWithPath: repoRoot)
        let script = root.appendingPathComponent("scripts/nuz_status.py")
        guard FileManager.default.fileExists(atPath: script.path) else {
            throw StatusError.invalidRepoRoot(repoRoot)
        }

        var arguments = [script.path, "status", "--json"]
        if !includeNetwork {
            arguments.append("--offline")
        } else {
            arguments.append("--refresh")
        }

        let output = try runProcess(executable: "/usr/bin/python3", arguments: arguments, cwd: root)
        let data = Data(output.stdout.utf8)
        do {
            return try JSONDecoder().decode(StatusPayload.self, from: data)
        } catch {
            if output.status != 0 {
                throw StatusError.commandFailed(output.stderr.isEmpty ? output.stdout : output.stderr)
            }
            throw error
        }
    }

    nonisolated private static func safeFix(repoRoot: String, target: String) throws -> String {
        let root = URL(fileURLWithPath: repoRoot)
        let script = root.appendingPathComponent("scripts/nuz_status.py")
        guard FileManager.default.fileExists(atPath: script.path) else {
            throw StatusError.invalidRepoRoot(repoRoot)
        }

        let output = try runProcess(
            executable: "/usr/bin/python3",
            arguments: [script.path, "fix", "--target", target, "--json"],
            cwd: root
        )
        let decoded = try JSONDecoder().decode(FixPayload.self, from: Data(output.stdout.utf8))
        if output.status != 0 || !decoded.ok {
            throw StatusError.commandFailed(decoded.stderr.isEmpty ? "Safe fix failed" : decoded.stderr)
        }
        return decoded.stdout.isEmpty ? "\(decoded.target): ok" : decoded.stdout
    }
}

struct DashboardView: View {
    @StateObject private var model = StatusModel()

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            content
        }
        .frame(minWidth: 760, minHeight: 520)
        .onAppear {
            model.refresh()
        }
    }

    private var header: some View {
        HStack(spacing: 14) {
            statusBadge(model.overallText)
            VStack(alignment: .leading, spacing: 3) {
                Text("Nuzantara Control")
                    .font(.title2.weight(.semibold))
                if let payload = model.payload {
                    Text("\(payload.machine.role) · \(payload.machine.user)@\(payload.machine.hostname)")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                } else {
                    Text("Status not loaded")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }
            Spacer()
            Toggle("Network", isOn: $model.includeNetworkChecks)
                .toggleStyle(.switch)
                .onChange(of: model.includeNetworkChecks) { _ in
                    model.refresh()
                }
            Button {
                model.refresh()
            } label: {
                Label("Refresh", systemImage: "arrow.clockwise")
            }
            .keyboardShortcut("r", modifiers: [.command])
            .disabled(model.isLoading)
        }
        .padding(18)
    }

    private var content: some View {
        HStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 14) {
                repoField
                checksList
            }
            .padding(18)
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)

            Divider()

            actionsPanel
                .frame(width: 260)
                .frame(maxHeight: .infinity, alignment: .top)
                .padding(18)
        }
        .overlay {
            if model.isLoading {
                ProgressView()
                    .controlSize(.large)
                    .padding(18)
                    .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8))
            }
        }
    }

    private var repoField: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Repo")
                .font(.headline)
            TextField("Repo root", text: $model.repoRoot)
                .textFieldStyle(.roundedBorder)
                .font(.system(.body, design: .monospaced))
                .onSubmit {
                    model.refresh()
                }
        }
    }

    private var checksList: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Checks")
                .font(.headline)

            if let error = model.lastError {
                MessageRow(kind: "fail", title: "Error", message: error)
            }

            if let payload = model.payload {
                ForEach(payload.checks) { check in
                    MessageRow(kind: check.status, title: check.id, message: check.summary)
                }
                Text("Updated \(payload.generatedAt)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .padding(.top, 4)
            } else if model.lastError == nil {
                Text("Waiting for first status sample")
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var actionsPanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Safe Fixes")
                .font(.headline)

            if let actions = model.payload?.actions, !actions.isEmpty {
                Button {
                    model.runAllEnabledFixes()
                } label: {
                    Label("Run enabled fixes", systemImage: "wand.and.stars")
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .disabled(model.enabledActions.isEmpty || model.isLoading)

                ForEach(actions) { action in
                    Button {
                        model.runFix(target: action.target)
                    } label: {
                        Label(action.label, systemImage: action.enabled ? "wrench.and.screwdriver" : "lock")
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .disabled(!action.enabled || model.isLoading)
                }
            } else {
                Text("No automated fix available")
                    .foregroundStyle(.secondary)
            }

            if let fixOutput = model.fixOutput {
                Text(fixOutput)
                    .font(.system(.caption, design: .monospaced))
                    .foregroundStyle(.secondary)
                    .textSelection(.enabled)
                    .padding(.top, 8)
            }

            Spacer()
        }
    }

    private func statusBadge(_ status: String) -> some View {
        let color: Color = switch status.lowercased() {
        case "ok": .green
        case "warn": .orange
        case "fail": .red
        default: .gray
        }
        return Text(status)
            .font(.caption.weight(.bold))
            .foregroundStyle(.white)
            .frame(width: 76, height: 32)
            .background(color, in: RoundedRectangle(cornerRadius: 8))
    }
}

struct MessageRow: View {
    let kind: String
    let title: String
    let message: String

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: icon)
                .foregroundStyle(color)
                .frame(width: 18)
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.body.weight(.medium))
                Text(message)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .textSelection(.enabled)
            }
            Spacer()
        }
        .padding(10)
        .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 8))
    }

    private var icon: String {
        switch kind {
        case "ok":
            return "checkmark.circle.fill"
        case "warn":
            return "exclamationmark.triangle.fill"
        case "fail":
            return "xmark.octagon.fill"
        default:
            return "questionmark.circle.fill"
        }
    }

    private var color: Color {
        switch kind {
        case "ok":
            return .green
        case "warn":
            return .orange
        case "fail":
            return .red
        default:
            return .gray
        }
    }
}

@main
struct NuzStatusApp: App {
    var body: some Scene {
        WindowGroup {
            DashboardView()
        }
        .windowResizability(.contentSize)
    }
}
