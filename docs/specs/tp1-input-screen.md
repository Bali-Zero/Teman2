# TP1 input screen — specification

Status: normative design for the next implementation (PR-C: the screen, PR-D: `build_verify_queue.py`).
It specifies decisions as entities, not a particular regex or library. The executable examples are
`scripts/tp1max/screen_corpus.yaml`; `scripts/tp1max/test_screen_corpus.py` keeps that corpus valid in CI.
Why it exists: the final gate blocked the screen three times (#7927 B1: 31 leaked shapes; #7971 B1: 16;
#7971 B1-r2: 12), each time on shapes nobody had written down. A cure at depth 2 is a spec, so here it is.

## Threat model

1. What leaves: the bytes of every queued file, its repository-relative path, and the prompt built from them.
2. To whom: a paid third-party model API (the TP1 plan), outside Nuzantara's trust boundary.
3. Never leaves: credential values; client PII — phone numbers in any grouping or reversible encoding, personal e-mail addresses, national-ID and passport numbers, personal names in CRM-like records.
4. May leave: ordinary source, exact role mailboxes on the project's own domains, RFC-reserved example addresses, prose that names a secret family without a value.
5. The screen decides on entities and context, fails closed, and counts every refusal; a public repo is no exception to the output boundary.

## Contract and decision order

The screen judges one candidate: `(path, bytes)` read from the working tree at build time — the bytes
that would leave, not the committed blob. It returns `queue` or `skip(reason)`. Order: structural
checks; bounded read; UTF-8 decode; decoded views; credential rules; PII rules. The first reason wins.
The path is screened as text together with the content, because it leaves in the job id and the prompt.

Builder policy is separate from the screen: candidate selection (`EXT`, `ROOTS`, `SKIP_PATH`, counted as
`excluded_path`) and the `MIN_CHARS` floor (counted as `short`). Corpus content rows are judged at the
screen entry point, never through `MIN_CHARS`; the path string `src/<id>.txt` (or `setup.path`) is part of the screened text.

The verdict must be identical on Python 3.9 and 3.11 with only declared dependencies. An optionally
installed detector must not change it (the #7971 Codex build did exactly that; the plugin layer was reverted).

### Literals, references and placeholders

A **literal** is a concrete scalar: quoted, after `=` or `:`, in a credential-bearing CLI slot, or in a
URI authority. Not a literal: a shell variable or `${…}`/`{…}` interpolation, `$(…)` command
substitution, a function call or attribute reference, an environment read, a type or class name, and a
value that is WHOLLY a placeholder (`<…>`, `redacted`, `example`, `dummy`, `fake`, `placeholder`,
`changeme`, `YOUR_…`). The placeholder test is on the complete value: a family token that merely
contains `xxxx` or `example` stays guilty (`kimi_34`, `kl_05`), and a run of one repeated character is
not a placeholder — that is how fixtures write tokens. An empty literal is not a value. A template or
concatenation is innocent only when every credential slot in it is a reference: a literal fragment in a
credential slot (`f"postgresql://app:<literal>@{host}"`, `c1_07`) is a literal.

## Credential entities (reason `secret`)

### Named assignments

The entity is `NAME <op> literal` in any of: `NAME = lit`, `NAME: lit`, `"NAME": "lit"`, `NAME=lit`,
`export NAME=lit`, keyword argument `name="lit"`, `.npmrc` `//host/:_authToken=lit`. The name is
normalised (case-folded, camelCase and `-` split into `_` segments); the rule reads its LAST segments.

| Tier | Name ends in                                                                                                                                     | Guilty literal                                                                                                                              | Innocent counterpart                                                                                                                         |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| P    | `PASS`, `PASSWD`, `PASSWORD`, `PASSPHRASE`, `PWD`, `PW`                                                                                          | any non-empty literal, any length, quoted or not, letters-only included (`DB_PASS`, `MYSQL_PWD`, `DRILL_PW`)                                | empty literal; number or boolean; a status word equal to a name segment or in {pass, passed, fail, failed, ok, skip} (`STATE_PASS = "pass"`) |
| S    | `SECRET`, `TOKEN`, `AUTH_TOKEN`, `API_KEY`, `APIKEY`, `ACCESS_KEY`, `SECRET_KEY`, `PRIVATE_KEY`, `SIGNING_KEY`, `CLIENT_SECRET`, `CREDENTIAL(S)` | ≥ 16 characters mixing letters with a digit or non-letter, or ≥ 32 hex digits                                                               | `token_type = "Bearer"`, `token_status` (last segment is not in the tier); references; `$(…)`                                                |
| K    | any other `KEY` except `PUBLIC_KEY`/`PUB_KEY`/`PUBKEY`                                                                                           | an opaque run: ≥ 32 hex digits, or ≥ 20 characters of the base64/base64url alphabet with a letter and a digit and no `:`, `.`, `/` or space | `CACHE_KEY = "session:user-profile:v2"`; settings references; public keys                                                                    |

A family signature (next section) overrides every length and tier condition.

**Value placement.** The literal may sit on the same line, or on the NEXT logical line after a
trailing `:` (`password:` then an indented `pw`), after a YAML block-scalar indicator (`|` or `>`, optional
`-`/`+` chomping: the first indented line, also inside a heredoc, `c1_08`), or after a trailing `=`
(one newline, optional indentation: `r2x_01`). The next-line case never takes a docstring opener, a line ending in `:`, a `def`/`class`
line, or a mapping/tuple item as the value (`class TokenUsage:` + docstring is innocent).

**Annotations.** After `:` in code, an unquoted value that is a builtin type name (`str`, `int`,
`bytes`, `bool`, `float`, `dict`, `list`, `Any`, `None`, `object`) or a CamelCase identifier,
optionally followed by `[…]`, `=`, `|` or `.attr(…)`, is an annotation or reference
(`private_key: Ed25519PrivateKey`, `private_key = Ed25519PrivateKey.generate()`). Any other unquoted
value after a Tier P/S/K name is a literal (`password: letmein`, same line, is guilty).

### Credential-bearing contexts

Guilty when the operand is a literal; quoting, `=` versus space, and glued short options do not change
the entity. A quoted operand extends to its closing quote or the end of the line, with no length cap
below the file cap, and may contain spaces (`kl_01`–`kl_03`).

- `-p<pw>` / `-p <pw>` after `mysql`, `mysqldump`, `sshpass`, `docker login`; `--password`,
  `--passwd`, `--http-password`, `--ftp-password`, `--proxy-password`;
- `-u user:pw`, `-uuser:pw`, `--user user:pw`, `--user=user:pw` (curl/wget style);
- `.netrc`: `login … password …` on one line or `password` as its own directive line; `.pgpass`:
  a five-field `host:port:db:user:password` row whose port is digits or `*` and whose user/password are not numeric;
- `Authorization` / `Proxy-Authorization`: `Basic|Bearer|Token <literal>`, header or mapping syntax;
- `auth=(user, password)` and equivalent literal two-tuples passed as `auth`;
- an HTTPS `git clone` URL and `postgres(ql)`, `redis(s)`, `mongodb(+srv)` URLs whose user-info
  holds a literal password or token, of any length (one character included).

Innocent: the same syntax with a variable, template or placeholder operand; prose naming an option
without an operand (an option at the end of a line or followed only by punctuation); `date -u +%Y…`; an all-numeric colon list (`7880:7881:7882:50000:60000`); a URL with
no user-info or a `{pwd}` template; `Authorization: Bearer YOUR_JWT_TOKEN`.

### Credential families

Bounded, complete entities with token boundaries, not prefixes anywhere: a prefix followed by ≥ 20
characters of `[A-Za-z0-9_-]` up to a non-alphabet character, unless stated otherwise — AWS ids exactly
16 `[A-Z0-9]`; Google `AIza` + 35; Telegram 8–10 digits, `:`, 35 characters; SendGrid `SG.` + 22 + `.` + 43;
Discord `discord(app).com/api/webhooks/` + 17–20 digits + `/` + ≥ 30 token characters; Slack
`hooks.slack.com/services/T…/B…/` + ≥ 20 characters (each path segment is its own grammar).
Required: GitHub `ghp_`,
`gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`; GitLab `glpat-`; npm `npm_`; Stripe `sk_live_`/`rk_live_`
and `whsec_`; OpenAI `sk-` (incl. `sk-proj-`); Brevo `xkeysib-`; SendGrid `SG.<22>.<43>`; HuggingFace
`hf_`; Slack `xox[abprs]-` and `hooks.slack.com/services/`; Discord webhook URLs; Telegram
`<bot id>:AA…`; Google `AIza`, `GOCSPX-`, `ya29.`; AWS `AKIA`/`ASIA` ids and 40-character secret
values under an AWS secret name (assignment or JSON key); Fly `FlyV1`, `fm1_`, `fm2_`, `fo1_`; age
`AGE-SECRET-KEY-1`; Azure `AccountKey=`. Every family here has its own corpus row; a family joins this
list only together with its row. PEM private keys: header in any case, LF, CRLF or `\n`-escaped; a header alone is
sufficient; a headerless body is guilty under a Tier S name. A PEM PUBLIC key block is innocent.
JWT: three base64url segments of 8–8192 characters each, the first starting `eyJ`, matched in linear time.

## Decoded views

Every credential and PII rule runs on a constant set of views: raw; one URL-unquote pass; `\uXXXX`,
`\UXXXXXXXX`, `\xXX` unescape; HTML entities (numeric and named); URL-unquote then HTML. For the
e-mail rule only, `[at]`/`(at)`/`{at}` and `[dot]`/`(dot)` are also normalised.

Base64: a candidate is a run of ≥ 16 characters of the standard or urlsafe alphabet, optional `=`
padding. Consecutive lines that are pure base64 and all but the last of equal length (the 64- or
76-column wrap) are joined first, so a credential across a wrap is one entity (`g7971r2_10`). The whole
candidate is decoded (no prefix window: `kimi_21`), read as latin-1, C0/C1 control characters except
tab/CR/LF deleted (`kl_04`: a NUL inside the name), and screened by the same rules. Decoding recurses to
a total depth of TWO layers (`normative_11`); a malformed candidate yields no view and the raw text is
still screened. Each layer is at most 3/4 of its input, so total work stays below 2.4·n.

## PII entities

### Phones (reason `phone`)

Normalise Unicode decimal digits to ASCII (NFKC; fullwidth included). Separators: ASCII and Unicode
spaces incl. NBSP, `(`, `)`, `.`, `/`, `-`, U+2010–U+2015, and at most one newline plus indentation.
Separators split the digit stream into GROUPS. A candidate starts at a group boundary that is not
preceded by a digit (a letter, `_` or punctuation may precede it: `phone628…`, `WA_NUMBER_62…`) and
spans consecutive groups up to 15 digits; every group-aligned prefix is tested, so a trailing year or a
second number (`… / 0813…`) does not hide the first. Markers: `+` glued to the first digit or inside
`(+62)`; `00` followed by a country code `[1-9]`; `tel:`, `wa.me/`, `@s.whatsapp.net`; a phone label
(`phone`, `tel`, `hp`, `wa`, `whatsapp`, `mobile`, `contact`) attached to the value.

Guilty shapes: Indonesian mobile `08` + 8–11 digits, `628`/`+628`/`00628` + 8–11, and `62 (0)8…` /
`+62 (0)8…` with the `(0)` dropped; Indonesian landline `0[2-7]` + 7–10 more digits, or the same after
`+62`; international `+`/`00` + country code with 8–15 digits in total.

Innocent, checked BEFORE phone matching and removed from the stream: dates and times (`YYYY-MM-DD`,
`DD-MM-YYYY`, `DD/MM/YYYY`, `YYYY.MM.DD` with valid month/day, optional `HH:MM[:SS]`, ISO 8601);
amounts `[+-]?\d{1,3}([.,]\d{3})+` with one uniform separator (`+15.000.000`); a sign after a separator
starts a new entity (`+1234/-5678`). The amount exemption never applies to a stream that starts
with an Indonesian mobile prefix (`+62.812.333.444` is a phone: `c1_03`); a `+` followed by a space is arithmetic (`Opus + 2026-09-23`).
Not phones by shape: versions, dotted IPs, UUIDs, SHAs, epochs, ISBNs, coordinates, ports, KBLI codes,
SVG path data (letters split the groups), a long id whose run does not START with a phone prefix
(`9912081200001234`), and a prefix alone in prose (`+62 or 08`).

### E-mail (reason `email`)

Recognise addresses in every view, including quoted local parts and punycode/Unicode domains. An
address may leave only if it is one of:

1. an exact role local — full match, after stripping one `+tag` — in {zantara, noreply, no-reply, info,
   admin, test, support, hello, contact, team, ops, dev, bot, notification, notifications, alert,
   alerts} on `balizero.com`, `zantara.io`, `nuzantara.com` or their subdomains;
2. an exact vendor no-reply ADDRESS on a short list (today: `noreply@anthropic.com`, the
   `Co-Authored-By` trailer) — the address is listed, never its domain;
3. any address under RFC 2606/6761 names (`example.com/.net/.org`, `.example`, `.test`, `.invalid`, `localhost`).

Everything else is guilty: role locals on any other domain (`info@` on a client domain), every
personal-looking local on an own domain, a role word used as a PREFIX (`infosynthetic@`: the rule is a
full match, never a prefix match).

### National IDs (reason `id_number`) and CRM-like names (reason `crm_name`)

`id_number`: a 16-digit NIK/KTP/KK, a 15–16-digit NPWP (with or without its `.`/`-` formatting: `c1_09`)
or a passport number (one letter + 7 digits) attached to a key or label `nik`, `ktp`, `no_ktp`,
`nomor_ktp`, `kk`, `npwp`, `passport`, `passport_no`, `paspor`. `crm_name`: a string literal of 2–6
words, each starting with a letter, under a key `name`, `full_name`, `nama`, `client_name`,
`customer_name` or `contact_name`, in a record whose other keys name a client/customer/contact/lead/stage
or hold a phone or e-mail field (`normative_10`).
Innocent: class names, authorship prose, personas under reserved domains, ordinary identifiers.
This screen is not a general named-entity recogniser; see the declared limits.

## Structural entities and failure behaviour

- `excluded_path`: the builder's `SKIP_PATH` (tests, fixtures, data, content, `.env`…); counted, never silent.
- `unsafe_path`: a path that is not printable ASCII, or holds a newline/control character, or does not
  decode as UTF-8 from `git ls-files -z`. Spaces and repeated dots are safe. Counted, never dropped.
- `symlink`: open every path component relative to its parent descriptor with `O_NOFOLLOW` (POSIX
  `dir_fd` walk), so a file symlink, a linked directory, and a parent swapped for a symlink AFTER the
  check (`kl_06`) are all refused at open time.
- `not_regular`: open with `O_NONBLOCK`, then `fstat` the descriptor; FIFO, directory, socket, device → skip. A FIFO never blocks.
- Read at most 512 KiB (524,288 bytes) plus one sentinel byte: larger → `oversized`; exactly the cap
  and one below are screened. 0 bytes → `empty`. UTF-8 BOM accepted; NUL or invalid UTF-8 → `binary`. CRLF = LF.
- `unreadable`: vanished, permission denied, or the descriptor's inode differs from the enumerated one.
  A hardlink is judged by the bytes read; it never bypasses content rules.
- `screen_error`: ANY `Exception` from path checks, read, decode, views or rules. A `BaseException`
  (`KeyboardInterrupt`) aborts the build; the queue is replaced atomically, so the old queue stays
  untouched and no temp file remains. **A screen crash never queues a file.**

## Bounds and accounting

Cost is O(n) per file for n ≤ 524,288 bytes: a constant number of views, base64 depth ≤ 2, no nested
unbounded quantifier, phone windows ≤ 15 digits. Memory O(n). Rows of category `cost` (`eyJ`×n,
letters-only, `%41`×n, digit groups — all at the cap) must each finish within 2 s CPU on the CI runner,
and doubling an adversarial input from 64 KiB to 512 KiB must grow time by no more than ~2.5× per doubling.

The builder prints one summary line, keys sorted, zero-count reasons optional:

    {"jobs": N, "skipped": {"binary": 0, "crm_name": 0, "email": 0, "empty": 0, "excluded_path": 0,
     "id_number": 0, "not_regular": 0, "oversized": 0, "phone": 0, "screen_error": 0, "secret": 0,
     "short": 0, "symlink": 0, "unreadable": 0, "unsafe_path": 0}, "prompt_chars": M}

Invariant: `jobs + sum(skipped) ==` the number of tracked paths under `ROOTS` with an `EXT` suffix, plus
the `unsafe_path` entries. `short` is builder policy; every other key is a screen reason.

## Declared limits

These guilt shapes MAY be queued. Each is a corpus row with `limit: true`; the test fails if this list
and those rows differ. Everything not listed here is a defect when it leaks.

- `limit:g7971n_05` — an unlabelled 16-digit NIK in prose: indistinguishable from long numeric ids.
- `limit:r2x_11` — a credential under three or more base64 layers (depth is bounded at two for cost).
- `limit:lim_01` — a personal name outside any CRM-like structure (no named-entity recognition).
- `limit:lim_02` — an address spelled with plain words (`person at client dot corp`).
- `limit:lim_03` — a capitalised letters-only password after `:` in code, read as a type annotation.
- `limit:lim_04` — a Tier S literal shorter than 16 characters or letters-only (`SERVICE_TOKEN = "shortTok"`).

Fail-closed bounds are not limits: oversized, binary, unsafe-path, unreadable and `screen_error` files
are refused and asserted as such. Encrypted, compressed or hashed values are not cleartext and are out of scope.

## Acceptance

1. On Python 3.9 AND 3.11, through the screen entry point: every guilt row without `limit: true` is
   skipped with exactly its `expected_reason`; every innocence row is queued (100 %); limit rows are
   reported, not asserted. Structural rows run through the builder in a temporary directory.
2. `test_screen_corpus.py` stays green: schema, reconstruction, claimed shapes, source counts
   (31 + 16 + 12 receipt leaks, 6 untested rules, ≥ 30 innocence rows), this limit list, and a corpus
   file with no token-, DSN- or phone-shaped literal.
3. Mutation: removing any single decoded view, family, context rule or structural check turns at least
   one corpus row red (#7971 r2 left 6 claimed rules green; Kimi D8: escape rows passing on raw text).
4. The guard suite proves the cost bound, deterministic per-reason accounting, atomic output, and that an
   injected exception yields `screen_error` and never a queued file.
5. The PR body reports the real-tree summary (`jobs`, per reason) and reads every file whose reason changed.
6. A fresh independent gate adds ≥ 20 invented shapes not in the corpus and finds 0 undeclared leaks.
   A new leak amends THIS spec and corpus first, then the code.
