"use strict";

/**
 * The grammar that decides whether an inbound message is a web lead.
 *
 * It lives in one module because three call sites need the same answer — the
 * conversation list, the aggregate endpoint, and the tests — and a grammar
 * copied per call site drifts until two of them disagree about who is a lead.
 *
 * It must also agree with `scripts/lead_intent_matcher.py`, which is the organ
 * that actually attributes a lead to a client. The Python side owns the
 * authoritative regex (`_LEAD_ID_RE`); this is its Postgres spelling.
 *
 * WORD BOUNDARIES ARE LOAD-BEARING. The matcher's cheap prefilter,
 * `strpos(body,'li_') > 0`, is a substring test, and ordinary Indonesian and
 * Italian prose contains those three characters. Measured on the live mirror
 * 2026-08-06: the loose predicate returns 7 rows, the word-bounded one returns
 * the 4 real tokens. On a dashboard the difference is not cosmetic — a false
 * positive labels somebody's private conversation as a web lead.
 */

// `\m` and `\M` are Postgres' start/end-of-word assertions, and Postgres must
// receive exactly ONE backslash before each. In JS source that is written
// "\\m", which is the two characters \ and m — embedding this in a template
// literal does not re-escape anything.
//
// Getting this wrong is silent in both directions, so it was measured rather
// than reasoned. Against the live mirror 2026-08-06, with `standard_conforming
// _strings` on (the default), the predicate matched:
//     '\\mli_…\\M'  (two backslashes) → 0 rows   ← every lead unbadged, no error
//     '\mli_…\M'    (one  backslash)  → 4 rows   ← the real tokens
// The first version shipped in this file and its unit test passed, because the
// test asserted the shape of the JS literal instead of what Postgres receives.
const TOKEN_REGEX_SQL = "\\mli_[a-z0-9]{6,20}\\M";

// The text a message really carries: the mirror leaves `body` empty on some
// rows and puts the content in `message_text`. Reading only `body` silently
// loses those, which is how a lead disappears without any error anywhere.
const MESSAGE_TEXT_SQL = "COALESCE(NULLIF(body, ''), message_text)";

// Two prefill formats are live in the historical data. The newer one adds a
// fine-grained `Source:` line; the older one only has the sentence. Requiring
// `Source:` would drop 3 of the 4 real leads, so the sentence is the fallback,
// not the other way round.
const SURFACE_SQL = `COALESCE(
  substring(${MESSAGE_TEXT_SQL} from 'Source: ([^\\r\\n]+)'),
  substring(${MESSAGE_TEXT_SQL} from 'I just used the ([a-zA-Z ]+) on your site')
)`;

const IS_LEAD_SQL = `COALESCE(${MESSAGE_TEXT_SQL}, '') ~ '${TOKEN_REGEX_SQL}'`;
const TOKEN_SQL = `substring(${MESSAGE_TEXT_SQL} from '${TOKEN_REGEX_SQL}')`;

// Mirror of the same grammar for anything decided in JS rather than SQL.
const TOKEN_REGEX_JS = /\bli_[a-z0-9]{6,20}\b/;

/** True when `text` carries a deeplink lead token. */
function isLeadText(text) {
  return typeof text === "string" && TOKEN_REGEX_JS.test(text);
}

module.exports = {
  TOKEN_REGEX_SQL,
  TOKEN_REGEX_JS,
  MESSAGE_TEXT_SQL,
  SURFACE_SQL,
  IS_LEAD_SQL,
  TOKEN_SQL,
  isLeadText,
};
