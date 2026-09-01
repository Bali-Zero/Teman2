import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// Named `*Messages` — NOT `it`/`id` — because vitest's global `it()` test
// function lives in this module's scope too; a default import literally named
// `it` shadows it and every `it(...)` below would silently resolve to the JSON
// module. (Same trap already documented in i18n/secondhome-forbidden-claims.)
import enMessages from "../../i18n/locales/en.json";
import itMessages from "../../i18n/locales/it.json";
import idMessages from "../../i18n/locales/id.json";

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
//
// Second round (2026-08-18). The first version was blind to every shape but the
// one it was written from. Measured misses, in this very repo:
//   - `{ value: "4.8h", label: "avg first-reply on WhatsApp" }` — `\s+` accepts
//     only whitespace, and "first-" sits between "avg" and "repl".
//   - `Typical first reply on WhatsApp in under 5 hours.` — a prepositional
//     phrase between the noun and "in".
//   - `Usually within 15 minutes.` — no reply word in the sentence at all; only
//     the <h1> above it made it a reply promise.
//   - `AVG_REPLY_MINUTES = 2` — an identifier, no space to match.
// The patterns below were chosen AFTER the innocence corpus was fixed, and each
// was run against all of it. Widening any of them means re-running both lists.
//
// Third round (2026-08-20). `packages/core` was opened, so the two shapes the
// DECLARED GAP block used to hold are now removable, and the block is gone —
// what it described no longer exists. Two changes, both re-run against the
// whole innocence list:
//   - Pattern 1: `\s+` -> `\.?[^.\n]{0,16}?`, so a hyphenated infix lands
//     ("avg first-reply"). The literal `\.?` is KEPT: `[^.\n]` excludes the
//     period, and dropping it would have silently un-caught "Avg. reply: 2 min",
//     which is in the guilt list. The recipe left in the old block omitted it.
//     "Avg Latency" survives because `\brepl(y|ies)\b` needs a whole word
//     within 16 chars, and "replace" is not one.
//   - Pattern 9 (new): the `responseMinutes` prop, by name and by its snake and
//     hyphen spellings. It is deliberately narrow — `responseTime` is a real
//     variable in this app (innocence list) and any pattern reaching it would
//     fire on machine latency, which is not a promise to a reader.
//
// Fourth round (2026-08-24). Three claims were still SERVED in production on
// `8ccd7d2b8` and none of the nine patterns above could have stopped them, for
// two structurally different reasons:
//   - `we'll pick up in under 5 hours.` (app/visa/clock/[hash]/page.tsx:177) sat
//     in a file this walk DOES read. No pattern fired: "pick up" is not a reply
//     word. Diction, not scope. -> Pattern 10 below.
//   - `secondHome.cta.note` in i18n/locales/{en,it,id}.json. Patterns 1 and 3 DO
//     match the English string — the walk simply never opened the file. Scope,
//     not diction. -> the i18n block at the bottom of this file.
// Pattern 10 requires a first-person subject and forbids an object between
// "pick up" and "in/within", for the same reason "respond" needs a subject:
// "pick up your passport in 3 days" is a collection time, not a reply promise.
// Measured against all 1,453 walked files: 1 hit, the offender, zero others.
const CLAIMS: RegExp[] = [
  /\b(avg|average|typical)\.?[^.\n]{0,16}?\brepl(y|ies)\b/i,
  /\b(avg|average|typical)\.?\s+response\s*[:=]?\s*(under\s+|less\s+than\s+)?\d/i,
  /\brepl(y|ies|ying)\b[^.\n]{0,20}?\b(in|within)\s+(under\s+|less\s+than\s+)?\d/i,
  /\b(we|our\s+team|balizero)\s+(repl(y|ies)|responds?)\s+(in|within)\s+(under\s+)?\d/i,
  /\bresponded\s+to\s+(in|within)\s+(under\s+)?\d/i,
  /\brepl(y|ies)\s+time\s*[:=]\s*\d/i,
  /\bavg[_\s-]*repl(y|ies)(?![a-z])/i,
  /\busually\s+(?:within|under)\s+\d+\s*(?:min|hour|hr)[a-z]*\b/i,
  /\b(response|repl(?:y|ies))[_\s-]*minutes\b/i,
  /\b(?:we|we'll|we will|our\s+team|balizero)\b[^.\n]{0,20}?\bpick\s+up\s+(?:in|within)\s+(?:under\s+|less\s+than\s+)?\d/i,
];

/**
 * The i18n surface, and why it is reached by IMPORT rather than by the walk.
 *
 * `SCANNED` is ["app", "components", "lib"]; the dictionaries live in
 * `src/i18n/locales/`, a sibling of all three. Widening the walk's extension
 * filter to `.json` — the obvious move — was MEASURED before being written:
 * there are ZERO `.json` files under app/components/lib, so it would read no
 * new file and still not reach a single locale. An armed-looking change that
 * cannot fire is the disease this guard exists to prevent, so it was not made.
 * Widening `SCANNED` itself is a separate decision and is deliberately not
 * taken here. The three dictionaries are therefore named explicitly, which is
 * also what the header above prescribes for exceptions: name the module, do
 * not widen a regex.
 *
 * Per-language patterns, because English-only matching is exactly how the
 * Italian and Indonesian copies of this same claim stayed green while the
 * English one was catchable (family #3 UNDER-match, the W77 language axis).
 */
const CLAIMS_IT: RegExp[] = [
  /\brispost[ae]\b[^.\n]{0,30}?\b(?:entro|in)\s+(?:meno\s+di\s+)?\d/i,
  /\brispondiamo\b[^.\n]{0,25}?\b(?:entro|in)\s+(?:meno\s+di\s+)?\d/i,
  /\btempo\s+di\s+rispost[ae]\s*[:=]\s*\d/i,
];

const CLAIMS_ID: RegExp[] = [
  /\bbalasan\b[^.\n]{0,30}?\b(?:kurang\s+dari|dalam|di\s+bawah)\s+\d/i,
  /\bkami\s+(?:akan\s+)?membalas\b[^.\n]{0,25}?\b(?:dalam|kurang\s+dari)\s+\d/i,
  /\bwaktu\s+balas(?:an)?\s*[:=]\s*\d/i,
];

const DICTIONARIES: {
  locale: string;
  messages: unknown;
  patterns: RegExp[];
}[] = [
  { locale: "en", messages: enMessages, patterns: CLAIMS },
  { locale: "it", messages: itMessages, patterns: CLAIMS_IT },
  { locale: "id", messages: idMessages, patterns: CLAIMS_ID },
];

/** Every string leaf under a JSON subtree, with its dotted key path. */
function leaves(node: unknown, path: string[], out: [string, string][]): void {
  if (typeof node === "string") {
    out.push([path.join("."), node]);
    return;
  }
  if (Array.isArray(node)) {
    node.forEach((v, i) => leaves(v, [...path, String(i)], out));
    return;
  }
  if (node && typeof node === "object") {
    for (const [k, v] of Object.entries(node as Record<string, unknown>)) {
      leaves(v, [...path, k], out);
    }
  }
}

function sweep(messages: unknown, patterns: RegExp[]): string[] {
  const out: [string, string][] = [];
  leaves(messages, [], out);
  return out
    .filter(([, value]) => patterns.some((re) => re.test(value)))
    .map(([key, value]) => `${key}: ${value}`);
}

// ── DECLARED GAP (2026-08-24) ─────────────────────────────────────────────
// Two reply-speed-adjacent surfaces are knowingly NOT covered here. Written
// down rather than left silent, because an undeclared residue is the next
// leak:
//
//   1. `app/(blog)/services/page.tsx:353` — "WhatsApp or Visa Check for a
//      first read — free, under 15 min." Whether "first read" is a reply-time
//      promise or a scope promise is an OWNER call that has not been made.
//      It is not removed and no pattern is aimed at it. If the owner rules it
//      a claim, the pattern belongs beside Pattern 10, not in a widened
//      Pattern 1.
//   2. `fr.json` / `ru.json` get no per-language ruleset. The measurement that
//      stood here EXPIRED, and it is worth naming how: it read "2026-08-24:
//      188 string leaves each … neither carries `secondHome.cta.note` at all,
//      so there is nothing to remove today". Six days later `2306023b1`
//      (#5381, 2026-08-30 22:18 UTC) added that key to both locales, claim
//      included — a frozen measurement quietly became a false statement.
//      Re-measured 2026-08-31: 259 string leaves each, both carrying the
//      claim; this commit removes it from both by hand. Neither file was ever
//      reachable by this guard — the imports above name en/it/id only, and
//      the walk could not have reached them either (see the SCANNED note
//      above). So nothing is left to remove today, but a reply-time claim
//      written in French or Russian still passes unseen. Closing that means
//      two more rulesets, their guilt fixtures, and two more imports — a
//      round of its own, filed rather than fixed here.

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

  it("guilt: it catches every shape that was actually served", () => {
    for (const served of [
      // shipped on the homepage until 2026-08-18
      "          <span>Avg reply: 2 min</span>",
      "          Chat with us — avg reply: 2 min",
      "  <span>Avg. reply: 2 min</span>",
      "  <p>Average response: 2 minutes</p>",
      "  <p>Typical reply: 2 min</p>",
      // identifier forms — no space for a word-spaced pattern to land on
      "export const AVG_REPLY_MINUTES = 2;",
      "export const AVG_REPLY = '2 min';",
      // removed 2026-08-18 (PR #4178), at the file:line each was measured at
      "Typical first reply on WhatsApp in under 5 hours.",
      "<span>Usually within 15 minutes.</span>",
      'note: "Fastest response — usually under 15 minutes.",',
      "Messages are typically responded to within 24 hours",
      // removed 2026-08-20, once packages/core was opened. They sat in a
      // DECLARED GAP block until now because the tuple arity and a required
      // prop made them unremovable from apps/mouth alone.
      '            { value: "4.8h", label: "avg first-reply on WhatsApp" },',
      "      trust={{ clientCount: 5000, rating: 4.9, responseMinutes: 15 }}",
      "  responseMinutes: number;",
      // removed 2026-08-24 — still SERVED on 8ccd7d2b8 at the file:line each
      // was measured at. The first three are one claim in three languages;
      // English-only patterns caught only the first.
      '      "note": "Typical first reply on WhatsApp in under 5 hours."',
      '      "note": "Prima risposta su WhatsApp in genere entro 5 ore."',
      '      "note": "Balasan pertama di WhatsApp biasanya kurang dari 5 jam."',
      '        description="Fixed fee, processed in ~14 days. Start on WhatsApp — we\'ll pick up in under 5 hours."',
      // caught by the first version, must not regress
      "  <p>We reply within 5 minutes</p>",
      "  <p>Our team responds in 2 minutes</p>",
      "  <span>Reply time: 2 min</span>",
    ]) {
      expect(
        [...CLAIMS, ...CLAIMS_IT, ...CLAIMS_ID].some((re) => re.test(served)),
        `no pattern caught: ${served}`,
      ).toBe(true);
    }
  });

  it("innocence: it does not fire on the durations that are not claims", () => {
    // Every string here is real code from this app, quoted at the file:line it
    // was measured at. A guard that trips on a Tailwind class or a poll
    // interval teaches the next person to delete it.
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
      // Machine latency on an internal dashboard — app/(workspace)/analytics/
      // page.tsx:349,745,829,1160,1172. "Avg" and "Response" both appear; the
      // subject is a server and no promise is made to a reader.
      '                <p className="text-xs text-[var(--bz-text-2)]">Avg Latency</p>',
      '                    <span className="text-[var(--bz-text-2)]">Avg Latency</span>',
      "                Response Times (Percentiles)",
      "    avg_latency_ms: number;",
      "                    {data.system.response_time_p95.toFixed(0)}ms",
      // Timers and animation, not promises.
      "    const interval = setInterval(fetchHealth, 5000); // Poll every 5s",
      "    const interval = setInterval(loadData, 60000);",
      "  pollIntervalMs = 30000,",
      "      setTimeout(() => setCopied(false), 2000);",
      "// Edge has a 30s timeout which kills workspace-stream responses.",
      "      const responseTime = performance.now() - startTime;",
      '                      className="object-cover transition-transform duration-700 group-hover:scale-105"',
      '          <h1 className="animate-in fade-in slide-in-from-bottom-4 duration-500 delay-100">',
      // A button label — app/portal/(authenticated)/_components/TimelineItem.tsx:193.
      '            Reply <ChevronRight className="w-3 h-3 ml-1" />',
      // The Visa Oracle stat card — app/v2/_components/FunnelBoxes.tsx:20.
      // "<3s" is the AI assistant's latency, not a person answering a customer;
      // same distinction as the SLO above. Whether <3s was ever measured is a
      // separate question from whether this guard should fire on it.
      '      { l: "Avg response", v: "<3s" },',
      // Survives on the contact page after the 15-minute promise was removed:
      // a reply word with no duration attached is not a claim.
      "            No bots in the first reply. WhatsApp is the fastest channel —",
      // Pattern 10's neighbours. A collection time is not a reply time, and
      // the object between "pick up" and "in" is what tells them apart.
      "You can pick up your passport in 3 days.",
      "We can pick up your documents in 2 days.",
      "Our team will pick up the file from the notary.",
      "Pick up the conversation where you left it.",
    ]) {
      const fired = [...CLAIMS, ...CLAIMS_IT, ...CLAIMS_ID].filter((re) =>
        re.test(innocent),
      );
      expect(fired.length, `fired on: ${innocent}`).toBe(0);
    }
  });

  // ── the i18n surface the walk cannot reach ──────────────────────────────
  describe("no locale dictionary promises a reply speed", () => {
    it("sees a plausible number of strings in each dictionary", () => {
      // A dictionary that failed to import, or a `leaves` walk that broke,
      // would let every assertion below pass by looking at nothing.
      for (const { locale, messages } of DICTIONARIES) {
        const out: [string, string][] = [];
        leaves(messages, [], out);
        expect(out.length, `${locale} dictionary looks empty`).toBeGreaterThan(
          100,
        );
      }
    });

    for (const { locale, messages, patterns } of DICTIONARIES) {
      it(`INNOCENCE (${locale}): the current dictionary makes no reply-time claim`, () => {
        // Reported verbatim with its key path — vetted copy is never silently
        // "fixed" from inside a test file.
        expect(sweep(messages, patterns)).toEqual([]);
      });
    }

    it("GUILT: the claim that was served is caught in all three languages", () => {
      const planted = {
        en: {
          secondHome: {
            cta: { note: "Typical first reply on WhatsApp in under 5 hours." },
          },
        },
        it: {
          secondHome: {
            cta: { note: "Prima risposta su WhatsApp in genere entro 5 ore." },
          },
        },
        id: {
          secondHome: {
            cta: {
              note: "Balasan pertama di WhatsApp biasanya kurang dari 5 jam.",
            },
          },
        },
      };
      expect(sweep(planted.en, CLAIMS)).toHaveLength(1);
      expect(sweep(planted.it, CLAIMS_IT)).toHaveLength(1);
      expect(sweep(planted.id, CLAIMS_ID)).toHaveLength(1);
    });

    it("INNOCENCE: neighbouring vetted copy does not trip the per-language sets", () => {
      // Real strings from these same dictionaries. Each contains the reply
      // word (reply / rispondiamo / balas) with NO duration attached — which
      // is the whole distinction the patterns are built on.
      const clean = {
        en: "Tell us your situation on WhatsApp. We reply with an honest read.",
        it: "Ti rispondiamo con una valutazione onesta: quale percorso conviene.",
        id: "Kami balas dengan penilaian jujur: jalur mana yang cocok.",
      };
      expect(sweep({ a: clean.en }, CLAIMS)).toEqual([]);
      expect(sweep({ a: clean.it }, CLAIMS_IT)).toEqual([]);
      expect(sweep({ a: clean.id }, CLAIMS_ID)).toEqual([]);
    });
  });
});
