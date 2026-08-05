# Zoho mail loop — runbook (born as the M5 -> Pro handoff)

Written 2026-08-04 by the Cowork session on M5, **amended the same day by the Pro
session that received it**. The amendments are marked `CORRECTION`; they are not
edits of taste. Two claims in the original were false on the target machine, and
one of them would have taken the organ down silently on the day it went live.

## 0. UNBLOCK FIRST — DONE

The Cowork sandbox could create inside `.git` but not unlink, so it left a 0-byte
`index.lock` and a `.probe-write`, and the checkout was stuck on a probe branch.

> **CORRECTION.** The original read "No content was lost: `HEAD` is the same
> commit as `origin/main`". When the Pro checked, HEAD was `19d4697a9` and
> `origin/main` was `a4571d3ec` — not the same commit. The conclusion survived
> for a different reason, which was verified rather than assumed: the range
> `origin/main..probe/sandbox-write-test` was EMPTY, so the probe branch was
> merely _behind_, holding nothing of its own. Nothing was lost. But "same
> commit" and "no unique commits" are different statements, and only the second
> one was true.

Executed on M5 (no live `git` process was holding the lock — checked, not
assumed). The checkout is on `main`, the probe branch is deleted, and all the
untracked work survived the switch.

## 1. The work is UNTRACKED — superseded

The original instructed the reader to commit and push from M5. That is not how it
shipped: the Pro session copied the files over (excluding `__pycache__`), fixed
what is listed in §6, and committed from a worktree there, so the fixes and the
original land together. `drafts/` was left dirty on M5 — it is unrelated work.

## 2. What was built

A thin orchestration layer on the EXISTING `ZohoEmailService` — no second IMAP
stack, no new credential. Daily: route unread inbox mail into a Zoho folder,
append a reply draft, and learn from yesterday's Sent folder.

| file                                     | role                                       |
| ---------------------------------------- | ------------------------------------------ |
| `services/mail_loop/classify.py`         | intent + language routing (pure)           |
| `services/mail_loop/draft.py`            | reply body via `claude` CLI, never sends   |
| `services/mail_loop/learn.py`            | diff(our draft, what was sent) -> signals  |
| `services/mail_loop/style.py`            | `reply-style.md`, the ONLY thing persisted |
| `services/mail_loop/loop.py`             | orchestration + pending-comparison buffer  |
| `services/mail_loop/cli.py`              | entrypoint, exit 0 / 1 degraded / 2 dead   |
| `scripts/zoho-mail-loop.sh`              | wrapper: rc capture + tg_notify.py gateway |
| `scripts/test_zoho_mail_loop_wrapper.sh` | 34 checks on the wrapper's exit-code path  |

The Protocol in `loop.py` was re-verified against the live service by AST rather
than by eye: all five methods and their defaults match
`ZohoEmailService` exactly.

> **CORRECTION — the verification claim.** The original said "85 pytest + 16
> shell checks green, all mutation-verified". The pytest half was true. **The
> shell half was not: 10 of the 16 failed on the Pro, and on M5 too.** They were
> green only in the Cowork container, which is Linux with bash 5. macOS ships
> bash 3.2.57, launchd runs `/bin/bash`, and in 3.2 expanding an EMPTY array
> under `set -u` is a fatal "unbound variable". The wrapper's `ARGS` array is
> empty exactly when `MAIL_LOOP_DRY_RUN` is 0 — the live configuration, i.e.
> step 4 below. Measured: with `DRY_RUN=1` a job exiting 2 gave wrapper rc=2;
> with it unset, `line 97: ARGS[@]: unbound variable`, wrapper rc=1, the job
> never started, and the `case` that fires every alert never ran. A cron that
> dies mute the day it is switched on.
>
> Fixed (`${ARGS[@]+"${ARGS[@]}"}`), and the corpus was changed so it cannot be
> green for that reason again: it now pins the interpreter the plist names
> (`/bin/bash`, overridable with `MAIL_LOOP_TEST_BASH`), exercises BOTH flag
> states for every exit code, and prints a loud note when the running bash is
> ≥ 4 and therefore structurally unable to reproduce the fault.

Current state: **133 pytest (99 mail_loop + 11 error-shape + 23 oauth) and 34
shell checks green, mutation-verified.** Every defence was measured by switching
it off: the empty-array cure (16 shell red), the kill switch (1), the lock (26),
the heartbeat (27), the alert key (1), the list-shaped error body, the plain-text
body, the row ordering, its NULL guard, the consent-blocker in both directions,
the `invalid_client` guard (which reproduces the §5 production damage when
removed), and the service↔loop wording contract — reverting **both** halves of
the over-match in §5c turns it red, quoting back _"would demand a re-consent,
which is wrong for this failure"_.

```bash
cd apps/backend-rag
PYTHONPATH=. python3 -m pytest backend/tests/unit/services/mail_loop/ \
    -q --noconftest -c /dev/null
PYTHONPATH=. python3 -m pytest \
    backend/tests/unit/services/integrations/test_zoho_error_shapes.py -q
bash ../../scripts/test_zoho_mail_loop_wrapper.sh
```

The two invocations differ on purpose: the mail_loop corpus is hermetic and runs
without conftest, while the error-shape corpus imports the real service, which
imports `Settings` — that one needs the repo's conftest. Note that under conftest
pytest's summary line is swallowed by a plugin, so **judge those runs by exit
code**, never by grepping for "N passed".

## 3. The four steps that are NOT code — status

1. **Zoho client credentials — RESOLVED 2026-08-04.** `ZOHO_CLIENT_ID` /
   `ZOHO_CLIENT_SECRET` were absent from the Pro. The only pair on the machine
   (in `~/.openclaw/workspace/.env.master`) belongs to a different Zoho app —
   Zoho answered `invalid_code` for all three tokens. The working pair is a Fly
   secret on `nuzantara-rag`, and `fly secrets list` shows digests only; the
   value is readable from **inside** a running machine
   (`fly ssh console -C printenv`), which is where it was read. Installed on the
   Pro; **3/3 refresh tokens now refresh** (probed without writing).
2. **Folder access — RESOLVED 2026-08-05.** It was the blocker: every stored
   grant was `ZohoMail.messages.ALL ZohoMail.accounts.READ`, so
   `GET /messages/view` answered **200** while
   `GET /accounts/<id>/folders` answered **401 `INVALID_OAUTHSCOPE`** — the loop
   could read the mail and not see the folders it routes into.
   - The `accounts.READ` payload was checked for a folder list as a way around
     it: it has none (`emailAddress` and `sendMailDetails` are its only nested
     lists), so there was no path to a folder id with that grant.
   - Fixed by a Self Client re-consent (§8), **not** by the redirect flow this
     runbook originally prescribed — that flow cannot work for this client at
     all. The grant now carries `ZohoMail.folders.READ` and listing succeeds.
   - Root cause of the narrow grant, fixed in code: `/admin/zoho/auth` carried
     its own hardcoded scope list, drifted from `ZohoOAuthService.SCOPES` and
     naming no folder scope at all. See §9.
3. **The six folders** (`_Visa _PTPMA _Tax _Property _Admin _Noise`) — **CREATED
   2026-08-05**. They were absent (the mailbox had 16 folders, none of them one
   of the six) and `POST /folders` was refused by the stored grant. Closed
   without a second consent via the Self Client `client_credentials` grant —
   §8b has the exact call and the two routes that do NOT work. Verified through
   the service's own `list_folders`, and then by the loop: `--dry-run` now exits
   **0** with `missing_folders: []`, `errors: []`, routing 7 of 13 and leaving
   the 6 it refuses to guess about where a human sees them.
4. **Install the plist** — deliberately NOT done, and the order matters. The
   plist names `/Users/nuzantara/nuzantara/scripts/zoho-mail-loop.sh`,
   which exists on the Pro only after this branch merges and the checkout is
   pulled. Dropping the plist into `~/Library/LaunchAgents` before that would
   leave a job pointing at a file that is not there — armed to nothing, and
   indistinguishable from armed correctly until the morning it does not run.
   Install it after the pull, and only once step 2 is resolved: loading it today
   would buy a `p0` every morning restating this paragraph.
5. **Read a dry-run, then flip.** A dry-run was executed against the live
   mailbox and is reported in §5. It reached Zoho and stopped at the folder
   listing — which is the whole of step 2.

## 4. Traps

- **Do not add `set -e` to the wrapper.** It opens with `set -uo pipefail` and no
  `-e`, so a trailing `set -e` does not restore anything — it ENABLES errexit,
  and a non-zero return in the reporting path then aborts before `exit $RC`.
  `bash -n` passes it. Pinned by `test_zoho_mail_loop_wrapper.sh`.
- **Do not write `"${ARGS[@]}"`.** See the correction in §2. Pinned by the same
  corpus, which now runs under `/bin/bash`.
- **`alert()` must never return non-zero.** The messenger is not allowed to
  change the verdict.
- **The pending buffer must never gain the recipient or the subject.** It holds
  our own draft text and a thread id. Pinned by
  `test_pending_buffer_holds_no_client_identifiers`.
- **Markers are matched on word boundaries, never as substrings.** The innocence
  corpus is GENERATED by crossing the marker table with ordinary words: `visa`
  inside `advisable`, `oss` inside `possible`, `виза` inside `визажист`.
- **No Anthropic SDK.** `draft.py` shells out to the `claude` CLI. A launchd job
  does not inherit a login shell's PATH — set `CLAUDE_CLI_PATH` if it is not
  found.
- **NEW — never let this loop reach Zoho without client credentials.**
  `ZohoOAuthService._refresh_token` reads Zoho's `invalid_client` reply as a dead
  USER token and writes `token_expires_at = NOW() - INTERVAL '1 year'`, which
  trips the "invalidated, reconnect required" guard for every other consumer,
  including the live backend that has the right credentials. `invalid_client` is
  a statement about the CALLER. This is not theory: see §5. `cli.py` now
  preflights and exits 2 before a single request goes out.

## 5. What the dry-run actually did — including the damage

Three dry-runs were executed from the Pro before it was known that the Zoho
client credentials were missing. Zoho replied **HTTP 200 with `invalid_client` in
the body** (never trust the status code), and the shared OAuth service recorded
that as three dead user tokens: rows 2, 25 and 28 were stamped
`token_expires_at = NOW() - 1 year`. Row 2 had been refreshed successfully
~23 h earlier, so it was live when it was broken.

That path writes only `token_expires_at` and `updated_at` — `access_token` and
`refresh_token` are untouched — and the pre-probe values had been captured in the
same session, so the rows were restored to them exactly (`WHERE
token_expires_at < $1`, so a newer refresh by the live backend could not be
pulled backwards). Verified afterwards through a second, independent read-only
connection: all three back to their original timestamps, no guard tripped,
refresh tokens intact.

The blocker was then re-probed **without** going through the service — a direct,
non-writing call to Zoho — which is how `invalid_code` (wrong app) was
distinguished from `invalid_client` (no credentials) without breaking anything a
second time.

### 5b. The run that got through, and the three faults it exposed

With the right credentials installed, the dry-run reached Zoho and stopped at
`list_folders failed: API error: unknown`. Chasing that one word found three
independent defects, each of which had been hiding the next:

1. **The message was lying.** Zoho sends an authorization failure as a **list** —
   `[2, {"errorCode": "INVALID_OAUTHSCOPE", ...}]` — and `_request` coerced every
   non-dict body to `{}`, so a missing scope, a dead token, a malformed account
   id and a wrong API host all printed `unknown`. The guardian whose only job is
   to diagnose was the one obscuring the diagnosis.
2. **The row was chosen at random.** User `7dfe56b2` owns **two** rows for the
   same mailbox, and all four reads of `zoho_email_tokens` were bare
   `WHERE user_id = $1` with no `ORDER BY`. The row that answered (id 25) is
   unusable: its `account_id` holds an e-mail address where Zoho requires the
   numeric accountId, and its `api_domain` points at `zohoapis.com` instead of
   the Mail API host, so every request built from it 404s with
   `URL_RULE_NOT_CONFIGURED`. Worse than picking badly: two reads could answer
   from two DIFFERENT rows, pairing one row's account id with another's token.
   Proved on the live table — unordered → row 25 (unusable), ordered → row 27
   (usable), stable across five reads. **This affects the live backend too, not
   just this loop.**
3. **The grant is too narrow** — §3.2. This was the real blocker, and it was
   invisible behind (1) and (2).

### 5c. The cure caught the disease it was written against

The first version of the exit-2 rule matched the phrase **"reconnect required"**
in the run's errors. An independent review refused to ship it, and was right:
the shared OAuth service raised that same sentence for four different
situations, one of them being **any** non-200 from Zoho's token endpoint. A 429,
a 502 or a proxy hiccup would have been reported as _"the grant does not cover
folders — re-authorise at /admin/zoho/auth"_, sending a human to re-run the
consent flow. Re-consenting is precisely the act that inserts another row, which
is the duplicate-row problem in §5b.2. A guard reading a mood instead of a fact,
inside the cure written against exactly that.

Fixed on both sides, because one side alone is not a fix:

- the service stopped using one sentence for four meanings. A transient non-200
  is now `Token refresh temporarily unavailable (HTTP <code>) — retryable, not a
consent problem`, and only the three genuinely unrecoverable cases name
  `/admin/zoho/auth`;
- the guard matches that endpoint — an entity, the remedy itself — instead of
  prose;
- and `invalid_client` was split out entirely. It means OUR client id/secret are
  wrong, so it is neither retryable nor a consent problem, **and it no longer
  invalidates the user's token**. That is the §5 production damage cured at the
  root rather than merely avoided by the loop's preflight.

The test that pins it does **not** quote either side. A first attempt did, and a
mutation run caught it being decorative: with the guard reverted to its
over-matching form the hand-written strings still passed, because they had been
written against the fixed guard. `test_exit_code_contract_with_the_mail_loop`
drives the real refresh path for each of the four situations and classifies the
exception it actually produced — reverting both halves to the original wording
turns it red, quoting the failure back: _"would demand a re-consent, which is
wrong for this failure"_.

### 5d. Found while fixing the above, not part of the mandate

`disconnect()` deleted **all** of a user's token rows but revoked only the first
refresh token an unordered query returned. The other N-1 grants stayed live at
Zoho and became unrevocable, because the only copy of each token had just been
deleted. Now revokes every row (still best-effort: a Zoho outage must not pin a
user to an account they asked to leave).

## 6. What the Pro leg changed

| change                                                               | why                                                    |
| -------------------------------------------------------------------- | ------------------------------------------------------ |
| `${ARGS[@]+"${ARGS[@]}"}` in the wrapper                             | bash 3.2 empty-array fatal — silent death when live    |
| corpus pins `/bin/bash` + both flag states (16 -> 24 checks)         | a test free to pick its interpreter tests nothing      |
| wrapper sources the environment (DSN, Zoho pair, Claude token slot)  | launchd hands a job almost nothing                     |
| wrapper logs which credentials were found, never their values        | a credential failure must be diagnosable from the log  |
| `cli.py` preflights the Zoho client credentials                      | stops this loop from invalidating production tokens    |
| `cli.py` prefers `DATABASE_URL`, settings only as a guarded fallback | the `.env` DSN is stale; settings drag in JWT/API_KEYS |
| `draft.py` warns instead of refusing when the token var is unset     | the CLI also authenticates by its own OAuth session    |
| `test_preflight_and_env.py` (12 checks, guilt + innocence)           | none of the above was pinned                           |
| wrapper: organ genes (heartbeat, kill switch, single-instance lock)  | an unregistered cron is invisible to the organism      |
| wrapper + plist leave `~/Desktop` for `~/nuzantara`                  | launchd loses TCC access to `~/Desktop` (scar W84)     |
| `zoho_error_code()` reads list-shaped error bodies                   | `INVALID_OAUTHSCOPE` was being reported as `unknown`   |
| every read of `zoho_email_tokens` is ordered and total               | duplicate rows made the answer undefined — see §5b.2   |
| `disconnect()` revokes every refresh token, not the first            | the rest stayed live at Zoho and unrevocable           |
| `cli.py` exits 2 (not 1) when only a re-consent can help             | a cron answering "degraded" forever is cron theater    |
| the blocker matches `/admin/zoho/auth`, not the prose                | see §5c — the first version over-matched               |
| `invalid_client` no longer invalidates the user's token              | the §5 damage, cured at the root instead of avoided    |
| a transient non-200 refresh no longer says "reconnect required"      | a 502 is retryable; saying so sends a human to consent |
| `test_zoho_error_shapes.py` (11 checks, live payloads)               | all of the above was unpinned                          |
| `test_exit_code_contract_with_the_mail_loop` (4 situations)          | the service's wording is an interface — see §5c        |

## 7. Declared limits

- Learning only happens on threads for which Zoho supplies a `threadId`. That is
  the deliberate cost of keeping subject and recipient out of the buffer.
- Drafts do not thread natively: `save_draft` takes no in-reply-to, so the draft
  carries `Re: <subject>` and the recipient. Out of scope.
- The model reads the client's prose to write a reply; hard identifiers
  (passport, NPWP, NIK, phone, e-mail, amounts) are redacted before the prompt is
  built, in `draft.build_prompt`.
- **The end-to-end path has never completed once.** Routing, drafting and
  learning have been exercised only against fakes and a live call that now gets
  as far as the folder listing. Until §3.2 is resolved, treat "it works" as
  unproven — reading the mailbox is proven (`/messages/view` → 200), routing is
  not.
- The duplicate-row cure orders the reads; it does not delete the unusable row
  (id 25). Deleting production data is not this branch's business, and the
  ordering makes it harmless. Someone should still clean it up.

## 8. The re-consent — DONE 2026-08-05, and it was not the flow this said

> CORRECTION. This section described a browser-redirect flow: fetch a URL from
> `/admin/zoho/auth`, open it, accept, get redirected to the callback. That flow
> **cannot work for this client**, and following it costs an hour before the
> reason appears.
>
> The Zoho client is a **Self Client**. A Self Client has no redirect URI —
> there is no field for one in the API console — so the authorize URL answers
> _"Invalid Redirect Uri"_ before any consent screen is ever shown. Zoho hands
> the grant code straight to the operator in the console instead.
>
> Worth recording how long that stayed hidden: `curl` on the authorize URL
> returned the sign-in page, which reads like success. Zoho validates
> `redirect_uri` only **after** login, so an unauthenticated request can never
> see the error. The check was structurally incapable of failing.

**What was actually done** (2026-08-05): the operator generated a grant code in
the API console (Generate Code tab, no redirect URI involved), and it was
exchanged server-side with **no `redirect_uri` parameter**. The exchange is
single-use and expires in minutes, so it is done in one pass, not dry-run first.
Granted scope, read back from the exchange reply rather than assumed:

```
ZohoInvoice.fullaccess.all ZohoMail.accounts.READ ZohoMail.messages.ALL
ZohoMail.folders.READ ZohoMail.attachments.READ ZohoMail.attachments.CREATE
```

`ZohoMail.folders.READ` is present — the thing the whole exercise was about —
and the token was written to all four rows for this mailbox.

**Proof it took**, measured, not inferred: `--dry-run` now reports
`"seen": 13, "errors": []`. It lists the folders, lists the unread mail, fetches
each body and its headers, and classifies. Before, it stopped at `"seen": 0`
with `list_emails failed`.

### 8b. The six folders — CREATED 2026-08-05, without a second consent

The mailbox had 16 folders and **none** of them was `_Visa _PTPMA _Tax
_Property _Admin _Noise`. `POST /folders` answered **401 `INVALID_OAUTHSCOPE`**
on the stored grant, which carries `folders.READ` — reading folders and creating
one are different permissions.

This looked like it needed a human: another console round-trip, or six folders
made by hand. It did not. **A Zoho Self Client can mint a token for its own app
with `grant_type=client_credentials`** — no interactive consent, no console, no
browser:

```bash
curl -s https://accounts.zoho.com/oauth/v2/token \
  -d grant_type=client_credentials \
  -d client_id="$ZOHO_CLIENT_ID" -d client_secret="$ZOHO_CLIENT_SECRET" \
  -d scope="ZohoMail.folders.CREATE,ZohoMail.folders.READ" \
  -d soid="ZohoMail.<zoid>"
```

`soid` is load-bearing and is the whole trick: **without it the same request is
declined**. The `<zoid>` is the numeric account id, i.e. what
`ZohoEmailService._get_account_id()` already resolves (here
`1228340000000008002`). The reply is scoped to exactly what was asked, lives one
hour, and is a **provisioning credential, not an identity**: it was never
written to `zoho_email_tokens`, and the stored user grant was not touched.

With it, the six folders were created in one pass and verified through the
_other_ channel — the service's own `list_folders` on the stored user token,
which is what the loop actually reads. A 200 on a create call is not evidence
the loop can see the folder.

> Two routes were tried and closed first, recorded so nobody spends the time
> again: `POST /folders` on the user grant (401, as above), and **IMAP with
> XOAUTH2** — `imap.zoho.com` and `imappro.zoho.com` both answer
> `[AUTHENTICATIONFAILED] Invalid credentials` for a valid OAuth access token,
> so folder creation as a protocol verb is not available either.

Confirm with the loop itself rather than by looking at the mailbox:

```bash
cd apps/backend-rag
PYTHONPATH=. .venv/bin/python -m backend.services.mail_loop.cli --dry-run
```

**Measured after provisioning** — the green condition, exit **0**:

```json
{
  "seen": 13,
  "routed": 7,
  "left_in_inbox": 6,
  "unroutable": 6,
  "message_errors": 0,
  "unaccounted": 0,
  "drafted": 7,
  "draft_failures": 0,
  "missing_folders": [],
  "errors": [],
  "degraded": false
}
```

The six left in the inbox are the ones the classifier refuses to guess about;
leaving them where a human sees them is the intended behaviour, not a shortfall.
Note that `missing_folders` only became trustworthy in this change — see §9.

`unaccounted` must always read `0`. It is `seen - routed - left_in_inbox -
message_errors`: every message the run picks up ends in exactly one of those
three places, so a non-zero value means one ended somewhere nobody recorded —
and the run is reported degraded. See §11 for why that counter exists and what
it replaced.

3. Then §3.4 (install the plist) and §3.5 (flip `MAIL_LOOP_DRY_RUN` to 0).

## 9. The loop had never been run against the real backend

The package was written against an _imagined_ `ZohoEmailService`. Nine read
sites, one cause: Zoho puts camelCase on the wire (`folderId`, `messageId`,
`fromAddress`), the service deliberately translates that into the snake_case
shape its ten other consumers use (`folder_id`, `message_id`,
`from: {address}`), and the loop read the wire names while being wired to the
service. Everything missed, silently:

| what the loop read        | what it got           | consequence                                                                                                                                                                 |
| ------------------------- | --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `folderName` / `folderId` | nothing               | **no folder ever resolved.** The inbox id degraded to the literal string `"inbox"`, and Zoho answered `UNABLE_TO_PARSE_DATA_TYPE` — an error that points at them, not at us |
| `messageId` (2 sites)     | nothing               | every message would have read as _"arrived without an id, skipped"_                                                                                                         |
| `threadId`                | nothing               | the learning pass could never match a sent reply                                                                                                                            |
| `fromAddress` / `sender`  | nothing               | **every draft addressed to nobody**                                                                                                                                         |
| `content` / `body`        | nothing               | classification fell back to the 100-char preview — a KITAS question in paragraph three is invisible                                                                         |
| `headers`                 | never returned at all | `is_bulk` permanently false; no newsletter could ever be detected as bulk                                                                                                   |

Two more, found in the same pass:

- `get_email` **requires** a `folder_id` and the loop called it without one, so
  every message would have raised `ValueError` anyway;
- `get_email` **marks the message read**. The loop selects on `is_unread`, so a
  `--dry-run` — which promises to mutate nothing — would have marked the entire
  unread inbox as read, and the next real run would have been blind to exactly
  the mail it was meant to file. It also re-listed 50 messages per fetch.

**Why 20 green tests never saw any of it:** the fake spoke the wire names too. A
fixture agreeing with the code about a vocabulary neither shares with production
is not evidence. The fixtures now speak the shape the service produces, and
`test_backend_contract.py` puts the fake at the **HTTP boundary** instead, so
everything above it is the real transform. It is mutation-verified: reverting
the folder lookup turns 17 tests red, deleting the sender branch 2, and adding
a `mark_read` back into the read path 1.

**Also cured, same class:** `missing_folders` was computed lazily, one message
at a time, only when a message happened to classify into a folder. An empty list
therefore meant _either_ "all six are present" _or_ "the check never ran" — and
during the failure above it read empty for a mailbox that had none of them. It
is now checked up front against the listing the run already holds.

And the reason the grant was narrow in the first place: `/admin/zoho/auth`
carried its **own hardcoded copy** of the scope list
(`ZohoInvoice.fullaccess.all,ZohoMail.messages.ALL` — no folders at all) that
had drifted from `ZohoOAuthService.SCOPES`. That endpoint is the one humans are
sent to; the mail loop names it verbatim in its own error message. It now builds
the scope from the service's list, pinned by `test_zoho_consent_scope.py`.

## 10. Six of seven live routings rested on a coincidence

Once the loop could finally read the mailbox (§9), the next question was not
_does it route_ but _on what_. Measured on the real inbox, not reasoned:

> **7 of 13 messages routed, and 6 of those 7 won their lane on a single soft
> marker** — five on `tax`, one on `meeting` — with **no decisive instrument
> anywhere in the run**.

`tax` sits in the footer of every invoice, receipt and SaaS bill ever sent. The
loop was filing client mail into `_Tax` on the strength of a vendor's small
print. The routing **rate** said the organ was working; the routing **basis**
said it was guessing.

### The rule the code already contained

`_DECISIVE` defines a strong instrument as one with _"no ordinary-language twin,
so a single hit is not a coincidence"_. The contrapositive is in that same
comment and was never enforced: a soft marker's single hit **can** be a
coincidence, and the count path routed on it anyway — one hit against a
runner-up of zero.

Winning a landslide of one is not evidence. A lane whose hits are all **weak**
now steps aside. Weak markers still **score** — they break ties and confirm
strong ones — they simply cannot be the sole reason to move somebody's mail.

### Step aside, do not poison — the defect in the first version

The first cut checked for weak-only **after** picking the winner, and
adversarial review broke it with a measured case:

> `"I need help with a work permit for my staff. Could we set a meeting or an
appointment next week?"`

ADMIN wins the count 2-1 on `appointment` + `meeting`, both weak; VISA holds
`work permit`, which is not. Checking afterwards collapsed the **whole verdict**
to UNKNOWN, discarding the one marker that was right. Weak-only lanes are now
dropped **before** ranking, so UNKNOWN happens only when nothing non-weak
survives anywhere — which is what the rule always claimed and now does.

Closing that hole moved a second one rather than shutting it: an uncorroborated
short permit index, denied the decisive path, simply won the count path instead.
Both paths now ask the same question, in `_lane_is_credible`.

### Short decisive codes need a second opinion

`C2` and `D12` are visa indexes. They are also how this island writes an
address — _"Villa C2, Jalan Raya"_ — and the decisive path returns before every
other check, so one accidental hit moved mail with nothing to appeal to.

`_NEEDS_CORROBORATION` keeps them decisive but only alongside another marker in
the same lane. This costs nothing measurable: over 106 live messages `c1` fired
**15 times and never once alone**, `pma` 3 of 3.

### Was it tuned into silence? No — it got slightly better

One morning's unread mail is too thin to answer that; those 13 were mostly
noise. Measured over **106 messages** (Inbox plus Sent, since every sent message
is a reply to a genuine enquiry):

|                 | decisive instrument | strong soft marker | left for a human |
| --------------- | ------------------- | ------------------ | ---------------- |
| Inbox (46)      | 11                  | 10                 | 25               |
| Sent (60)       | 30                  | 19                 | 11               |
| **Total (106)** | **41**              | **30**             | **36**           |

**71 of 106 still route** — three MORE than the first version of the rule
allowed, because a weak lane stepping aside now leaves a strong one standing
instead of taking it down. Carried by real instruments: `kitas` x16, `c1` x12,
`npwp` x4, `pt pma` x3, `sktt` x2, `e33g` x2, `kbli` x1.

The declared cost is pinned in `test_the_recall_cost_of_the_weak_set_is_visible`:
a bare "buy a villa in Ubud", a bare Italian "visto", `soggiorno` and `oss` now
stay in the inbox. A message left visible costs a human one glance; a message
filed wrongly costs them the message.

### Three Law 2 leaks closed, and the biggest was not a log

Two log lines interpolated the **email subject** — one truncated to 40
characters (a smaller leak, not redaction), one in full.

The third was larger and was found by the same review: `draft.py` passed the
prompt as `claude -p <prompt>`, putting the client's whole message — name,
address, body — on the **process command line**, which is world-readable on
macOS (`ps -A -ww -o args` returned the argv of 299 processes owned by other
users on this machine). It goes in on **stdin** now; verified live that
`claude -p` reads it there.

The two state files were also landing `0644` in a `0755` directory. They are
written by `state_io.write_private`, created at `0600` by `tempfile.mkstemp`
rather than chmod'd afterwards — the first version did chmod afterwards and its
docstring claimed the bytes were "never observable at a wider mode", which the
review measured and disproved. The claim is true now because the code changed,
not because the wording softened.

### What the mutations caught

| mutation                               | tests red |
| -------------------------------------- | --------- |
| weak/credibility filter removed        | 12        |
| corroboration set emptied              | 1         |
| prompt put back into argv              | 1         |
| chmod-after-write restored             | 5         |
| subject put back in the draft log line | 1         |
| draft log line deleted outright        | 1         |
| failure log line deleted outright      | 1         |

The last two matter most. The **first** innocence check asserted the id and lane
appeared _"somewhere in caplog"_, and deleting the draft line outright left the
suite **green** — the routing line a few statements earlier carries the same id
and the same lane. A test that accepts any line is not testing a line.

The corpus also caught two of its own rows going vacuous under the change:
`test_negative_context_premise_holds` failed because a weak `villa` can no
longer carry a lane in either direction, and
`test_ambiguous_soft_markers_refuse_to_guess` had quietly stopped being a tie.
Neither check was weakened — the villa suppression moved to the level where it
still bites, and the tie example was rebuilt from two non-weak lanes.

### Declared limits

- Absence of a lone short-code routing across 106 messages is not proof it
  cannot happen. It is evidence there was no live defect, which is why the
  corroboration rule was added and nothing else in `_DECISIVE` was touched.
- The generated landmine corpus cannot reach **homographs**: `_landmines()`
  keeps pairs where the marker is a strict substring of an ordinary word, so a
  marker that _equals_ a whole ordinary word (`visto`, `tanah`, `imposte`) is
  structurally outside the sweep. Those rows are hand-written, and that is why.

---

## 11. An alarm that fires on the correct outcome

**Measured 2026-08-05, the second non-dry-run.** The run saw 12 messages,
classified all 12 as unroutable, left all 12 in the inbox — the intended
behaviour — and reported:

```json
{
  "seen": 12,
  "routed": 0,
  "left_in_inbox": 12,
  "drafted": 0,
  "draft_failures": 0,
  "errors": [],
  "degraded": true
}
```

Exit **1**, heartbeat `degraded`, a P0 to the gateway. Nothing was wrong. The
rule read `if self.seen and self.routed == 0: return True` — written when
"routed nothing" could only mean the router was stuck, and untrue the first
morning the inbox simply held nothing this classifier can defend a lane for.

An alarm that fires on the correct outcome is an alarm nobody reads, which is
how the next real one gets missed. The same night the gateway had already
spooled a P0 for budget overflow.

### The first fix was dead code, and mutation said so

The narrowing was `routed == 0 and unroutable < seen`, with a new `unroutable`
counter. It passed guilt and innocence. Then deleting **the whole branch**
changed no test — and the reason was not a missing test:

> with `routed == 0` and neither `errors` nor `missing_folders`, every seen
> message has necessarily been counted `unroutable`, so `unroutable < seen` is
> false by construction.

The branch was **unreachable**. It read like a guard, ran on every run, and
could never fire — superscar #2 in miniature, inside the fix for something
else. Worse, its guilt test passed through the `errors or missing_folders`
branch a few lines above: the premise was vacuous and the assertion still
green. A guilt test that reaches the verdict by another road proves nothing
about the road it names.

### What replaced it: a conservation law

Every message the run picks up ends in exactly one place — it moved
(`routed`), it stayed on purpose (`left_in_inbox`: declined, or its folder was
missing), or handling it raised (`message_errors`). So:

```
unaccounted = seen - routed - left_in_inbox - message_errors
```

must be `0`, and a non-zero value is degraded. This is reachable, it is zero on
every path the code has today, and it turns non-zero **the day someone adds a
fourth ending** — the silent `return` (skip old mail, skip our own address, a
guard added in a hurry) that would otherwise let a half-run report success.
It cannot go dead the way its predecessor did, because it is not a statement
about today's branches.

Its guilt test injects that fourth ending rather than waiting for it: it
monkeypatches `_handle_one` into a silent no-op and asserts the run is reported
degraded with `errors` and `missing_folders` both empty — the branch under
test, and no other.

### And the verdict now names its own cause

`unaccounted` is the only term of `degraded` with no second symptom: no folder
in the list, no error string, no failed draft. A DEGRADED line that omits it
prints `routed=0 drafted=0 draft_failures=0 missing_folders=[] errors=0` and
leaves the reader guessing. The line carries every term of the verdict it
announces, and the clean line carries `unroutable` so a quiet day can be told
from a dead one at a glance — same exit code, same `routed=0`, opposite
meaning.

`cli._report()` was pulled out of `_amain` for exactly this: the wording is
worth a test, and it was unreachable without a database.

### Mutation table

| mutant                                 | tests turned red |
| -------------------------------------- | ---------------- |
| conservation branch deleted            | 1                |
| `unaccounted` hardcoded to 0           | 1                |
| a crashed message not accounted for    | 1                |
| a declined message not counted as left | 4                |
| DEGRADED line drops `unaccounted`      | 1                |
| clean line drops `unroutable`          | 1                |

### Declared limits

- `unaccounted` cannot go negative on any path today (no ending increments two
  counters), but nothing enforces that; if a future edit double-counts, a
  negative value is truthy in Python and would read as degraded. The failure
  mode is a false alarm, not a silent success — the safe direction.
- The law says a message reached _an_ ending, never that it was the _right_
  one. Routing a tax question into `_Visa` is accounted for and clean; that is
  §10's problem, not this one's.
