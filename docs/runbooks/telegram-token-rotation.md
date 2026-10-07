# Telegram bot token rotation (`@Balizerobot`)

Why: the fleet bot token answers 401 on Pro and Mini since 2026-09-22 (escalation
`healer-mini:telegram-bot-token-dead`). Every P0 lands in the gateway spool as `p0_unsent`.
Companion of `docs/runbooks/telegram-notification-gateway.md`. No token value belongs in
this file, in a shell history, in argv, or in any log: `${VAR:+SET}` probes only.

**The one human step** is BotFather. Everything below is one command per host.

**Conventions.** The blocks are pasted into interactive zsh (M5, Pro: `interactivecomments` off)
or bash 3.2, with or without bracketed paste. So: no `#` inside a block (zsh reads it as a word:
a parse error or extra arguments), explanations stay in prose; no `exit` (it closes the owner's
terminal or ssh session); every multi-line step is ONE `{ …; }` compound command, so nothing runs
before the whole block is read and no `read` can swallow the next pasted line; tokens are read
with `IFS= read -rs` and never reach argv (step 4's loader is the declared exception, see its
caveat). `scripts/ops/test_runbook_blocks.sh` (CI `tg-gateway`) pastes every block whole and
line by line in both shells and fails on any breach.

## 1. Where the token lives (names and counts, 2026-10-06, `c8b495ff35`)

| Place                            | Name                                                                                                            | Rotated by                             |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| Host secrets file, Pro and Mini  | `TELEGRAM_BOT_TOKEN` in `~/.nuzantara-secrets.env`                                                              | `scripts/ops/rotate_telegram_token.sh` |
| M5                               | none by design: P0s relay `ssh pro` (`TG_RELAY_SSH=pro`)                                                        | nothing to do                          |
| launchd user env (boot copy)     | `launchctl setenv` by `scripts/launchd_env_loader.sh` (allowlist: bot token + 3 chat ids), refreshed every 12 h | rerun the loader, step 4               |
| GitHub Actions secret            | `TELEGRAM_BOT_TOKEN` (36 refs in 21 workflows; chat id is `TELEGRAM_OWNER_CHAT_ID`, unchanged)                  | `gh secret set`, step 5                |
| Fly app `nuzantara-rag`          | `TELEGRAM_BOT_TOKEN` (`apps/backend-rag/backend/app/core/config.py`)                                            | `fly secrets import`, step 6           |
| Old `.bak-*` of the secrets file | the dead token                                                                                                  | harmless once rotated; keep 0600       |

Consumers that only read the file or the env at each run (`scripts/tg_notify.py`,
`scripts/tg_digest_flush.py`, cron wrappers, `infra/healer/healer-run.sh`) pick the new value
up on their next tick. Re-find stray copies by file NAME only, never print matches:

```bash
{ grep -lE '^(export )?TELEGRAM_BOT_TOKEN=' ~/.nuzantara-secrets.env* 2>/dev/null
grep -l 'TELEGRAM_BOT_TOKEN' ~/Library/LaunchAgents/*.plist 2>/dev/null; }
```

A plist hit means a daemon with an embedded or inherited value: decide per file, do not
bulk-restart. Other apps (`apps/cell`, `apps/evaluator`, `apps/mata-garuda`, `apps/organism`,
`apps/wa-mirror`, `apps/remediator`, `apps/bali-intel-scraper`) reference the variable by name
only; `scripts/lint_telegram_tokens.py` keeps any literal out of the tree.

## 2. Owner: new token from BotFather

- Account that owns `@Balizerobot`: **TO BE CONFIRMED BY THE OWNER** (placeholder).
- The old token was exposed in a public document on 2026-08-13 and BotFather answers only the
  creating account. If that account is recoverable: `/revoke` on `@Balizerobot`, copy the new token.
  If not: create a NEW bot, then `/start` it from the owner chat so it may write there. A new bot
  keeps `TELEGRAM_OWNER_CHAT_ID` valid; only its username in docs and old links changes.
- Never paste the token into chat, a ticket, a PR or a shell argument. It goes only into the
  hidden prompts below.

## 3. Per host (Pro, then Mini; run ON the host)

The checkout is `~/nuzantara` on every host (on Pro `~/Desktop/nuzantara` is a symlink to it).
The block shows which file and line would change (no value), prompts invisibly for the new token
and swaps it atomically after a shape check, then reports `TELEGRAM_BOT_TOKEN: SET, shape: ok`.

```bash
{ cd ~/nuzantara &&
scripts/ops/rotate_telegram_token.sh --dry-run &&
scripts/ops/rotate_telegram_token.sh &&
scripts/ops/rotate_telegram_token.sh --check; }
```

The script requires the file to be mode 600 already (fix with `chmod 600` first), writes an
exclusive `.bak-<UTC>` at 0600, never traces or puts the token on argv, refuses a symlinked file,
zero or duplicate token lines, a file changed mid-run and any token that fails `^[0-9]{8,10}:[A-Za-z0-9_-]{35}$`. A second run with
the same token is a no-op. Shape only: it cannot know the token is live, step 7 proves that.

## 4. Refresh the launchd boot copy (macOS hosts, after each host swap)

This re-sources the secrets file and sets only the loader's allowlist.

```bash
bash scripts/launchd_env_loader.sh
```

Caveat, existing code: the loader hands the value to `launchctl setenv` as an argument, visible
to same-user `ps` for an instant. An inherited env value WINS over the file in `tg_notify.py`
(`resolve_credentials`): a long-running process or shell started before the rotation keeps the
old token until restarted. Check a shell with `${TELEGRAM_BOT_TOKEN:+SET}` and `unset` it first.

## 5. GitHub secret

Paste the token only at the hidden prompt; it is not placed in argv.

```bash
gh secret set TELEGRAM_BOT_TOKEN -R Bali-Zero/Teman2
```

## 6. Fly (`nuzantara-rag`)

```bash
{ printf 'token: ' >&2; IFS= read -rs TG; echo >&2
  if [ -n "$TG" ]; then printf 'TELEGRAM_BOT_TOKEN=%s\n' "$TG" | fly secrets import -a nuzantara-rag
  else echo "empty: nothing imported" >&2; fi; unset TG; }
```

`fly secrets import` reads stdin, so the value never reaches argv or history, and it sets one
release. This restarts every machine of the app across process groups `api`, `rag`, and `drive`:
do it outside a client-facing window. Do not use `read -p` for the prompt: in zsh (the login shell
on M5 and Pro) `-p` means coprocess, the read fails, and the pipe would import an empty
`TELEGRAM_BOT_TOKEN=`.

Declared limits of `rotate_telegram_token.sh` (known, not fixed here):

- Under bash 3.2 (`/bin/bash` on macOS) the here-string that carries the token to awk is backed by an
  unlinked 0600 file in the temp dir for a moment. Never argv, env or log.
- A write landing between the final `cksum` re-check and the `mv` is lost. No writer of the secrets file is
  known besides humans.
- A secrets file without a trailing newline is refused ("line count differs"). An inline comment after
  the value is dropped and quoting is normalised on rewrite.
- A new bot (BotFather account lost) also needs the Fly webhook secret and webhook re-registration;
  this runbook does not cover that.

## 7. Verify

The first call is `getMe` with the host's own credentials and prints only ok and the username; the
second sends directly to the owner chat (through the gateway a new p0 family would go to the board).

```bash
{ python3 - <<'PY'
import json, sys, urllib.request
sys.path.insert(0, "scripts"); import tg_notify
t, _ = tg_notify.resolve_credentials()
try:
    r = json.load(urllib.request.urlopen(f"https://api.telegram.org/bot{t}/getMe", timeout=10))
    print("getMe ok:", r["ok"], r["result"]["username"])
except Exception as e:
    print("getMe FAILED:", type(e).__name__, getattr(e, "code", ""))
PY
python3 - <<'PY'
import sys; sys.path.insert(0, "scripts"); import socket, tg_notify
t, c = tg_notify.resolve_credentials()
print("sent:", tg_notify.send_telegram(t, c, f"token rotation test {socket.gethostname()}"))
PY
}
```

The test must print `sent: True` (with `TG_DRY_RUN` set it only spools, so unset it first) and the message must arrive in the owner chat.
`tg_notify.py --selftest` is hermetic (fake spool, fake world): it proves the gateway code, NOT the
token, so it is not a verification of this rotation. GitHub side: run the `telegram-secret-healthcheck`
workflow with `send_test_message=true`. Healer side: the `healer-mini:telegram-bot-token-dead`
escalation must close on its next tick.

## 8. After the token is live (a Claude session, not the owner)

1. **Reset the dead-man dedup key.** The cost-breaker dead-man alert has been muted by the
   gateway ladder while the token was dead. Remove only that key, under the spool flock:

   ```bash
   { python3 - <<'PY'
   import sys; sys.path.insert(0, "scripts"); import tg_notify as t
   KEY = "cost-breaker-deadman:governance-mute"
   sp = t._spool_dir()
   with t._spool_lock(sp):
       s = t._load_state(sp)
       print("removed" if s.get("dedup", {}).pop(KEY, None) else "absent")
       t._save_state(sp, s)
   PY
   }
   ```

   The lock in that block is the same `.spool.lock` flock taken by every gateway writer.

2. **Drain the spool.** Count first, render, then flush (one grouped message, grouped by source, cut at 3500 characters;
   unsent P0 lines carry a red mark, and a long spool can truncate them, so read the dry run):

   ```bash
   { S=~/.organism/tg_spool
   grep -c '"p0_unsent": true' "$S/pending.jsonl"; wc -l < "$S/pending.jsonl"
   python3 scripts/tg_digest_flush.py --dry-run | head -50; unset S; }
   ```

   Read that output, then send. A failed send keeps the spool and exits 3.

   ```bash
   python3 scripts/tg_digest_flush.py
   ```

   To discard instead of sending: archive, never delete (`archive/` is the history): move
   `pending.jsonl` into `archive/` under the same flock, then `: > pending.jsonl`.

3. **Re-derive the lost pajak alerts** (2026-09-25T16Z to 2026-10-06T02Z; the gateway answered
   "deduped" for a whole set and the items were marked seen undelivered). The durable traces are
   the per-item delivery state `~/.intel_scraper/pajak_delivery_state.json` (`first_seen`, no
   `delivered` flag) and the spool `archive/` (if the alert text was archived there). List only the
   public regulation titles and `pajak.go.id` URLs from those two sources into a plain list for
   the owner. Never paste spool lines wholesale: other sources share the same files.

## Owed rows

| Row                                                              | Owner                                                 |
| ---------------------------------------------------------------- | ----------------------------------------------------- |
| BotFather token, which account owns the bot                      | the owner                                             |
| Steps 3 to 6 on Pro, Mini, GitHub, Fly (one hidden prompt each)  | the owner, or a session the owner hands the prompt to |
| Step 7 verification, step 8 dedup reset, spool drain, pajak list | a Claude session once the token is live               |
