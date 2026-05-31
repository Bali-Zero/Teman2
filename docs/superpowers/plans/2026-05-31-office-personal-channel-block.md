# Office Personal-Channel Block — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Block personal WhatsApp/Telegram **Web** on Bali Zero corporate computers via per-device NextDNS, with tamper-detection that flags any device whose profile is removed (employees are Admin, so removal is detected, not prevented).

**Architecture:** Three deterrent layers — (1) per-device NextDNS DoH profile blocks the web channels; (2) a PKWTT contract clause forbids removing it; (3) a weekly Python tamper-detection digest on the Pro flags devices that stop reporting to NextDNS (= profile removed) to the operator's private Telegram. C1/C3/Step-0 are config/operator actions; C2/C4 are the only code.

**Tech Stack:** NextDNS (free tier) · macOS `.mobileconfig` DNSSettings (DoH) · `/usr/bin/profiles` · bash (`setup-balizero.sh` extension) · Python 3.11 (tamper-detection digest) · NextDNS Analytics API · Telegram Bot API.

**Spec:** `docs/superpowers/specs/2026-05-31-office-personal-channel-block-design.md`

---

## Nature of this plan

Two task types:

- **CONFIG/OPERATOR tasks** (Step 0, C1, C3) — manual actions by Antonello (NextDNS console, contract, Windows install). Given as exact checklists, not TDD — they are not repo code.
- **CODE tasks** (C2, C4) — real repo changes with tests where testable.

Sequencing: Step 0 (contract) ∥ C1 (NextDNS) first → C2 (Mac) → C3 (Windows) → C4 (tamper-detection, required).

---

## File Structure

| File                                                                     | Status                                                          | Responsibility                                                            |
| ------------------------------------------------------------------------ | --------------------------------------------------------------- | ------------------------------------------------------------------------- |
| `scripts/profile-monitor/mac-client/balizero-nextdns.mobileconfig`       | Create (asset, generated from NextDNS)                          | The DoH DNS profile installed on every Mac                                |
| `scripts/profile-monitor/mac-client/setup-balizero.sh`                   | Modify                                                          | Add STEP that installs the `.mobileconfig`                                |
| `scripts/nextdns-tamper-detect.py`                                       | Create                                                          | Weekly: per-device last-seen + blocked-attempts → private Telegram digest |
| `scripts/tests/test_nextdns_tamper_detect.py`                            | Create                                                          | Unit tests for the detection logic (pure functions, no network)           |
| `research/hr/device-enrollment-registry.md`                              | Create (gitignored, `research/hr/` already in `.gitignore:550`) | device-label → employee mapping, so "device X silent" → a person          |
| `~/Library/LaunchAgents/com.balizero.nextdns-tamper-detect.weekly.plist` | Create (HOME, not repo)                                         | Weekly schedule for the digest                                            |

Existing `scripts/nextdns-weekly-digest.sh` (top-20 domains) is **left untouched** — different purpose; C4 is the tamper-detection complement, not a replacement.

---

## Step 0 (PREREQUISITE, operator/HR): Contract clause

**This is not code. It is the spine of enforcement — do it first or in parallel.**

- [ ] **0.1 — Check the signed PKWTT / handbook for a device-security clause**

  Open the signed contracts (`~/Desktop/PKWTT-Contratti-2026-05-19/`) and the Employee Handbook. Look for any clause covering "company device security configuration must not be removed/disabled/bypassed."

- [ ] **0.2 — If absent, draft an addendum**

  Draft one paragraph (Bahasa Indonesia, since it's for the team) stating: the company DNS/security profile installed on corporate devices must not be removed, disabled, or circumvented; doing so is a disciplinary breach (`pelanggaran`). Have each employee sign it. Without this, a detected removal cannot be acted on.

  > Acceptance: every active employee has signed either the original clause or the addendum. Until then, C4's alerts are informational only.

---

## C1 (CONFIG, operator): NextDNS profile

**Not code. NextDNS console actions. ~30 min.**

- [ ] **C1.1 — Create / confirm the NextDNS profile**

  `https://nextdns.io` → sign in `zero@balizero.com` → profile `BaliZero-Office` (reuse if it already exists from the 2026-05-16 plan; free tier 300k queries/month).

- [ ] **C1.2 — Add the denylist**

  Profile → Denylist → add:
  - `web.whatsapp.com`
  - `web.telegram.org`
  - `webk.telegram.org`
  - `webz.telegram.org`

- [ ] **C1.3 — Enable logging**

  Profile → Logs → enable, retention 30 days. (Feeds C4 tamper-detection.)

- [ ] **C1.4 — Record the profile ID + API key into secrets**

  From `nextdns.io/account` (API key) and the profile URL (profile ID), add to `~/.nuzantara-secrets.env` if not already present:

  ```
  NEXTDNS_API_KEY=...
  NEXTDNS_PROFILE_ID=...
  ```

  (Reused by both the existing digest and C4.)

- [ ] **C1.5 — Smoke test the block on one device**

  Point any one device's DNS at the NextDNS profile DoH URL, then visit `https://web.whatsapp.com` → must fail to resolve/load. Visit a normal site → must load. Confirm the device appears in NextDNS → Logs.

  > Acceptance: WA Web blocked, normal browsing intact, device visible in logs.

---

## C2 (CODE): macOS `.mobileconfig` delivery via `setup-balizero.sh`

**Files:**

- Create: `scripts/profile-monitor/mac-client/balizero-nextdns.mobileconfig`
- Modify: `scripts/profile-monitor/mac-client/setup-balizero.sh` (add a STEP after STEP 3)

- [ ] **C2.1 — Generate the `.mobileconfig` from NextDNS**

  In the NextDNS `BaliZero-Office` setup page → **Apple** → "Download Configuration Profile" (this produces a DNSSettings/DoH `.mobileconfig` pinned to the profile). Save it as:

  ```
  scripts/profile-monitor/mac-client/balizero-nextdns.mobileconfig
  ```

  Verify it is a valid plist:

  ```bash
  plutil -lint scripts/profile-monitor/mac-client/balizero-nextdns.mobileconfig
  ```

  Expected: `... OK`

- [ ] **C2.2 — Add the install STEP to `setup-balizero.sh`**

  In `scripts/profile-monitor/mac-client/setup-balizero.sh`, the existing steps are STEP 0..4 (the banner says "STEP N/4"). Insert a new DNS step **after STEP 3 (Handbook), before STEP 4 (summary)**. Also bump the banner counters 0/4→0/5 etc. (cosmetic). Insert this block immediately before the `# ─── STEP 4: Test end-to-end` line:

  ```bash
  # ─── STEP 3.5: Profilo DNS NextDNS (blocco WA/Telegram Web) ─────────────
  echo "━━━ STEP 4/5 — Installazione profilo DNS NextDNS ━━━"

  MOBILECONFIG="$SCRIPT_DIR/balizero-nextdns.mobileconfig"
  if [[ ! -f "$MOBILECONFIG" ]]; then
      echo "❌ Profilo NextDNS non trovato: $MOBILECONFIG"
      echo "   Generalo da nextdns.io (profilo BaliZero-Office → Apple → Download Configuration Profile)"
      exit 1
  fi

  if ! plutil -lint "$MOBILECONFIG" >/dev/null 2>&1; then
      echo "❌ Profilo NextDNS non è un plist valido: $MOBILECONFIG"
      exit 1
  fi

  echo "   Installo profilo DNS (apre System Settings per conferma)…"
  # macOS 13+ richiede review manuale: il doppio-click apre System Settings → Profiles.
  # In ambiente non supervisionato non si può installare un config profile via CLI senza MDM.
  open "$MOBILECONFIG"
  echo ""
  echo "   👉 AZIONE MANUALE: System Settings → Privacy & Security → Profiles →"
  echo "      'NextDNS BaliZero-Office' → Install. Inserisci la password admin."
  echo ""
  read -r -p "   Premi INVIO dopo aver installato il profilo… " _

  # Verifica installazione
  if profiles list -all 2>/dev/null | grep -qi "nextdns\|BaliZero-Office"; then
      echo "✅ Profilo DNS NextDNS installato e attivo"
  else
      echo "⚠️  Profilo non rilevato in 'profiles list'. Verifica manuale in System Settings → Profiles."
      echo "    (Il setup continua; il profilo va installato perché il blocco sia attivo.)"
  fi
  echo ""
  ```

  > Note: macOS 13+ does **not** allow silent CLI install of a config profile on an unsupervised Mac — `profiles install` requires MDM enrollment. Hence the `open` + manual-confirm flow. This is a platform constraint, not a shortcut.

- [ ] **C2.3 — Static-check the modified script**

  Run:

  ```bash
  bash -n scripts/profile-monitor/mac-client/setup-balizero.sh
  ```

  Expected: no output (syntax OK).

- [ ] **C2.4 — Verify the block end-to-end on a test Mac profile**

  On a throwaway/test `balizero` profile, run `bash setup-balizero.sh <name>` through the new STEP, install the profile when prompted, then:

  ```bash
  dig web.whatsapp.com
  ```

  Expected: NextDNS returns the block response (NXDOMAIN or 0.0.0.0 per profile config); `web.whatsapp.com` does not load in a browser; a normal site loads.

- [ ] **C2.5 — Commit**

  ```bash
  git add scripts/profile-monitor/mac-client/balizero-nextdns.mobileconfig scripts/profile-monitor/mac-client/setup-balizero.sh
  git commit -m "feat(hr): install NextDNS DoH profile in setup-balizero.sh — block WA/Telegram Web on corporate Macs"
  ```

---

## C3 (CONFIG, operator): Windows delivery (Adit)

**Not code. Vendor installer on Adit's Windows PC.**

- [ ] **C3.1 — Install the NextDNS Windows client**

  On Adit's PC: download the NextDNS client from `https://nextdns.io/download` (Windows) → configure it with the `BaliZero-Office` profile ID → enable.

- [ ] **C3.2 — Verify the block + reporting**

  In a browser on the PC: `web.whatsapp.com` must fail; a normal site loads; the device appears in NextDNS → Logs as a distinct device.

  > Acceptance: WA Web blocked on Windows, device visible in NextDNS logs (so C4 can track it).

---

## C4 (CODE, REQUIRED): Tamper-detection digest

The load-bearing layer. Without it, an Admin employee removing the profile is invisible.

**Files:**

- Create: `scripts/nextdns-tamper-detect.py`
- Create: `scripts/tests/test_nextdns_tamper_detect.py`
- Create: `research/hr/device-enrollment-registry.md` (gitignored)
- Create: `~/Library/LaunchAgents/com.balizero.nextdns-tamper-detect.weekly.plist`

### C4a — The enrollment registry (data)

- [ ] **C4a.1 — Create the registry file**

  `research/hr/device-enrollment-registry.md` (already gitignored via `research/hr/`):

  ```markdown
  # NextDNS Device Enrollment Registry — Bali Zero

  Confidenziale. Non committare (research/hr/ è gitignored).
  Aggiornato: 2026-05-31

  device_label maps a NextDNS device name (Settings → Devices) → employee.
  Un device che SPARISCE dai log NextDNS = profilo rimosso = breach candidate.

  | device_label (NextDNS) | Employee | OS  | Enrolled | Notes |
  | ---------------------- | -------- | --- | -------- | ----- |
  |                        |          |     |          |       |
  ```

  Fill rows as each device is enrolled in C2/C3.

### C4b — Detection logic (pure functions, TDD)

- [ ] **C4b.1 — Write the failing test**

  `scripts/tests/test_nextdns_tamper_detect.py`:

  ```python
  from datetime import datetime, timezone, timedelta
  import sys, os
  sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
  from nextdns_tamper_detect import find_silent_devices, count_blocked_attempts

  NOW = datetime(2026, 5, 31, 8, 0, tzinfo=timezone.utc)

  def test_device_silent_beyond_threshold_is_flagged():
      # enrolled devices: surya, adit. NextDNS reports only adit recently.
      enrolled = ["surya-mac", "adit-win"]
      last_seen = {
          "adit-win": NOW - timedelta(hours=2),
          "surya-mac": NOW - timedelta(days=5),
      }
      silent = find_silent_devices(enrolled, last_seen, now=NOW, threshold_days=3)
      assert silent == ["surya-mac"]

  def test_device_never_seen_is_flagged():
      enrolled = ["surya-mac", "adit-win"]
      last_seen = {"adit-win": NOW - timedelta(hours=1)}  # surya never reported
      silent = find_silent_devices(enrolled, last_seen, now=NOW, threshold_days=3)
      assert silent == ["surya-mac"]

  def test_all_reporting_returns_empty():
      enrolled = ["surya-mac", "adit-win"]
      last_seen = {"surya-mac": NOW - timedelta(hours=1), "adit-win": NOW - timedelta(hours=1)}
      assert find_silent_devices(enrolled, last_seen, now=NOW, threshold_days=3) == []

  def test_count_blocked_attempts_groups_by_device():
      logs = [
          {"device": {"name": "surya-mac"}, "domain": "web.whatsapp.com", "status": "blocked"},
          {"device": {"name": "surya-mac"}, "domain": "web.whatsapp.com", "status": "blocked"},
          {"device": {"name": "adit-win"}, "domain": "web.telegram.org", "status": "blocked"},
          {"device": {"name": "surya-mac"}, "domain": "google.com", "status": "default"},
      ]
      counts = count_blocked_attempts(logs, denylist={"web.whatsapp.com", "web.telegram.org"})
      assert counts == {"surya-mac": 2, "adit-win": 1}
  ```

- [ ] **C4b.2 — Run the test, verify it fails**

  Run:

  ```bash
  cd scripts && python3 -m pytest tests/test_nextdns_tamper_detect.py -v
  ```

  Expected: FAIL — `ModuleNotFoundError: No module named 'nextdns_tamper_detect'`

- [ ] **C4b.3 — Write the pure-function core**

  `scripts/nextdns-tamper-detect.py` (the importable name is `nextdns_tamper_detect` — the file is hyphen, so the test imports work only if invoked as a module path; create the file ALSO importable: name it `scripts/nextdns_tamper_detect.py` with underscores to match the import). **Create `scripts/nextdns_tamper_detect.py`:**

  ```python
  #!/usr/bin/env python3
  """NextDNS tamper-detection + blocked-attempt digest → private Telegram.

  Detects corporate devices that stopped reporting to NextDNS (profile removed
  by an Admin employee) and counts blocked WA/Telegram-Web attempts per device.
  Sends a digest to the operator's Telegram chat only.
  """
  from __future__ import annotations

  import os
  import sys
  import json
  import urllib.request
  import urllib.parse
  from datetime import datetime, timezone, timedelta

  DENYLIST = {"web.whatsapp.com", "web.telegram.org", "webk.telegram.org", "webz.telegram.org"}
  THRESHOLD_DAYS = 3


  def find_silent_devices(
      enrolled: list[str],
      last_seen: dict[str, datetime],
      now: datetime,
      threshold_days: int = THRESHOLD_DAYS,
  ) -> list[str]:
      """Return enrolled devices whose last NextDNS report is older than the
      threshold, or that never reported at all. Sorted for stable output."""
      cutoff = now - timedelta(days=threshold_days)
      silent = []
      for dev in enrolled:
          seen = last_seen.get(dev)
          if seen is None or seen < cutoff:
              silent.append(dev)
      return sorted(silent)


  def count_blocked_attempts(
      logs: list[dict], denylist: set[str] = DENYLIST
  ) -> dict[str, int]:
      """Count blocked denylist hits per device name from NextDNS log rows."""
      counts: dict[str, int] = {}
      for row in logs:
          if row.get("status") != "blocked":
              continue
          if row.get("domain") not in denylist:
              continue
          name = (row.get("device") or {}).get("name", "unknown")
          counts[name] = counts.get(name, 0) + 1
      return counts
  ```

  And **rename the test import** accordingly (already `from nextdns_tamper_detect import ...` — matches the underscore filename).

- [ ] **C4b.4 — Run the test, verify it passes**

  Run:

  ```bash
  cd scripts && python3 -m pytest tests/test_nextdns_tamper_detect.py -v
  ```

  Expected: 4 passed.

- [ ] **C4b.5 — Commit the core**

  ```bash
  git add scripts/nextdns_tamper_detect.py scripts/tests/test_nextdns_tamper_detect.py
  git commit -m "feat(hr): NextDNS tamper-detection core — find_silent_devices + count_blocked_attempts (TDD)"
  ```

### C4c — I/O wiring (NextDNS API + registry + Telegram)

- [ ] **C4c.1 — Add the I/O `main()` to `scripts/nextdns_tamper_detect.py`**

  Append below the pure functions:

  ```python
  def _load_enrolled(registry_path: str) -> list[str]:
      """Parse device_label column from the markdown registry table."""
      devices = []
      try:
          with open(os.path.expanduser(registry_path)) as f:
              for line in f:
                  line = line.strip()
                  if not line.startswith("|"):
                      continue
                  cols = [c.strip() for c in line.strip("|").split("|")]
                  label = cols[0] if cols else ""
                  if label and label.lower() not in ("device_label (nextdns)", "---", ""):
                      devices.append(label)
      except FileNotFoundError:
          pass
      return devices


  def _fetch_nextdns_logs(api_key: str, profile_id: str, from_iso: str) -> list[dict]:
      url = (
          f"https://api.nextdns.io/profiles/{profile_id}/logs"
          f"?from={urllib.parse.quote(from_iso)}&limit=1000"
      )
      req = urllib.request.Request(url, headers={"X-Api-Key": api_key})
      with urllib.request.urlopen(req, timeout=20) as resp:
          return json.loads(resp.read()).get("data", [])


  def _last_seen_from_logs(logs: list[dict]) -> dict[str, datetime]:
      seen: dict[str, datetime] = {}
      for row in logs:
          name = (row.get("device") or {}).get("name")
          ts = row.get("timestamp")
          if not name or not ts:
              continue
          dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
          if name not in seen or dt > seen[name]:
              seen[name] = dt
      return seen


  def _send_telegram(token: str, chat_id: str, text: str) -> None:
      url = f"https://api.telegram.org/bot{token}/sendMessage"
      data = urllib.parse.urlencode(
          {"chat_id": chat_id, "parse_mode": "HTML", "text": text}
      ).encode()
      urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20).read()


  def build_digest(silent: list[str], blocked: dict[str, int]) -> str:
      lines = ["🛡️ <b>NextDNS Tamper-Detection (settimanale)</b>", ""]
      if silent:
          lines.append("🚨 <b>Device SPARITI dai log (profilo rimosso?):</b>")
          lines += [f"  • <code>{d}</code>" for d in silent]
          lines.append("→ verifica + clausola contratto (rimozione = pelanggaran)")
      else:
          lines.append("✅ Tutti i device enrolled riportano. 0 silenti.")
      lines.append("")
      if blocked:
          lines.append("📵 <b>Tentativi WA/Telegram Web bloccati:</b>")
          lines += [f"  • {d}: {n}" for d, n in sorted(blocked.items(), key=lambda x: -x[1])]
      else:
          lines.append("📵 0 tentativi bloccati questa settimana.")
      return "\n".join(lines)


  def main() -> int:
      api_key = os.environ.get("NEXTDNS_API_KEY")
      profile_id = os.environ.get("NEXTDNS_PROFILE_ID")
      tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
      tg_chat = os.environ.get("TELEGRAM_OWNER_CHAT_ID")
      registry = os.environ.get(
          "NEXTDNS_DEVICE_REGISTRY",
          os.path.expanduser("~/Desktop/nuzantara/research/hr/device-enrollment-registry.md"),
      )
      if not all([api_key, profile_id, tg_token, tg_chat]):
          print("[tamper-detect] missing env (NEXTDNS_*/TELEGRAM_*) — aborting", file=sys.stderr)
          return 1

      now = datetime.now(timezone.utc)
      from_iso = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
      enrolled = _load_enrolled(registry)
      try:
          logs = _fetch_nextdns_logs(api_key, profile_id, from_iso)
      except Exception as e:  # noqa: BLE001 — never silently skip (W55/W61 lesson)
          _send_telegram(tg_token, tg_chat, f"⚠️ NextDNS tamper-detect: API error: {e}")
          return 1

      silent = find_silent_devices(enrolled, _last_seen_from_logs(logs), now=now)
      blocked = count_blocked_attempts(logs)
      _send_telegram(tg_token, tg_chat, build_digest(silent, blocked))
      print(f"[tamper-detect] sent: {len(silent)} silent, {sum(blocked.values())} blocked attempts")
      return 0


  if __name__ == "__main__":
      raise SystemExit(main())
  ```

- [ ] **C4c.2 — Add a `build_digest` empty-state test**

  Append to `scripts/tests/test_nextdns_tamper_detect.py`:

  ```python
  from nextdns_tamper_detect import build_digest

  def test_digest_empty_state_says_zero_not_blank():
      msg = build_digest(silent=[], blocked={})
      assert "0 silenti" in msg
      assert "0 tentativi bloccati" in msg

  def test_digest_flags_silent_device():
      msg = build_digest(silent=["surya-mac"], blocked={"surya-mac": 3})
      assert "surya-mac" in msg
      assert "SPARITI" in msg
  ```

- [ ] **C4c.3 — Run all tests, verify pass**

  Run:

  ```bash
  cd scripts && python3 -m pytest tests/test_nextdns_tamper_detect.py -v
  ```

  Expected: 6 passed.

- [ ] **C4c.4 — Commit the I/O layer**

  ```bash
  git add scripts/nextdns_tamper_detect.py scripts/tests/test_nextdns_tamper_detect.py
  git commit -m "feat(hr): NextDNS tamper-detect I/O — registry parse + logs fetch + private Telegram digest"
  ```

### C4d — Schedule (LaunchAgent, HOME not repo)

- [ ] **C4d.1 — Create the weekly LaunchAgent**

  `~/Library/LaunchAgents/com.balizero.nextdns-tamper-detect.weekly.plist` (Monday 09:00 WITA = 01:00 UTC):

  ```xml
  <?xml version="1.0" encoding="UTF-8"?>
  <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
  <plist version="1.0">
  <dict>
      <key>Label</key><string>com.balizero.nextdns-tamper-detect.weekly</string>
      <key>ProgramArguments</key>
      <array>
          <string>/bin/bash</string>
          <string>-lc</string>
          <string>source ~/.nuzantara-secrets.env &amp;&amp; /opt/homebrew/bin/python3 ~/Desktop/nuzantara/scripts/nextdns_tamper_detect.py</string>
      </array>
      <key>StartCalendarInterval</key>
      <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>1</integer><key>Minute</key><integer>0</integer></dict>
      <key>StandardOutPath</key><string>/Users/nuzantara/logs/nextdns-tamper-detect.log</string>
      <key>StandardErrorPath</key><string>/Users/nuzantara/logs/nextdns-tamper-detect.err</string>
  </dict>
  </plist>
  ```

- [ ] **C4d.2 — Load + dry-run it**

  ```bash
  launchctl bootout gui/$(id -u)/com.balizero.nextdns-tamper-detect.weekly 2>/dev/null || true
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.nextdns-tamper-detect.weekly.plist
  launchctl kickstart -k gui/$(id -u)/com.balizero.nextdns-tamper-detect.weekly
  ```

  Expected: a Telegram digest arrives in chat `1125336968` (with whatever devices/blocks exist so far). Confirms the whole chain.

  > Acceptance: digest received; if registry is still empty it says "0 silenti / 0 tentativi" (empty-state correct, not a crash).

---

## Self-review notes

- **Spec coverage:** Step 0 (contract) ✓, C1 (NextDNS) ✓, C2 (macOS mobileconfig + setup-balizero.sh) ✓, C3 (Windows) ✓, C4 (tamper-detection digest + registry, load-bearing) ✓. Enforcement 3-layer model fully reflected (friction=C1/C2/C3, contract=Step 0, detection=C4). Honest limits live in the spec, not re-litigated here.
- **Import-name fix:** the importable module is `scripts/nextdns_tamper_detect.py` (underscores) so `from nextdns_tamper_detect import ...` resolves; the spec's prose "nextdns-tamper-detect.py" is reconciled to the underscore filename in C4b.3. No hyphen file is created.
- **No silent failure:** C4 `main()` sends an error Telegram on API failure rather than skipping (W55/W61 cicatrix lesson), and empty-state sends "0" so a quiet week ≠ broken cron.
- **Function-name consistency:** `find_silent_devices`, `count_blocked_attempts`, `build_digest` used identically in tests and impl.
