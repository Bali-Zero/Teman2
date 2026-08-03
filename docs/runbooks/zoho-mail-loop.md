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
| `scripts/test_zoho_mail_loop_wrapper.sh` | 24 checks on the wrapper's exit-code path  |

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

Current state: **93 pytest + 24 shell checks green, mutation-verified** — with a
defence disabled the corpus goes red (9 shell / 3 preflight / 2 draft).

```bash
cd apps/backend-rag
PYTHONPATH=. python3 -m pytest backend/tests/unit/services/mail_loop/ \
    -q --noconftest -c /dev/null
bash ../../scripts/test_zoho_mail_loop_wrapper.sh
```

## 3. The four steps that are NOT code — status

1. **Zoho OAuth token — VERIFIED, and it is the blocker.** A token row for
   `zero@balizero.com` exists (three, in fact: ids 2, 25, 28) with refresh tokens
   intact. It is the CLIENT credentials that are missing: `ZOHO_CLIENT_ID` /
   `ZOHO_CLIENT_SECRET` are absent from the Pro's environment and from
   `apps/backend-rag/.env`; the only pair on the machine lives in
   `~/.openclaw/workspace/.env.master` and Zoho answers `invalid_code` for all
   three tokens, i.e. it is a different Zoho app. The working pair is a Fly
   secret on `nuzantara-rag`, and Fly shows digests, never values. **See §5.**
2. **The six folders** (`_Visa _PTPMA _Tax _Property _Admin _Noise`) — NOT
   verified: listing them requires the credentials from step 1. The loop does not
   create them; a missing folder leaves the mail in the inbox and marks the run
   degraded. Note the granted scope set is `folders.READ` — creating them over
   the API is not possible with this consent even once it works, so this stays a
   Zoho-UI action.
3. **Install the plist** — the file is installed on the Pro but deliberately NOT
   loaded, because step 1 blocks it. Loading it today would buy a `p0` every
   morning saying what is already written here.
4. **Read a dry-run, then flip.** A dry-run was executed against the live
   mailbox and is reported in §5.

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
| `test_preflight_and_env.py` (8 checks, guilt + innocence)            | none of the above was pinned                           |

## 7. Declared limits

- Learning only happens on threads for which Zoho supplies a `threadId`. That is
  the deliberate cost of keeping subject and recipient out of the buffer.
- Drafts do not thread natively: `save_draft` takes no in-reply-to, so the draft
  carries `Re: <subject>` and the recipient. Out of scope.
- The model reads the client's prose to write a reply; hard identifiers
  (passport, NPWP, NIK, phone, e-mail, amounts) are redacted before the prompt is
  built, in `draft.build_prompt`.
- **The end-to-end path has never completed once.** Routing, drafting and
  learning have been exercised only against fakes and a live call that stopped at
  authentication. Until §3.1 is resolved, treat "it works" as unproven.
