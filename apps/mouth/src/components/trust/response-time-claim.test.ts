import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * `Avg reply: 2 min` was served on the homepage from three places — TrustBar's
 * desktop and mobile variants and the hero CTA — and nobody had ever measured
 * it. It was not merely unmeasured. Measured, it was false.
 *
 * Read-only against the live Meta inbox store (`meta_inbox_messages`), pairing
 * each inbound message with the first outbound in the same thread, 189 pairs
 * between 2026-06-03 and 2026-07-30:
 *
 *     average  548.8 min (~9h)   median 4.9 min   p90 411.2 min
 *     answered within 2 min: 24.3%
 *
 * Under the two framings most favourable to the claim it still does not hold:
 * counting only the first inbound of a customer turn gives an average of 191.4
 * min (median 2.6, n=31), and restricting to 08:00-18:00 WITA gives 556.6 min —
 * so it is not an overnight artefact either. The word on the page was "Avg",
 * and the average is hours.
 *
 * The claim is therefore removed rather than corrected: no store here can
 * support a public response-time number today. `whatsapp_message_context`, the
 * main WhatsApp mirror, has written nothing since 2026-05-25;
 * `conversation_messages` has `thread_id` NULL on all 881 rows, so an inbound
 * cannot even be linked to its reply there. That absence is why this was never
 * measured before.
 *
 * Declared limit: this guard cannot tell whether a response-time claim is TRUE.
 * It bans the shape outright. If one is ever measured and we want it back, it
 * belongs in a module beside the Google figures, carrying its own MEASURED_ON,
 * and this test gets an explicit exception naming that module — not a widened
 * regex.
 */

const SRC = join(__dirname, "..", "..");
const SCANNED = ["app", "components", "lib"];
const SELF = "response-time-claim";

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      out.push(...walk(full));
    } else if (/\.tsx?$/.test(entry) && !entry.includes(SELF)) {
      out.push(full);
    }
  }
  return out;
}

const FILES = SCANNED.flatMap((d) => walk(join(SRC, d)));

// Anchored to the CLAIM, not to a duration. "2 minutes" is a poll interval in
// MemoryPulse and "min-w-0" is a Tailwind class; neither asserts anything about
// how fast we answer. What is banned is a promise about reply speed.
// A machine answering a request is not a person answering a customer, and the
// first draft of this guard could not tell them apart: `responds? (in|within) N`
// fired on "knowledge search should respond within 2 seconds" (a latency SLO in
// an integration test) and on "We must respond within 3 s" (the Twitter CRC
// handshake, in generated API schema). Both are engineering, neither is a
// promise to a reader. So "respond" is only a claim when a first-person subject
// makes it; "reply" needs no subject, because nothing in this app says a server
// replies.
const CLAIMS: RegExp[] = [
  /\b(avg|average)\.?\s+repl(y|ies)\b/i,
  /\brepl(y|ies|ying)\s+(in|within)\s+(under\s+)?\d/i,
  /\b(we|our\s+team|balizero)\s+(repl(y|ies)|responds?)\s+(in|within)\s+(under\s+)?\d/i,
  /\breply\s+time\s*[:=]\s*\d/i,
];

describe("no page claims a response time nobody measured", () => {
  it("scans a plausible number of files", () => {
    // A broken walk returns nothing and lets the assertion below pass by having
    // looked at no files at all.
    expect(FILES.length).toBeGreaterThan(100);
  });

  it("no file promises a reply speed", () => {
    const offenders = FILES.filter((f) => {
      const body = readFileSync(f, "utf8");
      return CLAIMS.some((re) => re.test(body));
    }).map((f) => f.slice(SRC.length + 1));
    expect(offenders).toEqual([]);
  });

  it("guilt: it catches the three shapes that were actually served", () => {
    for (const served of [
      "          <span>Avg reply: 2 min</span>",
      "          Chat with us — avg reply: 2 min",
      "  <p>We reply within 5 minutes</p>",
      "  <p>Our team responds in 2 minutes</p>",
      "  <span>Reply time: 2 min</span>",
    ]) {
      expect(
        CLAIMS.some((re) => re.test(served)),
        `no pattern caught: ${served}`,
      ).toBe(true);
    }
  });

  it("innocence: it does not fire on the durations that are not claims", () => {
    // Every string here is real code from this app. A guard that trips on a
    // Tailwind class or a poll interval teaches the next person to delete it.
    for (const innocent of [
      '        <div className="flex items-center gap-2 min-w-0">',
      '          className="group flex items-center gap-2 px-3 py-2 min-h-[44px] rounded"',
      "const POLL_INTERVAL = 120000; // 2 minutes",
      "    // Refresh memory every 2 minutes or when a new chat starts",
      "  /** Streaming message timeout (2 minutes) */",
      '        <span className="text-xs">12 min read</span>',
      "          <span>Licensed Notary & Tax Agent</span>",
      "  const minutes = Math.floor(seconds / 60);",
      // A latency SLO and a webhook handshake deadline. Both say "respond
      // within N"; neither is addressed to a customer. These two are why the
      // "respond" pattern requires a first-person subject.
      '    it("knowledge search should respond within 2 seconds", async () => {',
      "     *     Twitter sends GET with ``?crc_token=TOKEN``.  We must respond within 3 s",
    ]) {
      const fired = CLAIMS.filter((re) => re.test(innocent));
      expect(fired.length, `fired on: ${innocent}`).toBe(0);
    }
  });
});
