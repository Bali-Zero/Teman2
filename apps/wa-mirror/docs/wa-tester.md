# wa-tester — WhatsApp phone-test CLI for the Zantara bot

## What it is

`wa-tester` is a standalone, on-demand CLI that runs end-to-end test
batteries against the Zantara WhatsApp bot (**+62 821 3465 159**) by sending
real WhatsApp messages **from Zero's own number (+62 822 3010 2328)** and
recording the bot's replies. It lets the team run a battery of real
questions through the real WhatsApp channel — the same path a client uses —
instead of only hitting the backend RAG API directly.

It lives at:

- `apps/wa-mirror/scripts/wa-tester-core.ts` — pure logic (allowlist guard,
  battery validation, quiet-period reply collection, transcript assembly).
  Fully unit-tested, no network/socket code.
- `apps/wa-mirror/scripts/wa-tester.ts` — the CLI entrypoint. Owns the live
  Baileys socket (connect, pair, send, listen).
- `apps/wa-mirror/scripts/wa-tester.sh` — thin wrapper (`PATH` fixup +
  `npx tsx`).

## It is NOT a mirror session — read this before touching anything

`apps/wa-mirror` is architected as a **read-only** mirror (`bridge/session.ts`
header: _"we never call sock.sendMessage"_) that connects each Bali Zero team
member's WhatsApp account and logs their conversations into the CRM. It is
managed by `scripts/start-one.sh` / `start-all.sh`, tracked in
`~/.wa-mirror.accounts.json`, supervised by `scripts/supervise-launcher.sh`,
and kept alive by a LaunchAgent plist.

`wa-tester` is architecturally the opposite of that on purpose:

|                         | wa-mirror (bridge)                | wa-tester                                                             |
| ----------------------- | --------------------------------- | --------------------------------------------------------------------- |
| Sends messages?         | Never (read-only)                 | Yes — that's the whole point                                          |
| Who's account?          | Every team member (9 sessions)    | ONLY Zero's own number, ad-hoc                                        |
| Roster?                 | `~/.wa-mirror.accounts.json`      | none — not an account, not a session                                  |
| Daemon/cron/plist?      | Yes (supervised, always-on)       | **No — CLI only, exits when done**                                    |
| Writes to Postgres/CRM? | Yes (every message)               | **No — zero DB dependency**                                           |
| Auth state path         | `apps/wa-mirror/sessions/<e164>/` | `~/.wa-tester/state/<e164>/` (separate tree, never under `sessions/`) |

**wa-tester must never be added to the accounts roster, never get a plist,
never run on a schedule, and its auth-state directory must never live under
`apps/wa-mirror/sessions/`.** If it did, the supervisor / `start-all.sh`
would try to manage it as a 10th read-only mirror session, which would be
both wrong (it sends messages) and a privacy violation (mirroring captures
_all_ of Zero's personal chats, not just the test conversation with the
bot).

`bridge/` itself is never modified by wa-tester — the two pure helpers it
imports (`isTerminalCloseCode`, `mapCloseReason` from `bridge/session.ts`)
are read-only, DB-agnostic close-code classifiers reused as-is.

## THE one rule: hardcoded recipient allowlist

wa-tester runs from Zero's **real** WhatsApp number. The one thing that
makes that safe is that it can never message anyone except the Zantara bot.

- The recipient JID is a compile-time constant in
  `wa-tester-core.ts` (`BOT_JID` / `BOT_PHONE_E164`, +62 821 3465 159).
  **No CLI flag, environment variable, or config file can change it.**
- Every battery file is validated **before any socket connects and before
  any message is sent** (`validateBattery` in `wa-tester-core.ts`). The
  validator scans both the battery root and every question for any
  recipient-lookalike field (`to`, `recipient`, `jid`, `phone`, `number`,
  `target`, `send_to`); if present and it does not resolve to the bot
  number, the whole run is refused with a hard error.
- The guard is covered by guilt + innocence tests in
  `tests/wa-tester-core.test.ts` (per the repo's guard-conformance
  discipline — `.claude/rules/cicatrix-superscar.md` family #3): a battery
  naming another number is refused, a normal battery (or one whose
  recipient field happens to already match the bot) passes.

## Pairing runbook

Auth state is a separate Baileys identity from any wa-mirror session —
pairing has to happen once, interactively, from Zero's phone.

```bash
cd apps/wa-mirror
bash scripts/wa-tester.sh --pair
```

1. A QR code is written to `/tmp/qr-tester-6282230102328.png` and also
   printed to the terminal as ASCII.
2. On Zero's phone: **WhatsApp → Settings → Linked Devices → Link a
   Device**, scan it.
3. WhatsApp always bounces the connection once right after pairing
   (Baileys close code 515, `restartRequired`) — wa-tester reconnects
   automatically exactly once and confirms the session is stable before
   exiting `0`. If it does not stabilize, re-run `--pair`.
4. Auth state is now persisted under `WA_TESTER_STATE_DIR` (default
   `~/.wa-tester/state/+6282230102328/`, `chmod 0700`). Nothing else needs
   to run — there is no daemon to start.

**Re-pairing** (device unlinked, or moving to a fresh state dir): delete the
state directory and run `--pair` again:

```bash
rm -rf ~/.wa-tester/state/+6282230102328
bash scripts/wa-tester.sh --pair
```

**Check pairing/connectivity without sending anything:**

```bash
bash scripts/wa-tester.sh --status
```

Prints one line — `NOT_PAIRED`, `PAIRED_AND_CONNECTED — <jid>`, or
`PAIRED_BUT_CONNECT_FAILED — <reason>` — with exit codes `1`/`0`/`2`
respectively. Sends no messages.

## Battery format

A battery is a JSON file with a list of questions to fire at the bot in
order, one at a time:

```json
{
  "questions": [
    { "id": "b211a-basics", "text": "Ciao, come funziona il B211A?" },
    { "id": "kitas-cost", "text": "Quanto costa il KITAS investor?" }
  ],
  "reply_timeout_s": 90,
  "inter_question_delay_s": 20
}
```

- `questions[].id` — unique string, used to key the transcript.
- `questions[].text` — the exact message sent to the bot.
- `reply_timeout_s` (default `90`) — hard cap: if zero replies arrive within
  this window, the question is recorded with 0 replies and the run moves on.
  Also a safety cap that stops collection even mid-conversation.
- `inter_question_delay_s` (default `20`) — pause between questions.
- Any field named `to`/`recipient`/`jid`/`phone`/`number`/`target`/`send_to`
  at the battery root or on a question is checked against the hardcoded bot
  number — see "THE one rule" above.

Run it:

```bash
bash scripts/wa-tester.sh --send-battery battery.json --out transcript.json
```

For each question, wa-tester sends the text to the bot, then collects
**every** reply message until either the `reply_timeout_s` cap is hit or a
**10-second quiet period** elapses after at least one reply has arrived
(handles multi-message bot answers that arrive as several bubbles).

Output transcript (`--out`, default `/tmp/wa-tester-transcript-<ts>.json`):

```json
{
  "battery_file": "/abs/path/battery.json",
  "bot_jid": "628213465159@s.whatsapp.net",
  "started_at": "2026-...",
  "finished_at": "2026-...",
  "questions": [
    {
      "id": "b211a-basics",
      "text": "Ciao, come funziona il B211A?",
      "sent_at": "2026-...",
      "replies": [
        { "text": "...", "timestamp": "2026-...", "latency_ms": 1832 }
      ],
      "reply_count": 1,
      "first_reply_latency_ms": 1832
    }
  ],
  "summary": { "total_questions": 2, "questions_with_zero_replies": 0 }
}
```

wa-tester exits non-zero if **any** question got zero replies —
`summary.questions_with_zero_replies > 0` — so it can gate a CI-style check
or a Telegram alert on a real end-to-end silence.

## Privacy rails

- The live socket subscribes to `messages.upsert` and processes **only**
  events whose `remoteJid` equals the hardcoded bot JID; every other chat
  (including group chats, status updates, and any of Zero's real personal
  conversations) is ignored in the handler and never logged, printed, or
  written to the transcript.
- Auth state directory is `chmod 0700` on creation (repo scar family #4 —
  secret-in-the-clear; Baileys auth state includes Signal session keys).
- No Postgres/CRM writes, no Telegram alerts, no EventBus emission — the
  tester has zero footprint outside its own state dir and the transcript
  file it's told to write.

## Runtime notes

- Runtime is the Pro machine. Non-interactive `ssh` sessions don't source
  the shell rc that puts Homebrew `node`/`npm` on `PATH` — `wa-tester.sh`
  prepends `/opt/homebrew/bin` explicitly so it works over `ssh pro
'bash apps/wa-mirror/scripts/wa-tester.sh --status'` without a login
  shell.
- Same Baileys version as the mirror (`@whiskeysockets/baileys@7.0.0-rc13`,
  reused from `package.json` — no second Baileys dependency).
