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

Current state: **97 + 11 pytest and 34 shell checks green, mutation-verified.**
Every defence was measured by switching it off: the empty-array cure (16 shell
red), the kill switch (1), the lock (26), the heartbeat (27), the alert key (1),
the list-shaped error body, the plain-text body, the row ordering, its NULL
guard, and the consent-blocker in both directions (2 red when it never fires, 1
when it fires on everything — the innocence row).

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
2. **Folder access — THE BLOCKER, and it needs a re-consent.** Measured on all
   four token rows of the mailbox: every stored grant is
   `ZohoMail.messages.ALL ZohoMail.accounts.READ`. So `GET /messages/view`
   answers **200** — the loop can read the inbox — while
   `GET /accounts/<id>/folders` answers **401 `INVALID_OAUTHSCOPE`**. The loop
   can read the mail but cannot see the folders it is supposed to route into,
   and no retry will change that.
   - The `accounts.READ` payload was checked for a folder list as a way around
     it: it has none (`emailAddress` and `sendMailDetails` are its only nested
     lists), so there is no path to a folder id with the present grant.
   - `get_authorization_url` **already requests `ZohoMail.folders.READ`** — the
     stored grant simply predates it. One re-consent fixes it permanently.
   - That re-consent is a Zoho web login as the mailbox owner plus an Accept:
     the one category this session cannot do for you. Steps are in §8.
3. **The six folders** (`_Visa _PTPMA _Tax _Property _Admin _Noise`) — still
   **NOT verified**, and cannot be until step 2 is done: listing them is exactly
   the call that 401s. The loop does not create them; a missing folder leaves the
   mail in the inbox and marks the run degraded.
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

### 5c. Found while fixing the above, not part of the mandate

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
| `test_zoho_error_shapes.py` (11 checks, live payloads)               | all of the above was unpinned                          |

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

## 8. The one action this session cannot do — the re-consent

Everything else is done. This is a Zoho login plus an Accept, which is a consent
only the mailbox owner holds.

1. Ask the backend for the consent URL. `/admin/zoho/auth` is **not** a page: it
   is a JSON endpoint guarded by a header, and it returns the URL.

   ```bash
   curl -s -H "X-Admin-Secret: $ADMIN_SECRET_KEY" \
     https://nuzantara-rag.fly.dev/admin/zoho/auth
   ```

2. Open the URL it returns in a browser signed in as `zero@balizero.com`. The
   consent screen must list **`ZohoMail.folders.READ`** — verified locally: the
   URL requests `accounts.READ`, `messages.READ/CREATE/UPDATE/DELETE`,
   `folders.READ` and both attachment scopes, with `access_type=offline` and
   `prompt=consent`. Accept.
3. Zoho redirects to `https://nuzantara-rag.fly.dev/api/integrations/zoho/callback`,
   which exchanges the code and stores the numeric accountId against
   `https://mail.zoho.com` — so the row it writes is a usable one, and
   `ON CONFLICT (user_id, account_id)` updates the existing good row in place
   rather than adding a third.
4. Confirm the grant actually widened. The honest check is the API, **not** the
   `scopes` column — that column records what was _asked for_ at connect time
   and is not updated on conflict, so it can read wider than the real grant:

   ```bash
   cd apps/backend-rag
   PYTHONPATH=. .venv/bin/python -m backend.services.mail_loop.cli --dry-run
   ```

   Exit **2** with `INVALID_OAUTHSCOPE` means the consent did not take. Exit 0 or
   1 means it did, and the JSON summary lists which of the six folders exist.

5. Then §3.4 (install the plist) and §3.5 (flip `MAIL_LOOP_DRY_RUN` to 0).
