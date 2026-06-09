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

## Notes / caveats

- The bot answers grounded on the Bali Zero visa knowledge base. On low confidence
  (ABSTAIN) it does NOT invent — it asks the user to contact the Bali Zero team.
- The visa-oracle backend has no Ukrainian in its language map (ru/en/id/...), so it
  may answer in Russian; `claude` rewrites the result into Ukrainian.
- **Rotate the token** (`/revoke` in @BotFather) if it was ever pasted in plaintext
  anywhere, then update `~/.ukrbali-bot.env`.
- Requires the `claude` CLI authenticated on Pro (MAX-plan OAuth). If `claude -p`
  fails, the bot falls back to the raw RAG answer (possibly Russian).
