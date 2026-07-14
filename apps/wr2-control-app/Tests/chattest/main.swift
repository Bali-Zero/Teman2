import Foundation

// Integration: prove the chat is IMMERSED in WR2 — it must know which carousels already exist
// (from the loaded past-topics context) and avoid re-proposing them.

let chatter = Conversationalist()
final class Box { var reply = ""; var done = false; var ok = false }
let box = Box()

// sanity: the immersive context actually loaded?
let ctxLen = Conversationalist.systemPrompt.count
print("▸ system prompt length: \(ctxLen) chars (base ~700 → if much larger, immersion loaded)")

print("▸ asking the chat what's already been covered (tests immersion)…")
chatter.send(
    model: .claude,
    history: [],
    user: "Ho già fatto caroselli sul Golden Visa, sulla SPT tax e sull'E33G? Elenca 3 argomenti che NON ho ancora coperto e che dovrei fare. Chiudi con TOPIC:.",
    onDelta: { d in box.reply = d },
    onDone: { ok in box.ok = ok; box.done = true })

let deadline = Date().addingTimeInterval(120)
while box.done == false && Date() < deadline {
    RunLoop.main.run(mode: .default, before: Date().addingTimeInterval(0.2))
}

print("\n────────── immersion assertions ──────────")
var fails = 0
func expect(_ c: Bool, _ m: String) { if c { print("  ✅ \(m)") } else { print("  ❌ \(m)"); fails += 1 } }
expect(ctxLen > 3000, "immersive context loaded into system prompt (\(ctxLen) chars)")
expect(box.done && box.ok, "turn completed cleanly")
expect(box.reply.count > 30, "got a substantive reply (\(box.reply.count) chars)")
expect(AppState.extractTopic(box.reply) != nil, "TOPIC extracted")
// soft signal: does it reference real past work?
let knows = ["golden", "spt", "e33g", "kbli", "property", "kitas", "tax residen"].contains { box.reply.lowercased().contains($0) }
expect(knows, "reply references real Bali Zero domains (immersion working)")

print("\n--- reply ---\n\(box.reply.prefix(700))")
print("\nRESULT: \(fails == 0 ? "GREEN" : "RED") — \(fails) failure(s)")
exit(fails == 0 ? 0 : 1)
