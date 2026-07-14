import SwiftUI

/// Brainstorm the carousel idea by chatting with Claude or Codex BEFORE launching the pipeline.
/// When the AI proposes a "TOPIC:", a button hands it off to the Studio launch field.
struct ChatView: View {
    var goToStudio: () -> Void
    @EnvironmentObject var state: AppState
    @EnvironmentObject var lang: LanguageManager
    @State private var draft: String = ""

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider().overlay(Theme.hairline)
            messages
            handoffBar
            inputBar
        }
        .background(Theme.ink)
    }

    private var header: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 6) {
                Text(lang.t("chat.title")).font(Theme.titleFont).foregroundStyle(Theme.white)
                FactRule(width: 44)
                Text(lang.t("chat.lead")).font(Theme.bodyFont).foregroundStyle(Theme.muted)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 8) {
                modelPicker
                Button { state.resetChat() } label: {
                    Label(lang.t("chat.reset"), systemImage: "arrow.counterclockwise").font(.system(size: 11))
                }.buttonStyle(.plain).foregroundStyle(Theme.muted)
            }
        }.padding(20)
    }

    private var modelPicker: some View {
        HStack(spacing: 6) {
            Text(lang.t("chat.with")).font(.system(size: 10)).foregroundStyle(Theme.muted)
            ForEach(ChatModel.allCases, id: \.self) { m in
                Button { state.chatModel = m } label: {
                    Label(m.label, systemImage: m.icon).font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(state.chatModel == m ? .black : Theme.muted)
                        .padding(.horizontal, 9).padding(.vertical, 4)
                        .background(Capsule().fill(state.chatModel == m ? Theme.yellow : Theme.hairline))
                }.buttonStyle(.plain).disabled(state.chatBusy)
            }
        }
    }

    private var messages: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 12) {
                    if state.chat.isEmpty {
                        emptyState
                    }
                    ForEach(state.chat) { m in bubble(m).id(m.id) }
                }
                .padding(20)
                .frame(maxWidth: 760, alignment: .leading)
                .frame(maxWidth: .infinity, alignment: .center)
            }
            .onChange(of: state.chat.count) { _, _ in
                if let last = state.chat.last { withAnimation { proxy.scrollTo(last.id, anchor: .bottom) } }
            }
        }
        .frame(maxHeight: .infinity)
    }

    private var emptyState: some View {
        VStack(spacing: 8) {
            Image(systemName: "bubble.left.and.bubble.right").font(.system(size: 30)).foregroundStyle(Theme.muted.opacity(0.5))
            Text(lang.t("chat.empty")).font(Theme.bodyFont).foregroundStyle(Theme.muted)
        }.frame(maxWidth: .infinity).padding(.top, 50)
    }

    private func bubble(_ m: ChatMessage) -> some View {
        HStack(alignment: .top, spacing: 10) {
            if m.role == .assistant {
                ZStack { Circle().fill(Theme.yellow.opacity(0.18)).frame(width: 26, height: 26)
                    Image(systemName: state.chatModel.icon).font(.system(size: 11)).foregroundStyle(Theme.yellow) }
            } else {
                Spacer(minLength: 60)
            }
            VStack(alignment: m.role == .user ? .trailing : .leading, spacing: 2) {
                Text(m.pending && m.text.isEmpty ? lang.t("chat.thinking") : m.text)
                    .font(.system(size: 13))
                    .foregroundStyle(m.role == .user ? .black : Theme.white)
                    .textSelection(.enabled)
                    .padding(.horizontal, 12).padding(.vertical, 9)
                    .background(RoundedRectangle(cornerRadius: 12)
                        .fill(m.role == .user ? Theme.yellow : Theme.inkLift))
                    .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.hairline))
            }
            if m.role == .user {
                ZStack { Circle().fill(Theme.hairline).frame(width: 26, height: 26)
                    Image(systemName: "person.fill").font(.system(size: 11)).foregroundStyle(Theme.muted) }
            } else {
                Spacer(minLength: 60)
            }
        }
        .frame(maxWidth: .infinity, alignment: m.role == .user ? .trailing : .leading)
    }

    @ViewBuilder private var handoffBar: some View {
        if let topic = state.pendingTopicFromChat {
            HStack(spacing: 10) {
                Image(systemName: "lightbulb.fill").foregroundStyle(Theme.yellow)
                Text(topic).font(.system(size: 12, weight: .semibold)).foregroundStyle(Theme.white).lineLimit(1)
                Spacer()
                Button {
                    state.prefillRequest = topic
                    goToStudio()
                } label: {
                    Label(lang.t("chat.useidea"), systemImage: "arrow.right.circle.fill")
                        .font(.system(size: 12, weight: .semibold)).foregroundStyle(.black)
                        .padding(.horizontal, 12).padding(.vertical, 7)
                        .background(Capsule().fill(Theme.yellow))
                }.buttonStyle(.plain)
            }
            .padding(.horizontal, 16).padding(.vertical, 10)
            .background(Theme.yellow.opacity(0.08))
            .overlay(Rectangle().fill(Theme.yellow).frame(height: 2), alignment: .top)
        }
    }

    private var inputBar: some View {
        HStack(spacing: 10) {
            TextField(lang.t("chat.placeholder"), text: $draft, axis: .vertical)
                .textFieldStyle(.plain).font(.system(size: 13)).foregroundStyle(Theme.white)
                .padding(.horizontal, 12).padding(.vertical, 10)
                .background(RoundedRectangle(cornerRadius: 10).fill(Theme.inkLift))
                .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(Theme.hairline))
                .lineLimit(1...4)
                .onSubmit(send)
            Button(action: send) {
                Image(systemName: state.chatBusy ? "ellipsis" : "paperplane.fill")
                    .font(.system(size: 14, weight: .semibold)).foregroundStyle(.black)
                    .frame(width: 40, height: 38).background(RoundedRectangle(cornerRadius: 10).fill(Theme.yellow))
            }.buttonStyle(.plain)
            .disabled(state.chatBusy || draft.trimmingCharacters(in: .whitespaces).isEmpty || state.claudePath == nil)
        }
        .padding(16)
        .background(Theme.antracite.opacity(0.4))
    }

    private func send() {
        let t = draft
        draft = ""
        state.sendChat(t)
    }
}
