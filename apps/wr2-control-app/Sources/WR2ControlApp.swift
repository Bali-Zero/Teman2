import AppKit
import SwiftUI

@main
struct WR2ControlApp: App {
    @StateObject private var state = AppState()
    @StateObject private var lang = LanguageManager()

    /// Launch the app directly in the ambient editorial wall (the Mini/TV postazione uses this).
    private let startAmbient = CommandLine.arguments.contains("--ambient")

    init() {
        // Off-screen snapshot mode (no GUI, no Screen Recording grant needed).
        // Must run on the main actor before the scene appears.
        if CommandLine.arguments.contains("--snapshot") {
            MainActor.assumeIsolated { _ = Snapshot.runIfRequested() }
            exit(0)
        }
        if CommandLine.arguments.contains("--makeicon") {
            MainActor.assumeIsolated { _ = IconMaker.runIfRequested() }
            exit(0)
        }
    }

    var body: some Scene {
        WindowGroup("WR2 Control") {
            RootView()
                .environmentObject(state)
                .environmentObject(lang)
                .frame(minWidth: 1040, minHeight: 700)
                .preferredColorScheme(.light)
                .onAppear { applyLaunchMode() }
        }
        .windowStyle(.titleBar)
        .defaultSize(width: 1180, height: 800)
    }

    @MainActor
    private func applyLaunchMode() {
        guard startAmbient else { return }
        state.mode = .ambient
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
            NSApp.windows.first?.toggleFullScreen(nil)
        }
    }
}
