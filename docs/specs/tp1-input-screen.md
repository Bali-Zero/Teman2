# TP1 input screen — specification

Status: normative design for the next implementation (PR-C: the screen, PR-D: `build_verify_queue.py`).
It specifies decisions as entities, not a particular regex or library. The executable examples are
`scripts/tp1max/screen_corpus.yaml`; `scripts/tp1max/test_screen_corpus.py` keeps that corpus valid in CI.
Why it exists: the final gate blocked the screen three times (#7927 B1: 31 leaked shapes; #7971 B1: 16;
#7971 B1-r2: 12), each time on shapes nobody had written down. A cure at depth 2 is a spec, so here it is.

## Threat model

1. What leaves: the bytes of every queued file, its repository-relative path, and the prompt built from them.
2. To whom: a paid third-party model API (the TP1 plan), outside Nuzantara's trust boundary.
3. Never leaves, in any grouping or reversible encoding that a declared rule covers: credential values; client PII — phone numbers, personal e-mail addresses, national-ID and passport numbers, personal names in CRM-like records (the four enumerated entities). What no rule covers is a declared remainder (item 7, Declared limits).
4. May leave: ordinary source, exact role mailboxes on the project's own domains, RFC-reserved example addresses, prose that names a secret family without a value.
5. The screen decides on entities and context, fails closed, and counts every refusal; a public repo is no exception to the output boundary.
6. Payment card numbers (PAN) and IBANs are adopted into `id_number`, fail-closed: a file holding one is not queued. They are personal financial data that UU PDP 27/2022 classifies as specific personal data (art. 4(2)(f)). A PAN is a Luhn-valid number of 13–19 digits, grouped by spaces or hyphens or contiguous under a card label; an IBAN is two letters, two check digits and 11–30 letters or digits whose ISO 13616 mod-97 check passes. A card-like number that fails Luhn and an IBAN-shaped string that fails its checksum are innocent.
7. Any other personal data outside the four enumerated entities, whatever its category, is SKIPPED as `pii_other`, fail-closed — for example a date of birth, a postal address, a messaging or social handle, a vehicle plate, location coordinates, religion or marital status, health notes, financial data other than the PAN and IBAN of item 6, such as a bank account number or a salary, or a record that combines such data with a name (UU PDP art. 4(2) and 4(3)); a label with a whole-value placeholder (`tanggal_lahir: YYYY-MM-DD`) is innocent.
8. Decision (2026-10-10): items 6 and 7 were adopted by the imperator session under the owner's explicit delegation ("fai tutto tu e decidi tu al meglio"); the owner can reverse it. Why: Builder Contract §4 makes PII an OUTPUT boundary with no cloud whose terms make cleartext PII acceptable, and UU PDP art. 4(2)(f) and 4(2)-(3) name these categories; TP1 is outside the trust boundary; the cost of a false block is only a file not sent.

## Contract and decision order

The screen judges one candidate: `(path, bytes)` read from the working tree at build time — the bytes
that would leave, not the committed blob. It returns `queue` or `skip(reason)`. Order: structural
checks; bounded read; UTF-8 decode; decoded views; credential rules; PII rules. The first reason wins. Within PII, the unique precedence is phone → e-mail → `id_number` → `crm_name` → `pii_other`; therefore `nomor_telepon` resolves to phone even though `nomor` is also an ID label.
The path is screened as text together with the content, because it leaves in the job id and the prompt.

Builder policy is separate from the screen: candidate selection (`EXT`, `ROOTS`, `SKIP_PATH`, counted as
`excluded_path`) and the `MIN_CHARS` floor (counted as `short`). Corpus content rows are judged at the
screen entry point, never through `MIN_CHARS`; the path string `src/<id>.txt` (or `setup.path`) is part of the screened text.

The verdict must be identical on Python 3.9 and 3.11 with only declared dependencies. An optionally
installed detector must not change it (the #7971 Codex build did exactly that; the plugin layer was reverted).

### Literals, references and placeholders

A **literal** is a concrete scalar: quoted, after `=` or `:`, in a credential-bearing CLI slot, or in a
URI authority. Not a literal: a shell variable or `${…}`/`{…}` interpolation, `$(…)` command
substitution, a function call or attribute reference in code syntax (`settings.indexnow_key`, `cfg.get(…)`), an environment read, a
type or class name, and a
value that is WHOLLY a placeholder (`<…>`, `redacted`, `example`, `dummy`, `fake`, `placeholder`, `xxx`,
`changeme`, `YOUR_…` or `your-…` in any case, as in the value `your-api-key-here` of
`g7988_innocent_05`). The placeholder test is on the complete value: a family token that merely
contains `xxxx` or `example` stays guilty (`kimi_34`, `kl_05`), and a run of one repeated character is
not a placeholder — that is how fixtures write tokens. An empty literal is not a value. A template or
concatenation is innocent only when every credential slot in it is a reference: a literal fragment in a
credential slot (`f"postgresql://app:<literal>@{host}"`, `c1_07`) is a literal. In a shell assignment
(`export NAME=…`, `NAME=… cmd`) every unquoted value except `$…`, `${…}` and `$(…)` is a literal: a dotted value there is
not an attribute reference (`export VAULT_TOKEN=hvs.…` is guilty, `r2_12`). A real credential whose whole value equals a placeholder word, a boolean or a status word that this spec declares innocent (a `changeme` or `passed` value that is the real password) is the declared limit `rem_placeholder`.

## Credential entities (reason `secret`)

### Named assignments

The entity is `NAME <op> literal` in any of: `NAME = lit`, `NAME: lit`, `"NAME": "lit"`, `NAME=lit`,
`export NAME=lit`, keyword argument `name="lit"`, `.npmrc` `//host/:_authToken=lit`, and the carriers below. The name is
normalised: case-folded; camelCase, `-` and `.` split into `_` segments; a trailing digit run is its own segment
(`PASSWORD2`, `oauthToken1`). A stem matches a segment that equals it or ends with it (`PGPASSWORD`, `SSHPASS`), in ANY
position of the name: `PG_PASSWORD_RO`, `DB_PASSWORD_2`, `CLAUDE_CODE_OAUTH_TOKEN_1` and `api_key_v2` are credential names
(`r2_04`, `r2_05`). The name takes the tier of its most specific stem: a two-segment stem such as `SECRET_KEY` beats `KEY`.
A credential under a name that holds no stem (`PIN = "482193"`, `ACCESS_CODE`, plurals such as `TOKENS`, a `sessionid` cookie, `PASSCODE`/`OTP`, the `default` of a Terraform `sensitive` variable) is the declared limit `rem_stem`.

**Property words.** A name is not credential-bearing when a property word follows its LAST stem segment: `file`, `path`,
`dir`, `url`, `uri`, `endpoint`, `host`, `port`, `len`, `length`, `min`, `max`, `count`, `size`, `limit`, `rounds`,
`retries`, `attempts`, `hash`, `digest`, `id`, `ids`, `name`, `names`, `type`, `kind`, `status`, `required`, `enabled`,
`disabled`, `policy`, `field`, `header`, `param`, `re`, `regex`, `pattern`, `ttl`, `expiry`, `expires`, `timeout`,
`prompt`, `label`, `hint`, `message`, `text`, `env`, `var`, `ref`, `scope`, `scopes`, `format`, `version`
(`PASSWORD_MIN_LENGTH`, `TOKEN_TYPE`, `SECRET_NAME`, `CANARY_TOKEN_HEADER`, `_TOKEN_RE`: `r2_innocent_01`). A stem after
the property word restores it (`PASSWORD_FILE_TOKEN` is Tier S, `r2_16`). A credential stored under such a name
(`DB_PASSWORD_FILE = "<the password itself>"`) is the declared limit `rem_property`.

**Ordinary words.** A segment that is an ordinary word ending in a stem is not a stem segment: `bypass`, `compass`,
`encompass`, `surpass`, `trespass`, `overpass`, `underpass`, `oldpwd`, `monkey`, `donkey`, `turkey`, `hockey`, `jockey`,
`whiskey`, `turnkey` (`BYPASS = "yes"`, `BYPASS_MODE = "yes"` and `COMPASS = "north"` are innocent).

| Tier | Stem, any segment                                                                                                                                | Guilty literal                                                                                                                                                                                                                                                                                                                                                                                 | Innocent counterpart                                                                                                                                                                                                                              |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P    | `PASS`, `PASSWD`, `PASSWORD`, `PASSPHRASE`, `PWD`, `PW`                                                                                          | any non-empty literal, any length, quoted or not, letters-only included (`DB_PASS`, `MYSQL_PWD`, `DRILL_PW`); an all-digit literal of ≥ 6 digits (eight digits under a Tier P key, `r2_08`)                                                                                                                                                                                                    | empty literal; an all-digit literal of fewer than 6 digits (declared limit `rem_short_digits`); a boolean word (true, false, yes, no); a status word equal to a name segment or in {pass, passed, fail, failed, ok, skip} (`STATE_PASS = "pass"`) |
| S    | `SECRET`, `TOKEN`, `AUTH_TOKEN`, `API_KEY`, `APIKEY`, `ACCESS_KEY`, `SECRET_KEY`, `PRIVATE_KEY`, `SIGNING_KEY`, `CLIENT_SECRET`, `CREDENTIAL(S)` | ≥ 16 characters mixing letters with a digit or non-letter, or ≥ 32 hex digits                                                                                                                                                                                                                                                                                                                  | `token_type = "Bearer"`, `token_status` (a property word follows the stem); references; `$(…)`; shorter, letters-only or letter-free literals (digits or punctuation only) that are not ≥ 32 hex digits are the declared limit `lim_04`           |
| K    | any other name ending in `KEY` except `PUBLIC_KEY`/`PUB_KEY`/`PUBKEY`                                                                            | an opaque value: ≥ 32 hex digits, or ≥ 20 characters all from the standard or URL-safe base64 alphabet (`+`, `/`, `-`, `_` and terminal `=` padding included) with a letter and a digit; a value holding `:`, `.` or a space is not opaque; values outside this grammar (shorter than 20 characters, without a digit, or holding `:`, `.` or a space) are the declared limit `rem_tierk_short` | `CACHE_KEY = "session:user-profile:v2"`; a path of lower-case `/`-separated segments (`uploads/2026/10/report`); settings references; public keys                                                                                                 |

A family signature (next section) overrides every length and tier condition.

**Value placement.** The literal may sit on the same line, or on the NEXT logical line after a
trailing `:` (`password:` then an indented `pw`), after a YAML block-scalar indicator (`|` or `>`, optional
`-`/`+` chomping: the first indented line, also inside a heredoc, `c1_08`), or after a trailing `=`
(one newline, optional indentation: `r2x_01`). The next-line case never takes a docstring opener, a line ending in `:`, a `def`/`class`
line, or a mapping/tuple item as the value (`class TokenUsage:` + docstring is innocent).

**Annotations and references.** After `:` in code, an unquoted value is an annotation or reference when it is a builtin
type name (`str`, `int`, `bytes`, `bool`, `float`, `dict`, `list`, `Any`, `None`, `object`) or a type-shaped
identifier — it starts with a capital letter, holds only letters and digits, has at most two digit runs, and every digit
run in it is directly followed by a capital letter (`Ed25519PrivateKey`, `Http2Client`, `SecretStr`, `Summer`) —
optionally followed by `[…]`, `|`, `=` or `.attr(…)` (`Optional[str]`, `str | None`). After `=` the same identifier is a
name reference (`private_key = Ed25519PrivateKey.generate()`). Any other unquoted value after a Tier P/S/K name is a
literal: `password: letmein`, `password: Sup3rSecret` (a digit followed by a lower-case letter), `password: Summer2024`
(a trailing digit run), a mixed token with three or more digit runs, and a base64 value under `password:` in a
Kubernetes Secret. A password shaped like a type identifier (`password: Summer`, `password: Welcome1Password`) is the
declared limit `lim_03`.

**Assignment carriers.** The tier of the NAME decides, unchanged, when the pair is written as a subscript assignment
`<expr>["NAME"] = lit` or `<expr>['NAME']=lit` on ANY expression — `os.environ`, a copied `env`, a `payload`, a nested
`cfg["smtp"]["password"]`, where the last quoted key is the NAME (`r2_01`–`r2_03`) — or as a pair-taking call whose first
argument is the quoted NAME and whose second is the literal: `.setdefault`, `.set`, `.put`, `.setItem`, `setenv`,
`putenv("NAME=lit")` and shell `setenv NAME lit`; as an XML element `<NAME>lit</NAME>` or a quoted attribute `NAME="lit"`
(`g7988_14`, `g7988_26`); or as `.pypirc` `password = lit`. A UI string stored under a Tier P name (`store.put("password", "minimum length")`) is skipped too: an accepted over-skip. `.git-credentials` lines are URIs (next section). Registry
auth slots are guilty for ANY non-empty literal, because they hold base64 of `user:password` or a registry token: Docker
`config.json` `"auth"` and `"identitytoken"` values, and `.npmrc` `_auth=`, `_authToken=` and `_password=`. A credential
that reaches code in any other shape — positionally without its name (`connect("db.invalid", "app", "<pw>")`), a
three-argument config setter, an unlisted builder call — is the declared limit `rem_carrier`.

### Credential-bearing contexts

Guilty when the operand is a literal; quoting, `=` versus space, and glued short options do not change
the entity. A quoted operand extends to its closing quote or the end of the line, with no length cap
below the file cap, and may contain spaces (`kl_01`–`kl_03`).

- `-p<pw>` / `-p <pw>` after `mysql`, `mysqldump`, `sshpass`, `docker login`; `--password`,
  `--passwd`, `--http-password`, `--ftp-password`, `--proxy-password`;
- `-a <pw>` / `-a<pw>` after `redis-cli`, `valkey-cli`, `keydb-cli`; `--pass`, `--auth`, `--authtoken`, `--auth-token`,
  `--authkey`, `--auth-key` after any command (`r2_09`);
- `-u user:pw`, `-uuser:pw`, `--user user:pw`, `--user=user:pw` (curl/wget style);
- `.netrc`: `login … password …` on one line or `password` as its own directive line; `.pgpass`:
  a five-field `host:port:db:user:password` row whose host is not all digits, whose port is digits or `*` and whose user is
  not numeric; the password may be numeric (`r2_18`);
- `Authorization` / `Proxy-Authorization`: `Basic|Bearer|Token <literal>`, header or mapping syntax;
- `auth=(user, password)` and equivalent literal two-tuples passed as `auth`;
- any URI whose scheme matches `[a-z][a-z0-9+.-]*://` and whose user-info is `user:literal@` (the user may be empty:
  `redis://:<pw>@cache`, `r2_15`),
  including mysql, AMQP, Redis, MongoDB, HTTPS and composite schemes such as
  `postgresql+asyncpg`; the literal may be one character.

Innocent: the same syntax with a variable, template or placeholder operand; prose naming an option
without an operand (an option at the end of a line or followed only by punctuation); `date -u +%Y…`; an all-numeric colon list (`7880:7881:7882:50000:60000`); a URL with
no user-info or a `{pwd}` template. In particular `user:${PASS}@`, `user:<password>@` and
`user:xxx@` are placeholders, not credentials; `Authorization: Bearer YOUR_JWT_TOKEN` is innocent. A credential in a context outside this list — a password flag of a tool not listed here (`ldapsearch -w`, `smbclient -U user%pw`), a `.pgpass` row whose host or user is numeric — is the declared limit `rem_cli`.

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
values under an AWS secret name (assignment or JSON key); Fly `FlyV1`, `fm1_`, `fm2_`, `fo1_`; Meta
`EAA[A-Za-z0-9]{20,}`; Tailscale `tskey-` (general grammar: the real
`tskey-auth-<id>CNTRL-<secret>` keeps its inner `-`, `g7988_08`); Groq
`gsk_[A-Za-z0-9]{20,}`; age `AGE-SECRET-KEY-1`; Azure `AccountKey=`. Every family here has its own corpus row; a family joins this
list only together with its row; what lies outside the list — an unlisted family, or a listed family's value outside its stated grammar (a JWT segment shorter than 8 characters, as in an empty `e30` payload) — is the declared limit `g7988_10`. PEM private keys: header in any case, LF, CRLF or `\n`-escaped; a header alone is
sufficient; a headerless body is guilty under a Tier S name. An OpenPGP `-----BEGIN PGP PRIVATE KEY
BLOCK-----` armor header is guilty like a PEM header (`g7988_27`). A PEM PUBLIC key block is innocent.
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
still screened. Each layer is at most 3/4 of its input, so total work stays below 2.4·n. A reversible view outside that set which contains either a credential or PII — a hex dump, rot13, reversed text, or a literal split by concatenation (`"08" + "12" + "3456" + "7890"`) — is uniquely assigned to declared limit `rem_views`.

## PII entities

### Phones (reason `phone`)

Normalise Unicode decimal digits to ASCII (NFKC; fullwidth included). Separators: ASCII and Unicode
spaces incl. NBSP, `(`, `)`, `.`, `/`, `-`, U+2010–U+2015, and at most one newline plus indentation.
Separators split the digit stream into GROUPS. A candidate starts at a group boundary that is not
preceded by a digit (a letter, `_` or punctuation may precede it: `phone628…`, `WA_NUMBER_62…`) and
spans consecutive groups up to 15 digits; every group-aligned prefix is tested, so a trailing year or a
second number (`… / 0813…`) does not hide the first. Markers: `+` glued to the first digit or inside
`(+62)`; `00` followed by a country code `[1-9]`; `tel:`, `wa.me/`, `@s.whatsapp.net`; a phone label attached to the value: a key or label whose normalised name has a segment `phone`, `telephone`, `telepon`, `telp`, `tel`, `mobile`, `cell`, `hp`, `wa`, `whatsapp` or `contact` (`no_hp`, `nomor_telepon`, `r2_07`). The markers `tel:`, `wa.me/` and `@s.whatsapp.net` act like a label: the 7–15-digit value they introduce is a phone with or without `+` (`https://wa.me/39 347 1234567`, `g8019_01`).
A labelled value with 7–15 digits is a phone in any domestic grouping, including Indonesian, Italian,
German and US forms; labels alone, placeholders and all-zero examples are innocent, as are ports and
version strings merely adjacent to a label. The amount exemption below never applies to a labelled value (`phone: "347.123.456"`, `r2_17`). A label segment followed by a property word (Named assignments: `contact_count`, `phone_type`) is not a phone label (`r2_innocent_03`). A phone-shaped digit stream without a recognised label — under a label outside this list (`ufficio: 347 123 4567`), in a table cell or in prose (`Chiamare Mario al 347 123 4567`) — in a grouping the guilty shapes do not name (a domestic non-Indonesian number, an Indonesian number whose first group is a lone `0` such as `0 361 777777`), or one the date or amount exemptions remove (`+39.347.123.456`, a labelled value shaped like a valid date), or a labelled value with fewer than 7 or more than 15 digits (`telp: 777777`, a local number without its area code), is the declared limit `rem_phone_label`.

Guilty shapes: Indonesian mobile `08` + 8–11 digits, `628`/`+628`/`00628` + 8–11, and `62 (0)8…` /
`+62 (0)8…` with the `(0)` dropped; Indonesian landline `0[2-7]` + 7–10 more digits, or the same after
`+62`; international `+`/`00` + country code with 8–15 digits in total. A landline candidate is one
whose OWN first group starts with `0[2-7]` (`(0361) 777777`, `021-5555555`), or one that carries a
marker (a phone label, a glued `+62`, `tel:`). A first group that is a lone `0` never starts a
landline, and a `/` with a space on either side is an operator that ends the chain (each side is its
own candidate), so `(h >>> 0) / 4294967295` is two numbers and neither is a phone, while the two
mobiles of `dux_06` stay two phones. Groups chained only by spaced `/` (`0812 / 3456 / 7890`) are the declared limit `rem_slash_phone`.

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

`id_number`: a 16-digit NIK/KTP/KK, a 15–16-digit NPWP (either with or without `.`, `-` or space grouping: `c1_09`, `r2_10`),
or a passport, KITAS or KITAP number: 6–16 letters and digits, with at least 6 digits, in any issuer's
order (`AB1234567`, a 9-digit US/UK number, `C01X00T47`, an alphanumeric KITAS card number). The value
must be attached to a key or label whose normalised name (as in Named assignments) has a segment
`nik`, `ktp`, `kk`, `npwp`, `kitas`, `kitap`, `passport`, `paspor`, `document`, `dokumen`, `nomor` or `national` (`no_ktp`, `nomor_kitas`, `passport_number`, `passportNo`, `no_paspor`, `document_number`, `no_dokumen`, `national_id`: `r2_06`, `r2_11`); `nomor_invoice: "INV2026001234"` is skipped too, an accepted over-skip. An identifier under a label outside this list (`ssn`, `codice_fiscale`) is the declared limit `rem_id_label`; a number under a recognised label but outside the 6–16 / ≥ 6-digit grammar (`passport: "AB12345"`) is the declared limit `rem_id_grammar`. An identity number of any issuer or grammar with no recognised ID label attached — in prose or in a table column (`| Paspor |`) — is the declared limit `g7971n_05`. A label by itself, a whole-value placeholder, or an
all-zero example is innocent. `crm_name`: a string literal of 2–6
words, each starting with a letter, under a key `name`, `full_name`, `nama`, `client_name`,
`customer_name` or `contact_name`, in a record whose other keys name a client/customer/contact/lead/stage
or hold a phone or e-mail field (`normative_10`). A name in a CRM record outside the 2–6-word grammar — a single word (mononyms are common in Indonesia), seven or more words, a word that starts with a non-letter — is the declared limit `rem_crm_mononym`. A 2–6-word name under any other key that denotes a person's name (`nama_lengkap`, `customerName`, `clientName`, `fullName`) inside a CRM-shaped record is the declared limit `rem_crm_key`.
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
     "id_number": 0, "not_regular": 0, "oversized": 0, "phone": 0, "pii_other": 0, "screen_error": 0, "secret": 0,
     "short": 0, "symlink": 0, "unreadable": 0, "unsafe_path": 0}, "prompt_chars": M}

Invariant: `jobs + sum(skipped) ==` the number of tracked paths under `ROOTS` with an `EXT` suffix, plus
the `unsafe_path` entries. `short` is builder policy; every other key is a screen reason.

## Closed vocabularies and their remainders

This section is the spec of the spec. Every closed list above is a vocabulary, and every vocabulary ends with its declared remainder — one, or two where the table lists two: what lies outside it is named in a sentence, has its own `limit: true` row and appears in the
Declared limits. A closed list without a remainder is a spec defect, and so is a remainder without a row. A new leak
is cured by naming the remainder it fell into, not by a row chasing the shape. Rows that pin a rule carry `rule:`, a
phrase quoted verbatim from this spec; the schema test fails when the phrase is missing, so deleting a PINNED phrase turns its row red (every remainder row carries one); rule text that no row quotes is not covered by this check.

| Vocabulary                     | Section                               | Remainder                                |
| ------------------------------ | ------------------------------------- | ---------------------------------------- |
| name stems (Tier P/S/K)        | Named assignments                     | `rem_stem`                               |
| property words                 | Named assignments                     | `rem_property`                           |
| all-digit Tier P threshold (6) | Named assignments                     | `rem_short_digits`                       |
| Tier S floor (16, mixed)       | Named assignments                     | `lim_04`                                 |
| Tier K floor (20)              | Named assignments                     | `rem_tierk_short`                        |
| type-shaped identifiers        | Annotations and references            | `lim_03`                                 |
| placeholder words              | Literals, references and placeholders | `rem_placeholder`                        |
| assignment carriers            | Assignment carriers                   | `rem_carrier`                            |
| CLI flags and contexts         | Credential-bearing contexts           | `rem_cli`                                |
| credential families            | Credential families                   | `g7988_10`                               |
| decoded views and depth        | Decoded views                         | `rem_views`, `r2x_11`                    |
| phone shapes and labels        | Phones                                | `rem_phone_label`                        |
| phone grouping chains          | Phones                                | `rem_slash_phone`                        |
| ID labels                      | National IDs                          | `rem_id_label`; unlabelled: `g7971n_05`  |
| ID number grammar              | National IDs                          | `rem_id_grammar`                         |
| CRM name grammar and structure | National IDs                          | `rem_crm_mononym`; outside CRM: `lim_01` |
| CRM name keys                  | National IDs                          | `rem_crm_key`                            |
| e-mail spellings               | E-mail                                | `lim_02`                                 |

The e-mail allowlist is the one closed list whose outside is GUILTY (everything not allowed is skipped), so it needs no
remainder.

## Declared limits

These guilt shapes MAY be queued. Each is a corpus row with `limit: true`; the test fails if this list
and those rows differ. Everything not listed here is a defect when it leaks.

- `limit:g7971n_05` — an identity number of any issuer or grammar (NIK, passport, KITAS/KITAP, NPWP, a foreign ID) without a recognised label attached, in prose or a table column.
- `limit:r2x_11` — a credential or a PII value under three or more base64 layers (depth is bounded at two for cost).
- `limit:lim_01` — a personal name outside any CRM-like structure (no named-entity recognition).
- `limit:lim_02` — an address spelled with plain words (`person at client dot corp`).
- `limit:lim_03` — an unquoted password shaped like a type identifier after `:` or `=` (`password: Summer`,
  `password: Welcome1Password`): indistinguishable from an annotation or a name reference.
- `limit:lim_04` — a Tier S literal outside the guilty grammar: shorter than 16 characters, letters-only, or with no letter at all (digits or punctuation only) — never a value of ≥ 32 hex digits, which is guilty (`SERVICE_TOKEN = "shortTok"`).
- `limit:g7988_10` — a bare token family absent from the explicit family list; unlisted bare families
  are not caught unless their surrounding assignment or credential context triggers a tier/context rule; also a listed family's value outside its own grammar (a JWT with a segment under 8 characters).
- `limit:rem_stem` — a credential under a name holding no Tier P/S/K stem (`PIN = "482193"`, `TOKENS`, `sessionid`, `PASSCODE`, a Terraform `sensitive` default).
- `limit:rem_property` — a credential stored under a stem followed by a property word (`DB_PASSWORD_FILE`).
- `limit:rem_short_digits` — an all-digit Tier P literal of fewer than 6 digits (`password: 4821`).
- `limit:rem_tierk_short` — a Tier K value outside the opaque grammar (short, digit-free, or holding `:`, `.` or a space).
- `limit:rem_placeholder` — a real credential equal to a placeholder, boolean or status word (`changeme`, `passed`).
- `limit:rem_carrier` — a credential reaching code in an unlisted carrier (positional, three-argument setter).
- `limit:rem_cli` — a credential in an unlisted context (`ldapsearch -w`, a `.pgpass` row with a numeric host or user).
- `limit:rem_views` — a credential or a PII value in a reversible view outside the decoded views (hex dump, rot13, split literal).
- `limit:rem_phone_label` — a phone-shaped digit stream without a recognised label (unlisted label, table cell, prose) in a grouping the guilty shapes do not name (non-Indonesian domestic, a lone `0` first group), or one the date/amount exemptions remove, or a labelled value outside the 7–15-digit band.
- `limit:rem_slash_phone` — phone groups chained only by spaced `/`.
- `limit:rem_id_label` — an identity number under an unlisted label (`ssn`, `codice_fiscale`).
- `limit:rem_id_grammar` — a number under an ID label outside the 6–16 / ≥ 6-digit grammar.
- `limit:rem_crm_mononym` — a CRM name outside the 2–6-word grammar (one word, seven or more, a non-letter start).
- `limit:rem_crm_key` — a 2–6-word personal name under an unlisted name key in a CRM-shaped record (`nama_lengkap`, `customerName`).

Fail-closed bounds are not limits: oversized, binary, unsafe-path, unreadable and `screen_error` files
are refused and asserted as such. Encrypted, compressed or hashed values are not cleartext and are out of scope.

## Acceptance

1. On Python 3.9 AND 3.11, through the screen entry point: every guilt row without `limit: true` is
   skipped with exactly its `expected_reason`; every innocence row is queued (100 %); limit rows are
   reported, not asserted. Structural rows run through the builder in a temporary directory.
2. `test_screen_corpus.py` stays green: schema, reconstruction, claimed shapes, source counts
   (31 + 16 + 12 receipt leaks, 6 untested rules, ≥ 30 innocence rows), this limit list (21 declared limits), the pinned adoption rows of items 6 and 7 (7 asserted guilt rows, 3 innocence rows), and a corpus
   file with no token-, DSN- or phone-shaped literal; every innocence row, MATERIALISED, carries no
   credential family and no Indonesian mobile (the schema test asserts both). The implementation test
   does the same before asserting that the row queues.
3. Mutation: removing any single decoded view, family, context rule or structural check turns at least
   one corpus row red (#7971 r2 left 6 claimed rules green; Kimi D8: escape rows passing on raw text).
4. The guard suite proves the cost bound, deterministic per-reason accounting, atomic output, and that an
   injected exception yields `screen_error` and never a queued file.
5. The PR body reports the real-tree summary (`jobs`, per reason) and reads every file whose reason changed.
6. A fresh independent gate adds ≥ 20 invented shapes not in the corpus and finds 0 undeclared leaks: every
   credential or PII shape it builds lands on a rule or on a declared remainder. A shape that lands on neither amends
   THIS spec and corpus first — by naming its remainder in Closed vocabularies — then the code.
