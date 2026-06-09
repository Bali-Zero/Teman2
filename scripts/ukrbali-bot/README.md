# @UkrBaliVisaAssistant_bot — Pro deploy (24/7)

Telegram visa assistant for Bali Zero (Ukrainian). Pipeline:

```
user message
  -> Nuzantara visa-oracle RAG  (grounded facts + sources + confidence)
  -> claude CLI rewrites into natural Ukrainian (no invented facts)
  -> reply in Telegram
```

No backend auth needed — `/api/v1/visa-oracle/chat` is a public endpoint.
The "brain" rewrite uses the local `claude` CLI (MAX-plan OAuth, per CLAUDE.md).

## Files

- `ukrbali_bot.py` — the bot (stdlib only; token read from env `UKRBALI_BOT_TOKEN`)
- `run.sh` — launchd wrapper (sources the secret env file, sets PATH, execs python)
- `com.balizero.ukrbali-bot.plist` — LaunchAgent (KeepAlive=true daemon)

## Install on Pro (one time)

```bash
# 1. Pull this branch on Pro
cd ~/Desktop/nuzantara && git fetch origin && git checkout claude/peaceful-feynman-en3bm5 && git pull

# 2. Put the bot token in a 0600 env file (NEVER in the plist / repo — security cicatrix)
echo 'export UKRBALI_BOT_TOKEN=<YOUR_BOTFATHER_TOKEN>' > ~/.ukrbali-bot.env
chmod 600 ~/.ukrbali-bot.env

# 3. Logs dir
mkdir -p ~/logs

# 4. Smoke test (Ctrl-C after you see "live (Nuzantara RAG)")
chmod +x scripts/ukrbali-bot/run.sh
bash scripts/ukrbali-bot/run.sh

# 5. Install the LaunchAgent
cp scripts/ukrbali-bot/com.balizero.ukrbali-bot.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.ukrbali-bot.plist
launchctl kickstart -k gui/$(id -u)/com.balizero.ukrbali-bot

# 6. Verify
launchctl print gui/$(id -u)/com.balizero.ukrbali-bot | grep -E 'state|last exit'
tail -f ~/logs/ukrbali-bot.log    # expect: live (Nuzantara RAG)
```

## Manage

```bash
# stop / start
launchctl bootout gui/$(id -u)/com.balizero.ukrbali-bot
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.ukrbali-bot.plist

# restart
launchctl kickstart -k gui/$(id -u)/com.balizero.ukrbali-bot

# logs
tail -f ~/logs/ukrbali-bot.{log,err}
```

## Standalone deploy on Railway (no Pro, no Nuzantara)

The bot is fully self-contained: it needs only the bot token, the Google Doc, and
your own Claude token. `Dockerfile` builds a container (Node + `claude` CLI + Python).

**You need two secrets:**
1. `UKRBALI_BOT_TOKEN` — from @BotFather.
2. `CLAUDE_CODE_OAUTH_TOKEN` — your long-lived Claude token. Generate once on any
   computer that has Claude Code: run `claude setup-token` and copy the value.

**Steps (from the phone):**
1. Put these files in a GitHub repo you own (e.g. a new repo `ukrbali-bot`):
   `ukrbali_bot.py`, `Dockerfile`. (Nothing else is required for the container.)
2. On [railway.app](https://railway.app): New Project → Deploy from GitHub repo → pick your repo.
   If the files are in a subfolder, set the service **Root Directory** to that folder.
3. Railway → your service → **Variables** → add:
   - `UKRBALI_BOT_TOKEN` = `<botfather token>`
   - `CLAUDE_CODE_OAUTH_TOKEN` = `<your claude setup-token value>`
   (optional: `UKRBALI_CLAUDE_MODEL=claude-fable-5`, `UKRBALI_USE_RAG=0` — already defaults)
4. Deploy. Check **Deploy Logs** for `live (brain=catalog, model=claude-fable-5)`.
5. Message the bot in Telegram to confirm.

Railway keeps the worker running 24/7 and restarts it on crash. Editing the Google
Doc + redeploy (or restart) refreshes the catalog.



By default (`UKRBALI_USE_RAG=0`) the bot answers **only** from the Bali Zero
product catalog (a Google Doc), matching its tone of voice (Ukrainian, friendly,
emojis, exact prices). The doc is fetched live at startup from:

- `UKRBALI_KNOWLEDGE_DOC_ID` (default: the Bali Zero catalog doc)
- export URL: `https://docs.google.com/document/d/<id>/export?format=txt`

Edit the Google Doc → restart the bot → changes take effect. No redeploy, no commit.
A local cache `knowledge.md` is written next to the script as a fallback (gitignored).
The doc must be link-accessible ("anyone with the link can view") for the live fetch.

## Modes

- **Catalog** (`UKRBALI_USE_RAG=0`, default) — grounded on the Google Doc catalog + its tone.
- **Zantara RAG** (`UKRBALI_USE_RAG=1`) — Nuzantara visa-oracle RAG + Ukrainian rewrite.

Set in `~/.ukrbali-bot.env`, e.g. `echo 'export UKRBALI_USE_RAG=0' >> ~/.ukrbali-bot.env`, then restart.

## Model

The brain runs on **Fable 5** by default (`UKRBALI_CLAUDE_MODEL=claude-fable-5`).
Override e.g. `export UKRBALI_CLAUDE_MODEL=claude-opus-4-8` in `~/.ukrbali-bot.env`.
Requires the `claude` CLI on Pro to have access to that model (MAX-plan OAuth).

- The bot keeps per-chat conversation memory (last 8 msgs / 500 chats); `/reset` clears it.
- The visa-oracle backend has no Ukrainian in its language map (ru/en/id/...), so it
  may answer in Russian; `claude` rewrites the result into Ukrainian.
- **Rotate the token** (`/revoke` in @BotFather) if it was ever pasted in plaintext
  anywhere, then update `~/.ukrbali-bot.env`.
- Requires the `claude` CLI authenticated on Pro (MAX-plan OAuth). If `claude -p`
  fails, the bot falls back to the raw RAG answer (possibly Russian).
