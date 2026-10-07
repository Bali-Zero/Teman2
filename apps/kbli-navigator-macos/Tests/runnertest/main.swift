import Foundation

func ck(_ c: Bool, _ m: String) { if c { print("  ✅ \(m)") } else { print("  ❌ FAIL: \(m)"); exit(1) } }

print("OpenClawRunner.parseReply tests:")
// Real shape: result.output[] entries with .text (verified live on Mini 2026-06-23)
let mock = """
some banner line
[model-fallback] noise
{
  "result": {
    "output": [
      { "type": "reasoning", "text": "" },
      { "type": "message", "text": "KBLI 55203 (Aktivitas Vila) è aperto a livello nazionale ma BLOCCATO a Bali dalla moratoria." }
    ],
    "stopReason": "stop"
  }
}
"""
let reply = OpenClawRunner.parseReply(mock)
ck(reply.contains("55203"), "parseReply extracts text mentioning 55203 (got: \(reply.prefix(60)))")
ck(reply.contains("BLOCCATO"), "parseReply keeps full message text")

// also accept the WhatsApp-bridge gateway shape (finalAssistantVisibleText) for forward-compat
let mockGw = #"prefix\n{"result":{"finalAssistantVisibleText":"Risposta gateway 55203."}}"#
ck(OpenClawRunner.parseReply(mockGw).contains("gateway 55203"), "parseReply also reads finalAssistantVisibleText")

// empty / malformed → empty string, never crash
ck(OpenClawRunner.parseReply("not json at all").isEmpty, "parseReply on garbage → empty (no crash)")

print("OpenClawRunner.command tests:")
let onMini = OpenClawRunner.commandArgs(host: "Mini-Pro2", message: "hi", agent: "zantara-kbli")
ck(onMini.first?.hasSuffix("openclaw") == true, "on Mini: argv[0] is openclaw binary (no shell)")
ck(onMini.contains("ssh") == false, "on Mini: local (no ssh)")
ck(onMini.contains("--agent") && onMini.contains("zantara-kbli"), "on Mini: passes agent")

let onM5 = OpenClawRunner.commandArgs(host: "Air-M5", message: "hi", agent: "zantara-kbli")
ck(onM5.first == "ssh", "on M5: argv[0] is ssh (no shell)")
ck(onM5.contains("mini"), "on M5: routes to mini")
ck(onM5.contains("zantara-kbli"), "on M5: passes agent name")

print("Grounding tests:")
let store = KBLIStore(jsonPath: ProcessInfo.processInfo.environment["KBLI_JSON"]!)!
let g = Grounding(store: store)
let src = g.sources(forQuery: "villa", code: store.code("55203"))
ck(src.contains("55203"), "grounding includes code 55203")
ck(src.contains("CHIUSO_PMA_NO_BESAR"), "grounding includes the real Bali status")
ck(src.uppercased().contains("FONTI") || src.contains("KBLI"), "grounding is labelled as sources")

ck(OpenClawRunner.parseReply("banner\n{\"result\":{}}").isEmpty, "auth-fail empty result -> empty reply (UI shows unavailable)")
ck(OpenClawRunner.parseReply("{\"result\":{\"output\":[{\"type\":\"reasoning\",\"text\":\"x\"}]}}").isEmpty, "reasoning-only -> empty (no leaked reasoning)")

// shell-injection guard (DeepSeek FATAL fix): metachar payload stays ONE verbatim argv element
let evil = "foo' ; echo PWNED ; $(whoami) && true"
let aMini = OpenClawRunner.commandArgs(host: "Mini-Pro2", message: evil, agent: "zantara-kbli")
ck(aMini.contains(evil), "message is ONE verbatim argv element (no shell, no injection)")
ck(!aMini.contains("/bin/zsh") && !aMini.contains("-lc"), "no shell wrapper in argv")

// ───────────────────────────────────────────────────────────────────────────────────
// REGRESSION (2026-06-25): the two real bugs that shipped "OpenClaw unreachable" on M5.
// Both passed the OLD suite — these tests would have caught them.
// ───────────────────────────────────────────────────────────────────────────────────

print("Regression: schema-drift (cicatrice #9) — payloads[] shape:")
// OpenClaw migrated output {result:…} → {payloads:[{text}]}. parseReply must read the new shape.
let mockPayloads = """
Config (/Users/nuzantara/.openclaw/openclaw.json): missing env var "X"
[bundle-mcp] noise without braces
Gateway target: ws://127.0.0.1:18789
{ "payloads": [ { "text": "Tidak. KBLI 55203 BLOKIR/CHIUSO_PMA_NO_BESAR di Bali.", "mediaUrl": null } ], "meta": { "stopReason": "stop" } }
"""
let rp = OpenClawRunner.parseReply(mockPayloads)
ck(rp.contains("55203"), "parseReply reads payloads[].text (got: \(rp.prefix(50)))")
ck(rp.contains("BLOKIR"), "parseReply keeps full payloads text")
// content key variant + last-non-empty selection
ck(OpenClawRunner.parseReply(#"{"payloads":[{"content":"hello 55203"}]}"#).contains("hello 55203"),
   "parseReply also accepts payloads[].content")
ck(OpenClawRunner.parseReply(#"{"payloads":[{"text":""},{"text":"final answer"}]}"#) == "final answer",
   "parseReply picks last non-empty payload")

print("Regression: HOME-fork (cicatrice #1) — remote ~ must stay LITERAL for the Mini's HOME:")
// THE killer bug: on M5 (user balizero) the openclaw path was tilde-expanded against the LOCAL
// HOME → /Users/balizero/.openclaw/… sent to the Mini (where it lives under /Users/nuzantara/).
// On the ssh path the openclaw arg MUST remain a literal "~" so the REMOTE shell expands it.
let onM5b = OpenClawRunner.commandArgs(host: "Air-M5", message: "hi", agent: "zantara-kbli")
ck(onM5b.contains("~/.openclaw/bin/openclaw"),
   "ssh path keeps LITERAL ~ (no local tilde-expansion). got: \(onM5b)")
ck(!onM5b.contains { $0.contains("/Users/balizero") } && !onM5b.contains { $0.contains("/Users/nuzantara") },
   "ssh path carries NO absolute /Users/* HOME (would be the HOME-fork bug)")
// Pro (user nuzantara, hostname Nuzantara) also takes the ssh path → same literal-~ requirement.
let onPro = OpenClawRunner.commandArgs(host: "Nuzantara", message: "hi", agent: "zantara-kbli")
ck(onPro.first == "ssh" && onPro.contains("~/.openclaw/bin/openclaw"),
   "Pro routes via ssh with literal ~ (not its own local HOME)")

print("Regression: shQuote — leading ~/ stays unquoted so the REMOTE shell tilde-expands:")
// The remote command is one string; single-quoting ~ would make it a literal char → path-not-found.
ck(OpenClawRunner.shQuoteForTest("~/.openclaw/bin/openclaw").hasPrefix("~/"),
   "shQuote leaves a leading ~/ UNquoted (remote shell expands HOME)")
ck(OpenClawRunner.shQuoteForTest("~/.openclaw/bin/openclaw").contains("'.openclaw/bin/openclaw'"),
   "shQuote still quotes the path remainder (injection-safe)")
ck(OpenClawRunner.shQuoteForTest("plain arg").hasPrefix("'") ,
   "shQuote fully quotes a non-tilde arg")
ck(OpenClawRunner.shQuoteForTest("a' ; rm -rf x").contains(#"'\''"#),
   "shQuote escapes embedded single-quotes (no break-out)")

print("ALL RUNNER TESTS PASSED")
