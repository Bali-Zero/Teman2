# Pricing search token matching (PricingService.search_service)

Status: spec, 2026-10-17. Owner surface: `apps/backend-rag/backend/services/pricing/pricing_service.py`
(`PricingService.search_service`). Consumers: `/api/pricing/search`, Zantara's PricingTool, and the
WhatsApp bot's price context, which passes the client's whole message
(`backend/services/whatsapp/wa_package_builder.py` around line 717).

## Why

The search splits the query on whitespace, drops a noise-word list and one-character tokens, and
includes a row when ANY remaining token is a SUBSTRING of the row text (key, name, notes,
description_en, legacy_names, keywords). Two consequences, both measured by independent gates:

- Generic words in a keyword phrase widen every query that contains them: the keyword
  "izin minuman beralkohol" made "izin tinggal", "izin usaha", "izin" return the alcohol licence
  rows (#8632, blocked). Removing that keyword (#8633) cured "izin", but "minuman" alone still pulls
  them ("izin usaha minuman ringan" 0 → 3, "PIRT minuman" 1 → 4).
- Short tokens match inside unrelated words: "ke" inside "keras", "mi"/"as" inside "miras",
  "ma"/"man" inside "minuman", "ber" inside "beralkohol" ("berapa biaya NIB ke OSS" 21 → 24).

Two corrections on the catalog side have already been made on this surface; per the PR contract
(fix-of-a-fix stops at depth 1) the cure is a matching rule, not another keyword edit.

## Rule

Normalise the query and the row text the same way: lower-case, Unicode word tokens
(`re.findall(r"\w+", text)`), so punctuation and `+`, `—`, `(`, `)` separate words.

1. **Descriptive text** (key, name, notes, description_en, legacy_names) matches a query token by
   WORD, not by an arbitrary substring. A token matches a row word when:
   - it equals the word; or
   - it is a PREFIX of the word and has at least 3 characters or contains a digit ("ext" →
     "extension", "kit" → "kitas", "visa" → "visas", "e33" → "e33g"; "ke" no longer → "keras");
   - the word is a PREFIX of the token, has at least 4 characters, and the remainder of the token
     is one of a small closed set of light suffixes (`_LIGHT_SUFFIXES`, EN/ID/IT: "kitasnya" →
     "kitas", "visas" → "visa", "alcoholic" → "alcohol"; "freelance" does NOT → "free"); or
   - it occurs INSIDE the word and has at least 5 characters (Indonesian circumfixes and
     cross-language roots: "polisi" → "kepolisian", "sehat" → "kesehatan", "igiene" → "higiene").
     Tokens of 1-2 characters therefore match whole words only.
2. **`keywords`** are curated terms and never match by a word they merely share with the query:
   - a MULTI-WORD keyword matches only as a contiguous word sequence contained in the query
     ("minuman ringan" does not match "minuman beralkohol"; "izin minuman beralkohol" does);
   - a SINGLE-WORD keyword matches a query token that equals it, that it prefixes (keyword of 4+
     characters, remainder in the same closed suffix set: "pensiunan" → "pensiun",
     "beralkoholnya" → "beralkohol"), or that prefixes it
     with at least 4 characters ("pensi" → "pensiun"; "ber" does NOT → "beralkohol"); never by
     the inside-the-word clause.
     Curated keywords must therefore carry the distinctive single words a client actually types
     (for the alcohol rows: "alkohol", "beralkohol"), never a generic one ("izin", "minuman").
     The three Alcohol License rows also carry the English, Italian and Indonesian distinctive words
     `liquor`, `beer`, `wine`, `alcol`, `alcolici`, `alcolico`, `bir`, and (owner ruling 2026-10-17) `bar`,
     `birra`, `vino`, `minol` (`bar` has three characters, so it matches by equality only: "bars" does not) (after #8655's gate, council of the
     licence-noise PR: "liquor license" lost its only bridge once `license` became noise); `spirit` is
     deliberately absent ("spirit festival" would over-match); the multi-word keywords
     `spirits license` and `spirits licence` cover that phrase only as a contiguous phrase.
     Revised 2026-10-17 after the council (codex-gpt-5.6-sol, agy-gemini-4-argon) measured recall
     losses of the first draft: "berapa biaya izin alkohol", "harga izin beralkohol", "alkohol",
     "polisi", "sehat", "certificato igiene", "voa ext", "kit", "pensi", "kitasnya".
3. **Noise words** keep their role and gain the short function words that the word rule alone
   would still let through as whole words in English/Indonesian/Italian descriptions (at least:
   `ke`, `di`, `dan`, `yang`, `untuk`, `dari`, `the`, `to`, `in`, `for`, `as`, `is`, `on`, `at`,
   `mi`, `ma`, `si`, `ci`, `lo`, `che`, `quanto`, `costa`, `berapa`, `biaya`, `harga`, `price`,
   `cost`, `how`, `much`) and the generic licence/sale words `license`, `licence`, `licensing`,
   `sell` (they sit in the Alcohol License row names and would otherwise let "licenses" or "selling"
   pull them). A query token is noise when it equals a noise word, or a noise word of 4+ characters
   plus a light suffix of rule 2 ("prices", "biayanya", "selling"), so inflected noise follows the
   same rule as row matching. `permit` and `izin` are NOT noise. The implementation measures before adding each one (rule 5) and does not
   add a word that is the only token of a legitimate single-word query in the corpus.
4. The one-character-token drop and the "all tokens were noise → use the raw query" fallback stay;
   the fallback uses the same matcher, after dropping the generic trade words of rule 3 (`license`,
   `licence`, `licensing`, `sell` and their inflections), so a query made only of those words and
   other noise words matches no row. The legacy LIST-format branch uses the same matcher.
   Result shape, ordering and the internal-row exclusion are unchanged.
   **Aliases.** A tiny curated map (`_TOKEN_ALIASES`) expands an acronym a client types into extra
   target words the old substring match found by accident: itas → kitas, itap → kitap, tka →
   rptka. Added only for genuine domain variants found by the single-token sweep.
   **Hyphen compounds.** A hyphenated query word ("re-entry", "pt-pma") is ONE term that matches
   only as a contiguous phrase of its parts in the row's word sequence (last part may take the
   usual prefix/light-suffix forms), never part by part.
   **Negators.** The single word after `non`, `tanpa`, `senza`, `without` is dropped from the
   query ("minuman tanpa alkohol"); a hyphen compound starting with a negator
   ("non-alcoholic") is dropped whole.
   **Empty query.** An empty or whitespace-only query returns no rows (the old code returned
   every row). No caller relies on all-rows: `/api/pricing/search` requires `min_length=1`, the
   tools and the WhatsApp builder search a non-empty client message, and `get_all_prices` lists
   everything; pinned by a test.
5. **Proof by corpus, both directions.** A committed query corpus (≥ 60 queries: EN, ID, IT;
   single words, codes, whole WhatsApp-style sentences) with, per query, the row names that MUST
   appear and the row names that MUST NOT appear. It includes at least:
   - must find: "alcohol license", "izin minuman beralkohol", "harga izin minuman beralkohol",
     "miras", "minuman keras" → the three Alcohol License rows; "SLHS", "halal certificate", "PIRT"
     → their rows; "kitas", "e33", "E33G", "c1", "B1 voa", "PT PMA", "virtual office",
     "pensiun" (E33F keywords), "driving license"/"SIM" if a row exists, every query that the
     existing tests already pin; and the council's recall cases: "berapa biaya izin alkohol",
     "harga izin beralkohol", "alkohol", "beralkohol", "minuman yang beralkohol",
     "izin minuman beralkoholnya berapa" → alcohol rows; "polisi"/"catatan polisi" → SKCK;
     "sehat" → BPJS Kesehatan; "certificato igiene" → SLHS; "voa ext" → the B1 VOA extension row;
     "kit", "kitasnya" → KITAS rows; "pensi", "pensiunan" → E33F rows; "visas" → visa rows;
   - must not find Alcohol License rows: "izin tinggal", "izin kerja", "izin usaha", "izin edar",
     "izin", "berapa biaya izin usaha restoran?", "izin usaha minuman ringan", "PIRT minuman",
     "berapa biaya NIB ke OSS", "harga visa ke bali", "mi serve un visto, quanto costa?",
     "ma quanto costa una PT PMA?", "SLHS as a restaurant" (SLHS yes, alcohol no).
     The PR reports a before/after table of hit counts for the whole corpus; every row LOST by a
     query that found it before must be listed and justified, or it is a defect.

## Out of scope

Ranking/scoring of results, the Qdrant semantic search (`bali_zero_pricing_hybrid`), catalog
content, the English "license" over-match (e.g. "driving license" → alcohol), which rule 3's
noise words now cure ("driving license" → no Alcohol License row; the Driving License row itself
was retired by #8658).

Accepted and documented, not fixed (council 2026-10-17, v4):

- Plural stemming hits that are semantically right but contextually off ("send your addresses",
  "Chrome extensions").
- A query whose every word is noise falls back to the raw-query path, so "prices" ALONE still
  returns the rows that carry that word. The generic trade words of rule 3 ("license", "licenses",
  "selling" ...) are dropped from that fallback (owner ruling 2026-10-17), so they alone match no row.
- "toko minuman" / "jualan minuman ringan" no longer return the alcohol rows: "minuman" alone is
  generic, by design.
- Typos such as "seha" do not match.

Revised 2026-10-17 (v4) after the council on `ea6a7c52bf` (codex-gpt-5.6-sol: CONCERNS on
ITAS/ITAP/TKA recall, hyphen compounds and negation; kimi-code/k3: PASS).

Revised 2026-10-17 after #8655's gate: noise words stem like row words; `license`, `licence`,
`licensing`, `sell` joined the noise list (rule 3).

Revised 2026-10-17 by owner ruling: a bare generic licence/sale word is not an alcohol question
(the all-noise fallback drops it, rule 4) and the Alcohol License rows carry `bar`, `birra`, `vino`,
`minol` (rule 2).
