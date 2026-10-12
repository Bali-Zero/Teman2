import SwiftUI

/// Chat with Zantara (KBLI 2025 specialist, GPT-5.5 via OpenClaw on the Mini).
/// NLM-style grounded: each user turn is enriched with a locally-retrieved FONTI block so the
/// reply is anchored on the real dataset. Redesigned to the Claude-Night look: periwinkle Zantara
/// identity, soft-tint bubbles, suggested-question chips, premium pill input.
struct ChatView: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    @State private var draft: String = ""
    /// Legacy brain — kept compiled/reachable only behind `useLegacyOpenClawBrain` (design §4).
    private let legacyRunner = OpenClawRunner()
    /// The in-flight turn, if any. Cancelling it tears down the WHOLE codex process group, not
    /// just the Swift-side wait (KBLICodexRunner.run's `withTaskCancellationHandler`) — cancelled
    /// on view-disappear and superseded on every new send (single-flight, design §2).
    @State private var activeTask: Task<Void, Never>?

    var body: some View {
        VStack(spacing: 0) {
            header
            messages
            inputBar
        }
        .background(Theme.antracite)
        .onAppear(perform: consumePendingCode)
        .onDisappear { activeTask?.cancel() }
    }

    // If the user arrived via "Ask Zantara" from a code, seed the conversation with it.
    private func consumePendingCode() {
        guard let k = state.pendingCodeContext else { return }
        state.pendingCodeContext = nil
        // The chat's own read of KBLIVerdict. Opening a turn with "and its Bali status" on a
        // code whose Bali applicability the records do not determine invites exactly the answer
        // the card no longer gives; the seed is therefore derived from the verdict, in
        // KBLIChatSeed (pure, so it is covered by a test rather than by reading this view).
        let q = KBLIChatSeed.question(code: k.kode, title: k.judul,
                                      verdict: KBLIVerdict.of(record: k),
                                      isEnglish: lang.lang == .en)
        send(q)
    }

    private var header: some View {
        HStack(alignment: .center, spacing: 12) {
            // periwinkle Zantara avatar with soft glow ring
            ZStack {
                Circle().fill(Theme.zantara.opacity(0.16)).frame(width: 40, height: 40)
                Image(systemName: "sparkles").foregroundStyle(Theme.zantara).font(Theme.scalable(17, weight: .semibold))
            }
            .overlay(Circle().strokeBorder(Theme.zantara.opacity(0.25), lineWidth: 1).frame(width: 40, height: 40))
            VStack(alignment: .leading, spacing: 3) {
                Text(lang.t("chat.title")).font(Theme.headingFont).foregroundStyle(Theme.white)
                Text(lang.t("chat.lead")).font(Theme.scalable(11)).foregroundStyle(Theme.faint).lineLimit(1)
            }
            Spacer()
            Button { state.resetChat() } label: {
                Label(lang.t("chat.reset"), systemImage: "arrow.counterclockwise").font(Theme.scalable(11))
            }.buttonStyle(.plain).foregroundStyle(Theme.muted)
        }
        .padding(.horizontal, 22).padding(.vertical, 16)
        .background(Theme.ink.opacity(0.6))
        .overlay(alignment: .bottom) { Rectangle().fill(Theme.hairline).frame(height: 1) }
    }

    private var messages: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if state.messages.isEmpty && !state.chatBusy { emptyState }
                    ForEach(state.messages) { m in bubble(m).id(m.id) }
                    if state.chatBusy { thinkingRow }
                }
                .padding(22).frame(maxWidth: .infinity, alignment: .leading)
            }
            .onChange(of: state.messages.count) { _, _ in
                if let last = state.messages.last { withAnimation { proxy.scrollTo(last.id, anchor: .bottom) } }
            }
        }
    }

    // suggested-question chips shown on an empty conversation
    private var emptyState: some View {
        // D4 "Anima Indonesiana" (2026-08-11): a guilloché rosette (3-layer polar, k=12/18/7 —
        // see D4Decor.swift) sits BEHIND this unchanged chip structure, zantara-tinted, at the
        // ambient alpha tier (draft's `'medallion'` canvas role: `rosette(..., p.zan, p.amb)`).
        ZStack(alignment: .topLeading) {
            GuillocheRosette(tint: Theme.zantara, size: 220, alpha: Theme.decorAmbientAlpha)
                .offset(x: 40, y: -20)
            VStack(alignment: .leading, spacing: 12) {
                Text(lang.t("chat.lead")).font(Theme.bodyFont).foregroundStyle(Theme.muted)
                    .fixedSize(horizontal: false, vertical: true)
                VStack(alignment: .leading, spacing: 8) {
                    ForEach([lang.t("chat.suggest1"), lang.t("chat.suggest2"), lang.t("chat.suggest3")], id: \.self) { s in
                        Button { send(s) } label: { suggestChip(s) }.buttonStyle(.plain)
                    }
                }
            }
            .frame(maxWidth: 560, alignment: .leading)
            .padding(.top, 8)
        }
    }

    private func suggestChip(_ text: String) -> some View {
        HStack(spacing: 8) {
            Image(systemName: "arrow.up.right").font(Theme.scalable(10, weight: .bold)).foregroundStyle(Theme.zantara)
            Text(text).font(Theme.scalable(13)).foregroundStyle(Theme.white)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 14).padding(.vertical, 11)
        .background(RoundedRectangle(cornerRadius: Theme.radiusMd).fill(Theme.zantara.opacity(0.08)))
        .overlay(RoundedRectangle(cornerRadius: Theme.radiusMd).strokeBorder(Theme.zantara.opacity(0.18), lineWidth: 1))
        .contentShape(Rectangle())
    }

    private var thinkingRow: some View {
        HStack(spacing: 8) {
            Image(systemName: "sparkles").foregroundStyle(Theme.zantara).font(Theme.scalable(12))
            ProgressView().scaleEffect(0.6).tint(Theme.zantara)
            Text(lang.t("chat.thinking")).font(Theme.scalable(11)).foregroundStyle(Theme.faint)
        }
    }

    private func bubble(_ m: ChatMessage) -> some View {
        let isUser = m.role == .user
        let accent: Color = isUser ? Theme.accent : Theme.zantara
        return HStack(alignment: .top, spacing: 10) {
            if isUser { Spacer(minLength: 64) }
            if !isUser {
                Image(systemName: "sparkles").foregroundStyle(Theme.zantara)
                    .font(Theme.scalable(13, weight: .semibold)).frame(width: 22).padding(.top, 4)
            }
            VStack(alignment: isUser ? .trailing : .leading, spacing: 5) {
                Text(isUser ? lang.t("chat.you") : "Zantara")
                    .font(Theme.scalable(10, weight: .semibold)).tracking(0.5).foregroundStyle(accent.opacity(0.9))
                Text(m.text)
                    .font(Theme.bodyFont).foregroundStyle(Theme.white).lineSpacing(3)
                    .textSelection(.enabled)
                    .padding(.horizontal, 14).padding(.vertical, 11)
                    .background(
                        RoundedRectangle(cornerRadius: Theme.radiusLg, style: .continuous)
                            .fill(m.role == .system ? Theme.riskHigh.opacity(0.12) : accent.opacity(0.12))
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: Theme.radiusLg, style: .continuous)
                            .strokeBorder(accent.opacity(0.18), lineWidth: 1)
                    )
                    .frame(maxWidth: 540, alignment: isUser ? .trailing : .leading)
            }
            if !isUser { Spacer(minLength: 64) }
        }
    }

    private var inputBar: some View {
        HStack(spacing: 10) {
            HStack(spacing: 8) {
                Image(systemName: "text.bubble").foregroundStyle(Theme.faint).font(Theme.scalable(13))
                TextField(lang.t("chat.placeholder"), text: $draft, axis: .vertical)
                    .textFieldStyle(.plain).lineLimit(1...4)
                    .foregroundStyle(Theme.white).font(Theme.bodyFont)
                    .onSubmit { sendDraft() }
                    .accessibilityIdentifier("chat.input")   // for AX-driven QA round-trip
            }
            .padding(.horizontal, 14).padding(.vertical, 10)
            // RoundedRectangle, NOT Capsule: the TextField grows to 4 lines (axis:.vertical),
            // and a Capsule would balloon its corner radius to half the height. (Review #2.)
            .background(RoundedRectangle(cornerRadius: Theme.radiusLg, style: .continuous).fill(Theme.ink))
            .overlay(RoundedRectangle(cornerRadius: Theme.radiusLg, style: .continuous).strokeBorder(Theme.hairline, lineWidth: 1))

            let canSend = !state.chatBusy && !draft.trimmingCharacters(in: .whitespaces).isEmpty
            Button { sendDraft() } label: {
                ZStack {
                    Circle().fill(canSend ? Theme.zantara : Theme.inkLift).frame(width: 36, height: 36)
                    Image(systemName: "arrow.up").font(Theme.scalable(14, weight: .bold))
                        .foregroundStyle(canSend ? Theme.iconOnZantaraFill : Theme.faint)
                }
            }.buttonStyle(.plain).disabled(!canSend)
            .accessibilityIdentifier("chat.send")   // for AX-driven QA round-trip
        }
        .padding(.horizontal, 18).padding(.vertical, 14)
        .background(Theme.ink.opacity(0.6))
        .overlay(alignment: .top) { Rectangle().fill(Theme.hairline).frame(height: 1) }
    }

    private func sendDraft() {
        let q = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard q.isEmpty == false else { return }
        draft = ""
        send(q)
    }

    /// Single-flight (design §2): a new send cancels whatever's still in flight before starting
    /// its own Task. `KBLICodexRunner`'s own `acquireSlot()` is a second, process-level guard —
    /// this cancellation is what makes that guard never actually need to fire in normal use.
    private func send(_ userText: String) {
        state.messages.append(ChatMessage(role: .user, text: userText))
        state.chatBusy = true
        activeTask?.cancel()
        activeTask = Task { @MainActor in
            await runTurn(userText)
        }
    }

    @MainActor
    private func runTurn(_ userText: String) async {
        defer { state.chatBusy = false }

        if useLegacyOpenClawBrain {
            await runLegacyTurn(userText)
            return
        }

        switch KBLIBrain.availability() {
        case .offline:
            state.messages.append(ChatMessage(role: .system, text: lang.t("chat.unavailable")))
            return
        case .ready:
            break
        }
        guard let schema = state.rawSchema else {
            state.messages.append(ChatMessage(role: .system, text: lang.t("chat.internalError")))
            return
        }

        // history = every stored turn BEFORE the user turn just appended by send(), which is
        // passed separately as `question` (design §3.4: history + the new question are distinct
        // package inputs, not the same list).
        let history = state.messages.dropLast().map {
            KBLIChatTurn(role: $0.role == .user ? "user" : "assistant", text: $0.text)
        }
        let outcome = KBLIContextPackageBuilder.build(
            question: userText,
            currentCard: state.selected,   // "the record of the page the user is on" (design §3.1)
            history: Array(history),
            store: state.store,
            schema: schema)

        switch outcome {
        case .narrowComparison:
            state.messages.append(ChatMessage(role: .system, text: lang.t("chat.narrow")))
        case .questionTooLong:
            state.messages.append(ChatMessage(role: .system, text: lang.t("chat.tooLong")))
        case .schemaViolation:
            // Fail-closed on unknown dataset keys (design §3) — should not happen against the
            // dataset this design was measured against; if the dataset drifts, degrade honestly
            // rather than serve an unverifiable card.
            state.messages.append(ChatMessage(role: .system, text: lang.t("chat.internalError")))
        case .built(let prompt, let includedCodes, let capsByCode, let conflictCodes, _):
            do {
                let raw = try await KBLICodexRunner().run(prompt: prompt)
                if Task.isCancelled { return }
                let gate = KBLIGateContext(
                    includedCodes: includedCodes, capsByCode: capsByCode,
                    conflictCodes: conflictCodes,
                    absentCodes: KBLIContextPackageBuilder.absentQuestionCodes(from: userText, knownIn: schema),
                    questionFigures: KBLIAnswerGate.figures(inQuestion: userText))
                switch KBLIAnswerGate.check(raw, context: gate) {
                case .pass(let text):
                    let stored = KBLIContextPackageBuilder.clipAssistantTurn(text)
                    state.messages.append(ChatMessage(role: .zantara, text: stored))
                case .rejected:
                    state.messages.append(ChatMessage(role: .system, text: lang.t("chat.unverifiable")))
                }
            } catch is CancellationError {
                // superseded by a newer send — no message (the newer turn owns the conversation)
            } catch {
                let msg = (error as? KBLICodexRunnerError)?.errorDescription ?? lang.t("chat.unavailable")
                state.messages.append(ChatMessage(role: .system, text: msg))
            }
        }
    }

    /// Legacy path, kept reachable only behind `useLegacyOpenClawBrain` (design §4). Unchanged
    /// behavior from the pre-Phase-2 implementation, just re-hosted under the async `runTurn`.
    @MainActor
    private func runLegacyTurn(_ userText: String) async {
        let grounding = Grounding(store: state.store)
        let focus = state.store.search(userText).rows.first
        let grounded = grounding.prompt(userMessage: userText, focusCode: focus)
        await withCheckedContinuation { (cont: CheckedContinuation<Void, Never>) in
            legacyRunner.ask(message: grounded) { result in
                switch result {
                case .success(let reply):
                    state.messages.append(ChatMessage(role: .zantara, text: reply))
                case .failure(let err):
                    let msg = (err as? OpenClawRunner.RunnerError) != nil
                        ? lang.t("chat.unavailable")
                        : err.localizedDescription
                    state.messages.append(ChatMessage(role: .system, text: msg))
                }
                cont.resume()
            }
        }
    }
}
