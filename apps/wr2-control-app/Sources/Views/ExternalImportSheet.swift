import SwiftUI
import AppKit
import UniformTypeIdentifiers

/// "Importa carosello esterno": bring in a carousel Zero built OUTSIDE the app — a single
/// PDF (page = slide), a folder of images, or several loose image files — via the
/// `wr2_carousel_import.py` normalizer. The sheet only picks the input, names the topic,
/// and picks a fit mode; the script does the normalize/resize/enqueue heavy lifting, so on
/// success the imported carousel appears in Revisione on its own (Step-7 handoff contract).
struct ExternalImportSheet: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    let onDismiss: () -> Void

    @State private var entries: [ExternalImport.InputEntry] = []
    @State private var topic: String = ""
    @State private var fit: ExternalImport.FitMode = .contain
    @State private var isRunning = false
    @State private var progressLines: [String] = []
    @State private var errorMessage: String?

    private var classification: Result<ExternalImport.InputKind, ExternalImport.ClassifyError> {
        ExternalImport.classify(entries)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            header
            pickerRow
            selectionSummary
            topicField
            fitPicker
            if isRunning { progressConsole }
            if let errorMessage {
                Text(errorMessage).font(.system(size: 12)).foregroundStyle(Theme.red)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            footer
        }
        .padding(24)
        .frame(width: 540)
        .background(Theme.antracite)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(lang.t("import.title")).font(Theme.headingFont).foregroundStyle(Theme.white)
            Text(lang.t("import.lead")).font(.system(size: 12)).foregroundStyle(Theme.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private var pickerRow: some View {
        Button { pickInputs() } label: {
            Label(lang.t("import.pickButton"), systemImage: "square.and.arrow.down")
                .font(.system(size: 12, weight: .semibold))
        }
        .buttonStyle(.bordered).tint(Theme.yellow)
        .disabled(isRunning)
    }

    @ViewBuilder private var selectionSummary: some View {
        switch classification {
        case .success(let kind):
            Text(summaryText(for: kind))
                .font(.system(size: 12)).foregroundStyle(Theme.muted)
        case .failure(let err):
            if entries.isEmpty {
                Text(lang.t("import.selection.none"))
                    .font(.system(size: 12)).foregroundStyle(Theme.muted)
            } else {
                Text(err.localized(lang))
                    .font(.system(size: 12)).foregroundStyle(Theme.red)
            }
        }
    }

    private func summaryText(for kind: ExternalImport.InputKind) -> String {
        switch kind {
        case .pdf(let u):
            return String(format: lang.t("import.selection.pdf"), u.lastPathComponent)
        case .folder(let u):
            return String(format: lang.t("import.selection.folder"), u.lastPathComponent)
        case .images(let urls):
            return String(format: lang.t("import.selection.images"), urls.count)
        }
    }

    private var topicField: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(lang.t("import.topic.label")).font(.system(size: 12, weight: .semibold)).foregroundStyle(Theme.white)
            TextField(lang.t("import.topic.placeholder"), text: $topic)
                .textFieldStyle(.roundedBorder)
                .disabled(isRunning)
        }
    }

    private var fitPicker: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(lang.t("import.fit.label")).font(.system(size: 12, weight: .semibold)).foregroundStyle(Theme.white)
            Picker("", selection: $fit) {
                ForEach(ExternalImport.FitMode.allCases) { mode in
                    Text(mode.label(lang)).tag(mode)
                }
            }
            .pickerStyle(.segmented)
            .disabled(isRunning)
            Text(fit.explanation(lang)).font(.system(size: 11)).foregroundStyle(Theme.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private var progressConsole: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 2) {
                ForEach(Array(progressLines.suffix(40).enumerated()), id: \.offset) { _, line in
                    Text(line).font(Theme.monoFont).foregroundStyle(Theme.muted)
                }
            }.frame(maxWidth: .infinity, alignment: .leading)
        }
        .frame(height: 120)
        .padding(8)
        .background(RoundedRectangle(cornerRadius: 8).fill(Theme.ink))
    }

    private var footer: some View {
        HStack {
            Spacer()
            Button { onDismiss() } label: {
                Text(lang.t("studio.cancel")).font(.system(size: 13))
            }.buttonStyle(.plain).foregroundStyle(Theme.muted).disabled(isRunning)

            Button { runImport() } label: {
                HStack(spacing: 6) {
                    if isRunning { ProgressView().controlSize(.small) }
                    Text(lang.t(isRunning ? "import.running" : "import.run"))
                }
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.black)
                .padding(.horizontal, 16).padding(.vertical, 8)
                .background(Capsule().fill(Theme.yellow))
            }
            .buttonStyle(.plain)
            .disabled(isRunning || classification.isSuccessValue == false)
        }
    }

    // MARK: - Actions

    private func pickInputs() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = true
        panel.prompt = lang.t("import.pick")
        var types: [UTType] = [.pdf, .png, .jpeg]
        if let webp = UTType(filenameExtension: "webp") { types.append(webp) }
        if let heic = UTType(filenameExtension: "heic") { types.append(heic) }
        panel.allowedContentTypes = types
        guard panel.runModal() == .OK, panel.urls.isEmpty == false else { return }
        entries = panel.urls.map { url in
            var isDir: ObjCBool = false
            FileManager.default.fileExists(atPath: url.path, isDirectory: &isDir)
            return ExternalImport.InputEntry(url: url, isDirectory: isDir.boolValue)
        }
        errorMessage = nil
    }

    private func runImport() {
        guard case .success(let kind) = classification else { return }
        let inputs = ExternalImport.inputPaths(for: kind)
        errorMessage = nil
        progressLines = []
        isRunning = true
        state.importExternalCarousel(
            inputs: inputs, topic: topic, fit: fit,
            onProgress: { line in progressLines.append(line) },
            completion: { outcome in
                isRunning = false
                switch outcome {
                case .success:
                    onDismiss()
                case .failure(let message):
                    errorMessage = message
                }
            })
    }
}

private extension Result {
    var isSuccessValue: Bool {
        if case .success = self { return true }
        return false
    }
}
