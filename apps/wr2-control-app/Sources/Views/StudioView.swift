import SwiftUI

/// The launch + live-monitor screen. Plain human language, no jargon. Bilingual.
struct StudioView: View {
    var onGoToStudio: (() -> Void)? = nil
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    @State private var request: String = ""
    @State private var showRawLog = false
    @State private var pulse: Double = 1.0

    private var suggestions: [String] {
        lang.lang == .it
        ? ["il nuovo visto E33G per i nomadi digitali",
           "le regole KBLI 2025 per aprire un'attività a Bali",
           "la scadenza fiscale SPT per le aziende",
           "l'acquisto di proprietà da stranieri in Indonesia"]
        : ["visa E33G baru untuk digital nomad",
           "aturan KBLI 2025 untuk membuka usaha di Bali",
           "tenggat pajak SPT untuk perusahaan",
           "pembelian properti oleh orang asing di Indonesia"]
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                header
                launchCard
                if let run = state.activeRun {
                    monitorCard(run)
                    if showRawLog { rawLogCard }
                } else {
                    emptyHint
                }
            }
            .padding(28)
            .frame(maxWidth: 840, alignment: .leading)
            .frame(maxWidth: .infinity, alignment: .center)
        }
        .onAppear {
            // pick up an idea handed off from the brainstorm chat
            if state.prefillRequest.isEmpty == false {
                request = state.prefillRequest
                state.prefillRequest = ""
            }
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(lang.t("studio.title")).font(Theme.titleFont).foregroundStyle(Theme.white)
            FactRule(width: 44)
            Text(lang.t("studio.lead")).font(Theme.bodyFont).foregroundStyle(Theme.muted)
        }
    }

    private var launchCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 14) {
                Label(lang.t("studio.ask"), systemImage: "text.bubble")
                    .font(Theme.headingFont).foregroundStyle(Theme.white)

                ZStack(alignment: .topLeading) {
                    if request.isEmpty {
                        Text(lang.t("studio.placeholder"))
                            .font(.system(size: 14)).foregroundStyle(Theme.muted.opacity(0.7))
                            .padding(.horizontal, 12).padding(.vertical, 12)
                    }
                    TextEditor(text: $request)
                        .font(.system(size: 14)).foregroundStyle(Theme.white)
                        .scrollContentBackground(.hidden).padding(6)
                        .frame(minHeight: 64, maxHeight: 100)
                }
                .background(RoundedRectangle(cornerRadius: 10).fill(Theme.ink))
                .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(Theme.hairline))

                FlowChips(items: suggestions) { request = $0 }

                HStack {
                    if state.isRunning {
                        Button(role: .destructive) { state.cancelRun() } label: {
                            Label(lang.t("studio.cancel"), systemImage: "stop.circle")
                        }.buttonStyle(.borderedProminent).tint(Theme.red)
                    } else {
                        Button { state.launch(humanRequest: request) } label: {
                            Label(lang.t("studio.create"), systemImage: "wand.and.stars")
                                .font(.system(size: 14, weight: .semibold))
                        }
                        .buttonStyle(.borderedProminent).tint(Theme.yellow).foregroundStyle(.black)
                        .disabled(request.trimmingCharacters(in: .whitespaces).isEmpty || state.claudePath == nil)
                    }
                    Spacer()
                    if state.claudePath == nil {
                        Text(lang.t("studio.unavailable")).font(.system(size: 11)).foregroundStyle(Theme.red)
                    }
                }
            }
        }
    }

    private func monitorCard(_ run: Run) -> some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Circle().fill(Theme.statusColor(run.status)).frame(width: 9, height: 9)
                        .opacity(state.isRunning ? pulse : 1)
                        .onAppear { if state.isRunning { startPulse() } }
                    Text(run.status.localized(lang)).font(Theme.headingFont).foregroundStyle(Theme.white)
                    Spacer()
                    if let pid = run.pid {
                        Text("\(lang.t("studio.process")) #\(pid)").font(Theme.monoFont).foregroundStyle(Theme.muted)
                    }
                    Button { showRawLog.toggle() } label: {
                        Label(showRawLog ? lang.t("studio.details.hide") : lang.t("studio.details"),
                              systemImage: "terminal").font(.system(size: 11))
                    }.buttonStyle(.plain).foregroundStyle(Theme.muted)
                }

                Text("« \(run.humanRequest) »")
                    .font(.system(size: 13, design: .serif)).italic().foregroundStyle(Theme.yellow)

                VStack(spacing: 0) {
                    ForEach(Array(run.steps.enumerated()), id: \.element.id) { idx, step in
                        StepRow(step: step, isLast: idx == run.steps.count - 1, lang: lang)
                    }
                }

                if let err = run.errorMessage {
                    HStack(alignment: .top, spacing: 8) {
                        Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(Theme.red)
                        Text(err).font(Theme.bodyFont).foregroundStyle(Theme.red)
                    }
                    .padding(10).background(RoundedRectangle(cornerRadius: 8).fill(Theme.red.opacity(0.12)))
                }

                if run.status == .succeeded {
                    HStack(spacing: 14) {
                        Label(lang.t("studio.ready"), systemImage: "checkmark.circle.fill")
                            .foregroundStyle(Theme.green).font(.system(size: 13, weight: .semibold))
                        if let c = run.costUSD {
                            Text(String(format: "~$%.2f", c)).font(Theme.monoFont).foregroundStyle(Theme.muted)
                        }
                    }
                }
            }
        }
    }

    private var rawLogCard: some View {
        GlassCard(padding: 12) {
            VStack(alignment: .leading, spacing: 6) {
                Text(lang.t("studio.techlog")).font(.system(size: 11, weight: .semibold)).foregroundStyle(Theme.muted)
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 2) {
                            ForEach(Array(state.rawLog.enumerated()), id: \.offset) { i, line in
                                Text(line).font(Theme.monoFont)
                                    .foregroundStyle(line.hasPrefix("⚠︎") ? Theme.red : Theme.muted)
                                    .lineLimit(1).truncationMode(.middle).id(i)
                            }
                        }.frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .frame(height: 180)
                    .onChange(of: state.rawLog.count) { _, n in if n > 0 { proxy.scrollTo(n - 1, anchor: .bottom) } }
                }
            }
        }
    }

    private var emptyHint: some View {
        VStack(spacing: 8) {
            Image(systemName: "sparkles").font(.system(size: 30)).foregroundStyle(Theme.muted.opacity(0.5))
            Text(lang.t("studio.empty")).font(Theme.bodyFont).foregroundStyle(Theme.muted)
        }.frame(maxWidth: .infinity).padding(.top, 30)
    }

    private func startPulse() {
        withAnimation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true)) { pulse = 0.3 }
    }
}

struct StepRow: View {
    let step: RunStep
    let isLast: Bool
    let lang: LanguageManager
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(spacing: 0) {
                ZStack {
                    Circle().fill(Theme.stepColor(step.state).opacity(0.18)).frame(width: 24, height: 24)
                    Image(systemName: icon).font(.system(size: 11, weight: .bold)).foregroundStyle(Theme.stepColor(step.state))
                }
                if !isLast { Rectangle().fill(Theme.hairline).frame(width: 2, height: 22) }
            }
            VStack(alignment: .leading, spacing: 2) {
                Text(lang.t(L10n.stepKey(step.id)))
                    .font(.system(size: 13, weight: step.state == .active ? .semibold : .regular))
                    .foregroundStyle(step.state == .pending ? Theme.muted : Theme.white)
                if let d = step.detail, step.state == .active {
                    Text(d).font(.system(size: 11)).foregroundStyle(Theme.muted).lineLimit(2)
                }
            }
            Spacer()
            Text(step.state.localized(lang)).font(.system(size: 10, weight: .medium))
                .foregroundStyle(Theme.stepColor(step.state)).padding(.top, 4)
        }
    }
    private var icon: String {
        switch step.state {
        case .pending: return "circle"
        case .active: return "circle.dotted"
        case .done: return "checkmark"
        case .failed: return "xmark"
        }
    }
}

struct FlowChips: View {
    let items: [String]
    let onTap: (String) -> Void
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach(items, id: \.self) { item in
                Button { onTap(item) } label: {
                    HStack(spacing: 5) {
                        Image(systemName: "sparkle").font(.system(size: 8)).foregroundStyle(Theme.yellow.opacity(0.8))
                        Text(item).font(.system(size: 11)).foregroundStyle(Theme.muted)
                    }
                    .padding(.horizontal, 10).padding(.vertical, 5)
                    .background(Capsule().fill(Theme.hairline))
                    .overlay(Capsule().strokeBorder(Theme.hairline))
                }.buttonStyle(.plain)
            }
        }
    }
}
