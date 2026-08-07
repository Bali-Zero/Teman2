"use strict";

/**
 * The web-lead grammar, and the false positive it exists to prevent.
 *
 * Ari's WhatsApp line carries our inbound web leads AND his own working
 * traffic. The badge that tells them apart is driven entirely by this grammar,
 * so a match that is too loose does not merely inflate a counter — it labels a
 * private conversation as a web lead on a screen the team reads.
 *
 * Guilt and innocence are both asserted, because a guard that only proves it
 * bites has never proved it bites the right thing.
 */

const assert = require("node:assert/strict");
const webLead = require("./web-lead-sql.cjs");

// ── guilt: the four real tokens this system has ever received ───────────────
// Measured on the live mirror 2026-08-06. If a grammar change rejects one of
// these, a real lead stops being badged and nothing anywhere reports an error.
for (const token of ["li_p7nz6ul6rq", "li_pgzr0j2494", "li_7bw3gte2x4", "li_wd5mklrxpk"]) {
  assert.equal(webLead.isLeadText(`Hi Bali Zero — Lead ID: ${token}`), true, `must match ${token}`);
}

// Guilt: the token is found wherever it sits in the message, since the lead may
// type ahead of the prefilled text rather than replacing it.
assert.equal(webLead.isLeadText("halo, saya mau tanya\n\nLead ID: li_p7nz6ul6rq"), true);

// ── innocence: prose that merely contains the three characters ──────────────
// This is the whole reason for the word boundaries. The matcher's cheap SQL
// prefilter (strpos 'li_') returned 7 rows on this mirror where only 4 were
// leads; the other 3 were ordinary messages. Badging them would be a lie about
// a real person's conversation.
for (const text of [
  "li_",
  "kali_belum sempat",       // Indonesian
  "li_ab",                    // too short to be a nanoid
  "gli_impegni di domani",    // Italian
  "LI_ABC123XYZ",             // wrong case — the minter only emits lowercase
  "xli_abc123def",            // no word boundary on the left
]) {
  assert.equal(webLead.isLeadText(text), false, `must NOT match: ${text}`);
}

// Innocence for the helper itself: non-strings must not throw or match.
assert.equal(webLead.isLeadText(null), false);
assert.equal(webLead.isLeadText(undefined), false);
assert.equal(webLead.isLeadText(42), false);

// ── the SQL spelling: word-bounded, and escaped as POSTGRES will read it ────
// The first version of this file doubled the backslashes and its test passed,
// because the test described the JS literal rather than the bytes Postgres
// receives. Live, that predicate matched 0 rows instead of 4: every lead went
// unbadged and nothing raised an error. So these assertions are written about
// the string's actual characters.
assert.ok(
  webLead.TOKEN_REGEX_SQL.startsWith("\\m"),
  "must open with a single-backslash \\m — Postgres reads \\\\m as a literal backslash",
);
assert.ok(webLead.TOKEN_REGEX_SQL.endsWith("\\M"), "must close with a single-backslash \\M");
assert.equal(
  webLead.TOKEN_REGEX_SQL.includes("\\\\"),
  false,
  "a doubled backslash silently matches nothing at all",
);
// And the rendered predicate — what actually reaches the driver — carries it.
assert.ok(webLead.IS_LEAD_SQL.includes("\\m"), "the rendered predicate lost the word boundary");
assert.equal(webLead.IS_LEAD_SQL.includes("\\\\"), false, "rendered predicate has doubled escapes");
assert.equal(webLead.IS_LEAD_SQL.includes("strpos"), false, "must not fall back to substring matching");

// The text expression must read the mirror's fallback column: rows with an
// empty `body` keep their content in `message_text`, and reading only `body`
// loses those leads silently.
assert.match(webLead.MESSAGE_TEXT_SQL, /message_text/);
assert.match(webLead.IS_LEAD_SQL, /message_text/);

// The surface must survive the OLDER prefill format, which has no `Source:`
// line — 3 of the 4 real leads are that shape. If `Source:` were required
// rather than preferred, they would all report as unlabelled.
assert.match(webLead.SURFACE_SQL, /I just used the/);
assert.match(webLead.SURFACE_SQL, /Source: /);

console.log("web-lead-sql: OK");
