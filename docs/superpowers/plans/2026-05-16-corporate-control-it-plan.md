# Corporate Control System — IT Implementation Plan (Slim)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Three lightweight IT controls for 10 Bali Zero employees — DNS logging, Android MDM, WA Linked Devices audit bot. Zero additional recurring cost.

**Architecture:** Three independent pieces, no code dependencies between them. (1) NextDNS at office router — pure config, no code; (2) Miradore Free MDM — pure config, physical device enrollment; (3) Telegram bot — one Python script running as LaunchAgent on Pro.

**Tech Stack:** NextDNS (free) · Miradore Free (free, ≤50 devices) · Python 3.11 · python-telegram-bot 20.x

**Out of scope (deferred or dropped):**
- Chrome Enterprise Core — marginal gain, dropped
- AppLocker — dropped
- CRM anomaly detector — dropped
- Drive external share alert — dropped
- wa-mirror (WA→DB bridge) — separate Codex project, see prompt in session history

---

## Task 1: NextDNS — office router DNS logging

**Files:** none (NextDNS console + router admin panel)

- [ ] **Step 1: Create NextDNS account**

  Go to `https://nextdns.io` → sign up with `zero@balizero.com` → create profile named `BaliZero-Office`.

  Free tier: 300,000 queries/month — sufficient for 10 employees on office WiFi.

- [ ] **Step 2: Configure log-only (no blocking except one)**

  NextDNS profile:
  - Security tab → disable all blocking toggles
  - Privacy tab → disable all blocklists
  - Logs tab → enable logging → retention 30 days
  - Denylist tab → add `web.whatsapp.com` (WA Web — only blocked item; WA Desktop app is separate and allowed)

- [ ] **Step 3: Point office router DNS to NextDNS**

  Get the two NextDNS DNS IPs from the Setup tab.

  Router admin panel (typically `192.168.1.1`) → WAN DNS settings → replace ISP DNS with NextDNS IPs.

  If router does not support WAN DNS override: set DNS on the corporate WiFi SSID DHCP settings instead.

- [ ] **Step 4: Verify**

  From a device on office WiFi, visit `https://test.nextdns.io` → should display "You are using NextDNS".

- [ ] **Step 5: Weekly digest cron**

  Create `~/scripts/nextdns-weekly-digest.sh`:
  ```bash
  #!/bin/bash
  # NextDNS weekly DNS digest → Telegram. Runs Monday 09:00 WITA via crontab.

  NEXTDNS_API_KEY="${NEXTDNS_API_KEY}"
  PROFILE_ID="${NEXTDNS_PROFILE_ID}"
  BOT_TOKEN="${TELEGRAM_BOT_TOKEN}"
  CHAT_ID="${TELEGRAM_OWNER_CHAT_ID}"

  DOMAINS=$(curl -s \
    -H "X-Api-Key: ${NEXTDNS_API_KEY}" \
    "https://api.nextdns.io/profiles/${PROFILE_ID}/logs/toplists/domains?from=-7d&limit=15" \
    | python3 -c "
  import sys, json
  data = json.load(sys.stdin)
  lines = [f\"{i['name']}: {i['count']}\" for i in data.get('data', [])[:15]]
  print('\n'.join(lines))
  ")

  curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
    -d "chat_id=${CHAT_ID}&text=📊 NextDNS digest (7d):%0A${DOMAINS}"
  ```

  ```bash
  chmod +x ~/scripts/nextdns-weekly-digest.sh
  ```

  Add `NEXTDNS_API_KEY` and `NEXTDNS_PROFILE_ID` to `~/.nuzantara-secrets.env` after getting them from `https://nextdns.io/account` and the profile URL.

  Add to crontab (`crontab -e`):
  ```
  0 1 * * 1 source ~/.nuzantara-secrets.env && /Users/nuzantara/scripts/nextdns-weekly-digest.sh
  ```
  (01:00 UTC = 09:00 WITA)

---

## Task 2: Miradore Free MDM — enroll 15 Android phones

**Files:** `research/hr/mdm-enrolled-devices.md` (gitignored)

- [ ] **Step 1: Create Miradore account**

  Go to `https://www.miradore.com` → Start for free → sign up `zero@balizero.com` → company "Bali Zero".

  Free tier: 50 devices. 15 phones = well within limit.

- [ ] **Step 2: Create Work Profile enrollment profile**

  Miradore console → Devices → Enrollment → Android → **Work Profile** (not Device Owner).

  Name: `BaliZero-Staff-Android`.

  Policies:
  - Screen lock: PIN minimum 6 digits → required
  - Device encryption → required
  - Unknown sources (sideloading) → blocked in work profile
  - Remote wipe scope → Work Profile only (personal data untouched)

- [ ] **Step 3: Generate enrollment QR code**

  Enrollment profile → Generate QR code → print or display on screen.

- [ ] **Step 4: Enroll all 15 phones**

  On each corporate Android phone:
  1. Settings → Accounts → Add Work Account → scan QR code
  2. Accept Work Profile setup
  3. Verify in Miradore console: device shows "Enrolled" + "Compliant"

  Log each device (add to `.gitignore` first):

  ```bash
  echo "research/hr/mdm-enrolled-devices.md" >> .gitignore
  echo "research/hr/sim-registry.md" >> .gitignore
  git add .gitignore && git commit -m "chore: gitignore HR sensitive files"
  ```

  Create `research/hr/mdm-enrolled-devices.md`:
  ```markdown
  # Miradore MDM Enrolled Devices
  Updated: 2026-05-16

  | # | Assigned to | Ruolo | Enrollment date | Compliant |
  |---|---|---|---|---|
  | 001 | Asya | Platform | — | — |
  | 002 | Vino | Marketing | — | — |
  | 003 | Krisna | LKPM | — | — |
  | 004 | Adit | Operations | — | — |
  | 005 | Ari Firda | Visa | — | — |
  | 006 | Dea | — | — | — |
  | 007 | Surya | Tax | — | — |
  | 008 | Damar | Marketing | — | — |
  | 009 | Sahira | Sales | — | — |
  | 010 | Rina | Reception | — | — |
  | 011-015 | Spare/Tax dept | — | — | — |
  ```

- [ ] **Step 5: Set compliance alert**

  Miradore → Alerts → create: "Device non-compliant for >24h" → notify `zero@balizero.com`.

---

## Task 3: Telegram WA Linked Devices audit bot

**Files:**
- Create: `scripts/wa-audit-bot/bot.py`
- Create: `scripts/wa-audit-bot/requirements.txt`
- Create: `~/Library/LaunchAgents/com.balizero.wa-audit-bot.plist`

- [ ] **Step 1: Create Telegram bot and group**

  1. Message `@BotFather` → `/newbot` → name `BaliZero WA Audit` → username `balizero_wa_audit_bot`
  2. Save bot token
  3. Create Telegram group `BaliZero - WA Audit Settimanale`
  4. Add bot as admin, add all 10 employee Telegram accounts
  5. Get group chat_id: send any message in group, then:
     ```bash
     curl "https://api.telegram.org/bot<TOKEN>/getUpdates" | python3 -m json.tool | grep -A2 '"chat"'
     ```
     Group chat_id is a negative number (e.g. `-1001234567890`).

- [ ] **Step 2: Write requirements.txt**

  Create `scripts/wa-audit-bot/requirements.txt`:
  ```
  python-telegram-bot==20.7
  ```

- [ ] **Step 3: Write bot.py**

  Create `scripts/wa-audit-bot/bot.py`:
  ```python
  import os
  import logging
  from datetime import time
  from zoneinfo import ZoneInfo
  from telegram import Update
  from telegram.ext import Application, MessageHandler, filters, ContextTypes

  logging.basicConfig(
      format="%(asctime)s %(levelname)s %(message)s",
      level=logging.INFO,
  )
  logger = logging.getLogger(__name__)

  BOT_TOKEN = os.environ["WA_AUDIT_BOT_TOKEN"]
  AUDIT_GROUP_CHAT_ID = int(os.environ["WA_AUDIT_GROUP_CHAT_ID"])
  MANAGEMENT_CHAT_ID = int(os.environ["TELEGRAM_OWNER_CHAT_ID"])
  WITA = ZoneInfo("Asia/Makassar")

  # Fill in after Step 5 below: Telegram user_id → display name
  EMPLOYEES: dict[int, str] = {
      # example: 123456789: "Surya",
  }

  # week_key → set of user_ids who submitted
  submissions: dict[str, set[int]] = {}

  async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
      msg = update.message
      if not msg or msg.chat_id != AUDIT_GROUP_CHAT_ID:
          return
      from datetime import datetime
      now = datetime.now(WITA)
      week_key = now.strftime("%Y-W%W")
      user_id = msg.from_user.id
      submissions.setdefault(week_key, set()).add(user_id)
      name = EMPLOYEES.get(user_id, f"user_{user_id}")
      logger.info("Screenshot received: %s week=%s", name, week_key)
      if now.weekday() == 0 and now.time() > time(10, 0):
          await context.bot.send_message(
              MANAGEMENT_CHAT_ID,
              f"⚠️ WA Audit: {name} ha inviato screenshot dopo le 10:00 WITA ({now.strftime('%H:%M')}). Penale Rp 2jt applicabile."
          )
      else:
          await msg.reply_text("✅ Ricevuto. Grazie.")

  async def monday_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
      await context.bot.send_message(
          AUDIT_GROUP_CHAT_ID,
          "📱 *Audit WA settimanale*\n\nEntro le 10:00 WITA:\n1. Apri WA Business\n2. Menu → Dispositivi collegati\n3. Screenshot → invia qui\n\nMancato invio = Rp 2.000.000 (contratto Lampiran V)",
          parse_mode="Markdown",
      )

  async def monday_check(context: ContextTypes.DEFAULT_TYPE) -> None:
      from datetime import datetime
      now = datetime.now(WITA)
      week_key = now.strftime("%Y-W%W")
      submitted = submissions.get(week_key, set())
      missing = [name for uid, name in EMPLOYEES.items() if uid not in submitted]
      if missing:
          names = "\n".join(f"  • {n}" for n in missing)
          await context.bot.send_message(
              MANAGEMENT_CHAT_ID,
              f"🚨 WA Audit — screenshot mancanti:\n{names}\n\nPenale Rp 2.000.000 per dipendente."
          )
      else:
          await context.bot.send_message(
              MANAGEMENT_CHAT_ID,
              f"✅ WA Audit {week_key}: tutti i 10 screenshot ricevuti."
          )

  def main() -> None:
      app = Application.builder().token(BOT_TOKEN).build()
      app.add_handler(MessageHandler(
          filters.PHOTO & filters.Chat(AUDIT_GROUP_CHAT_ID),
          handle_photo,
      ))
      # Monday 09:00 WITA = 01:00 UTC
      app.job_queue.run_daily(monday_reminder, time=time(1, 0), days=(0,))
      # Monday 10:05 WITA = 02:05 UTC
      app.job_queue.run_daily(monday_check, time=time(2, 5), days=(0,))
      logger.info("WA Audit Bot running")
      app.run_polling(drop_pending_updates=True)

  if __name__ == "__main__":
      main()
  ```

- [ ] **Step 4: Install and test manually**

  ```bash
  cd ~/scripts/wa-audit-bot
  python3 -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  ```

  ```bash
  export WA_AUDIT_BOT_TOKEN="<token>"
  export WA_AUDIT_GROUP_CHAT_ID="<negative-group-id>"
  export TELEGRAM_OWNER_CHAT_ID="1125336968"
  python bot.py
  ```

  In the Telegram audit group: send a test photo → bot replies "✅ Ricevuto. Grazie."

- [ ] **Step 5: Fill EMPLOYEES dict**

  Get each employee's Telegram user_id: have each one send any message to `@balizero_wa_audit_bot` directly, then:
  ```bash
  curl "https://api.telegram.org/bot<TOKEN>/getUpdates" | python3 -c "
  import sys, json
  for u in json.load(sys.stdin).get('result', []):
      m = u.get('message', {})
      f = m.get('from', {})
      print(f\"{f.get('first_name')} {f.get('last_name','')}: {f.get('id')}\")
  "
  ```
  Fill `EMPLOYEES` dict in `bot.py` with the results.

- [ ] **Step 6: Create LaunchAgent**

  Create `~/Library/LaunchAgents/com.balizero.wa-audit-bot.plist`:
  ```xml
  <?xml version="1.0" encoding="UTF-8"?>
  <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
  <plist version="1.0">
  <dict>
      <key>Label</key>
      <string>com.balizero.wa-audit-bot</string>
      <key>ProgramArguments</key>
      <array>
          <string>/Users/nuzantara/scripts/wa-audit-bot/.venv/bin/python</string>
          <string>/Users/nuzantara/scripts/wa-audit-bot/bot.py</string>
      </array>
      <key>EnvironmentVariables</key>
      <dict>
          <key>WA_AUDIT_BOT_TOKEN</key>
          <string>REPLACE_WITH_BOT_TOKEN</string>
          <key>WA_AUDIT_GROUP_CHAT_ID</key>
          <string>REPLACE_WITH_GROUP_CHAT_ID</string>
          <key>TELEGRAM_OWNER_CHAT_ID</key>
          <string>1125336968</string>
      </dict>
      <key>KeepAlive</key>
      <true/>
      <key>RunAtLoad</key>
      <true/>
      <key>StandardOutPath</key>
      <string>/Users/nuzantara/logs/wa-audit-bot.log</string>
      <key>StandardErrorPath</key>
      <string>/Users/nuzantara/logs/wa-audit-bot.err</string>
  </dict>
  </plist>
  ```

  Replace `REPLACE_WITH_BOT_TOKEN` and `REPLACE_WITH_GROUP_CHAT_ID` with actual values.

  ```bash
  chmod 0400 ~/Library/LaunchAgents/com.balizero.wa-audit-bot.plist
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wa-audit-bot.plist
  launchctl print gui/$(id -u)/com.balizero.wa-audit-bot
  ```

  Expected: `state = running`.

- [ ] **Step 7: Commit**

  ```bash
  git add scripts/wa-audit-bot/
  git commit -m "feat(wa-audit): add WA Linked Devices weekly audit Telegram bot"
  ```

---

## SIM Registry

- [ ] **Create registry (not in git)**

  `research/hr/sim-registry.md` — già in `.gitignore` dal Task 2.

  ```markdown
  # SIM Corporate Registry — Bali Zero
  Confidenziale. Non committare. Non condividere fuori dal management.
  Aggiornato: 2026-05-16

  Protocollo exit: sospendere SIM su portale Telkomsel Business PRIMA che il dipendente lasci l'edificio.

  | # | Numero E.164 | Assigned to | SIM PIN set | MDM enrolled | Exit date |
  |---|---|---|---|---|---|
  | 001 | +62-XXX | Asya | — | — | — |
  | 002 | +62-XXX | Vino | — | — | — |
  | 003 | +62-XXX | Krisna | — | — | — |
  | 004 | +62-XXX | Adit | — | — | — |
  | 005 | +62-XXX | Ari Firda | — | — | — |
  | 006 | +62-XXX | Dea | — | — | — |
  | 007 | +62-XXX | Surya | — | — | — |
  | 008 | +62-XXX | Damar | — | — | — |
  | 009 | +62-XXX | Sahira | — | — | — |
  | 010 | +62-XXX | Rina | — | — | — |
  | 011-015 | +62-XXX | Spare/Tax | — | — | — |
  ```
