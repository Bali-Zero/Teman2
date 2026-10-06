# Telegram bot token rotation (`@Balizerobot`)

Why: the fleet bot token answers 401 on Pro and Mini since 2026-09-22 (escalation
`healer-mini:telegram-bot-token-dead`). Every P0 lands in the gateway spool as `p0_unsent`.
Companion of `docs/runbooks/telegram-notification-gateway.md`. No token value belongs in
this file, in a shell history, in argv, or in any log: `${VAR:+SET}` probes only.

**The one human step** is BotFather. Everything below is one command per host.

## 1. Where the token lives (names and counts, 2026-10-06, `c8b495ff35`)

| Place                            | Name                                                                                                            | Rotated by                             |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| Host secrets file, Pro and Mini  | `TELEGRAM_BOT_TOKEN` in `~/.nuzantara-secrets.env`                                                              | `scripts/ops/rotate_telegram_token.sh` |
| M5                               | none by design: P0s relay `ssh pro` (`TG_RELAY_SSH=pro`)                                                        | nothing to do                          |
| launchd user env (boot copy)     | `launchctl setenv` by `scripts/launchd_env_loader.sh` (allowlist: bot token + 3 chat ids), refreshed every 12 h | rerun the loader, step 4               |
| GitHub Actions secret            | `TELEGRAM_BOT_TOKEN` (36 refs in 21 workflows; chat id is `TELEGRAM_OWNER_CHAT_ID`, unchanged)                  | `gh secret set`, step 5                |
| Fly app `nuzantara-rag`          | `TELEGRAM_BOT_TOKEN` (`apps/backend-rag/backend/app/core/config.py`)                                            | `fly secrets set`, step 6              |
| Old `.bak-*` of the secrets file | the dead token                                                                                                  | harmless once rotated; keep 0600       |

Consumers that only read the file or the env at each run (`scripts/tg_notify.py`,
`scripts/tg_digest_flush.py`, cron wrappers, `infra/healer/healer-run.sh`) pick the new value
up on their next tick. Re-find stray copies by file NAME only, never print matches:

```bash
grep -lE '^(export )?TELEGRAM_BOT_TOKEN=' ~/.nuzantara-secrets.env* 2>/dev/null
grep -l 'TELEGRAM_BOT_TOKEN' ~/Library/LaunchAgents/*.plist 2>/dev/null   # names only
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

```bash
cd ~/nuzantara   # Pro: ~/Desktop/nuzantara
scripts/ops/rotate_telegram_token.sh --dry-run   # which file and line would change, no value
scripts/ops/rotate_telegram_token.sh             # hidden prompt, shape check, atomic swap
scripts/ops/rotate_telegram_token.sh --check     # TELEGRAM_BOT_TOKEN: SET, shape: ok
```

The script requires the file to be mode 600 already (fix with `chmod 600` first), writes an
exclusive `.bak-<UTC>` at 0600, never traces or puts the token on argv, refuses a symlinked file,
zero or duplicate token lines, a file changed mid-run and any token that fails `^[0-9]{8,10}:[A-Za-z0-9_-]{35}$`. A second run with
the same token is a no-op. Shape only: it cannot know the token is live, step 7 proves that.

## 4. Refresh the launchd boot copy (macOS hosts, after each host swap)

```bash
bash scripts/launchd_env_loader.sh   # re-sources the file, setenv of the allowlist
```

Caveat, existing code: the loader hands the value to `launchctl setenv` as an argument, visible
to same-user `ps` for an instant. An inherited env value WINS over the file in `tg_notify.py`
(`resolve_credentials`): a long-running process or shell started before the rotation keeps the
old token until restarted. Check a shell with `${TELEGRAM_BOT_TOKEN:+SET}` and `unset` it first.

## 5. GitHub secret

```bash
gh secret set TELEGRAM_BOT_TOKEN -R Bali-Zero/Teman2   # paste at the prompt; nothing on argv
```

## 6. Fly (`nuzantara-rag`)

```bash
read -rs -p "token: " TG; echo
printf 'TELEGRAM_BOT_TOKEN=%s\n' "$TG" | fly secrets import -a nuzantara-rag; unset TG
```

`fly secrets import` reads stdin, so the value never reaches argv or history, and it sets one
release. This restarts the `api` machine: do it outside a client-facing window.

## 7. Verify

```bash
python3 - <<'PY'   # getMe with the host's own credentials; prints only ok + username
import json, sys, urllib.request
sys.path.insert(0, "scripts"); import tg_notify
t, _ = tg_notify.resolve_credentials()
try:
    r = json.load(urllib.request.urlopen(f"https://api.telegram.org/bot{t}/getMe", timeout=10))
    print("getMe ok:", r["ok"], r["result"]["username"])
except Exception as e:
    print("getMe FAILED:", type(e).__name__, getattr(e, "code", ""))
PY
python3 - <<'PY'   # direct send to the owner chat; the gateway would route a new p0 family to the board
import sys; sys.path.insert(0, "scripts"); import socket, tg_notify
t, c = tg_notify.resolve_credentials()
print("sent:", tg_notify.send_telegram(t, c, f"token rotation test {socket.gethostname()}"))
PY
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
   python3 - <<'PY'
   import sys; sys.path.insert(0, "scripts"); import tg_notify as t
   KEY = "cost-breaker-deadman:governance-mute"
   sp = t._spool_dir()
   with t._spool_lock(sp):          # same flock (.spool.lock) every gateway writer takes
       s = t._load_state(sp)
       print("removed" if s.get("dedup", {}).pop(KEY, None) else "absent")
       t._save_state(sp, s)
   PY
   ```

2. **Drain the spool.** Count first, render, then flush (one grouped message, grouped by source, cut at 3500 characters;
   unsent P0 lines carry a red mark, and a long spool can truncate them, so read the dry run):

   ```bash
   S=~/.organism/tg_spool
   grep -c '"p0_unsent": true' $S/pending.jsonl; wc -l < $S/pending.jsonl
   python3 scripts/tg_digest_flush.py --dry-run | head -50   # read before sending
   python3 scripts/tg_digest_flush.py                         # send; failure keeps the spool, exit 3
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
