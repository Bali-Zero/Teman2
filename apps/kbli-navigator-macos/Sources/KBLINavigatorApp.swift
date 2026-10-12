import AppKit
import CoreText
import SwiftUI

/// Phase-2 (design §2, R5-2/R6-2): runs the codex-runner launch sweep once per app launch (any
/// orphan process group left by a SIGKILL/crash of THIS app on a previous run gets cleaned up —
/// the one residual no in-process design can intercept) and does a best-effort group-kill of
/// whatever call is in flight when the app is about to quit, on every interceptable exit path.
final class KBLIAppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        DispatchQueue.global(qos: .utility).async {
            KBLIRunnerLaunchGuard.sweep()
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        KBLICodexRunner.terminateActiveCallForAppExit()
    }
}

@main
struct KBLINavigatorApp: App {
    @NSApplicationDelegateAdaptor(KBLIAppDelegate.self) private var appDelegate
    @StateObject private var state = AppState()
    @StateObject private var lang = LanguageManager()
    /// D4 "Anima Indonesiana" (2026-08-11): opens the custom About window (see `AboutView.swift`)
    /// from the `CommandGroup(replacing: .appInfo)` button below, replacing the system panel.
    @Environment(\.openWindow) private var openWindow
    // D3a (2026-08-11): the app now follows SYSTEM appearance (no more forced Night) — RootView
    // observes @Environment(\.colorScheme) and syncs ThemeManager.mode on first render via
    // .onChange(..., initial: true), before the user ever sees a frame. This seed value is just a
    // safe placeholder for the brief instant before that sync runs; it is not a design choice.
    @StateObject private var theme = ThemeManager(.dark)
    /// Same UserDefaults key as every other `@AppStorage("rowDensity")` read site (SearchListView,
    /// RootView's toolbar icon) — SwiftUI keeps independently-declared AppStorage properties bound
    /// to one key in sync, so ⌘⇧D here doesn't need a shared object to reach the list.
    @AppStorage("rowDensity") private var rowDensity: RowDensity = .comfortable

    init() {
        // R19 type (spec §1.5): the bundled cuts are registered for this process before any view —
        // live or snapshot — asks for one. `ATSApplicationFontsPath` (Info.plist) is the second route;
        // a cut it already registered makes this call report a harmless "already registered".
        Self.registerBundledFonts()
        // Off-screen QA snapshot mode (no GUI session needed). Must run before the scene.
        // `--snapshot-band` (design-baseline renderer, 2026-09-17) is checked FIRST and is a
        // distinct flag from legacy `--snapshot`, so both keep working independently.
        if CommandLine.arguments.contains("--snapshot-band") {
            // A band must never fall back to a system face silently: no bundled serif, no render.
            guard NSFont(name: Theme.FontName.display, size: 12) != nil else {
                FileHandle.standardError.write("font not registered: \(Theme.FontName.display)\n".data(using: .utf8)!)
                exit(4)
            }
            MainActor.assumeIsolated { _ = Snapshot.runBandIfRequested() }
            exit(0)
        }
        if CommandLine.arguments.contains("--snapshot") {
            MainActor.assumeIsolated { _ = Snapshot.runIfRequested() }
            exit(0)
        }
    }

    /// Registers every `.ttf` under `Contents/Resources/Fonts` for this process only (no install).
    private static func registerBundledFonts() {
        guard let dir = Bundle.main.resourceURL?.appendingPathComponent("Fonts", isDirectory: true),
              let files = try? FileManager.default.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil)
        else { return }
        for url in files where url.pathExtension.lowercased() == "ttf" {
            CTFontManagerRegisterFontsForURL(url as CFURL, .process, nil)
        }
    }

    var body: some Scene {
        WindowGroup("KBLI Navigator") {
            RootView()
                .environmentObject(state)
                .environmentObject(lang)
                .environmentObject(theme)
                .frame(minWidth: 1040, minHeight: 700)
        }
        .windowStyle(.titleBar)
        .defaultSize(width: 1180, height: 800)
        .commands {
            // D4 (2026-08-11): custom About window, replacing the system "About KBLI Navigator"
            // panel — Zero's direct ask for a branded window (BZLogo, arc, provenance) instead of
            // the generic AppKit one.
            CommandGroup(replacing: .appInfo) {
                Button("About KBLI Navigator") { openWindow(id: "about") }
            }
            // D2 (2026-08-11): a menu-bar `Commands` group so the search-focus / copy-code / density
            // shortcuts are discoverable (not just muscle-memory), per the Dash-style keyboard model.
            CommandMenu("Commands") {
                Button("Search Codes") { state.focusSearchTrigger += 1 }
                    .keyboardShortcut("k", modifiers: .command)

                Button("Copy KBLI Code") {
                    guard let code = state.selected?.kode else { return }
                    let pb = NSPasteboard.general
                    pb.clearContents()
                    pb.setString(code, forType: .string)
                }
                .keyboardShortcut("c", modifiers: .command)
                .disabled(state.selected == nil)
                // GOTCHA (declared, not fixed): ⌘C is ALSO the system Edit > Copy shortcut. macOS
                // resolves a key-equivalent collision by walking the menu bar left→right and firing
                // the first ENABLED match; Edit > Copy is validated via the responder chain (enabled
                // only when the first responder — e.g. a focused TextField with a selection — answers
                // `copy:`), so it wins whenever there's text to copy and this item only fires when
                // nothing else claims the shortcut (a code selected, no text field capturing it).
                // That fallback ordering is exactly the wanted behavior, but it rests on menu-bar
                // ordering that a GUI session must confirm — declared here per the "no GUI session"
                // build/verify path this task otherwise uses.

                Divider()

                Button("Toggle Density") { rowDensity.toggle() }
                    .keyboardShortcut("d", modifiers: [.command, .shift])
            }
        }

        // D4: custom About window (macOS 13+ `Window` scene). `.windowResizability(.contentSize)`
        // locks it to AboutView's own intrinsic size — no user resize handle on a fixed layout.
        Window("About KBLI Navigator", id: "about") {
            AboutView()
                .environmentObject(lang)
        }
        .windowResizability(.contentSize)
    }
}
